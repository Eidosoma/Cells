"""Online, bounded comparison of RK4 windows to explicit immutable reference trios."""

import heapq
import itertools
import json
from contextlib import ExitStack
from pathlib import Path
from time import perf_counter

import numpy as np

from scripts import qualify_source_preparations as prep
from tests import reference_graph_candidate as candidate
from tests.reference_graph_comparison import open_readers

ref, paths = candidate.ref, candidate.paths


class Comparison:
    def __init__(self, directories, selected, output, root, resources, observation_times):
        self.directories, self.selected = directories, selected
        self.folder, self.root = Path(output) / "comparison", Path(root)
        self.resources = resources
        self.observers = np.asarray(observation_times, dtype=np.float64)
        self.stack = ExitStack()
        self.samples = self.chunks = self.observer_samples = self.raw_array_bytes = 0
        self.scores = {key: {} for key in directories}
        self.residual = self.recording_seconds = 0.0
        self.last = None

    def open(self, start_tick, grid, guard):
        if (
            len(self.directories) != 3
            or set(self.directories) != set(self.selected["methods"])
            or "candidate" in self.directories
            or self.observers.ndim != 1
            or not np.isfinite(self.observers).all()
            or np.any(np.diff(self.observers) <= 0)
        ):
            raise ValueError("Invalid candidate comparison inventory/observers")
        self.grid, self.start, self.guard = grid, grid.time(start_tick), guard
        if self.start < 0 or grid.end > self.selected["duration"]:
            raise ValueError("Candidate comparison exceeds registered reference horizon")
        self.observers = self.observers[
            (self.observers >= self.start) & (self.observers <= grid.end)
        ]
        self.folder.mkdir(exist_ok=False)
        self.readers = self.stack.enter_context(open_readers(self.directories, self.selected))
        self.model = next(iter(self.readers.values())).model
        streams = [r.grid() for r in self.readers.values()]
        for stream in streams:
            self.stack.callback(stream.close)
        streams += [grid.points(start_tick), iter(self.observers)]
        merged = (key for key, _ in itertools.groupby(heapq.merge(*streams)))
        self.times = itertools.takewhile(
            lambda t: t <= grid.end, itertools.dropwhile(lambda t: t < self.start, merged)
        )
        self.next_time = next(self.times, None)

    def consume(self, data):
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
            states = {"candidate": candidate.sample_window(data, times)}
            states.update({key: reader.sample(times) for key, reader in self.readers.items()})
            readouts = {key: prep.observed(self.model, value) for key, value in states.items()}
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
            phase = perf_counter()
            flags = np.isin(times, self.observers)
            arrays = {"times": times, "observer": flags, **states}
            path = self.folder / f"chunk-{self.chunks:06d}.npz"
            paths.save_arrays(path, arrays, self.root, self.resources["artifact_budget_bytes"])
            with (self.folder / "chunks.jsonl").open("a") as handle:
                handle.write(
                    json.dumps(
                        {
                            "path": path.name,
                            "sha256": ref.sha(path),
                            "samples": len(times),
                            "start": float(times[0]),
                            "end": float(times[-1]),
                        },
                        sort_keys=True,
                        allow_nan=False,
                    )
                    + "\n"
                )
            self.samples += len(times)
            self.chunks += 1
            self.observer_samples += int(flags.sum())
            self.raw_array_bytes += sum(a.nbytes for a in arrays.values())
            self.last = float(times[-1])
            self.recording_seconds += perf_counter() - phase

    def finish(self):
        self.guard()
        if (
            self.next_time is not None
            or self.last != self.grid.end
            or self.observer_samples != len(self.observers)
        ):
            raise ValueError("Incomplete candidate comparison grid")
        maximum = max(score for scores in self.scores.values() for score in scores.values())
        result = {
            "status": "pass"
            if maximum <= 1 and self.residual <= self.selected["numerics"]["accounting_atol"]
            else "disagreement",
            "scope": "short_prefix_only_not_long_candidate_qualification",
            "scores": self.scores,
            "maximum_score": maximum,
            "maximum_accounting_residual": self.residual,
            "start": self.start,
            "end": self.grid.end,
            "samples": self.samples,
            "chunks": self.chunks,
            "observer_samples": self.observer_samples,
            "derived_readout_evaluations": self.samples * (1 + len(self.readers)),
            "raw_array_bytes": self.raw_array_bytes,
            "recording_seconds": self.recording_seconds,
            "index_sha256": ref.sha(self.folder / "chunks.jsonl"),
        }
        ref.write_json(self.folder / "comparison.json", result)
        return result

    def close(self):
        self.stack.close()


def chunks(directory, *, comparison=False):
    """Bounded hash-checked payload traversal; scientific algebra is a separate audit."""
    folder = Path(directory) / "comparison" if comparison else Path(directory)
    with (folder / "chunks.jsonl").open() as handle:
        for index, line in enumerate(handle):
            entry = json.loads(line)
            path = folder / entry["path"]
            if (
                entry["path"] != f"chunk-{index:06d}.npz"
                or path.resolve() != path.absolute()
                or ref.sha(path) != entry["sha256"]
            ):
                raise ValueError("Candidate evidence chunk identity differs")
            with np.load(path, allow_pickle=False) as data:
                yield entry, {key: data[key].copy() for key in data.files}
