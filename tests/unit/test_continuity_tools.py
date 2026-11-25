"""The continuity tools' own logic, without compiling a model program (validation/continuity).

probe.py's exact digests, its constants walker (jaxpr text omits closed-over values, design
section 4.3), its overlap length and its identity-free read; admit.py's comparisons and its
lineage check (section 5). The end-to-end runs are tests/integration/
test_continuity_acceptance.py.
"""

import json
import sys
from pathlib import Path
from types import SimpleNamespace

import jax
import jax.numpy as jnp
import numpy as np
import pytest

import cells
from cells.definitions.specs import ConfigError
from cells.execution import continuity
from cells.records import batch_io, io, source_layout
from validation.continuity import (
    admit,
    probe,
    verify_run,
)


@pytest.fixture(scope="module", autouse=True)
def x64():
    jax.config.update("jax_enable_x64", True)


def test_exact_keeps_every_bit():
    assert probe.exact(0.1) == {"float": (0.1).hex()}
    assert probe.exact(np.float64(0.1)) == probe.exact(0.1)
    assert probe.exact(np.nextafter(0.1, 1.0)) != probe.exact(0.1)
    value = probe.exact({"a": [1, True, None, "x"], 2: np.arange(3.0)})
    assert value["a"] == [1, True, None, "x"]
    assert value["2"] == probe.arr(np.arange(3.0)) and value["2"]["shape"] == [3]


def test_constants_are_found_where_the_text_omits_them():
    def closing(c):
        def f(x):
            return jax.lax.scan(lambda s, _: (s + jnp.asarray(c), None), x, None, length=2)[0]

        return jax.make_jaxpr(f)(np.zeros(5))

    a, b = closing(np.arange(5.0)), closing(np.arange(5.0) + 1.0)
    assert str(a) == str(b)  # The text does not carry the closed-over values ...
    ca, cb = probe.all_consts(a), probe.all_consts(b)
    assert len(ca) == len(cb) == 1
    assert probe.arr(ca[0]) != probe.arr(cb[0])  # ... their digests do.


def spec(changes=(), observations=()):
    return SimpleNamespace(
        simulation=SimpleNamespace(
            experiment=SimpleNamespace(
                changes=[SimpleNamespace(time=t) for t in changes], observation_times=observations
            )
        ),
        world_id=1,
    )


def rounds(ends, start=0.0):
    out, previous = [], start
    for end in ends:
        out.append(dict(clocks=[dict(start=previous, end=end, steps=1, live=True)]))
        previous = end
    return out


@pytest.mark.parametrize(
    ("changes", "observations", "expected"),
    [
        ((), (), 2),  # At least two rounds.
        ((0.024,), (), 3),  # An event at a round's end acts in the round after it.
        ((0.023,), (), 2),
        ((), (0.024,), 2),  # An observation at a round's end is in that round.
        ((), (0.032,), 3),
        ((0.5,), (), 4),  # Beyond the horizon: all of it.
        ((0.004,), (0.004,), 2),  # Before the checkpoint: not ahead.
    ],
)
def test_the_overlap_runs_past_the_next_event_and_observation(changes, observations, expected):
    batch = SimpleNamespace(worlds=[spec(changes, observations)])
    checkpoints = {1: SimpleNamespace(time=0.008)}
    built = rounds([0.016, 0.024, 0.032, 0.040], start=0.008)
    assert probe.minimum_overlap(batch, checkpoints, built) == expected
    assert probe.minimum_overlap(batch, checkpoints, built[:1]) == 1  # The whole horizon.


def test_differences_name_the_paths():
    a = {"x": [1, 2, {"y": 3}], "z": 1}
    b = {"x": [1, 5, {"y": 4}], "w": 1}
    assert admit.differences(a, b, "R") == [
        "R.w: present on one side only",
        "R.x[1]",
        "R.x[2].y",
        "R.z: present on one side only",
    ]
    assert admit.differences([1], [1, 2], "L") == ["L: length 1 against 2"]
    assert admit.differences(a, a) == []


def summary(**changes):
    base = dict(
        P0=dict(arguments={"a": 1}, program={"jaxpr_sha256": "1"}, compile_arguments="((), [])"),
        P={"f": {"checked_step": {"jaxpr_sha256": "2"}}},
        B=dict(
            plan={},
            resident={"r": 1},
            definitions={},
            rounds=2,
            rounds_sha256="3",
            minimum_overlap=2,
            first_round_equals_P0=True,
        ),
        H=dict(rows=[{"check_values": {}}], saved_states=1),
    )
    for part, value in changes.items():
        base[part] = {**base[part], **value}
    return base


def probe_dir(tmp_path, name, text="text", rounds_text="r0\nr1\n"):
    path = tmp_path / name
    (path / "texts").mkdir(parents=True)
    (path / "texts" / "vector_window.jaxpr.txt").write_text(text)
    (path / "rounds.jsonl").write_text(rounds_text)
    return path


def test_probe_comparison_parts(tmp_path):
    a, b = probe_dir(tmp_path, "a"), probe_dir(tmp_path, "b")
    report = admit.compare_probes(summary(), summary(), a, b)
    assert all(row["identical"] for row in report.values())
    report = admit.compare_probes(summary(), summary(H=dict(saved_states=2)), a, b)
    assert [p for p, row in report.items() if not row["identical"]] == ["H"]
    c = probe_dir(tmp_path, "c", text="other", rounds_text="r0\nrX\n")
    report = admit.compare_probes(summary(), summary(B=dict(rounds_sha256="4")), a, c)
    assert {p for p, row in report.items() if not row["identical"]} == {"B", "texts"}
    assert report["B"]["first_differing_round"] == 1
    report = admit.compare_probes(summary(), summary(B=dict(first_round_equals_P0=False)), a, b)
    assert not report["first_round_equals_P0_S1"]["identical"]


def overlap_summary(calls=({"arrays": [1]},), outputs=({"worlds": {}},), failure=None):
    return dict(
        O=dict(
            rounds=1,
            completed=len(outputs),
            calls=list(calls),
            outputs=list(outputs),
            failure=failure,
            arguments_equal_own_rounds=True,
        )
    )


def test_a_host_replay_that_raises_cannot_decide():
    """H would pass vacuously if a check raised identically under both trees."""
    clean = summary()
    assert admit.host_replay_errors(clean) == []
    raised = summary(
        H=dict(
            rows=[
                {
                    "state": "checkpoint",
                    "world": 1,
                    "step_index": 8,
                    "check_values": {"raised": "ConfigError: refused"},
                    "observe_history": {"times": probe.arr(np.zeros(1))},
                    "summarize": "0" * 64,
                }
            ]
        )
    )
    assert admit.host_replay_errors(raised) == ["checkpoint, world 1, step 8: check_values raised"]
    assert admit.compare_probes(raised, raised, *(Path("."),) * 2)["H"]["identical"]  # Vacuous.


def test_overlap_comparison_checks():
    report = admit.compare_overlaps(overlap_summary(), overlap_summary())
    assert all(report["checks"].values())
    report = admit.compare_overlaps(overlap_summary(), overlap_summary(calls=({"arrays": [2]},)))
    assert not report["checks"]["arguments_identical"] and report["checks"]["outputs_bitwise_equal"]
    refused = overlap_summary(outputs=(), failure={"error": "refused", "checks": ["step"]})
    assert not admit.compare_overlaps(overlap_summary(), refused)["checks"]["completed"]


def cohort_snapshot(tmp_path, jit=True):
    from cells.execution.batch import parse_batch
    from cells.execution.state import initialise
    from tests.batch_fixtures import definition, short_spec

    first = short_spec("reaction_transport_single", jit=jit)
    batch = parse_batch(definition([first, first]).to_dict())
    starts = {w.world_id: initialise(w.simulation) for w in batch.worlds}
    return batch_io.write_batch_snapshot(tmp_path / f"cohort-{jit}", batch, starts)


def test_the_probes_read_keeps_the_loader_checks(tmp_path):
    path = cohort_snapshot(tmp_path)
    spec, checkpoints, manifest, children = probe.read_cohort(path)
    loaded = batch_io.load_batch_snapshot(path)
    assert spec == loaded.spec and manifest["manifest_sha256"] == loaded.fingerprint
    assert sorted(children) == sorted(loaded.checkpoints) == [10, 11]
    for identity, checkpoint in checkpoints.items():
        for x, y in zip(checkpoint.state, loaded.checkpoints[identity].state, strict=True):
            np.testing.assert_array_equal(np.asarray(x), np.asarray(y))
    with (path / "world-11" / "state.npz").open("ab") as handle:
        handle.write(b"corrupted")
    with pytest.raises(ConfigError, match="^Checkpoint state checksum mismatch$"):
        probe.read_cohort(path)


def test_the_probes_read_keeps_the_layout_check(tmp_path, monkeypatch):
    """D195 item 4 under the resuming tree: a cohort written before a declared move is refused,
    so no record is proposed for it (a planted move that dissolved the definitions' folder)."""
    path = cohort_snapshot(tmp_path)
    folder = Path(sys.modules[ConfigError.__module__].__file__).parent
    move = source_layout.Move(
        "the planted move", (folder.relative_to(Path(cells.__file__).parent).as_posix(),), "tag"
    )
    monkeypatch.setattr(source_layout, "MOVES", (move,))
    with pytest.raises(ConfigError, match="^Batch checkpoint was written .* tagged tag$"):
        probe.read_cohort(path)
    with pytest.raises(ConfigError, match="^Checkpoint was written .* tagged tag$"):
        probe.read_scalar(path / "world-10")
    monkeypatch.setattr(probe, "LAYOUT", "cells.not_here.source_layout")  # A tree before the rule.
    assert sorted(probe.read_cohort(path)[1]) == [10, 11]
    monkeypatch.undo()
    monkeypatch.setattr(source_layout, "MOVES", ())  # The control: no move made.
    assert sorted(probe.read_cohort(path)[1]) == [10, 11]


def test_the_probe_cannot_decide_outside_the_first_landing(tmp_path):
    with pytest.raises(probe.CannotDecide, match="jit: false"):
        probe.read_cohort(cohort_snapshot(tmp_path, jit=False))
    scalar = tmp_path / "scalar"
    from cells.execution.state import initialise
    from tests.batch_fixtures import short_spec

    one = short_spec("reaction_transport_single")
    io.write_snapshot(scalar, one, initialise(one))
    with pytest.raises(probe.CannotDecide, match="names no cohort"):
        probe.read_cohort(scalar)
    # A model without device checks: the vector-windows path cannot run it.
    out = tmp_path / "probe"
    code = probe.main(
        [
            "run",
            "--checkpoint",
            str(cohort_snapshot(tmp_path)),
            "--out",
            str(out),
            "--window-steps",
            "4",
            "--recording",
            "checkpoints",
        ]
    )
    result = json.loads((out / "summary.json").read_text())
    assert code == 3 and result["status"] == "cannot_decide"
    assert "device checks" in result["reason"] and result["reproduces_manifest"] is True


def test_lineage_is_checked_not_trusted(tmp_path, monkeypatch):
    from tests.unit.test_continuity_loaders import build_record, change_source, write_record

    path = cohort_snapshot(tmp_path)
    fresh = tmp_path / "run0"
    fresh.mkdir()
    (fresh / "manifest.json").write_text(json.dumps({"provenance": {"operation": "fresh"}}))
    assert admit.lineage_of(fresh) == []
    change_source(monkeypatch)
    record_dir = tmp_path / "run1" / "continuity"
    record_dir.mkdir(parents=True)
    record = build_record(path)
    record_path = write_record(record_dir, record)
    admitted = tmp_path / "run1" / "manifest.json"
    provenance = {
        "operation": "admitted_resume",
        "continuity_record": str(record_path),
        "record_sha256": record["record_sha256"],
    }
    admitted.write_text(json.dumps({"provenance": provenance}))
    assert admit.lineage_of(tmp_path / "run1") == [
        {"record": str(record_path), "record_sha256": record["record_sha256"]}
    ]
    provenance["record_sha256"] = "0" * 64
    admitted.write_text(json.dumps({"provenance": provenance}))
    with pytest.raises(ValueError, match="names a record that differs"):
        admit.lineage_of(tmp_path / "run1")
    with pytest.raises(SystemExit, match="has no manifest.json"):
        admit.lineage_of(tmp_path / "absent")


def test_verify_run_walks_the_lineage_back_to_a_fresh_run(tmp_path, monkeypatch):
    """Two admissions of one run (design section 5): each record repeats its parent's chain."""
    from tests.unit.test_continuity_loaders import build_record, change_source

    path = cohort_snapshot(tmp_path)
    change_source(monkeypatch)

    def run(name, parent, record=None):
        folder = tmp_path / name
        (folder / "continuity").mkdir(parents=True)
        provenance = {"operation": "fresh"}
        if record is not None:
            target = folder / "continuity" / "record.json"
            target.write_text(json.dumps(record))
            provenance = {
                "operation": "admitted_resume",
                "continuity_record": str(target),
                "record_sha256": record["record_sha256"],
            }
        (folder / "manifest.json").write_text(json.dumps({"provenance": provenance}))
        parent = None if parent is None else str(parent)
        (folder / "inputs.json").write_text(json.dumps({"checkpoint_run": parent}))
        return folder

    run0 = run("run0", None)
    first = build_record(path)
    run1 = run("run1", run0, first)
    link = {
        "record": str(run1 / "continuity" / "record.json"),
        "record_sha256": first["record_sha256"],
    }
    second = build_record(path, lineage=[link])
    run2 = run("run2", run1, second)
    report = verify_run.Report()
    verify_run.lineage(run2, second, report)
    assert report.ok
    assert [c["check"] for c in report.checks] == [
        "lineage[0].record",
        "lineage[1].record",
        "lineage[2].fresh",
    ]
    report = verify_run.Report()
    verify_run.lineage(run2, build_record(path), report)  # The second without the first.
    assert not report.ok and not report.checks[0]["ok"]


def test_admit_proposes_what_the_loader_and_parse_record_accept():
    """The fields admit.py writes are the record's, less the admitter and the seal."""
    import inspect

    source = inspect.getsource(admit.propose)
    written = {
        k
        for k in continuity.RECORD_FIELDS
        if f'"{k}":' in source or f"'{k}':" in source or f"{k}=" in source
    }
    assert set(continuity.RECORD_FIELDS) - written == {
        "admitted_by",
        "admitted_utc",
        "record_sha256",
    }
    assert Path(admit.__file__).parent == Path(probe.__file__).parent


def test_a_gpu_cohorts_to_runtime_is_the_checkpoints_own():
    """Section 13.4: the CPU host cannot measure the GPU host's runtime; no runtime change is
    admissible, so to is the checkpoint's runtime under the resuming tree's cells_version."""
    probe_runtime = io.runtime_identity("cpu")
    manifest = {**probe_runtime, "cells_version": "0.0.1", "gpu": {"device_kind": "NVIDIA L4"}}
    runtime, fields = admit.resuming_runtime(manifest, probe_runtime, None)
    assert runtime is probe_runtime and fields == continuity.HOST_FIELDS  # A CPU cohort.
    runtime, fields = admit.resuming_runtime(manifest, probe_runtime, {"backend": "gpu"})
    assert runtime == {**manifest, "cells_version": probe_runtime["cells_version"]}
    assert fields == (*continuity.HOST_FIELDS, "packages.jaxlib")


def test_the_probe_decides_gpu_cohorts_and_refuses_the_rest():
    def batch(*backends, jit=True, projective=None):
        return SimpleNamespace(
            worlds=[
                SimpleNamespace(
                    world_id=i,
                    simulation=SimpleNamespace(
                        execution=SimpleNamespace(backend=b, jit=jit), projective=projective
                    ),
                )
                for i, b in enumerate(backends)
            ]
        )

    assert probe.require_scope(batch("cpu", "cpu")) == "cpu"
    assert probe.require_scope(batch("gpu", "gpu")) == "gpu"
    for refused, message in (
        (batch("gpu", jit=False), "jit: false"),
        (batch("gpu", projective=object()), "projective"),
        (batch("tpu"), "a tpu definition"),
        (batch("cpu", "gpu"), "mixes backends"),
    ):
        with pytest.raises(probe.CannotDecide, match=message):
            probe.require_scope(refused)


def test_the_device_patch_reaches_every_binding_and_is_recorded():
    """In a fresh process, as the probe runs: no module keeps the unpatched function."""
    import subprocess
    import sys

    root = Path(__file__).resolve().parents[2]
    code = (
        "import sys, json\n"
        "from validation.continuity import probe\n"
        "first = dict(probe.patch_execution_device())\n"
        "second = probe.patch_execution_device()\n"
        "from cells.execution import devices\n"
        "from cells.definitions.specs import parse_spec\n"
        "from cells.execution.state import initialise\n"
        "from cells.numerics import surface_imex as imex\n"
        "from validation.tissue import surface_pump_fixtures as fx\n"
        "kept = [n for n, m in sys.modules.items()\n"
        "        if getattr(getattr(m, 'execution_device', None), '__name__', '') "
        "== 'execution_device']\n"
        "bound = sorted(n for n, m in sys.modules.items()\n"
        "               if getattr(m, 'execution_device', None) is devices.execution_device)\n"
        "raw = fx.definition('clamped', backend='gpu', solver=imex.ARS222_ID)\n"
        "start = initialise(parse_spec(raw))  # Imports execution_device inside the function.\n"
        "placed = sorted({d.platform for v in start.state for d in v.devices()})\n"
        "print(json.dumps(dict(first=first, same=first == second, kept=kept, bound=bound,\n"
        "                      placed=placed)))\n"
    )
    done = subprocess.run(
        [sys.executable, "-B", "-c", code],
        env={
            "PYTHONPATH": f"{root / 'src'}:{root}",
            "PATH": "/usr/bin:/bin",
            "JAX_PLATFORMS": "cpu",
            "CUDA_VISIBLE_DEVICES": "",
        },
        capture_output=True,
        text=True,
        check=True,
    )
    found = json.loads(done.stdout.strip().splitlines()[-1])
    assert found["same"] and found["kept"] == [] and found["placed"] == ["cpu"]
    path_modules = {
        "cells.execution.devices",
        "cells.execution.runner",
        "cells.execution.batch",
        "cells.execution.batch_windows",
        "cells.execution.vector_windows",
        "cells.records.io",
    }
    assert path_modules <= set(found["bound"])
    assert found["first"] == {
        "backend": "gpu",
        "patched": True,
        "probe_device": "cpu",
        "modules_patched": found["first"]["modules_patched"],
        "lowering_platforms": ["cpu", "cuda"],
    }
    assert found["first"]["modules_patched"] >= len(path_modules)
    continuity._device_patch(found["first"])  # The note parse_record accepts.
