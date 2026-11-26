"""Q2, the presence gate (docs/CORE_SEAMS_DESIGN.md §18 at 931b6606; the lead's ruling of 19
November 2026, the @3 owner's option (a), in the form of B1's pump gate).

Each kind declares one or more presence fields per entity axis (F's contract, Kind.presence,
{entity axis: (layout field, ...)}, read through kind_registry.presence_fields on the bound kind;
the lead's ruling (2) of 19 November 2026). Where a closer is declared, @3 ands each with its
entities' host activity, through axis_hosts and the host table, before every rates, readouts and
stage-term call (surface_pump_v3.presence_gated), and binding holds every presence-declaring kind to
exact zeros with every entity absent (_check_presence). The plant is the real kind:
- the built-in transporter declaring transporter_present alone is refused, naming its cycles, heat
  and work: its kinetics read its law masks, not its presence;
- declaring all three of its masks (transporter_present, transporter_neutral, transporter_proton)
  is admitted, and on a closed patch (composition §13.1's 1.41e-5 fmol/s, @3's pump before B1) it
  moves exactly nothing, its rates and readouts are zero, and without a closer the same closed patch
  keeps cycling;
- a closer-free structure sees its layout unchanged, so its programs are today's;
- an own axis reads its entities' hosts through axis_hosts;
- @3's channel and face slots have hosts (the lead's ruling of 19 November 2026, matching the
  composite's close()): a channel population is active where its slot and its patch are, a face
  where its slot and both its outside nodes are. A planted kind on channel slots, its presence
  declared there, moves exactly nothing on a closed patch, its moves those of the same world with
  the kind absent, and without a closer the same closed patch keeps it carrying (the plant).
"""

import dataclasses
from types import SimpleNamespace

import numpy as np
import pytest

from cells.definitions.specs import ConfigError, parse_spec
from cells.definitions.surface_pump_v3_spec import control_values
from cells.kinds import transporter
from cells.laws.electrochemistry import F, R
from cells.models import surface_pump_v3
from cells.numerics.extracellular_field import scatter
from cells.numerics.species_sums import species_sum
from cells.registry import kind_registry
from tests import kind_fixtures
from tests.unit.test_transporter_kind import held_world, scoped

ALONE = {"membrane_slot": ("transporter_present",)}
ALL_THREE = {"membrane_slot": ("transporter_present", "transporter_neutral", "transporter_proton")}


def with_presence(kind, presence):
    """The kind with `presence`, {axis: (field, ...)}, and what F's declaration_errors asks of each
    named field: its axes in field_axes and its role, structural with fill False."""
    names = [name for group in presence.values() for name in group]
    return dataclasses.replace(
        kind,
        presence=presence,
        field_axes={**kind.field_axes, **{name: ("membrane_slot",) for name in names}},
        partition_roles={
            **kind.partition_roles,
            **{name: kind_registry.PartitionRole("structural", False) for name in names},
        },
    )


DECLARED = with_presence(transporter.TRANSPORTER, ALL_THREE)  # The built-in, all three masks.


def _bound(spec, *, closer):
    """(structure, state, layout, control) of the world at t = 0, with a closer declared or not."""
    structure = dataclasses.replace(surface_pump_v3.structure(spec.model), padding_fill=closer)
    state, p = surface_pump_v3.initial_values(spec, structure=structure)
    controls = control_values(spec, [0.0])
    control = surface_pump_v3.kind_types(structure).Control(*(v[0] for v in controls))
    return structure, state, p, control


def _closed(p):
    """The layout with the transporter's patch (membrane_0, slot 0) closed at the view."""
    active = np.asarray(p.membrane_active).copy()
    active[0] = False
    return p._replace(membrane_active=active)


def _rates(structure, state, p, control):
    potentials = surface_pump_v3.readouts(
        state, control, p, xp=np, structure=structure
    ).field.potential_V
    rates, _ = surface_pump_v3.explicit_rates(
        state, potentials, control, p, xp=np, structure=structure
    )
    return rates, potentials


def test_the_transporter_declaring_its_three_masks_on_a_closed_patch_moves_exactly_nothing():
    with scoped(DECLARED):
        spec = parse_spec(held_world())
        structure, state, p, control = _bound(spec, closer=True)
        closed = _closed(p)
        rates, potentials = _rates(structure, state, closed, control)
        for name in (
            "transporter_cycles",
            "transporter_dissipated_energy_pJ",
            "transporter_metabolic_work_pJ",
        ):
            assert np.asarray(getattr(rates, name))[0] == 0.0
        assert np.all(np.asarray(rates.transporter_fuel_supplied_fmol)[:, 0] == 0.0)
        # Its moves: the totals equal the same closed world's with no transporter at all.
        absent = closed._replace(transporter_present=np.zeros_like(p.transporter_present))
        without, _ = _rates(structure, state, absent, control)
        np.testing.assert_array_equal(rates.amount_increment, without.amount_increment)
        np.testing.assert_array_equal(
            rates.extracellular_amount_increment, without.extracellular_amount_increment
        )
        gated = surface_pump_v3.presence_gated(closed, structure, xp=np)
        read, _ = surface_pump_v3._stage_read(
            state, gated, surface_pump_v3._kinds(structure), xp=np
        )
        for column in DECLARED.readouts(state, read, potentials, control, gated, xp=np):
            assert np.asarray(column)[0] == 0.0
        # Planted: without a closer the gate is absent, and the closed patch keeps cycling.
        open_structure, _, _, _ = _bound(spec, closer=False)
        leaking, _ = _rates(open_structure, state, closed, control)
        assert np.asarray(leaking.transporter_cycles)[0] > 0.0


def test_a_closer_free_structure_keeps_its_layout():
    with scoped(DECLARED):
        spec = parse_spec(held_world())
        structure, _, p, _ = _bound(spec, closer=False)
        assert surface_pump_v3.presence_gated(p, structure, xp=np) is p
        assert surface_pump_v3.presence_gated(p, None, xp=np) is p


def test_an_own_axis_reads_its_entities_hosts_through_axis_hosts():
    with scoped(DECLARED):
        spec = parse_spec(held_world())
        _, _, p, _ = _bound(spec, closer=True)
    closed = _closed(p)
    hosts = SimpleNamespace(**closed._asdict(), route_host=np.array([0, 0, 0]))
    kind = SimpleNamespace(axis_hosts={"route": kind_registry.AxisHost("patch", "route_host")})
    activity = surface_pump_v3.entity_activity(kind, "route", hosts, xp=np)
    np.testing.assert_array_equal(activity, [False, False, False])  # All on the closed patch.
    np.testing.assert_array_equal(
        surface_pump_v3.entity_activity(kind, "membrane_slot", hosts, xp=np),
        closed.membrane_active,
    )


def test_the_contract_refuses_the_transporter_declaring_its_presence_alone():
    # The built-in transporter as it stands: its kinetics read the law masks, not its presence,
    # so with transporter_present alone false its cycles, heat and work do not vanish.
    with scoped(with_presence(transporter.TRANSPORTER, ALONE)):
        with pytest.raises(ConfigError, match="derivative of transporter_cycles") as caught:
            parse_spec(held_world())
    message = str(caught.value)
    assert "declares presence fields (transporter_present)" in message
    assert "rates' heat" in message and "rates' work" in message
    with scoped(DECLARED):  # All three of its masks: admitted, with no change to its code.
        parse_spec(held_world())


def test_a_presence_field_that_binds_no_bool_mask_is_refused():
    # Plant: F's declaration says fill False and no dtype; the gate ands, so binding refuses a
    # presence field whose array is not bool (the capacity, float).
    loose = {"membrane_slot": (*ALL_THREE["membrane_slot"], "transporter_capacity_fmol_s")}
    with scoped(with_presence(transporter.TRANSPORTER, loose)):
        with pytest.raises(ConfigError, match="transporter_capacity_fmol_s bind float64 arrays"):
            parse_spec(held_world())


# ------------------------------------------------------------------ the channel and face hosts
# `tests.kind.channel_carrier@1`: one channel population carries a declared species outward across
# its patch at a declared rate while its presence mask holds (kind_fixtures' charged carrier, per
# population). Its work is the carried species' electrochemical free-energy change. A kind parses
# against @3's base definition, which holds patches but no populations, so the declaration names
# the population's patch too, and the population is placed at binding (initial).

CHANNEL_CARRIER_KEY = "test_channel_carrier"


def _channel_carrier_parse(entries, base):
    m = base.model
    if set(entries) != {"species", "channel", "membrane", "rate_fmol_s"}:
        raise ConfigError("test_channel_carrier declares species, channel, membrane, rate_fmol_s")
    (patch,) = [x for x in m.membranes if x.id == entries["membrane"]]
    rate = float(entries["rate_fmol_s"])
    return (entries["species"], entries["channel"], patch.id, patch.inside, patch.outside, rate)


def _channel_carrier_to_dict(declaration):
    species, channel, membrane, _, _, rate = declaration
    return dict(species=species, channel=channel, membrane=membrane, rate_fmol_s=rate)


def _channel_carrier_initial(spec, declaration, layout):
    species, channel, membrane, _, _, rate = declaration
    m, k = spec.model, spec.execution.channel_capacity
    slot = [c.id for c in m.channels].index(channel)
    if m.channels[slot].membrane_id != membrane:
        raise ConfigError(f"test_channel_carrier: {channel} is not on {membrane}")
    rates = np.zeros((len(m.species_ids), k))
    rates[m.species_ids.index(species), slot] = rate
    present = np.zeros(k, dtype=bool)
    present[slot] = True
    state = dict(channel_carried=np.zeros_like(rates), channel_carrier_work_pJ=np.zeros(k))
    return state, dict(channel_carrier_rate_fmol_s=rates, channel_carrier_present=present)


def _channel_carrier_flow(p, control, *, xp):
    """Outward flow [species, channel] (fmol/s) of the present population."""
    rate = p.channel_carrier_rate_fmol_s * control.channel_carrier_availability[0]
    return xp.where(p.channel_carrier_present, rate, 0.0)


def _channel_carrier_rates(state, potentials, control, p, *, xp):
    flow = _channel_carrier_flow(p, control, xp=xp)
    ci, co = kind_fixtures._potentials(state, p, xp=xp)
    patch, n = p.channel_membranes, p.active.size
    cell, node = p.membrane_cell[patch], p.membrane_outside[patch]
    mu = R * p.temperature * (xp.log(co[:, node]) - xp.log(ci[:, cell]))  # J/mol, out - in
    mu = mu + p.valence * F * (potentials[n + node] - potentials[cell])
    work = 1e-3 * species_sum(flow * mu, xp=xp)  # pJ/s per population.
    return kind_registry.KindRates(
        cell=-scatter(flow, ci, (cell,), xp=xp),
        outside=scatter(flow, co, (node,), xp=xp),
        derivatives=dict(channel_carried=flow, channel_carrier_work_pJ=work),
        heat_pJ_s=xp.zeros(()),
        work_pJ_s=work,
    )


def _channel_carrier_ledger_terms(state, p, *, xp):
    moved, patch = state.channel_carried, p.channel_membranes
    return dict(
        cell=-scatter(moved, state.amount_increment, (p.membrane_cell[patch],), xp=xp),
        outside=scatter(
            moved, state.extracellular_amount_increment, (p.membrane_outside[patch],), xp=xp
        ),
        work_pJ=state.channel_carrier_work_pJ,
    )


def _channel_carrier_domain(state, p, *, xp):
    return xp.all(xp.isfinite(state.channel_carried)) & xp.all(
        xp.isfinite(state.channel_carrier_work_pJ)
    )


def _channel_carrier_moved_rows(declaration):
    species, _, _, inside, outside, _ = declaration
    return ((species, inside), (species, outside))


CHANNEL_CARRIER = kind_registry.Kind(
    kind_id="tests.kind.channel_carrier@1",
    model_key=CHANNEL_CARRIER_KEY,
    state_axes=(
        ("channel_carried", ("species", "channel_slot")),
        ("channel_carrier_work_pJ", ("channel_slot",)),
    ),
    layout_fields=("channel_carrier_rate_fmol_s", "channel_carrier_present"),
    control_fields=("channel_carrier_availability",),
    parse=_channel_carrier_parse,
    to_dict=_channel_carrier_to_dict,
    structure_entry=lambda declaration: (),
    initial=_channel_carrier_initial,
    control_values=lambda spec, declaration, times: dict(
        channel_carrier_availability=np.ones((len(times), 1))
    ),
    rates=_channel_carrier_rates,
    ledger_terms=_channel_carrier_ledger_terms,
    domain=_channel_carrier_domain,
    moved_rows=_channel_carrier_moved_rows,
    field_axes={
        "channel_carrier_rate_fmol_s": ("species", "channel_slot"),
        "channel_carrier_present": ("channel_slot",),
        "channel_carrier_availability": (),
    },
    partition_roles={"channel_carrier_present": kind_registry.PartitionRole("structural", False)},
    presence={"channel_slot": ("channel_carrier_present",)},
)


def channel_world():
    """The held world without its transporter, the planted kind carrying Y (10 mM on both sides)
    outward through kir_0, a population on membrane_0."""
    raw = held_world()
    m = raw["model"]
    del m[transporter.MODEL_KEY]
    m[CHANNEL_CARRIER_KEY] = dict(
        species="Y", channel="kir_0", membrane="membrane_0", rate_fmol_s=1e-3
    )
    return raw


def test_a_kind_on_channel_slots_moves_exactly_nothing_on_a_closed_patch():
    assert kind_registry.declaration_errors(CHANNEL_CARRIER) == []
    with scoped(CHANNEL_CARRIER):
        spec = parse_spec(channel_world())
        y = list(spec.model.species_ids).index("Y")
        structure, state, p, control = _bound(spec, closer=True)
        opened, _ = _rates(structure, state, p, control)
        assert np.asarray(opened.channel_carried)[y, 0] == 1e-3  # It carries on an open patch.
        closed = _closed(p)  # membrane_0: kir_0's patch.
        rates, _ = _rates(structure, state, closed, control)
        assert np.all(np.asarray(rates.channel_carried) == 0.0)
        assert np.all(np.asarray(rates.channel_carrier_work_pJ) == 0.0)
        # Its moves: the totals equal the same closed world's with the kind absent.
        absent = closed._replace(channel_carrier_present=np.zeros_like(p.channel_carrier_present))
        without, _ = _rates(structure, state, absent, control)
        np.testing.assert_array_equal(rates.amount_increment, without.amount_increment)
        np.testing.assert_array_equal(
            rates.extracellular_amount_increment, without.extracellular_amount_increment
        )
        # Planted: without a closer the gate is absent, and the closed patch keeps it carrying.
        open_structure, _, _, _ = _bound(spec, closer=False)
        leaking, _ = _rates(open_structure, state, closed, control)
        assert np.asarray(leaking.channel_carried)[y, 0] == 1e-3


def test_channel_and_face_slots_read_their_hosts():
    assert set(surface_pump_v3.PRESENCE_SLOT_AXES) == {
        "cell_slot", "extracellular_slot", "membrane_slot", "edge_slot", "channel_slot",
        "face_slot",
    }  # fmt: skip
    kind = SimpleNamespace(axis_hosts={})
    hosts = SimpleNamespace(
        channel_active=np.array([True, True, True, False]),
        channel_membranes=np.array([0, 0, 1, 1]),
        membrane_active=np.array([False, True]),  # Patch 0 closed.
        junction_active=np.zeros(0, dtype=bool),
        active=np.array([True]),
        membrane_cell=np.array([0, 0]),
        membrane_outside=np.array([0, 1]),
        junction_sender=np.zeros(0, dtype=np.int64),
        junction_receiver=np.zeros(0, dtype=np.int64),
        face_active=np.array([True, True, False]),
        face_sender=np.array([0, 1, 0]),
        face_receiver=np.array([1, 2, 2]),
        outside_active=np.array([True, False, True]),  # Outside node 1 closed.
    )
    channels = surface_pump_v3.entity_activity(kind, "channel_slot", hosts, xp=np)
    np.testing.assert_array_equal(channels, [False, False, True, False])
    faces = surface_pump_v3.entity_activity(kind, "face_slot", hosts, xp=np)
    np.testing.assert_array_equal(faces, [False, False, False])
    hosts.outside_active = np.array([True, True, True])
    faces = surface_pump_v3.entity_activity(kind, "face_slot", hosts, xp=np)
    np.testing.assert_array_equal(faces, [True, True, False])  # The third's own slot is closed.
