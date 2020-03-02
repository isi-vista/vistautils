from pathlib import Path

from vistautils.key_value import KeyValueSink, KeyValueSource
from vistautils.parameters import Parameters
from vistautils.scripts import split_key_value_store

from pytest import raises


def test_split_key_value_store_explicit_split(tmp_path: Path):
    output_foo = tmp_path / "foo"
    keys_foo = tmp_path / "foo_keys"
    with keys_foo.open("w") as keys:
        keys.write("key1\nkey2")
    foo_params = Parameters.from_mapping(
        {"output_file": str(output_foo), "keys_file": str(keys_foo)}
    )

    key_value_path = tmp_path / "key_value"
    with KeyValueSink.zip_character_sink(key_value_path) as sink:
        sink.put("key1", "value1")
        sink.put("key2", "value2")
        sink.put("key3", "value3")
        sink.put("key4", "value4")

    input_params = Parameters.from_mapping({"type": "zip", "path": str(key_value_path)})

    non_exhaustive = Parameters.from_mapping(
        {
            "input": input_params,
            "explicit_split": Parameters.from_mapping({"foo": foo_params}),
        }
    )
    with raises(
        RuntimeError,
        match=(
            "Expected the split to be a partition, but .* were not included in any output split, "
            "including .*. If you did not intend the split to be exhaustive, please specify set "
            "parameter must_be_exhaustive to False"
        ),
    ):
        split_key_value_store.main(non_exhaustive)

    output_foo.unlink()

    non_exhaustive = Parameters.from_mapping(
        {
            "input": input_params,
            "explicit_split": Parameters.from_mapping({"foo": foo_params}),
            "must_be_exhaustive": False,
        }
    )

    split_key_value_store.main(non_exhaustive)

    foo_reference = {"key1": "value1", "key2": "value2"}

    with KeyValueSource.zip_character_source(output_foo) as source:
        assert set(source.keys()) == set(foo_reference.keys())
        for key, reference_value in foo_reference.items():
            assert source[key] == reference_value

    output_foo.unlink()

    output_bar = tmp_path / "bar"
    keys_bar = tmp_path / "bar_keys"
    with keys_bar.open("w") as keys:
        keys.write("key3\nkey4")
    bar_params = Parameters.from_mapping(
        {"output_file": str(output_bar), "keys_file": str(keys_bar)}
    )

    output_none = tmp_path / "none"
    keys_none = tmp_path / "no_keys"
    keys_none.touch()
    none_params = Parameters.from_mapping(
        {"output_file": str(output_none), "keys_file": str(keys_none)}
    )

    split_params = Parameters.from_mapping(
        {"foo": foo_params, "bar": bar_params, "none": none_params}
    )

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

    # This fails currently - set(source.keys()) returns `{''}`
    with KeyValueSource.zip_character_source(output_none) as source:
        assert set(source.keys()) == set()
