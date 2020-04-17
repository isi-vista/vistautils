from pathlib import Path

from vistautils.key_value import KeyValueSink, KeyValueSource
from vistautils.parameters import Parameters
from vistautils.scripts import downsample_key_value_store

from pytest import raises


def test_downsample_key_value_store(tmp_path: Path):
    key_value_path = tmp_path / "key_value.zip"
    with KeyValueSink.zip_character_sink(key_value_path) as sink:
        sink["key1"] = "value1"
        sink["key2"] = "value2"
        sink["key3"] = "value3"
        sink["key4"] = "value4"

    input_params = Parameters.from_mapping({"type": "zip", "path": str(key_value_path)})

    output = tmp_path / "output.zip"

    main_params = Parameters.from_mapping(
        {"input": input_params, "num_to_sample": 2, "output_zip_path": str(output)}
    )

    downsample_key_value_store.main(main_params)

    reference = [
        ("key1", "value1"),
        ("key2", "value2"),
        ("key3", "value3"),
        ("key4", "value4"),
    ]

    with KeyValueSource.zip_character_source(output) as source:
        contents = source.items()
        assert next(contents) in reference
        assert next(contents) in reference
        with raises(StopIteration):
            next(contents)
