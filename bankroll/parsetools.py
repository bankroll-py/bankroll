from sys import stderr
from typing import Callable, Iterable, List, Optional, TypeVar
from warnings import warn

_T = TypeVar('_T')
_U = TypeVar('_U')


def lenientParse(xs: Iterable[_T], transform: Callable[[_T], _U],
                 lenient: bool) -> Iterable[_U]:
    def f(input: _T) -> Optional[_U]:
        try:
            return transform(input)
        except ValueError as err:
            if lenient:
                warn(
                    f'Failed to parse {input}: {err}',
                    category=RuntimeWarning,
                    # Pop all the way out of lenientParse() to show the warning
                    stacklevel=4)
                return None
            else:
                raise

    return (y for y in (f(x) for x in xs) if y is not None)
