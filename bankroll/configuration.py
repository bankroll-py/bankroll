from configparser import ConfigParser
from enum import Enum, unique
from io import StringIO
from itertools import chain
from typing import Dict, Generic, Iterable, Mapping, Type, TypeVar

import os
import pkg_resources


@unique
class Settings(str, Enum):
    @classmethod
    def sectionName(cls) -> str:
        pass


_S = TypeVar('_S', bound=Settings)


class Configuration:
    _defaultConfigName = 'bankroll.default.ini'

    def __init__(self, extraSearchPaths: Iterable[str] = []):
        self._config = ConfigParser(empty_lines_in_values=False)

        defaultConfig = pkg_resources.resource_string('bankroll',
                                                      self._defaultConfigName)
        self._config.read_string(defaultConfig.decode(),
                                 self._defaultConfigName)

        self._config.read(
            chain([os.path.expanduser('~/.bankroll.ini'), 'bankroll.ini'],
                  extraSearchPaths))

    def section(self, settings: Type[_S],
                overrides: Mapping[_S, str] = {}) -> Dict[_S, str]:
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
