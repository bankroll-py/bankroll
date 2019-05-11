from bankroll.analysis import realizedBasisForSymbol
from bankroll.model import Activity, Bond, Cash, Currency, Instrument, Position, Stock, DividendPayment, Trade, TradeFlags
from bankroll.csvsectionslicer import parseSectionsForCSV, CSVSectionCriterion, CSVSectionResult
from bankroll.parsetools import lenientParse
from collections import namedtuple
from datetime import datetime
from decimal import Decimal
from enum import unique
from pathlib import Path
from typing import Dict, List, NamedTuple, Optional, Set, Tuple

import bankroll.configuration as configuration
import csv
import re


@unique
class Settings(configuration.Settings):
    STATEMENT = 'Statement'

    @property
    def help(self) -> str:
        if self == self.STATEMENT:
            return "A local path to an exported statement CSV of Vanguard positions and trades."
        else:
            return ""

    @classmethod
    def sectionName(cls) -> str:
        return 'Vanguard'


class PositionsAndActivity(NamedTuple):
    positions: List[Position]
    activity: List[Activity]


class _VanguardPosition(NamedTuple):
    investmentName: str
    symbol: str
    shares: str
    sharePrice: str
    totalValue: str


class _VanguardPositionAndActivity(NamedTuple):
    position: _VanguardPosition
    activity: List[Activity]


def _guessInstrumentForInvestmentName(name: str) -> Instrument:
    instrument: Instrument
    if re.match(r'^.+\s\%\s.+$', name):
        # TODO: Determine valid CUSIP for bonds
        instrument = Bond(name, currency=Currency.USD, validateSymbol=False)
    else:
        instrument = Stock(name, currency=Currency.USD)

    return instrument


def _parseVanguardPositionAndActivity(vpb: _VanguardPositionAndActivity
                                      ) -> Position:
    return _parseVanguardPosition(vpb.position, vpb.activity)


def _parseVanguardPosition(p: _VanguardPosition,
                           activity: List[Activity]) -> Position:
    instrument: Instrument
    if len(p.symbol) > 0:
        instrument = Stock(p.symbol, currency=Currency.USD)
    else:
        instrument = _guessInstrumentForInvestmentName(p.investmentName)

    qty = Decimal(p.shares)

    realizedBasis = realizedBasisForSymbol(instrument.symbol, activity)
    assert realizedBasis, ("Invalid realizedBasis: %s for %s" %
                           (realizedBasis, instrument))

    return Position(instrument=instrument,
                    quantity=qty,
                    costBasis=realizedBasis)


def _parsePositions(path: Path,
                    activity: List[Activity],
                    lenient: bool = False) -> List[Position]:
    with open(path, newline='') as csvfile:
        criterion = CSVSectionCriterion(
            startSectionRowMatch=["Account Number"],
            endSectionRowMatch=[],
            rowFilter=lambda r: r[1:6])
        sections = parseSectionsForCSV(csvfile, [criterion])

        if len(sections) == 0:
            return []

        vanPositions = (_VanguardPosition._make(r) for r in sections[0].rows)
        vanPosAndBases = list(
            map(lambda pos: _VanguardPositionAndActivity(pos, activity),
                vanPositions))

        return list(
            lenientParse(vanPosAndBases,
                         transform=_parseVanguardPositionAndActivity,
                         lenient=lenient))


def parsePositionsAndActivity(path: Path,
                              lenient: bool = False) -> PositionsAndActivity:
    activity = _parseTransactions(path, lenient=lenient)
    positions = _parsePositions(path, activity=activity, lenient=lenient)
    return PositionsAndActivity(positions, activity)


class _VanguardTransaction(NamedTuple):
    tradeDate: str
    settlementDate: str
    transactionType: str
    transactionDescription: str
    investmentName: str
    symbol: str
    shares: str
    sharePrice: str
    principalAmount: str
    commissionFees: str
    netAmount: str
    accruedInterest: str
    accountType: str


def _parseVanguardTransactionDate(datestr: str) -> datetime:
    return datetime.strptime(datestr, '%m/%d/%Y')


def _forceParseVanguardTransaction(t: _VanguardTransaction,
                                   flags: TradeFlags) -> Optional[Trade]:
    instrument: Instrument
    if len(t.symbol) > 0:
        instrument = Stock(t.symbol, currency=Currency.USD)
    else:
        instrument = _guessInstrumentForInvestmentName(t.investmentName)

    totalFees = Decimal(t.commissionFees)
    amount = Decimal(t.principalAmount)

    if t.transactionDescription == 'Redemption':
        shares = Decimal(t.shares) * (-1)
    else:
        shares = Decimal(t.shares)

    return Trade(date=_parseVanguardTransactionDate(t.tradeDate),
                 instrument=instrument,
                 quantity=shares,
                 amount=Cash(currency=Currency(Currency.USD), quantity=amount),
                 fees=Cash(currency=Currency(Currency.USD),
                           quantity=totalFees),
                 flags=flags)


def _parseVanguardTransaction(t: _VanguardTransaction) -> Optional[Activity]:
    if t.transactionType == 'Dividend':
        return DividendPayment(date=_parseVanguardTransactionDate(t.tradeDate),
                               stock=Stock(
                                   t.symbol if t.symbol else t.investmentName,
                                   currency=Currency.USD),
                               proceeds=Cash(currency=Currency.USD,
                                             quantity=Decimal(t.netAmount)))

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
        'Corp Action (Redemption)': TradeFlags.CLOSE,
        'Transfer (outgoing)': TradeFlags.CLOSE,
    }

    return _forceParseVanguardTransaction(
        t, flags=flagsByTransactionType[t.transactionType])


# Transactions will be ordered from newest to oldest
def _parseTransactions(path: Path, lenient: bool = False) -> List[Activity]:
    with open(path, newline='') as csvfile:
        transactionsCriterion = CSVSectionCriterion(
            startSectionRowMatch=["Account Number", "Trade Date"],
            endSectionRowMatch=[],
            rowFilter=lambda r: r[1:-1])

        sections = parseSectionsForCSV(csvfile, [transactionsCriterion])

        if len(sections) == 0:
            return []

        return list(
            filter(
                None,
                lenientParse(
                    (_VanguardTransaction._make(r) for r in sections[0].rows),
                    transform=_parseVanguardTransaction,
                    lenient=lenient)))
