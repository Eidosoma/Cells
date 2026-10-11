"""Compile candidate data and check initial coupled rates/resources; no integration."""

import copy
import sys

import loop_context as ctx
import pilot_reference as reference

c, t = ctx.c, ctx.t


def parameters(r, variant, row):
    g, initial = row["geometry"], row["trace"]["initial"]["physical"]
    n = g["cell_count"]
    volume = [v / 1e-15 for v in g["cell_volumes_m3"]]
    vo = g["effective_bath_volume_m3"] / 1e-15
    return r["transport_protocol"]["constants"] | {
        "temperature_K": r["transport_protocol"]["temperature_K"],
        "volume_pL": volume,
        "area_m2": g["cell_areas_m2"],
        "cm_F_per_m2": g["specific_capacitance_F_per_m2"],
        "initial_K_fmol": [ci * v for ci, v in zip(initial["inside_mM"][1], volume, strict=True)],
        "outside_volume_pL": vo,
        "outside_K_fmol": t.uniform_bath(initial["outside_mM"][1]) * vo,
        "initial_voltage_V": t.uniform_faces(initial["voltage_V"], g["membrane_owners"], n),
        "channel_enabled": [variant["channel"]] * n,
        "Pmax_m_per_s": [
            r["transport_protocol"]["max_permeability_m_per_s"] * variant["permeability_fraction"]
        ]
        * n,
    }


def definition(r, variant, row, step):
    initial = row["trace"]["initial"]
    result = t.definition(
        r["base_protocol"],
        r["transport_protocol"],
        variant,
        row["geometry"],
        {"before": initial["physical"], "channel_before": initial["channel"]},
    )
    candidate = r["protocol"]["pilot_candidate"]
    result["experiment"].update(
        {
            "end_time": candidate["duration_s"],
            "observation_times": copy.deepcopy(candidate["observation_times_s"]),
        }
    )
    result["execution"].update(
        {
            "dt": step,
            "max_steps": candidate["max_steps"],
            "max_trace_bytes": candidate["max_trace_bytes"],
        }
    )
    return result


def worker(r, output):
    import jax
    import numpy as np

    from cells.core.resources import trace_bytes
    from cells.core.runner import timeline
    from cells.core.schedule import PhysicalIonicGraphControl, control_values
    from cells.core.specs import parse_spec
    from cells.io import runtime_identity
    from cells.models import finite_extracellular as model

    c.require(
        jax.default_backend() == "cpu"
        and jax.config.x64_enabled
        and not jax.config.jax_disable_jit,
        "Require CPU float64 and enabled JIT",
    )
    c.require(runtime_identity() == r["cells_runtime"], "Accepted Cells runtime differs")
    native = c.read(output / "betse.json")
    definitions, records = {}, []
    comparisons = ctx.check.Ledger(
        {
            "tolerances": r["transport_protocol"]["tolerances"]
            | {"power_pJ_per_s": r["protocol"]["initial_power_atol_pJ_per_s"]}
        }
    )
    for variant in r["transport_protocol"]["variants"]:
        row = native["rows"][variant["id"] + "/observed"]
        n = row["geometry"]["cell_count"]
        for step in r["protocol"]["pilot_candidate"]["cells_steps_s"]:
            key = variant["id"] + f"/dt_{step:.8g}"
            d = definition(r, variant, row, step)
            definitions[key] = d
            spec = parse_spec(d)
            state, layout = model.initial_values(spec)
            balances = model.check_values(state, spec)
            times = timeline(spec)  # Existing method/domain/resource precheck, no step.
            control = PhysicalIonicGraphControl(*(v[0] for v in control_values(spec, [0])))
            rate = model.rhs(state, control, layout, layout.active, xp=np)
            gates = model.channel_readouts(state, control.channel, layout, xp=np)
            c.require(
                all(
                    v.dtype == np.float64 and np.isfinite(v).all() for v in (*state, *rate, *gates)
                ),
                "Non-float64/nonfinite candidate state/rates",
            )
            par = parameters(r, variant, row)
            enabled = variant["channel"]
            m, h = r["protocol"]["initial_gate"] if enabled else [0.0, 0.0]
            oracle = reference.rates(par, [0.0] * n, [m] * n, [h] * n)
            pairs = (
                (
                    "voltage",
                    model.cell_voltage(state.amount_increment, layout, xp=np)[:n].tolist(),
                    oracle["voltage_V"],
                    "voltage_V",
                ),
                (
                    "K_rate",
                    rate.amount_increment[1, :n].tolist(),
                    oracle["inward_K_fmol_per_s"],
                    "flux_fmol_per_s",
                ),
                (
                    "outside_K_rate",
                    float(rate.extracellular_amount_increment[1, 0]),
                    oracle["outside_K_fmol_per_s"],
                    "flux_fmol_per_s",
                ),
            )
            for name, actual, expected, unit in pairs:
                comparisons.compare(key + "/" + name, actual, expected, unit)
            if enabled:
                comparisons.compare(
                    key + "/gates",
                    rate.gate[:, :n].tolist(),
                    oracle["gate_rate_per_s"],
                    "gate_rate_per_s",
                )
                comparisons.compare(
                    key + "/channel_transfer",
                    rate.channel_transferred[:n].tolist(),
                    oracle["inward_K_fmol_per_s"],
                    "flux_fmol_per_s",
                )
                comparisons.compare(
                    key + "/dissipation",
                    rate.dissipated_energy_pJ[:n].tolist(),
                    oracle["dissipation_pJ_per_s"],
                    "power_pJ_per_s",
                )
            # Full state is saved for the future restart contract, not collapsed to P or V.
            records.append(
                {
                    "id": key,
                    "grid_s": times.tolist(),
                    "steps": len(times) - 1,
                    "estimated_trace_bytes": trace_bytes(spec, len(times) - 1),
                    "initial_balances": balances,
                    "initial_state": {
                        k: v.tolist() for k, v in zip(state._fields, state, strict=True)
                    },
                    "initial_rhs": {k: v.tolist() for k, v in zip(rate._fields, rate, strict=True)},
                    "independent_parameters": par,
                    "independent_initial_rates": oracle,
                    "integration_executed": False,
                    "convergence_qualified": False,
                }
            )
    c.write(output / "pilot-candidate-definitions.json", definitions)
    failed = sum(not v["passed"] for v in comparisons.rows)
    result = {
        "status": "readiness_pass" if failed == 0 else "readiness_fail",
        "records": records,
        "comparisons": comparisons.rows,
        "failed_comparisons": failed,
        "cells_trajectory_runs": 0,
        "accepted_runtime": runtime_identity(),
        "environment": c.environment(),
        "engine": "unchanged_cells_initial_rates_and_candidate_grids",
    }
    c.require(
        not any(k == "betse" or k.startswith("betse.") for k in sys.modules),
        "Cells readiness imported BETSE",
    )
    return result
