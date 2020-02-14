import sys
from typing import Any
from unittest import TestCase

from immutablecollections import ImmutableSet

from vistautils.range import (
    _BELOW_ALL,
    BoundType,
    ImmutableRangeMap,
    ImmutableRangeSet,
    MutableRangeSet,
    Range,
    RangeSet,
)


class TestRange(TestCase):
    """
    Tests for Range.

    Almost entirely taken from Guava's Range tests (author Kevin Bourrillion)
    """

    def test_open(self):
        rng = Range.open(4, 8)
        self.check_contains(rng)
        self.assertTrue(rng.has_lower_bound())
        self.assertEqual(4, rng.lower_endpoint)
        self.assertEqual(BoundType.open(), rng.lower_bound_type)
        self.assertTrue(rng.has_upper_bound())
        self.assertEqual(8, rng.upper_endpoint)
        self.assertEqual(BoundType.open(), rng.upper_bound_type)
        self.assertFalse(rng.is_empty())
        self.assertEqual("(4..8)", str(rng))

        with self.assertRaises(ValueError):
            Range.open(8, 4)

        with self.assertRaises(ValueError):
            Range.open(4, 4)

    def test_closed(self):
        rng = Range.closed(5, 7)
        self.check_contains(rng)
        self.assertTrue(rng.has_lower_bound())
        self.assertEqual(5, rng.lower_endpoint)
        self.assertEqual(BoundType.closed(), rng.lower_bound_type)
        self.assertTrue(rng.has_upper_bound())
        self.assertEqual(7, rng.upper_endpoint)
        self.assertEqual(BoundType.closed(), rng.upper_bound_type)
        self.assertFalse(rng.is_empty())
        self.assertEqual("[5..7]", str(rng))
        # this is legal and should raise no exception
        Range.closed(4, 4)

        with self.assertRaises(ValueError):
            Range.closed(8, 4)

    def test_open_closed(self):
        rng = Range.open_closed(4, 7)
        self.check_contains(rng)
        self.assertTrue(rng.has_lower_bound())
        self.assertEqual(4, rng.lower_endpoint)
        self.assertEqual(BoundType.open(), rng.lower_bound_type)
        self.assertTrue(rng.has_upper_bound())
        self.assertEqual(7, rng.upper_endpoint)
        self.assertEqual(BoundType.closed(), rng.upper_bound_type)
        self.assertFalse(rng.is_empty())
        self.assertEqual("(4..7]", str(rng))

    def test_closed_open(self):
        rng = Range.closed_open(5, 8)
        self.check_contains(rng)
        self.assertTrue(rng.has_lower_bound())
        self.assertEqual(5, rng.lower_endpoint)
        self.assertEqual(BoundType.closed(), rng.lower_bound_type)
        self.assertTrue(rng.has_upper_bound())
        self.assertEqual(8, rng.upper_endpoint)
        self.assertEqual(BoundType.open(), rng.upper_bound_type)
        self.assertFalse(rng.is_empty())
        self.assertEqual("[5..8)", str(rng))

    def test_singleton(self):
        rng = Range.closed(4, 4)
        self.assertFalse(3 in rng)
        self.assertTrue(4 in rng)
        self.assertFalse(5 in rng)
        self.assertTrue(rng.has_lower_bound())
        self.assertEqual(4, rng.lower_endpoint)
        self.assertEqual(BoundType.closed(), rng.lower_bound_type)
        self.assertTrue(rng.has_upper_bound())
        self.assertEqual(4, rng.upper_endpoint)
        self.assertEqual(BoundType.closed(), rng.upper_bound_type)
        self.assertFalse(rng.is_empty())
        self.assertEqual("[4..4]", str(rng))

    def test_empty_1(self):
        rng = Range.closed_open(4, 4)
        self.assertFalse(3 in rng)
        self.assertFalse(4 in rng)
        self.assertFalse(5 in rng)
        self.assertTrue(rng.has_lower_bound())
        self.assertEqual(4, rng.lower_endpoint)
        self.assertEqual(BoundType.closed(), rng.lower_bound_type)
        self.assertTrue(rng.has_upper_bound())
        self.assertEqual(4, rng.upper_endpoint)
        self.assertEqual(BoundType.open(), rng.upper_bound_type)
        self.assertTrue(rng.is_empty())
        self.assertEqual("[4..4)", str(rng))

    def test_empty_2(self):
        rng = Range.open_closed(4, 4)
        self.assertFalse(3 in rng)
        self.assertFalse(4 in rng)
        self.assertFalse(5 in rng)
        self.assertTrue(rng.has_lower_bound())
        self.assertEqual(4, rng.lower_endpoint)
        self.assertEqual(BoundType.open(), rng.lower_bound_type)
        self.assertTrue(rng.has_upper_bound())
        self.assertEqual(4, rng.upper_endpoint)
        self.assertEqual(BoundType.closed(), rng.upper_bound_type)
        self.assertTrue(rng.is_empty())
        self.assertEqual("(4..4]", str(rng))

    def test_less_than(self):
        rng = Range.less_than(5)
        # how to check for largest negative value? -sys.maxsize -1 should probably work,
        # but as far as I can tell there is no guarantee. For now we check for a large negative
        # value
        self.assertTrue(-2 ** 30 in rng)
        self.assertTrue(4 in rng)
        self.assertFalse(5 in rng)
        self.assert_unbounded_below(rng)
        self.assertTrue(rng.has_upper_bound())
        self.assertEqual(5, rng.upper_endpoint)
        self.assertEqual(BoundType.open(), rng.upper_bound_type)
        self.assertFalse(rng.is_empty())
        self.assertEqual("(-\u221e..5)", str(rng))

    def test_greater_than(self):
        rng = Range.greater_than(5)
        self.assertFalse(5 in rng)
        self.assertTrue(6 in rng)
        self.assertTrue(sys.maxsize in rng)
        self.assertTrue(rng.has_lower_bound())
        self.assertEqual(5, rng.lower_endpoint)
        self.assertEqual(BoundType.open(), rng.lower_bound_type)
        self.assert_unbounded_above(rng)
        self.assertFalse(rng.is_empty())
        self.assertEqual("(5..+\u221e)", str(rng))

    def test_at_least(self):
        rng = Range.at_least(6)
        self.assertFalse(5 in rng)
        self.assertTrue(6 in rng)
        self.assertTrue(sys.maxsize in rng)
        self.assertTrue(rng.has_lower_bound())
        self.assertEqual(6, rng.lower_endpoint)
        self.assertEqual(BoundType.closed(), rng.lower_bound_type)
        self.assert_unbounded_above(rng)
        self.assertFalse(rng.is_empty())
        self.assertEqual("[6..+\u221e)", str(rng))

    def test_at_most(self):
        rng = Range.at_most(4)
        # how to check for largest negative value? -sys.maxsize -1 should probably work,
        # but as far as I can tell there is no guarantee. For now we check for a large negative
        # value
        self.assertTrue(-2 ** 30 in rng)
        self.assertTrue(4 in rng)
        self.assertFalse(5 in rng)
        self.assert_unbounded_below(rng)
        self.assertTrue(rng.has_upper_bound())
        self.assertEqual(4, rng.upper_endpoint)
        self.assertEqual(BoundType.closed(), rng.upper_bound_type)
        self.assertFalse(rng.is_empty())
        self.assertEqual("(-\u221e..4]", str(rng))

    def test_all(self):
        rng = Range.all()
        # how to check for largest negative value? -sys.maxsize -1 should probably work,
        # but as far as I can tell there is no guarantee. For now we check for a large negative
        # value
        self.assertTrue(-2 ** 30 in rng)
        self.assertTrue(sys.maxsize in rng)
        self.assert_unbounded_below(rng)
        self.assert_unbounded_above(rng)
        self.assertFalse(rng.is_empty())
        self.assertEqual("(-\u221e..+\u221e)", str(rng))
        self.assertTrue(rng is Range.all())

    def test_equals(self):
        self.assertEqual(Range.all(), Range.all())
        self.assertEqual(Range.greater_than(2), Range.greater_than(2))
        self.assertEqual(Range.open(1, 5), Range.open(1, 5))

    def test_encloses_open(self):
        rng = Range.open(2, 5)
        self.assertTrue(rng.encloses(rng))
        self.assertTrue(rng.encloses(Range.open(2, 4)))
        self.assertTrue(rng.encloses(Range.open(3, 5)))
        self.assertTrue(rng.encloses(Range.closed(3, 4)))

        self.assertFalse(rng.encloses(Range.open_closed(2, 5)))
        self.assertFalse(rng.encloses(Range.closed_open(2, 5)))
        self.assertFalse(rng.encloses(Range.closed(1, 4)))
        self.assertFalse(rng.encloses(Range.closed(3, 6)))
        self.assertFalse(rng.encloses(Range.greater_than(3)))
        self.assertFalse(rng.encloses(Range.less_than(3)))
        self.assertFalse(rng.encloses(Range.at_least(3)))
        self.assertFalse(rng.encloses(Range.at_most(3)))
        self.assertFalse(rng.encloses(Range.all()))

    def test_encloses_closed(self):
        rng = Range.closed(2, 5)
        self.assertTrue(rng.encloses(rng))
        self.assertTrue(rng.encloses(Range.open(2, 5)))
        self.assertTrue(rng.encloses(Range.open_closed(2, 5)))
        self.assertTrue(rng.encloses(Range.closed_open(2, 5)))
        self.assertTrue(rng.encloses(Range.closed(3, 5)))
        self.assertTrue(rng.encloses(Range.closed(2, 4)))

        self.assertFalse(rng.encloses(Range.open(1, 6)))
        self.assertFalse(rng.encloses(Range.greater_than(3)))
        self.assertFalse(rng.encloses(Range.less_than(3)))
        self.assertFalse(rng.encloses(Range.at_least(3)))
        self.assertFalse(rng.encloses(Range.at_most(3)))
        self.assertFalse(rng.encloses(Range.all()))

    def check_contains(self, rng: Range[int]) -> None:
        self.assertFalse(4 in rng)
        self.assertTrue(5 in rng)
        self.assertTrue(7 in rng)
        self.assertFalse(8 in rng)

    def assert_unbounded_below(self, rng: Range[Any]):
        self.assertFalse(rng.has_lower_bound())
        with self.assertRaises(ValueError):
            rng.lower_endpoint()
        # pylint: disable=pointless-statement
        with self.assertRaises(AssertionError):
            rng.lower_bound_type

    def assert_unbounded_above(self, rng: Range[Any]):
        self.assertFalse(rng.has_upper_bound())
        with self.assertRaises(ValueError):
            rng.upper_endpoint()
        # pylint: disable=pointless-statement
        with self.assertRaises(AssertionError):
            rng.upper_bound_type

    def test_cuts(self):
        self.assertFalse(_BELOW_ALL < _BELOW_ALL)
        self.assertFalse(_BELOW_ALL > _BELOW_ALL)
        self.assertTrue(_BELOW_ALL in [_BELOW_ALL])

    def test_intersection_empty(self):
        rng = Range.closed_open(3, 3)
        self.assertEqual(rng, rng.intersection(rng))
        with self.assertRaises(ValueError):
            rng.intersection(Range.open(3, 5))
        with self.assertRaises(ValueError):
            rng.intersection(Range.closed(0, 2))

    def test_intersection_de_facto_empty(self):
        rng = Range.open(3, 4)
        self.assertEqual(rng, rng.intersection(rng))
        self.assertEqual(Range.open_closed(3, 3), rng.intersection(Range.at_most(3)))
        self.assertEqual(Range.closed_open(4, 4), rng.intersection(Range.at_least(4)))

        with self.assertRaises(ValueError):
            rng.intersection(Range.less_than(3))
        with self.assertRaises(ValueError):
            rng.intersection(Range.greater_than(4))

        rng2 = Range.closed(3, 4)
        self.assertEqual(
            Range.open_closed(4, 4), rng2.intersection(Range.greater_than(4))
        )

    def test_intersection_singleton(self):
        rng = Range.closed(3, 3)
        self.assertEqual(rng, rng.intersection(rng))

        self.assertEqual(rng, rng.intersection(Range.at_most(4)))
        self.assertEqual(rng, rng.intersection(Range.at_most(3)))
        self.assertEqual(rng, rng.intersection(Range.at_least(3)))
        self.assertEqual(rng, rng.intersection(Range.at_least(2)))

        self.assertEqual(Range.closed_open(3, 3), rng.intersection(Range.less_than(3)))
        self.assertEqual(Range.open_closed(3, 3), rng.intersection(Range.greater_than(3)))

        with self.assertRaises(ValueError):
            rng.intersection(Range.at_least(4))
        with self.assertRaises(ValueError):
            rng.intersection(Range.at_most(2))

    def test_intersection_general(self):
        rng = Range.closed(4, 8)

        # separate
        with self.assertRaises(ValueError):
            rng.intersection(Range.closed(0, 2))

        # adjacent below
        self.assertEqual(
            Range.closed_open(4, 4), rng.intersection(Range.closed_open(2, 4))
        )

        # overlap below
        self.assertEqual(Range.closed(4, 6), rng.intersection(Range.closed(2, 6)))

        # enclosed with same start
        self.assertEqual(Range.closed(4, 6), rng.intersection(Range.closed(4, 6)))

        # enclosed, interior
        self.assertEqual(Range.closed(5, 7), rng.intersection(Range.closed(5, 7)))

        # enclosed with same end
        self.assertEqual(Range.closed(6, 8), rng.intersection(Range.closed(6, 8)))

        # equal
        self.assertEqual(rng, rng.intersection(rng))

        # enclosing with same start
        self.assertEqual(rng, rng.intersection(Range.closed(4, 10)))

        # enclosing with same end
        self.assertEqual(rng, rng.intersection(Range.closed(2, 8)))

        # enclosing, exterior
        self.assertEqual(rng, rng.intersection(Range.closed(2, 10)))

        # overlap above
        self.assertEqual(Range.closed(6, 8), rng.intersection(Range.closed(6, 10)))

        # adjacent above
        self.assertEqual(
            Range.open_closed(8, 8), rng.intersection(Range.open_closed(8, 10))
        )

        with self.assertRaises(ValueError):
            rng.intersection(Range.closed(10, 12))

    def test_intersects(self):
        rng = Range.closed(4, 8)

        # separate
        self.assertFalse(rng.intersects(Range.closed(0, 2)))

        # adjacent below
        self.assertTrue(rng.intersects(Range.closed_open(2, 4)))

        # overlap below
        self.assertTrue(rng.intersects(Range.closed(2, 6)))

        # enclosed with same start
        self.assertTrue(rng.intersects(Range.closed(4, 6)))

        # enclosed, interior
        self.assertTrue(rng.intersects(Range.closed(5, 7)))

        # enclosed with same end
        self.assertTrue(rng.intersects(Range.closed(6, 8)))

        # equal
        self.assertTrue(rng.intersects(rng))

        # enclosing with same start
        self.assertTrue(rng.intersects(Range.closed(4, 10)))

        # enclosing with same end
        self.assertTrue(rng.intersects(Range.closed(2, 8)))

        # enclosing, exterior
        self.assertTrue(rng.intersects(Range.closed(2, 10)))

        # overlap above
        self.assertTrue(rng.intersects(Range.closed(6, 10)))

        # adjacent above
        self.assertTrue(rng.intersects(Range.open_closed(8, 10)))

        self.assertFalse(rng.intersects(Range.closed(10, 12)))

    def test_create_spanning(self) -> None:
        with self.assertRaisesRegex(
            ValueError, "Cannot create range from span of empty range collection"
        ):
            Range.create_spanning([])

    def test_check_usable_in_set(self) -> None:
        range_set = ImmutableSet.of(
            [
                Range.open_closed(0, 1),
                Range.open_closed(0, 1),
                Range.at_most(1),
                Range.at_most(1),
            ]
        )
        self.assertEqual(2, len(range_set))

    def test_range_set_equality(self) -> None:
        self.assertEqual(
            ImmutableRangeSet.builder()  # type: ignore
            .add(Range.at_most(2))
            .add(Range.at_least(5))
            .build(),
            ImmutableRangeSet.builder()  # type: ignore
            .add(Range.at_least(5))
            .add(Range.at_most(2))
            .build(),
        )

    def test_range_enclosing_range(self) -> None:
        range_set: MutableRangeSet[int] = RangeSet.create_mutable()
        range_set.add_all([Range.at_most(2), Range.open_closed(5, 8), Range.at_least(10)])
        self.assertEqual(None, range_set.range_enclosing_range(Range.closed(2, 3)))
        self.assertEqual(
            Range.at_most(2), range_set.range_enclosing_range(Range.open(-1, 0))
        )
        self.assertEqual(
            Range.open_closed(5, 8),
            range_set.range_enclosing_range(Range.closed_open(6, 7)),
        )
        self.assertEqual(None, range_set.range_enclosing_range(Range.closed(5, 8)))

    def test_range_clear(self) -> None:
        range_set: MutableRangeSet[int] = RangeSet.create_mutable()
        range_set.add_all([Range.at_most(2), Range.open_closed(5, 8), Range.at_least(10)])
        range_set.clear()
        self.assertEqual(0, len(range_set.as_ranges()))

    def test_immutable_range_map_empty(self) -> None:
        self.assertTrue(ImmutableRangeMap.empty().is_empty())

    def test_ranges_enclosed_by_out_of_bounds(self) -> None:
        self.assertEqual(
            ImmutableSet.empty(),
            RangeSet.create_mutable()  # type: ignore
            .add(Range.closed(0, 10))
            .ranges_enclosed_by(Range.at_least(20)),
        )
