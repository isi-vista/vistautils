from unittest import TestCase

from typing import List

from vistautils.collection_utils import get_only


class TestCollectionUtils(TestCase):
    def test_get_only(self) -> None:
        empty: List[str] = []
        single = ["foo"]
        multiple = ["foo", "bar"]

        self.assertEqual("foo", get_only(single))
        with self.assertRaises(ValueError):
            get_only(empty)
        with self.assertRaises(ValueError):
            get_only(multiple)
