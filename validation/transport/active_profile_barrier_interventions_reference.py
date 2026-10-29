"""Independent raw-recipe coefficients and the exact full56 ionic equations."""

from copy import deepcopy
from decimal import Decimal, localcontext

import numpy as np

from validation.tissue import surface_kinetic_reference as active
from validation.topology import surface_profile_interventions_reference as membranes
from validation.topology import tissue_profile_preparation_reference as static_membranes
from validation.transport import environment_barrier_interventions_reference as barriers
from validation.transport import environment_barrier_preparation_reference as static_barriers
from validation.transport.owned_barrier_interventions_reference import _ionic_energy_rate

EXTRA = (
    "coupled_preparation",
    "membrane_interventions",
    "barrier_intervention",
    "phase",
    "timing_policy",
    "reset_policy",
)
flatten, unpack = active.flatten, active.unpack


def bind(raw):
    model = raw["model"]
    if model["id"] != "resolved_active_profile_barriers@1":
        raise ValueError("Wrong combined owner")
    provenance = model["coupled_preparation"]["provenance"]
    p = provenance["profile_preparation"]["provenance"]
    declarations = p["profile_declarations"]
    static = static_membranes.prepare(
        dict(definition=p["source_definition"], geometry=p["geometry"], **declarations)
    )
    geometry = p["geometry"]["layout"]
    profile_view = deepcopy(p)
    profile_view["diffusivity_m2_s"] = static["profile_result"]["diffusion_m2_s"]
    targets = static["profile_result"]["targets"]
    profile_view["binding"]["targets"] = {
        name: dict(membranes=[geometry["membrane_ids"][i] for i in row["membranes"]])
        for name, row in targets.items()
    }
    request = deepcopy(provenance["request"]["barrier_request"])
    request["definition"] = deepcopy(static["definition"])
    request["definition"]["model"]["id"] = "resolved_tissue@1"
    request["kind"] = static_barriers.REQUEST_KIND
    exterior = static_barriers.prepare(request)
    parent = deepcopy(raw)
    for key in EXTRA:
        parent["model"].pop(key)
    parent["model"]["id"] = "resolved_tissue@12"
    for key in ("intervention_capacity", "intervention_target_capacity", "barrier_target_capacity"):
        parent["execution"].pop(key)
    tolerance = (
        64 * np.finfo(float).eps * max(raw["experiment"]["end_time"], raw["execution"]["dt"])
    )
    physical = active.bind(parent)
    proxy = deepcopy(parent)
    proxy["model"].update(
        profile_preparation=dict(provenance=profile_view),
        interventions=deepcopy(model["membrane_interventions"]),
        phase=model["phase"],
        timing_policy=model["timing_policy"],
        reset_policy=model["reset_policy"],
    )
    for key in ("intervention_capacity", "intervention_target_capacity"):
        proxy["execution"][key] = raw["execution"][key]
    # Check static coefficients by stable IDs; independent Decimal arithmetic
    # may differ by an ulp from the production conversion.
    actual_mem = {v["id"]: v for v in parent["model"]["membranes"]}
    for expected in static["definition"]["model"]["membranes"]:
        for sid, value in expected["permeability_m_per_s"].items():
            np.testing.assert_allclose(
                actual_mem[expected["id"]]["permeability_m_per_s"][sid], value, rtol=5e-14, atol=0
            )
    expected_faces = {v["id"]: v for v in exterior["definition"]["model"]["faces"]}
    for face in parent["model"]["faces"]:
        for sid, value in face["diffusivity_m2_per_s"].items():
            np.testing.assert_allclose(
                value, expected_faces[face["id"]]["diffusivity_m2_per_s"][sid], rtol=5e-14, atol=0
            )
    return dict(
        parent=physical,
        parent_definition=parent,
        membrane_proxy=proxy,
        barrier_context=dict(
            request=request,
            static=exterior,
            event=deepcopy(model["barrier_intervention"]),
            phase=model["phase"],
            end_time=raw["experiment"]["end_time"],
            phase_clock_atol_s=tolerance,
        ),
        shapes=physical["shapes"] | dict(phase_clock_s=(1,)),
        phase_clock_atol_s=tolerance,
    )


def initial(context):
    return np.r_[active.initial(context["parent"]), 0.0]


def evaluate(context, vector, time, *, held_time=None):
    clock = float(vector[-1])
    if abs(clock - float(time)) > context["phase_clock_atol_s"]:
        raise ValueError("Stage clock mismatch")
    coefficients, membrane = membranes.permeability(context["membrane_proxy"], clock)
    exterior = barriers.coefficients(context["barrier_context"], clock)
    raw = deepcopy(context["parent_definition"])
    values = {v["id"]: v["permeability_m_per_s"] for v in coefficients["model"]["membranes"]}
    for patch in raw["model"]["membranes"]:
        patch["permeability_m_per_s"] = values[patch["id"]]
    for face in raw["model"]["faces"]:
        face["diffusivity_m2_per_s"] = {
            sid: exterior["face_m2_s"][sid][face["id"]] for sid in face["diffusivity_m2_per_s"]
        }
    if held_time is not None:
        for name, groups in raw["experiment"].items():
            if name.endswith("_controls"):
                for group in groups:
                    group["schedule"] = [
                        dict(
                            time=0.0,
                            availability=next(
                                v["availability"]
                                for v in reversed(group["schedule"])
                                if v["time"] <= held_time
                            ),
                        )
                    ]
    parent = active.bind(raw)
    derivative, potential, proof = active.evaluate(parent, vector[:-1], clock)
    return (
        np.r_[derivative, 1.0],
        potential,
        proof
        | dict(
            membrane_coefficients=membrane,
            barrier_coefficients=exterior,
            physical_energy_balance_pJ_s=_ionic_energy_rate(
                parent, vector[:-1], derivative, potential
            ),
        ),
    )


def conservation(context, vector):
    """Ideal-ion/capacitor energy and explicit complete-history owner loops."""
    c = context["parent"]
    d = unpack(context, vector)
    m = context["parent_definition"]["model"]
    phi = evaluate(context, vector, float(vector[-1]))[1]
    if "initial_phi" not in context:
        context["initial_phi"] = evaluate(context, initial(context), 0.0)[1]
    cells = [v["id"] for v in m["cells"]]
    outside = [v["id"] for v in m["extracellular"]]
    species = [v["id"] for v in m["species"]]
    mid = [v["id"] for v in m["membranes"]]
    with localcontext() as precision:
        precision.prec = 80

        def dec(value):
            return Decimal(str(float(value)))

        rt = Decimal("0.001") * dec(active.R) * dec(m["temperature_K"])
        energy = Decimal(0)
        for before, delta, volume in (
            (c["ai"], d["amount_increment"], c["vi"]),
            (c["ao"], d["extracellular_amount_increment"], c["vo"]),
        ):
            for s in range(len(species)):
                for i in range(len(volume)):
                    a0 = dec(before[s, i])
                    a = a0 + dec(delta[s, i])
                    v = dec(volume[i])
                    energy += rt * (a * ((a / v).ln() - 1) - a0 * ((a0 / v).ln() - 1))
        for patch in m["membranes"]:
            i, o = cells.index(patch["inside"]), len(cells) + outside.index(patch["outside"])
            voltage, before = (
                dec(phi[i] - phi[o]),
                dec(context["initial_phi"][i] - context["initial_phi"][o]),
            )
            energy += (
                Decimal("0.5e12")
                * dec(patch["capacitance_F"])
                * (voltage - before)
                * (voltage + before)
            )
        energy += sum(dec(np.sum(v)) for k, v in d.items() if k.endswith("_dissipated_energy_pJ"))
        energy -= sum(
            dec(np.sum(d[k]))
            for k in ("metabolic_work_pJ", "reservoir_work_pJ", "electrode_work_pJ")
        )
    local = d["amount_increment"].copy()
    external = d["extracellular_amount_increment"].copy() - d["reservoir_supplied"]
    transport = d["membrane_transferred"].copy()
    for j, ch in enumerate(m["channels"]):
        transport[:, mid.index(ch["membrane_id"])] += d["channel_transferred"][:, j]
    for j, patch in enumerate(m["membranes"]):
        if patch["pump"] is not None:
            transport[species.index(patch["pump"]["roles"]["sodium"]), j] += 3 * d["pump_cycles"][j]
            transport[species.index(patch["pump"]["roles"]["potassium"]), j] -= (
                2 * d["pump_cycles"][j]
            )
        local[:, cells.index(patch["inside"])] += transport[:, j]
        external[:, outside.index(patch["outside"])] -= transport[:, j]
    for family, values, names in (("junction", local, cells), ("face", external, outside)):
        for j, route in enumerate(m[family + "s"]):
            values[:, names.index(route["sender"])] += d[family + "_transferred"][:, j]
            values[:, names.index(route["receiver"])] -= d[family + "_transferred"][:, j]
    return dict(
        energy_pJ=float(energy),
        local_material_fmol=float(np.max(np.abs(local), initial=0)),
        outside_material_fmol=float(np.max(np.abs(external), initial=0)),
    )
