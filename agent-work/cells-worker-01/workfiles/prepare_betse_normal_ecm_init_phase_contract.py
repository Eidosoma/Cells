# ruff: noqa: E501
"""Write prospective INIT contracts from literal source metadata only."""

import ast
import hashlib
import json
from pathlib import Path

ROOT = Path("/home/robert/Cells")
WORK = ROOT / "agent-work/cells-worker-01/workfiles"
PARENT = Path("/mnt/workspaces/Cells/betse-normal-ecm-run-lifecycle-prepared-20261031-02")
PREFIX = "betse_normal_ecm_init_phase"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    with path.open("x") as stream:
        json.dump(value, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")


def main():
    tree = ast.parse((ROOT / "validation/betse" / f"{PREFIX}_fixtures.py").read_text())
    roster = {
        n.targets[0].id: ast.literal_eval(n.value)
        for n in tree.body
        if isinstance(n, ast.Assign)
        and isinstance(n.targets[0], ast.Name)
        and n.targets[0].id in {"CASES", "RAW_CASES", "DEPENDENCIES", "OBSERVER_CASES"}
    }
    test = "tests/unit/test_" + PREFIX + ".py"
    groups = {}
    for label, function, category in (
        ("CASES", "test_init_history", "positive"),
        ("RAW_CASES", "test_init_raw_refusal", "raw"),
        ("DEPENDENCIES", "test_init_dependency_refusal", "dependency"),
        ("OBSERVER_CASES", "test_init_observer_retention", "observer"),
    ):
        for case in roster[label]:
            count = 0 if case == "zero_calls" else 1 if case == "one_call" else 3
            groups[category + "-" + case] = dict(
                node_ids=[test + "::" + function + "[" + case + "]"],
                category=category,
                case=case,
                accepted_calls=count if category == "positive" else 0,
                independent_forms=6 + 14 * count if category == "positive" else 0,
            )
    native = {
        name: sha(Path("/mnt/workspaces/Cells/betse-v1.5.0") / name)
        for name in (
            "betse/science/sim.py",
            "betse/science/simrunner.py",
            "betse/science/parameters.py",
            "betse/science/sim_toolbox.py",
            "betse/science/phase/phasecls.py",
            "betse/science/chemistry/networks.py",
            "betse/science/tissue/tishandler.py",
            "betse/science/math/modulate.py",
        )
    }
    budgets = {
        name: dict(path=name, sha256=sha(PARENT / "source" / name))
        for name in (
            "validation/betse/betse_ecm_transport_protocol.json",
            "validation/betse/betse_normal_pump_join_protocol.json",
            "validation/betse/betse_normal_ecm_catalog_join_protocol.json",
            "validation/betse/betse_normal_ecm_event_mechanics_protocol.json",
        )
    }
    protocol = dict(
        kind="cells.ordinary_INIT_prospective_contract@1",
        status="held_source_preparation_unrun",
        law_id="betse_ordinary_FULL_ECM_supplied_INIT_v1_5_0@1",
        execution_hold=True,
        scientific_release_authorized=False,
        automatic_launch=False,
        automatic_polling=False,
        automatic_followup=False,
        parent=dict(
            path=str(PARENT / "inputs.json"),
            sha256=sha(PARENT / "inputs.json"),
            qualification_inherited=False,
        ),
        source_scope=dict(
            phase="INIT",
            legacy_run_sim=False,
            solver="FULL",
            is_ecm=True,
            grn_enabled=True,
            molecules_enabled=False,
            Ca_dyn=False,
            fluid_flow=False,
            td_deform=False,
            sim_eosmosis=False,
            maximum_material_calls=3,
            admitted_original_counts="N0,N1 and unchanged-calendar bounded prefix of any admitted native count",
            defaults="init active defaults True per population; all populations constructed even when inactive",
        ),
        setup_scope=[
            "Supplied pre-static tissue/init_core owner values, with source zero initial Vm and pressure",
            "One explicit native MT19937 static_K draw even at zero level; original K scaling and untouched base/scheduled stores",
            "Fresh cold GRN/catalog construction; full inactive private caches retained",
            "Supplied ordinary mechanics entry view and caches on identical owners/measures/maps",
            "Complete native global and targeted event finalizers, local Python shuffle, preserved unused shuffled-copy target convention",
            "Only constant or dormant source f_sweep targeted callbacks; legacy _run_sim=False leaves unspecified slope None",
            "Existing explicitly supplied conditional screening/conductivity cache seam; no whole init_dynamics qualification",
        ],
        call_order=[
            "reset fluxes",
            "real native maintained-pool NaK",
            "primary membrane/GJ/ECM/intracellular movers",
            "CaATP",
            "GRN clear/transporters/INIT-active channels/modulators/chemistry-movement",
            "osmotic and steady mechanics",
            "deferred primary commit",
            "current/environment/voltage reconstruction and check_v",
            "headless sample eligibility",
        ],
        unreachable=["SIM event fire", "SIM dynamic protein-noise draw and application"],
        explicit_refusals=[
            "General molecule handler or GRN-disabled owner composition remains unqualified",
            "Enabled ER, fluid flow, electroosmosis or dynamic deformation",
            "Seed/load/profile selection or full physical initializer claims",
            "INIT-to-SIM carry without audited source reinitialization",
            "Native sampled storage/display/pickle and whole run_sim_core completion",
            "Field <=16 cells versus quartic display >=25 boundary is unchanged",
        ],
        planned=dict(
            checks=len(groups),
            positive_cases=len(roster["CASES"]),
            raw_cases=len(roster["RAW_CASES"]),
            dependency_controls=len(roster["DEPENDENCIES"]),
            observer_controls=len(roster["OBSERVER_CASES"]),
            accepted_calls=sum(g["accepted_calls"] for g in groups.values()),
            independent_reference_forms=sum(g["independent_forms"] for g in groups.values()),
            native_captures=len(roster["CASES"])
            + len(roster["RAW_CASES"])
            + len(roster["OBSERVER_CASES"]),
        ),
        acceptance=dict(
            native="Complete same-source typed arrays/caches/stores, both RNG receipts and exact clock/native stages",
            independent="Fresh stdlib Decimal100/160 setup and seven one-call conditional modes, from each actual incoming state",
            reference_modes=[
                "setup",
                "cold_initialization",
                "bootstrap",
                "nak",
                "material",
                "calcium",
                "channels",
                "network",
                "mechanics",
                "field",
            ],
            self_resolution_fraction=0.1,
            carried_reference_forms=0,
            independent_trajectory=False,
            inherited_budget_files=budgets,
            budgets_changed=False,
            NaK_flux_proxy="existing 2e-18 + 2e-11*abs(reference)",
            static_K="existing ECM diffusion 3e-20 + 6e-12*abs(reference); uniform scalar 3e-14 + 6e-12*abs(reference)",
            physical_global_conservation_credit=False,
            formal_ATP_consumption_claim=False,
            retained_material_panel_passed=False,
            retained_material_failure="signed_environment remains 39/40; no new answer/tolerance used",
        ),
        capture_profile=dict(
            name="ordinary_ecm_init_phase_01",
            status="new prospective held profile; Chief review required",
            member_limit=310689,
            source_format_capacity_bound=True,
            observed_case_maximum_claim=False,
            all_captures_fit_byte_caps_claim=False,
            compressed_expanded_JSON_bytes_each=64 * 2**20,
            NPY_header_bytes=16 * 2**10,
            compression="ZIP_STORED",
        ),
        resources=dict(
            cpu_count=1,
            threads=1,
            gpu=False,
            max_command_seconds=480,
            max_process_tree_rss_bytes=2**30,
            min_available_host_memory_bytes=8 * 2**30,
            coordination="Chief chooses a CPU in a newly requested round; no worker launch or automatic followup",
        ),
        native_source=dict(
            checkout="/mnt/workspaces/Cells/betse-v1.5.0",
            installed_package="/mnt/workspaces/Cells/venv-betse/lib/python3.13/site-packages/betse",
            revision="5269a714aa2593ed2a6708c4516289977d8ae1a2",
            source_sha256=native,
        ),
        no_science_preparation=dict(
            imports=0,
            scientific_AST_executions=0,
            fixture_model_reference_evaluations=0,
            pytest_collection=0,
            numerical_runs=0,
            active_job_queries=0,
        ),
    )
    write(ROOT / "validation/betse" / f"{PREFIX}_protocol.json", protocol)
    write(
        WORK / f"{PREFIX}_workqueue.json",
        dict(
            kind="cells.held_INIT_workqueue@1",
            groups=groups,
            planned=protocol["planned"],
            execution_hold=True,
            automatic_launch=False,
        ),
    )
    write(
        ROOT / "validation/betse" / f"{PREFIX}_source_map.json",
        dict(
            kind="cells.ordinary_INIT_source_map@1",
            native_source=protocol["native_source"],
            source_boundary=str(WORK / f"{PREFIX}_source_boundary_01.json"),
            implementation_audit="agent-work/cells-worker-01/workfiles/"
            + PREFIX
            + "_implementation_audit_01.json",
            same_node_parent_sha256=sha(PARENT / "inputs.json"),
            source_dispatch="native read_channels/init_active and run_loop_channels under INIT; exact private dispatch phase substitution",
            full_bodies=[
                "native global and targeted finalizers",
                "native f_sweep",
                "native pumpNaKATP",
                "common _material_step with one mechanics hook",
                "native CaATP/current/environment/voltage capture bodies",
            ],
            source_slices=[
                "init_dynamics static_K/base/pressure/block/ER-disabled stores",
                "ordinary ECM NaK caller",
                "native count/phase-time/linspace/sampling clock",
            ],
            conditional_supplied_owners=[
                "tissue/init_core values before setup",
                "original macro geometry and cache-initializer inputs",
                "mechanical DEC and neighbor/inverse view",
            ],
            source_stage_equations_changed=False,
            shared_or_prior_frozen_files_edited=False,
            qualification_inherited=False,
        ),
    )
    print(json.dumps(protocol["planned"]))


if __name__ == "__main__":
    main()
