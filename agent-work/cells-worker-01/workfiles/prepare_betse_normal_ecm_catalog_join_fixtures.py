# ruff: noqa: E501
"""Write declared fixture code from catalog metadata without evaluating fixtures."""

import json
from pathlib import Path

ROOT = Path("/home/robert/Cells")
folder = ROOT / "validation/betse"
entries = json.loads((folder / "betse_normal_catalog_join_inventory.json").read_text())["classes"]
classes = tuple(entries)
families = {name: row["family"] for name, row in entries.items()}
header = '''"""Declared ECM modern populations; no worker-evaluated fixture outcomes.

All55 class prefixes use a predeclared nonsingular prepared Vm recipe before
bootstrap. These are separate identities from the preserved old Cav_G failure.
"""
import copy
from validation.betse.betse_normal_ecm_calcium_join_fixtures import fixture as calcium_fixture
'''
constants = "CLASSES = " + repr(classes) + "\nFAMILIES = " + repr(families) + "\n"
body = """
CONTEXT_CASES=("mixed_forward","mixed_reverse","empty_channels","cat_zero_Ca", "publication_carry",
    "rectangular","fast_duplicate","profile_duplicate","Ca_membrane_activator",
    "Ca_environment_inhibitor","rho_blocked","maximum_zero","init_inactive_SIM",
    "no_channels","no_CaATP","polarized")
CASES=CLASSES+CONTEXT_CASES
COMPONENT_CONTROLS=("rho_blocked","maximum_zero","no_channels","no_CaATP","empty_channels")
RAW_CASES=("cold_Cav_G_literal_pole","second_constructor_literal_pole","empty_profile_indices",
    "first_channel_overflow","second_channel_overflow","first_gene_after_channels",
    "second_gene_after_channels")
DEPENDENCIES=("ER_requested","expression_profile","legacy_cagPotassium","INIT_requested",
    "missing_profile_map","missing_route_ion","unsupported_modifier","missing_channel_cache",
    "missing_private_gate","changed_target_cache","changed_owner_flag","wrong_clock",
    "invented_rate_presence","supplied_old_field","missing_constructor_metadata","varying_dt")


def population(name,slot=0,maximum=1e-7,apply_to="all"):
    return {"name":"population_"+str(slot),"channel class":FAMILIES[name],"channel type":name,
        "max Dm":maximum,"apply to":apply_to,"init active":True}


def fixture(case="mixed_forward"):
    if case not in CASES:
        raise ValueError("Choose a declared ECM modern catalog prefix")
    base=case if case in ("publication_carry","rectangular","fast_duplicate","polarized","no_CaATP") else "active"
    data=calcium_fixture(base)
    field=data["field"]
    m=len(field["initial"]["voltage_V"])
    # Fixed before all numerical execution. No warm-field or gate-output selection.
    field["initial"]["voltage_V"]=[-0.031123+0.003317*j for j in range(m)]
    channel_names=[case] if case in CLASSES else ["Nav1p2","HCN2","Ca_L2"]
    if case=="mixed_reverse": channel_names.reverse()
    if case=="cat_zero_Ca": channel_names=["CatLeak","CaLeak"]
    if case in ("Ca_membrane_activator","Ca_environment_inhibitor"): channel_names=["CaLeak","Kv1p2","NaLeak"]
    if case in ("rho_blocked","maximum_zero","init_inactive_SIM"): channel_names=["NaLeak","HCN2"]
    rows=[population(name,j) for j,name in enumerate(channel_names)]
    profiles={}
    if case=="profile_duplicate":
        profiles={"alpha":[0,1,1],"beta":[4,7,1]}
        for row in rows: row["apply to"]=["beta","alpha"]
    if case=="Ca_membrane_activator":
        rows[1].update({"channel activators":["Ca"],"activator Km":[1.2e-4],"activator n":[2.0],"activator zone":["cell"]})
    if case=="Ca_environment_inhibitor":
        rows[1].update({"channel inhibitors":["Ca"],"inhibitor Km":[1.7],"inhibitor n":[2.0],"inhibitor zone":["env"]})
    if case=="rho_blocked":
        for call in field["steps"]: call["material"]["channel_multiplier"]=[0.0]*m
    if case=="maximum_zero":
        for row in rows: row["max Dm"]=0.0
    if case=="init_inactive_SIM":
        for row in rows: row["init active"]=False
    if case=="empty_channels": rows=[]
    if case=="no_channels": rows=None
    data.update(kind="cells.normal_ecm_catalog_join_inputs@1",case_id=case,
        case_role="component_control" if case in COMPONENT_CONTROLS else "new_ECM_modern_catalog_composition",
        catalog=dict(kind="cells.native_ECM_modern_channel_configuration@1",populations=rows,
            tissue_profiles=profiles,phase="SIM",provenance="Original read_channels and Channel.init_channel; prepared sim.dyna index maps; no expression profile"),
        stop_after_calls=1 if case in CLASSES else 3)
    field["input_recipe"].update(modern_cold_vm_recipe="-0.031123+0.003317*j V",
        channel_maxDm_m2_s=1e-7,explicit_source_clock_N=3)
    return data


def raw_fixture(case):
    if case not in RAW_CASES:
        raise ValueError("Choose a declared ECM catalog raw limit")
    data=fixture("mixed_forward")
    rows=[population("NaLeak")]
    if case in ("cold_Cav_G_literal_pole","second_constructor_literal_pole"):
        rows=[] if case.startswith("cold_") else [population("NaLeak")]
        rows.append(population("Cav_G",len(rows)))
        data["field"]["initial"]["voltage_V"][2]=-0.027
    elif case=="empty_profile_indices":
        rows[0]["apply to"]=[]
    elif case=="first_channel_overflow":
        rows[0]["max Dm"]=1e308
    elif case=="second_channel_overflow":
        rows.append(population("NaLeak",1,1e308))
    elif case in ("first_gene_after_channels","second_gene_after_channels"):
        i=0 if case.startswith("first_") else 1
        data["field"]["network"]["configuration"]["biomolecules"][i]["growth and decay"].update(
            {"production rate":0.0,"decay rate":1e8})
    data["catalog"]["populations"]=rows
    data.update(case_id=case,case_role="raw_native_constructor_channel_or_gene_limit",stop_after_calls=1)
    return data
"""
(folder / "betse_normal_ecm_catalog_join_fixtures.py").write_text(header + constants + body)
print(
    "Wrote55 one-call prefixes,16 three-call contexts,7 raw limits,16 dependency controls; no evaluation"
)
