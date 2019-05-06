from functools import reduce
from itertools import groupby
from model import Activity, Cash, DividendPayment, Trade, Instrument, Option, LiveDataProvider, Quote, Position
from progress.bar import Bar
from typing import Dict, Iterable, Optional, Tuple

import re


# Different brokers represent "identical" symbols differently, and they can all be valid.
# This function normalizes them so they can be compared across time and space.
def normalizeSymbol(symbol: str) -> str:
    # These issues mostly show up with separators for multi-class shares (like BRK A and B)
    return re.sub(r'[\.\s/]', '', symbol)


def _activityAffectsSymbol(activity: Activity, symbol: str) -> bool:
    normalized = normalizeSymbol(symbol)

    if isinstance(activity, DividendPayment):
        return normalizeSymbol(activity.stock.symbol) == normalized
    elif isinstance(activity, Trade):
        return (isinstance(activity.instrument, Option) and normalizeSymbol(
            activity.instrument.underlying) == normalized) or normalizeSymbol(
                activity.instrument.symbol) == normalized
    else:
        return False


# Calculates the "realized" basis for a particular symbol, given a trade history. This refers to the actual amounts paid in and out, including dividend payments, as well as money gained or lost on derivatives related to that symbol (e.g., short puts, covered calls).
#
# The principle here is that we want to treat dividends and options premium as "gains," where cost basis gets reduced over time as proceeds are paid out. This is not how the tax accounting works, of course, but it provides a different view into the return/profitability of an investment.
def realizedBasisForSymbol(symbol: str,
                           activity: Iterable[Activity]) -> Optional[Cash]:
    def f(basis: Optional[Cash], activity: Activity) -> Optional[Cash]:
        if isinstance(activity, DividendPayment):
            return basis - activity.proceeds if basis else -activity.proceeds
        elif isinstance(activity, Trade):
            return basis - activity.proceeds if basis else -activity.proceeds
        else:
            raise ValueError(f'Unexpected type of activity: {activity}')

    return reduce(f,
                  (t for t in activity if _activityAffectsSymbol(t, symbol)),
                  None)


def liveValuesForPositions(
        positions: Iterable[Position],
        dataProvider: LiveDataProvider,
        progressBar: Optional[Bar] = None,
) -> Dict[Position, Cash]:
    def priceFromQuote(q: Quote, p: Position) -> Optional[Cash]:
        # For a long position, the value should be what the market is willing to pay right now.
        # For a short position, the value should be what the market is asking to be paid right now.
        if p.quantity < 0:
            return q.ask or q.last or q.bid or q.close
        else:
            return q.bid or q.last or q.ask or q.close

    result = {}
    it = progressBar.iter(positions) if progressBar else positions

    for p in it:
        price = priceFromQuote(dataProvider.fetchQuote(p.instrument), p)
        if not price:
            continue

        result[p] = price * p.quantity * p.instrument.multiplier

    return result


def deduplicatePositions(positions: Iterable[Position]) -> Iterable[Position]:
    return (reduce(lambda a, b: a.combine(b), ps)
            for i, ps in groupby(sorted(positions, key=lambda p: p.instrument),
                                 key=lambda p: p.instrument))