"""Exact source epochs, complete parents and fixed conditional composition checks."""

import os
import subprocess
import sys
import traceback
from copy import deepcopy
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest

from cells.processes import betse_normal_ecm_mechanics_join as joined
from cells.processes import betse_normal_ion_join as ions
from tests.unit import test_betse_normal_ecm_field_join as established
from validation.betse import betse_mechanics_join_checks as mechanical_checks
from validation.betse import betse_normal_ecm_mechanics_join_boundaries as boundaries
from validation.betse import betse_normal_ecm_mechanics_join_checks as checks
from validation.betse import betse_normal_ecm_mechanics_join_fixtures as fixtures
from validation.betse import betse_normal_ecm_mechanics_join_runtime as runtime


def persist(root, name, value):
    runtime.write(root / (name + ".json"), value)
    runtime.write(root / (name + "-types.json"), runtime.typed_inventory(value))
    with (root / (name + ".npz")).open("xb") as stream:
        np.savez_compressed(stream, **runtime.arrays(value))
        stream.flush()
        os.fsync(stream.fileno())


def child(root, mode):
    with (root / (mode + ".stdout.log")).open("x") as stream:
        subprocess.run(
            [
                sys.executable,
                "-B",
                "-m",
                "validation.betse.betse_normal_ecm_mechanics_join_replay",
                "--mode",
                mode,
                "--case",
                root.name,
                "--source",
                str(root),
            ],
            stdout=stream,
            stderr=subprocess.STDOUT,
            check=True,
            timeout=400,
        )


def run(inputs, root):
    records, points = {}, []

    def observer(name, value):
        persist(root, name, value)
        records[name] = value
        kind = (
            "cold"
            if name == "cold-input"
            else "field"
            if name == "bootstrap-input"
            else (
                name.split("-")[-2]
                if name.startswith("step-") and name.endswith("-input")
                else None
            )
        )
        if kind in ("cold", "field", "material", "network", "mechanics"):
            points.append(dict(name=name, kind=kind))

    try:
        binding = joined.bind(inputs)
        persist(root, "binding", binding)
        parent = joined.initialize(binding, observer=observer)
        states, contexts = [parent], []
        for _ in range(3):
            original = ions.digest(parent)
            parent, context = joined.advance(binding, parent, observer=observer)
            assert original == ions.digest(states[-1])
            contexts.append(context)
            states.append(parent)
        return binding, states, contexts, records
    except Exception as error:
        persist(
            root,
            "failure",
            dict(
                type=type(error).__name__,
                reason=str(error),
                traceback=traceback.format_exc(),
                partial=getattr(error, "partial", None),
                partial_retained=getattr(error, "partial", None) is not None,
            ),
        )
        raise
    finally:
        runtime.write(root / "points-index.json", points)


def references(root, name):
    return [
        runtime.read(
            root / "references" / name / ("projected-reference-" + str(precision) + ".json")
        )
        for precision in (100, 160)
    ]


def mechanical_history(contexts):
    return [
        dict(
            frames=runtime.plain(ctx["mechanics_trial"].frames),
            auxiliaries=runtime.plain(ctx["mechanics_trial"].auxiliaries),
            candidate=runtime.plain(ctx["mechanics_trial"].candidate.cache),
            sample=None,
            carried_cache=runtime.plain(ctx["mechanics_trial"].candidate.cache),
        )
        for ctx in contexts
    ]


def complete_case(inputs, root, *, corruption_baseline=False):
    runtime.write(root / "inputs.json", inputs)
    before = deepcopy(inputs)
    binding, states, contexts, records = run(inputs, root)
    child(root, "produce-native")
    proof = runtime.read(root / "native/proof.json")
    child(root, "produce-references")
    # Every outgoing raw object and both precision references precede gates.
    reports, mechanics_reports = [], []

    def save(name, rows):
        persist(root, name, rows)
        reports.append(name)
        computed = checks.verify_rows(runtime.plain(rows))
        runtime.write(root / (name + "-recomputed-errors.json"), computed)
        checks.assert_rows(computed)

    native = proof["ionic_field"]
    assert proof["complete_source_condition_met"] and proof["RNG_unchanged"]
    assert not native["warnings"] and not proof["mechanics"]["warnings"]
    assert inputs == before
    established.exact(states[0].field.network.network_cache, native["cold_cache"])
    established.exact(
        states[0].field.network.material.values._asdict(), native["bootstrap"]["candidate"]
    )
    save(
        "comparison-cold",
        established.legacy.compare_cold(
            binding.field, records["cold-output"], *references(root, "cold-input")
        ),
    )
    save(
        "comparison-bootstrap",
        established.compare_field(
            binding.field, states[0].field.field, *references(root, "bootstrap-input")
        ),
    )
    for index, (state, context, captured) in enumerate(
        zip(states[1:], contexts, native["history"], strict=True)
    ):
        stem = "step-" + str(index)
        established.exact(records[stem + "-material-input"], captured["material_before"])
        established.exact(records[stem + "-network-input"], captured["network"]["before"])
        established.exact(records[stem + "-field-input"], captured["field"]["before"])
        established.compare_native_material(context["material_trial"], captured)
        established.exact(context["network_trace"], captured["network"])
        established.exact(state.field.network.network_cache, captured["post_material_cache"])
        established.exact(state.field.network.material.values._asdict(), captured["candidate"])
        for section, value in established.field_output(state.field.field).items():
            established.exact(value, captured["field"][section])
        boundaries.assert_identical(
            runtime.plain(context["mechanics_input"]), proof["mechanics_inputs"]["steps"][index]
        )
        save(
            "comparison-material-" + str(index),
            established.compare_material(
                context["material_trial"], *references(root, stem + "-material-input")
            ),
        )
        save(
            "comparison-network-" + str(index),
            established.legacy.compare_local(
                context["network_trace"], *references(root, stem + "-network-input")
            ),
        )
        save(
            "comparison-field-" + str(index),
            established.compare_field(
                binding.field, state.field.field, *references(root, stem + "-field-input")
            ),
        )
        lower, target = references(root, stem + "-mechanics-input")
        actual = mechanical_history([context])
        report = dict(
            actual=mechanical_checks.compare(actual, lower["history"]),
            resolution=mechanical_checks.compare(lower["history"], target["history"]),
            native=mechanical_checks.compare(
                actual, [proof["mechanics"]["history"][index]], native=True
            ),
        )
        name = "comparison-mechanics-" + str(index)
        persist(root, name, report)
        mechanics_reports.append(name)
        mechanical_checks.assert_compare(report["actual"])
        mechanical_checks.assert_compare(report["resolution"], resolution=True)
        mechanical_checks.assert_compare(report["native"])
    runtime.write(root / "comparison-index.json", reports)
    runtime.write(root / "mechanics-comparison-index.json", mechanics_reports)
    runtime.write(
        root / ("baseline-result.json" if corruption_baseline else "result.json"),
        dict(
            status="passed_conditional_source_composition",
            source_calls=3,
            mechanics_points=3,
            independently_carried_trajectory=False,
            source_display_or_physical_rebuild=False,
            original_material_panel_status="failed_39_of_40",
        ),
    )
    return binding, states, contexts, proof


@pytest.mark.parametrize("case", fixtures.CASES)
def test_complete_native_epochs_and_conditional_references(case):
    complete_case(fixtures.fixture(case), runtime.root(case))


@pytest.mark.parametrize("case", fixtures.REFUSALS)
def test_geometry_pressure_field_and_policy_prerequisites_refuse(case):
    inputs = fixtures.fixture()
    geometry = inputs["mechanics_definition"]["geometry"]
    if case == "foreign-cell-owners":
        geometry["cell_ids"][0] = "foreign"
    elif case == "foreign-membrane-owners":
        geometry["layout"]["membrane_ids"][0] = "foreign"
    elif case == "changed-cell-measure":
        geometry["layout"]["cell_volume_m3"][0] *= 2
    elif case == "changed-membrane-measure":
        geometry["layout"]["membrane_area_m2"][0] *= 2
    elif case == "changed-centres":
        geometry["layout"]["centers_m"][0][0] += 0.1
    elif case == "changed-environment-map":
        geometry["cell_to_environment"][0] = 1
        geometry["environment_average"][0] = [
            float(i == 1) for i in range(len(geometry["environment_ids"]))
        ]
    elif case == "wrong-pressure-stage":
        inputs["pressure_drives"][0]["stage"] = "after_voltage"
    elif case == "invented-zero-baseline-pressure":
        inputs["pressure_drives"][0]["P_mod_Pa"][0] = 1.0
    elif case == "wrong-phase-dt":
        inputs["mechanics_definition"]["parameters"]["dt_s"] *= 2
    elif case == "sampled-display":
        inputs["mechanics_definition"]["policy"]["display_regime"] = "global_quartic_conditional"
    elif case == "enabled-flow":
        inputs["mechanics_definition"]["policy"]["fluid_flow"] = True
    elif case == "dynamic-deformation":
        inputs["mechanics_definition"]["policy"]["td_deform"] = True
    elif case == "FAST":
        inputs["mechanics_definition"]["policy"]["solver"] = "FAST"
    elif case == "late-pressure-counter":
        inputs["pressure_drives"][0]["source_step"] = 1
    elif case == "nonzero-disabled-flow-drive":
        inputs["field_inputs"]["steps"][0]["material"]["velocity_x_m_s"][0][0] = 1.0
    root = runtime.root("refusal-" + case)
    runtime.write(root / "inputs.json", inputs)
    with pytest.raises((ValueError, AssertionError)) as error:
        binding = joined.bind(inputs)
        parent = joined.initialize(binding, observer=lambda name, value: persist(root, name, value))
        if case == "foreign-mechanics-parent":
            other = deepcopy(inputs)
            other["mechanics_definition"]["provenance"]["geometry_epoch"] = "foreign"
            foreign = joined.bind(other)
            parent = joined.state(
                binding,
                parent.field,
                joined.mechanics.state(foreign.mechanics, other["mechanics_initial"]),
            )
        elif case == "changed-prior-field":
            bad = replace(parent.field.field, identity="changed-field-seal")
            changed = joined.field.state(binding.field, parent.field.network, bad)
            parent = joined.state(binding, changed, parent.mechanics)
        persist(root, "attempted-parent", parent)
        joined.advance(binding, parent)
    runtime.write(
        root / "result.json", dict(status="correctly_refused", case=case, reason=str(error.value))
    )


@pytest.mark.parametrize("case", fixtures.RAW_CASES)
def test_complete_partial_source_failures_are_retained(case):
    inputs = fixtures.raw_fixture(case)
    root = runtime.root(case)
    runtime.write(root / "inputs.json", inputs)
    with pytest.raises(joined.CompositionRejected):
        run(inputs, root)
    child(root, "produce-native")
    proof = runtime.read(root / "native/proof.json")
    failure = runtime.read(root / "failure.json")
    assert failure["partial_retained"] and proof["RNG_unchanged"]
    if case == "network-negative":
        assert proof["ionic_field"]["failure"] is not None and proof["mechanics"] is None
    else:
        assert failure["partial"]["mechanics_failure"] is not None
        assert proof["mechanics"] is not None
    runtime.write(
        root / "result.json", dict(status="raw_source_boundary_retained", accuracy_credit=False)
    )


@pytest.mark.parametrize("case", (*fixtures.CORRUPTIONS, *fixtures.PHASE_CORRUPTIONS))
def test_wrong_mechanics_outputs_or_source_epochs_are_rejected(case):
    inputs = fixtures.fixture()
    root = runtime.root("corruption-" + case)
    _, _, contexts, proof = complete_case(inputs, root, corruption_baseline=True)
    if case in fixtures.PHASE_CORRUPTIONS:
        expected = proof["mechanics_inputs"]["steps"][0]
        corrupted = deepcopy(expected)
        row = proof["ionic_field"]["history"][0]
        if case == "end-field-for-previous-field":
            corrupted["electric_field_V_m"] = [
                list(v)
                for v in zip(*row["field"]["voltage"]["values"]["cell_field_xy_V_m"], strict=True)
            ]
        else:
            corrupted["primary_cell_mM"] = deepcopy(row["material_candidate"]["cell_mol_m3"])
        runtime.write(
            root / "corruption.json",
            dict(kind="phase-parent", corrupted=corrupted, native_expected=expected),
        )
        with pytest.raises(AssertionError):
            boundaries.assert_identical(corrupted, expected)
    else:
        actual = mechanical_history(contexts)
        corrupted = mechanical_checks.corrupt(actual, case)
        runtime.write(
            root / "corruption.json",
            dict(kind="mechanics-output", original=actual, corrupted=corrupted),
        )
        target = [
            references(root, "step-" + str(i) + "-mechanics-input")[0]["history"][0]
            for i in range(3)
        ]
        report = mechanical_checks.compare(corrupted, target)
        persist(root, "corruption-comparison", report)
        assert report["maximum_error_over_budget"] > 1
        with pytest.raises(AssertionError):
            mechanical_checks.assert_compare(report)
    runtime.write(root / "corruption-result.json", dict(status="correctly_rejected", case=case))
    runtime.write(
        root / "result.json",
        dict(
            status="correctly_rejected", case=case, baseline_is_not_an_additional_positive_case=True
        ),
    )


def test_protocol_has_exact_phase_order_and_closed_display_gap():
    root = runtime.root("source-protocol")
    path = (
        Path(__file__).resolve().parents[2]
        / "validation/betse/betse_normal_ecm_mechanics_join_protocol.json"
    )
    protocol = runtime.read(path)
    runtime.write(root / "protocol.json", protocol)
    assert protocol["scope"]["old_field_current_post_GRN_concentrations"]
    assert protocol["scope"]["sampled_display_admitted"] is False
    assert protocol["scope"]["physical_seed_or_geometry_claim"] is False
    assert protocol["scope"]["independently_carried_trajectory"] is False
    runtime.write(root / "result.json", dict(status="exact_reached_conditional_scope"))
