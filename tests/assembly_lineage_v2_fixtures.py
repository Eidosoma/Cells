"""Small worlds of cells.assembly_lineages@2 for its unit tests (OL1).

A lipid-like assembly: an amphiphile L that joins the membrane from the pool and from the lumen, a
second membrane lipid P and their dimer D in the membrane, a solute S that permeates between the
pool and the lumen, and a held precursor F in the pool that makes L there (a source, with its
reservoir work). The potentials are illustrative, not calibrated: L's bilayer potential is the
design note's transfer potential for oleate (−9.43 k_BT, §2.5), used only to keep the numbers in a
physical range; the volumes are small-count ones (X = N_A V c0 near 600 in the pool and 60 in the
lumen), so the unit tests' worlds hold tens of molecules.
"""

import copy

from cells.models.assembly_lineages_v2 import (
    IDEAL_MIXING,
    MASS_ACTION,
    MODEL_ID,
    REGULAR_MIXING,
    TRANSITION_STATE,
)

HELD_MM = 20.0  # The held precursor F's concentration: about one exchange a second in the pool.
CONVENTIONS = {
    "free_energy_form": "discrete",
    "condensed_measure": "multinomial",
    "membrane_kinetics": "count_on_m",
    "lumen_volume": "declared",
    "empty_catalyst_phase": "uncatalysed",
    "last_molecule": "kept",
}


def species(name, moieties, *, solution=None, bilayer=None):
    potentials = {}
    if solution is not None:
        potentials["solution"] = solution
    if bilayer is not None:
        potentials["bilayer"] = bilayer
    return {
        "id": name,
        "moieties": moieties,
        "standard_mu_RT": potentials,
        "catalogue": None,
        "evidence": None,
    }


def step(name, reactants, products, rate, *, phase=None, locus=None):
    out = {"id": name, "reactants": reactants, "products": products, "law": MASS_ACTION}
    out["phase" if phase is not None else "locus"] = phase if phase is not None else locus
    out["forward_rate_per_s"] = rate
    return out


def world(
    *,
    measure="multinomial",
    last="kept",
    regular=True,
    catalysis=True,
    held=True,
    lumen=True,
    conventions=None,
):
    tokens = dict(CONVENTIONS, condensed_measure=measure, last_molecule=last)
    tokens.update(conventions or {})
    pool = [{"id": "L", "kind": "finite"}, {"id": "S", "kind": "finite"}]
    if held:
        pool.append({"id": "F", "kind": "held", "held_mM": HELD_MM})
    out = {
        "units": {"time": "s", "temperature_K": 296.15, "standard_concentration_mM": 1000.0},
        "conventions": tokens,
        "species": [
            species("L", {"l": 1}, solution=0.0, bilayer=-9.43),
            species("P", {"p": 1}, bilayer=-12.0),
            species("D", {"l": 1, "p": 1}, bilayer=-22.5),
            species("S", {"s": 1}, solution=0.0),
            species("F", {"l": 1}, solution=2.0),
        ],
        "phases": {
            "pool": {"volume_L": 1e-21, "species": pool},
            "membrane": {"species": ["L", "P", "D"]},
        },
        "steps": [
            step("join_L", {"L@pool": 1}, {"L@membrane": 1}, 10.0, locus="membrane"),
            step("dimerise", {"L": 1, "P": 1}, {"D": 1}, 1.0, phase="membrane"),
        ],
        "free_energy": [{"law": IDEAL_MIXING}],
        "founder": {"L@pool": 50, "S@pool": 30, "L@membrane": 20, "P@membrane": 10, "D@membrane": 0},
    }
    if lumen:
        out["phases"]["lumen"] = {"volume_L": 1e-22, "species": ["L", "S"]}
        out["steps"] += [
            step("inner_L", {"L@lumen": 1}, {"L@membrane": 1}, 2.0, locus="membrane"),
            step("permeate_S", {"S@pool": 1}, {"S@lumen": 1}, 1.0, locus="membrane"),
        ]
        out["founder"].update({"L@lumen": 0, "S@lumen": 5})
    if held:
        out["steps"].append(step("make_L", {"F": 1}, {"L": 1}, 0.1, phase="pool"))
    if regular:
        out["free_energy"].append(
            {"law": REGULAR_MIXING, "chi_kT": [{"pair": ["L", "P"], "chi": 0.5},
                                               {"pair": ["L", "D"], "chi": -0.3}]}
        )  # fmt: skip
    if catalysis:
        out["rate_factor"] = {
            "law": TRANSITION_STATE,
            "catalysing_phase": "membrane",
            "entries": [{"catalyst": "P", "step": "join_L", "ddG_kT": 0.4},
                        {"catalyst": "D", "step": "dimerise", "ddG_kT": -0.2}],
        }  # fmt: skip
    return out


def paired(the_world):
    """The world with a pool step of order two in one species, 2 L -> Q (a planted power
    propensity, n^2 for n (n − 1), shows only on such a step)."""
    out = copy.deepcopy(the_world)
    out["species"].append(species("Q", {"l": 2}, solution=0.0))
    out["phases"]["pool"]["species"].append({"id": "Q", "kind": "finite"})
    out["founder"]["Q@pool"] = 0
    out["steps"].append(step("pair_L", {"L": 2}, {"Q": 1}, 0.7, phase="pool"))
    return out


def definition(
    the_world,
    *,
    horizon=1.0,
    event_limit=100000,
    row_every=10,
    observations=(),
    trace=True,
    uniforms=False,
    seed=1,
    lineage=0,
    molecules=256,
    chunk=16,
):
    return {
        "schema_version": 1,
        "model": {"id": MODEL_ID, "world": copy.deepcopy(the_world)},
        "experiment": {
            "time_horizon_s": horizon,
            "event_limit": event_limit,
            "row_every_events": row_every,
            "observation_times_s": list(observations),
            "trace": trace,
            "uniforms": uniforms,
        },
        "execution": {
            "backend": "cpu",
            "precision": "float64",
            "mode": "single_lineage",
            "stream": {"seed": seed, "environment": 0, "lineage": lineage, "branch": 0},
            "molecule_capacity": molecules,
            "chunk_events": chunk,
        },
    }
