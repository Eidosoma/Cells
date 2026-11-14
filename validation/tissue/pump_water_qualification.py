"""Qualification of resolved_pump_water@1 against the frozen predictions P1-P6 (W1e).

The predictions (validation/tissue/pump_water_predictions.py, independent reduced
reference) are frozen with their definitions before any engine run. Phases, each
writing <phase>.json in --output (or <phase>-failure.json):

  dt-study    every predicted trajectory world run with ARS(2,2,2) at 4, 2, 1, 0.5
              and 0.25 ms (windowed, observations only): the observed quantities at
              the predicted times, the ledger diagnostics, the observed orders and the
              1-ms step-error term e = |x(1 ms) - x(0.5 ms)| * 4/3 (second order).
  stationary  the engine's stationary analysis of the P2 heredity cell with water:
              Newton from the fixed-volume H, U and D compositions, step-map
              consistency, dense stability and the identity P3 at each state.
  judge       with the tolerances pinned in --protocol, one 1-ms engine run per world
              (and the stationary states) against the frozen predictions; a verdict
              per item. Whether a heredity disc renews is not an acceptance item.
  drift       an hour-scale 1-ms run of the P2 cell from the engine's stationary
              state --label (H, U or D; from --stationary): drift and ledgers.

Quantities: cell volume (pL), membrane voltage (V), cell concentrations (mM) and,
in P5, the finite outside volume (pL).
Usage: python -m validation.tissue.pump_water_qualification PHASE --predictions FILE
       --output DIR [--protocol FILE] [--parts P1 P2 ...]
       [--stationary FILE --hours H --label H|U|D]   (drift)
"""

import argparse
import copy
import json
import math
import time
import traceback
from pathlib import Path

import jax

jax.config.update("jax_enable_x64", True)

import numpy as np  # noqa: E402

from cells.core.specs import parse_spec  # noqa: E402
from cells.core.windows import WindowPolicy, run_windowed  # noqa: E402

STEPS_S = (4e-3, 2e-3, 1e-3, 5e-4, 2.5e-4)
QUANTITIES = ("cell_volume_pL", "membrane_voltage_V", "cell_concentration_mM")
TRAJECTORIES = {
    "P1": ("P1",),
    "P2_from_H": ("P2", "from_H"),
    "P2_from_D": ("P2", "from_D"),
    "P4": ("P4",),
    "P5": ("P5",),
    "P6": ("P6",),
}


def item(predictions, path):
    value = predictions
    for key in path:
        value = value[key]
    return value


def with_step(raw, dt):
    raw = copy.deepcopy(raw)
    x = raw["execution"]
    x["dt"] = dt
    x["max_steps"] = int(math.ceil(raw["experiment"]["end_time"] / dt)) + 64
    x["jit"] = True
    return raw


def engine_observations(raw, dt, window_steps=4000):
    """{time: {quantity: array}} at the definition's observation times, and diagnostics."""
    spec = parse_spec(with_step(raw, dt))
    seen = []
    started = time.perf_counter()
    result = run_windowed(
        spec, WindowPolicy(window_steps, "observations"), sink=lambda w: seen.append(w)
    )
    seconds = time.perf_counter() - started
    out = {}
    for window in seen:
        o = window.observations
        for i, t in enumerate(np.asarray(o.times)):
            out[f"{float(t):.6f}"] = {
                k: np.asarray(getattr(o, k)[i]) for k in (*QUANTITIES, "extracellular_volume_pL")
            }
    return out, dict(result.diagnostics), seconds


def reference_arrays(observation):
    return dict(
        cell_volume_pL=np.asarray(observation["cell_volume_pL"]),
        membrane_voltage_V=np.asarray(observation["membrane_voltage_V"]),
        cell_concentration_mM=np.asarray(observation["cell_concentration_mM"]).T,
        extracellular_volume_pL=np.asarray(observation["extracellular_volume_pL"]),
    )


def engine_quantities(name, observation, prediction_definition):
    out = {k: observation[k] for k in QUANTITIES}
    if name == "P5":
        finite = [
            i
            for i, o in enumerate(prediction_definition["model"]["extracellular"])
            if not o.get("reservoir", False)
        ]
        out["extracellular_volume_pL"] = observation["extracellular_volume_pL"][finite]
    return out


def p1_reference(predictions):
    return {
        t: dict(cell_volume_pL=np.array([v]))
        for t, v in predictions["P1"]["cell_volume_pL"].items()
    }


def dt_study(predictions, parts, progress=None):
    """The dt study of every predicted world; a failed run is recorded, not fatal.

    progress: a path rewritten after every run with each world's completed and
    failed runs (so a long study leaves its evidence as it goes).
    """
    out, log = {}, {}
    for name, path in TRAJECTORIES.items():
        if parts and path[0] not in parts:
            continue
        entry = item(predictions, path)
        raw = entry["definition"]
        runs, failures = {}, {}
        for dt in STEPS_S:
            started = time.perf_counter()
            try:
                observed, diagnostics, seconds = engine_observations(raw, dt)
                runs[dt] = dict(observed=observed, diagnostics=diagnostics, seconds=seconds)
                log.setdefault(name, {})[str(dt)] = dict(status="ok", seconds=seconds)
            except Exception as error:  # A refused run is evidence: record it.
                failures[str(dt)] = dict(
                    error=repr(error),
                    traceback=traceback.format_exc()[-3000:],
                    seconds=time.perf_counter() - started,
                )
                log.setdefault(name, {})[str(dt)] = dict(status="failed", error=repr(error))
            if progress is not None:
                Path(progress).write_text(json.dumps(log, indent=2) + "\n")
        if failures:
            out[name] = dict(failures=failures, completed=[str(dt) for dt in runs])
            continue
        times = sorted(runs[STEPS_S[0]]["observed"])
        record = dict(times=times, seconds={str(dt): r["seconds"] for dt, r in runs.items()})
        record["diagnostics"] = {str(dt): r["diagnostics"] for dt, r in runs.items()}
        terms, orders, values = {}, {}, {}
        keys = (*QUANTITIES, *(("extracellular_volume_pL",) if name == "P5" else ()))
        for key in keys:
            series = {
                dt: np.array(
                    [engine_quantities(name, runs[dt]["observed"][t], raw)[key] for t in times]
                )
                for dt in STEPS_S
            }
            finest = series[STEPS_S[-1]]
            errors = [float(np.max(np.abs(series[dt] - finest))) for dt in STEPS_S[:-1]]
            terms[key] = (np.abs(series[1e-3] - series[5e-4]) * 4 / 3).tolist()
            orders[key] = [
                math.log2(a / b) if a > 0 and b > 0 else None
                for a, b in zip(errors[:-1], errors[1:], strict=True)
            ]
            values[key] = {str(dt): series[dt].tolist() for dt in STEPS_S}
        record.update(step_error_term_1ms=terms, observed_orders=orders, values=values)
        out[name] = record
    return out


def stationary_phase(predictions):
    from cells.analysis import stationary as sa
    from cells.models import surface_pump_v3
    from cells.processes.electrochemistry import CHARGE_PER_FMOL, F, R

    raw = predictions["P2"]["definition"]
    spec = parse_spec(raw)
    records = []
    states = predictions["P2"]["states"]["approved"]
    v0 = raw["model"]["cells"][0]["volume_pL"]
    pb = sa.problem(spec)
    ids = list(spec.model.species_ids)
    for label, reference in zip(("H", "U", "D"), states, strict=False):
        # The reference state as a guess: its Na, K, M amounts and volume (P unchanged).
        base = sa._numpy(pb.base)
        volume = reference["volume_pL"]
        increment = np.array(base.amount_increment, dtype=float)
        for sid in ("Na", "K", "M"):
            k = ids.index(sid)
            increment[k, 0] = (
                reference["concentration_mM"][sid] * volume - pb.p.amount_reference[k, 0]
            )
        # Gates at their steady state at the reference voltage.
        target, _ = surface_pump_v3.channel_kinetics(
            np.full(pb.p.channel_laws.shape, reference["membrane_voltage_V"]),
            np.asarray(pb.p.channel_laws),
            xp=np,
        )
        gate = np.where(np.asarray(pb.p.channel_gate_active), target, base.channel_gate)
        guess_state = base._replace(
            amount_increment=increment,
            volume_increment_pL=np.array([volume - v0]),
            channel_gate=gate,
        )
        guess = pb.coordinates(guess_state)
        solution = sa.newton(pb, guess)
        record = dict(label=label, converged=solution.converged, message=solution.message)
        if solution.converged:
            described = sa.describe(pb, solution.u)
            state, p, _ = pb.embed(solution.u)
            state, p = sa._numpy(state), sa._numpy(p)
            volume = float(p.volume[0] + state.volume_increment_pL[0])
            vm = described["membrane_voltage_V"]["membrane_0"]
            m = spec.model
            ids = m.species_ids
            z = np.asarray(m.valence, dtype=float)
            charge = float(
                p.initial_cell_charge_C[0]
                + CHARGE_PER_FMOL * np.sum(z * state.amount_increment[:, 0])
            )
            bath = m.extracellular[0]
            c_bath = sum(bath.initial_amount_fmol) / bath.volume_pL
            m_bath = bath.initial_amount_fmol[ids.index("M")] / bath.volume_pL
            w = m.water.compartments[0]
            pressure = (
                w.bulk_modulus_Pa * (volume / w.reference_volume_pL - 1) + w.pressure_offset_Pa
            )
            rt = R * m.temperature_K
            n_p = float(
                p.amount_reference[ids.index("P"), 0] + state.amount_increment[ids.index("P"), 0]
            )
            identity = (
                n_p
                + (
                    w.impermeant_amount_fmol
                    + charge / CHARGE_PER_FMOL
                    - m.cells[0].fixed_charge_equivalent_fmol
                )
                / 2
            ) / ((c_bath + pressure / rt) / 2 - m_bath * math.exp(F * vm / rt))
            record.update(
                state=described,
                volume_pL=volume,
                identity_volume_pL=identity,
                identity_relative_error=abs(volume - identity) / volume,
                consistency=sa.consistency(pb, solution.u),
                stability=sa.stability(pb, solution.u),
                reference=reference,
                state_arrays=dict(
                    amount_fmol={
                        sid: float(
                            p.amount_reference[ids.index(sid), 0]
                            + state.amount_increment[ids.index(sid), 0]
                        )
                        for sid in ids
                    },
                    volume_pL=volume,
                    charge_C=charge,
                    channel_gate=np.asarray(state.channel_gate).tolist(),
                ),
            )
        records.append(record)
    return records


def stationary_definition(predictions, record, hours, interval_s=600.0):
    """The P2 definition started at an engine stationary state, run for `hours`."""
    raw = copy.deepcopy(predictions["P2"]["definition"])
    arrays = record["state_arrays"]
    cell = raw["model"]["cells"][0]
    z = {s["id"]: s["valence"] for s in raw["model"]["species"]}
    cell["initial_amount_fmol"] = dict(arrays["amount_fmol"])
    cell["volume_pL"] = arrays["volume_pL"]
    # The declared charge is F (sum z N + X) with the definition's background X.
    from cells.processes.electrochemistry import CHARGE_PER_FMOL

    cell["initial_charge_C"] = CHARGE_PER_FMOL * (
        sum(z[s] * n for s, n in arrays["amount_fmol"].items())
        + cell["fixed_charge_equivalent_fmol"]
    )
    gates = np.asarray(arrays["channel_gate"])
    for i, channel in enumerate(raw["model"]["channels"]):
        if channel["initial_gate"]:
            channel["initial_gate"] = [float(g) for g in gates[: len(channel["initial_gate"]), i]]
    end = hours * 3600.0
    raw["experiment"]["end_time"] = end
    raw["experiment"]["observation_times"] = [
        float(t) for t in np.arange(0.0, end + 0.5 * interval_s, interval_s)
    ]
    return raw


def drift(predictions, stationary, hours, label="H"):
    """Hour-scale run from the engine's stationary state: drift and ledgers."""
    record = next(r for r in stationary if r["label"] == label and r["converged"])
    raw = stationary_definition(predictions, record, hours)
    started = time.perf_counter()
    observed, diagnostics, seconds = engine_observations(raw, 1e-3, window_steps=20000)
    times = sorted(observed)
    first = observed[times[0]]
    return dict(
        label=label,
        hours=hours,
        steps=int(round(hours * 3600 / 1e-3)),
        wall_seconds=time.perf_counter() - started,
        run_seconds=seconds,
        diagnostics=diagnostics,
        drift={
            key: [float(np.max(np.abs(observed[t][key] - first[key]))) for t in times]
            for key in QUANTITIES
        },
        times=[float(t) for t in times],
        start=dict(
            volume_pL=record["volume_pL"],
            membrane_voltage_V=record["state"]["membrane_voltage_V"]["membrane_0"],
        ),
    )


def consistent(record, bound):
    """Every step-map fixed-point correction within the bound (or 4x its rounding floor)."""
    checks = [v for k, v in record.items() if k.startswith("step_map_")]
    if not checks:
        return False
    return all(v["correction"] <= max(bound, 4 * (v["rounding_floor"] or 0.0)) for v in checks)


def judge(predictions, protocol, parts):
    tolerances = protocol["tolerances"]
    items = []
    for name, path in TRAJECTORIES.items():
        if parts and path[0] not in parts:
            continue
        entry = item(predictions, path)
        raw = entry["definition"]
        observed, diagnostics, seconds = engine_observations(raw, 1e-3)
        reference = (
            p1_reference(predictions)
            if name == "P1"
            else {t: reference_arrays(v) for t, v in entry["observations"].items()}
        )
        for key, bound in tolerances[name].items():
            worst = 0.0
            for t, ref_values in reference.items():
                if key not in ref_values:
                    continue
                engine = engine_quantities(name, observed[t], raw)[key]
                worst = max(worst, float(np.max(np.abs(engine - ref_values[key]))))
            items.append(
                dict(world=name, quantity=key, worst=worst, tolerance=bound, pass_=worst <= bound)
            )
        items.append(
            dict(
                world=name,
                quantity="ledgers",
                diagnostics=diagnostics,
                pass_=True,  # The run raises on any ledger, domain or dissipation failure.
                seconds=seconds,
            )
        )
    if not parts or "P2" in parts:
        bounds = protocol["stationary"]
        for record in stationary_phase(predictions):
            reference = record.get("reference")
            ok = record["converged"]
            entry = dict(world="P2_stationary", quantity=record["label"], record=record)
            if ok:
                vm = record["state"]["membrane_voltage_V"]["membrane_0"]
                volume_error = (
                    abs(record["volume_pL"] - reference["volume_pL"]) / reference["volume_pL"]
                )
                voltage_error = abs(vm - reference["membrane_voltage_V"])
                ok = (
                    volume_error <= bounds["volume_relative"]
                    and voltage_error <= bounds["voltage_V"]
                    and record["identity_relative_error"] <= bounds["identity_relative"]
                    and consistent(record["consistency"], bounds["step_map_correction"])
                )
                entry.update(volume_relative_error=volume_error, voltage_error_V=voltage_error)
            entry["pass_"] = bool(ok)
            items.append(entry)
    return dict(
        verdict="pass" if all(i["pass_"] for i in items) else "fail",
        items=items,
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=("dt-study", "stationary", "judge", "drift"))
    parser.add_argument("--stationary", help="stationary.json (drift phase)")
    parser.add_argument("--hours", type=float, default=1.0)
    parser.add_argument("--label", default="H", choices=("H", "U", "D"), help="drift start state")
    parser.add_argument("--predictions", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--protocol")
    parser.add_argument("--parts", nargs="*", default=[])
    parser.add_argument(
        "--backend",
        choices=("cpu", "gpu"),
        help="set every definition's execution backend on a copy of the predictions (an L4 "
        "run: gpu); default: as registered",
    )
    args = parser.parse_args()
    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)
    predictions = json.loads(Path(args.predictions).read_text())
    backend = None
    if args.backend:  # The registered definitions declare the CPU; their backend picks the device.
        from validation.tissue import composite_l4_agreement as agreement

        predictions, backend = agreement.with_backend(predictions, args.backend)
    try:
        if args.phase == "dt-study":
            result = dt_study(predictions, args.parts, progress=out / "dt-study-progress.json")
        elif args.phase == "stationary":
            result = stationary_phase(predictions)
        elif args.phase == "drift":
            stationary = json.loads(Path(args.stationary).read_text())
            result = drift(predictions, stationary, args.hours, label=args.label)
        else:
            # A judged run takes the registered protocol or a registered backend variant of
            # it; any other file is marked a dry run (composite_l4_agreement.judged_protocol).
            from validation.tissue import composite_l4_agreement as agreement

            protocol, judged, acceptance = agreement.judged_protocol("w1", args.protocol)
            result = judge(predictions, protocol, args.parts)
            result.update(
                dry_run=not judged, protocol=args.protocol, protocol_acceptance=acceptance
            )
        if backend is not None and isinstance(result, dict):
            result["backend"] = backend
        (out / f"{args.phase}.json").write_text(json.dumps(result, indent=2, default=float) + "\n")
    except Exception:
        (out / f"{args.phase}-failure.json").write_text(
            json.dumps(dict(traceback=traceback.format_exc()), indent=2) + "\n"
        )
        raise


if __name__ == "__main__":
    main()
