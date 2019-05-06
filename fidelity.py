from csvsectionslicer import parseSectionsForCSV, CSVSectionCriterion, CSVSectionResult
from datetime import date, datetime
from decimal import Decimal
from enum import IntEnum, unique
from model import Activity, Cash, Currency, Instrument, Stock, Bond, Option, OptionType, Position, Trade, TradeFlags
from parsetools import lenientParse
from pathlib import Path
from sys import stderr
from typing import Callable, Dict, List, NamedTuple, Optional, Set
from warnings import warn

import csv
import re


class FidelityPosition(NamedTuple):
    symbol: str
    description: str
    quantity: str
    price: str
    beginningValue: str
    endingValue: str
    costBasis: str


InstrumentFactory = Callable[[FidelityPosition], Instrument]


def parseFidelityPosition(p: FidelityPosition,
                          instrumentFactory: InstrumentFactory) -> Position:
    qty = Decimal(p.quantity)
    return Position(instrument=instrumentFactory(p),
                    quantity=qty,
                    costBasis=Cash(currency=Currency.USD,
                                   quantity=Decimal(p.costBasis)))


@unique
class FidelityMonth(IntEnum):
    JAN = 1,
    FEB = 2,
    MAR = 3,
    APR = 4,
    MAY = 5,
    JUN = 6,
    JUL = 7,
    AUG = 8,
    SEP = 9,
    OCT = 10,
    NOV = 11,
    DEC = 12


def parseOptionsPosition(description: str) -> Option:
    match = re.match(
        r'^(?P<putCall>CALL|PUT) \((?P<underlying>[A-Z]+)\) .+ (?P<month>[A-Z]{3}) (?P<day>\d{2}) (?P<year>\d{2}) \$(?P<strike>[0-9\.]+) \(100 SHS\)$',
        description)
    if not match:
        raise ValueError(
            f'Could not parse Fidelity options description: {description}')

    if match['putCall'] == 'PUT':
        optionType = OptionType.PUT
    else:
        optionType = OptionType.CALL

    month = FidelityMonth[match['month']]
    year = datetime.strptime(match['year'], '%y').year

    return Option(underlying=match['underlying'],
                  currency=Currency.USD,
                  expiration=date(year, month, int(match['day'])),
                  optionType=optionType,
                  strike=Decimal(match['strike']))


def parsePositions(path: Path, lenient: bool = False) -> List[Position]:
    with open(path, newline='') as csvfile:
        stocksCriterion = CSVSectionCriterion(startSectionRowMatch=["Stocks"],
                                              endSectionRowMatch=[""],
                                              rowFilter=lambda r: r[0:7])
        bondsCriterion = CSVSectionCriterion(startSectionRowMatch=["Bonds"],
                                             endSectionRowMatch=[""],
                                             rowFilter=lambda r: r[0:7])
        optionsCriterion = CSVSectionCriterion(
            startSectionRowMatch=["Options"],
            endSectionRowMatch=["", ""],
            rowFilter=lambda r: r[0:7])

        instrumentBySection: Dict[CSVSectionCriterion, InstrumentFactory] = {
            stocksCriterion: lambda p: Stock(p.symbol, currency=Currency.USD),
            bondsCriterion: lambda p: Bond(p.symbol, currency=Currency.USD),
            optionsCriterion: lambda p: parseOptionsPosition(p.description),
        }

        sections = parseSectionsForCSV(
            csvfile, [stocksCriterion, bondsCriterion, optionsCriterion])

        positions: List[Position] = []

        for sec in sections:
            for r in sec.rows:
                pos = parseFidelityPosition(FidelityPosition._make(r),
                                            instrumentBySection[sec.criterion])
                positions.append(pos)

        return positions


class FidelityTransaction(NamedTuple):
    date: str
    account: str
    action: str
    symbol: str
    description: str
    securityType: str
    exchangeQuantity: str
    exchangeCurrency: str
    quantity: str
    currency: str
    price: str
    exchangeRate: str
    commission: str
    fees: str
    accruedInterest: str
    amount: str
    settlementDate: str


def parseOptionTransaction(symbol: str) -> Option:
    match = re.match(
        r'^-(?P<underlying>[A-Z]+)(?P<date>\d{6})(?P<putCall>C|P)(?P<strike>[0-9\.]+)$',
        symbol)
    if not match:
        raise ValueError(f'Could not parse Fidelity options symbol: {symbol}')

    if match['putCall'] == 'P':
        optionType = OptionType.PUT
    else:
        optionType = OptionType.CALL

    return Option(underlying=match['underlying'],
                  currency=Currency.USD,
                  expiration=datetime.strptime(match['date'], '%y%m%d').date(),
                  optionType=optionType,
                  strike=Decimal(match['strike']))


def guessInstrumentFromSymbol(symbol: str) -> Instrument:
    if re.search(r'[0-9]+(C|P)[0-9]+$', symbol):
        return parseOptionTransaction(symbol)
    elif Bond.validBondSymbol(symbol):
        return Bond(symbol, currency=Currency.USD)
    else:
        return Stock(symbol, currency=Currency.USD)


def forceParseFidelityTransaction(t: FidelityTransaction,
                                  flags: TradeFlags) -> Trade:
    quantity = Decimal(t.quantity)

    totalFees = Decimal(0)
    # Fidelity's total fees include commision and fees
    if t.commission:
        totalFees += Decimal(t.commission)
    if t.fees:
        totalFees += Decimal(t.fees)

    amount = Decimal(0)
    if t.amount:
        amount = Decimal(t.amount) + totalFees

    return Trade(date=datetime.strptime(t.date, '%m/%d/%Y'),
                 instrument=guessInstrumentFromSymbol(t.symbol),
                 quantity=quantity,
                 amount=Cash(currency=Currency(t.currency), quantity=amount),
                 fees=Cash(currency=Currency(t.currency), quantity=totalFees),
                 flags=flags)


def parseFidelityTransaction(t: FidelityTransaction) -> Optional[Trade]:
    flags = None
    if t.action.startswith('YOU BOUGHT'):
        flags = TradeFlags.OPEN
    elif t.action.startswith('YOU SOLD'):
        flags = TradeFlags.CLOSE
    elif t.action.startswith('REINVESTMENT'):
        flags = TradeFlags.OPEN | TradeFlags.DRIP
    else:
        return None

    return forceParseFidelityTransaction(t, flags=flags)


# Transactions will be ordered from newest to oldest
def parseTransactions(path: Path, lenient: bool = False) -> List[Activity]:
    with open(path, newline='') as csvfile:
        transactionsCriterion = CSVSectionCriterion(
            startSectionRowMatch=["Run Date", "Account", "Action"],
            endSectionRowMatch=[],
            rowFilter=lambda r: r if len(r) >= 17 else None)

        sections = parseSectionsForCSV(csvfile, [transactionsCriterion])

        if not sections:
            return []

        return list(
            filter(
                None,
                lenientParse(
                    (FidelityTransaction._make(r) for r in sections[0].rows),
                    transform=parseFidelityTransaction,
                    lenient=lenient)))
