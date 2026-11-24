"""FR-43 part 2B (D315): C2.8, both writers of one pool while the cell swells, against the
code-blind reference (validation/fr43_part2/references), on a shorter horizon than the registered
judgement.

The world is C2.8's swelling pair (the gene unit beside the network's N + X -> W, water declared
first, the bath at 0.4 of the cell's osmolarity), cut to END s; its samples are the reference's at
t <= END. By the specification's CRITERIA.md:
- every C2.8 quantity (n_N, n_X, n_W, V, each writer's net books and net rate of N, and F) meets
  the rule between dt and dt/2: the ratio in [3.6, 4.4], or both errors below 1e-8;
- each writer reading the declared volume V_0 instead (its half-step drops the composite's view)
  misses at dt/2, in n_N or its own books, by at least 10 times the correct run's error: the miss
  shows in amounts. (The registered judgement also runs each plant at dt for its ratio.)
The registered judgement over the full 40 s is part 2's registered-20261123/c28-ea813fae; this file
is its regression guard. Its reason and cost: four compiled runs of the pair over END s (seconds as
the tier tool measures).
"""

import jax
import pytest

from validation.tissue import shared_inventory_references as sir

END = 10.0  # s: a quarter of the registered horizon, the cell already past 1.5 V_0.


@pytest.fixture(scope="module", autouse=True)
def x64():
    jax.config.update("jax_enable_x64", True)


def shorter(raw):
    experiment = raw["experiment"]
    experiment["end_time"] = END
    experiment["observation_times"] = [t for t in experiment["observation_times"] if t <= END]


@pytest.fixture(scope="module")
def runs():
    times, ref = sir.reference_c28()
    keep = times <= END
    ref = {q: v[keep] for q, v in ref.items()}
    coarse = sir.engine_c28(sir.C28_WORLDS[0], shorter)[1]
    fine = sir.engine_c28(sir.C28_WORLDS[1], shorter)[1]
    return ref, coarse, fine


def test_c28_both_writers_meet_the_reference_at_second_order_while_the_cell_swells(runs):
    ref, coarse, fine = runs
    for q in sir.C28_QUANTITIES:
        verdict = sir.ratio_verdict(sir.error(coarse[q], ref[q]), sir.error(fine[q], ref[q]))
        assert verdict["passed"], (q, verdict)


@pytest.mark.parametrize("writer", sorted(sir.C28_PLANTS))
def test_c28_a_writer_on_the_declared_volume_misses_in_amounts(writer, runs):
    ref, _, fine = runs
    wrong, refusal = sir.planted_c28(writer, sir.C28_WORLDS[1], shorter)
    assert refusal is None, refusal
    books = sir.C28_PLANTS[writer][2]
    over = {
        q: sir.error(wrong[q], ref[q]) / max(sir.error(fine[q], ref[q]), 1e-300)
        for q in ("n_N", books)
    }
    assert max(over.values()) >= sir.C28_PLANT_FACTOR, over
