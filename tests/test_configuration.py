from bankroll.configuration import Configuration, Settings
from bankroll.brokers import *
from enum import unique
from hypothesis import given
from hypothesis.strategies import sampled_from, text

import unittest


@unique
class TestSettings(Settings):
    INT_KEY = 'Some integer'
    STR_KEY = 'String key'

    @classmethod
    def sectionName(cls) -> str:
        return 'Test'


class TestConfiguration(unittest.TestCase):
    def setUp(self) -> None:
        self.config = Configuration(['tests/bankroll.test.ini'])

    def testSettingsApplied(self) -> None:
        settings = self.config.section(TestSettings)
        self.assertEqual(settings[TestSettings.INT_KEY], '1234')
        self.assertEqual(settings[TestSettings.STR_KEY], 'foobar')

    # See bankroll.default.ini
    def testDefaultSettings(self) -> None:
        ibSettings = self.config.section(ibkr.Settings)
        self.assertEqual(ibSettings.get(ibkr.Settings.TWS_PORT), '4001')
        self.assertIsNone(ibSettings.get(ibkr.Settings.FLEX_TOKEN))
        self.assertIsNone(ibSettings.get(ibkr.Settings.TRADES))
        self.assertIsNone(ibSettings.get(ibkr.Settings.ACTIVITY))

        schwabSettings = self.config.section(schwab.Settings)
        self.assertIsNone(schwabSettings.get(schwab.Settings.POSITIONS))
        self.assertIsNone(schwabSettings.get(schwab.Settings.TRANSACTIONS))

        fidelitySettings = self.config.section(fidelity.Settings)
        self.assertIsNone(fidelitySettings.get(fidelity.Settings.POSITIONS))
        self.assertIsNone(fidelitySettings.get(fidelity.Settings.TRANSACTIONS))

        vanguardSettings = self.config.section(vanguard.Settings)
        self.assertIsNone(vanguardSettings.get(vanguard.Settings.STATEMENT))

    @given(sampled_from(TestSettings), text(min_size=1))
    def testOverrides(self, key: TestSettings, value: str) -> None:
        defaultSettings = self.config.section(TestSettings)

        settings = self.config.section(TestSettings, overrides={key: value})
        self.assertNotEqual(settings, defaultSettings)
        self.assertEqual(settings[key], value)

        for otherKey in list(TestSettings):
            if key == otherKey:
                continue

            self.assertEqual(settings[otherKey], defaultSettings[otherKey])