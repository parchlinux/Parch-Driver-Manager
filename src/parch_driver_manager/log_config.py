import logging
import os
import sys


def setup_logging(debug: bool = False) -> None:
    debug_env = debug or bool(os.environ.get("PARCH_DM_DEBUG"))
    level = logging.DEBUG if debug_env else logging.WARNING

    log_format = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    logging.basicConfig(level=level, format=log_format, stream=sys.stderr)

    parch_logger = logging.getLogger("parch_driver_manager")
    parch_logger.setLevel(logging.DEBUG if debug_env else logging.INFO)

    cache_dir = os.environ.get(
        "PARCH_DM_CACHE_DIR",
        os.path.join(os.path.expanduser("~"), ".cache", "parch-driver-manager"),
    )
    os.makedirs(cache_dir, exist_ok=True)
    log_file = os.path.join(cache_dir, "parch-dm.log")

    file_handler = logging.FileHandler(log_file)
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter(log_format))
    parch_logger.addHandler(file_handler)

    if debug_env:
        parch_logger.setLevel(logging.DEBUG)
        for handler in parch_logger.handlers:
            handler.setLevel(logging.DEBUG)
