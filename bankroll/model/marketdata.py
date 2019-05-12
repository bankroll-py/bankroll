from abc import ABC, abstractmethod
from itertools import permutations
from typing import Any, Iterable, Optional, Tuple, TypeVar

from .cash import Cash
from .instrument import Instrument
import pandas as pd

_Item = TypeVar('_Item')


def _allEqual(i: Iterable[_Item]) -> bool:
    for (a, b) in permutations(i, 2):
        if a != b:
            return False

    return True


class Quote:
    def __init__(self,
                 bid: Optional[Cash] = None,
                 ask: Optional[Cash] = None,
                 last: Optional[Cash] = None,
                 close: Optional[Cash] = None):
        if bid and ask and ask < bid:
            raise ValueError(f'Expected ask {ask} to be at least bid {bid}')

        if not _allEqual(
            (price.currency
             for price in [bid, ask, last, close] if price is not None)):
            raise ValueError(
                f'Currencies in a quote should match: {[bid, ask, last, close]}'
            )

        self._bid = bid
        self._ask = ask
        self._last = last
        self._close = close
        super().__init__()

    @property
    def bid(self) -> Optional[Cash]:
        return self._bid

    @property
    def ask(self) -> Optional[Cash]:
        return self._ask

    @property
    def last(self) -> Optional[Cash]:
        return self._last

    @property
    def close(self) -> Optional[Cash]:
        return self._close

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, Quote):
            return False

        return self.bid == other.bid and self.ask == other.ask and self.last == other.last and self.close == other.close

    def __hash__(self) -> int:
        return hash((self.bid, self.ask, self.last, self.close))

    def __repr__(self) -> str:
        return f'Quote(bid={self.bid!r}, ask={self.ask!r}, last={self.last!r}, close={self.close!r})'


class MarketDataProvider(ABC):
    # Fetches up-to-date quotes for the provided instruments.
    # May return the results in any order.
    @abstractmethod
    def fetchQuotes(self, instruments: Iterable[Instrument]
                    ) -> Iterable[Tuple[Instrument, Quote]]:
        pass

    def fetchHistoricalData(self, instrument: Instrument) -> pd.DataFrame:
        pass
