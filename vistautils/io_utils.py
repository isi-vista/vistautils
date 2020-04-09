import gzip
import io
import os
import tarfile
import types
from abc import ABCMeta, abstractmethod
from io import BytesIO
from pathlib import Path
from types import TracebackType
from typing import (
    Any,
    AnyStr,
    BinaryIO,
    Callable,
    Iterable,
    Iterator,
    List,
    Mapping,
    Optional,
    TextIO,
    Tuple,
    Type,
    Union,
    cast,
)
from zipfile import ZipFile

from attr import attrib, attrs, validators

from immutablecollections import ImmutableDict, ImmutableSet, immutableset

from vistautils.misc_utils import pathify


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
            return [line.rstrip("\n") for line in file_like]

    def is_empty(self) -> bool:
        """
        Gets whether this source has a non-empty string to provide.
        """
        with self.open() as inp:
            return inp.read(1) == ""

    @staticmethod
    def from_nowhere() -> "CharSource":
        """
        An empty source.
        """
        return _StringCharSource("")

    @staticmethod
    def from_string(s: str) -> "CharSource":
        """
        Get a source whose content is the given string.
        """
        return _StringCharSource(s)

    @staticmethod
    def from_byte_source(
        wrapped_source: "ByteSource", *, encoding="utf-8"
    ) -> "CharSource":
        """
        Gets a source for a ``ByteSource`` decoded according to the given encoding.

        The default encoding is UTF-8.
        """
        return _CharSourceWrappingByteSource(wrapped_source, encoding)

    @staticmethod
    def from_file(p: Union[str, Path]) -> "CharSource":
        """
        Get a source whose content is that of the given file.

        The file will be interpreted as UTF-8.
        """
        return _FileCharSource(pathify(p))

    @staticmethod
    def from_gzipped_file(p: Path, encoding: str = "utf-8") -> "CharSource":
        """
        Get a source whose content is the uncompressed content of the given file.

        Args:
            p: path to the file whose uncompressed content should be exposed
            encoding: the encoded of the uncompressed data. Defaults to UTF-8
        """
        return _GZipFileSource(p, encoding)

    @staticmethod
    def from_file_in_tgz(
        tgz_path: Path, path_within_tgz: str, encoding: str = "utf-8"
    ) -> "CharSource":
        """
        Gets a source whose content is that of the file at the given path within a .tar.gz file.

        Note that because .tar.gz files don't support random access, using this can be slow. In
        particular, avoid using this in a loop.
        """
        return _FileWithinTgzCharSource(tgz_path, path_within_tgz, encoding)

    @staticmethod
    def from_file_in_zip(
        zip_file: Union[Path, ZipFile], path_within_zip: str
    ) -> "CharSource":
        """
        Gets a source whose content is that of the file at the given path within a .zip file.

        The `zip_file` can be specified either as a ``Path`` or a ``ZipFile`` object.
        If the latter, this ``CharSource`` is only valid as long as that ``ZipFile``
        remains open.

        The file will be interpreted as UTF-8 text.
        """
        return CharSource.from_byte_source(
            ByteSource.from_file_in_zip(zip_file, path_within_zip)
        )


@attrs(slots=True, frozen=True, repr=False)
class _StringCharSource(CharSource):
    _string = attrib(validator=validators.instance_of(str))

    def open(self) -> TextIO:
        return io.StringIO(self._string)

    def is_empty(self) -> bool:
        return not self._string

    def __repr__(self) -> str:
        if len(self._string) > 100:
            s = self._string[:100] + "..."
        else:
            s = self._string
        return f"_StringCharSource({s})"


@attrs(slots=True, frozen=True)
class _FileCharSource(CharSource):
    _path = attrib(validator=validators.instance_of(Path))

    def open(self) -> TextIO:
        return open(self._path, "r", encoding="utf-8")

    def is_empty(self) -> bool:
        return os.path.getsize(self._path) == 0


@attrs(slots=True, frozen=True, auto_attribs=True)
class _CharSourceWrappingByteSource(CharSource):
    _wrapped_source: "ByteSource"
    _encoding: str

    def open(self) -> TextIO:
        return io.TextIOWrapper(self._wrapped_source.open(), encoding=self._encoding)


@attrs(slots=True, frozen=True)
class _GZipFileSource(CharSource):
    _path: Path = attrib(validator=validators.instance_of(Path))
    _encoding: str = attrib(validator=validators.instance_of(str))

    def open(self) -> TextIO:
        return gzip.open(self._path, "rt", encoding=self._encoding)  # type: ignore

    def is_empty(self) -> bool:
        with gzip.open(self._path) as inp:
            data = inp.read(1)
        return len(data) == 0


@attrs(slots=True, frozen=True)
class _FileWithinTgzCharSource(CharSource):
    _tgz_path: Path = attrib(validator=validators.instance_of(Path))
    _path_within_tgz: str = attrib(validator=validators.instance_of(str))
    _encoding: str = attrib(validator=validators.instance_of(str))

    def open(self) -> TextIO:
        tgz_file = tarfile.open(self._tgz_path, "r:gz", encoding=self._encoding)
        # extractfile here returns  binary file object. We are lazy here and load it all into
        # memory to make dealing with the encoding issues simple
        tgz_data = tgz_file.extractfile(self._path_within_tgz)
        if tgz_data is not None:
            ret = CharSource.from_string(tgz_data.read().decode(self._encoding)).open()
            # we need to fiddle with the close method on the returned TextIO so that when it is
            # closed the containing zip file is closed as well
            old_close: Callable = ret.close
        else:
            raise IOError(
                f"Could not extract path {self._path_within_tgz} from {self._tgz_path}"
            )

        def new_close(_):
            old_close()  # pylint:disable=not-callable
            tgz_file.close()

        ret.close = types.MethodType(new_close, ret)  # type: ignore
        return ret

    def is_empty(self) -> bool:
        tgz_file = tarfile.open(self._tgz_path, "r:gz", encoding=self._encoding)
        return tgz_file.getmember(self._path_within_tgz).size == 0


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
    def to_nowhere() -> "CharSink":
        """
        Get a sink which ignores its input.
        """
        return _NullCharSink()

    @staticmethod
    def to_file(p: Union[Path, str]) -> "CharSink":
        """
        Get a sink which writes to the given path.

        UTF-8 encoding will be used.
        """
        if isinstance(p, str):
            p = Path(p)
        if p.parent:
            p.parent.mkdir(parents=True, exist_ok=True)
        return _FileCharSink(p)

    @staticmethod
    def to_string() -> "StringCharSink":
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


class ByteSource(metaclass=ABCMeta):
    """
    Something which can provide byte data.

    This abstracts over whether the byte data is coming from a filesystem path, a database,
    a compressed file, etc.  This should be viewed as more analogous to a `Path` object than
    to a file.
    """

    @abstractmethod
    def open(self) -> BinaryIO:
        """
        Get a file-like object which reads from this ByteSource.
        """
        raise NotImplementedError()

    def read(self, size=-1) -> bytes:
        """
        Read and return data from the stream.

        If size is specified, at most size bytes will be read
        """
        with self.open() as binary_like:
            return binary_like.read(size)

    @staticmethod
    def from_file(p: Path) -> "ByteSource":
        """
        Get a source whose content is that of the given file.
        """
        return _FileByteSource(p)

    @staticmethod
    def from_file_in_zip(
        zip_file: Union[Path, ZipFile], path_within_zip: str
    ) -> "ByteSource":
        """
        Gets a source whose content is that of the file at the given path within a .zip file

        The `zip_file` can be specified either as a ``Path`` or a ``ZipFile`` object.
        If the latter, this ``ByteSource`` is only valid as long as that ``ZipFile``
        remains open.
        """
        if isinstance(zip_file, ZipFile):
            return _ByteSourceFromPathInOpenZipFile(zip_file, path_within_zip)
        else:
            return _ByteSourceFromPathInZipFile(zip_file, path_within_zip)


@attrs(slots=True, frozen=True)
class _FileByteSource(ByteSource):
    _path = attrib(validator=validators.instance_of(Path))

    def open(self) -> BinaryIO:
        return open(self._path, "rb")

    def is_empty(self) -> bool:
        return os.path.getsize(self._path) == 0


@attrs(slots=True, frozen=True)
class _ByteSourceFromPathInZipFile(ByteSource):
    _zip_path = attrib(validator=validators.instance_of(Path))
    _path_within_zip = attrib(validator=validators.instance_of(str))

    def open(self) -> BytesIO:
        # pylint:disable=not-callable
        # pylint:disable=unused-argument
        zip_file = ZipFile(self._zip_path, "r")
        ret = zip_file.open(self._path_within_zip, "r")
        # we need to fiddle with the close method on the returned BytesIO so that when it is
        # closed the containing zip file is closed as well
        old_close = ret.close

        def new_close(self):
            old_close()
            zip_file.close()

        ret.close = types.MethodType(new_close, ret)  # type: ignore
        return ret  # type: ignore


@attrs(slots=True, frozen=True)
class _ByteSourceFromPathInOpenZipFile(ByteSource):
    _zip_file = attrib(validator=validators.instance_of(ZipFile))
    _path_within_zip = attrib(validator=validators.instance_of(str))

    # mypy freaks out with this open function
    def open(self) -> BytesIO:  # type: ignore
        return self._zip_file.open(self._path_within_zip, "r")  # type: ignore


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
    def open(self) -> BinaryIO:
        raise NotImplementedError()

    @staticmethod
    def file_in_zip(zip_file: Path, filename_in_zip: str) -> "ByteSink":
        """
        Get a sink which writes to the given path in a zip file.
        """
        return _FileInZipByteSink(zip_file, filename_in_zip)

    @staticmethod
    def to_buffer() -> "BufferByteSink":
        """
        Get a sink which writes to a buffer in memory.

        The last bytes written can be read using methods on `BufferByteSink`
        """
        return BufferByteSink()

    @staticmethod
    def to_file(path: Path) -> "ByteSink":
        """
        Get a sink which writes to the given file.
        """
        if path.parent:
            path.parent.mkdir(parents=True, exist_ok=True)
        return _FileByteSink(path)

    def write(self, data: bytes) -> None:
        """
        Write the given data to the sink.

        Note that if you `write` twice, the second `write` will overwrite the first.
        If you wish to write incrementally, use `open`.
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

        @property
        def name(self):
            return "NullCharSink"

        @property
        def mode(self):
            return "w"

        def closed(self):
            return False

        @property
        def buffer(self) -> BinaryIO:
            raise NotImplementedError(
                "This isn't supposed to be part of the TextIO API"
                " but the type-checker requires it"
            )

        @property
        def encoding(self) -> str:
            return "utf-8"

        @property
        def errors(self) -> Optional[str]:
            return None

        @property
        def line_buffering(self) -> bool:
            return False

        @property
        def newlines(self) -> Any:
            return "\n"

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

        def __exit__(
            self,
            t: Optional[Type[BaseException]],
            value: Optional[BaseException],
            traceback: Optional[TracebackType],
        ) -> bool:
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
    _path: Path = attrib(validator=validators.instance_of(Path))

    def open(self) -> TextIO:
        return cast(TextIO, self._path.open(mode="w", encoding="utf-8"))


@attrs(slots=True, frozen=True)
class _FileByteSink(ByteSink):
    _path: Path = attrib(validator=validators.instance_of(Path))

    def open(self) -> BinaryIO:
        return cast(BinaryIO, self._path.open(mode="wb"))


@attrs(slots=True, frozen=True)
class _FileInZipByteSink(ByteSink):
    _zip_path = attrib(validator=validators.instance_of(Path))
    _path_within_zip = attrib(validator=validators.instance_of(str))

    def open(self) -> BytesIO:
        # pylint:disable=not-callable
        # pylint:disable=unused-argument
        zip_file = ZipFile(self._zip_path, "a")
        ret = zip_file.open(self._path_within_zip, "w")
        # we need to fiddle with the close method on the returned BytesIO so that when it is
        # closed the containing zip file is closed as well
        old_close = ret.close

        def new_close(self):
            old_close()
            zip_file.close()

        ret.close = types.MethodType(new_close, ret)  # type: ignore
        return ret  # type: ignore


class BufferByteSink(ByteSink):
    """
    A sink which writes to a byte buffer.

    The last byte string written can be recovered from the 'last_bytes_written' field.
    """

    def __init__(self):
        self.last_bytes_written: bytes = None

    def open(self) -> BytesIO:
        outer_self = self

        class BytesFileLike(io.BytesIO):
            def __exit__(self, exc_type, exc_val, exc_tb):
                outer_self.last_bytes_written = self.getvalue()
                super().__exit__(exc_type, exc_val, exc_tb)

        return BytesFileLike()


def file_lines_to_set(file: Path) -> ImmutableSet[str]:
    """
    Gets a set consisting of all the lines in the specified file.

    The iteration order of the returned set will match the order of the items in the file.

    Any blank lines are omitted.
    """
    return immutableset(
        line for line in file.read_text(encoding="utf-8").split("\n") if line
    )


def write_doc_id_to_file_map(
    doc_id_to_file_map: Mapping[str, Path], sink: CharSink
) -> None:
    """
    Writes a tab-separated docID-to-file-map to the specified sink.
    """
    with sink.open() as out:
        for doc_id in sorted(doc_id_to_file_map.keys()):
            out.write(
                "{!s}\t{!s}\n".format(doc_id, doc_id_to_file_map[doc_id].absolute())
            )


def read_doc_id_to_file_map(source: CharSource) -> Mapping[str, Path]:
    """
    Read a tab-separate docID-to-file map from the specified source.
    """
    items: List[Tuple[str, Path]] = []
    with source.open() as inp:
        for (line_num, line) in enumerate(inp):
            if line:
                parts = line.split("\t")
                if len(parts) == 2:
                    items.append((parts[0].strip(), Path(parts[1].strip())))
                else:
                    raise IOError(
                        "Bad docID to file map line {!s}: {!s}".format(line_num, line)
                    )
    return ImmutableDict.of(items)
