"""Actual charge grouping, independent endpoint fields and electrical identities."""

import ast
import inspect
from dataclasses import fields, replace
from types import SimpleNamespace

import jax
import jax.numpy as jnp
import numpy as np
import pytest

from cells.core import physiology_protein_projection as projection
from cells.core import physiology_tissue_binding as units
from cells.core.specs import parse_spec
from cells.core.state import Checkpoint
from cells.models import physiology_protein_work_view as host
from cells.numerics import physiology_protein_electrical_arrays as arrays
from cells.numerics import physiology_protein_interval_arrays as endpoints
from cells.processes.electrochemistry import F
from tests.integration.test_physiology_protein_charge_view import active_nodes, changed_protein
from tests.integration.test_physiology_protein_work_view import clamped_case, reservoir_transfer
from tests.unit.test_physiology_protein_interval_accounting import evidence
from tests.unit.test_physiology_tissue_binding import arguments, component_state
from tests.unit.test_physiology_tissue_step import KINDS, case, control, tissue
from validation.tissue import physiology_protein_electrical_arrays_reference as reference


def padded_change(before, after, binding, p, *, valence=-1):
    result = projection.delta(
        before.protein, after.protein, binding, valence=valence, faraday_C_mol=F
    )
    q = np.zeros(p.active.size + p.outside_active.size)
    q[: len(binding.tissue_cell_ids)] = result.cell_charge_delta_C
    q[p.active.size : p.active.size + len(binding.tissue_environment_ids)] = (
        result.environment_charge_delta_C
    )
    return q, result


def prepare(spec, point, binding, reference_component, before, after, *, valence=-1):
    implementation = endpoints.view.IMPLEMENTATIONS[type(spec.model)]
    p = point.layout._replace(
        membrane_permeability=units.component_permeability(before, binding).current_m_s
    )
    assert np.array_equal(
        p.membrane_permeability, units.component_permeability(after, binding).current_m_s
    )
    held = control(spec, point.time)
    b, _ = padded_change(reference_component, before, binding, p, valence=valence)
    e, _ = padded_change(reference_component, after, binding, p, valence=valence)
    request, change = padded_change(before, after, binding, p, valence=valence)
    ep0 = endpoints.endpoint_values(point.state, held, p, b, implementation=implementation, xp=np)
    ep1 = endpoints.endpoint_values(point.state, held, p, e, implementation=implementation, xp=np)
    assert ep0.charged_rates_valid and ep1.charged_rates_valid
    return ep0, ep1, request, change, implementation


def host_record(ep):
    p, state, delta = ep.runtime_layout, ep.source_state, ep.protein_charge_increment_C
    # Literal frozen charged-RHS argument grouping, independent of the new
    # electrical module. Host _electrical receives these actual snapshot data.
    ions = endpoints.passive.charge_increment(state, p, xp=np)
    actual = (
        np.r_[
            p.initial_cell_charge_C + delta[: p.active.size],
            p.initial_outside_charge_C + delta[p.active.size :],
        ]
        + ions
    )
    cap = p.field_capacitor_matrix @ ep.potential_V
    electrode = np.where(p.reservoir, cap[p.active.size :] - actual[p.active.size :], 0.0)
    field = SimpleNamespace(
        potential_V=ep.potential_V,
        membrane_voltage_V=ep.membrane_voltage_V,
        capacitor_node_charge_C=cap,
        electrode_charge_C=electrode,
    )
    return SimpleNamespace(after=field, total_charge_C=actual)


def compare(name, spec, point, binding, reference_component, before, after, *, valence=-1):
    ep0, ep1, request, change, implementation = prepare(
        spec, point, binding, reference_component, before, after, valence=valence
    )
    original = [a.tobytes() for a in (*point.state, *point.layout, request)]
    actual = arrays.evaluate(ep0, ep1, request, implementation=implementation, xp=np)
    expected_host = host._electrical(ep0.runtime_layout, host_record(ep0), host_record(ep1), change)
    errors = {}
    for field in fields(expected_host):
        key = field.name
        a, b = np.asarray(getattr(actual, key)), np.asarray(getattr(expected_host, key))
        if key.endswith("_bound_pJ"):
            budget = 3e-14 * abs(b) + 4 * abs(np.spacing(b))
            if key == "electrical_identity_bound_pJ":
                # Both use the frozen formula, whose assembly-error term is
                # itself a rounded energy difference. Account only for that
                # measured term's change; do not enlarge field/arithmetic gates.
                budget += abs(
                    abs(actual.edge_matrix_energy_difference_pJ)
                    - abs(expected_host.edge_matrix_energy_difference_pJ)
                )
        else:
            budget = (3e-27 if key.endswith("_C") else 3e-14) + 3e-10 * abs(b)
        difference = abs(a - b)
        ratio = np.divide(difference, budget, out=np.zeros_like(difference), where=budget > 0)
        assert not np.any((budget == 0) & (difference != 0)), key
        errors["host/" + key] = float(np.max(ratio, initial=0))
    declaration = dict(
        raw=spec.to_dict(),
        state=point.state._asdict(),
        binding=units.binding_record(binding),
        current_diffusion=after.diffusion.current_m2_s,
        held_control=control(spec, point.time)._asdict(),
        charge_reference=reference_component.protein._asdict(),
        before_protein=before.protein._asdict(),
        after_protein=after.protein._asdict(),
        valence=valence,
    )
    target = reference.evaluate(**declaration)
    for key in (
        "capacitor_energy_change_pJ",
        "clamp_work_pJ",
        "electrical_requirement_pJ",
        "midpoint_material_work_pJ",
        "gauge_work_coefficient_C",
    ):
        b = target[key]
        budget = (3e-27 if key.endswith("_C") else 3e-14) + 3e-10 * abs(b)
        errors["oracle/" + key] = abs(float(getattr(actual, key)) - b) / budget
    for key, mask in (
        ("membrane_capacitor_energy_change_pJ", point.layout.membrane_active),
        ("electrode_work_pJ", point.layout.outside_active),
        ("electrode_charge_change_C", point.layout.outside_active),
    ):
        a, b = np.asarray(getattr(actual, key))[mask], target[key]
        budget = (3e-27 if key.endswith("_C") else 3e-14) + 3e-10 * abs(b)
        errors["oracle/" + key] = float(np.max(abs(a - b) / budget, initial=0))
    for key in (
        "represented_material_charge_change_C",
        "requested_material_charge_change_C",
        "stored_reference_increment_change_C",
        "charge_input_roundoff_C",
    ):
        a, b = active_nodes(point, getattr(actual, key)), target[key]
        errors["oracle/" + key] = float(np.max(abs(a - b) / (3e-27 + 3e-10 * abs(b)), initial=0))
    evidence(
        "protein-electrical-arrays-" + name,
        dict(
            inputs=declaration,
            actual=actual._asdict(),
            expected=target,
            host_expected={f.name: getattr(expected_host, f.name) for f in fields(expected_host)},
            maximum_error_fraction=max(errors.values()),
            errors=errors,
            heat_inferred=False,
            driving_law_inferred=False,
        ),
    )
    assert actual.valid, [k for k, v in actual.checks.items() if not v]
    assert actual.electrical_identity_bound_pJ == (
        actual.field_residual_work_bound_pJ
        + abs(actual.edge_matrix_energy_difference_pJ)
        + actual.arithmetic_work_bound_pJ
    )
    assert max(errors.values()) <= 1
    assert abs(actual.electrical_identity_residual_pJ) <= actual.electrical_identity_bound_pJ
    assert original == [a.tobytes() for a in (*point.state, *point.layout, request)]
    return actual


@pytest.mark.parametrize("kind", KINDS)
@pytest.mark.parametrize("at_event", (False, True))
def test_initial_evolved_nonzero_common_reference_matches_host_and_full_node_oracle(kind, at_event):
    spec, point, binding, anchor, _ = case(kind, at_event=at_event, source_dt_scale=0.5)
    before = changed_protein(binding, anchor)
    after = changed_protein(binding, before)
    for stage in range(2):
        compare(
            kind + "-" + str(at_event) + "-" + str(stage),
            spec,
            point,
            binding,
            anchor,
            before,
            after,
        )
        if stage == 0:
            for _ in range(2 if at_event else 1):
                point = tissue.advance(spec, point, binding, anchor).checkpoint


def two_clamps(shared, shift=0.0):
    spec, point, binding, anchor = clamped_case(shift)
    if not shared:
        return spec, point, binding, anchor
    raw = spec.to_dict()
    for row in raw["model"]["extracellular"]:
        row.update(reservoir=False, boundary_potential_V=0.0)
    for row, voltage in zip(raw["model"]["extracellular"][:2], (0.002, -0.004), strict=True):
        row.update(reservoir=True, boundary_potential_V=voltage + shift)
    spec = parse_spec(raw)
    binding = units.bind_tissue(spec, **arguments(spec, reverse=True))
    anchor = component_state(binding)
    implementation = endpoints.view.IMPLEMENTATIONS[type(spec.model)]
    state, layout = implementation.initial_values(spec)
    return spec, Checkpoint(state, layout, 0.0, 0, 0), binding, anchor


@pytest.mark.parametrize("shared", (False, True))
def test_unequal_clamps_keep_reservoir_protein_work_and_common_gauge_coefficient(shared):
    results = []
    for shift in (0.0, 0.017):
        spec, point, binding, anchor = two_clamps(shared, shift)
        after = reservoir_transfer(spec, binding, anchor)
        result = compare(
            "clamps-" + str(shared) + "-" + str(shift), spec, point, binding, anchor, anchor, after
        )
        p = point.layout
        assert result.capacitor_energy_change_pJ == 0
        assert result.clamp_work_pJ != 0
        assert np.any(result.requested_material_charge_change_C[p.active.size :][p.reservoir] != 0)
        np.testing.assert_array_equal(
            result.electrode_charge_change_C[p.reservoir],
            -result.represented_material_charge_change_C[p.active.size :][p.reservoir],
        )
        results.append(result)
    np.testing.assert_allclose(
        results[1].electrical_requirement_pJ - results[0].electrical_requirement_pJ,
        1e12 * 0.017 * results[0].gauge_work_coefficient_C,
        rtol=3e-10,
        atol=3e-14,
    )


def test_common_reference_reversal_additivity_and_zero_change():
    spec, point, binding, a, _ = case(source_dt_scale=0.5)
    b, c = changed_protein(binding, a), changed_protein(binding, changed_protein(binding, a))
    results = {}
    for label, first, last in (
        ("ab", a, b),
        ("bc", b, c),
        ("ac", a, c),
        ("ba", b, a),
        ("aa", a, a),
    ):
        results[label] = compare("composition-" + label, spec, point, binding, a, first, last)
    for key in ("capacitor_energy_change_pJ", "clamp_work_pJ", "electrical_requirement_pJ"):
        np.testing.assert_allclose(
            getattr(results["ab"], key) + getattr(results["bc"], key),
            getattr(results["ac"], key),
            rtol=3e-10,
            atol=3e-14,
        )
        np.testing.assert_allclose(
            getattr(results["ab"], key), -getattr(results["ba"], key), rtol=3e-10, atol=3e-14
        )
        assert getattr(results["aa"], key) == 0


@pytest.mark.parametrize("tiny", (False, True))
def test_direct_requested_change_survives_tiny_or_large_reference_cancellation(tiny):
    spec, point, binding, anchor, _ = case(source_dt_scale=0.5)
    if tiny:
        anchor = replace(
            anchor,
            protein=anchor.protein._replace(
                cell_mol_m3=np.full_like(anchor.protein.cell_mol_m3, 2.0**-40),
                environment_mol_m3=np.full_like(anchor.protein.environment_mol_m3, 2.0**-40),
            ),
        )
        before, density = anchor, 2.0**-90
    else:
        before, density = changed_protein(binding, anchor), 2.0**-38
    cell, outside = (
        np.array(before.protein.cell_mol_m3),
        np.array(before.protein.environment_mol_m3),
    )
    c, o = binding.component.kernel.owner[0], binding.component.kernel.environment_owner[0]
    cell[c] -= density
    outside[o] += density * (
        binding.component.kernel.cell_volume_m3[c]
        / binding.component.kernel.environment_effective_volume_m3[o]
    )
    after = replace(
        before, protein=before.protein._replace(cell_mol_m3=cell, environment_mol_m3=outside)
    )
    result = compare("tiny-" + str(tiny), spec, point, binding, anchor, before, after)
    assert np.any(result.requested_material_charge_change_C != 0)
    assert np.any(result.charge_input_roundoff_C != 0)
    if tiny:
        assert result.diagnostics["requested_response_unresolved"]
        assert result.capacitor_energy_change_pJ == result.clamp_work_pJ == 0


def test_neutral_protein_has_no_electrical_work():
    spec, point, binding, anchor, _ = case("calcium", source_dt_scale=0.5)
    result = compare(
        "neutral", spec, point, binding, anchor, anchor, changed_protein(binding, anchor), valence=0
    )
    assert result.capacitor_energy_change_pJ == result.clamp_work_pJ == 0


@pytest.mark.parametrize(
    "edit", ("state", "permeability", "control", "grouping", "voltage", "rate_flag")
)
def test_stale_or_inconsistent_provider_records_are_refused(edit):
    spec, point, binding, anchor, _ = case(source_dt_scale=0.5)
    b, e, request, _, implementation = prepare(
        spec, point, binding, anchor, anchor, changed_protein(binding, anchor)
    )
    if edit == "state":
        value = np.array(e.source_state.amount_increment)
        value.flat[0] += 1e-4
        e = e._replace(source_state=e.source_state._replace(amount_increment=value))
        key = "source_association"
    elif edit == "permeability":
        e = e._replace(
            runtime_layout=e.runtime_layout._replace(
                membrane_permeability=e.runtime_layout.membrane_permeability * 0.97
            )
        )
        key = "source_association"
    elif edit == "control":
        e = e._replace(source_control=type(e.source_control)(*(v * 0.5 for v in e.source_control)))
        key = "source_association"
    elif edit == "grouping":
        value = np.array(e.charge_grouping_roundoff_C)
        value[0] += 1e-30
        e = e._replace(charge_grouping_roundoff_C=value)
        key = "charge_grouping"
    elif edit == "voltage":
        value = np.array(e.membrane_voltage_V)
        value[0] += 1e-4
        e = e._replace(membrane_voltage_V=value)
        key = "voltage_relation"
    else:
        e = e._replace(charged_rates_valid=np.asarray(False))
        key = "actual_rates"
    result = arrays.evaluate(b, e, request, implementation=implementation, xp=np)
    assert not result.valid and not result.checks["after/" + key]


def test_current_closure_rejects_a_floating_offset_even_with_charge_KVL_and_rate_flag():
    spec, point, binding, anchor, implementation = case(source_dt_scale=0.5)
    b, _, request, _, _ = prepare(spec, point, binding, anchor, anchor, anchor)
    fp, p = endpoints.passive.field_layout(point.layout), point.layout
    index = np.flatnonzero(fp.offset_free)[0]
    phi = b.potential_V + 0.001 * fp.floating_basis[:, index]
    vm = np.where(
        p.membrane_active, phi[p.membrane_cell] - phi[p.active.size + p.membrane_outside], 0.0
    )
    e = b._replace(potential_V=phi, membrane_voltage_V=vm)
    result = arrays.evaluate(b, e, request, implementation=implementation, xp=np)
    assert result.checks["after/matrix_charge"] and result.checks["after/voltage_relation"]
    assert result.checks["after/fixed_potential"] and result.checks["after/actual_rates"]
    assert not result.checks["after/component_current"] and not result.valid


def test_complete_control_domain_does_not_trust_a_stale_channel_rate_flag():
    spec, point, binding, anchor, implementation = case("calcium", source_dt_scale=0.5)
    b, e, request, _, _ = prepare(spec, point, binding, anchor, anchor, anchor)
    invalid = b.source_control._replace(channel=np.full_like(b.source_control.channel, 2.0))
    b, e = b._replace(source_control=invalid), e._replace(source_control=invalid)
    result = arrays.evaluate(b, e, request, implementation=implementation, xp=np)
    assert result.checks["after/source_association"] and result.checks["after/actual_rates"]
    assert not result.checks["after/control_domain"] and not result.valid


@pytest.mark.parametrize("edit", ("shape", "dtype", "nan", "padding"))
def test_requested_axis_precision_finiteness_and_inactive_padding(edit):
    spec, point, binding, anchor, implementation = case(source_dt_scale=0.5)
    b, e, request, _, _ = prepare(spec, point, binding, anchor, anchor, anchor)
    if edit in ("shape", "dtype"):
        bad = request[:-1] if edit == "shape" else request.astype(np.float32)
        with pytest.raises(ValueError, match="physical-node"):
            arrays.evaluate(b, e, bad, implementation=implementation, xp=np)
    else:
        request = np.array(request)
        request[0 if edit == "nan" else -1] = np.nan if edit == "nan" else 1e-20
        result = arrays.evaluate(b, e, request, implementation=implementation, xp=np)
        assert not result.valid and not result.checks["requested_domain"]


def test_hot_path_has_no_host_transfer_or_mutable_loop_dependency():
    for node in ast.walk(ast.parse(inspect.getsource(arrays))):
        if isinstance(node, ast.ImportFrom):
            assert node.module != "decimal" and "physiology_protein_loop" not in node.module
        if isinstance(node, ast.Attribute):
            assert node.attr not in ("item", "tolist", "device_get", "pure_callback", "io_callback")
            assert not (
                isinstance(node.value, ast.Name)
                and node.value.id == "np"
                and node.attr == "asarray"
            )


@pytest.mark.parametrize("kind", ("passive", "calcium"))
def test_cpu_jax_compiled_two_worlds_match_real_numpy_provider_records(kind):
    pairs, expected = [], []
    for index in range(2):
        if kind == "passive":
            spec, point, binding, anchor = two_clamps(True, 0.017 * index)
            after = reservoir_transfer(spec, binding, anchor)
        else:
            spec, point, binding, anchor, _ = case(kind, source_dt_scale=0.5)
            after = changed_protein(binding, anchor)
        b, e, request, _, implementation = prepare(spec, point, binding, anchor, anchor, after)
        pairs.append((b, e, request))
        expected.append(arrays.evaluate(b, e, request, implementation=implementation, xp=np))
    data = jax.tree.map(lambda *values: jnp.stack(values), *pairs)
    function = jax.jit(
        jax.vmap(lambda b, e, q: arrays.evaluate(b, e, q, implementation=implementation, xp=jnp))
    )
    actual = function(*data)
    actual.valid.block_until_ready()
    assert jax.default_backend() == "cpu" and jax.config.x64_enabled
    np.testing.assert_array_equal(actual.valid, [True, True])
    error = 0.0
    for i, target in enumerate(expected):
        for key in ("capacitor_energy_change_pJ", "clamp_work_pJ", "electrical_requirement_pJ"):
            value = float(getattr(actual, key)[i])
            wanted = float(getattr(target, key))
            error = max(error, abs(value - wanted) / (3e-14 + 3e-10 * abs(wanted)))
        for key, value in target.checks.items():
            assert bool(actual.checks[key][i]) == bool(value), key
    evidence(
        "protein-electrical-arrays-cpu-jax-" + kind,
        dict(
            compiled_scope="electrical diagnostics from actual NumPy provider records",
            actual=jax.tree.map(np.asarray, actual)._asdict(),
            expected=[a._asdict() for a in expected],
            maximum_error_fraction=error,
            worlds=2,
            fuel_interval_retry=False,
        ),
    )
    assert error <= 1
