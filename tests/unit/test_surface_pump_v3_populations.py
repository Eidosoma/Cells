"""B1's @3 part (docs/CORE_SEAMS_DESIGN.md §4.2, §4.3, §4.5): the door into @3, gating by host
activity, and @3's field roles.

Each claim at its cheapest level (D187), each with a planted error the check must catch:
- the door: a channel population that declares factors runs, at every stage, at its held
  availability times its sources' factors, a left fold in declared order: its readouts, its
  explicit rates and a whole IMEX step are bitwise those of the same world whose held
  availability is that product (the right fold is a different number); unknown sources, factors
  with no kind to expose them and malformed factors are refused; a definition without factors
  keeps today's form and structure, and one with them round-trips;
- the gate: where the structure declares a closer beside a pump law, a pump on a patch the view
  closes reads bitwise as a padded slot's, on the host and the device, while without the closer
  it keeps cycling (composition §13.1's ungated pump, the planted case); elsewhere the layout is
  returned as it is;
- the roles: every state field has one, and they reproduce the lifecycle's hand-written lists
  (the partition's record, its resets and anchors, the adapter's padded fields), with the
  partition's missing pump history named; a field given the wrong role fails.
"""

import copy
from dataclasses import replace
from decimal import Decimal
from functools import partial

import jax
import jax.numpy as jnp
import numpy as np
import pytest

from cells.definitions import surface_pump_v3_spec as spec_v3
from cells.definitions.specs import ConfigError, parse_spec
from cells.definitions.surface_pump_v3_spec import control_values
from cells.models import pump_composite_adapter as adapter
from cells.models import surface_pump_v3 as v3
from cells.numerics import surface_imex as imex
from cells.operators import partition
from cells.registry import kind_registry
from cells.registry.models import get_model
from tests import kind_fixtures as kf
from validation.fr51 import closed_forms as fr51_laws
from validation.fr51 import engine as fr51
from validation.fr51 import judge as fr51_judge
from validation.fr51 import plants as fr51_plants
from validation.tissue import pump_water_fixtures as water_fixtures
from validation.tissue import surface_pump_v3_fixtures as v3_fixtures

FACTORS = {"f_a": 0.5, "f_b": 0.7, "f_c": 0.65}
HELD = 0.9  # The first population's held availability: (0.9 x 0.7) x 0.65 != 0.9 x (0.7 x 0.65).
ARS = "imex_ars222_face_electromigration@1"


def bound(spec):
    impl = get_model(spec.model)
    state, p = impl.initial_values(spec)
    control = impl.Control(*(v[0] for v in control_values(spec, [0.0])))
    return impl, state, p, control


# ------------------------------------------------------------------ the door


def heredity(factors=None):
    """Heredity cell D (two channel populations) with the planted factor source declared, its
    first population held at HELD; that population declares `factors` where given."""
    raw = kf.declare_routing(water_fixtures.heredity_cell("D", end_time=0.004), factors=FACTORS)
    first = raw["model"]["channels"][0]["id"]
    for entry in raw["experiment"]["channel_controls"]:
        if entry["channel_id"] == first:
            entry["schedule"] = [dict(time=0.0, availability=HELD)]
    if factors is not None:
        raw["model"]["channels"][0]["factors"] = list(factors)
    return raw


def scoped():
    return kind_registry.scope(kf.registry(kf.factor_source()))


def left_fold(held, names):
    value = held
    for name in names:
        value = value * FACTORS[name]
    return value


def test_a_factored_population_runs_at_its_held_availability_times_its_factors():
    names = ("f_b", "f_c")
    with scoped():
        spec = parse_spec(heredity(names))
        impl, state, p, control = bound(spec)
        assert impl.structure.routes == (
            (v3.OWN_SINK, "channel", 0, ((kf.FACTOR_ID, 1), (kf.FACTOR_ID, 2))),
        )
        plain = parse_spec(heredity())  # The same world, its first population unfactored ...
        impl0, state0, p0, control0 = bound(plain)
        assert impl0.structure.routes == ()
        held = control.channel.copy()
        assert held[0] == HELD
        routed = held.copy()
        routed[0] = left_fold(held[0], names)
        control0 = control0._replace(channel=routed)  # ... held at the routed product.
        assert held[0] * (FACTORS["f_b"] * FACTORS["f_c"]) != routed[0]  # Plant: the right fold.
        w, w0 = impl.readouts(state, control, p, xp=np), impl0.readouts(state0, control0, p0, xp=np)
        assert np.array_equal(w.channel_flux_fmol_s, w0.channel_flux_fmol_s)
        assert np.any(w.channel_flux_fmol_s[:, 0] != 0.0)
        potentials = w.field.potential_V
        rates, ok = impl.explicit_rates(state, potentials, control, p, xp=np)
        rates0, ok0 = impl0.explicit_rates(state0, potentials, control0, p0, xp=np)
        assert ok and ok0 and np.array_equal(rates.channel_transferred, rates0.channel_transferred)
        dt = spec.execution.dt
        end, valid = impl.imex_step(state, dt, control, p, xp=np)
        end0, valid0 = impl0.imex_step(state0, dt, control0, p0, xp=np)
        assert valid and valid0
        for name in v3.STATE_TYPE._fields:  # The whole step, bitwise.
            assert np.array_equal(getattr(end, name), getattr(end0, name)), name
        unrouted = control0._replace(channel=held)  # The held value alone differs.
        assert not np.array_equal(
            impl0.readouts(state0, unrouted, p0, xp=np).channel_flux_fmol_s,
            w.channel_flux_fmol_s,
        )
        assert impl.RECORD_NOTES["channel_availability"] == v3.ROUTED_CHANNEL_NOTE
        assert "channel_availability" not in impl0.RECORD_NOTES


@pytest.mark.parametrize(
    "factors,reason",
    [
        (["f_missing"], "unknown factor sources"),
        ([], "non-empty list of distinct factor-source IDs"),
        (["f_a", "f_a"], "non-empty list of distinct factor-source IDs"),
        ([3], "non-empty list of distinct factor-source IDs"),
        ("f_a", "non-empty list of distinct factor-source IDs"),
        (None, "non-empty list of distinct factor-source IDs"),
    ],
)
def test_the_door_refuses_unknown_and_malformed_factors(factors, reason):
    raw = heredity()
    raw["model"]["channels"][0]["factors"] = factors
    with scoped(), pytest.raises(ConfigError, match=reason):
        parse_spec(raw)


def test_factors_without_a_kind_to_expose_them_are_refused():
    raw = water_fixtures.heredity_cell("D", end_time=0.004)
    raw["model"]["channels"][0]["factors"] = ["f_a"]
    with pytest.raises(ConfigError, match="only a declared kind exposes factors"):
        parse_spec(raw)


def test_without_factors_a_definition_keeps_todays_form_and_with_them_round_trips():
    raw = water_fixtures.heredity_cell("D", end_time=0.004)
    spec = parse_spec(raw)
    assert spec_v3.channel_factors(spec.model) == ()
    assert all(type(c) is spec_v3.kinetic.ChannelPopulation for c in spec.model.channels)
    assert get_model(spec.model).structure.routes == ()
    written = spec_v3.to_dict(spec)
    assert all(spec_v3.CHANNEL_FACTORS not in c for c in written["model"]["channels"])
    with scoped():
        raw = heredity(("f_c", "f_a"))
        factored = parse_spec(raw)
        first = raw["model"]["channels"][0]["id"]
        assert spec_v3.channel_factors(factored.model) == ((0, first, ("f_c", "f_a")),)
        assert type(factored.model.channels[0]) is spec_v3.FactoredChannelPopulation
        assert type(factored.model.channels[1]) is spec_v3.kinetic.ChannelPopulation
        again = spec_v3.to_dict(factored)
        assert again["model"]["channels"][0][spec_v3.CHANNEL_FACTORS] == ["f_c", "f_a"]
        assert parse_spec(copy.deepcopy(again)).fingerprint == factored.fingerprint
        assert factored.fingerprint != parse_spec(heredity()).fingerprint


def test_a_population_s_current_at_a_declared_voltage_with_the_halving_control():
    """FR-34 (D251, D252), host only: clamped_channel_flux at the cell's own voltage is readouts'
    channel flux bit for bit; at a declared voltage, half the availability gives half the current
    (the same count and driving force); the current is outward-positive (Kir's K current changes
    sign across E_K, NaV's Na current is inward below E_Na); a factored population reads its
    routed availability, as the door's rows above do; and channel_current_A takes a stack of
    recorded rows."""
    spec = parse_spec(water_fixtures.heredity_cell("D", end_time=0.004))
    impl, state, p, control = bound(spec)
    w = impl.readouts(state, control, p, xp=np)
    own = np.asarray(w.field.rates.membrane_voltage_V)
    flux, current = impl.clamped_channel_flux(state, control, p, own, xp=np)
    assert np.array_equal(flux, w.channel_flux_fmol_s)
    assert np.array_equal(current, v3.channel_current_A(w.channel_flux_fmol_s, p))
    rows = np.stack([w.channel_flux_fmol_s, 2.0 * w.channel_flux_fmol_s])
    assert np.array_equal(v3.channel_current_A(rows, p), np.stack([current, 2.0 * current]))
    kir, nav = ([c.id for c in spec.model.channels].index(i) for i in ("kir_0", "nav_0"))
    half = control._replace(channel=0.5 * control.channel)
    for volts, kir_sign in ((-0.12, -1.0), (-0.03, 1.0), (0.04, 1.0)):
        full_flux, full = impl.clamped_channel_flux(state, control, p, volts, xp=np)
        half_flux, halved = impl.clamped_channel_flux(state, half, p, volts, xp=np)
        assert np.array_equal(halved, 0.5 * full) and np.array_equal(half_flux, 0.5 * full_flux)
        assert np.sign(full[kir]) == kir_sign and full[nav] < 0  # E_K about -90 mV.
    names = ("f_b", "f_c")
    with scoped():
        factored = parse_spec(heredity(names))
        impl1, state1, p1, control1 = bound(factored)
        plain = parse_spec(heredity())
        impl0, state0, p0, control0 = bound(plain)
        routed = control1.channel.copy()
        routed[0] = left_fold(routed[0], names)
        at = impl1.clamped_channel_flux(state1, control1, p1, -0.05, xp=np)
        product = impl0.clamped_channel_flux(
            state0, control0._replace(channel=routed), p0, -0.05, xp=np
        )
        assert all(np.array_equal(a, b) for a, b in zip(at, product, strict=True))
        held = impl0.clamped_channel_flux(state0, control1, p0, -0.05, xp=np)
        assert not np.array_equal(held[1], at[1])  # The held value alone differs.


def test_the_effective_availability_is_recorded_where_the_door_routes_into_channels():
    """FR-34's second item, host only: where a population declares factors, the observed rows
    record channel_effective_availability, the held value times its factors (the left fold the
    flux runs at), declared for the run view with its note; a population without factors records
    its held value there; a world without factors records no such field, so its records and
    types are today's."""
    names = ("f_b", "f_c")
    with scoped():
        for raw, routed in ((heredity(names), True), (heredity(), False)):
            spec = parse_spec(raw)
            impl, state, layout = get_model(spec.model), *get_model(spec.model).initial_values(spec)
            history = type(state)(*(np.asarray(v)[None] for v in state))
            obs = impl.observe_history(np.array([0.0]), history, layout, np.array([0.0]), spec)
            assert (v3.EFFECTIVE_AVAILABILITY in impl.OBSERVATION_FIELDS) is routed
            assert hasattr(obs, v3.EFFECTIVE_AVAILABILITY) is routed
            held = np.asarray(obs.channel_availability)[0]
            assert held[0] == HELD
            if routed:
                effective = np.asarray(getattr(obs, v3.EFFECTIVE_AVAILABILITY))[0]
                assert effective[0] == left_fold(HELD, names) and effective[1] == held[1]
                assert impl.UNITS[v3.EFFECTIVE_AVAILABILITY] == "1"
                assert impl.OBSERVATION_AXES[v3.EFFECTIVE_AVAILABILITY] == ("channel_slot",)
                notes = impl.RECORD_NOTES
                assert notes[v3.EFFECTIVE_AVAILABILITY] == v3.EFFECTIVE_AVAILABILITY_NOTE
                assert type(state) is type(bound(parse_spec(heredity()))[1])  # Same state type.
            else:
                assert v3.EFFECTIVE_AVAILABILITY not in impl.UNITS


def test_the_model_gains_no_field_so_the_families_that_copy_it_still_parse():
    """The water families build their models from @3's model fields by name, so the door adds
    none (the factors ride on the population); a planted model field would break their parse."""
    raw = water_fixtures.with_water(
        water_fixtures.heredity_cell("D", end_time=0.004), pf_m_s=5e-4, bath_pressure_Pa=12.5
    )
    assert parse_spec(raw).model.water is not None
    assert "channel_factors" not in spec_v3.SurfacePumpChannelModel.__dataclass_fields__


# ------------------------------------------------------------------ the gate


@pytest.fixture(scope="module")
def pumped():
    """The @3 fixture with a Na/K and a Ca²⁺ pump on every patch, under ARS(2,2,2), and its
    layout with the first patch closed as a closer's view closes it."""
    spec = parse_spec(v3_fixtures.definition("open", solver=ARS))
    impl, state, p, control = bound(spec)
    active = p.membrane_active.copy()
    active[0] = False
    closed = p._replace(membrane_active=active)
    assert p.pump_present[0] and p.calcium_pump_present[0]
    return impl, state, p, control, closed


def padded_pumps(q):
    """q with the first patch's pumps absent: a padded slot's pumps."""
    nak, ca = q.pump_present.copy(), q.calcium_pump_present.copy()
    nak[0] = ca[0] = False
    return q._replace(pump_present=nak, calcium_pump_present=ca)


PUMP_FIELDS = (
    "pump_cycles",
    "pump_dissipated_energy_pJ",
    "metabolic_work_pJ",
    "calcium_pump_cycles",
    "calcium_pump_dissipated_energy_pJ",
    "calcium_metabolic_work_pJ",
)


def test_a_pump_on_a_closed_host_reads_as_a_padded_slot_where_a_closer_is_declared(pumped):
    impl, state, _, control, closed = pumped
    structure = impl.structure
    closer = replace(structure, padding_fill=True)
    gated = v3.readouts(state, control, closed, xp=np, structure=closer)
    padded = v3.readouts(state, control, padded_pumps(closed), xp=np, structure=closer)
    for name in v3.STATE_TYPE._fields:  # Every rate and readout: a padded slot's, bitwise.
        assert np.array_equal(getattr(gated.derivative, name), getattr(padded.derivative, name))
    assert np.array_equal(gated.pump_affinity_J_mol, padded.pump_affinity_J_mol)
    assert np.array_equal(gated.calcium_pump_affinity_J_mol, padded.calcium_pump_affinity_J_mol)
    for name in PUMP_FIELDS:
        assert getattr(gated.derivative, name)[0] == 0.0
        assert np.any(getattr(gated.derivative, name)[1:] != 0.0)  # Open patches still pump.
    ungated = v3.readouts(state, control, closed, xp=np, structure=structure)
    assert ungated.derivative.pump_cycles[0] != 0.0  # Plant: without the closer it keeps cycling.
    assert ungated.derivative.calcium_pump_cycles[0] != 0.0
    potentials = gated.field.potential_V
    rates, ok = v3.explicit_rates(state, potentials, control, closed, xp=np, structure=closer)
    rates0, ok0 = v3.explicit_rates(
        state, potentials, control, padded_pumps(closed), xp=np, structure=closer
    )
    assert bool(ok) == bool(ok0)
    for name in v3.STATE_TYPE._fields:
        assert np.array_equal(getattr(rates, name), getattr(rates0, name)), name
    device = jax.jit(partial(v3.readouts, structure=closer))(
        *(jax.tree.map(jnp.asarray, x) for x in (state, control, closed))
    )
    assert float(device.derivative.pump_cycles[0]) == 0.0
    assert float(device.derivative.calcium_pump_cycles[0]) == 0.0


def test_the_gate_is_static(pumped):
    impl, _, p, _, closed = pumped
    structure = impl.structure
    assert v3.host_gated_pumps(closed, structure, xp=np) is closed  # No closer.
    assert v3.host_gated_pumps(closed, None, xp=np) is closed  # Today's dispatch.
    pump_free = replace(structure, padding_fill=True, pump_laws=())
    assert v3.host_gated_pumps(closed, pump_free, xp=np) is closed
    gated = v3.host_gated_pumps(closed, replace(structure, padding_fill=True), xp=np)
    assert not gated.pump_present[0] and np.array_equal(gated.pump_present[1:], p.pump_present[1:])


# ------------------------------------------------------------------ the roles


HISTORY_AXES = {"membrane_slot", "edge_slot", "channel_slot"}  # Patches, contacts, populations.


def lifecycle_problems(roles):
    """How a role table departs from the lifecycle's hand-written lists of today."""
    problems = []
    missing = set(v3.STATE_AXES) - set(roles)
    if missing:
        problems.append(f"state fields without a role: {sorted(missing)}")
    known = set(v3.STATE_AXES) | set(v3.LAYOUT_TYPE._fields)
    if set(roles) - known or set(roles.values()) - set(v3.ROLES):
        problems.append("a role names an unknown field or role")
    history = {
        k
        for k, axes in v3.STATE_AXES.items()
        if roles.get(k) == "history" and HISTORY_AXES & {*axes}
    }
    if not set(partition.RECORD) <= history:  # The partition's record: history it retires.
        problems.append("a field the partition's record retires is not history")
    pumps = set(PUMP_FIELDS)
    if history - set(partition.RECORD) != pumps:  # The record's gap (composition §13.1).
        problems.append("the history beyond the partition's record is not the pumps'")
    resets = partition.IsopotentialPartition.STATE_RESETS
    if any(roles.get(k) != "intensive" for k in resets):  # Gates: copied, the closed ones held.
        problems.append("a gate the partition writes is not intensive")
    if any(
        roles.get(k) not in ("extensive", "intensive", "structural") for k in adapter.PADDED_FIELDS
    ):
        problems.append("a field close() pads has no padded role")
    anchors = (
        "volume",
        "amount_reference",
        "initial_cell_charge_C",
        "membrane_area",
        "membrane_capacitance",
        "junction_area",
    )
    if any(roles.get(k) != "extensive" for k in anchors):  # The anchor rule's splits.
        problems.append("an anchor the partition splits is not extensive")
    copied = (
        "membrane_permeability",
        "channel_abundance",
        "channel_permeability",
        "junction_permeability",
        "junction_threshold_voltage",
        "junction_minimum",
    )
    if any(roles.get(k) != "intensive" for k in copied):  # The fields a division keeps "same".
        problems.append("a field the partition copies is not intensive")
    return problems


def test_the_roles_reproduce_the_lifecycles_lists():
    assert lifecycle_problems(v3.FIELD_ROLES) == []
    wrong = dict(v3.FIELD_ROLES, channel_transferred="intensive")  # Plant: history as intensive.
    assert lifecycle_problems(wrong)
    wrong = dict(v3.FIELD_ROLES, membrane_area="intensive")  # Plant: an anchor copied.
    assert lifecycle_problems(wrong)
    wrong = dict(v3.FIELD_ROLES)
    del wrong["junction_gate"]  # Plant: a state field without a role.
    assert lifecycle_problems(wrong)


def test_the_roles_are_on_every_implementation_object():
    spec = parse_spec(water_fixtures.heredity_cell("D", end_time=0.004))
    assert get_model(spec.model).FIELD_ROLES is v3.FIELD_ROLES
    assert adapter.for_structure(v3.structure(spec.model)).FIELD_ROLES is v3.FIELD_ROLES


# ------------------------------------------------------------------ FR-51: two blocking modes
# fr51-channel-block-v1 (validation/fr51/REGISTRATION.md). The host rows compare @3's clamped entry
# point (validation/fr51/engine.host, NumPy) with the laws' 60-digit closed forms
# (validation/fr51/closed_forms), by the registration's bands. The code-blind references are the
# judged run's alone.

FR51_VOLTS = tuple(round(-0.120 + 0.005 * j, 3) for j in range(37))  # -120 to +60 mV.
FR51_HOST_CASES = (
    "P2_K_unequal",
    "P4_Cl_unequal",
    "Z1_zero_blocker",
    "B1_two_modes_E1",
    "B3_divalent_outside_E1",
    "B4_anion_effective",
    "B5_effective_valence_5",
    "S2_strong_two_modes",
    "G1_steep_K_inside_reversal",
    "G3_steep_Na_outside_voltage",
    "G5_steep_Cl_anion_outside",
)


def fr51_points(case_id):
    """Every 5 mV, then E_ion and its two neighbours 0.5 mV away (Decimals, binary64)."""
    e = fr51_laws.reversal(case_id)
    points = [Decimal(str(v)) for v in FR51_VOLTS] + [
        e,
        e - Decimal("0.0005"),
        e + Decimal("0.0005"),
    ]
    return points, np.array([float(v) for v in points])


def fr51_criteria(case_id, values=None):
    """{criterion: passed} on the host rows, read as the judge reads them (its own functions)."""
    points, volts = fr51_points(case_id)
    e, r = values or fr51.host(case_id, volts), fr51_laws.case_values(case_id, points)
    floor = fr51_judge.FLOOR * float(np.max(np.abs(r["I_free"])))
    out = {"P": fr51_judge.within(e["I_free"], r["I_free"], floor=floor)[0]}
    if np.all(np.isnan(e["T_V"])):  # No block.
        return out
    away = np.abs(volts - r["E_ion"]) >= fr51_judge.AWAY
    reversal = (
        fr51.spec_of()["blocks"][
            next(c for c in fr51.spec_of()["cases"] if c["id"] == case_id)["block"]
        ]["reference"]
        != "membrane_voltage"
    )
    return out | {
        "B-u": fr51_judge.within(e["u"], r["u"])[0],
        "B-ratio": fr51_judge.within(e["I_blocked"][away] / e["I_free"][away], r["u"][away])[0],
        "R": fr51_judge.within(e["u"][len(FR51_VOLTS)], r["u"][len(FR51_VOLTS)])[0],
        "S": fr51_judge.within(e["u"], r["u"])[0]
        and fr51_judge.within(e["slope_part"], r["slope_part"])[0],
        "G": fr51_judge.at_least(e["T_V"], r["dI"])[0],
        "E": not reversal
        or fr51_judge.at_least(e["T_co"], r["dco"])[0]
        and fr51_judge.at_least(e["T_ci"], r["dci"])[0],
    }


@pytest.mark.parametrize("case_id", FR51_HOST_CASES)
def test_a_blocked_population_s_current_fraction_and_terms_follow_the_laws(case_id):
    """FR-51 (criteria P, B, R, S, G and E on the host; no compile, about 0.3 s each): the current,
    the unblocked fraction u, the blocked-to-free ratio away from reversal, u read directly at
    E_ion, each mode's theta (1 - theta), and the per-stage terms T_V and T_c bounding the exact
    slopes."""
    found = fr51_criteria(case_id)
    assert all(found.values()), found


@pytest.mark.parametrize("name", list(fr51_plants.JUDGED))
def test_each_registered_plant_fails_its_criterion(name):
    """FR-51's plants (host, about 0.5 s each): each, planted in this process only
    (validation/fr51/plants), fails its registered criterion on one of its cases."""
    plant, criterion, cases = fr51_plants.JUDGED[name]
    with plant():
        found = [fr51_criteria(case_id)[criterion] for case_id in cases]
    assert not all(found)


def test_the_zero_blocker_and_one_count_on_the_host():
    """FR-51's P0, Z and C on the host (about 2 s; C2 is the composite with membrane state):
    - at c_B = 0, u is exactly 1 and the blocked current is the free one bit for bit;
    - C1, abundance doubled: the current is exactly twice B1's, and u bitwise B1's;
    - C2, units: the 1000-unit current is within 4 ulps of B1's, the 2000-unit one within 4 ulps
      of twice the 1000-unit one, and u is bitwise unchanged;
    - Z's plant (an unnormalized sum) and C's (c_B scaled by the count) fail."""
    _, volts = fr51_points("B1_two_modes_E1")
    zero = fr51.host("Z1_zero_blocker", volts)
    assert np.all(zero["u"] == 1.0) and np.array_equal(zero["I_blocked"], zero["I_free"])
    b1, c1 = fr51.host("B1_two_modes_E1", volts), fr51.host("C1_abundance_doubled", volts)
    assert np.array_equal(c1["I_blocked"], 2.0 * b1["I_blocked"]) and np.array_equal(
        c1["u"], b1["u"]
    )
    one, two = fr51.host("C2_units_declared", volts), fr51.host("C2_units_doubled", volts)
    ulps = 4 * np.spacing(np.abs(two["I_blocked"]))
    assert np.all(np.abs(two["I_blocked"] - 2.0 * one["I_blocked"]) <= ulps)
    assert np.all(
        np.abs(one["I_blocked"] - b1["I_blocked"]) <= 4 * np.spacing(np.abs(b1["I_blocked"]))
    )
    assert np.array_equal(one["u"], two["u"])
    with fr51_plants.zero_plant():
        assert not np.all(fr51.host("Z1_zero_blocker", volts)["u"] == 1.0)
    with fr51_plants.count_scaled():
        planted = fr51.host("C1_abundance_doubled", volts)["u"]
        assert not np.array_equal(planted, fr51.host("B1_two_modes_E1", volts)["u"])


def test_the_block_superposes_in_its_reference():
    """FR-51's B-superposition (host, about 1 s): under the reversal reference, B1's u at E1 and at
    E2 agrees at equal V - E within 1e-12 of max u; under the membrane voltage, B3's agrees at equal
    V. Plant (ii), E with the wrong sign of its valence, breaks the first."""
    offsets = np.array([-0.06, -0.03, 0.0, 0.03, 0.06])  # V - E (V).
    e1, e2 = (float(fr51_laws.reversal(c)) for c in ("B1_two_modes_E1", "B1_two_modes_E2"))

    def apart(first, second):
        return np.max(np.abs(first - second)) / max(first.max(), second.max())

    u1 = fr51.host("B1_two_modes_E1", e1 + offsets)["u"]
    u2 = fr51.host("B1_two_modes_E2", e2 + offsets)["u"]
    assert apart(u1, u2) <= 1e-12
    v = np.array([-0.08, -0.04, 0.0, 0.04])
    assert apart(fr51.host("B3_divalent_outside_E1", v)["u"],
                 fr51.host("B3_divalent_outside_E2", v)["u"]) <= 1e-12  # fmt: skip
    with fr51_plants.reversal_valence_flipped():
        planted = (fr51.host("B1_two_modes_E1", e1 + offsets)["u"],
                   fr51.host("B1_two_modes_E2", e2 + offsets)["u"])  # fmt: skip
    assert apart(*planted) > 1e-12


def fr51_block(**changes):
    """B1's block declaration with changes applied in place by the callables given."""
    raw = fr51.raw_world("B1_two_modes_E1")
    block = raw["model"]["channels"][0]["block"]
    for change in changes.values():
        change(block, raw)
    return raw


FR51_REFUSALS = {
    "both steepnesses": (
        lambda b, r: b["modes"][0].update(effective_valence=1.0),
        "exactly one of",
    ),
    "no steepness": (lambda b, r: b["modes"][0].pop("electrical_distance"), "exactly one of"),
    "delta above 1": (
        lambda b, r: b["modes"][0].update(electrical_distance=1.5),
        "electrical distance lies in",
    ),
    "effective valence 0": (
        lambda b, r: (
            b["modes"][0].pop("electrical_distance"),
            b["modes"][0].update(effective_valence=0.0),
        ),
        "effective valence is positive",
    ),
    "steepness above 8": (
        lambda b, r: (
            b["modes"][0].pop("electrical_distance"),
            b["modes"][0].update(effective_valence=9.0),
        ),
        "exceeds 8",
    ),
    "valence 0": (lambda b, r: b["blocker"].update(valence=0), "nonzero integer"),
    "valence not an integer": (lambda b, r: b["blocker"].update(valence=2.0), "nonzero integer"),
    "weight outside [0, 1]": (lambda b, r: b["modes"][0].update(weight=1.5), "weight lies in"),
    "weights not summing to 1": (lambda b, r: b["modes"][0].update(weight=0.5), "sum to 1"),
    "five modes": (lambda b, r: b["modes"].extend([dict(b["modes"][1])] * 3), "at most 4"),
    "K(0) outside its domain": (lambda b, r: b["modes"][0].update(k0_mM=1e-16), "k0_mM lies in"),
    "c_B outside its domain": (
        lambda b, r: b["blocker"].update(concentration_mM=2e3),
        "blocker concentration lies in",
    ),
    "an unknown side": (lambda b, r: b["blocker"].update(side="through"), "outside or inside"),
    "a reversal ion not carried": (
        lambda b, r: b.update(reference={"reversal_of": "Na"}),
        "does not carry",
    ),
    "a blocker named as a row": (lambda b, r: b["blocker"].update(id="Na"), "names a species row"),
    "N2 beside a block": (
        lambda b, r: r["execution"].update(solver=imex.IMPLICIT_CONDUCTANCE_IDS[0]),
        "N2",
    ),
}


@pytest.mark.parametrize("name", list(FR51_REFUSALS))
def test_each_block_refusal_names_its_reason(name):
    """FR-51's V7 (host, parse only): each refusal of the registration's §1.2 fires with its
    reason. The bounding patch's refusal is refusal 4's, a row of the compartments' tests."""
    change, reason = FR51_REFUSALS[name]
    with pytest.raises(ConfigError, match=reason):
        parse_spec(fr51_block(change=change))


def test_a_block_round_trips_alone_and_beside_factors():
    """FR-51's declaration (host): a blocked definition round-trips through to_dict, alone and on a
    population that also declares factors (B1's door). A population without either keeps today's
    form."""
    spec = parse_spec(fr51.raw_world("B1_two_modes_E1"))
    assert parse_spec(spec_v3.to_dict(spec)) == spec
    assert type(spec.model.channels[0]) is spec_v3.FactoredChannelPopulation
    assert spec_v3.channel_factors(spec.model) == ()
    with scoped():
        raw = heredity(("f_b", "f_c"))
        raw["model"]["channels"][0]["block"] = fr51.raw_world("B1_two_modes_E1")["model"][
            "channels"
        ][0]["block"] | {"reference": "membrane_voltage"}
        both = parse_spec(raw)
        assert parse_spec(spec_v3.to_dict(both)) == both
        assert both.model.channels[0].factors == ("f_b", "f_c")
        assert both.model.channels[0].block is not None
        assert type(both.model.channels[1]) is not spec_v3.FactoredChannelPopulation
