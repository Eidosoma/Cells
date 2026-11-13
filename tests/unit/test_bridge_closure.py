"""Tier-1 smoke test of cytoplasmic_bridge_closure@1 (docs/CELL_DIVISION_S5_DESIGN.md §4).

In NumPy on the compact division world with a bridge between its daughters (no compile):
* the bridge junction declares P_s A = 2 a_0 D_s^cyt, with D^cyt from the declared sigma_cyt, and a
  gate fixed open;
* its slot is @3 padding until the division (gate 0, minimum 0 at the view, closed): it opens
  with both daughters at its declared gate, carries no current at birth, and is padding again
  once a daughter retires, its history in the partition's record;
* its current follows the aperture: with unequal daughters it halves at a_0 / 2 and is exactly
  0 at a = 0, and at equal concentrations I / dV = 2 a sigma_cyt (end to end, through @3);
* exact half-steps: linear closure reaches a_0 (1 - t / tau) and stops at 0; exponential follows
  a_0 exp(-t / tau). Before its start the aperture is selected bitwise, and the availability
  factor is a / a_0 on the bridge and exactly 1 elsewhere;
* refusals: a gate not fixed open, P A off 2 a_0 D^cyt, a start off the division time, a
  daughter dividing again before its bridge has closed, and an a_0 beyond the step's
  explicit-rate bound (@3's step check, decision 12);
* a statically idle bridge set leaves the view and the ledgers bitwise unchanged.
"""

import copy
from types import SimpleNamespace

import jax
import numpy as np
import pytest

from cells.core.specs import ConfigError, parse_spec
from cells.models import pump_composite_adapter as adapter
from cells.models.operators import bridge_closure as bridge
from cells.models.operators import partition
from cells.models.registry import get_model
from cells.processes.electrochemistry import CHARGE_PER_FMOL
from tests import partition_fixtures as fx

H = 0.5 * fx.DT
TAU = 0.004


@pytest.fixture(scope="module", autouse=True)
def x64():
    jax.config.update("jax_enable_x64", True)


def bind(raw):
    spec = parse_spec(raw)
    model = get_model(spec.model)
    state, p = model.initial_values(spec)
    return spec, model, state, p


def operator(model, law):
    return next(op for op in model.operators if op.LAW_ID == law)


def divide(model, state, p, due):
    control = SimpleNamespace(partition_due=np.asarray(due, dtype=float))
    return operator(model, partition.LAW_ID).event(
        state, control, p, xp=np, view=lambda s: model.view(p, s, xp=np)
    )


def control_at(spec, model, time):
    values = fx.cs.control_values(spec, [time])
    return model.CONTROL_TYPE(*(np.asarray(v[0]) for v in values))


def edge(spec):
    return [j.id for j in spec.model.junctions].index("bridge_1")


def test_the_bridge_is_declared_from_sigma_cyt():
    spec, _, _, _ = bind(fx.divided(bridge=("linear", TAU)))
    junction = next(j for j in spec.model.junctions if j.id == "bridge_1")
    d = fx.diffusivity(fx.divided())
    for s, pa in zip(spec.model.species_ids, junction.permeability_m_per_s, strict=True):
        assert pa * junction.area_m2 == pytest.approx(2 * fx.APERTURE_M * d[s], rel=1e-15)
    assert junction.minimum_open_fraction == 1.0 and junction.initial_gate == 1.0
    # One obstruction factor sigma_cyt / sigma_free for every species.
    ratio = d["K"] / fx.FREE_D["K"]
    assert d["Na"] / fx.FREE_D["Na"] == pytest.approx(ratio) and 0 < ratio < 1


def test_the_bridge_is_padding_until_birth_and_after_retirement():
    spec, model, state, p = bind(fx.divided(bridge=("linear", 0.001), second=0.003, end=0.005))
    e = edge(spec)
    q = model.view(p, state, xp=np)
    assert not q.junction_active[e] and state.junction_gate[e] == 0 and q.junction_minimum[e] == 0
    born, ok = divide(model, state, p, (1, 0, 0))
    assert ok
    q = model.view(p, born, xp=np)
    assert q.junction_active[e] and born.junction_gate[e] == 1 and q.junction_minimum[e] == 1
    assert adapter.domain_valid(adapter.inner_state(born), q, q.active, xp=np)
    # Closed and carrying a history, it retires with the daughters into the record.
    history = np.array([2e-6, -1e-6, 5e-7, 0.0])
    closed = born._replace(
        bridge_aperture_m=np.zeros_like(born.bridge_aperture_m),
        junction_transferred=np.array(born.junction_transferred, copy=True),
        junction_dissipated_energy_pJ=np.array(born.junction_dissipated_energy_pJ, copy=True),
    )
    closed.junction_transferred[:, e] = history
    closed.junction_dissipated_energy_pJ[e] = 4e-8
    after, ok = divide(model, closed, p, (1, 1, 1))
    assert ok
    q = model.view(p, after, xp=np)
    assert not q.junction_active[e] and after.junction_gate[e] == 0 and q.junction_minimum[e] == 0
    assert np.array_equal(after.partition_retired_junction_transferred_fmol[:, e], history)
    assert after.partition_retired_junction_heat_pJ[e] == 4e-8
    assert (
        not after.junction_transferred[:, e].any() and after.junction_dissipated_energy_pJ[e] == 0
    )
    assert adapter.domain_valid(adapter.inner_state(after), q, q.active, xp=np)


def test_the_bridge_current_follows_its_aperture():
    spec, model, state, p = bind(fx.divided(bridge=("linear", TAU)))
    e = edge(spec)
    born, ok = divide(model, state, p, (1,))
    assert ok
    control = control_at(spec, model, 0.003)
    z = np.ravel(p.valence)

    def bridge_values(s, aperture):
        values = model.readouts(
            s._replace(bridge_aperture_m=np.array([aperture])), control, p, xp=np
        )
        assert values.valid
        r = values.field.rates
        return np.asarray(r.junction_flux_fmol_s)[:, e], float(np.asarray(r.junction_voltage_V)[e])

    at_birth, _ = bridge_values(born, fx.APERTURE_M)  # Equal potentials and concentrations.
    # Unequal daughters: K added to d1 (about 1 mV; its concentration moves by about 2e-6).
    s = born._replace(amount_increment=np.array(born.amount_increment, copy=True))
    s.amount_increment[list(spec.model.species_ids).index("K"), 1] += 8e-5
    full, dv = bridge_values(s, fx.APERTURE_M)
    half, _ = bridge_values(s, 0.5 * fx.APERTURE_M)
    zero, _ = bridge_values(s, 0.0)
    assert np.abs(full).max() > 0
    assert np.max(np.abs(at_birth)) <= 1e-9 * np.max(np.abs(full))
    assert np.allclose(half, 0.5 * full, rtol=1e-12, atol=0)
    assert not zero.any()
    current = CHARGE_PER_FMOL * np.sum(z * full)
    assert current * dv > 0  # Down the potential difference.
    assert current / dv == pytest.approx(2 * fx.APERTURE_M * fx.SIGMA_CYT, rel=1e-3)


def half_steps(model, state, p, closing, count):
    op = operator(model, fx.BRIDGE)
    control = SimpleNamespace(bridge_closing=np.asarray(closing, dtype=float))
    for _ in range(count):
        state, _ = op.half_step(state, H, control, p, xp=np)
    return state


@pytest.mark.parametrize("law", ["linear", "exponential"])
def test_exact_half_steps(law):
    _, model, state, p = bind(fx.divided(bridge=(law, TAU)))
    a0 = fx.APERTURE_M
    idle = half_steps(model, state, p, [0.0], 3)
    assert np.array_equal(idle.bridge_aperture_m, state.bridge_aperture_m)  # Selected, bitwise.
    k = 5
    moved = half_steps(model, state, p, [1.0], k)
    expected = a0 * (1 - k * H / TAU) if law == "linear" else a0 * np.exp(-k * H / TAU)
    assert moved.bridge_aperture_m[0] == pytest.approx(expected, rel=1e-13)
    factor = bridge.availability(moved, p, xp=np)
    assert factor[0] == pytest.approx(expected / a0, rel=1e-13)
    if law == "linear":
        closed = half_steps(model, moved, p, [1.0], 20)  # Past tau: stops at 0.
        assert closed.bridge_aperture_m[0] == 0.0


def test_the_availability_is_exactly_one_off_the_bridge():
    _, _, state, p = bind(fx.divided(bridge=("linear", TAU)))
    padded = p._replace(
        bridge_present=np.array([True, False]),
        bridge_initial_aperture_m=np.array([fx.APERTURE_M, 0.0]),
        bridge_closure_time_s=np.array([TAU, 1.0]),
        bridge_linear=np.array([True, False]),
    )
    shaped = state._replace(bridge_aperture_m=np.array([0.5 * fx.APERTURE_M, 0.0]))
    assert list(bridge.availability(shaped, padded, xp=np)) == [0.5, 1.0]


def edit(raw, change):
    raw = copy.deepcopy(raw)
    change(raw)
    return raw


def open_gate(raw):
    junction = next(j for j in raw["model"]["junctions"] if j["id"] == "bridge_1")
    junction["gate"]["minimum_open_fraction"] = 0.5


def off_permeability(raw):
    junction = next(j for j in raw["model"]["junctions"] if j["id"] == "bridge_1")
    junction["permeability_m_per_s"]["K"] *= 1 + 1e-9


def late_start(raw):
    raw["experiment"]["bridge_controls"][0]["start_time"] = 0.003


@pytest.mark.parametrize(
    "change, message",
    [
        (open_gate, "fixed open"),
        (off_permeability, "2 a_0 D"),
        (late_start, "starts closing at its division"),
    ],
)
def test_definition_refusals(change, message):
    with pytest.raises(ConfigError, match=message):
        parse_spec(edit(fx.divided(bridge=("linear", TAU)), change))


@pytest.mark.parametrize("law, tau", [("linear", 0.004), ("exponential", 0.0005)])
def test_a_daughter_divides_only_after_its_bridge_has_closed(law, tau):
    with pytest.raises(ConfigError, match="must have closed"):
        parse_spec(fx.divided(bridge=(law, tau), second=0.003, end=0.005))


def test_a_closed_bridge_admits_the_second_division():
    spec = parse_spec(fx.divided(bridge=("linear", 0.001), second=0.003, end=0.005))
    assert any(op.law == fx.BRIDGE for op in spec.model.operators)


def test_an_aperture_beyond_the_step_bound_is_refused():
    """a_0 is bounded by dt through @3's explicit-rate step check, which counts the bridge's
    declared conductance 2 a_0 sigma_cyt against the daughters' capacitances (decision 12)."""
    steps = np.array([fx.DT])
    spec = parse_spec(fx.divided(bridge=("linear", TAU)))
    get_model(spec.model).check_steps(spec, steps, None)  # The nominal aperture passes.
    wide = parse_spec(fx.divided(bridge=("linear", TAU, 50 * fx.APERTURE_M)))
    with pytest.raises(ConfigError, match="explicit-rate stability bound"):
        get_model(wide.model).check_steps(wide, steps, None)


def test_an_idle_bridge_set_changes_nothing():
    raw = fx.divided()
    raw["model"]["operators"].append(dict(law=fx.BRIDGE, bridges=[]))
    raw["experiment"]["bridge_controls"] = []
    _, idle, s1, p1 = bind(raw)
    _, plain, s2, p2 = bind(fx.divided())
    q1, q2 = idle.view(p1, s1, xp=np), plain.view(p2, s2, xp=np)
    for name in q2._fields:
        assert np.array_equal(np.asarray(getattr(q1, name)), np.asarray(getattr(q2, name))), name
    b1, b2 = idle.balances(s1, p1), plain.balances(s2, p2)
    for name in b2:
        assert np.array_equal(np.asarray(b1[name]), np.asarray(b2[name])), name
