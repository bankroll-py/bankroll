from datetime import date
from decimal import Decimal, ROUND_UP
from hypothesis import assume, given, reproduce_failure
from hypothesis.strategies import dates, decimals, from_type, integers, lists, one_of, sampled_from, text
from model import Cash, Currency, Instrument, Bond, Stock, Option, OptionType, FutureOption, Future, Forex, Position, Quote
from typing import List, TypeVar

import helpers
import unittest

T = TypeVar('T', Decimal, int)


class TestCash(unittest.TestCase):
    @given(
        sampled_from(Currency),
        helpers.decimalCashAmounts,
        helpers.decimalCashAmounts,
    )
    def test_addCash(self, cur: Currency, a: Decimal, b: Decimal) -> None:
        cashA = Cash(currency=cur, quantity=a)
        cashB = Cash(currency=cur, quantity=b)

        cashC = cashA + cashB
        self.assertEqual(cashC.currency, cur)
        self.assertEqual(cashC.quantity, Cash.quantize(a + b))

    @given(
        sampled_from(Currency),
        helpers.decimalCashAmounts,
        helpers.decimalCashAmounts,
    )
    def test_subtractCash(self, cur: Currency, a: Decimal, b: Decimal) -> None:
        cashA = Cash(currency=cur, quantity=a)
        cashB = Cash(currency=cur, quantity=b)

        cashC = cashA - cashB
        self.assertEqual(cashC.currency, cur)
        self.assertEqual(cashC.quantity, Cash.quantize(a - b))

    @given(
        lists(sampled_from(Currency), min_size=2, max_size=2, unique=True),
        helpers.decimalCashAmounts,
        helpers.decimalCashAmounts,
    )
    def test_addIncompatibleCash(self, curs: List[Currency], a: Decimal,
                                 b: Decimal) -> None:
        cashA = Cash(currency=curs[0], quantity=a)
        cashB = Cash(currency=curs[1], quantity=b)

        with self.assertRaises(AssertionError):
            cashA + cashB

    @given(
        lists(sampled_from(Currency), min_size=2, max_size=2, unique=True),
        helpers.decimalCashAmounts,
        helpers.decimalCashAmounts,
    )
    def test_subtractIncompatibleCash(self, curs: List[Currency], a: Decimal,
                                      b: Decimal) -> None:
        cashA = Cash(currency=curs[0], quantity=a)
        cashB = Cash(currency=curs[1], quantity=b)

        with self.assertRaises(AssertionError):
            cashA - cashB

    @given(
        from_type(Cash),
        one_of(
            helpers.decimalCashAmounts,
            helpers.decimalCashAmounts.map(lambda d: int(d.to_integral_value())
                                           )),
    )
    def test_multiplyCash(self, cashA: Cash, b: T) -> None:
        cashC = cashA * b
        self.assertEqual(cashC.currency, cashA.currency)
        self.assertEqual(cashC.quantity, Cash.quantize(cashA.quantity * b))

    @given(
        from_type(Cash),
        one_of(
            helpers.decimalCashAmounts,
            helpers.decimalCashAmounts.map(lambda d: int(d.to_integral_value())
                                           )).filter(lambda x: x != 0),
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
        helpers.decimalCashAmounts,
    )
    def test_cashEquality(self, cur: Currency, a: Decimal) -> None:
        cashA = Cash(currency=cur, quantity=a)
        cashB = Cash(currency=cur, quantity=a)
        self.assertEqual(cashA, cashB)
        self.assertEqual(hash(cashA), hash(cashB))

    @given(
        sampled_from(Currency),
        helpers.decimalCashAmounts,
        helpers.decimalCashAmounts.filter(lambda x: abs(x) >= Decimal('0.0001')
                                          ),
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
        helpers.decimalCashAmounts,
        helpers.decimalCashAmounts.map(abs),
    )
    def test_cashComparison(self, cur: Currency, a: Decimal,
                            b: Decimal) -> None:
        cashA = Cash(currency=cur, quantity=a)
        self.assertFalse(cashA < cashA)
        self.assertFalse(cashA > cashA)

        cashB = Cash(currency=cur, quantity=a + b)
        self.assertLessEqual(cashA,
                             cashB,
                             msg='{} not less than itself plus {}: {}'.format(
                                 a, b, a + b))
        self.assertGreaterEqual(
            cashB,
            cashA,
            msg='{} plus {} not greater than itself: {}'.format(a, b, a + b))

        cashB = Cash(currency=cur, quantity=a - b)
        self.assertLessEqual(cashB,
                             cashA,
                             msg='{} minus {} not less than itself: {}'.format(
                                 a, b, a - b))
        self.assertGreaterEqual(
            cashA,
            cashB,
            msg='{} not greater than itself minus {}: {}'.format(a, b, a - b))


class TestPosition(unittest.TestCase):
    @given(from_type(Position))
    def test_positionEqualsItself(self, p: Position) -> None:
        self.assertEqual(p, p)

    @given(from_type(Position), from_type(Position))
    def test_combineError(self, a: Position, b: Position) -> None:
        assume(a.instrument != b.instrument)

        with self.assertRaises(AssertionError):
            a.combine(b)

    @given(from_type(Instrument), from_type(Currency))
    def test_combineIncreasesBasis(self, i: Instrument, c: Currency) -> None:
        a = Position(instrument=i,
                     quantity=Decimal('100'),
                     costBasis=Cash(currency=c, quantity=Decimal('10')))
        b = Position(instrument=i,
                     quantity=Decimal('300'),
                     costBasis=Cash(currency=c, quantity=Decimal('20')))

        combined = a.combine(b)
        self.assertEqual(combined.instrument, i)
        self.assertEqual(combined.quantity, Decimal('400'))
        self.assertEqual(combined.costBasis,
                         Cash(currency=c, quantity=Decimal('30')))

    @given(from_type(Instrument), from_type(Currency),
           helpers.decimalPositionQuantities, helpers.decimalCashAmounts,
           helpers.decimalPositionQuantities, helpers.decimalCashAmounts)
    def test_combineIsCommutative(self, i: Instrument, c: Currency,
                                  aQty: Decimal, aPrice: Decimal,
                                  bQty: Decimal, bPrice: Decimal) -> None:
        assume(aQty != -bQty)

        a = Position(instrument=i,
                     quantity=aQty,
                     costBasis=Cash(currency=c, quantity=aPrice))
        b = Position(instrument=i,
                     quantity=bQty,
                     costBasis=Cash(currency=c, quantity=bPrice))
        self.assertEqual(a.combine(b), b.combine(a))

    @given(from_type(Position))
    def test_combineToZero(self, p: Position) -> None:
        opposite = Position(instrument=p.instrument,
                            quantity=-p.quantity,
                            costBasis=-p.costBasis)

        combined = p.combine(opposite)
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


if __name__ == '__main__':
    unittest.main()
