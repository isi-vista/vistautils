from unittest import TestCase

from flexnlp.parameters import Parameters, YAMLParametersWriter
from flexnlp.utils.io_utils import CharSink


class TestParameters(TestCase):
    WRITING_REFERENCE = """hello: world
moo:
    nested_dict:
        lalala: fooo
        list:
        - 1
        - 2
        - 3
        meep: 2\n"""

    def test_writing_to_yaml(self):
        params = Parameters.from_mapping(
            {
                'hello': 'world',
                'moo' : {
                    'nested_dict' : {
                        'lalala': 'fooo',
                        'meep': 2,
                        'list': [1,2,3]
                    }
                }
            })
        string_buffer = CharSink.to_string()
        YAMLParametersWriter().write(params, string_buffer)
        self.assertEqual(TestParameters.WRITING_REFERENCE, string_buffer.last_string_written)
