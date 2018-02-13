import shutil
import tempfile
from pathlib import Path
from unittest import TestCase
from zipfile import ZipFile

from flexnlp.utils.io_utils import CharSource, CharSink, ByteSink


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
        source = CharSource.from_file(Path(__file__).parent / 'char_source_test.txt')
        self.assertEqual("Hello\nworld\n", source.read_all())
        self.assertEqual(["Hello", "world"], source.readlines())
        self.assertFalse(source.is_empty())
        with source.open() as inp:
            self.assertEqual("Hello\n", inp.readline())
            self.assertEqual("world\n", inp.readline())

    def test_from_gzip_file(self):
        source = CharSource.from_gzipped_file(
            Path(__file__).parent / 'gzip_char_source_test.txt.gz')
        self.assertEqual("Hello\nworld\n", source.read_all())
        self.assertEqual(["Hello", "world"], source.readlines())
        with source.open() as inp:
            self.assertEqual("Hello\n", inp.readline())
            self.assertEqual("world\n", inp.readline())

    def test_empty_gzip(self):
        source = CharSource.from_gzipped_file(
            Path(__file__).parent / 'empty_gzip.txt.gz')
        self.assertTrue(source.is_empty())
        self.assertEqual("", source.read_all())

    def test_null_sink(self):
        sink = CharSink.to_nowhere()
        sink.write('foo')
        with sink.open() as out:
            out.write('meep')

    def test_to_file_write(self):
        tmp_dir = Path(tempfile.mkdtemp())
        file_path = tmp_dir / 'test.txt'
        sink = CharSink.to_file(file_path)
        sink.write('hello\n\nworld\n')
        source = CharSource.from_file(file_path)
        self.assertEqual('hello\n\nworld\n', source.read_all())
        shutil.rmtree(str(tmp_dir))

    def test_to_file_open(self):
        tmp_dir = Path(tempfile.mkdtemp())
        file_path = tmp_dir / 'test.txt'
        with CharSink.to_file(file_path).open() as out:
            out.write('hello\n\nworld\n')
        source = CharSource.from_file(file_path)
        self.assertEqual('hello\n\nworld\n', source.read_all())
        shutil.rmtree(str(tmp_dir))

    def test_file_in_zip(self):
        tmp_dir = Path(tempfile.mkdtemp())
        zip_path = tmp_dir / 'test.zip'

        ByteSink.file_in_zip(zip_path, 'fred').write("foo".encode('utf-8'))

        with ZipFile(zip_path, 'r') as zip_file:
            self.assertTrue('fred' in zip_file.namelist())
            self.assertEqual("foo".encode('utf-8'), zip_file.read('fred'))

        shutil.rmtree(str(tmp_dir))
