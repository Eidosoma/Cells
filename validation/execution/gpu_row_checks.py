"""Device row checks on a GPU: the evidence for execution/row_checks.GPU_QUALIFIED (D330).

docs/WINDOW_DEVICE_CHECKS_DESIGN.md §10. One definition per process, on the production path,
cells.execution.windows.iter_windows with WindowPolicy(width, recording, mode), on the
definition's own backend. Actions:

pair: WINDOWS windows in host mode, then the same windows in device mode, in one process, so that
both modes compile the same program with the same compiler state.
- C1: each window's times, history, observations and final state, compared by bytes between the
  modes; any array that differs is named.
- C2, the host-against-device spread: for each window and each ledger, the host's ratio
  |residual| / bound over the window's rows against the device's (G2 reads the windows the device
  decided; a window handed back is recorded too, for the diagnosis). The host's is
  computed with NumPy from the model's own host ledger functions (balances, magnitudes,
  ledger_limits) and its device-check constants, as the device's program computes its own; the
  largest difference over windows is the spread, in units of the bound. Each diagnostic's device
  maximum is also set against host mode's check_values, under the device-check tests' criteria
  (tests/window_row_check_fixtures.agrees), and reported.
- The band: each window's outcome (who decided, and why) and each ledger's largest device ratio,
  against row_checks.HOST_DECIDES_ABOVE.
long: STEPS steps in device mode only: every window's outcome and ratios, and every SAMPLE-th
window's C2 from its own rows.
twice: WINDOWS windows in device mode, twice in one process (a diagnostic of run-to-run
determinism: one mode, one compiled program, two runs), compared by bytes window by window.
compare: two saved final states (pair --state, or one window's of pair --states), array by array:
identical bytes, else the largest difference relative to the array's scale (its largest
magnitude), the index where it lies and the number of entries that differ. For the spread between
processes or devices; no value is printed.
Both record each mode's wall and CPU seconds per window (and ms per step after the first window),
the check program's temporary bytes, the device's peak bytes in use, and SHA-256 digests of each
device-mode window's arrays, for comparing processes. Ratios, digests, timings and memory only:
no amount or state value is written (GJ-N1's blindness, D330).

Usage (the source on PYTHONPATH, JAX_ENABLE_X64=1):
  python -B -m validation.execution.gpu_row_checks pair OUT.json DEFINITION.json --windows N
  python -B -m validation.execution.gpu_row_checks long OUT.json DEFINITION.json --steps N \\
      [--sample-every 50]
  python -B -m validation.execution.gpu_row_checks compare OUT.json A.npz B.npz
  Options: --width W (default 32, GJ-N1's field windows), --recording observations|checkpoints.
"""

import argparse
import hashlib
import json
import os
import resource
import sys
from pathlib import Path
from time import perf_counter

import numpy as np


def source():
    """The source's identity: its snapshot record (registered runs run from a frozen snapshot)."""
    root = Path(__file__).resolve().parents[2]
    snapshot = root / "SNAPSHOT.json"
    if not snapshot.exists():
        return dict(root=str(root), snapshot=None)
    record = json.loads(snapshot.read_text())
    keys = ("git_revision", "dirty", "status", "patch_sha256")
    return dict(root=str(root), snapshot={k: record.get(k) for k in keys if k in record})


def cpu_seconds():
    usage = resource.getrusage(resource.RUSAGE_SELF)
    return usage.ru_utime + usage.ru_stime


def arrays(window):
    """(name, array) of a window's times, history, observations and final state, in order."""
    out = [("times", np.asarray(window.times))]
    out += [(f"history.{k}", np.asarray(v)) for k, v in window.history._asdict().items()]
    if window.observations is not None:
        out += [(f"observations.{k}", np.asarray(v)) for k, v in vars(window.observations).items()]
    out += [(f"final.{k}", np.asarray(v)) for k, v in window.final.state._asdict().items()]
    return out


def digest(window):
    """SHA-256 of every array's bytes (with its name, dtype and shape), and per array."""
    whole, each = hashlib.sha256(), {}
    for name, value in arrays(window):
        h = hashlib.sha256(f"{name}|{value.dtype}|{value.shape}|".encode() + value.tobytes())
        each[name] = h.hexdigest()[:16]
        whole.update(h.digest())
    return whole.hexdigest()[:16], each


def host_ratios(model, spec, p, constants, window):
    """Each ledger's largest |residual| / bound over the window's rows, with NumPy: the host twin
    of the device checks' margins (models/surface_pump_checks.row_checks): 0 for a zero residual,
    +inf for a NaN one."""
    history = window.history
    first = window.final.step_index - (len(window.times) - 1)
    ratios = {name: 0.0 for name in model.DEVICE_CHECKS[1:-1]}
    with np.errstate(all="ignore"):
        for k in range(len(window.times)):
            row = type(history)(*(np.asarray(v)[k] for v in history))
            b = model.balances(row, p)
            _, bounds = model.ledger_limits(
                row,
                p,
                np.asarray(constants.material_atol),
                np.asarray(constants.energy_rtol),
                steps=first + k,
                magnitudes=model.magnitudes(row, p, xp=np),
                xp=np,
            )
            for (name, value), bound in zip(b.items(), bounds, strict=True):
                magnitude = np.abs(np.asarray(value))
                ratio = np.where(magnitude == 0, 0.0, magnitude / bound)
                ratio = np.where(np.isnan(ratio), np.inf, ratio)
                ratios[name] = max(ratios[name], float(np.max(ratio, initial=0.0)))
    return ratios


def criteria(spec, host_diagnostics, device_diagnostics):
    """The device-check tests' criteria on each diagnostic (reported): (key, host, device, ok)."""
    from tests.window_row_check_fixtures import agrees  # noqa: PLC0415

    tol = float(np.min(spec.execution.material_balance_atol_fmol))
    out = []
    for key, host in host_diagnostics.items():
        try:
            ok = bool(agrees(key, host, device_diagnostics[key], tol))
        except AssertionError:  # A diagnostic without a declared criterion there.
            ok = None
        out.append((key, host, device_diagnostics[key], ok))
    return out


class Clock:
    """Wall and CPU seconds between consecutive windows."""

    def __init__(self):
        self.mark = (perf_counter(), cpu_seconds())

    def lap(self):
        now = (perf_counter(), cpu_seconds())
        out = dict(wall_s=now[0] - self.mark[0], cpu_s=now[1] - self.mark[1])
        self.mark = now
        return out


def per_step(laps, windows):
    """ms per step (wall and CPU) after the first window."""
    after = list(zip(laps[1:], windows[1:], strict=True))
    steps = sum(len(w.times) - 1 for _, w in after)
    if not steps:
        return None
    return dict(
        wall_ms=1e3 * sum(lap["wall_s"] for lap, _ in after) / steps,
        cpu_ms=1e3 * sum(lap["cpu_s"] for lap, _ in after) / steps,
        steps=steps,
    )


def device_memory(spec):
    from cells.execution.devices import execution_device  # noqa: PLC0415

    stats = execution_device(spec.execution.backend).memory_stats() or {}
    return {k: stats[k] for k in ("peak_bytes_in_use", "bytes_in_use") if k in stats}


def compare(out, a_path, b_path):
    """Array by array: identical bytes, else max |a - b| / max |a| and the entries that differ."""
    with np.load(a_path) as a, np.load(b_path) as b:
        if sorted(a.files) != sorted(b.files):
            raise RuntimeError(f"{a_path} and {b_path} hold different arrays")
        report = {}
        for k in sorted(a.files):
            x, y = a[k], b[k]
            if x.dtype == y.dtype and x.shape == y.shape and x.tobytes() == y.tobytes():
                report[k] = dict(identical=True)
                continue
            scale = float(np.max(np.abs(x), initial=0.0))
            difference = np.abs(x.astype(np.float64) - y.astype(np.float64))
            report[k] = dict(
                identical=False,
                relative_to_scale=float(np.max(difference)) / scale if scale else float("inf"),
                largest_at=[int(i) for i in np.unravel_index(np.argmax(difference), x.shape)],
                entries_differing=int(np.count_nonzero(x != y)),
                entries=int(x.size),
            )
    summary = dict(
        arrays=len(report),
        identical=sum(r["identical"] for r in report.values()),
        largest_relative_to_scale=max(
            (r["relative_to_scale"] for r in report.values() if not r["identical"]), default=0.0
        ),
    )
    Path(out).write_text(json.dumps(dict(a=str(a_path), b=str(b_path), summary=summary,
                                         arrays=report), indent=1))  # fmt: skip
    print(json.dumps(summary))
    return summary


def run(
    action,
    out,
    definition,
    *,
    windows,
    steps,
    width,
    recording,
    sample_every,
    state=None,
    states=None,
):
    import jax

    jax.config.update("jax_enable_x64", True)
    import cells  # noqa: F401, PLC0415  (pins BLAS threads at import, D190)
    from cells.definitions.specs import parse_spec  # noqa: PLC0415
    from cells.execution import row_checks  # noqa: PLC0415
    from cells.execution.windows import WindowPolicy, iter_windows  # noqa: PLC0415
    from cells.registry.models import get_model  # noqa: PLC0415

    raw = json.loads(Path(definition).read_text())
    dt = raw["execution"]["dt"]
    count = windows * width if action in ("pair", "twice") else steps
    raw["experiment"]["end_time"] = count * dt
    raw["experiment"]["observation_times"] = [0.0, count * dt]
    spec = parse_spec(raw)
    model = get_model(spec.model)
    _, p = model.initial_values(spec)
    p = type(p)(*(np.asarray(v) for v in p))
    constants = model.device_check_constants(spec)
    record = dict(
        kind="gpu_row_checks", action=action, definition=str(definition), source=source(),
        fingerprint=spec.fingerprint, model=getattr(model, "MODEL_ID", None),
        field_solver=getattr(spec.execution, "field_solver", None),
        backend=spec.execution.backend, dt_s=dt, width=width, recording=recording,
        steps=count, band=row_checks.HOST_DECIDES_ABOVE, ledgers=list(model.DEVICE_CHECKS[1:-1]),
        devices=[str(d) for d in jax.devices()], cpus=sorted(os.sched_getaffinity(0)),
        jax=jax.__version__, environment={k: os.environ.get(k) for k in (
            "JAX_ENABLE_COMPILATION_CACHE", "XLA_FLAGS", "XLA_PYTHON_CLIENT_PREALLOCATE",
            "CUDA_VISIBLE_DEVICES", "JAX_PLATFORMS")},
    )  # fmt: skip
    if action == "twice":
        return _twice(out, record, spec, WindowPolicy(width, recording, "device"))
    modes = ("host", "device") if action == "pair" else ("device",)
    seen, laps = {}, {}
    for mode in modes:
        clock, seen[mode], laps[mode] = Clock(), [], []
        for window in iter_windows(spec, WindowPolicy(width, recording, mode)):
            laps[mode].append(clock.lap())
            seen[mode].append(window)
            if action == "long":  # Only its record is kept: the long run's rows are released.
                laps[mode][-1].update(
                    _device_window(
                        model,
                        spec,
                        p,
                        constants,
                        window,
                        sample=len(seen[mode]) % sample_every == 1,
                    )
                )
                seen[mode][-1] = None
    record["timings"] = {m: dict(per_window=laps[m], after_first=per_step(laps[m], seen[m])
                                 if action == "pair" else None) for m in modes}  # fmt: skip
    if action == "pair":
        record["windows"] = _pair(model, spec, p, constants, seen["host"], seen["device"])
        record["c1_identical"] = all(not w["c1_differs"] for w in record["windows"])
    else:
        device = laps["device"]
        steps_after = (count - width) if len(device) > 1 else 0
        record["timings"]["device"]["after_first"] = dict(
            wall_ms=1e3 * sum(x["wall_s"] for x in device[1:]) / max(steps_after, 1),
            cpu_ms=1e3 * sum(x["cpu_s"] for x in device[1:]) / max(steps_after, 1),
            steps=steps_after,
        )
    outcomes = [w["outcome"] for w in (record.get("windows") or laps["device"])]
    reasons = row_checks.HANDED_BACK
    record["band_summary"] = dict(
        windows=len(outcomes),
        host_decided={r: sum(o["handed_back"] == r for o in outcomes) for r in reasons},
        max_device_ratio={k: max(o["ratios"][k] for o in outcomes) for k in record["ledgers"]},
    )
    # G2 and G4 read every window, those the device handed back included (the lead's ruling).
    everything = [w["c2"] for w in (record.get("windows") or laps["device"]) if w.get("c2")]
    decided = [s for s in everything if s["decided_by"] == "device"]
    record["c2_summary"] = dict(
        windows=len(everything),
        max_spread={
            k: max((s["spread"][k] for s in everything), default=None) for k in record["ledgers"]
        },
        max_spread_device_decided={
            k: max((s["spread"][k] for s in decided), default=None) for k in record["ledgers"]
        },
        criteria_failed=sorted({c[0] for s in everything for c in s["criteria"] if c[3] is False}),
        criteria_undeclared=sorted(
            {c[0] for s in everything for c in s["criteria"] if c[3] is None}
        ),
    )
    temp = [w for w in seen["device"] if w is not None]
    record["memory"] = dict(
        check_temp_bytes=(temp[-1].row_checks.temp_bytes if temp else None),
        device=device_memory(spec), max_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
    )  # fmt: skip
    if action == "long":
        record["memory"]["check_temp_bytes"] = laps["device"][-1].get("check_temp_bytes")
    if states and temp:  # Each device-mode window's final state, for compare only.
        Path(states).mkdir(parents=True, exist_ok=True)
        for k, window in enumerate(temp):
            fields = window.final.state._asdict().items()
            np.savez(
                Path(states) / f"window-{k}.npz", **{f"final.{n}": np.asarray(v) for n, v in fields}
            )
        record["states_saved"] = str(states)
    if state and temp:  # The last device-mode window's final state, for compare only.
        final = temp[-1].final
        np.savez(state, **{f"final.{k}": np.asarray(v) for k, v in final.state._asdict().items()})
        record["state_saved"] = str(state)
    Path(out).write_text(json.dumps(record, indent=1, default=str))
    print(
        json.dumps(
            {
                k: record[k]
                for k in ("action", "backend", "steps", "band_summary", "c2_summary")
                if k in record
            },
            default=str,
        )
    )
    return record


def _twice(out, record, spec, policy):
    """Device mode twice in one process: per window, the arrays that differ between the runs."""
    from cells.execution.windows import iter_windows  # noqa: PLC0415

    runs = [list(iter_windows(spec, policy)) for _ in range(2)]
    record["windows"] = []
    for a, b in zip(*runs, strict=True):
        x, y = dict(arrays(a)), dict(arrays(b))
        record["windows"].append(
            dict(
                steps=len(a.times) - 1,
                differs=sorted(k for k in x if x[k].tobytes() != y[k].tobytes()),
                digests=[digest(a)[0], digest(b)[0]],
            )
        )
    record["identical"] = all(not w["differs"] for w in record["windows"])
    Path(out).write_text(json.dumps(record, indent=1, default=str))
    print(json.dumps(dict(action="twice", identical=record["identical"],
                          differing=[len(w["differs"]) for w in record["windows"]])))  # fmt: skip
    return record


def _outcome(window):
    o = window.row_checks
    return dict(decided_by=o.decided_by, handed_back=o.handed_back, ratios=dict(o.ratios),
                failing=dict(o.failing))  # fmt: skip


def _c2(model, spec, p, constants, window, host_diagnostics):
    host = host_ratios(model, spec, p, constants, window)
    device = dict(window.row_checks.ratios)
    return dict(
        decided_by=window.row_checks.decided_by,
        host_ratios=host,
        spread={k: abs(host[k] - device[k]) for k in host},
        criteria=criteria(spec, host_diagnostics, window.diagnostics),
    )


def _device_window(model, spec, p, constants, window, *, sample):
    """The long run's record of one device-mode window (C2 on every SAMPLE-th)."""
    out = dict(outcome=_outcome(window), digest=digest(window)[0],
               check_temp_bytes=window.row_checks.temp_bytes)  # fmt: skip
    if sample:
        first = window.final.step_index - (len(window.times) - 1)
        from cells.execution.runner import check_steps  # noqa: PLC0415

        host = model.check_values(
            window.history, spec, **check_steps(model, first, len(window.times))
        )
        out["c2"] = _c2(model, spec, p, constants, window, host)
    return out


def _pair(model, spec, p, constants, host, device):
    if len(host) != len(device):
        raise RuntimeError(f"host mode yielded {len(host)} windows, device mode {len(device)}")
    out = []
    for h, d in zip(host, device, strict=True):
        a, b = dict(arrays(h)), dict(arrays(d))
        differs = sorted(
            k for k in a.keys() | b.keys()
            if k not in a or k not in b or a[k].dtype != b[k].dtype or a[k].shape != b[k].shape
            or a[k].tobytes() != b[k].tobytes()
        )  # fmt: skip
        if (h.final.time, h.final.step_index) != (d.final.time, d.final.step_index):
            differs.append("final.time_or_step")
        whole, each = digest(d)
        item = dict(steps=len(d.times) - 1, c1_differs=differs, digest=whole, digests=each,
                    outcome=_outcome(d))  # fmt: skip
        item["c2"] = _c2(model, spec, p, constants, d, h.diagnostics)
        out.append(item)
    return out


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("action", choices=("pair", "long", "twice", "compare"))
    parser.add_argument("out")
    parser.add_argument("definition", help="a definition (pair, long), or state A (compare)")
    parser.add_argument("other", nargs="?", help="state B (compare)")
    parser.add_argument("--state", help="pair: save the last window's final state here")
    parser.add_argument("--states", help="pair: save each window's final state in this folder")
    parser.add_argument("--windows", type=int, default=8)
    parser.add_argument("--steps", type=int, default=20000)
    parser.add_argument("--width", type=int, default=32)
    parser.add_argument(
        "--recording", default="observations", choices=("observations", "checkpoints")
    )
    parser.add_argument("--sample-every", type=int, default=50)
    a = parser.parse_args(argv)
    if a.action == "compare":
        compare(a.out, a.definition, a.other)
        return
    run(a.action, a.out, a.definition, windows=a.windows, steps=a.steps, width=a.width,
        recording=a.recording, sample_every=a.sample_every, state=a.state,
        states=a.states)  # fmt: skip


if __name__ == "__main__":
    sys.exit(main())
