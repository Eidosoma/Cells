"""Time-varying kind controls: schedules on the step grid (docs/INNER_MODEL_V4_DESIGN.md §7.4 (l)).

tests/kind_fixtures.py's scheduled exchange (`tests.kind.exchange@1` with its availability under the
experiment key `test_exchange_controls`, registered from outside src/cells on a test-local
registry) moves the neutral species B from a heredity cell to its outside node at the declared
rate times its availability. At the definition, on the host (test_kind_schedules_runs.py runs it):
- the schedule's breakpoints join the experiment's change times, so each is a step boundary (an
  off-nominal one inserted exactly), and the change records carry its values;
- each step's control is the schedule's value at the step's start, held between change times;
- the definition round-trips with and without its key; an omitted key is the kind's default,
  which to_dict omits, and a definition without a scheduled kind keeps today's records;
- refused: an undeclared kind's key, a breakpoint past the horizon, a value outside the control
  domain at its breakpoint, a malformed series, an operator's key that a kind owns, and registry
  clashes;
- the schedule type's own rules;
- two schedules share one implementation object and compile key.
"""

import pytest

from cells.definitions import pump_composite_spec as cs
from cells.definitions import surface_pump_v2_spec as second
from cells.definitions import surface_pump_v3_spec as ionic
from cells.definitions.specs import ConfigError, parse_spec
from cells.definitions.surface_pump_v3_spec import control_values
from cells.execution.runner import timeline
from cells.execution.state import initialise
from cells.execution.vector_windows import spec_world_key
from cells.registry import kind_registry
from cells.registry.inventory_species import add_inventory_species
from cells.registry.models import get_model
from tests import kind_fixtures as kf
from validation.tissue import pump_water_fixtures as water_fixtures

RATE = 1e-3  # fmol/s, small against B's 1 fmol in the cell.
END_S = 0.004  # Four nominal 1 ms steps.
# 0.002 is on the nominal grid; 0.0025 is not, so the grid gains a boundary there.
POINTS = ((0.0, 1.0), (0.002, 0.25), (0.0025, 0.0), (0.003, 0.5))
GRID = (0.0, 0.001, 0.002, 0.0025, 0.003, 0.004)
HELD = (1.0, 1.0, 0.25, 0.0, 0.5)  # Each step's availability, at its start.
MOVED = RATE * (1.0 * 0.002 + 0.25 * 0.0005 + 0.0 * 0.0005 + 0.5 * 0.001)


def scheduled():
    return kf.registry(exchange=kf.SCHEDULED_EXCHANGE)


def world(points=POINTS, *, end_time=END_S):
    raw = water_fixtures.heredity_cell("D", end_time=end_time)
    raw = add_inventory_species(
        raw, "B", trace_mM=1.0, diffusivity_m2_per_s=1e-10, floor_fmol=1e-12
    )
    raw = kf.declare(raw, rate=RATE)
    return raw if points is None else kf.schedule(raw, points)


def test_breakpoints_join_the_change_times_and_split_the_step_grid():
    with kind_registry.scope(scheduled()):
        spec = parse_spec(world())
        assert spec.experiment.kinds == (
            (kf.KIND_ID, kind_registry.Schedule((("availability", POINTS),))),
        )
        records = spec.experiment.changes
        assert [c.time for c in records] == [t for t, _ in POINTS]
        assert all(type(c) is ionic.KindChange for c in records)
        assert [c.kinds for c in records] == [((a,),) for _, a in POINTS]
        times = timeline(spec)
        assert tuple(times) == GRID  # 0.0025 inserted exactly.
        held = control_values(spec, times[:-1]).exchange_availability
        assert held.shape == (len(GRID) - 1, 1) and tuple(held[:, 0]) == HELD
        # The rows are the change records' rows: constant between change times.
        assert tuple(
            control_values(spec, [0.0021, 0.0024, 0.0026, 0.0039]).exchange_availability[:, 0]
        ) == (0.25, 0.25, 0.0, 0.5)


def test_the_definition_round_trips_and_an_omitted_key_is_the_default():
    with kind_registry.scope(scheduled()):
        spec = parse_spec(world())
        raw = spec.to_dict()
        assert raw["experiment"][kf.SCHEDULE_KEY] == [
            dict(time=t, availability=a) for t, a in POINTS
        ]
        assert parse_spec(raw) == spec
        omitted = parse_spec(world(None))
        assert omitted.experiment.kinds == ((kf.KIND_ID, kf.DEFAULT_SCHEDULE),)
        assert kf.SCHEDULE_KEY not in omitted.to_dict()["experiment"]
        assert parse_spec(omitted.to_dict()) == omitted
        explicit = parse_spec(world(((0.0, 1.0),)))  # The default, written out: the same form.
        assert explicit == omitted and explicit.fingerprint == omitted.fingerprint
        held = control_values(omitted, [0.0, 0.001, 0.003]).exchange_availability
        assert held.tolist() == [[1.0], [1.0], [1.0]]
        # The default adds no change time: the grid is the nominal one.
        assert [c.time for c in omitted.experiment.changes] == [0.0]
        assert tuple(timeline(omitted)) == (0.0, 0.001, 0.002, 0.003, 0.004)


def test_a_definition_without_a_scheduled_kind_keeps_todays_records():
    spec = parse_spec(water_fixtures.heredity_cell("D", end_time=END_S))
    assert spec.experiment.kinds == ()
    assert all(type(c) is second.Change for c in spec.experiment.changes)
    with kind_registry.scope(kf.registry()):  # The exchange without a schedule: version 1.
        unscheduled = parse_spec(world(None))
        assert unscheduled.experiment.kinds == ()
        assert all(type(c) is second.Change for c in unscheduled.experiment.changes)


def test_refusals():
    with kind_registry.scope(scheduled()):
        undeclared = world()
        del undeclared["model"][kf.MODEL_KEY]
        with pytest.raises(ConfigError, match="which the model does not declare"):
            parse_spec(undeclared)
        with pytest.raises(ConfigError, match="past the horizon"):
            parse_spec(world(((0.0, 1.0), (0.005, 0.5))))
        with pytest.raises(ConfigError, match="domain invalid"):  # Rule (d), at its breakpoint.
            parse_spec(world(((0.0, 1.0), (0.002, 1.5))))
        with pytest.raises(ConfigError, match="starts at time 0"):
            parse_spec(world(((0.001, 1.0),)))
        with pytest.raises(ConfigError, match="strictly increase"):
            parse_spec(world(((0.0, 1.0), (0.002, 0.5), (0.002, 0.25))))
    claimed = kf.registry(  # An operator may not take a kind's key.
        kind_registry.Kind(
            kind_id="tests.kind.claims_water@1",
            model_key="test_claims_water",
            experiment_keys=("water_controls",),
            parse_schedule=lambda raw, base, declaration: kf.DEFAULT_SCHEDULE,
            schedule_to_dict=lambda schedule, declaration: {},
        ),
        exchange=kf.SCHEDULED_EXCHANGE,
    )
    with kind_registry.scope(claimed):
        with pytest.raises(ConfigError, match="which kind tests.kind.claims_water@1 owns"):
            parse_spec(cs.frozen_definition(water_fixtures.with_water(world())))
    registry = kf.registry(exchange=kf.SCHEDULED_EXCHANGE)
    with pytest.raises(ValueError, match="is tests.kind.exchange@1's"):
        registry.register(
            kind_registry.Kind(
                kind_id="tests.kind.other@1",
                model_key="test_other",
                experiment_keys=(kf.SCHEDULE_KEY,),
                parse_schedule=lambda raw, base, declaration: kf.DEFAULT_SCHEDULE,
                schedule_to_dict=lambda schedule, declaration: {},
            )
        )
    with pytest.raises(ValueError, match="supplies parse_schedule and schedule_to_dict"):
        registry.register(
            kind_registry.Kind(
                kind_id="tests.kind.bare@1", model_key="bare", experiment_keys=("x",)
            )
        )


def test_a_schedule_is_named_piecewise_constant_series():
    schedule = kind_registry.Schedule((("a", ((0, 1), (2.0, 0.5))), ("b", ((0.0, 3.0),))))
    assert schedule.series == (("a", ((0.0, 1.0), (2.0, 0.5))), ("b", ((0.0, 3.0),)))
    assert schedule.names == ("a", "b") and schedule.times == (0.0, 2.0)
    assert schedule.at(1.999) == (1.0, 3.0) and schedule.at(2.0) == (0.5, 3.0)
    assert schedule.values("a", [0.0, 1.0, 2.0, 7.0]).tolist() == [1.0, 1.0, 0.5, 0.5]
    for bad in ((), (("a", ()),), (("a", ((0.0, 1.0),)), ("a", ((0.0, 1.0),))),
                (("a", ((0.0, float("nan")),)),), (("a", ((0.0, True),)),)):  # fmt: skip
        with pytest.raises(ConfigError):
            kind_registry.Schedule(bad)
    points = kind_registry.parse_series([dict(time=0, value=0.0), dict(time=1.5, value=1)], "u")
    assert points == ((0.0, 0.0), (1.5, 1.0))
    assert kind_registry.series_to_dict(points) == [
        dict(time=0.0, value=0.0),
        dict(time=1.5, value=1.0),
    ]
    with pytest.raises(ConfigError, match="in \\[0, 1\\]"):
        kind_registry.parse_series([dict(time=0, value=2.0)], "u")
    assert kind_registry.parse_series([dict(time=0, value=-2.0)], "u", unit_interval=False) == (
        (0.0, -2.0),
    )
    with pytest.raises(ConfigError, match="missing"):
        kind_registry.parse_series([dict(time=0)], "u")


def test_two_schedules_share_one_implementation_object_and_compile_key():
    with kind_registry.scope(scheduled()):
        one = parse_spec(world())
        two = parse_spec(world(((0.0, 0.5), (0.001, 1.0))))
        model = get_model(one.model)
        assert get_model(two.model) is model
        assert spec_world_key(model, one, initialise(one)) == spec_world_key(
            model, two, initialise(two)
        )
