from bankroll.analysis import deduplicatePositions
from bankroll.brokers import *
from bankroll.model import Activity, Position, MarketDataProvider
from bankroll.configuration import Settings
from pathlib import Path
from typing import List, Mapping, Optional, Sequence


class DataAggregator:
    _positions: List[Position]
    _activity: List[Activity]
    _dataProvider: Optional[MarketDataProvider]

    def __init__(self, settings: Mapping[Settings, str]):
        self._settings = dict(settings)
        self._positions = []
        self._activity = []
        self._dataProvider = None
        super().__init__()

    def load(self, lenient: bool) -> 'DataAggregator':
        fidelityPositions = self._settings.get(fidelity.Settings.POSITIONS)
        if fidelityPositions:
            self._positions += fidelity.parsePositions(Path(fidelityPositions),
                                                       lenient=lenient)

        fidelityTransactions = self._settings.get(
            fidelity.Settings.TRANSACTIONS)
        if fidelityTransactions:
            self._activity += fidelity.parseTransactions(
                Path(fidelityTransactions), lenient=lenient)

        schwabPositions = self._settings.get(schwab.Settings.POSITIONS)
        if schwabPositions:
            self._positions += schwab.parsePositions(Path(schwabPositions),
                                                     lenient=lenient)

        schwabTransactions = self._settings.get(schwab.Settings.TRANSACTIONS)
        if schwabTransactions:
            self._activity += schwab.parseTransactions(
                Path(schwabTransactions), lenient=lenient)

        vanguardStatement = self._settings.get(vanguard.Settings.STATEMENT)
        if vanguardStatement:
            positionsAndActivity = vanguard.parsePositionsAndActivity(
                Path(vanguardStatement), lenient=lenient)
            self._positions += positionsAndActivity.positions
            self._activity += positionsAndActivity.activity

        ibSettings = {
            k: v
            for k, v in self._settings.items() if isinstance(k, ibkr.Settings)
        }

        (ibPositions, ibActivity,
         ib) = ibkr.loadPositionsAndActivity(ibSettings, lenient=lenient)

        self._positions += ibPositions
        self._activity += ibActivity

        if ib and not self._dataProvider:
            self._dataProvider = ibkr.IBDataProvider(ib)

        self._positions = list(deduplicatePositions(self._positions))
        return self

    @property
    def positions(self) -> Sequence[Position]:
        return self._positions

    @property
    def activity(self) -> Sequence[Activity]:
        return self._activity

    @property
    def dataProvider(self) -> Optional[MarketDataProvider]:
        return self._dataProvider