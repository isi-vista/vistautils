from pathlib import Path

from vistautils.key_value import KeyValueSink, KeyValueSource
from vistautils.parameters import Parameters
from vistautils.scripts import split_key_value_store


def test_split_key_value_store_explicit_split(tmp_path: Path):
    output_foo = tmp_path / "foo"
    output_bar = tmp_path / "bar"

    key_value_path = tmp_path / "key_value"
    key_value_path.touch()

    with KeyValueSink.zip_character_sink(key_value_path) as sink:
        sink.put("key1", "value1")
        sink.put("key2", "value2")
        sink.put("key3", "value3")
        sink.put("key4", "value4")

    keys_foo = tmp_path / "foo_keys"
    keys_foo.touch()
    with keys_foo.open("w") as keys:
        keys.write("key1\nkey2")

    keys_bar = tmp_path / "bar_keys"
    keys_bar.touch()
    with keys_bar.open("w") as keys:
        keys.write("key3\nkey4")

    input_params = Parameters.from_mapping({"type": "zip", "path": str(key_value_path)})

    foo_params = Parameters.from_mapping(
        {"output_file": str(output_foo), "keys_file": str(keys_foo)}
    )
    bar_params = Parameters.from_mapping(
        {"output_file": str(output_bar), "keys_file": str(keys_bar)}
    )

    split_params = Parameters.from_mapping({"foo": foo_params, "bar": bar_params})

    final_params = Parameters.from_mapping(
        {"input": input_params, "explicit_split": split_params}
    )

    split_key_value_store.main(final_params)

    foo_reference = {"key1": "value1", "key2": "value2"}
    bar_reference = {"key3": "value3", "key4": "value4"}

    with KeyValueSource.zip_character_source(output_foo) as source:
        assert set(source.keys()) == set(foo_reference.keys())
        for key, reference_value in foo_reference.items():
            assert source[key] == reference_value

    with KeyValueSource.zip_character_source(output_bar) as source:
        assert set(source.keys()) == set(bar_reference.keys())
        for key, reference_value in bar_reference.items():
            assert source[key] == reference_value
