"""FR-5's source kinds (the FR-4/FR-5 note's §16; INNER §7.4 (l), (n)): cells.patch_damage@1 and
cells.ph_condition@1.

Their declarations, the damage's schedules (`damage_controls`, the core's Schedule) and their
refusals through the real parse (FR-4's development world with the kinds declared), and their
hooks on the host: the damage's exact step at the step's held control (composition, the
equilibrium, [0, 1] at any step), the derivative the tableau carries, and both kinds' factors for
the routing door. The engine's runs are test_fr5_source_kinds_engine.py and
test_fr5_world_engine.py.
"""

import copy
import math
from types import SimpleNamespace

import numpy as np
import pytest

from cells.definitions.specs import ConfigError, parse_spec
from cells.definitions.surface_pump_v3_spec import control_values
from cells.kinds import patch_damage as damage
from cells.kinds import ph_condition as condition
from cells.laws.reactions import ph_condition as phc
from cells.laws.reactions import rapid_proton_buffer as closure
from cells.laws.transport import patch_damage as law
from cells.registry.kind_registry import declared_schedule
from validation.compartment_ph_engine import definitions as defs

DAMAGE = dict(id="damage_0", patch=defs.BOUNDING, law="bounding_patch_damage@1",
              initial_damage=0.25, injury_rate_per_s=1.0, resealing_rate_per_s=0.05)
CONDITION = dict(id="acid_0", node=defs.LUMEN, law="ph_conditioned_factor@1", ph50=5.5,
                 slope=4.0)
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
    (dict(law="tests.damage.other@1"), "law is cells.bounding_patch_damage@1"),
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
    (dict(law="ph_condition@1"), "law is cells.ph_conditioned_factor@1"),
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
