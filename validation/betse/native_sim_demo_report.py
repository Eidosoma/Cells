"""Direct saved demo@9/SIM report. Metadata consistency never issues live authority.

The older SEED/INIT report is unchanged. Its bounded file/wire readers and INIT
ancestor checks are reused explicitly; no saved kind or endpoint is relabelled.
"""

import argparse
import json
import re
from pathlib import Path
from types import SimpleNamespace

from validation import source_snapshot as snapshot
from validation.betse import native_seed_demo_evidence as evidence
from validation.betse import native_seed_demo_launch as launch
from validation.betse import native_seed_demo_report as legacy
from validation.betse import native_seed_rng_report as rng_report
from validation.betse import native_sim_demo_observation as observation
from validation.betse import native_single_cell_prefix_payload as payload

KIND = "cells.saved_complete_INIT_SIM_demo_report@1"
LAUNCH_KIND, DEMO_KIND = launch.SIM_KIND, launch.SIM_DEMO_KIND
ENDPOINT = "sim_terminal"
DEMO, LAUNCH, PARAMETER = legacy.DEMO, legacy.LAUNCH, legacy.PARAMETER
NUMPY_ORIGIN, MOLECULE_WRAPPER = legacy.NUMPY_ORIGIN, legacy.MOLECULE_WRAPPER
IMPORT_PROTOCOL = legacy.IMPORT_PROTOCOL
INITIAL_RNG, INITIAL_RNG_KIND = legacy.INITIAL_RNG, legacy.INITIAL_RNG_KIND
INITIAL_RNG_EPOCH, INITIAL_RNG_BOUNDARY = legacy.INITIAL_RNG_EPOCH, legacy.INITIAL_RNG_BOUNDARY
RNG_MODULES = legacy.RNG_MODULES
Reader, require = legacy.Reader, legacy.require
_hash_identity, _iterations = legacy._hash_identity, legacy._iterations
_parameter_roster, _parameter_archive = legacy._parameter_roster, legacy._parameter_archive
_parameter_load_prefix = legacy._parameter_load_prefix
_numpy_origin, _geometry_captures = legacy._numpy_origin, legacy._geometry_captures
LEGACY_SHA256 = "c9f3d6002e1faf680209c66123624ec6793c99781eb91179ee98974f1f627ad7"
INIT_STAGES = (
    "geometry",
    "poisson",
    "core",
    "profiles",
    "junctions",
    "init_setup",
    "init_prelude",
    "init_dynamics",
    "init_storage",
    "init_electrical",
    "init_terminal",
)
SIM_STAGES = ("sim_preparation", "sim_assembly", "sim_run")


def source_plan():
    return dict(
        kind=KIND,
        launch_kind=LAUNCH_KIND,
        demo_kind=DEMO_KIND,
        endpoint=ENDPOINT,
        prior_report_sha256=LEGACY_SHA256,
        parameter_acquisitions=launch.ACQUISITION_SEQUENCE,
        maximum_INIT_iterations=512,
        maximum_SIM_iterations=512,
        source_execution=False,
        owner_hydration=False,
        numerical_comparison=False,
        common_starting_authority_established=False,
        scientific_credit=0,
        completed_observation_required=True,
        comparison_request_requires_explicit_postprocess=True,
    )


def _initial_rng_declaration(reader, plan, demo, bundle, parameters, files):
    return rng_report.initial_rng_declaration(
        reader, plan, demo, bundle, parameters, files, demo_kind=DEMO_KIND, launch_kind=LAUNCH_KIND
    )


def _initial_rng_captures(reader, root, plan, value, captures):
    prefix = tuple(
        f"sim_imports.{role}.{event}"
        for role in launch.SIM_MODULES
        for event in ("factory", "enter")
    )
    return rng_report.initial_rng_captures(reader, root, plan, value, captures, prefix=prefix)


def _plan(reader, path, digest):
    require(
        type(digest) is str and len(digest) == 64 and all(c in "0123456789abcdef" for c in digest),
        "Explicit SHA-256 plan binding required",
    )
    require(
        snapshot.digest(Path(legacy.__file__)) == LEGACY_SHA256, "Prior report producer changed"
    )
    plan = reader.read(path, digest)
    require(plan.get("kind") == LAUNCH_KIND, "Unsupported launch schema")
    require(plan.get("held") is True and plan.get("automatic_retry") is False, "Held plan required")
    require(plan.get("flux_operator") in ("original", "disabled"), "Unknown flux mode")
    require(plan.get("endpoint") == ENDPOINT, "Unknown endpoint")
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
    import_policy = demo.get("source_plan", {}).get("optional_molecule_import_authority")
    if plan.get("endpoint", "seed") == ENDPOINT and import_policy is not None:
        require(
            type(import_policy) is dict
            and import_policy.get("protocol") == IMPORT_PROTOCOL
            and import_policy.get("modules")
            == {"molecule_wrappers": "cells.processes.betse_native_init_molecule_wrapper_authority"}
            and set(import_policy.get("source_pins", {})) == {"molecule_wrappers"}
            and set(import_policy.get("review_pins", {})) == {"molecule_wrappers"}
            and _hash_identity(import_policy["source_pins"]["molecule_wrappers"])
            and _hash_identity(import_policy["review_pins"]["molecule_wrappers"])
            and files.get(MOLECULE_WRAPPER) == import_policy["source_pins"]["molecule_wrappers"],
            "Declared original import observer source/review is not in the immutable closure",
        )
    else:
        import_policy = None
    plan = dict(plan, _molecule_import_policy=import_policy, _demo_kind=demo.get("kind"))
    require(demo.get("kind") == DEMO_KIND, "Direct demo@9 required; no legacy relabeling")
    count = _iterations(plan)
    require(demo.get("held") is True and demo.get("policy") == plan["policy"], "Held SIM domain")
    require(plan["policy"] == launch.POLICY, "Exact unchanged SIM resource policy")
    require(plan.get("limitations") == launch.source_plan(endpoint=ENDPOINT), "SIM launch policy")
    launch._environment_map(plan["release_environment"])
    launch._sim_contract(plan, demo, parameters, manifest)
    plan["_observation_policy"] = demo["source_plan"]["optional_sim_terminal"][
        "completed_observation"
    ]
    require(set(producers) == set(launch._producers(demo)), "Complete exact SIM producer roster")
    terminal = demo.get("source_plan", {}).get("optional_init_terminal", {})
    require(
        type(terminal.get("maximum_iterations")) is int
        and terminal["maximum_iterations"] == 512
        and terminal.get("init_iterations") is None
        and terminal.get("selected_stop") is False
        and all(
            terminal.get(name) is True
            for name in (
                "full_original_calendar",
                "normal_loop_context_and_caller_return",
                "before_native_pickle",
            )
        ),
        "Complete original INIT prerequisite required",
    )
    require(
        type(demo.get("init_iterations")) is type(count) and demo.get("init_iterations") == count,
        "Prepared iteration count changed",
    )
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
    from validation.betse import native_seed_demo_input_profiles as profiles

    require(
        bundle.get("configuration_profile", "original")
        == parameters["program"].get("input_profile", "original"),
        "Saved configuration profile and parameter program differ",
    )
    selected = bundle["modes"][plan["flux_operator"]]
    require(
        selected["program"] == parameters["program"]["manifest"]
        and selected["config"] == parameters["program"]["root"],
        "Actual input mode association changed",
    )
    declared_program = reader.bound(selected["program"])
    require(
        declared_program.get("input_profile", "original")
        == bundle.get("configuration_profile", "original"),
        "Saved raw input program profile changed",
    )
    for row in plan["external_files"]:
        reader.bind(row)
    originals = {}
    for name, row in sorted(profiles.selected_inventory(bundle)["files"].items()):
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
    for name, row in plan["sim_original_sources"]["files"].items():
        reader.bind(
            dict(path=str(Path(plan["sim_original_sources"]["root"]) / name), sha256=row["sha256"])
        )
    plan["_initial_rng_inputs"] = _initial_rng_declaration(
        reader, plan, demo, bundle, parameters, files
    )
    return plan, files, originals


def _runtime(reader, root, plan, files):
    result = rng_report._runtime(reader, root, plan, files)
    for name in ("runtime-before.json", "runtime-after.json"):
        observation.runtime_sources(reader.read(root / name), plan["sim_original_sources"])
    return result


def _current_parameter_prefix(reader, root, plan, outcome):
    """Retain a returned load prefix independently of later public validation failure."""
    directory = root / "current_parameters"
    present = [name for name in ("acquisition.json", "failure.json") if (directory / name).exists()]
    summary = dict(
        status="not_recorded",
        journal_files=present,
        operations=[],
        actual_world_ready_returned=False,
        completed_history_returned=False,
        final_live_parameters=None,
        acquisition_returned=False,
        usable_owner=False,
        init_or_sim_credit=False,
        scientific_credit=0,
        failure_present="failure.json" in present,
        evidence_complete=False,
    )
    if not present:
        if directory.exists():
            reader.issues.append(
                dict(
                    section="current_parameter_prefix",
                    type="MissingEvidence",
                    message="Parameter directory has no saved acquisition/failure journal",
                )
            )
            summary["status"] = "incomplete_evidence"
        return summary
    summary["status"] = "incomplete_evidence"
    records = {
        name: reader.check(
            "current_parameter_prefix." + name, lambda name=name: reader.read(directory / name)
        )
        for name in present
    }
    journal = (
        records.get("failure.json")
        if "failure.json" in present
        else records.get("acquisition.json")
    )
    if journal is None:
        return summary
    summary["primary"] = journal.get("primary")

    def declaration():
        roster = _parameter_roster(reader, plan)
        rows = journal["operations"]
        require(
            type(rows) is list
            and len(rows) <= len(roster)
            and all(type(row) is dict for row in rows)
            and [row.get("name") for row in rows] == roster[: len(rows)],
            "Original ordered unique parameter operation prefix required",
        )
        if "failure.json" in records:
            require(
                journal.get("source_or_evidence_incomplete") is True
                and type(journal.get("primary")) is dict,
                "Original parameter failure record",
            )
        if "acquisition.json" in records and records["acquisition.json"] is not None:
            acquired = records["acquisition.json"]
            require(
                acquired["packet"] == plan["parameter_inputs"]
                and acquired.get("distinct_fresh_native_load") is True
                and acquired.get("INIT_SIM_or_persisted_owner_admission") is False
                and acquired.get("acquisition_sequence") == list(launch.ACQUISITION_SEQUENCE)
                and len(acquired["operations"]) == len(roster)
                and all(
                    type(acquired.get(key)) is int and acquired[key] > 0
                    for key in (
                        "initial_owner_identity",
                        "initial_p_identity",
                        "actual_world_ready_identity",
                        "actual_p_identity",
                    )
                ),
                "Acquisition packet/source scope changed",
            )
            initial = reader.read(root / "parameters/acquisition.json")
            require(
                initial.get("acquisition_sequence") == list(launch.ACQUISITION_SEQUENCE)
                and acquired.get("initial_owner_identity") == initial["actual_world_ready_identity"]
                and acquired.get("initial_p_identity") == initial["actual_p_identity"]
                and acquired["actual_world_ready_identity"]
                != initial["actual_world_ready_identity"]
                and acquired["actual_p_identity"] != initial["actual_p_identity"],
                "Distinct current acquisition must retain exact initial pair",
            )
            reader.bound(acquired["packet"])
            require(
                acquired["actual_world_ready_identity"]
                == acquired["operations"][-3].get("returned_identity")
                and acquired["actual_p_identity"]
                == acquired["operations"][-1].get("returned_identity"),
                "Acquisition returned object identities changed",
            )
            if "failure.json" in records:
                require(acquired["operations"] == rows, "Conflicting parameter journals")
        return roster, rows

    declared = reader.check("current_parameter_prefix.journal", declaration)
    if declared is None:
        return summary
    roster, rows = declared
    budget = dict(bytes=0, authenticated_bytes=0, archives=0)
    valid_prefix = True
    for index, row in enumerate(rows):
        item = dict(
            name=row["name"],
            status="incomplete_evidence",
            returned_observed=False,
            evidence_complete=False,
            archives=[],
            primary=row.get("primary"),
            capture_errors=row.get("errors"),
            journal_returned=row.get("returned"),
            returned_identity=row.get("returned_identity"),
        )
        summary["operations"].append(item)
        operation = directory / "evidence" / f"{index:02d}-{row['name']}"

        def operation_metadata(row=row, operation=operation, index=index):
            require(
                row.get("attempted") is True
                and type(row.get("returned")) is bool
                and type(row.get("evidence_complete")) is bool
                and type(row.get("errors")) is list,
                "Exact parameter operation status fields",
            )
            require(
                reader.read(operation / "attempt.json")
                == dict(name=row["name"], attempt=index + 1),
                "Parameter attempt ordinal changed",
            )
            require(
                reader.read(operation / "outcome.json") == row, "Parameter outcome/journal mismatch"
            )
            if row["returned"]:
                require(
                    type(row.get("returned_identity")) is int
                    and row["returned_identity"] > 0
                    and row.get("primary") is None,
                    "Actual parameter return identity/status",
                )
            else:
                require(
                    type(row.get("primary")) is dict
                    and reader.read(operation / "primary.json") == row["primary"],
                    "Original parameter API failure evidence",
                )
            return True

        observed = reader.check("current_parameter_prefix." + row["name"], operation_metadata)
        if observed:
            item["returned_observed"] = row["returned"]
            if row.get("primary") is not None:
                item["status"] = "failed"
            archive_ok = True
            refs = [("payload", row.get("payload"))]
            for key, prefix in (("graphs", "graph-"), ("captures", "capture-")):
                values = row.get(key)
                if type(values) is not dict or len(values) > 64:
                    archive_ok = False
                    reader.issues.append(
                        dict(
                            section="current_parameter_prefix." + row["name"],
                            type="InvalidEvidence",
                            message="Bounded archive map required",
                        )
                    )
                    continue
                for name, reference in values.items():
                    if type(name) is not str or re.fullmatch(r"[A-Za-z0-9_-]{1,80}", name) is None:
                        archive_ok = False
                        reader.issues.append(
                            dict(
                                section="current_parameter_prefix." + row["name"],
                                type="InvalidEvidence",
                                message="Canonical archive role required",
                            )
                        )
                        continue
                    refs.append((prefix + name, reference))
            for role, reference in refs:
                archived = reader.check(
                    "current_parameter_prefix." + row["name"] + "." + role,
                    lambda role=role, reference=reference, operation=operation: _parameter_archive(
                        reader, reference, operation / role, budget
                    ),
                )
                archive_ok &= archived is not None
                item["archives"].append(dict(role=role, verified=archived))
            item["evidence_complete"] = (
                row["evidence_complete"] and not row["errors"] and archive_ok
            )
            if row["returned"] and item["evidence_complete"]:
                item["status"] = "returned"
        if not valid_prefix:
            reader.issues.append(
                dict(
                    section="current_parameter_prefix." + row["name"],
                    type="InvalidOrder",
                    message="Operation follows a failed/incomplete predecessor",
                )
            )
            item["evidence_complete"] = False
            item["status"] = "incomplete_evidence"
        valid_prefix &= item["status"] == "returned"
    by_name = {row["name"]: row for row in summary["operations"]}
    summary.update(
        actual_world_ready_returned=by_name.get("actual-world-ready", {}).get("status")
        == "returned",
        completed_history_returned=by_name.get("final-history", {}).get("status") == "returned",
        final_live_parameters=by_name.get("final-live-parameters"),
        evidence_complete=all(row["evidence_complete"] for row in summary["operations"]),
        archive_count=budget["archives"],
        authenticated_payload_bytes=budget["authenticated_bytes"],
        reader_charged_file_bytes=budget["bytes"],
    )
    summary["acquisition_returned"] = (
        len(rows) == len(roster)
        and valid_prefix
        and not summary["failure_present"]
        and type(outcome) is dict
        and type(outcome.get("operations")) is list
        and any(
            row == dict(name="current_parameters", status="returned")
            for row in outcome["operations"]
        )
    )
    summary["status"] = (
        "failed_after_recorded_prefix"
        if summary["failure_present"]
        else "returned_acquisition"
        if summary["acquisition_returned"]
        else "recorded_prefix"
    )
    if not summary["evidence_complete"]:
        summary["status"] = "incomplete_evidence"
    return summary


def inspect_attempt(plan_path, *, plan_sha256, output=None, observation_request=None):
    """One explicit read of saved terminal paths; never query or wait on a job."""
    reader = Reader()
    plan, files, originals = _plan(reader, Path(plan_path), plan_sha256)
    bundle = reader.bound(plan["input_bundle"])
    report = dict(
        kind=KIND,
        status="prepared_only",
        plan_sha256=plan_sha256,
        flux_operator=plan["flux_operator"],
        endpoint=plan.get("endpoint", "seed"),
        init_iterations_requested=plan.get("init_iterations"),
        source_files=files,
        original_input_files={
            name: row["sha256"] for name, row in bundle["source_inventory"]["files"].items()
        },
        selected_input_files=originals,
        configuration_profile=bundle.get("configuration_profile", "original"),
        configuration_changes=bundle.get("configuration_changes", []),
        policy=plan["policy"],
        original_flux_defect_repaired=False,
        numerical_comparison=False,
        scientific_credit=0,
        time_steps_qualified=0,
        init_iterations_completed=0,
        sim_iterations_completed=0,
        init_native_molecules=None,
        init_molecule_network_completed=False,
        restart_qualified=False,
        source_execution_complete=False,
        source_evidence_complete=False,
        saved_comparison_request=None,
        accepted_observer_sha256=plan["_observation_policy"]["observer_sha256"],
        evidence_scope=(
            "Endpoint and geometry captures plus declared source/input/runtime/resource/"
            "filesystem records and available parameter operation archives; "
            "no live failed-owner serialization claim"
        ),
    )
    if plan.get("_initial_rng_inputs") is not None:
        report.update(
            initial_rng_inputs=plan["_initial_rng_inputs"],
            common_starting_authority_established=False,
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
            if NUMPY_ORIGIN in plan["producers"]:
                report["numpy_copy_origin"] = reader.check(
                    "numpy_copy_origin", lambda: _numpy_origin(reader, root)
                )
            raw_outcome = reader.check(
                "outcome_read", lambda: reader.read(root / "demo/outcome.json")
            )
            prefix = _parameter_load_prefix(reader, root / "demo", plan, raw_outcome)
            report["parameter_load_prefix"] = prefix
            current = _current_parameter_prefix(reader, root / "demo", plan, raw_outcome)
            report["current_parameter_prefix"] = current
            if current["failure_present"]:
                report["status"] = "failed"
                failures.append(
                    dict(path="worker/demo/current_parameters/failure.json", failure=current)
                )
            if prefix["failure_present"]:
                report["status"] = "failed"
                failures.append(
                    dict(
                        path="worker/demo/parameters/failure.json",
                        failure=dict(
                            primary=prefix.get("primary"),
                            evidence_complete=prefix["evidence_complete"],
                        ),
                    )
                )
            result = (
                reader.check("outcome", lambda: _outcome(reader, root / "demo", plan, raw_outcome))
                if raw_outcome is not None
                else None
            )
            report["demonstration"] = result
            if result is not None:
                report.update(
                    init_native_molecules=result["molecule_network"]["selected"],
                    init_molecule_network_completed=result["molecule_network"]["completed"],
                )
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
                        and worker.get("endpoint", "seed") == report["endpoint"]
                        and type(worker.get("init_iterations")) is type(plan.get("init_iterations"))
                        and worker.get("init_iterations") == plan.get("init_iterations"),
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
                    if NUMPY_ORIGIN in plan["producers"]:
                        require(
                            worker.get("numpy_copy_origin_available") is True
                            and worker.get("numpy_copy_origin_completed") is True
                            and type(report.get("numpy_copy_origin")) is dict
                            and report["numpy_copy_origin"].get("completed") is True,
                            "Incomplete original NumPy construction proof",
                        )
                    require(
                        result is not None and result["outcome"]["status"] == "completed",
                        "Missing completed demonstration",
                    )
                    require(
                        (report.get("geometry") or {}).get("status") == "source_completed",
                        "Geometry did not complete",
                    )
                    require(
                        all(
                            name in (report.get("runtime") or {}).get("snapshot_producers", {})
                            for name in (
                                launch.SIM_FILE,
                                *launch.SIM_FILES,
                                observation.FILE,
                                observation.OBSERVER,
                                observation.WRITER,
                            )
                        ),
                        "Actual loaded SIM orchestration/stage producers required",
                    )
                    require(
                        worker.get("sim_observation") == result["outcome"].get("sim_observation"),
                        "Worker and demo observation records differ",
                    )
                    require(
                        prefix["acquisition_returned"]
                        and prefix["evidence_complete"]
                        and current["acquisition_returned"]
                        and current["evidence_complete"],
                        "Both complete parameter acquisition archives required",
                    )

                reader.check("completed_chain", completed)
                if not reader.issues and not failures:
                    report.update(
                        status="completed_unqualified",
                        source_execution_complete=True,
                        source_evidence_complete=True,
                        init_iterations_completed=result["outcome"]["init_time_steps_completed"],
                        sim_iterations_completed=result["outcome"]["sim_time_steps_completed"],
                    )
    if observation_request is not None:
        require(
            output is not None and report["source_evidence_complete"],
            "Saved comparison request requires completed guarded evidence",
        )
        report["saved_comparison_request"] = reader.check(
            "observation_finalization",
            lambda: _finalized(
                reader,
                plan,
                Path(plan_path),
                plan_sha256,
                Path(output),
                report,
                observation_request,
            ),
        )
    report["verification_issues"] = reader.issues
    report["observed_file_pins"] = [dict(path=k, sha256=v) for k, v in sorted(reader.pins.items())]
    return report


def _captures(reader, directory, rows):
    result = legacy._captures(reader, directory, rows)
    labels = [row["label"] for row in result]
    require(len(labels) == len(set(labels)), "Duplicate saved capture label")
    for row in result:
        if row["status"] != "saved" or not (
            row["label"].startswith("sim_") or row["label"] == "sim_imports"
        ):
            continue
        value = evidence.read(directory / row["path"], expected_sha256=row["sha256"], expand=False)
        label = row["label"]
        if label.endswith(".record") or label == "sim_run.linkage":
            require(type(value) is dict, "Actual SIM record object required")
            row["references"] = {
                key: item
                for key, item in value.items()
                if key
                not in (
                    "calls",
                    "raw",
                    "c_calls",
                    "exceptions",
                    "rng_calls",
                    "work",
                    "metadata_work",
                )
            }
            if label == "sim_run.record":
                require(type(value.get("calls")) is list, "Recorded original SIM work required")
                row["work_count"] = len(value["calls"])
        elif label == "sim_imports":
            row["references"] = value
        elif label == "sim_run.calendar":
            row.update(
                legacy._terminal_calendar(
                    value, evidence.files(directory / row["path"], expected_sha256=row["sha256"])
                )
            )
        elif label.endswith(".rng") or label in ("sim_run.stream_before", "sim_run.stream_after"):
            require(
                type(value) is list
                and len(value) == 2
                and all(
                    type(item) is dict and _hash_identity(item.get("identity")) for item in value
                ),
                "Both actual saved SIM RNG cache objects required",
            )
            row["stream_identities"] = [item["identity"] for item in value]
        elif label == "sim_run.configured_dt":
            require(
                type(value) is dict
                and set(value) == {"float64_bits"}
                and type(value["float64_bits"]) is str
                and len(value["float64_bits"]) == 16,
                "Actual original scalar SIM dt bits required",
            )
            raw = bytes.fromhex(value["float64_bits"])
            require(raw.hex() == value["float64_bits"], "Canonical scalar dt bits")
            row["dt_bits"] = raw[::-1].hex()
    return result


def _sim_captures(captures, outcome, mode):
    rows = {row["label"]: row for row in captures if row["status"] == "saved"}
    count = outcome["sim_time_steps_completed"]
    require(type(count) is int and 1 <= count <= 512, "Whole bounded SIM count required")
    required = ["sim_imports", *(name + ".record" for name in SIM_STAGES)]
    required += [
        "sim_run." + key
        for key in (
            "before",
            "ready",
            "after",
            "calendar",
            "sampled",
            "configured_dt",
            "stream_before",
            "stream_after",
            "linkage",
        )
    ]
    iterations = [
        f"sim_run.iteration.{i:04d}.{field}" for i in range(count) for field in ("after", "rng")
    ]
    legacy._required_captures(captures, required + iterations)
    require(
        [row["label"] for row in captures if row["label"].startswith("sim_run.iteration.")]
        == iterations,
        "Complete ordered SIM state/RNG iteration roster required",
    )
    imports = rows["sim_imports"]["references"]
    require(
        type(imports) is list
        and len(imports) == 3
        and [r.get("role") for r in imports] == list(launch.SIM_MODULES)
        and all(
            type(r.get(k)) is int and r[k] > 0
            for r in imports
            for k in ("proof_identity", "record_identity")
        )
        and all(
            r.get(k) is True
            for r in imports
            for k in ("entered", "exited", "published", "actual_import_not_replayed")
        ),
        "Actual closed three-provider SIM import observations required",
    )
    preparation = rows["sim_preparation.record"]["references"]
    assembly = rows["sim_assembly.record"]["references"]
    record = rows["sim_run.record"]["references"]
    linkage = rows["sim_run.linkage"]["references"]
    require(outcome.get("sim_linkage") == linkage, "Outcome SIM linkage differs from capture")
    for label in (
        "init_terminal.record",
        "sim_preparation.record",
        "sim_assembly.record",
        "sim_run.record",
    ):
        require(_hash_identity(rows[label].get("identity")), "Sealed actual stage record identity")
    init = rows["init_terminal.record"]["identity"]
    current = preparation.get("parameters")
    require(
        _hash_identity(current)
        and preparation.get("source_completed") is True
        and preparation.get("phase_or_SIM_execution_admitted") is False
        and preparation.get("init")
        == assembly.get("INIT")
        == record.get("INIT")
        == linkage.get("completed_INIT_identity")
        == init
        and assembly.get("preparation") == rows["sim_preparation.record"]["identity"]
        and assembly.get("current_parameters")
        == record.get("parameters")
        == linkage.get("current_parameters_identity")
        == current
        and assembly.get("constructor_completed") is True
        and type(assembly.get("SIM_iterations")) is int
        and assembly["SIM_iterations"] == 0
        and record.get("assembly")
        == linkage.get("constructor_identity")
        == rows["sim_assembly.record"]["identity"]
        and linkage.get("trial_identity") == rows["sim_run.record"]["identity"]
        and _hash_identity(record.get("request"))
        and linkage.get("request_identity") == record["request"],
        "Exact completed INIT/current parameters/preparation/assembly/SIM linkage required",
    )
    expected_mode = (
        "original_value_and_flux" if mode == "original" else "original_value_only_flux_omitted"
    )
    require(
        record.get("operator_mode") == linkage.get("operator_mode") == expected_mode,
        "Original flux convention changed",
    )
    require(
        type(linkage.get("configured_iterations")) is int
        and linkage["configured_iterations"] == count
        and type(linkage.get("maximum_iterations")) is int
        and linkage["maximum_iterations"] == 512
        and linkage.get("selected_stop") is False
        and linkage.get("native_pickle_checkpoint_or_physical_admission") is False
        and all(
            linkage.get(k) is True
            for k in (
                "complete_configured_calendar",
                "report_returned",
                "loop_returned",
                "context_returned",
                "before_native_pickle",
                "same_retained_simulator_and_cells",
                "distinct_current_parameters",
                "source_library_metadata_work_is_non_additive",
            )
        )
        and all(
            record.get(k) is True for k in ("report", "loop", "context", "before_native_pickle")
        ),
        "Entire SIM calendar and normal report/loop/context return required",
    )
    for field in ("before", "ready", "after", "calendar", "sampled"):
        require(
            _hash_identity(record.get(field))
            and rows["sim_run." + field].get("identity") == record[field],
            "SIM original cache association changed: " + field,
        )
    require(
        record.get("dt")
        == linkage.get("configured_dt_bits")
        == rows["sim_run.configured_dt"]["dt_bits"],
        "Original SIM dt bits changed",
    )
    streams = record.get("streams")
    require(
        type(streams) is list
        and len(streams) == 2
        and streams
        == [
            rows["sim_run.stream_before"]["stream_identities"],
            rows["sim_run.stream_after"]["stream_identities"],
        ],
        "Actual two-sided SIM RNG handoff changed",
    )
    require(assembly.get("rng_after") == streams[0], "Assembly to SIM RNG handoff changed")
    native = record.get("iterations")
    calendar = rows["sim_run.calendar"]
    require(
        type(native) is list and len(native) == count == calendar["calendar_length"],
        "Complete original SIM calendar required",
    )
    end = 0
    for i, row in enumerate(native):
        require(
            type(row) is list
            and len(row) == 9
            and type(row[0]) is int
            and row[0] == i
            and type(row[2]) is bool
            and row[1] == calendar["calendar_time_bits"][i]
            and _hash_identity(row[3])
            and row[3] == rows[f"sim_run.iteration.{i:04d}.after"].get("identity")
            and row[4] == rows[f"sim_run.iteration.{i:04d}.rng"]["stream_identities"]
            and type(row[5]) is int
            and end <= row[5] <= rows["sim_run.record"]["work_count"]
            and _hash_identity(row[6])
            and type(row[7]) is list
            and type(row[8]) is list,
            "Original SIM ordinal/time/sample/cache/RNG/work boundary changed",
        )
        end = row[5]
    return dict(
        recorded_iterations=count,
        source_time_bits=calendar["calendar_time_bits"],
        complete_configured_calendar=True,
        before_native_pickle=True,
        numerical_or_physical_qualification=False,
    )


def _outcome(reader, root, plan, value):
    require(
        value.get("kind") == DEMO_KIND
        and value.get("endpoint") == ENDPOINT
        and value.get("flux_operator") == plan["flux_operator"]
        and value.get("init_iterations") is None,
        "Direct exact SIM outcome schema required",
    )
    require(value.get("status") in ("completed", "failed"), "Known SIM outcome status")
    require(
        value.get("original_flux_defect_repaired") is False
        and type(value.get("scientific_or_physical_credit")) is int
        and value["scientific_or_physical_credit"] == 0
        and value.get("complete_seed_runner_or_INIT_SIM_restart_claim") is False
        and value.get("stage_work_is_non_additive") is True,
        "Saved SIM scope exceeds execution evidence",
    )
    captures = _captures(reader, root, value["captures"])
    rng = _initial_rng_captures(reader, root, plan, value, captures)
    # These helpers check the completed INIT ancestor, preserving the actual @9 outcome.
    molecules = legacy._molecule_captures(value, captures, "init_terminal")
    imports = legacy._molecule_import_captures(
        value, captures, "init_terminal", plan["_molecule_import_policy"]
    )
    history = sim = None
    if value["status"] == "completed":
        require(
            value.get("methods_completed") is True
            and value.get("primary") is None
            and value.get("secondary") == []
            and value.get("sim_secondary") == []
            and all(
                value.get(k) is True
                for k in (
                    "sim_completed",
                    "sim_imports_complete",
                    "sim_cleanup_complete",
                    "init_setup_completed",
                    "init_prelude_completed",
                    "init_dynamics_completed",
                    "init_storage_completed",
                    "init_electrical_completed",
                    "init_terminal_completed",
                )
            )
            and value.get("init_first_step_completed") is False
            and value.get("init_short_history_completed") is False
            and type(value.get("init_time_steps_completed")) is int
            and 1 <= value["init_time_steps_completed"] <= 512,
            "Completed SIM retains failure or incomplete INIT prerequisite",
        )
        require(
            value["completed_stage_trials"] == [*INIT_STAGES, *SIM_STAGES],
            "Complete ordered INIT/SIM stages required",
        )
        required = [
            f"sim_imports.{role}.{event}"
            for role in launch.SIM_MODULES
            for event in ("factory", "enter")
        ]
        required += ["callback", "constructor_preflight", "parameters", "initial_rng", "geometry"]
        for name in INIT_STAGES[1:]:
            required += [name + "_request", name]
        required += ["current_parameters"]
        for name in SIM_STAGES:
            required += [name + "_request", name, name + ".record"]
        required += [
            "sim_completed",
            "sim_final_check",
            "sim_observation",
            "sim_observation_final_check",
        ]
        observed = []
        for row in value["operations"]:
            target = {
                "profile_image_file": "profiles_request",
                "init_dynamics_file": "init_dynamics_request",
            }.get(row["name"])
            if target is not None:
                require(
                    len(observed) < len(required) and required[len(observed)] == target,
                    "File declaration outside its original source boundary",
                )
            else:
                observed.append(row["name"])
            require(row["status"] == "returned", "Failed operation in completed SIM")
        require(observed == required, "Complete ordered actual public SIM operations required")
        require(all(row["status"] == "saved" for row in captures), "Completed SIM has capture gaps")
        labels = [name + ".record" for name in INIT_STAGES[1:]] + [
            "poisson.cache",
            "core.cache",
            "profiles.after",
            "junctions.cache",
        ]
        for stage, fields in (
            ("init_setup", ("before", "after")),
            ("init_prelude", ("before", "after", "raw_returns")),
            (
                "init_dynamics",
                (
                    "before",
                    "after",
                    "stream_before",
                    "stream_after",
                    "rng_calls",
                    "tissue_record",
                    "raw_returns",
                ),
            ),
            (
                "init_storage",
                ("before", "after", "stream_before", "stream_after", "stores", "raw_returns"),
            ),
            (
                "init_electrical",
                ("before", "after", "rng_before", "rng_after", "stores", "raw_returns"),
            ),
            (
                "init_terminal",
                (
                    "linkage",
                    "before",
                    "after",
                    "calendar",
                    "sampled",
                    "configured_dt",
                    "stream_before",
                    "stream_after",
                    "work",
                    "helpers",
                    "callbacks",
                    "raw_returns",
                    "initial_diagnostics",
                ),
            ),
        ):
            labels.extend(stage + "." + field for field in fields)
        labels.extend(
            f"init_terminal.iteration.{i:04d}.after"
            for i in range(value["init_time_steps_completed"])
        )
        legacy._required_captures(captures, labels)
        require(
            molecules["selected"] is True
            and molecules["completed"] is True
            and imports["declared"] is True
            and imports["completed"] is True,
            "Actual enabled INIT molecular ancestry required",
        )
        history = legacy._short_history_captures(
            captures, value["init_time_steps_completed"], plan["flux_operator"], natural=True
        )
        sim = _sim_captures(captures, value, plan["flux_operator"])
    else:
        # A later publisher/runtime failure can follow a fully returned SIM.
        # Preserve that original claim and all available captures, while the
        # enclosing failed terminal always keeps completed-run credit at zero.
        require(
            type(value.get("sim_completed")) is bool
            and type(value.get("sim_time_steps_completed")) is int
            and 0 <= value["sim_time_steps_completed"] <= 512
            and value["sim_completed"] is (value["sim_time_steps_completed"] > 0),
            "Exact retained SIM prefix completion flags required",
        )
    return dict(
        outcome=value,
        captures=captures,
        initial_rng=rng,
        molecule_network=molecules,
        molecule_imports=imports,
        natural_terminal=history,
        complete_sim=sim,
        completed_observation=_observation(reader, root, plan, value),
    )


def _observation(reader, root, plan, outcome):
    """Authenticate available raw typed files; failed runs keep zero run credit."""
    policy = plan["_observation_policy"]
    value = outcome.get("sim_observation")
    completed = outcome["status"] == "completed"
    if value is None:
        require(not completed, "Completed SIM lacks its actual observation")
        return dict(completed=False, record=None, request_available=False)
    require(
        type(value) is dict
        and set(value)
        == {
            "started",
            "completed",
            "record",
            "cleanup_complete",
            "primary_present",
            "capture_errors",
            "captures",
            "raw_return_retained",
            "raw_partial_retained",
            "comparison_or_physical_credit",
        },
        "Exact observation outcome schema required",
    )
    for name in (
        "started",
        "completed",
        "cleanup_complete",
        "primary_present",
        "raw_return_retained",
        "raw_partial_retained",
        "comparison_or_physical_credit",
    ):
        require(type(value[name]) is bool, "Exact observation status required")
    require(
        value["comparison_or_physical_credit"] is False
        and type(value["capture_errors"]) is int
        and value["capture_errors"] >= 0,
        "Observation status cannot grant acceptance",
    )
    require(
        type(value["captures"]) is list and len(value["captures"]) <= 517,
        "Bounded observation capture roster required",
    )
    folder = root / "sim_observation"
    rows = []
    for index, row in enumerate(value["captures"]):
        require(
            type(row) is dict and set(row) == {"label", "status", "pin", "attempted_path"},
            "Exact typed capture row required",
        )
        require(row["status"] in ("saved", "attempted"), "Known typed capture status required")
        require(
            row["attempted_path"] == str(folder / f"capture-{index:04d}.json"),
            "Typed attempted capture path changed",
        )
        if row["pin"] is not None:
            path = reader.bind(row["pin"])
            require(
                path == folder / f"capture-{index:04d}.json", "Typed capture association changed"
            )
            for artifact in evidence.files(path, expected_sha256=row["pin"]["sha256"]):
                reader.bind(artifact)
            raw = evidence.read(path, expected_sha256=row["pin"]["sha256"])
            require(
                type(raw) is dict
                and set(raw) == {"tree", "columns"}
                and type(raw["tree"]) is dict
                and type(raw["columns"]) is dict,
                "Already typed wire required",
            )
            rows.append(dict(row, seal=evidence._seal(raw)))
        else:
            require(row["status"] != "saved", "Saved capture lacks its pin")
            partial = Path(row["attempted_path"])
            if partial.exists():
                reader.bind(launch.pin(partial))
                # Bytes exist, but no successful producer pin/complete capture is inferred.
    if value["record"] is None:
        require(not completed and value["completed"] is False, "Complete observation lacks record")
        return dict(
            completed=False, record=None, captures=value["captures"], request_available=False
        )
    path = reader.bind(value["record"])
    require(path == folder / "record.json", "Observation record association changed")
    record = reader.bound(value["record"])
    linkage = outcome.get("sim_linkage")
    require(
        type(linkage) is dict and type(linkage.get("configured_iterations")) is int,
        "Actual returned SIM linkage required",
    )
    count = linkage["configured_iterations"]
    require(1 <= count <= 512, "Complete bounded observation count required")
    trial = SimpleNamespace(
        identity=linkage["trial_identity"],
        iterations=range(count),
        operator_mode=linkage["operator_mode"],
    )
    provider = observation.constants(
        Path(plan["source"]) / observation.OBSERVER, ("KEY_SHA256", "KEY_REVIEW", "WRITER_SHA256")
    )
    context = SimpleNamespace(
        key_review=provider["KEY_REVIEW"],
        rows=rows,
        run_sha=plan["producers"][observation.KEY],
        observer_sha=policy["observer_sha256"],
    )
    observation._record(context, record, trial, plan["flux_operator"])
    require(
        record["producer"].get("review") == provider["KEY_REVIEW"],
        "Actual observer Key review changed",
    )
    reader.bound(policy["observer_review"])
    reader.bound(provider["KEY_REVIEW"])
    if completed or value["completed"]:
        require(
            value["started"]
            and value["completed"]
            and value["cleanup_complete"]
            and not value["primary_present"]
            and value["capture_errors"] == 0
            and value["raw_return_retained"],
            "Completed observation retains failure",
        )
    return dict(
        completed=value["completed"],
        record=value["record"],
        raw_record=record,
        captures=value["captures"],
        request_available=False,
    )


def _binding(reader, plan, output, report, terminal_pin):
    """Use authenticated saved execution artifacts, never a synthesized process."""
    require(
        report["status"] == "completed_unqualified" and not reader.issues,
        "Observation finalization requires full guarded completion",
    )
    policy = plan["_observation_policy"]
    completed = report["demonstration"]["completed_observation"]
    require(completed["completed"] is True, "Actual completed observation required")
    provider = observation.constants(
        Path(plan["source"]) / observation.OBSERVER, ("KEY_SHA256", "KEY_REVIEW", "WRITER_SHA256")
    )
    parameters = reader.bound(plan["parameter_inputs"])
    program = reader.bound(parameters["program"]["manifest"])
    from validation.betse import native_seed_demo_inputs as input_files

    root = Path(parameters["program"]["root"])
    current = input_files.inventory(root)
    initial = plan["initial_rng_inputs"]["inventory"]
    allowed = set(initial["directories"])
    for name, value in program["ordered_path_permission"]:
        if name.endswith("dirname") and value is not None:
            path = Path(value)
            require(path.is_relative_to(root), "Declared parameter directory escaped input tree")
            allowed.add(str(path.relative_to(root)))
            allowed.update(
                str(p.relative_to(root))
                for p in path.parents
                if p != root and p.is_relative_to(root)
            )
    require(
        current["files"] == initial["files"]
        and set(initial["directories"]) <= set(current["directories"]) <= allowed,
        "Complete input tree changed beyond declared native directories",
    )
    for name, row in current["files"].items():
        reader.bind(dict(path=str(root / name), sha256=row["sha256"]))
    originals = observation.check_original_sources(plan["sim_original_sources"])
    for name, row in originals["files"].items():
        reader.bind(dict(path=str(Path(originals["root"]) / name), sha256=row["sha256"]))
    return dict(
        kind=observation.BINDING_KIND,
        execution_source=dict(
            root=plan["source"],
            snapshot_sha256=plan["source_snapshot"]["sha256"],
            owned_files=plan["producers"],
        ),
        reviews=[policy["observer_review"], provider["KEY_REVIEW"]],
        runtime=launch.pin(output / "worker/runtime-after.json"),
        process=launch.pin(output / "process/result.json"),
        terminal=terminal_pin,
        inputs=dict(
            root=str(root),
            inventory=current,
            mode=plan["flux_operator"],
            profile=report["configuration_profile"],
        ),
        original_sources=originals["sha256"],
        observation_record=completed["record"],
    )


def _terminal(plan_path, digest, output, report):
    completed = report["demonstration"]["completed_observation"]
    return dict(
        kind="cells.completed_SIM_observation_postprocess@1",
        status="completed",
        observation=completed["record"],
        trial_identity=completed["raw_record"]["trial_identity"],
        plan=dict(path=str(Path(plan_path).resolve()), sha256=digest),
        controller=launch.pin(output / "result.json"),
        worker=launch.pin(output / "worker/result.json"),
        process=launch.pin(output / "process/result.json"),
        comparison_accepted=False,
        scientific_credit=0,
    )


def _finalized(reader, plan, plan_path, digest, output, report, request_pin, *, publishing=False):
    folder = Path(request_pin["path"]).parent
    require(
        not (folder / "failure.json").exists(), "Failed observation finalization cannot publish"
    )
    if not publishing:
        receipt = reader.read(folder / "result.json")
        require(
            receipt == dict(status="completed", request=request_pin, comparison_accepted=False),
            "Final observation request publication required",
        )
    request = reader.bound(request_pin)
    require(
        type(request) is dict and set(request) == {"record", "binding"},
        "Exact saved observation request required",
    )
    binding = reader.bound(request["binding"])
    terminal = reader.bound(binding["terminal"])
    require(
        terminal == _terminal(plan_path, digest, output, report),
        "Postprocess terminal differs from actual completed execution",
    )
    require(
        binding == _binding(reader, plan, output, report, binding["terminal"])
        and request["record"] == binding["observation_record"],
        "Saved observation binding differs from execution artifacts",
    )
    return dict(
        request=request,
        request_file=request_pin,
        accepted_observer_sha256=plan["_observation_policy"]["observer_sha256"],
        comparison_accepted=False,
        common_starting_authority_established=False,
    )


def finalize_observation(plan_path, *, plan_sha256, output, destination):
    """Explicit read-only-of-execution postprocess; source completion is not parity."""
    report = inspect_attempt(plan_path, plan_sha256=plan_sha256, output=output)
    require(
        report["status"] == "completed_unqualified"
        and report["source_evidence_complete"]
        and not report["verification_issues"],
        "Successful guarded SIM artifacts required",
    )
    reader = Reader()
    plan, _, _ = _plan(reader, Path(plan_path), plan_sha256)
    output, destination = payload._regular(output), payload._regular(destination)
    require(not destination.exists(), "Fresh observation finalization output required")
    protected = [
        output,
        Path(plan["source"]),
        Path(plan_path).parent,
        Path(reader.bound(plan["parameter_inputs"])["program"]["root"]),
        Path(plan["sim_original_sources"]["root"]),
        *map(Path, plan["runtime_roots"]),
    ]
    require(
        not any(
            destination == p or destination.is_relative_to(p) or p.is_relative_to(destination)
            for p in protected
        ),
        "Finalization output intersects evidence or inputs",
    )
    # Rebind all successful report bytes before creating any output.
    for row in report["observed_file_pins"]:
        reader.bind(row)
    destination.mkdir(parents=True, exist_ok=False)
    try:
        terminal = _terminal(plan_path, plan_sha256, output, report)
        snapshot.write_json(destination / "terminal.json", terminal)
        binding = _binding(reader, plan, output, report, launch.pin(destination / "terminal.json"))
        snapshot.write_json(destination / "binding.json", binding)
        request = dict(
            record=binding["observation_record"], binding=launch.pin(destination / "binding.json")
        )
        snapshot.write_json(destination / "request.json", request)
        selected = launch.pin(destination / "request.json")
        _finalized(
            reader, plan, Path(plan_path), plan_sha256, output, report, selected, publishing=True
        )
        for row in report["observed_file_pins"]:
            reader.bind(row)
        snapshot.write_json(
            destination / "result.json",
            dict(
                status="completed",
                request=selected,
                comparison_accepted=False,
            ),
        )
        return _finalized(reader, plan, Path(plan_path), plan_sha256, output, report, selected)
    except BaseException as error:
        try:
            snapshot.write_json(
                destination / "failure.json",
                dict(
                    status="failed",
                    primary=launch.error_record(error),
                    comparison_accepted=False,
                    partial_artifacts_may_exist=True,
                ),
            )
        except BaseException:
            pass
        raise


def _resources(reader, output, plan_path, plan, digest, terminal):
    # Explicit stack-diagnostic policy is part of this launch schema.
    checked = dict(plan, policy=dict(plan["policy"], wall_seconds=launch._wall_seconds(plan)))
    return legacy._resources(reader, output, plan_path, checked, digest, terminal)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", type=Path)
    parser.add_argument("--plan-sha256", required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--report", required=True, type=Path)
    args = parser.parse_args()
    value = inspect_attempt(args.plan, plan_sha256=args.plan_sha256, output=args.output)
    with args.report.open("x") as stream:
        json.dump(value, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
