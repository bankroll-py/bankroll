from rx.core.typing import Disposable
from typing import Callable


class AnonymousDisposable(Disposable):
    def __init__(self, fn: Callable[[], None]):
        self._fn = fn
        super().__init__()

    def dispose(self) -> None:
        self._fn()