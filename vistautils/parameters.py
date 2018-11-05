import inspect
import logging
import re
import shutil
from pathlib import Path
from typing import (
    Any,
    Dict,
    List,
    Mapping,
    Match,
    Optional,
    Sequence,
    Type,
    TypeVar,
    Union,
)

import yaml
from attr import attrs
from immutablecollections import ImmutableDict

from vistautils.attrutils import attrib_opt_immutable
from vistautils.io_utils import CharSink, is_empty_directory
from vistautils.misc_utils import eval_in_context_of_modules
from vistautils.preconditions import check_arg, check_isinstance

_logger = logging.getLogger(__name__)  # pylint:disable=invalid-name


class ParameterError(Exception):
    pass


ParamType = TypeVar("ParamType")  # pylint:disable=invalid-name


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

    _data: ImmutableDict[str, Any] = attrib_opt_immutable(ImmutableDict)

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
        becomes a namepace.
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
        if no parmeter by that name is present.  Throws a `ParameterError`
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

    def string(self, param_name: str) -> str:
        """
        Gets a string-valued parameter.

        Throws a `ParameterError` if `param` is not a known parameter.
        """
        return self.get(param_name, str)

    def __contains__(self, param_name: str) -> bool:
        return self._private_get(param_name, optional=True) is not None

    def namespace(self, name: str) -> "Parameters":
        """
        Get the namespace with the given name.
        """
        return self.get(name, Parameters)

    def integer(self, name: str) -> int:
        """
        Gets an integer parameters.
        """
        return self.get(name, int)

    def positive_integer(self, name: str) -> int:
        """
        Gets an parameter with a positive integer value.
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

    def optional_boolean(self, name: str) -> Optional[bool]:
        """
        Gets a boolean parameter if present.

        Avoid the temptation to do `params.optional_boolean('foo') or default_value`. If there is
        a default, prefer `optional_boolean_with_default`
        """
        return self.get_optional(name, bool)

    def optional_boolean_with_default(self, name: str, default_value: bool) -> bool:
        """
        Gets a boolean parameter if present; otherwise returns the provided default.
        """
        ret = self.optional_boolean(name)
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

    def optional_float(self, name: str) -> Optional[float]:
        """
        Gets a float parameter if present.

        Consider the idiom `params.optional_float('foo') or default_value`
        """
        return self.get_optional(name, float)

    def arbitrary_list(self, name: str) -> List:
        """
        Get a list with arbitrary structure.
        """
        return self.get(name, List)

    def optional_arbitrary_list(self, name: str) -> Optional[List]:
        """
        Get a list with arbitrary structure, if available
        """
        return self.get_optional(name, List)

    def optional_evaluate(
        self,
        name: str,
        expected_type: Type[ParamType],
        *,  # type: ignore
        namespace_param_name: str = "value",
        special_values: Dict[str, str] = ImmutableDict.empty()
    ) -> Optional[ParamType]:  # type: ignore
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
        *,  # type: ignore
        context: Optional[Dict] = None,
        namespace_param_name: str = "value",
        special_values: Dict[str, str] = ImmutableDict.empty()
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
    def object_from_parameters(  # type: ignore
        self,
        name: str,
        expected_type: Type[ParamType],
        *,
        context: Optional[Dict] = None,
        creator_namepace_param_name: str = "value",
        special_creator_values: Dict[str, str] = ImmutableDict.empty(),
        default_creator: Optional[Any] = None
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

        You can specify a default cretor to be used if none is specified with `default_creator`.

        You may specify additional context within which evaluation should happen with `context`.
        If you want evaluation to happen in the calling context, set this to `locals()`.

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
                ret = getattr(creator, "from_parameters")(params_to_pass)
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
        self, param_name: str, param_type: Type[ParamType]
    ) -> Optional[ParamType]:
        """
        Get a parameter with type-safety.

        Gets the given parameter, throwing a `ParameterError` if it is not of the
        specified type.

        If the parameter is unknown, returns `None`
        """
        ret = self._private_get(param_name, optional=True)
        if not ret or isinstance(ret, param_type):
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
        with open(file_list_file, "r") as inp:
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
        with open(file_map_file, "r") as inp:
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
    in a `ParameterError`.  You cannot currently interpolate from parameters in the same file,
    but this capability will be added in the future.

    See unit tests in `test_parameters` for examples.
    """

    def load(
        self, f: Union[str, Path], context=Parameters.empty(), root_path: Path = None
    ):
        """
        Loads parameters from a YAML file.

        If `context` is specified, its content will be included in the returned Parameters (if
        not overridden) and will be available for interpolation.

        If `root_path` is specified, that path is used for resolving relative path names in
        includes instead of the path of the parameter file being loaded.
        """
        if isinstance(f, str):
            f = Path(f)
        try:
            # if no special path is specified, included files will be resolved relative to
            # this file's path
            if not root_path:
                root_path = f.parent

            with open(f, "r") as ymlfile:
                raw_yaml = yaml.load(ymlfile)
                self._validate(raw_yaml)
            cur_context = context

            # process and remove special include directives
            if "_includes" in raw_yaml:
                for included_file in raw_yaml["_includes"]:
                    _logger.info("Processing included parameter file %s", included_file)
                    included_file_path = Path(root_path, included_file).resolve()
                    cur_context = self._unify(
                        cur_context,
                        self.load(
                            included_file_path, root_path=root_path, context=cur_context
                        ),
                    )
                del raw_yaml["_includes"]

            return self._unify(
                cur_context,
                self._interpolate(Parameters.from_mapping(raw_yaml), cur_context),
            )
        except Exception as e:
            raise IOError("Failure while loading parameter file " + str(f)) from e

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

    _INTERPOLATION_REGEX = re.compile("%((\\w|\\.)+)%")

    @staticmethod
    def _interpolate(to_interpolate: Parameters, context: Parameters) -> Parameters:
        # pylint:disable=protected-access
        def interpolate(key, raw_value) -> Any:
            def lookup_interpolation(interpolation_key: Match) -> str:
                try:
                    # we know it is safe to strip off the edge characters because they must
                    # be the wrapping '%'s
                    return context.string(interpolation_key.group()[1:-1])
                except ParameterError:
                    raise ParameterError(
                        "Exception while interpolating parameter "
                        + key
                        + " with raw value "
                        + raw_value
                    )

            if isinstance(raw_value, str):
                return YAMLParametersLoader._INTERPOLATION_REGEX.sub(
                    lookup_interpolation, raw_value
                )
            elif isinstance(raw_value, Parameters):
                # TODO: need topological sort. Issue #258
                return YAMLParametersLoader._interpolate(raw_value, context)
            else:
                return raw_value

        return Parameters.from_mapping(
            {key: interpolate(key, val) for (key, val) in to_interpolate._data.items()}
        )

    def _unify(self, old: Parameters, new: Parameters, namespace="") -> Parameters:
        #  pylint:disable=protected-access
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
