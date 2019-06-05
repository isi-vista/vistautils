import logging
from typing import Callable

import sys

import os

import yaml

from vistautils.parameters import YAMLParametersLoader, Parameters
from vistautils.logging_utils import configure_logging_from

log = logging.getLogger(__name__)  # pylint:disable=invalid-name


def parameters_representer(dumper: yaml.Dumper, params: Parameters) -> yaml.Node:
    """
    PyYAML representer for Parameters objects.
    """
    return dumper.represent_mapping("Parameters", params.as_mapping())


def parameters_only_entry_point(
    main_method: Callable[[Parameters], None], usage_message: str = None
) -> None:
    """
    Convenience wrapper for entry points which take a single parameter file as an argument.

    In addition to saving the boilerplate of loading parameters, this will also automatically
    configure logging from the param file itself (see `configure_logging_from`) and log the
    contents of the parameter file. In the future, other such conveniences may be added.

    This is primarily for ISI VISTA-internal use.
    """
    if len(sys.argv) == 2:
        params = YAMLParametersLoader().load(sys.argv[1])
        configure_logging_from(params)
        yaml.add_representer(Parameters, parameters_representer)
        parameters_as_yaml = yaml.dump(params, default_flow_style=False)
        log.info("Ran with parameters:\n%s", parameters_as_yaml)
        main_method(params)
    else:
        if not usage_message:
            import __main__ as main

            usage_message = "usage: {!s} param_file".format(
                os.path.basename(main.__file__)
            )
        log.error(usage_message)
        sys.exit(1)
