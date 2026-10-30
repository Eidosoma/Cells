"""Seal source-only ER preparation metadata without importing scientific code."""

# ruff: noqa: E501 -- protocol descriptions and fixed formula strings.

import ast
import copy
import hashlib
import json
from pathlib import Path

ROOT = Path("/home/robert/Cells")
WORK = ROOT / "agent-work/cells-worker-01/workfiles"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    with Path(path).open("x") as stream:
        json.dump(value, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")


base = json.loads((ROOT / "validation/betse/betse_normal_er_join_protocol.json").read_text())
source_map = json.loads(
    (ROOT / "validation/betse/betse_normal_er_join_source_map.json").read_text()
)
network_queue = json.loads((WORK / "betse_normal_network_join_workqueue.json").read_text())
proposal = Path("/mnt/workspaces/Cells/er-initial-state-design-20261030-01/proposal.json")
assert sha(proposal) == "6a81bc966e8a05e13868040bc7dcbede78ea65d472e245e732168bc371cc1ae5"
design = json.loads(proposal.read_text())
old_native = ast.parse((ROOT / "validation/betse/betse_normal_er_join_native.py").read_text())
new_native = ast.parse((ROOT / "validation/betse/betse_prepared_er_join_native.py").read_text())
old_evaluate = next(
    n for n in old_native.body if isinstance(n, ast.FunctionDef) and n.name == "evaluate"
)
new_evaluate = copy.deepcopy(
    next(n for n in new_native.body if isinstance(n, ast.FunctionDef) and n.name == "_whole_join")
)
new_evaluate.name = "evaluate"
changed_cache = changed_kind = 0
for node in ast.walk(new_evaluate):
    if (
        isinstance(node, ast.Assign)
        and ast.unparse(node.targets[0]) == "er_state_cache"
        and ast.unparse(node.value)
        == "restore_supplied_fields(inputs['prepared_er_input']['fields'])"
    ):
        node.value = ast.Constant(value=None)
        changed_cache += 1
    if (
        isinstance(node, ast.keyword)
        and node.arg == "kind"
        and isinstance(node.value, ast.Constant)
        and node.value.value == "cells.native_prepared_er_join_capture@1"
    ):
        node.value = ast.Constant(value="cells.native_normal_er_join_capture@1")
        changed_kind += 1
assert changed_cache == changed_kind == 1
assert ast.dump(new_evaluate, include_attributes=False) == ast.dump(
    old_evaluate, include_attributes=False
)
evidence = {
    "source_design": {"path": str(proposal), "sha256": sha(proposal)},
    "literal_ER02_inputs": design["binding_evidence"]["ER02_inputs"],
    "literal_ER02_failure": design["binding_evidence"]["ER02_failure"],
    "literal_ER02_review": design["binding_evidence"]["ER02_failure_review"],
    "worker_source_audit": design["binding_evidence"]["worker_source_audit"],
    "network02_inputs": {
        "path": "/mnt/workspaces/Cells/betse-normal-network-prepared-20261030-02/inputs.json",
        "sha256": "eaa1a1376c228a50c46e2c8aca2c0e8c826b16e5db808b8cd32d55cf9699d97e",
    },
}
for row in evidence.values():
    assert sha(row["path"]) == row["sha256"], row["path"]
budgets = dict(base["acceptance"]["inherited_budget_source_sha256"])
budgets["validation/betse/betse_normal_er_join_protocol.json"] = sha(
    ROOT / "validation/betse/betse_normal_er_join_protocol.json"
)
budgets["tests/unit/test_betse_normal_er_join.py"] = sha(
    ROOT / "tests/unit/test_betse_normal_er_join.py"
)
protocol = dict(
    kind="cells.prepared_owned_ER_static_contract@1",
    status="static_unqualified_no_numerical_execution",
    constructor_mode="prepared_owned_ER_before_outer_call_channels_primed_v1",
    engine_law=base["law_id"],
    purpose="Declare complete new positive initial inventories/cache phase for the unchanged conditional ER update; preserve literal initialization and failures",
    native_source=base["native_source"],
    source_map="validation/betse/betse_prepared_er_join_source_map.json",
    binding_evidence=evidence,
    exact_preparation_contract=design["exact_preparation_contract"],
    scope=dict(
        neutral_outer_declarations=13,
        neutral_Cl_declarations=12,
        stationary_P_allocation_controls=1,
        ER_only_thermal_sign_probes=2,
        matched_horizon_diagnostics=2,
        initial_counterion_choices=["Cl", "P"],
        initial_Ca_mM=0.2,
        chemistry="Maintained native pools and source kinetics; no finite fuel or new buffer",
        native_constructor_parity=False,
        native_restart_parity=False,
        full_Simulator_or_mesh_initialization=False,
        biological_cases=0,
    ),
    planned=dict(
        checks=23,
        native_captures=21,
        neutral_original_resolution_histories=13,
        additional_diagnostic_histories=6,
        ER_only_single_updates=2,
        actual_pre_ER_points=83,
        fresh_conditional_step_reference_forms=166,
        fresh_preparation_reference_forms=42,
        total_fresh_reference_forms=208,
        carried_reference_forms=0,
        preparation_refusals=6,
        repeated_original_resolution_diagnostic_histories=2,
        positive_trajectory_qualifications=0,
    ),
    source_policy=base["source_policy"],
    source_order=[
        "Attach the fully supplied prepared ER state before the first outer call",
        "Ordinary resets, NaK, membrane/GJ/intra and membrane-buffer refresh",
        "Plasma CaATP followed by original ER channels/SERCA/moving-ion flux/get_v",
        "Network clear, late channels and explicitly empty network chemistry",
        "Deferred ordinary commit/clipping, current and voltage",
        "Carry all owned ER fields, original caches and clocks into the next call",
    ],
    input_versus_execution=dict(
        supplied="Complete prepared all-ion ER packet, IP3 owner readouts and ordinary/channel forcing outputs",
        executed="Original ER owner lookup/channels/SERCA/electroflux/get_v and unchanged outer stepping",
        excluded="IP3-production or network dynamics, native ER initialization/restart or full Simulator/mesh preparation",
    ),
    preparation=dict(
        raw_conditions_archived_before_constructor_and_before_preparer=True,
        full_source_parent_and_prepared_packet_archived=True,
        source_constructor_unchanged=True,
        inventory_boundary="New declared initial inventory; neutral counterion allocation is not a transfer from the failed state",
        counterion="Decimal90 solve from exact binary64 parents, round once; independent Decimal90/140 reconstruction from raw parents",
        voltage="Literal get_v operand order on actual stored full ion rows; retain target residual rather than force ideal voltage",
        caches="Prime original channels once without advancing time; first update recomputes from actual pre-ER cytosol",
        association="Complete binding/source-parent/recipe/context/packet digests; reconstruction rejects resealed changes; attach uses real joined._state factory",
        immutability="Own frozen complete arrays and mappings, never writable aliases",
        nonzero_sign_scope="ER only; signed Cl redistribution seals total inventory and opposite compartment charge, never silently attached to unchanged membrane/outer voltage",
    ),
    acceptance=dict(
        primary=base["acceptance"]["primary"],
        step_budgets_unchanged=base["acceptance"],
        inherited_budget_source_sha256=budgets,
        initial_reference="Independent stdlib Decimal90/140 from exact binary64 raw inputs before production preparation; no production/native/NumPy/JAX imports",
        initial_exact_fields=[
            "cc_er",
            "cytosol_mM",
            "er_vol",
            "er_sa",
            "cm_er",
            "zer",
            "Dm_er_base",
            "requested_voltage_V",
            "target_charge_density_C_m3",
        ],
        initial_roundoff=dict(
            unit_roundoff="2^-53",
            gamma="g(n)=n*u/(1-n*u)",
            charge="g(3*ion_count+4)*sum(abs(z*F*c_ER))+1e-30 C/m3",
            target_charge="charge bound + abs(z_counterion*F)*ulp(stored_counterion)/2",
            voltage="abs(er_vol/er_sa/cm)*charge_bound*(1+g(6)) + g(6)*abs(exact_all_ion_V) +1e-30 V",
            target_voltage="voltage bound + abs(er_vol/er_sa/cm)*counterion_charge_store_bound",
            caches="g(128)*(abs(max_er)+abs(base)+abs(channel))+1e-30 m2/s; planned Hill exponents2",
            amount="g(8)*(abs(cytosol_amount)+abs(ER_amount))+1e-40 mol",
            paired_Cl_redistribution="g(16)*sum(abs(two prepared amounts + neutral baseline amounts))+1e-40 mol",
            boundary="Preparation only; never a propagated allowance or new ER step tolerance",
        ),
        self_resolution_fraction=0.1,
        no_outcome_tuning=True,
        full_error_budget_units_arrays=True,
    ),
    refinement=dict(
        subdivisions=[1, 2, 4],
        dt_s=[0.002, 0.001, 0.0005],
        horizon_s=0.006,
        output_times_s=[0.002, 0.004, 0.006],
        forcing="Repeat each original packet for its fixed 2ms interval; do not move control/temperature changes with refined call index",
        algorithm="Unchanged sequential source stepping, not RK4; no claimed fourth-order slope",
        report="Absolute per-field differences and complete states at matched boundaries; no new physical pass threshold",
        physical_accuracy_pass_threshold=None,
        independent_carried_reference_forms=0,
    ),
    failure_retention=dict(
        ER01_constructor_failures="Immutable failed evidence",
        ER02_observed_source_refusals=design["negative_controls"][
            "retained_observed_raw_native_failures"
        ],
        original_ER02_unrun_checks=12,
        original_unrun_raw_SERCA=design["negative_controls"]["existing_unrun_raw_SERCA_cases"],
        old_IDs_reclassified=False,
        new_refusals="Cells preparation contract only, no native refusal claim",
        on_failure="Archive raw outputs/partial state and stop; no automatic dt/parameter/counterion search",
    ),
    resources=dict(
        cpu=None,
        cpu_coordination="Later explicit requested round only",
        gpu=False,
        max_command_seconds=480,
        max_process_tree_rss_bytes=2**30,
        min_available_host_memory_bytes=8 * 2**30,
        threads=1,
    ),
    limitations=design["scope_limits"]
    + [
        "No numerical preparation, reference, native, test collection or update executed in this package",
        "Native source-derived geometry alternative is deferred; no prior geometry passes count as ER passes",
        "No simultaneous new network-feedback/ER integration claim",
    ],
    numerical_runs=0,
    scientific_imports=0,
    pytest_collection_runs=0,
    automatic_launch=False,
    automatic_followup=False,
    automatic_polling=False,
)
mapping = dict(
    kind="cells.prepared_owned_ER_source_map@1",
    source_revision=source_map["source_revision"],
    literal_source_methods_reused_unchanged=source_map["methods"],
    outer_helpers_reused_unchanged=source_map["source_seams"],
    original_source_map_sha256=sha(ROOT / "validation/betse/betse_normal_er_join_source_map.json"),
    source_to_state_mapping=design["source_to_state_mapping"],
    new_semantics=[
        "Initial counterion inventory solve and explicitly primed caches",
        "Target and actual stored charge/voltage remain separate",
        "Exact-binary-input independent preparation reconstruction",
        "Full first native incoming_state supplied, then normal carry",
    ],
    native_capture_inverse_AST_proof=dict(
        unchanged_after_only_function_name_capture_kind_and_first_state_input_reversal=True,
        original_evaluate_AST_sha256=hashlib.sha256(
            ast.dump(old_evaluate, include_attributes=False).encode()
        ).hexdigest(),
        numeric_steps_changed=False,
        original_helper_source_unchanged=True,
    ),
    factory_ownership=dict(
        prepare="betse_prepared_er_join.prepare",
        validate="Rebuild packet from exact source parent and recipe; reject resealed inconsistencies",
        attach="betse_normal_er_join._state with all original outer fields and clocks",
        ER_only="Same full supplied packet; no outer membrane/voltage association claim",
    ),
    no_scientific_AST_executed=True,
    numerical_runs=0,
)
write(ROOT / "validation/betse/betse_prepared_er_join_protocol.json", protocol)
write(ROOT / "validation/betse/betse_prepared_er_join_source_map.json", mapping)
owned = [
    "src/cells/processes/betse_prepared_er_join.py",
    "tests/unit/test_betse_prepared_er_join.py",
] + [
    "validation/betse/betse_prepared_er_join_" + name
    for name in ["fixtures.py", "native.py", "reference.py", "protocol.json", "source_map.json"]
]
protected = network_queue["protected_sha256"] | network_queue["owned_sha256"]
for rel, digest in protected.items():
    assert sha(ROOT / rel) == digest, rel
queue = dict(
    kind="cells.prepared_owned_ER_static_workqueue@1",
    status="implementation_prepared_static_audits_pending",
    owned=owned,
    owned_sha256={rel: sha(ROOT / rel) for rel in owned},
    protected_sha256=protected,
    runner="agent-work/cells-worker-01/workfiles/betse_prepared_er_join_checks.py",
    notes="agent-work/cells-worker-01/workfiles/BETSE_PREPARED_ER_JOIN_NOTES.md",
    workfiles=[
        "agent-work/cells-worker-01/workfiles/betse_prepared_er_join_checks.py",
        "agent-work/cells-worker-01/workfiles/BETSE_PREPARED_ER_JOIN_NOTES.md",
        "agent-work/cells-worker-01/workfiles/prepare_prepared_er_native.py",
        "agent-work/cells-worker-01/workfiles/prepare_prepared_er_package.py",
        "agent-work/cells-worker-01/workfiles/betse_prepared_er_join_static_audit.py",
    ],
    binding_evidence=evidence,
    coordinated_shared_edit_paths=network_queue["coordinated_shared_edit_paths"],
    authorized_physical_helper_refactor=network_queue["authorized_physical_helper_refactor"],
    coordinated_independent_reference_edits=network_queue[
        "coordinated_independent_reference_edits"
    ],
    reference_closure={},
    static_checks={},
    numerical_runs=0,
    scientific_imports=0,
    pytest_collection_runs=0,
    active_numerical_job=None,
    automatic_launch=False,
    automatic_followup=False,
    automatic_polling=False,
)
write(WORK / "betse_prepared_er_join_workqueue.json", queue)
print(
    json.dumps(
        dict(
            status=queue["status"],
            owned=len(owned),
            protected=len(protected),
            source_design_sha256=sha(proposal),
            checks=23,
            native_captures=21,
            fresh_preparation_forms=42,
            fresh_step_forms=166,
            numerical_runs=0,
        )
    )
)
