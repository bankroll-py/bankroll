from bankroll.broker.configuration import Configuration
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
