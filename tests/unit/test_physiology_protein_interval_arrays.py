"""Host/oracle parity, budget refusal and CPU compiled/vmapped array accounting."""

import ast
import ctypes
import gc
import inspect
import json
import os

import jax
import jax.numpy as jnp
import numpy as np
import pytest

from cells.core import physiology_protein_interval_accounting as host
from cells.core import physiology_tissue_binding as units
from cells.numerics import physiology_protein_interval_arrays as arrays
from tests.integration.test_physiology_protein_charge_view import changed_protein
from tests.unit import test_physiology_protein_interval_accounting as prior
from tests.unit.test_physiology_permeability_view import fingerprints
from tests.unit.test_physiology_tissue_step import KINDS, control
from validation.tissue import physiology_protein_interval_arrays_reference as reference

PRIMITIVES = (
    (1.0, 0.0, 0.0, 1.0, 1.0, 0.0),
    (1.0, 0.0, 1e-150, 1.0, 1.0, 0.0),
    (1.0, 1e-150, 2e-150, 1.0, 1.0, 0.0),
    (1.0, 0.0, 1e-300, 2.0, 1.0, 0.0),
    (1e100, 0.0, 1e-200, 1.0, 1.0, -3.0),
    (1e300, 0.0, 1e100, 1e300, 1.0, 0.0),
    (1.0, -0.9999999999999999, -0.9999999999999998, 1.0, 1.0, 0.0),
    (1.0, 0.0, 0.25, 1.0, 1.0, 0.0),
    (1.0, 0.2, -0.5, 0.01, 1000.0, 0.3),
    (1e250, 0.0, 1e-70, 1e250, 1.0, 0.0),
    (1.0, 1e-150, -1e-150, 1.0, 1.0, 0.0),
)


def inputs(spec, b, e, point, binding, anchor, current, start, end):
    p = point.layout._replace(
        membrane_permeability=units.component_permeability(current, binding).current_m_s
    )
    change = host.projection.delta(
        anchor.protein, current.protein, binding, valence=-1, faraday_C_mol=host.F
    )
    delta = np.zeros(p.active.size + p.outside_active.size)
    delta[: len(binding.tissue_cell_ids)] = change.cell_charge_delta_C
    delta[p.active.size : p.active.size + len(binding.tissue_environment_ids)] = (
        change.environment_charge_delta_C
    )
    return (
        b,
        e,
        p,
        delta,
        control(spec, start),
        control(spec, end),
        np.asarray(spec.execution.material_balance_atol_fmol),
    )


def compare(name, spec, b, e, point, binding, anchor, current, implementation, start, end):
    before = fingerprints(spec, b, point.layout, current)
    result = arrays.evaluate(
        *inputs(spec, b, e, point, binding, anchor, current, start, end),
        implementation=implementation,
        xp=np,
    )
    authoritative = prior.evaluate(
        spec, b, e, point, binding, anchor, current, start=start, end=end
    )
    assert before == fingerprints(spec, b, point.layout, current)
    declaration = dict(
        raw=spec.to_dict(),
        before=b._asdict(),
        after=e._asdict(),
        binding=units.binding_record(binding),
        current_diffusion=current.diffusion.current_m2_s,
        reference_protein=anchor.protein._asdict(),
        current_protein=current.protein._asdict(),
        valence=-1,
        before_control=control(spec, start)._asdict(),
        after_control=control(spec, end)._asdict(),
    )
    expected = reference.evaluate(declaration)
    errors = {}
    for key, target in expected["energy_terms"].items():
        errors["oracle/" + key] = abs(float(result.energy_terms[key]) - target) / (
            3e-14 + 3e-10 * abs(target)
        )
    for key, target in authoritative.balances.items():
        budget = (
            3e-27 if key.rsplit("/", 1)[-1] in ("charge", "electrode", "global_charge") else 3e-14
        )
        errors["host/" + key] = float(
            np.max(abs(result.balances[key] - target) / (budget + 3e-10 * abs(target)), initial=0)
        )
    prior.evidence(
        "protein-arrays-" + name,
        dict(
            inputs=declaration,
            actual_energy_terms=result.energy_terms,
            actual_balances=result.balances,
            expected=expected,
            checks=result.checks,
            diagnostics=result.diagnostics,
            limits=result.limits,
            maximum_error_fraction=max(errors.values()),
            errors=errors,
            host_valid=authoritative.valid,
            array_valid=result.valid,
            trajectory_accuracy_claim=False,
        ),
    )
    assert result.valid and authoritative.valid
    assert max(errors.values()) <= 1
    assert result.first_invalid_check == len(result.checks)
    assert result.limits["interval/energy"] == expected["original_energy_tolerance_pJ"]


@pytest.mark.parametrize(
    "kind,event", [(k, e) for k in KINDS for e in (False, True)] + [("open", False)]
)
def test_numpy_full_endpoint_ledgers_local_and_seed_cumulative_match_frozen_host_and_oracle(
    kind, event
):
    spec, point, binding, anchor, implementation = prior.fixture(kind, event=event)
    current = changed_protein(binding, anchor)
    h, state = spec.execution.dt / 4, point.state
    for i in range(2):
        end = prior.step(spec, state, point, binding, anchor, current, implementation, i * h, h)
        compare(
            kind + "-" + str(event) + "-local-" + str(i),
            spec,
            state,
            end,
            point,
            binding,
            anchor,
            current,
            implementation,
            i * h,
            (i + 1) * h,
        )
        state = end
    compare(
        kind + "-" + str(event) + "-cumulative",
        spec,
        point.state,
        state,
        point,
        binding,
        anchor,
        current,
        implementation,
        0.0,
        2 * h,
    )


@pytest.mark.parametrize("kind", KINDS)
def test_energy_and_heat_rejection_preserve_exact_original_budgets(kind):
    spec, point, binding, anchor, implementation = prior.fixture(kind)
    budget = 1e-9 if kind in ("calcium", "fuel") else 2e-8
    for change in (2 * budget, -3e-12):
        heat = np.array(point.state.membrane_dissipated_energy_pJ)
        heat[0] = change
        end = point.state._replace(membrane_dissipated_energy_pJ=heat)
        result = arrays.evaluate(
            *inputs(spec, point.state, end, point, binding, anchor, anchor, 0.0, 0.0),
            implementation=implementation,
            xp=np,
        )
        assert not result.valid and result.limits["interval/energy"] == budget
        if change > 0:
            assert not result.checks["interval/energy"]
        else:
            assert not result.checks["interval/nondecreasing/membrane_dissipated_energy_pJ"]


@pytest.mark.parametrize(
    "kind,name,check",
    [
        ("passive", "membrane_transferred", "after/local"),
        ("ionic", "pump_cycles", "after/metabolic_work"),
        ("calcium", "reaction_extent", "after/chemical_ledger"),
        ("calcium", "plasma_metabolic_work_pJ", "after/plasma_metabolic_work"),
        ("calcium", "er_metabolic_work_pJ", "after/er_metabolic_work"),
        ("fuel", "regeneration_supplied_work_pJ", "after/regeneration_work"),
        ("fuel", "energy_amount_increment_fmol", "after/pool_material"),
        ("fuel", "metabolic_work_pJ", "after/pool_energy"),
    ],
)
def test_complete_material_and_internal_external_work_guards(kind, name, check):
    spec, point, binding, anchor, implementation = prior.fixture(kind)
    value = np.array(getattr(point.state, name))
    value.flat[0] += 1e-4
    end = point.state._replace(**{name: value})
    result = arrays.evaluate(
        *inputs(spec, point.state, end, point, binding, anchor, anchor, 0.0, 0.0),
        implementation=implementation,
        xp=np,
    )
    assert not result.valid and not result.checks[check]
    if kind == "fuel" and name == "metabolic_work_pJ":
        assert result.energy_terms["external_metabolic_work_pJ"] == 0
        assert result.checks["interval/energy"]


@pytest.mark.parametrize("row", PRIMITIVES)
def test_numpy_tiny_quadratic_large_span_and_regular_chemical_changes(row):
    a, b, e, v, c, mu = row
    declaration = dict(
        anchor=[[a]],
        before=[[b]],
        after=[[e]],
        volume=[v],
        standard=c,
        mu0_rt=mu,
        temperature=298.15,
    )
    target = reference.ideal_change(declaration)
    result = arrays.ideal_change(
        np.array([[a]]), np.array([[b]]), np.array([[e]]), np.array([v]), c, mu, 298.15, True, xp=np
    )
    budget, ratio = reference.precision(result.value_pJ, target["value_pJ"])
    prior.evidence(
        "protein-arrays-primitive-" + str(PRIMITIVES.index(row)),
        dict(
            primitive_inputs=declaration,
            expected=target,
            actual=result._asdict(),
            budget=budget,
            error_fraction=ratio,
        ),
    )
    if target["representable"].all():
        assert result.valid.all() and np.max(ratio) <= 1
        if b != e:
            assert np.all(result.value_pJ != 0)
    else:
        assert not result.valid.all() and (result.underflow | result.cancellation_ambiguous).any()


def test_scaled_product_and_explicit_invalid_arithmetic_without_host_repair():
    value, under, over = arrays._scaled_product((1e300, 1e300, 1e-300, 1e-300), xp=np)
    assert abs(value - 1) <= 3e-15 and not under and not over
    invalid = arrays.ideal_change(
        np.array([[1e308]]),
        np.array([[1e308]]),
        np.array([[0.0]]),
        1.0,
        1.0,
        0.0,
        298.15,
        True,
        xp=np,
    )
    assert not invalid.valid.all() and invalid.overflow.any()
    exhausted = arrays.ideal_change(
        np.array([[1.0]]), np.array([[0.0]]), np.array([[-2.0]]), 1.0, 1.0, 0.0, 298.15, True, xp=np
    )
    assert not exhausted.domain_valid.all() and not exhausted.valid.all()


def test_static_shapes_and_hot_path_has_no_host_conversion_or_callback():
    source = inspect.getsource(arrays)
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute):
            assert node.attr not in ("item", "tolist", "device_get", "pure_callback", "io_callback")
            assert not (
                isinstance(node.value, ast.Name)
                and node.value.id == "np"
                and node.attr == "asarray"
            )
        if isinstance(node, ast.ImportFrom):
            assert node.module != "decimal"
    spec, point, binding, anchor, implementation = prior.fixture("passive")
    args = inputs(spec, point.state, point.state, point, binding, anchor, anchor, 0.0, 0.0)
    with pytest.raises(ValueError, match="species material tolerance"):
        arrays.evaluate(*args[:-1], np.ones(1), implementation=implementation, xp=np)


@pytest.mark.parametrize("kind", KINDS)
def test_cpu_jax_jit_vmap_accounting_from_actual_endpoint_records(kind):
    spec, point, binding, anchor, implementation = prior.fixture(kind)
    current = changed_protein(binding, anchor)
    h = spec.execution.dt / 4
    end = prior.step(spec, point.state, point, binding, anchor, current, implementation, 0.0, h)
    good = inputs(spec, point.state, end, point, binding, anchor, current, 0.0, h)
    heat = np.array(end.membrane_dissipated_energy_pJ)
    heat[0] += 3e-8
    bad = inputs(
        spec,
        point.state,
        end._replace(membrane_dissipated_energy_pJ=heat),
        point,
        binding,
        anchor,
        current,
        0.0,
        h,
    )
    # One original physical geometry/anchor recipe per compiled ensemble.
    # Current P, charge, state and controls remain actual per-world arrays.
    bad = (
        *bad[:2],
        bad[2]._replace(membrane_permeability=bad[2].membrane_permeability * 0.97),
        *bad[3:],
    )
    expected = [
        arrays.evaluate(*args, implementation=implementation, xp=np) for args in (good, bad)
    ]
    geometry = jax.tree.map(jnp.asarray, point.layout)
    world_inputs = [(*args[:2], *args[3:], args[2].membrane_permeability) for args in (good, bad)]
    batched = jax.tree.map(lambda a, b: jnp.stack((jnp.asarray(a), jnp.asarray(b))), *world_inputs)

    def prepare(state, control, delta, permeability):
        return arrays.endpoint_values(
            state,
            control,
            geometry._replace(membrane_permeability=permeability),
            delta,
            implementation=implementation,
            xp=jnp,
        )

    # The qualified charged RHS provider is evaluated as a separate device
    # operation. Compilation of two full Newton/RHS solves plus accounting in
    # one module is not claimed under the 1GiB compiler limit.
    prior.evidence(
        "protein-arrays-milestone-" + kind + "-provider-start", dict(stage="provider_start")
    )
    left_values, right_values = [], []
    with jax.disable_jit():
        for i in range(2):
            world = jax.tree.map(lambda value, index=i: value[index], batched)
            left_values.append(prepare(world[0], world[3], world[2], world[6]))
            right_values.append(prepare(world[1], world[4], world[2], world[6]))
        left_endpoint = jax.tree.map(lambda *v: jnp.stack(v), *left_values)
        right_endpoint = jax.tree.map(lambda *v: jnp.stack(v), *right_values)
    jax.block_until_ready((left_endpoint, right_endpoint))
    prior.evidence(
        "protein-arrays-milestone-" + kind + "-provider-ready", dict(stage="provider_ready")
    )
    jax.clear_caches()
    gc.collect()
    # Completed CPU provider scratch/executable pages can remain in glibc's
    # heap after caches are released. Trim only free pages, keeping every live
    # device input and endpoint buffer. This does not change the 1GiB limit.
    ctypes.CDLL(None).malloc_trim(0)
    prior.evidence(
        "protein-arrays-milestone-" + kind + "-compile-start", dict(stage="accounting_compile")
    )

    def evaluate(before, after, delta, left, right, tolerance, permeability, ep0, ep1):
        layout = geometry._replace(membrane_permeability=permeability)
        return arrays.evaluate(
            before,
            after,
            layout,
            delta,
            left,
            right,
            tolerance,
            implementation=implementation,
            xp=jnp,
            before_endpoint=ep0,
            after_endpoint=ep1,
        )

    compiled = jax.jit(jax.vmap(evaluate))
    result = compiled(*batched, left_endpoint, right_endpoint)
    result.valid.block_until_ready()
    assert jax.default_backend() == "cpu" and jax.config.x64_enabled
    np.testing.assert_array_equal(result.valid, [True, False])
    maximum = 0.0
    for i, target in enumerate(expected):
        for key, value in target.energy_terms.items():
            budget = 3e-14 + 3e-10 * abs(float(value))
            maximum = max(maximum, abs(float(result.energy_terms[key][i]) - value) / budget)
        for key, value in target.checks.items():
            assert bool(result.checks[key][i]) == bool(value), (kind, key)
    assert maximum <= 1
    prior.evidence(
        "protein-arrays-cpu-jax-" + kind,
        dict(
            kind=kind,
            valid=np.asarray(result.valid),
            numpy_energy_terms=[v.energy_terms for v in expected],
            compiled_energy_terms=jax.tree.map(np.asarray, result.energy_terms),
            maximum_error_fraction=maximum,
            batch_worlds=2,
            cpu_jit_vmap=True,
            shared_original_geometry=True,
            permeability_per_world=True,
            endpoint_provider="separate actual CPU JAX eager per-world array operations",
            compiled_scope="accounting from fully associated actual endpoint records",
        ),
    )
    if folder := os.environ.get("CELLS_COMPONENT_EVIDENCE"):
        with open(folder + "/cpu-jax-progress.jsonl", "a") as stream:
            stream.write(json.dumps(dict(kind=kind, maximum_error_fraction=maximum)) + "\n")


def test_cpu_jax_compiled_chemical_primitive_preserves_sub_bulk_quadratic_terms():
    data = np.asarray(PRIMITIVES)
    args = tuple(jnp.asarray(data[:, i : i + 1]) for i in range(6))
    function = jax.jit(
        lambda a, b, e, v, c, mu: arrays.ideal_change(a, b, e, v, c, mu, 298.15, True, xp=jnp)
    )
    result = function(*args)
    result.value_pJ.block_until_ready()
    expected = arrays.ideal_change(*(data[:, i : i + 1] for i in range(6)), 298.15, True, xp=np)
    np.testing.assert_array_equal(result.valid, expected.valid)
    budget, ratio = reference.precision(np.asarray(result.value_pJ), expected.value_pJ)
    assert np.max(ratio) <= 1
    prior.evidence(
        "protein-arrays-cpu-jax-primitive",
        dict(
            actual=jax.tree.map(np.asarray, result)._asdict(),
            expected=expected._asdict(),
            budget=budget,
            error_fraction=ratio,
        ),
    )


@pytest.mark.parametrize("kind", KINDS)
def test_numpy_endpoint_record_port_matches_full_default_accounting(kind):
    spec, point, binding, anchor, implementation = prior.fixture(kind)
    current = changed_protein(binding, anchor)
    h = spec.execution.dt / 4
    end = prior.step(spec, point.state, point, binding, anchor, current, implementation, 0.0, h)
    args = inputs(spec, point.state, end, point, binding, anchor, current, 0.0, h)
    b, e, p, delta, left, right, _ = args
    ep0 = arrays.endpoint_values(b, left, p, delta, implementation=implementation, xp=np)
    ep1 = arrays.endpoint_values(e, right, p, delta, implementation=implementation, xp=np)
    full = arrays.evaluate(*args, implementation=implementation, xp=np)
    separate = arrays.evaluate(
        *args, implementation=implementation, xp=np, before_endpoint=ep0, after_endpoint=ep1
    )
    assert separate.valid and full.valid
    for a, b in zip(jax.tree.leaves(full), jax.tree.leaves(separate), strict=True):
        np.testing.assert_array_equal(a, b)


@pytest.mark.parametrize("change", ("state", "control", "layout", "charge", "voltage", "valid"))
def test_endpoint_records_refuse_stale_context_or_altered_field_data(change):
    spec, point, binding, anchor, implementation = prior.fixture("passive")
    args = list(inputs(spec, point.state, point.state, point, binding, anchor, anchor, 0.0, 0.0))
    b, e, p, delta, left, right, _ = args
    ep0 = arrays.endpoint_values(b, left, p, delta, implementation=implementation, xp=np)
    ep1 = arrays.endpoint_values(e, right, p, delta, implementation=implementation, xp=np)
    if change == "state":
        value = np.array(e.amount_increment)
        value.flat[0] += 1e-5
        args[1] = e._replace(amount_increment=value)
    elif change == "control":
        args[5] = type(right)(*(v * 0.5 for v in right))
    elif change == "layout":
        args[2] = p._replace(membrane_permeability=p.membrane_permeability * 0.99)
    elif change == "charge":
        args[3] = np.array(delta)
        args[3][0] += 1e-20
    elif change == "voltage":
        value = np.array(ep1.membrane_voltage_V)
        value[0] += 1e-4
        ep1 = ep1._replace(membrane_voltage_V=value)
    else:
        ep1 = ep1._replace(charged_rates_valid=np.asarray(False))
    report = arrays.evaluate(
        *args, implementation=implementation, xp=np, before_endpoint=ep0, after_endpoint=ep1
    )
    assert not report.valid
    name = (
        "charged_endpoint"
        if change == "voltage"
        else "charged_field_rates"
        if change == "valid"
        else "endpoint_association"
    )
    assert not report.checks["after/" + name]


def test_numpy_provider_snapshots_do_not_alias_mutated_source_arrays():
    spec, point, binding, anchor, implementation = prior.fixture("passive")
    args = inputs(spec, point.state, point.state, point, binding, anchor, anchor, 0.0, 0.0)
    state = jax.tree.map(np.copy, args[0])
    endpoint = arrays.endpoint_values(
        state, args[4], args[2], args[3], implementation=implementation, xp=np
    )
    state.amount_increment.flat[0] += 1e-4
    assert endpoint.source_state.amount_increment.flat[0] == 0


@pytest.mark.parametrize("edit", ("cycle_voltage", "boundary_offset"))
def test_shared_cell_two_clamps_refuse_fields_that_node_charge_alone_cannot_admit(edit):
    original, _, _, _, _ = prior.fixture("open")
    raw = original.to_dict()
    for row, voltage in zip(raw["model"]["extracellular"][:2], (0.002, -0.004), strict=True):
        row.update(reservoir=True, boundary_potential_V=voltage)
    spec = prior.parse_spec(raw)
    binding = units.bind_tissue(spec, **prior.arguments(spec, reverse=True))
    implementation = arrays.view.IMPLEMENTATIONS[type(spec.model)]
    state, p = implementation.initial_values(spec)
    delta = np.zeros(p.active.size + p.outside_active.size)
    held = control(spec, 0.0)
    endpoint = arrays.endpoint_values(state, held, p, delta, implementation=implementation, xp=np)
    assert endpoint.charged_rates_valid
    if edit == "cycle_voltage":
        patches = np.flatnonzero(
            p.membrane_active & (p.membrane_cell == 0) & p.reservoir[p.membrane_outside]
        )
        assert len(patches) == 2
        a, b = patches
        vm = np.array(endpoint.membrane_voltage_V)
        vm[a] += 1e-4
        vm[b] -= 1e-4 * p.membrane_capacitance[a] / p.membrane_capacitance[b]
        altered = endpoint._replace(membrane_voltage_V=vm)
    else:
        altered = endpoint._replace(potential_V=endpoint.potential_V + 0.001)
    report = arrays.evaluate(
        state,
        state,
        p,
        delta,
        held,
        held,
        np.asarray(spec.execution.material_balance_atol_fmol),
        implementation=implementation,
        xp=np,
        before_endpoint=endpoint,
        after_endpoint=altered,
    )
    assert report.checks["after/charged_endpoint"]
    assert not report.valid
    key = "endpoint_voltage_relation" if edit == "cycle_voltage" else "endpoint_boundary"
    assert not report.checks["after/" + key]
    prior.evidence(
        "protein-arrays-clamp-refusal-" + edit,
        dict(
            definition=raw,
            binding=units.binding_record(binding),
            original_voltage=endpoint.membrane_voltage_V,
            altered_voltage=altered.membrane_voltage_V,
            original_potential=endpoint.potential_V,
            altered_potential=altered.potential_V,
            balances=report.balances,
            limits=report.limits,
            checks=report.checks,
        ),
    )
