#!/usr/bin/env python

"""
Split a key-value store into multiple key-value stores.

This is useful when splitting up input for parallel processing.

Currently the output stores are always zip file stores. This might become configurable
in the future.

The "input" namespace specifies the input key-value store. Please see
`byte_key_value_source_from_params` for details on the parameters used to specify input.

There are two options for how the split should be done.

If *num_slices* is specified, the input will be split into *num_slices* output stores
of size as equal as possible.
The list of zip files created will be stored in "_slices.txt" in the output directory.


If an *explicit_split* namespace is specified, each sub-namespace of it will specified one split.
The names of these sub-namespaces are ignored.
Each sub-namespace will result in an output store being written to
the file specified by its *output_file* parameter
containing those mappings from the original key-value store
whose keys are found in the file specified by its `keys_file` parameter.
That file is expected to list one key per line.
The split is expected to be exhaustive
(that is, to include every mapping from the original key-value store)
unless the parameter *explicit_split.must_be_exhaustive* is set to *False*.
*explicit_split* is useful for tasks which have standard train/test splits.
"""
import random
from contextlib import ExitStack

from immutablecollections import immutableset

from vistautils.io_utils import CharSink, file_lines_to_set
from vistautils.key_value import (
    KeyValueSink,
    KeyValueSource,
    byte_key_value_linear_source_from_params,
)
from vistautils.misc_utils import str_list_limited
from vistautils.parameters import Parameters
from vistautils.parameters_only_entrypoint import parameters_only_entry_point

_NUM_SLICES_PARAM = "num_slices"
_EXPLICIT_SPLIT_PARAM = "explicit_split"


def main(params: Parameters):
    params.assert_exactly_one_present([_NUM_SLICES_PARAM, _EXPLICIT_SPLIT_PARAM])

    with byte_key_value_linear_source_from_params(params) as input_source:
        if _NUM_SLICES_PARAM in params:
            _split_into_even_slices(input_source, params)
        elif _EXPLICIT_SPLIT_PARAM in params:
            _explicit_split(input_source, params)
        else:
            raise RuntimeError("No known split parameter specified.")


def _split_into_even_slices(input_source: KeyValueSource[str, bytes], params: Parameters):
    output_directory = params.creatable_directory("output_dir")
    slices = params.positive_integer("num_slices")
    random_seed = params.optional_positive_integer("random_seed")
    slice_paths = [output_directory / "{!s}.zip".format(i) for i in range(slices)]
    CharSink.to_file(output_directory / "_slices.txt").write(
        "\n".join(str(x) for x in slice_paths)
    )
    output_sinks = [KeyValueSink.zip_bytes_sink(slice_path) for slice_path in slice_paths]
    # this is the magic incantation for handling variable-length lists of context managers
    with ExitStack() as exit_stack:
        for output_sink in output_sinks:
            exit_stack.enter_context(output_sink)
        input_keys = sorted(
            list(input_source.keys())  # type: ignore
        )  # guarantee deterministic iteration order
        if random_seed:
            random.seed(random_seed)
            random.shuffle(input_keys)
        for (i, k) in enumerate(input_keys):
            output_sinks[i % slices].put(k, input_source[k])


def _explicit_split(source: KeyValueSource[str, bytes], params: Parameters):
    explicit_split_namespace = params.namespace(_EXPLICIT_SPLIT_PARAM)

    # We track these so we can ensure the split is a complete partition of the input,
    # if the user so desires.
    keys_copied = []

    for split_namespace in explicit_split_namespace.sub_namespaces():
        keys_for_split = file_lines_to_set(split_namespace.existing_file("keys_file"))
        with KeyValueSink.zip_bytes_sink(
            split_namespace.creatable_file("output_file")
        ) as split_sink:
            for key in keys_for_split:
                source_value = source.get(key)
                if source_value is not None:
                    split_sink.put(key, source_value)
                    keys_copied.append(key)
                else:
                    error_message = (
                        f"For split specified in {split_namespace.namespace_prefix}, "
                        f"requested key value {key} not found in {source}."
                    )
                    available_keys = source.keys()
                    if available_keys is not None:
                        error_message = (
                            f"{error_message} Here are a few"  # type: ignore
                            f"available keys: {str_list_limited(source.keys(), 10)}"
                        )
                    raise RuntimeError(error_message)

    if params.boolean("must_be_exhaustive", default=True):
        keys_not_copied = immutableset(source.keys()) - set(keys_copied)
        if keys_not_copied:
            raise RuntimeError(
                f"Expected the split to be a partition, but "
                f"{len(keys_not_copied)} were not included in any output split, "
                f"including {str_list_limited(keys_not_copied, 10)}.  "
                f"If you did not intend the split to be exhaustive, "
                f"please specify set parameter must_be_exhaustive to False"
            )


if __name__ == "__main__":
    parameters_only_entry_point(main)
