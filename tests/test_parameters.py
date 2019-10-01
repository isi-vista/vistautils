import os
import shutil
import tempfile
from typing import Type

import yaml
from textwrap import dedent
from pathlib import Path
from unittest import TestCase

from attr import attrs, attrib, validators
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
    WRITING_REFERENCE = dedent(
        """\
            hello: world
            moo:
                nested_dict:
                    lalala: fooo
                    list:
                    - 1
                    - 2
                    - 3
                    meep: 2
        """
    )

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

    def test_boolean(self):
        params = YAMLParametersLoader().load_string(
            """
            true_param : true
            false_param : false
            non_boolean_param: 'Fred'
        """
        )

        self.assertTrue(params.boolean("true_param"))
        self.assertFalse(params.boolean("false_param"))
        with self.assertRaises(ParameterError):
            params.boolean("non_boolean_param")

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

    MULTIPLE_INTERPOLATION_REFERENCE = """
            the_ultimate_fruit: "%apple%"
            apple: "%banana%"
            banana: "%pear%"
            pear: raspberry
            """
    MULTIPLE_INTERPOLATION_REFERENCE_NEEDING_CONTEXT = """
            the_ultimate_fruit: "%apple%"
            apple: "%banana%"
            banana: "%pear%"
            pear: "raspberry/%hello%"
            """
    NESTED_INTERPOLATION = """
            key: "%moo.nested_dict.meep%"
            key2: "%moo.nested_dict.lalala%"
            key3: "%moo.nested_dict%"
            """

    def test_interpolation(self):
        context = Parameters.from_mapping(yaml.safe_load(self.WRITING_REFERENCE))
        loader = YAMLParametersLoader()
        self.assertEqual(
            loader._interpolate(
                Parameters.from_mapping(
                    yaml.safe_load(self.MULTIPLE_INTERPOLATION_REFERENCE)
                ),
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
                    yaml.safe_load(self.MULTIPLE_INTERPOLATION_REFERENCE_NEEDING_CONTEXT)
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
                Parameters.from_mapping(yaml.safe_load(self.NESTED_INTERPOLATION)),
                context,
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
            r"These interpolated parameters form at least one graph cycle that must be fixed: "
            r"\('b', 'c'\)",
        ):
            loader._interpolate(
                Parameters.from_mapping(yaml.safe_load('a: "%b%"\nb: "%c%"\nc: "%b%"')),
                context,
            )

    def test_environmental_variable_interpolation(self):
        loader = YAMLParametersLoader()
        os.environ["___TEST_PARAMETERS___"] = "foo"
        os.environ["___TEST_CLASHING_PARAM___"] = "bar"
        loaded_params = loader.load_string(ENV_VAR_INTERPOLATION_INPUT)

        reference_params = Parameters.from_mapping(
            yaml.safe_load(ENV_VAR_INTERPOLATION_REFERENCE)
        )

        self.assertEqual(reference_params, loaded_params)

    def test_double_context_fail(self):
        # cannot specify both deprecated context argument and new included_context argument
        with self.assertRaises(ParameterError):
            YAMLParametersLoader().load(
                f='foo: "foo"',
                context=Parameters.empty(),
                included_context=Parameters.empty(),
            )

    def test_inclusion(self):
        loader = YAMLParametersLoader()
        test_root_dir = Path(tempfile.mkdtemp())
        # we want test inclusion across different directories
        test_nested_dir = test_root_dir / "nested"
        test_nested_dir.mkdir(exist_ok=True, parents=True)
        input_file = test_nested_dir / "input.params"
        input_file.write_text(INCLUSION_INPUT_FIRST_FILE, encoding="utf-8")

        included_file = test_root_dir / "include_one_level_up.params"
        included_file.write_text(INCLUSION_INPUT_PARENT, encoding="utf-8")

        grandparent_file = test_root_dir / "include_same_dir.params"
        grandparent_file.write_text(INCLUSION_INPUT_GRANDPARENT, encoding="utf-8")

        params = loader.load(input_file)
        shutil.rmtree(test_root_dir)

        self.assertEqual(INCLUSION_REFERENCE, dict(params.as_mapping()))

    def test_absents(self):
        empty_params = Parameters.from_mapping({})
        assert empty_params.optional_arbitrary_list("foo") is None
        assert empty_params.optional_boolean("foo") is None
        assert empty_params.optional_creatable_directory("foo") is None
        assert empty_params.optional_creatable_empty_directory("foo") is None
        assert empty_params.optional_creatable_file("foo") is None
        assert empty_params.optional_existing_directory("foo") is None
        assert empty_params.optional_existing_file("foo") is None
        assert empty_params.optional_floating_point("foo") is None
        assert empty_params.optional_integer("foo") is None
        assert empty_params.optional_namespace("foo") is None
        assert empty_params.optional_positive_integer("foo") is None
        assert empty_params.optional_string("foo") is None

    def test_optionals_when_present(self):
        params = Parameters.from_mapping(
            {
                "list": [1, 2, 3, ["a", "b", "c"]],
                "boolean": True,
                "float": 0.5,
                "integer": 42,
                "namespace": {"fred": "meep"},
                "string": "foo",
            }
        )

        assert params.optional_arbitrary_list("list") == [1, 2, 3, ["a", "b", "c"]]
        assert params.optional_boolean("boolean") == True
        assert params.optional_floating_point("float") == 0.5
        assert params.optional_integer("integer") == 42
        assert params.optional_namespace("namespace").as_mapping() == {"fred": "meep"}
        assert params.optional_string("string") == "foo"

    def test_object_from_parameters(self):
        @attrs
        class TestObj:
            val: int = attrib(
                default=None, validator=validators.optional(validators.instance_of(int))
            )

            @staticmethod
            def from_parameters(params: Parameters) -> "TestObj":
                return TestObj(params.integer("my_int"))

        simple_params = Parameters.from_mapping(
            {"test": {"value": "TestObj", "my_int": 5}}
        )

        self.assertEqual(
            TestObj(5),
            simple_params.object_from_parameters("test", TestObj, context=locals()),
        )

        # test when object needs no further parameters for instantiation
        @attrs
        class ArglessTestObj:
            pass

        argless_params = Parameters.from_mapping({"test": "ArglessTestObj"})
        self.assertEqual(
            ArglessTestObj(),
            argless_params.object_from_parameters(
                "test", ArglessTestObj, context=locals()
            ),
        )

        # test default_creator creator
        def default_creator(params: Parameters) -> int:
            return 42

        # test falling back to default creator
        self.assertEqual(
            42,
            Parameters.empty().object_from_parameters(
                "missing_param", expected_type=int, default_creator=default_creator
            ),
        )

        # test no specified or default creator
        with self.assertRaises(ParameterError):
            Parameters.empty().object_from_parameters("missing_param", expected_type=int)

        # test default creator being invalid
        bad_default_creator = "foo"
        with self.assertRaises(ParameterError):
            Parameters.empty().object_from_parameters(
                "missing_param", expected_type=int, default_creator=bad_default_creator
            )


# Used by test_environmental_variable_interpolation.
# Here we test:
# (a) one uninterpolated parameter
# (b) one normally interpolated parameter
# (c) one parameter interpolated with an environmental variable
# (d) one parameter interpolated with a key which is both explicitly specified and and an
#         environmental variable, demonstrating that the explicit parameter "wins"
ENV_VAR_INTERPOLATION_INPUT = """
        key1: "fred"
        regular_interpolation: "moo %key1%"
        env_var_interpolation: "moo %___TEST_PARAMETERS___%"
        ___TEST_CLASHING_PARAM___: "rab"
        interpolation_of_clashing_param: "moo %___TEST_CLASHING_PARAM___%"
        """

ENV_VAR_INTERPOLATION_REFERENCE = """
        key1: "fred"
        regular_interpolation: "moo fred"
        env_var_interpolation: "moo foo"
        ___TEST_CLASHING_PARAM___: "rab"
        interpolation_of_clashing_param: "moo rab"
        """

# used for detecting inclusion
INCLUSION_INPUT_FIRST_FILE = """
       _includes:
            - "../include_one_level_up.params"
       hello: "hello %message%"
"""

INCLUSION_INPUT_PARENT = """
       _includes:
            - "include_same_dir.params"
       message: "world %foo%"
"""

INCLUSION_INPUT_GRANDPARENT = """
foo: "meep"
"""

INCLUSION_REFERENCE = {
    "foo": "meep",
    "message": "world meep",
    "hello": "hello world meep",
}
