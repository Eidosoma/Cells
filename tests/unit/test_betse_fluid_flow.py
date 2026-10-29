"""Native flow correspondence, explicit units/owners, defects and CPU JAX."""

import hashlib
import json
import os
from copy import deepcopy
from math import cos, log2, pi
from pathlib import Path

import numpy as np
import pytest

from cells.processes import betse_deformation as mechanics
from cells.processes import betse_fluid_flow as flow
from cells.processes import betse_geometry as geometry
from validation.flow import betse_fluid_flow_reference as reference
from validation.flow.betse_fluid_flow_fixtures import (
    base,
    cases,
    cell_refinement,
    environment_refinement,
    limitations,
)

ROOT = Path(__file__).resolve().parents[2]
PROTOCOL = json.loads((ROOT / "validation/flow/betse_fluid_flow_protocol.json").read_text())


def captured(name):
    if not (folder := os.environ.get("CELLS_BETSE_FLOW_NATIVE_CAPTURE")):
        pytest.skip("Bounded wrapper supplies authenticated native flow captures")
    return json.loads((Path(folder) / (name + ".json")).read_text())


def evidence(name, data):
    if folder := os.environ.get("CELLS_COMPONENT_EVIDENCE"):
        path = Path(folder)
        path.mkdir(parents=True, exist_ok=True)
        (path / ("betse-fluid-flow-" + name + ".json")).write_text(
            json.dumps({**data, "status": "passed"}, indent=2, allow_nan=False) + "\n"
        )


def prepare(raw=None):
    raw = deepcopy(base() if raw is None else raw)
    mesh = raw["layout"]
    op = mechanics.bind_operators(
        *(
            mesh[k]
            for k in (
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
        )
    )
    cb = flow.bind_cells(
        raw["cell_ids"], op, dict(fixture=raw["name"], operator_law=mechanics.LAW_ID)
    )
    cf = flow.CellForcing(np.asarray(raw["cell_E_V_m"]), np.asarray(raw["cell_rho_C_m3"]))
    cp = flow.CellParameters(raw["viscosity_Pa_s"], raw["gj_fraction"])
    env = None
    if raw["is_ecm"]:
        ny, nx = raw["shape"]
        x0, _, y0, _ = raw["bounds_m"]
        h = raw["delta_m"]
        grid = geometry.bind_grid(
            geometry.GridSpec(
                tuple(raw["environment_ids"]),
                (ny, nx),
                tuple(raw["bounds_m"]),
                h,
                [[x0 + (j + 0.5) * h, y0 + (i + 0.5) * h] for i in range(ny) for j in range(nx)],
                dict.fromkeys("NSEW", "value"),
                dict(fixture=raw["name"]),
            )
        )
        eb = flow.bind_environment(grid)
        ef = flow.EnvironmentForcing(
            *(
                np.asarray(raw[k])
                for k in ("environment_E_V_m", "environment_potential_V", "diffusion_weight")
            )
        )
        ep = flow.EnvironmentParameters(
            raw["viscosity_Pa_s"], raw["epsilon_F_m"], raw["relative_permittivity"]
        )
        env = (ef, eb, ep)
    return raw, cf, cb, cp, env


def run(raw=None):
    _, cf, cb, cp, env = prepare(raw)
    return flow.flow(cf, cb, cp, fluid_flow=True, environment=env)


def close(actual, expected, key="", refinement=False):
    if refinement:
        atol = 2e-11
    elif "divergence" in key:
        atol = 2e-20
    elif "native" in key:
        atol = 3e-30
    elif "force" in key:
        atol = 3e-21
    else:
        atol = 3e-24
    np.testing.assert_allclose(actual, expected, rtol=8e-12, atol=atol)


@pytest.mark.parametrize("raw", cases(), ids=lambda r: r["name"])
def test_native_and_independent_flow_correspondence(raw):
    native, expected, result = captured(raw["name"]), reference.evaluate(raw), run(raw)
    assert native["status"] == "passed" and native["cell_hh_kwargs"] == dict(rot_only=True)
    for domain, value in zip(("cells", "environment"), result, strict=True):
        if value is None:
            assert domain == "environment" and "environment" not in native
            continue
        for key, actual in value._asdict().items():
            close(actual, expected[domain][key], key)
            if key in native[domain]:
                close(actual, native[domain][key], key)
    evidence(
        raw["name"],
        dict(
            native_status=native["status"],
            cell_peak_m_s=float(np.max(np.abs(result.cells.velocity_m_s))),
            ecm_peak_native_m3_s=float(np.max(np.abs(result.environment.output_native_m3_s)))
            if result.environment
            else None,
        ),
    )


def test_authenticated_source_and_real_reachability():
    native = captured("source-manifest")
    assert native["status"] == "passed" and native["version"] == "1.5.0"
    assert native["revision"] == PROTOCOL["native_source"]["revision"]
    assert not any(
        native[k]
        for k in (
            "full_simulator",
            "production_cells_imported",
            "jax_imported",
            "geometry_generation_or_cut_executed",
        )
    )
    assert len(native["executed_bodies"]) == 9
    for name, sha in PROTOCOL["native_source"]["source_sha256"].items():
        assert native["files"][name] == dict(sha256=sha, checkout_match=True)
        path = Path(os.environ["CELLS_BETSE_FLOW_NATIVE_CAPTURE"]) / "upstream" / name
        assert hashlib.sha256(path.read_bytes()).hexdigest() == sha
    reach = native["reachability"]
    assert len(reach["normal_getFlow_calls"]) == 1 and reach["fast_getFlow_calls"] == []
    assert (
        reach["normal_update_ecm_line"]
        < reach["normal_getFlow_calls"][0]
        < reach["normal_update_voltage_line"]
    )
    assert reach["initial_update_voltage_line"] < reach["normal_getFlow_calls"][0]
    assert "p.td_deform" in reach["graph_initialization_source"]
    assert {"recalculate fluid", "recalculate fluid flow"} == {
        s
        for s in ("recalculate fluid", "recalculate fluid flow")
        if any(repr(s) in row["source"] for row in reach["grn_loader_assignments"])
    }
    assert reach["pressure_names_in_getFlow"] == []
    assert not {"P_cells", "PP", "osmo_P_cell", "osmo_P_env", "lapENV_P_inv"}.intersection(
        reach["attributes_in_getFlow"]
    )
    evidence(
        "source-reachability",
        dict(
            source_files=len(native["files"]),
            executed_bodies=native["executed_bodies"],
            reachability=reach,
        ),
    )


def test_disabled_loader_missing_inverse_partial_writes_and_lag():
    policy = captured("caller-policy")
    assert policy["source_fluid_flow"] is False and policy["source_viscosity_Pa_s"] == 0.01
    assert policy["source_td_deform"] is False
    assert policy["disabled_writes_unchanged"]
    assert policy["initialized"]["cell_inverse"] is None
    assert policy["missing_inverse"]["type"] == "TypeError"
    assert policy["missing_inverse"]["ecm_written_before_cell_failure"]
    assert not np.any(policy["consumer_before"]) and np.any(policy["consumer_after"])
    assert not np.any(policy["consumer_disabled"])
    assert flow.flow(None, None, None) is None
    with pytest.raises(ValueError):
        flow.flow(None, None, None, fluid_flow=1)
    evidence("policy-and-lag", policy)


@pytest.mark.parametrize("raw", limitations(), ids=lambda r: r["name"])
def test_native_failures_and_invalid_numeric_domains_remain_recorded(raw):
    native = captured(raw["name"])
    defect = raw["defect"]
    exceptions = {
        "missing-cell-inverse": "TypeError",
        "missing-environment-inverse": "TypeError",
        "zero-viscosity": "ZeroDivisionError",
        "bad-cell-field-axis": "ValueError",
        "bad-ecm-voltage-axis": "ValueError",
        "missing-charge-owner": "AttributeError",
    }
    if defect in exceptions:
        assert (
            native["status"] == "source-exception"
            and native["exception"]["type"] == exceptions[defect]
        )
    elif defect.startswith("nan-"):
        assert native["status"] == "source-nonfinite"
    else:
        assert (
            native["status"] == "passed"
        )  # Native accepts signed coefficients; scoped domains reject.
    if defect in (
        "zero-viscosity",
        "negative-viscosity",
        "negative-gap-fraction",
        "negative-weight",
    ):
        with pytest.raises(ValueError):
            run(raw)
    evidence(
        defect,
        dict(
            native_status=native["status"],
            exception=native.get("exception"),
            warnings=native["warnings"],
        ),
    )


def test_pressure_is_external_and_not_a_flow_input():
    a, b = (
        run(raw)
        for raw in (base(), next(v for v in cases() if v["name"] == "pressure-changed-unused"))
    )
    for left, right in zip(a.cells, b.cells, strict=True):
        np.testing.assert_array_equal(left, right)
    for left, right in zip(a.environment, b.environment, strict=True):
        np.testing.assert_array_equal(left, right)
    assert "pressure_Pa" not in flow.CellForcing._fields
    assert "pressure" not in " ".join(flow.EnvironmentResult._fields)


@pytest.mark.parametrize(
    "name,cell_scale,ecm_scale",
    [
        ("viscosity-double", 0.5, 0.5),
        ("gap-fraction-double", 2.0, 1.0),
        ("gap-fraction-zero", 0.0, 1.0),
        ("permittivity-double", 1.0, 2.0),
        ("charge-reversed", -1.0, 1.0),
        ("electric-reversed", -1.0, -1.0),
        ("ecm-weight-zero", 1.0, 0.0),
        ("zero-electric", 0.0, 0.0),
    ],
)
def test_physical_parameter_sign_and_scaling(name, cell_scale, ecm_scale):
    a, b = run(), run(next(v for v in cases() if v["name"] == name))
    close(b.cells.velocity_m_s, cell_scale * a.cells.velocity_m_s)
    close(b.environment.output_native_m3_s, ecm_scale * a.environment.output_native_m3_s, "native")


def test_ecm_voltage_gauge_and_length_dimension_defects_are_explicit():
    a = run()
    offset = run(next(v for v in cases() if v["name"] == "ecm-potential-offset"))
    scaled = run(next(v for v in cases() if v["name"] == "geometry-scaled-two"))
    delta = float(
        np.max(np.abs(offset.environment.output_native_m3_s - a.environment.output_native_m3_s))
    )
    assert delta > 1e-22
    close(scaled.environment.slip_velocity_m_s, a.environment.slip_velocity_m_s, "native")
    close(scaled.environment.output_native_m3_s, 4 * a.environment.output_native_m3_s, "native")
    close(
        scaled.environment.stream_potential_native_m4_s,
        8 * a.environment.stream_potential_native_m4_s,
        "native",
    )
    close(scaled.cells.velocity_m_s, 4 * a.cells.velocity_m_s)
    evidence(
        "dimensions-and-offset",
        dict(
            offset_output_change_native_m3_s=delta,
            length_factor=2,
            output_factor=4,
            stream_factor=8,
            ecm_output_unit="m3/s",
            cell_output_unit="m/s",
        ),
    )


def test_ecm_boundary_is_not_no_slip_and_discarded_potential_is_nonzero():
    result = run().environment
    output, div = result.output_native_m3_s, result.divergence_numeric_m2_s
    tangent = np.concatenate((output[0, 0, :], output[0, -1, :], output[1, :, 0], output[1, :, -1]))
    normal = np.concatenate((output[1, 0, :], output[1, -1, :], output[0, :, 0], output[0, :, -1]))
    assert np.max(np.abs(tangent)) > 1e-22
    assert np.max(np.abs(normal)) < 1e-30
    assert np.max(np.abs(div)) > 1e-18
    assert np.max(np.abs(div[1:-1, 1:-1])) < 1e-25
    assert np.max(np.abs(result.discarded_scalar_native_m4_s)) > 1e-27
    evidence(
        "boundary-and-discarded-scalar",
        dict(
            tangent_peak_native_m3_s=float(np.max(np.abs(tangent))),
            normal_peak_native_m3_s=float(np.max(np.abs(normal))),
            boundary_divergence_peak_native_m2_s=float(np.max(np.abs(div))),
            interior_divergence_peak_native_m2_s=float(np.max(np.abs(div[1:-1, 1:-1]))),
            discarded_scalar_peak_native_m4_s=float(
                np.max(np.abs(result.discarded_scalar_native_m4_s))
            ),
        ),
    )


def test_two_rows_make_source_rotation_identically_zero():
    raw = next(v for v in cases() if v["name"] == "two-by-three-grid")
    result = run(raw).environment
    assert np.any(result.unprojected_native_m3_s)
    assert not np.any(result.output_native_m3_s)


def test_cell_manufactured_refinement_retains_quarter_stokes_gain():
    records = []
    for raw in cell_refinement():
        native = captured(raw["name"])
        actual = run(raw).cells.velocity_m_s
        close(actual, native["cells"]["velocity_m_s"], refinement=True)
        expected = reference.evaluate(raw)["cells"]["velocity_m_s"]
        np.testing.assert_allclose(actual, expected, rtol=8e-12, atol=2e-20)
        n = len(raw["cell_ids"])
        k = 2 * pi / 1e-3
        continuum = np.asarray([[0.0] * n, [cos(2 * pi * i / n) / (4 * k * k) for i in range(n)]])
        error = float(np.max(np.abs(actual - continuum)))
        gain = float(actual[1, 0] * k * k)
        theta = 2 * pi / n
        close(gain, theta**2 * (cos(theta / 2) / np.sin(theta / 2)) ** 2 / 16, refinement=True)
        records.append(dict(n=n, error_m_s=error, gain_relative_to_force_over_k2=gain))
    orders = [
        log2(a["error_m_s"] / b["error_m_s"])
        for a, b in zip(records[:-1], records[1:], strict=True)
    ]
    assert min(orders) > 1.95 and max(orders) < 2.05
    assert records[-1]["gain_relative_to_force_over_k2"] < 0.25
    evidence(
        "cell-refinement",
        dict(
            records=records,
            orders=orders,
            target_gain=0.25,
            claim=(
                "Manufactured periodic strip/source operator only; no physical Stokes convergence"
            ),
        ),
    )


def test_ecm_manufactured_refinement_and_actual_native_results():
    records = []
    for raw in environment_refinement():
        actual = run(raw).environment
        native = captured(raw["name"])["environment"]
        h = raw["delta_m"]
        for key, value in native.items():
            # Compare auxiliaries in the output-field unit. Otherwise a fixed
            # m3/s tolerance is incorrectly imposed on m2/s derivatives or
            # m4/s potentials, amplifying harmless SVD/derivative cancellation.
            scale = h if "divergence" in key else 1 / h if "m4_s" in key else 1.0
            close(scale * getattr(actual, key), scale * np.asarray(value), refinement=True)
        close(actual.unprojected_native_m3_s, raw["manufactured_raw"], refinement=True)
        if raw["shape"][0] == 5:
            expected = reference.environment(raw)
            for key, value in actual._asdict().items():
                close(value, expected[key], refinement=True)
        error = float(
            np.max(np.abs(actual.output_native_m3_s - np.asarray(raw["manufactured_output"])))
        )
        n = raw["shape"][0]
        theta = pi / (n - 1)
        # Both the input curl and output gradient use the discrete first
        # derivative sin(theta)/h; divide by the two-dimensional Laplacian.
        ratio = cos(theta / 2) ** 2
        close(
            actual.output_native_m3_s,
            ratio * np.asarray(raw["manufactured_output"]),
            refinement=True,
        )
        records.append(
            dict(n=n, error_native_m3_s=error, boundary_centres_span_m=1e-3, native_gain=ratio)
        )
    orders = [
        log2(a["error_native_m3_s"] / b["error_native_m3_s"])
        for a, b in zip(records[:-1], records[1:], strict=True)
    ]
    assert min(orders) > 1.94 and max(orders) < 2.05
    evidence(
        "ecm-refinement",
        dict(
            records=records,
            orders=orders,
            claim=(
                "Manufactured numerical native m3/s field; "
                "boundary-centre domain, not physical fluid velocity"
            ),
        ),
    )


def test_owner_bindings_are_immutable_and_order_explicit():
    raw, _, cb, _, env = prepare()
    assert cb.owner_ids == tuple(raw["cell_ids"]) and env[1].owner_ids == tuple(
        raw["environment_ids"]
    )
    with pytest.raises(ValueError):
        cb.operators.laplacian_inverse[0, 0] = 1.0
    reversed_binding = flow.bind_cells(
        cb.owner_ids[::-1], cb.operators, json.loads(cb.provenance_json)
    )
    assert reversed_binding.identity != cb.identity
    with pytest.raises(ValueError):
        flow.bind_cells(["same"] * len(cb.owner_ids), cb.operators, {"a": 1})
    with pytest.raises(ValueError):
        flow.bind_cells(cb.owner_ids, cb.operators, {})
    with pytest.raises(ValueError):
        flow.bind_cells(cb.owner_ids[:-1], cb.operators, {"a": 1})
    with pytest.raises(ValueError):
        flow.bind_environment(None)


@pytest.mark.parametrize(
    "defect",
    ["nan-e", "nan-rho", "zero-mu", "negative-mu", "nan-mu", "negative-fraction", "large-fraction"],
)
def test_cell_numeric_domain_predicate(defect):
    _, cf, cb, cp, _ = prepare()
    if defect == "nan-e":
        cf.electric_field_V_m[0, 0] = np.nan
    if defect == "nan-rho":
        cf.charge_density_C_m3[0] = np.nan
    if defect.endswith("mu"):
        cp = cp._replace(
            viscosity_Pa_s={"zero-mu": 0.0, "negative-mu": -1.0, "nan-mu": np.nan}[defect]
        )
    if defect == "negative-fraction":
        cp = cp._replace(gap_junction_fraction=-0.1)
    if defect == "large-fraction":
        cp = cp._replace(gap_junction_fraction=1.1)
    assert not flow.cell_valid(cf, cb.operators, cp, xp=np)
    with pytest.raises(ValueError):
        flow.flow(cf, cb, cp, fluid_flow=True)


@pytest.mark.parametrize(
    "defect", ["nan-e", "nan-phi", "negative-weight", "zero-epsilon", "zero-h", "nan-inverse"]
)
def test_environment_numeric_domain_predicate(defect):
    _, _, _, _, (ef, eb, ep) = prepare()
    op = eb.operators
    if defect == "nan-e":
        ef.electric_field_V_m[0, 0, 0] = np.nan
    if defect == "nan-phi":
        ef.potential_V[0, 0] = np.nan
    if defect == "negative-weight":
        ef.diffusion_weight[0, 0] = -1
    if defect == "zero-epsilon":
        ep = ep._replace(vacuum_permittivity_F_m=0)
    if defect == "zero-h":
        op = op._replace(delta_m=0)
    if defect == "nan-inverse":
        op = op._replace(laplacian_inverse_m2=np.full_like(op.laplacian_inverse_m2, np.nan))
    assert not flow.environment_valid(ef, op, ep, xp=np)


def test_wrong_owner_axes_are_rejected_without_broadcast_repair():
    _, cf, cb, cp, (ef, eb, ep) = prepare()
    with pytest.raises(ValueError):
        flow.cell_flow(cf._replace(charge_density_C_m3=np.ones(1)), cb.operators, cp, xp=np)
    with pytest.raises(ValueError):
        flow.cell_flow(cf, cb.operators, cp._replace(viscosity_Pa_s=np.ones(6)), xp=np)
    with pytest.raises(ValueError):
        flow.environment_flow(ef._replace(potential_V=np.ones(20)), eb.operators, ep, xp=np)
    with pytest.raises(ValueError):
        flow.environment_flow(ef, eb.operators._replace(laplacian_inverse_m2=None), ep, xp=np)
    with pytest.raises(ValueError):
        flow.environment_flow(
            ef._replace(electric_field_V_m=np.ones((2, 1, 20))), eb.operators, ep, xp=np
        )


@pytest.mark.parametrize("name", ["grn-current", "grn-negative-mean-valence"])
def test_actual_separate_grn_formula(name):
    native = captured(name)
    f = native["input"]
    args = tuple(f[k] for k in ("current_A_m2", "concentration_mol_m3", "valence", "faraday_C_mol"))
    actual = flow.grn_current_flow(*args, xp=np)
    assert flow.grn_valid(*args, xp=np) and native["fluid_flow"] is True
    close(actual, native["output"], refinement=True)
    current, c, z, F = (np.asarray(v) for v in args)
    # Independent scalar loops over the declared species/site axes.
    expected = [
        [
            [
                -current[a, i, j] / (float(F) * (sum(c[:, i, j]) / len(z)) * (sum(z) / len(z)))
                for j in range(5)
            ]
            for i in range(4)
        ]
        for a in range(2)
    ]
    close(actual, expected, refinement=True)
    evidence(name, dict(peak_velocity_m_s=float(np.max(np.abs(actual))), native_enabled_flag=True))


@pytest.mark.parametrize("name", ["grn-zero-mean-valence", "grn-zero-concentration"])
def test_actual_grn_singular_denominators_are_not_floored(name):
    native = captured(name)
    f = native["input"]
    args = tuple(f[k] for k in ("current_A_m2", "concentration_mol_m3", "valence", "faraday_C_mol"))
    with np.errstate(all="ignore"):
        assert not flow.grn_valid(*args, xp=np)
        assert not np.all(np.isfinite(flow.grn_current_flow(*args, xp=np)))
    assert native["status"] == "source-nonfinite" and native["fluid_flow"] is True
    evidence(name, dict(native_status=native["status"], warnings=native["warnings"]))


def test_jax_cpu_jit_batch_domains_and_world_order():
    import jax
    import jax.numpy as jnp

    assert jax.default_backend() == "cpu" and jax.config.x64_enabled
    _, cf, cb, cp, (ef, eb, ep) = prepare()
    scales = np.asarray([0.0, 1.0, -2.0])
    cfb = flow.CellForcing(scales[:, None, None] * cf.electric_field_V_m, cf.charge_density_C_m3)
    efb = ef._replace(electric_field_V_m=scales[:, None, None, None] * ef.electric_field_V_m)
    cfun = jax.jit(lambda f: flow.cell_flow(f, cb.operators, cp))
    efun = jax.jit(lambda f: flow.environment_flow(f, eb.operators, ep))
    cresult, eresult = cfun(cfb), efun(efb)
    for i, scale in enumerate(scales):
        close(
            cresult.velocity_m_s[i],
            scale * flow.cell_flow(cf, cb.operators, cp, xp=np).velocity_m_s,
        )
        close(
            eresult.output_native_m3_s[i],
            scale * flow.environment_flow(ef, eb.operators, ep, xp=np).output_native_m3_s,
            "native",
        )
    reversed_result = efun(efb._replace(electric_field_V_m=efb.electric_field_V_m[::-1]))
    close(reversed_result.output_native_m3_s, eresult.output_native_m3_s[::-1], "native")
    invalid = flow.CellParameters(np.asarray([[0.01], [0.0], [-0.01]]), 5e-8)
    np.testing.assert_array_equal(
        jax.jit(lambda f, p: flow.cell_valid(f, cb.operators, p))(cfb, invalid),
        [True, False, False],
    )
    einvalid = ep._replace(viscosity_Pa_s=jnp.asarray([[0.01], [0.0], [-0.01]]))
    np.testing.assert_array_equal(
        jax.jit(lambda f, p: flow.environment_valid(f, eb.operators, p))(efb, einvalid),
        [True, False, False],
    )
    evidence(
        "jax-batch",
        dict(
            backend=jax.default_backend(),
            worlds=3,
            valid=[True, False, False],
            reordered_equivalence=True,
        ),
    )


def test_jax_finite_zero_forcing_derivatives_and_linear_response():
    import jax
    import jax.numpy as jnp

    _, cf, cb, cp, (ef, eb, ep) = prepare()

    def cfun(e):
        return flow.cell_flow(cf._replace(electric_field_V_m=e), cb.operators, cp).velocity_m_s

    def efun(e):
        return flow.environment_flow(
            ef._replace(electric_field_V_m=e), eb.operators, ep
        ).output_native_m3_s

    cjac = jax.jit(jax.jacfwd(cfun))(jnp.zeros_like(cf.electric_field_V_m))
    ejac = jax.jit(jax.jacfwd(efun))(jnp.zeros_like(ef.electric_field_V_m))
    assert np.all(np.isfinite(cjac)) and np.all(np.isfinite(ejac))
    close(jnp.einsum("abij,ij->ab", cjac, cf.electric_field_V_m), cfun(cf.electric_field_V_m))
    close(
        jnp.einsum("abcijk,ijk->abc", ejac, ef.electric_field_V_m),
        efun(ef.electric_field_V_m),
        "native",
    )
    phi_zero = jax.jit(
        jax.jacfwd(
            lambda phi: (
                flow.environment_flow(
                    ef._replace(potential_V=phi), eb.operators, ep
                ).output_native_m3_s
            )
        )
    )(jnp.zeros_like(ef.potential_V))
    assert np.all(np.isfinite(phi_zero)) and np.any(np.asarray(phi_zero) != 0)
    evidence(
        "jax-derivatives",
        dict(
            finite_cell_zero_E=True,
            finite_ecm_zero_E=True,
            finite_zero_potential=True,
            ecm_nonzero_potential_derivative=True,
        ),
    )


def test_jax_stateless_forcing_sequence_split_has_no_hidden_history():
    import jax
    import jax.numpy as jnp

    _, cf, cb, cp, _ = prepare()
    scales = jnp.asarray([0.0, 1.0, -1.0, 2.0, 0.5, -0.3, 0.0])
    kernel = jax.jit(
        lambda values: jax.vmap(
            lambda a: (
                flow.cell_flow(
                    cf._replace(electric_field_V_m=a * cf.electric_field_V_m), cb.operators, cp
                ).velocity_m_s
            )
        )(values)
    )
    full = kernel(scales)
    split = jnp.concatenate((kernel(scales[:3]), kernel(scales[3:])), axis=0)
    close(full, split)
    np.testing.assert_array_equal(full[0], full[-1])
    evidence(
        "jax-stateless-sequence",
        dict(
            snapshots=7,
            split_after=3,
            exact_equal=bool(np.array_equal(full, split)),
            max_batch_roundoff_m_s=float(np.max(np.abs(np.asarray(full - split)))),
            claim=(
                "Independent forcing snapshots; "
                "no dynamic/checkpoint or physical elapsed-time claim"
            ),
        ),
    )


def test_jax_grn_current_formula_and_singular_mean_valence():
    import jax
    import jax.numpy as jnp

    raw = captured("grn-current")["input"]
    current, c, z, F = (
        jnp.asarray(raw[k])
        for k in ("current_A_m2", "concentration_mol_m3", "valence", "faraday_C_mol")
    )
    fn = jax.jit(flow.grn_current_flow)
    close(fn(current, c, z, F), flow.grn_current_flow(current, c, z, F, xp=np), refinement=True)
    valid = jax.jit(flow.grn_valid)
    assert valid(current, c, z, F)
    assert not valid(current, c, jnp.asarray([1.0, -1.0]), F)
    jac = jax.jit(jax.jacfwd(lambda v: flow.grn_current_flow(v, c, z, F)))(jnp.zeros_like(current))
    assert np.all(np.isfinite(jac))
    evidence(
        "jax-grn",
        dict(
            valid_formula=True,
            zero_mean_valence_rejected=True,
            finite_zero_current_derivatives=True,
        ),
    )
