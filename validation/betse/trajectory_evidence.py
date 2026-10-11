"""Read-only REF-003d v2 closeout, independent of either model's integration code."""

import argparse
import hashlib
import json
import math
import stat
import sys
import zipfile
from datetime import datetime
from pathlib import Path, PurePosixPath

import alignment as a
import contact as c
import trajectory_context as original
import trajectory_failure as prior
import trajectory_refinement_check as frozen
import trajectory_refinement_context as ctx
from trajectory_check import numbers, unpack

SESSION = c.ROOT / "runs/ref-003d-v2-2026-09-12/trajectory-01"
ANCHORS = {
    "verification.json": "05d982137e940f6f1479df1552ddc287fbd6cae702c43ae3b6b0999b35efcff0",
    "registration.json": "b3a26038fec113443f6a57ca1b4ac3b6c905d7be2f9d629d2d839c9cdb12c883",
    "comparison.json": "227bdeb196948d3bc63f1f217fa97c75c6b75acbcdaadcbcbf20bdd5a0767a35",
    "sources.zip": "f89a295c1490d8b501f635c740dbb103ec2fb892ab66ea57a30242a2708700ab",
}
OPERATIONAL = {"launch.json", "runner.stdout.log", "runner.stderr.log"}
TOP_PAYLOADS = {
    "betse.json",
    "cells.json",
    "comparison.json",
    "registration.json",
    "sources.zip",
    "started.json",
    "betse.stdout.log",
    "betse.stderr.log",
    "cells.stdout.log",
    "cells.stderr.log",
    "matplotlib-cache/fontlist-v3.11.0.json",
}


def trusted_registration():
    c.require(
        c.sha(SESSION / "registration.json") == ANCHORS["registration.json"],
        "Retained registration anchor changed",
    )
    return c.read(SESSION / "registration.json")


def expected_paths(registered):
    p = registered["protocol"]
    native = {
        original.key(case["id"], profile, dt): {
            mode: f"native/{original.key(case['id'], profile, dt)}/{mode}/result.json"
            for mode in ("observed", "unobserved")
        }
        for case in p["cases"]
        for profile in p["native_constant_profiles"]
        for dt in p["native_steps_s"]
    }
    local = {name: f"cells/{name}/result.json" for name in registered["cells_definitions"]}
    payloads = TOP_PAYLOADS | set(local.values())
    for pair in native.values():
        for name in pair.values():
            parent = PurePosixPath(name).parent
            payloads |= {
                str(parent / suffix)
                for suffix in (
                    "result.json",
                    "native.yaml",
                    "INITS/world_1.betse.gz",
                    "INITS/init_1.betse.gz",
                )
            }
    return native, local, payloads


def verify_manifest(output, registered):
    """Check coverage and digests even for rehashed test copies, without trusting a summary."""
    c.require(output.is_dir() and not output.is_symlink(), "Not a regular evidence directory")
    paths = list(output.rglob("*"))
    c.require(
        all(not p.is_symlink() and (stat.S_ISREG(p.stat().st_mode) or p.is_dir()) for p in paths),
        "Evidence contains a link or special file",
    )
    receipt = c.read(output / "verification.json")
    payloads = receipt["files_sha256"]
    c.require(
        all(
            isinstance(n, str)
            and not PurePosixPath(n).is_absolute()
            and ".." not in PurePosixPath(n).parts
            and str(PurePosixPath(n)) == n
            for n in payloads
        ),
        "Unsafe manifest path",
    )
    expected = expected_paths(registered)[2]
    c.require(set(payloads) == expected, "Payload coverage differs")
    actual = {str(p.relative_to(output)) for p in paths if p.is_file()}
    c.require(
        actual == expected | OPERATIONAL | {"verification.json"},
        "Unexpected or missing evidence file",
    )
    c.require(
        all(c.sha(output / name) == digest for name, digest in payloads.items()),
        "Payload digest differs",
    )
    for name in expected:
        if not name.endswith(".log"):
            c.require((output / name).stat().st_size > 0, "Empty evidence payload")
    return receipt


def inspect_packet(output):
    """Anchor metadata separately from the frozen numerical replay and receipt hash."""
    registered = c.read(output / "registration.json")
    ctx.validate_registration(registered)
    trusted = trusted_registration()
    c.require(registered["sources"] == trusted["sources"], "Source coverage/identity differs")
    with zipfile.ZipFile(output / "sources.zip") as archive:
        names = archive.namelist()
        c.require(
            len(names) == len(set(names)) == 35 and set(names) == set(trusted["sources"]),
            "Source capsule coverage differs",
        )
        c.require(
            all(
                hashlib.sha256(archive.read(n)).hexdigest() == trusted["sources"][n] for n in names
            ),
            "Source capsule bytes differ",
        )
    receipt = verify_manifest(output, registered)
    p = registered["protocol"]
    c.require(
        receipt["schema"] == "cells.betse_trajectory_refinement_capture@1"
        and receipt["status"] == "pass"
        and receipt["trajectory_run"] is True
        and receipt["biological_validation"] is False,
        "Capture scope/status differs",
    )
    c.require(
        receipt["registration_sha256"] == c.sha(output / "registration.json"),
        "Capture registration differs",
    )
    times = receipt["worker_seconds"]
    c.require(set(times) == {"betse", "cells"}, "Worker time coverage differs")
    for value, limit in [(receipt["seconds"], p["total_timeout_seconds"])] + [
        (value, p["worker_timeout_seconds"]) for value in times.values()
    ]:
        c.require(
            type(value) in (int, float) and math.isfinite(value) and 0 < value < limit,
            "Capture time budget differs",
        )
    c.require(sum(times.values()) <= receipt["seconds"], "Worker times exceed total")
    launched, started = c.read(output / "launch.json"), c.read(output / "started.json")
    c.require(
        launched["status"] == "launched_detached"
        and launched["registration_sha256"] == c.sha(output / "registration.json")
        and type(started["pid"]) is int
        and started["pid"] > 0
        and started["pid"] == launched["pid"],
        "Launch/start identity differs",
    )
    stamps = [
        datetime.fromisoformat(value)
        for value in (
            registered["registered_utc"],
            launched["launched_utc"],
            started["started_utc"],
            receipt["finished_utc"],
        )
    ]
    c.require(
        all(t.utcoffset() is not None for t in stamps)
        and stamps == sorted(stamps)
        and (stamps[-1] - stamps[-2]).total_seconds() <= receipt["seconds"],
        "Capture chronology differs",
    )
    actual_bytes = sum(q.stat().st_size for q in output.rglob("*") if q.is_file())
    c.require(
        receipt["artifact_bytes_before_receipt"]
        == actual_bytes - (output / "verification.json").stat().st_size
        and actual_bytes < p["max_artifact_bytes"],
        "Artifact budget/accounting differs",
    )
    old_baseline = c.read(ctx.PRESERVATION)["baseline_sha256"]
    preservation = receipt["preservation"]
    changed = preservation["changed_documents"]
    c.require(
        set(changed) == prior.ALLOWED_DOCUMENT_EDITS
        and all(
            entry["before"] == old_baseline[n] and entry["after"] != entry["before"]
            for n, entry in changed.items()
        )
        and preservation["baseline_files"] == len(old_baseline)
        and preservation["unchanged_baseline_files"] == len(old_baseline) - len(changed)
        and preservation["accepted_implementation_files_unchanged"] == 352
        and preservation["production_modules_unchanged"] == 51,
        "Capture preservation claims differ",
    )
    # Historical document 'after' hashes are capture-time claims, not a demand that
    # current status documents remain frozen. Closeout records their new edits separately.
    native, local = c.read(output / "betse.json"), c.read(output / "cells.json")
    a.provenance(registered, native, local)
    c.require(
        native["results"] == expected_paths(registered)[0]
        and local["results"] == expected_paths(registered)[1],
        "Worker coverage/paths differ",
    )
    c.require(
        native["engine"] == "actual_betse_full_init_loop"
        and local["engine"] == "unchanged_cells_checked_rk4_runner"
        and native["trajectory_run"] is local["trajectory_run"] is True
        and local["device"] == "cpu"
        and local["x64_enabled"] is True
        and local["jit_disabled"] is False,
        "Worker execution context differs",
    )
    for worker in (native, local):
        c.require(
            worker["registration_sha256"] == c.sha(output / "registration.json"),
            "Worker registration differs",
        )
        c.require(worker["warnings"] == [], "Unexpected worker warning")
    return registered, receipt


def native_links(registered, record, case):
    """Cross-link auxiliary exports; do not reinterpret a saved final flux as a final RHS."""
    count = round(registered["protocol"]["duration_s"] / record["dt_s"])
    c.require(len(record["trace"]["steps"]) == count, "Observer step coverage differs")

    def take(group, name, shape):
        array = record[group][name]
        c.require(array["shape"] == shape, "Auxiliary exported shape differs")
        return unpack(array)

    last = record["trace"]["steps"][-1]
    for name, expected in (
        ("fluxes_mem", last["density_mol_per_m2_s"]),
        ("fluxes_gj", last["junction_density_mol_per_m2_s"]),
    ):
        c.require(take("final", name, [6, 30]) == expected, "Final flux/observer link differs")
    c.require(
        take("final", "Phi_b", [100]) == last["after"]["boundary_voltage_V"],
        "Final boundary/observer link differs",
    )
    ci = take("final", "cc_cells", [6, 7])
    mapped = [[row[i] for i in registered["geometry"]["membrane_owners"]] for row in ci]
    c.require(
        take("final", "cc_at_mem", [6, 30]) == mapped,
        "Membrane concentration owner mapping differs",
    )
    diffusion = take("final", "Dm_cells", [6, 30])
    b = registered["base_protocol"]
    c.require(
        all(
            math.isclose(
                v,
                b["permeability_m_per_s"][s] * b["thickness_m"] * case["availability"],
                rel_tol=2e-15,
                abs_tol=0,
            )
            for s, row in enumerate(diffusion)
            for v in row
        ),
        "Final diffusion/permeability link differs",
    )
    c.require(
        take("ordinary", "dd_time", [count - 1, 6, 30]) == [diffusion] * (count - 1),
        "Constant diffusion history differs",
    )
    c.require(
        numbers(take("ordinary", "rate_NaKATP_time", [count - 1, 30]))
        == [0.0] * ((count - 1) * 30),
        "Disabled pump history differs",
    )
    # Native non-voltage-sensitive gates stay open; gj_surface=0 disables transport.
    # Gate openness is explicitly NOT evidence of nonzero junction transport.
    c.require(
        numbers(take("ordinary", "gjopen_time", [count - 1, 30])) == [1.0] * ((count - 1) * 30),
        "Constant junction gate history differs",
    )
    return count


def audit(output=SESSION):
    for name, digest in ANCHORS.items():
        c.require(c.sha(output / name) == digest, "Retained capture anchor changed")
    registered, receipt = inspect_packet(output)
    comparison = frozen.audit_data(registered, output)
    c.require(comparison == c.read(output / "comparison.json"), "Saved numerical replay differs")
    c.require(
        comparison["status"] == "pass"
        and comparison["failed_comparisons"] == 0
        and comparison["comparisons"] == 435144,
        "Incomplete numerical acceptance",
    )
    steps = 0
    for case in registered["protocol"]["cases"]:
        for profile in registered["protocol"]["native_constant_profiles"]:
            for dt in registered["protocol"]["native_steps_s"]:
                name = original.key(case["id"], profile, dt)
                steps += native_links(
                    registered, c.read(output / f"native/{name}/observed/result.json"), case
                )
    c.require(steps == comparison["native_steps_observed"] == 1120, "Observed total differs")
    forbidden = {"cells", "betse", "numpy", "jax"}
    c.require(
        not any(n.split(".")[0] in forbidden for n in sys.modules),
        "Saved-data audit imported a simulator or numerical runtime",
    )
    accepted = c.authenticate_cells()
    return {
        "schema": "cells.betse_trajectory_evidence_audit@1",
        "status": "pass",
        "scope": "1 ms neutral-prepared seven-cell passive/blocked finite bath only",
        "anchors": ANCHORS,
        "payload_files": len(receipt["files_sha256"]),
        "capsule_sources": len(registered["sources"]),
        "accepted_implementation_files": len(accepted["implementation_files_sha256"]),
        "retained_failed_packet_files": len(prior.files(prior.SESSION)),
        "auxiliary_export_runs_checked": 12,
        "native_steps_observed": steps,
        "comparison": comparison,
        "production_calls": 0,
        "model_imports": [],
        "capture_rerun": False,
        "trajectory_qualified": True,
        "original_v1_qualified": False,
        "one_cell_alignment_qualified": False,
        "biology_validated": False,
        "betse_family_parity": False,
        "gpu_tested": False,
        "driver_sha256": c.sha(Path(__file__)),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=SESSION)
    parser.add_argument("--receipt", type=Path, required=True)
    args = parser.parse_args()
    result = audit(args.output)
    c.write(args.receipt, result)
    print(
        json.dumps(
            {
                "status": result["status"],
                "comparisons": result["comparison"]["comparisons"],
                "production_calls": 0,
            }
        )
    )
