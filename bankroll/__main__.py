from argparse import ArgumentParser, Namespace
from functools import reduce
from ib_insync import IB
from itertools import chain
from bankroll import Activity, Instrument, Stock, Position, Trade, Cash, MarketDataProvider, analysis
from bankroll.brokers import *
from bankroll.configuration import Configuration
from pathlib import Path
from progress.bar import Bar
from typing import Dict, Iterable, List, Optional

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
ibGroup.add_argument(
    '--twsport',
    help=
    'Local port to connect to Trader Workstation, to import live portfolio data'
)
ibGroup.add_argument(
    '--flextoken',
    help=
    'Token ID from IB\'s Flex Web Service: https://www.interactivebrokers.com/en/software/am/am/reports/flex_web_service_version_3.htm'
)
ibGroup.add_argument(
    '--flexquery-trades',
    help=
    'Query ID for Trades report from IB\'s Flex Web Service: https://www.interactivebrokers.com/en/software/am/am/reports/flex_web_service_version_3.htm'
)
ibGroup.add_argument(
    '--ibtrades',
    help=
    'Path to exported XML of trade confirmations from IB\'s Flex Web Service',
    type=Path)
ibGroup.add_argument(
    '--flexquery-activity',
    help=
    'Query ID for Activity report from IB\'s Flex Web Service: https://www.interactivebrokers.com/en/software/am/am/reports/flex_web_service_version_3.htm'
)
ibGroup.add_argument(
    '--ibactivity',
    help='Path to exported XML of activity from IB\'s Flex Web Service',
    type=Path)

fidelityGroup = parser.add_argument_group(
    'Fidelity',
    'Options for importing data from local files in Fidelity\'s CSV export format.'
)
fidelityGroup.add_argument('--fidelitypositions',
                           help='Path to exported CSV of Fidelity positions',
                           type=Path)
fidelityGroup.add_argument(
    '--fidelitytransactions',
    help='Path to exported CSV of Fidelity transactions',
    type=Path)

schwabGroup = parser.add_argument_group(
    'Schwab',
    'Options for importing data from local files in Charles Schwab\'s CSV export format.'
)
schwabGroup.add_argument('--schwabpositions',
                         help='Path to exported CSV of Schwab positions',
                         type=Path)
schwabGroup.add_argument('--schwabtransactions',
                         help='Path to exported CSV of Schwab transactions',
                         type=Path)

vanguardGroup = parser.add_argument_group(
    'Vanguard',
    'Options for importing data from local files in Vanguard\'s CSV export format.'
)
vanguardGroup.add_argument(
    '--vanguardstatement',
    help='Path to exported CSV of Vanguard positions and trades',
    type=Path)

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

    if args.fidelitypositions:
        positions += fidelity.parsePositions(args.fidelitypositions,
                                             lenient=args.lenient)

    if args.fidelitytransactions:
        activity += fidelity.parseTransactions(args.fidelitytransactions,
                                               lenient=args.lenient)

    if args.schwabpositions:
        positions += schwab.parsePositions(args.schwabpositions,
                                           lenient=args.lenient)

    if args.schwabtransactions:
        activity += schwab.parseTransactions(args.schwabtransactions,
                                             lenient=args.lenient)

    if args.vanguardstatement:
        positionsAndActivity = vanguard.parsePositionsAndActivity(
            args.vanguardstatement, lenient=args.lenient)
        positions += positionsAndActivity.positions
        activity += positionsAndActivity.activity

    ibSettings = config.section(ibkr.Settings,
                                overrides={
                                    ibkr.Settings.TWS_PORT:
                                    args.twsport,
                                    ibkr.Settings.FLEX_TOKEN:
                                    args.flextoken,
                                    ibkr.Settings.TRADES:
                                    args.flexquery_trades,
                                    ibkr.Settings.ACTIVITY:
                                    args.flexquery_activity,
                                })

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

    if args.ibtrades:
        activity += ibkr.parseTrades(args.ibtrades, lenient=args.lenient)
    if args.ibactivity:
        activity += ibkr.parseNonTradeActivity(args.ibactivity,
                                               lenient=args.lenient)

    positions = list(analysis.deduplicatePositions(positions))
    commands[args.command](args)


if __name__ == '__main__':
    main()