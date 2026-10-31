# ruff: noqa: E501 -- explicit contract/provenance strings.
"""Write static catalog contracts and pins, without importing fixtures or science."""

import ast
import copy
import hashlib
import json
from pathlib import Path

ROOT = Path("/home/robert/Cells")
WORK = ROOT / "agent-work/cells-worker-01/workfiles"
PREFIX = "betse_normal_ecm_catalog_join"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    with Path(path).open("x") as stream:
        json.dump(value, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")


calcium = json.loads(
    (ROOT / "validation/betse/betse_normal_ecm_calcium_join_protocol.json").read_text()
)
prior_queue = json.loads((WORK / "betse_normal_ecm_calcium_join_workqueue.json").read_text())
catalog = json.loads(
    (ROOT / "validation/betse/betse_normal_catalog_join_protocol.json").read_text()
)
evidence = copy.deepcopy(calcium["binding_evidence"])


def bind(name, path, expected=None):
    digest = sha(path)
    if expected is not None:
        assert digest == expected, name
    evidence[name] = dict(path=str(path), sha256=digest)


bind(
    "frozen_calcium01_inputs",
    "/mnt/workspaces/Cells/betse-normal-ecm-calcium-join-prepared-20261031-01/inputs.json",
    "2e2ed97ee190d9495e3029fbe389a40039786fc9070f28a52f3b4e8ce3a226d8",
)
bind(
    "calcium01_static_receipt",
    WORK / "betse_normal_ecm_calcium_join_static_receipt_01.json",
    "008f94c21a1908ff790104b1533231486b0dd70edff86cd514ccf857e718e34e",
)
bind(
    "catalog06_prepared_not_launched",
    "/mnt/workspaces/Cells/betse-normal-catalog-prepared-20261030-06/inputs.json",
    "faf91ca4f1f21d816cd37c71cb1fb7b5bfd3643210e48b34db7927fb0122bc69",
)
bind(
    "whole_modern_reachability",
    WORK / f"{PREFIX}_reachability_01.json",
    "57d3520b0e041219bf92a78ac10e2f0e4aa99c4219cab6c1d39c8f926c54f192",
)
bind("catalog_composition_AST", WORK / f"{PREFIX}_AST_witness_01.json")
bind("explicit_dependency_refresh", WORK / f"{PREFIX}_dependency_witness_01.json")
bind(
    "Chief_finalized_field_calcium_repairs",
    "/mnt/workspaces/Cells/betse-normal-ecm-join-repair-preparation-20261031-01/result.json",
)
fixture = ast.parse((ROOT / "validation/betse" / f"{PREFIX}_fixtures.py").read_text())
constants = {
    target.id: ast.literal_eval(node.value)
    for node in fixture.body
    if isinstance(node, ast.Assign)
    for target in node.targets
    if isinstance(target, ast.Name)
    and target.id
    in ("CLASSES", "CASES", "CONTEXT_CASES", "COMPONENT_CONTROLS", "RAW_CASES", "DEPENDENCIES")
}
assert [
    len(constants[k])
    for k in (
        "CLASSES",
        "CASES",
        "CONTEXT_CASES",
        "COMPONENT_CONTROLS",
        "RAW_CASES",
        "DEPENDENCIES",
    )
] == [55, 71, 16, 5, 7, 16]
planned = dict(
    checks=94,
    positive_histories=71,
    one_call_class_prefixes=55,
    three_call_context_histories=16,
    new_ECM_modern_histories=66,
    component_control_histories=5,
    raw_partial_limits=7,
    dependency_controls=16,
    native_captures=78,
    independent_cold_points=71,
    actual_bootstrap_field_points=71,
    actual_pre_material_points=103,
    actual_pre_calcium_points=103,
    actual_pre_channel_points=103,
    actual_post_channel_pre_GRN_points=103,
    actual_end_field_points=103,
    fresh_cold_Decimal_forms=142,
    fresh_bootstrap_field_Decimal_forms=142,
    fresh_material_Decimal_forms=206,
    fresh_calcium_Decimal_forms=206,
    fresh_channel_Decimal_forms=206,
    fresh_network_Decimal_forms=206,
    fresh_end_field_Decimal_forms=206,
    fresh_Decimal_reference_forms=1314,
    carried_reference_forms=0,
    reachable_modern_classes=55,
    reachable_factory_families=7,
    Ca_routing_modern_classes=23,
    positive_native_Ca_handler_calls_per_implementation=103,
    positive_active_CaATP_helper_calls_per_implementation=100,
    positive_modern_population_updates_per_implementation=178,
    completed_positive_mover_invocations_per_implementation=206,
    source_clock_N=3,
    enabled_ER_calls=0,
    biological_cases=0,
)
protocol = copy.deepcopy(calcium)
protocol.update(
    kind="cells.normal_ecm_catalog_CaATP_field_static_contract@1",
    law_id="betse_normal_ecm_catalog_CaATP_field_join_v1_5_0@1",
    status="static_unqualified_no_numerics",
    purpose="Separately owned genuine modern ECM GRN channel reader/factory/cache/dispatch with reachable CaATP and evolving complete fields; conditional source fidelity only",
    source_map="validation/betse/" + PREFIX + "_source_map.json",
    planned=planned,
    binding_evidence=evidence,
    catalog_budgets=catalog["catalog_budgets"],
)
protocol["native_source"]["source_sha256"].update(catalog["native_source"]["source_sha256"])
protocol["scope"].update(
    source_order="Cold actual read_gene_config/read_channels initializes gates from prepared Vm; bootstrap update_V; actual normal N3 source-clock prefix: moving ions; CaATP; explicit late flux; GRN clear; channels; modulators; chemistry/molecular transport; deferred ordinary commit; full current/environment/voltage; NaN-only check_v",
    owner="Genuine X/Y MasterOfGenes/Core; source sets channels flag only after real reader. New distinct wire8 retains full Channel metadata, every private gate/core field, immutable initialized conditions and external call counters. Restore constructs actual owned classes and dynamic aliases, with no constructor rerun at current Vm",
    channels="All55 reachable modern classes/7 factory families use unchanged qualified catalog primitives.23 route Ca; all gates read Vm/dt/cache, without implicit free-Ca gating. Explicit native Hill activators/inhibitors can sample membrane alias (native cell zone) or mapped E-grid. Max conductivity remains original maxDm-valued branch with no unit conversion",
    targets="all/None derive cells.mem_i; named profile indices are explicit original prepared sim.dyna.tissue_target_inds, preserving source ordering/duplicates. Empty profile native float-index refusal preserved. Expression profiles, legacy cagPotassium, INIT dispatch and broader modifier labels require separate dependencies",
    read_times="Each population runs once on latest shared Vm before routes; each route samples latest bulk concentration gathered by owner and current full E-grid mapped to membranes. Direct update_Co changes bulk/membrane/grid before next route/population. CaATP earlier sampled membrane Ca and deferred its ordinary commit. No invented immediate CaATP-to-bulk feedback",
    limits="55 one-call bounded class prefixes and16 three-call contextual histories. Actual N3 linspace clock retained for all. Cold gate equations have exact native comparison only; independent gate caches are explicit incoming conditions. No full initialization/restart/sim_grn, broad catalog physiology, trajectory or biological credit",
    exclusions=[
        "Full native initialization, hot reinitialize/restart, normal phase lifecycle and sampling/persistence",
        "Mitochondria, ER activation, separate transporters, expression profiles, legacy cagPotassium/INIT channel dispatch and broader regulator labels",
        "Physical global conservation, biological calibration, independent carried trajectories, JAX/GPU qualification",
    ],
)
protocol["declared_cases"].pop("negative_environment_case", None)
protocol["declared_cases"].update(
    branches=[
        "all55 unchanged modern factory classes with real cold constructors and one normal call",
        "mixed/reversed populations, CatLeak zero-Ca route, publication carry",
        "rectangular grid, fast duplicate-last scatter, prepared named duplicate targets and None target branch",
        "live Ca membrane activator and mapped-grid inhibitor after direct Ca route",
        "rho0, maxDm0, None/empty channels, alpha_Ca0 controls",
        "init_activeFalse still initializes/runs in SIM; actual max conductivity branch",
        "nonzero cell polarizability",
    ],
    initial_channel_voltage_recipe="-0.031123+0.003317*j V, predeclared before any numerical evaluation; separate identity from old Cav_G nominal failure",
    channel_maxDm_m2_s=1e-7,
    conductivity_branch_maximum=2e-7,
    selected_from_observed_outcomes=False,
)
protocol["admission"].update(
    original_channel_owner_flag_required=True,
    complete_private_channel_and_constructor_caches=True,
    explicit_named_profile_state=True,
    expression_or_legacy_or_forced_INIT_refused=True,
    bounded_call_prefixes=[1, 3],
)
protocol["acceptance"].update(
    primary="Exact native original source reader/factory/dispatch/gates, ordered route/ECM aliases/current/last-route caches, complete material/CaATP/GRN/field returns and every available raw partial",
    independent="Fresh Decimal100/160 actual cold/bootstrap/pre-material/pre-CaATP/pre-channels/post-channels-pre-GRN/end-field conditionals. Whole scalar channel sequence inserted before ordinary deferred commit in material reference; no independent carried trajectory or cold constructor-law claim",
    channel_gates=catalog["acceptance"]["channel_gates"],
    channel_flux="Unchanged B24 128*eps*(ions+membranes+4+32)*local flux gross +1e-30 mol/(m2*s)",
    channel_current="Unchanged B23 32*eps*(ions+membranes+16)*local gross +1e-30 A/m2",
    channel_additional_observables="Unchanged ECM material concentration3e-13+6e-12*abs(target), diffusion3e-20+6e-12*abs(target), amount3e-14+6e-12*abs(target); native Hill modulation uses3e-14+6e-12*abs(target)",
    carried_initial_condition=catalog["acceptance"]["carried_initial_condition"],
    no_tolerance_tuning=True,
    old_Cav_G_failure_reclassified=False,
    old_material_failure_reclassified=False,
)
protocol["acceptance"]["inherited_budget_source_sha256"].update(
    catalog["acceptance"]["inherited_budget_source_sha256"]
)
protocol["acceptance"]["inherited_budget_source_sha256"][
    "validation/betse/betse_normal_catalog_join_protocol.json"
] = sha(ROOT / "validation/betse/betse_normal_catalog_join_protocol.json")
protocol["accounting"].update(
    channels="Direct modern ion updates never add to ordinary membrane flux arrays. Core current -F*z*flux accumulates then shares molecular publications. Source-effective uniform-site, conservative area-sum and actual true-grid volume amount books remain separate; fast duplicate-last differences are retained",
    material_ledgers="Legacy ledgers remain literal. Direct-channel amounts appear in ordinary accounting residuals rather than being silently erased. Full independent material predicts these source residuals with unchanged budgets",
    zero_weight="CatLeak Ca weight0 still evaluates electroflux/update_Co, refreshes membrane from bulk, consumes voltage nonce and overwrites last-route cache. No skipped-route or boundary-mask substitute",
)
protocol["failures"] = dict(
    raw=list(constants["RAW_CASES"]),
    retention="Complete native cold returns/failures and raw gate/core/Channel caches, all initializer and route hooks, parents, clocks, CaATP phases, GRN/core/simulator buffers, material arrays/frames/ledgers, field trials and tracebacks before assertions. Strict port finite guard is separate from native exception or nonfinite return",
    positive_credit=False,
)
protocol["source_defects_preserved"] += [
    "Modern channels bypass ordinary boundary masking; original targets/P/rho only",
    "Current Vm sampled once per population; route Vm nonce occurs even at permeability0",
    "Fresh bulk gather replaces stored membrane shell for direct route samples; direct update_Co ignores ignoreECM in ECM",
    "Source last-route-only chan_flux/DChan cache and deferred ordinary flux commit",
    "Empty named profile target np.asarray([]) retains float-index refusal",
    "Init-activeFalse cold constructor and normal SIM calls retained; no forced INIT path",
    "Literal Cav_G cold0/0 and prior failed nominal identity remain raw failures",
]
protocol["coordinated_dependency_inputs"]["Chief_owned_capture_test_repairs"] = json.loads(
    (WORK / f"{PREFIX}_dependency_witness_01.json").read_text()
)
write(ROOT / "validation/betse" / f"{PREFIX}_protocol.json", protocol)
proof = json.loads((WORK / f"{PREFIX}_AST_witness_01.json").read_text())
write(
    ROOT / "validation/betse" / f"{PREFIX}_source_map.json",
    dict(
        proof,
        kind="cells.normal_ecm_catalog_source_map@1",
        law_id=protocol["law_id"],
        scope=protocol["scope"],
        native_source_sha256=protocol["native_source"]["source_sha256"],
    ),
)
owned = [
    "src/cells/processes/" + PREFIX + ".py",
    "src/cells/processes/" + PREFIX + "_source.py",
    "tests/unit/test_" + PREFIX + ".py",
] + [
    "validation/betse/" + PREFIX + "_" + suffix
    for suffix in (
        "fixtures.py",
        "native.py",
        "native_network.py",
        "reference.py",
        "protocol.json",
        "source_map.json",
    )
]
# New files get explicit current dependency pins; preserve old packet receipts and failed evidence.
protected = (
    set(prior_queue["protected_sha256"])
    | set(prior_queue["owned"])
    | set(protocol["acceptance"]["inherited_budget_source_sha256"])
)
protected |= {
    "validation/betse/betse_normal_catalog_join_inventory.json",
    "validation/betse/betse_normal_catalog_join_native_helpers.py",
    "validation/betse/betse_normal_catalog_join_scalar.py",
    "validation/betse/betse_normal_catalog_join_equations.py",
}
workfiles = [
    str(p.relative_to(ROOT))
    for p in sorted(WORK.glob("*" + PREFIX + "*"))
    if p.suffix in (".py", ".json")
]
workfiles += [
    str((WORK / n).relative_to(ROOT))
    for n in (
        "BETSE_NORMAL_ECM_CATALOG_JOIN_NOTES.md",
        "betse_mito_grn_reachability_audit.py",
        "betse_normal_grn_join_static_audit.py",
        "betse_normal_network_join_checks_02.py",
    )
]
queue = {
    k: copy.deepcopy(prior_queue[k])
    for k in (
        "authorized_physical_helper_refactor",
        "coordinated_shared_edit_paths",
        "coordinated_unrelated_physics_edits",
        "automatic_launch",
        "automatic_polling",
        "automatic_followup",
    )
}
queue.update(
    kind="cells.normal_ecm_catalog_workqueue@1",
    status="ready_for_static_audits",
    owned=owned,
    owned_sha256={p: sha(ROOT / p) for p in owned},
    protected_sha256={p: sha(ROOT / p) for p in sorted(protected)},
    binding_evidence=evidence,
    planned=planned,
    workfiles=workfiles,
    runner=str((WORK / f"{PREFIX}_checks.py").relative_to(ROOT)),
    notes=str((WORK / "BETSE_NORMAL_ECM_CATALOG_JOIN_NOTES.md").relative_to(ROOT)),
    scientific_imports=0,
    scientific_AST_executions=0,
    pytest_collection_runs=0,
    numerical_runs=0,
    enabled_ER_calls=0,
    active_numerical_job=None,
    explicit_dependency_refresh=protocol["coordinated_dependency_inputs"][
        "Chief_owned_capture_test_repairs"
    ],
)
write(WORK / f"{PREFIX}_workqueue.json", queue)
print(
    json.dumps(
        dict(
            owned=len(owned),
            protected=len(protected),
            binding_evidence=len(evidence),
            native_files=len(protocol["native_source"]["source_sha256"]),
            planned=planned,
        ),
        sort_keys=True,
    )
)
