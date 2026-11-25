"""The two-cell closed world, compiled (docs/CALCIUM_STORE_AND_CHANNELS_DESIGN.md, section 14, row
14): validation/calcium_store/worlds.py's two_cells, of the registered laws. Two cells on the
gauge; near and far joined to it by faces, so two free field offsets and field solver version 3
(D147); a store per cell at -5 mV; a junction with a calcium route; calcium on the faces;
buffers, both pumps, the exchanger and a calcium channel per plasma patch; each release gated by
its cell's two conditions. Ten recorded steps in two windows meet every criterion of
tests/calcium_store_fixtures.py, and a restart from the written checkpoint repeats the second
window bit for bit.

Planted, each missed: the two stores exchanged, the junction route's sign turned, the pumps
without their voltage, near left out of the whole-world sums, a condition on the other cell, K
and n exchanged in a condition (in the criteria); one release 1% more permeable and one pump 1%
larger (in the world that the engine runs, each missed at that mover alone). Refused by name: the
stores' owners exchanged.

Seconds: about 40 on a quiet CPU, of which 27 are its one compile (a window's program, which the
restart and the planted worlds reuse), so tier 2. The reason (D224): two free offsets, two
stores, a junction and the feedback of two gated releases are in no other row's one program.
"""

import pytest

from cells.definitions.specs import ConfigError, parse_spec
from tests import calcium_store_fixtures as rows
from validation.calcium_store import worlds
from validation.tissue import field_solver_choice


@pytest.fixture(scope="module")
def two():
    return rows.run_two()


def test_the_two_cell_world_declares_version_3_because_near_and_far_float(two):
    assert field_solver_choice.free_field_offsets(two.raw) == 2
    assert field_solver_choice.declare(two.raw)["execution"]["field_solver"] == worlds.VERSION_3


def test_the_stores_owners_are_their_patches_cells():
    raw = worlds.two_cells(dt=rows.DT, steps=5)
    (owned,) = [o for o in raw["model"]["operators"] if o["law"] == worlds.COMPARTMENTS]
    first, second = owned["compartments"]
    first["owner"], second["owner"] = second["owner"], first["owner"]
    with pytest.raises(ConfigError, match="not on its declared owner"):
        parse_spec(raw)


def test_the_two_cell_world_moves_as_its_equations_and_restarts(two, tmp_path):
    rows.agrees(two)
    rows.restarts(two, tmp_path)


def test_planted_criteria_of_the_two_cell_world_miss(two):
    exchanged = set(rows.misses_moved(two, stores_exchanged=True))
    assert {"store_leak_0", "release_1", "store_pump_0"} <= exchanged
    assert set(rows.misses_moved(two, junction_turned=True)) == {"junction_calcium"}
    assert {"plasma_pump_0", "store_pump_1"} <= set(rows.misses_moved(two, voltage_dropped=True))
    assert {"K", "Na"} <= set(rows.misses_sums(two, left_out=("near",)))
    assert rows.misses_factors(two, node_of={"release_calcium_0": "cell_1"})
    declared = {c["id"]: c for c in two.raw["model"]["species_conditions"]}
    (read,) = declared["release_ip3_0"]["reads"]
    exchanged = dict(
        species=read["species"],
        form="activation",
        half_saturation_mM=read["hill_coefficient"],
        hill_coefficient=read["half_saturation_mM"],
    )
    assert rows.misses_factors(two, reads_of={"release_ip3_0": [exchanged]})


def more_release(first, second):
    first["calcium_routes"]["release"]["permeability_m_per_s"] *= 1.01


def more_pump(first, second):
    second["pumps"]["store_pump"]["capacity_fmol_per_s"] *= 1.01


@pytest.mark.parametrize(
    "edit,mover",
    [(more_release, "release_0"), (more_pump, "store_pump_1")],
    ids=["release", "pump"],
)
def test_a_world_with_one_number_1_percent_off_misses(two, edit, mover):
    assert set(rows.misses_moved(rows.run_two(edit=edit))) == {mover}
