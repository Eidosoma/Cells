"""Ordinary pressure/steady mechanics and conditional sampled-display evidence."""

import os
from copy import deepcopy
from dataclasses import replace

import numpy as np
import pytest

from cells.processes import betse_mechanics_join as mechanics
from validation.betse import betse_mechanics_join_checks as checks
from validation.betse import betse_mechanics_join_fixtures as fixtures
from validation.betse import betse_mechanics_join_native as native
from validation.betse import betse_mechanics_join_reference as reference
from validation.betse import betse_mechanics_join_runtime as runtime


def persist(root, name, value):
    runtime.write(root / (name + ".json"), value)
    runtime.write(root / (name + "-types.json"), runtime.typed_inventory(value))
    with (root / (name + ".npz")).open("xb") as stream:
        np.savez_compressed(stream, **runtime.arrays(value))
        stream.flush()
        os.fsync(stream.fileno())


def observed(inputs, root):
    binding = mechanics.bind(inputs["definition"])
    persist(root, "binding", binding)
    parent = mechanics.state(binding, inputs["initial"])
    persist(root, "initial", parent)
    history = []
    for index, packet in enumerate(inputs["steps"]):
        try:
            trial = mechanics.step(binding, parent, packet)
        except mechanics.MechanicsRejected as error:
            if error.trial is not None:
                persist(root, "failed-trial", error.trial)
            runtime.write(root / "failure.json", dict(stage=error.stage, reason=str(error)))
            raise
        persist(root, "trial-" + str(index), trial)
        row = dict(
            frames=runtime.plain(trial.frames),
            auxiliaries=runtime.plain(trial.auxiliaries),
            candidate=runtime.plain(trial.candidate.cache),
            sample=None,
        )
        parent = trial.candidate
        if packet["sample"]:
            try:
                receipt, parent = mechanics.sample(
                    binding,
                    parent,
                    clock_s=packet["clock_s"],
                    postcommit_receipt=dict(
                        stage=mechanics.SAMPLE_STAGE,
                        state_identity=parent.identity,
                        geometry_epoch=inputs["definition"]["provenance"]["geometry_epoch"],
                        clock_s=packet["clock_s"],
                    ),
                )
            except Exception as error:
                persist(root, "failed-display-parent", parent)
                if getattr(error, "trial", None) is not None:
                    persist(root, "failed-display-witness", error.trial)
                runtime.write(
                    root / "display-failure.json",
                    dict(type=type(error).__name__, reason=str(error)),
                )
                raise
            persist(root, "sample-" + str(index), dict(receipt=receipt, candidate=parent))
            row["sample"] = dict(
                interpolation=runtime.plain(receipt["interpolation"]),
                vertices_m=runtime.plain(parent.cache["display_vertices_m"]),
                cell_centres_m=runtime.plain(parent.cache["display_centres_m"]),
            )
        row["carried_cache"] = runtime.plain(parent.cache)
        history.append(row)
    runtime.write(root / "actual-history.json", history)
    return binding, parent, history


def references(inputs, root):
    def retain(name, payload):
        runtime.write(root / (name + ".json"), payload)

    return (
        reference.evaluate(inputs, refinement=1, retain=retain),
        reference.evaluate(inputs, refinement=2, retain=retain),
    )


@pytest.mark.parametrize("case", fixtures.CASES)
def test_complete_ordinary_mechanics_and_sampled_display(case):
    inputs = fixtures.fixture(case)
    before = deepcopy(inputs)
    root = runtime.root(case)
    runtime.write(root / "inputs.json", inputs)
    binding, parent, history = observed(inputs, root)
    proof = native.evaluate(inputs)
    persist(root, "native-proof", proof)
    first, second = references(inputs, root)
    reports = dict(
        native=checks.compare(history, proof["history"], native=True),
        independent=checks.compare(history, first["history"]),
        resolution=checks.compare(first["history"], second["history"]),
        operators=checks.compare(
            dict(
                operators={
                    key: value
                    for key, value in binding.operators._asdict().items()
                    if key != "active"
                }
            ),
            dict(operators=first["operators"]),
        ),
    )
    runtime.write(root / "comparisons.json", reports)
    assert inputs == before
    assert proof["failure"] is None and not proof["warnings"] and proof["RNG_unchanged"]
    assert (
        not proof["flow_forced_on"]
        and not proof["timeDeform_executed"]
        and not proof["physical_world_rebuilt"]
    )
    assert (
        checks.stages(history) == checks.stages(proof["history"]) == checks.stages(first["history"])
    )
    for name, report in reports.items():
        checks.assert_compare(report, resolution=name == "resolution")
    checks.assert_controls(inputs, history)
    for spline in proof["spline_calls"]:
        assert all(len(knots) == 10 for knots in spline["knots"])
    np.testing.assert_array_equal(
        proof["physical_geometry"]["centres_m"],
        inputs["definition"]["geometry"]["layout"]["centers_m"],
    )
    np.testing.assert_array_equal(
        proof["physical_geometry"]["vertices_m"],
        inputs["definition"]["geometry"]["layout"]["vertices_m"],
    )
    assert parent.step_index == len(inputs["steps"])
    if case == "imported-display-cache":
        assert (
            inputs["initial"]["display_vertices_m"]
            != inputs["definition"]["geometry"]["layout"]["vertices_m"]
        )
        np.testing.assert_array_equal(
            proof["history"][0]["frames"][0]["cache"]["display_vertices_m"],
            inputs["initial"]["display_vertices_m"],
        )
        np.testing.assert_array_equal(
            proof["complete_native_objects"]["sim"].cellso.mem_verts,
            inputs["definition"]["geometry"]["layout"]["vertices_m"],
        )
    runtime.write(
        root / "result.json",
        dict(
            status="passed_conditional_ordinary_slice",
            source_calls=len(history),
            samples=sum(row["sample"] is not None for row in history),
            maximum_error_over_budget=reports["independent"]["maximum_error_over_budget"],
            flow_qualified=False,
            dynamic_deformation_qualified=False,
            physical_rebuild_or_energy_qualified=False,
        ),
    )


@pytest.mark.parametrize("case", fixtures.REFUSALS)
def test_policy_prerequisite_and_raw_partial_refusals(case):
    inputs = fixtures.fixture(
        "noecm-osmotic"
        if case.startswith("noecm-")
        else "sampled-display"
        if case in ("sample-without-barrier", "duplicate-sample")
        else "ordinary-osmotic"
    )
    root = runtime.root("refusal-" + case)
    if case == "enabled-flow":
        inputs["definition"]["policy"]["fluid_flow"] = True
    elif case == "dynamic-deformation":
        inputs["definition"]["policy"]["td_deform"] = True
    elif case == "fast-solver":
        inputs["definition"]["policy"]["solver"] = "FAST"
    elif case == "missing-seed-provenance":
        inputs["definition"]["provenance"].pop("graph_origin")
    elif case == "wrong-environment-map":
        inputs["definition"]["geometry"]["environment_average"][0][0] = 0.25
    elif case == "wrong-field-epoch":
        inputs["steps"][0]["receipt"]["geometry_epoch"] = "stale-epoch"
    elif case == "wrong-field-stage":
        inputs["steps"][0]["receipt"]["stage"] = "after_voltage_refresh"
    elif case == "wrong-dt":
        inputs["steps"][0]["dt_s"] *= 2
    elif case == "missing-electric-after-osmotic":
        inputs["steps"][0].pop("electric_field_V_m")
    elif case == "nonfinite-pressure-after-osmotic":
        inputs["steps"][0]["pressure_Pa"][0] = float("nan")
    elif case == "adaptive-display":
        inputs["definition"]["policy"]["display_regime"] = "adaptive_FITPACK"
    elif case == "noecm-permuted-map":
        geometry = inputs["definition"]["geometry"]
        count = len(geometry["environment_ids"])
        geometry["membrane_to_environment"] = list(reversed(range(count)))
        sm = np.asarray(geometry["layout"]["sum_membranes"], dtype=float)
        geometry["environment_average"] = (
            (sm / sm.sum(axis=1)[:, None]) @ np.eye(count)[geometry["membrane_to_environment"]]
        ).tolist()
    elif case == "noecm-wrong-environment-size":
        geometry = inputs["definition"]["geometry"]
        geometry["environment_ids"].append("extra-unowned-environment")
        for row in geometry["environment_average"]:
            row.append(0.0)
        inputs["initial"]["osmo_P_env"].append(0.0)
        for packet in inputs["steps"]:
            for group in ("primary", "molecule", "grn"):
                for row in packet[group + "_env_mM"]:
                    row.append(0.0)
    runtime.write(root / "inputs.json", inputs)
    error = None
    try:
        binding = mechanics.bind(inputs["definition"])
        parent = mechanics.state(binding, inputs["initial"])
        persist(root, "initial", parent)
        if case == "foreign-state":
            changed = deepcopy(inputs["definition"])
            changed["provenance"]["geometry_epoch"] = "foreign"
            parent = mechanics.state(mechanics.bind(changed), inputs["initial"])
            persist(root, "foreign-parent", parent)
        trial = mechanics.step(binding, parent, inputs["steps"][0])
        persist(root, "returned-trial", trial)
        if case in ("sample-without-barrier", "duplicate-sample"):
            parent = trial.candidate
            receipt = (
                {}
                if case == "sample-without-barrier"
                else dict(
                    stage=mechanics.SAMPLE_STAGE,
                    state_identity=parent.identity,
                    geometry_epoch=inputs["definition"]["provenance"]["geometry_epoch"],
                    clock_s=0.0,
                )
            )
            witness, parent = mechanics.sample(
                binding, parent, clock_s=0.0, postcommit_receipt=receipt
            )
            persist(root, "first-sample", dict(witness=witness, parent=parent))
            mechanics.sample(
                binding,
                parent,
                clock_s=0.0,
                postcommit_receipt=dict(
                    stage=mechanics.SAMPLE_STAGE,
                    state_identity=parent.identity,
                    geometry_epoch=inputs["definition"]["provenance"]["geometry_epoch"],
                    clock_s=0.0,
                ),
            )
    except mechanics.MechanicsRejected as caught:
        error = caught
        if caught.trial is not None:
            persist(root, "failed-trial", caught.trial)
        runtime.write(root / "refusal.json", dict(stage=caught.stage, reason=str(caught)))
    if case in fixtures.RAW_FAILURES:
        proof = native.evaluate(inputs)
        persist(root, "native-proof", proof)
        assert error is not None and error.trial is not None
        assert any(frame["stage"] == "osmotic_pressure" for frame in error.trial.frames)
        assert proof["history"][0]["frames"][1]["stage"] == "osmotic_pressure"
        if case == "missing-electric-after-osmotic":
            assert proof["failure"] and proof["failure"]["stage"] == "steady_deformation"
            comparison = checks.compare(
                runtime.plain(error.trial.candidate.cache),
                runtime.plain(proof["history"][0]["candidate"]),
            )
            runtime.write(root / "partial-cache-comparison.json", comparison)
            checks.assert_compare(comparison)
        else:
            assert proof["failure"] is None
            assert not np.isfinite(error.trial.candidate.cache["d_cells_x"]).all()
        assert proof["RNG_unchanged"]
    assert error is not None
    if case.startswith("noecm-"):
        assert error.stage == "binding" and "original membrane environment axis" in str(error)
    runtime.write(
        root / "result.json",
        dict(
            status="correctly_refused",
            case=case,
            raw_native_partial_retained=case in fixtures.RAW_FAILURES,
            source_nonfinite_finite_guard_difference_retained=case
            == "nonfinite-pressure-after-osmotic",
        ),
    )


@pytest.mark.parametrize("case", fixtures.CORRUPTIONS)
def test_independent_complete_output_rejects_corruption(case):
    source_case = (
        "sampled-display" if case == "stale-second-display-centres" else "ordinary-osmotic"
    )
    inputs = fixtures.fixture(source_case)
    root = runtime.root("corruption-" + case)
    runtime.write(root / "inputs.json", inputs)
    _, _, history = observed(inputs, root)
    first, second = references(inputs, root)
    changed = checks.corrupt(history, case)
    runtime.write(
        root / "complete-corruption.json", dict(case=case, original=history, corrupted=changed)
    )
    valid = checks.compare(history, first["history"])
    invalid = checks.compare(changed, first["history"])
    resolution = checks.compare(first["history"], second["history"])
    runtime.write(
        root / "comparisons.json", dict(valid=valid, invalid=invalid, resolution=resolution)
    )
    checks.assert_compare(valid)
    checks.assert_compare(resolution, resolution=True)
    assert invalid["maximum_error_over_budget"] > 1
    with pytest.raises(AssertionError):
        checks.assert_compare(invalid)
    runtime.write(root / "result.json", dict(status="correctly_rejected", corruption=case))


def test_complete_binding_cache_and_operator_owners_are_immutable():
    inputs = fixtures.fixture()
    root = runtime.root("immutable")
    runtime.write(root / "inputs.json", inputs)
    binding, parent, _ = observed(inputs, root)
    for value in (
        *binding.operators,
        binding.environment_average,
        binding.display_weights,
        *parent.cache.values(),
    ):
        with pytest.raises(ValueError):
            value.setflags(write=True)
    with pytest.raises(mechanics.MechanicsRejected, match="Three-call"):
        mechanics.step(binding, parent, inputs["steps"][0])
    changed = binding.operators.laplacian_inverse * 2
    forged = replace(
        binding, operators=binding.operators._replace(laplacian_inverse=mechanics.freeze(changed))
    )
    forged = replace(forged, identity=mechanics.digest(mechanics._binding_record(forged)))
    forged_parent = mechanics.state(forged, inputs["initial"])
    persist(root, "resealed-operator-and-state", dict(binding=forged, parent=forged_parent))
    with pytest.raises(mechanics.MechanicsRejected, match="Changed geometry/operators"):
        mechanics.step(forged, forged_parent, inputs["steps"][0])
    runtime.write(root / "result.json", dict(status="immutable_exact_owners_and_source_cap"))


def test_protocol_has_seeded_graph_and_disabled_ordinary_flow_provenance():
    root = runtime.root("source-protocol")
    protocol = runtime.read(native.PROTOCOL)
    runtime.write(root / "source-protocol.json", protocol)
    assert protocol["ordinary_policy"]["fluid_flow"] is False
    assert protocol["ordinary_policy"]["td_deform"] is False
    assert protocol["source_correspondence"]["seed_graph_build_unconditional"] is True
    assert (
        protocol["source_correspondence"]["sole_flow_enable_enclosing_method"]
        == "MasterOfGenes.run_core_sim"
    )
    assert protocol["source_correspondence"]["physical_deformWorld_calls"] == []
    assert not protocol["numerical_execution"] and not protocol["qualification_inherited"]
    runtime.write(root / "result.json", dict(status="explicit_ordinary_source_scope"))
