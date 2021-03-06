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
    foo_reference = {"key1": "value1", "key2": "value2"}

    output_bar = tmp_path / "bar"
    keys_bar = tmp_path / "bar_keys"
    with keys_bar.open("w") as keys:
        keys.write("key3\nkey4\nkey2")
    bar_params = Parameters.from_mapping(
        {"output_file": str(output_bar), "keys_file": str(keys_bar)}
    )
    bar_reference = {"key2": "value2", "key3": "value3", "key4": "value4"}

    # Testing handling of empty key file
    output_none = tmp_path / "none"
    keys_none = tmp_path / "no_keys"
    keys_none.touch()
    none_params = Parameters.from_mapping(
        {"output_file": str(output_none), "keys_file": str(keys_none)}
    )

    split_params = Parameters.from_mapping(
        {"foo": foo_params, "bar": bar_params, "none": none_params}
    )

    key_value_path = tmp_path / "key_value"
    with KeyValueSink.zip_character_sink(key_value_path) as sink:
        sink["key1"] = "value1"
        sink["key2"] = "value2"
        sink["key3"] = "value3"
        sink["key4"] = "value4"

    input_params = Parameters.from_mapping({"type": "zip", "path": str(key_value_path)})

    final_params = Parameters.from_mapping(
        {"input": input_params, "explicit_split": split_params}
    )

    split_key_value_store.main(final_params)

    with KeyValueSource.zip_character_source(output_foo) as source:
        assert set(source.keys()) == set(foo_reference.keys())
        for key, reference_value in foo_reference.items():
            assert source[key] == reference_value

    with KeyValueSource.zip_character_source(output_bar) as source:
        assert set(source.keys()) == set(bar_reference.keys())
        for key, reference_value in bar_reference.items():
            assert source[key] == reference_value

    with KeyValueSource.zip_character_source(output_none) as source:
        assert set(source.keys()) == set()


def test_split_key_value_store_explicit_split_non_exhaustive_disallowed(tmp_path: Path):
    output = tmp_path / "foo"
    keys = tmp_path / "foo_keys"
    with keys.open("w") as kf:
        kf.write("key1\nkey2")
    foo_params = Parameters.from_mapping(
        {"output_file": str(output), "keys_file": str(keys)}
    )

    key_value_path = tmp_path / "key_value"
    with KeyValueSink.zip_character_sink(key_value_path) as sink:
        sink.put("key1", "value1")
        sink.put("key2", "value2")
        sink.put("key3", "value3")
        sink.put("key4", "value4")

    input_params = Parameters.from_mapping({"type": "zip", "path": str(key_value_path)})

    final_params = Parameters.from_mapping(
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
        split_key_value_store.main(final_params)


def test_split_key_value_store_explicit_split_non_exhaustive_allowed(tmp_path: Path):
    output = tmp_path / "foo"
    keys = tmp_path / "foo_keys"
    with keys.open("w") as kf:
        kf.write("key1\nkey2")
    foo_params = Parameters.from_mapping(
        {"output_file": str(output), "keys_file": str(keys)}
    )

    key_value_path = tmp_path / "key_value"
    with KeyValueSink.zip_character_sink(key_value_path) as sink:
        sink.put("key1", "value1")
        sink.put("key2", "value2")
        sink.put("key3", "value3")
        sink.put("key4", "value4")

    input_params = Parameters.from_mapping({"type": "zip", "path": str(key_value_path)})

    final_params = Parameters.from_mapping(
        {
            "input": input_params,
            "explicit_split": Parameters.from_mapping({"foo": foo_params}),
            "must_be_exhaustive": False,
        }
    )

    split_key_value_store.main(final_params)

    reference = {"key1": "value1", "key2": "value2"}

    with KeyValueSource.zip_character_source(output) as source:
        assert set(source.keys()) == set(reference.keys())
        for key, reference_value in reference.items():
            assert source[key] == reference_value


def test_split_key_value_store_even_split_random_seed(tmp_path: Path):
    output = tmp_path / "foo"

    key_value_path = tmp_path / "key_value"
    with KeyValueSink.zip_character_sink(key_value_path) as sink:
        sink.put("key1", "value1")
        sink.put("key2", "value2")
        sink.put("key3", "value3")
        sink.put("key4", "value4")

    input_params = Parameters.from_mapping({"type": "zip", "path": str(key_value_path)})

    final_params = Parameters.from_mapping(
        {
            "input": input_params,
            "num_slices": 2,
            "random_seed": 2,  # deterministic seed
            "output_dir": str(output),
        }
    )

    split_key_value_store.main(final_params)

    zip1 = {"key1": "value1", "key3": "value3"}
    zip0 = {"key2": "value2", "key4": "value4"}

    for handle in output.glob("*.zip"):
        with KeyValueSource.zip_character_source(handle) as source:
            print(handle.stem, source.keys())
            assert len(source.keys()) == 2  # num_slices / total keys
            if handle.stem == 1:
                for key, reference_value in zip1.items():
                    assert source[key] == reference_value
            elif handle.stem == 0:
                for key, reference_value in zip0.items():
                    assert source[key] == reference_value
