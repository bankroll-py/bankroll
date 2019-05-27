from dataclasses import dataclass
from decimal import Decimal
from typing import Dict

from .cash import Cash, Currency


# Represents uninvested cash (which nonetheless may accrue interest) sitting in
# a brokerage account.
#
# Cash explicitly invested in money market funds (e.g., such that they show up
# as Positions) will not be included in this accounting.
@dataclass(frozen=True)
class AccountBalance:
    cash: Dict[Currency, Cash]

    def __post_init__(self) -> None:
        super().__setattr__(
            'cash', {
                currency: cash
                for currency, cash in self.cash.items()
                if cash.quantity != Decimal(0)
            })

        for currency, cash in self.cash.items():
            if currency != cash.currency:
                raise ValueError(
                    f'Currency {currency} must match cash entry {cash}')

    def __str__(self) -> str:
        s = 'Balances:'
        for cash in self.cash.values():
            s += f'\n{cash}'

        return s
