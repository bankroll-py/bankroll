from analysis import realizedBasisForSymbol
from collections import namedtuple
from csvsectionslicer import parseSectionsForCSV, CSVSectionCriterion, CSVSectionResult
from datetime import datetime
from decimal import Decimal
from model import Bond, Cash, Currency, Instrument, Position, Stock, Trade, TradeFlags
from parsetools import lenientParse, parseDecimal
from pathlib import Path
from typing import Dict, List, NamedTuple, Optional, Set, Tuple

import camelot
import csv
import re


class VanguardPosition(NamedTuple):
    investmentName: str
    symbol: str
    shares: str
    sharePrice: str
    totalValue: str


class VanguardTransaction(NamedTuple):
    settlementDate: str
    tradeDate: str
    symbol: str
    name: str
    transactionType: str
    accountType: str
    quantity: str
    price: str
    commissionFees: str
    amount: str


class PositionsAndTrades(NamedTuple):
    positions: List[Position]
    trades: List[Trade]


class VanguardPositionAndTrades(NamedTuple):
    position: VanguardPosition
    trades: List[Trade]


def parseVanguardDecimal(s: str) -> Decimal:
    # when negative amounts split between 2 lines we get a space after the minus sign
    return parseDecimal(s.replace('- ', '-'))


def guessInstrumentForInvestmentName(name: str) -> Instrument:
    instrument: Instrument
    if re.match(r'^.+\s\%\s.+$', name):
        # TODO: Determine valid CUSIP for bonds
        instrument = Bond(name, currency=Currency.USD, validateSymbol=False)
    else:
        instrument = Stock(name, currency=Currency.USD)

    return instrument


def parseVanguardPositionAndTrades(vpb: VanguardPositionAndTrades) -> Position:
    return parseVanguardPosition(vpb.position, vpb.trades)


def parseVanguardPosition(p: VanguardPosition,
                          trades: List[Trade]) -> Position:
    instrument: Instrument
    if len(p.symbol) > 0:
        instrument = Stock(p.symbol, currency=Currency.USD)
    else:
        instrument = guessInstrumentForInvestmentName(p.investmentName)

    qty = Decimal(p.shares)

    realizedBasis = realizedBasisForSymbol(instrument.symbol, trades)
    assert realizedBasis, ("Invalid realizedBasis: %s for %s" %
                           (realizedBasis, instrument))

    return Position(instrument=instrument,
                    quantity=qty,
                    costBasis=realizedBasis)


def __parsePositions(path: Path, trades: List[Trade],
                     lenient: bool = False) -> List[Position]:
    with open(path, newline='') as csvfile:
        criterion = CSVSectionCriterion(
            startSectionRowMatch=["Account Number"],
            endSectionRowMatch=[],
            rowFilter=lambda r: r[1:6])
        sections = parseSectionsForCSV(csvfile, [criterion])

        if len(sections) == 0:
            return []

        vanPositions = (VanguardPosition._make(r) for r in sections[0].rows)
        vanPosAndBases = list(
            map(lambda pos: VanguardPositionAndTrades(pos, trades),
                vanPositions))

        return list(
            lenientParse(vanPosAndBases,
                         transform=parseVanguardPositionAndTrades,
                         lenient=lenient))


def parsePositionsAndTrades(positionsPath: Path,
                            tradesPath: Path,
                            lenient: bool = False) -> PositionsAndTrades:
    trades = __parseActivityPDF(tradesPath, lenient=lenient)
    positions = __parsePositions(positionsPath, trades=trades, lenient=lenient)
    return PositionsAndTrades(positions, trades)


def __parseActivityPDF(path: Path, lenient: bool = False) -> List[Trade]:
    tables = camelot.read_pdf(str(path),
                              pages='1-end',
                              flavor='stream',
                              row_tol=30)

    allTrades: List[Trade] = []
    for index, t in enumerate(tables):
        # print("parsing table %s of %s" % (index, len(tables)))
        df = t.df.replace({'\n': ''}, regex=True)
        headerValues = df.loc[df[0] == 'Settlement date'].index.values

        if (len(headerValues) == 0):
            # For now asserting that only the last page can be invalid which is true when exporting activity from Vanguard
            assert index == len(
                tables) - 1, "Invalid header for table: %s" % index
            print("Skipping table %s of %s" % (index, len(tables)))
            continue

        df = df.iloc[(headerValues[0] + 1):]

        trades = list(
            filter(
                None,
                lenientParse((VanguardTransaction._make(row.values)
                              for index, row in df.iterrows()),
                             transform=parseVanguardTransaction,
                             lenient=lenient)))
        allTrades.extend(trades)

    return allTrades


def forceParseVanguardTransaction(t: VanguardTransaction,
                                  flags: TradeFlags) -> Optional[Trade]:
    # skip transactions for the settlement account
    if '(settlement fund)' in t.name.lower():
        return None

    if t.quantity == "—":
        return None

    instrument: Instrument
    if len(t.symbol) > 0 and t.symbol != "—":
        instrument = Stock(t.symbol, currency=Currency.USD)
    else:
        instrument = guessInstrumentForInvestmentName(t.name)

    totalFees = parseVanguardDecimal(t.commissionFees)

    amount = parseVanguardDecimal(t.amount)

    quantity = parseVanguardDecimal(t.quantity)

    return Trade(date=datetime.strptime(t.tradeDate, '%m/%d/%Y'),
                 instrument=instrument,
                 quantity=quantity,
                 amount=Cash(currency=Currency(Currency.USD), quantity=amount),
                 fees=Cash(currency=Currency(Currency.USD),
                           quantity=totalFees),
                 flags=flags)


def parseVanguardTransaction(t: VanguardTransaction) -> Optional[Trade]:
    validTransactionTypes = set([
        'Buy', 'Sell', 'Reinvestment', 'Corp Action (Redemption)',
        'Transfer (outgoing)'
    ])

    if t.transactionType not in validTransactionTypes:
        return None

    flagsByTransactionType = {
        'Buy': TradeFlags.OPEN,
        'Sell': TradeFlags.CLOSE,
        'Reinvestment': TradeFlags.OPEN | TradeFlags.DRIP,
        'Corp Action (Redemption)': TradeFlags.CLOSE
    }

    return forceParseVanguardTransaction(
        t, flags=flagsByTransactionType[t.transactionType])
