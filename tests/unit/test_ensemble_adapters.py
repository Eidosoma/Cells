"""A model family joins `cells ensemble` through its row of the static model table (docs/
CORE_SEAMS_DESIGN.md §15's follow-up; the lead's ruling (a), 18 November 2026), each claim with a
planted error it must catch (D187):

- a family whose row names its EnsembleAdapter plans and runs its arms through the ensemble's plan
  and worker, with no edit to ensemble/* (planted: the same family with no row, whose kind the
  plan refuses);
- the table's ensemble entries are held to the protocol (planted, each refused: a missing module,
  a missing object, an object that is not an adapter, and an adapter taking one of today's kinds);
- today's five ensemble kinds keep their models and their chains: MODELS ends with them, and each
  of today's models finds no adapter (their plan-and-run tests are tests/unit/test_ensemble*.py).
"""

import json
import os
import queue
import signal
import threading
from types import MappingProxyType

import pytest

from cells.ensemble import families
from cells.ensemble.plan import plan
from cells.registry import model_table

MODEL = "tests.planted_ensemble@1"
KIND = "tests.planted_ensemble_kind@1"
PLANTED = '''"""A planted ensemble family: pure Python, no device, for the protocol alone."""

import json
from pathlib import Path
from types import SimpleNamespace

from cells.ensemble.families import EnsembleAdapter

MODEL = "tests.planted_ensemble@1"
FIELDS = ("worlds", "world_id_start", "seed", "end_time_s", "recording")


class Spec(SimpleNamespace):
    def to_dict(self):
        return {"model": MODEL, **{name: getattr(self, name) for name in FIELDS}}


def parse(data):
    spec = Spec(**{name: data[name] for name in FIELDS})
    spec.fingerprint = json.dumps(spec.to_dict(), sort_keys=True)
    return spec


def bind(data, *, worlds, world_id_start, seed, reject_owned=False):
    if reject_owned and {"worlds", "world_id_start", "seed"} & set(data):
        raise ValueError("the ensemble owns the counts")
    return {**data, "worlds": worlds, "world_id_start": world_id_start, "seed": seed}


def run(spec, *, backend, state=None, callback=None):
    worlds = list(range(spec.world_id_start, spec.world_id_start + spec.worlds))
    state = {"worlds": worlds, "values": [spec.seed + w for w in worlds]}
    if callback is not None:
        callback(0, state, None)
    return state, {"worlds": spec.worlds}


def write_checkpoint(path, spec, state, *, execution, provenance=None):
    Path(path).mkdir()
    (Path(path) / "manifest.json").write_text(json.dumps(state))
    return "planted"


def load_checkpoint(path):
    raise AssertionError("no continuation in this test")


ADAPTER = EnsembleAdapter(
    kind="tests.planted_ensemble_kind@1",
    model=MODEL,
    bind_definition=bind,
    population=lambda spec: spec,
    output_bound=lambda spec: 1024,
    parse_definition=parse,
    runtime=lambda spec: (run, load_checkpoint, write_checkpoint),
    first_completion=lambda spec, state: None,
    progress=lambda spec, state: {"worlds": len(state["worlds"])},
    failure_state=lambda spec, state: {},
)
NOT_AN_ADAPTER = object()
'''
EXECUTION = {
    "max_wall_seconds": 600,
    "max_output_bytes": 64 * 1024**2,
    "target_gpu_utilization_pct": 90,
    "worker_threads": 1,
}


def plan_data():
    arm = {"model": MODEL, "end_time_s": 1.0, "recording": "summary"}
    return {
        "kind": KIND,
        "seed": 7,
        "arms": [
            {
                "id": "arm-a",
                "definition": arm,
                "worlds": 4,
                "batch_worlds": 2,
                "seconds_per_world": None,
            }
        ],
        "execution": EXECUTION,
    }


def with_row(monkeypatch, entry):
    """The static table with one planted family row naming `entry` as its adapter."""
    row = model_table.Model(type="family", module="planted_ensemble", ensemble=entry)
    monkeypatch.setattr(model_table, "MODELS", MappingProxyType({**model_table.MODELS, MODEL: row}))


@pytest.fixture
def planted(tmp_path, monkeypatch):
    (tmp_path / "planted_ensemble.py").write_text(PLANTED)
    monkeypatch.syspath_prepend(str(tmp_path))
    return tmp_path


def run_worker(root, tasks, monkeypatch):
    """The ensemble's worker, in this process, over `tasks`; the process's environment, signal
    handlers and CPU affinity are restored afterwards."""
    from cells.ensemble.worker import worker

    for name in (
        "CUDA_VISIBLE_DEVICES",
        "JAX_PLATFORMS",
        "OMP_NUM_THREADS",
        "OPENBLAS_NUM_THREADS",
    ):
        monkeypatch.setenv(name, os.environ.get(name, ""))
    for name in ("MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
        monkeypatch.setenv(name, os.environ.get(name, ""))
    handlers = {sig: signal.getsignal(sig) for sig in (signal.SIGUSR1, signal.SIGTERM)}
    affinity = sorted(os.sched_getaffinity(0))  # A list, as the CLI passes it.
    work = queue.Queue()
    for task in tasks:
        work.put(task)
    work.put(None)
    try:
        worker(
            root, 0, {"uuid": "planted", "name": "planted"}, affinity, work, threading.Event(), {}
        )
    finally:
        os.sched_setaffinity(0, affinity)
        for sig, handler in handlers.items():
            signal.signal(sig, handler)


def test_a_family_joins_the_ensemble_through_its_table_row(planted, monkeypatch):
    with pytest.raises(ValueError, match="Require a named ensemble"):
        plan(plan_data(), 1)  # Planted: no row, so the ensemble does not know the kind.
    with_row(monkeypatch, "planted_ensemble:ADAPTER")
    assert families.MODELS[KIND] == MODEL and list(families.MODELS)[0] == KIND
    planned = plan(plan_data(), 1)
    tasks = planned["tasks"]
    assert planned["worlds"] == 4 and [t["definition"]["world_id_start"] for t in tasks] == [0, 2]
    root = planted / "run"
    (root / "tasks").mkdir(parents=True)
    run_worker(root, tasks, monkeypatch)
    for task in tasks:
        result = json.loads((root / "tasks" / task["id"] / "result.json").read_text())
        assert result["status"] == "completed" and result["worlds"] == 2
        assert result["checkpoint_manifest_sha256"] == "planted"


def test_the_table_s_ensemble_entries_are_held_to_the_protocol(planted, monkeypatch):
    assert families.adapter_errors(model_table.MODELS) == []
    for entry, words in (
        ("planted_missing_module:ADAPTER", "does not resolve"),
        ("planted_ensemble:MISSING", "does not resolve"),
        ("planted_ensemble:NOT_AN_ADAPTER", "is not an EnsembleAdapter"),
    ):
        with_row(monkeypatch, entry)
        (error,) = families.adapter_errors(model_table.MODELS)
        assert words in error, (entry, error)
        with pytest.raises(ValueError, match=words):
            families.adapters()
    # Planted: an adapter taking one of today's kinds.
    import planted_ensemble

    monkeypatch.setattr(
        planted_ensemble, "ADAPTER", planted_ensemble.ADAPTER._replace(kind="ionic_ensemble@1")
    )
    with_row(monkeypatch, "planted_ensemble:ADAPTER")
    (error,) = families.adapter_errors(model_table.MODELS)
    assert "is taken" in error


def test_today_s_five_keep_their_models_and_their_chains():
    assert dict(families.MODELS) == families.TODAY  # No row names an adapter today.
    assert list(families.TODAY) == [
        "assembly_ensemble@1",
        "finite_bond_ensemble@1",
        "assembly_cell_ensemble@1",
        "assembly_cluster_ensemble@1",
        "ionic_ensemble@1",
    ]
    assert all(families._adapter(model) is None for model in families.TODAY.values())
    data = {"model": "capsid_graph@1", "worlds": 1, "world_id_start": 0, "seed": 1}
    bound = families.bind_definition(data, worlds=3, world_id_start=5, seed=9)
    assert bound == {"model": "capsid_graph@1", "worlds": 3, "world_id_start": 5, "seed": 9}
