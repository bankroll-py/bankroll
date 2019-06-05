from abc import ABC, abstractmethod
from dataclasses import dataclass
from decimal import Decimal
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


@dataclass(frozen=True)
class Quote:
    bid: Optional[Cash] = None
    ask: Optional[Cash] = None
    last: Optional[Cash] = None
    close: Optional[Cash] = None

    def __post_init__(self) -> None:
        if self.bid and self.ask and self.ask < self.bid:
            raise ValueError(
                f'Expected ask {self.ask} to be at least bid {self.bid}')

        if not _allEqual(
            (price.currency
             for price in [self.bid, self.ask, self.last, self.close]
             if price is not None)):
            raise ValueError(
                f'Currencies in a quote should match: {[self.bid, self.ask, self.last, self.close]}'
            )

    @property
    def midpoint(self) -> Optional[Cash]:
        if self.bid and self.ask:
            return (self.bid + self.ask) / Decimal(2)
        else:
            return self.bid or self.ask

    @property
    def market(self) -> Optional[Cash]:
        return self.midpoint or self.last or self.close


class MarketDataProvider(ABC):
    # Fetches up-to-date quotes for the provided instruments.
    # May return the results in any order.
    @abstractmethod
    def fetchQuotes(self, instruments: Iterable[Instrument]
                    ) -> Iterable[Tuple[Instrument, Quote]]:
        pass

    def fetchHistoricalData(self, instrument: Instrument) -> pd.DataFrame:
        pass
