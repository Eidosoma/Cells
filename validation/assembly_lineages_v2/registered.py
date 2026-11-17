"""A reader of the references' registered worlds (format ool_references.world@1) into definitions.

OL1's independent references (OL5) register their worlds in their own format. This module maps one
such file to a cells.assembly_lineages@2 world, field by field, and nothing else. It never checks a
world: every refusal is the engine's parser's (spec.py). So a key the mapping does not know is
passed on unchanged, for the parser to refuse, and a defect in a registered refusal world reaches
the parser as it is.

The mapping (registered -> engine):
- units: time; temperature_K; standard_concentration_mM.float;
- species: id, moieties, standard_mu_RT {kind: entry.float} (μ°/RT; `exp_minus` is its exact
  exp(−μ°)), identity `label_only` as no catalogue;
- places, in the registered order within each phase: the pool's (held with held_mM.float, or
  finite), the membrane's, the lumen's; each dilute phase's volume_L.float;
- steps: id, law, locus, reactants, products, forward_rate_per_s.float, and every other key as it
  is; each step's transition_state_factor entries become the world's rate_factor entries
  (catalyst species, step, ddG_kT), with the catalysing phase the catalysts' phase (the engine
  refuses any but the membrane);
- regular_mixing_chi: the regular term's pairs, each chi an exact rational read as a float; none
  gives no regular term;
- initial_state: the founder.
The registered `X` of a dilute phase is the exact value of N_A V c0; it is returned beside the
definition, for the record (extents).
"""

import copy
from fractions import Fraction

from cells.models.assembly_lineages_v2 import (
    IDEAL_MIXING,
    MODEL_ID,
    REGULAR_MIXING,
    TRANSITION_STATE,
)

FORMAT = "ool_references.world@1"
MAPPED_STEP_KEYS = {"id", "law", "locus", "reactants", "products", "forward_rate_per_s",
                    "transition_state_factor"}  # fmt: skip


def _float(value):
    """A registered number: {exact, float} or a bare number or rational string."""
    if isinstance(value, dict):
        return float(value["float"])
    if isinstance(value, str):
        return float(Fraction(value))
    return value


def world(registered, conventions, role=None):
    """(the engine's world dict, the registered extents {phase: X}) of a registered world; `role`
    is the world_role the caller declares (probe for a rate table; none for a run)."""
    if registered.get("format") != FORMAT:
        raise ValueError(f"a registered world is {FORMAT}, not {registered.get('format')!r}")
    phases = registered["phases"]
    out_phases = {}
    places = registered["places"]
    pool = [p for p in places if p["phase"] == "pool"]
    if pool:
        out_phases["pool"] = {
            "volume_L": _float(phases["pool"]["volume_L"]),
            "species": [
                {"id": p["species"], "kind": "held", "held_mM": _float(p["held_mM"])}
                if "held_mM" in p
                else {"id": p["species"], "kind": "finite"}
                for p in pool
            ],
        }
    membrane = [p["species"] for p in places if p["phase"] == "membrane"]
    if membrane or "membrane" in phases:
        out_phases["membrane"] = {"species": membrane}
    lumen = [p["species"] for p in places if p["phase"] == "lumen"]
    if lumen:
        out_phases["lumen"] = {"volume_L": _float(phases["lumen"]["volume_L"]), "species": lumen}
    species = [
        {
            "id": s["id"],
            "moieties": copy.deepcopy(s["moieties"]),
            "standard_mu_RT": {kind: _float(entry) for kind, entry in s["standard_mu_RT"].items()},
            "catalogue": None,
            "evidence": None,
        }
        for s in registered["species"]
    ]
    steps, entries, catalysing = [], [], set()
    for s in registered["steps"]:
        step = {k: copy.deepcopy(v) for k, v in s.items() if k not in MAPPED_STEP_KEYS}
        step.update(
            id=s["id"],
            law=s["law"],
            locus=s["locus"],
            reactants=copy.deepcopy(s["reactants"]),
            products=copy.deepcopy(s["products"]),
            forward_rate_per_s=_float(s["forward_rate_per_s"]),
        )
        steps.append(step)
        for factor in s.get("transition_state_factor", []):
            name, phase = factor["catalyst"].split("@")
            catalysing.add(phase)
            entries.append({"catalyst": name, "step": s["id"], "ddG_kT": factor["ddG_kT"]})
    terms = [{"law": IDEAL_MIXING}]
    chi = registered.get("regular_mixing_chi") or []
    if chi:
        terms.append(
            {
                "law": REGULAR_MIXING,
                "chi_kT": [{"pair": list(e["pair"]), "chi": _float(e["chi"])} for e in chi],
            }
        )
    out = {
        "units": {
            "time": registered["units"]["time"],
            "temperature_K": registered["temperature_K"],
            "standard_concentration_mM": _float(registered["standard_concentration_mM"]),
        },
        "conventions": dict(conventions),
        "species": species,
        "phases": out_phases,
        "steps": steps,
        "free_energy": terms,
        "founder": dict(registered["initial_state"]),
    }
    if entries:
        phase = "membrane" if catalysing == {"membrane"} else sorted(catalysing - {"membrane"})[0]
        out["rate_factor"] = {
            "law": TRANSITION_STATE,
            "catalysing_phase": phase,
            "entries": entries,
        }
    if role is not None:
        out["world_role"] = role
    extents = {p: Fraction(phases[p]["X"]) for p in phases if "X" in phases[p]}
    return out, extents


def definition(registered, conventions, experiment, execution, role=None):
    """A complete definition: the registered world under the declared conventions."""
    the_world, _ = world(registered, conventions, role)
    return {
        "schema_version": 1,
        "model": {"id": MODEL_ID, "world": the_world},
        "experiment": copy.deepcopy(experiment),
        "execution": copy.deepcopy(execution),
    }
