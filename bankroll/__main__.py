from argparse import ArgumentParser, Namespace
from functools import reduce
from ib_insync import IB
from itertools import chain
from bankroll import Activity, Instrument, Stock, Position, Trade, Cash, MarketDataProvider, analysis
from bankroll.brokers import *
from bankroll.configuration import Configuration, Settings, addSettingsToArgumentGroup
from pathlib import Path
from progress.bar import Bar
from typing import Any, Callable, Dict, Iterable, List, Optional, Type, TypeVar

import logging

parser = ArgumentParser(prog='bankroll')

parser.add_argument(
    '--lenient',
    help=
    'Attempt to ignore invalid data instead of erroring out. May not be supported for all data sources.',
    default=False,
    action='store_true')
parser.add_argument('--no-lenient', dest='lenient', action='store_false')
parser.add_argument('-v',
                    '--verbose',
                    help='More logging.',
                    dest='verbose',
                    default=False,
                    action='store_true')
parser.add_argument(
    '--config',
    help=
    'Path to an INI file specifying configuration options. Can be specified multiple times.',
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

positions: List[Position] = []
activity: List[Activity] = []
dataProvider: Optional[MarketDataProvider] = None


def printPositions(args: Namespace) -> None:
    values: Dict[Position, Cash] = {}
    if args.live_value:
        if dataProvider:
            values = analysis.liveValuesForPositions(
                positions,
                dataProvider=dataProvider,
                progressBar=Bar('Loading market data for positions'))
        else:
            logging.error(
                'Live data connection required to fetch market values')

    for p in sorted(positions, key=lambda p: p.instrument):
        print(p)

        if p in values:
            print(f'\tMarket value: {values[p]}')
        elif args.live_value:
            logging.warning(f'Could not fetch market value for {p.instrument}')

        if not isinstance(p.instrument, Stock):
            continue

        print(f'\tCost basis: {p.costBasis}')

        if args.realized_basis:
            realizedBasis = analysis.realizedBasisForSymbol(
                p.instrument.symbol, activity=activity)
            print(f'\tRealized basis: {realizedBasis}')


def printActivity(args: Namespace) -> None:
    for t in sorted(activity, key=lambda t: t.date, reverse=True):
        print(t)


commands = {
    'positions': printPositions,
    'activity': printActivity,
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


def main() -> None:
    global positions
    global activity
    global dataProvider

    args = parser.parse_args()
    if args.verbose:
        logging.basicConfig(level=logging.INFO)

    config = Configuration(
        chain(Configuration.defaultSearchPaths,
              args.config if args.config else []))

    if not args.command:
        parser.print_usage()
        quit(1)

    fidelitySettings = readFidelitySettings(config, args)

    fidelityPositions = fidelitySettings.get(fidelity.Settings.POSITIONS)
    if fidelityPositions:
        positions += fidelity.parsePositions(Path(fidelityPositions),
                                             lenient=args.lenient)

    fidelityTransactions = fidelitySettings.get(fidelity.Settings.TRANSACTIONS)
    if fidelityTransactions:
        activity += fidelity.parseTransactions(Path(fidelityTransactions),
                                               lenient=args.lenient)

    schwabSettings = readSchwabSettings(config, args)

    schwabPositions = schwabSettings.get(schwab.Settings.POSITIONS)
    if schwabPositions:
        positions += schwab.parsePositions(Path(schwabPositions),
                                           lenient=args.lenient)

    schwabTransactions = schwabSettings.get(schwab.Settings.TRANSACTIONS)
    if schwabTransactions:
        activity += schwab.parseTransactions(Path(schwabTransactions),
                                             lenient=args.lenient)

    vanguardSettings = readVanguardSettings(config, args)
    vanguardStatement = vanguardSettings.get(vanguard.Settings.STATEMENT)
    if vanguardStatement:
        positionsAndActivity = vanguard.parsePositionsAndActivity(
            Path(vanguardStatement), lenient=args.lenient)
        positions += positionsAndActivity.positions
        activity += positionsAndActivity.activity

    ibSettings = readIBSettings(config, args)

    twsPort = ibSettings.get(ibkr.Settings.TWS_PORT)
    if twsPort:
        ib = IB()
        ib.connect('127.0.0.1', port=int(twsPort))

        if not dataProvider:
            dataProvider = ibkr.IBDataProvider(ib)

        positions += ibkr.downloadPositions(ib, lenient=args.lenient)

    flexToken = ibSettings.get(ibkr.Settings.FLEX_TOKEN)

    ibTrades = ibSettings.get(ibkr.Settings.TRADES)
    if ibTrades:
        path = Path(ibTrades)
        if path.is_file():
            activity += ibkr.parseTrades(path, lenient=args.lenient)
        elif flexToken:
            activity += ibkr.downloadTrades(token=flexToken,
                                            queryID=int(ibTrades),
                                            lenient=args.lenient)
        else:
            raise ValueError(
                f'Trades "{ibTrades}"" must exist as local path, or a Flex token must be provided to run as a query'
            )

    ibActivity = ibSettings.get(ibkr.Settings.ACTIVITY)
    if ibActivity:
        path = Path(ibActivity)
        if path.is_file():
            activity += ibkr.parseNonTradeActivity(path, lenient=args.lenient)
        elif flexToken:
            activity += ibkr.downloadNonTradeActivity(token=flexToken,
                                                      queryID=int(ibActivity),
                                                      lenient=args.lenient)
        else:
            raise ValueError(
                f'Activity "{ibActivity}"" must exist as local path, or a Flex token must be provided to run as a query'
            )

    positions = list(analysis.deduplicatePositions(positions))
    commands[args.command](args)


if __name__ == '__main__':
    main()