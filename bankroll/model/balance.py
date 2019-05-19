from dataclasses import dataclass
from typing import Dict

from .cash import Cash, Currency


@dataclass(frozen=True)
class AccountBalance:
    cash: Dict[Currency, Cash]

    def __post_init__(self) -> None:
        for currency, cash in self.cash.items():
            if currency != cash.currency:
                raise ValueError(
                    f'Currency {currency} must match cash entry {cash}')

    def __str__(self) -> str:
        s = 'Balances:'
        for cash in self.cash.values():
            s += f'\n{cash}'

        return s
