from bankroll.model import Activity, Cash, Currency, Instrument, Stock, Bond, Option, OptionType, Position, DividendPayment, Trade, TradeFlags
from bankroll.parsetools import lenientParse
from datetime import date, datetime
from decimal import Decimal
from enum import unique
from itertools import chain, groupby
from pathlib import Path
from typing import Dict, Iterable, List, NamedTuple, Optional, Sequence, TypeVar

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
            return "A local path to an exported CSV of Schwab positions."
        elif self == self.TRANSACTIONS:
            return "A local path to an exported CSV of Schwab transactions."
        else:
            return ""

    @classmethod
    def sectionName(cls) -> str:
        return 'Schwab'


def _schwabDecimal(s: str) -> Decimal:
    if s == 'N/A':
        return Decimal(0)
    else:
        return Decimal(s.replace(',', '').replace('$', ''))


def _parseOption(symbol: str) -> Option:
    match = re.match(
        r'^(?P<underlying>[A-Z0-9/]+) (?P<month>\d{2})/(?P<day>\d{2})/(?P<year>\d{4}) (?P<strike>[0-9\.]+) (?P<putCall>P|C)$',
        symbol)
    if not match:
        raise ValueError(f'Could not parse Schwab options symbol: {symbol}')

    if match['putCall'] == 'P':
        optionType = OptionType.PUT
    else:
        optionType = OptionType.CALL

    return Option(underlying=match['underlying'],
                  currency=Currency.USD,
                  expiration=date(int(match['year']), int(match['month']),
                                  int(match['day'])),
                  optionType=optionType,
                  strike=Decimal(match['strike']))


class _SchwabPosition(NamedTuple):
    symbol: str
    description: str
    quantity: str
    price: str
    priceChange: str
    priceChangePct: str
    marketValue: str
    dayChange: str
    dayChangePct: str
    costBasis: str
    gainLoss: str
    gainLossPct: str
    reinvestDividends: str
    capitalGains: str
    pctOfAccount: str
    dividendYield: str
    lastDividend: str
    exDivDate: str
    peRatio: str
    wk52Low: str
    wk52High: str
    volume: str
    securityType: str


def _parseSchwabPosition(p: _SchwabPosition) -> Optional[Position]:
    if re.match(r'Futures |Cash & Money Market|Account Total', p.symbol):
        return None

    instrument: Instrument
    if re.match(r'Equity|ETFs', p.securityType):
        instrument = Stock(p.symbol, currency=Currency.USD)
    elif re.match(r'Option', p.securityType):
        instrument = _parseOption(p.symbol)
    elif re.match(r'Fixed Income', p.securityType):
        instrument = Bond(p.symbol, currency=Currency.USD)
    else:
        raise ValueError(f'Unrecognized security type: {p.securityType}')

    return Position(instrument=instrument,
                    quantity=_schwabDecimal(p.quantity),
                    costBasis=Cash(currency=Currency.USD,
                                   quantity=_schwabDecimal(p.costBasis)))


_T = TypeVar('_T')


def padToLength(seq: Sequence[_T], length: int, padding: _T) -> Iterable[_T]:
    return chain(seq, [padding] * (length - len(seq)))


def parsePositions(path: Path, lenient: bool = False) -> Sequence[Position]:
    with open(path, newline='') as csvfile:
        reader = csv.reader(csvfile)

        # Filter out header rows, and invalid data
        rows = map(lambda r: r[0:-1],
                   filter(lambda r: len(r) > 1 and r[0] != 'Symbol', reader))

        return list(
            filter(
                None,
                lenientParse(
                    (
                        _SchwabPosition._make(
                            # Not all rows are the correct length, so pad until they are
                            padToLength(r, len(_SchwabPosition._fields), ''))
                        for r in rows),
                    transform=_parseSchwabPosition,
                    lenient=lenient)))


class _SchwabTransaction(NamedTuple):
    date: str
    action: str
    symbol: str
    description: str
    quantity: str
    price: str
    fees: str
    amount: str


def _guessInstrumentFromSymbol(symbol: str) -> Instrument:
    if re.search(r'\s(C|P)$', symbol):
        return _parseOption(symbol)
    elif Bond.validBondSymbol(symbol):
        return Bond(symbol, currency=Currency.USD)
    else:
        return Stock(symbol, currency=Currency.USD)


def _parseSchwabTransactionDate(datestr: str) -> datetime:
    return datetime.strptime(datestr[0:10], '%m/%d/%Y')


def _forceParseSchwabTransaction(t: _SchwabTransaction,
                                 flags: TradeFlags) -> Trade:
    quantity = Decimal(t.quantity)
    if re.match(r'^Sell', t.action):
        quantity = -quantity

    fees = Decimal(0)
    if t.fees:
        fees = _schwabDecimal(t.fees)

    amount = Decimal(0)
    if t.amount:
        # Schwab automatically deducts the fees, but we need to add them back in for consistency with other brokers
        # (where the denominating currency of these two things may differ)
        amount = _schwabDecimal(t.amount) + fees

    return Trade(date=_parseSchwabTransactionDate(t.date),
                 instrument=_guessInstrumentFromSymbol(t.symbol),
                 quantity=quantity,
                 amount=Cash(currency=Currency.USD, quantity=amount),
                 fees=Cash(currency=Currency.USD, quantity=fees),
                 flags=flags)


def _parseSchwabTransaction(
        t: _SchwabTransaction,
        otherTransactionsThisDate: Iterable[_SchwabTransaction]
) -> Optional[Activity]:
    dividendActions = [
        'Cash Dividend',
        'Reinvest Dividend',
    ]

    if t.action in dividendActions:
        return DividendPayment(date=_parseSchwabTransactionDate(t.date),
                               stock=Stock(t.symbol, currency=Currency.USD),
                               proceeds=Cash(currency=Currency.USD,
                                             quantity=_schwabDecimal(
                                                 t.amount)))

    # Bond redemptions are split into two entries, for some reason.
    if t.action == 'Full Redemption Adj':
        redemption = next(
            (r for r in otherTransactionsThisDate
             if r.symbol == t.symbol and r.action == 'Full Redemption'), None)
        if not redemption:
            raise ValueError(
                f'Expected to find "Full Redemption" action on same date as {t}'
            )

        quantity = Decimal(redemption.quantity)
        amount = _schwabDecimal(t.amount)

        return Trade(
            date=_parseSchwabTransactionDate(t.date),
            instrument=Bond(t.symbol, currency=Currency.USD),
            quantity=quantity,
            amount=Cash(currency=Currency.USD, quantity=amount),
            fees=Cash(currency=Currency.USD, quantity=Decimal(0)),
            # TODO: Do we want a new TradeFlag?
            flags=TradeFlags.CLOSE | TradeFlags.EXPIRED)

    if t.action == 'Full Redemption':
        adj = next(
            (r for r in otherTransactionsThisDate
             if r.symbol == t.symbol and r.action == 'Full Redemption Adj'),
            None)
        if not adj:
            raise ValueError(
                f'Expected to find "Full Redemption Adj" action on same date as {t}'
            )

        # Will process on the adjustment entry
        return None

    ignoredActions = [
        'Wire Funds',
        'Wire Funds Received',
        'MoneyLink Transfer',
        'MoneyLink Deposit',
        'Long Term Cap Gain Reinvest',
        'ATM Withdrawal',
        'Schwab ATM Rebate',
        'Credit Interest',
        'Margin Interest',
        'Service Fee',
        'Journal',
        'Misc Cash Entry',
        'Security Transfer',
    ]

    if t.action in ignoredActions:
        return None

    flagsByAction = {
        'Buy': TradeFlags.OPEN,
        'Sell Short': TradeFlags.OPEN,
        'Buy to Open': TradeFlags.OPEN,
        'Sell to Open': TradeFlags.OPEN,
        'Reinvest Shares': TradeFlags.OPEN | TradeFlags.DRIP,
        'Sell': TradeFlags.CLOSE,
        'Buy to Close': TradeFlags.CLOSE,
        'Sell to Close': TradeFlags.CLOSE,
        'Assigned': TradeFlags.CLOSE | TradeFlags.ASSIGNED_OR_EXERCISED,
        'Exchange or Exercise':
        TradeFlags.CLOSE | TradeFlags.ASSIGNED_OR_EXERCISED,
        'Expired': TradeFlags.CLOSE | TradeFlags.EXPIRED,
    }

    return _forceParseSchwabTransaction(t, flags=flagsByAction[t.action])


# Transactions will be ordered from oldest to newest
def parseTransactions(path: Path, lenient: bool = False) -> List[Activity]:
    with open(path, newline='') as csvfile:
        reader = csv.reader(csvfile)

        # Filter out header row, and invalid data
        rows = [
            _SchwabTransaction._make(r[0:-1]) for r in reader
            if len(r) > 1 and r[0] != 'Date'
        ]

        inboundTransfers = [
            _forceParseSchwabTransaction(r, flags=TradeFlags.OPEN)
            for r in rows if r.action == 'Security Transfer' and r.quantity
            and Decimal(r.quantity) > 0
        ]

        # Annoying hack because some transactions depend on others around them.
        rowsByDate = {
            d: list(t)
            for d, t in groupby(sorted(rows, key=lambda t: t.date),
                                key=lambda t: t.date)
        }

        activity = filter(
            None,
            lenientParse(rows,
                         transform=lambda t: _parseSchwabTransaction(
                             t, otherTransactionsThisDate=rowsByDate[t.date]),
                         lenient=lenient))
        return _fixUpShortSales(list(activity), inboundTransfers)


def _fixUpShortSales(activity: Sequence[Activity],
                     inboundTransfers: Sequence[Trade]) -> List[Activity]:
    positionsBySymbol: Dict[str, Decimal] = {}

    def f(t: Activity) -> Activity:
        if not isinstance(t, Trade):
            return t

        symbol = t.instrument.symbol

        pos = positionsBySymbol.setdefault(symbol, Decimal(0))
        positionsBySymbol[symbol] += t.quantity

        # Flip flags for a Buy order that followed a Sell Short, as this indicates closing a position.
        # TODO: How should this work if the quantity is greater than the position?
        if pos < 0 and t.quantity > 0 and t.quantity <= abs(
                pos) and t.flags & TradeFlags.OPEN:
            return t._replace(flags=(t.flags ^ TradeFlags.OPEN)
                              | TradeFlags.CLOSE)
        # Schwab records restricted stock sales as short selling followed by a security transfer.
        # If we find a short sale, see if there's a later transfer, and if so, record as closing a position.
        elif t.quantity < 0 and t.flags & TradeFlags.OPEN:
            txs = (tx for tx in reversed(inboundTransfers)
                   if tx.date >= t.date and tx.instrument.symbol ==
                   t.instrument.symbol and tx.quantity == abs(t.quantity))

            if next(txs, None):
                return t._replace(flags=(t.flags ^ TradeFlags.OPEN)
                                  | TradeFlags.CLOSE)
            else:
                return t
        else:
            return t

    # Start from oldest transactions, work to newer
    return [f(t) for t in reversed(activity)]
