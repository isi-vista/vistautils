from unittest import TestCase

import flexnlp.utils.misc_flexnlp_utils
import flexnlp.utils.misc_utils
from flexnlp.annotators.util import exceptionutils


class ExceptionUtilsTest(TestCase):
    def test_limit_str(self):
        self.assertEqual("['foo', 'bar', 'baz' and 3 more]",
                         flexnlp.utils.misc_utils.str_list_limited(['foo', 'bar', 'baz', 'moo', 'oink',
                                                          'baa'], limit=3))
        self.assertEqual("['foo', 'bar', 'baz']",
                         flexnlp.utils.misc_utils.str_list_limited(['foo', 'bar', 'baz'], limit=3))
        self.assertEqual("['foo', 'bar', 'baz' and 1 more]",
                         flexnlp.utils.misc_utils.str_list_limited(['foo', 'bar', 'baz', 'moo'], limit=3))
