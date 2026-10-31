"""Unchanged common material equations and INIT-filtered common channel equations.

No shared reference namespace is mutated. The single active-guard insertion has
an exact inverse AST; constitutive equations and numerical budgets are retained.
"""

from validation.betse import betse_normal_ecm_catalog_join_reference as catalog
from validation.betse import betse_normal_ecm_event_join_reference as events

Decimal = events.Decimal
control_at = events.control_at
copy = events.copy
d = events.d
geometry = events.geometry
inventory = events.inventory
kinetics = events.kinetics
localcontext = events.localcontext
ml = events.ml
modulation = events.modulation
numbers = events.numbers
_combine = catalog._combine
_derivative = catalog._derivative
_flatten = catalog._flatten
_reshape = catalog._reshape
calcium_equations = catalog.calcium_equations
deepcopy = catalog.deepcopy
flux = catalog.flux
material_channel_inputs = catalog.material_channel_inputs
native_parameters = catalog.native_parameters
serial = catalog.serial
smooth = catalog.smooth


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
            if row.get("init active", True) is False:
                continue
            name, cls = (row["name"], row["channel type"])
            entry = inventory()["classes"][cls]
            cache = copy.deepcopy(wire["channel_fields"][name]["core_fields"])
            targets = cache["targets"]
            moddy = modulation(row, v, molecules, names, mapping)
            gates = ("m",) if entry["family"] == "ML" else ("m", "h")
            updated = {key: [] for key in gates}
            for slot, j in enumerate(targets):
                target, tau = kinetics(cls, d(float(v["voltage_V"][j])), refinement)
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
                    rho = d(control_at(inputs["rho_channel"], j))
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
                conservative_oracle="Separate area-weighted membrane exchange, not native collocated transport",  # noqa: E501
                physical_material_or_energy_parity=False,
            )
        )
