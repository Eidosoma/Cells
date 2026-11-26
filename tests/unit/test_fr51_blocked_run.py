"""FR-51's run (fr51-channel-block-v1 criterion RUN): a cell started inside its blocked K
population's negative-slope region, under the IMEX solver.

The world is validation/fr51/engine.run_world: B1's block on a gate-free K population and a weak Na
leak on one patch, starting at +55 mV.

About 67 s, measured cold on the timed lane. It holds two compiled runs, the run and its restart
from mid-run, with host checks on every observed row; and criterion S, the fraction's strong end, on
two compiled clamped programs and one compiled checked step (RK4's). Reason: the per-stage bound's
new term is qualified on a compiled step, where the explicit stage meets a negative slope, and the
strong end where XLA flushes subnormals.
"""

import tempfile
from decimal import Decimal as D
from decimal import localcontext
from pathlib import Path

import jax
import numpy as np
import pytest

from cells.definitions import pump_composite_spec as cs
from cells.definitions.specs import parse_spec
from cells.definitions.surface_pump_v3_spec import control_values
from cells.execution.runner import run
from cells.laws.electrochemistry import CHARGE_PER_FMOL
from cells.records.io import load_snapshot, write_snapshot
from cells.registry.models import get_model
from validation.fr51 import closed_forms as fr51_laws
from validation.fr51 import engine as fr51
from validation.fr51 import judge as fr51_judge
from validation.fr51 import plants as fr51_plants

H = 1e-7  # The central difference's half step (V).
MID = 150  # The restart's checkpoint: the accepted time of this row, 15 ms.


def law_fraction(v, c_in, c_out, block, temperature):
    """B1's u at a row's V and its K concentrations, in 50-digit decimals (LAWS.md §3)."""
    with localcontext() as context:
        context.prec = 50
        f = D("6.02214076e23") * D("1.602176634e-19")
        r = D("6.02214076e23") * D("1.380649e-23")
        t = D(repr(temperature))
        e = r * t / f * (D(repr(c_out)) / D(repr(c_in))).ln()
        v_ref = D(repr(v)) - e
        c_b, z_b = D(repr(block.concentration_mM)), block.valence
        side = 1 if block.side == "outside" else -1
        num = den = D(0)
        for mode in block.modes:
            a = side * (1 if z_b > 0 else -1) * abs(z_b) * D(repr(mode.electrical_distance)) * f
            k = D(repr(mode.k0_mM)) * (a / (r * t) * v_ref).exp()
            w = D(repr(mode.weight))
            num, den = num + w * k / (c_b + k), den + w
        return float(num / den)


@pytest.fixture(scope="module")
def blocked_run():
    spec = parse_spec(fr51.run_world())
    model = get_model(spec.model)
    _, p = model.initial_values(spec)
    control = model.Control(*(v[0] for v in control_values(spec, [0.0])))
    return spec, model, p, control, run(spec)


def rows(result, model):
    """The run's state at each observed row (every step is observed)."""
    history = result.history
    count = np.asarray(history.channel_gate).shape[0]
    return [model.STATE_TYPE(*(np.asarray(v)[i] for v in history)) for i in range(count)]


def row_checks(model, p, control, state):
    """(V, the K population's dI/dV by central difference, the per-stage rate) at a row."""
    w = model.readouts(state, control, p, xp=np)
    v = float(w.field.rates.membrane_voltage_V[0])
    up = model.clamped_channel_flux(state, control, p, v + H, xp=np)[1][0]
    down = model.clamped_channel_flux(state, control, p, v - H, xp=np)[1][0]
    rate = float(model.membrane_rate(state, control, p, xp=np, potentials=w.field.potential_V))
    return v, (up - down) / (2 * H), rate


def test_a_blocked_run_holds_the_per_stage_bound_through_its_negative_slope(blocked_run):
    """RUN's items 1 to 4 on every observed row, the negative-slope rows, and its plant:
    1. the run completes, so every host check passed on every row, the ledgers included;
    2. each population's cumulative heat is non-decreasing;
    3. channel_unblocked_fraction equals the law at the row's V and E within 1e-12;
    4. the per-stage rate at the row's state is at least |dI_blocked/dV|/C, with the slope a central
       difference of the clamped current (h = 1e-7 V);
    - at least 10 rows lie where that slope is negative;
    - the block's term dropped (u G_max) fails item 4 on one of them."""
    spec, model, p, control, result = blocked_run
    heat = np.asarray(result.history.channel_dissipated_energy_pJ).sum(axis=1)
    assert np.all(np.diff(heat, axis=0) >= 0)
    block = spec.model.channels[0].block
    observed = result.observations
    u = np.asarray(observed.channel_unblocked_fraction)[:, 0]
    states = rows(result, model)
    capacitance = float(np.asarray(p.membrane_capacitance)[0])
    negative = 0
    for i, state in enumerate(states):
        v, slope, rate = row_checks(model, p, control, state)
        ci = float((np.asarray(p.amount_reference) + np.asarray(state.amount_increment))[1, 0])
        co = float(
            (np.asarray(p.extracellular_amount_reference)
             + np.asarray(state.extracellular_amount_increment))[1, 0]
        )  # fmt: skip
        expected = law_fraction(v, ci / float(p.volume[0]), co / float(p.extracellular_volume[0]),
                                block, float(p.temperature))  # fmt: skip
        assert abs(u[i] - expected) <= 1e-12 * expected, (i, u[i], expected)
        assert rate >= abs(slope) / capacitance * (1 - 1e-12), (i, rate, slope)
        negative += slope < 0
    assert negative >= 10
    with fr51_plants.term_dropped():
        planted = [row_checks(model, p, control, state) for state in states]
    assert any(s < 0 and r < abs(s) / capacitance for _, s, r in planted)


def test_a_blocked_run_restarts_bitwise_and_its_composite_clamps_as_at_3(blocked_run):
    """RUN's restart and its composite (about 15 s of the file's time):
    - a checkpoint at 15 ms, written, loaded and resumed, is the uninterrupted run bit for bit,
      each history field from the checkpoint's row on;
    - the composite's clamped entry point (the same world as cells.model.resolved_pump_composite@1) gives @3's
      flux and current bit for bit at the first row, with the block's terms too."""
    spec, model, p, control, result = blocked_run
    checkpoint = result.checkpoint_at(float(np.asarray(result.times)[MID]))
    with tempfile.TemporaryDirectory() as tmp:
        write_snapshot(Path(tmp) / "checkpoint", result.spec, checkpoint)
        loaded = load_snapshot(Path(tmp) / "checkpoint")
        resumed = run(loaded.spec, loaded.checkpoint)
    for a, b in zip(resumed.history, result.history, strict=True):
        assert np.array_equal(np.asarray(a), np.asarray(b)[checkpoint.step_index :])
    composite = parse_spec(cs.frozen_definition(fr51.run_world()))
    outer = get_model(composite.model)
    state0, p0 = outer.initial_values(composite)
    control0 = outer.CONTROL_TYPE(*(v[0] for v in cs.control_values(composite, [0.0])))
    state, _ = model.initial_values(spec)
    ours = outer.clamped_channel_flux(state0, control0, p0, 0.02, block=True)
    theirs = model.clamped_channel_flux(state, control, p, 0.02, xp=np, block=True)
    assert np.array_equal(ours[0], theirs[0]) and np.array_equal(ours[1], theirs[1])
    assert np.array_equal(ours[2].voltage_term_S, theirs[2].voltage_term_S)


STEP = 1e-5  # One checked step (s).


def test_the_fraction_s_strong_end_on_the_compiled_program():
    """FR-51's S compiled: u and each mode's theta (1 - theta) within 1e-12 of the closed forms for
    S1 (u about 1e-18) and S2, on the compiled clamped program; and one compiled checked step of
    S1's world moves the population's amount by u J_free dt within 1e-12 (delta = 0, so u is
    constant, and nothing else moves the cell's voltage). The literal form's plant is a host row."""
    grid = np.array([-0.120 + 0.0005 * j for j in range(361)])
    points = [D(str(v)) for v in grid[::40]]
    for case_id in ("S1_strong_one_mode", "S2_strong_two_modes"):
        _, state, control, p, _ = fr51.world(case_id)
        terms = fr51.program(case_id)(state, control, p, grid[::40])[2]
        r = fr51_laws.case_values(case_id, points)
        part = np.moveaxis(
            (np.asarray(terms.block.theta) * np.asarray(terms.block.free))[:, :, 0], 0, 1
        )
        assert fr51_judge.within(np.asarray(terms.block.u)[:, 0], r["u"])[0]
        assert fr51_judge.within(part, r["slope_part"])[0]
    model, state, control, p, _ = fr51.world("S1_strong_one_mode")
    v0 = float(model.readouts(state, control, p, xp=np).field.rates.membrane_voltage_V[0])
    strong = jax.jit(model.checked_step)(state, STEP, control, p, p.active)[0]
    law = fr51_laws.case_values("S1_strong_one_mode", [D(repr(v0))])
    expected = law["u"][0] * law["I_free"][0] / CHARGE_PER_FMOL * STEP  # fmol in one step.
    moved = np.asarray(strong.channel_transferred)[1, 0]  # K's row, the population.
    assert fr51_judge.within(moved, expected)[0]
