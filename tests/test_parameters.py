import os
import shutil
import tempfile
import yaml
from pathlib import Path
from unittest import TestCase

from immutablecollections import immutabledict
from vistautils.parameters import (
    Parameters,
    YAMLParametersWriter,
    ParameterError,
    YAMLParametersLoader,
)
from vistautils.io_utils import CharSink
from vistautils.range import Range
from vistautils._graph import ParameterInterpolationError


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
                "hello": "world",
                "moo": {"nested_dict": {"lalala": "fooo", "meep": 2, "list": [1, 2, 3]}},
            }
        )
        string_buffer = CharSink.to_string()
        YAMLParametersWriter().write(params, string_buffer)
        self.assertEqual(
            TestParameters.WRITING_REFERENCE, string_buffer.last_string_written
        )

    def test_optional_existing_file(self):
        test_dir = Path(tempfile.mkdtemp()).absolute()
        existing_file_path = test_dir / "existing_file"
        existing_file_path.touch()
        non_existing_file = test_dir / "non_existent_file"
        a_directory = test_dir / "directory"
        a_directory.mkdir(parents=True)

        params = Parameters.from_mapping(
            {
                "file_which_exists": str(existing_file_path.absolute()),
                "file_which_does_not_exist": non_existing_file,
                "a_directory": a_directory,
            }
        )

        # noinspection PyTypeChecker
        self.assertEqual(
            os.path.realpath(existing_file_path),
            os.path.realpath(params.optional_existing_file("file_which_exists")),
        )
        self.assertEqual(None, params.optional_existing_file("missing_param"))
        with self.assertRaises(ParameterError):
            params.optional_existing_file("file_which_does_not_exist")
        with self.assertRaises(ParameterError):
            params.optional_existing_file("a_directory")

        shutil.rmtree(test_dir)

    def test_optional_existing_directory(self):
        test_dir = Path(tempfile.mkdtemp()).absolute()
        existing_dir_path = test_dir / "existing_directory"
        existing_dir_path.mkdir(parents=True, exist_ok=True)
        non_existing_dir_path = test_dir / "non_existent_directory"
        a_file = test_dir / "a_file"
        a_file.touch()
        params = Parameters.from_mapping(
            {
                "directory_which_exists": str(existing_dir_path.absolute()),
                "directory_which_does_not_exist": non_existing_dir_path,
                "a_file": a_file,
            }
        )

        # noinspection PyTypeChecker
        self.assertEqual(
            os.path.realpath(existing_dir_path),
            os.path.realpath(
                params.optional_existing_directory("directory_which_exists")
            ),
        )
        self.assertEqual(None, params.optional_existing_directory("missing_param"))
        with self.assertRaises(ParameterError):
            params.optional_existing_directory("directory_which_does_not_exist")
        with self.assertRaises(ParameterError):
            params.optional_existing_directory("a_file")

        shutil.rmtree(test_dir)

    def test_string(self):
        params = Parameters.from_mapping({"hello": "world"})
        self.assertEqual("world", params.string("hello"))
        self.assertEqual("world", params.string("hello", valid_options=("world", "Mars")))

        with self.assertRaisesRegex(
            ParameterError,
            "Parameter foo not found. In in root context available parameters "
            "are \\['hello'\\], available namespaces are \\[\\]",
        ):
            params.string("foo")

        with self.assertRaisesRegex(
            ParameterError,
            "The value world for the parameter hello is not one of the "
            "valid options \\('Earth', 'Mars'\\)",
        ):
            params.string("hello", valid_options=("Earth", "Mars"))

    def test_float(self):
        params = Parameters.from_mapping({"test_float": 5.5})
        self.assertEqual(5.5, params.floating_point("test_float"))
        self.assertEqual(
            5.5, params.floating_point("test_float", valid_range=Range.open(5, 6))
        )

        with self.assertRaisesRegex(
            ParameterError,
            "For parameter test_float, expected a float in the range \\(0.0..1.0\\) but got 5.5",
        ):
            params.floating_point("test_float", valid_range=Range.open(0.0, 1.0))

    MULTIPLE_INTERPOLATION_REFERENCE = """the_ultimate_fruit: \"%apple%\"
apple: \"%banana%\"
banana: \"%pear%\"
pear: raspberry
"""
    MULTIPLE_INTERPOLATION_REFERENCE_NEEDING_CONTEXT = """the_ultimate_fruit: \"%apple%\"
apple: \"%banana%\"
banana: \"%pear%\"
pear: \"raspberry/%hello%\"
"""
    NESTED_INTERPOLATION = """key: \"%moo.nested_dict.meep%\"
key2: \"%moo.nested_dict.lalala%\"
key3: \"%moo.nested_dict%\"
"""

    def test_interpolation(self):
        context = Parameters.from_mapping(yaml.load(self.WRITING_REFERENCE))
        loader = YAMLParametersLoader()
        self.assertEqual(
            loader._interpolate(
                Parameters.from_mapping(yaml.load(self.MULTIPLE_INTERPOLATION_REFERENCE)),
                context,
            )._data,
            immutabledict(
                [
                    ("pear", "raspberry"),
                    ("banana", "raspberry"),
                    ("apple", "raspberry"),
                    ("the_ultimate_fruit", "raspberry"),
                ]
            ),
        )
        self.assertEqual(
            loader._interpolate(
                Parameters.from_mapping(
                    yaml.load(self.MULTIPLE_INTERPOLATION_REFERENCE_NEEDING_CONTEXT)
                ),
                context,
            )._data,
            immutabledict(
                [
                    ("pear", "raspberry/world"),
                    ("banana", "raspberry/world"),
                    ("apple", "raspberry/world"),
                    ("the_ultimate_fruit", "raspberry/world"),
                    # the actual pair ("hello", "world") should not be present
                ]
            ),
        )
        self.assertEqual(
            loader._interpolate(
                Parameters.from_mapping(yaml.load(self.NESTED_INTERPOLATION)), context
            )._data,
            immutabledict(
                [
                    ("key", 2),
                    ("key2", "fooo"),
                    (
                        "key3",
                        Parameters.from_mapping(
                            {"lalala": "fooo", "meep": 2, "list": [1, 2, 3]}
                        ),
                    ),
                ]
            ),
        )

        with self.assertRaisesRegex(
            ParameterInterpolationError,
            r"These interpolated parameters form at least one graph cycle that must be fixed: \('b', 'c'\)",
        ):
            loader._interpolate(
                Parameters.from_mapping(yaml.load('a: "%b%"\nb: "%c%"\nc: "%b%"')),
                context,
            )
