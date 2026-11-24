"""FR-50 references: the declared cases, parsed from spec/cases.json.

Parsing only. Every number stays the exact decimal string the spec declares; the routes turn the
strings into their own number types. Nothing here computes a law. A case's kind (K1, K2, K3, K4,
K4h, E1, E2, E3, E4 or E6) is its id's first part, after an INVENTED_ prefix for invented inputs.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

HERE = Path(__file__).resolve().parent
CASES_JSON = HERE / "spec" / "cases.json"
KIND = "cells.fr50_reference_spec@1"
_RULE = re.compile(r"^t_i = (\S+) i, i = 0 \.\.\. (\d+)$")

# The declared fields each kind needs
FIELDS = {
    "K1": ("T_K", "P_m_per_s", "A_m2", "opening", "V_cell_pL", "V_node_pL", "c_cell_mM",
           "c_node_mM", "record_times_s"),
    "K2": ("T_K", "P_m_per_s", "A_m2", "opening", "V_cell_pL", "V_node_pL", "c_cell_mM_at_0",
           "c_node_mM_at_0", "record_times_s"),
    "K3": ("T_K", "valence", "P_m_per_s", "A_m2", "opening", "c_in_mM", "c_out_mM", "voltages_V"),
    "K4": ("T_K", "stoichiometry", "capacity_fmol_cycles_per_s", "availability", "K_mM",
           "K_ATP_mM", "c0_mM", "mu0_over_RT", "fuel_mM", "c_in_mM", "c_out_mM",
           "record_times_s"),
    "K4h": ("T_K", "stoichiometry", "capacity_fmol_cycles_per_s", "availability", "K_mM",
            "K_ATP_mM", "c0_mM", "mu0_over_RT", "fuel_mM", "c_in_mM", "c_out_mM"),
    "E1": ("T_K", "valence", "P_m_per_s", "A_m2", "availability", "c_in_mM", "c_out_mM", "V",
           "record_times_s"),
    "E2": ("T_K", "P_m_per_s", "A_m2", "gate", "availability", "c_sender_mM", "c_receiver_mM",
           "record_times_s"),
    "E3": ("T_K", "D_m2_per_s", "A_m2", "L_m", "c_sender_mM", "c_receiver_mM", "record_times_s"),
    "E4": ("T_K", "valence", "P_m_per_s", "A_m2", "relative_permeability", "abundance",
           "open_fraction", "availability", "c_in_mM", "c_out_mM", "V", "block",
           "record_times_s"),
    "E6": ("T_K", "valence", "P_m_per_s", "A_m2", "relative_permeability", "abundance",
           "open_fraction", "availability", "c_in_mM", "c_out_mM", "block", "voltages_V",
           "availabilities"),
}


@dataclass(frozen=True)
class Samples:
    step: str
    last: int


@dataclass(frozen=True)
class Case:
    id: str
    kind: str
    raw: dict  # the declared entry, as written
    record_times: Samples | None

    def __getitem__(self, key: str):
        return self.raw[key]


@dataclass(frozen=True)
class Spec:
    path: Path
    invented: bool
    F_factors: tuple[str, str]
    R_factors: tuple[str, str]
    cases: tuple[Case, ...]


def _product(text: str) -> tuple[str, str]:
    left, right = (part.strip() for part in text.split("*"))
    return left, right


def _samples(raw: dict) -> Samples:
    match = _RULE.match(raw["rule"])
    if match is None:
        raise ValueError(f"unreadable time rule {raw['rule']!r}")
    return Samples(match.group(1), int(match.group(2)))


def kind_of(case_id: str) -> str:
    return case_id.removeprefix("INVENTED_").split("_")[0]


def load(path: Path = CASES_JSON) -> Spec:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if raw.get("kind") != KIND:
        raise ValueError(f"{path}: not the FR-50 reference spec")
    invented = raw.get("invented", False)
    if not isinstance(invented, bool):
        raise ValueError(f"{path}: 'invented' must be true or false")
    cases = []
    for case_id, entry in raw["cases"].items():
        if case_id.startswith("INVENTED_") != invented:
            raise ValueError(f"{path}: case ids start with INVENTED_ exactly when the inputs are "
                             "invented")
        kind = kind_of(case_id)
        if kind not in FIELDS:
            raise ValueError(f"{case_id}: unknown kind {kind!r}")
        missing = [f for f in FIELDS[kind] if f not in entry]
        if missing:
            raise ValueError(f"{case_id}: missing {missing}")
        if kind in ("E4", "E6"):
            reference = entry["block"]["reference"]
            if reference != {"reversal_of": "K"}:
                raise ValueError(f"{case_id}: the block's reference must be the reversal of K")
        times = _samples(entry["record_times_s"]) if "record_times_s" in entry else None
        cases.append(Case(case_id, kind, entry, times))
    constants = raw["constants"]
    return Spec(Path(path), invented, _product(constants["F_C_per_mol"]),
                _product(constants["R_J_per_mol_K"]), tuple(cases))
