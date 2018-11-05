from unittest import TestCase

from vistautils.preconditions import check_arg, check_not_none


class TestPreconditions(TestCase):
    def test_check_arg_interpolation(self):
        with self.assertRaisesRegex(
            ValueError, "Expected height to exceed 48 but got 41"
        ):
            height = 41
            reference = 48
            check_arg(
                height > reference,
                "Expected height to exceed %s but got %s",
                (reference, height),
            )

    def test_not_none(self):
        with self.assertRaises(ValueError):
            check_not_none(None)
        with self.assertRaisesRegex(ValueError, "foo"):
            check_not_none(None, "foo")
