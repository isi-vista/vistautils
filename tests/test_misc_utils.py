from typing import Any
from unittest import TestCase

from vistautils.misc_utils import eval_in_context_of_modules


class TestMiscUtils(TestCase):
    def test_eval_in_context_of_modules(self):
        evaled = eval_in_context_of_modules(
            "datetime.datetime.today()",
            locals(),
            context_modules=["datetime"],
            expected_type=object,
        )
        import datetime

        self.assertTrue(isinstance(evaled, datetime.datetime))

    def test_eval_in_context_of_modules_mismatched_type(self):
        with self.assertRaises(TypeError):
            eval_in_context_of_modules(
                "datetime.datetime.today()",
                locals(),
                context_modules=["datetime"],
                expected_type=str,
            )
