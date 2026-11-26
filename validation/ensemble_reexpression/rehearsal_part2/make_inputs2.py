"""Part 2's invented worlds: inputs_rehearsal_part2.json and the legacy definitions.

PART2.md section 15. Every number here is invented: `exclusions2.py` checks mechanically that none
of either part's declared numbers is among them, with the exceptions that it lists. A world's
numbers are drawn once, by a seeded generator about a round centre, and rounded to a few digits; the
file holds them. A world is written once, in `WORLDS`, and gives
- its blocks in inputs_part2.json's form (PART2_BLOCKS.md) with `scales`, `amount_refs`,
  `closure_share`, `closure_terms_V`, `closure_terms` and `p` by rules2.py, and
- the legacy definitions at h, h/2 and h/4 in the captured form, for the frozen snapshot.

    make_inputs2.py write              inputs_rehearsal_part2.json, beside this file
    make_inputs2.py origin DIR SNAPSHOT [WORLD ...]   the legacy definitions, the job list that
                                       validation/legacy_port's capture.sh reads and the origin's
                                       manifest, in a new folder (of every world, or of the named)
"""

import hashlib
import json
import math
import random
import sys
from datetime import UTC, datetime
from fractions import Fraction
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "rehearsal"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import make_inputs as part1  # noqa: E402
import rules  # noqa: E402
import rules2  # noqa: E402

HERE = rules2.HERE
SPECIES = {"Na": 1, "K": 1, "Cl": -1, "Ca": 2}
CHEMICAL = {"Ca": 2, "B": -2, "CaB": 0, "Ca2B": 2, "K": 1, "Na": 1, "Cl": -1}
IP3_ROWS = {"IP3": -3, "IP3_buffer": 0, "IP3_bound": -3}
KINDS = ("spatial", "plasma", "gated", "ip3")
ON = [[0.0, 1.0]]


# ------------------------------------------------------------------ the invented numbers


def digits(x, n):
    """x rounded to n significant digits."""
    return float(f"{x:.{n - 1}e}") if x else 0.0


class Draw:
    """Numbers near a centre, by a seeded generator, each rounded to a few digits."""

    def __init__(self, seed):
        self.random = random.Random(seed)

    def __call__(self, centre, spread=0.09, n=4):
        return digits(centre * self.random.uniform(1 - spread, 1 + spread), n)


def fixed(amounts, charge_C, decimals):
    """The fixed charge that closes a compartment's own charge, rounded to `decimals` decimals (Part
    1's, with Ca)."""
    need = Fraction(charge_C) / Fraction(rules.F * rules.FMOL) - sum(
        (Fraction(SPECIES[x]) * Fraction(n) for x, n in amounts.items()), Fraction(0)
    )
    return float(f"{float(need):.{decimals}f}")


# A cell's and its store's centres (concentrations in mM, the cell's volume in pL). The store's K
# is the cytosol's to seven digits, so calcium's currents make the store's voltage, as a K leak
# holds it.
CELLS = {
    "cell_0": dict(volume=0.63, Na=11.9, K=136.2, Cl=8.35, Ca=0.0022, voltage=-0.0535,
                   area=3.25e-10),
    "cell_1": dict(volume=0.86, Na=14.6, K=131.0, Cl=9.75, Ca=0.0024, voltage=-0.0375,
                   area=4.15e-10),
}  # fmt: skip
REGIONS = {
    "bath": dict(volume=2.35, Na=142.0, K=4.45, Cl=114.5, Ca=0.0092),
    "cleft": dict(volume=1.17, Na=124.0, K=7.35, Cl=107.0, Ca=0.0107),
    "rim": dict(volume=3.45, Na=134.0, K=3.15, Cl=109.0, Ca=0.0069),
}


def calcium(seed, kind, *, one=False, **f):
    """One invented world of a kind. `f` scales the centres of its parts (1 each unless given):
    leak, pump, channel, junction, gate, face, store_K, store_Ca, store_pump, release, binding,
    capacitor (the store's specific capacitance), volume (all), er_K (the store's K over the
    cytosol's), g0 (the junction's initial gate), cav, plasma, ip3."""
    d = Draw(seed)

    def x(name):
        return f.get(name, 1.0)

    cells = {c: v for c, v in CELLS.items() if not (one and c == "cell_1")}
    out = dict(kind=kind, seed=seed, one=one, cells={}, outside={}, stores={})
    specific = d(0.0114)
    fuel = dict(atp=d(1.64), adp=d(0.125), pi=d(0.138), dg0=d(-36400.0, 0.02, 5))
    for c, v in cells.items():
        volume = digits(d(v["volume"]) * x("volume"), 4)
        amounts = {k: digits(d(v[k], 0.05) * volume, 4) for k in ("Na", "K", "Cl")}
        amounts["Ca"] = digits(d(v["Ca"]) * volume, 4)
        area = d(v["area"])
        cap = rules.capacitance(area, specific)
        voltage = d(v["voltage"], 0.06)
        out["cells"][c] = dict(
            volume=volume, amounts=amounts, voltage=voltage, area=area, specific=specific, cap=cap,
            charge=rules.charge(cap, voltage),
        )  # fmt: skip
    for o, v in REGIONS.items():
        volume = digits(d(v["volume"]) * x("volume") * x("outside"), 4)
        amounts = {k: digits(d(v[k], 0.006) * volume, 4) for k in ("Na", "K", "Cl")}
        amounts["Ca"] = digits(d(v["Ca"], 0.05) * volume, 4)
        out["outside"][o] = dict(
            volume=volume, amounts=amounts, faces=tuple(cells) if o == "bath" else ()
        )
    out["leaks"] = {
        c: dict(
            Na=digits(d(1.25e-11) * x("leak"), 4), K=digits(d(2.45e-10) * x("leak"), 4),
            Cl=digits(d(9.1e-11) * x("leak"), 4), Ca=digits(d(6.1e-08) * x("leak"), 4),
        )
        for c in cells
    }  # fmt: skip
    constants = dict(km_na=d(11.4), km_k=d(0.245), km_atp=d(0.455))
    out["pumps"] = {
        c: dict(capacity=digits(d(0.058 if c == "cell_0" else 0.091) * x("pump"), 4), **constants,
                **fuel)
        for c in cells
    }  # fmt: skip
    m, h = d(0.245), d(0.655)
    out["channels"] = {}
    if x("channel"):
        out["channels"] = {
            c: dict(p_max=digits(d(2.85e-10) * x("channel"), 4), abundance=d(0.56), m=m, h=h)
            for c in cells
        }
    out["junctions"] = {}
    if not one:
        out["junctions"]["gap"] = dict(
            a="cell_0", b="cell_1", area=d(1.17e-10),
            perm=dict(
                Na=digits(d(2.75e-10) * x("junction"), 4), K=digits(d(4.45e-10) * x("junction"), 4),
                Cl=digits(d(3.65e-10) * x("junction"), 4), Ca=digits(d(2.3e-08) * x("junction"), 4),
            ),
            thr=d(0.0137), lo=d(0.115), g0=f.get("g0") or d(0.575),
        )  # fmt: skip
    diffusion = dict(Na=d(1.31e-09), K=d(1.87e-09), Cl=d(2.12e-09), Ca=d(7.7e-10))
    area, length = digits(d(1.29e-11) * x("face"), 4), d(2.25e-05)
    out["faces"] = {
        k: dict(a=a, b=b, area=area, length=length, diff=dict(diffusion))
        for k, a, b in (
            ("face_0", "bath", "cleft"), ("face_1", "cleft", "rim"), ("face_2", "rim", "bath"),
        )
    }  # fmt: skip
    # The stores.
    mu = dict(CaB=d(-6.6, 0.06, 5), Ca2B=d(-11.2, 0.05, 5), IP3_bound=d(-9.05, 0.04, 5))
    k = dict(
        bind_0_first=d(1180.0), bind_0_second=d(124.0), bind_1_first=d(1260.0),
        bind_1_second=d(131.0), ip3_binding=d(18600.0),
    )  # fmt: skip
    release = dict(
        activation=d(0.00115), activation_n=4, inhibition=d(0.0225), inhibition_n=3,
        specific=digits(d(0.0109) * x("capacitor"), 4),
    )  # fmt: skip
    store_pump = dict(km_ca=d(0.00118), km_atp=constants["km_atp"])
    for c, v in cells.items():
        cy = out["cells"][c]
        volume = digits(cy["volume"] * d(0.104, 0.08), 4)
        cytosol = {
            "B": digits(d(0.0485) * cy["volume"], 4), "CaB": digits(d(0.0097) * cy["volume"], 4),
            "Ca2B": digits(d(0.00098) * cy["volume"], 4),
        }  # fmt: skip
        ratio = x("er_K")
        er = {
            "Ca": digits(d(0.196) * volume, 4), "B": digits(d(0.0485) * volume, 4),
            "CaB": digits(d(0.0103) * volume, 4), "Ca2B": digits(d(0.00102) * volume, 4),
            "K": digits(cy["amounts"]["K"] / cy["volume"] * ratio * volume, 7),
            "Na": digits(d(11.7) * volume, 4), "Cl": digits(d(8.1) * volume, 4),
        }  # fmt: skip
        if kind == "ip3":
            cytosol |= {
                "IP3": digits(d(1.15e-04) * cy["volume"], 4),
                "IP3_buffer": digits(d(0.00108) * cy["volume"], 4),
                "IP3_bound": digits(d(2.2e-04) * cy["volume"], 4),
            }
            er |= {
                "IP3": digits(d(4.3e-05) * volume, 4), "IP3_buffer": digits(d(0.00107) * volume, 4),
                "IP3_bound": digits(d(2.1e-04) * volume, 4),
            }  # fmt: skip
        out["stores"][c] = dict(
            volume=volume, cytosol=cytosol, er=er, area=d(1.12e-09 if c == "cell_0" else 1.46e-09),
            perm=dict(
                Ca=digits(d(1.14e-08) * x("store_Ca"), 4), K=digits(d(9.3e-08) * x("store_K"), 4)
            ),
            mu=mu, rates={r: digits(v * x("binding"), 4) for r, v in k.items()},
            pump=dict(
                capacity=digits(d(0.0034 if c == "cell_0" else 0.0046) * x("store_pump"), 4),
                **store_pump, **fuel,
            ),
            release=dict(p=digits(d(1.13e-07) * x("release"), 4), **release),
        )  # fmt: skip
    if kind != "spatial":
        pmca, ncx = dict(km_ca=d(0.00113), km_atp=d(0.465)), dict(km_na=d(19.2), km_ca=d(0.00116))
        out["plasma"] = {
            c: dict(
                pump=dict(
                    capacity=digits(d(0.00215 if c == "cell_0" else 0.00305) * x("plasma"), 4),
                    **pmca, **fuel,
                ),
                exchanger=dict(
                    capacity=digits(d(0.00225 if c == "cell_0" else 0.00295) * x("plasma"), 4),
                    **ncx,
                ),
            )
            for c in cells
        }  # fmt: skip
    if kind in ("gated", "ip3"):
        m, h = d(0.185), d(0.735)
        out["cav"] = {
            c: dict(p_max=digits(d(2.15e-06) * x("cav"), 4), abundance=d(0.54), m=m, h=h)
            for c in cells
        }
    if kind == "ip3":
        out["ip3"] = dict(activation=d(1.63e-04), n=1)
    return out


def timed(world, consumer, *, end, candidate, fine_last, coarse_first, coarse, potentials,
          legacy=None, off_grid=None, **extra):  # fmt: skip
    """The world's clock: its horizon, its three steps (the retry's is half the last), its compared
    times, and the legacy's step where it is not the first."""
    return dict(
        world, consumer=consumer, end=end, candidate=candidate, legacy=legacy or candidate[0],
        fine=(0.0, fine_last, candidate[0]), coarse=(coarse_first, end, coarse),
        potentials=potentials, off_grid=off_grid, p=2, **extra,
    )  # fmt: skip


SHARED = dict(
    end=0.01568, candidate=(1.6e-05, 8e-06, 4e-06), fine_last=0.00064, coarse_first=0.00072,
    coarse=8e-05, potentials=(0.0, 0.00192, 0.00384, 0.00624, 0.00816, 0.01152, 0.01568),
    off_grid=5.3e-05,
)  # fmt: skip


def fuel_potentials(world, adp, pi):
    """Three potentials of the fuel rows (over RT, at 1 mM) that give the world's pumps their
    standard free energy at 1 M, with ADP's and Pi's chosen (2.2): they are large against it."""
    g = one_molar(next(iter(world["pumps"].values()))["dg0"])
    return dict(ATP=adp + pi + math.log(1000) - g / (rules.R * 298.15), ADP=adp, Pi=pi)


def worlds():
    out = {
        "inv_spatial": timed(calcium(2101, "spatial", junction=1.01), "spatial_calcium", **SHARED),
        "inv_plasma": timed(
            calcium(2122, "plasma", capacitor=6.0, plasma=1.01), "plasma_calcium", **SHARED
        ),
        "inv_gated": timed(calcium(2103, "gated", junction=1.01), "gated_calcium", **SHARED),
        "inv_ip3": timed(calcium(2147, "ip3"), "ip3_calcium", **SHARED),
        # One cell with one store, no junction, at steps where the order is resolved.
        "inv_single": timed(
            calcium(2105, "spatial", one=True),
            "spatial_calcium",
            end=0.01248,
            candidate=(4.8e-05, 2.4e-05, 1.2e-05),
            fine_last=0.00096,
            coarse_first=0.0012,
            coarse=0.00024,
            potentials=(0.0, 0.00144, 0.00288, 0.00528, 0.00768, 0.0096, 0.01248),
            off_grid=6.1e-05,
        ),
        # Amounts as large against s as the registered ones, and fixed charges off the rule.
        "inv_amounts": timed(
            calcium(
                2106,
                "spatial",
                leak=0.42,
                pump=0.4,
                channel=0.4,
                junction=0.35,
                face=0.3,
                store_K=0.3,
                store_Ca=0.4,
                store_pump=0.4,
                release=0.4,
                binding=0.35,
                volume=1.3,
            ),
            "spatial_calcium",
            end=0.0122,
            candidate=(2e-05, 1e-05, 5e-06),
            fine_last=0.0008,
            coarse_first=0.0012,
            coarse=0.0002,
            potentials=(0.0, 0.00218, 0.00406, 0.00612, 0.00816, 0.0104, 0.0122),
            off_grid=6.7e-05,
            off=True,
        ),
        # A family at rounding: slow routes, a store that holds its charge, small steps.
        "inv_slow": timed(
            calcium(
                2107,
                "plasma",
                leak=0.1,
                pump=0.1,
                channel=0.1,
                junction=0.102,
                face=0.1,
                store_K=2e-4,
                store_Ca=0.1,
                store_pump=0.1,
                release=0.1,
                binding=0.1,
                plasma=0.1,
            ),
            "plasma_calcium",
            end=0.001248,
            candidate=(1.2e-06, 6e-07, 3e-07),
            fine_last=4.8e-05,
            coarse_first=6e-05,
            coarse=1.2e-05,
            potentials=(0.0, 0.000216, 0.000408, 0.000624, 0.000816, 0.001032, 0.001248),
        ),
        # Little calcium crosses the store, so its voltage is small against its scale.
        "inv_thin": timed(
            calcium(2108, "plasma", junction=1.01, store_Ca=0.002, store_pump=0.002, release=0.002),
            "plasma_calcium",
            end=0.0105,
            candidate=(1.4e-05, 7e-06, 3.5e-06),
            fine_last=0.00056,
            coarse_first=0.0007,
            coarse=0.00014,
            potentials=(0.0, 0.00168, 0.00322, 0.00532, 0.0077, 0.0091, 0.0105),
        ),
        # The store's capacitor is big, so its voltage is far from quasi-steady.
        "inv_capacitor": timed(
            calcium(2109, "plasma", capacitor=48.0),
            "plasma_calcium",
            end=0.0102,
            candidate=(1.5e-05, 7.5e-06, 3.75e-06),
            fine_last=0.0006,
            coarse_first=0.00075,
            coarse=0.00015,
            potentials=(0.0, 0.00165, 0.00315, 0.00525, 0.00765, 0.00915, 0.0102),
        ),
        # The pumps' fuel potentials are large against their difference (section 2.4).
        "inv_fuel": timed(
            calcium(2110, "gated", one=True),
            "gated_calcium",
            end=0.0108,
            candidate=(1.8e-05, 9e-06, 4.5e-06),
            fine_last=0.00072,
            coarse_first=0.0009,
            coarse=0.00018,
            potentials=(0.0, 0.00162, 0.00324, 0.0054, 0.00774, 0.00936, 0.0108),
        ),
        # The stop: a store far from equilibrium behind a fast K leak, at a coarse step.
        "inv_stop": timed(
            calcium(
                2111,
                "gated",
                one=True,
                leak=0.1,
                pump=0.1,
                channel=0.1,
                face=0.02,
                plasma=0.1,
                cav=0.1,
                store_K=1.4,
                er_K=2.3,
            ),
            "gated_calcium",
            end=0.00464,
            candidate=(4e-05,),
            legacy=4e-06,
            fine_last=0.0008,
            coarse_first=0.00088,
            coarse=8e-05,
            potentials=(0.0, 0.00136, 0.00264, 0.00464),
        ),
    }
    out["inv_fuel"]["fuel"] = fuel_potentials(out["inv_fuel"], 731.25, 612.5)
    return out


# ------------------------------------------------------------------ the blocks (PART2_BLOCKS.md)


def names(world):
    """(membrane of a cell, channel of a cell): `membrane_0`, `channel_0` for the first cell, on."""
    cells = list(world["cells"])
    return (
        {c: f"membrane_{i}" for i, c in enumerate(cells)},
        {c: f"channel_{i}" for i, c in enumerate(cells) if c in world["channels"]},
    )


def cav_names(world):
    return {c: f"calcium_channel_{i}" for i, c in enumerate(world["cells"])}


def region_charge(world, name):
    faced = [world["cells"][c]["charge"] for c in world["outside"][name]["faces"]]
    return rules.countercharge(faced) if faced else 0.0


OFF = (1.0e-24, 5.1e-24)  # The captured worlds' fixed charges are off the rule by up to 5.1e-24 C.


def off_rule(amounts, charge_C):
    """A fixed charge off the electroneutral rule in the captured style (Part 1's, with Ca)."""
    for decimals in (14, 13, 12):
        value = fixed(amounts, charge_C, decimals)
        for k in (0, 1, -1, 2, -2, 3, -3):
            candidate = float(f"{value + k * 10.0**-decimals:.{decimals}f}")
            residual = rules.charge_residual_C(SPECIES, amounts, candidate, charge_C)
            if OFF[0] <= abs(residual) <= OFF[1]:
                return candidate
    raise ValueError("no decimal leaves the residual in the range")


def cell_fixed(world, c):
    v = world["cells"][c]
    return (off_rule if world.get("off") else lambda a, q: fixed(a, q, 13))(
        v["amounts"], v["charge"]
    )


def region_fixed(world, o):
    v, q = world["outside"][o], region_charge(world, o)
    if world.get("off"):
        return off_rule(v["amounts"], q)
    return fixed(v["amounts"], q, 13 if v["faces"] else 12)


def ionic_block(world):
    """The world's `ionic` block."""
    membrane, chan = names(world)
    cells, outside, membranes, channels, junctions, faces = {}, {}, {}, {}, {}, {}
    for c, v in world["cells"].items():
        cells[c] = dict(
            volume_pL=v["volume"],
            initial_amount_fmol=dict(v["amounts"]),
            fixed_charge_equivalent_fmol=cell_fixed(world, c),
            initial_voltage_V=v["voltage"],
            initial_charge_C=v["charge"],
        )
    for o, v in world["outside"].items():
        outside[o] = dict(
            volume_pL=v["volume"],
            initial_amount_fmol=dict(v["amounts"]),
            fixed_charge_equivalent_fmol=region_fixed(world, o),
            initial_charge_C=region_charge(world, o),
        )
    faced = {c: o for o, v in world["outside"].items() for c in v["faces"]}
    for c, v in world["cells"].items():
        p = world["pumps"][c]
        membranes[membrane[c]] = dict(
            inside=c,
            outside=faced[c],
            area_m2=v["area"],
            capacitance_F=v["cap"],
            passive=dict(law="constant_field", permeability_m_per_s=dict(world["leaks"][c])),
            pump=dict(
                law="nak_pump_positive",
                roles={"sodium": "Na", "potassium": "K"},
                stoichiometry={"Na": -3, "K": 2},
                capacity_fmol_per_s=p["capacity"],
                km_na_mM=p["km_na"],
                km_k_mM=p["km_k"],
                km_atp_mM=p["km_atp"],
                metabolism=dict(
                    kind="maintained_fuel",
                    atp_mM=p["atp"],
                    adp_mM=p["adp"],
                    pi_mM=p["pi"],
                    delta_g0_J_per_mol=p["dg0"],
                ),
            ),
        )
        if c in chan:
            k = world["channels"][c]
            channels[chan[c]] = dict(
                membrane_id=membrane[c],
                species_id="K",
                kinetic_law="kv15_mh",
                max_permeability_m_per_s=k["p_max"],
                abundance=k["abundance"],
                initial_gate={"m": k["m"], "h": k["h"]},
            )
    for j, v in world["junctions"].items():
        junctions[j] = dict(
            from_cell=v["a"],
            to_cell=v["b"],
            area_m2=v["area"],
            permeability_m_per_s=dict(v["perm"]),
            gate=dict(
                initial_gate=v["g0"],
                law="junction_relaxation",
                minimum_open_fraction=v["lo"],
                threshold_voltage_V=v["thr"],
            ),
        )
    for k, v in world["faces"].items():
        faces[k] = dict(
            sender=v["a"],
            receiver=v["b"],
            area_m2=v["area"],
            length_m=v["length"],
            diffusivity_m2_per_s=dict(v["diff"]),
            law="logmean_face",
        )
    return dict(
        temperature_K=298.15,
        species=dict(SPECIES),
        cells=cells,
        outside=outside,
        closure=dict(gauge_reference="bath"),
        membranes=membranes,
        channels=channels or [],
        junctions=junctions or [],
        faces=faces,
        controls=dict(
            leak={m: [list(p) for p in ON] for m in membranes},
            pump={m: [list(p) for p in ON] for m in membranes},
            channel={c: [list(p) for p in ON] for c in channels} or [],
            junction={j: [list(p) for p in ON] for j in junctions} or [],
        ),
        material_tolerance_fmol={"Cl": 3.1e-11, "K": 3.1e-11, "Na": 3.1e-11, "Ca": 9.2e-11},
        end_s=world["end"],
    )


def one_molar(dg0):
    """The pumps' standard free energy at 1 M, from the one for the numeric-mM quotient (2.2)."""
    return dg0 + rules.R * 298.15 * math.log(1000)


WORLDS = worlds()


def rows(world):
    return dict(CHEMICAL) | (IP3_ROWS if world["kind"] == "ip3" else {})


def reactions(world):
    """{reaction: (compartment, reactants, products)}, the captured ones' IDs."""
    out = {}
    for i, part in enumerate(("cytosol", "er")):
        out[f"bind_{i}_first"] = (part, {"Ca": 1, "B": 1}, {"CaB": 1})
        out[f"bind_{i}_second"] = (part, {"Ca": 1, "CaB": 1}, {"Ca2B": 1})
    if world["kind"] == "ip3":
        out["ip3_binding"] = ("cytosol", {"IP3": 1, "IP3_buffer": 1}, {"IP3_bound": 1})
    return out


def amounts_of(world, c, part):
    """A compartment's rows in the order of the species table."""
    cy, s = world["cells"][c], world["stores"][c]
    values = (cy["amounts"] | s["cytosol"]) if part == "cytosol" else s["er"]
    return {x: values[x] for x in rows(world)}


def calcium_pump(p):
    return dict(
        law="calcium_pump_positive",
        capacity_fmol_per_s=p["capacity"],
        km_ca_mM=p["km_ca"],
        km_atp_mM=p["km_atp"],
        atp_mM=p["atp"],
        adp_mM=p["adp"],
        pi_mM=p["pi"],
        delta_g0_at_1M_J_per_mol=one_molar(p["dg0"]),
    )


def stores_block(world):
    out = {}
    for c, s in world["stores"].items():
        cap = rules.capacitance(s["area"], s["release"]["specific"])
        out[c] = dict(
            law="mass_action_passive",
            temperature_K=298.15,
            standard_concentration_mM=1.0,
            species={
                x: dict(valence=z, standard_mu_RT=s["mu"].get(x, 0.0))
                for x, z in rows(world).items()
            },
            compartments=dict(
                cytosol=dict(
                    volume_pL=world["cells"][c]["volume"],
                    initial_amount_fmol=amounts_of(world, c, "cytosol"),
                ),
                er=dict(volume_pL=s["volume"], initial_amount_fmol=amounts_of(world, c, "er")),
            ),
            reactions={
                r: dict(
                    compartment=part,
                    reactants=a,
                    products=b,
                    forward_rate_per_s=s["rates"][r],
                )
                for r, (part, a, b) in reactions(world).items()
            },
            membrane=dict(
                cytosol="cytosol",
                er="er",
                area_m2=s["area"],
                capacitance_F=cap,
                initial_voltage_V=0.0,
                initial_charge_C=0.0,
                permeability_m_per_s={x: s["perm"].get(x, 0.0) for x in rows(world)},
                pump=calcium_pump(s["pump"]),
                release=dict(
                    law="hill_product_factor",
                    permeability_m_per_s=s["release"]["p"],
                    activation_mM=s["release"]["activation"],
                    activation_n=s["release"]["activation_n"],
                    inhibition_mM=s["release"]["inhibition"],
                    inhibition_n=s["release"]["inhibition_n"],
                ),
            ),
        )
    return out


def controls_block(world):
    """`calcium_controls`: every schedule is [[0, 1]]."""

    def on():
        return [list(p) for p in ON]

    membrane, _ = names(world)
    out = dict(
        store_passive={c: {"Ca": on(), "K": on()} for c in world["stores"]},
        store_pump={c: on() for c in world["stores"]},
        store_release={c: on() for c in world["stores"]},
        reactions={c: {r: on() for r in reactions(world)} for c in world["stores"]},
    )
    if "plasma" in world:
        out["calcium_pump"] = {membrane[c]: on() for c in world["plasma"]}
        out["exchanger"] = {membrane[c]: on() for c in world["plasma"]}
    if "cav" in world:
        out["calcium_channel"] = {v: on() for v in cav_names(world).values()}
    return out


def blocks(world):
    """The world's blocks, in inputs_part2.json's order."""
    membrane, _ = names(world)
    out = dict(ionic=ionic_block(world), stores=stores_block(world))
    if "plasma" in world:
        out["plasma_transport"] = {
            membrane[c]: dict(
                pump=calcium_pump(v["pump"]),
                exchanger=dict(
                    law="exchanger_3na_1ca",
                    capacity_fmol_per_s=v["exchanger"]["capacity"],
                    km_na_mM=v["exchanger"]["km_na"],
                    km_ca_mM=v["exchanger"]["km_ca"],
                ),
            )
            for c, v in world["plasma"].items()
        }
    if "cav" in world:
        out["calcium_channels"] = {
            cav_names(world)[c]: dict(
                membrane_id=membrane[c],
                species_id="Ca",
                kinetic_law="cav12_m2h",
                max_permeability_m_per_s=v["p_max"],
                abundance=v["abundance"],
                initial_gate={"m": v["m"], "h": v["h"]},
            )
            for c, v in world["cav"].items()
        }
    if "ip3" in world:
        out["ip3_release"] = {
            c: dict(
                species_id="IP3",
                law="hill_product_factor",
                activation_mM=world["ip3"]["activation"],
                activation_n=world["ip3"]["n"],
            )
            for c in world["cells"]
        }
    out["calcium_controls"] = controls_block(world)
    return out


# ------------------------------------------------------------------ the legacy definition


MOIETIES = ("B", "Ca", "Cl", "K", "Na")
MADE_OF = {
    "Ca": {"Ca": 1}, "B": {"B": 1}, "CaB": {"B": 1, "Ca": 1}, "Ca2B": {"B": 1, "Ca": 2},
    "K": {"K": 1}, "Na": {"Na": 1}, "Cl": {"Cl": 1}, "IP3": {"IP3": 1},
    "IP3_buffer": {"IP3_site": 1}, "IP3_bound": {"IP3": 1, "IP3_site": 1},
}  # fmt: skip


def legacy_pump(p, law):
    return dict(
        law=law,
        capacity_fmol_per_s=p["capacity"],
        km_ca_mM=p["km_ca"],
        km_atp_mM=p["km_atp"],
        metabolism="maintained_mM_quotient@1",
        atp_mM=p["atp"],
        adp_mM=p["adp"],
        pi_mM=p["pi"],
        delta_g0_J_per_mol=p["dg0"],
    )


def legacy_store(world, c):
    s = world["stores"][c]
    moieties = [*MOIETIES, *(("IP3", "IP3_site") if world["kind"] == "ip3" else ())]
    return dict(
        id="er_calcium@1",
        law="ideal_detailed_balance_mass_action@1",
        temperature_K=298.15,
        standard_concentration_mM=1.0,
        moieties=moieties,
        species=[
            dict(
                id=x,
                valence=z,
                moieties={m: MADE_OF[x].get(m, 0) for m in moieties},
                standard_mu_RT=s["mu"].get(x, 0.0),
            )
            for x, z in rows(world).items()
        ],
        compartments=[
            dict(
                id=part,
                volume_pL=world["cells"][c]["volume"] if part == "cytosol" else s["volume"],
                initial_amount_fmol=amounts_of(world, c, part),
            )
            for part in ("cytosol", "er")
        ],
        reactions=[
            dict(
                id=r,
                compartment=part,
                reactants=dict(a),
                products=dict(b),
                forward_rate_per_s=s["rates"][r],
            )
            for r, (part, a, b) in reactions(world).items()
        ],
        membrane=dict(
            id="er_membrane",
            cytosol="cytosol",
            er="er",
            calcium_species="Ca",
            area_m2=s["area"],
            specific_capacitance_F_per_m2=s["release"]["specific"],
            initial_voltage_V=0.0,
            permeability_m_per_s={x: s["perm"].get(x, 0.0) for x in rows(world)},
            pump=legacy_pump(s["pump"], "er_calcium_pump_positive@1"),
            release=dict(
                law="er_calcium_release@1",
                permeability_m_per_s=s["release"]["p"],
                activation_mM=s["release"]["activation"],
                activation_n=s["release"]["activation_n"],
                inhibition_mM=s["release"]["inhibition"],
                inhibition_n=s["release"]["inhibition_n"],
            ),
        ),
    )


MODEL_ID = {k: f"spatial_calcium@{i + 1}" for i, k in enumerate(KINDS)}


def legacy(world, step, *, observations):
    """The legacy definition at one step, in the captured form."""
    b = ionic_block(world)
    membrane, chan = names(world)
    cells = []
    for i, (c, v) in enumerate(world["cells"].items()):
        m = b["membranes"][membrane[c]]
        cells.append(
            dict(
                cell=dict(
                    id=c,
                    volume_pL=v["volume"],
                    initial_amount_fmol=dict(v["amounts"]),
                    initial_voltage_V=v["voltage"],
                    fixed_charge_equivalent_fmol=b["cells"][c]["fixed_charge_equivalent_fmol"],
                ),
                channel=None
                if c not in chan
                else dict(
                    id=chan[c],
                    membrane_id=membrane[c],
                    species_id="K",
                    kinetic_law="kv1p5_mh@1",
                    max_permeability_m_per_s=world["channels"][c]["p_max"],
                    abundance=world["channels"][c]["abundance"],
                    initial_gate={"m": world["channels"][c]["m"], "h": world["channels"][c]["h"]},
                ),
                membrane=dict(
                    id=membrane[c],
                    inside=c,
                    outside=m["outside"],
                    area_m2=v["area"],
                    specific_capacitance_F_per_m2=v["specific"],
                    passive=dict(
                        law="constant_field@1", permeability_m_per_s=dict(world["leaks"][c])
                    ),
                    pump=dict(
                        id=f"pump_{i}",
                        law="nak_atp_mass_action_positive@1",
                        roles=dict(m["pump"]["roles"]),
                        stoichiometry=dict(m["pump"]["stoichiometry"]),
                        capacity_fmol_per_s=m["pump"]["capacity_fmol_per_s"],
                        km_na_mM=m["pump"]["km_na_mM"],
                        km_k_mM=m["pump"]["km_k_mM"],
                        km_atp_mM=m["pump"]["km_atp_mM"],
                        metabolism=dict(
                            m["pump"]["metabolism"], kind="maintained_chemical_reservoirs@1"
                        ),
                    ),
                ),
            )
        )
    outside = {
        o: dict(
            id=o,
            volume_pL=v["volume_pL"],
            initial_amount_fmol=dict(v["initial_amount_fmol"]),
            fixed_charge_equivalent_fmol=v["fixed_charge_equivalent_fmol"],
        )
        for o, v in b["outside"].items()
    }
    ionic = dict(
        id="spatial_extracellular@2",
        species=[dict(id=x, valence=z) for x, z in SPECIES.items()],
        temperature_K=298.15,
        extracellular=outside["bath"],
        cells=cells,
        junctions=[
            dict(
                id=j,
                from_cell=v["a"],
                to_cell=v["b"],
                area_m2=v["area"],
                permeability_m_per_s=dict(v["perm"]),
                gate=dict(
                    law="junction_voltage_relaxation@1",
                    threshold_voltage_V=v["thr"],
                    minimum_open_fraction=v["lo"],
                    initial_gate=v["g0"],
                ),
            )
            for j, v in world["junctions"].items()
        ],
        surroundings=[outside[o] for o in outside if o != "bath"],
        faces=[
            dict(
                id=k,
                sender=v["a"],
                receiver=v["b"],
                area_m2=v["area"],
                length_m=v["length"],
                diffusivity_m2_per_s=dict(v["diff"]),
                law="logmean_electrodiffusion@1",
            )
            for k, v in world["faces"].items()
        ],
        closure=dict(law="capacitive_components_current_continuity@1", gauge_reference="bath"),
    )
    model = dict(
        id=MODEL_ID[world["kind"]],
        ionic=ionic,
        stores=[dict(cell_id=c, model=legacy_store(world, c)) for c in world["stores"]],
    )
    n = len(cells)
    experiment = dict(
        end_time=world["end"],
        observation_times=list(observations),
        membrane_controls=[
            dict(
                membrane_id=membrane[c],
                leak=[dict(time=0.0, multipliers={x: 1.0 for x in SPECIES})],
                pump=[dict(time=0.0, multiplier=1.0)],
            )
            for c in world["cells"]
        ],
        channel_controls=[
            dict(channel_id=chan[c], schedule=[dict(time=0.0, availability=1.0)]) for c in chan
        ],
        junction_controls=[
            dict(junction_id=j, schedule=[dict(time=0.0, open_fraction=1.0)])
            for j in world["junctions"]
        ],
        store_controls=[
            dict(
                cell_id=c,
                controls=[
                    dict(
                        time=0.0,
                        reactions={r: 1.0 for r in reactions(world)},
                        passive={x: 1.0 for x in rows(world)},
                        pump=1.0,
                        release=1.0,
                    )
                ],
            )
            for c in world["stores"]
        ],
    )
    if "plasma" in world:
        model["plasma_transport"] = dict(
            calcium_species="Ca",
            sodium_species="Na",
            membranes=[
                dict(
                    membrane_id=membrane[c],
                    pump=legacy_pump(v["pump"], "plasma_calcium_pump_positive@1"),
                    exchanger=dict(
                        law="ncx_3na_1ca_symmetric_barrier@1",
                        capacity_fmol_per_s=v["exchanger"]["capacity"],
                        km_na_mM=v["exchanger"]["km_na"],
                        km_ca_mM=v["exchanger"]["km_ca"],
                    ),
                )
                for c, v in world["plasma"].items()
            ],
        )
        experiment["plasma_controls"] = [
            dict(membrane_id=membrane[c], schedule=[dict(time=0.0, pump=1.0, exchanger=1.0)])
            for c in world["plasma"]
        ]
    if "cav" in world:
        model["calcium_channels"] = [
            dict(
                id=cav_names(world)[c],
                membrane_id=membrane[c],
                species_id="Ca",
                kinetic_law="cav1p2_m2h@1",
                max_permeability_m_per_s=v["p_max"],
                abundance=v["abundance"],
                initial_gate={"m": v["m"], "h": v["h"]},
            )
            for c, v in world["cav"].items()
        ]
        experiment["calcium_channel_controls"] = [
            dict(channel_id=v, schedule=[dict(time=0.0, availability=1.0)])
            for v in cav_names(world).values()
        ]
    if "ip3" in world:
        model["ip3_release"] = [
            dict(
                cell_id=c,
                species_id="IP3",
                law="ip3_er_release@1",
                activation_mM=world["ip3"]["activation"],
                activation_n=world["ip3"]["n"],
            )
            for c in world["cells"]
        ]
    return dict(
        schema_version=1,
        model=model,
        experiment=experiment,
        execution=dict(
            backend="cpu",
            precision="float64",
            solver="rk4",
            jit=True,
            dt=step,
            max_steps=20000,
            max_trace_bytes=2147483648,
            material_balance_atol_fmol=dict(b["material_tolerance_fmol"]),
            capacity=n + 1,
            membrane_capacity=n + 2,
            channel_capacity=n + 1,
            edge_capacity=2,
            extracellular_capacity=5,
            face_capacity=4,
            field_solver="gauged_dense_kirchhoff@1",
            chemical_capacity=3,
            reaction_capacity=6,
        ),
    )


# ------------------------------------------------------------------ the clusters and their pools


def ring(i):
    """A five-ring of the pool's graph: the outer nodes i, i + 1 and i + 2, and two inner ones."""
    return sorted([i, (i + 1) % 10, (i + 2) % 10, i + 10, (i + 2) % 10 + 10])


POOLS = {
    "cell_0": dict(
        stream=0,
        pool=part1.pool(ring(4), 47, 5.3e-15, 1.15e7, 1240.0, 272.0, 1.4, 2, SHARED["end"], 90000),
        seeds=(81230617, 81330617),
        root=5,
    ),
    "cell_1": dict(
        stream=1,
        pool=part1.pool(ring(6), 55, 4.8e-15, 1.25e7, 1120.0, 324.0, 1.8, 2, SHARED["end"], 90000),
        seeds=(81230618, 81330618),
        root=7,
    ),
}
SUMMARIES = (0.00192, 0.00384, 0.00816, 0.01152, 0.01568)
CLUSTERS = {
    f"inv_cluster_{k}": dict(
        consumer=f"cluster_{k}_calcium", child=f"inv_{k}", summaries=SUMMARIES, pools=POOLS
    )
    for k in KINDS
}
PATHS_UNDER = "inv_pools"  # The key of the four clusters' pools in reference_paths (the registered
# clusters' is `base`).
SEEDS, IDS = 2, 2  # Two seed indices (set A is 0, set B is 1) and the world IDs 0 and 1 of each.


def legacy_pool(cluster, c, seed):
    world = dict(pools=CLUSTERS[cluster]["pools"])
    return part1.legacy_pool(world, c, seed, cluster=True)


def legacy_assembly(cluster, step, seed_index):
    w = CLUSTERS[cluster]
    ionic = legacy(WORLDS[w["child"]], step, observations=(0.0, *w["summaries"]))
    return dict(
        model="assembly_regulated_cluster@1",
        pools=[
            dict(
                cell_id=c,
                stream_id=e["stream"],
                pool=legacy_pool(cluster, c, e["seeds"][seed_index]),
                coupling=dict(part1.COUPLING),
            )
            for c, e in w["pools"].items()
        ],
        ionic=ionic,
        window_ticks=32,
    )


# ------------------------------------------------------------------ the runs

RESTART = ("inv_ip3", 0.00768)
UNKNOWN = "inv_unknown_junction_law"  # A label of no law: an unknown label passes through as it is.
STOPPED = "inv_stop"


def run(name, world, *, family=None, seed=None, world_id=None, step=None, role="judged",
        variant=None, change=None):  # fmt: skip
    consumer = (WORLDS | CLUSTERS)[world]["consumer"]
    out = dict(
        name=name, consumer=consumer, family=family, world=world, seed_index=seed,
        world_id=world_id, step_s=step, role=role, variant=variant,
    )  # fmt: skip
    if change is not None:
        out["declared_change"] = change
    return out


def released(world, factor=1.01):
    """Both stores' release permeability times `factor`, as a declared change of the block."""
    return [
        {
            "path": ["stores", c, "membrane", "release", "permeability_m_per_s"],
            "value": s["release"]["p"] * factor,
        }
        for c, s in WORLDS[world]["stores"].items()
    ]


def refusals(world):
    """A refusal of each kind (TABLE section 4), each one run and no family."""
    w = WORLDS[world]
    h = w["candidate"][1]
    cold = [["ionic", "temperature_K"], *(["stores", c, "temperature_K"] for c in w["stores"])]
    fuel = digits(w["plasma"]["cell_0"]["pump"]["atp"] * 1.17, 3)
    changes = dict(
        definition=[{"path": ["ionic", "junctions", "gap", "gate", "law"], "value": UNKNOWN}],
        domain=[{"path": p, "value": 151.0} for p in cold],
        harness=[{"path": ["plasma_transport", "membrane_0", "pump", "atp_mM"], "value": fuel}],
    )
    return [
        run(f"{world} refused {kind}", world, step=h, variant=f"refused {kind}", change=change)
        for kind, change in changes.items()
    ]


def runs():
    out = []
    for w, world in WORLDS.items():
        single = len(world["candidate"]) == 1
        for h in world["candidate"]:
            out.append(run(f"{w} h={h!r}", w, family=None if single else w, step=h))
    w, at = RESTART
    h1, _, h3 = WORLDS[w]["candidate"]
    out.append(
        run(f"{w} h={h1!r} restart", w, step=h1, role="support", variant=f"restart at {at!r}")
    )
    for variant, name, change in (
        ("inv_EP3", f"{w} plant release", released(w)),
        ("EP3", f"{w} plant release by variant", None),
    ):
        out.append(run(name, w, family=w, step=h3, role="plant", variant=variant, change=change))
    out += refusals("inv_plasma")
    for w, cluster in CLUSTERS.items():
        for s in range(SEEDS):
            out.append(run(f"{w} s{s} pool", w, seed=s, variant="pool"))
        for s in range(SEEDS):
            for k in range(IDS):
                for h in WORLDS[cluster["child"]]["candidate"]:
                    out.append(
                        run(f"{w} s{s} w{k} h={h!r}", w, family=f"{w} s{s} w{k}", seed=s,
                            world_id=k, step=h, variant="ionic")
                    )  # fmt: skip
    w = "inv_cluster_gated"
    h3 = WORLDS[CLUSTERS[w]["child"]]["candidate"][2]
    for variant, name, change in (
        ("inv_EP4", f"{w} plant swapped", [{"exchange_channels": ["cell_0", "cell_1"]}]),
        ("EP4", f"{w} plant swapped by variant", None),
    ):
        out.append(
            run(name, w, family=f"{w} s1 w0", seed=1, world_id=0, step=h3, role="plant",
                variant=variant, change=change)
        )  # fmt: skip
    return out


# ------------------------------------------------------------------ the inputs file


def retry_step(world):
    return WORLDS[world]["candidate"][-1] / 2


def drift():
    """`closure_terms_V`: one number over all the children of the file (PART2.md section 8)."""
    return rules2.drift_of(
        {w: blocks(v) for w, v in WORLDS.items()}, {w: retry_step(w) for w in WORLDS}
    )


def derived(name, b, drift_V):
    world = rules2.World(b)
    scales = world.scales()
    sums, *_ = world.closure_sums(retry_step(name), drift_V)
    return dict(
        scales=scales,
        amount_refs=world.amount_refs(scales),
        closure_share=rules2.SHARE,
        closure_terms_V=dict(drift_V),
        closure_terms=rules2.terms(sums, scales),
    )


SUMMARY = ("channel_K", "cyt_Na", "cyt_K", "cyt_Cl", "cyt_Ca")


def cluster_derived(child):
    """A cluster's are its child's, without `phi_out`; a `_summary` entry takes its readout's."""
    out = {}
    for part in ("scales", "amount_refs", "closure_terms_V", "closure_terms"):
        block = {k: v for k, v in child[part].items() if k != "phi_out"}
        block |= {f"{k}_summary": child[part][k] for k in SUMMARY if k in child[part]}
        out[part] = block
    return out


def inputs():
    drift_V, worlds = drift(), {}
    for name, w in WORLDS.items():
        b = blocks(w)
        out = dict(consumer=w["consumer"], **b)
        (f0, f1, fs), (c0, c1, cs) = w["fine"], w["coarse"]
        out["history_times"] = dict(
            fine=dict(first_s=f0, last_s=f1, spacing_s=fs),
            coarse=dict(first_s=c0, last_s=c1, spacing_s=cs),
        )
        out["potential_times_s"] = list(w["potentials"])
        out["p"] = w["p"]
        if "fuel" in w:
            out["fuel_standard_mu_RT"] = dict(w["fuel"])
        out.update(derived(name, b, drift_V))
        worlds[name] = out
    for name, w in CLUSTERS.items():
        child = worlds[w["child"]]
        worlds[name] = dict(
            consumer=w["consumer"],
            same_as=w["child"],
            controls_channel="the pool's path (SPEC.md section 3.2)",
            final_s=child["ionic"]["end_s"],
            summary_times_s=list(w["summaries"]),
            pools={
                c: dict(
                    channel=f"channel_{i}",
                    stream_id=e["stream"],
                    pool=part1.pool_block(dict(pools=w["pools"]), c),
                    harness=dict(part1.HARNESS),
                    seeds=list(e["seeds"]),
                )
                for i, (c, e) in enumerate(w["pools"].items())
            },
            coupling=dict(law="assembly_observable", active=1.0, inactive=0.0),
            p=child["p"],
            closure_share=rules2.SHARE,
            **cluster_derived(child),
        )
    return dict(
        schema="ensemble-reexpression inputs, version 1",
        part=2,
        constants=dict(F_C_per_mol=rules.F, R_J_per_mol_K=rules.R, fmol_to_mol=rules.FMOL),
        worlds=worlds,
        runs=runs(),
    )


# ------------------------------------------------------------------ the legacy origin

REDUCTION = {"h": 1, "h2": 2, "h4": 4}


def observations(world):
    out = [0.0, *[t for t in world["potentials"] if t]]
    if world.get("off_grid"):
        out.append(world["off_grid"])
    return sorted(out)


def definition(name, step):
    w = WORLDS[name]
    return legacy(w, w["legacy"] / REDUCTION[step], observations=observations(w))


def jobs(only=None):
    """The job list of capture.sh, as capture_worlds.py writes one."""
    out = []
    for w, world in WORLDS.items():
        if only and w not in only:
            continue
        for step, k in REDUCTION.items():
            steps = rules.grid_steps(world["end"], world["legacy"] / k)
            out.append(
                dict(job=f"{w}-{step}", kind="ionic", definition=f"science/ionic/{w}/{step}.json",
                     world=w, step=step, order=steps)
            )  # fmt: skip
    for w, cluster in CLUSTERS.items():
        if only and w not in only:
            continue
        child = WORLDS[cluster["child"]]
        for step, k in REDUCTION.items():
            ticks = rules.grid_steps(child["end"], child["legacy"] / k)
            for s in range(SEEDS):
                out.append(
                    dict(job=f"{w}-{step}-s{s}", kind="assembly", command="assembly-cluster",
                         definition=f"science/assembly/{w}/{step}-s{s}.json", world=w, step=step,
                         seed_index=s, ticks=ticks, order=10**5 + ticks)
                )  # fmt: skip
    return out


def definition_of(job):
    """The definition file of one job, as a value."""
    if job["kind"] == "ionic":
        return dict(name=job["step"], definition=definition(job["world"], job["step"]))
    child = WORLDS[CLUSTERS[job["world"]]["child"]]
    return legacy_assembly(
        job["world"], child["legacy"] / REDUCTION[job["step"]], job["seed_index"]
    )


def origin(folder, snapshot, *only):
    """The legacy definitions, job list and manifest of every world, or of the named ones."""
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=False)
    for job in jobs(only):
        path = folder / job["definition"]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(definition_of(job), indent=1, allow_nan=False) + "\n")
    ordered = sorted(jobs(only), key=lambda j: -j["order"])
    (folder / "jobs-science.json").write_text(json.dumps(ordered, indent=1) + "\n")
    worlds = {}
    for w in sorted({j["world"] for j in ordered}):
        child = WORLDS[CLUSTERS[w]["child"]] if w in CLUSTERS else WORLDS[w]
        worlds[w] = dict(
            kind=MODEL_ID[child["kind"]],
            consumer=(WORLDS | CLUSTERS)[w]["consumer"],
            steps_s=[child["legacy"] / k for k in (1, 2, 4)],
            step_counts=[rules.grid_steps(child["end"], child["legacy"] / k) for k in (1, 2, 4)],
            seeds=[[e["seeds"][i] for e in CLUSTERS[w]["pools"].values()] for i in range(SEEDS)]
            if w in CLUSTERS
            else None,
        )
    (folder / "manifest.json").write_text(
        json.dumps(
            dict(
                kind="cells.legacy_rehearsal@1",
                utc=datetime.now(UTC).isoformat(timespec="seconds"),
                made_by="validation/ensemble_reexpression/rehearsal_part2/make_inputs2.py",
                snapshot=part1.snapshot_record(snapshot),
                worlds=worlds,
                files_sha256={
                    str(p.relative_to(folder)): hashlib.sha256(p.read_bytes()).hexdigest()
                    for p in sorted(folder.rglob("*.json"))
                    if p.name != "manifest.json"
                },
            ),
            indent=1,
        )
        + "\n"
    )
    print(f"{len(ordered)} jobs in {folder}")


if __name__ == "__main__":
    if sys.argv[1:2] == ["write"]:
        target = HERE / "inputs_rehearsal_part2.json"
        target.write_text(json.dumps(inputs(), indent=1, allow_nan=False) + "\n")
        print(target)
    elif sys.argv[1:2] == ["origin"]:
        origin(*sys.argv[2:])
    else:
        raise SystemExit(__doc__)
