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
from bankroll.interface import loadConfig

import pkg_resources


class TestConfiguration(unittest.TestCase):
    def setUp(self) -> None:
        self.config = loadConfig(["tests/bankroll.test.ini"])

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
        contents = (
            pkg_resources.resource_string("bankroll.interface", "bankroll.default.ini")
            .decode()
            .lower()
        )

        self.assertIn(key.value.lower(), contents)
