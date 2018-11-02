from typing import Iterator, Iterable, TypeVar
from unittest import TestCase

from vistautils.iter_utils import windowed, drop, only

# convenience methods for testing tools on both iterators and iterables
_T = TypeVar('_T')


def _as_iterable(it: Iterable[_T]) -> Iterable[_T]:
    return it


def _as_iterator(it: Iterable[_T]) -> Iterator[_T]:
    return iter(it)


_iterator_or_iterable = (_as_iterable, _as_iterator)


class TestIterUtils(TestCase):
    def test_drop(self):
        iterable = [1, 2, 3, 4]

        for to_it in _iterator_or_iterable:
            # test negative drop not allowed
            with self.assertRaises(ValueError):
                drop(to_it(iterable), -1)

            # we do all tests with both an iterable and an iterator

            # test dropping zero elements is allowed
            self.assertEqual(iterable, list(drop(to_it(iterable), 0)))

            # test dropping positive number of elements
            self.assertEqual([3, 4], list(drop(to_it(iterable), 2)))
            # check original iterable is unchanged
            self.assertEqual([1, 2, 3, 4], iterable)

            # test dropping more than the length of the iterable returns an empty list
            # (rather than throwing an exception)
            self.assertEqual([], list(drop(to_it(iterable), 100)))

        # test return types
        self.assertIsInstance(drop(iterable, 1), Iterable)
        self.assertIsInstance(drop(iter(iterable), 1), Iterator)

    def test_only(self):
        # we do all tests with both an iterable and an iterator

        for to_it in _iterator_or_iterable:
            # check for exception on empty input
            empty_set = set()
            with self.assertRaises(ValueError):
                only(to_it(empty_set))

            # check for exception on multiple inputs
            two_elements = {3, 4}
            with self.assertRaises(ValueError):
                only(to_it(two_elements))

            # check for non-exception case
            one_element = {3}
            self.assertEqual(3, only(to_it(one_element)))

    def test_windowed_bad_window_size(self):
        # need positive window size
        with self.assertRaises(ValueError):
            windowed(range(5), 0)

    def test_single_element_window(self):
        data = list(range(3))

        for to_it in _iterator_or_iterable:
            self.assertEqual([], list(windowed(to_it([]), 1)))
            self.assertEqual([(0,), (1,), (2,)], list(windowed(to_it(data), 1)))
            self.assertEqual([(0,), (1,), (2,)], list(windowed(to_it(data), 1,
                                                               partial_windows=True)))

    def test_two_element_window(self):
        data = list(range(3))

        for to_it in _iterator_or_iterable:
            self.assertEqual([(0, 1), (1, 2)], list(windowed(to_it(data), 2)))
            self.assertEqual([(0, 1), (1, 2), (2,)],
                             list(windowed(to_it(data), 2, partial_windows=True)))

    def test_window_size_equals_sequence_size(self):
        data = list(range(3))

        for to_it in _iterator_or_iterable:
            self.assertEqual([(0, 1, 2)], list(windowed(to_it(data), 3)))
            self.assertEqual([(0, 1, 2), (1, 2), (2, )],
                             list(windowed(to_it(data), 3, partial_windows=True)))

    def test_window_size_exceeds_sequence_size(self):
        data = list(range(3))

        for to_it in _iterator_or_iterable:
            # window size exceeds sequence length
            self.assertEqual([], list(windowed(to_it(data), 4)))
            self.assertEqual([(0, 1, 2), (1, 2), (2, )],
                             list(windowed(to_it(data), 4, partial_windows=True)))
