"""cells.rate_equations@1's shared pool (OL6 slice S2; the OL6 design note's §3, §6.9).

Closed forms and identities only, never a comparison with exact events (D304). A population of
two vesicles on one pool transfers by the exact operator's domain-6 draws, divides into its free
slot (every daughter lives, daughter 0 in its parent's slot) and stops `slots_full` when a split
finds no free slot; two identical vesicles lysing at one instant are refused (FR-20's rule). A new
file for the slice's population (D224): two population worlds compiled, about 45 s.
"""

import numpy as np
import pytest

from cells.definitions.specs import ConfigError, parse_spec
from cells.models.assembly_lineages_v2 import SHEAR_FISSION, runner, streams, transfer
from tests.unit.test_assembly_lineages_v2_rate_equations_vesicles import (
    population_definition,
    population_world,
)


def test_a_population_transfers_divides_into_a_free_slot_and_stops_when_full():
    w = population_world([12000, 10000], 0.3, slots=2)
    w["division"] = {"law": SHEAR_FISSION}
    fresh = [48356, 0]
    schedules = [
        {"index": 0, "kind": "transfer", "times_s": [1.0], "K_keep": 1, "fresh_pool": fresh},
        {"index": 1, "kind": "shear", "k": 2, "times_s": [2.0]},
        {"index": 2, "kind": "shear", "k": 2, "times_s": [3.0]},
    ]
    spec = parse_spec(population_definition(w, horizon=4.0, schedules=schedules))
    run = runner.run(spec)
    assert run.status == "slots_full"
    moved, split, full = run.events
    base = streams.base_key_data(1, 0, 0, 0)
    kept = transfer.sample(base, spec.experiment.schedules[0], 0, [0, 1], 1)[0]
    assert moved["kind"] == "transfer" and moved["kept"] == kept  # domain 6, as exact
    (alive,) = kept
    assert split["outcome"] == "split" and split["slot"] == alive
    assert sorted(split["homes"]) == [0, 1]  # daughter 0 in its slot, daughter 1 in the free one
    sub = alive  # founder i holds key i:0, its sub-lineage i
    assert split["keys"] == [(sub << 32) + 1, (sub << 32) + 2]
    first, second = (np.asarray(d) for d in split["daughters"])
    assert np.allclose(first, second, rtol=1e-15, atol=0.0)
    assert full["outcome"] == "slots_full"
    assert run.rows["alive"][-1].tolist() == [True, True] and run.moieties["closes"]


def test_two_identical_vesicles_lysing_at_one_instant_are_refused():
    w = population_world([12000, 12000], 0.97, slots=2)
    w["founder"]["L@pool"] = 2000
    spec = parse_spec(population_definition(w, horizon=50.0, schedules=None))
    with pytest.raises(ConfigError, match="two lyses at one instant"):
        runner.run(spec)
