from pathlib import Path
from typing import Optional

from vistautils.key_value import KeyValueSource
from vistautils.parameters import Parameters
from vistautils.scripts import directory_to_key_value_store

import pytest


@pytest.mark.parametrize("key_function", [None, "strip_one_extension"])
def test_directory_key_value_store(tmp_path: Path, key_function: Optional[str]):
    input_dir = tmp_path / "input_dir"
    input_dir.mkdir(exist_ok=True)

    # We test filenames with 0, 1, and 2 extensions.
    filenames = ("fred", "bob.txt", "melvin.tar.gz")
    filenames_without_one_extension = ("fred", "bob", "melvin.tar")
    file_content = ("hello", "world", "foo")

    for (filename, content) in zip(filenames, file_content):
        (input_dir / filename).write_text(content, encoding="utf-8")

    output_zip_path = (tmp_path / "output.zip").absolute()
    params = {
        "input_directory": str(input_dir.absolute()),
        "output": {"type": "zip", "path": str(output_zip_path)},
    }

    if key_function:
        params["key_function"] = key_function

    directory_to_key_value_store.main(Parameters.from_mapping(params))

    if key_function == "strip_one_extension":
        reference = dict(zip(filenames_without_one_extension, file_content))
    else:
        reference = dict(zip(filenames, file_content))

    with KeyValueSource.zip_character_source(output_zip_path) as source:
        assert set(source.keys()) == set(reference.keys())
        for key, reference_value in reference.items():
            assert source[key] == reference_value
