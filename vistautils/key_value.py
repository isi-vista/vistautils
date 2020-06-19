import tarfile
from abc import ABCMeta, abstractmethod
from contextlib import AbstractContextManager
from pathlib import Path
from typing import (
    AbstractSet,
    Any,
    Callable,
    Dict,
    Generic,
    Iterator,
    Mapping,
    MutableMapping,
    Optional,
    Set,
    Tuple,
    TypeVar,
    Union,
)
from zipfile import ZipFile

from attr import attrib, attrs

from immutablecollections import ImmutableDict, immutabledict, immutableset

from vistautils.io_utils import (
    ByteSink,
    ByteSource,
    CharSink,
    CharSource,
    read_doc_id_to_file_map,
    write_doc_id_to_file_map,
)
from vistautils.parameters import Parameters
from vistautils.preconditions import check_arg, check_not_none, check_state

K = TypeVar("K")
V = TypeVar("V")
T = TypeVar("T")


def _identity(x: str) -> str:
    return x


# the following two methods supply the default way of tracking keys in zip-backed stores
def _read_keys_from_keys_file(zip_file: ZipFile) -> Optional[AbstractSet[str]]:
    try:
        keys_data = zip_file.read("__keys")
        if keys_data:
            return immutableset(keys_data.decode("utf-8").split("\n"))
        else:
            # If keys_data is empty, the "split" above will return [''], which is wrong.
            return immutableset()
    except KeyError:
        return None


def _write_keys_to_keys_file(zip_file: ZipFile, keys: AbstractSet[str]) -> None:
    zip_file.writestr("__keys", "\n".join(keys).encode("utf-8"))


class KeyValueSink(Generic[K, V], metaclass=ABCMeta):
    """
    Anything which can accept key-value pairs.

    This can abstract over writing mappings to dictionaries, file systems, zip files, etc.

    Because some implementations should require cleanup, this should be used as a context
    manager:
    ```
    with KeyValueSink.zip_character_sink(foo) as sink:
       # use the sink
    ```

    Behavior in the face of duplicate keys is implementation-specific - implementations may choose
    to ignore, overwrite, or throw an exception.

    Particular implementations are free to reject certain keys (for example, a filesystem-backed
    implementation could reject keys which result in illegal path names).
    """

    @abstractmethod
    def put(self, key: K, value: V) -> None:
        raise NotImplementedError()

    def __setitem__(self, key, value) -> None:
        self.put(key, value)

    @abstractmethod
    def __enter__(self) -> "KeyValueSink[K,V]":
        raise NotImplementedError()

    @abstractmethod
    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        raise NotImplementedError()

    @staticmethod
    def zip_character_sink(
        path: Path,
        *,
        filename_function: Callable[[str], str] = _identity,
        overwrite: bool = True,
        keys_in_function: Callable[
            [ZipFile], Optional[AbstractSet[str]]
        ] = _read_keys_from_keys_file,
        keys_out_function: Callable[
            [ZipFile, AbstractSet[str]], None
        ] = _write_keys_to_keys_file,
    ) -> "KeyValueSink[str, str]":
        """
        A key-value sink backed by a zip file which stores character data.

        `file_namefunction` provides the mapping from keys to relative path names within the zip
        file.

        If overwrite is `True` (default) any existing zip file at the given path will be
        overwritten.  Otherwise, new entries will be appended to the given file.

        If duplicate keys are added, a `RuntimeError` will be thrown.

        By default, the list of keys will be stored in a file called `__keys` in the root of the
        zip file. To override this behavior, set `keys_in_function` and `keys_out_function`.
        Since these need to match, it is recommended to use a wrapper method around this one
        when overriding.
        """
        return _ZipCharFileKeyValueSink(
            path,
            filename_function=filename_function,
            overwrite=overwrite,
            keys_in_function=keys_in_function,
            keys_out_function=keys_out_function,
        )

    @staticmethod
    def zip_bytes_sink(
        path: Path,
        *,
        filename_function: Callable[[str], str] = _identity,
        overwrite: bool = True,
        keys_in_function: Callable[
            [ZipFile], Optional[AbstractSet[str]]
        ] = _read_keys_from_keys_file,
        keys_out_function: Callable[
            [ZipFile, AbstractSet[str]], None
        ] = _write_keys_to_keys_file,
    ) -> "KeyValueSink[str, bytes]":
        """
        A key-value sink backed by a zip file which stores character data.

        `file_namefunction` provides the mapping from keys to relative path names within
        the zip file.

        If overwrite is `True` (default) any existing zip file at the given path will be
        overwritten.  Otherwise, new entries will be appended to the given file.

        If duplicate keys are added, a `RuntimeError` will be thrown.

        By default, the list of keys will be stored in a file called `__keys` in the root of the
        zip file. To override this behavior, set `keys_in_function` and `keys_out_function`.
        Since these need to match, it is recommended to use a wrapper method around this one
        when overriding.
        """
        return _ZipBytesFileKeyValueSink(
            path,
            filename_function=filename_function,
            overwrite=overwrite,
            keys_in_function=keys_in_function,
            keys_out_function=keys_out_function,
        )


class KeyValueLinearSource(Generic[K, V], AbstractContextManager, metaclass=ABCMeta):
    """
    Anything which provide a sequence of key-value pairs.

    Many of these will be `KeyValueSources`, which allow random access, but some things, like
    .tar.gz files, lack efficient random access but can still be iterated over.
    """

    def items(
        self, key_filter: Callable[[K], bool] = lambda x: True
    ) -> Iterator[Tuple[K, V]]:
        raise NotImplementedError()

    @staticmethod
    def byte_linear_source_from_tar_gz(
        tgz_file: Path,
        key_function: Callable[[str], Optional[str]] = lambda x: x,
        name_filter: Callable[[str], bool] = lambda x: True,
    ) -> "KeyValueLinearSource[str,bytes]":
        """
        Expose a .tar.gz file as a str-bytes `KeyValueLinearSource`.

        This returns `KeyValueLinearSource` and not `KeyValueSource` because random-access
        is slow in TAR files.

        This will expose a sequence of key-value pairs for a .tar.gz file. By default, the keys
        are the keys within the .tar.gz file structure, which are typically relative paths, and the
        values are the byte content of that TAR file entry.

        If `name_filter` is specified, it will be call with the TAR file key for an entry; that
        entry
        will be processed only if `name_filter` returns `True`.

        If `key_function` is specified, it will be applied to the TAR file key for an entry and the
        string returned will be used as the key instead.  If `None` is returned, that entry is
        skipped.
        """
        return TarGzipBytesLinearKeyValueSource(tgz_file, key_function, name_filter)

    @staticmethod
    def str_linear_source_from_tar_gz(
        tgz_file: Path,
        key_function: Callable[[str], Optional[str]] = lambda x: x,
        name_filter: Callable[[str], bool] = lambda x: True,
    ) -> "KeyValueLinearSource[str,str]":
        """
        Exposes a .tar.gz file as a str-str `KeyValueLinearSource`.

        Exactly like `byte_linear_source_from_gz`, except the values are interpreted as UTF-8
        strings.
        """
        return KeyValueLinearSource.interpret_values(
            KeyValueLinearSource.byte_linear_source_from_tar_gz(
                tgz_file, key_function, name_filter
            ),
            lambda _, x: x.decode("utf-8"),
        )

    @staticmethod
    def interpret_values(
        wrapped: "KeyValueLinearSource[str, T]",
        interpretation_function: Callable[[str, T], V],
    ) -> "KeyValueLinearSource[str, V]":
        """
        Make a key-value linear source which interprets the values of another.

        This returns the same values are the wrapped source, except the values in each key-value
        pair of the wrapped source are replaced by the result of applying `interpretation_function`
        to the key and the value.
        """
        return InterpretedLinearKeyValueSource(wrapped, interpretation_function)


class KeyValueSource(Generic[K, V], KeyValueLinearSource[K, V], metaclass=ABCMeta):
    """
    Anything which can provides a key-value mapping.

    This can abstract over writing mappings to dictionaries, file systems, zip files, etc.

    Because some implementations could require cleanup, this should be used as a context
    manager:
    ```
    with KeyValueSource.zip_character_source(foo) as source:
       # use the source
    ```

    `None` will never be returned as an actual value; it always represents the absence of a
    key-value
    mapping.
    """

    @abstractmethod
    def __getitem__(self, item: K) -> V:
        """
        Get the value associated with the key.

        If there is no value associated, raises a `KeyError`.
        """
        raise NotImplementedError()

    @abstractmethod
    def get(self, key: K, _default: Optional[V] = None) -> Optional[V]:
        """
        Get the value associated with the key.

        If there is no value associated, returns None.
        """
        raise NotImplementedError()

    def keys(self) -> Optional[AbstractSet[K]]:
        """
        All the keys which can be looked up in this key-value source.

        Not every source will be able to provide this set; such sources will return `None`.
        """
        return None

    def items(
        self, key_filter: Callable[[K], bool] = lambda x: True
    ) -> Iterator[Tuple[K, V]]:
        keys = self.keys()  # pylint: disable=assignment-from-none
        if keys is not None:

            def generator_func() -> Iterator[Tuple[K, V]]:
                # mypy doesn't understand keys isn't None here
                for key in keys:  # type: ignore
                    if key_filter(key):
                        yield (key, self[key])

            return generator_func()
        else:
            raise NotImplementedError(
                "A KeyValueSource which supports item iteration but cannot "
                "provide keys must override the default implementation"
            )

    @staticmethod
    def from_path_mapping(id_to_path: Mapping[str, Path]) -> "KeyValueSource[str, str]":
        """
        Create a key-value source from a map of IDs to paths.

        The contents of the paths, interpreted as UTF-8, will be the values.
        """
        return _PathMappingCharKeyValueSource(id_to_path)  # type: ignore

    @staticmethod
    def from_doc_id_to_file_map(
        map_file: Union[str, Path, CharSource]
    ) -> "KeyValueSource[str,str]":
        if not isinstance(map_file, CharSource):
            map_file = CharSource.from_file(map_file)
        return _PathMappingCharKeyValueSource(  # type: ignore
            read_doc_id_to_file_map(map_file)
        )

    @staticmethod
    def binary_from_doc_id_to_file_map(
        map_file: Union[str, Path, CharSource]
    ) -> "KeyValueSource[str, bytes]":
        if not isinstance(map_file, CharSource):
            map_file = CharSource.from_file(map_file)
        return _PathMappingBytesKeyValueSource(  # type: ignore
            read_doc_id_to_file_map(map_file)
        )

    @staticmethod
    def zip_character_source(
        path: Path,
        filename_function: Callable[[str], str] = _identity,
        keys_function: Callable[
            [ZipFile], Optional[AbstractSet[str]]
        ] = _read_keys_from_keys_file,
    ) -> "KeyValueSource[str, str]":
        """
        A key-value source backed by a zip file which stores character data.

        `file_namefunction` provides the mapping from keys to relative path names within
        the zip file.

        By default, the set of `keys()` is available if there is  a special file inside the root of
        the zip called `__keys`, where they should be listed, one per line. If his file is absent,
        `keys()` returns `None`.  You may specify an alternative to this behavior by setting
        `keys_function`.
        """
        return _ZipCharFileKeyValuesSource(
            path, filename_function=filename_function, keys_function=keys_function
        )

    @staticmethod
    def zip_bytes_source(
        path: Path,
        filename_function: Callable[[str], str] = _identity,
        keys_function: Callable[
            [ZipFile], Optional[AbstractSet[str]]
        ] = _read_keys_from_keys_file,
    ) -> "KeyValueSource[str, bytes]":
        """
        A key-value source backed by a zip file which stores character data.

        `file_namefunction` provides the mapping from keys to relative path names within
        the zip file.

        By default, the set of `keys()` is available if there is  a special file inside the root of
        the zip called `__keys`, where they should be listed, one per line. If his file is absent,
        `keys()` returns `None`.  You may specify an alternative to this behavior by setting
        `keys_function`.
        """
        return _ZipBytesFileKeyValuesSource(
            path, filename_function=filename_function, keys_function=keys_function
        )

    # mypy is grumpy this doesn't agree with the signature of KeyValueLinearSource,
    # but it doesn't matter since it is a static method
    @staticmethod
    def interpret_values(  # type: ignore
        wrapped: "KeyValueSource[K, T]", interpretation_function: Callable[[K, T], V]
    ) -> "KeyValueSource[K, V]":  # type: ignore
        """
        Make a key-value source which interprets the values of another.

        This returns the same values are the wrapped source, except the values in each key-value
        pair of the wrapped source are replaced by the result of applying `interpretation_function`
        to the key and value.
        """
        return _InterpretedKeyValueSource(wrapped, interpretation_function)


class _DirectoryCharKeyValueSink(KeyValueSink[str, str]):
    def __init__(self, path: Path) -> None:
        self._path = path
        self.id_to_file: MutableMapping[str, Path] = dict()

    def put(self, key: str, value: str) -> None:
        out_file = self._path / key
        CharSink.to_file(out_file).write(value)
        self.id_to_file[key] = out_file

    def __enter__(self) -> "KeyValueSink[str,str]":
        self._path.rmdir()
        self._path.mkdir(parents=True, exist_ok=True)
        self.id_to_file = dict()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        write_doc_id_to_file_map(self.id_to_file, CharSink.to_file(self._path / "_index"))

    @staticmethod
    def from_parameters(params: Parameters) -> KeyValueSink[str, str]:
        """
        Create a key-value sink writing to a directory.
        """
        return _DirectoryCharKeyValueSink(params.existing_directory("path"))


class _DirectoryBytesKeyValueSink(KeyValueSink[str, bytes]):
    def __init__(self, path: Path) -> None:
        self._path = path
        self.id_to_file: MutableMapping[str, Path] = dict()

    def put(self, key: str, value: bytes) -> None:
        out_file = self._path / key
        ByteSink.to_file(out_file).write(value)
        self.id_to_file[key] = out_file

    def __enter__(self) -> "KeyValueSink[str,bytes]":
        self._path.rmdir()
        self._path.mkdir(parents=True, exist_ok=True)
        self.id_to_file = dict()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        write_doc_id_to_file_map(self.id_to_file, CharSink.to_file(self._path / "_index"))

    @staticmethod
    def from_parameters(params: Parameters) -> KeyValueSink[str, bytes]:
        """
        Create a key-value sink writing to a directory.
        """
        return _DirectoryBytesKeyValueSink(params.existing_directory("path"))


class _ZipKeyValueSink(Generic[V], KeyValueSink[str, V]):
    def __init__(
        self,
        path: Path,
        *,
        filename_function: Callable[[str], str] = _identity,
        keys_in_function: Callable[[ZipFile], Optional[AbstractSet[str]]] = None,
        keys_out_function: Callable[[ZipFile, AbstractSet[str]], None] = None,
        overwrite: bool = True,
    ) -> None:
        self._path = path
        self._zip_file: Optional[ZipFile] = None
        self._filename_function = filename_function
        self._overwrite = overwrite
        self._keys_in_function = keys_in_function
        self._keys_out_function = keys_out_function
        self._keys: Set[str] = set()
        check_arg(
            self._keys_out_function or not self._keys_in_function,
            "If you specify a key output function, you should also specify a key input"
            " function",
        )

    def put(self, key: str, value: V) -> None:
        check_state(self._zip_file, "Must use zip key-value sink as a context manager")
        check_not_none(key)
        check_not_none(value)
        if key in self._keys:
            raise ValueError(
                "Zip-backed key-value sinks do not support duplicate puts on the "
                "same key"
            )
        self._keys.add(key)
        filename = self._filename_function(key)
        check_arg(isinstance(value, str) or isinstance(value, bytes))
        self._zip_file.writestr(filename, value)  # type: ignore

    @abstractmethod
    def _to_bytes(self, val: V) -> bytes:
        raise NotImplementedError()

    def __enter__(self) -> "KeyValueSink[str, V]":
        self._zip_file = ZipFile(str(self._path), "w" if self._overwrite else "a")
        if self._keys_in_function:
            # update rather than assignment because return might not be mutable
            existing_keys = self._keys_in_function(self._zip_file)
            if existing_keys:
                self._keys.update(existing_keys)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        # if we are in a context manager, self._zip_file is not None
        if self._keys_out_function:
            self._keys_out_function(self._zip_file, self._keys)  # type: ignore
        self._zip_file.close()  # type: ignore


class _ZipCharFileKeyValueSink(_ZipKeyValueSink[str]):
    def _to_bytes(self, val: str) -> bytes:
        return val.encode("utf-8")

    @staticmethod
    def from_parameters(params: Parameters) -> KeyValueSink[str, str]:
        """
        Create a key-value sink writing to a zip file.

        Right now, these uses all the defaults for `KeyValueSink.zip_character_sink`. In the
        future, we might examine other parameters to allow greater customization.
        """
        return KeyValueSink.zip_character_sink(params.creatable_file("path"))


class _ZipBytesFileKeyValueSink(_ZipKeyValueSink[bytes]):
    def _to_bytes(self, val: bytes) -> bytes:
        return val

    @staticmethod
    def from_parameters(params: Parameters) -> KeyValueSink[str, bytes]:
        """
        Create a key-value sink writing to a zip file.

        Right now, these uses all the defaults for `KeyValueSink.zip_bytes_sink`. In the
        future, we might examine other parameters to allow greater customization.
        """
        return KeyValueSink.zip_bytes_sink(params.creatable_file("path"))


@attrs(frozen=True)
class _AbstractPathMappingKeyValueSource(Generic[V], KeyValueSource[str, V]):
    id_to_path: ImmutableDict[str, Path] = attrib(
        converter=immutabledict, default=immutabledict()
    )

    def keys(self) -> AbstractSet[str]:
        return self.id_to_path.keys()


@attrs(frozen=True)
class _PathMappingCharKeyValueSource(_AbstractPathMappingKeyValueSource[str]):
    def __getitem__(self, key: str) -> str:
        return CharSource.from_file(self.id_to_path[key]).read_all()

    def get(self, key: str, _default: Optional[str] = None) -> Optional[str]:
        if key in self.id_to_path:
            return self[key]
        else:
            return _default

    def __exit__(self, exc_type, exc_value, traceback):
        return False


@attrs(frozen=True)
class _PathMappingBytesKeyValueSource(_AbstractPathMappingKeyValueSource[bytes]):
    def __getitem__(self, key: str) -> bytes:
        return ByteSource.from_file(self.id_to_path[key]).read()

    def get(self, key: str, _default: Optional[bytes] = None) -> Optional[bytes]:
        if key in self.id_to_path:
            return self[key]
        else:
            return _default

    def __exit__(self, exc_type, exc_value, traceback):
        return False


class _ZipFileKeyValueSource(Generic[V], KeyValueSource[str, V], metaclass=ABCMeta):
    def __init__(
        self,
        path: Path,
        filename_function: Callable[[str], str] = _identity,
        keys_function: Callable[[ZipFile], Optional[AbstractSet[str]]] = None,
    ) -> None:
        self.path = path
        self._filename_function = filename_function
        self._keys_function = keys_function
        self._zip_file: Optional[ZipFile] = None
        self._keys: Optional[AbstractSet[str]] = None

    def keys(self) -> Optional[AbstractSet[str]]:
        check_state(self._zip_file, "Must use zip key-value source as a context manager")
        return self._keys

    def __getitem__(self, key: str) -> V:
        # we know _internal_get won't return the default value
        return self._internal_get(  # type: ignore
            key, has_default_val=False, default_val=None
        )

    def get(self, key: str, _default: Optional[V] = None) -> Optional[V]:
        return self._internal_get(key, has_default_val=True, default_val=_default)

    def _internal_get(
        self, key: str, *, has_default_val: bool, default_val: Optional[V]
    ) -> Optional[V]:
        check_state(self._zip_file, "Must use zip key-value source as a context manager")
        check_not_none(key)
        filename = self._filename_function(key)
        try:
            # safe by check_state above
            zip_bytes = self._zip_file.read(filename)  # type: ignore
        except KeyError as e:
            if has_default_val:
                return default_val
            raise KeyError(
                f"Key '{key}' not found in zip key-value source backed by " f"{self.path}"
            ) from e
        return self._process_bytes(zip_bytes)

    @abstractmethod
    def _process_bytes(self, _bytes: bytes) -> V:
        raise NotImplementedError()

    def __enter__(self) -> "KeyValueSource[str, V]":
        self._zip_file = ZipFile(str(self.path), "r")
        if self._keys_function:
            self._keys = self._keys_function(self._zip_file)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        check_state(self._zip_file)
        self._zip_file.close()  # type: ignore
        self._zip_file = None


class _ZipBytesFileKeyValuesSource(_ZipFileKeyValueSource[bytes]):
    def __init__(
        self,
        path: Path,
        *,
        filename_function: Callable[[str], str] = _identity,
        keys_function: Callable[[ZipFile], Optional[AbstractSet[str]]] = None,
    ) -> None:
        super().__init__(path, filename_function, keys_function)

    def _process_bytes(self, _bytes: bytes) -> bytes:
        return _bytes

    @staticmethod
    def from_parameters(params: Parameters) -> KeyValueSource[str, bytes]:
        """
        Construct a zip file key-value source from parameters.

        The "path" parameter should be the zip file to be opened.

        Currently we assume the zipfile contains a file with the IDs, which it will if it
        were created by the default `KeyValueSink.zip_bytes_sink()`. Support for custom key
        functions will be added in the future.
        """
        return KeyValueSource.zip_bytes_source(params.existing_file("path"))

    def __repr__(self) -> str:
        return f"_ZipBytesFileKeyValueSource({self.path})"


class _ZipCharFileKeyValuesSource(_ZipFileKeyValueSource[str]):
    def __init__(
        self,
        path: Path,
        *,
        filename_function: Callable[[str], str] = _identity,
        keys_function: Callable[[ZipFile], Optional[AbstractSet[str]]] = None,
    ) -> None:
        super().__init__(path, filename_function, keys_function)

    def _process_bytes(self, _bytes: bytes) -> str:
        return _bytes.decode("utf-8")

    @staticmethod
    def from_parameters(params: Parameters) -> KeyValueSource[str, str]:
        """
        Construct a zip file key-value source from parameters.

        The "path" parameter should be the zip file to be opened.

        Currently we assume the zipfile contains a file with the IDs, which it will if it
        were created by the default CharSink.zip_character_sink(). Support for custom key
        functions will be added in the future.
        """
        return KeyValueSource.zip_character_source(params.existing_file("path"))


class TarGzipBytesLinearKeyValueSource(KeyValueLinearSource[str, bytes]):
    """
    Expose a .tar.gz file as a str-bytes `KeyValueLinearSource`.

    See `KeyValueLinearSource.byte_linear_source_from_tar_gz` for documentation.

    This sub-classes `KeyValueLinearSource` and not `KeyValueSource` because random-access
    is slow in TAR files.

    This will expose a sequence of key-value pairs for a .tar.gz file. By default, the keys
    are the keys within the .tar.gz file structure, which are typically relative paths, and the
    values are the byte content of that TAR file entry.

    If `name_filter` is specified, it will be call with the TAR file key for an entry; that entry
    will be processed only if `name_filter` returns `True`.

    If `key_function` is specified, it will be applied to the TAR file key for an entry and the
    string returned will be used as the key instead.  If `None` is returned, that entry is
    skipped.
    """

    def __init__(
        self,
        tgz_path: Path,
        key_function: Callable[[str], Optional[str]] = lambda x: x,
        name_filter: Callable[[str], bool] = lambda x: True,
    ) -> None:
        self.tgz_path = tgz_path
        self.inp: Optional[tarfile.TarFile] = None
        self.key_function = key_function
        self.name_filter = name_filter

    def items(
        self, key_filter: Callable[[str], bool] = lambda x: True
    ) -> Iterator[Tuple[str, bytes]]:
        check_state(
            self.inp,
            "Need to enter TarGZipBytesLinearKeyValueSource as context "
            "manager before using it.",
        )

        def generator_function() -> Iterator[Tuple[str, bytes]]:
            # safe by check_state above
            for member in self.inp:  # type: ignore
                if member.isfile() and self.name_filter(member.name):
                    key = self.key_function(member.name)
                    if key and key_filter(key):
                        data = self.inp.extractfile(member)  # type: ignore
                        if data:
                            with data:
                                yield (key, data.read())
                        else:
                            raise IOError(f"Cannot read member {member} of {self}")

        return generator_function()

    def __enter__(self) -> "KeyValueLinearSource[str,bytes]":
        self.inp = tarfile.open(self.tgz_path, "r")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        self.inp.close()  # type: ignore
        return False


class InterpretedLinearKeyValueSource(Generic[V], KeyValueLinearSource[str, V]):
    """
    Key-value linear source which interprets the values of another.

    See `KeyValueLinearSource.interpret_values` for details.
    """

    def __init__(
        self,
        wrapped_source: KeyValueLinearSource[str, T],
        interpretation_function: Callable[[str, T], V],
    ) -> None:
        self.wrapped_source = wrapped_source
        self.interpretation_function = interpretation_function

    def items(
        self, key_filter: Callable[[str], bool] = lambda x: True
    ) -> Iterator[Tuple[K, V]]:
        def generator_function() -> Iterator[Tuple[str, V]]:
            for wrapped_pair in self.wrapped_source.items(key_filter=key_filter):
                yield wrapped_pair[0], self.interpretation_function(
                    wrapped_pair[0], wrapped_pair[1]
                )

        return generator_function()  # type: ignore

    def __enter__(self) -> "KeyValueLinearSource[str, V]":
        self.wrapped_source.__enter__()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> Optional[bool]:
        return self.wrapped_source.__exit__(exc_type, exc_val, exc_tb)


class _InterpretedKeyValueSource(Generic[K, V], KeyValueSource[K, V]):
    """
    Key-value source which interprets the values of another
    """

    def __init__(
        self,
        wrapped_source: KeyValueSource[K, T],
        interpretation_function: Callable[[K, T], V],
    ) -> None:
        self.wrapped_source = wrapped_source
        self.interpretation_function = interpretation_function

    def keys(self) -> Optional[AbstractSet[K]]:
        return self.wrapped_source.keys()

    def get(self, key: K, _default: Optional[V] = None) -> Optional[V]:
        # cannot use None as a "this is missing" marked in case underlying source really
        # does return None as a value for some non-missing key
        # and the user has a non-None default.
        sentinel = object()
        inner_get = self.wrapped_source.get(key, sentinel)  # type: ignore
        if inner_get is not sentinel:
            # if inner_get result is None, it is because X is Optional[something],
            # so interpretation_function can handle it
            return self.interpretation_function(key, inner_get)  # type: ignore
        else:
            return _default

    def __getitem__(self, item: K) -> V:
        return self.interpretation_function(item, self.wrapped_source[item])

    def __enter__(self) -> "KeyValueSource[K,V]":
        self.wrapped_source.__enter__()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return self.wrapped_source.__exit__(exc_type, exc_value, traceback)


_CHAR_KEY_VALUE_SOURCE_SPECIAL_VALUES = {
    "zip": "_ZipCharFileKeyValuesSource",
    "file-map": "_PathMappingCharKeyValueSource",
}

_BYTE_KEY_VALUE_SOURCE_SPECIAL_VALUES = {
    "zip": "_ZipBytesFileKeyValuesSource",
    "file-map": "_PathMappingBytesKeyValueSource",
}


def _doc_id_source_from_params(params: Parameters) -> KeyValueSource[str, str]:
    return KeyValueSource.from_doc_id_to_file_map(params.existing_file("path"))


def _doc_id_binary_source_from_params(params: Parameters) -> KeyValueSource[str, bytes]:
    return KeyValueSource.binary_from_doc_id_to_file_map(params.existing_file("path"))


def char_key_value_linear_source_from_params(
    params: Parameters,
    *,
    input_namespace: str = "input",
    eval_context: Optional[Mapping[Any, Any]] = None,
) -> KeyValueLinearSource[str, str]:
    """
    Get a key-value source based on parameters.

    This should be passed a parameter namespace.  If the "type" field is present, it should
    be the name of a class or method.  If a class, its static `from_parameters` method will be
    called with these parameters and should return a `KeyValueLinearSource[str, str]`. If a
    callable, it will be called with these parameters (and should also return a
    KeyValueLinearSource[str, str].

    The type 'zip' is a shortcut for a key-value zip file.  'file-map' is a shortcut for a
    docID to file map.

    If additional imports are needed to resolve 'type', they can be specified as a Python
    list in
    the `import` field.

    If no type is specified, a source will be constructed from the doc-id-to-file map specified
    by the `docIdToFileMap` parameter.

    This differs from "char_key_value_source_from_params" only in that is relaxes the guarantee
    on what is returned to only requiring iterability over mappings and not random access.
    """
    # to be sure the default special values can be evaluated, we want to include this module
    # itself in the evaluation context. We combine it with eval_context, giving priority to
    # the context specified by the user
    effective_context = dict(globals())
    effective_context.update(eval_context or {})
    return params.object_from_parameters(
        input_namespace,
        KeyValueLinearSource,
        special_factories=_CHAR_KEY_VALUE_SOURCE_SPECIAL_VALUES,
        default_factory=_doc_id_source_from_params,
        context=effective_context,
        factory_namespace_param_name="type",
    )


def byte_key_value_linear_source_from_params(
    params: Parameters,
    *,
    input_namespace: str = "input",
    eval_context: Optional[Dict] = None,
) -> KeyValueLinearSource[str, bytes]:
    """
    Get a key-value source based on parameters.

    This should be passed a parameter namespace.  If the "type" field is present, it should
    be the name of a class or method.  If a class, its static `from_parameters` method will be
    called with these parameters and should return a `KeyValueLinearSource[str, bytes]`. If a
    callable, it will be called with these parameters (and should also return a
    KeyValueLinearSource[str, bytes]).

    The type 'zip' is a shortcut for a key-value zip file.  'file-map' is a shortcut for a
    docID to file map.

    If additional imports are needed to resolve 'type', they can be specified as a Python
    list in
    the `import` field.

    If no type is specified, a source will be constructed from the doc-id-to-file map specified
    by the `docIdToFileMap` parameter.

    This differs from "byte_key_value_source_from_params" only in that is relaxes the guarantee
    on what is returned to only requiring iterability over mappings and not random access.
    """
    # to be sure the default special values can be evaluated, we want to include this module
    # itself in the evaluation context. We combine it with eval_context, giving priority to
    # the context specified by the user
    effective_context = dict(globals())
    effective_context.update(eval_context or {})
    return params.object_from_parameters(
        input_namespace,
        KeyValueLinearSource,
        special_factories=_BYTE_KEY_VALUE_SOURCE_SPECIAL_VALUES,
        default_factory=_doc_id_binary_source_from_params,
        context=effective_context,
        factory_namespace_param_name="type",
    )


def char_key_value_source_from_params(
    params: Parameters,
    *,
    input_namespace: str = "input",
    eval_context: Optional[Dict] = None,
) -> KeyValueSource[str, str]:
    """
    Get a random-access key-value source based on parameters.

    This should be passed a parameter namespace.  If the "type" field is present, it should
    be the name of a class or method.  If a class, its static `from_parameters` method will be
    called with these parameters and should return a `KeyValueSource[str, str]`. If a callable,
    it will be called with these parameters (and should also return a KeyValueSource[str, str].

    The type 'zip' is a shortcut for a key-value zip file.  'file-map' is a shortcut for a
    docID to file map.

    If additional imports are needed to resolve 'type', they can be specified as a Python
    list in
    the `import` field.

    If no type is specified, a source will be constructed from the doc-id-to-file map specified
    by the `docIdToFileMap` parameter.
    """
    # to be sure the default special values can be evaluated, we want to include this module
    # itself in the evaluation context. We combine it with eval_context, giving priority to
    # the context specified by the user
    effective_context = dict(globals())
    effective_context.update(eval_context or {})
    return params.object_from_parameters(  # type: ignore
        input_namespace,
        KeyValueSource,
        special_factories=_CHAR_KEY_VALUE_SOURCE_SPECIAL_VALUES,
        default_factory=_doc_id_source_from_params,
        context=effective_context,
        factory_namespace_param_name="type",
    )


def byte_key_value_source_from_params(
    params: Parameters,
    *,
    input_namespace: str = "input",
    eval_context: Optional[Dict] = None,
) -> KeyValueSource[str, bytes]:
    """
    Get a random-access key-value source based on parameters.

    This should be passed a parameter namespace.  If the "type" field is present, it should
    be the name of a class or method.  If a class, its static `from_parameters` method will be
    called with these parameters and should return a `KeyValueSource[str, bytes]`. If a callable,
    it will be called with these parameters (and should also return a KeyValueSource[str, bytes].

    The type 'zip' is a shortcut for a key-value zip file.  'file-map' is a shortcut for a
    docID to file map.

    If additional imports are needed to resolve 'type', they can be specified as a Python
    list in
    the `import` field.

    If no type is specified, a source will be constructed from the doc-id-to-file map specified
    by the `docIdToFileMap` parameter.
    """
    # to be sure the default special values can be evaluated, we want to include this module
    # itself in the evaluation context. We combine it with eval_context, giving priority to
    # the context specified by the user
    effective_context = dict(globals())
    effective_context.update(eval_context or {})
    return params.object_from_parameters(  # type: ignore
        input_namespace,
        KeyValueSource,
        special_factories=_BYTE_KEY_VALUE_SOURCE_SPECIAL_VALUES,
        default_factory=_doc_id_source_from_params,
        context=effective_context,
        factory_namespace_param_name="type",
    )


_CHAR_KEY_VALUE_SINK_SPECIAL_VALUES = {
    "zip": "_ZipCharFileKeyValueSink",
    "file-map": "_DirectoryCharKeyValueSink",
}

_BYTE_KEY_VALUE_SINK_SPECIAL_VALUES = {
    "zip": "_ZipBytesFileKeyValueSink",
    "file-map": "_DirectoryBytesKeyValueSink",
}


def char_key_value_sink_from_params(
    params: Parameters,
    *,
    output_namespace: str = "output",
    eval_context: Optional[Dict] = None,
) -> KeyValueSink[str, str]:
    """
    Get a key-value sink based on parameters.

    This should be passed a parameter namespace.  If the "type" field is present, it should
    be the name of a class or method.  If a class, its static `from_parameters` method will be
    called with these parameters and should return a `KeyValueSink[str, str]`. If a callable,
    it will be called with these parameters (and should also return a KeyValueSink[str, str].

    The type 'zip' is a shortcut for a key-value zip file.  'directory' is a shortcut for
    writing the output files to the specified directory.

    If additional imports are needed to resolve 'type', they can be specified as a Python list in
    the `import` field.

    If no type is specified, a 'directory' sink will be created.
    """
    # to be sure the default special values can be evaluated, we want to include this module
    # itself in the evaluation context. We combine it with eval_context, giving priority to
    # the context specified by the user
    effective_context = dict(globals())
    effective_context.update(eval_context or {})
    return params.object_from_parameters(  # type: ignore
        output_namespace,
        KeyValueSink,
        special_factories=_CHAR_KEY_VALUE_SINK_SPECIAL_VALUES,
        default_factory=_DirectoryCharKeyValueSink,
        context=effective_context,
        factory_namespace_param_name="type",
    )


def byte_key_value_sink_from_params(
    params: Parameters,
    *,
    output_namespace: str = "output",
    eval_context: Optional[Dict] = None,
) -> KeyValueSink[str, bytes]:
    """
    Get a binary key-value sink based on parameters.

    This should be passed a parameter namespace.  If the "type" field is present, it should
    be the name of a class or method.  If a class, its static `from_parameters` method will be
    called with these parameters and should return a `KeyValueSink[str, bytes]`. If a callable,
    it will be called with these parameters (and should also return a KeyValueSink[str, bytes].

    The type 'zip' is a shortcut for a key-value zip file.  'directory' is a shortcut for
    writing the output files to the specified directory.

    If additional imports are needed to resolve 'type', they can be specified as a Python list in
    the `import` field.

    If no type is specified, a 'directory' sink will be created.
    """
    # to be sure the default special values can be evaluated, we want to include this module
    # itself in the evaluation context. We combine it with eval_context, giving priority to
    # the context specified by the user
    effective_context = dict(globals())
    effective_context.update(eval_context or {})
    return params.object_from_parameters(  # type: ignore
        output_namespace,
        KeyValueSink,
        special_factories=_BYTE_KEY_VALUE_SINK_SPECIAL_VALUES,
        default_factory=_DirectoryBytesKeyValueSink,
        context=effective_context,
        factory_namespace_param_name="type",
    )
