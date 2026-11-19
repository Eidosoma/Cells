"""M3's cost forms (REGISTRATION_20261118.md §5.4), on one timed-lane CPU, one thread.

Programs: H2 at 1 ms; W0 with its operators as declared and no event in the timed windows; and
W0's inner sheet with R as an empty composition (regulated_availability_fixtures.sheet), for the
operators' share. For each:
* c_window: the engine's own window rollout (cells.execution.runner._compiled_window_rollout,
  lowered and compiled as the windowed runner does) over 2048 steps from the initial state, timed
  after a warm-up: the median of 7 repeats, programs interleaved;
* c_call: one jitted checked step (model.checked_step), the median of 30 calls after a warm-up
  (PUMP_COMPOSITE_V2_DESIGN §3's method).
A form is valid if IQR / median <= 0.10; otherwise it is repeated once and both are reported.
Every timed window must be valid (no refused step), or the form is reported as refused.
Stage 0 makes no qualification claim (amendment 1, Q1).

Usage: python -m validation.long_duration.m3_cost OUTPUT.json
"""

import json
import os
import statistics
import sys
import time

import numpy as np


def summary(samples):
    q = statistics.quantiles(samples, n=4)
    median = statistics.median(samples)
    return dict(
        median_s=median,
        iqr_s=q[2] - q[0],
        iqr_over_median=(q[2] - q[0]) / median,
        samples_s=list(samples),
    )


def window_program(raw, steps):
    """A callable timing one compiled window of `steps` steps of the definition from its
    initial state, and the window's validity."""
    import jax

    from cells.definitions.specs import parse_spec
    from cells.execution import runner
    from cells.execution.schedule import control_values
    from cells.execution.state import initialise
    from cells.registry.models import get_model

    spec = parse_spec(raw)
    model = get_model(spec.model)
    checkpoint = initialise(spec)
    dt = spec.execution.dt
    times = np.asarray([i * dt for i in range(steps + 1)])
    controls = control_values(spec, times[:-1])
    args = jax.device_put(
        (
            checkpoint.state,
            runner.integration_steps(spec, times),
            controls,
            model.parameters(spec, checkpoint.layout),
            checkpoint.layout.active,
            np.ones(steps, dtype=bool),
        )
    )
    compiled = runner._compiled_window_rollout.lower(
        *args,
        getattr(model, "rhs", None),
        getattr(model, "domain_valid", None),
        getattr(model, "checked_step", None),
    ).compile()

    def call():
        started = time.perf_counter()
        out = compiled(*args)
        jax.block_until_ready(out)
        return time.perf_counter() - started, bool(np.all(np.asarray(out[2])))

    return call


def call_program(raw):
    """A callable timing one jitted checked step from the initial state (the cost table's)."""
    import jax

    from validation.tissue import composite_crossrev as xr

    spec, model, (s, c, p) = xr._setup(raw)
    dt = jax.numpy.asarray(spec.execution.dt)
    step = jax.jit(lambda s, dt, c, p: model.checked_step(s, dt, c, p, p.active))

    def call():
        started = time.perf_counter()
        out = step(s, dt, c, p)
        jax.block_until_ready(out)
        return time.perf_counter() - started, bool(np.asarray(out[1]))

    return call


def interleaved(programs, repeats):
    """Each program called once to warm, then `repeats` rounds of one call each, in order."""
    for call in programs.values():
        call()
    samples = {k: [] for k in programs}
    valid = {k: True for k in programs}
    for _ in range(repeats):
        for name, call in programs.items():
            seconds, ok = call()
            samples[name].append(seconds)
            valid[name] &= ok
    return samples, valid


def measured(programs, repeats, limit, per_step):
    """The registered form: interleaved repeats, repeated once if any IQR / median exceeds the
    limit; per-step medians (s) and validity per program."""
    attempts = []
    for _ in range(2):
        samples, valid = interleaved(programs, repeats)
        forms = {k: summary([s / per_step for s in v]) | {"valid_windows": valid[k]}
                 for k, v in samples.items()}  # fmt: skip
        attempts.append(forms)
        if all(f["iqr_over_median"] <= limit for f in forms.values()):
            break
    return attempts


def run(output):
    import jax

    jax.config.update("jax_enable_x64", True)
    from cells.execution import blas_threads
    from validation.long_duration import harness, worlds
    from validation.tissue import regulated_availability_fixtures as ra

    reg = worlds.registration()["m3"]
    steps, end = reg["window_steps"], 3.0
    raws = dict(
        h2=worlds.h2(1e-3),
        w0=worlds.w0(end=end),
        w0_empty=ra.sheet(end=end, dt=1e-3, observation_times=[0.0, end]),
    )
    out = dict(
        measurement="M3 cost",
        registration=worlds.registration()["registration"],
        qualification_claim="none (stage 0; amendment 1, Q1)",
        snapshot_revision=harness.snapshot_revision(),
        cpu_affinity=sorted(os.sched_getaffinity(0)),
        blas=blas_threads.libraries(),
        started_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    )
    started = time.perf_counter()
    windows = {k: window_program(v, steps) for k, v in raws.items()}
    out["compile_seconds_windows"] = time.perf_counter() - started
    out["c_window"] = measured(windows, reg["window_repeats"], reg["iqr_over_median_max"], steps)
    calls = {k: call_program(v) for k, v in raws.items()}
    out["c_call"] = measured(calls, reg["call_repeats"], reg["iqr_over_median_max"], 1)
    share = {}
    for form in ("c_window", "c_call"):
        last = out[form][-1]
        with_ops, empty = last["w0"]["median_s"], last["w0_empty"]["median_s"]
        s = 1.0 - empty / with_ops
        share[form] = dict(
            w0_s=with_ops,
            w0_empty_s=empty,
            share=s,
            n1_gain_bound=1.0 / (1.0 - s) if s < 1 else None,
        )
    out["operators_share"] = share
    out["benchmarks"] = worlds.registration()["benchmarks"]["operators_share"] | dict(
        n1_gain_bound=worlds.registration()["benchmarks"]["n1_gain_bound"],
        one_core_step_ms_sheet7=worlds.registration()["benchmarks"]["one_core_step_ms"]["14"],
    )
    out["seconds"] = time.perf_counter() - started
    with open(output, "x") as stream:
        json.dump(out, stream, indent=1)
        stream.write("\n")
    print(json.dumps(share))
    return 0


if __name__ == "__main__":
    sys.exit(run(sys.argv[1]))
