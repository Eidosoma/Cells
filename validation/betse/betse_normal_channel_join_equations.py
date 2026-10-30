"""Independent Decimal late-channel equations and local conditioning scales."""

import copy
from decimal import Decimal, localcontext

from validation.betse.betse_normal_ion_join_reference import convert, d
from validation.channels import potassium_catalog_reference as potassium
from validation.channels import sodium_catalog_reference as sodium


def kinetics(voltage, name):
    if name == "Nav1p6":
        return sodium._kinetics(voltage, name)
    if name == "Kv3p2":
        return potassium._kinetics(voltage, name)
    if name == "ClLeak":
        return [Decimal(1), Decimal(1)], [Decimal(1), Decimal(1)]
    mv = 1000 * voltage
    return [
        1 / (1 + ((mv + 6) / Decimal("-6.4")).exp()),
        1 / (1 + ((mv + Decimal("25.3")) / Decimal("3.5")).exp()),
    ], [
        Decimal("0.001") * (Decimal("8.33") - Decimal("0.1163") * mv),
        Decimal("0.001") * (1620 - Decimal("15.5") * mv),
    ]


def initialize(inputs, refinement):
    with localcontext() as ctx:
        ctx.prec = 90 if refinement == 1 else 140
        caches = []
        vm = inputs["initial"]["voltage_V"]
        for row in inputs["channel_definition"]["channels"]:
            targets = row["targets"]
            pairs = [kinetics(d(vm[j]), row["class_name"])[0] for j in targets]
            caches.append(dict(m=[float(p[0]) for p in pairs], h=[float(p[1]) for p in pairs]))
        return caches


def channels(inputs, values, gross, forcing):
    """Mutate aliases at the actual late seam; no ordinary flux-storage write."""
    definition = inputs["definition"]
    g, species, p = definition["geometry"], definition["ions"], definition["parameters"]
    names, owner = species["ids"], g["owner"]
    m, n = len(owner), len(g["cell_ids"])
    rowsets = [[j for j, a in enumerate(owner) if a == cell] for cell in range(n)]
    roles = dict(Nav1p6="Na", Kv1p5="K", Kv3p2="K", ClLeak="Cl")
    powers = dict(Nav1p6=(1, 0), Kv1p5=(1, 1), Kv3p2=(2, 0), ClLeak=(0, 0))
    dt, temperature = d(forcing["dt_s"]), d(forcing["runtime_temperature_K"])
    F, R, thickness = (d(p[k]) for k in ("F_C_mol", "R_J_mol_K", "membrane_thickness_m"))
    live = inputs["channel_packet"]
    caches = copy.deepcopy(inputs["channel_caches"])
    calls = list(inputs["channel_calls"])
    extra = [Decimal(0)] * m
    extra_gross = extra.copy()
    delta_cell = [[Decimal(0)] * n for _ in names]
    delta_mem = [[Decimal(0)] * m for _ in names]
    delta_bath = [Decimal(0)] * len(names)
    events = []
    for slot, row in enumerate(inputs["channel_definition"]["channels"]):
        name, targets = row["class_name"], row["targets"]
        i = names.index(roles[name])
        before = copy.deepcopy(values)
        skip = live["phase_kind"] == "INIT" and not row["init_active"]
        if skip:
            events.append(dict(channel_id=row["id"], skipped=True, call_index=calls[slot]))
            continue
        old = caches[slot]
        target_pairs, tau_pairs = [], []
        updated, gate_scales = [[], []], [[], []]
        for k, j in enumerate(targets):
            target, tau = kinetics(d(float(values["voltage_V"][j])), name)
            target_pairs.append(target)
            tau_pairs.append(tau)
            for a, key in enumerate(("m", "h")):
                oldvalue = old[key][k] if isinstance(old[key], (tuple, list)) else old[key]
                value = (tau[a] * d(oldvalue) + dt * target[a]) / (tau[a] + dt)
                updated[a].append(value)
                # The local state and voltage enter once. Global sigmoid slopes
                # bound target sensitivity; linear native tau slopes are exact.
                slope = (
                    Decimal("41.3385")
                    if name == "Nav1p6"
                    else Decimal("39.0625")
                    if a == 0 and name == "Kv1p5"
                    else Decimal(250) / Decimal("3.5")
                    if name == "Kv1p5"
                    else Decimal(250) / Decimal("8.568187")
                    if name == "Kv3p2" and a == 0
                    else Decimal(0)
                )
                tau_slope = (
                    Decimal("0.1163")
                    if name == "Kv1p5" and a == 0
                    else Decimal("15.5")
                    if name == "Kv1p5"
                    else Decimal("19.106496") / (4 * Decimal("4.451533"))
                    if name == "Kv3p2" and a == 0
                    else Decimal(0)
                )
                derivative = (
                    dt * slope / abs(tau[a] + dt)
                    + dt * abs(d(oldvalue) - target[a]) * tau_slope / (tau[a] + dt) ** 2
                )
                gate_scales[a].append(
                    abs(value) + abs(d(oldvalue)) + derivative * abs(before["voltage_V"][j])
                )
        opening, opening_gross = [Decimal(0)] * m, [Decimal(0)] * m
        a, b = powers[name]
        for k, j in enumerate(targets):
            gm, gh = updated[0][k], updated[1][k]
            opened = (gm**a if a else Decimal(1)) * (gh**b if b else Decimal(1))
            bound = abs(opened)
            if a:
                bound += a * abs(gm) ** (a - 1) * (abs(gh) ** b if b else 1) * gate_scales[0][k]
            if b:
                bound += b * abs(gh) ** (b - 1) * (abs(gm) ** a if a else 1) * gate_scales[1][k]
            # Duplicate source targets overwrite rather than accumulate.
            opening[j], opening_gross[j] = opened, bound
        diffusion = [
            opening[j] * d(row["maxDm_m2_s"]) * d(live["modulators"][row["id"]][j])
            for j in range(m)
        ]
        dgross = [
            opening_gross[j] * abs(d(row["maxDm_m2_s"]) * d(live["modulators"][row["id"]][j]))
            for j in range(m)
        ]
        values["voltage_V"] = [d(float(v) + 1e-25) for v in values["voltage_V"]]
        flux, bounds = [], []
        for j in range(m):
            ca, cb = values["bath_mol_m3"][i], values["cell_mol_m3"][i][owner[j]]
            z = d(float(species["valence"][i]) + 1e-25)
            alpha = z * values["voltage_V"][j] * F / (R * temperature)
            exp = (-alpha).exp()
            flux.append(-diffusion[j] * alpha / thickness * (cb - ca * exp) / (1 - exp))
            scale_c = abs(ca) + abs(cb) + delta_bath[i] + delta_cell[i][owner[j]]
            bounds.append(dgross[j] / thickness * scale_c * (1 + 2 * abs(alpha)))
        for cell, rowset in enumerate(rowsets):
            values["cell_mol_m3"][i][cell] += (
                dt
                * sum(flux[j] * d(g["membrane_area_m2"][j]) for j in rowset)
                / d(g["cell_volume_m3"][cell])
            )
            delta_cell[i][cell] += (
                dt
                * sum(bounds[j] * d(g["membrane_area_m2"][j]) for j in rowset)
                / d(g["cell_volume_m3"][cell])
            )
        values["membrane_mol_m3"][i] = [values["cell_mol_m3"][i][a] for a in owner]
        delta_mem[i] = [delta_cell[i][a] for a in owner]
        values["bath_mol_m3"][i] -= (
            dt
            * sum(flux[j] * d(g["membrane_area_m2"][j]) for j in range(m))
            / (m * d(p["bath_volume_m3"]))
        )
        delta_bath[i] += (
            dt
            * sum(bounds[j] * d(g["membrane_area_m2"][j]) for j in range(m))
            / (m * d(p["bath_volume_m3"]))
        )
        for j in range(m):
            extra[j] += -flux[j] * F * d(species["valence"][i])
            extra_gross[j] += bounds[j] * F * abs(d(species["valence"][i]))
        calls[slot] += 1
        caches[slot] = dict(m=updated[0], h=updated[1])
        events.append(
            dict(
                channel_id=row["id"],
                class_name=name,
                skipped=False,
                call_index=calls[slot],
                m=updated[0],
                h=updated[1],
                P=opening,
                DChan=diffusion,
                chan_flux=flux,
                flux_gross=bounds,
                network_current=extra.copy(),
                network_current_gross=extra_gross.copy(),
                target_pairs=target_pairs,
                tau_pairs_s=tau_pairs,
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
        voltage_nonce_count=sum(not e["skipped"] for e in events),
    )


def augment_gross(gross, channel, moving, owner):
    result = copy.deepcopy(gross)
    for i in range(len(result["cell_mol_m3"])):
        result["cell_mol_m3"][i] = [
            d(x) + y
            for x, y in zip(result["cell_mol_m3"][i], channel["cell_gross_add"][i], strict=True)
        ]
        result["bath_mol_m3"][i] = d(result["bath_mol_m3"][i]) + channel["bath_gross_add"][i]
        addition = (
            [channel["cell_gross_add"][i][a] for a in owner]
            if i in moving
            else channel["membrane_gross_add"][i]
        )
        result["membrane_mol_m3"][i] = [
            d(x) + y for x, y in zip(result["membrane_mol_m3"][i], addition, strict=True)
        ]
    result["voltage_V"] = [
        d(x) + d(1e-25) * channel["voltage_nonce_count"] for x in result["voltage_V"]
    ]
    return convert(result, lambda v: float(v) if isinstance(v, Decimal) else v)
