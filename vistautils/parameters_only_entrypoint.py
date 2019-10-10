import logging
import os
import sys
from typing import Callable, Optional

from vistautils.logging_utils import configure_logging_from
from vistautils.parameters import Parameters, YAMLParametersLoader

log = logging.getLogger(__name__)  # pylint:disable=invalid-name


def parameters_only_entry_point(
    main_method: Callable[[Parameters], None],
    usage_message: str = None,
    *,
    parameters: Optional[Parameters] = None
) -> None:
    """
    Convenience wrapper for entry points which take a single parameter file as an argument.

    In addition to saving the boilerplate of loading parameters, this will also automatically
    configure logging from the param file itself (see `configure_logging_from`) and log the
    contents of the parameter file. In the future, other such conveniences may be added.

    The user may specify *parameters* explicitly,
    in which case the argument passed to the program is ignored.

    This is primarily for ISI VISTA-internal use.
    """
    if len(sys.argv) == 2:
        if parameters:
            params = parameters
        else:
            params = YAMLParametersLoader().load(sys.argv[1])
        configure_logging_from(params)
        log.info("Ran with parameters:\n%s", params)
        main_method(params)
    else:
        if not usage_message:
            import __main__ as main

            usage_message = "usage: {!s} param_file".format(
                os.path.basename(main.__file__)
            )
        log.error(usage_message)
        sys.exit(1)
