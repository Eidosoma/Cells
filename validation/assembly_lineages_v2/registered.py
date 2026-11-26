"""A reader of the references' registered worlds (format ool_references.world@1) into definitions.

OL1's independent references (OL5) register their worlds in their own format. This module maps one
such file to a cells.model.assembly_lineages@2 world, field by field, and nothing else. It never checks a
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
- initial_state: the founder;
- world_role (§0.2b rule 8): passed on as it is when the registered file declares it, never added.
The registered `X` of a dilute phase is the exact value of N_A V c0; it is returned beside the
definition, for the record (extents).

**OL2 and OL3** (`world2`, `run_entries`, `definition2`): OL5's registered OL2/OL3 worlds (format
ool_references.world2@1), runs (ool_references.run2@1) and amendment 7's division inputs
(ool_references.division_inputs@1), mapped the same way, field by field, never checked:
- units: temperature_K; standard_concentration_M × 10³ as standard_concentration_mM; time in s.
  The registered units block is the format's fixed declaration (UNITS2); any other is passed on;
- conventions: the seven tokens as declared;
- species: id, moieties, standard_mu_kT {bilayer, solution} as standard_mu_RT; no catalogue;
- phases: the pool's `finite` species in order, then its `held_mM` ones in order (held at that
  concentration), with volume_L from pool_volume_L; the membrane's and the lumen's species in order
  (the osmotic lumen declares no volume);
- steps: a join is cells.reaction.phase_exchange@1 and an entry cells.reaction.membrane_permeation@1, one molecule of
  the species from the direction's first phase to its second (so a leave, an exit or a join from
  the lumen reaches the parser as declared), its rate under the key its `constant` names
  (k_ins_m_per_s, D_m2_per_s, P_m_per_s as insertion_velocity_m_per_s, diffusivity_m2_per_s,
  permeability_m_per_s); its `encounter` is consumed when it is the world's token (a join) or
  permeation_area (an entry). A mass-action step keeps its law and locus, its sides become
  {species@phase: count}, forward_rate_constant_per_s becomes forward_rate_per_s, and its own
  membrane_kinetics is consumed when it is the world's token. `kind` is consumed;
- geometry: law from `model` (`interface` consumed when it is cells.assembly_geometry@1);
  area_quantum_m2; each membrane species' area_quanta as area_per_leaflet {quanta, provenance};
  vesicle_floor_quanta as vesicle_floor {quanta, provenance}; kappa_kT and kappa_bar_kT as {value,
  provenance} when closure_cost_kT names the closed sphere's formula (a number is closure_cost_kT
  {value, provenance}); sigma_max_N_per_m {value, provenance}, its provenance sigma_max_source;
- free energy: ideal mixing, and the osmotic lumen with outside_osmolarity_M × 10³ as
  outside_osmolarity_mM {value, provenance};
- the founder: {n, l, p} by position over the membrane, lumen and finite pool species; founder
  vesicles in population mode as the population block (cells.population.shared_pool@1, the run's slots), the
  world's founder holding the pool and every vesicle place at 0;
- the run: mode; slots; t_end_s as time_horizon_s; max_events as event_limit; its schedules as
  they are (an empty list declares none). Its `streams` text is not mapped: the engine records its
  own stream layout and identity;
- the division inputs: {law: cells.operator.shear_fission@1}, with the continuation and a non-null critical
  stress (as {value, provenance}) when declared.

**Provenance** (§0.2e rule 3, as ruled for OL5's probe roles, 22 November 2026): a value takes the
registered world's own source text where the registered format carries one, and otherwise
"unsourced; registered OL5 world <id>". The format carries one only for σ_max (sigma_max_source),
which §0.2c rule 8 requires: a missing sigma_max_source passes through as a σ_max with no
provenance, and the parser refuses it; the default text is never put in its place.

**Every defect reaches the parser as it is:** no value is cast (1.5 quanta and a floor of 0 pass as
declared, and a non-number is not converted); a missing field stays missing; a field the mapping
does not know, or whose engine block the document lacks, is passed on unchanged under its
registered name (OL4's `source`, `provenance` and step factors among them, until OL4's own
mapping); a per-place list whose length does not match its places passes on in its registered
form. The reader raises only for a document of another format.
"""

import copy
from fractions import Fraction

from cells.models.assembly_lineages_v2 import (
    IDEAL_MIXING,
    MEMBRANE_PERMEATION,
    MODEL_ID,
    OSMOTIC_LUMEN,
    PHASE_EXCHANGE,
    REGULAR_MIXING,
    SHARED_POOL,
    SHEAR_FISSION,
    TRANSITION_STATE,
)
from validation import id_table

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


def world(registered, conventions):
    """(the engine's world dict, the registered extents {phase: X}) of a registered world. Its
    world_role, when the registered file declares one, is passed on as it is; the reader adds none
    (§0.2b rule 8: the role is the registered world's own declaration)."""
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
    if "world_role" in registered:
        out["world_role"] = copy.deepcopy(registered["world_role"])
    extents = {p: Fraction(phases[p]["X"]) for p in phases if "X" in phases[p]}
    return out, extents


def definition(registered, conventions, experiment, execution):
    """A complete definition: the registered world under the declared conventions, its old IDs
    translated (validation/id_table.py)."""
    the_world, _ = world(registered, conventions)
    return {
        "schema_version": 1,
        "model": {"id": MODEL_ID, "world": id_table.translate(the_world)},
        "experiment": copy.deepcopy(experiment),
        "execution": copy.deepcopy(execution),
    }


# ------------------------------------------------------------------ OL2 and OL3 (world2@1)

FORMAT2 = "ool_references.world2@1"
RUN_FORMAT2 = "ool_references.run2@1"
DIVISION_FORMAT = "ool_references.division_inputs@1"
UNITS2 = {"D": "m^2/s", "P": "m/s", "concentration": "mol/L (held places: mM)", "energy": "k_BT",
          "k_ins": "m/s", "q": "m^2", "sigma_max": "N/m", "time": "s", "volume": "L"}  # fmt: skip
GEOMETRY_INTERFACE2 = "cells.assembly_geometry@1"
CLOSURE_FORMULA = "8 pi kappa + 4 pi kappa_bar"
RATE_KEYS2 = {"k_ins_m_per_s": "insertion_velocity_m_per_s", "D_m2_per_s": "diffusivity_m2_per_s",
              "P_m_per_s": "permeability_m_per_s"}  # fmt: skip
EXCHANGE2 = {"join": PHASE_EXCHANGE, "entry": MEMBRANE_PERMEATION}
PHASES2 = ("pool", "membrane", "lumen")
METADATA2 = frozenset({"format", "id", "registered", "authority", "description", "refusal"})
MAPPED2 = frozenset({"units", "conventions", "geometry", "temperature_K",
                     "standard_concentration_M", "outside_osmolarity_M", "pool_volume_L",
                     "species", "membrane", "lumen", "pool", "steps", "founder"})  # fmt: skip
RUN_KEYS2 = frozenset({"format", "id", "world", "registered", "authority", "description",
                       "refusal", "mode", "slots", "t_end_s", "max_events", "schedules",
                       "streams"})  # fmt: skip
SINGLE_LINEAGE, POPULATION = "single_lineage", "population"
_MISSING = object()


def provenance2(registered):
    """§0.2e rule 3's text for a value whose registered format carries no source of its own."""
    return f"unsourced; registered OL5 world {registered.get('id')}"


def _number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _milli(value):
    """A concentration in mol/L as mM (× 10³); anything else as it is, for the parser."""
    return value * 1e3 if _number(value) else copy.deepcopy(value)


def _valued(value, provenance):
    return {"value": copy.deepcopy(value), "provenance": provenance}


def _phase_species(entries, allowed):
    """The species of a registered membrane or lumen list, in order; None when an entry is not an
    object with its species and only the allowed keys (the list then passes on as it is)."""
    if not isinstance(entries, list):
        return None
    out = []
    for entry in entries:
        if not isinstance(entry, dict) or "species" not in entry or not set(entry) <= allowed:
            return None
        out.append(entry["species"])
    return out


def _pool2(raw, volume):
    """The pool phase: finite species in order, then held ones; None when it cannot be mapped."""
    if not isinstance(raw, dict) or not set(raw) <= {"finite", "held_mM"}:
        return None
    finite, held = raw.get("finite", []), raw.get("held_mM", {})
    if not isinstance(finite, list) or not isinstance(held, dict):
        return None
    species = [{"id": s, "kind": "finite"} for s in finite]
    species += [{"id": s, "kind": "held", "held_mM": copy.deepcopy(v)} for s, v in held.items()]
    out = {"species": species}
    if volume is not _MISSING:
        out["volume_L"] = copy.deepcopy(volume)
    return out


def _species2(entries):
    if not isinstance(entries, list):
        return copy.deepcopy(entries)
    out = []
    for s in entries:
        if not isinstance(s, dict) or not set(s) <= {"id", "moieties", "standard_mu_kT"}:
            out.append(copy.deepcopy(s))
            continue
        entry = {k: copy.deepcopy(s[k]) for k in ("id", "moieties") if k in s}
        if "standard_mu_kT" in s:
            entry["standard_mu_RT"] = copy.deepcopy(s["standard_mu_kT"])
        out.append(entry | {"catalogue": None, "evidence": None})
    return out


def _side2(side):
    """[{phase, species, count}] as {species@phase: count}; None when it cannot be mapped."""
    if not isinstance(side, list):
        return None
    out = {}
    for entry in side:
        if not isinstance(entry, dict) or set(entry) != {"phase", "species", "count"}:
            return None
        name = f"{entry['species']}@{entry['phase']}"
        if name in out:
            return None
        out[name] = copy.deepcopy(entry["count"])
    return out


def _step2(raw, tokens, provenance):
    """One registered step as the engine's (module docstring), or as it is when it cannot be
    mapped."""
    if not isinstance(raw, dict):
        return copy.deepcopy(raw)
    rest = copy.deepcopy(raw)
    kind = rest.pop("kind", None)
    if kind in EXCHANGE2:
        direction = rest.get("direction")
        ends = direction.split("_to_") if isinstance(direction, str) else []
        if "species" not in rest or len(ends) != 2 or not set(ends) <= set(PHASES2):
            return copy.deepcopy(raw)
        species = rest.pop("species")
        rest.pop("direction")
        out = {k: rest.pop(k) for k in ("id",) if k in rest}
        out |= {"locus": rest.pop("locus", "membrane"), "reactants": {f"{species}@{ends[0]}": 1},
                "products": {f"{species}@{ends[1]}": 1}, "law": EXCHANGE2[kind]}  # fmt: skip
        expected = tokens.get("exchange_encounter") if kind == "join" else "permeation_area"
        if "encounter" in rest and rest["encounter"] == expected:
            rest.pop("encounter")
        if rest.get("constant") in RATE_KEYS2 and "value" in rest:
            out[RATE_KEYS2[rest.pop("constant")]] = _valued(rest.pop("value"), provenance)
        return out | rest
    if kind in PHASES2:
        out = {}
        for side in ("reactants", "products"):
            if side in rest:
                mapped = _side2(rest[side])
                out[side] = mapped if mapped is not None else rest[side]
                del rest[side]
        if "forward_rate_constant_per_s" in rest:
            out["forward_rate_per_s"] = rest.pop("forward_rate_constant_per_s")
        if "membrane_kinetics" in rest and rest["membrane_kinetics"] == tokens.get(
            "membrane_kinetics"
        ):
            rest.pop("membrane_kinetics")
        return rest | out
    return copy.deepcopy(raw)


def _geometry2(raw, membrane_entries, provenance):
    """The geometry block (module docstring); anything it does not map passes on inside it."""
    if not isinstance(raw, dict):
        return copy.deepcopy(raw)
    rest = copy.deepcopy(raw)
    out = {}
    if "model" in rest:
        out["law"] = rest.pop("model")
    if rest.get("interface") == GEOMETRY_INTERFACE2:
        rest.pop("interface")
    if "area_quantum_m2" in rest:
        out["area_quantum_m2"] = rest.pop("area_quantum_m2")
    out["area_per_leaflet"] = {
        e["species"]: {"quanta": copy.deepcopy(e["area_quanta"]), "provenance": provenance}
        for e in (membrane_entries if isinstance(membrane_entries, list) else [])
        if isinstance(e, dict) and "species" in e and "area_quanta" in e
    }
    if "vesicle_floor_quanta" in rest:
        floor = rest.pop("vesicle_floor_quanta")
        out["vesicle_floor"] = {"quanta": floor, "provenance": provenance}
    formula = rest.pop("closure_cost_kT", _MISSING)
    if formula is _MISSING or formula == CLOSURE_FORMULA:
        for key in ("kappa_kT", "kappa_bar_kT"):
            if key in rest:
                out[key] = _valued(rest.pop(key), provenance)
    elif _number(formula):
        out["closure_cost_kT"] = _valued(formula, provenance)
    else:
        out["closure_cost_kT"] = formula
    if "sigma_max_N_per_m" in rest:
        entry = {"value": rest.pop("sigma_max_N_per_m")}
        if "sigma_max_source" in rest:  # its own source text, never the default (Q1's ruling)
            entry["provenance"] = rest.pop("sigma_max_source")
        out["sigma_max_N_per_m"] = entry
    return out | rest


def _by_position(species, counts, phase):
    if species is None or not isinstance(counts, list) or len(counts) != len(species):
        return None
    return {f"{s}@{phase}": copy.deepcopy(c) for s, c in zip(species, counts, strict=True)}


def _vesicle2(raw, membrane, lumen):
    if not isinstance(raw, dict) or set(raw) != {"n", "l"}:
        return None
    inner = _by_position(membrane, raw["n"], "membrane")
    inside = _by_position(lumen, raw["l"], "lumen")
    return None if inner is None or inside is None else inner | inside


def _founder2(raw, finite, membrane, lumen, mode, slots, vesicle):
    """(the founder, the population block or None); the registered founder as it is, and no
    block, when it cannot be mapped."""
    if not isinstance(raw, dict) or "p" not in raw:
        return copy.deepcopy(raw), None
    pool = _by_position(finite, raw["p"], "pool")
    if "vesicles" in raw and set(raw) == {"vesicles", "p"} and isinstance(raw["vesicles"], list):
        vesicles = [_vesicle2(v, membrane, lumen) for v in raw["vesicles"]]
    elif set(raw) == {"n", "l", "p"}:
        vesicles = [_vesicle2({"n": raw["n"], "l": raw["l"]}, membrane, lumen)]
    else:
        return copy.deepcopy(raw), None
    if pool is None or not vesicles or any(v is None for v in vesicles):
        return copy.deepcopy(raw), None
    if mode == POPULATION:
        empty = {place: 0 for place in vesicles[0]}
        block = {"structure": SHARED_POOL, "founders": vesicles}
        if slots is not _MISSING:
            block["slots"] = copy.deepcopy(slots)
        return pool | empty, block
    if vesicle is None:
        if len(vesicles) != 1:
            return copy.deepcopy(raw), None
        vesicle = 0
    if not 0 <= vesicle < len(vesicles):
        raise ValueError(f"the founder has {len(vesicles)} vesicles, not a vesicle {vesicle}")
    return pool | vesicles[vesicle], None


def world2(registered, *, mode=SINGLE_LINEAGE, slots=1, division=None, vesicle=None):
    """The engine's world dict of a registered world2 document (module docstring). A single
    lineage's founder is the document's own, or its founder vesicle `vesicle` (one vesicle of a
    world of several, for a probe); a population's founders are its vesicles in `slots` slots.
    `division` is amendment 7's entry for this world, or None (no division block)."""
    if registered.get("format") != FORMAT2:
        raise ValueError(f"a registered world is {FORMAT2}, not {registered.get('format')!r}")
    p = provenance2(registered)
    out = {k: copy.deepcopy(v) for k, v in registered.items() if k not in METADATA2 | MAPPED2}
    tokens = registered.get("conventions")
    tokens = tokens if isinstance(tokens, dict) else {}
    units = {"time": "s"}
    if "temperature_K" in registered:
        units["temperature_K"] = copy.deepcopy(registered["temperature_K"])
    if "standard_concentration_M" in registered:
        units["standard_concentration_mM"] = _milli(registered["standard_concentration_M"])
    out["units"] = units
    if "units" in registered and registered["units"] != UNITS2:
        out["registered_units"] = copy.deepcopy(registered["units"])
    if "conventions" in registered:
        out["conventions"] = copy.deepcopy(registered["conventions"])
    if "species" in registered:
        out["species"] = _species2(registered["species"])
    phases = {}
    pool = _pool2(registered.get("pool"), registered.get("pool_volume_L", _MISSING))
    if pool is not None:
        phases["pool"] = pool
    else:
        out |= {k: copy.deepcopy(registered[k]) for k in ("pool", "pool_volume_L")
                if k in registered}  # fmt: skip
    membrane = _phase_species(registered.get("membrane"), {"species", "area_quanta"})
    if membrane is not None:
        phases["membrane"] = {"species": membrane}
    if "membrane" in registered and (membrane is None or "geometry" not in registered):
        out["membrane"] = copy.deepcopy(registered["membrane"])  # areas with no geometry block
    lumen = _phase_species(registered.get("lumen"), {"species"})
    if lumen is not None:
        phases["lumen"] = {"species": lumen}
    elif "lumen" in registered:
        out["lumen"] = copy.deepcopy(registered["lumen"])
    out["phases"] = phases
    if isinstance(registered.get("steps"), list):
        out["steps"] = [_step2(s, tokens, p) for s in registered["steps"]]
    elif "steps" in registered:
        out["steps"] = copy.deepcopy(registered["steps"])
    terms = [{"law": IDEAL_MIXING}]
    if "outside_osmolarity_M" in registered:
        terms.append({"law": OSMOTIC_LUMEN,
                      "outside_osmolarity_mM": _valued(_milli(registered["outside_osmolarity_M"]),
                                                       p)})  # fmt: skip
    out["free_energy"] = terms
    if "founder" in registered:
        finite = registered["pool"].get("finite") if pool is not None else None
        founder, block = _founder2(registered["founder"], finite, membrane, lumen, mode, slots,
                                   vesicle)  # fmt: skip
        out["founder"] = founder
        if block is not None:
            out["population"] = block
    if "geometry" in registered:
        out["geometry"] = _geometry2(registered["geometry"], registered.get("membrane"), p)
    if division is not None:
        block = {"law": SHEAR_FISSION}
        rest = copy.deepcopy(division)
        if "continuation" in rest:
            block["continuation"] = rest.pop("continuation")
        stress = rest.pop("critical_stress_Pa", None)
        if stress is not None:
            block["critical_stress_Pa"] = _valued(stress, p)
        out["division"] = block | rest
    return out


def run_entries(run):
    """(mode, slots, experiment entries) of a registered run2 document (module docstring): the
    horizon, the event limit and the schedules (none for an empty list); slots is _MISSING when
    the run declares none. A key the mapping does not know is passed on in the entries."""
    if run.get("format") != RUN_FORMAT2:
        raise ValueError(f"a registered run is {RUN_FORMAT2}, not {run.get('format')!r}")
    entries = {k: copy.deepcopy(v) for k, v in run.items() if k not in RUN_KEYS2}
    if "t_end_s" in run:
        entries["time_horizon_s"] = copy.deepcopy(run["t_end_s"])
    if "max_events" in run:
        entries["event_limit"] = copy.deepcopy(run["max_events"])
    if "schedules" in run and run["schedules"] != []:
        entries["schedules"] = copy.deepcopy(run["schedules"])
    mode = run.get("mode", _MISSING)
    slots = run.get("slots", _MISSING)
    if mode != POPULATION and slots is not _MISSING and slots != 1:
        entries["slots"] = copy.deepcopy(slots)  # a single lineage holds one assembly
    return mode, slots, entries


def definition2(registered, *, experiment, execution, run=None, division=None, vesicle=None):
    """A complete definition of a registered world2 document: under its run2 document (mode,
    slots, horizon, event limit and schedules) when given, else as a single lineage, and with
    amendment 7's division entry when given, the document's old IDs translated. The driver's
    `experiment` and `execution` complete it; the run's entries take precedence over the
    driver's."""
    mode, slots, entries = (SINGLE_LINEAGE, 1, {}) if run is None else run_entries(run)
    the_world = world2(registered, mode=mode, slots=slots, division=division, vesicle=vesicle)
    the_execution = copy.deepcopy(execution)
    the_execution.pop("mode", None)
    if mode is not _MISSING:
        the_execution["mode"] = copy.deepcopy(mode)
    return {
        "schema_version": 1,
        "model": {"id": MODEL_ID, "world": id_table.translate(the_world)},
        "experiment": copy.deepcopy(experiment) | entries,
        "execution": the_execution,
    }
