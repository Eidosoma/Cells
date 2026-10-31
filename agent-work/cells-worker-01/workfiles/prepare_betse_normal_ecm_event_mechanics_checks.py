# ruff: noqa: E501
"""Static preparation of an isolated prospective runner from the event01 driver."""

import ast
from pathlib import Path

ROOT = Path("/home/robert/Cells")
WORK = ROOT / "agent-work/cells-worker-01/workfiles"
PREFIX = "betse_normal_ecm_event_mechanics"
old = Path("/mnt/workspaces/Cells/betse-normal-ecm-event-join-prepared-20261031-01/driver.py")
text = old.read_text()
text = (
    text.replace("betse_normal_ecm_event_join_source_map.json", PREFIX + "_source_map.json")
    .replace("betse_normal_ecm_event_join_protocol.json", PREFIX + "_protocol.json")
    .replace("betse_normal_ecm_event_join_workqueue.json", PREFIX + "_workqueue.json")
    .replace("test_betse_normal_ecm_event_join.py", "test_" + PREFIX + ".py")
)
start = text.index("        tree = ast.parse(")
stop = text.index('        stage = "final_snapshot_hashes"', start)
text = text[:start] + "        groups, required = plan(source, protocol)\n" + text[stop:]
start = text.index("        for path, expected in hashes.items():")
stop = text.index('        (out / "driver.py")', start)
text = (
    text[:start]
    + """        controlled=queue["owned_sha256"] | queue["protected_sha256"]
        for path,expected in controlled.items():
            if sha(ROOT/path)!=expected or hashes[path]!=expected:
                raise ValueError("Controlled dependency changed during freeze: "+path)
"""
    + text[stop:]
)
text = text.replace(
    'kind="cells.normal_ecm_event_join_prepared@1"',
    'kind="cells.normal_ecm_event_mechanics_prepared@1"',
)
text = text.replace(
    '                native_source_copies=2 * len(native["source_sha256"]),',
    """                native_source_copies=2*len(native["source_sha256"]),
                snapshot_only_unloaded_paths=sorted(set(hashes)-set(controlled)),
                snapshot_only_paths_are_not_adopted_dependencies=True,
                explicit_dependency_binding=queue["explicit_dependency_binding"],
                new_or_retained_qualification_passes=0,
                component_qualification_pending=True,""",
)
# Existing immutable native-source and binding-copy loop retains original bytes.
text = text.replace('name + ".json"', 'name + Path(row["path"]).suffix')
plan = """
def plan(source,protocol):
    fixture=ast.parse((source/"validation/betse/betse_normal_ecm_event_mechanics_fixtures.py").read_text())
    constants={t.id:ast.literal_eval(n.value) for n in fixture.body if isinstance(n,ast.Assign) for t in n.targets if isinstance(t,ast.Name) and t.id in {"CASES","COMPONENT_CONTROLS","RAW_CASES","DEPENDENCIES","CORRUPTIONS"}}
    groups={name:[] for name in ("core","events","controls","raw","dependencies")}
    groups.update({"corruption-"+case:[] for case in constants["CORRUPTIONS"]})
    required={group:dict(positive=[],raw=[],corruptions=[]) for group in groups}
    for case in constants["CASES"]:
        group="controls" if case in constants["COMPONENT_CONTROLS"] else "core" if case in {"combined","temperature","moving_P_noise","ecmJ"} else "events"
        groups[group].append(TEST+"::test_event_mechanics_history["+case+"]")
        required[group]["positive"].append("isolated-"+case+"/comparison.json")
    for case in constants["RAW_CASES"]:
        groups["raw"].append(TEST+"::test_event_mechanics_raw["+case+"]")
        required["raw"]["raw"].append("isolated-"+case+"/raw-retention.json")
    for case in constants["DEPENDENCIES"]:
        groups["dependencies"].append(TEST+"::test_event_mechanics_dependencies["+case+"]")
    for case in constants["CORRUPTIONS"]:
        group="corruption-"+case
        groups[group].append(TEST+"::test_event_mechanics_corruptions["+case+"]")
        required[group]["positive"].append("isolated-combined/comparison.json")
        required[group]["corruptions"].append("corruption-"+case+".json")
    ids=[i for nodes in groups.values() for i in nodes]
    assert len(ids)==len(set(ids))==protocol["planned"]["checks"]==62
    assert sum(len(row["positive"])+len(row["raw"]) for row in required.values())==36
    return groups,required

"""
text = text.replace("\ndef prepare(out):", "\n" + plan + "\ndef prepare(out):", 1)
# Retain exactly the established positive report dict, whose entries are literal metadata.
tree = ast.parse((ROOT / "tests/unit" / ("test_" + PREFIX + ".py")).read_text())
fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "run_history")
report = next(
    n.value
    for n in fn.body
    if isinstance(n, ast.Assign)
    and isinstance(n.targets[0], ast.Name)
    and n.targets[0].id == "report"
)
expected = {k.arg: ast.literal_eval(k.value) for k in report.keywords}
reader = """
def molecule_reports(target,group,inputs):
    base=target/"evidence/normal-ecm-event-mechanics"
    required=inputs["required_reports"][group]
    reports=[]
    def reference(folder,mode):
        comp=json.loads((folder/"comparison.json").read_text())
        if not (comp["fresh_conditional_reference"] is True and comp["physical_global_conservation_credit"] is False and comp["fields"] and comp["resolutions"] and all(0<=v["normalized_max_error"]<=1 for v in comp["fields"].values()) and all(0<=v["normalized_max_error"]<=0.1 for v in comp["resolutions"].values())):
            raise ValueError("Inherited conditional budget failed")
        for level in (1,2):
            row=json.loads((folder/("reference-"+str(level)+".json")).read_text())
            if not (row["production_imports_denied"] is True and not row["loaded_production_modules"] and type(row["carried_reference_forms"]) is int and row["carried_reference_forms"]==0 and row["decimal_precision"]==(100 if level==1 else 160) and isinstance(row["runtime"]["measured_cpu_affinity"],list)):
                raise ValueError("Missing fresh reference/runtime receipt")
            if mode=="cold" and row["cold_initialization"] is not True:raise ValueError("Missing cold form")
            if mode in {"field","material","calcium","events","noise","mechanics"} and row["mode"]!=mode:raise ValueError("Wrong conditional mode")
            if mode=="mechanics":
                raw=folder/("raw-reference-"+str(level))/("raw-decimal-"+str(100 if level==1 else 160)+".json")
                preserved=json.loads(raw.read_text())
                if not (preserved["precision"]==(100 if level==1 else 160) and preserved["payload"]):raise ValueError("Missing complete raw Decimal mechanics tree")
    positive={str(p.relative_to(base)):p for p in base.glob("isolated-*/comparison.json")}
    if set(positive)!=set(required["positive"]):raise ValueError("Wrong exact positive/baseline report set")
    for name,path in sorted(positive.items()):
        row=json.loads(path.read_text())
        expected=POSITIVE_EXPECTED
        if set(row)!=set(expected) or any(type(row[k]) is not type(v) or row[k]!=v for k,v in expected.items()):raise ValueError("Invalid coupled source history/scope report")
        case=path.parent.name.removeprefix("isolated-")
        prep=base/("preparation-"+case)
        reference(prep/"cold","cold");reference(prep/"bootstrap","field")
        for index in range(3):
            for mode in ("events","material","calcium","channels","network","noise","mechanics","field"):
                reference(prep/("point-"+str(index))/mode,mode)
        reports.append(dict(path=name,**row))
    raw={str(p.relative_to(base)):p for p in base.glob("isolated-*/raw-retention.json")}
    if set(raw)!=set(required["raw"]):raise ValueError("Wrong exact raw source-limit report set")
    for name,path in sorted(raw.items()):
        row=json.loads(path.read_text());case=path.parent.name.removeprefix("isolated-")
        if not (row["positive_credit"] is False and type(row["completed_calls"]) is int and 0<=row["completed_calls"]<3 and row["completed_calls"]==(2 if case=="late_negative_temperature" else row["completed_calls"]) and row["full_native_partial_retained"] is True and row["full_owned_partial_retained"] is True and row["source_and_owned_endpoints_reported_separately"] is True and row["display_completed"] is False and row["physical_global_conservation_credit"] is False and row["qualification_inherited"] is False and row["port_stage"]=="event_noise_mechanics_material_field" and row["native_status"] in ("source_completed","source_refused") and type(row["native_complete_calls"]) is int and 0<=row["native_complete_calls"]<=3):raise ValueError("Invalid raw refusal/partial scope report")
        reports.append(dict(path=name,**row))
    if group=="dependencies":
        names=[node.split("[",1)[1][:-1] for node in inputs["groups"][group]]
        found={p.name:p for p in base.glob("dependency-*.json")}
        if set(found)!={"dependency-"+name+".json" for name in names}:raise ValueError("Wrong dependency set")
        for name in names:
            row=json.loads(found["dependency-"+name+".json"].read_text())
            if not (row["baseline_admitted"] is True and row["intended_failure_reached"] is True and row["actual_leaf_type"] in ("ValueError","AssertionError","MechanicsRejected") and row["expected_fragment"] in row["actual_message"] and row["source_failure_credit"] is False and row["display_completed"] is False):raise ValueError("Invalid dependency witness")
            reports.append(dict(path="dependency-"+name+".json",**row))
    found={p.name:p for p in base.glob("corruption-*.json")}
    if set(found)!=set(required["corruptions"]):raise ValueError("Wrong corruption report set")
    for name,path in sorted(found.items()):
        row=json.loads(path.read_text())
        if row!=dict(baseline_complete=True,intended_corruption_rejected=True,duplicate_baseline_positive_credit=False,scientific_budget_changed=False):raise ValueError("Invalid corruption control")
        reports.append(dict(path=name,**row))
    return reports

"""
reader = reader.replace("POSITIVE_EXPECTED", repr(expected))
start = text.index("\ndef molecule_reports(")
stop = text.index("\ndef run(", start)
text = text[:start] + "\n" + reader + text[stop:]
text = text.replace("CELLS_ECM_EVENT_CPU=str(cpu)", "CELLS_ECM_EVENT_MECHANICS_CPU=str(cpu)")
start = text.index(
    "                conditional_event_material_calcium_network_noise_field_only=True,"
)
stop = text.index("                automatic_followup=False,", start)
text = (
    text[:start]
    + """                scoped_supplied_event_noise_steady_mechanics_contract=True,
                new_positive_contexts=0 if group.startswith("corruption-") else len(inputs["required_reports"][group]["positive"]),
                duplicate_baseline_positive_credit=False,
                component_qualification_pending=True,
                carried_reference_forms=0,
                sampled_display_completed=False,
                native_full_initialization_parity=False,
                physical_global_conservation_credit=False,
                full_native_normal_solver_executed=False,
"""
    + text[stop:]
)
path = WORK / (PREFIX + "_checks.py")
with path.open("x") as stream:
    stream.write(text)
print(path)
