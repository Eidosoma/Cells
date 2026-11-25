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
  it hosts instead of the declared ones, which the same comparison must catch);
- cycle and route laws name their step terms (CORE_SEAMS §18, amended): stage_term,
  material_term, charge_bound and material_bound, each a kernel's name or None after today's
  fields; the passive kind's leak names its charge slope and its neutral law its material bound,
  each a kernel of its own module, and only the proton pump's charge slope besides (planted, each
  refused: an empty name and a non-name in each of the four, on each type);
- a cycle and a route law may declare `forms` "base" (CORE_SEAMS §5.2), a cycle law its general
  form, checked by the form's own errors(), and a binding law its general closure's fields
  (§19 as amended); each is None today (planted, each refused: other forms, a form whose errors()
  reports, a form without errors(), a malformed report, binding forms other than "registry", and
  a non-callable kernel); hosted_laws is the active registry's lookup by interface and host;
- a cycle law whose form carries it may leave its moves empty and its kernels None, the form's
  own errors() then holding, while a law without a form keeps version 1's checks (planted, each
  refused: such a law whose form reports, a formed law with a non-callable kernel, and a law
  without a form missing its moves or a kernel);
- cycle_changes reads a cycle law's change rows as declared, the manifest's one source: version
  1's moves, or its form's changes() rows in the row form's key order, counts and parameter names
  unresolved (planted, each refused at registration, by the reader and by the manifest's: a list
  of rows, a row that is not a mapping, one without its mode, one with an extra key, an unnamed
  role, a fractional and a bool count, an unnamed mode, and a form without changes(); a form whose
  own errors() report is never asked for rows, a route law is not read, and version 1's moves
  refuse a fractional count);
- the ID grammar (registry/ids.py): a piece's ID, an interface's, and what is neither (planted: a
  family outside the cells list, an interface's noun for its word, and each malformed shape).
"""

import dataclasses
import re

import jax
import pytest

from cells.definitions import surface_pump_v3_spec as spec3
from cells.definitions.specs import ConfigError, parse_spec
from cells.kinds import passive_routes, proton_buffer, transporter
from cells.laws.channels import (
    clleak_always_open,
    kv1p1_mh2,
    kv1p2_mh,
    kv1p3_mh,
    kv1p4_mh,
    kv1p6_mh,
)
from cells.laws.cycles import (
    adenylate_kinase,
    cytochrome_c_oxygen_proton_cycle,
    electrogenic_nucleotide_exchange,
    held_reductant_supply,
    nadh_ubiquinone_proton_cycle,
    phosphate_proton_symport,
    potassium_proton_exchange,
    proton_coupled_atp_synthesis_cycle,
    ubiquinol_cytochrome_c_proton_cycle,
)
from cells.laws.cycles import na2_anion_symport_diagram as symport2
from cells.laws.cycles import na_anion_symport_factored as symport
from cells.laws.cycles import sodium_calcium_exchange_symmetric_barrier as exchange
from cells.laws.junctions import junction_series_gates
from cells.laws.routes import passive_permeation
from cells.laws.transport import proton_leak, proton_leak_v2
from cells.models import inner_laws, surface_pump_v3
from cells.registry import declarations, ids, laws
from tests.unit.test_passive_routes_kind import closed_pair, route
from tests.unit.test_transporter_kind import held_world, population
from validation.tissue import composite_crossrev as crossrev
from validation.tissue import pump_water_fixtures as water_fixtures

HOST = inner_laws.HOST
KV1P5 = inner_laws.CHANNEL_LAWS["kv1p5_mh@1"]


def planted_laws():
    """One planted law of each cells interface whose host a world below can declare, all in the
    tests namespace: a gated channel law on @3 (code 99, reserved for plants), a cycle law on the
    transporter, a route law on the passive routes and a binding law on the proton buffer."""

    def kernel(*args, **kwargs):
        raise AssertionError("an undeclared law's kernel is never called")

    return (
        laws.ChannelLaw(
            "tests.planted_channel@1",
            99,
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
    todays = {law_id: inner_laws.CHANNEL_LAWS[law_id] for law_id in spec3.TODAYS_CHANNEL_LAWS}
    series = junction_series_gates.LAW_ID  # FR-30's cited series law (D262), beside today's.
    junctions = {k: v for k, v in inner_laws.JUNCTION_LAWS.items() if k != series}
    tables = {
        laws.CHANNEL_LAW: todays,
        laws.JUNCTION_LAW: junctions,
        laws.CYCLE_LAW: inner_laws.PUMP_LAWS,
        laws.ROUTE_LAW: inner_laws.ROUTE_LAWS,
    }
    # @3 also hosts the Kv1 pilot's five, cited laws registered since the Kv1 trigger, and the
    # always-open chloride leak (D228 item 3); and FR-30's series gates (D262).
    kv1 = {m.LAW_ID: m.LAW for m in (kv1p1_mh2, kv1p2_mh, kv1p3_mh, kv1p4_mh, kv1p6_mh)}
    kv1[clleak_always_open.LAW_ID] = clleak_always_open.LAW
    extra = {laws.CHANNEL_LAW: kv1, laws.JUNCTION_LAW: {series: junction_series_gates.LAW}}
    assert inner_laws.JUNCTION_LAWS[series] is junction_series_gates.LAW
    series_law = junction_series_gates.LAW
    assert series_law.provenance == "cited" and not series_law.errors()
    for interface, table in tables.items():
        assert table and all(type(law).interface == interface for law in table.values())
        assert all(isinstance(law, laws.Law) and law.host == HOST for law in table.values())
        assert all(law.provenance == "parity" and not law.errors() for law in table.values())
        hosted = {**table, **extra.get(interface, {})}
        assert laws.active().laws(interface, HOST) == tuple(
            law for _, law in sorted((laws.qualified(k), v) for k, v in hosted.items())
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
        # A route law's reads (MT-1b's leak @2, face plan item 3): stage-read IDs, () by default.
        "its reads are a tuple of stage-read IDs": dataclasses.replace(route_law, reads=("",)),
    }
    assert route_law.reads == () and not route_law.errors()
    # A third part, the family's, is admitted in a law's and a host's ID, a fourth is not, and an
    # interface keeps its two (D345).
    three = dict(law_id="tests.binding.planted@1", host="tests.kind.planted@1")
    assert dataclasses.replace(binding, **three).errors() == []
    for name, value in three.items():
        four = {**three, name: value.replace("tests.", "tests.a.")}
        assert len(dataclasses.replace(binding, **four).errors()) == 1, name
    interface = type("ThreePart", (laws.Law,), {"interface": "tests.binding.planted_law@1"})
    assert interface(**three).errors() == [
        "its type declares a namespaced interface ID with its major"
    ]
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


def test_cycle_and_route_laws_name_their_step_terms():
    # After today's fields, so today's positional call sites keep their meaning.
    assert [f.name for f in dataclasses.fields(laws.CycleLaw) if not f.kw_only] == [
        "law_id",
        "moves",
        "fuel_kinds",
        "kinetics",
        "domain_valid",
        "reads",
        "stage_term",
        "loop_term",
        *laws.STEP_TERMS[1:],
        "forms",
        "cycle",
    ]
    assert [f.name for f in dataclasses.fields(laws.RouteLaw) if not f.kw_only] == [
        "law_id",
        "hosts",
        "basis",
        *laws.STEP_TERMS,
        "forms",
        "reads",  # MT-1b's leak @2 (face plan item 3), defaulted to () last.
    ]
    _, cycle, route_law, _ = planted_laws()
    for law in (cycle, route_law):
        assert all(getattr(law, name) is None for name in laws.STEP_TERMS) and law.errors() == []
        for name in laws.STEP_TERMS:
            for value in ("", 1):  # Planted: an empty name and a non-name.
                with pytest.raises(ValueError, match=f"its {name} is named, or None"):
                    laws.LawRegistry().register(dataclasses.replace(law, **{name: value}))
            named = dataclasses.replace(law, **{name: "a_kernel"})
            assert laws.LawRegistry().register(named) is named
    # The passive kind's two declarations, each a kernel of its law's own module.
    assert callable(getattr(proton_leak, passive_routes.LEAK.stage_term))
    assert getattr(proton_leak_v2, passive_routes.LEAK_V2.stage_term) is proton_leak.conductance_S
    assert callable(getattr(passive_permeation, passive_routes.NEUTRAL.material_bound))
    declared = {
        (law.law_id, name): getattr(law, name)
        for law in laws.active()._laws.values()
        if type(law).interface in (laws.CYCLE_LAW, laws.ROUTE_LAW)
        for name in laws.STEP_TERMS
        if getattr(law, name) is not None
    }
    assert declared == {
        (passive_routes.LEAK_LAW_ID, "stage_term"): "conductance_S",
        (passive_routes.LEAK_V2_LAW_ID, "stage_term"): "conductance_S",  # @1's kernel (item 3).
        (passive_routes.LAW_ID, "material_bound"): "bound_rate_per_s",
        (passive_routes.RECTIFIER_LAW_ID, "stage_term"): "slope_conductance_S",
        (passive_routes.CHARGED_LAW_ID, "stage_term"): "conductance_S",  # FR-15 P2.
        (passive_routes.CHARGED_LAW_ID, "material_term"): "material_slope_per_s",
        (transporter.PROTON.law_id, "stage_term"): "electrogenic_conductance_S",  # The kind's.
    }


# ------------------------------------------------------------------ the ID grammar


@pytest.mark.parametrize(
    ("value", "expected"),  # A piece's parts, "interface", or None: neither.
    [
        ("cells.channel.a_law@1", ("cells", "channel", "a_law", 1)),
        ("cells.operator.an_operator@12", ("cells", "operator", "an_operator", 12)),
        ("acme.any_word.a_law@1", ("acme", "any_word", "a_law", 1)),  # Its families are its own.
        ("cells.channel.a_mM_law@1", ("cells", "channel", "a_mM_law", 1)),  # A name's, as written.
        ("cells.potential_set.a_set@2", ("cells", "potential_set", "a_set", 2)),  # A sub-law's.
        ("cells.Channel.a_law@1", None),
        ("cells.any_word.a_law@1", None),  # The cells families are a closed list.
        ("cells.channel_law.a_law@1", None),  # An interface's noun is not its word.
        ("cells.a_law@1", "interface"),
        ("acme.a_law@1", "interface"),
        ("a_law@1", None),
        ("cells.channel.a_law@0", None),
        ("cells.channel.a_law@01", None),
        ("cells.channel.a_law", None),
        ("cells.channel.A_law@1", None),
        ("cells.channel.1_law@1", None),
        ("cells.channel.a.law@1", None),
        ("cells.channel.a_law@1\n", None),
        (None, None),
    ],
)
def test_the_id_grammar(value, expected):
    assert ids.interface(value) is (expected == "interface")
    assert ids.piece(value) is isinstance(expected, tuple)
    if isinstance(expected, tuple):
        assert ids.parts(value) == expected and ids.piece(value, family=expected[1])
        assert not ids.piece(value, family="kind")
    else:
        with pytest.raises(ValueError, match="is not namespace.family.name@major"):
            ids.parts(value)


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
        symport.DECLARED_ID: symport.LAW,
        symport2.DECLARED_ID: symport2.LAW,
        exchange.DECLARED_ID: exchange.LAW,
        **{  # The mitochondrion's inner-membrane laws (the kinds owner's, from its appendix).
            m.DECLARED_ID: m.LAW
            for m in (
                nadh_ubiquinone_proton_cycle,
                ubiquinol_cytochrome_c_proton_cycle,
                cytochrome_c_oxygen_proton_cycle,
                proton_coupled_atp_synthesis_cycle,
                electrogenic_nucleotide_exchange,
                phosphate_proton_symport,
                potassium_proton_exchange,
                held_reductant_supply,  # The matrix's NADH supply (the second head).
                adenylate_kinase,  # The intermembrane space's kinase (the second head).
            )
        },
    }
    assert passive_routes.hosted_laws() == {
        passive_routes.LAW_ID: passive_routes.NEUTRAL,
        passive_routes.LEAK_LAW_ID: passive_routes.LEAK,
        passive_routes.RECTIFIER_LAW_ID: passive_routes.RECTIFIER,
        passive_routes.CHARGED_LAW_ID: passive_routes.CHARGED,  # FR-15 P2.
        passive_routes.LEAK_V2_LAW_ID: passive_routes.LEAK_V2,  # MT-1b's face plan, item 3.
    }
    builtin = list(transporter.hosted_laws())  # Before the planted scope.
    planted = planted_laws()
    elsewhere = dataclasses.replace(planted[1], law_id="tests.elsewhere@1", host=HOST)
    with laws.scope(laws.BUILTIN.extended(*planted, elsewhere)):
        hosted = transporter.hosted_laws()  # Found with no edit to the kind: interface and host.
        assert list(hosted) == sorted([*builtin, "tests.planted_cycle@1"])  # Canonical: sorted IDs.
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
        rest = ", ".join(transporter.hosted_laws())  # Sorted, without the proton law.
        with pytest.raises(ConfigError, match=f"law is one of {re.escape(rest)}$"):
            parse_spec(held_world(proton))
    rest = [law for law in passive_routes.hosted_laws() if law != passive_routes.LAW_ID]  # Bare.
    with laws.scope(without(passive_routes.LAW_ID)):
        with pytest.raises(ConfigError, match=f"law must be one of {re.escape(', '.join(rest))}$"):
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


PLANTED_ROWS = ({"role": "role@in", "per_cycle": 1, "mode": "planted"},)


class PlantedForm:
    """A planted general form: its own errors() reports `problems`, and its changes() gives
    `rows`."""

    def __init__(self, *problems, rows=PLANTED_ROWS):
        self.problems = list(problems)
        self.rows = rows

    def errors(self):
        return self.problems

    def changes(self):
        return self.rows


def test_forms_a_cycle_form_and_a_general_closure_are_declared_and_checked():
    _, cycle, route_law, binding = planted_laws()
    for law in (cycle, route_law):
        assert law.forms is None
        assert dataclasses.replace(law, forms="base").errors() == []
        assert "its forms are" in " ".join(dataclasses.replace(law, forms="free").errors())
    assert cycle.cycle is None
    form = PlantedForm()
    assert laws.LawRegistry().register(dataclasses.replace(cycle, cycle=form)).cycle is form
    for planted_form, words in (
        (PlantedForm("its modes share an edge"), "its cycle: its modes share an edge"),
        (object(), "a form with its own errors()"),
        (type("Bad", (), {"errors": lambda self: "one string"})(), "returns a list of reasons"),
    ):
        with pytest.raises(ValueError, match=words):
            laws.LawRegistry().register(dataclasses.replace(cycle, cycle=planted_form))
    assert (binding.forms, binding.free_energy, binding.envelope, binding.free_amounts) == (
        (None,) * 4
    )
    general = dataclasses.replace(
        binding, forms="registry", free_energy=len, envelope=len, free_amounts=len
    )
    assert general.errors() == []
    for changes, words in (
        (dict(forms="base"), 'its forms are "registry"'),
        (dict(free_amounts="free_proton"), "its free_amounts is callable"),
        (dict(envelope=1.0), "its envelope is callable"),
    ):
        with pytest.raises(ValueError, match=words):
            laws.LawRegistry().register(dataclasses.replace(binding, **changes))
    hosted = laws.hosted_laws(laws.CHANNEL_LAW, HOST)
    assert hosted == laws.active().laws(laws.CHANNEL_LAW, HOST) and KV1P5 in hosted


def test_a_cycle_form_carries_its_law_and_version_1_keeps_its_checks():
    _, cycle, _, _ = planted_laws()
    host = transporter.KIND_ID
    carried = laws.CycleLaw("tests.planted_carried_cycle@1", cycle=PlantedForm(), host=host)
    assert (carried.moves, carried.kinetics, carried.domain_valid) == ((), None, None)
    assert carried.errors() == [] and laws.LawRegistry().register(carried) is carried
    # Planted, each refused: the carried law's form reporting, a non-callable kernel beside a form,
    # and version 1's law without its moves or a kernel.
    for law, words in (
        (dataclasses.replace(carried, cycle=PlantedForm("a mode without a cycle")), "its cycle:"),
        (dataclasses.replace(carried, kinetics="kinetics"), "its kinetics is callable, or None"),
        (dataclasses.replace(cycle, moves=()), "its moves are (role, count) pairs"),
        (dataclasses.replace(cycle, kinetics=None), "its kinetics is callable"),
        (laws.CycleLaw("tests.planted_bare_cycle@1", host=host), "its moves are"),
    ):
        with pytest.raises(ValueError, match=re.escape(words)):
            laws.LawRegistry().register(law)


class ReportingForm(PlantedForm):
    """A planted form whose own errors() report: asking it for rows fails the test."""

    def changes(self):
        raise AssertionError("a form that breaks its own contract is never asked for rows")


def test_cycle_changes_reads_a_cycle_law_s_declared_rows_from_one_source():
    _, cycle, route_law, _ = planted_laws()
    # Version 1's law: its moves, each count as declared (a parameter's name stays a name).
    assert laws.cycle_changes(cycle) == ({"role": "role", "per_cycle": -1},)
    named = dataclasses.replace(cycle, moves=(("substrate", "-n_coupled"), ("product", 2)))
    assert laws.cycle_changes(named) == (
        {"role": "substrate", "per_cycle": "-n_coupled"},
        {"role": "product", "per_cycle": 2},
    )
    # A form-carried law: its form's rows as declared, in the row form's key order.
    rows = (
        {"mode": "coupled", "role": "substrate@in", "per_cycle": "-n_coupled"},
        {"role": "product@out", "per_cycle": 2, "mode": "coupled"},
    )
    host = transporter.KIND_ID
    carried = laws.CycleLaw(
        "tests.planted_carried_cycle@1", cycle=PlantedForm(rows=rows), host=host
    )
    assert laws.LawRegistry().register(carried) is carried
    read = laws.cycle_changes(carried)
    assert read == rows and [list(row) for row in read] == [["role", "per_cycle", "mode"]] * 2
    assert declarations._cycle_changes(carried) == list(read)  # The manifest's, from one source.
    with pytest.raises(TypeError, match="reads a CycleLaw"):
        laws.cycle_changes(route_law)
    with pytest.raises(ValueError, match=re.escape("its moves are (role, count) pairs")):
        laws.LawRegistry().register(dataclasses.replace(cycle, moves=(("role", 1.5),)))
    # A form whose own errors() report is refused for them and never asked for its rows.
    with pytest.raises(ValueError, match="its cycle: a mode without a cycle"):
        laws.LawRegistry().register(
            dataclasses.replace(carried, cycle=ReportingForm("a mode without a cycle"))
        )
    # Planted, each refused at registration, by the reader and by the manifest's reader.
    good, malformed = rows[1], "returns a tuple of {role, per_cycle, mode} rows"
    for form, words in (
        (PlantedForm(rows=list(rows)), malformed),  # A list, not a tuple.
        (PlantedForm(rows=(("role", "per_cycle", "mode"),)), malformed),  # Names, not a mapping.
        (PlantedForm(rows=({"role": "product@out", "per_cycle": 2},)), malformed),  # No mode.
        (PlantedForm(rows=(dict(good, sign="+"),)), malformed),  # An extra key.
        (PlantedForm(rows=(dict(good, role=""),)), malformed),
        (PlantedForm(rows=(dict(good, per_cycle=1.5),)), malformed),
        (PlantedForm(rows=(dict(good, per_cycle=True),)), malformed),
        (PlantedForm(rows=(dict(good, mode=None),)), malformed),
        (type("ErrorsOnly", (), {"errors": lambda self: []})(), "a form with its own changes()"),
    ):
        planted = dataclasses.replace(carried, cycle=form)
        for read_it in (
            laws.LawRegistry().register,
            laws.cycle_changes,
            declarations._cycle_changes,
        ):
            with pytest.raises(ValueError, match=re.escape(words)):
                read_it(planted)
