# ruff: noqa: E501 -- emitted templates are formatted separately.
"""Emit standalone fixture and independent-reference code, never evaluate it."""

from pathlib import Path

ROOT = Path("/home/robert/Cells")

fixture = '''"""Prepared-phase standalone GRN cases; no normal solver advance."""
import copy
from validation.betse.betse_normal_grn_join_fixtures import fixture as previous

CASES=("standard","fractional_sampling","single_step","sparse_samples","time_dilation","temperature_split","no_growth","no_transport","no_modulators","cold_publication_off")
COMPONENT_CONTROLS=("no_growth","no_transport","no_modulators")
RAW_CASES=("cold_missing_Y_Dm","first_negative","second_negative","second_call_missing_Y_Dm","late_plot_cell")
DEPENDENCIES=("ECM","mitochondria","fluid","unsafe_sampling","missing_owner_state","missing_boundary_state","file_restart")


def fixture(case="standard"):
    if case not in CASES:
        raise ValueError("Choose a declared standalone case")
    old=previous(case if case in ("time_dilation","temperature_split","no_growth","no_modulators") else "regulated")
    net=copy.deepcopy(old["channel_definition"]["network"])
    net["grn_initialization_publish"]=case!="cold_publication_off"
    if case=="no_transport":
        for config,row in zip(net["grn_configuration"]["biomolecules"],net["molecules"],strict=True):
            config.update({"Dm":0.0,"Dgj":0.0,"GJ impermeable":True})
            row["parameters"].update(Dm=0.0,Dgj=0.0,ignoreGJ=True)
    calls=[dict(dt_s=0.002,total_s=0.006,sample_s=0.002,plot_cell=1,raw_fault=None),dict(dt_s=0.001,total_s=0.004,sample_s=0.002,plot_cell=1,raw_fault=None)]
    if case=="fractional_sampling":
        calls[0].update(total_s=0.007,sample_s=0.003)
        calls[1].update(total_s=0.0045,sample_s=0.0015)
    if case=="single_step":
        for call in calls:
            call["total_s"]=call["dt_s"]
    if case=="sparse_samples":
        for call in calls:
            call["sample_s"]=0.1
    return dict(kind="cells.betse_sim_grn_inputs@1",provenance="Explicit prior initialized phase; original simrunner new-owner branch and entire run_core_sim; file I/O captured in memory",
        ion_definition=copy.deepcopy(old["ion_definition"]),current_definition=copy.deepcopy(old["current_definition"]),
        initial=copy.deepcopy(old["initial"]),network=net,calls=calls,case_id=case,
        case_role="component_control" if case in COMPONENT_CONTROLS else "new_standalone_grn_case",
        initial_dt_s=0.123,runtime_temperature_K=281.0 if case=="temperature_split" else 298.15,
        simulator_time_before=[-0.2,-0.1],incoming_charge_C_m3=[0.01,-0.02,0.03],
        incoming_current_A_m2=[(j-4)*1e-6 for j in range(9)],
        scope=dict(mitochondria=False,fluid=False,cuts=False,grn_unpickle_filename=None))


def raw_fixture(case):
    if case not in RAW_CASES:
        raise ValueError("Choose a declared standalone partial failure")
    data=fixture()
    net=data["network"]
    if case=="cold_missing_Y_Dm":
        del net["grn_configuration"]["biomolecules"][1]["Dm"]
        net["raw_initialization_fault"]="Y"
    elif case in ("first_negative","second_negative"):
        i=0 if case=="first_negative" else 1
        net["molecules"][i]["growth"].update(production_rate_mM_s=0.0,decay_rate_per_s=1e6)
        net["grn_configuration"]["biomolecules"][i]["growth and decay"].update({"production rate":0.0,"decay rate":1e6})
    elif case=="second_call_missing_Y_Dm":
        data["calls"][1]["raw_fault"]="missing_Y_Dm"
    else:
        data["calls"][0]["plot_cell"]=99
    data["case_id"],data["case_role"]=case,"raw_partial_failure"
    return data
'''
with (ROOT / "validation/betse/betse_sim_grn_fixtures.py").open("x") as f:
    f.write(fixture)

ref = (ROOT / "validation/betse/betse_normal_grn_join_reference.py").read_text()
ref = ref.replace(
    'for row in definition["modulators"]:',
    "for row in ():  # Standalone never dispatches configured modulators.",
)
ref = ref.replace("scale_factor=d(1),", 'scale_factor=d(row.get("scale factor",1)),', 1)
ref = ref.replace(
    "        return plain(\n            dict(\n                molecule_fields=genes,",
    """        simulator=dict(extra_rho_cells=list(map(d,inputs["incoming_charge_C_m3"])),extra_J_mem=list(map(d,inputs["incoming_current_A_m2"])))
        if net["grn_initialization_publish"]:
            simulator.update(extra_rho_cells=[d(0)]*n,extra_rho_env=[d(0)]*m)
        return plain(
            dict(
                molecule_fields=genes,""",
)
start = ref.index("                simulator_fields=dict(")
end = ref.index("                owner_fields=dict(", start)
ref = ref[:start] + "                simulator_fields=simulator,\n" + ref[end:]
ref = ref.replace(
    "charge_has_been_balanced=True,",
    'charge_has_been_balanced=net["grn_initialization_publish"],',
    1,
)
index = ref.index("\ndef evaluate(")
clock = '''

def clock(inputs,*,refinement=1):
    """Independent binary64 clock specification; no NumPy or source execution.

    Decimal90/140 additionally counts the amount of numerical dt advanced.
    Source linspace has N endpoints over N*dt; timestamps and dt differ.
    """
    call=inputs["call"]
    dt,total,sample=map(float,(call["dt_s"],call["total_s"],call["sample_s"]))
    n=int(float(total/dt))
    if not 1<=n<=8 or sample<dt:
        raise ValueError("Require bounded progressing standalone clocks")
    end=float(n*dt)
    if n==1:
        tt=[0.0]
    else:
        interval=float(end/(n-1))
        tt=[float(i*interval) for i in range(n)]
        tt[-1]=end
    stride=float(sample/dt)
    i,indices=0,[]
    while i<n-stride:
        i=int(float(i+stride))
        indices.append(i)
    with localcontext() as ctx:
        ctx.prec=90 if refinement==1 else 140
        return plain(dict(tt=tt,sample_indices=indices,sample_times=[tt[i] for i in indices],
            steps=n,source_dt_s=dt,declared_total_s=total,source_endpoint_s=end,
            timestamp_interval_s=None if n==1 else float(end/(n-1)),
            numerical_dt_advanced_s=d(dt)*n,
            forced_substances_affect_charge=False,clear_run_loop_called=False,
            configured_modulators_dispatched=False,owner_time_resets=True,
            simulator_time_appends=True,concentrations_reset_by_reinitialize=False,
            sample_cache_reset_by_clear_cache=True,first_step_t_zero_advances=True,
            decimal_precision=ctx.prec,carried_reference_forms=0,
            physical_conservation_credit=False,standalone_clock=True))
'''
ref = ref[:index] + clock + ref[index:]
ref = ref.replace(
    '    if inputs.get("mode") == "cold_initialization":',
    '    if inputs.get("mode")=="standalone_clock":\n        return clock(inputs,refinement=refinement)\n    if inputs.get("mode") == "cold_initialization":',
)
with (ROOT / "validation/betse/betse_sim_grn_reference.py").open("x") as f:
    f.write(ref)
print({"emitted_without_evaluating": 2})
