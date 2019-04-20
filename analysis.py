from functools import reduce
from model import Cash, Trade, Instrument, Option, LiveDataProvider, Quote, Position
from progress.bar import Bar
from typing import Dict, Iterable, Optional, Tuple


def tradeAffectsSymbol(trade: Trade, symbol: str) -> bool:
    return (isinstance(trade.instrument, Option)
            and trade.instrument.underlying == symbol
            ) or trade.instrument.symbol == symbol


# Calculates the "realized" basis for a particular symbol, given a trade history. This refers to the actual amounts paid in and out, including dividend payments, as well as money gained or lost on derivatives related to that symbol (e.g., short puts, covered calls).
def realizedBasisForSymbol(symbol: str,
                           trades: Iterable[Trade]) -> Optional[Cash]:
    def f(basis: Optional[Cash], trade: Trade) -> Optional[Cash]:
        return basis - trade.proceeds if basis else -trade.proceeds

    return reduce(f, (t for t in trades if tradeAffectsSymbol(t, symbol)),
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
