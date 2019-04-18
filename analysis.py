from functools import reduce
from model import Cash, Trade, Instrument, Option, LiveDataProvider, Quote, Position
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


def liveValuesForPositions(positions: Iterable[Position],
                           dataProvider: LiveDataProvider
                           ) -> Dict[Position, Cash]:
    def priceFromQuote(q: Quote, p: Position) -> Cash:
        # For a long position, the value should be what the market is willing to pay right now.
        # For a short position, the value should be what the market is asking to be paid right now.
        # TODO: Use order depth if available?
        if p.quantity < 0:
            return q.ask
        else:
            return q.bid

    return {
        p:
        priceFromQuote(dataProvider.fetchQuote(p.instrument), p) * p.quantity
        for p in positions
    }
