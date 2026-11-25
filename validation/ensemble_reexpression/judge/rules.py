"""The scales, the amount references and the closures by their rules (SPEC section 5 and section 6),
from a world's block alone.
"""

from __future__ import annotations

import math

from . import constants as c
from .registration import World


def scales(world: World) -> tuple:
    """(scales, amount_refs, closure_terms_V) of a world, by rule."""
    block, K = world.block, world.constants
    F, R, unit = K["F_C_per_mol"], K["R_J_per_mol_K"], K["fmol_to_mol"]
    T, T_K = world.end_s, block["temperature_K"]
    RT = R * T_K
    drive = {x: abs(world.valence[x]) * F * c.V_STAR / RT for x in world.species}
    chi = {x: 1 + drive[x] for x in world.species}

    compartments = {**block["cells"], **block["outside"]}
    conc = {
        k: {x: v["initial_amount_fmol"][x] / v["volume_pL"] for x in world.species}
        for k, v in compartments.items()
    }

    def gross(conductance, a, b, x):
        return conductance / unit * max(conc[a][x], conc[b][x]) * chi[x] * T

    def passive_heat(route, a, b):
        return sum(
            v * 1e-3 * RT * (1 + abs(math.log(conc[a][x] / conc[b][x])) + drive[x])
            for x, v in route.items()
        )

    touching = {k: {x: 0.0 for x in world.species} for k in compartments}
    leaks, channels, pumps, junctions, faces = {}, {}, {}, {}, {}
    for m, v in block["membranes"].items():
        a, b = v["inside"], v["outside"]
        leaks[m] = {
            x: gross(p * v["area_m2"], a, b, x)
            for x, p in v["passive"]["permeability_m_per_s"].items()
        }
        for x, value in leaks[m].items():
            touching[a][x] += value
            touching[b][x] += value
        if v["pump"] is not None:
            pumps[m] = v["pump"]["capacity_fmol_per_s"] * T
            for x, nu in v["pump"]["stoichiometry"].items():
                touching[a][x] += abs(nu) * pumps[m]
                touching[b][x] += abs(nu) * pumps[m]
    for k in world.channels:
        v = block["channels"][k]
        m = block["membranes"][v["membrane_id"]]
        a, b, x = m["inside"], m["outside"], v["species_id"]
        channels[k] = {
            x: gross(v["max_permeability_m_per_s"] * v["abundance"] * m["area_m2"], a, b, x)
        }
        touching[a][x] += channels[k][x]
        touching[b][x] += channels[k][x]
    for j in world.junctions:
        v = block["junctions"][j]
        a, b = v["from_cell"], v["to_cell"]
        junctions[j] = {
            x: gross(p * v["area_m2"], a, b, x) for x, p in v["permeability_m_per_s"].items()
        }
        for x, value in junctions[j].items():
            touching[a][x] += value
            touching[b][x] += value
    for f in world.faces:
        v = block["faces"][f]
        a, b = v["sender"], v["receiver"]
        faces[f] = {
            x: gross(d * v["area_m2"] / v["length_m"], a, b, x)
            for x, d in v["diffusivity_m2_per_s"].items()
        }
        for x, value in faces[f].items():
            touching[a][x] += value
            touching[b][x] += value

    def pump_heat(m):
        v = block["membranes"][m]
        fuel = v["pump"]["metabolism"]
        a, b, na, k = (
            v["inside"],
            v["outside"],
            v["pump"]["roles"]["sodium"],
            v["pump"]["roles"]["potassium"],
        )
        volts = F * c.V_STAR / RT
        out = abs(fuel["delta_g0_J_per_mol"]) + RT * abs(
            math.log(fuel["adp_mM"] * fuel["pi_mM"] / (1000 * fuel["atp_mM"]))
        )
        out += 3 * RT * (1 + abs(math.log(conc[a][na] / conc[b][na])) + volts)
        out += 2 * RT * (1 + abs(math.log(conc[a][k] / conc[b][k])) + volts)
        return pumps[m] * 1e-3 * out

    def work(m):
        fuel = block["membranes"][m]["pump"]["metabolism"]
        energy = abs(fuel["delta_g0_J_per_mol"]) + RT * abs(
            math.log(fuel["adp_mM"] * fuel["pi_mM"] / (1000 * fuel["atp_mM"]))
        )
        return pumps[m] * 1e-3 * energy

    membrane_heat = {}
    for m, v in block["membranes"].items():
        total = passive_heat(leaks[m], v["inside"], v["outside"])
        if m in pumps:
            total += pump_heat(m)
        for k in world.channels_of(m):
            total += passive_heat(channels[k], v["inside"], v["outside"])
        membrane_heat[m] = total
    junction_heat = {
        j: passive_heat(
            junctions[j], block["junctions"][j]["from_cell"], block["junctions"][j]["to_cell"]
        )
        for j in junctions
    }
    face_heat = {
        f: passive_heat(faces[f], block["faces"][f]["sender"], block["faces"][f]["receiver"])
        for f in faces
    }

    out = {}
    for x in world.species:
        out[f"n_cell_{x}"] = max(touching[k][x] for k in world.cells)
        out[f"n_out_{x}"] = max(touching[k][x] for k in world.regions)
        if not world.zero_routes:
            out[f"leak_{x}"] = max(route[x] for route in leaks.values())
        if junctions:
            out[f"junction_{x}"] = max(route[x] for route in junctions.values())
        if faces:
            out[f"face_{x}"] = max(route[x] for route in faces.values())
        found = [route[x] for route in channels.values() if x in route]
        if found:
            out[f"channel_{x}"] = max(found)
    if channels:
        out["gate_m"] = out["gate_h"] = 1.0
    if pumps:
        out["pump"] = max(pumps.values())
    if junctions:
        out["junction_gate"] = 1.0
        out["heat_junction"] = max(junction_heat.values())
    if faces:
        out["heat_face"] = max(face_heat.values())
    if pumps or channels or not world.zero_routes:
        out["heat_membrane"] = max(membrane_heat.values())

    def volts(m, amounts):
        v = block["membranes"][m]
        return (
            F
            * unit
            / v["capacitance_F"]
            * sum(abs(world.valence[x]) * amounts(v["inside"])[x] for x in world.species)
        )

    out["voltage"] = max(abs(v["initial_voltage_V"]) for v in block["cells"].values())
    out["voltage"] += max(volts(m, lambda k: touching[k]) for m in world.membranes)
    close = {}
    if "phi_out" in world.data["scales"]:
        out["phi_out"] = RT / F
        close["phi_out"] = c.PHI_CLOSE_SHARE * c.V_STAR
    energy = (
        sum(membrane_heat.values())
        + sum(junction_heat.values())
        + sum(face_heat.values())
        + sum(work(m) for m in pumps)
    )
    for k in compartments:
        energy += sum(
            touching[k][x] * 1e-3 * RT * (1 + abs(math.log(conc[k][x]))) for x in world.species
        )
    energy += sum(
        1e12 * block["membranes"][m]["capacitance_F"] * out["voltage"] ** 2 for m in world.membranes
    )
    out["energy_identity"] = energy

    def initial(k):
        return compartments[k]["initial_amount_fmol"]

    refs = {}
    for x in world.species:
        refs[f"n_cell_{x}"] = max(initial(k)[x] for k in world.cells)
        refs[f"n_out_{x}"] = max(initial(k)[x] for k in world.regions)
    refs["voltage"] = max(volts(m, initial) for m in world.membranes)
    total = sum(
        1e-3 * RT * (1 + abs(math.log(conc[k][x]))) * initial(k)[x]
        for k in compartments
        for x in world.species
    )
    total += sum(
        1e12 * block["membranes"][m]["capacitance_F"] * out["voltage"] * volts(m, initial)
        for m in world.membranes
    )
    refs["energy_identity"] = total
    return out, refs, close
