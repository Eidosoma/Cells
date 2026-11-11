"""Guard (a) of design §3.7: the empty composition equals resolved_pump_tissue@3, bitwise.

On the heredity cell (H and D) and the seven-cell gated held-bath sheet with IMEX
Euler and ARS(2,2,2) at 1 ms over a horizon with a NaV1.2 and a Na/K pump
schedule change, @3's padded reference world (finite outside nodes, faces, Ca
pumps, a gauge and a channel release), an RK4 world, uncompiled, and as a vmap
batch: every state field, observation column and max_ diagnostic equals @3's run
(np.array_equal, as the frozen equivalence tests compare). Restart from a
checkpoint is bitwise. The run manifest and summary carry the run identity.
"""

import json

import jax
import numpy as np
import pytest

from cells.core import pump_composite_spec as cs
from cells.core.batch import BatchSpec, WorldSpec
from cells.core.runner import run
from cells.core.specs import parse_spec
from cells.core.vector_windows import run_vector_windowed
from cells.core.windows import WindowPolicy
from cells.io import load_snapshot, write_run, write_snapshot
from cells.numerics import surface_imex as imex
from validation.tissue import cell_replacement_fixtures as rfx
from validation.tissue import composite_guard as guard
from validation.tissue import pump_water_fixtures as wfx
from validation.tissue import surface_pump_v3_fixtures as v3fx

WORLDS = {
    "cell_H": lambda **k: wfx.heredity_cell("H", **k),
    "cell_D": lambda **k: wfx.heredity_cell("D", **k),
    "sheet7": wfx.gated_sheet,
}


@pytest.fixture(scope="module", autouse=True)
def x64():
    jax.config.update("jax_enable_x64", True)


def pair(raw):
    return parse_spec(raw), parse_spec(cs.frozen_definition(raw))


def scheduled(world, solver, *, end=0.3, changes=((0.1, 0.5), (0.2, 0.8)), jit=True):
    raw = WORLDS[world](dt=1e-3, end_time=end, solver=solver)
    raw = wfx.scheduled(raw, channel_change=changes[0], pump_change=changes[1])
    raw["experiment"]["observation_times"] = [0.0, round(end / 3, 3), round(end / 2, 3), end]
    raw["execution"]["jit"] = jit
    return raw


@pytest.mark.parametrize("solver", (imex.EULER_ID, imex.ARS222_ID))
@pytest.mark.parametrize("world", WORLDS)
def test_empty_composition_is_resolved_pump_tissue_3_compiled(world, solver):
    reference, composite = pair(scheduled(world, solver))
    guard.assert_same(run(reference), run(composite))


def test_empty_composition_uncompiled():
    raw = scheduled(
        "sheet7", imex.ARS222_ID, end=0.012, changes=((0.004, 0.5), (0.007, 0.8)), jit=False
    )
    reference, composite = pair(raw)
    guard.assert_same(run(reference), run(composite))


def test_empty_composition_on_wider_worlds():
    raw = v3fx.definition("release", solver=imex.ARS222_ID)
    raw["experiment"]["end_time"] = 0.0012
    raw["experiment"]["observation_times"] = [0.0, 0.0007, 0.0012]
    reference, composite = pair(raw)
    guard.assert_same(run(reference), run(composite))
    raw = rfx.heredity_sheet(1, 0, dt=2.5e-6, end_time=40 * 2.5e-6, solver="rk4")
    raw["experiment"]["observation_times"] = [0.0, 20 * 2.5e-6, 40 * 2.5e-6]
    reference, composite = pair(raw)
    guard.assert_same(run(reference), run(composite))


def batch(specs):
    worlds = tuple(WorldSpec(i + 1, s) for i, s in enumerate(specs))
    return BatchSpec(worlds, len(worlds), 10**6, 2**31)


def test_empty_composition_vmap_batch_and_restart(tmp_path):
    references, composites = [], []
    for i, world in enumerate(("cell_H", "cell_D", "cell_H")):
        raw = WORLDS[world](dt=1e-3, end_time=0.1, solver=imex.ARS222_ID)
        raw = wfx.scheduled(raw, channel_change=(0.03, 0.5 + 0.1 * i), pump_change=(0.06, 0.8))
        raw["experiment"]["observation_times"] = [0.0, 0.05, 0.1]
        for c in raw["model"]["channels"]:
            c["max_permeability_m_per_s"] *= 1 + 0.05 * i
        a, b = pair(raw)
        references.append(a)
        composites.append(b)
    policy = WindowPolicy(40, "checkpoints")
    a = run_vector_windowed(batch(references), policy)
    b = run_vector_windowed(batch(composites), policy)
    for world in a.worlds:
        reference, result = a.worlds[world].final.state, b.worlds[world].final.state
        for key in type(reference)._fields:
            assert guard.compare_arrays(key, getattr(reference, key), getattr(result, key)) is None
        for key, value in a.worlds[world].diagnostics.items():
            if key.startswith("max_"):
                assert b.worlds[world].diagnostics[key] == value, (world, key)
    # Restart from a checkpoint is bitwise, and the run artifacts carry the identity.
    value = run(composites[1])
    checkpoint = value.checkpoint_at(0.05)
    write_snapshot(tmp_path / "checkpoint", value.spec, checkpoint)
    loaded = load_snapshot(tmp_path / "checkpoint")
    resumed = run(loaded.spec, loaded.checkpoint)
    for x, y in zip(resumed.history, value.history, strict=True):
        assert np.array_equal(np.asarray(x), np.asarray(y)[checkpoint.step_index :])
    summary = write_run(tmp_path / "run", value)
    manifest = json.loads((tmp_path / "run" / "manifest.json").read_text())
    identity = dict(model=cs.MODEL_ID, inner_model="resolved_pump_tissue@3", operators=[])
    assert manifest["composition"] == identity
    assert summary["composition"] == identity
    assert summary["composition_status"] == cs.DEVELOPMENT_STATUS
