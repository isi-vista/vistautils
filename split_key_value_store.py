"""
Split any character key-value store in multiple character key-value stores.

This is useful when splitting up input for parallel processing.

Currently the output stores are always zip file stores. This might become configurable
in the future.

The "input" namespace specifies the input key-value store. Please see
char_key_value_source_from_params for details on the parameters used to specify input.

The "num_slices" param specifies how many slices to create.

The list of zip files created will be stored in "_slices.txt" in the output directory.
"""
import sys
from contextlib import ExitStack

from flexnlp.parameters import Parameters, YAMLParametersLoader
from flexnlp.utils.io_utils import CharSink
from flexnlp.utils.key_value import char_key_value_source_from_params, KeyValueSink


def main(params: Parameters):
    output_directory = params.creatable_directory('output_dir')
    slices = params.positive_integer('num_slices')

    slice_paths = [output_directory / "{!s}.zip".format(i) for i in range(slices)]
    CharSink.to_file(output_directory / "_slices.txt").write('\n'.join(str(x) for x in slice_paths))
    output_sinks = [KeyValueSink.zip_character_sink(slice_path) for slice_path in slice_paths]

    # this is the magic incantation for handling variable-length lists of context managers
    with ExitStack() as exit_stack:
        for output_sink in output_sinks:
            exit_stack.enter_context(output_sink)
        with char_key_value_source_from_params('input', params) as input_source:
            for (i, key) in enumerate(input_source.keys()):
                output_sinks[i % slices].put(key, input_source[key])


if __name__ == '__main__':
    main(YAMLParametersLoader().load(sys.argv[1]))
