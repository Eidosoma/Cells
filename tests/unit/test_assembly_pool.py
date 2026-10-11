"""Independent reaction histories, material conservation and complete replay."""

import json
import os
from dataclasses import replace

import jax
import numpy as np
import pytest

from cells.assembly.engine import device_for
from cells.assembly.graph import EDGES, FULL
from cells.assembly.kernel import random_pair
from cells.assembly.spec import AssemblyError
from cells.assembly_pool import reference
from cells.assembly_pool.engine import initial_state, run, validate_state
from cells.assembly_pool.io import load_checkpoint, write_checkpoint
from cells.assembly_pool.spec import FULL_BONDS, parse_spec

BACKEND = os.environ.get("CELLS_POOL_TEST_BACKEND", "cpu")


def assert_same(a, b):
    for name, x, y in zip(a._fields, a, b, strict=True):
        assert np.asarray(x).tobytes() == np.asarray(y).tobytes(), name


def test_independent_event_histories():
    spec = parse_spec(
        {
            "worlds": 8,
            "end_time_s": 2.0,
            "recording": "events",
            "max_events_per_world": 3000,
            "event_chunk_size": 32,
            "k_on_M_inv_s": 1e9,
            "initial_free_trimers": 15,
            "k_fragment_dissolve_s_inv": 20.0,
        }
    )
    chunks = []
    state, result = run(
        spec,
        backend=BACKEND,
        callback=lambda _, s, t: chunks.append(tuple(np.asarray(x) for x in t)),
    )
    traces = [np.concatenate([chunk[j] for chunk in chunks]) for j in range(5)]
    assert all(value > 0 for value in result["reaction_counts"].values())
    device = device_for("cpu")
    for world in range(spec.worlds):
        count = int(state.event_count[world])
        with jax.default_device(device):
            variates = jax.vmap(
                lambda event, world=world: random_pair(
                    np.uint32(spec.seed), np.uint32(world), event
                )
            )(np.arange(count + 1, dtype=np.uint32))
        expected = reference.trajectory(spec, np.asarray(variates))
        observed = [x[:, world][traces[4][:, world] >= 0] for x in traces]
        assert len(expected) == count
        for j, column in enumerate(observed):
            target = [row[j] for row in expected]
            if j == 0:
                np.testing.assert_allclose(column, target, rtol=2e-12, atol=2e-14)
            else:
                np.testing.assert_array_equal(column, target)
        np.testing.assert_array_equal(state.fragments[world], expected[-1][5])
        assert state.removed[world] == sum(row[7] for row in expected)
        assert (
            state.free[world]
            + int(state.occupied[world]).bit_count()
            + sum(i * int(n) for i, n in enumerate(state.fragments[world]))
            == spec.total_trimers
        )


def test_cycles_break_and_full_cage_is_not_absorbing():
    fragments = [0] * 21
    cut = reference.transition(FULL, FULL_BONDS, 0, fragments, 30, 10)
    assert cut[:3] == (FULL, FULL_BONDS ^ 1, 0)
    assert cut[5] == 0
    spec = parse_spec(
        {
            "initial_nodes": list(range(20)),
            "initial_free_trimers": 0,
            "worlds": 8,
            "end_time_s": 0.1,
            "k_close_s_inv": 0.0,
        }
    )
    state, result = run(spec, backend=BACKEND)
    assert np.all(state.event_count > 0)
    assert np.all(state.bonds != FULL_BONDS)
    assert np.all(state.full_first_s == 0)
    assert result["ever_full_cages"] == 8 and result["currently_full_cages"] == 0
    assert 0 < result["full_cage_dwell_total_s"] < 0.8


def test_fragments_return_exact_material():
    # Root--0--1--2--3: cutting the root spoke releases one four-trimer fragment.
    spec = parse_spec({"initial_nodes": [10, 0, 1, 2, 3], "initial_free_trimers": 0})
    cut = 30 + EDGES.index((0, 10))
    a = reference.transition(spec.initial_mask, spec.initial_bonds, 0, [0] * 21, cut, 10)
    assert a[0] == 1 << 10 and a[2] == 0 and a[3][4] == 1 and a[5] == 4
    b = reference.transition(*a[:4], 58 + 4, 10)
    assert b[2] == 4 and sum(b[3]) == 0


def test_pool_depletion_and_zero_rate_clock():
    spec = parse_spec(
        {
            "initial_nodes": [10],
            "worlds": 8,
            "initial_free_trimers": 2,
            "k_on_M_inv_s": 1e10,
            "k_off_s_inv": 0.0,
            "end_time_s": 2.0,
        }
    )
    state, _ = run(spec, backend=BACKEND)
    assert np.all(state.free == 0)
    assert np.all(np.bitwise_count(state.occupied) == 3)
    assert np.all(np.isinf(state.pending_time_s)) and np.all(state.pending_event == -1)
    spec = replace(spec, initial_free_trimers=0)
    state, _ = run(spec, backend=BACKEND)
    assert np.all(state.event_count == 0) and np.all(state.time_s == 2.0)


def test_pending_checkpoint_partition_and_chunk_replay(tmp_path):
    spec = parse_spec({"worlds": 8, "end_time_s": 0.8, "k_fragment_dissolve_s_inv": 20.0})
    whole, _ = run(spec, backend=BACKEND)
    part, _ = run(spec, backend=BACKEND, until=0.237)
    assert np.all(part.pending_valid)
    checkpoint = tmp_path / "checkpoint"
    write_checkpoint(checkpoint, spec, part, execution={"backend": BACKEND})
    saved, restored, _ = load_checkpoint(checkpoint)
    assert_same(part, restored)
    resumed, _ = run(saved, backend=BACKEND, state=restored)
    assert_same(whole, resumed)
    rechunked, _ = run(replace(spec, event_chunk_size=19), backend=BACKEND)
    assert_same(whole, rechunked)
    halves = [run(replace(spec, worlds=4, world_id_start=i), backend=BACKEND)[0] for i in (0, 4)]
    combined = type(whole)(*(np.concatenate((a, b)) for a, b in zip(*halves, strict=True)))
    assert_same(whole, combined)
    payload = checkpoint / "state.npz"
    data = bytearray(payload.read_bytes())
    data[50] ^= 1
    payload.write_bytes(data)
    with pytest.raises(AssemblyError, match="state_sha256"):
        load_checkpoint(checkpoint)


@pytest.mark.parametrize(
    "field", ["free", "fragments", "bonds", "reaction_counts", "pending_event"]
)
def test_corrupt_state_rejected(field):
    spec = parse_spec({"worlds": 1})
    state = initial_state(spec)
    value = getattr(state, field).copy()
    if field == "fragments":
        value[0, 2] = 1
    elif field == "reaction_counts":
        value[0, 0] = 1
    elif field == "bonds":
        value[0] = FULL_BONDS
    else:
        value[0] += 1
    with pytest.raises(AssemblyError):
        validate_state(spec, state._replace(**{field: value}))


@pytest.mark.parametrize(
    "changes",
    [
        {"initial_free_trimers": -1},
        {"initial_free_trimers": True},
        {"pool_volume_L": 0},
        {"k_close_s_inv": float("nan")},
        {"k_fragment_dissolve_s_inv": 1e14},
        {"initial_bond_indices": []},
        {"initial_bond_indices": [0]},
        {"worlds": 1000000},
        {"recording": "events", "max_output_bytes": 1024**2},
    ],
)
def test_invalid_definitions(changes):
    with pytest.raises(AssemblyError):
        parse_spec(changes)


def test_fault_evidence_reaches_callback():
    spec = parse_spec({"worlds": 8, "max_events_per_world": 1, "end_time_s": 2.0})
    evidence = []
    with pytest.raises(AssemblyError, match="fault"):
        run(spec, backend=BACKEND, callback=lambda _, state, trace: evidence.append(state))
    assert any(np.any(state.fault == 2) for state in evidence)


def test_public_cli_run_and_resume(tmp_path, capsys):
    from cells.__main__ import main

    spec = parse_spec({"worlds": 8, "end_time_s": 0.5})
    config = tmp_path / "pool.json"
    config.write_text(json.dumps(spec.to_dict()))
    assert main(["assembly-pool", "validate", str(config)]) == 0
    first, second = tmp_path / "first", tmp_path / "second"
    assert (
        main(
            [
                "assembly-pool",
                "run",
                str(config),
                "--backend",
                BACKEND,
                "--output",
                str(first),
                "--until",
                "0.123",
            ]
        )
        == 0
    )
    assert (first / "completion.json").exists()
    assert (
        main(
            [
                "assembly-pool",
                "resume",
                str(first / "checkpoint"),
                "--backend",
                BACKEND,
                "--output",
                str(second),
            ]
        )
        == 0
    )
    assert (second / "completion.json").exists()
    _, restored, _ = load_checkpoint(second / "checkpoint")
    whole, _ = run(spec, backend=BACKEND)
    assert_same(restored, whole)
    assert main(["assembly-pool", "run", str(config), "--output", str(first)]) == 2
    capsys.readouterr()


@pytest.mark.skipif(BACKEND != "gpu", reason="Explicit real-GPU qualification only")
def test_cpu_gpu_agreement():
    spec = parse_spec({"worlds": 48, "end_time_s": 1.0, "k_fragment_dissolve_s_inv": 20.0})
    cpu, _ = run(spec, backend="cpu")
    gpu, result = run(spec, backend="gpu")
    assert result["backend"] == "gpu"
    for name, a, b in zip(cpu._fields, cpu, gpu, strict=True):
        if a.dtype.kind == "f":
            np.testing.assert_allclose(a, b, rtol=2e-12, atol=2e-14, err_msg=name)
        else:
            np.testing.assert_array_equal(a, b, err_msg=name)
