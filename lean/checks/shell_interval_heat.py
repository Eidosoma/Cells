"""Compare the compiled deterministic shell's interval heat on an invented wash schedule."""

import json
import math

import jax

from cells.definitions.specs import parse_spec
from cells.models.assembly_lineages_v2 import runner
from tests.unit.test_assembly_lineages_v2_rate_equations_population import shell_definition, shell_world
from validation.assembly_lineages_v2.fr47_judge import d_intervals, d_observables, d_stops


INITIAL = 240
FULL_WASH, WITHDRAWAL, HORIZON = 0.625, 1.75, 2.5  # seconds
FRACTION = 0.25
NA = 6.02214076e23


def site(coeff, n, *, plant=False):
    if n == 0:
        return coeff - 1 if plant else 0.0
    return n * (coeff + math.log(n) - 1)


def energy(coeffs, counts, *, plant=False):
    return math.fsum(site(a, n, plant=plant) for a, n in zip(coeffs, counts, strict=True))


def evolve(start, dt, entry, leave):
    pool, lumen = start
    gain = (leave * lumen - entry * pool) * (-math.expm1(-(entry + leave) * dt) / (entry + leave))
    return pool + gain, lumen - gain


def compare():
    delta = math.log(1.5)
    world = shell_world(tracer=INITIAL, delta=delta)
    volumes = [world["phases"][name]["volume_L"] for name in ("pool", "lumen")]
    mu = world["species"][0]["standard_mu_RT"]
    c0 = world["units"]["standard_concentration_mM"] / 1000.0
    coeffs = [mu[phase] - math.log(NA * v * c0)
              for phase, v in zip(("solution", "lumen"), volumes, strict=True)]
    pa = world["steps"][0]["permeability_m_per_s"]["value"] * world["geometry"]["area_m2"]["value"]
    entry = pa / (volumes[0] * 1e-3)
    leave = pa * math.exp(mu["lumen"] - mu["solution"]) / (volumes[1] * 1e-3)
    schedule = (("replacement", FULL_WASH, None), ("withdrawal", WITHDRAWAL, FRACTION))
    reads = (0.25, 1.125, 2.0)
    spec = parse_spec(shell_definition(world, stops=schedule, times=reads, horizon=HORIZON, rtol=1e-10))
    run = runner.run(spec)
    assert run.status == "complete" and run.moieties["closes"] and run.dissipation["holds"]
    assert run.statistics["e2"]["zero_starts"] == 2
    places = ("S@pool", "S@lumen")
    counts = d_observables(run, spec.model.world, places, reads)
    stops = d_stops(run)
    assert [(t, k) for t, k, _, _ in stops] == [(t, k) for k, t, _ in schedule]
    edges = (0.0, FULL_WASH, WITHDRAWAL, HORIZON)
    native = d_intervals(run, [FULL_WASH, WITHDRAWAL], HORIZON)
    intervals = []
    washes = []
    start = (float(INITIAL), 0.0)
    count_atol = 1e-6 * INITIAL
    for i, ((t0, t1, booked), a, b, obs) in enumerate(zip(native, edges[:-1], edges[1:], reads, strict=True)):
        assert (t0, t1) == (a, b)
        predicted = evolve(start, obs - a, entry, leave)
        read = [counts[(place, obs)] for place in places]
        assert all(abs(x - y) <= count_atol for x, y in zip(read, predicted, strict=True))
        end = evolve(start, b - a, entry, leave)
        expected = energy(coeffs, start) - energy(coeffs, end)
        planted = energy(coeffs, start, plant=True) - energy(coeffs, end, plant=True)
        assert min(end) > 0 and expected >= 0
        intervals.append({"start_s": a, "end_s": b, "initial_means": start, "final_means": end,
                          "read_time_s": obs, "count_read": read, "count_prediction": predicted,
                          "booked_kBT": booked, "predicted_kBT": expected, "P9_kBT": planted})
        if i < len(schedule):
            removed = end[0] if i == 0 else FRACTION * end[0]
            assert abs(stops[i][2] - removed) <= count_atol
            washes.append({"time_s": b, "kind": schedule[i][0], "removed": stops[i][2],
                           "predicted_removed": removed, "mixing_heat_kBT": stops[i][3]})
            start = (end[0] - removed, end[1])
    heat_atol = 1e-5 * max(row["predicted_kBT"] for row in intervals)
    for row, bias in zip(intervals, (coeffs[1] - 1, coeffs[0] - 1, 0.0), strict=True):
        assert abs(row["booked_kBT"] - row["predicted_kBT"]) <= heat_atol
        assert math.isclose(row["P9_kBT"] - row["predicted_kBT"], bias, abs_tol=1e-10)
        assert (abs(row["P9_kBT"] - row["booked_kBT"]) > heat_atol) == (bias != 0)
    assert all(row["P9_kBT"] > 0 for row in intervals[:2])
    return {"status": run.status, "zero_starts": run.statistics["e2"]["zero_starts"],
            "input": {"pool_lumen_volumes_L": volumes, "standard_mu_RT": mu, "c0_M": c0,
                      "entry_per_s": entry, "leave_per_s": leave, "initial_tracer": INITIAL,
                      "withdrawn_fraction": FRACTION},
            "intervals": intervals, "washes": washes,
            "count_atol_molecules": count_atol, "heat_atol_kBT": heat_atol,
            "max_abs_heat_error_kBT": max(abs(r["booked_kBT"] - r["predicted_kBT"]) for r in intervals)}


if __name__ == "__main__":
    jax.config.update("jax_enable_x64", True)
    print(json.dumps(compare(), indent=2, allow_nan=False))
