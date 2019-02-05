from unittest import TestCase

from attr import attrs, attrib
from immutablecollections import ImmutableSet

from vistautils.span import Span, HasSpanIndex


@attrs(hash=True)
class Foo:
    span = attrib()


class TestSpan(TestCase):
    def test_index(self):
        items = Foo(Span(0, 10)), Foo(Span(5, 25)), Foo(Span(20, 30))
        index = HasSpanIndex.index(items)
        self.assertEqual(ImmutableSet.of([items[0]]), index.exactly_matching(Span(0, 10)))
        self.assertEqual(ImmutableSet.of([items[1]]), index.exactly_matching(Span(5, 25)))
        self.assertEqual(
            ImmutableSet.of([items[2]]), index.exactly_matching(Span(20, 30))
        )
        self.assertEqual(ImmutableSet.empty(), index.exactly_matching(Span(6, 26)))
