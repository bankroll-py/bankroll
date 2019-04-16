from functools import reduce
from model import Cash, Trade, Instrument, Option
from typing import Iterable, Optional


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
