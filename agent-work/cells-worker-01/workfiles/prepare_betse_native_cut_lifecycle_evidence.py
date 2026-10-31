# ruff: noqa: E501
"""Exclusive protocol/map/queue writer; AST/JSON/hash only, no science."""

import ast
import hashlib
import json
from pathlib import Path

ROOT = Path("/home/robert/Cells")
WORK = ROOT / "agent-work/cells-worker-01/workfiles"
PREFIX = "betse_native_cut_lifecycle"
EVENT = Path("/mnt/workspaces/Cells/betse-normal-ecm-event-join-prepared-20261031-01")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    with path.open("x") as stream:
        json.dump(value, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")


reach = json.loads((WORK / (PREFIX + "_source_witness_01.json")).read_text())
proof = json.loads((WORK / (PREFIX + "_AST_witness_01.json")).read_text())
prior = json.loads((EVENT / "inputs.json").read_text())
old = json.loads((ROOT / "validation/topology/betse_tissue_cut_protocol.json").read_text())
assert (
    sha(EVENT / "inputs.json") == "569101232c058441830f794fd5209356027e4d609237d444ee637e676fa626c9"
)
fixture = ast.parse((ROOT / "validation/topology" / (PREFIX + "_fixtures.py")).read_text())
constants = {
    t.id: ast.literal_eval(n.value)
    for n in fixture.body
    if isinstance(n, ast.Assign)
    for t in n.targets
    if isinstance(t, ast.Name) and t.id in ("CASES", "RAW_CASES", "DEPENDENCIES")
}
assert [len(constants[k]) for k in ("CASES", "RAW_CASES", "DEPENDENCIES")] == [6, 8, 11]
native = dict(old["native_source"])
native["source_sha256"] = dict(native["source_sha256"])
name = "betse/science/tissue/picker/tispickcls.py"
native["source_sha256"][name] = reach["original_source_sha256"][name]
native["scope"] = (
    "Original pre-mesh prefix and flatten only execute in deferred capture. Whole lifecycle methods are AST/capability evidence. Supplied picker returns, source data carriers and no geometry creation/solver calls; no native constructor or full cut claim."
)
planned = dict(
    checks=25,
    prefix_conditions=6,
    raw_limits=8,
    dependency_controls=11,
    native_captures=14,
    fresh_independent_reference_forms=6,
    existing_quantity_precision=80,
    carried_reference_forms=0,
    geometry_calls=0,
    complete_native_cuts=0,
    physical_mesh_cases=0,
    ordinary_resumes=0,
    biological_cases=0,
)
scope = dict(
    prefix="Literal first32 original _cut_cells statements including its docstring, normalized doc/type decorators only, plus return-locals observation. Stop before line1153 DEC cut. Actual ordinary is_ecmTrue/Ca_dynFalse prerequisites; never force source flags.",
    owner="Qualified existing explicit stable CutPlan/OwnedField removal/quantity sink ledger runs separately from native length heuristics. Its after-topology is a conservative owner target, never inferred regenerated native geometry.",
    selection="Both supplied picker target arrays and cell-to-membrane occurrence map are explicit. Preserve selected-cell and membrane occurrence order. Typed empty arrays are a supplied source conditional; no empty-picker constructor/RNG equivalence.",
    snapshots="Full supplied field inventories before/after and available source/helper-frame partial locals; dictionary traversal order, shared container identities and typed numeric/object arrays retained. Distinct ndarray-view buffer ownership is not a general checkpoint contract; source prefix does not mutate existing numeric buffers.",
    raw="Preserve list mutation/errors, stale/unbound data2, scalar len failure and species/cell global-grid collision. A completed raw prefix can still be an invalid ownership/world result; no positive full-cut credit.",
    lifecycle=reach["outer_order"],
    rebind="Every actual call including typed empty selection invalidates changing geometry/operators, diffusion/profile/RNG/GRN/gates/fields/bindings/checkpoint owners. Supplied post-cut declarations are recorded in a Cells dependency order, distinct from the original native call trace. No metadata-only record can unlock a runnable checkpoint.",
    refusal="Ordinary continuation always refuses at the currently unqualified changing-mesh boundary. Requires future qualified geometry and actual typed post-cut checkpoint integration, not reinitialization at fabricated defaults, stale caches or forged old binding IDs.",
    reference="Independent original-AST native prefix plus fresh stdlib hurt and stable-owner oracle. Existing80-digit quantity reductions and existing budgets retained. No independently carried trajectory.",
    exclusions=[
        "DEC/geometric/Poisson regeneration, full native cut or complete handler numeric execution",
        "Cell-content/ATP release, native conservation or energy closure",
        "Native RNG/picker/constructor history, original warm-clock or gate-cache preservation inferred by remapping",
        "Whole-loop, physical-mesh, biological or JAX/GPU qualification",
    ],
)
bindings = {}
for name, path in (
    ("frozen_event01_inputs", EVENT / "inputs.json"),
    ("frozen_event01_receipt", WORK / "betse_normal_ecm_event_join_static_receipt_01.json"),
    ("cut_whole_source_capability_audit", WORK / (PREFIX + "_source_witness_01.json")),
    ("cut_literal_prefix_AST", WORK / (PREFIX + "_AST_witness_01.json")),
):
    bindings[name] = dict(path=str(path), sha256=sha(path))
acceptance = dict(
    native="Exact full typed field/alias records and source exception type/message; no numerical tolerance can hide changed source buffers.",
    owned_state="Exact explicit owner maps, unchanged survivor/removed state values and source hurt mask.",
    quantities=old["tolerances"],
    metadata="Ordinary continuation is a deliberate prerequisite refusal even after a complete chain of supplied owner metadata; no physical geometry/checkpoint credit.",
    inherited_budget_source_sha256={
        p: sha(ROOT / p)
        for p in (
            "validation/topology/betse_tissue_cut_protocol.json",
            "validation/topology/betse_tissue_cut_reference.py",
            "src/cells/processes/betse_tissue_cut.py",
        )
    },
)
protocol = dict(
    kind="cells.native_cut_lifecycle_contract@1",
    law_id="betse_native_cut_deletion_prefix_and_owner_epoch@1",
    status="static_prepared_unexecuted_unqualified",
    purpose="Resolve actual native deletion/alias defects and cascading invalidation/reinitialization before permitting a changing-geometry ordinary handoff.",
    native_source=native,
    scope=scope,
    planned=planned,
    declared_cases=constants,
    acceptance=acceptance,
    binding_evidence=bindings,
    source_boundary=reach["prefix_boundary"],
    native_lifecycle_methods=reach["methods"],
    source_defects_preserved=reach["findings"],
    resources=dict(
        cpu=None,
        threads=1,
        gpu=False,
        max_command_seconds=480,
        max_process_tree_rss_bytes=2**30,
        min_available_host_memory_bytes=8 * 2**30,
    ),
    accounting=dict(
        native_material_conservation_credit=False,
        explicit_owner_sink_ledger_is_separate=True,
        physical_global_conservation_credit=False,
        complete_native_cut=False,
        physical_mesh_qualified=False,
        ordinary_checkpoint_ready=False,
    ),
    automatic_launch=False,
    automatic_polling=False,
    automatic_followup=False,
)
write(ROOT / "validation/topology" / (PREFIX + "_protocol.json"), protocol)
write(
    ROOT / "validation/topology" / (PREFIX + "_source_map.json"),
    dict(
        kind="cells.native_cut_lifecycle_source_map@1",
        scope=scope,
        source_AST_proof=proof,
        native_source_sha256=native["source_sha256"],
        installed_exact_python_files=332,
        source_boundary=reach["prefix_boundary"],
        whole_lifecycle_method_count=32,
        full_lifecycle_numeric_credit=False,
    ),
)
owned = [
    str(p.relative_to(ROOT))
    for folder, pattern in (
        ("src/cells/processes", PREFIX + "*.py"),
        ("validation/topology", PREFIX + "*"),
        ("tests/unit", "test_" + PREFIX + ".py"),
    )
    for p in sorted((ROOT / folder).glob(pattern))
    if p.is_file()
]
assert len(owned) == 9, owned
protected = prior["owned_sha256"] | prior["protected_sha256"]
for path, expected in protected.items():
    assert sha(ROOT / path) == expected, path
workfiles = [str(p.relative_to(ROOT)) for p in sorted(WORK.glob("*" + PREFIX + "*")) if p.is_file()]
workfiles += [
    "agent-work/cells-worker-01/workfiles/BETSE_NATIVE_CUT_LIFECYCLE_NOTES.md",
    "agent-work/cells-worker-01/workfiles/betse_normal_grn_join_static_audit.py",
]
queue = dict(
    kind="cells.native_cut_lifecycle_workqueue@1",
    status=protocol["status"],
    owned=owned,
    owned_sha256={p: sha(ROOT / p) for p in owned},
    protected_sha256=protected,
    workfiles=workfiles,
    runner="agent-work/cells-worker-01/workfiles/" + PREFIX + "_checks.py",
    planned=planned,
    binding_evidence=bindings,
    freeze_prerequisites=dict(frozen_event01_bound=bindings["frozen_event01_inputs"]),
    coordinated_shared_edit_paths=json.loads(
        (WORK / "betse_normal_ecm_event_join_workqueue.json").read_text()
    )["coordinated_shared_edit_paths"],
    authorized_physical_helper_refactor=prior["authorized_physical_helper_refactor"],
    scientific_imports=0,
    scientific_AST_executions=0,
    fixture_evaluations=0,
    pytest_collection_runs=0,
    numerical_runs=0,
    automatic_launch=False,
    automatic_polling=False,
    automatic_followup=False,
    active_numerical_job=None,
)
write(WORK / (PREFIX + "_workqueue.json"), queue)
print(
    json.dumps(
        dict(status=queue["status"], owned=len(owned), protected=len(protected), planned=planned),
        sort_keys=True,
    )
)
