from configparser import ConfigParser
from enum import Enum, unique
from typing import List, Optional, no_type_check

import pkg_resources

import os

_DEFAULT_CONFIG_NAME = 'bankroll.default.ini'


def load(extraSearchPaths: List[str] = []) -> ConfigParser:
    config = ConfigParser()

    defaultConfig = pkg_resources.resource_string('bankroll',
                                                  _DEFAULT_CONFIG_NAME)
    config.read_string(defaultConfig.decode(), _DEFAULT_CONFIG_NAME)

    config.read(
        extraSearchPaths +
        ['bankroll.ini', os.path.expanduser('~/.bankroll.ini')])
    return config


@unique
class _ConfigSection(Enum):
    IBKR = 'IBKR'
    Fidelity = 'Fidelity'
    Schwab = 'Schwab'
    Vanguard = 'Vanguard'


@no_type_check
def ibkrTWSPort(config: ConfigParser) -> Optional[int]:
    return config.getint(_ConfigSection.IBKR.value, 'tws port', fallback=None)


@no_type_check
def ibkrFlexToken(config: ConfigParser) -> Optional[str]:
    return config.get(_ConfigSection.IBKR.value, 'flex token', fallback=None)


@no_type_check
def ibkrTradesFlexQuery(config: ConfigParser) -> Optional[int]:
    return config.getint(_ConfigSection.IBKR.value,
                         'trades flex query',
                         fallback=None)


@no_type_check
def ibkrActivityFlexQuery(config: ConfigParser) -> Optional[int]:
    return config.getint(_ConfigSection.IBKR.value,
                         'activity flex query',
                         fallback=None)
