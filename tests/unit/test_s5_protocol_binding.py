"""The PROPOSED S5 protocol binds the drivers' frozen constants (the lead, 14 November).

Q2's seen seed, spreads, draws per set, defect ladder, threshold, families, targets and near-zero
cases are stated in validation/division/s5_protocol.json and used by
validation/division/q2_rops_comparison.py: changing either without the other fails here. The
judged seeds live in the protocol (and its builder) alone. Q3's judged step and Q10's nominal
closure are bound likewise. Nothing here draws a set or runs a judge entry.
"""

import json
from pathlib import Path

from validation.division import q2_rops_comparison as q2
from validation.division import q3_tissue_comparison as q3
from validation.division import q10_sensitivity as q10
from validation.division import s5_protocol


def protocol():
    return json.loads(s5_protocol.PROTOCOL.read_text())


def judged_seeds():
    return protocol()["Q2"]["random_sets"]["judged"]["seeds"]


def test_q2s_random_sets_are_the_drivers():
    item = protocol()["Q2"]["random_sets"]
    assert item["spreads_declared_charges"] == list(q2.SPREADS)
    assert item["draws_per_set"] == q2.RANDOM_STATES
    assert item["seen"]["seed"] == q2.SEEN_SEED
    seeds = judged_seeds()
    assert set(seeds) == set(q2.random_worlds())
    assert all(set(w) == {f"spread {s:g}" for s in q2.SPREADS} for w in seeds.values())
    flat = [s for w in seeds.values() for s in w.values()]
    assert len(set(flat)) == len(flat) == 6 and q2.SEEN_SEED not in flat
    assert seeds == s5_protocol.JUDGED_SEEDS


def test_the_judged_seeds_are_the_protocols_alone():
    source = Path(q2.__file__).read_text()
    for world in judged_seeds().values():
        for seed in world.values():
            assert str(seed) not in source


def test_q2s_controls_are_the_drivers():
    controls = protocol()["Q2"]["negative_controls"]
    assert controls["deltas"] == list(q2.DEFECTS)
    assert controls["threshold"] == q2.THRESHOLD
    assert controls["families"] == {k: list(v) for k, v in q2.CONTROL_GROUPS.items()}
    assert controls["targets"] == {k: list(v) for k, v in q2.CONTROL_TARGETS.items()}
    assert set(controls["defects"]) == set(q2.CONTROL_TARGETS)
    near = controls["near_zero"]
    assert near["members"] == [list(x) for x in q2.NEAR_ZERO]
    assert near["worst_seen"] == list(q2.WORST_SEEN) and q2.WORST_SEEN in q2.NEAR_ZERO
    assert str(q2.NEAR_ZERO_V) in near["rule"]


def test_q3_and_q10_are_the_drivers():
    item = protocol()
    assert item["Q3"]["judged_dt_s"] == q3.DT
    assert item["Q10"]["dt_s"] == 2.5e-4
    assert q10.TAU == 0.002 and q10.APERTURE_TP == q10.NOMINAL_TP  # The nominal overlaps.
