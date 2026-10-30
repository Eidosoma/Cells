"""Independent named-owner protein increments and full-node field response.

No Cells/JAX imports. The reference reconstructs geometry and concentrations
from declarations and retained material fields, then solves the existing
independent full-node charge/current equations without rebasing any anchor.
"""

from decimal import Decimal, localcontext
from numbers import Real

import numpy as np

from validation.tissue import physiology_permeability_view_reference as permeability
from validation.tissue import surface_dynamics_reference as passive
from validation.tissue import surface_field_reference as electrical


def evaluate(raw, fields, binding, current_diffusion, held_control, before, after, *, valence):
    if (
        not isinstance(valence, Real)
        or isinstance(valence, (bool, np.bool_))
        or not np.isfinite(valence)
    ):
        raise ValueError("Require an explicit finite real protein valence")
    effective = permeability.reconstruct(raw, binding, current_diffusion, held_control)
    oracle = permeability.ORACLES[raw["model"]["id"]]
    context = oracle.bind(effective)
    state = oracle.flatten(context, fields)
    values = oracle.unpack(context, state)
    if "energy_initial" in context:
        # The finite-fuel wrapper has its own outer raw definition. Reconstruct
        # its actual calcium/cytosol context from current fuel, as its full
        # independent reference does; do not treat the wrapper as ionic input.
        amount = context["energy_initial"] + values["energy_amount_increment_fmol"]
        context = permeability.calcium.bind(permeability.fuel._project(context, amount))
        state = passive.flatten(context, values)
        values = passive.unpack(context, state)
    packet = passive.stage(context, state, 0.0)
    model = context["raw"]["model"]
    if "stores" in context:
        species = [row["id"] for row in model["species"]]
        free = np.stack(
            [
                (store.n0 + values["chemical_amount_increment"][i])[
                    [store.ids.index(name) for name in species], store.cy
                ]
                for i, store in enumerate(context["stores"])
            ],
            axis=1,
        )
        packet["ci"] = free / context["vi"]
    if "junction_gate" in values:
        packet["junction_open"] = np.asarray(packet["junction_open"]) * values["junction_gate"]
    delta = []
    with localcontext() as decimal_context:
        decimal_context.prec = 80
        for domain, axis, owners in (
            ("cell_mol_m3", "cell_ids", model["cells"]),
            ("environment_mol_m3", "environment_ids", model["extracellular"]),
        ):
            names = binding["inputs"][axis]
            for owner in owners:
                i = names.index(owner["id"])
                amount = (
                    Decimal.from_float(float(after[domain][i]))
                    - Decimal.from_float(float(before[domain][i]))
                ) * Decimal.from_float(float(owner["volume_pL"]) * 1e-15)
                delta.append(
                    float(
                        amount
                        * Decimal.from_float(float(valence))
                        * Decimal.from_float(electrical.F)
                    )
                )
    delta = np.asarray(delta)
    n = len(model["cells"])
    source_charge = np.r_[packet["cell_charge_C"], packet["outside_charge_C"]]
    answers = []
    for charge in (source_charge, source_charge + delta):
        current = dict(packet, cell_charge_C=charge[:n], outside_charge_C=charge[n:])
        phi, proof = electrical.solve(current)
        capacitor, _, reservoir, _, _, _ = electrical.topology(current)
        cap_charge = capacitor @ phi
        a, b = packet["layout"]["membrane_cell"], packet["layout"]["membrane_outside"]
        vm = phi[a] - phi[n + np.asarray(b)]
        membrane_charge = np.asarray(packet["layout"]["membrane_capacitance"]) * vm
        answers.append(
            dict(
                potential_V=phi,
                membrane_voltage_V=vm,
                membrane_charge_C=membrane_charge,
                capacitor_node_charge_C=cap_charge,
                electrode_charge_C=np.where(reservoir, cap_charge - charge, 0.0)[n:],
                capacitor_energy_pJ=0.5e12 * np.sum(membrane_charge * vm),
                proof=proof,
            )
        )
    return dict(
        before=answers[0],
        after=answers[1],
        source_charge_C=source_charge,
        applied_delta_charge_C=delta,
        total_charge_C=source_charge + delta,
        potential_change_V=answers[1]["potential_V"] - answers[0]["potential_V"],
        capacitor_energy_change_pJ=(
            answers[1]["capacitor_energy_pJ"] - answers[0]["capacitor_energy_pJ"]
        ),
    )
