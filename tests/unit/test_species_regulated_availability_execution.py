"""cells.operator.species_regulated_availability@1: execution guards on the moving world (tier 3).

docs/INVENTORY_COUPLING_DESIGN.md §1.9 and §4.4 A8. Four compiled programs on the sheet's moving
world (regulated_availability_fixtures.dynamic_world: R cleared and dosed in cell_0, a state of Na
with a crossing level, a switched-off interval, a write placed before the dose), so this file is
deliberately tier 3 (the lead's ruling, 14 November 2026), beside _guards:
* **vmap batches (§1.9).** Three moving worlds of one signature, with every parameter, s0, θ, the
  dose, the switch and the write varied, in one batch: each world's final state is its own
  windowed run's (floats within 1e-12, integers exact), the batch in reverse order is bitwise the
  same, and two worlds differing only in one factor parameter differ in junction_0's transfer.
* **Windows against one scan.** The moving world run in 4-step windows is bitwise its one-scan run.
* **A snapshot in a fresh process (A8).** Resumed from a written snapshot in a new interpreter
  (D152's pattern), it is bitwise the uninterrupted run.
"""

import numpy as np

from cells.definitions.cell_replacement_spec import exact_event_times
from cells.definitions.specs import parse_spec
from cells.execution.batch import BatchSpec, WorldSpec
from cells.execution.runner import run
from cells.execution.vector_windows import run_vector_windowed
from cells.execution.windows import WindowPolicy, run_windowed
from validation.tissue import regulated_availability_fixtures as rf

# ------------------------------------------------------------------ the moving world


DYNAMIC_END = 0.03
STEPS = round(DYNAMIC_END / 1e-3)
FRESH = """
import json, sys
import jax
jax.config.update("jax_enable_x64", True)
import numpy as np
from cells.execution.runner import run
from cells.records.io import load_snapshot
loaded = load_snapshot(sys.argv[1])
result = run(loaded.spec, loaded.checkpoint)
np.savez(sys.argv[2], **{k: np.asarray(v) for k, v in result.history._asdict().items()})
print(json.dumps(dict(start=int(loaded.checkpoint.step_index))))
"""


def grid(*steps):
    return exact_event_times(steps, 1e-3)


VARIANTS = [
    dict(),
    dict(half_saturation=2e-3),  # One factor parameter only: the batch must see it.
    dict(
        clearance=30.0,
        dose=(grid(14)[0], 0.5),
        coefficient=2.0,
        basal=0.1,
        on=8.0,
        off=2.0,
        s0=(0.4, 0.1),
        level=0.3,
        write=(grid(8)[0], 0.8),
        switch=grid(6, 18),
    ),
]
POLICY = WindowPolicy(4, "checkpoints")


def test_a_vector_batch_reproduces_each_worlds_own_run():
    """Three moving worlds of one signature (regulated_availability_fixtures.dynamic_world), every
    parameter, s0, θ, the dose, the switch and the write varied: each world's final state is its own
    windowed run's (floats within 1e-12, integers exact), the reversed batch is bitwise the same,
    and the two worlds that differ only in c_r's half-saturation differ in junction_0's transfer."""
    specs = [parse_spec(rf.dynamic_world(end=DYNAMIC_END, **v)) for v in VARIANTS]

    def batch(order):
        worlds = tuple(WorldSpec(i + 1, specs[j]) for i, j in enumerate(order))
        return run_vector_windowed(BatchSpec(worlds, len(worlds), 10**6, 2**31), POLICY)

    forward, backward = batch([0, 1, 2]), batch([2, 1, 0])
    finals = [forward.worlds[k + 1].final.state for k in range(3)]
    for k, spec in enumerate(specs):
        for a, b in zip(finals[k], backward.worlds[3 - k].final.state, strict=True):
            assert np.asarray(a).tobytes() == np.asarray(b).tobytes(), k
        own = run_windowed(spec, POLICY).final.state
        for name, a, b in zip(type(own)._fields, finals[k], own, strict=True):
            a, b = np.asarray(a), np.asarray(b)
            assert a.shape == b.shape and a.dtype == b.dtype, (k, name)
            if a.dtype.kind != "f":
                assert a.tobytes() == b.tobytes(), (k, name)
                continue
            scale = float(np.max(np.abs(b), initial=0.0))
            assert float(np.max(np.abs(a - b), initial=0.0)) <= 1e-12 * scale + 1e-30, (k, name)
    j0 = [j.id for j in specs[0].model.junctions].index("junction_0")
    first, second = (np.asarray(f.junction_transferred)[:, j0] for f in finals[:2])
    assert first.tobytes() != second.tobytes()  # The factor reaches @3 in the batch.
    assert [list(np.asarray(f.regulatory_writes_applied)) for f in finals] == [[0, 1]] * 3
    assert {int(np.asarray(f.coupling_step_count)[0]) for f in finals} == {STEPS}


def test_windowed_and_unwindowed_runs_agree_bit_for_bit():
    """The moving world run in one scan and in 4-step windows (which do not divide 30)."""
    from cells.execution.windows import iter_windows

    spec = parse_spec(rf.dynamic_world(end=DYNAMIC_END))
    whole = run(spec)
    rows = {}
    for window in iter_windows(spec, WindowPolicy(4, "full")):
        for i, _ in enumerate(np.asarray(window.times)):
            rows[window.start_step + i] = [np.asarray(v)[i] for v in window.history]
    assert sorted(rows) == list(range(STEPS + 1))
    for step, row in rows.items():
        for name, a, b in zip(type(whole.history)._fields, row, whole.history, strict=True):
            assert a.tobytes() == np.asarray(b)[step].tobytes(), (step, name)


def test_a_snapshot_resumed_in_a_fresh_process_is_bitwise(tmp_path):
    """A8 through a fresh process (D152's pattern): the checkpoint between the write and the dose,
    written, read back by load_snapshot in a new interpreter and run to the end."""
    import json
    import os
    import subprocess
    import sys
    from pathlib import Path

    from cells.records.io import write_snapshot

    root = Path(__file__).resolve().parents[2]
    spec = parse_spec(rf.dynamic_world(end=DYNAMIC_END))
    result = run(spec)
    times = np.asarray(result.times)
    checkpoint = result.checkpoint_at(float(times[np.argmin(np.abs(times - 0.011))]))
    write_snapshot(tmp_path / "checkpoint", result.spec, checkpoint)
    env = dict(
        os.environ,
        PYTHONPATH=os.pathsep.join([str(root / "src"), str(root)]),
        JAX_ENABLE_X64="1",
        JAX_PLATFORMS="cpu",
    )
    done = subprocess.run(
        [sys.executable, "-B", "-c", FRESH, str(tmp_path / "checkpoint"), str(tmp_path / "h.npz")],
        env=env,
        capture_output=True,
        text=True,
        timeout=900,
        check=False,
    )
    assert done.returncode == 0, done.stderr[-2000:]
    start = json.loads(done.stdout.strip().splitlines()[-1])["start"]
    assert start == checkpoint.step_index
    fresh = np.load(tmp_path / "h.npz")
    for name, value in result.history._asdict().items():
        expected = np.asarray(value)[start:]
        assert fresh[name].dtype == expected.dtype, name
        assert fresh[name].tobytes() == expected.tobytes(), name
