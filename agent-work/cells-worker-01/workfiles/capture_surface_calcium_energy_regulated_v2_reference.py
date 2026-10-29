"""Independent @2 channel/junction regulation oracle capture, outside pytest/conftest.

Only the existing independent equations are executed. Production Cells and
JAX imports are forbidden before/after both reference import and integration.
"""

import argparse
import json
import os
import sys
from importlib import metadata
from pathlib import Path


def independent():
    offenders = sorted(k for k in sys.modules if k == "cells" or k.startswith(("cells.", "jax")))
    assert not offenders, offenders
    return offenders


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    before = independent()
    import numpy as np

    from validation.regulation import integrated_network_regulation_v2_reference as reference

    after_import = independent()
    definition = json.loads((args.output / "inputs/v2.json").read_text())
    c, times, state, proof = reference.integrate(definition)
    assert len(c["shapes"]) == 38
    after_capture = independent()
    destination = args.output / "references/v2.npz"
    assert not destination.exists()
    np.savez_compressed(destination, times=times, state=state)
    report = dict(
        status="passed",
        inputs=definition,
        solver=proof,
        fields=list(c["shapes"]),
        times=times.tolist(),
        production_imported=False,
        jax_imported=False,
        independence_guards=dict(
            before_import=before,
            after_reference_import=after_import,
            after_integration=after_capture,
        ),
        execution=dict(
            pid=os.getpid(),
            parent_pid=os.getppid(),
            executable=sys.executable,
            pytest_imported="pytest" in sys.modules,
        ),
        versions={name: metadata.version(name) for name in ("numpy", "scipy")},
    )
    assert not report["execution"]["pytest_imported"]
    (args.output / "evidence/independent-v2.json").write_text(
        json.dumps(report, indent=2, allow_nan=False) + "\n"
    )
    print(
        json.dumps(
            dict(status="passed", pid=os.getpid(), fields=len(c["shapes"]), independent=True)
        )
    )


if __name__ == "__main__":
    main()
