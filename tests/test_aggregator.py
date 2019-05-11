from bankroll.aggregator import DataAggregator
from bankroll.brokers import *
from bankroll.configuration import Settings
from pathlib import Path

import helpers
import unittest


class TestDataAggregator(unittest.TestCase):
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

        self.data = DataAggregator(self.settings)

    def testValuesStartEmpty(self) -> None:
        self.assertEqual(self.data.positions, [])
        self.assertEqual(self.data.activity, [])
        self.assertIsNone(self.data.dataProvider)

    def testLoadData(self) -> None:
        self.data.loadData(lenient=False)

        instruments = set((p.instrument for p in self.data.positions))

        for p in fidelity.parsePositions(
                Path(self.settings[fidelity.Settings.POSITIONS])):
            self.assertIn(p.instrument, instruments)
        for a in fidelity.parseTransactions(
                Path(self.settings[fidelity.Settings.TRANSACTIONS])):
            self.assertIn(a, self.data.activity)

        for p in schwab.parsePositions(
                Path(self.settings[schwab.Settings.POSITIONS])):
            self.assertIn(p.instrument, instruments)
        for a in schwab.parseTransactions(
                Path(self.settings[schwab.Settings.TRANSACTIONS])):
            self.assertIn(a, self.data.activity)

        for a in ibkr.parseTrades(Path(self.settings[ibkr.Settings.TRADES])):
            self.assertIn(a, self.data.activity)
        for a in ibkr.parseNonTradeActivity(
                Path(self.settings[ibkr.Settings.ACTIVITY])):
            self.assertIn(a, self.data.activity)

        vanguardData = vanguard.parsePositionsAndActivity(
            Path(self.settings[vanguard.Settings.STATEMENT]))

        for p in vanguardData.positions:
            self.assertIn(p.instrument, instruments)
        for a in vanguardData.activity:
            self.assertIn(a, self.data.activity)