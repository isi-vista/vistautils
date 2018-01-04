from unittest import TestCase

from flexnlp.utils.preconditions import check_arg


class TestPreconditions(TestCase):
    def test_check_arg_interpolation(self):
        with self.assertRaisesRegex(ValueError, "Expected height to exceed 48 but got 41"):
            height = 41
            reference = 48
            check_arg(height > reference, "Expected height to exceed %s but got %s",
                      (reference, height))
