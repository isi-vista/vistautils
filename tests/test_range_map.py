from unittest import TestCase

from immutablecollections import ImmutableSet
from vistautils.range import ImmutableRangeMap, Range, immutablerangemap


class TestRangeMap(TestCase):
    def test_empty(self):
        self.assertFalse(0 in ImmutableRangeMap.empty())

    def test_no_overlap(self):
        with self.assertRaises(ValueError):
            (
                ImmutableRangeMap.builder()
                .put(Range.closed(0, 2), "foo")
                .put(Range.closed(1, 3), "bar")
                .build()
            )

    def test_lookup(self):
        range_map = (
            ImmutableRangeMap.builder()
            .put(Range.closed(0, 2), "foo")
            .put(Range.open_closed(6, 8), "bar")
            .build()
        )
        self.assertEqual("foo", range_map[0])
        self.assertEqual("foo", range_map[1])
        self.assertEqual("foo", range_map[2])
        self.assertEqual(None, range_map[6])
        self.assertEqual("bar", range_map[7])
        self.assertEqual("bar", range_map[8])
        self.assertEqual(None, range_map[9])

    def test_enclosed(self):
        range_map: ImmutableRangeMap[int, str] = (
            ImmutableRangeMap.builder()
            .put(Range.closed(0, 2), "foo")
            .put(Range.open_closed(6, 8), "bar")
            .put(Range.open(12, 14), "meep")
            .build()
        )

        self.assertEqual(
            ImmutableSet.of(["foo", "bar", "meep"]),
            range_map.get_enclosed_by(Range.closed(-1, 15)),
        )
        self.assertEqual(
            ImmutableSet.of(["foo"]), range_map.get_enclosed_by(Range.closed(0, 6))
        )
        self.assertEqual(
            ImmutableSet.empty(), range_map.get_enclosed_by(Range.closed(5, 5))
        )

    def test_overlapping_keys_banned(self):
        with self.assertRaisesRegex(
            ValueError,
            "Some range keys are connected or overlapping. Overlapping keys "
            "will never be supported. Support for connected keys is tracked in "
            "https://github.com/isi-vista/vistautils/issues/37",
        ):
            (
                ImmutableRangeMap.builder()
                .put(Range.closed(0, 2), 0)
                .put(Range.closed(1, 3), 1)
                .build()
            )

    # this test should be remove after
    # https://github.com/isi-vista/vistautils/issues/37 is fixed
    def test_temporary_exception_on_connected_range_keys(self):
        with self.assertRaisesRegex(
            ValueError,
            "Some range keys are connected or overlapping. Overlapping keys "
            "will never be supported. Support for connected keys is tracked in "
            "https://github.com/isi-vista/vistautils/issues/37",
        ):
            (
                ImmutableRangeMap.builder()
                .put(Range.open(0, 2), 0)
                .put(Range.closed(2, 3), 1)
                .build()
            )

    # adapted from corresponding tests in test_range_set
    def test_get_maximal_containing_or_below(self):
        range_map = immutablerangemap(
            (
                (Range.closed(-2, -1), 0),
                (Range.closed_open(0, 2), 1),
                # we don't do [0, 2), [2.1, 3] because they will coalesce
                # ditto for (4, 5] and (5.1, 7)
                (Range.closed(2.1, 3), 2),
                (Range.open_closed(4, 5), 3),
                (Range.open(5.1, 7), 4),
            )
        )

        # probe value is in the middle of a set
        # [2.1  ... *2.5* ... 3]
        self.assertEqual(2, range_map.get_from_maximal_containing_or_below(2.5))
        # probe value is at a closed upper limit
        # [2.1 .... *3*]
        self.assertEqual(2, range_map.get_from_maximal_containing_or_below(3.0))
        # probe value is at a closed lower limit
        # [*2.1* .... 3]
        self.assertEqual(2, range_map.get_from_maximal_containing_or_below(2.1))
        # probe value is at an open lower limit
        # [2.1 ... 3], (*4* ... 5]
        self.assertEqual(2, range_map.get_from_maximal_containing_or_below(4.0))
        # probe value is at an open upper limit
        # [0 ... *2.1*)
        self.assertEqual(1, range_map.get_from_maximal_containing_or_below(2.0))
        # probe value falls into a gap
        # [-2, -1] ... *-0.5* ... [0, 2)
        self.assertEqual(0, range_map.get_from_maximal_containing_or_below(-0.5))
        # no range below
        # *-3* .... [-2,-1]
        self.assertIsNone(range_map.get_from_maximal_containing_or_below(-3.0))
        # empty rangeset
        self.assertIsNone(
            immutablerangemap(
                ((Range.closed(1.0, 2.0), 1),)
            ).get_from_maximal_containing_or_below(0.0)
        )
        # lowest range has open lower bound
        # (*1*,2)
        self.assertIsNone(
            immutablerangemap(
                ((Range.open(1.0, 2.0), 1),)
            ).get_from_maximal_containing_or_below(1.0)
        )

    # adapted from corresponding tests in test_range_set
    def test_get_minimal_containing_or_above(self):
        range_map = immutablerangemap(
            (
                (Range.closed(-2, -1), 0),
                (Range.closed_open(0, 2), 1),
                # we don't do [0, 2), [2.1, 3] because they will coalesce
                # ditto for (4, 5] and (5.1, 7)
                (Range.closed(2.1, 3), 2),
                (Range.open_closed(4, 5), 3),
                (Range.open(5.1, 7), 4),
            )
        )

        # probe value is in the middle of a set
        # [2.1  ... *2.5* ... 3]
        self.assertEqual(2, range_map.get_from_minimal_containing_or_above(2.5))
        # probe value is at a closed upper limit
        # [2.1 .... *3*]
        self.assertEqual(2, range_map.get_from_minimal_containing_or_above(3.0))
        # probe value is at a closed lower limit
        # [*2.1* .... 3]
        self.assertEqual(2, range_map.get_from_minimal_containing_or_above(2.1))
        # probe value is at an open lower limit
        # [2 ... 3], (*4* ... 5]
        self.assertEqual(3, range_map.get_from_minimal_containing_or_above(4.0))
        # probe value is at an open upper limit
        # [0 ... *2*) [2.1, 3.0]
        self.assertEqual(2, range_map.get_from_minimal_containing_or_above(2.0))
        # probe value falls into a gap
        # [-2, -1] ... *-0.5* ... [0, 2)
        self.assertEqual(1, range_map.get_from_minimal_containing_or_above(-0.5))
        # no range above
        # (5.1 ... 7) ... *8*
        self.assertIsNone(range_map.get_from_minimal_containing_or_above(8))
        # empty rangeset
        self.assertIsNone(
            immutablerangemap(
                ((Range.closed(1.0, 2.0), 1),)
            ).get_from_minimal_containing_or_above(3.0)
        )
        # higher range has open upper bound
        # (1,*2*)
        self.assertIsNone(
            immutablerangemap(
                ((Range.open(1.0, 2.0), 1),)
            ).get_from_minimal_containing_or_above(2.0)
        )
