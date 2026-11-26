"""The invented worlds of Part 2: calcium stores in two cells, in the form of PART2_BLOCKS.

The worlds are this file's own: no number of them is inputs_part2.json's or a rehearsal's, and
nothing of them is judged. `invented()` is an inputs file of them (the rows and the format sample).
"""

import copy
import math

from validation.ensemble_reexpression import sample
from validation.ensemble_reexpression.inputs import SCHEMA

ONES = [[0.0, 1.0]]
CALCIUM_MM = {"c_a": 0.0023, "c_b": 0.0017, "bath": 0.011, "shell": 0.009, "rim": 0.008}
CARRIED = {"m_a": 4.7e-08, "m_b": 5.3e-08}  # Calcium's leak (m/s) on each plasma membrane.
POTENTIAL = {  # Standard potentials over RT at 1 mM.
    "Ca": 0.0,
    "B": 0.0,
    "CaB": -math.log(700.0),
    "Ca2B": -math.log(9.0e4),
    "K": 0.0,
    "Na": 0.0,
    "Cl": 0.0,
}
VALENCE = {"Ca": 2, "B": -2, "CaB": 0, "Ca2B": 2, "K": 1, "Na": 1, "Cl": -1}
IP3 = {"IP3": (-3, 0.0), "IP3_buffer": (0, 0.0), "IP3_bound": (-3, -math.log(8000.0))}
BUFFER_MM = {"B": 0.052, "CaB": 0.011, "Ca2B": 0.0012}
IP3_MM = {"IP3": 0.00011, "IP3_buffer": 0.0011, "IP3_bound": 0.00021}
END_S = sample.END_S


def ionic(channel_controls):
    """The sample's cluster with calcium as a fourth species of every entity."""
    block = copy.deepcopy(sample.cluster(channel_controls))
    block["species"] = dict(block["species"]) | {"Ca": 2}
    for name, node in (*block["cells"].items(), *block["outside"].items()):
        calcium = CALCIUM_MM[name] * node["volume_pL"]
        node["initial_amount_fmol"] = dict(node["initial_amount_fmol"]) | {"Ca": calcium}
        node["fixed_charge_equivalent_fmol"] -= 2 * calcium
    for name, membrane in block["membranes"].items():
        passive = membrane["passive"]
        passive["permeability_m_per_s"] = dict(passive["permeability_m_per_s"])
        passive["permeability_m_per_s"]["Ca"] = CARRIED[name]
    block["junctions"]["j_ab"]["permeability_m_per_s"]["Ca"] = 1.7e-08
    for face in block["faces"].values():
        face["diffusivity_m2_per_s"]["Ca"] = 7.7e-10
    block["material_tolerance_fmol"] = dict(block["material_tolerance_fmol"]) | {"Ca": 1e-10}
    return block


def calcium_pump(capacity):
    return {
        "law": "calcium_pump_positive",
        "capacity_fmol_per_s": capacity,
        "km_ca_mM": 0.0012,
        "km_atp_mM": 0.45,
        "atp_mM": 1.3,
        "adp_mM": 0.12,
        "pi_mM": 0.14,
        "delta_g0_at_1M_J_per_mol": -19123.4,
    }


def reactions(ip3):
    out = {
        f"bind_{k}_{name}": {
            "compartment": compartment,
            "reactants": {"Ca": 1, with_: 1},
            "products": {product: 1},
            "forward_rate_per_s": rate,
        }
        for k, compartment in enumerate(("cytosol", "er"))
        for name, with_, product, rate in (
            ("first", "B", "CaB", 1100.0),
            ("second", "CaB", "Ca2B", 120.0),
        )
    }
    if ip3:
        out["ip3_binding"] = {
            "compartment": "cytosol",
            "reactants": {"IP3": 1, "IP3_buffer": 1},
            "products": {"IP3_bound": 1},
            "forward_rate_per_s": 17000.0,
        }
    return out


def store(cell, scale, *, ip3):
    """A cell's store of a twelfth of its volume, with its buffers and its membrane."""
    inside, outside = cell["volume_pL"], cell["volume_pL"] / 12
    species = {s: {"valence": z, "standard_mu_RT": POTENTIAL[s]} for s, z in VALENCE.items()}
    extra = IP3 if ip3 else {}
    species |= {s: {"valence": z, "standard_mu_RT": mu} for s, (z, mu) in extra.items()}
    buffers = BUFFER_MM | (IP3_MM if ip3 else {})
    cytosol = {s: c * inside for s, c in buffers.items()} | dict(cell["initial_amount_fmol"])
    er = {s: c * outside for s, c in buffers.items()}
    er |= {"Ca": 0.21 * outside, "K": 131.0 * outside, "Na": 12.0 * outside, "Cl": 9.0 * outside}
    return {
        "law": "mass_action_passive",
        "temperature_K": 301.0,
        "standard_concentration_mM": 1.0,
        "species": species,
        "compartments": {
            "cytosol": {"volume_pL": inside, "initial_amount_fmol": cytosol},
            "er": {"volume_pL": outside, "initial_amount_fmol": er},
        },
        "reactions": reactions(ip3),
        "membrane": {
            "cytosol": "cytosol",
            "er": "er",
            "area_m2": 1.2e-09 * scale,
            "capacitance_F": 1.3e-11 * scale,
            "initial_voltage_V": 0.0,
            "initial_charge_C": 0.0,
            "permeability_m_per_s": {s: 0.0 for s in species} | {"Ca": 1.2e-08, "K": 0.9e-07},
            "pump": calcium_pump(0.0031 * scale),
            "release": {
                "law": "hill_product_factor",
                "permeability_m_per_s": 1.3e-07 * scale,
                "activation_mM": 0.0012,
                "activation_n": 2,
                "inhibition_mM": 0.023,
                "inhibition_n": 2,
            },
        },
    }


def calcium_channel(patch, abundance):
    return {
        "membrane_id": patch,
        "species_id": "Ca",
        "kinetic_law": "cav12_m2h",
        "max_permeability_m_per_s": 2.4e-06,
        "abundance": abundance,
        "initial_gate": {"m": 0.22, "h": 0.68},
    }


def blocks(channel_controls, *, transport, channels, ip3):
    """The blocks of a world, with the pieces that these say."""
    inner = ionic(channel_controls)
    cells = inner["cells"]
    stores = {c: store(cells[c], scale, ip3=ip3) for c, scale in (("c_a", 1.0), ("c_b", 1.3))}
    out = {"ionic": inner, "stores": stores}
    if transport:
        out["plasma_transport"] = {
            m: {
                "pump": calcium_pump(0.0021 * scale),
                "exchanger": {
                    "law": "exchanger_3na_1ca",
                    "capacity_fmol_per_s": 0.0019 * scale,
                    "km_na_mM": 19.0,
                    "km_ca_mM": 0.0011,
                },
            }
            for m, scale in (("m_a", 1.0), ("m_b", 1.3))
        }
    if channels:
        out["calcium_channels"] = {
            "ca_a": calcium_channel("m_a", 0.5),
            "ca_b": calcium_channel("m_b", 0.4),
        }
    if ip3:
        out["ip3_release"] = {
            c: {
                "species_id": "IP3",
                "law": "hill_product_factor",
                "activation_mM": 0.00014,
                "activation_n": 2,
            }
            for c in stores
        }
    out["calcium_controls"] = controls(out)
    return out


def controls(out):
    """Every schedule of the calcium pieces: 1 throughout."""
    stores, membranes = out["stores"], out["ionic"]["membranes"]
    made = {
        "store_passive": {c: {"Ca": ONES, "K": ONES} for c in stores},
        "store_pump": {c: ONES for c in stores},
        "store_release": {c: ONES for c in stores},
        "reactions": {c: {r: ONES for r in s["reactions"]} for c, s in stores.items()},
    }
    if "plasma_transport" in out:
        made |= {"calcium_pump": {m: ONES for m in membranes}}
        made |= {"exchanger": {m: ONES for m in membranes}}
    if "calcium_channels" in out:
        made["calcium_channel"] = {c: ONES for c in out["calcium_channels"]}
    return copy.deepcopy(made)


def world(consumer, entry, **more):
    return {
        "consumer": consumer,
        **entry,
        **more,
        "scales": {},
        "p": 2,
        "amount_refs": {},
        "closure_share": 1e-10,
        "closure_terms_V": {},
    }


BOTH = {"k_a": ONES, "k_b": ONES}
SMALL, WHOLE, PAIR = "inv_sample_store", "inv_sample_whole", "inv_sample_store_pair"


def invented():
    """The invented inputs of Part 2: the first child's form and the last one's, a cluster of the
    last one, a restart and the two plants."""
    history = {
        "fine": {"first_s": 0.0, "last_s": 4e-05, "spacing_s": 2e-05},
        "coarse": {"first_s": 8e-05, "last_s": END_S, "spacing_s": 4e-05},
    }
    times = {"history_times": history, "potential_times_s": [0.0, 4e-05, 0.00012, END_S]}
    whole = blocks(BOTH, transport=True, channels=True, ip3=True)
    worlds = {
        SMALL: world(
            "spatial_calcium", blocks(BOTH, transport=False, channels=False, ip3=False), **times
        ),
        WHOLE: world("ip3_calcium", whole, **times),
        PAIR: world(
            "cluster_gated_calcium",
            {"same_as": WHOLE, "controls_channel": sample.PATH},
            final_s=END_S,
            summary_times_s=[8e-05, END_S],
            pools={
                "c_a": sample.pool("k_a", 0, [811, 812]) | {"pool": pool()},
                "c_b": sample.pool("k_b", 1, [821, 822]) | {"pool": pool()},
            },
            coupling={"law": "assembly_observable", "active": 1.0, "inactive": 0.0},
        ),
    }
    coarse, fine = 2e-05, 1e-05
    run = sample.run
    runs = [
        run(f"{SMALL} h={coarse!r}", "spatial_calcium", SMALL, SMALL, step=coarse),
        run(f"{WHOLE} h={coarse!r}", "ip3_calcium", WHOLE, WHOLE, step=coarse),
        run(f"{WHOLE} h={fine!r}", "ip3_calcium", WHOLE, WHOLE, step=fine),
        run(
            f"{WHOLE} h={coarse!r} restart",
            "ip3_calcium",
            None,
            WHOLE,
            step=coarse,
            role="support",
            variant="restart at 0.00012",
        ),
        run(f"{WHOLE} plant release", "ip3_calcium", WHOLE, WHOLE, step=fine, role="plant")
        | {"variant": "EP3"},
        run(f"{PAIR} s1 pool", "cluster_gated_calcium", None, PAIR, seed=1, variant="pool"),
        run(
            f"{PAIR} s1 w0 h={coarse!r}",
            "cluster_gated_calcium",
            f"{PAIR} s1 w0",
            PAIR,
            seed=1,
            at=0,
            step=coarse,
            variant="ionic",
        ),
        run(
            f"{PAIR} plant swapped",
            "cluster_gated_calcium",
            f"{PAIR} s1 w0",
            PAIR,
            seed=1,
            at=0,
            step=coarse,
            role="plant",
        )
        | {"variant": "EP4"},
    ]
    return {"schema": SCHEMA, "part": 2, "constants": {}, "worlds": worlds, "runs": runs}


def pool():
    return sample.pool("k", 0, [])["pool"] | {"worlds": 2}
