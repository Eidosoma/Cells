"""Protocol G2-Q1 (registered at 70f5456): tolerance pinning (development) and the judged run.

Engine model: resolved_pump_replacement@1 (inner resolved_pump_tissue@3), on the
frozen definitions of validation/tissue/cell_replacement_q1_predictions.json, IMEX
ARS(2,2,2), junction_heat_booking trapezoid_nonnegative@1, through core/runner.run
(every host row check). Parts (one JSON each in --output, which must not exist):

  dtstudy   engine runs of every case at dt 1 ms and 0.5 ms (development): every
            cell's Vm and the replaced slots' amounts at the predicted records
  refterm   the references at tolerances x 0.1 (R-full rtol 1e-12, atol 1e-16;
            R-fast rtol 1e-11, atol 1e-14) on the same records
  pin       the pinned tolerances, 3 x max over records of (step term + reference
            term [+ reduction term for Q4]) per case and quantity, from dtstudy
            and refterm; writes the pinned block into the protocol file

Usage: python -m validation.tissue.cell_replacement_qualification PART --output DIR
       [--dtstudy DIR --refterm DIR for pin] [--cases NAME,...]
"""

import argparse
import copy
import json
import platform
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
PREDICTIONS = ROOT / "validation" / "tissue" / "cell_replacement_q1_predictions.json"
PROTOCOL = ROOT / "validation" / "tissue" / "cell_replacement_protocol.json"
BOOKING = "trapezoid_nonnegative@1"
STUDY_DTS = (1e-3, 5e-4)


def provenance():
    git = ["git", "-C", str(ROOT)]
    return dict(
        argv=sys.argv,
        host=platform.node(),
        revision=subprocess.run(
            [*git, "rev-parse", "HEAD"], capture_output=True, text=True
        ).stdout.strip(),
        dirty=subprocess.run(
            [*git, "status", "--porcelain", "--untracked-files=no"], capture_output=True, text=True
        ).stdout,
    )


def slots_of(raw):
    order = {c["id"]: i for i, c in enumerate(raw["model"]["cells"])}
    return sorted({order[e["slot"]] for e in raw["experiment"]["replacement_events"]})


def at_dt(raw, dt):
    raw = copy.deepcopy(raw)
    raw["execution"]["dt"] = dt
    end = raw["experiment"]["end_time"]
    raw["execution"]["max_steps"] = int(round(end / dt)) + 16
    raw["model"]["junction_heat_booking"] = BOOKING
    # The frozen definitions declare records at decimal times (round(0.1 k, 10)); the
    # engine observes only accepted boundaries, which are the float products k * dt.
    # Each record maps to its own boundary, a shift below 1e-16 s (protocol amendment).
    raw["experiment"]["observation_times"] = [
        int(round(t / dt)) * dt for t in raw["experiment"]["observation_times"]
    ]
    return raw


def engine_records(raw, dt):
    import jax

    jax.config.update("jax_enable_x64", True)
    from cells.core.runner import run
    from cells.core.specs import parse_spec

    spec = parse_spec(at_dt(raw, dt))
    started = time.perf_counter()
    result = run(spec)
    obs = result.observations
    slots = slots_of(raw)
    records = []
    for k, t in enumerate(np.asarray(obs.times)):
        amount = np.asarray(obs.amount)[k]
        records.append(
            dict(
                time_s=float(raw["experiment"]["observation_times"][k]),
                engine_time_s=float(t),
                membrane_voltage_V=np.asarray(obs.membrane_voltage_V)[k].tolist(),
                slot_amount_fmol={i: amount[:, i].tolist() for i in slots},
            )
        )
    return records, time.perf_counter() - started


def part_dtstudy(args):
    predictions = json.loads(PREDICTIONS.read_text())
    out = dict(kind="cells.cell_replacement_q1_dtstudy@1", dts=STUDY_DTS, cases={})
    for name, entry in predictions["cases"].items():
        if args.cases and name not in args.cases:
            continue
        out["cases"][name] = {}
        for dt in STUDY_DTS:
            records, seconds = engine_records(entry["definition"], dt)
            out["cases"][name][f"{dt:g}"] = dict(records=records, wall_s=seconds)
            print(name, dt, round(seconds, 1), "s", flush=True)
    return out


def part_refterm(args):
    from validation.tissue import cell_replacement_predictions as pr
    from validation.tissue import cell_replacement_reference as ref

    predictions = json.loads(PREDICTIONS.read_text())
    out = dict(
        kind="cells.cell_replacement_q1_reference_term@1",
        tolerances=dict(r_full=[1e-12, 1e-16], r_fast=[1e-11, 1e-14]),
        cases={},
    )
    for name, entry in predictions["cases"].items():
        if args.cases and name not in args.cases:
            continue
        raw = entry["definition"]
        started = time.perf_counter()
        model = ref.ReplacementReference(raw)
        states = model.integrate(pr.HORIZON, pr.RECORDS, rtol=1e-12, atol=1e-16)
        slots = slots_of(raw)
        full = []
        for t in pr.RECORDS:
            o = model.observe(states[t])
            full.append(
                dict(
                    time_s=t,
                    membrane_voltage_V=o["membrane_voltage_V"],
                    slot_amount_fmol={i: o["cell_amount_fmol"][i] for i in slots},
                )
            )
        case = dict(q3_r_full=full)
        if "q4_r_fast" in entry:
            chain = ref.ReducedChain(raw)
            fast = chain.integrate(pr.HORIZON, pr.RECORDS, rtol=1e-11, atol=1e-14)
            case["q4_r_fast"] = [
                dict(time_s=t, membrane_voltage_V=fast[t].tolist()) for t in pr.RECORDS
            ]
        case["wall_s"] = time.perf_counter() - started
        out["cases"][name] = case
        print(name, round(case["wall_s"], 1), "s", flush=True)
    return out


def _difference(a, b, key):
    """Per record: max |a - b| over the quantity's entries (Vm: cells; amounts: slots x species)."""
    out = []
    for x, y in zip(a, b, strict=True):
        if x["time_s"] != y["time_s"]:
            raise ValueError("records differ in time")
        if key == "membrane_voltage_V":
            out.append(float(np.max(np.abs(np.subtract(x[key], y[key])))))
        else:
            out.append(
                max(float(np.max(np.abs(np.subtract(x[key][k], y[key][k])))) for k in x[key])
            )
    return np.asarray(out)


def _normal(records):
    """Slot keys as strings (JSON) in every record."""
    return [
        dict(r, slot_amount_fmol={str(k): v for k, v in r.get("slot_amount_fmol", {}).items()})
        if "slot_amount_fmol" in r
        else r
        for r in records
    ]


def part_pin(args):
    predictions = json.loads(PREDICTIONS.read_text())
    study = json.loads((args.dtstudy / "dtstudy.json").read_text())
    term = json.loads((args.refterm / "refterm.json").read_text())
    pinned = {}
    for name, entry in predictions["cases"].items():
        fine = _normal(study["cases"][name][f"{STUDY_DTS[1]:g}"]["records"])
        coarse = _normal(study["cases"][name][f"{STUDY_DTS[0]:g}"]["records"])
        reference = _normal(entry["q3_r_full"])
        tight = _normal(term["cases"][name]["q3_r_full"])
        case = {}
        for key, unit in (("membrane_voltage_V", "V"), ("slot_amount_fmol", "fmol")):
            step = _difference(coarse, fine, key)
            ref_term = _difference(reference, tight, key)
            case[f"q3_{key}"] = dict(
                tolerance=float(3 * np.max(step + ref_term)),
                unit=unit,
                max_step_term=float(np.max(step)),
                max_reference_term=float(np.max(ref_term)),
            )
        if "q4_r_fast" in entry:
            step = _difference(coarse, fine, "membrane_voltage_V")
            ref_term = _difference(
                entry["q4_r_fast"], term["cases"][name]["q4_r_fast"], "membrane_voltage_V"
            )
            reduction = np.asarray(entry["q4_reduction_term_V"])
            case["q4_membrane_voltage_V"] = dict(
                tolerance=float(3 * np.max(step + ref_term + reduction)),
                unit="V",
                max_step_term=float(np.max(step)),
                max_reference_term=float(np.max(ref_term)),
                max_reduction_term=float(np.max(reduction)),
            )
        pinned[name] = case
    protocol = json.loads(PROTOCOL.read_text())
    protocol["pinned_tolerances"] = dict(
        rule=protocol["tolerance_rule"]["method"],
        engine_step_term=f"|engine(dt {STUDY_DTS[0]:g}) - engine(dt {STUDY_DTS[1]:g})|, "
        f"dt study {args.dtstudy}",
        reference_term=f"|reference - reference at tolerances x 0.1|, {args.refterm}",
        dtstudy_revision=study.get("revision"),
        refterm_revision=term.get("revision"),
        cases=pinned,
    )
    protocol["status"] = "registered at 70f5456; tolerances pinned before the judged run"
    PROTOCOL.write_text(json.dumps(protocol, indent=1) + "\n")
    return dict(kind="cells.cell_replacement_q1_pinned@1", pinned=pinned)


PARTS = dict(dtstudy=part_dtstudy, refterm=part_refterm, pin=part_pin)


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("part", choices=sorted(PARTS))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--dtstudy", type=Path)
    parser.add_argument("--refterm", type=Path)
    parser.add_argument("--cases", type=lambda s: s.split(","), default=None)
    args = parser.parse_args(argv)
    args.output.mkdir(parents=True, exist_ok=False)
    started = time.perf_counter()
    result = PARTS[args.part](args)
    result.update(wall_s=time.perf_counter() - started, **provenance())
    with open(args.output / f"{args.part}.json", "x") as f:
        json.dump(result, f, indent=1, default=float)


if __name__ == "__main__":
    main()
