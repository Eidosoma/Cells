"""The run view on the windowed paths (cells/run_view.py; window_io and batch_window_io).

* A windowed run's view names every chunk once per time base, from the run's index (requirement
  8: one entry per record, its base listing (file, rows)); the manifest covers view.json, and
  without view= the manifest's fixed inventory is unchanged.
* A recording subset keeps every n-th observation across window boundaries, as write_run does.
* A windowed batch writes one view per world, in worlds/world-<id>/, each covered by the
  manifest; a request that misses a world is refused before any output.

Declarations an operator does not carry yet are planted for a test's duration only.
"""

import json

import numpy as np
import pytest

from cells import run_view
from cells.batch_window_io import write_windowed_batch
from cells.core.windows import WindowPolicy
from cells.window_io import write_windowed_run
from tests.batch_fixtures import definition
from tests.run_view_fixtures import declare_secretion, load, secretion


@pytest.fixture
def declared(monkeypatch):
    declare_secretion(monkeypatch)


def chunk_names(root):
    return sorted(str(p.relative_to(root)) for p in (root / "chunks").glob("*.npz"))


def test_a_windowed_run_names_each_chunk_once_per_time_base(declared, tmp_path):
    spec = secretion()
    times = spec.experiment.observation_times
    keep = run_view.Recording(
        fields=("membrane_voltage_V", "amount", "exchange_moved_fmol"),
        elements={"species": ("S",), "membrane": ("contact_0",)},
        every=2,
    )
    runs = {
        "full": (WindowPolicy(3, "full"), run_view.Request()),
        "observations": (WindowPolicy(3, "observations"), run_view.Request()),
        "subset": (WindowPolicy(3, "full"), run_view.Request(recording=keep)),
    }
    for name, (policy, request) in runs.items():
        root = tmp_path / name
        write_windowed_run(root, spec, policy, view=request)
        view = load(root)
        run_view.validate(view, root)
        bases = {b["id"]: b for b in view["time"]["bases"]}
        assert set(bases) == (
            {"observation"} if policy.recording == "observations" else {"accepted", "observation"}
        )
        assert sorted({f["file"] for b in bases.values() for f in b["files"]}) == chunk_names(root)
        index = [json.loads(line) for line in (root / "windows.jsonl").read_text().splitlines()]
        counted = sum(e["observation_records"] for e in index if e["kind"] == "window")
        assert bases["observation"]["files"][-1]["rows"][1] == counted
        manifest = json.loads((root / "manifest.json").read_text())
        assert "view.json" in manifest["files_sha256"] and len(manifest["files_sha256"]) == 8
        assert view["recording"]["mode"] == policy.recording
    observed = np.concatenate(
        [
            np.load(tmp_path / "subset" / c)["observation_times"]
            for c in chunk_names(tmp_path / "subset")
        ]
    )
    np.testing.assert_array_equal(observed, times[::2])  # Across window boundaries.
    plain = tmp_path / "plain"
    write_windowed_run(plain, spec, WindowPolicy(3, "full"))
    assert not (plain / "view.json").exists()
    assert len(json.loads((plain / "manifest.json").read_text())["files_sha256"]) == 7
    # A saved windowed run gets the same view afterwards, but for the engine that ran it.
    run_view.write_view(plain, out=tmp_path / "later")
    later, full = load(tmp_path / "later"), load(tmp_path / "full")
    whys = []
    for each in (later, full):  # Each says why it names no engine source.
        (source,) = [u for u in each["unstated"] if u["id"] == "source"]
        each["unstated"].remove(source)
        whys.append(source["why"])
    assert later == full and whys[0] == "the view is written for a run already on disk"


def test_a_windowed_batch_writes_one_view_per_world(declared, tmp_path):
    specs = [secretion(produce=1e-4), secretion(produce=2e-4)]
    batch = definition(specs)
    with pytest.raises(run_view.ViewRefused, match="name every world once"):
        write_windowed_batch(tmp_path / "x", batch, WindowPolicy(4), view={10: run_view.Request()})
    assert not (tmp_path / "x").exists()
    write_windowed_batch(tmp_path / "wb", batch, WindowPolicy(4), view=run_view.Request())
    manifest = json.loads((tmp_path / "wb" / "manifest.json").read_text())
    for world, spec in zip((10, 11), specs, strict=True):
        folder = tmp_path / "wb" / "worlds" / f"world-{world}"
        view = load(folder)
        run_view.validate(view, folder)
        assert view["run"]["definition_sha256"] == spec.fingerprint
        files = {f["file"] for b in view["time"]["bases"] for f in b["files"]}
        assert files == set(chunk_names(folder))
        assert f"worlds/world-{world}/view.json" in manifest["files_sha256"]
