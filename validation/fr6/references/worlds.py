"""FR-6's A5'' worlds: the self-contained inputs file, and its translation into R-cell's World.

    python -m validation.fr6.references.worlds      # writes reference_inputs.json

The world follows ``docs/INVENTORY_COUPLING_DESIGN.md`` §4.4's A5, with a regulatory state put
between the regulator and the channel, and a per-cell prior (FR-6 item 3; §7.2 item 3: a
per-cell s0). It takes A5's judged numbers where the design's §9.1 gives them (2 pL, 4 pF, a
2e-9 m/s K-leak population, the dose and the Hill law). The patch area, the leaks, the cytosol
and the bath come from the coupling references' synthetic builder (reference_crosschecks.py),
and the clearance of 5/s is this package's choice:
- two identical pump-free cells, each of 2 pL on one constant-field patch of 4 pF facing a held
  bath at 0 V, with Na, K and Cl leaks;
- a gate-free K-leak population in each cell (``kleak_always_open@1``: K only);
- a neutral regulator X in each cell, held at 1 uM by D150's turnover and driven toward 10 uM
  over [0.2, 0.5) s: the same dose in both cells;
- a regulatory state s1 in both cells, read from X by a Hill activation (K 3 uM, n 2), with
  k_on 5/s and k_off 1/s, starting at s0 = 0.1 in cell a and 0.8 in cell b;
- on each cell's population a coupling F = b + (1 - b) s1 with b = 0.1 (``state_fraction``).

Every value is synthetic, chosen within the A5 world's bracket. The bath is at 0 V, and V is each
cell's potential. Both cells start at -60 mV (``initial_V``), so the prior acts through the
dynamics only.
"""

from __future__ import annotations

import json
import sys
from fractions import Fraction
from pathlib import Path

from validation.coupling import cells_reference as rc
from validation.coupling import state_reference as rs

HERE = Path(__file__).resolve().parent
INPUTS = HERE / "reference_inputs.json"
REGISTERED = "2026-11-18"
SI = {"avogadro_per_mol": 6.02214076e23, "elementary_charge_C": 1.602176634e-19,
      "boltzmann_J_per_K": 1.380649e-23}


def _records(end_s: float, every_s: float) -> list:
    n = round(end_s / every_s)
    return [float(Fraction(k) * Fraction(every_s)) for k in range(n + 1)]


def _cell_block(s0: float) -> dict:
    return {"volume_pL": 2.0, "mM": {"Na": 12.0, "K": 140.0, "Cl": 30.0}, "initial_V": -0.06,
            "patch": {"area_m2": 4e-10, "capacitance_F": 4e-12,
                      "leak_permeability_m_per_s": {"Na": 1e-10, "K": 2e-9, "Cl": 5e-10}},
            "population": {"law": "kleak_always_open@1", "permeability_m_per_s": 2e-9,
                           "relative": {"Na": 0.0, "K": 1.0, "Cl": 0.0}, "abundance": 1.0,
                           "opening": 1.0, "schedule": [[0.0, 1.0]]},
            "regulator_X": {"initial_mM": 1e-3, "segments": [
                {"time_s": 0.0, "production_fmol_per_s": 1e-3 * 2.0 * 5.0, "clearance_per_s": 5.0},
                {"time_s": 0.2, "production_fmol_per_s": 1e-2 * 2.0 * 5.0, "clearance_per_s": 5.0},
                {"time_s": 0.5, "production_fmol_per_s": 1e-3 * 2.0 * 5.0,
                 "clearance_per_s": 5.0}]},
            "state_s1_initial": s0}


def build() -> dict:
    world = {
        "item": "A5'' (FR-6 item 3 with item 1): a channel driven through a regulatory state with "
                "a per-cell prior",
        "temperature_K": 310.0,
        "species": {"Na": 1, "K": 1, "Cl": -1},
        "bath_mM": {"Na": 140.0, "K": 5.0, "Cl": 145.0},
        "bath_potential_V": 0.0,
        "cells": {"a": _cell_block(0.1), "b": _cell_block(0.8)},
        "state_s1": {"cells": ["a", "b"], "input": {"law": "hill_activation", "source": "X",
                                                     "K_mM": 3e-3, "n": 2.0},
                     "k_on_per_s": 5.0, "k_off_per_s": 1.0},
        "couplings": [{"id": "k_a", "target": "population of a", "law": "state_fraction",
                       "source": "s1", "basal": 0.1},
                      {"id": "k_b", "target": "population of b", "law": "state_fraction",
                       "source": "s1", "basal": 0.1}],
        "end_s": 2.0,
        "record_times_s": _records(2.0, 0.05),
    }
    return {
        "kind": "FR-6 A5'': the references' registered inputs",
        "registered": REGISTERED,
        "forms": "docs/INVENTORY_COUPLING_DESIGN.md Appendix A (A.1-A.3) and §4.4's A5; FR-6 "
                 "item 3 (a per-cell prior)",
        "units": {"amount": "fmol", "volume": "pL", "concentration": "mM", "time": "s",
                  "permeability": "m/s", "area": "m^2", "capacitance": "F", "potential": "V",
                  "rate": "1/s"},
        "constants": dict(SI, faraday_C_per_mol="avogadro_per_mol x elementary_charge_C (exact)",
                          gas_constant_J_per_mol_K="avogadro_per_mol x boltzmann_J_per_K (exact)"),
        "conventions": [
            "the bath is held at 0 V; V is each cell's potential; each cell starts at initial_V, "
            "its background charge following",
            "constant-field flux for every leak and for the population, outward positive; the "
            "population carries P r_s a_eff A, with a_eff = a_sched x F",
            "F = b + (1 - b) s1 (state_fraction), and ds1/dt = k_on u (1 - s1) - k_off s1 in each "
            "cell, with u = X^n/(K^n + X^n) of that cell's own X",
            "X follows D150's turnover in each cell: n(t) = n_j e^(-k tau) + (P/k)(1 - e^(-k tau)) "
            "per segment, the same dose in both cells",
            "records are the states at the record times, t = 0 included; every segment start is "
            "an exact multiple of each dt of the ladder",
        ],
        "dt_ladder_s": [1e-3, 5e-4, 2.5e-4, 1.25e-4],
        "worlds": {"a5pp_prior": world},
    }


def write(path=INPUTS) -> Path:
    Path(path).write_text(json.dumps(build(), indent=1) + "\n")
    return Path(path)


def to_world(block: dict, constants: dict | None = None, s0_override: dict | None = None,
             couplings_override: dict | None = None, state_override: dict | None = None):
    """An R-cell World of a world block. The overrides serve the planted controls only."""
    c = constants or SI
    F = c["avogadro_per_mol"] * c["elementary_charge_C"]
    R = c["avogadro_per_mol"] * c["boltzmann_J_per_K"]
    const = rc.Constants(F, R, block["temperature_K"])
    sp = tuple(block["species"])
    z = tuple(block["species"][s] for s in sp)
    cells, patches, pops, regs = {}, {}, {}, {}
    for name, cb in block["cells"].items():
        cells[name] = rc.Cell(cb["volume_pL"], tuple(cb["mM"][s] for s in sp),
                              initial_V=cb["initial_V"])
        pb = cb["patch"]
        patches[f"{name}.m"] = rc.Patch(name, pb["area_m2"], pb["capacitance_F"],
                                        tuple(pb["leak_permeability_m_per_s"][s] for s in sp))
        po = cb["population"]
        pops[f"kleak_{name}"] = rc.Population(f"{name}.m", po["permeability_m_per_s"],
                                              tuple(po["relative"][s] for s in sp),
                                              abundance=po["abundance"], opening=po["opening"],
                                              schedule=tuple(tuple(x) for x in po["schedule"]))
        rx = cb["regulator_X"]
        regs[name] = rs.Turnover(rx["initial_mM"] * cb["volume_pL"], cb["volume_pL"],
                                 tuple((sg["time_s"], sg["production_fmol_per_s"],
                                        sg["clearance_per_s"]) for sg in rx["segments"]))
    st = dict(block["state_s1"], **(state_override or {}))
    s0 = {name: cb["state_s1_initial"] for name, cb in block["cells"].items()}
    s0.update(s0_override or {})
    inp = st["input"]
    states = {"s1": rc.State(tuple(st["cells"]), (rc.Input(inp["law"], inp["source"],
                                                           inp["K_mM"], inp["n"]),),
                             st["k_on_per_s"], st["k_off_per_s"], initial=s0)}
    couplings = {}
    for cp in block["couplings"]:
        cell = cp["target"].split()[-1]
        couplings[cp["id"]] = rc.Coupling(f"kleak_{cell}", cp["law"], cp["source"],
                                          basal=cp["basal"])
    if couplings_override is not None:
        couplings = couplings_override
    return rc.World(const, sp, z, tuple(block["bath_mM"][s] for s in sp), cells=cells,
                    patches=patches, populations=pops, regulators={"X": rc.Regulator(regs)},
                    states=states, couplings=couplings)


if __name__ == "__main__":
    print(write())
    sys.exit(0)
