"""Pinned mechanics/pressure/display, independent mathematics and CPU JAX."""

import hashlib
import json
import os
from copy import deepcopy
from math import cos, pi, sqrt
from pathlib import Path

import numpy as np
import pytest

from cells.processes import betse_deformation as mechanics
from validation.mechanics import betse_deformation_reference as reference
from validation.mechanics.betse_deformation_fixtures import (
    base,
    cases,
    compatible_modal_operators,
    display_cases,
    limitations,
)

CASES = cases()
ROOT = Path(__file__).resolve().parents[2]
PROTOCOL = json.loads((ROOT / "validation/mechanics/betse_deformation_protocol.json").read_text())


def evidence(name, data):
    if folder := os.environ.get("CELLS_COMPONENT_EVIDENCE"):
        path = Path(folder)
        path.mkdir(parents=True, exist_ok=True)
        (path / ("betse-deformation-" + name + ".json")).write_text(
            json.dumps(data, indent=2, allow_nan=False) + "\n"
        )


def captured(name):
    if not (folder := os.environ.get("CELLS_BETSE_DEFORMATION_NATIVE_CAPTURE")):
        pytest.skip("Bounded wrapper supplies authenticated native mechanics captures")
    return json.loads((Path(folder) / (name + ".json")).read_text())


def prepare(raw=None, padding=0):
    raw = deepcopy(base() if raw is None else raw)
    mesh = raw["layout"]
    n = len(mesh["centers_m"])
    op = mechanics.bind_operators(
        *(
            mesh[key]
            for key in (
                "neighbors",
                "lengths_m",
                "force_directions",
                "curl_directions",
                "sum_membranes",
                "incidence",
                "incidence_inverse",
                "dual_edge_m",
                "primal_edge_m",
                "dual_area_m2",
            )
        ),
        cell_capacity=n + padding,
    )
    p = mechanics.Parameters(
        raw["young_modulus_Pa"] / (2 * 1.49),
        raw["galvanotropism_m2_V"],
        raw["include_osmotic"],
        raw["fixed_boundary"],
        raw["dt_s"],
        raw["viscous_damping_native"],
        raw["cell_radius_m"],
    )

    def pad(value, fill=0.0):
        a = np.asarray(value, float)
        return np.pad(a, [(0, 0)] * (a.ndim - 1) + [(0, padding)], constant_values=fill)

    f = mechanics.Forcing(
        *(
            pad(raw[key], 1.0 if key == "conductivity_S_m" else 0.0)
            for key in (
                "pressure_Pa",
                "PP_native",
                "electric_field_V_m",
                "current_density_A_m2",
                "charge_density_C_m3",
                "conductivity_S_m",
            )
        )
    )
    history = mechanics.History(pad(raw["displacement_m"]), pad(raw["previous_displacement_m"]))
    return raw, f, history, op, p


def osmotic_inputs(raw, op):
    mesh, count = raw["layout"], op.active.size
    n, env_count = len(mesh["centers_m"]), len(raw["primary_env_mM"][0])
    cell = np.sum(
        np.asarray([*raw["primary_cell_mM"], *raw["molecule_cell_mM"], *raw["grn_cell_mM"]]), axis=0
    )
    env = np.sum(
        np.asarray([*raw["primary_env_mM"], *raw["molecule_env_mM"], *raw["grn_env_mM"]]), axis=0
    )
    mapping = np.asarray(raw["cell_to_environment"], int)
    if raw["is_ecm"]:
        average = np.eye(env_count)[mapping]
    else:
        env = env[mapping[np.repeat(np.arange(n), 4)]]
        sm = np.asarray(mesh["sum_membranes"], float)
        average = sm / sm.sum(axis=1)[:, None]
    g = mechanics.OsmoticGeometry(
        np.pad(average, ((0, count - n), (0, 0))),
        np.pad(mesh["cell_area_m2"], (0, count - n)),
        np.pad(mesh["cell_volume_m3"], (0, count - n)),
    )
    params = mechanics.OsmoticParameters(
        *(
            raw[key]
            for key in (
                "gas_constant_J_mol_K",
                "temperature_K",
                "aquaporin_fraction",
                "water_viscosity_Pa_s",
                "membrane_thickness_m",
                "density_kg_m3",
                "dt_s",
            )
        )
    )
    return np.pad(cell, (0, count - n)), env, np.pad(raw["pressure_Pa"], (0, count - n)), g, params


def close(actual, expected, *, operator=False, pressure=False, display=False, auxiliary=False):
    atol = (
        2e-14
        if operator
        else 3e-9
        if pressure
        else 3e-17
        if display
        else 3e-14
        if auxiliary
        else 3e-20
    )
    np.testing.assert_allclose(actual, expected, rtol=8e-12, atol=atol)


def result_dict(result):
    if isinstance(result, mechanics.DisabledTimeResult):
        return {
            **result._asdict(),
            "displacement_m": result.history.displacement_m,
            "previous_displacement_m": result.history.previous_displacement_m,
        }
    return result._asdict()


@pytest.mark.parametrize("raw", CASES, ids=lambda r: r["name"])
def test_native_and_independent_operator_forcing_correspondence(raw):
    raw, f, history, op, p = prepare(raw)
    expected, native = reference.evaluate(raw), captured(raw["name"])
    assert native["status"] == "passed" and native["source_td_deform"] is False
    close(p.shear_modulus_Pa, native["source_shear_Pa"], auxiliary=True)
    for key, matrix in op._asdict().items():
        if key != "active":
            close(matrix, expected["operators"][key], operator=True)
    for key, matrix in native["native_operators"].items():
        close(getattr(op, key), matrix, operator=True)
    if raw["compute_osmotic"]:
        cell, env, pressure, geometry, params = osmotic_inputs(raw, op)
        assert mechanics.osmotic_domain_valid(cell, env, pressure, geometry, op, params, xp=np)
        osmo = mechanics.osmotic_auxiliary(cell, env, pressure, geometry, op, params, xp=np)
        for key, actual in osmo._asdict().items():
            close(
                actual,
                native["osmotic"][key],
                pressure=key.endswith("_Pa"),
                auxiliary=not key.endswith("_Pa"),
            )
        assert native["geometry_volumes_unchanged"]
        f = f._replace(osmotic_PP_native=osmo.PP_native)
    if raw["mode"] == "time":
        assert mechanics.domain_valid(f, op, p, history=history, time_s=raw["clock_s"], xp=np)
        result = mechanics.disabled_time_step(history, f, op, p, xp=np)
    else:
        assert mechanics.domain_valid(f, op, p, xp=np)
        result = mechanics.steady(f, op, p, xp=np)
    actual = result_dict(result)
    for key, value in expected["result"].items():
        close(
            actual[key],
            value,
            pressure=key.startswith("pressure_gradient"),
            auxiliary=key
            in (
                "source_k_m2",
                "source_gamma_native",
                "divided_body_force_native",
                "divergence_numeric",
            ),
        )
    close(actual["displacement_m"], native["result"]["displacement_m"])
    evidence(
        raw["name"],
        dict(
            status="passed",
            input=raw,
            displacement_m=np.asarray(actual["displacement_m"]).tolist(),
            native_time_enabled=False,
            branch=raw["mode"],
            divergence_numeric=np.asarray(actual["divergence_numeric"]).tolist(),
        ),
    )


@pytest.mark.parametrize("raw", display_cases(), ids=lambda r: r["name"])
def test_display_polynomial_regime_and_repeated_sample_ownership(raw):
    native, expected = captured(raw["name"]), reference.display_expected(raw)
    mesh = raw["layout"]
    centres, original = np.asarray(mesh["centers_m"]), np.asarray(mesh["vertices_m"])
    sm, area = np.asarray(mesh["sum_membranes"]), np.asarray(mesh["membrane_area_m2"])
    weights = sm * area / np.asarray(mesh["cell_area_m2"])[:, None]
    initial = centres.copy()
    for index in range(raw["calls"]):
        interpolation = mechanics.quartic_display_interpolator(centres, original)
        assert mechanics.display_domain_valid(
            np.asarray(raw["displacement_m"]), interpolation, original, weights, xp=np
        )
        result = mechanics.display(
            np.asarray(raw["displacement_m"]), interpolation, original, weights, xp=np
        )
        for key, value in result._asdict().items():
            close(value, expected[index][key], display=True)
            close(value, np.asarray(native["display_calls"][index][key], float), display=True)
        centres = result.cell_centres_m
    np.testing.assert_array_equal(initial, mesh["centers_m"])
    assert (
        native["physical_centres_unchanged"]
        and native["original_membrane_vertices_unchanged"]
        and native["volumes_unchanged"]
    )
    assert native["history_counts"] == dict(
        vertices=raw["calls"], centres=raw["calls"], displacement=raw["calls"]
    )
    if raw["calls"] == 2:
        shift = np.max(
            np.abs(
                np.asarray(native["display_calls"][1]["vertices_m"], float)
                - np.asarray(native["display_calls"][0]["vertices_m"], float)
            )
        )
        assert shift > 1e-12
        evidence(
            "display-repeat",
            dict(
                status="passed",
                samples=2,
                repeat_difference_m=float(shift),
                physical_geometry_changed=False,
                operator_recomputed_for_current_display_centres=True,
            ),
        )


def test_boundary_flag_is_ignored_and_electric_is_added_after_rotation():
    raw, f, _, op, p = prepare()
    left, right = (
        mechanics.steady(f, op, p._replace(fixed_cluster_boundary=flag), xp=np)
        for flag in (True, False)
    )
    for actual, expected in zip(left, right, strict=True):
        np.testing.assert_array_equal(actual, expected)
    constant = f._replace(pressure_Pa=np.ones_like(f.pressure_Pa))
    actual = mechanics.steady(constant, op, p, xp=np)
    close(actual.displacement_m, f.electric_field_V_m * raw["galvanotropism_m2_V"])
    assert np.max(np.abs(actual.displacement_m)) > 0
    _, projected_electric = mechanics.rotation_only(actual.electric_addition_m, op, xp=np)
    assert np.max(np.abs(projected_electric - actual.displacement_m)) > 1e-9


def test_osmotic_clock_scaling_and_no_volume_update():
    raw = next(r for r in CASES if r["name"] == "osmotic-ecm")
    _, _, _, op, _ = prepare(raw)
    cell, env, pressure, geometry, p = osmotic_inputs(raw, op)
    before = deepcopy((cell, env, pressure, geometry))
    first = mechanics.osmotic_auxiliary(cell, env, pressure, geometry, op, p, xp=np)
    double = mechanics.osmotic_auxiliary(
        cell, env, pressure, geometry, op, p._replace(dt_s=p.dt_s * 2), xp=np
    )
    close(double.PP_native, 2 * first.PP_native, auxiliary=True)
    for a, b in zip(first[:-1], double[:-1], strict=True):
        np.testing.assert_array_equal(a, b)
    for actual, expected in zip(
        (cell, env, pressure, *geometry), (*before[:3], *before[3]), strict=True
    ):
        np.testing.assert_array_equal(actual, expected)


def test_disabled_time_double_shear_and_hardcoded_density():
    raw, f, history, op, p = prepare(next(r for r in CASES if r["name"] == "time-positive"))
    f = f._replace(pressure_Pa=np.zeros_like(f.pressure_Pa))
    zero = mechanics.History(
        np.zeros_like(history.displacement_m), np.zeros_like(history.previous_displacement_m)
    )
    result = mechanics.disabled_time_step(zero, f, op, p, xp=np)
    body = (
        f.current_density_A_m2 / f.conductivity_S_m * f.charge_density_C_m3 * p.galvanotropism_m2_V
    )
    close(result.unprojected_candidate_m, (p.dt_s**2 / (1000 * p.shear_modulus_Pa)) * body)
    assert float(result.source_k_m2[0]) == p.dt_s**2 * (p.shear_modulus_Pa / 1000)
    assert raw["density_kg_m3"] == 1050.0


def test_native_gradient_refinement_and_nonprojector_gain():
    errors, gains = [], []
    for n in (8, 16, 32):
        raw = next(r for r in CASES if r["name"] == "periodic-strip-" + str(n))
        _, f, _, op, _ = prepare(raw)
        phase = 2 * pi * np.arange(n) / n
        k = 2 * pi / 1e-3
        exact = -0.5 * k * np.cos(phase)
        gradient = op.pressure_gradient_x @ np.sin(phase)
        errors.append(float(np.max(np.abs(gradient - exact))))
        vector = np.stack((np.zeros(n), np.sin(phase)))
        _, first = mechanics.rotation_only(vector, op, xp=np)
        _, twice = mechanics.rotation_only(first, op, xp=np)
        gain = cos(pi / n) ** 2 / 4
        close(first[1], gain * vector[1], auxiliary=True)
        close(twice[1], gain**2 * vector[1], auxiliary=True)
        assert np.max(np.abs(first - twice)) > 0.1
        gains.append(gain)
    orders = np.log2(np.asarray(errors[:-1]) / np.asarray(errors[1:]))
    assert np.all((orders > 1.9) & (orders < 2.1))
    assert gains[-1] < 0.25
    evidence(
        "spatial-refinement",
        dict(
            status="passed",
            cell_counts=[8, 16, 32],
            gradient_errors_per_m=errors,
            orders=orders.tolist(),
            native_rotation_gains=gains,
            continuum_source_gain=0.25,
            orthogonal_projection_claim=False,
            scope=(
                "Supplied periodic-strip native operator arithmetic, "
                "not a tissue mesh convergence claim"
            ),
        ),
    )


def modal_state(dt_s):
    raw = compatible_modal_operators()
    d, z, lap, inverse = (
        np.asarray(raw[key], float) for key in ("gradient", "zero", "laplacian", "inverse")
    )
    op = mechanics.validate_operators(
        mechanics.Operators(-d, z, d, z, lap, inverse, np.ones(len(d), bool))
    )
    n, mu, amplitude = len(d), 1000 / (2 * 1.49), 1e-7
    p = mechanics.Parameters(mu, 0.0, False, True, dt_s, 0.0, 1e-5)
    f = mechanics.Forcing(
        np.zeros(n), np.zeros(n), np.zeros((2, n)), np.zeros((2, n)), np.zeros(n), np.ones(n)
    )
    omega = raw["k_per_m"] * sqrt(mu / 1000)
    current = np.stack((np.zeros(n), amplitude * np.asarray(raw["mode"])))
    previous = current * cos(omega * dt_s)
    return raw, f, mechanics.History(current, previous), op, p, omega


def test_disabled_primed_recurrence_time_refinement():
    _, _, _, _, _, omega = modal_state(1e-6)
    duration = 0.37 * 2 * pi / omega
    errors, steps = [], [32, 64, 128]
    for count in steps:
        raw, f, history, op, p, omega = modal_state(duration / count)
        start = history.displacement_m.copy()
        for _step in range(count):
            history = mechanics.disabled_time_step(history, f, op, p, xp=np).history
        assert mechanics.domain_valid(f, op, p, history=history, time_s=duration, xp=np)
        exact = start * cos(omega * duration)
        errors.append(float(np.max(np.abs(history.displacement_m - exact))))
        assert np.all(np.isfinite(history.displacement_m))
    orders = np.log2(np.asarray(errors[:-1]) / np.asarray(errors[1:]))
    assert np.all((orders > 1.9) & (orders < 2.1))
    evidence(
        "disabled-time-refinement",
        dict(
            status="passed",
            native_enabled=False,
            density_in_recurrence_kg_m3=1000.0,
            omega_per_s=omega,
            physical_duration_s=duration,
            dt_s=[duration / count for count in steps],
            steps=steps,
            errors_m=errors,
            orders=orders.tolist(),
            initialization=(
                "Supplied analytic two-level history; native t=0 initialization remains broken"
            ),
            scope=(
                "Compatible manufactured solenoidal modal operators; "
                "no native geometry/whole-tissue settling"
            ),
        ),
    )


def test_native_has_no_displacement_clamp_and_caller_limit_is_explicit():
    raw = next(r for r in limitations() if r["name"] == "steady-unbounded-displacement")
    _, f, _, op, p = prepare(raw)
    actual = mechanics.steady(f, op, p, xp=np)
    assert np.max(np.abs(actual.displacement_m)) > 100
    assert mechanics.domain_valid(f, op, p, xp=np)
    assert not mechanics.domain_valid(f, op, p, max_displacement_m=p.cell_radius_m, xp=np)
    _, f, history, op, p, omega = modal_state(1e-6)
    p = p._replace(dt_s=3 / omega)
    assert mechanics.domain_valid(f, op, p, history=history, time_s=1.0, xp=np)
    assert not mechanics.domain_valid(
        f, op, p, history=history, time_s=1.0, max_displacement_m=2e-7, xp=np
    )


@pytest.mark.parametrize("raw", limitations(), ids=lambda r: r["name"])
def test_source_limitations_are_preserved(raw):
    native = captured(raw["name"])
    expected = raw.get(
        "expected_outcomes",
        ["captured_failure" if raw["expected_failure"] else "captured_limitation"],
    )
    assert native["status"] in expected
    if raw.get("display_only"):
        with pytest.raises(ValueError):
            mechanics.quartic_display_interpolator(
                raw["layout"]["centers_m"], raw["layout"]["vertices_m"]
            )
    elif raw["name"] == "disabled-time-zero-np-float":
        assert native["failure_type"] == "AttributeError"
        assert len(native["history_x"]) == 2
    elif raw["name"] not in (
        "steady-missing-PP",
        "time-positive-missing-history",
        "steady-unbounded-displacement",
    ):
        _, f, history, op, p = prepare(raw)
        with np.errstate(all="ignore"):
            assert not mechanics.domain_valid(
                f,
                op,
                p,
                history=history if raw["mode"] == "time" else None,
                time_s=raw["clock_s"],
                xp=np,
            )


@pytest.mark.parametrize(
    "variant",
    (
        "nan-pressure",
        "inf-E",
        "zero-shear",
        "negative-dt",
        "negative-damping",
        "nonboolean-boundary",
        "bad-operator",
        "bad-shape",
        "dirty-padding",
        "zero-limit",
    ),
)
def test_invalid_trial_rejected_without_mutation(variant):
    _, f, history, op, p = prepare(padding=2)
    if variant == "nan-pressure":
        f.pressure_Pa[0] = np.nan
    elif variant == "inf-E":
        f.electric_field_V_m[0, 0] = np.inf
    elif variant == "zero-shear":
        p = p._replace(shear_modulus_Pa=0.0)
    elif variant == "negative-dt":
        p = p._replace(dt_s=-1e-6)
    elif variant == "negative-damping":
        p = p._replace(viscous_damping_native=-0.1)
    elif variant == "nonboolean-boundary":
        p = p._replace(fixed_cluster_boundary=1)
    elif variant == "bad-operator":
        op.laplacian[0, 0] = np.nan
    elif variant == "bad-shape":
        f = f._replace(pressure_Pa=f.pressure_Pa[:-1])
    elif variant == "dirty-padding":
        f.electric_field_V_m[0, -1] = 1.0
    before = deepcopy((f, op))
    with np.errstate(all="ignore"):
        assert not mechanics.domain_valid(
            f, op, p, max_displacement_m=0.0 if variant == "zero-limit" else None, xp=np
        )
    for left, right in zip((*f, *op), (*before[0], *before[1]), strict=True):
        np.testing.assert_array_equal(left, right)


def test_padding_and_batch_parameter_axes():
    raw = next(r for r in CASES if r["name"] == "time-positive-osmotic")
    _, f, history, op, p = prepare(raw)
    _, fp, hp, opp, pp = prepare(raw, padding=2)
    left = mechanics.disabled_time_step(history, f, op, p, xp=np)
    right = mechanics.disabled_time_step(hp, fp, opp, pp, xp=np)
    close(right.history.displacement_m[..., :-2], left.history.displacement_m)
    np.testing.assert_array_equal(right.history.displacement_m[..., -2:], 0.0)
    assert mechanics.domain_valid(fp, opp, pp, history=hp, time_s=raw["clock_s"], xp=np)
    fields = mechanics.Forcing(*(np.stack((v, v * 1.2)) for v in f))
    histories = mechanics.History(*(np.stack((v, v * 0.7)) for v in history))
    params = p._replace(galvanotropism_m2_V=np.array([[1e-9], [-2e-9]]))
    batched = mechanics.disabled_time_step(histories, fields, op, params, xp=np)
    for i in range(2):
        expected = mechanics.disabled_time_step(
            mechanics.History(*(v[i] for v in histories)),
            mechanics.Forcing(*(v[i] for v in fields)),
            op,
            p._replace(galvanotropism_m2_V=[1e-9, -2e-9][i]),
            xp=np,
        )
        close(batched.history.displacement_m[i], expected.history.displacement_m)


def test_parameter_world_broadcast_preserves_restart_history_shape():
    _, f, history, op, p = prepare(next(r for r in CASES if r["name"] == "time-positive"))
    p = p._replace(galvanotropism_m2_V=np.array([[1e-9], [-2e-9]]))
    result = mechanics.disabled_time_step(history, f, op, p, xp=np)
    assert (
        result.history.displacement_m.shape
        == result.history.previous_displacement_m.shape
        == (2, 2, op.active.size)
    )
    assert mechanics.domain_valid(f, op, p, history=result.history, time_s=0.002, xp=np)


def test_dirty_osmotic_padding_and_invalid_display_are_rejected():
    raw = next(r for r in CASES if r["name"] == "osmotic-ecm")
    _, _, _, op, _ = prepare(raw, padding=1)
    cell, env, pressure, geometry, p = osmotic_inputs(raw, op)
    pressure[-1] = 1.0
    assert not mechanics.osmotic_domain_valid(cell, env, pressure, geometry, op, p, xp=np)
    raw = display_cases()[0]
    mesh = raw["layout"]
    matrix = mechanics.quartic_display_interpolator(mesh["centers_m"], mesh["vertices_m"])
    weights = np.asarray(mesh["sum_membranes"], float) / 4
    bad = np.asarray(raw["displacement_m"], float)
    bad[0, 0] = np.nan
    assert not mechanics.display_domain_valid(bad, matrix, mesh["vertices_m"], weights, xp=np)
    weights[0, 0] = -1.0
    assert not mechanics.display_domain_valid(
        raw["displacement_m"], matrix, mesh["vertices_m"], weights, xp=np
    )


def test_source_identity_disabled_flags_and_reset_contract():
    if not (folder := os.environ.get("CELLS_BETSE_DEFORMATION_NATIVE_CAPTURE")):
        pytest.skip("Bounded wrapper supplies authenticated native mechanics captures")
    directory = Path(folder)
    manifest = json.loads((directory / "source-manifest.json").read_text())
    assert manifest["component_cases"] == len(CASES) == 20
    assert manifest["display_cases"] == 4 and manifest["limitations"] == len(limitations()) == 10
    assert not manifest["production_cells_imported"] and not manifest["jax_imported"]
    assert not manifest["time_deformation_enabled"]
    for relative, sha in PROTOCOL["native_source"]["source_sha256"].items():
        assert hashlib.sha256((directory / "upstream" / relative).read_bytes()).hexdigest() == sha
    reset = json.loads((directory / "initialization-reset.json").read_text())
    np.testing.assert_array_equal(reset["initialized"]["x"], 0.0)
    np.testing.assert_array_equal(reset["after_cut_reset_x"], 3.0)
    assert reset["history_count_after_cut_reset"] == 1 and reset["separate_copy"]
    source = (ROOT / "validation/mechanics/betse_deformation_reference.py").read_text()
    assert (
        "import numpy" not in source and "import jax" not in source and "from cells" not in source
    )


def test_cpu_jax_steady_batch_and_world_isolation():
    import jax
    import jax.numpy as jnp

    _, f, _, op, p = prepare(padding=2)
    assert jax.config.x64_enabled and all(d.platform == "cpu" for d in jax.devices())
    f, op, p = (jax.tree.map(jnp.asarray, value) for value in (f, op, p))
    fields = mechanics.Forcing(*(jnp.stack((v, v)) for v in f))
    fields = fields._replace(electric_field_V_m=fields.electric_field_V_m.at[1, 0, 0].set(jnp.nan))
    valid = jax.jit(jax.vmap(lambda force: mechanics.domain_valid(force, op, p)))(fields)
    np.testing.assert_array_equal(valid, [True, False])
    result = jax.jit(jax.vmap(lambda force: mechanics.steady(force, op, p)))(fields)
    expected = mechanics.steady(jax.tree.map(np.asarray, f), op, p, xp=np)
    close(result.displacement_m[0], expected.displacement_m)
    np.testing.assert_array_equal(result.displacement_m[:, :, -2:], 0.0)


def test_cpu_jax_osmotic_clock_auxiliary():
    import jax
    import jax.numpy as jnp

    raw = next(r for r in CASES if r["name"] == "osmotic-ecm")
    _, _, _, op, _ = prepare(raw, padding=2)
    cell, env, pressure, geometry, p = osmotic_inputs(raw, op)
    op, geometry, p = (jax.tree.map(jnp.asarray, value) for value in (op, geometry, p))
    compiled = jax.jit(
        lambda c, e, pressure: (
            mechanics.osmotic_auxiliary(c, e, pressure, geometry, op, p),
            mechanics.osmotic_domain_valid(c, e, pressure, geometry, op, p),
        )
    )
    actual, valid = compiled(cell, env, pressure)
    assert valid
    expected = mechanics.osmotic_auxiliary(cell, env, pressure, geometry, op, p, xp=np)
    for left, right in zip(actual, expected, strict=True):
        close(left, right, pressure=True)
    np.testing.assert_array_equal(actual.PP_native[-2:], 0.0)


def test_cpu_jax_primed_history_restart_and_time_gradient():
    import jax
    import jax.numpy as jnp

    _, f, history, op, p, _ = modal_state(1e-6)
    f, history, op, p = (jax.tree.map(jnp.asarray, value) for value in (f, history, op, p))

    def run(state, count):
        def body(carry, _):
            result = mechanics.disabled_time_step(carry, f, op, p)
            return result.history, result.history.displacement_m

        return jax.lax.scan(body, state, xs=None, length=count)

    full, trace = jax.jit(lambda state: run(state, 8))(history)
    half, _ = jax.jit(lambda state: run(state, 4))(history)
    restarted, _ = jax.jit(lambda state: run(state, 4))(half)
    for left, right in zip(full, restarted, strict=True):
        np.testing.assert_array_equal(left, right)
    assert mechanics.domain_valid(f, op, p, history=full, time_s=8e-6)
    evidence(
        "jax-primed-restart",
        dict(
            status="passed",
            native_enabled=False,
            steps=8,
            dt_s=1e-6,
            physical_span_s=8e-6,
            exact_restart=True,
            shape=list(trace.shape),
            scope=(
                "Primed disabled source recurrence carry only; "
                "no native initialization/checkpoint migration"
            ),
        ),
    )


def test_cpu_jax_display_map_and_electric_sensitivity():
    import jax
    import jax.numpy as jnp

    raw = display_cases()[0]
    mesh = raw["layout"]
    matrix = mechanics.quartic_display_interpolator(mesh["centers_m"], mesh["vertices_m"])
    weights = np.asarray(mesh["sum_membranes"]) / 4
    compiled = jax.jit(
        lambda displacement: mechanics.display(
            displacement, jnp.asarray(matrix), jnp.asarray(mesh["vertices_m"]), jnp.asarray(weights)
        )
    )
    actual = compiled(np.asarray(raw["displacement_m"]))
    expected = reference.display_expected(raw)[0]
    close(actual.vertices_m, expected["vertices_m"], display=True)
    close(actual.cell_centres_m, expected["cell_centres_m"], display=True)
    _, f, _, op, p = prepare()
    f, op, p = (jax.tree.map(jnp.asarray, value) for value in (f, op, p))

    def scalar(galvanotropism):
        return mechanics.steady(
            f, op, p._replace(galvanotropism_m2_V=galvanotropism)
        ).displacement_m[0, 0]

    derivative = float(jax.jit(jax.grad(scalar))(p.galvanotropism_m2_V))
    close(derivative, f.electric_field_V_m[0, 0], auxiliary=True)
    evidence(
        "jax-sensitivity",
        dict(
            status="passed",
            derivative_m_per_galvanotropism=derivative,
            expected_electric_field_V_m=float(f.electric_field_V_m[0, 0]),
        ),
    )
