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
            'tests/schwab_positions.csv',
            schwab.Settings.TRANSACTIONS:
            'tests/schwab_transactions.csv',
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
        self.assertIn(
            fidelity.parsePositions(
                Path(self.settings[fidelity.Settings.POSITIONS])),
            self.data.positions)
        self.assertIn(
            fidelity.parseTransactions(
                Path(self.settings[fidelity.Settings.TRANSACTIONS])),
            self.data.positions)
        self.assertIn(
            schwab.parsePositions(
                Path(self.settings[schwab.Settings.POSITIONS])),
            self.data.positions)
        self.assertIn(
            schwab.parseTransactions(
                Path(self.settings[schwab.Settings.TRANSACTIONS])),
            self.data.positions)
        self.assertIn(
            ibkr.parseTrades(Path(self.settings[ibkr.Settings.TRADES])),
            self.data.activity)
        self.assertIn(
            ibkr.parseNonTradeActivity(
                Path(self.settings[ibkr.Settings.ACTIVITY])),
            self.data.activity)

        vanguardData = vanguard.parsePositionsAndActivity(
            Path(self.settings[vanguard.Settings.STATEMENT]))
        self.assertIn(vanguardData.positions, self.data.positions)
        self.assertIn(vanguardData.activity, self.data.activity)