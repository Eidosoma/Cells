# ruff: noqa: E501
"""Prepare new standalone ECM protocol/runner, without running any science."""

import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path("/home/robert/Cells")
WORK = ROOT / "agent-work/cells-worker-01/workfiles"
NEW = "betse_ecm_sim_grn"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    with path.open("x") as stream:
        stream.write(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n")


scalar = json.loads((ROOT / "validation/betse/betse_sim_grn_protocol.json").read_text())
ecm = json.loads((ROOT / "validation/betse/betse_ecm_grn_protocol.json").read_text())
prior = json.loads((WORK / "betse_ecm_charged_grn_workqueue.json").read_text())
evidence = dict(prior["binding_evidence"])
for label, path in (
    (
        "standalone_scalar01_inputs",
        Path("/mnt/workspaces/Cells/betse-sim-grn-prepared-20261030-01/inputs.json"),
    ),
    ("standalone_scalar01_static_receipt", WORK / "betse_sim_grn_static_receipt_01.json"),
    (
        "protected_ecm_charged02_inputs",
        Path("/mnt/workspaces/Cells/betse-ecm-charged-grn-prepared-20261031-02/inputs.json"),
    ),
    ("protected_ecm_charged02_receipt", WORK / "betse_ecm_charged_grn_static_receipt_02.json"),
    ("standalone_ecm_reachability", WORK / (NEW + "_reachability_01.json")),
):
    evidence[label] = dict(path=str(path), sha256=sha(path))
protocol = dict(scalar)
protocol.update(
    kind="cells.native_standalone_ecm_sim_grn_static_contract@1",
    law_id="betse_standalone_ecm_sim_grn_v1_5_0@1",
    source_map="validation/betse/" + NEW + "_source_map.json",
    purpose="Actual standalone new-owner and entire run_core_sim on native-derived ECM grid/buffers, with repeated reinitialization/sampling/field-publication carry",
    binding_evidence=evidence,
    native_source=dict(ecm["native_source"]),
)
protocol["native_source"]["source_sha256"] = (
    ecm["native_source"]["source_sha256"] | scalar["native_source"]["source_sha256"]
)
protocol["planned"] = dict(
    checks=35,
    positive_two_invocation_histories=18,
    new_ecm_standalone_histories=13,
    component_control_histories=5,
    inherited_scalar_controls=3,
    positive_standalone_invocations=36,
    actual_pre_core_points=121,
    independent_cold_points=18,
    independent_clock_points=36,
    fresh_warm_Decimal_forms=242,
    fresh_cold_Decimal_forms=36,
    fresh_clock_Decimal_forms=72,
    fresh_Decimal_reference_forms=350,
    carried_reference_forms=0,
    raw_partial_failures=7,
    dependency_controls=10,
    native_captures=25,
    completed_positive_mover_invocations_per_implementation=242,
    biological_cases=0,
)
scope = dict(scalar["scope"])
scope["supplied_phase"] = (
    "Explicit native-derived ECM three-cell/nine-membrane/four-ion phase with E9 or E12 grid. Original field grid/owner/environment AST constructs native geometry; port derives the same from original declarations. No phase pickle/world loading, full init_dynamics/profile/diffusion-mask lifecycle or field solve is performed."
)
scope["state"] = (
    "Entire public owner/core/molecule/reaction/modulator state, complete simulator/parameters/boundaries, all active grid fields and Na-derived coefficients, sampled caches and captured output text persist. Native owner and grid objects remain live; port hydrates fields and rebuilds enabled concentration aliases, skipping disabled Ca."
)
scope["distinctions"] = (
    "Actual run_core_sim forces publication False, skips clear_run_loop and configured modulator/channel dispatch, and keeps all five incoming simulator charge/current fields. Original core constructor supplies three zero current fields; absent core rho fields are preserved as absent. Charged product electrodiffusion still executes. No new charge/current publication is credited."
)
scope["ECM"] = (
    "Actual full E-grid versus M-membrane arrays, original membrane/GJ mover, Na-normalized diffusion weights/TJ indices, collocated FD/electrodiffusion, fast duplicate-last versus area-sum exchange, boundary clamp and smoothing. External old electric fields/rho_channel/gap controls stay held; no normal material or field advance."
)
scope["cold"] = (
    "Original SimRunner new-owner true branch and actual local MasterOfGenes.read_gene_config. Charged cold publication disabled; a neutral cold-publication control writes source zero rho. Charged compensation and externally preenabled mitochondria remain outside this boundary."
)
scope["exclusions"] = [
    entry.replace("Mitochondrial/ECM spatial state", "Mitochondrial state")
    for entry in scope["exclusions"]
]
protocol["scope"] = scope
protocol["retained_ecm_limit"] = ecm["retained_ecm_limit"]
protocol["inherited_status"] = (
    "Scalar standalone initial22 was reported completed, without importing a pending implementation or claiming terminal acceptance here. ECM01 failed6/2 with17 unrun; ECM02 and charged packages remain separately reviewed/qualified by Chief. No predecessor result is inherited as ECM standalone accuracy."
)
acceptance = dict(ecm["acceptance"])
acceptance.update(
    primary="Exact independently captured original new-owner/run_core_sim, cold/full owner+grid+simulator state, every core/mover/reinit/cache/sample/IO frame, all full repeated-invocation states and raw partial errors. Port cold parent and all returned raw calls archived before subsequent calls/assertions.",
    independent="Fresh Decimal100/160 cold configuration with independent geometry, source-independent binary64 clock/sampling specification and high-precision dt counts, fresh independent ECM GAD/reaction/mover/FD/books from each actual pre-core point. Zero carried forms.",
    warm_reference_delta="Entire prior ECM warm reference AST is unchanged after restoring only the removed modulator-dispatch iteration; standalone never calls these configured modulators. Scalar clock AST changes only Decimal precision90/140 to100/160.",
    clock="Exact independent source-rounded binary64 linspace/sampling-index specification; actual source parameter rewrites and sampled arrays exact. Timestamp intervals and numerical dt advanced are separate.",
    publication="All five simulator fields persist exactly through forced publication False; three existing core current fields persist, absent core rho fields stay absent. Hypothetical zero reference rho is not a source publication or conservation claim.",
)
protocol["acceptance"] = acceptance
protocol["accounting"] = dict(ecm["accounting"])
protocol["accounting"]["standalone"] = (
    "No ordinary ionic material advance. Ionic buffers and boundary values persist; molecular sources/transport/clamp/FD/smoothing source terms use uniform source site volume. Native true-volume diagnostics remain separate. No physical/global material/charge/energy claim follows."
)
protocol["failures"] = dict(
    raw=[
        "cold_missing_Y_Dm",
        "first_negative",
        "second_negative",
        "second_call_missing_Y_Dm",
        "late_plot_cell",
        "first_environment_negative",
        "second_environment_negative",
    ],
    retention="Cold KeyError, first/second molecular chemical or E12-grid instability, second-invocation property failure before sampled-cache clear, late invalid plot cell after save/dir. Complete partial state, grid/fields, clocks/samples, prior completed calls, mover locals/tracebacks retained. Unexpected returned parents/calls are archived immediately.",
    dependencies="Ten exact admission/cache boundaries with admitted valid baseline and durable malformed snapshot before invocation; sampling below dt is rejected rather than executing the nonprogressing source loop.",
    positive_credit=False,
)
write(ROOT / ("validation/betse/" + NEW + "_protocol.json"), protocol)
spec = importlib.util.spec_from_file_location("ECM_standalone_AST", WORK / (NEW + "_ast_audit.py"))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
proof = module.audit()
write(
    ROOT / ("validation/betse/" + NEW + "_source_map.json"),
    dict(
        kind="cells.ecm_standalone_source_map@1",
        law_id=protocol["law_id"],
        native_source_sha256=protocol["native_source"]["source_sha256"],
        scope=scope,
        **proof,
    ),
)
owned = ["src/cells/processes/" + NEW + ".py", "tests/unit/test_" + NEW + ".py"] + [
    "validation/betse/" + NEW + "_" + suffix
    for suffix in ("fixtures.py", "native.py", "reference.py", "protocol.json", "source_map.json")
]
q = {
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
q.update(
    kind="cells.ecm_standalone_workqueue@1",
    status="static_implementation_ready_pending_coordinated_capture03_pins",
    owned=owned,
    owned_sha256={p: sha(ROOT / p) for p in owned},
    protected_sha256=prior["protected_sha256"] | prior["owned_sha256"],
    binding_evidence=evidence,
    runner="agent-work/cells-worker-01/workfiles/" + NEW + "_checks.py",
    active_numerical_job=None,
    scientific_imports=0,
    scientific_AST_executions=0,
    pytest_collection_runs=0,
    numerical_runs=0,
    protected_but_not_imported_side_package_paths=prior["owned"]
    + [
        p
        for p in prior["protected_sha256"]
        if any(
            name in p
            for name in ("betse_sim_grn", "betse_normal_transporter", "betse_normal_charged_grn")
        )
    ],
    workfiles=[
        "agent-work/cells-worker-01/workfiles/" + p
        for p in (
            NEW + "_ast_audit.py",
            NEW + "_static_audit.py",
            NEW + "_checks.py",
            NEW + "_reachability_01.json",
            "prepare_" + NEW + "_science.py",
            "prepare_" + NEW + "_inputs.py",
            "prepare_" + NEW + "_checks.py",
            "prepare_" + NEW + "_audit.py",
            "prepare_" + NEW + "_evidence.py",
            "ecm_sim_grn_context_template.txt",
            "record_static_freeze_receipt.py",
        )
    ],
)
write(WORK / (NEW + "_workqueue.json"), q)
runner = (WORK / "betse_sim_grn_checks.py").read_text().replace("betse_sim_grn", NEW)
runner = runner.replace("test_standalone_grn_", "test_ecm_standalone_grn_").replace(
    "sim-grn", "ecm-sim-grn"
)
runner = runner.replace("CELLS_SIM_GRN_CPU", "CELLS_ECM_SIM_GRN_CPU")
runner = runner.replace('"new_standalone_grn_case"', '"new_ecm_standalone_case"')
runner = runner.replace("== 22", "== 35").replace("== 15", "== 25")
runner = runner.replace(
    "native_source_copies=44,",
    "native_source_copies=" + str(2 * len(protocol["native_source"]["source_sha256"])) + ",",
)
runner = runner.replace("(90 if level == 1 else 140)", "(100 if level == 1 else 160)")
runner = runner.replace(
    "cells.genuine_standalone_grn_prepared@1", "cells.standalone_ecm_grn_prepared@1"
)
start = runner.index("        core = {")
end = runner.index('        for case in constants["CASES"]:', start)
runner = (
    runner[:start]
    + '        core={"standard","negative","rectangular","fast_duplicate","tight_junction"}\n'
    + runner[end:]
)
runner = runner.replace(
    'and row["standalone_run_core_sim"] is True',
    'and row["standalone_run_core_sim"] is True\n            and row["standalone_ECM"] is True\n'
    '            and row["full_grid_E_buffers_and_publication_carry"] is True',
)
with (WORK / (NEW + "_checks.py")).open("x") as stream:
    stream.write(runner)
print(
    json.dumps(
        dict(
            owned=7,
            protected=len(q["protected_sha256"]),
            literal_bodies=52,
            native_pins=len(protocol["native_source"]["source_sha256"]),
            planned=protocol["planned"],
            scientific_execution=False,
        )
    )
)
