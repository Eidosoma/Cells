"""Event-split independent equations; no Cells, JAX or BETSE imports."""

import math

import experiment as x

x.u.module_path("pump_coupled")
import coupled_reference as equations  # noqa: E402


def integrate(case, setting, plan):
    import numpy as np
    from scipy.integrate import solve_ivp

    times = np.asarray(plan["common_times_s"])
    state = np.zeros(equations.size(case))
    states, accepted, segments, calls = [state.tolist()], [state.tolist()], [], 0
    accepted_times = [0.0]
    for index, row in enumerate(case["controls"]):
        start = row["time_s"]
        end = (
            case["controls"][index + 1]["time_s"]
            if index + 1 < len(case["controls"])
            else case["end_time_s"]
        )
        held = row["pump"], row["leak"]

        def rhs(_time, value, held=held):
            nonlocal calls
            calls += 1
            x.u.need(
                calls <= plan["reference"]["max_rhs_calls_per_solve"], "Recovery reference RHS cap"
            )
            return equations.rhs(case, value, held)

        initial = state.copy()
        result = solve_ivp(
            rhs,
            (start, end),
            state,
            method=setting["method"],
            rtol=setting["rtol"],
            atol=setting["atol"],
            max_step=setting["max_step_s"],
            dense_output=True,
        )
        x.u.need(result.success and result.t[-1] == end, "Recovery reference solver failed")
        selected = times[(times > start) & (times <= end)]
        states.extend(result.sol(selected).T.tolist())
        accepted.extend(result.y.T[1:].tolist())
        accepted_times.extend(result.t[1:].tolist())
        state = result.y[:, -1].copy()
        segments.append(
            dict(
                start_s=start,
                end_s=end,
                control=list(held),
                initial=initial.tolist(),
                final=state.tolist(),
            )
        )
        x.u.need(
            len(accepted) - 1 <= plan["reference"]["max_accepted_steps_per_solve"],
            "Recovery reference step cap",
        )
    x.u.need(len(states) == len(times), "Recovery reference sample coverage")
    accounting = []
    min_concentration, min_dissipation = math.inf, math.inf
    for time, state in zip(times.tolist() + accepted_times, states + accepted, strict=True):
        values = equations.accounting(case, state)
        limits = plan["accounting"]
        for key, budget in (
            ("material_residual_fmol", "cells_material_fmol"),
            ("charge_residual_C", "cells_charge_C"),
            ("energy_residual_pJ", "cells_energy_pJ"),
        ):
            x.u.need(
                math.isfinite(values[key]) and values[key] <= limits[budget],
                "Recovery reference " + key,
            )
        rate = equations.rhs(case, state, x.control_at(case["controls"], time))
        x.u.need(all(math.isfinite(v) for v in rate), "Nonfinite recovery reference rate")
        min_concentration = min(min_concentration, values["min_concentration_mM"])
        min_dissipation = min(min_dissipation, *rate[52:])
        accounting.append(values)
    x.u.need(min_concentration > 0 and min_dissipation >= -1e-14, "Recovery reference domain")
    return dict(
        setting=setting,
        times_s=times.tolist(),
        states=states,
        voltage_V=[equations.read_state(case, y)[2] for y in states],
        accepted_times_s=accepted_times,
        accepted_states=accepted,
        segments=segments,
        accounting_maxima={
            key: max(v[key] for v in accounting)
            for key in ("material_residual_fmol", "charge_residual_C", "energy_residual_pJ")
        },
        min_concentration_mM=min_concentration,
        min_dissipation_rate_pJ_s=min_dissipation,
        rhs_calls=calls,
        steady_state_qualified=False,
    )


def worker(root):
    x.u.module_path("pump_relaxation_scope")
    from pilot_reference import gate
    from relax_reference import model_fence

    protocol = x.u.read(root / "protocol.json")
    preparation = x.u.read(root / "preparation.json")
    plan, records = x.plan(protocol), {}
    with model_fence():
        for arm in protocol["arms"]:
            for setting in plan["reference"]["solves"]:
                name = arm + "/" + setting["id"]
                record = integrate(x.case(preparation, arm, protocol), setting, plan)
                x.u.write(root / "reference" / arm / (setting["id"] + ".json"), record)
                records[name] = record
                print("Independent reference", name, flush=True)
        return {"gate": gate(plan, records), "reference_solves": len(records)}
