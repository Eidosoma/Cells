# ruff: noqa: E501 -- native capture templates, formatted before review.
"""Text-only native CaATP extension of the frozen complete ECM field capture."""

import ast
from pathlib import Path

ROOT = Path("/home/robert/Cells")
source = (ROOT / "validation/betse/betse_normal_ecm_field_join_native.py").read_text()


def change(before, after):
    global source
    assert source.count(before) == 1, before[:100]
    source = source.replace(before, after)


change(
    "def evaluate(inputs):\n",
    """def evaluate(declared):
    inputs=declared["field"]
""",
)
change(
    "    return source, geometry, sites, geometry_sites, pins, lines\n",
    """    ca_nodes,ca_sites=calcium_nodes(root)
    api=dict(np=np,BetseSimUnstableException=network.science()["BetseSimUnstableException"],
        SimPhaseKind=network.science()["SimPhaseKind"])
    exec(compile(ast.fix_missing_locations(ast.Module(body=ca_nodes,type_ignores=[])),
        "<complete original ECM calcium caller>","exec"),api)
    api["stb"]=SimpleNamespace(pumpCaATP=api["pumpCaATP"])
    geometry["ca_api"]=api
    geometry_sites.update(ca_sites)
    return source, geometry, sites, geometry_sites, pins, lines
""",
)
insert = """def calcium_nodes(root):
    sim_tree=ast.parse((root/"betse/science/sim.py").read_bytes())
    cls=next(n for n in sim_tree.body if isinstance(n,ast.ClassDef) and n.name=="Simulator")
    methods={n.name:n for n in cls.body if isinstance(n,ast.FunctionDef)}
    tb=ast.parse((root/"betse/science/sim_toolbox.py").read_bytes())
    functions={n.name:n for n in tb.body if isinstance(n,ast.FunctionDef)}
    parameters=ast.parse((root/"betse/science/parameters.py").read_bytes())
    needed={"Ca_dyn","alpha_Ca","cATP","cADP","cPi","KmCa_Ca","KmCa_ATP","deltaGATP","F","R"}
    defaults=[n for n in ast.walk(parameters) if isinstance(n,ast.Assign) and ast.unparse(n.targets[0]) in {"self."+k for k in needed}]
    assert len(defaults)==len(needed)
    init=methods["init_dynamics"]
    cold=[n for n in init.body if isinstance(n,ast.Assign) and ast.unparse(n.targets[0]) in ("self.CaATP_block","self.rho_pump")]
    cold += [n for n in methods["init_core"].body if isinstance(n,ast.Assign) and ast.unparse(n.targets[0])=="self.met_concs"]
    cold += [n for n in init.body if isinstance(n,ast.If) and ast.unparse(n.test)=="p.ions_dict['Ca'] == 1 and p.Ca_dyn"]
    assert len(cold)==4
    plot=methods["_plot_loop"]
    clock=[n for n in plot.body if isinstance(n,ast.If) and ast.unparse(n.test)=="phase.kind is SimPhaseKind.INIT"]
    clock += [n for n in plot.body if isinstance(n,ast.Assign) and ast.unparse(n.targets[0]) in ("phase_time_len","time_steps")]
    assert len(clock)==3
    built=[field_native.wrapper("calcium_defaults","self,iu",defaults),
        field_native.wrapper("calcium_cold","self,cells,p",cold),
        field_native.wrapper("source_clock","phase",clock+ast.parse("return time_steps").body)]
    originals=[methods["ca_handler"],functions["pumpCaATP"],functions["no_negs"]]
    sites={name:dict(lines=[[n.lineno,n.end_lineno] for n in nodes],ast_sha256=hashlib.sha256(
        ast.dump(ast.Module(body=nodes,type_ignores=[]),include_attributes=False).encode()).hexdigest())
        for name,nodes in dict(calcium_defaults=defaults,calcium_cold=cold,source_clock=clock,
            ca_handler=[methods["ca_handler"]],pumpCaATP=[functions["pumpCaATP"]],Ca_no_negs=[functions["no_negs"]]).items()}
    return copy.deepcopy(originals)+built,sites


"""
a = source.index("def capture():")
source = source[:a] + insert + source[a:]
# Qualified owner/dispatch bridge with the actual normal source t argument.
tree = ast.parse((ROOT / "validation/betse/betse_ecm_grn_native_network.py").read_text())
dispatch = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "run_dispatch")
dispatch.args.args.append(ast.arg(arg="source_time_s"))
for node in ast.walk(dispatch):
    if isinstance(node, ast.Call) and ast.unparse(node.func) == "science()['dispatch']":
        node.args[1] = ast.Name(id="source_time_s", ctx=ast.Load())
    if (
        isinstance(node, ast.Name)
        and isinstance(node.ctx, ast.Load)
        and node.id in ("attach", "science", "cache", "material_values", "owner_evidence", "clone")
    ):
        node.id = "network." + node.id
a = source.index("def evaluate(")
source = source[:a] + ast.unparse(ast.fix_missing_locations(dispatch)) + "\n\n" + source[a:]
change(
    "    field_phase, material_candidate, post_material_cache = None, None, None\n",
    """    field_phase, material_candidate, post_material_cache = None, None, None
    ca_api=geometry_code["ca_api"]
    calcium_rows,calcium_arithmetic,calcium_local,calcium_pump_local=[],{},{},{}
    calcium_codes={name:ca_api[name].__code__ for name in ("ca_handler","pumpCaATP","no_negs")}
    calcium_error,helper_returned=False,False
    source_times=None
""",
)
change(
    """        local = frame.f_locals
        field_name = next(""",
    """        nonlocal calcium_error,helper_returned
        local = frame.f_locals
        calcium_name=next((key for key,code in calcium_codes.items() if frame.f_code is code),None)
        if calcium_name is not None:
            if calcium_name=="no_negs" and frame.f_back is not None and frame.f_back.f_code is calcium_codes["pumpCaATP"]:
                owner=frame.f_back.f_locals
                label="membrane" if local["data"] is owner["cCai"] else "bath"
                if event in ("call","return"):
                    calcium_arithmetic[("before" if event=="call" else "after")+"_no_negs_"+label]=np.array(local["data"],copy=True)
            if event=="line" and calcium_name=="pumpCaATP" and "Qdenomo" in local and "inds_Z" not in local:
                calcium_arithmetic.setdefault("quotient_denominator_raw",np.array(local["Qdenomo"],copy=True))
            if event=="exception":calcium_error=True
            if event=="return":
                if calcium_name=="pumpCaATP":
                    calcium_pump_local.update({key:np.array(value,copy=True) for key,value in local.items() if isinstance(value,(np.ndarray,np.generic))})
                    helper_returned=arg is not None
                    if arg is not None:calcium_arithmetic["raw_flux_mol_m2_s"]=np.array(arg,copy=True)
                    names=dict(Qnumo="quotient_numerator",Qdenomo="quotient_denominator_used",Q="quotient",Keq="equilibrium",numo_E="forward_numerator",denomo_E="forward_denominator",frwd="forward",numo_Eb="backward_numerator_unused",denomo_Eb="backward_denominator_unused",bkwrd="backward_unused")
                    calcium_arithmetic.update({key:np.array(local[native],copy=True) for native,key in names.items() if native in local})
                    if "inds_Z" in local:calcium_arithmetic["zero_denominator_indices"]=np.array(local["inds_Z"][0],copy=True)
                elif calcium_name=="ca_handler":
                    calcium_local.update({key:np.array(value,copy=True) for key,value in local.items() if isinstance(value,(np.ndarray,np.generic))})
                    calcium_local["rate_aliases_handler_flux"]=hasattr(sim,"rate_CaATP") and local.get("f_CaATP") is sim.rate_CaATP
            return trace
        field_name = next(""",
)
anchor = '    definition = inputs["network"]\n'
helper = """    def rate_cache():
        return dict(present=hasattr(sim,"rate_CaATP"),value=network.clone(sim.rate_CaATP) if hasattr(sim,"rate_CaATP") else None)

    def clock(index):
        return dict(source_times_s=source_times.copy(),call_index=index,material_dt_sum_s=index*inputs["bootstrap"]["dt_s"])

    def calcium_call(index):
        nonlocal calcium_error,helper_returned,field_phase
        field_phase="calcium"
        calcium_arithmetic.clear();calcium_local.clear();calcium_pump_local.clear()
        calcium_error,helper_returned=False,False
        before=dict(mode="calcium",definition=network.clone(raw),values_before=values(),
            parameters={k:getattr(parameters,k) for k in ("cATP","cADP","cPi","KmCa_Ca","KmCa_ATP","deltaGATP","alpha_Ca","F","R")},
            alpha_Ca=parameters.alpha_Ca,rate_cache_before=rate_cache(),clock=clock(index),dt_s=parameters.dt,
            runtime_temperature_K=sim.T,block_unused=sim.CaATP_block.copy(),rho_pump=sim.rho_pump,
            met_unused=sim.met_concs,Ca_dyn=parameters.Ca_dyn,ER_executed=False)
        record=dict(before=copy.deepcopy(before),source_completed=False)
        calcium_rows.append(record)
        try:
            sim.ca_handler(cells,parameters)
            record["source_completed"]=True
        finally:
            record.update(arithmetic=copy.deepcopy(calcium_arithmetic),handler_locals=copy.deepcopy(calcium_local),
                helper_locals=copy.deepcopy(calcium_pump_local),helper_returned=helper_returned,
                rate_cache_after=rate_cache(),values_after=values(),source_exception_observed=calcium_error)
            if parameters.alpha_Ca>0:
                record["helper"]=dict(incoming_membrane_mM=before["values_before"]["membrane_mol_m3"][sim.iCa],
                    incoming_bath_mM=before["values_before"]["environment_mol_m3"][sim.iCa][cells.map_mem2ecm],
                    membrane_after_mM=calcium_pump_local.get("cCai"),bath_after_mM=calcium_pump_local.get("cCao"),
                    voltage_V=before["values_before"]["voltage_V"],runtime_temperature_K=sim.T,parameters=before["parameters"],
                    block_unused=before["block_unused"],met_unused=before["met_unused"],arithmetic=copy.deepcopy(calcium_arithmetic),
                    flux_mol_m2_s=calcium_arithmetic.get("raw_flux_mol_m2_s"),source_completed=helper_returned,
                    finite=all(np.isfinite(value).all() for value in (calcium_pump_local.get("cCai",np.nan),
                        calcium_pump_local.get("cCao",np.nan),sim.vm,*calcium_arithmetic.values())),failure=None)
            else:record["helper"]=None
        observe("calcium_handler")
        return copy.deepcopy(record)

"""
change(anchor, helper + anchor)
change(
    """    try:
        cold_cache = network.cold(ctx)
""",
    """    ca_api["calcium_defaults"](parameters,{"alpha_Ca":declared["calcium"]["alpha_Ca"]})
    ca_api["calcium_cold"](sim,cells,parameters)
    sim.ca_handler=MethodType(ca_api["ca_handler"],sim)
    sim.iCa=names.index("Ca")
    cold_policy=dict(Ca_dyn=parameters.Ca_dyn,CaATP_block=sim.CaATP_block.copy(),rho_pump=sim.rho_pump,
        met_concs=sim.met_concs,endo_retic=sim.endo_retic,rate_CaATP_present=hasattr(sim,"rate_CaATP"),
        parameters={k:getattr(parameters,k) for k in ("cATP","cADP","cPi","KmCa_Ca","KmCa_ATP","deltaGATP","alpha_Ca","F","R")})
    try:
        cold_cache = network.cold(ctx)
""",
)
change(
    """    cold_material = values()
""",
    """    cold_material = values()
    parameters.sim_tsteps=3
    parameters.dt=inputs["bootstrap"]["dt_s"]
    ctx.phase.kind=ca_api["SimPhaseKind"].SIM
    source_times=ca_api["source_clock"](ctx.phase)
""",
)
change(
    """                    steps=[network.clone(packet)],
""",
    """                    steps=[network.clone(packet)],calcium=network.clone(declared["calcium"]),rate_cache_before=rate_cache(),clock=clock(index),
""",
)
change(
    """                source["ordered"](sim, cells, parameters, float(index))
""",
    """                source["ordered"](sim, cells, parameters, float(source_times[index]))
                calcium_result=calcium_call(index)
                field_phase="material_network"
""",
)
change(
    """                source["resets"](sim, cells, parameters, float(index))
""",
    """                source["resets"](sim, cells, parameters, float(source_times[index]))
""",
)
change(
    """                network.run_dispatch(ctx, raw, call["publication"])
""",
    """                run_dispatch(ctx, raw, call["publication"],float(source_times[index]))
""",
)
change(
    """                            field=field_result,
""",
    """                            field=field_result,calcium=calcium_result,clock_before=clock(index),clock_after=clock(index+1),rate_cache_after=rate_cache(),
""",
)
change(
    """                        material_before=locals().get("material_before"),
""",
    """                        material_before=locals().get("material_before"),calcium=copy.deepcopy(calcium_rows[-1]) if calcium_rows else None,
""",
)
change(
    """        cold_cache=cold_cache,
""",
    """        cold_cache=cold_cache,cold_policy=cold_policy,source_times_s=source_times,calcium_rows=calcium_rows,
""",
)
source = source.replace(
    '"""Authenticated normal material/network plus complete native ECM field suffix.',
    '"""Authenticated normal ECM CaATP/GRN/full fields with source-disabled ER.',
)
path = ROOT / "validation/betse/betse_normal_ecm_calcium_join_native.py"
with path.open("x") as f:
    f.write(source)
print(path)
