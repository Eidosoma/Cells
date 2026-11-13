"""E07-v1 renewal stage: arm set, replacement schedules, donor rules and the copy-only null.

PROPOSED design (docs/E07_V1_DESIGN.md), not registered. No engine runs here: the null
copies D/H labels only, with no physics. The engine's result for an arm and seed will be
read as its deviation from this null for the same schedule and donor draws: D copies
lost to H, and H copies (or isolated newcomers) converted to D.

Geometry: validation/stationary/worlds.hexagon (the 127-cell held-bath sheet of
heredity_pilot.long_sheet_definition, the same cell and edge order). The disc is the
cells within ring 2 (19 cells) or ring 3 (37 cells) of the centre, as heredity_pilot.

Schedules (the same construction as heredity_turnover_literature.plan):
- scope "sheet" replaces every cell of the sheet; "disc" only the disc's cells;
- the founders share one age, so a seeded permutation of the scope orders them;
  afterwards the oldest carrier is always next. Slot i of the permutation is replaced
  every residence R, with events at (j + 1/2) R / N on the dt grid;
- donor rules: "neighbour", a uniformly drawn junction neighbour of the slot, blind to
  its state (the test arms); "disc_neighbour", a uniformly drawn disc neighbour (the
  control, which passes B1 by construction under copying); "isolated", the H template.
Seeds: replicate r draws the permutation from default_rng([20261113, 0, r]) and the
donors, one per event in event order, from default_rng([20261113, 1, r]).

The null: a newcomer takes its donor's label at the event time, read before any event at
that time (the engine's donor rule), or H when isolated. Records are those of the
engine's arms: every 10 s, each taken before any event at its own time. J is the Jaccard
of the D set against the disc over the whole sheet, as in the pre-screen.

Usage: python -m validation.tissue.e07_v1_turnover null --output DIR [--seeds N]
"""

import argparse
import functools
import json
import platform
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

from validation.stationary import worlds

SHEET_RADIUS = 6
DISC_RINGS = {19: 2, 37: 3}  # As heredity_pilot.DISCS.
SEED_BASE = 20261113
DT = 0.005
RECORD_S = 10.0
END_MARGIN_S = 300.0
CUE_OFF_S, START_S = 2.5, 120.0  # Stage B starts from sheet70's state at 120 s.
B1_J = 0.8
BRACKETS = dict(
    fast=dict(lag_s=120.0, time_constant_s=900.0),
    central=dict(lag_s=600.0, time_constant_s=1800.0),
)
# Threshold-finding (labelled so): the fast bracket's shape (lag = 2 tau / 15) at shorter
# tau, at the fast k1 residence. tau 40 s is the engine minimum and was seen only after the
# pre-screen's predictions were frozen; it tests no literature value.
LADDER_TAU_S = (40.0, 120.0, 300.0)
FAST_RESIDENCE_S = 1020.0  # k1 of the fast bracket: lag + tau.


def ladder_formation(tau):
    return dict(lag_s=tau * 2.0 / 15.0, time_constant_s=tau)


def _arm(group, label, kind, scope, rule, size, s, formation, residence, seeds, note):
    return dict(
        id=f"{group}-{label}-d{size}-s{s}",
        group=group,
        kind=kind,
        scope=scope,
        rule=rule,
        size=size,
        s=s,
        formation=dict(formation),
        residence_s=residence,
        end_s=2 * residence + END_MARGIN_S,
        seeds=list(seeds),
        note=note,
    )


def arm_set():
    """The PROPOSED arm set: (a) test, (b) threshold-finding, (c) control."""
    held = ((37, 1.0), (37, 0.6), (37, 0.3), (19, 0.6), (19, 0.3))
    fast, central = BRACKETS["fast"], BRACKETS["central"]
    arms = []
    for size, s in held:
        arms.append(
            _arm("a", "donor-fast-k1", "donor", "sheet", "neighbour", size, s, fast,
                 FAST_RESIDENCE_S, (1, 2, 3, 4),
                 "inheritance route; state-blind replacement and donors")
        )  # fmt: skip
    for size, s in ((37, 1.0), (37, 0.6)):
        arms.append(
            _arm("a", "donor-central-k1", "donor", "sheet", "neighbour", size, s, central,
                 central["lag_s"] + central["time_constant_s"], (1, 2),
                 "inheritance route; central bracket; ends 87 min after the cue")
        )  # fmt: skip
    for size, s in ((37, 1.0), (37, 0.6)):
        for tau in LADDER_TAU_S:
            arms.append(
                _arm("b", f"iso-tau{tau:g}", "iso", "sheet", "isolated", size, s,
                     ladder_formation(tau), FAST_RESIDENCE_S, (1,),
                     "threshold-finding: tau below the literature range")
            )  # fmt: skip
    for size, s in ((37, 1.0), (37, 0.6)):
        arms.append(
            _arm("c", "disconly-fast-k1", "donor", "disc", "disc_neighbour", size, s, fast,
                 FAST_RESIDENCE_S, (1,),
                 "control: disc slots and disc donors pass B1 by construction under copying")
        )  # fmt: skip
    return arms


# ------------------------------------------------------------------ geometry


@functools.cache
def sheet():
    cells, edges = worlds.hexagon(SHEET_RADIUS)
    neighbours = {i: [] for i in range(len(cells))}
    for a, b in edges:
        neighbours[a].append(b)
        neighbours[b].append(a)
    return cells, edges, {i: sorted(v) for i, v in neighbours.items()}


@functools.cache
def disc(size):
    cells, _, _ = sheet()
    return frozenset({i for i, c in enumerate(cells) if worlds.ring(c) <= DISC_RINGS[size]})


# ------------------------------------------------------------------ schedules


def rngs(seed):
    return (
        np.random.default_rng([SEED_BASE, 0, int(seed)]),
        np.random.default_rng([SEED_BASE, 1, int(seed)]),
    )


def plan(*, scope, rule, size, residence_s, end_s, seed, dt=DT):
    """Events [(step, slot, donor or None)] of one arm and seed, and the turnover times."""
    cells, _, neighbours = sheet()
    inside = disc(size)
    slots = list(range(len(cells))) if scope == "sheet" else sorted(inside)
    if scope not in ("sheet", "disc") or rule not in ("neighbour", "disc_neighbour", "isolated"):
        raise ValueError((scope, rule))
    order, donors = rngs(seed)
    permutation = [int(v) for v in order.permutation(slots)]
    n, interval = len(slots), residence_s / len(slots)
    events, j = [], 0
    while True:
        step = int(round((j + 0.5) * interval / dt))
        if step * dt >= end_s - dt:
            break
        slot = permutation[j % n]
        donor = None
        if rule == "neighbour":
            donor = int(donors.choice(neighbours[slot]))
        elif rule == "disc_neighbour":
            donor = int(donors.choice([k for k in neighbours[slot] if k in inside]))
        events.append((step, slot, donor))
        j += 1
    return dict(
        events=events,
        permutation=permutation,
        interval_s=interval,
        turnover_complete_s=[(n - 0.5) * interval, (2 * n - 0.5) * interval],
    )


# ------------------------------------------------------------------ the null


def null_series(events, size, end_s, *, dt=DT, record_s=RECORD_S, n_cells=None):
    """Copy-only labels at the engine's regular records (t = 0 and every record_s)."""
    n_cells = n_cells or len(sheet()[0])
    inside = np.zeros(n_cells, dtype=bool)
    inside[sorted(disc(size))] = True
    label = inside.copy()
    times = np.round(np.arange(0.0, end_s + 1e-9, record_s), 9)
    out = dict(t=times, J=[], d_inside=[], d_outside=[])
    k = 0
    for t in times:
        # Apply every event strictly before this record; events at one step read their
        # donors before any of them is applied.
        while k < len(events) and events[k][0] * dt < t - 1e-9:
            step = events[k][0]
            batch = []
            while k < len(events) and events[k][0] == step:
                batch.append(events[k])
                k += 1
            new = [
                (slot, False if donor is None else bool(label[donor])) for _, slot, donor in batch
            ]
            for slot, value in new:
                label[slot] = value
        union = np.sum(label | inside)
        out["J"].append(float(np.sum(label & inside) / union) if union else 1.0)
        out["d_inside"].append(int(label[inside].sum()))
        out["d_outside"].append(int(label[~inside].sum()))
    return {key: np.asarray(v) for key, v in out.items()}


def series_summary(series, turnover):
    """The readouts of the engine arms' analysis, on a null series."""
    t, j = series["t"], series["J"]

    def at_or_before(x):
        return float(j[np.searchsorted(t, x + 1e-9) - 1])

    through = t <= turnover[1] + 1e-9
    below = np.flatnonzero(j < B1_J)
    window = [(t > 0) & (t <= turnover[0] + 1e-9), (t > turnover[0]) & (t <= turnover[1] + 1e-9)]
    return dict(
        J_after_turnover=[at_or_before(x) for x in turnover],
        J_min_in_turnover=[float(j[w].min()) for w in window],
        b1=bool(np.all(j[through] >= B1_J)),
        first_J_below_0p8_s=None if not len(below) else float(t[below[0]]),
        d_inside_end=int(series["d_inside"][-1]),
        d_outside_max=int(series["d_outside"].max()),
        d_total_end=int(series["d_inside"][-1] + series["d_outside"][-1]),
        all_H_by_end=bool(series["d_inside"][-1] + series["d_outside"][-1] == 0),
    )


def distribution(scope, rule, size, residence_s, end_s, seeds):
    """Null readouts over replicate seeds, with quantile bands of J(t)."""
    rows, js, first = [], [], None
    for seed in seeds:
        p = plan(scope=scope, rule=rule, size=size, residence_s=residence_s, end_s=end_s, seed=seed)
        series = null_series(p["events"], size, end_s)
        rows.append(series_summary(series, p["turnover_complete_s"]))
        js.append(series["J"])
        first = first or (series["t"], p["turnover_complete_s"])
    js = np.array(js)
    q = (0.05, 0.25, 0.5, 0.75, 0.95)

    def quant(values):
        return dict(zip([f"q{int(100 * x):02d}" for x in q],
                        np.quantile(values, q).tolist(), strict=True))  # fmt: skip

    return dict(
        scope=scope,
        rule=rule,
        size=size,
        residence_s=residence_s,
        end_s=end_s,
        seeds=len(seeds),
        turnover_complete_s=first[1],
        b1_probability=float(np.mean([r["b1"] for r in rows])),
        J_after_first_turnover=quant([r["J_after_turnover"][0] for r in rows]),
        J_after_second_turnover=quant([r["J_after_turnover"][1] for r in rows]),
        J_min_first_turnover=quant([r["J_min_in_turnover"][0] for r in rows]),
        d_total_end=quant([r["d_total_end"] for r in rows]),
        d_outside_max=quant([r["d_outside_max"] for r in rows]),
        all_H_by_end_probability=float(np.mean([r["all_H_by_end"] for r in rows])),
        band=dict(
            t_s=first[0].tolist(),
            **{
                k: np.quantile(js, x, axis=0).tolist()
                for k, x in zip(("q05", "q50", "q95"), (0.05, 0.5, 0.95), strict=True)
            },
        ),  # fmt: skip
    )


PRESCREEN = Path("/mnt/workspaces/Cells/heredity-turnover-literature-20261111-01/arms")


def prescreen_check(directory=PRESCREEN):
    """The null on each pre-screen arm's own events, against that arm's engine J series.

    Where the engine lost no D carrier and converted no newcomer, the two must be
    identical record by record; elsewhere their difference is the engine's deviation.
    """
    out = {}
    for arm in sorted(p for p in directory.iterdir() if (p / "outcome.json").exists()):
        if ".killed" in arm.name:
            continue
        p = json.loads((arm / "plan.json").read_text())
        o = json.loads((arm / "outcome.json").read_text())
        events = [
            (int(k), int(slot), None if d is None else int(d)) for k, slot, d, _ in p["events"]
        ]
        series = null_series(events, p["size"], o["end_s"])
        engine_t = np.round(np.asarray(o["series"]["t_s"]), 9)
        engine_j = np.asarray(o["series"]["jaccard"])
        null_j = dict(zip(series["t"].tolist(), series["J"].tolist(), strict=True))
        diff = np.array([e - null_j[float(t)] for t, e in zip(engine_t, engine_j, strict=True)])
        out[arm.name] = dict(
            records=len(diff),
            identical_records=int(np.sum(diff == 0)),
            max_abs_difference=float(np.max(np.abs(diff))),
            engine_minus_null_at_end=float(diff[-1]),
            first_difference_s=None
            if not np.any(diff)
            else float(engine_t[np.flatnonzero(diff)[0]]),
            founders_lost=o["founders_lost_before_replacement"],
            d_copies_lost=o["d_newcomers_lost_before_replacement"],
            isolated_converted=o["isolated_newcomers_ever_D"],
        )
    return out


def provenance():
    git = ["git", "-C", str(Path(__file__).resolve().parents[2])]

    def run(*a):
        return subprocess.run([*git, *a], capture_output=True, text=True).stdout.strip()

    return dict(argv=sys.argv, host=platform.node(), revision=run("rev-parse", "HEAD") or None,
                dirty=run("status", "--porcelain", "--untracked-files=no"),
                source=str(Path(__file__).resolve()))  # fmt: skip


def part_null(args):
    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)
    tick = time.perf_counter()
    seeds = range(1, args.seeds + 1)
    configs = {}
    for size in (37, 19):
        for label, residence in (("fast-k1", FAST_RESIDENCE_S), ("central-k1", 2400.0)):
            end = 2 * residence + END_MARGIN_S
            for name, scope, rule in (
                ("state-blind donors, whole sheet (test)", "sheet", "neighbour"),
                ("disc slots, disc donors (control)", "disc", "disc_neighbour"),
                ("isolated templates, whole sheet (boundary reference)", "sheet", "isolated"),
                ("disc slots, state-blind donors (the pre-screen's design)", "disc", "neighbour"),
            ):  # fmt: skip
                key = f"{scope}-{rule}-d{size}-{label}"
                configs[key] = dict(
                    description=name, **distribution(scope, rule, size, residence, end, seeds)
                )
                c = configs[key]
                print(f"{key}: P(B1) {c['b1_probability']:.3f}, J T1 median "
                      f"{c['J_after_first_turnover']['q50']:.3f}, T2 median "
                      f"{c['J_after_second_turnover']['q50']:.3f}", flush=True)  # fmt: skip
    registered = {}
    for arm in arm_set():
        for seed in arm["seeds"]:
            p = plan(scope=arm["scope"], rule=arm["rule"], size=arm["size"],
                     residence_s=arm["residence_s"], end_s=arm["end_s"], seed=seed)  # fmt: skip
            series = null_series(p["events"], arm["size"], arm["end_s"])
            registered[f"{arm['id']}/seed{seed}"] = dict(
                events=len(p["events"]),
                isolated_events=sum(d is None for _, _, d in p["events"]),
                **series_summary(series, p["turnover_complete_s"]),
                series=dict(t_s=series["t"].tolist(), J=series["J"].tolist(),
                            d_inside=series["d_inside"].tolist(),
                            d_outside=series["d_outside"].tolist()),
            )  # fmt: skip
    value = dict(
        kind="cells.e07_v1_copy_only_null@1",
        status="PROPOSED design; no engine run; labels copied only",
        seeds_per_distribution=args.seeds,
        configurations=configs,
        registered_seeds=registered,
        prescreen_check=prescreen_check(),
        arm_set=arm_set(),
        wall_s=time.perf_counter() - tick,
        provenance=provenance(),
    )
    path = out / "null.json"
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(value, indent=1) + "\n")
    tmp.replace(path)
    print(f"null: {len(configs)} configurations, {len(registered)} registered seeds, "
          f"{value['wall_s']:.1f} s", flush=True)  # fmt: skip


def part_offsets(args):
    """D147 on E07-v1's worlds: free field offsets of the pre-screen's sheet definitions.

    The same held-bath sheets (one per disc and s) that E07-v1 rebuilds. Parsing and the
    layout only; nothing is stepped.
    """
    from validation.tissue import field_solver_choice

    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)
    rows = {}
    for arm in sorted(PRESCREEN.iterdir()):
        name = arm.name
        if not name.startswith("donor-fast-k1-") or ".killed" in name:
            continue
        raw = json.loads((arm / "definition.json").read_text())
        rows[name.removeprefix("donor-fast-k1-")] = dict(
            free_field_offsets=field_solver_choice.free_field_offsets(raw),
            declared=raw["execution"].get("field_solver"),
            auto_choice=field_solver_choice.solver_for(raw, "auto"),
        )
    value = dict(kind="cells.e07_v1_field_offsets@1", decision="D147", worlds=rows,
                 provenance=provenance())  # fmt: skip
    (out / "offsets.json").write_text(json.dumps(value, indent=1) + "\n")
    print(json.dumps(rows), flush=True)


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("part", choices=["null", "offsets"])
    parser.add_argument("--output", required=True)
    parser.add_argument("--seeds", type=int, default=2000)
    args = parser.parse_args(argv)
    (part_null if args.part == "null" else part_offsets)(args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
