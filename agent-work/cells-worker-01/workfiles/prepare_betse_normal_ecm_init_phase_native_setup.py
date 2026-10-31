# ruff: noqa: E501
"""Stdlib extraction of independent original INIT setup and ECM NaK slices."""

import ast
import copy
import hashlib
import json
from pathlib import Path

ROOT = Path("/home/robert/Cells")
NATIVE = Path("/mnt/workspaces/Cells/betse-v1.5.0/betse")


def fn(path, name, owner=None):
    tree = ast.parse(path.read_text())
    if owner:
        tree = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == owner)
    return copy.deepcopy(
        next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name)
    )


def wrapper(name, args, statements):
    node = ast.parse("def " + name + "(" + args + "):\n    pass").body[0]
    node.body = copy.deepcopy(statements)
    return node


def main():
    init = fn(NATIVE / "science/sim.py", "init_dynamics", "Simulator")
    start = next(
        i
        for i, n in enumerate(init.body)
        if isinstance(n, ast.Assign) and ast.unparse(n.targets[0]) == "Dm_cellsA"
    )
    end = next(
        i
        for i, n in enumerate(init.body)
        if isinstance(n, ast.If) and ast.unparse(n.test) == "p.ions_dict['Ca'] == 1 and p.Ca_dyn"
    )
    static = wrapper("static_and_blocks", "self,cells,p,rng", init.body[start : end + 1])

    class RNG(ast.NodeTransformer):
        def visit_Attribute(self, node):
            if ast.unparse(node) == "np.random.random":
                return ast.Attribute(
                    value=ast.Name(id="rng", ctx=ast.Load()), attr="random", ctx=ast.Load()
                )
            return self.generic_visit(node)

    static = RNG().visit(static)
    loop = fn(NATIVE / "science/sim.py", "_run_sim_core_loop", "Simulator")
    outer = next(n for n in loop.body if isinstance(n, ast.For))
    first = next(
        i
        for i, n in enumerate(outer.body)
        if isinstance(n, ast.If) and ast.unparse(n.test) == "p.alpha_NaK == 0.0"
    )
    pump_slice = wrapper("nak_call", "self,cells,p", outer.body[first : first + 2])
    assert ast.unparse(outer.body[first + 1].test) == "p.alpha_NaK > 0.0"
    nodes = [static, fn(NATIVE / "science/sim_toolbox.py", "pumpNaKATP"), pump_slice]
    for name in ("_finalize_events_global", "_finalize_events_tissue"):
        node = fn(NATIVE / "science/tissue/tishandler.py", name, "TissueHandler")
        node.decorator_list = []
        node.returns = None
        for arg in node.args.args:
            arg.annotation = None
        if name == "_finalize_events_global":
            node.args.kwonlyargs.append(ast.arg(arg="shuffle"))
            node.args.kw_defaults.append(None)
        nodes.append(node)
    node = fn(NATIVE / "science/math/modulate.py", "f_sweep")
    node.returns = None
    nodes.append(node)
    # Parameter producer statements are literal, independent of the owned helper.
    parameters = ast.parse((NATIVE / "science/parameters.py").read_text())
    keys = {"cATP", "cADP", "cPi", "KmNK_Na", "KmNK_K", "KmNK_ATP", "deltaGATP"}
    defaults = [
        n
        for n in ast.walk(parameters)
        if isinstance(n, ast.Assign) and ast.unparse(n.targets[0]) in {"self." + k for k in keys}
    ]
    assert len(defaults) == len(keys)
    nodes.append(wrapper("nak_defaults", "self", defaults))
    header = '''# ruff: noqa: E731, F841
"""Independent literal INIT setup and pump source, never importing Cells.

These are bounded source slices/whole helpers on supplied pre-setup tissue/core
and conditional initializer-cache owners. No whole init_dynamics/load claim.
"""

import copy
import hashlib
import json
import random
import sys
from types import SimpleNamespace

import numpy as np

from validation.betse import betse_normal_ecm_catalog_join_native_network as network
from validation.betse import betse_normal_ecm_event_join_native_events as rng_native

'''
    tail = """

mod = SimpleNamespace(f_sweep=f_sweep)
stb = SimpleNamespace(pumpNaKATP=pumpNaKATP)
EndoRetic = None  # unreachable under the explicit ordinary Ca_dyn=False guard
STORES = ("T", "P_cells", "P_base", "P_mod", "div_u_osmo", "Dm_base", "Dm_scheduled", "Dm_cells", "D_env_base", "D_env", "D_free", "channel_noise_factor", "gj_block", "NaKATP_block", "CaATP_block", "rho_pump", "rho_channel", "met_concs", "endo_retic", "c_env_bound", "bound_V")


def snapshot(sim):
    return {key: network.clone(getattr(sim,key)) for key in STORES}


def document_hash(payload):
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def python_manifest(rng):
    payload = dict(kind="python.random.MT19937.full_state@1", implementation=sys.implementation.name,
                   python_version=list(sys.version_info[:3]), state=json.loads(json.dumps(rng.getstate())))
    return dict(payload, identity=document_hash(payload))


def tuples(value):
    return tuple(tuples(v) for v in value) if isinstance(value,(list,tuple)) else value


def callable_record(value):
    if callable(value):
        return dict(callable=True, evaluated=False, name=value.__name__, free_variables=list(value.__code__.co_freevars),
                    closure=[] if value.__closure__ is None else [None if c.cell_contents is None else c.cell_contents if isinstance(c.cell_contents,(int,float,str)) else type(c.cell_contents).__name__ for c in value.__closure__])
    return network.clone(value)


class Owner:
    def __init__(self, ctx, declaration):
        self.ctx, self.declaration = ctx, declaration
        raw = declaration["setup"]
        self.rng = rng_native.restore_rng(raw["numpy_rng"])
        self.python = random.Random(0)
        self.python.setstate(tuples(raw["python_rng"]["state"]))
        if python_manifest(self.python) != raw["python_rng"]:
            raise ValueError("Independent native Python setup stream mismatch")
        p, sim = ctx.p, ctx.sim
        p._run_sim = False
        ctx.phase.kind = "INIT"
        p.channel_noise_level = raw["channel_noise_level"]
        p.global_options = copy.deepcopy(raw["global_options"])
        p.scheduled_options = copy.deepcopy(raw["scheduled_options"])
        p.f_scan_properties = copy.deepcopy(raw["frequency_sweep"])
        p.Ca_dyn = False
        p.is_ecm = True
        sim.P_cells = np.zeros(sim.cdl)
        sim.D_env_base = sim.D_env.copy()
        sim.bound_V = dict(declaration["field"]["bootstrap"]["boundary_V"])
        before = sim.Dm_cells.copy()
        static_and_blocks(sim,ctx.cells,p,self.rng)
        sim.rho_pump = 1
        sim.rho_channel = 1
        sim.met_concs = None
        self.pre = dict(stage="pre_cold_static_setup", source_phase="INIT", legacy_run_sim=False, setup_draw_count=1,
                        numpy_rng_before=raw["numpy_rng"], numpy_rng_after=rng_native.manifest(self.rng),
                        python_rng_before=raw["python_rng"], static_uniforms=sim.channel_noise_factor.copy(),
                        static_level=p.channel_noise_level, static_diffusion_before=before, stores=snapshot(sim), receipts=raw["receipts"])
        nak_defaults(p)
        p.alpha_NaK = declaration["flags"]["alpha_NaK"]
        self.nak_history = []

    def finalize(self):
        ctx, raw = self.ctx, self.declaration["setup"]
        for key, values in raw["maps"].items():
            setattr(ctx.sim.dyna,key,copy.deepcopy(values))
        owner = SimpleNamespace(**{key: network.clone(value) for key,value in vars(ctx.sim.dyna).items()})
        _finalize_events_global(owner,ctx.phase,shuffle=self.python.shuffle)
        _finalize_events_tissue(owner,ctx.phase)
        return dict(stage="event_finalization_after_cold",global_options=raw["global_options"],scheduled_options=raw["scheduled_options"],
                    finalized_fields={key: callable_record(value) for key,value in vars(owner).items()},
                    frequency_sweep_after=copy.deepcopy(ctx.p.f_scan_properties),python_rng_before=raw["python_rng"],python_rng_after=python_manifest(self.python),
                    event_fire_calls=0,dynamic_noise_calls=0,dynamic_noise_configuration=raw["dynamic_noise"],source_phase="INIT",legacy_run_sim=False)

    def pump(self, values):
        ctx, p, sim = self.ctx, self.ctx.p, self.ctx.sim
        packet = dict(alpha_NaK=p.alpha_NaK,block=np.broadcast_to(sim.NaKATP_block,(sim.mdl,)).copy(),rho_pump=np.broadcast_to(sim.rho_pump,(sim.mdl,)).copy(),met_concs=None)
        before = dict(mode="nak",definition=copy.deepcopy(self.declaration["field"]["definition"]),values_before=values(),
                      parameters={k:getattr(p,k) for k in ("cATP","cADP","cPi","KmNK_Na","KmNK_K","KmNK_ATP","deltaGATP")},
                      packet=packet,incoming_rate=dict(present=hasattr(sim,"rate_NaKATP"),value=network.clone(getattr(sim,"rate_NaKATP",None))),
                      runtime_temperature_K=sim.T,boundary=ctx.cells.bflags_mems.copy(),cluster_open=p.cluster_open,source_phase="INIT",legacy_run_sim=False)
        raw = {}
        previous = sys.gettrace()
        fields = dict(Qnumo="quotient_numerator",Qdenomo="quotient_denominator_used",Q="quotient",Keq="equilibrium",numo_E="saturation_numerator",denomo_E="saturation_denominator",fwd_co="saturation",f_Na="raw_sodium_flux_mol_m2_s",f_K="raw_potassium_flux_mol_m2_s")
        def trace(frame,event,arg):
            if previous is not None:
                previous(frame,event,arg)
            if frame.f_code is pumpNaKATP.__code__:
                local=frame.f_locals
                if event=="line" and "Qdenomo" in local and "inds_Z" not in local:
                    raw.setdefault("quotient_denominator_raw",np.array(local["Qdenomo"],copy=True))
                if event=="return":
                    raw.update({key:network.clone(local[native]) for native,key in fields.items() if native in local})
                    if "inds_Z" in local:
                        raw["zero_denominator_indices"]=local["inds_Z"][0].copy()
                    if arg is not None:
                        raw["raw_rate_proxy_mol_m2_s"]=arg[2].copy()
            return trace
        completed=False
        try:
            sys.settrace(trace)
            nak_call(sim,ctx.cells,p)
            completed=True
        finally:
            sys.settrace(previous)
            result=dict(before=before,arithmetic=raw if p.alpha_NaK>0 else None,applied_flux=sim.fluxes_mem.copy(),
                        raw_rate_proxy=network.clone(getattr(sim,"rate_NaKATP",None)),source_completed=completed)
            self.nak_history.append(copy.deepcopy(result))
        return result
"""
    output = ROOT / "validation/betse/betse_normal_ecm_init_phase_native_setup.py"
    with output.open("x") as stream:
        stream.write(
            header + "\n\n".join(ast.unparse(ast.fix_missing_locations(n)) for n in nodes) + tail
        )
    proof = dict(
        kind="cells.init_native_setup_generation@1",
        scientific_execution=False,
        statements=dict(
            static=[init.body[start].lineno, init.body[end].end_lineno],
            pump=[outer.body[first].lineno, outer.body[first + 1].end_lineno],
        ),
        native_sha256={
            str(p.relative_to(NATIVE)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in (
                NATIVE / "science/sim.py",
                NATIVE / "science/sim_toolbox.py",
                NATIVE / "science/parameters.py",
                NATIVE / "science/tissue/tishandler.py",
                NATIVE / "science/math/modulate.py",
            )
        },
    )
    with (
        ROOT
        / "agent-work/cells-worker-01/workfiles/betse_normal_ecm_init_phase_native_setup_generation_01.json"
    ).open("x") as stream:
        json.dump(proof, stream, indent=2)
        stream.write("\n")


if __name__ == "__main__":
    main()
