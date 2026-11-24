"""FR-49 references: the declared worlds, parsed from spec/cases.json.

Parsing only. Every number stays the exact decimal string the spec declares; the routes turn the
strings into their own number types. Nothing here computes a law.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

HERE = Path(__file__).resolve().parent
CASES_JSON = HERE / "spec" / "cases.json"
KIND = "cells.fr49_reference_spec@1"
WORLDS = ("L", "B", "C1", "C2")
_RULE = re.compile(r"^t_i = (\S+) i, i = 0 \.\.\. (\d+)$")


@dataclass(frozen=True)
class Samples:
    step: str  # s
    last: int  # i = 0 ... last


@dataclass(frozen=True)
class Sites:
    copies: str
    sites_per_copy: int
    accessible_fraction: str


@dataclass(frozen=True)
class WorldL:
    V_O: str
    V_C: str
    a: str
    k_d: str
    P: str
    n_O0: str
    n_C0: str
    x_O0: str
    x_C0: str
    t1: str
    t2: str
    horizon: str
    samples: Samples


@dataclass(frozen=True)
class WorldB:
    V_C: str
    sites: Sites
    k_on: str
    k_off: str
    n_L0: str
    B0: str
    horizon: str
    samples: Samples
    wash_time: str
    wash_fraction: str
    wash_node: str


@dataclass(frozen=True)
class WorldC1:
    V_W: str
    x_W0: str
    b_W0: str
    wash_time: str
    wash_fraction: str
    buffer_mM: str


@dataclass(frozen=True)
class Ligand:
    id: str
    k_on: str
    k_off: str
    total: str


@dataclass(frozen=True)
class WorldC2:
    V_C: str
    sites: Sites
    ligands: tuple[Ligand, ...]
    B0: tuple[str, ...]
    horizon: str
    samples: Samples


@dataclass(frozen=True)
class Spec:
    path: Path
    invented: bool
    sites_per_fmol: str
    L: WorldL
    B: WorldB
    C1: WorldC1
    C2: WorldC2


def _samples(raw: dict) -> Samples:
    match = _RULE.match(raw["rule"])
    if match is None:
        raise ValueError(f"unreadable sample-time rule {raw['rule']!r}")
    return Samples(match.group(1), int(match.group(2)))


def _sites(raw: dict) -> Sites:
    nu = raw["sites_per_copy"]
    if not isinstance(nu, int) or isinstance(nu, bool) or nu < 1:
        raise ValueError("sites_per_copy must be a positive integer")
    return Sites(raw["copies"], nu, raw["accessible_fraction"])


def load(path: Path = CASES_JSON) -> Spec:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if raw.get("kind") != KIND:
        raise ValueError(f"{path}: not the FR-49 reference spec")
    invented = raw.get("invented", False)
    if not isinstance(invented, bool):
        raise ValueError(f"{path}: 'invented' must be true or false")
    worlds = raw["worlds"]
    if tuple(worlds) != WORLDS:
        raise ValueError(f"{path}: the worlds must be {WORLDS}, in that order")
    sites_per_fmol = raw["units"]["sites_per_fmol"].split()[0]
    L, B, C1, C2 = (worlds[name] for name in WORLDS)
    init = L["initial_fmol"]
    world_L = WorldL(L["V_O_pL"], L["V_C_pL"], L["a_pL_per_s"], L["k_d_per_s"],
                     L["P_fmol_per_s"], init["n_O"], init["n_C"], init["x_O"], init["x_C"],
                     L["pulse_s"]["t1"], L["pulse_s"]["t2"], L["horizon_s"],
                     _samples(L["sample_times_s"]))
    wash = B["wash_elsewhere"]
    world_B = WorldB(B["V_C_pL"], _sites(B["sites"]), B["k_on_per_mM_per_s"], B["k_off_per_s"],
                     B["initial_fmol"]["n_L"], B["initial_fmol"]["B"], B["horizon_s"],
                     _samples(B["sample_times_s"]), wash["time_s"], wash["fraction"],
                     wash["node"])
    if C1["world_L"] != "as world L above, unchanged":
        raise ValueError(f"{path}: C1's world L must be world L unchanged")
    buffer = C1["wash"]["buffer_mM"]
    if set(buffer) != {"S"}:
        raise ValueError(f"{path}: C1's buffer declares S only")
    world_C1 = WorldC1(C1["V_W_pL"], C1["initial_fmol"]["x_W"], C1["initial_fmol"]["b_W"],
                       C1["wash"]["time_s"], C1["wash"]["fraction"], buffer["S"])
    ligands = tuple(Ligand(g["id"], g["k_on_per_mM_per_s"], g["k_off_per_s"], g["total_fmol"])
                    for g in C2["ligands"])
    bound = C2["initial_bound_fmol"]
    world_C2 = WorldC2(C2["V_C_pL"], _sites(C2["sites"]), ligands,
                       tuple(bound[f"B{j + 1}"] for j in range(len(ligands))), C2["horizon_s"],
                       _samples(C2["sample_times_s"]))
    return Spec(Path(path), invented, sites_per_fmol, world_L, world_B, world_C1, world_C2)
