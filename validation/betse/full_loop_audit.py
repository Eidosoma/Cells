"""Independent offline audit of the narrow SIM pilot; never load model pickles."""

import argparse
import ast
import hashlib
import importlib.abc
import json
import math
import stat
import struct
import sys
import zipfile
from datetime import datetime
from pathlib import Path, PurePosixPath

import contact as c
import full_loop_audit_context as ctx
import full_loop_bridge_context as pilot
import trajectory_check as arithmetic
import trajectory_evidence as previous

OPERATIONAL = {"launch.json", "runner.stdout.log", "runner.stderr.log"}
TOP = {
    "registration.json",
    "sources.zip",
    "started.json",
    "worker.json",
    "worker.log",
    "matplotlib-cache/fontlist-v3.11.0.json",
}
COMMON = {
    "started.json",
    "core.json",
    "final-state.json",
    "final-metadata.json",
    "result.json",
    "checks.json",
    "native.yaml",
    "INITS/world_1.betse.gz",
    "SIMS/sim_1.betse.gz",
}
OBSERVED = {"dynamics.json", "loop-entry.json", "loop-metadata.json", "events.json"}
LINKS = {
    "inside_mM": "cc_cells",
    "outside_mM": "cc_env",
    "voltage_V": "vm",
    "rho_C_per_m3": "rho_cells",
    "inward_current_A": "I_mem",
    "boundary_voltage_V": "Phi_b",
}
FIXED = {
    "Dm_cells",
    "Dm_base",
    "Dm_scheduled",
    "P_cells",
    "P_base",
    "P_mod",
    "zs",
    "NaKATP_block",
    "CaATP_block",
    "gj_block",
    "Phi_b",
}
SETUP = {"run_sim_core": 1, "init_dynamics": 1, "clear_storage": 1, "pre_loop_update_V": 1}
FORBIDDEN = {"cells", "betse", "numpy", "jax"}


class ImportFence(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split(".")[0] in FORBIDDEN:
            raise RuntimeError("Offline audit forbids model/array import: " + fullname)


def trusted_registration():
    c.require(
        c.sha(ctx.SESSION / "registration.json") == ctx.ANCHORS["registration.json"],
        "Pilot input anchor changed",
    )
    return c.read(ctx.SESSION / "registration.json")


def expected_paths(registered):
    pilot.validate_plan(registered["plan"])
    c.require(registered["rows"] == pilot.rows(registered["plan"]), "Pilot row coverage differs")
    result = set(TOP)
    for row in registered["rows"]:
        for mode in pilot.MODES:
            directory = PurePosixPath("native") / pilot.key(row) / mode
            result |= {
                str(directory / name)
                for name in COMMON | (OBSERVED if mode == "observed" else set())
            }
    return result


def verify_manifest(output, registered):
    """Structure/digest checks also work on rehashed pytest-owned corruptions."""
    c.require(output.is_dir() and not output.is_symlink(), "Not a regular pilot directory")
    paths = list(output.rglob("*"))
    c.require(
        all(not p.is_symlink() and (p.is_dir() or stat.S_ISREG(p.stat().st_mode)) for p in paths),
        "Pilot contains a link or special file",
    )
    capture = c.read(output / "capture.json")
    expected = expected_paths(registered)
    c.require(set(capture["files_sha256"]) == expected, "Pilot manifest coverage differs")
    c.require(
        {str(p.relative_to(output)) for p in paths if p.is_file()}
        == expected | OPERATIONAL | {"capture.json"},
        "Unexpected/missing pilot payload",
    )
    c.require(
        all(c.sha(output / n) == h for n, h in capture["files_sha256"].items()),
        "Pilot payload digest differs",
    )
    c.require(
        all((output / n).stat().st_size > 0 for n in expected if not n.endswith(".log")),
        "Empty pilot payload",
    )
    return capture


def inspect_packet(output):
    registered = c.read(output / "registration.json")
    c.require(registered == trusted_registration(), "Unanchored pilot registration")
    capture = verify_manifest(output, registered)
    prelaunch = c.read(pilot.PRELAUNCH)
    c.require(
        c.sha(pilot.PRELAUNCH) == ctx.PILOT_PRELAUNCH_SHA
        and registered["prelaunch_sha256"] == ctx.PILOT_PRELAUNCH_SHA
        and registered["preservation_sha256"] == c.sha(pilot.PRESERVATION)
        and registered["prior_handoff_sha256"] == pilot.PRIOR_SHA
        and registered["prior_trajectory_registration_sha256"]
        == previous.ANCHORS["registration.json"],
        "Pilot predecessor/prospective checks differ",
    )
    c.require(
        registered["sources"] == prelaunch["sources"] and len(registered["sources"]) == 58,
        "Captured pilot source set differs",
    )
    with zipfile.ZipFile(output / "sources.zip") as archive:
        names = archive.namelist()
        c.require(
            len(names) == len(set(names)) == 58 and set(names) == set(registered["sources"]),
            "Pilot capsule coverage differs",
        )
        c.require(
            all(
                hashlib.sha256(archive.read(n)).hexdigest() == registered["sources"][n]
                for n in names
            ),
            "Pilot capsule bytes differ",
        )
    c.require(
        capture["schema"] == "cells.betse_full_loop_bridge_capture@1"
        and capture["status"] == "capture_controls_pass_pending_independent_audit"
        and capture["registration_sha256"] == c.sha(output / "registration.json")
        and capture["native_runs"] == 12
        and capture["observed_steps"] == 240
        and capture["trajectory_run"] is True
        and capture["cells_runs"] == 0,
        "Capture identity/counts differ",
    )
    c.require(
        all(
            capture[k] is False
            for k in (
                "trajectory_qualified",
                "independent_audit_run",
                "expanded_bridge_qualified",
                "nonzero_intervention",
                "biology_validated",
                "gpu_tested",
            )
        ),
        "Capture overclaims scope",
    )
    elapsed = capture["elapsed_seconds"]
    c.require(
        type(elapsed) in (int, float)
        and math.isfinite(elapsed)
        and 0 < elapsed < registered["plan"]["total_timeout_seconds"],
        "Pilot time budget differs",
    )
    launch, started = c.read(output / "launch.json"), c.read(output / "started.json")
    c.require(
        launch["status"] == "launched_detached"
        and launch["registration_sha256"] == ctx.ANCHORS["registration.json"]
        and type(started["pid"]) is int
        and started["pid"] == launch["pid"] > 0
        and launch["automatic_polling"] is False
        and launch["independent_audit"] == "await_user_instruction"
        and all(
            launch[k] == registered["plan"][k]
            for k in ("worker_timeout_seconds", "total_timeout_seconds")
        ),
        "Pilot launch identity differs",
    )
    stamps = [
        datetime.fromisoformat(t)
        for t in (
            registered["registered_utc"],
            launch["launched_utc"],
            started["started_utc"],
            capture["finished_utc"],
        )
    ]
    c.require(
        all(t.utcoffset() is not None for t in stamps)
        and stamps == sorted(stamps)
        and 0 < (stamps[-1] - stamps[-2]).total_seconds() <= elapsed,
        "Pilot chronology differs",
    )
    size = sum(p.stat().st_size for p in output.rglob("*") if p.is_file())
    c.require(
        size - (output / "capture.json").stat().st_size == capture["artifact_bytes_before_receipt"]
        and size < registered["plan"]["max_artifact_bytes"],
        "Pilot byte accounting/budget differs",
    )
    c.require(
        all(
            (output / n).stat().st_size <= registered["plan"]["max_worker_file_bytes"]
            for n in expected_paths(registered)
        ),
        "Worker file budget differs",
    )
    worker = c.read(output / "worker.json")
    prior = previous.trusted_registration()
    reference = c.read(c.ROOT / c.read(pilot.PRIOR)["native_attempt"] / "worker.json")
    c.require(
        worker["schema"] == "cells.betse_full_loop_bridge_worker@1"
        and worker["status"] == capture["status"]
        and worker["warnings"] == []
        and worker["environment"] == reference["environment"]
        and worker["package_path"]
        == str(c.REFERENCE_PYTHON.parent.parent / "lib/python3.13/site-packages/betse")
        and worker["installed_python_sha256"]
        == {
            n: h
            for n, h in prior["upstream"]["files_sha256"].items()
            if n.startswith("betse/") and n.endswith(".py")
        },
        "Native worker provenance differs",
    )
    c.require(
        worker["native_runs"] == 12
        and worker["observed_steps"] == worker["event_dispatch_calls_observed"] == 240
        and worker["enabled_target_event_dispatches_observed"] == 80
        and worker["trajectory_run"] is True
        and worker["cells_runs"] == 0
        and all(
            worker[k] is False
            for k in (
                "trajectory_qualified",
                "expanded_bridge_qualified",
                "nonzero_intervention",
                "biology_validated",
                "gpu_tested",
            )
        ),
        "Worker counts/scope differ",
    )
    expected_results = []
    for row in registered["rows"]:
        for mode in pilot.MODES:
            path = f"native/{pilot.key(row)}/{mode}/result.json"
            expected_results.append(
                {
                    "row": row,
                    "mode": mode,
                    "path": path,
                    "sha256": c.sha(output / path),
                    "status": "capture_row_checks_pass",
                    "observed_steps": 40 if mode == "observed" else 0,
                }
            )
    c.require(
        worker["results"] == expected_results
        and worker["observer_pairs"] == [{"status": "observer_pair_exact"}] * 6
        and worker["variant_controls"]
        == [{"status": "profile_and_noop_controls_exact", "comparisons": 2}] * 2,
        "Worker row/control coverage differs",
    )
    return registered, capture


def voltage_nonce():
    path = c.SOURCE / "betse/science/sim_toolbox.py"
    expected = previous.trusted_registration()["upstream"]["files_sha256"][
        "betse/science/sim_toolbox.py"
    ]
    c.require(c.sha(path) == expected, "Native flux source changed")
    function = next(
        n
        for n in ast.parse(path.read_text()).body
        if isinstance(n, ast.FunctionDef) and n.name == "electroflux"
    )
    values = [
        ast.literal_eval(n.value)
        for n in ast.walk(function)
        if isinstance(n, ast.Assign)
        and any(isinstance(t, ast.Name) and t.id == "FLOAT_NONCE" for t in n.targets)
    ]
    additions = [
        n
        for n in ast.walk(function)
        if isinstance(n, ast.AugAssign) and isinstance(n.target, ast.Name) and n.target.id == "vBA"
    ]
    c.require(
        values == [1e-25]
        and len(additions) == 1
        and isinstance(additions[0].op, ast.Add)
        and isinstance(additions[0].value, ast.Name)
        and additions[0].value.id == "FLOAT_NONCE",
        "Native nonce semantics changed",
    )
    return values[0]


def typed_values(record, expected_shape):
    if record.get("dtype") == "<i8":
        values = arithmetic.shaped(record["values"], record["shape"])
        c.require(
            all(type(v) is int and -(2**63) <= v < 2**63 for v in values), "Non-integer valence"
        )
        digest = hashlib.sha256(b"".join(struct.pack("<q", v) for v in values)).hexdigest()
        c.require(digest == record["bytes_sha256"], "Integer array digest differs")
    else:
        arithmetic.unpack(record)
    c.require(
        record["shape"] == expected_shape
        and set(record) == {"dtype", "shape", "values", "bytes_sha256"},
        "Typed array shape/fields differ",
    )
    return record["values"]


def state_values(state, initial, owners):
    c.require(
        set(state) == set(initial) and set(state["arrays"]) == set(initial["arrays"]),
        "Event-state field coverage differs",
    )
    c.require(
        all(state[k] == initial[k] for k in initial if k != "arrays"),
        "Event temperature/scaling changed",
    )
    arrays = state["arrays"]
    values = {}
    for name, baseline in initial["arrays"].items():
        record = arrays[name]
        if "scalar" in baseline:
            c.require(
                record == baseline and type(record["scalar"]) is int,
                "Native scalar representation changed",
            )
        else:
            c.require(record["dtype"] == baseline["dtype"], "Event dtype changed")
            values[name] = typed_values(record, baseline["shape"])
        if name in FIXED:
            c.require(record == baseline, "Inactive event changed a fixed state/control")
    c.require(
        values["cc_at_mem"] == [[v[i] for i in owners] for v in values["cc_cells"]],
        "Membrane ownership differs",
    )
    c.require(
        all(v == 0 for v in arithmetic.numbers(values["fluxes_gj"])),
        "Disabled junction transported",
    )
    return values


def read_row(output, row, mode):
    directory = output / "native" / pilot.key(row) / mode
    names = {
        "core": "core.json",
        "result": "result.json",
        "final_state": "final-state.json",
        "final_metadata": "final-metadata.json",
        "started": "started.json",
        "checks": "checks.json",
    }
    if mode == "observed":
        names |= {
            "dynamics": "dynamics.json",
            "entry": "loop-entry.json",
            "metadata": "loop-metadata.json",
            "events": "events.json",
        }
    result = {k: c.read(directory / n) for k, n in names.items()}
    c.require(
        result["result"]["numerical"]["native_yaml_sha256"] == c.sha(directory / "native.yaml"),
        "Row YAML link differs",
    )
    return result


def audit_row(row, mode, packet, prepared, retained, prior, nonce):
    result, initial = packet["result"], prepared["ready"]["state"]
    c.require(
        result["row"] == row
        and result["mode"] == mode
        and result["hook_restored"] is True
        and result["schema"] == "cells.betse_full_loop_bridge_row@1"
        and result["status"] == "exported_not_qualified",
        "Row identity/scope differs",
    )
    c.require(
        packet["started"]["row"] == row
        and packet["started"]["mode"] == mode
        and packet["checks"]
        == {"status": "capture_row_checks_pass", "observed_steps": 40 if mode == "observed" else 0},
        "Row start/check coverage differs",
    )
    c.require(
        packet["core"] == prepared["core"]
        and result["final_junctions"] == prepared["core"]["junctions"],
        "Core geometry/topology changed",
    )
    c.require(
        result["final_metadata"]
        == packet["final_metadata"]
        == prepared["metadata"] | {"pickles_present": {"seed": True, "init": False, "sim": True}},
        "Final phase/settings/SIM pickle metadata differs",
    )
    c.require(result["final_state"] == packet["final_state"], "Durable final physical copy differs")
    numerical = result["numerical"]
    c.require(
        {k: v for k, v in numerical.items() if k != "native_yaml_sha256"}
        == {k: v for k, v in retained.items() if k != "native_yaml_sha256"},
        "SIM/retained INIT numerical correspondence differs",
    )
    owners = prior["geometry"]["membrane_owners"]
    final = state_values(result["final_state"], initial, owners)
    c.require(
        all(
            result["final_state"]["arrays"][k] == numerical["final"][k] for k in numerical["final"]
        ),
        "Final numerical/state links differ",
    )
    for group in ("ordinary", "final"):
        for record in numerical[group].values():
            arithmetic.unpack(record)
    if mode == "unobserved":
        c.require(
            numerical["trace"] is None and result["lifecycle"] is None,
            "Observer-off partner has a trace",
        )
        return 0
    entry, events, trace = packet["entry"], packet["events"], numerical["trace"]
    c.require(
        packet["dynamics"] == packet["core"]
        and packet["metadata"] == prepared["metadata"]
        and entry
        == {
            "state": initial,
            "initial": trace["initial"],
            "pre_loop_calls": SETUP,
            "labels_s": trace["labels_s"],
            "sampled_indices": trace["sampled_indices"],
        }
        and result["lifecycle"] == {"calls": SETUP, "run_returns": 1, "hook_restored": True},
        "Native full-loop preparation/lifecycle differs",
    )
    before_values = state_values(initial, initial, owners)
    c.require(
        {k: before_values[n] for k, n in LINKS.items()} == trace["initial"],
        "Loop-entry snapshot link differs",
    )
    c.require(
        events["mode"] == "full_sim_loop"
        and events["integration_calls"] == 1
        and events["initial"] == initial
        and events["hook_restored"] is True
        and len(events["events"]) == len(trace["steps"]) == 40,
        "Event coverage differs",
    )
    last = trace["initial"]
    for index, (event, step) in enumerate(zip(events["events"], trace["steps"], strict=True)):
        c.require(
            set(event)
            == {"index", "raw_label_s", "flux_ion_indices", "before", "after", "before_update"}
            and event["index"] == index == step["index"]
            and event["raw_label_s"] == trace["labels_s"][index] == step["raw_label_s"]
            and event["flux_ion_indices"] == list(range(6))
            and event["before"] == event["after"],
            "No-op event/order differs",
        )
        before = state_values(event["before"], initial, owners)
        state_values(event["after"], initial, owners)
        after_flux = state_values(event["before_update"], initial, owners)
        c.require(
            {k: before[n] for k, n in LINKS.items()} == last, "Pre-event/previous step link differs"
        )
        c.require(
            all(v == 0 for v in arithmetic.numbers(before["fluxes_mem"])),
            "Pre-event flux reset differs",
        )
        c.require(
            {k: after_flux[n] for k, n in LINKS.items()} == step["before"]
            and after_flux["fluxes_mem"] == step["density_mol_per_m2_s"]
            and after_flux["fluxes_gj"] == step["junction_density_mol_per_m2_s"],
            "Post-flux/step links differ",
        )
        voltage = list(before["vm"])
        for _ in event["flux_ion_indices"]:
            voltage = [v + nonce for v in voltage]
        c.require(voltage == after_flux["vm"], "Source voltage nonce sequence differs")
        last = step["after"]
    c.require({k: final[n] for k, n in LINKS.items()} == last, "Final/last-step link differs")
    return 40


def prepared_rows(registered):
    directory = c.ROOT / c.read(pilot.PRIOR)["native_attempt"]
    return {
        pilot.key(row): {
            name: c.read(directory / f"preparation-{i:02d}" / (name + ".json"))
            for name in ("core", "ready", "metadata")
        }
        for i, row in enumerate(registered["rows"])
    }


def audit_controls(packets, registered):
    for row in registered["rows"]:
        watched, plain = (packets[pilot.key(row), mode] for mode in pilot.MODES)
        for part in ("core", "final_state", "final_metadata"):
            c.require(watched[part] == plain[part], "Observer-off physical control differs")
        c.require(
            all(
                watched["result"]["numerical"][k] == plain["result"]["numerical"][k]
                for k in ("ordinary", "final")
            ),
            "Observer-off numerical control differs",
        )
    for case in registered["plan"]["case_ids"]:
        variants = {
            row["variant"]: packets[pilot.key(row), "observed"]
            for row in registered["rows"]
            if row["case"]["id"] == case
        }
        for variant in ("default_profile", "zero_amplitude"):
            c.require(
                all(
                    variants[variant][k] == variants["baseline"][k]
                    for k in ("core", "dynamics", "entry", "events", "final_state")
                ),
                "Profile/no-op physical control differs",
            )
            c.require(
                all(
                    variants[variant]["result"]["numerical"][k]
                    == variants["baseline"]["result"]["numerical"][k]
                    for k in ("ordinary", "final", "trace")
                ),
                "Profile/no-op trajectory differs",
            )
    return {"observer_pairs": 6, "variant_comparisons": 4}


def audit(output=ctx.SESSION):
    c.require(
        not any(n.split(".")[0] in FORBIDDEN for n in sys.modules),
        "Audit already imported a model/array runtime",
    )
    fence = ImportFence()
    sys.meta_path.insert(0, fence)
    try:
        ctx.preservation_check()
        for name, digest in ctx.ANCHORS.items():
            c.require(c.sha(output / name) == digest, "Pilot anchor changed")
        registered, capture = inspect_packet(output)
        prior = previous.trusted_registration()
        prepared, nonce = prepared_rows(registered), voltage_nonce()
        checks, packets, summaries, steps = arithmetic.Checks(), {}, [], 0
        for row in registered["rows"]:
            for mode in pilot.MODES:
                packet = read_row(output, row, mode)
                steps += audit_row(
                    row,
                    mode,
                    packet,
                    prepared[pilot.key(row)],
                    c.read(pilot.retained_path(row, mode)),
                    prior,
                    nonce,
                )
                packets[pilot.key(row), mode] = packet
                if mode == "observed":
                    before = checks.count
                    arithmetic.native_record(
                        prior,
                        packet["result"]["numerical"],
                        row["case"],
                        row["profile"],
                        row["dt_s"],
                        checks,
                    )
                    previous.native_links(prior, packet["result"]["numerical"], row["case"])
                    summaries.append({"row": row, "comparisons": checks.count - before})
        controls = audit_controls(packets, registered)
        c.require(
            steps == 240 and checks.count == 88956 and len(summaries) == 6,
            "Incomplete independent numerical coverage",
        )
        result = {
            "schema": "cells.betse_full_loop_pilot_audit@1",
            "status": "pass" if checks.failed_count == 0 else "fail",
            "scope": (
                "1 ms neutral-prepared seven-cell passive/blocked SIM pilot; "
                "matched constants at 25 us only"
            ),
            "anchors": ctx.ANCHORS,
            "payload_files": len(capture["files_sha256"]),
            "capsule_sources": len(registered["sources"]),
            "comparisons": checks.count,
            "failed_comparisons": checks.failed_count,
            "maximum_normalized_error": checks.maximum,
            "worst": checks.worst,
            "failures": checks.failures,
            "row_summaries": summaries,
            "observed_steps": steps,
            "controls": controls,
            "voltage_nonce_V": nonce,
            "enabled_target_event_dispatches": 80,
            "criteria_registration_sha256": previous.ANCHORS["registration.json"],
            "capture_seconds": capture["elapsed_seconds"],
            "production_calls": 0,
            "model_imports": [],
            "capture_rerun": False,
            "trajectory_qualified": False,
            "qualification_pending_regression_closeout": True,
            "expanded_bridge_qualified": False,
            "new_refinement_run": False,
            "cells_runs": 0,
            "nonzero_intervention": False,
            "restart_qualified": False,
            "biology_validated": False,
            "gpu_tested": False,
            "driver_sha256": c.sha(Path(__file__)),
        }
        ctx.preservation_check()
        c.require(
            not any(n.split(".")[0] in FORBIDDEN for n in sys.modules),
            "Offline import fence breached",
        )
        return result
    finally:
        sys.meta_path.remove(fence)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--receipt", type=Path, required=True)
    args = parser.parse_args()
    result = audit()
    c.write(args.receipt, result)
    print(
        json.dumps(
            {"status": result["status"], "comparisons": result["comparisons"], "model_imports": []}
        )
    )
    c.require(result["status"] == "pass", "Independent pilot numerical checks failed")
