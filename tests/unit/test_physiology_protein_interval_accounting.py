"""Independent interval energies, original budgets and complete-ledger refusal."""

from collections.abc import Mapping
from dataclasses import FrozenInstanceError, replace
from decimal import Decimal, localcontext

import numpy as np
import pytest

from cells.core import physiology_protein_charge_step as charged_step
from cells.core import physiology_protein_interval_accounting as accounting
from cells.core import physiology_tissue_binding as units
from cells.core.specs import parse_spec
from cells.core.state import Checkpoint
from cells.models import physiology_permeability_view as view
from tests.integration.test_physiology_protein_charge_view import changed_protein
from tests.unit.test_physiology_permeability_view import fingerprints
from tests.unit.test_physiology_tissue_binding import arguments, component_state
from tests.unit.test_physiology_tissue_step import KINDS, case, control
from tests.unit.test_physiology_tissue_step import evidence as save_evidence
from validation.tissue import physiology_protein_interval_accounting_reference as reference
from validation.tissue import surface_dynamics_fixtures


def evidence(name, record, arrays=None):
    def plain(value):
        if isinstance(value, Mapping):
            return {key: plain(item) for key, item in value.items()}
        if isinstance(value, (tuple, list)):
            return [plain(item) for item in value]
        return value

    save_evidence(name, plain(record), arrays)


def fixture(kind="passive", *, event=False):
    if kind != "open":
        return case(kind, at_event=event, source_dt_scale=0.5)
    raw = surface_dynamics_fixtures.definition("open", padded=True)
    for row in raw["model"]["extracellular"]:
        row["volume_pL"] = 4.0
    raw["execution"]["dt"] *= 0.5
    spec = parse_spec(raw)
    args = arguments(spec, reverse=True)
    args["membrane_thickness_m"] = {row.id: 2.0**-28 for row in spec.model.membranes}
    binding = units.bind_tissue(spec, **args)
    component = component_state(binding)
    implementation = view.IMPLEMENTATIONS[type(spec.model)]
    state, layout = implementation.initial_values(spec)
    return spec, Checkpoint(state, layout, 0.0, 0, 0), binding, component, implementation


def evaluate(spec, before, after, point, binding, anchor, current, *, start=0.0, end=0.0):
    return accounting.evaluate(
        spec,
        before,
        after,
        point.layout,
        binding,
        anchor,
        current,
        protein_species_id="separate_protein",
        valence=-1,
        before_control=control(spec, start),
        after_control=control(spec, end),
    )


def step(spec, state, point, binding, anchor, current, implementation, time, h):
    physical = units.component_permeability(current, binding)
    p = point.layout._replace(membrane_permeability=physical.current_m_s)
    change = accounting.projection.delta(
        anchor.protein, current.protein, binding, valence=-1, faraday_C_mol=accounting.F
    )
    delta = np.zeros(p.active.size + p.outside_active.size)
    delta[: len(binding.tissue_cell_ids)] = change.cell_charge_delta_C
    delta[p.active.size : p.active.size + len(binding.tissue_environment_ids)] = (
        change.environment_charge_delta_C
    )
    trial = charged_step.array_rk4_step(
        state, control(spec, time), p, delta, h, implementation=implementation, xp=np
    )
    assert trial.valid
    return trial.proposed_state


def compare(name, spec, before, after, point, binding, anchor, current, *, start, end):
    original = fingerprints(spec, before, point.layout, current)
    result = evaluate(spec, before, after, point, binding, anchor, current, start=start, end=end)
    assert original == fingerprints(spec, before, point.layout, current)
    raw_inputs = dict(
        raw=spec.to_dict(),
        before=before._asdict(),
        after=after._asdict(),
        binding=units.binding_record(binding),
        current_diffusion=current.diffusion.current_m2_s,
        reference_protein=anchor.protein._asdict(),
        current_protein=current.protein._asdict(),
        valence=-1,
        before_control=control(spec, start)._asdict(),
        after_control=control(spec, end)._asdict(),
    )
    target = reference.evaluate(**raw_inputs)
    errors, arrays = {}, {}
    for key, expected in target["energy_terms"].items():
        actual = result.energy_terms[key]
        budget = 3e-14 + 3e-10 * abs(expected)
        errors[key] = abs(actual - expected) / budget
        arrays["actual__" + key] = actual
        arrays["expected__" + key] = expected
        arrays["budget__" + key] = budget
    for key, expected in target["balances"].items():
        actual = np.asarray(result.balances[key])
        slices = tuple(slice(0, size) for size in np.shape(expected))
        if slices:
            actual = actual[slices]
        budget = 3e-14 + 3e-10 * abs(np.asarray(expected))
        errors[key] = float(np.max(abs(actual - expected) / budget, initial=0))
    evidence(
        "protein-interval-" + name,
        dict(
            inputs=raw_inputs,
            actual_energy_terms=dict(result.energy_terms),
            actual_balances=dict(result.balances),
            expected=target,
            errors=errors,
            limits=dict(result.limits),
            checks=dict(result.checks),
            diagnostics=dict(result.diagnostics),
            maximum_error_fraction=max(errors.values()),
            trajectory_accuracy_claim=False,
        ),
        arrays,
    )
    assert max(errors.values()) <= 1
    assert result.valid and all(result.checks.values())
    return result


@pytest.mark.parametrize(
    "kind,event", [(k, e) for k in KINDS for e in (False, True)] + [("open", False)]
)
def test_carried_charged_intervals_and_seed_cumulative_match_independent_accounting(kind, event):
    spec, point, binding, anchor, implementation = fixture(kind, event=event)
    current = changed_protein(binding, anchor)
    h, state = spec.execution.dt / 4, point.state
    for index in range(2):
        end = step(spec, state, point, binding, anchor, current, implementation, index * h, h)
        result = compare(
            kind + "-" + str(event) + "-local-" + str(index),
            spec,
            state,
            end,
            point,
            binding,
            anchor,
            current,
            start=index * h,
            end=(index + 1) * h,
        )
        if kind == "fuel":
            assert result.energy_terms["external_metabolic_work_pJ"] == 0
            assert "after/pool_energy" in result.checks and "interval/pool_energy" in result.checks
            assert "after/metabolic_work" not in result.checks
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
        start=0.0,
        end=2 * h,
    )


@pytest.mark.parametrize("kind", KINDS)
def test_zero_charge_interval_retains_original_energy_identity_and_anchors(kind):
    spec, point, binding, anchor, implementation = fixture(kind)
    h = spec.execution.dt / 4
    end = step(spec, point.state, point, binding, anchor, anchor, implementation, 0.0, h)
    result = evaluate(spec, point.state, end, point, binding, anchor, anchor, end=h)
    old = implementation.balances(end, point.layout)["energy"]
    assert abs(float(result.balances["interval/energy"]) - old) < 3e-14
    assert result.limits["interval/energy"] == (1e-9 if kind in ("calcium", "fuel") else 2e-8)


@pytest.mark.parametrize("kind", KINDS)
def test_zero_numeric_interval_with_control_jump_has_zero_energy_and_no_state_change(kind):
    spec, point, binding, anchor, _ = fixture(kind, event=True)
    current = changed_protein(binding, anchor)
    event = spec.experiment.observation_times[1]
    result = evaluate(spec, point.state, point.state, point, binding, anchor, current, end=event)
    assert all(value == 0 for value in result.energy_terms.values())
    assert result.balances["interval/energy"] == 0


@pytest.mark.parametrize("kind", ("calcium", "fuel"))
def test_family_energy_rejects_inside_gap_to_looser_passive_budget(kind):
    spec, point, binding, anchor, _ = fixture(kind)
    changed = np.array(point.state.membrane_dissipated_energy_pJ)
    changed[0] = 2e-9
    end = point.state._replace(membrane_dissipated_energy_pJ=changed)
    with pytest.raises(accounting.IntervalAccountingRejected) as error:
        evaluate(spec, point.state, end, point, binding, anchor, anchor)
    report = error.value.report
    assert report is not None and not report.valid
    assert not report.checks["interval/energy"]
    assert report.limits["interval/energy"] == 1e-9
    assert 1e-9 < abs(report.balances["interval/energy"]) < 2e-8


def test_pool_energy_rejects_internal_work_even_when_aggregate_energy_is_exactly_zero():
    spec, point, binding, anchor, _ = fixture("fuel")
    changed = np.array(point.state.metabolic_work_pJ)
    changed[0] = 2e-9
    end = point.state._replace(metabolic_work_pJ=changed)
    with pytest.raises(accounting.IntervalAccountingRejected) as error:
        evaluate(spec, point.state, end, point, binding, anchor, anchor)
    report = error.value.report
    assert report.checks["interval/energy"] and report.balances["interval/energy"] == 0
    assert not report.checks["after/pool_energy"] and not report.checks["interval/pool_energy"]
    assert report.limits["after/pool_energy"] == report.limits["interval/pool_energy"] == 1e-9


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
    ],
)
def test_independent_ledger_checks_remain_visible_with_simultaneous_energy_failure(
    kind, name, check
):
    spec, point, binding, anchor, _ = fixture(kind)
    altered = np.array(getattr(point.state, name))
    altered.flat[0] += 1e-4
    heat = np.array(point.state.membrane_dissipated_energy_pJ)
    heat[0] += 1e-5
    end = point.state._replace(**{name: altered, "membrane_dissipated_energy_pJ": heat})
    with pytest.raises(accounting.IntervalAccountingRejected) as error:
        evaluate(spec, point.state, end, point, binding, anchor, anchor)
    report = error.value.report
    assert report is not None
    assert not report.checks[check] and not report.checks["interval/energy"]
    assert check in report.diagnostics["failures"]
    np.testing.assert_array_equal(getattr(error.value.after, name), altered)
    evidence(
        "protein-interval-rejected-" + kind + "-" + name,
        dict(
            checks=dict(report.checks),
            balances=dict(report.balances),
            limits=dict(report.limits),
            diagnostics=dict(report.diagnostics),
        ),
    )


@pytest.mark.parametrize("kind", KINDS)
def test_nonnegative_and_nondecreasing_heat_guards_survive_cancelled_interval_energy(kind):
    spec, point, binding, anchor, _ = fixture(kind)
    value = np.array(point.state.membrane_dissipated_energy_pJ)
    value[0] = -3e-12
    end = point.state._replace(membrane_dissipated_energy_pJ=value)
    with pytest.raises(accounting.IntervalAccountingRejected) as error:
        evaluate(spec, point.state, end, point, binding, anchor, anchor)
    report = error.value.report
    assert report.checks["interval/energy"]
    assert not report.checks["interval/nondecreasing/membrane_dissipated_energy_pJ"]


@pytest.mark.parametrize(
    "a,b,e,v,mu",
    [
        (1.0, 0.0, 1e-150, 1.0, 0.0),
        (1.0, 1e-150, 2e-150, 1.0, 0.0),
        (1.0, 0.0, 1e-300, 2.0, 0.0),
        (1e100, 0.0, 1e-200, 1.0, -3.0),
        (1e250, 0.0, 1e-70, 1e250, 0.0),
        (1.0, -0.9999999999999999, -0.9999999999999998, 1.0, 0.0),
    ],
)
def test_tiny_changes_below_bulk_ulp_preserve_linear_and_quadratic_energy(a, b, e, v, mu):
    args = (np.array([[a]]), np.array([[b]]), np.array([[e]]), np.array([v]), 1.0, mu, 298.15)
    with localcontext() as context:
        context.prec = 9
        actual = accounting._ideal_change(*args, True)[0, 0]
        expected = reference.ideal_change(*args)[0, 0]
    with localcontext() as context:
        context.prec = 80
        fraction = abs(actual - expected) / (Decimal("3e-150") * abs(expected))
    assert actual != 0 and fraction <= 1
    evidence(
        "protein-interval-tiny-" + str(a) + "-" + str(b) + "-" + str(e),
        dict(
            args=dict(
                anchor=[[a]],
                before=[[b]],
                after=[[e]],
                volume=[v],
                standard=1.0,
                mu0_rt=mu,
                temperature=298.15,
            ),
            actual=str(actual),
            expected=str(expected),
            maximum_error_fraction=float(fraction),
            bulk_amount_rounded_unchanged=(a + e == a + b),
        ),
    )


def test_immutable_reports_original_layout_refusal_and_no_random_draw(monkeypatch):
    spec, point, binding, anchor, _ = fixture("passive")
    current = changed_protein(binding, anchor)
    monkeypatch.setattr(
        accounting.units.step.streams, "draw", lambda *a, **kw: pytest.fail("unexpected draw")
    )
    result = evaluate(spec, point.state, point.state, point, binding, anchor, current)
    with pytest.raises(FrozenInstanceError):
        result.valid = False
    with pytest.raises(TypeError):
        result.checks["forged"] = True
    with pytest.raises(ValueError):
        result.balances["interval/local"].flags.writeable = True
    changed = point.layout._replace(initial_cell_charge_C=point.layout.initial_cell_charge_C * 2)
    with pytest.raises(accounting.IntervalAccountingRejected, match="unchanged original"):
        evaluate(
            spec, point.state, point.state, replace(point, layout=changed), binding, anchor, current
        )


def test_unrepresentable_energy_retains_exact_nonzero_evidence():
    with pytest.raises(ValueError, match="Unrepresentable nonzero"):
        accounting._number(Decimal("1e-500"))


def test_nonpositive_chemical_endpoint_keeps_partial_checks_and_raw_state():
    spec, point, binding, anchor, _ = fixture("passive")
    value = np.array(point.state.amount_increment)
    value[0, 0] = -2 * point.layout.amount_reference[0, 0]
    end = point.state._replace(amount_increment=value)
    with pytest.raises(accounting.IntervalAccountingRejected) as error:
        evaluate(spec, point.state, end, point, binding, anchor, anchor)
    report = error.value.report
    assert report is not None and not report.valid
    assert not report.checks["after/domain"]
    assert not report.checks["accounting_computed"]
    np.testing.assert_array_equal(error.value.after.amount_increment, value)
