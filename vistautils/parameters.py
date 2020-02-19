# pylint: skip-file
import inspect
import logging
import os
import pickle
import re
import shutil
from pathlib import Path
from typing import (
    Any,
    Callable,
    Dict,
    Iterable,
    List,
    Mapping,
    Match,
    Optional,
    Pattern,
    Sequence,
    Tuple,
    Type,
    TypeVar,
    Union,
    overload,
)

from attr import attrib, attrs, evolve

from immutablecollections import ImmutableDict, immutabledict
from immutablecollections.converter_utils import _to_tuple

from vistautils._graph import Digraph
from vistautils.io_utils import CharSink, is_empty_directory
from vistautils.misc_utils import eval_in_context_of_modules
from vistautils.preconditions import check_arg, check_isinstance
from vistautils.range import Range

import yaml

_logger = logging.getLogger(__name__)  # pylint:disable=invalid-name


class ParameterError(Exception):
    pass


_ParamType = TypeVar("_ParamType")  # pylint:disable=invalid-name
_U = TypeVar("_U")  # pylint:disable=invalid-name


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
    namespace_prefix: Tuple[str, ...] = attrib(
        default=tuple(), converter=_to_tuple, kw_only=True
    )

    def __attrs_post_init__(self) -> None:
        for key in self._data:
            check_arg(
                "." not in key, "Parameter keys cannot contain namespace separator '.'"
            )

    @staticmethod
    def empty(*, namespace_prefix: Iterable[str] = tuple()) -> "Parameters":
        """
        A `Parameters` with no parameter mappings.
        """
        return Parameters.from_mapping(
            ImmutableDict.empty(), namespace_prefix=namespace_prefix
        )

    @staticmethod
    def from_mapping(
        mapping: Mapping, *, namespace_prefix: Iterable[str] = tuple()
    ) -> "Parameters":
        """
        Convert a dictionary of dictionaries into a `Parameter`s

        The top-level dictionary becomes the top-level namespace.  Each mapping-valued parameter
        becomes a namespace.
        """
        check_isinstance(mapping, Mapping)
        ret: List[Tuple[str, Any]] = []
        for (key, val) in mapping.items():
            if isinstance(val, Mapping):
                sub_namespace_prefix = list(namespace_prefix)
                sub_namespace_prefix.append(key)
                ret.append(
                    (
                        key,
                        Parameters.from_mapping(
                            val, namespace_prefix=sub_namespace_prefix
                        ),
                    )
                )
            else:
                # this case will also be triggered if the value is already a parameters object
                ret.append((key, val))
        return Parameters(ret, namespace_prefix=namespace_prefix)

    def as_nested_dicts(self) -> Dict[str, Any]:
        """
        A nested dictionary representing this `Parameters`.
        """

        def dictify(data):
            if isinstance(data, Dict):
                return data
            elif isinstance(data, Parameters):
                return dictify(data._data)
            elif isinstance(data, Mapping):
                return {k: dictify(v) for (k, v) in data.items()}
            else:
                # an atomic key value
                return data

        return dictify(self._data)

    def namespaced_items(self) -> Iterable[Tuple[str, Any]]:
        """
        Get all entries in this `Parameters`, both top-level and nested
        as *(param_name, value)* pairs
        where the param names are "fully-qualified"
        (that is, they are prefixed with their namespaces)
        """
        for (key, value) in self._data.items():
            if isinstance(value, Parameters):
                for (param_name, value) in value.namespaced_items():
                    yield param_name, value
            else:
                prefix = ".".join(self.namespace_prefix) + (
                    "." if self.namespace_prefix else ""
                )
                yield f"{prefix}{key}", value

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
        self,
        param_name: str,
        valid_options: Optional[Iterable[str]] = None,
        default: Optional[str] = None,
    ) -> str:
        """
        Gets a string-valued parameter.

        Throws a `ParameterError` if `param` is not a known parameter.
        """
        ret = self.get(param_name, str, default=default)
        if valid_options is not None and ret not in valid_options:
            raise ParameterError(
                f"The value {ret} for the parameter {param_name} is not one of the valid options "
                f"{tuple(valid_options)}"
            )
        return ret

    @overload
    def optional_string(
        self, param_name: str, valid_options: Optional[Iterable[str]] = None
    ) -> Optional[str]:
        ...

    @overload
    def optional_string(
        self,
        param_name: str,
        valid_options: Optional[Iterable[str]] = None,
        *,
        default: str,
    ) -> str:
        ...

    def optional_string(
        self,
        param_name: str,
        valid_options: Optional[Iterable[str]] = None,
        *,
        default: Optional[str] = None,
    ):
        """
        Gets a string-valued parameter, if possible.
        If a default is provided, return the default
        else returns *None* if the parameter is absent.

        Throws a `ParameterError` if `param` is not a known parameter.
        """
        if default is not None:
            self._warn_about_default()
        if param_name in self:
            return self.string(param_name, valid_options)
        else:
            return default  # type: ignore

    def __contains__(self, param_name: str) -> bool:
        return self._private_get(param_name, optional=True) is not None

    def namespace(self, name: str) -> "Parameters":
        """
        Get the namespace with the given name.
        """
        return self.get(name, Parameters)

    def has_namespace(self, name: str) -> bool:
        """
        Returns whether the parameter of the specified *name* has a value
        which is a nested `Parameters`.
        """
        maybe_namespace = self._private_get(name, optional=True)
        return maybe_namespace is not None and isinstance(maybe_namespace, Parameters)

    def integer(
        self,
        name: str,
        *,
        default: Optional[int] = None,
        valid_range: Range[int] = Range.all(),
    ) -> int:
        """
        Gets an integer parameter.
        """
        ret = self.get(name, int, default=default)
        if ret not in valid_range:
            raise ParameterError(
                f"Invalid value for integer parameter {name}. Expected a value in {valid_range}."
            )
        return ret

    @overload
    def optional_integer(self, name: str) -> Optional[int]:
        ...

    @overload
    def optional_integer(self, name, *, default: int) -> int:
        ...

    def optional_integer(self, name: str, *, default: Optional[int] = None):
        """
        Gets an integer parameter, if possible.

        Returns *None* if the parameter is not present.
        """
        if default is not None:  # pragma: no cover
            self._warn_about_default()

        if name in self:
            return self.integer(name)
        else:
            return default  # type: ignore

    def positive_integer(self, name: str, *, default: Optional[int] = None) -> int:
        """
        Gets an parameter with a positive integer value.

        Throws an exception if the parameter is present but is not a positive integer.
        """
        ret = self.integer(name, default=default)
        if ret > 0:
            return ret
        else:
            raise ParameterError(
                "For parameter {!s}, expected a positive integer but got {!s}".format(
                    name, ret
                )
            )

    @overload
    def optional_positive_integer(self, name: str) -> Optional[int]:
        ...

    @overload
    def optional_positive_integer(self, name: str, *, default: int) -> int:
        ...

    def optional_positive_integer(self, name: str, *, default: Optional[int] = None):
        """
        Gets a positive integer parameter, if possible.

        Returns *None* if the parameter is not present.
        Throws an exception if the parameter is present but is not a positive integer.
        """
        if default is not None:
            self._warn_about_default()

        if name in self:
            return self.positive_integer(name)
        if default:
            if isinstance(default, int) and default > 0:
                return default  # type: ignore
            else:
                raise ParameterError(f"Default value: {default} is not a positive value")
        return None

    def floating_point(
        self,
        name: str,
        valid_range: Optional[Range[float]] = None,
        *,
        default: Optional[float] = None,
    ) -> float:
        """
        Gets a float parameter.

        Throws a `ParameterError` if `param` is not within the given range.

        This method isn't called `float` to avoid a clash with the Python type.
        """
        ret = self.get(name, float, default=default)
        if valid_range is not None and ret not in valid_range:
            raise ParameterError(
                "For parameter {!s}, expected a float in the range {!s} but got {!s}".format(
                    name, valid_range, ret
                )
            )
        return ret

    @overload
    def optional_floating_point(
        self, name: str, valid_range: Optional[Range[float]] = None
    ) -> Optional[float]:
        ...

    @overload
    def optional_floating_point(
        self, name: str, valid_range: Optional[Range[float]] = None, *, default: float
    ) -> float:
        ...

    def optional_floating_point(
        self,
        name: str,
        valid_range: Optional[Range[float]] = None,
        *,
        default: Optional[float] = None,
    ):
        """
        Gets a float parameter if present.

        Throws a `ParameterError` if `param` is not within the given range.
        """
        if default is not None:
            self._warn_about_default()

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
            return default  # type: ignore
        else:
            return None

    def optional_float(
        self, name: str, valid_range: Optional[Range[float]] = None
    ) -> Optional[float]:
        """
        Deprecated, prefer `optional_floating_point` for more consistent naming.
        """
        return self.optional_floating_point(name, valid_range)

    def boolean(self, name: str, *, default: Optional[bool] = None) -> bool:
        """
        Gets a boolean parameter.
        """
        return self.get(name, bool, default=default)

    @overload
    def optional_boolean(self, name: str) -> Optional[bool]:
        ...

    @overload
    def optional_boolean(self, name: str, *, default: bool) -> bool:
        ...

    def optional_boolean(self, name: str, *, default: Optional[bool] = None):
        """
        Gets a boolean parameter if present.

        Avoid the temptation to do `params.optional_boolean('foo') or default_value`.
        """
        if default is not None:
            self._warn_about_default()

        return self.get_optional(name, bool, default=default)

    def optional_boolean_with_default(self, name: str, default_value: bool) -> bool:
        """
        Deprecated. Prefer `boolean` with default as a parameter.

        Gets a boolean parameter if present; otherwise returns the provided default.
        """
        if default_value is not None:  # pragma: no cover
            self._warn_about_default()

        ret = self.optional_boolean(name, default=default_value)
        if ret is not None:
            return ret
        else:
            return default_value

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

    def namespace_or_empty(self, name: str) -> Optional["Parameters"]:
        """
        Get the namespace with the given name, or an empty one.

        If the namespace is present, return it.
        If the parameter is present but is not a namespace, throw an exception.
        If the namespace is absent, return an empty namespace with the appropriate path prefix.
        """
        ret = self.get_optional(name, object)
        if isinstance(ret, Parameters):
            return ret
        elif ret is None:
            sub_namespace_prefix = list(self.namespace_prefix)
            sub_namespace_prefix.append(name)
            return Parameters.empty(namespace_prefix=sub_namespace_prefix)
        else:
            raise ParameterError(
                f"Expected a namespace, but got a regular parameters for {name}"
            )

    def arbitrary_list(self, name: str, *, default: Optional[List] = None) -> List:
        """
        Get a list with arbitrary structure.
        """
        return self.get(name, List, default=default)

    @overload
    def optional_arbitrary_list(self, name: str) -> Optional[List]:
        ...

    @overload
    def optional_arbitrary_list(self, name: str, *, default: List) -> List:
        ...

    def optional_arbitrary_list(self, name: str, *, default: Optional[List] = None):
        """
        Get a list with arbitrary structure, if available
        """
        if default is not None:  # pragma: no cover
            self._warn_about_default()

        if not default:
            return self.get_optional(name, List)
        elif isinstance(default, List):
            return self.get_optional(name, List, default=default)

        raise ParameterError(
            f"Provided default to optional arbitrary list isn't a list. {default}"
        )

    def optional_evaluate(
        self,
        name: str,
        expected_type: Type[_ParamType],
        *,
        namespace_param_name: str = "value",
        special_values: Mapping[str, str] = ImmutableDict.empty(),
    ) -> Optional[_ParamType]:
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
        expected_type: Type[_ParamType],
        *,
        context: Optional[Mapping] = None,
        namespace_param_name: str = "value",
        special_values: Mapping[str, str] = ImmutableDict.empty(),
        default: Optional[_ParamType] = None,
    ) -> _ParamType:
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
            to_evaluate = None
            context_modules: List = []

            if namespace:
                to_evaluate = namespace.string(namespace_param_name)
                context_modules = namespace.optional_arbitrary_list("import") or []
            elif name in self:
                to_evaluate = self.string(name)
                context_modules = []
            elif default is not None:
                return default
            else:
                raise ParameterError(f"Cannot evaluate non-existent parameter {name}")

            return eval_in_context_of_modules(
                handle_special_values(to_evaluate),
                context or locals(),
                context_modules=context_modules,
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
        expected_type: Type[_ParamType],
        *,
        context: Optional[Mapping] = None,
        creator_namepace_param_name: str = "value",
        special_creator_values: Mapping[str, str] = ImmutableDict.empty(),
        default_creator: Optional[Any] = None,
    ) -> _ParamType:
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
            if self.has_namespace(name):
                params_to_pass = self.namespace(name)
            else:
                params_to_pass = Parameters.empty(
                    namespace_prefix=_extend_prefix(self.namespace_prefix, name)
                )
        elif default_creator:
            creator = default_creator
            params_to_pass = Parameters.empty(
                namespace_prefix=_extend_prefix(self.namespace_prefix, name)
            )
        else:
            raise ParameterError(
                "No creator class specified when creating an object from {!s}".format(
                    name
                )
            )

        if inspect.isclass(creator):
            if hasattr(creator, "from_parameters"):
                ret: Callable[[Optional[Parameters]], _ParamType] = getattr(
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

    def get(
        self,
        param_name: str,
        param_type: Type[_ParamType],
        default: Optional[_ParamType] = None,
    ) -> _ParamType:
        """
        Get a parameter with type-safety.

        Gets the given parameter, throwing a `ParameterError` if it is not of the specified type.

        Throws a `ParameterError` if the parameter is unknown.
        """

        ret = self._private_get(param_name, default=default)
        if isinstance(ret, param_type):
            return ret
        else:
            raise ParameterError(
                f"{self._namespace_message()}When looking up parameter '{param_name}', "
                f"expected a value of type {param_type}, but got {ret} "
                "of type {type(ret)}"
            )

    @overload
    def get_optional(
        self, param_name: str, param_type: Type[_ParamType]
    ) -> Optional[_ParamType]:
        ...

    @overload
    def get_optional(
        self, param_name: str, param_type: Type[_ParamType], *, default: _U
    ) -> _U:
        ...

    def get_optional(
        self, param_name: str, param_type: Type[_ParamType], *, default: _U = None
    ):
        """
        Get a parameter with type-safety.

        Gets the given parameter, throwing a `ParameterError` if it is not of the
        specified type.

        If a default is provided return the default otherwise
        If the parameter is unknown, returns `None`
        """
        if default is not None:
            self._warn_about_default()

        ret = self._private_get(param_name, optional=True)
        if ret is not None:
            if isinstance(ret, param_type):
                return ret
            else:
                raise ParameterError(
                    "When looking up parameter '{!s}', expected a value of type {!s}, but got {!s} "
                    "of type {!s}".format(param_name, param_type, ret, type(ret))
                )
        else:
            return default

    def path_list_from_file(
        self, param: str, *, log_name=None, resolve_relative_to: Optional[Path] = None
    ) -> Sequence[Path]:
        """
        Gets a list of paths from the file pointed to by param

        The paths are assumed to be listed one-per-line. Blank lines and lines
        where the first non-whitespace character is '#' are skipped.

        If log_name is specified, a message will be logged at info level of the form "Loaded
        <number> <log_name> from <file>"

        All the paths in the file
        will be resolved relative to *resolve_relative_to* if it is specified.
        """
        file_list_file = self.existing_file(param)
        with open(str(file_list_file), "r", encoding="utf-8") as inp:
            ret = [
                resolve_relative_to / line.strip()
                if resolve_relative_to
                else Path(line.strip())
                for line in inp
                if line.strip() and not line.strip().startswith("#")
            ]
            if log_name:
                _logger.info("Loaded %s %s from %s", len(ret), log_name, file_list_file)
            return ret

    def path_map_from_file(
        self, param: str, *, log_name=None, resolve_relative_to: Optional[Path] = None
    ) -> Mapping[str, Path]:
        """
        Gets a map of keys to paths from the file pointed to by param

        We assume there are two tab-separated fields.  The first is the string key,
        the second is the path.

        If log_name is specified, a message will be logged at info level of the form "Loaded
        <number> <log_name> from <file>"

        All the paths in the file
        will be resolved relative to *resolve_relative_to* if it is specified.
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
                    path_part = parts[1].strip()
                    path = (
                        resolve_relative_to / path_part
                        if resolve_relative_to
                        else Path(path_part)
                    )
                    ret_b.put(parts[0].strip(), path)
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

    def pickled_object_from_file(self, param_name: str) -> Any:
        """
        Returns an unpickled object from file containing a pickled object at param_name
        """
        pickled_object_path = Path(self.get(param_name, str)).resolve()
        with pickled_object_path.open("rb") as pickled_object_file:
            return pickle.load(pickled_object_file)

    def _private_get(
        self, param_name: str, *, optional: bool = False, default: Optional[Any] = None
    ) -> Any:
        check_arg(isinstance(param_name, str))
        # pylint:disable=protected-access
        param_components = param_name.split(".")
        check_arg(param_components, "Parameter name cannot be empty")

        current = self
        namespaces_processed = []
        for param_component in param_components:
            if not isinstance(current, Parameters):
                if default:
                    return default
                elif optional:
                    return None
                else:
                    raise ParameterError(
                        self._namespace_message()
                        + "When getting parameter "
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
            elif default is not None:
                return default
            elif optional:
                return None
            else:
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
                    self._namespace_message()
                    + "Parameter "
                    + param_name
                    + " not found. In "
                    + context_string
                    + " available parameters are "
                    + available_parameters
                    + ", available namespaces are "
                    + available_namespaces
                )
        return current

    def __str__(self) -> str:
        str_sink = CharSink.to_string()
        YAMLParametersWriter().write(self, str_sink)
        return str_sink.last_string_written

    def _namespace_message(self) -> str:
        if self.namespace_prefix:
            namespace_str = ".".join(self.namespace_prefix)
            return f"In namespace {namespace_str}: "
        else:
            return ""

    def as_mapping(self) -> Mapping[str, Any]:
        """
        Deprecated and may be removed. Prefer `Parameters.as_nested_dicts`.
        """
        return self._data

    def _warn_about_default(self) -> None:
        logging.warning(
            "Using default with optional_X methods is deprecated; "
            "prefer using the non-optional method with a default=... argument"
        )


def _extend_prefix(
    namespace_prefix: Tuple[str, ...], new_element: str
) -> Tuple[str, ...]:
    ret = list(namespace_prefix)
    ret.append(new_element)
    return tuple(new_element)


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
        namespace_path: Sequence[str] = tuple(),
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
            namespace_path=namespace_path,
        )

    def load_string(
        self,
        param_file_content: str,
        *,
        included_context: Parameters = Parameters.empty(),
        namespace_path: Sequence[str] = tuple(),
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
            namespace_path=namespace_path,
        )

    def _inner_load_from_string(
        self,
        param_file_content: str,
        error_string: str,
        *,
        included_context: Parameters = Parameters.empty(),
        includes_are_relative_to: Optional[Path] = None,
        namespace_path: Sequence[str] = tuple(),
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

            interpolation_context = dict(previously_loaded.as_nested_dicts())
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
                namespace_prefix=namespace_path,
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

    _INTERPOLATION_REGEX = re.compile(r"%([\w.\-]+)%")

    # noinspection PyProtectedMember
    @staticmethod
    def _interpolate(to_interpolate: Parameters, context: Parameters) -> Parameters:
        r"""
        Perform interpolation within arbitrarily nested `Parameter`\ s,
        looking up values in a context if necessary.

        Any strings surrounded by *%*s will be replaced by the value
        of the parameter obtained by looking up the string within the *%*s as a parameter.
        Example:
            - name: "Bob"
            - greeting: "hello %name%"
        will yield a value of "hello Bob" for the parameter *greeting*.
        Parameter lookups are first performed relative to *to_interpolate*,
        falling back to *context* on lookup failures.

        If the entire uninterpolated string is an interpolation placeholder
        (e.g.  *foo: "%interpolate_me%"*), the parameter will be assigned
        the value of the parameter referred to by the interpolation placeholder.
        Note that this value may be a non-string.

        Both the parameter to interpolate and the parameter being interpolated
        may be nested below the top level.

        Limitations:
        - Keys are not interpolated, only values.
        - Both the key to be interpolated and the value to interpolate must be strings.
        """
        check_arg(
            not to_interpolate.namespace_prefix,
            "Cannot interpolate non-top-level Parameters",
        )
        check_arg(
            not context.namespace_prefix, "Cannot interpolate with non-top-level context"
        )

        # These will be used when we represent parameters as dicts-of-dicts below.
        def get_from_nested_dict(
            nested_dict: Dict[str, Any], param_name: str
        ) -> Optional[Any]:
            parts = param_name.split(".")
            cur_dict = nested_dict
            for part in parts[:-1]:
                if part in cur_dict:
                    cur_dict = cur_dict[part]
                else:
                    return None
            param_name = parts[-1]
            return cur_dict.get(param_name, None)

        def set_in_nested_dict(
            nested_dict: Dict[str, Any], fully_qualified_param_name: str, value: Any
        ) -> None:
            parts = fully_qualified_param_name.split(".")
            cur_dict = nested_dict
            for part in parts[:-1]:
                if part in cur_dict:
                    cur_dict = cur_dict[part]
                else:
                    return None
            param_name = parts[-1]
            cur_dict[param_name] = value

        # We make a mutable representation of the parameters we are interpolating
        # as nested dictionaries in order to perform the actual interpolation.
        # We will convert back to immutable Parameters objects at the end.
        mutable_parameters = to_interpolate.as_nested_dicts()

        # In order to perform arbitrary interpolation, we perform topological sort on a graph where
        # the nodes are parameter keys, and edges point from those keys to each interpolation group
        # in that key's value. For example, the parameter entry `foo: %bar%/projects/%meep.baz%`
        # would give the edges (foo, bar) and (foo, meep.baz).
        #
        # pylint:disable=protected-access
        # Perform the interpolation in-place.
        nodes = list()
        edges = list()

        def gather_interpolation_edges(params: Parameters) -> None:
            for key, val in params.namespaced_items():
                if isinstance(val, str):
                    for interp_match in YAMLParametersLoader._INTERPOLATION_REGEX.findall(
                        val
                    ):
                        nodes.append(key)
                        if get_from_nested_dict(mutable_parameters, interp_match):
                            # We don't want to include nodes from the context in the interpolation
                            # ordering since the context is present
                            # only to be referred to by for interpolation into other parameters,
                            # not to include its parameters directly in the interpolation result.
                            nodes.append(interp_match)
                            edges.append((key, interp_match))
                elif isinstance(val, Parameters):
                    gather_interpolation_edges(val)

        gather_interpolation_edges(to_interpolate)

        g = Digraph(nodes=nodes, edges=edges)
        # Since each edge has been created to point from a key to a dependency, this is to make the
        # ordering start from the leaves.
        interpolation_ordering = tuple(reversed(tuple(g.topological_sort())))

        def get_backing_off_to_context(param_name: str) -> Any:
            from_these_params = get_from_nested_dict(mutable_parameters, param_name)
            if from_these_params:
                return from_these_params

            # if the parameter is not present in the parameters we are interpolating directly,
            # we look it up in the context.
            try:
                return context._private_get(param_name)
            except ParameterError as e:
                raise ParameterError(
                    f"The key '{param_to_interpolate}' doesn't exist in the parameters."
                ) from e

        for param_to_interpolate in interpolation_ordering:
            # first, we need to get the *uninterpolated* parameters value
            # (i.e. with %foo%s still present).
            uninterpolated_param_value = get_from_nested_dict(
                mutable_parameters, param_to_interpolate
            )

            if not uninterpolated_param_value:
                raise RuntimeError(f"This should be impossible: {param_to_interpolate}")

            # Next, we need to actually interpolate the values.
            if isinstance(uninterpolated_param_value, str):
                # We only known how to interpolate string params.

                # We need to special-case when the value to be interpolated is a non-string.
                # This allowed only when the only contents of the uninterpolated string
                # is the interpolation placeholder.
                # In this case, the value of the parameter is assigned to be
                # the value of the parameter referred to by the interpolation placeholder.
                if YAMLParametersLoader._INTERPOLATION_REGEX.fullmatch(
                    uninterpolated_param_value
                ):
                    interpolated_value = get_backing_off_to_context(
                        uninterpolated_param_value[1:-1]
                    )
                else:
                    # the more usual case of interpolating a string into a string
                    def replace_param(param_match: Match[str]) -> str:
                        variable_to_interpolate = param_match.group()[1:-1]
                        value_to_interpolate = get_backing_off_to_context(
                            variable_to_interpolate
                        )
                        if isinstance(value_to_interpolate, str):
                            return value_to_interpolate
                        else:
                            # Note we already checked for the only allowable case
                            # for non-string interpolation on the other branch of the else.
                            raise ParameterError(
                                f"Can only replace an interpolation variable with a non-string "
                                f"value if the variable is the entire non-interpolated "
                                f"parameter value: {param_to_interpolate}"
                            )

                    interpolated_value = re.sub(
                        YAMLParametersLoader._INTERPOLATION_REGEX,
                        replace_param,
                        uninterpolated_param_value,
                    )
                set_in_nested_dict(
                    mutable_parameters, param_to_interpolate, interpolated_value
                )

        # Re-convert from the mutable dict-of-dict-....-of-dicts format
        # we have been using back to immutable Parameters.
        return Parameters.from_mapping(
            immutabledict(
                (key, mutable_parameters[key]) for key in to_interpolate._data.keys()
            ),
            namespace_prefix=to_interpolate.namespace_prefix,
        )

    def _unify(
        self,
        old: Parameters,
        new: Parameters,
        *,
        namespace_prefix: Sequence[str] = tuple(),
    ) -> Parameters:
        # pylint:disable=protected-access
        ret = dict()
        for (key, old_val) in old._data.items():
            if key in new:
                new_val = new._data[key]
                if isinstance(old_val, Parameters) != isinstance(new_val, Parameters):
                    if namespace_prefix:
                        namespace_prefix_str = ".".join(namespace_prefix)
                        param_str = f"{namespace_prefix_str}.{key}"
                    else:
                        param_str = key

                    raise IOError(
                        f"When unifying parameters, {param_str} is a parameter on one side and a "
                        f"namespace on the other"
                    )
                elif isinstance(old_val, Parameters):
                    new_namespace_prefix = list(namespace_prefix)
                    new_namespace_prefix.append(key)
                    ret[key] = self._unify(
                        old_val, new_val, namespace_prefix=new_namespace_prefix
                    )
                else:
                    ret[key] = new_val
            else:
                ret[key] = old_val

        for (key, new_val) in new._data.items():
            if key not in old:
                ret[key] = new_val

        return Parameters.from_mapping(ret, namespace_prefix=namespace_prefix)


@attrs(frozen=True)
class YAMLParametersWriter:
    def write(self, params: Parameters, sink: Union[Path, str, CharSink]) -> None:
        # pylint:disable=protected-access

        if isinstance(sink, Path) or isinstance(sink, str):
            sink = CharSink.to_file(sink)
        with sink.open() as out:
            yaml.dump(
                params.as_nested_dicts(),
                out,
                # prevents leaf dictionaries from being written in the
                # human unfriendly compact style
                default_flow_style=False,
                indent=4,
                width=78,
            )
