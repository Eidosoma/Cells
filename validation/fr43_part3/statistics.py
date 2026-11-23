"""FR-43 part 3's closed-form statistical checks, with their numbers (REGISTRATION.md §3, §4).

    python -m validation.fr43_part3.statistics run OUT
        C3.3 (feedback off, 16,384 sites, and the plant with the assembly rate 10% high) and
        C3.5 (64 seeds x 128 sites at f = 1/2, and the plant at f = 0.55): every criterion's
        numbers and verdict in OUT/statistics.json; exit 1 unless every registered check passes

tests/unit/test_integer_unit_population_statistics.py asserts the same criteria through these
functions. Run it from a frozen snapshot (PYTHONPATH=SNAPSHOT/src:SNAPSHOT).
"""

import argparse
import json
import math
import sys
from pathlib import Path

import numpy as np

W1 = "W1_two_subunits_feedback"
# §4: C3.3.
SITES, KA, KD, DT, SEED = 16384, 0.5, 1.0, 0.05, 777
TIMES = tuple(0.25 * m for m in range(1, 11))
Z = 3.89  # Bonferroni for 10 comparisons at an overall alpha of 0.001 (two-sided).
PATHWISE_SITES, PATHWISE_BOUND_S, TRACE = 16, 1e-11, 12
# §3: C3.5.
SEEDS, PER_WORLD, BAND = 64, 128, 3.29  # Two-sided 99.9%.


def p0(t, ka=KA, kd=KD):
    """The exact two-state P(no active unit) from (2 free, 0 active), ff(2, 2) = 2."""
    on, off = 2 * ka, kd
    rest = off / (on + off)
    return rest + (1 - rest) * math.exp(-(on + off) * t)


def rows_of(spec, every_step=False):
    from cells.execution.windows import WindowPolicy, iter_windows

    steps = int(round(spec.experiment.end_time / spec.execution.dt))
    policy = WindowPolicy(steps, "full" if every_step else "observations")
    rows = {}
    for window in iter_windows(spec, policy, None):
        for i, t in enumerate(np.asarray(window.times)):
            rows[round(float(t), 9)] = type(window.history)(
                *(np.asarray(v)[i] for v in window.history)
            )
    return rows


def two_state_rows(ka):
    from cells.definitions.specs import parse_spec
    from validation.fr43_part3 import worlds

    raw = worlds.many_sites(
        W1, SITES, dt=DT, end=TIMES[-1], every=0.25, seed=SEED, trace=TRACE,
        rates={"assembly": ka, "disassembly": KD},
    )  # fmt: skip
    return rows_of(parse_spec(raw))


def two_state(rows):
    """Per time: the fraction with no active unit, P0, the band and whether it misses."""
    out = []
    for t in TIMES:
        empty = float(np.mean(rows[round(t, 9)].integer_counts[:, 1] == 0))
        p = p0(t)
        band = Z * math.sqrt(p * (1 - p) / SITES)
        out.append(dict(time_s=t, fraction=empty, p0=p, band=band, miss=abs(empty - p) > band))
    return out


def pathwise(rows):
    """The first PATHWISE_SITES sites' traces against the exact kernel's for the same uniforms:
    (largest |Δt| in s, channel mismatches, events compared)."""
    import jax.numpy as jnp

    from cells.numerics import counter_streams as streams

    last = rows[round(TIMES[-1], 9)]
    worst, mismatches, compared = 0.0, 0, 0
    for s in range(PATHWISE_SITES):
        words = jnp.asarray([streams.key_data(SEED, s, "events")])
        t, counts = 0.0, [2, 0]
        recorded = int(min(last.integer_events[s], last.integer_trace_time_s.shape[1]))
        for k in range(recorded):
            u1, u2 = (float(x) for x in streams.site_uniforms(words, jnp.asarray([k]), 2)[0])
            rates = [KA * counts[0] * (counts[0] - 1), KD * counts[1]]
            a0 = rates[0] + rates[1]
            t += -math.log(u1) / a0
            channel = 0 if rates[0] > min(u2 * a0, math.nextafter(a0, 0.0)) else 1
            counts = [0, 1] if channel == 0 else [2, 0]
            worst = max(worst, abs(float(last.integer_trace_time_s[s, k]) - t))
            mismatches += int(last.integer_trace_channel[s, k] != channel)
            compared += 1
    return worst, mismatches, compared


def split_batch(f):
    """C3.5's batch at area fraction f: (first daughter's active count per draw [N], one-recipient
    and exact-record checks)."""
    from cells.definitions.specs import parse_spec
    from cells.execution.batch import BatchSpec, WorldSpec, run_batch
    from validation.fr43_part3 import worlds

    entries = []
    for seed in range(SEEDS):
        raw = worlds.divided(
            sites=PER_WORLD, transfer=False, counts={"free": 0, "active": 1},
            rates={"assembly": 0.0, "disassembly": 0.0}, f=f, at=0.02, end=0.03, seed=1000 + seed,
            trace=0,
        )  # fmt: skip
        entries.append(WorldSpec(seed + 1, parse_spec(raw)))  # World IDs start at 1.
    result = run_batch(BatchSpec(tuple(entries), SEEDS, 4096, 2**33))  # Padded: steps x worlds.
    firsts, one_each, records = [], True, True
    for world in result.worlds.values():
        counts = np.asarray(world.history.integer_counts)[-1]
        divided = np.asarray(world.history.integer_divided_units)[-1]
        parents, kids = counts[:PER_WORLD], counts[PER_WORLD:].reshape(PER_WORLD, 2, -1)
        one_each &= bool(
            np.all(parents == 0)
            and np.all(np.sort(kids[:, :, 1], axis=1) == [0, 1])
            and np.all(kids[:, :, 0] == 0)
        )
        moved = divided[:PER_WORLD] + divided[PER_WORLD:].reshape(PER_WORLD, 2, -1).sum(axis=1)
        records &= bool(np.all(moved == 0))
        firsts.append(kids[:, 0, 1])
    return np.concatenate(firsts), one_each, records


def splits(f):
    first, one_each, records = split_batch(f)
    n = int(first.size)
    x = int(first.sum())
    half = BAND * math.sqrt(0.25 / n)
    own = BAND * math.sqrt(f * (1 - f) / n)
    return dict(
        f=f, draws=n, first=x, frequency=x / n, band_at_half=half, band_at_own=own,
        exactly_one_recipient=one_each, records_exact=records,
    )  # fmt: skip


def run(out):
    report = {}
    rows = {ka: two_state_rows(ka) for ka in (KA, 1.1 * KA)}
    checks = two_state(rows[KA])
    plant = two_state(rows[1.1 * KA])
    worst, mismatches, compared = pathwise(rows[KA])
    report["C3.3"] = dict(
        criterion="REGISTRATION.md §4",
        sites=SITES, z=Z, times=checks, plant_times=plant,
        passed=not any(c["miss"] for c in checks),
        plant_failed=any(c["miss"] for c in plant),
        pathwise=dict(sites=PATHWISE_SITES, events=compared, max_time_difference_s=worst,
                      channel_mismatches=mismatches,
                      passed=worst <= PATHWISE_BOUND_S and mismatches == 0),
    )  # fmt: skip
    half, plant_split = splits(0.5), splits(0.55)
    report["C3.5"] = dict(
        criterion="REGISTRATION.md §3",
        half=half,
        plant=plant_split,
        passed=half["exactly_one_recipient"]
        and half["records_exact"]
        and abs(half["frequency"] - 0.5) <= half["band_at_half"],
        plant_outside_half_band=abs(plant_split["frequency"] - 0.5) > plant_split["band_at_half"],
        plant_inside_own_band=abs(plant_split["frequency"] - 0.55) <= plant_split["band_at_own"],
    )
    Path(out).mkdir(parents=True, exist_ok=True)
    Path(out, "statistics.json").write_text(json.dumps(report, indent=1) + "\n")
    c33, c35 = report["C3.3"], report["C3.5"]
    ok = (
        c33["passed"] and c33["plant_failed"] and c33["pathwise"]["passed"]
        and c35["passed"] and c35["plant_outside_half_band"] and c35["plant_inside_own_band"]
    )  # fmt: skip
    print("C3.3", c33["passed"], c33["plant_failed"], c33["pathwise"]["passed"])
    print("C3.5", c35["passed"], c35["plant_outside_half_band"], c35["plant_inside_own_band"])
    return 0 if ok else 1


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    r = sub.add_parser("run")
    r.add_argument("out")
    args = parser.parse_args(argv)
    return run(args.out)


if __name__ == "__main__":
    sys.exit(main())
