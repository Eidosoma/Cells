"""Independent segmented ECM trajectories and molecular/capacitive accounting."""

import math
from decimal import Decimal, localcontext

import numpy as np
from scipy.integrate import solve_ivp

from validation.chemistry import finite_energy_reference as pools
from validation.transport import owned_barrier_interventions_reference as scheduled


class IntegrationFailure(RuntimeError):
    def __init__(self, message, arrays):
        super().__init__(message)
        self.arrays = arrays


def integrate(raw, left, right, times, initial_state=None, *, factor=1):
    context = scheduled.bind(raw)
    state = (
        scheduled.initial(context) if initial_state is None else np.array(initial_state, copy=True)
    )
    if (
        factor not in (1, 2)
        or not np.isfinite(state).all()
        or abs(state[-1] - left) > context["phase_clock_atol_s"]
    ):
        raise ValueError(
            "Require a complete finite continuation at the actual absolute phase clock"
        )
    knots = {left, right}
    for name, groups in raw["experiment"].items():
        if name.endswith("_controls"):
            for row in groups:
                knots.update(
                    v["time"]
                    for v in row.get("controls", row.get("schedule", []))
                    if left < v["time"] < right
                )
    knots = sorted(knots)
    floors = {
        k: np.full(
            shape,
            1e-29
            if k.endswith("_C")
            else 1e-24
            if k == "face_transferred"
            else 1e-22
            if k == "phase_clock_s"
            else 2e-14,
        )
        for k, shape in context["shapes"].items()
    }
    atol = scheduled.flatten(context, floors) / factor
    saved = {left: state.copy()}
    nfev = 0
    for start, stop in zip(knots[:-1], knots[1:], strict=True):
        solved = solve_ivp(
            lambda t, y, held=start: scheduled.evaluate(context, y, t, held_time=held)[0],
            (start, stop),
            state,
            method="DOP853",
            rtol=2e-11 / factor,
            atol=atol,
            max_step=min(62.5e-9 / factor, stop - start),
            dense_output=True,
        )
        if not solved.success:
            raise IntegrationFailure(
                solved.message,
                dict(
                    times_s=np.asarray(sorted(saved)),
                    state_flat=np.stack([saved[t] for t in sorted(saved)]),
                    solver_times_s=solved.t,
                    solver_state_flat=solved.y.T,
                ),
            )
        state = solved.y[:, -1].copy()
        for time in times:
            if start < time <= stop:
                saved[time] = state.copy() if time == stop else solved.sol(time)
        nfev += solved.nfev
    return (
        np.asarray(times),
        np.stack([saved[t] for t in times]),
        dict(
            method="segmented independent DOP853",
            factor=factor,
            rhs_evaluations=nfev,
            rtol=2e-11 / factor,
            bulk_atol=2e-14 / factor,
            face_transfer_atol_fmol=1e-24 / factor,
            charge_atol_C=1e-29 / factor,
            clock_atol_s=1e-22 / factor,
            max_step_s=62.5e-9 / factor,
            held_control_knots_s=knots,
            original_clock_preserved=True,
        ),
    )


def conservation(context, vector):
    """Direct 80-digit molecular energy, ion ownership and neutral-pool invariants."""
    parent = context["parent"]
    fields = scheduled.unpack(context, vector)
    clock = float(fields["phase_clock_s"][0])
    _, potential, _ = scheduled.evaluate(context, vector, clock)
    if "initial_phi" not in context:
        zero = scheduled.initial(context)
        context["initial_phi"] = scheduled.evaluate(context, zero, 0.0)[1]
    calcium = parent.get("calcium", parent)
    ion = scheduled.leaf(context["parent_definition"])
    before_phi = context["initial_phi"]
    with localcontext() as precision:
        precision.prec = 80

        def dec(value):
            return Decimal(str(float(value)))

        rt = dec(scheduled.ionic.R) * dec(parent["layout"]["temperature"]) * Decimal("0.001")
        stored = Decimal(0)
        if "chemical_amount_increment" in fields:
            for i, store in enumerate(calcium["stores"]):
                for s in range(len(store.ids)):
                    for k in range(store.n0.shape[1]):
                        a0 = dec(store.n0[s, k])
                        amount = a0 + dec(fields["chemical_amount_increment"][i, s, k])
                        denominator = dec(store.volume[k]) * dec(store.c0)
                        stored += rt * (
                            amount * (dec(store.mu0[s]) + (amount / denominator).ln() - 1)
                            - a0 * (dec(store.mu0[s]) + (a0 / denominator).ln() - 1)
                        )
                change = (
                    Decimal("1e-15")
                    * dec(scheduled.ionic.F)
                    / dec(store.cap)
                    * sum(
                        dec(z) * dec(a)
                        for z, a in zip(
                            store.z,
                            fields["chemical_amount_increment"][i, :, store.er],
                            strict=True,
                        )
                    )
                )
                stored += (
                    Decimal("0.5e12")
                    * dec(store.cap)
                    * change
                    * (2 * dec(store.membrane["initial_voltage_V"]) + change)
                )
        else:
            for s in range(parent["ai"].shape[0]):
                for i in range(len(parent["vi"])):
                    a0 = dec(parent["ai"][s, i])
                    amount = a0 + dec(fields["amount_increment"][s, i])
                    volume = dec(parent["vi"][i])
                    stored += rt * (
                        amount * ((amount / volume).ln() - 1) - a0 * ((a0 / volume).ln() - 1)
                    )
        for s in range(parent["ao"].shape[0]):
            for i in range(len(parent["vo"])):
                a0 = dec(parent["ao"][s, i])
                amount = a0 + dec(fields["extracellular_amount_increment"][s, i])
                volume = dec(parent["vo"][i])
                stored += rt * (
                    amount * ((amount / volume).ln() - 1) - a0 * ((a0 / volume).ln() - 1)
                )
        cells = [p["id"] for p in ion["cells"]]
        outsides = [p["id"] for p in ion["extracellular"]]
        n = len(cells)
        for patch in ion["membranes"]:
            i, o = cells.index(patch["inside"]), n + outsides.index(patch["outside"])
            voltage, before = dec(potential[i] - potential[o]), dec(before_phi[i] - before_phi[o])
            stored += (
                Decimal("0.5e12")
                * dec(patch["capacitance_F"])
                * (voltage - before)
                * (voltage + before)
            )
        if "energy_amount_increment_fmol" in fields:
            initial = parent["energy_initial"]
            current = initial + fields["energy_amount_increment_fmol"]
            stored += sum(
                dec(
                    pools.free_energy_change(
                        initial[:, i],
                        current[:, i],
                        parent["vi"][i],
                        parent["vi"][i],
                        parent["temperature"],
                        parent["energy_delta_g0"][i],
                    )
                )
                for i in range(n)
            )
        heat = sum(dec(np.sum(v)) for k, v in fields.items() if k.endswith("_dissipated_energy_pJ"))
        work_names = (
            ("regeneration_supplied_work_pJ",)
            if "energy_amount_increment_fmol" in fields
            else ("metabolic_work_pJ", "plasma_metabolic_work_pJ", "er_metabolic_work_pJ")
        )
        work = sum(
            dec(np.sum(fields[k]))
            for k in (*work_names, "reservoir_work_pJ", "electrode_work_pJ")
            if k in fields
        )
        residual = float(stored + heat - work)
    local = fields["amount_increment"].copy()
    outside = fields["extracellular_amount_increment"].copy() - fields["reservoir_supplied"]
    for j, route in enumerate(ion["membranes"]):
        i, o = cells.index(route["inside"]), outsides.index(route["outside"])
        flux = fields["membrane_transferred"][:, j].copy()
        for c, ch in enumerate(ion["channels"]):
            if ch["membrane_id"] == route["id"]:
                flux += fields["channel_transferred"][:, c]
        if route["pump"] is not None:
            ids = [s["id"] for s in ion["species"]]
            flux[ids.index("Na")] += 3 * fields["pump_cycles"][j]
            flux[ids.index("K")] -= 2 * fields["pump_cycles"][j]
        if "plasma_pump_cycles" in fields:
            ids = [s["id"] for s in ion["species"]]
            flux[ids.index("Ca")] += (
                fields["plasma_pump_cycles"][j]
                + fields["plasma_exchange_cycles"][j]
                + fields["calcium_channel_transferred"][j]
            )
            flux[ids.index("Na")] -= 3 * fields["plasma_exchange_cycles"][j]
        local[:, i] += flux
        outside[:, o] -= flux
    for family, values, names in (("junction", local, cells), ("face", outside, outsides)):
        for j, route in enumerate(ion[family + "s"]):
            values[:, names.index(route["sender"])] += fields[family + "_transferred"][:, j]
            values[:, names.index(route["receiver"])] -= fields[family + "_transferred"][:, j]
    result = dict(
        energy_pJ=residual,
        local_material_fmol=float(np.max(np.abs(local), initial=0)),
        outside_material_fmol=float(np.max(np.abs(outside), initial=0)),
    )
    if "energy_amount_increment_fmol" in fields:
        change = fields["energy_amount_increment_fmol"]
        result.update(
            adenylate_fmol=float(np.max(np.abs(change[0] + change[1]), initial=0)),
            phosphorus_fmol=float(
                np.max(np.abs(3 * change[0] + 2 * change[1] + change[2]), initial=0)
            ),
        )
    return result


def assert_conservation(rows):
    maxima = {k: max(abs(row[k]) for row in rows) for k in rows[0]}
    for key, value in maxima.items():
        assert math.isfinite(value) and value <= (1e-9 if key == "energy_pJ" else 2e-11), (
            key,
            value,
        )
    return maxima
