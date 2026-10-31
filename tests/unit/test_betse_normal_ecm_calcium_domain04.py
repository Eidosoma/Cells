"""Prospective full calcium roster and exact-input observed floating-point raw history."""

import hashlib
import json
import subprocess
import sys
import traceback
from pathlib import Path

import numpy as np
import pytest

from tests.unit import test_betse_normal_ecm_calcium_join as base
from validation.betse import betse_normal_ecm_calcium_domain04_fixtures as fixtures
from validation.betse import betse_normal_ecm_calcium_domain04_reference as chemistry

joined, ions, field = base.joined, base.ions, base.base
exact, archive = base.exact, base.archive


@pytest.mark.parametrize("case", fixtures.CASES)
def test_calcium_domain04_positive(tmp_path, case):
    base.test_ecm_calcium_field_history(tmp_path, case)


@pytest.mark.parametrize("case", fixtures.RAW_CASES)
def test_calcium_domain04_raw(tmp_path, case):
    base.test_ecm_calcium_raw_partial(tmp_path, case)


@pytest.mark.parametrize("dependency", fixtures.DEPENDENCIES)
def test_calcium_domain04_dependencies(tmp_path, dependency):
    base.test_ecm_calcium_dependencies(tmp_path, dependency)


def chemistry_references(folder, actual_native_before):
    folder.mkdir(parents=True, exist_ok=False)
    # Retain every read value exactly; do not sanitize any source-consumed input.
    projected = {key: actual_native_before[key] for key in chemistry.CHEMISTRY_INPUT_KEYS}
    projected["values_before"] = {
        key: actual_native_before["values_before"][key] for key in chemistry.CHEMISTRY_VALUE_KEYS
    }
    text = (
        json.dumps(field.legacy.old.old.plain(ions.data(projected)), indent=2, allow_nan=False)
        + "\n"
    )
    (folder / "inputs.json").write_text(text)
    answers = []
    for level in (1, 2):
        out = folder / ("reference-" + str(level) + ".json")
        with (folder / ("reference-" + str(level) + ".stdout.log")).open("x") as stream:
            subprocess.run(
                [
                    sys.executable,
                    "-B",
                    "-m",
                    "validation.betse.betse_normal_ecm_calcium_domain04_reference",
                    "--inputs",
                    str(folder / "inputs.json"),
                    "--output",
                    str(out),
                    "--refinement",
                    str(level),
                ],
                check=True,
                timeout=180,
                stdout=stream,
                stderr=subprocess.STDOUT,
            )
        row = json.loads(out.read_text())
        assert row["production_imports_denied"] and not row["loaded_production_modules"]
        assert set(row["runtime"]) == {
            "python",
            "measured_cpu_affinity",
            "executable",
            "loaded_files",
            "modules_without_files",
        }
        assert row["runtime"]["loaded_files"]
        assert row["decimal_precision"] == (100 if level == 1 else 160)
        assert row["carried_reference_forms"] == row["transport_evaluations"] == 0
        assert row["complete_network_return_predicted"] is False
        answers.append(row)
    return answers


def compare_chemistry_prefix(feedback, lower, target):
    rows, add = field.legacy.comparisons()
    for key in ("growth_rates", "reaction_rates", "all_rates"):
        wanted = np.asarray(target["rhs"][key])
        add(
            "rhs/" + key,
            feedback["rhs"][key],
            wanted,
            lower["rhs"][key],
            2e-14 + 5e-12 * abs(wanted),
            "unchanged GRN RHS budget",
        )
    core = feedback["cache_after"]["wire"]["core_fields"]
    add(
        "delta",
        core["delta_conc"],
        target["delta_conc"],
        lower["delta_conc"],
        6e-14 + 5e-12 * np.asarray(target["delta_gross"]),
        "unchanged GRN delta budget",
    )
    before = feedback["before"]
    n, m = len(before["molecular_geometry"]["cell_volume_m3"]), len(before["gap_open"])
    e = len(before["values_before"]["environment_mol_m3"][0])
    factor = 128 * np.finfo(float).eps * (len(before["ion_ids"]) + 2 + n + m + e + 64)
    commits = [
        row
        for row in feedback["molecule_frames"]
        if row["stage"] == "chemical_commit" and row["species"] == "X"
    ]
    assert len(commits) == 1
    observed = commits[0]["cache"]["wire"]["molecule_fields"]["X"]["c_cells"]
    add(
        "X/chemical_commit",
        observed,
        target["chemical_commit"]["X"],
        lower["chemical_commit"]["X"],
        3e-13 + factor * np.asarray(target["chemical_gross"]["X"]),
        "unchanged GRN concentration/gross budget",
    )
    return rows


def compare_complete(
    binding, parent, returned, native_call, observed, answers, tmp_path, case, index, point
):
    candidate, trial, feedback, phase, context = returned
    exact(observed["material"], native_call["material_before"])
    exact(observed["calcium"], native_call["calcium"]["before"])
    exact(observed["network"], native_call["network"]["before"])
    exact(observed["field"], native_call["field"]["before"])
    field.compare_native_material(trial, native_call)
    exact(feedback, native_call["network"])
    base.compare_calcium_native(phase, native_call["calcium"])
    exact(ions.data(candidate.rate_cache), native_call["rate_cache_after"])
    exact(ions.data(parent.clock), native_call["clock_before"])
    exact(ions.data(candidate.clock), native_call["clock_after"])
    exact(candidate.network.network_cache, native_call["post_material_cache"])
    exact(context["material_parent"].network_cache, native_call["post_material_cache"])
    exact(candidate.network.material.values._asdict(), native_call["candidate"])
    for section, value in field.field_output(candidate.field).items():
        exact(value, native_call["field"][section])
    for mode, rows in (
        ("material", field.compare_material(trial, *answers["material"])),
        ("calcium", base.compare_calcium(phase, *answers["calcium"])),
        ("network", field.legacy.compare_local(feedback, *answers["network"])),
        ("field", field.compare_field(binding, candidate.field, *answers["field"])),
    ):
        base.check(tmp_path, case + "-domain-" + mode + "-errors-" + str(index), point / mode, rows)


@pytest.mark.parametrize("case", fixtures.RAW_DOMAIN_CASES)
def test_calcium_domain04_observed_history(tmp_path, case):
    inputs = fixtures.raw_domain_fixture(case)
    prep = base.root(tmp_path) / ("preparation-" + case)
    prep.mkdir(parents=True, exist_ok=False)
    original = (
        Path(fixtures.__file__)
        .with_name("betse_normal_ecm_calcium_domain04_negative_genes.json")
        .read_bytes()
    )
    assert hashlib.sha256(original).hexdigest() == fixtures.SAVED_INPUT_SHA256
    (prep / "inputs-before-constructor.json").write_bytes(original)
    archive(tmp_path, case + "-domain-original-input", inputs)
    cold_input = field.cold_inputs(inputs["field"])
    cold_input.update(
        calcium_configuration=inputs["calcium"], bootstrap_dt_s=inputs["field"]["bootstrap"]["dt_s"]
    )
    cold = base.references(prep / "cold", cold_input)
    cold_returns, bootstrap = [], []

    def after_cold(value):
        archive(tmp_path, case + "-domain-cold-return", value)
        cold_returns.append(value)

    def before_bootstrap(value):
        bootstrap.extend(base.references(prep / "bootstrap", value))

    parent = None
    try:
        binding = joined.bind(inputs)
        parent = joined.initialize(binding, after_cold=after_cold, before_field=before_bootstrap)
        archive(tmp_path, case + "-domain-bootstrap-return", parent)
    except Exception as error:
        archive(
            tmp_path,
            case + "-domain-constructor-refusal",
            dict(
                parent=parent,
                error=str(error),
                partial=getattr(error, "partial", None),
                traceback=traceback.format_exc(),
            ),
        )
        raise
    folder, captured = base.isolated(tmp_path, inputs)
    assert captured["status"] == "source_refused" and len(captured["history"]) == 3
    assert [row["source_completed"] for row in captured["history"]] == [True, True, False]
    assert captured["failure"]["type"] == "BetseSimUnstableException"
    assert captured["failure"]["stage"] == "material_network"
    assert "no_negs" in captured["failure"]["traceback"]
    assert len(cold_returns) == 1 and len(bootstrap) == 2
    saved_cold = cold_returns[0]
    exact(saved_cold["network"].network_cache, captured["cold_cache"])
    exact(saved_cold["network"].material.values._asdict(), captured["cold_material"])
    exact(saved_cold["policy"], captured["cold_policy"])
    base.check(
        tmp_path,
        case + "-domain-cold-errors",
        prep / "cold",
        base.compare_cold(binding, saved_cold, *cold),
    )
    exact(parent.field.before, captured["bootstrap"]["before"])
    for section, value in field.field_output(parent.field).items():
        exact(value, captured["bootstrap"][section])
    exact(parent.network.material.values._asdict(), captured["bootstrap"]["candidate"])
    base.check(
        tmp_path,
        case + "-domain-bootstrap-errors",
        prep / "bootstrap",
        field.compare_field(binding, parent.field, *bootstrap),
    )
    completed = []
    for index in range(2):
        point = prep / ("point-" + str(index))
        point.mkdir()
        answers = {name: [] for name in ("material", "calcium", "network", "field")}
        observed = {}

        def before(name, index=index, point=point, observed=observed, answers=answers):
            def callback(value):
                archive(tmp_path, case + "-domain-actual-" + name + "-input-" + str(index), value)
                observed[name] = ions.data(value)
                answers[name].extend(base.references(point / name, value))

            return callback

        old_digest = ions.digest(parent)
        try:
            returned = joined.advance(
                binding,
                parent,
                before_material=before("material"),
                before_calcium=before("calcium"),
                before_network=before("network"),
                before_field=before("field"),
            )
            archive(
                tmp_path,
                case + "-domain-complete-return-" + str(index),
                dict(parent=parent, returned=returned),
            )
        except Exception as error:
            archive(
                tmp_path,
                case + "-domain-unexpected-prefix-refusal-" + str(index),
                dict(
                    parent=parent,
                    error=str(error),
                    partial=getattr(error, "partial", None),
                    traceback=traceback.format_exc(),
                ),
            )
            raise
        assert old_digest == ions.digest(parent) and all(len(v) == 2 for v in answers.values())
        compare_complete(
            binding,
            parent,
            returned,
            captured["history"][index],
            observed,
            answers,
            tmp_path,
            case,
            index,
            point,
        )
        completed.append(returned)
        parent = returned[0]
    native_failed = captured["history"][2]
    assert (
        native_failed["material_candidate"]
        is native_failed["post_material_cache"]
        is native_failed["field"]
        is None
    )
    assert native_failed["calcium"]["helper"]["finite"] is False
    assert native_failed["calcium"]["helper"]["source_completed"] is True
    # First nonfinite source store is the earlier ordinary Na junction flux.
    first = next(
        (i, f)
        for i, f in enumerate(native_failed["frames"])
        if any(not np.isfinite(value).all() for value in f["values"].values())
    )
    assert first[0] == 4 and first[1]["stage"] == "junction_flux" and first[1]["ion_id"] == "Na"
    ids = inputs["field"]["definition"]["environment_geometry_definition"]["current_definition"][
        "ions"
    ]["ids"]
    bad = np.flatnonzero(
        ~np.isfinite(first[1]["values"]["junction_flux_mol_m2_s"][ids.index("Na")])
    )
    np.testing.assert_array_equal(bad, [7, 8])
    native_net = native_failed["network"]
    assert not native_net["source_completed"] and native_net["completed_transports"] == 1
    assert native_net["molecule_frames"][-1]["stage"] == "transport_after"
    assert native_net["molecule_frames"][-1]["species"] == "X"
    mol = native_net["cache_after"]["wire"]["molecule_fields"]["X"]
    assert np.isnan(mol["c_cells"]).any() or np.isnan(mol["c_env"]).any()
    archive(tmp_path, case + "-domain-native-before-failed-chemistry", native_net["before"])
    chemistry_answers = chemistry_references(prep / "failed-third-chemistry", native_net["before"])
    base.check(
        tmp_path,
        case + "-domain-failed-chemistry-prefix-errors",
        prep / "failed-third-chemistry",
        compare_chemistry_prefix(native_net, *chemistry_answers),
    )
    observed = {}

    def retain(name):
        def callback(value):
            observed[name] = ions.data(value)
            archive(tmp_path, case + "-domain-third-" + name + "-input", value)

        return callback

    old_digest = ions.digest(parent)
    try:
        returned = joined.advance(
            binding,
            parent,
            before_material=retain("material"),
            before_calcium=retain("calcium"),
            before_network=retain("network"),
            before_field=retain("field"),
        )
    except joined.CalciumJoinRejected as error:
        partial = error.partial
        archive(
            tmp_path,
            case + "-domain-complete-third-refusal",
            dict(
                parent=parent, partial=partial, error=str(error), traceback=traceback.format_exc()
            ),
        )
        assert partial["stage"] == "material_calcium_network"
        assert partial["network"] is None and partial["calcium"] is None
        phase = partial["calcium_failure"]["phase"]
        assert phase["helper"].source_completed and not phase["helper"].finite
        base.compare_calcium_native(phase, native_failed["calcium"], helper_only=True)
        exact(observed["material"], native_failed["material_before"])
        exact(observed["calcium"], native_failed["calcium"]["before"])
        assert set(observed) == {"material", "calcium"}
        frames = partial["material"]["frames"]
        handler_index = next(
            i
            for i, frame in enumerate(native_failed["frames"])
            if frame["stage"] == "calcium_handler"
        )
        shared_prefix = native_failed["frames"][:handler_index]
        assert frames and len(frames) == len(shared_prefix)
        for actual, wanted in zip(frames, shared_prefix, strict=True):
            assert (actual["stage"], actual["ion_id"]) == (wanted["stage"], wanted["ion_id"])
            exact(actual["values"], wanted["values"])
        assert all(f["stage"] != "calcium_handler" for f in frames)
        assert parent.network.material.step_index == parent.clock.call_index == 2
        assert old_digest == ions.digest(parent)
        leaf = error
        while leaf.__cause__ is not None:
            leaf = leaf.__cause__
        assert (
            type(leaf) is ValueError
            and str(leaf) == "Nonfinite actual CaATP helper trial; stricter finite admission"
        )
    except Exception as error:
        archive(
            tmp_path,
            case + "-domain-unexpected-third-refusal",
            dict(
                parent=parent,
                error=str(error),
                partial=getattr(error, "partial", None),
                traceback=traceback.format_exc(),
            ),
        )
        raise
    else:
        archive(tmp_path, case + "-domain-unexpected-third-return", returned)
        raise AssertionError("Exact original unstable domain unexpectedly completed")
    (folder / "raw-domain-retention.json").write_text(
        json.dumps(
            dict(
                positive_credit=False,
                case_id=case,
                input_sha256=fixtures.SAVED_INPUT_SHA256,
                input_retained_exactly=True,
                context="negatively_charged_gene_products",
                native_completed_calls=2,
                port_completed_calls=2,
                native_history_records=3,
                first_nonfinite_frame=4,
                first_nonfinite_stage="junction_flux",
                first_nonfinite_ion="Na",
                first_nonfinite_membrane_occurrences=[7, 8],
                native_stop="GRN_X_transport_no_negs_NaN",
                port_stop="existing_CaATP_finite_guard",
                distinct_native_port_stops=True,
                calcium_specific_cause_claim=False,
                cold_reference_forms=2,
                bootstrap_reference_forms=2,
                completed_prefix_reference_forms=16,
                failed_native_chemistry_reference_forms=2,
                total_fresh_reference_forms=22,
                carried_reference_forms=0,
                full_native_and_port_partials_retained=True,
                source_ER_disabled=True,
                native_full_history_accepted=False,
                physical_global_conservation_credit=False,
                dt_rates_coefficients_or_guards_changed=False,
            ),
            indent=2,
        )
        + "\n"
    )


@pytest.fixture(scope="module", autouse=True)
def runtime_receipt(tmp_path_factory):
    row = base.inventory()
    import os

    if cpu := os.environ.get("CELLS_ECM_CALCIUM_DOMAIN04_CPU"):
        assert row["measured_cpu_affinity"] == [int(cpu)]
    folder = base.root(tmp_path_factory.getbasetemp())
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "runtime.json").write_text(json.dumps(row, indent=2) + "\n")
