"""Direct finite-ATP owner removal and independently reconstructed full rates."""

import hashlib
import json
import math
from copy import deepcopy
from functools import lru_cache

import numpy as np
import pytest

from cells.core import calcium_energy_atp_transport_tissue_excision as cut_model
from cells.core import surface_calcium_energy_atp_transport_excision_spec as schema
from cells.core.errors import NumericalError
from cells.core.grid import EventGrid
from cells.core.schedule import control_values, event_index
from cells.core.specs import ConfigError
from cells.core.state import Checkpoint
from cells.models import surface_calcium_energy_atp_transport as parent
from cells.models import surface_calcium_energy_atp_transport_excision as model
from cells.numerics.fixed_step import rk4_step
from tests.unit.test_surface_catalog import evidence
from tests.unit.test_surface_kinetic import exact
from validation.tissue import calcium_energy_atp_transport_excision_fixtures as fixtures
from validation.tissue import calcium_energy_atp_transport_excision_reference as reference


def controls(spec, time):
    table = control_values(spec, [time])
    return type(table)(*(value[0] for value in table))


@lru_cache(maxsize=16)
def prepared(arm="removed_neutral_history", *, evolved=False, padded=True):
    spec = cut_model._parse(fixtures.definition(arm, padded=padded))
    state, layout = parent.initial_values(spec)
    time = 0.0
    if evolved:
        # One physical step gives nonzero removed and retained histories. Its
        # complete rate/state is compared independently below; no settling claim.
        def rhs(value, control, p, active):
            result = parent.readouts(value, control, p, xp=np)
            assert result.valid
            assert abs(float(result.field.energy_balance_pJ_s)) <= 1e-10
            return result.derivative

        time = spec.execution.dt
        state = rk4_step(rhs, state, time, controls(spec, 0.0), layout, layout.active)
        parent.check_values(state, spec)
    point = Checkpoint(
        state, layout, time, EventGrid(spec).exact_index(time), event_index(spec, time)
    )
    return spec, point


def independent_comparison(spec, point, cut):
    before = reference.bind(cut_model._serialize(spec))
    expected = reference.excise(
        cut_model._serialize(spec),
        reference.flatten(before, point.state._asdict()),
        cut.report["removed_cell_ids"],
        point.time,
    )
    if cut.spec is None:
        assert expected["raw"] is None
        return {"terminal": True}
    c = reference.bind(cut_model._serialize(cut.spec))
    state = reference.flatten(c, cut.checkpoint.state._asdict())
    np.testing.assert_array_equal(state, expected["state"])
    actual = parent.readouts(
        cut.checkpoint.state, controls(cut.spec, point.time), cut.checkpoint.layout, xp=np
    )
    target, phi, proof = reference.evaluate(c, state, point.time)
    packed = reference.flatten(c, actual.derivative._asdict())
    atol = reference.flatten(
        c,
        {
            key: np.full(shape, 3e-23 if key.endswith("_C") else 3e-12)
            for key, shape in c["shapes"].items()
        },
    )
    bound = atol + 3e-10 * np.abs(target)
    ratio = float(np.max(np.abs(packed - target) / bound, initial=0))
    evidence(
        "atp-cut-stage-"
        + hashlib.sha256(
            json.dumps(cut_model._serialize(spec), sort_keys=True).encode()
        ).hexdigest()[:16]
        + "-"
        + str(point.time)
        + "-"
        + "_".join(cut.report["removed_cell_ids"]),
        dict(
            source=cut_model._serialize(spec),
            after=cut_model._serialize(cut.spec),
            report=cut.report,
            full_state_fields=46,
            max_error_over_budget=ratio,
            claim="independent removal and instantaneous complete RHS, no long trajectory",
        ),
        dict(
            state=state,
            actual_rate=packed,
            expected_rate=target,
            budget=bound,
            signed_error=packed - target,
            expected_potential_V=phi,
        ),
    )
    assert actual.valid and ratio <= 1.0 and len(c["shapes"]) == 46
    assert abs(float(proof["physical_energy_balance_pJ_s"])) <= 1e-10
    p = cut.checkpoint.layout
    actual_phi = np.r_[
        actual.field.potential_V[: len(p.active)][p.active],
        actual.field.potential_V[len(p.active) :][p.outside_active],
    ]
    np.testing.assert_allclose(actual_phi, phi, rtol=3e-10, atol=3e-12)
    for key in reference.network.EXTRA_FIELDS:
        for archive, expected_key in (
            ("archived_retained_state", "archived_retained_network_state"),
            ("archived_removed_state", "archived_removed_network_state"),
        ):
            np.testing.assert_array_equal(
                cut.report[archive][key], expected["audit"][expected_key][key]
            )
    np.testing.assert_allclose(
        cut.report["unresolved_cut_energy_pJ"],
        expected["audit"]["unresolved_cut_energy_pJ"],
        rtol=3e-9,
        atol=2e-10,
    )
    return dict(max_error_over_budget=ratio)


@pytest.mark.parametrize("arm", fixtures.ARMS)
@pytest.mark.parametrize("evolved", [False, True])
def test_complete_removal_matches_independent_owners_and_all46_rates(arm, evolved):
    spec, point = prepared(arm, evolved=evolved)
    source = cut_model.capture_source(spec, point)
    cut = cut_model.excise(spec, point, ["cell_1"])
    independent_comparison(spec, point, cut)
    assert type(cut.spec.model) is schema.SurfaceCalciumEnergyATPTransportExcisionModel
    assert model.STATE_TYPE is parent.STATE_TYPE and model.LAYOUT_TYPE is parent.LAYOUT_TYPE
    assert model.initial_time(cut.spec) == point.time
    assert cut.spec == cut_model._parse(cut_model._serialize(cut.spec))
    assert cut.checkpoint.time == point.time
    assert cut.spec.execution.dt == spec.execution.dt
    assert len(cut.checkpoint.state) == 46
    assert set(cut.report["archived_retained_state"]) == set(parent.STATE_AXES)
    assert set(cut.report["archived_removed_state"]) == set(parent.STATE_AXES)
    assert len(cut.report["local_ledger_fields"]) == 43
    for key in cut.report["local_ledger_fields"]:
        assert not np.any(getattr(cut.checkpoint.state, key))
    original_clocks = {v.time for v in spec.experiment.changes}
    assert original_clocks <= {v.time for v in cut.spec.experiment.changes}
    assert {v.id for v in cut.spec.model.network_transporters} == set(
        cut.report["retained_network_transporter_ids"]
    )
    before = cut_model.physical(spec, point)
    kept = [i for i, cell in enumerate(spec.model.cells) if cell.id != "cell_1"]
    removed = [i for i, cell in enumerate(spec.model.cells) if cell.id == "cell_1"]
    for prefix, key, axis in (("chemical", "chemical_amount", 0), ("fuel", "fuel_amount", 1)):
        for label, ids in (("retained", kept), ("removed", removed)):
            np.testing.assert_array_equal(
                cut.report[label + "_" + prefix + "_amount_fmol"],
                np.take(before[key], ids, axis=axis),
            )
    # Owner arrays are exact partitions. The report subtracts separately
    # reduced float64 totals; for this three-owner fixture, summation and two
    # subtractions allow eight epsilon times the absolute source inventory.
    # This checks representation roundoff without changing any physics budget.
    for key, values in (
        ("material_residual_fmol", before["chemical_species_amount"].T),
        ("moiety_residual_fmol", before["moiety_amount"].T),
        ("fuel_material_residual_fmol", before["fuel_amount"]),
        ("fuel_moiety_residual_fmol", before["fuel_moieties"]),
    ):
        bound = (
            8
            * np.finfo(np.float64).eps
            * np.array([math.fsum(abs(v) for v in row) for row in values])
        )
        assert np.all(np.abs(cut.report[key]) <= bound)
    if evolved and arm == "removed_neutral_history":
        removed = cut.report["archived_removed_state"]
        assert np.any(np.asarray(removed["network_cycles_fmol"]) > 0)
        assert np.any(np.asarray(removed["network_dissipated_energy_pJ"]) > 0)
        assert np.any(np.asarray(removed["network_gross_hydrolysis_fmol"]) > 0)
        assert np.any(np.asarray(removed["network_gross_synthesis_fmol"]) > 0)
        assert np.any(np.asarray(removed["network_chemical_work_pJ"]) != 0)
        np.testing.assert_allclose(
            np.asarray(removed["network_fuel_work_pJ"]),
            np.asarray(removed["network_dissipated_energy_pJ"])
            + np.asarray(removed["network_chemical_work_pJ"])
            + np.asarray(removed["network_electrical_work_pJ"]),
            atol=3e-12,
            rtol=0,
        )
    assert cut_model.capture_source(spec, point) == source


def test_noop_terminal_and_successive_removals_keep_explicit_lineage():
    spec, point = prepared("sequential", evolved=True)
    source = cut_model.capture_source(spec, point)
    noop = cut_model.excise(spec, point, [])
    assert noop.spec == spec and noop.checkpoint is point
    exact(noop.checkpoint.state, point.state)
    terminal = cut_model.excise(spec, point, [v.id for v in spec.model.cells])
    assert terminal.spec is None and terminal.checkpoint is None
    independent_comparison(spec, point, terminal)
    first = cut_model.excise(spec, point, ["cell_1"])
    second = cut_model.excise(first.spec, first.checkpoint, ["cell_0"])
    independent_comparison(first.spec, first.checkpoint, second)
    raw = cut_model._serialize(second.spec)
    assert raw["model"]["excision"]["source"]["definition"] == cut_model._serialize(first.spec)
    assert raw["model"]["excision"]["source"]["definition"]["model"]["excision"]["source"] == source
    assert cut_model.capture_source(spec, point) == source


def test_charged_closed_exterior_cut_refuses_without_neutralizing_source():
    spec, point = prepared(evolved=True)
    source = cut_model.capture_source(spec, point)
    with pytest.raises((ConfigError, NumericalError)):
        cut_model.excise(spec, point, ["cell_0"])
    assert cut_model.capture_source(spec, point) == source


@pytest.mark.parametrize(
    "fault",
    ["work", "physical-ledger", "missing-field", "route-owner", "old-family", "past-control"],
)
def test_corrupt_source_or_survivors_refuse_without_mutating_accepted_state(fault):
    spec, point = prepared(evolved=True)
    source = cut_model.capture_source(spec, point)
    cut = cut_model.excise(spec, point, ["cell_1"])
    raw = deepcopy(cut_model._serialize(cut.spec))
    if fault == "work":
        raw["model"]["tissue"]["network_transport"]["routes"][0]["drive"]["atp_per_cycle"] += 1
    elif fault == "physical-ledger":
        raw["model"]["excision"]["source"]["checkpoint"]["state"]["network_chemical_work_pJ"][
            0
        ] += 1
    elif fault == "missing-field":
        del raw["model"]["excision"]["source"]["checkpoint"]["state"]["network_electrical_work_pJ"]
    elif fault == "route-owner":
        raw["model"]["tissue"]["network_transport"]["routes"][0]["membrane_id"] = (
            "membrane_1_shared"
        )
    elif fault == "old-family":
        raw["model"]["excision"]["source"]["definition"]["model"]["id"] = (
            "resolved_calcium_energy_transport@1"
        )
    else:
        raw["experiment"]["network_transport_controls"][0]["schedule"][0]["availability"] = 0.123
    with pytest.raises((ConfigError, NumericalError)):
        cut_model._parse(raw)
    assert cut_model.capture_source(spec, point) == source


@pytest.mark.parametrize("field", ["network_gross_hydrolysis_fmol", "network_gross_synthesis_fmol"])
def test_both_gross_history_fields_are_required_in_full_source_archive(field):
    spec, point = prepared(evolved=True)
    cut = cut_model.excise(spec, point, ["cell_1"])
    raw = deepcopy(cut_model._serialize(cut.spec))
    del raw["model"]["excision"]["source"]["checkpoint"]["state"][field]
    with pytest.raises(ConfigError):
        cut_model._parse(raw)


def test_short_postcut46_field_history_preserves_internal_fuel_and_original_event_grid():
    recipe = fixtures.definition(padded=False)
    recipe["execution"]["dt"] = fixtures.DT / 8
    spec = cut_model._parse(recipe)
    state, layout = parent.initial_values(spec)
    start = fixtures.DT

    def prefix_rhs(value, control, params, active):
        result = parent.readouts(value, control, params, xp=np)
        assert result.valid and abs(float(result.field.energy_balance_pJ_s)) <= 1e-10
        return result.derivative

    for index in range(8):
        state = rk4_step(
            prefix_rhs,
            state,
            spec.execution.dt,
            controls(spec, index * spec.execution.dt),
            layout,
            layout.active,
        )
        parent.check_values(state, spec)
    point = Checkpoint(
        state, layout, start, EventGrid(spec).exact_index(start), event_index(spec, start)
    )
    cut = cut_model.excise(spec, point, ["cell_1"])
    raw = cut_model._serialize(cut.spec)
    c = reference.bind(raw)
    dt, start = spec.execution.dt, point.time
    end, event = start + 2 * fixtures.DT, 1.75 * fixtures.DT
    requested = [start, event, 2 * fixtures.DT, end]
    assert cut.spec.execution.dt == spec.execution.dt == fixtures.DT / 8
    standard = reference.integrate(
        raw,
        start_time=start,
        end_time=end,
        observation_times=requested,
        max_step_s=dt,
        first_step_s=dt / 2,
    )
    tight = reference.integrate(
        raw,
        start_time=start,
        end_time=end,
        observation_times=requested,
        refinement=2,
        max_step_s=dt,
        first_step_s=dt / 2,
    )
    target = tight["state"]
    atol = reference.flatten(
        c,
        {
            key: np.full(shape, 3e-23 if key.endswith("_C") else 3e-12)
            for key, shape in c["shapes"].items()
        },
    )
    budget = atol + 3e-10 * np.abs(target)
    uncertainty = float(np.max(np.abs(standard["state"] - target) / budget, initial=0))
    errors, arrays = {}, dict(oracle=target, standard=standard["state"], budget=budget)
    for divisor in (1, 2):
        step = dt / divisor
        times = sorted(
            {
                start,
                end,
                event,
                *(i * step for i in range(int(np.ceil(end / step)) + 1) if start < i * step < end),
            }
        )
        state, states = cut.checkpoint.state, [cut.checkpoint.state]

        def rhs(value, control, layout, active):
            result = parent.readouts(value, control, layout, xp=np)
            assert result.valid and abs(float(result.field.energy_balance_pJ_s)) <= 1e-10
            return result.derivative

        for left, right in zip(times[:-1], times[1:], strict=True):
            state = rk4_step(
                rhs,
                state,
                right - left,
                controls(cut.spec, left),
                cut.checkpoint.layout,
                cut.checkpoint.layout.active,
            )
            model.check_values(state, cut.spec)
            states.append(state)
        packed = np.stack([reference.flatten(c, value._asdict()) for value in states])
        error = packed[[times.index(time) for time in requested]] - target
        errors[str(divisor)] = float(np.max(np.abs(error) / budget, initial=0))
        arrays.update(
            {
                "dt" + str(divisor) + "_state": packed,
                "dt" + str(divisor) + "_times": np.asarray(times),
                "dt" + str(divisor) + "_error": error,
            }
        )
        endpoint = reference.network.endpoint_balance(
            c, reference.flatten(c, state._asdict()), time=end
        )
        assert abs(endpoint["balance_pJ"]) <= 1e-10
        assert np.any(state.network_gross_hydrolysis_fmol > 0)
        assert np.any(state.network_gross_synthesis_fmol > 0)
    evidence(
        "atp-cut-short-history",
        dict(
            definition=raw,
            accuracy=errors,
            oracle_uncertainty_fraction=uncertainty,
            fields=46,
            event_time_s=event,
            source_time_s=start,
            end_time_s=end,
            source_nominal_dt_s=dt,
            original_fixture_dt_s=fixtures.DT,
            scope="same2.5us postcut interval, finer source dt declared before cut; no order claim",
        ),
        arrays,
    )
    assert uncertainty <= 0.1 and all(value <= 1 for value in errors.values())
    assert errors["2"] <= errors["1"] or max(errors.values()) <= 0.01
    assert event in standard["event_times"]
    assert cut.report["network_work_external"] is False
    assert cut.report["network_fuel_work_internal"] is True
    assert len(cut.report["network_route_ledger_fields"]) == 8
