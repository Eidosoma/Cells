"""The harness's fine runs (REGISTRATION_20261118.md §5.1-§5.2) and M3's c_e2e (§5.4).

One arm per call: H2 at its dt through the engine's windowed runner (window_steps 2048, device
row checks), keeping the full state at every observation row through the runner's sink, and the
run's cost record. Stage 0 makes no qualification claim (amendment 1, Q1).

Outputs in OUT_DIR: rows.npz (times and every state field at the observation rows) and run.json
(the arm, the steps, the runner's timings, diagnostics and resources, wall and CPU seconds,
c_e2e, CPU affinity, BLAS record and the snapshot's revision).

Usage: python -m validation.long_duration.harness ARM OUT_DIR [DEVELOPMENT_END]
(ARM: R1, R2 or R3; a DEVELOPMENT_END horizon makes a smoke run, never a run of record)
"""

import json
import os
import sys
import time
from pathlib import Path

import numpy as np

DYNAMIC_FIELDS = ("amount_increment", "extracellular_amount_increment", "channel_gate",
                  "junction_gate")  # fmt: skip


class Keeper:
    """A windowed run's sink: the full state at each wanted time, first occurrence kept (a
    window's first row repeats the previous window's last)."""

    def __init__(self, wanted):
        self.wanted = np.asarray(sorted(set(float(t) for t in wanted)))
        self.rows = {}
        self.fields = None

    def __call__(self, window):
        times = np.asarray(window.times, dtype=float)
        history = window.history
        if self.fields is None:
            self.fields = type(history)._fields
        hits = np.flatnonzero(np.isin(times, self.wanted))
        for i in hits:
            t = float(times[i])
            if t not in self.rows:
                self.rows[t] = tuple(np.array(np.asarray(v)[i], copy=True) for v in history)

    def stacked(self):
        missing = [t for t in self.wanted if float(t) not in self.rows]
        if missing:
            raise RuntimeError(f"{len(missing)} observation rows were not seen, first {missing[0]}")
        times = np.asarray(sorted(self.rows))
        columns = list(zip(*(self.rows[t] for t in times), strict=True))
        return times, {k: np.stack(v) for k, v in zip(self.fields, columns, strict=True)}


def snapshot_revision(root=None):
    path = Path(root or os.getcwd()) / "SNAPSHOT.json"
    if not path.is_file():
        return None
    return json.loads(path.read_text())["git_revision"]


def cue_times(raw):
    """(on, off) of the cue channel's schedule, read from the definition."""
    group = next(g for g in raw["experiment"]["channel_controls"] if g["channel_id"] == "cue_0")
    changes = [c["time"] for c in group["schedule"] if c["time"] > 0]
    return float(changes[0]), float(changes[1])


def run_arm(arm, out_dir, development_end=None):
    import jax

    jax.config.update("jax_enable_x64", True)
    from cells.definitions.specs import parse_spec
    from cells.execution import blas_threads
    from cells.execution.windows import WindowPolicy, run_windowed
    from validation.long_duration import worlds

    reg = worlds.registration()["harness"]
    dt = reg["arms_dt_s"][arm]
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=False)
    raw = worlds.h2(dt, development_end=development_end)
    spec = parse_spec(raw)
    keeper = Keeper(spec.experiment.observation_times)
    policy = WindowPolicy(
        window_steps=reg["window_steps"], recording="observations", row_checks=reg["row_checks"]
    )
    started, cpu = time.perf_counter(), time.process_time()
    record = dict(
        measurement="harness",
        arm=arm,
        dt_s=dt,
        development_end_s=development_end,
        run_of_record=development_end is None,
        cue_s=cue_times(raw),
        registration=worlds.registration()["registration"],
        qualification_claim="none (stage 0; amendment 1, Q1)",
        snapshot_revision=snapshot_revision(),
        cpu_affinity=sorted(os.sched_getaffinity(0)),
        started_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    )
    try:
        result = run_windowed(spec, policy, sink=keeper)
    except Exception as error:  # A refusal is the arm's result (§0): recorded, then re-raised.
        record.update(
            status="refused",
            error_type=type(error).__name__,
            error=str(error),
            wall_seconds=time.perf_counter() - started,
            cpu_seconds=time.process_time() - cpu,
        )
        (out / "run.json").write_text(json.dumps(record, indent=1) + "\n")
        raise
    wall, cpu = time.perf_counter() - started, time.process_time() - cpu
    times, rows = keeper.stacked()
    np.savez_compressed(out / "rows.npz", times=times, **rows)
    steps = int(result.resources["executed_steps"])
    timings = {k: float(v) for k, v in result.timings.items()}
    compile_seconds = sum(v for k, v in timings.items() if "compile" in k)
    record.update(
        status="complete",
        steps=steps,
        end_time_s=float(result.final.time),
        observation_rows=len(times),
        timings=timings,
        diagnostics={k: float(v) for k, v in result.diagnostics.items()},
        resources=json.loads(json.dumps(result.resources, default=str)),
        wall_seconds=wall,
        cpu_seconds=cpu,
        c_e2e_s=timings["total_run_seconds"] / steps,
        c_e2e_net_s=(timings["total_run_seconds"] - timings["preflight_seconds"] - compile_seconds)
        / steps,
        compile_seconds=compile_seconds,
        cpu_hours_per_simulated_hour=cpu / 3600.0 / (float(result.final.time) / 3600.0),
        fields=list(rows),
        history_fields=[k for k in rows if k not in DYNAMIC_FIELDS],
        blas=blas_threads.libraries(),
        finished_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    )
    (out / "run.json").write_text(json.dumps(record, indent=1, default=str) + "\n")
    print(json.dumps({k: record[k] for k in ("arm", "steps", "wall_seconds", "c_e2e_s")}))
    return 0


if __name__ == "__main__":
    # A third argument is a development horizon (s): a smoke run, never a run of record.
    sys.exit(run_arm(sys.argv[1], sys.argv[2], float(sys.argv[3]) if len(sys.argv) > 3 else None))
