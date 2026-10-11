"""D039 lossless window codecs and explicit publication; no production imports."""

import hashlib
import itertools
import json
import math
import os
import zipfile
from contextlib import closing
from pathlib import Path
from time import perf_counter

import numpy as np

from scripts import continue_source_graph_paths as prior
from tests import reference_graph_candidate as candidate

ref = candidate.ref
REVISION = "rk4_window_evidence@1"
POLICIES = ("full_trace", "rk4_basis")
MAX_LINE_BYTES = 65536


def validate_policy(policy):
    if policy not in POLICIES:
        raise ValueError("Unknown explicit evidence policy")


def array_digest(arrays):
    result = hashlib.sha256()
    for name in sorted(arrays):
        value = arrays[name]
        result.update(json.dumps([name, value.dtype.str, value.shape]).encode())
        result.update(value.tobytes())
    return result.hexdigest()


def estimate_array_bytes(width, size, cells):
    return 8 * ((width + 1) * 48 * size + 64 * cells)


def layout(policy, width, size, cells):
    validate_policy(policy)
    if (
        type(width) is not int
        or not 1 <= width <= 256
        or type(cells) is not int
        or cells < 1
        or type(size) is not int
        or size < 13 * cells
        or (size - 13 * cells) % 4
    ):
        raise ValueError("Invalid bounded evidence dimensions")
    result = {
        "times": ((width + 1,), np.dtype(np.float64)),
        "ticks": ((width + 1,), np.dtype(np.int64)),
        "slopes": ((width, 5, size), np.dtype(np.float64)),
        "anchor": ((6, cells), np.dtype(np.float64)),
        "context": ((3, cells), np.dtype(np.float64)),
    }
    if policy == "full_trace":
        result |= {
            "increments": ((width + 1, size), np.dtype(np.float64)),
            "coefficients": ((width, 4, size), np.dtype(np.float64)),
        }
    else:
        result |= {
            name: ((size,), np.dtype(np.float64))
            for name in ("first_increments", "last_increments")
        }
    return result


def validate_arrays(arrays, expected):
    if set(arrays) != set(expected) or any(
        not isinstance(arrays[k], np.ndarray)
        or arrays[k].shape != shape
        or arrays[k].dtype != dtype
        or not np.isfinite(arrays[k]).all()
        for k, (shape, dtype) in expected.items()
    ):
        raise ValueError("Evidence array inventory/shape/precision/values differ")


def preflight(width, size, cells, budget):
    layout("full_trace", width, size, cells)
    if type(budget) is not int or budget <= 0:
        raise ValueError("Invalid evidence array budget")
    if estimate_array_bytes(width, size, cells) > budget:
        raise ref.BudgetExceeded("Evidence encode/decode working array estimate exceeds budget")


def decode_window(policy, arrays, *, width, size, cells, budget):
    preflight(width, size, cells, budget)
    validate_arrays(arrays, layout(policy, width, size, cells))
    if np.any(np.diff(arrays["times"]) <= 0) or np.any(np.diff(arrays["ticks"]) != 1):
        raise ValueError("Evidence window clocks do not advance")
    if policy == "full_trace":
        return {k: value.copy() for k, value in arrays.items()}
    states = np.empty((width + 1, size))
    coefficients = np.empty((width, 4, size))
    states[0] = arrays["first_increments"]
    for i in range(width):
        h = arrays["times"][i + 1] - arrays["times"][i]
        k1, k2, k3, k4, right = arrays["slopes"][i]
        states[i + 1] = states[i] + h * (k1 + 2 * k2 + 2 * k3 + k4) / 6
        change, left, right_scaled = states[i + 1] - states[i], h * k1, h * right
        coefficients[i] = np.stack(
            (
                states[i],
                left,
                3 * change - 2 * left - right_scaled,
                -2 * change + left + right_scaled,
            )
        )
    if states[-1].tobytes() != arrays["last_increments"].tobytes():
        raise ValueError("Reconstructed complete checkpoint differs")
    result = {k: arrays[k] for k in ("times", "ticks", "slopes", "anchor", "context")}
    result |= {"increments": states, "coefficients": coefficients}
    validate_arrays(result, layout("full_trace", width, size, cells))
    return result


def encode_window(policy, data, *, width, size, cells, budget):
    preflight(width, size, cells, budget)
    validate_policy(policy)
    validate_arrays(data, layout("full_trace", width, size, cells))
    encoded = dict(data)
    if policy == "rk4_basis":
        encoded = {k: data[k] for k in ("times", "ticks", "slopes", "anchor", "context")}
        encoded |= {
            "first_increments": data["increments"][0],
            "last_increments": data["increments"][-1],
        }
    decoded = decode_window(policy, encoded, width=width, size=size, cells=cells, budget=budget)
    logical = array_digest(data)
    if array_digest(decoded) != logical:
        raise ValueError("Lossless evidence reconstruction differs; no policy fallback")
    return encoded, logical


def sync_directory(directory):
    descriptor = os.open(directory, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def allocation(path, root, estimate, limit, *, emergency=False):
    path, root = Path(path).absolute(), Path(root).absolute()
    if path.resolve() != path or root.resolve() != root or not path.is_relative_to(root):
        raise ValueError("Evidence path must be unlinked and inside its budget root")
    reserve = 0 if emergency else candidate.paths.TAIL_RESERVE
    if prior.tree_bytes(root) + estimate + reserve > limit:
        raise ref.BudgetExceeded("Evidence artifact budget exceeded before write")


def save_arrays(path, arrays, root, limit, *, emergency=False):
    if any(not isinstance(value, np.ndarray) or value.dtype.hasobject for value in arrays.values()):
        raise ValueError("Evidence writer requires non-object arrays")
    allocation(
        path,
        root,
        sum(v.nbytes for v in arrays.values()) + 4096 * len(arrays),
        limit,
        emergency=emergency,
    )
    with Path(path).open("xb") as handle:
        np.savez_compressed(
            handle, **{k: np.ascontiguousarray(v) if v.ndim else v for k, v in arrays.items()}
        )
        handle.flush()
        os.fsync(handle.fileno())
    sync_directory(Path(path).parent)


def save_json(path, value, root, limit, *, emergency=False):
    payload = (json.dumps(value, sort_keys=True, allow_nan=False, indent=2) + "\n").encode()
    allocation(path, root, len(payload), limit, emergency=emergency)
    with Path(path).open("xb") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())
    sync_directory(Path(path).parent)


def read_arrays(path, expected, *, budget):
    """Bound ZIP members and NPY headers before any advertised array allocation."""
    path = Path(path).absolute()
    if path.resolve() != path or path.stat().st_nlink != 1:
        raise ValueError("Linked evidence payload")
    raw = sum(math.prod(shape) * dtype.itemsize for shape, dtype in expected.values())
    if raw + 16384 * len(expected) > budget:
        raise ref.BudgetExceeded("Encoded evidence array inventory exceeds budget")
    result = {}
    with zipfile.ZipFile(path) as archive:
        if sorted(archive.namelist()) != sorted(k + ".npy" for k in expected):
            raise ValueError("Evidence archive member inventory differs")
        for name, (shape, dtype) in expected.items():
            member = archive.getinfo(name + ".npy")
            count = math.prod(shape) * dtype.itemsize
            if member.file_size > count + 16384:
                raise ValueError("Evidence archive member allocation exceeds layout")
            with archive.open(member) as handle:
                version = np.lib.format.read_magic(handle)
                header = {
                    (1, 0): np.lib.format.read_array_header_1_0,
                    (2, 0): np.lib.format.read_array_header_2_0,
                }.get(version)
                if header is None:
                    raise ValueError("Unsupported evidence NPY header version")
                actual_shape, fortran, actual_dtype = header(handle, max_header_size=10000)
                if actual_shape != shape or fortran or actual_dtype != dtype:
                    raise ValueError("Evidence NPY header differs from bounded layout")
                payload = handle.read(count + 1)
                if len(payload) != count:
                    raise ValueError("Evidence NPY payload length differs")
                result[name] = np.frombuffer(payload, dtype=dtype).reshape(shape).copy()
    return result


def comparison_prefix(folder, count):
    if type(count) is not int or count < 1:
        raise ValueError("Invalid comparison commit count")
    result = hashlib.sha256()
    samples, last = 0, None
    with (Path(folder) / "comparison/chunks.jsonl").open("rb") as handle:
        for i in range(count):
            line = handle.readline(MAX_LINE_BYTES + 1)
            if not line.endswith(b"\n") or len(line) > MAX_LINE_BYTES:
                raise ValueError("Incomplete or oversized comparison commit prefix")
            entry = json.loads(line)
            if (
                entry["path"] != f"chunk-{i:06d}.npz"
                or type(entry["samples"]) is not int
                or not 1 <= entry["samples"] <= 256
            ):
                raise ValueError("Comparison commit prefix inventory differs")
            if ref.sha(Path(folder) / "comparison" / entry["path"]) != entry["sha256"]:
                raise ValueError("Committed comparison payload differs")
            samples += entry["samples"]
            last = entry["end"]
            result.update(line)
    return {"chunks": count, "samples": samples, "index_sha256": result.hexdigest(), "end": last}


def append_commit(path, entry, root, limit):
    payload = (json.dumps(entry, sort_keys=True, allow_nan=False) + "\n").encode()
    if len(payload) > MAX_LINE_BYTES:
        raise ValueError("Evidence commit record exceeds line bound")
    allocation(path, root, len(payload), limit)
    with Path(path).open("ab") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())
    sync_directory(Path(path).parent)


class Recorder(candidate.Recorder):
    """Same numerical buffers, explicit codec and publish-after-comparison boundary."""

    def __init__(self, model, output, resources, root, grid, tick, value, consumer, *, policy):
        validate_policy(policy)
        super().__init__(model, output, resources, root, grid, tick, value, consumer)
        self.policy, self.failed = policy, False
        self.head = ref.sha(self.output / "attempt.json")
        self.committed_tick = tick
        self.encoded_array_bytes = self.encode_seconds = 0
        self.comparison_chunks = 0

    def window(self):
        width = self.buffered
        data = {
            "times": self.times[: width + 1].copy(),
            "ticks": self.ticks[: width + 1].copy(),
            "increments": self.values[: width + 1].copy(),
            "coefficients": self.coefficients[:width].copy(),
            "slopes": self.slopes[:width].copy(),
            "anchor": self.model.anchor,
            "context": self.model.context,
        }
        for value in data.values():
            value.setflags(write=False)
        return data

    def flush(self):
        if not self.buffered:
            return
        if self.failed:
            raise ValueError("Failed window publication cannot be retried")
        begun, data = perf_counter(), self.window()
        try:
            encoded, logical = encode_window(
                self.policy,
                data,
                width=self.buffered,
                size=self.model.coordinates.size,
                cells=self.model.n,
                budget=self.resources["estimated_array_budget_bytes"],
            )
            self.encode_seconds += perf_counter() - begun
            path = self.output / f"chunk-{self.chunks:06d}.npz"
            save_arrays(path, encoded, self.root, self.resources["artifact_budget_bytes"])
            self.recording_seconds += perf_counter() - begun
            compared = None
            if self.consumer is not None:
                phase = perf_counter()
                self.consumer.consume(data)
                maximum = max(
                    v for scores in self.consumer.scores.values() for v in scores.values()
                )
                if (
                    not np.isfinite(maximum)
                    or not np.isfinite(self.consumer.residual)
                    or maximum > 1
                    or self.consumer.residual
                    > self.consumer.selected["numerics"]["accounting_atol"]
                ):
                    raise ValueError("Candidate comparison limits failed before window commit")
                # Synchronize the unchanged comparison recorder's new payloads
                # before binding its index prefix into a committed checkpoint.
                files = itertools.chain(
                    (
                        self.consumer.folder / f"chunk-{i:06d}.npz"
                        for i in range(self.comparison_chunks, self.consumer.chunks)
                    ),
                    [self.consumer.folder / "chunks.jsonl"],
                )
                for file in files:
                    with file.open("rb") as handle:
                        os.fsync(handle.fileno())
                sync_directory(self.consumer.folder)
                compared = comparison_prefix(self.output, self.consumer.chunks)
                if (
                    compared["samples"] != self.consumer.samples
                    or compared["end"] != data["times"][-1]
                ):
                    raise ValueError("Comparison commit does not cover the complete window")
                self.comparison_seconds += perf_counter() - phase
            phase = perf_counter()
            entry = {
                "path": path.name,
                "sha256": ref.sha(path),
                "steps": self.buffered,
                "start": float(data["times"][0]),
                "end": float(data["times"][-1]),
                "start_tick": int(data["ticks"][0]),
                "end_tick": int(data["ticks"][-1]),
                "previous_sha256": self.head,
                "logical_sha256": logical,
                "logical_array_bytes": sum(v.nbytes for v in data.values()),
                "encoded_array_bytes": sum(v.nbytes for v in encoded.values()),
                "comparison": compared,
            }
            entry["commit_sha256"] = candidate.digest(entry)
            append_commit(
                self.output / "chunks.jsonl",
                entry,
                self.root,
                self.resources["artifact_budget_bytes"],
            )
            self.head, self.committed_tick = entry["commit_sha256"], entry["end_tick"]
            self.times[0], self.ticks[0], self.values[0] = (
                data["times"][-1],
                data["ticks"][-1],
                data["increments"][-1],
            )
            self.raw_array_bytes += entry["logical_array_bytes"]
            self.encoded_array_bytes += entry["encoded_array_bytes"]
            self.buffered = 0
            self.chunks += 1
            self.comparison_chunks = 0 if compared is None else compared["chunks"]
            self.recording_seconds += perf_counter() - phase
        except BaseException:
            self.failed = True
            raise

    def summary(self):
        return {
            "revision": REVISION,
            "policy": self.policy,
            "committed_chunks": self.chunks,
            "committed_tick": self.committed_tick,
            "head_sha256": self.head,
            "logical_array_bytes": self.raw_array_bytes,
            "encoded_array_bytes": self.encoded_array_bytes,
            "encode_and_verify_seconds": self.encode_seconds,
            "comparison_evidence_reduced": False,
            "RHS_replay": False,
        }


def checkpoint_layout(size, cells):
    return {
        "tick": ((), np.dtype(np.int64)),
        "time": ((), np.dtype(np.float64)),
        "increments": ((size,), np.dtype(np.float64)),
        "anchor": ((6, cells), np.dtype(np.float64)),
        "context": ((3, cells), np.dtype(np.float64)),
    }


def closed_attempt(directory):
    directory = Path(directory).absolute()
    prior.tree_bytes(directory)
    names = [name for name in ("trajectory.json", "failure.json") if (directory / name).exists()]
    if len(names) != 1:
        raise ValueError("Evidence restart/reader requires exactly one closed attempt")
    attempt, closure = (
        ref.read_json(directory / "attempt.json"),
        ref.read_json(directory / names[0]),
    )
    recording = attempt["recording"]
    if recording != {"revision": REVISION, "policy": recording.get("policy")}:
        raise ValueError("Unknown recording schema; no implicit checkpoint migration")
    validate_policy(recording["policy"])
    if attempt["contract_sha256"] != candidate.digest(attempt["contract"]):
        raise ValueError("Evidence numerical contract digest differs")
    if closure["attempt_sha256"] != ref.sha(directory / "attempt.json"):
        raise ValueError("Evidence attempt closure identity differs")
    count = closure["chunks"] if names[0] == "trajectory.json" else closure["committed_chunks"]
    if type(count) is not int or count < 0:
        raise ValueError("Invalid closed evidence prefix count")
    for file, key in (("initial.npz", "initial_sha256"), ("chunks.jsonl", "index_sha256")):
        actual = ref.sha(directory / file) if (directory / file).exists() else None
        if actual != closure[key] or (count and actual is None):
            raise ValueError("Evidence initial/index closure differs")
    return directory, attempt, closure, names[0], count


def chunks(directory, *, decoder=None):
    """Bounded closed-prefix reader. The auditor supplies its own numerical decoder."""
    directory, attempt, closure, _, count = closed_attempt(directory)
    decoder = decode_window if decoder is None else decoder
    if not count:
        if (directory / "chunks.jsonl").exists() and (directory / "chunks.jsonl").stat().st_size:
            raise ValueError("Uncommitted index tail cannot be promoted")
        return
    contract, resources = attempt["contract"], attempt["resources"]
    cells, edges = len(contract["case"]["cell_ids"]), len(contract["case"]["edges"])
    size, policy = 13 * cells + 4 * edges, attempt["recording"]["policy"]
    preflight(resources["window_steps"], size, cells, resources["estimated_array_budget_bytes"])
    grid = candidate.Grid(contract["step"], contract["end"])
    initial = read_arrays(
        directory / "initial.npz",
        checkpoint_layout(size, cells),
        budget=resources["estimated_array_budget_bytes"],
    )
    validate_arrays(initial, checkpoint_layout(size, cells))
    np.testing.assert_array_equal(initial["anchor"], contract["case"]["primary"])
    np.testing.assert_array_equal(initial["context"], contract["case"]["context"])
    tick, value = int(initial["tick"]), initial["increments"]
    if tick != attempt["start_tick"] or initial["time"] != grid.time(tick):
        raise ValueError("Initial committed clock differs")
    logical_bytes = encoded_bytes = 0
    head, seen, previous_samples, previous_comparisons = (
        ref.sha(directory / "attempt.json"),
        0,
        0,
        0,
    )
    with (directory / "chunks.jsonl").open("rb") as handle:
        while line := handle.readline(MAX_LINE_BYTES + 1):
            if seen >= count or len(line) > MAX_LINE_BYTES or not line.endswith(b"\n"):
                raise ValueError("Uncommitted, incomplete or oversized index tail")
            entry = json.loads(line)
            fields = {
                "path",
                "sha256",
                "steps",
                "start",
                "end",
                "start_tick",
                "end_tick",
                "previous_sha256",
                "logical_sha256",
                "logical_array_bytes",
                "encoded_array_bytes",
                "comparison",
                "commit_sha256",
            }
            if (
                set(entry) != fields
                or entry["previous_sha256"] != head
                or entry["commit_sha256"]
                != candidate.digest({k: v for k, v in entry.items() if k != "commit_sha256"})
            ):
                raise ValueError("Evidence commit hash chain differs")
            width = entry["steps"]
            if (
                type(width) is not int
                or not 1 <= width <= resources["window_steps"]
                or entry["path"] != f"chunk-{seen:06d}.npz"
                or tick + width > grid.count
            ):
                raise ValueError("Evidence committed window inventory differs")
            path = directory / entry["path"]
            if ref.sha(path) != entry["sha256"]:
                raise ValueError("Evidence committed payload hash differs")
            encoded = read_arrays(
                path,
                layout(policy, width, size, cells),
                budget=resources["estimated_array_budget_bytes"],
            )
            data = decoder(
                policy,
                encoded,
                width=width,
                size=size,
                cells=cells,
                budget=resources["estimated_array_budget_bytes"],
            )
            validate_arrays(data, layout("full_trace", width, size, cells))
            if (
                array_digest(data) != entry["logical_sha256"]
                or sum(a.nbytes for a in encoded.values()) != entry["encoded_array_bytes"]
                or sum(a.nbytes for a in data.values()) != entry["logical_array_bytes"]
            ):
                raise ValueError("Decoded evidence identity/size differs")
            if data["increments"][0].tobytes() != value.tobytes():
                raise ValueError("Committed complete state carry differs")
            np.testing.assert_array_equal(
                data["ticks"], np.arange(tick, tick + width + 1, dtype=np.int64)
            )
            np.testing.assert_array_equal(
                data["times"], [grid.time(i) for i in range(tick, tick + width + 1)]
            )
            np.testing.assert_array_equal(data["anchor"], contract["case"]["primary"])
            np.testing.assert_array_equal(data["context"], contract["case"]["context"])
            if (entry["start_tick"], entry["end_tick"], entry["start"], entry["end"]) != (
                tick,
                tick + width,
                grid.time(tick),
                grid.time(tick + width),
            ):
                raise ValueError("Committed index clock differs")
            compared = entry["comparison"]
            if compared is not None:
                if (
                    compared != comparison_prefix(directory, compared["chunks"])
                    or compared["end"] != entry["end"]
                    or compared["samples"] <= previous_samples
                    or compared["chunks"] <= previous_comparisons
                ):
                    raise ValueError("Committed comparison prefix differs")
                previous_samples, previous_comparisons = compared["samples"], compared["chunks"]
            elif previous_comparisons or closure.get("comparison") is not None:
                raise ValueError("Missing committed comparison prefix")
            tick, value, head = tick + width, data["increments"][-1].copy(), entry["commit_sha256"]
            logical_bytes += entry["logical_array_bytes"]
            encoded_bytes += entry["encoded_array_bytes"]
            seen += 1
            yield entry, data
    if (
        seen != count
        or closure["evidence"]["head_sha256"] != head
        or closure["evidence"]["committed_tick"] != tick
    ):
        raise ValueError("Closed committed prefix is truncated or inconsistent")
    summary = closure["evidence"]
    if (
        summary["revision"] != REVISION
        or summary["policy"] != policy
        or summary["committed_chunks"] != count
        or summary["logical_array_bytes"] != logical_bytes
        or summary["encoded_array_bytes"] != encoded_bytes
        or summary["comparison_evidence_reduced"]
        or summary["RHS_replay"]
        or not np.isfinite(summary["encode_and_verify_seconds"])
        or summary["encode_and_verify_seconds"] < 0
    ):
        raise ValueError("Evidence encoding totals/policy differ")


def load_checkpoint(directory, chunk, expected_contract, *, decoder=None):
    directory, attempt, _, closure_name, count = closed_attempt(directory)
    if attempt["contract"] != expected_contract or attempt["contract_sha256"] != candidate.digest(
        expected_contract
    ):
        raise ValueError("Checkpoint numerical/source/runtime identity differs")
    if type(chunk) is not int or not 0 <= chunk < count:
        raise ValueError("Checkpoint is not a committed accepted boundary")
    selected = None
    # Exhaust the index, including its closure/tail checks, while retaining only
    # the requested complete state. Never promote an uncommitted dump.
    with closing(chunks(directory, decoder=decoder)) as stream:
        for i, (entry, data) in enumerate(stream):
            if i == chunk:
                selected = {
                    "parent_directory": str(directory),
                    "parent_chunk": chunk,
                    "parent_attempt_sha256": ref.sha(directory / "attempt.json"),
                    "parent_chunk_sha256": entry["sha256"],
                    "parent_commit_sha256": entry["commit_sha256"],
                    "parent_closure": closure_name,
                    "parent_closure_sha256": ref.sha(directory / closure_name),
                    "contract_sha256": candidate.digest(expected_contract),
                    "tick": entry["end_tick"],
                    "time": entry["end"],
                    "increments": data["increments"][-1].tolist(),
                }
    if selected is None:
        raise ValueError("Checkpoint committed prefix is incomplete")
    return selected
