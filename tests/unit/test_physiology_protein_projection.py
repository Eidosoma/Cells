"""Named owner/unit conservation checks for explicit protein charge projection."""

from dataclasses import asdict, fields, replace

import numpy as np
import pytest

from cells.core import physiology_perturbation_step as component_step
from cells.core import physiology_protein_projection as projection
from cells.core import physiology_random_streams as streams
from cells.core import physiology_tissue_binding as units
from cells.numerics import surface_field
from cells.processes import betse_perturbations as perturb
from cells.processes.electrochemistry import F
from tests.unit.test_physiology_tissue_binding import bind, component_state
from tests.unit.test_physiology_tissue_step import KINDS, evidence
from validation.tissue import physiology_protein_projection_reference as reference


def protein(binding):
    def values(ids, offset):
        return np.asarray([(offset + sum(map(ord, name)) % 17) / 8 for name in ids])

    return perturb.ProteinState(
        values(binding.component.cell_ids, 8),
        np.full(len(binding.component.membrane_ids), 1e99),
        values(binding.component.environment_ids, 24),
    )


def transfer(before, binding, change=2**-16):
    cell, environment = before.cell_mol_m3.copy(), before.environment_mol_m3.copy()
    c = binding.component.cell_ids.index(binding.tissue_cell_ids[0])
    e = binding.component.environment_ids.index(binding.tissue_environment_ids[0])
    cell[c] += change
    environment[e] -= (
        change
        * binding.component.kernel.cell_volume_m3[c]
        / binding.component.kernel.environment_effective_volume_m3[e]
    )
    return perturb.ProteinState(cell, np.zeros_like(before.membrane_mol_m3), environment)


def expected_array(answer, result, name):
    domain = "cell" if name.startswith("cell_") else "environment"
    ids = result.cell_ids if domain == "cell" else result.environment_ids
    return np.asarray([answer[domain][owner][name.removeprefix(domain + "_")] for owner in ids])


def relative_error(actual, target):
    target = np.asarray(target)
    return float(
        np.max(
            np.divide(
                np.abs(actual - target),
                np.abs(target),
                out=np.abs(np.asarray(actual)).copy(),
                where=target != 0,
            ),
            initial=0,
        )
    )


@pytest.mark.parametrize("kind", KINDS)
@pytest.mark.parametrize("padded", [False, True])
@pytest.mark.parametrize("permuted", [False, True])
def test_all_physical_owner_stocks_and_conservative_deltas_match_named_Decimal(
    kind, padded, permuted
):
    spec, binding = bind(kind, padded=padded, reverse=permuted, reorder=permuted)
    before = protein(binding)
    after = transfer(before, binding)
    original = tuple((value.tobytes(), value.flags.writeable) for value in (*before, *after))
    absolute = projection.project(before, binding, valence=-1, faraday_C_mol=F)
    change = projection.delta(before, after, binding, valence=-1, faraday_C_mol=F)
    raw, record = spec.to_dict(), units.binding_record(binding)
    expected = reference.project(raw, record, before._asdict(), valence=-1, faraday_C_mol=F)
    expected_change = reference.delta(
        raw, record, before._asdict(), after._asdict(), valence=-1, faraday_C_mol=F
    )
    arrays, errors = {}, {}
    for field in fields(absolute):
        name = field.name
        if isinstance(value := getattr(absolute, name), np.ndarray):
            target = expected_array(expected, absolute, name)
            arrays["project__" + name], arrays["reference__" + name] = value, target
            errors[name] = relative_error(value, target)
    for field in fields(change):
        name = field.name
        if isinstance(value := getattr(change, name), np.ndarray):
            target = expected_array(expected_change, absolute, name)
            arrays["delta__" + name], arrays["delta_reference__" + name] = value, target
            errors[name] = relative_error(value, target)
    evidence(
        "protein-projection-" + kind + "-" + str(padded) + "-" + str(permuted),
        dict(
            definition=raw,
            binding=record,
            reference_protein=before._asdict(),
            current_protein=after._asdict(),
            valence=-1,
            faraday_C_mol=F,
            physical_cell_ids=absolute.cell_ids,
            physical_environment_ids=absolute.environment_ids,
            projection=asdict(absolute),
            delta=asdict(change),
            owner_relative_errors=errors,
            expected=expected,
            expected_delta=expected_change,
            tolerance=dict(relative=3e-15, absolute=0.0),
            scope=(
                "Actual unpadded owners; raw-source Decimal volumes and named axes; "
                "no field/RHS coupling"
            ),
        ),
        arrays,
    )
    assert max(errors.values()) <= 3e-15
    assert change.strict_conservation_valid and change.conservation_valid
    assert not change.storage_resolution_used
    assert absolute.cell_ids == binding.tissue_cell_ids
    assert absolute.environment_ids == binding.tissue_environment_ids
    assert absolute.cell_amount_mol.shape == (len(spec.model.cells),)
    assert absolute.environment_amount_mol.shape == (len(spec.model.extracellular),)
    np.testing.assert_allclose(
        absolute.total_amount_mol, expected["total_amount_mol"], rtol=3e-15, atol=0
    )
    np.testing.assert_allclose(
        absolute.total_charge_C, expected["total_charge_C"], rtol=3e-15, atol=0
    )
    assert (
        tuple((value.tobytes(), value.flags.writeable) for value in (*before, *after)) == original
    )


def test_native_and_Cells_Faraday_constants_are_declared_distinct_and_units_are_explicit():
    _, binding = bind()
    state = protein(binding)
    native = projection.project(state, binding, valence=-1, faraday_C_mol=96485)
    cells = projection.project(state, binding, valence=-1, faraday_C_mol=F)
    np.testing.assert_array_equal(native.cell_amount_mol, cells.cell_amount_mol)
    assert not np.array_equal(native.cell_charge_C, cells.cell_charge_C)
    np.testing.assert_allclose(cells.cell_amount_fmol, cells.cell_amount_mol * 1e15, rtol=0, atol=0)
    np.testing.assert_allclose(cells.cell_charge_C, -F * cells.cell_amount_mol, rtol=3e-16, atol=0)
    assert native.faraday_C_mol == 96485 and cells.faraday_C_mol == F


@pytest.mark.parametrize("valence", [-2.5, 0.0, 3.0])
def test_declared_valence_scales_charge_without_changing_owner_amounts(valence):
    _, binding = bind()
    state = protein(binding)
    actual = projection.project(state, binding, valence=valence, faraday_C_mol=F)
    neutral = projection.project(state, binding, valence=0, faraday_C_mol=F)
    np.testing.assert_array_equal(actual.cell_amount_mol, neutral.cell_amount_mol)
    np.testing.assert_allclose(
        actual.cell_charge_C, (actual.cell_amount_mol * valence) * F, rtol=0, atol=0
    )


def test_membrane_view_refresh_at_enabled_zero_noise_creates_no_stock_or_charge_change():
    _, binding = bind(reverse=True)
    component = component_state(binding)
    component = replace(
        component,
        controls=replace(
            component.controls,
            phase="SIM",
            dynamic_enabled=True,
            protein_enabled=True,
            dynamic_level_mol_m2_s=0.0,
        ),
    )
    result = component_step.advance(component, binding.component)
    assert result.packet is not None
    assert not np.array_equal(
        component.protein.membrane_mol_m3, result.state.protein.membrane_mol_m3
    )
    change = projection.delta(
        component.protein, result.state.protein, binding, valence=-1, faraday_C_mol=F
    )
    for field in fields(change):
        if isinstance(value := getattr(change, field.name), np.ndarray):
            assert np.count_nonzero(value) == 0
    assert change.strict_conservation_valid and change.conservation_valid
    assert change.balance_residual_mol == change.balance_residual_C == 0
    assert not change.storage_resolution_used


def test_one_ULP_concentration_delta_retains_information_lost_by_absolute_stock_subtraction():
    _, binding = bind()
    before = protein(binding)
    values = before.cell_mol_m3.copy()
    values[0] = np.nextafter(values[0], np.inf)
    after = before._replace(cell_mol_m3=values)
    result = projection.delta(before, after, binding, valence=-1, faraday_C_mol=F)
    index = int(binding.cell_to_tissue[0])
    expected = (values[0] - before.cell_mol_m3[0]) * binding.component.kernel.cell_volume_m3[0]
    assert result.cell_amount_delta_mol[index] == expected
    subtraction = result.current.cell_amount_mol[index] - result.baseline.cell_amount_mol[index]
    assert subtraction != expected
    assert result.conservation_valid and not result.strict_conservation_valid
    assert result.storage_resolution_used


@pytest.mark.parametrize("valence", [-1, 0])
def test_nonconservative_owner_creation_is_reported_without_charge_or_inventory_repair(valence):
    _, binding = bind()
    before = protein(binding)
    after = before._replace(cell_mol_m3=before.cell_mol_m3 + 0.125)
    result = projection.delta(before, after, binding, valence=valence, faraday_C_mol=F)
    assert not result.strict_conservation_valid and not result.conservation_valid
    assert not result.storage_resolution_used
    assert result.balance_residual_mol > 0
    np.testing.assert_array_equal(result.environment_amount_delta_mol, 0)
    assert np.all(result.cell_amount_delta_mol > 0)
    if valence == 0:
        assert result.balance_residual_C == 0


def test_actual_component_transfer_rounding_has_separate_visible_resolution_bound():
    _, binding = bind(reverse=True)
    component = component_state(binding)
    controls = replace(
        component.controls,
        phase="SIM",
        dynamic_enabled=True,
        protein_enabled=True,
        dynamic_level_mol_m2_s=1e-8,
        dt_s=1e-4,
    )
    component = replace(component, controls=controls)
    transition = component_step.advance(component, binding.component)
    result = projection.delta(
        component.protein, transition.state.protein, binding, valence=-1, faraday_C_mol=F
    )
    exact_transfer = perturb.protein_step(
        component.protein,
        transition.packet.values,
        controls.dynamic_level_mol_m2_s,
        controls.dt_s,
        binding.component,
        xp=np,
    )
    expected = np.r_[
        exact_transfer.cell_amount_change_mol[np.argsort(binding.cell_to_tissue)],
        exact_transfer.environment_amount_change_mol[np.argsort(binding.environment_to_tissue)],
    ]
    observed = np.r_[result.cell_amount_delta_mol, result.environment_amount_delta_mol]
    error = float(np.sum(np.abs(observed - expected)))
    assert result.conservation_valid
    assert error <= result.stock_resolution_bound_mol + result.projection_roundoff_bound_mol
    assert abs(result.balance_residual_mol) <= (
        result.conservation_tolerance_mol
        + result.stock_resolution_bound_mol
        + result.projection_roundoff_bound_mol
    )
    evidence(
        "protein-projection-stock-resolution",
        dict(
            reference_protein=component.protein._asdict(),
            current_protein=transition.state.protein._asdict(),
            prescribed_uniforms=transition.packet.values,
            delta=asdict(result),
            transfer_ledger_difference_mol=error,
            scope=(
                "Stored stock resolution is reported; original transfer tolerance "
                "and field tolerance are unchanged"
            ),
        ),
        dict(observed=observed, prescribed_transfer=expected, error=observed - expected),
    )


@pytest.mark.parametrize(
    "parameter,value",
    [
        ("valence", True),
        ("valence", np.nan),
        ("valence", np.inf),
        ("valence", [1]),
        ("faraday_C_mol", True),
        ("faraday_C_mol", 0),
        ("faraday_C_mol", -1),
        ("faraday_C_mol", np.inf),
        ("faraday_C_mol", np.nan),
    ],
)
def test_valence_and_charge_unit_constant_require_explicit_finite_scalars(parameter, value):
    _, binding = bind()
    kwargs = dict(valence=-1, faraday_C_mol=F) | {parameter: value}
    with pytest.raises(ValueError):
        projection.project(protein(binding), binding, **kwargs)


@pytest.mark.parametrize(
    "failure", ["negative", "nan", "infinity", "dtype", "shape", "membrane_shape"]
)
def test_bad_physical_buffers_are_not_coerced_or_clipped(failure):
    _, binding = bind()
    state = protein(binding)
    cell = state.cell_mol_m3.copy()
    if failure in ("negative", "nan", "infinity"):
        cell[0] = dict(negative=-1, nan=np.nan, infinity=np.inf)[failure]
    elif failure == "dtype":
        cell = cell.astype(np.float32)
    elif failure == "shape":
        cell = cell[:-1]
    else:
        state = state._replace(membrane_mol_m3=state.membrane_mol_m3[:-1])
    state = state._replace(cell_mol_m3=cell)
    before = tuple(value.tobytes() for value in state)
    with pytest.raises(ValueError):
        projection.project(state, binding, valence=-1, faraday_C_mol=F)
    assert tuple(value.tobytes() for value in state) == before


@pytest.mark.parametrize("failure", ["amount_underflow", "charge_underflow", "overflow"])
def test_unrepresentable_physical_conversion_retains_raw_unmodified_trial(failure):
    _, binding = bind()
    state = protein(binding)
    cell = state.cell_mol_m3.copy()
    valence = -1.0
    if failure == "amount_underflow":
        cell[0] = np.nextafter(0.0, 1.0)
    elif failure == "charge_underflow":
        valence = -np.nextafter(0.0, 1.0)
    else:
        cell[0] = 1e308
    state = state._replace(cell_mol_m3=cell)
    with pytest.raises(projection.ProteinProjectionError) as caught:
        projection.project(state, binding, valence=valence, faraday_C_mol=F)
    assert caught.value.raw
    evidence(
        "protein-projection-rejected-" + failure,
        dict(
            protein=state._asdict(),
            valence=valence,
            faraday_C_mol=F,
            reason=str(caught.value),
        ),
        dict(caught.value.raw),
    )
    for value in caught.value.raw.values():
        with pytest.raises(ValueError):
            value.setflags(write=True)


def test_projection_is_pure_immutable_and_calls_no_rng_component_or_field_solver(monkeypatch):
    _, binding = bind()
    state = protein(binding)
    after = transfer(state, binding)
    before = tuple((value.tobytes(), value.flags.writeable) for value in (*state, *after))

    def forbidden(*args, **kwargs):
        pytest.fail("Pure protein projection invoked an evolution/RNG/field operation")

    with monkeypatch.context() as guard:
        guard.setattr(streams, "draw", forbidden)
        guard.setattr(component_step, "advance", forbidden)
        guard.setattr(surface_field, "solve", forbidden)
        result = projection.delta(state, after, binding, valence=-1, faraday_C_mol=F)
    for value in (result.baseline, result.current, result):
        for field in fields(value):
            if isinstance(array := getattr(value, field.name), np.ndarray):
                with pytest.raises(ValueError):
                    array.setflags(write=True)
    assert tuple((value.tobytes(), value.flags.writeable) for value in (*state, *after)) == before
