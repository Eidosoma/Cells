"""Independent integer-ratio conversion and initial-state field comparisons.

Conversion uses global Green/ear geometry and integer rounding-cell tests. The
field lane reuses independent scalar transport/chemistry and full-node roots;
it never advances time or imports production. Scientific imports are lazy so
the conversion lane can deny every scientific package in a fresh process.
"""

import importlib
import math
from decimal import localcontext

from validation.geometry import conservative_polygon_geometry_reference as polygon
from validation.geometry import stable_geometry_primitives_reference as rounding


def ratio(value):
    return polygon._ratio(*float(value).as_integer_ratio())


def multiply(a, b):
    return polygon._mul(a, b)


def divide(a, b):
    an, ad = polygon._pair(a)
    bn, bd = polygon._pair(b)
    return polygon._ratio(an * bd, ad * bn)


def subtract(a, b):
    an, ad = polygon._pair(a)
    bn, bd = polygon._pair(b)
    return polygon._ratio(an * bd - bn * ad, ad * bd)


def rounded(exact, *, radical=False, precision=4096):
    with localcontext() as ctx:
        ctx.prec = precision
        target = polygon._decimal(exact)
        if radical:
            target = target.sqrt()
            value = float(target)
            if not math.isfinite(value) or (value == 0 and int(exact["numerator"]) != 0):
                raise ValueError("Unrepresentable independent square-root target")
            if not polygon._sqrt_rounding_cell(value, exact):
                raise ValueError("Independent target did not resolve its integer rounding cell")
        else:
            exact_hex = rounding._rounded_ratio(exact, target)
            if exact_hex is None:
                raise ValueError("Unrepresentable independent rational target")
            value = float.fromhex(exact_hex)
    return value


def semantic(value, path=()):
    """Named chemistry tables are sets; ionic axes, gates and clocks stay ordered."""
    if isinstance(value, dict):
        return {key: semantic(item, (*path, key)) for key, item in value.items()}
    if not isinstance(value, list):
        return value
    result = [semantic(item, (*path, index)) for index, item in enumerate(value)]
    name = path[-1] if path else None
    chemical_table = (
        len(path) == 5
        and path[0] == "model"
        and path[1] == "stores"
        and type(path[2]) is int
        and path[3] == "model"
    )
    if chemical_table and name == "moieties":
        assert all(type(label) is str for label in result)
        assert len(set(result)) == len(result)
        return sorted(result)
    keys = {
        "cells": "id",
        "extracellular": "id",
        "membranes": "id",
        "junctions": "id",
        "channels": "id",
        "stores": "cell_id",
        "calcium_channels": "membrane_id",
        "ip3_release": "cell_id",
        "energy_pools": "id",
        "regeneration_ports": "id",
        "membrane_controls": "membrane_id",
        "junction_controls": "junction_id",
        "channel_controls": "channel_id",
        "pump_controls": "pump_id",
        "store_controls": "cell_id",
        "plasma_controls": "membrane_id",
        "calcium_channel_controls": "channel_id",
        "regeneration_controls": "regeneration_id",
    }
    key = keys.get(name)
    if chemical_table and name in ("species", "compartments", "reactions"):
        key = "id"
    elif name == "membranes" and result and "membrane_id" in result[0]:
        key = "membrane_id"
    if key:
        assert len({row[key] for row in result}) == len(result)
        return sorted(result, key=lambda row: row[key])
    return result


def materialize(declaration, binding, request, *, refinement=1):
    """Derive quantities from original vertices, never production certificates."""
    targets = polygon.evaluate(declaration, refinement=refinement)
    cells = {row["id"]: row for row in targets["cells"]}
    edges = {tuple(row["vertex_ids"]): row for row in targets["edges"]}
    geom_edges = {row["id"]: row for row in binding["edges"]}
    membranes = {row["id"]: row for row in binding["membranes"]}
    contacts = {row["id"]: row for row in binding["contacts"]}
    baths = {row["id"]: row for row in declaration["baths"]}
    partitions = {row["cell_id"]: ratio(row["ER_fraction"]) for row in request["cell_partitions"]}
    er = {row["cell_id"]: row for row in request["ER_geometry"]}
    paths = {row["contact_id"]: row for row in request["contact_geometry"]}
    conversions = []

    def edge_for(row):
        return edges[tuple(geom_edges[row["edge_id"]]["vertex_ids"])]

    def visit(value, path=()):
        if isinstance(value, dict) and "$geometry" in value:
            name = value["$geometry"]
            radical = False
            if name == "cell_volume_pL":
                exact = cells[value["cell_id"]]["exact_ratios"]["volume_m3"]
                if value["role"] != "total":
                    f = partitions[value["cell_id"]]
                    exact = multiply(exact, f if value["role"] == "ER" else subtract(ratio(1), f))
                exact = multiply(exact, ratio(1e15))
                unit = "pL"
            elif name == "bath_volume_pL":
                exact = multiply(ratio(baths[value["bath_id"]]["volume_m3"]), ratio(1e15))
                unit = "pL"
            elif name in ("membrane_area_m2", "membrane_capacitance_F", "contact_area_m2"):
                owner = (
                    contacts[value["contact_id"]]
                    if name.startswith("contact_")
                    else membranes[value["membrane_id"]]
                )
                exact = edge_for(owner)["squared_targets"]["area_m2"]
                if name == "membrane_capacitance_F":
                    c = ratio(value["specific_capacitance_F_per_m2"])
                    exact = multiply(exact, multiply(c, c))
                radical = True
                unit = "F" if name.endswith("_F") else "m2"
            elif name == "ER_area_m2":
                exact, unit = ratio(er[value["cell_id"]]["area_m2"]), "m2"
            elif name.endswith("permeability_m_per_s"):
                if name.startswith("membrane_"):
                    length = declaration["thickness_m"]
                elif name.startswith("contact_"):
                    length = paths[value["contact_id"]]["path_length_m"]
                else:
                    length = er[value["cell_id"]]["thickness_m"]
                exact = divide(ratio(value["diffusivity_m2_per_s"]), ratio(length))
                unit = "m/s"
            else:
                raise ValueError("Unknown independent geometry quantity: " + name)
            number = rounded(exact, radical=radical, precision=targets["precision_digits"])
            conversions.append(
                dict(
                    path=list(path),
                    reference=value,
                    exact_target=exact,
                    radical=radical,
                    units=unit,
                    value_binary64_hex=number.hex(),
                )
            )
            return number
        if isinstance(value, dict):
            return {key: visit(item, (*path, key)) for key, item in value.items()}
        if isinstance(value, list):
            return [visit(item, (*path, i)) for i, item in enumerate(value)]
        return value

    definition = visit(request["definition_template"])
    return dict(
        definition=definition,
        conversions=conversions,
        geometry_targets=targets,
        refinement=refinement,
    )


def compare_conversion(packet):
    primary = materialize(packet["geometry_declaration"], packet["geometry"], packet["request"])
    refined = materialize(
        packet["geometry_declaration"], packet["geometry"], packet["request"], refinement=2
    )
    checks = polygon.compare(
        packet["geometry_declaration"],
        packet["geometry"],
        primary["geometry_targets"],
        refined["geometry_targets"],
    )
    assert primary["definition"] == refined["definition"]
    assert semantic(primary["definition"]) == semantic(packet["definition"])
    actual = {tuple(row["path"]): row for row in packet["provenance"]["conversions"]}
    expected = {tuple(row["path"]): row for row in primary["conversions"]}
    assert set(actual) == set(expected)
    for path, row in expected.items():
        assert actual[path]["reference"] == row["reference"]
        assert actual[path]["units"] == row["units"]
        assert actual[path]["value_binary64_hex"] == row["value_binary64_hex"]
        certificate = actual[path]["certificate"]
        if row["radical"]:
            assert certificate["radicand"] == row["exact_target"]
        else:
            assert certificate["exact"] == row["exact_target"]
    return dict(
        status="passed",
        primary=primary,
        refined=refined,
        geometry_checks=checks,
        conversion_count=len(expected),
        all_nongeometric_declarations_preserved=True,
        production_imports=False,
        trajectory_executed=False,
        native_equivalence=False,
    )


REFERENCE_MODULES = {
    "resolved_tissue@2": "surface_kinetic_reference",
    "resolved_tissue@12": "surface_kinetic_reference",
    "resolved_energy@1": "surface_energy_reference",
    "resolved_energy@2": "surface_energy_reference",
    "resolved_calcium@1": "surface_calcium_reference",
    "resolved_calcium@11": "surface_calcium_reference",
    "resolved_calcium_energy@1": "surface_calcium_energy_reference",
    "resolved_calcium_energy@5": "surface_calcium_energy_reference",
    "resolved_open_calcium@1": "open_calcium_reference",
    "resolved_open_calcium_energy@1": "open_calcium_reference",
}


# Existing instantaneous residual limits, in pJ/s, for actual and independent
# implementations respectively. These are intentionally distinct: a reference
# proof can have a stricter budget than the production readout. None means the
# ionic reference has no total-energy identity; it must never be replaced by 0.
ENERGY_LIMITS = {
    "resolved_tissue@2": (1e-10, None),
    "resolved_tissue@12": (1e-10, None),
    "resolved_energy@1": (2e-8, 2e-8),
    "resolved_energy@2": (2e-8, 2e-10),
    "resolved_calcium@1": (1e-10, 1e-10),
    "resolved_calcium@11": (1e-10, 1e-10),
    "resolved_calcium_energy@1": (2e-10, 3e-10),
    "resolved_calcium_energy@5": (1e-10, 3e-10),
    "resolved_open_calcium@1": (1e-10, 1e-10),
    "resolved_open_calcium_energy@1": (1e-10, 1e-10),
}


def energy_evidence(model_id, actual, proof):
    actual_limit, reference_limit = ENERGY_LIMITS[model_id]
    return dict(
        actual_energy_balance_pJ_s=float(actual),
        actual_absolute_budget_pJ_s=actual_limit,
        independent_energy_balance_pJ_s=(
            None if reference_limit is None else float(proof["physical_energy_balance_pJ_s"])
        ),
        independent_absolute_budget_pJ_s=reference_limit,
        independent_identity_available=reference_limit is not None,
    )


def assert_energy(model_id, record):
    actual_limit, reference_limit = ENERGY_LIMITS[model_id]
    assert record["actual_absolute_budget_pJ_s"] == actual_limit
    actual = record["actual_energy_balance_pJ_s"]
    assert math.isfinite(actual) and abs(actual) <= actual_limit
    assert record["independent_absolute_budget_pJ_s"] == reference_limit
    assert record["independent_identity_available"] is (reference_limit is not None)
    reference = record["independent_energy_balance_pJ_s"]
    if reference_limit is None:
        assert reference is None
    else:
        assert math.isfinite(reference) and abs(reference) <= reference_limit


def compare_initial_field(packet, *, retain=None):
    import numpy as np

    raw = packet["definition"]
    ref = importlib.import_module("validation.tissue." + REFERENCE_MODULES[raw["model"]["id"]])
    context = ref.bind(raw)
    state = ref.initial(context)
    ion = raw["model"].get("ionic", raw["model"])
    declared = packet["request"]["provenance"]
    intended_phi = np.asarray(
        [declared["declared_cell_potential_V"][row["id"]] for row in ion["cells"]]
        + [declared["declared_bath_potential_V"][row["id"]] for row in ion["extracellular"]]
    )
    if retain is not None:
        retain(
            "independent-initial",
            dict(
                state=state.tolist(),
                shapes={key: list(shape) for key, shape in context["shapes"].items()},
            ),
        )
    # Independent zero padding checks precede compact packing. All complete
    # state fields, including fuel/chemical/electrode ledgers, must be present.
    assert set(packet["state"]) == set(context["shapes"])

    def packed(values):
        for key, shape in context["shapes"].items():
            array = np.asarray(values[key])
            assert array.ndim == len(shape) and all(
                a >= b for a, b in zip(array.shape, shape, strict=True)
            )
            mask = np.ones(array.shape, dtype=bool)
            mask[tuple(slice(0, n) for n in shape)] = False
            assert np.isfinite(array).all() and not np.any(array[mask])
        return ref.flatten(context, values)

    np.testing.assert_array_equal(packed(packet["state"]), state)
    atol = ref.flatten(
        context,
        {
            key: np.full(shape, 3e-23 if key.endswith("_C") else 3e-12)
            for key, shape in context["shapes"].items()
        },
    )
    stages = []
    for trial in packet["initial_control_probes"]:
        time = trial["time_s"]
        expected, phi, proof = ref.evaluate(context, state, time)
        if retain is not None:
            retain(
                "independent-raw-return-" + str(len(stages)),
                dict(
                    time_s=time, derivative=expected.tolist(), potential_V=phi.tolist(), proof=proof
                ),
            )
        actual = packed(trial["derivative"])
        budget = atol + 3e-10 * np.abs(expected)
        score = float(np.max(np.abs(actual - expected) / budget, initial=0))
        observed_phi = np.asarray(trial["potential_V"])
        field_budget = 3e-13 + 3e-10 * np.abs(phi)
        field_score = float(np.max(np.abs(observed_phi - phi) / field_budget, initial=0))
        manufactured_score = float(np.max(np.abs(phi - intended_phi) / field_budget, initial=0))
        stages.append(
            dict(
                time_s=time,
                state=state.tolist(),
                actual_derivative=actual.tolist(),
                expected_derivative=expected.tolist(),
                derivative_budget=budget.tolist(),
                actual_potential_V=observed_phi.tolist(),
                expected_potential_V=phi.tolist(),
                field_budget_V=field_budget.tolist(),
                derivative_error_over_budget=score,
                potential_error_over_budget=field_score,
                intended_potential_V=intended_phi.tolist(),
                intended_potential_error_over_budget=manufactured_score,
                proof=proof,
                energy=energy_evidence(
                    raw["model"]["id"], trial["field"]["energy_balance_pJ_s"], proof
                ),
                production_stage_valid=trial["valid"],
            )
        )
        if retain is not None:
            retain("independent-stage-" + str(len(stages) - 1), stages[-1])
    # Return before assertions so callers persist every failed trial.
    return dict(
        status="compared",
        model_id=raw["model"]["id"],
        stages=stages,
        shapes={key: list(shape) for key, shape in context["shapes"].items()},
        complete_state_field_count=len(context["shapes"]),
        production_imports=False,
        time_advanced=False,
        trajectory_executed=False,
        native_equivalence=False,
    )


def assert_initial_field(report):
    for stage in report["stages"]:
        assert stage["derivative_error_over_budget"] <= 1
        assert stage["potential_error_over_budget"] <= 1
        assert stage["intended_potential_error_over_budget"] <= 1
        assert stage["production_stage_valid"]
        assert max(abs(v) for v in stage["expected_potential_V"]) > 1e-3
        assert_energy(report["model_id"], stage["energy"])
