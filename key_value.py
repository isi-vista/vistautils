from abc import abstractmethod, ABCMeta
from pathlib import Path
from typing import Generic, TypeVar, Callable, Optional, AbstractSet, Set
from zipfile import ZipFile

from flexnlp.utils.immutablecollections import ImmutableSet
from flexnlp.utils.preconditions import check_state, check_arg, check_not_none

K = TypeVar('K')
V = TypeVar('V')


def _identity(x: str) -> str:
    return x


# the following two methods supply the default way of tracking keys in zip-backed stores
def _read_keys_from_keys_file(zip_file: ZipFile) -> Optional[AbstractSet[str]]:
    try:
        keys_data = zip_file.read('__keys')
        return ImmutableSet.of(keys_data.decode('utf-8').split('\n'))
    except KeyError:
        return None


def _write_keys_to_keys_file(zip_file: ZipFile, keys: AbstractSet[str]) -> None:
    zip_file.writestr('__keys', '\n'.join(keys).encode('utf-8'))


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

    @abstractmethod
    def __enter__(self) -> 'KeyValueSink[K,V]':
        raise NotImplementedError()

    @abstractmethod
    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        raise NotImplementedError()

    @staticmethod
    def zip_character_sink(path: Path, *,
                           filename_function: Callable[[str], str] = _identity,
                           overwrite: bool = True,
                           keys_in_function: Callable[[ZipFile], Optional[AbstractSet[str]]] =
                           _read_keys_from_keys_file,
                           keys_out_function: Callable[[ZipFile, AbstractSet[str]], None] =
                           _write_keys_to_keys_file) -> 'KeyValueSink[str, str]':
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
        return _ZipCharFileKeyValuesSink(path, filename_function=filename_function,
                                         overwrite=overwrite,
                                         keys_in_function=keys_in_function,
                                         keys_out_function=keys_out_function)

    @staticmethod
    def zip_bytes_sink(path: Path,
                       *,
                       filename_function: Callable[[str], str] = _identity,
                       overwrite: bool = True,
                       keys_in_function: Callable[[ZipFile], Optional[AbstractSet[str]]] =
                       _read_keys_from_keys_file,
                       keys_out_function: Callable[[ZipFile, AbstractSet[str]], None] =
                       _write_keys_to_keys_file) -> 'KeyValueSink[str, bytes]':
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
        return _ZipBytesFileKeyValuesSink(path, filename_function=filename_function,
                                          overwrite=overwrite,
                                          keys_in_function=keys_in_function,
                                          keys_out_function=keys_out_function)


class KeyValueSource(Generic[K, V], metaclass=ABCMeta):
    """
    Anything which can accept key-value pairs.

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
    def get(self, key: K) -> Optional[V]:
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

    @abstractmethod
    def __enter__(self) -> 'KeyValueSource[K,V]':
        raise NotImplementedError()

    @abstractmethod
    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        raise NotImplementedError()

    @staticmethod
    def zip_character_source(path: Path, filename_function: Callable[[str], str] = _identity,
                             keys_function: Callable[[ZipFile], AbstractSet[str]] =
                             _read_keys_from_keys_file) -> 'KeyValueSource[str, str]':
        """
        A key-value source backed by a zip file which stores character data.

        `file_namefunction` provides the mapping from keys to relative path names within
        the zip file.

        By default, the set of `keys()` is available if there is  a special file inside the root of
        the zip called `__keys`, where they should be listed, one per line. If his file is absent,
        `keys()` returns `None`.  You may specify an alternative to this behavior by setting
        `keys_function`.
        """
        return _ZipCharFileKeyValuesSource(path, filename_function=filename_function,
                                           keys_function=keys_function)

    @staticmethod
    def zip_bytes_source(path: Path, filename_function: Callable[[str], str] = _identity,
                         keys_function: Callable[[ZipFile], AbstractSet[str]] =
                         _read_keys_from_keys_file) -> 'KeyValueSource[str, bytes]':
        """
        A key-value source backed by a zip file which stores character data.

        `file_namefunction` provides the mapping from keys to relative path names within
        the zip file.

        By default, the set of `keys()` is available if there is  a special file inside the root of
        the zip called `__keys`, where they should be listed, one per line. If his file is absent,
        `keys()` returns `None`.  You may specify an alternative to this behavior by setting
        `keys_function`.
        """
        return _ZipBytesFileKeyValuesSource(path, filename_function=filename_function,
                                            keys_function=keys_function)


class _ZipKeyValueSink(Generic[V], KeyValueSink[str, V]):
    def __init__(self, path: Path, *,
                 filename_function: Callable[[str], str] = _identity,
                 keys_in_function: Callable[[ZipFile], Optional[AbstractSet[str]]] = None,
                 keys_out_function: Callable[[ZipFile, AbstractSet[str]], None] = None,
                 overwrite: bool = True) -> None:
        self._path = path
        self._zip_file: ZipFile = None
        self._filename_function = filename_function
        self._overwrite = overwrite
        self._keys_in_function = keys_in_function
        self._keys_out_function = keys_out_function
        self._keys: Set[str] = set()
        check_arg(self._keys_out_function or not self._keys_in_function,
                  "If you specify a key output function, you should also specify a key input"
                  " function")

    def put(self, key: str, value: V) -> None:
        check_state(self._zip_file, 'Must use zip key-value sink as a context manager')
        check_not_none(key)
        check_not_none(value)
        if key in self._keys:
            raise ValueError("Zip-backed key-value sinks do not support duplicate puts on the "
                             "same key")
        self._keys.add(key)
        filename = self._filename_function(key)
        check_arg(isinstance(value, str) or isinstance(value, bytes))
        self._zip_file.writestr(filename, value)  # type: ignore

    @abstractmethod
    def _to_bytes(self, val: V) -> bytes:
        raise NotImplementedError()

    def __enter__(self) -> 'KeyValueSink[str, V]':
        self._zip_file = ZipFile(str(self._path), 'w' if self._overwrite else 'a')
        if self._keys_in_function:
            # update rather than assignment because return might not be mutable
            existing_keys = self._keys_in_function(self._zip_file)
            if existing_keys:
                self._keys.update(existing_keys)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        if self._keys_out_function:
            self._keys_out_function(self._zip_file, self._keys)
        self._zip_file.close()


class _ZipCharFileKeyValuesSink(_ZipKeyValueSink[str]):
    def _to_bytes(self, val: str) -> bytes:
        return val.encode('utf-8')


class _ZipBytesFileKeyValuesSink(_ZipKeyValueSink[bytes]):
    def _to_bytes(self, val: bytes) -> bytes:
        return val


class _ZipFileKeyValueSource(Generic[V], KeyValueSource[str, V], metaclass=ABCMeta):
    def __init__(self, path: Path,
                 filename_function: Callable[[str], str] = _identity,
                 keys_function: Callable[[ZipFile], Optional[AbstractSet[str]]] = None) -> None:
        self.path = path
        self._filename_function = filename_function
        self._keys_function = keys_function
        self._zip_file: ZipFile = None
        self._keys: Optional[AbstractSet[str]] = None

    def keys(self) -> Optional[AbstractSet[str]]:
        check_state(self._zip_file, 'Must use zip key-value source as a context manager')
        return self._keys

    def get(self, key: str) -> Optional[V]:
        check_state(self._zip_file, 'Must use zip key-value source as a context manager')
        check_not_none(key)
        filename = self._filename_function(key)
        try:
            zip_bytes = self._zip_file.read(filename)
        except KeyError:
            return None
        return self._process_bytes(zip_bytes)

    @abstractmethod
    def _process_bytes(self, _bytes: bytes) -> V:
        raise NotImplementedError()

    def __enter__(self) -> 'KeyValueSource[str, V]':
        self._zip_file = ZipFile(str(self.path), 'r')
        if self._keys_function:
            self._keys = self._keys_function(self._zip_file)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self._zip_file.close()
        self._zip_file = None


class _ZipBytesFileKeyValuesSource(_ZipFileKeyValueSource[bytes]):
    def __init__(self, path: Path, *,
                 filename_function: Callable[[str], str] = _identity,
                 keys_function: Callable[[ZipFile], AbstractSet[str]] = None) -> None:
        super().__init__(path, filename_function, keys_function)

    def _process_bytes(self, _bytes: bytes) -> bytes:
        return _bytes


class _ZipCharFileKeyValuesSource(_ZipFileKeyValueSource[str]):
    def __init__(self, path: Path, *,
                 filename_function: Callable[[str], str] = _identity,
                 keys_function: Callable[[ZipFile], AbstractSet[str]] = None) -> None:
        super().__init__(path, filename_function, keys_function)

    def _process_bytes(self, _bytes: bytes) -> str:
        return _bytes.decode('utf-8')
