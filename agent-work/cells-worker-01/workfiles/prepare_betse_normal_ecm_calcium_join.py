# ruff: noqa: E501 -- emitted implementation template is formatted separately.
"""Assemble the separate ECM CaATP boundary as text/AST only."""

import ast
import copy
from pathlib import Path

ROOT = Path("/home/robert/Cells")


def functions(path):
    return {
        n.name: n for n in ast.parse(Path(path).read_text()).body if isinstance(n, ast.FunctionDef)
    }


oldpath = ROOT / "src/cells/processes/betse_ecm_grn_join.py"
old = oldpath.read_text()
head = old[: old.index('@np.errstate(all="ignore")')]
head = head.replace(
    "from cells.processes import betse_ecm_grn_source as source\n",
    "from cells.processes import betse_ecm_grn_source as source\n"
    "from cells.processes import betse_calcium_atp_source as calcium_source\n"
    "from cells.processes import betse_normal_ecm_field_join as full\n",
)
head = head.replace(
    'LAW_ID = "betse_normal_ecm_grn_network_v1_5_0@1"',
    'LAW_ID = "betse_normal_ecm_calcium_field_join_v1_5_0@1"',
)
material = copy.deepcopy(functions(oldpath)["material_step"])
material.name = "_material_step"
material.args.kwonlyargs.append(ast.arg(arg="on_calcium"))
material.args.kw_defaults.append(None)


class CalciumHook(ast.NodeTransformer):
    def visit_AugAssign(self, node):
        if ast.unparse(node) == "fm += forcing.supplied_late_membrane_flux_mol_m2_s":
            return ast.parse(
                'on_calcium([cell,membrane,env,vm,fm,fg,fx_all,fy_all,vgj,egj,exy,opening])\nobserve("calcium_handler")'
            ).body + [node]
        return node


material = CalciumHook().visit(material)
dispatch = copy.deepcopy(
    functions(ROOT / "src/cells/processes/betse_ecm_grn_source.py")["run_dispatch"]
)
dispatch.name = "run_dispatch"
dispatch.args.args.insert(3, ast.arg(arg="source_time_s"))
for node in ast.walk(dispatch):
    if isinstance(node, ast.Call) and ast.unparse(node.func) == "science()['dispatch']":
        node.args[1] = ast.Name(id="source_time_s", ctx=ast.Load())
# Qualified bridge globals live on source; do not recreate a scientific owner.
for node in ast.walk(dispatch):
    if (
        isinstance(node, ast.Name)
        and isinstance(node.ctx, ast.Load)
        and node.id in ("attach", "science", "cache", "material_values", "owner_evidence", "clone")
    ):
        node.id = "source." + node.id

body = """

@dataclass(frozen=True)
class Binding:
    material_binding:object
    voltage_binding:object
    inputs:object
    calcium:object
    identity:str


@dataclass(frozen=True)
class RateCache:
    present:bool
    value:object


@dataclass(frozen=True)
class Clock:
    source_times_s:object
    call_index:int
    material_dt_sum_s:float


@dataclass(frozen=True)
class CalciumFieldState:
    binding_identity:str
    network:object
    field:object
    rate_cache:RateCache
    clock:Clock
    identity:str


class CalciumJoinRejected(RuntimeError):
    def __init__(self,error,partial):
        super().__init__(str(error))
        self.partial=freeze(partial)


def parameters(binding):
    # Original Parameters producers, individually authenticated by static AST.
    return dict(cATP=1.5,cADP=0.1,cPi=0.1,KmCa_Ca=1.0e-3,KmCa_ATP=0.5,
        deltaGATP=-37000,alpha_Ca=binding.calcium["alpha_Ca"],F=96485,R=8.314)


def native_policy(ctx,binding):
    # Native cold producers. No source path initializes rate_CaATP here.
    ctx.p.Ca_dyn=False
    ctx.sim.CaATP_block=np.ones(ctx.sim.mdl)
    ctx.sim.rho_pump=1
    ctx.sim.met_concs=None
    ctx.sim.endo_retic=None
    for key,value in parameters(binding).items():setattr(ctx.p,key,value)
    return dict(Ca_dyn=ctx.p.Ca_dyn,CaATP_block=ctx.sim.CaATP_block,rho_pump=ctx.sim.rho_pump,
        met_concs=ctx.sim.met_concs,endo_retic=ctx.sim.endo_retic,
        rate_CaATP_present=hasattr(ctx.sim,"rate_CaATP"),parameters=parameters(binding))


def bind(raw):
    raw=ions.data(raw)
    if set(raw)!={"kind","case_id","case_role","field","calcium"} or raw["kind"]!="cells.normal_ecm_calcium_join_inputs@1":
        raise ValueError("Require separately declared native ECM calcium composition")
    policy=raw["calcium"]
    if set(policy)!={"kind","Ca_dyn","alpha_Ca","provenance"} or policy["kind"]!="cells.native_ECM_CaATP_configuration@1":
        raise ValueError("Derive native maintained pools, Km, blocks and rate-cache absence")
    if type(policy["Ca_dyn"]) is not bool or policy["Ca_dyn"] is not False:
        raise ValueError("Native ordinary ER is disabled; no forced Ca_dyn or missing kinetics")
    if type(policy["alpha_Ca"]) not in (int,float) or not math.isfinite(policy["alpha_Ca"]) or policy["alpha_Ca"]<0:
        raise ValueError("Require finite nonnegative configured native alpha_Ca")
    if not isinstance(policy["provenance"],str) or not policy["provenance"].strip():
        raise ValueError("Require calcium source provenance")
    base=full.bind(raw["field"])
    cb=base.material_binding.geometry_binding.current_binding
    if "Ca" not in cb.ion_ids or cb.kernel.valence[cb.ion_ids.index("Ca")]!=2:
        raise ValueError("Require a real Ca+2 ion role and complete material arrays")
    if cb.kernel.F_C_mol!=96485 or base.material_binding.kernel.R_J_mol_K!=8.314:
        raise ValueError("Require the original native CaATP F and R producers")
    dt=base.inputs["bootstrap"]["dt_s"]
    if any(row["material"]["dt_s"]!=dt for row in base.inputs["steps"]):
        raise ValueError("Require one configured dt for the actual normal source clock")
    return Binding(base.material_binding,base.voltage_binding,base.inputs,freeze(policy),
        ions.digest((LAW_ID,base.identity,policy)))


def record(parent):
    return (parent.binding_identity,parent.network,parent.field,parent.rate_cache,parent.clock)


def joined_state(binding,network,fields,rate_cache,clock):
    result=CalciumFieldState(binding.identity,network,fields,rate_cache,clock,"")
    return replace(result,identity=ions.digest(record(result)))


def initialize(binding,*,after_cold=None,before_field=None):
    parent=material.state(binding.material_binding,ions.data(binding.inputs["initial"]))
    working=Values(*(np.array(v,copy=True) for v in parent.values))
    ctx=network.make_context(binding,working,ions.data(binding.inputs["network"]))
    policy=native_policy(ctx,binding)
    try:cached=source.cold(ctx)
    except Exception as error:
        raise CalciumJoinRejected(error,dict(stage="cold",policy=policy,**network._failure_snapshot(ctx,None))) from error
    parent=material.state(binding.material_binding,source.material_values(ctx.sim))
    initial=network._state(binding,parent,cached,ions.data(binding.inputs["network"])["initial_controls"])
    dt=binding.inputs["bootstrap"]["dt_s"]
    clock=Clock(ions.freeze(np.linspace(0,3*dt,3)),0,0.0)
    rate=RateCache(False,None)
    if after_cold is not None:after_cold(dict(network=initial,policy=policy,rate_cache=rate,clock=clock))
    try:
        prepared,fields=full.reconstruct(binding,initial,dt,ions.data(binding.inputs["bootstrap"]["boundary_V"]),"bootstrap",before_field)
    except full.FieldJoinRejected as error:
        raise CalciumJoinRejected(error,dict(stage="bootstrap",partial=error.partial,rate_cache=rate,clock=clock)) from error
    return joined_state(binding,prepared,fields,rate,clock)


def calcium(binding,arrays,forcing,incoming,clock,observer=None):
    values={key:ions.freeze(np.asarray(value)) for key,value in zip(Values._fields,arrays,strict=True)}
    cb=binding.material_binding.geometry_binding.current_binding
    i=cb.ion_ids.index("Ca")
    mapping=binding.material_binding.geometry_binding.geometry.membrane_to_grid
    before=dict(mode="calcium",definition=ions.data(binding.inputs["definition"]),
        values_before=values,parameters=parameters(binding),alpha_Ca=binding.calcium["alpha_Ca"],
        rate_cache_before=ions.data(incoming),clock=ions.data(clock),dt_s=forcing.dt_s,
        runtime_temperature_K=forcing.runtime_temperature_K,block_unused=np.ones(len(cb.membrane_ids)),
        rho_pump=1,met_unused=None,Ca_dyn=False,ER_executed=False)
    if observer is not None:observer(source.clone(before))
    phase=dict(before=freeze(before),helper=None,source_completed=False,rate_cache_after=incoming)
    membrane,env,vm,fm=arrays[1],arrays[2],arrays[3],arrays[4]
    rate=incoming
    try:
        if binding.calcium["alpha_Ca"]>0:
            core=None
            try:
                core=calcium_source.evaluate(membrane_mM=membrane[i],bath_mM=env[i][mapping],voltage_V=vm,
                    runtime_temperature_K=forcing.runtime_temperature_K,parameters=parameters(binding),
                    block=np.ones(len(cb.membrane_ids)),met=None)
            except calcium_source.CalciumSourceRefused as error:
                core=error.partial
                raise
            finally:
                if core is not None:
                    phase["helper"]=core
                    membrane[i]=core.membrane_after_mM
            # Native ECM co is a fancy-index copy: never copy its clipping back.
            if not core.finite:raise ValueError("Nonfinite actual CaATP helper trial; stricter finite admission")
            masked=1*core.flux_mol_m2_s.copy()
            if not binding.material_binding.kernel.cluster_open:masked[cb.kernel.owner*0+np.asarray(binding.inputs["definition"]["junction_geometry"]["boundary"],bool)] = 0
            rate=RateCache(True,ions.freeze(masked))
            fm[i]+=1*masked
        phase.update(source_completed=True,rate_cache_after=rate,
            source_rate_aliases_handler_flux=binding.calcium["alpha_Ca"]>0,
            source_rate_aliases_helper_flux=False)
        return rate,freeze(dict(phase,values_after={key:ions.freeze(np.asarray(value)) for key,value in zip(Values._fields,arrays,strict=True)}))
    except Exception as error:
        phase.update(values_after={key:ions.freeze(np.asarray(value)) for key,value in zip(Values._fields,arrays,strict=True)})
        raise CalciumJoinRejected(error,dict(stage="calcium",phase=phase)) from error


def advance(binding,parent,*,before_material=None,before_calcium=None,before_network=None,before_field=None,after_calcium=None,after_material=None):
    if type(parent) is not CalciumFieldState or parent.binding_identity!=binding.identity or parent.identity!=ions.digest(record(parent)):
        raise ValueError("Require the unchanged owned calcium/field parent")
    fields=parent.field
    if type(fields) is not full.FieldStage or fields.binding_identity!=binding.identity or fields.identity!=ions.digest(full.field_record(fields)):
        raise ValueError("Require the actual previous reconstructed full field")
    rate=parent.rate_cache
    m=len(binding.material_binding.geometry_binding.current_binding.membrane_ids)
    if type(rate) is not RateCache or type(rate.present) is not bool or (rate.value is not None if not rate.present else not isinstance(rate.value,np.ndarray) or rate.value.shape!=(m,) or rate.value.dtype!=np.float64 or rate.value.flags.writeable or not np.isfinite(rate.value).all()):
        raise ValueError("Require actual rate-cache absence or complete immutable source-written rate")
    index=parent.network.material.step_index
    dt=binding.inputs["bootstrap"]["dt_s"]
    if type(parent.clock) is not Clock or parent.clock.call_index!=index or parent.clock.material_dt_sum_s!=index*dt or not np.array_equal(parent.clock.source_times_s,np.linspace(0,3*dt,3)):
        raise ValueError("Require original normal time vector and accumulated material dt")
    row=ions.data(binding.inputs["steps"][index])
    control=ions.data(parent.network.controls) if row["scheduled_controls"] is None else row["scheduled_controls"]
    forcing=material.drive(binding.material_binding,dict(row["material"],junction_block=control["gj_block"],
        electric_x_source=fields.environment.values.electric_x_source,electric_y_source=fields.environment.values.electric_y_source))
    material_inputs=dict(mode="material",definition=ions.data(binding.inputs["definition"]),initial=ions.data(parent.network.material.values._asdict()),
        steps=[source.clone(forcing._asdict())],calcium=ions.data(binding.calcium),rate_cache_before=ions.data(rate),clock=ions.data(parent.clock))
    if before_material is not None:before_material(material_inputs)
    holder={}
    def on_calcium(arrays):
        result,phase=calcium(binding,arrays,forcing,rate,parent.clock,before_calcium)
        holder.update(rate=result,calcium=phase)
        if after_calcium is not None:after_calcium(result,phase)
    def on_network(arrays):
        ctx=network.make_context(binding,arrays,ions.data(binding.inputs["network"]),forcing)
        holder["ctx"]=ctx
        source.restore(ctx,parent.network.network_cache)
        native_policy(ctx,binding)
        if holder["rate"].present:ctx.sim.rate_CaATP=holder["rate"].value.copy()
        ctx.sim.gj_block=np.asarray(control["gj_block"],np.float64).copy()
        ctx.sim.NaKATP_block=np.asarray(control["NaKATP_block"],np.float64).copy()
        run_dispatch(ctx,ions.data(binding.inputs["definition"]),row["publication"],float(parent.clock.source_times_s[index]),before_network)
    def failed(local):
        holder["material_partial"]=dict(frames=ions.data(tuple(local.get("frames",()))),environment_records=ions.data(tuple(local.get("environment_records",()))),
            trial=local.get("trial"),diagnostics=local.get("diagnostics"),failure=local.get("failure"),
            available_arrays={name:value.copy() for name,value in local.items() if isinstance(value,np.ndarray)})
    try:
        trial=_material_step(binding.material_binding,parent.network.material,forcing,on_network=on_network,on_failure=failed,on_calcium=on_calcium)
        ctx=holder["ctx"]
        candidate=network._state(binding,trial.candidate,source.cache(ctx),ctx.trace["controls_after"])
    except Exception as error:
        ctx=holder.get("ctx")
        raise CalciumJoinRejected(error,dict(stage="material_calcium_network",parent=parent,inputs=material_inputs,
            material=holder.get("material_partial"),calcium=holder.get("calcium"),network=None if ctx is None else ctx.trace,
            inner_partial=getattr(error,"partial",None),**network._failure_snapshot(ctx,parent.network.network_cache))) from error
    if after_material is not None:after_material(candidate,trial,ctx.trace,holder["calcium"])
    try:prepared,next_fields=full.reconstruct(binding,candidate,forcing.dt_s,row["boundary_V"],"field",before_field)
    except full.FieldJoinRejected as error:
        raise CalciumJoinRejected(error,dict(stage="field",parent=parent,material_parent=candidate,trial=trial,
            calcium=holder["calcium"],network=ctx.trace,partial=error.partial)) from error
    clock=Clock(parent.clock.source_times_s,index+1,(index+1)*dt)
    result=joined_state(binding,prepared,next_fields,holder["rate"],clock)
    return result,trial,freeze(ctx.trace),holder["calcium"],dict(material_parent=candidate,initial_field=fields,fields=next_fields,clock_before=parent.clock,clock_after=clock)
"""
head = head.replace(
    "from cells.processes import betse_ecm_grn_source as source\n",
    "from cells.processes import betse_ecm_grn_source as source\nfrom cells.processes import betse_ecm_grn_join as network\n",
)
out = (
    head
    + ast.unparse(ast.fix_missing_locations(material))
    + "\n\n"
    + ast.unparse(ast.fix_missing_locations(dispatch))
    + body
)
path = ROOT / "src/cells/processes/betse_normal_ecm_calcium_join.py"
with path.open("x") as f:
    f.write(out)
print(path)
