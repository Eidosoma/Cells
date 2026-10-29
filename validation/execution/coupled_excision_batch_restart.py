"""Qualify batch recovery from saved compiled cut cases, without checkpoint migration.

Run each family with its original frozen Cells runtime. The two worlds repeat
one physical case; they test execution and persistence, not biological breadth.
Preparation loads and checks artifacts but never integrates an ODE. Baseline
and restart must be separate processes under the established resource runner.
"""

import hashlib
import importlib
import json
import os
import sys
from pathlib import Path

import numpy as np

from cells.batch_io import load_batch_snapshot, write_batch_snapshot
from cells.core.batch import BatchSpec, WorldSpec
from cells.core.batch_windows import iter_batch_windows, plan_batch_windows
from cells.core.grid import EventGrid
from cells.core.windows import WindowPolicy
from cells.excision_io import load_excision
from cells.io import load_snapshot, runtime_identity, source_hashes, write_run
from tests.unit.test_surface_kinetic import assert_states, exact

WORLD_IDS = (3, 79)
FAMILIES = {"transport": 42, "mitochondria": 45, "water": 43}
SCOPE = "Two execution copies of one saved physical case per family; no new biological cases."


def read(path):
    return json.loads(Path(path).read_text())


def sha(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x") as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write("\n")


def process_identity():
    fields = Path("/proc/self/stat").read_text().rsplit(")", 1)[1].split()
    return {"pid": os.getpid(), "start_ticks": int(fields[19])}


class Qualification:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.config = read(self.root / "case.json")
        self.family = self.config["family"]
        self.field_count = FAMILIES[self.family]
        self.midpoint = self.config["midpoint"]
        self.width = self.midpoint["largest_divisor_le128"]
        self.policy = WindowPolicy(self.width)
        self.original = importlib.import_module(
            f"tests.unit.test_surface_calcium_energy_{self.family}_excision"
        )
        self.reference = importlib.import_module(
            f"validation.tissue.calcium_energy_{self.family}_excision_reference"
        )

    def identity(self):
        expected = self.config["source_runtime_identity"]
        actual = {"runtime": runtime_identity("cpu"), "source_hashes": source_hashes()}
        assert actual == expected, "Use the original frozen runtime; migration is forbidden"
        for name in ("XLA_FLAGS", "JAX_DISABLE_JIT"):
            assert name not in os.environ, f"The saved checkpoint requires {name} unset"
        return actual

    def load_inputs(self):
        self.identity()
        for item in self.config["input_receipts"]:
            assert sha(item["path"]) == item["sha256"], item["path"]
        for relative, expected in self.config["source_sha256"].items():
            path = Path(relative)
            assert not path.is_absolute() and ".." not in path.parts
            assert sha(self.root / "source" / path) == expected, relative
        # Source hashes alone do not establish which oracle Python imported.
        # Refuse mixed live/frozen test or reference modules even when a caller
        # invokes the check outside the prescribed prepared runner.
        source = self.root / "source"
        for name, module in tuple(sys.modules.items()):
            if not name.startswith(("tests.", "validation.")):
                continue
            location = getattr(module, "__file__", None)
            if location is not None:
                relative = Path(location).resolve().relative_to(source)
                assert str(relative) in self.config["source_sha256"], name
        prefix = Path(self.config["prefix_root"])
        scalar = Path(self.config["scalar_root"])
        before = self.original._load_compiled_phase(prefix)
        after = self.original._load_compiled_phase(scalar)
        assert after["prefix_metadata_sha256"] == sha(prefix / "metadata.json")
        self.cut = load_excision(prefix / "cut")
        self.scalar_final = load_snapshot(scalar / "run" / "checkpoint_final")
        spec, point = self.cut.spec, self.cut.checkpoint
        assert before["after"] == spec.to_dict() == self.scalar_final.spec.to_dict()
        assert spec.to_dict()["model"]["id"] == self.config["model_id"]
        assert spec.execution.backend == "cpu" and spec.execution.jit
        assert len(point.state) == self.field_count
        assert point.time == 50e-6 < self.midpoint["time_s"] < spec.experiment.end_time
        assert spec.experiment.end_time == self.scalar_final.checkpoint.time
        self.context = self.reference.bind(spec.to_dict())
        assert set(self.context["shapes"]) == set(point.state._fields)
        self.batch = BatchSpec(tuple(WorldSpec(i, spec) for i in WORLD_IDS), 2, 20000, 2**30)
        self.checkpoints = {i: point for i in WORLD_IDS}
        grid = EventGrid(spec)
        index = grid.exact_index(self.midpoint["time_s"])
        assert index == self.midpoint["global_step_index"]
        offset = index - point.step_index
        assert offset == self.midpoint["accepted_index_offset_from_cut"]
        assert offset == self.width * self.midpoint["rounds_to_checkpoint"]
        assert len(grid) - 1 - index == self.midpoint["remaining_accepted_steps"] > 0
        with np.load(scalar / "run" / "trajectory.npz", allow_pickle=False) as trace:
            expected_times = np.array([grid[i] for i in range(point.step_index, len(grid))])
            np.testing.assert_array_equal(trace["accepted_times"], expected_times)
            assert trace["accepted_times"][offset] == self.midpoint["time_s"]
            assert (
                trace["observation_times"][self.midpoint["observation_index"]]
                == (self.midpoint["time_s"])
            )
            for name, initial in point.state._asdict().items():
                np.testing.assert_array_equal(initial, trace[name][0])
                np.testing.assert_array_equal(
                    getattr(self.scalar_final.checkpoint.state, name), trace[name][-1]
                )
            actual = self.reference.flatten(
                self.context, {k: trace[f"observed_{k}"] for k in point.state._fields}
            )
        with np.load(scalar / "comparison.npz", allow_pickle=False) as comparison:
            np.testing.assert_array_equal(actual, comparison["actual"])
            assert_states(self.context, actual, comparison["reference"])
        # Admission validates the full event schedule, stage domains and memory
        # estimates; it does not advance the numerical state or compile a rollout.
        plan = plan_batch_windows(self.batch, self.policy, self.checkpoints)
        assert plan.fixed_kernel_width == self.width
        return plan

    def folder(self, phase):
        return self.root / phase / "evidence"

    def begin(self, phase):
        folder = self.folder(phase)
        folder.mkdir(parents=True, exist_ok=False)
        return folder

    def finish(self, phase, record):
        folder = self.folder(phase)
        write(
            folder / "metadata.json",
            dict(
                record,
                status="passed",
                phase=phase,
                scope=SCOPE,
                process=process_identity(),
                case_sha256=sha(self.root / "case.json"),
                source_runtime_identity=self.identity(),
                files_sha256={
                    str(p.relative_to(folder)): sha(p)
                    for p in sorted(folder.rglob("*"))
                    if p.is_file()
                },
            ),
        )

    def artifact(self, phase):
        folder = self.folder(phase)
        record = self.original._load_compiled_phase(folder)
        assert record["phase"] == phase
        assert record["source_runtime_identity"] == self.identity()
        assert record["case_sha256"] == sha(self.root / "case.json")
        return record

    def admission(self):
        plan = self.load_inputs()
        folder = self.begin("admission")
        loaded = load_batch_snapshot(
            write_batch_snapshot(folder / "saved_cut_batch", self.batch, self.checkpoints)
        )
        assert loaded.spec == self.batch and set(loaded.checkpoints) == set(WORLD_IDS)
        for point in loaded.checkpoints.values():
            assert (point.time, point.step_index) == (
                self.cut.checkpoint.time,
                self.cut.checkpoint.step_index,
            )
            exact(point.state, self.cut.checkpoint.state)
            exact(point.layout, self.cut.checkpoint.layout)
        self.finish(
            "admission",
            dict(
                integration_performed=False,
                compiled_qualification=False,
                fields=self.field_count,
                midpoint=self.midpoint,
                window_steps=self.width,
                estimated_working_bytes=plan.estimated_working_bytes,
                saved_cut_batch_roundtrip_exact=True,
            ),
        )

    def integrate(self, phase, spec, checkpoints, *, save_midpoint):
        records = {i: [] for i in WORLD_IDS}
        captured = False
        folder = self.folder(phase)
        with (folder / "rounds.jsonl").open("x") as log:
            for window in iter_batch_windows(spec, self.policy, checkpoints):
                assert set(window.worlds) == set(window.checkpoints) == set(WORLD_IDS)
                for world_id, result in window.worlds.items():
                    records[world_id].append(result)
                log.write(
                    json.dumps(
                        dict(
                            round=window.index,
                            times={str(i): p.time for i, p in window.checkpoints.items()},
                            timings=window.timings,
                            resources=window.resources,
                        ),
                        allow_nan=False,
                    )
                    + "\n"
                )
                log.flush()
                if save_midpoint and not captured:
                    times = [p.time for p in window.checkpoints.values()]
                    assert all(t <= self.midpoint["time_s"] for t in times)
                    if all(t == self.midpoint["time_s"] for t in times):
                        write_batch_snapshot(folder / "midpoint", spec, window.checkpoints)
                        captured = True
        assert not save_midpoint or captured
        results = {i: self.original.merge_windows(rows) for i, rows in records.items()}
        for world_id, result in results.items():
            # Save all accepted, observed, final-state and layout arrays before
            # any correspondence assertion, preserving useful failed evidence.
            write_run(folder / f"world-{world_id}", result)
        write_batch_snapshot(
            folder / "checkpoint_final", spec, {i: r.final for i, r in results.items()}
        )
        return results

    def correspondence(self, phase, world_id, result):
        scalar = Path(self.config["scalar_root"])
        assert result.final.time == self.scalar_final.checkpoint.time
        assert result.final.step_index == self.scalar_final.checkpoint.step_index
        assert len(result.history) == self.field_count and len(result.times) > 1
        exact(result.final.layout, self.scalar_final.checkpoint.layout)
        with np.load(scalar / "run" / "trajectory.npz", allow_pickle=False) as target:
            indices = np.flatnonzero(target["accepted_times"] >= result.times[0])
            np.testing.assert_array_equal(result.times, target["accepted_times"][indices])
            scalar_state = self.reference.flatten(
                self.context, {k: target[k][indices] for k in result.history._fields}
            )
            selected = np.flatnonzero(target["observation_times"] >= result.times[0])
            np.testing.assert_array_equal(
                result.observations.times, target["observation_times"][selected]
            )
        with np.load(scalar / "comparison.npz", allow_pickle=False) as comparison:
            independent = comparison["reference"][selected]
        actual = self.reference.flatten(self.context, vars(result.observations))
        np.savez_compressed(
            self.folder(phase) / f"world-{world_id}-comparison.npz",
            times=result.observations.times,
            actual=actual,
            reference=independent,
        )
        scalar_ratio = assert_states(
            self.context,
            self.reference.flatten(self.context, result.history._asdict()),
            scalar_state,
        )
        reference_ratio = assert_states(self.context, actual, independent)
        return dict(
            world_id=world_id,
            fields=self.field_count,
            start_time=float(result.times[0]),
            end_time=result.final.time,
            executed_steps=len(result.times) - 1,
            observation_rows=len(result.observations.times),
            scalar_error_over_budget=scalar_ratio,
            independent_error_over_budget=reference_ratio,
            diagnostics=result.diagnostics,
        )

    def baseline(self):
        self.load_inputs()
        self.artifact("admission")
        self.begin("baseline")
        results = self.integrate("baseline", self.batch, self.checkpoints, save_midpoint=True)
        comparisons = [self.correspondence("baseline", i, r) for i, r in results.items()]
        self.finish(
            "baseline", dict(worlds=comparisons, midpoint=self.midpoint, window_steps=self.width)
        )

    def restart(self):
        self.load_inputs()
        baseline = self.artifact("baseline")
        assert baseline["process"] != process_identity(), "Restart must run in a fresh process"
        saved = load_batch_snapshot(self.folder("baseline") / "midpoint")
        assert saved.spec == self.batch and set(saved.checkpoints) == set(WORLD_IDS)
        for point in saved.checkpoints.values():
            assert point.time == self.midpoint["time_s"]
            assert point.step_index == self.midpoint["global_step_index"]
        self.begin("restart")
        results = self.integrate("restart", saved.spec, saved.checkpoints, save_midpoint=False)
        comparisons = []
        for world_id, result in results.items():
            assert len(result.times) - 1 == self.midpoint["remaining_accepted_steps"] > 0
            original = self.folder("baseline") / f"world-{world_id}"
            with np.load(original / "trajectory.npz", allow_pickle=False) as target:
                indices = np.flatnonzero(target["accepted_times"] >= result.times[0])
                np.testing.assert_array_equal(result.times, target["accepted_times"][indices])
                for name, actual in result.history._asdict().items():
                    np.testing.assert_array_equal(actual, target[name][indices])
                selected = np.flatnonzero(target["observation_times"] >= result.times[0])
                for name, actual in vars(result.observations).items():
                    key = "observation_times" if name == "times" else f"observed_{name}"
                    np.testing.assert_array_equal(actual, target[key][selected])
            final = load_snapshot(original / "checkpoint_final")
            exact(result.final.state, final.checkpoint.state)
            exact(result.final.layout, final.checkpoint.layout)
            comparisons.append(self.correspondence("restart", world_id, result))
        self.finish(
            "restart",
            dict(
                worlds=comparisons,
                window_steps=self.width,
                baseline_metadata_sha256=sha(self.folder("baseline") / "metadata.json"),
                exact_complete_state_layout_clock_and_observation_suffix=True,
                fresh_process=True,
            ),
        )
