"""Pinned global setter and actual voltage-event class execution; no full solver."""

import ast
import copy
import hashlib
import os
from abc import ABCMeta
from functools import lru_cache
from pathlib import Path
from types import SimpleNamespace

import numpy as np

PINNED = {
    "betse/science/math/toolbox.py": (
        "a2a63fe1f44303fe05d2b1fbcfe9250e4575992f688cbe4cbd7fd99ef99e60a3"
    ),
    "betse/science/tissue/tishandler.py": (
        "057ddab87be773e5d338d0681bd503b12aee02861be0902d6ef46e1133d42f54"
    ),
    "betse/science/tissue/event/tiseveabc.py": (
        "490e9e10f3ff713878145bc332a79a3b11bf0d7650238d31d7ff1032e85205a6"
    ),
    "betse/science/tissue/event/tisevevolt.py": (
        "28e1124a729bfbea9a3c4ce6821a93f419a0b82fadc6342d4ce9ab648d02b29b"
    ),
}
SIDES = ("top", "bottom", "left", "right")
CHARS = ("T", "B", "L", "R")


class NativeEventError(ValueError):
    pass


@lru_cache(maxsize=1)
def capture():
    root = Path(os.environ.get("CELLS_BETSE_SOURCE", "/mnt/workspaces/Cells/betse-v1.5.0"))
    trees = {}
    for name, expected in PINNED.items():
        data = (root / name).read_bytes()
        if hashlib.sha256(data).hexdigest() != expected:
            raise ValueError("Pinned global event source changed")
        trees[name] = ast.parse(data)
    nodes = []
    for name, names in (
        ("betse/science/math/toolbox.py", ("pulse",)),
        ("betse/science/tissue/event/tiseveabc.py", ("SimEventABC", "SimEventPulseABC")),
        (
            "betse/science/tissue/event/tisevevolt.py",
            ("SimEventPulseVoltage", "_convert_boundary_str_to_char"),
        ),
    ):
        selected = [
            copy.deepcopy(n)
            for n in trees[name].body
            if isinstance(n, (ast.ClassDef, ast.FunctionDef)) and n.name in names
        ]
        assert len(selected) == len(names)
        nodes.extend(selected)
    cls = next(
        n
        for n in trees["betse/science/tissue/tishandler.py"].body
        if isinstance(n, ast.ClassDef) and n.name == "TissueHandler"
    )
    nodes.append(
        copy.deepcopy(
            next(
                n
                for n in cls.body
                if isinstance(n, ast.FunctionDef) and n.name == "_fire_events_global"
            )
        )
    )
    namespace = dict(
        np=np,
        ABCMeta=ABCMeta,
        SimPhase=SimpleNamespace,
        BetseSimEventException=NativeEventError,
        type_check=lambda f: f,
    )
    exec(
        compile(
            ast.fix_missing_locations(ast.Module(body=nodes, type_ignores=[])),
            "<pinned BETSE global setters>",
            "exec",
        ),
        namespace,
    )
    namespace["tb"] = namespace["toolbox"] = SimpleNamespace(pulse=namespace["pulse"])
    return namespace


def evaluate(program, state, time_s, original_temperature_K, *, events_enabled=True):
    source = capture()
    sim = SimpleNamespace(
        T=state["temperature_K"],
        gj_block=np.array(state["junction_available"], dtype=float),
        NaKATP_block=state["pump_available"],
        bound_V=dict(zip(CHARS, state["boundary_voltage_V"], strict=True)),
    )
    p = SimpleNamespace(
        T=original_temperature_K,
        global_options=dict.fromkeys(
            ("K_env", "Cl_env", "Na_env", "T_change", "gj_block", "NaKATP_block"), 0
        ),
        sim_time_total=1.0,
    )
    handler, voltage = SimpleNamespace(), None
    for row in program["events"]:
        kind = row["kind"]
        if kind == "voltage":
            p._conf = {
                "apply external voltage": {
                    "change start": row["on_s"],
                    "change finish": row["off_s"],
                    "change rate": row["change_s"],
                    "peak voltage": row["amplitude"],
                    "positive voltage boundary": row["positive_boundary"],
                    "negative voltage boundary": row["negative_boundary"],
                }
            }
            voltage = source["SimEventPulseVoltage"](p)
            continue
        option, suffix = {
            "temperature": ("T_change", "T"),
            "junction_block": ("gj_block", "GJ"),
            "pump_block": ("NaKATP_block", "NK"),
        }[kind]
        p.global_options[option] = 1
        for attr, key in (("ton", "on_s"), ("toff", "off_s"), ("tramp", "change_s")):
            setattr(handler, attr + suffix, row[key])
        if kind == "temperature":
            handler.multT = row["amplitude"]
        elif kind == "junction_block":
            handler.targets_gj_block = [program["membrane_ids"].index(n) for n in row["target_ids"]]
    if events_enabled:
        phase = SimpleNamespace(p=p, sim=sim)
        with np.errstate(over="ignore", invalid="ignore", under="ignore"):
            source["_fire_events_global"](handler, phase, time_s)
            if voltage is not None:
                voltage.fire(phase, time_s)
    return dict(
        temperature_K=float(sim.T),
        junction_available=sim.gj_block.tolist(),
        pump_available=float(sim.NaKATP_block),
        boundary_voltage_V=[float(sim.bound_V[c]) for c in CHARS],
    )
