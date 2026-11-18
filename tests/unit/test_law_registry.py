"""The law template and the law registry (docs/CORE_SEAMS_DESIGN.md §8.1, §8.3; seam F).

Each claim is checked once, with a planted error it must catch (D187):
- today's ChannelLaw, JunctionLaw, PumpLaw and RouteLaw are instances of the template, with
  their fields kept; the template refuses a malformed declaration at registration (planted: a
  cited law without its citation, a reserved B8 field, a type that is not its interface's);
- a duplicate ID is refused whatever its spelling, a built-in cells ID cannot be rebound in
  another registry, and a host's channel codes stay distinct (planted: each of the three);
- kinds and @3 find their laws in the active registry by interface and host, never in a module
  tuple (planted: a registry without a law a module tuple would still list; a law of a kind's
  interface that its version-1 layout has no path for);
- a registered but undeclared law changes no program (planted: a consumer that reads every law
  it hosts instead of the declared ones, which the same comparison must catch).
"""

import dataclasses

import jax
import pytest

from cells.definitions.specs import ConfigError, parse_spec
from cells.kinds import passive_routes, proton_buffer, transporter
from cells.models import inner_laws, surface_pump_v3
from cells.registry import laws
from tests.unit.test_passive_routes_kind import closed_pair, route
from tests.unit.test_transporter_kind import held_world, population
from validation.tissue import composite_crossrev as crossrev
from validation.tissue import pump_water_fixtures as water_fixtures

HOST = inner_laws.HOST
KV1P5 = inner_laws.CHANNEL_LAWS["kv1p5_mh@1"]


def planted_laws():
    """One planted law of each cells interface whose host a world below can declare, all in the
    tests namespace: a gated channel law on @3 (code 5), a cycle law on the transporter, a route
    law on the passive routes and a binding law on the proton buffer."""

    def kernel(*args, **kwargs):
        raise AssertionError("an undeclared law's kernel is never called")

    return (
        laws.ChannelLaw(
            "tests.planted_channel@1",
            5,
            ("m", "h"),
            (("K", 1, 1.0),),
            KV1P5.voltage_domain_V,
            KV1P5.rk4_step_s,
            KV1P5.kinetics,  # Traced like Kv1.5's if a consumer reads it: the control's teeth.
            KV1P5.opening,
            host=HOST,
        ),
        laws.CycleLaw(
            "tests.planted_cycle@1", (("role", -1),), (), kernel, kernel, host=transporter.KIND_ID
        ),
        laws.RouteLaw(
            "tests.planted_route@1", ("membrane",), "a planted route", host=passive_routes.KIND_ID
        ),
        laws.BindingLaw("tests.planted_binding@1", ("proton",), kernel, host=proton_buffer.KIND_ID),
    )


def without(*law_ids):
    """BUILTIN's laws less `law_ids`, in a new registry (cells laws as BUILTIN's own objects)."""
    out = laws.LawRegistry()
    for key, law in sorted(laws.active()._laws.items()):
        if key not in {laws.qualified(i) for i in law_ids}:
            out.register(law)
    return out


# ------------------------------------------------------------------ the template (§8.1)


def test_todays_declarations_are_template_instances_with_their_fields_kept():
    assert laws.PumpLaw is laws.CycleLaw and inner_laws.PumpLaw is laws.CycleLaw
    tables = {
        laws.CHANNEL_LAW: inner_laws.CHANNEL_LAWS,
        laws.JUNCTION_LAW: inner_laws.JUNCTION_LAWS,
        laws.CYCLE_LAW: inner_laws.PUMP_LAWS,
        laws.ROUTE_LAW: inner_laws.ROUTE_LAWS,
    }
    for interface, table in tables.items():
        assert table and all(type(law).interface == interface for law in table.values())
        assert all(isinstance(law, laws.Law) and law.host == HOST for law in table.values())
        assert all(law.provenance == "parity" and not law.errors() for law in table.values())
        assert laws.active().laws(interface, HOST) == tuple(
            law for _, law in sorted((laws.qualified(k), v) for k, v in table.items())
        )
    # Positional order kept: today's call sites construct each type positionally.
    assert [f.name for f in dataclasses.fields(laws.ChannelLaw) if not f.kw_only][:9] == [
        "law_id",
        "code",
        "gates",
        "permeant",
        "voltage_domain_V",
        "rk4_step_s",
        "kinetics",
        "opening",
        "stage_term",
    ]
    assert dataclasses.replace(KV1P5, host=HOST) == KV1P5


def test_the_template_refuses_a_malformed_declaration():
    registry = laws.LawRegistry()
    channel, cycle, route_law, binding = planted_laws()
    cases = {
        "a cited law gives its source as a Citation": dataclasses.replace(
            cycle, provenance="cited"
        ),
        "its provenance is one of": dataclasses.replace(cycle, provenance="moved"),
        "B8's fields are reserved": dataclasses.replace(route_law, represents="a reference"),
        "its host is the ID": dataclasses.replace(binding, host="the buffer"),
        "its law_id is": dataclasses.replace(binding, law_id="Planted Binding"),
        "a gated law gives its kinetics and opening": dataclasses.replace(channel, opening=None),
        "its moves are": dataclasses.replace(cycle, moves=(("role", 1.5),)),
    }
    for reason, law in cases.items():
        with pytest.raises(ValueError, match=reason):
            registry.register(law)

    @dataclasses.dataclass(frozen=True)
    class Pretender(laws.RouteLaw):  # Claims the channel interface on a route law's fields.
        interface = laws.CHANNEL_LAW

    with pytest.raises(ValueError, match="not a cells interface of its type"):
        registry.register(Pretender("tests.pretender@1", ("membrane",), "x", host=HOST))
    with pytest.raises(ValueError, match="built on the template"):
        registry.register(object())
    cited = laws.Citation("a source", "its section", "no numbers taken")
    assert registry.register(dataclasses.replace(cycle, provenance="cited", source=cited))
    assert not registry._laws.keys() - {"tests.planted_cycle@1"}  # Only the admitted one.


# ------------------------------------------------------------------ the registry (§8.3)


def test_a_duplicate_id_is_refused_whatever_its_spelling():
    registry = laws.BUILTIN
    assert registry.register(KV1P5) is KV1P5  # The same object again: a no-op.
    for spelling in ("kv1p5_mh@1", "cells.kv1p5_mh@1"):  # Bare and namespaced: one ID.
        with pytest.raises(ValueError, match="already registered"):
            registry.register(dataclasses.replace(KV1P5, law_id=spelling, code=9))
    planted = planted_laws()
    extended = laws.BUILTIN.extended(*planted)
    with pytest.raises(ValueError, match="already registered"):
        extended.register(dataclasses.replace(planted[1], fuel_kinds=("other@1",)))
    # One object per cells ID in every registry: a rebinding of a built-in is refused, so caches
    # keyed on law IDs never mix two declarations under one ID.
    with pytest.raises(ValueError, match="only as BUILTIN's own declaration"):
        laws.LawRegistry().register(dataclasses.replace(KV1P5, rk4_step_s=1e-6))
    with pytest.raises(ValueError, match="only as BUILTIN's own declaration"):
        laws.LawRegistry().register(dataclasses.replace(planted[2], law_id="cells.planted@1"))
    with pytest.raises(ValueError, match="code 0 is cells.kv1p5_mh@1's"):  # Codes distinct.
        extended.register(dataclasses.replace(planted[0], law_id="tests.second@1", code=0))
    assert laws.qualified("tests.planted_channel@1") in extended._laws
    assert "tests.planted_channel@1" not in laws.BUILTIN  # extended() leaves its source alone.


def test_kinds_and_the_inner_model_find_their_laws_by_interface_and_host():
    assert transporter.hosted_laws() == {
        transporter.NEUTRAL_LAW: transporter.NEUTRAL,
        transporter.PROTON_LAW: transporter.PROTON,
    }
    assert passive_routes.hosted_laws() == {
        passive_routes.LAW_ID: passive_routes.NEUTRAL,
        passive_routes.LEAK_LAW_ID: passive_routes.LEAK,
    }
    planted = planted_laws()
    elsewhere = dataclasses.replace(planted[1], law_id="tests.elsewhere@1", host=HOST)
    with laws.scope(laws.BUILTIN.extended(*planted, elsewhere)):
        hosted = transporter.hosted_laws()  # Found with no edit to the kind: interface and host.
        assert list(hosted) == [*transporter.VERSION_1_LAWS, "tests.planted_cycle@1"]
        assert "tests.planted_route@1" in passive_routes.hosted_laws()
        # Version 1 dispatches its two laws by name: another law of its own is refused, never run
        # as the proton law.
        with pytest.raises(
            ConfigError, match="version 1's layout runs .*, not tests.planted_cycle@1"
        ):
            parse_spec(held_world(population(law="tests.planted_cycle@1")))
        with pytest.raises(ConfigError, match="version 1 runs .*, not tests.planted_route@1"):
            parse_spec(closed_pair(routes=[dict(route("r", 1e-9), law="tests.planted_route@1")]))
    # The planted errors a module tuple would miss: each law is admitted only while registered.
    proton = population(law=transporter.PROTON_LAW, role="H")
    with laws.scope(without(transporter.PROTON_LAW)):
        with pytest.raises(ConfigError, match="law is one of cells.atp_driven"):
            parse_spec(held_world(proton))
    with laws.scope(without(passive_routes.LAW_ID)):
        with pytest.raises(ConfigError, match="law must be one of proton_constant_field_leak@1$"):
            parse_spec(closed_pair())
    parse_spec(closed_pair())  # Both admitted under BUILTIN.
    structure = surface_pump_v3.structure(parse_spec(water_fixtures.heredity_cell("D")).model)
    assert structure.channel_laws == tuple(
        inner_laws.CHANNEL_LAWS[law] for law in structure.declared_channel_laws
    )
    with laws.scope(without("nav1p2_m3h_regularized@1")):
        with pytest.raises(ValueError, match="Undeclared laws in an inner structure"):
            dataclasses.replace(structure)


# ------------------------------------------------------------------ registered but undeclared


def programs(raw):
    """(spec, implementation, {program: (jaxpr text, constants)}) of a world, traced afresh."""
    jax.clear_caches()
    spec, model, arrays = crossrev._setup(raw)
    traced = crossrev._traced(spec, model, arrays)
    return spec, model, {k: (str(v), crossrev.const_record(v)) for k, v in traced.items()}


def leaky_channel_laws(self):
    """The planted consumer: every gated channel law @3 hosts, not the declared ones."""
    return tuple(law for law in inner_laws._hosted(laws.CHANNEL_LAW) if law.gated)


def test_a_registered_but_undeclared_law_changes_no_program(monkeypatch):
    jax.config.update("jax_enable_x64", True)
    worlds = {
        "heredity": water_fixtures.heredity_cell("D", end_time=0.01),
        "fr4_development": crossrev.kinds_worlds()["fr4_development"],
    }
    extended = laws.BUILTIN.extended(*planted_laws())
    for name, raw in worlds.items():
        spec, model, today = programs(raw)
        with laws.scope(extended):
            again, built, registered = programs(raw)
        assert again == spec and again.to_dict() == spec.to_dict(), name
        assert built is model and built.structure == model.structure, name
        assert registered == today, name
    # The planted consumer: the same comparison sees the undeclared law in its program.
    monkeypatch.setattr(inner_laws.InnerStructure, "channel_laws", property(leaky_channel_laws))
    _, _, today = programs(worlds["heredity"])
    with laws.scope(extended):
        _, _, registered = programs(worlds["heredity"])
    assert registered["checked_step"][0] != today["checked_step"][0]
