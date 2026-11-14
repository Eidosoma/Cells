"""The PROPOSED S5 protocol binds the drivers' frozen constants (the lead, 14 November).

Q2's seen seed, spreads, draws per set, defect ladder, threshold, families, targets and near-zero
cases are stated in validation/division/s5_protocol.json and used by
validation/division/q2_rops_comparison.py: changing either without the other fails here. The
judged seeds live in the protocol (and its builder) alone. Q3's judged step and Q10's nominal
closure are bound likewise. Q2's copy of the partition's event checks is bound to event_map
(a staleness guard). Nothing here draws a set or runs a judge entry.
"""

import ast
import inspect
import json
import textwrap
from pathlib import Path

from cells.models.operators import partition
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
    # The third amendment: these three are reported, not judged, on the near-zero cases.
    assert controls["near_zero_reported"] == list(q2.NEAR_ZERO_REPORTED)
    judged = set(q2.CONTROL_TARGETS) - set(q2.NEAR_ZERO_REPORTED)
    assert judged == {"parent charge", "non-conservation", "f", "W"}
    near = controls["near_zero"]
    assert near["members"] == [list(x) for x in q2.NEAR_ZERO]
    assert near["worst_seen"] == list(q2.WORST_SEEN) and q2.WORST_SEEN in q2.NEAR_ZERO
    assert str(q2.NEAR_ZERO_V) in near["rule"]


def assignments(function, names):
    """ast.unparse of each statement in function that assigns one of names, in source order."""
    tree = ast.parse(textwrap.dedent(inspect.getsource(function)))
    found = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.Assign, ast.AugAssign)):
            targets = [node.target] if isinstance(node, ast.AugAssign) else node.targets
            assigned = {n.id for t in targets for n in ast.walk(t) if isinstance(n, ast.Name)}
            if assigned & names:
                found.append((node.lineno, ast.unparse(node)))
    return [statement for _, statement in sorted(found)]


def test_q2s_event_checks_copy_the_event_maps():
    """The staleness guard (the lead, 14 November): q2.event_checks copies the checks that the
    partition's event_map states inline. A check event_map gains, loses or changes, or a change
    to what those checks read, fails here, and so does a drift in event_checks' names."""
    checks = assignments(partition.event_map, {"valid"})
    assert checks == [statement for statement, _ in q2.ENGINE_EVENT_CHECKS]
    reads = {"phi0", "phi1", "scale", "jump", "outside", "image", "amounts", "alive"}
    assert assignments(partition.event_map, reads) == list(q2.ENGINE_EVENT_READS)
    tree = ast.parse(textwrap.dedent(inspect.getsource(q2.event_checks)))
    made = next(
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Assign) and ast.unparse(node.targets[0]) == "checks"
    )
    assert [k.arg for k in made.keywords] == [name for _, name in q2.ENGINE_EVENT_CHECKS]


def test_q3_and_q10_are_the_drivers():
    item = protocol()
    assert item["Q3"]["judged_dt_s"] == q3.DT
    assert item["Q10"]["dt_s"] == 2.5e-4
    assert q10.TAU == 0.002 and q10.APERTURE_TP == q10.NOMINAL_TP  # The nominal overlaps.
