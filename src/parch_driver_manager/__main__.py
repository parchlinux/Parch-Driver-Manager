import sys
from typing import List, Optional

from . import __version__
from .log_config import setup_logging


def main(argv: Optional[List[str]] = None) -> int:
    if argv is None:
        argv = sys.argv

    if "--version" in argv or "-v" in argv:
        print(f"Parch Driver Manager {__version__}")
        return 0

    debug = "--debug" in argv or "-d" in argv
    filtered = [a for a in argv if a not in ("--debug", "-d")]

    setup_logging(debug=debug)

    from .ui import main as ui_main

    return ui_main(filtered)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
