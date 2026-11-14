"""Protocol G2-Q1 judged run for resolved_pump_replacement@1 (registered; run once).

Engine model: resolved_pump_replacement@1 (inner resolved_pump_tissue@3), on the
frozen definitions of validation/tissue/cell_replacement_q1_predictions.json, with
junction_heat_booking trapezoid_nonnegative@1, IMEX ARS(2,2,2) at dt 1 ms unless an
item says otherwise. Every engine run goes through core/runner.run, which applies the
host row checks to every accepted row. A refusal fails its item and is recorded.

Items (validation/tissue/cell_replacement_protocol.json):
  Q1  host (run) and device (row_checks over every accepted row) checks, every case
      and the W37 swap world
  Q2  the engine's event map against R-ops on each case's first event set
  Q3  every cell's Vm and the replaced slots' amounts against R-full, pinned tolerances
  Q4  C9: Vm against R-fast (pinned, reduction term included) and the end states
  Q5  W7 and C9 isolated short-lag at dt 2, 1, 0.5, 0.25 ms: order in [1.8, 2.2] (A3)
  Q6  restart at t_e - dt, t_e, t_e + dt bitwise; vmap cohorts of 2 and 8 worlds
  Q7  no events on the 825-node world: bitwise equal to resolved_pump_tissue@3

Usage: python -m validation.tissue.cell_replacement_judge --output DIR --items Q1,Q2,...
(run from a clean snapshot of the registering commit; DIR must not exist)
"""

import argparse
import copy
import json
import platform
import subprocess
import sys
import time
import traceback
from pathlib import Path

import jax
import jax.numpy as jnp
import numpy as np

jax.config.update("jax_enable_x64", True)

from cells.core.batch import BatchSpec, WorldSpec  # noqa: E402
from cells.core.runner import run  # noqa: E402
from cells.core.specs import parse_spec  # noqa: E402
from cells.core.vector_windows import run_vector_windowed  # noqa: E402
from cells.core.windows import WindowPolicy, run_windowed  # noqa: E402
from cells.models import cell_replacement as model  # noqa: E402
from cells.models import surface_pump_v3  # noqa: E402
from validation.tissue import cell_replacement_fixtures as fx  # noqa: E402
from validation.tissue import cell_replacement_qualification as qual  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
EPS = np.finfo(float).eps
THRESHOLD_V = -0.03944519911117352  # The heredity cell's U state (fixtures.HEREDITY_STATES).


REGISTERED = dict(w37_rim=(0, 1), w37_inner=0, w37_step=200, q7_channel_scale=1.0)


def load(protocol_path=None, predictions_path=None):
    protocol = json.loads(Path(protocol_path or qual.PROTOCOL).read_text())
    if "pinned_tolerances" not in protocol:
        raise SystemExit("The protocol has no pinned tolerances")
    return protocol, json.loads(Path(predictions_path or qual.PREDICTIONS).read_text())


def engine(raw, dt=1e-3):
    spec = parse_spec(qual.at_dt(raw, dt))
    return spec, run(spec)


def records(result, raw, dt):
    times = qual.at_dt(raw, dt)["experiment"]["observation_times"]
    obs = result.observations
    slots = qual.slots_of(raw)
    out = []
    for k, t in enumerate(times):
        amount = np.asarray(obs.amount)[k]
        out.append(
            dict(
                time_s=float(raw["experiment"]["observation_times"][k]),
                membrane_voltage_V=np.asarray(obs.membrane_voltage_V)[k].tolist(),
                slot_amount_fmol={str(i): amount[:, i].tolist() for i in slots},
            )
        )
        assert np.asarray(obs.times)[k] == t
    return out


def device_failures(spec, result, chunk=512):
    """Device checks (row_checks) on every accepted row; (failing rows, checks failed)."""
    p = model.initial_values(spec)[1]
    constants = model.device_check_constants(spec)
    h = result.history
    n = len(result.times)
    check = jax.jit(
        jax.vmap(lambda a, b, s: model.device_checks(a, b, p, constants, s)[0], in_axes=(0, 0, 0))
    )
    failing, names = [], set()
    for start in range(1, n, chunk):
        stop = min(n, start + chunk)
        window = slice(start - 1, stop - 1), slice(start, stop)
        prev = jax.tree.map(lambda v, w=window[0]: jnp.asarray(np.asarray(v)[w]), h)
        rows = jax.tree.map(lambda v, w=window[1]: jnp.asarray(np.asarray(v)[w]), h)
        steps = jnp.arange(start, stop) + result.start_step
        failed = np.asarray(check(prev, rows, steps))
        for k in np.flatnonzero(failed.any(axis=1)):
            failing.append(int(start + k))
            names |= {c for c, f in zip(model.DEVICE_CHECKS, failed[k], strict=True) if f}
    return failing, sorted(names)


def worst(a, b, key):
    return float(max(qual._difference(qual._normal(a), qual._normal(b), key)))


# ---------------------------------------------------------------- items


def q1_q3_q4(protocol, predictions, out, w37=None):
    pinned = protocol["pinned_tolerances"]["cases"]
    for name, entry in predictions["cases"].items():
        raw = entry["definition"]
        started = time.perf_counter()
        try:
            spec, result = engine(raw)
        except Exception as error:  # A refusal fails the items of this case.
            for item in ("Q1", "Q3", "Q4"):
                if item != "Q4" or "q4_r_fast" in entry:
                    out[item]["cases"][name] = dict(verdict="fail", refused=repr(error))
            continue
        try:
            case_items(name, entry, spec, result, pinned, out)
        except Exception as error:  # Kept; this case fails the items it had not reached.
            for item in ("Q1", "Q3", "Q4"):
                if item != "Q4" or "q4_r_fast" in entry:
                    out[item]["cases"].setdefault(
                        name, dict(verdict="fail", error=repr(error), tb=traceback.format_exc())
                    )
        out["Q1"]["cases"][name]["wall_s"] = time.perf_counter() - started
        print(name, out["Q1"]["cases"][name]["verdict"], flush=True)
    if w37 is not None:
        try:
            w37_case(out, **w37)
        except Exception as error:
            out["Q1"]["cases"]["W37"] = dict(
                verdict="fail", error=repr(error), tb=traceback.format_exc()
            )


def case_items(name, entry, spec, result, pinned, out):
    raw = entry["definition"]
    if True:  # Indented block kept for a minimal diff of the per-case items.
        failing, names = device_failures(spec, result)
        out["Q1"]["cases"][name] = dict(
            verdict="pass" if not failing else "fail",
            host_checks="passed (core/runner.run)",
            device_failing_rows=failing[:20],
            device_failed_checks=names,
            diagnostics={k: v for k, v in result.diagnostics.items() if k.startswith("max_")},
        )
        mine = records(result, raw, 1e-3)
        q3 = {}
        for key in ("membrane_voltage_V", "slot_amount_fmol"):
            diff = worst(mine, entry["q3_r_full"], key)
            tol = pinned[name][f"q3_{key}"]["tolerance"]
            q3[key] = dict(max_difference=diff, tolerance=tol, ratio=diff / tol)
        out["Q3"]["cases"][name] = dict(
            verdict="pass" if all(v["ratio"] <= 1 for v in q3.values()) else "fail", **q3
        )
        if "q4_r_fast" in entry:
            diff = worst(mine, entry["q4_r_fast"], "membrane_voltage_V")
            tol = pinned[name]["q4_membrane_voltage_V"]["tolerance"]
            engine_end = [v > THRESHOLD_V for v in mine[-1]["membrane_voltage_V"]]
            fast_end = [v > THRESHOLD_V for v in entry["q4_r_fast"][-1]["membrane_voltage_V"]]
            out["Q4"]["cases"][name] = dict(
                verdict="pass" if diff <= tol and engine_end == fast_end else "fail",
                max_difference=diff,
                tolerance=tol,
                ratio=diff / tol,
                end_state_engine="".join("D" if x else "H" for x in engine_end),
                end_state_r_fast="".join("D" if x else "H" for x in fast_end),
            )


def declared(raw, backend):
    """raw itself (the registered path), or a copy whose every definition declares `backend`
    (--backend: the registered definitions declare the CPU, and that picks the device)."""
    if backend is None:
        return raw
    from validation.tissue import composite_l4_agreement as agreement

    return agreement.on_backend(raw, backend)[0]


def w37_raw(backend=None):
    """W37's definition before its replacement events."""
    raw = fx.heredity_sheet(6, 3, scale=0.3, dt=1e-3, end_time=3.0)
    raw["experiment"]["observation_times"] = [0.0, 3.0]
    raw["model"]["junction_heat_booking"] = qual.BOOKING
    return declared(raw, backend)


def w37_case(out, rim, inner, step, backend=None):
    """W37: the 127-cell D->H swap world of cell_replacement_cost swap (3000 steps)."""
    from cells.core.cell_replacement_spec import exact_event_times
    from validation.stationary import worlds

    raw = w37_raw(backend)
    cells, _ = worlds.hexagon(6)
    rings = [worlds.ring(c) for c in cells]
    rims = [i for i, r in enumerate(rings) if r == 3]
    inners = [i for i, r in enumerate(rings) if r == 1]
    slots = [*(rims[k] for k in rim), inners[inner]]
    h = next(i for i, r in enumerate(rings) if r == 6)
    (t,) = exact_event_times((step,), 1e-3)
    template = fx.template_from_cell(raw, f"cell_{h}", "h")
    events = [(t, f"cell_{i}", "h", f"n{i}") for i in slots]
    started = time.perf_counter()
    try:
        spec = parse_spec(fx.with_replacement(raw, [template], events))
        result = run(spec)
    except Exception as error:
        out["Q1"]["cases"]["W37"] = dict(verdict="fail", refused=repr(error), slots=slots)
        return
    failing, names = device_failures(spec, result)
    out["Q1"]["cases"]["W37"] = dict(
        verdict="pass" if not failing else "fail",
        slots=slots,
        event_time_s=t,
        device_failing_rows=failing[:20],
        device_failed_checks=names,
        generation_end=np.asarray(result.history.generation)[-1].tolist(),
        wall_s=time.perf_counter() - started,
    )


def q2(protocol, predictions, out):
    from validation.tissue.cell_replacement_reference import R

    for name, entry in predictions["cases"].items():
        try:
            q2_case(name, entry, out, R)
        except Exception as error:
            out["Q2"]["cases"][name] = dict(
                verdict="fail", error=repr(error), tb=traceback.format_exc()
            )
        print(name, "Q2", out["Q2"]["cases"][name]["verdict"], flush=True)


def q2_case(name, entry, out, R):
    if True:  # Indented block kept for a minimal diff of the per-case comparison.
        raw = entry["definition"]
        spec = parse_spec(qual.at_dt(raw, 1e-3))
        state, p = model.initial_values(spec)
        pred = entry["q2"]
        t = pred["event_time_s"]
        control = model.Control(*(np.asarray(v[0]) for v in model.control_values(spec, [t])))
        after, ok = model.apply_events(state, control, p, xp=np)
        slots = [int(i) for i in pred["bookings"]["slots"]]
        amounts = np.asarray(p.amount_reference) + after.amount_increment
        before = np.asarray(p.amount_reference) + state.amount_increment
        chans = spec.model.channels
        membranes = {m.id: k for k, m in enumerate(spec.model.membranes)}
        owner = [int(np.asarray(p.membrane_cell)[membranes[c.membrane_id]]) for c in chans]
        gated = [k for k, c in enumerate(chans) if c.initial_gate and owner[k] in slots]
        incident = np.isin(np.asarray(p.junction_sender), slots) | np.isin(
            np.asarray(p.junction_receiver), slots
        )
        ne = len(spec.model.junctions)
        n_out = len(spec.model.extracellular)
        image = (after.electrode_charge_transferred_C - state.electrode_charge_transferred_C)[
            :n_out
        ]
        temperature = float(spec.model.temperature_K)
        volume = np.asarray(p.volume)

        def chemical(n, temperature=temperature, volume=volume):
            return 1e-3 * R * temperature * np.abs(n * (np.log(n / volume) - 1.0))

        energy_scale = float(
            np.sum(chemical(before)[:, slots]) + np.sum(chemical(amounts)[:, slots])
        ) + float(np.sum(after.replacement_energy_magnitude_pJ))
        comparisons = {}

        def compare(label, mine, theirs, magnitude, comparisons=comparisons):
            diff = float(np.max(np.abs(np.subtract(mine, theirs)), initial=0))
            tol = 64 * EPS * magnitude
            comparisons[label] = dict(
                max_difference=diff,
                tolerance=tol,
                ratio=diff / tol if tol else (0.0 if diff == 0 else np.inf),
            )

        for i in slots:
            key = str(i)
            compare(
                f"slot_amount_{i}",
                amounts[:, i],
                pred["slot_amount_fmol"][key],
                np.max(amounts[:, i]),
            )
            compare(
                f"removed_{i}",
                after.replacement_removed_fmol[:, i],
                pred["bookings"]["removed_fmol"][key],
                np.max(before[:, i]),
            )
            compare(
                f"supplied_{i}",
                after.replacement_supplied_fmol[:, i],
                pred["bookings"]["supplied_fmol"][key],
                np.max(amounts[:, i]),
            )
            qmag = model.CHARGE_PER_FMOL * float(
                np.sum(np.abs(before[:, i]) + np.abs(amounts[:, i]))
            )
            compare(
                f"charge_{i}",
                after.replacement_charge_C[i],
                pred["bookings"]["charge_C"][key],
                qmag,
            )
        compare(
            "slot_channel_gate",
            np.stack([after.channel_gate[:, k] for k in gated]),
            pred["slot_channel_gate"],
            1.0,
        )
        compare(
            "incident_junction_gate",
            after.junction_gate[:ne][incident[:ne]],
            pred["incident_junction_gate"],
            1.0,
        )
        qmag = model.CHARGE_PER_FMOL * float(
            np.sum(np.abs(before[:, slots]) + np.abs(amounts[:, slots]))
        )
        compare("image_charge", image, pred["bookings"]["image_charge_C"], qmag)
        compare(
            "free_energy",
            float(np.sum(after.replacement_free_energy_pJ)),
            pred["bookings"]["free_energy_pJ"],
            energy_scale,
        )
        out["Q2"]["cases"][name] = dict(
            verdict="pass" if ok and all(c["ratio"] <= 1 for c in comparisons.values()) else "fail",
            schedule_consistent=bool(ok),
            comparisons=comparisons,
        )


def observed_order(errors_by_dt, fine):
    """Order p from e(dt) = C (dt^p - fine^p) at the two smallest coarse steps."""
    (h1, e1), (h2, e2) = sorted(errors_by_dt.items())[:2]
    ratio = e2 / e1

    def f(p):
        return (h2**p - fine**p) / (h1**p - fine**p) - ratio

    lo, hi = 0.2, 6.0
    if f(lo) * f(hi) > 0:
        return None
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        lo, hi = (mid, hi) if f(lo) * f(mid) > 0 else (lo, mid)
    return 0.5 * (lo + hi)


Q5_CASES = ("W7/short_lag", "C9/isolated/short_lag")  # Amendment A3.
Q5_DTS = (2e-3, 1e-3, 5e-4, 2.5e-4)


def q5(protocol, predictions, out):
    """Amendment A3: order log2(D(1 ms, 0.5 ms) / D(0.5 ms, 0.25 ms)), D the max over the
    records after the first event of |slot Vm(h) - slot Vm(h/2)|; window [1.8, 2.2]."""
    for name in Q5_CASES:
        raw = predictions["cases"][name]["definition"]
        slots = qual.slots_of(raw)
        first = min(e["time"] for e in raw["experiment"]["replacement_events"])
        series = {}
        try:
            for dt in Q5_DTS:
                _, result = engine(raw, dt)
                series[dt] = np.asarray(result.observations.membrane_voltage_V)[:, slots]
            after = np.asarray(raw["experiment"]["observation_times"]) > first
            differences = {
                f"{a:g}-{b:g}": float(np.max(np.abs(series[a][after] - series[b][after])))
                for a, b in zip(Q5_DTS[:-1], Q5_DTS[1:], strict=True)
            }
            ratios = {
                f"h {h:g}": float(
                    np.log2(differences[f"{2 * h:g}-{h:g}"] / differences[f"{h:g}-{h / 2:g}"])
                )
                for h in (1e-3, 5e-4)
            }
            p = ratios["h 0.0005"]
            out["Q5"]["cases"][name] = dict(
                verdict="pass" if 1.8 <= p <= 2.2 else "fail",
                observed_order=p,
                coarser_ratio_order=ratios["h 0.001"],
                successive_differences_V=differences,
            )
        except Exception as error:
            out["Q5"]["cases"][name] = dict(verdict="fail", refused=repr(error))
        print(name, "Q5", out["Q5"]["cases"][name], flush=True)


def q6(protocol, predictions, out):
    # Restart: W7/short_lag around its first event.
    raw = predictions["cases"]["W7/short_lag"]["definition"]
    spec, result = engine(raw)
    first = min(e["time"] for e in raw["experiment"]["replacement_events"])
    restarts = {}
    for t in (first - 1e-3, first, first + 1e-3):
        t = int(round(t / 1e-3)) * 1e-3
        again = run(spec, result.checkpoint_at(t))
        k = int(np.flatnonzero(result.times == t)[0])
        same = all(
            np.array_equal(
                np.asarray(getattr(again.history, f)), np.asarray(getattr(result.history, f))[k:]
            )
            for f in model.STATE_TYPE._fields
        )
        restarts[f"{t:.6g}"] = bool(same)
    # vmap: a cohort of the 2 W7 schedule variants, and of 8 C9 worlds.
    cohorts = {}
    w7 = [
        qual.at_dt(predictions["cases"][n]["definition"], 1e-3)
        for n in ("W7/literature", "W7/short_lag")
    ]
    c9 = [
        qual.at_dt(predictions["cases"][n]["definition"], 1e-3)
        for n in predictions["cases"]
        if n.startswith("C9/")
    ]
    extra = copy.deepcopy(c9[0])
    end = extra["experiment"]["end_time"]
    extra["experiment"]["replacement_events"][0]["time"] = int(round(0.2 * end / 1e-3)) * 1e-3
    extra2 = copy.deepcopy(c9[3])
    extra2["experiment"]["replacement_events"][0]["time"] = int(round(0.3 * end / 1e-3)) * 1e-3
    c9 += [extra, extra2]
    for label, raws in (("2_W7", w7), ("8_C9", c9)):
        specs = [parse_spec(r) for r in raws]
        cohort = BatchSpec(
            tuple(WorldSpec(i + 1, s) for i, s in enumerate(specs)), len(specs), 10**8, 2**33
        )
        policy = WindowPolicy(1000, "checkpoints")
        batch = run_vector_windowed(cohort, policy)
        worst_rel = 0.0
        for w in cohort.worlds:
            own = run_windowed(w.simulation, policy).final.state
            mine = batch.worlds[w.world_id].final.state
            for a, b in zip(mine, own, strict=True):
                a, b = np.asarray(a, dtype=float), np.asarray(b, dtype=float)
                scale = max(float(np.max(np.abs(b), initial=0)), 1e-300)
                worst_rel = max(worst_rel, float(np.max(np.abs(a - b), initial=0)) / scale)
        cohorts[label] = dict(worlds=len(specs), max_relative_difference=worst_rel)
    out["Q6"] = dict(
        verdict="pass"
        if all(restarts.values())
        and all(c["max_relative_difference"] <= 1e-12 for c in cohorts.values())
        else "fail",
        restart_bitwise=restarts,
        vmap=cohorts,
    )
    print("Q6", out["Q6"], flush=True)


def q7_raw(channel_scale=1.0, backend=None):
    """Q7's 825-node tissue with its channels scaled."""
    from validation.tissue import surface_pump_v3_study as study

    raw = study.tissue_definition(dt=1e-3, end_time=0.2, observation_times=[0.0, 0.1, 0.2])
    for channel in raw["model"]["channels"]:
        channel["max_permeability_m_per_s"] *= channel_scale
    return declared(raw, backend)


def q7(protocol, predictions, out, world=None, channel_scale=1.0, backend=None):
    raw = q7_raw(channel_scale, backend) if world is None else declared(world, backend)
    reference = run(parse_spec(raw))
    wrapped = run(parse_spec(fx.with_replacement(raw)))
    fields = {
        k: bool(
            np.array_equal(
                np.asarray(getattr(wrapped.history, k)), np.asarray(getattr(reference.history, k))
            )
        )
        for k in surface_pump_v3.STATE_TYPE._fields
    }
    observed = {
        k: bool(np.array_equal(np.asarray(getattr(wrapped.observations, k)), v))
        for k, v in vars(reference.observations).items()
    }
    diagnostics = {
        k: wrapped.diagnostics[k] == v
        for k, v in reference.diagnostics.items()
        if k.startswith("max_")
    }
    zero = all(
        not np.any(np.asarray(getattr(wrapped.history, k))) for k in model.REPLACEMENT_STATE_AXES
    )
    out["Q7"] = dict(
        verdict="pass"
        if all(fields.values()) and all(observed.values()) and all(diagnostics.values()) and zero
        else "fail",
        steps=len(reference.times) - 1,
        state_fields_bitwise=fields,
        observations_bitwise=observed,
        diagnostics_equal=diagnostics,
        replacement_fields_zero=zero,
    )
    print("Q7", out["Q7"]["verdict"], flush=True)


ITEMS = dict(Q1=q1_q3_q4, Q2=q2, Q5=q5, Q6=q6, Q7=q7)


def provenance():
    git = ["git", "-C", str(ROOT)]
    return dict(
        argv=sys.argv,
        host=platform.node(),
        jax=jax.__version__,
        source_root=str(ROOT),
        revision=subprocess.run(
            [*git, "rev-parse", "HEAD"], capture_output=True, text=True
        ).stdout.strip(),
        dirty=subprocess.run(
            [*git, "status", "--porcelain", "--untracked-files=no"], capture_output=True, text=True
        ).stdout,
        snapshot=(ROOT / "SNAPSHOT.json").exists(),
    )


def run_kind(protocol=None, predictions=None, parameters=None):
    """(dry run?, the protocol's acceptance) of a judge invocation.

    A --protocol file is judged only when it is a registered backend variant of the
    registered protocol (validation/tissue/composite_l4_agreement.judged_protocol); any
    other file, and any --predictions or --parameters, make a dry run.
    """
    from validation.tissue import composite_l4_agreement as agreement

    judged, acceptance = True, None
    if protocol:
        _, judged, acceptance = agreement.judged_protocol("g2", protocol)
    return bool(not judged or predictions or parameters), acceptance


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--items", type=lambda s: s.split(","), required=True)
    parser.add_argument(
        "--protocol",
        type=Path,
        help="a registered backend variant for a judged run; any other file for dry runs "
        "only (default: registered)",
    )
    parser.add_argument("--predictions", type=Path, help="dry runs only (default: registered)")
    parser.add_argument("--parameters", type=Path, help="dry runs only: W37 and Q7 inputs (JSON)")
    parser.add_argument(
        "--backend",
        choices=("cpu", "gpu"),
        help="set every definition's execution backend on a copy (the predictions, W37 and "
        "Q7; an L4 run: gpu); default: as registered",
    )
    args = parser.parse_args(argv)
    args.output.mkdir(parents=True, exist_ok=False)
    protocol, predictions = load(args.protocol, args.predictions)
    backend = None
    if args.backend:  # The registered definitions declare the CPU; their backend picks the device.
        from validation.tissue import composite_l4_agreement as agreement

        predictions, backend = agreement.with_backend(predictions, args.backend)
    params = dict(REGISTERED)
    if args.parameters:
        params |= json.loads(args.parameters.read_text())
    dry, acceptance = run_kind(args.protocol, args.predictions, args.parameters)
    kwargs = dict(
        Q1=dict(
            w37=dict(
                rim=tuple(params["w37_rim"]), inner=params["w37_inner"], step=params["w37_step"]
            )
        ),
        Q7=dict(channel_scale=params["q7_channel_scale"]),
    )
    if args.backend:  # The two worlds the judge builds itself, outside the predictions.
        kwargs["Q1"]["w37"]["backend"] = args.backend
        kwargs["Q7"]["backend"] = args.backend
    for item in args.items:
        started = time.perf_counter()
        out = {k: dict(cases={}) for k in ("Q1", "Q2", "Q3", "Q4", "Q5")}
        produced = ("Q1", "Q3", "Q4") if item == "Q1" else (item,)
        try:
            ITEMS[item](protocol, predictions, out, **kwargs.get(item, {}))
        except Exception as error:  # Kept as evidence with any partial results; the item fails.
            for name in produced:
                out.setdefault(name, {})
                out[name].update(verdict="fail", error=repr(error), tb=traceback.format_exc())
        for name in produced:
            result = out[name]
            if "verdict" not in result:
                cases = result.get("cases", {})
                result["verdict"] = (
                    "pass"
                    if cases and all(c["verdict"] == "pass" for c in cases.values())
                    else "fail"
                )
            result.update(
                item=name,
                dry_run=dry,
                inputs=dict(
                    protocol=str(args.protocol or qual.PROTOCOL),
                    protocol_acceptance=acceptance or "the registered protocol",
                    predictions=str(args.predictions or qual.PREDICTIONS),
                    parameters=params,
                    **({} if backend is None else dict(backend=backend)),
                ),
                wall_s=time.perf_counter() - started,
                **provenance(),
            )
            with open(args.output / f"{name}.json", "x") as f:
                json.dump(result, f, indent=1, default=float)
            print(name, result["verdict"], round(result["wall_s"], 1), "s", flush=True)


if __name__ == "__main__":
    main()
