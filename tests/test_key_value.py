import shutil
import tarfile
import tempfile
from io import BytesIO
from pathlib import Path
from typing import Optional
from unittest import TestCase

from immutablecollections import ImmutableSet

from vistautils.key_value import (
    KeyValueLinearSource,
    KeyValueSink,
    KeyValueSource,
    byte_key_value_sink_from_params,
    byte_key_value_source_from_params,
    char_key_value_sink_from_params,
    char_key_value_source_from_params,
)
from vistautils.parameters import YAMLParametersLoader


class TestKeyValue(TestCase):
    def test_zip_bytes(self):
        tmp_dir = Path(tempfile.mkdtemp())

        with KeyValueSink.zip_bytes_sink(tmp_dir / "test.zip") as zip_sink:
            zip_sink.put("hello", "world".encode("utf-8"))
            zip_sink.put("foo", "bar".encode("utf-8"))

        with KeyValueSource.zip_bytes_source(tmp_dir / "test.zip") as zip_source:
            self.assertIsNotNone(zip_source.keys())
            self.assertEqual(ImmutableSet.of(["hello", "foo"]), zip_source.keys())
            self.assertEqual("world".encode("utf-8"), zip_source["hello"])
            self.assertEqual("bar".encode("utf-8"), zip_source["foo"])
            self.assertIsNone(zip_source.get("not-there", None))
            self.assertEqual(
                "moo".encode("utf-8"), zip_source.get("not-there", "moo".encode("utf-8"))
            )
            with self.assertRaises(KeyError):
                zip_source["not-there"]

        # test adding to an existing zip
        with KeyValueSink.zip_bytes_sink(
            tmp_dir / "test.zip", overwrite=False
        ) as zip_sink:
            zip_sink.put("meep", "lalala".encode("utf-8"))

        with KeyValueSource.zip_bytes_source(tmp_dir / "test.zip") as zip_source:
            self.assertIsNotNone(zip_source.keys())
            self.assertEqual(ImmutableSet.of(["hello", "foo", "meep"]), zip_source.keys())
            self.assertEqual("world".encode("utf-8"), zip_source["hello"])
            self.assertEqual("bar".encode("utf-8"), zip_source["foo"])
            self.assertEqual("lalala".encode("utf-8"), zip_source["meep"])
            self.assertIsNone(zip_source.get("not-there", None))
            self.assertEqual(
                "moo".encode("utf-8"), zip_source.get("not-there", "moo".encode("utf-8"))
            )
            with self.assertRaises(KeyError):
                zip_source["not-there"]

        shutil.rmtree(str(tmp_dir))

    def test_zip_chars(self):
        tmp_dir = Path(tempfile.mkdtemp())

        with KeyValueSink.zip_character_sink(tmp_dir / "test.zip") as zip_sink:
            zip_sink.put("hello", "world")
            zip_sink.put("foo", "bar")

        with KeyValueSource.zip_character_source(tmp_dir / "test.zip") as zip_source:
            self.assertIsNotNone(zip_source.keys())
            self.assertEqual(ImmutableSet.of(["hello", "foo"]), zip_source.keys())
            self.assertEqual("world", zip_source["hello"])
            self.assertEqual("bar", zip_source["foo"])
            self.assertIsNone(zip_source.get("not-there", None))
            self.assertEqual("moo", zip_source.get("not-there", "moo"))
            with self.assertRaises(KeyError):
                zip_source["not-there"]

        # test adding to an existing zip
        with KeyValueSink.zip_character_sink(
            tmp_dir / "test.zip", overwrite=False
        ) as zip_sink:
            zip_sink.put("meep", "lalala")

        with KeyValueSource.zip_character_source(tmp_dir / "test.zip") as zip_source:
            self.assertIsNotNone(zip_source.keys())
            self.assertEqual(ImmutableSet.of(["hello", "foo", "meep"]), zip_source.keys())
            self.assertEqual("world", zip_source["hello"])
            self.assertEqual("bar", zip_source["foo"])
            self.assertEqual("lalala", zip_source["meep"])
            self.assertIsNone(zip_source.get("not-there", None))
            self.assertEqual("moo", zip_source.get("not-there", "moo"))
            with self.assertRaises(KeyError):
                zip_source["not-there"]

        shutil.rmtree(str(tmp_dir))

    def test_tgz_chars(self):
        tmp_dir = Path(tempfile.mkdtemp())

        def write_string_to_tar(key: str, val: str):
            val_bytes = BytesIO(val.encode("utf-8"))
            info = tarfile.TarInfo(name=key)
            info.size = len(val_bytes.getvalue())
            tar_file.addfile(info, val_bytes)

        # manually make a three-element tar file for testing
        with tarfile.open(tmp_dir / "tmp.tgz", "w:gz") as tar_file:
            write_string_to_tar("foo123", "hello")
            write_string_to_tar("meepbadmeep", "i should get filtered out")
            write_string_to_tar("bar3435", "world")
            write_string_to_tar("a", "thrown out because key too short")

        def filter_out_keys_containing_bad(key: str) -> bool:
            return "bad" not in key

        def keep_only_first_three_chars_of_key_ban_too_short(key: str) -> Optional[str]:
            if len(key) < 3:
                return None
            else:
                return key[0:3]

        with KeyValueLinearSource.str_linear_source_from_tar_gz(
            tmp_dir / "tmp.tgz",
            name_filter=filter_out_keys_containing_bad,
            key_function=keep_only_first_three_chars_of_key_ban_too_short,
        ) as source:
            vals = set([x for x in source.items()])
            self.assertEqual({("foo", "hello"), ("bar", "world")}, vals)

        shutil.rmtree(str(tmp_dir))


# all newer tests are in pytest format


def test_char_source_sink_from_params(tmp_path: Path) -> None:
    sink_params_text = f"""
output:
   type: zip
   path: {tmp_path / "output.zip"}
    """
    sink_params = YAMLParametersLoader().load_string(sink_params_text)
    with char_key_value_sink_from_params(sink_params) as sink:
        sink.put("hello", "world")
        sink.put("goodbye", "fred")
    source_params_text = f"""
    altinput:
       type: zip
       path: {tmp_path / "output.zip"}
        """
    source_params = YAMLParametersLoader().load_string(source_params_text)

    # we test specifying an alternate namespace
    with char_key_value_source_from_params(
        source_params, input_namespace="altinput"
    ) as source:
        assert "world" == source["hello"]
        assert "fred" == source["goodbye"]


def test_binary_source_sink_from_params(tmp_path: Path) -> None:
    sink_params_text = f"""
output:
   type: zip
   path: {tmp_path / "output.zip"}
    """
    sink_params = YAMLParametersLoader().load_string(sink_params_text)
    with byte_key_value_sink_from_params(sink_params) as sink:
        sink.put("hello", "world".encode("utf-8"))
        sink.put("goodbye", "fred".encode("utf-8"))
    source_params_text = f"""
    altinput:
       type: zip
       path: {tmp_path / "output.zip"}
        """
    source_params = YAMLParametersLoader().load_string(source_params_text)

    # we test specifying an alternate namespace
    with byte_key_value_source_from_params(
        source_params, input_namespace="altinput"
    ) as source:
        assert "world" == source["hello"].decode("utf-8")
        assert "fred" == source["goodbye"].decode("utf-8")
