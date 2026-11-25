"""FR-6's A5'' world: a K-leak population driven through a regulatory state with a per-cell prior.

FR-6 items 1 and 3 (D216; docs/INVENTORY_COUPLING_DESIGN.md §4.4's A5, with a state): two cells,
a and b, each a 2 pL pump-free cell on one constant-field patch facing a bath held at 0 V, with a
gate-free K-leak population (kleak_always_open@1); a neutral regulator X in each cell under D150's
turnover, given the same dose in both; a regulatory state s1 in both cells read from X by a Hill
activation, with the per-cell prior s0 = 0.1 in a and 0.8 in b; and a state_fraction coupling on
each cell's population (F = b + (1 - b) s1, b = 0.1).

The world is the references' own: validation/fr6/references/reference_inputs.json, world
a5pp_prior, registered code-blind before any engine output (the lead's ruling). This module is the
engine-layout adapter: it declares the world as R-cell's documented `World`
(validation/coupling/REFERENCES_USAGE.md's classes; their code is not read here) and translates it
with the coupling protocol's adapter (validation/tissue/regulated_availability_references.
engine_definition: resolved_pump_composite@1 over resolved_pump_tissue@3, with
species_regulated_availability@1 and, for X, D150's scheduled_species_turnover@1). The start, each
cell's potential and background charge, is the references' registered start
(designs/fr6_a5pp_values.json's V0_V and background_fmol), the one both sides share, as the
coupling protocol's A5 started both sides from the reference's.

Control worlds (each one declared change of the registered world, run by the engine, judged by how
far it departs from the registered world's reference): the prior swapped between the cells,
shared (a's, b's, the mean) or ignored (both 0); the state bypassed (A5's instantaneous Hill form:
the same activation of X, K, n and basal, read at once on each population); k_on or k_off x 1.01;
and the basal level x (1 + delta).
"""

import copy
import json
import math
from pathlib import Path

from validation import id_table
from validation.coupling import cells_reference as rc
from validation.coupling import state_reference as rs
from validation.tissue import regulated_availability_references as rr

ROOT = Path(__file__).resolve().parents[2]
REFS = ROOT / "validation" / "fr6" / "references"
INPUTS = REFS / "reference_inputs.json"
VALUES = REFS / "designs" / "fr6_a5pp_values.json"
DESIGN = REFS / "designs" / "fr6_a5pp_design.json"
WORLD_ID = "a5pp_prior"
DECLARED_DT = 1e-3
LADDER_S = (1e-3, 5e-4, 2.5e-4, 1.25e-4)  # The references' dt_ladder_s (checked against them).
RECORD_UNIT_S = 1e-3  # Records align on integer milliseconds.
STATE = "s1"
REGULATOR = "X"


def inputs():
    return id_table.load(INPUTS)


def registered():
    """The references' world, as registered (a deep copy)."""
    return copy.deepcopy(inputs()["worlds"][WORLD_ID])


def registered_start():
    """{cell: (V, background_fmol)}: the references' registered start (designs/
    fr6_a5pp_values.json), shared by both sides."""
    values = json.loads(VALUES.read_text())
    return {c: (float(values["V0_V"][c]), float(values["background_fmol"][c]))
            for c in values["cells"]}


def population_name(cell):
    return f"kleak_{cell}"


def patch_name(cell):
    return f"p_{cell}"


def world_of(w):
    """R-cell's World of a world in the references' form (registered or a control's)."""
    species = tuple(w["species"])
    z = tuple(int(w["species"][s]) for s in species)
    if float(w.get("temperature_K", rr.TEMPERATURE_K)) != rr.TEMPERATURE_K:
        raise ValueError("the adapter's worlds are at 310 K (the coupling adapter's)")
    if species != rr.SPECIES or tuple(w["bath_mM"][s] for s in species) != tuple(
            w["bath_mM"].values()):
        raise ValueError("the species are the coupling adapter's (Na, K, Cl), in that order")
    if float(w["bath_potential_V"]) != 0.0:
        raise ValueError("the bath is held at 0 V")
    cells, patches, populations, regulators = {}, {}, {}, {}
    for c, cell in w["cells"].items():
        cells[c] = rc.Cell(float(cell["volume_pL"]), tuple(float(cell["mM"][s]) for s in species),
                           initial_V=float(cell["initial_V"]))
        patch = cell["patch"]
        patches[patch_name(c)] = rc.Patch(
            c, float(patch["area_m2"]), float(patch["capacitance_F"]),
            tuple(float(patch["leak_permeability_m_per_s"][s]) for s in species))
        q = cell["population"]
        if q["law"] != "kleak_always_open@1":
            raise ValueError("the population is kleak_always_open@1")
        populations[population_name(c)] = rc.Population(
            patch_name(c), float(q["permeability_m_per_s"]),
            tuple(float(q["relative"][s]) for s in species), abundance=float(q["abundance"]),
            opening=float(q["opening"]),
            schedule=tuple((float(t), float(a)) for t, a in q["schedule"]))
        x = cell["regulator_X"]
        volume = float(cell["volume_pL"])
        segments = tuple((float(seg["time_s"]), float(seg["production_fmol_per_s"]),
                          float(seg["clearance_per_s"])) for seg in x["segments"])
        regulators.setdefault(REGULATOR, {})[c] = rs.Turnover(
            float(x["initial_mM"]) * volume, volume, segments)
    state = w["state_s1"]
    entry = state["input"]
    if entry["source"] != REGULATOR:
        raise ValueError("the state reads X")
    states = {STATE: rc.State(
        tuple(state["cells"]), (rc.Input(entry["law"], REGULATOR, float(entry["K_mM"]),
                                         float(entry["n"])),),
        float(state["k_on_per_s"]), float(state["k_off_per_s"]),
        initial={c: float(w["cells"][c]["state_s1_initial"]) for c in state["cells"]})}
    couplings = {}
    for k in w["couplings"]:
        cell = k["target"].split(" of ")[-1]
        if k["law"] in ("state_fraction", "state_complement"):
            couplings[k["id"]] = rc.Coupling(population_name(cell), k["law"], k["source"],
                                             basal=float(k["basal"]))
        else:  # The state bypassed: an instantaneous Hill law of X.
            couplings[k["id"]] = rc.Coupling(population_name(cell), k["law"], k["source"],
                                             basal=float(k["basal"]), K_mM=float(k["K_mM"]),
                                             n=float(k["n"]))
    regulators = {name: rc.Regulator(amounts) for name, amounts in regulators.items()}
    if not any(k["law"].startswith("state_") for k in w["couplings"]):
        states = {}  # No coupling reads the state: it is not declared.
    return rc.World(rr.CONSTANTS, species, z, tuple(float(w["bath_mM"][s]) for s in species),
                    cells, patches, populations=populations, regulators=regulators,
                    states=states, couplings=couplings)


def record_times(w, dt):
    """The world's record times on the step grid: k dt, k = round(t / dt), strictly increasing."""
    return [k * dt for k in sorted({round(t / dt) for t in w["record_times_s"]})]


def build(w, *, dt=DECLARED_DT):
    """The engine definition of a world in the references' form, from the registered start."""
    world = world_of(w)
    return rr.engine_definition(world, dt=dt, end=float(w["end_s"]), times=record_times(w, dt),
                                initial=registered_start())


def registered_world(*, dt=DECLARED_DT):
    return build(registered(), dt=dt)


# ------------------------------------------------------------------ control worlds


def prior(mode):
    """s0 swapped between the cells, shared (a's, b's or the mean), or ignored (both 0)."""
    w = registered()
    a, b = (w["cells"][c]["state_s1_initial"] for c in ("a", "b"))
    values = dict(swapped=(b, a), shared_a=(a, a), shared_b=(b, b),
                  shared_mean=(0.5 * (a + b),) * 2, ignored=(0.0, 0.0))[mode]
    for c, value in zip(("a", "b"), values, strict=True):
        w["cells"][c]["state_s1_initial"] = value
    return w


def state_bypassed():
    """A5's instantaneous form: each population read at once from its cell's X by the state's own
    Hill activation (the same K, n and basal), with no state."""
    w = registered()
    entry = w["state_s1"]["input"]
    w["couplings"] = [dict(k, law=entry["law"], source=entry["source"], K_mM=entry["K_mM"],
                           n=entry["n"]) for k in w["couplings"]]
    return w


def rate(which, factor=1.01):
    """k_on or k_off of the state x factor."""
    w = registered()
    w["state_s1"][f"{which}_per_s"] *= factor
    return w


def basal(delta):
    """Every coupling's basal level x (1 + delta)."""
    w = registered()
    for k in w["couplings"]:
        k["basal"] *= 1.0 + delta
    return w


def ms(t):
    return int(round(t / RECORD_UNIT_S))


def check_ladder():
    found = tuple(inputs()["dt_ladder_s"])
    if found != LADDER_S:
        raise ValueError(f"the references' ladder is {found}")
    return math.isclose(min(found), LADDER_S[-1])
