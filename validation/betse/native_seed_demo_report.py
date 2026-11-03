"""Read saved SEED demonstrations without importing or running BETSE.

A completed report establishes recorded execution and evidence consistency only.
It neither compares numerical solutions nor grants INIT, SIM or restart parity.
Original and disabled flux-inverse modes retain their separate dispositions.
"""

import argparse
import json
from pathlib import Path

from validation import source_snapshot as snapshot
from validation.betse import native_seed_demo_evidence as evidence
from validation.betse import native_single_cell_prefix_payload as payload

KIND = "cells.saved_seed_demo_report@1"
LAUNCH_KINDS = tuple(f"cells.genuine_seed_demo_detached_launch@{v}" for v in (6, 7))
DEMO_KINDS = tuple(f"cells.genuine_seed_core_profiles_junctions_demo@{v}" for v in (2, 3))
ENDPOINTS = ("seed", "init_setup", "init_prelude")
DEMO = "validation/betse/native_seed_demo.py"
LAUNCH = "validation/betse/native_seed_demo_launch.py"
PARAMETER = "validation/betse/betse_native_parameter_world_ready_qualification.py"
GEOMETRY_STAGES = (
    "four_aliases",
    "cell_index",
    "cellVerts",
    "cellMatrices",
    "cell_vols",
    "mem_processing",
    "near_neigh",
    "makeECM",
    "environment",
    "grid_len",
    "make_maskM",
)


def source_plan():
    return dict(
        kind=KIND,
        accepted_launch_kinds=LAUNCH_KINDS,
        accepted_outcome_kinds=DEMO_KINDS,
        endpoints=ENDPOINTS,
        owner_hydration=False,
        model_execution=False,
        numerical_comparison=False,
        polling=False,
        scientific_credit=0,
    )


def require(value, message):
    if not value:
        raise ValueError(message)


class Reader:
    """Bind the files actually read; capture problems remain separate from failures."""

    def __init__(self):
        self.pins, self.issues = {}, []

    def bind(self, row):
        require(type(row) is dict and set(row) == {"path", "sha256"}, "Exact file pin required")
        path = payload._regular(row["path"])
        require(path.is_file() and path.stat().st_nlink == 1, "Regular unlinked file required")
        before = path.stat()
        actual = snapshot.digest(path)
        after = path.stat()
        require(
            (before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns)
            == (after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns),
            "File changed while hashing",
        )
        require(actual == row["sha256"], "Changed file: " + str(path))
        require(self.pins.get(str(path), actual) == actual, "Conflicting saved file pins")
        self.pins[str(path)] = actual
        return path

    def read(self, path, expected=None):
        path = payload._regular(path)
        value, digest = payload._metadata(path, payload.MAX_METADATA, expected)
        self.bind(dict(path=str(path), sha256=digest))
        require(type(value) is dict, "JSON object required: " + str(path))
        return value

    def bound(self, row):
        return self.read(self.bind(row), row["sha256"])

    def check(self, section, function):
        try:
            return function()
        except Exception as error:
            self.issues.append(dict(section=section, type=type(error).__name__, message=str(error)))
            return None


def _plan(reader, path, digest):
    require(
        type(digest) is str and len(digest) == 64 and all(c in "0123456789abcdef" for c in digest),
        "Explicit SHA-256 plan binding required",
    )
    plan = reader.read(path, digest)
    require(plan.get("kind") in LAUNCH_KINDS, "Unsupported launch schema")
    require(plan.get("held") is True and plan.get("automatic_retry") is False, "Held plan required")
    require(plan.get("flux_operator") in ("original", "disabled"), "Unknown flux mode")
    require(plan.get("endpoint", "seed") in ENDPOINTS, "Unknown endpoint")
    source = payload._regular(plan["source"])
    require(
        reader.bind(plan["source_snapshot"]) == source / "SNAPSHOT.json", "Snapshot association"
    )
    manifest = snapshot.verify(source, manifest_sha256=plan["source_snapshot"]["sha256"])
    files = {name: row["sha256"] for name, row in manifest["files"].items()}
    producers = plan["producers"]
    require(all(name in producers for name in (DEMO, LAUNCH, PARAMETER)), "Missing producer roster")
    require(
        all(files.get(name) == sha for name, sha in producers.items()), "Producer source mismatch"
    )
    demo, parameters = reader.bound(plan["demo_plan"]), reader.bound(plan["parameter_inputs"])
    require(
        demo["snapshot_sha256"] == plan["source_snapshot"]["sha256"]
        and Path(demo["parameter_packet"]) / "source" == source
        and Path(demo["parameter_packet"]) / "inputs.json" == Path(plan["parameter_inputs"]["path"])
        and demo["parameter_sha256"] == plan["parameter_inputs"]["sha256"]
        and demo["flux_operator"] == plan["flux_operator"]
        and demo.get("endpoint", "seed") == plan.get("endpoint", "seed")
        and parameters["source_snapshot"] == plan["source_snapshot"]
        and parameters["runtime"] == plan["runtime"],
        "Prepared source/input/endpoint association changed",
    )
    bundle = reader.bound(plan["input_bundle"])
    selected = bundle["modes"][plan["flux_operator"]]
    require(
        selected["program"] == parameters["program"]["manifest"]
        and selected["config"] == parameters["program"]["root"],
        "Actual input mode association changed",
    )
    reader.bind(selected["program"])
    for row in plan["external_files"]:
        reader.bind(row)
    originals = {}
    for name, row in sorted(bundle["source_inventory"]["files"].items()):
        snapshot.relative_path(name)
        originals[name] = row["sha256"]
    require(bool(originals), "Empty original input inventory")
    expected = [
        dict(path=str(Path(selected["config"]) / name), sha256=sha)
        for name, sha in originals.items()
    ]
    require(plan["input_files"] == expected, "Selected input file roster changed")
    for row in expected:
        reader.bind(row)
    return plan, files, originals


def _captures(reader, directory, rows):
    require(type(rows) is list, "Capture list required")
    paths, summary = set(), []
    for row in rows:
        name = row["path"]
        snapshot.relative_path(name)
        require(name not in paths, "Duplicate capture path")
        paths.add(name)
        require(type(row["label"]) is str, "Capture label required")
        require(row["status"] in ("saved", "capture_failed"), "Unknown capture disposition")
        record = dict(row)
        if row["status"] == "saved":
            pins = evidence.files(directory / name, expected_sha256=row["sha256"])
            for pin in pins:
                reader.bind(pin)
            record["verified_files"] = len(pins)
            # Retain only the small linkage inventory in the report. Raw columns,
            # returns and work remain in the hash-bound, fully checked sidecars.
            value = evidence.read(directory / name, expected_sha256=row["sha256"], expand=False)
            if type(value) is dict:
                record["identity"] = value.get("identity")
                if row["label"].endswith(".record"):
                    record["references"] = {
                        key: value[key]
                        for key in (
                            "before",
                            "cache",
                            "helper_cache",
                            "rng_before",
                            "rng_after",
                            "stream_before",
                            "stream_after",
                            "before_MT",
                            "after_MT",
                            "stages",
                        )
                        if key in value
                    }
        else:
            require("error" in row, "Capture failure must retain its error")
        summary.append(record)
    return summary


def _required_captures(captures, labels):
    saved = [row["label"] for row in captures if row["status"] == "saved"]
    require(
        all(saved.count(label) == 1 for label in labels),
        "Missing or duplicate required raw capture",
    )


def _geometry_captures(captures):
    names = ("phase", "lattice", "image", "mesh", "lifecycle", "geometry")
    _required_captures(
        captures,
        [name + ".record" for name in names]
        + [
            "completed_geometry.cache",
            "diagnostics",
            *(f"phase.stage_trials.{index}.cache.cache" for index in range(4)),
        ],
    )
    identities = {row.get("identity") for row in captures if type(row.get("identity")) is str}
    records = {
        row["label"]: row.get("references", {})
        for row in captures
        if row["label"].endswith(".record")
    }
    for name in names[1:]:
        record = records[name + ".record"]
        for field in ("before", "cache"):
            require(
                type(record.get(field)) is str and record[field] in identities,
                "Missing geometry raw cache: " + name + "." + field,
            )
        for field in (
            "helper_cache",
            "rng_before",
            "rng_after",
            "stream_before",
            "stream_after",
            "before_MT",
            "after_MT",
        ):
            if record.get(field) is not None:
                require(record[field] in identities, "Missing geometry RNG/helper capture")
    stages = records["geometry.record"]["stages"]
    require([name for name, _ in stages] == list(GEOMETRY_STAGES), "Geometry stage roster changed")
    require(
        all(identity in identities for _, identity in stages), "Missing intermediate geometry cache"
    )


def _runtime(reader, root, plan, files):
    source, roots = Path(plan["source"]), [Path(p) for p in plan["runtime_roots"]]
    external = {row["path"]: row["sha256"] for row in plan["external_files"]}
    inventories, producers = [], {}
    for name in ("runtime-before.json", "runtime-after.json"):
        value = reader.read(root / name)
        require(value["measured_cpu_affinity"] == [plan["policy"]["cpu"]], "Recorded CPU mismatch")
        require(
            value["executable"] == plan["runtime"]["executable"], "Recorded executable mismatch"
        )
        reader.bind(value["executable"])
        for module, row in value["loaded_files"].items():
            path = reader.bind(row)
            if (
                module == "cells"
                or module.startswith(("cells.", "validation."))
                or path.is_relative_to(source)
            ):
                require(path.is_relative_to(source), "Mutable project producer: " + module)
                relative = str(path.relative_to(source))
                require(files.get(relative) == row["sha256"], "Unbound snapshot producer")
                producers[relative] = row["sha256"]
            else:
                require(
                    any(path.is_relative_to(folder) for folder in roots)
                    or external.get(str(path)) == row["sha256"],
                    "Undeclared loaded origin: " + module,
                )
        for row in value["mapped_files"]:
            reader.bind(row)
        inventories.append(value)
    require(
        all(name in producers for name in (LAUNCH, PARAMETER)), "Actual recorder producers missing"
    )
    require(
        all(
            inventories[1]["loaded_files"].get(k) == v
            for k, v in inventories[0]["loaded_files"].items()
        ),
        "Loaded producer removed or changed during execution",
    )
    after = reader.read(root / "source-after.json")
    require(
        after["source_snapshot"] == plan["source_snapshot"]
        and after["producers"] == plan["producers"],
        "Final source binding changed",
    )
    return dict(
        before_modules=len(inventories[0]["loaded_files"]),
        after_modules=len(inventories[1]["loaded_files"]),
        snapshot_producers=producers,
    )


def _resources(reader, output, plan_path, plan, digest, terminal):
    process_dir = output / "process"
    result = reader.read(
        process_dir / ("failure.json" if (process_dir / "failure.json").exists() else "result.json")
    )
    inputs = reader.read(output / "process/process-inputs.json")
    command = inputs["command"]
    for flag, expected in (
        ("--worker", str(Path(plan_path).absolute())),
        ("--plan-sha256", digest),
        ("--output", str(output / "worker")),
    ):
        require(
            command.count(flag) == 1 and command[command.index(flag) + 1] == expected,
            "Process association changed",
        )
    require(inputs["cwd"] == plan["source"], "Process source directory changed")
    limits, policy = result["limits"], plan["policy"]
    require(
        inputs["limits"] == limits
        and limits["max_wall_seconds"] == policy["wall_seconds"]
        and limits["max_process_tree_rss_bytes"] == policy["max_rss_bytes"]
        and limits["min_available_host_memory_bytes"] == policy["reserve_bytes"]
        and result["process_tree_memory_metric"] == "rss",
        "Resource policy association changed",
    )
    within = (
        result["elapsed_seconds"] <= policy["wall_seconds"]
        and result["sampled_peak_process_tree_rss_bytes"] <= policy["max_rss_bytes"]
        and result["minimum_available_host_memory_bytes"] >= policy["reserve_bytes"]
        and result["samples"] > 0
    )
    if terminal is not None:
        require(
            result == terminal["process"]
            and result["status"] == "completed"
            and result["returncode"] == 0
            and within,
            "Completed worker/resource evidence disagrees",
        )
    return dict(
        result=result, sampled_limits_met=within, high_water_is_distinct_from_sampled_peak=True
    )


def _outcome(reader, root, plan, value):
    require(value.get("kind") in DEMO_KINDS, "Unsupported demo outcome schema")
    require(
        value["flux_operator"] == plan["flux_operator"]
        and value.get("endpoint", "seed") == plan.get("endpoint", "seed"),
        "Outcome mode/endpoint changed",
    )
    require(value["status"] in ("completed", "failed"), "Unknown demo disposition")
    require(
        value["original_flux_defect_repaired"] is False
        and type(value["scientific_or_physical_credit"]) is int
        and value["scientific_or_physical_credit"] == 0
        and type(value["init_time_steps_completed"]) is int
        and value["init_time_steps_completed"] == 0
        and value["complete_seed_runner_or_INIT_SIM_restart_claim"] is False
        and value["stage_work_is_non_additive"] is True,
        "Outcome exceeds the supported demonstration claim",
    )
    captures = _captures(reader, root, value["captures"])
    if value["status"] == "completed":
        stages = ["geometry", "poisson", "core", "profiles", "junctions"]
        endpoint = plan.get("endpoint", "seed")
        if endpoint != "seed":
            stages.append("init_setup")
        if endpoint == "init_prelude":
            stages.append("init_prelude")
        require(
            value["methods_completed"] is True
            and value["primary"] is None
            and value["secondary"] == [],
            "Completed outcome retains a failure",
        )
        require(value["completed_stage_trials"] == stages, "Incomplete or reordered stage trials")
        require(
            value["init_setup_completed"] is (endpoint != "seed")
            and value.get("init_prelude_completed", False) is (endpoint == "init_prelude"),
            "Endpoint completion flags changed",
        )
        required = ["callback", "parameters", "geometry"]
        for name in stages[1:]:
            required.extend((name + "_request", name))
        observed = [
            row["name"] for row in value["operations"] if row["name"] != "profile_image_file"
        ]
        require(
            observed == required
            and all(row["status"] == "returned" for row in value["operations"]),
            "Incomplete or reordered public operations",
        )
        require(
            all(row["status"] == "saved" for row in captures), "Completed outcome has capture gaps"
        )
        labels = [name + ".record" for name in stages[1:]] + [
            "poisson.cache",
            "core.cache",
            "profiles.after",
            "junctions.cache",
        ]
        if endpoint != "seed":
            labels.extend(("init_setup.before", "init_setup.after"))
        if endpoint == "init_prelude":
            labels.extend(("init_prelude.before", "init_prelude.after", "init_prelude.raw_returns"))
        _required_captures(captures, labels)
    return dict(outcome=value, captures=captures)


def inspect_attempt(plan_path, *, plan_sha256, output=None):
    """One explicit read of saved terminal paths; never query or wait on a job."""
    reader = Reader()
    plan, files, originals = _plan(reader, Path(plan_path), plan_sha256)
    report = dict(
        kind=KIND,
        status="prepared_only",
        plan_sha256=plan_sha256,
        flux_operator=plan["flux_operator"],
        endpoint=plan.get("endpoint", "seed"),
        source_files=files,
        original_input_files=originals,
        policy=plan["policy"],
        original_flux_defect_repaired=False,
        numerical_comparison=False,
        scientific_credit=0,
        time_steps_qualified=0,
        restart_qualified=False,
        source_execution_complete=False,
        source_evidence_complete=False,
        evidence_scope=(
            "Endpoint and geometry captures plus declared source/input/runtime/resource/"
            "filesystem records; no live failed-owner serialization claim"
        ),
    )
    if output is not None:
        output = payload._regular(output)
        root = output / "worker"
        names = (
            "result.json",
            "failure.json",
            "worker/failure.json",
            "process/failure.json",
            "worker/demo/outcome.json",
        )
        present = {name for name in names if (output / name).exists()}
        report.update(output=str(output), observed_terminal_files=sorted(present))
        if not present:
            report["status"] = "no_terminal_observed"
        else:
            terminal = (
                reader.check("controller", lambda: reader.read(output / "result.json"))
                if "result.json" in present
                else None
            )
            failures = []
            failure_names = {name for name in present if name.endswith("failure.json")}
            for name in sorted(failure_names):
                failure = reader.check(name, lambda name=name: reader.read(output / name))
                if failure is not None:
                    failures.append(dict(path=name, failure=failure))
            report["failures"] = failures
            report["status"] = "failed" if failure_names else "incomplete_evidence"
            report["resources"] = reader.check(
                "resources",
                lambda: _resources(reader, output, plan_path, plan, plan_sha256, terminal),
            )
            report["runtime"] = reader.check("runtime", lambda: _runtime(reader, root, plan, files))
            raw_outcome = reader.check(
                "outcome_read", lambda: reader.read(root / "demo/outcome.json")
            )
            result = (
                reader.check("outcome", lambda: _outcome(reader, root / "demo", plan, raw_outcome))
                if raw_outcome is not None
                else None
            )
            report["demonstration"] = result
            if raw_outcome is not None and raw_outcome.get("status") == "failed":
                report["status"] = "failed"
                failures.append(dict(path="worker/demo/outcome.json", failure=raw_outcome))
            filesystem = reader.check("filesystem", lambda: reader.read(root / "filesystem.json"))
            if filesystem is not None:
                reader.check(
                    "filesystem_failures",
                    lambda: require(
                        filesystem["failures"] == [] and filesystem["first_error"] is None,
                        "Recorded filesystem failure",
                    ),
                )
            geometry_path = root / "demo/geometry/outcome.json"
            if geometry_path.exists():

                def geometry():
                    value = reader.read(geometry_path)
                    captures = _captures(reader, geometry_path.parent, value["captures"])
                    if value["status"] == "source_completed":
                        require(
                            value["source_completed"] is True
                            and value["source_error"] is None
                            and value["metadata_error"] is None
                            and value["capture_errors"] == []
                            and all(row["status"] == "saved" for row in captures),
                            "Completed geometry retains an execution/capture failure",
                        )
                        _geometry_captures(captures)
                    return dict(status=value["status"], diagnostics=value["diagnostics"])

                report["geometry"] = reader.check("geometry", geometry)
            elif result is not None and result["outcome"]["status"] == "completed":
                reader.issues.append(
                    dict(
                        section="geometry",
                        type="MissingEvidence",
                        message="Completed demonstration lacks geometry outcome",
                    )
                )
            if terminal is not None:

                def completed():
                    require(
                        terminal["kind"] == plan["kind"]
                        and terminal["status"] == "source_completed_unqualified"
                        and terminal["plan_sha256"] == plan_sha256
                        and terminal["scientific_credit"] == 0,
                        "Controller completion binding",
                    )
                    require(
                        Path(terminal["worker"]["path"]) == root / "result.json",
                        "Worker result association",
                    )
                    worker = reader.bound(terminal["worker"])
                    require(
                        worker["kind"] == plan["kind"]
                        and worker["status"] == terminal["status"]
                        and worker["plan_sha256"] == plan_sha256
                        and worker["flux_operator"] == plan["flux_operator"]
                        and worker.get("endpoint", "seed") == report["endpoint"],
                        "Worker completion binding",
                    )
                    require(
                        all(
                            worker.get(k) is True
                            for k in (
                                "public_entry_attempted",
                                "public_entry_returned",
                                "runtime_before_available",
                                "runtime_after_available",
                                "filesystem_audit_installed",
                            )
                        ),
                        "Incomplete worker observations",
                    )
                    require(
                        result is not None and result["outcome"]["status"] == "completed",
                        "Missing completed demonstration",
                    )
                    require(
                        (report.get("geometry") or {}).get("status") == "source_completed",
                        "Geometry did not complete",
                    )

                reader.check("completed_chain", completed)
                if not reader.issues and not failures:
                    report.update(
                        status="completed_unqualified",
                        source_execution_complete=True,
                        source_evidence_complete=True,
                    )
    report["verification_issues"] = reader.issues
    report["observed_file_pins"] = [dict(path=k, sha256=v) for k, v in sorted(reader.pins.items())]
    return report


def compare_modes(original, disabled):
    """Compare two checked execution reports, never their numerical solutions."""
    require(original.get("kind") == disabled.get("kind") == KIND, "Saved report schemas required")
    require(
        original["flux_operator"] == "original" and disabled["flux_operator"] == "disabled",
        "Exact separate original/disabled reports required",
    )
    checks = {
        name: original[name] == disabled[name]
        for name in ("source_files", "original_input_files", "policy", "endpoint")
    }
    complete = all(
        value.get("source_execution_complete") is True
        and value.get("source_evidence_complete") is True
        and value["status"] == "completed_unqualified"
        and value["verification_issues"] == []
        for value in (original, disabled)
    )
    return dict(
        kind=KIND,
        original=original,
        disabled=disabled,
        matching=checks,
        paired_execution_complete=complete and all(checks.values()),
        numerical_equality_checked=False,
        physical_parity=False,
        restart_qualified=False,
        original_flux_defect_repaired=False,
        flux_note=(
            "Original mode retains the native inverse; disabled mode skips that inverse. "
            "Ordinary transport is unchanged."
        ),
        work_ledgers_additive=False,
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", required=True, type=Path)
    parser.add_argument("--plan-sha256", required=True)
    parser.add_argument("--attempt", type=Path)
    parser.add_argument("--disabled-plan", type=Path)
    parser.add_argument("--disabled-plan-sha256")
    parser.add_argument("--disabled-attempt", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    value = inspect_attempt(args.plan, plan_sha256=args.plan_sha256, output=args.attempt)
    if args.disabled_plan is not None:
        require(args.disabled_plan_sha256 is not None, "Disabled plan digest required")
        value = compare_modes(
            value,
            inspect_attempt(
                args.disabled_plan,
                plan_sha256=args.disabled_plan_sha256,
                output=args.disabled_attempt,
            ),
        )
    else:
        require(
            args.disabled_plan_sha256 is None and args.disabled_attempt is None,
            "Disabled plan required",
        )
    if args.output is not None:
        snapshot.write_json(args.output, value)
    else:
        print(json.dumps(value, indent=2, sort_keys=True, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
