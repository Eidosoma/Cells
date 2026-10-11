"""Graph, stochastic-law, independent-oracle and complete-restart checks."""

import json
import math
import os
from dataclasses import replace

import jax
import numpy as np
import pytest

from cells.assembly.engine import device_for, initial_state, run, validate_state
from cells.assembly.graph import EDGES, FULL, NEIGHBORS, OPEN_CHAIN, RING, component, mask_of
from cells.assembly.io import digest, load_checkpoint, write_checkpoint
from cells.assembly.kernel import event_options, random_pair
from cells.assembly.reference import events, trajectory
from cells.assembly.spec import AssemblyError, parse_spec

BACKENDS = ("cpu", "gpu") if os.environ.get("CELLS_ASSEMBLY_TEST_GPU") == "1" else ("cpu",)


def test_dodecahedron_and_seed_geometry():
    assert len(EDGES) == 30 and len(set(EDGES)) == 30
    assert all(len(neighbors) == 3 for neighbors in NEIGHBORS)
    assert component(FULL, 10) == FULL
    cycles = set()
    for root in range(20):
        todo = [(root,)]
        while todo:
            path = todo.pop()
            for other in NEIGHBORS[path[-1]]:
                if other == root and len(path) >= 3:
                    assert len(path) >= 5
                    if len(path) == 5:
                        cycles.add(frozenset(path))
                if other not in path and len(path) < 5:
                    todo.append(path + (other,))
    assert len(cycles) == 12
    for nodes, forward, reverse in ((RING, 5, 0), (OPEN_CHAIN, 7, 4), ((10,), 3, 0)):
        rates, _ = events(mask_of(nodes), 10, 1.0, 1.0)
        assert np.count_nonzero(rates[:30]) == forward
        assert np.count_nonzero(rates[30:]) == reverse


@pytest.mark.parametrize(
    "patch",
    [
        {"model": "unknown"},
        {"topology": "arbitrary"},
        {"unknown": 1},
        {"worlds": True},
        {"worlds": 0},
        {"seed": -1},
        {"world_id_start": 2**32 - 1},
        {"initial_nodes": [10, 10]},
        {"initial_nodes": [10, 15]},
        {"initial_nodes": [1]},
        {"initial_nodes": [True, 10]},
        {"root_node": -1},
        {"free_trimer_M": math.nan},
        {"k_off_s_inv": -1},
        {"k_on_M_inv_s": math.inf},
        {"end_time_s": 0},
        {"max_events_per_world": 2**32},
        {"max_wall_seconds": 0},
        {"recording": "everything"},
        {"recording": "events", "worlds": 10000, "max_events_per_world": 100000},
    ],
)
def test_bad_definitions_refused(patch):
    with pytest.raises(AssemblyError):
        parse_spec(patch)


@pytest.mark.parametrize("backend", BACKENDS)
def test_device_graph_against_independent_bfs(backend):
    rng = np.random.default_rng(752)
    masks, roots = [], []
    for _ in range(256):
        root = int(rng.integers(20))
        nodes = {root}
        for _ in range(int(rng.integers(20))):
            frontier = sorted({n for node in nodes for n in NEIGHBORS[node]} - nodes)
            if frontier:
                nodes.add(int(rng.choice(frontier)))
        masks.append(mask_of(nodes))
        roots.append(root)
    args = jax.device_put(
        (np.array(masks, np.uint32), np.array(roots, np.uint32), 0.17, 10.0), device_for(backend)
    )
    kernel = jax.jit(jax.vmap(event_options, in_axes=(0, 0, None, None)))
    rates, targets, cumulative = map(np.asarray, kernel(*args))
    for row, (mask, root) in enumerate(zip(masks, roots, strict=True)):
        expected, expected_targets = events(mask, root, 0.17, 10.0)
        np.testing.assert_array_equal(rates[row], expected)
        np.testing.assert_array_equal(targets[row][expected > 0], expected_targets[expected > 0])
        np.testing.assert_allclose(cumulative[row], np.cumsum(expected), atol=1e-12, rtol=1e-14)


def common_variates(spec, world, count=512):
    device = device_for("cpu")
    args = jax.device_put(
        (np.uint32(spec.seed), np.uint32(world), np.arange(count, dtype=np.uint32)), device
    )
    return np.asarray(jax.jit(jax.vmap(random_pair, in_axes=(None, None, 0)))(*args))


@pytest.mark.parametrize("backend", BACKENDS)
def test_event_trajectories_against_scalar_oracle(backend):
    spec = parse_spec(
        {
            "worlds": 8,
            "initial_nodes": list(OPEN_CHAIN),
            "end_time_s": 3.0,
            "event_chunk_size": 32,
            "max_events_per_world": 512,
            "recording": "events",
        }
    )
    traces = []
    state, report = run(
        spec,
        backend=backend,
        callback=lambda _, __, trace: traces.append(tuple(map(np.asarray, trace))),
    )
    times, masks, choices = [np.concatenate([row[i] for row in traces]) for i in range(3)]
    for world in range(spec.worlds):
        expected = trajectory(spec, common_variates(spec, world))
        accepted = choices[:, world] >= 0
        assert accepted.sum() == state.event_count[world] == len(expected)
        np.testing.assert_allclose(
            times[accepted, world], [row[0] for row in expected], atol=2e-12, rtol=2e-13
        )
        np.testing.assert_array_equal(masks[accepted, world], [row[1] for row in expected])
        np.testing.assert_array_equal(choices[accepted, world], [row[2] for row in expected])
    assert report["faulted_worlds"] == 0
    assert (
        report["initial_subunits"] + report["added_subunits"] - report["removed_subunits"]
        == report["final_subunits"]
    )
    assert sum(report["dwell_by_size_total_s"]) == pytest.approx(spec.worlds * spec.end_time_s)


@pytest.mark.parametrize("backend", BACKENDS)
def test_saved_pending_event_and_chunk_independent_restart(backend, tmp_path):
    spec = parse_spec({"worlds": 8, "end_time_s": 3.0, "event_chunk_size": 32})
    complete, _ = run(spec, backend=backend)
    early, _ = run(spec, backend=backend, until=0.013)
    assert early.pending_valid.all() and np.all(early.pending_time_s > 0.013)
    checkpoint = tmp_path / backend
    write_checkpoint(checkpoint, spec, early, execution={"backend": backend})
    restored_spec, restored, _ = load_checkpoint(checkpoint)
    resumed, _ = run(replace(restored_spec, event_chunk_size=7), backend=backend, state=restored)
    for name in complete._fields:
        np.testing.assert_array_equal(getattr(complete, name), getattr(resumed, name), err_msg=name)


@pytest.mark.parametrize("backend", BACKENDS)
def test_closed_seed_zero_supply_and_complete_shell_are_absorbing(backend):
    for nodes in (RING, tuple(range(20))):
        spec = parse_spec(
            {
                "initial_nodes": list(nodes),
                "free_trimer_M": 0.0,
                "worlds": 8,
                "end_time_s": 3.0,
                "event_chunk_size": 32,
            }
        )
        state, report = run(spec, backend=backend)
        assert not state.event_count.any()
        assert np.isinf(state.pending_time_s).all()
        assert np.all(state.occupied == spec.initial_mask)
        assert report["completed_shells"] == (8 if len(nodes) == 20 else 0)


@pytest.mark.parametrize("backend", BACKENDS)
def test_irreversible_growth_completes_with_exact_inventory(backend):
    spec = parse_spec(
        {
            "initial_nodes": [10],
            "k_off_s_inv": 0.0,
            "free_trimer_M": 1e-6,
            "worlds": 8,
            "end_time_s": 3.0,
            "event_chunk_size": 32,
        }
    )
    state, report = run(spec, backend=backend)
    assert report["completed_shells"] == spec.worlds
    assert np.all(state.event_count == 19) and np.all(state.added == 19)
    assert not state.removed.any()
    assert (state.first_passage_s[:, 1:] >= 0).all()


@pytest.mark.parametrize("backend", BACKENDS)
def test_event_budget_reports_partial_failure(backend):
    spec = parse_spec(
        {
            "worlds": 8,
            "initial_nodes": list(OPEN_CHAIN),
            "end_time_s": 3.0,
            "event_chunk_size": 32,
            "max_events_per_world": 1,
        }
    )
    partial = []
    with pytest.raises(AssemblyError, match="fault"):
        run(spec, backend=backend, callback=lambda _, state, __: partial.append(state))
    assert np.any(partial[-1].fault == 2)
    assert np.all(partial[-1].event_count <= 1)
    validate_state(spec, partial[-1], allow_fault=True)


@pytest.mark.parametrize("backend", BACKENDS)
def test_initial_waiting_law_and_event_symmetry(backend):
    spec = parse_spec(
        {"initial_nodes": [10], "worlds": 4096, "end_time_s": 1e-12, "event_chunk_size": 1}
    )
    state, _ = run(spec, backend=backend)
    assert not state.event_count.any()
    standardized = state.pending_time_s * (3 * spec.k_on_M_inv_s * spec.free_trimer_M)
    assert abs(standardized.mean() - 1) < 6 / math.sqrt(spec.worlds)
    assert abs((standardized < 1).mean() - (1 - math.exp(-1))) < 6 * 0.5 / math.sqrt(spec.worlds)
    counts = np.unique(state.pending_event, return_counts=True)[1]
    assert len(counts) == 3
    assert np.max(abs(counts - spec.worlds / 3)) < 6 * math.sqrt(spec.worlds * 2 / 9)


@pytest.mark.parametrize("backend", BACKENDS)
def test_world_identity_survives_partitioning(backend):
    spec = parse_spec(
        {"worlds": 8, "world_id_start": 97, "end_time_s": 3.0, "event_chunk_size": 32}
    )
    full, _ = run(spec, backend=backend)
    parts = [
        run(replace(spec, worlds=4, world_id_start=97 + offset), backend=backend)[0]
        for offset in (0, 4)
    ]
    for field in full._fields:
        np.testing.assert_array_equal(
            getattr(full, field), np.concatenate([getattr(p, field) for p in parts]), err_msg=field
        )


def test_checkpoint_corruption_and_invalid_state_refused(tmp_path):
    spec = parse_spec({"worlds": 2})
    state = initial_state(spec)
    invalid = state._replace(added=np.ones(2, dtype=np.int64))
    with pytest.raises(AssemblyError, match="inventory"):
        validate_state(spec, invalid)
    target = tmp_path / "snapshot"
    write_checkpoint(target, spec, state, execution={"backend": "cpu"})
    with (target / "state.npz").open("ab") as stream:
        stream.write(b"changed")
    with pytest.raises(AssemblyError, match="digest"):
        load_checkpoint(target)
    manifest = json.loads((target / "manifest.json").read_text())
    manifest["state_sha256"] = digest(target / "state.npz")
    manifest["sources_sha256"]["kernel.py"] = "changed"
    (target / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(AssemblyError, match="source identity"):
        load_checkpoint(target)


def test_rate_underflow_and_checkpoint_expansion_refused(tmp_path):
    with pytest.raises(AssemblyError, match="underflows"):
        parse_spec({"k_on_M_inv_s": 1e-250, "free_trimer_M": 1e-250})
    spec = parse_spec({"worlds": 2})
    target = tmp_path / "oversized"
    write_checkpoint(target, spec, initial_state(spec), execution={"backend": "cpu"})
    np.savez_compressed(target / "state.npz", occupied=np.zeros(100000, dtype=np.uint32))
    manifest = json.loads((target / "manifest.json").read_text())
    manifest["state_sha256"] = digest(target / "state.npz")
    (target / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(AssemblyError, match="uncompressed"):
        load_checkpoint(target)


def pending_population():
    spec = parse_spec({"worlds": 2048, "initial_nodes": list(OPEN_CHAIN)})
    rates, targets = events(
        spec.initial_mask, spec.root_node, spec.k_on_M_inv_s * spec.free_trimer_M, spec.k_off_s_inv
    )
    choices = np.resize(np.flatnonzero(rates > 0), spec.worlds).astype(np.int32)
    state = initial_state(spec)._replace(
        pending_time_s=np.ones(spec.worlds),
        pending_valid=np.ones(spec.worlds, bool),
        pending_event=choices,
        pending_occupied=targets[choices],
    )
    return spec, state


def test_repeated_graph_checks_still_validate_every_world_target():
    spec, state = pending_population()
    validate_state(spec, state)
    altered = state.pending_occupied.copy()
    altered[-1] ^= np.uint32(1)
    with pytest.raises(AssemblyError, match="permitted graph transition"):
        validate_state(spec, state._replace(pending_occupied=altered))
    # A rejected replica must not contaminate the next independent state check.
    validate_state(spec, state)


@pytest.mark.parametrize("change", [{"free_trimer_M": 0}, {"k_off_s_inv": 0}, {"root_node": 0}])
def test_pending_witness_changes_with_rates_and_retained_root(change):
    spec, state = pending_population()
    validate_state(spec, state)
    with pytest.raises(AssemblyError, match="permitted graph transition"):
        validate_state(replace(spec, **change), state)


def test_no_event_witness_cannot_hide_one_changed_target_or_new_supply():
    spec = parse_spec({"worlds": 2048, "free_trimer_M": 0})
    state = initial_state(spec)._replace(
        pending_time_s=np.full(spec.worlds, np.inf),
        pending_valid=np.ones(spec.worlds, bool),
    )
    validate_state(spec, state)
    targets = state.pending_occupied.copy()
    targets[-1] ^= np.uint32(1)
    with pytest.raises(AssemblyError, match="no-event"):
        validate_state(spec, state._replace(pending_occupied=targets))
    with pytest.raises(AssemblyError, match="no-event"):
        validate_state(replace(spec, free_trimer_M=17e-9), state)


def test_lossless_checkpoint_preserves_complete_pending_array_bytes(tmp_path):
    spec, state = pending_population()
    state.time_s[0] = -0.0
    path = tmp_path / "checkpoint"
    write_checkpoint(path, spec, state, execution={"backend": "cpu"})
    restored_spec, restored, _ = load_checkpoint(path)
    assert spec.fingerprint == restored_spec.fingerprint
    for expected, actual in zip(state, restored, strict=True):
        assert expected.dtype == actual.dtype and expected.shape == actual.shape
        assert expected.tobytes() == actual.tobytes()
