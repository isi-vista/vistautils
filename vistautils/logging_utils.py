import logging
import logging.config

from vistautils.parameters import Parameters, ParameterError

log = logging.getLogger(__name__)   # pylint:disable=invalid-name

# we need to store this mapping here because logging doens't provide a (non-deprecated) way to map
# from strings to levels
# https://github.com/python/typeshed/issues/1842
_LEVEL_STRINGS_TO_LEVELS = {
    'CRITICAL': logging.CRITICAL,
    'FATAL': logging.FATAL,
    'ERROR': logging.ERROR,
    'WARNING': logging.WARNING,
    'WARN': logging.WARNING,
    'INFO': logging.INFO,
    'DEBUG': logging.DEBUG
}


def configure_logging_from(params: Parameters, *, log_params=True) -> None:
    """
    Configures logging from parameters.

    This will examine the 'logging' namespace of the provided parameters. If that namespace
    has a 'config_file' parameter, logging will be configured based on the parameter file it
    points to.  Otherwise, if 'logging.root_level' is specified, the logging level of the root
    logger will be set to its value.  For reference, the standard values are CRITICAL, FATAL,
    ERROR, WARNING, INFO, and DEBUG.
    """
    if 'logging.config_file' in params:
        logging.config.fileConfig(str(params.existing_file('logging.config_file')))
    else:
        _config_logging_from_params(params)

    if log_params:
        log.info(str(params))


def _config_logging_from_params(params):
    # Python's default logging level of "warning" is not typically what we want in our programs,
    # so we change the default level to INFO unless overriden below
    set_root_level_to = 'INFO'

    if 'logging' in params:
        # if no config file is provided we default to logging to the Console
        logging.getLogger().addHandler(logging.StreamHandler())
        if 'logging.root_level' in params:
            set_root_level_to = params.string('logging.root_level')

    try:
        level = _LEVEL_STRINGS_TO_LEVELS[set_root_level_to]
    except KeyError:
        raise ParameterError("Invalid logging level {!s}. Valid levels "
                             "are {!s}".format(set_root_level_to,
                                               list(_LEVEL_STRINGS_TO_LEVELS.keys())))
    logging.getLogger().setLevel(level)

    # configure a console handler with the default formatter. We could make this
    # configurable in the future
    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)
    console_handler.setFormatter(logging.Formatter(logging.BASIC_FORMAT))
    logging.getLogger().addHandler(console_handler)
