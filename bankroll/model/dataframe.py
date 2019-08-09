from abc import ABC
from dataclasses import asdict
from typing import Any, Iterable, Type, TypeVar

try:
    import pandas as pd
except ImportError:
    pd = None

_T = TypeVar('_T', bound=Any)

if pd:
    # Converts multiple dataclasses (models) of the same type into a Pandas DataFrame.
    # Note that each model _must_ be a dataclass, though this is not expressed statically in the type.
    def asDataFrame(it: Iterable[_T]) -> pd.DataFrame:
        return pd.DataFrame((asdict(x) for x in it))

    # Converts a Pandas DataFrame into multiple dataclasses (models) of the same type.
    # Note that the type _must_ represent a dataclass, though this is not expressed statically.
    def fromDataFrame(cls: Type[_T], df: pd.DataFrame) -> Iterable[_T]:
        return (cls(**t) for t in df.itertuples())
