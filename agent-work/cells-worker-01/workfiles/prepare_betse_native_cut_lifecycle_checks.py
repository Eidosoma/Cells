# ruff: noqa: E501
"""Exclusive static runner source adaptation; no numerical/fixture calls."""

import ast
from pathlib import Path

root = Path("/home/robert/Cells")
old = (
    root / "agent-work/cells-worker-01/workfiles/betse_normal_ecm_event_join_checks.py"
).read_text()
old = old.replace("betse_normal_ecm_event_join", "betse_native_cut_lifecycle").replace(
    "validation/betse/betse_native_cut_lifecycle", "validation/topology/betse_native_cut_lifecycle"
)
old = old.replace("normal-ecm-event-join", "native-cut-lifecycle").replace(
    "CELLS_ECM_EVENT_CPU", "CELLS_NATIVE_CUT_CPU"
)
old = old.replace("cells.normal_ecm_event_join_prepared@1", "cells.native_cut_lifecycle_prepared@1")
old = old.replace(
    'queue["freeze_prerequisites"]["Chief03_source_review"]',
    'queue["freeze_prerequisites"]["frozen_event01_bound"]',
)
old = old.replace(
    "Chief03 source review is required before the event freeze",
    "Frozen event01 dependency evidence is required before the separate cut freeze",
)
start = old.index("        groups = {")
end = old.index('        stage = "final_snapshot_hashes"', start)
old = (
    old[:start]
    + """        groups={name:[] for name in ("core","raw","dependencies")}
        required={group:dict(positive={},raw=[]) for group in groups}
        for case in constants["CASES"]:
            groups["core"].append(TEST+"::test_native_cut_prefix["+case+"]")
            required["core"]["positive"][case+"/comparison.json"]=dict(exact_native_prefix=True)
        for case in constants["RAW_CASES"]:
            groups["raw"].append(TEST+"::test_native_cut_raw_partial["+case+"]")
            required["raw"]["raw"].append(case+"/raw-retention.json")
        for case in constants["DEPENDENCIES"]:
            groups["dependencies"].append(TEST+"::test_native_cut_capabilities["+case+"]")
        ids=[node for group in groups.values() for node in group]
        assert len(ids)==len(set(ids))==protocol["planned"]["checks"]==25
        assert sum(len(row["positive"])+len(row["raw"]) for row in required.values())==14
"""
    + old[end:]
)
tree = ast.parse(old)
reader = ast.parse("""def molecule_reports(target,group,inputs):
    base=target/"evidence/native-cut-lifecycle"
    required=inputs["required_reports"][group]
    reports=[]
    positive={str(p.relative_to(base)):p for p in base.glob("*/comparison.json")}
    if set(positive)!=set(required["positive"]):
        raise ValueError("Exact native cut prefix positive set differs")
    for name,path in sorted(positive.items()):
        row=json.loads(path.read_text())
        if not (row["completed"] is True and row["exact_native_prefix"] is True
                and row["fresh_reference_forms"]==1 and row["carried_reference_forms"]==0
                and row["retained_prefix_and_sink_ledgers"] is True
                and row["ordinary_continuation_refused"] is True
                and row["source_mesh_calls"]==0 and row["complete_native_cut"] is False
                and row["physical_mesh_qualified"] is False
                and row["physical_global_conservation_credit"] is False
                and row["amount_metrics"] and all(0<=v<=1 for v in row["amount_metrics"].values())):
            raise ValueError("Invalid cut prefix/owner conditional report")
        ref=json.loads((path.parent/"independent/result.json").read_text())
        if not (ref["production_imports_denied"] is True and not ref["loaded_production_modules"]
                and ref["decimal_precision"]==80 and ref["carried_reference_forms"]==0
                and ref["physical_mesh_qualified"] is False and ref["complete_native_cut"] is False):
            raise ValueError("Missing independent conditional cut form")
        reports.append(dict(path=name,**row))
    raw={str(p.relative_to(base)):p for p in base.glob("*/raw-retention.json")}
    if set(raw)!=set(required["raw"]):
        raise ValueError("Exact raw cut set differs")
    for name,path in sorted(raw.items()):
        row=json.loads(path.read_text())
        if not (row["positive_credit"] is False and row["complete_raw_native_and_port_evidence"] is True
                and row["strict_ordinary_continuation_credit"] is False
                and row["complete_native_cut"] is False and row["physical_mesh_qualified"] is False
                and row["geometry_calls"]==0):
            raise ValueError("Invalid raw native cut retention report")
        reports.append(dict(path=name,**row))
    dependencies={p.parent.name.removeprefix("dependency-"):p for p in base.glob("dependency-*/dependency.json")}
    expected=[node.split("[",1)[1][:-1] for node in inputs["groups"][group]] if group=="dependencies" else []
    if set(dependencies)!=set(expected):
        raise ValueError("Exact cut dependency set differs")
    for name,path in sorted(dependencies.items()):
        row=json.loads(path.read_text())
        if not (row["baseline_admitted"] is True and row["intended_failure_reached"] is True
                and row["ordinary_checkpoint_ready"] is False and row["source_failure_credit"] is False
                and row["actual_type"]==row["expected_type"]
                and row["actual_message"]==row["expected_message"]):
            raise ValueError("Invalid cut dependency refusal witness")
        reports.append(dict(path=name,**row))
    return reports
""").body[0]
for i, node in enumerate(tree.body):
    if isinstance(node, ast.FunctionDef) and node.name == "molecule_reports":
        tree.body[i] = reader
run = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "run")
for call in ast.walk(run):
    if (
        not isinstance(call, ast.Call)
        or not isinstance(call.func, ast.Name)
        or call.func.id != "dict"
    ):
        continue
    if any(
        k.arg == "conditional_event_material_calcium_network_noise_field_only"
        for k in call.keywords
    ):
        keep = {
            "status",
            "group",
            "checks",
            "exact_pytest_ids",
            "resources",
            "reports",
            "source_unchanged",
            "automatic_followup",
        }
        call.keywords = [k for k in call.keywords if k.arg in keep]
        extra = ast.parse(
            "dict(native_deletion_prefix_only=True,geometry_calls_executed=0,complete_native_cut=False,physical_mesh_qualified=False,ordinary_checkpoint_ready=False,existing_owner_ledger_is_separate=True,carried_reference_forms=0,physical_global_conservation_credit=False)",
            mode="eval",
        ).body
        call.keywords += extra.keywords
with (root / "agent-work/cells-worker-01/workfiles/betse_native_cut_lifecycle_checks.py").open(
    "x"
) as stream:
    stream.write(ast.unparse(tree) + "\n")
