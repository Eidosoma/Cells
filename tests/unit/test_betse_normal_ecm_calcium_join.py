"""Prepared native ECM CaATP/full-field checks; ER stays source-disabled."""

import copy
import json
import os
import subprocess
import sys
import traceback
from pathlib import Path

import numpy as np
import pytest

from cells.processes import betse_normal_ecm_calcium_join as joined
from cells.processes import betse_normal_ion_join as ions
from tests.unit import test_betse_normal_ecm_field_join as base
from tests.unit.test_betse_fast_solver import archive_read
from validation.betse import betse_normal_ecm_calcium_join_fixtures as fixtures
from validation.betse import betse_normal_ecm_calcium_join_native as native
from validation.betse.betse_normal_channel_join_runtime import inventory

exact = base.exact


def root(tmp_path):
    return (
        Path(os.environ.get("CELLS_COMPONENT_EVIDENCE", str(tmp_path))) / "normal-ecm-calcium-join"
    )


def archive(tmp_path, name, value):
    return native.archives.write_archive(root(tmp_path) / name, ions.data(value))


def references(folder, inputs):
    folder.mkdir(parents=True, exist_ok=False)
    (folder / "inputs.json").write_text(
        json.dumps(base.legacy.old.old.plain(ions.data(inputs)), indent=2, allow_nan=False) + "\n"
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
                    "validation.betse.betse_normal_ecm_calcium_join_reference",
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
        assert (
            row["decimal_precision"] == (100 if level == 1 else 160)
            and row["carried_reference_forms"] == 0
        )
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
                "validation.betse.betse_normal_ecm_calcium_join_native",
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
    assert (
        captured["production_imports_denied"]
        and not captured["loaded_production_modules"]
        and captured["RNG_unchanged"]
    )
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


def compare_calcium_native(phase, captured, *, helper_only=False):
    exact(phase["before"], captured["before"])
    core = phase["helper"]
    if core is None:
        assert captured["helper"] is None
    else:
        exact(ions.data(core), captured["helper"])
    if not helper_only:
        exact(ions.data(phase["rate_cache_after"]), captured["rate_cache_after"])
        exact(phase["values_after"], captured["values_after"])
        assert captured["source_completed"] and phase["source_completed"]
        assert (
            captured["handler_locals"]["rate_aliases_handler_flux"]
            == phase["source_rate_aliases_handler_flux"]
        )
        assert (
            captured["handler_locals"]["rate_aliases_helper_flux"]
            == phase["source_rate_aliases_helper_flux"]
        )
    assert phase["before"]["Ca_dyn"] is False and not phase["before"]["ER_executed"]


def compare_calcium(phase, lower, target):
    rows, add = base.legacy.comparisons()
    cached = phase["rate_cache_after"]
    assert cached.present is target["rate_cache_after"]["present"]
    if cached.present:
        wanted = np.asarray(target["rate_cache_after"]["value"])
        add(
            "rate_after",
            cached.value,
            wanted,
            lower["rate_cache_after"]["value"],
            2e-18 + 2e-11 * abs(wanted),
            "mol/m2/s",
        )
    else:
        assert cached.value is None and target["rate_cache_after"]["value"] is None
    before = phase["before"]["values_before"]
    ids = phase["before"]["definition"]["environment_geometry_definition"]["current_definition"][
        "ions"
    ]["ids"]
    i = ids.index("Ca")
    applied = (
        phase["values_after"]["membrane_flux_mol_m2_s"][i] - before["membrane_flux_mol_m2_s"][i]
    )
    wanted = np.asarray(target["applied_flux_mol_m2_s"])
    add(
        "applied",
        applied,
        wanted,
        lower["applied_flux_mol_m2_s"],
        2e-18 + 2e-11 * abs(wanted),
        "mol/m2/s",
    )
    if target["arithmetic"] is not None:
        core = phase["helper"]
        for key, value in target["arithmetic"].items():
            if key == "zero_denominator_indices":
                np.testing.assert_array_equal(core.arithmetic[key], value)
                continue
            wanted = np.asarray(value)
            floor = 2e-18 if key == "raw_flux_mol_m2_s" else 2e-14
            add(
                "kernel/" + key,
                core.arithmetic[key],
                wanted,
                lower["arithmetic"][key],
                floor + 2e-11 * abs(wanted),
                "native conditional CaATP arithmetic",
            )
    for key in ("membrane_mol_m3", "environment_mol_m3", "membrane_flux_mol_m2_s"):
        wanted = np.asarray(target["values_after"][key])
        floor = 1e-18 if "flux" in key else 3e-13
        add(
            "handler/" + key,
            phase["values_after"][key],
            wanted,
            lower["values_after"][key],
            floor + 6e-12 * abs(wanted),
            "source material buffer",
        )
    return rows


def compare_cold(binding, parent, lower, target):
    rows = base.legacy.compare_cold(binding, parent["network"], lower, target)
    _, add = base.legacy.comparisons()
    more = {}
    for section, actual in (
        ("native_policy", parent["policy"]),
        ("clock", ions.data(parent["clock"])),
    ):
        for key, value in target[section].items():
            if isinstance(value, dict):
                assert dict(actual[key]) == value
            elif value is None or type(value) is bool:
                assert actual[key] is value
            else:
                a, b = np.asarray(actual[key]), np.asarray(value)
                np.testing.assert_array_equal(a, b)
                # Fixed scalar/clock defaults are exact, independent source producers.
                more[section + "/" + key] = dict(
                    actual=a,
                    target=b,
                    lower=np.asarray(lower[section][key]),
                    error=abs(a - b),
                    budget=np.full(a.shape, 1e-30),
                    unit="native cold producer",
                    metric=base.legacy.old.old.metric(a, b, 1e-30),
                    resolution=base.legacy.old.old.metric(lower[section][key], b, 1e-30),
                )
    rows.update(more)
    assert not parent["rate_cache"].present and parent["rate_cache"].value is None
    return rows


@pytest.mark.parametrize("case", fixtures.CASES)
def test_ecm_calcium_field_history(tmp_path, case):
    inputs = fixtures.fixture(case)
    prep = root(tmp_path) / ("preparation-" + case)
    prep.mkdir(parents=True, exist_ok=False)
    (prep / "inputs-before-constructor.json").write_text(json.dumps(inputs, indent=2) + "\n")
    cold_inputs = base.cold_inputs(inputs["field"])
    cold_inputs.update(
        calcium_configuration=inputs["calcium"], bootstrap_dt_s=inputs["field"]["bootstrap"]["dt_s"]
    )
    cold = references(prep / "cold", cold_inputs)
    cold_parents, bootstrap = [], []

    def after_cold(value):
        archive(tmp_path, case + "-cold-return-before-bootstrap", value)
        cold_parents.append(value)

    def before_bootstrap(value):
        bootstrap.extend(references(prep / "bootstrap", value))

    try:
        binding = joined.bind(inputs)
        parent = joined.initialize(binding, after_cold=after_cold, before_field=before_bootstrap)
        archive(tmp_path, case + "-bootstrap-return", dict(parent=parent))
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
    assert len(cold_parents) == 1 and len(bootstrap) == 2
    exact(cold_parents[0]["network"].network_cache, captured["cold_cache"])
    exact(cold_parents[0]["network"].material.values._asdict(), captured["cold_material"])
    exact(cold_parents[0]["policy"], captured["cold_policy"])
    np.testing.assert_array_equal(parent.clock.source_times_s, captured["source_times_s"])
    check(
        tmp_path,
        case + "-cold-errors",
        prep / "cold",
        compare_cold(binding, cold_parents[0], *cold),
    )
    exact(parent.field.before, captured["bootstrap"]["before"])
    for section, value in base.field_output(parent.field).items():
        exact(value, captured["bootstrap"][section])
    exact(parent.network.material.values._asdict(), captured["bootstrap"]["candidate"])
    check(
        tmp_path,
        case + "-bootstrap-errors",
        prep / "bootstrap",
        base.compare_field(binding, parent.field, *bootstrap),
    )
    for index, native_call in enumerate(captured["history"]):
        point = prep / ("point-" + str(index))
        point.mkdir()
        answers = {name: [] for name in ("material", "calcium", "network", "field")}
        observed = {}

        def before(name, observed=observed, answers=answers, point=point):
            def callback(incoming):
                observed[name] = ions.data(incoming)
                answers[name].extend(references(point / name, incoming))

            return callback

        def after_calcium(rate, phase, index=index):
            archive(
                tmp_path,
                case + "-CaATP-return-before-GRN-" + str(index),
                dict(rate=rate, phase=phase),
            )

        def after_material(candidate, trial, feedback, phase, index=index, parent=parent):
            archive(
                tmp_path,
                case + "-material-return-before-field-" + str(index),
                dict(
                    parent=parent, candidate=candidate, trial=trial, network=feedback, calcium=phase
                ),
            )

        digest = ions.digest(parent)
        try:
            candidate, trial, feedback, phase, context = joined.advance(
                binding,
                parent,
                before_material=before("material"),
                before_calcium=before("calcium"),
                before_network=before("network"),
                before_field=before("field"),
                after_calcium=after_calcium,
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
                    calcium=phase,
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
        exact(observed["material"], native_call["material_before"])
        exact(observed["calcium"], native_call["calcium"]["before"])
        exact(observed["network"], native_call["network"]["before"])
        exact(observed["field"], native_call["field"]["before"])
        base.compare_native_material(trial, native_call)
        exact(feedback, native_call["network"])
        exact(context["material_parent"].network_cache, native_call["post_material_cache"])
        exact(candidate.network.network_cache, native_call["post_material_cache"])
        compare_calcium_native(phase, native_call["calcium"])
        exact(ions.data(candidate.rate_cache), native_call["rate_cache_after"])
        exact(ions.data(parent.clock), native_call["clock_before"])
        exact(ions.data(candidate.clock), native_call["clock_after"])
        assert (
            candidate.clock.call_index == index + 1
            and candidate.clock.material_dt_sum_s
            == (index + 1) * inputs["field"]["bootstrap"]["dt_s"]
        )
        for section, value in base.field_output(candidate.field).items():
            exact(value, native_call["field"][section])
        exact(candidate.network.material.values._asdict(), native_call["candidate"])
        for key in (
            "junction_voltage_V",
            "junction_field_source",
            "junction_field_xy_source",
            "gap_open",
        ):
            np.testing.assert_array_equal(
                getattr(candidate.network.material.values, key),
                getattr(context["material_parent"].material.values, key),
            )
        for mode, rows in (
            ("material", base.compare_material(trial, *answers["material"])),
            ("calcium", compare_calcium(phase, *answers["calcium"])),
            ("network", base.legacy.compare_local(feedback, *answers["network"])),
            ("field", base.compare_field(binding, candidate.field, *answers["field"])),
        ):
            check(tmp_path, case + "-" + mode + "-errors-" + str(index), point / mode, rows)
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
                conditional_material_reference_forms=6,
                conditional_calcium_reference_forms=6,
                conditional_network_reference_forms=6,
                conditional_field_reference_forms=6,
                carried_reference_forms=0,
                complete_native_ECM_CaATP=True,
                source_ER_disabled=True,
                maintained_native_producers=True,
                actual_rate_cache_absence_and_carry=True,
                actual_normal_source_clock=True,
                old_field_seam_removed=True,
                stale_gap_caches_preserved=True,
                retained_material_panel_accepted=False,
                retained_material_checks_passed=39,
                retained_material_checks_total=40,
                physical_global_conservation_credit=False,
                formal_ATP_consumption_claim=False,
                native_ER_cold_or_restart_parity=False,
                independent_trajectory=False,
            ),
            indent=2,
        )
        + "\n"
    )


@pytest.mark.parametrize("case", fixtures.RAW_CASES)
def test_ecm_calcium_raw_partial(tmp_path, case):
    inputs = fixtures.raw_fixture(case)
    archive(tmp_path, case + "-raw-inputs", inputs)
    folder, captured = isolated(tmp_path, inputs)
    completed = []
    parent = None

    def after_cold(value):
        archive(tmp_path, case + "-raw-cold-return", value)

    def before_calcium(value):
        archive(tmp_path, case + "-raw-before-CaATP-" + str(len(completed)), value)

    def after_calcium(rate, phase):
        archive(
            tmp_path,
            case + "-raw-CaATP-return-" + str(len(completed)),
            dict(rate=rate, phase=phase),
        )

    def after_material(candidate, trial, feedback, phase):
        archive(
            tmp_path,
            case + "-raw-material-return-" + str(len(completed)),
            dict(candidate=candidate, trial=trial, network=feedback, calcium=phase),
        )

    try:
        binding = joined.bind(inputs)
        parent = joined.initialize(binding, after_cold=after_cold)
        archive(tmp_path, case + "-raw-bootstrap-return", dict(parent=parent))
        for index in range(3):
            candidate, trial, feedback, phase, context = joined.advance(
                binding,
                parent,
                before_calcium=before_calcium,
                after_calcium=after_calcium,
                after_material=after_material,
            )
            archive(
                tmp_path,
                case + "-raw-complete-return-" + str(index),
                dict(
                    parent=parent,
                    candidate=candidate,
                    trial=trial,
                    network=feedback,
                    calcium=phase,
                    context=context,
                ),
            )
            completed.append((candidate, trial, feedback, phase, context))
            parent = candidate
    except joined.CalciumJoinRejected as error:
        partial = error.partial
        archive(
            tmp_path,
            case + "-raw-available-partial",
            dict(
                parent=parent, partial=partial, error=str(error), traceback=traceback.format_exc()
            ),
        )
        expected = 2 if case == "late_CaATP_underflow" else 0
        assert len(completed) == expected
        strict = case not in ("first_gene_negative", "second_gene_negative")
        if case == "bootstrap_zero_screen":
            assert (
                partial["stage"] == "bootstrap" and not captured["bootstrap"]["all_fields_finite"]
            )
            trial = partial["partial"]["rejected_trial"]
            exact(trial.values._asdict(), captured["bootstrap"]["environment"]["values"])
        elif case in ("CaATP_equilibrium_underflow", "late_CaATP_underflow"):
            phase = partial["calcium_failure"]["phase"]
            assert phase["helper"].source_completed and not phase["helper"].finite
            compare_calcium_native(
                phase, captured["calcium_rows"][len(completed)], helper_only=True
            )
        else:
            compare_calcium_native(partial["calcium"], captured["calcium_rows"][len(completed)])
            if not strict:
                assert (
                    captured["status"] == "source_refused"
                    and not partial["network"]["source_completed"]
                )
                exact(partial["network"], captured["history"][len(completed)]["network"])
            assert partial["material"]["frames"]
        for returned, source in zip(completed, captured["history"], strict=False):
            candidate, trial, feedback, phase, context = returned
            base.compare_native_material(trial, source)
            compare_calcium_native(phase, source["calcium"])
            exact(feedback, source["network"])
            exact(candidate.network.material.values._asdict(), source["candidate"])
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
        archive(tmp_path, case + "-raw-unexpected-complete", dict(parent=parent))
        raise AssertionError("Declared calcium or full-field raw limit was not reached")
    (folder / "raw-retention.json").write_text(
        json.dumps(
            dict(
                positive_credit=False,
                completed_calls=len(completed),
                native_status=captured["status"],
                strict_finite_guard_distinct_from_native_exception=strict,
                complete_native_raw_buffers_retained=True,
                complete_available_port_partial_retained=True,
                source_ER_disabled=True,
                physical_global_conservation_credit=False,
            ),
            indent=2,
        )
        + "\n"
    )


@pytest.mark.parametrize("dependency", fixtures.DEPENDENCIES)
def test_ecm_calcium_dependencies(tmp_path, dependency):
    inputs = fixtures.fixture()
    archive(tmp_path, dependency + "-baseline-inputs-before-constructor", inputs)
    try:
        binding = joined.bind(inputs)
        parent = joined.initialize(
            binding,
            after_cold=lambda value: archive(tmp_path, dependency + "-baseline-cold-return", value),
        )
    except Exception as error:
        archive(
            tmp_path,
            dependency + "-unexpected-valid-admission",
            dict(
                error=str(error),
                traceback=traceback.format_exc(),
                partial=getattr(error, "partial", None),
            ),
        )
        raise
    archive(tmp_path, dependency + "-valid-admission", dict(binding=binding, parent=parent))
    messages = dict(
        ER_requested="Native ordinary ER is disabled; no forced Ca_dyn or missing kinetics",
        ER_kinetics_injected="Derive native maintained pools, Km, blocks and rate-cache absence",
        maintained_override="Derive native maintained pools, Km, blocks and rate-cache absence",
        missing_Ca="Require a real Ca+2 ion role and complete material arrays",
        wrong_Ca_valence="Require a real Ca+2 ion role and complete material arrays",
        changed_rate_cache=(
            "Require actual rate-cache absence or complete immutable source-written rate"
        ),
        invented_rate_presence=(
            "Require actual rate-cache absence or complete immutable source-written rate"
        ),
        wrong_clock="Require original normal time vector and accumulated material dt",
        varying_dt="Require one configured dt for the actual normal source clock",
        supplied_old_field="Old electric fields must come from the actual preceding field stage",
        negative_alpha="Require finite nonnegative configured native alpha_Ca",
        missing_network_cache="Require complete ECM GRN owner cache",
    )
    if dependency in (
        "changed_rate_cache",
        "invented_rate_presence",
        "wrong_clock",
        "missing_network_cache",
    ):
        rate, clock, net = parent.rate_cache, parent.clock, parent.network
        if dependency == "changed_rate_cache":
            rate = joined.RateCache(True, np.ones(9))
        elif dependency == "invented_rate_presence":
            rate = joined.RateCache(True, ions.freeze(np.zeros(9)))
        elif dependency == "wrong_clock":
            clock = joined.Clock(parent.clock.source_times_s, 1, 0.0)
        else:
            cached = ions.data(parent.network.network_cache)
            cached["kind"] = "missing"
            net = joined.network._state(
                binding, parent.network.material, cached, parent.network.controls
            )
        changed = joined.joined_state(binding, net, parent.field, rate, clock)
        archive(
            tmp_path,
            dependency + "-malformed-parent-before-call",
            dict(inputs=inputs, parent=changed),
        )
        with pytest.raises((ValueError, joined.CalciumJoinRejected)) as caught:
            joined.advance(binding, changed)
        archive(
            tmp_path, dependency + "-partial", dict(partial=getattr(caught.value, "partial", None))
        )
    else:
        changed = copy.deepcopy(inputs)
        if dependency == "ER_requested":
            changed["calcium"]["Ca_dyn"] = True
        elif dependency == "ER_kinetics_injected":
            changed["calcium"]["serca_max"] = 1e-8
        elif dependency == "maintained_override":
            changed["calcium"]["cATP"] = 2.0
        elif dependency in ("missing_Ca", "wrong_Ca_valence"):
            roles = changed["field"]["definition"]["environment_geometry_definition"][
                "current_definition"
            ]["ions"]
            i = roles["ids"].index("Ca")
            if dependency == "missing_Ca":
                roles["ids"].pop(i)
                roles["valence"].pop(i)
            else:
                roles["valence"][i] = 1.0
        elif dependency == "varying_dt":
            changed["field"]["steps"][1]["material"]["dt_s"] *= 2
        elif dependency == "supplied_old_field":
            changed["field"]["steps"][0]["material"]["electric_x_source"] = [[0.0]]
        else:
            changed["calcium"]["alpha_Ca"] = -1.0
        archive(tmp_path, dependency + "-malformed-inputs-before-call", changed)
        with pytest.raises(ValueError) as caught:
            joined.bind(changed)
    leaf = caught.value
    while leaf.__cause__ is not None:
        leaf = leaf.__cause__
    archive(tmp_path, dependency + "-refusal", dict(type=type(leaf).__name__, message=str(leaf)))
    assert type(leaf) is ValueError and str(leaf) == messages[dependency]
    (root(tmp_path) / ("dependency-" + dependency + ".json")).write_text(
        json.dumps(
            dict(
                baseline_admitted=True,
                intended_failure_reached=True,
                actual_leaf_type=type(leaf).__name__,
                expected_message=messages[dependency],
                actual_message=str(leaf),
                source_failure_credit=False,
                source_ER_disabled=True,
            ),
            indent=2,
        )
        + "\n"
    )


@pytest.fixture(scope="module", autouse=True)
def runtime_receipt(tmp_path_factory):
    row = inventory()
    if cpu := os.environ.get("CELLS_ECM_CALCIUM_CPU"):
        assert row["measured_cpu_affinity"] == [int(cpu)]
    folder = root(tmp_path_factory.getbasetemp())
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "runtime.json").write_text(json.dumps(row, indent=2) + "\n")
