# Bioelectric one-cell design checks

Date: 2026-09-08 UTC. Outcome: 74 independent instantaneous checks passed for the
[proposed physical contract](../docs/BIOELECTRIC_CELL_SPEC.md). This is a
specification-stage calculator, not an integrated trajectory, a production Cells
model, a BETSE comparison, or biological validation. It adds no pytest cases.

## Reproduce and inspect

```bash
taskset -c 0-3 .venv/bin/python -W error scripts/check_bioelectric_contract.py
```

To retain a new receipt, add `--output reports/my-bioelectric-design-check.json`.
The destination must not exist; the script refuses overwriting. The retained
[JSON receipt](bioelectric-design-check.json) was generated with this option at
10:17:29 UTC using Python 3.13.5 and NumPy 2.5.3. Its
[calculator](../scripts/check_bioelectric_contract.py) imports no Cells code.
Verifier SHA-256:
`c2deeb28049a6567b9af09f6db2544dc42e0d1ecbf6b08e8facb02bae0bb57a9`.

Checks cover units, initial background/bath charge, a high-precision Bernoulli
expression reference, diffusion/Nernst/off/reversal/area limits, pump
stoichiometry/off/stall/reversal, passive and pump dissipation on a declared
parameter panel, and an algebraic charge/ledger identity. The reference expression
uses 70-digit Decimal arithmetic at nine arguments from -50 to +50, including zero
and near-zero points. The dissipative panel varies internal sodium, voltage,
and chemical drive; it is not exhaustive arbitrary-state validation.

## Selected numerical results

All values refer to the synthetic initial fixture, not a steady state or a
physiologically calibrated cell. Species ordering is Na, K, Cl.

| Quantity | Result |
| --- | --- |
| Maximum scaled Bernoulli error | 1.11e-16 |
| Maximum species-specific Nernst flux residual | 3.55e-18 fmol/s |
| Separate Nernst voltages | [64.0215, -85.6129, -69.5768] mV |
| Initial passive inward fluxes | [0.0395964, -0.0169147, 0.000536006] fmol/s |
| Initial forward pump rate | 0.0188275 fmol cycles/s |
| Initial pump cycle free-energy change | -8676.27 J/mol cycles |
| Initial signed chemical power supplied | 9.41374e-13 W |
| Initial net inward current | 3.20160e-13 A |
| Initial voltage derivative | +0.0320160 V/s |
| Frozen-concentration local relaxation estimate | 0.0631282 s |

The relaxation estimate is `-C / (dI_inward/dV)` from a central finite difference
at the initial concentrations and voltage. It indicates a restoring local
electrical response under frozen chemistry. It does not select a timestep,
establish a stability bound for the evolving cell, or prove long-time convergence.
The ledger check uses a declared algebraic amount change; no integration was
performed by this calculator.

## Existing implementation and next evidence

The unchanged Cells 0.4.0 regression suite was rerun with warnings as errors:
**270 passed in 49.50 s** using `taskset -c 0-3 .venv/bin/python -m pytest -q -W error`.
Ruff lint/format and installed dependency checks also passed. Production source
and existing run artifacts were not changed; no package-version bump or new
bioelectric run is implied. Historical acceptance receipts remain intact.
All 22 production Python-file hashes were checked against the retained 0.4.0
single-cell composition manifest and match. The new JSON receipt's verifier hash
also matches the current calculator source.

A repeat calculator run reproduced every numerical field exactly; attempting to
reuse the existing receipt path was refused without changing its bytes.
Documentation checks passed for 20 Markdown documents, 40 tables, and 243 local
link occurrences including heading anchors. Git whitespace checks passed.

Next NUM-002 builds independent integrated CPU references, establishes numerical
accuracy and a supported domain, and selects a candidate solver. MODEL-003 then
implements and verifies the physical cell through Cells' shared engineering.
These gates must precede source-selective coupling claims. The reviewed
external experimental evidence is recorded separately in
[BETSE design review](../docs/BETSE_DESIGN_REVIEW.md).

Subsequent delivery: [NUM-002 qualification](NUM002_REFERENCE.md) now supplies
the independent trajectories and bounded numerical candidate. This historical
design-check receipt and its 74 instantaneous checks remain unchanged.
