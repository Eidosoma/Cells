"""A parameter-only change reuses the compiled window and gives a fresh compile's result (A4).

docs/INNER_MODEL_V4_DESIGN.md §2.2 and §7.4 (e) 4, D174's executable-reuse target. On the vector
window path (core/vector_windows.compile_window, keyed on the implementation's structure, its
step and check functions, and the arguments' shapes): a heredity cell's value twin (every
membrane permeability scaled) compiles nothing and matches, bit for bit, the same twin compiled
afresh; a world with another structure (NaV1.2 removed) compiles its own executable.
"""

import copy

import numpy as np

from cells.definitions.specs import parse_spec
from cells.execution import vector_windows
from cells.execution.batch import BatchSpec, WorldSpec
from cells.execution.state import initialise
from cells.execution.windows import WindowPolicy
from cells.registry.models import get_model
from validation.tissue import pump_water_fixtures as water_fixtures

STEPS = 8
NAV = "cells.channel.nav1p2_m3h_regularized@1"


def scaled(raw, factor):
    raw = copy.deepcopy(raw)
    for membrane in raw["model"]["membranes"]:
        p = membrane["permeability_m_per_s"]
        membrane["permeability_m_per_s"] = {k: factor * v for k, v in p.items()}
    return raw


def without_nav(raw):
    raw = copy.deepcopy(raw)
    gone = {c["id"] for c in raw["model"]["channels"] if c["kinetic_law"] == NAV}
    raw["model"]["channels"] = [c for c in raw["model"]["channels"] if c["id"] not in gone]
    controls = raw["experiment"]["channel_controls"]
    raw["experiment"]["channel_controls"] = [g for g in controls if g["channel_id"] not in gone]
    return raw


def first_window(raw):
    """(compile seconds, final states) of the first vector window of a one-world batch."""
    spec = parse_spec(raw)
    batch = BatchSpec((WorldSpec(1, spec),), 1, 2**53 - 1, 2**53 - 1)
    window = next(
        iter(vector_windows.iter_vector_windows(batch, WindowPolicy(STEPS, "checkpoints")))
    )
    final = window.checkpoints[1]
    return window.timings["compile_seconds"], [np.asarray(v) for v in final.state]


def same(a, b):
    return all(
        x.shape == y.shape and x.dtype == y.dtype and x.tobytes() == y.tobytes()
        for x, y in zip(a, b, strict=True)
    )


def test_parameter_only_change_reuses_the_executable():
    base = water_fixtures.heredity_cell("D", dt=1e-3, end_time=STEPS * 1e-3)
    twin = scaled(base, 0.75)
    vector_windows._EXECUTABLES.clear()
    compiled, base_state = first_window(base)
    assert compiled > 0.0
    (stored,) = vector_windows._EXECUTABLES  # compile_window keys on world_key first...
    spec = parse_spec(base)
    host = vector_windows.spec_world_key(get_model(spec.model), spec, initialise(spec))
    assert stored[0] == host  # ...which a planner computes on the host, before any compile.
    reused, twin_state = first_window(twin)
    assert reused == 0.0  # The value twin compiled nothing.
    assert not same(base_state, twin_state)  # Its values did change the result.
    vector_windows._EXECUTABLES.clear()
    fresh, fresh_state = first_window(twin)
    assert fresh > 0.0
    assert same(twin_state, fresh_state)  # Reuse gives the fresh compile's bits.
    other, _ = first_window(without_nav(base))
    assert other > 0.0  # Another structure compiles its own executable.
