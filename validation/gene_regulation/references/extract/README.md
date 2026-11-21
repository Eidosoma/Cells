# A1's protein trajectory from the G2 code-blind references

**What this is.** The trajectory comes from the **code-blind references** at the sheet's numeric
test instance. It is **not an engine export**.
- The references were computed from the equation sheet `docs/TEMPLATED_POLYMERISATION_LAWS.md` at
  tag `gr1-sheet-2026-11-20` alone; see `../README.md`.
- The engine's own A1 export comes after G3 and G4.

It gives one A1 trajectory, so that a reviewer of gene regulation option A (GR-1A, FR-25) can check
that an assay comparison reads the right fields: the protein row, its cumulative completions and
degradations, and the products identity.

**The file.** `a1_protein_reference.csv`.
- Its first lines, each beginning with `#`, name the sheet tag, the references' commits and the
  generator.
- Read it with `pandas.read_csv(path, comment="#")` or equivalent.

| Column | Meaning | Unit (sheet §0) |
| --- | --- | --- |
| `t_s` | elapsed time from 0, on A1's output grid 0, 60, …, 21,600 | s |
| `n_P_fmol` | protein amount n_P, the row `P` | fmol per cell |
| `int_Q_tl_fmol` | cumulative protein completions: ∫Q for translation, the protein releases (§4.7, §4.8) | fmol |
| `int_D_P_fmol` | cumulative protein degradation ∫D_P | fmol |
| `products_residual_fmol` | n_P(0) + ∫Q − ∫D − n_P, the products identity of §4.8 | fmol |

One molecule is 10¹⁵/N_A = 1.660539067 × 10⁻⁹ fmol. The cell is V = 1 pL, so an amount in fmol is
also a concentration in mM.

**Which A1.**
- It is the sheet's A1 (§5.1): the regulator holds u = 0.51 until t_off = 10,800 s, then X decays.
- It runs at the numeric test instance of §3.3: ΔG′°_ATP = −32 kJ/mol, E_pd = −5.3 kcal/mol,
  E_pep = −3.6 kcal/mol, E_rc/RT = ln 1.05.
- n_P starts at the sheet's trace, 10⁻¹² fmol.

**How good it is.**
- The trajectory is the references' judged solve, DOP853 at rtol 2.5 × 10⁻¹².
- A 100× tighter re-solve changes these three columns by at most 1.7 × 10⁻¹⁴ of their scales.
- The residual column stays below 6 × 10⁻¹⁹ fmol, against n_P(0) + ∫Q(t_end) ≈ 1.29 × 10⁻⁴ fmol:
  rounding.

**Provenance and regeneration.**
- The data were generated at commit `cea053592f1a`, in one invocation from a source snapshot. They
  sit in `../interface/trajectories_test_instances.json` (set `0`, world `A1`), committed at
  `291cfa64654f`.
- `python validation/gene_regulation/references/extract/make_extract.py` (standard library only)
  rewrites the CSV from that file, identically.
- At other potential values, first run the references into a fresh folder with
  `python -m validation.gene_regulation.references.run --out NEW_DIR --potentials ...`. Then point
  the generator at that run's interface.
