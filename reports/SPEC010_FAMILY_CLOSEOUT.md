# SPEC-010 bounded kinetic finite-bath closeout

2026-09-16, D114. **Bounded development scope independently closed.**
The working model is `finite_extracellular@2` / 0.16.0.dev0. This is not a full
release promotion, a native coupled BETSE qualification or biological validation.
The [original launch handoff](SPEC010_FAMILY_HANDOFF.md) remains unchanged.

## Evidence

The detached acceptance completed at **13:48:17 UTC**, in **418.438 s**:

- **74 family tests + 348 targeted regression tests = 422 pass**, without
  failures, errors or skips. The new-family tests took 143.566 s; regression
  took 265.701 s. Neither simulator nor the test matrix was rerun for this review.
- Twelve complete 10 ms production trajectories: six registered cases at
  100/50 µs, compared with both saved independent DOP853 and Radau references.
- Twelve bitwise-equal restart suffixes, each from a complete 6 ms checkpoint.
  Other runner features (branching, fresh-process replay, off-grid controls,
  windows, batches and cohorts) have the matrix's software-test evidence.
- All **601 captured source/configuration/contract inputs**, the complete
  **55-module production inventory**, and **292 result files** authenticate.

The separate saved-data review completed at **15:24:50 UTC**, in **3.601 s**.
It uses a strict stdlib-only NPY/NPZ decoder (including C/Fortran storage order)
and 60-digit Decimal accounting. Imports of Cells, BETSE, NumPy, JAX, SciPy,
the producer's reference/comparison code and the previous physics audit are
blocked. No solver runs or production changes occur.

It reconstructs **3,256 reference state comparisons**, their voltage checks,
**1,944 physical records**, all twelve full-state restart suffixes, and
**36 complete checkpoint links**. Layouts, masks, species roles, maintained
metabolism, capacities, controls, source identities and clocks are checked
against the registered preparation. Voltage/work observations are independently
reconstructed; this is not a claim to re-derive every exported observable.

| Reconstructed maximum | Result | Original budget |
| --- | --- | --- |
| Local material residual | 1.681e-18 fmol | 2e-11 fmol |
| Outside transfer residual | 1.843e-18 fmol | 2e-11 fmol |
| Global material residual | 9.216e-19 fmol | 2e-11 fmol |
| Countercharge residual | 1.658e-25 C | 1e-20 C |
| Energy residual | 3.782e-14 pJ | 2e-8 pJ |
| State error / registered budget | 1.486e-5 | 1 |

The independent review's [24 software checks](spec-010-family-audit-checks-02.xml)
pass in **0.37 s**, including malformed/nonfinite artifacts, import fencing,
changed ownership/roles/pools, padding, depleted inventory and deliberately
broken material/energy ledgers. The earlier 24-test receipt 01 is retained;
receipt 02 binds the final source after the reference-voltage check was added.
No scientific tolerance was changed.

## Immutable identities

- Capture: `runs/spec-010-family-2026-09-16/acceptance-01`.
  Completion SHA-256:
  `0901fb6ce8facddf4701bd32534d361fef60832c8dbf8427b0aaeab2aa26eb1f`.
- Independent review: `runs/spec-010-family-audit-2026-09-16/audit-01`.
  Completion SHA-256:
  `b5b8490afbcdf6c2d2f9504ce342585d378a9c1f247f3399587e325e650a92b0`.

New audit files legitimately extend the worktree. They do not change any of
the original 601 inputs. The original launcher's whole-directory inventory guard
is not relaxed or reused as if the growing tree were the original context.
Historical scripts and checkpoints retain their strict source identities.

## Remaining gates and test routing

- Stable **0.14.0** and fully accepted development **0.15.0.dev0** remain
  preserved. The bounded 422-test result is not the historical 4,190-test
  six-context release matrix.
- Future broader release work must distinguish current-context functional
  regressions from source-identity suites run in their preserved contexts.
  Establish a registered coverage manifest before launching that campaign;
  do not patch historical expectations to accept the new tree. No campaign
  was launched here.
- [REF-005b](../docs/BETSE_PUMP_LOOP_PREFLIGHT.md) prepares native pump/passive
  lifecycle evidence before a matched coupled trajectory comparison.
- Longer relaxation, biological data, more transporters, spatial composition,
  GPU execution and cross-resolution/organ validation remain separate work.
