"""Native complete ECM chronology and separate conservative exchange evidence."""

import json
import os
from copy import deepcopy
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest

from cells.processes import betse_ecm_transport as transport
from cells.processes import betse_normal_current as current
from validation.betse import betse_ecm_transport_checks as checks
from validation.betse import betse_ecm_transport_fixtures as fixtures
from validation.betse import betse_ecm_transport_native as native
from validation.betse import betse_ecm_transport_reference as reference


def run(data):
    binding = transport.bind(data["definition"])
    parent = transport.state(binding, data["initial"])
    rows = []
    for packet in data["steps"]:
        trial = transport.step(binding, parent, transport.drive(binding, packet))
        assert trial.parent_identity == parent.identity
        rows.append(trial)
        parent = trial.candidate
    return binding, rows


def write(name, record, categories, *, raw=False):
    if directory := os.environ.get("CELLS_COMPONENT_EVIDENCE"):
        root = Path(directory) / ("ecm-transport-raw" if raw else "ecm-transport")
        root.mkdir(parents=True, exist_ok=True)
        with (root / (name + ".npz")).open("xb") as stream:
            np.savez_compressed(
                stream,
                **{
                    category + "__" + key.replace(".", "__"): value
                    for category, values in categories.items()
                    for key, value in values.items()
                },
            )
            stream.flush()
            os.fsync(stream.fileno())
        with (root / (name + ".json")).open("x") as stream:
            json.dump(transport.plain(record), stream, indent=2, allow_nan=False)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())


def all_columns(rows, *, ledgers):
    result = {}
    for index, row in enumerate(rows):
        result.update(
            {
                "step_" + str(index) + "." + key: value
                for key, value in checks.columns(row, ledgers=ledgers).items()
            }
        )
    return result


@pytest.mark.parametrize("case", (*fixtures.CASES, fixtures.LOW_INVENTORY_CASE))
def test_complete_native_and_independent_ecm_history(case):
    data = fixtures.fixture(case)
    before = deepcopy(data)
    binding, observed = run(data)
    proof = native.evaluate(data)
    write(
        case,
        dict(
            mode="precomparison_raw_evidence",
            inputs=data,
            actual_metadata=[checks.metadata(row) for row in observed],
            native_metadata=[checks.metadata(row) for row in proof["history"]],
            native_failure=proof["failure"],
        ),
        dict(
            actual=all_columns(observed, ledgers=True),
            native=all_columns(proof["history"], ledgers=False),
        ),
        raw=True,
    )
    first, second = reference.evaluate(data), reference.evaluate(data, refinement=2)
    write(
        case + "-references",
        dict(
            mode="precomparison_reference_evidence",
            inputs=data,
            reference=first,
            refined_reference=second,
        ),
        dict(
            reference=all_columns(first["history"], ledgers=True),
            refined=all_columns(second["history"], ledgers=True),
        ),
        raw=True,
    )
    assert data == before
    assert proof["failure"] is None and not proof["warnings"] and proof["RNG_unchanged"]
    actual_geometry = binding.geometry_binding.geometry._asdict()
    checks.geometry_compare(
        dict(geometry={key: actual_geometry[key] for key in proof["geometry"]}),
        dict(geometry=proof["geometry"]),
        exact=True,
    )
    maximum = checks.geometry_compare(
        dict(geometry={key: actual_geometry[key] for key in proof["geometry"]}),
        dict(geometry={key: first["geometry"][key] for key in proof["geometry"]}),
    )
    resolution = 0.0
    for i, trial in enumerate(observed):
        source, independent, refined = (
            proof["history"][i],
            first["history"][i],
            second["history"][i],
        )
        assert checks.metadata(trial) == checks.metadata(source) == checks.metadata(independent)
        checks.compare(
            checks.columns(trial, ledgers=False), checks.columns(source, ledgers=False), exact=True
        )
        maximum = max(maximum, checks.compare(checks.columns(trial), checks.columns(independent)))
        resolution = max(
            resolution, checks.compare(checks.columns(independent), checks.columns(refined))
        )
        assert (
            trial.diagnostics["finite"]
            and not trial.diagnostics["physical_material_or_energy_parity"]
        )
        for oracle in independent["conservative_exchange"]:
            assert abs(oracle["balance_residual_mol"]) <= 1e-85
            at = binding.geometry_binding.current_binding.ion_ids.index(oracle["ion_id"])
            frame = next(
                frame
                for frame in trial.frames
                if frame.stage == "membrane_commit" and frame.ion_id == oracle["ion_id"]
            )
            checks.compare(
                {"oracle.cell_mol_m3": frame.values.cell_mol_m3[at]},
                {"oracle.cell_mol_m3": oracle["cell_mol_m3"]},
            )
            if not binding.kernel.fast_update_ecm:
                checks.compare(
                    {"oracle.environment_mol_m3": frame.values.environment_mol_m3[at]},
                    {"oracle.environment_mol_m3": oracle["environment_mol_m3"]},
                )
    assert resolution <= 0.1
    write(
        case,
        dict(
            mode="complete_source_history",
            inputs=data,
            original_binding_identity=binding.identity,
            parent_identities=[row.parent_identity for row in observed],
            candidate_identities=[row.candidate.identity for row in observed],
            native_source_sha256=proof["native_source_sha256"],
            native_source_sites=proof["source_sites"],
            geometry_source_sites=proof["geometry_source_sites"],
            frame_metadata=[checks.metadata(row) for row in observed],
            fields=list(all_columns(observed, ledgers=True)),
            native_fields=list(all_columns(observed, ledgers=False)),
            reference=first,
            refined_reference=second,
            full_refined_buffers_retained=True,
            maximum_error_fraction=maximum,
            maximum_reference_resolution_fraction=resolution,
            source_calls=len(observed),
            complete_snapshots=sum(len(row.frames) for row in observed),
            environment_record_count=sum(len(row.environment_records) for row in observed),
            carried_error_allowance=False,
            physical_material_or_energy_parity=False,
        ),
        dict(
            actual=all_columns(observed, ledgers=True),
            native=all_columns(proof["history"], ledgers=False),
            reference=all_columns(first["history"], ledgers=True),
            refined=all_columns(second["history"], ledgers=True),
        ),
    )


@pytest.mark.parametrize("case", ("slow", "fast_duplicate"))
def test_conservative_exchange_oracle_distinguishes_fast_duplicate_defect(case):
    binding, rows = run(fixtures.fixture(case))
    defect = rows[0].diagnostics["fast_exchange_defect_mol"]
    if binding.kernel.fast_update_ecm:
        assert np.max(abs(defect)) > 1e-9
    else:
        assert np.max(abs(defect)) < 3e-14


def test_fast_exchange_is_conditionally_balanced_for_equal_duplicate_fluxes():
    _, rows = run(fixtures.fixture("fast_equal_flux"))
    assert np.max(abs(rows[0].diagnostics["fast_exchange_defect_mol"])) < 3e-14


def test_membrane_flux_samples_environment_before_boundary_clamp():
    binding, rows = run(fixtures.fixture())
    row = rows[0]
    initial = row.frames[0].values
    clamped = next(f.values for f in row.frames if f.stage == "ecm_clamp")
    mapping = binding.geometry_binding.geometry.membrane_to_grid
    assert np.any(initial.environment_mol_m3[0, mapping] != clamped.environment_mol_m3[0, mapping])
    assert [frame.stage for frame in row.frames[:8]] == [
        "initial",
        "reset_flux",
        "supplied_pump_flux",
        "membrane_flux",
        "junction_flux",
        "ecm_clamp",
        "ecm_commit",
        "refresh_at_mem",
    ]
    assert next(i for i, f in enumerate(row.frames) if f.stage == "supplied_late_flux") > max(
        i for i, f in enumerate(row.frames) if f.stage == "refresh_at_mem"
    )


def test_stationary_pump_role_has_stored_uncommitted_flux():
    binding, rows = run(fixtures.fixture("stationary_pump_role"))
    row = rows[0]
    assert "Na" not in binding.definition["ions"]["moving_ids"]
    assert np.any(row.candidate.values.membrane_flux_mol_m2_s[0] != 0)
    np.testing.assert_array_equal(
        row.candidate.values.cell_mol_m3[0], row.frames[0].values.cell_mol_m3[0]
    )
    np.testing.assert_array_equal(
        row.candidate.values.environment_mol_m3[0], row.frames[0].values.environment_mol_m3[0]
    )
    assert row.diagnostics["native_environment_exchange_mol"][0] == 0


def test_clipping_and_signed_environment_remain_source_outputs():
    _, clipped = run(fixtures.fixture("bulk_clipping"))
    assert np.any(clipped[0].diagnostics["clipping_added_mol"] > 0)
    assert clipped[0].diagnostics["negative_membrane_retained"]
    _, signed = run(fixtures.fixture("signed_environment"))
    assert signed[0].diagnostics["negative_environment_retained"]


def test_membrane_buffer_precedes_gap_bulk_and_clipping():
    _, rows = run(fixtures.fixture("membrane_lag"))
    assert np.max(abs(rows[0].diagnostics["membrane_bulk_difference_mol_m3"])) > 1e-9


def test_flow_flag_ignores_supplied_velocity_when_disabled():
    data = fixtures.fixture()
    _, first = run(data)
    for packet in data["steps"]:
        packet["velocity_x_m_s"] = [[1e4] * 3 for _ in range(3)]
        packet["velocity_y_m_s"] = [[-1e4] * 3 for _ in range(3)]
    _, second = run(data)
    for a, b in zip(first, second, strict=True):
        checks.compare(checks.columns(a), checks.columns(b), exact=True)


def test_nonce_and_configured_runtime_temperature_stores_are_explicit():
    _, rows = run(fixtures.fixture("neutral_nonce"))
    assert np.any(rows[0].diagnostics["source_voltage_nonce_delta_V"] != 0)
    for frame in rows[0].frames:
        if frame.stage == "junction_flux":
            np.testing.assert_array_equal(frame.values.junction_field_source, np.zeros(9))
            np.testing.assert_array_equal(frame.values.junction_voltage_V, np.full(9, 1e-25))
    data = fixtures.fixture("temperature_split")
    _, first = run(data)
    data["definition"]["environment_geometry_definition"]["parameters"][
        "configured_temperature_K"
    ] = 290.0
    _, second = run(data)
    a = next(f for f in first[0].frames if f.stage == "junction_flux")
    b = next(f for f in second[0].frames if f.stage == "junction_flux")
    np.testing.assert_array_equal(a.values.membrane_flux_mol_m2_s, b.values.membrane_flux_mol_m2_s)
    assert np.any(a.values.junction_flux_mol_m2_s != b.values.junction_flux_mol_m2_s)


@pytest.mark.parametrize("failure", ("electroflux_overflow", "environment_overflow"))
def test_raw_failed_source_arrays_are_retained_without_parent_commit(failure):
    data = fixtures.fixture()
    data["steps"] = data["steps"][:1]
    if failure == "electroflux_overflow":
        data["initial"]["voltage_V"] = [-1e6] * 9
    else:
        data["steps"][0]["electric_x_source"] = [[-1e308, 0.0, 1e308] for _ in range(3)]
        data["steps"][0]["boundary_mol_m3"] = [1000.0] * 4
    binding = transport.bind(data["definition"])
    parent = transport.state(binding, data["initial"])
    before = current.record(transport.state_record(parent))
    with pytest.raises(transport.ECMTransportRejected) as caught:
        transport.step(binding, parent, transport.drive(binding, data["steps"][0]))
    trial = caught.value.trial
    assert trial is not None and not trial.diagnostics["finite"]
    assert current.record(transport.state_record(parent)) == before
    proof = native.evaluate(data)
    write(
        failure,
        dict(
            mode="precomparison_raw_refusal",
            inputs=data,
            actual_metadata=checks.metadata(trial),
            native_metadata=checks.metadata(proof["history"][0]),
            native_failure=proof["failure"],
        ),
        dict(
            trial=checks.columns(trial, ledgers=False),
            native=checks.columns(proof["history"][0], ledgers=False),
        ),
        raw=True,
    )
    assert proof["warnings"]
    assert checks.metadata(trial) == checks.metadata(proof["history"][0])
    checks.compare(
        checks.columns(trial, ledgers=False),
        checks.columns(proof["history"][0], ledgers=False),
        exact=True,
    )
    if failure == "electroflux_overflow":
        assert proof["failure"] and trial.frames[-1].stage == "clip_bulk_failure"
    else:
        assert proof["failure"] is None
    write(
        failure,
        dict(
            mode="raw_nonfinite_source_refusal",
            inputs=data,
            failure_kind=failure,
            native_source_sha256=proof["native_source_sha256"],
            native_failure=proof["failure"],
            frame_metadata=checks.metadata(trial),
            fields=list(checks.columns(trial, ledgers=False)),
            no_partial_commit=True,
            binary64_overflow_reference_parity=False,
        ),
        dict(
            trial=checks.columns(trial, ledgers=False),
            native=checks.columns(proof["history"][0], ledgers=False),
        ),
    )


@pytest.mark.parametrize("target", ("operator", "state", "drive"))
def test_resealed_or_mutable_source_associations_are_rejected(target):
    data = fixtures.fixture()
    binding = transport.bind(data["definition"])
    parent = transport.state(binding, data["initial"])
    packet = transport.drive(binding, data["steps"][0])
    if target == "operator":
        wrong = binding.kernel.environment_diffusion_m2_s.copy()
        wrong[0, 0] *= 2
        binding = replace(
            binding,
            kernel=binding.kernel._replace(environment_diffusion_m2_s=transport.freeze(wrong)),
        )
        binding = replace(binding, identity=current._digest(transport.binding_record(binding)))
    elif target == "state":
        parent = replace(
            parent, values=parent.values._replace(cell_mol_m3=parent.values.cell_mol_m3.copy())
        )
    else:
        packet = packet._replace(junction_block=packet.junction_block.copy())
    with pytest.raises(transport.ECMTransportRejected):
        transport.step(binding, parent, packet)


def test_exact_binary_state_reconstruction_and_three_call_cap():
    data = fixtures.fixture()
    binding, rows = run(data)
    reloaded = transport.state(
        binding,
        {
            key: np.frombuffer(value.tobytes(), dtype=value.dtype).reshape(value.shape)
            for key, value in rows[0].candidate.values._asdict().items()
        },
        step_index=1,
    )
    assert reloaded.identity == rows[0].candidate.identity
    resumed = transport.step(binding, reloaded, transport.drive(binding, data["steps"][1]))
    checks.compare(checks.columns(resumed), checks.columns(rows[1]), exact=True)
    with pytest.raises(transport.ECMTransportRejected, match="three-call cap"):
        transport.step(binding, rows[-1].candidate, transport.drive(binding, data["steps"][0]))


def test_all_state_and_derived_buffers_are_immutable():
    binding, rows = run(fixtures.fixture())
    buffers = [
        *rows[0].candidate.values,
        binding.kernel.environment_diffusion_m2_s,
        binding.geometry_binding.geometry.membrane_divergence_map_m2,
    ]
    for value in buffers:
        with pytest.raises(ValueError):
            value.setflags(write=True)


@pytest.mark.parametrize(
    "defect",
    ("noECM", "moving_duplicate", "sensitive_gate", "bad_map", "unmasked_pump", "nonfinite_field"),
)
def test_incomplete_or_unsupported_sources_refuse(defect):
    data = fixtures.fixture()
    if defect == "noECM":
        data["definition"]["environment_geometry_definition"]["is_ecm"] = False
    elif defect == "moving_duplicate":
        data["definition"]["ions"]["moving_ids"] = ["Na", "Na"]
    elif defect == "sensitive_gate":
        data["definition"]["parameters"]["v_sensitive_gj"] = True
    elif defect == "bad_map":
        data["definition"]["junction_geometry"]["partner"][0] = 99
    elif defect == "unmasked_pump":
        data["steps"][0]["supplied_pump_membrane_flux_mol_m2_s"][0][1] = 1
    else:
        data["steps"][0]["electric_x_source"][0][0] = float("nan")
    with pytest.raises((ValueError, transport.ECMTransportRejected)):
        run(data)


def test_protocol_has_fixed_budgets_and_explicit_external_seams():
    protocol = json.loads(Path(native.PROTOCOL).read_text())
    assert protocol["law_id"] == transport.LAW_ID
    assert protocol["tolerances"]["carried_or_propagated_allowance"] is False
    assert protocol["tolerances"]["max_source_calls"] == transport.MAX_STEPS
    assert len(protocol["native_source"]["source_sha256"]) == 7
    assert not protocol["automatic_followup"] and not protocol["automatic_polling"]
