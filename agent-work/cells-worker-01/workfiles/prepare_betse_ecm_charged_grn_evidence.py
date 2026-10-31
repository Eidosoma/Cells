# ruff: noqa: E501
"""Assemble a static review package; evaluate only stdlib AST builders."""

import ast
import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path("/home/robert/Cells")
WORK = ROOT / "agent-work/cells-worker-01/workfiles"
OLD, NEW = "betse_ecm_grn", "betse_ecm_charged_grn"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    with path.open("x") as stream:
        stream.write(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n")


def emit(name, value):
    with (WORK / name).open("x") as stream:
        stream.write(value)


audit = (WORK / (OLD + "_ast_audit.py")).read_text().replace(OLD, NEW)
charged = (WORK / "betse_normal_charged_grn_join_ast_audit.py").read_text()
numeric = next(
    ast.get_source_segment(charged, n)
    for n in ast.parse(charged).body
    if isinstance(n, ast.ClassDef) and n.name == "Numeric"
)
point = audit.index("\ndef audit():")
audit = audit[:point] + "\n\n" + numeric + "\n\n" + audit[point:]
audit = audit.replace(
    "    previous = old.captured_nodes()",
    "    old.Numeric = Numeric\n    previous = old.captured_nodes()",
    1,
)
point = audit.index("    assert len(proof) == 47, len(proof)")
audit = (
    audit[:point]
    + """    exception_source = classes(ast.parse((PIN / "exceptions.py").read_text()))["BetseSimConfException"]
    native_exception = classes(captured)["BetseSimConfException"]
    for node in (own["BetseSimConfException"], native_exception):
        assert digest(old.Numeric().visit(copy.deepcopy(node))) == digest(old.Numeric().visit(copy.deepcopy(exception_source)))
    proof["BetseSimConfException"] = dict(original_AST_equal=True,
        numeric_AST_sha256=digest(old.Numeric().visit(copy.deepcopy(exception_source))))
"""
    + audit[point:]
)
audit = audit.replace("== 47", "== 48").replace(
    "literal_scientific_body_count=47", "literal_scientific_body_count=48"
)
audit = audit.replace(
    '        "validate_definition",',
    '        "validate_definition",\n        "validate",\n        "wire",\n'
    '        "ionic_state",\n        "observe_balance",\n        "validate_ionic_cache",',
    1,
)
point = audit.index("    return dict(\n        literal_scientific_body_count=48,")
audit = (
    audit[:point]
    + """    old_ecm = functions(ast.parse((ROOT / "validation/betse/betse_ecm_grn_reference.py").read_text()))
    assert digest(ref["warm"]) == digest(old_ecm["warm"])
    assert digest(ref["hill"]) == digest(old_ecm["hill"])
    initial = ast.unparse(joined["initialize"])
    assert "source.material_values(ctx.sim)" in initial and "_state(binding, compensated" in initial
    assert "boundary_override" in ast.unparse(joined["advance"])
    assert "parent.network_cache['wire']['ion_boundary_state']" in ast.unparse(joined["advance"])
    assert "net._balance_events = clone(raw['balance_events'])" in ast.unparse(ownf["restore"])
    assert "setattr(ctx.sim, key, clone(value))" in ast.unparse(ownf["restore"])
    assert "self.mit_enabled = mit_enabled" in ast.unparse(functions(own["MasterOfNetworks"])["__init__"])
    assert "cc_env" in ast.unparse(ownf["validate_ionic_cache"])
"""
    + audit[point:]
)
audit = audit.replace(
    "        independent_Hill_reference_unchanged=True,",
    """        independent_Hill_reference_unchanged=True,
        independent_ECM_warm_reference_entire_AST_unchanged=True,
        actual_source_ConfException_class=True,
        compensated_material_parent_adopted_before_first_call=True,
        full_ionic_snapshot_and_cold_balance_events_carried=True,
        boundary_carry_default_with_explicit_packet_override=True,
        all_five_simulator_publications_carried=True,
        caller_disabled_mitochondrial_flag_preserved=True,""",
)
emit(NEW + "_ast_audit.py", audit)

prior = json.loads((WORK / (OLD + "_workqueue.json")).read_text())
protocol = json.loads((ROOT / f"validation/betse/{OLD}_protocol.json").read_text())
protocol.update(
    kind="cells.normal_ecm_charged_grn_static_contract@1",
    law_id="betse_normal_ecm_charged_grn_network_v1_5_0@1",
    source_map=f"validation/betse/{NEW}_source_map.json",
    purpose="Reachable charged ECM cold compensation with genuine owner, compensated material parent, full cache/publication and normal dispatch carry",
)
evidence = dict(prior["binding_evidence"])
for label, path in (
    ("frozen_ecm01_inputs", Path(prior["prepared_inputs"])),
    ("frozen_ecm01_static_receipt", ROOT / prior["static_receipt"]),
    ("ecm_charged_grn_reachability", WORK / (NEW + "_reachability_01.json")),
):
    evidence[label] = dict(path=str(path), sha256=sha(path))
protocol["binding_evidence"] = evidence
protocol["planned"] = dict(
    checks=35,
    positive_three_call_histories=18,
    new_ecm_charged_grn_histories=14,
    component_control_histories=4,
    raw_partial_capacity_failures=4,
    raw_cold_failures=4,
    raw_ecm_runtime_failures=0,
    dependency_controls=13,
    native_captures=22,
    actual_pre_network_points=54,
    independent_cold_points=22,
    fresh_warm_Decimal_forms=108,
    fresh_cold_Decimal_forms=44,
    fresh_Decimal_reference_forms=152,
    carried_reference_forms=0,
    completed_positive_mover_invocations_per_implementation=108,
    biological_cases=0,
)
scope = protocol["scope"]
scope["charge"] = (
    "Actual Na(+1), K(+1), stationary M(-1) rows; caller splits old P(-1) input by exactly supplied M. Cold weighted source Q, cell compensation before full E-grid env and boundary compensation, then balanced flag. Source membrane caches stay stale; negative cell threshold gap preserved. Compensated buffers become the material parent."
)
scope["cold_hot"] = (
    "Original cold constructors/readers once; live native owner persists. Full public owner/core/molecule/reaction/modulator state, ionic snapshots, compensation events, grid coefficients and all five simulator publications carry. Hot alias rebuild uses current material buffers, never replaces them with older ionic observations and never reruns cold readers. Default cold-compensated boundary carries; an explicit scheduled override replaces it and then carries."
)
scope["exclusions"] = [
    item.replace(", charged cold counterion compensation", "") for item in scope["exclusions"]
]
scope["exclusions"].append(
    "Mitochondria remain caller-disabled at both native constructor sites; no forced flag or externally preenabled pickle"
)
protocol["acceptance"]["cold"] = (
    "Fresh Decimal100/160 from immutable inputs before either constructor. Independent source-rounded scalar Q/branch decisions, full cell/E-grid concentrations, unchanged M-membrane caches, ionic boundary, publications and balanced flag. Independent per-species cell and source-uniform-site amounts, native true-volume diagnostic and formal-vs-ionic charge ledgers. Raw partial failures use the same fixed checks."
)
protocol["acceptance"]["cold_budget"] = (
    "factor=128*eps*(ions+cells+membranes+environment_sites+64). Concentrations3e-13+factor*(abs(input)+abs(independent predicted)); charge1e-25+factor*(independent ionic absolute before/after gross+abs(independent formal charge)); counts factor*independent amount gross+3e-13*input-derived measure; cold currents1e-30 and rho1e-25+factor*F*independent gross Q. Actual outgoing arrays never determine budgets."
)
protocol["acceptance"]["primary"] += (
    "; complete cold ionic/cache/boundary snapshots and compensated full material-parent handoff exact, genuine ConfException type and partial earlier writes"
)
protocol["accounting"]["cold_compensation"] = (
    "Counterion removal is an explicit material sink. Cold boundary scalars are not inventory. Formal gene charge uses scale_factor but raw gene amounts do not. Cell-negative admission uses bulk M mean while refusal uses stale membrane M mean; the gap can publish rho and set balanced True without removing M. Ordinary moving-ion updates and stale stationary M are preserved."
)
protocol["accounting"]["cold_environment"] = (
    "Full E grid is distinct from M membranes. Source-effective environment amounts use uniform cell_height*delta^2; native true_environment_volume is a separate diagnostic. No single-bath volume reinterpretation or global conservation claim."
)
protocol["failures"] = dict(
    raw=[
        "cell_positive_excess",
        "cell_negative_excess",
        "env_positive_excess",
        "env_negative_excess",
    ],
    retention="Actual original BetseSimConfException with full ionic/boundary/publication/public cache and before/after compensation observations. Cell failures precede rho/flag writes; env failures preserve completed cell compensation/rho and leave balanced False. Env failure recipes use E12/M9. Full raw source stdout and traceback retained.",
    dependencies="Valid baseline first; exact thirteen intended ValueError witnesses and exact report/pytest ID sets; never substitute preflight refusal for source failure.",
    positive_credit=False,
)
write(ROOT / f"validation/betse/{NEW}_protocol.json", protocol)
spec = importlib.util.spec_from_file_location("ecm_charged_AST", WORK / (NEW + "_ast_audit.py"))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
proof = module.audit()
write(
    ROOT / f"validation/betse/{NEW}_source_map.json",
    dict(
        kind="cells.normal_ecm_charged_grn_source_map@1",
        law_id=protocol["law_id"],
        native_source_sha256=protocol["native_source"]["source_sha256"],
        scope=scope,
        **proof,
    ),
)

owned = [path.replace(OLD, NEW) for path in prior["owned"]]
queue = {
    key: prior[key]
    for key in (
        "authorized_physical_helper_refactor",
        "coordinated_shared_edit_paths",
        "coordinated_unrelated_physics_edits",
        "automatic_launch",
        "automatic_polling",
        "automatic_followup",
    )
    if key in prior
}
queue.update(
    kind="cells.normal_ecm_charged_grn_workqueue@1",
    status="ready_for_static_audits",
    owned=owned,
    owned_sha256={path: sha(ROOT / path) for path in owned},
    protected_sha256=prior["protected_sha256"] | prior["owned_sha256"],
    binding_evidence=evidence,
    runner="agent-work/cells-worker-01/workfiles/" + NEW + "_checks.py",
    scientific_imports=0,
    scientific_AST_executions=0,
    pytest_collection_runs=0,
    numerical_runs=0,
    active_numerical_job=None,
    protected_but_not_imported_side_package_paths=prior[
        "protected_but_not_imported_side_package_paths"
    ],
    workfiles=[
        "agent-work/cells-worker-01/workfiles/" + name
        for name in (
            NEW + "_ast_audit.py",
            NEW + "_static_audit.py",
            NEW + "_checks.py",
            "prepare_" + NEW + "_science.py",
            "prepare_" + NEW + "_inputs.py",
            "prepare_" + NEW + "_checks.py",
            "prepare_" + NEW + "_evidence.py",
            NEW + "_reachability_01.json",
            "record_static_freeze_receipt.py",
        )
    ],
)
write(WORK / (NEW + "_workqueue.json"), queue)

runner = (WORK / (OLD + "_checks.py")).read_text().replace(OLD, NEW)
runner = runner.replace("test_ecm_grn_", "test_ecm_charged_grn_").replace(
    "ecm-grn", "ecm-charged-grn"
)
runner = runner.replace("CELLS_ECM_GRN_CPU", "CELLS_ECM_CHARGED_GRN_CPU")
runner = runner.replace('"new_ecm_grn_case"', '"new_ecm_charged_grn_case"')
runner = runner.replace(
    '{"charged", "negative", "tight_junction", "fast_duplicate"}',
    '{"positive", "negative", "negative_threshold_gap", "rectangular", "fast_duplicate"}',
)
runner = runner.replace("== 25", "== 35").replace("== 17", "== 22")
runner = runner.replace(
    "cells.normal_ecm_grn_prepared@1", "cells.normal_ecm_charged_grn_prepared@1"
)
runner = runner.replace(
    'and row["genuine_ecm_grn"] is True',
    'and row["genuine_ecm_grn"] is True\n'
    '            and row["charged_cold_compensation_checked"] is True\n'
    '            and row["compensated_parent_handoff_exact"] is True\n'
    '            and row["source_compensation_is_not_physical_conservation"] is True',
)
start = runner.index('        cold = case.startswith("cold_")')
end = runner.index("        reports.append(dict(path=name, **row))", start)
runner = (
    runner[:start]
    + """        if not (
            row["source_refused"] is True and row["source_type"] == "BetseSimConfException"
            and row["cold_initialization_failure"] is True and row["exact_native_partial"] is True
            and row["complete_ionic_boundary_cache_and_publication"] is True
            and row["cell_before_environment"] is True and row["independent_cold_reference_forms"] == 2
            and row["source_compensation_is_not_physical_conservation"] is True
            and row["positive_credit"] is False and row["physical_conservation_credit"] is False
        ):
            raise ValueError("Invalid ECM charged raw capacity retention")
        references(base / ("preparation-"+case) / "cold",True)
"""
    + runner[end:]
)
emit(NEW + "_checks.py", runner)
print(
    json.dumps(
        dict(
            owned=len(owned),
            protected=len(queue["protected_sha256"]),
            literal_bodies=proof["literal_scientific_body_count"],
            planned=protocol["planned"],
            numerical_runs=0,
        )
    )
)
