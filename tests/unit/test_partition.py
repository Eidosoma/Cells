"""Tier-1 smoke test of isopotential_partition@1 and the closers (docs/CELL_DIVISION_S5_DESIGN.md).

In NumPy on bound compact worlds (no compile), all built from neither J1 input:
* closers (§2): pending daughters are @3 padding at the view, with closed masks, zero reference
  amounts and law code 0, and @3's domain holds there;
* the energy rule's reference (§3.6 point 4): every ledger is exactly 0 at row 0 with pending
  slots, and the capacitor energy is 1/2 sum C V^2(t) - 1/2 sum C V^2(0) over the live slots,
  checked against a nodal solve written here;
* the event (§3.4): a symmetric division is exact (the daughters' increments are half the
  parent's bit for bit, every booking an exact zero); moved transfers sum to zero; the record
  holds the retired history, which @3 sees zeroed; the daughters sit at the parent's potential;
  the event changes no ledger, and heat stays monotone on the adjusted row;
* an asymmetric division with mismatch carriers: the charge follows the patches and the booked
  work is the unmixing term, RT sum delta^2 / (2 n f (1 - f));
* refusals: inexact anchors, an unmapped population, a pump, a provider beside a closer, a
  daughter amount driven <= 0, and a division of an unborn parent;
* an idle partition is bitwise the composition without it; the lineage summary.
The compiled guards are test_partition_runs.py.
"""

import copy
import math
from types import SimpleNamespace

import jax
import numpy as np
import pytest

from cells.core.specs import ConfigError, parse_spec
from cells.models import pump_composite_adapter as adapter
from cells.models.operators import partition
from cells.models.registry import get_model
from cells.processes.electrochemistry import CHARGE_PER_FMOL, R
from tests import partition_fixtures as fx

HISTORY = (1e-3, -1e-3, 2e-4, 0.0)  # A synthetic pre-event increment of the parent (fmol).


@pytest.fixture(scope="module", autouse=True)
def x64():
    jax.config.update("jax_enable_x64", True)


def bind(raw):
    spec = parse_spec(raw)
    model = get_model(spec.model)
    state, p = model.initial_values(spec)
    return spec, model, state, p


def operator(model):
    return next(op for op in model.operators if op.LAW_ID == partition.LAW_ID)


def with_history(state, p):
    """A pre-event state: increments, transfers and heat on the parent, and a grown patch."""
    s = state._replace(
        **{
            k: np.array(getattr(state, k), copy=True)
            for k in (
                "amount_increment",
                "membrane_transferred",
                "membrane_dissipated_energy_pJ",
                "channel_dissipated_energy_pJ",
                "membrane_area_increment_m2",
                "membrane_capacitance_increment_F",
            )
        }
    )
    s.amount_increment[:, 0] = HISTORY
    s.membrane_transferred[:, 0] = -s.amount_increment[:, 0]
    s.membrane_dissipated_energy_pJ[0] = 1e-6
    s.channel_dissipated_energy_pJ[1, 0] = 3e-7
    s.membrane_area_increment_m2[0] = 2.5e-13
    s.membrane_capacitance_increment_F[0] = 0.05 * 2.5e-13
    return s


def divide(model, state, p, due=(1.0,)):
    control = SimpleNamespace(partition_due=np.asarray(due, dtype=float))
    return operator(model).event(state, control, p, xp=np, view=lambda s: model.view(p, s, xp=np))


def live_energy(state, q):
    """1/2 sum C V^2 (pJ) of the live patches by a nodal solve written here (not the adapter's)."""
    n, o = q.active.size, q.outside_active.size
    live = np.asarray(q.membrane_active)
    i, j = np.asarray(q.membrane_cell), n + np.asarray(q.membrane_outside)
    c = np.where(live, q.membrane_capacitance, 0.0)
    k = np.zeros((n + o, n + o))
    for a, b, value in zip(i, j, c, strict=True):
        k[a, a] += value
        k[b, b] += value
        k[a, b] -= value
        k[b, a] -= value
    charge = np.concatenate((q.initial_cell_charge_C, q.initial_outside_charge_C))
    charge = charge + CHARGE_PER_FMOL * np.concatenate(
        (
            np.sum(q.valence * state.amount_increment, axis=0),
            np.sum(q.valence * state.extracellular_amount_increment, axis=0),
        )
    )
    free = np.concatenate((np.asarray(q.active), np.asarray(q.outside_active) & ~q.reservoir))
    phi = np.zeros(n + o)
    phi[n:] = np.where(q.reservoir, q.boundary_V, 0.0)
    held = ~free
    phi[free] = np.linalg.solve(
        k[np.ix_(free, free)], charge[free] - k[np.ix_(free, held)] @ phi[held]
    )
    v = phi[i] - phi[j]
    return 0.5e12 * np.sum(c * v * v), phi


def test_pending_daughters_are_padding_at_the_view():
    _, model, state, p = bind(fx.divided())
    q = model.view(p, state, xp=np)
    assert list(q.active) == [True, False, False]
    assert list(q.membrane_active) == [True, False, False]
    assert not q.channel_active[2:].any() and q.channel_active[:2].all()
    assert (q.channel_laws[2:] == 0).all() and (q.amount_reference[:, 1:] == 0).all()
    assert adapter.domain_valid(adapter.inner_state(state), q, q.active, xp=np)


def test_every_ledger_is_zero_at_row_zero_with_pending_slots():
    """Exactly 0, apart from @3's own capacitor-consistency ledger on the declared layout, whose
    solve over every declared cell leaves rounding (about 1e-28 C)."""
    _, model, state, p = bind(fx.divided(second=0.003))
    for name, value in model.balances(state, p).items():
        if name == "charge":
            assert np.max(np.abs(np.asarray(value))) <= 1e-26, name
        else:
            assert np.all(np.asarray(value) == 0), name


def test_the_capacitor_energy_is_referenced_to_the_initial_view():
    """The composite's capacitor energy is 1/2 sum C V^2(t) - 1/2 sum C V^2(0) over live slots,
    before the event and after it (an independent nodal solve)."""
    _, model, state, p = bind(fx.divided())
    e0, _ = live_energy(state, model.view(p, state, xp=np))
    s = with_history(state, p)
    for current in (s, divide(model, s, p)[0]):
        q = model.view(p, current, xp=np)
        bound = adapter.inner_layout(p)
        _, _, dv = adapter.tissue.capacitor_change(current, bound, xp=np)
        declared = 0.5e12 * np.sum(
            bound.membrane_capacitance * dv * (2 * bound.initial_membrane_voltage_V + dv)
        )
        energy = declared + model._view_energy_terms(current, p, xp=np)[0]
        e1, _ = live_energy(current, q)
        assert energy == pytest.approx(e1 - e0, rel=1e-9, abs=1e-12 * abs(e0))


def test_a_symmetric_division_is_exact():
    _, model, state, p = bind(fx.divided())
    s = with_history(state, p)
    new, ok = divide(model, s, p)
    assert ok
    half = 0.5 * np.asarray(HISTORY)
    assert np.array_equal(new.amount_increment[:, 1], half)
    assert np.array_equal(new.amount_increment[:, 2], half)
    assert np.array_equal(new.amount_increment[:, 0], np.zeros(4))
    assert np.array_equal(new.partition_moved_fmol.sum(axis=1), np.zeros(4))
    # The chemical part of the work is exactly 0 (halving is exact); what is left is the
    # capacitor energy's rounding between the two views' solves.
    g0 = adapter.chemical_free_energy_pJ(s.amount_increment, p, xp=np)
    g1 = adapter.chemical_free_energy_pJ(new.amount_increment, p, xp=np)
    assert g1[1] + g1[2] == g0[0] and g1[0] == 0.0
    u = 0.5e12 * p.membrane_capacitance[0] * 0.1**2  # A bound on 1/2 C V^2 (|V| < 0.1 V).
    assert abs(new.partition_work_pJ[0]) <= 1e-14 * u
    assert list(new.division_applied) == [1]
    # The record holds the retired history; @3 sees it zeroed.
    assert np.array_equal(
        new.partition_retired_membrane_transferred_fmol[:, 0], -np.asarray(HISTORY)
    )
    assert new.partition_retired_membrane_heat_pJ[0] == 1e-6
    assert new.membrane_dissipated_energy_pJ[0] == 0.0 and not new.membrane_transferred[:, 0].any()
    assert new.channel_dissipated_energy_pJ[1, 0] == 0.0
    assert new.partition_retired_channel_heat_pJ[1, 0] == 3e-7
    # Areas and gates.
    assert new.membrane_area_increment_m2[1] == new.membrane_area_increment_m2[2] == 1.25e-13
    assert new.membrane_area_increment_m2[0] == 0.0
    # Populations [kir, nav, kir_d1, kir_d2, nav_d1, nav_d2]: each daughter's takes its parent's.
    for kid, source in ((2, 0), (3, 0), (4, 1), (5, 1)):
        assert np.array_equal(new.channel_gate[:, kid], s.channel_gate[:, source])


def test_the_daughters_sit_at_the_parents_potential():
    _, model, state, p = bind(fx.divided())
    s = with_history(state, p)
    new, _ = divide(model, s, p)
    _, phi0 = live_energy(s, model.view(p, s, xp=np))
    _, phi1 = live_energy(new, model.view(p, new, xp=np))
    assert phi1[1] == pytest.approx(phi0[0], rel=1e-12)
    assert phi1[2] == pytest.approx(phi0[0], rel=1e-12)
    q1 = model.view(p, new, xp=np)
    assert list(q1.active) == [False, True, True]
    assert adapter.domain_valid(adapter.inner_state(new), q1, q1.active, xp=np)


def test_the_event_changes_no_ledger_and_heat_stays_monotone():
    _, model, state, p = bind(fx.divided())
    s = with_history(state, p)
    new, _ = divide(model, s, p)
    before, after = model.balances(s, p), model.balances(new, p)
    for name in before:
        scale = np.max(np.abs(np.asarray(before[name])), initial=0.0)
        diff = np.max(np.abs(np.asarray(after[name]) - np.asarray(before[name])), initial=0.0)
        assert diff <= 1e-12 * max(scale, 1e-12), name
    a0, a1 = model._adjusted(s, p, xp=np), model._adjusted(new, p, xp=np)
    for name in model.DISSIPATION_FIELDS:
        assert np.all(np.asarray(getattr(a1, name)) - np.asarray(getattr(a0, name)) >= 0), name
    # Negative control: a replay with the record zeroed moves the local ledger.
    blank = new._replace(**{r: np.zeros_like(getattr(new, r)) for r in partition.RECORD.values()})
    assert np.max(np.abs(model.balances(blank, p)["local"] - before["local"])) > 1e-6


def test_a_neighbour_contact_maps_to_the_daughters_with_its_gate():
    """A gated contact to a neighbour (§8.1's variant): its daughter contacts are padding until
    the division (gate 0 and minimum 0 at the view), then take the parent contact's gate at the
    event; the parent's contact becomes padding, its history in the record; no ledger moves."""
    _, model, state, p = bind(fx.divided(neighbour=True))
    q = model.view(p, state, xp=np)
    assert list(q.junction_active) == [True, False, False]  # [contact, contact_d1, contact_d2]
    assert list(state.junction_gate) == [fx.CONTACT["gate"]["initial_gate"], 0.0, 0.0]
    assert list(q.junction_minimum) == [0.1, 0.0, 0.0]
    assert adapter.domain_valid(adapter.inner_state(state), q, q.active, xp=np)
    # A pre-event history: a gate away from its declared value, and transfers through the
    # parent's patch and across the contact matched by the cells' increments. Dyadic values keep
    # every sum exact, so the local ledger is exactly 0.
    s = state._replace(
        amount_increment=np.array(state.amount_increment, copy=True),
        membrane_transferred=np.array(state.membrane_transferred, copy=True),
        junction_transferred=np.array(state.junction_transferred, copy=True),
        junction_gate=np.array([0.37, 0.0, 0.0]),
        junction_dissipated_energy_pJ=np.array([2e-7, 0.0, 0.0]),
    )
    leak = np.array([-(2.0**-10), 2.0**-10, -(2.0**-12), 0.0])  # fmol
    flow = np.array([2.0**-15, -(2.0**-16), 2.0**-17, 0.0])  # fmol
    s.membrane_transferred[:, 0] = leak
    s.junction_transferred[:, 0] = flow
    s.amount_increment[:, 0] = -(leak + flow)
    s.amount_increment[:, 1] = flow
    new, ok = divide(model, s, p)
    assert ok
    assert list(new.junction_gate) == [0.0, 0.37, 0.37]
    q1 = model.view(p, new, xp=np)
    assert list(q1.junction_active) == [False, True, True]
    assert list(q1.junction_minimum) == [0.0, 0.1, 0.1]
    assert adapter.domain_valid(adapter.inner_state(new), q1, q1.active, xp=np)
    assert np.array_equal(new.partition_retired_junction_transferred_fmol[:, 0], flow)
    assert new.partition_retired_junction_heat_pJ[0] == 2e-7
    assert not new.junction_transferred.any() and not new.junction_dissipated_energy_pJ.any()
    before, after = model.balances(s, p), model.balances(new, p)
    for name in before:
        scale = np.max(np.abs(np.asarray(before[name])), initial=0.0)
        diff = np.max(np.abs(np.asarray(after[name]) - np.asarray(before[name])), initial=0.0)
        assert diff <= 1e-12 * max(scale, 1e-12), name
    assert not np.asarray(before["local"]).any() and not np.asarray(after["local"]).any()


def test_an_asymmetric_division_books_the_unmixing_work():
    f, a = 0.75, 0.6
    _, model, state, p = bind(fx.divided(f=f, area_fraction=a, carriers={"Na": 0.5, "K": 0.5}))
    s = with_history(state, p)
    q = model.view(p, s, xp=np)
    v = adapter.patch_voltages(adapter.node_potentials(s, q, xp=np), q, xp=np)
    charge = q.membrane_capacitance[0] * v[0]
    new, ok = divide(model, s, p)
    assert ok
    dq = (a - f) * charge
    delta = np.array([0.5, 0.5, 0.0, 0.0]) * dq / CHARGE_PER_FMOL
    expected = f * np.asarray(HISTORY) + delta
    assert np.allclose(new.amount_increment[:, 1], expected, rtol=1e-12, atol=1e-18)
    # The daughter's charge follows its patches: Q_D1 = a q (one patch).
    q_d1 = p.initial_cell_charge_C[1] + CHARGE_PER_FMOL * np.sum(
        np.ravel(p.valence) * new.amount_increment[:, 1]
    )
    assert q_d1 == pytest.approx(
        a
        * (
            p.initial_cell_charge_C[0]
            + CHARGE_PER_FMOL * np.sum(np.ravel(p.valence) * s.amount_increment[:, 0])
        ),
        rel=1e-12,
    )
    # The unmixing term, to leading order, and >= 0.
    n = p.amount_reference[:, 0] + s.amount_increment[:, 0]
    rt = 1e-3 * R * p.temperature
    unmixing = rt * np.sum(delta**2 / (2 * n * f * (1 - f)))
    assert new.partition_work_pJ[0] >= 0
    assert new.partition_work_pJ[0] == pytest.approx(unmixing, rel=1e-3)  # Next order: delta/n.


def test_a_daughter_driven_empty_refuses_the_event():
    _, model, state, p = bind(fx.divided())
    s = state._replace(amount_increment=np.array(state.amount_increment, copy=True))
    s.amount_increment[0, 0] = -0.999 * p.amount_reference[0, 0]
    s.amount_increment[0, 0] -= 0.5 * p.amount_reference[0, 0]  # Below zero once halved.
    with np.errstate(invalid="ignore"):  # The emptied parent's logarithm is NaN, as meant.
        _, ok = divide(model, s, p)
    assert not ok


def edited(change):
    raw = fx.divided()
    change(raw)
    return raw


def perturb_volume(raw):
    cell = next(c for c in raw["model"]["cells"] if c["id"] == "d1")
    cell["volume_pL"] *= 1 + 1e-15


def drop_population(raw):
    block = raw["model"]["operators"][1]["divisions"][0]
    block["populations"] = block["populations"][1:]


def add_pump(raw):
    base = fx.wfx.heredity_cell("H", dt=fx.DT, end_time=0.004)
    patch = next(m for m in raw["model"]["membranes"] if m["id"] == "membrane_0")
    patch["pump"] = copy.deepcopy(base["model"]["membranes"][0]["pump"])
    raw["experiment"]["pump_controls"] = copy.deepcopy(base["experiment"]["pump_controls"])


def unborn_parent(raw):
    raw2 = fx.divided(second=0.003)
    raw.clear()
    raw.update(raw2)
    for event in raw["experiment"]["partition_events"]:
        if event["division"] == "second_d1":
            event["time"] = 0.001


@pytest.mark.parametrize(
    "change, message",
    [
        (perturb_volume, "anchor rule"),
        (drop_population, "population"),
        (add_pump, "Pumps"),
        (unborn_parent, "after its parent's birth"),
    ],
)
def test_definition_refusals(change, message):
    with pytest.raises(ConfigError, match=message):
        parse_spec(edited(change))


def test_a_provider_beside_a_closer_is_refused():
    raw = fx.divided()
    raw["model"]["operators"].append(
        dict(
            law="scheduled_membrane_insertion@1",
            patches=[
                dict(
                    membrane_id="membrane_0",
                    specific_capacitance_F_per_m2=0.05,
                    population_densities_per_m2={},
                )
            ],
        )
    )
    raw["experiment"]["insertion_controls"] = [
        dict(
            membrane_id="membrane_0", onset_time=None, schedule=[dict(time=0.0, rate_m2_per_s=0.0)]
        )
    ]
    with pytest.raises(ConfigError, match="closers or a provider|cannot run with"):
        parse_spec(raw)


def test_an_idle_partition_is_the_composition_without_it():
    _, idle, s1, p1 = bind(fx.without_divisions())
    _, plain, s2, p2 = bind(fx.without_partition())
    q1, q2 = idle.view(p1, s1, xp=np), plain.view(p2, s2, xp=np)
    for name in q2._fields:
        assert np.array_equal(np.asarray(getattr(q1, name)), np.asarray(getattr(q2, name))), name
    b1, b2 = idle.balances(s1, p1), plain.balances(s2, p2)
    for name in b2:
        assert np.array_equal(np.asarray(b1[name]), np.asarray(b2[name])), name


def test_the_step_end_domain_reads_the_view_with_closers():
    """_end_domain's closer branch (§2), through a stub whose view follows its split: at the
    view with closers the bound state's padding is valid (the bridge's gate 0 below its declared
    minimum 1), where the split view alone, without closers, refuses it; a closed contact
    holding a gate is refused at the view."""
    spec = parse_spec(fx.divided(bridge=("linear", 0.004)))
    model = fx.with_follower(spec)
    state, p = model.initial_values(spec)
    assert model.domain_views and model.closers
    assert model._end_domain(state, p, model.operators, xp=np)
    split_only = model.inner.view(p, state, model.domain_views, xp=np)
    inner = model.inner.inner_state(state)
    assert not model.inner.domain_valid(inner, split_only, p.active, xp=np)
    gated = state._replace(junction_gate=np.array([0.5]))
    assert not model._end_domain(gated, p, model.operators, xp=np)


def test_the_lineage_records_the_division():
    spec, model, _, _ = bind(fx.divided())
    entries = list(fx.cs.entries(spec))
    op, declaration, schedule = next(e for e in entries if e[0].LAW_ID == partition.LAW_ID)
    records = partition.lineage(spec, declaration, schedule, np.array([1]))
    founder = next(r for r in records if r["carrier_id"] == "cell_0")
    assert founder["death_s"] == fx.EVENT and founder["successors"] == ["c1", "c2"]
    kids = [r for r in records if r["kind"] == "daughter"]
    assert [(r["carrier_id"], r["slot"], r["parent_carrier"]) for r in kids] == [
        ("c1", "d1", "cell_0"),
        ("c2", "d2", "cell_0"),
    ]
    assert math.isclose(sum(r["volume_fraction"] for r in kids), 1.0)
    assert partition.lineage(spec, declaration, schedule, np.array([0]))[0]["death_s"] is None
