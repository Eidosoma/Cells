# NUM-011: bounded kinetic pump coupling independently closed

2026-09-16, D110. The user requested continuation after the detached D109 panel.
This closes the numerical prerequisite in the
[integration contract](../docs/KINETIC_PUMP_INTEGRATION.md), not a production
simulation family, native BETSE whole-cell trajectory or biological experiment.

## Saved capture

`runs/num-011-kinetic-pump-2026-09-16/candidate-01` finished at
**2026-09-16 12:14:23.502445 UTC**, in **21.908402455970645 s**. Six synthetic
10 ms cases give 12 independent DOP853/Radau references, 24 NumPy/compiled-JAX
paths and 12 complete-state restart suffixes. All **4,070 comparisons / 30
groups / 12 refinement groups** pass, with zero worker warnings. Capture
completion SHA-256:
`57df709995d155139e20f026dbdd40bd37b417e9cbc8c182586ae8ecf681cbcb`.

The largest state error is **1.4857251481318058e-5 of its allowed budget**;
the maximum voltage difference is **5.331846075762314e-14 V**. All refinement
groups use the preregistered roundoff floor. In some groups the fine error is
slightly larger: this is **not a measured convergence order**, and no general
or maximum stable timestep follows. Original values and tolerances remain intact.

## Independent saved-state review

New standard-library tooling in `validation/betse/pump_coupled_audit/` has an
import fence against both simulators, numerical packages and all original
candidate/reference/comparator modules. No solver is rerun.

It rebuilds all 4,070 state comparisons and their 30 saved error summaries,
all 12 refinement decisions and 12 complete checkpoint/suffix links. It checks
all **3,756 physical records**: 3,624 candidate endpoints and 132 reference
samples. Additional checks cover full-state/sample linkage, reference segment
endpoints/clocks, exact blocking, suppression histories and nondecreasing
dissipation.

Material, charge, voltage and full finite-system energy are recalculated with
**60-digit Decimal arithmetic**, including explicit metabolic work and direct
extensive chemical/capacitor energy differences. This is not a call to the old
anchored-log1p accounting. Independent physical residuals need not be bitwise
equal to the old float64 diagnostics; each must satisfy the original budgets.
The state-error summaries and refinement records reconstruct exactly.

Independent maxima:

| Ledger | Residual | Existing bound |
| --- | --- | --- |
| Material | 1.6263032587282567e-18 fmol | 2e-11 fmol |
| Countercharge | 6.815969686617123e-29 C | 1e-20 C |
| Finite-system energy | 1.6523810517591156e-13 pJ | 2e-8 pJ |

Review passed in **4.535091300029308 s**, finishing **2026-09-16
12:27:26.565247 UTC**, at `runs/num-011-coupled-audit-2026-09-16/audit-01`.
Completion SHA-256:
`9a8500c86464bd487754cc8d4a56c2c30b94f85451b217960aeff7cff7be5fb1`.

All 14 original capture files and 14 candidate source/contract/report inputs
authenticate unchanged. Before adding any production source, the review also
authenticates and records all **352 accepted implementation files / 51 modules**,
the runtime and the already-preserved accepted archive:
`runs/core-010-2026-09-11/acceptance-02/implementation_sources.zip`, SHA-256
`7631383a29db621a5e83bf48dfc914153b128a0ee94c818c6fdcd5ac291812f0`.

[Software receipt 02](num-011-coupled-audit-checks-02.xml): **20 passed / 0.37 s**.
[Receipt 01](num-011-coupled-audit-checks-01.xml) retains 19 passes / one failure:
a synthetic 1e-18 fmol transfer was incorrectly expected to give bitwise-zero
Decimal residuals. Its binary expansion exceeds 60 digits; the test now allows
the corresponding sub-1e-70 arithmetic residual. No physical budget changed.

## Scope and next work

This qualifies the saved endpoint/reference-sample scope for these fixed short
cases at 100/50 µs. It does not qualify Hermite interiors, longer relaxation,
ordinary-runner checkpoints/branches/windows/cohorts with a new pump, native
full-loop correspondence, arbitrary regimes, experimental biology or GPU.

The next increment is the [named production process](../docs/KINETIC_PUMP_PROCESS.md),
followed by versioned configuration/layout composition and runner acceptance.
Old audit receipts retain their historical status; no source hash is relaxed
to load an old checkpoint into a changed package.
