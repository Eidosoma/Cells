"""Replay the Phase A pore rate, tension hold and heat in single and shared-pool vesicles.

Print the measured controls and return nonzero if any hold endpoint changes the exact
event classification for the same binary64 rate, threshold and interval.
"""

import json
import math
from fractions import Fraction

from cells.definitions.specs import parse_spec
from cells.models.assembly_lineages_v2 import pore_clock, pore_nucleation, runner
from tests.unit import test_assembly_lineages_v2_pores as fixture


def rate_controls():
    spec = parse_spec(fixture.pore_definition())
    world = spec.model.world
    log_nu, gamma, activation, _ = pore_nucleation.parameters(world)
    temp = world.units.temperature_K
    largest = pore_nucleation.sigma_beta(gamma, temp) / 4
    points = []
    for tension in (fixture.SIGMA / 2, fixture.SIGMA, largest):
        parse_spec(fixture.pore_definition(sigma=tension))

        def log_rate(temperature, area=fixture.AREA):
            return pore_nucleation.log_rate(area, tension, temperature, log_nu, gamma, activation)

        ratio = math.exp(log_rate(temp, 2 * fixture.AREA) - log_rate(temp))
        slope = pore_nucleation.dlog_rate_dt(tension, temp, gamma, activation)
        # A backward difference keeps both probes within the admitted tension range at its edge.
        h = 0.01
        difference = (3 * log_rate(temp) - 4 * log_rate(temp - h) + log_rate(temp - 2 * h)) / (2 * h)
        assert math.isclose(ratio, 2.0, rel_tol=1e-13)
        assert math.isclose(slope, difference, rel_tol=1e-7) and temp * slope > 2.5
        assert log_rate(temp - 1) < log_rate(temp)
        points.append(dict(tension_N_per_m=tension, doubled_area_rate_ratio=ratio,
                           scaled_temperature_slope=temp * slope, finite_difference_per_K=difference))
    return points


def threshold_controls():
    spec = parse_spec(fixture.pore_definition(start=0.5, end=4.5))
    world, holds = spec.model.world, spec.experiment.tension_holds
    rate = math.exp(pore_clock.log_rate(world, fixture.AREA, holds[0].sigma))
    times = []
    for fraction in (0.75, 1.0, 1.25):
        energy = fraction * (4.0 * rate)
        t, chosen, _ = pore_clock.rupture_time(world, holds, fixture.AREA, energy)
        if fraction == 0.75:
            assert chosen == holds[0] and math.isclose(t, 3.5, rel_tol=0, abs_tol=2 * math.ulp(3.5))
        elif fraction == 1:
            assert chosen == holds[0] and t == holds[0].end
        else:
            assert chosen is None and t == math.inf
        times.append(t if chosen else None)
    return times


def heats(event):
    return event["opening_heat_kT"], event["release"]["release_heat_kT"]


def population_survival(events, per_area):
    # One second of exposure for the two equally weighted founders, using their recorded rates.
    areas = [e["area_m2"] for e in events]
    lo, hi = min(areas), max(areas)
    mean = sum(areas) / len(areas)
    lower = math.exp(-per_area * mean)
    fraction_hi = (mean - lo) / (hi - lo)
    upper = (1 - fraction_hi) * math.exp(-per_area * lo) + fraction_hi * math.exp(-per_area * hi)
    mixture = sum(math.exp(-e["rate_per_s"]) for e in events) / len(events)
    assert lower < mixture and math.isclose(mixture, upper, rel_tol=1e-13)
    return dict(duration_s=1.0, at_mean_area=lower, from_engine_rates=mixture, upper_chord=upper)


def host_controls():
    spec, base = fixture.single_run()
    _, scaled = fixture.single_run(eta=10 * fixture.ETA_298)
    _, population = fixture.population_run()
    assert base.status == scaled.status == "lysed"
    assert base.closure["holds"] and scaled.closure["holds"] and population.closure["holds"]
    (first,), (second,) = base.pores["events"], scaled.pores["events"]
    assert (first["time_s"], first["work_kT"]) == (second["time_s"], second["work_kT"])
    opening, release = heats(first)
    moved_open, moved_release = heats(second)
    assert math.isclose(moved_open - opening, math.log(10), rel_tol=0, abs_tol=1e-12)
    assert math.isclose(moved_release - release, -math.log(10), rel_tol=0, abs_tol=1e-12)
    total_change = float(scaled.rows["event_heat_kT"][-1] - base.rows["event_heat_kT"][-1])
    assert abs(total_change) <= 1e-12
    by_key = {event["key"]: event for event in population.pores["events"]}
    assert set(by_key) == {key for key, _ in fixture.FOUNDERS}
    per_area = first["rate_per_s"] / first["area_m2"]
    for event in [first, *by_key.values()]:
        expected_work, _ = fixture.sheet_opening(spec, area=event["area_m2"])
        close = pore_nucleation.collapse_rate(event["sigma_N_per_m"], fixture.T_K,
                                               fixture.GAMMA, fixture.E_A, fixture.ETA_298)
        assert math.isclose(event["rate_per_s"] / event["area_m2"], per_area, rel_tol=1e-13)
        assert math.isclose(event["work_kT"], expected_work, rel_tol=1e-13)
        assert abs(math.log(event["rate_per_s"] / close) - event["opening_heat_kT"]) <= 1e-12
    return dict(single_time_s=first["time_s"], work_kT=first["work_kT"],
                opening_heat_shift_kT=moved_open - opening, release_heat_shift_kT=moved_release - release,
                final_heat_change_kT=total_change, population_events=len(by_key),
                survival=population_survival(by_key.values(), per_area)), first


def endpoint_controls(first):
    # The founder's real stream draw and its computed rate are identical in the two modes.
    # The three declared endpoints straddle the crossing. Fractions preserve every input bit.
    start = 1.0
    energy, rate = first["threshold_E"], first["rate_per_s"]
    crossing = Fraction(start) + Fraction(energy) / Fraction(rate)
    center = float(crossing)
    cases = []
    for end in (math.nextafter(center, -math.inf), center, math.nextafter(center, math.inf)):
        expected = crossing <= Fraction(end)
        observed = {}
        for mode in ("lineage", "population"):
            world = fixture.pore_world(population=mode == "population")
            spec = parse_spec(fixture.pore_definition(world, start=start, end=end, horizon=2.0))
            result = runner.run(spec)
            assert result.closure["holds"]
            events = [e for e in result.pores["events"] if e["key"] == first["key"]]
            assert len(events) <= 1
            if events:
                event = events[0]
                assert (event["threshold_E"], event["rate_per_s"]) == (energy, rate)
                assert start <= event["time_s"] <= end
            observed[mode] = events[0]["time_s"] if events else None
        deficit = Fraction(energy) - Fraction(rate) * (Fraction(end) - Fraction(start))
        cases.append(dict(hold_end_s=end, exact_crossing_minus_end_s=float(crossing - Fraction(end)),
                          exact_threshold_minus_exposure=str(deficit),
                          rounded_exposure_reaches_threshold=rate * (end - start) >= energy,
                          expected_event=expected, event_time_s=observed,
                          matches_exact=all((t is not None) == expected for t in observed.values())))
    return dict(start_s=start, threshold=energy, rate_per_s=rate, cuts=cases)


if __name__ == "__main__":
    rates, thresholds = rate_controls(), threshold_controls()
    results, founder = host_controls()
    endpoints = endpoint_controls(founder)
    print(json.dumps(dict(rate=rates, threshold_times_s=thresholds, host=results, endpoint=endpoints),
                     indent=2, allow_nan=False))
    raise SystemExit(0 if all(row["matches_exact"] for row in endpoints["cuts"]) else 1)
