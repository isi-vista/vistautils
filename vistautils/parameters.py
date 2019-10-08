import inspect
import logging
import os
import re
import shutil
from enum import Enum
from pathlib import Path
from typing import (
    Any,
    Callable,
    Iterable,
    List,
    Mapping,
    Optional,
    Pattern,
    Sequence,
    Type,
    TypeVar,
    Union,
)

from attr import attrib, attrs

from immutablecollections import ImmutableDict, immutabledict

from vistautils._graph import Digraph
from vistautils.io_utils import CharSink, is_empty_directory
from vistautils.misc_utils import eval_in_context_of_modules
from vistautils.preconditions import check_arg, check_isinstance
from vistautils.range import Range

import yaml

_logger = logging.getLogger(__name__)  # pylint:disable=invalid-name


class ParameterError(Exception):
    pass


ParamType = TypeVar("ParamType")  # pylint:disable=invalid-name
_U = TypeVar("_U")  # pylint:disable=invalid-name


class _Marker(Enum):
    """
    Singleton type, as described in:
    https://python.org/dev/peps/pep-0484/#support-for-singleton-types-in-unions
    """

    MARKER = object()


_marker = _Marker.MARKER  # pylint:disable=invalid-name


@attrs(frozen=True, slots=True)
class Parameters:
    """
    Configuration parameters for a program.

    A `Parameters` object can be thought of as a hierarchical dictionary mapping parameter name
    strings to arbitrary values.  Hierarchical levels within a parameter name can be indicated
    via `.`; the levels are called namespaces. So `hello.world.foo` means "look up the 'foo'
    parameter within the namespace 'world' which is itself within the namespace 'hello'.

    The advantage of using this class over simple dictionary of dictionaries is that it provides
    type-safe accessors for parameters which can do validation and ensure certain conditions hold.
    This tends to push the discovery of errors earlier in program execution (or even before program
    execution).

    `Parameters` objects can be represented in multiple formats. The only loader currently
    implemented is `YAMLParametersLoader`.

    You can check if a lookup of a parameter would be successful using the `in` operator.
    """

    _data: ImmutableDict[str, Any] = attrib(
        default=immutabledict(), converter=immutabledict
    )

    def __attrs_post_init__(self) -> None:
        for key in self._data:
            check_arg(
                "." not in key, "Parameter keys cannot contain namespace separator '.'"
            )

    @staticmethod
    def empty() -> "Parameters":
        """
        A `Parameters` with no parameter mappings.
        """
        return Parameters.from_mapping(ImmutableDict.empty())

    @staticmethod
    def from_mapping(mapping: Mapping) -> "Parameters":
        """
        Convert a dictionary of dictionaries into a `Parameter`s

        The top-level dictionary becomes the top-level namespace.  Each mapping-valued parameter
        becomes a namespace.
        """
        check_isinstance(mapping, Mapping)
        ret: ImmutableDict.Builder[str, Any] = ImmutableDict.builder()
        for (key, val) in mapping.items():
            if isinstance(val, Mapping):
                ret.put(key, Parameters.from_mapping(val))
            else:
                # this case will also be triggered if the value is already a parameters object
                ret.put(key, val)
        return Parameters(ret.build())

    def as_mapping(self) -> Mapping[str, Any]:
        """
        Get these parameter values as a ``Mapping``.
        """
        return self._data

    def creatable_directory(self, param: str) -> Path:
        """
        Get a directory which can be written to.

        Interprets the string-valued parameter `param` as a directory path and creates it if
        it does not exist.  This allows writing files within this directory without needing to
        remember to create it or its parent directories.

        Throws a `ParameterError` if `param` is not a known parameter.
        """
        ret = Path.resolve(Path(self.string(param)))
        ret.mkdir(parents=True, exist_ok=True)
        return ret

    def optional_creatable_directory(self, param: str) -> Optional[Path]:
        """
        Get a directory which can be written to, if possible.

        If *param* is not present, returns *None*.

        Interprets the string-valued parameter `param` as a directory path and creates it if
        it does not exist.  This allows writing files within this directory without needing to
        remember to create it or its parent directories.

        Throws a `ParameterError` if `param` is not a known parameter.
        """
        if param in self:
            return self.creatable_directory(param)
        else:
            return None

    def creatable_empty_directory(self, param: str, *, delete=False) -> Path:
        """
        Get an empty directory which can be written to.

        Interprets the string-valued parameter `param` as a directory path and creates it if
        it does not exist.  If the directory already exists and is non-empty, behavior depends
        on the value of the `delete` argument.  If False (the default), an exception will be
        raised.  If True, the directory and its contents will be deleted.

        This allows writing files within this directory without needing to remember to create it
        or its parent directories.

        Throws a `ParameterError` if `param` is not a known parameter.
        """
        ret = Path.resolve(Path(self.string(param)))
        if ret.is_dir():
            if not is_empty_directory(ret):
                if delete:
                    shutil.rmtree(str(ret))
                    ret.mkdir(parents=True, exist_ok=True)
                else:
                    raise ParameterError(
                        "Expected an empty directory for parameters {!s},"
                        "but got non-empty path {!s}".format(param, ret)
                    )
            return ret
        elif ret.exists():
            raise ParameterError(
                "Expected an empty directory for parameters {!s},"
                "but got non-directory {!s}".format(param, ret)
            )
        else:
            return self.creatable_directory(param)

    def optional_creatable_empty_directory(
        self, param: str, *, delete: bool = False
    ) -> Optional[Path]:
        """
        Get an empty directory which can be written to, if possible.

        If *param* is absent, returns *None*.

        Interprets the string-valued parameter `param` as a directory path and creates it if
        it does not exist.  If the directory already exists and is non-empty, behavior depends
        on the value of the `delete` argument.  If False (the default), an exception will be
        raised.  If True, the directory and its contents will be deleted.

        This allows writing files within this directory without needing to remember to create it
        or its parent directories.

        Throws a `ParameterError` if `param` is not a known parameter.
        """
        if param in self:
            return self.creatable_empty_directory(param, delete=delete)
        else:
            return None

    def creatable_file(self, param: str) -> Path:
        """
        Get a file path which can be written to.

        Interprets the string-valued parameter `param` as a file path and creates its parent
        directory if it does not exist.  This allows writing to this file without needing to
        remember to create its parent directories.

        Throws a `ParameterError` if `param` is not a known parameter.
        """
        ret = Path.resolve(Path(self.string(param)))
        ret.parent.mkdir(parents=True, exist_ok=True)
        return ret

    def optional_creatable_file(self, param: str) -> Optional[Path]:
        """
        Get a file path which can be written to, if specified.

        Just like `creatable_file` but returns `None` if the parameter is absent.
        """
        if param in self:
            return self.creatable_file(param)
        else:
            return None

    def existing_file(self, param: str) -> Path:
        """
        Gets a path for an existing file.

        Interprets the string-valued parameter `param` as a file path. Throws a `ParameterError`
        if the path does not exist or is not a file.

        Throws a `ParameterError` if `param` is not a known parameter.
        """
        ret = Path.resolve(Path(self.string(param)))
        if ret.exists():
            if ret.is_file():
                return ret
            else:
                raise ParameterError(
                    "For parameter "
                    + param
                    + ", expected an existing file but got existing non-file "
                    + str(ret)
                )
        else:
            raise ParameterError(
                "For parameter "
                + param
                + ", expected an existing file but got non-existent "
                + str(ret)
            )

    def optional_existing_file(self, param: str) -> Optional[Path]:
        """
        Gets a path for an existing file, if specified.

        Interprets the string-valued parameter `param` as a file path. Returns `None`
        if no parameter by that name is present.  Throws a `ParameterError`
        if the path does not exist.
        """
        if param in self:
            return self.existing_file(param)
        else:
            return None

    def existing_directory(self, param: str) -> Path:
        """
        Gets a path for an existing directory.

        Interprets the string-valued parameter `param` as a directory path. Throws a
        `ParameterError` if the path does not exist or is not a directory.

        Throws a `ParameterError` if `param` is not a known parameter.
        """
        ret = Path.resolve(Path(self.string(param)))
        if ret.exists():
            if ret.is_dir():
                return ret
            else:
                raise ParameterError(
                    "For parameter "
                    + param
                    + ", expected an existing directory but got existing "
                    "non-directory " + str(ret)
                )
        else:
            raise ParameterError(
                "For parameter "
                + param
                + ", expected an existing directory but got non-existent "
                + str(ret)
            )

    def optional_existing_directory(self, param: str) -> Optional[Path]:
        """
        Gets a path for an existing directory, if specified.

        Interprets the string-valued parameter `param` as a directory path.
        If the parameter is not present, returns `None`.  Throws a
        `ParameterError` if the path does not exist.
        """
        if param in self:
            return self.existing_directory(param)
        else:
            return None

    def string(
        self, param_name: str, valid_options: Optional[Iterable[str]] = None
    ) -> str:
        """
        Gets a string-valued parameter.

        Throws a `ParameterError` if `param` is not a known parameter.
        """
        ret = self.get(param_name, str)
        if valid_options is not None and ret not in valid_options:
            raise ParameterError(
                f"The value {ret} for the parameter {param_name} is not one of the valid options "
                f"{tuple(valid_options)}"
            )
        return ret

    def optional_string(
        self,
        param_name: str,
        valid_options: Optional[Iterable[str]] = None,
        default: _U = None,
    ) -> Union[Optional[str], _U]:
        """
        Gets a string-valued parameter, if possible.
        If a default is provided, return the default
        else returns *None* if the parameter is absent.

        Throws a `ParameterError` if `param` is not a known parameter.
        """
        if param_name in self:
            return self.string(param_name, valid_options)
        else:
            return default

    def __contains__(self, param_name: str) -> bool:
        return self._private_get(param_name, optional=True) is not None

    def namespace(self, name: str) -> "Parameters":
        """
        Get the namespace with the given name.
        """
        return self.get(name, Parameters)

    def integer(self, name: str) -> int:
        """
        Gets an integer parameter.
        """
        return self.get(name, int)

    def optional_integer(self, name: str, default: _U = None) -> Union[Optional[int], _U]:
        """
        Gets an integer parameter, if possible.

        Returns *None* if the parameter is not present.
        """
        if name in self:
            return self.integer(name)
        else:
            return default

    def positive_integer(self, name: str) -> int:
        """
        Gets an parameter with a positive integer value.

        Throws an exception if the parameter is present but is not a positive integer.
        """
        ret = self.integer(name)
        if ret > 0:
            return ret
        else:
            raise ParameterError(
                "For parameter {!s}, expected a positive integer but got {!s}".format(
                    name, ret
                )
            )

    def optional_positive_integer(
        self, name: str, default: _U = None
    ) -> Union[Optional[int], _U]:
        """
        Gets a positive integer parameter, if possible.

        Returns *None* if the parameter is not present.
        Throws an exception if the parameter is present but is not a positive integer.
        """
        if name in self:
            return self.positive_integer(name)
        if isinstance(default, int) and default > 0:
            return default
        else:
            raise ParameterError(f"Default value: {default} is not a positive value")

    def floating_point(
        self, name: str, valid_range: Optional[Range[float]] = None
    ) -> float:
        """
        Gets a float parameter.

        Throws a `ParameterError` if `param` is not within the given range.

        This method isn't called `float` to avoid a clash with the Python type.
        """
        ret = self.get(name, float)
        if valid_range is not None and ret not in valid_range:
            raise ParameterError(
                "For parameter {!s}, expected a float in the range {!s} but got {!s}".format(
                    name, valid_range, ret
                )
            )
        return ret

    def optional_floating_point(
        self, name: str, valid_range: Optional[Range[float]] = None, default: _U = None
    ) -> Union[Optional[float], _U]:
        """
        Gets a float parameter if present.

        Throws a `ParameterError` if `param` is not within the given range.
        """
        if name in self:
            return self.floating_point(name, valid_range)
        if default:
            if (
                valid_range is not None
                and isinstance(default, float)
                and default not in valid_range
            ):
                raise ParameterError(
                    f"Default value of {default} not in the range of {valid_range}."
                )
            return default
        else:
            return None

    def optional_float(
        self, name: str, valid_range: Optional[Range[float]] = None
    ) -> Optional[float]:
        """
        Deprecated, prefer `optional_floating_point` for more consistent naming.
        """
        return self.optional_floating_point(name, valid_range)

    def boolean(self, name: str) -> bool:
        """
        Gets a boolean parameter.
        """
        return self.get(name, bool)

    def optional_boolean(
        self, name: str, default: _U = None
    ) -> Union[Optional[bool], _U]:
        """
        Gets a boolean parameter if present.

        Avoid the temptation to do `params.optional_boolean('foo') or default_value`.
        """
        return self.get_optional(name, bool, default)

    def optional_boolean_with_default(self, name: str, default_value: bool) -> bool:
        """
        Deprecated. Prefer `optional_boolean` with default as a parameter.

        Gets a boolean parameter if present; otherwise returns the provided default.
        """
        return self.optional_boolean(name, default_value)

    def optional_namespace(self, name: str) -> Optional["Parameters"]:
        """
        Get the namespace with the given name, if possible.

        If the namespace is not present or there is a non-namespace parameter of the given name,
        If the namespace is not present or there is a non-namespace parameter of the given name,
        `None` is returned.
        """
        ret = self.get_optional(name, object)
        if isinstance(ret, Parameters):
            return ret
        else:
            return None

    def arbitrary_list(self, name: str) -> List:
        """
        Get a list with arbitrary structure.
        """
        return self.get(name, List)

    def optional_arbitrary_list(self, name: str, default: _U = None) -> Optional[List]:
        """
        Get a list with arbitrary structure, if available
        """
        if not default:
            return self.get_optional(name, List)
        elif isinstance(default, List):
            return self.get_optional(name, List, default)

        raise ParameterError(
            f"Provided default to optional arbitrary list isn't a list. {default}"
        )

    def optional_evaluate(
        self,
        name: str,
        expected_type: Type[ParamType],
        *,
        namespace_param_name: str = "value",
        special_values: Mapping[str, str] = ImmutableDict.empty(),
    ) -> Optional[ParamType]:
        """
        Get a parameter, if present, interpreting its value as Python code.

        Same as `evaluate` except returning `None` if the requested parameter is not present.
        """
        if name in self:
            return self.evaluate(
                name,
                expected_type,
                namespace_param_name=namespace_param_name,
                special_values=special_values,
            )
        else:
            return None

    # type ignored because ImmutableDict.empty() has type Dict[Any, Any]
    def evaluate(
        self,
        name: str,
        expected_type: Type[ParamType],
        *,
        context: Optional[Mapping] = None,
        namespace_param_name: str = "value",
        special_values: Mapping[str, str] = ImmutableDict.empty(),
    ) -> ParamType:
        """
        Get a parameter, interpreting its value as Python code.

        The result of the code evaluation will be the parameter value. In addition to being a
        simple parameter, "name" can point to a namespace. In this case, the "value" parameter
        within the namespace is evaluated (unless some other parameter has been specified as
        `namespace_param_name`), but the list of modules given by the "import" parameter
        in that namespace (if present) are first imported.

        If the type of the result of the evaluation doesn't match `expected_type`, a
        `ParameterError` is raised.

        If `context` is specified, evaluation will happen in the context given. If you want
        evaluation to happen in the calling context, pass `locals()`.
        If the namespace contains the parameter *import*, it will be interpreted
        as a list of modules to import into the context before evaluation.

        Sometimes is it convenient to provide shortcuts for common cases. These can be specified
        in a `special_values` map whose keys are the special case values and whose values are the
        strings of expressions to be evaluated.
        """

        def handle_special_values(val: str) -> str:
            return special_values.get(val, val)

        namespace = self.optional_namespace(name)
        try:
            if namespace:
                return eval_in_context_of_modules(
                    handle_special_values(namespace.string(namespace_param_name)),
                    context or locals(),
                    context_modules=namespace.optional_arbitrary_list("import") or [],
                    expected_type=expected_type,
                )
            else:
                return eval_in_context_of_modules(
                    handle_special_values(self.string(name)),
                    context or locals(),
                    context_modules=[],
                    expected_type=expected_type,
                )
        except Exception as e:
            raise ParameterError(
                "Error while evaluating parameter {!s}".format(name)
            ) from e

    # type ignored because ImmutableDict.empty() has type Dict[Any, Any]
    def object_from_parameters(
        self,
        name: str,
        expected_type: Type[ParamType],
        *,
        context: Optional[Mapping] = None,
        creator_namepace_param_name: str = "value",
        special_creator_values: Mapping[str, str] = ImmutableDict.empty(),
        default_creator: Optional[Any] = None,
    ) -> ParamType:
        """
        Get an object of `expected_type`, initialized by the parameters in `name`.

        If `name` is a namespace, the `value` parameter within it is evaluated to get a "creator".
        If the result of the evaluation is a function, that function is itself the creator. If
        the result of the evaluation is a class, its `from_parameters` static method
        taking a single `Parameters` object will be used as the creator, if it exists. Otherwise
        its constructor will be used without parameters. The creator is then
        called with the namespace as its argument and the result is returned.  If the result does
        not match `expected_type` an exception will be raised. Do not include generic type arguments
        in `expected_type`.

        If `name` is a string, the same process is followed exception the string is evaluated
        directly to get the "creator" and an empty `Parameters` is passed.

        You can specify a different field within a namespace to be evaluated besides 'value' by
        specifying `creator_namespace_param_name`.

        You can specify a default creator to be used if none is specified with `default_creator`.

        You may specify additional context within which evaluation should happen with `context`.
        If you want evaluation to happen in the calling context, set this to `locals()`.
        If the namespace contains the parameter *import*, it will be interpreted
        as a list of modules to import into the context before evaluation.

        For the user's convenience, you may include a map of special values to expression strings.
        If the expression to be evaluated exactly matches any key of this map, the value from the
        map will be evaluated instead.

        If the namespace contains the field `import`, it will be treated as a comma-separated list
        of modules to be imported before evaluation.
        """
        if name in self:
            creator = self.evaluate(
                name,
                object,
                context=context,
                namespace_param_name=creator_namepace_param_name,
                special_values=special_creator_values,
            )
        elif default_creator:
            creator = default_creator
        else:
            raise ParameterError(
                "No creator class specified when creating an object from {!s}".format(
                    name
                )
            )

        params_to_pass = self.optional_namespace(name) or Parameters.empty()
        if inspect.isclass(creator):
            if hasattr(creator, "from_parameters"):
                ret: Callable[[Optional[Parameters]], ParamType] = getattr(
                    creator, "from_parameters"
                )(params_to_pass)
            else:
                ret = creator()  # type: ignore
        elif callable(creator):
            ret = creator(params_to_pass)
        else:
            raise ParameterError(
                "Expected a class with from_parameters or a callable but got {!s}".format(
                    creator
                )
            )

        if isinstance(ret, expected_type):
            return ret
        else:
            raise ParameterError(
                "When instantiating using from_parameters, expected {!s} but"
                " got {!s}".format(expected_type, ret)
            )

    def get(self, param_name: str, param_type: Type[ParamType]) -> ParamType:
        """
        Get a parameter with type-safety.

        Gets the given parameter, throwing a `ParameterError` if it is not of the specified type.

        Throws a `ParameterError` if the parameter is unknown.
        """

        ret = self._private_get(param_name)
        if isinstance(ret, param_type):
            return ret
        else:
            raise ParameterError(
                "When looking up parameter '{!s}', expected a value of type {!s}, but got {!s} "
                "of type {!s}".format(param_name, param_type, ret, type(ret))
            )

    def get_optional(
        self, param_name: str, param_type: Type[ParamType], default: _U = None
    ) -> Union[Optional[ParamType], _U]:
        """
        Get a parameter with type-safety.

        Gets the given parameter, throwing a `ParameterError` if it is not of the
        specified type.

        If a default is provided return the default otherwise
        If the parameter is unknown, returns `None`
        """
        ret = self._private_get(param_name, optional=True)
        if not ret:
            if default:
                return default
            return ret
        elif isinstance(ret, param_type):
            return ret
        else:
            raise ParameterError(
                "When looking up parameter '{!s}', expected a value of type {!s}, but got {!s} "
                "of type {!s}".format(param_name, param_type, ret, type(ret))
            )

    def path_list_from_file(self, param: str, *, log_name=None) -> Sequence[Path]:
        """
        Gets a list of paths from the file pointed to by param

        The paths are assumed to be listed one-per-line. Blank lines and lines
        where the first non-whitespace character is '#' are skipped.

        If log_name is specified, a message will be logged at info level of the form "Loaded
        <number> <log_name> from <file>"
        """
        file_list_file = self.existing_file(param)
        with open(str(file_list_file), "r", encoding="utf-8") as inp:
            ret = [
                Path(line.strip())
                for line in inp
                if line.strip() and not line.strip().startswith("#")
            ]
            if log_name:
                _logger.info("Loaded %s %s from %s", len(ret), log_name, file_list_file)
            return ret

    def path_map_from_file(self, param: str, *, log_name=None) -> Mapping[str, Path]:
        """
        Gets a map of keys to paths from the file pointed to by param

        We assume there are two tab-separated fields.  The first is the string key,
        the second is the path.

        If log_name is specified, a message will be logged at info level of the form "Loaded
        <number> <log_name> from <file>"
        """
        file_map_file = self.existing_file(param)
        with open(str(file_map_file), encoding="utf-8") as inp:
            ret_b: ImmutableDict.Builder[str, Path] = ImmutableDict.builder()
            for (line_num, line) in enumerate(inp):
                try:
                    parts = line.split("\t")
                    if len(parts) != 2:
                        raise IOError(
                            "Expected two tab-separated fields but got {!s}".format(
                                len(parts)
                            )
                        )
                    ret_b.put(parts[0].strip(), Path(parts[1].strip()))
                except Exception as e:
                    raise IOError(
                        "Error parsing line {!s} of {!s}:\n{!s}".format(
                            line_num, file_map_file, line
                        )
                    ) from e

            ret = ret_b.build()
            if log_name:
                _logger.info("Loaded %s %s from %s", len(ret), log_name, file_map_file)
            return ret

    def _private_get(self, param_name: str, optional=False) -> Any:
        # pylint:disable=protected-access
        param_components = param_name.split(".")
        check_arg(param_components, "Parameter name cannot be empty")

        current = self
        namespaces_processed = []
        for param_component in param_components:
            if not isinstance(current, Parameters):
                if optional:
                    return None
                else:
                    raise ParameterError(
                        "When getting parameter "
                        + param_name
                        + " expected "
                        + ".".join(namespaces_processed)
                        + " to be a map, but it is a leaf: "
                        + str(current)
                        + ". Maybe you mistakenly prefixed the map keys with '-'?"
                    )

            if param_component in current._data:
                current = current._data[param_component]
                namespaces_processed.append(param_component)
            elif not optional:
                if namespaces_processed:
                    context_string = "in context " + ".".join(namespaces_processed)
                else:
                    context_string = "in root context"
                available_parameters = str(
                    [
                        key
                        for (key, val) in current._data.items()
                        if not isinstance(val, Parameters)
                    ]
                )
                available_namespaces = str(
                    [
                        key
                        for (key, val) in current._data.items()
                        if isinstance(val, Parameters)
                    ]
                )
                raise ParameterError(
                    "Parameter "
                    + param_name
                    + " not found. In "
                    + context_string
                    + " available parameters are "
                    + available_parameters
                    + ", available namespaces are "
                    + available_namespaces
                )
            else:
                # absent optional parameter
                return None

        return current

    def __str__(self) -> str:
        str_sink = CharSink.to_string()
        YAMLParametersWriter().write(self, str_sink)
        return str_sink.last_string_written


@attrs(auto_attribs=True)
class YAMLParametersLoader:
    """
    Loads `Parameters` from a modified YAML format.

    The format of the parameters file is YAML with the following restrictions:
    * all non-leaf objects, including the top-level, must be maps
    * all keys must be strings
    * duplicate keys are not allowed (this is not currently enforced: #259)

    The following additional processing will be done:
    * if there is a top-level list-valued key '_includes', it will be removed.  Each of its
    values will be interpreted as a path and loaded.  If there are multiple included files,
    parameters loaded from earlier files will form the loading context (See `load`) for later ones.
    Parameter mappings in files loaded later will overwrite those in files loaded earlier.  Relative
    paths will be interpreted relative to the parameter file being loaded.

    * any parameters containing strings surrounded by `%` will be interpolated by replacing that
    string (and the `%`s) with the value of the parameter.  Failed interpolations will result
    in a `ParameterError`.

    If *interpolate_environmental_variables* (default: true) is specified, then environmental
    variables will be available for interpolation, though they will not themselves appear in the
    loaded parameters.  Explicitly-specified parameters have priority over environmental variables.

    See unit tests in `test_parameters` for examples.
    """

    interpolate_environmental_variables: bool = True

    def load(
        self,
        f: Union[str, Path],
        context: Optional[Parameters] = None,
        *,
        included_context: Optional[Parameters] = None,
    ):
        """
        Loads parameters from a YAML file.

        If `included_context` is specified, its content will be included in the returned
        Parameters (if not overridden) and will be available for interpolation.
        """

        # handle deprecated context parameter
        if context is not None:
            if included_context is not None:
                raise ParameterError(
                    "Cannot specify both included_context and deprecated context"
                    "parameters. Only specify the former."
                )
            else:
                included_context = context

        # provide default value for included context
        if included_context is None:
            non_none_included_context = Parameters.empty()
        else:
            non_none_included_context = included_context

        if isinstance(f, str):
            f = Path(f)

        return self._inner_load_from_string(
            f.read_text(encoding="utf-8"),
            error_string=str(f),
            includes_are_relative_to=f.parent,
            included_context=non_none_included_context,
        )

    def load_string(
        self,
        param_file_content: str,
        *,
        included_context: Parameters = Parameters.empty(),
    ) -> Parameters:
        """
        Loads parameters from a string.

        This behaves just like *load*, except relative includes are not allowed.
        """
        return self._inner_load_from_string(
            param_file_content,
            error_string=f"String param file:\n{param_file_content}",
            includes_are_relative_to=None,
            included_context=included_context,
        )

    def _inner_load_from_string(
        self,
        param_file_content: str,
        error_string: str,
        *,
        included_context: Parameters = Parameters.empty(),
        includes_are_relative_to: Optional[Path] = None,
    ):
        """
        Loads parameters from a YAML file.

        If `context` is specified, its content will be included in the returned Parameters (if
        not overridden) and will be available for interpolation.
        """
        try:
            raw_yaml = yaml.safe_load(param_file_content)
            self._validate(raw_yaml)
            previously_loaded = included_context

            # process and remove special include directives
            if "_includes" in raw_yaml:
                for included_file in raw_yaml["_includes"]:
                    _logger.info("Processing included parameter file %s", included_file)
                    if not os.path.isabs(included_file):
                        if includes_are_relative_to is not None:
                            included_file_path = Path(
                                includes_are_relative_to, included_file
                            ).resolve(strict=True)
                        else:
                            raise ParameterError(
                                "Cannot do relative includes when loading from"
                                "a string."
                            )
                    else:
                        included_file_path = Path(included_file)
                    previously_loaded = self._unify(
                        previously_loaded,
                        self._inner_load_from_string(
                            included_file_path.read_text(encoding="utf-8"),
                            error_string=str(included_file_path),
                            includes_are_relative_to=included_file_path.parent,
                            included_context=previously_loaded,
                        ),
                    )
                del raw_yaml["_includes"]

            interpolation_context = dict(previously_loaded.as_mapping())
            if self.interpolate_environmental_variables:
                for k, v in os.environ.items():
                    # environmental variables are overridden by explicit parameters
                    if k not in interpolation_context:
                        interpolation_context[k] = v

            return self._unify(
                previously_loaded,
                self._interpolate(
                    Parameters.from_mapping(raw_yaml),
                    Parameters.from_mapping(interpolation_context),
                ),
            )
        except Exception as e:
            raise IOError(f"Failure while loading parameter file {error_string}") from e

    @staticmethod
    def _validate(raw_yaml: Mapping):
        # we don't use check_isinstance so we can have a custom error message
        check_arg(
            isinstance(raw_yaml, Mapping),
            "Parameters YAML files must be mappings at the top level",
        )
        YAMLParametersLoader._check_all_keys_strings(raw_yaml)

    @staticmethod
    def _check_all_keys_strings(mapping: Mapping, path=None):
        if path is None:
            path = []

        non_string_keys = [x for x in mapping.keys() if not isinstance(x, str)]
        if non_string_keys:
            context_string = (
                (" in context" + ".".join(path)) if path else " in root context"
            )
            raise IOError("Non-string key(s) " + str(non_string_keys) + context_string)

        for val in mapping.values():
            if isinstance(val, Mapping):
                YAMLParametersLoader._check_all_keys_strings(val)

    _INTERPOLATION_REGEX = re.compile(r"%([\w\.]+)%")

    # noinspection PyProtectedMember
    @staticmethod
    def _interpolate(to_interpolate: Parameters, context: Parameters) -> Parameters:
        """Perform interpolation within arbitrarily nested Parameters, looking up values
        in a context if necessary.

        Limitations:
        - There cannot be interpolation in keys.
        """
        # In order to perform arbitrary interpolation, we perform topological sort on a graph where
        # the nodes are parameter keys, and edges point from those keys to each interpolation group
        # in that key's value. For example, the parameter entry `foo: %bar%/projects/%meep.baz%`
        # would give the edges (foo, bar) and (foo, meep.baz).
        #
        # pylint:disable=protected-access
        nodes = list(to_interpolate._data.keys())
        edges = list()
        for key, val in to_interpolate._data.items():
            if isinstance(val, str):
                for interp_match in YAMLParametersLoader._INTERPOLATION_REGEX.findall(
                    val
                ):
                    nodes.append(interp_match)
                    edges.append((key, interp_match))
        g = Digraph(nodes=nodes, edges=edges)
        # Since each edge has been created to point from a key to a dependency, this is to make the
        # ordering start from the leaves.
        interpolation_ordering = tuple(reversed(tuple(g.topological_sort())))

        # Perform the interpolation in-place.
        interpolation_mapping = dict(to_interpolate._data)

        for start_node in interpolation_ordering:
            if start_node in interpolation_mapping:
                end_node = interpolation_mapping[start_node]
            else:
                try:
                    end_node = context._private_get(start_node)
                except ParameterError:
                    raise ParameterError(
                        f"The key '{start_node}' doesn't exist in the parameters."
                    )
            if isinstance(end_node, str):
                replaced_end_node = _recursively_replace_matches(
                    end_node,
                    YAMLParametersLoader._INTERPOLATION_REGEX,
                    interpolation_mapping,
                )
            elif isinstance(end_node, Parameters):
                replaced_end_node = YAMLParametersLoader._interpolate(end_node, context)
            else:
                replaced_end_node = end_node
            interpolation_mapping[start_node] = replaced_end_node
        return Parameters.from_mapping(
            immutabledict(
                (key, interpolation_mapping[key]) for key in to_interpolate._data.keys()
            )
        )

    def _unify(self, old: Parameters, new: Parameters, namespace="") -> Parameters:
        # pylint:disable=protected-access
        ret = dict()
        for (key, old_val) in old._data.items():
            if key in new:
                new_val = new._data[key]
                if isinstance(old_val, Parameters) != isinstance(new_val, Parameters):
                    raise IOError(
                        "When unifying parameters, "
                        + namespace
                        + key
                        + "is a parameter on one side and a namespace on the other"
                    )
                elif isinstance(old_val, Parameters):
                    ret[key] = self._unify(old_val, new_val, namespace + key + ".")
                else:
                    ret[key] = new_val
            else:
                ret[key] = old_val

        for (key, new_val) in new._data.items():
            if key not in old:
                ret[key] = new_val

        return Parameters.from_mapping(ret)


@attrs(frozen=True)
class YAMLParametersWriter:
    def write(self, params: Parameters, sink: Union[Path, str, CharSink]) -> None:
        # pylint:disable=protected-access

        def dictify(data):
            if isinstance(data, ImmutableDict):
                return {k: dictify(v) for (k, v) in data.items()}
            elif isinstance(data, Parameters):
                return dictify(data._data)
            else:
                return data

        if isinstance(sink, Path) or isinstance(sink, str):
            sink = CharSink.to_file(sink)
        with sink.open() as out:
            yaml.dump(
                dictify(params._data),
                out,
                # prevents leaf dictionaries from being written in the
                # human unfriendly compact style
                default_flow_style=False,
                indent=4,
                width=78,
            )


def _recursively_replace_matches(
    candidate: Any, pattern: Pattern[str], mapping: Mapping[str, Any]
) -> Any:
    """Replace as many groups for interpolation in a string as possible.

    For a candidate that may need to be interpolated,
    - If we've reached something that isn't a string, we're done.
    - If the interpolation pattern doesn't match, we're done.
    """
    if not isinstance(candidate, str):
        return candidate
    match = pattern.search(candidate)
    if not match:
        return candidate
    interp_match = match.group()[1:-1]
    if not isinstance(mapping[interp_match], str):
        return mapping[interp_match]
    return _recursively_replace_matches(
        candidate.replace(f"%{interp_match}%", mapping[interp_match]), pattern, mapping
    )
