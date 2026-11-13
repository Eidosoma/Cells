"""surface_tissue.capacitor_change gives one computation of a state's plate charges.

S3 prerequisite (c) (docs/PUMP_COMPOSITE_V2_DESIGN.md §3). The electrode ledger books the
change of the held nodes' plate charges over each step and checks the running sum against
the plate charges of the current state, so every evaluation of one state must give the
same bits. On the Xenopus egg, XLA once summed the species in two orders: in species order
at the start of @3's step, and as (Na + Cl) + K at its end, where the sum was fused with
the end state's amounts. Once Na's increment passed 2^16 fmol, with Cl's term a fraction of
Na's ulp, the ledger drifted by 7e-22 C per step.

The state is built directly, not from a saved run: Na and K increments of +-66,396 fmol
and Cl's -7.34e-12 fmol, the values the egg's pulses left at 300 s. Without the fix, both
programs below (injection idle, and no operator) lose 6.96e-22 C on every step.
"""

import copy

import jax
import numpy as np
import pytest

jax.config.update("jax_enable_x64", True)

from cells.core import runner  # noqa: E402
from cells.core.schedule import control_values  # noqa: E402
from cells.core.specs import parse_spec  # noqa: E402
from cells.core.state import initialise  # noqa: E402
from cells.models import pump_composite_adapter as adapter  # noqa: E402
from cells.models import surface_tissue as tissue  # noqa: E402
from cells.models.registry import get_model  # noqa: E402
from validation.tissue import injection_rm1 as rm1  # noqa: E402

STEPS = 300
EGG_INCREMENTS = {"Na": 66396.38382056737, "K": -66396.3838205675, "Cl": -7.340350549611685e-12}


def egg(*, injection):
    """The uncleaved Rm1 egg at 1 ms for STEPS steps: injection idle, or no operator."""
    raw = copy.deepcopy(rm1.definition(1e-3))
    raw["experiment"]["end_time"] = STEPS * 1e-3
    raw["experiment"]["observation_times"] = [0.0, STEPS * 1e-3]
    raw["execution"]["max_steps"] = STEPS + 8
    controls = raw["experiment"]["injection_controls"]
    if injection:
        cell = controls[0]["cell_id"]
        raw["experiment"]["injection_controls"] = [
            dict(cell_id=cell, schedule=[dict(time=0.0, current_A=0.0)])
        ]
    else:
        raw["model"]["operators"] = []
        del raw["experiment"]["injection_controls"]
    return raw


@pytest.mark.parametrize("injection", [True, False], ids=["injection_idle", "no_operator"])
def test_the_electrode_ledger_closes_exactly_at_egg_scale(injection):
    raw = egg(injection=injection)
    spec = parse_spec(raw)
    model = get_model(spec.model)
    start = initialise(spec)
    bound = adapter.inner_layout(start.layout)
    n = bound.active.size
    ids = [s["id"] for s in raw["model"]["species"]]
    increment = np.array(start.state.amount_increment, copy=True)
    for species, value in EGG_INCREMENTS.items():
        increment[ids.index(species), 0] = value
    state = start.state._replace(amount_increment=increment)

    def plates(row):
        _, cap, _ = tissue.capacitor_change(model.inner_state(row), bound, xp=np)
        return np.where(bound.reservoir, cap[n:], 0.0)

    state = state._replace(electrode_charge_transferred_C=plates(state))  # Ledger 0 at start.
    times = runner.timeline(spec)
    _, history, valid = runner._compiled_discrete_rollout(
        state,
        runner.integration_steps(spec, times),
        control_values(spec, times[:-1]),
        model.parameters(spec, start.layout),
        start.layout.active,
        model.checked_step,
    )
    h = type(history)(*(np.asarray(v) for v in history))
    assert np.all(np.asarray(valid)) and len(h.amount_increment) == STEPS
    na, cl = ids.index("Na"), ids.index("Cl")
    assert np.all(h.amount_increment[:, na, 0] > 2.0**16)  # Na's ulp is 2^-36 fmol throughout,
    assert np.all(h.amount_increment[:, cl, 0] == EGG_INCREMENTS["Cl"])  # and Cl's term fixed.
    plate = np.asarray([plates(type(h)(*(v[r] for v in h))) for r in range(STEPS)])
    ledger = h.electrode_charge_transferred_C - plate
    # The device's bookings telescope bit for bit. The host's solve (NumPy) and the device's
    # (XLA) may differ by one rounding of a plate charge, so the host ledger is at most one
    # ulp on a row and never accumulates. Without the fix it fell by 7e-22 C per step.
    assert np.all(np.abs(ledger) <= np.spacing(np.abs(plate)))
