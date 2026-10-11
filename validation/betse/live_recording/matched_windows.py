"""Qualify existing public Cells APIs on the actual seven-cell matched preparation."""

import hashlib
import sys

import live_context as ctx

sys.path.insert(0, str(ctx.HERE.parent / "pump_matched_pilot"))
import pilot_context as prior  # noqa: E402


class Arrays:
    def __init__(self):
        self.count = self.values = 0
        self.digest = hashlib.sha256()

    def match(self, actual, expected, name):
        import numpy as np

        a, b = np.asarray(actual), np.asarray(expected)
        ctx.need(a.dtype == b.dtype and a.shape == b.shape, "Array schema differs: " + name)
        ctx.need(
            a.dtype.kind in "biuf" and np.isfinite(a).all() and np.isfinite(b).all(),
            "Nonfinite/nonnumeric array: " + name,
        )
        raw = a.tobytes(order="C")
        ctx.need(raw == b.tobytes(order="C"), "Array bits differ: " + name)
        self.digest.update(name.encode() + b"\0" + a.dtype.str.encode() + repr(a.shape).encode())
        self.digest.update(hashlib.sha256(raw).digest())
        self.count += 1
        self.values += a.size

    def checkpoint(self, a, b):
        ctx.need(
            (a.time, a.step_index, a.event_index) == (b.time, b.step_index, b.event_index),
            "Checkpoint clock/cursor",
        )
        for group in ("state", "layout"):
            left, right = getattr(a, group), getattr(b, group)
            ctx.need(left._fields == right._fields, "Checkpoint field coverage")
            for name, x, y in zip(left._fields, left, right, strict=True):
                self.match(x, y, group + "/" + name)

    def report(self):
        return dict(
            exact_arrays=self.count,
            exact_values=int(self.values),
            comparison_sha256=self.digest.hexdigest(),
        )


class WindowCheck:
    def __init__(self, full, width, checkpoint=None):
        self.full, self.width, self.arrays = full, width, Arrays()
        self.next_step = 0 if checkpoint is None else checkpoint.step_index
        self.obs = sum(
            float(t) < (0 if checkpoint is None else checkpoint.time)
            for t in full.observations.times
        )
        self.diagnostics, self.windows = {}, 0

    def __call__(self, part):
        from cells.core.windows import merge_diagnostics

        start, end = part.start_step, part.final.step_index
        ctx.need(start == self.next_step and 0 <= end - start <= self.width, "Window step coverage")
        self.arrays.match(part.times, self.full.times[start : end + 1], "accepted_times")
        ctx.need(part.history._fields == self.full.history._fields, "State field coverage")
        for name in part.history._fields:
            self.arrays.match(
                getattr(part.history, name), getattr(self.full.history, name)[start : end + 1], name
            )
        n = len(part.observations.times)
        ctx.need(
            vars(part.observations).keys() == vars(self.full.observations).keys(),
            "Observation fields",
        )
        for name, value in vars(part.observations).items():
            self.arrays.match(
                value,
                getattr(self.full.observations, name)[self.obs : self.obs + n],
                "observed/" + name,
            )
        for value in (*part.history, part.times, *vars(part.observations).values()):
            ctx.need(not value.flags.writeable, "Writable window evidence")
        self.arrays.checkpoint(part.final, self.full.checkpoint_at(part.final.time))
        merge_diagnostics(self.diagnostics, part.diagnostics)
        self.next_step, self.obs, self.windows = end, self.obs + n, self.windows + 1

    def finish(self, result, *, suffix=False):
        ctx.need(
            self.windows > 0
            and self.next_step == self.full.final.step_index
            and self.obs == len(self.full.observations.times),
            "Window coverage incomplete",
        )
        self.arrays.checkpoint(result.final, self.full.final)
        ctx.need(result.diagnostics == self.diagnostics, "Window diagnostic reduction differs")
        if not suffix:
            ctx.need(
                result.diagnostics == self.full.diagnostics, "Full/window diagnostic maxima differ"
            )
        return self.arrays.report() | dict(
            windows=self.windows, diagnostics=self.diagnostics, resources=result.resources
        )


def baseline(full, directory):
    import numpy as np

    arrays = Arrays()
    manifest = ctx.read(directory / "manifest.json")
    ctx.hashes(directory, manifest["files_sha256"])
    with np.load(directory / "trajectory.npz", allow_pickle=False) as saved:
        expected = dict(accepted_times=full.times)
        expected.update(zip(full.history._fields, full.history, strict=True))
        expected.update(
            {
                "cell_ids" if k == "ids" else k: v
                for k, v in zip(full.final.layout._fields, full.final.layout, strict=True)
            }
        )
        expected.update(
            {
                "observation_times" if k == "times" else "observed_" + k: v
                for k, v in vars(full.observations).items()
            }
        )
        ctx.need(set(saved.files) == set(expected), "Prior trajectory field coverage")
        for name, value in expected.items():
            arrays.match(value, saved[name], name)
    return arrays.report()


def disk_check(directory, full, policy):
    import numpy as np

    from cells.io import load_snapshot

    arrays = Arrays()
    manifest = ctx.read(directory / "manifest.json")
    ctx.hashes(directory, manifest["files_sha256"])
    ctx.need(
        manifest["policy"] == policy.to_dict() and manifest["status"] == "complete",
        "Recording policy",
    )
    accepted = observed = validated = 0
    diagnostics, windows, next_step = {}, 0, 0
    from cells.core.windows import merge_diagnostics

    with (directory / "windows.jsonl").open() as handle:
        for line in handle:
            entry = __import__("json").loads(line)
            if entry["kind"] == "checkpoint":
                path = ctx.path_for(directory, entry["path"])
                ctx.need(
                    ctx.sha(path / "manifest.json") == entry["manifest_sha256"]
                    and ctx.sha(path / "state.npz") == entry["state_sha256"],
                    "Snapshot hashes",
                )
                saved = load_snapshot(path).checkpoint
                arrays.checkpoint(saved, full.checkpoint_at(entry["time"]))
                continue
            ctx.need(
                entry["kind"] == "window"
                and entry["index"] == windows
                and entry["start_step"] == next_step,
                "Disk window order",
            )
            windows += 1
            next_step = entry["end_step"]
            merge_diagnostics(diagnostics, entry["diagnostics"])
            n, m = entry["accepted_records"], entry["observation_records"]
            validated += entry["validated_observations"]
            if entry["path"] is None:
                ctx.need(
                    n == m == 0
                    and (
                        policy.recording == "checkpoints"
                        or (
                            policy.recording == "observations"
                            and entry["validated_observations"] == 0
                        )
                    ),
                    "Missing payload",
                )
            else:
                path = ctx.path_for(directory, entry["path"])
                ctx.need(ctx.sha(path) == entry["sha256"], "Chunk hash")
                with np.load(path, allow_pickle=False) as payload:
                    expected = {}
                    if policy.recording == "full":
                        expected["accepted_times"] = full.times[accepted : accepted + n]
                        expected.update(
                            {
                                k: v[accepted : accepted + n]
                                for k, v in zip(full.history._fields, full.history, strict=True)
                            }
                        )
                    if m:
                        expected.update(
                            {
                                "observation_times" if k == "times" else "observed_" + k: v[
                                    observed : observed + m
                                ]
                                for k, v in vars(full.observations).items()
                            }
                        )
                    ctx.need(set(payload.files) == set(expected), "Disk recording field coverage")
                    for name, value in expected.items():
                        arrays.match(payload[name], value, name)
            accepted, observed = accepted + n, observed + m
    ctx.need(
        accepted == (len(full.times) if policy.recording == "full" else 0), "Saved state coverage"
    )
    ctx.need(
        observed == (len(full.observations.times) if policy.recording != "checkpoints" else 0),
        "Saved observations",
    )
    ctx.need(
        validated == len(full.observations.times)
        and next_step == full.final.step_index
        and diagnostics == full.diagnostics,
        "Sparse recording lost checks",
    )
    arrays.checkpoint(load_snapshot(directory / "checkpoint_final").checkpoint, full.final)
    arrays.checkpoint(
        load_snapshot(directory / "checkpoint_initial").checkpoint, full.checkpoint_at(0)
    )
    return arrays.report() | dict(
        validated_observations=validated,
        saved_accepted=accepted,
        saved_observations=observed,
        diagnostics=diagnostics,
    )


def worker(output, registration):
    import jax

    from cells.core.runner import run
    from cells.core.specs import parse_spec
    from cells.core.windows import WindowPolicy, run_windowed
    from cells.io import load_snapshot, write_run
    from cells.window_io import write_windowed_run

    ctx.need(
        jax.default_backend() == "cpu"
        and jax.config.x64_enabled
        and not jax.config.jax_disable_jit,
        "CPU float64/JIT required",
    )
    original = ctx.read(ctx.LEGACY / "registration.json")
    ctx.need(prior.runtime() == original["cells_reference_runtime"], "Cells runtime changed")
    old_records = ctx.read(ctx.LEGACY / "cells.json")["records"]
    records = {}
    for key, previous in sorted(old_records.items()):
        ctx.budget(output, reserve=64 * 1024**2)
        case, step, jit = previous["case"], previous["step_s"], previous["jit"]
        spec = parse_spec(prior.definition(original["cases"][case], step, jit=jit))
        full = run(spec)
        directory = output / "cells" / key
        write_run(directory / "full", full, provenance=dict(protocol="D125", matched_case=case))
        report = dict(
            prior_overlap=baseline(full, ctx.LEGACY / previous["directory"]),
            windows=[],
            recordings=[],
            restarts=[],
        )
        for width, recording in ((1, "full"), (7, "observations"), (64, "checkpoints")):
            check = WindowCheck(full, width)
            result = run_windowed(spec, WindowPolicy(width, recording), sink=check)
            report["windows"].append(dict(width=width, recording=recording, **check.finish(result)))
        if jit and step == 25e-6:
            for recording in ("full", "observations", "checkpoints"):
                policy = WindowPolicy(7, recording)
                target = directory / recording
                write_windowed_run(target, spec, policy, checkpoint_times=(0.0005,))
                report["recordings"].append(
                    dict(recording=recording, **disk_check(target, full, policy))
                )
            loaded = load_snapshot(directory / "checkpoints/snapshots/step-0000000020")
            arrays = Arrays()
            arrays.checkpoint(loaded.checkpoint, full.checkpoint_at(0.0005))
            resumed = run(loaded.spec, loaded.checkpoint)
            write_run(directory / "resumed", resumed)
            for name, value in zip(full.history._fields, full.history, strict=True):
                arrays.match(getattr(resumed.history, name), value[20:], "resumed/" + name)
            arrays.match(resumed.times, full.times[20:], "resumed/times")
            arrays.checkpoint(resumed.final, full.final)
            offset = sum(float(t) < loaded.checkpoint.time for t in full.observations.times)
            for name, value in vars(full.observations).items():
                arrays.match(
                    getattr(resumed.observations, name), value[offset:], "resumed/observed/" + name
                )
            check = WindowCheck(full, 3, loaded.checkpoint)
            result = run_windowed(
                loaded.spec, WindowPolicy(3, "full"), loaded.checkpoint, sink=check
            )
            report["restarts"].append(
                dict(loaded=arrays.report(), windows=check.finish(result, suffix=True))
            )
            ctx.need(result.diagnostics == resumed.diagnostics, "Restart diagnostic maxima")
            zero = WindowCheck(full, 3, full.final)
            zresult = run_windowed(spec, WindowPolicy(3), full.final, sink=zero)
            report["zero_length"] = zero.finish(zresult, suffix=True)
        if case == "pump_leak" and step == 50e-6:
            sparse = parse_spec(
                prior.definition(original["cases"][case], step, jit=jit, times=[0.0, 0.001])
            )
            sfull = run(sparse)
            arrays = Arrays()
            for name in full.history._fields:
                arrays.match(
                    getattr(sfull.history, name), getattr(full.history, name), "sparse/" + name
                )
            ctx.need(sfull.diagnostics == full.diagnostics, "Sparse observations lost diagnostics")
            check = WindowCheck(sfull, 7)
            result = run_windowed(sparse, WindowPolicy(7, "checkpoints"), sink=check)
            report["sparse_observation_schedule"] = dict(
                states=arrays.report(), windows=check.finish(result)
            )
        ctx.write(directory / "comparison.json", report)
        records[key] = dict(
            directory=str(directory.relative_to(output)),
            sha256=ctx.sha(directory / "comparison.json"),
            windows=len(report["windows"]),
            recordings=len(report["recordings"]),
            restarts=len(report["restarts"]),
        )
        ctx.budget(output)
        print("Matched Cells windows exact: " + key, flush=True)
    ctx.need(
        len(records) == 24 and sum(v["restarts"] for v in records.values()) == 6,
        "Cells matrix incomplete",
    )
    ctx.need(
        not any(n == "betse" or n.startswith("betse.") for n in sys.modules), "Cells imported BETSE"
    )
    return dict(
        status="matched_windows_pass_pending_independent_review",
        records=records,
        full_trajectories=24,
        window_runs=72,
        disk_recordings=18,
        restart_suffixes=6,
        restart_window_runs=6,
        zero_length_runs=6,
        sparse_schedule_controls=2,
        runtime=prior.runtime(),
        rss=ctx.rss(),
        production_changed=False,
    )
