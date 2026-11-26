"""Recompute the checks of the gap-junction references (validation/gap_junction_tissue/references).

Task A, the GJ-L1 linear model: the exact rational solve is re-implemented here (a different
elimination order from the generator's); about 0.1 s. Task B, the "neither" threshold: the
interface's conditions, stage 1 and the line's two final ends, re-integrated with LSODA and an
independent right-hand side; about 1-2 s, nearly all the line.

Self-contained on purpose: the specs and the interfaces are read as data, so nothing under
validation/gap_junction_tissue/ is imported. No world is compiled. The whole file takes about
2.5 s under pytest.
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


# --------------------------------------------------------------------------- the "neither" threshold (task B)

NEITHER_SPEC = REFS / "spec" / "neither.json"
NEITHER = REFS / "interface" / "neither.json"
NEITHER_TAG = "gj-neither-registered-2026-11-23"
NEITHER_CELLS = {"line": 25, "field": 625}


@pytest.fixture(scope="module")
def neither():
    return json.loads(NEITHER_SPEC.read_text()), json.loads(NEITHER.read_text())


def _cell_rates(constants):
    """model.equations for one cell, written out independently of the generator."""
    c = constants
    coef = [math.comb(6, i) * c["l"][i] for i in range(7)]

    def rates(u, m, z):
        ru, rm = (z / c["K_u"]) ** c["n_u"], (z / c["K_m"]) ** c["n_m"]
        x = u / c["x0"]
        poly = coef[6]
        for a in coef[5::-1]:  # Horner: sum_i C(6, i) l_i x^i
            poly = poly * x + a
        bound = poly / (1 + x) ** 6
        return (
            c["g_u"] * (1 + c["lambda_u"] * ru) / (1 + ru) - c["k_u"] * u,
            c["g_m"] * (1 + c["lambda_m"] * rm) / (1 + rm) - c["k_m"] * m,
            c["g_z"] * m * bound - c["k_z"] * z,
        )

    return rates


def test_neither_schema_and_echo(neither):
    spec, refs = neither
    assert list(refs) == list(spec["interface"]["keys"])
    assert refs["format"] == spec["interface"]["format"] == "gap_junction_tissue.neither_references@1"
    assert refs["registration"] == NEITHER_TAG
    assert json.dumps(refs["model"]["constants"]) == json.dumps(spec["model"]["constants"])
    assert refs["model"]["seeds"] == {k: spec["model"]["seeds"][k] for k in ("tumor", "healthy")}
    assert list(refs["model"]) == ["constants", "seeds"]
    assert {k: list(v) for k, v in refs["stage1"].items()} == {"tumor": ["u", "m", "z"], "healthy": ["u", "m", "z"]}
    assert "line" in refs["geometries"] and set(refs["geometries"]) <= set(NEITHER_CELLS)
    for geometry in refs["geometries"].values():
        assert list(geometry) == ["bracket", "points", "tighter", "method"]
        for point in geometry["points"]:
            assert list(point) == ["d", "normalized", "epithelial_cells", "min_margin", "max_row_spread"]


def test_neither_conditions(neither):
    spec, refs = neither
    first, last = spec["search"]["bracket"]
    for name, geometry in refs["geometries"].items():
        lo, hi = geometry["bracket"]
        assert first < lo < hi < last
        assert Fraction(hi) <= Fraction(1001, 1000) * Fraction(lo)  # hi <= (1 + 0.001) lo
        points = geometry["points"]
        ds = [p["d"] for p in points]
        assert ds == sorted(set(ds))
        outcome = {p["d"]: p["normalized"] for p in points}
        assert outcome[first] is False and outcome[last] is True
        assert [p["normalized"] for p in points] == sorted(p["normalized"] for p in points)  # monotone in d
        assert max(d for d, o in outcome.items() if not o) == lo and min(d for d, o in outcome.items() if o) == hi
        assert geometry["tighter"] == {"factor": 10, "lo_normalized": False, "hi_normalized": True}
        for p in points:
            assert p["normalized"] == (p["min_margin"] > 0 and p["max_row_spread"] <= 2)
            assert (p["epithelial_cells"] == NEITHER_CELLS[name]) == (p["min_margin"] > 0)
            assert name != "line" or p["max_row_spread"] == 0.0


def test_neither_stage1_and_line_ends(neither):
    """Stage 1, and the line's two final ends, recomputed with ODEPACK's LSODA (scipy odeint, banded
    Jacobian by differences); the generator uses DOP853 and BDF. About 1.1 s, nearly all the line."""
    np = pytest.importorskip("numpy")
    integrate = pytest.importorskip("scipy.integrate")
    spec, refs = neither
    rates = _cell_rates(spec["model"]["constants"])
    end = {}
    for name in ("tumor", "healthy"):
        seed = spec["model"]["seeds"][name]
        end[name] = integrate.odeint(
            lambda t, y: rates(*y), [seed[k] for k in "umz"], [0.0, 500.0], tfirst=True, rtol=1e-11, atol=1e-14,
            mxstep=10**6,
        )[-1]
        expected = np.array([refs["stage1"][name][k] for k in "umz"])
        assert np.all(np.abs(end[name] - expected) <= 1e-8 * np.abs(expected))
    start = np.concatenate([end["tumor"] if k < 6 else end["healthy"] for k in range(25)])
    g_over_v = spec["model"]["constants"]["g_over_v_per_d"]
    for d, normalized in zip(refs["geometries"]["line"]["bracket"], (False, True)):

        def fun(t, y, gv=g_over_v * d):
            out = np.empty_like(y)
            out[0::3], out[1::3], out[2::3] = rates(y[0::3], y[1::3], y[2::3])
            flux = gv * (y[3::3] - y[0:-3:3])  # junction c_k - c_(k+1): G/V (u_k - u_(k+1)) leaves c_k
            out[0:-3:3] += flux
            out[3::3] -= flux
            return out

        y = integrate.odeint(
            fun, start, [0.0, 20000.0], tfirst=True, ml=3, mu=3, rtol=1e-9, atol=1e-12, mxstep=10**6
        )[-1]
        assert bool(np.all(y[0::3] > y[1::3] + 2)) is normalized, d
