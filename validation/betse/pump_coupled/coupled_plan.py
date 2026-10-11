"""Prospective synthetic finite-bath pump/leak fixtures, not experimental data."""

import copy
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import contact as c  # noqa: E402

F = 6.02214076e23 * 1.602176634e-19
R = 6.02214076e23 * 1.380649e-23
AUDIT = c.ROOT / "runs/ref-005a-pump-audit-2026-09-16/audit-01"
AUDIT_SHA = "e968f4a4cbeab64d612029bd61623ec9916d3d720f03903f169c6428dd092ffe"


def cases():
    base = {
        "id": "pump_leak",
        "species": ["Na", "K", "Cl"],
        "valence": [1, 1, -1],
        "pump_stoichiometry": [-3, 2, 0],
        "sodium_index": 0,
        "potassium_index": 1,
        "temperature_K": 298.15,
        "volume_pL": [1.0],
        "outside_volume_pL": 1.0,
        "initial_inside_mM": [[12.0, 140.0, 10.0]],
        "initial_outside_mM": [140.0, 4.0, 120.0],
        "initial_voltage_V": [-0.08],
        "area_m2": [1e-9],
        "specific_capacitance_F_m2": [0.01],
        "permeability_m_s": [[5e-10, 1.8e-9, 1.4e-10]],
        "alpha_mol_m2_s": [1e-7],
        "atp_mM": [1.5],
        "adp_mM": [0.1],
        "pi_mM": [0.1],
        "km_na_mM": [12.0],
        "km_k_mM": [0.2],
        "km_atp_mM": [0.5],
        "delta_g0_J_mol": [-37000.0],
        "end_time_s": 0.01,
        "controls": [{"time_s": 0.0, "pump": 1.0, "leak": 1.0}],
    }
    result = [copy.deepcopy(base)]
    for name, pump, leak in (("pump_only", 1, 0), ("leak_only", 0, 1), ("all_blocked", 0, 0)):
        result.append(
            {
                **copy.deepcopy(base),
                "id": name,
                "controls": [{"time_s": 0.0, "pump": float(pump), "leak": float(leak)}],
            }
        )
    result.append(
        {
            **copy.deepcopy(base),
            "id": "pump_block_release",
            "controls": [
                {"time_s": 0.0, "pump": 1.0, "leak": 1.0},
                {"time_s": 0.004, "pump": 0.0, "leak": 1.0},
                {"time_s": 0.006, "pump": 1.0, "leak": 1.0},
            ],
        }
    )
    pair = copy.deepcopy(base)
    pair["id"], pair["outside_volume_pL"] = "two_cells_shared_bath", 0.2
    for name in (
        "volume_pL",
        "initial_inside_mM",
        "initial_voltage_V",
        "area_m2",
        "specific_capacitance_F_m2",
        "permeability_m_s",
        "alpha_mol_m2_s",
        "atp_mM",
        "adp_mM",
        "pi_mM",
        "km_na_mM",
        "km_k_mM",
        "km_atp_mM",
        "delta_g0_J_mol",
    ):
        pair[name].append(copy.deepcopy(pair[name][0]))
    pair["volume_pL"][1], pair["area_m2"][1] = 1.4, 1.2e-9
    pair["initial_inside_mM"][1] = [20.0, 130.0, 15.0]
    pair["initial_voltage_V"][1], pair["alpha_mol_m2_s"][1] = -0.045, 0.7e-7
    result.append(pair)
    for case in result:
        # Manufactured preparation, not a repair in the solver. All resulting
        # fixed-charge inputs are explicitly saved in the registered definition.
        capacitive = [
            area * cm * v / (F * 1e-15)
            for area, cm, v in zip(
                case["area_m2"],
                case["specific_capacitance_F_m2"],
                case["initial_voltage_V"],
                strict=True,
            )
        ]
        case["fixed_inside_charge_fmol"] = [
            q - vol * math.fsum(z * v for z, v in zip(case["valence"], row, strict=True))
            for q, vol, row in zip(
                capacitive, case["volume_pL"], case["initial_inside_mM"], strict=True
            )
        ]
        case["fixed_outside_charge_fmol"] = -math.fsum(capacitive) - case[
            "outside_volume_pL"
        ] * math.fsum(
            z * v for z, v in zip(case["valence"], case["initial_outside_mM"], strict=True)
        )
    return result


def protocol():
    return {
        "schema": "cells.kinetic_pump_coupled_candidate@1",
        "decision": "D109",
        "law_id": "nak_atp_mass_action_positive@1",
        "cases": cases(),
        "constants": {"F": F, "R": R},
        "sample_dt_s": 0.001,
        "rk4_steps_s": [0.0001, 0.00005],
        "reference_methods": ["DOP853", "Radau"],
        "reference_rtol": 2e-11,
        "reference_atol": 1e-13,
        "reference_max_step_s": 0.0002,
        "state_atol": 1e-8,
        "state_rtol": 2e-7,
        "voltage_atol_V": 1e-7,
        "material_atol_fmol": 2e-11,
        "charge_atol_C": 1e-20,
        "energy_atol_pJ": 2e-8,
        "refinement_ratio_limit": 0.25,
        "roundoff_scaled_error_floor": 0.001,
        "cpu_affinity": [0, 1, 2, 3],
        "worker_timeout_seconds": 240,
        "total_timeout_seconds": 600,
        "per_file_bytes": 16 * 1024**2,
        "artifact_bytes": 64 * 1024**2,
        "production_changed": False,
        "native_betse_trajectory": False,
        "biology_validated": False,
        "gpu_tested": False,
    }


def controls(case, dt):
    count = round(case["end_time_s"] / dt)
    c.require(abs(count * dt - case["end_time_s"]) < 1e-15, "Horizon off grid")
    starts = [round(row["time_s"] / dt) for row in case["controls"]]
    c.require(
        all(
            abs(k * dt - row["time_s"]) < 1e-15
            for k, row in zip(starts, case["controls"], strict=True)
        ),
        "Input off grid",
    )
    rows, index = [], 0
    for step in range(count):
        while index + 1 < len(starts) and starts[index + 1] <= step:
            index += 1
        value = case["controls"][index]
        rows.append([value["pump"], value["leak"]])
    return rows


def predecessor():
    c.require(c.sha(AUDIT / "completion.json") == AUDIT_SHA, "Pump contact closeout changed")
    receipt = c.read(AUDIT / "completion.json")
    c.require(
        receipt["status"] == "pump_contact_independently_closed" and receipt["comparisons"] == 1240,
        "Pump contact is not closed",
    )
    c.require(
        all(c.sha(AUDIT / n) == h for n, h in receipt["files_sha256"].items()),
        "Pump audit payload changed",
    )
    audit_registration = c.read(AUDIT / "registration.json")
    capture = c.ROOT / audit_registration["capture"]
    c.require(
        all(c.sha(capture / n) == h for n, h in audit_registration["capture_sha256"].items()),
        "Original pump contact payload changed",
    )
    capture_registration = c.read(capture / "registration.json")
    c.require(
        all(c.sha(c.ROOT / n) == h for n, h in capture_registration["sources_sha256"].items()),
        "Audited pump source changed",
    )
    return {"path": str(AUDIT.relative_to(c.ROOT)), "completion_sha256": AUDIT_SHA}
