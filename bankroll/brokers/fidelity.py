from bankroll.csvsectionslicer import parseSectionsForCSV, CSVSectionCriterion, CSVSectionResult
from bankroll.model import Activity, Cash, Currency, Instrument, Stock, Bond, Option, OptionType, Position, DividendPayment, Trade, TradeFlags
from bankroll.parsetools import lenientParse
from datetime import date, datetime
from decimal import Decimal
from enum import IntEnum, unique
from pathlib import Path
from sys import stderr
from typing import Callable, Dict, List, NamedTuple, Optional, Set
from warnings import warn

import bankroll.configuration as configuration
import csv
import re


@unique
class Settings(configuration.Settings):
    POSITIONS = 'Positions'
    TRANSACTIONS = 'Transactions'

    @property
    def help(self) -> str:
        if self == self.POSITIONS:
            return "A local path to an exported CSV of Fidelity positions."
        elif self == self.TRANSACTIONS:
            return "A local path to an exported CSV of Fidelity transactions."
        else:
            return ""

    @classmethod
    def sectionName(cls) -> str:
        return 'Fidelity'


class _FidelityPosition(NamedTuple):
    symbol: str
    description: str
    quantity: str
    price: str
    beginningValue: str
    endingValue: str
    costBasis: str


_InstrumentFactory = Callable[[_FidelityPosition], Instrument]


def _parseFidelityPosition(p: _FidelityPosition,
                           instrumentFactory: _InstrumentFactory) -> Position:
    qty = Decimal(p.quantity)
    return Position(instrument=instrumentFactory(p),
                    quantity=qty,
                    costBasis=Cash(currency=Currency.USD,
                                   quantity=Decimal(p.costBasis)))


@unique
class _FidelityMonth(IntEnum):
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


def _parseOptionsPosition(description: str) -> Option:
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

    month = _FidelityMonth[match['month']]
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

        instrumentBySection: Dict[CSVSectionCriterion, _InstrumentFactory] = {
            stocksCriterion: lambda p: Stock(p.symbol, currency=Currency.USD),
            bondsCriterion: lambda p: Bond(p.symbol, currency=Currency.USD),
            optionsCriterion: lambda p: _parseOptionsPosition(p.description),
        }

        sections = parseSectionsForCSV(
            csvfile, [stocksCriterion, bondsCriterion, optionsCriterion])

        positions: List[Position] = []

        for sec in sections:
            for r in sec.rows:
                pos = _parseFidelityPosition(
                    _FidelityPosition._make(r),
                    instrumentBySection[sec.criterion])
                positions.append(pos)

        return positions


class _FidelityTransaction(NamedTuple):
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


def _parseOptionTransaction(symbol: str, currency: Currency) -> Option:
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
                  currency=currency,
                  expiration=datetime.strptime(match['date'], '%y%m%d').date(),
                  optionType=optionType,
                  strike=Decimal(match['strike']))


def _guessInstrumentFromSymbol(symbol: str, currency: Currency) -> Instrument:
    if re.search(r'[0-9]+(C|P)[0-9]+$', symbol):
        return _parseOptionTransaction(symbol, currency)
    elif Bond.validBondSymbol(symbol):
        return Bond(symbol, currency=currency)
    else:
        return Stock(symbol, currency=currency)


def _parseFidelityTransactionDate(datestr: str) -> datetime:
    return datetime.strptime(datestr, '%m/%d/%Y')


def _forceParseFidelityTransaction(t: _FidelityTransaction,
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

    currency = Currency(t.currency)
    return Trade(date=_parseFidelityTransactionDate(t.date),
                 instrument=_guessInstrumentFromSymbol(t.symbol, currency),
                 quantity=quantity,
                 amount=Cash(currency=currency, quantity=amount),
                 fees=Cash(currency=currency, quantity=totalFees),
                 flags=flags)


def _parseFidelityTransaction(t: _FidelityTransaction) -> Optional[Activity]:
    if t.action == 'DIVIDEND RECEIVED':
        return DividendPayment(date=_parseFidelityTransactionDate(t.date),
                               stock=Stock(t.symbol,
                                           currency=Currency(t.currency)),
                               proceeds=Cash(currency=Currency(t.currency),
                                             quantity=Decimal(t.amount)))

    flags = None
    # TODO: Handle 'OPENING TRANSACTION' and 'CLOSING TRANSACTION' text for options transactions
    if t.action.startswith('YOU BOUGHT'):
        flags = TradeFlags.OPEN
    elif t.action.startswith('YOU SOLD'):
        flags = TradeFlags.CLOSE
    elif t.action.startswith('REINVESTMENT'):
        flags = TradeFlags.OPEN | TradeFlags.DRIP

    if not flags:
        return None

    return _forceParseFidelityTransaction(t, flags=flags)


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
                    (_FidelityTransaction._make(r) for r in sections[0].rows),
                    transform=_parseFidelityTransaction,
                    lenient=lenient)))
