from typing import List
from unittest import TestCase

from vistautils.collection_utils import get_only


class TestCollectionUtils(TestCase):
    def test_get_only(self) -> None:
        empty: List[str] = []
        single = ["foo"]
        multiple = ["foo", "bar", "baz"]
        generator = (x for x in multiple)

        self.assertEqual("foo", get_only(single))
        with self.assertRaisesRegex(
            ValueError, "Expected one item in sequence but got none"
        ):
            get_only(empty)
        with self.assertRaisesRegex(
            ValueError,
            r"Expected one item in sequence but got \['foo', 'bar', 'baz'\]",
        ):
            get_only(multiple)
        with self.assertRaisesRegex(
            ValueError,
            "Expected one item in sequence but got 'foo', 'bar', and possibly more",
        ):
            get_only(generator)
