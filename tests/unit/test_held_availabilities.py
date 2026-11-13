"""The pump family's experiment.changes are built once per experiment (immutable schedules).

Execution reads experiment.changes several times per window (held controls, control
tables, each window's event index); rebuilding them took about 10 ms per access at 825
nodes. surface_pump_v2_spec.Experiment keeps the built rows on the instance, outside the
dataclass fields. These tests pin that the kept rows are the rows a fresh build gives,
for @2 and @3 and for the experiments that extend them (water, replacement), that a
replaced experiment builds its own, and that fields, equality and hashing ignore them.
"""

import pickle
from dataclasses import fields, replace

from cells.core.schedule import control_values, event_index
from cells.core.specs import parse_spec
from cells.numerics import surface_imex as imex
from validation.tissue import cell_replacement_fixtures as replacement
from validation.tissue import pump_water_fixtures as water
from validation.tissue import surface_pump_v2_fixtures as fixtures_2
from validation.tissue import surface_pump_v3_fixtures as fixtures_3


def pump(version):
    fixtures = {2: fixtures_2, 3: fixtures_3}[version]
    return parse_spec(fixtures.definition("release", solver=imex.ARS222_ID))


def test_changes_are_built_once_and_equal_a_fresh_build():
    for version in (2, 3):
        experiment = pump(version).experiment
        first = experiment.changes
        assert experiment.changes is first
        assert experiment.__dict__["_changes"] is first
        assert first == experiment._held_availabilities()
        assert replace(experiment).changes == first  # A new instance builds its own.


def test_extending_experiments_read_the_same_rows():
    sheet = replacement.heredity_sheet(radius=1, end_time=0.1)
    template = replacement.template_from_cell(sheet, "cell_0", "t0")
    for raw in (
        water.with_water(water.heredity_cell(end_time=0.01)),
        replacement.with_replacement(sheet, [template], [(0.05, "cell_1", "t0", "carrier_0")]),
    ):
        experiment = parse_spec(raw).experiment
        first = experiment.changes
        assert experiment.changes == first == replace(experiment).changes


def test_kept_rows_are_outside_the_fields_equality_and_hash():
    experiment = pump(3).experiment
    twin = replace(experiment)
    assert experiment.changes  # Kept from here on.
    assert "_changes" in experiment.__dict__ and "_changes" not in twin.__dict__
    assert "_changes" not in {f.name for f in fields(experiment)}
    assert experiment == twin and hash(experiment) == hash(twin)
    assert pickle.loads(pickle.dumps(experiment)).changes == experiment.changes


def test_a_replaced_experiment_builds_its_own_rows():
    experiment = pump(3).experiment
    before = experiment.changes
    membranes = list(experiment.membranes)
    first = membranes[0]
    membranes[0] = (*first, replace(first[-1], time=first[-1].time + 3e-4, availability=0.25))
    changed = replace(experiment, membranes=tuple(membranes))
    assert "_changes" not in changed.__dict__
    assert changed.changes != before and changed.changes == changed._held_availabilities()


def test_event_index_and_control_tables_are_unchanged():
    kept = pump(3)
    assert kept.experiment.changes  # Rows kept before the reads below.
    times = [0.0, 0.0005, 0.00073, 0.0008, 0.0019]
    for t in times:
        assert event_index(kept, t) == event_index(pump(3), t)
    for a, b in zip(control_values(kept, times), control_values(pump(3), times), strict=True):
        assert a.dtype == b.dtype and a.shape == b.shape and a.tobytes() == b.tobytes()
