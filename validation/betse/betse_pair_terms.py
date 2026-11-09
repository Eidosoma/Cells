#!/usr/bin/env python3
"""Plain BETSE against plain BETSE on one seed: step terms and option (artifact) terms.

Reads two ``betse_reference_extract.py`` extractions with the same geometry and writes, per
phase, the difference rows of default_world_adapter's difference budget (BUDGET observables,
per-ion concentration maxima and the interior ECM without the boundary ring). Samples pair at
equal elapsed times; when the second case has the smaller INIT step, its samples pair one of
its steps later (BETSE sample k is the state after k + 1 updates), as in betse-step-term.

Unlike ``default_world_adapter.py betse-step-term``, no adapter mapping checks are made, so it
also serves cases the resolved backend does not map (general network, fast ECM update, ECM
smoothing). No Cells model is involved.

    python3 validation/betse/betse_pair_terms.py --base CASE_A --other CASE_B --out FILE.json
"""

import argparse
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
if __name__ == "__main__":
    for entry in (ROOT / "src", ROOT):
        if str(entry) not in sys.path:
            sys.path.insert(0, str(entry))

from validation.betse import betse_reference_run as reference_run  # noqa: E402
from validation.betse import default_world_adapter as adapter  # noqa: E402


def minimal_world(case):
    """The fields the difference rows read: species, grid, boundary ring, membrane owners."""
    directory, manifest = adapter.load_case(case)
    geometry = np.load(directory / "geometry.npz")
    rows, cols = (int(v) for v in geometry["X"].shape)
    k = np.arange(rows * cols)
    ring = np.flatnonzero(
        (k // cols == 0) | (k % cols == 0) | (k // cols == rows - 1) | (k % cols == cols - 1)
    )
    return {
        "species": list(manifest["ions"]["order"]),
        "grid_shape": (rows, cols),
        "ring_sites": ring,
        "membrane_cell": np.asarray(geometry["mem_to_cells"], dtype=np.int64),
    }


def pair_terms(base, other):
    world = minimal_world(base)
    result = adapter.betse_step_term(world, base, other)
    result["kind"] = "cells.betse_pair_terms@1"
    result["base"], result["other"] = result.pop("dense"), result.pop("fine")
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--base", required=True, help="BETSE case or extraction")
    parser.add_argument("--other", required=True, help="same seed; option or step changed")
    parser.add_argument("--out", required=True, help="fresh JSON file")
    args = parser.parse_args(argv)
    out = reference_run.resolve_out(args.out)
    result = pair_terms(args.base, args.other)
    result["git"] = reference_run.git_provenance(
        [Path(__file__), ROOT / "validation/betse/default_world_adapter.py"]
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    reference_run.write_json(out, adapter.compare.json_safe(result))
    print(json.dumps({"out": str(out)}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
