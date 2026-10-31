"""Declare the held lifecycle plan and scope using literal source metadata only."""
# ruff: noqa: E501 -- Literal scope and provenance statements.

import ast
import hashlib
import json
from pathlib import Path

ROOT = Path("/home/robert/Cells")
WORK = Path(__file__).parent
BASE = Path("/mnt/workspaces/Cells")
PARENT = BASE / "betse-normal-ecm-molecule-transport-prepared-20261031-01"
PREFIX = "betse_normal_ecm_molecule_lifecycle"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    with path.open("x") as stream:
        json.dump(value, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")


def main():
    names = {
        "CASES",
        "RAW_INIT_CASES",
        "RAW_SIM_CASES",
        "PREFIX_REFUSALS",
        "OBSERVER_CASES",
        "DEPENDENCIES",
    }
    data = {
        n.targets[0].id: ast.literal_eval(n.value)
        for n in ast.parse((ROOT / "validation/betse" / (PREFIX + "_fixtures.py")).read_text()).body
        if isinstance(n, ast.Assign)
        and isinstance(n.targets[0], ast.Name)
        and n.targets[0].id in names
    }
    groups = {}
    for key, test, category in (
        ("CASES", "test_actual_lifecycle", "positive"),
        ("RAW_INIT_CASES", "test_original_INIT_failure", "raw_INIT"),
        ("RAW_SIM_CASES", "test_original_warm_failure", "raw_SIM"),
        ("PREFIX_REFUSALS", "test_incomplete_INIT_refusal", "prefix"),
        ("OBSERVER_CASES", "test_observer_partial_retention", "observer"),
        ("DEPENDENCIES", "test_lifecycle_dependency_refusal", "dependency"),
    ):
        for case in data[key]:
            positive = key == "CASES"
            count = 0 if case == "zero_INIT_calls" else 1 if case == "one_INIT_call" else 3
            enabled = {"general_only": 1, "GRN_only": 1, "both_disabled": 0}.get(case, 2)
            transporting = case not in ("GRN_only", "both_disabled", "null_transporters")
            groups[category + "-" + case] = dict(
                category=category,
                case=case,
                node_ids=[f"tests/unit/test_{PREFIX}.py::{test}[{case}]"],
                positive_INIT_calls=count if positive else 0,
                positive_SIM_calls=3 if positive else 0,
                independent_forms=12
                + 2 * enabled
                + (count + 3) * (12 + 4 * enabled + 2 * transporting)
                if positive
                else 0,
                native_captures=5 + count
                if positive
                else 1
                if key in ("RAW_INIT_CASES", "RAW_SIM_CASES")
                else 0,
                source_status="unrun",
                biological_case=False,
            )
    planned = dict(
        checks=len(groups),
        positive_cases=len(data["CASES"]),
        raw_INIT_cases=len(data["RAW_INIT_CASES"]),
        raw_SIM_cases=len(data["RAW_SIM_CASES"]),
        prefix_refusals=len(data["PREFIX_REFUSALS"]),
        observer_cases=len(data["OBSERVER_CASES"]),
        dependency_controls=len(data["DEPENDENCIES"]),
        positive_INIT_calls=sum(g["positive_INIT_calls"] for g in groups.values()),
        positive_SIM_calls=sum(g["positive_SIM_calls"] for g in groups.values()),
        independent_reference_forms=sum(g["independent_forms"] for g in groups.values()),
        native_captures=sum(g["native_captures"] for g in groups.values()),
        biological_cases=0,
        independently_carried_reference_trajectories=0,
    )
    assert len({node for g in groups.values() for node in g["node_ids"]}) == planned["checks"] == 54
    assert planned["positive_INIT_calls"] == 61 and planned["positive_SIM_calls"] == 66
    write(
        WORK / (PREFIX + "_workqueue.json"),
        dict(
            kind="cells.held_molecule_lifecycle_workqueue@1",
            status="unrun",
            execution_hold=True,
            automatic_launch=False,
            groups=groups,
            planned=planned,
            form_arithmetic="Each positive: 12 setup/bootstrap/clock/phase-reset forms + 2 per enabled cold owner + (INIT_calls+3)*(12 NaK/material/CaATP/disabled-mechanics/commit/field forms + 4 per enabled channels/network owner + 2 if general transporters is non-null). Empty configurations retain the source flag.",
            capture_arithmetic="Positive: 1 cold + INIT_calls dispatch + 1 retained warm + 3 SIM dispatch; six raw controls each retain one actual failure conditional. Other controls have no accuracy forms/captures or accepted-call credit; their actual source-prefix preparation remains uncredited.",
            pytest_collections=0,
            scientific_evaluations=0,
        ),
    )
    audit = WORK / (PREFIX + "_implementation_audit_03.json")
    boundary = WORK / (PREFIX + "_boundary_01.json")
    deps = WORK / (PREFIX + "_dependencies_01.json")
    old = json.loads(
        (
            PARENT / "source/validation/betse/betse_normal_ecm_molecule_transport_protocol.json"
        ).read_text()
    )
    inherited_keys = (
        "unchanged_budgets",
        "inherited_oracle_limits",
        "transporter_source_defects",
        "configuration_obstruction",
        "native_revision",
        "accounting",
        "amounts",
        "ordinary_pump_weight",
    )
    protocol = {k: old[k] for k in inherited_keys}
    protocol.update(
        kind="cells.held_ordinary_ECM_molecule_lifecycle_protocol@1",
        status="source_static_only_unrun",
        law_id="betse_supplied_ECM_general_transport_INIT_to_SIM_v1_5_0@1",
        purpose="Resolve phase-selector identity, retained owner/core/molecule identity, transporter rebuild/flux epoch, storage resets, INIT completion admission and independent SIM clock risks.",
        source_scope="Supplied cold setup -> bounded complete headless INIT -> retained original general-then-GRN reinitialize -> three-call supplied no-intervention SIM material seam. Independent stable owner flags and stable configured chemistry/gates/publication policy. Original physical declarations are unchanged and untuned.",
        source_call_order=[
            "actual phase/legacy selection",
            "supplied core/tissue seams and static setup",
            "general then GRN cold constructors",
            "INIT source labels/NaK/material/CaATP/general transporters+channels+chemistry/GRN channels+chemistry/deferred commit/fields",
            "complete INIT admission",
            "SIM profiles/initDenv/static/block resets",
            "general then GRN retained reinitialize",
            "mechanics entry/event finalizers/screening/clear_storage",
            "new SIM clock/journal/bootstrap",
            "three source-ordered SIM calls",
        ],
        event_boundary="No fire_events or makeAllChanges equivalence is claimed. Native SIM calls those even with no scheduled interventions. This explicit supplied material seam keeps their inputs stable and records zero event-fire calls; it is not a whole SIM loop or physical initializer claim.",
        cold_presence="rho_pump and rho_channel are absent before cold owners and are written late. Actual cache presence and original failures are retained; no missing native attribute is inferred.",
        owner_rules="Enabled original owners, cores and molecule objects survive warm setup; no read_substances call or fresh cold substitute. Non-null configured transporters/channels rebuild; None and empty retain distinct flags. Stable disabled owners stay absent; latent-null or changed-enable transitions are refused with source evidence rather than erased.",
        reset_rules="Literal clear_storage/clear_cache resets actual time lists, not concentrations or transporter flux. Non-null read_transporters already rebuilds flux=None. CaATP and NaK attributes survive entry; disabled CaATP retains cache while each SIM NaK producer can reset its proxy.",
        clock_rules="Parameters.load truncates total/dt; phase selects independent original calendar. Labels are linspace(0,N*dt,N), separate from accumulated material dt. Counts0/1/3 and sample indices retain native endpoint rules. No rebasing an incomplete, failed, paused or capped INIT prefix.",
        independent_reference_scope="Fresh Decimal100/160 actual incoming conditionals for cold/setup, clocks, phase reset, NaK/primary material/CaATP, each actual owner's transporters/channels/chemistry, deferred primary commit and full fields. No carried reference trajectory. Exact native captures are local owner boundaries, not independent whole trajectories.",
        explicit_dependencies=json.loads(deps.read_text()),
        source_boundary_sha256=sha(boundary),
        implementation_audit_sha256=sha(audit),
        implementation_audit=str(audit.relative_to(ROOT)),
        failure_capture_dependency=json.loads(
            (WORK / (PREFIX + "_capture_dependency_01.json")).read_text()
        ),
        AST_proofs=len(json.loads(audit.read_text())["proofs"]),
        native_methods_audited=27,
        native_files_installed_exact=332,
        planned=planned,
        original_partials="Two cold and two retained warm missing-max-rate controls preserve original KeyError and earlier writes. Validator-only witnesses never restore a field in executed input. Raw general/GRN negative-molecule and observer failures retain actual partials and accepted prefix distinctly.",
        exclusions=[
            "native seed/parser/physical initializer/pickle/load/storage/display",
            "whole SIM event loop",
            "changed owner enablement/configuration/cold-publication or latent dictionaries",
            "general transporter subset targets or configured GRN transporters",
            "Molecule.pump/gating active branches",
            "ER/mitochondria/flow/electroosmosis/dynamic deformation/osmotic coupling/noise/events/FAST/GPU",
            "nonunit rho or extra flux",
            "global physical conservation, energy/ATP/heat closure and biological calibration",
        ],
        release=dict(
            execution_hold=True,
            metadata_only_driver=True,
            separately_requested_Chief_review_and_release_controller_required=True,
        ),
        scientific_imports=0,
        scientific_AST_executions=0,
        fixture_model_reference_evaluations=0,
        pytest_collections=0,
        numerical_runs=0,
        inherited_scientific_passes=0,
    )
    write(ROOT / "validation/betse" / (PREFIX + "_protocol.json"), protocol)
    for suffix in ("driver", "metadata_check"):
        source = (
            PARENT
            / "source/agent-work/cells-worker-01/workfiles"
            / ("betse_normal_ecm_molecule_transport_" + suffix + ".py")
        )
        text = (
            source.read_text()
            .replace("betse_normal_ecm_molecule_transport", PREFIX)
            .replace("ordinary_ecm_molecule_transport_01", "ordinary_ecm_molecule_lifecycle_01")
            .replace("positive-general_transport", "positive-both_enabled")
            .replace(
                "General-transporter source handoff is held",
                "Molecule-lifecycle source handoff is held",
            )
        )
        if suffix == "metadata_check":
            text = text.replace(
                "max_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024,",
                "measured_process_VmHWM_bytes=int(next(row.split()[1] for row in Path('/proc/self/status').read_text().splitlines() if row.startswith('VmHWM:'))) * 1024,\n            inherited_getrusage_maxrss_is_not_this_process_measurement=True,",
            )
        with (WORK / (PREFIX + "_" + suffix + ".py")).open("x") as stream:
            stream.write(text)
    print(json.dumps(planned, sort_keys=True))


if __name__ == "__main__":
    main()
