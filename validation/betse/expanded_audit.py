"""Independent saved expanded-SIM audit; no capture checker, model or array runtime."""

import argparse
import copy
import hashlib
import json
import math
import stat
import sys
import zipfile
from datetime import datetime
from pathlib import Path, PurePosixPath

import contact as c
import expanded_audit_context as ctx
import full_loop_audit as shared
import full_loop_bridge_context as pilot
import trajectory_check as arithmetic
import trajectory_context as numerical
import trajectory_evidence as previous

VARIANTS = ("baseline", "default_profile", "zero_amplitude")
MODES = ("observed", "unobserved")
CORE = {"Dm_cells", "P_cells", "cc_at_mem", "cc_cells", "cc_env", "zs"}
CONTROLS = {"observer_pairs": 36, "variant_comparisons": 24, "pilot_overlap_runs": 12}
SCOPE = (
    "1 ms neutral-prepared seven-cell passive/blocked SIM bridge; "
    "both F/R profiles at 25/12.5/6.25 us; zero-amplitude controls only"
)


def trusted_registration():
    c.require(
        c.sha(ctx.SESSION / "registration.json") == ctx.ANCHORS["registration.json"],
        "Expanded registration anchor changed",
    )
    return c.read(ctx.SESSION / "registration.json")


def expected_rows():
    p = previous.trusted_registration()["protocol"]
    return [
        {"case": case, "profile": profile, "dt_s": dt, "variant": variant}
        for case in p["cases"]
        for profile in p["native_constant_profiles"]
        for dt in p["native_steps_s"]
        for variant in VARIANTS
    ]


def count(row):
    return round(0.001 / row["dt_s"])


def group(row):
    return numerical.key(row["case"]["id"], row["profile"], row["dt_s"])


def is_overlap(row):
    return row["profile"] == "matched_constants" and row["dt_s"] == 0.000025


def expected_paths(registered):
    ctx.capture.validate_plan(registered["plan"])
    c.require(registered["rows"] == expected_rows(), "Expanded row coverage differs")
    paths = set(shared.TOP)
    for row in registered["rows"]:
        for mode in MODES:
            directory = PurePosixPath("native") / pilot.key(row) / mode
            paths |= {
                str(directory / n)
                for n in shared.COMMON | (shared.OBSERVED if mode == "observed" else set())
            }
    return paths


def verify_manifest(output, registered):
    c.require(output.is_dir() and not output.is_symlink(), "Not a regular expanded directory")
    paths = list(output.rglob("*"))
    c.require(
        all(not p.is_symlink() and (p.is_dir() or stat.S_ISREG(p.stat().st_mode)) for p in paths),
        "Expanded packet contains a link or special file",
    )
    receipt = c.read(output / "capture.json")
    expected = expected_paths(registered)
    c.require(set(receipt["files_sha256"]) == expected, "Expanded manifest coverage differs")
    c.require(
        {str(p.relative_to(output)) for p in paths if p.is_file()}
        == expected | shared.OPERATIONAL | {"capture.json"},
        "Unexpected/missing expanded payload",
    )
    c.require(
        all(c.sha(output / n) == h for n, h in receipt["files_sha256"].items()),
        "Expanded payload digest differs",
    )
    c.require(
        all((output / n).stat().st_size > 0 for n in expected if not n.endswith(".log")),
        "Empty expanded payload",
    )
    return receipt


def inspect_metadata(registered, receipt, worker, launch, started):
    plan = registered["plan"]
    expected_paths(registered)
    c.require(
        receipt["schema"] == "cells.betse_expanded_bridge_capture@1"
        and receipt["status"] == "capture_controls_pass_pending_independent_audit"
        and receipt["registration_sha256"] == ctx.ANCHORS["registration.json"]
        and receipt["native_runs"] == 72
        and receipt["observed_steps"] == 3360
        and all(receipt[k] == v for k, v in CONTROLS.items())
        and receipt["trajectory_run"] is True
        and receipt["cells_runs"] == 0,
        "Expanded capture identity/counts differ",
    )
    c.require(
        all(
            receipt[k] is False
            for k in (
                "trajectory_qualified",
                "independent_audit_run",
                "expanded_bridge_qualified",
                "nonzero_intervention",
                "biology_validated",
                "gpu_tested",
                "automatic_retry",
            )
        ),
        "Capture overclaims scope",
    )
    elapsed = receipt["elapsed_seconds"]
    c.require(
        type(elapsed) in (int, float)
        and math.isfinite(elapsed)
        and 0 < elapsed < plan["total_timeout_seconds"],
        "Capture time budget differs",
    )
    c.require(
        launch["status"] == "launched_detached"
        and launch["registration_sha256"] == ctx.ANCHORS["registration.json"]
        and type(started["pid"]) is int
        and started["pid"] == launch["pid"] > 0
        and launch["automatic_polling"] is False
        and launch["independent_audit"] == "await_user_instruction"
        and all(launch[k] == plan[k] for k in ("worker_timeout_seconds", "total_timeout_seconds")),
        "Expanded launch identity differs",
    )
    stamps = [
        datetime.fromisoformat(t)
        for t in (
            registered["registered_utc"],
            launch["launched_utc"],
            started["started_utc"],
            receipt["finished_utc"],
        )
    ]
    c.require(
        all(t.utcoffset() is not None for t in stamps)
        and stamps == sorted(stamps)
        and 0 < (stamps[-1] - stamps[-2]).total_seconds() <= elapsed,
        "Capture chronology differs",
    )
    prior = previous.trusted_registration()
    pilot_worker = c.read(shared.ctx.SESSION / "worker.json")
    c.require(
        worker["schema"] == "cells.betse_expanded_bridge_worker@1"
        and worker["status"] == receipt["status"]
        and worker["warnings"] == []
        and worker["environment"] == pilot_worker["environment"]
        and worker["package_path"] == pilot_worker["package_path"]
        and worker["installed_python_sha256"]
        == {
            n: h
            for n, h in prior["upstream"]["files_sha256"].items()
            if n.startswith("betse/") and n.endswith(".py")
        },
        "Expanded worker provenance differs",
    )
    c.require(
        worker["native_runs"] == 72
        and worker["observed_steps"] == worker["event_dispatch_calls_observed"] == 3360
        and worker["enabled_target_event_dispatches_observed"] == 1120
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
        "Expanded worker counts/scope differ",
    )
    rows = expected_rows()
    expected = []
    for row in rows:
        for mode in MODES:
            path = f"native/{pilot.key(row)}/{mode}/result.json"
            expected.append(
                {
                    "row": row,
                    "mode": mode,
                    "path": path,
                    "sha256": receipt["files_sha256"][path],
                    "status": "capture_row_checks_pass",
                    "observed_steps": count(row) if mode == "observed" else 0,
                }
            )
    c.require(worker["results"] == expected, "Worker result coverage differs")
    c.require(
        worker["observer_pairs"]
        == [{"key": pilot.key(r), "status": "observer_pair_exact"} for r in rows],
        "Worker observer coverage differs",
    )
    c.require(
        worker["variant_controls"]
        == [
            {"key": pilot.key(r), "status": "variant_control_exact", "variant": r["variant"]}
            for r in rows
            if r["variant"] != "baseline"
        ],
        "Worker variant coverage differs",
    )
    c.require(
        worker["pilot_overlap"]
        == [
            {"key": pilot.key(r), "mode": mode, "status": "original_pilot_overlap_exact"}
            for r in rows
            if is_overlap(r)
            for mode in MODES
        ],
        "Worker pilot overlap coverage differs",
    )
    preserved = c.read(ctx.capture.PRESERVATION)
    changes = receipt["changed_documents"]
    c.require(
        set(changes) == ctx.edits.ALLOWED_EDITS
        and all(
            d["before"] == preserved["baseline_sha256"][n] and d["after"] != d["before"]
            for n, d in changes.items()
        )
        and receipt["baseline_files"] == len(preserved["baseline_sha256"]) == 912
        and receipt["unchanged_baseline_files"] == 905
        and receipt["pilot_files_unchanged"] == 142
        and receipt["audit_files_unchanged"] == 11
        and receipt["accepted_implementation_files_unchanged"] == 352
        and receipt["production_modules_unchanged"] == 51,
        "Capture preservation claims differ",
    )


def check_capsule(output, registered):
    with zipfile.ZipFile(output / "sources.zip") as archive:
        names = archive.namelist()
        c.require(
            len(names) == len(set(names)) == 67 and set(names) == set(registered["sources"]),
            "Expanded capsule coverage differs",
        )
        c.require(
            all(
                hashlib.sha256(archive.read(n)).hexdigest() == registered["sources"][n]
                for n in names
            ),
            "Expanded capsule bytes differ",
        )


def inspect_packet(output):
    registered = c.read(output / "registration.json")
    c.require(registered == trusted_registration(), "Unanchored expanded registration")
    receipt = verify_manifest(output, registered)
    preflight = c.read(ctx.capture.PRELAUNCH)
    c.require(
        c.sha(ctx.capture.PRELAUNCH) == ctx.CAPTURE_PREFLIGHT_SHA
        and registered["prelaunch_sha256"] == ctx.CAPTURE_PREFLIGHT_SHA
        and registered["preservation_sha256"] == c.sha(ctx.capture.PRESERVATION)
        and registered["pilot_closeout_sha256"] == ctx.capture.ANCHORS["completion.json"]
        and registered["prior_trajectory_registration_sha256"]
        == previous.ANCHORS["registration.json"]
        and registered["sources"] == preflight["sources"]
        and len(registered["sources"]) == 67,
        "Expanded predecessor/source provenance differs",
    )
    prior = previous.trusted_registration()
    c.require(
        registered["upstream"]["files_sha256"] == prior["upstream"]["files_sha256"],
        "Upstream source differs",
    )
    c.require(
        registered["retained_init_files_sha256"]
        == {
            str(pilot.retained_path(r, mode).relative_to(c.ROOT)): c.sha(
                pilot.retained_path(r, mode)
            )
            for r in expected_rows()
            for mode in MODES
        },
        "Retained INIT links differ",
    )
    check_capsule(output, registered)
    inspect_metadata(
        registered,
        receipt,
        c.read(output / "worker.json"),
        c.read(output / "launch.json"),
        c.read(output / "started.json"),
    )
    size = sum(p.stat().st_size for p in output.rglob("*") if p.is_file())
    c.require(
        size - (output / "capture.json").stat().st_size == receipt["artifact_bytes_before_receipt"]
        and size < registered["plan"]["max_artifact_bytes"],
        "Expanded byte accounting/budget differs",
    )
    c.require(
        all(
            (output / n).stat().st_size <= registered["plan"]["max_worker_file_bytes"]
            for n in expected_paths(registered)
        ),
        "Worker file budget differs",
    )
    return registered, receipt


def prepared_rows():
    return shared.prepared_rows(shared.trusted_registration())


def preparation(row, prepared):
    return prepared[pilot.key(row | {"profile": "matched_constants", "dt_s": 0.000025})]


def expected_metadata(row, prepared, prior):
    """Independent input expectation; no captured entry state is synthesized."""
    result = copy.deepcopy(preparation(row, prepared)["metadata"])
    result["constants"] = prior["base_protocol"]["profiles"][row["profile"]]
    result["dt_s"] = result["sampling_s"] = row["dt_s"]
    result["configured_steps"] = count(row)
    if row["variant"] == "zero_amplitude":
        pulse = c.read(c.HERE / "intervention_plan.json")["candidate_pulse"]
        scale = count(row) / (count(row) - 1)
        for ion in ("Na", "K", "Cl"):
            result["scheduled_options"][ion + "_mem"] = [
                *(pulse[k] * scale for k in ("on_s", "off_s", "transition_s")),
                0.0,
                ["Base"],
                "None",
            ]
    return result


def payload(record, omit=()):
    return {k: v for k, v in record.items() if k not in {"native_yaml_sha256", *omit}}


def audit_row(row, mode, packet, prepared, retained, prior, nonce):
    c.require(row in expected_rows() and mode in MODES, "Unregistered audit row/mode")
    reference = preparation(row, prepared)
    fixed = reference["ready"]["state"]
    result = packet["result"]
    observed = mode == "observed"
    c.require(
        set(packet)
        == {
            "core",
            "result",
            "final_state",
            "final_metadata",
            "started",
            "checks",
        }
        | ({"dynamics", "entry", "metadata", "events"} if observed else set()),
        "Row evidence fields differ",
    )
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
        == {"status": "capture_row_checks_pass", "observed_steps": count(row) if observed else 0},
        "Row start/check coverage differs",
    )
    c.require(
        packet["core"] == reference["core"]
        and result["final_junctions"] == reference["core"]["junctions"],
        "Core geometry/topology changed",
    )
    expected = expected_metadata(row, prepared, prior)
    c.require(
        result["final_metadata"]
        == packet["final_metadata"]
        == expected | {"pickles_present": {"seed": True, "init": False, "sim": True}},
        "Final phase/settings/SIM serialization differs",
    )
    c.require(result["final_state"] == packet["final_state"], "Durable final physical copy differs")
    record = result["numerical"]
    c.require(
        payload(record) == payload(retained), "SIM/retained INIT numerical correspondence differs"
    )
    owners = prior["geometry"]["membrane_owners"]
    final = shared.state_values(result["final_state"], fixed, owners)
    c.require(
        set(record["final"]) == set(numerical.FINAL_NAMES)
        and set(record["ordinary"]) == set(numerical.ORDINARY_NAMES),
        "Numerical array coverage differs",
    )
    c.require(
        all(
            result["final_state"]["arrays"][k] == record["final"][k] for k in numerical.FINAL_NAMES
        ),
        "Final numerical/state links differ",
    )
    for section in ("ordinary", "final"):
        for value in record[section].values():
            arithmetic.unpack(value)
    if not observed:
        c.require(
            record["trace"] is None and result["lifecycle"] is None,
            "Observer-off partner has a trace",
        )
        return 0
    entry, events, trace = packet["entry"], packet["events"], record["trace"]
    initial = entry["state"]
    c.require(
        packet["dynamics"] == packet["core"]
        and packet["metadata"] == expected
        and entry
        == {
            "state": initial,
            "initial": trace["initial"],
            "pre_loop_calls": shared.SETUP,
            "labels_s": trace["labels_s"],
            "sampled_indices": trace["sampled_indices"],
        }
        and result["lifecycle"] == {"calls": shared.SETUP, "run_returns": 1, "hook_restored": True},
        "Native full-loop preparation/lifecycle differs",
    )
    initial_values = shared.state_values(initial, fixed, owners)
    c.require(
        {k: initial["arrays"][k] for k in CORE} == packet["core"]["arrays"]
        and {k: initial_values[n] for k, n in shared.LINKS.items()} == trace["initial"]
        and all(v == 0 for v in arithmetic.numbers(initial_values["fluxes_mem"])),
        "Actual loop-entry INIT/core/flux link differs",
    )
    c.require(
        events["mode"] == "full_sim_loop"
        and events["integration_calls"] == 1
        and events["initial"] == initial
        and events["hook_restored"] is True
        and len(events["events"]) == len(trace["steps"]) == count(row),
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
            and event["before"] == event["after"]
            and step["before_elapsed_s"] == index * row["dt_s"]
            and step["after_elapsed_s"] == (index + 1) * row["dt_s"],
            "No-op event/order/clock differs",
        )
        before = shared.state_values(event["before"], fixed, owners)
        shared.state_values(event["after"], fixed, owners)
        after_flux = shared.state_values(event["before_update"], fixed, owners)
        c.require(
            {k: before[n] for k, n in shared.LINKS.items()} == last,
            "Pre-event/previous step link differs",
        )
        c.require(
            all(v == 0 for v in arithmetic.numbers(before["fluxes_mem"])),
            "Pre-event flux reset differs",
        )
        c.require(
            {k: after_flux[n] for k, n in shared.LINKS.items()} == step["before"]
            and after_flux["fluxes_mem"] == step["density_mol_per_m2_s"]
            and after_flux["fluxes_gj"] == step["junction_density_mol_per_m2_s"],
            "Post-flux/step links differ",
        )
        voltage = list(before["vm"])
        for _ in event["flux_ion_indices"]:
            voltage = [v + nonce for v in voltage]
        c.require(voltage == after_flux["vm"], "Source voltage nonce sequence differs")
        last = step["after"]
    c.require(
        {k: final[n] for k, n in shared.LINKS.items()} == last, "Final/last-step link differs"
    )
    return count(row)


def audit_pair(watched, plain):
    c.require(
        all(watched[k] == plain[k] for k in ("core", "final_state", "final_metadata")),
        "Observer-off physical control differs",
    )
    c.require(
        watched["result"]["row"] == plain["result"]["row"]
        and payload(watched["result"]["numerical"], ("mode", "trace"))
        == payload(plain["result"]["numerical"], ("mode", "trace")),
        "Observer-off numerical control differs",
    )


def audit_variant(baseline, alternate):
    left, right = baseline["result"]["row"], alternate["result"]["row"]
    c.require(
        left["variant"] == "baseline"
        and right["variant"] in VARIANTS[1:]
        and group(left) == group(right),
        "Wrong variant group",
    )
    c.require(
        all(
            baseline[k] == alternate[k]
            for k in ("core", "dynamics", "entry", "events", "final_state")
        ),
        "Profile/no-op physical control differs",
    )
    c.require(
        payload(baseline["result"]["numerical"]) == payload(alternate["result"]["numerical"]),
        "Profile/no-op trajectory differs",
    )


def audit_overlap(row, mode, packet):
    c.require(is_overlap(row), "Outside original pilot overlap")
    original = shared.read_row(shared.ctx.SESSION, row, mode)
    c.require(
        all(packet[k] == original[k] for k in set(packet) - {"result", "started"}),
        "Original pilot physical overlap differs",
    )
    c.require(
        payload(packet["result"]["numerical"]) == payload(original["result"]["numerical"])
        and {k: v for k, v in packet["result"].items() if k != "numerical"}
        == {k: v for k, v in original["result"].items() if k != "numerical"},
        "Original pilot numerical overlap differs",
    )


class VariantChecks(arithmetic.Checks):
    variant = ""

    def compare(self, label, actual, expected, unit, limits):
        super().compare(self.variant + "/" + label, actual, expected, unit, limits)


def audit(output=ctx.SESSION):
    c.require(
        not any(n.split(".")[0] in shared.FORBIDDEN for n in sys.modules),
        "Audit already imported a model/array runtime",
    )
    fence = shared.ImportFence()
    sys.meta_path.insert(0, fence)
    try:
        ctx.preservation_check()
        for n, h in ctx.ANCHORS.items():
            c.require(c.sha(output / n) == h, "Expanded capture anchor changed")
        registered, receipt = inspect_packet(output)
        prior, prepared, nonce = (
            previous.trusted_registration(),
            prepared_rows(),
            shared.voltage_nonce(),
        )
        checks, summaries, steps = VariantChecks(), [], 0
        controls = dict.fromkeys(CONTROLS, 0)
        current_group, baseline = None, None
        for row in registered["rows"]:
            if group(row) != current_group:
                c.require(row["variant"] == "baseline", "Missing first baseline")
                current_group, baseline = group(row), None
            pair = {}
            for mode in MODES:
                packet = shared.read_row(output, row, mode)
                steps += audit_row(
                    row,
                    mode,
                    packet,
                    prepared,
                    c.read(pilot.retained_path(row, mode)),
                    prior,
                    nonce,
                )
                if is_overlap(row):
                    audit_overlap(row, mode, packet)
                    controls["pilot_overlap_runs"] += 1
                pair[mode] = packet
                if mode == "observed":
                    before = checks.count
                    checks.variant = row["variant"]
                    arithmetic.native_record(
                        prior,
                        packet["result"]["numerical"],
                        row["case"],
                        row["profile"],
                        row["dt_s"],
                        checks,
                    )
                    previous.native_links(prior, packet["result"]["numerical"], row["case"])
                    c.require(
                        checks.count - before == 266 + 364 * count(row),
                        "Independent per-row arithmetic coverage differs",
                    )
                    summaries.append({"row": row, "comparisons": checks.count - before})
            audit_pair(pair["observed"], pair["unobserved"])
            controls["observer_pairs"] += 1
            if row["variant"] == "baseline":
                baseline = pair["observed"]
            else:
                audit_variant(baseline, pair["observed"])
                controls["variant_comparisons"] += 1
            print(
                json.dumps({"audited_row": pilot.key(row), "comparisons_so_far": checks.count}),
                flush=True,
            )
        c.require(
            steps == 3360
            and checks.count == ctx.COMPARISONS
            and len(summaries) == 36
            and controls == CONTROLS,
            "Incomplete expanded independent coverage",
        )
        result = {
            "schema": "cells.betse_expanded_bridge_audit@1",
            "status": "pass" if checks.failed_count == 0 else "fail",
            "scope": SCOPE,
            "anchors": ctx.ANCHORS,
            "payload_files": len(receipt["files_sha256"]),
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
            "enabled_target_event_dispatches": 1120,
            "criteria_registration_sha256": previous.ANCHORS["registration.json"],
            "capture_seconds": receipt["elapsed_seconds"],
            "production_calls": 0,
            "model_imports": [],
            "capture_rerun": False,
            "trajectory_qualified": False,
            "qualification_pending_regression_closeout": True,
            "expanded_bridge_qualified": False,
            "cells_runs": 0,
            "nonzero_intervention": False,
            "restart_qualified": False,
            "biology_validated": False,
            "gpu_tested": False,
            "driver_sha256": c.sha(Path(__file__)),
        }
        ctx.preservation_check()
        c.require(
            not any(n.split(".")[0] in shared.FORBIDDEN for n in sys.modules),
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
    c.require(result["status"] == "pass", "Independent expanded numerical checks failed")
