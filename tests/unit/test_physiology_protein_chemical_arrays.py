"""Independent SI energies, strict material and CPU array/JIT/vmap diagnostics."""

import ast
import inspect
from decimal import Decimal, localcontext

import jax
import jax.numpy as jnp
import numpy as np
import pytest

from cells.core import physiology_protein_chemical_arrays as arrays
from cells.core import physiology_protein_thermodynamics as host
from cells.processes.betse_perturbations import ProteinState
from cells.processes.electrochemistry import R
from tests.unit.test_physiology_protein_interval_accounting import evidence
from tests.unit.test_physiology_protein_projection import protein, transfer
from tests.unit.test_physiology_tissue_binding import bind
from tests.unit.test_physiology_tissue_step import KINDS
from validation.tissue import physiology_protein_chemical_arrays_reference as reference


def state(cell, environment, *, membrane=1e99):
    return ProteinState(
        np.asarray(cell, dtype=float), np.array([membrane]), np.asarray(environment, dtype=float)
    )


def frame(t=310.0, standard=1.0, gas=R):
    return dict(temperature_K=t, standard_concentration_mol_m3=standard, gas_constant_J_mol_K=gas)


def declaration(before, after, vc, ve, parameters):
    return dict(
        reference_protein=before._asdict(),
        current_protein=after._asdict(),
        cell_volume_m3=vc,
        environment_volume_m3=ve,
        **parameters,
    )


def compare(name, before, after, vc, ve, *, parameters=None, expected_strict=None):
    parameters = frame() if parameters is None else parameters
    original = tuple(
        (a.dtype.str, a.shape, a.tobytes(), a.flags.writeable) for a in (*before, *after, vc, ve)
    )
    result = arrays.change(before, after, vc, ve, **parameters, xp=np)
    inputs = declaration(before, after, vc, ve, parameters)
    target = reference.change(**inputs)
    errors, comparisons = {}, {}
    for key in (
        "cell_free_energy_change_pJ",
        "environment_free_energy_change_pJ",
        "total_free_energy_change_pJ",
        "cell_before_chemical_potential_J_mol",
        "cell_after_chemical_potential_J_mol",
        "environment_before_chemical_potential_J_mol",
        "environment_after_chemical_potential_J_mol",
    ):
        actual, expected = np.asarray(getattr(result, key)), np.asarray(target[key])
        np.testing.assert_array_equal(np.isneginf(actual), np.isneginf(expected))
        assert np.isfinite(actual[np.isfinite(expected)]).all()
        budget, ratio = reference.precision(actual, expected)
        errors[key] = float(np.max(ratio, initial=0))
        comparisons[key] = dict(
            actual=actual, expected=expected, budget=budget, error_fraction=ratio
        )
    assert not result.strict_conservation_valid or target["strict_conservation_valid"]
    if expected_strict is not None:
        assert bool(result.strict_conservation_valid) == expected_strict
    with localcontext() as context:
        context.prec = 160
        scale = Decimal(2) ** int(result.material.binary_exponent)
        normalized_net = Decimal.from_float(
            float(result.material.net_normalized)
        ) + Decimal.from_float(float(result.material.net_remainder_normalized))
        delta = abs(normalized_net * scale - Decimal(target["net_mol_exact"]))
        bound = Decimal.from_float(float(result.material.roundoff_bound_normalized)) * scale
        assert delta <= bound or delta == 0
    evidence(
        "protein-chemical-arrays-" + name,
        dict(
            inputs=inputs,
            actual=result._asdict() | dict(material=result.material._asdict()),
            expected=target,
            comparisons=comparisons,
            maximum_error_fraction=max(errors.values()),
            normalized_net_error_mol_exact=str(delta),
            normalized_net_error_bound_mol_exact=str(bound),
            heat_inferred=False,
            driving_law_inferred=False,
        ),
    )
    assert result.valid
    assert result.closed_valid == (result.valid & result.strict_conservation_valid)
    assert max(errors.values()) <= 1
    assert original == tuple(
        (a.dtype.str, a.shape, a.tobytes(), a.flags.writeable) for a in (*before, *after, vc, ve)
    )
    return result


@pytest.mark.parametrize("kind", KINDS)
@pytest.mark.parametrize("permuted", (False, True))
def test_physical_owner_frames_match_frozen_host_and_independent_SI_functionals(kind, permuted):
    spec, binding = bind(kind, reverse=permuted, reorder=permuted)
    before = protein(binding)
    after = transfer(before, binding)
    parameters = frame(spec.model.temperature_K)
    vc, ve = (
        binding.component.kernel.cell_volume_m3,
        binding.component.kernel.environment_effective_volume_m3,
    )
    actual = compare(
        kind + "-" + str(permuted),
        before,
        after,
        vc,
        ve,
        parameters=parameters,
        expected_strict=True,
    )
    expected = host.change(before, after, binding, **parameters)
    for domain, ids, physical in (
        ("cell", binding.component.cell_ids, binding.tissue_cell_ids),
        ("environment", binding.component.environment_ids, binding.tissue_environment_ids),
    ):
        target = getattr(expected, domain + "_free_energy_change_pJ")
        target = np.asarray([target[physical.index(owner)] for owner in ids])
        _, ratio = reference.precision(getattr(actual, domain + "_free_energy_change_pJ"), target)
        assert np.max(ratio, initial=0) <= 1
    _, ratio = reference.precision(
        actual.total_free_energy_change_pJ, expected.total_free_energy_change_pJ
    )
    assert ratio <= 1
    assert actual.strict_conservation_valid == expected.strict_conservation_valid


EDGE_CASES = (
    ("birth", [0.0], [1.0], [2.0], [1.5], [2e-15], [4e-15], True),
    ("death", [1.0], [0.0], [1.0], [1.5], [2e-15], [4e-15], True),
    ("all-zero", [0.0], [0.0], [0.0], [0.0], [2e-15], [4e-15], True),
    ("empty-cell", [], [], [1.0], [1.0], [], [4e-15], True),
    ("empty-environment", [1.0], [1.0], [], [], [2e-15], [], True),
    ("empty-both", [], [], [], [], [], [], True),
    ("tiny", [2e-300], [1e-300], [1e-300], [1.5e-300], [2e-15], [4e-15], True),
    ("near-standard", [1.0], [np.nextafter(1.0, np.inf)], [], [], [2e-15], [], False),
    ("open", [1.0], [2.0], [3.0], [3.0], [2e-15], [4e-15], False),
    (
        "no-stock-grace",
        [1e100],
        [np.nextafter(1e100, np.inf)],
        [1e100],
        [1e100],
        [1.0],
        [1.0],
        False,
    ),
)


@pytest.mark.parametrize("name,bc,ac,be,ae,vc,ve,strict", EDGE_CASES)
def test_zero_empty_tiny_and_open_owners_have_explicit_domains_and_strict_material(
    name, bc, ac, be, ae, vc, ve, strict
):
    result = compare(
        name,
        state(bc, be),
        state(ac, ae),
        np.asarray(vc, dtype=float),
        np.asarray(ve, dtype=float),
        expected_strict=strict,
    )
    if name == "tiny":
        assert result.total_free_energy_change_pJ != 0
        assert not result.material.display_representable
        assert result.material.gross_normalized > 0
    if name == "no-stock-grace":
        assert abs(result.material.net_mol) > result.material.tolerance_mol


@pytest.mark.parametrize("standard,gas", ((0.001, R), (7.0, R), (1.0, 0.5)))
def test_explicit_standard_and_gas_constant_preserve_real_open_material_term(standard, gas):
    before, after = state([1.0], [3.0]), state([2.0], [3.0])
    compare(
        "frame-" + str(standard) + "-" + str(gas),
        before,
        after,
        np.array([2e-15]),
        np.array([4e-15]),
        parameters=frame(standard=standard, gas=gas),
        expected_strict=False,
    )


@pytest.mark.parametrize(
    "field,value",
    (
        ("temperature_K", 0.0),
        ("standard_concentration_mol_m3", 0.0),
        ("gas_constant_J_mol_K", -1.0),
        ("gas_constant_J_mol_K", np.inf),
        ("gas_constant_J_mol_K", 1e-320),
    ),
)
def test_invalid_or_subnormal_frame_is_explicit_refusal(field, value):
    parameters = frame() | {field: value}
    result = arrays.change(
        state([1.0], [2.0]),
        state([2.0], [2.0]),
        np.array([2e-15]),
        np.array([4e-15]),
        **parameters,
        xp=np,
    )
    assert not result.valid and not result.closed_valid and not result.diagnostics["frame_valid"]


@pytest.mark.parametrize(
    "kind", ("negative", "nan", "zero-volume", "subnormal-stock", "bad-membrane")
)
def test_complete_owner_or_view_domain_refusal_never_repairs_buffers(kind):
    before, after, vc = state([1.0], [2.0]), state([2.0], [2.0]), np.array([2e-15])
    if kind == "negative":
        after = state([-1.0], [2.0])
    elif kind == "nan":
        after = state([np.nan], [2.0])
    elif kind == "zero-volume":
        vc = np.array([0.0])
    elif kind == "subnormal-stock":
        after = state([1e-320], [2.0])
    else:
        after = state([2.0], [2.0], membrane=-1.0)
    original = tuple(a.tobytes() for a in (*before, *after, vc))
    result = arrays.change(before, after, vc, np.array([4e-15]), **frame(), xp=np)
    assert not result.valid and not result.closed_valid
    assert original == tuple(a.tobytes() for a in (*before, *after, vc))


@pytest.mark.parametrize("kind", ("underflow", "overflow", "ambiguous-swap"))
def test_unrepresentable_or_unresolved_chemical_change_is_diagnostic_refusal(kind):
    if kind == "underflow":
        before, after, vc, ve = (
            state([1e-100], []),
            state([2e-100], []),
            np.array([1e-300]),
            np.zeros(0),
        )
    elif kind == "overflow":
        before, after, vc, ve = state([1.0], []), state([2.0], []), np.array([1e308]), np.zeros(0)
    else:
        before, after, vc, ve = (
            state([2.0], [3.0]),
            state([3.0], [2.0]),
            np.array([1.0]),
            np.array([1.0]),
        )
    answer = arrays.change(before, after, vc, ve, **frame(), xp=np)
    target = reference.change(**declaration(before, after, vc, ve, frame()))
    assert not answer.valid and not answer.closed_valid
    if kind == "ambiguous-swap":
        assert target["total_free_energy_change_pJ"] == 0 and target["strict_conservation_valid"]
    else:
        assert not target["energy_display_representable"]
    evidence(
        "protein-chemical-arrays-refused-" + kind,
        dict(
            refusal=kind,
            actual=answer._asdict(),
            expected=target,
            inputs=declaration(before, after, vc, ve, frame()),
        ),
    )


def test_membrane_views_are_not_inventory_and_hot_path_has_no_host_conversion():
    before, after = state([1.0], [3.0]), state([2.0], [3.0])
    args = (np.array([2e-15]), np.array([4e-15]))
    a = arrays.change(before, after, *args, **frame(), xp=np)
    b = arrays.change(
        before._replace(membrane_mol_m3=np.array([1e300])),
        after._replace(membrane_mol_m3=np.array([1e200])),
        *args,
        **frame(),
        xp=np,
    )
    assert a.total_free_energy_change_pJ == b.total_free_energy_change_pJ
    assert a.material.net_mol == b.material.net_mol
    for node in ast.walk(ast.parse(inspect.getsource(arrays))):
        if isinstance(node, ast.ImportFrom):
            assert node.module != "decimal"
        if isinstance(node, ast.Attribute):
            assert node.attr not in ("item", "tolist", "device_get", "pure_callback", "io_callback")
            assert not (
                isinstance(node.value, ast.Name)
                and node.value.id == "np"
                and node.attr == "asarray"
            )
    with pytest.raises(ValueError, match="owner axes"):
        arrays.change(before, after, np.array([1.0, 2.0]), args[1], **frame(), xp=np)


def test_cpu_jax_compiled_vmap_preserves_zero_and_tiny_closed_changes():
    rows = [EDGE_CASES[0], EDGE_CASES[6]]
    inputs, expected = [], []
    for _, bc, ac, be, ae, vc, ve, _ in rows:
        b, e, vc, ve = state(bc, be), state(ac, ae), np.array(vc), np.array(ve)
        inputs.append((b, e, vc, ve, np.array(310.0), np.array(1.0), np.array(R)))
        expected.append(arrays.change(b, e, vc, ve, **frame(), xp=np))
    batched = jax.tree.map(lambda *values: jnp.stack(values), *inputs)
    function = jax.jit(
        jax.vmap(
            lambda b, e, vc, ve, t, c0, r: arrays.change(
                b,
                e,
                vc,
                ve,
                temperature_K=t,
                standard_concentration_mol_m3=c0,
                gas_constant_J_mol_K=r,
                xp=jnp,
            )
        )
    )
    actual = function(*batched)
    actual.valid.block_until_ready()
    assert jax.default_backend() == "cpu" and jax.config.x64_enabled
    np.testing.assert_array_equal(actual.valid, [True, True])
    np.testing.assert_array_equal(actual.closed_valid, [True, True])
    errors = []
    for i, target in enumerate(expected):
        for key in (
            "cell_free_energy_change_pJ",
            "environment_free_energy_change_pJ",
            "total_free_energy_change_pJ",
        ):
            _, ratio = reference.precision(
                np.asarray(getattr(actual, key)[i]), getattr(target, key)
            )
            errors.append(float(np.max(ratio, initial=0)))
    evidence(
        "protein-chemical-arrays-cpu-jax",
        dict(
            actual=jax.tree.map(np.asarray, actual)._asdict(),
            expected=[a._asdict() for a in expected],
            maximum_error_fraction=max(errors),
            worlds=2,
        ),
    )
    assert max(errors) <= 1


@pytest.mark.parametrize("empty", (False, True))
def test_cpu_jax_compiled_empty_and_invalid_domains(empty):
    before = state([], []) if empty else state([1.0], [2.0])
    after = before if empty else state([-1.0], [2.0])
    vc = np.zeros(0) if empty else np.array([2e-15])
    ve = np.zeros(0) if empty else np.array([4e-15])
    function = jax.jit(lambda b, e, v, w: arrays.change(b, e, v, w, **frame(), xp=jnp))
    actual = function(
        jax.tree.map(jnp.asarray, before),
        jax.tree.map(jnp.asarray, after),
        jnp.asarray(vc),
        jnp.asarray(ve),
    )
    actual.valid.block_until_ready()
    assert bool(actual.valid) == empty
    if empty:
        assert actual.total_free_energy_change_pJ == 0
