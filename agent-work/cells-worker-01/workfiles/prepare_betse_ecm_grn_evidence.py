# ruff: noqa: E501 -- frozen protocol and emitted report templates.
"""Bind retained ECM limits and emit a static new-prefix GRN package."""

import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path("/home/robert/Cells")
WORK = "agent-work/cells-worker-01/workfiles/"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    with (ROOT / path).open("x") as f:
        json.dump(value, f, indent=2, sort_keys=True, allow_nan=False)
        f.write("\n")


prior = json.loads((ROOT / (WORK + "betse_sim_grn_workqueue.json")).read_text())
neutral = json.loads((ROOT / "validation/betse/betse_normal_grn_join_protocol.json").read_text())
ecm_plan_path = ROOT / "agent-work/cells-specialist/betse_ecm_transport_qualification_plan.json"
ecm_plan = json.loads(ecm_plan_path.read_text())
ecm_protocol = json.loads((ROOT / "validation/betse/betse_ecm_transport_protocol.json").read_text())
assert ecm_plan["original_panel"] == dict(
    output="/mnt/workspaces/Cells/betse-ecm-transport-20261030-02",
    checks=40,
    passed=39,
    failed=1,
    accepted=False,
)
evidence = dict(prior["binding_evidence"])
review = Path(
    "/mnt/workspaces/Cells/betse-normal-charged-grn-tests-20261030-01/root-review-01/REVIEW.json"
)
evidence.update(
    accepted_charged_grn_review=dict(path=str(review), sha256=sha(review)),
    protected_standalone_inputs=dict(
        path=prior["prepared_inputs"], sha256=prior["prepared_inputs_sha256"]
    ),
    protected_standalone_receipt=dict(
        path=str(ROOT / prior["static_receipt"]), sha256=prior["static_receipt_sha256"]
    ),
    retained_ecm_qualification_plan=dict(path=str(ecm_plan_path), sha256=sha(ecm_plan_path)),
    retained_ecm_failed_round=dict(
        path=ecm_plan["failed_round_receipt"], sha256=ecm_plan["failed_round_receipt_sha256"]
    ),
)
native = dict(neutral["native_source"])
native["source_sha256"] = (
    dict(native["source_sha256"]) | ecm_protocol["native_source"]["source_sha256"]
)
planned = dict(
    checks=25,
    positive_three_call_histories=13,
    new_ecm_grn_histories=9,
    component_control_histories=4,
    raw_partial_failures=4,
    raw_cold_failures=2,
    raw_ecm_runtime_failures=2,
    dependency_controls=8,
    native_captures=17,
    actual_pre_network_points=39,
    independent_cold_points=13,
    fresh_warm_Decimal_forms=78,
    fresh_cold_Decimal_forms=26,
    fresh_Decimal_reference_forms=104,
    carried_reference_forms=0,
    completed_positive_mover_invocations_per_implementation=78,
    biological_cases=0,
)
protocol = dict(
    kind="cells.normal_ecm_grn_static_contract@1",
    law_id="betse_normal_ecm_grn_network_v1_5_0@1",
    status="static_unqualified_no_numerics",
    purpose="Actual nonempty GRN initialization/normal guarded dispatch with molecular ECM transport/publication between retained ordinary ECM transport and deferred commit",
    native_source=native,
    source_map="validation/betse/betse_ecm_grn_source_map.json",
    binding_evidence=evidence,
    planned=planned,
    resources=dict(neutral["resources"]),
    scope=dict(
        context="Retained native-derived Cartesian grid/ownership/maps/area-sum operators and complete ECM material buffers; full E-site environments distinct from M membrane buffers",
        source_order="Original cold GRN guard884-900; per-call original ECM reset/ion/clamp/transport/refresh, supplied late flux, actual guarded GRN1306-1319, deferred ordinary update_all_concs1357",
        owner="Actual MasterOfGenes and actual configured MasterOfNetworks/Molecule objects; molecules owner disabled, grn_enabled=True are executed source-context flags",
        nonempty="Two configured X/Y genes, native Hill GAD, one irreversible X-to-Y conversion and ion-driven GJ/NaK modulators; full original intra refresh, all RHS before commits, sequential real transport",
        charge="Charged +/-1 equal-weight products with scale1e-6; cold publication/compensation disabled. Separate neutral cold-publication control; actual ECM rho_env/Jenv_x/Jenv_y and membrane/cell publication execute",
        context_derivation="Original radial-vector/radius statements; original Na D_env/max and weight-base copy; original TJ-index concatenation from explicitly supplied original boundary-index groups. Full diffusion-mask/tissue generation excluded",
        cold_hot="Cold native constructors/readers execute once; live native owner persists. Port hydrates full public fields/aliases plus grid coefficients. Current packet ionic boundaries stay authoritative; gene boundary scalars and simulator publications carry",
        controls="Carried/scheduled GJ control feeds next ordinary fixed-gap branch; new modulator output immediately feeds molecule GJ transport with already-computed gap opening. NaK output carries but supplied pump flux does not authenticate a pump law",
        external="Pump/late flux, channel multiplier, fixed-gap branch controls and old electric field supplied; fluid disabled and no field/current/voltage solver feedback",
        exclusions=[
            "Full seed/mesh/tissue/diffusion-mask/Simulator lifecycle",
            "Mitochondria, fluid/cuts/events/noise, separate transporters/channels, charged cold counterion compensation",
            "Standalone sim-grn orchestration",
            "Physical global material/charge/energy conservation, finite/shared fuel, biological calibration or independently carried trajectory accuracy",
        ],
    ),
    retained_ecm_limit=dict(
        ecm_plan["known_failed_case"],
        panel=ecm_plan["original_panel"],
        source=ecm_plan["failed_round_receipt"],
        new_package_reclassifies_old_panel=False,
        low_inventory_alternative_not_run_or_credited=True,
    ),
    acceptance=dict(
        primary="Exact full original/native derived maps, cold owner/cache/defaults, ordinary/material frames and ECM locals, actual GRN stages/RHS/mover/complete public cache/boundary/controls/publication and raw partial failures",
        independent="Fresh Decimal100/160 from inputs archived before constructors or outgoing GRN computation; independent geometry from original declarations, ordinary Hill/reaction equations, membrane/GJ/fast-vs-slow scatter, molecular clamp/FD/Euler/smoothing and charge/current",
        inherited_budget_source_sha256=neutral["acceptance"]["inherited_budget_source_sha256"]
        | {
            "validation/betse/betse_ecm_transport_protocol.json": sha(
                ROOT / "validation/betse/betse_ecm_transport_protocol.json"
            )
        },
        material="3e-13 concentration or1e-18 flux floor +128*eps*(ions+2+cells+membranes+environment_sites+64)*independent local gross",
        gradients="A priori derivative gross uses sums of absolute predicted neighboring values over delta (2*delta interior); flux gross propagates cancellation plus q/kb electric terms; no actual outgoing values enter budgets",
        publication="Same reference-fixed factor*independent F*z*scale-weighted concentration/flux gross +1e-25 C/m3 or1e-30 A/m2",
        rates="Inherited2e-14 mM/s +5e-12*abs(reference); delta6e-14 +5e-12*independent gross",
        amount="Factor times independent absolute old/new amounts, signed source mechanisms and native-true-volume gross, plus3e-13 concentration floors times input volume sums",
        cold="Exact independent configured/default scalar/array fields, matrix and source publication; independently derived maps/operators checked separately",
        self_resolution_fraction=0.1,
        no_outcome_tuning=True,
        old_ecm_diagnostic_budget_unchanged=True,
    ),
    accounting=dict(
        source_effective="Uniform source site volume cell_height*delta^2; separately retain cell membrane transfer, source grid exchange, conservative area-sum oracle, fast duplicate-last defect, gene source/conversion, directed GJ, boundary-clamp reservoir writes, collocated transport and smoothing changes",
        alternate="Native true_environment_volume field is a separate diagnostic amount change, never a volume reinterpretation that closes source books",
        source_identity="Final minus initial minus independently predicted source terms; signed terms and full errors/budgets retained",
        physical_global_conservation_credit=False,
        energetic_conservation_credit=False,
        retained_failure="Original signed_environment diagnostic and39/40 panel remain failed; no rerun, reconstruction or budget relaxation",
    ),
    failures=dict(
        raw=[
            "cold_X_missing_Dm",
            "cold_Y_missing_Dm",
            "first_environment_negative",
            "second_environment_negative",
        ],
        retention="Original KeyError or genuine BetseSimUnstableException, complete cold/partial gene and ionic/boundary/cache/publication state, prefix frames/locals and tracebacks; first successful species retained before second failure",
        raw_stress="Only chosen molecule Do becomes1e12 with zero supplied Ey and linear Ex; source collocated environment instability remains raw, not clipped/repaired",
        dependencies="Valid cold baseline first, exact intended terminal ValueError and exact witness set; no source failure credit",
        positive_credit=False,
    ),
    input_versus_execution=dict(
        supplied="Original geometry/material/configuration declarations, external physical seams and explicit TJ index groups",
        executed="Actual original normal GRN guard/lifecycle/molecular ECM FD equations and retained ordinary material chronology",
        conditional_credit="Independent local network accuracy only; no upstream or whole-ECM-solver qualification follows",
    ),
)
write("validation/betse/betse_ecm_grn_protocol.json", protocol)
spec = importlib.util.spec_from_file_location(
    "ecm_AST", ROOT / (WORK + "betse_ecm_grn_ast_audit.py")
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
proof = module.audit()
write(
    "validation/betse/betse_ecm_grn_source_map.json",
    dict(
        kind="cells.normal_ecm_grn_source_map@1",
        law_id=protocol["law_id"],
        native_source_sha256=native["source_sha256"],
        scope=protocol["scope"],
        **proof,
    ),
)
protected = prior["protected_sha256"] | prior["owned_sha256"] | ecm_plan["owned_source_sha256"]
owned = [
    "src/cells/processes/betse_ecm_grn_source.py",
    "src/cells/processes/betse_ecm_grn_join.py",
    "tests/unit/test_betse_ecm_grn_join.py",
] + [
    "validation/betse/betse_ecm_grn_" + suffix
    for suffix in (
        "fixtures.py",
        "native.py",
        "native_network.py",
        "reference.py",
        "protocol.json",
        "source_map.json",
    )
]
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
if "src/cells/models/open_calcium_runtime.py" not in queue["coordinated_shared_edit_paths"]:
    queue["coordinated_shared_edit_paths"].append("src/cells/models/open_calcium_runtime.py")
queue.update(
    kind="cells.normal_ecm_grn_workqueue@1",
    status="ready_for_static_audits",
    owned=owned,
    protected_sha256=protected,
    binding_evidence=evidence,
    runner=WORK + "betse_ecm_grn_checks.py",
    notes=WORK + "BETSE_ECM_GRN_NETWORK_NOTES.md",
    scientific_imports=0,
    scientific_AST_executions=0,
    pytest_collection_runs=0,
    numerical_runs=0,
    active_numerical_job=None,
    protected_but_not_imported_side_package_paths=prior["owned"]
    + [
        name
        for name in prior["protected_sha256"]
        if "betse_normal_charged_grn" in name or "betse_normal_transporter" in name
    ],
    workfiles=[
        WORK + name
        for name in (
            "betse_ecm_grn_ast_audit.py",
            "betse_ecm_grn_static_audit.py",
            "betse_ecm_grn_checks.py",
            "prepare_betse_ecm_grn_science.py",
            "prepare_betse_ecm_grn_join.py",
            "prepare_betse_ecm_grn_native.py",
            "prepare_betse_ecm_grn_inputs.py",
            "prepare_betse_ecm_grn_evidence.py",
            "ecm_grn_adapter_template.txt",
            "ecm_grn_validation_template.txt",
            "BETSE_ECM_GRN_NETWORK_NOTES.md",
            "record_static_freeze_receipt.py",
        )
    ],
)
queue["owned_sha256"] = {name: sha(ROOT / name) for name in owned}
write(WORK + "betse_ecm_grn_workqueue.json", queue)
runner = (
    (ROOT / (WORK + "betse_sim_grn_checks.py"))
    .read_text()
    .replace("betse_sim_grn", "betse_ecm_grn")
    .replace(
        'TEST = "tests/unit/test_betse_ecm_grn.py"',
        'TEST = "tests/unit/test_betse_ecm_grn_join.py"',
    )
    .replace('"evidence/sim-grn"', '"evidence/ecm-grn"')
    .replace("CELLS_SIM_GRN_CPU", "CELLS_ECM_GRN_CPU")
)
runner = (
    runner.replace("test_standalone_grn_advancing_history", "test_ecm_grn_history")
    .replace("test_standalone_grn_partial_failure", "test_ecm_grn_partial_failure")
    .replace("test_standalone_grn_dependencies", "test_ecm_grn_dependencies")
)
start = runner.index("        core = {")
end = runner.index('        for case in constants["CASES"]:', start)
runner = (
    runner[:start]
    + '        core = {"charged","negative","tight_junction","fast_duplicate"}\n'
    + runner[end:]
)
runner = (
    runner.replace('actual_core_calls=2 if case == "single_step" else 7,', "genuine_ecm_grn=True,")
    .replace('"new_standalone_grn_case"', '"new_ecm_grn_case"')
    .replace("== 22\n", "== 25\n")
    .replace("== 15\n", "== 17\n")
)
start = runner.index("def molecule_reports(")
end = runner.index("\ndef run(", start)
runner = (
    runner[:start]
    + """def molecule_reports(target,group,inputs):
    base=target/"evidence/ecm-grn"
    required=inputs["required_reports"][group]
    found={str(p.relative_to(base)):p for p in base.glob("isolated-*/comparison.json")}
    if set(found)!=set(required["positive"]):raise ValueError("Exact ECM positive report set differs")
    reports=[]
    def references(folder,cold=False):
        comp=json.loads((folder/"comparison.json").read_text())
        if not(comp["fresh_conditional_reference"] is True and comp["physical_global_conservation_credit"] is False and comp["fields"] and all(0<=v["normalized_max_error"]<=1 for v in comp["fields"].values()) and all(0<=v["normalized_max_error"]<=0.1 for v in comp["resolutions"].values())):raise ValueError("ECM conditional reference budget failed")
        for level in (1,2):
            answer=json.loads((folder/("reference-"+str(level)+".json")).read_text())
            if not(answer["production_imports_denied"] and not answer["loaded_production_modules"] and answer["carried_reference_forms"]==0 and answer["decimal_precision"]==(100 if level==1 else 160)):raise ValueError("Missing fresh independent ECM form")
            if cold and answer["cold_initialization"] is not True:raise ValueError("Missing independent ECM cold form")
    for name,path in sorted(found.items()):
        row=json.loads(path.read_text())
        if not(row["completed"] is True and row["exact_native"] is True and row["complete_calls"]==3 and row["conditional_pre_network_checks"]==3 and row["genuine_ecm_grn"] is True and row["complete_public_cache_carry"] is True and row["cold_reference_forms"]==2 and row["warm_reference_forms"]==6 and row["carried_reference_forms"]==0 and row["retained_material_panel_accepted"] is False and row["retained_material_checks_passed"]==39 and row["retained_material_checks_total"]==40 and row["physical_global_conservation_credit"] is False and row["field_solver_executed"] is False and all(row[k]==v for k,v in required["positive"][name].items())):raise ValueError("Invalid ECM GRN history credit")
        case=path.parent.name.removeprefix("isolated-");prep=base/("preparation-"+case)
        references(prep/"cold",True)
        for index in range(3):references(prep/("point-"+str(index)))
        reports.append(dict(path=name,**row))
    raw={str(p.relative_to(base)):p for p in base.glob("isolated-*/raw-retention.json")}
    if set(raw)!=set(required["raw"]):raise ValueError("Exact ECM raw report set differs")
    for name,path in sorted(raw.items()):
        row=json.loads(path.read_text());case=path.parent.name.removeprefix("isolated-")
        cold=case.startswith("cold_");expected="KeyError" if cold else "BetseSimUnstableException"
        completed=0 if cold or case=="first_environment_negative" else 1
        if not(row["source_refused"] is True and row["source_type"]==expected and row["cold_initialization_failure"]==cold and row["exact_native_partial"] is True and row["partial_ecm_state_preserved"] is True and row["completed_transports"]==completed and row["positive_credit"] is False and row["physical_conservation_credit"] is False):raise ValueError("Invalid ECM partial failure")
        reports.append(dict(path=name,**row))
    if group=="dependencies":
        names=[n.split("[",1)[1][:-1] for n in inputs["groups"][group]]
        found={p.name:p for p in base.glob("dependency-*.json")}
        if set(found)!={"dependency-"+n+".json" for n in names}:raise ValueError("Exact ECM dependency report set differs")
        for name in names:
            row=json.loads(found["dependency-"+name+".json"].read_text())
            if not(row["baseline_admitted"] is True and row["intended_failure_reached"] is True and row["actual_leaf_type"]=="ValueError" and row["actual_message"]==row["expected_message"] and row["source_failure_credit"] is False):raise ValueError("Invalid ECM dependency witness")
            reports.append(dict(path="dependency-"+name+".json",**row))
    return reports

"""
    + runner[end:]
)
runner = runner.replace(
    "genuine_standalone_GRN_orchestration=True,",
    "genuine_normal_ECM_GRN_orchestration=True,\n                retained_ECM_material_panel_accepted=False,",
).replace("standalone_sim_grn=True,", "standalone_sim_grn=False,")
with (ROOT / (WORK + "betse_ecm_grn_checks.py")).open("x") as f:
    f.write(runner)
print(
    json.dumps(
        dict(
            owned=9,
            protected=len(protected),
            planned=planned,
            scientific_imports=0,
            numerical_runs=0,
        )
    )
)
