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
from cells.laws.electrochemistry import F as F_
from cells.laws.electrochemistry import R as R_
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


# The note's §9.3: the composed world (validation/fr64/worlds.composed_world), every step observed.
STEP_AT, COMPOSED_END, COMPOSED_DT = 0.06, 0.12, 2e-4
P1, P2, P3, P4 = 1, 2, 0, 3  # kv_bath, kv_reversal, B1's K population, na_block: channel slots.


@pytest.fixture(scope="module")
def composed():
    raw = worlds.composed_world(dt=COMPOSED_DT, end=COMPOSED_END, step_at=STEP_AT)
    spec = parse_spec(raw)
    return raw, spec, run(spec)


def composed_findings(raw, spec, result):
    """{item: worst misfit, at most 1 to pass} of §9.3's items 2 to 5 on every observed row."""
    from validation.fr64 import closed_forms

    model = get_model(spec.model)
    _, p = model.initial_values(spec)
    ids = list(spec.model.species_ids)
    k, h_row = ids.index("K"), ids.index("H")
    observed, history = result.observations, result.history
    v = np.asarray(observed.membrane_voltage_V)[:, 0]
    targets = np.asarray(observed.channel_targets)
    u = np.asarray(observed.channel_unblocked_fraction)
    cell_ph = np.asarray(observed.pH)[:, 0]
    held = np.asarray(history.bath_held_amount_fmol)
    c_in = (p.amount_reference[k, 0] + np.asarray(history.amount_increment)[:, k, 0]) / p.volume[0]
    c_out = held[:, k, 0] / p.extracellular_volume[0]
    h_bath = held[:, h_row, 0] / p.extracellular_volume[0]
    temperature = float(p.temperature)
    e_k = R_ * temperature / F_ * (np.log(c_out) - np.log(c_in))
    bath_shift = worlds.SIGMA * (-np.log10(h_bath / 1000.0) - worlds.REFERENCE_PH)
    cell_shift = worlds.SIGMA * (cell_ph - worlds.REFERENCE_PH)
    out = {}
    heat = np.asarray(history.channel_dissipated_energy_pJ)
    out["2: heat never falls"] = float(np.max(-np.diff(heat, axis=0), initial=0.0) > 0)
    worst = 0.0
    for slot, shift in ((P1, bath_shift), (P2, e_k)):
        m_at, h_at = kv_kinetics(v - shift)[0][0], kv_kinetics(v)[0][1]
        worst = max(worst, np.max(np.abs(targets[:, 0, slot] - m_at)) / 1e-11,
                    np.max(np.abs(targets[:, 1, slot] - h_at)) / 1e-11)  # fmt: skip
    out["3: the gates' targets at V_r"] = float(worst)
    block = next(c for c in spec.model.channels if c.id == "na_block").block
    modes = [(m.weight, m.k0_mM, s) for m, s in zip(block.modes, block.steepness(), strict=True)]
    worst = 0.0
    for slot, shift in ((P3, e_k), (P4, cell_shift)):
        for i in range(0, v.size, 25):
            law = closed_forms.unblocked(float(v[i] - shift[i]), temperature,
                                         block.concentration_mM, modes)  # fmt: skip
            worst = max(worst, abs(float(u[i, slot]) - float(law)) / (1e-12 * float(law)))
    out["4: the blocks' u at V_ref"] = worst
    gate = np.asarray(history.channel_gate)
    before = int(round(STEP_AT / COMPOSED_DT)) - 1
    worst = 0.0
    for row in (before, v.size - 1):
        for slot, shift in ((P1, bath_shift), (P2, e_k)):
            at_vr = kv_kinetics(np.asarray([v[row] - shift[row]]))[0][0, 0]
            at_v = kv_kinetics(np.asarray([v[row]]))[0][0, 0]
            worst = max(worst, abs(gate[row, 0, slot] - at_vr) / (abs(at_v - at_vr) / 4))
    out["5: the stage path, settled m at m_inf(V_r)"] = worst
    return out


def kv_kinetics(voltage):
    from cells.laws.channels import kv1p5_mh

    return kv1p5_mh.kinetics(np.asarray(voltage, dtype=float), xp=np)


def test_the_composed_world_reads_each_shift_on_every_row_and_restarts(composed, tmp_path):
    """§9.3 (compiled; about 45 s here, the compile included, measured at landing): over 600
    steps of ARS(2,2,2) on B4's world with a KCl-for-NaCl step at 60 ms, every host check passes,
    no population's heat falls, P1's and P2's observed m and h targets are Kv1.5's law at their
    V_r and at V, P3's and P4's observed u is FR-51's law at their V_ref (P4's pH B4's recorded),
    and at the settled rows before the step and at the end, P1's and P2's m sit at m_inf(V_r)
    within a quarter of |m_inf(V_r) - m_inf(V)|: the stage path. A restart from mid-run is bit
    for bit the uninterrupted run."""
    raw, spec, result = composed
    findings = composed_findings(raw, spec, result)
    assert all(value <= 1.0 for value in findings.values()), findings
    checkpoint = result.checkpoint_at(float(np.asarray(result.times)[len(result.times) // 2]))
    resumed = run(spec, checkpoint)
    for a, b in zip(resumed.history, result.history, strict=True):
        assert np.asarray(a)[-1].tobytes() == np.asarray(b)[-1].tobytes()
