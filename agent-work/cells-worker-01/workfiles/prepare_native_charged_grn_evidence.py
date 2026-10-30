# ruff: noqa: E501 -- exact metadata and emitted runner templates.
"""Emit charged protocol, ownership queue and static-only freeze driver."""

import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path("/home/robert/Cells")
WORK = "agent-work/cells-worker-01/workfiles/"
OLD, NEW = "betse_normal_grn", "betse_normal_charged_grn"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(relative, value):
    with (ROOT / relative).open("x") as stream:
        json.dump(value, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")


prior = json.loads((ROOT / (WORK + OLD + "_join_workqueue.json")).read_text())
protocol = json.loads((ROOT / ("validation/betse/" + OLD + "_join_protocol.json")).read_text())
protocol.pop("native_key_retention_repair02", None)
evidence = dict(prior["binding_evidence"])
evidence.update(
    neutral_grn02_static_inputs=dict(
        path=prior["prepared_inputs"], sha256=prior["prepared_inputs_sha256"]
    ),
    neutral_grn02_static_receipt=dict(
        path=str(ROOT / prior["static_receipt"]), sha256=prior["static_receipt_sha256"]
    ),
    charged_grn_key_schema01=dict(
        path=str(ROOT / (WORK + "betse_normal_charged_grn_key_schema_witness_01.json")),
        sha256=sha(ROOT / (WORK + "betse_normal_charged_grn_key_schema_witness_01.json")),
    ),
)
protocol.update(
    kind="cells.normal_charged_grn_initialization_static_contract@1",
    law_id="betse_normal_native_charged_grn_initialization_v1_5_0@1",
    purpose="Actual charged GRN cold compensation, complete state/default/owner writes, compensated material handoff and subsequent normal dispatch",
    status="static_unqualified_no_charged_grn_numerics",
    source_map="validation/betse/" + NEW + "_join_source_map.json",
    binding_evidence=evidence,
)
protocol["planned"] = dict(
    checks=22,
    positive_three_call_histories=12,
    new_charged_grn_histories=9,
    component_control_histories=3,
    raw_partial_failures=4,
    raw_cold_failures=4,
    raw_runtime_failures=0,
    dependency_controls=6,
    native_captures=16,
    positive_native_outer_calls=36,
    actual_pre_network_points=36,
    independent_cold_configuration_points=12,
    independent_raw_cold_points=4,
    fresh_warm_Decimal_forms=72,
    fresh_cold_Decimal_forms=24,
    fresh_raw_cold_Decimal_forms=8,
    fresh_Decimal_reference_forms=104,
    carried_reference_forms=0,
    positive_completed_mover_calls_per_implementation=72,
    biological_cases=0,
)
protocol["scope"] = dict(
    owner="Actual MasterOfGenes and source-initialized MasterOfNetworks; actual grn_enabled=True and molecules_enabled=False",
    initialization="Original guarded normal cold initialization884-900; actual read_gene_config/read_substances/tissue_init; Qcells/Qenv sums and cell-before-env bal_charge3914-3987; flag publishes True only after both succeed",
    dispatch="Original guarded normal GRN block1306-1319; clear, optional ion-driven modulators, original Core/Molecule growth/reaction/mover; cold readers never repeated on hot restore",
    counterions="Real separate sixth stationary M(-1) row plus actual K(+1)/Na(+1), get_ion indices, explicit six-value boundary vector. Positive removes cell K and env Na/boundary; negative removes cell/env M and env boundary; ionic membrane caches unchanged",
    input_recipe="Caller adds manufactured M and subtracts its concentration from prior P(-1) arrays to preserve nominal initial ionic charge. This is archived input preparation, not source compensation or a physical initialization solve",
    charged_products="Manufactured equal-monovalent X/Y, formal charge scale1e-6 or2e-6; charge-preserving X-to-Y conversion. z0 control and disabled cold/runtime publication are distinct",
    handoff="Adopt cold compensated bulk/bath/membrane ionic arrays into immutable material parent before ordinary call1, retaining Vm/Vgj, gate cache/clocks and pump proxy",
    source_defect="Negative-cell admission uses M bulk mean, refusal uses M membrane mean. The explicit gap case performs no cell removal but publishes charge and ultimately balanced=True; preserve and diagnose it",
    excluded=[
        "Standalone sim-grn, reinitialize, full Simulator/YAML/mesh lifecycle",
        "Mitochondria/ECM, network channels/transporters, profiles/functions/asymmetry, events/optimization/plotting",
        "Finite/shared fuel, physical global or energetic conservation, physiological calibration, independently carried trajectory accuracy",
    ],
)
protocol["input_versus_execution"] = dict(
    supplied="Pinned native configuration plus actual six-ion buffers/geometry/boundaries/F/R and caller-prepared M/P split; before-constructor inputs archived first",
    executed="Original charged tissue_init and bal_charge, exact float64 arithmetic, original guarded wrapper initialization/dispatch and subsequent chemistry/mover",
    observations="Read-only before/after compensation hooks capture full ionic/boundary/simulator state and source flag; exceptions retain every preceding write",
    hot_adapter="Complete public fields, ionic snapshots, boundary state and compensation observations carried; live aliases rebuilt, original cold readers not rerun",
)
protocol["owned_state"]["grn_owner"] = (
    "Every public owner/Core/Molecule/reaction/modulator field, scalar/array/expression/default, source simulator fields, boundary values, ionic snapshot and complete cold compensation events; full state participates in identity"
)
protocol["owned_state"]["forcing_order"] = (
    "Cold source compensation before normal forcing; adopt compensated material buffers. Capture source cold charge writes, then apply caller-supplied cell/current packet. Hot environment fields persist until actual source publication overwrites them"
)
protocol["acceptance"]["cold_initialization"] = (
    "Fresh independent Decimal90/140 ionic/boundary/count/charge formulas from before-constructor inputs. Separate explicit primitive binary64 Q products/sums describe source branches; neither native nor model outputs condition this cold reference. Exact configured gene fields/matrix, raw partial-write refusals and a priori roundoff budgets"
)
protocol["acceptance"]["cold_roundoff"] = dict(
    factor="128*eps*(ion_count+cell_count+membrane_count+64)",
    concentration="Inherited concentration floor + factor*(abs(before)+abs(predicted_after))",
    count="factor*(abs(before_amount)+abs(predicted_after_amount))+1e-40 mol",
    ionic_charge="factor*(F*sum(abs(z)*(abs(before)+abs(predicted_after)))+abs(formal_gene_charge))+1e-25 C/m3",
    simulator_charge="factor*F*max(source_Q_gross)+1e-25 C/m3",
    a_priori=True,
    no_outcome_tuning=True,
)
protocol["accounting"].update(
    cold_source_compensation="Counterion removal is an actual numeric material sink, not a species conversion or implicit reservoir transfer. The boundary scalar is not a reservoir inventory. Formal gene charge uses source scale_factor; raw concentration/amount inventory does not",
    cold_ionic_counts="Per-species volume-weighted cell amount, declared single-bath mean*vol_env and separate source-effective sum(env*vol_env) before/after/change, including raw partial writes",
    cold_charge="Independent ionic charge change plus formal weighted gene charge, source Q and published source fields kept separate. The threshold-gap/off/failure cases need not cancel and gain no physical conservation credit",
    charged_environment="Cold bal_charge writes F*Qenv. Subsequent no-ECM publication writes zero molecular extra_rho_env; with runtime publication disabled, prior cold env charge persists. Preserve both behaviors",
    physical_global_conservation_credit=False,
    energetic_conservation_credit=False,
)
protocol["component_controls"]["new_caller_controls"] = [
    "zero_charge_control",
    "compensation_off",
    "growth_off",
]
protocol["failures"] = dict(
    raw=[
        "cell_positive_excess",
        "cell_negative_excess",
        "env_positive_excess",
        "env_negative_excess",
    ],
    capacity="Actual BetseSimConfException class/body, no ValueError alias; failures stop in bal_charge before regional rho write. Env failures retain completed cell removal and rho but balanced flag remains False",
    observations="Before/after events and full raw ionic/boundary/owner/simulator writes captured before assertions; reference inputs archived before constructors",
    dependencies="Each requires valid baseline admission followed by exact intended terminal refusal; every unexpected constructor archived",
    old_evidence="All neutral, pending transporter, accepted and failed packages untouched",
    positive_credit=False,
    retry="No worker numerical import/collection/evaluation/run, retry, polling or automatic follow-up",
)
protocol["source_order"] = [
    "Caller-prepared genuine M(-1)/P split and explicit native GRN configuration archived before constructors",
    "Original genuine owner/Core cold readers, source defaults, weighted Qcell/Qenv; cell compensation then env; source flag only after both complete",
    "Full cold state captured; compensated ionic buffers adopted into material parent; ordinary forcing applied",
    "Unchanged ordinary pump/ions/GJ/CaATP prefix and deferred commits; original normal GRN dispatch clear/modulators/Core",
    "All regulated GAD/reaction rates before commits, sequential original Molecule mover and source charge/current/no-ECM env omission",
    "Exact full caches/current/voltage carry; independent local warm forms and separate single-bath/directed-GJ ledgers",
]
write("validation/betse/" + NEW + "_join_protocol.json", protocol)
spec = importlib.util.spec_from_file_location(
    "charged_ast", ROOT / (WORK + NEW + "_join_ast_audit.py")
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
proof = module.audit()
write(
    "validation/betse/" + NEW + "_join_source_map.json",
    dict(
        kind="cells.normal_charged_grn_source_map@1",
        law_id=protocol["law_id"],
        source_revision=protocol["native_source"]["revision"],
        source_sha256=protocol["native_source"]["source_sha256"],
        scope=protocol["scope"],
        **proof,
    ),
)
protected = prior["protected_sha256"] | prior["owned_sha256"]
assert len(protected) == 245
queue = {
    key: value
    for key, value in prior.items()
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
    kind="cells.normal_charged_grn_static_workqueue@1",
    status="implementation_ready_for_static_audits",
    notes=WORK + "BETSE_NORMAL_CHARGED_GRN_JOIN_NOTES.md",
    runner=WORK + NEW + "_join_checks.py",
    owned=[name.replace(OLD, NEW) for name in prior["owned"]],
    protected_sha256=protected,
    binding_evidence=evidence,
    scientific_imports=0,
    numerical_runs=0,
    pytest_collection_runs=0,
    active_numerical_job=None,
    pending_transporter_dependency=False,
    pending_neutral_grn_dependency=False,
    protected_but_not_imported_side_package_paths=prior["owned"]
    + prior["protected_but_not_imported_side_package_paths"],
    workfiles=[
        WORK + name
        for name in (
            NEW + "_join_checks.py",
            NEW + "_join_ast_audit.py",
            NEW + "_join_static_audit.py",
            "betse_normal_charged_grn_key_schema_audit.py",
            "betse_normal_charged_grn_key_schema_witness_01.json",
            "prepare_native_charged_grn_package.py",
            "prepare_native_charged_grn_references.py",
            "prepare_native_charged_grn_checks.py",
            "prepare_native_charged_grn_evidence.py",
            "BETSE_NORMAL_CHARGED_GRN_JOIN_NOTES.md",
            "record_static_freeze_receipt.py",
        )
    ],
)
queue["owned_sha256"] = {name: sha(ROOT / name) for name in queue["owned"]}
write(WORK + NEW + "_join_workqueue.json", queue)
runner = (ROOT / (WORK + OLD + "_join_checks.py")).read_text().replace(OLD, NEW)
runner = runner.replace("normal-grn-join", "normal-charged-grn-join").replace(
    "CELLS_GRN_JOIN_CPU", "CELLS_CHARGED_GRN_JOIN_CPU"
)
runner = runner.replace(
    "cells.genuine_normal_grn_owner_prepared@1", "cells.normal_charged_grn_prepared@1"
)
runner = runner.replace(
    "test_genuine_grn_owner_and_conditional_reference",
    "test_charged_grn_owner_and_conditional_reference",
)
runner = runner.replace("test_genuine_grn_partial_failure", "test_charged_grn_partial_failure")
runner = runner.replace("test_complete_grn_dependencies", "test_complete_charged_grn_dependencies")
runner = runner.replace(
    'core = {"regulated", "GJ_zero", "source_defaults", "time_dilation"}',
    'core = {"positive", "negative", "negative_threshold_gap", "scaled_charge", "source_defaults", "time_dilation"}',
)
runner = (
    runner.replace('"new_grn_case"', '"new_charged_grn_case"')
    .replace("== 19\n", "== 22\n")
    .replace("== 14\n", "== 16\n")
)
runner = runner.replace(
    'and row["genuine_grn_owner_dispatch"] is True',
    'and row["genuine_grn_owner_dispatch"] is True\n            and row["charged_cold_compensation_checked"] is True\n            and row["compensated_parent_handoff_exact"] is True\n            and row["source_compensation_is_not_physical_conservation"] is True',
)
start, end = (
    runner.index("    for name, path in sorted(raw.items()):"),
    runner.index('    if group == "dependencies":'),
)
runner = (
    runner[:start]
    + """    for name, path in sorted(raw.items()):
        row = json.loads(path.read_text())
        case = path.parent.name.removeprefix("isolated-")
        if not (row["source_refused"] is True and row["source_type"] == "BetseSimConfException"
                and row["cold_initialization_failure"] is True and row["partial_owner_fields_preserved"] is True
                and row["completed_transports"] == 0 and row["cell_compensation_completed"] == case.startswith("env_")
                and row["preserved_source_charge_balanced_flag"] is False and row["cold_reference_forms"] == 2
                and row["intended_capacity_failure"] == case and row["positive_grn_credit"] is False
                and row["physical_conservation_credit"] is False):
            raise ValueError("Invalid charged GRN partial capacity failure")
        folder = base / ("preparation-" + case) / "cold-initialization"
        comp = json.loads((folder / "comparison.json").read_text())
        if not (comp["actual_cold_configuration_only"] is True and comp["physical_conservation_credit"] is False
                and comp["fields"] and all(0 <= v["normalized_max_error"] <= (0.1 if k.startswith("reference/") else 1) for k,v in comp["fields"].items())):
            raise ValueError("Invalid independent raw cold charge/count comparison")
        for level in (1,2):
            answer = json.loads((folder / ("reference-" + str(level) + ".json")).read_text())
            if not (answer["production_imports_denied"] and not answer["loaded_production_modules"]
                    and answer["cold_initialization"] is True and answer["decimal_precision"] == (90 if level == 1 else 140)
                    and answer["carried_reference_forms"] == 0 and answer["failure_case"] == case
                    and answer["source_exception"] == "BetseSimConfException" and answer["charge_has_been_balanced"] is False
                    and answer["source_compensation_only"] is True and answer["physical_conservation_credit"] is False):
                raise ValueError("Missing independent raw cold charge/count form")
        reports.append(dict(path=name, **row))
"""
    + runner[end:]
)
runner = runner.replace(
    'and answer["cold_initialization"] is True',
    'and answer["cold_initialization"] is True\n                and answer["source_compensation_only"] is True\n                and answer["physical_conservation_credit"] is False',
    1,
)
with (ROOT / (WORK + NEW + "_join_checks.py")).open("x") as stream:
    stream.write(runner)
print(
    json.dumps(
        dict(
            owned=10,
            protected=245,
            planned=protocol["planned"],
            scientific_imports=0,
            numerical_runs=0,
        )
    )
)
