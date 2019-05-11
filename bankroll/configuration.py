from configparser import ConfigParser
from enum import Enum, unique
from io import StringIO
from typing import Dict, Generic, Iterable, Mapping, Optional, Type, TypeVar

import os
import pkg_resources


# Config sections should be implemented by subclassing this type,
# and defining enum members where the values are the INI keys.
@unique
class Settings(str, Enum):
    @classmethod
    def sectionName(cls) -> str:
        pass


_S = TypeVar('_S', bound=Settings)


class Configuration:
    defaultSearchPaths = [
        os.path.expanduser('~/.bankroll.ini'), 'bankroll.ini'
    ]

    _defaultConfigName = 'bankroll.default.ini'

    def __init__(self, searchPaths: Iterable[str] = defaultSearchPaths):
        self._config = ConfigParser(empty_lines_in_values=False)

        defaultConfig = pkg_resources.resource_string('bankroll',
                                                      self._defaultConfigName)
        self._config.read_string(defaultConfig.decode(),
                                 self._defaultConfigName)
        self._config.read(searchPaths)

    def section(self,
                settings: Type[_S],
                overrides: Mapping[_S, Optional[str]] = {}) -> Dict[_S, str]:
        elements: Iterable[_S] = list(settings)

        optionalValues = {
            key: overrides.get(key)
            or self._config.get(settings.sectionName(), key.value, fallback='')
            for key in elements
        }

        return {key: value for key, value in optionalValues.items() if value}

    def __str__(self) -> str:
        output = StringIO()
        self._config.write(output)

        result = output.getvalue()
        output.close()

        return result
