"""Tier-1 smoke test of scheduled_cell_replacement@2 over water (v2 design §2).

The operator's event map on the bound heredity sheet under water, in NumPy (no compile):
* on occupants swollen or shrunk, with changed composition, replaced by a template at its own
  arrival volume and by a donor copy: the volume is written and booked, every ledger's
  residual is unchanged across the event (water's included), and the booked work equals the
  slots' free-energy change written out independently of the adapter and of water's code;
* a donor copy is the donor's state: volume, amounts, water potential and water free energy
  bitwise;
* water's per-node free energy equals the dilution and elastic terms of water_ledgers;
* after the event the view carries the newcomer's volume, and water's first flow is the
  analytic one;
* the combined step bounds (R5), the event's impermeant check, an idle step, and the
  definition refusals.
The compiled guards are test_cell_replacement_v2_runs.py.
"""

import copy
from types import SimpleNamespace

import numpy as np
import pytest

from cells.core import pump_composite_spec as cs
from cells.core.cell_replacement_spec import exact_event_times
from cells.core.specs import ConfigError, parse_spec
from cells.models import surface_pump as first
from cells.models import surface_pump_v3 as ionic
from cells.models.operators import cell_replacement as v1
from cells.models.operators import osmotic_water as water
from cells.models.registry import get_model
from cells.processes.electrochemistry import CHARGE_PER_FMOL, R
from tests import replacement_water_fixtures as fx
from validation.tissue import pump_water_fixtures as wfx

DT = fx.DT
T1 = exact_event_times((10,), DT)[0]
# Largest change of each ledger's residual across one event (rounding of the bookings).
CHANGE_TOLERANCE = dict(
    local=1e-11,
    outside=1e-11,
    total=1e-11,
    charge=1e-24,
    electrode=1e-24,
    global_charge=1e-24,
    energy=1e-9,
    reservoir_work=1e-12,
    electrode_work=1e-12,
    metabolic_work=1e-12,
    water_local=1e-14,
    water_outside=1e-14,
    water_total=1e-14,
    bath_water_work=1e-12,
)


def bound(raw, templates, events, **kw):
    spec = parse_spec(fx.over_water(raw, templates, events, **kw))
    model = get_model(spec.model)
    state, p = model.initial_values(spec)
    return spec, model, state, p


def control_at(spec, model, time):
    return model.CONTROL_TYPE(*(np.asarray(v[0]) for v in cs.control_values(spec, [time])))


@pytest.fixture(scope="module")
def world():
    raw = fx.sheet(end=0.02)
    v0 = raw["model"]["cells"][0]["volume_pL"]
    slot, donor = fx.ring_neighbours(raw)
    ring = [c["id"] for c in raw["model"]["cells"] if c["id"] not in (slot, donor, "cell_3")]
    target = ring[0]
    templates = fx.templates(raw, volumes={"d": 1.04 * v0})
    events = ((T1, target, "d", "n1"), (T1, slot, None, "c1", donor))
    spec, model, state, p = bound(raw, templates, events)
    order = {c.id: i for i, c in enumerate(spec.model.cells)}
    return SimpleNamespace(
        raw=raw,
        spec=spec,
        model=model,
        op=model.operators[1],
        state=state,
        p=p,
        control=control_at(spec, model, T1),
        target=order[target],
        slot=order[slot],
        donor=order[donor],
        arrival=1.04 * v0,
        species=list(spec.model.species_ids),
    )


def prepared(w):
    """Occupants and donor swollen or shrunk, their K and M changed together (no charge)."""
    s, p = w.state, w.p
    dv = np.array(s.volume_increment_pL, copy=True)
    inc = np.array(s.amount_increment, copy=True)
    k, m = w.species.index("K"), w.species.index("M")
    for cell, swell, delta in ((w.target, -0.03, 0.4), (w.slot, 0.02, -0.3), (w.donor, 0.05, 0.25)):
        dv[cell] = swell * p.volume[cell]
        inc[k, cell] += delta
        inc[m, cell] += delta
    return s._replace(volume_increment_pL=dv, amount_increment=inc)


def replaced(w):
    before = prepared(w)
    after, ok = w.op.event(before, w.control, w.p, xp=np)
    assert ok
    return before, after


def test_the_event_writes_and_books_the_volume(world):
    w = world
    before, after = replaced(w)
    v0, dv = w.p.volume, before.volume_increment_pL
    assert after.volume_increment_pL[w.target] == w.arrival - v0[w.target]
    assert after.volume_increment_pL[w.slot] == dv[w.donor]  # The donor's increment, bitwise.
    others = np.ones(v0.size, dtype=bool)
    others[[w.target, w.slot]] = False
    assert np.array_equal(after.volume_increment_pL[others], dv[others])
    removed, supplied = after.replacement_volume_removed_pL, after.replacement_volume_supplied_pL
    assert removed[w.target] == v0[w.target] + dv[w.target]
    assert removed[w.slot] == v0[w.slot] + dv[w.slot]
    assert supplied[w.target] == v0[w.target] + after.volume_increment_pL[w.target]
    assert supplied[w.slot] == v0[w.slot] + dv[w.donor]
    assert not np.any(removed[others]) and not np.any(supplied[others])


def test_every_ledger_is_unchanged_across_the_event(world):
    w = world
    before, after = replaced(w)
    b0, b1 = w.model.balances(before, w.p), w.model.balances(after, w.p)
    assert set(b0) == set(CHANGE_TOLERANCE)
    for name, tolerance in CHANGE_TOLERANCE.items():
        change = np.max(np.abs(np.asarray(b1[name]) - np.asarray(b0[name])), initial=0.0)
        assert change <= tolerance, (name, change)
    # The volume terms are booked: without them water's local ledger moves by the volume change.
    net = after.replacement_volume_supplied_pL - after.replacement_volume_removed_pL
    assert np.max(np.abs(net)) > 1e-3


def free_energy(w, state):
    """Each cell's free energy (pJ), written out from the declarations: the ideal chemical
    term at the actual volume, the elastic energy against V0 and the capacitor energy of its
    one membrane, whose held bath is at 0 V (so V_m = V_m0 + dq / C)."""
    m, p = w.spec.model, w.p
    cells = len(m.cells)
    rt = 1e-3 * R * m.temperature_K
    n = np.array([c.initial_amount_fmol for c in m.cells]).T + state.amount_increment[:, :cells]
    v0 = np.array([c.volume_pL for c in m.cells])
    v = v0 + state.volume_increment_pL[:cells]
    chemical = rt * np.sum(n * (np.log(n / v) - 1.0), axis=0)
    declared = {r.compartment_id: r for r in m.operators[0].compartments}
    rows = [declared[c.id] for c in m.cells]
    k = np.array([r.bulk_modulus_Pa / r.reference_volume_pL for r in rows])
    p0 = k * (v0 - np.array([r.reference_volume_pL for r in rows]))
    p0 += np.array([r.pressure_offset_Pa for r in rows])
    elastic = 1e-3 * (p0 * (v - v0) + 0.5 * k * (v - v0) ** 2)
    z = np.array(m.valence, dtype=float)[:, None]
    ids = [c.id for c in m.cells]
    inside = np.array([ids.index(q.inside) for q in m.membranes])
    assert sorted(inside) == list(range(cells))  # One membrane per cell.
    c = np.array([q.capacitance_F for q in m.membranes])
    dq = CHARGE_PER_FMOL * np.sum(z * state.amount_increment[:, inside], axis=0)
    vm = p.initial_membrane_voltage_V[: len(m.membranes)] + dq / c
    capacitor = np.zeros(cells)
    capacitor[inside] = 0.5e12 * c * vm**2
    return chemical + elastic + capacitor


def test_the_booked_work_is_the_free_energy_change(world):
    w = world
    before, after = replaced(w)
    g0, g1 = free_energy(w, before), free_energy(w, after)
    due = [w.target, w.slot]
    booked = (
        np.sum(after.replacement_free_energy_pJ - before.replacement_free_energy_pJ)
        + np.sum(after.replacement_water_free_energy_pJ - before.replacement_water_free_energy_pJ)
        + np.sum(after.electrode_work_pJ - before.electrode_work_pJ)
    )
    expected = np.sum(g1[due] - g0[due])
    scale = np.sum(np.abs(g0[due]) + np.abs(g1[due]))
    assert abs(booked - expected) <= 1e-12 * scale, (booked, expected)
    # Water's share is not negligible: the volumes moved by percents.
    water_share = np.sum(after.replacement_water_free_energy_pJ)
    assert abs(water_share) > 1e3 * 1e-12 * scale
    assert np.all(after.replacement_water_energy_magnitude_pJ[due] > 0)


def test_a_donor_copy_is_the_donors_state_bit_for_bit(world):
    w = world
    before, after = replaced(w)
    p = w.p
    assert water.volumes(after, p, xp=np)[w.slot] == water.volumes(before, p, xp=np)[w.donor]
    copied = p.amount_reference[:, w.slot] + after.amount_increment[:, w.slot]
    donor = p.amount_reference[:, w.donor] + before.amount_increment[:, w.donor]
    assert np.array_equal(copied, donor)  # Every amount within 2x the slot's reference.
    open_ = p.membrane_active.astype(float)
    psi0 = water.water_rates(before, open_, p, xp=np).edges.water_potential_Pa
    psi1 = water.water_rates(after, open_, p, xp=np).edges.water_potential_Pa
    assert psi1[w.slot] == psi0[w.donor]
    w0 = water.node_free_energy_pJ(before, p, xp=np)
    w1 = water.node_free_energy_pJ(after, p, xp=np)
    assert w1[w.slot] == w0[w.donor]


def test_waters_free_energy_per_node_is_its_ledger_term(world):
    w = world
    rng = np.random.default_rng(20261113)
    n = w.p.active.size
    for _ in range(5):
        state = w.state._replace(
            volume_increment_pL=rng.uniform(-0.4, 0.6, n) * w.p.volume,
            amount_increment=w.state.amount_increment
            + rng.uniform(-0.5, 0.5, w.state.amount_increment.shape),
        )
        energy, _ = water.water_ledgers(state, w.p, xp=np)  # No heat or work booked here.
        nodes = water.node_free_energy_pJ(state, w.p, xp=np)
        assert np.sum(nodes) == pytest.approx(energy, rel=1e-12, abs=1e-12)


def test_after_the_event_the_view_carries_the_newcomers_volume(world):
    w = world
    before, after = replaced(w)
    p = w.p
    view = w.model.view(p, after, xp=np)
    assert view.volume[w.target] == p.volume[w.target] + after.volume_increment_pL[w.target]
    assert view.volume[w.target] != p.volume[w.target]
    assert view.volume[w.slot] == p.volume[w.donor] + before.volume_increment_pL[w.donor]
    # Water's first flow at the newcomers' state, written out: G (psi_cell - psi_bath).
    m = w.spec.model
    rt = R * m.temperature_K
    rows = {c.compartment_id: c for c in m.operators[0].compartments}
    lp = {r.membrane_id: r.hydraulic_permeability_m_per_Pa_s for r in m.operators[0].membranes}
    flows = water.water_rates(after, p.membrane_active.astype(float), p, xp=np).flow
    for cell in (w.target, w.slot):
        name = m.cells[cell].id
        membrane = next(k for k, q in enumerate(m.membranes) if q.inside == name)
        bath = m.extracellular[[c.id for c in m.extracellular].index(m.membranes[membrane].outside)]
        row = rows[name]
        v = view.volume[cell]
        n = np.sum(p.amount_reference[:, cell] + after.amount_increment[:, cell])
        pressure = row.bulk_modulus_Pa * (v / row.reference_volume_pL - 1) + row.pressure_offset_Pa
        psi_cell = pressure - rt * (n + row.impermeant_amount_fmol) / v
        psi_bath = -rt * sum(bath.initial_amount_fmol) / bath.volume_pL
        g = 1e15 * m.membranes[membrane].area_m2 * lp[m.membranes[membrane].id]
        assert flows[membrane] == pytest.approx(g * (psi_cell - psi_bath), rel=1e-12)


def test_an_idle_step_selects_the_state(world):
    w = world
    control = control_at(w.spec, w.model, 0.0)
    after, ok = w.op.event(prepared(w), control, w.p, xp=np)
    assert ok
    for a, b in zip(after, prepared(w), strict=True):
        assert np.asarray(a).tobytes() == np.asarray(b).tobytes()


def test_a_copy_with_another_impermeant_content_refuses_its_step(world):
    w = world
    before = prepared(w)
    inc = np.array(before.amount_increment, copy=True)
    inc[w.species.index("P"), w.donor] += 1.0  # As if a route had moved P into the donor.
    _, ok = w.op.event(before._replace(amount_increment=inc), w.control, w.p, xp=np)
    assert not ok


def test_the_combined_bounds_refuse_what_neither_existing_check_sees():
    raw = fx.sheet(end=0.02)
    leak = leaky_template(raw, "leaky", K=200 * 1.3333333333333340e-10)
    spec, model, _, _ = bound(raw, [leak], ((T1, "cell_0", "leaky", "n1"),))
    op, declaration = model.operators[1], spec.model.operators[1]
    schedule = spec.experiment.operators[1].data
    own = op.bind_check_steps(spec, declaration, schedule, model)
    waters = water.WaterStepChecks(spec, spec.model.operators[0], model)
    inner = ionic.bind_step_checks(v1.worst_case(spec, declaration, schedule))
    existing = max(waters.explicit_rate, inner.explicit_rate)
    assert own.explicit_rate > 1.5 * existing
    step = np.array([0.5 * first.EXPLICIT_STEP_BOUND * (1 / own.explicit_rate + 1 / existing)])
    waters(step)
    inner(step)
    with pytest.raises(ConfigError, match="minimum volumes"):
        own(step)
    # Water's relaxation at a newcomer's own state: a small template is stiffer. One cell, so
    # that no junction's explicit bound binds first at these steps.
    cell = wfx.heredity_cell("H", dt=DT, end_time=0.02)
    cell["experiment"]["observation_times"] = [0.0, 0.02]
    name = cell["model"]["cells"][0]["id"]
    small = fx.rfx.template_from_cell(cell, name, "h")
    small["volume_pL"] = 0.55 * cell["model"]["cells"][0]["volume_pL"]
    spec, model, _, _ = bound(cell, [small], ((T1, name, "h", "n1"),))
    declaration, schedule = spec.model.operators[1], spec.experiment.operators[1].data
    own = model.operators[1].bind_check_steps(spec, declaration, schedule, model)
    waters = water.WaterStepChecks(spec, spec.model.operators[0], model)
    assert own.water_rate > 1.5 * waters.water_rate
    bound_ = water.MAX_WATER_RELAXATION_PER_STEP
    step = np.array([0.5 * bound_ * (1 / own.water_rate + 1 / waters.water_rate)])
    waters(step)
    with pytest.raises(ConfigError, match="newcomer's state"):
        own(step)


def leaky_template(raw, template_id, **leaks):
    """Template "h" with larger leak permeabilities (m/s) on the slot's existing leaks."""
    template = fx.templates(raw)[0]
    template["id"] = template_id
    template["route_values"]["membrane_permeability_m_per_s"] = dict(leaks)
    return template


def refused(raw, match):
    with pytest.raises(ConfigError, match=match):
        parse_spec(raw)


def test_the_definition_refusals():
    raw = fx.sheet(end=0.02)
    v0 = raw["model"]["cells"][0]["volume_pL"]
    slot, donor = fx.ring_neighbours(raw)
    templates = fx.templates(raw)
    events = ((T1, "cell_0", "h", "n1"),)
    good = fx.over_water(raw, templates, events)
    alone = copy.deepcopy(good)
    alone["model"]["operators"] = alone["model"]["operators"][1:]
    del alone["experiment"]["water_controls"]
    refused(alone, "requires ideal_osmosis_linear_compliance_water@1 before it")
    reversed_ = copy.deepcopy(good)
    reversed_["model"]["operators"] = reversed_["model"]["operators"][::-1]
    refused(reversed_, "requires ideal_osmosis_linear_compliance_water@1 before it")
    steady = dict(fx.rfx.FORMATION, initial_abundance=1.0, lag_s=0.0, gate_at_arrival="law_steady")
    refused(fx.over_water(raw, templates, events, formation=steady), "law_steady")
    outside = fx.templates(raw, volumes={"h": 0.4 * v0})
    refused(fx.over_water(raw, outside, events), "outside water's bounds")
    copied = fx.over_water(raw, templates, ((T1, slot, None, "c1", donor),))
    other = copy.deepcopy(copied)
    rows = other["model"]["operators"][0]["compartments"]
    next(r for r in rows if r["compartment_id"] == donor)["bulk_modulus_Pa"] = 61.0
    refused(other, "water compartment differs")
    refused(fx.over_water(raw, templates, events, impermeant=("K",)), "has a route")
    refused(fx.over_water(raw, templates, events, impermeant=("Q",)), "distinct declared")
    heavy = copy.deepcopy(templates)
    heavy[0]["amounts_fmol"]["P"] += 1.0
    refused(fx.over_water(raw, heavy, events), "another P content")
    unequal = copy.deepcopy(raw)
    cell = next(c for c in unequal["model"]["cells"] if c["id"] == donor)
    cell["initial_amount_fmol"]["P"] += 1.0  # With Na, so its charge anchor stays.
    cell["initial_amount_fmol"]["Na"] += 1.0
    copy_event = ((T1, slot, None, "c1", donor),)
    refused(fx.over_water(unequal, templates, copy_event), "another P content")
    parse_spec(copied)  # The admitted copy, for contrast.
