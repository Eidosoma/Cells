"""Independent stdlib array-byte checks and expected rolling-receipt replay.

Persisted arrays are compared directly. Unsaved window/sparse/zero-length
results are checked through their sealed comparison receipts, NOT decoded as
if their trajectories had been saved. No physics or numerical solver is run.
"""

import hashlib
import math
import struct

import audit_context as c

STATE = (
    "amount_increment",
    "leak_transferred",
    "pump_cycles",
    "dissipated_energy_pJ",
    "gate",
    "channel_transferred",
    "junction_gate",
    "junction_transferred",
    "junction_dissipated_energy_pJ",
    "extracellular_amount_increment",
)
DIGEST_FIELDS = {"exact_arrays", "exact_values", "comparison_sha256"}
RESOURCE_FIELDS = {
    "estimated_working_bytes",
    "executed_steps",
    "max_observations_per_window",
    "peak_host_history_bytes",
    "peak_host_observation_bytes",
    "resident_off_nominal_events",
    "validated_observations",
    "windows",
}
DIAGNOSTICS = {
    "max_balance_error_fmol",
    "max_charge_balance_error_V",
    "max_countercharge_error_C",
    "max_energy_balance_error_pJ",
    "max_extracellular_balance_error_fmol",
    "max_global_balance_error_fmol",
}


def same(a, b, label):
    c.exact.Exact().match(a, b, label)


def raw(a):
    values = list(c.arrays.flatten(a["values"]))
    c.need(len(values) == math.prod(a["shape"]), "Array shape/value extent")
    dtype = a["dtype"]
    c.need(dtype in ("<f8", "<i8", "|b1"), "Array dtype")
    kind = {"<f8": float, "<i8": int, "|b1": bool}[dtype]
    c.need(all(type(v) is kind and math.isfinite(v) for v in values), "Array finite type")
    return struct.pack(
        "<" + str(len(values)) + {"<f8": "d", "<i8": "q", "|b1": "B"}[dtype], *values
    )


def cut(a, start, stop):
    c.need(a["shape"] and 0 <= start <= stop <= a["shape"][0], "Array slice extent")
    return dict(
        dtype=a["dtype"], shape=[stop - start, *a["shape"][1:]], values=a["values"][start:stop]
    )


def row(a, index):
    c.need(a["shape"] and 0 <= index < a["shape"][0], "Array row extent")
    return dict(dtype=a["dtype"], shape=a["shape"][1:], values=a["values"][index])


class Bytes:
    def __init__(self):
        self.arrays = self.values = 0
        self.digest = hashlib.sha256()

    def add(self, a, name, expected=None):
        data = raw(a)
        if expected is not None:
            c.need(
                a["dtype"] == expected["dtype"]
                and a["shape"] == expected["shape"]
                and data == raw(expected),
                "Saved array bits/schema: " + name,
            )
        self.digest.update(
            name.encode() + b"\0" + a["dtype"].encode() + repr(tuple(a["shape"])).encode()
        )
        self.digest.update(hashlib.sha256(data).digest())
        self.arrays += 1
        self.values += math.prod(a["shape"])

    def report(self):
        return dict(
            exact_arrays=self.arrays,
            exact_values=self.values,
            comparison_sha256=self.digest.hexdigest(),
        )

    def receipt(self, saved):
        same({k: saved[k] for k in DIGEST_FIELDS}, self.report(), "Reconstructed array receipt")


class Baseline:
    def __init__(self, directory):
        self.directory = directory
        self.data = c.arrays.decode_npz(directory / "trajectory.npz")
        self.spec = c.read(directory / "resolved_config.json", None)
        self.manifest = c.read(directory / "manifest.json", None)
        self.summary = c.read(directory / "summary.json", None)
        self.times = self.data["accepted_times"]["values"]
        self.obs = tuple(
            k for k in self.data if k == "observation_times" or k.startswith("observed_")
        )
        self.layout = tuple(k for k in self.data if k not in {"accepted_times", *STATE, *self.obs})
        c.need(
            list(self.data) == ["accepted_times", *STATE, *self.layout, *self.obs]
            and len(self.layout) == 54
            and len(self.obs) == 53,
            "Accepted array contract",
        )
        c.need(
            self.times[0] == 0.0
            and self.times[-1] == 0.001
            and all(a < b for a, b in zip(self.times, self.times[1:], strict=False)),
            "Accepted clock",
        )
        self.n = len(self.times) - 1
        self.diagnostics = {k: self.summary[k] for k in DIAGNOSTICS}
        c.need(self.n in (20, 40, 80), "Matched step extent")

    def checkpoint_arrays(self, step):
        return {
            **{k: row(self.data[k], step) for k in STATE},
            **{("ids" if k == "cell_ids" else k): self.data[k] for k in self.layout},
        }

    def cp_digest(self, digest, step):
        for k, a in self.checkpoint_arrays(step).items():
            digest.add(a, ("state/" if k in STATE else "layout/") + k)

    def observation_arrays(self, sparse=False):
        if not sparse:
            return {k: self.data[k] for k in self.obs}
        return {
            k: dict(
                dtype=self.data[k]["dtype"],
                shape=[2, *self.data[k]["shape"][1:]],
                values=[self.data[k]["values"][0], self.data[k]["values"][-1]],
            )
            for k in self.obs
        }


def obs_name(name):
    return "times" if name == "observation_times" else name.removeprefix("observed_")


def checkpoint(directory, base, step, direct):
    m = c.read(directory / "manifest.json", None)
    c.need(set(c.inventory(directory)[0]) == {"manifest.json", "state.npz"}, "Checkpoint files")
    c.need(
        m["kind"] == "cells_complete_numerical_checkpoint"
        and m["schema_version"] == 1
        and m["random_state"] is None,
        "Checkpoint schema/random state",
    )
    same(
        m["clock"],
        dict(time=base.times[step], step_index=step, event_index=0),
        "Checkpoint clock/cursor",
    )
    same(m["spec"], base.spec, "Checkpoint definition")
    c.need(
        m["spec_sha256"] == c.arrays.digest(base.spec)
        and m["state_sha256"] == c.sha(directory / "state.npz")
        and m["manifest_sha256"]
        == c.arrays.digest({k: v for k, v in m.items() if k != "manifest_sha256"}),
        "Checkpoint digests",
    )
    for key in ("runtime", "source_hashes"):
        same(m[key], base.manifest[key], "Checkpoint " + key)
    data, expected = c.arrays.decode_npz(directory / "state.npz"), base.checkpoint_arrays(step)
    c.need(data.keys() == expected.keys(), "Checkpoint fields")
    for name, a in expected.items():
        direct.add(data[name], "checkpoint/" + name, a)


def metadata(directory, base, *, windowed=False):
    m = c.read(directory / "manifest.json", None)
    c.hashes(directory, m["files_sha256"])
    same(c.read(directory / "resolved_config.json", None), base.spec, "Saved definition")
    for key in (
        "schema_version",
        "definition_sha256",
        "runtime",
        "source_hashes",
        "device",
        "observer",
        "numerics",
        "status",
    ):
        same(m[key], base.manifest[key], "Run metadata/" + key)
    c.need(m["definition_sha256"] == c.arrays.digest(base.spec), "Run definition checksum")
    fixed = {
        "resolved_config.json",
        "summary.json",
        "checkpoint_final/manifest.json",
        "checkpoint_final/state.npz",
    }
    fixed |= (
        {"windows.jsonl", "checkpoint_initial/manifest.json", "checkpoint_initial/state.npz"}
        if windowed
        else {"trajectory.npz"}
    )
    c.need(set(m["files_sha256"]) == fixed, "Manifest fixed coverage")
    if not windowed:
        c.need(set(c.inventory(directory)[0]) == fixed | {"manifest.json"}, "Run file coverage")
    return m


def diag_subset(values, maxima):
    c.need(
        set(values) == DIAGNOSTICS
        and all(
            type(v) is float and math.isfinite(v) and 0 <= v <= maxima[k] for k, v in values.items()
        ),
        "Diagnostic bound/schema",
    )


def ordinary(directory, base, direct, start=0):
    metadata(directory, base)
    data = c.arrays.decode_npz(directory / "trajectory.npz")
    c.need(data.keys() == base.data.keys(), "Run array coverage")
    offset = sum(t < base.times[start] for t in base.data["observation_times"]["values"])
    for name, original in base.data.items():
        expected = (
            cut(original, start, base.n + 1)
            if name in ("accepted_times", *STATE)
            else cut(original, offset, original["shape"][0])
            if name in base.obs
            else original
        )
        direct.add(data[name], name, expected)
    checkpoint(directory / "checkpoint_final", base, base.n, direct)
    summary = c.read(directory / "summary.json", None)
    expected = base.summary | dict(start_time=base.times[start], executed_steps=base.n - start)
    c.need(summary.keys() == expected.keys(), "Summary fields")
    diag_subset({k: summary[k] for k in DIAGNOSTICS}, base.diagnostics)
    for k in summary:
        if start == 0 or k not in DIAGNOSTICS:
            same(summary[k], expected[k], "Run summary/" + k)
    return {k: summary[k] for k in DIAGNOSTICS}


def windows(base, width, start=0, sparse=False):
    observations = base.observation_arrays(sparse)
    times = observations["observation_times"]["values"]
    cursor = sum(t < base.times[start] for t in times)
    begin = start
    while True:
        end = min(begin + width, base.n)
        stop = sum(t <= base.times[end] for t in times)
        yield begin, end, cursor, stop, observations
        if end == base.n:
            break
        begin, cursor = end, stop


def expected_windows(base, width, start=0, sparse=False):
    digest, history_bytes, observation_bytes, max_obs, count = Bytes(), 0, 0, 0, 0
    observed = 0
    for begin, end, lo, hi, obs in windows(base, width, start, sparse):
        history = {k: cut(base.data[k], begin, end + 1) for k in ("accepted_times", *STATE)}
        selected = {k: cut(a, lo, hi) for k, a in obs.items()}
        for name, a in history.items():
            digest.add(a, name)
        for name, a in selected.items():
            digest.add(a, "observed/" + obs_name(name))
        base.cp_digest(digest, end)
        history_bytes = max(history_bytes, sum(len(raw(a)) for a in history.values()))
        observation_bytes = max(observation_bytes, sum(len(raw(a)) for a in selected.values()))
        observed += hi - lo
        max_obs = max(max_obs, hi - lo)
        count += 1
    base.cp_digest(digest, base.n)
    return digest, dict(
        executed_steps=base.n - start,
        windows=count,
        validated_observations=observed,
        max_observations_per_window=max_obs,
        peak_host_history_bytes=history_bytes,
        peak_host_observation_bytes=observation_bytes,
        resident_off_nominal_events=0,
    )


def window_receipt(saved, base, width, *, start=0, sparse=False, diagnostics=None):
    digest, resources = expected_windows(base, width, start, sparse)
    digest.receipt(saved)
    same(saved["windows"], resources["windows"], "Window count")
    c.need(set(saved["resources"]) == RESOURCE_FIELDS, "Window resource fields")
    for name, value in resources.items():
        same(saved["resources"][name], value, "Array extent resource/" + name)
    # Reservation is a producer estimate, not independent measured peak process memory.
    estimate = saved["resources"]["estimated_working_bytes"]
    c.need(
        type(estimate) is int and 0 < estimate <= base.spec["execution"]["max_trace_bytes"],
        "Working reservation bounds",
    )
    diag_subset(saved["diagnostics"], base.diagnostics)
    if diagnostics is not None:
        same(saved["diagnostics"], diagnostics, "Window diagnostic reduction")
    return digest.report()


def recording(directory, base, policy, saved, direct):
    m = metadata(directory, base, windowed=True)
    same(m["policy"], dict(window_steps=7, recording=policy), "Disk policy")
    c.need(m["kind"] == "cells_windowed_run" and m["index"] == "windows.jsonl", "Disk manifest")
    same(c.read(directory / "summary.json", None), base.summary, "Disk summary")
    entries = [
        c.wire.json_value(line) for line in (directory / "windows.jsonl").read_text().splitlines()
    ]
    planned = list(windows(base, 7))
    c.need(len(entries) == len(planned) + 1, "Disk index coverage")
    digest, members = Bytes(), set(m["files_sha256"]) | {"manifest.json"}
    maxima, accepted, observed, index, snaps, chunk_bytes = {}, 0, 0, 0, 0, 0
    for entry in entries:
        if entry["kind"] == "checkpoint":
            c.wire.fields(
                entry,
                {"kind", "step_index", "time", "path", "manifest_sha256", "state_sha256"},
                "Index snapshot",
            )
            c.need(
                snaps == 0 and index == 3 and entry["path"] == "snapshots/step-0000000020",
                "Requested snapshot coverage/order",
            )
            same(
                {k: entry[k] for k in ("step_index", "time")},
                dict(step_index=20, time=0.0005),
                "Snapshot index clock",
            )
            target = c.child(directory, entry["path"])
            c.hashes(
                target,
                {"manifest.json": entry["manifest_sha256"], "state.npz": entry["state_sha256"]},
            )
            checkpoint(target, base, 20, direct)
            base.cp_digest(digest, 20)
            members.update(entry["path"] + "/" + k for k in ("manifest.json", "state.npz"))
            snaps += 1
            continue
        c.wire.fields(
            entry,
            {
                "kind",
                "index",
                "start_step",
                "end_step",
                "start_time",
                "end_time",
                "accepted_records",
                "observation_records",
                "validated_observations",
                "diagnostics",
                "path",
                "sha256",
            },
            "Window index",
        )
        c.need(index < len(planned), "Extra disk window")
        begin, end, lo, hi, obs = planned[index]
        n = (end - begin + int(index == 0)) if policy == "full" else 0
        count = hi - lo if policy != "checkpoints" else 0
        same(
            {
                k: entry[k]
                for k in (
                    "kind",
                    "index",
                    "start_step",
                    "end_step",
                    "start_time",
                    "end_time",
                    "accepted_records",
                    "observation_records",
                    "validated_observations",
                )
            },
            dict(
                kind="window",
                index=index,
                start_step=begin,
                end_step=end,
                start_time=base.times[begin],
                end_time=base.times[end],
                accepted_records=n,
                observation_records=count,
                validated_observations=hi - lo,
            ),
            "Window index clock/coverage",
        )
        diag_subset(entry["diagnostics"], base.diagnostics)
        for k, v in entry["diagnostics"].items():
            maxima[k] = max(maxima.get(k, 0.0), v)
        expected = {}
        if n:
            expected.update(
                {k: cut(base.data[k], accepted, accepted + n) for k in ("accepted_times", *STATE)}
            )
        if count:
            expected.update({k: cut(a, lo, hi) for k, a in obs.items()})
        if expected:
            path = f"chunks/window-{index:08d}.npz"
            c.need(entry["path"] == path, "Canonical chunk ownership")
            target = c.child(directory, path)
            c.need(c.sha(target) == entry["sha256"], "Chunk index digest")
            payload = c.arrays.decode_npz(target)
            c.need(payload.keys() == expected.keys(), "Chunk field coverage")
            for name, a in expected.items():
                direct.add(payload[name], "chunk/" + name, a)
                digest.add(payload[name], name, a)
            members.add(path)
            chunk_bytes += target.stat().st_size
        else:
            c.need(
                entry["path"] is None and entry["sha256"] is None, "Spurious empty-policy payload"
            )
        accepted, observed, index = accepted + n, observed + count, index + 1
    c.need(snaps == 1 and index == len(planned), "Incomplete disk traversal")
    same(maxima, base.diagnostics, "Disk diagnostic maxima")
    for name, step in (("checkpoint_final", base.n), ("checkpoint_initial", 0)):
        checkpoint(directory / name, base, step, direct)
        base.cp_digest(digest, step)
    c.need(set(c.inventory(directory)[0]) == members, "Unindexed recording payload")
    digest.receipt(saved)
    same(
        {
            k: saved[k]
            for k in (
                "recording",
                "validated_observations",
                "saved_accepted",
                "saved_observations",
                "diagnostics",
            )
        },
        dict(
            recording=policy,
            validated_observations=5,
            saved_accepted=accepted,
            saved_observations=observed,
            diagnostics=maxima,
        ),
        "Disk receipt",
    )
    _, resources = expected_windows(base, 7)
    expected_resources = resources | dict(
        saved_accepted_records=accepted,
        saved_observation_records=observed,
        requested_snapshots=1,
        chunk_payload_bytes=chunk_bytes,
    )
    c.need(
        set(m["resources"]) == set(expected_resources) | {"estimated_working_bytes"},
        "Disk resource fields",
    )
    for k, v in expected_resources.items():
        same(m["resources"][k], v, "Disk resources/" + k)
    c.need(
        0 < m["resources"]["estimated_working_bytes"] <= base.spec["execution"]["max_trace_bytes"],
        "Disk reservation bound",
    )
    return digest.report()


def inspect(directory, accepted):
    base, direct = Baseline(accepted), Bytes()
    report = c.read(directory / "comparison.json", None)
    checkpoint_case = base.n == 40 and base.spec["execution"]["jit"]
    sparse_case = directory.parts[-3] == "pump_leak" and base.n == 20
    fields = {
        "prior_overlap",
        "windows",
        "recordings",
        "restarts",
        "output_layout_version",
        "output_paths",
        "baseline_files_sha256",
    }
    fields |= {"zero_length"} if checkpoint_case else set()
    fields |= {"sparse_observation_schedule"} if sparse_case else set()
    c.need(set(report) == fields, "Case report coverage")
    same(report["output_paths"], c.LAYOUT, "Output roles")
    c.need(report["output_layout_version"] == c.LAYOUT_VERSION, "Output layout version")
    baseline = directory / "baseline"
    c.need(
        c.inventory(baseline)[0] == report["baseline_files_sha256"], "Preserved baseline inventory"
    )
    ordinary(baseline, base, direct)
    digest = Bytes()
    for name, a in base.data.items():
        digest.add(a, name)
    digest.receipt(report["prior_overlap"])
    c.need(len(report["windows"]) == 3, "Window policy coverage")
    replayed = []
    for saved, (width, policy) in zip(
        report["windows"], ((1, "full"), (7, "observations"), (64, "checkpoints")), strict=True
    ):
        c.need(
            set(saved)
            == DIGEST_FIELDS | {"width", "recording", "windows", "diagnostics", "resources"}
            and saved["width"] == width
            and saved["recording"] == policy,
            "Window report contract",
        )
        replayed.append(window_receipt(saved, base, width, diagnostics=base.diagnostics))
    c.need(
        len(report["recordings"]) == (3 if checkpoint_case else 0)
        and len(report["restarts"]) == int(checkpoint_case),
        "Recording/restart coverage",
    )
    disk = []
    if checkpoint_case:
        for policy, saved in zip(
            ("full", "observations", "checkpoints"), report["recordings"], strict=True
        ):
            disk.append(recording(directory / "recordings" / policy, base, policy, saved, direct))
        resumed_diag = ordinary(directory / "resumed", base, direct, 20)
        restart = Bytes()
        base.cp_digest(restart, 20)
        for name in STATE:
            restart.add(cut(base.data[name], 20, base.n + 1), "resumed/" + name)
        restart.add(cut(base.data["accepted_times"], 20, base.n + 1), "resumed/times")
        base.cp_digest(restart, base.n)
        for name, a in base.observation_arrays().items():
            restart.add(cut(a, 2, 5), "resumed/observed/" + obs_name(name))
        restart.receipt(report["restarts"][0]["loaded"])
        replayed.append(
            window_receipt(
                report["restarts"][0]["windows"], base, 3, start=20, diagnostics=resumed_diag
            )
        )
        replayed.append(window_receipt(report["zero_length"], base, 3, start=base.n))
    if sparse_case:
        sparse = report["sparse_observation_schedule"]
        digest = Bytes()
        for name in STATE:
            digest.add(base.data[name], "sparse/" + name)
        digest.receipt(sparse["states"])
        replayed.append(digest.report())
        replayed.append(
            window_receipt(sparse["windows"], base, 7, sparse=True, diagnostics=base.diagnostics)
        )
    expected_dirs = {"baseline"} | ({"recordings", "resumed"} if checkpoint_case else set())
    c.need(
        {p.name for p in directory.iterdir()} == expected_dirs | {"comparison.json"},
        "Case output membership",
    )
    return dict(
        status="saved_arrays_exact_and_expected_receipts_match",
        direct_arrays=direct.arrays,
        direct_values=direct.values,
        direct_comparison_sha256=direct.digest.hexdigest(),
        baseline_trajectories=1,
        window_receipts=3,
        disk_recordings=len(disk),
        saved_restart_suffixes=int(checkpoint_case),
        restart_window_receipts=int(checkpoint_case),
        zero_length_receipts=int(checkpoint_case),
        sparse_schedule_receipts=int(sparse_case),
        replayed_receipts=replayed,
        disk_checks=disk,
        unsaved_trajectories_directly_inspected=False,
        physics_recomputed=False,
        working_reservation_independently_measured=False,
    )
