"""Preserve and replay the failed REF-003d packet without running either model."""

import argparse
import hashlib
import json
import math
import subprocess
import sys
import zipfile
from collections import Counter
from datetime import UTC, datetime

import contact as c
import trajectory_check as check
import trajectory_context as ctx

SESSION = c.ROOT / "runs/ref-003d-2026-09-12/trajectory-01"
ANCHORS = {
    "registration.json": "9f41747f0f59eda41782368adfcf58b734f89ee7c51e2729c9ca9425a754927c",
    "failure.json": "fd5f2baebca2e32a3b108c58628e0c2c9a4f409eb6ab61572a7fe42d593839e8",
    "comparison.json": "c8ae7af0b0c8f0057990dd65cec8f7b46f0183fc69a5fda0b9c677646ddb7ad9",
    "sources.zip": "5c879920a325711a7783f2b656ace71596e8da738bb99a458a2390b7a1313a36",
    "launch.json": "6e1d365bf7609f58963b77e9a655cbc680997270e426aafbf0c6c7b19e13829a",
}
PRESERVATION = c.ROOT / "reports/ref-003d-v2-preservation.json"
AUDIT = c.ROOT / "reports/ref-003d-failure-audit.json"
NEW_FILES = {
    "trajectory_failure.py",
    "trajectory_refinement.py",
    "trajectory_refinement_context.py",
    "trajectory_refinement_check.py",
    "trajectory_refinement_protocol.json",
    "test_refinement.py",
}
ALLOWED_DOCUMENT_EDITS = {
    "PROGRESS.md",
    "README.md",
    "docs/DECISIONS.md",
    "docs/BETSE_REFERENCE_PLAN.md",
    "docs/BETSE_CAPABILITY_ROADMAP.md",
    "docs/BETSE_PASSIVE_TRAJECTORY_PLAN.md",
    "validation/betse/README.md",
}


def files(output):
    ctx.evidence.require_regular_payloads(output)
    return {str(p.relative_to(output)): c.sha(p) for p in sorted(output.rglob("*")) if p.is_file()}


def authenticate(output=SESSION):
    ctx.evidence.require_regular_payloads(output)
    c.require(not (output / "verification.json").exists(), "Failed packet claims qualification")
    c.require(
        all(c.sha(output / name) == digest for name, digest in ANCHORS.items()),
        "Original trajectory evidence changed",
    )
    registered = c.read(output / "registration.json")
    c.require(registered["protocol"] == c.read(ctx.PROTOCOL), "Original protocol changed")
    c.require(
        registered["preservation_sha256"] == c.sha(ctx.PRESERVATION),
        "Original preservation changed",
    )
    c.require(registered["prior_closeout_sha256"] == ctx.PRIOR_SHA, "Original predecessor changed")
    with zipfile.ZipFile(output / "sources.zip") as archive:
        c.require(
            len(archive.namelist()) == len(registered["sources"])
            and set(archive.namelist()) == set(registered["sources"]),
            "Source capsule coverage differs",
        )
        for name, digest in registered["sources"].items():
            c.require(
                hashlib.sha256(archive.read(name)).hexdigest() == digest
                and c.sha(c.HERE / name) == digest,
                "Frozen trajectory source changed",
            )
    failed = c.read(output / "failure.json")
    c.require(
        failed["status"] == "failed_not_qualified"
        and "Trajectory comparison failed; retain full packet" in failed["traceback"],
        "Not the recorded numerical rejection",
    )
    c.require(
        0 < failed["seconds"] < registered["protocol"]["total_timeout_seconds"],
        "Original time budget differs",
    )
    return registered


def preserve():
    authenticate()
    accepted = ctx.authenticate()
    names = (
        subprocess.check_output(
            ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z", "--", "."],
            cwd=c.ROOT,
        )
        .decode()
        .split("\0")
    )
    owned = {"validation/betse/" + name for name in NEW_FILES}
    baseline = {name: c.sha(c.ROOT / name) for name in sorted(set(names) - owned - {""})}
    payloads = files(SESSION)
    value = {
        "schema": "cells.betse_trajectory_refinement_preservation@1",
        "status": "pass",
        "created_utc": datetime.now(UTC).isoformat(),
        "baseline_sha256": baseline,
        "failed_session": str(SESSION.relative_to(c.ROOT)),
        "failed_packet_sha256": payloads,
        "failed_packet_bytes": sum((SESSION / name).stat().st_size for name in payloads),
        "accepted_sources": accepted["implementation_files_sha256"],
        "runtime": accepted["runtime"],
        "anchors": ANCHORS,
    }
    c.write(PRESERVATION, value)
    print(
        json.dumps(
            {
                "status": "preserved",
                "baseline_files": len(baseline),
                "failed_packet_files": len(payloads),
                "failed_packet_bytes": value["failed_packet_bytes"],
            }
        )
    )


def retained(output=SESSION):
    registered = authenticate(output)
    saved = c.read(PRESERVATION)
    c.require(saved["anchors"] == ANCHORS, "Preservation anchors differ")
    c.require(files(output) == saved["failed_packet_sha256"], "Failed packet payload changed")
    return registered


def diagnostic(registered, output):
    """Recalculate endpoint inventories/flux integrals directly, outside the comparator."""
    geometry = registered["geometry"]
    volumes = [v / 1e-15 for v in geometry["cell_volumes_m3"]]
    bath_volume = geometry["effective_bath_volume_m3"] / 1e-15
    local = c.read(output / "cells/passive/jax_jit/0.00005000/result.json")
    inside_local = check.unpack(local["history"]["amount_increment"])[-1]
    outside_local = check.unpack(local["history"]["extracellular_amount_increment"])[-1]
    endpoints, rows = [], []
    for dt in registered["protocol"]["native_steps_s"]:
        native = c.read(output / f"native/passive/matched_constants/{dt:.8f}/observed/result.json")
        initial, steps = native["trace"]["initial"], native["trace"]["steps"]
        final = steps[-1]["after"]
        outside = [
            (final["outside_mM"][s][0] - initial["outside_mM"][s][0]) * bath_volume
            for s in range(3)
        ]
        inside = [
            [(final["inside_mM"][s][i] - initial["inside_mM"][s][i]) * volumes[i] for i in range(7)]
            for s in range(3)
        ]
        endpoints.append(outside)
        rows.append(
            {
                "dt_s": dt,
                "bath_increment_fmol": outside,
                "bath_error_vs_cells_fmol": [outside[s] - outside_local[s][0] for s in range(3)],
                "per_cell_errors_fmol": [
                    [inside[s][i] - inside_local[s][i] for i in range(7)] for s in range(3)
                ],
                "material_residual_fmol": [outside[s] + math.fsum(inside[s]) for s in range(3)],
                "bath_vs_integrated_flux_residual_fmol": [
                    outside[s]
                    + math.fsum(
                        step["density_mol_per_m2_s"][s][j]
                        * geometry["membrane_areas_m2"][j]
                        * dt
                        / 1e-15
                        for step in steps
                        for j in range(30)
                    )
                    for s in range(3)
                ],
            }
        )
    orders = [
        math.log2(abs((endpoints[0][s] - endpoints[1][s]) / (endpoints[1][s] - endpoints[2][s])))
        for s in range(3)
    ]
    return {
        "species": ["Na", "K", "Cl"],
        "endpoints": rows,
        "observed_endpoint_orders": orders,
        "extrapolated_endpoint_error_fmol": [
            2 * endpoints[2][s] - endpoints[1][s] - outside_local[s][0] for s in range(3)
        ],
        "extrapolation_is_qualification": False,
    }


def audit(output=SESSION):
    registered = retained(output)
    ctx.authenticate()
    replay = check.audit_data(registered, output)
    c.require(replay == c.read(output / "comparison.json"), "Frozen comparison replay differs")
    c.require(
        replay["status"] == "failed"
        and replay["comparisons"] == 129384
        and replay["failed_comparisons"] == len(replay["first_failures"]) == 36,
        "Original rejection coverage differs",
    )
    kinds = Counter(row["id"].split("/")[0] for row in replay["first_failures"])
    quantities = Counter("/".join(row["id"].split("/")[-2:]) for row in replay["first_failures"])
    c.require(
        kinds == {"native_refinement": 18, "cross": 18}
        and quantities == {"amount_fmol/21": 12, "amount_fmol/22": 24},
        "Failure classification differs",
    )
    c.require(
        not any(
            n in ("cells", "betse", "jax", "numpy")
            or n.startswith(("cells.", "betse.", "jax.", "numpy."))
            for n in sys.modules
        ),
        "Saved-data audit imported a numerical/model runtime",
    )
    return {
        "schema": "cells.betse_failed_trajectory_audit@1",
        "status": "rejection_confirmed",
        "qualified": False,
        "anchors": ANCHORS,
        "preservation_sha256": c.sha(PRESERVATION),
        "packet_files": len(files(output)),
        "replayed_comparison": replay,
        "independent_endpoint_diagnostic": diagnostic(registered, output),
        "model_calls": 0,
        "full_trajectory_rerun": False,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("preserve", "audit"))
    args = parser.parse_args()
    if args.action == "preserve":
        preserve()
    else:
        result = audit()
        c.write(AUDIT, result)
        print(
            json.dumps(
                {
                    "status": result["status"],
                    "comparisons": result["replayed_comparison"]["comparisons"],
                    "failed_comparisons": 36,
                    "model_calls": 0,
                }
            )
        )
