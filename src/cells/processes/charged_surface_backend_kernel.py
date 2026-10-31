"""Guarded one-interval maps, with unchanged scalar energy/material expressions.

Every record carries an evaluation mask. A false mask means an absent
computation, never a repaired physical result. Failed kernels retain their raw
NaNs; rejected worlds publish their exact parents. The arithmetic slots after
the first refusal are explicitly unevaluated.
"""

from cells.processes import charged_surface_backend_arrays as arrays
from cells.processes.charged_surface_backend_equations import build_equations

STAGE_CODES = {
    -1: "not_attempted",
    0: "ok",
    1: "state_domain",
    2: "flux_domain",
    3: "nonfinite_energetics",
    4: "cargo_charge_rate",
    5: "open_energy_rate",
    6: "ideal_dissipation_rate",
}
INTERVAL_CODES = {
    0: "terminal_noop",
    1: "candidate",
    10: "declared_dt",
    11: "source_state_domain",
    12: "source_ledgers",
    13: "initial_rates",
    14: "declared_loss_bound",
    20: "k1",
    21: "k2",
    22: "k3",
    23: "k4",
    30: "endpoint",
    31: "endpoint_ledgers",
}


def build_kernel(*, xp, jax, movement, fixed, F, R, ordered_scatter, scalar, dimensions):
    """Factory invoked only after scalar qualification and backend release gates."""
    schema = arrays.schemas(*dimensions)
    domain, energetic_values, balances = build_equations(
        xp, movement, arrays.State, F, R, ordered_scatter
    )
    is_numpy = jax is None

    def cond(predicate, yes, no):
        if is_numpy:
            return yes(None) if bool(predicate) else no(None)
        return jax.lax.cond(predicate, yes, no, None)

    def flag(value):
        return xp.asarray(value, dtype="bool")

    def code(value):
        return xp.asarray(value, dtype="int32")

    def all_finite(value):
        return xp.stack([xp.isfinite(leaf).all() for leaf in arrays.leaf_list(value)]).all()

    def energy_status(values):
        finite = all_finite(values)
        charge = (
            xp.max(xp.abs(values["cell_cargo_charge_rate_C_s"]), initial=0)
            <= scalar.CHARGE_RATE_ATOL_A
        )
        energy = (
            xp.max(xp.abs(values["energy_rate_residual_pJ_s"]), initial=0)
            <= scalar.ENERGY_RATE_ATOL_PJ_S
        )
        heat = xp.min(values["dissipation_edge_pJ_s"], initial=0) >= -scalar.ENERGY_RATE_ATOL_PJ_S
        status = xp.where(
            ~finite, 3, xp.where(~charge, 4, xp.where(~energy, 5, xp.where(~heat, 6, 0)))
        )
        return finite & charge & energy & heat, status.astype("int32")

    def stage(vector, parameters, allowed):
        p, anchor, reference, potential = parameters
        empty_kernel = arrays.zero_tree(schema["kernel"], xp)
        empty_values = arrays.zero_tree(schema["energy"], xp)

        def called(_):
            valid_domain = domain(vector, p, anchor)

            def flux(_):
                # Container conversion preserves every returned field and bit.
                result = arrays.KernelValues(
                    *movement.rates(anchor + vector.amount_increment_fmol, potential, p, xp=xp)
                )

                def energy(_):
                    values = energetic_values(vector, result, p, anchor, reference, potential)
                    okay, status = energy_status(values)
                    return arrays.StageTrace(
                        vector,
                        flag(True),
                        valid_domain,
                        flag(True),
                        result,
                        flag(True),
                        values,
                        okay,
                        status,
                    )

                def refused_flux(_):
                    return arrays.StageTrace(
                        vector,
                        flag(True),
                        valid_domain,
                        flag(True),
                        result,
                        flag(False),
                        empty_values,
                        flag(False),
                        code(2),
                    )

                return cond(result.valid, energy, refused_flux)

            def refused_domain(_):
                return arrays.StageTrace(
                    vector,
                    flag(True),
                    valid_domain,
                    flag(False),
                    empty_kernel,
                    flag(False),
                    empty_values,
                    flag(False),
                    code(1),
                )

            return cond(valid_domain, flux, refused_domain)

        def absent(_):
            return arrays.StageTrace(
                vector,
                flag(False),
                flag(False),
                flag(False),
                empty_kernel,
                flag(False),
                empty_values,
                flag(False),
                code(-1),
            )

        return cond(allowed, called, absent)

    def ledger(vector, parameters, allowed, previous=None):
        p, anchor, reference, potential = parameters

        def called(_):
            values = balances(vector, p, anchor, reference, potential)
            material = (
                xp.max(xp.abs(values["local_material_fmol"]), initial=0)
                <= scalar.MATERIAL_ATOL_FMOL
            )
            material = material & (
                xp.max(xp.abs(values["cell_material_fmol"]), initial=0) <= scalar.MATERIAL_ATOL_FMOL
            )
            charge = (
                xp.max(xp.abs(values["cell_cargo_charge_C"]), initial=0) <= scalar.CHARGE_ATOL_C
            )
            energy = xp.max(xp.abs(values["energy_balance_pJ"]), initial=0) <= scalar.ENERGY_ATOL_PJ
            energy = energy & (
                xp.max(xp.abs(values["exact_prescribed_field_transfer_work_link_pJ"]), initial=0)
                <= scalar.ENERGY_ATOL_PJ
            )
            heat = xp.min(vector.dissipated_energy_pJ, initial=0) >= -scalar.DISSIPATION_ATOL_PJ
            if previous is not None:
                heat = heat & (
                    xp.min(vector.dissipated_energy_pJ - previous.dissipated_energy_pJ, initial=0)
                    >= -scalar.DISSIPATION_ATOL_PJ
                )
            return arrays.BalanceTrace(
                flag(True), values, all_finite(values) & material & charge & energy & heat
            )

        def absent(_):
            return arrays.BalanceTrace(
                flag(False), arrays.zero_tree(schema["balances"], xp), flag(False)
            )

        return cond(allowed, called, absent)

    def one_world(inputs):
        vector, parameters, dt, ready = inputs
        p, anchor, _, _ = parameters
        source_domain = domain(vector, p, anchor)
        dt_ok = xp.isfinite(dt) & (dt > 0)
        before = ledger(vector, parameters, ready & source_domain & dt_ok)
        initial = stage(vector, parameters, ready & source_domain & dt_ok & before.ok)
        loss_called = initial.ok
        loss = cond(
            loss_called,
            lambda _: dt * initial.kernel.outgoing_rate_s_inv,
            lambda _: xp.zeros_like(vector.amount_increment_fmol),
        )
        loss_ok = xp.max(loss, initial=0) <= scalar.MAX_LOSS_PER_STEP
        start = ready & source_domain & dt_ok & before.ok & initial.ok & loss_ok
        trials = []

        def rhs(trial):
            allowed = start if not trials else start & trials[-1].ok
            record = stage(trial, parameters, allowed)
            trials.append(record)
            # These zeros fill unevaluated solver slots after refusal. Actual
            # raw stage derivatives remain in record.values without masking.
            return cond(
                record.ok,
                lambda _: record.values["derivative"],
                lambda _: arrays.zero_tree(schema["state"], xp),
            )

        # Exactly the established four RHS calls and weighted RK4 arithmetic.
        proposed = fixed.rk4_step(rhs, vector, dt)
        formed = start & xp.stack([record.ok for record in trials]).all()
        endpoint = stage(proposed, parameters, formed)
        after = ledger(proposed, parameters, endpoint.ok, previous=vector)
        success = formed & endpoint.ok & after.ok
        candidate = cond(success, lambda _: proposed, lambda _: vector)
        status = code(1)
        status = xp.where(~after.ok, 31, status)
        status = xp.where(~endpoint.ok, 30, status)
        for index in (3, 2, 1, 0):
            status = xp.where(~trials[index].ok, 20 + index, status)
        status = xp.where(~loss_ok, 14, status)
        status = xp.where(~initial.ok, 13, status)
        status = xp.where(~before.ok, 12, status)
        status = xp.where(~source_domain, 11, status)
        status = xp.where(~dt_ok, 10, status)
        status = xp.where(~ready, 0, status).astype("int32")
        return arrays.Attempt(
            before,
            initial,
            tuple(trials),
            endpoint,
            after,
            loss_called,
            loss,
            dt,
            ready,
            formed,
            (~ready) | success,
            status,
            candidate,
        )

    def group(inputs):
        if is_numpy:
            worlds = inputs.ready.shape[0]
            results = [
                one_world(arrays.map_tree(lambda leaf, i=i: leaf[i], inputs)) for i in range(worlds)
            ]
            return _stack(results, xp)
        # No vmap or lax.map batch_size: scalar cond must guard each world.
        return jax.lax.map(one_world, inputs)

    return one_world, group


def _stack(values, xp):
    first = values[0]
    if isinstance(first, dict):
        return {key: _stack([value[key] for value in values], xp) for key in sorted(first)}
    if isinstance(first, tuple):
        children = (_stack([value[index] for value in values], xp) for index in range(len(first)))
        return type(first)(*children) if hasattr(first, "_fields") else tuple(children)
    return xp.stack(values)
