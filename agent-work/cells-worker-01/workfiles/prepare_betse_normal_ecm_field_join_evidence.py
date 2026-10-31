# ruff: noqa: E501 -- declarative contract strings.
"""Create reviewable static contracts; no fixture/model imports or evaluation."""

import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path("/home/robert/Cells")
WORK = ROOT / "agent-work/cells-worker-01/workfiles"
PREFIX = "betse_normal_ecm_field_join"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    if Path(path).exists():
        assert json.loads(Path(path).read_text()) == value, path
        return
    with Path(path).open("x") as f:
        json.dump(value, f, indent=2, sort_keys=True, allow_nan=False)
        f.write("\n")


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    obj = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(obj)
    return obj


prior = json.loads((WORK / "betse_ecm_grn_workqueue.json").read_text())
inherited = json.loads((ROOT / "validation/betse/betse_ecm_grn_protocol.json").read_text())
material_plan = json.loads(
    (ROOT / "agent-work/cells-specialist/betse_ecm_transport_qualification_plan.json").read_text()
)
field_plan = json.loads(
    (
        ROOT / "agent-work/cells-specialist/betse_environment_field_qualification_plan.json"
    ).read_text()
)
evidence = {}


def bind(name, path, expected=None):
    actual = sha(path)
    if expected is not None:
        assert actual == expected, name
    evidence[name] = dict(path=str(path), sha256=actual)


bind(
    "accepted_ECM02_inputs",
    "/mnt/workspaces/Cells/betse-ecm-grn-prepared-20261031-02/inputs.json",
    "b745902da40be9677582250d768f2c190c2d00880cd8309a945a9c3bbbd58317",
)
bind(
    "accepted_ECM02_review",
    "/mnt/workspaces/Cells/betse-ecm-grn-tests-20261031-02/root-review-01/REVIEW.json",
    "c47105e71db20d6d3312f921583c4cb74b93db8edce3e568e6f1386a939c18fb",
)
bind(
    "accepted_ECM02_static_receipt",
    WORK / "betse_ecm_grn_static_receipt_02.json",
    "855be396818cab9410d9e1ec4724afe2c531ea55ac6f636cc09023d428a2c9db",
)
bind(
    "retained_failed_material_round",
    material_plan["failed_round_receipt"],
    material_plan["failed_round_receipt_sha256"],
)
bind(
    "instantaneous_field_completion",
    field_plan["completion_verification"],
    field_plan["completion_verification_sha256"],
)
for name, file in (
    ("actual_caller_reachability", "betse_normal_ecm_field_join_reachability_01.json"),
    ("literal_source_and_composition", "betse_normal_ecm_field_join_AST_witness_01.json"),
    ("coordinated_diagnostic_inputs", "betse_normal_ecm_field_join_dependency_witness_01.json"),
):
    bind(name, WORK / file)
planned = dict(
    checks=31,
    positive_three_call_histories=16,
    new_field_composition_histories=12,
    component_control_histories=4,
    raw_partial_limits=5,
    dependency_controls=10,
    native_captures=21,
    independent_cold_points=16,
    actual_bootstrap_field_points=16,
    actual_pre_material_points=48,
    actual_pre_network_points=48,
    actual_end_field_points=48,
    fresh_cold_Decimal_forms=32,
    fresh_bootstrap_field_Decimal_forms=32,
    fresh_material_Decimal_forms=96,
    fresh_network_Decimal_forms=96,
    fresh_end_field_Decimal_forms=96,
    fresh_Decimal_reference_forms=352,
    carried_reference_forms=0,
    completed_positive_mover_invocations_per_implementation=96,
    biological_cases=0,
)
protocol = dict(
    kind="cells.normal_ecm_field_join_static_contract@1",
    law_id="betse_normal_ecm_field_material_network_v1_5_0@1",
    status="static_unqualified_no_numerics",
    purpose="Actual normal ECM material and nonempty GRN composed with full original current/environment/voltage bootstrap and suffix; close supplied-old-field seam",
    native_source=inherited["native_source"],
    binding_evidence=evidence,
    planned=planned,
    resources=inherited["resources"],
    source_map="validation/betse/" + PREFIX + "_source_map.json",
    scope=dict(
        source_order="Explicit prepared phase; original run_sim_core1041 bootstrap update_V; normal resets/ordinary ion transport; guarded GRN1306-1319; update_all_concs1357; update_V1360; NaN-only check_v1363",
        initial_preparation="Original geometry/owner/normal/measure declarations plus initializer material and D_free; derive actual Cartesian grid, maps, source operators/inverses, smoothing weights, sigma/ko, radius and diviterm. Full seed/phase/diffusion-mask/dynamic initialization excluded",
        cache="Original configured-temperature sigma/ko initialized from explicitly declared pre-state, held fixed. update_V sigma_cell independently recomputed per call using species mean and F^2/(R*T)*0.1; this differs from cached q*F/(kb*T) sum",
        owner="Original nonempty configured X/Y MasterOfGenes/Core with native GAD/reaction/modulator/ECM transport, real cold readers, full public cache and coefficient carry; charged cold compensation excluded",
        field_state="Complete intracellular current, environment rho/surface/Gaussian/voltage/E/HH/B/current and cell conductivity/voltage/mean/E/normal/dvm outputs retained. Previous reconstructed E_env alone supplies next ordinary and molecular transport. Vm updates after each field, earlier GJ caches stay stale",
        external="Explicit pump and late membrane flux, channel multiplier, fixed-gap control, ionic bath and applied R/L/T/B voltage; fluid/noise/forces/deformation/events disabled or excluded. Original geometry inputs remain explicit preparation",
        exclusions=[
            "Full native initialization/normal solver and sampling/persistence",
            "Charged cold ion compensation, mitochondria, separate transporters/channels and intracellular molecular field branch",
            "Physical global material/charge/energy conservation, biological calibration, independent carried trajectories, JAX/GPU qualification",
        ],
    ),
    admission=dict(
        boundary="Stricter finite current/environment/voltage guards retain available raw trials; native bootstrap has no check_v and normal check_v only tests NaNs in vm",
        no_prepared_operator_or_old_fields=True,
        positive_capacitance=True,
        bounded_calls=3,
    ),
    declared_cases=dict(
        recipe="New manufactured nominally electroneutral P=Na+K-Cl bulk/membrane/grid/boundary declarations; source nonces and finite cancellation remain",
        fixed_dt_s=1e-4,
        fixed_capacitance_F_m2=1.0,
        fixed_formal_gene_charge_scale=1e-4,
        reason="Metre-scale manufactured geometry and bounded explicit transport; fixed before any execution, no observed outcome or tolerance tuning",
        branches=[
            "zero polarizability",
            "nonzero polarizability",
            "negative gene products",
            "rectangular and duplicate maps",
            "ordinary smoothing",
            "runtime/configured T split",
            "time dilation",
            "publication carry",
            "boundary reversal/change",
            "stationary ions",
            "neutral/no-modulator/no-molecular-transport/zero-boundary controls",
        ],
    ),
    acceptance=dict(
        primary="Exact complete original/native material frames/ECM locals/GRN traces/caches/field inputs/HH and all current/environment/voltage arrays; actual post-material cache captured separately from pre-commit dispatch cache",
        independent="Fresh Decimal100/160 at actual archived cold, bootstrap, pre-material, pre-GRN and end-field inputs; no independent trajectory. Full lower/target/actual/error/budget arrays retained",
        inherited_budget_source_sha256=inherited["acceptance"]["inherited_budget_source_sha256"]
        | {
            "validation/betse/betse_ecm_transport_checks.py": sha(
                ROOT / "validation/betse/betse_ecm_transport_checks.py"
            ),
            "validation/betse/betse_environment_field_protocol.json": sha(
                ROOT / "validation/betse/betse_environment_field_protocol.json"
            ),
            "validation/betse/betse_normal_voltage_protocol.json": sha(
                ROOT / "validation/betse/betse_normal_voltage_protocol.json"
            ),
        },
        material="Unchanged legacy ECM typed3e-14 mol/1e-40 V/1e-18 flux/1e-28 GJ-field/3e-20 D/3e-14 alpha-opening/3e-13 concentration floors +6e-12*abs(reference). Ordinary conditional comparisons omit only molecule-induced Vm/vgj nonces after dispatch and total voltage-nonce ledger; independent GRN and exact native validate those separately",
        network=inherited["acceptance"]["material"],
        rates=inherited["acceptance"]["rates"],
        publication=inherited["acceptance"]["publication"],
        amount=inherited["acceptance"]["amount"],
        field_factor="128*eps*(ions+cells+membranes+grid_sites+64)",
        field_gross="Independent sum|F*z*c| and |F*z*flux|; absolute smoothing/area projection; absolute inverse times FD-neighbor gross; positive Gaussian of surface-charge gross; fixed cache/screen and derivative-neighbor sums. Independent voltage arithmetic propagates charge/current/conductivity cancellation. No actual outgoing array enters its allowance",
        field_floors="1e-30 current/charge;3e-14 V;3e-18 magnetic;3e-13 other source fields/HH. Add fixed factor*independent predicted gross; operator3e-13+6e-12*abs(reference), maps exact",
        self_resolution_fraction=0.1,
        no_outcome_tuning=True,
        old_material_budget_unchanged=True,
    ),
    accounting=dict(
        source_effective=inherited["accounting"]["source_effective"],
        alternate=inherited["accounting"]["alternate"],
        source_identity=inherited["accounting"]["source_identity"],
        field="Full source currents, charge reconstruction and nonphysical HH/Gaussian/voltage outputs; no physical continuity, projector or field-energy identity is asserted",
        physical_global_conservation_credit=False,
        energetic_conservation_credit=False,
        retained_failure="Original signed_environment39/40 material panel remains failed, including raw membrane_bulk_difference at fixed old budget. Missing separately retained failed complete reference buffers are not reconstructed",
    ),
    retained_ecm_limit=dict(
        panel=material_plan["original_panel"],
        known_failed_case=material_plan["known_failed_case"],
        new_package_reclassifies_old_panel=False,
        old_frozen_packets_refreshed=False,
    ),
    coordinated_dependency_inputs=json.loads(
        (WORK / "betse_normal_ecm_field_join_dependency_witness_01.json").read_text()
    ),
    failures=dict(
        raw=[
            "first/second network-negative source errors",
            "zero-screen source-completed nonfinite bootstrap fields, stricter adapter guard",
            "post-cache declared current overflow, native nonfinite bootstrap and later possible source error",
            "late boundary-driven voltage overflow in next material call with prior completed states retained",
        ],
        retention="Archive actual inputs before computation and full cold/material/composed returned parents before later work/assertions. Retain current/env/voltage trials, native locals/HH/observations, material frames/locals/ledgers, cache/publication and tracebacks. Unexpected successes retained",
        positive_credit=False,
    ),
    source_defects_preserved=[
        "HH Dirichlet inverse and AA magnetic assignment",
        "source diff edge signs; HH L/R/B/T versus Phi R/L/T/B corners",
        "Gaussian constant0 ECM and repeated-map mean area denominator",
        "fast duplicate-last exchange, deferred shell/cache timing and source nonces",
        "unweighted mean membrane voltage; direct boundary subtraction only at zero polarizability",
        "NaN-only source check_v; stricter adapter finite guards labelled",
    ],
    automatic_launch=False,
    automatic_polling=False,
    automatic_followup=False,
)
write(ROOT / "validation/betse" / f"{PREFIX}_protocol.json", protocol)
proof = module("new_field_AST", WORK / f"{PREFIX}_ast_audit.py").audit()
write(
    ROOT / "validation/betse" / f"{PREFIX}_source_map.json",
    dict(
        proof,
        kind="cells.normal_ecm_field_join_source_map@1",
        law_id=protocol["law_id"],
        native_source_sha256=protocol["native_source"]["source_sha256"],
        scope=protocol["scope"],
    ),
)
owned = ["src/cells/processes/" + PREFIX + ".py", "tests/unit/test_" + PREFIX + ".py"] + [
    "validation/betse/" + PREFIX + "_" + suffix
    for suffix in ("fixtures.py", "native.py", "reference.py", "protocol.json", "source_map.json")
]
workfiles = [
    str(p.relative_to(ROOT))
    for p in sorted(WORK.glob("*" + PREFIX + "*"))
    if p.suffix in (".py", ".json")
] + [
    str((WORK / name).relative_to(ROOT))
    for name in (
        "BETSE_NORMAL_ECM_FIELD_JOIN_NOTES.md",
        "betse_ecm_grn_ast_audit.py",
        "betse_normal_grn_join_ast_audit.py",
        "betse_normal_grn_join_static_audit.py",
        "betse_normal_network_join_checks_02.py",
        "record_static_freeze_receipt.py",
    )
]
queue = {
    k: prior[k]
    for k in (
        "authorized_physical_helper_refactor",
        "coordinated_shared_edit_paths",
        "coordinated_unrelated_physics_edits",
        "automatic_launch",
        "automatic_polling",
        "automatic_followup",
    )
    if k in prior
}
queue.update(
    kind="cells.normal_ecm_field_join_workqueue@1",
    status="ready_for_static_audits",
    owned=owned,
    owned_sha256={p: sha(ROOT / p) for p in owned},
    protected_sha256={},
    workfiles=workfiles,
    binding_evidence=evidence,
    planned=planned,
    runner=str((WORK / f"{PREFIX}_checks.py").relative_to(ROOT)),
    notes=str((WORK / "BETSE_NORMAL_ECM_FIELD_JOIN_NOTES.md").relative_to(ROOT)),
    coordinated_dependency_inputs=protocol["coordinated_dependency_inputs"],
    scientific_imports=0,
    scientific_AST_executions=0,
    pytest_collection_runs=0,
    numerical_runs=0,
    active_numerical_job=None,
)
write(WORK / f"{PREFIX}_workqueue.json", queue)
print(
    json.dumps(
        dict(
            status="static_contracts_prepared",
            owned=len(owned),
            planned=planned,
            binding_evidence=len(evidence),
        )
    )
)
