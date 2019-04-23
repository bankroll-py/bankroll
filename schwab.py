from datetime import date, datetime
from decimal import Decimal
from model import Cash, Currency, Instrument, Stock, Bond, Option, OptionType, Position, Trade, TradeFlags
from parsetools import lenientParse
from pathlib import Path
from typing import Dict, List, NamedTuple, Optional

import csv
import re


def schwabDecimal(s: str) -> Decimal:
    if s == 'N/A':
        return Decimal(0)
    else:
        return Decimal(s.replace(',', '').replace('$', ''))


def parseOption(symbol: str) -> Option:
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


class SchwabPosition(NamedTuple):
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
    securityType: str


def parseSchwabPosition(p: SchwabPosition) -> Optional[Position]:
    if re.match(r'Futures |Cash & Money Market|Account Total', p.symbol):
        return None

    instrument: Instrument
    if re.match(r'Equity|ETFs', p.securityType):
        instrument = Stock(p.symbol, currency=Currency.USD)
    elif re.match(r'Option', p.securityType):
        instrument = parseOption(p.symbol)
    elif re.match(r'Fixed Income', p.securityType):
        instrument = Bond(p.symbol, currency=Currency.USD)
    else:
        raise ValueError(f'Unrecognized security type: {p.securityType}')

    return Position(instrument=instrument,
                    quantity=schwabDecimal(p.quantity),
                    costBasis=Cash(currency=Currency.USD,
                                   quantity=schwabDecimal(p.costBasis)))


def parsePositions(path: Path, lenient: bool = False) -> List[Position]:
    with open(path, newline='') as csvfile:
        reader = csv.reader(csvfile)

        # Filter out header rows, and invalid data
        rows = map(lambda r: r[0:-1],
                   filter(lambda r: len(r) > 1 and r[0] != 'Symbol', reader))

        return list(
            filter(
                None,
                lenientParse((SchwabPosition._make(r) for r in rows),
                             transform=parseSchwabPosition,
                             lenient=lenient)))


class SchwabTransaction(NamedTuple):
    date: str
    action: str
    symbol: str
    description: str
    quantity: str
    price: str
    fees: str
    amount: str


def guessInstrumentFromSymbol(symbol: str) -> Instrument:
    if re.search(r'\s(C|P)$', symbol):
        return parseOption(symbol)
    elif Bond.validBondSymbol(symbol):
        return Bond(symbol, currency=Currency.USD)
    else:
        return Stock(symbol, currency=Currency.USD)


def forceParseSchwabTransaction(t: SchwabTransaction,
                                flags: TradeFlags) -> Trade:
    quantity = Decimal(t.quantity)
    if re.match(r'^Sell', t.action):
        quantity = -quantity

    fees = Decimal(0)
    if t.fees:
        fees = schwabDecimal(t.fees)

    amount = Decimal(0)
    if t.amount:
        # Schwab automatically deducts the fees, but we need to add them back in for consistency with other brokers
        # (where the denominating currency of these two things may differ)
        amount = schwabDecimal(t.amount) + fees

    return Trade(date=datetime.strptime(t.date[0:10], '%m/%d/%Y'),
                 instrument=guessInstrumentFromSymbol(t.symbol),
                 quantity=quantity,
                 amount=Cash(currency=Currency.USD, quantity=amount),
                 fees=Cash(currency=Currency.USD, quantity=fees),
                 flags=flags)


def parseSchwabTransaction(t: SchwabTransaction) -> Optional[Trade]:
    ignoredActions = [
        'Wire Funds',
        'Wire Funds Received',
        'MoneyLink Transfer',
        'MoneyLink Deposit',
        'Cash Dividend',
        'Reinvest Dividend',
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

    return forceParseSchwabTransaction(t, flags=flagsByAction[t.action])


# Transactions will be ordered from oldest to newest
def parseTransactions(path: Path, lenient: bool = False) -> List[Trade]:
    with open(path, newline='') as csvfile:
        reader = csv.reader(csvfile)

        # Filter out header row, and invalid data
        rows = [
            SchwabTransaction._make(r[0:-1]) for r in reader
            if len(r) > 1 and r[0] != 'Date'
        ]

        inboundTransfers = [
            forceParseSchwabTransaction(r, flags=TradeFlags.OPEN) for r in rows
            if r.action == 'Security Transfer' and r.quantity
            and Decimal(r.quantity) > 0
        ]

        trades = filter(
            None,
            lenientParse(rows,
                         transform=parseSchwabTransaction,
                         lenient=lenient))
        return fixUpShortSales(list(trades), inboundTransfers)


def fixUpShortSales(trades: List[Trade],
                    inboundTransfers: List[Trade]) -> List[Trade]:
    positionsBySymbol: Dict[str, Decimal] = {}

    def f(t: Trade) -> Trade:
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
    return [f(t) for t in reversed(trades)]
