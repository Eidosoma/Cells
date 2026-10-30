"""Independent ideal chemistry, zero/tiny stocks and conditional endpoint work."""

import math
from dataclasses import asdict, fields, replace
from decimal import Decimal, localcontext

import numpy as np
import pytest

from cells.core import physiology_perturbation_step as component_step
from cells.core import physiology_protein_projection as projection
from cells.core import physiology_protein_thermodynamics as thermo
from cells.core import physiology_random_streams as streams
from cells.core import physiology_tissue_binding as units
from cells.numerics import surface_field
from cells.processes import betse_perturbations as perturb
from cells.processes.electrochemistry import R
from tests.unit.test_physiology_protein_projection import protein, transfer
from tests.unit.test_physiology_tissue_binding import bind, component_state
from tests.unit.test_physiology_tissue_step import KINDS, evidence
from validation.tissue import physiology_protein_thermodynamics_reference as reference


def frame(spec, standard=1.0):
    return dict(
        temperature_K=spec.model.temperature_K,
        standard_concentration_mol_m3=standard,
        gas_constant_J_mol_K=R,
    )


def expected_value(answer, result, name):
    if name == "total_free_energy_pJ" or name == "total_free_energy_change_pJ":
        return np.asarray(answer[name])
    domain = "cell" if name.startswith("cell_") else "environment"
    ids = result.cell_ids if domain == "cell" else result.environment_ids
    return np.asarray([answer[domain][owner][name.removeprefix(domain + "_")] for owner in ids])


def precision(actual, expected):
    actual, expected = np.asarray(actual), np.asarray(expected)
    finite = np.isfinite(expected)
    np.testing.assert_array_equal(np.isneginf(actual), np.isneginf(expected))
    assert np.isfinite(actual[finite]).all()
    assert np.all(actual[expected == 0] == 0)
    budget = np.zeros_like(expected)
    budget[finite] = 3e-15 * np.abs(expected[finite]) + 2 * np.abs(np.spacing(expected[finite]))
    difference = np.zeros_like(expected)
    difference[finite] = np.abs(actual[finite] - expected[finite])
    ratio = np.divide(difference, budget, out=np.zeros_like(expected), where=finite)
    return budget, ratio


def compare_case(name, spec, binding, before, after, *, standard=1.0):
    parameters = frame(spec, standard)
    raw, record = spec.to_dict(), units.binding_record(binding)
    original = tuple((value.tobytes(), value.flags.writeable) for value in (*before, *after))
    start = thermo.evaluate(before, binding, **parameters)
    end = thermo.evaluate(after, binding, **parameters)
    change = thermo.change(before, after, binding, **parameters)
    expected_start = reference.evaluate(raw, record, before._asdict(), **parameters)
    expected_end = reference.evaluate(raw, record, after._asdict(), **parameters)
    expected_change = reference.change(raw, record, before._asdict(), after._asdict(), **parameters)
    arrays, errors = {}, {}
    energy_names = (
        "cell_free_energy_pJ",
        "environment_free_energy_pJ",
        "total_free_energy_pJ",
        "cell_chemical_potential_J_mol",
        "environment_chemical_potential_J_mol",
    )
    for label, actual, target, names in (
        ("before", start, expected_start, energy_names),
        ("after", end, expected_end, energy_names),
        (
            "change",
            change,
            expected_change,
            (
                "cell_free_energy_change_pJ",
                "environment_free_energy_change_pJ",
                "total_free_energy_change_pJ",
            ),
        ),
    ):
        for key in names:
            actual_value = np.asarray(getattr(actual, key))
            expected = expected_value(target, start, key)
            budget, error = precision(actual_value, expected)
            tag = label + "__" + key
            arrays[tag], arrays["expected__" + tag] = actual_value, expected
            arrays["budget__" + tag], arrays["error__" + tag] = budget, error
            errors[tag] = float(np.max(error, initial=0))
    work_record = None
    if change.strict_conservation_valid:
        work = thermo.endpoint_work(change, capacitor_energy_change_pJ=0.25, clamp_work_pJ=-0.125)
        expected_work = reference.endpoint_work(
            expected_change["total_free_energy_change_pJ"],
            capacitor_energy_change_pJ=0.25,
            clamp_work_pJ=-0.125,
        )
        budget, error = precision(work.conditional_reversible_driving_work_pJ, expected_work)
        arrays["conditional_work"] = work.conditional_reversible_driving_work_pJ
        arrays["expected__conditional_work"] = expected_work
        arrays["budget__conditional_work"] = budget
        errors["conditional_work"] = float(error)
        work_record = dict(
            capacitor_energy_change_pJ=0.25,
            clamp_work_pJ=-0.125,
            conditional_reversible_driving_work_pJ=work.conditional_reversible_driving_work_pJ,
            admission=dict(work.admission),
        )
    evidence(
        "protein-thermo-" + name,
        dict(
            definition=raw,
            binding=record,
            reference_protein=before._asdict(),
            current_protein=after._asdict(),
            parameters=parameters,
            physical_cell_ids=start.cell_ids,
            physical_environment_ids=start.environment_ids,
            before=asdict(start),
            after=asdict(end),
            change=asdict(change),
            errors=errors,
            conditional_work=work_record,
            tolerance=dict(relative=3e-15, absolute_ulps=2),
            scope=(
                "Optional Cells fixed-volume ideal-protein diagnostic only; "
                "no native energy law, path, heat, noise or holding-work claim"
            ),
        ),
        arrays,
    )
    assert max(errors.values()) <= 1
    assert (
        tuple((value.tobytes(), value.flags.writeable) for value in (*before, *after)) == original
    )
    return change


@pytest.mark.parametrize("kind", KINDS)
@pytest.mark.parametrize("padded", [False, True])
@pytest.mark.parametrize("permuted", [False, True])
def test_named_owner_free_energies_mu_and_stable_changes_match_independent_reference(
    kind, padded, permuted
):
    spec, binding = bind(kind, padded=padded, reverse=permuted, reorder=permuted)
    before = protein(binding)
    change = compare_case(
        kind + "-" + str(padded) + "-" + str(permuted),
        spec,
        binding,
        before,
        transfer(before, binding),
        standard=1000.0 if padded else 1.0,
    )
    assert change.strict_conservation_valid


@pytest.mark.parametrize(
    "case", ["zero", "tiny_create", "tiny_remove", "tiny_grow", "tiny_ulp", "mixed_zero"]
)
def test_zero_and_tiny_stocks_retain_energy_without_mol_underflow_or_floors(case):
    spec, binding = bind()
    base = protein(binding)
    zero = perturb.ProteinState(*(np.zeros_like(value) for value in base))
    before, after = zero, zero
    tiny = np.nextafter(0.0, 1.0)
    if case == "tiny_create":
        cells = zero.cell_mol_m3.copy()
        cells[0] = tiny
        after = zero._replace(cell_mol_m3=cells)
    elif case == "tiny_remove":
        cells = zero.cell_mol_m3.copy()
        cells[0] = tiny
        before = zero._replace(cell_mol_m3=cells)
    elif case in ("tiny_grow", "tiny_ulp"):
        cells = zero.cell_mol_m3.copy()
        cells[0] = 1e-300
        before = zero._replace(cell_mol_m3=cells)
        cells = cells.copy()
        cells[0] = 2e-300 if case == "tiny_grow" else np.nextafter(1e-300, np.inf)
        after = zero._replace(cell_mol_m3=cells)
    elif case == "mixed_zero":
        cells = zero.cell_mol_m3.copy()
        cells[0] = tiny
        exterior = zero.environment_mol_m3.copy()
        exterior[-1] = 1e-200
        before = zero._replace(environment_mol_m3=exterior)
        after = before._replace(cell_mol_m3=cells)
    change = compare_case("boundary-" + case, spec, binding, before, after)
    if case == "zero":
        assert change.total_free_energy_change_pJ == 0
        assert np.isneginf(change.baseline.cell_chemical_potential_J_mol).all()
        assert np.count_nonzero(change.baseline.cell_free_energy_pJ) == 0
        assert change.strict_conservation_valid
    else:
        assert change.total_free_energy_change_pJ != 0
    if case == "tiny_create":
        assert tiny * binding.component.kernel.cell_volume_m3[0] == 0
        assert np.any(change.current.cell_free_energy_pJ != 0)
        assert not change.material_diagnostics_representable


def test_equilibrium_one_ULP_transfer_has_positive_second_order_energy():
    spec, binding = bind()
    original = protein(binding)
    before = perturb.ProteinState(
        np.ones_like(original.cell_mol_m3),
        original.membrane_mol_m3,
        np.ones_like(original.environment_mol_m3),
    )
    after = transfer(before, binding, change=np.spacing(1.0))
    change = compare_case("equilibrium-ulp", spec, binding, before, after)
    assert change.strict_conservation_valid and change.total_free_energy_change_pJ > 0
    assert change.current.total_free_energy_pJ == change.baseline.total_free_energy_pJ


def test_closed_material_change_is_independent_of_standard_concentration():
    spec, binding = bind()
    before = protein(binding)
    after = transfer(before, binding)
    a = thermo.change(before, after, binding, **frame(spec, 1.0))
    b = thermo.change(before, after, binding, **frame(spec, 1000.0))
    assert Decimal(a.amount_balance_residual_mol_exact) == 0
    assert a.total_free_energy_change_pJ == b.total_free_energy_change_pJ
    assert a.baseline.total_free_energy_pJ != b.baseline.total_free_energy_pJ


def test_open_material_change_keeps_its_explicit_standard_frame_and_fails_closed_work_gate():
    spec, binding = bind()
    before = protein(binding)
    after = before._replace(cell_mol_m3=before.cell_mol_m3 + 0.125)
    a = thermo.change(before, after, binding, **frame(spec, 1.0))
    b = thermo.change(before, after, binding, **frame(spec, 1000.0))
    assert not a.strict_conservation_valid
    predicted = (
        -R * spec.model.temperature_K * math.log(1000) * a.amount_balance_residual_mol * 1e12
    )
    np.testing.assert_allclose(
        b.total_free_energy_change_pJ - a.total_free_energy_change_pJ, predicted, rtol=3e-15, atol=0
    )
    with pytest.raises(thermo.ProteinThermodynamicsError, match="strict material") as caught:
        thermo.endpoint_work(a, capacitor_energy_change_pJ=0, clamp_work_pJ=0)
    assert caught.value.raw


def test_free_energy_derivative_converges_to_declared_chemical_potential():
    spec, binding = bind()
    center = protein(binding)
    cells = center.cell_mol_m3.copy()
    cells[0] = 2.0
    center = center._replace(cell_mol_m3=cells)
    state = thermo.evaluate(center, binding, **frame(spec))
    physical = int(binding.cell_to_tissue[0])
    target = state.cell_chemical_potential_J_mol[physical]
    errors = []
    for h in (2**-10, 2**-11):
        left, right = cells.copy(), cells.copy()
        left[0] -= h
        right[0] += h
        change = thermo.change(
            center._replace(cell_mol_m3=left),
            center._replace(cell_mol_m3=right),
            binding,
            **frame(spec),
        )
        observed = (
            change.total_free_energy_change_pJ
            * 1e-12
            / (2 * h * binding.component.kernel.cell_volume_m3[0])
        )
        errors.append(abs(observed - target) / abs(target))
    assert errors[1] < errors[0] / 3 and errors[1] < 2e-8


def test_tiny_closed_energy_survives_large_capacitor_clamp_cancellation():
    spec, binding = bind()
    original = protein(binding)
    cell, env = np.zeros_like(original.cell_mol_m3), np.zeros_like(original.environment_mol_m3)
    cell[0], env[0] = 2e-300, 1e-300
    before = perturb.ProteinState(cell, original.membrane_mol_m3, env)
    premature = transfer(before, binding, change=-1e-300)
    refused = thermo.change(before, premature, binding, **frame(spec))
    evidence(
        "protein-thermo-tiny-premature-mol-rounding",
        dict(
            source_definition=spec.to_dict(),
            binding=units.binding_record(binding),
            before_protein=before._asdict(),
            after_protein=premature._asdict(),
            change=asdict(refused),
            classification=(
                "Original fixture is nonconservative after premature subnormal mol rounding"
            ),
        ),
    )
    assert not refused.strict_conservation_valid
    with pytest.raises(thermo.ProteinThermodynamicsError, match="strict material"):
        thermo.endpoint_work(refused, capacitor_energy_change_pJ=1e308, clamp_work_pJ=1e308)
    updated_cell, updated_env = cell.copy(), env.copy()
    updated_cell[0] -= 1e-300
    ratio = (
        binding.component.kernel.cell_volume_m3[0]
        / binding.component.kernel.environment_effective_volume_m3[0]
    )
    assert ratio == 0.5
    updated_env[0] += 1e-300 * ratio
    after = perturb.ProteinState(updated_cell, original.membrane_mol_m3, updated_env)
    change = thermo.change(before, after, binding, **frame(spec))
    evidence(
        "protein-thermo-tiny-concentration-update",
        dict(
            source_definition=spec.to_dict(),
            binding=units.binding_record(binding),
            before_protein=before._asdict(),
            after_protein=after._asdict(),
            change=asdict(change),
            classification=(
                "Same tiny transfer formed in concentration coordinates; unchanged strict gate"
            ),
        ),
    )
    assert change.strict_conservation_valid and change.total_free_energy_change_pJ != 0
    result = thermo.endpoint_work(change, capacitor_energy_change_pJ=1e308, clamp_work_pJ=1e308)
    evidence(
        "protein-thermo-tiny-conditional-work",
        dict(
            chemical_change_pJ=change.total_free_energy_change_pJ,
            capacitor_energy_change_pJ=1e308,
            clamp_work_pJ=1e308,
            conditional_work_pJ=result.conditional_reversible_driving_work_pJ,
            admission=dict(result.admission),
        ),
    )
    assert result.conditional_reversible_driving_work_pJ == change.total_free_energy_change_pJ
    assert result.reversible_driving_work_pJ == result.conditional_reversible_driving_work_pJ


@pytest.mark.parametrize("du,clamp,expected", [(2, 1, 1), (2, -1, 3), (-2, 1, -3), (0, 0, 0)])
def test_conditional_work_signs_do_not_infer_heat_noise_or_attainable_minimum(du, clamp, expected):
    spec, binding = bind()
    state = protein(binding)
    change = thermo.change(state, state, binding, **frame(spec))
    result = thermo.endpoint_work(change, capacitor_energy_change_pJ=du, clamp_work_pJ=clamp)
    assert result.conditional_reversible_driving_work_pJ == expected
    assert (
        not result.admission["heat_inferred"] and not result.admission["stochastic_work_inferred"]
    )
    assert (
        not result.admission["holding_work_included"]
        and not result.admission["attainable_minimum_claim"]
    )


def test_reversal_and_additivity_are_endpoint_identities_at_fixed_frame():
    spec, binding = bind()
    a = protein(binding)
    b = transfer(a, binding)
    c = transfer(b, binding)
    ab, bc, ac, ca = [
        thermo.change(x, y, binding, **frame(spec)) for x, y in ((a, b), (b, c), (a, c), (c, a))
    ]
    np.testing.assert_allclose(
        ab.total_free_energy_change_pJ + bc.total_free_energy_change_pJ,
        ac.total_free_energy_change_pJ,
        rtol=3e-15,
        atol=0,
    )
    assert ca.total_free_energy_change_pJ == -ac.total_free_energy_change_pJ
    forward = thermo.endpoint_work(ac, capacitor_energy_change_pJ=0.125, clamp_work_pJ=-0.5)
    reverse = thermo.endpoint_work(ca, capacitor_energy_change_pJ=-0.125, clamp_work_pJ=0.5)
    assert (
        forward.conditional_reversible_driving_work_pJ
        == -reverse.conditional_reversible_driving_work_pJ
    )


@pytest.mark.parametrize(
    "parameter,value",
    [
        ("temperature_K", 0),
        ("temperature_K", -1),
        ("temperature_K", True),
        ("temperature_K", np.inf),
        ("standard_concentration_mol_m3", 0),
        ("standard_concentration_mol_m3", -1),
        ("standard_concentration_mol_m3", np.nan),
        ("standard_concentration_mol_m3", [1]),
        ("gas_constant_J_mol_K", 0),
        ("gas_constant_J_mol_K", -1),
        ("gas_constant_J_mol_K", False),
        ("gas_constant_J_mol_K", np.nan),
    ],
)
def test_declared_thermodynamic_frame_requires_positive_finite_scalars(parameter, value):
    spec, binding = bind()
    with pytest.raises(ValueError):
        thermo.evaluate(protein(binding), binding, **(frame(spec) | {parameter: value}))


@pytest.mark.parametrize("case", ["underflow", "overflow"])
def test_unrepresentable_nonzero_energy_is_retained_instead_of_silently_zeroed(case):
    spec, binding = bind()
    original = protein(binding)
    cells = np.zeros_like(original.cell_mol_m3)
    cells[0] = np.nextafter(0.0, 1.0) if case == "underflow" else 1e308
    state = perturb.ProteinState(
        cells, original.membrane_mol_m3, np.zeros_like(original.environment_mol_m3)
    )
    parameters = frame(spec) | dict(
        temperature_K=np.nextafter(0.0, 1.0) if case == "underflow" else 1e308
    )
    with pytest.raises(thermo.ProteinThermodynamicsError, match="Unrepresentable") as caught:
        thermo.evaluate(state, binding, **parameters)
    assert caught.value.raw
    evidence(
        "protein-thermo-rejected-" + case,
        dict(
            protein=state._asdict(),
            parameters=parameters,
            reason=str(caught.value),
            raw=dict(caught.value.raw),
        ),
    )


def test_pure_immutable_diagnostic_ignores_ambient_decimal_and_calls_no_evolution(monkeypatch):
    spec, binding = bind()
    before = protein(binding)
    after = transfer(before, binding)
    normal = thermo.change(before, after, binding, **frame(spec, 1.75))

    def forbidden(*args, **kwargs):
        pytest.fail(
            "Chemical endpoint diagnostic invoked evolution, charge projection, or field solve"
        )

    with monkeypatch.context() as guard:
        for module, name in (
            (streams, "draw"),
            (component_step, "advance"),
            (surface_field, "solve"),
            (projection, "project"),
            (projection, "delta"),
        ):
            guard.setattr(module, name, forbidden)
        with localcontext() as context:
            context.prec, context.Emin, context.Emax = 7, -3, 3
            thermo._ln.cache_clear()
            result = thermo.change(before, after, binding, **frame(spec, 1.75))
            assert (context.prec, context.Emin, context.Emax) == (7, -3, 3)
    assert result.total_free_energy_change_pJ == normal.total_free_energy_change_pJ
    for obj in (result, result.baseline, result.current):
        for field in fields(obj):
            if isinstance(value := getattr(obj, field.name), np.ndarray):
                with pytest.raises(ValueError):
                    value.setflags(write=True)


def test_ideal_energy_and_mu_scale_with_declared_T_and_R():
    spec, binding = bind()
    state = protein(binding)
    original = thermo.evaluate(state, binding, **frame(spec))
    for update in (
        dict(temperature_K=2 * spec.model.temperature_K),
        dict(gas_constant_J_mol_K=2 * R),
    ):
        changed = thermo.evaluate(state, binding, **(frame(spec) | update))
        np.testing.assert_array_equal(changed.cell_free_energy_pJ, 2 * original.cell_free_energy_pJ)
        np.testing.assert_array_equal(
            changed.cell_chemical_potential_J_mol, 2 * original.cell_chemical_potential_J_mol
        )


def test_zero_level_membrane_view_refresh_adds_no_chemical_energy():
    spec, binding = bind()
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
    change = thermo.change(component.protein, result.state.protein, binding, **frame(spec))
    assert change.total_free_energy_change_pJ == 0 and change.strict_conservation_valid


@pytest.mark.parametrize(
    "parameter,value",
    [
        ("capacitor_energy_change_pJ", np.nan),
        ("capacitor_energy_change_pJ", True),
        ("clamp_work_pJ", np.inf),
        ("clamp_work_pJ", [0]),
    ],
)
def test_explicit_endpoint_work_terms_must_be_finite_scalars(parameter, value):
    spec, binding = bind()
    state = protein(binding)
    change = thermo.change(state, state, binding, **frame(spec))
    with pytest.raises(ValueError):
        thermo.endpoint_work(
            change, **(dict(capacitor_energy_change_pJ=0, clamp_work_pJ=0) | {parameter: value})
        )


def test_extreme_standard_activity_uses_logs_and_positive_tiny_stock_has_zero_mu_at_c0():
    spec, binding = bind()
    state = protein(binding)
    tiny = np.nextafter(0.0, 1.0)
    compare_case(
        "standard-min-dense", spec, binding, state, transfer(state, binding), standard=tiny
    )
    low = perturb.ProteinState(
        np.full_like(state.cell_mol_m3, tiny),
        state.membrane_mol_m3,
        np.full_like(state.environment_mol_m3, tiny),
    )
    change = compare_case("standard-min-tiny", spec, binding, low, low, standard=tiny)
    assert np.count_nonzero(change.baseline.cell_chemical_potential_J_mol) == 0
    assert not change.baseline.cell_zero_stock.any()
    assert np.count_nonzero(change.baseline.cell_free_energy_pJ) > 0
