from configparser import ConfigParser
from enum import Enum, unique
from typing import List, Optional, no_type_check

import os


def load(extraSearchPaths: List[str] = []) -> ConfigParser:
    config = ConfigParser()
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
def ibkrFlexToken(config: ConfigParser) -> Optional[str]:
    return config.get(_ConfigSection.IBKR.value, 'flex token', fallback=None)


@no_type_check
def ibkrTradesFlexQuery(config: ConfigParser) -> Optional[int]:
    return config.get(_ConfigSection.IBKR.value,
                      'trades flex query',
                      fallback=None)


@no_type_check
def ibkrActivityFlexQuery(config: ConfigParser) -> Optional[int]:
    return config.get(_ConfigSection.IBKR.value,
                      'activity flex query',
                      fallback=None)
