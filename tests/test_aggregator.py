from bankroll.aggregator import AccountAggregator
from bankroll.brokers import *
from bankroll.configuration import Settings
from bankroll.model import AccountBalance, AccountData
from pathlib import Path
from typing import List

from tests import helpers
import unittest


class TestAccountAggregator(unittest.TestCase):
    accounts: List[AccountData]

    def setUp(self) -> None:
        settings = helpers.fixtureSettings

        self.accounts = [
            fidelity.FidelityAccount(
                positions=Path(settings[fidelity.Settings.POSITIONS]),
                transactions=Path(settings[fidelity.Settings.TRANSACTIONS])),
            schwab.SchwabAccount(
                positions=Path(settings[schwab.Settings.POSITIONS]),
                transactions=Path(settings[schwab.Settings.TRANSACTIONS])),
            ibkr.IBAccount(trades=Path(settings[ibkr.Settings.TRADES]),
                           activity=Path(settings[ibkr.Settings.ACTIVITY])),
            vanguard.VanguardAccount(
                statement=Path(settings[vanguard.Settings.STATEMENT]))
        ]

    def testAccountAggregatorTestsAreComplete(self) -> None:
        for subclass in AccountData.__subclasses__():
            if subclass == AccountAggregator:
                continue

            self.assertTrue(
                any((type(a) == subclass for a in self.accounts)),
                msg=
                f'Expected to find {subclass} in TestAccountAggregator (to fix this error, instantiate an example {subclass} in the setUp method)'
            )

    def testDataAddsUp(self) -> None:
        aggregator = AccountAggregator.fromSettings(helpers.fixtureSettings,
                                                    lenient=False)
        instruments = set((p.instrument for p in aggregator.positions()))

        balance = AccountBalance(cash={})
        for account in self.accounts:
            balance += account.balance()

            for p in account.positions():
                self.assertIn(
                    p.instrument,
                    instruments,
                    msg=
                    f'Expected {p} from {account} to show up in aggregated data'
                )

            for a in account.activity():
                self.assertIn(
                    a,
                    aggregator.activity(),
                    msg=
                    f'Expected {a} from {account} to show up in aggregated data'
                )

        self.assertEqual(aggregator.balance(), balance)
