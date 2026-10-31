# ruff: noqa: E501 -- explicit source contract strings.
"""Freeze planning metadata; no fixture imports, collection or computation."""

import copy
import hashlib
import json
from pathlib import Path

ROOT = Path("/home/robert/Cells")
WORK = ROOT / "agent-work/cells-worker-01/workfiles"
PREFIX = "betse_normal_ecm_calcium_join"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    with Path(path).open("x") as f:
        json.dump(value, f, indent=2, sort_keys=True, allow_nan=False)
        f.write("\n")


field = json.loads(
    (ROOT / "validation/betse/betse_normal_ecm_field_join_protocol.json").read_text()
)
field_queue = json.loads((WORK / "betse_normal_ecm_field_join_workqueue.json").read_text())
evidence = copy.deepcopy(field["binding_evidence"])


def bind(name, path, expected=None):
    actual = sha(path)
    if expected is not None:
        assert actual == expected, name
    evidence[name] = dict(path=str(path), sha256=actual)


bind(
    "frozen_field01_inputs",
    "/mnt/workspaces/Cells/betse-normal-ecm-field-join-prepared-20261031-01/inputs.json",
    "0c4b575619efdad36239c28642014ef0b521e436304cd9d6591a43cc1fae2abb",
)
bind(
    "field01_static_receipt",
    WORK / "betse_normal_ecm_field_join_static_receipt_01.json",
    "c8ef54bc4437adc04d5d691724ca04b26a9fc548b3d947682d3719067f1d126a",
)
bind(
    "whole_native_calcium_policy",
    WORK / f"{PREFIX}_reachability_01.json",
    "733da3737e98e189e33d6b5b140c9dea7b0f90e6930a8b2406f7995e98611b5c",
)
bind(
    "calcium_and_clock_AST",
    WORK / f"{PREFIX}_AST_witness_02.json",
    "83f388961651dff5cf90ebf748b906ac9d2be71597ca173eb3226ae463e1b4c9",
)
calcium_queue = json.loads((WORK / "betse_normal_calcium_join_workqueue.json").read_text())
bind("retained_calcium04_inputs", calcium_queue["prepared_inputs"])
bind(
    "retained_CaATP20_review",
    "/mnt/workspaces/Cells/betse-normal-calcium-tests-20261030-02/root-review-01/REVIEW.json",
    "b9781ad497d00da81041a43f809a5b9ff833e128147d2ef115fe2831799f7f4e",
)
bind(
    "retained_calcium_raw4",
    "/mnt/workspaces/Cells/betse-normal-calcium-raw-subset-tests-20261030-01/worker-review-01/completion-verification.json",
    "dd1d0c1b9a9746e8e16686143a0c89cdaa1610a42094fd54272a1208de1fac8b",
)
bind(
    "failed_literal_ER_review",
    "/mnt/workspaces/Cells/betse-normal-er-tests-20261030-02/root-review-01/REVIEW.json",
    "7ae9c06aebd41b5ac59bc63412eabeee193084aa1ab1ea4d0a7a9cc893e01656",
)
bind(
    "separate_supplied_ER_review",
    "/mnt/workspaces/Cells/betse-prepared-er-tests-20261030-02/root-review-01/REVIEW.json",
    "a946f94703c1e860d444a5f98e591fe53c7e35379ea6233bc03914799def1334",
)
planned = dict(
    checks=34,
    positive_three_call_histories=16,
    new_ECM_CaATP_histories=12,
    component_control_histories=4,
    raw_partial_limits=6,
    dependency_controls=12,
    native_captures=22,
    independent_cold_points=16,
    actual_bootstrap_field_points=16,
    actual_pre_material_points=48,
    actual_pre_calcium_points=48,
    actual_pre_network_points=48,
    actual_end_field_points=48,
    fresh_cold_Decimal_forms=32,
    fresh_bootstrap_field_Decimal_forms=32,
    fresh_material_Decimal_forms=96,
    fresh_calcium_Decimal_forms=96,
    fresh_network_Decimal_forms=96,
    fresh_end_field_Decimal_forms=96,
    fresh_Decimal_reference_forms=448,
    carried_reference_forms=0,
    positive_native_Ca_handler_calls_per_implementation=48,
    positive_active_CaATP_helper_calls_per_implementation=45,
    completed_positive_mover_invocations_per_implementation=96,
    enabled_ER_calls=0,
    biological_cases=0,
)
protocol = copy.deepcopy(field)
protocol.update(
    kind="cells.normal_ecm_calcium_field_static_contract@1",
    law_id="betse_normal_ecm_calcium_field_join_v1_5_0@1",
    status="static_unqualified_no_numerics",
    purpose="Reachable native ECM CaATP after ordinary ion refresh and before GRN, with evolving full current/environment/voltage fields; preserve actual disabled-ER policy",
    source_map="validation/betse/" + PREFIX + "_source_map.json",
    planned=planned,
    binding_evidence=evidence,
)
protocol["scope"].update(
    source_order="Actual prepared normal SIM source clock; bootstrap update_V; ordinary ion refresh; guarded ca_handler(CaATP, Ca_dynFalse); explicit late-flux seam; GRN; deferred ordinary commit; full fields/update_V; NaN-only check_v",
    calcium="Real Ca+2 material/cache/diffusion role. Native CaATP_block ones, rho_pump1, met_concsNone, maintained ATP1.5/ADP0.1/Pi0.1, KmCa_Ca1e-3/KmCa_ATP0.5, deltaGATP-37000/F96485/R8.314 derive from actual original producers. Explicit configured alpha_Ca; no supplied pool/Km/block/rate defaults",
    rate_cache="Native rate_CaATP has no cold producer. Carry actual absence until a positive configured-alpha call writes masked post-first-rho handler flux, then carry immutable complete rate. Alpha0 keeps absence in this fixed-configuration normal phase; no fabricated zeros",
    clocks="Constant dt within three normal calls. Actual original SIM _plot_loop gives N3, linspace(0,N*dt,N); pass that t to original ordinary and GRN calls. Keep accumulated material dt separately, with configured p.T distinct from runtime sim.T. Event/sampling/persistence/whole phase clock lifecycle excluded",
    ER="Whole332-file installed-exact audit: sole Ca_dyn writerFalse at Parameters771; all8 legacy ER kinetics lack producers. Native guarded constructor/update remain disabled. Existing prepared_ER is a separate externally supplied inventory/cache seam, never ordinary cold/restart parity",
)
protocol["admission"].update(
    source_ER_disabled=True,
    ER_kinetics_or_pool_overrides_refused=True,
    native_rate_presence_bound_to_prior_positive_source_calls=True,
    source_clock_immutable_and_matched_to_step=True,
)
protocol["declared_cases"].update(
    recipe="New Ca+2 row, declared Ca diffusion and nominally neutral P=Na+K+2Ca-Cl initial and external boundary recipes; fixed macro dt/cm/gene scale inherited before any execution",
    CaATP_configured_alpha=1e-6,
    negative_environment_case="Explicit signed post-cache live grid and warm external reservoir; finite nonnegative separately declared initializer cache and cold GRN reservoir. Mapped helper clipping never rewrites grid",
    no_CaATP_control="Configured alpha0, actual rate-cache absence through all calls",
)
protocol["acceptance"].update(
    primary="Exact full original CaATP helper arithmetic and native caller membrane-copy/mask/rate/cache state; source/port full material/GRN/field arrays and actual clock/owned caches",
    independent="Fresh Decimal100/160 from actual cold/bootstrap/pre-material/pre-CaATP/pre-GRN/end-field snapshots; ordinary scalar material reference now includes independent CaATP at the real boundary. Full lower/target/actual/error/budget buffers; no independent carried trajectory",
    calcium_flux="Existing pump_loop_preflight2e-18 mol/m2/s +2e-11*abs(reference), including masked rate and applied density; no changed budget",
    calcium_arithmetic="2e-14 named-unit floor +2e-11*abs(reference); zero-product branch uses original stored binary64 product and literal1e-16 replacement. Before/after material buffers use unchanged typed ECM budgets",
    clock="Exact native/port N3 vector and step/cache timing; independent cold reference uses explicit binary64 end/delta store seams",
    native_ER_accuracy_claim=False,
)
protocol["acceptance"]["inherited_budget_source_sha256"].update(
    {
        "validation/betse/pump_loop_preflight/protocol.json": sha(
            ROOT / "validation/betse/pump_loop_preflight/protocol.json"
        ),
        "validation/betse/betse_normal_calcium_join_protocol.json": sha(
            ROOT / "validation/betse/betse_normal_calcium_join_protocol.json"
        ),
    }
)
protocol["accounting"].update(
    calcium="CaATP density adds to ordinary Ca membrane flux, committed only where Ca is moving. Stationary-Ca stored flux, directed GJ/deferred shell/cache, fast duplicate-last exchange and all legacy ledgers remain literal",
    maintained_pools="ATP/ADP/Pi are original fixed maintained parameters. No formal ATP use, finite shared fuel, ER reservoir, buffer or thermodynamic global closure is asserted",
    formal_ATP_consumption_claim=False,
    enabled_ER_conservation_claim=False,
)
protocol["failures"] = dict(
    raw=[
        "first/second gene negative after returned CaATP",
        "initial and late field-driven CaATP equilibrium underflow with moving ions disabled by explicit declaration",
        "zero-screen bootstrap strict field refusal",
        "finite configured alpha1e308 with raw later nonfinite material/source outputs",
    ],
    retention="Full native raw snapshots, Ca helper before/after/local arithmetic and rate aliases, all available port partials/working arrays/ledgers, immutable parent, clock and tracebacks. Strict finite guard differs from native exception; source may return nonfinite buffers before later error",
    positive_credit=False,
    source_ER_disabled=True,
)
protocol["source_defects_preserved"] += [
    "ECM mapped environment fancy-index copy clips separately from live membrane view",
    "rho_pump twice; rate aliases masked handler local after first density multiplication, distinct from original helper return array",
    "No cold rate_CaATP writer; configured alpha0 never fabricates a cache",
    "Maintained CaATP pools, denominator-zero replacement and unused backward arithmetic",
    "Disabled ordinary native ER and missing kinetic producers; failed literal ER and external prepared_ER scope remain distinct",
    "Normal np.linspace clock starts t0 while first material call advances dt",
]
write(ROOT / "validation/betse" / f"{PREFIX}_protocol.json", protocol)
proof = json.loads((WORK / f"{PREFIX}_AST_witness_02.json").read_text())
mapping = dict(
    proof,
    kind="cells.normal_ecm_CaATP_field_source_map@1",
    law_id=protocol["law_id"],
    native_source_sha256=protocol["native_source"]["source_sha256"],
    scope=protocol["scope"],
)
write(ROOT / "validation/betse" / f"{PREFIX}_source_map.json", mapping)
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
        "BETSE_NORMAL_ECM_CALCIUM_JOIN_NOTES.md",
        "betse_mito_grn_reachability_audit.py",
        "betse_normal_grn_join_static_audit.py",
        "betse_normal_network_join_checks_02.py",
    )
]
queue = {
    k: field_queue[k]
    for k in (
        "authorized_physical_helper_refactor",
        "coordinated_shared_edit_paths",
        "coordinated_unrelated_physics_edits",
        "automatic_launch",
        "automatic_polling",
        "automatic_followup",
    )
    if k in field_queue
}
queue.update(
    kind="cells.normal_ecm_CaATP_field_workqueue@1",
    status="ready_for_static_audits",
    owned=owned,
    owned_sha256={p: sha(ROOT / p) for p in owned},
    protected_sha256={},
    binding_evidence=evidence,
    planned=planned,
    workfiles=workfiles,
    runner=str((WORK / f"{PREFIX}_checks.py").relative_to(ROOT)),
    notes=str((WORK / "BETSE_NORMAL_ECM_CALCIUM_JOIN_NOTES.md").relative_to(ROOT)),
    source_ER_disabled=True,
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
            status="static_CaATP_contracts_prepared",
            owned=7,
            binding_evidence=len(evidence),
            planned=planned,
        )
    )
)
