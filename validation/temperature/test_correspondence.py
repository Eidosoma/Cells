"""Pinned active-temperature probes; source coverage is not coupled validation."""

import ast
import json
import os
from pathlib import Path

import numpy as np
import pytest

from validation.temperature import checks, native, reference

P = native.PROTOCOL
CLASSES = [(module, name) for module, names in P["channel_classes"].items() for name in names]


def jsonable(value):
    if isinstance(value, dict):
        return {key: jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [jsonable(item) for item in value]
    if hasattr(value, "tolist"):
        return jsonable(value.tolist())
    if isinstance(value, float) and not np.isfinite(value):
        return None
    return value


def evidence(name, record, arrays=None):
    if directory := os.environ.get("CELLS_COMPONENT_EVIDENCE"):
        root = Path(directory) / "native-temperature"
        root.mkdir(parents=True, exist_ok=True)
        with (root / (name + ".json")).open("x") as handle:
            json.dump(jsonable(record), handle, indent=2, sort_keys=True, allow_nan=False)
            handle.write("\n")
        if arrays is not None:
            np.savez_compressed(root / (name + ".npz"), **arrays)


def numeric_equal(first, second):
    assert set(first) == set(second)
    for key in first:
        np.testing.assert_array_equal(first[key], second[key], strict=True)


@pytest.mark.parametrize("module,name", CLASSES)
def test_all_supported_class_bodies_keep_fixed_empirical_curves_across_declared_T(module, name):
    rows = []
    maximum = 0.0
    raw = {}
    for targeted in (False, True):
        baseline = native.channel_probe(
            module,
            name,
            configured_temperature_K=298.15,
            runtime_temperature_K=298.15,
            targeted=targeted,
        )
        for temperature in P["temperatures_K"]:
            for mode in ("reinitialize", "runtime_only"):
                row = native.channel_probe(
                    module,
                    name,
                    configured_temperature_K=temperature if mode == "reinitialize" else 298.15,
                    runtime_temperature_K=temperature,
                    targeted=targeted,
                )
                proof = checks.channel(row, P)
                maximum = max(maximum, proof["maximum_error_fraction"])
                row["mode"] = mode
                # Sites and immutable upstream files identify the complete body once.
                row["source"] = {
                    key: value for key, value in row["source"].items() if key != "code"
                }
                rows.append(dict(actual=row, reference=proof))
                numeric_equal(row["initialized"], baseline["initialized"])
                numeric_equal(row["before"], baseline["before"])
                numeric_equal(row["updated"], baseline["updated"])
                assert "T" not in row["parameter_reads"] and not row["runtime_temperature_reads"]
                for key, value in row["updated"].items():
                    raw[f"{len(rows)}_{key}"] = value
                    assert np.isfinite(value).all(), (name, key, temperature)
    evidence(
        "channel-" + name,
        dict(
            kind="channel",
            protocol=P,
            source=baseline["source"],
            rows=rows,
            maximum_error_fraction=maximum,
            native_temperature_direct_effect=False,
            indirect_voltage_calcium_feedback_excluded=True,
        ),
        raw,
    )
    assert len(rows) == 20 and maximum <= 1


@pytest.mark.parametrize("temperature", P["temperatures_K"])
@pytest.mark.parametrize("profile", P["constant_profiles"])
def test_literal_and_matched_ion_field_laws_keep_runtime_and_configured_T_distinct(
    temperature, profile
):
    row = native.transport_probe(temperature, profile)
    proof = checks.transport(row, P)
    evidence(
        f"transport-{profile}-{temperature}", dict(kind="transport", actual=row, reference=proof)
    )
    assert proof["maximum_error_fraction"] <= 1
    assert row["configured_temperature_K"] == 298.15
    if profile == "literal_native":
        assert abs(proof["reference"]["mixed_constant_relative_difference"]) > 1e-6
    else:
        assert abs(proof["reference"]["mixed_constant_relative_difference"]) < 1e-14


@pytest.mark.parametrize("temperature", P["temperatures_K"])
@pytest.mark.parametrize("profile", P["constant_profiles"])
@pytest.mark.parametrize("projection", (False, True))
def test_native_NaK_PMCA_SERCA_and_explicit_temperature_dependent_standard_conversion(
    temperature, profile, projection
):
    row = native.pump_probe(temperature, profile, common_pool_projection=projection)
    proof = checks.pumps(row, P)
    evidence(
        f"pumps-{profile}-{temperature}-{projection}",
        dict(kind="pumps", actual=row, reference=proof),
    )
    assert proof["maximum_error_fraction"] <= 1
    difference = proof["reference"]["calcium_vs_1M_pool_standard_difference_J_mol"]
    if projection:
        assert abs(difference) <= 3e-10
    else:
        assert difference == pytest.approx(proof["reference"]["RT_log_1000_J_mol"], rel=2e-14)


@pytest.mark.parametrize("temperature", P["temperatures_K"])
@pytest.mark.parametrize("profile", P["constant_profiles"])
def test_legacy_instantaneous_calcium_K_uses_runtime_T_as_a_separate_uncalled_function(
    temperature, profile
):
    row = native.legacy_probe(temperature, profile)
    proof = checks.legacy(row, P)
    evidence(f"legacy-{profile}-{temperature}", dict(kind="legacy", actual=row, reference=proof))
    assert proof["maximum_error_fraction"] <= 1
    assert row["runtime_temperature_reads"] == ("T",)
    assert row["runtime_callsite_found"] is False


@pytest.mark.parametrize("temperature", P["temperatures_K"])
@pytest.mark.parametrize("profile", P["constant_profiles"])
def test_actual_native_junction_caller_passes_configured_T_despite_changed_runtime_T(
    temperature, profile
):
    row = native.junction_caller_probe(temperature, profile)
    proof = checks.junction(row, P)
    changed = native.junction_caller_probe(
        temperature, profile, configured_temperature_K=temperature
    )
    changed_proof = checks.junction(changed, P)
    evidence(
        f"junction-{profile}-{temperature}",
        dict(
            kind="junction",
            actual=row,
            reference=proof,
            changed_configured=changed,
            changed_configured_reference=changed_proof,
        ),
    )
    assert max(proof["maximum_error_fraction"], changed_proof["maximum_error_fraction"]) <= 1
    assert row["passed_calls"][0]["temperature_argument_K"] == 298.15
    assert not row["runtime_temperature_reads"]
    if temperature != 298.15:
        assert not np.array_equal(row["flux"], changed["flux"])


@pytest.mark.parametrize("temperature", P["temperatures_K"])
@pytest.mark.parametrize("profile", P["constant_profiles"])
def test_actual_network_reaction_generators_use_J_per_mol_and_runtime_temperature(
    temperature, profile
):
    rows = native.reaction_generators(temperature, profile)
    proof = checks.reactions(rows, P)
    baseline = reference.reaction_equilibrium(-12000.0, 298.15, rows[0]["R"])
    evidence(
        f"reaction-{profile}-{temperature}",
        dict(
            kind="reactions",
            actual=rows,
            reference=proof,
            fixed_dimensionless_mu_RT_prediction=baseline,
        ),
    )
    assert len(rows) == 3 and proof["maximum_error_fraction"] <= 1
    assert all(row["runtime_temperature_reads"] == ("T",) for row in rows)
    if temperature != 298.15:
        assert all(row["value"] != baseline for row in rows)


@pytest.mark.parametrize("probe", P["singular_probes"])
def test_native_gate_singularities_are_retained_without_regularization_or_finite_credit(probe):
    row = native.singular_channel_probe(probe["class_name"], probe["module"], probe["voltage_V"])
    evidence(
        "singular-" + probe["class_name"],
        dict(kind="source_singularity", actual=row, finite_comparison=False),
        row["raw"],
    )
    assert any(not np.all(value) for value in row["finite"].values())
    assert row["warnings"] and row["source_repaired"] is False


@pytest.mark.parametrize("profile", P["constant_profiles"])
def test_native_optional_met_argument_does_not_supply_the_shared_finite_pool(profile):
    first = native.pump_probe(310.15, profile)
    second = native.pump_probe(310.15, profile, met_override=True)
    blocked = native.pump_probe(310.15, profile, block_fraction=0.0)
    for key in ("nak", "pmca", "serca"):
        np.testing.assert_array_equal(first[key], second[key])
    np.testing.assert_array_equal(first["pmca"], blocked["pmca"])
    assert np.count_nonzero(blocked["nak"]) == 0 and np.count_nonzero(first["nak"])
    evidence(
        "met-ignored-" + profile,
        dict(
            kind="native_met_argument",
            ordinary=first,
            changed_met=second,
            zero_block_argument=blocked,
            native_PMCA_block_argument_ignored=True,
            argument_ignored_on_captured_paths=True,
            finite_fuel_parity=False,
        ),
    )


def test_pinned_temperature_source_inventory_keeps_exact_sites_comments_and_limits():
    rows = native.inventory()
    catalog = native.catalog_sources()
    assert len(CLASSES) == 55
    assert set(reference.extra_na.CLASSES) == set(P["channel_classes"]["channels/vg_na.py"])
    caller = [
        row
        for row in rows
        if row["source"]["path"] == "betse/science/sim.py"
        and row["context"].endswith("update_gj")
        and row["kind"] == "configured_temperature"
    ]
    assert caller
    direct_calls = []
    for path in native.MANIFEST["temperature_scan_files"]:
        for node in ast.walk(native.source(path)[1]):
            if isinstance(node, ast.Call) and (
                (isinstance(node.func, ast.Name) and node.func.id == "cagPotassium")
                or (isinstance(node.func, ast.Attribute) and node.func.attr == "cagPotassium")
            ):
                direct_calls.append(native.site(path, node))
    assert not direct_calls
    channel_runtime = [
        row
        for row in rows
        if row["source"]["path"] in {item["source"]["path"] for item in catalog}
        and row["kind"] in ("runtime_temperature", "configured_temperature")
    ]
    assert not channel_runtime
    assert {row["class_name"] for row in catalog} == {name for _, name in CLASSES}
    assert all(row["source"]["code"] for row in catalog)
    evidence(
        "inventory",
        dict(
            kind="source_inventory",
            sites=rows,
            supported_catalog_sources=catalog,
            reviewed_files=len(native.MANIFEST["temperature_scan_files"]),
            catalog_class_bodies=55,
            legacy_functions=1,
            direct_legacy_calls=direct_calls,
            whole_native_simulation=False,
            physically_uniform_runtime_T=False,
        ),
    )


def test_invalid_native_calcium_input_mutation_is_saved_and_does_not_relax_Cells_domains():
    initial = np.asarray([-1e-4])
    actual = initial.copy()
    outside = np.asarray([2.0])
    result = native.toolbox()["pumpCaATP"](
        actual, outside, np.asarray([-0.05]), 298.15, native.parameters(), np.asarray([1.0])
    )
    evidence(
        "source-negative-calcium",
        dict(
            kind="native_invalid_input",
            initial=initial,
            after=actual,
            result=result,
            physical_input_admitted=False,
            Cells_clipping_adopted=False,
        ),
        dict(initial=initial, after=actual, result=result),
    )
    assert actual[0] == 0 and initial[0] < 0
