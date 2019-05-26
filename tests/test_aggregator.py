from bankroll.aggregator import AccountAggregator
from bankroll.brokers import *
from bankroll.configuration import Settings
from pathlib import Path

import helpers
import unittest


class TestAccountAggregator(unittest.TestCase):
    def setUp(self) -> None:
        self.settings = {
            fidelity.Settings.POSITIONS:
            'tests/fidelity_positions.csv',
            fidelity.Settings.TRANSACTIONS:
            'tests/fidelity_transactions.csv',
            ibkr.Settings.ACTIVITY:
            'tests/ibkr_activity.xml',
            ibkr.Settings.TRADES:
            'tests/ibkr_trades.xml',
            schwab.Settings.POSITIONS:
            'tests/schwab_positions.CSV',
            schwab.Settings.TRANSACTIONS:
            'tests/schwab_transactions.CSV',
            vanguard.Settings.STATEMENT:
            'tests/vanguard_positions_and_transactions.csv',
        }

        # Tests that keys do not clobber each other.
        self.assertEqual(len(self.settings), 7)

        self.data = AccountAggregator.fromSettings(self.settings,
                                                   lenient=False)

    def testLoadData(self) -> None:
        instruments = set((p.instrument for p in self.data.positions()))

        fidelityAccount = fidelity.FidelityAccount(
            positions=Path(self.settings[fidelity.Settings.POSITIONS]),
            transactions=Path(self.settings[fidelity.Settings.TRANSACTIONS]))
        for p in fidelityAccount.positions():
            self.assertIn(p.instrument, instruments)
        for a in fidelityAccount.activity():
            self.assertIn(a, self.data.activity())

        schwabAccount = schwab.SchwabAccount(
            positions=Path(self.settings[schwab.Settings.POSITIONS]),
            transactions=Path(self.settings[schwab.Settings.TRANSACTIONS]))
        for p in schwabAccount.positions():
            self.assertIn(p.instrument, instruments)
        for a in schwabAccount.activity():
            self.assertIn(a, self.data.activity())

        ibAccount = ibkr.IBAccount(
            trades=Path(self.settings[ibkr.Settings.TRADES]),
            activity=Path(self.settings[ibkr.Settings.ACTIVITY]))
        for a in ibAccount.activity():
            self.assertIn(a, self.data.activity())

        vanguardAccount = vanguard.VanguardAccount(
            statement=Path(self.settings[vanguard.Settings.STATEMENT]))
        for p in vanguardAccount.positions():
            self.assertIn(p.instrument, instruments)
        for a in vanguardAccount.activity():
            self.assertIn(a, self.data.activity())