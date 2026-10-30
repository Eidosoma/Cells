"""Authenticated native temperature/calendar sites, without production imports.

The original scalar/array arithmetic executes unchanged. Phase, tissue and
storage interfaces are normalized explicitly; ionic/voltage loops do not run.
"""

import ast
import copy
import hashlib
import json
import os
from enum import Enum
from functools import lru_cache
from pathlib import Path
from types import MethodType, SimpleNamespace

import numpy as np

PROTOCOL = Path(__file__).with_name("betse_temperature_calendar_protocol.json")


class Phase(Enum):
    INIT = 1
    SIM = 2


def _executable(node):
    result = copy.deepcopy(node)
    for part in ast.walk(result):
        if isinstance(part, ast.FunctionDef):
            part.decorator_list, part.returns = [], None
            for arg in (*part.args.posonlyargs, *part.args.args, *part.args.kwonlyargs):
                arg.annotation = None
    return result


def _wrapper(name, arguments, body, returns=None):
    fn = ast.parse(f"def {name}({arguments}):\n pass\n").body[0]
    fn.body = copy.deepcopy(body)
    if returns is not None:
        fn.body.append(ast.Return(copy.deepcopy(returns)))
    return fn


def _literal(expression):
    return ast.parse(expression, mode="eval").body


def _methods(tree, name):
    cls = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == name)
    return {node.name: node for node in cls.body if isinstance(node, ast.FunctionDef)}


@lru_cache(maxsize=1)
def capture():
    plan = json.loads(PROTOCOL.read_text())
    native = plan["native_source"]
    root = Path(os.environ.get("CELLS_BETSE_SOURCE", native["checkout"]))
    installed = Path(native["installed_package"]).parent
    trees = {}
    for name, expected in native["source_sha256"].items():
        data = (root / name).read_bytes()
        if hashlib.sha256(data).hexdigest() != expected:
            raise ValueError("Pinned native temperature source changed: " + name)
        if hashlib.sha256((installed / name).read_bytes()).hexdigest() != expected:
            raise ValueError("Pinned installed native temperature source changed: " + name)
        trees[name] = ast.parse(data, filename=name)
    sim = _methods(trees["betse/science/sim.py"], "Simulator")
    cells = _methods(trees["betse/science/cells.py"], "Cells")
    handler = _methods(trees["betse/science/tissue/tishandler.py"], "TissueHandler")
    channel = _methods(trees["betse/science/channels/channelsabc.py"], "ChannelsABC")
    toolkit = {
        node.name: node
        for node in trees["betse/science/sim_toolbox.py"].body
        if isinstance(node, ast.FunctionDef)
    }
    namespace, sites = dict(np=np, SimPhaseKind=Phase), {}

    def execute(path, nodes, *, origin=None):
        for node in nodes:
            originals = [node] if origin is None else origin
            sites[node.name] = dict(
                file=path,
                source_sha256=native["source_sha256"][path],
                original_lines=[[part.lineno, part.end_lineno] for part in originals],
                selected_AST_sha256=hashlib.sha256(
                    ast.dump(
                        ast.Module(body=originals, type_ignores=[]), include_attributes=False
                    ).encode()
                ).hexdigest(),
                executed_AST_sha256=hashlib.sha256(
                    ast.dump(node, include_attributes=False).encode()
                ).hexdigest(),
                executed_body_AST_sha256=hashlib.sha256(
                    ast.dump(
                        ast.Module(body=node.body, type_ignores=[]), include_attributes=False
                    ).encode()
                ).hexdigest(),
            )
        exec(
            compile(
                ast.fix_missing_locations(ast.Module(body=nodes, type_ignores=[])), path, "exec"
            ),
            namespace,
        )

    execute(
        "betse/science/sim.py", [_executable(sim[name]) for name in ("fast_sim_init", "get_ion")]
    )
    execute(
        "betse/science/sim_toolbox.py",
        [_executable(toolkit[name]) for name in ("ghk_calculator", "get_conductivity")],
    )
    execute(
        "betse/science/tissue/tishandler.py",
        [_executable(handler[name]) for name in ("fire_events", "_fire_events_global")],
    )
    execute(
        "betse/science/channels/channelsabc.py",
        [_executable(channel[name]) for name in ("update_mh", "update_ml")],
    )
    pulse = next(
        node
        for node in trees["betse/science/math/toolbox.py"].body
        if isinstance(node, ast.FunctionDef) and node.name == "pulse"
    )
    execute("betse/science/math/toolbox.py", [_executable(pulse)])
    namespace["tb"] = SimpleNamespace(pulse=namespace["pulse"])
    namespace["stb"] = SimpleNamespace(ghk_calculator=namespace["ghk_calculator"])

    fresh = [
        node
        for method in sim.values()
        for node in ast.walk(method)
        if isinstance(node, ast.Assign)
        and ast.unparse(node.value) == "p.T"
        and any(ast.unparse(target) == "self.T" for target in node.targets)
    ]
    if len(fresh) != 1:
        raise ValueError("Original configured-temperature copy is ambiguous")
    execute("betse/science/sim.py", [_wrapper("fresh_temperature", "self,p", fresh)], origin=fresh)
    constants = [
        node
        for node in ast.walk(trees["betse/science/parameters.py"])
        if isinstance(node, ast.Assign)
        and len(node.targets) == 1
        and ast.unparse(node.targets[0]) in ("self.F", "self.R", "self.q", "self.kb")
    ]
    counts = [
        node
        for node in ast.walk(trees["betse/science/parameters.py"])
        if isinstance(node, ast.Assign)
        and any(
            ast.unparse(target) in ("self.init_tsteps", "self.sim_tsteps")
            for target in node.targets
        )
    ]
    if len(constants) != 4 or len(counts) != 2:
        raise ValueError("Original native constants or duration-count declarations changed")
    execute(
        "betse/science/parameters.py",
        [_wrapper("native_constants", "self", constants)],
        origin=constants,
    )
    execute(
        "betse/science/parameters.py", [_wrapper("duration_counts", "self", counts)], origin=counts
    )
    phase_methods = _methods(trees["betse/science/phase/phasecls.py"], "SimPhase")
    branches = [
        node
        for method in phase_methods.values()
        for node in ast.walk(method)
        if isinstance(node, ast.If)
        and ast.unparse(node.test) == "self.kind is SimPhaseKind.INIT"
        and any(
            isinstance(item, ast.Assign)
            and any(ast.unparse(target) == "self.p.dt" for target in item.targets)
            for item in ast.walk(node)
        )
    ]
    if len(branches) != 1:
        raise ValueError("Original INIT/SIM dt selector is ambiguous")
    namespace["BetseSimPhaseException"] = ValueError
    execute(
        "betse/science/phase/phasecls.py",
        [_wrapper("phase_step", "self", branches)],
        origin=branches,
    )
    for name, method in (("sigma_initial", sim["init_dynamics"]), ("sigma_after", sim["update_V"])):
        body = [
            node
            for node in method.body
            if isinstance(node, ast.Assign)
            and any(ast.unparse(target) == "self.sigma_cell" for target in node.targets)
        ]
        if len(body) != 1:
            raise ValueError("Original configured-temperature conductivity overwrite changed")
        execute("betse/science/sim.py", [_wrapper(name, "self,p", body)], origin=body)

    matrix_method = next(
        method
        for method in cells.values()
        if any(
            isinstance(node, ast.Assign)
            and any(ast.unparse(target) == "self.M_sum_mems" for target in node.targets)
            for node in method.body
        )
    )
    first = next(
        i
        for i, node in enumerate(matrix_method.body)
        if isinstance(node, ast.Assign)
        and any(ast.unparse(target) == "self.M_sum_mems" for target in node.targets)
    )
    last = next(
        i
        for i, node in enumerate(matrix_method.body)
        if isinstance(node, ast.Assign)
        and any(ast.unparse(target) == "self.num_mems" for target in node.targets)
        and isinstance(node.value, ast.Call)
        and ast.unparse(node.value.func) == "np.asarray"
    )
    body = matrix_method.body[first : last + 1]
    execute("betse/science/cells.py", [_wrapper("owner_matrices", "self", body)], origin=body)
    plot = sim["_plot_loop"]
    first = next(i for i, node in enumerate(plot.body) if isinstance(node, ast.If))
    last = next(i for i, node in enumerate(plot.body) if isinstance(node, ast.While))
    body = plot.body[first : last + 1]
    execute(
        "betse/science/sim.py",
        [_wrapper("calendar", "phase", body, _literal("(time_steps,time_steps_sampled)"))],
        origin=body,
    )
    for name, method in (
        ("normal", sim["_run_sim_core_loop"]),
        ("fast", sim["_run_fast_sim_core_loop"]),
    ):
        loop = next(node for node in method.body if isinstance(node, ast.For))
        body = [
            node
            for node in loop.body
            if isinstance(node, ast.If)
            and ast.unparse(node.test) == "phase.kind is SimPhaseKind.SIM"
            and any(
                isinstance(call, ast.Call) and ast.unparse(call.func) == "phase.dyna.fire_events"
                for call in ast.walk(node)
            )
        ]
        if len(body) != 1:
            raise ValueError("Native temperature event guard changed")
        execute("betse/science/sim.py", [_wrapper("event_" + name, "phase,t", body)], origin=body)

    eflux = toolkit["electroflux"]
    last = next(
        i
        for i, node in enumerate(eflux.body)
        if isinstance(node, ast.Assign)
        and any(ast.unparse(target) == "alpha" for target in node.targets)
    )
    body = eflux.body[1 : last + 1]
    execute(
        "betse/science/sim_toolbox.py",
        [_wrapper("electroflux_coefficients", "zc,vBA,T,p", body, _literal("(alpha,vBA,zc)"))],
        origin=body,
    )
    body = [
        node
        for node in toolkit["nernst_planck_vector"].body
        if isinstance(node, ast.Assign)
        and any(ast.unparse(target) == "alpha" for target in node.targets)
    ]
    execute(
        "betse/science/sim_toolbox.py",
        [_wrapper("NP_alpha", "D,z,T,p", body, _literal("alpha"))],
        origin=body,
    )
    for name, method, expected in (
        ("membrane_temperature", sim["_run_sim_core_loop"], "self.T"),
        ("junction_temperature", sim["update_gj"], "p.T"),
    ):
        arguments = [
            call.args[6]
            for call in ast.walk(method)
            if isinstance(call, ast.Call)
            and ast.unparse(call.func) == "stb.electroflux"
            and len(call.args) >= 8
        ]
        if not arguments or any(ast.unparse(arg) != expected for arg in arguments):
            raise ValueError("Actual membrane/junction temperature argument changed")
        execute(
            "betse/science/sim.py",
            [_wrapper(name, "self,p", [], copy.deepcopy(arguments[0]))],
            origin=arguments,
        )

    for name, method, fields in (
        ("HH_arithmetic", channel["update_mh"], ("self.m", "self.h")),
        ("ML_arithmetic", channel["update_ml"], ("self.m",)),
    ):
        dt = next(
            node
            for node in method.body
            if isinstance(node, ast.Assign)
            and any(ast.unparse(target) == "dt" for target in node.targets)
        )
        expressions = [
            node.value
            for node in method.body
            if isinstance(node, ast.Assign)
            and any(ast.unparse(target) in fields for target in node.targets)
        ]
        if any(
            not isinstance(expr, ast.BinOp) or not isinstance(expr.op, ast.Div)
            for expr in expressions
        ):
            raise ValueError("Native gate recurrence expression changed")
        outputs = [ast.Name(id="dt", ctx=ast.Load())]
        outputs += [copy.deepcopy(expr.left) for expr in expressions]
        outputs += [copy.deepcopy(expr.right) for expr in expressions]
        execute(
            "betse/science/channels/channelsabc.py",
            [_wrapper(name, "self,p", [dt], ast.Tuple(elts=outputs, ctx=ast.Load()))],
            origin=[dt, *expressions],
        )
    return namespace, sites, native


def _cache(sim, initial_sigma):
    return dict(
        leak_reversal_V=sim.E_Leak.copy(),
        leak_conductance_S_m2=sim.G_Leak.copy(),
        junction_conductance_S_m2=sim.G_gj.copy(),
        init_dynamics_sigma_S_m=initial_sigma,
        sigma_cell_S_m=sim.sigma_cell.copy(),
        membrane_conductivity_S_m2=np.asarray(sim.sigma_mem),
        ion_reversal_V=copy.deepcopy(sim.rev_E_dic),
        ion_mean_mol_m3=copy.deepcopy(sim.cbar_dic),
        cbar_all_mol_m3=np.asarray(sim.cbar_all),
        cbar_sum_mol_m3=np.asarray(sim.cbar_sum),
    )


def evaluate(inputs, *, solver="normal"):
    source, sites, pins = capture()
    raw, calendar, program = (inputs[key] for key in ("raw", "calendar", "program"))
    if (
        solver not in ("normal", "fast")
        or calendar["phase"] not in ("INIT", "SIM")
        or type(calendar["step_count"]) is not int
        or not 0 <= calendar["step_count"] <= 64
        or not np.isfinite(calendar["dt_s"])
        or calendar["dt_s"] <= 0
        or not np.isfinite(calendar["sample_stride"])
        or calendar["sample_stride"] < 1
        or len(program["events"]) > 1
        or any(event["kind"] != "temperature" for event in program["events"])
    ):
        raise ValueError("Refuse ambiguous/unbounded native temperature source microcase")
    material = raw["material"]
    g, ions, constants = (material[key] for key in ("geometry", "ions", "parameters"))
    owner = np.asarray(g["owner"], dtype=np.int64)
    m, n, count = len(owner), len(g["cell_ids"]), len(ions["ids"])
    if not 1 <= m <= 128 or not 1 <= n <= 16 or not 1 <= count <= 7 or constants["is_ecm"]:
        raise ValueError("Native source temperature owner axes exceed the declared boundary")
    p = SimpleNamespace(
        R=constants["R_J_mol_K"],
        F=constants["F_C_mol"],
        q=constants["q_C"],
        kb=constants["kb_J_K"],
        T=constants["configured_temperature_K"],
        tm=constants["membrane_thickness_m"],
        cell_space=constants["gap_length_m"],
        gj_surface=constants["junction_surface_fraction"],
        is_ecm=False,
        molecules_enabled=False,
        grn_enabled=False,
        dt=calendar["dt_s"],
        ions_dict={name: 1 for name in ions["ids"]},
        init_tsteps=calendar["step_count"],
        sim_tsteps=calendar["step_count"],
        t_resample=calendar["sample_stride"],
        global_options=dict.fromkeys(
            ("K_env", "Cl_env", "Na_env", "T_change", "gj_block", "NaKATP_block"), 0
        ),
    )
    literal = SimpleNamespace()
    source["native_constants"](literal)
    if raw["constant_profile"] == "literal_native" and any(
        getattr(p, key) != getattr(literal, key) for key in ("R", "F", "q", "kb")
    ):
        raise ValueError("Native literal constants differ from the actual pinned declarations")
    dt = calendar["dt_s"]
    phase_name = calendar["phase"]
    p.init_time_step = dt if phase_name == "INIT" else 2 * dt
    p.sim_time_step = dt if phase_name == "SIM" else 2 * dt
    p.init_time_sampling = p.sim_time_sampling = dt * calendar["sample_stride"]
    requested = calendar.get("requested_duration_s")
    p.init_time_total = p.sim_time_total = (
        calendar["step_count"] * dt if requested is None else requested
    )
    source["phase_step"](SimpleNamespace(kind=Phase[phase_name], p=p))
    configured_counts = None
    if requested is not None:
        source["duration_counts"](p)
        configured_counts = dict(INIT=p.init_tsteps, SIM=p.sim_tsteps)
        if configured_counts[phase_name] != calendar["step_count"]:
            raise ValueError("Original native requested-duration count differs from the calendar")
    cells = SimpleNamespace(
        cell_i=np.arange(n),
        mem_i=np.arange(m),
        mem_to_cells=owner,
        cell_to_mems=[np.flatnonzero(owner == i).tolist() for i in range(n)],
        mem_sa=np.asarray(g["membrane_area_m2"]),
        cell_sa=np.asarray(g["cell_area_m2"]),
        map_mem2ecm=np.asarray(g["environment_index"]),
    )
    source["owner_matrices"](cells)
    sim = SimpleNamespace(
        cc_cells=np.asarray(ions["cell_mol_m3"]),
        cc_env=np.asarray(ions["environment_mol_m3"]),
        zs=np.asarray(ions["valence"]),
        D_free=np.asarray(ions["free_diffusion_m2_s"]),
        Dm_cells=np.asarray(ions["membrane_diffusion_m2_s"]),
        T=constants["temperature_K"],
        mdl=m,
        cdl=n,
    )
    for name in ("Na", "K", "Cl", "Ca", "M", "H", "P"):
        setattr(sim, "i" + name, ions["ids"].index(name) if name in ions["ids"] else [])
    sim.get_ion = MethodType(source["get_ion"], sim)
    if raw["entry_mode"] == "fresh_configured_copy":
        source["fresh_temperature"](sim, p)
    source["sigma_initial"](sim, p)
    initial_sigma = sim.sigma_cell.copy()
    source["fast_sim_init"](sim, cells, p)
    source["sigma_after"](sim, p)
    cache = _cache(sim, initial_sigma)
    gates = raw["clock_probes"]
    hh = SimpleNamespace(
        m=np.asarray(gates["initial_hh_m"]),
        h=np.asarray(gates["initial_hh_h"]),
        _mInf=np.asarray(gates["hh_m_inf"]),
        _hInf=np.asarray(gates["hh_h_inf"]),
        _mTau=np.asarray(gates["hh_m_tau_native"]),
        _hTau=np.asarray(gates["hh_h_tau_native"]),
        time_unit=gates["time_unit"],
    )
    ml = SimpleNamespace(
        m=np.asarray(gates["initial_ml_m"]),
        _mInf=np.asarray(gates["ml_m_inf"]),
        _mTau=np.asarray(gates["ml_tau_native"]),
        time_unit=gates["time_unit"],
        Phi=gates["Phi"],
    )
    handler = SimpleNamespace()
    for row in program["events"]:
        p.global_options["T_change"] = 1
        handler.tonT, handler.toffT, handler.trampT = (
            row[key] for key in ("on_s", "off_s", "change_s")
        )
        handler.multT = row["amplitude"]
    stage_order, current_arithmetic = [], None

    def global_events(self, *, phase, t):
        source["_fire_events_global"](self, phase, t)
        stage_order.append("SIM_global_temperature")

    def tissue_events(*, phase, t):
        nonlocal current_arithmetic
        hdt, mn, hn, md, hd = source["HH_arithmetic"](hh, p)
        mdt, mln, mld = source["ML_arithmetic"](ml, p)
        assert hdt == mdt
        current_arithmetic = dict(
            duration_native_units=np.asarray(hdt),
            hh_m_numerator=mn.copy(),
            hh_h_numerator=hn.copy(),
            hh_m_denominator=md.copy(),
            hh_h_denominator=hd.copy(),
            ml_numerator=mln.copy(),
            ml_denominator=mld.copy(),
        )
        source["update_mh"](hh, p)
        source["update_ml"](ml, p)
        stage_order.append("selected_tissue_clock_probes")

    handler._fire_events_global = MethodType(global_events, handler)
    handler._fire_events_tissue = tissue_events
    handler.makeAllChanges = lambda sim: stage_order.append("makeAllChanges_marker")
    phase = SimpleNamespace(kind=Phase[calendar["phase"]], p=p, sim=sim, dyna=handler)
    handler.fire_events = MethodType(source["fire_events"], handler)
    labels, sampled = source["calendar"](phase)
    frames = []
    for i, label in enumerate(labels):
        stage_order.clear()
        current_arithmetic = None
        with np.errstate(all="ignore"):
            source["event_" + solver](phase, label)
            ma, ja, np_alpha, cond, used_z = [], [], [], [], []
            membrane_used = junction_used = None
            for ion, name in enumerate(ions["ids"]):
                alpha, used_v, mutated_z = source["electroflux_coefficients"](
                    np.full(m, sim.zs[ion], dtype=np.float64),
                    np.asarray(raw["membrane_voltage_V"], dtype=np.float64).copy(),
                    source["membrane_temperature"](sim, p),
                    p,
                )
                ma.append(alpha)
                used_z.append(mutated_z)
                membrane_used = used_v
                alpha, used_v, _ = source["electroflux_coefficients"](
                    np.full(m, sim.zs[ion], dtype=np.float64),
                    np.asarray(raw["junction_voltage_V"], dtype=np.float64).copy(),
                    source["junction_temperature"](sim, p),
                    p,
                )
                ja.append(alpha)
                junction_used = used_v
                np_alpha.append(
                    source["NP_alpha"](
                        np.full(m, sim.D_free[ion]), np.full(m, sim.zs[ion]), sim.T, p
                    )
                )
                cond.append(
                    source["get_conductivity"](
                        sim.Dm_cells[ion], sim.zs[ion], sim.cbar_dic[name], p.tm, p
                    )
                )
        stage_order.append("coefficient_readouts")
        frames.append(
            dict(
                call_index=i,
                event_label_s=float(label),
                duration_s=p.dt,
                elapsed_start_s=i * p.dt,
                elapsed_end_s=(i + 1) * p.dt,
                sampled=bool(label in sampled),
                events_enabled=calendar["phase"] == "SIM",
                source_order=list(stage_order),
                values=dict(
                    temperature_K=np.asarray(sim.T),
                    hh_m=hh.m.copy(),
                    hh_h=hh.h.copy(),
                    ml_m=ml.m.copy(),
                ),
                probes=dict(
                    membrane_electroflux_alpha=np.asarray(ma),
                    configured_junction_electroflux_alpha=np.asarray(ja),
                    live_nernst_planck_alpha=np.asarray(np_alpha),
                    configured_conductivity_S_m2=np.asarray(cond),
                    configured_normal_sigma_S_m=sim.sigma_cell.copy(),
                    membrane_voltage_after_nonce_V=membrane_used,
                    junction_voltage_after_nonce_V=junction_used,
                    valence_after_nonce=np.asarray(used_z),
                ),
                gate_arithmetic=current_arithmetic,
            )
        )
    return dict(
        cache=cache,
        frames=frames,
        source_sites=sites,
        native_source_sha256=pins["source_sha256"],
        solver_guard=solver,
        configured_counts=configured_counts,
        source_selected_dt_s=p.dt,
        sampling_stride_scope=(
            "Caller-declared original p.t_resample; YAML sampling inversion omitted"
        ),
        scope="Unchanged source clock/setter/selected HH/ML/cache/transport-coefficient sites; "
        "held material and voltages, no coupled ionic or thermal evolution.",
    )
