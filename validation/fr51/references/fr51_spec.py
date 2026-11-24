"""FR-51 references: the declared cases, parsed from spec/cases.json.

Parsing only. Every number stays the exact decimal string the spec declares, and each route
turns the strings into its own number type (route A: decimal.Decimal; route B:
fractions.Fraction). Nothing here computes a law.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

HERE = Path(__file__).resolve().parent
SPEC_DIR = HERE / "spec"
CASES_JSON = SPEC_DIR / "cases.json"


@dataclass(frozen=True)
class Mode:
    weight: str
    k0_mM: str
    electrical_distance: str | None
    effective_valence: str | None


@dataclass(frozen=True)
class Block:
    name: str
    z_B: int
    side: str  # "outside" or "inside"
    c_B_mM: str
    reversal_ion: str | None  # None: the membrane-voltage reference
    modes: tuple[Mode, ...]


@dataclass(frozen=True)
class Case:
    id: str
    population: str
    ion: str
    z: int
    relative_permeability: str
    area_m2: str
    permeability_m_per_s: str
    open_fraction: str
    availability: str
    c_i_mM: str
    c_o_mM: str
    block: Block | None
    # The abundance: the population's own, a case's override (C1), or a count of units (C2)
    abundance: str | None
    abundance_from: str  # "population", "case" or "units"
    units_count: str | None
    reference_density_per_m2: str | None


@dataclass(frozen=True)
class Spec:
    path: Path
    invented: bool  # True for invented inputs (a format sample), never for the registered spec
    F_factors: tuple[str, str]  # F = N_A x e
    R_factors: tuple[str, str]  # R = N_A x k_B
    T_K: str
    grid_start: str
    grid_step: str
    grid_count: int
    cases: tuple[Case, ...]


def _product(text: str) -> tuple[str, str]:
    left, right = (part.strip() for part in text.split("*"))
    return left, right


def _block(name: str, raw: dict) -> Block:
    blocker = raw["blocker"]
    z_B = blocker["valence"]
    if not isinstance(z_B, int) or isinstance(z_B, bool) or z_B == 0:
        raise ValueError(f"block {name}: the blocker's valence must be a nonzero integer")
    if blocker["side"] not in ("outside", "inside"):
        raise ValueError(f"block {name}: side must be outside or inside")
    reference = raw["reference"]
    if reference == "membrane_voltage":
        reversal_ion = None
    elif isinstance(reference, dict) and set(reference) == {"reversal_of"}:
        reversal_ion = reference["reversal_of"]
    else:
        raise ValueError(f"block {name}: unknown reference {reference!r}")
    modes = []
    for mode in raw["modes"]:
        distance = mode.get("electrical_distance")
        valence = mode.get("effective_valence")
        if (distance is None) == (valence is None):
            raise ValueError(f"block {name}: a mode declares exactly one steepness (LAWS.md 3)")
        modes.append(Mode(mode["weight"], mode["k0_mM"], distance, valence))
    return Block(name, z_B, blocker["side"], blocker["concentration_mM"], reversal_ion,
                 tuple(modes))


def load(path: Path = CASES_JSON) -> Spec:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if raw.get("kind") != "cells.fr51_reference_spec@1":
        raise ValueError(f"{path}: not the FR-51 reference spec")
    invented = raw.get("invented", False)
    if not isinstance(invented, bool):
        raise ValueError(f"{path}: 'invented' must be true or false")
    for entry in raw["cases"]:
        if entry["id"].startswith("INVENTED_") != invented:
            raise ValueError(f"{path}: case ids start with INVENTED_ exactly when the inputs "
                             "are invented")
    constants = raw["constants"]
    grid = raw["voltage_grid_V"]
    populations = raw["populations"]
    blocks = {name: _block(name, body) for name, body in raw["blocks"].items()}
    cases = []
    for entry in raw["cases"]:
        population = populations[entry["population"]]
        block = None if entry["block"] is None else blocks[entry["block"]]
        if block is not None and block.reversal_ion not in (None, population["ion"]):
            raise ValueError(f"{entry['id']}: the reversal ion is not the population's ion")
        units = entry.get("units")
        if units is not None and "abundance" in entry:
            raise ValueError(f"{entry['id']}: declares both an abundance and units")
        abundance = entry.get("abundance", None if units is not None else population["abundance"])
        cases.append(Case(
            id=entry["id"],
            population=entry["population"],
            ion=population["ion"],
            z=population["valence"],
            relative_permeability=population["relative_permeability"],
            area_m2=population["area_m2"],
            permeability_m_per_s=population["permeability_m_per_s"],
            open_fraction=population["open_fraction"],
            availability=population["availability"],
            c_i_mM=entry["c_i_mM"],
            c_o_mM=entry["c_o_mM"],
            block=block,
            abundance=abundance,
            abundance_from=("units" if units is not None
                            else "case" if "abundance" in entry else "population"),
            units_count=None if units is None else units["count"],
            reference_density_per_m2=None if units is None else units["reference_density_per_m2"],
        ))
    return Spec(
        path=Path(path),
        invented=invented,
        F_factors=_product(constants["F_C_per_mol"]),
        R_factors=_product(constants["R_J_per_mol_K"]),
        T_K=constants["T_K"],
        grid_start=grid["start"],
        grid_step=grid["step"],
        grid_count=int(grid["count"]),
        cases=tuple(cases),
    )
