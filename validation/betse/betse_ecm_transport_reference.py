"""Independent Decimal ECM chronology and conservative membrane exchange oracle.

No production/native numerical package imports or supplied prepared geometry.
Source nonce stores round to binary64; equations and carried states use Decimal.
No carried or propagated error allowance is computed here.
"""

from copy import deepcopy
from decimal import Decimal, localcontext

from validation.betse.betse_environment_field_reference import (
    _combine,
    _derivative,
    _flatten,
    _reshape,
    d,
    geometry,
    serial,
)


def numbers(value):
    if isinstance(value, dict):
        return {key: numbers(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [numbers(item) for item in value]
    return d(value)


def flux(ca, cb, diffusion, distance, valence, voltage, temperature, F, R, rho):
    alpha = valence * voltage * F / (R * temperature)
    exponential = (-alpha).exp()
    return -(diffusion * alpha / distance) * ((cb - ca * exponential) / (1 - exponential)) * rho


def smooth(image, sharpness):
    result = deepcopy(image)
    for i in range(1, len(image) - 1):
        for j in range(1, len(image[0]) - 1):
            result[i][j] = sharpness * image[i][j] + (1 - sharpness) / 4 * (
                image[i - 1][j] + image[i + 1][j] + image[i][j - 1] + image[i][j + 1]
            )
    return result


def evaluate(inputs, *, refinement=1):
    if refinement not in (1, 2):
        raise ValueError("Require the declared independent precision settings")
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
        cg, cd = external["current_definition"]["geometry"], external["current_definition"]
        names, valence = cd["ions"]["ids"], cd["ions"]["valence"]
        g = geometry(external, precision=context.prec)
        ny, nx = g["shape"]
        s, m, n, e = len(names), len(cg["membrane_ids"]), len(cg["cell_ids"]), ny * nx
        owner, partner, mapping = cg["owner"], junction["partner"], g["membrane_to_grid"]
        moving = [names.index(name) for name in ions["moving_ids"]]
        area, volume = (
            numbers(cg["membrane_area_m2"]),
            numbers(external["geometry"]["cell_volume_m3"]),
        )
        site_volume = d(external["parameters"]["cell_height_m"]) * g["delta_m"] ** 2
        length, weights = numbers(junction["gap_length_m"]), numbers(junction["gap_weights"])
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
        q, kb = d(external["parameters"]["q_C"]), d(external["parameters"]["kb_J_K"])
        zero = Decimal(0)
        v = numbers(inputs["initial"])
        history = []
        for packet_raw in inputs["steps"]:
            packet = numbers(packet_raw)
            dt, temperature = packet["dt_s"], packet["runtime_temperature_K"]
            old = deepcopy(v)
            frames, environment_records, conservative_exchange = [], [], []
            clamp, collocated, smoothing, exchange, clip = ([zero] * s for _ in range(5))

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
                fx, fy = [], []
                for row in range(ny):
                    x, y = [], []
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
                    (a - b) * site_volume for a, b in zip(_flatten(image), before, strict=True)
                )
                collocated[i] = sum(
                    (a - b) * site_volume
                    for a, b in zip(_flatten(euler), _flatten(image), strict=True)
                )
                smoothing[i] = sum(
                    (a - b) * site_volume
                    for a, b in zip(_flatten(result), _flatten(euler), strict=True)
                )
                v["environment_mol_m3"][i] = _flatten(result)
                observe("ecm_commit", i)
                v["membrane_mol_m3"][i] = [v["cell_mol_m3"][i][a] for a in owner]
                observe("refresh_at_mem", i)
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
            for i in moving:
                fm, fg = v["membrane_flux_mol_m2_s"][i], v["junction_flux_mol_m2_s"][i]
                before_cell, before_env = v["cell_mol_m3"][i][:], v["environment_mol_m3"][i][:]
                for a in range(n):
                    v["cell_mol_m3"][i][a] += (
                        dt * sum(fm[j] * area[j] for j in range(m) if owner[j] == a) / volume[a]
                    )
                v["membrane_mol_m3"][i] = [v["cell_mol_m3"][i][a] for a in owner]
                conservative_env = before_env[:]
                for face, site in enumerate(mapping):
                    conservative_env[site] -= dt * fm[face] * area[face] / site_volume
                transfer = dt * sum(fm[j] * area[j] for j in range(m))
                conservative_exchange.append(
                    dict(
                        ion_id=names[i],
                        cell_mol_m3=v["cell_mol_m3"][i][:],
                        environment_mol_m3=conservative_env,
                        transfer_mol=transfer,
                        balance_residual_mol=sum(
                            (a - b) * vv
                            for a, b, vv in zip(
                                v["cell_mol_m3"][i], before_cell, volume, strict=True
                            )
                        )
                        + sum(
                            (a - b) * site_volume
                            for a, b in zip(conservative_env, before_env, strict=True)
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
                        -sum(fm[j] * area[j] for j in range(m) if mapping[j] == site) / site_volume
                        for site in range(e)
                    ]
                v["environment_mol_m3"][i] = [
                    c + dt * rate for c, rate in zip(before_env, rates, strict=True)
                ]
                exchange[i] = dt * sum(rates) * site_volume
                observe("membrane_commit", i)
                for a in range(n):
                    v["cell_mol_m3"][i][a] -= (
                        dt * sum(fg[j] * area[j] for j in range(m) if owner[j] == a) / volume[a]
                    )
                observe("junction_commit", i)
                clip[i] = sum(
                    -c * vv for c, vv in zip(v["cell_mol_m3"][i], volume, strict=True) if c < 0
                )
                v["cell_mol_m3"][i] = [max(zero, c) for c in v["cell_mol_m3"][i]]
                observe("clip_bulk", i)
            membrane_transfer = [
                dt * sum(f * a for f, a in zip(row, area, strict=True))
                for row in v["membrane_flux_mol_m2_s"]
            ]
            gap_transfer = [
                dt * sum(f * a for f, a in zip(row, area, strict=True))
                for row in v["junction_flux_mol_m2_s"]
            ]
            cell_change = [
                sum(
                    (a - b) * vv
                    for a, b, vv in zip(row, old["cell_mol_m3"][i], volume, strict=True)
                )
                for i, row in enumerate(v["cell_mol_m3"])
            ]
            env_change = [
                sum(
                    (a - b) * site_volume
                    for a, b in zip(row, old["environment_mol_m3"][i], strict=True)
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
                )
            )
        return serial(
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
