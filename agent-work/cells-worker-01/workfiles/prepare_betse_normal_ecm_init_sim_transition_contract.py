"""Write prospective transition declarations from literal AST metadata only."""
# ruff: noqa: E501 -- protocol prose and literal metadata strings.

import ast
import hashlib
import json
from pathlib import Path

ROOT = Path("/home/robert/Cells")
WORK = ROOT / "agent-work/cells-worker-01/workfiles"
PREFIX = "betse_normal_ecm_init_sim_transition"
PARENT = Path("/mnt/workspaces/Cells/betse-normal-ecm-init-phase-prepared-20261031-02")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    with path.open("x") as stream:
        json.dump(value, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")


def main():
    fixture = ROOT / "validation/betse" / f"{PREFIX}_fixtures.py"
    values = {}
    for node in ast.parse(fixture.read_text()).body:
        if (
            isinstance(node, ast.Assign)
            and isinstance(node.targets[0], ast.Name)
            and node.targets[0].id
            in {"CASES", "PREFIX_REFUSALS", "DEPENDENCIES", "OBSERVER_CASES", "KNOWN_ORACLE_LIMIT"}
        ):
            # Constants and a keyword-only dict literal are metadata, not fixture calls.
            if isinstance(node.value, ast.Call):
                values[node.targets[0].id] = {
                    k.arg: ast.literal_eval(k.value) for k in node.value.keywords
                }
            else:
                values[node.targets[0].id] = ast.literal_eval(node.value)
    groups = {}
    for key, category, test in (
        ("CASES", "positive", "test_retained_transition"),
        ("PREFIX_REFUSALS", "prefix", "test_prefix_refusal"),
        ("DEPENDENCIES", "dependency", "test_transition_dependency"),
        ("OBSERVER_CASES", "observer", "test_transition_observer_failure"),
    ):
        for case in values[key]:
            groups[category + "-" + case] = dict(
                category=category,
                case=case,
                node_ids=[f"tests/unit/test_{PREFIX}.py::{test}[{case}]"],
                SIM_accepted_calls=3
                if category == "positive"
                else {"before_call": 0, "accepted_call": 1, "headless_observation": 2}.get(case, 0),
                independent_forms=58 if category == "positive" else 0,
                native_captures=2
                if category == "positive"
                else int(case == "latent_None_channels"),
            )
    ids = [name for row in groups.values() for name in row["node_ids"]]
    assert len(ids) == len(set(ids)) == 42
    planned = dict(
        checks=42,
        positive_cases=16,
        prefix_refusals=5,
        dependency_controls=18,
        observer_controls=3,
        SIM_accepted_calls=51,
        positive_SIM_accepted_calls=48,
        independent_reference_forms=928,
        native_captures=33,
        biological_cases=0,
        independent_complete_INIT_SIM_trajectories=0,
    )
    assert sum(row["independent_forms"] for row in groups.values()) == 928
    assert sum(row["native_captures"] for row in groups.values()) == 33
    assert sum(row["SIM_accepted_calls"] for row in groups.values()) == 51
    queue = dict(
        kind="cells.held_INIT_SIM_transition_workqueue@1",
        status="unrun",
        execution_hold=True,
        automatic_launch=False,
        groups=groups,
        planned=planned,
        positive_form_arithmetic="16 * (2 phase rules + 2 bootstrap + 3 * 18 nine-mode forms) = 928",
        native_capture_arithmetic="16 retained reinitialize + 16 supplied-entry SIM + 1 latent-None raw = 33",
        no_fixture_reference_model_evaluation=True,
        pytest_collection=False,
    )
    write(WORK / f"{PREFIX}_workqueue.json", queue)
    source_audit = WORK / f"{PREFIX}_implementation_audit_03.json"
    protocol = dict(
        kind="cells.held_supplied_INIT_SIM_transition_protocol@1",
        status="source_static_only_unrun",
        law_id="betse_supplied_retained_INIT_to_SIM_v1_5_0@1",
        native_revision="5269a714aa2593ed2a6708c4516289977d8ae1a2",
        INIT_dependency=dict(path=str(PARENT), manifest_sha256=sha(PARENT / "MANIFEST.json")),
        independent_INIT02_source_gate_review=dict(
            path="/mnt/workspaces/Cells/betse-normal-ecm-init-phase-preflight-20261031-02/REVIEW.json",
            sha256="09ddb3c75ddef1492744932e16ae7c40890dc1df6ba2c077b3553717190a9fd2",
            scientific_acceptance=False,
        ),
        source_audit_sha256=sha(source_audit),
        planned=planned,
        form_modes=[
            "phase_rules",
            "bootstrap",
            "nak",
            "events",
            "material",
            "calcium",
            "channels",
            "network",
            "noise",
            "mechanics",
            "field",
        ],
        independent_precision=[100, 160],
        carried_reference_forms=0,
        unchanged_component_budget_sources=[
            "tests/unit/test_betse_normal_ecm_init_phase.py",
            "tests/unit/test_betse_normal_ecm_event_mechanics.py",
            "tests/unit/test_betse_normal_ecm_event_join.py",
            "validation/betse/betse_mechanics_join_checks.py",
        ],
        acceptance=dict(
            field_normalized_error_max=1.0,
            self_resolution_max=0.1,
            exact_native_owner_buffer_correspondence_required=True,
            full_selected_observation_and_native_sampling_checks_required=True,
        ),
        prepared_artifacts=dict(
            complete="CompleteInit, only exhausted full original INIT calendar",
            failed="FailedInitPrefix with actual InitRejected and accepted parent/declaration",
            paused_or_capped="Refused by normal preparation; original calendar preserved",
            SIM="SimPhase retains CompleteInit and separate fresh lifecycle journal",
        ),
        source_order=[
            "Retain simulator/cell/core/molecule owners; associate explicit equal general/world subsets and identical geometry/ion owners.",
            "Restore actual INIT cache, select new SIM flag/dt/total and explicit process RNG; execute initDenv and supplied ordered profile assignments.",
            "Execute unconditional static K draw, base/scheduled pressure/diffusion and block setup; reinitialize actual retained GRN, reconstruct non-None channels at carried Vm.",
            "Apply source mechanical entry writes, rho defaults and event finalizers, screening/conductivity and clear_storage/GRN history clearing; retain CaATP/NaK rates.",
            "Run source bootstrap update_V without normal check_v, create new SIM cursor/journal; then events, real NaK, material/CaATP/GRN/noise/mechanics/deferred commit/field checks in source order.",
        ],
        native_capture_scope="Independent native conditionals from actual incoming reinitialize and pre-bootstrap SIM buffers; no independently carried INIT trajectory.",
        RNG_contract="Explicit supplied SIM process stream or actual same-process post-INIT stream with no unowned draws; never inferred from pickle.",
        latent_None_channels="Capture actual retained latent gate cache then refuse; empty list reconstructs an empty enabled dictionary.",
        source_persistence_caveat="Native _pickle_phase saves before final sampled report; N0/N1 headless completion and failed prefixes do not attest native pickle/load/whole phase completion.",
        oracle_limit=values["KNOWN_ORACLE_LIMIT"],
        other_oracle_limits="INIT-ORACLE-DOMAIN-03: KLeak/CaLeak still guard [-0.120,+0.060] V before constant branches. No domain changes or fixture tuning.",
        inherited_failure="signed_environment remains failed 39/40; catalog05 remains 82 passed/1 Nav reference refusal/11 unrun. No prior pass inherited.",
        exclusions=[
            "native seed/load/pickle",
            "whole physical init_core/init_dynamics/run_sim_core",
            "native profile selection",
            "enabled general molecules",
            "GRN-disabled run",
            "ER/Ca_dyn",
            "enabled flow/electroosmosis/dynamic deformation",
            "FAST solver",
            "native storage/display",
            "GPU",
            "global material/energy conservation",
            "biological realism",
            "active Nav outside unchanged oracle domain",
        ],
        release=dict(
            execution_hold=True,
            driver_metadata_only=True,
            new_explicit_Chief_release_controller_required=True,
            no_scientific_launch=True,
            no_automatic_followup=True,
        ),
        scientific_imports=0,
        scientific_AST_executions=0,
        pytest_collections=0,
        fixture_reference_model_evaluations=0,
        numerical_runs=0,
        active_job_queries=0,
    )
    write(ROOT / "validation/betse" / f"{PREFIX}_protocol.json", protocol)
    # Reuse exactly the established stdlib capture/hold controls, adapting only
    # profile/case/hold names for this independently held format profile.
    metadata = (WORK / "betse_normal_ecm_init_phase_metadata_check.py").read_text()
    metadata = metadata.replace("ordinary_ecm_init_phase_01", "ordinary_ecm_init_sim_transition_01")
    metadata = metadata.replace("positive-active", "positive-ordinary")
    metadata = metadata.replace("INIT source handoff is held", "INIT-to-SIM source handoff is held")
    metadata = metadata.replace(
        "new_INIT_profile_accepts_scalar", "transition_profile_accepts_scalar"
    )
    metadata = metadata.replace(
        "cells.INIT_metadata_controls@1", "cells.INIT_SIM_metadata_controls@1"
    )
    with (WORK / f"{PREFIX}_metadata_check.py").open("x") as stream:
        stream.write(metadata)
    print(
        json.dumps(
            dict(
                status="held_declarations_written",
                checks=42,
                reference_forms=928,
                native_captures=33,
            )
        )
    )


if __name__ == "__main__":
    main()
