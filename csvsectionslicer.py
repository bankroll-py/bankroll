from pathlib import Path
from typing import Callable, Dict, Iterator, List, NamedTuple, Optional, Sequence

import csv

CriterionRowFilter = Callable[[List[str]], Optional[List[str]]]


class CSVSectionCriterion(object):
    def __init__(self,
                 startSectionRowMatch: List[str],
                 endSectionRowMatch: List[str],
                 rowFilter: Optional[CriterionRowFilter] = None):
        self._startSectionRowMatch = startSectionRowMatch
        self._endSectionRowMatch = endSectionRowMatch
        self._rowFilter = rowFilter
        super().__init__()

    @property
    def startSectionRowMatch(self) -> List[str]:
        return self._startSectionRowMatch

    @property
    def endSectionRowMatch(self) -> List[str]:
        return self._endSectionRowMatch

    @property
    def rowFilter(self) -> Optional[CriterionRowFilter]:
        return self._rowFilter

    def __hash__(self) -> int:
        return hash((''.join(self._startSectionRowMatch),
                     ''.join(self._endSectionRowMatch)))

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, CSVSectionCriterion):
            return NotImplemented
        else:
            return ((self._startSectionRowMatch,
                     self._endSectionRowMatch) == (other._startSectionRowMatch,
                                                   other._endSectionRowMatch))


class CSVSectionResult(NamedTuple):
    criterion: CSVSectionCriterion
    rows: List[List[str]]


def parseSectionsForCSV(csvFile: Iterator[str],
                        criteria: List[CSVSectionCriterion]
                        ) -> List[CSVSectionResult]:
    results: List[CSVSectionResult] = []

    assert len(criteria)

    reader = csv.reader(csvFile, skipinitialspace=True)

    currentCriterionIndex = 0
    matchingRows: Optional[List[List[str]]] = None
    for r in reader:
        criterion = criteria[currentCriterionIndex]
        startSectionRowMatchLength = len(criterion.startSectionRowMatch)
        endSectionRowMatchLength = len(criterion.endSectionRowMatch)

        def rowEndsSection(row: List[str]) -> bool:
            if endSectionRowMatchLength == 0 and len(r) == 0:
                return True
            elif endSectionRowMatchLength > 0 and \
                len(row) >= endSectionRowMatchLength and \
                row[0:endSectionRowMatchLength] == criterion.endSectionRowMatch:
                return True
            else:
                return False

        if len(r) >= startSectionRowMatchLength and r[
                0:startSectionRowMatchLength] == criterion.startSectionRowMatch:
            # starting section
            matchingRows = []
            continue
        elif matchingRows is not None and rowEndsSection(r):
            # end of section
            section = CSVSectionResult(criterion=criterion, rows=matchingRows)
            results.append(section)
            matchingRows = None

            currentCriterionIndex += 1
            if currentCriterionIndex >= len(criteria):
                # no more criteria to parse
                break

        if matchingRows is not None:
            filteredRow = criterion.rowFilter(r) if criterion.rowFilter else r
            if filteredRow is not None:
                matchingRows.append(filteredRow)

    return results
