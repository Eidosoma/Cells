"""FR-64's compiled worlds (D224: their seconds and reason are stated at landing).

**Why a compiled file.** Only a compiled run reaches the step's record block and the stage path
with the static switches traced. The host rows are tests/unit/test_surface_pump_v3_populations.py's.

**D327's pair** (the lead's ruling 1 of 27 November). FR-50 phase 2's one-way channel records sit
on three shifted populations of FR-50's World 1, with B4 at its cell
(validation/fr64/worlds.pair_world):
- a block on the cell's pH (B4's free h, read through the step's end views);
- Kv1.5's m on the bath's pH;
- Kv1.5's m on V - E_K.

The world is steady at V = E_K, so FR-50's E4 criteria (validation/fr50/REGISTRATION.md §3) apply
unchanged on every accepted row of 100 compiled steps of 0.1 ms:
- each direction within 1e-11 of its 50-digit closed form, the block's u at its V_ref
  (validation/fr64/closed_forms.pair_one_way);
- the gap at most 1e-12;
- closure;
- the kernel closure within 4 ulps, by the host split at the row's own state.

The plants are host rows: the split's u without the shift, its permeation at V_ref, and the end
view's stored row in place of its read.
"""

import numpy as np
import pytest

from cells.definitions.specs import parse_spec
from cells.definitions.surface_pump_v3_spec import control_values
from cells.execution.runner import run
from cells.registry.models import get_model
from validation.fr50 import engine as fr50
from validation.fr64 import closed_forms as laws
from validation.fr64 import worlds

DT, END = 1e-4, 1e-2
POPULATIONS = ("k_population", *worlds.KV)


@pytest.fixture(scope="module")
def pair():
    raw = worlds.pair_world(dt=DT, end=END)
    spec = parse_spec(raw)
    return raw, spec, run(spec)


def kernel_closure(spec, result):
    """The largest excess of |forward - backward - flux| over 4 ulps of forward + backward, per
    population of the K row, at every accepted row's own state (the host split, as FR-50's
    channel_split_rows forms it)."""
    impl = get_model(spec.model)
    _, p = impl.initial_values(spec)
    times = np.asarray(result.times, dtype=np.float64)
    controls = control_values(spec, times)
    history = [np.asarray(v) for v in result.history]
    k, worst = list(spec.model.species_ids).index("K"), 0.0
    for i in range(times.size):
        state = impl.STATE_TYPE(*(v[i] for v in history))
        control = impl.Control(*(np.asarray(v)[i] for v in controls))
        voltage = impl.field_values(state, control, p, xp=np).rates.membrane_voltage_V
        flux, _, (out, back) = impl.clamped_channel_flux(state, control, p, voltage, xp=np,
                                                         one_way=True)  # fmt: skip
        for slot in range(len(POPULATIONS)):
            f, b, j = out[k, slot], back[k, slot], flux[k, slot]
            worst = max(worst, float(abs(f - b - j) / (4 * np.spacing(f + b))))
    return worst


def test_the_pair_s_records_meet_e4_s_criteria_on_every_row(pair):
    """D327's pair, compiled (about 30 s, the compile included): each population's records against
    its closed form at every accepted row, the gap, the closure and the kernel closure."""
    raw, spec, result = pair
    for name in POPULATIONS:
        rows = fr50.own_rows(result, DT, ("channel", name, "K"))
        forward, backward = (float(v) for v in laws.pair_one_way(raw, name, worlds.CELL_PH))
        t = rows["n"] * DT
        live = t > 0
        assert np.all(np.abs(rows["F"][live] - forward * t[live]) <= 1e-11 * forward * t[live])
        assert np.all(np.abs(rows["B"][live] - backward * t[live]) <= 1e-11 * backward * t[live])
        assert np.all(rows["gap"] <= 1e-12), name
        net0, eps = rows["net"][0], np.finfo(float).eps
        scale = rows["F"] + rows["B"] + np.abs(rows["net"]) + abs(net0)
        assert np.all(
            np.abs(rows["F"] - rows["B"] - (rows["net"] - net0)) <= 2.5 * eps * rows["n"] * scale
        ), name
    assert kernel_closure(spec, result) <= 1.0
