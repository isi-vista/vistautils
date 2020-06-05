"""
Given a directory, copies its content into an object which can be used as a `KeyValueSource`.

The form of the output key-value store is given by the "output" sub-namespace of the parameters.
See `byte_key_value_sink_from_params` for details.
In the most common case of a zip-backed store, create a sub-namespace like this:
.. code-block:: YAML

    output:
      type: zip
      path: path of zip to write to

Each file in the input directory will become one entry in the output store
with a value equal to the binary content of the file.
The key will by default be the file name (not the full path).
This can be changed by specifying the *key_function* parameter.
Currently the only key function supported is *strip_one_extension*,
which removes the first extension (if present) from the file name before using it as the key.

Because the correct way to handle them is unclear,
if any sub-directories of the input directory are encountered, an error will be raised.
This behavior is subject to change in the future and should not be relied upon.
"""
import logging
from pathlib import Path
from typing import Callable

from vistautils.key_value import byte_key_value_sink_from_params
from vistautils.parameters import Parameters
from vistautils.parameters_only_entrypoint import parameters_only_entry_point


def main(params: Parameters) -> None:
    input_directory = params.existing_directory("input_directory")
    key_function = key_function_from_params(params)

    with byte_key_value_sink_from_params(params, eval_context=locals()) as sink:
        for item_path in input_directory.rglob("*"):
            if item_path.is_file():
                logging.info("Copying %s to output sink", item_path)
                sink.put(key=key_function(item_path), value=item_path.read_bytes())


def key_function_from_params(params: Parameters) -> Callable[[Path], str]:
    key_function_string = (
        params.optional_string("key_function", [IDENTITY, STRIP_ONE_EXTENSION])
        or IDENTITY
    )
    if key_function_string == IDENTITY:
        return identity_key_function
    elif key_function_string == STRIP_ONE_EXTENSION:
        return strip_one_extension_key_function
    else:
        raise NotImplementedError(f"Unknown key function %s", key_function_string)


IDENTITY = "identity"
STRIP_ONE_EXTENSION = "strip_one_extension"


def identity_key_function(path: Path) -> str:
    return path.name


def strip_one_extension_key_function(path: Path) -> str:
    return path.stem


if __name__ == "__main__":
    parameters_only_entry_point(main)
