"""Execute pinned calendar, duration-count and solver event-guard source sites.

This captures the source arithmetic and dispatch labels only. Ionic transport,
protein noise, observation payloads, plotting and the full solver are not run.
"""

import ast
import copy
import hashlib
import os
from enum import Enum
from functools import lru_cache
from pathlib import Path
from types import SimpleNamespace

import numpy as np

PINNED = {
    "betse/science/sim.py": "02a9a049b5daa5cf6bc543332aa89437f58a4700ed31310abc3ee13697f22d43",
    "betse/science/parameters.py": (
        "f36ec747918aa285ca043fe51086bcff4e4e2198cd4f30a138f1e58a51ecf85e"
    ),
}


class Phase(Enum):
    INIT = 1
    SIM = 2


def _function(name, args, body):
    fn = ast.parse(f"def {name}({args}):\n    pass\n").body[0]
    fn.body = copy.deepcopy(body)
    return fn


@lru_cache(maxsize=1)
def capture():
    root = Path(os.environ.get("CELLS_BETSE_SOURCE", "/mnt/workspaces/Cells/betse-v1.5.0"))
    trees = {}
    for name, expected in PINNED.items():
        data = (root / name).read_bytes()
        if hashlib.sha256(data).hexdigest() != expected:
            raise ValueError("Pinned native source changed: " + name)
        trees[name] = ast.parse(data)
    cls = next(
        item
        for item in trees["betse/science/sim.py"].body
        if isinstance(item, ast.ClassDef) and item.name == "Simulator"
    )
    methods = {item.name: item for item in cls.body if isinstance(item, ast.FunctionDef)}
    method = methods["_plot_loop"]
    start = next(i for i, item in enumerate(method.body) if isinstance(item, ast.If))
    end = next(i for i, item in enumerate(method.body) if isinstance(item, ast.While)) + 1
    body = method.body[start:end]
    assert ast.unparse(body[0].test) == "phase.kind is SimPhaseKind.INIT"
    assert any(
        isinstance(item, ast.Call) and ast.unparse(item.func) == "np.linspace"
        for item in ast.walk(ast.Module(body=body, type_ignores=[]))
    )
    functions = [
        _function(
            "calendar",
            "phase",
            [*body, ast.parse("return time_steps, time_steps_sampled").body[0]],
        )
    ]
    sites = {"calendar": [body[0].lineno, body[-1].end_lineno]}
    for name, method_name in (
        ("normal", "_run_sim_core_loop"),
        ("fast", "_run_fast_sim_core_loop"),
    ):
        method = methods[method_name]
        loop = next(item for item in method.body if isinstance(item, ast.For))
        assert ast.unparse(loop.target) == "t" and ast.unparse(loop.iter) == "time_steps"
        guards = [
            item
            for item in loop.body
            if isinstance(item, ast.If)
            and ast.unparse(item.test) == "phase.kind is SimPhaseKind.SIM"
            and any(
                isinstance(call, ast.Call) and ast.unparse(call.func) == "phase.dyna.fire_events"
                for call in ast.walk(item)
            )
        ]
        assert len(guards) == 1
        captured_loop = copy.deepcopy(loop)
        captured_loop.body = copy.deepcopy(guards)
        captured_loop.orelse = []
        functions.append(_function("events_" + name, "phase,time_steps", [captured_loop]))
        sites[name] = [guards[0].lineno, guards[0].end_lineno]
    assignments = []
    for item in ast.walk(trees["betse/science/parameters.py"]):
        if isinstance(item, ast.Assign) and any(
            ast.unparse(target) in ("self.init_tsteps", "self.sim_tsteps")
            for target in item.targets
        ):
            assignments.append(item)
    assert len(assignments) == 2
    functions.append(_function("counts", "self", assignments))
    sites["counts"] = [item.lineno for item in assignments]
    namespace = {"np": np, "SimPhaseKind": Phase}
    exec(
        compile(
            ast.fix_missing_locations(ast.Module(body=functions, type_ignores=[])),
            "<pinned BETSE calendar sites>",
            "exec",
        ),
        namespace,
    )
    return namespace, sites


def evaluate(parameters, *, solver):
    count, dt, stride = (
        parameters["step_count"],
        parameters["dt_s"],
        parameters["sample_stride"],
    )
    if not (0 <= count <= 1_000_000 and np.isfinite(dt) and dt > 0 and stride >= 1):
        raise ValueError("Refuse unbounded/nonterminating native calendar inputs")
    if solver not in ("normal", "fast"):
        raise ValueError("Require an explicit native solver guard")
    source, sites = capture()
    p = SimpleNamespace(init_tsteps=count, sim_tsteps=count, dt=dt, t_resample=stride)
    events = []
    phase = SimpleNamespace(
        p=p,
        kind=Phase[parameters["phase"]],
        dyna=SimpleNamespace(fire_events=lambda *, phase, t: events.append(float(t))),
    )
    labels, sampled = source["calendar"](phase)
    source["events_" + solver](phase, labels)
    counts = None
    if (duration := parameters.get("requested_duration_s")) is not None:
        p.init_time_total = p.sim_time_total = duration
        p.init_time_step = p.sim_time_step = dt
        source["counts"](p)
        counts = dict(INIT=p.init_tsteps, SIM=p.sim_tsteps)
    return dict(
        event_label_s=labels.tolist(),
        sampled=[bool(label in sampled) for label in labels],
        event_call_labels_s=events,
        configured_counts=counts,
        source_sites=sites,
        native_source_sha256=dict(PINNED),
        scope="calendar/count/guard sites only; no native coupled evolution",
    )
