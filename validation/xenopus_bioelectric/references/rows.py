"""Row registry, the floor model and the band rule (registered once, applied to every row).

BAND RULE (every compared row):

    band = max( tol_abs + tol_rel * |reference| ,  FLOOR_FACTOR * floor )

``tol_abs`` and ``tol_rel`` come from DESIGN.md (the row's family says which section) or, where DESIGN.md
gives none, are labelled ``borrowed`` or ``proposed`` in the family's ``tol_source``.

FLOOR MODEL (``input_perturbation_float64``): a float64 engine holds each real input to a relative
rounding u = 2**-53 and rounds each of at most ~16 operations. The floor of a row is

    floor = G u ( |q| + sum_j | q(x_j (1+u)) - q(x_j) | ),    G = 16,

q the row's function of its real inputs x_j (all of them: T, R, F, concentrations, permeabilities, areas...).
For a root V* of I(V; x) = 0 the same sum is taken through the implicit function:
floor = G u ( |V*| + sum_j |I(V*; x_j(1+u)) - I(V*)| / |dI/dV| ). FLOOR_FACTOR = 10 as in FR-2's references.
The floor is a statement about float64 evaluation; it is not an estimate of the engine's time-stepping error,
which the tolerance covers.

Kinds: ``abs`` (|engine - reference| <= band), ``sign`` (sign equal, compared only when |aux| > band),
``exact_zero`` (engine value must be exactly 0), ``flag`` (equal), ``info`` (not compared).
"""

from __future__ import annotations

from decimal import Decimal

from .exact import U64, fmt

G_OPS = 16
FLOOR_FACTOR = 10


def floor_closed(fn, p, keys=None):
    """Floor of q = fn(p) by input perturbation; p is a dict of Decimals (other entries ignored)."""
    q0 = fn(p)
    tot = abs(q0)
    for k, v in p.items():
        if not isinstance(v, Decimal) or v == 0 or (keys is not None and k not in keys):
            continue
        q = dict(p)
        q[k] = v * (1 + U64)
        tot += abs(fn(q) - q0)
    return G_OPS * U64 * tot


def floor_root(resid, dresid, root, p):
    tot = abs(root)
    d = abs(dresid(root, p))
    for k, v in p.items():
        if not isinstance(v, Decimal) or v == 0:
            continue
        q = dict(p)
        q[k] = v * (1 + U64)
        tot += abs(resid(root, q) - resid(root, p)) / d
    return G_OPS * U64 * tot


class Rows:
    def __init__(self):
        self.meta, self.values, self.floors, self.aux, self.tol_row = {}, {}, {}, {}, {}

    def family(self, fam, claim, quantity, unit, kind, tol_abs=0.0, tol_rel=0.0, tol_source="", note=""):
        assert fam not in self.meta, fam
        self.meta[fam] = {"claim": claim, "quantity": quantity, "unit": unit, "kind": kind,
                          "tol_abs": float(tol_abs), "tol_rel": float(tol_rel), "tol_source": tol_source,
                          "note": note}
        self.values[fam], self.floors[fam], self.aux[fam], self.tol_row[fam] = {}, {}, {}, {}

    def add(self, fam, key, value, floor=Decimal(0), aux=None, tol_abs=None):
        kind = self.meta[fam]["kind"]
        if kind in ("sign",):
            self.values[fam][key] = str(int(value))
        elif kind == "flag":
            self.values[fam][key] = "true" if value else "false"
        elif kind == "exact_zero":
            assert value == 0
            self.values[fam][key] = "0"
        else:
            self.values[fam][key] = fmt(Decimal(value))
        floor = Decimal(floor)
        if kind == "abs" and floor == 0 and Decimal(value) != 0:
            floor = G_OPS * U64 * abs(Decimal(value))      # rows without a sensitivity analysis: G u |q|
        self.floors[fam][key] = float(floor)
        if aux is not None:
            self.aux[fam][key] = fmt(Decimal(aux)) if isinstance(aux, Decimal) else aux
        if tol_abs is not None:
            self.tol_row[fam][key] = float(tol_abs)

    def band(self, fam, key):
        m = self.meta[fam]
        if m["kind"] in ("info", "flag", "exact_zero"):
            return 0.0
        v = Decimal(self.aux[fam][key]) if m["kind"] == "sign" else Decimal(self.values[fam][key])
        tol_abs = self.tol_row[fam].get(key, m["tol_abs"])
        tol = tol_abs + m["tol_rel"] * float(abs(v)) if m["kind"] != "sign" else tol_abs
        return max(tol, FLOOR_FACTOR * self.floors[fam][key])

    def bands_json(self):
        out = {}
        for fam, m in self.meta.items():
            rows = {}
            for key in self.values[fam]:
                rows[key] = {"floor": self.floors[fam][key], "band": self.band(fam, key)}
            out[fam] = dict(m, rows=rows)
        return out

    def values_json(self):
        out = {}
        for fam in self.meta:
            out[fam] = {"values": self.values[fam]}
            if self.aux[fam]:
                out[fam]["aux"] = self.aux[fam]
        return out
