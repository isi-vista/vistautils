from unittest import TestCase

from attr import attrs
from immutablecollections import immutableset

from vistautils.span import Span, HasSpanIndex


@attrs(auto_attribs=True, frozen=True, slots=True)
class Foo:
    span: Span


@attrs(auto_attribs=True, frozen=True, slots=True)
class Bar:
    span: Span


class TestSpan(TestCase):
    def test_index(self) -> None:
        overlapping_items = (
            Foo(Span(0, 10)),
            Foo(Span(5, 25)),
            Foo(Span(20, 30)),
            Bar(Span(20, 30)),
        )
        index = HasSpanIndex.index(overlapping_items)
        self.assertEqual(
            immutableset([overlapping_items[0]]), index.get_exactly_matching(Span(0, 10))
        )
        self.assertEqual(
            immutableset([overlapping_items[1]]), index.get_exactly_matching(Span(5, 25))
        )
        self.assertEqual(
            immutableset([overlapping_items[2], overlapping_items[3]]),
            index.get_exactly_matching(Span(20, 30)),
        )
        self.assertEqual(immutableset(), index.get_exactly_matching(Span(6, 26)))
        self.assertEqual(immutableset(), index.get_overlapping(Span(31, 35)))
        self.assertEqual(
            immutableset([overlapping_items[2], overlapping_items[3]]),
            index.get_overlapping(Span(29, 32)),
        )
        self.assertEqual(immutableset(), index.get_contained(Span(25, 30)))
        self.assertEqual(
            immutableset([overlapping_items[2], overlapping_items[3]]),
            index.get_contained(Span(20, 30)),
        )
        self.assertEqual(
            immutableset(
                [
                    overlapping_items[0],
                    overlapping_items[1],
                    overlapping_items[2],
                    overlapping_items[3],
                ]
            ),
            index.get_contained(Span(0, 30)),
        )
        self.assertEqual(immutableset(), index.get_containing(Span(0, 15)))
        self.assertEqual(
            immutableset(
                [overlapping_items[1], overlapping_items[2], overlapping_items[3]]
            ),
            index.get_containing(Span(21, 24)),
        )

    def test_disjoint_index(self) -> None:
        overlapping_items = (
            Foo(Span(0, 10)),
            Foo(Span(5, 25)),
            Foo(Span(20, 30)),
            Bar(Span(20, 30)),
        )
        with self.assertRaisesRegex(
            ValueError, "Some range keys are connected or overlapping"
        ):
            HasSpanIndex.index_disjoint(overlapping_items)

        s1, s2, s3 = (Span(0, 3), Span(5, 25), Span(25, 30))
        s2_within = Span(5, 10)
        s4_contains = Span(5, 30)
        fs1, fs2, fs3 = Foo(s1), Foo(s2), Foo(s3)
        index = HasSpanIndex.index_disjoint((fs1, fs2, fs3))

        self.assertIsNone(index.get_exactly_matching(s2_within))
        self.assertEqual(fs3, index.get_exactly_matching(s3))
        self.assertEqual(immutableset(), index.get_overlapping(Span(35, 40)))
        self.assertEqual(immutableset([fs3]), index.get_overlapping(Span(28, 35)))
        self.assertEqual(immutableset([fs1, fs2]), index.get_overlapping(Span(2, 7)))
        self.assertEqual(immutableset(), index.get_contained(s2_within))
        self.assertEqual(immutableset([fs2, fs3]), index.get_contained(s4_contains))
        self.assertIsNone(index.get_containing(s4_contains))
        self.assertEqual(fs2, index.get_containing(s2_within))
