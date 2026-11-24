"""FR-43 part 3's registered comparison with the same-draws references (REGISTRATION.md §1, §2).

    python -m validation.fr43_part3.compare run OUT [--only WORLD:DT ...]
        the engine's traces of W1, W2 and W4 at 20 and 5 ms and of W3 at 20, 10, 5, 2.5 and
        1.25 ms, one JSON per world and step under OUT/engine/ (times as float.hex)
    python -m validation.fr43_part3.compare judge OUT REFERENCES
        the registered criteria against the references' results (REFERENCES/<world>.json, the
        spec's requested_outputs), written to OUT/verdict.json; exit 1 unless every world passes

The engine records each event's time, channel and the route's two pools (the operator's trace);
the counts after each event follow from the initial counts and the channels. Run it from a frozen
snapshot (PYTHONPATH=SNAPSHOT/src:SNAPSHOT) so the record names the source it ran.
"""

import argparse
import json
import math
import sys
import time
from pathlib import Path

import numpy as np

EXACT_WORLDS = (
    "W1_two_subunits_feedback",
    "W2_four_subunits_feedback",
    "W4_four_subunits_node_read",
)
EXACT_STEPS = (0.02, 0.005)
ORDER_WORLD = "W3_two_way_turnover"
ORDER_STEPS = (0.02, 0.01, 0.005, 0.0025, 0.00125)
TIME_BOUND_S = 1e-9  # §1, against the reference.
POOL_BOUND_FMOL = 1e-9  # §1.
SELF_BOUND_S = 1e-11  # §1, the engine's two steps against each other.
ORDER_BAND = (1.7, 2.3)  # §2, the least-squares slope.
PHASE_FACTOR = 4.0  # §2, max/min of RMS/dt^2 over the window.
FINEST_RMS_S = 1e-6  # §2, at 1.25 ms.
REFERENCE_ACCURACY_S = 1e-10  # The spec's declared target; above it the comparison is inconclusive.


def engine_trace(world_id, dt):
    """The engine's trace of one spec world at one step: a JSON-ready record."""
    from cells.definitions.specs import parse_spec
    from cells.execution.windows import WindowPolicy, iter_windows
    from validation.fr43_part3 import worlds

    world = worlds.spec_worlds()[world_id]
    end = world["horizon_s"]
    spec = parse_spec(worlds.spec_world(world_id, dt=dt, end=end, every=end))
    steps = int(round(end / dt))
    start = time.perf_counter()
    last = None
    for window in iter_windows(spec, WindowPolicy(steps, "observations"), None):
        last = type(window.history)(*(np.asarray(v)[-1] for v in window.history))
    wall = time.perf_counter() - start
    events = int(last.integer_events[0])
    recorded = min(events, last.integer_trace_time_s.shape[1])
    if recorded < events:
        raise SystemExit(f"{world_id} at {dt}: {events} events above the trace's capacity")
    names = [c["id"] for c in world["channels"]]
    states = [u["id"] for u in world["unit_states"]]
    counts = [world["initial_counts"][s] for s in states]
    rows = []
    for k in range(recorded):
        channel = names[int(last.integer_trace_channel[0, k])]
        spec_channel = world["channels"][names.index(channel)]
        for s, r in spec_channel["reactants"].items():
            counts[states.index(s)] -= r
        for s, r in spec_channel["products"].items():
            counts[states.index(s)] += r
        rows.append(
            dict(
                k=k,
                time_s=float(last.integer_trace_time_s[0, k]).hex(),
                channel=channel,
                counts_after=dict(zip(states, counts, strict=True)),
                cell_S_fmol=float(last.integer_trace_cell_fmol[0, k, 0]).hex(),
                node_S_fmol=float(last.integer_trace_node_fmol[0, k, 0]).hex(),
            )
        )
    return dict(world=world_id, dt_s=dt, steps=steps, wall_s=wall, events=rows)


def run(out, only=None):
    target = Path(out) / "engine"
    target.mkdir(parents=True, exist_ok=True)
    plan = [(w, dt) for w in EXACT_WORLDS for dt in EXACT_STEPS]
    plan += [(ORDER_WORLD, dt) for dt in ORDER_STEPS]
    if only:
        plan = [(w, dt) for w, dt in plan if f"{w}:{dt}" in only]
    for world_id, dt in plan:
        record = engine_trace(world_id, dt)
        path = target / f"{world_id}-{dt}.json"
        path.write_text(json.dumps(record, indent=1) + "\n")
        print(world_id, dt, len(record["events"]), "events", round(record["wall_s"], 1), "s")


def _engine(out, world_id, dt):
    record = json.loads((Path(out) / "engine" / f"{world_id}-{dt}.json").read_text())
    return record["events"]


def _times(events, key="time_s"):
    out = []
    for e in events:
        value = e[key]
        out.append(float.fromhex(value) if isinstance(value, str) else float(value))
    return np.asarray(out)


def _reference(references, world_id):
    doc = json.loads((Path(references) / f"{world_id}.json").read_text())
    horizon = 20.0
    events = [e for e in doc["events"] if float(e["time_s"]) <= horizon]
    return doc, events


def reported_accuracy(doc):
    """The reference's largest reported event-time difference between its methods (s): the
    maximum of every cross-check's max_event_time_diff_s in its accuracy record; None when it
    reports none (then the comparison is inconclusive)."""
    found = [
        float(v["max_event_time_diff_s"])
        for v in doc.get("accuracy", {}).values()
        if isinstance(v, dict) and "max_event_time_diff_s" in v
    ]
    return max(found) if found else None


def judge_exact(out, references, world_id):
    doc, ref = _reference(references, world_id)
    verdict = dict(world=world_id, criterion="REGISTRATION.md §1", steps={})
    reported = reported_accuracy(doc)
    inconclusive = reported is None or reported > REFERENCE_ACCURACY_S
    passed = True
    traces = {}
    for dt in EXACT_STEPS:
        eng = _engine(out, world_id, dt)
        traces[dt] = _times(eng)
        same = len(eng) == len(ref) and all(
            a["channel"] == b["channel"] and a["counts_after"] == b["counts_after"]
            for a, b in zip(eng, ref, strict=False)
        )
        dt_times = np.abs(_times(eng)[: len(ref)] - _times(ref)[: len(eng)])
        pools = [
            max(
                abs(float.fromhex(a["cell_S_fmol"]) - float(b["cell_S_fmol"])),
                abs(float.fromhex(a["node_S_fmol"]) - float(b["node_S_fmol"])),
            )
            for a, b in zip(eng, ref, strict=False)
        ]
        row = dict(
            events=len(eng),
            reference_events=len(ref),
            same_events_channels_counts=bool(same),
            max_time_difference_s=float(dt_times.max(initial=0.0)),
            max_pool_difference_fmol=float(max(pools, default=0.0)),
        )
        row["passed"] = bool(
            same
            and row["max_time_difference_s"] <= TIME_BOUND_S
            and row["max_pool_difference_fmol"] <= POOL_BOUND_FMOL
        )
        verdict["steps"][str(dt)] = row
        passed &= row["passed"]
    a, b = traces[EXACT_STEPS[0]], traces[EXACT_STEPS[1]]
    self_gap = float(np.abs(a - b).max(initial=0.0)) if len(a) == len(b) else math.inf
    verdict["engine_steps_gap_s"] = self_gap
    passed &= self_gap <= SELF_BOUND_S
    verdict["reference_reported_accuracy_s"] = reported
    verdict["result"] = "inconclusive" if inconclusive else ("pass" if passed else "fail")
    return verdict


def judge_order(out, references):
    doc, ref = _reference(references, ORDER_WORLD)
    rt = _times(ref)
    rms, worst, same = [], [], True
    for dt in ORDER_STEPS:
        eng = _engine(out, ORDER_WORLD, dt)
        same &= len(eng) == len(ref) and all(
            a["channel"] == b["channel"] for a, b in zip(eng, ref, strict=False)
        )
        n = min(len(eng), len(ref))
        e = np.abs(_times(eng)[:n] - rt[:n])
        rms.append(float(np.sqrt(np.mean(e**2))))
        worst.append(float(e.max()))
    slope = float(np.polyfit(np.log(ORDER_STEPS), np.log(rms), 1)[0])
    scaled = [r / dt**2 for r, dt in zip(rms, ORDER_STEPS, strict=True)]
    factor = max(scaled) / min(scaled)
    passed = (
        same
        and ORDER_BAND[0] <= slope <= ORDER_BAND[1]
        and factor <= PHASE_FACTOR
        and rms[-1] <= FINEST_RMS_S
    )
    return dict(
        world=ORDER_WORLD,
        criterion="REGISTRATION.md §2",
        steps_s=list(ORDER_STEPS),
        same_events_and_channels=bool(same),
        rms_error_s=rms,
        max_error_s=worst,
        least_squares_order_rms=slope,
        least_squares_order_max=float(np.polyfit(np.log(ORDER_STEPS), np.log(worst), 1)[0]),
        rms_over_dt2=scaled,
        phase_factor=factor,
        result="pass" if passed else "fail",
    )


def judge(out, references):
    verdicts = [judge_exact(out, references, w) for w in EXACT_WORLDS]
    verdicts.append(judge_order(out, references))
    doc = dict(
        kind="cells.fr43_part3_comparison@1", registration="REGISTRATION.md", worlds=verdicts
    )
    Path(out, "verdict.json").write_text(json.dumps(doc, indent=1) + "\n")
    for v in verdicts:
        print(v["world"], v["result"])
    return 0 if all(v["result"] == "pass" for v in verdicts) else 1


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    r = sub.add_parser("run")
    r.add_argument("out")
    r.add_argument("--only", nargs="*")
    j = sub.add_parser("judge")
    j.add_argument("out")
    j.add_argument("references")
    args = parser.parse_args(argv)
    if args.command == "run":
        run(args.out, args.only)
        return 0
    return judge(args.out, args.references)


if __name__ == "__main__":
    sys.exit(main())
