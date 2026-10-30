"""Common-input work, strict SI admission and preserved unresolved endpoints."""

from dataclasses import replace

import jax
import jax.numpy as jnp
import numpy as np
import pytest

from cells.models import physiology_protein_work_view as host
from cells.numerics import physiology_protein_work_arrays as arrays
from cells.processes.electrochemistry import F, R
from tests.integration.test_physiology_protein_charge_view import changed_protein
from tests.integration.test_physiology_protein_work_view import reservoir_transfer
from tests.unit.test_physiology_protein_electrical_arrays import prepare, two_clamps
from tests.unit.test_physiology_protein_interval_accounting import evidence
from tests.unit.test_physiology_tissue_step import KINDS, case, control, tissue
from validation.tissue import physiology_protein_chemical_arrays_reference as chemical_reference
from validation.tissue import physiology_protein_work_arrays_reference as reference


def geometry(binding):
    k = binding.component.kernel
    return arrays.WorkGeometry(
        binding.cell_to_tissue,
        binding.environment_to_tissue,
        binding.membrane_to_tissue,
        k.cell_volume_m3,
        k.environment_effective_volume_m3,
        k.owner,
        k.environment_owner,
        k.membrane_area_m2,
    )


def frame(spec, *, valence=-1.0, standard=1.0):
    return dict(
        valence=float(valence),
        faraday_C_mol=F,
        temperature_K=spec.model.temperature_K,
        standard_concentration_mol_m3=float(standard),
        gas_constant_J_mol_K=R,
    )


def inputs(spec, point, binding, anchor, before, after, parameters):
    return dict(
        raw=spec.to_dict(),
        state=point.state._asdict(),
        binding=host.units.binding_record(binding),
        current_diffusion=after.diffusion.current_m2_s,
        held_control=control(spec, point.time)._asdict(),
        charge_reference=anchor.protein._asdict(),
        before_protein=before.protein._asdict(),
        after_protein=after.protein._asdict(),
        **parameters,
    )


def evaluate(spec, point, binding, anchor, before, after, *, valence=-1.0, standard=1.0):
    b, e, _, _, implementation = prepare(
        spec, point, binding, anchor, before, after, valence=valence
    )
    return arrays.evaluate(
        anchor.protein,
        before.protein,
        after.protein,
        b,
        e,
        geometry(binding),
        **frame(spec, valence=valence, standard=standard),
        implementation=implementation,
        xp=np,
    )


def record(result):
    return result._asdict() | dict(
        chemical=result.chemical._asdict() | dict(material=result.chemical.material._asdict()),
        electrical=result.electrical._asdict(),
        **{
            name: getattr(result, name)._asdict()
            for name in ("before_projection", "after_projection", "requested_projection")
        },
    )


def compare(
    name,
    spec,
    point,
    binding,
    anchor,
    before,
    after,
    *,
    valence=-1.0,
    standard=1.0,
    expected_valid=True,
    allowed_refusals=(),
    compare_host=True,
):
    frozen = [
        a.tobytes()
        for a in (*point.state, *point.layout, *anchor.protein, *before.protein, *after.protein)
    ]
    parameters = frame(spec, valence=valence, standard=standard)
    actual = evaluate(
        spec, point, binding, anchor, before, after, valence=valence, standard=standard
    )
    declaration = inputs(spec, point, binding, anchor, before, after, parameters)
    expected = reference.evaluate(**declaration)
    values = dict(
        chemical_energy_change_pJ=actual.chemical.total_free_energy_change_pJ,
        capacitor_energy_change_pJ=actual.electrical.capacitor_energy_change_pJ,
        clamp_work_pJ=actual.electrical.clamp_work_pJ,
        conditional_reversible_work_pJ=actual.conditional_reversible_work_pJ,
    )
    errors = {}
    for key, value in values.items():
        budget = 3e-14 + 3e-10 * abs(expected[key])
        errors["reference/" + key] = abs(value - expected[key]) / budget
    for key in (
        "cell_free_energy_change_pJ",
        "environment_free_energy_change_pJ",
        "total_free_energy_change_pJ",
    ):
        _, ratio = chemical_reference.precision(
            getattr(actual.chemical, key), expected["chemical"][key]
        )
        errors["SI_chemical/" + key] = float(np.max(ratio, initial=0))
    if actual.electrical.capacitor_energy_change_pJ == actual.electrical.clamp_work_pJ == 0:
        _, ratio = chemical_reference.precision(
            actual.conditional_reversible_work_pJ, expected["conditional_reversible_work_pJ"]
        )
        errors["pure_chemical_work_relative"] = float(ratio)
    host_values = None
    if compare_host:
        target = host.evaluate(
            spec,
            point,
            binding,
            anchor,
            before,
            after,
            protein_species_id="separate_protein",
            valence=valence,
            standard_concentration_mol_m3=standard,
        )
        host_values = dict(
            chemical_energy_change_pJ=target.thermodynamics.total_free_energy_change_pJ,
            capacitor_energy_change_pJ=target.electrical.capacitor_energy_change_pJ,
            clamp_work_pJ=target.electrical.clamp_work_pJ,
            conditional_reversible_work_pJ=target.conditional_reversible_work_pJ,
        )
        for key, value in host_values.items():
            errors["host/" + key] = abs(values[key] - value) / (3e-14 + 3e-10 * abs(value))
    refused = [key for key, value in actual.checks.items() if not value]
    evidence(
        "protein-work-arrays-" + name,
        dict(
            inputs=declaration,
            actual=record(actual),
            expected=expected,
            values=values,
            host_expected=host_values,
            expected_valid=expected_valid,
            allowed_refusals=allowed_refusals,
            refused_checks=refused,
            errors=errors,
            maximum_error_fraction=max(errors.values()),
            conditional_endpoint_only=True,
            heat_inferred=False,
            driving_law_inferred=False,
        ),
    )
    if expected_valid is not None:
        assert bool(actual.valid) == expected_valid, refused
    assert set(refused) <= set(allowed_refusals), refused
    assert max(errors.values()) <= 1
    assert not actual.valid or expected["strict_conservation_valid"]
    assert actual.valid == all(actual.checks.values())
    assert frozen == [
        a.tobytes()
        for a in (*point.state, *point.layout, *anchor.protein, *before.protein, *after.protein)
    ]
    return actual


@pytest.mark.parametrize("kind", KINDS)
@pytest.mark.parametrize("at_event", (False, True))
def test_complete_common_reference_initial_evolved_contract_matches_host_and_SI(kind, at_event):
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


@pytest.mark.parametrize("shared", (False, True))
def test_unequal_clamp_ports_and_common_shift_are_carried_into_conditional_work(shared):
    results = []
    for shift in (0.0, 0.017):
        spec, point, binding, anchor = two_clamps(shared, shift)
        after = reservoir_transfer(spec, binding, anchor)
        results.append(
            compare(
                "clamp-" + str(shared) + "-" + str(shift),
                spec,
                point,
                binding,
                anchor,
                anchor,
                after,
            )
        )
    np.testing.assert_allclose(
        results[1].conditional_reversible_work_pJ - results[0].conditional_reversible_work_pJ,
        1e12 * 0.017 * results[0].electrical.gauge_work_coefficient_C,
        rtol=3e-10,
        atol=3e-14,
    )
    assert (
        results[0].chemical.total_free_energy_change_pJ
        == results[1].chemical.total_free_energy_change_pJ
    )


def test_same_reference_reversal_additivity_zero_and_membrane_views():
    spec, point, binding, a, _ = case(source_dt_scale=0.5)
    b = changed_protein(binding, a)
    c = changed_protein(binding, b)
    records = {}
    for label, before, after in (
        ("ab", a, b),
        ("bc", b, c),
        ("ac", a, c),
        ("ba", b, a),
        ("aa", a, a),
    ):
        records[label] = compare("composition-" + label, spec, point, binding, a, before, after)
    np.testing.assert_allclose(
        records["ab"].conditional_reversible_work_pJ + records["bc"].conditional_reversible_work_pJ,
        records["ac"].conditional_reversible_work_pJ,
        rtol=3e-10,
        atol=3e-14,
    )
    np.testing.assert_allclose(
        records["ab"].conditional_reversible_work_pJ,
        -records["ba"].conditional_reversible_work_pJ,
        rtol=3e-10,
        atol=3e-14,
    )
    assert records["aa"].conditional_reversible_work_pJ == 0
    huge = replace(
        b, protein=b.protein._replace(membrane_mol_m3=np.full_like(b.protein.membrane_mol_m3, 1e99))
    )
    result = evaluate(spec, point, binding, a, a, huge)
    assert (
        result.valid
        and result.conditional_reversible_work_pJ == records["ab"].conditional_reversible_work_pJ
    )


@pytest.mark.parametrize("density", (2.0**-28, 2.0**-38))
def test_small_closed_transfer_preserves_energy_and_reports_precision(density):
    spec, point, binding, anchor = two_clamps(True)
    after = reservoir_transfer(spec, binding, anchor)
    indices = np.flatnonzero(
        np.asarray(after.protein.environment_mol_m3) != anchor.protein.environment_mol_m3
    )
    values = np.array(anchor.protein.environment_mol_m3)
    values[indices[0]] -= density
    values[indices[1]] += density
    after = replace(anchor, protein=anchor.protein._replace(environment_mol_m3=values))
    result = compare(
        "small-" + density.hex(),
        spec,
        point,
        binding,
        anchor,
        anchor,
        after,
        expected_valid=True if density == 2.0**-28 else None,
        allowed_refusals=("precision/conditional_work", "precision/requested_charge_response"),
    )
    assert result.chemical.closed_valid and result.requested_projection.strict_valid
    assert np.any(result.requested_projection.charge_delta_C != 0)


@pytest.mark.parametrize("valence", (-1.0, 0.0))
def test_tiny_neutral_work_resolves_while_lost_electrical_response_refuses(valence):
    spec, point, binding, anchor = two_clamps(True)
    stock = 2.0**-40
    anchor = replace(
        anchor,
        protein=anchor.protein._replace(
            cell_mol_m3=np.full_like(anchor.protein.cell_mol_m3, stock),
            environment_mol_m3=np.full_like(anchor.protein.environment_mol_m3, stock),
        ),
    )
    # Select both finite reservoir owners directly.
    indices = [
        binding.component.environment_ids.index(row.id)
        for row in spec.model.extracellular
        if row.reservoir
    ]
    values = np.array(anchor.protein.environment_mol_m3)
    values[indices[0]] -= 2.0**-90
    values[indices[1]] += 2.0**-90
    after = replace(anchor, protein=anchor.protein._replace(environment_mol_m3=values))
    result = compare(
        "tiny-" + str(valence),
        spec,
        point,
        binding,
        anchor,
        anchor,
        after,
        valence=valence,
        standard=stock,
        expected_valid=valence == 0,
        allowed_refusals=()
        if valence == 0
        else ("precision/requested_charge_response", "precision/conditional_work"),
    )
    assert result.chemical.closed_valid and result.requested_projection.strict_valid
    assert result.conditional_reversible_work_pJ > 0
    if valence:
        assert np.any(result.diagnostics["lost_requested_charge_mask"])
    else:
        assert result.component_roundoff_bound_pJ == result.chemical.roundoff_bound_pJ


def test_cancellation_keeps_all_terms_and_refuses_an_unresolved_work_sign():
    spec, point, binding, anchor = two_clamps(True)
    after = reservoir_transfer(spec, binding, anchor)
    first = evaluate(spec, point, binding, anchor, anchor, after)
    z = -first.chemical.total_free_energy_change_pJ / first.electrical.clamp_work_pJ
    result = compare(
        "conditional-cancellation",
        spec,
        point,
        binding,
        anchor,
        anchor,
        after,
        valence=z,
        expected_valid=False,
        allowed_refusals=("precision/conditional_work",),
    )
    assert result.chemical.closed_valid and result.electrical.valid
    assert abs(result.conditional_reversible_work_pJ) <= result.work_roundoff_bound_pJ
    assert result.chemical.total_free_energy_change_pJ != 0 and result.electrical.clamp_work_pJ != 0


@pytest.mark.parametrize("scope", ("requested", "reference"))
def test_neutral_nonconservative_protein_does_not_pass_on_coulomb_cancellation(scope):
    spec, point, binding, anchor, _ = case(source_dt_scale=0.5)
    values = np.array(anchor.protein.cell_mol_m3)
    values[0] += 1e-4
    after = replace(anchor, protein=anchor.protein._replace(cell_mol_m3=values))
    result = (
        evaluate(spec, point, binding, anchor, anchor, after, valence=0.0)
        if scope == "requested"
        else evaluate(spec, point, binding, after, anchor, anchor, valence=0.0)
    )
    assert not result.valid and result.electrical.valid and result.chemical.valid
    if scope == "requested":
        assert not result.checks["chemical/strict_closed"]
        assert not result.checks["projection/requested_strict_material_charge"]
    else:
        assert result.chemical.closed_valid
        assert not result.checks["projection/before_strict_material_charge"]


@pytest.mark.parametrize(
    "edit", ("reference", "before", "after", "permeability", "control", "state")
)
def test_protein_or_complete_field_source_mismatch_refuses_an_unrelated_endpoint(edit):
    spec, point, binding, anchor, implementation = case(source_dt_scale=0.5)
    before, after = (
        changed_protein(binding, anchor),
        changed_protein(binding, changed_protein(binding, anchor)),
    )
    b, e, _, _, _ = prepare(spec, point, binding, anchor, before, after)
    proteins = [anchor.protein, before.protein, after.protein]
    if edit in ("reference", "before", "after"):
        i = ("reference", "before", "after").index(edit)
        proteins[i] = changed_protein(binding, (anchor, before, after)[i]).protein
        key = (
            "association/after_protein_charge"
            if edit == "after"
            else "association/before_protein_charge"
        )
    elif edit == "permeability":
        e = e._replace(
            runtime_layout=e.runtime_layout._replace(
                membrane_permeability=e.runtime_layout.membrane_permeability * 0.9
            )
        )
        key = "electrical/complete_endpoint_checks"
    elif edit == "control":
        e = e._replace(source_control=type(e.source_control)(*(a * 0.9 for a in e.source_control)))
        key = "electrical/complete_endpoint_checks"
    else:
        value = np.array(e.source_state.amount_increment)
        value.flat[0] += 1e-4
        e = e._replace(source_state=e.source_state._replace(amount_increment=value))
        key = "electrical/complete_endpoint_checks"
    result = arrays.evaluate(
        *proteins, b, e, geometry(binding), **frame(spec), implementation=implementation, xp=np
    )
    assert not result.valid and not result.checks[key]


@pytest.mark.parametrize(
    "edit",
    (
        "cell_units",
        "environment_units",
        "area_units",
        "duplicate",
        "padding",
        "incidence",
        "negative",
    ),
)
def test_numeric_geometry_rechecks_actual_units_complete_coverage_and_incidence(edit):
    spec, point, binding, anchor, implementation = case(source_dt_scale=0.5)
    after = changed_protein(binding, anchor)
    b, e, _, _, _ = prepare(spec, point, binding, anchor, anchor, after)
    g = geometry(binding)
    field, factor, key = {
        "cell_units": ("cell_volume_m3", 1e15, "geometry/SI_volumes"),
        "environment_units": ("environment_volume_m3", 1e15, "geometry/SI_volumes"),
        "area_units": ("membrane_area_m2", 1e12, "geometry/SI_area"),
        "negative": ("cell_volume_m3", -1.0, "geometry/domain"),
    }.get(edit, (None, None, None))
    if field:
        g = g._replace(**{field: getattr(g, field) * factor})
    elif edit in ("duplicate", "padding"):
        value = np.array(g.cell_to_tissue)
        value[0] = value[1] if edit == "duplicate" else point.layout.active.size - 1
        g = g._replace(cell_to_tissue=value)
        key = "geometry/cell_coverage"
    else:
        g = g._replace(membrane_owner=(g.membrane_owner + 1) % g.cell_to_tissue.size)
        key = "geometry/membrane_incidence"
    with np.errstate(all="ignore"):
        result = arrays.evaluate(
            anchor.protein,
            anchor.protein,
            after.protein,
            b,
            e,
            g,
            **frame(spec),
            implementation=implementation,
            xp=np,
        )
    assert not result.valid and not result.checks[key]


@pytest.mark.parametrize("edit", ("F", "R", "T", "standard", "shape", "dtype"))
def test_scalar_parameter_frame_cannot_be_mixed_with_the_field_source(edit):
    spec, point, binding, anchor, implementation = case(source_dt_scale=0.5)
    after = changed_protein(binding, anchor)
    b, e, _, _, _ = prepare(spec, point, binding, anchor, anchor, after)
    parameters = frame(spec)
    if edit in ("F", "R", "T"):
        name = dict(F="faraday_C_mol", R="gas_constant_J_mol_K", T="temperature_K")[edit]
        parameters[name] *= 1.01
    elif edit == "standard":
        parameters["standard_concentration_mol_m3"] = -1.0
    else:
        parameters["valence"] = np.array([-1.0]) if edit == "shape" else np.float32(-1.0)
        with pytest.raises(ValueError, match="scalar float64"):
            arrays.evaluate(
                anchor.protein,
                anchor.protein,
                after.protein,
                b,
                e,
                geometry(binding),
                **parameters,
                implementation=implementation,
                xp=np,
            )
        return
    result = arrays.evaluate(
        anchor.protein,
        anchor.protein,
        after.protein,
        b,
        e,
        geometry(binding),
        **parameters,
        implementation=implementation,
        xp=np,
    )
    assert not result.valid
    assert not (
        result.chemical.closed_valid
        if edit == "standard"
        else result.checks["frame/Cells_SI_parameters"]
    )


@pytest.mark.parametrize("kind", ("passive", "calcium"))
def test_cpu_jax_compiled_two_dynamic_protein_worlds_under_one_shared_complete_frame(kind):
    spec, point, binding, anchor, implementation = case(kind, source_dt_scale=0.5)
    before, after = anchor, changed_protein(binding, anchor)
    pairs, expected = [], []
    for _ in range(2):
        b, e, _, _, _ = prepare(spec, point, binding, anchor, before, after)
        pairs.append((anchor.protein, before.protein, after.protein, b[3:], e[3:]))
        expected.append(evaluate(spec, point, binding, anchor, before, after))
        before, after = after, changed_protein(binding, after)
    shared = jax.tree.map(jnp.asarray, (b.source_state, b.source_control, b.runtime_layout))
    g, parameters = jax.tree.map(jnp.asarray, geometry(binding)), frame(spec)

    def work(a, before, after, b, e):
        first = arrays.endpoints.ArrayEndpoint(*shared, *b)
        last = arrays.endpoints.ArrayEndpoint(*shared, *e)
        return arrays.evaluate(
            a, before, after, first, last, g, **parameters, implementation=implementation, xp=jnp
        )

    batch = jax.tree.map(lambda *values: jnp.stack(values), *pairs)
    compiled = jax.jit(jax.vmap(work))
    actual = compiled(*batch)
    actual.valid.block_until_ready()
    assert jax.default_backend() == "cpu" and jax.config.x64_enabled
    np.testing.assert_array_equal(actual.valid, [True, True])
    bad_protein = batch[2]._replace(cell_mol_m3=batch[2].cell_mol_m3.at[0, 0].add(1e-4))
    refused = compiled(batch[0], batch[1], bad_protein, batch[3], batch[4])
    refused.valid.block_until_ready()
    np.testing.assert_array_equal(refused.valid, [False, True])
    assert not bool(refused.checks["association/after_protein_charge"][0])
    assert not bool(refused.checks["projection/requested_strict_material_charge"][0])
    error = 0.0
    for i, target in enumerate(expected):
        wanted = float(target.conditional_reversible_work_pJ)
        error = max(
            error,
            abs(float(actual.conditional_reversible_work_pJ[i]) - wanted)
            / (3e-14 + 3e-10 * abs(wanted)),
        )
        for key, value in target.checks.items():
            assert bool(actual.checks[key][i]) == bool(value), key
    evidence(
        "protein-work-arrays-cpu-jax-" + kind,
        dict(
            actual=record(jax.tree.map(np.asarray, actual)),
            expected=[record(x) for x in expected],
            maximum_error_fraction=error,
            worlds=2,
            dynamic_invalid_world_valid=np.asarray(refused.valid),
            compiled_scope=(
                "complete combined kernel; dynamic proteins/field traces, "
                "shared exact ions/P/geometry/controls"
            ),
            fuel_interval_retry=False,
        ),
    )
    assert error <= 1
