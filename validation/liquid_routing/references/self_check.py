"""An independent check of the published files: structure, classes, values, plants and margins.

    python -B -P self_check.py --out DIR --inputs SPEC/inputs.json [--report FILE]

It imports nothing of `lrrefs` and shares no code with the writer. Each value is recomputed another way:

- flows: uniformization of each column of the propagator, written here from scratch; labels by superposition of columns;
- H_tot of a flow: one ideal mixing of finite portions from t = 0 to the output (the state function's other face);
- two wells: relaxation to the common level; D by logarithms of ratios; H_def by the J^2/W form;
- arm 4: RT (sum v x ln x - n ln(n/V));
- arm 5's and 6's holder heats: Clenshaw-Curtis on graded pieces, with closed-form levels (hyperbolic functions for arm 6);
- the plants: from these same second formulas.
"""

import argparse
import decimal
import hashlib
import json
import math
import os
import re
import sys
from decimal import Decimal as D

decimal.getcontext().prec = 100
VALUE = re.compile(r"^(0|-?\d\.\d{39}E[+-]\d+)$")
BOUND = re.compile(r"^(0|\d\.\d{2}E[+-]\d+)$")
TOP_KEYS = {"arm", "cases", "checks", "constants", "events", "inputs_sha256", "kind", "planted_series", "plants",
            "plants_reported", "provenance", "reported", "worlds"}
U = D(2) ** -53
ROWS = []


def note(name, residual, bound):
    ROWS.append({"name": name, "residual": f"{abs(residual):.6E}" if residual != 0 else "0", "bound": f"{bound:.3E}",
                 "passes": bool(abs(residual) <= bound)})


def fault(name, condition=False):
    ROWS.append({"name": name, "residual": "0" if condition else "1", "bound": "0", "passes": bool(condition)})


def ln(x):
    return x.ln()


def thermal(world):
    return D(float("6.02214076e23")) * D(float("1.380649e-23")) * D(world["temperature_K"]) / 1000


def xlog(x, y):
    return D(0) if x == 0 else x * y.ln()


def f_phi(r):
    return D(1) if r == 0 else r * r.ln() - r + 1


# ---- worlds, read again ------------------------------------------------------------------------------------------------

class W:
    def __init__(self, name, block):
        self.name, self.b = name, block
        self.rt = thermal(block)
        self.V = {k: D(v) for k, v in block["volumes_pL"].items()}
        self.n0 = {x: {k: D(v) for k, v in t.items()} for x, t in block["start_fmol"].items()}
        self.species = sorted(block["start_fmol"])
        self.nodes = sorted(self.V)
        self.links = [(s, t, D(sched[0][1])) for s, t, sched in block["links_pL_per_s"]]
        self.inlet = {i: {x: [(D(t), D(c)) for t, c in sched] for x, sched in table.items()}
                      for i, table in block["inlets_mM"].items()}
        touched = {a for s, t, _ in self.links for a in (s, t)}
        self.flow_nodes = [n for n in self.nodes if n in touched]
        self.holders = len(self.inlet) + len(self.flow_nodes) + len(block["collectors"])
        self.times = [0.0] + (list(block["outputs_s"]) if isinstance(block["outputs_s"], list) else list(block.get("compare_s", [])))
        self.memo = {}

    def x(self, inlet, species, t=D(0)):
        level = None
        for start, c in self.inlet[inlet][species]:
            if start <= t:
                level = c
        return level

    def q_out(self, node):
        return sum((q for s, _, q in self.links if s == node), D(0))

    def total(self, species, t):
        n = sum(self.n0[species].values(), D(0))
        for s, _, q in self.links:
            if s in self.inlet:
                for a, b, c in self.pieces(s, species, t):
                    n += q * c * (b - a)
        for e in self.b["events"]:
            if e["kind"] == "delivery" and D(e["time_s"]) < t:
                n += D(e["volume_pL"]) * self.x(e["inlet"], species, D(e["time_s"]))
        return n

    def pieces(self, inlet, species, t):
        sched = self.inlet[inlet][species]
        out = []
        for k, (start, c) in enumerate(sched):
            stop = sched[k + 1][0] if k + 1 < len(sched) else t
            a, b = start, min(stop, t)
            if b > a:
                out.append((a, b, c))
        return out

    def lam(self):
        levels = [n / self.V[k] for x in self.species for k, n in self.n0[x].items()]
        levels += [c for i in self.inlet.values() for s in i.values() for _, c in s]
        levels += [D(c) for e in self.b["events"] if e["kind"] == "exchange" for c in e["buffer_mM"].values()]
        return max(abs(ln(c)) for c in levels)

    def s_f(self, t):
        return self.rt * (self.lam() + 1) * sum((self.total(x, t) for x in self.species), D(0))

    # ---- flows by columns --------------------------------------------------------------------------------------------
    def columns(self, t):
        """(P, S): P[i][j] the fraction of j's start found in i at t; S[i][I] the inlet's liquid (pL) found in i at t."""
        if t in self.memo:
            return self.memo[t]
        names = self.flow_nodes + list(self.b["collectors"])
        rate = {j: self.q_out(j) / self.V[j] for j in self.flow_nodes}
        q = max([*rate.values(), D("0.01")])
        steps = {}

        def jump(v):
            new = {i: v[i] * (1 - rate.get(i, D(0)) / q) for i in names}
            for s, target, flow in self.links:
                if s in self.V:
                    new[target] += v[s] * flow / self.V[s] / q
            return new

        def run(start, source):
            weight = (-q * t).exp()
            v, total = dict(start), {i: weight * start[i] for i in names}
            integral_weight = D(0)
            if source is not None:
                # y' = G y + s: e^(Gt) convolved; use the integral of the same Poisson weights
                tail = 1 - weight
                acc = {i: D(0) for i in names}
                v_src = {i: D(0) for i in names}
                for s, target, flow in self.links:
                    if s == source:
                        v_src[target] += flow
                k = 0
                current = dict(v_src)
                while True:
                    # integral over (0, t) of e^(-qs)(qs)^k/k! ds = (1 - sum_{m<=k} e^(-qt)(qt)^m/m!)/q
                    for i in names:
                        acc[i] += current[i] * tail / q
                    if k > q * t and tail < D(10) ** -97:
                        break
                    k += 1
                    weight = weight * q * t / k
                    tail -= weight
                    current = jump(current)
                return acc
            k = 0
            while True:
                k += 1
                weight = weight * q * t / k
                v = jump(v)
                for i in names:
                    total[i] += weight * v[i]
                if k > q * t and weight < D(10) ** -98:
                    break
            return total

        p, s = {i: {} for i in names}, {i: {} for i in names}
        for j in self.flow_nodes:
            column = run({i: D(1) if i == j else D(0) for i in names}, None)
            for i in names:
                p[i][j] = column[i]
        for inlet in self.inlet:
            column = run({i: D(0) for i in names}, inlet)
            for i in names:
                s[i][inlet] = column[i]
        self.memo[t] = (p, s)
        return p, s

    def amounts(self, species, t, scale=D(1)):
        if t == 0:
            return {i: self.n0[species].get(i, D(0)) for i in self.nodes + list(self.b["collectors"])}
        p, s = self.columns(t)
        out = {}
        for i in p:
            out[i] = sum((p[i][j] * self.n0[species].get(j, D(0)) for j in p[i]), D(0))
            out[i] += sum((s[i][inlet] * self.x(inlet, species) for inlet in s[i]), D(0))
        for node in self.nodes:
            if node not in out:
                out[node] = self.n0[species].get(node, D(0))
        return out

    def label(self, label, t):
        spec = self.b["labels"]
        species, base = spec["species"], spec["base"]
        start = {}
        for node in self.flow_nodes:
            shares = spec["start_shares"].get(node, {})
            tagged = sum((D(v) for k, v in shares.items() if k != base), D(0))
            share = (1 - tagged) if label == base else D(shares.get(label, 0.0))
            start[node] = self.n0[species].get(node, D(0)) * share
        names = self.flow_nodes + list(self.b["collectors"])
        if t == 0:
            return {i: start.get(i, D(0)) for i in names}
        p, s = self.columns(t)
        out = {}
        for i in names:
            out[i] = sum((p[i][j] * start[j] for j in start), D(0))
            if label == base:
                out[i] += sum((s[i][inlet] * self.x(inlet, species) for inlet in s[i]), D(0))
        return out

    def volume_k(self, t):
        return sum((q for _, target, q in self.links if target in self.b["collectors"]), D(0)) * t

    def mixing_total(self, t):
        """H_tot(t) as one ideal mixing: every holder receives from every origin, in a single step from 0 to t."""
        p, s = self.columns(t)
        total = D(0)
        for i in p:
            volume = self.V[i] if i in self.V else self.volume_k(t)
            for x in self.species:
                n_i = self.amounts(x, t)[i]
                y = n_i / volume
                for j in p[i]:
                    v = p[i][j] * self.V[j]
                    if v != 0:
                        total += v * y * f_phi(self.n0[x].get(j, D(0)) / self.V[j] / y)
                for inlet in s[i]:
                    if s[i][inlet] != 0:
                        total += s[i][inlet] * y * f_phi(self.x(inlet, x) / y)
        return self.rt * total


def wells(w):
    (a, b, table), = w.b["faces_pL_per_s"]
    sp, = w.species
    return w.n0[sp][a], w.n0[sp][b], w.V[a], w.V[b], D(table[sp])


def relax(n1, n2, v1, v2, pa, t):
    """The exact two-well solution as a relaxation to the common level."""
    level = (n1 + n2) / (v1 + v2)
    decay = (-pa * (1 / v1 + 1 / v2) * t).exp()
    return v1 * level + (n1 - v1 * level) * decay, v2 * level + (n2 - v2 * level) * decay


def lost(rt, n1, n2, v1, v2, m):
    """D(m) by logarithms of ratios."""
    c1, c2, d1, d2 = n1 / v1, n2 / v2, (n1 - m) / v1, (n2 + m) / v2
    return rt * (n1 * ln(c1 / d1) + n2 * ln(c2 / d2) + m * ln(d1 / d2))


def stage_constants():
    gamma = 1 - D("0.5").sqrt()
    return gamma, 1 - 1 / (2 * gamma)


def scheme_moved(n1, n2, v1, v2, pa, h):
    """The scheme's one step by its explicit stages on the difference of levels."""
    gamma, delta = stage_constants()
    j1 = pa * (n1 / v1 - n2 / v2)
    j2 = pa * ((n1 - gamma * h * j1) / v1 - (n2 + gamma * h * j1) / v2)
    return h * (delta * j1 + (1 - delta) * j2), j1, j2


def default_heat(rt, n1, n2, v1, v2, pa, h):
    gamma, delta = stage_constants()
    _, j1, j2 = scheme_moved(n1, n2, v1, v2, pa, h)
    mean = delta * j1 + (1 - delta) * j2
    c1, c2 = n1 / v1 - h / 2 * j1 / v1, n2 / v2 + h / 2 * j1 / v2
    return rt * h * mean * mean * ln(c1 / c2) / (pa * (c1 - c2))


def default_bound(rt, n1, n2, v1, v2, pa, h):
    z = pa * (1 / v1 + 1 / v2) * h
    reach = (n1 / v1 - n2 / v2) / (1 / v1 + 1 / v2)
    m, star, d = reach * (z - z * z / 2), reach * z / 2, reach * z * z / 4
    slope = lambda s: rt * (1 / (n1 - s) + 1 / (n2 + s))
    bend = lambda s: abs(rt * (1 / (n2 + s) ** 2 - 1 / (n1 - s) ** 2))
    return m * d * max(slope(m / 2), slope(star)) + m ** 3 / 24 * max(bend(D(0)), bend(m))


# ---- Clenshaw-Curtis ------------------------------------------------------------------------------------------------------

def cosine(x):
    total, term, k = D(1), D(1), 0
    x = +x
    halvings = 0
    while abs(x) > D("0.05"):
        x /= 2
        halvings += 1
    square = x * x
    total, term, k = D(1), D(1), 0
    while True:
        k += 1
        term = -term * square / ((2 * k - 1) * (2 * k))
        total += term
        if abs(term) < D(10) ** -105:
            break
    for _ in range(halvings):
        total = 2 * total * total - 1
    return total


def big_pi():
    # Gauss-Legendre's arithmetic-geometric mean (the writer uses Machin's formula)
    a, b, t, p = D(1), 1 / D(2).sqrt(), D("0.25"), D(1)
    for _ in range(9):
        a, b, t, p = (a + b) / 2, (a * b).sqrt(), t - p * ((a - b) / 2) ** 2, 2 * p
    return (a + b) ** 2 / (4 * t)


class ClenshawCurtis:
    def __init__(self, n=48):
        pi = big_pi()
        angles = [pi * k / n for k in range(n + 1)]
        cos_table = {}
        for k in range(n // 2 + 1):
            for j in range(n // 2 + 1):
                m = (2 * j * k) % (2 * n)
                if m not in cos_table:
                    cos_table[m] = cosine(pi * m / n)
        self.rule = []
        for k in range(n + 1):
            total = D(1)
            for j in range(1, n // 2 + 1):
                b = D(1) if j == n // 2 else D(2)
                total -= b / (4 * j * j - 1) * cosine_index(cos_table, 2 * j * k, n, pi)
            c = D(1) if k in (0, n) else D(2)
            self.rule.append(((1 - cosine(angles[k])) / 2, c * total / n / 2))

    def points(self, a, b):
        return [(a + (b - a) * s, (b - a) * w) for s, w in self.rule]


def cosine_index(table, m, n, pi):
    m %= 2 * n
    if m not in table:
        table[m] = cosine(pi * m / n)
    return table[m]


def graded(a, b, depth):
    edges = [a] + [a + (b - a) / 2 ** k for k in range(depth, -1, -1)]
    return list(zip(edges, edges[1:]))


# ---- closed-form levels of a chain, with or without a face --------------------------------------------------------------------

class ChainLevels:
    def __init__(self, w, species):
        self.w, self.species = w, species
        (self.i, self.a, self.q), (_, self.b, _), (_, self.k, _) = w.links
        self.x = w.x(self.i, species)
        self.v1, self.v2 = w.V[self.a], w.V[self.b]
        self.n1, self.n2 = w.n0[species].get(self.a, D(0)), w.n0[species].get(self.b, D(0))
        self.p = D(0)
        for fa, fb, table in w.b["faces_pL_per_s"]:
            self.p = D(table[species])

    def at(self, t):
        """(c_first, c_second, c_K) at t > 0."""
        q, p, v1, v2 = self.q, self.p, self.v1, self.v2
        if p == 0:
            a, b = q / v1, q / v2
            ea, eb = (-a * t).exp(), (-b * t).exp()
            u1, u2 = self.n1 - v1 * self.x, self.n2 - v2 * self.x
            passed = a * t * ea if a == b else a * (ea - eb) / (b - a)
            n1, n2 = v1 * self.x + u1 * ea, v2 * self.x + u2 * eb + u1 * passed
        else:
            rest = self.x if q != 0 else (self.n1 + self.n2) / (v1 + v2)
            m11, m12, m21, m22 = -(q + p) / v1, p / v1, (q + p) / v2, -(q + p) / v2
            s = (m11 + m22) / 2
            d = ((m11 - m22) ** 2 / 4 + m12 * m21).sqrt()
            e1, e2 = ((s + d) * t).exp(), ((s - d) * t).exp()
            ch, sh = (e1 + e2) / 2, (e1 - e2) / 2 / d
            u1, u2 = self.n1 / v1 - rest, self.n2 / v2 - rest
            n1 = v1 * (rest + ch * u1 + sh * ((m11 - s) * u1 + m12 * u2))
            n2 = v2 * (rest + ch * u2 + sh * (m21 * u1 + (m22 - s) * u2))
        collected = self.n1 + self.n2 + q * self.x * t - n1 - n2
        return n1 / v1, n2 / v2, (collected / (q * t) if q != 0 else D(0)), (n1, n2, collected)

    def rates(self, t):
        """(r_first, r_second, r_K, face) at t >= 0, for this species."""
        rt, q = self.w.rt, self.q
        if t == 0:
            c1, c2 = self.n1 / self.v1, self.n2 / self.v2
            ck = c2
        else:
            c1, c2, ck, _ = self.at(t)
        rate = lambda x, y: D(0) if q == 0 else rt * q * (x * ln(x / y) - x + y)
        face = D(0) if self.p == 0 or c1 == c2 else rt * self.p * (c1 - c2) * ln(c1 / c2)
        return rate(self.x, c1), rate(c1, c2), rate(c2, ck), face


# ---- comparisons -----------------------------------------------------------------------------------------------------------------

class Compare:
    """The largest |published - mine| against accuracy + an allowance."""

    def __init__(self):
        self.worst, self.count = D(0), 0

    def __call__(self, published, accuracy, mine, allowance):
        gap = abs(D(published) - mine)
        allowed = D(accuracy) + allowance
        self.count += 1
        fraction = gap / allowed if allowed != 0 else (D(0) if gap == 0 else D(10) ** 9)
        self.worst = max(self.worst, fraction)

    def done(self, name):
        note(f"{name}: {self.count} values, the largest gap over accuracy plus the method's allowance", self.worst, D(1))


def check_structure(path, document, inputs_bytes, arm):
    label = os.path.basename(path)
    fault(f"{label}: top-level keys", set(document) == TOP_KEYS)
    fault(f"{label}: kind, arm, constants, provenance",
          document["kind"] == "liquid-routing reference, version 1" and document["arm"] == arm
          and document["constants"] == {"N_A": "6.02214076e23", "k_B": "1.380649e-23"}
          and set(document["provenance"]) == {"revision", "sha256_of_this_file_excluded"}
          and document["provenance"]["sha256_of_this_file_excluded"] is True)
    fault(f"{label}: inputs_sha256", document["inputs_sha256"] == hashlib.sha256(inputs_bytes).hexdigest())
    good = True
    for name, world in document["worlds"].items():
        n = len(world["times_s"])
        for series in world["series"].values():
            good &= len(series["class"]) == len(series["value"]) == len(series["accuracy"]) == n
            good &= all(c in "ERBSLU" and len(c) == 1 for c in series["class"])
            good &= all(VALUE.match(v) for v in series["value"]) and all(BOUND.match(v) for v in series["accuracy"])
            for c, v, a in zip(series["class"], series["value"], series["accuracy"]):
                if c == "E":
                    good &= v == "0" and a == "0"
                if v == "0":
                    good &= a == "0"
                else:
                    good &= D(a) > 0
    fault(f"{label}: lists parallel, classes among the six, 40 digits, E entries zero with accuracy 0", good)
    for row in document["checks"]:
        if not row["passes"] or not (D(row["residual"]) <= D(row["bound"]) and not row["residual"].startswith("-")):
            fault(f"{label}: check fails: {row['name']}")
    fault(f"{label}: every check passes ({len(document['checks'])})", all(r["passes"] for r in document["checks"]))
    below = []
    for plant in document["plants"]:
        required = {"plant", "check", "world", "time_s", "step_s", "honest", "planted", "distance", "expected_tolerance", "margin",
                    "no_margin", "class"}
        fault(f"{label}: plant keys {plant['plant']} {plant['check']} {plant['world']}", required <= set(plant))
        if plant["no_margin"]:
            fault(f"{label}: {plant['plant']} has no margin: tolerance \"0\", margin null, distance not zero",
                  plant["margin"] is None and plant["expected_tolerance"] == "0" and D(plant["distance"]) != 0
                  and plant["class"] == "E")
        else:
            if D(plant["margin"]) < 10:
                below.append((plant["plant"], plant["check"], plant["world"], plant["margin"]))
            gap = abs(D(plant["margin"]) - D(plant["distance"]) / D(plant["expected_tolerance"]))
            fault(f"{label}: {plant['plant']} {plant['check']} {plant['world']} margin is distance over tolerance",
                  gap <= D(plant["margin"]) * D(10) ** -37)
            gap = abs(abs(D(plant["planted"]) - D(plant["honest"])) - D(plant["distance"]))
            fault(f"{label}: {plant['plant']} {plant['check']} {plant['world']} distance is |planted - honest|",
                  gap <= (abs(D(plant["honest"])) + abs(D(plant["planted"]))) * D(10) ** -38)
    fault(f"{label}: every plant margin is at least 10 ({len(document['plants'])} plants): {below if below else 'all'}", not below)


def expected_series(w, arm):
    """{series: [class at each time]} re-derived from SPEC section 4, READOUTS section 3 and Amendment 1."""
    b, times = w.b, w.times
    n = len(times)
    out = {}
    still = bool(b["faces_pL_per_s"]) and bool(b["links_pL_per_s"]) and all(q == 0 for _, _, q in w.links)
    crossing = {x for _, _, t in b["faces_pL_per_s"] for x, p in t.items() if p != 0}
    later = lambda k: ["E"] + [k] * (n - 1)
    if arm == 1:
        return {"n_T_1": ["R"], "n_T_2": ["R"], "H_face": ["E"]}
    if arm == 2:
        return {"n_T_1": ["S"] * n, "n_T_2": ["S"] * n, "H_face": later("S")}
    for x in w.species:
        for node in w.nodes:
            if b["sites"] and (x, node) == (b["sites"]["ligand"], b["sites"]["node"]):
                continue
            out[f"n_{x}_{node}"] = ["S" if arm == 6 and x in crossing else "R"] * n
        for k in b["collectors"]:
            out[f"n_{x}_{k}"] = ["E"] * n if still else later("S" if arm == 6 and x in crossing else "R")
        out[f"supplied_{x}"] = later("R")
    out["V_K"] = ["E"] * n if still else later("R")
    out["H_tot"] = later("S" if arm == 6 else "R")
    if arm == 4:
        out["H_K"] = later("R")
    if arm == 5:
        uniform = all(w.n0[x][k] / w.V[k] == w.x("I", x) for x in w.species for k in w.nodes)
        for h in w.flow_nodes + list(b["collectors"]):
            out[f"H_{h}"] = later("U" if uniform else "S")
    if arm == 6:
        out["H_face"] = later("S")
        if still:
            for h in w.flow_nodes + list(b["collectors"]):
                out[f"H_{h}"] = ["E"] * n
    if b["labels"]:
        spec = b["labels"]
        for label in spec["names"]:
            for h in w.flow_nodes + list(b["collectors"]):
                zero = h in b["collectors"] or (label != spec["base"] and D(spec["start_shares"].get(h, {}).get(label, 0.0)) == 0)
                out[f"label_{spec['species']}_{label}_{h}"] = later("R") if zero else ["R"] * n
    return out


def check_worlds(document, inputs_worlds, arm_of, label):
    good = True
    missing = []
    for name, arm in arm_of.items():
        if name not in document["worlds"]:
            missing.append(name)
            continue
        w = inputs_worlds[name]
        want = expected_series(w, arm)
        have = document["worlds"][name]["series"]
        times = [0.0] if arm == 1 else w.times
        if set(want) != set(have) or any(have[s]["class"] != want[s] for s in want) or document["worlds"][name]["times_s"] != times:
            good = False
            missing.append((name, sorted(set(want) ^ set(have)), [s for s in want if s in have and have[s]["class"] != want[s]]))
    fault(f"{label}: series names, times and classes re-derived: {missing if missing else 'all'}", good and not missing
          and set(document["worlds"]) == set(arm_of))


def check_values(document, worlds, arm_of, label, runs):
    tiny = D(10) ** -60
    for name in sorted(arm_of):
        arm, w = arm_of[name], worlds[name]
        table = document["worlds"][name]
        series = {s: [(v, a) for v, a in zip(t["value"], t["accuracy"])] for s, t in table["series"].items()}
        times = [D(t) for t in table["times_s"]]
        compare = Compare()
        if arm == 1:
            n1, n2, *_ = wells(w)
            compare(*series["n_T_1"][0], n1, tiny)
            compare(*series["n_T_2"][0], n2, tiny)
            compare(*series["H_face"][0], D(0), D(0))
            own = [r for r in runs if r["world"] == name and r["arm"] == 1]
            wanted = {r["step"]["s"] for r in own}
            for heat in ("exact", "default"):
                judged = [r["step"]["s"] for r in own if r["heat"] == heat and r["role"] == "judged"]
                if judged:
                    wanted.add(min(judged) / 2)               # the retry's next halving (CRITERIA section 2)
            fault(f"{label}: the cases of {name} are its runs' steps and the retry's", {k for k in document["cases"]
                  if k.split("|")[0] == name} == {f"{name}|{v!r}" for v in wanted})
            for step in sorted(wanted):
                h = D(step)
                case = document["cases"][f"{name}|{step!r}"]
                n1, n2, v1, v2, pa = wells(w)
                e1, e2 = relax(n1, n2, v1, v2, pa, h)
                m_r, _, _ = scheme_moved(n1, n2, v1, v2, pa, h)
                mine = {"m_star": n1 - e1, "m_R": m_r, "D_star": lost(w.rt, n1, n2, v1, v2, n1 - e1),
                        "D_R": lost(w.rt, n1, n2, v1, v2, m_r), "A0": w.rt * ln(n1 * v2 / (n2 * v1)),
                        "H_def": default_heat(w.rt, n1, n2, v1, v2, pa, h), "B_def": default_bound(w.rt, n1, n2, v1, v2, pa, h)}
                for k, value in mine.items():
                    compare(case[k], case["accuracy"][k], value, abs(value) * tiny)
                for k, pair in (("levels_exact", (e1, e2)), ("levels_scheme", (n1 - m_r, n2 + m_r))):
                    for published, accuracy, value in zip(case[k], case["accuracy"][k], pair):
                        compare(published, accuracy, value, abs(value) * tiny)
                want = {"m_star", "m_R", "levels_exact", "levels_scheme", "D_star", "D_R", "A0", "H_def", "B_def", "accuracy"}
                fault(f"{label}: case {name}|{step!r} keys", set(case) == want)
            compare.done(f"{label}: {name}, cases")
            continue
        if arm == 2:
            n1, n2, v1, v2, pa = wells(w)
            event = w.b["events"][0] if w.b["events"] else None
            for k, t in enumerate(times):
                if event is None or t <= D(event["time_s"]):
                    a1, a2 = relax(n1, n2, v1, v2, pa, t)
                    heat = lost(w.rt, n1, n2, v1, v2, n1 - a1)
                else:
                    te, f, x = D(event["time_s"]), D(event["fraction"]), D(event["buffer_mM"]["T"])
                    b1, b2 = relax(n1, n2, v1, v2, pa, te)
                    heat = lost(w.rt, n1, n2, v1, v2, n1 - b1)
                    after = b1 - f * b1 + f * v1 * x
                    a1, a2 = relax(after, b2, v1, v2, pa, t - te)
                    heat += lost(w.rt, after, b2, v1, v2, after - a1)
                for s, value in (("n_T_1", a1), ("n_T_2", a2), ("H_face", heat)):
                    compare(*series[s][k], value, max(abs(value), D(1)) * D(10) ** -90)
            if event is not None:
                te, f, x = D(event["time_s"]), D(event["fraction"]), D(event["buffer_mM"]["T"])
                b1, b2 = relax(n1, n2, v1, v2, pa, te)
                after = b1 - f * b1 + f * v1 * x
                c, c_after = b1 / v1, after / v1
                heat = w.rt * v1 * c_after * ((1 - f) * f_phi(c / c_after) + f * f_phi(x / c_after))
                block = document["events"][name]
                for k, value in (("before", b1), ("sample", f * b1), ("supplied", f * v1 * x), ("heat", heat)):
                    compare(block[k], block["accuracy"][k], value, max(abs(value), D(1)) * D(10) ** -90)
                fault(f"{label}: event {name} time and classes", block["time_s"] == event["time_s"] and block["class"] ==
                      {"before": "S", "sample": "S", "supplied": "R", "heat": "S"})
            else:
                fault(f"{label}: no event for {name}", name not in document["events"])
            compare.done(f"{label}: {name}, series and event")
            continue
        if arm == 4:
            entries = [(D(e["time_s"]), D(e["volume_pL"]), w.x(e["inlet"], "T", D(e["time_s"]))) for e in w.b["events"]]
            for k, t in enumerate(times):
                if entries:
                    joined = [(v, x) for at, v, x in entries if at < t]
                else:
                    joined = [(q * (b - a), c) for s, _, q in w.links for a, b, c in w.pieces(s, "T", t)]
                n, v = sum((v * x for v, x in joined), D(0)), sum((v for v, _ in joined), D(0))
                heat = w.rt * (sum((v_ * x * ln(x) for v_, x in joined), D(0)) - (n * ln(n / v) if n else D(0)))
                for s, value in (("n_T_K", n), ("V_K", v), ("supplied_T", n), ("H_K", heat), ("H_tot", heat)):
                    compare(*series[s][k], value, max(abs(value), D(1)) * D(10) ** -90)
            if entries:
                n = v = D(0)
                blocks = document["events"][name]
                fault(f"{label}: {name} has one event block a portion", len(blocks) == len(entries))
                for k, ((at, dv, x), block) in enumerate(zip(entries, blocks)):
                    before = (n, v)
                    n, v = n + dv * x, v + dv
                    y = n / v
                    resident = w.rt * (before[1] * y * f_phi(before[0] / before[1] / y)) if before[1] else D(0)
                    arriving = w.rt * dv * y * f_phi(x / y) if before[1] else D(0)
                    for key, value in (("volume_pL", dv), ("amount", dv * x), ("loss", resident + arriving), ("resident", resident),
                                       ("arriving", arriving)):
                        compare(block[key], block["accuracy"][key], value, max(abs(value), D(1)) * D(10) ** -90)
                    fault(f"{label}: {name} portion {k} time and class", block["time_s"] == float(at)
                          and block["class"]["loss"] == ("E" if k == 0 else "R") and (k or block["loss"] == "0"))
            compare.done(f"{label}: {name}, series and portions")
            continue
        # arms 3, 5 and 6
        still = bool(w.b["faces_pL_per_s"]) and all(q == 0 for _, _, q in w.links)
        for k, t in enumerate(times):
            for x in w.species:
                if arm == 6:
                    levels = ChainLevels(w, x)
                    if t == 0:
                        mine = dict(w.n0[x], K=D(0))
                    else:
                        n1, n2, nk = levels.at(t)[3]
                        mine = {levels.a: n1, levels.b: n2, "K": nk if not still else D(0)}
                else:
                    mine = w.amounts(x, t)
                for name_i, value in mine.items():
                    s = f"n_{x}_{name_i}"
                    if s in series:
                        compare(*series[s][k], value, abs(value) * D(10) ** -80 + D(10) ** -90)
                compare(*series[f"supplied_{x}"][k], sum((q * w.x(s_, x) * t for s_, _, q in w.links if s_ in w.inlet), D(0)), tiny * D(10) ** -20)
            compare(*series["V_K"][k], w.volume_k(t), tiny * D(10) ** -20)
            if w.b["labels"]:
                spec = w.b["labels"]
                for lab in spec["names"]:
                    for name_i, value in w.label(lab, t).items():
                        compare(*series[f"label_{spec['species']}_{lab}_{name_i}"][k], value, abs(value) * D(10) ** -80 + D(10) ** -90)
            if arm == 3 and t > 0:
                compare(*series["H_tot"][k], w.mixing_total(t), w.s_f(t) * D(10) ** -80)
        compare.done(f"{label}: {name}, amounts, volumes, supplied, labels" + (", H_tot" if arm == 3 else ""))
        if arm in (5, 6):
            check_heats(document, w, series, times, label, arm, still)


def check_heats(document, w, series, times, label, arm, still):
    """Holder and face heats by Clenshaw-Curtis, H_tot by the logarithmic state function."""
    rule = ClenshawCurtis(48)
    levels = {x: ChainLevels(w, x) for x in w.species}
    names = [levels[w.species[0]].a, levels[w.species[0]].b, "K", "face"]
    low = min([n / w.V[k] for x in w.species for k, n in w.n0[x].items()] + [c for i in w.inlet.values() for s in i.values() for _, c in s])
    high = max([n / w.V[k] for x in w.species for k, n in w.n0[x].items()])
    depth = 8
    while 2 ** depth < high / low * 64:
        depth += 1
    totals = {h: D(0) for h in names}
    worst = D(0)
    tot = D(0)
    left = D(0)
    uniform = all(c == "U" for c in document["worlds"][w.name]["series"].get("H_A", {"class": ["S", "S"]})["class"][1:])
    for k, t in enumerate(times):
        if t == 0:
            continue
        for a, b in graded(left, t, depth if left == 0 else 0):
            for s, weight in rule.points(a, b):
                for x in w.species:
                    for h, r in zip(names, levels[x].rates(s)):
                        totals[h] += weight * r
        left = t
        state = D(0)
        for x in w.species:
            for node, n in w.n0[x].items():
                state += xlog(n, n / w.V[node])
            if t:
                c1, c2, ck, (n1, n2, nk) = levels[x].at(t)
                state -= xlog(n1, n1 / levels[x].v1) + xlog(n2, n2 / levels[x].v2)
                if nk and levels[x].q:
                    state -= xlog(nk, nk / (levels[x].q * t))
                    state += levels[x].q * t * xlog(levels[x].x, levels[x].x)
        state *= w.rt
        scale = w.s_f(t)
        published_total = D(series["H_tot"][k][0])
        worst = max(worst, abs(published_total - (D(0) if uniform else state)) / scale)
        checks = [(names[0], f"H_{names[0]}"), (names[1], f"H_{names[1]}"), ("K", "H_K")] if arm == 5 else [("face", "H_face")]
        for h, s in checks:
            worst = max(worst, abs(D(series[s][k][0]) - totals[h]) / scale)
        if still:
            for h in (names[0], names[1], "K"):
                worst = max(worst, abs(D(series[f"H_{h}"][k][0])))
        if arm == 6:
            worst = max(worst, abs(sum(totals.values()) - published_total) / scale)
    note(f"{label}: {w.name}, holder and face heats by Clenshaw-Curtis, H_tot by logarithms (over s_F)", worst, D(10) ** -24)


# ---- the plants, again ------------------------------------------------------------------------------------------------------------

def check_plants(document, worlds, label, plan, runs):
    rows = document["plants"]
    tight = D(10) ** -30

    def find(plant, check, world, step=None, heat=None):
        hits = [r for r in rows if r["plant"] == plant and r["check"] == check and r["world"] == world
                and (step is None or r["step_s"] == step) and (heat is None or r.get("heat") == heat)]
        return hits[0] if len(hits) == 1 else None

    def same(name, row, honest, planted, tolerance, klass):
        if row is None:
            fault(f"{label}: {name} is listed once")
            return
        ok = abs(D(row["honest"]) - honest) <= (abs(honest) + D(10) ** -9) * tight
        ok &= abs(D(row["planted"]) - planted) <= (abs(planted) + D(10) ** -9) * tight
        ok &= row["class"] == klass
        if tolerance is not None:
            ok &= abs(D(row["expected_tolerance"]) / tolerance - 1) <= tight
        fault(f"{label}: {name} recomputed (honest, planted, tolerance)", ok)

    def e_round(m, s, scale):
        return m * (s + 1) * U * scale

    def m_n(w):
        return 2 * (w.holders + 18)

    if "P14" in plan:
        w = worlds[plan["P14"]]
        n1, n2, v1, v2, pa = wells(w)
        reach = (n1 / v1 - n2 / v2) / (1 / v1 + 1 / v2)
        for run in runs:
            if run["world"] == w.name and run["heat"] == "exact" and run["arm"] == 1 and run["role"] == "judged":
                h = D(run["step"]["s"])
                e1, _ = relax(n1, n2, v1, v2, pa, h)
                z1 = h * pa / v1
                planted = reach * (z1 - z1 * z1 / 2)
                z = h * pa * (1 / v1 + 1 / v2)
                tol = reach * z ** 3 / 6 + e_round(40, 1, n1 + n2)
                same(f"P14 {w.name} h={run['step']['s']}", find("P14", "n_T_1", w.name, run["step"]["s"]), e1, n1 - planted, tol, "B")
                table = document["planted_series"]["P14"][f"{w.name}|{run['step']['s']!r}"]
                fault(f"{label}: P14 planted series {w.name}|{run['step']['s']!r}",
                      abs(D(table["n_T_1"]["value"][0]) - (n1 - planted)) <= abs(n1) * tight and table["n_T_1"]["times_s"] == [run["step"]["s"]]
                      and abs(D(table["n_T_2"]["value"][0]) - (n2 + planted)) <= abs(n2) * tight)
    for name in plan.get("P15", ()):
        w = worlds[name]
        n1, n2, v1, v2, pa = wells(w)
        h = D(plan["P15 step"])
        gamma, delta = stage_constants()

        def flux(a, b):
            return pa * ((a / v1 + b / v2) / 2) * ln((a / v1) / (b / v2))

        j1 = flux(n1, n2)
        j2 = flux(n1 - gamma * h * j1, n2 + gamma * h * j1)
        moved = h * (delta * j1 + (1 - delta) * j2)
        reach = (n1 / v1 - n2 / v2) / (1 / v1 + 1 / v2)
        z = h * pa * (1 / v1 + 1 / v2)
        e1, e2 = relax(n1, n2, v1, v2, pa, h)
        same(f"P15 {name}", find("P15", "n_T_1", name), e1, n1 - moved, reach * z ** 3 / 6 + e_round(40, 1, n1 + n2), "B")
        same(f"P15 {name} (well 2)", find("P15", "n_T_2", name), e2, n2 + moved, reach * z ** 3 / 6 + e_round(40, 1, n1 + n2), "B")
        table = document["planted_series"]["P15"][f"{name}|{plan['P15 step']!r}"]
        fault(f"{label}: P15 planted series {name}", abs(D(table["n_T_1"]["value"][0]) / (n1 - moved) - 1) <= D(10) ** -35
              and abs(D(table["n_T_2"]["value"][0]) / (n2 + moved) - 1) <= D(10) ** -35)
    if "P16" in plan:
        w = worlds[plan["P16"]]
        n1, n2, v1, v2, pa = wells(w)
        scale = w.rt * (w.lam() + 1) * (n1 + n2)
        for run in runs:
            if run["world"] != w.name or run["arm"] != 1 or run["role"] != "judged":
                continue
            h = D(run["step"]["s"])
            m, _, _ = scheme_moved(n1, n2, v1, v2, pa, h)
            planted = m * w.rt * ln(n1 * v2 / (n2 * v1))
            honest = lost(w.rt, n1, n2, v1, v2, m)
            if run["heat"] == "default":
                tol = default_bound(w.rt, n1, n2, v1, v2, pa, h) + e_round(90, 1, scale)
                same(f"P16 default h={run['step']['s']}", find("P16", "H_face", w.name, run["step"]["s"], "default"), honest, planted, tol, "B")
        first = [r for r in runs if r["world"] == w.name and r["arm"] == 1 and r["heat"] == "exact" and r["role"] == "judged"][0]
        h = D(first["step"]["s"])
        m, _, _ = scheme_moved(n1, n2, v1, v2, pa, h)
        same("P16 exact j=0", find("P16", "H_face", w.name, first["step"]["s"], "exact"), lost(w.rt, n1, n2, v1, v2, m),
             m * w.rt * ln(n1 * v2 / (n2 * v1)), e_round(64, 1, scale), "R")
    if "P17" in plan:
        w = worlds[plan["P17"]]
        n1, n2, v1, v2, pa = wells(w)
        event = w.b["events"][0]
        step = [r for r in runs if r["world"] == w.name and r["arm"] == 2 and r["heat"] == "exact" and r["role"] == "judged"][-1]["step"]["s"]
        f, te = D(event["fraction"]), D(event["time_s"])
        same("P17", find("P17", "sample", w.name), f * relax(n1, n2, v1, v2, pa, te)[0],
             f * relax(n1, n2, v1, v2, pa, te + D(step))[0], 8 * U * (n1 + n2), "R")
    if "P1" in plan:
        a, b = (worlds[n] for n in plan["P1"])
        t, h = D(plan["P1 time"]), D(plan["P1 step"])
        ka, kb = a.amounts("T", t)["K"], b.amounts("T", t)["K"]
        same(f"P1 {a.name}", find("P1", "n_T_K", a.name), ka, kb, e_round(m_n(a), t / h, a.total("T", t)), "R")
        same(f"P1 {b.name}", find("P1", "n_T_K", b.name), kb, ka, e_round(m_n(b), t / h, b.total("T", t)), "R")
        same("P10", find("P10", "n_T_K", a.name), ka, a.amounts("T", 2 * t)["K"], e_round(m_n(a), t / h, a.total("T", t)), "R")

        def best(candidates):
            return max(candidates, key=lambda c: abs(c[2] - c[1]) / c[3])

        chain = {}
        for name in plan["P2"]:
            w = worlds[name]
            q, x = w.links[0][2], w.x("I", "T")
            times = [D(v) for v in w.times[1:] if (D(v) / h) % 1 == 0]
            for node in ("B", "K"):
                options = []
                for v in times:
                    n = w.amounts("T", v)
                    planted = w.n0["T"]["B"] if node == "B" else w.n0["T"]["A"] + q * x * v - n["A"]
                    options.append((v, n[node], planted, e_round(m_n(w), v / h, w.total("T", v))))
                v, honest, planted, tol = best(options)
                same(f"P2 {name} {node}", find("P2", f"n_T_{node}", name), honest, planted, tol, "R")
                series = document["planted_series"]["P2"][name][f"n_T_{node}"]
                fault(f"{label}: P2 planted series {name} {node}", series["times_s"] == [float(v_) for v_ in times] and all(
                    abs(D(s) - o[2]) <= (abs(o[2]) + D(10) ** -9) * tight for s, o in zip(series["value"], options)))
        for name, control in ((plan["P3 equal"], True), (plan["P3 unequal"], False)):
            w = worlds[name]
            q, x, va = w.links[0][2], w.x("I", "T"), w.V["A"]
            k = q / va
            times = [D(v) for v in w.times[1:] if (D(v) / h) % 1 == 0]
            rest = q * x / k
            options = {"B": [], "K": [], "V_K": []}
            worst = D(0)
            for v in times:
                n = w.amounts("T", v)
                e = (-k * v).exp()
                na = rest + (w.n0["T"]["A"] - rest) * e
                nb = rest + (w.n0["T"]["B"] - rest) * e + (w.n0["T"]["A"] - rest) * k * v * e
                nk = w.n0["T"]["A"] + w.n0["T"]["B"] + q * x * v - na - nb
                tol = e_round(m_n(w), v / h, w.total("T", v))
                options["B"].append((v, n["B"], nb, tol))
                options["K"].append((v, n["K"], nk, tol))
                options["V_K"].append((v, w.volume_k(v), D(0), e_round(m_n(w), v / h, w.volume_k(D(w.b["end_s"])))))
                worst = max(worst, abs(n["A"] - na), abs(n["B"] - nb), abs(n["K"] - nk))
            if control:
                note(f"{label}: P3's amounts are the honest ones at equal volumes, {name} (fmol)", worst, D(10) ** -80)
            else:
                for node in ("B", "K"):
                    v, honest, planted, tol = best(options[node])
                    same(f"P3 {name} {node}", find("P3", f"n_T_{node}", name), honest, planted, tol, "R")
            v, honest, planted, tol = best(options["V_K"])
            same(f"P3 {name} V_K", find("P3", "V_K", name), honest, planted, tol, "R")
            series = document["planted_series"]["P3"][name]
            fault(f"{label}: P3 planted series {name}", series["V_K"]["value"] == ["0"] * len(times) and all(
                abs(D(s) - o[2]) <= (abs(o[2]) + D(10) ** -9) * tight for s, o in zip(series["n_T_B"]["value"], options["B"])))
        w = worlds[plan["P4"]]
        factor = 1 + D(2) ** -20
        times = [D(v) for v in w.times[1:] if (D(v) / h) % 1 == 0]
        # every Q scaled by a common factor is the honest network at a longer time, with the collector's inlet share alike
        for node in ("B", "K"):
            options = []
            for v in times:
                options.append((v, w.amounts("U", v)[node], w.amounts("U", v * factor)[node], e_round(m_n(w), v / h, w.total("U", v))))
            v, honest, planted, tol = best(options)
            same(f"P4 {node}", find("P4", f"n_U_{node}", w.name), honest, planted, tol, "R")
            series = document["planted_series"]["P4"][w.name][f"n_U_{node}"]
            fault(f"{label}: P4 planted series {node}", series["times_s"] == [float(o[0]) for o in options] and all(
                abs(D(s) / o[2] - 1) <= D(10) ** -35 for s, o in zip(series["value"], options)))
        w = worlds[plan["P11"]]
        h11 = D(plan["P11 step"])
        tag, = [l for l in w.b["labels"]["names"] if l != w.b["labels"]["base"]]
        times = [D(v) for v in w.times[1:] if (D(v) / h11) % 1 == 0]
        options = []
        planted = D(0)
        t = D(0)
        for v in times:
            while t < v:
                before, after = w.amounts("T", t), w.amounts("T", t + h11 / 2)
                share = w.label(tag, t)["B"] / before["B"]
                planted += (after["K"] - before["K"]) * share
                t += h11 / 2
            options.append((v, w.label(tag, v)["K"], planted, e_round(6 * w.holders + 106, v / h11, w.total("T", v))))
        v, honest, planted_best, tol = best(options)
        same("P11", find("P11", f"label_T_{tag}_K", w.name), honest, planted_best, tol, "R")
        series = document["planted_series"]["P11"][f"{w.name}|{plan['P11 step']!r}"][f"label_T_{tag}_K"]
        fault(f"{label}: P11 planted series", all(abs(D(s) - o[2]) <= D(10) ** -35 for s, o in zip(series["value"], options)))
    if "P9" in plan:
        w = worlds[plan["P9"]]
        event = w.b["events"][0]
        v0, n0 = D(2) ** -10, D(2) ** -10 * D(1e-12)
        dv, x = D(event["volume_pL"]), w.x(event["inlet"], "T", D(event["time_s"]))
        y = (n0 + dv * x) / (v0 + dv)
        loss = w.rt * (n0 * ln(n0 / v0 / y) + dv * x * ln(x / y))
        same("P9", find("P9", "loss", w.name), D(0), loss, None, "E")
        series = document["planted_series"]["P9"][w.name]["loss"]
        fault(f"{label}: P9 planted series", series["times_s"] == [event["time_s"]] and abs(D(series["value"][0]) / loss - 1)
              <= D(10) ** -35)
    if "P5" in plan:
        w = worlds[plan["P5"]]
        levels = ChainLevels(w, "T")
        rule = ClenshawCurtis(48)
        steps = sorted(r["step"]["s"] for r in runs if r["world"] == w.name and r["role"] == "judged")
        times = [D(t) for t in w.times[1:]]
        q, x, v1 = levels.q, levels.x, levels.v1
        u = levels.n1 - v1 * x
        a = q / v1
        tv = abs(levels.rates(D(0))[0] - levels.rates(times[-1])[0])
        tol = 3 * D(steps[0]) / 2 * tv
        honest, options, left = D(0), [], D(0)
        for t in times:
            for lo, hi in graded(left, t, 8 if left == 0 else 0):
                honest += sum((weight * levels.rates(s)[0] for s, weight in rule.points(lo, hi)), D(0))
            left = t
            options.append((t, honest, honest - w.rt * u * (1 - (-a * t).exp()), tol))
        t, h_, p_, _ = max(options, key=lambda c: abs(c[2] - c[1]))
        row = find("P5", f"H_{levels.a}", w.name)
        note(f"{label}: P5 honest, planted and tolerance recomputed (relative)", max(
            abs(D(row["honest"]) / h_ - 1), abs(D(row["planted"]) / p_ - 1), abs(D(row["expected_tolerance"]) / tol - 1)), D(10) ** -24)
        fault(f"{label}: P5 is class S at its largest gap", row["class"] == "S" and row["time_s"] == float(t)
              and row["step_s"] == steps[0])
        table = document["planted_series"]["P5"][w.name][f"H_{levels.a}"]
        fault(f"{label}: P5 planted series", table["times_s"] == [float(o[0]) for o in options] and all(
            abs(D(v) / o[2] - 1) <= D(10) ** -24 for v, o in zip(table["value"], options)))
    for name in plan.get("P7", ()):
        w = worlds[name]
        levels = ChainLevels(w, "T")
        step = min(r["step"]["s"] for r in runs if r["world"] == name and r["role"] == "judged")
        h7 = D(step)
        times = [D(t) for t in w.times[1:]]
        booked, t, options = D(0), D(0), []
        table = document["worlds"][name]["series"]
        for k, stop in enumerate(times):
            while t < stop:
                booked += h7 * levels.rates(t)[1]
                t += h7
            honest = D(table["H_tot"]["value"][k + 1])
            planted = honest + booked - D(table[f"H_{levels.b}"]["value"][k + 1])
            m_h = 24 + 2 * w.holders * (len(w.species) + 1)
            options.append((stop, honest, planted, (m_n(w) + m_h) * (stop / h7 + 1) * U * w.s_f(stop)))
        stop, honest, planted, tol = max(options, key=lambda c: abs(c[2] - c[1]) / c[3])
        row = find("P7", "H_tot", name)
        note(f"{label}: P7 {name} recomputed (relative)", max(abs(D(row["honest"]) / honest - 1), abs(D(row["planted"]) / planted - 1),
                                                            abs(D(row["expected_tolerance"]) / tol - 1)), D(10) ** -30)
        fault(f"{label}: P7 {name} at its best entry", row["time_s"] == float(stop) and row["step_s"] == step)
        series = document["planted_series"]["P7"][f"{name}|{step!r}"]["H_tot"]
        fault(f"{label}: P7 planted series {name}", series["times_s"] == [float(o[0]) for o in options] and all(
            abs(D(v) / o[2] - 1) <= D(10) ** -28 for v, o in zip(series["value"], options)))
    if "P19" in plan:
        w = worlds[plan["P19"]]
        levels = ChainLevels(w, "T")
        times = [D(t) for t in w.times[1:]]
        steps = sorted({r["step"]["s"] for r in runs if r["world"] == w.name and r["role"] == "judged"}, reverse=True)
        p, v1, v2, q = levels.p, levels.v1, levels.v2, levels.q
        out = {}
        for kind in ("strang", "lie"):
            for step in steps:
                h = D(step)
                # the flow's exact map over s as a function of (n_A, n_B), from the plain chain's closed form
                def flow_map(n, s):
                    a, b = q / v1, q / v2
                    ea, eb = (-a * s).exp(), (-b * s).exp()
                    x = levels.x
                    u1, u2 = n[0] - v1 * x, n[1] - v2 * x
                    passed = a * s * ea if a == b else a * (ea - eb) / (b - a)
                    return [v1 * x + u1 * ea, v2 * x + u2 * eb + u1 * passed]

                def face_map(n):
                    k = p * (1 / v1 + 1 / v2)
                    reach = (n[0] / v1 - n[1] / v2) / (1 / v1 + 1 / v2)
                    z = k * h
                    m = reach * (z - z * z / 2)
                    return [n[0] - m, n[1] + m]

                n, rows_, t = [levels.n1, levels.n2], [], D(0)
                wanted = set(times)
                while t < times[-1]:
                    if kind == "strang":
                        n = flow_map(face_map(flow_map(n, h / 2)), h / 2)
                    else:
                        n = face_map(flow_map(n, h))
                    t += h
                    if t in wanted:
                        rows_.append(n[0])
                out[kind, step] = rows_
        d2 = max(abs(a - b) for a, b in zip(out["strang", steps[0]], out["strang", steps[1]]))
        d1 = max(abs(a - b) for a, b in zip(out["strang", steps[1]], out["strang", steps[2]]))
        tol = 3 * max(d1 / 3, d2 / 12)
        l2 = max(abs(a - b) for a, b in zip(out["lie", steps[0]], out["lie", steps[1]]))
        l1 = max(abs(a - b) for a, b in zip(out["lie", steps[1]], out["lie", steps[2]]))
        order = ln(l2 / l1) / ln(D(2))
        row = find("P19", "n_T_A", w.name)
        reference = [levels.at(t)[3][0] for t in times]
        gaps = [(abs(a - b), a, b, t) for a, b, t in zip(out["lie", steps[-1]], reference, times)]
        gap, planted, honest, when = max(gaps)
        ok = all(abs(D(row[k]) / v - 1) <= D(10) ** -35 for k, v in (("planted", planted), ("honest", honest), ("expected_tolerance", tol),
                                                                    ("planted_order", order)))
        fault(f"{label}: P19 recomputed (honest, planted, tolerance, order at most 1.25)", ok and order <= D("1.25") and row["time_s"] == float(when))
        for step in steps:
            series = document["planted_series"]["P19"][f"{w.name}|{step!r}"]["n_T_A"]
            fault(f"{label}: P19 planted series at h = {step}", all(abs(D(s) / v - 1) <= D(10) ** -35
                                                                  for s, v in zip(series["value"], out["lie", step])))


PLANS = {
    "registered": {"P14": "r4-mid", "P15": ("eq-lo", "eq-mid", "eq-hi"), "P15 step": 0.25, "P16": "eq-mid", "P17": "N-buffered",
                   "P1": ("F1", "F2"), "P1 time": 8.0, "P1 step": 1.0, "P2": ("F1", "F3"), "P3 equal": "F1", "P3 unequal": "F3",
                   "P4": "F1", "P11": "F1L", "P11 step": 8.0, "P9": "G1", "P5": "H1", "P7": ("H2", "H3", "H4"), "P19": "J1"},
    "invented": {"P14": "inv-r4-mid", "P15": ("inv-eq-mid",), "P15 step": 0.15625, "P16": "inv-eq-mid", "P17": "inv-N-buffered",
                 "P1": ("inv-F1", "inv-F2"), "P1 time": 8.25, "P1 step": 1.03125, "P2": ("inv-F1", "inv-F3"),
                 "P3 equal": "inv-F1", "P3 unequal": "inv-F3", "P4": "inv-F1", "P11": "inv-F1L", "P11 step": 8.25, "P9": "inv-G1",
                 "P5": "inv-H1", "P7": ("inv-H2",), "P19": "inv-J1"},
}
ARM_PLANTS = {1: ("P14", "P15", "P16"), 2: ("P17",), 3: ("P1", "P2", "P3", "P4", "P10", "P11"), 4: ("P9",), 5: ("P5", "P7"),
              6: ("P19",)}
SERIES_PLANTS = {1: {"P14", "P15"}, 2: set(), 3: {"P2", "P3", "P4", "P11"}, 4: {"P9"}, 5: {"P5", "P7"}, 6: {"P19"}}
KEYED_BY_STEP = {"P7", "P11", "P14", "P15", "P19"}


def plan_for(arm, which):
    plan = PLANS[which]
    if arm == 0:
        return plan
    keep = {1: ("P14", "P15", "P15 step", "P16"), 2: ("P17",),
            3: ("P1", "P1 time", "P1 step", "P2", "P3 equal", "P3 unequal", "P4", "P11", "P11 step"), 4: ("P9",),
            5: ("P5", "P7"), 6: ("P19",)}[arm]
    return {k: v for k, v in plan.items() if k in keep}


def check_coverage(document, arm, label):
    arms = [arm] if arm else [1, 2, 3, 4, 5, 6]
    names = {p for a in arms for p in ARM_PLANTS[a]}
    fault(f"{label}: the plants are exactly {sorted(names)}", {r["plant"] for r in document["plants"]} == names)
    wanted = set().union(*(SERIES_PLANTS[a] for a in arms))
    fault(f"{label}: planted series are exactly {sorted(wanted)}", set(document["planted_series"]) == wanted)
    good = True
    for plant, table in document["planted_series"].items():
        for key in table:
            good &= ("|" in key) == (plant in KEYED_BY_STEP)
    fault(f"{label}: planted series keyed by step exactly where Amendment 1 says", good)
    reported = {r["run"].replace("inv-", "") for r in document["plants_reported"]}
    want = {p for a, p in ((2, "P8 event"), (3, "P8 flow")) if a in arms}
    fault(f"{label}: plants_reported holds {sorted(want)}", reported == want)
    for row in document["plants_reported"]:
        fault(f"{label}: {row['run']} lists a missing heat at every time", len(row["times_s"]) == len(row["H_missing"])
              and all(D(v) > 0 for v in row["H_missing"]))
        if row["run"].endswith("P8 event"):
            same = row["H_missing"] == [document["events"][row["world"]]["heat"]]
        else:
            table = document["worlds"][row["world"]]
            series = dict(zip(table["times_s"], table["series"]["H_tot"]["value"]))
            same = row["H_missing"] == [series[t] for t in row["times_s"]] and row["times_s"] == table["times_s"][1:]
        fault(f"{label}: {row['run']}'s missing heat is the file's own event heat or H_tot", same)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True)
    parser.add_argument("--inputs", required=True)
    parser.add_argument("--report")
    parser.add_argument("--only", choices=("invented", "registered"))
    parser.add_argument("--arms", help="registered arms, as 1,3")
    arguments = parser.parse_args()

    def load(path):
        with open(path, "rb") as handle:
            data = handle.read()
        return data, json.loads(data.decode("ascii"), parse_constant=lambda c: fault(f"non-finite number {c} in {os.path.basename(path)}"))

    jobs = []
    if arguments.only in (None, "invented"):
        data, table = load(os.path.join(arguments.out, "inputs_invented.json"))
        jobs.append((0, data, table, "reference_invented.json", "invented"))
    if arguments.only in (None, "registered"):
        data, table = load(arguments.inputs)
        for arm in ([int(a) for a in arguments.arms.split(",")] if arguments.arms else range(1, 7)):
            jobs.append((arm, data, table, f"reference_arm{arm}.json", "registered"))
    for arm, data, table, name, which in jobs:
        path = os.path.join(arguments.out, name)
        _, document = load(path)
        label = name.replace(".json", "").replace("reference_", "")
        check_structure(path, document, data, arm)
        own = {}
        for run in table["runs"]:
            own.setdefault(run["world"], run["arm"])
        arm_of = {w: a for w, a in own.items() if arm == 0 or a == arm}
        worlds = {w: W(w, table["worlds"][w]) for w in table["worlds"]}
        if which == "invented":
            prefix = all(w.startswith("inv-") for w in table["worlds"]) and all(r["name"].startswith("inv-") for r in table["runs"])
            fault("invented: every world and run name has the prefix inv-", prefix)
            fault("invented: every world of a run exists", all(r["world"] in table["worlds"] for r in table["runs"]))
            classes = {c for w in document["worlds"].values() for s in w["series"].values() for c in s["class"]}
            fault(f"invented: classes used {sorted(classes)}", classes >= {"E", "R", "S", "U"})
        check_worlds(document, worlds, arm_of, label)
        check_coverage(document, arm, label)
        check_values(document, worlds, arm_of, label, table["runs"])
        check_plants(document, worlds, label, plan_for(arm, which), table["runs"])
        print(f"{label}: {sum(r['passes'] for r in ROWS)} of {len(ROWS)} pass so far", flush=True)
    if arguments.report:
        with open(arguments.report, "w", encoding="ascii") as handle:
            json.dump({"passed": sum(r["passes"] for r in ROWS), "rows": ROWS, "total": len(ROWS)}, handle, indent=1, sort_keys=True)
            handle.write("\n")
    for row in ROWS:
        if not row["passes"]:
            print("MISS", row)
    sys.exit(0 if all(r["passes"] for r in ROWS) else 1)


if __name__ == "__main__":
    main()
