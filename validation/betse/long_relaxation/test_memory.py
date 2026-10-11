"""Bounded checksums, exact inline buffers and ordinary checkpoint compatibility."""

import copy
import hashlib
import importlib.util
import json
import struct
import subprocess
import sys
import tracemalloc
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location(
    "memory_evidence", HERE.parent / "pump_loop_audit/evidence.py"
)
e = importlib.util.module_from_spec(spec)
spec.loader.exec_module(e)


def array(values, shape):
    return dict(
        dtype="<f8",
        shape=shape,
        values=values,
        bytes_sha256=hashlib.sha256(
            b"".join(struct.pack("<d", v) for v in e.flat(values))
        ).hexdigest(),
    )


@pytest.mark.parametrize(
    "values,shape",
    [
        ([], [0]),
        ([[]], [1, 0]),
        ([-0.0], [1]),
        ([[1.0, -0.0], [1e-300, -1e300]], [2, 2]),
        (list(range(20000)), [20000]),
    ],
)
def test_history_checksum_preserves_bytes_and_original_return(values, shape):
    record = array(values, shape)
    original = copy.deepcopy(record)
    assert e.array(record) is values
    assert record == original


@pytest.mark.parametrize("change", ["signed_zero", "shape", "digest", "nan", "dtype"])
def test_history_checksum_retains_rejection(change):
    record = array([[-0.0, 2.0]], [1, 2])
    if change == "signed_zero":
        record["values"][0][0] = 0.0
    elif change == "shape":
        record["shape"] = [2, 1]
    elif change == "digest":
        record["bytes_sha256"] = "0" * 64
    elif change == "nan":
        record["values"][0][1] = float("nan")
    else:
        record["dtype"] = "<f4"
    with pytest.raises(ValueError):
        e.array(record)


def test_history_checksum_temporary_memory_is_bounded():
    record = array([0.125] * 400000, [400000])
    tracemalloc.start()
    try:
        e.array(record)
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    assert peak < 1024**2


@pytest.mark.parametrize("change", [None, "value", "zero", "alias", "shape", "dtype"])
def test_checkpoint_graph_checks_values_and_shared_state(change):
    import numpy as np
    from memory_native import compare_graph

    original = dict(a=np.array([[-0.0, 1.0]]))
    original["b"] = original["a"]
    original["cycle"] = original
    restored = copy.deepcopy(original)
    if change == "value":
        restored["a"][0, 1] += 1.0
    elif change == "zero":
        restored["a"][0, 0] = 0.0
    elif change == "alias":
        restored["b"] = restored["b"].copy()
    elif change == "shape":
        restored["a"] = restored["a"].reshape(2)
    elif change == "dtype":
        restored["a"] = restored["a"].astype(np.float32)
    if change is None:
        assert compare_graph(original, restored)["values_and_aliases_exact"]
    else:
        with pytest.raises(ValueError):
            compare_graph(original, restored)


@pytest.mark.parametrize("target", ["/new/INITS/a.gz", "/new/INITS/b.gz", "/elsewhere/INITS/a.gz"])
def test_checkpoint_relocation_preserves_relative_path(target):
    from memory_native import compare_graph

    if target == "/new/INITS/a.gz":
        assert (
            compare_graph(
                {"path": "/old/INITS/a.gz"}, {"path": target}, relocated_roots=("/old", "/new")
            )["relocated_paths"]
            == 1
        )
    else:
        with pytest.raises(ValueError):
            compare_graph(
                {"path": "/old/INITS/a.gz"}, {"path": target}, relocated_roots=("/old", "/new")
            )


@pytest.mark.parametrize("failure", [None, "memory", "disk"])
def test_memory_job_keeps_resource_reserve_and_failure_evidence(tmp_path, monkeypatch, failure):
    from types import SimpleNamespace

    import memory_job as job

    gib = 1024**3
    monkeypatch.setattr(
        job.pilot, "available_memory", lambda: (19 if failure == "memory" else 25) * gib
    )
    monkeypatch.setattr(
        job.shutil,
        "disk_usage",
        lambda _: SimpleNamespace(free=(9 if failure == "disk" else 12) * gib),
    )
    if failure is None:
        assert job.resource_check(tmp_path, "capacity")["passed"]
    else:
        with pytest.raises(ValueError, match="memory/disk reserve"):
            job.resource_check(tmp_path, "capacity")
        assert not json.loads((tmp_path / "resource-capacity.json").read_text())["passed"]


@pytest.mark.parametrize(
    "field", ["duration_s", "dt_s", "steps", "capacity_steps", "checkpoint_mode", "protocol"]
)
def test_memory_job_rejects_clock_writer_or_tolerance_changes(field):
    import memory_job as job

    r = dict(
        duration_s=job.DURATION,
        dt_s=job.DT,
        steps=job.STEPS,
        capacity_steps=job.CAPACITY_STEPS,
        checkpoint_mode=job.MODE,
        protocol=job.u.plan(),
    )
    job.controls(r)
    r[field] = None
    with pytest.raises(ValueError):
        job.controls(r)


@pytest.mark.parametrize("timeout", [False, True])
def test_memory_job_stops_on_worker_failure_and_preserves_partial_evidence(
    tmp_path, monkeypatch, timeout
):
    import memory_job as job

    job.u.write(tmp_path / "registration.json", dict(workspace=str(tmp_path)))
    monkeypatch.setattr(job, "resource_check", lambda root, phase: None)
    calls = []

    def failed_worker(argv, **kwargs):
        calls.append(argv[-1])
        directory = tmp_path / argv[-1]
        directory.mkdir()
        (directory / "partial.bin").write_bytes(b"preserve")
        if timeout:
            raise subprocess.TimeoutExpired(argv, kwargs["timeout"])
        raise subprocess.CalledProcessError(1, argv)

    monkeypatch.setattr(job.subprocess, "run", failed_worker)
    with pytest.raises((subprocess.TimeoutExpired, subprocess.CalledProcessError)):
        job.controller(tmp_path)
    assert calls == ["regression"]
    assert (tmp_path / "regression/partial.bin").read_bytes() == b"preserve"
    failure = job.u.read(tmp_path / "failure.json")
    assert failure["phase"] == "regression" and not failure["automatic_retry"]
    assert job.u.read(tmp_path / "regression/failure.json") == failure
    assert not (tmp_path / "completion.json").exists()


def test_inline_pickle_arrays_aliases_cycles_and_global_restoration(tmp_path):
    script = r"""
import sys, json
from pathlib import Path
sys.path.insert(0, sys.argv[1])
import numpy as np
import dill
from betse.lib.pickle import pickles
pickles.init()
from pickle_buffers import inline_arrays
root = Path(sys.argv[2])
base = np.arange(64, dtype=np.float64).reshape(8,8)
readonly = base.copy(); readonly.flags.writeable = False
payload = [base, base, np.asfortranarray(base), base[:,::2], readonly,
    np.array([-0.0, np.nextafter(0.,1.)]), np.arange(40000,dtype=np.float64),
    np.array(1.5), np.array([{'x':1}],dtype=object), np.array([],dtype=np.float64)]
payload.append(payload)
old_class, old_protocol = dill._dill.Pickler, pickles.PROTOCOL
with inline_arrays() as facts:
    pickles.save(payload, filename=str(root/'inline.betse.gz'))
assert facts['globals_restored'] and facts['inline_buffers'] == 7
assert dill._dill.Pickler is old_class and pickles.PROTOCOL == old_protocol
out = pickles.load(str(root/'inline.betse.gz'))
assert out[0] is out[1] and out[-1] is out
for a,b in zip(payload[:-1],out[:-1],strict=True):
    assert type(a) is type(b) and a.dtype == b.dtype and a.shape == b.shape
    if a.dtype.hasobject: assert a.tolist() == b.tolist()
    else: assert a.tobytes() == b.tobytes()
assert not out[4].flags.writeable and out[2].flags.f_contiguous
try:
    with inline_arrays() as aborted:
        raise RuntimeError('intentional')
except RuntimeError: pass
assert aborted['globals_restored'] and dill._dill.Pickler is old_class
assert pickles.PROTOCOL == old_protocol
with inline_arrays():
    try:
        with inline_arrays(): pass
    except ValueError: pass
    else: raise AssertionError('Nested writer accepted')
print(json.dumps(facts))
"""
    result = subprocess.run(
        [
            "/mnt/workspaces/Cells/venv-betse/bin/python",
            "-B",
            "-c",
            script,
            str(HERE),
            str(tmp_path),
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    assert not result.stderr
    facts = json.loads(result.stdout)
    assert facts["external_buffers"] == 0 and facts["inline_bytes"] > 320000


def test_inline_capture_is_initialized_in_a_fresh_native_process(tmp_path):
    script = r"""
import sys,json
from pathlib import Path
sys.path.insert(0,sys.argv[1])
import memory_job as job
import prepare
u=job.u
w=Path('/mnt/workspaces/Cells')
p=u.read(w/'ref-005e-fresh-20260919-01/prepare/preparation.json')
result=prepare.capture(Path(sys.argv[2])/'capture',w,p,'pump_leak',None,'observed',
    8*job.DT,dt_s=job.DT,checkpoint_mode=job.MODE)
assert result['steps'] == 8
assert result['checkpoint_storage']['inline_buffers'] > 0
assert result['checkpoint_storage']['globals_restored']
from betse.lib.pickle import pickles
assert pickles.PROTOCOL == 4
print(json.dumps(result['checkpoint_storage']))
"""
    result = subprocess.run(
        [
            "/mnt/workspaces/Cells/venv-betse/bin/python",
            "-B",
            "-c",
            script,
            str(HERE),
            str(tmp_path),
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    assert all(
        line.endswith(" Ignoring cutting event, as cut profiles are disabled.")
        for line in result.stderr.splitlines()
    )
    assert json.loads(result.stdout.splitlines()[-1])["external_buffers"] == 0


@pytest.mark.parametrize(
    "kwargs",
    [
        dict(dt_s=0.0, index=None),
        dict(dt_s=float("nan"), index=None),
        dict(dt_s=1e-7, index=2),
        dict(checkpoint_mode="unknown", index=2),
    ],
)
def test_capture_refuses_ambiguous_clock_or_writer_before_native_import(tmp_path, kwargs):
    sys.path.insert(0, str(HERE.parent / "fresh_rerun"))
    import prepare

    with pytest.raises(ValueError):
        prepare.capture(
            tmp_path / "out",
            tmp_path,
            {},
            "pump_leak",
            kwargs.pop("index"),
            "observed",
            0.01,
            **kwargs,
        )
