"""Independent control, alternate transport algebra and complete K-only RHS assembly."""

import math
from fractions import Fraction

import history_audit_math as hm

am, ind, require = hm.base, hm.ind, hm.require


def availability(schedule, time_s, side="right"):
    require(
        side in ("left", "right") and math.isfinite(time_s) and time_s >= 0, "Control query domain"
    )
    require(schedule and schedule[0]["time"] == 0, "Control origin")
    require(
        all(
            set(row) == {"time", "availability"}
            and type(row["time"]) in (int, float)
            and math.isfinite(row["time"])
            and row["time"] >= 0
            and type(row["availability"]) in (int, float)
            and math.isfinite(row["availability"])
            and 0 <= row["availability"] <= 1
            for row in schedule
        )
        and all(a["time"] < b["time"] for a, b in zip(schedule[:-1], schedule[1:], strict=True)),
        "Control timeline/domain",
    )
    selected = schedule[0]["availability"]
    for row in schedule:
        if row["time"] < time_s or (side == "right" and row["time"] == time_s):
            selected = row["availability"]
    return selected


def rates(p, state, u):
    q, m, h, _energy = hm.unpack(p, state)
    result = hm.field.rates(p, q, m, h)
    for name in (
        "inward_K_fmol_per_s",
        "inward_current_A",
        "permeability_m_per_s",
        "dissipation_pJ_per_s",
    ):
        result[name] = [u * v for v in result[name]]
    return result


def readout(p, state, u):
    value = hm.readout(p, state)
    for name in ("flux_fmol_per_s", "inward_current_A", "permeability_m_per_s"):
        value[name] = [u * v for v in value[name]]
    return value


def full_rhs(definition, p, state, u):
    q, m, h, energy = (
        state["amount_increment"][1][:7],
        state["gate"][0][:7],
        state["gate"][1][:7],
        state["dissipated_energy_pJ"][:7],
    )
    value = rates(p, q + m + h + energy, u)
    result = {name: am.ready.zeros(shape) for name, shape in am.ready.STATE_SHAPES.items()}
    entries = definition["model"]["cells"]
    require(
        len(entries) == 7 and not definition["model"]["junctions"], "RHS minimal ownership scope"
    )
    for i, entry in enumerate(entries):
        require(
            entry["membrane"]["inside"] == entry["cell"]["id"]
            and entry["channel"]["membrane_id"] == entry["membrane"]["id"]
            and entry["channel"]["species_id"] == "K"
            and entry["membrane"]["outside"] == definition["model"]["extracellular"]["id"],
            "RHS transfer owner",
        )
        result["amount_increment"][1][i] = result["channel_transferred"][i] = value[
            "inward_K_fmol_per_s"
        ][i]
        result["dissipated_energy_pJ"][i] = value["dissipation_pJ_per_s"][i]
        for gate in range(2):
            result["gate"][gate][i] = value["gate_rate_per_s"][gate][i]
    result["extracellular_amount_increment"][1][0] = -math.fsum(value["inward_K_fmol_per_s"])
    return result, value


def rounded_sum(a, b):
    return float(Fraction.from_float(a) + Fraction.from_float(b))


def ordered_mean(values):
    require(
        len(values) == 30 and all(type(v) is float and math.isfinite(v) and v > 0 for v in values),
        "Audit mean domain",
    )
    lanes = [rounded_sum(rounded_sum(values[i], values[i + 8]), values[i + 16]) for i in range(8)]
    pairs = [rounded_sum(lanes[i], lanes[i + 1]) for i in (0, 2, 4, 6)]
    total = rounded_sum(rounded_sum(pairs[0], pairs[1]), rounded_sum(pairs[2], pairs[3]))
    for value in values[24:]:
        total = rounded_sum(total, value)
    return float(Fraction.from_float(total) / 30)


def nonce_voltage(previous):
    result = []
    for value in previous:
        for _ in range(6):
            value = rounded_sum(value, 1e-25)
        result.append(value)
    return result
