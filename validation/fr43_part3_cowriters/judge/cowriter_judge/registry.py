"""The registered inputs (`inputs.json`, or the invented set's `inputs_invented.json`) as the judge reads them.

Every number of a world comes from the inputs file passed in. What is written here is the text's own: names of
readouts, the readouts' scale lines (READOUTS.md §2), the operation counts m (LAWS.md §7), u = 2^-53 and the
constants of the criteria (CRITERIA.md).
"""

from __future__ import annotations

import functools
import math
from dataclasses import dataclass, field
from decimal import Decimal, localcontext
from fractions import Fraction
from typing import Any

from . import strictjson as sj

U = Fraction(1, 2**53)  # LAWS.md §0: the unit roundoff of binary64
UF = 2.0**-53

M_TIME = 4  # LAWS.md §7: an event's time
M_ROW = 16  # LAWS.md §7: a row or a book at a sample

# TABLE.md §3: the series of each world kind, in the table's order.
SERIES = {
    "reactions": ["n_S_c", "n_S_o", "n_X", "n_Y", "n_W", "xi_1", "xi_2", "moved"],
    "gene": ["n_R_c", "n_R_o", "n_N", "n_M", "n_Pi", "free", "engaged", "transit", "inits", "exits", "made", "lost",
             "moved"],
}

# READOUTS.md §2: the scale of a readout, as the terms whose absolute values are summed (at t; '0' marks t = 0).
# A readout with no line has the largest |value| over the copies and samples.
SCALE_LINES = {
    "n_S_c": [("n_S_c", "t"), ("n_S_c", "0"), ("xi_1", "t"), ("xi_2", "t"), ("moved", "t")],
    "n_S_o": [("n_S_o", "t"), ("n_S_o", "0"), ("moved", "t")],
    "moved": [("moved", "t")],
    "xi_2": [("xi_2", "t")],
    "lost": [("lost", "t")],
    "made": [("made", "t")],
    "exits": [("exits", "t")],
    "n_R_c": [("n_R_c", "t"), ("n_R_c", "0"), ("made", "t"), ("lost", "t"), ("moved", "t")],
    "n_R_o": [("n_R_o", "t"), ("n_R_o", "0"), ("moved", "t")],
}

PLANT_MARGIN = 10.0 * (1.0 - 1e-9)  # CRITERIA.md §6.2 and §4.2
PAIR_FACTOR = 10.0  # CRITERIA.md §3.5
RESOLVE_FACTOR = 10.0  # CRITERIA.md §3.3
SIZING_ORDER_HALF_WINDOW = 0.4  # CRITERIA.md §4.2: [p - 0.4, p + 0.4]
ORDER_HALF_WINDOW = 0.5  # CRITERIA.md §3.3: [p - 1/2, p + 1/2]
P3_C0_HALF_WINDOW = 0.25  # CRITERIA.md §4.2, §6.2: within 1/4 of p - 1
P3_WINDOW = (-1.5, -0.5)  # CRITERIA.md §6.3: [p - 3/2, p - 1/2]
START_ULPS = 4  # READOUTS.md §4: 4 u |declared|
REL_TIME = 1e-12  # sample times, restart time, echo numbers: 1e-12 relative


def dec(value: float | int) -> Decimal:
    """The declared decimal of a JSON number (its shortest round-trip text)."""
    return Decimal(repr(value)) if isinstance(value, float) else Decimal(value)


@functools.lru_cache(maxsize=65536)
def steps(t: float, h: float) -> Fraction:
    """S = t/h from the registered grid, as an exact rational of the declared decimals (an integer on the grid)."""
    with localcontext() as ctx:
        ctx.prec = 60
        return Fraction(dec(t)) / Fraction(dec(h))


def e_round(m: int, s_steps: Fraction | int, scale: float) -> float:
    """LAWS.md §7: e_round = m (S + 1) u s."""
    return float(m * (Fraction(s_steps) + 1) * U * Fraction(scale))


def copy_fmol(n_a_text: str) -> float:
    """LAWS.md §0: COPY = 10^15/N_A fmol, the decimal quotient read as its nearest double."""
    with localcontext() as ctx:
        ctx.prec = 80
        return float(Decimal(10) ** 15 / Decimal(n_a_text))


@dataclass
class Channel:
    id: str
    jump: tuple[int, ...]
    reactants: dict[str, int]


@dataclass
class World:
    name: str
    kind: str
    block: dict
    end_s: float
    samples: list[float]
    rungs: list[float]
    retry_rung: float | None
    seeds: list[int]
    copies: int
    unit_states: list[str]
    weights: list[int]
    initial_counts: tuple[int, ...]
    channels: dict[str, Channel]
    channel_order: list[str]
    judged: dict
    identities: dict[str, list[tuple[str, float, str]]]
    start: dict[str, Any]
    minimum_per_copy: int
    minimum_total: int
    restart: dict | None
    families: list[str] = field(default_factory=list)

    @property
    def series(self) -> list[str]:
        return SERIES[self.kind]

    @property
    def ledger_total(self) -> int:
        return sum(w * n for w, n in zip(self.weights, self.initial_counts))

    def s_readouts(self) -> list[tuple[str, int]]:
        return [(entry["readout"], int(entry["p"])) for entry in self.judged.get("S", [])]

    def order_of(self, readout: str) -> int:
        for name, p in self.s_readouts():
            if name == readout:
                return p
        raise KeyError(readout)

    def at_rounding(self) -> list[str]:
        return list(self.judged.get("at_rounding", []))

    def m_of(self, readout: str) -> int:
        return M_TIME if readout == "t_events" else M_ROW


@dataclass
class Family:
    id: str
    world: str
    first: str
    rungs: list[float]
    retry_rung: float | None
    arm: int


@dataclass
class RunSpec:
    name: str
    arm: int
    world: str
    first: str
    copy: int
    step: float
    role: str
    variant: str | None
    raw: dict

    @property
    def family(self) -> str:
        return f"{self.world} {self.first}-first"


@dataclass
class Plant:
    id: str
    kind: str
    world: str
    families: list[str]
    must_fail: list[tuple[str, str]]
    change: Any
    no_margin: bool
    raw: dict

    @property
    def base(self) -> str:
        return self.id.split("-")[0]


class Inputs:
    """One inputs file (registered or invented)."""

    def __init__(self, path: str) -> None:
        loaded = sj.load_file(path)
        self.path = path
        self.sha256 = loaded.sha256
        self.data = loaded.data
        self.problems = list(sj.problems(self.data))
        d = self.data
        self.copy_fmol = copy_fmol(d["constants"]["N_A_per_mol"])
        self.guard_steps = int(d["guard_steps"])
        self.pairs_per_copy = int(d["draws"]["pairs_per_copy"])
        self.echo = d["echo"]
        self.arms = {int(k): v for k, v in d["arms"].items()}
        self.families: dict[str, Family] = {}
        for fam in d["families"]:
            self.families[fam["id"]] = Family(
                id=fam["id"], world=fam["world"], first=fam["first"], rungs=list(fam["rungs_s"]),
                retry_rung=fam.get("retry_rung_s"), arm=int(fam["arm"]))
        self.worlds: dict[str, World] = {}
        for name, block in d["worlds"].items():
            pop = block["population"]
            states = [s["id"] for s in pop["unit_states"]]
            weights = [int(s["subunits"]) for s in pop["unit_states"]]
            initial = tuple(int(pop["initial_counts"].get(s, 0)) for s in states)
            channels = {}
            order = []
            for ch in pop["channels"]:
                jump = tuple(int(ch.get("products", {}).get(s, 0)) - int(ch.get("reactants", {}).get(s, 0))
                             for s in states)
                channels[ch["id"]] = Channel(id=ch["id"], jump=jump, reactants=dict(ch.get("reactants", {})))
                order.append(ch["id"])
            ident = {key: [(term[0], float(term[1]), str(term[2])) for term in terms]
                     for key, terms in d["identities"][name].items()}
            minimum = d["minimum_events"][name]
            self.worlds[name] = World(
                name=name, kind=block["kind"], block=block, end_s=float(block["end_s"]),
                samples=list(block["samples_s"]), rungs=list(block["rungs_s"]), retry_rung=block.get("retry_rung_s"),
                seeds=[int(s) for s in block["seeds"]], copies=int(block["copies"]), unit_states=states,
                weights=weights, initial_counts=initial, channels=channels, channel_order=order,
                judged=d["judged"][name], identities=ident, start=d["start"][name],
                minimum_per_copy=int(minimum["per_copy"]), minimum_total=int(minimum["total"]),
                restart=d.get("restart", {}).get(name))
        for fam in self.families.values():
            self.worlds[fam.world].families.append(fam.id)
        self.runs: dict[str, RunSpec] = {}
        self.run_list: list[RunSpec] = []
        for r in d["runs"]:
            spec = RunSpec(name=r["name"], arm=int(r["arm"]), world=r["world"], first=r["first"], copy=int(r["copy"]),
                           step=float(r["step_s"]), role=r["role"], variant=r.get("variant"), raw=r)
            self.runs[spec.name] = spec
            self.run_list.append(spec)
        self.listed_retry_runs: list[dict] = list(d.get("retry", {}).get("runs", []))
        self.plants: list[Plant] = []
        for p in d["plants"]:
            fams = p["families"]
            if fams == "both":
                fams = list(self.worlds[p["world"]].families)
            self.plants.append(Plant(
                id=p["id"], kind=p["kind"], world=p["world"], families=list(fams),
                must_fail=[(str(c[0]), str(c[1])) for c in p["must_fail"]], change=p.get("change"),
                no_margin=bool(p.get("no_margin", False)), raw=p))

    # ---- names ----

    def judged_run(self, family: str, step: float, copy: int) -> str | None:
        fam = self.families[family]
        for spec in self.run_list:
            if (spec.role == "judged" and spec.world == fam.world and spec.first == fam.first
                    and spec.copy == copy and spec.step == step):
                return spec.name
        return None

    @staticmethod
    def retry_name(family: Family, copy: int) -> str:
        """CRITERIA.md §7: `{world} {first}-first h={step!r} c{copy} retry`."""
        return f"{family.world} {family.first}-first h={family.retry_rung!r} c{copy} retry"

    def retry_spec(self, family_id: str, copy: int) -> RunSpec:
        fam = self.families[family_id]
        name = self.retry_name(fam, copy)
        return RunSpec(name=name, arm=fam.arm, world=fam.world, first=fam.first, copy=copy,
                       step=float(fam.retry_rung), role="judged", variant=None,
                       raw={"name": name, "arm": fam.arm, "world": fam.world, "first": fam.first, "copy": copy,
                            "step_s": fam.retry_rung, "role": "judged", "variant": None})

    def plants_of(self, world: str) -> list[Plant]:
        return [p for p in self.plants if p.world == world]

    def start_value(self, world: str, readout: str) -> float:
        """READOUTS.md §4: the declared start; `free` is machines_copies × COPY (a double product)."""
        value = self.worlds[world].start[readout]
        if isinstance(value, str):
            if value.replace(" ", "") != "machines_copies*copy_fmol":
                raise ValueError(f"start {world} {readout}: {value!r} is not a known form")
            copies = self.worlds[world].block["gene"]["machines_copies"]
            return float(copies) * self.copy_fmol
        return float(value)

    def gene_r_and_l(self, world: str) -> tuple[float, float]:
        gene = self.worlds[world].block["gene"]
        return gene["residues"] / gene["stages"], float(gene["residues"])


def relative_equal(a: float, b: float, rel: float) -> bool:
    """|a - b| <= rel |b|; a declared zero exactly zero (CRITERIA.md §4.1, TABLE.md §3). Decided in doubles where
    the margin is clear, and exactly near the boundary."""
    if b == 0:
        return a == 0
    if a == b:
        return True
    diff = abs(a - b)
    limit = rel * abs(b)
    if diff < limit * (1 - 1e-6):
        return True
    if diff > limit * (1 + 1e-6):
        return False
    return abs(Fraction(a) - Fraction(b)) <= Fraction(rel) * abs(Fraction(b))


def finite(x: Any) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)
