from abc import ABC, abstractmethod
from dataclasses import asdict
from typing import Any, Dict, Iterable, Type, TypeVar

try:
    import pandas as pd
except ImportError:
    pd = None

_DFC = TypeVar('_DFC', bound='DataFrameConvertible')


class DataFrameConvertible(ABC):
    @abstractmethod
    def __init__(self: _DFC, **kwargs: Dict[str, Any]) -> None:
        pass

    @classmethod
    def fromDataFrameDict(cls: Type[_DFC], d: Dict[str, Any]) -> _DFC:
        return cls(**d)

    def dataFrameDict(self) -> Dict[str, Any]:
        return asdict(self)


if pd:
    # Converts multiple dataclasses (models) of the same type into a Pandas DataFrame.
    # Note that each model _must_ be a dataclass, though this is not expressed statically in the type.
    def asDataFrame(it: Iterable[_T]) -> pd.DataFrame:
        return pd.DataFrame((asdict(x) for x in it))

    # Converts a Pandas DataFrame into multiple dataclasses (models) of the same type.
    # Note that the type _must_ represent a dataclass, though this is not expressed statically.
    def fromDataFrame(cls: Type[_T], df: pd.DataFrame) -> Iterable[_T]:
        return (cls(**t._asdict()) for t in df.itertuples(index=False))
