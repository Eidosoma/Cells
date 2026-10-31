"""Runner-only pytest provenance; no scientific hooks or test modifications."""

import os
import traceback
from pathlib import Path

from common import write
from runtime_inventory import inventory


def pytest_sessionfinish(session, exitstatus):
    folder = Path(os.environ["CELLS_INIT_RUNNER_METADATA"])
    try:
        write(folder / "pytest-runtime.json", inventory())
        write(
            folder / "pytest-exit.json",
            dict(exitstatus=int(exitstatus), no_scientific_hooks=True),
        )
    except BaseException as error:
        write(
            folder / "pytest-runtime-failure.json",
            dict(
                type=type(error).__name__,
                message=str(error),
                traceback=traceback.format_exc(),
                original_exitstatus=int(exitstatus),
            ),
        )
        session.exitstatus = 1
