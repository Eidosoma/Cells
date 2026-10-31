"""Independent ECM modern channels, CaATP, material, GRN and full-field conditionals.

No native or numerical-package imports. Each boundary starts from archived actual
inputs; no independently carried trajectory or native enabled-ER claim follows.
"""

import copy
import json
from decimal import Decimal, localcontext
from pathlib import Path

from validation.betse import betse_ecm_cal2_reference as ecm_cal2
from validation.betse import betse_ecm_reference_failure as reference_failure
from validation.betse import betse_ecm_sodium_reference as ecm_sodium
from validation.betse import betse_ecm_transport_reference as ordinary
from validation.betse import betse_environment_field_reference as environment
from validation.betse import betse_normal_ecm_field_join_reference as full
from validation.betse.betse_normal_catalog_join_scalar import (
    cav_kinetics,
    hcn_kinetics,
    kv1_kinetics,
)
from validation.channels import calcium_catalog_extra_reference as calcium_gates
from validation.channels import hcn_extra_reference as hcn
from validation.channels import morris_lecar_channels_reference as ml
from validation.channels import potassium_catalog_reference as potassium
from validation.channels import sodium_catalog_reference as sodium

deepcopy = copy.deepcopy
numbers, flux, smooth = (ordinary.numbers, ordinary.flux, ordinary.smooth)
geometry, serial = (environment.geometry, environment.serial)
_combine, _derivative, _flatten, _reshape = (
    environment._combine,
    environment._derivative,
    environment._flatten,
    environment._reshape,
)


def d(value):
    return value if isinstance(value, Decimal) else Decimal.from_float(float(value))


def native_parameters(policy):
    return dict(
        cATP=1.5,
        cADP=0.1,
        cPi=0.1,
        KmCa_Ca=0.001,
        KmCa_ATP=0.5,
        deltaGATP=-37000,
        alpha_Ca=policy["alpha_Ca"],
        F=96485,
        R=8.314,
    )


def calcium_equations(v, policy, p, incoming, mapping, boundary, cluster_open, temperature):
    i = policy["Ca_index"]
    m = len(v["voltage_V"])
    applied = [Decimal(0)] * m
    rate = copy.deepcopy(incoming)
    arithmetic = None
    if d(policy["alpha_Ca"]) > 0:
        ci = list(map(d, v["membrane_mol_m3"][i]))
        co = [d(v["environment_mol_m3"][i][k]) for k in mapping]
        arithmetic = dict(before_no_negs_membrane=ci[:], before_no_negs_bath=co[:])
        ci = [max(Decimal(0), c) for c in ci]
        co = [max(Decimal(0), c) for c in co]
        arithmetic.update(after_no_negs_membrane=ci[:], after_no_negs_bath=co[:])
        v["membrane_mol_m3"][i] = ci
        labels = (
            "quotient_numerator",
            "quotient_denominator_raw",
            "quotient_denominator_used",
            "quotient",
            "equilibrium",
            "forward_numerator",
            "forward_denominator",
            "forward",
            "backward_numerator_unused",
            "backward_denominator_unused",
            "backward_unused",
            "raw_flux_mol_m2_s",
        )
        arithmetic.update({key: [] for key in labels})
        zeros = []
        atp, adp, pi, F, R, kc, ka, dg = (
            d(p[key])
            for key in ("cATP", "cADP", "cPi", "F", "R", "KmCa_Ca", "KmCa_ATP", "deltaGATP")
        )
        T = d(temperature)
        for j in range(m):
            qnum = adp * pi * co[j]
            qraw = atp * ci[j]
            stored_product = float(p["cATP"]) * float(ci[j])
            qden = d(1e-16) if stored_product == 0 else qraw
            if stored_product == 0:
                zeros.append(j)
            quotient = qnum / qden
            equilibrium = (-(dg / (R * T) - 2 * F * d(v["voltage_V"][j]) / (R * T))).exp()
            fn = ci[j] / kc * (atp / ka)
            fd = (1 + ci[j] / kc) * (1 + atp / ka)
            forward = fn / fd
            bn, bd = (co[j] / kc, 1 + co[j] / kc)
            backward = bn / bd
            value = -d(policy["alpha_Ca"]) * forward * (1 - quotient / equilibrium)
            for key, item in zip(
                labels,
                (qnum, qraw, qden, quotient, equilibrium, fn, fd, forward, bn, bd, backward, value),
                strict=True,
            ):
                arithmetic[key].append(item)
            applied[j] = Decimal(0) if not cluster_open and boundary[j] else value
            v["membrane_flux_mol_m2_s"][i][j] += applied[j]
        arithmetic["zero_denominator_indices"] = zeros
        rate = dict(present=True, value=applied[:])
    return dict(
        arithmetic=arithmetic,
        rate_cache_after=rate,
        applied_flux_mol_m2_s=applied,
        values_after=copy.deepcopy(v),
        ER_executed=False,
        Ca_dyn=False,
        conditional_before_calcium=True,
    )


def calcium(inputs, *, refinement=1):
    if refinement not in (1, 2):
        raise ValueError("Require declared independent precision")
    with localcontext() as ctx:
        ctx.prec = 100 if refinement == 1 else 160
        external = inputs["definition"]["environment_geometry_definition"]
        g = environment.geometry(external, precision=ctx.prec)
        values = full.tree(inputs["values_before"], d)
        policy = dict(
            alpha_Ca=inputs["alpha_Ca"],
            Ca_index=external["current_definition"]["ions"]["ids"].index("Ca"),
        )
        result = calcium_equations(
            values,
            policy,
            inputs["parameters"],
            inputs["rate_cache_before"],
            g["membrane_to_grid"],
            inputs["definition"]["junction_geometry"]["boundary"],
            inputs["definition"]["parameters"]["cluster_open"],
            inputs["runtime_temperature_K"],
        )
        result.update(
            mode="calcium",
            decimal_precision=ctx.prec,
            carried_reference_forms=0,
            fresh_conditional_reference=True,
            physical_global_conservation_credit=False,
            formal_ATP_consumption_claim=False,
        )
        return serial(result)


def inventory():
    return json.loads(
        Path(__file__).with_name("betse_normal_catalog_join_inventory.json").read_text()
    )


def kinetics(name, voltage, refinement):
    family = inventory()["classes"][name]["family"]
    precision = 100 if refinement == 1 else 160
    if name == "NaLeak":
        # Native leak targets and time constants are voltage independent. The
        # standalone sodium oracle keeps its own bounded-voltage contract.
        sodium._d(voltage, "voltage")
        return ([Decimal(1), Decimal(1)], [Decimal(1), Decimal(1)])
    if name == "CaLeak":
        # Native CaLeak gates are constant; retain finite/type admission while
        # the standalone calcium oracle keeps its bounded-voltage contract.
        calcium_gates._d(voltage, "voltage")
        return ([Decimal(1), Decimal(1)], [Decimal(1), Decimal(1)])
    if family == "Na":
        return ecm_sodium.kinetics(voltage, name, precision=precision)
    if family == "K":
        return (
            kv1_kinetics(voltage, int(name[-1]), precision=precision)
            if name.startswith("Kv1p")
            else potassium._kinetics(voltage, name)
        )
    if name == "Ca_L2":
        return ecm_cal2.kinetics(voltage, name, precision=precision)
    if family == "Ca":
        return (
            calcium_gates._kinetics(voltage, name)
            if name in ("Ca_L2", "Ca_L3", "Cav_G", "CaLeak")
            else cav_kinetics(voltage, name, precision=precision)
        )
    if family == "Fun":
        return (
            hcn._kinetics(voltage, name)
            if name in ("HCNLeak", "HCN2_cAMP", "HCN4_cAMP")
            else hcn_kinetics(voltage, int(name[3:]), precision=precision)
        )
    if family in ("Cl", "Cat"):
        return ([Decimal(1), Decimal(1)], [Decimal(1), Decimal(1)])
    target, tau, _, _, _, _ = ml._values(voltage, name)
    return ([target], [tau])


def modulation(row, values, molecules, names, mapping):
    m = len(mapping)
    result = [Decimal(1)] * m
    for role in ("activator", "inhibitor"):
        species = row.get("channel " + role + "s") or []
        zones = row.get(role + " zone") or ["cell"] * len(species)
        for label, km, power, zone in zip(
            species, row.get(role + " Km") or [], row.get(role + " n") or [], zones, strict=True
        ):
            if label in names:
                samples = (
                    values["membrane_mol_m3"][names.index(label)]
                    if zone == "cell"
                    else [
                        values["environment_mol_m3"][names.index(label)][site] for site in mapping
                    ]
                )
            else:
                samples = (
                    molecules[label]["cc_at_mem"]
                    if zone == "cell"
                    else [molecules[label]["c_env"][site] for site in mapping]
                )
            for j, sample in enumerate(samples):
                hill = (d(sample) / d(km)) ** d(power)
                result[j] *= hill / (1 + hill) if role == "activator" else 1 / (1 + hill)
    return result


def channel_sequence(inputs, *, refinement=1, values=None):
    with localcontext() as context:
        context.prec = 100 if refinement == 1 else 160
        raw = inputs["material_declaration"]
        external = raw["environment_geometry_definition"]
        current = external["current_definition"]
        names = current["ions"]["ids"]
        zvals = current["ions"]["valence"]
        cg = current["geometry"]
        geom = geometry(external, precision=context.prec)
        mapping = geom["membrane_to_grid"]
        owner = cg["owner"]
        area = numbers(cg["membrane_area_m2"])
        volume = numbers(external["geometry"]["cell_volume_m3"])
        site_volume = d(external["parameters"]["cell_height_m"]) * geom["delta_m"] ** 2
        m, n, e = (len(owner), len(volume), len(geom["grid_points_m"]))
        F, R, tm, dt, T = (
            d(inputs[k])
            for k in ("F", "R", "membrane_thickness_m", "dt_s", "runtime_temperature_K")
        )
        v = numbers(inputs["values_before"]) if values is None else values
        start = copy.deepcopy(v)
        wire = inputs["cache_before"]["wire"]
        molecules = wire["molecule_fields"]
        extra = numbers(inputs["incoming_channel_current_A_m2"])
        extra_gross = [abs(x) for x in extra]
        cell_add = [[Decimal(0)] * n for _ in names]
        mem_add = [[Decimal(0)] * m for _ in names]
        env_add = [[Decimal(0)] * e for _ in names]
        books = []
        events = []
        nonce = 0
        for row in inputs["catalog"]["populations"] or []:
            name, cls = (row["name"], row["channel type"])
            entry = inventory()["classes"][cls]
            cache = copy.deepcopy(wire["channel_fields"][name]["core_fields"])
            targets = cache["targets"]
            moddy = modulation(row, v, molecules, names, mapping)
            gates = ("m",) if entry["family"] == "ML" else ("m", "h")
            updated = {key: [] for key in gates}
            for slot, j in enumerate(targets):
                try:
                    target, tau = kinetics(cls, d(float(v["voltage_V"][j])), refinement)
                except Exception as error:
                    # Retain the reached conditional state before propagating
                    # the original class/message/cause. No model is rerun.
                    try:
                        error.reference_partial = dict(
                            stage="channel_kinetics",
                            population_name=name,
                            class_name=cls,
                            target_slot=slot,
                            membrane_index=j,
                            decimal_precision=context.prec,
                            actual_gate_input_V=d(float(v["voltage_V"][j])),
                            values_before_failed_gate=copy.deepcopy(v),
                            cache_before_failed_population=copy.deepcopy(cache),
                            updated_gates_partial=copy.deepcopy(updated),
                            completed_population_books=copy.deepcopy(books),
                            completed_population_events=copy.deepcopy(events),
                            source_voltage_nonce_count=nonce,
                        )
                    except Exception as capture_error:
                        error.add_note("Reference partial capture refused: " + str(capture_error))
                    raise
                for a, key in enumerate(gates):
                    old = cache[key][slot] if isinstance(cache[key], (tuple, list)) else cache[key]
                    updated[key].append(
                        target[a]
                        if entry["family"] == "ML" and cls not in ml.KINETIC
                        else (tau[a] * d(old) + dt * target[a]) / (tau[a] + dt)
                    )
            opening = [Decimal(0)] * m
            powers = (
                (1, 0)
                if entry["family"] == "ML"
                else (int(cache["_mpower"]), int(cache["_hpower"]))
            )
            for k, j in enumerate(targets):
                a, b = powers
                opening[j] = (updated["m"][k] ** a if a else Decimal(1)) * (
                    updated["h"][k] ** b if b else Decimal(1)
                )
            routes = []
            maxdm = d(
                row.get("max conductivity")
                if row.get("max conductivity") is not None
                else row["max Dm"]
            )
            for ion, relative in entry["routes"]:
                i = names.index(ion)
                diffusion = [
                    x * d(relative) * maxdm * y for x, y in zip(opening, moddy, strict=True)
                ]
                before_cell = v["cell_mol_m3"][i][:]
                before_mem = v["membrane_mol_m3"][i][:]
                before_env = v["environment_mol_m3"][i][:]
                sampled_mem = [before_cell[a] for a in owner]
                sampled_env = [before_env[k] for k in mapping]
                v["voltage_V"] = [d(float(x) + 1e-25) for x in v["voltage_V"]]
                nonce += 1
                z = d(float(zvals[i]) + 1e-25)
                fluxes = []
                gross = []
                for j in range(m):
                    alpha = z * v["voltage_V"][j] * F / (R * T)
                    exp = (-alpha).exp()
                    rho = d(inputs["rho_channel"][j])
                    fluxes.append(
                        -diffusion[j]
                        * alpha
                        / tm
                        * (sampled_mem[j] - sampled_env[j] * exp)
                        / (1 - exp)
                        * rho
                    )
                    probability = max(Decimal(1), abs(opening[j]))
                    dscale = probability * abs(d(relative) * maxdm * moddy[j] * rho)
                    concentration = (
                        abs(sampled_mem[j])
                        + abs(sampled_env[j])
                        + cell_add[i][owner[j]]
                        + env_add[i][mapping[j]]
                    )
                    gross.append(dscale / tm * concentration * (1 + 2 * abs(alpha)))
                for a in range(n):
                    v["cell_mol_m3"][i][a] += (
                        dt
                        * sum((fluxes[j] * area[j] for j in range(m) if owner[j] == a))
                        / volume[a]
                    )
                    cell_add[i][a] += (
                        dt
                        * sum((gross[j] * area[j] for j in range(m) if owner[j] == a))
                        / volume[a]
                    )
                v["membrane_mol_m3"][i] = [v["cell_mol_m3"][i][a] for a in owner]
                mem_add[i] = [cell_add[i][a] for a in owner]
                conservative = before_env[:]
                for j, site in enumerate(mapping):
                    conservative[site] -= dt * fluxes[j] * area[j] / site_volume
                if raw["parameters"]["fast_update_ecm"]:
                    last = [Decimal(0)] * e
                    last_gross = [Decimal(0)] * e
                    for j, site in enumerate(mapping):
                        last[site] = -fluxes[j]
                        last_gross[site] = gross[j]
                    rates = [
                        last[k] * geom["membrane_area_per_site_m2"][k] / site_volume
                        for k in range(e)
                    ]
                    rate_gross = [
                        last_gross[k] * geom["membrane_area_per_site_m2"][k] / site_volume
                        for k in range(e)
                    ]
                else:
                    rates = [
                        -sum((fluxes[j] * area[j] for j in range(m) if mapping[j] == k))
                        / site_volume
                        for k in range(e)
                    ]
                    rate_gross = [
                        sum((gross[j] * area[j] for j in range(m) if mapping[j] == k)) / site_volume
                        for k in range(e)
                    ]
                v["environment_mol_m3"][i] = [
                    x + dt * r for x, r in zip(before_env, rates, strict=True)
                ]
                env_add[i] = [a + dt * b for a, b in zip(env_add[i], rate_gross, strict=True)]
                extra = [a - f * F * d(zvals[i]) for a, f in zip(extra, fluxes, strict=True)]
                extra_gross = [
                    a + f * F * abs(d(zvals[i])) for a, f in zip(extra_gross, gross, strict=True)
                ]
                transfer = dt * sum((f * a for f, a in zip(fluxes, area, strict=True)))
                cell_amount = sum(
                    (
                        (a - b) * vol
                        for a, b, vol in zip(v["cell_mol_m3"][i], before_cell, volume, strict=True)
                    )
                )
                effective = sum(
                    (
                        (a - b) * site_volume
                        for a, b in zip(v["environment_mol_m3"][i], before_env, strict=True)
                    )
                )
                conservative_amount = sum(
                    ((a - b) * site_volume for a, b in zip(conservative, before_env, strict=True))
                )
                book = dict(
                    population=name,
                    ion=ion,
                    membrane_transfer_mol=transfer,
                    cell_change_mol=cell_amount,
                    source_effective_environment_change_mol=effective,
                    source_effective_balance_mol=cell_amount + effective,
                    conservative_environment_change_mol=conservative_amount,
                    conservative_balance_mol=cell_amount + conservative_amount,
                    true_grid_environment_change_mol=sum(
                        (
                            (a - b) * vol
                            for a, b, vol in zip(
                                v["environment_mol_m3"][i],
                                before_env,
                                geom["true_environment_volume_m3"],
                                strict=True,
                            )
                        )
                    ),
                    source_minus_conservative_environment_mol=effective - conservative_amount,
                )
                books.append(book)
                routes.append(
                    dict(
                        ion_id=ion,
                        relative_permeability=relative,
                        DChan=diffusion,
                        chan_flux=fluxes,
                        flux_gross=gross,
                        sampled_bulk_at_membrane=sampled_mem,
                        sampled_environment_at_membrane=sampled_env,
                        stored_membrane_before=before_mem,
                        network_current=extra[:],
                        network_current_gross=extra_gross[:],
                        cell_after=v["cell_mol_m3"][i][:],
                        membrane_after=v["membrane_mol_m3"][i][:],
                        environment_after=v["environment_mol_m3"][i][:],
                        book=book,
                    )
                )
            events.append(
                dict(
                    name=name,
                    class_name=cls,
                    targets=targets,
                    modulator=moddy,
                    **updated,
                    P=opening,
                    routes=routes,
                )
            )
        return dict(
            events=events,
            values_after=copy.deepcopy(v),
            values_before=start,
            extra_current=extra,
            extra_current_gross=extra_gross,
            cell_gross_add=cell_add,
            membrane_gross_add=mem_add,
            environment_gross_add=env_add,
            voltage_nonce_count=nonce,
            amount_books=books,
            decimal_precision=context.prec,
            carried_reference_forms=0,
            fresh_conditional_reference=True,
            physical_global_conservation_credit=False,
            independent_constructor_credit=False,
        )


def material_channel_inputs(inputs, packet, v):
    raw = inputs["definition"]
    return dict(
        material_declaration=raw,
        catalog=inputs["catalog"],
        values_before=v,
        cache_before=inputs["network_cache"],
        incoming_channel_current_A_m2=[0.0] * len(v["voltage_V"]),
        F=raw["environment_geometry_definition"]["current_definition"]["parameters"]["F_C_mol"],
        R=raw["parameters"]["R_J_mol_K"],
        membrane_thickness_m=raw["parameters"]["membrane_thickness_m"],
        dt_s=packet["dt_s"],
        runtime_temperature_K=packet["runtime_temperature_K"],
        rho_channel=packet["channel_multiplier"],
    )


def evaluate(inputs, *, refinement=1):
    if inputs.get("mode") == "channels":
        return serial(dict(channel_sequence(inputs, refinement=refinement), mode="channels"))
    if inputs.get("mode") == "calcium":
        return calcium(inputs, refinement=refinement)
    if inputs.get("mode") == "material":
        adapted = copy.deepcopy(inputs)
        adapted["calcium"]["Ca_index"] = inputs["definition"]["environment_geometry_definition"][
            "current_definition"
        ]["ions"]["ids"].index("Ca")
        result = material_model(adapted, refinement=refinement)
        result.update(
            mode="material",
            decimal_precision=result["precision"],
            carried_reference_forms=0,
            fresh_conditional_reference=True,
            physical_global_conservation_credit=False,
        )
        return result
    result = full.evaluate(inputs, refinement=refinement)
    if inputs.get("mode") == "cold_initialization":
        result["owner_fields"]["channels"] = inputs["catalog"]["populations"] is not None
    if inputs.get("mode") == "cold_initialization":
        end = 3 * float(inputs["bootstrap_dt_s"])
        result.update(
            native_policy=dict(
                Ca_dyn=False,
                CaATP_block=[1.0] * inputs["membranes"],
                rho_pump=1,
                met_concs=None,
                endo_retic=None,
                rate_CaATP_present=False,
                parameters=native_parameters(inputs["calcium_configuration"]),
            ),
            clock=dict(source_times_s=[0.0, end / 2, end], call_index=0, material_dt_sum_s=0.0),
        )
    return result


def material_model(inputs, *, refinement=1, retain_decimal=None):
    if refinement not in (1, 2):
        raise ValueError("Require the declared independent precision settings")
    if retain_decimal is not None and (not callable(retain_decimal)):
        raise ValueError("Decimal retention requires an explicit callable")

    def finish(result):
        if retain_decimal is not None:
            retain_decimal(deepcopy(result))
        return serial(result)

    with localcontext() as context:
        context.prec = 100 if refinement == 1 else 160
        raw = inputs["definition"]
        external, junction, ions, p = (
            raw[key]
            for key in (
                "environment_geometry_definition",
                "junction_geometry",
                "ions",
                "parameters",
            )
        )
        cg, cd = (external["current_definition"]["geometry"], external["current_definition"])
        names, valence = (cd["ions"]["ids"], cd["ions"]["valence"])
        g = geometry(external, precision=context.prec)
        ny, nx = g["shape"]
        s, m, n, e = (len(names), len(cg["membrane_ids"]), len(cg["cell_ids"]), ny * nx)
        owner, partner, mapping = (cg["owner"], junction["partner"], g["membrane_to_grid"])
        moving = [names.index(name) for name in ions["moving_ids"]]
        area, volume = (
            numbers(cg["membrane_area_m2"]),
            numbers(external["geometry"]["cell_volume_m3"]),
        )
        site_volume = d(external["parameters"]["cell_height_m"]) * g["delta_m"] ** 2
        length, weights = (numbers(junction["gap_length_m"]), numbers(junction["gap_weights"]))
        normal = numbers(cg["normal_xy"])
        dm, dg, de, tj = (
            numbers(ions[key])
            for key in (
                "membrane_diffusion_m2_s",
                "gap_diffusion_m2_s",
                "environment_diffusion_m2_s",
                "tight_junction_modulator",
            )
        )
        F, R, thickness, fraction, configured_T = (
            d(cd["parameters"]["F_C_mol"]),
            d(p["R_J_mol_K"]),
            d(p["membrane_thickness_m"]),
            d(p["gap_surface_fraction"]),
            d(external["parameters"]["configured_temperature_K"]),
        )
        q, kb = (d(external["parameters"]["q_C"]), d(external["parameters"]["kb_J_K"]))
        zero = Decimal(0)
        v = numbers(inputs["initial"])
        history = []
        for packet_raw in inputs["steps"]:
            packet = numbers(packet_raw)
            dt, temperature = (packet["dt_s"], packet["runtime_temperature_K"])
            old = deepcopy(v)
            frames, environment_records, conservative_exchange = ([], [], [])
            clamp, collocated, smoothing, exchange, clip = ([zero] * s for _ in range(5))
            requested_gap_outward_increment = [[zero] * n for _ in range(s)]

            def observe(stage, i=None, destination=frames):
                destination.append(
                    dict(stage=stage, ion_id=None if i is None else names[i], values=deepcopy(v))
                )

            observe("initial")
            for key, count in (
                ("membrane_flux_mol_m2_s", m),
                ("junction_flux_mol_m2_s", m),
                ("environment_flux_x_mol_m2_s", e),
                ("environment_flux_y_mol_m2_s", e),
            ):
                v[key] = [[zero] * count for _ in range(s)]
            observe("reset_flux")
            for i in range(s):
                v["membrane_flux_mol_m2_s"][i] = packet["supplied_pump_membrane_flux_mol_m2_s"][i][
                    :
                ]
            observe("supplied_pump_flux")
            for i in moving:
                z = d(float(valence[i]) + 1e-25)
                v["voltage_V"] = [d(float(value) + 1e-25) for value in v["voltage_V"]]
                for j in range(m):
                    value = flux(
                        v["environment_mol_m3"][i][mapping[j]],
                        v["membrane_mol_m3"][i][j],
                        dm[i][j],
                        thickness,
                        z,
                        v["voltage_V"][j],
                        temperature,
                        F,
                        R,
                        packet["channel_multiplier"][j],
                    )
                    if not p["cluster_open"] and junction["boundary"][j]:
                        value = zero
                    v["membrane_flux_mol_m2_s"][i][j] += value
                observe("membrane_flux", i)
                pre_gap_voltage = [v["voltage_V"][partner[j]] - v["voltage_V"][j] for j in range(m)]
                v["junction_field_source"] = [-pre_gap_voltage[j] / length[j] for j in range(m)]
                v["junction_field_xy_source"] = [
                    [v["junction_field_source"][j] * normal[j][axis] for axis in (0, 1)]
                    for j in range(m)
                ]
                v["gap_open"] = [packet["junction_block"][j] * weights[j] for j in range(m)]
                v["junction_voltage_V"] = [d(float(value) + 1e-25) for value in pre_gap_voltage]
                for j in range(m):
                    value = flux(
                        v["membrane_mol_m3"][i][j],
                        v["membrane_mol_m3"][i][partner[j]],
                        dg[i][j] * fraction * v["gap_open"][j],
                        length[j],
                        z,
                        v["junction_voltage_V"][j],
                        configured_T,
                        F,
                        R,
                        Decimal(1),
                    )
                    if junction["boundary"][j]:
                        value = zero
                    v["junction_flux_mol_m2_s"][i][j] = value
                observe("junction_flux", i)
                before = v["environment_mol_m3"][i][:]
                image = _reshape(before, (ny, nx))
                for row in range(ny):
                    image[row][0] = image[row][-1] = packet["boundary_mol_m3"][i]
                for col in range(nx):
                    image[0][col] = image[-1][col] = packet["boundary_mol_m3"][i]
                v["environment_mol_m3"][i] = _flatten(image)
                observe("ecm_clamp", i)
                gx, gy = _derivative(image, g["delta_m"], source_boundary=False)
                diffusion = _reshape([a * b for a, b in zip(de[i], tj[i], strict=True)], (ny, nx))
                alpha = [
                    [dd * d(valence[i]) * q / (kb * temperature) for dd in row] for row in diffusion
                ]
                fx, fy = ([], [])
                for row in range(ny):
                    x, y = ([], [])
                    for col in range(nx):
                        c = image[row][col]
                        ux = packet["velocity_x_m_s"][row][col] if p["fluid_flow"] else zero
                        uy = packet["velocity_y_m_s"][row][col] if p["fluid_flow"] else zero
                        x.append(
                            -diffusion[row][col] * gx[row][col]
                            + alpha[row][col] * packet["electric_x_source"][row][col] * c
                            + ux * c
                        )
                        y.append(
                            -diffusion[row][col] * gy[row][col]
                            + alpha[row][col] * packet["electric_y_source"][row][col] * c
                            + uy * c
                        )
                    fx.append(x)
                    fy.append(y)
                v["environment_flux_x_mol_m2_s"][i] = _flatten(fx)
                v["environment_flux_y_mol_m2_s"][i] = _flatten(fy)
                dx, _ = _derivative(
                    [[-value for value in row] for row in fx], g["delta_m"], source_boundary=True
                )
                _, dy = _derivative(
                    [[-value for value in row] for row in fy], g["delta_m"], source_boundary=True
                )
                divergence = _combine(dx, dy)
                euler = [
                    [c + dt * rate for c, rate in zip(row, rate_row, strict=True)]
                    for row, rate_row in zip(image, divergence, strict=True)
                ]
                result = smooth(euler, d(p["sharpness"])) if p["sharpness"] < 1 else euler
                environment_records.append(
                    dict(
                        ion_id=names[i],
                        before_mol_m3=before,
                        clamped_mol_m3=image,
                        gradient_x=gx,
                        gradient_y=gy,
                        effective_diffusion_m2_s=diffusion,
                        alpha=alpha,
                        flux_x_mol_m2_s=fx,
                        flux_y_mol_m2_s=fy,
                        divergence_mol_m3_s=divergence,
                        euler_mol_m3=euler,
                        smoothed_mol_m3=result,
                    )
                )
                clamp[i] = sum(
                    ((a - b) * site_volume for a, b in zip(_flatten(image), before, strict=True))
                )
                collocated[i] = sum(
                    (
                        (a - b) * site_volume
                        for a, b in zip(_flatten(euler), _flatten(image), strict=True)
                    )
                )
                smoothing[i] = sum(
                    (
                        (a - b) * site_volume
                        for a, b in zip(_flatten(result), _flatten(euler), strict=True)
                    )
                )
                v["environment_mol_m3"][i] = _flatten(result)
                observe("ecm_commit", i)
                v["membrane_mol_m3"][i] = [v["cell_mol_m3"][i][a] for a in owner]
                observe("refresh_at_mem", i)
            calcium_equations(
                v,
                inputs["calcium"],
                native_parameters(inputs["calcium"]),
                inputs["rate_cache_before"],
                mapping,
                junction["boundary"],
                p["cluster_open"],
                temperature,
            )
            observe("calcium_handler")
            for i in range(s):
                v["membrane_flux_mol_m2_s"][i] = [
                    a + b
                    for a, b in zip(
                        v["membrane_flux_mol_m2_s"][i],
                        packet["supplied_late_membrane_flux_mol_m2_s"][i],
                        strict=True,
                    )
                ]
            observe("supplied_late_flux")
            channel_result = channel_sequence(
                material_channel_inputs(inputs, packet, v), refinement=refinement, values=v
            )
            for i in moving:
                fm, fg = (v["membrane_flux_mol_m2_s"][i], v["junction_flux_mol_m2_s"][i])
                before_cell, before_env = (v["cell_mol_m3"][i][:], v["environment_mol_m3"][i][:])
                for a in range(n):
                    v["cell_mol_m3"][i][a] += (
                        dt * sum((fm[j] * area[j] for j in range(m) if owner[j] == a)) / volume[a]
                    )
                v["membrane_mol_m3"][i] = [v["cell_mol_m3"][i][a] for a in owner]
                conservative_env = before_env[:]
                for face, site in enumerate(mapping):
                    conservative_env[site] -= dt * fm[face] * area[face] / site_volume
                transfer = dt * sum((fm[j] * area[j] for j in range(m)))
                conservative_exchange.append(
                    dict(
                        ion_id=names[i],
                        cell_mol_m3=v["cell_mol_m3"][i][:],
                        environment_mol_m3=conservative_env,
                        transfer_mol=transfer,
                        balance_residual_mol=sum(
                            (
                                (a - b) * vv
                                for a, b, vv in zip(
                                    v["cell_mol_m3"][i], before_cell, volume, strict=True
                                )
                            )
                        )
                        + sum(
                            (
                                (a - b) * site_volume
                                for a, b in zip(conservative_env, before_env, strict=True)
                            )
                        ),
                    )
                )
                if p["fast_update_ecm"]:
                    last = [zero] * e
                    for face, site in enumerate(mapping):
                        last[site] = -fm[face]
                    rates = [
                        last[site] * g["membrane_area_per_site_m2"][site] / site_volume
                        for site in range(e)
                    ]
                else:
                    rates = [
                        -sum((fm[j] * area[j] for j in range(m) if mapping[j] == site))
                        / site_volume
                        for site in range(e)
                    ]
                v["environment_mol_m3"][i] = [
                    c + dt * rate for c, rate in zip(before_env, rates, strict=True)
                ]
                exchange[i] = dt * sum(rates) * site_volume
                observe("membrane_commit", i)
                for a in range(n):
                    requested_gap_outward_increment[i][a] = (
                        dt * sum((fg[j] * area[j] for j in range(m) if owner[j] == a)) / volume[a]
                    )
                    v["cell_mol_m3"][i][a] -= (
                        dt * sum((fg[j] * area[j] for j in range(m) if owner[j] == a)) / volume[a]
                    )
                observe("junction_commit", i)
                clip[i] = sum(
                    (-c * vv for c, vv in zip(v["cell_mol_m3"][i], volume, strict=True) if c < 0)
                )
                v["cell_mol_m3"][i] = [max(zero, c) for c in v["cell_mol_m3"][i]]
                observe("clip_bulk", i)
            membrane_transfer = [
                dt * sum((f * a for f, a in zip(row, area, strict=True)))
                for row in v["membrane_flux_mol_m2_s"]
            ]
            gap_transfer = [
                dt * sum((f * a for f, a in zip(row, area, strict=True)))
                for row in v["junction_flux_mol_m2_s"]
            ]
            cell_change = [
                sum(
                    (
                        (a - b) * vv
                        for a, b, vv in zip(row, old["cell_mol_m3"][i], volume, strict=True)
                    )
                )
                for i, row in enumerate(v["cell_mol_m3"])
            ]
            env_change = [
                sum(
                    (
                        (a - b) * site_volume
                        for a, b in zip(row, old["environment_mol_m3"][i], strict=True)
                    )
                )
                for i, row in enumerate(v["environment_mol_m3"])
            ]
            committed = [i in moving for i in range(s)]
            ledgers = dict(
                boundary_clamp_change_mol=clamp,
                collocated_transport_change_mol=collocated,
                smoothing_change_mol=smoothing,
                membrane_transfer_mol=membrane_transfer,
                native_environment_exchange_mol=exchange,
                conservative_environment_exchange_mol=[
                    -membrane_transfer[i] if committed[i] else zero for i in range(s)
                ],
                fast_exchange_defect_mol=[
                    exchange[i] + (membrane_transfer[i] if committed[i] else zero) for i in range(s)
                ],
                gap_net_outward_mol=gap_transfer,
                clipping_added_mol=clip,
                cell_change_mol=cell_change,
                environment_change_mol=env_change,
                cell_accounting_residual_mol=[
                    cell_change[i]
                    - (membrane_transfer[i] - gap_transfer[i] + clip[i] if committed[i] else zero)
                    for i in range(s)
                ],
                environment_accounting_residual_mol=[
                    env_change[i] - (clamp[i] + collocated[i] + smoothing[i] + exchange[i])
                    for i in range(s)
                ],
                membrane_bulk_difference_mol_m3=[
                    [c - v["cell_mol_m3"][i][a] for c, a in zip(row, owner, strict=True)]
                    for i, row in enumerate(v["membrane_mol_m3"])
                ],
                junction_requested_outward_increment_mol_m3=requested_gap_outward_increment,
                source_voltage_nonce_delta_V=[
                    a - b for a, b in zip(v["voltage_V"], old["voltage_V"], strict=True)
                ],
            )
            history.append(
                dict(
                    frames=frames,
                    environment_records=environment_records,
                    candidate=deepcopy(v),
                    ledgers=ledgers,
                    conservative_exchange=conservative_exchange,
                    channel_reference=channel_result,
                )
            )
        return finish(
            dict(
                geometry=g,
                history=history,
                precision=context.prec,
                fixed_budget_reference=True,
                carried_error_allowance=False,
                conservative_oracle=(
                    "Separate area-weighted membrane exchange, not native collocated transport"
                ),
                physical_material_or_energy_parity=False,
            )
        )


def main():
    import argparse
    import builtins
    import importlib.abc
    import json
    import sys
    from pathlib import Path

    from validation.betse.betse_normal_channel_join_runtime import inventory

    parser = argparse.ArgumentParser()
    parser.add_argument("--inputs", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--refinement", type=int, choices=(1, 2), required=True)
    args = parser.parse_args()
    blocked = {"cells", "betse", "numpy", "jax", "jaxlib"}
    original = builtins.__import__

    def guarded(name, *rest, **kwargs):
        if name.split(".")[0] in blocked:
            raise ImportError("Independent molecule reference import denied: " + name)
        return original(name, *rest, **kwargs)

    class Guard(importlib.abc.MetaPathFinder):
        def find_spec(self, fullname, path=None, target=None):
            if fullname.split(".")[0] in blocked:
                raise ImportError("Independent molecule reference import denied: " + fullname)

    builtins.__import__ = guarded
    sys.meta_path.insert(0, Guard())
    input_bytes = args.inputs.read_bytes()
    inputs = json.loads(input_bytes)
    result = None
    try:
        result = evaluate(inputs, refinement=args.refinement)
        loaded = [name for name in sys.modules if name.split(".")[0] in blocked]
        assert not loaded
        result.update(
            production_imports_denied=True, loaded_production_modules=loaded, runtime=inventory()
        )
        with args.output.open("x") as stream:
            json.dump(result, stream, indent=2, allow_nan=False)
            stream.write("\n")
    except Exception as error:
        try:
            reference_failure.write(
                args.output,
                input_bytes=input_bytes,
                mode=inputs.get("mode"),
                refinement=args.refinement,
                error=error,
                runtime=inventory(),
                available_result=result,
            )
        except Exception as capture_error:
            error.add_note("Reference failure sidecar refused: " + str(capture_error))
        raise


if __name__ == "__main__":
    main()
