# ruff: noqa: E501 -- emitted runner/report template, formatted before audit.
"""Adapt the established durable runner without launching or collecting tests."""

from pathlib import Path

ROOT = Path("/home/robert/Cells")
WORK = ROOT / "agent-work/cells-worker-01/workfiles"
code = (
    (WORK / "betse_ecm_grn_checks.py")
    .read_text()
    .replace("betse_ecm_grn", "betse_normal_ecm_field_join")
)
code = code.replace(
    "test_betse_normal_ecm_field_join_join.py", "test_betse_normal_ecm_field_join.py"
)
code = code.replace('"evidence/ecm-grn"', '"evidence/normal-ecm-field-join"')
code = code.replace("CELLS_ECM_GRN_CPU", "CELLS_NORMAL_ECM_FIELD_CPU")
code = code.replace("test_ecm_grn_history", "test_normal_ecm_field_history")
code = code.replace("test_ecm_grn_partial_failure", "test_normal_ecm_field_raw_partial")
code = code.replace("test_ecm_grn_dependencies", "test_normal_ecm_field_dependencies")
code = code.replace(
    'core = {"charged", "negative", "tight_junction", "fast_duplicate"}',
    'core = {"coupled", "polarized", "negative", "fast_duplicate", "rectangular"}',
)
code = code.replace("genuine_ecm_grn=True,", "full_native_field_suffix=True,")
code = code.replace('"new_ecm_grn_case"', '"new_normal_ecm_field_case"')
code = code.replace("== 25\n", "== 31\n").replace("== 17\n", "== 21\n")
a = code.index("def molecule_reports(")
b = code.index("\ndef run(", a)
report = """def molecule_reports(target,group,inputs):
    base=target/"evidence/normal-ecm-field-join"
    required=inputs["required_reports"][group]
    positive={str(p.relative_to(base)):p for p in base.glob("isolated-*/comparison.json")}
    if set(positive)!=set(required["positive"]):raise ValueError("Exact field-join positive set differs")
    reports=[]
    def reference(folder,mode):
        comp=json.loads((folder/"comparison.json").read_text())
        if not(comp["fresh_conditional_reference"] is True and comp["physical_global_conservation_credit"] is False
               and comp["fields"] and all(0<=v["normalized_max_error"]<=1 for v in comp["fields"].values())
               and all(0<=v["normalized_max_error"]<=0.1 for v in comp["resolutions"].values())):
            raise ValueError("Conditional field-join budget failed")
        for level in (1,2):
            result=json.loads((folder/("reference-"+str(level)+".json")).read_text())
            if not(result["production_imports_denied"] and not result["loaded_production_modules"]
                   and result["carried_reference_forms"]==0 and result["decimal_precision"]==(100 if level==1 else 160)):
                raise ValueError("Missing independent fresh field-join form")
            if mode=="cold" and result["cold_initialization"] is not True:raise ValueError("Missing cold form")
            if mode in ("field","material") and result["mode"]!=mode:raise ValueError("Wrong conditional mode")
    for name,path in sorted(positive.items()):
        row=json.loads(path.read_text())
        if not(row["completed"] is True and row["exact_native"] is True and row["complete_calls"]==3
               and row["cold_reference_forms"]==2 and row["bootstrap_reference_forms"]==2
               and all(row["conditional_"+name+"_reference_forms"]==6 for name in ("material","network","field"))
               and row["carried_reference_forms"]==0 and row["full_native_field_suffix"] is True
               and row["old_field_seam_removed"] is True and row["initialization_boundary_explicit"] is True
               and row["stale_gap_caches_preserved"] is True and row["retained_material_panel_accepted"] is False
               and row["retained_material_checks_passed"]==39 and row["retained_material_checks_total"]==40
               and row["physical_global_conservation_credit"] is False and row["independent_trajectory"] is False
               and all(row[k]==v for k,v in required["positive"][name].items())):
            raise ValueError("Invalid full normal ECM field-join history report")
        case=path.parent.name.removeprefix("isolated-")
        prep=base/("preparation-"+case)
        reference(prep/"cold","cold")
        reference(prep/"bootstrap","field")
        for index in range(3):
            for mode in ("material","network","field"):reference(prep/("point-"+str(index))/mode,mode)
        reports.append(dict(path=name,**row))
    raw={str(p.relative_to(base)):p for p in base.glob("isolated-*/raw-retention.json")}
    if set(raw)!=set(required["raw"]):raise ValueError("Exact field-join raw set differs")
    for name,path in sorted(raw.items()):
        row=json.loads(path.read_text())
        case=path.parent.name.removeprefix("isolated-")
        if not(row["positive_credit"] is False and row["physical_global_conservation_credit"] is False
               and row["complete_native_raw_buffers_retained"] is True and row["complete_available_port_partial_retained"] is True
               and row["strict_finite_guard_distinct_from_native_exception"]==case.startswith("bootstrap_")
               and row["completed_calls"]==(2 if case.startswith("late_") else 0)):
            raise ValueError("Invalid field-join raw limit report")
        reports.append(dict(path=name,**row))
    if group=="dependencies":
        names=[node.split("[",1)[1][:-1] for node in inputs["groups"][group]]
        found={p.name:p for p in base.glob("dependency-*.json")}
        if set(found)!={"dependency-"+name+".json" for name in names}:raise ValueError("Exact dependency set differs")
        for name in names:
            row=json.loads(found["dependency-"+name+".json"].read_text())
            if not(row["baseline_admitted"] is True and row["intended_failure_reached"] is True
                   and row["actual_leaf_type"]=="ValueError" and row["actual_message"]==row["expected_message"]
                   and row["source_failure_credit"] is False):raise ValueError("Invalid field-join dependency witness")
            reports.append(dict(path="dependency-"+name+".json",**row))
    return reports

"""
code = code[:a] + report + code[b:]
code = code.replace(
    "conditional_pre_network_only=True,", "conditional_material_network_field_only=True,"
)
code = code.replace(
    "genuine_normal_ECM_GRN_orchestration=True,",
    "genuine_normal_ECM_GRN_orchestration=True,\n                complete_ECM_field_reconstruction=True,\n                prior_reconstructed_field_feedback=True,",
)
code = code.replace(
    '"""Freeze the static normal ECM GRN package.',
    '"""Freeze the static full normal ECM field composition package.',
)
path = WORK / "betse_normal_ecm_field_join_checks.py"
with path.open("x") as handle:
    handle.write(code)
print(path)
