"""Capture actual clean interpreter bootstrap using only stdlib runner helpers."""

import json
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
from runtime_inventory import inventory  # noqa: E402 -- set policy before the helper import

if __name__ == "__main__":
    target = Path(sys.argv[1])
    row = inventory()
    expected_cpu = (
        int(sys.argv[2])
        if len(sys.argv) > 2
        else json.loads(Path(__file__).with_name("plan.json").read_text())["cpu"]
    )
    assert sorted(os.sched_getaffinity(0)) == [expected_cpu]
    assert "sitecustomize" in row["loaded_files"]
    assert not any(
        name.split(".")[0]
        in {"cells", "betse", "validation", "tests", "numpy", "scipy", "jax", "jaxlib"}
        for name in row["loaded_files"]
    )
    with target.open("x") as stream:
        json.dump(row, stream, indent=2, allow_nan=False)
        stream.write("\n")
