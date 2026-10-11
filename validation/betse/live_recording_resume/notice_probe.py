"""Exercise the installed BETSE terminal formatter as a real script, without a model."""

import logging

from betse.util.io.log.conf.logconfcls import LogConf

# Initialize only the actual terminal handlers; no rotating user logfile or simulator.
config = LogConf.__new__(LogConf)
config._logger_root = logging.getLogger()
config._init_logger_root_handler_std()
try:
    logging.warning("Ignoring cutting event, as cut profiles are disabled.")
finally:
    for handler in (config._logger_root_handler_stdout, config._logger_root_handler_stderr):
        config._logger_root.removeHandler(handler)
        handler.close()
