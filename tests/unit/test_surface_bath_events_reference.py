"""Independent complete bath stages and original-anchor conservation checks.

Short1ns transport prefixes and separate clock/control probes qualify coupling
and controller accounting. They are not full bath trajectories or equilibration.
"""

import json
import os
from functools import lru_cache
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from cells.core.errors import NumericalError
from cells.core.specs import ConfigError
from cells.numerics.fixed_step import rk4_step
from tests.unit.test_surface_bath_events import control, setup
from validation.transport import surface_bath_events_fixtures as fixtures
from validation.transport import surface_bath_events_reference as reference


def evidence(name, record, arrays=None):
    if directory := os.environ.get("CELLS_COMPONENT_EVIDENCE"):
        folder = Path(directory) / "surface-bath-events"
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
    u = control(schema, spec, 0.0)
    evolved = rk4_step(lambda y, *args: model.rhs(y, *args, xp=np), state, 1e-9, u, p, p.active)
    return schema, model, count, raw, spec, state, p, evolved, reference.bind(raw)


def budget(context, target):
    return reference.flatten(
        context,
        {
            key: np.full(shape, 3e-23 if key.endswith("_C") else 3e-12)
            for key, shape in context["shapes"].items()
        },
    ) + 3e-10 * np.abs(target)


@pytest.mark.parametrize("family", fixtures.FAMILIES)
def test_complete_all_control_and_bath_clock_stages_from_actual_prefix(family):
    schema, model, count, raw, spec, state, p, evolved, c = prefix(family)
    clocks = {0.0, spec.experiment.end_time, *(v.time for v in spec.experiment.changes)}
    for event in spec.model.bath_events:
        clocks.update((event.on_s, (event.on_s + event.off_s) / 2, event.off_s))
    np.testing.assert_array_equal(reference.flatten(c, state._asdict()), reference.initial(c))
    assert np.any(evolved.face_transferred != 0)
    if family == "active":
        assert np.any(evolved.channel_transferred != 0)
        assert len({v.kinetic_law for v in spec.model.channels}) == 56
    reports, arrays = [], {}
    for i, time in enumerate(sorted(clocks)):
        stage = evolved._replace(phase_clock_s=np.asarray([time]))
        vector = reference.flatten(c, stage._asdict())
        target, phi, proof = reference.evaluate(c, vector, held_time=time)
        u = control(schema, spec, time)
        actual = reference.flatten(c, model.rhs(stage, u, p, p.active, xp=np)._asdict())
        bound = budget(c, target)
        ratio = float(np.max(np.abs(actual - target) / bound, initial=0))
        fields = model.field_values(stage, u, p, xp=np)
        expected_fields = reference.field_observables(c, vector, target, phi, held_time=time)
        potential = np.r_[
            fields.potential_V[: p.active.size][p.active],
            fields.potential_V[p.active.size :][p.outside_active],
        ]
        reports.append(
            dict(
                time_s=time,
                error_over_budget=ratio,
                independent=proof,
                controller_chemical_power_pJ_s=float(
                    np.sum(proof["program"]["chemical_power_pJ_s"])
                ),
                transport_energy_residual_pJ_s=float(fields.energy_balance_pJ_s),
            )
        )
        arrays.update(
            {
                str(i) + "-" + key: value
                for key, value in dict(
                    state=vector,
                    actual=actual,
                    independent=target,
                    budget=bound,
                    potential_V=potential,
                    independent_potential_V=phi,
                    physical_reservoir_supply=fields.rates.reservoir_supply_fmol_s,
                    independent_reservoir_supply=expected_fields["reservoir_supply_fmol_s"],
                ).items()
            }
        )
        evidence(
            "stages-" + family,
            dict(
                definition=raw,
                stages=reports,
                complete_fields=count,
                scope="actual1ns transport prefix plus independent stage-clock/control probes",
            ),
            arrays,
        )
        assert ratio <= 1
        assert fields.converged
        np.testing.assert_allclose(potential, phi, rtol=3e-10, atol=3e-13)
        for key in (
            "dose_fmol",
            "dose_rate_fmol_s",
            "charge_C",
            "chemical_work_pJ",
            "electrochemical_work_pJ",
            "electrode_work_pJ",
        ):
            np.testing.assert_allclose(
                getattr(model.signal_values(stage, p, xp=np), key),
                np.pad(
                    proof["program"][key],
                    [
                        (0, a - b)
                        for a, b in zip(
                            getattr(model.signal_values(stage, p, xp=np), key).shape,
                            proof["program"][key].shape,
                            strict=True,
                        )
                    ],
                ),
                rtol=5e-13,
                atol=3e-25 if key.endswith("_C") else 3e-12,
                err_msg=key,
            )
        for key in (
            "membrane_flux_fmol_s",
            "junction_flux_fmol_s",
            "face_flux_fmol_s",
            "reservoir_supply_fmol_s",
        ):
            mask = {
                "membrane_flux_fmol_s": p.membrane_active,
                "junction_flux_fmol_s": p.junction_active,
                "face_flux_fmol_s": p.face_active,
                "reservoir_supply_fmol_s": p.outside_active,
            }[key]
            np.testing.assert_allclose(
                getattr(fields.rates, key)[:, mask],
                expected_fields[key],
                rtol=3e-10,
                atol=3e-12,
                err_msg=key,
            )
        for key in ("electrode_current_A", "electrode_charge_C"):
            np.testing.assert_allclose(
                getattr(fields, key)[p.outside_active],
                expected_fields[key],
                rtol=3e-10,
                atol=3e-23,
                err_msg=key,
            )
        for key in (
            "chemical_energy_rate_pJ_s",
            "capacitor_energy_rate_pJ_s",
            "dissipation_pJ_s",
            "reservoir_power_pJ_s",
            "electrode_power_pJ_s",
        ):
            np.testing.assert_allclose(
                getattr(fields, key), expected_fields[key], rtol=3e-10, atol=3e-12, err_msg=key
            )
        assert abs(fields.energy_balance_pJ_s) <= 1e-10
        assert abs(expected_fields["energy_balance_pJ_s"]) <= 1e-10


@pytest.mark.parametrize("family", fixtures.FAMILIES)
@pytest.mark.parametrize("case", ("overlap", "single", "negative", "permuted"))
def test_original_material_charge_energy_and_variable_work_with_initial_dose(family, case):
    _, model, _, raw, spec, state, p, evolved, c = prefix(family, case)
    records = []
    for current in (state, evolved):
        model.check_values(current, spec)
        for time in (float(current.phase_clock_s[0]), 2.5e-6, fixtures.END):
            probe = current._replace(phase_clock_s=np.asarray([time]))
            proof = reference.conservation(c, reference.flatten(c, probe._asdict()))
            records.append(dict(time_s=time, proof=proof))
            evidence(
                "accounting-" + family + "-" + case,
                dict(
                    definition=raw, initial_operation=model.initial_operation(spec), records=records
                ),
                {"prefix-" + key: np.asarray(value) for key, value in evolved._asdict().items()},
            )
            for key in ("local_fmol", "outside_fmol", "global_fmol"):
                np.testing.assert_allclose(proof[key], 0.0, rtol=0, atol=3e-14, err_msg=key)
            for key in ("capacitor_charge_C", "electrode_charge_C", "global_charge_C"):
                np.testing.assert_allclose(proof[key], 0.0, rtol=0, atol=3e-25, err_msg=key)
            for key in (
                "energy_residual_pJ",
                "chemical_work_residual_pJ",
                "electrode_work_residual_pJ",
            ):
                np.testing.assert_allclose(proof[key], 0.0, rtol=0, atol=1e-10, err_msg=key)


@pytest.mark.parametrize("family", fixtures.FAMILIES)
def test_accepted_observer_exposes_physical_totals_and_distinct_maintenance(family):
    schema, model, _, _, spec, state, p, evolved, _ = prefix(family)
    before = {k: np.array(v, copy=True) for k, v in evolved._asdict().items()}
    history = model.STATE_TYPE(*(np.stack((a, b)) for a, b in zip(state, evolved, strict=True)))
    observed = model.observe_history(np.asarray([0.0, 1e-9]), history, p, [0.0, 1e-9], spec)
    assert tuple(vars(observed)) == model.OBSERVATION_FIELDS
    for i, row in enumerate((state, evolved)):
        s = model.signal_values(row, p, xp=np)
        value = model.readouts(row, control(schema, spec, row.phase_clock_s[0]), p, xp=np)
        physical = model.physical_state(row, p, xp=np)
        np.testing.assert_array_equal(
            observed.extracellular_amount[i], model.physical_amounts(row, p)[1]
        )
        np.testing.assert_array_equal(observed.reservoir_supplied[i], row.reservoir_supplied)
        np.testing.assert_array_equal(
            observed.physical_reservoir_supplied[i], physical.reservoir_supplied
        )
        np.testing.assert_allclose(
            observed.reservoir_supply_fmol_s[i],
            value.field.rates.reservoir_supply_fmol_s,
            rtol=5e-15,
            atol=1e-15,
        )
        np.testing.assert_allclose(
            observed.reservoir_supply_fmol_s[i] - observed.maintenance_reservoir_supply_fmol_s[i],
            s.dose_rate_fmol_s,
            rtol=5e-15,
            atol=1e-15,
        )
        np.testing.assert_allclose(
            observed.electrode_current_A[i] - observed.maintenance_electrode_current_A[i],
            -s.charge_rate_A,
            rtol=5e-15,
            atol=1e-25,
        )
        for name in ("reservoir_work_pJ", "electrode_work_pJ", "electrode_charge_transferred_C"):
            np.testing.assert_array_equal(
                getattr(observed, "physical_" + name)[i], getattr(physical, name)
            )
    for key in evolved._fields:
        np.testing.assert_array_equal(getattr(evolved, key), before[key], err_msg=key)
    empty = model.observe_history(np.asarray([0.0, 1e-9]), history, p, [], spec)
    assert all(v.shape[0] == 0 for v in vars(empty).values())


@pytest.mark.parametrize("family", fixtures.FAMILIES)
@pytest.mark.parametrize(
    "ledger",
    (
        "reservoir_supplied",
        "reservoir_work_pJ",
        "electrode_charge_transferred_C",
        "electrode_work_pJ",
        "reservoir_chemical_work_pJ",
    ),
)
def test_finite_ledger_corruption_is_rejected_without_repair(family, ledger):
    _, model, _, _, spec, _, p, evolved, c = prefix(family)
    value = np.array(getattr(evolved, ledger), copy=True)
    value.flat[0] += 1e-10 if ledger.endswith("_C") else 1e-4
    changed = evolved._replace(**{ledger: value})
    assert model.domain_valid(changed, p, p.active, xp=np)
    proof = reference.conservation(c, reference.flatten(c, changed._asdict()))
    assert (
        np.max(np.abs(proof["global_fmol"])) > 1e-6
        or np.max(np.abs(proof["electrode_charge_C"])) > 1e-12
        or abs(proof["energy_residual_pJ"]) > 1e-6
        or np.max(np.abs(proof["chemical_work_residual_pJ"])) > 1e-6
    )
    with pytest.raises(NumericalError, match="accounting"):
        model.check_values(changed, spec)


@pytest.mark.parametrize("family", fixtures.FAMILIES)
def test_clock_padding_and_finite_reservoir_history_cannot_hide_programming(family):
    _, model, _, _, spec, state, p, _, _ = prefix(family)
    for clock in (
        np.asarray([float("nan")]),
        np.asarray([-1e-9]),
        np.asarray([2 * fixtures.END]),
        np.asarray([0.0, 0.0]),
    ):
        changed = state._replace(phase_clock_s=clock)
        assert not model.domain_valid(changed, p, p.active, xp=np)
        with pytest.raises((NumericalError, ValueError)):
            model.check_values(changed, spec)
    outside = np.array(state.extracellular_amount_increment, copy=True)
    outside[0, np.flatnonzero(p.reservoir)[0]] = 1e-3
    assert not model.domain_valid(
        state._replace(extracellular_amount_increment=outside), p, p.active, xp=np
    )
    chemical = np.array(state.reservoir_chemical_work_pJ, copy=True)
    chemical[~p.outside_active] = 1e-4
    assert not model.domain_valid(
        state._replace(reservoir_chemical_work_pJ=chemical), p, p.active, xp=np
    )
    model.check_checkpoint(spec, SimpleNamespace(state=state, time=0.0))
    with pytest.raises(ConfigError, match="checkpoint time"):
        model.check_checkpoint(spec, SimpleNamespace(state=state, time=1e-9))


def test_independent_reference_dependency_closure_has_no_production_imports():
    root = Path(os.environ.get("CELLS_COMPONENT_SOURCE_ROOT", Path(__file__).resolve().parents[2]))
    sources = reference.dependency_manifest(root)
    assert any("surface_kinetic_reference.py" in name for name in sources)
    assert any("surface_dynamics_reference.py" in name for name in sources)
    evidence("dependency-closure", dict(sources=sources, production_imports=False))
