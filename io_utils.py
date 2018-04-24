import gzip
import io
import os
import types
from abc import abstractmethod, ABCMeta
from io import BytesIO
from pathlib import Path
from types import TracebackType
from typing import TextIO, AnyStr, Iterable, Optional, Iterator, Type, List, BinaryIO, Any, \
    Mapping, Tuple, Union
from zipfile import ZipFile

from attr import attrs

from flexnlp.utils.attrutils import attrib_instance_of
from flexnlp.utils.immutablecollections import ImmutableDict
from flexnlp.utils.misc_utils import pathify


def is_empty_directory(path: Path) -> bool:
    """
    Returns if path is a directory with no content.
    """
    sentinel = object()
    return path.is_dir() and next(path.iterdir().__iter__(), sentinel) == sentinel


class CharSource(metaclass=ABCMeta):
    """
    Something which can provide string data.

    This abstracts over whether the string data is coming from a filesystem path, a database,
    a compressed file, etc.  This should be viewed as more analogous to a `Path` object than
    to a file.

    You can get a file-like object from this by using `open` with a context manager.

    This is inspired by Guava's `CharSource`
    """

    @abstractmethod
    def open(self) -> TextIO:
        """
        Get a file-like object which reads from this CharSource.

        You should typically use this with a context manager.

        Note that if you `read` twice, the second `read` will usually (not guaranteed) return the
        same thing as the first.  If you wish to read incrementally, use `open`.
        """
        raise NotImplementedError()

    def read_all(self) -> str:
        """
        Get the entire string which can be extacted from this source.
        """
        with self.open() as file_like:
            return file_like.read()

    def readlines(self) -> List[str]:
        """
        Get the entire string which can be extracted from this source as a list of lines.

        Lines are always broken on `\n` and line endings are not removed.
        """
        with self.open() as file_like:
            return [line.rstrip('\n') for line in file_like]

    def is_empty(self) -> bool:
        """
        Gets whether this source has a non-empty string to provide.
        """
        raise NotImplementedError()

    @staticmethod
    def from_nowhere() -> 'CharSource':
        """
        An empty source.
        """
        return _StringCharSource("")

    @staticmethod
    def from_string(s: str) -> 'CharSource':
        """
        Get a source whose content is the given string.
        """
        return _StringCharSource(s)

    @staticmethod
    def from_file(p: Union[str, Path]) -> 'CharSource':
        """
        Get a source whose content is that of the given file.

        The file will be interpreted as UTF-8.
        """
        return _FileCharSource(pathify(p))

    @staticmethod
    def from_gzipped_file(p: Path, encoding: str = 'utf-8') -> 'CharSource':
        """
        Get a source whose content is the uncompressed content of the given file.

        Args:
            p: path to the file whose uncompressed content should be exposed
            encoding: the encoded of the uncompressed data. Defaults to UTF-8
        """
        return _GZipFileSource(p, encoding)


@attrs(slots=True, frozen=True)
class _StringCharSource(CharSource):
    _string = attrib_instance_of(str)

    def open(self) -> TextIO:
        return io.StringIO(self._string)

    def is_empty(self) -> bool:
        return not self._string


@attrs(slots=True, frozen=True)
class _FileCharSource(CharSource):
    _path = attrib_instance_of(Path)

    def open(self) -> TextIO:
        return open(self._path, 'r')

    def is_empty(self) -> bool:
        return os.path.getsize(self._path) == 0


@attrs(slots=True, frozen=True)
class _GZipFileSource(CharSource):
    _path: Path = attrib_instance_of(Path)
    _encoding: str = attrib_instance_of(str)

    def open(self) -> TextIO:
        return gzip.open(self._path, 'rt', encoding=self._encoding)  # type: ignore

    def is_empty(self) -> bool:
        with gzip.open(self._path) as inp:
            data = inp.read(1)
        return len(data) == 0


class CharSink(metaclass=ABCMeta):
    """
    Something which can accept string data.

    This abstracts over whether the string data is being written to a filesystem path,
    a database, a compressed file, nowhere, etc.  This should be viewed as more analogous to a
    `Path` object than to a file.

    You can get a file-like object from this by using `open` with a context manager.

    This is inspired by Guava's `CharSink`.
    """

    @abstractmethod
    def open(self) -> TextIO:
        """
        Get a file-like object which write to this sink.

        You should typically use this with a context manager
        """
        raise NotImplementedError()

    @staticmethod
    def to_nowhere() -> 'CharSink':
        """
        Get a sink which ignores its input.
        """
        return _NullCharSink()

    @staticmethod
    def to_file(p: Path) -> 'CharSink':
        """
        Get a sink which writes to the given path.

        UTF-8 encoding will be used.
        """
        return _FileCharSink(p)

    @staticmethod
    def to_string() -> 'StringCharSink':
        """
        Gets a sink which writes to a string buffer.

        See 'StringCharSink' for how to retrieve what has been written.
        """
        return StringCharSink()

    def write(self, data: str) -> None:
        """
        Write the given data to the sink.

        Note that if you `write` twice, the second `write` will overwrite the first.  If you wish
        to write incrementally, use `open`.
        """
        with self.open() as out:
            out.write(data)


class ByteSink(metaclass=ABCMeta):
    """
    Something which can accept binary data.

    This abstracts over whether the binary data is being written to a filesystem path,
    a database, a compressed file, nowhere, etc.  This should be viewed as more analogous to a
    `Path` object than to a file.

    You can get a file-like object from this by using `open` with a context manager.

    This is inspired by Guava's `ByteSink`.
    """
    @abstractmethod
    def open(self) -> BytesIO:
        raise NotImplementedError()

    @staticmethod
    def file_in_zip(zip_file: Path, filename_in_zip: str) -> 'ByteSink':
        """
        Get a sink which writes to the given path in a zip file.
        """
        return _FileInZipByteSink(zip_file, filename_in_zip)

    def write(self, data: bytes) -> None:
        """
        Write the given data to the sink.

        Note that if you `write` twice, the second `write` will overwrite the first.  If you
        wish
        to write incrementally, use `open`.
        """
        with self.open() as out:
            out.write(data)


@attrs(slots=True, frozen=True)
class _NullCharSink(CharSink):
    """
    A `CharSink` which throws away anything sent to it.
    """

    def open(self) -> TextIO:
        return _NullCharSink.NullFileLike()

    class NullFileLike(TextIO):
        def __enter__(self) -> TextIO:
            return self

        def name(self):
            return 'NullCharSink'

        def mode(self):
            return 'w'

        def closed(self):
            return False

        def buffer(self) -> BinaryIO:
            raise NotImplementedError("This isn't supposed to be part of the TextIO API"
                                      " but the type-checker requires it")

        def encoding(self) -> str:
            return 'utf-8'

        def errors(self) -> Optional[str]:
            return None

        def line_buffering(self) -> bool:
            return False

        def newlines(self) -> Any:
            return '\n'

        def close(self) -> None:
            pass

        def fileno(self) -> int:
            pass

        def flush(self) -> None:
            pass

        def isatty(self) -> bool:
            return False

        def read(self, n: int = 0) -> AnyStr:
            raise NotImplementedError("Null char sink is write-only")

        def readable(self) -> bool:
            raise NotImplementedError("Null char sink is write-only")

        def readline(self, limit: int = 0) -> AnyStr:
            raise NotImplementedError("Null char sink is write-only")

        def readlines(self, hint: int = 0) -> List[AnyStr]:
            raise NotImplementedError("Null char sink is write-only")

        def seek(self, offset: int, whence: int = 0) -> int:
            raise NotImplementedError("Null char sink is write-only")

        def seekable(self) -> bool:
            return False

        def tell(self) -> int:
            pass

        def truncate(self, size: Optional[int] = 0) -> int:
            raise NotImplementedError("Cannot truncate null char sink")

        def writable(self) -> bool:
            return True

        def write(self, s: AnyStr) -> int:
            pass

        def writelines(self, lines: Iterable[AnyStr]) -> None:
            pass

        def __next__(self) -> AnyStr:
            raise NotImplementedError("Null char sink is write-only")

        def __iter__(self) -> Iterator[AnyStr]:
            raise NotImplementedError("Null char sink is write-only")

        def __exit__(self, t: Optional[Type[BaseException]], value: Optional[BaseException],
                     traceback: Optional[TracebackType]) -> bool:
            pass


class StringCharSink(CharSink):
    """
    A sink which writes to a string buffer.

    The last string written can be recovered from the 'last_string_written' field.
    """
    def __init__(self):
        self.last_string_written = None

    def open(self) -> TextIO:
        outer_self = self

        class StringFileLike(io.StringIO):
            def __exit__(self, exc_type, exc_val, exc_tb):
                outer_self.last_string_written = self.getvalue()
                super().__exit__(exc_type, exc_val, exc_tb)

        return StringFileLike()


@attrs(slots=True, frozen=True)
class _FileCharSink(CharSink):
    _path = attrib_instance_of(Path)

    def open(self) -> TextIO:
        return open(self._path, 'w')


@attrs(slots=True, frozen=True)
class _FileInZipByteSink(ByteSink):
    _zip_path = attrib_instance_of(Path)
    _path_within_zip = attrib_instance_of(str)

    def open(self) -> BytesIO:
        # pylint:disable=not-callable
        # pylint:disable=unused-argument
        zip_file = ZipFile(self._zip_path, 'a')
        ret = zip_file.open(self._path_within_zip, 'w')
        # we need to fiddle with the close method on the returned BytesIO so that when it is
        # closed the containing zip file is closed as well
        old_close = ret.close

        def new_close(self):
            old_close()
            zip_file.close()

        ret.close = types.MethodType(new_close, ret)  # type: ignore
        return ret  # type: ignore


def write_doc_id_to_file_map(doc_id_to_file_map: Mapping[str, Path],
                             sink: CharSink) -> None:
    """
    Writes a tab-separated docID-to-file-map to the specified sink.
    """
    with sink.open() as out:
        for doc_id in sorted(doc_id_to_file_map.keys()):
            out.write("{!s}\t{!s}\n".format(
                doc_id, doc_id_to_file_map[doc_id].absolute()))


def read_doc_id_to_file_map(source: CharSource) -> Mapping[str, Path]:
    """
    Read a tab-separate docID-to-file map from the specified source.
    """
    items: List[Tuple[str, Path]] = []
    with source.open() as inp:
        for (line_num, line) in enumerate(inp):
            if line:
                parts = line.split('\t')
                if len(parts) == 2:
                    items.append((parts[0].strip(), Path(parts[1].strip())))
                else:
                    raise IOError("Bad docID to file map line {!s}: {!s}".format(
                        line_num, line))
    return ImmutableDict.of(items)
