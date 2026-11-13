"""Compiled guard of cytoplasmic_bridge_closure@1: Q4's open-bridge limit (S5 design §7.3).

With the bridge open (a = a_0: an exponential closure of 1e4 s, nearly constant over the run)
and R_b << Rm, a small current into d1 couples into d2 with the two-cell circuit's DC ratio,
V2 / V1 = Rm / (Rm + R_b).
* R_b = 1 / (2 a sigma_cyt) is the bridge's declared conductance.
* Rm is a daughter's input resistance, measured on the same world without a bridge.
The voltages are the changes from the same world without current, about 1.5 s after the
division. The worlds are passive (no channel populations), as §7.3's circuit limits and
R-tissue's worlds are, and the current is small (0.01 pA). The bridge's own conductance in the
run, its current over its voltage, is 2 a sigma_cyt to 1e-3. A few minutes on one core (four
compiled runs).
"""

import math

import jax
import numpy as np
import pytest

from cells.core.runner import run
from cells.core.specs import parse_spec
from cells.models import pump_composite_adapter as adapter
from cells.models.registry import get_model
from cells.processes.electrochemistry import CHARGE_PER_FMOL
from tests import partition_fixtures as fx

END = 1.5
CURRENT_A = 1e-14
TAU = 1e4
# 0.25 ms. The injection's split half-steps lag the bridge's fast antisymmetric mode (rate about
# 490/s here) by half a step's charge, an O(dt) offset of V1 - V2 at the step's end: 8% of
# 1 - V2/V1 at 1 ms, about 2% at 0.25 ms.
DT = 2.5e-4


@pytest.fixture(scope="module", autouse=True)
def x64():
    jax.config.update("jax_enable_x64", True)


def passive(raw):
    """raw without channel populations (in place): §7.3's limits are linear-circuit ones, and
    R-tissue's worlds are passive too. Kir2.1 and NaV1.2 would make the two daughters' small-
    signal membranes differ under the current."""
    raw["model"]["channels"] = []
    raw["experiment"]["channel_controls"] = []
    raw["execution"]["channel_capacity"] = 0
    for block in raw["model"]["operators"]:
        if block["law"] == "membrane_entity_state@1":
            block["populations"] = []
        for division in block.get("divisions", []):
            division["populations"] = []
    return raw


def final_voltages(raw):
    """{cell id: its patch voltage} at the end (one patch per daughter, on the bath)."""
    raw["experiment"]["observation_times"] = [0.0, END]
    raw["execution"].update(dt=DT, max_steps=int(math.ceil(END / DT)) + 8)
    spec = parse_spec(passive(raw))
    model = get_model(spec.model)
    result = run(spec)
    _, p = model.initial_values(spec)
    state = model.STATE_TYPE(*(np.asarray(v[-1]) for v in result.history))
    q = model.view(p, state, xp=np)
    v = adapter.patch_voltages(adapter.node_potentials(state, q, xp=np), q, xp=np)
    cells = [c.id for c in spec.model.cells]
    voltages = {
        cells[int(q.membrane_cell[k])]: float(v[k])
        for k in np.flatnonzero(np.asarray(q.membrane_active))
    }
    return voltages, (model, spec, state, p)


def test_an_open_bridge_couples_with_the_circuit_ratio():
    bridge = ("exponential", TAU)
    coupled, (model, spec, state, p) = final_voltages(
        fx.divided(bridge=bridge, injection=CURRENT_A, end=END)
    )
    base, _ = final_voltages(fx.divided(bridge=bridge, end=END))
    alone, _ = final_voltages(fx.divided(injection=CURRENT_A, end=END))
    alone_base, _ = final_voltages(fx.divided(end=END))
    rm = (alone["d1"] - alone_base["d1"]) / CURRENT_A
    a = float(np.asarray(state.bridge_aperture_m)[0])
    rb = 1.0 / (2 * a * fx.SIGMA_CYT)
    # The bridge carries 2 a sigma_cyt in the run: its current over its voltage at the end.
    control = model.CONTROL_TYPE(*(np.asarray(v[0]) for v in fx.cs.control_values(spec, [END])))
    flux = np.asarray(model.readouts(state, control, p, xp=np).field.rates.junction_flux_fmol_s)
    current = CHARGE_PER_FMOL * np.sum(np.ravel(p.valence) * flux[:, 0])
    v1, v2 = coupled["d1"] - base["d1"], coupled["d2"] - base["d2"]
    assert current / (v1 - v2) == pytest.approx(1 / rb, rel=1e-3)
    assert rm > 50 * rb  # R_b << Rm.
    assert 1 - v2 / v1 == pytest.approx(rb / (rm + rb), rel=0.05)
