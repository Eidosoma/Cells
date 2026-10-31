# ruff: noqa: E501 -- literal source scaffold strings.
"""Emit original event/noise source adapters from AST only; never execute science."""

import ast
import copy
from pathlib import Path

ROOT = Path("/home/robert/Cells")
PIN = Path("/mnt/workspaces/Cells/betse-v1.5.0/betse")
DEST = ROOT / "src/cells/processes/betse_normal_ecm_event_join_source.py"


class Clean(ast.NodeTransformer):
    def visit_Expr(self, node):
        if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
            return None
        return self.generic_visit(node)

    def visit_FunctionDef(self, node):
        node.decorator_list = []
        node.returns = None
        for arg in (*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs):
            arg.annotation = None
        return self.generic_visit(node)


def literal_nodes(root):
    tree = ast.parse((root / "science/tissue/tishandler.py").read_text())
    handler = copy.deepcopy(
        next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "TissueHandler")
    )
    names = {"fire_events", "_fire_events_global", "_fire_events_tissue", "makeAllChanges"}
    handler.body = [
        Clean().visit(n) for n in handler.body if isinstance(n, ast.FunctionDef) and n.name in names
    ]
    # Observer additions affect only the orchestration wrapper after returned source calls.
    fire = next(n for n in handler.body if n.name == "fire_events")
    body = []
    for statement in fire.body:
        body.append(statement)
        if isinstance(statement, ast.Expr) and isinstance(statement.value, ast.Call):
            label = ast.unparse(statement.value.func).rsplit(".", 1)[-1]
            body += ast.parse("self._observe(" + repr(label) + ",phase.sim)").body
    fire.body = body
    tb = ast.parse((root / "science/math/toolbox.py").read_text())
    pulse = Clean().visit(
        copy.deepcopy(
            next(n for n in tb.body if isinstance(n, ast.FunctionDef) and n.name == "pulse")
        )
    )
    voltage_tree = ast.parse((root / "science/tissue/event/tisevevolt.py").read_text())
    voltage = copy.deepcopy(
        next(
            n
            for n in voltage_tree.body
            if isinstance(n, ast.ClassDef) and n.name == "SimEventPulseVoltage"
        )
    )
    voltage.bases = [ast.Name(id="object", ctx=ast.Load())]
    voltage.body = [
        Clean().visit(n)
        for n in voltage.body
        if isinstance(n, ast.FunctionDef) and n.name == "fire"
    ]
    simulator = ast.parse((root / "science/sim.py").read_text())
    cls = next(n for n in simulator.body if isinstance(n, ast.ClassDef) and n.name == "Simulator")
    core = next(
        n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == "_run_sim_core_loop"
    )
    branch = copy.deepcopy(
        next(
            n
            for n in ast.walk(core)
            if isinstance(n, ast.If) and "p.dynamic_noise == 1" in ast.unparse(n.test)
        )
    )

    class DrawInterface(ast.NodeTransformer):
        def visit_Call(self, node):
            if ast.unparse(node.func) == "np.random.random":
                node.func = ast.parse("p._native_random", mode="eval").body
            return self.generic_visit(node)

    branch = DrawInterface().visit(branch)
    noise = ast.parse("def protein_noise(self,cells,p,phase):\n    pass").body[0]
    noise.body = [branch]
    return [pulse, handler, voltage, noise]


HEADER = '''# ruff: noqa: B007, B905
"""Literal pre-step source events and post-GRN protein-noise interfaces.

Tissue/callback owners are explicit supplied post-finalization conditions.
No profile picking, mesh construction, native cold/restart or physics claim.
"""
from types import SimpleNamespace
import numpy as np
from cells.processes import betse_ecm_grn_source as material_source
from cells.processes import betse_normal_ecm_catalog_join_source as catalog_source
from cells.processes import betse_perturbations as perturbations
from cells.processes import betse_time_modulation as time_laws

clone=catalog_source.clone
SimPhaseKind=SimpleNamespace(SIM="SIM",INIT="INIT")
stb=SimpleNamespace(update_Co=material_source.update_Co)
'''
PLUMBING = """
EVENT_STORES=("T","c_env_bound","gj_block","NaKATP_block","rho_channel","bound_V",
    "Dm_base","Dm_scheduled","Dm_cells","D_env_base","D_env","D_env_weight_base","D_env_weight",
    "D_free","P_base","P_mod","P_cells")


def event_snapshot(sim):
    return {key:clone(getattr(sim,key)) for key in EVENT_STORES}


def prepared_callback(record):
    # Source-return spatial arrays already belong to the supplied finalized owner.
    # Keep full shape and occurrence order; do not gather/repair them by targets.
    kind=record["kind"]
    if kind=="constant":
        return lambda t:1
    if kind=="periodic":
        program=time_laws.periodic_program(frequency_Hz=record["frequency"],
            phase_rad=record["phase"],provenance=record["provenance"])
        # Qualified helper preserves literal multiplication order, with NumPy only.
        return lambda t:time_laws.evaluate(program,t,xp=np).value
    if kind=="sweep":
        program=time_laws.sweep_program(start_Hz=record["start"],stop_Hz=record["stop"],
            slope_Hz_s=record["slope"],duration_s=record["duration"],run_sim=True,
            provenance=record["provenance"])
        return lambda t:time_laws.evaluate(program,t,xp=np).value
    raise ValueError("Require explicit prepared constant/periodic/sweep callback ownership")


def install_owner(ctx,declaration,state,observer=None):
    handler=object.__new__(TissueHandler)
    # These are supplied actual handler fields, never guessed profile/initializer values.
    vars(handler).update(clone(declaration["handler_fields"]))
    handler.tissue_default=SimpleNamespace(**clone(declaration["tissue_default"]))
    for key in ("tissue_target_inds","cell_target_inds","env_target_inds"):
        setattr(handler,key,clone(declaration[key]))
    handler.event_cut=None # Declaration must separately prove/refuse this disabled prerequisite.
    saved=declaration["voltage"]
    if saved is None:
        handler._event_voltage=None
    else:
        voltage=object.__new__(SimEventPulseVoltage)
        vars(voltage).update(clone(saved))
        handler._event_voltage=voltage
    for suffix,record in declaration["callbacks"].items():
        setattr(handler,"dyna_"+suffix,prepared_callback(record["dynamic"]))
        scalar=record["source_scalar"]
        setattr(handler,"scalar_"+suffix,np.asarray(scalar,np.float64) if isinstance(scalar,(list,tuple)) else scalar)
    ctx.p.global_options=clone(declaration["global_options"])
    ctx.p.scheduled_options=clone(declaration["scheduled_options"])
    ctx.p.env_concs=clone(declaration["configured_environment"])
    for key,value in state.items():
        setattr(ctx.sim,key,clone(value))
    for ion in ("Na","K","Cl","Ca","M","P"):
        ctx.p.ions_dict[ion]=int(ion in ctx.ion_ids)
        if ion in ctx.ion_ids:setattr(ctx.sim,"i"+ion,ctx.ion_ids.index(ion))
    def observe(stage,sim):
        if observer is not None:observer(dict(stage=stage,state=event_snapshot(sim)))
    handler._observe=observe
    ctx.sim.dyna=ctx.phase.dyna=handler
    return handler


def fire(ctx,t,observer=None):
    before=event_snapshot(ctx.sim)
    result=dict(before=before,stages=[],source_time_s=float(t),source_completed=False)
    old=ctx.phase.dyna._observe
    def observe(stage,sim):
        snapshot=dict(stage=stage,state=event_snapshot(sim))
        result["stages"].append(snapshot)
        if observer is not None:observer(clone(snapshot))
    ctx.phase.dyna._observe=observe
    try:
        ctx.phase.dyna.fire_events(phase=ctx.phase,t=t)
        result["source_completed"]=True
    finally:
        result["after"]=event_snapshot(ctx.sim)
        ctx.phase.dyna._observe=old
    return result


def noise(ctx,stream,noise_binding,index,configuration,observer=None):
    result=dict(before=catalog_source.material_values(ctx.sim),stream_before=perturbations.native_stream_manifest(stream),
        draws=[],source_completed=False)
    active=stream
    def random(size):
        nonlocal active
        if size!=len(noise_binding.membrane_ids):
            raise ValueError("Require the actual complete membrane noise draw axis")
        draw,active=perturbations.sample_native(active,noise_binding,site="protein_flux",tick=index)
        result["draws"].append(perturbations.draw_manifest(draw,noise_binding))
        return draw.values.copy()
    ctx.p._native_random=random
    ctx.p.dynamic_noise=configuration["enabled"]
    ctx.p.dynamic_noise_level=configuration["level_mol_m2_s"]
    if observer is not None:observer(clone(result))
    try:
        protein_noise(ctx.sim,ctx.cells,ctx.p,ctx.phase)
        result["source_completed"]=True
    finally:
        result.update(after=catalog_source.material_values(ctx.sim),
            stream_after=perturbations.native_stream_manifest(active),
            cache_present=hasattr(ctx.sim,"protein_noise_flux"),
            cache_value=clone(ctx.sim.protein_noise_flux) if hasattr(ctx.sim,"protein_noise_flux") else None)
    return active,result
"""


if __name__ == "__main__":
    nodes = literal_nodes(PIN)
    text = (
        HEADER
        + "\n"
        + ast.unparse(ast.Module(body=nodes, type_ignores=[]))
        + "\ntb=toolbox=SimpleNamespace(pulse=pulse)\n"
        + PLUMBING
    )
    with DEST.open("x") as stream:
        stream.write(text)
    print("Wrote event/noise literal adapter scaffold; scientific modules not imported or executed")
