import pickle
from typing import List, Sequence
from unittest import TestCase

from immutablecollections import ImmutableSet, immutableset
from sortedcontainers import SortedDict

from vistautils.iterutils import tile_with_pairs

# noinspection PyProtectedMember
from vistautils.range import (
    BoundType,
    ImmutableRangeSet,
    MutableRangeSet,
    Range,
    RangeSet,
    _value_at_or_above,
    _value_at_or_below,
    _value_below,
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

    def test_intersect_ranges(self):
        range_set = RangeSet.create_mutable()
        range_set.add_all(
            [
                Range.closed(2, 4),
                Range.closed(5, 7),
                Range.closed(10, 12),
                Range.closed(18, 20),
            ]
        )
        self.assertEqual(range_set.ranges_overlapping(Range.closed(0, 1)), immutableset())
        self.assertEqual(
            range_set.ranges_overlapping(Range.closed(21, 23)), immutableset()
        )
        self.assertEqual(
            range_set.ranges_overlapping(Range.closed(13, 15)), immutableset()
        )
        self.assertEqual(
            range_set.ranges_overlapping(Range.closed(0, 2)),
            immutableset([Range.closed(2, 4)]),
        )
        self.assertEqual(
            range_set.ranges_overlapping(Range.closed(12, 15)),
            immutableset([Range.closed(10, 12)]),
        )
        self.assertEqual(
            range_set.ranges_overlapping(Range.closed(5, 16)),
            immutableset([Range.closed(5, 7), Range.closed(10, 12)]),
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
        self.assertEqual(tuple([Range.closed(1, 6)]), tuple(range_set.as_ranges()))

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
        self.assertEqual(tuple([Range.closed_open(1, 6)]), tuple(range_set.as_ranges()))

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
        self.assertEqual(tuple(range_set.as_ranges()), tuple([Range.open_closed(1, 11)]))

    def test_all_single_ranges_intersecting(self):
        for query in TestRangeSet.QUERY_RANGES:
            self._test_intersects(RangeSet.create_mutable().add(query))

    def test_all_two_ranges_intersecting(self):
        for query_1 in TestRangeSet.QUERY_RANGES:
            for query_2 in TestRangeSet.QUERY_RANGES:
                self._test_intersects(RangeSet.create_mutable().add(query_1).add(query_2))

    # forms the basis for corresponding tests in test_range_map
    def test_rightmost_containing_or_below(self):
        range_set = RangeSet.create_mutable().add_all(
            (
                Range.closed(-2, -1),
                Range.closed_open(0, 2),
                # we don't do [0, 2), [2.1, 3] because they will coalesce
                # ditto for (4, 5] and (5.1, 7)
                Range.closed(2.1, 3),
                Range.open_closed(4, 5),
                Range.open(5.1, 7),
            )
        )

        # probe value is in the middle of a set
        # [2.1  ... *2.5* ... 3]
        self.assertEqual(
            Range.closed(2.1, 3.0), range_set.rightmost_containing_or_below(2.5)
        )
        # probe value is at a closed upper limit
        # [2.1 .... *3*]
        self.assertEqual(
            Range.closed(2.1, 3.0), range_set.rightmost_containing_or_below(3.0)
        )
        # probe value is at a closed lower limit
        # [*2.1* .... 3]
        self.assertEqual(
            Range.closed(2.1, 3.0), range_set.rightmost_containing_or_below(2.1)
        )
        # probe value is at an open lower limit
        # [2.1 ... 3], (*4* ... 5]
        self.assertEqual(
            Range.closed(2.1, 3.0), range_set.rightmost_containing_or_below(4.0)
        )
        # probe value is at an open upper limit
        # [0 ... *2.1*)
        self.assertEqual(
            Range.closed_open(0.0, 2.0), range_set.rightmost_containing_or_below(2.0)
        )
        # probe value falls into a gap
        # [-2, -1] ... *-0.5* ... [0, 2)
        self.assertEqual(
            Range.closed(-2.0, -1.0), range_set.rightmost_containing_or_below(-0.5)
        )
        # no range below
        # *-3* .... [-2,-1]
        self.assertIsNone(range_set.rightmost_containing_or_below(-3.0))
        # empty rangeset
        self.assertIsNone(
            RangeSet.create_mutable()
            .add(Range.closed(1.0, 2.0))
            .rightmost_containing_or_below(0.0)
        )
        # lowest range has open lower bound
        # (*1*,2)
        self.assertIsNone(
            RangeSet.create_mutable()
            .add(Range.open(1.0, 2.0))
            .rightmost_containing_or_below(1.0)
        )

    # forms the basis for corresponding tests in test_range_set
    def test_leftmost_containing_or_above(self):
        range_set = RangeSet.create_mutable().add_all(
            (
                Range.closed(-2, -1),
                Range.closed_open(0, 2),
                # we don't do [0, 2), [2.1, 3] because they will coalesce
                # ditto for (4, 5] and (5.1, 7)
                Range.closed(2.1, 3),
                Range.open_closed(4, 5),
                Range.open(5.1, 7),
            )
        )

        # probe value is in the middle of a set
        # [2.1  ... *2.5* ... 3]
        self.assertEqual(
            Range.closed(2.1, 3.0), range_set.leftmost_containing_or_above(2.5)
        )
        # probe value is at a closed upper limit
        # [2.1 .... *3*]
        self.assertEqual(
            Range.closed(2.1, 3.0), range_set.leftmost_containing_or_above(3.0)
        )
        # probe value is at a closed lower limit
        # [*2.1* .... 3]
        self.assertEqual(
            Range.closed(2.1, 3.0), range_set.leftmost_containing_or_above(2.1)
        )
        # probe value is at an open lower limit
        # [2 ... 3], (*4* ... 5]
        self.assertEqual(
            Range.open_closed(4.0, 5.0), range_set.leftmost_containing_or_above(4.0)
        )
        # probe value is at an open upper limit
        # [0 ... *2*) [2.1, 3.0]
        self.assertEqual(
            Range.closed(2.1, 3.0), range_set.leftmost_containing_or_above(2.0)
        )
        # probe value falls into a gap
        # [-2, -1] ... *-0.5* ... [0, 2)
        self.assertEqual(
            Range.closed_open(0, 2), range_set.leftmost_containing_or_above(-0.5)
        )
        # no range above
        # (5.1 ... 7) ... *8*
        self.assertIsNone(range_set.leftmost_containing_or_above(8))
        # empty rangeset
        self.assertIsNone(
            RangeSet.create_mutable()
            .add(Range.closed(1.0, 2.0))
            .leftmost_containing_or_above(3.0)
        )
        # higher range has open upper bound
        # (1,*2*)
        self.assertIsNone(
            RangeSet.create_mutable()
            .add(Range.open(1.0, 2.0))
            .leftmost_containing_or_above(2.0)
        )

    def test_len(self):
        self.assertEqual(0, len(RangeSet.create_mutable()))
        self.assertEqual(1, len(RangeSet.create_mutable().add(Range.closed(1, 2))))
        self.assertEqual(
            2,
            len(RangeSet.create_mutable().add(Range.closed(1, 2)).add(Range.open(3, 4))),
        )

    # support methods

    def _pair_test(self, a: Range[int], b: Range[int]) -> None:
        range_set: MutableRangeSet[int] = RangeSet.create_mutable()
        range_set.add(a)
        range_set.add(b)
        if a.is_empty() and b.is_empty():
            self.assertTrue(range_set.is_empty())
            self.assertFalse(range_set.as_ranges())
        elif a.is_empty():
            self.assertTrue(b in range_set.as_ranges())
        elif b.is_empty():
            self.assertTrue(a in range_set.as_ranges())
        elif a.is_connected(b):
            self.assertEqual(tuple(range_set.as_ranges()), tuple([a.span(b)]))
        else:
            if a.lower_endpoint < b.lower_endpoint:
                self.assertEqual(tuple(range_set.as_ranges()), tuple([a, b]))
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
        as_ranges: Sequence[Range[int]] = tuple(range_set.as_ranges())

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
                # pylint: disable=pointless-statement
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

    def test_pickling(self):
        empty_mutable_rangeset = MutableRangeSet.create_mutable()
        empty_immutable_rangeset = ImmutableRangeSet.builder().build()
        ranges = (Range.closed(0, 2), Range.closed(5, 29), Range.closed(35, 39))
        mutable_rangeset = MutableRangeSet.create_mutable().add_all(ranges)
        immutable_rangeset = ImmutableRangeSet.builder().add_all(ranges).build()

        self.assertEqual(
            empty_mutable_rangeset, pickle.loads(pickle.dumps(empty_mutable_rangeset))
        )
        self.assertEqual(
            empty_immutable_rangeset, pickle.loads(pickle.dumps(empty_immutable_rangeset))
        )
        self.assertEqual(mutable_rangeset, pickle.loads(pickle.dumps(mutable_rangeset)))
        self.assertEqual(
            immutable_rangeset, pickle.loads(pickle.dumps(immutable_rangeset))
        )

        self.assertEqual(empty_mutable_rangeset.__getstate__(), ())
        self.assertEqual(empty_immutable_rangeset.__getstate__(), ())

        self.assertEqual(mutable_rangeset.__getstate__(), ranges)
        self.assertEqual(immutable_rangeset.__getstate__(), ranges)
