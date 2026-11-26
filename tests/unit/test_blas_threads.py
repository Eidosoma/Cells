"""One BLAS thread for every run (D190; execution/blas_threads.py).

`import cells` loads scipy's LAPACK (jaxlib's) and sets every loaded BLAS to 1 thread. Each run
entry point pins again and reads the count back, refusing the run if any loaded BLAS is not at 1,
which is the failure the read-back exists for: a library the limit does not reach. Planted here as
threadpoolctl reporting a library still at 4 threads after the entry's pin, it is refused at each
of the five run paths' entry points, before any work. The run manifest records each loaded
library's version, kernel architecture and thread count as threadpoolctl reads them: after a run,
both OpenBLAS builds at 1 thread, and a planted further library appears in the record, so the
record is read, not written from a fixed list.
"""

import json
from pathlib import Path

import pytest
import threadpoolctl

from cells.definitions.specs import ConfigError, load_spec
from cells.execution import blas_threads
from cells.execution.batch import BatchSpec, WorldSpec, run_batch
from cells.execution.batch_windows import iter_batch_windows, run_batch_windowed
from cells.execution.runner import run
from cells.execution.vector_windows import iter_vector_windows, run_vector_windowed
from cells.execution.windows import WindowPolicy, iter_windows, run_windowed
from cells.records.io import write_run

ROOT = Path(__file__).resolve().parents[2]
POLICY = WindowPolicy(5, "checkpoints")


def spec():
    return load_spec(ROOT / "configs/reaction_transport_single.json")


def batch():
    return BatchSpec((WorldSpec(1, spec()),), 1, 10**6, 2**31)


ENTRIES = {
    "run": lambda: run(spec()),
    "run_windowed": lambda: run_windowed(spec(), POLICY),
    "iter_windows": lambda: iter_windows(spec(), POLICY),
    "run_batch": lambda: run_batch(batch()),
    "run_batch_windowed": lambda: run_batch_windowed(batch(), POLICY),
    "iter_batch_windows": lambda: iter_batch_windows(batch(), POLICY),
    "run_vector_windowed": lambda: run_vector_windowed(batch(), POLICY),
    "iter_vector_windows": lambda: iter_vector_windows(batch(), POLICY),
}


def with_library(info, **planted):
    """threadpoolctl's info with one more BLAS library, `planted` over a copy of the first."""
    first = next(i for i in info if i.get("user_api") == "blas")
    return [*info, dict(first, prefix="planted", version="0.0.planted", **planted)]


@pytest.mark.parametrize("entry", ENTRIES)
def test_a_library_left_above_one_thread_after_the_pin_is_refused_at_entry(entry, monkeypatch):
    real = threadpoolctl.threadpool_info
    monkeypatch.setattr(
        threadpoolctl, "threadpool_info", lambda: with_library(real(), num_threads=4)
    )
    with pytest.raises(ConfigError, match=r"D190.*0\.0\.planted"):
        ENTRIES[entry]()
    monkeypatch.undo()
    assert all(lib["num_threads"] == 1 for lib in blas_threads.require_pinned(entry))


def test_the_run_manifest_records_each_library_as_read(tmp_path, monkeypatch):
    write_run(tmp_path / "run", run(spec()))
    record = json.loads((tmp_path / "run" / "manifest.json").read_text())["blas"]
    assert record["threadpoolctl"] == threadpoolctl.__version__
    libraries = record["libraries"]
    assert libraries == blas_threads.libraries() and len(libraries) >= 2  # numpy's and scipy's.
    for lib in libraries:
        assert lib["num_threads"] == 1 and lib["version"] and lib["architecture"], lib
    real = threadpoolctl.threadpool_info
    monkeypatch.setattr(
        threadpoolctl, "threadpool_info", lambda: with_library(real(), num_threads=1)
    )
    write_run(tmp_path / "planted", run(spec()))
    manifest = json.loads((tmp_path / "planted" / "manifest.json").read_text())
    versions = [lib["version"] for lib in manifest["blas"]["libraries"]]
    assert versions[-1] == "0.0.planted" and len(versions) == len(libraries) + 1
