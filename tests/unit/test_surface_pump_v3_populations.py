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
import dataclasses
import math
from dataclasses import replace
from types import MappingProxyType
from decimal import Decimal
from functools import partial

import jax
import jax.numpy as jnp
import numpy as np
import pytest

from cells.definitions import pump_composite_spec as composite_spec
from cells.definitions import surface_pump_v3_spec as spec_v3
from cells.definitions.specs import ConfigError, parse_spec
from cells.definitions.surface_pump_v3_spec import control_values
from cells.laws import electrochemistry
from cells.laws.channels import cav1p2_m2h, kleak_always_open, kv1p5_mh
from cells.laws.channels import open_channel_block as block_law
from cells.laws.channels import voltage_shift as vshift
from cells.laws.junctions.selective import selective_flux
from cells.models import pump_composite
from cells.models import pump_composite_adapter as adapter
from cells.models import surface_pump_v3 as v3
from cells.numerics import fixed_step
from cells.numerics import surface_imex as imex
from cells.operators import partition
from cells.registry import kind_registry
from cells.registry import laws as law_registry
from cells.registry.models import get_model
from tests import kind_fixtures as kf
from tests import membrane_insertion_fixtures as insertion_fixtures
from tests import partition_fixtures
from tests.unit.test_proton_buffer_kind import buffered_world
from validation.fr50 import closed_forms as fr50_closed
from validation.fr50 import engine as fr50_engine
from validation.fr50 import judge as fr50_judge
from validation.fr50 import plants as fr50_plants
from validation.fr51 import closed_forms as fr51_laws
from validation.fr51 import engine as fr51
from validation.fr51 import judge as fr51_judge
from validation.fr51 import plants as fr51_plants
from validation.fr64 import closed_forms as fr64_laws
from validation.fr64 import worlds as fr64_worlds
from validation.tissue import cell_replacement_fixtures as replacement_fixtures
from validation.tissue import pump_water_fixtures as water_fixtures
from validation.tissue import surface_pump_v3_fixtures as v3_fixtures

FACTORS = {"f_a": 0.5, "f_b": 0.7, "f_c": 0.65}
HELD = 0.9  # The first population's held availability: (0.9 x 0.7) x 0.65 != 0.9 x (0.7 x 0.65).
ARS = "cells.solver.imex_ars222_face_electromigration@1"


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
    """The water families build their models from @3's model fields by name, so a model field
    they do not carry would break their parse. The door adds none (the factors ride on the
    population). FR-50 phase 2 adds one, one_way_records, which @3's model gains only where it is
    declared: empty by default, written by to_dict only where declared, and carried empty by the
    water model (which refuses a declared one), so the water world parses and writes as before."""
    from cells.definitions import surface_pump_water_spec as water_spec

    raw = water_fixtures.with_water(
        water_fixtures.heredity_cell("D", end_time=0.004), pf_m_s=5e-4, bath_pressure_Pa=12.5
    )
    spec = parse_spec(raw)
    assert spec.model.water is not None
    assert "channel_factors" not in spec_v3.SurfacePumpChannelModel.__dataclass_fields__
    assert spec_v3.SurfacePumpChannelModel.__dataclass_fields__["one_way_records"].default == ()
    assert spec.model.one_way_records == ()
    assert spec_v3.ONE_WAY_RECORDS_KEY not in water_spec.to_dict(spec)["model"]


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


def test_a_frozen_input_reads_through_the_id_table():
    """D345's translator on the tagged cases.json: its populations' laws are the engine's own. With
    an empty table it is the file's data itself; through a table and its inverse it comes back. The
    table it reads, as data, is the engine's."""
    import json

    from cells.registry import laws as law_registry
    from cells.registry.renamed_ids import RENAMED
    from validation import id_table

    assert id_table.renamed() == RENAMED
    for population in fr51.spec_of()["populations"].values():
        law_registry.active().lookup(population["law"])
    cases = json.loads(fr51_judge.SPEC.read_text())
    laws = {p["law"] for p in cases["populations"].values()}
    assert id_table.translate(cases, {}) is cases
    table = {law: f"tests.planted.{law}" for law in laws}
    there = id_table.translate(cases, table)
    assert {p["law"] for p in there["populations"].values()} == set(table.values())
    assert id_table.translate(there, {new: old for old, new in table.items()}) == cases


def capped_valence():
    """D352's plant, engine-only like zero_plant (JUDGED keeps its eleven): each effective valence
    capped at the blocker's |z_B|, its sign kept."""
    original = spec_v3.ChannelBlock.steepness

    def planted(self):
        return tuple(
            s
            if m.effective_valence is None
            else (1.0 if s > 0 else -1.0) * min(abs(s), abs(self.valence))
            for s, m in zip(original(self), self.modes, strict=True)
        )

    return fr51_plants._patched(spec_v3.ChannelBlock, "steepness", planted)


FR51_PLANTS = fr51_plants.JUDGED | {
    # D352: an admitted effective valence above |z_B| (B5: z_B = +4 inside, z_eff = 5).
    "D352: the effective valence capped at the blocker's valence": (
        capped_valence,
        "B-u",
        ("B5_effective_valence_5",),
    ),
}


@pytest.mark.parametrize("name", list(FR51_PLANTS))
def test_each_registered_plant_fails_its_criterion(name):
    """FR-51's plants (host, about 0.5 s each): each, planted in this process only
    (validation/fr51/plants), fails its registered criterion on one of its cases. D352's row: the
    cap fails B5's u against the closed forms, which B5's host row meets unplanted."""
    plant, criterion, cases = FR51_PLANTS[name]
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


FR51_SLOT_WRITERS = {
    "cells.operator.isopotential_partition@1": lambda: partition_fixtures.divided(),
    "cells.operator.scheduled_membrane_insertion@1": lambda: insertion_fixtures.with_operators(
        insertion_fixtures.cleft_cell(), insertion=insertion_fixtures.furrow_insertion()
    ),
    "cells.operator.scheduled_cell_replacement@1": lambda: composite_spec.frozen_definition(
        replacement_fixtures.with_replacement(replacement_fixtures.heredity_sheet(radius=1))
    ),
}


@pytest.mark.parametrize("law", list(FR51_SLOT_WRITERS))
def test_a_block_beside_an_operator_that_rewrites_channel_slots_is_refused(law, monkeypatch):
    """FR-51's follow-up (parse only, about 1 s each; one row per operator family): replacement,
    partition and insertion rewrite channel slots but not the block's per-slot fields, so a blocked
    population beside one is refused by name (pump_composite.SLOT_WRITERS, @1 and @2 alike). Every
    row is the composite form, where that refusal is the only wall (D364; the standalone replacement
    model meets @3's BLOCK_STRUCTURE_REFUSAL too): with it planted away, the world is admitted, its
    block kept."""
    raw = FR51_SLOT_WRITERS[law]()
    raw["model"]["channels"][0]["block"] = fr51_block()["model"]["channels"][0]["block"]
    with pytest.raises(ConfigError, match=f"{law} rewrites channel slots"):
        parse_spec(raw)
    monkeypatch.setattr(pump_composite, "block_slot_errors", lambda pairs, spec: [])  # The plant.
    assert parse_spec(raw).model.channels[0].block is not None


def test_a_block_round_trips_alone_and_beside_factors():
    """FR-51's declaration (host): a blocked definition round-trips through to_dict, alone and on a
    population that also declares factors (B1's door). A population without either keeps today's
    form. D352: B5's effective valence of 5, above its blocker's |z_B| = 4, is admitted, with the
    signed steepness s sgn(z_B) z_eff, and round-trips."""
    spec = parse_spec(fr51.raw_world("B1_two_modes_E1"))
    assert parse_spec(spec_v3.to_dict(spec)) == spec
    assert type(spec.model.channels[0]) is spec_v3.FactoredChannelPopulation
    assert spec_v3.channel_factors(spec.model) == ()
    b5 = parse_spec(fr51.raw_world("B5_effective_valence_5"))
    assert b5.model.channels[0].block.steepness() == (-5.0,)  # Inside (s = -1), z_B = +4.
    assert parse_spec(spec_v3.to_dict(b5)) == b5
    with scoped():
        raw = heredity(("f_b", "f_c"))
        raw["model"]["channels"][0]["block"] = fr51.raw_world("B1_two_modes_E1")["model"][
            "channels"
        ][0]["block"]
        both = parse_spec(raw)
        assert parse_spec(spec_v3.to_dict(both)) == both
        assert both.model.channels[0].factors == ("f_b", "f_c")
        assert both.model.channels[0].block is not None
        assert type(both.model.channels[1]) is not spec_v3.FactoredChannelPopulation


# ------------------------------------------------------------------ FR-64: a declared voltage shift
# docs/FR64_VOLTAGE_SHIFT_DESIGN.md §5 and §9 (§17 at main 7149f90a). The declaration's refusals by
# name, on B4's buffered heredity cell D (test_proton_buffer_kind.buffered_world: its Kir2.1
# population kir_0, H and B rows, B4 at the cell) with FR-51's B1 block on kir_0; and the closed
# set's kernels against their 50-digit closed forms (validation/fr64/closed_forms.py).

FR64_PH = {
    "side": "outside", "shift_V_per_ph": -0.0234, "reference_ph": 7.3, "ph_window": [6.8, 7.5]
}  # fmt: skip


def ph_shift(**changes):
    return {"ph": FR64_PH | changes}


def fr64_world(shift=None, *, block=True, change=None):
    """buffered_world with FR-51's B1 block on kir_0 (read through validation/fr51/engine), and
    `shift` as kir_0's voltage_shift where given; change(raw) edits it further."""
    raw = buffered_world()
    kir = raw["model"]["channels"][0]
    if block:
        kir["block"] = fr51.raw_world("B1_two_modes_E1")["model"]["channels"][0]["block"]
    if shift is not None:
        kir["voltage_shift"] = shift
    if change is not None:
        change(raw)
    return raw


def gate_free(raw):
    """kir_0 as an always-open K leak (no gates)."""
    kir = raw["model"]["channels"][0]
    kir.update(kinetic_law=kleak_always_open.LAW_ID, initial_gate=[])


def old_reference(raw):
    raw["model"]["channels"][0]["block"]["reference"] = {"reversal_of": "K"}


FR64_REFUSALS = {  # name: (kir_0's voltage_shift, a block on kir_0, a further change, the reason)
    "not a mapping": ("membrane_voltage", True, None, "omit it for none"),
    "empty": ({}, True, None, "omit it for none"),
    "an unknown key": ({"gate": {"m": ph_shift()}}, True, None, "omit it for none"),
    "empty gates": ({"gates": {}}, True, None, "non-empty"),
    "a gate not the law's": ({"gates": {"n": ph_shift()}}, True, None, "no such reader"),
    "gates on a gate-free law": ({"gates": {"m": ph_shift()}}, True, gate_free, "has no gates"),
    "the block without a block": (
        {"block": {"reversal_of": "K"}}, False, None, "declares no block",
    ),
    "an unknown kind": ({"block": {"surface_charge": 0.01}}, True, None, "no shift kind"),
    "two kinds on one reader": (
        {"block": {"reversal_of": "K", "ph": FR64_PH}}, True, None, "a shift is one",
    ),
    "the membrane voltage spelled": ({"block": "membrane_voltage"}, True, None, "omit the reader"),
    "a reversal of an ion not carried": (
        {"block": {"reversal_of": "Na"}}, True, None, "does not carry",
    ),
    "a proton row the model lacks": (
        {"gates": {"m": ph_shift(proton="Hx")}}, True, None, "declares no 'Hx'",
    ),
    "a proton row not of valence +1": (
        {"gates": {"m": ph_shift(proton="B")}}, True, None, "of valence \\+1",
    ),
    "not the closure's proton row": (
        {"gates": {"m": ph_shift(proton="Na")}}, True, None, "not the closure's proton row",
    ),
    "an unknown side": (
        {"gates": {"m": ph_shift(side="both")}}, True, None, "neither is a default",
    ),
    "a slope that is not finite": (
        {"gates": {"m": ph_shift(shift_V_per_ph=math.nan)}}, True, None, "finite number",
    ),
    "a window low above high": (
        {"gates": {"m": ph_shift(ph_window=[7.5, 6.8])}}, True, None, "lies below its high",
    ),
    "a reference outside the window": (
        {"gates": {"m": ph_shift(reference_ph=7.6)}}, True, None, "inside its window",
    ),
    "a missing field": (
        {"gates": {"m": {"ph": {k: v for k, v in FR64_PH.items() if k != "side"}}}},
        True, None, "missing=\\['side'\\]",
    ),
    "the block's pH shift above 0.369 V": (
        {"block": ph_shift(shift_V_per_ph=-0.8)}, True, None, "above 0.369 V",
    ),
    "the block's old reference key": (
        None, True, old_reference, "moved to the population's voltage_shift.block",
    ),
}  # fmt: skip


@pytest.mark.parametrize("name", list(FR64_REFUSALS))
def test_each_shift_refusal_names_its_reason(name):
    """FR-64's §5 (host, parse only, milliseconds each): each refusal of the declaration fires
    with its reason. The accepted control, the block's shift on the K reversal (FR-51's, moved) in
    the same world, is the round trip's row. The refusals beside a slot writer, of a path without
    the structure and of the stationary analysis are their sites' rows."""
    shift, block, change, reason = FR64_REFUSALS[name]
    with pytest.raises(ConfigError, match=reason):
        parse_spec(fr64_world(shift, block=block, change=change))


def with_neutral(raw):
    """raw with a neutral species N0 at 1 mM in every node, moved by no route."""
    m = raw["model"]
    m["species"].append(dict(id="N0", valence=0, standard_mu_RT=0.0))
    for node in (*m["cells"], *m["extracellular"]):
        node["initial_amount_fmol"]["N0"] = 1.0 * node["volume_pL"]
    for patch in m["membranes"]:
        patch["permeability_m_per_s"]["N0"] = 0.0
    raw["execution"]["material_balance_atol_fmol"]["N0"] = 1e-10


@pytest.mark.parametrize(
    "case", ["an idle ion, on a gate", "an idle ion, on the block", "a neutral species"]
)
def test_a_reversal_of_an_ion_not_moved_or_neutral_is_refused(case):
    """FR-64's question 4 (ruled), and E's own domain. A law registered at run time can carry an
    ion at relative permeability 0, which its population does not move, so a closure could hold
    it: a reversal of it is refused by name, on a gate or on the block. A neutral species has no
    reversal potential (E divides by z): refused by name. No registered law has either."""
    neutral = case == "a neutral species"
    idle, neutral = (None, ("N0", 0, 1.0)) if neutral else (("Na", 1, 0.0), None)
    base = kv1p5_mh.LAW if case != "an idle ion, on the block" else kleak_always_open.LAW
    law = dataclasses.replace(
        base, law_id="tests.channel.k_beside_another@1", code=99,
        permeant=(("K", 1, 1.0), idle or neutral),
        material_term=cav1p2_m2h.LAW.material_term if neutral else base.material_term,
    )  # fmt: skip
    other = (idle or neutral)[0]

    def beside(raw):
        if neutral:
            with_neutral(raw)
        kir = raw["model"]["channels"][0]
        kir.update(
            kinetic_law=law.law_id,
            initial_gate=[0.5, 0.5] if law.gates else [],
            permeant_ions=[dict(species_id=s, relative_permeability=r) for s, _, r in law.permeant],
        )

    named = {"reversal_of": other}
    shift = {"gates": {"m": named}} if law.gates else {"block": named}
    reason = "has no reversal potential" if neutral else "carries at relative permeability 0"
    with law_registry.scope(law_registry.BUILTIN.extended(law)):
        with pytest.raises(ConfigError, match=reason):
            parse_spec(fr64_world(shift, change=beside))


def test_a_shifted_definition_round_trips_and_without_a_shift_nothing_moves():
    """FR-64's declaration (host): the block's shift on a reversal round-trips through to_dict,
    alone (FR-51's B1, its frozen reference translated) and beside factors on heredity cell D's
    Kir2.1. A population with neither key keeps today's type and form. The gates' and the pH's
    round trips are the sites' rows."""
    spec = parse_spec(fr51.raw_world("B1_two_modes_E1"))
    assert spec.model.channels[0].voltage_shift == spec_v3.VoltageShift(
        block=vshift.ReversalShift("K")
    )
    assert spec_v3.to_dict(spec)["model"]["channels"][0]["voltage_shift"] == {
        "block": {"reversal_of": "K"}
    }
    assert "reference" not in spec_v3.to_dict(spec)["model"]["channels"][0]["block"]
    assert parse_spec(spec_v3.to_dict(spec)) == spec
    assert spec_v3.shifted_readers(spec.model) == (("population", "block", "reversal_of"),)
    with scoped():
        raw = heredity(("f_b", "f_c"))
        kir = raw["model"]["channels"][0]
        kir["block"] = fr51.raw_world("B1_two_modes_E1")["model"]["channels"][0]["block"]
        kir["voltage_shift"] = {"block": {"reversal_of": "K"}}
        both = parse_spec(raw)
        assert parse_spec(spec_v3.to_dict(both)) == both
        assert both.model.channels[0].factors == ("f_b", "f_c")
        plain = both.model.channels[1]
        assert type(plain) is not spec_v3.FactoredChannelPopulation
        assert "voltage_shift" not in spec_v3.to_dict(both)["model"]["channels"][1]
    unshifted = parse_spec(fr51.raw_world("B1_two_modes_E1", blocked=False))
    assert spec_v3.shifted_readers(unshifted.model) == ()
    accepted = parse_spec(fr64_world({"block": {"reversal_of": "K"}}))  # The refusals' control.
    assert accepted.model.channels[0].voltage_shift.block == vshift.ReversalShift("K")


def test_every_kind_s_dictionary_form_round_trips_on_every_reader():
    """FR-64's dictionary form at the spec level (host, no run): both gates and the block, each
    kind, the pH on either side and with a proton row other than the default, parse from their
    declaration (parse_voltage_shift on kir_0 as parsed), write it back (VoltageShift.to_dict) and
    parse again to the same shifts, in the law's gate order. The worlds that run them are the
    sites' rows; the closure's proton row is check_shift_protons', a refusal row."""
    spec = parse_spec(fr64_world(None))
    m = spec.model
    kir = m.channels[0]

    def parsed(raw):
        return spec_v3.parse_voltage_shift(raw, kir, m.species_ids, m.valence, kir.block)

    for raw in (
        {"gates": {"h": {"reversal_of": "K"}, "m": ph_shift()}},
        {
            "gates": {"m": ph_shift(side="inside", proton="Na")},
            "block": ph_shift(shift_V_per_ph=0.05),
        },
        {"block": {"reversal_of": "K"}},
    ):
        shift = parsed(raw)
        declared = raw.get("gates", {})
        assert [gate for gate, _ in shift.gates] == [g for g in ("m", "h") if g in declared]
        assert shift.to_dict() == {key: value for key, value in raw.items()}
        assert parsed(shift.to_dict()) == shift
    written = parsed({"gates": {"m": ph_shift(proton="Na")}}).to_dict()
    assert written["gates"]["m"]["ph"]["proton"] == "Na"
    assert "proton" not in parsed({"gates": {"m": ph_shift()}}).to_dict()["gates"]["m"]["ph"]


FR64_REVERSALS = (  # (c_i, c_o) in mM and z, across FR-51's admitted 1e-3 to 1e3 mM.
    ("140", "5.4", 1), ("10", "145", 1), ("5", "5", 1), ("1e-4", "2", 2), ("20", "120", -1),
    ("1e-3", "1e3", 1), ("1e3", "1e-3", -1),
)  # fmt: skip
FR64_PHS = ("4", "6.4", "6.8", "7.2", "7.3", "7.4", "8.5", "10")
FR64_SLOPES = ("-0.0234", "-0.0078", "0", "0.05", "-0.1")
TEMPERATURE_K = 310.0


def fr64_kernel_misfit():
    """The largest misfit of the closed set's kernels from their 50-digit closed forms:
    ReversalShift's E and its slope at each end, and PhShift's pH, dV and slope over the pH and
    slope grids. Each is
    |kernel - closed form| / (1e-13 |closed form| + floor), with floor 1e-18 V for E and its
    slopes, 1e-15 for the pH and 1e-14 |sigma| V for dV (a few ulps of the pH), so a value at most
    1 fits."""
    worst = 0.0

    def misfit(found, expected, floor):
        nonlocal worst
        found, expected = Decimal(float(found)), Decimal(expected)
        bound = Decimal("1e-13") * abs(expected) + floor
        worst = max(worst, float(abs(found - expected) / bound))

    for c_in, c_out, z in FR64_REVERSALS:
        ci, co = float(c_in), float(c_out)
        e = vshift.ReversalShift.delta_v(np.float64(ci), np.float64(co), z, TEMPERATURE_K)
        misfit(e, fr64_laws.reversal(c_in, c_out, z, TEMPERATURE_K), Decimal("1e-18"))
        for c in (ci, co):
            slope = vshift.ReversalShift.slope(np.float64(c), z, TEMPERATURE_K)
            misfit(slope, fr64_laws.reversal_slope(c, z, TEMPERATURE_K), Decimal("1e-18"))
    for ph in FR64_PHS:
        h = 1000.0 * 10.0 ** -float(ph)
        misfit(vshift.PhShift.ph(np.float64(h)), fr64_laws.ph(h), Decimal("1e-15"))
        for sigma in FR64_SLOPES:
            dv = vshift.PhShift.delta_v(np.float64(h), float(sigma), 7.3)
            floor = Decimal("1e-14") * abs(Decimal(sigma)) + Decimal("1e-30")
            misfit(dv, fr64_laws.ph_shift(h, float(sigma), 7.3), floor)
            slope = vshift.PhShift.slope(np.float64(h), float(sigma))
            misfit(slope, fr64_laws.ph_slope(h, float(sigma)), Decimal("1e-30"))
    return worst


def reversal_plant(change):
    """A plant on electrochemistry.reversal_potential, which ReversalShift reads through its
    module."""
    original = electrochemistry.reversal_potential

    def planted(inside, outside, valence, temperature, *, xp=np):
        return change(original, inside, outside, valence, temperature, xp)

    return planted


FR64_KERNEL_PLANTS = {  # name: (owner, attribute, planted value)
    "E's valence sign flipped": (
        electrochemistry, "reversal_potential",
        reversal_plant(lambda f, i, o, z, t, xp: f(i, o, -z, t, xp=xp)),
    ),
    "c_i and c_o exchanged": (
        electrochemistry, "reversal_potential",
        reversal_plant(lambda f, i, o, z, t, xp: f(o, i, z, t, xp=xp)),
    ),
    "h without the 1 M reference": (vshift, "PH_REFERENCE_mM", 1.0),
    "the pH shift's sign flipped": (
        vshift.PhShift, "delta_v",
        staticmethod(
            lambda h, sigma, reference, *, xp=np: -sigma * (vshift.PhShift.ph(h, xp=xp) - reference)
        ),
    ),
}  # fmt: skip


@pytest.mark.parametrize("plant", [None, *FR64_KERNEL_PLANTS])
def test_the_shift_kernels_meet_their_closed_forms_and_each_plant_misses_them(plant, monkeypatch):
    """FR-64's kernels (host, about 0.1 s): the reversal's E and its slope, and the pH, dV and its
    slope, each within 1e-13 relative of the 50-digit closed forms; each plant misses them."""
    if plant is not None:
        monkeypatch.setattr(*FR64_KERNEL_PLANTS[plant])
    misfit = fr64_kernel_misfit()
    assert (misfit <= 1.0) if plant is None else (misfit > 1e3), misfit


def test_the_ph_window_is_closed_with_its_rounding_margin_and_the_block_bound_admits_its_limit():
    """The window (the note's §3.5, option (c)): a pH on either edge, or within PH_MARGIN beyond it,
    is admitted; 2 PH_MARGIN beyond is refused, and so are h <= 0 and a non-finite h. The block's
    0.369 V bound (§4.3) admits its limit and refuses just above it."""
    low, high = 6.8, 7.5
    for ph, admitted in (
        (low, True), (high, True), (7.1, True), (low - 0.5e-9, True), (high + 0.5e-9, True),
        (low - 2e-9, False), (high + 2e-9, False),
    ):  # fmt: skip
        h = np.float64(1000.0 * 10.0 ** -ph)
        assert bool(vshift.PhShift.valid(h, low, high)) is admitted, ph
    for h in (0.0, -1.0, math.inf, math.nan):
        assert not bool(vshift.PhShift.valid(np.float64(h), low, high))
    reach = max(7.3 - (low - vshift.PH_MARGIN), (high + vshift.PH_MARGIN) - 7.3)
    sigma = vshift.BLOCK_SHIFT_LIMIT_V / reach
    while vshift.PhShift("outside", sigma, 7.3, (low, high)).largest_shift_V() > 0.369:
        sigma = math.nextafter(sigma, 0.0)
    at_limit = fr64_world({"block": ph_shift(shift_V_per_ph=sigma, ph_window=[low, high])})
    assert parse_spec(at_limit).model.channels[0].voltage_shift.block.shift_V_per_ph == sigma
    steeper = ph_shift(shift_V_per_ph=sigma * (1 + 1e-6), ph_window=[low, high])
    above = fr64_world({"block": steeper})
    with pytest.raises(ConfigError, match="above 0.369 V"):
        parse_spec(above)


FR64_KIND_ROWS = {  # each kind of the closed set: its refusal rows and its kernel plants
    "reversal_of": (
        ("a reversal of an ion not carried", "the block without a block"),
        ("E's valence sign flipped", "c_i and c_o exchanged"),
    ),
    "ph": (
        ("a proton row not of valence +1", "not the closure's proton row", "an unknown side",
         "the block's pH shift above 0.369 V"),
        ("h without the 1 M reference", "the pH shift's sign flipped"),
    ),
}  # fmt: skip


def closed_set_gaps(kinds):
    """What a kind of the table lacks: a dV kernel, a slope kernel, its refusal rows, its plants."""
    out = []
    for key, kind in kinds.items():
        if not all(callable(getattr(kind, name, None)) for name in ("delta_v", "slope", "parse")):
            out.append(f"{key}: a kernel or its parse")
        refusals, plants = FR64_KIND_ROWS.get(key, ((), ()))
        if not refusals or any(name not in FR64_REFUSALS for name in refusals):
            out.append(f"{key}: its refusal rows")
        if not plants or any(name not in FR64_KERNEL_PLANTS for name in plants):
            out.append(f"{key}: its plants")
    return out


def test_the_closed_set_has_its_kernels_refusals_and_plants():
    """The closed set's guard row (milliseconds): the parse, the model and this row read one table
    (vshift.KINDS), and each kind has its two kernels, its refusal rows and its plants. Planted: a
    third kind added to the table alone."""
    assert closed_set_gaps(vshift.KINDS) == []
    assert tuple(vshift.KINDS) == ("reversal_of", "ph")

    class SurfaceCharge:
        KEY = "surface_charge"

    planted = MappingProxyType(dict(vshift.KINDS) | {SurfaceCharge.KEY: SurfaceCharge})
    assert closed_set_gaps(planted) == [
        "surface_charge: a kernel or its parse",
        "surface_charge: its refusal rows",
        "surface_charge: its plants",
    ]


# ------------------------------------------------------------------ FR-64: the sites
# The note's §9.1 and §9.2 on the host. Each site reads its reader's voltage (reader_voltages) at
# the stage's read, and nothing else moves: permeation, its heat and its charge read V.

SIGMA, PH_REF = -0.0234, 7.3


def kir_shifted(shift, *, declare=True, block=False, nav=None):
    """buffered_world (B4 at its cell where declare; the bath held at pH 7.4, the cell at 7.2)
    with `shift` as kir_0's voltage_shift and `nav` as nav_0's where given, and FR-51's B1 block
    on kir_0 where asked. At the start V is -21.5 mV, E_K -96.8 mV and E_Na about +70 mV, so a
    gate of nav_0 on E_Na reads about -92 mV, while one of kir_0 on E_K would read +75 mV, off
    its law's domain, and is refused there."""
    raw = fr64_world(shift, block=block) if declare else buffered_world(declare=False)
    if not declare:
        kir = raw["model"]["channels"][0]
        if block:
            kir["block"] = fr51.raw_world("B1_two_modes_E1")["model"]["channels"][0]["block"]
        if shift is not None:
            kir["voltage_shift"] = shift
    if nav is not None:
        raw["model"]["channels"][1]["voltage_shift"] = nav
    return raw


def stepped(raw):
    """(implementation, layout, control, the start's readouts, the state after one host step)."""
    spec = parse_spec(raw)
    impl, state, p, control = bound(spec)
    after, valid = impl.imex_step(state, raw["execution"]["dt"], control, p, xp=np)
    assert bool(valid)
    return impl, p, control, impl.readouts(state, control, p, xp=np), after


def bath_shift_V(p, species_ids):
    """dV of a pH shift read at the held bath (kir_0's patch's outside node), as the engine forms
    it from the layout: sigma (pH(h) - pH_ref), h the bath's H over its volume."""
    h = p.extracellular_amount_reference[species_ids.index("H"), 0] / p.extracellular_volume[0]
    return vshift.PhShift.delta_v(np.float64(h), SIGMA, PH_REF)


def twin_law(delta_v):
    """Kir2.1's law, code 99, its m row read at V - delta_v: the shifted population's twin."""
    from cells.laws.channels import kir2p1_mh2

    base = kir2p1_mh2.LAW

    def kinetics(voltage, *, xp):
        moved, plain = base.kinetics(voltage - delta_v, xp=xp), base.kinetics(voltage, xp=xp)
        target = xp.concatenate((moved[0][..., :1, :], plain[0][..., 1:, :]), axis=-2)
        tau = xp.concatenate((moved[1][..., :1, :], plain[1][..., 1:, :]), axis=-2)
        return target, tau

    return dataclasses.replace(base, law_id="tests.channel.kir_m_twin@1", code=99,
                               kinetics=kinetics)  # fmt: skip


def same_bits(a, b):
    """Bit for bit, field by field, into nested tuples; a field on one side only is skipped."""
    if hasattr(a, "_fields"):
        return all(same_bits(getattr(a, f), getattr(b, f)) for f in a._fields if f in b._fields)
    if isinstance(a, (tuple, list)):
        return len(a) == len(b) and all(same_bits(x, y) for x, y in zip(a, b, strict=True))
    if isinstance(a, dict):
        return a.keys() == b.keys() and all(same_bits(a[k], b[k]) for k in a)
    x, y = np.asarray(a), np.asarray(b)
    return x.shape == y.shape and x.tobytes() == y.tobytes()


def kir_versus_twin():
    """(the shifted world's readouts and stepped state, its twin's): kir_0's m on the bath's pH
    against the twin law at V - dV, both on B4's world under ARS(2,2,2)."""
    shift = {"gates": {"m": ph_shift(side="outside", reference_ph=PH_REF, shift_V_per_ph=SIGMA,
                                    ph_window=[6.8, 7.5])}}  # fmt: skip
    _, p, _, shifted, after = stepped(kir_shifted(shift))
    law = twin_law(bath_shift_V(p, list(parse_spec(kir_shifted(None)).model.species_ids)))
    with law_registry.scope(law_registry.BUILTIN.extended(law)):
        raw = kir_shifted(None)
        raw["model"]["channels"][0]["kinetic_law"] = law.law_id
        _, _, _, twin, twin_after = stepped(raw)
    return (shifted, after), (twin, twin_after)


@pytest.mark.parametrize("solver", ["n2", "rk4"])
def test_the_twin_holds_under_n2_and_rk4_and_in_the_clamp(solver):
    """FR-64's test double beyond ARS(2,2,2) (§9.2; host, about 1 s each): under N2 on B4's
    world, and under RK4 (25 us, the gated laws' bound) without kinds, which RK4 refuses, the
    shifted population's start readouts, one step and its clamped flux and current at -30 mV are
    bit for bit its twin's. The clamp reads the state's gates, so the gate's shift reaches it only
    through them, and never through permeation."""
    shift = {"gates": {"m": ph_shift(side="outside", reference_ph=PH_REF, shift_V_per_ph=SIGMA,
                                    ph_window=[6.8, 7.5])}}  # fmt: skip

    def world(shift, law=None):
        raw = kir_shifted(shift, declare=solver == "n2")
        if law is not None:
            raw["model"]["channels"][0]["kinetic_law"] = law
        if solver == "n2":
            raw["execution"]["solver"] = imex.IMPLICIT_CONDUCTANCE_IDS[0]
        else:
            raw["execution"].update(solver="rk4", dt=2.5e-5)
        return raw

    def evaluate(raw):
        spec = parse_spec(raw)
        impl, state, p, control = bound(spec)
        dt = raw["execution"]["dt"]
        if solver == "rk4":  # RK4's own path, its rhs at each stage, on the host.
            rates = partial(impl.rhs, xp=np)
            after = fixed_step.rk4_step(rates, state, dt, control, p, p.active)
            valid = impl.domain_valid(after, p, p.active, xp=np)
        else:
            after, valid = impl.imex_step(state, dt, control, p, xp=np)
        assert bool(valid)
        clamp = impl.clamped_channel_flux(state, control, p, -0.030, xp=np)
        return impl.readouts(state, control, p, xp=np), after, clamp, p

    shifted, after, clamp, p = evaluate(world(shift))
    law = twin_law(bath_shift_V(p, list(parse_spec(world(None)).model.species_ids)))
    with law_registry.scope(law_registry.BUILTIN.extended(law)):
        twin, twin_after, twin_clamp, _ = evaluate(world(None, law.law_id))
    assert same_bits(shifted, twin) and same_bits(after, twin_after)
    assert same_bits(clamp, twin_clamp)


def test_a_reversal_at_equal_concentrations_is_no_shift():
    """§9.1's zero size for the reversal (host, about 0.5 s): nav_0's m reads V - E_Na with the
    cell's Na set to the bath's, so E is 0 and the start's readouts and explicit rates are bit for
    bit the unshifted world's."""

    def world(shift):
        raw = kir_shifted(None, nav=shift)
        cell, bath = raw["model"]["cells"][0], raw["model"]["extracellular"][0]
        equal = bath["initial_amount_fmol"]["Na"] / bath["volume_pL"] * cell["volume_pL"]
        cell["fixed_charge_equivalent_fmol"] -= equal - cell["initial_amount_fmol"]["Na"]
        cell["initial_amount_fmol"]["Na"] = equal
        spec = parse_spec(raw)
        impl, state, p, control = bound(spec)
        values = impl.readouts(state, control, p, xp=np)
        rates = impl.explicit_rates(state, values.field.potential_V, control, p, xp=np)
        return values, rates

    shifted = world({"gates": {"m": {"reversal_of": "Na"}}})
    plain = world(None)
    assert same_bits(shifted[0], plain[0]) and same_bits(shifted[1], plain[1])


def potential_kinetics_at_v(original):
    def planted(potential, p, *, xp=jnp, structure=None, read=None):
        return original(potential, p, xp=xp, structure=structure)

    return planted


def kinetics_tau_at_v(original):
    def planted(voltage, codes, *, xp=jnp, structure=None, gate_voltages=None):
        given = dict(xp=xp, structure=structure)
        target, _ = original(voltage, codes, gate_voltages=gate_voltages, **given)
        _, tau = original(voltage, codes, **given)
        return target, tau

    return planted


def shift_layout(change):
    original = v3.shift_initial_values

    def planted(spec, structure):
        fields = {k: np.array(v) for k, v in original(spec, structure).items()}
        change(fields)
        return fields

    return planted


def flip_side(fields):
    fields["channel_shift_outside"][0, 0] = ~fields["channel_shift_outside"][0, 0]


def shift_h_too(fields):
    for name in ("ph", "outside", "row", "V_per_ph", "reference_ph", "ph_low", "ph_high"):
        fields[f"channel_shift_{name}"][1, 0] = fields[f"channel_shift_{name}"][0, 0]


def permeation_leak(original):
    """The shift leaking into permeation: a shifted world's channel voltage moved by 1 mV."""

    def planted(membrane_voltage, p, *, xp=jnp):
        voltage = original(membrane_voltage, p, xp=xp)
        if "channel_shift_ph" in type(p)._fields:
            voltage = voltage - xp.where(xp.any(p.channel_shift_ph, axis=0), 1e-3, 0.0)
        return voltage

    return planted


FR64_GATE_PLANTS = {  # name: (owner, attribute, a function of the original)
    "the shift leaking into permeation": (v3, "channel_voltage", permeation_leak),
    "the stage gate at V": (v3, "potential_kinetics", potential_kinetics_at_v),
    "tau read at V": (v3, "channel_kinetics", kinetics_tau_at_v),
    "the other side read": (v3, "shift_initial_values", lambda _: shift_layout(flip_side)),
    "h's row shifted too": (v3, "shift_initial_values", lambda _: shift_layout(shift_h_too)),
}


@pytest.mark.parametrize("plant", [None, *FR64_GATE_PLANTS])
def test_a_gate_on_ph_is_its_twin_bit_for_bit_and_each_plant_breaks_it(plant, monkeypatch):
    """FR-64's test double (§9.2; host, about 1 s): kir_0's m reads the held bath's pH, so dV is
    constant, and the shifted population is bit for bit a twin running Kir2.1's law with m's row
    at V - dV (code 99). Compared: the start's readouts (targets, taus, fluxes, every column) and
    one host ARS(2,2,2) step on B4's world, whose stage gates read each stage's read (O2(b)).
    Plants, each breaking the equality: the stage gate at V, tau read at V, the cell's pH read in
    place of the bath's, and h's row shifted too."""
    if plant is not None:
        owner, name, make = FR64_GATE_PLANTS[plant]
        monkeypatch.setattr(owner, name, make(getattr(owner, name)))
        v3._implementation.cache_clear()
    (shifted, after), (twin, twin_after) = kir_versus_twin()
    v3._implementation.cache_clear()
    equal = same_bits(shifted, twin) and same_bits(after, twin_after)
    assert equal if plant is None else not equal, plant


@pytest.mark.parametrize("declare", [True, False], ids=["B4", "no kinds"])
def test_the_stage_gates_read_each_stage_s_state(declare, monkeypatch):
    """FR-64's stage-state row (§9.1; host, about 1 s): nav_0's m reads V - E_Na at its own cell,
    whose Na its own flux moves, so E moves within the step. In one host ARS(2,2,2) step on B4's
    world, every stage's kinetics are bit for bit NaV1.2's law at V - E of that stage's read (m)
    and at V (h). Planted: the stage gate at V."""
    from cells.laws.channels import nav1p2_m3h_regularized as nav

    def run(planted):
        if planted:
            monkeypatch.setattr(v3, "potential_kinetics", potential_kinetics_at_v(
                v3.potential_kinetics))  # fmt: skip
        captured, original = [], v3.potential_kinetics

        def capturing(potential, p, *, xp=jnp, structure=None, read=None):
            out = original(potential, p, xp=xp, structure=structure, read=read)
            captured.append((potential, read, p, out))
            return out

        monkeypatch.setattr(v3, "potential_kinetics", capturing)
        stepped(kir_shifted(None, declare=declare, nav={"gates": {"m": {"reversal_of": "Na"}}}))
        monkeypatch.undo()
        return captured

    def matches(captured):
        assert captured and all(read is not None for _, read, _, _ in captured)
        same = True
        for potential, read, p, (target, tau, _) in captured:
            k, n, slot = 0, p.active.size, 1  # Na's row; nav_0 (slot 1), the cell to the bath.
            v = np.asarray([potential[0] - potential[n + 0]])
            c_in = (p.amount_reference[k, 0] + read.amount_increment[k, 0]) / p.volume[0]
            outside = p.extracellular_amount_reference[k, 0]
            outside = outside + read.extracellular_amount_increment[k, 0]
            c_out = outside / p.extracellular_volume[0]
            ends = np.asarray([c_in]), np.asarray([c_out])
            e = vshift.ReversalShift.delta_v(*ends, 1, p.temperature)
            at_vr, at_v = nav.LAW.kinetics(v - e, xp=np), nav.LAW.kinetics(v, xp=np)
            same &= target[0, slot] == at_vr[0][0, 0] and tau[0, slot] == at_vr[1][0, 0]
            same &= target[1, slot] == at_v[0][1, 0] and tau[1, slot] == at_v[1][1, 0]
        return same

    assert matches(run(planted=False))
    assert not matches(run(planted=True))


def test_a_zero_shift_is_no_shift_and_its_neighbour_is_unchanged():
    """§9.1's zero size (host, about 1 s): sigma = 0 on kir_0's m and on its block leaves the
    start's readouts and one host ARS(2,2,2) step on B4's world bit for bit the unshifted world's,
    nav_0's included."""
    zero = ph_shift(shift_V_per_ph=0.0)
    zeroed = {"gates": {"m": zero}, "block": zero}
    _, _, _, shifted, after = stepped(kir_shifted(zeroed, block=True))
    _, _, _, plain, plain_after = stepped(kir_shifted(None, block=True))
    assert same_bits(shifted, plain) and same_bits(after, plain_after)


def block_u(v_ref, block, temperature):
    """FR-51's law at V_ref (50 digits): (sum_k w_k K_k/(c_B + K_k)) / (sum_k w_k)."""
    from decimal import localcontext

    with localcontext() as ctx:
        ctx.prec = 50
        f_rt = fr64_laws.F / (fr64_laws.R * Decimal(float(temperature)))
        c_b = Decimal(block.concentration_mM)
        num = den = Decimal(0)
        for mode, steep in zip(block.modes, block.steepness(), strict=True):
            k = Decimal(mode.k0_mM) * (Decimal(steep) * f_rt * v_ref).exp()
            num, den = num + Decimal(mode.weight) * k / (c_b + k), den + Decimal(mode.weight)
        return num / den


@pytest.mark.parametrize("side", ["inside", "outside"])
def test_the_block_on_ph_meets_fr51_s_law_at_its_v_ref(side):
    """The block on pH (§9.2; host, about 0.3 s): kir_0's B1 block reads the pH of its cell (B4's
    free h) or of the held bath. u meets FR-51's law at V_ref = V - sigma (pH - pH_ref), with the
    pH formed from the read's h in 50 digits, within 1e-12 relative, every 10 mV from -100 to
    +40 mV. Planted: the pH read on the other side."""
    raw = kir_shifted({"block": ph_shift(side=side)}, block=True)
    spec = parse_spec(raw)
    impl, state, p, control = bound(spec)
    read, _ = v3._stage_read(state, p, v3._kinds(impl.structure), xp=np)
    h_row = list(spec.model.species_ids).index("H")
    cell_h = (p.amount_reference[h_row, 0] + read.amount_increment[h_row, 0]) / p.volume[0]
    bath_h = p.extracellular_amount_reference[h_row, 0] / p.extracellular_volume[0]
    block = spec.model.channels[0].block
    worst, other = 0.0, 0.0
    for v in np.arange(-0.100, 0.0401, 0.010):
        u = impl.clamped_channel_flux(state, control, p, float(v), xp=np, block=True)[2].block.u[0]
        for h, which in ((cell_h if side == "inside" else bath_h, "own"),
                         (bath_h if side == "inside" else cell_h, "other")):  # fmt: skip
            dv = Decimal(SIGMA) * (fr64_laws.ph(float(h)) - Decimal(PH_REF))
            expected = block_u(Decimal(float(v)) - dv, block, p.temperature)
            gap = float(abs(Decimal(float(u)) - expected) / expected)
            if which == "own":
                worst = max(worst, gap)
            else:
                other = max(other, gap)
    assert worst <= 1e-12 and other > 1e-6, (worst, other)


def ph_block_world(declare, side="inside"):
    """kir_0 with FR-51's B1 block on pH at `side`; without B4 the cell's row stores free h, at
    pH 7.2, its charge kept."""
    raw = kir_shifted({"block": ph_shift(side=side)}, block=True, declare=declare)
    if not declare:
        cell = raw["model"]["cells"][0]
        free = 1000.0 * 10.0**-7.2 * cell["volume_pL"]
        cell["fixed_charge_equivalent_fmol"] -= free - cell["initial_amount_fmol"]["H"]
        cell["initial_amount_fmol"]["H"] = free
    return raw


def without_proton_term(original):
    def planted(*args, **kwargs):
        terms = original(*args, **kwargs)
        return terms._replace(proton_slope=np.zeros_like(terms.proton_slope))

    return planted


@pytest.mark.parametrize("declare", [False, True], ids=["unbuffered", "buffered"])
def test_the_block_on_ph_s_material_term_bounds_the_proton_slope(declare, monkeypatch):
    """The block on pH's material term (§4.2; host, about 1 s): kir_0's B1 block reads its cell's
    pH. block_material_rates' part at the cell (its rate less the same rate with proton_slope
    zeroed) bounds |dJ_K/dn_H|, a central difference at the state's own potentials. Unbuffered,
    the stored row is free h and the bound is tight within 1e-6 (B1's modes share their sign).
    B4-buffered, the stored row is H_eq and dh/dH_eq <= 1. material_rate includes it. Plants: the
    term dropped (proton_slope zeroed), and block_material_rates reading the stored H_eq in place
    of the read, which misses the buffered bound."""
    spec = parse_spec(ph_block_world(declare))
    impl, state, p, control = bound(spec)
    structure = impl.structure
    k, h_row = 1, list(spec.model.species_ids).index("H")
    values = impl.field_values(state, control, p, xp=np)
    potentials, v = values.potential_V, values.rates.membrane_voltage_V
    routed, _ = v3._route(structure, v3._kinds(structure), state, control, p, xp=np)
    n_h = p.amount_reference[h_row, 0] + state.amount_increment[h_row, 0]
    step = 1e-6 * n_h

    def flux(delta):
        moved = state.amount_increment.copy()
        moved[h_row, 0] += delta
        out = impl.clamped_channel_flux(state._replace(amount_increment=moved), control, p, v,
                                        xp=np)  # fmt: skip
        return out[0][k, 0]

    slope = abs(flux(step) - flux(-step)) / (2 * step)

    def cell_rate():
        return v3.block_material_rates(state, p, potentials, xp=np, structure=structure,
                                       control=routed)[0]  # fmt: skip

    honest = cell_rate()
    with monkeypatch.context() as plant:
        plant.setattr(v3, "channel_block_terms", without_proton_term(v3.channel_block_terms))
        dropped = cell_rate()
    part = honest - dropped
    assert part >= slope * (1 - 1e-6) and dropped < slope
    if not declare:
        assert part <= slope * (1 + 1e-6)
    assert impl.material_rate(state, control, p, xp=np, potentials=potentials) >= honest
    if declare:  # Planted: the stored H_eq in place of the read, inside block_material_rates.
        with monkeypatch.context() as plant:
            plant.setattr(v3, "_stage_read", lambda state, p, kinds, *, xp: (state, True))
            stored = cell_rate()
        assert stored - dropped < slope * (1 - 1e-6)


def test_the_block_on_ph_at_a_held_bath_adds_no_material_term(monkeypatch):
    """At a held bath the pH does not move, so the block on the bath's pH adds no material term
    anywhere (§4.2; host, about 0.3 s)."""
    spec = parse_spec(ph_block_world(True, side="outside"))
    impl, state, p, control = bound(spec)
    structure = impl.structure
    potentials = impl.field_values(state, control, p, xp=np).potential_V
    routed, _ = v3._route(structure, v3._kinds(structure), state, control, p, xp=np)

    def rates():
        return v3.block_material_rates(state, p, potentials, xp=np, structure=structure,
                                       control=routed)  # fmt: skip

    honest = rates()
    with monkeypatch.context() as plant:
        plant.setattr(v3, "channel_block_terms", without_proton_term(v3.channel_block_terms))
        assert np.array_equal(rates(), honest)


def test_a_step_whose_end_leaves_a_block_s_window_is_refused_within_it(monkeypatch):
    """§3.5, as the lead ruled on 27 November (host, about 1 s). kir_0's block reads its
    unbuffered cell's pH, which a proton route at 1e-5 m/s lowers by 5e-4 in one step. With the
    window's low edge half way down, the start is inside, ARS(2,2,2)'s inner stage too, and the
    end outside: the step is refused within it, by the end-of-step check (shift_window_valid).
    Planted: the check left out, and the step is accepted with its end state off the window."""
    raw = ph_block_world(False)
    for patch in raw["model"]["membranes"]:
        patch["permeability_m_per_s"]["H"] = 1e-5
    raw["model"]["channels"][0]["voltage_shift"]["block"]["ph"]["ph_window"] = [7.2 - 2.5e-4, 7.5]
    spec = parse_spec(raw)
    impl, state, p, control = bound(spec)
    dt = raw["execution"]["dt"]
    assert not bool(impl.imex_step(state, dt, control, p, xp=np)[1])
    monkeypatch.setattr(v3, "shift_window_valid", lambda state, p, structure, *, xp: True)
    after, ok = impl.imex_step(state, dt, control, p, xp=np)
    h_row = list(spec.model.species_ids).index("H")
    free = (p.amount_reference[h_row, 0] + after.amount_increment[h_row, 0]) / p.volume[0]
    assert bool(ok) and -np.log10(free / 1000.0) < 7.2 - 2.5e-4 - vshift.PH_MARGIN


def test_a_ph_off_its_window_or_a_v_r_off_its_law_s_domain_is_refused():
    """§3.5 and §4.3 at run time (host, about 1 s). kir_0's m reads the bath's pH on [6.8, 7.5]:
    with the bath moved to pH 6.79, the readers, the readouts and the step are each refused, never
    clipped. A bath declared at pH 6.79 is refused at its definition's initial state. kir_0's m on
    E_K, whose V_r is +75 mV, off Kir2.1's domain, is refused there too."""
    raw = kir_shifted({"gates": {"m": ph_shift()}})
    spec = parse_spec(raw)
    impl, state, p, control = bound(spec)
    h_row = list(spec.model.species_ids).index("H")
    acid = state.extracellular_amount_increment.copy()
    acid[h_row, 0] = 1000.0 * 10.0**-6.79 * p.extracellular_volume[0]
    acid[h_row, 0] -= p.extracellular_amount_reference[h_row, 0]
    moved = state._replace(extracellular_amount_increment=acid)
    ci, co = v3.physical_amounts(moved, p)
    ci, co = ci / p.volume, np.where(p.outside_active, co / p.extracellular_volume, 1.0)
    v = impl.field_values(moved, control, p, xp=np).rates.membrane_voltage_V
    voltage = v3.channel_voltage(v, p, xp=np)
    assert not bool(v3.reader_voltages(ci, co, voltage, p, xp=np, structure=impl.structure).valid)
    assert not bool(impl.readouts(moved, control, p, xp=np).valid)
    assert not bool(impl.imex_step(moved, raw["execution"]["dt"], control, p, xp=np)[1])
    bath = raw["model"]["extracellular"][0]
    acidic = 1000.0 * 10.0**-6.79 * bath["volume_pL"]
    bath["fixed_charge_equivalent_fmol"] -= acidic - bath["initial_amount_fmol"]["H"]
    bath["initial_amount_fmol"]["H"] = acidic
    with pytest.raises(ConfigError, match="domain invalid"):
        parse_spec(raw)
    with pytest.raises(ConfigError, match="domain invalid"):
        parse_spec(kir_shifted({"gates": {"m": {"reversal_of": "K"}}}))


FR64_SLOT_WRITERS = FR51_SLOT_WRITERS | {
    "cells.model.resolved_pump_replacement@1": lambda: replacement_fixtures.with_replacement(
        replacement_fixtures.heredity_sheet(radius=1)
    ),  # The standalone model: it runs the composite's check (cell_replacement.check_definition).
}


@pytest.mark.parametrize("law", list(FR64_SLOT_WRITERS))
def test_a_gate_shift_beside_an_operator_that_rewrites_channel_slots_is_refused(law, monkeypatch):
    """FR-64's widened slot refusal (parse only, about 1 s each): a gate's shift, with no block,
    beside replacement, partition or insertion is refused by name in the composite form, and with
    the refusal planted away it is admitted, its shift kept. The standalone replacement model
    meets the same refusal through the composite's check; with it planted away, it fails closed
    at @3's structure, which it builds without, as FR-51's block does there (D364)."""
    raw = FR64_SLOT_WRITERS[law]()
    entry = raw["model"]["channels"][0]
    gates = spec_v3.channel_laws()[entry["kinetic_law"]].gates
    assert gates
    ion = next(i["species_id"] for i in entry["permeant_ions"] if i["relative_permeability"])
    entry["voltage_shift"] = {"gates": {gates[0]: {"reversal_of": ion}}}
    with pytest.raises(ConfigError, match="rewrites channel slots but not a voltage shift"):
        parse_spec(raw)
    monkeypatch.setattr(pump_composite, "block_slot_errors", lambda pairs, spec: [])  # The plant.
    if law == "cells.model.resolved_pump_replacement@1":  # It then fails closed at the structure.
        with pytest.raises(ConfigError, match="voltage_shift runs in @3 through its structure"):
            parse_spec(raw)
        return
    assert parse_spec(raw).model.channels[0].voltage_shift is not None


def test_a_path_without_the_structure_and_the_stationary_analysis_refuse_a_shift():
    """FR-64's fail-closed sites (host, about 1.5 s): @3's initial values without the structure,
    which would drop the shift, and the stationary analysis, which does not read it, refuse a
    gate's shift by name. So do the frozen water family models, water@1 and water@2 (crossrev's
    worlds, nav_0's m on the Na reversal), which build @3 without the structure; D327's probe
    found them (validation/fr64/d327_probe.py). Their compositions admit the shift."""
    from cells.analysis import stationary

    on_na = {"gates": {"m": {"reversal_of": "Na"}}}
    spec = parse_spec(kir_shifted(None, declare=False, nav=on_na))
    with pytest.raises(ConfigError, match="voltage_shift runs in @3 through its structure"):
        v3.initial_values(spec)
    with pytest.raises(ConfigError, match="declared voltage shift"):
        stationary.problem(spec)
    cell = water_fixtures.heredity_cell("D", end_time=0.1)
    water = water_fixtures.with_water(cell, pf_m_s=5e-4, bath_pressure_Pa=12.5)
    symport = water_fixtures.with_symport(water, flux_mmol_L_h=15.0, steepness=0.12)
    for raw in (water, symport):
        nav = next(c for c in raw["model"]["channels"] if c["id"] == "nav_0")
        nav["voltage_shift"] = on_na
        with pytest.raises(ConfigError, match="voltage_shift runs in @3 through its structure"):
            parse_spec(raw)
        assert parse_spec(composite_spec.frozen_definition(raw)).model.channels  # Admitted.


def test_a_world_with_every_reader_and_kind_round_trips():
    """FR-64's declaration at the world level (host, about 0.5 s): both gates and the block, each
    kind, on B4's world, parse, round-trip through to_dict and name their readers sorted."""
    shift = {"gates": {"m": ph_shift()}, "block": ph_shift(side="inside")}
    on_na = {"gates": {"h": {"reversal_of": "Na"}}}
    spec = parse_spec(kir_shifted(shift, block=True, nav=on_na))
    assert parse_spec(spec_v3.to_dict(spec)) == spec
    assert spec_v3.shifted_readers(spec.model) == (
        ("kir_0", "block", "ph"), ("kir_0", "m", "ph"), ("nav_0", "h", "reversal_of"),
    )  # fmt: skip


# ------------------------------------------------------------------ FR-64: D327's pair on the host
# FR-50 phase 2's one-way channel records on shifted populations (the lead's ruling 1), the tier-2
# supplement to tests/unit/test_voltage_shift_compiled.py, with the pair's three plants.


def split_u_without_shift(original):
    """The split's u formed at V, the block's own law with no shift."""

    def planted(c_in, c_out, voltage, opening, availability, u, p, *, xp):
        k = block_law.dissociation(p.channel_block_k0_mM, p.channel_block_steepness, voltage,
                                   p.temperature, xp=xp)  # fmt: skip
        _, free = block_law.fractions(p.channel_block_concentration_mM, k)
        plain = block_law.unblocked_fraction(p.channel_block_weight, free)
        plain = xp.where(p.channel_active, plain, 1.0)
        return original(c_in, c_out, voltage, opening, availability, plain, p, xp=xp)

    return planted


def split_at_v_ref(original):
    """The split's permeation read at the block's V_ref (its pH shift on the inside)."""

    def planted(c_in, c_out, voltage, opening, availability, u, p, *, xp):
        row, acid = p.channel_shift_row[-1], p.channel_shift_ph[-1]
        h = xp.where(acid, c_in[row, xp.arange(row.size)], 1000.0)
        dv = vshift.PhShift.delta_v(h, p.channel_shift_V_per_ph[-1],
                                    p.channel_shift_reference_ph[-1], xp=xp)  # fmt: skip
        moved = voltage - xp.where(acid, dv, 0.0)
        return original(c_in, c_out, moved, opening, availability, u, p, xp=xp)

    return planted


def end_view_stored(original):
    """The step's end views read their stored rows in place of their reads."""

    def planted(view, p, structure, *, xp=jnp):
        return original(view._replace(read=view.state), p, structure, xp=xp)

    return planted


FR64_PAIR_PLANTS = {  # name: (the module function of @3's it wraps, the plant)
    "the split's u without the shift": ("channel_one_way_split", split_u_without_shift),
    "the split's permeation at V_ref": ("channel_one_way_split", split_at_v_ref),
    "the end view's stored row": ("channel_one_way_fluxes", end_view_stored),
}


@pytest.mark.parametrize("plant", [None, *FR64_PAIR_PLANTS])
def test_the_pair_s_records_on_the_host_and_each_plant(plant, monkeypatch):
    """D327's pair on the host (about 1 s each): three host ARS(2,2,2) steps of
    validation/fr64/worlds.pair_world. Each population's records meet their closed forms within
    1e-11, and their gaps are at most 1e-12. Each plant misses the block-on-pH population's
    absolute value, and only it: the split's u formed at V without the shift; the split's
    permeation at V_ref; the end views' stored H_eq in place of their reads."""
    if plant is not None:
        name, make = FR64_PAIR_PLANTS[plant]
        monkeypatch.setattr(v3, name, make(getattr(v3, name)))
    raw = fr64_worlds.pair_world()
    spec = parse_spec(raw)
    impl, state, p, control = bound(spec)
    dt = raw["execution"]["dt"]
    for _ in range(3):
        state, valid = impl.imex_step(state, dt, control, p, xp=np)
        assert bool(valid)
    misses = []
    for slot, name in enumerate(("k_population", *fr64_worlds.KV)):
        expected = fr64_laws.pair_one_way(raw, name, fr64_worlds.CELL_PH)
        forward, backward = (float(v) * 3 * dt for v in expected)
        f, b = state.one_way_forward_fmol[slot], state.one_way_backward_fmol[slot]
        if abs(f - forward) > 1e-11 * forward or abs(b - backward) > 1e-11 * backward:
            misses.append(name)
    assert plant is not None or np.all(state.one_way_gap_relative <= 1e-12)
    assert misses == ([] if plant is None else ["k_population"]), misses


# ------------------------------------------------------------------ FR-50 phase 2: @3's own records
# fr50-one-way-records-v1 §3 (validation/fr50/REGISTRATION.md): the model key one_way_records. The
# host rows take the registered cases' worlds (validation/fr50/engine) and the builder's closed
# forms (validation/fr50/closed_forms), read by the tagged judge's own checks; the code-blind
# references are the judged run's alone. The compiled rows are test_one_way_records_own.py.

FR50 = fr50_engine._cases()  # {case kind: its registered case}
FR50_PLANTS = {name: plant for name, plant in fr50_judge.PLANTS.items() if plant["kind"] == "E6"}


def fr50_world(name, **kwargs):
    if name == "world_1":
        return fr50_engine.world_1(FR50["E1"], FR50["E4"], dt=1e-4, end=1e-3, **kwargs)
    return fr50_engine.world_2(FR50["E2"], FR50["E3"], dt=5e-3, end=5e-2, **kwargs)


@pytest.mark.parametrize("plant", [None, *FR50_PLANTS])
def test_the_channel_split_off_reversal_and_each_registered_plant(plant):
    """E6 (host, about 0.3 s): World 1's blocked population at the five declared voltages and two
    availabilities, through clamped_channel_flux: u and each direction within 1e-12 of the closed
    forms, the kernel closure within 4 ulps and Ussing's ratio within 1e-12, by the judge's own
    check_e6. Each registered plant (validation/fr50/plants) fails as the judge's PLANTS say: the
    availability left out of the split, the block left out, B(x) and B(-x) exchanged."""
    ref = fr50_closed.e6("E6", FR50["E6"])
    request = fr50_judge.request_for(ref, plant=plant)
    results = fr50_judge.judge_case(ref, fr50_engine.engine(request), request)
    if plant is None:
        assert all(r["passed"] for r in results.values()), results
    else:
        assert fr50_judge._plant_caught(FR50_PLANTS[plant], results)[0], results


def test_the_channel_split_closes_to_channel_rates_flux_within_four_ulps():
    """The kernel closure (fr50-one-way-records-v1 §1) on a sweep (host, about 3 s): World 1's
    population at five K pairs (each world's V is its E_K, inside the domain), every 12 mV from
    -120 to +60 mV and three availabilities, under its
    reversal reference, under the membrane voltage and with a second mode: outward less inward is
    channel_rates' outward flux within 4 ulps of their sum at every point. Plant: the split without
    the block fails where u is not 1."""

    def sweep(case):
        spec = parse_spec(fr50_engine.world_1(None, case, dt=1e-4, end=1e-4))
        impl, state, p, control = bound(spec)
        k, worst = list(spec.model.species_ids).index("K"), 0.0
        for v in np.arange(-0.120, 0.0601, 0.012):
            for a in (1.0, 0.5, 0.3):
                held = control._replace(channel=np.full_like(control.channel, a))
                flux, _, (out, back) = impl.clamped_channel_flux(
                    state, held, p, float(v), xp=np, one_way=True
                )
                f, b, j = (float(x[k, 0]) for x in (out, back, flux))
                excess = abs(Decimal(f) - Decimal(b) - Decimal(j))
                worst = max(worst, float(excess / Decimal(float(np.spacing(f + b)))))
        return worst

    pairs = (("140", "5.4"), ("140", "50"), ("30", "140"), ("0.5", "0.2"), ("5", "5"))
    block = FR50["E4"]["block"]
    variants = (
        block,
        dict(block, reference="membrane_voltage"),
        dict(block, modes=[dict(weight="0.6", k0_mM="1", electrical_distance="0.5"),
                           dict(weight="0.4", k0_mM="0.2", electrical_distance="0.9")]),
    )  # fmt: skip
    for c_in, c_out in pairs:
        for b in variants:
            assert sweep(dict(FR50["E4"], c_in_mM=c_in, c_out_mM=c_out, block=b)) <= 4.0
    with fr50_plants.planted("E6b_block_omitted"):
        assert sweep(dict(FR50["E4"], c_in_mM="140", c_out_mM="50")) > 4.0


def test_each_route_s_split_is_its_net_record_s_two_directions():
    """@3's own kernels at one end (host, own_one_way_fluxes on a LabelView): World 1's patch route
    at -60 mV, its inward over outward Ussing's (c_o/c_i) e^(-x) within 1e-12 and its difference the
    transport's membrane flux within 4 ulps of their sum; World 2's face and junction at unequal S
    (2 and 1 uM), each direction g c of its own end within 1e-15 of the closed forms' g. Plant: the
    potentials negated (B(x) and B(-x) exchanged) misses Ussing's ratio."""
    from cells.laws.electrochemistry import F, R
    from cells.registry.kind_registry import LabelView

    spec = parse_spec(fr50_world("world_1"))
    impl, state, p, control = bound(spec)
    n, v = p.active.size, -0.060
    potentials = np.zeros(n + p.outside_active.size)
    potentials[0] = v

    def membrane(volts):
        view = LabelView(state, state, volts, control)
        forward, backward = v3.own_one_way_fluxes(view, p, impl.structure, xp=np)
        return float(forward[1]), float(backward[1])  # The structure's order: channel, membrane.

    out, back = membrane(potentials)
    x = F * v / (R * spec.model.temperature_K)
    ussing = (5.4 / 140) * np.exp(-x)
    assert abs(back / out - ussing) <= 1e-12 * ussing
    k = list(spec.model.species_ids).index("K")
    j = float(selective_flux(140.0, 5.4, v, 1, spec.model.temperature_K, p.membrane_area[0],
                             p.membrane_permeability[k, 0], 0.0, 1.0, 1.0, xp=np))  # fmt: skip
    assert abs(out - back - j) <= 4 * float(np.spacing(out + back))  # The transport's own law.
    planted, planted_back = membrane(-potentials)
    assert abs(planted_back / planted - ussing) > 1e-6 * ussing
    raw = fr50_world("world_2")
    for node, c in ((fr50_engine.CELL, 2e-3), (fr50_engine.NODE, 2e-3)):
        amounts = next(x for x in (*raw["model"]["cells"], *raw["model"]["extracellular"])
                       if x["id"] == node)["initial_amount_fmol"]  # fmt: skip
        amounts["S"] = c * 1.0
    spec = parse_spec(raw)
    impl, state, p, control = bound(spec)
    view = LabelView(state, state, np.zeros(p.active.size + p.outside_active.size), control)
    forward, backward = v3.own_one_way_fluxes(view, p, impl.structure, xp=np)
    face = 1e15 * 1e-10 * 1e-10 / 1e-5  # g = 1e15 D A / L (pL/s), E3's.
    junction = 1e15 * 1e-9 * 1e-12  # g = 1e15 P A gate v, E2's.
    for got, want in zip((*forward, *backward), (face * 2e-3, junction * 2e-3, face * 1e-3,
                                                  junction * 1e-3), strict=True):  # fmt: skip
        assert abs(float(got) - want) <= 1e-14 * want


def test_the_registered_refusals_each_name_one_way_and_their_cause_beside_an_accepted_control():
    """E5 (parse only, about 2 s): a charged face row, a forms face, a pump and RK4, each refused
    with its declaration's name and its cause, and each control (the same world without the
    declaration; for RK4, erratum 1's) accepted, by the judge's own check_refusals."""
    results = fr50_judge.check_refusals("E5", fr50_engine.e5(FR50))
    assert all(r["passed"] for r in results.values()), results


def fr50_refusal_world(name):
    """(raw, reason) of each further refusal of @3's own records (FR50_REFUSALS)."""
    raw = fr50_world("world_1")
    m, record = raw["model"], raw["model"]["one_way_records"]
    if name == "an empty list":
        m["one_way_records"] = []
    elif name == "an unknown entity kind":
        record[0]["entity"] = "pore"
    elif name == "a kind's route":
        record[0]["entity"] = "passive_route"
    elif name == "an unknown entity":
        record[0]["id"] = "nowhere"
    elif name == "an unknown species":
        record[0]["species"] = ["Q"]
    elif name == "a pair twice":
        record.append(dict(record[0]))
    elif name == "an unknown key":
        record[0]["readout"] = True
    elif name == "a calcium pump":
        raw = v3_fixtures.definition("closed")
        pump = raw["model"]["membranes"][0]["calcium_pump"]["id"]
        raw["model"]["one_way_records"] = [dict(entity="calcium_pump", id=pump, species=["Ca"])]
    return raw


FR50_REFUSALS = {
    "an empty list": "non-empty list",
    "an unknown entity kind": "entity is one of",
    "a kind's route": "keep their own one_way records",
    "an unknown entity": "names no membrane",
    "an unknown species": "distinct species rows",
    "a pair twice": "declared twice",
    "an unknown key": "unknown=",
    "a calcium pump": "is a pump",
}


@pytest.mark.parametrize("name", list(FR50_REFUSALS))
def test_each_further_refusal_of_the_records_names_its_reason(name):
    """@3's own records (parse only, about 0.2 s each): each malformed declaration is refused with
    its reason."""
    with pytest.raises(ConfigError, match=FR50_REFUSALS[name]):
        parse_spec(fr50_refusal_world(name))


def fr50_beside(name):
    """(raw, reason) of the records beside a path that cannot carry them (each fails closed)."""
    if name == "a slot changer (partition)":
        raw = partition_fixtures.divided()
        reason = "opens, closes or retires slots, and @3 keeps its own one_way records"
    elif name == "a fixed-field operator (replacement@1)":
        raw = composite_spec.frozen_definition(
            replacement_fixtures.with_replacement(replacement_fixtures.heredity_sheet(radius=1))
        )
        reason = "today's fixed fields, which drop @3's own one_way records"
    elif name.startswith("the integer unit population"):  # D327 beside FR-52's cohorts.
        from validation.fr52_cohorts import worlds as fr52_worlds

        raw = fr52_worlds.qualification(cohorts=name.endswith("cohorts"))
        reason = (
            "cells.operator.integer_unit_population@1 is refused beside @3's own one_way records"
        )
    else:  # The water family, whose internals are today's fixed fields.
        raw = water_fixtures.with_water(water_fixtures.heredity_cell("D", end_time=0.004),
                                        pf_m_s=5e-4)  # fmt: skip
        reason = "does not run @3's own one_way records"
    patch = raw["model"]["membranes"][0]["id"]
    raw["model"]["one_way_records"] = [dict(entity="membrane", id=patch, species=["K"])]
    return raw, reason


@pytest.mark.parametrize(
    "name",
    [
        "a slot changer (partition)",
        "a fixed-field operator (replacement@1)",
        "water@1",
        "the integer unit population with its cohorts",
        "the integer unit population without cohorts",
    ],
)
def test_the_records_are_refused_where_a_path_would_drop_them(name):
    """Fails closed (parse only, about 1 s each): beside a composite operator that opens, closes or
    retires slots, or that builds the inner fields with today's fixed fields, and in a family with
    fixed internals, @3's own records are refused by name, as are a kind's beside a closer. Beside
    cells.operator.integer_unit_population@1, with or without FR-52's cohorts, they are refused by
    name until a world qualifies the pair (D327's rule for two landings' combinations); FR-52's
    qualification world parses without them in its own tests."""
    raw, reason = fr50_beside(name)
    with pytest.raises(ConfigError, match=reason):
        parse_spec(raw)


def test_records_run_on_the_fine_engine_and_through_their_structure_alone():
    """Fails closed (host, about 1 s): under execution.projective both phases' records are refused
    (a jump would extrapolate them and their gap's running maximum), @3's own and a kind's (phase
    1's routes world: the lead's ruling 2 of 26 November 2026; no registered or judged world ran
    one there); and a path that runs @3 without its structure refuses @3's own records."""
    one = parse_spec(fr50_world("world_1"))
    cases = fr50_engine._cases()
    kinds = parse_spec(fr50_engine.routes_world(cases["K1"], cases["K2"], dt=0.1, end=0.2))
    for spec in (one, kinds):
        with pytest.raises(ConfigError, match="one_way records run on the fine engine"):
            get_model(spec.model).check_steps(replace(spec, projective=object()),
                                              [spec.execution.dt], None)  # fmt: skip
    plain = parse_spec(fr50_world("world_1", records=False))
    get_model(plain.model).check_steps(replace(plain, projective=None), [plain.execution.dt], None)
    with pytest.raises(ConfigError, match="one_way_records runs in @3 through its structure"):
        v3.initial_values(parse_spec(fr50_world("world_2")))  # World 1's block refuses first.


def test_the_records_key_round_trips_and_without_it_nothing_moves():
    """D148 (host): with one_way_records the definition round-trips, its structure holds the sorted
    pairs, the state gains exactly the three record fields on the pair axis and the layout the
    pairs' entity slot and species row; without it, to_dict writes no key and the structure, the
    state and the layout are the world's without records."""
    spec = parse_spec(fr50_world("world_1"))
    assert parse_spec(spec_v3.to_dict(spec)) == spec
    assert (
        spec_v3.to_dict(spec)["model"]["one_way_records"]
        == fr50_world("world_1")["model"]["one_way_records"]
    )
    impl, state, p, _ = bound(spec)
    assert impl.structure.one_way_records == (
        ("channel", fr50_engine.CHANNEL, "K"), ("membrane", fr50_engine.WALL, "K"),
    )  # fmt: skip
    plain = parse_spec(fr50_world("world_1", records=False))
    assert "one_way_records" not in spec_v3.to_dict(plain)["model"]
    assert v3.structure(plain.model).one_way_records == ()
    base, plain_state, plain_p, _ = bound(plain)
    assert base.STATE_TYPE is v3.STATE_TYPE  # A block alone adds no state field.
    assert type(state)._fields == (*v3.STATE_TYPE._fields, *v3.ONE_WAY_STATE_AXES)
    assert type(p)._fields == (*type(plain_p)._fields, *v3.ONE_WAY_LAYOUT_FIELDS)
    k = list(spec.model.species_ids).index("K")
    assert p.one_way_entity.tolist() == [0, 0] and p.one_way_row.tolist() == [k, k]
    assert all(np.all(getattr(state, f) == 0) for f in v3.ONE_WAY_STATE_AXES)


@pytest.mark.parametrize("solver", [ARS, "cells.solver.imex_euler_face_electromigration@1"])
def test_the_records_are_passive_and_d327_s_planted_fault_doubles_them(solver):
    """Three host steps of each world, under ARS(2,2,2) and the Euler IMEX (about 2 s each):
    - with and without the records, every other field is bit for bit the same (nothing reads them);
    - every pair's records grow and close to its net record, with its gap at most 1e-12;
    - D327's planted fault, FR-51's block left out of both directions of the channel split, doubles
      World 1's channel records at V = E_K (u = 1/2) while its net, gap and closure still hold,
      which only an absolute check (E4-1) sees."""

    def steps(raw):
        raw["execution"]["solver"] = solver
        impl, state, p, control = bound(parse_spec(raw))
        for _ in range(3):
            state, valid = impl.imex_step(state, raw["execution"]["dt"], control, p, xp=np)
            assert bool(valid)
        return state

    for name in ("world_1", "world_2"):
        recorded, plain = steps(fr50_world(name)), steps(fr50_world(name, records=False))
        for field in type(plain)._fields:
            assert (
                np.asarray(getattr(recorded, field)).tobytes()
                == np.asarray(getattr(plain, field)).tobytes()
            ), (name, field)
        forward, backward = recorded.one_way_forward_fmol, recorded.one_way_backward_fmol
        assert np.all(forward > 0) and np.all(backward > 0)
        assert np.all(recorded.one_way_gap_relative <= 1e-12)
        if name == "world_1":
            with fr50_plants.planted("E4_block_omitted"):
                planted = steps(fr50_world(name))
            channel = 0  # The structure's order: the channel's pair first.
            for record in ("one_way_forward_fmol", "one_way_backward_fmol"):
                ratio = getattr(planted, record)[channel] / getattr(recorded, record)[channel]
                assert abs(ratio - 2.0) <= 1e-12
            assert np.all(planted.one_way_gap_relative <= 1e-12)
