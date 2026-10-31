"""Deferred prepared ECM event/noise checks; fixture code is not run during preparation."""

import copy
import json
import os
import subprocess
import sys
import traceback
from pathlib import Path

import numpy as np
import pytest

from cells.processes import betse_normal_ecm_event_join as joined
from cells.processes import betse_normal_ion_join as ions
from tests.unit import test_betse_normal_ecm_catalog_join as catalog
from tests.unit import test_betse_normal_ecm_field_join as base
from tests.unit.test_betse_fast_solver import archive_read
from validation.betse import betse_normal_ecm_event_join_fixtures as fixtures
from validation.betse import betse_normal_ecm_event_join_native as native
from validation.betse.betse_normal_channel_join_runtime import inventory

exact = base.exact
MODES = ("events", "material", "calcium", "channels", "network", "noise", "field")


def root(tmp_path):
    return Path(os.environ.get("CELLS_COMPONENT_EVIDENCE", str(tmp_path))) / "normal-ecm-event-join"


def archive(tmp_path, name, value):
    return native.archives.write_archive(root(tmp_path) / name, ions.data(value))


def references(folder, inputs):
    folder.mkdir(parents=True, exist_ok=False)
    (folder / "inputs.json").write_text(
        json.dumps(fixtures.plain(ions.data(inputs)), indent=2, allow_nan=False) + "\n"
    )
    answers = []
    for level in (1, 2):
        path = folder / ("reference-" + str(level) + ".json")
        with (folder / ("reference-" + str(level) + ".stdout.log")).open("x") as stream:
            subprocess.run(
                [
                    sys.executable,
                    "-B",
                    "-m",
                    "validation.betse.betse_normal_ecm_event_join_reference",
                    "--inputs",
                    str(folder / "inputs.json"),
                    "--output",
                    str(path),
                    "--refinement",
                    str(level),
                ],
                stdout=stream,
                stderr=subprocess.STDOUT,
                check=True,
                timeout=180,
            )
        row = json.loads(path.read_text())
        assert row["production_imports_denied"] and not row["loaded_production_modules"]
        assert row["decimal_precision"] == (100 if level == 1 else 160)
        assert row["carried_reference_forms"] == 0
        answers.append(row)
    return answers


def isolated(tmp_path, inputs):
    folder = root(tmp_path) / ("isolated-" + inputs["case_id"])
    folder.mkdir(parents=True, exist_ok=False)
    (folder / "inputs.json").write_text(json.dumps(inputs, indent=2, allow_nan=False) + "\n")
    with (folder / "native.stdout.log").open("x") as stream:
        subprocess.run(
            [
                sys.executable,
                "-B",
                "-m",
                "validation.betse.betse_normal_ecm_event_join_native",
                "--inputs",
                str(folder / "inputs.json"),
                "--output",
                str(folder / "native"),
            ],
            stdout=stream,
            stderr=subprocess.STDOUT,
            check=True,
            timeout=180,
        )
    captured = archive_read(folder / "native")
    assert captured["production_imports_denied"] and not captured["loaded_production_modules"]
    assert captured["RNG_unchanged"]
    return folder, captured


def check(tmp_path, name, folder, rows):
    archive(tmp_path, name, dict(fields=rows, physical_global_conservation_credit=False))
    result = dict(
        fields={k: v["metric"] for k, v in rows.items()},
        resolutions={k: v["resolution"] for k, v in rows.items()},
        fresh_conditional_reference=True,
        carried_reference_forms=0,
        physical_global_conservation_credit=False,
    )
    (folder / "comparison.json").write_text(json.dumps(result, indent=2) + "\n")
    assert rows and max(v["normalized_max_error"] for v in result["fields"].values()) <= 1
    assert max(v["normalized_max_error"] for v in result["resolutions"].values()) <= 0.1


def numeric_leaves(value, prefix=""):
    if isinstance(value, dict):
        result = {}
        for key, item in value.items():
            result.update(numeric_leaves(item, prefix + "/" + key))
        return result
    return {prefix: np.asarray(value)}


def compare_events(event, reset, lower, target):
    rows, add = base.legacy.comparisons()
    assert [row["stage"] for row in event["stages"]] == [row["stage"] for row in target["stages"]]
    actual_parts = [
        ("after", event["after"], lower["after"], target["after"]),
        ("reset", reset, lower["reset_return"], target["reset_return"]),
    ]
    actual_parts.extend(
        (str(i), a["state"], b["state"], c["state"])
        for i, (a, b, c) in enumerate(
            zip(event["stages"], lower["stages"], target["stages"], strict=True)
        )
    )
    for section, actual, lo, wanted in actual_parts:
        a, b, c = map(numeric_leaves, (actual, lo, wanted))
        assert a.keys() == b.keys() == c.keys()
        for key, value in c.items():
            if section == "reset":
                budget = base.material_checks.budget(key.replace("/", "."), value)
            elif any(stem in key for stem in ("Dm_", "D_env", "D_free")):
                floor = 3e-14 if "weight" in key else 1e-21 if "D_env" in key else 1e-30
                budget = floor + 5e-12 * abs(value)
            elif any("/" + stem in key for stem in ("P_base", "P_mod", "P_cells")):
                budget = 3e-13 + 5e-12 * abs(value)
            elif "/c_env_bound" in key:
                budget = 2e-14 + 5e-13 * abs(value)
            elif "/rho_channel" in key:
                budget = 3e-14 + 5e-12 * abs(value)
            else:
                budget = 64 * np.finfo(float).eps * np.maximum(1.0, abs(value))
            add(
                section + key,
                a[key],
                value,
                b[key],
                budget,
                "unchanged setter/tissue component budgets",
            )
    return rows


def compare_noise_native(actual, captured):
    for key in (
        "before",
        "after",
        "stream_before",
        "stream_after",
        "cache_present",
        "cache_value",
        "source_completed",
        "guard_active",
    ):
        exact(actual[key], captured[key])
    assert len(actual["draws"]) == len(captured["draws"])
    for a, b in zip(actual["draws"], captured["draws"], strict=True):
        np.testing.assert_array_equal(a["values"], b["values"])
        assert a["provenance"]["before_identity"] == b["stream_before"]["identity"]
        assert a["provenance"]["after_identity"] == b["stream_after"]["identity"]


def compare_noise(phase, lower, target):
    rows, add = base.legacy.comparisons()
    for key, wanted in target["values_after"].items():
        wanted = np.asarray(wanted)
        floor = 1e-23 if "flux" in key else 2e-14
        add(
            "after/" + key,
            phase["after"][key],
            wanted,
            lower["values_after"][key],
            floor + 5e-13 * abs(wanted),
            "unchanged protein component budget",
        )
    assert phase["cache_present"] is target["cache_after"]["present"]
    if target["flux"] is None:
        exact(phase["cache_value"], target["cache_after"]["value"])
    else:
        wanted = np.asarray(target["flux"])
        add(
            "flux",
            phase["cache_value"],
            wanted,
            lower["flux"],
            1e-23 + 5e-13 * abs(wanted),
            "unchanged protein flux component budget",
        )
        # Reconstruct source-effective, true-grid and conservative books separately.
        inputs = phase["reference_input"]
        raw = inputs["definition"]
        ext = raw["environment_geometry_definition"]
        cg = ext["current_definition"]["geometry"]
        i = ext["current_definition"]["ions"]["ids"].index("P")
        before, after = phase["before"], phase["after"]
        area = np.asarray(cg["membrane_area_m2"])
        volume = np.asarray(ext["geometry"]["cell_volume_m3"])
        g = phase["geometry"]
        dc = np.asarray(after["cell_mol_m3"])[i] - np.asarray(before["cell_mol_m3"])[i]
        de = (
            np.asarray(after["environment_mol_m3"])[i] - np.asarray(before["environment_mol_m3"])[i]
        )
        transfer = inputs["dt_s"] * np.sum(np.asarray(phase["cache_value"]) * area)
        cell = np.sum(dc * volume)
        effective = np.sum(de) * ext["parameters"]["cell_height_m"] * g.delta_m**2
        book = dict(
            membrane_transfer_mol=transfer,
            cell_change_mol=cell,
            source_effective_environment_change_mol=effective,
            source_effective_balance_mol=cell + effective,
            conservative_environment_change_mol=-transfer,
            conservative_balance_mol=cell - transfer,
            true_grid_environment_change_mol=np.sum(de * g.true_environment_volume_m3),
            source_minus_conservative_environment_mol=effective + transfer,
        )
        for key, wanted in target["book"].items():
            # Fixed amount floor from existing ECM direct-update books; no balance credit.
            add(
                "book/" + key,
                book[key],
                wanted,
                lower["book"][key],
                3e-14 + 6e-12 * abs(wanted),
                "unchanged ECM amount budget",
            )
    for key in (
        "membrane_flux_mol_m2_s",
        "junction_flux_mol_m2_s",
        "environment_flux_x_mol_m2_s",
        "environment_flux_y_mol_m2_s",
    ):
        np.testing.assert_array_equal(phase["before"][key], phase["after"][key])
    return rows


@pytest.mark.parametrize("case", fixtures.CASES)
def test_ecm_event_history(tmp_path, case):
    inputs = fixtures.fixture(case)
    prep = root(tmp_path) / ("preparation-" + case)
    prep.mkdir(parents=True, exist_ok=False)
    (prep / "inputs-before-constructor.json").write_text(json.dumps(inputs, indent=2) + "\n")
    cold_input = base.cold_inputs(inputs["field"])
    cold_input.update(
        catalog=inputs["catalog"],
        calcium_configuration=inputs["calcium"],
        bootstrap_dt_s=inputs["field"]["bootstrap"]["dt_s"],
    )
    cold = references(prep / "cold", cold_input)
    cold_returns, bootstrap = [], []

    def after_cold(value):
        archive(tmp_path, case + "-cold-return", value)
        cold_returns.append(value)

    def before_bootstrap(value):
        bootstrap.extend(references(prep / "bootstrap", value))

    try:
        binding = joined.bind(inputs)
        parent = joined.initialize(binding, after_cold=after_cold, before_field=before_bootstrap)
        archive(tmp_path, case + "-bootstrap-return", parent)
    except Exception as error:
        archive(
            tmp_path,
            case + "-unexpected-cold",
            dict(
                error=str(error),
                traceback=traceback.format_exc(),
                partial=getattr(error, "partial", None),
            ),
        )
        raise
    folder, captured = isolated(tmp_path, inputs)
    assert captured["status"] == "source_completed" and len(captured["history"]) == 3
    assert len(cold_returns) == 1 and len(bootstrap) == 2
    cold_parent = cold_returns[0]
    exact(cold_parent["network"].network_cache, captured["cold_cache"])
    exact(cold_parent["network"].material.values._asdict(), captured["cold_material"])
    exact(cold_parent["policy"], captured["cold_policy"])
    exact(cold_parent["channel_trace"], captured["cold_trace"])
    exact(cold_parent["event_stores"], captured["cold_event_stores"])
    exact(
        joined.random_source.native_stream_manifest(parent.noise_stream),
        captured["cold_noise_stream"],
    )
    exact(ions.data(parent.noise_cache), captured["cold_noise_cache"])
    check(
        tmp_path,
        case + "-cold-errors",
        prep / "cold",
        catalog.compare_cold(binding, cold_parent, *cold),
    )
    exact(parent.field.before, captured["bootstrap"]["before"])
    for section, value in base.field_output(parent.field).items():
        exact(value, captured["bootstrap"][section])
    check(
        tmp_path,
        case + "-bootstrap-errors",
        prep / "bootstrap",
        base.compare_field(binding, parent.field, *bootstrap),
    )
    for index, native_call in enumerate(captured["history"]):
        point = prep / ("point-" + str(index))
        point.mkdir()
        answers = {name: [] for name in MODES}
        observed = {}

        def before(name, index=index, observed=observed, answers=answers, point=point):
            def callback(incoming):
                archive(tmp_path, case + "-actual-" + name + "-input-" + str(index), incoming)
                observed[name] = ions.data(incoming)
                answers[name].extend(references(point / name, incoming))

            return callback

        def after_material(candidate, trial, feedback, calcium, noise, index=index):
            archive(
                tmp_path,
                case + "-material-before-field-" + str(index),
                dict(
                    candidate=candidate,
                    trial=trial,
                    feedback=feedback,
                    calcium=calcium,
                    noise=noise,
                ),
            )

        digest = ions.digest(parent)
        try:
            candidate, trial, feedback, calcium, noise, context = joined.advance(
                binding,
                parent,
                before_events=before("events"),
                before_material=before("material"),
                before_calcium=before("calcium"),
                before_channels=before("channels"),
                before_network=before("network"),
                before_noise=before("noise"),
                before_field=before("field"),
                after_events=lambda value, index=index: archive(
                    tmp_path, case + "-event-return-" + str(index), value
                ),
                after_noise=lambda value, index=index: archive(
                    tmp_path, case + "-noise-return-" + str(index), value
                ),
                after_material=after_material,
            )
            archive(
                tmp_path,
                case + "-complete-return-" + str(index),
                dict(
                    parent=parent,
                    candidate=candidate,
                    trial=trial,
                    network=feedback,
                    calcium=calcium,
                    noise=noise,
                    context=context,
                ),
            )
        except Exception as error:
            archive(
                tmp_path,
                case + "-unexpected-call-" + str(index),
                dict(
                    parent=parent,
                    error=str(error),
                    traceback=traceback.format_exc(),
                    partial=getattr(error, "partial", None),
                ),
            )
            raise
        assert digest == ions.digest(parent) and all(len(row) == 2 for row in answers.values())
        exact(observed["events"], native_call["before_events"])
        exact(context["events"], native_call["events"])
        exact(context["reset_return"], native_call["reset_return"])
        material_input = copy.deepcopy(observed["material"])
        # Qualified draw labels are port metadata. Native owns its original draw/stream.
        material_input.pop("prospective_noise_draw")
        exact(material_input, native_call["material_before"])
        exact(observed["calcium"], native_call["calcium"]["before"])
        exact(observed["channels"], native_call["network"]["before_channels"])
        exact(observed["network"], native_call["network"]["before"])
        exact(observed["field"], native_call["field"]["before"])
        base.compare_native_material(trial, native_call)
        exact(feedback, native_call["network"])
        catalog.compare_calcium_native(calcium, native_call["calcium"])
        compare_noise_native(noise, native_call["noise"])
        exact(ions.data(candidate.noise_cache), native_call["noise_cache_after"])
        exact(
            joined.random_source.native_stream_manifest(candidate.noise_stream),
            native_call["noise_stream_after"],
        )
        exact(candidate.event_stores, native_call["event_stores_after"])
        exact(candidate.network.network_cache, native_call["post_material_cache"])
        exact(candidate.network.material.values._asdict(), native_call["candidate"])
        exact(ions.data(candidate.rate_cache), native_call["rate_cache_after"])
        exact(ions.data(parent.clock), native_call["clock_before"])
        exact(ions.data(candidate.clock), native_call["clock_after"])
        for section, value in base.field_output(candidate.field).items():
            exact(value, native_call["field"][section])
        assert (
            context["runtime_material_binding"].geometry_binding.identity
            == binding.material_binding.geometry_binding.identity
        )
        preview = observed["material"]
        assert preview["prospective_draw_is_uncommitted"] is True
        exact(preview["noise_stream_before"], noise["stream_before"])
        exact(preview["prospective_stream_after"], noise["stream_after"])
        if noise["guard_active"]:
            assert len(noise["draws"]) == 1
            np.testing.assert_array_equal(
                preview["prospective_noise_uniforms"], noise["draws"][0]["values"]
            )
        else:
            assert not noise["draws"] and preview["prospective_noise_uniforms"] is None
        noise_comparison = dict(
            ions.data(noise),
            reference_input=observed["noise"],
            geometry=binding.material_binding.geometry_binding.geometry,
        )
        for mode, rows in (
            (
                "events",
                compare_events(context["events"], context["reset_return"], *answers["events"]),
            ),
            ("material", base.compare_material(trial, *answers["material"])),
            ("calcium", catalog.compare_calcium(calcium, *answers["calcium"])),
            ("channels", catalog.compare_channels(binding, feedback, *answers["channels"])),
            ("network", base.legacy.compare_local(feedback, *answers["network"])),
            ("noise", compare_noise(noise_comparison, *answers["noise"])),
            ("field", base.compare_field(binding, candidate.field, *answers["field"])),
        ):
            check(tmp_path, case + "-" + mode + "-errors-" + str(index), point / mode, rows)
        if case == "NaK_shape":
            assert np.asarray(context["events"]["after"]["NaKATP_block"]).shape == ()
        if case == "voltage_same_edge":
            assert context["events"]["after"]["bound_V"]["R"] <= 0
        if case == "static_K_reset" and index == 0:
            np.testing.assert_array_equal(
                context["events"]["after"]["Dm_cells"], inputs["entry_event_state"]["Dm_base"]
            )
        if case == "noise_zero_level":
            assert len(noise["draws"]) == 1 and np.count_nonzero(noise["cache_value"]) == 0
        if case in ("noise_disabled", "static_K_reset"):
            assert not noise["draws"]
        if case == "noise_disabled":
            exact(ions.data(candidate.noise_cache), ions.data(parent.noise_cache))
            assert candidate.noise_cache.present
        assert candidate.clock.material_dt_sum_s == (index + 1) * inputs["calendar"]["dt_s"]
        parent = candidate
    (folder / "comparison.json").write_text(
        json.dumps(
            dict(
                completed=True,
                exact_native=True,
                complete_calls=3,
                case_role=inputs["case_role"],
                cold_reference_forms=2,
                bootstrap_reference_forms=2,
                conditional_event_reference_forms=6,
                conditional_material_reference_forms=6,
                conditional_calcium_reference_forms=6,
                conditional_channel_reference_forms=6,
                conditional_network_reference_forms=6,
                conditional_noise_reference_forms=6,
                conditional_field_reference_forms=6,
                carried_reference_forms=0,
                complete_native_ECM_events=True,
                complete_native_ECM_protein_noise=True,
                actual_persistent_coefficient_owner=True,
                actual_normal_source_clock=True,
                source_ER_disabled=True,
                retained_material_panel_accepted=False,
                retained_material_checks_passed=39,
                retained_material_checks_total=40,
                physical_global_conservation_credit=False,
                native_initializer_or_mesh_claim=False,
                independent_trajectory=False,
            ),
            indent=2,
        )
        + "\n"
    )


@pytest.mark.parametrize("case", fixtures.RAW_CASES)
def test_ecm_event_raw_partial(tmp_path, case):
    inputs = fixtures.raw_fixture(case)
    archive(tmp_path, case + "-raw-inputs", inputs)
    folder, captured = isolated(tmp_path, inputs)
    binding, parent, completed = None, None, 0
    try:
        binding = joined.bind(inputs)
        parent = joined.initialize(
            binding, after_cold=lambda value: archive(tmp_path, case + "-raw-cold-return", value)
        )
        for index in range(inputs["stop_after_calls"]):
            returned = joined.advance(
                binding,
                parent,
                before_events=lambda value, index=index: archive(
                    tmp_path, case + "-raw-events-input-" + str(index), value
                ),
                after_events=lambda value, index=index: archive(
                    tmp_path, case + "-raw-events-return-" + str(index), value
                ),
                before_network=lambda value, index=index: archive(
                    tmp_path, case + "-raw-GRN-input-" + str(index), value
                ),
                before_noise=lambda value, index=index: archive(
                    tmp_path, case + "-raw-noise-input-" + str(index), value
                ),
                after_noise=lambda value, index=index: archive(
                    tmp_path, case + "-raw-noise-return-" + str(index), value
                ),
                after_material=lambda *value, index=index: archive(
                    tmp_path, case + "-raw-material-return-" + str(index), value
                ),
            )
            archive(tmp_path, case + "-raw-complete-return-" + str(index), returned)
            parent = returned[0]
            completed += 1
    except joined.EventJoinRejected as error:
        partial = ions.data(error.partial)
        archive(
            tmp_path,
            case + "-raw-available-partial",
            dict(
                parent=parent, partial=partial, error=str(error), traceback=traceback.format_exc()
            ),
        )
        assert partial["stage"] == "event_material_network_noise_field"
        assert partial["available"] and partial["available_event_stores"]
        native_complete = sum(row.get("source_completed", False) for row in captured["history"])
        if case in ("zero_global_pulse_width", "radial_pressure_shape"):
            assert completed == 0 and captured["status"] == "source_refused"
            assert captured["failure"]["stage"] == "events"
            exact(partial["available_event_stores"], captured["history"][0]["events"]["after"])
            assert not partial["available"].get("noise")
        elif case == "negative_Dm_source_return":
            # Native N3 labels are 0, 1.5dt, 3dt. The smooth pulse leaves
            # nonnegative diffusion at call0; its negative lobe is reached at
            # call1. Preserve the completed prefix and the stricter port guard.
            assert completed == 1 and parent.clock.call_index == 1
            assert captured["status"] == "source_completed" and native_complete == 3
            assert np.min(captured["history"][0]["events"]["after"]["Dm_cells"]) >= 0
            diffusion = partial["available_event_stores"]["Dm_cells"]
            assert np.isfinite(diffusion).all() and np.min(diffusion) < 0
            assert str(error) == "Incomplete/nonfinite source array or domain: membrane diffusion"
            assert partial["available"]["events"]["source_completed"]
            expected = captured["history"][1]
            exact(partial["available"]["before_events"]["clock"], expected["clock_before"])
            assert partial["available"]["events"]["source_time_s"] == (
                1.5 * inputs["calendar"]["dt_s"]
            )
            exact(partial["available"]["events"]["stages"], expected["events"]["stages"])
            exact(partial["available_event_stores"], expected["events"]["after"])
            assert not partial["available"].get("noise")
        elif case == "GRN_refuses_before_noise":
            assert completed == 0 and captured["status"] == "source_refused"
            assert not partial["available"].get("noise")
            exact(captured["history"][0]["noise_stream_after"], inputs["prepared_rng"]["manifest"])
            exact(
                partial["catalog_trace"]["before"],
                captured["history"][0]["network"]["before"],
            )
        elif case == "late_negative_temperature":
            assert completed == 2 and partial["available_event_stores"]["T"] < 0
            assert partial["available"]["events"]["source_completed"]
        else:
            # Retain actual reached noise/field/source limit; do not predetermine
            # an overflow stage, assume nonfinite flux, or tune its amplitude.
            assert case == "protein_noise_large_limit" and completed < 3
            assert partial["available"].get("before_noise") or captured["noise_rows"]
        report = dict(
            positive_credit=False,
            completed_calls=completed,
            native_complete_calls=native_complete,
            native_status=captured["status"],
            port_stage=partial["stage"],
            strict_port_guard_distinct_from_native_exception=case
            in (
                "negative_Dm_source_return",
                "protein_noise_large_limit",
                "late_negative_temperature",
            ),
            complete_native_raw_buffers_retained=True,
            complete_available_port_partial_retained=True,
            source_ER_disabled=True,
            physical_global_conservation_credit=False,
        )
    except Exception as error:
        archive(
            tmp_path,
            case + "-raw-unexpected-refusal",
            dict(
                parent=parent,
                error=str(error),
                traceback=traceback.format_exc(),
                partial=getattr(error, "partial", None),
            ),
        )
        raise
    else:
        archive(
            tmp_path,
            case + "-raw-unexpected-complete",
            dict(parent=parent, completed_calls=completed),
        )
        raise AssertionError(
            "Declared source/strict-port raw limit not reached; preserve returned evidence"
        )
    (folder / "raw-retention.json").write_text(json.dumps(report, indent=2) + "\n")


@pytest.mark.parametrize("dependency", fixtures.DEPENDENCIES)
def test_ecm_event_dependencies(tmp_path, dependency):
    inputs = fixtures.fixture("combined")
    archive(tmp_path, dependency + "-baseline-inputs", inputs)
    binding = joined.bind(inputs)
    parent = joined.initialize(
        binding, after_cold=lambda value: archive(tmp_path, dependency + "-baseline-cold", value)
    )
    archive(tmp_path, dependency + "-valid-admission", dict(binding=binding, parent=parent))
    changed = copy.deepcopy(inputs)
    owner = changed["event_owner"]
    expected = {
        "missing_owner": "Require a separately declared ECM event/catalog/noise composition",
        "changed_geometry_owner": (
            "Tissue/event owners must bind the supplied original geometry declaration"
        ),
        "mismatched_environment_targets": (
            "Supplied tissue ECM targets differ from original membrane-grid ownership"
        ),
        "missing_M_role": "Native K/Na salt events require an explicit complete M-1 ion role",
        "wrong_RNG_version": "Native replay requires the recorded NumPy version",
        "missing_Gaussian_cache": (
            "Require complete MT19937 algorithm/words/position/Gaussian cache state"
        ),
        "changed_noise_cache": "Require complete immutable actual protein-noise cache or absence",
        "changed_event_store": "Event and GRN control owners differ at the actual parent epoch",
        "competing_control_override": (
            "Event-owned persistent controls cannot have competing per-step overrides"
        ),
        "cut_requested": "Cuts/remeshing require separately supplied changing geometry ownership",
        "bitmap_unowned": (
            "Bitmap/unowned callback initialization requires separate supplied dependencies"
        ),
        "inconsistent_time_callbacks": (
            "Native callbacks share one supplied phase time-program configuration"
        ),
        "wrong_scalar_callback": "Preserve actual source scalar-one callback default",
        "missing_field": "Require the actual preceding full field",
        "wrong_clock": "Require original source labels and separate accumulated material dt",
        "missing_network_cache": "Require every ECM owner/cache field",
    }[dependency]
    parent_deps = {
        "changed_noise_cache",
        "changed_event_store",
        "missing_field",
        "wrong_clock",
        "missing_network_cache",
    }
    if dependency in parent_deps:
        stores = ions.data(parent.event_stores)
        net, field, clock, cache = parent.network, parent.field, parent.clock, parent.noise_cache
        if dependency == "changed_noise_cache":
            cache = joined.NoiseCache(True, ions.freeze(np.zeros(1)))
        elif dependency == "changed_event_store":
            stores["NaKATP_block"] = 0.25
        elif dependency == "missing_field":
            field = None
        elif dependency == "wrong_clock":
            clock = joined.Clock(parent.clock.source_times_s, 1, 0.0)
        else:
            cached = ions.data(net.network_cache)
            cached["wire"].pop("channel_fields")
            net = joined.network._state(binding, net.material, cached, net.controls)
        malformed = joined.joined_state(
            binding, net, field, parent.rate_cache, clock, stores, parent.noise_stream, cache
        )
        archive(tmp_path, dependency + "-malformed-parent", malformed)
        with pytest.raises((ValueError, joined.EventJoinRejected)) as caught:
            joined.advance(binding, malformed)
    elif dependency == "missing_M_role":
        # Direct role prerequisite, with actual supplied owner and a declared
        # no-M role list. No fabricated scientific Binding is admitted.
        with pytest.raises(ValueError) as caught:
            joined.require_salt_roles(owner, ["Na", "K", "Cl", "Ca", "P"], [1, 1, -1, 2, -1])
    else:
        if dependency == "missing_owner":
            changed.pop("event_owner")
        elif dependency == "changed_geometry_owner":
            owner["geometry_declaration_sha256"] = "0" * 64
        elif dependency == "mismatched_environment_targets":
            owner["env_target_inds"]["all"][0] = (owner["env_target_inds"]["all"][0] + 1) % len(
                owner["owners"]["environment_ids"]
            )
        elif dependency == "wrong_RNG_version":
            changed["prepared_rng"]["manifest"]["numpy_version"] = "unowned"
        elif dependency == "missing_Gaussian_cache":
            changed["prepared_rng"]["manifest"]["state"] = changed["prepared_rng"]["manifest"][
                "state"
            ][:3]
        elif dependency == "competing_control_override":
            changed["field"]["steps"][1]["material"]["runtime_temperature_K"] += 1
        elif dependency == "cut_requested":
            owner["event_cut"] = {"is_fired": False}
        elif dependency == "bitmap_unowned":
            owner["scheduled_options"]["Na_mem"][5] = "bitmap"
            owner["callbacks"]["Namem"]["source_function"] = "bitmap"
            fixtures.rebuild_owner(changed)
        elif dependency == "inconsistent_time_callbacks":
            for suffix in ("Namem", "Kmem"):
                owner["scheduled_options"]["Na_mem" if suffix == "Namem" else "K_mem"][5] = (
                    "periodic"
                )
                owner["callbacks"][suffix]["source_function"] = "periodic"
                owner["callbacks"][suffix]["dynamic"] = dict(
                    kind="periodic",
                    frequency=1.0 if suffix == "Namem" else 2.0,
                    phase=0.0,
                    provenance="Explicit inconsistent source shared configuration",
                )
            fixtures.rebuild_owner(changed)
        else:
            owner["callbacks"]["Namem"]["source_scalar"] = 2.0
        archive(tmp_path, dependency + "-malformed-inputs", changed)
        with pytest.raises(ValueError) as caught:
            joined.bind(changed)
    leaf = caught.value
    archive(tmp_path, dependency + "-partial", getattr(leaf, "partial", None))
    while leaf.__cause__ is not None:
        leaf = leaf.__cause__
    archive(tmp_path, dependency + "-refusal", dict(type=type(leaf).__name__, message=str(leaf)))
    assert type(leaf) is ValueError and str(leaf) == expected
    (root(tmp_path) / ("dependency-" + dependency + ".json")).write_text(
        json.dumps(
            dict(
                baseline_admitted=True,
                intended_failure_reached=True,
                actual_leaf_type=type(leaf).__name__,
                actual_message=str(leaf),
                expected_message=expected,
                source_failure_credit=False,
            ),
            indent=2,
        )
        + "\n"
    )


@pytest.fixture(scope="module", autouse=True)
def runtime_receipt(tmp_path_factory):
    row = inventory()
    if cpu := os.environ.get("CELLS_ECM_EVENT_CPU"):
        assert row["measured_cpu_affinity"] == [int(cpu)]
    folder = root(tmp_path_factory.getbasetemp())
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "runtime.json").write_text(json.dumps(row, indent=2) + "\n")
