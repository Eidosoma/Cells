"""Independent complete Ca/fuel bath fields, source/work and original budgets.

Actual1ns prefixes and separately frozen-history clock/control probes assess
coupling. They make no full8us, equilibrium or biological trajectory claim.
"""

import json
import os
from copy import deepcopy
from functools import lru_cache
from pathlib import Path

import numpy as np
import pytest

from cells.core.errors import NumericalError
from cells.core.schedule import control_values
from cells.core.specs import ConfigError
from cells.numerics.fixed_step import rk4_step
from tests.unit.test_open_calcium_bath_events import OWNERS, control, setup
from validation.tissue import open_calcium_bath_fixtures as fixtures
from validation.tissue import open_calcium_bath_reference as reference


def evidence(name, record, arrays=None):
    if directory := os.environ.get("CELLS_COMPONENT_EVIDENCE"):
        folder = Path(directory) / "open-calcium-bath-events"
        folder.mkdir(parents=True, exist_ok=True)
        if arrays is not None:
            np.savez_compressed(folder / (name + ".npz"), **arrays)
        (folder / (name + ".json")).write_text(
            json.dumps(
                record, indent=2, allow_nan=False, default=lambda value: np.asarray(value).tolist()
            )
            + "\n"
        )


@lru_cache
def prefix(family, case="overlap"):
    schema, model, count, raw, spec, state, p = setup(family, case)
    evolved = rk4_step(
        lambda y, *args: model.rhs(y, *args, xp=np),
        state,
        1e-9,
        control(schema, spec, 0.0),
        p,
        p.active,
    )
    return schema, model, count, raw, spec, state, p, evolved, reference.bind(raw)


@pytest.mark.parametrize("family", fixtures.FAMILIES)
@pytest.mark.parametrize("case", ("overlap", "single", "negative", "permuted", "cl_only"))
def test_full36_40_independent_stage_fields_and_all_actual_bath_sources(family, case):
    schema, model, count, raw, spec, state, p, evolved, context = prefix(family, case)
    np.testing.assert_array_equal(
        reference.flatten(context, state._asdict()), reference.initial(context)
    )
    assert len(state) == len(context["shapes"]) == count
    assert len({row.kinetic_law for row in spec.model.channels}) == 56
    reference.owner.validate_padded_state(context["parent"], model.parent_state(evolved)._asdict())
    clocks = {0.0, spec.experiment.end_time, *(row.time for row in spec.experiment.changes)}
    for event in spec.model.bath_events:
        clocks.update((event.on_s, (event.on_s + event.off_s) / 2, event.off_s))
    reports, arrays = [], {}
    for i, time in enumerate(sorted(clocks)):
        stage = evolved._replace(phase_clock_s=np.asarray([time]))
        vector = reference.flatten(context, stage._asdict())
        expected, phi, proof = reference.evaluate(context, vector, held_time=time)
        value = model.readouts(stage, control(schema, spec, time), p, xp=np)
        actual = reference.flatten(context, value.derivative._asdict())
        absolute = reference.flatten(
            context,
            {
                key: np.full(shape, 3e-23 if key.endswith("_C") else 3e-12)
                for key, shape in context["shapes"].items()
            },
        )
        budget = absolute + 3e-10 * np.abs(expected)
        ratio = float(np.max(np.abs(actual - expected) / budget, initial=0))
        potential = np.r_[
            value.field.potential_V[: p.active.size][p.active],
            value.field.potential_V[p.active.size :][p.outside_active],
        ]
        reports.append(
            dict(
                time_s=time,
                error_over_budget=ratio,
                independent=proof,
                complete_fields=count,
                rate_energy_residual_pJ_s=float(value.field.energy_balance_pJ_s),
            )
        )
        arrays.update(
            {
                str(i) + "-" + key: item
                for key, item in dict(
                    state=vector,
                    actual=actual,
                    independent=expected,
                    budget=budget,
                    potential_V=potential,
                    independent_potential_V=phi,
                    actual_reservoir_supply=value.field.rates.reservoir_supply_fmol_s,
                    independent_reservoir_supply=proof["physical_reservoir_supply_fmol_s"],
                ).items()
            }
        )
        evidence(
            "stages-" + family + "-" + case,
            dict(
                definition=raw,
                stages=reports,
                scope="actual1ns prefix plus separate full clock/control probes",
            ),
            arrays,
        )
        assert value.valid and ratio <= 1.0
        np.testing.assert_allclose(potential, phi, rtol=3e-10, atol=3e-13)
        for key in (
            "dose_fmol",
            "dose_rate_fmol_s",
            "charge_C",
            "chemical_work_pJ",
            "electrochemical_work_pJ",
            "electrode_work_pJ",
        ):
            target = np.asarray(proof["program"][key])
            target = np.pad(
                target,
                [
                    (0, a - b)
                    for a, b in zip(getattr(value.signal, key).shape, target.shape, strict=True)
                ],
            )
            np.testing.assert_allclose(getattr(value.signal, key), target, rtol=3e-10, atol=3e-12)
        np.testing.assert_allclose(
            value.field.rates.reservoir_supply_fmol_s[:, p.outside_active],
            proof["physical_reservoir_supply_fmol_s"],
            rtol=3e-10,
            atol=3e-12,
        )
        np.testing.assert_allclose(
            value.field.electrode_current_A[p.outside_active],
            proof["physical_electrode_current_A"],
            rtol=3e-10,
            atol=3e-23,
        )
        for actual_key, proof_key in (
            ("chemical_energy_rate_pJ_s", "physical_chemical_power_pJ_s"),
            ("reservoir_power_pJ_s", "physical_reservoir_power_pJ_s"),
            ("electrode_power_pJ_s", "physical_electrode_power_pJ_s"),
        ):
            np.testing.assert_allclose(
                getattr(value.field, actual_key), proof[proof_key], rtol=3e-10, atol=3e-12
            )
        assert abs(value.field.energy_balance_pJ_s) <= 1e-10
        assert abs(proof["physical_energy_balance_pJ_s"]) <= 1e-10


@pytest.mark.parametrize("family", fixtures.FAMILIES)
@pytest.mark.parametrize("case", ("overlap", "negative", "cl_only"))
def test_actual_prefix_complete_original_anchor_material_charge_ER_and_fuel_budgets(family, case):
    _, model, _, raw, spec, state, p, evolved, context = prefix(family, case)
    records = []
    for row in (state, evolved):
        checks = model.check_values(row, spec)
        proof = reference.conservation(context, reference.flatten(context, row._asdict()))
        records.append(dict(diagnostics=checks, independent=proof))
        evidence(
            "conservation-" + family + "-" + case,
            dict(definition=raw, checks=records),
            {key: np.asarray(value) for key, value in row._asdict().items()},
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
            "program_energy_pJ",
        ):
            np.testing.assert_allclose(proof[key], 0.0, rtol=0, atol=1e-10, err_msg=key)
        for key in ("pool_material_fmol", "adenylate_fmol", "phosphorus_fmol"):
            np.testing.assert_allclose(proof[key], 0.0, rtol=0, atol=2e-12, err_msg=key)
        physical = reference.physical_fields(context, reference.flatten(context, row._asdict()))
        actual = model.physical_state(row, p, xp=np)
        compact = reference.owner.unpack(
            context["parent"], reference.owner.flatten(context["parent"], actual._asdict())
        )
        for key in actual._fields:
            np.testing.assert_allclose(
                compact[key],
                physical[key],
                rtol=3e-10,
                atol=3e-23 if key.endswith("_C") else 3e-12,
                err_msg=key,
            )


@pytest.mark.parametrize("family", fixtures.FAMILIES)
@pytest.mark.parametrize(
    "ledger",
    (
        "reservoir_supplied",
        "electrode_charge_transferred_C",
        "reservoir_work_pJ",
        "electrode_work_pJ",
        "reservoir_chemical_work_pJ",
    ),
)
def test_each_external_transport_work_or_charge_ledger_corruption_is_detected(family, ledger):
    _, model, _, _, spec, _, p, evolved, context = prefix(family)
    changed = np.array(getattr(evolved, ledger), copy=True)
    changed[..., np.flatnonzero(p.reservoir)[0]] += 1e-12 if ledger.endswith("_C") else 1e-4
    corrupt = evolved._replace(**{ledger: changed})
    assert model.domain_valid(corrupt, p, p.active, xp=np)
    with pytest.raises(NumericalError, match="accounting"):
        model.check_values(corrupt, spec)
    proof = reference.conservation(context, reference.flatten(context, corrupt._asdict()))
    assert any(
        np.max(np.abs(proof[key]), initial=0) > bound
        for key, bound in (
            ("outside_material_fmol", 1e-6),
            ("electrode_charge_C", 1e-15),
            ("reservoir_work_pJ", 1e-7),
            ("energy_residual_pJ", 1e-7),
        )
    )


def test_current_finite_ATP_controls_all_pump_families_under_the_actual_bath():
    schema, model, _, _, spec, state, p, _, context = prefix("energy")
    change = np.zeros_like(state.energy_amount_increment_fmol)
    used = 0.5 * p.energy_initial_amount_fmol[0]
    change[0], change[1], change[2] = -used, used, used
    depleted = state._replace(energy_amount_increment_fmol=change, phase_clock_s=np.asarray([2e-6]))
    full = state._replace(phase_clock_s=np.asarray([2e-6]))
    u = control(schema, spec, 2e-6)
    actual = model.readouts(depleted, u, p, xp=np)
    previous = model.readouts(full, u, p, xp=np)
    assert actual.valid and previous.valid
    expected, _, _ = reference.evaluate(
        context, reference.flatten(context, depleted._asdict()), held_time=2e-6
    )
    np.testing.assert_allclose(
        reference.flatten(context, actual.derivative._asdict()), expected, rtol=3e-10, atol=3e-12
    )
    for key in ("pump_cycles", "plasma_pump_cycles", "er_pump_transferred"):
        assert np.any(getattr(actual.derivative, key) != getattr(previous.derivative, key))
    # This is an A/P-preserving instantaneous rate probe. Unrecorded fuel
    # transfer is still refused as a physical history by the full ledger check.
    with pytest.raises(NumericalError):
        model.check_values(depleted, spec)


def test_actual_bath_corner_gross_turnover_crosses_0p05_with_all_other_guards_kept():
    """New low-Pi admission input; no biological or full-trajectory claim.

    A small real Pi pool makes the fractional material-turnover guard relevant
    before the inherited gate/loss ceilings. Raising real bath K then increases
    the actual Na/K demand. Only new input values and its resolved time horizon
    are chosen; no bound or production function is bypassed or patched.
    """
    schema, model, _ = OWNERS["energy"]
    raw = fixtures.definition("energy")
    targets = set(raw["model"]["bath_site_ids"])
    route = next(
        row
        for row in raw["model"]["ionic"]["membranes"]
        if row["outside"] in targets and row["pump"] is not None
    )
    pool = next(row for row in raw["model"]["energy_pools"] if row["cell_id"] == route["inside"])
    cell = next(row for row in raw["model"]["ionic"]["cells"] if row["id"] == route["inside"])
    # The inherited ER-pump decoder requires at least1e-9 mM. Stay above
    # that real-input limit; no parser or physical guard is bypassed.
    pool["initial_amount_fmol"]["Pi"] = 2e-9 * cell["volume_pL"]
    raw["model"]["bath_events"][0]["amplitude"] = 1.0
    evidence(
        "gross-turnover-actual-boundary",
        dict(
            status="evaluating_physical_input",
            raw_template=raw,
            affected_cell=route["inside"],
            bypassed_guards=[],
        ),
    )
    spec = schema.parse(raw)
    corner = model.initial_pool_turnover_bound(spec)
    empty_raw = deepcopy(raw)
    empty_raw["model"]["bath_events"] = []
    static = model.initial_pool_turnover_bound(schema.parse(empty_raw))
    evidence(
        "gross-turnover-actual-boundary",
        dict(
            status="evaluating_bounds",
            raw_template=raw,
            actual_initial_pool_corner=corner,
            actual_static_initial_pool=static,
            bypassed_guards=[],
        ),
    )
    assert corner["maximum_fraction_rate_s_inv"] > static["maximum_fraction_rate_s_inv"] > 0
    corner_step = 0.05 / corner["maximum_fraction_rate_s_inv"]
    static_step = 0.05 / static["maximum_fraction_rate_s_inv"]
    accepted_step = corner_step * (1 - 1e-6)
    rejected_step = 0.5 * (corner_step + static_step)
    # Fit the entire explicitly declared program and controls within128 nominal
    # rejected steps, keeping the original512-step quota and all other caps.
    scale = 128 * rejected_step / raw["experiment"]["end_time"]
    raw["experiment"]["end_time"] *= scale
    raw["experiment"]["observation_times"] = [
        time * scale for time in raw["experiment"]["observation_times"]
    ]
    for name, groups in raw["experiment"].items():
        if name.endswith("_controls"):
            for group in groups:
                key = "controls" if "controls" in group else "schedule"
                for row in group[key]:
                    row["time"] *= scale
    for event in raw["model"]["bath_events"]:
        for key in ("on_s", "off_s", "change_s"):
            event[key] *= scale
    inputs = {}
    checked = []
    for name, step in (("accepted", accepted_step), ("rejected", rejected_step)):
        current = deepcopy(raw)
        current["execution"]["dt"] = step
        current_spec = schema.parse(current)
        table = control_values(schema.owner_spec(current_spec), [0.0])
        inputs[name] = current
        evidence(
            "gross-turnover-actual-boundary",
            dict(
                status="checking_" + name,
                actual_initial_pool_corner=corner,
                actual_static_initial_pool=static,
                corner_step_s=corner_step,
                static_step_s=static_step,
                new_manufactured_inputs=inputs,
                completed_checks=checked,
                bypassed_guards=[],
            ),
        )
        # Both real inputs retain and pass EVERY static inherited guard.
        model.base.check_steps(schema.owner_spec(current_spec), np.asarray([step]), table)
        if name == "accepted":
            model.check_steps(current_spec, np.asarray([step]), table)
        else:
            with pytest.raises(ConfigError, match="Bath initial-pool gross turnover"):
                model.check_steps(current_spec, np.asarray([step]), table)
        checked.append(name)
    evidence(
        "gross-turnover-actual-boundary",
        dict(
            actual_initial_pool_corner=corner,
            actual_static_initial_pool=static,
            corner_step_s=corner_step,
            static_step_s=static_step,
            accepted_step_s=accepted_step,
            rejected_step_s=rejected_step,
            new_manufactured_inputs=inputs,
            inherited_guards_passed_for_both=True,
            bypassed_guards=[],
            claim="physical-input step admission only; no trajectory or biology",
        ),
    )


@pytest.mark.parametrize("family", fixtures.FAMILIES)
def test_observer_contains_all_full_owners_and_separate_programmed_histories(family):
    _, model, _, _, spec, state, p, evolved, _ = prefix(family)
    history = model.STATE_TYPE(*(np.stack((a, b)) for a, b in zip(state, evolved, strict=True)))
    observed = model.observe_history(np.asarray([0.0, 1e-9]), history, p, [0.0, 1e-9], spec)
    assert set(vars(observed)) == set(model.OBSERVATION_FIELDS)
    for key in model.base.STATE_TYPE._fields:
        np.testing.assert_array_equal(getattr(observed, key)[1], getattr(evolved, key), err_msg=key)
    signal = model.signal_values(evolved, p, xp=np)
    np.testing.assert_array_equal(
        observed.physical_reservoir_supplied[1], evolved.reservoir_supplied + signal.dose_fmol
    )
    np.testing.assert_array_equal(
        observed.physical_electrode_charge_transferred_C[1],
        evolved.electrode_charge_transferred_C - signal.charge_C,
    )
    np.testing.assert_array_equal(
        observed.physical_reservoir_chemical_work_pJ[1],
        evolved.reservoir_chemical_work_pJ + signal.chemical_work_pJ,
    )
    np.testing.assert_allclose(
        observed.ionic_moiety_fmol[1],
        model.base.readouts(
            model.parent_state(evolved),
            control(OWNERS[family][0], spec, 1e-9),
            model.stage_layout(p, signal),
            xp=np,
        ).ionic_moiety_fmol,
        rtol=0,
        atol=0,
    )
    assert np.any(observed.physical_extracellular_amount_increment[1] != 0)


@pytest.mark.parametrize("family", fixtures.FAMILIES)
def test_nonpositive_real_M_inventory_and_current_fuel_are_not_floored(family):
    schema, model, _, _, spec, state, p = setup(family)
    amount = np.array(state.chemical_amount_increment, copy=True)
    m = [row.id for row in spec.model.stores[0].species].index("M")
    amount[0, m, 0] = -p.er_initial_amount[0, m, 0]
    bad = state._replace(chemical_amount_increment=amount)
    assert not model.domain_valid(bad, p, p.active, xp=np)
    with pytest.raises(NumericalError):
        model.check_values(bad, spec)
    context = reference.bind(fixtures.definition(family))
    with pytest.raises(ValueError, match="Nonpositive"):
        reference.evaluate(context, reference.flatten(context, bad._asdict()), held_time=0.0)
    if family == "energy":
        pool = np.zeros_like(state.energy_amount_increment_fmol)
        pool[0] = -p.energy_initial_amount_fmol[0]
        exhausted = state._replace(energy_amount_increment_fmol=pool)
        assert not model.domain_valid(exhausted, p, p.active, xp=np)
        with pytest.raises(ValueError, match="positive pools"):
            reference.evaluate(
                context, reference.flatten(context, exhausted._asdict()), held_time=0.0
            )
    assert control(schema, spec, 0.0) is not None


def test_independent_reference_import_closure_contains_full_Ca_fuel_and_Decimal_setters():
    root = Path(__file__).resolve().parents[2]
    manifest = reference.dependency_manifest(root)
    required = (
        "validation/tissue/open_calcium_reference.py",
        "validation/transport/surface_bath_events_reference.py",
        "tests/reference_ip3_calcium.py",
        "validation/chemistry/finite_energy_reference.py",
    )
    assert all(name in manifest for name in required)
    assert not any(name.startswith("src/cells/") for name in manifest)
    evidence("reference-dependencies", dict(files=manifest, imported_production_or_jax=False))
