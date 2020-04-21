#!/usr/bin/env python

"""
Reduce the size of a key-value store.

This is typically useful as an optional step
to run workflows in a fast "debugging" mode.

The downsampled output is written to a zip key-value store
 at the path specified by *output_zip_path*.
This might become more configurable in the future.

The "input" namespace specifies the input key-value store. Please see
`byte_key_value_source_from_params` for details on the parameters used to specify input.

*num_to_sample* specifies the number of random key-value pairs
from the input will be preserved in the output
(or however many are available, if fewer than that number).

The ordering of the key-value pairs in the output is undefined but deterministic.
"""
import logging
import random

from vistautils.key_value import KeyValueSink, byte_key_value_source_from_params
from vistautils.parameters import Parameters
from vistautils.parameters_only_entrypoint import parameters_only_entry_point

_NUM_TO_SAMPLE_PARAM = "num_to_sample"
_RANDOM_SEED_PARAM = "random_seed"


def main(params: Parameters):
    with byte_key_value_source_from_params(params) as input_source:
        keys = list(input_source.keys())
        num_to_sample = min(params.positive_integer(_NUM_TO_SAMPLE_PARAM), len(keys))
        random.shuffle(
            keys,
            random=random.Random(params.integer(_RANDOM_SEED_PARAM, default=0)).random,
        )
        keys_to_keep = keys[:num_to_sample]
        output_zip_path = params.creatable_file("output_zip_path")
        logging.info("Downsampling %s files to %s", num_to_sample, output_zip_path)
        with KeyValueSink.zip_bytes_sink(output_zip_path) as out:
            for key in keys_to_keep:
                out.put(key, input_source[key])


if __name__ == "__main__":
    parameters_only_entry_point(main)
