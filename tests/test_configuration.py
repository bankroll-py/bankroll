import unittest
from argparse import ArgumentParser
from enum import unique

from hypothesis import given
from hypothesis.strategies import from_type, sampled_from, text
from tests import helpers

import bankroll.brokers.fidelity as fidelity
import bankroll.brokers.ibkr as ibkr
import bankroll.brokers.schwab as schwab
import bankroll.brokers.vanguard as vanguard
from bankroll.broker import configuration


@unique
class TestSettings(configuration.Settings):
    INT_KEY = "Some integer"
    STR_KEY = "String key"

    @classmethod
    def sectionName(cls) -> str:
        return "Test"


class TestConfiguration(unittest.TestCase):
    def setUp(self) -> None:
        self.config = configuration.Configuration(["tests/bankroll.test.ini"])

    def testSettingsApplied(self) -> None:
        settings = self.config.section(TestSettings)
        self.assertEqual(settings[TestSettings.INT_KEY], "1234")
        self.assertEqual(settings[TestSettings.STR_KEY], "foobar")

    # See bankroll.default.ini
    def testDefaultSettings(self) -> None:
        ibSettings = self.config.section(ibkr.Settings)
        self.assertIsNone(ibSettings.get(ibkr.Settings.TWS_PORT))
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

    def testNamespacedSettingsDoNotClobberEachOther(self) -> None:
        # Tests that settings keys do not clobber each other.
        self.assertEqual(len(helpers.fixtureSettings), 7)

    # Verifies that settings keys are present in bankroll.default.ini, even if commented out.
    @given(from_type(configuration.Settings))
    def testSettingsListedInDefaultINI(self, key: configuration.Settings) -> None:
        # FIXME
        pass
        # contents = configuration.Configuration._readDefaultConfig().lower()
        # self.assertIn(key.value.lower(), contents)

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

    def testAddSettingsToArgumentGroup(self) -> None:
        parser = ArgumentParser()
        readSettings = configuration.addSettingsToArgumentGroup(TestSettings, parser)

        values = self.config.section(TestSettings)

        self.assertEqual(readSettings(self.config, parser.parse_args([])), values)

        values[TestSettings.INT_KEY] = "5"
        self.assertEqual(
            readSettings(self.config, parser.parse_args(["--test-some-integer", "5"])),
            values,
        )

        values[TestSettings.STR_KEY] = "fuzzbuzz"
        self.assertEqual(
            readSettings(
                self.config,
                parser.parse_args(
                    ["--test-some-integer", "5", "--test-string-key", "fuzzbuzz"]
                ),
            ),
            values,
        )
