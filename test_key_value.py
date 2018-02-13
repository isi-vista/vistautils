import shutil
import tempfile
from pathlib import Path
from unittest import TestCase

from flexnlp.utils.immutablecollections import ImmutableSet
from flexnlp.utils.key_value import KeyValueSink, KeyValueSource


class TestKeyValue(TestCase):
    def test_zip_bytes(self):
        tmp_dir = Path(tempfile.mkdtemp())

        with KeyValueSink.zip_bytes_sink(tmp_dir / 'test.zip') as zip_sink:
            zip_sink.put('hello', 'world'.encode('utf-8'))
            zip_sink.put('foo', 'bar'.encode('utf-8'))

        with KeyValueSource.zip_bytes_source(tmp_dir / 'test.zip') as zip_source:
            self.assertIsNotNone(zip_source.keys())
            self.assertEqual(ImmutableSet.of(['hello', 'foo']), zip_source.keys())
            self.assertEqual('world'.encode('utf-8'), zip_source.get('hello'))
            self.assertEqual('bar'.encode('utf-8'), zip_source.get('foo'))
            self.assertIsNone(zip_source.get('not-there'))

        # test adding to an existing zip
        with KeyValueSink.zip_bytes_sink(tmp_dir / 'test.zip',
                                         overwrite=False) as zip_sink:
            zip_sink.put('meep', 'lalala'.encode('utf-8'))

        with KeyValueSource.zip_bytes_source(tmp_dir / 'test.zip') as zip_source:
            self.assertIsNotNone(zip_source.keys())
            self.assertEqual(ImmutableSet.of(['hello', 'foo', 'meep']), zip_source.keys())
            self.assertEqual('world'.encode('utf-8'), zip_source.get('hello'))
            self.assertEqual('bar'.encode('utf-8'), zip_source.get('foo'))
            self.assertEqual('lalala'.encode('utf-8'), zip_source.get('meep'))
            self.assertIsNone(zip_source.get('not-there'))

        shutil.rmtree(str(tmp_dir))

    def test_zip_chars(self):
        tmp_dir = Path(tempfile.mkdtemp())

        with KeyValueSink.zip_character_sink(tmp_dir / 'test.zip') as zip_sink:
            zip_sink.put('hello', 'world')
            zip_sink.put('foo', 'bar')

        with KeyValueSource.zip_character_source(tmp_dir / 'test.zip') as zip_source:
            self.assertIsNotNone(zip_source.keys())
            self.assertEqual(ImmutableSet.of(['hello', 'foo']), zip_source.keys())
            self.assertEqual('world', zip_source.get('hello'))
            self.assertEqual('bar', zip_source.get('foo'))
            self.assertIsNone(zip_source.get('not-there'))

        # test adding to an existing zip
        with KeyValueSink.zip_character_sink(tmp_dir / 'test.zip',
                                             overwrite=False) as zip_sink:
            zip_sink.put('meep', 'lalala')

        with KeyValueSource.zip_character_source(tmp_dir / 'test.zip') as zip_source:
            self.assertIsNotNone(zip_source.keys())
            self.assertEqual(ImmutableSet.of(['hello', 'foo', 'meep']), zip_source.keys())
            self.assertEqual('world', zip_source.get('hello'))
            self.assertEqual('bar', zip_source.get('foo'))
            self.assertEqual('lalala', zip_source.get('meep'))
            self.assertIsNone(zip_source.get('not-there'))

        shutil.rmtree(str(tmp_dir))

