"""Independent initial-state, data mapping and resource contracts; no model imports."""

import math
from decimal import Decimal, localcontext

import loop_independent as ind

SPECIES = ("Na", "K", "Cl")
STATE_SHAPES = {
    "amount_increment": [3, 8],
    "leak_transferred": [3, 9],
    "pump_cycles": [9],
    "dissipated_energy_pJ": [9],
    "gate": [2, 10],
    "channel_transferred": [10],
    "junction_gate": [1],
    "junction_transferred": [3, 1],
    "junction_dissipated_energy_pJ": [1],
    "extracellular_amount_increment": [3, 2],
}


def parameters(row, variant, physics):
    g, state = row["geometry"], row["trace"]["initial"]["physical"]
    volumes = [v / 1e-15 for v in g["cell_volumes_m3"]]
    outside_volume = g["effective_bath_volume_m3"] / 1e-15
    return physics["constants"] | {
        "temperature_K": physics["temperature_K"],
        "volume_pL": volumes,
        "area_m2": g["cell_areas_m2"],
        "cm_F_per_m2": g["specific_capacitance_F_per_m2"],
        "initial_K_fmol": [v * c for v, c in zip(volumes, state["inside_mM"][1], strict=True)],
        "outside_volume_pL": outside_volume,
        "outside_K_fmol": outside_volume * ind.uniform(state["outside_mM"][1]),
        "initial_voltage_V": ind.owner_values(state["voltage_V"], g),
        "channel_enabled": [variant in ind.VARIANTS[2:]] * 7,
        "Pmax_m_per_s": [
            physics["max_permeability_m_per_s"] if variant == "active_channel" else 0.0
        ]
        * 7,
    }


def vector_field(p, transfer, m_gate, h_gate):
    """Independent continuous equations, not a numerical reference solution."""
    n = len(p["volume_pL"])
    ind.require(n > 0, "Empty coupled state")
    for value in (
        transfer,
        m_gate,
        h_gate,
        p["area_m2"],
        p["initial_K_fmol"],
        p["initial_voltage_V"],
        p["channel_enabled"],
        p["Pmax_m_per_s"],
    ):
        ind.require(len(value) == n, "Coupled state axes differ")
    ind.require(p["temperature_K"] == 298.15, "Unqualified kinetic temperature")
    ind.require(
        all(
            ind.finite(p[k]) > 0
            for k in (
                "F",
                "R",
                "temperature_K",
                "outside_volume_pL",
                "outside_K_fmol",
                "cm_F_per_m2",
            )
        ),
        "Invalid physical parameters",
    )
    output = {
        k: []
        for k in (
            "voltage_V",
            "inside_K_mM",
            "inward_K_fmol_per_s",
            "permeability_m_per_s",
            "inward_current_A",
            "dissipation_pJ_per_s",
        )
    }
    output["gate_rate_per_s"] = [[], []]
    with localcontext() as context:
        context.prec = 80
        q = [ind.decimal(ind.finite(v)) for v in transfer]
        co = (ind.decimal(p["outside_K_fmol"]) - sum(q)) / ind.decimal(p["outside_volume_pL"])
        ind.require(co > 0, "Exhausted outside amount")
        for i in range(n):
            volume, area, amount = (
                ind.decimal(ind.finite(p[k][i])) for k in ("volume_pL", "area_m2", "initial_K_fmol")
            )
            amount += q[i]
            ind.require(min(volume, area, amount) > 0, "Nonpositive cell geometry or amount")
            enabled = p["channel_enabled"][i]
            ind.require(type(enabled) is bool, "Invalid channel mask")
            maximum = ind.decimal(ind.finite(p["Pmax_m_per_s"][i]))
            m, h = (ind.decimal(ind.finite(v[i])) for v in (m_gate, h_gate))
            ind.require(maximum >= 0 and 0 <= m <= 1 and 0 <= h <= 1, "Invalid channel state")
            ind.require(enabled or maximum == m == h == 0, "State on absent channel")
            v = ind.decimal(p["initial_voltage_V"][i]) + q[i] * ind.decimal(p["F"]) * Decimal(
                "1e-15"
            ) / (area * ind.decimal(p["cm_F_per_m2"]))
            ind.require(Decimal("-.12") <= v <= Decimal(".06"), "Kinetic voltage domain")
            inside, permeability = amount / volume, maximum * m * h
            flow = (
                ind.inward_density(v, inside, co, permeability, p, p["temperature_K"])
                * area
                * Decimal("1e15")
            )
            potential = (
                ind.decimal(p["R"]) * ind.decimal(p["temperature_K"]) * (inside / co).ln()
                + ind.decimal(p["F"]) * v
            )
            gate_rate = ind.gate_values(float(v), [float(m), float(h)]) if enabled else [0.0, 0.0]
            for name, value in (
                ("voltage_V", v),
                ("inside_K_mM", inside),
                ("permeability_m_per_s", permeability),
                ("inward_K_fmol_per_s", flow),
                ("dissipation_pJ_per_s", -Decimal(".001") * flow * potential),
            ):
                output[name].append(float(value))
            output["inward_current_A"].append(
                float(ind.decimal(p["F"]) * Decimal("1e-15") * ind.decimal(float(flow)))
            )
            for j in range(2):
                output["gate_rate_per_s"][j].append(gate_rate[j])
        output["outside_K_mM"] = float(co)
    output["outside_K_fmol_per_s"] = -math.fsum(output["inward_K_fmol_per_s"])
    return output


def expected_definition(row, variant, step, r):
    """Build independently from measured geometry and all six ionic inventories."""
    g, s = row["geometry"], row["trace"]["initial"]["physical"]
    p, candidate = r["transport_protocol"], r["protocol"]["pilot_candidate"]
    enabled = variant in ind.VARIANTS[2:]
    entries, membrane_controls, channel_controls = [], [], []
    voltage = ind.owner_values(s["voltage_V"], g)
    outside = [ind.uniform(v) for v in s["outside_mM"]]
    for i in range(7):
        volume = g["cell_volumes_m3"][i] / 1e-15
        channel = None
        if enabled:
            channel = {
                "id": f"channel_{i}",
                "membrane_id": f"membrane_{i}",
                "species_id": "K",
                "kinetic_law": "betse_kv1p5_mh@1",
                "abundance": 1.0,
                "max_permeability_m_per_s": p["max_permeability_m_per_s"]
                if variant == "active_channel"
                else 0.0,
                "initial_gate": dict(zip(("m", "h"), r["protocol"]["initial_gate"], strict=True)),
            }
            channel_controls.append(
                {"channel_id": f"channel_{i}", "schedule": [{"time": 0, "availability": 1}]}
            )
        entries.append(
            {
                "cell": {
                    "id": f"cell_{i}",
                    "volume_pL": volume,
                    "initial_voltage_V": voltage[i],
                    "initial_amount_fmol": {
                        name: s["inside_mM"][j][i] * volume for j, name in enumerate(SPECIES)
                    },
                    "fixed_charge_equivalent_fmol": math.fsum(
                        ind.VALENCE[j] * s["inside_mM"][j][i] * volume for j in range(3, 6)
                    ),
                },
                "membrane": {
                    "id": f"membrane_{i}",
                    "inside": f"cell_{i}",
                    "outside": "bath",
                    "area_m2": g["cell_areas_m2"][i],
                    "specific_capacitance_F_per_m2": 0.01,
                    "passive": {
                        "law": "constant_field@1",
                        "permeability_m_per_s": dict.fromkeys(SPECIES, 0.0),
                    },
                    "pump": None,
                },
                "channel": channel,
            }
        )
        membrane_controls.append(
            {
                "membrane_id": f"membrane_{i}",
                "leak": [{"time": 0, "multipliers": dict.fromkeys(SPECIES, 0)}],
                "pump": [{"time": 0, "multiplier": 0}],
            }
        )
    volume = g["effective_bath_volume_m3"] / 1e-15
    return {
        "schema_version": 1,
        "model": {
            "id": "finite_extracellular@1",
            "species": [
                {"id": name, "valence": z} for name, z in zip(SPECIES, ind.VALENCE[:3], strict=True)
            ],
            "temperature_K": 298.15,
            "cells": entries,
            "junctions": [],
            "extracellular": {
                "id": "bath",
                "volume_pL": volume,
                "initial_amount_fmol": {
                    name: outside[j] * volume for j, name in enumerate(SPECIES)
                },
                "fixed_charge_equivalent_fmol": math.fsum(
                    ind.VALENCE[j] * outside[j] * volume for j in range(3, 6)
                ),
            },
        },
        "execution": {
            "backend": "cpu",
            "precision": "float64",
            "jit": True,
            "solver": "rk4",
            "capacity": 8,
            "membrane_capacity": 9,
            "channel_capacity": 10,
            "edge_capacity": 1,
            "extracellular_capacity": 2,
            "dt": step,
            "max_steps": candidate["max_steps"],
            "max_trace_bytes": candidate["max_trace_bytes"],
            "material_balance_atol_fmol": dict.fromkeys(SPECIES, 1e-10),
        },
        "experiment": {
            "end_time": candidate["duration_s"],
            "observation_times": candidate["observation_times_s"],
            "membrane_controls": membrane_controls,
            "channel_controls": channel_controls,
            "junction_controls": [],
        },
    }


def zeros(shape):
    return [zeros(shape[1:]) for _ in range(shape[0])] if shape else 0.0


def expected_initial(enabled):
    state = {key: zeros(shape) for key, shape in STATE_SHAPES.items()}
    if enabled:
        state["gate"][0][:7], state["gate"][1][:7] = [0.2] * 7, [0.6] * 7
    return state


def resources(definition, record):
    e, experiment = definition["execution"], definition["experiment"]
    dt, end = e["dt"], experiment["end_time"]
    ind.require(dt in (50e-6, 25e-6, 12.5e-6) and end == 0.002, "Unregistered candidate grid")
    steps = math.ceil(end / dt)
    grid = [i * dt for i in range(steps)] + [end]
    ind.require(
        record["grid_s"] == grid and record["steps"] == steps, "Candidate elapsed grid differs"
    )
    ind.require(
        steps <= e["max_steps"]
        and max(b - a for a, b in zip(grid[:-1], grid[1:], strict=True)) <= 0.001,
        "Candidate step guard",
    )
    # Independently expand the production resource contract, not a RAM forecast.
    species = len(definition["model"]["species"])
    columns = (
        (16 * species + 24) * e["capacity"]
        + (56 * species + 80) * e["membrane_capacity"]
        + 160 * e["channel_capacity"]
        + (64 * species + 160) * (e["edge_capacity"] + e["extracellular_capacity"])
    )
    estimate = 8 * (columns * (steps + 1 + len(experiment["observation_times"])) + 4 * (steps + 1))
    ind.require(
        columns == 5464
        and estimate == record["estimated_trace_bytes"]
        and estimate <= e["max_trace_bytes"],
        "Trace reservation differs",
    )
    ind.require(
        record["integration_executed"] is False and record["convergence_qualified"] is False,
        "Readiness overclaims trajectory",
    )


def state_contract(record, definition, oracle, enabled):
    initial = expected_initial(enabled)
    ind.require(
        set(record["initial_state"]) == set(record["initial_rhs"]) == set(STATE_SHAPES),
        "Full state membership differs",
    )
    for field, shape in STATE_SHAPES.items():
        list(ind.scalars(record["initial_state"][field], shape))
        list(ind.scalars(record["initial_rhs"][field], shape))
        ind.require(record["initial_state"][field] == initial[field], "Wrong initial state/padding")
    rate = {key: zeros(shape) for key, shape in STATE_SHAPES.items()}
    rate["amount_increment"][1][:7] = oracle["inward_K_fmol_per_s"]
    rate["extracellular_amount_increment"][1][0] = oracle["outside_K_fmol_per_s"]
    rate["channel_transferred"][:7] = oracle["inward_K_fmol_per_s"]
    rate["dissipated_energy_pJ"][:7] = oracle["dissipation_pJ_per_s"]
    if enabled:
        for j in range(2):
            rate["gate"][j][:7] = oracle["gate_rate_per_s"][j]
    for field, expected in rate.items():
        absolute = 1e-12 if "energy" in field else 2e-10
        ind.near(record["initial_rhs"][field], expected, absolute)
        for actual, target in zip(
            ind.scalars(record["initial_rhs"][field], STATE_SHAPES[field]),
            ind.scalars(expected, STATE_SHAPES[field]),
            strict=True,
        ):
            if target == 0:
                ind.require(actual == 0, "Inactive/padded RHS is nonzero")
    balances = record["initial_balances"]
    ind.require(
        set(balances)
        == {
            "max_balance_error_fmol",
            "max_charge_balance_error_V",
            "max_countercharge_error_C",
            "max_energy_balance_error_pJ",
            "max_extracellular_balance_error_fmol",
            "max_global_balance_error_fmol",
        },
        "Initial balance membership differs",
    )
    ind.require(
        all(v == 0 for k, v in balances.items() if k != "max_countercharge_error_C"),
        "Nonzero initial ledger residual",
    )
    f = record["independent_parameters"]["F"]
    capacitor_charges = []
    for entry in definition["model"]["cells"]:
        cell, membrane = entry["cell"], entry["membrane"]
        charge = (
            f
            * 1e-15
            * math.fsum(
                [cell["fixed_charge_equivalent_fmol"]]
                + [
                    z * cell["initial_amount_fmol"][name]
                    for name, z in zip(SPECIES, ind.VALENCE[:3], strict=True)
                ]
            )
        )
        capacitance = membrane["area_m2"] * membrane["specific_capacitance_F_per_m2"]
        ind.near(charge / capacitance, cell["initial_voltage_V"], 1e-10, 0)
        capacitor_charges.append(capacitance * cell["initial_voltage_V"])
    bath = definition["model"]["extracellular"]
    bath_charge = (
        f
        * 1e-15
        * math.fsum(
            [bath["fixed_charge_equivalent_fmol"]]
            + [
                z * bath["initial_amount_fmol"][name]
                for name, z in zip(SPECIES, ind.VALENCE[:3], strict=True)
            ]
        )
    )
    residual = abs(math.fsum([bath_charge, *capacitor_charges]))
    ind.require(
        0 <= ind.finite(balances["max_countercharge_error_C"]) <= 1e-20 and residual <= 1e-20,
        "Countercharge guard",
    )
    ind.near(balances["max_countercharge_error_C"], residual, 1e-20, 0)


def add_comparisons(metrics, key, record, definition, oracle, enabled):
    rate = record["initial_rhs"]
    metrics.add(
        key + "/voltage",
        [entry["cell"]["initial_voltage_V"] for entry in definition["model"]["cells"]],
        oracle["voltage_V"],
        "voltage_V",
    )
    metrics.add(
        key + "/K_rate",
        rate["amount_increment"][1][:7],
        oracle["inward_K_fmol_per_s"],
        "flux_fmol_per_s",
    )
    metrics.add(
        key + "/outside_K_rate",
        rate["extracellular_amount_increment"][1][0],
        oracle["outside_K_fmol_per_s"],
        "flux_fmol_per_s",
    )
    if enabled:
        metrics.add(
            key + "/gates",
            [v[:7] for v in rate["gate"]],
            oracle["gate_rate_per_s"],
            "gate_rate_per_s",
        )
        metrics.add(
            key + "/channel_transfer",
            rate["channel_transferred"][:7],
            oracle["inward_K_fmol_per_s"],
            "flux_fmol_per_s",
        )
        metrics.add(
            key + "/dissipation",
            rate["dissipated_energy_pJ"][:7],
            oracle["dissipation_pJ_per_s"],
            "power_pJ_per_s",
        )


def readiness_metrics(r, native, cells, definitions, metrics):
    records = {row["id"]: row for row in cells["records"]}
    expected_ids = {v + f"/dt_{step:.8g}" for v in ind.VARIANTS for step in (50e-6, 25e-6, 12.5e-6)}
    ind.require(
        len(records) == len(cells["records"]) == 12
        and set(records) == set(definitions) == expected_ids,
        "Candidate coverage differs",
    )
    for variant in ind.VARIANTS:
        row = native["rows"][variant + "/observed"]
        par = parameters(row, variant, r["transport_protocol"])
        enabled = variant in ind.VARIANTS[2:]
        oracle = vector_field(
            par, [0.0] * 7, [0.2 if enabled else 0.0] * 7, [0.6 if enabled else 0.0] * 7
        )
        for step in (50e-6, 25e-6, 12.5e-6):
            key = variant + f"/dt_{step:.8g}"
            record, definition = records[key], definitions[key]
            ind.require(
                definition == expected_definition(row, variant, step, r),
                "Independent candidate definition differs",
            )
            ind.require(
                record["independent_parameters"] == par, "Independent parameter mapping differs"
            )
            ind.require(
                set(record["independent_initial_rates"]) == set(oracle),
                "Initial oracle fields differ",
            )
            for name, expected in oracle.items():
                absolute = (
                    1e-22
                    if name == "permeability_m_per_s"
                    else 2e-20
                    if name == "inward_current_A"
                    else 1e-12
                    if name == "dissipation_pJ_per_s"
                    else 2e-10
                )
                ind.near(record["independent_initial_rates"][name], expected, absolute)
            resources(definition, record)
            state_contract(record, definition, oracle, enabled)
            add_comparisons(metrics, key, record, definition, oracle, enabled)
    return {
        "candidate_definition_contracts_checked": 12,
        "full_initial_states_checked": 12,
        "full_initial_rhs_checked": 12,
        "candidate_grid_resource_contracts_checked": 12,
    }
