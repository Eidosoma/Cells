"""Native stochastic site correspondence, independent budgets, replay and JAX."""

import json
import os
from copy import deepcopy
from dataclasses import replace
from math import sqrt
from pathlib import Path

import numpy as np
import pytest

from validation.betse.physiology import native_noise as perturb
from validation.perturbations.betse_perturbations_fixtures import base, cases

ROOT = Path(__file__).resolve().parents[3]
PROTOCOL = json.loads(
    (ROOT / "validation/perturbations/betse_perturbations_protocol.json").read_text()
)


def captured(name):
    folder = os.environ.get("CELLS_BETSE_PERTURBATIONS_NATIVE_CAPTURE")
    if not folder:
        pytest.skip("Bounded wrapper supplies authenticated actual stochastic-site captures")
    return json.loads((Path(folder) / (name + ".json")).read_text())


def evidence(name, record):
    if folder := os.environ.get("CELLS_COMPONENT_EVIDENCE"):
        path = Path(folder)
        path.mkdir(parents=True, exist_ok=True)
        (path / ("betse-perturbations-" + name + ".json")).write_text(
            json.dumps(record, indent=2, allow_nan=False) + "\n"
        )


def layout(raw=None):
    raw = base() if raw is None else raw
    mode = (
        "mixed_bath" if not raw["is_ecm"] else "source_fast" if raw["fast_update_ecm"] else "matrix"
    )
    return perturb.Layout(
        tuple(raw["cell_ids"]),
        tuple(raw["membrane_ids"]),
        tuple(raw["environment_ids"]),
        tuple(raw["ion_ids"]),
        tuple(raw["cell_ids"][i] for i in raw["owner"]),
        tuple(raw["environment_ids"][i] for i in raw["environment_owner"]),
        tuple(raw["cell_ids"][i] for i in raw["boundary_cells"]),
        np.asarray(raw["membrane_area_m2"]),
        np.asarray(raw["cell_volume_m3"]),
        raw["environment_volume_m3"] if raw["is_ecm"] else raw["bath_parameter_volume_m3"],
        mode,
        dict(
            native_case=raw["name"],
            seed=raw["seed"],
            source_revision=PROTOCOL["native_source"]["revision"],
        ),
    )


def controls(raw=None):
    raw = base() if raw is None else raw
    return perturb.Controls(
        raw["phase"],
        raw["solver"],
        raw["dynamic_enabled"],
        raw["protein_enabled"],
        raw["static_level"],
        raw["dynamic_level"],
        raw["dt_s"],
    )


def pstate(raw):
    return perturb.ProteinState(
        *(np.asarray(raw[k], float) for k in ("cell", "membrane", "environment"))
    )


def initial(raw=None):
    raw = base() if raw is None else raw
    return perturb.ProteinState(
        *(
            np.asarray(raw[k], float)
            for k in (
                "initial_cell_mol_m3",
                "initial_membrane_mol_m3",
                "initial_environment_mol_m3",
            )
        )
    )


def close(a, b, *, rtol=5e-13, atol=2e-14):
    np.testing.assert_allclose(a, np.asarray(b, float), rtol=rtol, atol=atol)


def replay_native_calls(record, binding):
    stream = perturb.native_stream(record["input"]["seed"])
    packets = []
    tick = 0
    for i, row in enumerate(record["draws"]):
        site = (
            "static_K"
            if i == 0
            else "boundary_choice"
            if row["family"] == "choice"
            else "microtubule_gaussian"
            if row["family"] == "normal"
            else "protein_flux"
        )
        current_tick = tick if site == "protein_flux" else 0
        packet, stream = perturb.sample_native(stream, binding, site=site, tick=current_tick)
        np.testing.assert_array_equal(
            packet.values,
            row["standard_normal"]
            if row["family"] == "normal"
            else [row["values"]]
            if row["family"] == "choice"
            else row["values"],
        )
        assert perturb.native_stream_manifest(stream)["state"] == row["state_after"]
        restored = perturb.draw_from_manifest(
            json.loads(json.dumps(perturb.draw_manifest(packet, binding))), binding
        )
        np.testing.assert_array_equal(restored.values, packet.values)
        packets.append(packet)
        if site == "protein_flux":
            tick += 1
    assert perturb.native_stream_manifest(stream)["state"] == record["rng_after"]
    return packets, stream


def run_native_window(binding, ctrl, state, stop):
    p = state.protein
    d = state.diffusion
    rng = state.rng
    for tick in range(state.tick, stop):
        if ctrl.phase == "SIM":
            d = perturb.finalize_scheduled(d, xp=np)
        if perturb.dynamic_active(ctrl):
            draw, rng = perturb.sample_native(rng, binding, site="protein_flux", tick=tick)
            p = perturb.protein_step(
                p, draw.values, ctrl.dynamic_level_mol_m2_s, ctrl.dt_s, binding, xp=np
            ).state
        if ctrl.solver == "normal" and ctrl.protein_enabled:
            p = p._replace(membrane_mol_m3=p.cell_mol_m3[binding.kernel.owner].copy())
    return perturb.Replay(p, d, rng, stop, state.time_s + (stop - state.tick) * ctrl.dt_s)


def test_component_native_replay_roundtrip_exact_restart_and_stale_controls():
    raw = base()
    binding = perturb.bind_layout(layout(raw))
    ctrl = controls(raw)
    rng = perturb.native_stream(raw["seed"])
    draw, rng = perturb.sample_native(rng, binding, site="static_K", tick=0)
    d = perturb.static_initialize(
        np.asarray(raw["initial_diffusion_m2_s"]), draw.values, ctrl.static_level, binding, xp=np
    )
    _, rng = perturb.sample_native(rng, binding, site="boundary_choice", tick=0)
    state = perturb.Replay(initial(raw), d, rng, 0, 0.0)
    full = run_native_window(binding, ctrl, state, 7)
    half = run_native_window(binding, ctrl, state, 3)
    record = perturb.replay_record(binding, ctrl, half)
    restored = perturb.restore_replay(json.loads(json.dumps(record)), binding, ctrl)
    resumed = run_native_window(binding, ctrl, restored, 7)
    for left, right in zip(
        (*full.protein, *full.diffusion), (*resumed.protein, *resumed.diffusion), strict=True
    ):
        np.testing.assert_array_equal(left, right)
    assert full.rng == resumed.rng and full.tick == resumed.tick
    close(full.time_s, resumed.time_s, atol=1e-17)
    with pytest.raises(ValueError, match="controls"):
        perturb.restore_replay(record, binding, replace(ctrl, dt_s=0.003))
    corrupted = deepcopy(record)
    corrupted["protein"]["cell_mol_m3"][0] += 1
    with pytest.raises(ValueError, match="identity"):
        perturb.restore_replay(corrupted, binding, ctrl)
    evidence(
        "native-replay",
        dict(
            status="passed",
            ticks=7,
            split_tick=3,
            time_s=full.time_s,
            exact_buffers=True,
            exact_rng_state=True,
            replay_record=record,
            scope=(
                "Prescribed component clocks and zero-other-flux scaffold; "
                "no shared simulator checkpoint migration"
            ),
        ),
    )


def moments(values, *, normal=False):
    values = np.asarray(values, float)
    n = len(values)
    mean = float(np.mean(values))
    variance = float(np.var(values, ddof=1))
    expected_mean, expected_var = (0.0, 1.0) if normal else (0.5, 1 / 12)
    mean_bound = 6 * sqrt(expected_var / n)
    variance_bound = 6 * sqrt((2 if normal else 1 / 180) / (n - 1))
    assert abs(mean - expected_mean) < mean_bound
    assert abs(variance - expected_var) < variance_bound
    return dict(
        samples=n,
        mean=mean,
        variance=variance,
        mean_six_sigma_bound=mean_bound,
        variance_six_sigma_bound=variance_bound,
    )


@pytest.mark.parametrize(
    "variant",
    (
        "duplicate-ids",
        "wrong-owner",
        "negative-area",
        "boolean-area",
        "zero-volume",
        "invalid-mode",
        "empty-boundary",
        "wrong-env-owner",
    ),
)
def test_invalid_owner_and_measure_bindings(variant):
    value = layout()
    if variant == "duplicate-ids":
        value = replace(value, cell_ids=("same",) * 3)
    elif variant == "wrong-owner":
        value = replace(value, membrane_cell_ids=("missing",) * 7)
    elif variant == "negative-area":
        value = replace(value, membrane_area_m2=-value.membrane_area_m2)
    elif variant == "boolean-area":
        value = replace(value, membrane_area_m2=np.ones(7, bool))
    elif variant == "zero-volume":
        value = replace(value, cell_volume_m3=np.zeros(3))
    elif variant == "invalid-mode":
        value = replace(value, environment_mode="automatic")
    elif variant == "empty-boundary":
        value = replace(value, boundary_cell_occurrences=())
    else:
        value = replace(value, membrane_environment_ids=("wrong",) * 7)
    with pytest.raises(ValueError):
        perturb.bind_layout(value)


@pytest.mark.parametrize(
    "variant",
    ("key-count", "position", "cache-flag", "cache-nan", "version", "identity", "all-zero"),
)
def test_native_rng_state_rejection(variant):
    record = perturb.native_stream_manifest(perturb.native_stream(17))
    if variant == "key-count":
        record["state"][1].pop()
    elif variant == "position":
        record["state"][2] = 625
    elif variant == "cache-flag":
        record["state"][3] = True
    elif variant == "cache-nan":
        record["state"][4] = np.nan
    elif variant == "version":
        record["numpy_version"] = "different"
    elif variant == "identity":
        record["identity"] = "wrong"
    else:
        record["state"][1] = [0] * 624
    with pytest.raises(ValueError):
        perturb.native_stream_from_manifest(record)


def test_mixed_bath_effective_volume_and_replay_owner_identity():
    raw = next(r for r in cases() if r["name"] == "non-ECM-mixed-bath")
    binding = perturb.bind_layout(layout(raw))
    close(
        binding.kernel.environment_effective_volume_m3,
        [len(binding.membrane_ids) * raw["bath_parameter_volume_m3"]],
        atol=1e-30,
    )
    rng = perturb.native_stream(17)
    packet, _ = perturb.sample_native(rng, binding, site="protein_flux", tick=0)
    different = perturb.bind_layout(replace(layout(raw), provenance=dict(changed=True)))
    with pytest.raises(ValueError, match="Stale"):
        perturb.draw_manifest(packet, different)
    for value in binding.kernel:
        assert not value.flags.writeable
    assert not packet.values.flags.writeable
    with pytest.raises(ValueError):
        packet.values[0] = 1.0
    with pytest.raises(ValueError):
        perturb.boundary_mask(0, binding, domain="automatic", xp=np)
    with pytest.raises(ValueError):
        perturb.micro_angle_step(
            np.zeros(7),
            np.zeros(7),
            np.ones(7),
            np.zeros(7),
            np.zeros(7),
            0.001,
            1,
            binding,
            diagnostic=False,
            xp=np,
        )


def test_cpu_jax_stable_world_owner_site_and_batch_order_isolation():
    import jax
    import jax.numpy as jnp

    binding = perturb.bind_layout(layout())
    tokens = binding.kernel.membrane_tokens
    tick = perturb.words64(2**40 + 3)
    ids = [7, 2**32 + 7, 19]
    words = jnp.asarray(np.stack([perturb.words64(v) for v in ids]))
    sampler = jax.jit(
        jax.vmap(lambda w: perturb.stable_uniforms(17, w, tick, tokens, site="protein_flux"))
    )
    full = np.asarray(sampler(words))
    reverse = np.asarray(sampler(words[::-1]))
    np.testing.assert_array_equal(full, reverse[::-1])
    assert not np.array_equal(full[0], full[1])
    single = jax.jit(
        lambda tok: perturb.stable_uniforms(17, words[0], tick, tok, site="protein_flux")
    )
    np.testing.assert_array_equal(single(tokens[::-1]), full[0, ::-1])
    np.testing.assert_array_equal(single(tokens[[1, 4]]), full[0, [1, 4]])
    static = perturb.stable_uniforms(17, words[0], tick, tokens, site="static_K")
    assert not np.array_equal(static, full[0])
    assert np.all((full > 0) & (full < 1))
    coords = perturb.StableCoordinates(17, ids[1])
    packet = perturb.sample_stable(coords, binding, site="protein_flux", tick=2**40 + 3)
    np.testing.assert_array_equal(packet.values, full[1])
    value = layout()
    reverse_layout = replace(
        value,
        membrane_ids=value.membrane_ids[::-1],
        membrane_cell_ids=value.membrane_cell_ids[::-1],
        membrane_environment_ids=value.membrane_environment_ids[::-1],
        membrane_area_m2=value.membrane_area_m2[::-1],
    )
    other = perturb.bind_layout(reverse_layout)
    reordered = perturb.sample_stable(coords, other, site="protein_flux", tick=2**40 + 3)
    np.testing.assert_array_equal(packet.values, reordered.values[::-1])
    native, _ = perturb.sample_native(
        perturb.native_stream(17), binding, site="protein_flux", tick=0
    )
    native_reordered, _ = perturb.sample_native(
        perturb.native_stream(17), other, site="protein_flux", tick=0
    )
    np.testing.assert_array_equal(native.values, native_reordered.values)
    assert not np.array_equal(native.values, native_reordered.values[::-1])
    with pytest.raises(ValueError):
        perturb.draw_manifest(packet, other)
    evidence(
        "stable-isolation",
        dict(
            status="passed",
            world_ids=ids,
            tick=2**40 + 3,
            world_order_exact=True,
            owner_order_subset_exact=True,
            site_separated=True,
            rng_id=perturb.STABLE_RNG_ID,
        ),
    )


def test_cpu_jax_stable_distributions_boundary_weights_and_replay_record():
    import jax
    import jax.numpy as jnp

    binding = perturb.bind_layout(layout())
    n = 8192
    words = jnp.stack(
        (jnp.arange(n, dtype=jnp.uint32), jnp.ones(n, dtype=jnp.uint32) * 13), axis=-1
    )
    token = perturb.owner_tokens(("test-owner",), domain="membrane")
    pairs = jax.jit(
        jax.vmap(
            lambda w: perturb.stable_pairs(23, w, perturb.words64(9), token, site="protein_flux")
        )
    )(words)[:, 0]
    uniform = np.asarray(pairs[:, 0])
    z = np.asarray(jnp.sqrt(-2 * jnp.log(pairs[:, 0])) * jnp.cos(2 * jnp.pi * pairs[:, 1]))
    um, nm = moments(uniform), moments(z, normal=True)
    selected = np.asarray(
        jax.jit(lambda u: perturb.stable_boundary_index(u, binding))(jnp.asarray(uniform))
    )
    counts = np.bincount(selected, minlength=3)
    weights = np.asarray([2, 1, 3]) / 6
    scores = (counts - n * weights) / np.sqrt(n * weights * (1 - weights))
    assert np.max(np.abs(scores)) < 6
    reversed_binding = perturb.bind_layout(
        replace(
            layout(), boundary_cell_occurrences=tuple(reversed(layout().boundary_cell_occurrences))
        )
    )
    np.testing.assert_array_equal(
        selected, perturb.stable_boundary_index(jnp.asarray(uniform), reversed_binding)
    )
    coordinates = perturb.StableCoordinates(23, 2**48 + 9)
    packet = perturb.sample_stable(coordinates, binding, site="static_K", tick=0)
    diffusion = perturb.static_initialize(
        np.asarray(base()["initial_diffusion_m2_s"]), packet.values, 2.0, binding, xp=np
    )
    snap = perturb.replay_record(
        binding, controls(), perturb.Replay(initial(), diffusion, coordinates, 9, 0.018)
    )
    restored = perturb.restore_replay(json.loads(json.dumps(snap)), binding, controls())
    future = perturb.sample_stable(coordinates, binding, site="protein_flux", tick=9)
    repeated = perturb.sample_stable(restored.rng, binding, site="protein_flux", tick=restored.tick)
    np.testing.assert_array_equal(future.values, repeated.values)
    evidence(
        "stable-distributions-replay",
        dict(
            status="passed",
            uniform=um,
            standard_normal=nm,
            boundary_counts=counts.tolist(),
            boundary_z_scores=scores.tolist(),
            exact_coordinate_replay=True,
            source_rng_equivalence=False,
            rng_id=perturb.STABLE_RNG_ID,
        ),
    )
