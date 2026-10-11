"""D040 lossless comparison representations; frozen numerical stepping is reused."""

import json
from contextlib import ExitStack, closing
from pathlib import Path
from time import perf_counter

import numpy as np

from tests import reference_graph_diagnostics as diagnostics
from tests import reference_graph_evidence as evidence
from tests import reference_recorded_candidate as runner

original, ref, prep = diagnostics.original, diagnostics.ref, diagnostics.prep
fingerprint = diagnostics.fingerprint
REVISION = "reference_backed_comparison@1"
POLICIES = ("full_samples", "trajectory_backed")
MAX_MANIFEST_BYTES = 1_048_576
SOURCE_FILES = (
    "tests/reference_comparison_evidence.py",
    "tests/reference_candidate_comparison.py",
    "tests/reference_graph_candidate.py",
    "tests/reference_graph_diagnostics.py",
    "tests/reference_graph_evidence.py",
    "tests/reference_graph_comparison.py",
    "tests/reference_source_graph_numerics.py",
)


def validate_policy(policy):
    if policy not in POLICIES:
        raise ValueError("Unknown explicit comparison storage policy")


def layout(policy, samples, size, variants):
    validate_policy(policy)
    if (
        type(samples) is not int
        or not 1 <= samples <= 256
        or type(size) is not int
        or size < 13
        or len(variants) != 3
        or len(set(variants)) != 3
        or any(type(k) is not str or not k.isidentifier() for k in variants)
        or set(variants) & {"times", "observer", "candidate"}
    ):
        raise ValueError("Invalid bounded comparison dimensions or variants")
    result = {
        "times": ((samples,), np.dtype(np.float64)),
        "observer": ((samples,), np.dtype(np.bool_)),
    }
    if policy == "full_samples":
        result |= {k: ((samples, size), np.dtype(np.float64)) for k in ["candidate", *variants]}
    return result


def estimate_array_bytes(width, size, cells):
    """Aggregate estimate: D039 buffers, cached readouts and extra decoding readers."""
    return 8 * ((width + 1) * (256 * size + 512 * cells) + 9 * 257 * (8 * size + 20) + 256 * size)


def preflight(width, size, cells, budget):
    evidence.layout("rk4_basis", width, size, cells)
    if type(budget) is not int or budget <= 0:
        raise ValueError("Invalid comparison working array budget")
    if estimate_array_bytes(width, size, cells) > budget:
        raise ref.BudgetExceeded(
            "Aggregate comparison reconstruction array estimate exceeds budget"
        )


def decode_samples(policy, arrays, *, size, variants, reconstruct, budget):
    if (
        "times" not in arrays
        or not isinstance(arrays["times"], np.ndarray)
        or arrays["times"].ndim != 1
    ):
        raise ValueError("Comparison sample clocks missing")
    samples = len(arrays["times"])
    expected = layout(policy, samples, size, variants)
    if type(budget) is not int or budget <= 0 or 8 * samples * (16 * size + 32) > budget:
        raise ref.BudgetExceeded("Comparison decoded array estimate exceeds budget")
    evidence.validate_arrays(arrays, expected)
    if np.any(np.diff(arrays["times"]) <= 0):
        raise ValueError("Comparison sample clocks must advance")
    result = {k: v.copy() for k, v in arrays.items()}
    if policy == "trajectory_backed":
        states = reconstruct(arrays["times"])
        if set(states) != {"candidate", *variants}:
            raise ValueError("Reconstructed comparison input inventory differs")
        result.update(states)
    evidence.validate_arrays(result, layout("full_samples", samples, size, variants))
    return result


def encode_samples(policy, arrays, *, size, variants, reconstruct, budget):
    validate_policy(policy)
    if (
        "times" not in arrays
        or not isinstance(arrays["times"], np.ndarray)
        or arrays["times"].ndim != 1
    ):
        raise ValueError("Comparison sample clocks missing")
    evidence.validate_arrays(arrays, layout("full_samples", len(arrays["times"]), size, variants))
    encoded = arrays if policy == "full_samples" else {k: arrays[k] for k in ("times", "observer")}
    decoded = decode_samples(
        policy, encoded, size=size, variants=variants, reconstruct=reconstruct, budget=budget
    )
    logical = evidence.array_digest(arrays)
    if evidence.array_digest(decoded) != logical:
        raise ValueError("Lossless comparison reconstruction differs; no fallback")
    return encoded, logical


def unlinked(path):
    path = Path(path).absolute()
    if path.resolve() != path or path.stat().st_nlink != 1:
        raise ValueError("Comparison dependency must be an unlinked local file")
    return path


def bounded_json(path):
    path = unlinked(path)
    if path.stat().st_size > MAX_MANIFEST_BYTES:
        raise ValueError("Comparison dependency manifest exceeds bound")
    return ref.read_json(path)


def source_identity():
    root = Path(__file__).resolve().parents[1]
    return {name: ref.sha(root / name) for name in SOURCE_FILES}


def reference_pin(directory):
    directory = Path(directory).absolute()
    if directory.resolve() != directory or not directory.is_dir():
        raise ValueError("Linked or missing reference dependency directory")
    names = ("case.json", "trajectory.json", "chunks.jsonl")
    hashes = {name: ref.sha(unlinked(directory / name)) for name in names}
    report = bounded_json(directory / "trajectory.json")
    count = 0
    with (directory / "chunks.jsonl").open("rb") as handle:
        while line := handle.readline(evidence.MAX_LINE_BYTES + 1):
            if len(line) > evidence.MAX_LINE_BYTES or not line.endswith(b"\n"):
                raise ValueError("Reference dependency index line differs")
            entry = json.loads(line)
            if entry["path"] != f"chunk-{count:06d}.npz":
                raise ValueError("Reference dependency payload inventory differs")
            if ref.sha(unlinked(directory / entry["path"])) != entry["sha256"]:
                raise ValueError("Reference dependency payload hash differs")
            count += 1
    if count != report["chunks"] or count < 1:
        raise ValueError("Reference dependency chunk count differs")
    return {"directory": str(directory), "hashes": hashes, "chunks": count}


def dependencies(folder, directories, selected, policy):
    validate_policy(policy)
    folder = Path(folder).absolute()
    attempt = bounded_json(folder / "attempt.json")
    if (
        set(directories) != set(selected["methods"])
        or len(directories) != 3
        or attempt["contract"]["case"] != selected["case"]
        or attempt["contract"]["numerics"] != selected["numerics"]
    ):
        raise ValueError("Comparison dependency selected case/numerics/method inventory differs")
    return {
        "revision": REVISION,
        "policy": policy,
        "candidate_attempt_sha256": ref.sha(folder / "attempt.json"),
        "candidate_contract_sha256": attempt["contract_sha256"],
        "selected": selected,
        "references": {k: reference_pin(d) for k, d in directories.items()},
        "source_hashes": source_identity(),
        "runtime": prep.runtime(),
        "RHS_replay": False,
        "logical_evidence_reduced": False,
    }


def check_dependencies(folder, *, directories=None, selected=None):
    folder = Path(folder).absolute()
    manifest = bounded_json(folder / "comparison/dependencies.json")
    actual_dirs = {k: Path(v["directory"]) for k, v in manifest["references"].items()}
    if directories is not None and actual_dirs != {
        k: Path(v).absolute() for k, v in directories.items()
    }:
        raise ValueError("Comparison dependency directories differ from expected inputs")
    if selected is not None and manifest["selected"] != selected:
        raise ValueError("Comparison dependency selection differs from expected inputs")
    if manifest != dependencies(folder, actual_dirs, manifest["selected"], manifest["policy"]):
        raise ValueError("Comparison dependency identity/runtime/source differs")
    return manifest, actual_dirs


def window_identity(index, data, path):
    return {
        "path": f"chunk-{index:06d}.npz",
        "sha256": ref.sha(unlinked(path)),
        "logical_sha256": evidence.array_digest(data),
        "steps": len(data["times"]) - 1,
        "start_tick": int(data["ticks"][0]),
        "end_tick": int(data["ticks"][-1]),
    }


class Comparison(diagnostics.Comparison):
    """Explicit storage policy; inherited numerical/readout equations stay frozen."""

    def __init__(self, *args, storage_policy, **kwargs):
        validate_policy(storage_policy)
        super().__init__(*args, **kwargs)
        self.storage_policy = storage_policy
        self.window_count = self.encoded_array_bytes = 0
        self.codec_seconds = self.dependency_seconds = 0.0

    def open(self, start_tick, grid, guard):
        cells, edges = len(self.selected["case"]["cell_ids"]), len(self.selected["case"]["edges"])
        size = 13 * cells + 4 * edges
        width, budget = (
            self.resources["window_steps"],
            self.resources["estimated_array_budget_bytes"],
        )
        preflight(width, size, cells, budget)
        self.estimated_array_bytes = estimate_array_bytes(width, size, cells)
        super().open(start_tick, grid, guard)
        begun = perf_counter()
        manifest = dependencies(
            self.folder.parent, self.directories, self.selected, self.storage_policy
        )
        if len(json.dumps(manifest).encode()) * 2 > MAX_MANIFEST_BYTES:
            raise ValueError("Comparison dependency manifest exceeds bound")
        evidence.save_json(
            self.folder / "dependencies.json",
            manifest,
            self.root,
            self.resources["artifact_budget_bytes"],
        )
        self.dependency_sha256 = ref.sha(self.folder / "dependencies.json")
        self.decoding_readers = (
            self.stack.enter_context(original.open_readers(self.directories, self.selected))
            if self.storage_policy == "trajectory_backed"
            else None
        )
        self.dependency_seconds = perf_counter() - begun

    def begin_window(self, data):
        path = self.folder.parent / f"chunk-{self.window_count:06d}.npz"
        self.window_binding = window_identity(self.window_count, data, path)
        self.decoding_window = None
        if self.storage_policy == "trajectory_backed":
            begun = perf_counter()
            attempt = bounded_json(self.folder.parent / "attempt.json")
            policy, width = attempt["recording"]["policy"], len(data["times"]) - 1
            size, cells = self.model.coordinates.size, self.model.n
            budget = self.resources["estimated_array_budget_bytes"]
            loaded = evidence.read_arrays(
                path, evidence.layout(policy, width, size, cells), budget=budget
            )
            self.decoding_window = evidence.decode_window(
                policy, loaded, width=width, size=size, cells=cells, budget=budget
            )
            if evidence.array_digest(self.decoding_window) != self.window_binding["logical_sha256"]:
                raise ValueError("Persisted candidate dependency differs from live window")
            self.codec_seconds += perf_counter() - begun

    def reconstruct(self, times):
        return {
            "candidate": original.candidate.sample_window(self.decoding_window, times),
            **{key: reader.sample(times) for key, reader in self.decoding_readers.items()},
        }

    def record(self, arrays, readout_hashes):
        begun = perf_counter()
        encoded, logical = encode_samples(
            self.storage_policy,
            arrays,
            size=self.model.coordinates.size,
            variants=list(self.directories),
            reconstruct=self.reconstruct,
            budget=self.resources["estimated_array_budget_bytes"],
        )
        self.codec_seconds += perf_counter() - begun
        path = self.folder / f"chunk-{self.chunks:06d}.npz"
        evidence.save_arrays(path, encoded, self.root, self.resources["artifact_budget_bytes"])
        entry = {
            "path": path.name,
            "sha256": ref.sha(path),
            "samples": len(arrays["times"]),
            "start": float(arrays["times"][0]),
            "end": float(arrays["times"][-1]),
            "readout_hashes": readout_hashes,
            "revision": REVISION,
            "policy": self.storage_policy,
            "dependency_sha256": self.dependency_sha256,
            "candidate_window": self.window_binding,
            "logical_sha256": logical,
            "input_hashes": {
                key: evidence.array_digest({key: arrays[key]})
                for key in ["candidate", *self.directories]
            },
            "logical_array_bytes": sum(v.nbytes for v in arrays.values()),
            "encoded_array_bytes": sum(v.nbytes for v in encoded.values()),
        }
        evidence.append_commit(
            self.folder / "chunks.jsonl", entry, self.root, self.resources["artifact_budget_bytes"]
        )
        self.encoded_array_bytes += entry["encoded_array_bytes"]

    def consume(self, data):
        # Keep the frozen source's grid, scoring and recording operation order.
        # The only numerical substitution is this instance's readout evaluator.
        self.begin_window(data)
        width = self.resources["window_steps"]
        while self.next_time is not None and self.next_time <= data["times"][-1]:
            self.guard()
            batch = []
            while (
                self.next_time is not None
                and self.next_time <= data["times"][-1]
                and len(batch) < width
            ):
                batch.append(self.next_time)
                self.next_time = next(self.times, None)
            times = np.asarray(batch, dtype=np.float64)
            states = {"candidate": original.candidate.sample_window(data, times)}
            states.update({key: reader.sample(times) for key, reader in self.readers.items()})
            begun = perf_counter()
            readouts = {
                key: self.cached.observed(value)
                if self.cached is not None
                else prep.observed(self.model, value)
                for key, value in states.items()
            }
            self.readout_seconds += perf_counter() - begun
            self.readout_batches += len(states)
            for value in states.values():
                self.residual = max(
                    self.residual, float(np.max(abs(ref.residual(self.model, value))))
                )
                if np.any(value[:, ref.blocked_coordinates(self.model)] != 0):
                    raise ValueError("Blocked comparison history changed")
            for key in self.readers:
                scores = prep.comparison_scores(
                    self.model,
                    states["candidate"],
                    states[key],
                    readouts["candidate"],
                    readouts[key],
                    self.selected["numerics"]["targets"],
                )
                for quantity, score in scores.items():
                    if not np.isfinite(score):
                        raise ValueError("Nonfinite candidate comparison score")
                    self.scores[key][quantity] = max(self.scores[key].get(quantity, 0), score)
            begun = perf_counter()
            readout_hashes = {key: fingerprint(value) for key, value in readouts.items()}
            self.fingerprint_seconds += perf_counter() - begun
            phase = perf_counter()
            flags = np.isin(times, self.observers)
            arrays = {"times": times, "observer": flags, **states}
            self.record(arrays, readout_hashes)
            self.samples += len(times)
            self.chunks += 1
            self.observer_samples += int(flags.sum())
            self.raw_array_bytes += sum(value.nbytes for value in arrays.values())
            self.last = float(times[-1])
            self.recording_seconds += perf_counter() - phase

        self.window_count += 1
        self.decoding_window = None

    def finish(self):
        result = super().finish()
        evidence.save_json(
            self.folder / "storage.json",
            {
                "revision": REVISION,
                "policy": self.storage_policy,
                "dependency_sha256": self.dependency_sha256,
                "index_sha256": ref.sha(self.folder / "chunks.jsonl"),
                "samples": self.samples,
                "chunks": self.chunks,
                "logical_array_bytes": self.raw_array_bytes,
                "encoded_array_bytes": self.encoded_array_bytes,
                "codec_seconds": self.codec_seconds,
                "dependency_validation_seconds": self.dependency_seconds,
                "aggregate_array_estimate_bytes": self.estimated_array_bytes,
                "RHS_replay": False,
                "logical_evidence_reduced": False,
            },
            self.root,
            self.resources["artifact_budget_bytes"],
        )
        return result


def reconstruct_states(data, times, readers):
    return {
        "candidate": original.candidate.sample_window(data, times),
        **{key: reader.sample(times) for key, reader in readers.items()},
    }


def chunks(
    directory, *, directories=None, selected=None, decoder=None, window_decoder=None, sampler=None
):
    """Decode only closed committed comparison prefixes; never integrate/replay RHS."""
    directory, attempt, closure, closure_name, _ = evidence.closed_attempt(directory)
    manifest, dirs = check_dependencies(directory, directories=directories, selected=selected)
    policy, variants = manifest["policy"], list(dirs)
    decode = decode_samples if decoder is None else decoder
    reconstruct = reconstruct_states if sampler is None else sampler
    cells, edges = (
        len(attempt["contract"]["case"]["cell_ids"]),
        len(attempt["contract"]["case"]["edges"]),
    )
    size, resources = 13 * cells + 4 * edges, attempt["resources"]
    budget = resources["estimated_array_budget_bytes"]
    preflight(resources["window_steps"], size, cells, budget)
    manifest_hash = ref.sha(directory / "comparison/dependencies.json")
    count = samples = logical_bytes = encoded_bytes = 0
    last = None
    fields = {
        "path",
        "sha256",
        "samples",
        "start",
        "end",
        "readout_hashes",
        "revision",
        "policy",
        "dependency_sha256",
        "candidate_window",
        "logical_sha256",
        "input_hashes",
        "logical_array_bytes",
        "encoded_array_bytes",
    }
    with ExitStack() as stack:
        readers = stack.enter_context(original.open_readers(dirs, manifest["selected"]))
        windows = stack.enter_context(closing(evidence.chunks(directory, decoder=window_decoder)))
        handle = stack.enter_context(unlinked(directory / "comparison/chunks.jsonl").open("rb"))
        for window_index, (committed, data) in enumerate(windows):
            binding = window_identity(window_index, data, directory / committed["path"])
            if committed["comparison"] is None:
                raise ValueError("Comparison evidence requires committed comparison prefixes")
            while count < committed["comparison"]["chunks"]:
                line = handle.readline(evidence.MAX_LINE_BYTES + 1)
                if len(line) > evidence.MAX_LINE_BYTES or not line.endswith(b"\n"):
                    raise ValueError("Missing, oversized or incomplete comparison record")
                entry = json.loads(line)
                if (
                    set(entry) != fields
                    or entry["path"] != f"chunk-{count:06d}.npz"
                    or entry["revision"] != REVISION
                    or entry["policy"] != policy
                    or entry["dependency_sha256"] != manifest_hash
                    or entry["candidate_window"] != binding
                    or type(entry["samples"]) is not int
                    or not 1 <= entry["samples"] <= resources["window_steps"]
                    or set(entry["readout_hashes"]) != {"candidate", *variants}
                ):
                    raise ValueError("Comparison record identity/dependency/window differs")
                path = unlinked(directory / "comparison" / entry["path"])
                if ref.sha(path) != entry["sha256"]:
                    raise ValueError("Comparison payload hash differs")
                encoded = evidence.read_arrays(
                    path, layout(policy, entry["samples"], size, variants), budget=budget
                )
                logical = decode(
                    policy,
                    encoded,
                    size=size,
                    variants=variants,
                    reconstruct=lambda times, window=data: reconstruct(window, times, readers),
                    budget=budget,
                )
                evidence.validate_arrays(
                    logical, layout("full_samples", entry["samples"], size, variants)
                )
                times = logical["times"]
                if (
                    not data["times"][0] <= times[0] <= times[-1] <= data["times"][-1]
                    or np.any(np.diff(times) <= 0)
                    or (last is not None and times[0] <= last)
                    or (entry["start"], entry["end"]) != (times[0], times[-1])
                    or evidence.array_digest(logical) != entry["logical_sha256"]
                    or entry["input_hashes"]
                    != {k: evidence.array_digest({k: logical[k]}) for k in ["candidate", *variants]}
                    or entry["logical_array_bytes"] != sum(v.nbytes for v in logical.values())
                    or entry["encoded_array_bytes"] != sum(v.nbytes for v in encoded.values())
                ):
                    raise ValueError("Comparison reconstruction clocks/digests/bytes differ")
                count += 1
                samples += len(times)
                logical_bytes += entry["logical_array_bytes"]
                encoded_bytes += entry["encoded_array_bytes"]
                last = float(times[-1])
                yield entry, logical
            if samples != committed["comparison"]["samples"] or last != committed["end"]:
                raise ValueError("Decoded comparison prefix does not cover committed window")
        if closure_name == "trajectory.json":
            if handle.read(1):
                raise ValueError("Unaccounted successful comparison index tail")
            storage = bounded_json(directory / "comparison/storage.json")
            fixed = {
                "revision": REVISION,
                "policy": policy,
                "dependency_sha256": manifest_hash,
                "index_sha256": ref.sha(directory / "comparison/chunks.jsonl"),
                "samples": samples,
                "chunks": count,
                "logical_array_bytes": logical_bytes,
                "encoded_array_bytes": encoded_bytes,
                "aggregate_array_estimate_bytes": estimate_array_bytes(
                    resources["window_steps"], size, cells
                ),
                "RHS_replay": False,
                "logical_evidence_reduced": False,
            }
            if (
                set(storage) != set(fixed) | {"codec_seconds", "dependency_validation_seconds"}
                or any(storage[k] != v for k, v in fixed.items())
                or any(
                    not np.isfinite(storage[k]) or storage[k] < 0
                    for k in ("codec_seconds", "dependency_validation_seconds")
                )
                or closure["comparison"]["samples"] != samples
                or closure["comparison"]["chunks"] != count
            ):
                raise ValueError("Comparison storage closure differs")


def load_checkpoint(directory, chunk, expected):
    """D040 restart API: complete D039 carry AND eligible reconstruction dependencies."""
    carry = evidence.load_checkpoint(directory, chunk, expected)
    with closing(chunks(directory)) as stream:
        for _ in stream:
            pass
    return carry


def integrate(model, output, *, comparison, **kwargs):
    """Scoped adapter; do not alter the frozen runner or infer comparison policy."""
    if not isinstance(comparison, Comparison):
        raise ValueError("D040 requires an explicit comparison recorder")
    if (
        comparison.resources != kwargs["resources"]
        or comparison.folder.absolute().parent != Path(output).absolute()
        or comparison.root.absolute() != Path(kwargs["artifact_root"]).absolute()
        or comparison.selected["case"] != model.case
        or comparison.selected["numerics"] != kwargs["numerics"]
    ):
        raise ValueError("Comparison adapter case/numerics/resources/output differ from runner")
    if kwargs.get("initial") is not None:
        initial = kwargs["initial"]
        expected = runner.contract(
            model,
            runner.Grid(kwargs["step"], kwargs["end"]),
            kwargs["numerics"],
            kwargs["identity"],
        )
        if initial != load_checkpoint(
            initial["parent_directory"], initial["parent_chunk"], expected
        ):
            raise ValueError("Dependency-aware restart carry differs")
    return runner.integrate(model, output, comparison=comparison, **kwargs)
