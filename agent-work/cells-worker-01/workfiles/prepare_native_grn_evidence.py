# ruff: noqa: E501 -- exact review metadata and emitted runner templates.
"""Build a genuine GRN protocol/workqueue/runner without any scientific import."""

import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path("/home/robert/Cells")
WORK = "agent-work/cells-worker-01/workfiles/"
OLD, NEW = "betse_normal_molecule", "betse_normal_grn"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(relative, value):
    with (ROOT / relative).open("x") as stream:
        json.dump(value, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")


mol = json.loads((ROOT / (WORK + OLD + "_join_workqueue.json")).read_text())
trans = json.loads((ROOT / (WORK + "betse_normal_transporter_join_workqueue.json")).read_text())
protocol = json.loads((ROOT / ("validation/betse/" + OLD + "_join_protocol.json")).read_text())
protocol.pop("adapter_field_repair_02", None)
for relative in ("betse/science/chemistry/gene.py", "betse/science/chemistry/netplot.py"):
    protocol["native_source"]["source_sha256"][relative] = sha(
        Path(protocol["native_source"]["checkout"]) / relative
    )
review = Path(
    "/mnt/workspaces/Cells/betse-normal-molecule-tests-20261030-02/root-review-01/REVIEW.json"
)
assert sha(review) == "747b98ca85f05ce444999cd752c575d83bd54da4e6844fcfa1deb3f71f6217b5"
evidence = dict(mol["binding_evidence"])
evidence.update(
    accepted_molecule02_inputs=dict(
        path=mol["prepared_inputs"], sha256=mol["prepared_inputs_sha256"]
    ),
    accepted_molecule02_review=dict(path=str(review), sha256=sha(review)),
    molecule02_static_receipt=dict(
        path=str(ROOT / mol["static_receipt"]), sha256=mol["static_receipt_sha256"]
    ),
)
protocol.update(
    kind="cells.genuine_normal_grn_owner_dispatch_static_contract@1",
    law_id="betse_normal_native_grn_owner_dispatch_v1_5_0@1",
    purpose="Real MasterOfGenes/Core cold configuration and original guarded normal GRN dispatch with configured GAD regulation, source-default hydration and complete carried public caches",
    status="static_unqualified_no_grn_numerics",
    source_map="validation/betse/" + NEW + "_join_source_map.json",
    binding_evidence=evidence,
)
protocol["planned"] = dict(
    checks=19,
    positive_three_call_histories=10,
    new_grn_histories=7,
    component_control_histories=3,
    raw_partial_failures=4,
    raw_cold_failures=2,
    raw_runtime_failures=2,
    dependency_controls=5,
    native_captures=14,
    positive_native_outer_calls=30,
    actual_pre_network_points=30,
    independent_cold_configuration_points=10,
    fresh_warm_Decimal_forms=60,
    fresh_cold_Decimal_forms=20,
    fresh_Decimal_reference_forms=80,
    carried_reference_forms=0,
    positive_completed_mover_calls_per_implementation=60,
    biological_cases=0,
)
protocol["scope"] = dict(
    owner="Actual MasterOfGenes stores an actual source-initialized MasterOfNetworks; molecules owner disabled and grn_enabled=True are actual source-context flags",
    initialization="Original sim initialization guard884-900 cold branch -> MasterOfGenes constructor/read_gene_config -> Core ctor/read_substances/tissue_init, actual default/source builders, neutral zero-Q bal_charge and default set_net_opts",
    dispatch="Original normal sim guarded GRN block1306-1319 executes clear, optional configured ion modulators and core; configured GRN transporters/channels absent so original flags are False",
    chemistry="Genuine configured neutral X/Y all-cell products with ordinary cross-gene/ion Hill growth and decay regulation and one X-to-Y reaction",
    cold_vs_hot="Cold source readers execute once at constructor boundary (native before first ordinary forcing). Subsequent calls restore complete cached public owner/core/molecule/reaction/modulator state and live aliases without rerunning cold readers.",
    excluded=[
        "Standalone run_core_sim (different timing/publication/order)",
        "GRN reinitialize warm configuration changes",
        "Charged gene compensation, mitochondria/ECM or generated mesh initialization",
        "Network channels/transporters, optimizers, asymmetry/functions/profiles, plotting, events/cuts/flow/motor/active molecule pumps",
        "YAML/file-loader/full Simulator lifecycle",
        "Finite/shared-fuel GRN coupling, physical single-bath conservation, heat/energy or independently carried trajectory accuracy",
    ],
)
protocol["input_versus_execution"] = dict(
    supplied="Frozen native GRN configuration dictionary plus neutral constrained projection, actual ion/boundary/geometry/forcing context",
    executed="Literal original MasterOfGenes read/configuration and normal GRN guarded initialization/dispatch; actual Core/Molecule/readers/writers/mover",
    observations="Before-constructor inputs, complete cold owner/core/molecule fields and simulator writes; actual post-clear/pre-GRN equations; full cache, stages and raw partial failures",
    hot_adapter="Complete public fields are persisted; only live alias objects, separately serialized object containers and observation-only fields are omitted and reconstructed explicitly",
)
protocol["owned_state"]["grn_owner"] = (
    "Every public wrapper flag, Core scalar/array/expression/default/plot metadata, complete Molecule fields, reactions/modulators and simulator network fields/boundary state; full state participates in parent identity"
)
protocol["owned_state"]["default_hydration"] = (
    "Source constructors/read_substances/tissue_init set defaults including ignore_ECM_pump=True and omitted Dgj=1e-16. Static42-attribute closure and full-public-field hot restore prevent a new manual adapter omission."
)
protocol["owned_state"]["forcing_order"] = (
    "Cold lifecycle precedes ordinary forcing. Native cold simulator fields are captured at initialization, then explicitly supplied incoming charge/current packet is applied; hot environment/publication fields persist."
)
protocol["acceptance"]["primary"] = (
    "Exact complete native cold state, public cache fields, real owner classes/identity/flags, guarded dispatch stages, source equations, ordinary/GRN/mover frames, current/voltage and partial exceptions"
)
protocol["acceptance"]["cold_initialization"] = (
    "Independent Decimal90/140 from inputs archived before constructors; exact binary64 configuration/default/index/zero-field assignments and independently constructed reaction matrix. Full typed errors/budgets retained; no floating preparation solve."
)
protocol["acceptance"]["warm_regulated_growth"] = (
    "Fresh Decimal90/140 ordinary Hill factors applied to configured GAD production/regulated decay using actual pre-GRN cells; unchanged inherited growth/rate/material/current budgets"
)
protocol["acceptance"]["dependency_admission"] = (
    "Every dependency first requires genuine valid cold admission, then exact terminal refusal and complete witness set"
)
protocol["component_controls"] = dict(
    new_caller_controls=["no_regulators", "no_modulators", "no_growth"],
    credit="Old grn_owner label cases earn no real GRN dispatch/lifecycle credit; old passes are not rerun or counted here",
    secondary="Unchanged separate ion-modulation component comparison at each actual pre-GRN point",
)
protocol["failures"] = dict(
    raw=[
        "cold_first_missing_Dm",
        "cold_second_missing_Dm",
        "runtime_first_negative",
        "runtime_second_negative",
    ],
    cold="Actual KeyError after source read_substances and first/second tissue assignment; partial owner/core/molecule fields and phase flags preserved before any ordinary step",
    runtime="Actual first/second molecule BetseSimUnstableException through real owner dispatch; all completed prior species and source caches/current/nonce writes retained",
    old_evidence="All accepted, failed and pending predecessor snapshots remain unchanged",
    positive_credit=False,
    retry="No worker numerical launch/retry, polling or automatic regression",
)
protocol["source_order"] = [
    "Original cold p.grn_enabled initialization guard constructs MasterOfGenes and genuine configured Core; molecules owner disabled",
    "Cold scalar/zero/default state and neutral charge cache writes captured separately; then ordinary forcing applied",
    "Carried/scheduled controls feed unchanged NaK/ordinary ions/GJ/CaATP prefix",
    "Original normal GRN p.grn_enabled guard clears caches/current, tests actual wrapper flags, runs ion-driven modulators then Core",
    "Actual all-molecule intra refresh, all regulated GAD/reaction rates/stack/matrix before commits, sequential real molecule transport and publication",
    "Source-effective M*vol_env ledger and physical single-bath defect remain separate, including directed-GJ term",
    "Ordinary deferred commit, current/voltage and complete owner/cache/control carry; no cold-reader rerun on subsequent calls",
]
write("validation/betse/" + NEW + "_join_protocol.json", protocol)
spec = importlib.util.spec_from_file_location(
    "grn_AST_audit", ROOT / (WORK + NEW + "_join_ast_audit.py")
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
proof = module.audit()
write(
    "validation/betse/" + NEW + "_join_source_map.json",
    dict(
        kind="cells.genuine_normal_grn_source_map@1",
        law_id=protocol["law_id"],
        source_revision=protocol["native_source"]["revision"],
        source_sha256=protocol["native_source"]["source_sha256"],
        scope=protocol["scope"],
        **proof,
    ),
)
protected = mol["protected_sha256"] | mol["owned_sha256"] | trans["owned_sha256"]
assert len(protected) == 235
queue = {
    key: value
    for key, value in mol.items()
    if key
    in {
        "authorized_physical_helper_refactor",
        "coordinated_shared_edit_paths",
        "coordinated_unrelated_physics_edits",
        "automatic_launch",
        "automatic_polling",
        "automatic_followup",
    }
}
queue.update(
    kind="cells.genuine_normal_grn_workqueue@1",
    status="implementation_ready_for_final_static_audits",
    notes=WORK + "BETSE_NORMAL_GRN_JOIN_NOTES.md",
    runner=WORK + NEW + "_join_checks.py",
    binding_evidence=evidence,
    owned=[name.replace(OLD, NEW) for name in mol["owned"]],
    protected_sha256=protected,
    scientific_imports=0,
    numerical_runs=0,
    pytest_collection_runs=0,
    active_numerical_job=None,
    pending_transporter_dependency=False,
    protected_but_not_imported_side_package_paths=trans["owned"],
    workfiles=[
        WORK + name
        for name in (
            NEW + "_join_checks.py",
            NEW + "_join_ast_audit.py",
            NEW + "_join_static_audit.py",
            "prepare_native_grn_package.py",
            "prepare_native_grn_bridges.py",
            "prepare_native_grn_reference.py",
            "prepare_native_grn_checks.py",
            "prepare_native_grn_evidence.py",
            "grn_owner_adapter_template.txt",
            "BETSE_NORMAL_GRN_JOIN_NOTES.md",
            "record_static_freeze_receipt.py",
        )
    ],
)
queue["owned_sha256"] = {name: sha(ROOT / name) for name in queue["owned"]}
write(WORK + NEW + "_join_workqueue.json", queue)
runner = (
    (ROOT / (WORK + OLD + "_join_checks.py"))
    .read_text()
    .replace(OLD, NEW)
    .replace("normal-molecule-join", "normal-grn-join")
    .replace("CELLS_MOLECULE_JOIN_CPU", "CELLS_GRN_JOIN_CPU")
)
runner = (
    runner.replace(
        "cells.native_molecule_chemistry_transport_prepared@1",
        "cells.genuine_normal_grn_owner_prepared@1",
    )
    .replace(
        "test_native_chemical_transport_and_conditional_reference",
        "test_genuine_grn_owner_and_conditional_reference",
    )
    .replace("test_native_molecule_partial_failure", "test_genuine_grn_partial_failure")
    .replace("test_complete_molecule_dependencies", "test_complete_grn_dependencies")
)
start = runner.index("        core = {")
end = runner.index('        for case in constants["CASES"]:', start)
runner = (
    runner[:start]
    + """        core={"regulated","GJ_zero","source_defaults","time_dilation"}
"""
    + runner[end:]
)
runner = (
    runner.replace('executed_chemistry=case != "transport_only"', "executed_chemistry=True")
    .replace('"new_coupled_case"', '"new_grn_case"')
    .replace("== 21\n", "== 19\n")
    .replace("== 17\n", "== 14\n")
    .replace("native_source_copies=38", "native_source_copies=42")
)
runner = runner.replace(
    'and row["conditional_pre_network_checks"] == 3',
    'and row["conditional_pre_network_checks"] == 3\n            and row["genuine_grn_owner_dispatch"] is True\n            and row["cold_initialization_checks"] == 1\n            and row["cold_reference_forms"] == 2',
)
start = runner.index("    for name, path in sorted(raw.items()):")
end = runner.index("    return reports", start)
runner = (
    runner[:start]
    + """    for name,path in sorted(raw.items()):
        row=json.loads(path.read_text())
        cold="cold_" in name
        expected_type="KeyError" if cold else "BetseSimUnstableException"
        expected_completed=0 if cold or "first" in name else 1
        if not(row["source_refused"] is True and row["source_type"]==expected_type and row["cold_initialization_failure"]==cold and row["partial_owner_fields_preserved"] is True and row["completed_transports"]==expected_completed and row["positive_grn_credit"] is False and row["physical_conservation_credit"] is False):
            raise ValueError("Invalid genuine GRN partial-failure retention")
        reports.append(dict(path=name,**row))
    if group=="dependencies":
        names=[name.split("[",1)[1][:-1] for name in inputs["groups"][group]]
        found={path.name:path for path in base.glob("dependency-*.json")}
        if set(found)!={"dependency-"+name+".json" for name in names}:
            raise ValueError("Exact GRN dependency witness set differs")
        for name in names:
            row=json.loads(found["dependency-"+name+".json"].read_text())
            if not(row["baseline_admitted"] is True and row["genuine_grn_owner"] is True and row["actual_leaf_type"]=="ValueError" and row["actual_message"]==row["expected_message"] and row["intended_failure_reached"] is True and row["source_failure_credit"] is False):
                raise ValueError("Invalid GRN admission/refusal witness")
            reports.append(dict(path="dependency-"+name+".json",**row))
"""
    + runner[end:]
)
needle = "        reports.append(dict(path=name, **row))\n"
assert runner.count(needle) == 1
runner = runner.replace(
    needle,
    """        case=path.parent.name.removeprefix("isolated-")
        cold_folder=base/("preparation-"+case)/"cold-initialization"
        comparison=json.loads((cold_folder/"comparison.json").read_text())
        if not(comparison["actual_cold_configuration_only"] is True and comparison["physical_conservation_credit"] is False and comparison["fields"] and all(0<=value["normalized_max_error"]<=1 for value in comparison["fields"].values())):
            raise ValueError("Invalid independent cold GRN comparison")
        for level in (1,2):
            answer=json.loads((cold_folder/("reference-"+str(level)+".json")).read_text())
            if not(answer["production_imports_denied"] and not answer["loaded_production_modules"] and answer["cold_initialization"] is True and answer["decimal_precision"]==(90 if level==1 else 140) and answer["carried_reference_forms"]==0):
                raise ValueError("Missing independent cold GRN form")
"""
    + needle,
    1,
)
runner = runner.replace(
    "genuine_molecule_mover=True,",
    "genuine_molecule_mover=True,\n                genuine_grn_owner_lifecycle_and_normal_dispatch=True,\n                standalone_sim_grn=False,",
)
with (ROOT / (WORK + NEW + "_join_checks.py")).open("x") as stream:
    stream.write(runner)
print(
    json.dumps(
        dict(
            owned=10,
            protected=235,
            native_pins=len(protocol["native_source"]["source_sha256"]),
            scientific_bodies=proof["literal_scientific_body_count"],
            planned=protocol["planned"],
            scientific_imports=0,
            numerical_runs=0,
        )
    )
)
