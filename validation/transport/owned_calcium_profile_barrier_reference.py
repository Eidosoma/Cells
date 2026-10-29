"""Independent coefficients plus complete calcium@11 and live-fuel@5 dynamics."""

from copy import deepcopy
from decimal import Decimal, localcontext

import numpy as np

from validation.chemistry import finite_energy_reference as pools
from validation.tissue import surface_calcium_energy_reference as energy
from validation.tissue import surface_calcium_reference as calcium
from validation.topology import surface_profile_interventions_reference as membranes
from validation.topology import tissue_profile_preparation_reference as static_membranes
from validation.transport import environment_barrier_interventions_reference as barriers
from validation.transport import environment_barrier_preparation_reference as static_barriers

OWNERS = {
    "resolved_calcium_profile_barriers@1": ("resolved_calcium@11", calcium),
    "resolved_calcium_energy_profile_barriers@1": ("resolved_calcium_energy@5", energy),
}
EXTRA = (
    "coupled_preparation",
    "membrane_interventions",
    "barrier_intervention",
    "phase",
    "timing_policy",
    "reset_policy",
)
flatten, unpack = calcium.flatten, calcium.unpack
F, R = calcium.F, calcium.R


def bind(raw):
    m = raw["model"]
    parent_id, equation = OWNERS[m["id"]]
    provenance = m["coupled_preparation"]["provenance"]
    if provenance["parent_model_id"] != parent_id:
        raise ValueError("Wrong complete physical parent")
    parent = deepcopy(raw)
    for key in EXTRA:
        parent["model"].pop(key)
    parent["model"]["id"] = parent_id
    if parent["model"]["ionic"]["id"] != "resolved_tissue@12":
        raise ValueError("Require full56 ionic identity")
    for key in ("intervention_capacity", "intervention_target_capacity", "barrier_target_capacity"):
        parent["execution"].pop(key)
    physical = equation.bind(parent)
    p = provenance["profile_preparation"]["provenance"]["direct_parameter_preparation"]
    static = static_membranes.prepare(
        dict(definition=p["source_definition"], geometry=p["geometry"], **p["profile_declarations"])
    )
    view = deepcopy(p)
    view["diffusivity_m2_s"] = static["profile_result"]["diffusion_m2_s"]
    ids = p["geometry"]["layout"]["membrane_ids"]
    view["binding"]["targets"] = {
        name: dict(membranes=[ids[i] for i in row["membranes"]])
        for name, row in static["profile_result"]["targets"].items()
    }
    request = deepcopy(provenance["request"]["barrier_request"])
    request["kind"] = static_barriers.REQUEST_KIND
    request["definition"] = deepcopy(static["definition"])
    request["definition"]["model"]["id"] = "resolved_tissue@1"
    exterior = static_barriers.prepare(request)
    proxy = deepcopy(parent)
    proxy["model"] = deepcopy(parent["model"]["ionic"])
    proxy["model"].update(
        profile_preparation=dict(provenance=view),
        interventions=deepcopy(m["membrane_interventions"]),
        phase=m["phase"],
        timing_policy=m["timing_policy"],
        reset_policy=m["reset_policy"],
    )
    for key in ("intervention_capacity", "intervention_target_capacity"):
        proxy["execution"][key] = raw["execution"][key]
    tolerance = (
        64 * np.finfo(float).eps * max(raw["experiment"]["end_time"], raw["execution"]["dt"])
    )
    return dict(
        equation=equation,
        parent=physical,
        parent_definition=parent,
        membrane_proxy=proxy,
        barrier_context=dict(
            request=request,
            static=exterior,
            event=deepcopy(m["barrier_intervention"]),
            phase=m["phase"],
            end_time=raw["experiment"]["end_time"],
            phase_clock_atol_s=tolerance,
        ),
        shapes=physical["shapes"] | dict(phase_clock_s=(1,)),
        phase_clock_atol_s=tolerance,
    )


def initial(context):
    return np.r_[context["equation"].initial(context["parent"]), 0.0]


def evaluate(context, vector, time, *, held_time=None):
    clock = float(vector[-1])
    if abs(clock - float(time)) > context["phase_clock_atol_s"]:
        raise ValueError("Full-owner stage clock mismatch")
    parameters, membrane = membranes.permeability(context["membrane_proxy"], clock)
    exterior = barriers.coefficients(context["barrier_context"], clock)
    raw = deepcopy(context["parent_definition"])
    target = raw["model"]["ionic"]
    values = {v["id"]: v["permeability_m_per_s"] for v in parameters["model"]["membranes"]}
    for patch in target["membranes"]:
        patch["permeability_m_per_s"] = values[patch["id"]]
    for face in target["faces"]:
        face["diffusivity_m2_per_s"] = {
            sid: exterior["face_m2_s"][sid][face["id"]] for sid in face["diffusivity_m2_per_s"]
        }
    if held_time is not None:
        for name, groups in raw["experiment"].items():
            if name.endswith("_controls"):
                for group in groups:
                    key = "controls" if "controls" in group else "schedule"
                    selected = deepcopy(
                        next(v for v in reversed(group[key]) if v["time"] <= held_time)
                    )
                    selected["time"] = 0.0
                    group[key] = [selected]
    current = context["equation"].bind(raw)
    derivative, phi, proof = context["equation"].evaluate(current, vector[:-1], clock)
    return (
        np.r_[derivative, 1.0],
        phi,
        proof | dict(membrane_coefficients=membrane, barrier_coefficients=exterior),
    )


def conservation(context, vector):
    """Direct 80-digit molecular energy, ion ownership and neutral-pool invariants."""
    parent = context["parent"]
    fields = unpack(context, vector)
    clock = float(fields["phase_clock_s"][0])
    _, potential, _ = evaluate(context, vector, clock)
    if "initial_phi" not in context:
        zero = initial(context)
        context["initial_phi"] = evaluate(context, zero, 0.0)[1]
    calcium = parent.get("calcium", parent)
    ion = context["parent_definition"]["model"]["ionic"]
    before_phi = context["initial_phi"]
    with localcontext() as precision:
        precision.prec = 80

        def dec(value):
            return Decimal(str(float(value)))

        rt = dec(R) * dec(parent["layout"]["temperature"]) * Decimal("0.001")
        stored = Decimal(0)
        if "chemical_amount_increment" in fields:
            for i, store in enumerate(calcium["stores"]):
                for s in range(len(store.ids)):
                    for k in range(store.n0.shape[1]):
                        a0 = dec(store.n0[s, k])
                        amount = a0 + dec(fields["chemical_amount_increment"][i, s, k])
                        denominator = dec(store.volume[k]) * dec(store.c0)
                        stored += rt * (
                            amount * (dec(store.mu0[s]) + (amount / denominator).ln() - 1)
                            - a0 * (dec(store.mu0[s]) + (a0 / denominator).ln() - 1)
                        )
                change = (
                    Decimal("1e-15")
                    * dec(F)
                    / dec(store.cap)
                    * sum(
                        dec(z) * dec(a)
                        for z, a in zip(
                            store.z,
                            fields["chemical_amount_increment"][i, :, store.er],
                            strict=True,
                        )
                    )
                )
                stored += (
                    Decimal("0.5e12")
                    * dec(store.cap)
                    * change
                    * (2 * dec(store.membrane["initial_voltage_V"]) + change)
                )
        else:
            for s in range(parent["ai"].shape[0]):
                for i in range(len(parent["vi"])):
                    a0 = dec(parent["ai"][s, i])
                    amount = a0 + dec(fields["amount_increment"][s, i])
                    volume = dec(parent["vi"][i])
                    stored += rt * (
                        amount * ((amount / volume).ln() - 1) - a0 * ((a0 / volume).ln() - 1)
                    )
        for s in range(parent["ao"].shape[0]):
            for i in range(len(parent["vo"])):
                a0 = dec(parent["ao"][s, i])
                amount = a0 + dec(fields["extracellular_amount_increment"][s, i])
                volume = dec(parent["vo"][i])
                stored += rt * (
                    amount * ((amount / volume).ln() - 1) - a0 * ((a0 / volume).ln() - 1)
                )
        cells = [p["id"] for p in ion["cells"]]
        outsides = [p["id"] for p in ion["extracellular"]]
        n = len(cells)
        for patch in ion["membranes"]:
            i, o = cells.index(patch["inside"]), n + outsides.index(patch["outside"])
            voltage, before = dec(potential[i] - potential[o]), dec(before_phi[i] - before_phi[o])
            stored += (
                Decimal("0.5e12")
                * dec(patch["capacitance_F"])
                * (voltage - before)
                * (voltage + before)
            )
        if "energy_amount_increment_fmol" in fields:
            pool_initial = parent["energy_initial"]
            current = pool_initial + fields["energy_amount_increment_fmol"]
            stored += sum(
                dec(
                    pools.free_energy_change(
                        pool_initial[:, i],
                        current[:, i],
                        parent["vi"][i],
                        parent["vi"][i],
                        parent["temperature"],
                        parent["energy_delta_g0"][i],
                    )
                )
                for i in range(n)
            )
        heat = sum(dec(np.sum(v)) for k, v in fields.items() if k.endswith("_dissipated_energy_pJ"))
        work_names = (
            ("regeneration_supplied_work_pJ",)
            if "energy_amount_increment_fmol" in fields
            else ("metabolic_work_pJ", "plasma_metabolic_work_pJ", "er_metabolic_work_pJ")
        )
        work = sum(
            dec(np.sum(fields[k]))
            for k in (*work_names, "reservoir_work_pJ", "electrode_work_pJ")
            if k in fields
        )
        residual = float(stored + heat - work)
    local = fields["amount_increment"].copy()
    outside = fields["extracellular_amount_increment"].copy() - fields["reservoir_supplied"]
    for j, route in enumerate(ion["membranes"]):
        i, o = cells.index(route["inside"]), outsides.index(route["outside"])
        flux = fields["membrane_transferred"][:, j].copy()
        for c, ch in enumerate(ion["channels"]):
            if ch["membrane_id"] == route["id"]:
                flux += fields["channel_transferred"][:, c]
        if route["pump"] is not None:
            ids = [s["id"] for s in ion["species"]]
            flux[ids.index("Na")] += 3 * fields["pump_cycles"][j]
            flux[ids.index("K")] -= 2 * fields["pump_cycles"][j]
        if "plasma_pump_cycles" in fields:
            ids = [s["id"] for s in ion["species"]]
            flux[ids.index("Ca")] += (
                fields["plasma_pump_cycles"][j]
                + fields["plasma_exchange_cycles"][j]
                + fields["calcium_channel_transferred"][j]
            )
            flux[ids.index("Na")] -= 3 * fields["plasma_exchange_cycles"][j]
        local[:, i] += flux
        outside[:, o] -= flux
    for family, values, names in (("junction", local, cells), ("face", outside, outsides)):
        for j, route in enumerate(ion[family + "s"]):
            values[:, names.index(route["sender"])] += fields[family + "_transferred"][:, j]
            values[:, names.index(route["receiver"])] -= fields[family + "_transferred"][:, j]
    result = dict(
        energy_pJ=residual,
        local_material_fmol=float(np.max(np.abs(local), initial=0)),
        outside_material_fmol=float(np.max(np.abs(outside), initial=0)),
    )
    if "energy_amount_increment_fmol" in fields:
        change = fields["energy_amount_increment_fmol"]
        result.update(
            adenylate_fmol=float(np.max(np.abs(change[0] + change[1]), initial=0)),
            phosphorus_fmol=float(
                np.max(np.abs(3 * change[0] + 2 * change[1] + change[2]), initial=0)
            ),
        )
    return result
