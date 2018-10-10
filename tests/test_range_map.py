from unittest import TestCase

from flexnlp.utils.immutablecollections import ImmutableSet
from flexnlp.utils.range import ImmutableRangeMap, Range


class TestRangeMap(TestCase):
    def test_empty(self):
        self.assertFalse(0 in ImmutableRangeMap.empty())

    def test_no_overlap(self):
        with self.assertRaises(ValueError):
            (ImmutableRangeMap.builder().put(Range.closed(0, 2), 'foo')
                .put(Range.closed(1, 3), 'bar').build())

    def test_lookup(self):
        range_map = (ImmutableRangeMap.builder()
            .put(Range.closed(0, 2), 'foo')
            .put(Range.open_closed(6, 8), 'bar').build())
        self.assertEqual('foo', range_map[0])
        self.assertEqual('foo', range_map[1])
        self.assertEqual('foo', range_map[2])
        self.assertEqual(None, range_map[6])
        self.assertEqual('bar', range_map[7])
        self.assertEqual('bar', range_map[8])
        self.assertEqual(None, range_map[9])

    def test_enclosed(self):
        range_map: ImmutableRangeMap[int, str] = (ImmutableRangeMap.builder()
            .put(Range.closed(0, 2), 'foo')
            .put(Range.open_closed(6, 8), 'bar')
            .put(Range.open(12, 14), 'meep')
            .build())

        self.assertEqual(ImmutableSet.of(['foo', 'bar', 'meep']),
                         range_map.get_enclosed_by(Range.closed(-1, 15)))
        self.assertEqual(ImmutableSet.of(['foo']), range_map.get_enclosed_by(Range.closed(0, 6)))
        self.assertEqual(ImmutableSet.empty(), range_map.get_enclosed_by(Range.closed(5, 5)))
