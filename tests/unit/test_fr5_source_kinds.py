"""FR-5's source kinds (the FR-4/FR-5 note's §16; INNER §7.4 (l), (n)): cells.kind.patch_damage@1 and
cells.kind.ph_condition@1.

Their declarations, the damage's schedules (`damage_controls`, the core's Schedule) and their
refusals through the real parse (FR-4's development world with the kinds declared), and their
hooks on the host: the damage's exact step at the step's held control (composition, the
equilibrium, [0, 1] at any step), the derivative the tableau carries, and both kinds' factors for
the routing door. The engine's runs are test_fr5_source_kinds_engine.py and
test_fr5_world_engine.py.

The third source kind, cells.kind.species_condition@1 (G-5), is declared in the same world: its
declaration's refusals by name, its stateless layout, structure entry and view, its read of the free
form at a buffered node, and its feedback hooks, whose planted errors are an inhibition's sign
dropped, the derivative in n for the one in ln n, and a pair named twice. Its engine rows are
test_species_condition_kind.py; its law's are test_hill_factors.py.
"""

import copy
import dataclasses
import math
from functools import partial
from types import SimpleNamespace

import jax
import jax.numpy as jnp
import numpy as np
import pytest

from cells.definitions.specs import ConfigError, parse_spec
from cells.definitions.surface_pump_v3_spec import control_values
from cells.kinds import patch_damage as damage
from cells.kinds import ph_condition as condition
from cells.kinds import species_condition as species
from cells.laws.reactions import hill_product_factor as product
from cells.laws.reactions import ph_condition as phc
from cells.laws.reactions import rapid_proton_buffer as closure
from cells.laws.transport import patch_damage as law
from cells.registry import kind_registry
from cells.registry import laws as law_registry
from cells.registry.kind_registry import declared_schedule
from validation.compartment_ph_engine import definitions as defs

DAMAGE = dict(id="damage_0", patch=defs.BOUNDING, law="cells.damage.bounding_patch_damage@1",
              initial_damage=0.25, injury_rate_per_s=1.0, resealing_rate_per_s=0.05)
CONDITION = dict(
    id="acid_0",
    node=defs.LUMEN,
    law="cells.transfer_factor.ph_conditioned_factor@1",
    ph50=5.5,
    slope=4.0,
)
SCHEDULE = [dict(damage_id="damage_0",
                 injury=[dict(time=0.0, value=0.0), dict(time=0.25, value=1.0),
                         dict(time=0.5, value=0.0)],
                 resealing=[dict(time=0.0, value=0.0), dict(time=0.5, value=1.0)])]


def world(damages=(DAMAGE,), conditions=(CONDITION,), schedule=None):
    """FR-4's development world (1 s) with the source kinds declared (no route reads them)."""
    d = defs.development_world(defs.fr4_world())
    d["experiment"]["end_time"] = 1.0
    d["experiment"]["observation_times"] = [0.0, 1.0]
    d["execution"]["max_steps"] = 1008
    if damages is not None:
        d["model"]["patch_damage"] = [copy.deepcopy(x) for x in damages]
    if conditions is not None:
        d["model"]["ph_conditions"] = [copy.deepcopy(x) for x in conditions]
    if schedule is not None:
        d["experiment"]["damage_controls"] = copy.deepcopy(schedule)
    return d


def refused(match, **changes):
    with pytest.raises(ConfigError, match=match):
        parse_spec(world(**changes))


# ------------------------------------------------------------------------ declarations


def test_both_kinds_parse_round_trip_and_append_their_fields():
    spec = parse_spec(world())
    kinds = dict(spec.model.kinds)
    (d,) = kinds[damage.KIND_ID]
    (c,) = kinds[condition.KIND_ID]
    assert d == damage.Damage("damage_0", defs.BOUNDING, 0.25, 1.0, 0.05)
    assert c == condition.Condition("acid_0", defs.LUMEN, 5.5, 4.0, "H")
    assert damage.parse(damage.to_dict(kinds[damage.KIND_ID]), spec) == kinds[damage.KIND_ID]
    assert condition.parse(condition.to_dict(kinds[condition.KIND_ID]), spec) == kinds[
        condition.KIND_ID]
    # The routing door's source hooks, registered (§7.4 (n)).
    for kind, sources in ((damage.PATCH_DAMAGE, ("damage_0",)),
                          (condition.PH_CONDITION, ("acid_0",))):
        assert kind.factor_sources(dict(spec.model.kinds)[kind.kind_id]) == sources
        assert kind.factors is not None and kind.routed_controls is None
    from cells.registry.models import get_model

    model = get_model(spec.model)
    assert "patch_damage" in model.STATE_TYPE._fields
    state, p = model.initial_values(spec)
    bounding = [m.id for m in spec.model.membranes].index(defs.BOUNDING)
    assert float(state.patch_damage[bounding]) == 0.25
    assert np.count_nonzero(state.patch_damage) == 1
    assert list(p.patch_damage_source_slot) == [bounding]
    nodes = [c.id for c in spec.model.cells] + [o.id for o in spec.model.extracellular]
    assert list(p.ph_condition_node) == [nodes.index(defs.LUMEN)]


@pytest.mark.parametrize("change, match", [
    (dict(patch="nowhere"), "unknown membrane patch"),
    (dict(law="tests.damage.other@1"), "law is cells.damage.bounding_patch_damage@1"),
    (dict(initial_damage=1.5), r"lies in \[0, 1\]"),
    (dict(initial_damage=-0.1), "initial_damage must be finite and nonnegative"),
    (dict(resealing_rate_per_s=-1.0), "resealing_rate_per_s must be finite and nonnegative"),
    (dict(injury_rate_per_s=float("nan")), "injury_rate_per_s must be finite"),
    (dict(id=defs.LUMEN), "unique among the model's IDs"),
])
def test_a_damage_entity_outside_its_contract_is_refused(change, match):
    refused(match, damages=(dict(DAMAGE, **change),))


def test_one_damage_per_patch_unique_ids_and_a_nonempty_list():
    refused("already carries a damage", damages=(DAMAGE, dict(DAMAGE, id="damage_1")))
    refused("unique", damages=(DAMAGE, dict(DAMAGE, patch=defs.PLASMA)))
    refused("non-empty list", damages=())
    refused("missing", damages=({k: v for k, v in DAMAGE.items() if k != "initial_damage"},))


@pytest.mark.parametrize("change, match", [
    (dict(node="nowhere"), "unknown node"),
    (dict(law="cells.kind.ph_condition@1"), "law is cells.transfer_factor.ph_conditioned_factor@1"),
    (dict(slope=0.0), "slope"),
    (dict(slope=-4.0), "slope"),
    (dict(ph50=float("inf")), "ph50"),
    (dict(proton="Q"), "unknown proton row"),
    (dict(proton="Cl"), "valence"),
    (dict(proton="K"), "closure's proton row"),
    (dict(id=defs.BOUNDING), "unique among the model's IDs"),
])
def test_a_condition_outside_its_contract_is_refused(change, match):
    refused(match, conditions=(dict(CONDITION, **change),))


def test_an_undeclared_source_kind_is_absent():
    spec = parse_spec(world(damages=None, conditions=None))
    assert not {damage.KIND_ID, condition.KIND_ID} & set(dict(spec.model.kinds))
    from cells.registry.models import get_model

    fields = get_model(spec.model).STATE_TYPE._fields
    assert not any(f.startswith("patch_damage") for f in fields)
    refused("damage_controls", damages=None, schedule=SCHEDULE)  # An undeclared kind's key.


# ------------------------------------------------------------------------ the schedules


def test_the_schedules_are_the_cores_with_breakpoints_in_the_change_times():
    spec = parse_spec(world(schedule=SCHEDULE))
    schedule = declared_schedule(spec, damage.KIND_ID)
    assert schedule.names == ("damage_0.injury", "damage_0.resealing")
    assert dict(schedule.series) == {"damage_0.injury": ((0.0, 0.0), (0.25, 1.0), (0.5, 0.0)),
                                     "damage_0.resealing": ((0.0, 0.0), (0.5, 1.0))}
    times = [c.time for c in spec.experiment.changes]
    assert {0.25, 0.5} <= set(times)
    bounding = [m.id for m in spec.model.membranes].index(defs.BOUNDING)
    table = control_values(spec, [0.0, 0.2, 0.25, 0.4999, 0.5, 0.9])
    assert list(table.patch_damage_injury[:, bounding]) == [0, 0, 1, 1, 0, 0]
    assert list(table.patch_damage_resealing[:, bounding]) == [0, 0, 0, 0, 1, 1]
    assert not np.delete(np.asarray(table.patch_damage_injury), bounding, axis=1).any()
    # Round trip, and the default omitted: the definition without the key keeps its form.
    again = parse_spec(spec.to_dict())
    assert again.fingerprint == spec.fingerprint
    assert spec.to_dict()["experiment"]["damage_controls"] == SCHEDULE
    plain = parse_spec(world())
    assert "damage_controls" not in plain.to_dict()["experiment"]
    assert declared_schedule(plain, damage.KIND_ID) == damage.default_schedule(
        dict(plain.model.kinds)[damage.KIND_ID])


@pytest.mark.parametrize("entry, match", [
    (dict(SCHEDULE[0], damage_id="damage_9"), "unknown damage entity"),
    ({k: v for k, v in SCHEDULE[0].items() if k != "resealing"}, "missing"),
    (dict(SCHEDULE[0], injury=[dict(time=0.0, value=1.5)]), r"in \[0, 1\]"),
    (dict(SCHEDULE[0], injury=[dict(time=0.1, value=1.0)]), "starts at time 0"),
    (dict(SCHEDULE[0], injury=[dict(time=0.0, value=0.0), dict(time=2.0, value=1.0)]),
     "horizon|end"),
])
def test_a_schedule_outside_its_contract_is_refused(entry, match):
    refused(match, schedule=[entry])


def test_an_entity_is_scheduled_at_most_once_and_the_list_is_nonempty():
    refused("scheduled twice", schedule=SCHEDULE * 2)
    refused("non-empty list", schedule=[])


def test_fr5s_world_declares_every_field_and_column_for_the_run_view():
    """D154 (the kinds' KindView, core-next 74a75241), as test_inner_view_declarations' kind-world
    test, on FR-5's world: every state field and readout column of the structure, the source
    kinds' among them, has a unit, a record kind and a layer; every readout has its axes; every
    axis has a view set (the condition's own included)."""
    from cells.registry.models import get_model
    from tests.unit.test_inner_view_declarations import INNER_AXES, RECORD_KINDS
    from validation.compartment_ph_engine.parameters import ARM_R

    spec = parse_spec(defs.development_world(defs.fr5_world(ARM_R)))
    impl = get_model(spec.model)
    assert {damage.KIND_ID, condition.KIND_ID} <= {k for k, _ in impl.structure.kinds}
    names = [*impl.STATE_TYPE._fields, *(f for f in impl.OBSERVATION_FIELDS if f != "times")]
    assert {"patch_damage", "ph_condition_factor"} <= set(names)
    layers = {layer["id"] for layer in impl.VIEW_LAYERS}
    for name in names:
        assert impl.UNITS[name] and impl.RECORD_KINDS[name] in RECORD_KINDS, name
        assert impl.RECORD_LAYERS[name] in layers, name
    readouts = [f for f in names if f not in impl.STATE_TYPE._fields]
    assert set(readouts) <= set(impl.OBSERVATION_AXES)
    sets = impl.view_sets(spec)
    assert sets["ph_condition"]["ids"] == ["acid_0"]
    assert sets["ph_condition"]["at"] == [{"node": defs.LUMEN}]
    axes = {a for name in names for a in (impl.STATE_AXES.get(name) or impl.OBSERVATION_AXES[name])}
    assert axes <= INNER_AXES | set(impl.VIEW_AXIS_SETS) | set(sets), axes - INNER_AXES


# ------------------------------------------------------------------------ the damage's step


def layout(present=(False, True, False), injury=1.0, resealing=0.05):
    present = np.asarray(present)
    return SimpleNamespace(
        patch_damage_present=present,
        patch_damage_injury_rate_per_s=np.where(present, injury, 0.0),
        patch_damage_resealing_rate_per_s=np.where(present, resealing, 0.0),
        patch_damage_source_slot=np.flatnonzero(present),
    )


def closed_form(d0, a, b, t):
    s = a + b
    if s == 0:
        return d0
    eq = a / s
    return eq + (d0 - eq) * math.exp(-s * t)


@pytest.mark.parametrize("d0, a, b", [(0.0, 1.0, 0.0), (0.25, 1.0, 0.05), (0.99995, 0.0, 0.05),
                                       (0.5, 0.0, 0.0), (1.0, 1.0, 0.0), (0.3, 2e3, 7e2)])
def test_the_exact_step_composes_and_matches_the_closed_form(d0, a, b):
    """n steps of the law's exact step equal the closed form to rounding, and two half steps equal
    one step: d is exact at every step's end."""
    h, n = 5e-4, 2000
    d = np.asarray(d0)
    for _ in range(n):
        d = law.exact_step(d, a, b, 1.0, 1.0, h, xp=np)
    assert abs(float(d) - closed_form(d0, a, b, n * h)) <= 8 * n * np.finfo(float).eps
    one = law.exact_step(np.asarray(d0), a, b, 1.0, 1.0, h, xp=np)
    half = law.exact_step(law.exact_step(np.asarray(d0), a, b, 1.0, 1.0, h / 2, xp=np),
                          a, b, 1.0, 1.0, h / 2, xp=np)
    assert abs(float(one) - float(half)) <= 4 * np.finfo(float).eps
    assert 0.0 <= float(d) <= 1.0
    for big in (1e4, 1e8):  # Any step stays in [0, 1].
        assert 0.0 <= float(law.exact_step(np.asarray(d0), a, b, 1.0, 1.0, big, xp=np)) <= 1.0


def test_book_takes_the_held_control_and_rates_carry_the_derivative():
    p = layout()
    control = SimpleNamespace(patch_damage_injury=np.array([0.0, 1.0, 0.0]),
                              patch_damage_resealing=np.array([0.0, 1.0, 0.0]))
    start = SimpleNamespace(patch_damage=np.array([0.0, 0.4, 0.0]))
    booked, ok = damage.book(None, start, None, control, p, 1e-3, xp=np)
    expected = closed_form(0.4, 1.0, 0.05, 1e-3)
    assert ok and abs(booked["patch_damage"][1] - expected) <= 4 * np.finfo(float).eps
    assert booked["patch_damage"][0] == booked["patch_damage"][2] == 0.0
    off = SimpleNamespace(patch_damage_injury=np.zeros(3), patch_damage_resealing=np.zeros(3))
    assert damage.book(None, start, None, off, p, 1e-3, xp=np)[0]["patch_damage"][1] == 0.4
    state = SimpleNamespace(patch_damage=np.array([0.0, 0.4, 0.0]),
                            amount_increment=np.zeros((9, 1)),
                            extracellular_amount_increment=np.zeros((9, 2)))
    rates = damage.rates(state, None, control, p, xp=np)
    assert rates.valid and not rates.cell.any() and not rates.outside.any()
    assert rates.derivatives["patch_damage"][1] == pytest.approx(1.0 * 0.6 - 0.05 * 0.4)
    assert set(rates.derivatives) == {"patch_damage"}
    assert float(rates.heat_pJ_s) == float(rates.work_pJ_s) == 0.0
    out_of_range = SimpleNamespace(**{**vars(state), "patch_damage": np.array([0.0, 1.2, 0.0])})
    assert not damage.rates(out_of_range, None, control, p, xp=np).valid


def test_the_damage_domain_and_its_factor():
    p = layout()
    good = SimpleNamespace(patch_damage=np.array([0.0, 0.7, 0.0]))
    assert damage.domain(good, p, xp=np)
    for value in ([0.0, 1.0 + 1e-12, 0.0], [0.1, 0.7, 0.0], [0.0, -1e-30, 0.0]):
        assert not damage.domain(SimpleNamespace(patch_damage=np.array(value)), p, xp=np)
    assert list(damage.factors(good, p, xp=np)) == [0.7]


# ------------------------------------------------------------------------ the condition's factor


def test_the_condition_reads_free_h_at_its_node_as_every_rate_does():
    spec = parse_spec(world())
    from cells.registry.models import get_model

    model = get_model(spec.model)
    state, p = model.initial_values(spec)
    from cells.kinds import proton_buffer

    read, ok = proton_buffer.PROTON_BUFFER.stage_read(state, p, xp=np)
    assert ok
    nodes = [c.id for c in spec.model.cells] + [o.id for o in spec.model.extracellular]
    lumen = nodes.index(defs.LUMEN)
    # The condition reads what every rate of the stage reads: the read's H row over the volume.
    h = condition.free_proton_mM(read, p, xp=np)
    volume = np.concatenate((p.volume, p.extracellular_volume))
    amounts = np.concatenate((p.amount_reference + read.amount_increment,
                              p.extracellular_amount_reference
                              + read.extracellular_amount_increment), axis=1)
    assert float(h[0]) == float(amounts[[s for s, _ in defs.SPECIES].index("H"), lumen]
                                / volume[lumen])
    ph_read = -np.log10(h[0] / closure.PH_REFERENCE_mM)
    f = condition.factors(read, p, xp=np)
    assert float(f[0]) == float(phc.factor(ph_read, 5.5, 4.0, xp=np))
    assert 0.0 < float(f[0]) < 1e-6  # pH 7.2 against pH50 5.5: closed.
    # B4's own readout recomputes h from the closure; the read holds h V as an increment on the
    # stored row's reference, so the two agree to about eps H_eq / (h V) relative in h.
    columns = proton_buffer.PROTON_BUFFER.readouts(state, read, None, None, p, xp=np)
    ph = dict(zip(proton_buffer.COLUMNS, columns, strict=True))["pH"]
    assert abs(float(ph_read) - float(ph[lumen])) <= 1e-11
    (column,) = condition.readouts(state, read, None, None, p, xp=np)
    assert list(column) == list(f)


# ------------------------------------------------------------------ cells.kind.species_condition@1 (G-5)


def reading(row, form, half_saturation_mM, hill_coefficient):
    return dict(species=row, form=form, half_saturation_mM=half_saturation_mM,
                hill_coefficient=hill_coefficient)


# Two conditions: K twice and ATP at the cell; the free proton at the lumen, as CONDITION reads it.
GATE = dict(id="gate_0", node=defs.CELL, law=product.LAW_ID, reads=[
    reading("K", "hill_activation", 100.0, 2.0), reading("ATP", "hill_inhibition", 2.0, 1.5),
    reading("K", "hill_inhibition", 300.0, 1.0)])
ACID = dict(id="gate_1", node=defs.LUMEN, law=product.LAW_ID, reads=[
    reading("H", "hill_activation", 10.0 ** (3.0 - 5.5), 4.0)])


def gated(*conditions):
    """FR-4's development world with species conditions alone declared (no route reads them)."""
    d = world(damages=None, conditions=None)
    d["model"]["species_conditions"] = copy.deepcopy(list(conditions or (GATE, ACID)))
    return d


@pytest.fixture(scope="module")
def gate_world():
    """(spec, implementation, state, layout) of the gated world."""
    from cells.registry.models import get_model

    spec = parse_spec(gated())
    impl = get_model(spec.model)
    return (spec, impl, *impl.initial_values(spec))


def test_the_species_condition_parses_round_trips_and_has_no_state(gate_world):
    from cells.registry.models import get_model

    spec, impl, _, p = gate_world
    declared = dict(spec.model.kinds)[species.KIND_ID]
    assert declared == (
        species.Condition("gate_0", defs.CELL, (
            species.Reading("K", "hill_activation", 100.0, 2.0),
            species.Reading("ATP", "hill_inhibition", 2.0, 1.5),
            species.Reading("K", "hill_inhibition", 300.0, 1.0))),
        species.Condition("gate_1", defs.LUMEN, (
            species.Reading("H", "hill_activation", 10.0 ** (3.0 - 5.5), 4.0),)))
    assert species.parse(species.to_dict(declared), spec) == declared
    assert parse_spec(spec.to_dict()).fingerprint == spec.fingerprint
    kind = species.SPECIES_CONDITION
    assert kind.factor_sources(declared) == ("gate_0", "gate_1")
    assert kind.factors is not None and kind.routed_controls is None
    # No state, control or route entry; its layout fields and its one readout column.
    plain = get_model(parse_spec(world(damages=None, conditions=None)).model)
    assert impl.STATE_TYPE._fields == plain.STATE_TYPE._fields
    assert impl.Control._fields == plain.Control._fields and impl.structure.routes == ()
    assert set(impl.LAYOUT_TYPE._fields) - set(plain.LAYOUT_TYPE._fields) == set(
        species.LAYOUT_FIELDS)
    assert set(impl.OBSERVATION_FIELDS) - set(plain.OBSERVATION_FIELDS) == {
        "species_condition_factor"}
    ids = list(spec.model.species_ids)
    k, atp, h = (ids.index(s) for s in ("K", "ATP", "H"))
    nodes = [c.id for c in spec.model.cells] + [o.id for o in spec.model.extracellular]
    for name, expected in {
        "node": [nodes.index(defs.CELL), nodes.index(defs.LUMEN)],
        "row": [[k, atp, k], [h, 0, 0]],
        "form": [[1, 2, 2], [1, 0, 0]],
        "half_saturation_mM": [[100.0, 2.0, 300.0], [10.0 ** (3.0 - 5.5), 1.0, 1.0]],
        "coefficient": [[2.0, 1.5, 1.0], [4.0, 1.0, 1.0]],
        "pair": [[0, 1, 0], [2, 0, 0]],
        "pair_condition": [0, 0, 1],
    }.items():
        assert np.array_equal(getattr(p, f"species_condition_{name}"), expected), name
    # The structure entry is value-free: the numbers of reads and pairs. Two worlds of one shape
    # share their programs (planted: one read fewer, and a read of a third species, do not).
    def entry(*conditions):
        return species.structure_entry(species.parse(list(conditions), spec))

    other = copy.deepcopy(GATE)
    other["reads"][1].update(form="hill_activation", half_saturation_mM=3.0, hill_coefficient=0.5)
    todays = entry(GATE, ACID)
    assert dict(impl.structure.kinds)[species.KIND_ID] == todays == (
        species.LAW_ID, ((3, 2), (1, 1)))
    assert entry(dict(other, node=defs.LUMEN), ACID) == todays
    assert entry(dict(GATE, reads=GATE["reads"][:2]), ACID) != todays
    other["reads"][2]["species"] = "Cl"
    assert entry(other, ACID) != todays


def test_the_species_condition_s_view_and_its_planted_set(gate_world):
    from cells.records import run_view
    from cells.registry.models import get_model

    def prepared(spec):
        layout = get_model(spec.model).initial_values(spec)[1]
        return run_view.prepare(spec, run_view.Request(), layout=layout)

    spec, impl, *_ = gate_world
    column = "species_condition_factor"
    assert impl.UNITS[column] == "1" and impl.OBSERVATION_AXES[column] == ("species_condition",)
    assert impl.RECORD_KINDS[column] == "level" and impl.RECORD_LAYERS[column] == "membrane"
    entry = impl.view_sets(spec)["species_condition"]
    assert entry["ids"] == ["gate_0", "gate_1"] and entry["kinds"] == ["factor", "factor"]
    assert entry["at"] == [{"node": defs.CELL}, {"node": defs.LUMEN}]
    assert entry["laws"] == [{"law_id": species.LAW_ID}] * 2
    assert entry["reads"] == [GATE["reads"], ACID["reads"]] and set(entry["roles"]) == {"node"}
    assert prepared(spec).sets["species_condition"]["reads"] == entry["reads"]  # Admitted.
    # Planted: without its set, the axis is refused by the run view's writer.
    planted = kind_registry.KindRegistry()
    for kind_id in dict(spec.model.kinds):
        kind = kind_registry.BUILTIN.lookup(kind_id)
        if kind_id == species.KIND_ID:
            kind = dataclasses.replace(kind, view_sets=None)
        planted.register(kind)
    with kind_registry.scope(planted):
        with pytest.raises(run_view.ViewRefused, match="no set for its axis species_condition"):
            prepared(parse_spec(gated()))


def changed_read(**changes):
    return dict(reads=[dict(GATE["reads"][0], **changes), *GATE["reads"][1:]])


@pytest.mark.parametrize("change, match", [
    (dict(node="nowhere"), "unknown node 'nowhere'"),
    (dict(node=[defs.CELL]), "unknown node"),
    (dict(law=phc.LAW_ID), f"law is one of {species.LAW_ID}"),
    (dict(law=None), f"law is one of {species.LAW_ID}"),
    (dict(reads=[]), "reads is a non-empty list"),
    (dict(reads=GATE["reads"][0]), "reads is a non-empty list"),
    (changed_read(species="Q"), "read 0: unknown species 'Q'"),
    (changed_read(species=["K"]), "read 0: unknown species"),
    (changed_read(form="hill"), "read 0: form is one of hill_activation, hill_inhibition"),
    (changed_read(half_saturation_mM=0.0), "half_saturation_mM must be finite and positive"),
    (changed_read(half_saturation_mM=-1.0), "half_saturation_mM must be finite and positive"),
    (changed_read(half_saturation_mM=float("inf")), "half_saturation_mM must be finite"),
    (changed_read(half_saturation_mM=True), "half_saturation_mM must be a finite number"),
    (changed_read(half_saturation_mM=1e-310), "half_saturation_mM is a normal float"),
    (changed_read(hill_coefficient=0.0), "hill_coefficient must be finite and positive"),
    (changed_read(hill_coefficient=-2.0), "hill_coefficient must be finite and positive"),
    (changed_read(hill_coefficient=float("nan")), "hill_coefficient must be finite"),
    (changed_read(hill_coefficient=1e-310), "hill_coefficient is a normal float"),
    (changed_read(valence=2), r"read 0: missing=\[\], unknown=\['valence'\]"),
    (dict(basal=0.1), r"unknown=\['basal'\]"),
    (dict(id=""), "its ID must be a name, unique among the model's IDs"),
    (dict(id=defs.LUMEN), "its ID must be a name, unique among the model's IDs"),
    (dict(id=defs.BOUNDING), "its ID must be a name, unique among the model's IDs"),
])
def test_a_species_condition_outside_its_contract_is_refused_by_name(gate_world, change, match):
    with pytest.raises(ConfigError, match=match) as refusal:
        species.parse([dict(GATE, **change)], gate_world[0])
    named = f"{species.KIND_ID}: condition {change.get('id', GATE['id'])!r}"
    assert str(refusal.value).startswith(named)  # The kind, the condition, then the thing.


def test_a_species_condition_s_list_ids_and_law_are_refused_by_name(gate_world):
    spec = gate_world[0]
    for entries in ([], {}, None):
        with pytest.raises(ConfigError, match="species_conditions is a non-empty list"):
            species.parse(entries, spec)
    with pytest.raises(ConfigError, match="'gate_0': its ID must be a name, unique"):
        species.parse([GATE, dict(ACID, id="gate_0")], spec)
    with pytest.raises(ConfigError, match="condition None must be an object"):
        species.parse(["gate_0"], spec)
    refused_world = gated(dict(GATE, node="nowhere"))  # The real parse refuses it the same way.
    with pytest.raises(ConfigError, match="condition 'gate_0': unknown node 'nowhere'"):
        parse_spec(refused_world)
    # A law of its interface and host that version 1 has no kernel path for, and none at all.
    other = dataclasses.replace(product.LAW, law_id="tests.transfer_factor.planted_factor@1")
    with law_registry.scope(law_registry.BUILTIN.extended(other)):
        with pytest.raises(ConfigError, match=f"version 1 runs {species.LAW_ID}, not tests"):
            species.parse([dict(GATE, law="tests.transfer_factor.planted_factor@1")], spec)
    with law_registry.scope(law_registry.LawRegistry()):
        with pytest.raises(ConfigError, match="'gate_0': law is one of $"):
            species.parse([GATE], spec)


def test_the_species_condition_reads_the_free_form_at_a_buffered_node(gate_world):
    """H at the lumen: the condition's factor on the stage's read is the pH condition's law at the
    free proton (planted: the stored row, B4's proton equivalents, gives another number)."""
    from cells.kinds import proton_buffer

    spec, _, state, p = gate_world
    read, ok = proton_buffer.PROTON_BUFFER.stage_read(state, p, xp=np)
    assert ok
    nodes = [c.id for c in spec.model.cells] + [o.id for o in spec.model.extracellular]
    lumen, row = nodes.index(defs.LUMEN) - 1, list(spec.model.species_ids).index("H")
    h = (p.extracellular_amount_reference + read.extracellular_amount_increment)[row, lumen]
    ph = -np.log10(h / p.extracellular_volume[lumen] / closure.PH_REFERENCE_mM)
    expected = float(phc.factor(ph, 5.5, 4.0, xp=np))
    # The pH law's tanh form keeps 1e-9 of this small factor (3e-15 of 1, test_hill_factors).
    assert float(species.factors(read, p, xp=np)[1]) == pytest.approx(expected, rel=1e-8, abs=0)
    assert float(species.factors(state, p, xp=np)[1]) != pytest.approx(expected, rel=1e-2, abs=0)
    (column,) = species.readouts(state, read, None, None, p, xp=np)
    assert np.array_equal(column, species.factors(read, p, xp=np))


# ------------------------------------------------------------------ its feedback hooks


def scaled(state, p, rng):
    """The state with every amount scaled by a random factor, as a stage's read."""
    cell = p.amount_reference * 10.0 ** rng.uniform(-3, 3, p.amount_reference.shape)
    node = p.extracellular_amount_reference
    node = node * 10.0 ** rng.uniform(-3, 3, node.shape)
    return state._replace(
        amount_increment=cell - p.amount_reference,
        extracellular_amount_increment=node - p.extracellular_amount_reference,
    )


def bumped(read, p, row, node, factor):
    """The read with one row's amount at one node (cells, then outside nodes) times `factor`."""
    n = p.amount_reference.shape[1]
    inside = node < n
    name = "amount" if inside else "extracellular_amount"
    column = node if inside else node - n
    increment = np.array(getattr(read, f"{name}_increment"))
    amount = getattr(p, f"{name}_reference")[row, column] + increment[row, column]
    increment[row, column] += amount * (factor - 1.0)
    return read._replace(**{f"{name}_increment": increment})


def pair_indices(spec, rows):
    """The (row, node) indices of the flattened pairs, as the core resolves the names."""
    nodes = [c.id for c in spec.model.cells] + [o.id for o in spec.model.extracellular]
    ids = list(spec.model.species_ids)
    return [(ids.index(s), nodes.index(n)) for pairs in rows for s, n in pairs]


def test_the_feedback_hooks_name_each_row_once_and_give_the_slopes_of_ln_f(gate_world):
    spec, _, state, p = gate_world
    declared = dict(spec.model.kinds)[species.KIND_ID]
    rows = kind_registry.kind_factor_rows(species.SPECIES_CONDITION, declared)
    assert rows == ((("K", defs.CELL), ("ATP", defs.CELL)), (("H", defs.LUMEN),))
    traced = jax.eval_shape(partial(species.factor_log_slopes, xp=jnp), state, p)
    assert traced.shape == (3,) and traced.dtype == jnp.float64  # [P], what the core binds.
    owners = [0, 0, 1]  # Each flattened pair's condition.
    rng, h = np.random.default_rng(3), 1e-5
    worst = dict.fromkeys(("slope", "sign dropped", "in n"), 0.0)
    for _ in range(20):
        read = scaled(state, p, rng)
        slopes = species.factor_log_slopes(read, p, xp=np)
        amounts = np.concatenate((p.amount_reference + read.amount_increment,
                                  p.extracellular_amount_reference
                                  + read.extracellular_amount_increment), axis=1)
        for j, (row, node) in enumerate(pair_indices(spec, rows)):
            up, down = (np.log(species.factors(bumped(read, p, row, node, math.exp(s * h)), p,
                                               xp=np))[owners[j]] for s in (1, -1))
            difference = (up - down) / (2 * h)
            worst["slope"] = max(worst["slope"], abs(slopes[j] - difference))
            worst["sign dropped"] = max(worst["sign dropped"], abs(abs(slopes[j]) - difference))
            worst["in n"] = max(worst["in n"], abs(slopes[j] / amounts[row, node] - difference))
    assert worst["slope"] < 1e-5, worst
    assert worst["sign dropped"] > 0.1 and worst["in n"] > 0.1  # Plants.
    assert np.array_equal(
        np.asarray(jax.jit(partial(species.factor_log_slopes, xp=jnp))(state, p)).round(12),
        species.factor_log_slopes(state, p, xp=np).round(12))
    # At zero, a trace and a very large amount the slopes are their limits, finite: K's is +2 from
    # its activation, then -1 from its inhibition; ATP's inhibition 0, then -1.5.
    for amount, limits in ((0.0, [2.0, 0.0]), (1e-160, [2.0, 0.0]), (1e30, [-1.0, -1.5])):
        extreme = p._replace(amount_reference=np.full_like(p.amount_reference, amount))
        read = state._replace(amount_increment=np.zeros_like(state.amount_increment))
        with np.errstate(divide="ignore"):  # ln 0 = -infinity, in the kernel's terms.
            slopes = species.factor_log_slopes(read, extreme, xp=np)
        assert slopes[:2] == pytest.approx(limits, abs=1e-9)


def test_a_source_s_rows_are_checked_when_read_and_a_pair_named_twice_is_refused(gate_world):
    declared = dict(gate_world[0].model.kinds)[species.KIND_ID]
    kind = species.SPECIES_CONDITION
    honest = kind.factor_rows(declared)
    assert kind_registry.kind_factor_rows(condition.PH_CONDITION, ()) is None  # No hooks.
    plants = {
        "names a pair twice": (honest[0] + honest[0][:1], honest[1]),
        "one entry per source": honest[:1],
        "pairs": (honest[0], (("H",),)),
        r"pairs$": (honest[0], (("H", 2),)),
        "a tuple of": [*honest],
    }
    for match, rows in plants.items():
        planted = dataclasses.replace(kind, factor_rows=lambda d, rows=rows: rows)
        with pytest.raises(ValueError, match=match) as refusal:
            kind_registry.kind_factor_rows(planted, declared)
        assert species.KIND_ID in str(refusal.value)
