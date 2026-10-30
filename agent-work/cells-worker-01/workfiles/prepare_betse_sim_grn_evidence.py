# ruff: noqa: E501 -- frozen protocol and emitted runner templates.
"""Prepare standalone ownership, protocol and runner without scientific imports."""

import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path("/home/robert/Cells")
WORK = "agent-work/cells-worker-01/workfiles/"
PREFIX = "betse_sim_grn"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(relative, value):
    with (ROOT / relative).open("x") as stream:
        json.dump(value, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")


previous = json.loads((ROOT / (WORK + "betse_normal_charged_grn_join_workqueue.json")).read_text())
neutral = json.loads((ROOT / (WORK + "betse_normal_grn_join_workqueue.json")).read_text())
old_protocol = json.loads(
    (ROOT / "validation/betse/betse_normal_grn_join_protocol.json").read_text()
)
evidence = dict(previous["binding_evidence"])
review = Path("/mnt/workspaces/Cells/betse-normal-grn-tests-20261030-01/root-review-01/REVIEW.json")
assert sha(review) == "6cccb0a9c1c759f00de3bfb725f99ce97eb05f1904d4a7a6e4ccc37620bbff31"
evidence.update(
    accepted_neutral_grn_review=dict(path=str(review), sha256=sha(review)),
    protected_charged02_inputs=dict(
        path=previous["prepared_inputs"], sha256=previous["prepared_inputs_sha256"]
    ),
    protected_charged02_receipt=dict(
        path=str(ROOT / previous["static_receipt"]), sha256=previous["static_receipt_sha256"]
    ),
)
native = dict(old_protocol["native_source"])
native["source_sha256"] = dict(native["source_sha256"])
native["source_sha256"]["betse/science/simrunner.py"] = sha(
    Path(native["checkout"]) / "betse/science/simrunner.py"
)
planned = dict(
    checks=22,
    positive_two_invocation_histories=10,
    new_standalone_histories=7,
    component_control_histories=3,
    positive_standalone_invocations=20,
    actual_pre_core_points=65,
    independent_cold_points=10,
    independent_clock_points=20,
    fresh_warm_Decimal_forms=130,
    fresh_cold_Decimal_forms=20,
    fresh_clock_Decimal_forms=40,
    fresh_Decimal_reference_forms=190,
    carried_reference_forms=0,
    raw_partial_failures=5,
    dependency_controls=7,
    native_captures=15,
    completed_positive_mover_invocations_per_implementation=130,
    biological_cases=0,
)
protocol = dict(
    kind="cells.native_standalone_sim_grn_static_contract@1",
    law_id="betse_standalone_sim_grn_v1_5_0@1",
    status="static_unqualified_no_numerics",
    purpose="Entire original standalone run_core_sim orchestration at an explicit supplied-phase boundary with cold and advancing repeated-invocation capture",
    source_map="validation/betse/betse_sim_grn_source_map.json",
    native_source=native,
    resources=old_protocol["resources"],
    binding_evidence=evidence,
    planned=planned,
    scope=dict(
        supplied_phase="Explicit initialized no-ECM three-cell/nine-membrane/five-ion phase; no world loading, init_core, init_dynamics/profile generation or full SimRunner parity claim",
        cold="Original SimRunner.sim_grn new-owner true-branch constructs actual local MasterOfGenes and calls read_gene_config; owner remains local rather than a normal-solver GRN label",
        run="Entire original MasterOfGenes.run_core_sim, actual reinitialize, clear_cache, Core/Molecule scientific bodies, write_data/report, init_saving and CSV export bodies",
        state="All public owner/Core/Molecule/reaction/modulator fields, complete simulator and parameter state, boundary values, sample caches and captured output texts persist between invocations through explicit hydration; native retains actual live objects",
        source_order="Force charge publication False; overwrite standalone clocks; construct linspace/sampling; reinitialize without resetting concentrations; clear sampled caches; reset owner time; actual Core loop; sample/report; save boundary; init_saving; export_eval_strings; export_equations",
        distinctions="No per-step clear_run_loop, channel or configured modulator dispatch. Configured ion modulators remain present but unused; source controls and charge/current publications persist. Vm/Vgj change only through original molecular mover nonces",
        clock="N=int(total/dt), linspace(0,N*dt,N); first t0 advances dt. Timestamp spacing is N*dt/(N-1), except N1 only t0. Sampling repeatedly truncates i+t_resample; owner time/cache resets while sim.time appends across invocations",
        IO="Original init_saving and CSV exporter bodies execute against explicit in-memory directory/file sinks; saveSim records argument identities and complete scientific state. No pickle/filesystem-persistence credit",
        exclusions=[
            "SEED/INIT/SIM file loading, automatic seeding/initialization, actual pickle restart or file persistence",
            "Mitochondrial/ECM spatial state, fluid/cut/event dynamics, optimizers, transporters/channels, charged cold counterion initialization",
            "Normal material/pump/gate/current/voltage solver dispatch",
            "Physical global or energetic conservation, finite/shared fuel, biological calibration or independently carried trajectory accuracy",
        ],
    ),
    acceptance=dict(
        primary="Exact native cold/full public state, all orchestration/per-core/mover/chemistry frames, full repeated-invocation caches/clocks/samples/boundary/parameters, original output call order and CSV text, original partial exceptions",
        independent="Fresh Decimal90/140 cold configuration, explicit independent binary64 clock specification with Decimal count of dt advanced, and independent local GAD/reaction/mover equations before each outgoing Core call; zero carried reference forms",
        inherited_budget_source_sha256=old_protocol["acceptance"]["inherited_budget_source_sha256"],
        warm_material=old_protocol["acceptance"]["molecule_material"],
        reaction_rates=old_protocol["acceptance"]["reaction_rates"],
        amount="factor*(abs(reference_initial)+abs(reference_final)+abs(reference_chemical)+abs(reference_directed_GJ)) + unchanged concentration floors times input volume; factor128*eps*(ions+2+cells+membranes+64)",
        cold="Exact source/default fields and independently built matrix/publication writes; unchanged concentration floors and1e-25 exact-assignment envelope",
        clock="Exact independent binary64 timestamps/sample indices plus exact captured original parameter rewrites; timestamps and dt advancement reported separately",
        self_resolution_fraction=0.1,
        no_outcome_tuning=True,
        dependency="Every dependency first admits a valid cold baseline then reaches exact terminal ValueError reason; no source failure credit",
    ),
    accounting=dict(
        old_protocol["accounting"],
        standalone="No ordinary ion evolution or physical publication solve; source forces publication off and retains simulator fields. Explicit concentration/count/source ledgers stay conditional and local",
        physical_global_conservation_credit=False,
        energetic_conservation_credit=False,
    ),
    blockers=dict(
        unsafe_sampling="sample<dt can stall the original int(i+t_resample) loop; require sample>=dt rather than alter native timing",
        unsupported_state="Mitochondria, ECM, fluid/cuts and file restarts require independent state/data boundaries; explicit dependency refusals retain these distinctions",
    ),
    failures=dict(
        raw=[
            "cold_missing_Y_Dm",
            "first_negative",
            "second_negative",
            "second_call_missing_Y_Dm",
            "late_plot_cell",
        ],
        retention="Exact native partial owner/ionic/boundary/clock/sample/default/output state and tracebacks; second-invocation reinitialize refusal precedes cache clear; invalid plot cell refuses after all three first-invocation Core steps and save/directory boundary",
        positive_credit=False,
    ),
    input_versus_execution=dict(
        supplied="Explicit phase dictionaries and native gene config",
        executed="Actual new-owner branch and full standalone source body; scientific equations unchanged",
        output_boundary="In-memory native CSV output and save-call observation only",
    ),
)
write("validation/betse/betse_sim_grn_protocol.json", protocol)
spec = importlib.util.spec_from_file_location(
    "standalone_AST", ROOT / (WORK + "betse_sim_grn_ast_audit.py")
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
proof = module.audit()
write(
    "validation/betse/betse_sim_grn_source_map.json",
    dict(
        kind="cells.standalone_sim_grn_source_map@1",
        law_id=protocol["law_id"],
        source_sha256=native["source_sha256"],
        scope=protocol["scope"],
        **proof,
    ),
)
protected = previous["protected_sha256"] | previous["owned_sha256"]
assert len(protected) == 255
queue = {
    key: value
    for key, value in previous.items()
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
owned = ["src/cells/processes/betse_sim_grn.py", "tests/unit/test_betse_sim_grn.py"] + [
    "validation/betse/betse_sim_grn_" + suffix
    for suffix in ("fixtures.py", "native.py", "reference.py", "protocol.json", "source_map.json")
]
queue.update(
    kind="cells.standalone_sim_grn_static_workqueue@1",
    status="ready_for_static_audits",
    owned=owned,
    protected_sha256=protected,
    binding_evidence=evidence,
    runner=WORK + "betse_sim_grn_checks.py",
    notes=WORK + "BETSE_SIM_GRN_NOTES.md",
    scientific_imports=0,
    scientific_AST_executions=0,
    numerical_runs=0,
    pytest_collection_runs=0,
    active_numerical_job=None,
    protected_but_not_imported_side_package_paths=previous["owned"]
    + [n for n in previous["protected_sha256"] if "betse_normal_transporter" in n],
    accepted_neutral_grn_dependency=True,
    workfiles=[
        WORK + name
        for name in (
            "betse_sim_grn_ast_audit.py",
            "betse_sim_grn_static_audit.py",
            "betse_sim_grn_checks.py",
            "prepare_betse_sim_grn.py",
            "prepare_betse_sim_grn_inputs.py",
            "prepare_betse_sim_grn_evidence.py",
            "sim_grn_adapter_template.txt",
            "BETSE_SIM_GRN_NOTES.md",
            "record_static_freeze_receipt.py",
        )
    ],
)
queue["owned_sha256"] = {name: sha(ROOT / name) for name in owned}
write(WORK + "betse_sim_grn_workqueue.json", queue)
runner = (ROOT / (WORK + "betse_normal_charged_grn_join_checks.py")).read_text()
runner = (
    runner.replace("betse_normal_charged_grn_join", "betse_sim_grn")
    .replace("normal-charged-grn-join", "sim-grn")
    .replace("CELLS_CHARGED_GRN_JOIN_CPU", "CELLS_SIM_GRN_CPU")
)
runner = (
    runner.replace(
        "test_charged_grn_owner_and_conditional_reference", "test_standalone_grn_advancing_history"
    )
    .replace("test_charged_grn_partial_failure", "test_standalone_grn_partial_failure")
    .replace("test_complete_charged_grn_dependencies", "test_standalone_grn_dependencies")
)
start = runner.index("        core = {")
end = runner.index('        for case in constants["CASES"]:', start)
runner = (
    runner[:start]
    + '        core = {"standard","fractional_sampling","time_dilation"}\n'
    + runner[end:]
)
runner = runner.replace('"new_charged_grn_case"', '"new_standalone_grn_case"').replace(
    "                executed_chemistry=True,",
    '                actual_core_calls=2 if case=="single_step" else 7,',
)
runner = runner.replace("== 16\n", "== 15\n").replace(
    "native_source_copies=42", "native_source_copies=44"
)
runner = runner.replace(
    "cells.normal_charged_grn_prepared@1", "cells.standalone_sim_grn_prepared@1"
)
start = runner.index("def molecule_reports(")
end = runner.index("\ndef run(", start)
runner = (
    runner[:start]
    + """def molecule_reports(target,group,inputs):
    base=target/"evidence/sim-grn"
    required=inputs["required_reports"][group]
    found={str(p.relative_to(base)):p for p in base.glob("isolated-*/comparison.json")}
    if set(found)!=set(required["positive"]):
        raise ValueError("Exact standalone positive report set differs")
    reports=[]
    def forms(folder,mode=None):
        answers=[]
        for level in (1,2):
            answer=json.loads((folder/("reference-"+str(level)+".json")).read_text())
            if not(answer["production_imports_denied"] and not answer["loaded_production_modules"] and answer["carried_reference_forms"]==0 and answer["decimal_precision"]==(90 if level==1 else 140)):
                raise ValueError("Missing independent standalone reference form")
            if mode is not None and answer[mode] is not True:
                raise ValueError("Standalone reference mode differs")
            answers.append(answer)
        return answers
    def metrics(folder):
        comp=json.loads((folder/"comparison.json").read_text())
        if not(comp["fresh_conditional_reference"] is True and comp["physical_global_conservation_credit"] is False and comp["fields"] and all(0<=v["normalized_max_error"]<=1 for v in comp["fields"].values()) and all(0<=v["normalized_max_error"]<=0.1 for v in comp["resolutions"].values())):
            raise ValueError("Standalone independent error/budget comparison failed")
    for name,path in sorted(found.items()):
        row=json.loads(path.read_text())
        if not(row["completed"] is True and row["exact_native"] is True and row["standalone_run_core_sim"] is True and row["normal_solver_executed"] is False and row["advancing_invocations"]==2 and row["cold_reference_forms"]==2 and row["clock_reference_forms"]==4 and row["warm_reference_forms"]==2*row["actual_core_calls"] and row["carried_reference_forms"]==0 and row["complete_public_state_carry"] is True and row["real_reinitialize_and_cache_reset"] is True and row["force_publication_off"] is True and row["configured_modulators_dispatched"] is False and row["physical_global_conservation_credit"] is False and row["file_persistence_credit"] is False and all(row[k]==v for k,v in required["positive"][name].items())):
            raise ValueError("Incomplete standalone history")
        case=path.parent.name.removeprefix("isolated-")
        prep=base/("preparation-"+case)
        forms(prep/"cold","cold_initialization")
        metrics(prep/"cold")
        points=0
        for invocation in range(2):
            clock=prep/("clock-"+str(invocation))
            answer=forms(clock,"standalone_clock")[1]
            comp=json.loads((clock/"comparison.json").read_text())
            if not(comp["exact_native_clock"] is True and comp["independent_clock"] is True and comp["clock_reference_forms"]==2 and comp["steps"]==answer["steps"] and comp["physical_conservation_credit"] is False):
                raise ValueError("Standalone clock check failed")
            for point in range(answer["steps"]):
                local=prep/("call-"+str(invocation)+"-point-"+str(point))
                forms(local)
                metrics(local)
                points+=1
        if points!=row["actual_core_calls"]:
            raise ValueError("Standalone point count differs")
        reports.append(dict(path=name,**row))
    raw={str(p.relative_to(base)):p for p in base.glob("isolated-*/raw-retention.json")}
    if set(raw)!=set(required["raw"]):
        raise ValueError("Exact standalone raw report set differs")
    for name,path in sorted(raw.items()):
        row=json.loads(path.read_text())
        case=path.parent.name.removeprefix("isolated-")
        expected="KeyError" if case in ("cold_missing_Y_Dm","second_call_missing_Y_Dm") else "BetseSimConfException" if case=="late_plot_cell" else "BetseSimUnstableException"
        if not(row["source_refused"] is True and row["source_type"]==expected and row["intended_failure"]==case and row["partial_state_and_clock_preserved"] is True and row["exact_native_partial"] is True and row["positive_credit"] is False and row["physical_conservation_credit"] is False):
            raise ValueError("Invalid standalone partial-failure retention")
        reports.append(dict(path=name,**row))
    if group=="dependencies":
        names=[n.split("[",1)[1][:-1] for n in inputs["groups"][group]]
        found={p.name:p for p in base.glob("dependency-*.json")}
        if set(found)!={"dependency-"+n+".json" for n in names}:
            raise ValueError("Exact standalone dependency witness set differs")
        for name in names:
            row=json.loads(found["dependency-"+name+".json"].read_text())
            if not(row["baseline_admitted"] is True and row["intended_failure_reached"] is True and row["actual_leaf_type"]=="ValueError" and row["actual_message"]==row["expected_message"] and row["source_failure_credit"] is False):
                raise ValueError("Invalid standalone dependency witness")
            reports.append(dict(path="dependency-"+name+".json",**row))
    return reports

"""
    + runner[end:]
)
runner = runner.replace(
    "genuine_grn_owner_lifecycle_and_normal_dispatch=True,",
    "genuine_standalone_GRN_orchestration=True,\n                normal_solver_executed=False,\n                file_persistence_credit=False,",
).replace("standalone_sim_grn=False,", "standalone_sim_grn=True,")
with (ROOT / (WORK + "betse_sim_grn_checks.py")).open("x") as f:
    f.write(runner)
print(
    json.dumps(
        dict(owned=7, protected=255, planned=planned, scientific_imports=0, numerical_runs=0)
    )
)
