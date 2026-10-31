# ruff: noqa: B007, B905, E501, E402
"""Independent pinned-AST standalone GRN capture; production imports denied."""

import ast
import copy
import csv
import hashlib
import io
import json
import os
import traceback
from abc import ABCMeta
from collections import OrderedDict
from collections.abc import MutableMapping
from pathlib import Path
from types import SimpleNamespace

import numpy as np

from validation.betse import betse_ecm_grn_native_network as previous
from validation.betse import betse_environment_field_native as field_native
from validation.betse import betse_normal_grn_join_native as archive_native

clone, public, wire = previous.clone, previous.public, previous.wire
PROTOCOL = Path(__file__).with_name("betse_ecm_sim_grn_protocol.json")
_ACTIVE = None
_SCIENCE = None
CORE_METHODS = {
    "clear_cache",
    "write_data",
    "report",
    "init_saving",
    "export_eval_strings",
    "export_equations",
}


class Clean(ast.NodeTransformer):
    def visit_Expr(self, node):
        if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
            return None
        return self.generic_visit(node)

    def visit_FunctionDef(self, node):
        node.decorator_list, node.returns = ([], None)
        for arg in (*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs):
            arg.annotation = None
        return self.generic_visit(node)


def original_nodes(root):
    network = ast.parse((root / "science/chemistry/networks.py").read_text())
    core = Clean().visit(
        copy.deepcopy(
            next(
                (
                    n
                    for n in network.body
                    if isinstance(n, ast.ClassDef) and n.name == "MasterOfNetworks"
                )
            )
        )
    )
    core.body = [n for n in core.body if isinstance(n, ast.FunctionDef) and n.name in CORE_METHODS]
    core.bases = [ast.parse("base.MasterOfNetworks", mode="eval").body]
    owner = Clean().visit(
        copy.deepcopy(
            next(
                (
                    n
                    for n in ast.parse((root / "science/chemistry/gene.py").read_text()).body
                    if isinstance(n, ast.ClassDef) and n.name == "MasterOfGenes"
                )
            )
        )
    )
    run = next(
        (n for n in owner.body if isinstance(n, ast.FunctionDef) and n.name == "run_core_sim")
    )

    class Observe(ast.NodeTransformer):
        def visit_Expr(self, node):
            if isinstance(node.value, ast.Call) and ast.unparse(node.value.func) in {
                "self.reinitialize",
                "self.core.clear_cache",
                "self.core.run_loop",
                "self.core.write_data",
            }:
                name = ast.unparse(node.value.func).rsplit(".", 1)[-1]
                before = ast.parse("observe('before_" + name + "',self,phase,locals())").body
                after = ast.parse("observe('after_" + name + "',self,phase,locals())").body
                return before + [node] + after
            return node

    Observe().visit(run)
    runner = ast.parse((root / "science/simrunner.py").read_text())
    branch = next(
        (
            n
            for n in ast.walk(runner)
            if isinstance(n, ast.If)
            and ast.unparse(n.test) == "self._p.grn_unpickle_filename is None"
        )
    )
    start = ast.parse("def start_new(self,phase):\n    pass\n").body[0]
    start.body = Clean().visit(
        copy.deepcopy(ast.Module(body=branch.body, type_ignores=[]))
    ).body + [ast.Return(value=ast.Name(id="MoG", ctx=ast.Load()))]
    assignment = next((i for i, n in enumerate(start.body) if isinstance(n, ast.Assign)))
    start.body[assignment + 1 : assignment + 1] = ast.parse("created(MoG,phase)").body
    return [core, owner, start]


def literal_nodes(root):
    original = original_nodes(root)
    inherited = previous.literal_nodes(root)
    core = next(n for n in inherited if getattr(n, "name", None) == "MasterOfNetworks")
    core.body.extend(original[0].body)
    inherited = [
        n
        for n in inherited
        if getattr(n, "name", None) not in {"MasterOfGenes", "initialize_owner", "dispatch"}
    ]
    exceptions = ast.parse((root / "exceptions.py").read_text())
    conf = Clean().visit(
        copy.deepcopy(
            next(
                n
                for n in exceptions.body
                if isinstance(n, ast.ClassDef) and n.name == "BetseSimConfException"
            )
        )
    )
    return inherited + [conf, original[1], original[2]]


def science():
    global _SCIENCE
    if _SCIENCE is None:
        pins = json.loads(PROTOCOL.read_text())["native_source"]
        for name, digest in pins["source_sha256"].items():
            data = (Path(pins["checkout"]) / name).read_bytes()
            assert hashlib.sha256(data).hexdigest() == digest
            assert data == (Path(pins["installed_package"]).parent / name).read_bytes()
        ns = dict(
            np=np,
            copy=copy,
            csv=csv,
            open=capture_open,
            ABCMeta=ABCMeta,
            OrderedDict=OrderedDict,
            SimpleNamespace=SimpleNamespace,
            MappingMutableType=MutableMapping,
            types=SimpleNamespace(trim=repr),
            BetseMethodUnimplementedException=NotImplementedError,
            logs=SimpleNamespace(log_info=lambda *_: None, log_warning=lambda *_: None),
            tex_val=str,
            Mito=outside,
            mods=SimpleNamespace(),
            fd=SimpleNamespace(gradient=outside, divergence=outside, integrator=outside),
            div_env=outside,
            nernst_planck_flux=outside,
            observe=observe,
            created=created,
            plt=None,
            viz=None,
            fh=SimpleNamespace(saveSim=save_boundary),
            pathnames=SimpleNamespace(join=os.path.join),
            dirs=SimpleNamespace(make_unless_dir=directory_boundary),
        )
        exec(
            compile(
                ast.fix_missing_locations(
                    ast.Module(
                        body=literal_nodes(Path(pins["checkout"]) / "betse"), type_ignores=[]
                    )
                ),
                "<pinned standalone GRN>",
                "exec",
            ),
            ns,
        )
        ns["fd"] = SimpleNamespace(
            **{name: ns[name] for name in ("gradient", "divergence", "integrator")}
        )
        ns["stb"] = SimpleNamespace(
            molecule_mover=ns["molecule_mover"], no_negs=ns["no_negs"], map_to_cells=outside
        )
        _SCIENCE = ns
    return _SCIENCE


import math
from contextlib import contextmanager


def outside(*args, **kwargs):
    raise ValueError(
        "Standalone boundary excludes ECM, mitochondria, fluid, cuts and file restarts"
    )


def validate(inputs):
    if inputs.get("kind") != "cells.betse_ecm_sim_grn_inputs@1":
        raise ValueError("Require explicit standalone GRN phase inputs")
    scope = inputs["scope"]
    if inputs.get("is_ecm") is not True:
        raise ValueError("Require explicit ECM-enabled standalone phase")
    if scope["mitochondria"] is not False:
        raise ValueError("Standalone mitochondria require separate organelle state")
    if scope["fluid"] is not False or scope["cuts"] is not False:
        raise ValueError("Standalone fluid and cuts require separate phase dynamics")
    if scope["grn_unpickle_filename"] is not None:
        raise ValueError("File restart requires a separate persistence boundary")
    if not 1 <= len(inputs["calls"]) <= 3:
        raise ValueError("Require one to three bounded standalone invocations")
    for call in inputs["calls"]:
        values = [call[k] for k in ("dt_s", "total_s", "sample_s")]
        if any(type(v) not in (int, float) or not math.isfinite(v) or v <= 0 for v in values):
            raise ValueError("Require finite positive standalone clocks")
        if call["sample_s"] < call["dt_s"]:
            raise ValueError("Sampling below dt stalls the source sampling-index loop")
        if not 1 <= int(call["total_s"] / call["dt_s"]) <= 8:
            raise ValueError("Require one to eight source clock points")
        if call["raw_fault"] not in (None, "missing_Y_Dm"):
            raise ValueError("Undeclared standalone partial failure")
        if type(call["plot_cell"]) is not int:
            raise ValueError("Require an explicit integer plot-cell index")
    definition = inputs["material_definition"]
    external = definition["environment_geometry_definition"]
    ids = external["current_definition"]["ions"]["ids"]
    n = len(external["current_definition"]["geometry"]["cell_ids"])
    m = len(external["current_definition"]["geometry"]["membrane_ids"])
    if not (1 <= n <= 16 and 1 <= m <= 128 and 1 <= len(ids) <= 32):
        raise ValueError("Refuse unbounded original standalone ECM context")


def new_trace():
    return dict(events=[], steps=[], molecule_frames=[], mover_frames=[], io_events=[])


def make_context(inputs):
    definition, initial = inputs["material_definition"], inputs["initial"]
    external = definition["environment_geometry_definition"]
    current = external["current_definition"]
    g, ion = current["geometry"], current["ions"]
    n, m = len(g["cell_ids"]), len(g["owner"])
    rawp, transport = external["parameters"], definition["parameters"]
    sim = SimpleNamespace(
        cdl=n,
        mdl=m,
        edl=len(initial["environment_mol_m3"][0]),
        cc_cells=np.asarray(initial["cell_mol_m3"], np.float64).copy(),
        cc_at_mem=np.asarray(initial["membrane_mol_m3"], np.float64).copy(),
        cc_env=np.asarray(initial["environment_mol_m3"], np.float64).copy(),
        vm=np.asarray(initial["voltage_V"], np.float64).copy(),
        vgj=np.asarray(initial["junction_voltage_V"], np.float64).copy(),
        gjopen=np.asarray(initial["gap_open"], np.float64).copy(),
        zs=np.asarray(ion["valence"], np.float64),
        Dm_cells=np.asarray(definition["ions"]["membrane_diffusion_m2_s"], np.float64),
        D_env=np.asarray(definition["ions"]["environment_diffusion_m2_s"], np.float64),
        T=inputs["runtime_temperature_K"],
        rho_channel=np.asarray(inputs["rho_channel"], np.float64).copy(),
        gj_block=np.asarray(inputs["network"]["initial_controls"]["gj_block"], np.float64).copy(),
        NaKATP_block=np.asarray(
            inputs["network"]["initial_controls"]["NaKATP_block"], np.float64
        ).copy(),
        c_env_bound=np.asarray(inputs["network"]["initial_ion_boundary"], np.float64).copy(),
        time=clone(inputs["simulator_time_before"]),
        E_env_x=np.asarray(inputs["electric_x_source"], np.float64).copy(),
        E_env_y=np.asarray(inputs["electric_y_source"], np.float64).copy(),
    )
    for key, value in inputs["incoming_publication_fields"].items():
        setattr(sim, key, np.asarray(value, np.float64).copy())
    for key, attr in (
        ("membrane_flux_mol_m2_s", "fluxes_mem"),
        ("junction_flux_mol_m2_s", "fluxes_gj"),
        ("environment_flux_x_mol_m2_s", "fluxes_env_x"),
        ("environment_flux_y_mol_m2_s", "fluxes_env_y"),
        ("junction_field_source", "Egj"),
    ):
        setattr(sim, attr, np.asarray(initial[key], np.float64).copy())
    sim.E_gj_x, sim.E_gj_y = np.asarray(initial["junction_field_xy_source"], np.float64).T.copy()
    sim.get_ion = lambda name: ion["ids"].index(name)
    for name in ("Na", "K", "Cl"):
        setattr(sim, "i" + name, sim.get_ion(name))
    cells = SimpleNamespace(
        cell_i=np.arange(n),
        mem_i=np.arange(m),
        mem_to_cells=np.asarray(g["owner"], np.int64),
        cell_to_mems=[np.flatnonzero(np.asarray(g["owner"]) == i).tolist() for i in range(n)],
        nn_i=np.asarray(definition["junction_geometry"]["partner"], np.int64),
        bflags_mems=np.asarray(definition["junction_geometry"]["boundary"], bool),
        mem_sa=np.asarray(g["membrane_area_m2"], np.float64),
        cell_sa=np.asarray(g["cell_area_m2"], np.float64),
        cell_vol=np.asarray(external["geometry"]["cell_volume_m3"], np.float64),
        cell_centres=np.asarray(external["geometry"]["cell_centres_m"], np.float64),
        mem_mids_flat=np.asarray(external["geometry"]["membrane_midpoints_m"], np.float64),
        mem_vects_flat=np.column_stack((np.zeros((m, 2)), g["normal_xy"])),
        M_sum_mems=np.asarray([[int(i == o) for o in g["owner"]] for i in range(n)], np.float64),
        gj_len=np.asarray(definition["junction_geometry"]["gap_length_m"], np.float64),
        **{key: external["world"][key + "_m"] for key in ("xmin", "xmax", "ymin", "ymax")},
    )
    p = SimpleNamespace(
        F=current["parameters"]["F_C_mol"],
        R=transport["R_J_mol_K"],
        T=rawp["configured_temperature_K"],
        q=rawp["q_C"],
        kb=rawp["kb_J_K"],
        dt=inputs["initial_dt_s"],
        tm=transport["membrane_thickness_m"],
        cluster_open=transport["cluster_open"],
        fast_update_ecm=transport["fast_update_ecm"],
        sharpness=transport["sharpness"],
        is_ecm=True,
        fluid_flow=False,
        grid_size=external["world"]["grid_size"],
        cell_height=rawp["cell_height_m"],
        cell_space=rawp["cell_space_m"],
        ions_dict={name: 1 for name in ion["ids"]},
        substances_affect_charge=inputs["network"]["cold_publish"],
        plot_network=False,
        grn=SimpleNamespace(conf=clone(inputs["network"]["configuration"])),
        visual=SimpleNamespace(single_cell_index=0),
        grn_runmodesim=False,
        grn_unpickle_filename=None,
        grn_pickle_filename="/captured/grn/network.pickle",
        grn_pickle_dirname="/captured/grn",
    )
    p.ions_dict.setdefault("Ca", 0)
    build_grid(cells, p, inputs)
    cells.ecm_vol = p.cell_height * cells.delta**2
    for key, value in inputs["network"]["grid_index_groups"].items():
        setattr(cells, key, np.asarray(value, np.int64).copy())
    science()["derive_context"](sim, cells)
    phase = SimpleNamespace(sim=sim, cells=cells, p=p, kind="INIT", dyna=SimpleNamespace())
    return SimpleNamespace(
        inputs=inputs,
        sim=sim,
        cells=cells,
        p=p,
        phase=phase,
        owner=None,
        trace=new_trace(),
        files={},
        directories=[],
        before_step=None,
    )


@contextmanager
def active(ctx):
    global _ACTIVE
    previous = _ACTIVE
    _ACTIVE = ctx
    try:
        yield
    finally:
        _ACTIVE = previous


def created(owner, phase):
    assert phase is _ACTIVE.phase
    _ACTIVE.owner = owner


def snapshot(ctx):
    return dict(
        wire=wire(ctx.owner, ctx.sim),
        grid_fields={name: clone(getattr(ctx.cells, name)) for name in GRID_FIELDS},
        simulator=public(ctx.sim),
        parameters=public(ctx.p, {"grn", "visual"}),
        configuration=clone(ctx.p.grn.conf),
        visual=public(ctx.p.visual),
        captured_files=clone(ctx.files),
        directories=clone(ctx.directories),
    )


def configure_call(ctx, call):
    ctx.p.grn_dt, ctx.p.grn_total_time, ctx.p.grn_tsample = (
        call["dt_s"],
        call["total_s"],
        call["sample_s"],
    )
    ctx.p.visual.single_cell_index = call["plot_cell"]
    if call["raw_fault"] == "missing_Y_Dm":
        del ctx.p.grn.conf["biomolecules"][1]["Dm"]


def restore(ctx, incoming):
    if "wire" not in incoming or "owner_fields" not in incoming["wire"]:
        raise ValueError("Require complete standalone owner state")
    if "grid_fields" not in incoming or set(incoming["grid_fields"]) != set(GRID_FIELDS):
        raise ValueError("Require complete generated standalone ECM grid state")
    if not {"D_env_weight", "D_env_weight_base", "TJ_targets"} <= incoming["simulator"].keys():
        raise ValueError("Require standalone ECM coefficient state")
    vars(ctx.cells).update(clone(incoming["grid_fields"]))
    raw = incoming["wire"]
    if "ion_boundary_state" not in raw:
        raise ValueError("Require standalone boundary state")
    if set(raw) != {
        "owner_fields",
        "core_fields",
        "molecule_fields",
        "reaction_fields",
        "modulator_fields",
        "ion_boundary_state",
        "simulator_fields",
    }:
        raise ValueError("Require all standalone public cache fields")
    api = science()
    owner = object.__new__(api["MasterOfGenes"])
    vars(owner).update(clone(raw["owner_fields"]))
    net = object.__new__(api["MasterOfNetworks"])
    vars(net).update(clone(raw["core_fields"]))
    owner.core, ctx.owner = net, owner
    for attr, key, cls in (
        ("molecules", "molecule_fields", "Molecule"),
        ("reactions", "reaction_fields", "Reaction"),
        ("modulators", "modulator_fields", "Modulator"),
    ):
        objects = OrderedDict()
        for name, fields in raw[key].items():
            obj = object.__new__(api[cls])
            vars(obj).update(clone(fields))
            objects[name] = obj
        setattr(net, attr, objects)
    net.reactions_env, net.reactions_mit, net.transporters, net.channels, net.mit = (
        OrderedDict(),
        OrderedDict(),
        OrderedDict(),
        OrderedDict(),
        None,
    )
    vars(ctx.sim).update(clone(incoming["simulator"]))
    ctx.sim.c_env_bound = clone(raw["ion_boundary_state"])
    vars(ctx.p).update(clone(incoming["parameters"]))
    ctx.p.grn = SimpleNamespace(conf=clone(incoming["configuration"]))
    ctx.p.visual = SimpleNamespace(**clone(incoming["visual"]))
    ctx.files, ctx.directories = clone(incoming["captured_files"]), clone(incoming["directories"])
    for attr, ionic, molecular in (
        ("cell_concs", "cc_cells", "c_cells"),
        ("mem_concs", "cc_at_mem", "cc_at_mem"),
        ("env_concs", "cc_env", "c_env"),
        ("bound_concs", "c_env_bound", "c_bound"),
    ):
        mapping = OrderedDict()
        for name, enabled in ctx.p.ions_dict.items():
            if enabled != 1:
                continue
            i = ctx.sim.get_ion(name)
            mapping[name] = api["DynamicValue"](
                lambda i=i, a=ionic: getattr(ctx.sim, a)[i],
                lambda value, i=i, a=ionic: getattr(ctx.sim, a).__setitem__(i, value),
            )
        for name in net.molecules:
            mapping[name] = api["DynamicValue"](
                lambda name=name, a=molecular: getattr(net.molecules[name], a),
                lambda value, name=name, a=molecular: setattr(net.molecules[name], a, value),
            )
        setattr(net, attr, api["DynamicValueDict"](mapping))
    net.mit_concs = None
    attach(ctx)


def attach(ctx):
    net = ctx.owner.core

    def chemistry(stage, species, actual):
        ctx.trace["molecule_frames"].append(dict(stage=stage, species=species, state=snapshot(ctx)))

    def rhs(growth, reaction, combined):
        ctx.trace["current_rhs"] = dict(
            growth_rates=clone(growth), reaction_rates=clone(reaction), all_rates=clone(combined)
        )

    def mover(stage, name, local, actual):
        ctx.trace["mover_frames"].append(
            dict(
                stage=stage,
                species=name,
                fields={
                    k: clone(local.get(k))
                    for k in (
                        "f_X_ED",
                        "fgj_X",
                        "cX_cells",
                        "cX_env_o",
                        "cX_mems",
                        "fenvx",
                        "fenvy",
                        "cenv",
                        "gcx",
                        "gcy",
                        "fx",
                        "fy",
                        "div_fa",
                    )
                },
                vm=actual.vm.copy(),
                vgj=actual.vgj.copy(),
            )
        )

    net._observe_chem, net._observe_rhs, ctx.p._mover_observe = chemistry, rhs, mover


def local_inputs(ctx, t):
    sim, p, cells, net = ctx.sim, ctx.p, ctx.cells, ctx.owner.core
    configured = []
    for name, obj in net.molecules.items():
        g = dict(
            enabled=obj.simple_growth,
            production_rate_mM_s=0.0 if obj.r_production is None else obj.r_production,
            decay_rate_per_s=0.0 if obj.r_decay is None else obj.r_decay,
            decay_max_per_s=0.0 if not obj.simple_growth else obj.decay_max,
            scale_factor=obj.gad_scale_factor,
        )
        configured.append(
            dict(
                name=name,
                parameters={key: clone(getattr(obj, key)) for key in PARAMETERS},
                growth=g,
            )
        )
    return dict(
        conditioned_before_model_network=True,
        ecm_normal_grn=True,
        material_declaration=clone(ctx.inputs["material_definition"]),
        definition=dict(
            molecules=configured,
            grn_configuration=clone(p.grn.conf),
            reactions=clone(p.grn.conf["reactions"]),
            modulators=clone(p.grn.conf.get("modulators") or []),
        ),
        values_before=material_values(sim),
        molecule_states_before={
            name: {
                key: clone(getattr(obj, key))
                for key in ("c_cells", "cc_at_mem", "c_env", "flux_intra")
            }
            for name, obj in net.molecules.items()
        },
        core_publication_fields_before={
            key: clone(getattr(net, key)) for key in PUBLICATIONS if hasattr(net, key)
        },
        controls_before=dict(gj_block=clone(sim.gj_block), NaKATP_block=clone(sim.NaKATP_block)),
        molecular_geometry=dict(
            owner=clone(cells.mem_to_cells),
            partner=clone(cells.nn_i),
            boundary=clone(cells.bflags_mems),
            membrane_area_m2=clone(cells.mem_sa),
            cell_volume_m3=clone(cells.cell_vol),
            gap_length_m=clone(cells.gj_len),
        ),
        dt_s=p.dt,
        F=p.F,
        R=p.R,
        q_C=p.q,
        kb_J_K=p.kb,
        membrane_thickness_m=p.tm,
        runtime_temperature_K=sim.T,
        configured_temperature_K=p.T,
        gap_open=clone(sim.gjopen),
        rho_channel=clone(sim.rho_channel),
        ion_ids=[name for name, enabled in p.ions_dict.items() if enabled == 1],
        valence=clone(sim.zs),
        electric_x_source=clone(sim.E_env_x),
        electric_y_source=clone(sim.E_env_y),
        D_env=clone(sim.D_env),
        grid_index_groups=clone(ctx.inputs["network"]["grid_index_groups"]),
        substances_affect_charge=p.substances_affect_charge,
        sharpness=p.sharpness,
        cluster_open=p.cluster_open,
        incoming_channel_current_A_m2=clone(net.extra_J_mem),
        simulator_fields_before=wire(ctx.owner, sim)["simulator_fields"],
        standalone_dispatch=True,
        source_time_s=t,
    )


def observe(stage, owner, phase, local):
    ctx = _ACTIVE
    assert ctx.owner is owner and phase is ctx.phase
    t = local.get("t")
    event = dict(stage=stage, t=clone(t), state=snapshot(ctx))
    if stage == "before_reinitialize":
        event["clock"] = dict(
            tt=local["tt"].copy(),
            tsamples=sorted(local["tsamples"]),
            loop_time_step_max=local["loop_time_step_max"],
            loop_seconds_max=local["loop_seconds_max"],
        )
    if stage == "before_run_loop":
        before = local_inputs(ctx, t)
        ctx.trace["steps"].append(dict(before=before, after=None, rhs=None))
        if ctx.before_step is not None:
            ctx.before_step(clone(before))
    if stage == "after_run_loop":
        ctx.trace["steps"][-1].update(after=snapshot(ctx), rhs=clone(ctx.trace["current_rhs"]))
    ctx.trace["events"].append(event)


def save_boundary(filename, data):
    ctx = _ACTIVE
    assert data[0] is ctx.owner and data[1] is ctx.cells and data[2] is ctx.p
    ctx.trace["io_events"].append(
        dict(
            operation="saveSim",
            filename=filename,
            scientific_snapshot=snapshot(ctx),
            persistence_executed=False,
        )
    )


def directory_boundary(path):
    ctx = _ACTIVE
    ctx.directories.append(path)
    ctx.trace["io_events"].append(
        dict(operation="make_unless_dir", path=path, persistence_executed=False)
    )


def capture_open(path, mode="r", newline=None):
    if mode != "w" or newline != "":
        raise ValueError("Only standalone CSV output capture is admitted")
    ctx = _ACTIVE

    class CapturedFile(io.StringIO):
        def close(self):
            if not self.closed:
                text = self.getvalue()
                ctx.files[path] = text
                ctx.trace["io_events"].append(
                    dict(operation="CSV", path=path, text=text, persistence_executed=False)
                )
            super().close()

    return CapturedFile(newline=newline)


def capture(inputs):
    validate(inputs)
    ctx = make_context(inputs)
    before = copy.deepcopy(np.random.get_state())
    answer = dict(cold=None, history=[], failure=None)
    try:
        with active(ctx):
            ctx.owner = science()["start_new"](SimpleNamespace(_p=ctx.p), ctx.phase)
        answer["cold"] = snapshot(ctx)
        attach(ctx)
        for index, call in enumerate(inputs["calls"]):
            ctx.trace = new_trace()
            configure_call(ctx, call)
            try:
                with active(ctx):
                    ctx.owner.run_core_sim(ctx.phase)
            except Exception as error:
                answer["failure"] = dict(
                    type=type(error).__name__,
                    message=str(error),
                    traceback=traceback.format_exc(),
                    invocation=index,
                    stage="run_core_sim",
                )
            answer["history"].append(dict(snapshot=snapshot(ctx), trace=clone(ctx.trace)))
            if answer["failure"]:
                break
    except Exception as error:
        answer["failure"] = dict(
            type=type(error).__name__,
            message=str(error),
            traceback=traceback.format_exc(),
            stage="cold",
        )
        answer["partial"] = snapshot(ctx)
    answer.update(
        status="source_refused" if answer["failure"] else "source_completed",
        RNG_unchanged=all(
            np.array_equal(a, b) for a, b in zip(before, np.random.get_state(), strict=True)
        ),
        file_persistence_credit=False,
        normal_solver_executed=False,
    )
    return answer


def main():
    import argparse
    import builtins
    import importlib.abc
    import sys

    parser = argparse.ArgumentParser()
    parser.add_argument("--inputs", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    blocked = {"cells", "betse", "jax", "jaxlib"}
    original = builtins.__import__

    def guarded(name, *rest, **kwargs):
        if name.split(".")[0] in blocked:
            raise ImportError("Standalone native production import denied: " + name)
        return original(name, *rest, **kwargs)

    class Guard(importlib.abc.MetaPathFinder):
        def find_spec(self, fullname, path=None, target=None):
            if fullname.split(".")[0] in blocked:
                raise ImportError("Standalone native production import denied: " + fullname)

    builtins.__import__ = guarded
    sys.meta_path.insert(0, Guard())
    result = capture(json.loads(args.inputs.read_text()))
    loaded = [name for name in sys.modules if name.split(".")[0] in blocked]
    assert not loaded
    result.update(
        production_imports_denied=True,
        loaded_production_modules=loaded,
        runtime=archive_native.runtime_inventory(),
    )
    archive_native.write_archive(args.output, result)


PARAMETERS = previous.PARAMETERS

PUBLICATIONS = ("extra_rho_cells", "extra_rho_env", "extra_J_mem", "extra_Jenv_x", "extra_Jenv_y")
GRID_FIELDS = (
    "X",
    "Y",
    "xypts",
    "delta",
    "map_cell2ecm",
    "map_mem2ecm",
    "M_sum_mems",
    "num_mems",
    "memSa_per_envSquare",
    "M_divmap_mem2ecm",
    "true_ecm_vol",
    "ecm_vol",
    "rads",
    "R_rads",
    "all_bound_mem_inds",
    "interior_bound_mem_inds",
    "ecm_inds_bound_cell",
)
material_values = previous.material_values


def build_grid(cells, p, inputs):
    code, sites, pins = field_native.capture()
    code["grid"](cells, p)
    code["owner_matrices"](cells)
    code["environment"](cells, p)


if __name__ == "__main__":
    main()
