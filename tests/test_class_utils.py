from unittest import TestCase

from vistautils.range import ImmutableRangeSet

from vistautils.class_utils import fully_qualified_name_of_type, fully_qualified_name


class TestClassUtils(TestCase):
    def test_fully_qualified_name(self) -> None:
        # test built-in types
        self.assertEqual("str", fully_qualified_name_of_type("foo"))
        self.assertEqual("int", fully_qualified_name_of_type(4))
        irsb = ImmutableRangeSet.builder()
        # test nested classes
        # these need to be changed if we alter the implementation of ImmutableRangeSet
        self.assertEqual(
            "vistautils.range._ImmutableSortedDictRangeSet.Builder",
            fully_qualified_name_of_type(irsb),
        )
        # test regular classes
        self.assertEqual(
            "vistautils.range._ImmutableSortedDictRangeSet",
            fully_qualified_name_of_type(irsb.build()),
        )

        # test mypy on class version
        fully_qualified_name(ImmutableRangeSet)
