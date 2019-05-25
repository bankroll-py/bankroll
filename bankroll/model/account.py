from abc import ABC, abstractmethod
from typing import Iterable, Optional

from .activity import Activity
from .marketdata import MarketDataProvider
from .position import Position


# Offers data about one or more brokerage accounts, initialized with data
# (e.g., exported files) or a mechanism to get the data (e.g., a live
# connection).
class AccountData(ABC):
    # Returns the positions currently held, fetching the data on-demand if
    # necessary.
    #
    # Subclasses are encouraged to memoize this result.
    @abstractmethod
    def positions(self) -> Iterable[Position]:
        pass

    # Returns historical account activity, loading it if necessary.
    #
    # Subclasses are encouraged to memoize this result.
    @abstractmethod
    def activity(self) -> Iterable[Activity]:
        pass

    @property
    def marketDataProvider(self) -> Optional[MarketDataProvider]:
        return None