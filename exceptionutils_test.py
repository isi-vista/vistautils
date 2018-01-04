from unittest import TestCase

from flexnlp.annotators.util import exceptionutils


class ExceptionUtilsTest(TestCase):
    def test_limit_str(self):
        self.assertEqual("['foo', 'bar', 'baz' and 3 more]",
                         exceptionutils.str_list_limited(['foo', 'bar', 'baz', 'moo', 'oink',
                                                          'baa'], limit=3))
        self.assertEqual("['foo', 'bar', 'baz']",
                         exceptionutils.str_list_limited(['foo', 'bar', 'baz'], limit=3))
        self.assertEqual("['foo', 'bar', 'baz' and 1 more]",
                         exceptionutils.str_list_limited(['foo', 'bar', 'baz', 'moo'], limit=3))
