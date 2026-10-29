"""Independent native coefficients and complete water@2/repair@2 physics.

Decimal coefficient recipes and full molecular, finite-fuel, moving-volume and
lesion equations use no Cells/JAX imports. Physical stage fields are complete.
"""

import math
from copy import deepcopy

import numpy as np

from validation.tissue import calcium_energy_water_hcn_extra_reference as water
from validation.tissue import calcium_energy_water_repair_hcn_extra_reference as repair
from validation.topology import surface_profile_interventions_reference as membranes
from validation.topology import tissue_profile_preparation_reference as static_membranes
from validation.transport import environment_barrier_interventions_reference as barriers
from validation.transport import environment_barrier_preparation_reference as static_barriers

OWNERS = {
    "resolved_calcium_energy_water_profile_barriers@1": (water.MODEL_ID, water),
    "resolved_calcium_energy_water_repair_profile_barriers@1": (repair.MODEL_ID, repair),
}
EXTRA = (
    "coupled_preparation",
    "membrane_interventions",
    "barrier_intervention",
    "phase",
    "timing_policy",
    "reset_policy",
)
flatten, unpack = water.flatten, water.unpack
F, R = water.F, water.R


def normalized_owners(value):
    if isinstance(value, dict):
        return {
            key: sorted(item)
            if key == "moieties"
            and isinstance(item, list)
            and all(isinstance(s, str) for s in item)
            else normalized_owners(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        rows = [normalized_owners(item) for item in value]
        for key in ("id", "cell_id", "membrane_id", "channel_id", "compartment_id"):
            if rows and all(isinstance(row, dict) and key in row for row in rows):
                if len({row[key] for row in rows}) == len(rows):
                    return sorted(rows, key=lambda row: row[key])
        return rows
    return value


def _same_owner(actual, expected):
    actual = deepcopy(actual)
    target, source = actual["ionic"], expected["ionic"]
    for domain, key in (
        ("membranes", "permeability_m_per_s"),
        ("junctions", "permeability_m_per_s"),
        ("faces", "diffusivity_m2_per_s"),
    ):
        values = {row["id"]: row[key] for row in source[domain]}
        if set(values) != {row["id"] for row in target[domain]}:
            raise ValueError("Static preparation changed route owners")
        for row in target[domain]:
            recipe = values[row["id"]]
            if set(recipe) != set(row[key]) or any(
                not math.isclose(
                    row[key][species], value, rel_tol=64 * np.finfo(float).eps, abs_tol=0
                )
                for species, value in recipe.items()
            ):
                raise ValueError("Static coefficients differ from the independent Decimal recipe")
            row[key] = deepcopy(recipe)
    if normalized_owners(actual) != normalized_owners(expected):
        raise ValueError("Static preparation changed a physical owner, anchor, store or pool")


def _check_static_owners(parent, provenance, membrane, exterior):
    profile = provenance["profile_preparation"]
    expected = deepcopy(profile["provenance"]["source_definition"]["model"])
    if expected["id"] != parent["model"]["id"]:
        raise ValueError("Wrong complete parent in the membrane recipe")
    leaf = expected["ionic"]
    for domain in ("membranes", "junctions"):
        source = {row["id"]: row for row in membrane["definition"]["model"][domain]}
        for row in leaf[domain]:
            row["permeability_m_per_s"] = deepcopy(source[row["id"]]["permeability_m_per_s"])
    _same_owner(profile["definition"]["model"], expected)
    request = provenance["request"]["barrier_request"]
    _same_owner(request["definition"]["model"], expected)
    faces = {row["id"]: row for row in exterior["definition"]["model"]["faces"]}
    for row in leaf["faces"]:
        row["diffusivity_m2_per_s"] = deepcopy(faces[row["id"]]["diffusivity_m2_per_s"])
    _same_owner(provenance["barrier_preparation"]["definition"]["model"], expected)
    _same_owner(parent["model"], expected)


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
    if (
        m["phase"] not in ("INIT", "SIM")
        or m["timing_policy"] != "phase_clock_rk_stage_native_logistic@1"
        or m["reset_policy"] != "fresh_phase_zero_scheduled_sim_only@1"
        or provenance["kind"] != "cells.joint_water_profile_barrier_preparation@1"
        or provenance["order"] != "static_membrane_profiles_then_extracellular_barriers@1"
    ):
        raise ValueError("Require explicit complete-owner preparation and shared fresh phase clock")
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
    _check_static_owners(parent, provenance, static, exterior)
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
        end_time=raw["experiment"]["end_time"],
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


def current_definition(context, vector, time=None, *, held_time=None):
    values = unpack(context, vector)
    clock = float(values["phase_clock_s"][0])
    if (
        not np.isfinite(vector).all()
        or not math.isfinite(clock)
        or not 0 <= clock <= context["end_time"] + context["phase_clock_atol_s"]
        or (
            time is not None
            and (
                not math.isfinite(float(time))
                or abs(clock - float(time)) > context["phase_clock_atol_s"]
            )
        )
    ):
        raise ValueError("Complete water/repair stage clock mismatch or invalid state")
    held = clock if held_time is None else float(held_time)
    if not math.isfinite(held) or not 0 <= held <= clock + context["phase_clock_atol_s"]:
        raise ValueError("Invalid left-held physical control time")
    parameters, membrane = membranes.permeability(context["membrane_proxy"], clock)
    exterior = barriers.coefficients(context["barrier_context"], clock)
    raw = deepcopy(context["parent_definition"])
    target = raw["model"]["ionic"]
    by_id = {row["id"]: row["permeability_m_per_s"] for row in parameters["model"]["membranes"]}
    for patch in target["membranes"]:
        patch["permeability_m_per_s"] = by_id[patch["id"]]
    for face in target["faces"]:
        face["diffusivity_m2_per_s"] = {
            species: exterior["face_m2_s"][species][face["id"]]
            for species in face["diffusivity_m2_per_s"]
        }
    return raw, held, membrane, exterior


def evaluate(context, vector, time=None, *, held_time=None):
    raw, held, membrane, exterior = current_definition(context, vector, time, held_time=held_time)
    equation = context["equation"]
    current = equation.bind(raw)
    slope, phi, proof = equation.evaluate(current, vector[:-1], held)
    return (
        np.r_[slope, 1.0],
        phi,
        proof
        | dict(
            membrane_coefficients=membrane,
            barrier_coefficients=exterior,
            background_and_face_parameter_work_pJ_s=0.0,
        ),
    )


def conservation(context, vector):
    """Original molecular/pool/compliance energy and local material/water ledgers."""
    fields = unpack(context, vector)
    clock = float(fields["phase_clock_s"][0])
    parent = context["parent"]
    equation = context["equation"]
    stored = equation.free_energy_change(parent, vector[:-1], clock)
    heat = math.fsum(
        float(np.sum(value))
        for key, value in fields.items()
        if key.endswith("_dissipated_energy_pJ")
    )
    work = math.fsum(
        float(np.sum(fields[key]))
        for key in ("regeneration_supplied_work_pJ", "reservoir_work_pJ", "electrode_work_pJ")
    )
    residual = stored + heat - work
    ion = context["parent_definition"]["model"]["ionic"]
    cells = [row["id"] for row in ion["cells"]]
    outsides = [row["id"] for row in ion["extracellular"]]
    local = fields["amount_increment"].copy()
    outside = fields["extracellular_amount_increment"].copy() - fields["reservoir_supplied"]
    for j, route in enumerate(ion["membranes"]):
        i, o = cells.index(route["inside"]), outsides.index(route["outside"])
        flux = fields["membrane_transferred"][:, j].copy()
        if "injury_transferred" in fields:
            flux += fields["injury_transferred"][:, j]
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
    local_water = fields["volume_increment_pL"].copy()
    outside_water = fields["extracellular_volume_increment_pL"].copy()
    for j, route in enumerate(ion["membranes"]):
        local_water[cells.index(route["inside"])] += fields["water_transferred_pL"][j]
        outside_water[outsides.index(route["outside"])] -= fields["water_transferred_pL"][j]
    result.update(
        water_local_pL=float(np.max(np.abs(local_water), initial=0)),
        water_outside_pL=float(np.max(np.abs(outside_water), initial=0)),
        water_total_pL=float(
            abs(
                np.sum(fields["volume_increment_pL"])
                + np.sum(fields["extracellular_volume_increment_pL"])
            )
        ),
    )
    if "damage" in fields:
        result["damage_ledger"] = float(
            np.max(
                np.abs(
                    fields["damage"]
                    - context["parent"]["initial_damage"]
                    - fields["damage_opened"]
                    + fields["damage_closed"]
                ),
                initial=0,
            )
        )
    return result
