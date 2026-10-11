"""Event order, component independence, conservation and exact coupled restart."""

import json
import os
from dataclasses import replace
from pathlib import Path

import jax
import numpy as np
import pytest

from cells.assembly.engine import device_for
from cells.assembly.graph import OPEN_CHAIN
from cells.assembly.kernel import random_pair
from cells.assembly.spec import AssemblyError
from cells.assembly_cell import engine
from cells.assembly_cell.io import flatten, load_checkpoint, write_checkpoint
from cells.assembly_cell.spec import parse_spec
from cells.assembly_pool import reference
from cells.core.errors import NumericalError
from cells.core.schedule import PhysicalIonicGraphControl, control_values
from cells.models import kinetic_finite_extracellular as ionic

BACKEND = os.environ.get("CELLS_COUPLED_TEST_BACKEND", "cpu")
CONFIG = Path(__file__).resolve().parents[2] / "configs/assembly_regulated_cell.json"


def spec_for(**pool):
    raw = json.loads(CONFIG.read_text())
    raw["pool"].update(worlds=4, k_off_s_inv=300.0, k_close_s_inv=1000.0)
    raw["pool"].update(pool)
    return parse_spec(raw)


def same(a, b):
    for key, value in flatten(a).items():
        assert value.tobytes() == flatten(b)[key].tobytes(), key


def test_event_order_and_independent_ionic_reference():
    scipy = pytest.importorskip("scipy.integrate")
    spec = spec_for(worlds=2)
    state, result = engine.run(spec, backend=BACKEND)
    fine_spec = replace(
        spec,
        ionic=replace(
            spec.ionic, execution=replace(spec.ionic.execution, dt=spec.ionic.execution.dt / 2)
        ),
    )
    fine, _ = engine.run(fine_spec, backend=BACKEND)
    np.testing.assert_array_equal(state.pool.occupied, fine.pool.occupied)
    np.testing.assert_array_equal(state.pool.bonds, fine.pool.bonds)
    assert result["ionic_accounting"]["max_global_balance_error_fmol"] < 1e-13
    initial, layout = ionic.initial_values(spec.ionic)
    template = initial
    shapes, sizes = [v.shape for v in initial], [v.size for v in initial]
    cuts = np.cumsum([0, *sizes])

    def unpack(y):
        return type(template)(
            *(y[cuts[i] : cuts[i + 1]].reshape(shape) for i, shape in enumerate(shapes))
        )

    base = PhysicalIonicGraphControl(*(v[0] for v in control_values(spec.ionic, [0.0])))
    for world in range(spec.pool.worlds):
        count = int(state.pool.event_count[world])
        with jax.default_device(device_for("cpu")):
            randoms = np.asarray(
                jax.vmap(
                    lambda e, world=world: random_pair(
                        np.uint32(spec.pool.seed), np.uint32(world), e
                    )
                )(np.arange(count + 1, dtype=np.uint32))
            )
        events = reference.trajectory(spec.pool, randoms)
        assert len(events) == count
        mask, bonds = spec.pool.initial_mask, spec.pool.initial_bonds
        y = np.concatenate([v.ravel() for v in initial])
        previous, exposure = 0.0, 0.0
        for event in [*events, (spec.pool.end_time_s, mask, bonds)]:
            end = event[0]
            opening = (
                spec.active_availability
                if bonds.bit_count() >= mask.bit_count()
                else spec.inactive_availability
            )
            control = base._replace(channel=base.channel * opening)

            def rhs(_, value, control=control):
                return np.concatenate(
                    [
                        v.ravel()
                        for v in ionic.rhs(unpack(value), control, layout, layout.active, xp=np)
                    ]
                )

            solution = scipy.solve_ivp(
                rhs, (previous, end), y, method="DOP853", rtol=1e-11, atol=1e-14
            )
            assert solution.success
            y = solution.y[:, -1]
            exposure += opening * (end - previous)
            previous, mask, bonds = end, event[1], event[2]
        actual = np.concatenate([v[world].ravel() for v in state.ionic])
        np.testing.assert_allclose(actual, y, rtol=3e-9, atol=3e-12)
        refined = np.concatenate([v[world].ravel() for v in fine.ionic])
        assert np.max(np.abs(refined - y)) <= 0.5 * np.max(np.abs(actual - y)) + 1e-13
        assert state.availability_exposure_s[world] == pytest.approx(exposure, abs=2e-14)
        if events:
            assert state.pool.occupied[world] == events[-1][1]
            assert state.pool.bonds[world] == events[-1][2]
            assert state.pool.free[world] == events[-1][3]


def test_checkpoint_window_and_world_partition_replay(tmp_path):
    spec = spec_for()
    whole, _ = engine.run(spec, backend=BACKEND)
    first, _ = engine.run(spec, backend=BACKEND, until=0.0073)
    path = tmp_path / "coupled"
    write_checkpoint(path, spec, first, backend=BACKEND)
    saved, restored, _ = load_checkpoint(path, backend=BACKEND)
    same(first, restored)
    resumed, _ = engine.run(saved, backend=BACKEND, state=restored)
    same(whole, resumed)
    windows, _ = engine.run(replace(spec, window_ticks=7), backend=BACKEND)
    same(whole, windows)
    halves = [
        engine.run(
            replace(spec, pool=replace(spec.pool, worlds=2, world_id_start=i)), backend=BACKEND
        )[0]
        for i in (0, 2)
    ]
    same(whole, jax.tree.map(lambda a, b: np.concatenate((a, b)), *halves))
    with pytest.raises(AssemblyError, match="backend"):
        load_checkpoint(path, backend="gpu" if BACKEND == "cpu" else "cpu")


def test_organization_controls_availability_and_disable_is_effective():
    spec = spec_for(k_off_s_inv=0.0, k_on_M_inv_s=0.0, k_close_s_inv=0.0)
    ring, _ = engine.run(spec, backend=BACKEND)
    raw = spec.to_dict()
    raw["pool"].update(initial_nodes=list(OPEN_CHAIN), initial_bond_indices=None)
    opened, _ = engine.run(parse_spec(raw), backend=BACKEND)
    assert np.all(ring.availability_exposure_s > 0)
    assert np.all(opened.availability_exposure_s == 0)
    assert np.all(opened.ionic.channel_transferred == 0)
    assert np.all(np.abs(ring.ionic.channel_transferred[:, 0]) > 1e-10)
    assert np.all(ring.pool.free == opened.pool.free)
    disabled, _ = engine.run(replace(spec, active_availability=0.0), backend=BACKEND)
    for a, b in zip(disabled.ionic, opened.ionic, strict=True):
        np.testing.assert_array_equal(a, b)


def test_invalid_common_clock_and_corruption():
    spec = spec_for()
    with pytest.raises(AssemblyError, match="grid"):
        engine.run(spec, until=0.00013)
    initial = engine.initial_state(spec)
    with pytest.raises(AssemblyError, match="clocks"):
        engine.validate_state(spec, initial._replace(tick=np.ones(spec.pool.worlds, np.uint32)))
    corrupted = jax.tree.map(np.copy, initial)
    corrupted.ionic.extracellular_amount_increment[0, 0, 0] = 0.01
    with pytest.raises(NumericalError):
        engine.validate_state(spec, corrupted)


def test_public_cli_complete_world(tmp_path, capsys):
    from cells.__main__ import main

    spec = spec_for(worlds=2)
    config = tmp_path / "definition.json"
    config.write_text(json.dumps(spec.to_dict()))
    first, second = tmp_path / "first", tmp_path / "resumed"
    assert main(["assembly-cell", "validate", str(config)]) == 0
    assert (
        main(
            [
                "assembly-cell",
                "run",
                str(config),
                "--output",
                str(first),
                "--backend",
                BACKEND,
                "--until",
                "0.0001",
            ]
        )
        == 0
    )
    assert (first / "completion.json").exists()
    assert (
        main(
            [
                "assembly-cell",
                "resume",
                str(first / "checkpoint"),
                "--output",
                str(second),
                "--backend",
                BACKEND,
                "--until",
                "0.0002",
            ]
        )
        == 0
    )
    assert (second / "completion.json").exists()
    saved, state, _ = load_checkpoint(second / "checkpoint", backend=BACKEND)
    assert saved.fingerprint == spec.fingerprint and np.all(state.tick == 2)
    path = second / "checkpoint/state.npz"
    payload = bytearray(path.read_bytes())
    payload[50] ^= 1
    path.write_bytes(payload)
    with pytest.raises(AssemblyError, match="state_sha256"):
        load_checkpoint(second / "checkpoint", backend=BACKEND)
    capsys.readouterr()


@pytest.mark.skipif(BACKEND != "gpu", reason="Explicit real GPU check")
def test_cpu_gpu_composition_agreement():
    spec = spec_for()
    cpu, _ = engine.run(spec, backend="cpu")
    gpu, result = engine.run(spec, backend="gpu")
    assert result["device_kind"] == "NVIDIA L4" or result["backend"] == "gpu"
    for key, a in flatten(cpu).items():
        b = flatten(gpu)[key]
        if a.dtype.kind == "f":
            np.testing.assert_allclose(a, b, rtol=3e-10, atol=3e-13, err_msg=key)
        else:
            np.testing.assert_array_equal(a, b, err_msg=key)
