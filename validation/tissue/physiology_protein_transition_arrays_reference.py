"""Independent prescribed-packet component and associated SI work/drive oracle.

Named owner loops and 4096-digit exact-float arithmetic replace production
surface matrices. No Cells/JAX imports, sampler, packet authentication or loop
acceptance. Supplied RNG successors remain externally admitted records.
"""

from copy import deepcopy
from decimal import Context, Decimal, localcontext

import numpy as np

from validation.tissue import physiology_protein_drive_arrays_reference as drive


def _d(value):
    return Decimal.from_float(float(value))


def propose(binding, source, packet):
    c, p, g, axes = source["controls"], source["protein"], binding["geometry"], binding["inputs"]
    active = bool(
        c["phase"] == 1 and c["solver"] == 0 and c["dynamic_enabled"] and c["protein_enabled"]
    )
    if bool(packet["present"]) != active:
        raise ValueError("Independent supplied packet violates original draw guard")
    values = np.asarray(packet["values"])
    if (
        values.shape != (len(axes["membrane_ids"]),)
        or not np.isfinite(values).all()
        or np.any((values < 0) | (values >= 1))
    ):
        raise ValueError("Independent explicit uniform packet domain/owner mismatch")
    if not active and np.any(values != 0):
        raise ValueError("Independent absent packet requires zero placeholder values")
    with localcontext(Context(prec=4096)):
        dt, level = _d(c["dt_s"]), _d(c["dynamic_level_mol_m2_s"])
        flux = [level * (_d(v) - Decimal("0.5")) if active else Decimal(0) for v in values]
        areas = [_d(v) for v in g["membrane_area_m2"]]
        cell_amounts, env_amounts, cell, outside = [], [], [], []
        for names, membrane_owners, volumes, field, sign, amounts, result in (
            (
                axes["cell_ids"],
                g["membrane_cell_ids"],
                g["cell_volume_m3"],
                "cell_mol_m3",
                1,
                cell_amounts,
                cell,
            ),
            (
                axes["environment_ids"],
                g["membrane_environment_ids"],
                g["environment_volume_m3"],
                "environment_mol_m3",
                -1,
                env_amounts,
                outside,
            ),
        ):
            for i, owner in enumerate(names):
                change = (
                    sign
                    * dt
                    * sum(
                        (
                            f * a
                            for f, a, name in zip(flux, areas, membrane_owners, strict=True)
                            if name == owner
                        ),
                        Decimal(0),
                    )
                )
                amounts.append(change)
                result.append(float(_d(p[field][i]) + change / _d(volumes[i])))
        membrane = (
            [cell[axes["cell_ids"].index(name)] for name in g["membrane_cell_ids"]]
            if active
            else list(p["membrane_mol_m3"])
        )
        diffusion = {key: np.asarray(value) for key, value in source["diffusion"].items()}
        if c["phase"] == 1:
            current = np.empty_like(diffusion["base_m2_s"], dtype=float)
            for index in np.ndindex(current.shape):
                current[index] = float(
                    _d(diffusion["base_m2_s"][index]) + _d(diffusion["scheduled_m2_s"][index])
                )
            diffusion["current_m2_s"] = current
        trial = dict(
            protein=dict(cell_mol_m3=cell, membrane_mol_m3=membrane, environment_mol_m3=outside),
            diffusion=diffusion,
            stream=deepcopy(packet["successor_stream"] if active else source["stream"]),
            controls=deepcopy(c),
            time_s=float(source["time_s"]) + float(c["dt_s"]),
            loop_calls=int(source["loop_calls"]) + 1,
        )
        net, gross = (
            sum((*cell_amounts, *env_amounts), Decimal(0)),
            sum((abs(v) for v in (*cell_amounts, *env_amounts)), Decimal(0)),
        )
        return dict(
            trial=trial,
            active=active,
            flux_mol_m2_s=[float(v) for v in flux],
            requested_cell_amount_change_mol=[float(v) for v in cell_amounts],
            requested_environment_amount_change_mol=[float(v) for v in env_amounts],
            requested_balance_mol_exact=str(net),
            requested_gross_mol_exact=str(gross),
            strict_requested_material=bool(abs(net) <= _d(3e-13) * gross),
            sampler_or_loop_credit=False,
        )


def evaluate(
    raw,
    state,
    binding,
    held_control,
    charge_reference,
    source,
    packet,
    *,
    external_work_pJ,
    dissipated_free_energy_pJ,
    budget_provenance,
    valence,
    faraday_C_mol,
    temperature_K,
    standard_concentration_mol_m3,
    gas_constant_J_mol_K,
):
    component = propose(binding, source, packet)
    declaration = drive.evaluate(
        raw,
        state,
        binding,
        component["trial"]["diffusion"]["current_m2_s"],
        held_control,
        charge_reference,
        source["protein"],
        component["trial"]["protein"],
        external_work_pJ=external_work_pJ,
        dissipated_free_energy_pJ=dissipated_free_energy_pJ,
        budget_provenance=budget_provenance,
        valence=valence,
        faraday_C_mol=faraday_C_mol,
        temperature_K=temperature_K,
        standard_concentration_mol_m3=standard_concentration_mol_m3,
        gas_constant_J_mol_K=gas_constant_J_mol_K,
    )
    return dict(
        component=component,
        declared_drive=declaration,
        heat_inferred=False,
        sampler_credit=False,
        loop_acceptance=False,
    )
