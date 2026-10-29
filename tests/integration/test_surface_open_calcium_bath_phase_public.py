"""Full calcium/fuel bath INIT carry, explicit SIM work, replay and restart."""

import hashlib
import json
import sys
from copy import deepcopy
from dataclasses import replace

import numpy as np
import pytest

from cells.core import open_calcium_bath_phase_handoff as bridge
from cells.core.batch import BatchSpec, WorldSpec, parse_batch
from cells.core.errors import NumericalError
from cells.core.runner import branch_checkpoint, validate_checkpoint
from cells.core.schedule import control_values
from cells.core.specs import ConfigError, parse_spec
from cells.core.state import initialise
from cells.core.windows import WindowPolicy, iter_windows
from cells.ensemble.ionic import parse_spec as parse_worlds
from cells.io import load_snapshot, write_snapshot
from cells.models.registry import get_model
from cells.tissue_phase import _source_adapter, main, prepare_request, read_preparation
from tests.integration.test_surface_bath_events_public import arrays_and_observations, invoke
from tests.surface_open_calcium_bath_phase_fixtures import (
    OWNERS,
    PREFIX_DT,
    prepared,
    request,
    source_checkpoint,
)
from tests.unit.test_surface_catalog import evidence
from tests.unit.test_surface_kinetic import exact


def export_snapshot(snapshot, output):
    saved = load_snapshot(snapshot)
    model = get_model(saved.spec.model)
    assert type(saved.checkpoint.state) is model.STATE_TYPE
    assert type(saved.checkpoint.layout) is model.LAYOUT_TYPE
    np.savez(output, **arrays_and_observations(model, saved.spec, saved.checkpoint))
    print(
        json.dumps(
            dict(
                definition=saved.spec.to_dict(),
                clocks=model.handoff_record(saved.spec)["clocks"],
                operation=model.initial_operation(saved.spec),
            )
        )
    )


@pytest.mark.parametrize("family", OWNERS)
def test_owned_bath_epoch_public_routes_exact_carry_and_separate_operation(tmp_path, family):
    schema, model, count = OWNERS[family]
    spec = parse_spec(prepared(family).definition)
    source, before = source_checkpoint(family)
    point = initialise(spec)
    assert get_model(spec.model) is model
    assert spec == parse_spec(spec.to_dict())
    assert _source_adapter(source) == (bridge, schema.POLICIES)
    assert type(point.state) is model.STATE_TYPE and len(point.state) == count
    assert type(point.layout) is model.LAYOUT_TYPE
    for key in point.state._fields:
        expected = np.zeros(1) if key == "phase_clock_s" else getattr(before.state, key)
        np.testing.assert_array_equal(getattr(point.state, key), expected, err_msg=key)
    assert np.any(point.state.reservoir_chemical_work_pJ != 0)
    exact(model.parent_layout(point.layout), model.parent_layout(before.layout))
    controls = control_values(spec, [0.0, PREFIX_DT])
    exact(controls, control_values(schema.scheduled_spec(spec), [0.0, PREFIX_DT]))
    assert np.any(controls.membrane != control_values(source, [0.0, PREFIX_DT]).membrane)
    assert len({channel.kinetic_law for channel in spec.model.channels}) == 56
    assert len(spec.experiment.channels) == len(spec.model.channels)
    assert len(spec.experiment.pumps) == len(spec.model.membranes)
    assert np.any(point.state.chemical_amount_increment != 0)
    if family == "energy":
        assert np.any(point.state.energy_amount_increment_fmol != 0)
    record = model.handoff_record(spec)
    operation = record["controller_operation"]
    assert operation == model.initial_operation(spec)

    # The sealed operation is computed on host arrays. Compare the same host
    # arithmetic here; initialise() puts the new checkpoint on JAX, whose
    # scalar arithmetic can otherwise enter an xp=np expression. All carried
    # checkpoint arrays above and the saved arrays below remain exact checks.
    def host(values):
        return type(values)(*(np.asarray(value) for value in values))

    old = model.physical_state(host(before.state), host(before.layout), xp=np)
    new = model.physical_state(host(point.state), host(point.layout), xp=np)
    assert np.any(np.asarray(operation["dose_fmol"]) != 0)
    for field, delta in (
        ("extracellular_amount_increment", "dose_fmol"),
        ("reservoir_supplied", "dose_fmol"),
        ("electrode_charge_transferred_C", "electrode_charge_C"),
        ("reservoir_work_pJ", "electrochemical_work_pJ"),
        ("electrode_work_pJ", "electrode_work_pJ"),
    ):
        np.testing.assert_array_equal(
            getattr(new, field), np.asarray(getattr(old, field)) + operation[delta], err_msg=field
        )
    saved = load_snapshot(write_snapshot(tmp_path / "epoch", spec, point))
    assert saved.spec == spec
    exact(saved.checkpoint.state, point.state)
    exact(saved.checkpoint.layout, point.layout)
    for target, incompatible in ((spec, before), (source, point)):
        with pytest.raises(ConfigError):
            validate_checkpoint(target, incompatible)
    with pytest.raises(ConfigError):
        branch_checkpoint(source, before, spec)
    with pytest.raises(ConfigError):
        _source_adapter(spec)
    mixed = BatchSpec(
        (WorldSpec(3, spec), WorldSpec(71, schema.scheduled_spec(spec))), 2, 512, 2**30
    )
    with pytest.raises(ConfigError, match="model family"):
        parse_batch(mixed.to_dict())
    evidence(
        "owned-bath-epoch-public-carry-" + family,
        dict(
            definition=spec.to_dict(),
            operation=operation,
            carried_fields=[key for key in point.state._fields if key != "phase_clock_s"],
            full_trajectory_credit=False,
        ),
        arrays_and_observations(model, spec, point),
    )


@pytest.mark.parametrize("backend", ("cpu", "gpu"))
@pytest.mark.parametrize("family", OWNERS)
def test_owned_bath_epoch_world_admission_preserves_owner_and_controls(family, backend):
    # Execution settings participate in the authenticated controller operation.
    # An edited generated definition must fail; a new request seals new settings.
    edited = deepcopy(prepared(family).definition)
    edited["execution"].update(backend=backend, jit=True)
    with pytest.raises(ConfigError, match="operation"):
        parse_spec(edited)
    recipe = request(family)
    recipe["simulation"]["execution"]["backend"] = backend
    raw = prepare_request(recipe).definition
    with pytest.raises(ValueError, match="JIT"):
        parse_worlds(dict(model="ionic_worlds@1", simulation=raw, worlds=2))
    recipe["simulation"]["execution"]["jit"] = True
    raw = prepare_request(recipe).definition
    spec = parse_spec(raw)
    # The embedded INIT history remains resident. Bound the window instead of
    # raising the trace budget; the declared physical duration is unchanged.
    worlds = parse_worlds(dict(model="ionic_worlds@1", simulation=raw, worlds=2, window_steps=8))
    assert worlds.simulation == spec and worlds.window_steps == 8
    assert get_model(spec.model) is OWNERS[family][1]
    batch = BatchSpec((WorldSpec(3, spec), WorldSpec(71, spec)), 2, 512, 2**30)
    assert parse_batch(batch.to_dict()) == batch


def snapshot_payload_hashes(directory):
    return {
        path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in directory.iterdir()
    }


def prepare_cli_case(tmp_path, family):
    """Persist complete expected values so fresh CLI phases can run separately."""
    schema, _, count = OWNERS[family]
    source, point = source_checkpoint(family)
    snapshot = write_snapshot(tmp_path / "INIT", source, point)
    simulation = tmp_path / "SIM.json"
    simulation.write_text(json.dumps(request(family)["simulation"]))
    expected = prepared(family)
    (tmp_path / "expected-preparation.json").write_text(
        json.dumps(
            dict(
                family=family,
                model_id=schema.MODEL_ID,
                carried_fields=count - 1,
                definition=expected.definition,
                provenance=expected.provenance,
                source_payload_sha256=snapshot_payload_hashes(snapshot),
            )
        )
    )


def assert_cli_preparation(tmp_path, result):
    expected = json.loads((tmp_path / "expected-preparation.json").read_text())
    assert result["model_id"] == expected["model_id"]
    assert len(result["carried_fields"]) == expected["carried_fields"]
    assert "reservoir_chemical_work_pJ" in result["carried_fields"]
    assert result["controller_operation"] == expected["provenance"]["controller_operation"]
    assert (
        result["carried_admission"]
        == expected["definition"]["model"]["handoff"]["carried_admission"]
    )
    actual = read_preparation(tmp_path / "prepared")
    assert actual.definition == expected["definition"]
    assert actual.provenance == expected["provenance"]
    assert snapshot_payload_hashes(tmp_path / "INIT") == expected["source_payload_sha256"]


def assert_cli_replay(tmp_path, result):
    expected = json.loads((tmp_path / "expected-preparation.json").read_text())
    replayed = read_preparation(tmp_path / "replayed")
    assert replayed.definition == expected["definition"]
    assert replayed.provenance == expected["provenance"]
    assert result["model_id"] == expected["model_id"]
    assert (
        result["carried_admission"]
        == expected["definition"]["model"]["handoff"]["carried_admission"]
    )
    evidence(
        "owned-bath-epoch-public-cli-" + expected["family"],
        dict(summary=result, portable_replay=True, full_trajectory_credit=False),
    )


@pytest.mark.parametrize("family", OWNERS)
def test_owned_bath_epoch_fresh_cli_prepare_and_portable_replay(tmp_path, family):
    prepare_cli_case(tmp_path, family)
    snapshot, simulation = tmp_path / "INIT", tmp_path / "SIM.json"
    output = tmp_path / "prepared"
    result = invoke(
        tmp_path,
        "prepare",
        [
            "-m",
            "cells",
            "tissue-phase",
            "from-snapshot",
            snapshot,
            simulation,
            "--output",
            output,
        ],
    )
    assert_cli_preparation(tmp_path, result)
    validated = invoke(tmp_path, "validate", ["-m", "cells", "tissue-phase", "validate", output])
    assert validated["carried_admission"] == result["carried_admission"]
    snapshot.rename(tmp_path / "archived-INIT")
    simulation.unlink()
    replayed = tmp_path / "replayed"
    result = invoke(
        tmp_path,
        "replay",
        [
            "-m",
            "cells",
            "tissue-phase",
            "replay",
            output / "provenance.json",
            "--output",
            replayed,
        ],
    )
    assert_cli_replay(tmp_path, result)


@pytest.mark.parametrize("family", OWNERS)
def test_owned_bath_epoch_fresh_snapshot_has_every_array_and_explicit_operation(tmp_path, family):
    _, model, _ = OWNERS[family]
    spec = parse_spec(prepared(family).definition)
    point = initialise(spec)
    snapshot = write_snapshot(tmp_path / "epoch", spec, point)
    restored = tmp_path / "restored.npz"
    result = invoke(
        tmp_path,
        "restore",
        [
            "-c",
            "from tests.integration.test_surface_open_calcium_bath_phase_public "
            "import export_snapshot; "
            "import sys; export_snapshot(*sys.argv[1:])",
            snapshot,
            restored,
        ],
    )
    assert result["definition"] == spec.to_dict()
    assert result["clocks"] == model.handoff_record(spec)["clocks"]
    assert result["operation"] == model.initial_operation(spec)
    expected = arrays_and_observations(model, spec, point)
    with np.load(restored, allow_pickle=False) as actual:
        assert set(actual.files) == set(expected)
        for key, value in expected.items():
            assert actual[key].dtype == value.dtype
            np.testing.assert_array_equal(actual[key], value, err_msg=key)
    evidence(
        "owned-bath-epoch-public-fresh-snapshot-" + family,
        dict(
            complete_state_layout_physical_observations_exact=True,
            initial_controller_operation=result["operation"],
            full_trajectory_credit=False,
        ),
        expected,
    )


@pytest.mark.parametrize("family", OWNERS)
def test_owned_bath_epoch_actual_windows_restart_preserves_init_and_sim_history(tmp_path, family):
    _, model, _ = OWNERS[family]
    spec = parse_spec(prepared(family).definition)
    assert spec.execution.jit is False
    iterator = iter_windows(spec, WindowPolicy(1, "full"))
    first, expected = next(iterator), next(iterator)
    iterator.close()
    assert first.final.time == PREFIX_DT and expected.final.time == 2 * PREFIX_DT
    saved = load_snapshot(write_snapshot(tmp_path / "SIM-middle", spec, first.final))
    wrong_clock = replace(
        saved.checkpoint, state=saved.checkpoint.state._replace(phase_clock_s=np.zeros(1))
    )
    with pytest.raises((ConfigError, NumericalError), match="clock"):
        validate_checkpoint(spec, wrong_clock)
    iterator = iter_windows(spec, WindowPolicy(1, "full"), saved.checkpoint)
    actual = next(iterator)
    iterator.close()
    exact(actual.final.state, expected.final.state)
    exact(actual.final.layout, expected.final.layout)
    exact(actual.history, expected.history)
    baseline_times = np.concatenate((first.observations.times, expected.observations.times))
    selected = baseline_times >= PREFIX_DT
    for name in vars(expected.observations):
        baseline = np.concatenate(
            (getattr(first.observations, name), getattr(expected.observations, name)), axis=0
        )
        np.testing.assert_array_equal(
            getattr(actual.observations, name), baseline[selected], err_msg=name
        )
    init_time = source_checkpoint(family)[1].time
    np.testing.assert_array_equal(actual.observations.init_phase_clock_s, init_time)
    np.testing.assert_allclose(
        actual.observations.elapsed_time_s[:, 0],
        init_time + actual.observations.times,
        rtol=0,
        atol=1e-22,
    )
    for result in (first, expected, actual):
        assert result.timings["compile_or_cache_seconds"] == 0
    evidence(
        "owned-bath-epoch-public-window-restart-" + family,
        dict(
            definition=spec.to_dict(),
            init_time_s=init_time,
            duration_s=2 * PREFIX_DT,
            complete_restart_exact=True,
            full_trajectory_credit=False,
            compiled_or_GPU_execution=False,
        ),
        arrays_and_observations(model, spec, actual.final),
    )


@pytest.mark.parametrize("family", OWNERS)
def test_owned_bath_epoch_cli_refuses_changed_operation_and_overwrite(tmp_path, capsys, family):
    path = tmp_path / "request.json"
    path.write_text(json.dumps(request(family)))
    output = tmp_path / "prepared"
    assert main(["prepare", str(path), "--output", str(output)]) == 0
    capsys.readouterr()
    before = {p.name: p.read_bytes() for p in output.iterdir()}
    assert main(["prepare", str(path), "--output", str(output)]) == 2
    assert capsys.readouterr().err
    assert {p.name: p.read_bytes() for p in output.iterdir()} == before
    provenance = json.loads((output / "provenance.json").read_text())
    provenance["controller_operation"]["dose_fmol"][0][0] += 0.1
    (output / "provenance.json").write_text(json.dumps(provenance))
    assert main(["validate", str(output)]) == 2
    assert capsys.readouterr().err


if __name__ == "__main__":
    export_snapshot(*sys.argv[1:])
