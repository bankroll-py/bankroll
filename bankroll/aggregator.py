from itertools import chain
from typing import Dict, Iterable, Mapping, Optional, Sequence

from bankroll.analysis import deduplicatePositions
from bankroll.brokers import *
from bankroll.configuration import Configuration, Settings
from bankroll.model import AccountData, Activity, MarketDataProvider, Position


class AccountAggregator(AccountData):
    @classmethod
    def allSettings(cls, config: Configuration = Configuration()
                    ) -> Dict[Settings, str]:
        return dict(
            chain(
                config.section(ibkr.Settings).items(),
                config.section(fidelity.Settings).items(),
                config.section(schwab.Settings).items(),
                config.section(vanguard.Settings).items()))

    @classmethod
    def fromSettings(cls, settings: Mapping[Settings, str],
                     lenient: bool) -> 'AccountAggregator':
        return AccountAggregator(accounts=[
            fidelity.FidelityAccount.fromSettings(settings, lenient=lenient),
            ibkr.IBAccount.fromSettings(settings, lenient=lenient),
            schwab.SchwabAccount.fromSettings(settings, lenient=lenient),
            vanguard.VanguardAccount.fromSettings(settings, lenient=lenient),
        ],
                                 lenient=lenient)

    def __init__(self, accounts: Sequence[AccountData], lenient: bool):
        self._accounts = accounts
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

    @property
    def marketDataProvider(self) -> Optional[MarketDataProvider]:
        # Don't retrieve data providers twice to check for None, in case
        # they're expensive to construct.
        return next((p for p in (account.marketDataProvider
                                 for account in self._accounts) if p), None)
