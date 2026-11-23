#!/usr/bin/env python3
"""Exact, code-blind references for GJ-L1, the linear model of the gap-junction
cancer replication.

Inputs, and the only inputs: the preprint (J. Grodstein, J. Mathews and
M. Levin, "Membrane voltage and connexin expression work together to enhance
tumor growth and metastasis in cancer", bioRxiv 10.64898/2026.09.02.748840 v1,
CC-BY 4.0) and the registered specification ``spec/linear.json`` read from the
tag ``TAG``. Every value is solved exactly in rational arithmetic
(``fractions.Fraction``), checked exactly, and rounded once to binary64.
Standard library only; nothing here imports the engine or any other module of
this folder's parent package.

Regenerate from anywhere (the default reads the spec with ``git show TAG:...``):

    python -I validation/gap_junction_tissue/references/linear_reference.py
    python -I validation/gap_junction_tissue/references/linear_reference.py --check

``--check`` recomputes and compares with the committed interface byte for byte.
README.md in this folder holds the derivations.
"""

from __future__ import annotations

import argparse
import json
import math
import subprocess
import sys
from fractions import Fraction
from pathlib import Path

TAG = "gj-linear-registered-2026-11-23"
SPEC_FORMAT = "gap_junction_tissue.linear_spec@1"
FORMAT = "gap_junction_tissue.linear_references@1"
SPEC_REL = "validation/gap_junction_tissue/references/spec/linear.json"
HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
INTERFACE = HERE / "interface" / "linear.json"

UNIT_ROUNDOFF = Fraction(1, 2**53)  # binary64, round to nearest
ACCURACY_CEILING = Fraction(1, 10**13)  # spec: every accuracy_rel at most 1e-13
READINGS = ("binary64", "decimal", "simplest")

# model.chain: a straight chain of equal cells (size 1), every junction
# G_GJ = G_eq,1, every cell unloaded 1; conductances in units of G_eq,1.
CHAIN_SIZE = Fraction(1)
CHAIN_G_GJ = Fraction(1)
CHAIN_UNLOADED = Fraction(1)
# Port loads (held, G_probe) for the full-balance derivation of the chains:
# the figure8 networks' two loads, plus a third that must fall on the same line.
CHAIN_LOADS = ((Fraction(1, 2), Fraction(1)), (Fraction(2), Fraction(1)), (Fraction(0), Fraction(3)))

# Clauses of the registered texts that the derivations below rest on.
REQUIRED_CLAUSES = {
    ("model", "balance"): (
        "V_i dc_i/dt = G_eq,i (u_i - c_i) + sum over its junctions of G_GJ (c_j - c_i)"
        " + sum over its probes of G_probe (h_p - c_i)",
        "G_eq,i = size_i G_eq,1",
    ),
    ("model", "chain"): (
        "a straight chain of n equal cells, every junction G_GJ = G_eq,1, unloaded 1,"
        " sealed at its first cell and seen from its last (the port)",
        "u_n - i_exit / G_eq,n",
        "i_exit leaves the port",
    ),
    ("requested", "limits"): (
        "figure3: the common limit of Figure 3b's two cells (unloaded 5 and 10, equal sizes)",
        "figure5b: the same for Figure 5b's pair (A unloaded 10, size 1; B unloaded 5, size 4/3)",
        "chain: G_eq,n / G_eq,1 as n grows, at G_GJ = G_eq,1",
    ),
    ("requested", "printed_recursion"): (
        "G_eq,n+1 = 1 / [(G_eq,n^-1 + G_GJ^-1)^-1 + G_eq,n]",
        "at G_GJ = G_eq,1 = 1 for n = 1 to 10",
        "G_eq,n+1 = (G_eq,n^-1 + G_GJ^-1)^-1 + G_eq,n",
    ),
}
INTERFACE_KEYS = ["format", "registration", "networks", "chains", "limits", "printed_recursion"]
PRINTED_COUNT = 10  # [G_eq,1 .. G_eq,10]


# --------------------------------------------------------------------------- input


def read_spec_text(spec_file: str | None) -> str:
    if spec_file is not None:
        return Path(spec_file).read_text()
    out = subprocess.run(
        ["git", "-C", str(REPO), "show", f"{TAG}:{SPEC_REL}"],
        check=True,
        capture_output=True,
        text=True,
    )
    return out.stdout


def validate_spec(spec: dict) -> None:
    if spec.get("format") != SPEC_FORMAT:
        raise ValueError(f"spec format {spec.get('format')!r}, expected {SPEC_FORMAT!r}")
    for (section, key), clauses in REQUIRED_CLAUSES.items():
        text = spec[section][key]
        for clause in clauses:
            if clause not in text:
                raise ValueError(f"spec {section}.{key} no longer contains {clause!r}")
    interface = spec["interface"]
    if interface["format"] != FORMAT or list(interface["keys"]) != INTERFACE_KEYS:
        raise ValueError("spec interface differs from the one these references implement")
    for nid, net in spec["networks"].items():
        if set(net) != {"cells", "junctions", "probes"}:
            raise ValueError(f"{nid}: unexpected network keys {sorted(net)}")
        for cell in net["cells"]:
            if set(cell) != {"id", "unloaded", "size"}:
                raise ValueError(f"{nid}: unexpected cell keys {sorted(cell)}")
        for junction in net["junctions"]:
            if set(junction) != {"id", "a", "b", "g"}:
                raise ValueError(f"{nid}: unexpected junction keys {sorted(junction)}")
        for probe in net["probes"]:
            if set(probe) != {"id", "cell", "held", "g"}:
                raise ValueError(f"{nid}: unexpected probe keys {sorted(probe)}")


def simplest_rational_rounding_to(x: float) -> Fraction:
    """First continued-fraction convergent of x's exact value that rounds back to x."""
    exact = Fraction(x)
    num, den = exact.numerator, exact.denominator
    h_prev, h = 0, 1
    k_prev, k = 1, 0
    while den:
        q, rem = divmod(num, den)
        h_prev, h = h, q * h + h_prev
        k_prev, k = k, q * k + k_prev
        candidate = Fraction(h, k)
        if float(candidate) == x:
            return candidate
        num, den = den, rem
    return exact


def read_number(as_float, as_decimal, reading: str) -> Fraction:
    """One declared JSON number under a reading of it.

    binary64: the exact value of the float any JSON reader gets (the primary reading);
    decimal: the decimal literal exactly; simplest: the simplest rational that
    rounds to the same float (4/3 for 1.3333333333333333).
    """
    if reading == "binary64":
        return Fraction(as_float)
    if reading == "decimal":
        return Fraction(as_decimal)
    if reading == "simplest":
        return simplest_rational_rounding_to(float(as_float))
    raise ValueError(reading)


def inexact_literals(decl: dict, decl_decimal: dict) -> list[str]:
    """Declared numbers whose three readings are not all equal."""
    found = set()
    for kind, fields in (("cells", ("size", "unloaded")), ("junctions", ("g",)), ("probes", ("held", "g"))):
        for item, item_decimal in zip(decl[kind], decl_decimal[kind]):
            for field in fields:
                values = {read_number(item[field], item_decimal[field], r) for r in READINGS}
                if len(values) > 1:
                    found.add(repr(item[field]))
    return sorted(found)


def network_problem(decl: dict, decl_decimal: dict, reading: str):
    cells = [
        (c["id"], read_number(c["size"], d["size"], reading), read_number(c["unloaded"], d["unloaded"], reading))
        for c, d in zip(decl["cells"], decl_decimal["cells"])
    ]
    junctions = [
        (j["a"], j["b"], read_number(j["g"], d["g"], reading))
        for j, d in zip(decl["junctions"], decl_decimal["junctions"])
    ]
    probes = [
        (p["cell"], read_number(p["held"], d["held"], reading), read_number(p["g"], d["g"], reading))
        for p, d in zip(decl["probes"], decl_decimal["probes"])
    ]
    return cells, junctions, probes


# --------------------------------------------------------------------------- exact steady state


def balance_residuals(cells, junctions, probes, conc) -> dict:
    """Right side of model.balance for every cell (units of G_eq,1 x concentration)."""
    residual = {cid: size * (unloaded - conc[cid]) for cid, size, unloaded in cells}
    for left, right, g in junctions:
        flow = g * (conc[right] - conc[left])  # into `left`, out of `right`
        residual[left] += flow
        residual[right] -= flow
    for cell, held, g in probes:
        residual[cell] += g * (held - conc[cell])
    return residual


def steady_state(cells, junctions, probes) -> dict:
    """Exact steady state of model.balance by Gauss-Jordan elimination over the rationals.

    The matrix is size_i + sum(g) + sum(G_probe) on the diagonal and -g off it:
    strictly diagonally dominant (every size_i > 0), hence nonsingular, and no
    pivot vanishes without pivoting. The solution is checked by exact zero residuals.
    """
    ids = [cid for cid, _, _ in cells]
    index = {cid: k for k, cid in enumerate(ids)}
    if len(index) != len(ids):
        raise ValueError("duplicate cell id")
    n = len(ids)
    rows = [[Fraction(0)] * (n + 1) for _ in range(n)]
    for k, (_, size, unloaded) in enumerate(cells):
        if size <= 0:
            raise ValueError("size must be positive")
        rows[k][k] += size
        rows[k][n] += size * unloaded
    for left, right, g in junctions:
        i, j = index[left], index[right]
        if i == j or g <= 0:
            raise ValueError("bad junction")
        rows[i][i] += g
        rows[j][j] += g
        rows[i][j] -= g
        rows[j][i] -= g
    for cell, held, g in probes:
        i = index[cell]
        if g <= 0:
            raise ValueError("bad probe")
        rows[i][i] += g
        rows[i][n] += g * held
    for col in range(n):
        pivot = rows[col][col]
        if pivot == 0:
            raise ArithmeticError("zero pivot")
        for r in range(n):
            if r != col and rows[r][col]:
                factor = rows[r][col] / pivot
                rows[r] = [a - factor * b for a, b in zip(rows[r], rows[col])]
    conc = {ids[k]: rows[k][n] / rows[k][k] for k in range(n)}
    if any(balance_residuals(cells, junctions, probes, conc).values()):
        raise ArithmeticError("nonzero exact residual")
    return conc


# --------------------------------------------------------------------------- independent closed forms


def norton_tree(cells, junctions, probes) -> dict:
    """The preprint's black-box reduction (eq. 1, Fig. 7) on any tree of junctions.

    Fold every subtree, leaves first, into its Norton pair (G, U) at its root;
    seen through the junction g to the parent it is the conductance
    (G^-1 + g^-1)^-1 with source U. Solve the root, then unfold downwards.
    """
    size = {cid: s for cid, s, _ in cells}
    nbrs = {cid: [] for cid in size}
    for left, right, g in junctions:
        nbrs[left].append((right, g))
        nbrs[right].append((left, g))
    if len(junctions) != len(cells) - 1:
        raise ValueError("not a tree")
    g_sum = dict(size)  # total conductance attached at each cell (own decay + probes + folded children)
    gu_sum = {cid: s * u for cid, s, u in cells}
    for cell, held, g in probes:
        g_sum[cell] += g
        gu_sum[cell] += g * held
    root = cells[0][0]
    parent, parent_g, order, stack = {root: None}, {}, [], [root]
    while stack:
        v = stack.pop()
        order.append(v)
        for w, g in nbrs[v]:
            if w == parent[v]:
                continue
            if w in parent:
                raise ValueError("not a tree")
            parent[w], parent_g[w] = v, g
            stack.append(w)
    if len(order) != len(cells):
        raise ValueError("not connected")
    for v in reversed(order):
        if parent[v] is not None:
            through = 1 / (1 / g_sum[v] + 1 / parent_g[v])
            g_sum[parent[v]] += through
            gu_sum[parent[v]] += through * (gu_sum[v] / g_sum[v])
    conc = {root: gu_sum[root] / g_sum[root]}
    for v in order:
        if parent[v] is not None:
            conc[v] = (gu_sum[v] + parent_g[v] * conc[parent[v]]) / (g_sum[v] + parent_g[v])
    return conc


def pair_eq2(cells, junctions, probes) -> dict | None:
    """The preprint's eq. (2), A line, and its mirror for B (G_rel,X^-1 = G_GJ / G_eq,X)."""
    if len(cells) != 2 or len(junctions) != 1 or probes:
        return None
    (ida, sa, ua), (idb, sb, ub) = cells
    left, right, g = junctions[0]
    if {left, right} != {ida, idb}:
        return None
    ra, rb = g / sa, g / sb
    den = 1 + ra + rb
    return {ida: ((1 + rb) * ua + ra * ub) / den, idb: (rb * ua + (1 + ra) * ub) / den}


def fibonacci(k: int) -> int:
    a, b = 0, 1
    for _ in range(k):
        a, b = b, a + b
    return a


def uniform_chain_port_load(cells, junctions, probes):
    """(n, u, held, G_probe) when the network is model.chain's chain with one load at its port."""
    ids = [cid for cid, _, _ in cells]
    n = len(ids)
    if len(probes) != 1 or probes[0][0] != ids[-1]:
        return None
    if any(s != CHAIN_SIZE or u != CHAIN_UNLOADED for _, s, u in cells):
        return None
    if [(a, b) for a, b, _ in junctions] != list(zip(ids, ids[1:])):
        return None
    if any(g != CHAIN_G_GJ for _, _, g in junctions):
        return None
    _, held, g_probe = probes[0]
    return n, CHAIN_UNLOADED, held, g_probe


def uniform_chain_closed_form(cells, junctions, probes) -> dict | None:
    """c_k = u + F_(2k+1) e_0 with e_0 = G_p (h - u) / (F_2n + G_p F_(2n-1)) (README, section 4)."""
    found = uniform_chain_port_load(cells, junctions, probes)
    if found is None:
        return None
    n, u, held, g_probe = found
    e0 = g_probe * (held - u) / (fibonacci(2 * n) + g_probe * fibonacci(2 * n - 1))
    return {cid: u + fibonacci(2 * k + 1) * e0 for k, (cid, _, _) in enumerate(cells)}


# --------------------------------------------------------------------------- chains


def chain_network(n: int):
    ids = [f"c{k}" for k in range(n)]
    cells = [(cid, CHAIN_SIZE, CHAIN_UNLOADED) for cid in ids]
    junctions = [(a, b, CHAIN_G_GJ) for a, b in zip(ids, ids[1:])]
    return ids, cells, junctions


def chain_by_circuit(n: int):
    """Norton recursion from the sealed cell: add one cell (own G_eq,1, source u) at the port."""
    g_eq1 = CHAIN_SIZE
    g, u = g_eq1, CHAIN_UNLOADED
    for _ in range(n - 1):
        through = 1 / (1 / g + 1 / CHAIN_G_GJ)
        g, u = through + g_eq1, (through * u + g_eq1 * CHAIN_UNLOADED) / (through + g_eq1)
    return g, u


def chain_by_balance(n: int):
    """Full balance of the n-cell chain with a load at the port, solved exactly per load.

    i_exit = G_probe (c_port - held) leaves the port; two loads fix the line
    c_port = U - i_exit / G; the third must lie on it; the unloaded chain gives U directly.
    """
    ids, cells, junctions = chain_network(n)
    port = ids[-1]
    points = []
    for held, g_probe in CHAIN_LOADS:
        conc = steady_state(cells, junctions, [(port, held, g_probe)])
        points.append((g_probe * (conc[port] - held), conc[port]))
    (i1, c1), (i2, c2), (i3, c3) = points
    g = -(i2 - i1) / (c2 - c1)
    u = c1 + i1 / g
    if c3 != u - i3 / g:
        raise ArithmeticError("port response not linear")
    if steady_state(cells, junctions, [])[port] != u:
        raise ArithmeticError("open-circuit port value differs from the intercept")
    return g, u


def chain_closed_form(n: int):
    return Fraction(fibonacci(2 * n), fibonacci(2 * n - 1)), CHAIN_UNLOADED


# --------------------------------------------------------------------------- limits and printed recursion


def pair_common_limit(cells) -> Fraction:
    """Common limit as G_GJ grows: the size-weighted mean, proved via the exact identity
    c_X(g) - L = s_A s_B (u_X - L) / (s_A s_B + g (s_A + s_B)), checked at five g."""
    (ida, sa, ua), (idb, sb, ub) = cells
    total = sa + sb
    limit = (sa * ua + sb * ub) / total
    for g in (Fraction(1, 2), Fraction(1), Fraction(10), Fraction(10**6), Fraction(10**30)):
        conc = steady_state(cells, [(ida, idb, g)], [])
        for cid, u in ((ida, ua), (idb, ub)):
            if conc[cid] - limit != sa * sb * (u - limit) / (sa * sb + g * total):
                raise ArithmeticError("pair identity fails")
    return limit


def golden_ratio_bracket(bits: int = 256):
    """Rational lo < phi < hi from an integer square root; phi = (1 + sqrt 5) / 2."""
    s = math.isqrt(5 << (2 * bits))  # floor(sqrt(5) 2^bits); 5 is not a square, so strict
    lo = Fraction((1 << bits) + s, 1 << (bits + 1))
    hi = Fraction((1 << bits) + s + 1, 1 << (bits + 1))
    if not (lo * lo - lo - 1 < 0 < hi * hi - hi - 1):
        raise ArithmeticError("bracket does not hold the positive root of G^2 - G - 1")
    return lo, hi


def printed_literal(count: int):
    seq = [Fraction(1)]
    while len(seq) < count:
        g = seq[-1]
        seq.append(1 / (1 / (1 / g + 1 / CHAIN_G_GJ) + g))
    return seq


def printed_resistance_form(count: int):
    seq = [Fraction(1)]
    while len(seq) < count:
        g = seq[-1]
        seq.append(1 / (1 / g + 1 / CHAIN_G_GJ) + g)
    return seq


# --------------------------------------------------------------------------- rounding and accuracy


def rounded(x: Fraction) -> float:
    """float(x), with an exact proof that no neighbouring binary64 is nearer to x."""
    f = float(x)
    error = abs(Fraction(f) - x)
    for neighbour in (math.nextafter(f, math.inf), math.nextafter(f, -math.inf)):
        if abs(Fraction(neighbour) - x) < error:
            raise ArithmeticError(f"float({x}) is not correctly rounded")
    return f


def rel_error(f: float, x: Fraction) -> Fraction:
    if x == 0:
        raise ZeroDivisionError("relative error of an exact zero")
    return abs(Fraction(f) - x) / abs(x)


def declared_bound(worst: Fraction) -> float:
    """The unit roundoff 2^-53 when it covers `worst`, else `worst` rounded up to two digits."""
    if worst <= UNIT_ROUNDOFF:
        return float(UNIT_ROUNDOFF)
    exponent = 0
    while worst * 10**exponent < 10:
        exponent += 1
    mantissa = math.ceil(worst * 10**exponent)
    while Fraction(float(Fraction(mantissa, 10**exponent))) < worst:
        mantissa += 1
    return float(Fraction(mantissa, 10**exponent))


# --------------------------------------------------------------------------- build


def fraction_text(x: Fraction) -> str:
    return str(x.numerator) if x.denominator == 1 else f"{x.numerator}/{x.denominator}"


def build(spec_text: str) -> tuple[dict, dict]:
    """Return (interface, exact) where exact holds the rationals and check notes for the README."""
    spec = json.loads(spec_text)
    spec_decimal = json.loads(spec_text, parse_float=Fraction, parse_int=Fraction)
    validate_spec(spec)
    exact = {"networks": {}, "chains": {}, "limits": {}, "printed_recursion": {}}

    networks = {}
    for nid, decl in spec["networks"].items():
        problems = {r: network_problem(decl, spec_decimal["networks"][nid], r) for r in READINGS}
        solutions = {r: steady_state(*problems[r]) for r in READINGS}
        primary = problems["binary64"]
        solution = solutions["binary64"]
        checks = ["the preprint's black-box (Norton) reduction on the junction tree"]
        if norton_tree(*primary) != solution:
            raise ArithmeticError(f"{nid}: Norton reduction disagrees")
        eq2 = pair_eq2(*primary)
        if eq2 is not None:
            if eq2 != solution:
                raise ArithmeticError(f"{nid}: eq. 2 disagrees")
            checks.append("eq. 2 (two cells)")
        chain_form = uniform_chain_closed_form(*primary)
        if chain_form is not None:
            if chain_form != solution:
                raise ArithmeticError(f"{nid}: uniform-chain closed form disagrees")
            checks.append("the uniform-chain closed form c_k = 1 + F(2k+1) e_0")
        concentrations = {cid: rounded(x) for cid, x in solution.items()}
        worst = max(rel_error(concentrations[cid], solutions[r][cid]) for r in READINGS for cid in solution)
        accuracy = declared_bound(worst)
        readings_differ = any(problems[r] != primary for r in READINGS)
        literals = inexact_literals(decl, spec_decimal["networks"][nid])
        if readings_differ != bool(literals):
            raise AssertionError(f"{nid}: reading bookkeeping inconsistent")
        spread = max(abs(solutions[r][cid] - solution[cid]) / abs(solution[cid]) for r in READINGS for cid in solution)
        method = (
            "exact rational steady state of model.balance (fractions.Fraction, Gauss-Jordan), every declared"
            " number taken as its exact binary64 value; every cell's balance residual is exactly zero; equal"
            " exactly to " + " and to ".join(checks) + "; each concentration is the correctly rounded binary64"
            " of its exact rational (checked exactly against both neighbours)"
        )
        if readings_differ:
            simplest = [fraction_text(simplest_rational_rounding_to(float(x))) for x in literals]
            method += (
                f"; the declared {', '.join(literals)} is not exact in binary64, so the network was also solved"
                " exactly with it read as its decimal literal and as the simplest rational that rounds to it"
                f" ({', '.join(simplest)}): the three exact solutions differ by at most {float(spread):.1e}"
                " relative, and accuracy_rel bounds the error against all three"
            )
        networks[nid] = {
            "declaration": decl,
            "concentrations": concentrations,
            "accuracy_rel": accuracy,
            "method": method,
        }
        exact["networks"][nid] = {
            "concentrations": {cid: fraction_text(x) for cid, x in solution.items()},
            "worst_rel_error": float(worst),
            "readings_differ": readings_differ,
            "spread": float(spread),
            "checks": checks,
        }

    chain_lines = {}
    chains = {}
    for n in spec["chains"]:
        g_circuit, u_circuit = chain_by_circuit(n)
        g_balance, u_balance = chain_by_balance(n)
        g_closed, u_closed = chain_closed_form(n)
        if not (g_circuit == g_balance == g_closed and u_circuit == u_balance == u_closed):
            raise ArithmeticError(f"chain {n}: derivations disagree")
        chain_lines[n] = (g_circuit, u_circuit)
        ratio, intercept = rounded(g_circuit), rounded(u_circuit)
        worst = max(rel_error(ratio, g_circuit), rel_error(intercept, u_circuit))
        chains[str(n)] = {
            "g_eq_ratio": ratio,
            "intercept": intercept,
            "accuracy_rel": declared_bound(worst),
            "method": (
                "exact rational: Norton recursion from the sealed cell, G_eq,k+1 = (G_eq,k^-1 + G_GJ^-1)^-1"
                " + G_eq,1 with the open-circuit concentration carried along; equal exactly to the full"
                " balance of the n-cell chain solved under port loads held 0.5 and 2 (G_probe = G_eq,1; a third"
                " load, held 0 and G_probe = 3 G_eq,1, lies on the same line; the unloaded chain gives the"
                f" intercept) and to F(2n)/F(2n-1); exactly G_eq,n/G_eq,1 = {fraction_text(g_circuit)},"
                f" intercept {fraction_text(u_circuit)}; correctly rounded"
            ),
        }
        exact["chains"][n] = {"g_eq_ratio": fraction_text(g_circuit), "intercept": fraction_text(u_circuit)}

    # Every figure8-style network (model.chain's chain with one load at its port) lies on its chain's line.
    on_line = 0
    for nid, decl in spec["networks"].items():
        cells, junctions, probes = network_problem(decl, spec_decimal["networks"][nid], "binary64")
        found = uniform_chain_port_load(cells, junctions, probes)
        if found is None:
            continue
        n, _, held, g_probe = found
        g, u = chain_lines.get(n) or chain_by_circuit(n)
        port = cells[-1][0]
        c_port = steady_state(cells, junctions, probes)[port]
        if c_port != u - g_probe * (c_port - held) / g:
            raise ArithmeticError(f"{nid}: port value off its chain's Norton line")
        on_line += 1
    exact["chains"]["networks_on_line"] = on_line

    figure3_cells = {
        tuple(network_problem(d, spec_decimal["networks"][nid], "simplest")[0])
        for nid, d in spec["networks"].items()
        if nid.startswith("figure3-")
    }
    figure5_cells = {
        tuple(network_problem(d, spec_decimal["networks"][nid], "simplest")[0])
        for nid, d in spec["networks"].items()
        if nid.startswith("figure5-lumped-")
    }
    if len(figure3_cells) != 1 or len(figure5_cells) != 1:
        raise ValueError("figure3 or figure5-lumped networks do not share one pair of cells")
    (pair3,), (pair5,) = figure3_cells, figure5_cells
    if [(u, s) for _, s, u in pair3] != [(5, 1), (10, 1)]:
        raise ValueError("figure3 pair differs from requested.limits")
    if [(u, s) for _, s, u in pair5] != [(10, 1), (5, Fraction(4, 3))]:
        raise ValueError("figure5b pair differs from requested.limits")
    limit3, limit5 = pair_common_limit(list(pair3)), pair_common_limit(list(pair5))
    phi_lo, phi_hi = golden_ratio_bracket()
    phi = rounded(phi_lo)
    if rounded(phi_hi) != phi:
        raise ArithmeticError("golden-ratio bracket straddles a rounding boundary")
    g_last = chain_by_circuit(spec["chains"][-1])[0]
    if not (g_last < phi_lo and phi_hi - g_last < Fraction(1, 10**6)):
        raise ArithmeticError("chain conductance does not approach the golden ratio from below")
    limits = {"figure3": rounded(limit3), "figure5b": rounded(limit5), "chain": phi}
    exact["limits"] = {
        "figure3": fraction_text(limit3),
        "figure5b": fraction_text(limit5),
        "chain": "(1 + sqrt 5)/2",
        "chain_bracket_width": float(phi_hi - phi_lo),
    }

    literal = printed_literal(PRINTED_COUNT)
    resistance = printed_resistance_form(PRINTED_COUNT)
    physical = [chain_by_circuit(n)[0] for n in range(1, PRINTED_COUNT + 1)]
    if any(physical[k] in (literal[k], resistance[k]) for k in range(2, PRINTED_COUNT)):
        raise ArithmeticError("a printed recursion matches the physical chain at n >= 3")
    printed = {"literal": [rounded(x) for x in literal], "resistance_form": [rounded(x) for x in resistance]}
    exact["printed_recursion"] = {
        "literal": [fraction_text(x) for x in literal],
        "resistance_form": [fraction_text(x) for x in resistance],
        "physical": [fraction_text(x) for x in physical],
    }

    for entry in list(networks.values()) + list(chains.values()):
        if not 0 < Fraction(entry["accuracy_rel"]) <= ACCURACY_CEILING:
            raise ArithmeticError("accuracy_rel out of range")

    interface = {
        "format": FORMAT,
        "registration": TAG,
        "networks": networks,
        "chains": chains,
        "limits": limits,
        "printed_recursion": printed,
    }
    return interface, exact


def render(interface: dict) -> str:
    return json.dumps(interface, indent=1) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--spec", help="read the spec from this file instead of git show TAG:...")
    parser.add_argument("--out", default=str(INTERFACE), help="interface file to write or check")
    parser.add_argument("--check", action="store_true", help="recompute and compare, write nothing")
    parser.add_argument("--exact", action="store_true", help="print the exact rationals and check notes")
    args = parser.parse_args(argv)
    interface, exact = build(read_spec_text(args.spec))
    text = render(interface)
    if args.exact:
        print(json.dumps(exact, indent=1))
    out = Path(args.out)
    if args.check:
        if not out.exists() or out.read_text() != text:
            print(f"MISMATCH: {out} differs from the recomputed references", file=sys.stderr)
            return 1
        print(f"ok: {out} matches the recomputed references")
        return 0
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text)
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
