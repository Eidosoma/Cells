# ruff: noqa: E501 -- emitted code is formatted separately.
"""Add a separate network boundary to the retained ECM material chronology."""

import ast
import copy
from pathlib import Path

ROOT = Path("/home/robert/Cells")
old = ast.parse((ROOT / "src/cells/processes/betse_ecm_transport.py").read_text())
step = copy.deepcopy(
    next(n for n in old.body if isinstance(n, ast.FunctionDef) and n.name == "step")
)
step.name = "material_step"
step.args.kwonlyargs = [ast.arg(arg="on_network"), ast.arg(arg="on_failure")]
step.args.kw_defaults = [None, None]
target = next(
    n
    for n in ast.walk(step)
    if isinstance(n, ast.With) and "np.errstate" in ast.unparse(n.items[0].context_expr)
)
point = next(
    i
    for i, n in enumerate(target.body)
    if isinstance(n, ast.Expr)
    and isinstance(n.value, ast.Call)
    and ast.unparse(n.value.func) == "observe"
    and ast.literal_eval(n.value.args[0]) == "supplied_late_flux"
)
target.body[point + 1 : point + 1] = ast.parse("""
if on_network is not None:
    on_network([cell,membrane,env,vm,fm,fg,fx_all,fy_all,vgj,egj,exy,opening])
    observe("ecm_grn_dispatch")
""").body
handler = step.body[-1].handlers[0]
handler.body[:0] = ast.parse("if on_failure is not None:\n    on_failure(locals())").body
header = '''"""Nonempty genuine GRN at the normal ECM late-network/deferred-commit boundary."""
import math
from dataclasses import dataclass,replace
from types import SimpleNamespace
import numpy as np
from cells.processes import betse_ecm_transport as material
from cells.processes import betse_environment_field as geometry_source
from cells.processes import betse_normal_current as current
from cells.processes import betse_normal_ion_join as ions
from cells.processes import betse_ecm_grn_source as source
LAW_ID="betse_normal_ecm_grn_network_v1_5_0@1"
validate_binding,state,drive=material.validate_binding,material.state,material.drive
State,Values,Frame,ECMRecord,Trial,ECMTransportRejected=(material.State,material.Values,material.Frame,material.ECMRecord,material.Trial,material.ECMTransportRejected)
freeze,_electroflux,_smooth=material.freeze,material._electroflux,material._smooth
MAX_STEPS=material.MAX_STEPS
'''
api = """

@dataclass(frozen=True)
class Binding:
    material_binding: object
    inputs: object
    identity: str


@dataclass(frozen=True)
class NetworkState:
    binding_identity: str
    material: object
    network_cache: object
    controls: object
    identity: str


class ECMNetworkRejected(RuntimeError):
    def __init__(self,error,partial):
        super().__init__(str(error))
        self.partial=freeze(partial)


def _state(binding,parent,cache,controls):
    cache,controls=freeze(cache),freeze(controls)
    return NetworkState(binding.identity,parent,cache,controls,ions.digest((binding.identity,parent,cache,controls)))


def bind(inputs):
    inputs=ions.data(inputs)
    mb=material.bind(inputs["definition"])
    source.validate(inputs["network"],mb)
    if len(inputs["steps"])!=3:
        raise ValueError("Require three declared bounded ECM network calls")
    for row in inputs["steps"]:
        if type(row["publication"]) is not bool:
            raise ValueError("Require actual source publication flags")
        material.drive(mb,row["material"])
    return Binding(mb,freeze(inputs),ions.digest((mb.identity,inputs)))


def make_context(binding,values,definition,packet=None):
    mb=binding.material_binding
    gb,k=mb.geometry_binding,mb.kernel
    cb,g=gb.current_binding,gb.geometry
    raw,external=mb.definition,gb.definition
    cg=cb.definition["geometry"]
    ep=external["parameters"]
    arrays=[np.asarray(value,np.float64) for value in values]
    sim=SimpleNamespace(**{attr:arrays[Values._fields.index(key)] for key,attr in source.MATERIAL_PAIRS},
        mdl=len(cb.membrane_ids),edl=math.prod(g.shape),
        zs=cb.kernel.valence,Dm_cells=k.membrane_diffusion_m2_s,D_gj=k.gap_diffusion_m2_s,
        D_env=k.environment_diffusion_m2_s,TJ_modulator=k.tight_junction_modulator)
    sim.E_gj_x,sim.E_gj_y=arrays[10][:,0],arrays[10][:,1]
    owner=cb.kernel.owner
    cells=SimpleNamespace(cell_i=np.arange(len(cb.cell_ids)),mem_i=np.arange(len(cb.membrane_ids)),
        mem_to_cells=owner,nn_i=k.partner,bflags_mems=k.boundary,gj_len=k.gap_length_m,
        mem_sa=cb.kernel.membrane_area_m2,cell_sa=cb.kernel.cell_area_m2,
        cell_vol=np.asarray(external["geometry"]["cell_volume_m3"],np.float64),
        cell_centres=np.asarray(external["geometry"]["cell_centres_m"],np.float64),
        mem_mids_flat=np.asarray(external["geometry"]["membrane_midpoints_m"],np.float64),
        X=g.X_m,Y=g.Y_m,xypts=g.grid_points_m,delta=g.delta_m,
        map_mem2ecm=g.membrane_to_grid,M_sum_mems=cb.kernel.owner_sum,
        memSa_per_envSquare=g.membrane_area_per_site_m2,M_divmap_mem2ecm=g.membrane_divergence_map_m2,
        ecm_vol=ep["cell_height_m"]*g.delta_m**2)
    p=SimpleNamespace(is_ecm=True,F=cb.kernel.F_C_mol,R=k.R_J_mol_K,T=ep["configured_temperature_K"],
        q=ep["q_C"],kb=ep["kb_J_K"],cell_height=ep["cell_height_m"],
        tm=k.membrane_thickness_m,cluster_open=k.cluster_open,fast_update_ecm=k.fast_update_ecm,
        sharpness=k.sharpness,fluid_flow=False,dt=0.0)
    m,e=len(cb.membrane_ids),math.prod(g.shape)
    sim.T=p.T
    sim.rho_channel=np.ones(m)
    sim.gj_block=np.asarray(definition["initial_controls"]["gj_block"],np.float64).copy()
    sim.NaKATP_block=np.asarray(definition["initial_controls"]["NaKATP_block"],np.float64).copy()
    sim.c_env_bound=np.asarray(definition["initial_ion_boundary"],np.float64).copy()
    for key,size in (("extra_rho_cells",len(cb.cell_ids)),("extra_rho_env",e),("extra_J_mem",m),("extra_Jenv_x",e),("extra_Jenv_y",e)):
        setattr(sim,key,np.zeros(size))
    sim.E_env_x,sim.E_env_y=np.zeros(g.shape),np.zeros(g.shape)
    if packet is not None:
        p.dt,sim.T=packet.dt_s,packet.runtime_temperature_K
        sim.rho_channel=packet.channel_multiplier
        sim.c_env_bound=packet.boundary_mol_m3.copy()
        sim.E_env_x,sim.E_env_y=packet.electric_x_source,packet.electric_y_source
    return source.augment(sim,cells,p,definition,list(cb.ion_ids))


def initialize(binding):
    parent=material.state(binding.material_binding,ions.data(binding.inputs["initial"]))
    definition=ions.data(binding.inputs["network"])
    ctx=make_context(binding,parent.values,definition)
    try:
        cached=source.cold(ctx)
    except Exception as error:
        raise ECMNetworkRejected(error,dict(stage="cold",cache=source.cache(ctx),material=parent)) from error
    return _state(binding,parent,cached,definition["initial_controls"])


def advance(binding,parent,*,before_network=None):
    if parent.binding_identity!=binding.identity or parent.identity!=ions.digest((binding.identity,parent.material,parent.network_cache,parent.controls)):
        raise ValueError("Changed ECM network parent")
    row=ions.data(binding.inputs["steps"][parent.material.step_index])
    control=ions.data(parent.controls) if row["scheduled_controls"] is None else row["scheduled_controls"]
    forcing=material.drive(binding.material_binding,dict(row["material"],junction_block=control["gj_block"]))
    holder={}
    def network(arrays):
        ctx=make_context(binding,arrays,ions.data(binding.inputs["network"]),forcing)
        holder["ctx"]=ctx
        source.restore(ctx,parent.network_cache)
        ctx.sim.gj_block=np.asarray(control["gj_block"],np.float64).copy()
        ctx.sim.NaKATP_block=np.asarray(control["NaKATP_block"],np.float64).copy()
        source.dispatch(ctx,ions.data(binding.inputs["definition"]),row["publication"],before_network)
    def failed(local):
        holder["material_partial"]=dict(frames=tuple(local.get("frames",())),environment_records=tuple(local.get("environment_records",())))
    try:
        trial=material_step(binding.material_binding,parent.material,forcing,on_network=network,on_failure=failed)
        ctx=holder["ctx"]
    except Exception as error:
        ctx=holder.get("ctx")
        partial=dict(stage="network" if ctx is not None else "material",material=holder.get("material_partial"),
            network=None if ctx is None else ctx.trace,cache=None if ctx is None else source.cache(ctx))
        raise ECMNetworkRejected(error,partial) from error
    candidate=_state(binding,trial.candidate,source.cache(ctx),ctx.trace["controls_after"])
    return candidate,trial,freeze(ctx.trace)
"""
with (ROOT / "src/cells/processes/betse_ecm_grn_join.py").open("x") as f:
    f.write(header + ast.unparse(ast.fix_missing_locations(step)) + "\n" + api)
print({"new_material_boundary_file": 1, "scientific_evaluations": 0})
