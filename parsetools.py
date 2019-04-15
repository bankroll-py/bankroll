from decimal import Decimal
from sys import stderr
from typing import Callable, Iterable, List, Optional, TypeVar
from warnings import warn

T = TypeVar('T')
U = TypeVar('U')


def parseDecimal(s: str) -> Decimal:
    if s == 'N/A' or s == "—" or s.lower() == 'free':
        return Decimal(0)
    else:
        return Decimal(s.replace(',', '').replace('$', ''))


def lenientParse(xs: Iterable[T], transform: Callable[[T], U],
                 lenient: bool) -> Iterable[U]:
    def f(input: T) -> Optional[U]:
        try:
            return transform(input)
        except ValueError as err:
            if lenient:
                warn(
                    'Failed to parse {}: {}'.format(input, err),
                    category=RuntimeWarning,
                    # Pop all the way out of lenientParse() to show the warning
                    stacklevel=4)
                return None
            else:
                raise

    return (y for y in (f(x) for x in xs) if y is not None)