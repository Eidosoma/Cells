"""Read-only REF-003c evidence closeout; preserve the frozen capture/checker sources."""

import argparse
import json
import math
import xml.etree.ElementTree as ET
from pathlib import Path

import alignment as a
import cluster_alignment as cluster
import contact as c
import geometry_probe as geometry

SESSION = c.ROOT / "runs/ref-003c-2026-09-12/cluster-01"
CAPTURE_SHA = "ca064838d5177543b7b51f8a226f89df18ecfea5d0e51cbf5e04243da42e91c8"
GEOMETRY_SHA = "7c37798dc3700419fb690e7c9857a493cccfd09c95522ec0d360ac95ef2b3b28"


def require_regular_payloads(output):
    c.require(output.is_dir() and not output.is_symlink(), "Not a regular evidence directory")
    c.require(
        all(not p.is_symlink() for p in output.rglob("*")), "Evidence contains a symbolic link"
    )


def geometry_audit(output):
    """Authenticate the diagnostic and its negative meaning, not just its envelope."""
    require_regular_payloads(output)
    result = geometry.audit(output)
    registered = c.read(output / "registration.json")
    native = c.read(output / "native_result.json")
    completed = c.read(output / "completion.json")
    c.require(registered["schema"] == "cells.betse_svg_geometry_probe@1", "Geometry schema differs")
    c.require(registered["base_protocol"] == c.read(a.PROTOCOL), "Geometry base inputs differ")
    c.require(
        registered["prior_handoff_sha256"] == c.sha(geometry.PRIOR_HANDOFF),
        "Geometry predecessor differs",
    )
    c.require(
        completed["one_cell_seed_succeeded"] is False
        and native["native_seed_completed"] is False
        and "cell_count" not in native
        and "membrane_count" not in native,
        "A failed seed must not claim a completed one-cell geometry",
    )
    c.require(
        type(native["requested_explicit_centres"]) is int
        and native["requested_explicit_centres"] == 1,
        "Requested centre count differs",
    )
    c.require(
        c.sha(output / "single_cell.svg") == registered["sources"]["single_cell.svg"],
        "SVG input differs from registered source",
    )
    circles = (
        ET.parse(output / "single_cell.svg")
        .getroot()
        .findall(".//{http://www.w3.org/2000/svg}circle")
    )
    c.require(len(circles) == 1, "SVG does not contain exactly one centre")
    c.require(
        native["exception_type"] == "QhullError"
        and "not enough points(1)" in native["exception"]
        and "trimesh_core_calcs" in native["traceback"]
        and "Delaunay(self.tri_verts)" in native["traceback"],
        "Not the recorded native one-point triangulation rejection",
    )
    c.require(
        native["warnings"]
        == [
            {"category": "RuntimeWarning", "message": "invalid value encountered in scalar divide"}
        ],
        "Geometry failure warning record differs",
    )
    expected_sources = {
        k: v
        for k, v in registered["upstream"]["files_sha256"].items()
        if k.startswith("betse/") and k.endswith(".py")
    }
    c.require(
        native["installed_python_sha256"] == expected_sources, "Geometry installed source differs"
    )
    c.require(
        native["environment"]["packages"] == c.locked_reference_packages()
        and native["environment"]["python"] == "3.13.5"
        and Path(native["environment"]["executable"]) == c.REFERENCE_PYTHON,
        "Geometry runtime differs",
    )
    c.require(
        type(completed["seconds"]) in (int, float)
        and math.isfinite(completed["seconds"])
        and 0 <= completed["seconds"] < 30,
        "Geometry time budget differs",
    )
    return result | {
        "schema": "cells.betse_svg_negative_evidence_audit@1",
        "status": "native_one_centre_rejection_confirmed",
        "explicit_svg_centres": len(circles),
        "installed_python_files": len(expected_sources),
        "production_calls": 0,
        "alignment_qualified": False,
    }


def audit(output):
    """Replay the frozen arithmetic and independently anchor joint provenance claims."""
    require_regular_payloads(output)
    registered = c.read(output / "registration.json")
    receipt = c.read(output / "verification.json")
    c.require(
        registered["schema"] == "cells.betse_cluster_alignment_registration@1"
        and receipt["schema"] == "cells.betse_cluster_alignment_capture@1",
        "Cluster evidence schema differs",
    )
    c.require(receipt["trajectory_run"] is False, "Capture receipt overclaims trajectory scope")
    preserved = c.authenticate_cells()
    c.require(
        registered["cells_runtime"] == preserved["runtime"],
        "Registered Cells runtime differs from accepted runtime",
    )
    # Use the independently retained preparation, not two mutually agreeing copies.
    protocol = c.read(cluster.PROTOCOL)
    source = c.ROOT / protocol["geometry_source"]
    prior = c.read(source)
    c.require(
        registered["expected_geometry"] == {key: prior[key] for key in cluster.GEOMETRY_FIELDS},
        "Registered geometry differs from retained native preparation",
    )
    result = cluster.audit(output)
    diagnostic = geometry_audit(cluster.GEOMETRY_PROBE)
    return result | {
        "schema": "cells.betse_cluster_evidence_audit@1",
        "scope": "Initialization, instantaneous RHS and prescribed updates; no trajectory",
        "geometry_diagnostic": diagnostic,
        "accepted_implementation_files": len(preserved["implementation_files_sha256"]),
        "biology_validated": False,
        "trajectory_run": False,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("kind", choices=("cluster", "geometry"))
    parser.add_argument("output", type=Path)
    parser.add_argument("--receipt", type=Path, required=True)
    args = parser.parse_args()
    result = (audit if args.kind == "cluster" else geometry_audit)(args.output.resolve())
    c.write(args.receipt, result)
    print(json.dumps(result))
