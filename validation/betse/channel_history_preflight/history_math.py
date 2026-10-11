"""Independent history witness and complete zero-time state/RHS; no model imports."""

import copy
import math

import history_context as ctx

ind = ctx.prior.pilot.audit.independent
ready = ctx.prior.pilot.audit.readiness


def open_rate(gates, rates):
    ctx.c.require(len(gates) == len(rates) == 2, "Gate axis")
    m, h = (ind.finite(v) for v in gates)
    dm, dh = (ind.finite(v) for v in rates)
    ctx.c.require(0 <= m <= 1 and 0 <= h <= 1, "Gate domain")
    return math.fsum((h * dm, m * dh))


def initial_rates(parameters, gates):
    n = len(parameters["volume_pL"])
    return ready.vector_field(parameters, [0.0] * n, [gates[0]] * n, [gates[1]] * n)


def witness(parameters, first, second):
    ctx.c.require(first != second, "History states must differ")
    ctx.c.require(first[0] * first[1] == second[0] * second[1], "Initial products differ")
    a, b = (initial_rates(parameters, g) for g in (first, second))
    n = len(parameters["volume_pL"])
    delta = [
        open_rate(first, [a["gate_rate_per_s"][j][i] for j in range(2)])
        - open_rate(second, [b["gate_rate_per_s"][j][i] for j in range(2)])
        for i in range(n)
    ]
    # At equal inventories/voltage/product, the initial transfer, voltage and
    # concentration derivatives match. Only the gate contribution to the
    # *difference* in flux slopes remains. No trajectory Taylor extrapolation.
    fully_open = initial_rates(parameters, [1.0, 1.0])["inward_K_fmol_per_s"]
    curvature = [flow * d for flow, d in zip(fully_open, delta, strict=True)]
    return {
        "open_rate_difference_per_s": delta,
        "transfer_acceleration_difference_fmol_per_s2": curvature,
        "voltage_acceleration_difference_V_per_s2": [
            q * parameters["F"] * 1e-15 / (area * parameters["cm_F_per_m2"])
            for q, area in zip(curvature, parameters["area_m2"], strict=True)
        ],
        "integrated_prediction": False,
    }


def without_gates(definition):
    result = copy.deepcopy(definition)
    for entry in result["model"]["cells"]:
        entry["channel"].pop("initial_gate")
    return result


def expected_arrays(definition, oracle):
    """Independent bounded K-only, one-channel-per-cell assembly with padding."""
    m, x = definition["model"], definition["execution"]
    entries, species = m["cells"], [s["id"] for s in m["species"]]
    n = len(entries)
    ctx.c.require(species == ["Na", "K", "Cl"] and not m["junctions"], "Wrong minimal assembly")
    ctx.c.require(
        n > 0 and min(x[k] for k in ("capacity", "membrane_capacity", "channel_capacity")) >= n,
        "Insufficient capacities",
    )
    nc, nm, nk, ne, no = (
        x[k]
        for k in (
            "capacity",
            "membrane_capacity",
            "channel_capacity",
            "edge_capacity",
            "extracellular_capacity",
        )
    )

    def zeros(rows, columns):
        return [[0.0] * columns for _ in range(rows)]

    state = {
        "amount_increment": zeros(3, nc),
        "leak_transferred": zeros(3, nm),
        "pump_cycles": [0.0] * nm,
        "dissipated_energy_pJ": [0.0] * nm,
        "gate": zeros(2, nk),
        "channel_transferred": [0.0] * nk,
        "junction_gate": [0.0] * ne,
        "junction_transferred": zeros(3, ne),
        "junction_dissipated_energy_pJ": [0.0] * ne,
        "extracellular_amount_increment": zeros(3, no),
    }
    rate = copy.deepcopy(state)
    for i, entry in enumerate(entries):
        ctx.c.require(
            entry["channel"]["membrane_id"] == entry["membrane"]["id"]
            and entry["channel"]["species_id"] == "K"
            and entry["membrane"]["inside"] == entry["cell"]["id"]
            and entry["membrane"]["outside"] == m["extracellular"]["id"],
            "Wrong membrane/channel owner",
        )
        for j, gate in enumerate(("m", "h")):
            state["gate"][j][i] = entry["channel"]["initial_gate"][gate]
            rate["gate"][j][i] = oracle["gate_rate_per_s"][j][i]
        flow = oracle["inward_K_fmol_per_s"][i]
        rate["amount_increment"][1][i] = flow
        rate["channel_transferred"][i] = flow
        rate["dissipated_energy_pJ"][i] = oracle["dissipation_pJ_per_s"][i]
    rate["extracellular_amount_increment"][1][0] = oracle["outside_K_fmol_per_s"]
    return state, rate
