"""Q2, the presence gate (docs/CORE_SEAMS_DESIGN.md §18 at 931b6606; the lead's ruling of 19
November 2026, the @3 owner's option (a), in the form of B1's pump gate).

Each kind declares one presence field per entity axis (F's contract; here the stand-in attribute
`presence_fields`, ((entity axis, layout field), ...), on a test-local Kind). Where a closer is
declared, @3 ands each presence field with its entities' host activity, through axis_hosts and the
host table, before every rates, readouts and stage-term call (surface_pump_v3.presence_gated), and
binding holds every presence-declaring kind to exact zeros with every entity absent
(_check_presence). The claims, each with its planted error:
- a planted transporter on a closed patch (composition §13.1's 1.41e-5 fmol/s, @3's pump before
  B1) moves exactly nothing, its own rates are exactly zero, and its readouts vanish; without the
  gate the same closed patch keeps cycling;
- a closer-free structure sees its layout unchanged, so its programs are today's;
- an own axis reads its entities' hosts through axis_hosts;
- the built-in transporter as it stands fails the contract with transporter_present as its
  presence field: its cycles, heat and work do not vanish with every entity absent (its kinetics
  read its law masks, not its presence). A planted kind whose rates ignore its presence field is
  refused the same way.
"""

import dataclasses
from types import SimpleNamespace

import numpy as np
import pytest

from cells.definitions.specs import ConfigError, parse_spec
from cells.definitions.surface_pump_v3_spec import control_values
from cells.kinds import transporter
from cells.models import surface_pump_v3
from cells.registry import kind_registry
from tests.unit.test_transporter_kind import held_world, scoped

PRESENCE = (("membrane_slot", "transporter_present"),)


@dataclasses.dataclass(frozen=True, eq=False)
class PresenceKind(kind_registry.Kind):
    """A kind with the stand-in for F's presence declaration."""

    presence_fields: tuple = ()  # ((entity axis, presence layout field), ...)


def with_presence(kind, **over):
    fields = {f.name: getattr(kind, f.name) for f in dataclasses.fields(kind_registry.Kind)}
    return PresenceKind(**{**fields, **over}, presence_fields=PRESENCE)


def _masked_rates(state, potentials, control, p, *, xp):
    """The transporter's rates with every per-patch output zero where no population: the
    planted transporter, which honours its presence field."""
    kr = transporter.rates(state, potentials, control, p, xp=xp)
    present = p.transporter_present
    return kr._replace(
        derivatives={k: xp.where(present, v, 0.0) for k, v in kr.derivatives.items()},
        heat_pJ_s=xp.where(present, kr.heat_pJ_s, 0.0),
        work_pJ_s=xp.where(present, kr.work_pJ_s, 0.0),
    )


PLANTED = with_presence(transporter.TRANSPORTER, rates=_masked_rates)


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


def test_the_planted_transporter_on_a_closed_patch_moves_exactly_nothing():
    with scoped(PLANTED):
        spec = parse_spec(held_world())
        structure, state, p, control = _bound(spec, closer=True)
        closed = _closed(p)
        rates, potentials = _rates(structure, state, closed, control)
        for name in ("transporter_cycles", "transporter_dissipated_energy_pJ"):
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
        for column in PLANTED.readouts(state, read, potentials, control, gated, xp=np):
            assert np.asarray(column)[0] == 0.0
        # Planted: without a closer the gate is absent, and the closed patch keeps cycling.
        open_structure, _, _, _ = _bound(spec, closer=False)
        leaking, _ = _rates(open_structure, state, closed, control)
        assert np.asarray(leaking.transporter_cycles)[0] > 0.0


def test_a_closer_free_structure_keeps_its_layout():
    with scoped(PLANTED):
        spec = parse_spec(held_world())
        structure, _, p, _ = _bound(spec, closer=False)
        assert surface_pump_v3.presence_gated(p, structure, xp=np) is p
        assert surface_pump_v3.presence_gated(p, None, xp=np) is p


def test_an_own_axis_reads_its_entities_hosts_through_axis_hosts():
    with scoped(PLANTED):
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


def test_the_contract_refuses_a_kind_whose_rates_ignore_its_presence():
    # The built-in transporter as it stands: its kinetics read the law masks, not its presence,
    # so with every entity absent its cycles, heat and work do not vanish.
    with scoped(with_presence(transporter.TRANSPORTER)):
        with pytest.raises(ConfigError, match="derivative of transporter_cycles") as caught:
            parse_spec(held_world())
    message = str(caught.value)
    assert "declares presence fields (transporter_present)" in message
    assert "rates' heat" in message and "rates' work" in message
    with scoped(PLANTED):  # The planted transporter honours it, and binds.
        parse_spec(held_world())
