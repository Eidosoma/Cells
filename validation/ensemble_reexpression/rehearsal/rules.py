"""The rules of the spec folder that form the rehearsal's files from a world's block alone.

SPEC.md section 0 (constants), section 2.2 (derived declarations), section 4 (the grid rule),
section 5 (the scales and `amount_refs`) and section 6 (the bands' terms), CRITERIA.md section 1,
4.3 (the order rule and the band at U_c = 0). Standard library only: it reads no engine, no
builder's and no judge's code. `rules.py check` recomputes `scales`, `amount_refs` and
`closure_terms_V` of the registered worlds from their blocks and compares them with inputs.json's
numbers.
"""

import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SPEC = HERE.parent / "spec"

N_A, K_B, E = 6.02214076e23, 1.380649e-23, 1.602176634e-19
F = N_A * E  # C/mol, each the double product (SPEC section 0).
R = N_A * K_B  # J/mol/K.
FMOL = 1e-15  # mol.
EPS = 2.0**-52
V_STAR = 0.12  # V, the gate law's domain.
CLOSE = 4e-12  # e_close of every readout but phi_out (SPEC section 6).
CLOSE_PHI_V = 4.3e-12 * V_STAR  # Two codes at 2.13e-12 V*, rounded up (SPEC section 6).


# ------------------------------------------------------------------ derived declarations, section
# 2.2


def capacitance(area_m2, specific_F_per_m2):
    return area_m2 * specific_F_per_m2


def charge(capacitance_F, voltage_V):
    return capacitance_F * voltage_V


def countercharge(charges):
    """Minus the correctly rounded sum of the charges of the cells that face the region."""
    return -math.fsum(charges) if charges else 0.0


def fixed_charge_fmol(valence, amounts, charge_C):
    """The fixed charge that closes a compartment's own charge, before it is rounded."""
    return charge_C / (F * FMOL) - math.fsum(valence[x] * n for x, n in amounts.items())


def charge_residual_C(valence, amounts, fixed, charge_C):
    """What a declared fixed charge leaves of the rule (C): the charge of its amounts and its fixed
    charge, less the charge that its capacitors hold (the captured worlds leave up to 5.1e-24 C)."""
    total = math.fsum((fixed, *(valence[x] * n for x, n in amounts.items())))
    return F * FMOL * total - charge_C


# ------------------------------------------------------------------ the grid, section 4


def on_grid(t, h):
    """SPEC section 4: t is on the grid if it differs from some k h by at most 2 eps t."""
    k = round(t / h)
    return any(abs(t - i * h) <= 2 * EPS * t for i in (k - 1, k, k + 1) if i >= 0)


def grid_steps(end_s, step_s):
    n = round(end_s / step_s)
    if not on_grid(end_s, step_s):
        raise ValueError(f"end {end_s!r} is no multiple of {step_s!r}")
    return n


# ------------------------------------------------------------------ a world's parts


class Block:
    """The ionic block of a world (SPEC section 2.5), read by name."""

    def __init__(self, ionic, *, channels_open=True):
        b = self.b = ionic
        self.T = b["temperature_K"]
        self.end = b["end_s"]
        self.z = b["species"]
        self.x = list(self.z)
        self.cells = b["cells"]
        self.outside = b["outside"]
        self.membranes = b["membranes"]
        self.channels = b["channels"] or {}
        self.junctions = b["junctions"] or {}
        self.faces = b["faces"] or {}
        self.RT = R * self.T

    def chi(self, x):
        return 1 + abs(self.z[x]) * F * V_STAR / self.RT

    def conc(self, name, x):
        c = self.cells.get(name) or self.outside[name]
        return c["initial_amount_fmol"][x] / c["volume_pL"]

    # Each route: its scale per species (fmol) and its heat scale (pJ).
    def _passive(self, factor_m3_s, a, b, x):
        """factor: P A or D A/L in m^3/s. The scale of one species of one route."""
        c = max(self.conc(a, x), self.conc(b, x))
        return factor_m3_s / FMOL * c * self.chi(x) * self.end

    def _passive_heat(self, scale, a, b):
        total = 0.0
        for x, s in scale.items():
            log = abs(math.log(self.conc(a, x) / self.conc(b, x)))
            total += s * 1e-3 * self.RT * (1 + log + abs(self.z[x]) * F * V_STAR / self.RT)
        return total

    def leak(self, mid):
        m = self.membranes[mid]
        scale = {
            x: self._passive(p * m["area_m2"], m["inside"], m["outside"], x)
            for x, p in m["passive"]["permeability_m_per_s"].items()
        }
        return scale, self._passive_heat(scale, m["inside"], m["outside"])

    def channel(self, cid):
        c = self.channels[cid]
        m = self.membranes[c["membrane_id"]]
        x = c["species_id"]
        s = self._passive(
            c["max_permeability_m_per_s"] * c["abundance"] * m["area_m2"],
            m["inside"],
            m["outside"],
            x,
        )
        scale = {x: s}
        return scale, self._passive_heat(scale, m["inside"], m["outside"])

    def junction(self, jid):
        j = self.junctions[jid]
        scale = {
            x: self._passive(p * j["area_m2"], j["from_cell"], j["to_cell"], x)
            for x, p in j["permeability_m_per_s"].items()
        }
        return scale, self._passive_heat(scale, j["from_cell"], j["to_cell"])

    def face(self, fid):
        f = self.faces[fid]
        scale = {
            x: self._passive(d * f["area_m2"] / f["length_m"], f["sender"], f["receiver"], x)
            for x, d in f["diffusivity_m2_per_s"].items()
        }
        return scale, self._passive_heat(scale, f["sender"], f["receiver"])

    def drive(self, pump):
        """|DeltaG0| + R T |ln(ADP Pi/(1000 ATP))|, J/mol."""
        m = pump["metabolism"]
        return abs(m["delta_g0_J_per_mol"]) + self.RT * abs(
            math.log(m["adp_mM"] * m["pi_mM"] / (1000 * m["atp_mM"]))
        )

    def pump(self, mid):
        """(cycles' scale, {species: nu}, heat scale, work scale) or None."""
        m = self.membranes[mid]
        p = m["pump"]
        if p is None:
            return None
        cycles = p["capacity_fmol_per_s"] * self.end
        na, k = p["roles"]["sodium"], p["roles"]["potassium"]
        field = F * V_STAR / self.RT
        ratios = {
            x: abs(math.log(self.conc(m["inside"], x) / self.conc(m["outside"], x)))
            for x in (na, k)
        }
        heat = (
            cycles
            * 1e-3
            * (
                self.drive(p)
                + 3 * self.RT * (1 + ratios[na] + field)
                + 2 * self.RT * (1 + ratios[k] + field)
            )
        )
        work = cycles * 1e-3 * self.drive(p)
        return cycles, {x: abs(v) for x, v in p["stoichiometry"].items()}, heat, work

    # -------------------------------------------------------------- sums over the routes of a
    # compartment

    def routes_of(self, name):
        """{species: the sum of the scales of the routes that touch the compartment}."""
        total = {x: 0.0 for x in self.x}

        def add(scale):
            for x, s in scale.items():
                total[x] += s

        for mid, m in self.membranes.items():
            if name in (m["inside"], m["outside"]):
                add(self.leak(mid)[0])
                for cid, c in self.channels.items():
                    if c["membrane_id"] == mid:
                        add(self.channel(cid)[0])
                p = self.pump(mid)
                if p is not None:
                    add({x: p[0] * nu for x, nu in p[1].items()})
        for jid, j in self.junctions.items():
            if name in (j["from_cell"], j["to_cell"]):
                add(self.junction(jid)[0])
        for fid, f in self.faces.items():
            if name in (f["sender"], f["receiver"]):
                add(self.face(fid)[0])
        return total

    def membrane_heat(self, mid):
        total = self.leak(mid)[1]
        for cid, c in self.channels.items():
            if c["membrane_id"] == mid:
                total += self.channel(cid)[1]
        p = self.pump(mid)
        return total + (0.0 if p is None else p[2])

    # -------------------------------------------------------------- section 5

    def scales(self, consumer):
        """The scale of every entry the consumer has, by name (SPEC 5, READOUTS 3)."""
        s, x3 = {}, self.x
        cells = {c: self.routes_of(c) for c in self.cells}
        regions = {o: self.routes_of(o) for o in self.outside}
        leak = {m: self.leak(m) for m in self.membranes}
        junction = {j: self.junction(j) for j in self.junctions}
        face = {f: self.face(f) for f in self.faces}
        channel = {c: self.channel(c) for c in self.channels}
        pump = {m: self.pump(m) for m in self.membranes}
        pumped = {m: p for m, p in pump.items() if p is not None}
        for x in x3:
            s[f"n_cell_{x}"] = max(v[x] for v in cells.values())
            s[f"n_out_{x}"] = max(v[x] for v in regions.values())
            if any(self.membranes[m]["passive"]["permeability_m_per_s"][x] for m in self.membranes):
                s[f"leak_{x}"] = max(v[0][x] for v in leak.values())
            if junction:
                s[f"junction_{x}"] = max(v[0][x] for v in junction.values())
            if face:
                s[f"face_{x}"] = max(v[0][x] for v in face.values())
        if channel:
            s["channel_K"] = max(next(iter(v[0].values())) for v in channel.values())
            s["gate_m"] = s["gate_h"] = 1.0
        if pumped:
            s["pump"] = max(p[0] for p in pumped.values())
        if junction:
            s["junction_gate"] = 1.0
            s["heat_junction"] = max(v[1] for v in junction.values())
        if face:
            s["heat_face"] = max(v[1] for v in face.values())
        if pumped or channel or any(sum(v[0].values()) for v in leak.values()):
            s["heat_membrane"] = max(self.membrane_heat(m) for m in self.membranes)
        s["voltage"] = max(abs(c["initial_voltage_V"]) for c in self.cells.values()) + max(
            F
            * FMOL
            / m["capacitance_F"]
            * sum(abs(self.z[x]) * v for x, v in cells[m["inside"]].items())
            for m in self.membranes.values()
        )
        if consumer == "jupiter":
            s["phi_out"] = self.RT / F
        s["energy_identity"] = self.energy_scale(
            cells, regions, leak, junction, face, channel, pumped, s["voltage"]
        )
        return s

    def energy_scale(self, cells, regions, leak, junction, face, channel, pumped, voltage):
        total = sum(self.membrane_heat(m) for m in self.membranes)
        total += sum(v[1] for v in junction.values()) + sum(v[1] for v in face.values())
        total += sum(p[3] for p in pumped.values())
        for group in (cells, regions):
            for name, routes in group.items():
                for x, s in routes.items():
                    total += s * 1e-3 * self.RT * (1 + abs(math.log(self.conc(name, x))))
        for m in self.membranes.values():
            total += 1e12 * m["capacitance_F"] * voltage**2
        return total

    def amount_refs(self, voltage):
        refs = {}
        for x in self.x:
            refs[f"n_cell_{x}"] = max(c["initial_amount_fmol"][x] for c in self.cells.values())
        for x in self.x:
            refs[f"n_out_{x}"] = max(c["initial_amount_fmol"][x] for c in self.outside.values())
        refs["voltage"] = max(
            F
            * FMOL
            / m["capacitance_F"]
            * sum(
                abs(self.z[x]) * n
                for x, n in self.cells[m["inside"]]["initial_amount_fmol"].items()
            )
            for m in self.membranes.values()
        )
        energy = 0.0
        for name, c in (*self.cells.items(), *self.outside.items()):
            for x, n in c["initial_amount_fmol"].items():
                energy += 1e-3 * self.RT * (1 + abs(math.log(self.conc(name, x)))) * n
        for m in self.membranes.values():
            charged = sum(
                abs(self.z[x]) * n
                for x, n in self.cells[m["inside"]]["initial_amount_fmol"].items()
            )
            energy += (
                1e12 * m["capacitance_F"] * voltage * (F * FMOL / m["capacitance_F"]) * charged
            )
        refs["energy_identity"] = energy
        return refs


def closure_terms(consumer):
    return {"phi_out": CLOSE_PHI_V} if consumer == "jupiter" else {}


def derived(consumer, ionic):
    """`scales`, `amount_refs` and `closure_terms_V` of a world, from its block alone."""
    block = Block(ionic)
    scales = block.scales(consumer)
    return dict(
        scales=scales,
        amount_refs=block.amount_refs(scales["voltage"]),
        closure_terms_V=closure_terms(consumer),
    )


# ------------------------------------------------------------------ the free offsets, section 6


def field_factors(ionic):
    """(the row-sum factor, the largest conductance over the smallest incident sum, the free
    regions) at the declared initial values: the two numbers that SPEC section 6 takes from the
    JUPITER cluster (2.01 and 0.53). A free region is one that is not the gauge: the cells that
    face it share its offset, so a junction between cells of two regions is an edge of the
    conductances too. The first number is the largest over the free regions of their row sum of the
    inverse conductance matrix times their own incident sum. None without a free region."""
    b = Block(ionic)
    gauge = ionic["closure"]["gauge_reference"]
    free = [o for o in b.outside if o != gauge]
    if not free or not b.faces:
        return None
    region = {m["inside"]: m["outside"] for m in b.membranes.values()}
    edges = {}
    for fid, f in b.faces.items():
        total = 0.0
        for x, d in f["diffusivity_m2_per_s"].items():
            a, c = b.conc(f["sender"], x), b.conc(f["receiver"], x)
            mean = a if a == c else (a - c) / math.log(a / c)
            total += b.z[x] ** 2 * d * f["area_m2"] / f["length_m"] * mean
        edges[fid] = (f["sender"], f["receiver"], F * F / b.RT * total)
    for jid, j in b.junctions.items():
        ends = region[j["from_cell"]], region[j["to_cell"]]
        if ends[0] != ends[1]:
            total = sum(
                b.z[x] ** 2 * p * max(b.conc(j["from_cell"], x), b.conc(j["to_cell"], x))
                for x, p in j["permeability_m_per_s"].items()
            )
            slope = F * F / b.RT * j["area_m2"] * total * j["gate"]["initial_gate"]
            edges[jid] = (*ends, slope)
    sums = {o: sum(g for a, c, g in edges.values() if o in (a, c)) for o in free}
    n = len(free)
    k = [[0.0] * n for _ in range(n)]
    for i, o in enumerate(free):
        k[i][i] = sums[o]
    for a, c, g in edges.values():
        if a in free and c in free:
            i, j = free.index(a), free.index(c)
            k[i][j] -= g
            k[j][i] -= g
    inverse = _invert(k)
    row = max(sum(abs(v) for v in inverse[i]) * sums[o] for i, o in enumerate(free))
    return row, max(g for _, _, g in edges.values()) / min(sums.values()), sorted(free)


def _invert(a):
    n = len(a)
    m = [row[:] + [1.0 if i == j else 0.0 for j in range(n)] for i, row in enumerate(a)]
    for c in range(n):
        p = max(range(c, n), key=lambda r: abs(m[r][c]))
        m[c], m[p] = m[p], m[c]
        d = m[c][c]
        m[c] = [v / d for v in m[c]]
        for r in range(n):
            if r != c:
                f = m[r][c]
                m[r] = [v - f * w for v, w in zip(m[r], m[c], strict=True)]
    return [row[n:] for row in m]


# ------------------------------------------------------------------ bands, CRITERIA sections 1 and
# 4.3


def e_round(steps, s):
    return 8 * EPS * (steps + 1) * s


def e_store(steps, ref):
    return 2.5 * EPS * (steps + 1) * ref


def e_close(entry, scales, closure):
    if entry in closure:
        return closure[entry]
    return CLOSE * scales[base(entry, scales)]


def base(entry, scales):
    """The readout an entry takes its scale from (READOUTS: `<readout>_summary`)."""
    return entry if entry in scales else entry.removesuffix("_summary")


def legacy_threshold(steps, s):
    """10 x 8 x 2^-52 x (S + 1) x s: the legacy side's theta (e_store is 0 there)."""
    return 10 * e_round(steps, s)


def order_class(d2, d1, theta, p=4.0):
    if d2 <= theta and d1 <= theta:
        return "unresolved"
    if d2 <= theta or d1 <= theta:
        return "mixed"
    q = math.log2(d2 / d1) if d1 > 0 else math.inf
    return "resolved" if p - 0.5 <= q <= 4.5 else "resolved outside its window"


# ------------------------------------------------------------------ check


def check():
    inputs = json.loads((SPEC / "inputs.json").read_text())
    worst = {}
    for name, w in inputs["worlds"].items():
        mine = derived(w["consumer"], w["ionic"])
        for part in ("scales", "amount_refs", "closure_terms_V"):
            if set(mine[part]) != set(w[part]):
                raise SystemExit(f"{name}: {part} keys differ: {set(mine[part]) ^ set(w[part])}")
            for k, v in w[part].items():
                got = mine[part][k]
                if got != v:
                    r = abs(got - v) / abs(v)
                    worst[(name, part, k)] = r
                    if r > 4 * EPS:
                        raise SystemExit(f"{name} {part} {k}: {got!r} against {v!r}")
        if w["consumer"] in ("jupiter", "base"):
            row, conductance, free = field_factors(w["ionic"])
            print(name, f"row factor {row:.4f}, conductance ratio {conductance:.4f}, free {free}")
    print(f"{len(inputs['worlds'])} worlds agree; {len(worst)} leaves differ in the last bits")
    for k, r in sorted(worst.items()):
        print(" ", *k, f"{r:.2e}")


if __name__ == "__main__":
    if sys.argv[1:] != ["check"]:
        raise SystemExit("usage: rules.py check")
    check()
