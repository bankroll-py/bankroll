from bankroll.configuration import Configuration, Settings
from bankroll.brokers import ibkr
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
        settings = self.config.section(ibkr.Settings)
        self.assertEqual(settings.get(ibkr.Settings.TWS_PORT), '4001')
        self.assertIsNone(settings.get(ibkr.Settings.FLEX_TOKEN))
        self.assertIsNone(settings.get(ibkr.Settings.TRADES_FLEX_QUERY))
        self.assertIsNone(settings.get(ibkr.Settings.ACTIVITY_FLEX_QUERY))

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