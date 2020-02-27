import logging
import os
import sys
from argparse import ArgumentParser
from pathlib import Path
from typing import Callable, Optional, Sequence

from vistautils.logging_utils import configure_logging_from
from vistautils.parameters import Parameters, YAMLParametersLoader

log = logging.getLogger(__name__)  # pylint:disable=invalid-name


def parameters_only_entry_point(
    main_method: Callable[[Parameters], None],
    usage_message: str = None,
    *,
    parameters: Optional[Parameters] = None,
    program_name: Optional[str] = None
) -> None:
    """
    Convenience wrapper for entry points which take a single parameter file as an argument.

    In addition to saving the boilerplate of loading parameters, this will also automatically
    configure logging from the param file itself (see `configure_logging_from`) and log the
    contents of the parameter file. In the future, other such conveniences may be added.

    The caller of this function may specify *parameters* explicitly,
    in which case the user should not pass a parameter file to the program.

    The user may override parameters from the parameter file
    by specifying pairs of the form *-p param_name param_value*.
    Separate namespace components with *.*s in the parameter name.

    This is primarily for ISI VISTA-internal use.
    """
    # We split the real work off into another function so we can test argument parsing.
    _real_parameters_only_entry_point(
        main_method,
        usage_message,
        parameters=parameters,
        program_name=program_name,
        args=sys.argv[1:],
    )


def _real_parameters_only_entry_point(
    main_method: Callable[[Parameters], None],
    usage_message: str = None,
    *,
    parameters: Optional[Parameters] = None,
    program_name: Optional[str] = None,
    args: Sequence[str]
) -> None:
    if not program_name:
        # Get original script name for use in the usage message.
        import __main__ as main  # pylint:disable=import-outside-toplevel

        program_name = os.path.basename(main.__file__)

    arg_parser = ArgumentParser(prog=program_name, description=usage_message)
    if not parameters:
        arg_parser.add_argument("param_file", type=Path)
    arg_parser.add_argument("-p", action="append", nargs=2, required=False)

    parsed_args = arg_parser.parse_args(args)

    params = YAMLParametersLoader().load(parsed_args.param_file)
    if parsed_args.p:
        params = params.unify(params.from_key_value_pairs(parsed_args.p))
    configure_logging_from(params)
    log.info("Ran with parameters:\n%s", params)
    main_method(params)
