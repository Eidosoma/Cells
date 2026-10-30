"""Full held-protein ionic/chemical rates and their independent field roots."""

import json
import os
from dataclasses import replace
from pathlib import Path

import jax
import jax.numpy as jnp
import numpy as np
import pytest

from cells.core import physiology_random_streams as streams
from cells.core import physiology_tissue_binding as units
from cells.core import physiology_tissue_step as tissue
from cells.models import physiology_protein_charge_rhs as rhs
from tests.integration.test_physiology_protein_charge_view import active_nodes, changed_protein
from tests.unit.test_physiology_permeability_view import exact_tree, fingerprints
from tests.unit.test_physiology_tissue_step import KINDS, case, control
from validation.tissue import physiology_protein_charge_rhs_reference as reference


def evaluate(spec, point, binding, anchor, current, *, valence=-1):
    return rhs.evaluate(
        spec,
        point,
        binding,
        anchor,
        current,
        protein_species_id="separate_protein",
        valence=valence,
        step_s=spec.execution.dt / 4,
    )


def evidence(name, record, arrays=None):
    if directory := os.environ.get("CELLS_COMPONENT_EVIDENCE"):
        root = Path(directory) / "protein-charge-rhs"
        root.mkdir(parents=True, exist_ok=True)
        (root / (name + ".json")).write_text(
            json.dumps(
                record, indent=2, allow_nan=False, default=lambda value: np.asarray(value).tolist()
            )
            + "\n"
        )
        if arrays is not None:
            np.savez_compressed(root / (name + ".npz"), **arrays)


def compare(name, spec, point, binding, anchor, current):
    source = fingerprints(spec, point.state, point.layout, current)
    actual = evaluate(spec, point, binding, anchor, current)
    held = control(spec, point.time)
    context, target, phi, proof = reference.evaluate(
        spec.to_dict(),
        point.state._asdict(),
        units.binding_record(binding),
        current.diffusion.current_m2_s,
        held._asdict(),
        anchor.protein._asdict(),
        current.protein._asdict(),
        valence=-1,
    )
    oracle = reference.permeability.ORACLES[spec.to_dict()["model"]["id"]]
    packed = oracle.flatten(context, actual.derivative._asdict())
    atol = oracle.flatten(
        context,
        {
            key: np.full(shape, 3e-23 if key.endswith("_C") else 3e-12)
            for key, shape in context["shapes"].items()
        },
    )
    budget = atol + 3e-10 * abs(target)
    fraction = abs(packed - target) / budget
    got_phi = active_nodes(point, actual.field.potential_V)
    evidence(
        name,
        dict(
            definition=spec.to_dict(),
            fields=point.state._asdict(),
            binding=units.binding_record(binding),
            current_diffusion=current.diffusion.current_m2_s,
            held_control=held._asdict(),
            reference_protein=anchor.protein._asdict(),
            current_protein=current.protein._asdict(),
            valence=-1,
            numeric_time_s=point.time,
            step_s=spec.execution.dt / 4,
            complete_derivative_fields=len(point.state),
            maximum_rate_error_fraction=np.max(fraction),
            energy_rate_residual_pJ_s=actual.field.energy_balance_pJ_s,
            reference_proof=proof,
            passive_fraction=actual.admission["passive_fraction"],
            fuel_fraction=actual.admission["fuel_fraction"],
            ordinary_history_fixture=True,
            coupled_trajectory=False,
        ),
        dict(
            actual_rate=packed,
            expected_rate=target,
            budget=budget,
            actual_phi=got_phi,
            expected_phi=phi,
            requested_charge=actual.rates.protein_charge_increment_C,
            actual_charge=actual.rates.actual_charge_C,
            charge_grouping_roundoff=actual.rates.charge_grouping_roundoff_C,
        ),
    )
    assert np.isfinite(fraction).all() and np.max(fraction) <= 1
    assert len(context["shapes"]) == len(point.state)
    np.testing.assert_allclose(got_phi, phi, rtol=3e-10, atol=3e-13)
    assert actual.field.charge_normalized <= 1 and actual.field.current_normalized <= 1
    assert abs(float(actual.field.energy_balance_pJ_s)) <= 1e-10
    assert fingerprints(spec, point.state, point.layout, current) == source
    assert actual.admission["coupled_rhs"] and not actual.admission["coupled_trajectory"]
    assert np.any(actual.derivative.amount_increment != actual.original.derivative.amount_increment)
    return actual


@pytest.mark.parametrize("kind", KINDS)
@pytest.mark.parametrize("at_event", [False, True])
def test_complete_initial_and_evolved_rates_match_independent_reference(kind, at_event):
    spec, point, binding, anchor, _ = case(kind, at_event=at_event, source_dt_scale=0.5)
    current = changed_protein(binding, anchor)
    for stage in range(2):
        compare(
            "stage-" + kind + "-" + str(at_event) + "-" + str(stage),
            spec,
            point,
            binding,
            anchor,
            current,
        )
        if stage == 0:
            for _ in range(2 if at_event else 1):
                point = tissue.advance(spec, point, binding, anchor).checkpoint


@pytest.mark.parametrize("kind", KINDS)
@pytest.mark.parametrize("neutral", [False, True])
def test_zero_offset_is_exact_complete_original_model_identity(kind, neutral):
    spec, point, binding, anchor, _ = case(kind)
    current = changed_protein(binding, anchor) if neutral else anchor
    result = evaluate(spec, point, binding, anchor, current, valence=0 if neutral else -1)
    exact_tree(result.rates.readouts, result.original.readouts)
    exact_tree(result.derivative, result.original.derivative)
    assert np.all(result.rates.protein_charge_increment_C == 0)
    assert np.all(result.rates.charge_grouping_roundoff_C == 0)


@pytest.mark.parametrize("kind", ["passive", "fuel"])
def test_array_port_executes_on_cpu_JAX_with_the_same_charge_and_rates(kind):
    spec, point, binding, anchor, implementation = case(kind)
    current = changed_protein(binding, anchor)
    result = evaluate(spec, point, binding, anchor, current)
    actual = rhs.array_readouts(
        jax.tree.map(jnp.asarray, point.state),
        jax.tree.map(jnp.asarray, control(spec, point.time)),
        jax.tree.map(jnp.asarray, result.original.runtime_layout),
        jnp.asarray(result.rates.protein_charge_increment_C),
        implementation=implementation,
        xp=jnp,
    )
    assert actual.valid
    for name in result.derivative._fields:
        np.testing.assert_allclose(
            getattr(actual.derivative, name),
            getattr(result.derivative, name),
            rtol=3e-10,
            atol=3e-23 if name.endswith("_C") else 3e-12,
        )
    np.testing.assert_allclose(
        actual.field.potential_V, result.field.potential_V, rtol=3e-10, atol=3e-13
    )
    np.testing.assert_array_equal(actual.actual_charge_C, result.rates.actual_charge_C)


@pytest.mark.parametrize("kind", ["calcium", "fuel"])
def test_ER_intrinsics_stay_owned_while_plasma_influx_and_fuel_demand_respond(kind):
    spec, point, binding, anchor, _ = case(kind)
    result = evaluate(spec, point, binding, anchor, changed_protein(binding, anchor))
    before, after = result.original.derivative, result.derivative
    for name in (
        "reaction_extent",
        "reaction_dissipated_energy_pJ",
        "er_passive_transferred",
        "er_pump_transferred",
        "er_release_transferred",
        "er_transport_dissipated_energy_pJ",
        "er_metabolic_work_pJ",
    ):
        np.testing.assert_array_equal(getattr(before, name), getattr(after, name))
    di = after.amount_increment - before.amount_increment
    expected = np.stack(
        [
            (point.layout.free_ion_selector @ di[:, i])[:, None] * point.layout.cytosol_selector[i]
            for i in range(point.layout.er_initial_amount.shape[0])
        ]
    )
    np.testing.assert_allclose(
        after.chemical_amount_increment - before.chemical_amount_increment,
        expected,
        rtol=3e-10,
        atol=3e-12,
    )
    original, charged = result.original.readouts, result.rates.readouts
    if kind == "fuel":
        exact_tree(original.energy, charged.energy)
        exact_tree(original.regeneration, charged.regeneration)
        assert np.any(before.energy_amount_increment_fmol != after.energy_amount_increment_fmol)
        original, charged = original.kinetic, charged.kinetic
    np.testing.assert_array_equal(original.er_voltage_V, charged.er_voltage_V)
    arguments = rhs._charge_arguments(
        result.original.runtime_layout, result.rates.protein_charge_increment_C
    )
    for name in point.layout._fields:
        if name not in ("initial_cell_charge_C", "initial_outside_charge_C"):
            np.testing.assert_array_equal(
                getattr(arguments, name), getattr(result.original.runtime_layout, name)
            )


def test_evolved_fuel_rates_use_live_pools_when_reference_rebuilds_its_calcium_context():
    from cells.core.schedule import event_index
    from cells.core.specs import parse_spec
    from cells.core.state import Checkpoint
    from tests.unit.test_physiology_tissue_binding import arguments, component_state, definition

    raw = definition("fuel")
    raw["execution"]["dt"] *= 0.5
    for port in raw["experiment"]["regeneration_controls"]:
        for entry in port["schedule"]:
            entry["availability"] = 0.0
    spec = parse_spec(raw)
    binding = units.bind_tissue(spec, **arguments(spec, reverse=True))
    anchor = component_state(binding)
    state, layout = rhs.permeability.fuel.initial_values(spec)
    point = Checkpoint(state, layout, 0.0, 0, event_index(spec, 0.0))
    for _ in range(2):
        point = tissue.advance(spec, point, binding, anchor).checkpoint
    assert np.any(point.state.energy_amount_increment_fmol[0] < 0)
    current = changed_protein(binding, anchor)
    result = compare("stage-live-fuel", spec, point, binding, anchor, current)
    # An initial-pool shortcut is a wrong-frame numerical control, not another
    # biological case. It must disagree under the actual comparison budget.
    fields = dict(
        point.state._asdict(),
        energy_amount_increment_fmol=np.zeros_like(point.state.energy_amount_increment_fmol),
    )
    context, wrong, _, _ = reference.evaluate(
        spec.to_dict(),
        fields,
        units.binding_record(binding),
        current.diffusion.current_m2_s,
        control(spec, point.time)._asdict(),
        anchor.protein._asdict(),
        current.protein._asdict(),
        valence=-1,
    )
    oracle = reference.permeability.ORACLES[spec.to_dict()["model"]["id"]]
    actual = oracle.flatten(context, result.derivative._asdict())
    assert np.any(abs(actual - wrong) > 3e-12 + 3e-10 * abs(actual))


def test_shifted_complete_channel_domain_refuses_despite_a_converged_passive_field():
    spec, point, binding, anchor, _ = case("ionic")
    small = changed_protein(binding, anchor)
    current = replace(
        anchor,
        protein=anchor.protein._replace(
            cell_mol_m3=anchor.protein.cell_mol_m3
            + 256 * (small.protein.cell_mol_m3 - anchor.protein.cell_mol_m3),
            environment_mol_m3=anchor.protein.environment_mol_m3
            + 256 * (small.protein.environment_mol_m3 - anchor.protein.environment_mol_m3),
        ),
    )
    source = fingerprints(spec, point.state, point.layout, current)
    with pytest.raises(rhs.ProteinChargeRHSRejected) as raised:
        evaluate(spec, point, binding, anchor, current)
    error = raised.value
    assert error.stage == "charged_rates" and error.charge_response is not None
    assert error.charge_response.after.charge_normalized <= 1
    assert error.trial is not None and not error.trial.valid
    evidence(
        "rejected-channel-domain",
        dict(
            stage=error.stage,
            reason=str(error),
            complete_rate_valid=error.trial.valid,
            charge_normalized=error.charge_response.after.charge_normalized,
        ),
    )
    assert fingerprints(spec, point.state, point.layout, current) == source


def test_actual_charged_turnover_guard_retains_full_trial(monkeypatch):
    spec, point, binding, anchor, _ = case("fuel")
    monkeypatch.setattr(tissue, "_gross_fractions", lambda *a, **k: (0.01, 0.051, True))
    with pytest.raises(rhs.ProteinChargeRHSRejected) as raised:
        evaluate(spec, point, binding, anchor, changed_protein(binding, anchor))
    assert raised.value.stage == "gross_turnover" and raised.value.trial.valid
    assert raised.value.diagnostics["fuel_fraction"] == 0.051


def test_read_only_view_never_advances_or_draws_and_keeps_history_and_buffers_immutable(
    monkeypatch,
):
    spec, point, binding, anchor, _ = case("fuel")
    current = changed_protein(binding, anchor)
    before = fingerprints(spec, point.state, point.layout, current)
    for module, name in ((streams, "draw"), (tissue, "advance")):
        monkeypatch.setattr(module, name, lambda *a, **k: pytest.fail("RHS advanced an owner"))
    result = evaluate(spec, point, binding, anchor, current)
    assert fingerprints(spec, point.state, point.layout, current) == before
    for value in jax.tree.leaves(result.rates):
        assert not value.flags.writeable
        with pytest.raises(ValueError):
            value.setflags(write=True)
    with pytest.raises(TypeError):
        result.admission["coupled_trajectory"] = True


@pytest.mark.parametrize("defect", ["shape", "padding"])
def test_array_charge_owner_axis_cannot_broadcast_or_hide_in_padding(defect):
    spec, point, binding, anchor, implementation = case()
    result = evaluate(spec, point, binding, anchor, changed_protein(binding, anchor))
    delta = np.array(result.rates.protein_charge_increment_C)
    if defect == "shape":
        with pytest.raises(ValueError, match="owner axis"):
            rhs.array_readouts(
                point.state,
                control(spec, point.time),
                result.original.runtime_layout,
                delta[None, :],
                implementation=implementation,
                xp=np,
            )
    else:
        delta[np.flatnonzero(~point.layout.active)[0]] = 1e-25
        actual = rhs.array_readouts(
            point.state,
            control(spec, point.time),
            result.original.runtime_layout,
            delta,
            implementation=implementation,
            xp=np,
        )
        assert not actual.valid
