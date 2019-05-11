from bankroll.configuration import Configuration
from bankroll.brokers import ibkr

import unittest


class TestConfiguration(unittest.TestCase):
    def setUp(self) -> None:
        self.config = Configuration(extraSearchPaths=['bankroll.test.ini'])

    def testIBKRSettings(self) -> None:
        settings = self.config.section(ibkr.Settings)
        self.assertEqual(settings[ibkr.Settings.TWS_PORT], '1234')
        self.assertEqual(settings[ibkr.Settings.FLEX_TOKEN], 'abcdef')
        self.assertEqual(settings[ibkr.Settings.TRADES_FLEX_QUERY], '50001')
        self.assertEqual(settings[ibkr.Settings.ACTIVITY_FLEX_QUERY], '60001')