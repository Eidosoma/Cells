"""Prepared independent catalog gates and ordered late transport equations.

No production/NumPy/BETSE import. Initial class caches are explicit conditions;
native initialization itself has a separate exact-source comparison.
"""

import copy
import json
from decimal import Decimal
from pathlib import Path

from validation.betse.betse_normal_catalog_join_scalar import (
    cav_kinetics,
    hcn_kinetics,
    kv1_kinetics,
)
from validation.betse.betse_normal_channel_join_equations import augment_gross as augment_gross
from validation.betse.betse_normal_ion_join_reference import d
from validation.channels import calcium_catalog_extra_reference as calcium
from validation.channels import hcn_extra_reference as hcn
from validation.channels import morris_lecar_channels_reference as ml
from validation.channels import potassium_catalog_reference as potassium
from validation.channels import sodium_catalog_reference as sodium


def inventory():
    return json.loads(
        Path(__file__).with_name("betse_normal_catalog_join_inventory.json").read_text()
    )


def initialize(inputs, refinement):
    if "initial_channel_caches" not in inputs:
        raise ValueError("Carried diagnostics require explicit initialized cache conditions")
    return copy.deepcopy(inputs["initial_channel_caches"])


def kinetics(name, voltage, refinement):
    family = inventory()["classes"][name]["family"]
    precision = 90 if refinement == 1 else 140
    if family == "Na":
        return sodium._kinetics(voltage, name)
    if family == "K":
        return (
            kv1_kinetics(voltage, int(name[-1]), precision=precision)
            if name.startswith("Kv1p")
            else potassium._kinetics(voltage, name)
        )
    if family == "Ca":
        return (
            calcium._kinetics(voltage, name)
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
        return [Decimal(1), Decimal(1)], [Decimal(1), Decimal(1)]
    target, tau, _, _, _, _ = ml._values(voltage, name)
    return [target], [tau]


def channels(inputs, values, gross, forcing):
    definition = inputs["definition"]
    geometry, ions, p = definition["geometry"], definition["ions"], definition["parameters"]
    names, owner = ions["ids"], geometry["owner"]
    m, n = len(owner), len(geometry["cell_ids"])
    rows = [[j for j, a in enumerate(owner) if a == cell] for cell in range(n)]
    live = inputs["channel_packet"]
    caches = copy.deepcopy(inputs["channel_caches"])
    calls = list(inputs["channel_calls"])
    entries = inventory()["classes"]
    dt, T = d(forcing["dt_s"]), d(forcing["runtime_temperature_K"])
    F, R, thickness = (d(p[k]) for k in ("F_C_mol", "R_J_mol_K", "membrane_thickness_m"))
    extra, extra_gross = [Decimal(0)] * m, [Decimal(0)] * m
    delta_cell = [[Decimal(0)] * n for _ in names]
    delta_mem = [[Decimal(0)] * m for _ in names]
    delta_bath = [Decimal(0)] * len(names)
    events = []
    nonce_calls = 0
    for slot, row in enumerate(inputs["channel_definition"]["channels"]):
        name, targets = row["class_name"], row["targets"]
        entry = entries[name]
        skip = live["phase_kind"] == "INIT" and not row["init_active"]
        if skip:
            events.append(
                dict(channel_id=row["id"], skipped=True, call_index=calls[slot], routes=[])
            )
            continue
        cache = caches[slot]
        gate_names = ("m",) if entry["family"] == "ML" else ("m", "h")
        updated = {key: [] for key in gate_names}
        for k, j in enumerate(targets):
            target, tau = kinetics(name, d(float(values["voltage_V"][j])), inputs["refinement"])
            for a, key in enumerate(gate_names):
                old = cache[key][k] if isinstance(cache[key], (list, tuple)) else cache[key]
                updated[key].append(
                    target[a]
                    if entry["family"] == "ML" and name not in ml.KINETIC
                    else (tau[a] * d(old) + dt * target[a]) / (tau[a] + dt)
                )
        opening = [Decimal(0)] * m
        powers = (
            (1, 0) if entry["family"] == "ML" else (int(cache["_mpower"]), int(cache["_hpower"]))
        )
        for k, j in enumerate(targets):
            a, b = powers
            opening[j] = (updated["m"][k] ** a if a else Decimal(1)) * (
                updated["h"][k] ** b if b else Decimal(1)
            )
        routes = []
        for ion_id, relative in entry["routes"]:
            i = names.index(ion_id)
            diffusion = [
                v * d(relative) * d(row["maxDm_m2_s"]) * d(live["modulators"][row["id"]][j])
                for j, v in enumerate(opening)
            ]
            values["voltage_V"] = [d(float(v) + 1e-25) for v in values["voltage_V"]]
            nonce_calls += 1
            flux, bounds = [], []
            for j in range(m):
                ca, cb = values["bath_mol_m3"][i], values["cell_mol_m3"][i][owner[j]]
                z = d(float(ions["valence"][i]) + 1e-25)
                alpha = z * values["voltage_V"][j] * F / (R * T)
                exp = (-alpha).exp()
                flux.append(-diffusion[j] * alpha / thickness * (cb - ca * exp) / (1 - exp))
                # Exact incoming float conditions and binary64 nonce seams.
                # Ordinary catalog probabilities are bounded by one; preserve
                # all signed modulation and previous direct-update scales.
                probability_bound = max(Decimal(1), abs(opening[j]))
                dscale = probability_bound * abs(
                    d(relative) * d(row["maxDm_m2_s"]) * d(live["modulators"][row["id"]][j])
                )
                cscale = abs(ca) + abs(cb) + delta_bath[i] + delta_cell[i][owner[j]]
                bounds.append(dscale / thickness * cscale * (1 + 2 * abs(alpha)))
            for cell, rowset in enumerate(rows):
                values["cell_mol_m3"][i][cell] += (
                    dt
                    * sum(flux[j] * d(geometry["membrane_area_m2"][j]) for j in rowset)
                    / d(geometry["cell_volume_m3"][cell])
                )
                delta_cell[i][cell] += (
                    dt
                    * sum(bounds[j] * d(geometry["membrane_area_m2"][j]) for j in rowset)
                    / d(geometry["cell_volume_m3"][cell])
                )
            values["membrane_mol_m3"][i] = [values["cell_mol_m3"][i][a] for a in owner]
            delta_mem[i] = [delta_cell[i][a] for a in owner]
            values["bath_mol_m3"][i] -= (
                dt
                * sum(flux[j] * d(geometry["membrane_area_m2"][j]) for j in range(m))
                / (m * d(p["bath_volume_m3"]))
            )
            delta_bath[i] += (
                dt
                * sum(bounds[j] * d(geometry["membrane_area_m2"][j]) for j in range(m))
                / (m * d(p["bath_volume_m3"]))
            )
            for j in range(m):
                extra[j] += -flux[j] * F * d(ions["valence"][i])
                extra_gross[j] += bounds[j] * F * abs(d(ions["valence"][i]))
            routes.append(
                dict(
                    ion_id=ion_id,
                    relative_permeability=relative,
                    DChan=diffusion,
                    chan_flux=flux,
                    flux_gross=bounds,
                    network_current=extra.copy(),
                    network_current_gross=extra_gross.copy(),
                )
            )
        calls[slot] += 1
        caches[slot] = dict(cache, **updated)
        events.append(
            dict(
                channel_id=row["id"],
                class_name=name,
                skipped=False,
                call_index=calls[slot],
                **updated,
                P=opening,
                routes=routes,
            )
        )
    return dict(
        events=events,
        caches=caches,
        calls=calls,
        extra_current=extra,
        extra_current_gross=extra_gross,
        cell_gross_add=delta_cell,
        membrane_gross_add=delta_mem,
        bath_gross_add=delta_bath,
        voltage_nonce_count=nonce_calls,
    )
