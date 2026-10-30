"""Common-reference endpoint chemistry, capacitance and clamp work."""

import json
import os
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest

from cells.core import physiology_random_streams as streams
from cells.core import physiology_tissue_binding as units
from cells.core import physiology_tissue_step as tissue
from cells.core.schedule import event_index
from cells.core.specs import parse_spec
from cells.core.state import Checkpoint
from cells.models import physiology_protein_work_view as work
from tests.integration.test_physiology_protein_charge_view import active_nodes, changed_protein
from tests.unit.test_physiology_permeability_view import fingerprints
from tests.unit.test_physiology_tissue_binding import arguments, component_state
from tests.unit.test_physiology_tissue_step import KINDS, case, control
from validation.tissue import physiology_protein_work_view_reference as reference
from validation.tissue import surface_dynamics_fixtures as fixtures


def evaluate(spec, point, binding, anchor, before, after, *, valence=-1, standard=1.0):
    return work.evaluate(
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


def evidence(name, record, arrays=None):
    if directory := os.environ.get("CELLS_COMPONENT_EVIDENCE"):
        root = Path(directory) / "protein-work-view"
        root.mkdir(parents=True, exist_ok=True)
        (root / (name + ".json")).write_text(
            json.dumps(
                record, indent=2, allow_nan=False, default=lambda value: np.asarray(value).tolist()
            )
            + "\n"
        )
        if arrays is not None:
            np.savez_compressed(root / (name + ".npz"), **arrays)


def totals(result):
    return dict(
        chemical_energy_change_pJ=result.thermodynamics.total_free_energy_change_pJ,
        capacitor_energy_change_pJ=result.electrical.capacitor_energy_change_pJ,
        clamp_work_pJ=result.electrical.clamp_work_pJ,
        conditional_reversible_work_pJ=result.conditional_reversible_work_pJ,
    )


def compare(name, spec, point, binding, anchor, before, after, *, valence=-1, standard=1.0):
    initial = fingerprints(spec, point.state, point.layout, after)
    actual = evaluate(
        spec, point, binding, anchor, before, after, valence=valence, standard=standard
    )
    held = control(spec, point.time)
    expected = reference.evaluate(
        spec.to_dict(),
        point.state._asdict(),
        units.binding_record(binding),
        after.diffusion.current_m2_s,
        held._asdict(),
        anchor.protein._asdict(),
        before.protein._asdict(),
        after.protein._asdict(),
        valence=valence,
        standard_concentration_mol_m3=standard,
    )
    got = totals(actual)
    for key, value in got.items():
        np.testing.assert_allclose(value, expected[key], rtol=3e-10, atol=3e-14)
    owner_terms = dict(
        owner_chemical_energy_change_pJ=np.r_[
            actual.thermodynamics.cell_free_energy_change_pJ,
            actual.thermodynamics.environment_free_energy_change_pJ,
        ],
        membrane_capacitor_energy_change_pJ=actual.electrical.membrane_capacitor_energy_change_pJ[
            point.layout.membrane_active
        ],
        electrode_work_pJ=actual.electrical.electrode_work_pJ[point.layout.outside_active],
    )
    for key, value in owner_terms.items():
        np.testing.assert_allclose(value, expected[key], rtol=3e-10, atol=3e-14)
    for label in ("before", "after"):
        field = getattr(actual, label + "_field").after
        np.testing.assert_allclose(
            active_nodes(point, field.potential_V),
            expected[label + "_potential_V"],
            rtol=3e-10,
            atol=3e-13,
        )
        assert field.charge_normalized <= 1 and field.current_normalized <= 1
    electric = actual.electrical
    assert abs(electric.electrical_identity_residual_pJ) <= electric.electrical_identity_bound_pJ
    assert fingerprints(spec, point.state, point.layout, after) == initial
    assert not actual.admission["ionic_holding_work_accounted"]
    assert not actual.admission["driving_or_heat_law_inferred"]
    evidence(
        name,
        dict(
            definition=spec.to_dict(),
            fields=point.state._asdict(),
            binding=units.binding_record(binding),
            current_diffusion=after.diffusion.current_m2_s,
            held_control=held._asdict(),
            charge_reference=anchor.protein._asdict(),
            before=before.protein._asdict(),
            after=after.protein._asdict(),
            valence=valence,
            standard_concentration_mol_m3=standard,
            numeric_time_s=point.time,
            actual=got,
            expected={key: expected[key] for key in got},
            electrical_identity_residual_pJ=electric.electrical_identity_residual_pJ,
            electrical_identity_bound_pJ=electric.electrical_identity_bound_pJ,
            conditional_endpoint_only=True,
        ),
        dict(
            requested_charge_C=electric.requested_material_charge_change_C,
            represented_charge_C=electric.represented_material_charge_change_C,
            input_roundoff_C=electric.charge_input_roundoff_C,
            electrode_charge_change_C=electric.electrode_charge_change_C,
            actual_before_phi=active_nodes(point, actual.before_field.after.potential_V),
            actual_after_phi=active_nodes(point, actual.after_field.after.potential_V),
            expected_before_phi=expected["before_potential_V"],
            expected_after_phi=expected["after_potential_V"],
            **{"actual_" + key: value for key, value in owner_terms.items()},
            **{"expected_" + key: expected[key] for key in owner_terms},
        ),
    )
    return actual


@pytest.mark.parametrize("kind", KINDS)
@pytest.mark.parametrize("at_event", [False, True])
def test_initial_and_evolved_work_matches_independent_full_node_and_Decimal_reference(
    kind, at_event
):
    spec, point, binding, anchor, _ = case(kind, at_event=at_event, source_dt_scale=0.5)
    after = changed_protein(binding, anchor)
    for stage in range(2):
        compare(
            "field-" + kind + "-" + str(at_event) + "-" + str(stage),
            spec,
            point,
            binding,
            anchor,
            anchor,
            after,
        )
        if stage == 0:
            for _ in range(2 if at_event else 1):
                point = tissue.advance(spec, point, binding, anchor).checkpoint


def clamped_case(shift=0.0):
    raw = fixtures.definition("clamped", padded=True)
    for owner in raw["model"]["extracellular"]:
        owner["volume_pL"] = 4.0
        if owner["reservoir"]:
            owner["boundary_potential_V"] += shift
    spec = parse_spec(raw)
    binding = units.bind_tissue(spec, **arguments(spec, reverse=True))
    anchor = component_state(binding)
    implementation = work.charge_view.permeability.IMPLEMENTATIONS[type(spec.model)]
    state, layout = implementation.initial_values(spec)
    return spec, Checkpoint(state, layout, 0.0, 0, event_index(spec, 0.0)), binding, anchor


def reservoir_transfer(spec, binding, anchor):
    reservoirs = [row.id for row in spec.model.extracellular if row.reservoir]
    assert len(reservoirs) == 2
    indices = [binding.component.environment_ids.index(name) for name in reservoirs]
    values = np.array(anchor.protein.environment_mol_m3)
    values[indices[0]] -= 2.0**-16
    values[indices[1]] += 2.0**-16
    return replace(anchor, protein=anchor.protein._replace(environment_mol_m3=values))


def test_transfer_between_two_clamp_owners_keeps_both_protein_stocks_and_correct_work_sign():
    spec, point, binding, anchor = clamped_case()
    after = reservoir_transfer(spec, binding, anchor)
    result = compare("two-clamps", spec, point, binding, anchor, anchor, after)
    assert result.electrical.capacitor_energy_change_pJ == 0
    assert result.electrical.clamp_work_pJ > 0
    assert result.thermodynamics.total_free_energy_change_pJ > 0
    assert result.conditional_reversible_work_pJ < 0
    np.testing.assert_array_equal(
        result.before_field.after.potential_V, result.after_field.after.potential_V
    )
    mask = point.layout.reservoir
    represented = result.electrical.represented_material_charge_change_C[point.layout.active.size :]
    np.testing.assert_array_equal(
        result.electrical.electrode_charge_change_C[mask], -represented[mask]
    )


def test_common_reference_reversal_additivity_and_zero_change():
    spec, point, binding, a, _ = case()
    b = changed_protein(binding, a)
    c = changed_protein(binding, b)
    ab = evaluate(spec, point, binding, a, a, b)
    ba = evaluate(spec, point, binding, a, b, a)
    bc = evaluate(spec, point, binding, a, b, c)
    ac = evaluate(spec, point, binding, a, a, c)
    aa = evaluate(spec, point, binding, a, a, a)
    for name in totals(ab):
        np.testing.assert_allclose(totals(ab)[name], -totals(ba)[name], rtol=3e-10, atol=3e-14)
        np.testing.assert_allclose(
            totals(ab)[name] + totals(bc)[name], totals(ac)[name], rtol=3e-10, atol=3e-14
        )
        assert totals(aa)[name] == 0
    np.testing.assert_array_equal(
        ab.after_field.after.potential_V, bc.before_field.after.potential_V
    )


def test_clamp_voltage_reference_shift_has_declared_electrode_charge_coefficient():
    results = []
    for shift in (0.0, 0.017):
        spec, point, binding, anchor = clamped_case(shift)
        results.append(
            compare(
                "gauge-" + str(shift),
                spec,
                point,
                binding,
                anchor,
                anchor,
                reservoir_transfer(spec, binding, anchor),
            )
        )
    first, last = results
    predicted = 1e12 * 0.017 * first.electrical.gauge_work_coefficient_C
    np.testing.assert_allclose(
        last.conditional_reversible_work_pJ - first.conditional_reversible_work_pJ,
        predicted,
        rtol=3e-10,
        atol=3e-14,
    )
    np.testing.assert_allclose(
        last.electrical.capacitor_energy_change_pJ,
        first.electrical.capacitor_energy_change_pJ,
        rtol=3e-10,
        atol=3e-14,
    )


def test_neutral_protein_has_chemical_work_without_electrical_work():
    spec, point, binding, anchor, _ = case("fuel")
    result = compare(
        "neutral", spec, point, binding, anchor, anchor, changed_protein(binding, anchor), valence=0
    )
    assert result.electrical.capacitor_energy_change_pJ == result.electrical.clamp_work_pJ == 0
    assert (
        result.conditional_reversible_work_pJ == result.thermodynamics.total_free_energy_change_pJ
    )


def test_empty_endpoint_owners_have_finite_ideal_energy_changes():
    spec, point, binding, anchor, _ = case()
    c, o = binding.component.kernel.owner[0], binding.component.kernel.environment_owner[0]
    inside = np.zeros_like(anchor.protein.cell_mol_m3)
    inside[c] = 2.0**-20
    outside = np.zeros_like(anchor.protein.environment_mol_m3)
    anchor = replace(
        anchor, protein=anchor.protein._replace(cell_mol_m3=inside, environment_mol_m3=outside)
    )
    outside = np.array(outside)
    outside[o] = (
        inside[c]
        * binding.component.kernel.cell_volume_m3[c]
        / binding.component.kernel.environment_effective_volume_m3[o]
    )
    after = replace(
        anchor,
        protein=anchor.protein._replace(
            cell_mol_m3=np.zeros_like(inside), environment_mol_m3=outside
        ),
    )
    result = compare("zero-owners", spec, point, binding, anchor, anchor, after)
    assert all(np.isfinite(v) for v in totals(result).values())


def test_tiny_change_keeps_requested_versus_represented_charge_difference_visible():
    spec, point, binding, anchor, _ = case()
    c, o = binding.component.kernel.owner[0], binding.component.kernel.environment_owner[0]
    inside = np.array(anchor.protein.cell_mol_m3)
    outside = np.array(anchor.protein.environment_mol_m3)
    inside[c] -= 2.0**-38
    outside[o] += (
        2.0**-38
        * binding.component.kernel.cell_volume_m3[c]
        / binding.component.kernel.environment_effective_volume_m3[o]
    )
    after = replace(
        anchor, protein=anchor.protein._replace(cell_mol_m3=inside, environment_mol_m3=outside)
    )
    result = compare("tiny-change", spec, point, binding, anchor, anchor, after)
    assert np.any(result.electrical.charge_input_roundoff_C != 0)
    assert np.any(result.electrical.requested_material_charge_change_C != 0)


@pytest.mark.parametrize("standard", [0.0, -1.0, float("nan")])
def test_invalid_ideal_reference_refuses_without_source_change(standard):
    spec, point, binding, anchor, _ = case()
    before = fingerprints(spec, point.state, point.layout, anchor)
    with pytest.raises(work.ProteinWorkViewRejected):
        evaluate(
            spec,
            point,
            binding,
            anchor,
            anchor,
            changed_protein(binding, anchor),
            standard=standard,
        )
    assert fingerprints(spec, point.state, point.layout, anchor) == before


@pytest.mark.parametrize("defect", ["permeability", "creation", "resolution_only"])
def test_changes_outside_closed_held_parameter_work_contract_refuse_before_fields(
    defect, monkeypatch
):
    spec, point, binding, anchor, _ = case()
    after = changed_protein(binding, anchor)
    if defect == "permeability":
        after = replace(
            after,
            diffusion=after.diffusion._replace(current_m2_s=after.diffusion.current_m2_s * 0.5),
        )
    elif defect == "creation":
        after = replace(
            anchor, protein=anchor.protein._replace(cell_mol_m3=anchor.protein.cell_mol_m3 + 0.01)
        )
    else:
        value = np.array(anchor.protein.cell_mol_m3)
        value[0] = np.nextafter(value[0], np.inf)
        after = replace(anchor, protein=anchor.protein._replace(cell_mol_m3=value))
    monkeypatch.setattr(
        work.charge_view,
        "evaluate",
        lambda *a, **k: pytest.fail("Invalid work contract reached field"),
    )
    with pytest.raises(work.ProteinWorkViewRejected):
        evaluate(spec, point, binding, anchor, anchor, after)


def test_endpoint_field_failure_retains_original_trial_and_first_endpoint(monkeypatch):
    spec, point, binding, anchor, _ = case()
    after = changed_protein(binding, anchor)
    original, calls = work.charge_view.evaluate, []

    def refuse_second(*args, **kwargs):
        result = original(*args, **kwargs)
        calls.append(result)
        if len(calls) == 2:
            raise work.charge_view.ProteinChargeViewRejected(
                "injected closure refusal",
                stage="protein_field",
                before=result.before,
                charges=result.total_charge_C,
                change=result.projection_change,
            )
        return result

    monkeypatch.setattr(work.charge_view, "evaluate", refuse_second)
    with pytest.raises(work.ProteinWorkViewRejected) as raised:
        evaluate(spec, point, binding, anchor, anchor, after)
    assert raised.value.stage == "after_field" and raised.value.before_field is calls[0]
    assert raised.value.field_rejection is not None and raised.value.electrical is None


def test_work_view_is_read_only_and_does_not_draw_or_advance(monkeypatch):
    spec, point, binding, anchor, _ = case("fuel")
    after = changed_protein(binding, anchor)
    fingerprint = fingerprints(spec, point.state, point.layout, after)
    for module, name in ((streams, "draw"), (tissue, "advance")):
        monkeypatch.setattr(
            module, name, lambda *a, **k: pytest.fail("Endpoint work advanced an owner")
        )
    result = evaluate(spec, point, binding, anchor, anchor, after)
    assert fingerprints(spec, point.state, point.layout, after) == fingerprint
    for value in work.vars_from_slots(result.electrical):
        if isinstance(value, np.ndarray):
            assert not value.flags.writeable
            with pytest.raises(ValueError):
                value.setflags(write=True)
    with pytest.raises(TypeError):
        result.admission["coupled_trajectory"] = True
