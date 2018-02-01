import logging
import logging.config

from flexnlp.parameters import Parameters


def configure_logging_from(params: Parameters) -> None:
    """
    Configures logging from parameters.

    This will examine the 'logging' namespace of the provided parameters. If that namespace
    has a 'config_file' parameter, logging will be configured based on the parameter file it
    points to.  Otherwise, if 'logging.root_level' is specified, the logging level of the root
    logger will be set to its value.  For reference, the standard values are CRITICAL, FATAL,
    ERROR, WARNING, INFO, and DEBUG.
    """
    if 'logging' in params:
        if 'logging.config_file' in params:
            logging.config.fileConfig(str(params.existing_file('logging.config_file')))
            return

        # if no config file is provided we default to logging to the Console
        logging.getLogger().addHandler(logging.StreamHandler())
        if 'logging.root_level' in params:
            user_level_string = params.string('logging.root_level')
            # we need to translate the user provided string into the numeric value used to
            # specify logging levels.  We need to work around the quirk that if the user string
            # doesn't correspond to any known level, getLevelName just returns it input
            # preceded by "Level "

            # https://github.com/python/typeshed/issues/1842
            level_name = logging.getLevelName(user_level_string)  # type: ignore
            if isinstance(level_name, str) and level_name == "Level " + user_level_string:
                raise ValueError("Invalid logging level " + user_level_string)
            logging.getLogger().setLevel(level_name)
