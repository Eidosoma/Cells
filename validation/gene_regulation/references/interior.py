"""The published interior sample (gr1-sheet-2026-11-20b, §5.6, erratum E3): an interface addition.

From a run of `run.py --sets published-interior` (stages refs and closed), `write_addition` writes
interior_published.json. At each of the sheet's 32 published points it records:
- A1's closed-form gaps against ε_A1 (§5.1), relative to the limit's steady state;
- every A1-M world's J̄, E and F gaps against ε_M (§5.2), with the closed forms themselves;
- the solves' convergence (the 100× check) and their worst identity level;
- the same gaps in the original interface's interior sets, which hold the same points, for an exact
  comparison.
"""

from __future__ import annotations

import json
from pathlib import Path

from . import plants, sheet
from .assemble import _write
from .run import _load, slug, world_by_name, world_names


def _k(label: str) -> int:
    return int(label.rsplit(" ", 1)[1])


def write_addition(out: Path, sets: list, prov: dict, reference: Path | None = None) -> Path:
    out = Path(out)
    wn = world_names()
    ref = None
    if reference is not None and (Path(reference) / "inputs.json").exists():
        ref = {n: json.loads((Path(reference) / f"{n}.json").read_text())
               for n in ("inputs", "r_chain", "r_machine")}
        keys = ("G_ATP_kJ_mol", "E_pd_kJ_mol", "E_pep_kJ_mol", "E_rc_RT")
        by_value = {tuple(float(p[k]) for k in keys): p["index"]
                    for p in ref["inputs"]["potential_sets"]}
    rows = []
    for i, p in enumerate(sets):
        closed = _load(out / "closed" / f"{i:02d}.pkl")
        recs = {w: _load(out / "refs" / f"{i:02d}_{slug(w)}.pkl") for w in wn}
        a1 = plants.a1_gaps(recs["A1"]["readouts"], closed["a1"])
        a1m, cf = {}, {}
        for w in wn:
            if w == "A1":
                continue
            W = world_by_name(w)
            c = closed["machine"][w]
            a1m[w] = plants.machine_gaps(recs[w]["readouts"], c, [r.name for r in W.routes],
                                         next(iter(W.pools)))
            cf[w] = {k: float(v) for k, v in c.items() if k != "prec"}
        row = {"k": _k(p.label), "potentials": p.as_dict(),
               "a1_gaps": a1, "a1_within_eps_A1": max(a1.values()) <= sheet.EPS_A1,
               "a1m_gaps": a1m, "a1m_closed": cf,
               "a1m_within_eps_M": all(max(g.values()) <= sheet.EPS_M for g in a1m.values()),
               "convergence_worst": max(max(r["convergence"].values()) for r in recs.values()),
               "identity_worst": max(max(r["identity_levels"].values()) for r in recs.values()),
               "closed_form_precision": closed["precision"]}
        if ref is not None:
            j = by_value.get(tuple(float(getattr(p, k)) for k in ("G_ATP", "E_pd", "E_pep",
                                                                 "E_rc_RT")))
            row["reference_set"] = j
            if j is not None:
                ra1 = ref["r_chain"]["sets"][j]["gaps"]
                rm = ref["r_machine"]["sets"][j]["worlds"]
                row["difference_to_reference"] = {
                    "a1": max(abs(a1[k] - ra1[k]) for k in a1),
                    "a1m": max(abs(a1m[w][k] - rm[w]["gaps"][k]) for w in a1m for k in a1m[w])}
        rows.append(row)
    a1_best = max(((v, r["k"], key) for r in rows for key, v in r["a1_gaps"].items()))
    m_best = max(((v, r["k"], w, key) for r in rows for w, g in r["a1m_gaps"].items()
                  for key, v in g.items()))
    summary = {
        "points": len(rows),
        "a1_largest_gap": {"value": a1_best[0], "k": a1_best[1], "readout": a1_best[2]},
        "a1m_largest_gap": {"value": m_best[0], "k": m_best[1], "world": m_best[2],
                            "item": m_best[3]},
        "eps_A1": sheet.EPS_A1, "eps_M": sheet.EPS_M,
        "all_within_eps_A1": all(r["a1_within_eps_A1"] for r in rows),
        "all_within_eps_M": all(r["a1m_within_eps_M"] for r in rows),
        "sheet_interior": {"A1": float(sheet.SHEET_BOUNDS["A1 interior"][0]),
                           "A1-M": float(sheet.SHEET_BOUNDS["A1-M interior"][0])},
        "convergence_worst": max(r["convergence_worst"] for r in rows),
        "identity_worst": max(r["identity_worst"] for r in rows),
    }
    if ref is not None:
        diffs = [r["difference_to_reference"] for r in rows if "difference_to_reference" in r]
        summary["reference"] = {
            "interface_sets": sorted(r["reference_set"] for r in rows),
            "matched": len(diffs),
            "largest_difference": max(max(d.values()) for d in diffs) if diffs else None}
    doc = {"kind": "cells.gene_regulation.references.interior_published@1",
           "sheet": {"tag": sheet.SHEET_TAG_B, "section": "§5.6, erratum E3: the published table"},
           "definition": "A1: max over the outputs on [0, t_off) of |closed form − ODE| over the "
                         "limit's steady state. A1-M: |ODE − closed form|/closed form for J̄ over "
                         "the final window and E and F at t_end.",
           "provenance": prov,
           "invocations": [json.loads(q.read_text())
                           for q in sorted((out / "invocations").glob("*.json"))],
           "summary": summary, "rows": rows}
    target = out / "interface_addition"
    target.mkdir(exist_ok=True)
    _write(target / "interior_published.json", doc)
    print("interior addition:", json.dumps(summary))
    return target / "interior_published.json"
