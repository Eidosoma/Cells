"""A model family joins `cells ensemble` through its row of the static model table (docs/
CORE_SEAMS_DESIGN.md §15's follow-up; the lead's ruling (a), 18 November 2026), each claim with a
planted error it must catch (D187):

- a family whose row names its EnsembleAdapter plans and runs its arms through the ensemble's plan
  and worker, with no edit to ensemble/* (planted: the same family with no row, whose kind the
  plan refuses);
- through the whole launch path, `cells ensemble run` (register, the controller, its spawned
  workers and its summary), a family runs whichever form its definitions write the model in, a
  string or {"id": ..., ...}, and the controller's summary is its adapter's aggregate hook (the
  second external review's finding 5: the object form was refused by the planner, then by the
  launcher's lookup, and an adapter family failed in the summary after its whole campaign);
- the table's ensemble entries are held to the protocol (planted, each refused: a missing module,
  a missing object, an object that is not an adapter, an adapter without its aggregate hook, and
  an adapter taking one of today's kinds), and the summary refuses an adapter family's rows mixed
  with others, an aggregate writing the controller's own timing keys, and one dropping an arm;
- today's three ensemble kinds keep their models and their chains: MODELS ends with them, and each
  of today's models finds no adapter (their plan-and-run tests are tests/unit/test_ensemble*.py); a
  parked kind is refused by its name, as its command line is, and an adapter may take it.
"""

import json
import os
import queue
import signal
import subprocess
import sys
import threading
from pathlib import Path
from types import MappingProxyType

import pytest

import cells
from cells.__main__ import main
from cells.ensemble import cli, families
from cells.ensemble.plan import plan
from cells.registry import model_table

ROOT = Path(cells.__file__).resolve().parents[2]
MODEL = "tests.model.planted_ensemble@1"
KIND = "tests.planted_ensemble_kind@1"
PLANTED = '''"""A planted ensemble family: pure Python, no device, for the protocol alone."""

import json
from pathlib import Path
from types import SimpleNamespace

from cells.ensemble.families import EnsembleAdapter

MODEL = "tests.model.planted_ensemble@1"
FORM = "{form}"  # How its definitions write the model: a string, or an object with an ID.
FIELDS = ("worlds", "world_id_start", "seed", "end_time_s", "recording")


def model_field():
    return {{"id": MODEL, "variant": "planted"}} if FORM == "object" else MODEL


class Spec(SimpleNamespace):
    def to_dict(self):
        return {{"model": model_field(), **{{name: getattr(self, name) for name in FIELDS}}}}


def parse(data):
    given = data["model"]["id"] if isinstance(data["model"], dict) else data["model"]
    if given != MODEL:
        raise ValueError("not this family")
    spec = Spec(**{{name: data[name] for name in FIELDS}})
    spec.fingerprint = json.dumps(spec.to_dict(), sort_keys=True)
    return spec


def bind(data, *, worlds, world_id_start, seed, reject_owned=False):
    if reject_owned and {{"worlds", "world_id_start", "seed"}} & set(data):
        raise ValueError("the ensemble owns the counts")
    return {{**data, "worlds": worlds, "world_id_start": world_id_start, "seed": seed}}


def run(spec, *, backend, state=None, callback=None):
    worlds = list(range(spec.world_id_start, spec.world_id_start + spec.worlds))
    state = {{"worlds": worlds, "values": [spec.seed + w for w in worlds]}}
    if callback is not None:
        callback(0, state, None)
    return state, {{"worlds": spec.worlds}}


def write_checkpoint(path, spec, state, *, execution, provenance=None):
    Path(path).mkdir()
    (Path(path) / "manifest.json").write_text(json.dumps(state))
    return "planted"


def load_checkpoint(path):
    raise AssertionError("no continuation in this test")


def aggregate(rows):
    arms = {{}}
    for row in rows:
        arm = arms.setdefault(row["arm"], {{"tasks": 0}})
        arm["tasks"] += 1
    return arms


ADAPTER = EnsembleAdapter(
    kind="tests.planted_ensemble_kind@1",
    model=MODEL,
    bind_definition=bind,
    population=lambda spec: spec,
    output_bound=lambda spec: 1024,
    parse_definition=parse,
    runtime=lambda spec: (run, load_checkpoint, write_checkpoint),
    first_completion=lambda spec, state: None,
    progress=lambda spec, state: {{"worlds": len(state["worlds"])}},
    failure_state=lambda spec, state: {{}},
    aggregate=aggregate,
)
NOT_AN_ADAPTER = object()
'''
# The launch path's driver: its top level, which the controller's spawned workers run again as
# their __mp_main__, joins the planted family to the model table and stands in a GPU row and a
# monitor for nvidia-smi; `cells ensemble run` then registers, runs the controller in the
# foreground, and writes the summary.
DRIVER = """import sys
sys.path.insert(0, {root!r})
from types import MappingProxyType
from cells.registry import model_table
from pathlib import Path
module, entry = "planted_ensemble", "planted_ensemble:ADAPTER"
row = model_table.Model(type="family", module=module, ensemble=entry)
model_table.MODELS = MappingProxyType({{**model_table.MODELS, {model!r}: row}})
from cells.ensemble import cli
gpu = {{"index": "0", "uuid": "GPU-planted", "name": "planted"}}
cli.devices = lambda requested, expected: [gpu]


class NoMonitor:  # No GPU to sample: an empty sample file, as a monitor without readings leaves.
    def __init__(self, path, uuids, **kwargs):
        self.path = Path(path)

    def start(self):
        self.path.write_text("")

    def finish(self):
        pass


cli.Monitor = NoMonitor
if __name__ == "__main__":
    sys.exit(cli.main(["run", sys.argv[1], "--output", sys.argv[2], "--allocated-gpus", "1"]))
"""
EXECUTION = {
    "max_wall_seconds": 600,
    "max_output_bytes": 64 * 1024**2,
    "target_gpu_utilization_pct": 90,
    "worker_threads": 1,
}


def plan_data(form="string"):
    model = {"id": MODEL, "variant": "planted"} if form == "object" else MODEL
    arm = {"model": model, "end_time_s": 1.0, "recording": "summary"}
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


def write_family(root, form="string", text=PLANTED):
    (root / "planted_ensemble.py").write_text(text.format(form=form))


@pytest.fixture
def planted(tmp_path, monkeypatch):
    write_family(tmp_path)
    monkeypatch.syspath_prepend(str(tmp_path))
    yield tmp_path
    sys.modules.pop("planted_ensemble", None)


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


@pytest.mark.parametrize("form", ["string", "object"])
def test_either_model_form_runs_through_register_the_controller_and_its_workers(tmp_path, form):
    family = tmp_path / "family"
    family.mkdir()
    write_family(family, form)
    (tmp_path / "drive.py").write_text(DRIVER.format(root=str(family), model=MODEL))
    (tmp_path / "ensemble.json").write_text(json.dumps(plan_data(form)))
    out = tmp_path / "out" / "run"
    env = dict(
        os.environ,
        PYTHONPATH=os.pathsep.join((str(ROOT / "src"), str(ROOT))),
        CELLS_OUTPUT_ROOT=str(tmp_path / "out"),
        JAX_PLATFORMS="cpu",
        PYTHONDONTWRITEBYTECODE="1",
    )
    done = subprocess.run(
        [sys.executable, str(tmp_path / "drive.py"), str(tmp_path / "ensemble.json"), str(out)],
        capture_output=True,
        text=True,
        env=env,
        cwd=ROOT,
        timeout=600,
    )
    assert done.returncode == 0, (done.stdout[-2000:], done.stderr[-4000:])
    summary = json.loads((out / "result.json").read_text())
    (arm,) = summary["arms"].values()
    assert set(summary["arms"]) == {"arm-a"} and arm["tasks"] == 2  # The adapter's own summary,
    assert arm["worlds"] == 4 and len(arm["task_seconds_per_world"]) == 2  # beside the timing.
    assert (out / "cost-profile.json").exists()  # Its cost profile reads that timing.
    registration = json.loads((out / "registration.json").read_text())
    for task in registration["plan"]["tasks"]:
        written = task["definition"]["model"]
        assert written == ({"id": MODEL, "variant": "planted"} if form == "object" else MODEL)
        row = json.loads((out / "tasks" / task["id"] / "result.json").read_text())
        assert row["status"] == "completed" and families.row_model(row) == MODEL


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
    # Planted: an adapter without its aggregate hook, which cannot be built.
    sys.modules.pop("planted_ensemble", None)
    write_family(planted, text=PLANTED.replace("    aggregate=aggregate,\n", ""))
    with_row(monkeypatch, "planted_ensemble:ADAPTER")
    (error,) = families.adapter_errors(model_table.MODELS)
    assert "does not resolve" in error and "aggregate" in error
    # Planted: an adapter taking one of today's kinds.
    sys.modules.pop("planted_ensemble", None)
    write_family(planted)
    import planted_ensemble

    monkeypatch.setattr(
        planted_ensemble, "ADAPTER", planted_ensemble.ADAPTER._replace(kind="ionic_ensemble@1")
    )
    (error,) = families.adapter_errors(model_table.MODELS)
    assert "is taken" in error
    parked = planted_ensemble.ADAPTER._replace(kind="assembly_cell_ensemble@1")
    monkeypatch.setattr(planted_ensemble, "ADAPTER", parked)  # A parked kind is free to take.
    assert families.adapter_errors(model_table.MODELS) == []
    assert families.MODELS["assembly_cell_ensemble@1"] == MODEL


def test_the_summary_refuses_an_adapter_family_mixed_with_others(planted, monkeypatch):
    with_row(monkeypatch, "planted_ensemble:ADAPTER")
    ours = {"arm": "arm-a", "worlds": 2, "wall_start": 0.0, "wall_end": 4.0}
    ours["definition"] = {"model": {"id": MODEL}}
    assert cli.aggregate([ours]) == {
        "arm-a": {
            "worlds": 2,
            "task_wall_seconds": [4.0],
            "task_seconds_per_world": [2.0],
            "tasks": 1,
        }
    }
    theirs = {"arm": "arm-b", "worlds": 2, "model": "cells.model.ionic_worlds@1"}
    with pytest.raises(ValueError, match="cannot mix an adapter family's results"):
        cli.aggregate([ours, theirs])
    # Planted: an aggregate that writes the controller's own keys, and one that drops an arm.
    import planted_ensemble

    adapter = planted_ensemble.ADAPTER
    for hook, words in (
        (lambda rows: {"arm-a": {"worlds": 9}}, "writes the controller's keys"),
        (lambda rows: {}, "summarises each of its arms once"),
    ):
        monkeypatch.setattr(planted_ensemble, "ADAPTER", adapter._replace(aggregate=hook))
        with pytest.raises(ValueError, match=words):
            cli.aggregate([ours])


def test_today_s_three_keep_their_models_and_their_chains(capsys):
    assert dict(families.MODELS) == families.TODAY  # No row names an adapter today.
    assert list(families.TODAY) == [
        "assembly_ensemble@1",
        "finite_bond_ensemble@1",
        "ionic_ensemble@1",
    ]
    assert all(families.adapter_of(model) is None for model in families.TODAY.values())
    data = {"model": "cells.model.capsid_graph@1", "worlds": 1, "world_id_start": 0, "seed": 1}
    bound = families.bind_definition(data, worlds=3, world_id_start=5, seed=9)
    assert bound == {
        "model": "cells.model.capsid_graph@1",
        "worlds": 3,
        "world_id_start": 5,
        "seed": 9,
    }
    assert families.model_of({"id": "cells.model.capsid_graph@1"}) == families.model_of(
        "cells.model.capsid_graph@1"
    )
    for kind in ("assembly_cell_ensemble@1", "assembly_cluster_ensemble@1"):
        with pytest.raises(
            ValueError, match=f"^{kind} is parked: .* cells.model.resolved_pump_composite@1"
        ):
            plan(dict(plan_data(), kind=kind), 1)
    for command in ("assembly-cell", "assembly-cluster"):  # And so are their two command lines.
        assert main([command]) == 2
        assert capsys.readouterr().err.startswith(f"cells: {command} is parked: ")
