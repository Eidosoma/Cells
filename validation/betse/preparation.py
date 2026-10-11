"""Read-only evidence checks for the rejected native one-cell preparation.

A successful diagnostic audit confirms the mismatch, not numerical alignment.
"""

import argparse
import hashlib
import json
import math
import zipfile
from pathlib import Path

import alignment as a
import contact as c


def audit(output):
    c.require(not (output / "verification.json").exists(), "Not a rejected capture")
    failed = c.read(output / "failure.json")
    c.require(failed["status"] == "failed_not_qualified", "Missing failure status")
    c.require(
        all(
            not (output / name).exists()
            for name in ("betse.json", "cells.json", "cells_definition.json", "comparison.json")
        ),
        "Unexpected downstream numerical evidence",
    )
    registration = c.read(output / "registration.json")
    c.require(registration["source_sha256"] == a.source_hashes(), "Use captured source context")
    c.require(registration["protocol"] == c.read(a.PROTOCOL), "Protocol differs")
    c.require(registration["preservation_sha256"] == c.sha(a.PRESERVATION), "Preservation changed")
    c.require(registration["upstream"] == c.inspect_source(), "Pinned source differs")
    with zipfile.ZipFile(output / "adapter_sources.zip") as archive:
        c.require(
            len(archive.namelist()) == len(a.FILES) and set(archive.namelist()) == set(a.FILES),
            "Capsule coverage differs",
        )
        for name, digest in registration["source_sha256"].items():
            c.require(
                hashlib.sha256(archive.read(name)).hexdigest() == digest, "Capsule bytes differ"
            )
    native = c.read(output / "native_preparation.json")
    c.require(
        native["registration_sha256"] == c.sha(output / "registration.json"),
        "Worker registration differs",
    )
    c.require(
        native["native_config_sha256"] == c.sha(output / "native.yaml"), "Native YAML differs"
    )
    c.require(
        native["configuration_loaded"] is True and native["native_seed_completed"] is True,
        "Native initialization incomplete",
    )
    c.require(
        native["requested_single_cell"] is True and native["cell_count"] == 7,
        "Reported seven-cell mismatch differs",
    )
    c.require(
        native["molecules_enabled"] is False and native["time_integration_run"] is False,
        "Wrong preparation scope",
    )
    c.require(
        "Requested one cell; native seed contains 7 cells"
        in (output / "betse.stderr.log").read_text(),
        "Native shape guard did not fail as recorded",
    )
    p = registration["protocol"]
    c.require(native["constants"] == p["profiles"]["source_constants"], "Native constants differ")
    c.require(
        native["species"] == p["expected_species"] and native["valence"] == p["expected_valence"],
        "Native species differ",
    )
    c.require(
        native["environment"]["python"] == "3.13.5"
        and Path(native["environment"]["executable"]) == c.REFERENCE_PYTHON
        and native["environment"]["packages"] == c.locked_reference_packages(),
        "Native environment differs",
    )
    expected = {
        k: v
        for k, v in registration["upstream"]["files_sha256"].items()
        if k.startswith("betse/") and k.endswith(".py")
    }
    c.require(native["installed_python_sha256"] == expected, "Native installed sources differ")
    n, m = native["cell_count"], native["membrane_count"]
    c.require(m >= n and set(native["membrane_owners"]) == set(range(n)), "Membrane owners differ")
    c.require(
        len(native["membrane_owners"]) == len(native["membrane_areas_m2"]) == m,
        "Membrane shape differs",
    )
    c.require(
        len(native["cell_centres_m"])
        == len(native["cell_volumes_m3"])
        == len(native["cell_areas_m2"])
        == n,
        "Cell shape differs",
    )
    for point in native["cell_centres_m"]:
        c.require(len(point) == 2 and all(math.isfinite(v) for v in point), "Invalid cell centre")
    c.require(
        all(
            math.isfinite(v) and v > 0
            for v in native["cell_volumes_m3"]
            + native["cell_areas_m2"]
            + native["membrane_areas_m2"]
        ),
        "Invalid geometry",
    )
    for i, area in enumerate(native["cell_areas_m2"]):
        face_sum = math.fsum(
            ar
            for owner, ar in zip(
                native["membrane_owners"], native["membrane_areas_m2"], strict=True
            )
            if owner == i
        )
        c.require(math.isclose(area, face_sum, rel_tol=1e-13), "Native area ownership differs")
    for field, expected_values, count in (
        ("native_initial_inside_mM", p["inside_mM"], n),
        ("native_initial_outside_mM", p["outside_mM"], m),
    ):
        c.require(len(native[field]) == 6, "Concentration species shape differs")
        for row, value in zip(native[field], expected_values, strict=True):
            c.require(
                len(row) == count
                and all(math.isclose(v, value, abs_tol=2e-12, rel_tol=2e-11) for v in row),
                "Native initialized concentrations differ",
            )
    c.require(0 <= failed["seconds"] <= p["total_timeout_seconds"], "Failure exceeded time budget")
    c.require(
        sum(path.stat().st_size for path in output.rglob("*") if path.is_file())
        <= p["max_artifact_bytes"],
        "Failure exceeded storage budget",
    )
    a.authenticate()
    return {
        "schema": "cells.betse_preparation_diagnostic_audit@1",
        "status": "mismatch_confirmed",
        "alignment_qualified": False,
        "requested_cells": 1,
        "actual_cells": n,
        "actual_membranes": m,
        "network_disabled": True,
        "installed_python_files_authenticated": len(expected),
        "files_sha256": {
            str(path.relative_to(output)): c.sha(path)
            for path in output.rglob("*")
            if path.is_file()
        },
        "upstream_calls": 0,
        "production_calls": 0,
        "trajectory_calls": 0,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--receipt", type=Path, required=True)
    args = parser.parse_args()
    result = audit(args.output.resolve())
    c.write(args.receipt, result)
    print(json.dumps({k: v for k, v in result.items() if k != "files_sha256"}))
