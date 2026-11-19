"""FR-2's declared worlds and drives, frozen into ``reference_inputs.json`` and built for the refs.

The numbers are the builder's declared inputs (the workspace's
fr2-retrieval-v1-20261119/declared_inputs.json, written from fr2-retrieval-v1 c710d841, clean),
read as the exact values of their doubles. Only that file was read: never the fixtures, the
operator or its tests. ``freeze`` copies every number the references use, with its unit and any
derivation rule, and drops the per-number source strings (each world keeps the set of its sources).

    python -m validation.membrane_trafficking.references.worlds DECLARED_INPUTS.json   # freeze

**The drives** (``drives``) are the operator-level tests' half-steps, as the declared
``test_drives`` give them. Each half-step is S_ret(H/2) S_rec(H) S_ret(H/2) with H = dt/2, and its
rates are the declared ones (fraction × the declared area / H). The one drive given as a formula
only, T4's recycling at 0.2 of the pool's area after three retrievals, uses
0.2 (A_b0 + 3 × 0.02 A_k0)/H, as the lead stated it (19 November 2026).
"""

from __future__ import annotations

import copy
import json
import sys
from decimal import Decimal
from pathlib import Path

from validation.core_seams.references.exact import context, dec

from .network import World
from .trafficking import State

HERE = Path(__file__).resolve().parent
INPUTS_FILE = HERE / "reference_inputs.json"

WORLDS = ("held_bath_cell", "held_bath_cell_cycle_enrichments", "cleft_cell",
          "two_routes_one_cleft", "cycle", "t8_sheet")


# --------------------------------------------------------------------------------------------
# Freezing the declared inputs
# --------------------------------------------------------------------------------------------

def _strip(o, sources: set):
    if isinstance(o, dict):
        out = {}
        for k, v in o.items():
            if k == "source":
                sources.add(v)
                continue
            out[k] = _strip(v, sources)
        return out
    if isinstance(o, list):
        return [_strip(v, sources) for v in o]
    return o


def freeze(declared_path) -> dict:
    """reference_inputs.json from the declared inputs: every number, unit and rule, sources per
    world."""
    d = json.loads(Path(declared_path).read_text())
    out = {"about": "FR-2 v1's declared inputs (design statement 1 §12), frozen for the code-blind "
                    "references; sources listed per world",
           "declared_by": {"file": "fr2-retrieval-v1-20261119/declared_inputs.json (workspace)",
                           "generated_by": d.get("generated_by"), "tree": d["tree"]},
           "conventions": d["conventions"], "worlds": {}}
    for name in WORLDS:
        sources = set()
        w = _strip(d["worlds"][name], sources)
        w["sources"] = sorted(sources)
        out["worlds"][name] = w
    out["stress_worlds"] = stress_worlds(out)
    INPUTS_FILE.write_text(json.dumps(out, indent=1, sort_keys=False) + "\n")
    return out


def load() -> dict:
    return json.loads(INPUTS_FILE.read_text())


def world_record(inputs: dict, name: str) -> dict:
    if name in inputs["worlds"]:
        return inputs["worlds"][name]
    return inputs["stress_worlds"][name]


# --------------------------------------------------------------------------------------------
# The stress worlds (approved by the lead, 19 November 2026)
# --------------------------------------------------------------------------------------------

STRESS = ("stress_held_bath", "stress_cleft")
STRESS_POOL_mM = {"Na": 20.0, "K": 120.0, "M": 130.0, "P": 10.0}
STRESS_POOL_fmol = {"Na": 1.0, "K": 6.0, "M": 6.5, "P": 0.5}          # × 0.05 pL
STRESS_CLEFT_fmol = {"Na": 1.0, "K": 0.4, "M": 1.2, "P": 0.2}     # 100/40/120/20 mM × 0.01 pL
STRESS_V_b0 = 0.04                                                     # V, the pool's start
STRESS_CARRIERS = {"K": 0.75, "M": 0.25}       # binary-exact, so the doubles sum to 1 exactly
                                               # (0.7 + 0.3 as doubles is 1 - 5.55e-17)


def _find(items, ident):
    for x in items:
        if x["id"] == ident:
            return x
    raise KeyError(ident)


def _num(value, unit, rule=None):
    out = {"value": value, "unit": unit}
    if rule:
        out["derived"] = rule
    return out


def stress_worlds(frozen: dict) -> dict:
    """Two worlds derived from the declared ones by stated changes, for power the declared worlds
    lack: both declared carriers are +1 at t = 0.5 (a dropped z or swapped t passes), and pool,
    cleft and bath share one composition (the carriers' work is second order). Each change is
    listed."""
    from .network import CHARGE_PER_FMOL
    cpf = float(CHARGE_PER_FMOL)
    out = {}
    for name, base in (("stress_held_bath", "held_bath_cell"), ("stress_cleft", "cleft_cell")):
        w = copy.deepcopy(frozen["worlds"][base])
        w.pop("test_drives", None)
        w.pop("sources", None)
        changes = []
        pool = _find(w["nodes"], "pool_0")
        pool["initial_amounts"] = {s: _num(x, "fmol") for s, x in STRESS_POOL_fmol.items()}
        C_b = _find(w["patches"], "pool_membrane_0")["capacitance"]["value"]
        anchor = -C_b * STRESS_V_b0
        pool["charge_anchor"] = _num(anchor, "C", "-C(pool_membrane_0) x 0.04 V, so V_b = +40 mV")
        pool["fixed_charge_equivalent"] = _num(anchor / cpf, "fmol",
                                               "charge_anchor / CHARGE_PER_FMOL (sum z n0 = 0)")
        changes.append("pool_0: 20/120/130/10 mM Na/K/M/P (1.0/6.0/6.5/0.5 fmol), anchor "
                       "-C_b x 40 mV")
        if name == "stress_cleft":
            cleft = _find(w["nodes"], "cleft_0")
            cleft["initial_amounts"] = {s: _num(x, "fmol") for s, x in STRESS_CLEFT_fmol.items()}
            zsum = sum(x * (1 if s in ("Na", "K") else -1) for s, x in STRESS_CLEFT_fmol.items())
            cleft["fixed_charge_equivalent"] = _num(cleft["charge_anchor"]["value"] / cpf - zsum,
                                                    "fmol", "charge_anchor / CHARGE_PER_FMOL - "
                                                    "sum z n0")
            changes.append("cleft_0: 100/40/120/20 mM Na/K/M/P (1.0/0.4/1.2/0.2 fmol), its "
                           "declared anchor kept")
        route = w["routes"][0]
        route["carriers"] = {s: _num(t, "1 (transference number)")
                             for s, t in STRESS_CARRIERS.items()}
        changes.append("uptake_0's carriers: K 0.75, M (z = -1) 0.25")
        if name == "stress_held_bath":
            route["retrieval_enrichment"] = {"kir_0": _num(1.0, "1"), "nav_0": _num(0.5, "1")}
            route["recycling_enrichment"] = {"kir_0": _num(2.0, "1"), "nav_0": _num(1.0, "1")}
            route["R0"] = {"kir_0": _num(400.0, "units"), "nav_0": _num(200.0, "units")}
            changes.append("enrichments e: Kir 1, NaV 0.5; e_r: Kir 2, NaV 1; R0: Kir 400, "
                           "NaV 200 units")
        H = 0.0005
        A_k0 = _find(w["patches"], route["source_patch"])["area"]["value"]
        A_b0 = _find(w["patches"], "pool_membrane_0")["area"]["value"]

        def ret(f, rid=route["id"], src=route["source_patch"], A=A_k0, H=H):
            return {rid: _num(f * A / H, "m^2/s", f"{f} x A({src}) / H")}

        def rec(f, rid=route["id"], A=A_b0, H=H):
            return {rid: _num(f * A / H, "m^2/s", f"{f} x A(pool_membrane_0) / H")}

        if name == "stress_held_bath":
            drives_ = [
                {"id": "retrieval", "checks": "T4 and T6",
                 "half_steps": [{"retrieval": ret(0.03), "recycling": {}}]},
                {"id": "recycling", "checks": "T4 and T6",
                 "half_steps": [{"retrieval": {}, "recycling": rec(0.2)}]},
                {"id": "both directions", "checks": "T6",
                 "half_steps": [{"retrieval": ret(0.02), "recycling": rec(0.1)}]},
                {"id": "cycle", "checks": "T3 and T5 (units with R0 > 0)",
                 "half_steps": [{"retrieval": ret(0.02), "recycling": {}}] * 2
                 + [{"retrieval": {}, "recycling": rec(0.1)}] * 2}]
        else:
            drives_ = [{"id": "retrieval", "checks": "T4 and T6",
                        "half_steps": [{"retrieval": ret(0.03), "recycling": {}}]}]
        w["stress_drives"] = [dict(d, H=_num(H, "s")) for d in drives_]
        w["notes"] = (f"Stress world from the declared {base}, changed as listed; every other "
                      "number is the declared one. Its drives are explicit half-steps.")
        w["derived_from"] = base
        w["changes"] = changes
        out[name] = w
    return out


# --------------------------------------------------------------------------------------------
# Building a world
# --------------------------------------------------------------------------------------------

def v(x):
    """A declared number's value, exactly."""
    return dec(x["value"])


def build(inputs: dict, name: str) -> State:
    """The declared world as a reference State: nodes, patches, amounts, populations, routes."""
    w = world_record(inputs, name)
    valences = {s["id"]: int(s["valence"]["value"]) for s in w["species"]}
    nodes, amounts = {}, {}
    for c in w["cells"]:
        nodes[c["id"]] = {"kind": "cell", "volume_pL": v(c["volume"]),
                          "anchor_C": v(c["charge_anchor"])}
        amounts[c["id"]] = {s: v(x) for s, x in c["initial_amounts"].items()}
    for n in w["nodes"]:
        if n["held"]:
            nodes[n["id"]] = {"kind": "held", "volume_pL": v(n["volume"]),
                              "potential_V": v(n["held_potential"]),
                              "reference_mM": {s: v(x) for s, x in
                                               n["reference_concentrations"].items()}}
        else:
            nodes[n["id"]] = {"kind": "free", "volume_pL": v(n["volume"]),
                              "anchor_C": v(n["charge_anchor"])}
            amounts[n["id"]] = {s: v(x) for s, x in n["initial_amounts"].items()}
    patches = {p["id"]: {"inside": p["inside"], "outside": p["outside"], "area_m2": v(p["area"]),
                         "capacitance_F": v(p["capacitance"])} for p in w["patches"]}
    world = World(nodes, patches, amounts, valences, v(w["temperature"]))
    routes, records = [], {}
    for r in w["routes"]:
        routes.append({"id": r["id"], "plasma_patch": r["source_patch"],
                       "pool_patch": r["destination"]["patch"],
                       "pool_node": r["destination"]["node"],
                       "carriers": {s: v(x) for s, x in r["carriers"].items()},
                       "enrichment": {p: v(x) for p, x in
                                      r.get("retrieval_enrichment", {}).items()},
                       "recycling_enrichment": {p: v(x) for p, x in
                                                r.get("recycling_enrichment", {}).items()}})
        for p, x in r.get("R0", {}).items():
            records[(r["id"], p)] = v(x)
    populations = {p["id"]: {"units": v(p["N0"]), "patch": p["patch"]}
                   for p in w.get("populations", [])}
    return State(world, routes, populations, records)


def anchor_consistency(inputs: dict, name: str) -> dict:
    """Each declared anchor against CHARGE_PER_FMOL (Σ z n_0 + the fixed-charge equivalent): the
    relative difference (a check of the declared data, not of the engine)."""
    from .network import CHARGE_PER_FMOL
    w = world_record(inputs, name)
    z = {s["id"]: int(s["valence"]["value"]) for s in w["species"]}
    out = {}
    with context():
        for n in list(w["cells"]) + [n for n in w["nodes"] if not n["held"]]:
            q = CHARGE_PER_FMOL * (sum((z[s] * v(x) for s, x in n["initial_amounts"].items()),
                                       Decimal(0)) + v(n["fixed_charge_equivalent"]))
            a = v(n["charge_anchor"])
            out[n["id"]] = float(abs(q - a) / abs(a)) if a != 0 else float(abs(q))
    return out


# --------------------------------------------------------------------------------------------
# The operator-level drives
# --------------------------------------------------------------------------------------------

def _area(w: dict, patch: str) -> Decimal:
    for p in w["patches"]:
        if p["id"] == patch:
            return v(p["area"])
    raise KeyError(patch)


def drives(inputs: dict) -> dict:
    """Every operator-level drive: {id: {"world", "test", "H", "half_steps": [(ret, rec)]}}, with
    each half-step's retrieval and recycling rates per route (m²/s)."""
    out = {}
    with context():
        for name in WORLDS:
            w = inputs["worlds"][name]
            for i, d in enumerate(w.get("test_drives", [])):
                test = d["test"]
                if "retrieval" not in d and "retrieval_rates" not in d:
                    continue                                # T5's ODE drive: see t5_both()
                H = v(d["H"])
                route = w["routes"][0]["id"]
                if "retrieval_rates" in d:                  # two routes, one half-step
                    ret = {r: v(x) for r, x in d["retrieval_rates"].items()}
                    steps = [(ret, {})] * int(d["half_steps"]["value"])
                else:
                    ret = {route: v(d["retrieval"]["rate"])}
                    rec = {route: v(d["recycling"]["rate"])}
                    steps = [(ret, rec)] * int(d["half_steps"]["value"])
                    A_k0 = _area(w, w["routes"][0]["source_patch"])
                    A_b0 = _area(w, w["routes"][0]["destination"]["patch"])
                    note = d.get("note", "")
                    if note.startswith("then one half-step of recycling at 0.2 of the pool patch's "
                                       "area after these three"):
                        steps = steps + [({}, {route: Decimal("0.2") * (A_b0 + 3 * Decimal("0.02")
                                                                         * A_k0) / H})]
                    elif note == ("then one half-step of recycling at 0.2 of the pool patch's "
                                  "declared area"):
                        steps = steps + [({}, {route: Decimal("0.2") * A_b0 / H})]
                    elif note == ("then one half-step with retrieval 0.02 and recycling 0.1 of the "
                                  "declared areas"):
                        steps = steps + [({route: Decimal("0.02") * A_k0 / H},
                                          {route: Decimal("0.1") * A_b0 / H})]
                    elif note == ("then 4 half-steps of recycling at 0.05 of the pool patch's "
                                  "declared area"):
                        steps = steps + [({}, {route: Decimal("0.05") * A_b0 / H})] * 4
                    elif note:
                        raise ValueError(f"{name} drive {i}: an unread note: {note!r}")
                key = f"{name}:{test.split('::')[-1]}"
                out[key] = {"world": name, "test": test, "H": H, "half_steps": steps}
        for name in STRESS:
            w = inputs["stress_worlds"][name]
            for d in w["stress_drives"]:
                steps = [({r: v(x) for r, x in hs["retrieval"].items()},
                          {r: v(x) for r, x in hs["recycling"].items()}) for hs in d["half_steps"]]
                out[f"{name}:{d['id']}"] = {"world": name, "test": f"stress ({d['checks']})",
                                            "H": v(d["H"]), "half_steps": steps}
    return out


def t5_both(inputs: dict) -> dict:
    """T5's both-directions drive: the rates, the duration and the populations' enrichments."""
    w = inputs["worlds"]["held_bath_cell_cycle_enrichments"]
    d = [x for x in w["test_drives"] if "retrieval_rate" in x][0]
    r = w["routes"][0]
    pops = {p["id"]: {"N0": v(p["N0"]), "e": v(r["retrieval_enrichment"][p["id"]]),
                      "e_r": v(r["recycling_enrichment"][p["id"]]), "R0": v(r["R0"][p["id"]])}
            for p in w["populations"]}
    return {"test": d["test"], "r1": v(d["retrieval_rate"]), "r2": v(d["recycling_rate"]),
            "duration": v(d["duration"]), "A_k0": _area(w, r["source_patch"]),
            "A_b0": _area(w, r["destination"]["patch"]), "populations": pops,
            "note": d["note"]}


if __name__ == "__main__":
    freeze(sys.argv[1])
    print(f"wrote {INPUTS_FILE}")
