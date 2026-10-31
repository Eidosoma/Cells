"""Freeze and run one independent original-source comparison of a saved prefix.

Preparation is metadata only. A separate exact-plan release permits one native
reference child, followed by the stdlib comparator. No Cells trajectory is
replayed, no retry is automatic, and matched source caches do not establish
physical accuracy or full application equivalence.
"""

import argparse
import hashlib
import json
import os
import resource
import runpy
import sys
import traceback
from pathlib import Path

from validation import source_snapshot
from validation.betse import native_single_cell_prefix_native as native
from validation.betse import native_single_cell_prefix_qualification as prior

ROOT = Path(__file__).resolve().parents[2]
OWN = "validation/betse/native_single_cell_prefix_comparison.py"
NATIVE = "validation/betse/native_single_cell_prefix_native.py"
COMPARE = "validation/betse/native_single_cell_prefix_compare.py"
TEST = "tests/unit/test_native_single_cell_prefix_native.py"
ORCHESTRATION_TEST = "tests/unit/test_native_single_cell_prefix_comparison.py"
KINDS = (
    "cells.single_cell_prefix_comparison_plan@1",
    "cells.single_cell_prefix_comparison_release@1",
)
METHODS = ("before", *native.METHODS)
ENDPOINTS = ("near_neigh", "makeECM", "make_maskM")
ENVIRONMENT_STORE_LINES = (521, 533, 534, 535, 536, 1118, 1119, 1122, 1127, 1128, 1129, 1130, 1131)
ENVIRONMENT_STORE_ROSTER = (
    "_conf",
    "world_len",
    "cell_radius",
    "cell_lattice_disorder",
    "cell_lattice_type",
    "plot_grid_size",
    "wsx",
    "wsy",
    "cell_height",
    "cell_space",
    "ac",
    "scale_cell",
    "tm",
    "d_cell",
    "nx",
    "ny",
    "wsx",
    "wsy",
)
ENVIRONMENT_INLINE_SITE = "betse/science/cells.py:make_world.grid_len"


def endpoint(value):
    if type(value) is not str or value not in ENDPOINTS:
        raise ValueError("Comparison supports only near_neigh, makeECM or make_maskM")
    return value


def _same(left, right):
    # JSON metadata equality retains scalar types, signed zero and list order.
    return json.dumps(left, sort_keys=True, allow_nan=False) == json.dumps(
        right, sort_keys=True, allow_nan=False
    )


def _identity(value):
    if (
        type(value) is not str
        or len(value) != 64
        or any(c not in "0123456789abcdef" for c in value)
    ):
        raise ValueError("Missing exact saved identity")
    return value


def _completed_trial(trial):
    if (
        type(trial) is not dict
        or trial.get("source_completed") is not True
        or any(
            key not in trial or trial[key] is not None
            for key in ("failure_stage", "failure_type", "failure_message")
        )
        or any(
            trial.get(key) is not None
            for key in ("source_error", "capture_error", "observer_error")
        )
    ):
        raise ValueError("Saved trial is incomplete or records a source/capture failure")
    for key in ("identity", "parent_identity", "request_identity"):
        _identity(trial[key])


def capture_lineage(values, configuration, stop_after):
    """Check available saved associations without replaying or issuing owners.

    The geometry prefix Request and its later live continuation Request have
    different identities. Their equality is deliberately not asserted. Frozen
    diagnostic source/plan and every capture remain bound separately.
    """
    endpoint(stop_after)
    if len(values) != len(prior.stage_names(stop_after)):
        raise ValueError("Require every declared saved capture")
    first, initial, core, request, geometry = values[:5]
    try:
        if (
            initial["request_identity"] != _identity(first["request"]["identity"])
            or initial["status"] != "source_completed_unqualified"
            or initial["constructor_completed"] is not True
            or initial["pre_mesh_completed"] is not True
            or any(
                initial[key] is not None
                for key in ("failure_stage", "failure_type", "failure_message")
            )
            or not _same(core["initial_request"], first["request"])
            or not _same(core["initial_state"], initial)
        ):
            raise ValueError("Changed saved initial/core lineage")
        parameters = request["prefix_request"]["parameter_request"]
        if (
            not _same(parameters["core_request"], core)
            or not _same(json.loads(parameters["configuration_json"]), configuration)
            or parameters["projection"]
            != ("environment_mask" if stop_after == "make_maskM" else "initial_geometry")
            or parameters.get("grid_descriptor")
            != ("native_grid_size_yaml_alias@1" if stop_after != "near_neigh" else None)
        ):
            raise ValueError("Changed saved geometry parameter/core lineage")
        for value in (initial, core, request, request["prefix_request"], parameters):
            _identity(value["identity"])
        _completed_trial(geometry)
        if [row[0] for row in geometry["stages"]] != list(METHODS):
            raise ValueError("Incomplete saved geometry stage order")
        if stop_after != "near_neigh":
            continuation, ecm = values[5:7]
            _completed_trial(ecm)
            if type(continuation) is not dict or set(continuation) != {
                "law",
                "geometry_trial",
                "parameter_trial",
                "selected_descriptor",
                "boundary",
                "invalidated_owners",
                "physical_checkpoint_admitted",
            }:
                raise ValueError("Incomplete saved ECM continuation record")
            request_digest = hashlib.sha256(
                json.dumps(
                    continuation, sort_keys=True, separators=(",", ":"), allow_nan=False
                ).encode()
            ).hexdigest()
            if (
                continuation["law"] != "betse_owned_single_cell_makeECM@1"
                or continuation["boundary"] != "ordinary makeECM; stop before environment"
                or continuation["physical_checkpoint_admitted"] is not False
                or continuation["geometry_trial"] != geometry["identity"]
                or ecm["parent_identity"] != geometry["identity"]
                or ecm["request_identity"] != request_digest
                or not _same(ecm["stream_before"], geometry["stream_after"])
            ):
                raise ValueError("Changed saved geometry/ECM request, parent or stream lineage")
            _identity(continuation["parameter_trial"])
        if stop_after == "make_maskM":
            environment_request, environment = values[7:9]
            _completed_trial(environment)
            if (
                geometry.get("parameter_projection") != "environment_mask"
                or not _same(geometry.get("parameter_store_lines"), list(ENVIRONMENT_STORE_LINES))
                or not _same(geometry.get("parameter_store_roster"), list(ENVIRONMENT_STORE_ROSTER))
            ):
                raise ValueError("Saved geometry lacks the original fresh ENV13 parameter stores")
            if type(environment_request) is not dict or set(environment_request) != {
                "law",
                "parent",
                "methods",
                "parameter",
                "boundary",
                "invalidated_owners",
                "full_make_world_Parameters_YAML_phase_physical_checkpoint",
            }:
                raise ValueError("Incomplete saved environment continuation record")
            request_digest = hashlib.sha256(
                json.dumps(
                    environment_request, sort_keys=True, separators=(",", ":"), allow_nan=False
                ).encode()
            ).hexdigest()
            if (
                environment_request["law"] != "betse_owned_single_cell_environment_mask@1"
                or environment_request["boundary"] != "before first environmental makeLaplacian"
                or environment_request["full_make_world_Parameters_YAML_phase_physical_checkpoint"]
                is not False
                or environment_request["parent"] != ecm["identity"]
                or environment_request["parameter"] != continuation["parameter_trial"]
                or not _same(
                    environment_request["invalidated_owners"], continuation["invalidated_owners"]
                )
                or environment_request["methods"] != list(native.ENVIRONMENT_STAGES)
                or environment["parent_identity"] != ecm["identity"]
                or environment["request_identity"] != request_digest
                or not _same(environment["stream_before"], ecm["stream_after"])
                or [row[0] for row in environment["stages"]] != list(native.ENVIRONMENT_STAGES)
            ):
                raise ValueError(
                    "Changed saved ECM/environment request, parent, stage or stream lineage"
                )
    except (KeyError, TypeError, IndexError) as error:
        raise ValueError("Malformed saved prefix lineage") from error


def saved_prefix(diagnostic, parent):
    result = prior.read(diagnostic / "result.json")
    recorded = prior.read(diagnostic / "diagnostic.json")
    stop = endpoint(recorded.get("stop_after", "near_neigh"))
    if (
        result.get("status") != "completed_unqualified"
        or "failure" not in result
        or result["failure"] is not None
        or result.get("diagnostic") != prior.pin(diagnostic / "diagnostic.json")
        or result.get("stop_after", "near_neigh") != stop
        or recorded.get("status") != "source_completed_unqualified"
        or recorded.get("completed_stages") != list(prior.stage_names(stop))
        or "observer_error" not in recorded
        or "source_error" not in recorded
        or any(
            recorded.get(key) is not None
            for key in (
                "observer_error",
                "source_error",
                "failed_stage",
                "interrupted_exception_graph",
            )
        )
    ):
        raise ValueError("Require a completed exact-endpoint diagnostic without failures")
    parent_plan = prior.verify_plan(parent, recorded["plan_sha256"])
    if parent_plan.get("stop_after", "near_neigh") != stop:
        raise ValueError("Diagnostic and parent endpoints differ")
    case = recorded["case"]
    if case not in prior.CASES or case != result["case"]:
        raise ValueError("Unregistered saved input case")
    captures = recorded["captures"]
    if [row.get("label") for row in captures] != list(prior.stage_names(stop)) or any(
        row.get("status") != "saved" for row in captures
    ):
        raise ValueError("Incomplete or reordered saved captures")
    values, paths = [], set()
    for row in captures:
        relative = source_snapshot.relative_path(row["path"])
        path = diagnostic / relative
        if relative in paths or prior.pin(path)["sha256"] != row["sha256"]:
            raise ValueError("Duplicated or changed saved stage capture")
        paths.add(relative)
        values.append(prior.read(path))
    capture_lineage(values, parent_plan["configuration"], stop)
    return stop, case, parent_plan, captures, values[0]["native_comparison_inputs"]


def metadata_modules(plan):
    """Map the exact allowed native metadata modules to their pinned files."""
    stop = endpoint(plan.get("stop_after", "near_neigh"))
    allowed = native.metadata_imports_for(stop)
    pins = native.pins_for(stop)
    if len(allowed) != len(set(allowed)):
        raise ValueError("Repeated metadata import permission")
    rows = {}
    for name in allowed:
        if (
            type(name) is not str
            or not (name == "betse" or name.startswith("betse."))
            or name == "betse.science"
            or name.startswith("betse.science.")
        ):
            raise ValueError("Native science/package permission is not a metadata module")
        stem = name.replace(".", "/")
        candidates = [p for p in (stem + ".py", stem + "/__init__.py") if p in pins]
        if len(candidates) != 1:
            raise ValueError("Metadata module lacks a unique original source pin: " + name)
        relative = candidates[0]
        rows[name] = dict(
            path=str(Path(plan["native_source_root"]) / relative), sha256=pins[relative]
        )
    return rows


def import_guard(plan, attempted):
    allowed = metadata_modules(plan)

    def guard(event, args):
        if event != "import":
            return
        name = args[0]
        root = name.split(".")[0]
        if root in {"cells", "jax", "jaxlib"} or (root == "betse" and name not in allowed):
            attempted.append(name)
            raise ImportError("Independent reference refuses model/package imports: " + name)

    return guard


def verify_metadata_modules(plan, modules=None):
    allowed = metadata_modules(plan)
    modules = sys.modules if modules is None else modules
    observed = {}
    for name, module in list(modules.items()):
        root = name.split(".")[0]
        if root in {"cells", "jax", "jaxlib"}:
            raise ValueError("Independent worker contains a prohibited model module: " + name)
        if root != "betse":
            continue
        if name not in allowed:
            raise ValueError("Unlisted native metadata import: " + name)
        expected = allowed[name]
        file = getattr(module, "__file__", None)
        origin = getattr(getattr(module, "__spec__", None), "origin", None)
        if file != expected["path"] or origin != expected["path"] or prior.pin(file) != expected:
            raise ValueError("Changed native metadata producer origin/hash: " + name)
        observed[name] = expected
    return observed


def retained_inputs(plan):
    stop = endpoint(plan.get("stop_after", "near_neigh"))
    names = (
        ("input_capture", "owned_trial")
        if stop == "near_neigh"
        else ("input_capture", "owned_geometry", "owned_ecm")
    )
    if stop == "make_maskM":
        names += ("owned_environment",)
    return [plan[name] for name in names]


def inline_assignment_sites(sites, stop_after):
    """Bind the actual make_world assignment separately from callable methods."""
    if endpoint(stop_after) != "make_maskM":
        return {}
    if type(sites) is not dict:
        raise ValueError("Missing original inline source roster")
    site = sites.get(ENVIRONMENT_INLINE_SITE)
    if (
        type(site) is not dict
        or set(site) != {"first_line", "last_line", "ast_sha256"}
        or type(site["first_line"]) is not int
        or type(site["last_line"]) is not int
        or site["first_line"] != 494
        or site["last_line"] != 494
    ):
        raise ValueError("Missing exact original inline grid_len assignment site")
    _identity(site["ast_sha256"])
    return {ENVIRONMENT_INLINE_SITE: dict(site)}


def protected_output(output, prepared, plan):
    output = prior.execution_output(output, prepared, plan)
    if any(
        Path(row["path"]).is_relative_to(output) or output.is_relative_to(Path(row["path"]))
        for row in retained_inputs(plan)
    ):
        raise ValueError("Output overlaps retained input evidence")
    return output


def unique_pins(rows):
    pins = {}
    for row in rows:
        if row["path"] in pins and pins[row["path"]] != row:
            raise ValueError("Conflicting retained/native source pin")
        pins[row["path"]] = row
    return list(pins.values())


def prepare(destination, diagnostic, parent, *, cpu=3):
    """Bind saved input/evidence and fresh code; never execute a fixture/model."""
    destination = prior.output_path(destination)
    diagnostic, parent = Path(diagnostic).absolute(), Path(parent).absolute()
    if any(
        destination.is_relative_to(p) or p.is_relative_to(destination)
        for p in (ROOT, diagnostic, parent, prior.NATIVE)
    ):
        raise ValueError("Preparation overlaps source or retained evidence")
    if type(cpu) is not int or os.sched_getaffinity(0) != {cpu}:
        raise ValueError("Declare the actual single preparation CPU")
    stop, case, parent_plan, captures, declared = saved_prefix(diagnostic, parent)
    _, image_path = native.inputs(declared, parent_plan["configuration"], stop_after=stop)
    _, sites = native.source_nodes(prior.NATIVE, stop_after=stop)
    external = [
        prior.pin(diagnostic / name)
        for name in ("result.json", "diagnostic.json", "root-review.json")
    ]
    external += [prior.pin(diagnostic / row["path"]) for row in captures]
    external += [prior.pin(image_path), prior.pin(parent / "plan.json")]
    external += [
        dict(path=str(prior.NATIVE / name), sha256=h) for name, h in native.pins_for(stop).items()
    ]
    # Retain the parent's exact overlays AND installed beartype pins. Those
    # descriptor dependencies need not live under an explicit runtime overlay.
    external += parent_plan["external_inputs"]
    external = unique_pins(external)
    prior.verify_pins(external)
    destination.mkdir(parents=True, exist_ok=False)
    try:
        closure = runpy.run_path(str(ROOT / prior.CLOSURE))["closure"]
        files = closure(
            ROOT,
            [
                OWN,
                NATIVE,
                COMPARE,
                TEST,
                ORCHESTRATION_TEST,
                "tests/unit/test_native_single_cell_prefix_compare.py",
            ],
        )
        files[prior.CLOSURE] = source_snapshot.digest(ROOT / prior.CLOSURE)
        for directory in {Path(name).parent for name in files}:
            for path in (ROOT / directory).glob("*.json"):
                files[str(path.relative_to(ROOT))] = source_snapshot.digest(path)
        snapshot = source_snapshot.freeze(
            ROOT, destination / "source", {name: name for name in files}
        )
        plan = dict(
            kind=KINDS[0],
            purpose="independent_original_source_prefix_comparison",
            case=case,
            parent_diagnostic=str(diagnostic),
            parent_prepared=str(parent),
            input_capture=prior.pin(diagnostic / captures[0]["path"]),
            stop_after=stop,
            saved_captures=[
                dict(label=row["label"], **prior.pin(diagnostic / row["path"])) for row in captures
            ],
            configuration=parent_plan["configuration"],
            snapshot_sha256=source_snapshot.digest(destination / "source/SNAPSHOT.json"),
            git_revision=snapshot["git_revision"],
            external_inputs=external,
            native_source_root=str(prior.NATIVE),
            original_source_sites=sites,
            runtime_paths=parent_plan["runtime_paths"],
            interpreter=str(Path(sys.executable).absolute()),
            cpu=cpu,
            limits=prior.LIMITS,
            stages=["before", *native.methods_for(stop)],
            native_metadata_imports=list(native.metadata_imports_for(stop)),
            comparison="exact_typed_values_source_layout_and_MT_state",
            native_executions=1,
            cells_replays=0,
            automatic_retry=False,
            independent_physical_oracle=False,
            physical_geometry_admitted=False,
            full_package_or_phase_admitted=False,
            ordinary_checkpoint_admitted=False,
            shared_descriptor_helpers=(stop != "near_neigh"),
        )
        if stop != "near_neigh":
            plan.update(
                owned_geometry=prior.pin(diagnostic / captures[4]["path"]),
                owned_ecm=prior.pin(diagnostic / captures[6]["path"]),
            )
        else:
            plan["owned_trial"] = prior.pin(diagnostic / captures[4]["path"])
        if stop == "make_maskM":
            plan.update(
                owned_environment=prior.pin(diagnostic / captures[8]["path"]),
                environment_stages=list(native.ENVIRONMENT_STAGES),
                inline_assignment_sites=inline_assignment_sites(sites, stop),
            )
        source_snapshot.assert_checkout_unchanged(destination / "source")
        prior.verify_pins(external)
        prior.write(destination / "plan.json", plan)
        (destination / "plan.json").chmod(0o444)
        return plan
    except BaseException:
        prior.write(
            destination / "preparation-failure.json",
            dict(traceback=traceback.format_exc(), scientific_acceptance=False),
        )
        raise


def verify(prepared, plan_sha256, release):
    prepared = prior.output_path(prepared)
    if source_snapshot.digest(prepared / "plan.json") != plan_sha256:
        raise ValueError("Changed comparison plan")
    plan = prior.read(prepared / "plan.json")
    stop = endpoint(plan.get("stop_after", "near_neigh"))
    if (
        (prepared / "preparation-failure.json").exists()
        or plan.get("kind") != KINDS[0]
        or plan.get("limits") != prior.LIMITS
        or plan.get("stages") != ["before", *native.methods_for(stop)]
        or plan.get("native_executions") != 1
        or type(plan.get("native_executions")) is not int
        or plan.get("cells_replays") != 0
        or type(plan.get("cells_replays")) is not int
        or type(plan.get("cpu")) is not int
        or plan.get("automatic_retry") is not False
        or plan.get("independent_physical_oracle") is not False
        or plan.get("physical_geometry_admitted") is not False
        or plan.get("full_package_or_phase_admitted") is not False
        or plan.get("ordinary_checkpoint_admitted") is not False
        or plan.get("case") not in prior.CASES
    ):
        raise ValueError("Incomplete or widened comparison plan")
    source_snapshot.verify(prepared / "source", manifest_sha256=plan["snapshot_sha256"])
    prior.verify_pins(plan["external_inputs"])
    if "stop_after" in plan:
        captures = plan.get("saved_captures", [])
        if (
            plan.get("native_metadata_imports") != list(native.metadata_imports_for(stop))
            or plan.get("shared_descriptor_helpers") is not (stop != "near_neigh")
            or [row.get("label") for row in captures] != list(prior.stage_names(stop))
        ):
            raise ValueError("Incomplete endpoint capture/import declaration")
        required = [
            dict(path=str(Path(plan["native_source_root"]) / name), sha256=h)
            for name, h in native.pins_for(stop).items()
        ]
        required += retained_inputs(plan)
        required += [dict(path=row["path"], sha256=row["sha256"]) for row in captures]
        if any(row not in plan["external_inputs"] for row in required):
            raise ValueError("Missing endpoint input, native or metadata-helper source pin")
        if (
            retained_inputs(plan)[0] != {k: captures[0][k] for k in ("path", "sha256")}
            or retained_inputs(plan)[1] != {k: captures[4][k] for k in ("path", "sha256")}
            or (
                stop != "near_neigh"
                and retained_inputs(plan)[2] != {k: captures[6][k] for k in ("path", "sha256")}
            )
            or (
                stop == "make_maskM"
                and retained_inputs(plan)[3] != {k: captures[8][k] for k in ("path", "sha256")}
            )
        ):
            raise ValueError("Retained comparison inputs do not match declared captures")
        if stop == "make_maskM" and (
            plan.get("environment_stages") != list(native.ENVIRONMENT_STAGES)
            or not _same(
                plan.get("inline_assignment_sites"),
                inline_assignment_sites(plan.get("original_source_sites", {}), stop),
            )
        ):
            raise ValueError("Incomplete environment stages or inline source binding")
        capture_lineage([prior.read(row["path"]) for row in captures], plan["configuration"], stop)
        metadata_modules(plan)
    grant = prior.read(release)
    if (
        grant.get("kind") != KINDS[1]
        or grant.get("plan_sha256") != plan_sha256
        or grant.get("snapshot_sha256") != plan["snapshot_sha256"]
        or grant.get("case") != plan["case"]
        or grant.get("stop_after", "near_neigh") != stop
        or grant.get("allow_one_native_reference") is not True
        or grant.get("physical_geometry_admitted") is not False
        or type(grant.get("source_review")) is not dict
        or set(grant["source_review"]) != {"path", "sha256"}
    ):
        raise ValueError("Exact source-reviewed single-reference release required")
    prior.verify_pins([grant["source_review"]])
    if os.sched_getaffinity(0) != {plan["cpu"]}:
        raise ValueError("Wrong declared reference CPU")
    return plan


def worker(prepared, plan_sha256, release, output):
    plan = verify(prepared, plan_sha256, release)
    if (
        ROOT != Path(prepared) / "source"
        or str(Path(sys.executable).absolute()) != plan["interpreter"]
    ):
        raise ValueError("Reference worker must use frozen source and interpreter")
    resource.setrlimit(resource.RLIMIT_AS, (2**30, 2**30))
    output = protected_output(output, prepared, plan)
    attempted = []
    stop = endpoint(plan.get("stop_after", "near_neigh"))
    sys.addaudithook(import_guard(plan, attempted))
    outcome = dict(
        status="failed",
        accepted_source_comparisons=0,
        physical_geometry_admitted=False,
        ordinary_checkpoint_admitted=False,
        native_executions=0,
        stop_after=stop,
    )
    try:
        verify_metadata_modules(plan)
        declared = prior.read(plan["input_capture"]["path"])["native_comparison_inputs"]
        outcome["native_executions"] = 1
        reference = native.evaluate(
            declared,
            plan["configuration"],
            Path(plan["native_source_root"]),
            record_exception=prior.exception_record,
            stop_after=stop,
        )
        # Existing independent archive transport only; no production decoder.
        serialized = prior.archive.snapshot(reference)
        prior.write(output / "native.json", serialized)
        from validation.betse.native_single_cell_prefix_compare import compare, compare_ecm

        if stop == "make_maskM":
            from validation.betse.native_single_cell_prefix_compare import compare_environment

            comparison = compare_environment(
                prior.read(plan["owned_geometry"]["path"]),
                prior.read(plan["owned_ecm"]["path"]),
                prior.read(plan["owned_environment"]["path"]),
                serialized,
            )
        elif stop == "makeECM":
            comparison = compare_ecm(
                prior.read(plan["owned_geometry"]["path"]),
                prior.read(plan["owned_ecm"]["path"]),
                serialized,
            )
        else:
            comparison = compare(prior.read(plan["owned_trial"]["path"]), serialized)
        prior.write(output / "comparison.json", comparison)
        verify(prepared, plan_sha256, release)
        outcome["native_metadata_producers"] = verify_metadata_modules(plan)
        if attempted:
            raise RuntimeError("Reference imported the tested model")
        outcome.update(
            status="exact_source_match" if comparison["exact_match"] else "source_mismatch",
            accepted_source_comparisons=int(comparison["exact_match"]),
            native=prior.pin(output / "native.json"),
            comparison=prior.pin(output / "comparison.json"),
        )
    except Exception as error:
        outcome["error"] = prior.exception_record(error)
    finally:
        outcome["attempted_model_imports"] = attempted
        try:
            outcome["native_metadata_producers"] = verify_metadata_modules(plan)
            prior.write(output / "runtime-producers.json", prior.runtime_inventory(ROOT))
            outcome["runtime_producers"] = prior.pin(output / "runtime-producers.json")
        except Exception as capture_error:
            outcome["runtime_capture_error"] = prior.exception_record(capture_error)
            outcome["status"] = "failed"
            outcome["accepted_source_comparisons"] = 0
        prior.write(output / "worker-result.json", outcome)
    return 0 if outcome["status"] == "exact_source_match" else 1


def launch(prepared, plan_sha256, release, output):
    plan = verify(prepared, plan_sha256, release)
    output = protected_output(output, prepared, plan)
    output.mkdir(parents=True, exist_ok=False)
    process, error = None, None
    try:
        (output / "process").mkdir()
        prior.write(
            output / "inputs.json",
            dict(
                plan_sha256=plan_sha256,
                release=prior.pin(release),
                case=plan["case"],
                stop_after=plan.get("stop_after", "near_neigh"),
            ),
        )
        if prior.guard.memory_available() < 12 * 2**30:
            raise RuntimeError("Reference launch requires 12 GiB available")
        process = prior.guard.run_bounded(
            [
                plan["interpreter"],
                "-B",
                "-m",
                "validation.betse.native_single_cell_prefix_comparison",
                "worker",
                "--prepared",
                str(prepared),
                "--plan-sha256",
                plan_sha256,
                "--release",
                str(release),
                "--output",
                str(output),
            ],
            directory=output / "process",
            cwd=Path(prepared) / "source",
            env=prior.environment(Path(prepared) / "source", plan),
            **plan["limits"],
        )
        child = prior.read(output / "worker-result.json")
        if process["returncode"] or child["status"] != "exact_source_match":
            raise RuntimeError("Reference/comparison did not produce an exact match")
    except Exception as caught:
        error = prior.exception_record(caught)
    result = dict(
        status="failed" if error else "exact_source_match_pending_review",
        process=process,
        error=error,
        worker_result=prior.pin(output / "worker-result.json")
        if (output / "worker-result.json").is_file()
        else None,
        accepted_scientific_cases=0,
        physical_geometry_admitted=False,
        ordinary_checkpoint_admitted=False,
        automatic_retry=False,
        stop_after=plan.get("stop_after", "near_neigh"),
    )
    prior.write(output / ("failure.json" if error else "result.json"), result)
    return int(error is not None)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("prepare")
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--diagnostic", type=Path, required=True)
    p.add_argument("--parent", type=Path, required=True)
    p.add_argument("--cpu", type=int, default=3)
    for command in ("run", "worker"):
        p = sub.add_parser(command)
        p.add_argument("--prepared", type=Path, required=True)
        p.add_argument("--plan-sha256", required=True)
        p.add_argument("--release", type=Path, required=True)
        p.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "prepare":
        resource.setrlimit(resource.RLIMIT_AS, (512 * 2**20, 2**30))
        prepare(args.output, args.diagnostic, args.parent, cpu=args.cpu)
        return 0
    return (worker if args.command == "worker" else launch)(
        args.prepared, args.plan_sha256, args.release, args.output
    )


if __name__ == "__main__":
    raise SystemExit(main())
