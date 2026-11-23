"""Recompute the checks of the GJ-L1 linear references (validation/gap_junction_tissue/references).

Self-contained on purpose: the spec and the interface are read as data and the exact rational
solve is re-implemented here (a different elimination order from the generator's), so nothing
under validation/gap_junction_tissue/ is imported. About 0.1 s of checks (0.5 s for the file
under pytest, collection included); no world is compiled.
"""

from __future__ import annotations

import json
import math
from fractions import Fraction
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
REFS = ROOT / "validation" / "gap_junction_tissue" / "references"
SPEC = REFS / "spec" / "linear.json"
INTERFACE = REFS / "interface" / "linear.json"
TAG = "gj-linear-registered-2026-11-23"
UNIT_ROUNDOFF = Fraction(1, 2**53)
CEILING = Fraction(1, 10**13)
READINGS = ("binary64", "decimal", "simplest")


@pytest.fixture(scope="module")
def data():
    text = SPEC.read_text()
    spec = json.loads(text)
    spec_decimal = json.loads(text, parse_float=Fraction, parse_int=Fraction)
    refs = json.loads(INTERFACE.read_text())
    return spec, spec_decimal, refs


def _simplest(x: float) -> Fraction:
    """Smallest-denominator rational that rounds to x (searched directly)."""
    for q in range(1, 10**4):
        p = round(Fraction(x) * q)
        if float(Fraction(p, q)) == x:
            return Fraction(p, q)
    return Fraction(x)


def _number(as_float, as_decimal, reading):
    return {"binary64": Fraction(as_float), "decimal": Fraction(as_decimal), "simplest": _simplest(as_float)}[reading]


def _problem(decl, decl_decimal, reading):
    cells = [
        (c["id"], _number(c["size"], d["size"], reading), _number(c["unloaded"], d["unloaded"], reading))
        for c, d in zip(decl["cells"], decl_decimal["cells"])
    ]
    junctions = [(j["a"], j["b"], _number(j["g"], d["g"], reading)) for j, d in zip(decl["junctions"], decl_decimal["junctions"])]
    probes = [
        (p["cell"], _number(p["held"], d["held"], reading), _number(p["g"], d["g"], reading))
        for p, d in zip(decl["probes"], decl_decimal["probes"])
    ]
    return cells, junctions, probes


def _solve(cells, junctions, probes):
    """Exact steady state of model.balance (units of G_eq,1), with an exact zero-residual check."""
    ids = [c[0] for c in cells]
    pos = {cid: i for i, cid in enumerate(ids)}
    n = len(ids)
    m = [[Fraction(0)] * (n + 1) for _ in range(n)]
    for i, (_, size, unloaded) in enumerate(cells):
        m[i][i] += size
        m[i][n] += size * unloaded
    for a, b, g in junctions:
        i, j = pos[a], pos[b]
        m[i][i] += g
        m[j][j] += g
        m[i][j] -= g
        m[j][i] -= g
    for cell, held, g in probes:
        m[pos[cell]][pos[cell]] += g
        m[pos[cell]][n] += g * held
    for col in range(n):  # forward elimination, then back substitution
        for r in range(col + 1, n):
            if m[r][col]:
                f = m[r][col] / m[col][col]
                m[r] = [x - f * y for x, y in zip(m[r], m[col])]
    x = [Fraction(0)] * n
    for i in reversed(range(n)):
        x[i] = (m[i][n] - sum(m[i][j] * x[j] for j in range(i + 1, n))) / m[i][i]
    conc = dict(zip(ids, x))
    residual = {cid: size * (unloaded - conc[cid]) for cid, size, unloaded in cells}
    for a, b, g in junctions:
        residual[a] += g * (conc[b] - conc[a])
        residual[b] += g * (conc[a] - conc[b])
    for cell, held, g in probes:
        residual[cell] += g * (held - conc[cell])
    assert not any(residual.values())
    return conc


def _correctly_rounded(f: float, x: Fraction) -> bool:
    error = abs(Fraction(f) - x)
    return all(abs(Fraction(math.nextafter(f, d)) - x) >= error for d in (math.inf, -math.inf))


def _within(f: float, x: Fraction, bound: float) -> bool:
    return abs(Fraction(f) - x) <= Fraction(bound) * abs(x)


def _chain(n: int):
    ids = [f"c{k}" for k in range(n)]
    return ids, [(cid, Fraction(1), Fraction(1)) for cid in ids], [(a, b, Fraction(1)) for a, b in zip(ids, ids[1:])]


def _chain_line(n: int):
    """G_eq,n and the intercept from the full balance under two port loads (held 0.5 and 2, G_p = 1)."""
    ids, cells, junctions = _chain(n)
    pts = []
    for held in (Fraction(1, 2), Fraction(2)):
        c = _solve(cells, junctions, [(ids[-1], held, Fraction(1))])[ids[-1]]
        pts.append((c - held, c))  # (i_exit leaving the port, port concentration)
    (i1, c1), (i2, c2) = pts
    g = -(i2 - i1) / (c2 - c1)
    return g, c1 + i1 / g


def test_interface_schema(data):
    spec, _, refs = data
    assert list(refs) == list(spec["interface"]["keys"])
    assert refs["format"] == spec["interface"]["format"] == "gap_junction_tissue.linear_references@1"
    assert refs["registration"] == TAG
    assert list(refs["networks"]) == list(spec["networks"])
    assert list(refs["chains"]) == [str(n) for n in spec["chains"]]
    assert list(refs["limits"]) == ["figure3", "figure5b", "chain"]
    assert list(refs["printed_recursion"]) == ["literal", "resistance_form"]


def test_networks_exact(data):
    spec, spec_decimal, refs = data
    for nid, decl in spec["networks"].items():
        entry = refs["networks"][nid]
        assert list(entry) == ["declaration", "concentrations", "accuracy_rel", "method"]
        assert entry["declaration"] == decl
        assert json.dumps(entry["declaration"]) == json.dumps(decl)
        assert list(entry["concentrations"]) == [c["id"] for c in decl["cells"]]
        bound = entry["accuracy_rel"]
        assert 0 < Fraction(bound) <= CEILING
        for reading in READINGS:
            exact = _solve(*_problem(decl, spec_decimal["networks"][nid], reading))
            for cid, f in entry["concentrations"].items():
                assert _within(f, exact[cid], bound), (nid, reading, cid)
                if reading == "binary64":
                    assert f == float(exact[cid]) and _correctly_rounded(f, exact[cid]), (nid, cid)


def test_chains_from_the_balance(data):
    spec, spec_decimal, refs = data
    lines = {}
    for n in spec["chains"]:
        entry = refs["chains"][str(n)]
        g_balance, u_balance = _chain_line(n)
        g, u = Fraction(1), Fraction(1)  # Norton recursion from the sealed cell
        for _ in range(n - 1):
            g = 1 / (1 / g + 1) + 1
        assert (g, u) == (g_balance, u_balance)
        assert g == Fraction(_fib(2 * n), _fib(2 * n - 1))
        lines[n] = (g, u)
        assert 0 < Fraction(entry["accuracy_rel"]) <= CEILING
        for key, x in (("g_eq_ratio", g), ("intercept", u)):
            assert entry[key] == float(x) and _correctly_rounded(entry[key], x)
            assert _within(entry[key], x, entry["accuracy_rel"])
    # The figure8 networks (the chain with a load at its port) lie on their chain's line.
    for nid, decl in spec["networks"].items():
        if not nid.startswith("figure8-"):
            continue
        cells, junctions, probes = _problem(decl, spec_decimal["networks"][nid], "binary64")
        assert (cells, junctions) == _chain(len(cells))[1:]
        (port, held, g_probe), = probes
        g, u = lines[len(cells)]
        c = _solve(cells, junctions, probes)[port]
        assert c == u - g_probe * (c - held) / g


def _fib(k: int) -> int:
    a, b = 0, 1
    for _ in range(k):
        a, b = b, a + b
    return a


def test_limits(data):
    spec, spec_decimal, refs = data
    limits = refs["limits"]
    for key, prefix, expected_pair in (
        ("figure3", "figure3-", [(5, 1), (10, 1)]),
        ("figure5b", "figure5-lumped-", [(10, 1), (5, Fraction(4, 3))]),
    ):
        pairs = {
            tuple(_problem(d, spec_decimal["networks"][nid], "simplest")[0])
            for nid, d in spec["networks"].items()
            if nid.startswith(prefix)
        }
        assert len(pairs) == 1
        (pair,) = pairs
        assert [(u, s) for _, s, u in pair] == expected_pair
        (ida, sa, ua), (idb, sb, ub) = pair
        limit = (sa * ua + sb * ub) / (sa + sb)
        for g in (Fraction(10**9), Fraction(10**18)):  # approach from the exact solution
            conc = _solve(list(pair), [(ida, idb, g)], [])
            assert all(abs(c - limit) <= 10 * abs(ua - ub) / g for c in conc.values())
        assert limits[key] == float(limit) and _correctly_rounded(limits[key], limit)
    bits = 256
    s = math.isqrt(5 << (2 * bits))
    lo, hi = Fraction((1 << bits) + s, 1 << (bits + 1)), Fraction((1 << bits) + s + 1, 1 << (bits + 1))
    assert lo * lo - lo - 1 < 0 < hi * hi - hi - 1
    assert limits["chain"] == float(lo) == float(hi)
    assert _correctly_rounded(limits["chain"], lo) and _correctly_rounded(limits["chain"], hi)


def test_printed_recursion(data):
    _, _, refs = data
    literal, resistance = [Fraction(1)], [Fraction(1)]
    while len(literal) < 10:
        literal.append(1 / ((1 / (1 / literal[-1] + 1)) + literal[-1]))
        resistance.append(1 / (1 / resistance[-1] + 1) + resistance[-1])
    for key, values in (("literal", literal), ("resistance_form", resistance)):
        assert len(refs["printed_recursion"][key]) == 10
        for f, x in zip(refs["printed_recursion"][key], values):
            assert f == float(x) and _correctly_rounded(f, x)
