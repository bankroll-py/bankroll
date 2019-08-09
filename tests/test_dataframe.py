from bankroll.model.dataframe import asDataFrame, fromDataFrame
from hypothesis import given

from tests import helpers
from typing import Any
import unittest


class TestDataFrame(unittest.TestCase):
    @given(helpers.dataclassModels())
    def test_emptyConversion(self, model: Any) -> None:
        df = asDataFrame([])
        self.assertTrue(df.empty)
        self.assertEqual(list(fromDataFrame(type(model), df)), [])

    @given(helpers.dataclassModels())
    def test_singleConversion(self, model: Any) -> None:
        df = asDataFrame([model])
        self.assertFalse(df.empty)
        self.assertTrue(df.equals(asDataFrame([model])))

        l = list(fromDataFrame(type(model), df))
        self.assertEqual(l[0], model)