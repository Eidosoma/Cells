"""Complete irreversible owner removal, independent rates and public restart."""

import json
import math
from copy import deepcopy
from functools import lru_cache

import numpy as np
import pytest

from cells.core import calcium_energy_irreversible_transport_tissue_excision as cut_model
from cells.core import surface_calcium_energy_irreversible_transport_excision_spec as schema
from cells.core.batch import BatchSpec, WorldSpec, parse_batch
from cells.core.errors import NumericalError
from cells.core.excision import excise
from cells.core.grid import EventGrid
from cells.core.runner import timeline
from cells.core.schedule import control_values, event_index
from cells.core.specs import ConfigError, parse_spec
from cells.core.state import Checkpoint
from cells.core.windows import WindowPolicy, iter_windows
from cells.ensemble.ionic import parse_spec as parse_worlds
from cells.excision_io import (
    CALCIUM_ENERGY_IRREVERSIBLE_TRANSPORT_KIND,
    load_excision,
    write_excision,
)
from cells.io import load_snapshot, write_snapshot
from cells.models import surface_calcium_energy_irreversible_transport as parent
from cells.models import surface_calcium_energy_irreversible_transport_excision as model
from cells.models.registry import get_model
from cells.numerics.fixed_step import rk4_step
from tests.unit.test_surface_catalog import evidence
from tests.unit.test_surface_kinetic import exact
from validation.tissue import calcium_energy_irreversible_transport_excision_fixtures as fixtures
from validation.tissue import calcium_energy_irreversible_transport_excision_reference as reference


def controls(spec, time):
    table = control_values(spec, [time])
    return type(table)(*(value[0] for value in table))


@lru_cache(maxsize=16)
def prepared(arm="removed_neutral_history", *, evolved=False, padded=True):
    spec = parse_spec(fixtures.definition(arm, padded=padded))
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
    before = reference.bind(spec.to_dict())
    expected = reference.excise(
        spec.to_dict(),
        reference.flatten(before, point.state._asdict()),
        cut.report["removed_cell_ids"],
        point.time,
    )
    if cut.spec is None:
        assert expected["raw"] is None
        return {"terminal": True}
    c = reference.bind(cut.spec.to_dict())
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
        "irreversible-cut-stage-"
        + spec.fingerprint[:16]
        + "-"
        + str(point.time)
        + "-"
        + "_".join(cut.report["removed_cell_ids"]),
        dict(
            source=spec.to_dict(),
            after=cut.spec.to_dict(),
            report=cut.report,
            full_state_fields=44,
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
    assert actual.valid and ratio <= 1.0 and len(c["shapes"]) == 44
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
def test_complete_removal_matches_independent_owners_and_all44_rates(arm, evolved):
    spec, point = prepared(arm, evolved=evolved)
    source = cut_model.capture_source(spec, point)
    cut = excise(spec, point, ["cell_1"])
    independent_comparison(spec, point, cut)
    assert get_model(cut.spec.model) is model
    assert cut.spec == parse_spec(cut.spec.to_dict())
    assert cut.checkpoint.time == point.time
    assert cut.spec.execution.dt == spec.execution.dt
    assert len(cut.checkpoint.state) == 44
    assert set(cut.report["archived_retained_state"]) == set(parent.STATE_AXES)
    assert set(cut.report["archived_removed_state"]) == set(parent.STATE_AXES)
    assert len(cut.report["local_ledger_fields"]) == 41
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
        bound = 8 * np.finfo(np.float64).eps * np.array(
            [math.fsum(abs(v) for v in row) for row in values]
        )
        assert np.all(np.abs(cut.report[key]) <= bound)
    if evolved and arm == "removed_neutral_history":
        removed = cut.report["archived_removed_state"]
        assert np.any(np.asarray(removed["network_cycles_fmol"]) > 0)
        assert np.any(np.asarray(removed["network_dissipated_energy_pJ"]) > 0)
        assert np.any(np.asarray(removed["network_chemical_work_pJ"]) != 0)
        np.testing.assert_allclose(
            np.asarray(removed["network_supplied_work_pJ"]),
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
    noop = excise(spec, point, [])
    assert noop.spec == spec and noop.checkpoint is point
    exact(noop.checkpoint.state, point.state)
    terminal = excise(spec, point, [v.id for v in spec.model.cells])
    assert terminal.spec is None and terminal.checkpoint is None
    independent_comparison(spec, point, terminal)
    first = excise(spec, point, ["cell_1"])
    second = excise(first.spec, first.checkpoint, ["cell_0"])
    independent_comparison(first.spec, first.checkpoint, second)
    raw = second.spec.to_dict()
    assert raw["model"]["excision"]["source"]["definition"] == first.spec.to_dict()
    assert raw["model"]["excision"]["source"]["definition"]["model"]["excision"]["source"] == source
    assert cut_model.capture_source(spec, point) == source


def test_charged_closed_exterior_cut_refuses_without_neutralizing_source():
    spec, point = prepared(evolved=True)
    source = cut_model.capture_source(spec, point)
    with pytest.raises((ConfigError, NumericalError)):
        excise(spec, point, ["cell_0"])
    assert cut_model.capture_source(spec, point) == source


@pytest.mark.parametrize(
    "fault",
    ["work", "physical-ledger", "missing-field", "route-owner", "old-family", "past-control"],
)
def test_corrupt_source_or_survivors_refuse_without_mutating_accepted_state(fault):
    spec, point = prepared(evolved=True)
    source = cut_model.capture_source(spec, point)
    cut = excise(spec, point, ["cell_1"])
    raw = deepcopy(cut.spec.to_dict())
    if fault == "work":
        raw["model"]["tissue"]["network_transport"]["routes"][0]["drive"][
            "supplied_energy_J_per_mol"
        ] += 1
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
        parse_spec(raw)
    assert cut_model.capture_source(spec, point) == source


@pytest.mark.parametrize("backend", ["cpu", "gpu"])
def test_public_serialization_ensemble_and_absolute_control_admission(backend):
    spec, point = prepared(evolved=True)
    cut = excise(spec, point, ["cell_1"])
    raw = cut.spec.to_dict()
    raw["execution"]["backend"] = backend
    raw["execution"]["jit"] = True
    parsed = parse_spec(raw)
    assert get_model(parsed.model) is model
    assert parse_spec(parsed.to_dict()) == parsed
    batch = BatchSpec((WorldSpec(11, parsed), WorldSpec(31, parsed)), 2, 2048, 2**32)
    assert parse_batch(batch.to_dict()) == batch
    assert (
        parse_worlds(
            dict(model="ionic_worlds@1", simulation=raw, worlds=2, window_steps=8)
        ).simulation
        == parsed
    )
    assert point.time == model.initial_time(parsed)
    # The accepted grid stays anchored at zero; the model's execution origin
    # selects the cut time on that original grid rather than renumbering it.
    assert point.time in timeline(parsed)
    assert EventGrid(parsed).exact_index(point.time) == point.step_index
    base = schema.base_spec(parsed)
    for time in (point.time, 13.3e-6, 61.1e-6):
        exact(controls(parsed, time), controls(base, time))
    evidence(
        "irreversible-cut-admission-" + backend,
        dict(definition=raw, host_admission_only=True, GPU_or_compiled_execution=False),
    )


def test_portable_cut_artifact_and_exact_actual_continuation_restart(tmp_path):
    spec, point = prepared(evolved=True)
    cut = excise(spec, point, ["cell_1"])
    path = write_excision(tmp_path / "cut", cut)
    assert (
        json.loads((path / "manifest.json").read_text())["kind"]
        == CALCIUM_ENERGY_IRREVERSIBLE_TRANSPORT_KIND
    )
    restored = load_excision(path)
    assert restored.spec == cut.spec and restored.report == cut.report
    exact(restored.checkpoint.state, cut.checkpoint.state)
    exact(restored.checkpoint.layout, cut.checkpoint.layout)
    iterator = iter_windows(cut.spec, WindowPolicy(1, "full"), cut.checkpoint)
    first, expected = next(iterator), next(iterator)
    iterator.close()
    saved = load_snapshot(write_snapshot(tmp_path / "resume", cut.spec, first.final))
    iterator = iter_windows(saved.spec, WindowPolicy(1, "full"), saved.checkpoint)
    actual = next(iterator)
    iterator.close()
    exact(actual.final.state, expected.final.state)
    exact(actual.final.layout, expected.final.layout)
    exact(actual.history, expected.history)
    times = np.r_[first.observations.times, expected.observations.times]
    for key in vars(expected.observations):
        combined = np.concatenate(
            (getattr(first.observations, key), getattr(expected.observations, key))
        )
        np.testing.assert_array_equal(
            getattr(actual.observations, key), combined[times >= first.final.time], strict=True
        )
    assert actual.final.time == point.time + 2 * spec.execution.dt
    assert np.any(actual.final.state.network_dissipated_energy_pJ > 0)
    assert np.any(actual.final.state.network_chemical_work_pJ != 0)
    assert all(r.timings["compile_or_cache_seconds"] == 0 for r in (first, expected, actual))
    evidence(
        "irreversible-cut-actual-restart",
        dict(
            source=spec.to_dict(),
            report=cut.report,
            after=cut.spec.to_dict(),
            initial_time_s=point.time,
            final_time_s=actual.final.time,
            exact_all44_state_layout_history_observers=True,
            full_transient_claim=False,
        ),
    )
    with pytest.raises(FileExistsError):
        write_excision(path, cut)
    tampered = json.loads((path / "transition.json").read_text())
    tampered["archived_removed_state"]["network_electrical_work_pJ"][0] += 1
    (path / "transition.json").write_text(json.dumps(tampered))
    with pytest.raises(ConfigError, match="checksum"):
        load_excision(path)
