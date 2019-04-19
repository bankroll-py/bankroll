from argparse import ArgumentParser, Namespace
from functools import reduce
from ib_insync import IB
from itertools import groupby
from model import Instrument, Stock, Position, Trade, Cash, LiveDataProvider
from pathlib import Path
from progress.bar import Bar
from typing import Dict, Iterable, List, Optional

import analysis
import ibkr
import fidelity
import logging
import schwab
import vanguard

parser = ArgumentParser()

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

ibGroup = parser.add_argument_group(
    'IB', 'Options for importing data from Interactive Brokers.')
ibGroup.add_argument(
    '--twsport',
    help=
    'Local port to connect to Trader Workstation, to import live portfolio data',
    type=int)
ibGroup.add_argument(
    '--flextoken',
    help=
    'Token ID from IB\'s Flex Web Service: https://www.interactivebrokers.com/en/software/am/am/reports/flex_web_service_version_3.htm'
)
ibGroup.add_argument(
    '--flexquery',
    help=
    'Query ID from IB\'s Flex Web Service: https://www.interactivebrokers.com/en/software/am/am/reports/flex_web_service_version_3.htm',
    type=int)
ibGroup.add_argument(
    '--ibtrades',
    help=
    'Path to exported XML of trade confirmations from IB\'s Flex Web Service',
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
vanguardGroup.add_argument('--vanguardpositions',
                           help='Path to exported CSV of Vanguard positions',
                           type=Path)
vanguardGroup.add_argument(
    '--vanguardtransactions',
    help='Path to exported PDF or CSV of Vanguard transactions',
    type=Path)

vanguardGroup.add_argument('--vanguardactivity',
                           help='Path to exported PDF of Vanguard activity',
                           type=Path)

vanguardGroup.add_argument('--vanguardoutput',
                           help='Output path for converted activity',
                           type=Path)


def combinePositions(positions: Iterable[Position]) -> Iterable[Position]:
    return (reduce(lambda a, b: a.combine(b), ps)
            for i, ps in groupby(sorted(positions, key=lambda p: p.instrument),
                                 key=lambda p: p.instrument))


positions: List[Position] = []
trades: List[Trade] = []
dataProvider: Optional[LiveDataProvider] = None


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
            print('\tMarket value: {}'.format(values[p]))
        elif args.live_value:
            logging.warning('Could not fetch market value for {}'.format(
                p.instrument))

        if not isinstance(p.instrument, Stock):
            continue

        print('\tCost basis: {}'.format(p.costBasis))

        if args.realized_basis:
            realizedBasis = analysis.realizedBasisForSymbol(
                p.instrument.symbol, trades=trades)
            print('\tRealized basis: {}'.format(realizedBasis))


def printTrades(args: Namespace) -> None:
    for t in sorted(trades, key=lambda t: t.date, reverse=True):
        print(t)


def convert(args: Namespace) -> None:
    if args.vanguardactivity and args.vanguardoutput:
        vanguard.exportActivityCSV(args.vanguardactivity, args.vanguardoutput)
    else:
        print(
            'Please provide a path to the input pdf and a path to output the csv'
        )


commands = {
    'positions': printPositions,
    'trades': printTrades,
    'convert': convert,
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

tradesParser = subparsers.add_parser(
    'trades', help='Operations upon the imported list of trades')

convertParser = subparsers.add_parser('convert', help='convert activity')
convertParser.add_argument('--vanguardactivity',
                           help='Path to exported PDF of Vanguard activity',
                           type=Path)
convertParser.add_argument('--vanguardoutput',
                           help='Output path for converted activity',
                           type=Path)

if __name__ == '__main__':
    args = parser.parse_args()
    if args.verbose:
        logging.basicConfig(level=logging.INFO)

    if not args.command:
        parser.print_usage()
        quit(1)

    if (args.vanguardpositions and args.vanguardtransactions):
        positionsAndTrades = vanguard.parsePositionsAndTrades(
            args.vanguardpositions,
            args.vanguardtransactions,
            lenient=args.lenient)
        positions += positionsAndTrades.positions
        trades += positionsAndTrades.trades
    elif (args.vanguardpositions or args.vanguardtransactions):
        parser.error(
            '--vanguardpositions and ---vanguardtransactions must both be provided'
        )

    if args.fidelitypositions:
        positions += fidelity.parsePositions(args.fidelitypositions,
                                             lenient=args.lenient)

    if args.fidelitytransactions:
        trades += fidelity.parseTransactions(args.fidelitytransactions,
                                             lenient=args.lenient)

    if args.schwabpositions:
        positions += schwab.parsePositions(args.schwabpositions,
                                           lenient=args.lenient)

    if args.schwabtransactions:
        trades += schwab.parseTransactions(args.schwabtransactions,
                                           lenient=args.lenient)

    if args.twsport:
        ib = IB()
        ib.connect('127.0.0.1', port=args.twsport)

        if not dataProvider:
            dataProvider = ibkr.IBDataProvider(ib)

        positions += ibkr.downloadPositions(ib, lenient=args.lenient)

    if args.flextoken or args.flexquery:
        if not args.flextoken or not args.flexquery:
            raise Exception(
                'Both a Flex token and a Flex query ID are required to download trade reports'
            )

        trades += ibkr.downloadTrades(token=args.flextoken,
                                      queryID=args.flexquery,
                                      lenient=args.lenient)

    if args.ibtrades:
        trades += ibkr.parseTrades(args.ibtrades, lenient=args.lenient)

    positions = list(combinePositions(positions))
    commands[args.command](args)
