from functools import reduce
from itertools import chain
from typing import Dict, Iterable, Mapping, Optional, Sequence

from bankroll.analysis import deduplicatePositions
from bankroll.brokers import *
from bankroll.configuration import Configuration, Settings
from bankroll.model import AccountBalance, AccountData, Activity, MarketDataProvider, Position

import operator


class AccountAggregator(AccountData):
    @classmethod
    def allSettings(cls, config: Configuration = Configuration()
                    ) -> Dict[Settings, str]:
        return dict(
            chain.from_iterable(
                (config.section(settingsCls).items()
                 for settingsCls in Settings.__subclasses__())))

    @classmethod
    def fromSettings(cls, settings: Mapping[Settings, str],
                     lenient: bool) -> 'AccountAggregator':
        return AccountAggregator(
            accounts=(accountCls.fromSettings(settings, lenient=lenient)
                      for accountCls in AccountData.__subclasses__()
                      if not issubclass(accountCls, AccountAggregator)),
            lenient=lenient)

    def __init__(self, accounts: Iterable[AccountData], lenient: bool):
        self._accounts = list(accounts)
        self._lenient = lenient
        super().__init__()

    def positions(self) -> Iterable[Position]:
        # TODO: Memoize the result of deduplication?
        return deduplicatePositions(
            chain.from_iterable(
                (account.positions() for account in self._accounts)))

    def activity(self) -> Iterable[Activity]:
        return chain.from_iterable(
            (account.activity() for account in self._accounts))

    def balance(self) -> AccountBalance:
        return reduce(operator.add,
                      (account.balance() for account in self._accounts),
                      AccountBalance(cash={}))

    @property
    def marketDataProvider(self) -> Optional[MarketDataProvider]:
        # Don't retrieve data providers twice to check for None, in case
        # they're expensive to construct.
        return next((p for p in (account.marketDataProvider
                                 for account in self._accounts) if p), None)
