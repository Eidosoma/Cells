"""Compiled guard of cytoplasmic_bridge_closure@1: Q4's open-bridge limit (S5 design §7.3).

With the bridge open (a = a_0: an exponential closure of 1e4 s, nearly constant over the run)
and R_b << Rm, a small current into d1 couples into d2 with the two-cell circuit's DC ratio,
V2 / V1 = Rm / (Rm + R_b).
* R_b = 1 / (2 a sigma_cyt) is the bridge's declared conductance.
* Rm is a daughter's input resistance, measured on the same world without a bridge.
The voltages are the changes from the same world without current, about 1.5 s (six membrane
time constants) after the division. The current is small (0.01 pA, about 0.3 mV), so the
membranes are linear. About a minute on one core (four compiled runs).
"""

import jax
import numpy as np
import pytest

from cells.core.runner import run
from cells.core.specs import parse_spec
from cells.models import pump_composite_adapter as adapter
from cells.models.registry import get_model
from tests import partition_fixtures as fx

END = 1.5
CURRENT_A = 1e-14
TAU = 1e4


@pytest.fixture(scope="module", autouse=True)
def x64():
    jax.config.update("jax_enable_x64", True)


def final_voltages(raw):
    """{cell id: its patch voltage} at the end (one patch per daughter, on the bath)."""
    raw["experiment"]["observation_times"] = [0.0, END]
    spec = parse_spec(raw)
    model = get_model(spec.model)
    result = run(spec)
    _, p = model.initial_values(spec)
    state = model.STATE_TYPE(*(np.asarray(v[-1]) for v in result.history))
    q = model.view(p, state, xp=np)
    v = adapter.patch_voltages(adapter.node_potentials(state, q, xp=np), q, xp=np)
    cells = [c.id for c in spec.model.cells]
    return {
        cells[int(q.membrane_cell[k])]: float(v[k])
        for k in np.flatnonzero(np.asarray(q.membrane_active))
    }, state


def test_an_open_bridge_couples_with_the_circuit_ratio():
    bridge = ("exponential", TAU)
    coupled, state = final_voltages(fx.divided(bridge=bridge, injection=CURRENT_A, end=END))
    base, _ = final_voltages(fx.divided(bridge=bridge, end=END))
    alone, _ = final_voltages(fx.divided(injection=CURRENT_A, end=END))
    alone_base, _ = final_voltages(fx.divided(end=END))
    rm = (alone["d1"] - alone_base["d1"]) / CURRENT_A
    a = float(np.asarray(state.bridge_aperture_m)[0])
    rb = 1.0 / (2 * a * fx.SIGMA_CYT)
    v1, v2 = coupled["d1"] - base["d1"], coupled["d2"] - base["d2"]
    assert rm > 50 * rb  # R_b << Rm.
    assert 1 - v2 / v1 == pytest.approx(rb / (rm + rb), rel=0.05)
