from unittest import TestCase

from vistautils.iter_utils import windowed


class TestIterUtils(TestCase):
    def test_windowed_bad_window_size(self):
        # need positive window size
        with self.assertRaises(ValueError):
            windowed(range(5), 0)

    def test_single_element_window(self):
        self.assertEqual([], list(windowed([], 1)))
        self.assertEqual([(0,), (1,), (2,)], list(windowed(range(3), 1)))
        self.assertEqual([(0,), (1,), (2,)], list(windowed(range(3), 1,
                                                           partial_windows=True)))

    def test_two_element_window(self):
        self.assertEqual([(0, 1), (1, 2)], list(windowed(range(3), 2)))
        self.assertEqual([(0, 1), (1, 2), (2,)],
                         list(windowed(range(3), 2, partial_windows=True)))

    def test_window_size_equals_sequence_size(self):
        self.assertEqual([(0, 1, 2)], list(windowed(range(3), 3)))
        self.assertEqual([(0, 1, 2), (1, 2), (2, )],
                         list(windowed(range(3), 3, partial_windows=True)))

    def test_window_size_exceeds_sequence_size(self):
        # window size exceeds sequence length
        self.assertEqual([], list(windowed(range(3), 4)))
        self.assertEqual([(0, 1, 2), (1, 2), (2, )],
                         list(windowed(range(3), 4, partial_windows=True)))
