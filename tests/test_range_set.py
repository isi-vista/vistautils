from typing import List
from unittest import TestCase

from sortedcontainers import SortedDict

from vistautils.iterutils import tile_with_pairs
from immutablecollections import ImmutableSet, ImmutableList

# noinspection PyProtectedMember
from vistautils.range import (
    Range,
    BoundType,
    RangeSet,
    _value_below,
    _value_at_or_below,
    _value_at_or_above,
)


class TestRangeSet(TestCase):
    """
    Tests for RangeSet

    Derived from Guava's TreeRangeSet tests, which were written by Louis Wasserman and Chris Povrik
    """

    MIN_BOUND = -1
    MAX_BOUND = 1
    BOUND_TYPES = [BoundType.open(), BoundType.closed()]

    QUERY_RANGES: List[Range[int]] = [Range.all()]
    for i in range(MIN_BOUND, MAX_BOUND + 1):
        QUERY_RANGES.extend(
            [
                Range.at_most(i),
                Range.at_least(i),
                Range.less_than(i),
                Range.greater_than(i),
                Range.closed(i, i),
                Range.open_closed(i, i),
                Range.closed_open(i, i),
            ]
        )
        for j in range(i + 1, MAX_BOUND + 1):
            QUERY_RANGES.extend(
                [
                    Range.open(i, j),
                    Range.open_closed(i, j),
                    Range.closed_open(i, j),
                    Range.closed(i, j),
                ]
            )

    def test_empty_enclosing(self):
        self._test_encloses(RangeSet.create_mutable())

    def test_empty_intersects(self):
        self._test_intersects(RangeSet.create_mutable())

    def test_all_single_ranges_enclosing(self):
        for query_range in TestRangeSet.QUERY_RANGES:
            self._test_encloses(RangeSet.create_mutable().add(query_range))
        # also test for the complement of empty once complements are implemented

    def test_all_pair_ranges_enclosing(self):
        for query_range_1 in TestRangeSet.QUERY_RANGES:
            for query_range_2 in TestRangeSet.QUERY_RANGES:
                self._test_encloses(
                    RangeSet.create_mutable().add(query_range_1).add(query_range_2)
                )

    def test_merges_connected_with_overlap(self):
        range_set = RangeSet.create_mutable()
        range_set.add(Range.closed(1, 4))
        range_set.add(Range.open(2, 6))
        self._test_invariants(range_set)
        self.assertTrue(Range.closed_open(1, 6) in range_set.as_ranges())

    def test_merges_connected_disjoint(self):
        range_set = RangeSet.create_mutable()
        range_set.add(Range.closed(1, 4))
        range_set.add(Range.open(4, 6))
        self._test_invariants(range_set)
        self.assertTrue(Range.closed_open(1, 6) in range_set.as_ranges())

    def test_ignores_smaller_sharing_no_bound(self):
        range_set = RangeSet.create_mutable()
        range_set.add(Range.closed(1, 6))
        range_set.add(Range.open(2, 4))
        self._test_invariants(range_set)
        self.assertTrue(Range.closed(1, 6) in range_set.as_ranges())

    def test_ignores_smaller_sharing_lower_bound(self):
        range_set = RangeSet.create_mutable()
        range_set.add(Range.closed(1, 6))
        range_set.add(Range.closed(1, 4))
        self._test_invariants(range_set)
        self.assertEqual(
            ImmutableList.of([Range.closed(1, 6)]),
            ImmutableList.of(range_set.as_ranges()),
        )

    def test_ignores_smaller_sharing_upper_bound(self):
        range_set = RangeSet.create_mutable()
        range_set.add(Range.closed(1, 6))
        range_set.add(Range.closed(3, 6))
        self._test_invariants(range_set)
        self.assertTrue(Range.closed(1, 6) in range_set.as_ranges())

    def test_ignores_equal(self):
        range_set = RangeSet.create_mutable()
        range_set.add(Range.closed(1, 6))
        range_set.add(Range.closed(1, 6))
        self._test_invariants(range_set)
        self.assertTrue(Range.closed(1, 6) in range_set.as_ranges())

    def test_extend_same_lower_bound(self):
        range_set = RangeSet.create_mutable()
        range_set.add(Range.closed(1, 4))
        range_set.add(Range.closed(1, 6))
        self._test_invariants(range_set)
        self.assertTrue(Range.closed(1, 6) in range_set.as_ranges())

    def test_extend_same_upper_bound(self):
        range_set = RangeSet.create_mutable()
        range_set.add(Range.closed(3, 6))
        range_set.add(Range.closed(1, 6))
        self._test_invariants(range_set)
        self.assertTrue(Range.closed(1, 6) in range_set.as_ranges())

    def test_extend_both_directions(self):
        range_set = RangeSet.create_mutable()
        range_set.add(Range.closed(3, 4))
        range_set.add(Range.closed(1, 6))
        self._test_invariants(range_set)
        self.assertTrue(Range.closed(1, 6) in range_set.as_ranges())

    def test_add_empty(self):
        range_set = RangeSet.create_mutable()
        range_set.add(Range.closed_open(3, 3))
        self._test_invariants(range_set)
        self.assertTrue(len(range_set.as_ranges()) == 0)
        self.assertTrue(range_set.is_empty())

    def test_fill_hole_exactly(self):
        range_set = RangeSet.create_mutable()
        range_set.add(Range.closed_open(1, 3))
        range_set.add(Range.closed_open(4, 6))
        range_set.add(Range.closed_open(3, 4))
        self._test_invariants(range_set)
        self.assertTrue(Range.closed_open(1, 6) in range_set.as_ranges())

    def test_fill_hole_with_overlap(self):
        range_set = RangeSet.create_mutable()
        range_set.add(Range.closed_open(1, 3))
        range_set.add(Range.closed_open(4, 6))
        range_set.add(Range.closed_open(2, 5))
        self._test_invariants(range_set)
        self.assertEqual(
            ImmutableList.of([Range.closed_open(1, 6)]),
            ImmutableList.of(range_set.as_ranges()),
        )

    def test_add_many_pairs(self):
        for a_low in range(0, 6):
            for a_high in range(0, 6):
                if a_low > a_high:
                    continue
                a_ranges = [
                    Range.closed(a_low, a_high),
                    Range.open_closed(a_low, a_high),
                    Range.closed_open(a_low, a_high),
                ]
                if a_low != a_high:
                    a_ranges.append(Range.open(a_low, a_high))

                for b_low in range(0, 6):
                    for b_high in range(0, 6):
                        if b_low > b_high:
                            continue
                        b_ranges = [
                            Range.closed(b_low, b_high),
                            Range.open_closed(b_low, b_high),
                            Range.closed_open(b_low, b_high),
                        ]
                        if b_low != b_high:
                            b_ranges.append(Range.open(b_low, b_high))
                        for a_range in a_ranges:
                            for b_range in b_ranges:
                                self._pair_test(a_range, b_range)

    def test_range_containing1(self):
        range_set = RangeSet.create_mutable()
        range_set.add(Range.closed(3, 10))
        self.assertEqual(Range.closed(3, 10), range_set.range_containing(5))
        self.assertTrue(5 in range_set)
        self.assertIsNone(range_set.range_containing(1))
        self.assertFalse(1 in range_set)

    def test_add_all(self):
        range_set = RangeSet.create_mutable()
        range_set.add(Range.closed(3, 10))
        range_set.add_all([Range.open(1, 3), Range.closed(5, 8), Range.closed(9, 11)])
        self.assertEqual(
            ImmutableList.of(range_set.as_ranges()),
            ImmutableList.of([Range.open_closed(1, 11)]),
        )

    def test_all_single_ranges_intersecting(self):
        for query in TestRangeSet.QUERY_RANGES:
            self._test_intersects(RangeSet.create_mutable().add(query))

    def test_all_two_ranges_intersecting(self):
        for query_1 in TestRangeSet.QUERY_RANGES:
            for query_2 in TestRangeSet.QUERY_RANGES:
                self._test_intersects(RangeSet.create_mutable().add(query_1).add(query_2))

    # support methods

    def _pair_test(self, a: Range[int], b: Range[int]) -> None:
        range_set = RangeSet.create_mutable()
        range_set.add(a)
        range_set.add(b)
        if a.is_empty() and b.is_empty():
            range_set.is_empty()
            self.assertTrue(len(range_set.as_ranges()) == 0)
        elif a.is_empty():
            self.assertTrue(b in range_set.as_ranges())
        elif b.is_empty():
            self.assertTrue(a in range_set.as_ranges())
        elif a.is_connected(b):
            self.assertEqual(
                ImmutableList.of(range_set.as_ranges()), ImmutableList.of([a.span(b)])
            )
        else:
            if a.lower_endpoint < b.lower_endpoint:
                self.assertEqual(
                    ImmutableList.of(range_set.as_ranges()), ImmutableList.of([a, b])
                )
            else:
                self.assertEqual(
                    ImmutableSet.of([a, b]), ImmutableSet.of(range_set.as_ranges())
                )

    def _test_encloses(self, range_set: RangeSet[int]):
        self.assertTrue(range_set.encloses_all(ImmutableSet.empty()))
        for query_range in TestRangeSet.QUERY_RANGES:
            expected_to_enclose = any(
                x.encloses(query_range) for x in range_set.as_ranges()
            )
            self.assertEqual(expected_to_enclose, range_set.encloses(query_range))
            self.assertEqual(expected_to_enclose, range_set.encloses_all([query_range]))

    def _test_intersects(self, range_set: RangeSet[int]):
        for query in TestRangeSet.QUERY_RANGES:
            expect_intersects = any(
                r.is_connected(query) and not r.intersection(query).is_empty()
                for r in range_set.as_ranges()
            )
            self.assertEqual(expect_intersects, range_set.intersects(query))

    def _test_invariants(self, range_set: RangeSet[int]):
        self.assertEqual(len(range_set.as_ranges()) == 0, range_set.is_empty())
        as_ranges: List[Range[int]] = ImmutableList.of(range_set.as_ranges())

        # test that connected ranges are coalesced
        for (range_1, range_2) in tile_with_pairs(as_ranges):
            self.assertFalse(range_1.is_connected(range_2))

        for rng in as_ranges:
            self.assertFalse(rng.is_empty())

        # test that the RangeSet's span is the span of all the ranges
        if as_ranges:
            self.assertEqual(Range.create_spanning(range_set.as_ranges()), range_set.span)
        else:
            with self.assertRaises(ValueError):
                # noinspection PyStatementEffect
                range_set.span

    # test internal utility functions

    def test_entry_above_below(self):
        sorted_dict = SortedDict({1: 1, 3: 3, 5: 5, 7: 7, 9: 9})
        value_at_or_below_reference = (
            (0, None),
            (1, 1),
            (2, 1),
            (3, 3),
            (4, 3),
            (5, 5),
            (6, 5),
            (7, 7),
            (8, 7),
            (9, 9),
            (10, 9),
            (200, 9),
        )
        for (key, ref) in value_at_or_below_reference:
            self.assertEqual(_value_at_or_below(sorted_dict, key), ref)

        value_below_reference = (
            (0, None),
            (1, None),
            (2, 1),
            (3, 1),
            (4, 3),
            (5, 3),
            (6, 5),
            (7, 5),
            (8, 7),
            (9, 7),
            (10, 9),
            (200, 9),
        )
        for (key, ref) in value_below_reference:
            self.assertEqual(_value_below(sorted_dict, key), ref)

        value_at_or_above_reference = (
            (0, 1),
            (1, 1),
            (2, 3),
            (3, 3),
            (4, 5),
            (5, 5),
            (6, 7),
            (7, 7),
            (8, 9),
            (9, 9),
            (10, None),
            (200, None),
        )
        for (key, ref) in value_at_or_above_reference:
            self.assertEqual(_value_at_or_above(sorted_dict, key), ref)
