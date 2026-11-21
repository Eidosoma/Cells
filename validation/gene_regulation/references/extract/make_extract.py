"""Write a1_protein_reference.csv: one A1 trajectory from the G2 code-blind references.

Reads ../interface/trajectories_test_instances.json (set 0, the sheet's numeric test instance;
world A1) and writes, on A1's output grid, the protein amount, its cumulative releases and
degradations, and the products identity's residual. Standard library only:

    python validation/gene_regulation/references/extract/make_extract.py
"""

import csv
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCE = HERE.parent / "interface" / "trajectories_test_instances.json"
OUT = HERE / "a1_protein_reference.csv"

HEADER = [
    "# G2 code-blind references for gene regulation option A (GR-1A): A1's deterministic reference "
    "trajectory at the sheet's numeric test instance.",
    "# NOT an engine export. Computed from the equation sheet alone; the engine's own A1 export "
    "comes after G3 and G4.",
    "# Sheet: docs/TEMPLATED_POLYMERISATION_LAWS.md at tag gr1-sheet-2026-11-20.",
    "# References: validation/gene_regulation/references/; data generated at commit cea053592f1a "
    "(one invocation from a source snapshot); interface committed at 291cfa64654f.",
    "# Generator: validation/gene_regulation/references/extract/make_extract.py, from "
    "validation/gene_regulation/references/interface/trajectories_test_instances.json "
    "(set 0, world A1).",
    "# Potentials: the sheet's numeric test instance (3.3): dG'0_ATP = {G} kJ/mol, "
    "E_pd = {pd} kJ/mol (-5.3 kcal/mol), E_pep = {pep} kJ/mol (-3.6 kcal/mol), "
    "E_rc/RT = ln 1.05 = {rc}.",
    "# Solver: DOP853 at rtol 2.5e-12, outputs hit exactly every 60 s. A 100x tighter re-solve "
    "changes these columns by at most 1.7e-14 of their scales (any A1 readout by 2.9e-11).",
    "# Units (sheet 0): t in s; amounts and cumulative extents in fmol per cell "
    "(1 molecule = 1e15/N_A fmol = 1.660539067e-9 fmol).",
    "# products_residual_fmol = n_P(0) + int_Q_tl - int_D_P - n_P, the products identity of "
    "sheet 4.8 (zero up to rounding).",
]


def main() -> None:
    data = json.loads(SOURCE.read_text())
    s0 = data["sets"]["0"]
    pot = s0["potentials"]
    a1 = s0["worlds"]["A1"]
    t, ro = a1["t"], a1["readouts"]
    nP, Q, D = ro["n_P"], ro["int_Q_tl"], ro["int_D_P"]
    fill = {"G": pot["G_ATP_kJ_mol"], "pd": pot["E_pd_kJ_mol"], "pep": pot["E_pep_kJ_mol"],
            "rc": f"{float(pot['E_rc_RT']):.17g}"}
    with OUT.open("w", newline="") as f:
        for line in HEADER:
            f.write(line.format(**fill) + "\n")
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["t_s", "n_P_fmol", "int_Q_tl_fmol", "int_D_P_fmol", "products_residual_fmol"])
        for k in range(len(t)):
            w.writerow([repr(t[k]), repr(nP[k]), repr(Q[k]), repr(D[k]),
                        repr(nP[0] + Q[k] - D[k] - nP[k])])
    worst = max(abs(nP[0] + Q[k] - D[k] - nP[k]) for k in range(len(t)))
    print(f"{OUT.name}: {len(t)} rows, t = {t[0]}..{t[-1]} s; largest |residual| {worst:.3e} fmol "
          f"against n_P(0) + int_Q(t_end) = {nP[0] + Q[-1]:.6e} fmol")


if __name__ == "__main__":
    main()
