"""Independent stdlib/Decimal noise transforms and owner budgets, no RNG engine."""

from decimal import Decimal, localcontext
from math import cos, fsum, hypot, sin, sqrt


def static(raw, uniforms):
    result = [list(row) for row in raw["initial_diffusion_m2_s"]]
    potassium = raw["ion_ids"].index("K")
    with localcontext() as context:
        context.prec = 80
        for i, u in enumerate(uniforms):
            result[potassium][i] = float(
                Decimal(str(result[potassium][i]))
                * (1 + Decimal(str(raw["static_level"])) * Decimal(str(u)))
            )
    return result


def active(raw):
    return (
        raw["solver"] == "normal"
        and raw["phase"] == "SIM"
        and raw["dynamic_enabled"] == 1
        and raw["protein_enabled"] == 1
    )


def protein(raw, state, uniforms):
    if uniforms is None:
        return dict(state=state, flux=None)
    with localcontext() as context:
        context.prec = 80
        dt = Decimal(str(raw["dt_s"]))
        level = Decimal(str(raw["dynamic_level"]))
        flux = [level * (Decimal(str(u)) - Decimal("0.5")) for u in uniforms]
        areas = [Decimal(str(v)) for v in raw["membrane_area_m2"]]
        volumes = [Decimal(str(v)) for v in raw["cell_volume_m3"]]
        cells = [
            Decimal(str(v))
            + dt
            * sum(
                (
                    f * a
                    for f, a, owner in zip(flux, areas, raw["owner"], strict=True)
                    if owner == i
                ),
                Decimal(0),
            )
            / volumes[i]
            for i, v in enumerate(state["cell"])
        ]
        if raw["is_ecm"]:
            ec = [Decimal(str(v)) for v in state["environment"]]
            ev = Decimal(str(raw["environment_volume_m3"]))
            for site in range(len(ec)):
                positions = [i for i, owner in enumerate(raw["environment_owner"]) if owner == site]
                if raw["fast_update_ecm"]:
                    change = (
                        -flux[positions[-1]] * sum((areas[i] for i in positions), Decimal(0))
                        if positions
                        else Decimal(0)
                    )
                else:
                    change = -sum((flux[i] * areas[i] for i in positions), Decimal(0))
                ec[site] += dt * change / ev
        else:
            old = state["environment"]
            if len(old) == 1:
                old = old * len(flux)
            ev = Decimal(str(raw["bath_parameter_volume_m3"]))
            ec = [
                sum(
                    (
                        Decimal(str(v)) - dt * f * a / ev
                        for v, f, a in zip(old, flux, areas, strict=True)
                    ),
                    Decimal(0),
                )
                / len(flux)
            ]
        result = dict(
            cell=[float(v) for v in cells],
            membrane=[float(cells[i]) for i in raw["owner"]],
            environment=[float(v) for v in ec],
        )
    return dict(state=result, flux=[float(f) for f in flux])


def bulk_zero_flux(raw, state):
    result = {k: list(v) for k, v in state.items()}
    result["membrane"] = [state["cell"][i] for i in raw["owner"]]
    result["cell"] = [max(0, v) for v in state["cell"]]
    if not raw["is_ecm"]:
        result["environment"] = [fsum(state["environment"]) / len(state["environment"])]
    return result


def boundary(raw, chosen):
    values = [float(i == chosen) + raw["modulator_offset"] for i in range(len(raw["cell_ids"]))]
    if raw["target_count"] == len(raw["membrane_ids"]):
        return [values[i] for i in raw["owner"]]
    if raw["target_count"] == len(raw["cell_ids"]):
        return values
    raise ValueError("Native subset callback has no bound axis")


def micro(raw, standard_normals):
    p = raw["micro"]
    owner = raw["owner"]
    m = len(owner)
    theta = p["theta"]
    if p["dilation"] <= 0:
        return dict(theta=list(theta), stdev=None, drift=None)
    ex = [p["E_x"][i] for i in owner]
    ey = [p["E_y"][i] for i in owner]
    stdev = []
    drift = []
    out = []
    for i in range(m):
        length = p["length_m"][i]
        ui = cos(theta[i]) * length
        vi = sin(theta[i]) * length
        gx = (ex[p["partner"][i]] - ex[i]) / p["neighbor_length_m"][i]
        gy = (ey[p["partner"][i]] - ey[i]) / p["neighbor_length_m"][i]
        # Captures declare membrane-to-partner direction along each normal.
        tx, ty = p["normal"][i]
        if p["tethered"]:
            torque = p["charge_C"][i] * (ui * ey[i] - vi * ex[i])
        else:
            torque = p["charge_C"][i] * (ui * ex[i] + vi * ey[i]) + p["charge_C"][i] * (
                ui * (gy * tx * ui + gy * ty * vi) - vi * (gx * tx * ui + gx * ty * vi)
            )
        rate = torque / p["drag_native"][i]
        drift.append(rate)
        correlation = hypot(p["ux"][owner[i]], p["uy"][owner[i]]) + p["kb"] * p["sim_T"]
        sd = sqrt(
            2
            * raw["dt_s"]
            * p["dilation"]
            * ((p["kb"] * p["T"]) / p["drag_native"][i])
            * correlation
            * length**2
        )
        stdev.append(sd)
        out.append(
            theta[i]
            + rate * raw["dt_s"] * p["dilation"] * p["modulator"][i]
            + sd * standard_normals[i]
        )
    return dict(theta=out, stdev=stdev, drift=drift)
