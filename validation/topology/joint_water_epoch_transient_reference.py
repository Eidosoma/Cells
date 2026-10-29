"""Independent complete epoch transients and original-origin conservation checks.

No Cells/JAX imports. Physical equations reuse the frozen pure full56 joint
oracle; the independent INIT endpoint supplies the new SIM initial condition.
"""

import numpy as np
from scipy.integrate import solve_ivp

from validation.topology import joint_water_profile_interventions_reference as scheduled


class IntegrationFailure(RuntimeError):
    def __init__(self, message, arrays):
        super().__init__(message)
        self.arrays = arrays


def integrate(raw, initial_state=None):
    context = scheduled.bind(raw)
    zero = scheduled.initial(context)
    state = zero.copy() if initial_state is None else np.array(initial_state, copy=True)
    if state.shape != zero.shape or not np.isfinite(state).all() or state[-1] != 0.0:
        raise ValueError("Require complete finite phase-zero state with original anchors")
    end = raw["experiment"]["end_time"]
    clocks = {0.0, end}
    for name, rows in raw["experiment"].items():
        if name.endswith("_controls"):
            clocks.update(
                c["time"]
                for row in rows
                for c in row["controls" if "controls" in row else "schedule"]
            )
    clocks = sorted(clocks)
    times = sorted({*clocks, *raw["experiment"]["observation_times"]})
    floors = {
        name: np.full(
            shape,
            1e-29 if name.endswith("_C") else 1e-24 if name == "membrane_transferred" else 2e-14,
        )
        for name, shape in context["parent"]["shapes"].items()
    }
    atol = np.r_[context["process"].flatten(context["parent"], floors), 1e-22]
    saved = {0.0: state.copy()}
    evaluations = 0
    for left, right in zip(clocks[:-1], clocks[1:], strict=True):
        solved = solve_ivp(
            lambda t, y, held=left: scheduled.evaluate(context, y, held_time=held)[0],
            (left, right),
            state,
            method="DOP853",
            rtol=2e-11,
            atol=atol,
            max_step=min(0.0625e-6, right - left),
            dense_output=True,
        )
        if not solved.success:
            raise IntegrationFailure(
                solved.message,
                dict(
                    partial_times_s=np.asarray(sorted(saved)),
                    partial_states=np.stack([saved[t] for t in sorted(saved)]),
                    solver_times_s=solved.t,
                    solver_states=solved.y.T,
                ),
            )
        state = solved.y[:, -1].copy()
        for time in times:
            if left < time <= right:
                saved[time] = state.copy() if time == right else solved.sol(time)
        evaluations += solved.nfev
    return (
        np.asarray(times),
        np.stack([saved[t] for t in times]),
        dict(
            method="segmented independent DOP853",
            evaluations=evaluations,
            rtol=2e-11,
            amount_volume_energy_atol=2e-14,
            background_transfer_atol_fmol=1e-24,
            charge_atol_C=1e-29,
            clock_atol_s=1e-22,
            max_step_s=0.0625e-6,
            held_control_boundaries_s=clocks,
            all_observations_compared=True,
        ),
    )


def energy_residual(context, vector):
    process, parent = context["process"], context["parent"]
    d = process.unpack(parent, vector[:-1])
    result = process.free_energy_change(parent, vector[:-1], float(vector[-1]))
    result += sum(np.sum(v) for k, v in d.items() if k.endswith("_dissipated_energy_pJ"))
    result -= sum(
        np.sum(d[k])
        for k in ("regeneration_supplied_work_pJ", "reservoir_work_pJ", "electrode_work_pJ")
    )
    return float(result)


def conservation(context, vector):
    c = context["parent"]
    d = context["process"].unpack(c, vector[:-1])
    inside, outside = d["volume_increment_pL"], d["extracellular_volume_increment_pL"]
    local = inside.copy()
    external = outside.copy()
    np.add.at(local, c["patch_owners"], d["water_transferred_pL"])
    ionic = c["raw"]["model"]["ionic"]
    outside_ids = [row["id"] for row in ionic["extracellular"]]
    patch_outsides = [outside_ids.index(row["outside"]) for row in ionic["membranes"]]
    np.add.at(external, patch_outsides, -d["water_transferred_pL"])
    amounts = c["energy_initial"] + d["energy_amount_increment_fmol"]
    a = c["energy_initial"]
    result = dict(
        water_local_pL=float(np.max(np.abs(local), initial=0)),
        water_outside_pL=float(np.max(np.abs(external), initial=0)),
        water_total_pL=float(abs(np.sum(inside) + np.sum(outside))),
        adenylate_fmol=float(np.max(np.abs(amounts[0] + amounts[1] - a[0] - a[1]), initial=0)),
        phosphorus_fmol=float(
            np.max(
                np.abs(3 * amounts[0] + 2 * amounts[1] + amounts[2] - 3 * a[0] - 2 * a[1] - a[2]),
                initial=0,
            )
        ),
    )
    if "damage" in d:
        initial = c["initial_damage"]
        result["damage_ledger"] = float(
            np.max(
                np.abs(d["damage"] - initial - d["damage_opened"] + d["damage_closed"]), initial=0
            )
        )
    return result
