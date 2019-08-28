from bankroll.broker import AccountAggregator
from bankroll.broker.configuration import Configuration
from bankroll.marketdata import MarketDataProvider, MarketConnectedAccountData
from typing import Iterable

import pkg_resources


def loadConfig(
    searchPaths: Iterable[str] = Configuration.defaultSearchPaths
) -> Configuration:
    defaultConfigName = "bankroll.default.ini"
    defaultConfig = pkg_resources.resource_string(
        "bankroll.interface", defaultConfigName
    ).decode()

    return Configuration(
        searchPaths=searchPaths,
        defaultConfig=defaultConfig,
        defaultConfigName=defaultConfigName,
    )


def marketDataProvider(accounts: AccountAggregator) -> MarketDataProvider:
    return next(
        (
            account.marketDataProvider
            for account in accounts.accounts
            if isinstance(account, MarketConnectedAccountData)
        )
    )

