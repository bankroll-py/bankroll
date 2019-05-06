from functools import reduce
from itertools import groupby
from model import Activity, Cash, Trade, Instrument, Option, LiveDataProvider, Quote, Position
from progress.bar import Bar
from typing import Dict, Iterable, Optional, Tuple

import re


# Different brokers represent "identical" symbols differently, and they can all be valid.
# This function normalizes them so they can be compared across time and space.
def normalizeSymbol(symbol: str) -> str:
    # These issues mostly show up with separators for multi-class shares (like BRK A and B)
    return re.sub(r'[\.\s/]', '', symbol)


def tradeAffectsSymbol(trade: Trade, symbol: str) -> bool:
    return (isinstance(trade.instrument, Option) and normalizeSymbol(
        trade.instrument.underlying) == normalizeSymbol(symbol)
            ) or normalizeSymbol(
                trade.instrument.symbol) == normalizeSymbol(symbol)


# Calculates the "realized" basis for a particular symbol, given a trade history. This refers to the actual amounts paid in and out, including dividend payments, as well as money gained or lost on derivatives related to that symbol (e.g., short puts, covered calls).
def realizedBasisForSymbol(symbol: str,
                           activity: Iterable[Activity]) -> Optional[Cash]:
    def f(basis: Optional[Cash], trade: Trade) -> Optional[Cash]:
        return basis - trade.proceeds if basis else -trade.proceeds

    return reduce(f,
                  (t for t in activity
                   if isinstance(t, Trade) and tradeAffectsSymbol(t, symbol)),
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