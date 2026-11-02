"""Independent sign, unit, conservation and refusal checks for the bridge."""

from collections.abc import Mapping
from dataclasses import fields, is_dataclass
from fractions import Fraction
from types import SimpleNamespace

import numpy as np
import pytest

from cells.processes import betse_normal_current as current
from cells.processes import rectangular_current_transfer as transfer
from cells.processes import rectangular_environment as field
from cells.processes import rectangular_membrane_coupling as membrane
from tests.unit.test_rectangular_environment import exact_four, spec
from tests.unit.test_rectangular_environment import save as save_arrays


def policy():
    return dict(
        conductivity_S_m=2.0,
        depth_m=0.25,
        max_iterations=32,
        field_rtol=2e-12,
        transfer_rtol=2e-12,
    )


def binding(areas=(0.5, 2.0, 1.0, 4.0, 1.0), *, sharpness=0.5, surface_scale=1.0, F=2.0):
    return current.bind(
        dict(
            kind=current.INPUT_KIND,
            provenance="Declared arithmetic membrane component; no native tissue owner",
            geometry=dict(
                cell_ids=("inside:0", "inside:1"),
                membrane_ids=tuple(f"membrane:{i}" for i in range(5)),
                owner=[0, 0, 1, 1, 1],
                membrane_area_m2=areas,
                cell_area_m2=[sum(areas[:2]) * surface_scale, sum(areas[2:]) * surface_scale],
                normal_xy=[[1, 0], [-1, 0], [1, 0], [0, 1], [-1, 0]],
            ),
            ions=dict(ids=("cation", "anion", "neutral"), valence=[1, -1, 0]),
            parameters=dict(F_C_mol=F, sharpness_cell=sharpness),
        )
    )


def inputs(b, *, density=None, junction_scale=1.0):
    if density is None:
        flux = np.array([[1, -2, 3, -4, 5], [0.5, -1, 2, -2, 5], [99] * 5], dtype=float)
        extra = np.array([3.0, -1.0, 1.0, -4.5, 0.0])
    else:
        flux = np.zeros((3, 5))
        extra = np.asarray(density, dtype=float)
    return current.inputs(
        b,
        np.zeros((3, 2)),
        flux,
        np.array([[2, -1, 3, -2, 1], [0] * 5, [7] * 5], dtype=float) * junction_scale,
        np.zeros(2),
        extra,
    )


def mapped(b, grid, targets=(0, 0, 1, 3, 2)):
    return transfer.bind(
        grid,
        source_ids=b.membrane_ids,
        target_environment_ids=tuple(grid.environment_ids[i] for i in targets),
    )


def save(name, result, **metadata):
    def flatten(prefix, value):
        if is_dataclass(value):
            for f in fields(value):
                flatten(prefix + "_" + f.name, getattr(value, f.name))
        elif hasattr(value, "_asdict"):
            for key, part in value._asdict().items():
                flatten(prefix + "_" + key, part)
        elif isinstance(value, Mapping):
            for key, part in value.items():
                flatten(prefix + "_" + key, part)
        else:
            metadata[prefix] = np.asarray(value)

    flatten("result", result)
    metadata["usable"] = np.asarray(result.usable)
    save_arrays("membrane-" + name, **metadata)


@pytest.mark.parametrize("dx,dy", [(1.0, 1.0), (2.0, 0.5), (0.5, 1.25)])
def test_flux_charge_area_and_voltage_match_exact_reference(dx, dy):
    b = binding()
    source = inputs(b)
    grid = field.bind_metric(spec(dx=dx, dy=dy))
    mapping = mapped(b, grid)
    before = current.record((current.binding_record(b), source))
    expected_density = [
        -Fraction(b.kernel.F_C_mol)
        * sum(
            Fraction(float(z)) * Fraction(float(v))
            for z, v in zip(b.kernel.valence, row, strict=True)
        )
        + Fraction(float(extra))
        for row, extra in zip(
            source.membrane_flux_mol_m2_s.T, source.extra_current_A_m2, strict=True
        )
    ]
    expected_current = [
        j * Fraction(float(a))
        for j, a in zip(expected_density, b.kernel.membrane_area_m2, strict=True)
    ]
    assert expected_current == list(map(Fraction, (1, 2, -1, -2, 0)))
    volume = Fraction(dx) * Fraction(dy) * Fraction(1, 4)
    expected_phi = exact_four(
        1 / Fraction(dx) ** 2,
        1 / Fraction(dy) ** 2,
        [-Fraction(i) / (2 * volume) for i in (3, -1, 0, -2)],
    )
    result = membrane.solve(b, source, mapping, grid, **policy())
    save(
        f"exact-{dx}-{dy}",
        result,
        exact_density=list(map(str, expected_density)),
        exact_current=list(map(str, expected_current)),
        exact_voltage=list(map(str, expected_phi)),
    )
    assert result.usable and result.current.source is source
    assert result.membrane_area_m2 is b.kernel.membrane_area_m2
    assert before == current.record((current.binding_record(b), source))
    np.testing.assert_array_equal(result.outward_current_A, list(map(float, expected_current)))
    np.testing.assert_allclose(
        result.field.field.fields.potential_V, list(map(float, expected_phi)), rtol=2e-12
    )
    assert sum(expected_current) == 0
    assert result.field.deposition.total_input_A == result.field.deposition.total_accumulated_A == 0
    # Volume division, reduction of four terms, and multiplication need not
    # return exact zero. Bound those six rounded operations independently of
    # the production conservation tolerance; retain the actual residual.
    epsilon = Fraction(1, 2**52)
    gamma6 = 6 * epsilon / (1 - 6 * epsilon)
    roundoff_bound = gamma6 * sum(map(abs, expected_current))
    assert abs(Fraction(float(result.field.deposition.total_grid_A))) <= roundoff_bound
    assert result.field.site_power_W == pytest.approx(
        float(result.field.field.fields.dissipation_W), rel=2e-12
    )
    assert not np.array_equal(
        result.outward_current_A, -result.current.values.inward_membrane_current_A
    )


def test_junctions_and_smoothing_do_not_become_environment_injection():
    grid = field.bind_metric(spec())
    a, b = binding(sharpness=0.25), binding(sharpness=1.0, surface_scale=2.0)
    left = membrane.solve(a, inputs(a, junction_scale=0), mapped(a, grid), grid, **policy())
    right = membrane.solve(b, inputs(b, junction_scale=19), mapped(b, grid), grid, **policy())
    save("without-junctions", left)
    save("changed-junctions-and-smoothing", right)
    assert left.usable and right.usable
    assert not np.array_equal(
        left.current.values.normal_current_A_m2, right.current.values.normal_current_A_m2
    )
    assert np.any(right.current.diagnostics["smoothing_current_difference_A"] != 0)
    np.testing.assert_array_equal(left.outward_current_A, right.outward_current_A)
    np.testing.assert_array_equal(
        left.field.field.fields.potential_V, right.field.field.fields.potential_V
    )


def test_current_evaluated_once_and_field_budget_is_not_retried(monkeypatch):
    b, grid = binding(), field.bind_metric(spec())
    source, calls = inputs(b), []
    evaluate = current.evaluate

    def observed(*args):
        calls.append(args)
        return evaluate(*args)

    monkeypatch.setattr(current, "evaluate", observed)
    opts = policy()
    opts["max_iterations"] = 0
    result = membrane.solve(b, source, mapped(b, grid), grid, **opts)
    save("no-retry", result)
    assert len(calls) == 1 and calls[0][0] is b and calls[0][1] is source
    assert result.area_conversion_ok and not result.usable
    assert result.field.field.linear_solve.iterations == 0


@pytest.mark.parametrize("kind", ["order", "missing", "different_grid"])
def test_wrong_assignment_refuses_before_current_evaluation(monkeypatch, kind):
    b, grid = binding(), field.bind_metric(spec())
    link = mapped(b, grid)
    if kind == "different_grid":
        grid = field.bind_metric(spec(dx=2.0))
    else:
        ids = b.membrane_ids[::-1] if kind == "order" else b.membrane_ids[:-1]
        link = transfer.bind(
            grid, source_ids=ids, target_environment_ids=(grid.environment_ids[0],) * len(ids)
        )

    def forbidden(*args):
        pytest.fail("Wrong membrane assignments must refuse before current work")

    monkeypatch.setattr(current, "evaluate", forbidden)
    with pytest.raises(ValueError):
        membrane.solve(b, inputs(b), link, grid, **policy())
    save_arrays("membrane-wrong-map-" + kind, refusal=True, mapping_identity=link.identity)


@pytest.mark.parametrize(
    "kind", ["lost_zero", "subnormal_density", "subnormal_area", "subnormal_output", "overflow"]
)
def test_raw_area_conversion_refusal_survives_downstream_result(kind):
    area, density = {
        "lost_zero": (1e-100, 1e-300),
        "subnormal_density": (1e300, 1e-310),
        "subnormal_area": (1e-310, 1e300),
        "subnormal_output": (1e-110, 1e-200),
        "overflow": (1e200, 1e200),
    }[kind]
    b, grid = binding((area,) * 5), field.bind_metric(spec())
    signed = np.array([density, -density, 0, 0, 0])
    source = inputs(b, density=signed, junction_scale=0)
    if kind == "overflow":
        source = current.inputs(
            b,
            source.cell_mol_m3,
            source.membrane_flux_mol_m2_s,
            np.array([-signed / 2, np.zeros(5), np.zeros(5)]),
            source.extra_charge_C_m3,
            signed,
        )
    with np.errstate(all="ignore"):
        expected = signed * area
        result = membrane.solve(b, source, mapped(b, grid, (0, 3, 1, 2, 2)), grid, **policy())
    save("conversion-" + kind, result, expected_current=expected)
    assert not result.area_conversion_ok and not result.usable
    np.testing.assert_array_equal(
        result.outward_current_A.view(np.uint64), expected.view(np.uint64)
    )
    if kind == "lost_zero":
        assert result.field.usable and np.all(result.outward_current_A == 0)
    elif kind in ("subnormal_density", "subnormal_area"):
        assert result.field.usable


def test_unbalanced_membrane_source_remains_a_field_refusal():
    b, grid = binding(), field.bind_metric(spec())
    source = inputs(b, density=np.ones(5), junction_scale=0)
    result = membrane.solve(b, source, mapped(b, grid), grid, **policy())
    save("unbalanced", result)
    assert result.area_conversion_ok and result.field.deposition.usable
    assert not result.field.field.source_compatible and not result.usable
    np.testing.assert_array_equal(result.outward_current_A, b.kernel.membrane_area_m2)


def test_downstream_metadata_refusal_retains_complete_current_and_cause():
    b, grid = binding(), field.bind_metric(spec())
    source = inputs(b)
    opts = policy()
    opts["conductivity_S_m"] = 0.0
    with pytest.raises(membrane.MembraneCouplingRejected) as raised:
        membrane.solve(b, source, mapped(b, grid), grid, **opts)
    error = raised.value
    assert error.__cause__ is error.source_error and error.current.source is source
    assert error.membrane_area_m2 is b.kernel.membrane_area_m2
    assert error.stage == "field" and error.area_conversion_ok and error.field is None
    np.testing.assert_array_equal(error.outward_current_A, [1, 2, -1, -2, 0])
    save_arrays(
        "membrane-field-metadata-refusal",
        current=error.outward_current_A,
        current_identity=error.current.identity,
        error=str(error.source_error),
    )


@pytest.mark.parametrize("when", ["before_product", "after_product"])
def test_conversion_exception_retains_completed_readout_and_available_product(monkeypatch, when):
    b, grid = binding(), field.bind_metric(spec())
    source = inputs(b)
    cause = RuntimeError("declared conversion cause")
    primary = MemoryError("declared conversion observation failure")

    def fail(*args, **kwargs):
        raise primary from cause

    def forbidden(*args, **kwargs):
        pytest.fail("A failed conversion must stop before field work")

    if when == "before_product":
        monkeypatch.setattr(membrane, "np", SimpleNamespace(errstate=fail))
    else:
        monkeypatch.setattr(membrane.conduction, "_portable", fail)
    monkeypatch.setattr(membrane.coupling, "solve", forbidden)
    with pytest.raises(membrane.MembraneCouplingRejected) as raised:
        membrane.solve(b, source, mapped(b, grid), grid, **policy())
    error = raised.value
    assert error.source_error is primary and error.__cause__ is primary
    assert primary.__cause__ is cause and error.current.source is source
    assert error.membrane_area_m2 is b.kernel.membrane_area_m2
    assert error.stage == "conversion" and error.area_conversion_ok is error.field is None
    data = dict(
        density=error.current.values.membrane_current_A_m2,
        area=error.membrane_area_m2,
        membrane_flux=source.membrane_flux_mol_m2_s,
        junction_flux=source.junction_flux_mol_m2_s,
        extra_current=source.extra_current_A_m2,
        stage=error.stage,
        product_available=error.outward_current_A is not None,
        primary=str(primary),
        cause=str(cause),
        current_identity=error.current.identity,
    )
    if when == "before_product":
        assert error.outward_current_A is None
    else:
        np.testing.assert_array_equal(error.outward_current_A, [1, 2, -1, -2, 0])
        data["product"] = error.outward_current_A
    save_arrays("membrane-conversion-exception-" + when, **data)


def test_upstream_nonfinite_trial_is_preserved_without_field_work(monkeypatch):
    b, grid = binding(F=1e308), field.bind_metric(spec())
    source = current.inputs(
        b, np.full((3, 2), 4.0), np.zeros((3, 5)), np.zeros((3, 5)), np.zeros(2), np.zeros(5)
    )

    def forbidden(*args, **kwargs):
        pytest.fail("A failed current readout must not reach the field solver")

    monkeypatch.setattr(membrane.coupling, "solve", forbidden)
    with pytest.raises(current.NormalCurrentRejected) as raised:
        membrane.solve(b, source, mapped(b, grid), grid, **policy())
    error = raised.value
    assert error.source is source and error.trial.source is source
    assert not error.trial.diagnostics["finite"] and error.__cause__ is not None
    save_arrays(
        "membrane-upstream-refusal",
        charge=error.trial.values.charge_density_C_m3,
        source_identity=error.trial.source_identity,
        trial_identity=error.trial.identity,
        error=str(error.__cause__),
    )
