"""Independent maintained-pool pump and source join equations.

Carried outputs are diagnostics. Acceptance also uses fresh conditional local
answers from each actual incoming float state, with inherited component budgets.
"""

import copy
from decimal import Decimal, localcontext

from validation.betse import betse_normal_catalog_join_equations as channel_equations
from validation.betse.betse_normal_channel_join_runtime import inventory as runtime_inventory
from validation.betse.betse_normal_current_reference import evaluate as current_equations
from validation.betse.betse_normal_gated_join_reference import gate_step, initialize
from validation.betse.betse_normal_ion_join_reference import convert, d
from validation.betse.betse_normal_voltage_reference import tree, voltage_equations


def pump_phase(inputs, values, gross, step, refinement):
    """Independent source pump arithmetic; finite branch is binary64-selected."""
    raw, live = inputs["pump_definition"], inputs["pump_packet"]
    definition = inputs["definition"]
    names = definition["ions"]["ids"]
    na, potassium = names.index(raw["sodium_id"]), names.index(raw["potassium_id"])
    pools, kinetics = raw["maintained"], raw["kinetics"]
    atp, adp, pi = (d(pools[key]) for key in ("cATP", "cADP", "cPi"))
    kna, kk, katp, dg = (d(kinetics[key]) for key in ("KmNK_Na", "KmNK_K", "KmNK_ATP", "deltaGATP"))
    F, R = d(definition["parameters"]["F_C_mol"]), d(definition["parameters"]["R_J_mol_K"])
    temperature = d(step["runtime_temperature_K"])
    alpha = d(live["alpha_NaK"])
    m = len(values["voltage_V"])
    zero = Decimal(0)
    before = copy.deepcopy(values["membrane_flux_mol_m2_s"])
    proxy_before = [d(x) for x in inputs["incoming_rate_proxy_mol_m2_s"]]
    proxy = proxy_before.copy() if alpha != 0 else [zero] * m
    applied_na, applied_k, scaled_na, scaled_k = ([zero] * m for _ in range(4))
    bound_na, bound_k, proxy_gross = ([zero] * m, [zero] * m, [abs(x) for x in proxy])
    arithmetic = None
    if alpha > 0:
        arithmetic = {
            key: []
            for key in (
                "quotient_numerator",
                "quotient_denominator_raw",
                "quotient_denominator_used",
                "zero_denominator_indices",
                "quotient",
                "equilibrium",
                "saturation_numerator",
                "saturation_denominator",
                "saturation",
                "raw_sodium_flux_mol_m2_s",
                "raw_potassium_flux_mol_m2_s",
                "raw_rate_proxy_mol_m2_s",
            )
        }
        for j in range(m):
            nai, nao = values["membrane_mol_m3"][na][j], values["bath_mol_m3"][na]
            ki, ko = values["membrane_mol_m3"][potassium][j], values["bath_mol_m3"][potassium]
            vm = values["voltage_V"][j]
            qnum = (adp * d(1e-3)) * (pi * d(1e-3)) * (nao * d(1e-3)) ** 3 * (ki * d(1e-3)) ** 2
            qraw = (atp * d(1e-3)) * (nai * d(1e-3)) ** 3 * (ko * d(1e-3)) ** 2
            # The literal denominator guard is selected on stored binary64
            # products. Constitutive arithmetic then uses independent Decimal.
            try:
                selected = (float(atp) * 1e-3) * (float(nai) * 1e-3) ** 3 * (float(ko) * 1e-3) ** 2
            except OverflowError:
                selected = float("inf")
            floor = selected == 0
            qden = d(1e-15) if floor else qraw
            if floor:
                arithmetic["zero_denominator_indices"].append(j)
            quotient = qnum / qden
            equilibrium = ((F * vm - dg) / (R * temperature)).exp()
            a, b, c = (nai / kna) ** 3, (ko / kk) ** 2, atp / katp
            snum, sden = a * b * c, (1 + a) * (1 + b) * (1 + c)
            saturation = snum / sden
            block, rho = d(live["block"][j]), d(live["rho_pump"][j])
            sodium = -3 * block * alpha * saturation * (1 - quotient / equilibrium)
            potassium_flux = -d(2 / 3) * sodium
            proxy[j] = -sodium
            scaled_na[j], scaled_k[j] = rho * sodium, rho * potassium_flux
            applied_na[j], applied_k[j] = scaled_na[j], scaled_k[j]
            # Local first-derivative conditioning; it is reset from the actual
            # incoming parent in conditional checks, never a trajectory bound.
            dsna = (3 * nai**2 / kna**3) * b * c / ((1 + a) ** 2 * (1 + b) * (1 + c))
            dsko = (2 * ko / kk**2) * a * c / ((1 + b) ** 2 * (1 + a) * (1 + c))
            dqna = zero if floor or nai == 0 else -3 * quotient / nai
            dqko = zero if floor or ko == 0 else -2 * quotient / ko
            dqnao = zero if nao == 0 else 3 * quotient / nao
            dqki = zero if ki == 0 else 2 * quotient / ki
            departure_gross = 1 + abs(quotient / equilibrium)
            sensitivities = (
                abs(dsna) * departure_gross + abs(saturation * dqna / equilibrium),
                abs(saturation * dqnao / equilibrium),
                abs(saturation * dqki / equilibrium),
                abs(dsko) * departure_gross + abs(saturation * dqko / equilibrium),
                abs(saturation * quotient / equilibrium) * F / (R * temperature),
            )
            incoming_gross = (
                gross["membrane_mol_m3"][na][j],
                gross["bath_mol_m3"][na],
                gross["membrane_mol_m3"][potassium][j],
                gross["bath_mol_m3"][potassium],
                gross["voltage_V"][j],
            )
            gna = abs(3 * block * alpha) * (
                abs(saturation)
                + abs(saturation * quotient / equilibrium)
                + sum(s * g for s, g in zip(sensitivities, incoming_gross, strict=True))
            )
            proxy_gross[j] = gna
            bound_na[j], bound_k[j] = abs(rho) * gna, abs(rho) * d(2 / 3) * gna
            if (
                not definition["parameters"]["cluster_open"]
                and definition["geometry"]["boundary"][j]
            ):
                applied_na[j] = applied_k[j] = bound_na[j] = bound_k[j] = zero
            entries = (
                qnum,
                qraw,
                qden,
                quotient,
                equilibrium,
                snum,
                sden,
                saturation,
                sodium,
                potassium_flux,
                -sodium,
            )
            keys = tuple(key for key in arithmetic if key != "zero_denominator_indices")
            for key, value in zip(keys, entries, strict=True):
                arithmetic[key].append(value)
    for j in range(m):
        values["membrane_flux_mol_m2_s"][na][j] += applied_na[j]
        values["membrane_flux_mol_m2_s"][potassium][j] += applied_k[j]
        gross["membrane_flux_mol_m2_s"][na][j] += bound_na[j]
        gross["membrane_flux_mol_m2_s"][potassium][j] += bound_k[j]
    return dict(
        arithmetic=arithmetic,
        values=dict(
            scaled_sodium_flux_mol_m2_s=scaled_na,
            scaled_potassium_flux_mol_m2_s=scaled_k,
            applied_sodium_flux_mol_m2_s=applied_na,
            applied_potassium_flux_mol_m2_s=applied_k,
            storage_before_mol_m2_s=before,
            storage_after_mol_m2_s=copy.deepcopy(values["membrane_flux_mol_m2_s"]),
            rate_proxy_before_mol_m2_s=proxy_before,
            rate_proxy_after_mol_m2_s=proxy,
        ),
        flux_gross=copy.deepcopy(gross["membrane_flux_mol_m2_s"]),
        proxy_gross=proxy_gross,
    )


def material_equations_active(inputs, *, refinement=1):
    if refinement not in (1, 2):
        raise ValueError("Require the two independent precision levels")
    with localcontext() as ctx:
        ctx.prec = 90 if refinement == 1 else 140
        raw = inputs["definition"]
        g, ions, p = (raw["geometry"], raw["ions"], raw["parameters"])
        owner, partner = (g["owner"], g["partner"])
        n, m = (len(g["cell_ids"]), len(owner))
        rows = [[j for j, a in enumerate(owner) if a == cell] for cell in range(n)]
        moving = [ions["ids"].index(name) for name in ions["moving_ids"]]
        v = convert(inputs["initial"], d)
        gross = convert(v, abs)
        A, V, length = (
            convert(g[key], d) for key in ("membrane_area_m2", "cell_volume_m3", "gap_length_m")
        )
        norms = convert(g["normal_xy"], d)
        dm, dg = (
            convert(ions[key], d) for key in ("membrane_diffusion_m2_s", "gap_diffusion_m2_s")
        )
        F, R, thickness, fraction, volume_env, pt = (
            d(p[key])
            for key in (
                "F_C_mol",
                "R_J_mol_K",
                "membrane_thickness_m",
                "junction_surface_fraction",
                "bath_volume_m3",
                "configured_temperature_K",
            )
        )
        zero, nonce = (Decimal(0), d(1e-25))
        history = []
        gate_frames = []
        gross["gap_open"] = convert(inputs["gate_input_gross"], d)
        gross["voltage_V"] = convert(inputs["gate_voltage_gross"], d)

        def flux(ca, cb, gca, gcb, diffusion, distance, z, voltage, temperature):
            alpha = z * voltage * F / (R * temperature)
            exponential = (-alpha).exp()
            denominator = 1 - exponential
            factor = -diffusion * alpha / (distance * denominator)
            return (factor * (cb - ca * exponential), abs(factor) * (gcb + gca * abs(exponential)))

        for step_index, forcing in enumerate(inputs["steps"]):
            dt, temperature = (d(forcing["dt_s"]), d(forcing["runtime_temperature_K"]))
            block = convert(forcing["junction_block"], d)
            frames = []
            old = copy.deepcopy(v)
            clipped = [zero for _ in ions["ids"]]

            def observe(stage, i=None, actual_frames=frames):
                actual_frames.append(
                    dict(
                        stage=stage,
                        ion_id=None if i is None else ions["ids"][i],
                        values=copy.deepcopy(v),
                        gross=copy.deepcopy(gross),
                    )
                )

            observe("initial")
            for key in ("membrane_flux_mol_m2_s", "junction_flux_mol_m2_s"):
                v[key] = [[zero] * m for _ in ions["ids"]]
                gross[key] = [[zero] * m for _ in ions["ids"]]
            observe("reset_flux")
            pump_phase_result = pump_phase(
                inputs, v, gross, inputs["steps"][step_index], refinement
            )
            observe("pump_accumulated")
            for i in moving:
                z = d(float(ions["valence"][i]) + 1e-25)
                v["voltage_V"] = [d(float(value) + 1e-25) for value in v["voltage_V"]]
                gross["voltage_V"] = [value + nonce for value in gross["voltage_V"]]
                for j in range(m):
                    value, bound = flux(
                        v["bath_mol_m3"][i],
                        v["membrane_mol_m3"][i][j],
                        gross["bath_mol_m3"][i],
                        gross["membrane_mol_m3"][i][j],
                        dm[i][j],
                        thickness,
                        z,
                        v["voltage_V"][j],
                        temperature,
                    )
                    if not p["cluster_open"] and g["boundary"][j]:
                        value = bound = zero
                    v["membrane_flux_mol_m2_s"][i][j] += value
                    gross["membrane_flux_mol_m2_s"][i][j] += bound
                observe("membrane_flux", i)
                pre_voltage = [v["voltage_V"][partner[j]] - v["voltage_V"][j] for j in range(m)]
                v["junction_field_V_m"] = [-pre_voltage[j] / length[j] for j in range(m)]
                gross["junction_field_V_m"] = [
                    (gross["voltage_V"][partner[j]] + gross["voltage_V"][j]) / length[j]
                    for j in range(m)
                ]
                v["junction_field_xy_V_m"] = [
                    [v["junction_field_V_m"][j] * norms[j][axis] for axis in (0, 1)]
                    for j in range(m)
                ]
                gross["junction_field_xy_V_m"] = [
                    [gross["junction_field_V_m"][j] * abs(norms[j][axis]) for axis in (0, 1)]
                    for j in range(m)
                ]
                answer = gate_step(
                    v["gap_open"],
                    gross["gap_open"],
                    pre_voltage,
                    [gross["voltage_V"][j] + gross["voltage_V"][partner[j]] for j in range(m)],
                    dt,
                    block,
                    inputs["gate_definition"],
                    ions["ids"][i],
                    inputs["gate_update_base"] + len(gate_frames) + 1,
                )
                v["gap_open"], gross["gap_open"] = (answer[0], answer[1])
                gate_frames.append(answer[2])
                v["junction_voltage_V"] = [d(float(value) + 1e-25) for value in pre_voltage]
                gross["junction_voltage_V"] = [
                    gross["voltage_V"][partner[j]] + gross["voltage_V"][j] + nonce for j in range(m)
                ]
                for j in range(m):
                    value, bound = flux(
                        v["membrane_mol_m3"][i][j],
                        v["membrane_mol_m3"][i][partner[j]],
                        gross["membrane_mol_m3"][i][j],
                        gross["membrane_mol_m3"][i][partner[j]],
                        dg[i][j] * fraction * v["gap_open"][j],
                        length[j],
                        z,
                        v["junction_voltage_V"][j],
                        pt,
                    )
                    if g["boundary"][j]:
                        value = bound = zero
                    v["junction_flux_mol_m2_s"][i][j] = value
                    gross["junction_flux_mol_m2_s"][i][j] = bound
                observe("junction_flux", i)
                v["membrane_mol_m3"][i] = [v["cell_mol_m3"][i][a] for a in owner]
                gross["membrane_mol_m3"][i] = [gross["cell_mol_m3"][i][a] for a in owner]
                observe("refresh_at_mem", i)
            channel_result = channel_equations.channels(inputs, v, gross, forcing)
            for i in moving:
                fm, fg = (v["membrane_flux_mol_m2_s"][i], v["junction_flux_mol_m2_s"][i])
                gm, gg = (gross["membrane_flux_mol_m2_s"][i], gross["junction_flux_mol_m2_s"][i])
                for cell, row in enumerate(rows):
                    v["cell_mol_m3"][i][cell] += dt * sum((fm[j] * A[j] for j in row)) / V[cell]
                    gross["cell_mol_m3"][i][cell] += dt * sum((gm[j] * A[j] for j in row)) / V[cell]
                v["membrane_mol_m3"][i] = [v["cell_mol_m3"][i][a] for a in owner]
                gross["membrane_mol_m3"][i] = [gross["cell_mol_m3"][i][a] for a in owner]
                v["bath_mol_m3"][i] -= dt * sum((fm[j] * A[j] for j in range(m))) / (m * volume_env)
                gross["bath_mol_m3"][i] += (
                    dt * sum((gm[j] * A[j] for j in range(m))) / (m * volume_env)
                )
                observe("membrane_commit", i)
                for cell, row in enumerate(rows):
                    v["cell_mol_m3"][i][cell] -= dt * sum((fg[j] * A[j] for j in row)) / V[cell]
                    gross["cell_mol_m3"][i][cell] += dt * sum((gg[j] * A[j] for j in row)) / V[cell]
                observe("junction_commit", i)
                for cell in range(n):
                    if v["cell_mol_m3"][i][cell] < 0:
                        clipped[i] -= v["cell_mol_m3"][i][cell] * V[cell]
                        v["cell_mol_m3"][i][cell] = zero
                observe("clip_bulk", i)
            history.append(
                dict(
                    step_index=step_index + 1,
                    frames=frames,
                    final_state=copy.deepcopy(v),
                    final_gross=copy.deepcopy(gross),
                    clipping_added_mol=clipped,
                    cell_change_mol=[
                        sum(
                            (
                                (v["cell_mol_m3"][i][j] - old["cell_mol_m3"][i][j]) * V[j]
                                for j in range(n)
                            )
                        )
                        for i in range(len(ions["ids"]))
                    ],
                    bath_change_mol=[
                        (v["bath_mol_m3"][i] - old["bath_mol_m3"][i]) * volume_env
                        for i in range(len(ions["ids"]))
                    ],
                )
            )
        return convert(
            dict(
                history=history,
                decimal_precision=ctx.prec,
                refinement=refinement,
                gate_updates=gate_frames,
                pump_phase=pump_phase_result,
                channels=channel_result,
            ),
            lambda value: float(value) if isinstance(value, Decimal) else value,
        )


def transport_gross(inputs, old, forcing, carried, gate_bounds, pump_bounds):
    """Propagate gross scales through feedback using |Bernoulli'(x)| <= 1.

    The GHK flux is D/d*(ca*B(alpha)-cb*B(-alpha)). For real alpha,
    |B(alpha)| <= 1+|alpha| and |B'(alpha)| <= 1. These scalar bounds carry
    prior voltage cancellation scales into fluxes and subsequent amounts.
    """
    raw = inputs["ion_definition"]
    g, species, p = (raw["geometry"], raw["ions"], raw["parameters"])
    owner, partner = (g["owner"], g["partner"])
    count, m = (len(species["ids"]), len(owner))
    out = copy.deepcopy(carried)
    gm = copy.deepcopy(pump_bounds)
    gg = [[0.0] * m for _ in range(count)]
    dt = forcing["material"]["dt_s"]
    gv = [x + len(species["moving_ids"]) * 1e-25 for x in carried["voltage_V"]]
    ggap = [gv[j] + gv[partner[j]] + 1e-25 for j in range(m)]
    for name in species["moving_ids"]:
        i = species["ids"].index(name)
        z = abs(float(species["valence"][i]) + 1e-25)
        km = z * p["F_C_mol"] / (p["R_J_mol_K"] * forcing["material"]["runtime_temperature_K"])
        kg = z * p["F_C_mol"] / (p["R_J_mol_K"] * p["configured_temperature_K"])
        for j in range(m):
            cg = carried["bath_mol_m3"][i] + carried["membrane_mol_m3"][i][j]
            gm[i][j] += (
                species["membrane_diffusion_m2_s"][i][j]
                / p["membrane_thickness_m"]
                * cg
                * (1 + km * (abs(old["voltage_V"][j]) + gv[j]))
            )
            cg = carried["membrane_mol_m3"][i][j] + carried["membrane_mol_m3"][i][partner[j]]
            gg[i][j] = (
                species["gap_diffusion_m2_s"][i][j]
                * p["junction_surface_fraction"]
                * gate_bounds[i][j]
                / g["gap_length_m"][j]
                * cg
                * (1 + kg * (abs(old["voltage_V"][partner[j]] - old["voltage_V"][j]) + ggap[j]))
            )
            if g["boundary"][j]:
                gg[i][j] = 0.0
                if not p["cluster_open"]:
                    gm[i][j] = 0.0
        for cell in range(len(g["cell_ids"])):
            row = [j for j, a in enumerate(owner) if a == cell]
            membrane_add = (
                dt
                * sum((gm[i][j] * g["membrane_area_m2"][j] for j in row))
                / g["cell_volume_m3"][cell]
            )
            gap_add = (
                dt
                * sum((gg[i][j] * g["membrane_area_m2"][j] for j in row))
                / g["cell_volume_m3"][cell]
            )
            out["cell_mol_m3"][i][cell] = carried["cell_mol_m3"][i][cell] + membrane_add + gap_add
            for j in row:
                out["membrane_mol_m3"][i][j] = carried["cell_mol_m3"][i][cell] + membrane_add
        out["bath_mol_m3"][i] = carried["bath_mol_m3"][i] + dt * sum(
            (gm[i][j] * g["membrane_area_m2"][j] for j in range(m))
        ) / (m * p["bath_volume_m3"])
    if not species["moving_ids"]:
        out.update(membrane_flux_mol_m2_s=gm, junction_flux_mol_m2_s=gg)
        return out
    out.update(
        membrane_flux_mol_m2_s=gm,
        junction_flux_mol_m2_s=gg,
        voltage_V=gv,
        junction_voltage_V=ggap,
        junction_field_V_m=[ggap[j] / g["gap_length_m"][j] for j in range(m)],
        junction_field_xy_V_m=[
            [ggap[j] / g["gap_length_m"][j] * abs(g["normal_xy"][j][a]) for a in (0, 1)]
            for j in range(m)
        ],
        gap_open=[gate_bounds[i][j] for j in range(m)],
    )
    return out


def evaluate(inputs, *, refinement=1, mode="carried"):
    if refinement not in (1, 2) or mode not in ("carried", "conditional_local"):
        raise ValueError("Require declared precision and carried/actual-parent local mode")
    if mode == "conditional_local":
        if (
            len(inputs["drives"]) != 1
            or not inputs.get("actual_parent_identity")
            or "actual_gate_memory" not in inputs
        ):
            raise ValueError(
                "Conditional checks require exactly one call and full recorded incoming state"
            )
        gate_cache = copy.deepcopy(inputs["actual_gate_memory"])
        channel_caches = copy.deepcopy(inputs["actual_channel_caches"])
        channel_calls = list(inputs["actual_channel_calls"])
    else:
        gate_cache = initialize(inputs, refinement)
        channel_caches = channel_equations.initialize(inputs, refinement)
        channel_calls = [0] * len(channel_caches)
    initial_cache = copy.deepcopy(gate_cache)
    state = copy.deepcopy(inputs["initial"])
    proxy = copy.deepcopy(inputs["initial_rate_proxy_mol_m2_s"])
    names = inputs["ion_definition"]["ions"]["ids"]
    history = []
    for forcing in inputs["drives"]:
        # These are conditional, single-call scales, not propagated trajectory
        # bounds. Full carried errors remain separate diagnostic measurements.
        carried = tree(state, abs)
        old = state
        active = material_equations_active(
            dict(
                definition=inputs["ion_definition"],
                initial=state,
                steps=[forcing["material"]],
                gate_definition=inputs["gate_definition"],
                gate_input_gross=carried["gap_open"],
                gate_voltage_gross=carried["voltage_V"],
                gate_update_base=gate_cache["updates"],
                pump_definition=inputs["pump_definition"],
                pump_packet=forcing["pump"],
                incoming_rate_proxy_mol_m2_s=proxy,
                channel_definition=inputs["channel_definition"],
                channel_packet=forcing["channels"],
                channel_caches=channel_caches,
                channel_calls=channel_calls,
                refinement=refinement,
            ),
            refinement=refinement,
        )
        material = active["history"][0]
        state = material["final_state"]
        pump = active["pump_phase"]
        channel_result = active["channels"]
        channel_caches, channel_calls = channel_result["caches"], channel_result["calls"]
        gate_bounds = [[0.0] * len(inputs["initial"]["voltage_V"]) for _ in names]
        for gate in active["gate_updates"]:
            gate_bounds[names.index(gate["ion_id"])] = gate["gross"]["opening_stored"]
            for key in ("alpha_per_ms", "raw_beta_per_ms", "beta_per_ms"):
                gate_cache[key] = gate["values"][key]
            gate_cache["updates"] = gate["update_index"]
        material_gross = transport_gross(
            inputs, old, forcing, carried, gate_bounds, pump["flux_gross"]
        )
        channel_result_decimal = convert(
            channel_result,
            lambda v: d(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else v,
        )
        material_gross = channel_equations.augment_gross(
            material_gross,
            channel_result_decimal,
            [names.index(name) for name in inputs["ion_definition"]["ions"]["moving_ids"]],
            inputs["ion_definition"]["geometry"]["owner"],
        )
        published = forcing["channels"]["substances_affect_charge"]
        actual_extra_current = (
            channel_result["extra_current"] if published else forcing["extra_current_A_m2"]
        )
        actual_extra_charge = (
            [0.0] * len(state["cell_mol_m3"][0]) if published else forcing["extra_charge_C_m3"]
        )
        current_source = dict(
            cell_mol_m3=state["cell_mol_m3"],
            membrane_flux_mol_m2_s=state["membrane_flux_mol_m2_s"],
            junction_flux_mol_m2_s=state["junction_flux_mol_m2_s"],
            extra_charge_C_m3=actual_extra_charge,
            extra_current_A_m2=actual_extra_current,
        )
        readout = current_equations(
            inputs["current_definition"], current_source, refinement=refinement
        )
        gross_source = dict(
            cell_mol_m3=material_gross["cell_mol_m3"],
            membrane_flux_mol_m2_s=material_gross["membrane_flux_mol_m2_s"],
            junction_flux_mol_m2_s=material_gross["junction_flux_mol_m2_s"],
            extra_charge_C_m3=tree(actual_extra_charge, abs),
            extra_current_A_m2=channel_result["extra_current_gross"]
            if published
            else tree(actual_extra_current, abs),
        )
        readout["gross"] = current_equations(
            inputs["current_definition"], gross_source, refinement=refinement
        )["gross"]
        voltage = voltage_equations(inputs, state, readout, forcing, refinement, material_gross)
        before = copy.deepcopy(state)
        state = copy.deepcopy(state)
        state["voltage_V"] = voltage["values"]["voltage_V"]
        proxy = pump["values"]["rate_proxy_after_mol_m2_s"]
        history.append(
            dict(
                material_state=before,
                material_gross=material_gross,
                current=readout,
                voltage=voltage,
                final_state=state,
                gate_updates=active["gate_updates"],
                gate_cache=copy.deepcopy(gate_cache),
                pump=pump,
                channels=channel_result,
                rate_proxy=proxy,
            )
        )
    return dict(
        history=history,
        initialization=initial_cache,
        refinement=refinement,
        decimal_precision=90 if refinement == 1 else 140,
        mode=mode,
        conditional_on_actual_parent_identity=inputs.get("actual_parent_identity")
        if mode == "conditional_local"
        else None,
        carried_local_scales_are_not_trajectory_error_bounds=True,
        carried_profile_is_diagnostic_only=mode == "carried",
    )


def main():
    import argparse
    import builtins
    import importlib.abc
    import json
    import sys
    from pathlib import Path

    parser = argparse.ArgumentParser()
    parser.add_argument("--inputs", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--refinement", type=int, choices=(1, 2), required=True)
    parser.add_argument("--mode", choices=("carried", "conditional_local"), required=True)
    args = parser.parse_args()
    blocked = {"cells", "betse", "numpy", "jax", "jaxlib"}
    original = builtins.__import__

    def guarded(name, *values, **kwargs):
        if name.split(".")[0] in blocked:
            raise ImportError("Pump reference import denied: " + name)
        return original(name, *values, **kwargs)

    class Guard(importlib.abc.MetaPathFinder):
        def find_spec(self, fullname, path=None, target=None):
            if fullname.split(".")[0] in blocked:
                raise ImportError("Reference import denied: " + fullname)

    builtins.__import__ = guarded
    sys.meta_path.insert(0, Guard())
    result = evaluate(
        json.loads(args.inputs.read_text()), refinement=args.refinement, mode=args.mode
    )
    loaded = [name for name in sys.modules if name.split(".")[0] in blocked]
    if loaded:
        raise ValueError("Independent reference loaded production/numerical packages")
    result.update(
        production_imports_denied=True,
        loaded_production_modules=loaded,
        runtime=runtime_inventory(),
    )
    with args.output.open("x") as stream:
        json.dump(result, stream, indent=2, allow_nan=False)
        stream.write("\n")
    print(
        json.dumps(
            dict(
                mode=args.mode,
                calls=len(result["history"]),
                decimal_precision=result["decimal_precision"],
            )
        )
    )


if __name__ == "__main__":
    main()
