"""Check assembly encounters, paired catalyst factors and the two-state clock on CPU."""

import argparse
import json
import math

import numpy as np
from assembly_mixing import INPUTS

from cells.definitions.specs import parse_spec
from cells.models.assembly_lineages_v2 import IDEAL_MIXING, TRANSITION_STATE, runner, streams
from tests.assembly_lineage_v2_fixtures import CONVENTIONS, definition, species, step
from validation.assembly_lineages_v2 import probes
from validation.ool.references import detailed_balance
from validation.ool.references.common import UNIT_ROUNDOFF
from validation.ool.references.laws import Law
from validation.ool.references.world import Conventions, parse_world


def probe_pair(doc, grid, pair):
    """Get the registered host kernel and an independent reference in the same place/step order."""
    spec = parse_spec(probes._definition(doc, pair, horizon=1.0, events=1, row_every=1))
    law = Law(parse_world(doc), Conventions.from_declared(probes.tokens(pair)))
    names, states = grid["places"], grid["states"]
    assert names == [p.name for p in law.world.finite]
    assert (
        grid["steps"] == [s.name for s in law.world.steps] == [s.id for s in spec.model.world.steps]
    )
    plus, minus, _ = probes.rate_table(spec, names, states)
    ref = detailed_balance.reference_table(law, states)
    for side in ("forward", "reverse"):
        result = detailed_balance.compare_rates(law, states, plus, minus, side, ref)
        assert result.passed, result.as_dict()
    return law, plus, minus, ref


def paired_factors(doc, grid, pair):
    # r3 has one inhibiting D molecule on the common side of A → E in these two states.
    states = list(grid["states"])
    for moving in ("A@membrane", "E@membrane"):
        n = [int(place in (moving, "D@membrane")) for place in grid["places"]]
        if n not in states:
            states.append(n)
    grid = grid | {"states": states}
    bare = doc | {"steps": [s | {"transition_state_factor": []} for s in doc["steps"]]}
    _, base_plus, base_minus, _ = probe_pair(bare, grid, pair)
    law, plus, minus, ref = probe_pair(doc, grid, pair)
    index = {tuple(n): j for j, n in enumerate(grid["states"])}
    errors, observed = [], []
    for n, j in index.items():
        for r, reaction in enumerate(law.world.steps):
            p = tuple(a + d for a, d in zip(n, law.nu[reaction.name], strict=True))
            if p not in index or ref["one_way_plus"][j, r]:
                continue
            k = index[p]
            if not (np.isfinite(ref["ln_plus"][j, r]) and np.isfinite(ref["ln_minus"][k, r])):
                continue
            exact = law.factor(reaction, law.common_state(reaction, n))
            observed.append(exact)
            for ratio in (plus[j, r] / base_plus[j, r], minus[k, r] / base_minus[k, r]):
                errors.append(abs(math.log(ratio) - math.log(exact)))
    assert any(f < 1 for f in observed) and any(f > 1 for f in observed)
    assert max(errors) < 1e-12
    return {
        "states": len(states),
        "edges": len(observed),
        "inhibited": sum(f < 1 for f in observed),
        "accelerated": sum(f > 1 for f in observed),
        "factor_range": [float(min(observed)), float(max(observed))],
        "max_log_error": max(errors),
        "singular_rate_entries": int(np.isposinf(plus).sum() + np.isposinf(minus).sum()),
    }


def boundary(doc, grid, pair):
    _, plus, minus, _ = probe_pair(doc, grid, pair)
    one, two = grid["states"].index([1]), grid["states"].index([2])
    reverse_join, leave, consume_two = (
        grid["steps"].index("x1"),
        grid["steps"].index("x3"),
        grid["steps"].index("x4"),
    )
    return {
        "last_leave_reverse_join_per_s": float(minus[one, reverse_join]),
        "last_leave_forward_per_s": float(plus[one, leave]),
        "two_molecule_leave_per_s": float(plus[two, consume_two]),
    }


def two_state_spec(moving, spectator, k):
    """A ⇌ B in a membrane with one stationary C. Both A and B have zero standard potential."""
    world = {
        "units": {"time": "s", "temperature_K": 298.15, "standard_concentration_mM": 1.0},
        "conventions": CONVENTIONS,
        "species": [species(i, {"x": 1}, bilayer=0.0) for i in "ABC"],
        "phases": {"membrane": {"species": list("ABC")}},
        "steps": [step("isomer", {"A": 1}, {"B": 1}, k, phase="membrane")],
        "free_energy": [{"law": IDEAL_MIXING}],
        "founder": {"A@membrane": 1, "B@membrane": 0, "C@membrane": 1},
    }
    if moving is not None:
        world["rate_factor"] = {
            "law": TRANSITION_STATE,
            "catalysing_phase": "membrane",
            "entries": [
                {"catalyst": i, "step": "isomer", "ddG_kT": energy}
                for i, energy in zip("ABC", (moving, moving, spectator), strict=True)
            ],
        }
    return parse_spec(definition(world, horizon=60.0, event_limit=4, row_every=1, uniforms=True))


def check_clock(spec, exact, draws):
    names = [i + "@membrane" for i in "ABC"]
    plus, minus, _ = probes.rate_table(spec, names, [[1, 0, 1], [0, 1, 1]])
    rates = [float(plus[0, 0]), float(minus[1, 0])]
    run = runner.run(spec)
    events = run.trace["event_channel"].tolist()
    # A and B alternate. At each visit the sole enabled rate is k exp(energy_C).
    expected_times = np.cumsum(-np.log(draws[:, 0]) / exact)
    assert expected_times[-1] < spec.experiment.time_horizon_s
    relative_error = max(abs(rate / exact - 1) for rate in rates)
    log_tol = detailed_balance.TOL_FACTOR * UNIT_ROUNDOFF * (4 + 2 * abs(math.log(exact)))
    rate_ok = all(rate > 0 and abs(math.log(rate) - math.log(exact)) <= log_tol for rate in rates)
    has_trace = events == [1, -1, 1, -1]
    clock_ok = has_trace and np.allclose(
        run.trace["event_time"], expected_times, rtol=1e-12, atol=0
    )
    if has_trace:
        np.testing.assert_array_equal(run.diagnostics["event_uniforms"], draws)
    return {
        "expected_rate_per_s": exact,
        "forward_reverse_per_s": rates,
        "max_relative_rate_error": relative_error,
        "first_expected_s": float(expected_times[0]),
        "first_recorded_s": float(run.trace["event_time"][0]) if events else None,
        "events": len(events),
        "status": run.status,
        "ledger_holds": bool(run.closure["holds"]),
        "world_probe_pairs": run.world_report["pairs"],
        "world_probe_error_kT": run.world_report["max_abs_deviation_ln"],
        "passed": bool(
            rate_ok and clock_ok and run.status == "event_limit" and run.closure["holds"]
        ),
    }


def main(controls_only):
    def load(name):
        return json.loads((INPUTS / name).read_text())

    doc, grid = load("ol1_wa.world.json"), load("ol1_kernel_probe_states.json")
    bd, bg = load("ol1_boundary.world.json"), load("ol1_boundary_probe_states.json")
    comparisons = {probes.pair_name(pair): paired_factors(doc, grid, pair) for pair in probes.PAIRS}
    boundaries = {
        probes.pair_name(pair): boundary(bd, bg, pair)
        for pair in (*probes.PAIRS, ("multinomial", "reversible"))
    }
    k = 1e9
    exact = k * math.exp(-20.0)
    # On these two accessible states the spectator is always the only common molecule.
    # Absorb its constant multiplier into k to get the same clock with no catalyst arithmetic.
    folded = two_state_spec(None, None, exact)
    stream = streams.stream_key_data(streams.base_key_data(1, 0, 0, 0), 0, "events")
    draws = np.stack([streams.uniforms(stream, event, 2) for event in range(4)])
    clocks = {
        "constant_folded_into_k": check_clock(folded, exact, draws),
        "moderate": check_clock(two_state_spec(2.0, -2.0, k), k * math.exp(-2.0), draws),
    }
    if not controls_only:
        clocks["neutral_movers"] = check_clock(two_state_spec(0.0, -20.0, k), exact, draws)
        clocks["opposed_contacts"] = check_clock(two_state_spec(20.0, -20.0, k), exact, draws)
    print(
        json.dumps(
            {"paired_factors": comparisons, "boundary": boundaries, "clocks": clocks},
            indent=2,
            allow_nan=False,
        )
    )
    return all(row["passed"] for row in clocks.values())


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--controls-only", action="store_true", help="run the grids and two well-conditioned clocks"
    )
    raise SystemExit(0 if main(parser.parse_args().controls_only) else 1)
