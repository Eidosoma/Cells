"""The rules of Part 2's spec that form the rehearsal's files from a world's block alone.

PART2.md section 8 (the scales, `amount_refs`, `closure_terms_V`, `closure_terms`), section 2.2 (the
derived declarations) and section 7.4's bands, on top of Part 1's rules (`../rehearsal/rules.py`:
SPEC.md sections 2.2, 4, 5 and 6, CRITERIA.md sections 1 and 4.3). Standard library only: it reads
no engine, no builder's and no judge's code. `rules2.py check` forms `scales`, `amount_refs`,
`closure_terms_V` and `closure_terms` of the registered worlds from their blocks and compares them
with inputs_part2.json's numbers, and prints the paths' shares that section 8 prints.

`rules2.py check FILE` reads another inputs_part2.json (the criteria's commit's).
"""

import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "rehearsal"))
import rules  # noqa: E402

SPEC = HERE.parent / "spec"
F, R, FMOL, EPS, V_STAR = rules.F, rules.R, rules.FMOL, rules.EPS, rules.V_STAR

SHARE = 1e-10  # `closure_share`: e_close of every entry without a number of its own.
CHARGE_RTOL = 2e-12  # The engine's declared charge tolerance (section 8).
CHARGE_ATOL_C = 3e-25
GAMMA = 1 - 1 / math.sqrt(2)  # ARS(2,2,2)'s implicit diagonal.
ROW_FACTOR = 2.01  # The free regions' row sum times the region's own conductances (section 8).
LEGACY_OFFSET = 2.13e-12  # Legacy's solve at its limit, in V* (Part 1's, SPEC section 6).
CLOSE_PHI_V = rules.CLOSE_PHI_V
# The share of a potential error that a gate takes besides its target's: a relaxation's response to
# its time constant, at most 1/e of its logarithmic slope (section 8).
TAU_SHARE = 0.368


# ------------------------------------------------------------------ the laws' slopes, per V


def sigmoid(x):
    return 1 / (1 + math.exp(-x)) if x >= 0 else math.exp(x) / (1 + math.exp(x))


def largest(f, low, high, n=20001):
    """The largest of f over [low, high]: a grid, then a golden section about its largest."""
    step = (high - low) / (n - 1)
    k = max(range(n), key=lambda i: f(low + i * step))
    a, b = low + max(k - 1, 0) * step, low + min(k + 1, n - 1) * step
    ratio = (math.sqrt(5) - 1) / 2
    for _ in range(80):
        c, d = b - ratio * (b - a), a + ratio * (b - a)
        if f(c) > f(d):
            b = d
        else:
            a = c
    return max(f((a + b) / 2), f(low), f(high), f(low + k * step))


KV_DOMAIN = (-0.120, 0.060)


def kv_slopes():
    """(m, h): the target's largest slope and the time constant's largest logarithmic slope."""
    low, high = KV_DOMAIN
    return dict(
        m=(1 / (4 * 0.0064), largest(lambda v: 0.1163 / (0.008330 - 0.1163 * v), low, high)),
        h=(1 / (4 * 0.0035), largest(lambda v: 15.5 / (1.62 - 15.5 * v), low, high)),
    )


def cav_slopes():
    low, high = KV_DOMAIN

    def log_slope(base, span, middle, width):
        def at(v):
            s = sigmoid(-(v - 0.010 + middle) / width)
            return span * s * (1 - s) / width / (base + span * s)

        return largest(at, low, high)

    return dict(
        m=(1 / (4 * 0.006), log_slope(0.005, 0.020, 0.025, 0.005)),
        h=(1 / (4 * 0.0064), log_slope(0.020, 0.050, 0.040, 0.007)),
    )


def junction_slopes(threshold, minimum):
    """The relaxation gate's two slopes over |V| in [0, 0.12 V]."""

    def rates(v):
        shift = v - threshold
        a = 1.3 * math.exp(-77.0 * shift)
        x = 0.065 * math.exp(140.0 * shift)
        b = 20.0 * x / (1 + x)
        da, db = -77.0 * a, 140.0 * b / (1 + x)
        return a, b, da, db

    def target(v):
        a, b, da, db = rates(v)
        return (1 - minimum) * abs(da * b - a * db) / (a + b) ** 2

    def log_tau(v):
        a, b, da, db = rates(v)
        return abs(da + db) / (a + b)

    return largest(target, 0.0, V_STAR), largest(log_tau, 0.0, V_STAR)


def slope(pair):
    return pair[0] + TAU_SHARE * pair[1]


# ------------------------------------------------------------------ a world


def two_figures_up(x):
    """x rounded up to two significant figures."""
    if x == 0:
        return 0.0
    e = math.floor(math.log10(x)) - 1
    n = math.ceil(x / 10.0**e - 1e-9)
    return float(f"{n}e{e}")


class World(rules.Block):
    """A Part 2 world: the ionic block with its stores, plasma transport and calcium channels."""

    def __init__(self, world):
        super().__init__(world["ionic"])
        self.world = world
        self.stores = world["stores"]
        self.plasma = world.get("plasma_transport") or {}
        self.cav = world.get("calcium_channels") or {}
        self.u = F / self.RT
        self.membrane_of = {m["inside"]: i for i, m in self.membranes.items()}

    # -------------------------------------------------------------- amounts and concentrations

    def mM(self, cell, part, x):
        c = self.stores[cell]["compartments"][part]
        return c["initial_amount_fmol"][x] / c["volume_pL"]

    def field(self, z=1):
        return abs(z) * F * V_STAR / self.RT

    def chi_z(self, z):
        return 1 + self.field(z)

    # -------------------------------------------------------------- the calcium routes, each
    # (scale, heat scale)

    def calcium_pump(self, pump, ratio):
        """A calcium pump's cycles and heat scale; `ratio` is |ln| of its Ca ratio."""
        s = pump["capacity_fmol_per_s"] * self.end
        g = pump["delta_g0_at_1M_J_per_mol"] - self.RT * math.log(1000)
        fuel = math.log(pump["adp_mM"] * pump["pi_mM"] / pump["atp_mM"])
        heat = 1e-3 * (
            abs(g) + self.RT * abs(fuel) + self.RT * (1 + ratio + 2 * F * V_STAR / self.RT)
        )
        return s, s * heat

    def ratio(self, a, b):
        return abs(math.log(a / b))

    def store_routes(self, cell):
        """leak_Ca, leak_K, release and pump of one store: {name: (scale, heat scale, z)}."""
        m = self.stores[cell]["membrane"]
        out = {}
        for name, x, p in (
            ("leak_Ca", "Ca", m["permeability_m_per_s"]["Ca"]),
            ("leak_K", "K", m["permeability_m_per_s"]["K"]),
            ("release", "Ca", m["release"]["permeability_m_per_s"]),
        ):
            z = self.stores[cell]["species"][x]["valence"]
            a, b = self.mM(cell, "cytosol", x), self.mM(cell, "er", x)
            s = p * m["area_m2"] / FMOL * max(a, b) * self.chi_z(z) * self.end
            heat = s * 1e-3 * self.RT * (1 + self.ratio(a, b) + self.field(z))
            out[name] = (s, heat, z)
        a, b = self.mM(cell, "cytosol", "Ca"), self.mM(cell, "er", "Ca")
        s, heat = self.calcium_pump(m["pump"], self.ratio(a, b))
        out["pump"] = (s, heat, 2)
        return out

    def plasma_routes(self, mid):
        """ca_pump and exchanger of one membrane: {name: (scale, heat scale)}."""
        if mid not in self.plasma:
            return {}
        m = self.membranes[mid]
        ca = self.ratio(self.conc(m["inside"], "Ca"), self.conc(m["outside"], "Ca"))
        na = self.ratio(self.conc(m["inside"], "Na"), self.conc(m["outside"], "Na"))
        out = {}
        p, x = self.plasma[mid]["pump"], self.plasma[mid]["exchanger"]
        if p is not None:
            out["ca_pump"] = self.calcium_pump(p, ca)
        if x is not None:
            s = x["capacity_fmol_per_s"] * self.end * math.exp(F * V_STAR / (2 * self.RT))
            heat = s * 1e-3 * self.RT * (4 + 3 * na + ca + F * V_STAR / self.RT)
            out["exchanger"] = (s, heat)
        return out

    def cav_routes(self, mid):
        """The calcium channels of one membrane: {id: (scale, heat scale)}."""
        out = {}
        for cid, c in self.cav.items():
            if c["membrane_id"] == mid:
                m = self.membranes[mid]
                s = self._passive(
                    c["max_permeability_m_per_s"] * c["abundance"] * m["area_m2"],
                    m["inside"],
                    m["outside"],
                    c["species_id"],
                )
                out[cid] = (s, self._passive_heat({c["species_id"]: s}, m["inside"], m["outside"]))
        return out

    # -------------------------------------------------------------- the reactions

    def totals(self, cell, part):
        """{species: the largest amount that the moieties of the compartment allow}, fmol. The
        moieties follow from the reactions: a product is made of its reactants."""
        s = self.stores[cell]
        amounts = s["compartments"][part]["initial_amount_fmol"]
        parts = {}
        for r in s["reactions"].values():
            if r["compartment"] != part:
                continue
            (product,) = r["products"]
            made = {}
            for x, n in r["reactants"].items():
                for k, v in parts.get(x, {x: 1}).items():
                    made[k] = made.get(k, 0) + n * v
            parts[product] = made
        # What a reaction makes of nothing is a moiety; the rest are made of moieties.
        content = {x: parts.get(x, {x: 1}) for x in amounts}
        total = {}
        for x, n in amounts.items():
            for k, v in content[x].items():
                total[k] = total.get(k, 0.0) + v * n
        return {x: min(total[k] / v for k, v in c.items()) for x, c in content.items()}

    def reactions(self, cell):
        """{reaction: (extent's scale, heat per extent in pJ/fmol, compartment)}."""
        s = self.stores[cell]
        out = {}
        for rid, r in s["reactions"].items():
            part = r["compartment"]
            v = s["compartments"][part]["volume_pL"]
            c0 = s["standard_concentration_mM"]
            most = self.totals(cell, part)
            dmu = math.fsum(
                n * s["species"][x]["standard_mu_RT"] for x, n in r["products"].items()
            ) - math.fsum(n * s["species"][x]["standard_mu_RT"] for x, n in r["reactants"].items())
            k = r["forward_rate_per_s"]

            def rate(side, k):
                value = k * v * c0  # noqa: B023
                for x, n in side.items():
                    value *= (most[x] / (v * c0)) ** n  # noqa: B023
                return value

            s_r = max(rate(r["reactants"], k), rate(r["products"], k * math.exp(dmu))) * self.end
            logs = sum(
                n * abs(math.log(self.mM(cell, part, x) / c0))
                for side in (r["reactants"], r["products"])
                for x, n in side.items()
            )
            out[rid] = (s_r, 1e-3 * self.RT * (1 + abs(dmu) + logs), part)
        return out

    # -------------------------------------------------------------- what a compartment's rows are
    # sums of: lists of (path, scale)

    def membrane_movers(self, mid):
        """{species: [(path, scale)]} of what crosses one membrane, plus each move's charge."""
        m = self.membranes[mid]
        out = {x: [] for x in self.x}
        for x, s in self.leak(mid)[0].items():
            out[x].append((("leak", abs(self.z[x])), s))
        for cid, c in self.channels.items():
            if c["membrane_id"] == mid:
                for x, s in self.channel(cid)[0].items():
                    out[x].append((("channel", abs(self.z[x])), s))
        p = self.pump(mid)
        if p is not None:
            for x, nu in p[1].items():
                out[x].append((("pump", 1), p[0] * nu))
        for name, (s, _) in self.plasma_routes(mid).items():
            if name == "ca_pump":
                out["Ca"].append((("ca_pump", 2), s))
            else:
                out["Ca"].append((("exchanger", 1), s))
                out["Na"].append((("exchanger", 1), 3 * s))
        for s, _ in self.cav_routes(mid).values():
            out["Ca"].append((("cav", 2), s))
        assert m["inside"] in self.cells
        return out

    def cell_movers(self, cell):
        """{species: [(path, scale)]} of the cell's whole ledger (`exchange_x`)."""
        out = self.membrane_movers(self.membrane_of[cell])
        for jid, j in self.junctions.items():
            if cell in (j["from_cell"], j["to_cell"]):
                for x, s in self.junction(jid)[0].items():
                    out[x].append((("junction", abs(self.z[x]), jid), s))
        return out

    def region_movers(self, name):
        out = {x: [] for x in self.x}
        for mid, m in self.membranes.items():
            if m["outside"] == name:
                for x, v in self.membrane_movers(mid).items():
                    out[x] += v
        for fid, f in self.faces.items():
            if name in (f["sender"], f["receiver"]):
                for x, s in self.face(fid)[0].items():
                    out[x].append((("face", abs(self.z[x])), s))
        return out

    def store_movers(self, cell):
        routes = self.store_routes(cell)
        return dict(
            Ca=[
                (("store", 2), routes["leak_Ca"][0]),
                (("store", 2), routes["release"][0]),
                (("store_pump", 2), routes["pump"][0]),
            ],
            K=[(("store", 1), routes["leak_K"][0])],
        )

    # -------------------------------------------------------------- section 8's scales

    def rows(self, cell):
        return list(self.stores[cell]["species"])

    def scales(self):
        s = {}
        cells = {c: self.cell_movers(c) for c in self.cells}
        regions = {o: self.region_movers(o) for o in self.outside}

        def total(movers):
            return {x: sum(v for _, v in rows) for x, rows in movers.items()}

        cell_total = {c: total(m) for c, m in cells.items()}
        region_total = {o: total(m) for o, m in regions.items()}
        plasma = {m: self.plasma_routes(m) for m in self.membranes}
        cav = {m: self.cav_routes(m) for m in self.membranes}
        for name in ("ca_pump", "exchanger"):
            got = [p[name] for p in plasma.values() if name in p]
            if got:
                s[name] = max(v for v, _ in got)
                s["heat_" + name] = max(h for _, h in got)
        got = [v for p in cav.values() for v in p.values()]
        if got:
            s["ca_channel"] = max(v for v, _ in got)
            s["heat_ca_channel"] = max(h for _, h in got)
            s["ca_gate_m"] = s["ca_gate_h"] = 1.0
        for x in self.x:
            s[f"exchange_{x}"] = max(v[x] for v in cell_total.values())
            s[f"n_out_{x}"] = max(v[x] for v in region_total.values())
            s[f"leak_{x}"] = max(self.leak(m)[0][x] for m in self.membranes)
            if self.junctions:
                s[f"junction_{x}"] = max(self.junction(j)[0][x] for j in self.junctions)
            if self.faces:
                s[f"face_{x}"] = max(self.face(f)[0][x] for f in self.faces)
        if self.channels:
            s["channel_K"] = max(next(iter(self.channel(c)[0].values())) for c in self.channels)
            s["gate_m"] = s["gate_h"] = 1.0
        s["pump"] = max(self.pump(m)[0] for m in self.membranes)
        if self.junctions:
            s["junction_gate"] = 1.0
            s["heat_junction"] = max(self.junction(j)[1] for j in self.junctions)
        if self.faces:
            s["heat_face"] = max(self.face(f)[1] for f in self.faces)
        s["heat_membrane"] = max(self.membrane_heat(m) for m in self.membranes)
        s["voltage"] = max(abs(c["initial_voltage_V"]) for c in self.cells.values()) + max(
            F
            * FMOL
            / m["capacitance_F"]
            * sum(abs(self.z[x]) * v for x, v in cell_total[m["inside"]].items())
            for m in self.membranes.values()
        )
        s["phi_out"] = self.RT / F
        stores = {c: self.store_routes(c) for c in self.stores}
        reactions = {c: self.reactions(c) for c in self.stores}
        for name, key in (
            ("store_leak_Ca", "leak_Ca"),
            ("store_leak_K", "leak_K"),
            ("store_pump", "pump"),
            ("store_release", "release"),
        ):
            s[name] = max(v[key][0] for v in stores.values())
        s["heat_store_leak"] = max(v["leak_Ca"][1] + v["leak_K"][1] for v in stores.values())
        s["heat_store_pump"] = max(v["pump"][1] for v in stores.values())
        s["heat_store_release"] = max(v["release"][1] for v in stores.values())
        for r in next(iter(reactions.values())):
            s[f"extent_{r}"] = max(v[r][0] for v in reactions.values())
        for c in self.row_names():
            s[f"cyt_{c}"] = max(self.row_scale(k, "cytosol", c, cell_total) for k in self.stores)
            s[f"store_{c}"] = max(self.row_scale(k, "er", c, cell_total) for k in self.stores)
        # The text's max |V0| is the cells' (the registered 16.02 V is 0.06 V + the rest, where the
        # stores' own V0 is 0).
        s["store_voltage"] = max(abs(c["initial_voltage_V"]) for c in self.cells.values()) + max(
            F
            * FMOL
            / self.stores[k]["membrane"]["capacitance_F"]
            * sum(
                abs(self.stores[k]["species"][c]["valence"])
                * self.row_scale(k, "er", c, cell_total)
                for c in self.rows(k)
            )
            for k in self.stores
        )
        for part, name in (("cytosol", "heat_reactions_cytosol"), ("er", "heat_reactions_store")):
            s[name] = max(
                sum(e * h for e, h, p in v.values() if p == part) for v in reactions.values()
            )
        return {k: v for k, v in s.items() if v != 0.0}

    def row_names(self):
        return self.rows(next(iter(self.stores)))

    def row_scale(self, cell, part, c, cell_total):
        total = 0.0
        if part == "cytosol" and c in self.x:
            total += cell_total[cell][c]
        routes = self.store_routes(cell)
        if c == "Ca":
            total += routes["leak_Ca"][0] + routes["release"][0] + routes["pump"][0]
        if c == "K":
            total += routes["leak_K"][0]
        r_block = self.stores[cell]["reactions"]
        for r, (e, _, p) in self.reactions(cell).items():
            if p == part:
                n = r_block[r]["reactants"].get(c, 0) + r_block[r]["products"].get(c, 0)
                total += n * e
        return total

    # -------------------------------------------------------------- amount_refs

    def touched(self, cell, part):
        s = self.stores[cell]
        out = set()
        for r in s["reactions"].values():
            if r["compartment"] == part:
                out |= set(r["reactants"]) | set(r["products"])
        return out

    def ref(self, cell, part, c):
        n = self.stores[cell]["compartments"][part]["initial_amount_fmol"][c]
        return 7 / 5 * n if c in self.touched(cell, part) else n

    def amount_refs(self, scales):
        out = {}
        for c in self.row_names():
            for part, name in (("cytosol", f"cyt_{c}"), ("er", f"store_{c}")):
                if name in scales:
                    out[name] = max(self.ref(k, part, c) for k in self.stores)
        for x in self.x:
            out[f"n_out_{x}"] = max(c["initial_amount_fmol"][x] for c in self.outside.values())

        def charged(cell, part):
            s = self.stores[cell]["species"]
            return sum(abs(s[c]["valence"]) * self.ref(cell, part, c) for c in self.rows(cell))

        out["voltage"] = max(
            F
            * FMOL
            / m["capacitance_F"]
            * (charged(m["inside"], "cytosol") + charged(m["inside"], "er"))
            for m in self.membranes.values()
        )
        out["store_voltage"] = max(
            F * FMOL / self.stores[k]["membrane"]["capacitance_F"] * charged(k, "er")
            for k in self.stores
        )
        return out

    # -------------------------------------------------------------- the closure, section 8

    def conductances(self):
        """(the faces' conductances over the free regions as (row sum factor, the largest row sum
        of the inverse), or None)."""
        gauge = self.b["closure"]["gauge_reference"]
        free = [o for o in self.outside if o != gauge]
        if not free or not self.faces:
            return None
        edges = []
        for f in self.faces.values():
            total = 0.0
            for x, d in f["diffusivity_m2_per_s"].items():
                a, c = self.conc(f["sender"], x), self.conc(f["receiver"], x)
                mean = a if a == c else (a - c) / math.log(a / c)
                total += self.z[x] ** 2 * d * f["area_m2"] / f["length_m"] * mean
            edges.append((f["sender"], f["receiver"], F * F / self.RT * total))
        sums = {o: sum(g for a, c, g in edges if o in (a, c)) for o in free}
        n = len(free)
        k = [[0.0] * n for _ in range(n)]
        for i, o in enumerate(free):
            k[i][i] = sums[o]
        for a, c, g in edges:
            if a in free and c in free:
                i, j = free.index(a), free.index(c)
                k[i][j] -= g
                k[j][i] -= g
        inverse = rules._invert(k)
        rows = [sum(abs(v) for v in inverse[i]) for i in range(n)]
        factor = max(r * sums[o] for r, o in zip(rows, free, strict=True))
        ratio = max(g for _, _, g in edges) / min(sums.values())
        return factor, max(rows), ratio

    def stage_errors(self, step, row_factor=None):
        """The stage's potential errors (V), each the largest over its entities; `step` is the
        family's smallest (the retry's), where the free offset's is largest."""
        cm = {i: m["capacitance_F"] for i, m in self.membranes.items()}
        one = {i: CHARGE_RTOL * V_STAR + 2 * CHARGE_ATOL_C / c for i, c in cm.items()}
        out = dict(membrane=max(one.values()))
        pairs = [
            one[self.membrane_of[j["from_cell"]]] + one[self.membrane_of[j["to_cell"]]]
            for j in self.junctions.values()
        ]
        if pairs:
            out["junction"] = max(pairs)
        out["store"] = max(
            CHARGE_RTOL * V_STAR + CHARGE_ATOL_C / s["membrane"]["capacitance_F"]
            for s in self.stores.values()
        )
        c = self.conductances()
        if c is not None:
            factor = max(ROW_FACTOR, c[0]) if row_factor is None else row_factor
            out["offset_engine"] = factor * CHARGE_RTOL * V_STAR + CHARGE_ATOL_C * c[1] / (
                GAMMA * step
            )
            out["offset"] = out["offset_engine"] + LEGACY_OFFSET * V_STAR
        return out

    def gate_slopes(self):
        out = {}
        if self.channels:
            kv = kv_slopes()
            out["gate_m"], out["gate_h"] = slope(kv["m"]), slope(kv["h"])
        if self.cav:
            cav = cav_slopes()
            out["ca_gate_m"], out["ca_gate_h"] = slope(cav["m"]), slope(cav["h"])
        if self.junctions:
            out["junction_gate"] = max(
                slope(
                    junction_slopes(
                        j["gate"]["threshold_voltage_V"], j["gate"]["minimum_open_fraction"]
                    )
                )
                for j in self.junctions.values()
            )
        return out

    def shares(self, delta):
        """The shares of s by path, at the potential errors `delta`."""
        u, g = self.u, self.gate_slopes()
        out = {}

        def field(z, d):
            return z * u * d / self.chi_z(z)

        for z in (1, 2):
            out[("leak", z)] = field(z, delta["membrane"])
            out[("store", z)] = field(z, delta["store"])
            if "offset" in delta:
                out[("face", z)] = field(z, delta["offset"])
            if self.channels:
                out[("channel", z)] = (
                    field(z, delta["membrane"]) + (g["gate_m"] + g["gate_h"]) * delta["membrane"]
                )
            if self.junctions:
                out[("junction", z)] = (
                    field(z, delta["junction"]) + g["junction_gate"] * delta["junction"]
                )
            if self.cav:
                out[("cav", z)] = (
                    field(z, delta["membrane"])
                    + (2 * g["ca_gate_m"] + g["ca_gate_h"]) * delta["membrane"]
                )
        out[("pump", 1)] = u * delta["membrane"]
        out[("ca_pump", 2)] = 2 * u * delta["membrane"]
        out[("exchanger", 1)] = 1.5 * u * delta["membrane"]
        out[("store_pump", 2)] = 2 * u * delta["store"]
        return out

    def affinity(self, kind, z, delta):
        """The affinity's share of a heat."""
        u = self.u
        d = {
            "leak": "membrane", "channel": "membrane", "pump": "membrane", "ca_pump": "membrane",
            "exchanger": "membrane", "cav": "membrane", "junction": "junction", "face": "offset",
            "store": "store", "store_pump": "store",
        }[kind]  # fmt: skip
        if kind in ("pump", "exchanger"):
            return u * delta[d] / self.chi_z(1)
        if kind in ("ca_pump", "store_pump"):
            return 2 * u * delta[d] / self.chi_z(2)
        return z * u * delta[d] / self.chi_z(z)

    def moved_V(self, step, **kw):
        """(voltage, store_voltage): what the stages' errors have done to the charges, as
        potentials, plus the observed row's own solve (before any rounding)."""
        delta = self.stage_errors(step, **kw)
        share = self.shares(delta)
        v = max(
            F
            * FMOL
            / self.membranes[self.membrane_of[c]]["capacitance_F"]
            * self._charge(self.cell_movers(c), share)
            for c in self.cells
        )
        w = max(
            F
            * FMOL
            / self.stores[c]["membrane"]["capacitance_F"]
            * self._charge(self.store_movers(c), share)
            for c in self.stores
        )
        return delta["membrane"] + v, delta["store"] + w, v, w

    @staticmethod
    def _charge(movers, share):
        """Sum of one-pass share x scale x the move's charge: |z| of a passive route, and of a
        cycle the charge of a cycle, once (not once a species)."""
        total, cycles = 0.0, {}
        for x, rows in movers.items():
            for path, s in rows:
                kind, z = path[:2]
                if kind == "pump":
                    cycles["pump"] = max(cycles.get("pump", 0.0), 0.0)
                    if x == "Na":
                        total += share[("pump", 1)] * s / 3
                elif kind == "exchanger":
                    if x == "Ca":
                        total += share[("exchanger", 1)] * s
                else:
                    total += share[(kind, z)] * s * z
        return total

    def closure_sums(self, step, drift_V, **kw):
        """{entry: its sum over the routes, in its unit} at the stage's errors plus the drift."""
        stage = self.stage_errors(step, **kw)
        delta = dict(
            membrane=stage["membrane"] + drift_V["voltage"],
            store=stage["store"] + drift_V["store_voltage"],
        )
        if "junction" in stage:
            delta["junction"] = stage["junction"] + 2 * drift_V["voltage"]
        if "offset" in stage:
            delta["offset"] = stage["offset"] + drift_V["phi_out"]
        share, g = self.shares(delta), self.gate_slopes()
        out = {}

        def add(rows):
            return sum(share[p[:2]] * s for p, s in rows)

        cells = {c: self.cell_movers(c) for c in self.cells}
        stores = {c: self.store_movers(c) for c in self.stores}
        regions = {o: self.region_movers(o) for o in self.outside}
        for x in self.x:
            z = abs(self.z[x])
            out[f"leak_{x}"] = share[("leak", z)] * max(self.leak(m)[0][x] for m in self.membranes)
            out[f"exchange_{x}"] = max(add(m[x]) for m in cells.values())
            out[f"n_out_{x}"] = max(add(m[x]) for m in regions.values())
            if self.junctions:
                out[f"junction_{x}"] = share[("junction", z)] * max(
                    self.junction(j)[0][x] for j in self.junctions
                )
            if self.faces:
                out[f"face_{x}"] = share[("face", z)] * max(self.face(f)[0][x] for f in self.faces)
        for c in self.channels:
            z = abs(self.z[self.channels[c]["species_id"]])
            s = next(iter(self.channel(c)[0].values()))
            out["channel_K"] = max(out.get("channel_K", 0.0), share[("channel", z)] * s)
        out["pump"] = share[("pump", 1)] * max(self.pump(m)[0] for m in self.membranes)
        for m in self.membranes:
            for name, (s, h) in self.plasma_routes(m).items():
                z = {"ca_pump": 2, "exchanger": 1}[name]
                out[name] = max(out.get(name, 0.0), share[(name, z)] * s)
                heat = (share[(name, z)] + self.affinity(name, z, delta)) * h
                out["heat_" + name] = max(out.get("heat_" + name, 0.0), heat)
            for s, h in self.cav_routes(m).values():
                out["ca_channel"] = max(out.get("ca_channel", 0.0), share[("cav", 2)] * s)
                heat = (share[("cav", 2)] + self.affinity("cav", 2, delta)) * h
                out["heat_ca_channel"] = max(out.get("heat_ca_channel", 0.0), heat)
        for name, value in g.items():
            d = "junction" if name == "junction_gate" else "membrane"
            out[name] = value * delta[d]
        # The heats, route by route.
        out["heat_membrane"] = max(self._membrane_heat(m, share, delta) for m in self.membranes)
        if self.junctions:
            out["heat_junction"] = max(
                self._passive_heat_sum("junction", self.junction(j)[0],
                                       (v["from_cell"], v["to_cell"]), share, delta)
                for j, v in self.junctions.items()
            )  # fmt: skip
        if self.faces:
            out["heat_face"] = max(
                self._passive_heat_sum("face", self.face(f)[0], (v["sender"], v["receiver"]),
                                       share, delta)
                for f, v in self.faces.items()
            )  # fmt: skip
        for c in self.stores:
            r = self.store_routes(c)

            def heat(name, r=r):
                _, h, z = r[name]
                kind = "store_pump" if name == "pump" else "store"
                return (share[(kind, z)] + self.affinity(kind, z, delta)) * h

            for entry, value in (
                ("store_leak_Ca", share[("store", 2)] * r["leak_Ca"][0]),
                ("store_leak_K", share[("store", 1)] * r["leak_K"][0]),
                ("store_release", share[("store", 2)] * r["release"][0]),
                ("store_pump", share[("store_pump", 2)] * r["pump"][0]),
                ("heat_store_leak", heat("leak_Ca") + heat("leak_K")),
                ("heat_store_release", heat("release")),
                ("heat_store_pump", heat("pump")),
            ):
                out[entry] = max(out.get(entry, 0.0), value)
            movers = dict(
                cytosol=add(cells[c]["Ca"]) + add(stores[c]["Ca"]), er=add(stores[c]["Ca"])
            )
            heats = {"cytosol": 0.0, "er": 0.0}
            block = self.stores[c]["reactions"]
            calcium = {}
            for rid, (_, per, part) in self.reactions(c).items():
                names = set(block[rid]["reactants"]) | set(block[rid]["products"])
                value = movers[part] if "Ca" in names else 0.0
                out[f"extent_{rid}"] = max(out.get(f"extent_{rid}", 0.0), value)
                heats[part] += value * per
                if "Ca" in names:
                    calcium.setdefault(part, set()).update(names)
            for part, entry in (("cytosol", "heat_reactions_cytosol"),
                                ("er", "heat_reactions_store")):  # fmt: skip
                out[entry] = max(out.get(entry, 0.0), heats[part])
            for row in self.rows(c):
                cyt = er = 0.0
                if row in calcium.get("cytosol", {"Ca"}):
                    cyt = movers["cytosol"]
                elif row in self.x:
                    cyt = add(cells[c][row]) + add(stores[c].get(row, []))
                if row in calcium.get("er", {"Ca"}):
                    er = movers["er"]
                elif row in stores[c]:
                    er = add(stores[c][row])
                out[f"cyt_{row}"] = max(out.get(f"cyt_{row}", 0.0), cyt)
                out[f"store_{row}"] = max(out.get(f"store_{row}", 0.0), er)
        return out, stage, delta, share

    def _membrane_heat(self, mid, share, delta):
        m = self.membranes[mid]
        total = self._passive_heat_sum(
            "leak", self.leak(mid)[0], (m["inside"], m["outside"]), share, delta
        )
        for cid, c in self.channels.items():
            if c["membrane_id"] == mid:
                total += self._passive_heat_sum(
                    "channel", self.channel(cid)[0], (m["inside"], m["outside"]), share, delta
                )
        p = self.pump(mid)
        if p is not None:
            total += (share[("pump", 1)] + self.affinity("pump", 1, delta)) * p[2]
        return total

    def _passive_heat_sum(self, kind, scale, ends, share, delta):
        total = 0.0
        for x, s in scale.items():
            z = abs(self.z[x])
            heat = self._passive_heat({x: s}, *ends)
            total += (share[(kind, z)] + self.affinity(kind, z, delta)) * heat
        return total


def terms(sums, scales):
    """The entries' own numbers: those above the share of their scale, rounded up."""
    return {k: two_figures_up(v) for k, v in sums.items() if k in scales and v > SHARE * scales[k]}


# ------------------------------------------------------------------ check


def drift_of(worlds, steps):
    """`closure_terms_V`: the largest over the worlds of the file, rounded up to two figures."""
    v = max(World(w).moved_V(steps[name])[0] for name, w in worlds.items())
    s = max(World(w).moved_V(steps[name])[1] for name, w in worlds.items())
    return dict(phi_out=CLOSE_PHI_V, voltage=two_figures_up(v), store_voltage=two_figures_up(s))


def check(path):
    inputs = json.loads(Path(path).read_text())
    children = {k: w for k, w in inputs["worlds"].items() if "ionic" in w}
    retry = {k: 1.5625e-06 for k in children}
    drift = drift_of(children, retry)
    print("closure_terms_V", drift)
    worst = 0
    for name, w in children.items():
        world = World(w)
        scales = world.scales()
        refs = world.amount_refs(scales)
        sums, stage, delta, share = world.closure_sums(retry[name], drift)
        mine = terms(sums, scales)
        for part, got in (("scales", scales), ("amount_refs", refs)):
            want = w[part]
            if set(got) != set(want):
                print(name, part, "keys differ", set(got) ^ set(want))
            for k in set(got) & set(want):
                r = abs(got[k] - want[k]) / abs(want[k])
                worst = max(worst, r)
                if r > 8 * EPS:
                    print(name, part, k, got[k], want[k], f"{r:.2e}")
        want = w["closure_terms"]
        for k in sorted(set(mine) | set(want)):
            if mine.get(k) != want.get(k):
                print(name, "closure", k, mine.get(k), want.get(k), sums[k], SHARE * scales[k])
        print(
            name, len(scales), len(refs), len(mine), len(want), "moved", world.moved_V(retry[name])
        )
        print(
            "  stage", stage, "\n  with the drift", delta, "\n  conductances", world.conductances()
        )
        for k, v in w["closure_terms_V"].items():
            if drift[k] != v:
                print(name, k, drift[k], v)
    print("the largest relative departure of a scale or a reference:", f"{worst:.2e}")


if __name__ == "__main__":
    if sys.argv[1:2] != ["check"]:
        raise SystemExit("usage: rules2.py check [inputs_part2.json]")
    check(sys.argv[2] if len(sys.argv) > 2 else SPEC / "inputs_part2.json")
