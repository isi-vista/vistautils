import shutil
import tempfile
from pathlib import Path
from unittest import TestCase
from zipfile import ZipFile

from attr import attrs
from immutablecollections import ImmutableDict

from vistautils.attrutils import attrib_instance_of
from vistautils.io_utils import (
    ByteSink,
    CharSink,
    CharSource,
    read_doc_id_to_file_map,
    write_doc_id_to_file_map,
)
from vistautils.parameters import Parameters


class TestIOUtils(TestCase):
    def test_empty(self):
        empty = CharSource.from_nowhere()
        self.assertEqual("", empty.read_all())
        self.assertEqual([], empty.readlines())
        self.assertTrue(empty.is_empty())

    def test_wrap(self):
        wrapped = CharSource.from_string("Hello\nworld")
        self.assertEqual("Hello\nworld", wrapped.read_all())
        self.assertEqual(["Hello", "world"], wrapped.readlines())
        self.assertFalse(wrapped.is_empty())
        with wrapped.open() as inp:
            self.assertEqual("Hello\n", inp.readline())
            self.assertEqual("world", inp.readline())

    def test_from_file(self):
        source = CharSource.from_file(Path(__file__).parent / "char_source_test.txt")
        self.assertEqual("Hello\nworld\n", source.read_all())
        self.assertEqual(["Hello", "world"], source.readlines())
        self.assertFalse(source.is_empty())
        with source.open() as inp:
            self.assertEqual("Hello\n", inp.readline())
            self.assertEqual("world\n", inp.readline())

    def test_from_gzip_file(self):
        source = CharSource.from_gzipped_file(
            Path(__file__).parent / "gzip_char_source_test.txt.gz"
        )
        self.assertEqual("Hello\nworld\n", source.read_all())
        self.assertEqual(["Hello", "world"], source.readlines())
        with source.open() as inp:
            self.assertEqual("Hello\n", inp.readline())
            self.assertEqual("world\n", inp.readline())

    def test_empty_gzip(self):
        source = CharSource.from_gzipped_file(Path(__file__).parent / "empty_gzip.txt.gz")
        self.assertTrue(source.is_empty())
        self.assertEqual("", source.read_all())

    def test_from_within_tgz_file(self):
        # prepare test archive
        file_path = Path(__file__).parent / "test_read_from_tar.tgz"
        path_within_tgz = "./hello/world"
        self.assertEqual(
            "hello\nworld\n",
            CharSource.from_file_in_tgz(file_path, path_within_tgz, "utf-8").read_all(),
        )

    def test_null_sink(self):
        sink = CharSink.to_nowhere()
        sink.write("foo")
        with sink.open() as out:
            out.write("meep")

    def test_to_file_write(self):
        tmp_dir = Path(tempfile.mkdtemp())
        file_path = tmp_dir / "test.txt"
        sink = CharSink.to_file(file_path)
        sink.write("hello\n\nworld\n")
        source = CharSource.from_file(file_path)
        self.assertEqual("hello\n\nworld\n", source.read_all())
        shutil.rmtree(str(tmp_dir))

    def test_to_file_write_string_arg(self):
        tmp_dir = Path(tempfile.mkdtemp())
        file_path = tmp_dir / "test.txt"
        sink = CharSink.to_file(str(file_path))
        sink.write("hello\n\nworld\n")
        source = CharSource.from_file(str(file_path))
        self.assertEqual("hello\n\nworld\n", source.read_all())
        shutil.rmtree(str(tmp_dir))

    def test_to_file_open(self):
        tmp_dir = Path(tempfile.mkdtemp())
        file_path = tmp_dir / "test.txt"
        with CharSink.to_file(file_path).open() as out:
            out.write("hello\n\nworld\n")
        source = CharSource.from_file(file_path)
        self.assertEqual("hello\n\nworld\n", source.read_all())
        shutil.rmtree(str(tmp_dir))

    def test_file_in_zip(self):
        tmp_dir = Path(tempfile.mkdtemp())
        zip_path = tmp_dir / "test.zip"

        ByteSink.file_in_zip(zip_path, "fred").write("foo".encode("utf-8"))
        ByteSink.file_in_zip(zip_path, "empty_file").write("".encode("utf-8"))

        with ZipFile(zip_path, "r") as zip_file:
            self.assertTrue("fred" in zip_file.namelist())
            self.assertEqual("foo".encode("utf-8"), zip_file.read("fred"))
            self.assertEqual(
                "foo", CharSource.from_file_in_zip(zip_file, "fred").read_all()
            )
            self.assertTrue(
                CharSource.from_file_in_zip(zip_file, "empty_file").is_empty()
            )

        # also test version which takes zip file path rather than zip file object
        self.assertEqual("foo", CharSource.from_file_in_zip(zip_path, "fred").read_all())
        self.assertTrue(CharSource.from_file_in_zip(zip_path, "empty_file").is_empty())

        shutil.rmtree(str(tmp_dir))

    def test_string_sink(self):
        string_sink = CharSink.to_string()
        string_sink.write("hello world")
        self.assertEqual("hello world", string_sink.last_string_written)

    def test_byte_buffer_sink(self):
        byte_sink = ByteSink.to_buffer()
        byte_sink.write("hello world".encode("utf-8"))
        self.assertEqual("hello world", byte_sink.last_bytes_written.decode("utf-8"))

    def test_read_write_doc_id_to_file_map(self):
        map = ImmutableDict.of([("foo", Path("/home/foo")), ("bar", Path("/home/bar"))])
        string_sink = CharSink.to_string()
        write_doc_id_to_file_map(map, string_sink)
        # note the reordering because it alphabetizes the docids
        self.assertEqual(
            "bar\t/home/bar\nfoo\t/home/foo\n", string_sink.last_string_written
        )

        reloaded_map = read_doc_id_to_file_map(
            CharSource.from_string(string_sink.last_string_written)
        )

        self.assertEqual(map, reloaded_map)

    def test_object_from_parameters(self):
        @attrs
        class TestObj:
            val: int = attrib_instance_of(int)

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
