"""Complete static open-owned source/work laws, hard domains and live fuel."""

import json
import os
from copy import deepcopy
from functools import lru_cache
from pathlib import Path

import numpy as np
import pytest

from cells.core import surface_open_calcium_energy_spec as fuel_schema
from cells.core import surface_open_calcium_spec as calcium_schema
from cells.core.errors import NumericalError
from cells.core.schedule import control_values
from cells.core.specs import ConfigError
from cells.models import surface_open_calcium as calcium
from cells.models import surface_open_calcium_energy as fuel
from cells.numerics.fixed_step import rk4_step
from validation.tissue import open_calcium_fixtures as fixtures
from validation.tissue import open_calcium_reference as reference

OWNERS = {"calcium": (calcium_schema, calcium, 34), "energy": (fuel_schema, fuel, 38)}


@lru_cache
def setup(family, case="all", padded=True, depleted=False):
    schema, model, count = OWNERS[family]
    raw = fixtures.definition(family, case, padded=padded, depleted=depleted)
    spec = schema.parse(raw)
    state, layout = model.initial_values(spec)
    return schema, model, count, raw, spec, state, layout, reference.bind(raw)


def control(schema, spec, time):
    table = control_values(schema.equation_spec(spec), [time])
    return type(table)(*(v[0] for v in table))


@lru_cache
def prefix(family, case="all", padded=True, depleted=False):
    schema, model, count, raw, spec, state, p, context = setup(family, case, padded, depleted)
    value = rk4_step(
        lambda y, *args: model.rhs(y, *args, xp=np),
        state,
        fixtures.DT,
        control(schema, spec, 0.0),
        p,
        p.active,
    )
    return schema, model, count, raw, spec, state, p, context, value


def evidence(name, record, arrays=None):
    if directory := os.environ.get("CELLS_COMPONENT_EVIDENCE"):
        folder = Path(directory) / "open-owned-calcium"
        folder.mkdir(parents=True, exist_ok=True)
        if arrays is not None:
            np.savez_compressed(folder / (name + ".npz"), **arrays)
        (folder / (name + ".json")).write_text(
            json.dumps(record, indent=2, allow_nan=False, default=lambda v: np.asarray(v).tolist())
            + "\n"
        )


@pytest.mark.parametrize("family", fixtures.FAMILIES)
@pytest.mark.parametrize("case", ("all", "mixed", "blocked", "permuted"))
def test_full_owned_control_stages_and_independent_reservoir_closure(family, case):
    schema, model, count, raw, spec, state, p, context, evolved = prefix(family, case)
    assert len(state) == len(context["shapes"]) == count
    assert len({row.kinetic_law for row in spec.model.channels}) == 56
    assert np.any(evolved.chemical_amount_increment != 0) or case == "blocked"
    reference.validate_padded_state(context, state._asdict())
    reference.validate_padded_state(context, evolved._asdict())
    np.testing.assert_array_equal(
        reference.flatten(context, state._asdict()), reference.initial(context)
    )
    reports, arrays = [], {}
    for i, time in enumerate(
        sorted({0.0, spec.experiment.end_time, *(row.time for row in spec.experiment.changes)})
    ):
        u = control(schema, spec, time)
        vector = reference.flatten(context, evolved._asdict())
        expected, phi, proof = reference.evaluate(context, vector, time)
        result = model.rhs(evolved, u, p, p.active, xp=np)
        reference.validate_padded_state(context, result._asdict())
        actual = reference.flatten(context, result._asdict())
        budget = reference.flatten(
            context,
            {
                key: np.full(shape, 3e-23 if key.endswith("_C") else 3e-12)
                for key, shape in context["shapes"].items()
            },
        ) + 3e-10 * np.abs(expected)
        ratio = float(np.max(np.abs(actual - expected) / budget, initial=0))
        fields = model.readouts(evolved, u, p, xp=np)
        potential = np.r_[
            fields.field.potential_V[: p.active.size][p.active],
            fields.field.potential_V[p.active.size :][p.outside_active],
        ]
        reports.append(
            dict(
                time_s=time,
                error_over_budget=ratio,
                independent=proof,
                production_energy_residual_pJ_s=float(fields.field.energy_balance_pJ_s),
            )
        )
        arrays.update(
            {
                str(i) + "-" + key: value
                for key, value in dict(
                    state=vector,
                    actual=actual,
                    independent=expected,
                    budget=budget,
                    potential_V=potential,
                    independent_potential_V=phi,
                    additional_plasma_reservoir_supply=fields.closure.additional_reservoir_supply_fmol_s,
                ).items()
            }
        )
        evidence(
            "stages-" + family + "-" + case,
            dict(
                definition=raw,
                stages=reports,
                complete_fields=count,
                scope=(
                    "one62.5ns prefix plus frozen-history control probes; no full trajectory claim"
                ),
            ),
            arrays,
        )
        assert ratio <= 1
        assert fields.valid
        np.testing.assert_allclose(potential, phi, rtol=3e-10, atol=3e-13)
        assert abs(fields.field.energy_balance_pJ_s) <= 1e-10
        assert abs(proof["physical_energy_balance_pJ_s"]) <= 1e-10
        np.testing.assert_array_equal(result.extracellular_amount_increment[:, p.reservoir], 0.0)
        np.testing.assert_allclose(
            fields.field.rates.reservoir_supply_fmol_s[:, p.outside_active],
            proof["reservoir_supply_fmol_s"],
            rtol=3e-10,
            atol=3e-12,
        )
        np.testing.assert_allclose(
            fields.field.electrode_current_A[p.outside_active],
            proof["electrode_current_A"],
            rtol=3e-10,
            atol=3e-23,
        )
        for key, target in (
            ("reservoir_power_pJ_s", "reservoir_power_pJ_s"),
            ("electrode_power_pJ_s", "electrode_power_pJ_s"),
            ("chemical_energy_rate_pJ_s", "chemical_power_pJ_s"),
            ("capacitor_energy_rate_pJ_s", "capacitor_power_pJ_s"),
            ("dissipation_pJ_s", "dissipation_pJ_s"),
        ):
            np.testing.assert_allclose(
                getattr(fields.field, key), proof[target], rtol=3e-10, atol=3e-12
            )


@pytest.mark.parametrize("family", fixtures.FAMILIES)
@pytest.mark.parametrize("case", ("all", "mixed", "permuted"))
def test_original_molecular_capacitor_source_and_fuel_budgets(family, case):
    _, model, _, raw, spec, state, p, context, evolved = prefix(family, case)
    reports = []
    for value in (state, evolved):
        diagnostics = model.check_values(value, spec)
        proof = reference.conservation(context, reference.flatten(context, value._asdict()))
        reports.append(dict(diagnostics=diagnostics, proof=proof))
        evidence(
            "conservation-" + family + "-" + case,
            dict(definition=raw, checks=reports),
            {key: np.asarray(v) for key, v in evolved._asdict().items()},
        )
        for key in (
            "local_material_fmol",
            "outside_material_fmol",
            "chemical_ledger_fmol",
            "ionic_ownership_fmol",
            "nonionic_moiety_fmol",
            "ionic_global_fmol",
        ):
            np.testing.assert_allclose(proof[key], 0.0, rtol=0, atol=3e-14, err_msg=key)
        for key in ("capacitor_charge_C", "electrode_charge_C", "global_charge_C"):
            np.testing.assert_allclose(proof[key], 0.0, rtol=0, atol=3e-25, err_msg=key)
        for key in (
            "reservoir_work_pJ",
            "electrode_work_pJ",
            "energy_residual_pJ",
            "pool_energy_pJ",
        ):
            np.testing.assert_allclose(proof[key], 0.0, rtol=0, atol=1e-10, err_msg=key)
        for key in ("pool_material_fmol", "adenylate_fmol", "phosphorus_fmol"):
            np.testing.assert_allclose(proof[key], 0.0, rtol=0, atol=2e-12, err_msg=key)


@pytest.mark.parametrize("family", fixtures.FAMILIES)
@pytest.mark.parametrize(
    "ledger",
    (
        "reservoir_supplied",
        "electrode_charge_transferred_C",
        "reservoir_work_pJ",
        "electrode_work_pJ",
    ),
)
def test_finite_external_ledger_corruption_cannot_be_hidden(family, ledger):
    _, model, _, _, spec, _, p, context, evolved = prefix(family)
    changed = np.array(getattr(evolved, ledger), copy=True)
    changed.flat[0] += 1e-12 if ledger.endswith("_C") else 1e-4
    corrupt = evolved._replace(**{ledger: changed})
    assert model.domain_valid(corrupt, p, p.active, xp=np)
    with pytest.raises(NumericalError, match="accounting"):
        model.check_values(corrupt, spec)
    proof = reference.conservation(context, reference.flatten(context, corrupt._asdict()))
    assert (
        np.max(np.abs(proof["outside_material_fmol"])) > 1e-6
        or np.max(np.abs(proof["electrode_charge_C"])) > 1e-15
        or abs(proof["energy_residual_pJ"]) > 1e-6
    )


@pytest.mark.parametrize("family", fixtures.FAMILIES)
def test_complete_extra_plasma_supply_is_required_by_actual_reservoir_rates(family):
    schema, model, _, _, spec, state, p, _ = setup(family)
    value = model.readouts(state, control(schema, spec, 0.0), p, xp=np)
    raw = value.parent
    assert np.any(raw.derivative.extracellular_amount_increment[:, p.reservoir] != 0)
    np.testing.assert_array_equal(
        value.derivative.extracellular_amount_increment[:, p.reservoir], 0
    )
    np.testing.assert_allclose(
        value.derivative.reservoir_supplied - raw.derivative.reservoir_supplied,
        value.closure.additional_reservoir_supply_fmol_s,
        rtol=5e-15,
        atol=3e-14,
    )
    assert np.any(value.derivative.reservoir_supplied != raw.derivative.reservoir_supplied)
    assert np.any(
        value.derivative.electrode_charge_transferred_C
        != raw.derivative.electrode_charge_transferred_C
    )


@pytest.mark.parametrize("family", fixtures.FAMILIES)
def test_ionic_ceiling_is_a_hard_domain_limit_not_a_conserved_pool_or_clamp(family):
    schema, model, _, raw, spec, state, p, context = setup(family)
    u = control(schema, spec, 0.0)
    initial = reference.ionic_moieties(context, reference.initial(context))
    index = spec.model.species_ids.index("Na")
    # A valid carried interior amount can exceed the original closed total;
    # its explicit source/material history is required by check_values.
    changed = np.array(state.chemical_amount_increment, copy=True)
    owner = 0
    chemical_names = [s.id for s in spec.model.stores[owner].species]
    cy = next(
        i
        for i, row in enumerate(spec.model.stores[owner].compartments)
        if row.id == spec.model.stores[owner].membrane.cytosol
    )
    changed[owner, chemical_names.index("Na"), cy] += 1.0
    changed[owner, chemical_names.index("Cl"), cy] += 1.0
    exchange = np.array(state.amount_increment, copy=True)
    exchange[index, owner] += 1.0
    exchange[spec.model.species_ids.index("Cl"), owner] += 1.0
    probe = state._replace(chemical_amount_increment=changed, amount_increment=exchange)
    # This algebraic interior probe tests the domain only, not reachability or
    # capacitor/material conservation of an unintegrated injection.
    assert model.domain_valid(probe, p, p.active, xp=np)
    assert model.control_domain_valid(probe, u, p, p.active, xp=np)
    assert (
        reference.ionic_moieties(context, reference.flatten(context, probe._asdict()))[index]
        > initial[index]
    )
    narrow = raw.copy()
    narrow["model"] = deepcopy(raw["model"])
    narrow["model"]["ionic_moiety_ceiling_fmol"]["Na"] = initial[index] + 0.5
    constrained = schema.parse(narrow)
    _, limited = model.initial_values(constrained)
    assert not model.domain_valid(probe, limited, limited.active, xp=np)
    rejected = model.rhs(probe, u, limited, limited.active, xp=np)
    assert all(np.isnan(v).all() for v in rejected)
    with pytest.raises(ValueError, match="exceeded"):
        reference.evaluate(reference.bind(narrow), reference.flatten(context, probe._asdict()), 0.0)
    np.testing.assert_array_equal(probe.chemical_amount_increment, changed)


@pytest.mark.parametrize("family", fixtures.FAMILIES)
def test_independent_open_bounds_and_inherited_step_limits(family):
    schema, model, _, raw, spec, _, _, context = setup(family)
    independent = reference.loss_bound(context)
    actual = model.loss_bound(spec)
    np.testing.assert_allclose(actual, independent["total_s_inverse"], rtol=5e-13, atol=3e-12)
    table = control_values(schema.equation_spec(spec), [0.0])
    model.check_steps(spec, np.asarray([fixtures.DT]), table)
    with pytest.raises(ConfigError):
        model.check_steps(spec, np.asarray([max(2e-6, 0.25 / actual * (1 + 1e-7))]), table)
    for bad in (float("nan"), float("inf"), -1e-9):
        with pytest.raises(ConfigError, match="finite nonnegative"):
            model.check_steps(spec, np.asarray([bad]), table)
    larger = deepcopy(raw)
    larger["model"]["ionic_moiety_ceiling_fmol"]["Ca"] *= 1e6
    widened = schema.parse(larger)
    assert model.loss_bound(widened) >= actual
    cutoff = 0.25 / model.loss_bound(widened)
    assert cutoff < 1.25e-6
    # Separate step-bound probes, not a claim that the fixture's unchanged
    # nominal integration grid is admitted under this wider domain.
    model.check_steps(widened, np.asarray([cutoff * (1 - 1e-8)]), table)
    with pytest.raises(ConfigError, match="loss"):
        model.check_steps(widened, np.asarray([cutoff * (1 + 1e-8)]), table)
    evidence(
        "loss-bound-" + family,
        dict(
            definition=raw,
            independent=independent,
            production_s_inverse=actual,
            limits=(
                "explicit ionic ceilings; true nonionic and neutral fuel conservation; "
                "strict stage domains"
            ),
        ),
    )


def test_finite_fuel_uses_actual_current_pools_for_all_pump_families():
    schema, model, _, _, spec, state, p, _ = setup("energy")
    u = control(schema, spec, 0.0)
    normal = model.readouts(state, u, p, xp=np)
    # Material-consistent neutral counterfactual: hydrolyse half the current
    # ATP in one owner, preserving both A and P. This probes rates, not a
    # zero-work reachable history or a rebased energy anchor.
    delta = np.array(state.energy_amount_increment_fmol, copy=True)
    used = p.energy_initial_amount_fmol[0, 0] / 2
    delta[:, 0] += [-used, used, used]
    carried = state._replace(energy_amount_increment_fmol=delta)
    assert model.domain_valid(carried, p, p.active, xp=np)
    current = model.readouts(carried, u, p, xp=np)
    assert current.valid
    for key in ("pump_cycles", "plasma_pump_cycles", "er_pump_transferred"):
        assert np.any(getattr(normal.derivative, key) != getattr(current.derivative, key)), key
    context = reference.bind(setup("energy")[3])
    expected, _, _ = reference.evaluate(context, reference.flatten(context, carried._asdict()), 0.0)
    actual = reference.flatten(context, current.derivative._asdict())
    budget = reference.flatten(
        context,
        {
            key: np.full(shape, 3e-23 if key.endswith("_C") else 3e-12)
            for key, shape in context["shapes"].items()
        },
    ) + 3e-10 * np.abs(expected)
    assert np.max(np.abs(actual - expected) / budget) <= 1


@pytest.mark.parametrize("family", fixtures.FAMILIES)
def test_observer_reports_complete_physical_reservoir_work_and_domain(family):
    schema, model, _, _, spec, _, p, _, evolved = prefix(family)
    history = model.STATE_TYPE(*(v[None] for v in evolved))
    observed = model.observe_history(np.asarray([0.0]), history, p, [0.0], spec)
    value = model.readouts(evolved, control(schema, spec, 0.0), p, xp=np)
    np.testing.assert_array_equal(
        observed.reservoir_supply_fmol_s[0], value.derivative.reservoir_supplied
    )
    np.testing.assert_array_equal(
        observed.electrode_current_A[0], value.derivative.electrode_charge_transferred_C
    )
    np.testing.assert_array_equal(observed.ionic_moiety_fmol[0], value.ionic_moiety_fmol)
    np.testing.assert_array_equal(observed.ideal_reservoir_active[0], p.reservoir)
    assert abs(observed.energy_balance_pJ_s[0, 0]) <= 1e-10
    empty = model.observe_history(np.asarray([0.0]), history, p, [], spec)
    assert all(v.shape[0] == 0 for v in vars(empty).values())


@pytest.mark.parametrize("family", fixtures.FAMILIES)
@pytest.mark.parametrize("fault", ("outside_zero", "cytosol_zero", "ER_zero", "nan", "padding"))
def test_actual_nonpositive_inventory_or_bad_padding_is_rejected_without_floor(family, fault):
    schema, model, _, _, spec, state, p, context = setup(family, "mixed")
    ca = spec.model.species_ids.index("Ca")
    if fault == "outside_zero":
        change = np.array(state.extracellular_amount_increment, copy=True)
        index = np.flatnonzero(p.outside_active & ~p.reservoir)[0]
        change[ca, index] = -p.extracellular_amount_reference[ca, index]
        probe = state._replace(extracellular_amount_increment=change)
    elif fault in ("cytosol_zero", "ER_zero"):
        store = model.base.store_layout(model.parent_layout(p), 0)
        part = store.cytosol if fault == "cytosol_zero" else store.er
        change = np.array(state.chemical_amount_increment, copy=True)
        amount = store.initial_amount[store.calcium, part]
        change[0, store.calcium, part] = -amount
        ionic = np.array(state.amount_increment, copy=True)
        ionic[ca, 0] = -amount
        probe = state._replace(chemical_amount_increment=change, amount_increment=ionic)
    else:
        change = np.array(state.amount_increment, copy=True)
        change[0, -1 if fault == "padding" else 0] = 1e-4 if fault == "padding" else np.nan
        probe = state._replace(amount_increment=change)
    before = {key: np.array(v, copy=True) for key, v in probe._asdict().items()}
    assert not model.domain_valid(probe, p, p.active, xp=np)
    assert not model.control_domain_valid(probe, control(schema, spec, 0.0), p, p.active, xp=np)
    with pytest.raises(NumericalError):
        model.check_values(probe, spec)
    if fault == "padding":
        with pytest.raises(ValueError, match="padding"):
            reference.validate_padded_state(context, probe._asdict())
    else:
        with np.errstate(all="ignore"), pytest.raises((ValueError, AssertionError)):
            reference.evaluate(context, reference.flatten(context, probe._asdict()), 0.0)
    for key in probe._fields:
        np.testing.assert_array_equal(getattr(probe, key), before[key], err_msg=key)


def test_actual_finite_ATP_exhaustion_is_not_replaced_by_maintained_fuel():
    schema, model, _, _, spec, state, p, context = setup("energy")
    change = np.array(state.energy_amount_increment_fmol, copy=True)
    amount = p.energy_initial_amount_fmol[0, 0]
    change[:, 0] = [-amount, amount, amount]
    exhausted = state._replace(energy_amount_increment_fmol=change)
    assert not model.domain_valid(exhausted, p, p.active, xp=np)
    assert not model.control_domain_valid(exhausted, control(schema, spec, 0.0), p, p.active, xp=np)
    with pytest.raises(NumericalError):
        model.check_values(exhausted, spec)
    with pytest.raises(ValueError, match="positive pools"):
        reference.evaluate(context, reference.flatten(context, exhausted._asdict()), 0.0)
