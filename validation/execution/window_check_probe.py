"""Where a scalar window's wall time goes, and the device row checks on the same rows.

A measurement probe for docs/WINDOW_DEVICE_CHECKS_DESIGN.md (development evidence, not a
verdict). For each world, given as a results-baseline record (validation/results_baseline.py:
SET/WORLD.json holds the definition run) or as a definition file:

1. **The scalar windowed path as it is** (core.windows.iter_windows, the runner's window
   rollout): up to --windows windows of --window-steps steps. Each window's own timings
   (core.runner._segment) are kept, with the model's check_values and observe_history timed
   apart. The rows each check_values call received are kept, so a window that the host check
   refuses still gives its rows.
2. **Inside the host check:** cProfile of one check_values call on the last window's rows (the
   functions under it by total and cumulative time).
3. **The model's device checks on the same rows** (model.device_checks, as
   execution/vector_windows.py runs them for each world): compiled once vmapped over the rows and
   once as a scan over the rows reduced to per-check first failing rows and diagnostic maxima
   (the summary a device window would return); compile seconds and warm seconds per row.
4. **Parity, row by row:** check_values on each row alone (its row tests, with the row's step
   count) against the device row's failure bits and diagnostics: whether the verdicts agree,
   and per diagnostic the largest |host - device| over the rows and the largest |host|.

**--long: each ledger's ratio to its bound over a long run** (the design's first clean-core
measurement, §3.2, and the guard band's handback rate). The runner's own compiled window rollout
steps every window (no host checks, no observers), and after each window a compiled scan of the
model's device checks over its rows returns each ledger's largest |residual| / bound, each
diagnostic's maximum and each check's first failing row. The ratios come from the models' own
device checks: surface_pump_checks.row_checks is wrapped in this process only, recomputing the
ledgers and bounds it receives (the design's margins keyword is not built). Every
--sample-every-th window, the host's check_values runs on the same rows and its diagnostics are
compared with the device maxima. Reported: the ratios' maxima over the run and over its last
tenth, and the windows a pass filter with a guard band at 1/2 would hand to the host.

Usage (venv-cpu, CPU only, from the checkout or a snapshot on PYTHONPATH):
  python -m validation.execution.window_check_probe OUT \
      [--baseline DIR --worlds SET/WORLD ...] [--definition NAME=PATH ...] [--fr4-dt DT] \
      [--window-steps N] [--windows K] [--repeats R] \
      [--long [--sample-every S] [--max-windows M]]
Writes OUT/<name>.json per world and OUT/summary.json (with the source's git state).
"""

import argparse
import cProfile
import json
import os
import platform
import pstats
import subprocess
import sys
import traceback
from pathlib import Path
from time import perf_counter

import numpy as np


def source():
    root = Path(__file__).resolve().parents[2]
    git = ["git", "-C", str(root)]
    run = lambda *a: subprocess.run([*git, *a], capture_output=True, text=True).stdout.strip()  # noqa: E731
    from validation import executed_sources  # noqa: PLC0415
    executed_sources.refuse_untracked(root, "window_check_probe's source record")  # D259

    return dict(
        root=str(root),
        git_revision=run("rev-parse", "HEAD"),
        dirty=run("status", "--porcelain", "--untracked-files=no"),
    )


class Timed:
    """A model method wrapped with a timer. Keeps (seconds, rows, arguments) of the calls since
    the last take(): a window's main check_values call is its first call with the most rows
    (the checkpoint validation checks one row, the observation-continuity check the observed
    rows after the window's)."""

    def __init__(self, function):
        self.function, self.pending = function, []
        # inspect.signature follows __wrapped__, so runner.takes_steps still sees `steps`.
        self.__wrapped__ = function

    def __call__(self, *args, **kwargs):
        started = perf_counter()
        try:
            return self.function(*args, **kwargs)
        finally:
            rows = np.shape(getattr(args[0], "amount_increment", np.zeros((1, 1, 1))))
            count = rows[0] if len(rows) == 3 else 1
            self.pending.append((perf_counter() - started, count, (args, kwargs)))

    def take(self):
        calls, self.pending = self.pending, []
        if not calls:
            return None, 0.0, None
        main = max(range(len(calls)), key=lambda i: (calls[i][1], -i))
        other = sum(c[0] for i, c in enumerate(calls) if i != main)
        return calls[main][0], other, calls[main][2]


def rows_of(history, start, stop):
    return type(history)(*(np.asarray(v)[start:stop] for v in history))


def profile_check(model, history, spec, steps, top=18):
    profile = cProfile.Profile()
    profile.enable()
    started = perf_counter()
    try:
        model.check_values(history, spec, steps=steps)
    except Exception as error:  # A refusing window still profiles up to its refusal.
        outcome = f"{type(error).__name__}: {error}"
    else:
        outcome = "passed"
    seconds = perf_counter() - started
    profile.disable()
    stats = pstats.Stats(profile)
    entries = []
    for (path, line, name), (_, calls, tottime, cumtime, _) in stats.stats.items():
        entries.append(
            dict(
                function=f"{Path(path).name}:{line}:{name}",
                calls=calls,
                tottime=tottime,
                cumtime=cumtime,
            )
        )
    by_total = sorted(entries, key=lambda e: -e["tottime"])[:top]
    cells = [e for e in entries if e["function"].split(":")[0].endswith(".py")]
    by_cumulative = sorted(cells, key=lambda e: -e["cumtime"])[:top]
    return dict(
        seconds=seconds,
        rows=len(steps),
        outcome=outcome,
        by_total=by_total,
        by_cumulative=by_cumulative,
    )


def device_programs(model):
    import jax
    import jax.numpy as jnp

    checks = model.device_checks
    vmapped = jax.jit(jax.vmap(checks, in_axes=(0, 0, None, None, 0)))

    def scanned(rows, steps, p, constants):
        """Per-check first failing row (-1: none) and diagnostic maxima over the rows."""
        first_row = jax.tree.map(lambda v: v[0], rows)
        failed0, values0 = checks(first_row, first_row, p, constants, steps[0])
        first = jnp.where(failed0, 0, -1).astype(jnp.int32)

        def advance(carry, inputs):
            previous, first, maxima = carry
            row, step, index = inputs
            failed, values = checks(previous, row, p, constants, step)
            first = jnp.where((first < 0) & failed, index, first)
            return (row, first, jnp.maximum(maxima, values)), None

        rest = jax.tree.map(lambda v: v[1:], rows)
        indices = jnp.arange(1, steps.shape[0], dtype=jnp.int32)
        (_, first, maxima), _ = jax.lax.scan(
            advance, (first_row, first, values0), (rest, steps[1:], indices)
        )
        return first, maxima

    return vmapped, jax.jit(scanned)


def timed_program(program, args, repeats):
    import jax

    started = perf_counter()
    compiled = program.lower(*args).compile()
    compile_seconds = perf_counter() - started
    best = None
    for _ in range(repeats):
        started = perf_counter()
        out = jax.block_until_ready(compiled(*args))
        seconds = perf_counter() - started
        best = seconds if best is None else min(best, seconds)
    return out, compile_seconds, best


def device_part(model, spec, layout, history, steps, repeats):
    params = model.parameters(spec, layout)
    constants = model.device_check_constants(spec)
    previous = type(history)(*(np.concatenate((v[:1], v[:-1])) for v in history))
    vmapped, scanned = device_programs(model)
    steps = np.asarray(steps, dtype=np.int64)
    (failed, values), vmap_compile, vmap_seconds = timed_program(
        vmapped, (previous, history, params, constants, steps), repeats
    )
    (first, maxima), scan_compile, scan_seconds = timed_program(
        scanned, (history, steps, params, constants), repeats
    )
    rows = len(steps)
    return (
        dict(
            rows=rows,
            vmap=dict(
                compile_seconds=vmap_compile,
                warm_seconds=vmap_seconds,
                ms_per_row=1e3 * vmap_seconds / rows,
            ),
            scan=dict(
                compile_seconds=scan_compile,
                warm_seconds=scan_seconds,
                ms_per_row=1e3 * scan_seconds / rows,
            ),
            scan_first_failing_rows={
                name: int(v) for name, v in zip(model.DEVICE_CHECKS, np.asarray(first), strict=True)
            },
            scan_maxima={
                name: float(v)
                for name, v in zip(model.DEVICE_DIAGNOSTICS, np.asarray(maxima), strict=True)
            },
        ),
        np.asarray(failed),
        np.asarray(values),
    )


def parity(model, spec, history, steps, failed, values):
    """check_values on each row alone against the device row (its own row tests)."""
    from cells.definitions.specs import ConfigError
    from cells.execution.errors import NumericalError

    names = model.DEVICE_DIAGNOSTICS
    rows = len(steps)
    host = np.full((rows, len(names)), np.nan)
    verdicts, disagreements = [], []
    started = perf_counter()
    for j in range(rows):
        try:
            found = model.check_values(rows_of(history, j, j + 1), spec, steps=[int(steps[j])])
            host[j] = [found[k] for k in names]
            message = None
        except (NumericalError, ConfigError) as error:
            message = str(error)
        bits = [n for n, f in zip(model.DEVICE_CHECKS, failed[j], strict=True) if f]
        if message is None and j and bits == ["dissipation"]:
            # The decrease since the predecessor: the host checks it over rows j - 1 and j.
            try:
                model.check_values(
                    rows_of(history, j - 1, j + 1),
                    spec,
                    steps=[int(s) for s in steps[j - 1 : j + 1]],
                )
            except (NumericalError, ConfigError) as error:
                message = str(error)
        device_fails = bool(bits)
        if (message is not None) != device_fails:
            disagreements.append(dict(row=j, host=message, device=bits))
        if message is not None or bits:
            verdicts.append(dict(row=j, host=message, device=bits))
    seconds = perf_counter() - started
    differences = {}
    for k, name in enumerate(names):
        ok = ~np.isnan(host[:, k])
        h, d = host[ok, k], values[ok, k]
        differences[name] = dict(
            rows=int(ok.sum()),
            largest_host=float(np.max(np.abs(h), initial=0.0)),
            largest_device=float(np.max(np.abs(d), initial=0.0)),
            largest_difference=float(np.max(np.abs(h - d), initial=0.0)),
            bitwise_rows=int(np.sum(h == d)),
        )
    return dict(
        single_row_host_seconds=seconds,
        failing_rows=verdicts[:20],
        disagreements=disagreements[:20],
        disagreement_count=len(disagreements),
        diagnostics=differences,
    )


def probe_world(name, raw, window_steps, windows, repeats):
    import jax

    from cells.definitions.specs import ConfigError, parse_spec
    from cells.execution.errors import NumericalError
    from cells.execution.windows import WindowPolicy, iter_windows
    from cells.registry.models import get_model

    record = dict(name=name)
    started = perf_counter()
    spec = parse_spec(raw)
    model = get_model(spec.model)
    record["model"] = getattr(model, "MODEL_ID", None) or str(spec.model.__class__.__name__)
    record["model_repr"] = repr(model)[:300]
    record["model_cached"] = get_model(spec.model) is model
    record["device_hooks"] = all(
        hasattr(model, k) for k in ("device_checks", "DEVICE_CHECKS", "device_check_constants")
    )
    check, observe = Timed(model.check_values), Timed(model.observe_history)
    model.check_values, model.observe_history = check, observe
    last, results = None, []
    try:
        for index, window in enumerate(
            iter_windows(spec, WindowPolicy(window_steps, "checkpoints"))
        ):
            main, other, last = check.take()
            observed = sum(c[0] for c in observe.pending)
            observe.pending = []
            results.append(
                dict(
                    index=index,
                    steps=len(window.times) - 1,
                    timings=dict(window.timings),
                    check_values_seconds=main,
                    other_check_values_seconds=other,
                    observe_seconds=observed,
                )
            )
            if index + 1 >= windows:
                break
        record["refusal"] = None
    except (NumericalError, ConfigError) as error:
        record["refusal"] = dict(type=type(error).__name__, message=str(error)[:600])
        _, _, refused = check.take()
        last = refused or last
    finally:
        model.check_values, model.observe_history = check.function, observe.function
    record["windows"] = results
    warm = [w for w in results if w["index"] > 0] or results
    if warm:
        steps = sum(w["steps"] for w in warm)
        execute = sum(w["timings"]["execute_seconds"] for w in warm)
        checks = sum(w["check_values_seconds"] for w in warm)
        analysis = sum(w["timings"]["analysis_seconds"] for w in warm)
        total = sum(w["timings"]["total_run_seconds"] for w in warm)
        rows = sum(w["steps"] + 1 for w in warm)
        full = [w for w in warm if w["steps"]]
        record["warm"] = dict(
            windows=len(warm),
            steps=steps,
            checked_rows=rows,
            execute_ms_per_step=1e3 * execute / max(steps, 1),
            host_check_ms_per_row=1e3 * checks / max(rows, 1),
            median_execute_ms_per_step=float(
                np.median([1e3 * w["timings"]["execute_seconds"] / w["steps"] for w in full])
            )
            if full
            else None,
            median_host_check_ms_per_row=float(
                np.median([1e3 * w["check_values_seconds"] / (w["steps"] + 1) for w in full])
            )
            if full
            else None,
            other_check_seconds=sum(w["other_check_values_seconds"] for w in warm),
            observe_seconds=sum(w["observe_seconds"] for w in warm),
            transfer_seconds=sum(w["timings"]["host_transfer_and_assembly_seconds"] for w in warm),
            preparation_seconds=sum(w["timings"]["preparation_seconds"] for w in warm),
            analysis_seconds=analysis,
            total_seconds=total,
            host_check_share=checks / total if total else None,
        )
    if last is not None:
        (history, _spec), kwargs = last
        history = type(history)(*(np.asarray(v) for v in history))
        steps = kwargs.get("steps")
        steps = np.arange(len(history.amount_increment)) if steps is None else np.asarray(steps)
        record["profile"] = profile_check(model, history, spec, steps)
        if record["device_hooks"]:
            from cells.execution.state import initialise

            layout = initialise(spec).layout
            layout = type(layout)(*(np.asarray(v) for v in layout))
            try:
                record["device"], failed, values = device_part(
                    model, spec, layout, history, steps, repeats
                )
                record["parity"] = parity(model, spec, history, steps, failed, values)
            except Exception:  # Recorded, not fatal: the probe reports what it could measure.
                record["device_error"] = traceback.format_exc()[-3000:]
    record["seconds"] = perf_counter() - started
    jax.clear_caches()
    return record


GUARD_BAND = 0.5  # The design's HOST_DECIDES_ABOVE (§4.2): above it, the host decides a window.


def ratio_checks(model):
    """(scan program, ledger names): the model's device checks over a window's rows with each
    ledger's largest |residual| / bound. surface_pump_checks.row_checks is wrapped while the
    program traces (here only), recomputing the ledgers and bounds it is given."""
    import jax
    import jax.numpy as jnp

    import cells.models.pump_composite as composite
    import cells.models.surface_pump_checks as shared

    original, names = shared.row_checks, []

    def with_ratios(previous, row, p, constants, steps, **hooks):
        failed, values = original(previous, row, p, constants, steps, **hooks)
        ledgers = hooks["balances"](row, p)
        _, bounds = hooks["limits"](
            row,
            p,
            constants.material_atol,
            constants.energy_rtol,
            steps=steps,
            magnitudes=hooks["magnitudes"](row, p, xp=jnp),
            xp=jnp,
        )
        names[:] = list(ledgers)
        ratios = []
        for value, bound in zip(ledgers.values(), bounds, strict=True):
            size = jnp.abs(value)
            ratio = jnp.where(size == 0, 0.0, size / bound)
            ratios.append(jnp.max(jnp.where(jnp.isnan(ratio), jnp.inf, ratio), initial=0.0))
        return failed, values, jnp.stack(ratios)

    def scan(start, history, count, first_step, params, constants):
        width = jax.tree.leaves(history)[0].shape[0]
        failed0, values0, ratios0 = model.device_checks(start, start, params, constants, first_step)
        first = jnp.where(failed0, 0, -1).astype(jnp.int64)

        def advance(carry, inputs):
            previous, first, maxima, ratios = carry
            row, index = inputs
            failed, values, rate = model.device_checks(
                previous, row, params, constants, first_step + index
            )
            live = index <= count
            first = jnp.where(live & (first < 0) & failed, index, first)
            maxima = jnp.where(live, jnp.maximum(maxima, values), maxima)
            ratios = jnp.where(live, jnp.maximum(ratios, rate), ratios)
            return (row, first, maxima, ratios), None

        indices = jnp.arange(1, width + 1, dtype=jnp.int64)
        (_, first, maxima, ratios), _ = jax.lax.scan(
            advance, (start, first, values0, ratios0), (history, indices)
        )
        return first, maxima, ratios

    def build(args):
        shared.row_checks = composite.row_checks = with_ratios
        try:
            return jax.jit(scan).lower(*args).compile()
        finally:
            shared.row_checks = composite.row_checks = original

    return build, names


def long_run(name, raw, window_steps, sample_every, max_windows):
    """Every window by the runner's compiled rollout, with the device ratio scan after each."""
    import jax

    from cells.definitions.specs import parse_spec
    from cells.execution.devices import execution_device
    from cells.execution.runner import _compiled_window_rollout, integration_steps
    from cells.execution.schedule import control_values
    from cells.execution.state import initialise
    from cells.execution.windows import WindowPolicy, plan_windows
    from cells.registry.models import get_model

    started = perf_counter()
    spec = parse_spec(raw)
    plan = plan_windows(spec, WindowPolicy(window_steps, "checkpoints"))
    spec, model = plan.spec, get_model(plan.spec.model)
    device = execution_device(spec.execution.backend)
    start = initialise(spec)
    layout = type(start.layout)(*(np.asarray(v) for v in start.layout))
    width = min(window_steps, len(plan.grid) - 1 - plan.start_step)
    params = jax.device_put(model.parameters(spec, layout), device)
    active = jax.device_put(layout.active, device)
    constants = jax.device_put(model.device_check_constants(spec), device)
    state = jax.device_put(start.state, device)
    build, names = ratio_checks(model)
    rollout = checks = None
    step_index, windows, samples = start.step_index, [], []
    timing = dict(compile_seconds=0.0, step_seconds=0.0, check_seconds=0.0, host_seconds=0.0)
    refusal = None
    for k, times in enumerate(plan.grid.windows(plan.start_step, window_steps)):
        if max_windows and k >= max_windows:
            break
        count = len(times) - 1
        pad = width - count
        steps = np.pad(integration_steps(spec, times), (0, pad))
        controls = jax.tree.map(
            lambda v, pad=pad: np.pad(v, ((0, pad), *((0, 0) for _ in v.shape[1:]))),
            control_values(spec, times[:-1]),
        )
        enabled = np.arange(width) < count
        args = jax.device_put((state, steps, controls, params, active, enabled), device)
        if rollout is None:
            began = perf_counter()
            rollout = _compiled_window_rollout.lower(
                *args,
                getattr(model, "rhs", None),
                getattr(model, "domain_valid", None),
                getattr(model, "checked_step", None),
            ).compile()
            timing["compile_seconds"] += perf_counter() - began
        began = perf_counter()
        final, history, valid = jax.block_until_ready(rollout(*args))
        timing["step_seconds"] += perf_counter() - began
        refused = np.flatnonzero(~np.asarray(valid)[:count])
        if len(refused):
            refusal = dict(window=k, step=int(step_index + refused[0] + 1), kind="step")
            break
        inputs = (state, history, np.int64(count), np.int64(step_index), params, constants)
        if checks is None:
            began = perf_counter()
            checks = build(inputs)
            timing["compile_seconds"] += perf_counter() - began
        began = perf_counter()
        first, maxima, ratios = (np.asarray(v) for v in checks(*inputs))
        timing["check_seconds"] += perf_counter() - began
        record = dict(
            window=k,
            end_step=int(step_index + count),
            ratios=[float(v) for v in ratios],
            maxima=[float(v) for v in maxima],
            failing={c: int(f) for c, f in zip(model.DEVICE_CHECKS, first, strict=True) if f >= 0},
        )
        windows.append(record)
        if sample_every and k % sample_every == 0:
            rows = model.STATE_TYPE(
                *(
                    np.concatenate((np.asarray(a)[None], np.asarray(b)[:count]))
                    for a, b in zip(state, history, strict=True)
                )
            )
            began = perf_counter()
            try:
                host = model.check_values(rows, spec, steps=step_index + np.arange(count + 1))
                outcome = None
            except Exception as error:
                host, outcome = {}, f"{type(error).__name__}: {error}"
            timing["host_seconds"] += perf_counter() - began
            samples.append(
                dict(
                    window=k,
                    host_outcome=outcome,
                    differences={
                        d: dict(host=host[d], device=record["maxima"][j])
                        for j, d in enumerate(model.DEVICE_DIAGNOSTICS)
                        if d in host
                    },
                )
            )
        state, step_index = final, step_index + count
    ratios = np.array([w["ratios"] for w in windows]) if windows else np.zeros((0, len(names)))
    late = ratios[int(0.9 * len(ratios)) :] if len(ratios) else ratios
    handed = [
        w["window"] for w in windows if w["failing"] or max(w["ratios"], default=0) > GUARD_BAND
    ]
    return dict(
        name=name,
        model=getattr(model, "MODEL_ID", None),
        window_steps=window_steps,
        windows=len(windows),
        steps=int(step_index - start.step_index),
        refusal=refusal,
        ledgers=list(names),
        max_ratio={
            n: float(v) for n, v in zip(names, ratios.max(axis=0, initial=0.0), strict=True)
        },
        late_max_ratio={
            n: float(v) for n, v in zip(names, late.max(axis=0, initial=0.0), strict=True)
        },
        handed_to_host=len(handed),
        handback_rate=len(handed) / len(windows) if windows else None,
        first_handed=handed[:20],
        timings=timing | dict(total_seconds=perf_counter() - started),
        samples=samples,
        per_window=windows,
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("out", type=Path)
    parser.add_argument("--baseline", type=Path)
    parser.add_argument("--worlds", nargs="*", default=[])
    parser.add_argument("--definition", nargs="*", default=[], help="NAME=PATH")
    parser.add_argument("--window-steps", type=int, default=200)
    parser.add_argument("--windows", type=int, default=2)
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument("--fr4-dt", type=float, help="FR-4's development world at this dt")
    parser.add_argument("--long", action="store_true", help="each ledger's ratio over a long run")
    parser.add_argument("--sample-every", type=int, default=50)
    parser.add_argument("--max-windows", type=int, default=0)
    args = parser.parse_args(argv)
    import jax

    from validation import id_table

    jax.config.update("jax_enable_x64", True)
    args.out.mkdir(parents=True, exist_ok=True)
    worlds = []
    for key in args.worlds:
        set_name, name = key.split("/", 1)
        path = args.baseline / set_name / (name.replace("/", "__") + ".json")
        worlds.append((key, id_table.load(path)["definition"]))
    for item in args.definition:
        name, path = item.split("=", 1)
        worlds.append((name, json.loads(Path(path).read_text())))
    if args.fr4_dt:
        from validation.compartment_ph_engine.definitions import development_world, fr4_world

        worlds.append((f"fr4_dt{args.fr4_dt:g}", development_world(fr4_world(dt_s=args.fr4_dt))))
    summary = dict(
        kind="cells.window_check_probe@1",
        source=source(),
        environment=dict(
            jax=jax.__version__,
            numpy=np.__version__,
            python=platform.python_version(),
            cpu_affinity=sorted(os.sched_getaffinity(0)),
            nice=os.nice(0),
            JAX_PLATFORMS=os.environ.get("JAX_PLATFORMS"),
            XLA_FLAGS=os.environ.get("XLA_FLAGS"),
        ),
        arguments=dict(
            window_steps=args.window_steps,
            windows=args.windows,
            repeats=args.repeats,
            long=args.long,
            sample_every=args.sample_every,
            max_windows=args.max_windows,
            guard_band=GUARD_BAND,
        ),
        worlds={},
    )
    for key, raw in worlds:
        print(f"{key}: start", flush=True)
        if args.long:
            try:
                record = long_run(key, raw, args.window_steps, args.sample_every, args.max_windows)
            except Exception:
                record = dict(name=key, error=traceback.format_exc()[-4000:])
            (args.out / (key.replace("/", "__") + ".json")).write_text(
                json.dumps(record, indent=1, default=str) + "\n"
            )
            summary["worlds"][key] = {
                k: record.get(k)
                for k in (
                    "model",
                    "windows",
                    "steps",
                    "refusal",
                    "max_ratio",
                    "late_max_ratio",
                    "handed_to_host",
                    "handback_rate",
                    "timings",
                    "error",
                )
            }
            (args.out / "summary.json").write_text(
                json.dumps(summary, indent=1, default=str) + "\n"
            )
            print(f"{key}: {json.dumps(summary['worlds'][key], default=str)[:2000]}", flush=True)
            continue
        try:
            record = probe_world(key, raw, args.window_steps, args.windows, args.repeats)
        except Exception:
            record = dict(name=key, error=traceback.format_exc()[-4000:])
        (args.out / (key.replace("/", "__") + ".json")).write_text(
            json.dumps(record, indent=1, default=str) + "\n"
        )
        warm = record.get("warm", {})
        device = record.get("device", {})
        summary["worlds"][key] = dict(
            model=record.get("model"),
            refusal=record.get("refusal"),
            error=bool(record.get("error") or record.get("device_error")),
            execute_ms_per_step=warm.get("execute_ms_per_step"),
            median_execute_ms_per_step=warm.get("median_execute_ms_per_step"),
            host_check_ms_per_row=warm.get("host_check_ms_per_row"),
            median_host_check_ms_per_row=warm.get("median_host_check_ms_per_row"),
            host_check_share=warm.get("host_check_share"),
            device_vmap_ms_per_row=device.get("vmap", {}).get("ms_per_row"),
            device_scan_ms_per_row=device.get("scan", {}).get("ms_per_row"),
            device_scan_compile_seconds=device.get("scan", {}).get("compile_seconds"),
            parity_disagreements=record.get("parity", {}).get("disagreement_count"),
            seconds=record.get("seconds"),
        )
        (args.out / "summary.json").write_text(json.dumps(summary, indent=1, default=str) + "\n")
        print(f"{key}: {json.dumps(summary['worlds'][key], default=str)}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
