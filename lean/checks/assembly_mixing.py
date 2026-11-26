"""Check the two membrane free-energy terms in cells.model.assembly_lineages@2 on CPU."""

import json
import math
from fractions import Fraction
from pathlib import Path

import cholesterol_activity
import numpy as np

from cells.definitions.specs import parse_spec
from cells.models.assembly_lineages_v2 import kernel, runner
from validation import id_table
from validation.assembly_lineages_v2 import probes
from validation.ool.references import detailed_balance, ledger
from validation.ool.references.laws import Law
from validation.ool.references.ssa_oracle import ChannelTable
from validation.ool.references.world import Conventions, parse_world

INPUTS = Path(__file__).resolve().parents[2] / "validation/ool/references/designs"
ENERGY_ATOL = 1e-10  # k_BT for absolute state energies in this finite probe.


def check_grid(spec, law, grid):
    names, states = grid["places"], grid["states"]
    assert names == [p.name for p in law.world.finite]
    assert grid["steps"] == [step.id for step in spec.model.world.steps]
    assert grid["steps"] == [step.name for step in law.world.steps]
    plus, minus, free = probes.rate_table(spec, names, states)
    exact = [law.free_energy(tuple(n)) for n in states]
    np.testing.assert_allclose(free, exact, rtol=0, atol=ENERGY_ATOL)

    checks = detailed_balance.check_kernel_table(law, states, plus, minus)
    for result in checks.values():
        assert result.passed, result.as_dict()
    return {
        "states": len(states),
        "max_energy_error_kT": float(np.max(np.abs(free - exact))),
        "reversible_edges": checks["identity"].detail["edges_checked"],
        "max_edge_error_kT": checks["identity"].detail["max_abs_residual"],
        "cycles": checks["kolmogorov"].detail["cycles_checked"],
        "max_cycle_log_ratio": checks["kolmogorov"].detail["max_abs_log_ratio"],
    }


def check_trajectory(spec, law):
    run = runner.run(spec).check()
    world, rows = spec.model.world, run.rows
    events = run.trace["event_channel"]
    assert len(events) == spec.experiment.event_limit and min(events) < 0 < max(events)
    directions = {"forward": 1, "reverse": -1}
    channels = [
        {"step": r["step"], "direction": directions[r["direction"]], "code": r["event_channel"]}
        for r in kernel.channel_table(world)["rows"]
    ]
    counts = rows["place_count"][:, [world.place_index(p.name) for p in law.world.finite]]
    initial = law.world.state_from(law.world.initial_state)
    result = ledger.check_ledger(
        law,
        ChannelTable.from_declared(channels, law),
        initial,
        events,
        rows["row_event"],
        counts,
        rows["event_heat_kT"],
        rows["reservoir_work_kT"],
    )
    assert result.passed, result.as_dict()
    expected = [law.free_energy(tuple(map(int, n))) for n in counts]
    np.testing.assert_allclose(rows["free_energy_kT"], expected, rtol=0, atol=ENERGY_ATOL)
    return {
        "events": len(events),
        "rows": len(counts),
        "max_row_energy_error_kT": float(np.max(np.abs(rows["free_energy_kT"] - expected))),
        "max_independent_closure_kT": float(result.detail["max_abs_closure"]),
    }


def check_binary(ideal, regular, names, offset):
    """χ_AB = 1, both membrane standard potentials zero, step x1 inserts A."""
    world = regular.model.world
    enter = next(i for i, step in enumerate(world.steps) if step.id == "x1")
    results = []
    for b in (3, 30):
        states = [[0] * len(names) for _ in range(2)]
        for j, n in enumerate(states):
            n[names.index("A@membrane")] = b + j
            n[names.index("B@membrane")] = b
        pi, mi, fi = probes.rate_table(ideal, names, states)
        pr, mr, fr = probes.rate_table(regular, names, states)
        N = 2 * b
        expected = float(Fraction(b * b, N * (N + 1)))
        ideal_activity = math.exp(fi[1] - fi[0])
        cost = (fr[1] - fr[0]) - (fi[1] - fi[0])
        np.testing.assert_allclose(
            ideal_activity, float(Fraction(b + 1, N + 1 - offset)), rtol=0, atol=ENERGY_ATOL
        )
        np.testing.assert_allclose(
            [cost, math.log(mr[1, enter] / mi[1, enter])], expected, rtol=0, atol=ENERGY_ATOL
        )
        assert pr[0, enter] == pi[0, enter] > 0
        results.append({"N": N, "ideal_activity": ideal_activity, "excess_insertion_kT": cost})
    return results


def main():
    world = id_table.load(INPUTS / "ol1_wa.world.json")
    grid = json.loads((INPUTS / "ol1_kernel_probe_states.json").read_text())
    report = {}
    for pair in probes.PAIRS:
        conventions = Conventions.from_declared(probes.tokens(pair))
        entries, specs = {}, {}
        for label, doc in (("ideal", world | {"regular_mixing_chi": []}), ("regular", world)):
            law = Law(parse_world(doc), conventions)
            spec = parse_spec(probes._definition(doc, pair, horizon=60.0, events=80, row_every=8))
            specs[label] = spec
            entries[label] = check_grid(spec, law, grid) | check_trajectory(spec, law)
        entries["binary"] = check_binary(
            specs["ideal"], specs["regular"], grid["places"], conventions.c
        )
        report[probes.pair_name(pair)] = entries
        if conventions.c == 0:
            report["cholesterol"] = cholesterol_activity.compare(
                specs["ideal"], specs["regular"], grid["places"]
            )
    print(json.dumps(report, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
