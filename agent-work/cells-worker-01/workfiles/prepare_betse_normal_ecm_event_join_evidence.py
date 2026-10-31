# ruff: noqa: E501
"""Exclusive event protocol/map/workqueue source preparation, stdlib only."""

import ast
import copy
import hashlib
import json
from pathlib import Path

ROOT = Path("/home/robert/Cells")
WORK = ROOT / "agent-work/cells-worker-01/workfiles"
PREFIX = "betse_normal_ecm_event_join"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    if path.is_file():
        assert json.loads(path.read_text()) == json.loads(json.dumps(value)), path
        return
    with path.open("x") as stream:
        json.dump(value, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")


old = json.loads(
    (ROOT / "validation/betse/betse_normal_ecm_catalog_join_protocol.json").read_text()
)
oldq = json.loads((WORK / "betse_normal_ecm_catalog_join_workqueue.json").read_text())
reach = json.loads((WORK / (PREFIX + "_reachability_01.json")).read_text())
proof = json.loads((WORK / (PREFIX + "_AST_witness_02.json")).read_text())
dep = json.loads((WORK / (PREFIX + "_dependency_witness_01.json")).read_text())
fixture = ast.parse((ROOT / "validation/betse" / (PREFIX + "_fixtures.py")).read_text())
constants = {
    t.id: ast.literal_eval(n.value)
    for n in fixture.body
    if isinstance(n, ast.Assign)
    for t in n.targets
    if isinstance(t, ast.Name)
    and t.id in ("CASES", "COMPONENT_CONTROLS", "RAW_CASES", "DEPENDENCIES")
}
assert [
    len(constants[k]) for k in ("CASES", "COMPONENT_CONTROLS", "RAW_CASES", "DEPENDENCIES")
] == [20, 6, 6, 16]
planned = dict(
    checks=42,
    positive_histories=20,
    new_event_histories=14,
    component_control_histories=6,
    raw_partial_limits=6,
    dependency_controls=16,
    native_captures=26,
    source_clock_N=3,
    three_call_context_histories=20,
    positive_normal_calls_per_implementation=60,
    independent_cold_points=20,
    actual_bootstrap_field_points=20,
    fresh_cold_Decimal_forms=40,
    fresh_bootstrap_field_Decimal_forms=40,
    fresh_Decimal_reference_forms=920,
    carried_reference_forms=0,
    enabled_ER_calls=0,
    biological_cases=0,
)
for name in ("event", "material", "calcium", "channel", "network", "noise", "end_field"):
    planned["actual_" + name + "_conditional_points"] = 60
    planned["fresh_" + name + "_Decimal_forms"] = 120
scope = dict(
    supplied_entry="Explicit supplied post-finalization tissue/callback owners, fixed declared geometry and complete local MT state/cache presence. No native profile selection, mesh, seed history, whole cold initialization or restart reconstruction.",
    source_order="One real reset, SIM events(global K/Cl/Na salts,T,GJ,NaK; tissue Na/K/Cl/Ca,pressure,ECM junctions,voltage;makeAllChanges); ordinary ion work;CaATP;catalog/GRN;dynamic protein noise;ordinary commit;full fields/check_v.",
    clocks="Original N3 linspace(0,3dt,3) labels are distinct from accumulated configured dt. Dense events/noise do not depend on sampling.",
    persistent="Complete source live diffusion/base/scheduled/molecular-weight,pressure,bath,T,GJ/NaK/rho/boundary owners carried. Restore prior GRN then reapply actual earlier event stores. Preserve scalar controls and duplicate-last writes.",
    lowering="New composition owns legitimate per-step material.bind from unchanged baseline except current Dm_cells/D_env; lower actual post-event values with real component identity and identical fixed geometry. No old binding forgery or checkpoint migration.",
    noise="Original SIM/dynamic==1/P guard, one full M-uniform vector even t0/level0, after GRN before commit. Explicit local complete MT19937/version/Gaussian cache; no ambient mutation or Brownian scaling. Disabled preserves cache and consumes none.",
    prospective="Independent full material input may include an uncommitted cloned incoming-stream preview; actual sampling remains after successful GRN and must match it. A failed GRN cannot consume the actual stream.",
    callbacks="Supplied scalar/full-axis spatial returns and original constant/periodic/explicit-slope sweep. No guessed spatial constructor history, missing profile, bitmap or cut/remesh lifecycle. Literal length/duplicate assignment defects retained.",
    salt="Explicit manufactured complete M-1 ion row and reservoir, not a renamed Cl/P or native default. Later Cl/Na salt boundary assignments override earlier shared entries.",
    voltage="Positive then negative edge assignment; same edge retains latter. Untargeted edges persist. Actual events feed full field stage.",
    calcium=old["scope"]["calcium"],
    channels=old["scope"]["channels"],
    cache=old["scope"]["cache"],
    field_state=old["scope"]["field_state"],
    limits="20 supplied three-call contexts,6 raw limits,16 dependency controls; existing catalog55 class laws are inherited, not a new all-class event panel. Fresh100/160 conditionals only; no independent carried trajectory or biological claim.",
    exclusions=[
        "Native mesh/profile/RNG initialization and full SimRunner/phase lifecycle equivalence",
        "Cuts/remeshing/bitmap reconstruction, fluid mechanics/force/deformation coupling (pressure writes retained only)",
        "Enabled ER/mitochondria, broader transporters/legacy channels, physical thermodynamics/energy/ATP closure",
        "JAX/GPU/stable-owner RNG equivalence and biological calibration",
    ],
)
native = copy.deepcopy(old["native_source"])
for name in (
    "betse/science/math/modulate.py",
    "betse/science/math/toolbox.py",
    "betse/science/tissue/tishandler.py",
    "betse/science/tissue/event/tisevevolt.py",
):
    native["source_sha256"][name] = reach["original_source_sha256"][name]
acceptance = copy.deepcopy(old["acceptance"])
for name in (
    "validation/topology/betse_tissue_profiles_protocol.json",
    "validation/perturbations/betse_perturbations_protocol.json",
    "tests/unit/test_betse_global_controls.py",
    "tests/unit/test_betse_time_modulation.py",
):
    acceptance["inherited_budget_source_sha256"][name] = sha(ROOT / name)
acceptance.update(
    independent="Fresh Decimal100/160 actual cold/bootstrap/events/post-events-material/pre-CaATP/pre-channels/post-channels-pre-GRN/pre-noise/end-field. Full material inserts direct noise before ordinary commit and retains separate books. No independently carried trajectory.",
    events="Exact native full stores/stages/reset and unchanged global64eps*max(1,abs), tissue5e-12 relative with Dm1e-30,Denv1e-21,factor3e-14,pressure3e-13; salts use existing concentration2e-14+5e-13 relative.",
    noise="Exact original draws,streams,source buffers/cache epochs; independent protein concentration2e-14+5e-13*abs and flux1e-23+5e-13*abs. Separate source-effective/conservative/true-grid books use unchanged ECM3e-14+6e-12*abs amount budget. No conservation acceptance credit.",
    metadata="Before-material callback clones the exact original incoming packet after unchanged Drive validation; array coercion never replaces actual declaration metadata.",
)
accounting = copy.deepcopy(old["accounting"])
accounting.update(
    noise="Direct post-GRN protein update changes bulk,membrane,ECM without ordinary flux storage or clipping. Source-effective uniform-site,conservative area-sum and true-grid volume books separate; fast last-duplicate defect retained. If P moves ordinary later commit/clipping/shell semantics remain source.",
    material_ledgers="Legacy ledgers remain literal; direct-channel and noise amounts appear in ordinary residuals. Full independent material predicts source residuals; no silent subtraction.",
    pressure="Source P_mod/P_cells writes retained without a mechanics or energy claim.",
)
binding = copy.deepcopy(oldq["binding_evidence"])
for name, path in (
    ("event_reachability", WORK / (PREFIX + "_reachability_01.json")),
    ("event_source_AST", WORK / (PREFIX + "_AST_witness_02.json")),
    ("event_explicit03_dependency_refresh", WORK / (PREFIX + "_dependency_witness_01.json")),
    ("event_bounded_metadata_check", WORK / (PREFIX + "_reporting_metadata_check_01.json")),
    ("Chief03_callback_preparation", Path(dep["preparation"]["path"])),
):
    binding[name] = dict(path=str(path), sha256=sha(path))
for family, row in dep["successors"].items():
    binding[family + "03_callback_inputs"] = dict(path=row["inputs"], sha256=row["sha256"])
protocol = dict(
    kind="cells.normal_ecm_event_join_contract@1",
    law_id="betse_normal_ecm_event_catalog_CaATP_field_join_v1_5_0@1",
    status="static_preparation_no_numerics_pending_Chief03_review",
    purpose="Resolve source scheduled-event order, persistent live coefficient owners, scalar control shapes and post-GRN noise/RNG epochs at the ordinary ECM catalog boundary before a new numerical claim.",
    native_source=native,
    planned=planned,
    declared_cases=constants,
    scope=scope,
    acceptance=acceptance,
    catalog_budgets=old["catalog_budgets"],
    accounting=accounting,
    resources=old["resources"],
    binding_evidence=binding,
    admission=dict(
        source_ER_disabled=True,
        supplied_geometry_tissue_callback_owners=True,
        full_MT_state_and_cache_presence=True,
        competing_step_overrides_refused=True,
        source_original_normal_calendar=True,
        owned_parent_and_prior_field_required=True,
        live_coefficient_lowering_preserves_geometry=True,
    ),
    source_defects_preserved=reach["source_defects_preserved"],
    retained_ecm_limit=old["retained_ecm_limit"],
    failures=dict(
        source_native_and_strict_port_distinct=True,
        complete_raw_buffers_and_partials=True,
        late_failures_keep_prior_completed_steps=True,
        unknown_huge_noise_limit_retained_without_outcome_tuning=True,
    ),
    source_map="validation/betse/" + PREFIX + "_source_map.json",
    automatic_launch=False,
    automatic_polling=False,
    automatic_followup=False,
)
write(ROOT / "validation/betse" / (PREFIX + "_protocol.json"), protocol)
mapping = dict(
    proof,
    kind="cells.normal_ecm_event_join_source_map@1",
    law_id=protocol["law_id"],
    native_source_sha256=native["source_sha256"],
    whole_installed_exact_python_files=332,
    scope=scope,
    source_clock_N3_and_dt_distinct=True,
    new_scientific_source_files=3,
    inherited_catalog_network_bodies=47,
    inherited_CaATP_functions=3,
    inherited_field_functions=10,
    enabled_ER_calls=0,
    source_er_disabled=True,
)
write(ROOT / "validation/betse" / (PREFIX + "_source_map.json"), mapping)
owned = [
    str(p.relative_to(ROOT))
    for folder in ("src/cells/processes", "validation/betse", "tests/unit")
    for p in sorted((ROOT / folder).glob(("*" if folder == "tests/unit" else "") + PREFIX + "*"))
    if p.is_file()
]
assert len(owned) == 10, owned
protected = dict(json.loads(Path(dep["prior_inputs"]).read_text())["owned_sha256"])
protected.update(json.loads(Path(dep["prior_inputs"]).read_text())["protected_sha256"])
for path, row in dep["changes"].items():
    protected[path] = row["new_sha256"]
workfiles = [str(p.relative_to(ROOT)) for p in sorted(WORK.glob("*" + PREFIX + "*")) if p.is_file()]
workfiles += [
    "agent-work/cells-worker-01/workfiles/BETSE_NORMAL_ECM_EVENT_JOIN_NOTES.md",
    "agent-work/cells-worker-01/workfiles/betse_normal_grn_join_static_audit.py",
]
queue = dict(
    kind="cells.normal_ecm_event_join_workqueue@1",
    status=protocol["status"],
    owned=owned,
    owned_sha256={p: sha(ROOT / p) for p in owned},
    protected_sha256=protected,
    workfiles=workfiles,
    runner="agent-work/cells-worker-01/workfiles/" + PREFIX + "_checks.py",
    planned=planned,
    binding_evidence=binding,
    explicit_dependency_refresh=dep,
    freeze_prerequisites=dict(Chief03_source_review=None),
    authorized_physical_helper_refactor=oldq["authorized_physical_helper_refactor"],
    coordinated_shared_edit_paths=oldq["coordinated_shared_edit_paths"],
    notes=[
        "Own prefix; all failed/frozen evidence and active jobs untouched",
        "No fixture generation,evaluation,scientific imports,collection,numerical run or job query",
        "Chief owns independent review and any later explicitly requested numerical round",
    ],
    scientific_imports=0,
    scientific_AST_executions=0,
    fixture_evaluations=0,
    pytest_collection_runs=0,
    numerical_runs=0,
    enabled_ER_calls=0,
    automatic_launch=False,
    automatic_polling=False,
    automatic_followup=False,
    active_numerical_job=None,
)
write(WORK / (PREFIX + "_workqueue.json"), queue)
print(
    json.dumps(
        dict(
            status=protocol["status"], owned=len(owned), protected=len(protected), planned=planned
        ),
        sort_keys=True,
    )
)
