"""The comparison of gene regulation's option A (G4) with G2's code-blind references, read from
their interface in the tree (validation/gene_regulation/references/interface/, data only), through
validation/gene_regulation/compare.py. No world is compiled: the engine's side is the operator's own
half-steps in NumPy (validation/gene_regulation/kernel.py) over each world's first outputs.

- Every one of G2's 50 potential sets is exactly one of the sheet's (sheet_check.potential_sets),
  matched by the four values, so each engine run meets the reference of its own set.
- Over the first outputs at the test instance, every readout G2 holds is within 1e-4 of its scale
  (the sheet's §6: its largest magnitude over G2's horizon), and every heat class and G(t) - G(0)
  within 1e-6: a development bound, G6 registers the judged one. A wrong law moves a readout far
  beyond it; the sheet's plants move theirs by 1e-4 to 50%.
- G(t) - G(0), from the state alone, meets the booked heat within 1e-10 of the heat; the kernel's
  own file holds it to its inputs' rounding.
"""

import pytest

from validation.gene_regulation import compare, engine_run, kernel, worlds
from validation.gene_regulation import sheet_check as sheet

REFERENCES = compare.References()
TRAJECTORY_BOUND = 1e-4
HEAT_BOUND = 1e-6


def test_every_reference_set_is_one_sheet_set():
    sets = sheet.potential_sets(interior=True)
    found = {label: REFERENCES.find({k: str(v) for k, v in s.items()}) for label, s in sets.items()}
    assert sorted(found.values()) == sorted(REFERENCES.sets) == list(range(50))
    assert found["test instance"] == 0 and found["Spirin's E_pep"] == 1


# (world, horizon in seconds): five outputs or more each, every route of A1's but its regulator's
# coupling, which only the composite applies (A1 runs there: engine_run.py).
WORLDS = [("pol T=5", 150.0), ("two-gene", 150.0), ("rib n_R=10", 60.0)]


@pytest.mark.parametrize(("world", "horizon"), WORLDS)
def test_the_kernel_meets_the_references_over_the_first_outputs(world, horizon):
    spec, _, states, _ = kernel.run(kernel.truncated(worlds.world(world), horizon))
    times, values, checks = engine_run.readouts(spec, states)
    _, references = REFERENCES.sets[0]
    gaps = compare.gaps(dict(t=times, readouts=values), references[world])
    assert len(gaps) >= 20
    heats = {k: v for k, v in gaps.items() if k.startswith("H_") or k == "G_minus_G0"}
    assert heats and max(heats.values()) <= HEAT_BOUND, heats
    worst = max(gaps, key=gaps.get)
    assert gaps[worst] <= TRAJECTORY_BOUND, (worst, gaps[worst])
    assert checks["G_identity_over_sum_H_at_end"] <= 1e-10
