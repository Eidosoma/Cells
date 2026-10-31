"""Write prospective declarations and metadata tools from frozen source only."""
# ruff: noqa: E501 -- Scientific scope statements and exact metadata adaptations.

import ast
import hashlib
import json
from pathlib import Path

ROOT = Path("/home/robert/Cells")
WORK = Path(__file__).parent
BASE = Path("/mnt/workspaces/Cells")
PARENT = BASE / "betse-normal-ecm-molecule-dispatch-prepared-20261031-01"
TRANSPORTER = BASE / "betse-normal-transporter-prepared-20261030-03"
PREFIX = "betse_normal_ecm_molecule_transport"
OLD = "betse_normal_ecm_molecule_dispatch"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    with path.open("x") as stream:
        json.dump(value, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")


def constants(path, names):
    return {
        n.targets[0].id: ast.literal_eval(n.value)
        for n in ast.parse(path.read_text()).body
        if isinstance(n, ast.Assign)
        and isinstance(n.targets[0], ast.Name)
        and n.targets[0].id in names
    }


def main():
    data = constants(
        ROOT / "validation/betse" / (PREFIX + "_fixtures.py"),
        {"CASES", "COMPONENT_CONTROLS", "RAW_CASES", "RAW_SETUP_CASES", "TRANSPORT_DEPENDENCIES"},
    )
    prior = constants(PARENT / "source/validation/betse" / (OLD + "_fixtures.py"), {"DEPENDENCIES"})
    groups = {}
    for key, test, category in (
        ("CASES", "test_two_owner_history", "positive"),
        ("RAW_CASES", "test_original_molecule_failure", "raw"),
        ("RAW_SETUP_CASES", "test_original_transporter_setup_failure", "raw_setup"),
        ("TRANSPORT_DEPENDENCIES", "test_transporter_dependency", "dependency"),
        ("DEPENDENCIES", "test_two_owner_dependency", "dependency"),
    ):
        for case in (prior if key == "DEPENDENCIES" else data)[key]:
            enabled = {"general_transport": 1, "GRN_only": 1, "both_disabled": 0}.get(case, 2)
            transporting = case not in ("GRN_only", "both_disabled", "disabled_configuration")
            positive = category == "positive"
            groups[category + "-" + case] = dict(
                category="component_control" if case in data["COMPONENT_CONTROLS"] else category,
                case=case,
                node_ids=[f"tests/unit/test_{PREFIX}.py::{test}[{case}]"],
                accepted_calls=3 if positive else 0,
                independent_forms=26 + 14 * enabled + 6 * transporting if positive else 0,
                native_captures=4
                if positive
                else 2
                if category == "raw"
                else 1
                if category == "raw_setup"
                else 0,
                biological_case=False,
                source_status="unrun",
            )
    planned = dict(
        checks=len(groups),
        positive_cases=len(data["CASES"]),
        component_controls=len(data["COMPONENT_CONTROLS"]),
        raw_cases=len(data["RAW_CASES"]),
        raw_setup_cases=len(data["RAW_SETUP_CASES"]),
        dependency_controls=len(data["TRANSPORT_DEPENDENCIES"]) + len(prior["DEPENDENCIES"]),
        accepted_calls=sum(g["accepted_calls"] for g in groups.values()),
        independent_reference_forms=sum(g["independent_forms"] for g in groups.values()),
        native_captures=sum(g["native_captures"] for g in groups.values()),
        biological_cases=0,
        independently_carried_trajectories=0,
    )
    assert len({node for g in groups.values() for node in g["node_ids"]}) == planned["checks"] == 60
    assert (
        planned["accepted_calls"] == 69
        and planned["independent_reference_forms"] == 1306
        and planned["native_captures"] == 102
    )
    write(
        WORK / (PREFIX + "_workqueue.json"),
        dict(
            kind="cells.held_general_ECM_transporter_workqueue@1",
            status="unrun",
            execution_hold=True,
            automatic_launch=False,
            groups=groups,
            planned=planned,
            form_arithmetic="Each positive case: 2 bootstrap + 2 per enabled cold owner + 3*(8 prefix/CaATP/commit/field + 4 per enabled channel/network owner + 2 if the general transporter flag is true). Empty-list configuration still sets that source flag true.",
            capture_arithmetic="23*(1 setup+3 dispatch)+4*(1 setup+1 failed molecular dispatch)+2*(1 failed transporter setup)=102.",
            pytest_collection=False,
            scientific_evaluations=0,
        ),
    )
    boundary = WORK / (PREFIX + "_boundary_01.json")
    audit = WORK / (PREFIX + "_implementation_audit_03.json")
    old = json.loads((PARENT / "source/validation/betse" / (OLD + "_protocol.json")).read_text())
    protocol = dict(old)
    protocol.update(
        kind="cells.held_ordinary_ECM_general_transporter_protocol@1",
        status="source_static_only_unrun",
        law_id="betse_supplied_FULL_ECM_general_transport_then_GRN_v1_5_0@1",
        purpose="Resolve the new reachable ECM configured-transporter update, complete object-cache and pre-channel conditional-input risks while retaining literal source defects.",
        parent=dict(path=str(PARENT), manifest_sha256=sha(PARENT / "MANIFEST.json")),
        transporter_component=dict(
            path=str(TRANSPORTER),
            inputs_sha256=sha(TRANSPORTER / "inputs.json"),
            common_files_byte_exact_to_parent=True,
            scientific_passes_inherited=0,
        ),
        planned=planned,
        native_methods_audited=14,
        native_files_installed_exact=332,
        source_boundary_sha256=sha(boundary),
        implementation_audit_sha256=sha(audit),
        implementation_audit="agent-work/cells-worker-01/workfiles/" + audit.name,
        source_scope="All-target cell-zone general-owner configured transporters on supplied ordinary FULL ECM input, optional independent existing GRN owner. None and empty-list configurations retain distinct native flags.",
        independent_reference_scope="Fresh Decimal100/160 configured rate/ordered ECM commits from actual pre-transporter input plus unchanged independently conditioned primary/CaATP, per-owner channels/chemistry/molecular ECM transport, deferred commit and complete field references. No carried reference trajectory.",
        transporter_cache="Complete public Transporter fields, generated strings, original cold metadata, ordered names/targets and flux presence are owned by molecules. Static fields cannot change; flux None is cold-only. Disabled owners remain absent.",
        original_partials="Explicit raw first/second missing-max-rate declarations reach original KeyError during cold read_transporters. A structural validation witness fills that single field only in a private validator copy, never in executed/native inputs. Inherited first/second general/GRN negative-molecule declarations retain all earlier transporter writes and original refusals.",
        transporter_source_defects=[
            "Current increment precedes all material commits; no transaction rollback or retry.",
            "Internal membrane-sample updates omit the stoichiometric coefficient; report the predicted discrepancy.",
            "ECM fast projection uses duplicate-site indexed last writes with total site membrane area; slow projection uses the original area map.",
            "Environment commits use the original target indexing after div_env; no ideal conservative scatter substitutes.",
            "ignore ECM is stored but unused in the native builder/executor; first scope explicitly declares False.",
            "Product Km is absent from the final executable rate; conversion factor 1e-3 lies outside each concentration power.",
            "Native transporter current uses bare valence while molecular charge publication retains scale_factor; no forced electrical closure.",
        ],
        accounting="Separate per-species bulk/environment changes, requested exchange, fast collocation defect, membrane-buffer discrepancy, source-weighted charge and current. Continue complete material/field/owner books. Compare original residuals to independent predictions rather than forcing zero.",
        ordinary_pump_weight="rho_pump remains scalar identity 1; cached activation is refused. No dormant movement, projector replacement or hypothetical ECM CaATP nonunit branch.",
        exclusions=[
            "whole native parser/physical initializer/seed/load/pickle/storage/display",
            "phase transition or latent disabled owner",
            "configured transporters in GRN owner and subset/expression transporter targets",
            "Molecule.pump and Molecule.gating active branches",
            "mitochondria/ER/flow/electroosmosis/dynamic deformation/osmotic mechanics/noise/events/FAST/GPU",
            "physical global conservation, energy/ATP/heat closure or biological calibration",
        ],
        unchanged_budgets=dict(
            old["unchanged_budgets"],
            configured_transporter_rates="validation/transport/betse_network_transport_protocol.json",
            configured_transporter_commits="Original ion FLOORS plus the existing 128*eps operation-count rule extended by the ECM site count; declared before any evaluation.",
        ),
    )
    write(ROOT / "validation/betse" / (PREFIX + "_protocol.json"), protocol)
    for suffix in ("driver", "metadata_check"):
        source = (
            PARENT / "source/agent-work/cells-worker-01/workfiles" / (OLD + "_" + suffix + ".py")
        )
        text = source.read_text().replace(OLD, PREFIX)
        text = text.replace(
            "ordinary_ecm_molecule_dispatch_01", "ordinary_ecm_molecule_transport_01"
        )
        text = text.replace("positive-general_only", "positive-general_transport")
        text = text.replace(
            "General-molecule source handoff is held", "General-transporter source handoff is held"
        )
        with (WORK / (PREFIX + "_" + suffix + ".py")).open("x") as stream:
            stream.write(text)
    print(json.dumps(planned, sort_keys=True))


if __name__ == "__main__":
    main()
