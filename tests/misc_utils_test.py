from unittest import TestCase

from flexnlp.utils.misc_utils import str_list_limited, flatten_once_to_list


class ExceptionUtilsTest(TestCase):
    def test_limit_str(self):
        self.assertEqual("['foo', 'bar', 'baz' and 3 more]",
                         str_list_limited(
                             ['foo', 'bar', 'baz', 'moo', 'oink',
                              'baa'], limit=3))
        self.assertEqual("['foo', 'bar', 'baz']",
                         str_list_limited(['foo', 'bar', 'baz'], limit=3))
        self.assertEqual("['foo', 'bar', 'baz' and 1 more]",
                         str_list_limited(['foo', 'bar', 'baz', 'moo'],
                                                                   limit=3))

    def test_flatten_once(self):
        # test that flatten_once removes one level of nesting but not more than one
        nested = [[1, [2, 3]], [[4, 5], [6, 7]]]
        reference = [1, [2, 3], [4, 5], [6, 7]]
        self.assertEqual(reference, flatten_once_to_list(nested))
