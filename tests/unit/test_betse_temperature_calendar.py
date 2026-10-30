"""Native clock/setter/cache correspondence and exact causal restart evidence."""

import hashlib
import json
import math
import os
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
from types import MappingProxyType

import numpy as np
import pytest

from cells import betse_temperature_calendar_io as archive
from cells.core import physiology_native_calendar as clocks
from cells.processes import betse_global_controls as setters
from cells.processes import betse_temperature_calendar as replay
from validation.betse import betse_temperature_calendar_fixtures as fixtures
from validation.betse import betse_temperature_calendar_native as native
from validation.betse import betse_temperature_calendar_reference as reference

PROFILES = ("literal_native", "matched_SI")


def build(case="fresh", phase="SIM", profile="literal_native", *, count=7, mutate=None):
    data = fixtures.fixture(case, phase, profile, count)
    if mutate is not None:
        mutate(data)
    return bind_data(data)


def bind_data(data):
    calendar = clocks.bind(**data["calendar"])
    events = tuple(
        setters.Event(**(row | dict(target_ids=tuple(row["target_ids"])))) for row in data["events"]
    )
    program = setters.bind(
        membrane_ids=data["raw"]["material"]["geometry"]["membrane_ids"],
        events=events,
        provenance="Explicit original temperature-only source program for calendar replay",
    )
    return replay.bind(data["raw"], calendar, program)


def inputs(binding):
    return dict(
        raw=binding.definition,
        calendar=clocks.record(binding.calendar),
        program=setters.record(binding.program),
    )


def flat(value, prefix=""):
    if hasattr(value, "_asdict"):
        value = value._asdict()
    if isinstance(value, (dict, MappingProxyType)):
        answer = {}
        for key, item in value.items():
            answer.update(flat(item, prefix + ("." if prefix else "") + key))
        return answer
    if value is None:
        return {}
    return {prefix: np.asarray(value, dtype=np.float64)}


def budget(name, expected):
    absolute = (
        3e-12
        if name.endswith("temperature_K")
        else 3e-14
        if name.endswith(("_V", ".hh_m", ".hh_h", ".ml_m")) or "ion_reversal_V." in name
        else 3e-13
    )
    return absolute + 6e-12 * abs(expected)


def compare(actual, expected):
    first, last = flat(actual), flat(expected)
    assert first.keys() == last.keys()
    maximum = 0.0
    for name, wanted in last.items():
        observed = first[name]
        assert observed.shape == wanted.shape, name
        error = float(np.max(abs(observed - wanted) / budget(name, wanted), initial=0))
        assert error <= 1, (name, error)
        maximum = max(maximum, error)
    return maximum


def evidence(name, record, columns=None):
    if directory := os.environ.get("CELLS_COMPONENT_EVIDENCE"):
        root = Path(directory) / "temperature-calendar"
        root.mkdir(parents=True, exist_ok=True)
        with (root / (name + ".json")).open("x") as stream:
            json.dump(replay.plain(record), stream, indent=2, allow_nan=False)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        if columns is not None:
            np.savez_compressed(root / (name + ".npz"), **columns)


def raw_input(value):
    if isinstance(value, dict):
        return {key: raw_input(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [raw_input(item) for item in value]
    if isinstance(value, float) and not math.isfinite(value):
        return replay.buffer_record(value)
    return value


def row_values(trial):
    return dict(values=trial.values, probes=trial.probes, gate_arithmetic=trial.gate_arithmetic)


def run(binding):
    point = replay.initialise(binding)
    receipts = []
    for _ in range(binding.calendar.step_count):
        receipt = replay.advance(binding, point)
        receipts.append(receipt)
        point = receipt.checkpoint
    return point, receipts


def qualify(binding, name):
    original = replay.binding_record(binding)
    state = replay.initialise(binding)
    parent_records, receipts = [], []
    for _ in range(binding.calendar.step_count):
        parent = replay.checkpoint_record(state)
        receipt = replay.advance(binding, state)
        assert replay.checkpoint_record(state) == parent
        assert replay.binding_record(binding) == original
        assert receipt.trial.parent_identity == state.identity
        assert receipt.checkpoint.cache_identity == binding.cache.identity
        assert all(receipt.trial.diagnostics.values())
        parent_records.append(parent)
        receipts.append(receipt)
        state = receipt.checkpoint
    replay.validate(binding, state)
    with pytest.raises(replay.TemperatureCalendarRejected, match="exhausted"):
        replay.advance(binding, state)
    declared = inputs(binding)
    source = {solver: native.evaluate(declared, solver=solver) for solver in ("normal", "fast")}
    independent = reference.evaluate(declared, precision=125)
    resolved = reference.evaluate(declared, precision=170)
    actual_cache = {
        key: getattr(binding.cache.coefficients, key) for key in source["normal"]["cache"]
    }
    columns = {
        "cache__" + key.replace(".", "__"): value for key, value in flat(actual_cache).items()
    }
    errors = [compare(actual_cache, independent["cache"])]
    resolution = [compare(independent["cache"], resolved["cache"])]
    rows = []
    for solver, capture in source.items():
        errors.append(compare(actual_cache, capture["cache"]))
        assert capture["source_selected_dt_s"] == binding.calendar.dt_s
        if binding.calendar.requested_duration_s is not None:
            assert (
                capture["configured_counts"][binding.calendar.phase] == binding.calendar.step_count
            )
        assert len(capture["frames"]) == len(receipts)
        for i, (receipt, expected) in enumerate(zip(receipts, capture["frames"], strict=True)):
            trial = receipt.trial
            for key in (
                "call_index",
                "event_label_s",
                "elapsed_start_s",
                "elapsed_end_s",
                "duration_s",
                "sampled",
                "events_enabled",
            ):
                assert getattr(trial, key) == expected[key], key
            assert list(trial.source_order) == expected["source_order"]
            errors.append(
                compare(row_values(trial), {key: expected[key] for key in row_values(trial)})
            )
            for key, value in flat({key: expected[key] for key in row_values(trial)}).items():
                columns[f"native_{solver}__row_{i}__" + key.replace(".", "__")] = value
    for i, receipt in enumerate(receipts):
        trial, expected = receipt.trial, independent["frames"][i]
        errors.append(compare(row_values(trial), {key: expected[key] for key in row_values(trial)}))
        resolution.append(
            compare(
                {key: expected[key] for key in row_values(trial)},
                {key: resolved["frames"][i][key] for key in row_values(trial)},
            )
        )
        assert abs(trial.event_label_s - expected["event_label_s"]) <= (
            4 * math.ulp(expected["event_label_s"])
        )
        assert trial.duration_s == binding.calendar.dt_s
        assert trial.sampled == expected["sampled"]
        for key, value in flat(row_values(trial)).items():
            columns[f"actual__row_{i}__" + key.replace(".", "__")] = value
        rows.append(
            dict(
                call_index=i,
                event_label_s=trial.event_label_s,
                elapsed_start_s=trial.elapsed_start_s,
                elapsed_end_s=trial.elapsed_end_s,
                duration_s=trial.duration_s,
                sampled=trial.sampled,
                events_enabled=trial.events_enabled,
                source_order=list(trial.source_order),
                diagnostics=dict(trial.diagnostics),
                fields=list(flat(row_values(trial))),
                checkpoint=replay.checkpoint_record(receipt.checkpoint),
            )
        )
    assert max(resolution) <= 0.1
    evidence(
        name,
        dict(
            mode="complete_source_stream",
            inputs=declared,
            original_binding_identity=binding.identity,
            cache_identity=binding.cache.identity,
            native_source_sha256=source["normal"]["native_source_sha256"],
            native_source_sites=source["normal"]["source_sites"],
            native_solver_guards=["normal", "fast"],
            reference=independent,
            rows=rows,
            cache_fields=list(flat(actual_cache)),
            maximum_error_fraction=max(errors),
            maximum_reference_resolution_fraction=max(resolution),
            endpoint=replay.checkpoint_record(state),
            parents_unchanged=True,
            thermal_transition=False,
            complete_channel_class_trajectories=False,
        ),
        columns,
    )
    return state, receipts


@pytest.mark.parametrize("case", fixtures.CASES)
@pytest.mark.parametrize("phase", ("INIT", "SIM"))
@pytest.mark.parametrize("profile", PROFILES)
def test_complete_native_source_calendar_temperature_clock_probes_and_caches(case, phase, profile):
    binding = build(case, phase, profile)
    _, receipts = qualify(binding, f"stream-{case}-{phase}-{profile}")
    if phase == "INIT":
        assert all(
            np.array_equal(r.checkpoint.values.hh_m, binding.gate_parameters["initial_hh_m"])
            for r in receipts
        )
    if case == "zero_voltage":
        for receipt in receipts:
            assert np.all(receipt.trial.probes.membrane_voltage_after_nonce_V == 1e-25)
            assert np.all(binding.membrane_voltage_V == 0)


@pytest.mark.parametrize("phase", ("INIT", "SIM"))
@pytest.mark.parametrize("count", (0, 1, 2))
def test_empty_single_and_two_call_original_phase_calendars(phase, count):
    qualify(build(phase=phase, count=count), f"clock-edge-{phase}-{count}")


@pytest.mark.parametrize("phase", ("INIT", "SIM"))
def test_requested_duration_retains_native_binary64_truncation(phase):
    binding = build(
        phase=phase, count=2, mutate=lambda data: data["calendar"].update(requested_duration_s=0.3)
    )
    assert binding.calendar.step_count == int(0.3 / 0.1) == 2
    qualify(binding, "duration-truncation-" + phase)


@pytest.mark.parametrize("phase", ("INIT", "SIM"))
@pytest.mark.parametrize("profile", PROFILES)
def test_exact_disk_restart_preserves_original_phase_caches_and_causal_prefix(
    phase, profile, tmp_path
):
    binding = build("carried", phase, profile)
    endpoint, full = run(binding)
    for split in (0, 1, 3, 7):
        point = replay.initialise(binding) if split == 0 else full[split - 1].checkpoint
        directory = tmp_path / str(split)
        archive.save_checkpoint(directory, binding, point)
        restored_binding, restored = archive.load_checkpoint(
            directory, expected_binding_identity=binding.identity
        )
        assert replay.binding_record(restored_binding) == replay.binding_record(binding)
        assert replay.checkpoint_record(restored) == replay.checkpoint_record(point)
        for original in full[split:]:
            receipt = replay.advance(restored_binding, restored)
            assert replay.trial_record(receipt.trial) == replay.trial_record(original.trial)
            restored = receipt.checkpoint
        assert replay.checkpoint_record(restored) == replay.checkpoint_record(endpoint)
    evidence(
        f"restart-{phase}-{profile}",
        dict(
            mode="exact_causal_restart",
            original_binding_identity=binding.identity,
            original_step_count=7,
            split_cursors=[0, 1, 3, 7],
            all_tail_buffers_exact=True,
            disk_archive_used=True,
            original_cache_identity=binding.cache.identity,
        ),
    )


BAD_DEFINITIONS = (
    "kind",
    "provenance",
    "profile",
    "constants",
    "fresh_entry",
    "ecm",
    "extra",
    "missing_gate",
    "extra_gate",
    "owners",
    "short_gate",
    "scalar_gate",
    "negative_probability",
    "large_probability",
    "nonfinite_probability",
    "zero_tau",
    "negative_tau",
    "boolean_unit",
    "zero_phi",
    "too_many_calls",
    "foreign_event",
)


@pytest.mark.parametrize("defect", BAD_DEFINITIONS)
def test_declared_source_owner_constant_and_probe_domains_refuse(defect):
    def damage(data):
        raw, gates = data["raw"], data["raw"]["clock_probes"]
        if defect == "kind":
            raw["kind"] = "ordinary-thermal-model"
        elif defect == "provenance":
            raw["provenance"] = ""
        elif defect == "profile":
            raw["constant_profile"] = "guessed-Q10"
        elif defect == "constants":
            raw["material"]["parameters"]["F_C_mol"] += 1
        elif defect == "fresh_entry":
            raw["material"]["parameters"]["temperature_K"] += 1
        elif defect == "ecm":
            raw["material"]["parameters"]["is_ecm"] = True
        elif defect == "extra":
            raw["heat_capacity"] = 1
        elif defect == "missing_gate":
            gates.pop("hh_m_inf")
        elif defect == "extra_gate":
            gates["guessed_gate"] = 1
        elif defect == "owners":
            gates["owner_ids"] = gates["owner_ids"][::-1]
        elif defect == "short_gate":
            gates["hh_m_inf"] = gates["hh_m_inf"][:-1]
        elif defect == "scalar_gate":
            gates["hh_m_inf"] = 0.5
        elif defect == "negative_probability":
            gates["hh_m_inf"][0] = -0.1
        elif defect == "large_probability":
            gates["hh_m_inf"][0] = 1.1
        elif defect == "nonfinite_probability":
            gates["hh_m_inf"][0] = float("nan")
        elif defect == "zero_tau":
            gates["hh_m_tau_native"][0] = 0
        elif defect == "negative_tau":
            gates["hh_m_tau_native"][0] = -1
        elif defect == "boolean_unit":
            gates["time_unit"] = True
        elif defect == "zero_phi":
            gates["Phi"] = 0
        elif defect == "too_many_calls":
            data["calendar"]["step_count"] = replay.MAX_CALLS + 1
        else:
            data["events"] = [
                dict(
                    kind="pump_block",
                    on_s=0.1,
                    off_s=0.5,
                    change_s=0.1,
                    amplitude=0.0,
                    target_ids=[],
                    positive_boundary=None,
                    negative_boundary=None,
                )
            ]

    damaged = fixtures.fixture()
    damage(damaged)
    with pytest.raises(ValueError):
        bind_data(damaged)
    evidence(
        "rejected-definition-" + defect,
        dict(
            mode="source_definition_refusal",
            defect=defect,
            raw_inputs=raw_input(damaged),
            no_source_call_published=True,
        ),
    )


@pytest.mark.parametrize(
    "defect",
    (
        "temperature",
        "gate",
        "cursor",
        "boolean_cursor",
        "cache_identity",
        "binding_identity",
        "parent",
        "extra",
        "missing",
        "shape",
    ),
)
def test_resealed_restart_changes_cannot_replace_original_source_prefix(defect):
    binding = build()
    _, receipts = run(binding)
    point = receipts[2].checkpoint
    saved = deepcopy(replay.checkpoint_record(point))
    if defect == "temperature":
        saved["values"]["temperature_K"] = replay.buffer_record(point.values.temperature_K + 1)
    elif defect == "gate":
        saved["values"]["hh_m"] = replay.buffer_record(point.values.hh_m + 1e-3)
    elif defect == "cursor":
        saved["call_index"] -= 1
    elif defect == "boolean_cursor":
        saved["call_index"] = True
    elif defect in ("cache_identity", "binding_identity", "parent"):
        saved["parent_identity" if defect == "parent" else defect] = "0" * 64
    elif defect == "extra":
        saved["clock_origin"] = 3
    elif defect == "missing":
        saved["values"].pop("hh_h")
    else:
        saved["values"]["hh_m"]["shape"] = [len(binding.program.membrane_ids) + 1]
    payload = {key: value for key, value in saved.items() if key != "identity"}
    saved["identity"] = replay._digest(payload)
    with pytest.raises(ValueError):
        replay.restore(binding, saved)
    replay.validate(binding, point)
    evidence(
        "rejected-restart-" + defect,
        dict(
            mode="resealed_checkpoint_refusal",
            defect=defect,
            parent_retained=True,
            original_checkpoint=replay.checkpoint_record(point),
            resealed_saved=saved,
        ),
    )


@pytest.mark.parametrize("amplitude", (-4.0, 1e308))
@pytest.mark.parametrize("phase", ("INIT", "SIM"))
def test_raw_invalid_temperature_refuses_without_cache_or_parent_commit(amplitude, phase):
    binding = build(phase=phase, mutate=lambda data: data["events"][0].update(amplitude=amplitude))
    if phase == "INIT":
        qualify(binding, f"unused-temperature-INIT-{amplitude}")
        return
    source = native.evaluate(inputs(binding))
    independent = reference.evaluate(inputs(binding))
    point = replay.initialise(binding)
    refused = None
    for _ in range(binding.calendar.step_count):
        original = replay.checkpoint_record(point)
        try:
            receipt = replay.advance(binding, point)
        except replay.TemperatureCalendarRejected as error:
            refused = error
            assert replay.checkpoint_record(point) == original
            assert error.source is point and error.trial is not None
            trial = error.trial
            assert not trial.diagnostics["temperature_positive"]
            expected = source["frames"][point.call_index]
            np.testing.assert_allclose(
                trial.values.temperature_K,
                expected["values"]["temperature_K"],
                atol=3e-12,
                rtol=6e-12,
            )
            assert independent["first_refused_call_index"] == point.call_index
            evidence(
                f"raw-refusal-{phase}-{amplitude}",
                dict(
                    mode="raw_temperature_refusal",
                    inputs=inputs(binding),
                    accepted_prefix_calls=point.call_index,
                    original_checkpoint=replay.checkpoint_record(point),
                    raw_trial=replay.trial_record(trial),
                    cache_identity=binding.cache.identity,
                    independent_refusal_index=independent["first_refused_call_index"],
                    no_partial_commit=True,
                ),
                {
                    "actual_temperature_K": trial.values.temperature_K,
                    "native_temperature_K": expected["values"]["temperature_K"],
                    **{"raw_probe__" + key: value for key, value in trial.probes._asdict().items()},
                },
            )
            break
        point = receipt.checkpoint
    if phase == "INIT":
        assert refused is None and point.call_index == binding.calendar.step_count
    else:
        assert refused is not None


@pytest.mark.parametrize("defect", ("cache_values", "cache_identity", "kernel", "gate", "voltage"))
def test_resealed_prepared_buffers_do_not_replace_original_declaration(defect):
    binding = build()
    if defect == "cache_values":
        coefficients = binding.cache.coefficients._replace(
            leak_reversal_V=replay._frozen(binding.cache.coefficients.leak_reversal_V + 0.01)
        )
        forged = replace(binding, cache=replace(binding.cache, coefficients=coefficients))
    elif defect == "cache_identity":
        forged = replace(binding, cache=replace(binding.cache, identity="0" * 64))
    elif defect == "kernel":
        forged = replace(
            binding,
            kernel=binding.kernel._replace(
                temperature_multiplier=replay._frozen(binding.kernel.temperature_multiplier + 0.1)
            ),
        )
    elif defect == "gate":
        forged = replace(
            binding,
            gate_parameters=MappingProxyType(
                dict(binding.gate_parameters)
                | dict(hh_m_inf=replay._frozen(binding.gate_parameters["hh_m_inf"] + 0.01))
            ),
        )
    else:
        forged = replace(
            binding, membrane_voltage_V=replay._frozen(binding.membrane_voltage_V + 0.01)
        )
    forged = replace(forged, identity=replay._digest(replay.binding_record(forged)))
    with pytest.raises(ValueError):
        replay.validate_binding(forged)
    evidence(
        "rejected-preparation-" + defect,
        dict(
            mode="resealed_prepared_buffer_refusal",
            defect=defect,
            original_binding_identity=binding.identity,
            no_source_call_published=True,
        ),
    )


@pytest.mark.parametrize(
    "defect", ("checksum", "resealed_gate", "cache_record", "rebased_calendar")
)
def test_restart_files_cannot_reseal_wrong_original_inputs_or_prefix(defect, tmp_path):
    binding = build()
    _, receipts = run(binding)
    point = receipts[2].checkpoint
    path = tmp_path / defect
    archive.save_checkpoint(path, binding, point)
    if defect in ("checksum", "resealed_gate"):
        file = path / "checkpoint.json"
        saved = json.loads(file.read_text())
        saved["values"]["hh_m"] = replay.buffer_record(point.values.hh_m + 0.001)
        saved["identity"] = replay._digest(
            {key: value for key, value in saved.items() if key != "identity"}
        )
    else:
        file = path / "binding.json"
        saved = json.loads(file.read_text())
        if defect == "cache_record":
            saved["binding"]["cache_identity"] = "0" * 64
        else:
            original = binding.calendar
            new = clocks.bind(
                phase=original.phase,
                step_count=original.step_count - 3,
                dt_s=original.dt_s,
                sample_stride=original.sample_stride,
                provenance=original.provenance,
            )
            saved["binding"]["calendar"] = clocks.record(new)
    file.write_text(json.dumps(saved, indent=2, allow_nan=False))
    if defect != "checksum":
        manifest = json.loads((path / "manifest.json").read_text())
        manifest["files"][file.name] = hashlib.sha256(file.read_bytes()).hexdigest()
        (path / "manifest.json").write_text(json.dumps(manifest, indent=2))
    with pytest.raises(ValueError):
        archive.load_checkpoint(path, expected_binding_identity=binding.identity)
    assert point.identity == receipts[2].checkpoint.identity
    evidence(
        "rejected-disk-" + defect,
        dict(
            mode="resealed_restart_archive_refusal",
            defect=defect,
            old_parent_unchanged=True,
            original_binding_identity=binding.identity,
        ),
    )


def test_label_spacing_does_not_replace_physical_gate_clock_or_refresh_caches():
    binding = build()
    _, receipts = run(binding)
    first, middle = receipts[0].trial, receipts[3].trial
    assert middle.event_label_s != middle.elapsed_start_s
    assert middle.event_label_s != middle.elapsed_end_s
    assert middle.values.temperature_K != first.values.temperature_K
    assert first.gate_arithmetic.duration_native_units == binding.calendar.dt_s * 1000
    assert first.gate_arithmetic.duration_native_units != (
        binding.calendar.step_count
        * binding.calendar.dt_s
        / (binding.calendar.step_count - 1)
        * 1000
    )
    for key in (
        "configured_junction_electroflux_alpha",
        "configured_conductivity_S_m2",
        "configured_normal_sigma_S_m",
    ):
        np.testing.assert_array_equal(getattr(first.probes, key), getattr(middle.probes, key))
    assert not np.array_equal(
        first.probes.membrane_electroflux_alpha, middle.probes.membrane_electroflux_alpha
    )
    assert all(receipt.trial.cache_identity == binding.cache.identity for receipt in receipts)
    evidence(
        "explicit-clock-cache-separation",
        dict(
            mode="source_clock_cache_separation",
            original_phase_count=7,
            labels_are_not_update_durations=True,
            live_and_configured_T_paths_distinct=True,
            original_fast_cache_never_refreshed=True,
            no_physical_thermal_transition=True,
        ),
    )


def test_nonfinite_gate_intermediates_remain_raw_and_unpublished():
    def huge_probe(data):
        data["raw"]["clock_probes"]["time_unit"] = 1e308
        data["raw"]["clock_probes"]["Phi"] = 1e308

    binding = build(mutate=huge_probe)
    point = replay.initialise(binding)
    original = replay.checkpoint_record(point)
    source = native.evaluate(inputs(binding))
    independent = reference.evaluate(inputs(binding))
    with pytest.raises(replay.TemperatureCalendarRejected) as caught:
        replay.advance(binding, point)
    trial = caught.value.trial
    assert trial is not None and not trial.diagnostics["gate_arithmetic_finite"]
    assert replay.checkpoint_record(point) == original
    assert independent["first_refused_call_index"] == 0
    assert not independent["frames"][0]["gate_arithmetic_finite"]
    np.testing.assert_array_equal(trial.values.ml_m, source["frames"][0]["values"]["ml_m"])
    evidence(
        "raw-gate-overflow-refusal",
        dict(
            mode="raw_gate_overflow_refusal",
            inputs=inputs(binding),
            raw_trial=replay.trial_record(trial),
            original_checkpoint=original,
            independent_refusal_index=0,
            no_partial_commit=True,
        ),
        {
            "actual_ml_m": trial.values.ml_m,
            "native_ml_m": source["frames"][0]["values"]["ml_m"],
            **{
                "raw_arithmetic__" + key: value
                for key, value in trial.gate_arithmetic._asdict().items()
            },
        },
    )
