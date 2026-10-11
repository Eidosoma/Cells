"""Ordinary production Cells definitions and complete-state trajectory/restart runs."""

import numpy as np


def definition(c, protocol, dt):
    ids = c["species"]

    def mapped(values):
        return dict(zip(ids, map(float, values), strict=True))

    locals_ = []
    for i in range(len(c["volume_pL"])):
        locals_.append(
            {
                "cell": {
                    "id": f"cell_{i}",
                    "volume_pL": float(c["volume_pL"][i]),
                    "initial_amount_fmol": mapped(c["initial_amount_fmol"][:, i]),
                    "initial_voltage_V": float(c["initial_voltage_V"][i]),
                    "fixed_charge_equivalent_fmol": float(c["fixed_inside_charge_fmol"][i]),
                },
                "membrane": {
                    "id": f"membrane_{i}",
                    "inside": f"cell_{i}",
                    "outside": "outside",
                    "area_m2": float(c["area_m2"][i]),
                    "specific_capacitance_F_per_m2": c["specific_capacitance_F_m2"],
                    "passive": {
                        "law": "constant_field@1",
                        "permeability_m_per_s": mapped([0] * len(ids)),
                    },
                    "pump": None,
                },
                "channel": None,
            }
        )
    edges = []
    for e, (a, b) in enumerate(zip(c["senders"], c["receivers"], strict=True)):
        edges.append(
            {
                "id": f"junction_{e}",
                "from_cell": f"cell_{a}",
                "to_cell": f"cell_{b}",
                "area_m2": float(c["edge_area_m2"][e]),
                "permeability_m_per_s": mapped(c["permeability_m_s"][:, e]),
                # Residual=1 makes conductance independent of the generic gate.
                # That gate remains a saved coordinate, not a BETSE correspondence claim.
                "residual_fraction": mapped([1] * len(ids)),
                "gate": {
                    "law": "symmetric_opposing_relaxation@1",
                    "sensitivity_per_V": 100.0,
                    "half_voltage_V": 0.05,
                    "tau_s": 0.01,
                    "initial_gate": 0.5,
                },
            }
        )
    end = protocol["duration_s"]
    return {
        "schema_version": 1,
        "model": {
            "id": "finite_extracellular@2",
            "species": [
                {"id": s, "valence": int(z)} for s, z in zip(ids, c["valence"], strict=True)
            ],
            "temperature_K": c["temperature_K"],
            "extracellular": {
                "id": "outside",
                "volume_pL": c["outside_volume_pL"],
                "initial_amount_fmol": mapped(
                    c["outside_concentration_mM"] * c["outside_volume_pL"]
                ),
                "fixed_charge_equivalent_fmol": c["fixed_outside_charge_fmol"],
            },
            "cells": locals_,
            "junctions": edges,
        },
        "experiment": {
            "end_time": end,
            "observation_times": np.linspace(
                0, end, round(end / protocol["observation_step_s"]) + 1
            ).tolist(),
            "membrane_controls": [
                {
                    "membrane_id": f"membrane_{i}",
                    "leak": [{"time": 0.0, "multipliers": mapped([1] * len(ids))}],
                    "pump": [{"time": 0.0, "multiplier": 1.0}],
                }
                for i in range(len(locals_))
            ],
            "channel_controls": [],
            "junction_controls": [
                {
                    "junction_id": f"junction_{e}",
                    "schedule": [{"time": 0.0, "open_fraction": float(opening)}],
                }
                for e, opening in enumerate(c["opening"])
            ],
        },
        "execution": {
            "dt": dt,
            "jit": True,
            "capacity": len(locals_),
            "membrane_capacity": len(locals_),
            "channel_capacity": 0,
            "edge_capacity": len(edges),
            "extracellular_capacity": 1,
            "backend": "cpu",
            "precision": "float64",
            "solver": "rk4",
            "max_steps": 10000,
            "max_trace_bytes": 134217728,
            "material_balance_atol_fmol": mapped(
                [protocol["tolerances"]["material_fmol"]] * len(ids)
            ),
        },
    }


def physical(history):
    return np.concatenate(
        (
            np.asarray(history.amount_increment).reshape((len(history.amount_increment), -1)),
            np.asarray(history.junction_transferred).reshape((len(history.amount_increment), -1)),
            np.asarray(history.junction_dissipated_energy_pJ),
        ),
        axis=-1,
    )


def run(c, protocol, dt, output, write):
    from cells.core.runner import run as simulate
    from cells.core.specs import parse_spec
    from cells.core.state import Checkpoint
    from cells.io import load_snapshot, write_snapshot

    output.mkdir(parents=True, exist_ok=False)
    raw = definition(c, protocol, dt)
    write(output / "definition.json", raw)
    spec = parse_spec(raw)
    result = simulate(spec)
    np.savez_compressed(
        output / "trajectory.npz",
        times_s=result.times,
        **{k: np.asarray(v) for k, v in zip(result.history._fields, result.history, strict=True)},
    )
    mid = (len(result.times) - 1) // 2
    state = type(result.final.state)(*(np.asarray(v[mid]) for v in result.history))
    checkpoint = Checkpoint(
        time=float(result.times[mid]),
        step_index=mid,
        event_index=0,
        state=state,
        layout=result.final.layout,
    )
    write_snapshot(output / "restart", spec, checkpoint)
    saved = load_snapshot(output / "restart")
    resumed = simulate(saved.spec, saved.checkpoint)
    for a, b in zip(resumed.history, result.history, strict=True):
        np.testing.assert_array_equal(a, b[mid:])
    for field in (
        "extracellular_amount_increment",
        "leak_transferred",
        "pump_cycles",
        "dissipated_energy_pJ",
        "channel_transferred",
    ):
        np.testing.assert_array_equal(getattr(result.history, field), 0)
    report = {
        "status": "complete_production_trajectory_and_restart",
        "dt_s": dt,
        "restart_time_s": checkpoint.time,
        "restart_exact": True,
        "restart_loaded_from_disk": True,
        "timings": result.timings,
        "diagnostics": result.diagnostics,
    }
    write(output / "result.json", report)
    return result.times, physical(result.history), report
