from argparse import Namespace
from configparser import ConfigParser
from enum import Enum, unique
from io import StringIO
from typing import Any, Callable, Dict, Iterable, Mapping, Optional, Type, TypeVar

import os
import pkg_resources


# Config sections should be implemented by subclassing this type,
# and defining enum members where the values are the INI keys.
@unique
class Settings(Enum):
    @property
    def help(self) -> str:
        return ''

    @classmethod
    def sectionName(cls) -> str:
        pass


_S = TypeVar('_S', bound=Settings)


class Configuration:
    defaultSearchPaths = [
        os.path.expanduser('~/.bankroll.ini'), 'bankroll.ini'
    ]

    _defaultConfigName = 'bankroll.default.ini'

    @classmethod
    def _readDefaultConfig(cls) -> str:
        return pkg_resources.resource_string('bankroll',
                                             cls._defaultConfigName).decode()

    def __init__(self, searchPaths: Iterable[str] = defaultSearchPaths):
        self._config = ConfigParser(empty_lines_in_values=False)

        defaultConfig = self._readDefaultConfig()
        self._config.read_string(defaultConfig, self._defaultConfigName)
        self._config.read(searchPaths)
        super().__init__()

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


# Populates an argparse argument group with settings keys, suitably reformatted.
# `group` should be one of the return values from ArgParser.add_argument_group().
#
# Returns a callable which will extract settings corresponding to this new argument group.
def addSettingsToArgumentGroup(
        settings: Type[_S],
        group: Any) -> Callable[[Configuration, Namespace], Dict[_S, str]]:
    section = settings.sectionName().lower()

    elements: Iterable[_S] = list(settings)
    argsBySetting: Dict[_S, str] = {
        setting: section + '-' + setting.value.lower().replace(' ', '-')
        for setting in elements
    }

    for setting, cliKey in argsBySetting.items():
        group.add_argument(f'--{cliKey}', help=setting.help)

    def readSettings(config: Configuration, ns: Namespace) -> Dict[_S, str]:
        argValues: Dict[str, str] = vars(ns)

        return config.section(settings,
                              overrides={
                                  setting:
                                  argValues.get(cliKey.replace('-', '_'))
                                  for setting, cliKey in argsBySetting.items()
                              })

    return readSettings