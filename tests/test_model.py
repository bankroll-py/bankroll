from bankroll.brokers import ibkr, vanguard
from bankroll.model import AccountBalance, AccountData, Cash, Currency, Instrument, Bond, Stock, Option, OptionType, FutureOption, Future, Position, Quote, Trade
from datetime import date
from decimal import Decimal, ROUND_UP
from hypothesis import assume, given, reproduce_failure
from hypothesis.strategies import dates, decimals, from_type, integers, lists, one_of, sampled_from, text
from typing import List, Optional, Tuple, TypeVar

from tests import helpers
import unittest

T = TypeVar('T', Decimal, int)


class TestCash(unittest.TestCase):
    @given(
        sampled_from(Currency),
        helpers.cashAmounts(),
        helpers.cashAmounts(),
    )
    def test_addCash(self, cur: Currency, a: Decimal, b: Decimal) -> None:
        cashA = Cash(currency=cur, quantity=a)
        cashB = Cash(currency=cur, quantity=b)

        cashC = cashA + cashB
        self.assertEqual(cashC.currency, cur)
        self.assertEqual(cashC.quantity, Cash.quantize(a + b))

    @given(
        sampled_from(Currency),
        helpers.cashAmounts(),
        helpers.cashAmounts(),
    )
    def test_subtractCash(self, cur: Currency, a: Decimal, b: Decimal) -> None:
        cashA = Cash(currency=cur, quantity=a)
        cashB = Cash(currency=cur, quantity=b)

        cashC = cashA - cashB
        self.assertEqual(cashC.currency, cur)
        self.assertEqual(cashC.quantity, Cash.quantize(a - b))

    @given(
        lists(sampled_from(Currency), min_size=2, max_size=2, unique=True),
        helpers.cashAmounts(),
        helpers.cashAmounts(),
    )
    def test_addIncompatibleCash(self, curs: List[Currency], a: Decimal,
                                 b: Decimal) -> None:
        cashA = Cash(currency=curs[0], quantity=a)
        cashB = Cash(currency=curs[1], quantity=b)

        with self.assertRaises(ValueError):
            cashA + cashB

    @given(
        lists(sampled_from(Currency), min_size=2, max_size=2, unique=True),
        helpers.cashAmounts(),
        helpers.cashAmounts(),
    )
    def test_subtractIncompatibleCash(self, curs: List[Currency], a: Decimal,
                                      b: Decimal) -> None:
        cashA = Cash(currency=curs[0], quantity=a)
        cashB = Cash(currency=curs[1], quantity=b)

        with self.assertRaises(ValueError):
            cashA - cashB

    @given(
        from_type(Cash),
        one_of(
            helpers.cashAmounts(),
            helpers.cashAmounts().map(lambda d: int(d.to_integral_value()))),
    )
    def test_multiplyCash(self, cashA: Cash, b: T) -> None:
        cashC = cashA * b
        self.assertEqual(cashC.currency, cashA.currency)
        self.assertEqual(cashC.quantity, Cash.quantize(cashA.quantity * b))

    @given(
        from_type(Cash),
        one_of(helpers.cashAmounts(),
               helpers.cashAmounts().map(lambda d: int(d.to_integral_value()))
               ).filter(lambda x: x != 0),
    )
    def test_divideCash(self, cashA: Cash, b: T) -> None:
        cashC = cashA / b
        self.assertEqual(cashC.currency, cashA.currency)
        self.assertEqual(cashC.quantity, Cash.quantize(cashA.quantity / b))

    @given(from_type(Cash))
    def test_cashEqualsSelf(self, cashA: Cash) -> None:
        self.assertEqual(cashA, cashA)

    @given(
        sampled_from(Currency),
        helpers.cashAmounts(),
    )
    def test_cashEquality(self, cur: Currency, a: Decimal) -> None:
        cashA = Cash(currency=cur, quantity=a)
        cashB = Cash(currency=cur, quantity=a)
        self.assertEqual(cashA, cashB)
        self.assertEqual(hash(cashA), hash(cashB))

    @given(
        sampled_from(Currency),
        helpers.cashAmounts(),
        helpers.cashAmounts().filter(lambda x: abs(x) >= Decimal('0.0001')),
    )
    def test_cashInequality(self, cur: Currency, a: Decimal,
                            b: Decimal) -> None:
        cashA = Cash(currency=cur, quantity=a)
        cashB = Cash(currency=cur, quantity=a + b)
        self.assertNotEqual(cashA, cashB)

        cashB = Cash(currency=cur, quantity=a - b)
        self.assertNotEqual(cashA, cashB)

    @given(
        sampled_from(Currency),
        helpers.cashAmounts(),
        helpers.cashAmounts().map(abs),
    )
    def test_cashComparison(self, cur: Currency, a: Decimal,
                            b: Decimal) -> None:
        cashA = Cash(currency=cur, quantity=a)
        self.assertFalse(cashA < cashA)
        self.assertFalse(cashA > cashA)

        cashB = Cash(currency=cur, quantity=a + b)
        self.assertLessEqual(cashA,
                             cashB,
                             msg=f'{a} not less than itself plus {b}: {a + b}')
        self.assertGreaterEqual(
            cashB, cashA, msg=f'{a} plus {b} not greater than itself: {a + b}')

        cashB = Cash(currency=cur, quantity=a - b)
        self.assertLessEqual(
            cashB, cashA, msg=f'{a} minus {b} not less than itself: {a - b}')
        self.assertGreaterEqual(
            cashA,
            cashB,
            msg=f'{a} not greater than itself minus {b}: {a - b}')


class TestPosition(unittest.TestCase):
    @given(from_type(Position))
    def test_positionEqualsItself(self, p: Position) -> None:
        self.assertEqual(p, p)

    @given(from_type(Position), from_type(Position))
    def test_combineError(self, a: Position, b: Position) -> None:
        assume(a.instrument != b.instrument)

        with self.assertRaises(ValueError):
            a + b

    @given(from_type(Instrument))
    def test_combineIncreasesBasis(self, i: Instrument) -> None:
        a = Position(instrument=i,
                     quantity=Decimal('100'),
                     costBasis=Cash(currency=i.currency,
                                    quantity=Decimal('10')))
        b = Position(instrument=i,
                     quantity=Decimal('300'),
                     costBasis=Cash(currency=i.currency,
                                    quantity=Decimal('20')))

        combined = a + b
        self.assertEqual(combined.instrument, i)
        self.assertEqual(combined.quantity, Decimal('400'))
        self.assertEqual(combined.costBasis,
                         Cash(currency=i.currency, quantity=Decimal('30')))

    @given(from_type(Instrument), helpers.positionQuantities(),
           helpers.cashAmounts(), helpers.positionQuantities(),
           helpers.cashAmounts())
    def test_combineIsCommutative(self, i: Instrument, aQty: Decimal,
                                  aPrice: Decimal, bQty: Decimal,
                                  bPrice: Decimal) -> None:
        assume(aQty != -bQty)

        a = Position(instrument=i,
                     quantity=aQty,
                     costBasis=Cash(currency=i.currency, quantity=aPrice))
        b = Position(instrument=i,
                     quantity=bQty,
                     costBasis=Cash(currency=i.currency, quantity=bPrice))
        self.assertEqual(a + b, b + a)

    @given(from_type(Position))
    def test_combineToZero(self, p: Position) -> None:
        opposite = Position(instrument=p.instrument,
                            quantity=-p.quantity,
                            costBasis=-p.costBasis)

        combined = p + opposite
        self.assertEqual(combined.quantity, Decimal(0))
        self.assertEqual(combined.costBasis, Decimal(0))


class TestInstrument(unittest.TestCase):
    @given(from_type(Instrument))
    def test_instrumentEqualsItself(self, i: Instrument) -> None:
        self.assertEqual(i, i)

    @given(from_type(Instrument))
    def test_instrumentHashStable(self, i: Instrument) -> None:
        self.assertEqual(hash(i), hash(i))

    @given(from_type(Instrument), from_type(Instrument))
    def test_differentInstrumentTypesNotEqual(self, a: Instrument,
                                              b: Instrument) -> None:
        assume(type(a) != type(b))
        self.assertNotEqual(a, b)


class TestOption(unittest.TestCase):
    # https://en.wikipedia.org/wiki/Option_symbol#The_OCC_Option_Symbol
    def test_spxSymbol(self) -> None:
        o = Option(underlying='SPX',
                   currency=Currency.USD,
                   optionType=OptionType.PUT,
                   expiration=date(2014, 11, 22),
                   strike=Decimal('19.50'))
        self.assertEqual(o.symbol, 'SPX   141122P00019500')

    def test_lamrSymbol(self) -> None:
        o = Option(underlying='LAMR',
                   currency=Currency.USD,
                   optionType=OptionType.CALL,
                   expiration=date(2015, 1, 17),
                   strike=Decimal('52.50'))
        self.assertEqual(o.symbol, 'LAMR  150117C00052500')

    # TODO: Mini-options support


class TestQuote(unittest.TestCase):
    @given(from_type(Quote))
    def test_quoteEqualsItself(self, q: Quote) -> None:
        self.assertEqual(q, q)

    @given(from_type(Currency), helpers.optionals(helpers.cashAmounts()),
           helpers.optionals(helpers.cashAmounts()),
           helpers.optionals(helpers.cashAmounts()),
           helpers.optionals(helpers.cashAmounts()))
    def test_quoteEquality(self, currency: Currency, bid: Optional[Decimal],
                           ask: Optional[Decimal], last: Optional[Decimal],
                           close: Optional[Decimal]) -> None:
        assume((not bid) or (not ask) or (ask > bid))

        cashBid = Cash(currency=currency, quantity=bid) if bid else None
        cashAsk = Cash(currency=currency, quantity=ask) if ask else None
        cashLast = Cash(currency=currency, quantity=last) if last else None
        cashClose = Cash(currency=currency, quantity=close) if close else None

        a = Quote(cashBid, cashAsk, cashLast, cashClose)
        b = Quote(cashBid, cashAsk, cashLast, cashClose)
        self.assertEqual(a, b)
        self.assertEqual(hash(a), hash(b))


class TestTrade(unittest.TestCase):
    @given(from_type(Trade))
    def test_tradeEqualsItself(self, t: Trade) -> None:
        self.assertEqual(t, t)

    @given(from_type(Trade))
    def test_signOfTradePrice(self, t: Trade) -> None:
        if t.quantity >= 0:
            if t.amount.quantity >= 0:
                self.assertLessEqual(
                    t.price.quantity,
                    0,
                    msg=
                    'Buy transaction for profit should have a negative price')
            else:
                self.assertGreaterEqual(
                    t.price.quantity,
                    0,
                    msg='Buy transaction for loss should have a positive price'
                )
        else:
            if t.amount.quantity >= 0:
                self.assertGreaterEqual(
                    t.price.quantity,
                    0,
                    msg=
                    'Sell transaction for profit should have a positive price')
            else:
                self.assertLessEqual(
                    t.price.quantity,
                    0,
                    msg='Sell transaction for loss should have a negative price'
                )


class TestAccountData(unittest.TestCase):
    @given(from_type(AccountData))
    def test_positionsLoad(self, account: AccountData) -> None:
        # IB position loading requires a live connection, which we won't have
        # in test.
        assume(not isinstance(account, ibkr.IBAccount))

        self.assertNotEqual(list(account.positions()), [])

    @given(from_type(AccountData))
    def test_activityLoads(self, account: AccountData) -> None:
        self.assertNotEqual(list(account.activity()), [])

    @given(from_type(AccountData))
    def test_balanceLoads(self, account: AccountData) -> None:
        # IB balance loading requires a live connection, which we won't have in
        # test.
        assume(not isinstance(account, ibkr.IBAccount))

        # Vanguard balance is always zero.
        assume(not isinstance(account, vanguard.VanguardAccount))

        self.assertNotEqual(account.balance().cash, {})
        self.assertEqual({c.currency
                          for c in account.balance().cash.values()},
                         set(account.balance().cash.keys()))

    @given(from_type(AccountData))
    def test_dataLoadingIsIdempotent(self, account: AccountData) -> None:
        self.assertEqual(list(account.positions()), list(account.positions()))
        self.assertEqual(list(account.activity()), list(account.activity()))
        self.assertEqual(account.balance(), account.balance())


class TestAccountBalance(unittest.TestCase):
    @given(
        from_type(Currency).flatmap(lambda cx: helpers.accountBalances(
            currencies=sampled_from([
                cy for cy in Currency.__members__.values() if cy != cx
            ])).map(lambda balance: (cx, balance))))
    def test_zeroEntriesIgnoredForEquality(self,
                                           t: Tuple[Currency, AccountBalance]
                                           ) -> None:
        zeroCurrency, balance = t

        cashWithZero = balance.cash.copy()
        cashWithZero[zeroCurrency] = Cash(currency=zeroCurrency,
                                          quantity=Decimal(0))
        balanceWithZero = AccountBalance(cash=cashWithZero)

        self.assertEqual(balance, balanceWithZero,
                         f'Expected <{balance}> to equal <{balanceWithZero}>')

    @given(from_type(AccountBalance))
    def test_unhashable(self, balance: AccountBalance) -> None:
        # Account balances are not hashable at the moment. If they ever become
        # so, we should verify that object equality implies hash equality.
        with self.assertRaises(TypeError):
            hash(balance)

    @given(from_type(AccountBalance), from_type(AccountBalance))
    def test_additionAndSubtraction(self, first: AccountBalance,
                                    second: AccountBalance) -> None:
        self.assertEqual(first + second - second, first)
        self.assertEqual(first - second + second, first)


if __name__ == '__main__':
    unittest.main()
