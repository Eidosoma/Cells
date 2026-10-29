"""Native stochastic site correspondence, independent budgets, replay and JAX."""

import hashlib
import json
import os
from copy import deepcopy
from dataclasses import replace
from math import sqrt
from pathlib import Path

import numpy as np
import pytest

from cells.processes import betse_perturbations as perturb
from validation.perturbations import betse_perturbations_reference as reference
from validation.perturbations.betse_perturbations_fixtures import base, cases, limitations

ROOT = Path(__file__).resolve().parents[2]
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


@pytest.mark.parametrize("raw", cases(), ids=lambda x: x["name"])
def test_native_rng_order_timing_owners_and_independent_arithmetic(raw):
    record = captured(raw["name"])
    binding = perturb.bind_layout(layout(raw))
    ctrl = controls(raw)
    assert record["status"] == "passed"
    packets, stream = replay_native_calls(record, binding)
    static = perturb.static_initialize(
        np.asarray(raw["initial_diffusion_m2_s"]),
        packets[0].values,
        raw["static_level"],
        binding,
        xp=np,
    )
    assert perturb.static_domain_valid(
        np.asarray(raw["initial_diffusion_m2_s"]),
        packets[0].values,
        raw["static_level"],
        binding,
        xp=np,
    )
    close(static.current_m2_s, record["static"]["Dm_cells"], atol=1e-30)
    close(static.current_m2_s, reference.static(raw, packets[0].values), atol=1e-30)
    np.testing.assert_array_equal(static.base_m2_s, raw["initial_diffusion_m2_s"])
    np.testing.assert_array_equal(static.scheduled_m2_s, 0)
    choice = int(packets[1].values[0])
    mask = perturb.boundary_mask(
        choice, binding, domain=raw["modulator_domain"], offset=raw["modulator_offset"], xp=np
    )
    close(mask, record["boundary"]["mask"])
    close(mask, reference.boundary(raw, choice))
    assert record["boundary"]["dynamics"] == [1] * len(raw["times_s"])
    active = perturb.dynamic_active(ctrl)
    uniform_packets = iter(p for p in packets if p.site == "protein_flux")
    maximum_balance = 0.0
    for row in record["records"]:
        if raw["phase"] == "SIM":
            static = perturb.finalize_scheduled(static, xp=np)
        close(static.current_m2_s, row["Dm_cells"], atol=1e-30)
        assert row["draw_calls"] == int(active)
        packet = next(uniform_packets) if active else None
        value = np.zeros(len(binding.membrane_ids)) if packet is None else packet.values
        state = pstate(row["before"])
        assert perturb.protein_domain_valid(
            state, value, raw["dynamic_level"], raw["dt_s"], binding, enabled=active, xp=np
        )
        result = perturb.protein_step(
            state, value, raw["dynamic_level"], raw["dt_s"], binding, enabled=active, xp=np
        )
        expected = reference.protein(raw, row["before"], None if packet is None else packet.values)
        for actual, key in zip(result.state, ("cell", "membrane", "environment"), strict=True):
            close(actual, row["after_noise"][key])
            close(actual, expected["state"][key])
        if active:
            close(result.flux_mol_m2_s, row["flux"], atol=1e-23)
        bulk = (
            reference.bulk_zero_flux(raw, row["after_noise"])
            if raw["solver"] == "normal" and raw["protein_enabled"]
            else row["after_noise"]
        )
        for key in ("cell", "membrane", "environment"):
            close(bulk[key], row["after_bulk"][key])
        maximum_balance = max(maximum_balance, abs(float(result.balance_residual_mol)))
    if raw["run_microtubule"]:
        p = raw["micro"]
        normal = next((v for v in packets if v.site == "microtubule_gaussian"), None)
        z = np.zeros(len(binding.membrane_ids)) if normal is None else normal.values
        expected = reference.micro(raw, z)
        assert perturb.micro_domain_valid(
            np.asarray(p["ux"]),
            np.asarray(p["uy"]),
            np.asarray(p["length_m"]),
            np.asarray(p["drag_native"]),
            p["kb"],
            p["T"],
            p["sim_T"],
            raw["dt_s"],
            p["dilation"],
            binding,
            xp=np,
        )
        scale = perturb.micro_noise_scale(
            np.asarray(p["ux"]),
            np.asarray(p["uy"]),
            np.asarray(p["length_m"]),
            np.asarray(p["drag_native"]),
            p["kb"],
            p["T"],
            p["sim_T"],
            raw["dt_s"],
            p["dilation"],
            binding,
            diagnostic=True,
            xp=np,
        )
        if normal is not None:
            close(scale, expected["stdev"], atol=1e-30)
            drift = np.asarray(expected["drift"])
        else:
            drift = np.zeros(len(binding.membrane_ids))
        theta = perturb.micro_angle_step(
            np.asarray(p["theta"]),
            drift,
            np.asarray(p["modulator"]),
            scale,
            z,
            raw["dt_s"],
            p["dilation"],
            binding,
            diagnostic=True,
            xp=np,
        )
        close(theta, record["micro"]["theta"], atol=2e-15)
        close(theta, expected["theta"], atol=2e-15)
    evidence(
        raw["name"],
        dict(
            status="passed",
            layout_identity=binding.identity,
            draws=len(packets),
            native_final_rng_identity=stream.identity,
            maximum_balance_residual_mol=maximum_balance,
            source_dynamic_active=active,
            clock_times_s=raw["times_s"],
            dt_s=raw["dt_s"],
            microtubule_path_enabled=False,
            full_physiology=False,
        ),
    )


def test_zero_levels_still_consume_native_draws_and_static_noise_is_reset_only_in_SIM():
    normal = captured("normal-SIM")
    zero = captured("static-zero-still-draws")
    no_dynamic = captured("dynamic-disabled")
    assert zero["rng_after"] == normal["rng_after"]
    assert len(no_dynamic["draws"]) == 2 and len(normal["draws"]) == 5
    np.testing.assert_array_equal(zero["static"]["Dm_cells"], zero["static"]["Dm_base"])
    assert not np.array_equal(normal["static"]["Dm_cells"], normal["static"]["Dm_base"])
    np.testing.assert_array_equal(normal["records"][0]["Dm_cells"], normal["static"]["Dm_base"])
    init = captured("INIT-skips-dynamic-and-events")
    np.testing.assert_array_equal(init["records"][0]["Dm_cells"], init["static"]["Dm_cells"])
    # Loop labels do not determine the integration dt or draw count.
    labels = captured("clock-labels-do-not-set-dt")
    assert labels["rng_after"] == normal["rng_after"]
    for a, b in zip(labels["records"], normal["records"], strict=True):
        assert a["after_noise"] == b["after_noise"]


def test_native_gaussian_cache_roundtrip_and_global_rng_isolation():
    raw = next(v for v in cases() if v["name"] == "disabled-microtubule-tethered-drift")
    binding = perturb.bind_layout(layout(raw))
    record = captured(raw["name"])
    before = np.random.get_state()
    _, stream = replay_native_calls(record, binding)
    assert json.loads(stream.state_json)[3] == 1
    cached = json.loads(stream.state_json)[4]
    _, stream = perturb.sample_native(stream, binding, site="protein_flux", tick=7)
    manifest = json.loads(json.dumps(perturb.native_stream_manifest(stream)))
    assert manifest["state"][3] == 1 and manifest["state"][4] == cached
    restored = perturb.native_stream_from_manifest(manifest)
    draw, left = perturb.sample_native(stream, binding, site="microtubule_gaussian", tick=8)
    repeated, right = perturb.sample_native(restored, binding, site="microtubule_gaussian", tick=8)
    np.testing.assert_array_equal(draw.values, repeated.values)
    assert left == right
    assert draw.values[0] == cached
    after = np.random.get_state()
    assert before[0] == after[0] and before[2:] == after[2:]
    np.testing.assert_array_equal(before[1], after[1])
    evidence(
        "native-gaussian-cache",
        dict(
            status="passed",
            cached_value=cached,
            first_replayed_value=float(draw.values[0]),
            global_numpy_rng_untouched=True,
        ),
    )


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


def test_actual_native_uniform_gaussian_and_duplicate_weighted_boundary_distributions():
    record = captured("native-distributions")
    raw = record["input"]
    uniform = np.asarray(record["uniform"])
    normal = np.asarray(record["standard_normal"])
    assert np.all((uniform >= 0) & (uniform < 1)) and np.isfinite(normal).all()
    um, nm = moments(uniform), moments(normal, normal=True)
    chosen = np.asarray(record["chosen_cells"])
    counts = np.bincount(chosen, minlength=3)
    weights = np.bincount(raw["boundary_cells"], minlength=3) / len(raw["boundary_cells"])
    z = (counts - len(chosen) * weights) / np.sqrt(len(chosen) * weights * (1 - weights))
    assert np.max(np.abs(z)) < 6
    evidence(
        "native-distributions",
        dict(
            status="passed",
            uniform=um,
            standard_normal=nm,
            boundary_counts=counts.tolist(),
            boundary_probabilities=weights.tolist(),
            boundary_z_scores=z.tolist(),
            static_factor_mean=1 + raw["static_level"] * um["mean"],
            static_factor_expected_mean=1 + raw["static_level"] / 2,
            source_rng_id=perturb.NATIVE_RNG_ID,
        ),
    )


def test_protein_covariance_budget_and_dt_refinement_are_not_wiener_scaling():
    record = captured("native-distributions")
    raw = base()
    binding = perturb.bind_layout(layout(raw))
    m = len(binding.membrane_ids)
    flat = np.asarray(record["uniform"])
    worlds = 512
    level = raw["dynamic_level"]
    dt = raw["dt_s"]
    results = []
    for steps, local_dt in ((3, dt), (6, dt / 2)):
        uniforms = flat[: worlds * steps * m].reshape(worlds, steps, m)
        state = initial(raw)
        total = np.zeros((worlds, len(binding.cell_ids)))
        env = np.zeros((worlds, len(binding.environment_ids)))
        for i in range(steps):
            result = perturb.protein_step(state, uniforms[:, i], level, local_dt, binding, xp=np)
            state = result.state
            total += result.cell_amount_change_mol
            env += result.environment_amount_change_mol
        expected = (
            steps
            * (local_dt * level) ** 2
            / 12
            * np.sum(binding.kernel.cell_surface_map**2, axis=1)
        )
        mean = np.mean(total, axis=0)
        variance = np.var(total, axis=0, ddof=1)
        assert np.all(np.abs(mean) < 6 * np.sqrt(expected / worlds))
        assert np.all(np.abs(variance - expected) < 6 * np.sqrt(2 / (worlds - 1)) * expected)
        balance = np.sum(total, axis=1) + np.sum(env, axis=1)
        assert np.all(
            np.abs(balance) <= 3e-13 * (np.sum(np.abs(total), axis=1) + np.sum(np.abs(env), axis=1))
        )
        results.append(
            dict(
                steps=steps,
                dt_s=local_dt,
                variance_mol2=variance.tolist(),
                expected_variance_mol2=expected.tolist(),
                mean_mol=mean.tolist(),
            )
        )
    close(
        np.asarray(results[1]["expected_variance_mol2"]) / results[0]["expected_variance_mol2"],
        0.5,
        atol=1e-15,
    )
    # One-step cell/environment anti-covariance follows shared membrane owners.
    worlds = len(flat) // m
    u = flat[: worlds * m].reshape(worlds, m)
    result = perturb.protein_step(initial(raw), u, level, dt, binding, xp=np)
    a = result.cell_amount_change_mol
    b = result.environment_amount_change_mol
    actual = (a - a.mean(axis=0)).T @ (b - b.mean(axis=0)) / (worlds - 1)
    expected = (
        -((dt * level) ** 2)
        / 12
        * (binding.kernel.cell_surface_map @ binding.kernel.environment_surface_map.T)
    )
    va = (dt * level) ** 2 / 12 * np.sum(binding.kernel.cell_surface_map**2, axis=1)
    vb = (dt * level) ** 2 / 12 * np.sum(binding.kernel.environment_surface_map**2, axis=1)
    assert np.all(
        np.abs(actual - expected) <= 6 * np.sqrt(2 * va[:, None] * vb[None, :] / (worlds - 1))
    )
    evidence(
        "protein-statistics",
        dict(
            status="passed",
            worlds=512,
            panels=results,
            fixed_elapsed_s=3 * dt,
            expected_half_dt_variance_ratio=0.5,
            cell_environment_covariance_mol2=actual.tolist(),
            expected_covariance_mol2=expected.tolist(),
            scope=(
                "Uniform flux at fixed amplitude: integrated variance proportional to dt; "
                "no Brownian rescaling"
            ),
        ),
    )


@pytest.mark.parametrize("raw", limitations(), ids=lambda x: x["name"])
def test_native_broken_unsupported_and_disabled_paths_are_retained(raw):
    record = captured(raw["name"])
    name = raw["name"]
    failures = {
        "missing-potassium-index": "AttributeError",
        "boundary-empty": "ValueError",
        "boundary-subset-axis": "UnboundLocalError",
        "missing-microtubule-parameters": "AttributeError",
        "microtubule-missing-correlation": "AttributeError",
    }
    assert record["status"] == ("captured_failure" if name in failures else "captured_limitation")
    if name in failures:
        assert record["failure_type"] == failures[name] and record["traceback"]
    if name == "missing-potassium-index":
        binding = perturb.bind_layout(layout(raw))
        with pytest.raises(ValueError, match="potassium"):
            perturb.static_initialize(
                np.asarray(raw["initial_diffusion_m2_s"]),
                np.asarray(record["draws"][0]["values"]),
                0,
                binding,
                xp=np,
            )
    elif name == "negative-static-diffusion":
        binding = perturb.bind_layout(layout(raw))
        assert not perturb.static_domain_valid(
            np.asarray(raw["initial_diffusion_m2_s"]),
            np.asarray(record["draws"][0]["values"]),
            raw["static_level"],
            binding,
            xp=np,
        )
    elif name == "nonboolean-dynamic-guard":
        with pytest.raises(ValueError, match="boolean"):
            perturb.validate_controls(controls(raw))
    elif name == "fast-ECM-duplicate-overwrite":
        binding = perturb.bind_layout(layout(raw))
        row = record["records"][0]
        u = np.asarray(record["draws"][2]["values"])
        state = pstate(row["before"])
        result = perturb.protein_step(state, u, raw["dynamic_level"], raw["dt_s"], binding, xp=np)
        close(result.state.environment_mol_m3, row["after_noise"]["environment"])
        assert not perturb.protein_domain_valid(
            state, u, raw["dynamic_level"], raw["dt_s"], binding, xp=np
        )
        assert perturb.protein_domain_valid(
            state, u, raw["dynamic_level"], raw["dt_s"], binding, conservation_required=False, xp=np
        )
        assert abs(float(result.balance_residual_mol)) > 1e-25
        evidence(
            "fast-ECM-defect",
            dict(
                status="passed",
                retained_source_balance_residual_mol=float(result.balance_residual_mol),
                conservative_acceptance=False,
            ),
        )
    elif name == "negative-protein-clamp":
        row = next(r for r in record["records"] if min(r["after_noise"]["cell"]) < 0)
        assert min(row["after_bulk"]["cell"]) == 0 and min(row["after_bulk"]["membrane"]) < 0
        binding = perturb.bind_layout(layout(raw))
        u = np.asarray(record["draws"][2 + row["tick"]]["values"])
        assert not perturb.protein_domain_valid(
            pstate(row["before"]), u, raw["dynamic_level"], raw["dt_s"], binding, xp=np
        )
    elif name == "non-ECM-heterogeneous-bath-collapse":
        assert len(record["records"][0]["after_noise"]["environment"]) == 1
        with pytest.raises(ValueError, match="mixed_bath"):
            perturb.bind_layout(layout(raw))
    elif name == "boundary-empty":
        with pytest.raises(ValueError, match="Boundary"):
            perturb.bind_layout(layout(raw))
        assert len(record["draws"]) == 1
    elif name == "boundary-subset-axis":
        assert len(record["draws"]) == 2
    elif name == "boundary-equal-count-axis":
        binding = perturb.bind_layout(layout(raw))
        chosen = record["boundary"]["chosen_cell_index"]
        explicit = perturb.boundary_mask(
            chosen, binding, domain="cell", offset=raw["modulator_offset"], xp=np
        )
        assert not np.array_equal(explicit, record["boundary"]["mask"])
    elif name == "zero-source-dt-still-draws":
        assert len(record["draws"]) == 5
        with pytest.raises(ValueError, match="positive dt"):
            perturb.validate_controls(controls(raw))
    elif name == "microtubule-invalid-drag-initializer":
        assert any(v == "nan" for v in record["micro_initializer"]["drag_r"])
        assert not captured("normal-SIM")["input"]["run_microtubule"]
    elif name == "microtubule-negative-time":
        assert any(v == "nan" for v in record["micro"]["theta"])
        binding = perturb.bind_layout(layout(raw))
        p = raw["micro"]
        assert not perturb.micro_domain_valid(
            np.asarray(p["ux"]),
            np.asarray(p["uy"]),
            np.asarray(p["length_m"]),
            np.asarray(p["drag_native"]),
            p["kb"],
            p["T"],
            p["sim_T"],
            raw["dt_s"],
            p["dilation"],
            binding,
            xp=np,
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


def test_source_authentication_and_reference_independence():
    folder = os.environ.get("CELLS_BETSE_PERTURBATIONS_NATIVE_CAPTURE")
    if not folder:
        pytest.skip("Bounded wrapper supplies native captures")
    path = Path(folder)
    manifest = json.loads((path / "source-manifest.json").read_text())
    assert manifest["component_cases"] == len(cases()) == 21
    assert manifest["limitations"] == len(limitations()) == 14
    assert not manifest["production_cells_imported"] and not manifest["jax_imported"]
    assert not manifest["microtubules_enabled"] and not manifest["geometry_or_full_physiology"]
    assert (
        manifest["sites"]["fast_dynamic_rng_sites"] == []
        and not manifest["sites"]["microtubules_integrated"]
    )
    for relative, digest in PROTOCOL["native_source"]["source_sha256"].items():
        assert hashlib.sha256((path / "upstream" / relative).read_bytes()).hexdigest() == digest
    source = (ROOT / "validation/perturbations/betse_perturbations_reference.py").read_text()
    assert (
        "import numpy" not in source and "import jax" not in source and "from cells" not in source
    )


def test_cpu_jax_native_tape_kernels_batching_budget_and_exact_restart():
    import jax
    import jax.numpy as jnp

    raw = base()
    binding = perturb.bind_layout(layout(raw))
    record = captured(raw["name"])
    packets, _ = replay_native_calls(record, binding)
    assert jax.config.x64_enabled and all(d.platform == "cpu" for d in jax.devices())
    u = jnp.asarray([p.values for p in packets if p.site == "protein_flux"])
    state = jax.tree.map(jnp.asarray, initial(raw))
    step = jax.jit(
        lambda s, x: perturb.protein_step(s, x, raw["dynamic_level"], raw["dt_s"], binding)
    )

    def run(s, values):
        for row in values:
            s = step(s, row).state
        return s

    full = run(state, u)
    half = run(state, u[:1])
    restarted = run(half, u[1:])
    for a, b in zip(full, restarted, strict=True):
        np.testing.assert_array_equal(a, b)
    expected = initial(raw)
    for row in np.asarray(u):
        expected = perturb.protein_step(
            expected, row, raw["dynamic_level"], raw["dt_s"], binding, xp=np
        ).state
    for a, b in zip(full, expected, strict=True):
        close(a, b)
    batch = jnp.asarray(np.stack((packets[2].values, packets[3].values)))
    result = jax.jit(
        lambda value: perturb.protein_step(state, value, raw["dynamic_level"], raw["dt_s"], binding)
    )(batch)
    assert result.state.cell_mol_m3.shape == (2, 3)
    close(result.balance_residual_mol, 0, atol=1e-34)
    static = jax.jit(
        lambda value: perturb.static_initialize(
            jnp.asarray(raw["initial_diffusion_m2_s"]), value, raw["static_level"], binding
        )
    )(batch)
    assert (
        static.current_m2_s.shape
        == static.base_m2_s.shape
        == static.scheduled_m2_s.shape
        == (2, 3, 7)
    )
    evidence(
        "jax-native-tape",
        dict(
            status="passed",
            exact_restart=True,
            batch_shape=[2, 3],
            ticks=3,
            replay_scope=(
                "Identical source draw tape and component step function; "
                "no NumPy/JAX RNG stream equivalence"
            ),
        ),
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


def test_cpu_jax_invalid_world_isolation_and_noise_jacobians():
    import jax
    import jax.numpy as jnp

    raw = base()
    binding = perturb.bind_layout(layout(raw))
    state = jax.tree.map(jnp.asarray, initial(raw))
    u = jnp.asarray(captured("normal-SIM")["draws"][2]["values"])
    worlds = jnp.stack((u, u.at[0].set(jnp.nan), u))
    valid = jax.jit(
        jax.vmap(
            lambda x: perturb.protein_domain_valid(
                state, x, raw["dynamic_level"], raw["dt_s"], binding
            )
        )
    )(worlds)
    np.testing.assert_array_equal(valid, [True, False, True])
    jac = jax.jit(
        jax.jacfwd(
            lambda x: (
                perturb.protein_step(
                    state, x, raw["dynamic_level"], raw["dt_s"], binding
                ).state.cell_mol_m3
            )
        )
    )(u)
    expected = (
        raw["dt_s"]
        * raw["dynamic_level"]
        * binding.kernel.cell_surface_map
        / binding.kernel.cell_volume_m3[:, None]
    )
    close(jac, expected, atol=1e-25)
    p = raw["micro"]
    scale = perturb.micro_noise_scale(
        np.asarray(p["ux"]),
        np.asarray(p["uy"]),
        np.asarray(p["length_m"]),
        np.asarray(p["drag_native"]),
        p["kb"],
        p["T"],
        p["sim_T"],
        raw["dt_s"],
        p["dilation"],
        binding,
        diagnostic=True,
        xp=np,
    )
    derivative = jax.jit(
        jax.jacfwd(
            lambda normal: perturb.micro_angle_step(
                jnp.asarray(p["theta"]),
                jnp.zeros(7),
                jnp.ones(7),
                jnp.asarray(scale),
                normal,
                raw["dt_s"],
                p["dilation"],
                binding,
                diagnostic=True,
            )
        )
    )(jnp.zeros(7))
    close(derivative, np.diag(scale), atol=1e-30)
    evidence(
        "jax-validity-derivatives",
        dict(
            status="passed",
            valid_worlds=[True, False, True],
            protein_uniform_jacobian_shape=list(jac.shape),
            disabled_microtubule_noise_jacobian="Diagonal prescribed numeric scale",
        ),
    )
