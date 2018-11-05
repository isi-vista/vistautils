from typing import TypeVar, Generic, Container
from unittest import TestCase

from attr import attrs

T = TypeVar("T")


# this test is to track https://github.com/python-attrs/attrs/issues/313
class TestGenericBug(TestCase):
    def test_no_slots_ok(self):
        @attrs
        class Foo(Generic[T]):
            pass

    def test_no_attrs(self):
        class Meep(Generic[T]):
            __slots__ = ()

    def test_frozen_with_generic_parent_ok(self):
        @attrs(frozen=True)
        class Foo2(Generic[T], Container[T]):
            def __contains__(self, x: object) -> bool:
                return False

    def test_slots_with_no_parent(self):
        with self.assertRaisesRegex(TypeError, "Cannot inherit from plain Generic"):

            @attrs(slots=True)
            class Foo4(Generic[T]):
                pass
