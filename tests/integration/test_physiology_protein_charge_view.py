"""Explicit protein charge enters a field solve without changing accepted state."""

import json
import os
from dataclasses import asdict, replace
from pathlib import Path

import numpy as np
import pytest

from cells.core import physiology_perturbation_step as component_step
from cells.core import physiology_random_streams as streams
from cells.core import physiology_tissue_binding as units
from cells.core import physiology_tissue_step as tissue
from cells.models import physiology_protein_charge_view as view
from cells.processes.electrochemistry import F
from tests.unit.test_physiology_permeability_view import exact_tree, fingerprints
from tests.unit.test_physiology_tissue_step import KINDS, case, control
from validation.tissue import physiology_protein_charge_view_reference as reference


def changed_protein(binding, component):
    """Manufactured internal transfer along an actual membrane owner pair."""
    cell = np.array(component.protein.cell_mol_m3)
    outside = np.array(component.protein.environment_mol_m3)
    c, o = binding.component.kernel.owner[0], binding.component.kernel.environment_owner[0]
    density = 2.0**-16
    cell[c] -= density
    outside[o] += (
        density
        * binding.component.kernel.cell_volume_m3[c]
        / binding.component.kernel.environment_effective_volume_m3[o]
    )
    return replace(
        component,
        protein=component.protein._replace(cell_mol_m3=cell, environment_mol_m3=outside),
    )


def evaluate(spec, point, binding, baseline, current, **kwargs):
    return view.evaluate(
        spec,
        point,
        binding,
        baseline,
        current,
        protein_species_id=kwargs.pop("protein_species_id", "separate_protein"),
        valence=kwargs.pop("valence", -1),
        **kwargs,
    )


def evidence(name, record, arrays=None):
    if path := os.environ.get("CELLS_COMPONENT_EVIDENCE"):
        root = Path(path) / "protein-charge-view"
        root.mkdir(parents=True, exist_ok=True)
        (root / (name + ".json")).write_text(
            json.dumps(
                record, indent=2, allow_nan=False, default=lambda value: np.asarray(value).tolist()
            )
            + "\n"
        )
        if arrays is not None:
            np.savez_compressed(root / (name + ".npz"), **arrays)


def active_nodes(point, values):
    p, n = point.layout, point.layout.active.size
    return np.r_[values[:n][p.active], values[n:][p.outside_active]]


@pytest.mark.parametrize("kind", KINDS)
@pytest.mark.parametrize("at_event", [False, True])
def test_initial_and_evolved_field_response_matches_independent_full_node_roots(kind, at_event):
    spec, point, binding, baseline, implementation = case(
        kind, at_event=at_event, source_dt_scale=0.5
    )
    current = changed_protein(binding, baseline)
    for stage in range(2):
        before = fingerprints(spec, point.state, point.layout, current)
        actual = evaluate(spec, point, binding, baseline, current)
        held = control(spec, point.time)
        expected = reference.evaluate(
            spec.to_dict(),
            point.state._asdict(),
            units.binding_record(binding),
            current.diffusion.current_m2_s,
            held._asdict(),
            baseline.protein._asdict(),
            current.protein._asdict(),
            valence=-1,
        )
        arrays = {}
        for label in ("before", "after"):
            result, target = getattr(actual, label), expected[label]
            for name, mask in (
                ("potential_V", None),
                ("capacitor_node_charge_C", None),
                ("membrane_voltage_V", point.layout.membrane_active),
                ("membrane_charge_C", point.layout.membrane_active),
                ("electrode_charge_C", point.layout.outside_active),
            ):
                raw = getattr(result, name)
                value = active_nodes(point, raw) if mask is None else raw[mask]
                atol = 3e-25 if name.endswith("_C") else 3e-13
                np.testing.assert_allclose(value, target[name], rtol=3e-10, atol=atol)
                arrays[label + "__" + name] = value
                arrays[label + "__expected__" + name] = target[name]
            np.testing.assert_allclose(
                result.capacitor_energy_pJ, target["capacitor_energy_pJ"], rtol=3e-10, atol=3e-14
            )
            assert result.charge_normalized <= 1 and result.current_normalized <= 1
        np.testing.assert_allclose(
            active_nodes(point, actual.applied_delta_charge_C),
            expected["applied_delta_charge_C"],
            rtol=3e-13,
            atol=1e-30,
        )
        np.testing.assert_allclose(
            active_nodes(point, actual.potential_change_V),
            expected["potential_change_V"],
            rtol=3e-10,
            atol=6e-13,
        )
        assert np.max(abs(actual.potential_change_V)) > 1e-9
        assert fingerprints(spec, point.state, point.layout, current) == before
        assert actual.admission["faraday_C_mol"] == F
        assert not actual.admission["coupled_rhs"]
        assert not actual.admission["protein_transfer_work_accounted"]
        exact_tree(actual.admission["held_control"], held)
        evidence(
            "field-" + kind + "-" + str(at_event) + "-" + str(stage),
            dict(
                definition=spec.to_dict(),
                fields=point.state._asdict(),
                binding=units.binding_record(binding),
                held_control=held._asdict(),
                current_diffusion=current.diffusion.current_m2_s,
                reference_protein=baseline.protein._asdict(),
                current_protein=current.protein._asdict(),
                valence=-1,
                faraday_C_mol=F,
                numeric_time_s=point.time,
                charge_normalized=float(actual.after.charge_normalized),
                current_normalized=float(actual.after.current_normalized),
                preserved_source=True,
                coupled_trajectory=False,
            ),
            arrays,
        )
        if stage == 0:
            for _ in range(2 if at_event else 1):
                point = tissue.advance(spec, point, binding, baseline).checkpoint


@pytest.mark.parametrize("kind", KINDS)
def test_nonzero_reference_stock_and_membrane_views_add_no_charge_by_themselves(kind):
    spec, point, binding, baseline, implementation = case(kind, changed=False)
    current = replace(
        baseline,
        protein=baseline.protein._replace(
            membrane_mol_m3=np.full(len(binding.component.membrane_ids), 7e98)
        ),
    )
    actual = evaluate(spec, point, binding, baseline, current)
    original = implementation.field_values(
        point.state, control(spec, point.time), point.layout, xp=np
    )
    np.testing.assert_array_equal(actual.before.potential_V, original.potential_V)
    np.testing.assert_array_equal(actual.after.potential_V, original.potential_V)
    assert np.count_nonzero(actual.applied_delta_charge_C) == 0
    assert np.count_nonzero(actual.potential_change_V) == 0
    assert actual.capacitor_energy_change_pJ == 0


def test_view_does_not_draw_advance_finalize_or_modify_anchors(monkeypatch):
    spec, point, binding, baseline, _ = case("fuel")
    current = changed_protein(binding, baseline)
    before = fingerprints(spec, point.state, point.layout, current)

    def forbidden(*args, **kwargs):
        pytest.fail("Field view performed a material, random or numerical update")

    for module, name in ((streams, "draw"), (component_step, "advance"), (tissue, "advance")):
        monkeypatch.setattr(module, name, forbidden)
    solved = []
    original = view.surface_field.solve

    def observe(*args, **kwargs):
        solved.append((np.array(args[2]), np.array(args[3])))
        return original(*args, **kwargs)

    monkeypatch.setattr(view.surface_field, "solve", observe)
    actual = evaluate(spec, point, binding, baseline, current)
    assert fingerprints(spec, point.state, point.layout, current) == before
    np.testing.assert_array_equal(np.r_[*solved[-2]], actual.source_charge_C)
    np.testing.assert_array_equal(np.r_[*solved[-1]], actual.total_charge_C)
    for state in (actual.before, actual.after):
        for value in asdict(state).values():
            # asdict copies arrays; inspect the returned arrays themselves below.
            assert np.isfinite(value).all()
        for name in state.__dataclass_fields__:
            value = getattr(state, name)
            assert not value.flags.writeable
            with pytest.raises(ValueError):
                value.setflags(write=True)
    for value in (
        actual.source_charge_C,
        actual.applied_delta_charge_C,
        actual.total_charge_C,
        actual.potential_change_V,
    ):
        assert not value.flags.writeable


@pytest.mark.parametrize("kind,name", [("passive", "Na"), ("calcium", "IP3"), ("fuel", "ATP")])
def test_existing_ionic_chemical_or_fuel_inventory_cannot_be_counted_again(kind, name, monkeypatch):
    spec, point, binding, baseline, _ = case(kind)
    monkeypatch.setattr(
        view, "_solve", lambda *a, **k: pytest.fail("Duplicate inventory reached field")
    )
    with pytest.raises(view.ProteinChargeViewRejected, match="already belongs"):
        evaluate(spec, point, binding, baseline, baseline, protein_species_id=name)


@pytest.mark.parametrize("defect", ["clock", "layout", "material", "binding", "name", "valence"])
def test_bad_checkpoint_component_binding_or_declaration_refuses(defect):
    spec, point, binding, baseline, _ = case()
    current = changed_protein(binding, baseline)
    kwargs = {}
    if defect == "clock":
        point = replace(point, step_index=1)
    elif defect == "layout":
        point = replace(
            point,
            layout=point.layout._replace(
                initial_cell_charge_C=point.layout.initial_cell_charge_C + 1e-15
            ),
        )
    elif defect == "material":
        current = replace(
            current,
            protein=current.protein._replace(
                cell_mol_m3=np.full_like(current.protein.cell_mol_m3, -1.0)
            ),
        )
    elif defect == "binding":
        binding = replace(binding, source_definition_sha256="changed")
    elif defect == "name":
        kwargs["protein_species_id"] = ""
    else:
        kwargs["valence"] = True
    with pytest.raises(view.ProteinChargeViewRejected):
        evaluate(spec, point, binding, baseline, current, **kwargs)


def test_nonconservative_material_change_cannot_be_hidden_as_charge_input():
    spec, point, binding, baseline, _ = case()
    current = replace(
        baseline, protein=baseline.protein._replace(cell_mol_m3=baseline.protein.cell_mol_m3 + 0.01)
    )
    with pytest.raises(view.ProteinChargeViewRejected, match="external material") as raised:
        evaluate(spec, point, binding, baseline, current)
    assert raised.value.stage == "protein_projection"
    assert raised.value.projection_change is not None and raised.value.trial is None


def test_field_refusal_retains_raw_trial_and_leaves_all_sources_unchanged(monkeypatch):
    spec, point, binding, baseline, _ = case()
    current = changed_protein(binding, baseline)
    before = fingerprints(spec, point.state, point.layout, current)
    original, trials = view._solve, []

    def refuse_second(*args, **kwargs):
        answer = original(*args, **kwargs)
        trials.append(answer)
        return answer._replace(converged=np.bool_(False)) if len(trials) == 2 else answer

    monkeypatch.setattr(view, "_solve", refuse_second)
    with pytest.raises(view.ProteinChargeViewRejected, match="original field closure") as raised:
        evaluate(spec, point, binding, baseline, current)
    error = raised.value
    assert error.stage == "protein_field" and not error.trial.converged
    assert error.before is not None and error.projection_change is not None
    np.testing.assert_array_equal(error.trial.potential_V, trials[-1].potential_V)
    assert fingerprints(spec, point.state, point.layout, current) == before
    evidence(
        "rejected-field",
        dict(stage=error.stage, synthetic_status_fault=True, preserved_source=True),
        dict(raw_potential_V=error.trial.potential_V, raw_charge_C=error.charges),
    )
