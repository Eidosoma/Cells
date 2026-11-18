"""Row OL2-5: the OL2/OL3 declarations every engine must refuse (``designs/refusals2/``), and the
references' own reading of the parse rules that refuse them.

Each declaration is a registered world (``ol2_wa``) or run (``ol3_population_run``) with one
defect, named by the rule it breaks (§0.2b rule 1, §0.2c rules 1-8). ``validate`` is the
references' parser: it accepts every registered world and run and refuses each declaration for
its own reason (the registration test holds both); the row asks only that the engine refuses each.

A run refused for JAX's threefry not being partitionable (§0.2d 9) is an environment refusal, not
a declaration; the runs' environment records carry the flag instead (``population.environment_check``).
"""

from __future__ import annotations

import copy
import json
import math
from pathlib import Path

from .common import CheckResult
from .ol2 import K_B, N_A

DIR = Path(__file__).resolve().parent / "designs" / "refusals2"


class Refused(Exception):
    def __init__(self, rule: str, message: str):
        super().__init__(f"{rule}: {message}")
        self.rule = rule


def _phases(doc: dict) -> dict:
    out = {"membrane": {m["species"] for m in doc.get("membrane", [])},
           "lumen": {m["species"] for m in doc.get("lumen", [])},
           "pool": set(doc.get("pool", {}).get("finite", [])) | set(doc.get("pool", {}).get("held_mM", {}))}
    return out


def _tension(doc: dict, ves: dict) -> float:
    q = doc["geometry"]["area_quantum_m2"]
    k = {m["species"]: m["area_quanta"] for m in doc["membrane"]}
    W = sum(n * k[m["species"]] for n, m in zip(ves["n"], doc["membrane"]))
    A = q * W / 2
    NL = sum(ves["l"])
    c_ext = doc["outside_osmolarity_M"]
    V_osm = NL / (N_A * c_ext)
    V_sph = A ** 1.5 / (6 * math.sqrt(math.pi)) * 1e3
    if NL == 0 or V_osm <= V_sph:
        return 0.0
    R = math.sqrt(A / (4 * math.pi))
    return K_B * doc["temperature_K"] * 1e3 * (NL / V_sph - N_A * c_ext) * R / 2


def validate(doc: dict) -> None:
    """Raise ``Refused`` for the first rule a world2 or run2 document breaks."""
    if doc.get("format") == "ool_references.run2@1":
        return validate_run(doc)
    conv = doc.get("conventions", {})
    geo = doc.get("geometry")
    if geo is not None and "exchange_encounter" not in conv:
        raise Refused("§0.2c rule 1", "a world that declares a geometry declares exchange_encounter")
    if geo is None and "exchange_encounter" in conv:
        raise Refused("§0.2c rule 1", "a world without a geometry may not declare exchange_encounter")
    ph = _phases(doc)
    for m in doc.get("membrane", []):
        if "area_quanta" not in m:
            raise Refused("§0.2b rule 1", f"membrane species {m['species']} has no declared area")
        if not isinstance(m["area_quanta"], int) or isinstance(m["area_quanta"], bool) or m["area_quanta"] < 1:
            raise Refused("§0.2c rule 4", f"{m['species']}'s area is not a positive integer number of quanta")
    for st in doc.get("steps", []):
        kind = st["kind"]
        if kind == "join":
            if st.get("direction") != "pool_to_membrane":
                raise Refused("§0.2c rules 2-3", f"{st['id']}: phase exchange is declared only as a join from the pool")
        elif kind == "entry":
            if st.get("direction") != "pool_to_lumen":
                raise Refused("§0.2c rule 2", f"{st['id']}: permeation is declared only as an entry from the pool")
        else:
            places = [(p["phase"], p["species"], p["count"]) for p in st["reactants"] + st["products"]]
            phases = {p[0] for p in places}
            lumen_reactants = sum(p["count"] for p in st["reactants"] if p["phase"] == "lumen")
            if st.get("locus") == "lumen" and lumen_reactants >= 2 and conv.get("lumen_volume") == "osmotic":
                raise Refused("§0.2c rule 7", f"{st['id']}: a lumen step with two or more lumen reactant molecules")
            if st.get("locus") == "membrane" and lumen_reactants and conv.get("lumen_volume") == "osmotic":
                raise Refused("§0.2c rule 7", f"{st['id']}: a membrane step with a lumen reactant")
            if geo is not None and len(phases) > 1:
                raise Refused("§0.2c rule 3", f"{st['id']}: a cross-phase reaction needs a declared geometric encounter")
            if st.get("locus") == "membrane" and phases != {"membrane"}:
                raise Refused("§0.2c rule 3", f"{st['id']}: count_on_m only on steps whose places lie in the membrane")
            for phase, s, _ in places:
                if s not in ph.get(phase, set()):
                    raise Refused("places", f"{st['id']}: {s} has no {phase} place")
    if geo is not None:
        floor = geo.get("vesicle_floor_quanta")
        if floor is None:
            raise Refused("§0.2c rule 5", "a geometry requires vesicle_floor")
        if not isinstance(floor, int) or floor < 1:
            raise Refused("§0.2c rule 5", "vesicle_floor is a whole number of quanta, at least 1")
        if conv.get("last_molecule") != "kept":
            raise Refused("§0.2c rule 5", "vesicle_floor requires last_molecule: kept")
        if conv.get("lumen_volume") == "osmotic":
            if "sigma_max_N_per_m" not in geo:
                raise Refused("§0.2c rule 8", "sigma_max is required under osmotic")
            if not geo.get("sigma_max_source"):
                raise Refused("§0.2c rule 8", "sigma_max is required with its source")
        c_ext = doc["outside_osmolarity_M"]
        if c_ext < pool_osmolarity(doc, doc["founder"]["p"]):
            raise Refused("§0.2c rule 6", "c_ext is below the declared pool solutes' total")
        if math.isfinite(geo.get("sigma_max_N_per_m", math.inf)):
            for s in ph["membrane"] | ph["lumen"]:
                if s not in ph["pool"]:
                    raise Refused("§0.2c rule 8", f"{s} has no pool place to return to at lysis")
        f = doc["founder"]
        for ves in f.get("vesicles") or [dict(n=f["n"], l=f["l"])]:
            if _tension(doc, ves) > geo.get("sigma_max_N_per_m", math.inf):
                raise Refused("§0.2c rule 8", "a founder beyond sigma_max")


def pool_osmolarity(doc: dict, finite_counts) -> float:
    """The pool's declared solutes in mol/L: finite counts over the pool's volume, held places."""
    V = doc["pool_volume_L"]
    tot = sum(int(x) for x in finite_counts) / (N_A * V)
    return tot + sum(c * 1e-3 for c in doc["pool"]["held_mM"].values())


def validate_run(doc: dict) -> None:
    from .registered2 import world_document, worlds

    world = world_document(worlds()[doc["world"]])
    for s in doc.get("schedules", []):
        if s["kind"] == "transfer" and pool_osmolarity(world, s["fresh_pool"]) > world["outside_osmolarity_M"]:
            raise Refused("§0.2c rule 6", f"schedule {s['index']}'s fresh pool is above c_ext")
        if s["kind"] == "shear" and "k" not in s:
            raise Refused("§0.2c rule 11", f"schedule {s['index']} declares no k")


def _mutations() -> dict:
    """(base, rule, mutation) per declaration."""

    def drop(path):
        def f(d):
            x = d
            for p in path[:-1]:
                x = x[p]
            del x[path[-1]]
        return f

    def setv(path, v):
        def f(d):
            x = d
            for p in path[:-1]:
                x = x[p]
            x[path[-1]] = v
        return f

    def add_step(step):
        return lambda d: d["steps"].append(step)

    def add_species(sid, moieties, phase, step=None):
        def f(d):
            d["species"].append({"id": sid, "moieties": moieties, "standard_mu_kT": {"solution": 0.0}})
            if phase == "lumen":
                d["lumen"].append({"species": sid})
            if step:
                d["steps"].append(step)
        return f

    def mp(phase, s, c=1):
        return {"phase": phase, "species": s, "count": c}

    wa, run = "ol2_wa", "ol3_population_run"
    return {
        "refuse_geometry_without_encounter": (wa, "§0.2c rule 1", drop(["conventions", "exchange_encounter"])),
        "refuse_encounter_without_geometry": (wa, "§0.2c rule 1", drop(["geometry"])),
        "refuse_membrane_species_without_area": (wa, "§0.2b rule 1", drop(["membrane", 1, "area_quanta"])),
        "refuse_non_integer_area_quanta": (wa, "§0.2c rule 4", setv(["membrane", 1, "area_quanta"], 1.5)),
        "refuse_leave_declared": (wa, "§0.2c rules 2-3", setv(["steps", 0, "direction"], "membrane_to_pool")),
        "refuse_join_from_lumen": (wa, "§0.2c rules 2-3", setv(["steps", 1, "direction"], "lumen_to_membrane")),
        "refuse_exit_declared": (wa, "§0.2c rule 2", setv(["steps", 2, "direction"], "lumen_to_pool")),
        "refuse_count_on_m_cross_phase": (wa, "§0.2c rule 3", add_step(
            {"id": "x1", "kind": "membrane", "locus": "membrane", "law": "cells.stochastic_mass_action@1",
             "reactants": [mp("membrane", "L1"), mp("pool", "L1")], "products": [mp("membrane", "L2")],
             "forward_rate_constant_per_s": 0.1})),
        "refuse_interfacial_reaction": (wa, "§0.2c rule 3", add_step(
            {"id": "x2", "kind": "membrane", "locus": "pool", "law": "cells.stochastic_mass_action@1",
             "reactants": [mp("pool", "L1"), mp("membrane", "L1")], "products": [mp("membrane", "L2")],
             "forward_rate_constant_per_s": 0.1})),
        "refuse_pool_to_lumen_reaction": (wa, "§0.2c rule 3", add_step(
            {"id": "x3", "kind": "pool", "locus": "pool", "law": "cells.stochastic_mass_action@1",
             "reactants": [mp("pool", "S")], "products": [mp("lumen", "S")], "forward_rate_constant_per_s": 0.1})),
        "refuse_geometry_without_floor": (wa, "§0.2c rule 5", drop(["geometry", "vesicle_floor_quanta"])),
        "refuse_floor_below_one": (wa, "§0.2c rule 5", setv(["geometry", "vesicle_floor_quanta"], 0)),
        "refuse_floor_without_kept": (wa, "§0.2c rule 5", setv(["conventions", "last_molecule"], "reversible")),
        "refuse_c_ext_below_pool_solutes": (wa, "§0.2c rule 6", setv(["outside_osmolarity_M"], 0.004)),
        "refuse_lumen_step_two_lumen_reactants": (wa, "§0.2c rule 7", add_species("T", {"s": 2}, "lumen", {
            "id": "x4", "kind": "lumen", "locus": "lumen", "law": "cells.stochastic_mass_action@1",
            "reactants": [mp("lumen", "S", 2)], "products": [mp("lumen", "T")], "forward_rate_constant_per_s": 0.1})),
        "refuse_membrane_step_lumen_reactant": (wa, "§0.2c rule 7", add_step(
            {"id": "x5", "kind": "membrane", "locus": "membrane", "law": "cells.stochastic_mass_action@1",
             "reactants": [mp("membrane", "L1"), mp("lumen", "G")], "products": [mp("membrane", "L1"), mp("lumen", "S")],
             "forward_rate_constant_per_s": 0.1})),
        "refuse_lysis_species_without_pool_place": (wa, "§0.2c rule 8", setv(["pool", "finite"], ["L1"])),
        "refuse_osmotic_without_sigma_max": (wa, "§0.2c rule 8", drop(["geometry", "sigma_max_N_per_m"])),
        "refuse_sigma_max_without_source": (wa, "§0.2c rule 8", drop(["geometry", "sigma_max_source"])),
        "refuse_founder_beyond_sigma_max": (wa, "§0.2c rule 8", setv(["founder", "l"], [400000, 2000])),
        "refuse_fresh_pool_above_c_ext": (run, "§0.2c rule 6", setv(["schedules", 1, "fresh_pool"], [10 ** 9, 0])),
        "refuse_shear_without_k": (run, "§0.2c rule 11", drop(["schedules", 0, "k"])),
    }


def declarations() -> dict:
    from .registered2 import REGISTERED_ON, run_document, runs, world_document, worlds

    ws = worlds()
    base = {"ol2_wa": world_document(ws["ol2_wa"]), "ol3_population_run": run_document(runs(ws)["ol3_population_run"])}
    out = {}
    for rid, (b, rule, mutate) in _mutations().items():
        d = copy.deepcopy(base[b])
        mutate(d)
        d["id"] = rid
        d["registered"] = REGISTERED_ON
        d["refusal"] = {"rule": rule, "base": b}
        out[rid] = d
    return out


def file_name(rid: str, doc: dict) -> str:
    return f"{rid}.{'run2' if doc.get('format') == 'ool_references.run2@1' else 'world2'}.json"


def write_all(out_dir=DIR) -> list:
    from .registered2 import canonical

    Path(out_dir).mkdir(parents=True, exist_ok=True)
    out = []
    for rid, doc in declarations().items():
        p = Path(out_dir) / file_name(rid, doc)
        p.write_bytes(canonical(doc))
        out.append(p)
    return out


def refusal_check(record: dict) -> CheckResult:
    expected = sorted(p.name.split(".")[0] for p in DIR.glob("*.json"))
    missing = [r for r in expected if r not in record]
    accepted = [r for r in expected if r in record and not record[r].get("refused")]
    return CheckResult("registered_refusals_ol2_ol3", not missing and not accepted and bool(expected),
                       dict(declarations=len(expected), missing=missing, accepted=accepted)).as_dict()


def registered_documents() -> list:
    return [json.loads(p.read_text()) for p in sorted(DIR.glob("*.json"))]
