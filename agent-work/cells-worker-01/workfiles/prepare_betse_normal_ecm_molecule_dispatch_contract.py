"""Write held declarations and adapt existing metadata-only packaging helpers."""
# ruff: noqa: E501 -- protocol text and exact helper adaptations.

import ast
import hashlib
import json
from pathlib import Path

ROOT = Path("/home/robert/Cells")
WORK = ROOT / "agent-work/cells-worker-01/workfiles"
PREFIX = "betse_normal_ecm_molecule_dispatch"
PARENT = Path("/mnt/workspaces/Cells/betse-normal-ecm-init-phase-prepared-20261031-02")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    with path.open("x") as stream:
        json.dump(value, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")


def main():
    data = {
        n.targets[0].id: ast.literal_eval(n.value)
        for n in ast.parse((ROOT / "validation/betse" / f"{PREFIX}_fixtures.py").read_text()).body
        if isinstance(n, ast.Assign)
        and isinstance(n.targets[0], ast.Name)
        and n.targets[0].id in {"CASES", "RAW_CASES", "DEPENDENCIES"}
    }
    groups = {}
    for label, category, test in (
        ("CASES", "positive", "test_two_owner_history"),
        ("RAW_CASES", "raw", "test_original_molecule_failure"),
        ("DEPENDENCIES", "dependency", "test_two_owner_dependency"),
    ):
        for case in data[label]:
            enabled = {
                "general_only": 1,
                "GRN_only": 1,
                "both_disabled": 0,
                "disabled_shared_carry": 0,
            }.get(case, 2)
            groups[category + "-" + case] = dict(
                category=category,
                case=case,
                node_ids=[f"tests/unit/test_{PREFIX}.py::{test}[{case}]"],
                accepted_calls=3 if category == "positive" else 0,
                independent_forms=26 + 14 * enabled if category == "positive" else 0,
                native_captures=4 if category == "positive" else 2 if category == "raw" else 0,
            )
    planned = dict(
        checks=44,
        positive_cases=19,
        raw_cases=4,
        dependency_controls=21,
        accepted_calls=57,
        independent_reference_forms=942,
        native_captures=84,
        biological_cases=0,
        independently_carried_trajectories=0,
    )
    assert (
        len(groups) == 44 and len({name for v in groups.values() for name in v["node_ids"]}) == 44
    )
    assert sum(v["independent_forms"] for v in groups.values()) == 942
    assert sum(v["native_captures"] for v in groups.values()) == 84
    assert sum(v["accepted_calls"] for v in groups.values()) == 57
    write(
        WORK / f"{PREFIX}_workqueue.json",
        dict(
            kind="cells.held_general_molecule_workqueue@1",
            status="unrun",
            execution_hold=True,
            automatic_launch=False,
            groups=groups,
            planned=planned,
            form_arithmetic="Each positive case: 2 bootstrap + 2 per enabled cold owner + 3*(8 prefix/CaATP/commit/field forms + 4 per enabled channel/network owner); total 942.",
            capture_arithmetic="19*(1 setup + 3 dispatch) + 4*(1 setup + 1 failed dispatch) = 84 conditional captures.",
            scientific_evaluations=0,
            pytest_collection=False,
        ),
    )
    boundary = WORK / f"{PREFIX}_source_boundary_01.json"
    source_audit = WORK / f"{PREFIX}_implementation_audit_01.json"
    protocol = dict(
        kind="cells.held_ordinary_ECM_general_molecule_protocol@1",
        status="source_static_only_unrun",
        law_id="betse_supplied_FULL_ECM_general_then_GRN_v1_5_0@1",
        native_revision="5269a714aa2593ed2a6708c4516289977d8ae1a2",
        parent=dict(path=str(PARENT), manifest_sha256=sha(PARENT / "MANIFEST.json")),
        source_boundary_sha256=sha(boundary),
        implementation_audit_sha256=sha(source_audit),
        native_methods_audited=22,
        native_files_installed_exact=332,
        AST_proofs=26,
        planned=planned,
        declaration="Separate actual general-network and GRN configurations, independent flags, role-labelled nonempty X/Y owners, common qualified primary/field geometry and explicit shared initial publications.",
        source_setup="Native general handler constructor/read or retained reinitializer before GRN; this first fresh supplied entry admits absent disabled owners, not latent disabled caches or a phase transition.",
        source_call_order=[
            "ordinary primary refresh",
            "CaATP with source-disabled ER",
            "supplied qualified late flux seam",
            "general clear/transporters/channels/modulators/chemistry+ECM transport",
            "GRN clear/transporters/channels/modulators/chemistry+ECM transport",
            "noise/mechanics guards explicitly false",
            "deferred primary commit",
            "full current/environment/voltage fields",
        ],
        source_flags="Present general network implements an explicit True/False flag; GRN is selected independently. No active GRN object is constructed in the GRN-disabled path.",
        configuration_obstruction=json.loads(boundary.read_text())[
            "general_configuration_obstruction"
        ],
        obstruction_scope="Local Parameters.load missing-section branch has no molecules_enabled writer; no native file parser or complete configuration run has been executed.",
        general_schema_bridge="Keep owner=molecules in actual declarations/cache identities; reuse existing core validation predicates with a temporary validation-only owner label. This does not construct a GRN or infer a source flag.",
        publication="Native direct assignment: general writes first and GRN replaces it when both enabled and publication is true. Publication false retains the previous shared epoch. Field projections bind that exact shared epoch; publications are never summed.",
        amounts="Separate namespaced source-effective molecular books, native true-volume diagnostics, all deferred primary candidate buffers and original primary amount ledgers. Old signed_environment 39/40 failure remains failed; no global conservation credit.",
        osmotic_limit="Native osmotic_P sums both active molecular owners independently; this first composition keeps its source guard false and does not claim enabled osmotic/mechanical coupling.",
        independent_reference_scope="Fresh Decimal100/160 primary/CaATP prefix, each enabled channels/chemistry/ECM-transport boundary, actual pre-deferred-commit and full-field conditionals. No independently carried trajectory or accumulated allowance.",
        native_scope="Original setup and adjacent FULL two-handler dispatch slices on complete actual incoming buffers, including source refusals before runtime inventory.",
        unchanged_budgets=dict(
            material="validation/betse/betse_ecm_transport_checks.py",
            fields="tests/unit/test_betse_normal_ecm_field_join.py",
            molecular_amount_charge_current="tests/unit/test_betse_ecm_grn_join.py",
            channels_and_CaATP="tests/unit/test_betse_normal_ecm_catalog_join.py",
            max_normalized_error=1.0,
            max_self_resolution=0.1,
        ),
        source_ER="Parameters.load sets Ca_dyn=False; handler flags cannot enable ER. No forced enabled branch.",
        inherited_oracle_limits="Nav and other channel reference domains remain unchanged. KLeak/CaLeak guards still precede constant branches. Catalog05 no_CaATP Nav reference refusal and all 11 unrun cases remain uncredited; no fixture/domain tuning.",
        exclusions=[
            "whole physical initializer/phase",
            "seed/load/pickle/native storage/display",
            "INIT-to-SIM transition",
            "latent disabled owner carry",
            "enabled extra transporters",
            "mitochondria",
            "flow/electroosmosis/dynamic deformation",
            "enabled osmotic/mechanics",
            "dynamic noise/scheduled events",
            "FAST",
            "GPU",
            "biological realism/global conservation",
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
        active_job_queries=0,
    )
    write(ROOT / "validation/betse" / f"{PREFIX}_protocol.json", protocol)
    old = "betse_normal_ecm_init_sim_transition"
    adaptations = (
        ("driver.py", WORK / f"{old}_driver.py"),
        ("metadata_check.py", WORK / f"{old}_metadata_check.py"),
        ("package.py", WORK / f"prepare_{old}_package.py"),
    )
    for suffix, path in adaptations:
        text = (
            path.read_text()
            .replace(old, PREFIX)
            .replace("init-sim-transition", "molecule-dispatch")
        )
        text = text.replace(
            "INIT-to-SIM source handoff is held", "General-molecule source handoff is held"
        )
        text = text.replace("positive-ordinary", "positive-general_only")
        text = text.replace("_implementation_audit_03.json", "_implementation_audit_01.json")
        text = text.replace(
            "cells.held_INIT_SIM_transition", "cells.held_general_molecule_dispatch"
        )
        text = text.replace("cells.INIT_SIM_metadata", "cells.general_molecule_metadata")
        text = text.replace(
            "Supplied hydrated retained owners, native reinitialize and post-clear SIM conditionals; no independently carried INIT/SIM trajectory or native persistence",
            "Supplied ordinary FULL/ECM general and GRN owners, original setup/dispatch and prefix/commit/field conditionals; explicit disabled paths, no whole initializer/trajectory/persistence",
        )
        target = WORK / (("prepare_" if suffix == "package.py" else "") + PREFIX + "_" + suffix)
        text = text.replace(
            "ordinary_ecm_init_sim_transition_01", "ordinary_ecm_molecule_dispatch_01"
        )
        text = text.replace("transition", "general_molecule")
        text = text.replace(
            "Source-only INIT-to-SIM preparation", "Source-only general-molecule preparation"
        )
        with target.open("x") as stream:
            stream.write(text)
        compile(text, str(target), "exec")
    print(
        json.dumps(dict(status="held_contract_written", checks=44, forms=942, native_captures=84))
    )


if __name__ == "__main__":
    main()
