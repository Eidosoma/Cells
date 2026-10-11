"""Launch the registered free-voltage junction panel with the existing detached runner."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "junction_transport"))
from run import main  # noqa: E402

if __name__ == "__main__":
    main(kind="trajectory")
