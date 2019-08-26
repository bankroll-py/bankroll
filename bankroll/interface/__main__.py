from argparse import ArgumentParser, Namespace
from itertools import chain
from bankroll import Activity, Instrument, Stock, Position, Trade, Cash, MarketDataProvider, AccountAggregator, analysis
from bankroll.brokers import *
from bankroll.configuration import Configuration, Settings, addSettingsToArgumentGroup
from progress.bar import Bar
from typing import Dict, Callable, Iterable, List, Optional

import logging

parser = ArgumentParser(
    prog='bankroll',
    add_help=False,
    description=
    'Ingests portfolio and other data from multiple brokerages, and analyzes it.',
    epilog=
    'For more information, or to report issues, please visit: https://github.com/jspahrsummers/bankroll'
)

# Add our own help option for consistent formatting.
parser.add_argument('-h',
                    '--help',
                    help='Show this help message and exit.',
                    action='help')

parser.add_argument(
    '--lenient',
    help=
    'Attempt to ignore invalid data instead of erroring out. May not be supported for all data sources.',
    default=False,
    action='store_true')
parser.add_argument('--no-lenient',
                    dest='lenient',
                    help='Opposite of --lenient.',
                    action='store_false')
parser.add_argument('-v',
                    '--verbose',
                    help='Turns on more logging, for debugging purposes.',
                    dest='verbose',
                    default=False,
                    action='store_true')
parser.add_argument(
    '--config',
    help=
    "Path to an INI file specifying configuration options, taking precedence over the default search paths. Can be specified multiple times, with the latest file's settings taking precedence over those previous.",
    action='append')

ibGroup = parser.add_argument_group(
    'IB', 'Options for importing data from Interactive Brokers.')
readIBSettings = addSettingsToArgumentGroup(ibkr.Settings, ibGroup)

fidelityGroup = parser.add_argument_group(
    'Fidelity',
    'Options for importing data from local files in Fidelity\'s CSV export format.'
)
readFidelitySettings = addSettingsToArgumentGroup(fidelity.Settings,
                                                  fidelityGroup)

schwabGroup = parser.add_argument_group(
    'Schwab',
    'Options for importing data from local files in Charles Schwab\'s CSV export format.'
)
readSchwabSettings = addSettingsToArgumentGroup(schwab.Settings, schwabGroup)

vanguardGroup = parser.add_argument_group(
    'Vanguard',
    'Options for importing data from local files in Vanguard\'s CSV export format.'
)
readVanguardSettings = addSettingsToArgumentGroup(vanguard.Settings,
                                                  vanguardGroup)


def printPositions(accounts: AccountAggregator, args: Namespace) -> None:
    values: Dict[Position, Cash] = {}
    if args.live_value:
        dataProvider = accounts.marketDataProvider
        if dataProvider:
            values = analysis.liveValuesForPositions(
                accounts.positions(),
                dataProvider=dataProvider,
                progressBar=Bar('Loading market data for positions'))
        else:
            logging.error(
                'Live data connection required to fetch market values')

    for p in sorted(accounts.positions(), key=lambda p: p.instrument):
        print(p)

        if p in values:
            print(f'\tMarket value: {values[p]}')
        elif args.live_value:
            logging.warning(f'Could not fetch market value for {p.instrument}')

        print(f'\tCost basis: {p.costBasis}')

        if args.realized_basis and isinstance(p.instrument, Stock):
            realizedBasis = analysis.realizedBasisForSymbol(
                p.instrument.symbol, activity=accounts.activity())
            print(f'\tRealized basis: {realizedBasis}')


def printActivity(accounts: AccountAggregator, args: Namespace) -> None:
    for t in sorted(accounts.activity(), key=lambda t: t.date, reverse=True):
        print(t)


def printBalances(accounts: AccountAggregator, args: Namespace) -> None:
    print(accounts.balance())


def symbolTimeline(accounts: AccountAggregator, args: Namespace) -> None:
    for entry in reversed(
            list(analysis.timelineForSymbol(args.symbol,
                                            accounts.activity()))):
        print(entry)


commands: Dict[str, Callable[[AccountAggregator, Namespace], None]] = {
    'positions': printPositions,
    'activity': printActivity,
    'balances': printBalances,
    'timeline': symbolTimeline,
}

subparsers = parser.add_subparsers(dest='command', help='What to inspect')

positionsParser = subparsers.add_parser(
    'positions',
    help='Operations upon the imported list of portfolio positions')
positionsParser.add_argument(
    '--realized-basis',
    help='Calculate realized basis for stock positions',
    default=False,
    action='store_true')
positionsParser.add_argument(
    '--live-value',
    help='Fetch live, mark-to-market value of positions',
    default=False,
    action='store_true')

activityParser = subparsers.add_parser(
    'activity', help='Operations upon imported portfolio activity')

balancesParser = subparsers.add_parser(
    'balances', help='Operations upon imported portfolio cash balances')

timelineParser = subparsers.add_parser(
    'timeline', help='Traces a position and P/L for a symbol over time')
timelineParser.add_argument(
    'symbol',
    help=
    'The symbol to look up (multi-part symbols like BRK.B will be normalized so they can be tracked across brokers)'
)


def main() -> None:
    args = parser.parse_args()
    if args.verbose:
        logging.basicConfig(level=logging.INFO)

    config = Configuration(
        chain(Configuration.defaultSearchPaths,
              args.config if args.config else []))

    if not args.command:
        parser.print_usage()
        quit(1)

    mergedSettings: Dict[Settings, str] = dict(
        chain(
            readFidelitySettings(config, args).items(),
            readSchwabSettings(config, args).items(),
            readVanguardSettings(config, args).items(),
            readIBSettings(config, args).items()))

    accounts = AccountAggregator.fromSettings(mergedSettings,
                                              lenient=args.lenient)
    commands[args.command](accounts, args)


if __name__ == '__main__':
    main()