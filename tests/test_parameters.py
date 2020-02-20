import os
import pickle
import shutil
import tempfile
from pathlib import Path
from textwrap import dedent
from unittest import TestCase

from attr import attrib, attrs, validators

from immutablecollections import immutabledict

from vistautils._graph import ParameterInterpolationError
from vistautils.io_utils import CharSink
from vistautils.parameters import (
    ParameterError,
    Parameters,
    YAMLParametersLoader,
    YAMLParametersWriter,
)
from vistautils.range import Range

import pytest
import yaml


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

        self.assertTrue(params.boolean("not-appearing", default=True))
        # test with a False-y default
        self.assertFalse(params.boolean("not-appearing", default=False))

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

    def test_optional_creatable_directory(self):
        test_dir = Path(tempfile.mkdtemp()).absolute()
        existing_dir_path = test_dir / "existing_directory"
        existing_dir_path.mkdir(parents=True, exist_ok=True)
        non_existing_dir_path = test_dir / "non_existent_directory"
        a_file = existing_dir_path / "a_file"
        a_file.touch()
        params = Parameters.from_mapping(
            {
                "directory_which_exists": str(existing_dir_path.absolute()),
                "directory_which_does_not_exist": str(non_existing_dir_path.absolute()),
                "a_file": a_file,
            }
        )

        self.assertEqual(
            os.path.realpath(existing_dir_path),
            os.path.realpath(
                params.optional_creatable_directory("directory_which_exists")
            ),
        )
        self.assertEqual(None, params.optional_creatable_directory("missing_param"))
        self.assertEqual(
            os.path.realpath(non_existing_dir_path),
            os.path.realpath(
                params.optional_creatable_directory("directory_which_does_not_exist")
            ),
        )
        with self.assertRaises(ParameterError):
            params.optional_existing_directory("a_file")

    def test_optional_creatable_empty_directory(self):
        test_dir = Path(tempfile.mkdtemp()).absolute()
        existing_dir_path = test_dir / "existing_directory"
        existing_dir_path.mkdir(parents=True, exist_ok=True)
        non_existing_dir_path = test_dir / "non_existent_directory"
        a_file = existing_dir_path / "a_file"
        a_file.touch()
        params = Parameters.from_mapping(
            {
                "directory_which_exists": str(existing_dir_path.absolute()),
                "directory_which_does_not_exist": str(non_existing_dir_path.absolute()),
                "a_file": a_file,
            }
        )

        self.assertEqual(None, params.optional_creatable_empty_directory("missing_param"))
        self.assertEqual(
            os.path.realpath(non_existing_dir_path),
            os.path.realpath(
                params.optional_creatable_empty_directory(
                    "directory_which_does_not_exist"
                )
            ),
        )
        with self.assertRaises(ParameterError):
            params.optional_creatable_empty_directory("a_file")
        with self.assertRaises(ParameterError):
            params.optional_creatable_empty_directory("directory_which_exists")
        self.assertEqual(
            os.path.realpath(existing_dir_path),
            os.path.realpath(
                params.optional_creatable_empty_directory(
                    "directory_which_exists", delete=True
                )
            ),
        )

    def test_optional_creatable_file(self):
        test_dir = Path(tempfile.mkdtemp()).absolute()
        existing_dir_path = test_dir / "existing_directory"
        existing_dir_path.mkdir(parents=True, exist_ok=True)
        non_existing_dir_path = test_dir / "non_existent_directory"
        a_file = existing_dir_path / "a_file"
        a_file.touch()
        non_existing_file = test_dir / "b_file"
        params = Parameters.from_mapping(
            {
                "directory_which_exists": str(existing_dir_path.absolute()),
                "directory_which_does_not_exist": str(non_existing_dir_path.absolute()),
                "a_file": str(a_file.absolute()),
                "non_existing_file": str(non_existing_file.absolute()),
            }
        )

        self.assertEqual(None, params.optional_creatable_file("missing_param"))
        self.assertEqual(
            os.path.realpath(non_existing_file),
            os.path.realpath(params.optional_creatable_file("non_existing_file")),
        )

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

    def test_integer(self):
        params = Parameters.from_mapping({"test_int": 5})
        self.assertEqual(5, params.integer("test_int"))
        self.assertEqual(2, params.integer("not_appearing", default=2))
        with self.assertRaisesRegex(
            ParameterError, "Invalid value for integer parameter"
        ):
            params.integer("test_int", valid_range=Range.closed(1, 3))
        with self.assertRaisesRegex(
            ParameterError, "Invalid value for integer parameter"
        ):
            params.integer("not_appearing", default=2, valid_range=Range.closed(10, 20))

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

    # pylint: disable=protected-access
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
            ).as_nested_dicts(),
            {
                "key": 2,
                "key2": "fooo",
                "key3": {"lalala": "fooo", "meep": 2, "list": [1, 2, 3]},
            },
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

        self.assertEqual(INCLUSION_REFERENCE, dict(params.as_nested_dicts()))

    def test_arbitrary_list(self):
        params = Parameters.from_mapping({"hello": [1, 2, 3]})
        self.assertEqual([1, 2, 3], params.arbitrary_list("hello"))
        self.assertEqual(
            ["foo", "bar"], params.arbitrary_list("world", default=["foo", "bar"])
        )

    def test_positive_integer(self):
        params = Parameters.from_mapping({"hello": 2, "world": -2})
        self.assertEqual(2, params.positive_integer("hello"))
        with self.assertRaises(ParameterError):
            params.positive_integer("world")

    def test_absents(self):
        empty_params = Parameters.empty()
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
                "negative_int": -5,
                "namespace": {"fred": "meep"},
                "string": "foo",
            }
        )

        assert params.optional_arbitrary_list("list") == [1, 2, 3, ["a", "b", "c"]]
        assert params.optional_boolean("boolean")
        assert params.optional_floating_point("float") == 0.5
        assert params.optional_integer("integer") == 42
        assert params.optional_positive_integer("integer") == 42
        with self.assertRaises(ParameterError):
            params.optional_positive_integer("negative_int")
        assert params.optional_namespace("namespace").as_nested_dicts() == {
            "fred": "meep"
        }
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
        # pylint: disable=unused-argument
        def default_creator(params: Parameters) -> int:
            return 42

        # test falling back to default creator
        self.assertEqual(
            42,
            Parameters.empty().object_from_parameters(
                "missing_param", expected_type=int, default_creator=default_creator
            ),
        )

        # test missing parameter and no default creator
        with self.assertRaises(ParameterError):
            self.assertEqual(
                "fred",
                Parameters.empty().object_from_parameters(
                    "missing_param", default_creator=None, expected_type=str
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

    def test_optional_defaults(self):
        empty_params = Parameters.empty()
        default_list = [False]
        assert (
            empty_params.optional_arbitrary_list(  # pylint: disable=unexpected-keyword-arg
                "foo", default=default_list
            )
            == default_list
        )
        assert empty_params.optional_boolean(  # pylint: disable=unexpected-keyword-arg
            "foo", default=True
        )
        assert (  # pylint: disable=unexpected-keyword-arg
            empty_params.optional_floating_point("foo", default=-1.5) == -1.5
        )
        assert (  # pylint: disable=unexpected-keyword-arg
            empty_params.optional_integer("foo", default=-5) == -5
        )
        assert (  # pylint: disable=unexpected-keyword-arg
            empty_params.optional_positive_integer("foo", default=5) == 5
        )
        assert (  # pylint: disable=unexpected-keyword-arg
            empty_params.optional_string("foo", default="test") == "test"
        )
        with self.assertRaises(ParameterError):
            empty_params.optional_floating_point(  # pylint: disable=unexpected-keyword-arg
                "foo", default=-1.5, valid_range=Range.closed(0.0, 10.0)
            )

    def test_namespace_prefix(self):
        assert Parameters.from_mapping({"hello": {"world": {"foo": "bar"}}}).namespace(
            "hello"
        ).namespace("world").namespace_prefix == ("hello", "world")
        assert Parameters.empty(namespace_prefix=("foo",)).namespace_prefix == ("foo",)
        # test it works even for empty parameters
        assert Parameters.empty().namespace_or_empty("foo").namespace_or_empty(
            "bar"
        ).namespace_prefix == ("foo", "bar")

    def test_pickled_object_from_file(self):
        temp_dir = Path(tempfile.mkdtemp()).absolute()
        pickled_obj_file = temp_dir / "pickle"
        obj = {"foo": "bar", "thing": "amabob"}
        with pickled_obj_file.open("wb") as bf:
            pickle.dump(obj, bf)

        params = Parameters.from_mapping(
            {"pickled_obj_file": str(pickled_obj_file.absolute())}
        )

        # noinspection PyTypeChecker
        self.assertEqual(obj, params.pickled_object_from_file("pickled_obj_file"))


def test_interpolating_nested_parameters(tmp_path):
    included_params = {
        # - and _ to test they work when finding params to interpolate.
        "hello": {"world": {"foo-foo_foo": "meep"}},
        "same_file": "moo %hello.world.foo-foo_foo% moo",
        "nested": {"interpolate_me_nested": "%hello.world.foo-foo_foo% nested"},
    }
    included_params_path = tmp_path / "included.params"
    with open(included_params_path, "w") as included_params_out:
        yaml.dump(included_params, included_params_out)

    reloaded_included_params = YAMLParametersLoader().load(included_params_path)

    # check nested interpolation works within the same file
    assert reloaded_included_params.string("same_file") == "moo meep moo"
    # check interpolation works when the parameter being interpolate is not top-level
    assert (
        reloaded_included_params.string("nested.interpolate_me_nested") == "meep nested"
    )

    including_params = {
        "_includes": ["included.params"],
        "interpolate_me": "lala %hello.world.foo-foo_foo% lala",
    }

    including_params_path = tmp_path / "including.params"
    with open(including_params_path, "w") as including_params_out:
        yaml.dump(including_params, including_params_out)

    loaded_params = YAMLParametersLoader().load(including_params_path)

    # check nested interpolation works across files
    assert loaded_params.string("interpolate_me") == "lala meep lala"


def test_exception_when_interpolating_unknown_param(tmp_path) -> None:
    parameters = {"hello": "world", "interpolate_me": "%unknown_param%"}
    params_file = tmp_path / "tmp.params"
    with open(params_file, "w") as out:
        yaml.dump(parameters, out)
    with pytest.raises(Exception):
        YAMLParametersLoader().load(params_file)


def test_namespaced_items():
    params = Parameters.from_mapping(
        {"hello": "world", "foo": {"bar": "meep", "inner": {"not_a_string": 42}}}
    )
    assert set(params.namespaced_items()) == {
        ("hello", "world"),
        ("foo.bar", "meep"),
        ("foo.inner.not_a_string", 42),
    }


def test_relative_path_list(tmp_path):
    file_list = tmp_path / "list.txt"
    CharSink.to_file(file_list).write("\n".join(["fred/bob.txt", "foo.txt"]))
    params = Parameters.from_mapping({"file_list": str(file_list)})
    assert list(
        params.path_list_from_file("file_list", resolve_relative_to=Path("/hello/world"))
    ) == [Path("/hello/world/fred/bob.txt"), Path("/hello/world/foo.txt")]


def test_relative_path_map(tmp_path):
    file_map = tmp_path / "map.txt"
    CharSink.to_file(file_map).write("\n".join(["one\tfred/bob.txt", "two\tfoo.txt"]))
    params = Parameters.from_mapping({"file_map": str(file_map)})
    assert dict(
        params.path_map_from_file("file_map", resolve_relative_to=Path("/hello/world"))
    ) == {"one": Path("/hello/world/fred/bob.txt"), "two": Path("/hello/world/foo.txt")}


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
