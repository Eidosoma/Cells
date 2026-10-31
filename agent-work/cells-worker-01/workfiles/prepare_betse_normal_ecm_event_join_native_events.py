# ruff: noqa: E501
"""Emit independent native event helpers; no import/execute of scientific code."""

import ast
from pathlib import Path

ROOT = Path("/home/robert/Cells")
WORK = ROOT / "agent-work/cells-worker-01/workfiles"
PREFIX = "betse_normal_ecm_event_join"
generator = ast.parse((WORK / f"prepare_{PREFIX}_source.py").read_text())
definitions = [
    n
    for n in generator.body
    if isinstance(n, (ast.ClassDef, ast.FunctionDef)) and n.name in ("Clean", "literal_nodes")
]
text = ast.unparse(ast.Module(body=definitions, type_ignores=[]))
# The native body uses the unmodified NumPy draw call, through its local proxy.
text = text.replace("branch = DrawInterface().visit(branch)", "branch = branch")
header = '''# ruff: noqa: E501
"""Independent authenticated original AST events and local native RNG replay."""
import ast
import copy
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np

from validation.betse import betse_normal_ecm_catalog_join_native_network as network

PROTOCOL=Path(__file__).with_name("betse_normal_ecm_event_join_protocol.json")
STORES=("T","c_env_bound","gj_block","NaKATP_block","rho_channel","bound_V","Dm_base","Dm_scheduled","Dm_cells",
    "D_env_base","D_env","D_env_weight_base","D_env_weight","D_free","P_base","P_mod","P_cells")
clone=network.clone
RNG_ID="numpy_mt19937_legacy_state_with_gaussian_cache@1"
'''
body = """
def manifest(rng):
    state=rng.get_state()
    values=[state[0],state[1].tolist(),int(state[2]),int(state[3]),float(state[4])]
    payload=dict(rng_id=RNG_ID,numpy_version=np.__version__,state=values)
    identity=hashlib.sha256(json.dumps(payload,sort_keys=True,separators=(",",":"),allow_nan=False).encode()).hexdigest()
    return dict(payload,identity=identity)


def restore_rng(saved):
    if saved["rng_id"]!=RNG_ID or saved["numpy_version"]!=np.__version__:
        raise ValueError("Require the supplied native MT19937 law/version")
    data=saved["state"];rng=np.random.RandomState(0)
    rng.set_state((data[0],np.asarray(data[1],np.uint32),data[2],data[3],data[4]))
    if manifest(rng)!=saved:raise ValueError("Supplied native RNG identity differs")
    return rng


def snapshot(sim):
    return {name:clone(getattr(sim,name)) for name in STORES}


class NumpyProxy:
    def __init__(self,random):self.random=SimpleNamespace(random=random)
    def __getattr__(self,name):return getattr(np,name)


def authenticated(random):
    pins=json.loads(PROTOCOL.read_text())["native_source"]
    for name,digest in pins["source_sha256"].items():
        data=(Path(pins["checkout"])/name).read_bytes()
        if hashlib.sha256(data).hexdigest()!=digest or data!=(Path(pins["installed_package"]).parent/name).read_bytes():
            raise ValueError("Pinned native event source changed: "+name)
    root=Path(pins["checkout"])/"betse"
    nodes=literal_nodes(root)
    # Add original pure temporal factories, never production helpers.
    mod=ast.parse((root/"science/math/modulate.py").read_text())
    nodes += [Clean().visit(copy.deepcopy(n)) for n in mod.body if isinstance(n,ast.FunctionDef) and n.name in ("periodic","f_sweep")]
    # Original flux-reset and SIM event guard fragments.
    sim=ast.parse((root/"science/sim.py").read_text())
    cls=next(n for n in sim.body if isinstance(n,ast.ClassDef) and n.name=="Simulator")
    core=next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name=="_run_sim_core_loop")
    loop=next(n for n in core.body if isinstance(n,ast.For))
    reset=[copy.deepcopy(n) for n in loop.body if
        isinstance(n,ast.Expr) and ast.unparse(n) in ("self.fluxes_mem.fill(0)","self.fluxes_gj.fill(0)")
        or isinstance(n,ast.If) and ast.unparse(n.test)=="p.is_ecm" and "self.fluxes_env_x =" in ast.unparse(n)]
    guard=[copy.deepcopy(n) for n in loop.body if isinstance(n,ast.If) and "phase.dyna.fire_events" in ast.unparse(n)]
    for name,args,body in (("reset_fluxes","self,p",reset),("fire_events_guarded","phase,t",guard)):
        fn=ast.parse("def "+name+"("+args+"):\\n pass").body[0];fn.body=body;nodes.append(fn)
    ns=dict(np=NumpyProxy(random),SimpleNamespace=SimpleNamespace,
        SimPhaseKind=SimpleNamespace(SIM="SIM",INIT="INIT"),logs=SimpleNamespace(log_info=lambda *_:None))
    exec(compile(ast.fix_missing_locations(ast.Module(body=nodes,type_ignores=[])),"<original native event and protein-noise bodies>","exec"),ns)
    ns["tb"]=ns["toolbox"]=SimpleNamespace(pulse=ns["pulse"])
    ns["stb"]=SimpleNamespace(update_Co=network.science()["update_Co"])
    return ns


class Owner:
    def __init__(self,ctx,declared):
        self.ctx,self.declared=ctx,declared
        self.rng=restore_rng(declared["prepared_rng"]["manifest"])
        self.draws=[]
        self.api=authenticated(self.random)
        self.install()

    def random(self,size):
        if size!=self.ctx.sim.mdl:raise ValueError("Native noise draw size changed")
        before=manifest(self.rng)
        values=self.rng.random(size)
        self.draws.append(dict(values=values.copy(),stream_before=before,stream_after=manifest(self.rng)))
        return values

    def install(self):
        ctx=self.ctx;declaration=self.declared["event_owner"]
        handler=object.__new__(self.api["TissueHandler"])
        vars(handler).update(clone(declaration["handler_fields"]))
        handler.tissue_default=SimpleNamespace(**clone(declaration["tissue_default"]))
        for key in ("tissue_target_inds","cell_target_inds","env_target_inds"):
            setattr(handler,key,clone(declaration[key]))
        handler.event_cut=declaration["event_cut"]
        if declaration["voltage"] is None:handler._event_voltage=None
        else:
            voltage=object.__new__(self.api["SimEventPulseVoltage"])
            vars(voltage).update(clone(declaration["voltage"]))
            handler._event_voltage=voltage
        for suffix,record in declaration["callbacks"].items():
            program=record["dynamic"]
            if program["kind"]=="constant":dynamic=lambda t:1
            elif program["kind"]=="periodic":
                p=SimpleNamespace(periodic_properties={"frequency":program["frequency"],"phase":program["phase"]})
                _,dynamic=self.api["periodic"]([],ctx.cells,p)
            elif program["kind"]=="sweep":
                p=SimpleNamespace(f_scan_properties={"f start":program["start"],"f slope":program["slope"]})
                _,dynamic=self.api["f_sweep"]([],ctx.cells,p)
            else:raise ValueError("Unknown supplied native temporal callback")
            setattr(handler,"dyna_"+suffix,dynamic)
            scalar=record["source_scalar"]
            setattr(handler,"scalar_"+suffix,np.asarray(scalar,np.float64) if isinstance(scalar,(list,tuple)) else scalar)
        handler._observe=lambda *_:None
        ctx.p.global_options=clone(declaration["global_options"])
        ctx.p.scheduled_options=clone(declaration["scheduled_options"])
        ctx.p.env_concs=clone(declaration["configured_environment"])
        ctx.p.dynamic_noise=self.declared["noise"]["enabled"]
        ctx.p.dynamic_noise_level=self.declared["noise"]["level_mol_m2_s"]
        for key,value in self.declared["entry_event_state"].items():
            setattr(ctx.sim,key,np.asarray(value,np.float64).copy() if isinstance(value,list) else clone(value))
        for role in ("Na","K","Cl","Ca","M","P"):
            ctx.p.ions_dict[role]=int(role in ctx.ion_ids)
            if role in ctx.ion_ids:setattr(ctx.sim,"i"+role,ctx.ion_ids.index(role))
        cache=self.declared["noise_cache"]
        if cache["present"]:ctx.sim.protein_noise_flux=np.asarray(cache["value"],np.float64).copy()
        ctx.sim.dyna=ctx.phase.dyna=handler

    def fire(self,t):
        result=dict(before=snapshot(self.ctx.sim),source_time_s=float(t),stages=[],source_completed=False)
        self.ctx.phase.dyna._observe=lambda stage,sim:result["stages"].append(dict(stage=stage,state=snapshot(sim)))
        try:
            self.api["fire_events_guarded"](self.ctx.phase,t)
            result["source_completed"]=True
        finally:result["after"]=snapshot(self.ctx.sim)
        return result

    def preview(self,index):
        sim,p=self.ctx.sim,self.ctx.p
        if not (p.dynamic_noise==1 and p.ions_dict["P"]==1):return None,manifest(self.rng)
        copy_rng=restore_rng(manifest(self.rng))
        return copy_rng.random(sim.mdl),manifest(copy_rng)

    def noise(self):
        ctx=self.ctx
        before=network.material_values(ctx.sim)
        start=manifest(self.rng);self.draws.clear()
        result=dict(before=before,stream_before=start,source_completed=False)
        try:
            self.api["protein_noise"](ctx.sim,ctx.cells,ctx.p,ctx.phase)
            result["source_completed"]=True
        finally:
            result.update(after=network.material_values(ctx.sim),draws=clone(self.draws),stream_after=manifest(self.rng),
                cache_present=hasattr(ctx.sim,"protein_noise_flux"),
                cache_value=clone(ctx.sim.protein_noise_flux) if hasattr(ctx.sim,"protein_noise_flux") else None)
        return result
"""
destination = ROOT / "validation/betse" / f"{PREFIX}_native_events.py"
with destination.open("x") as stream:
    stream.write(header + "\n" + text + "\n" + body)
print("Wrote independent native event/noise helper code; scientific AST not executed")
