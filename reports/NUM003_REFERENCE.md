# NUM-003: independent physical-pair qualification

Completed 2026-09-08 UTC. All 20 frozen physical-pair cases pass independent
reference/method qualification. The selected bounded candidate is **CPU float64
RK4, nominal maximum step 0.001 s, with interval-controlled cubic Hermite
observations**. No JAX pair is registered yet. Cells remains 0.5.0; all 25
production source-file hashes are unchanged.

See the [numerical contract](../docs/SELECTIVE_CONTACT_NUMERICS.md),
[physical specification](../docs/SELECTIVE_CONTACT_SPEC.md),
[frozen panel](../configs/reference/bioelectric_pair_panel_v1.json), and
[qualification receipt](../runs/num-003-2026-09-08/qualification/verification.json).

## Verified scope

- 20 full-panel cases, three implicit reference solves each: Radau/BDF at
  `rtol=1e-11`, `atol=1e-13`, and refined Radau at `rtol=1e-12`, `atol=1e-14`.
- 101002 RK4 intervals and 404028 comparison samples across the panel. Samples
  include every accepted endpoint and each interval's three quarter points.
- Three predeclared timestep-study cases at five steps each. Seven trials pass;
  eight accuracy failures remain recorded. No physical parameter or target changed.
- Independent blocked-pair/one-cell, analytic gate, closed-system, symmetric,
  reversed-edge and impermeant-route checks pass. Prescribed inhibitions preserve
  their own ledgers exactly, including Q17's sub-base-step block.
- Final suite: **542 tests pass in 125.97 s**, warnings treated as errors.
  [Final JUnit record](num-003-final-tests.xml). This adds 52 reference tests and
  seven separate-auditor tests to the preceding 483-test suite.
- Lint, formatting (58 Python files), dependency and whitespace checks pass.
  Documentation checks pass for 29 Markdown files, 57 tables and 395 local links.

The separate [artifact auditor](../scripts/audit_bioelectric_pair_reference.py)
imports neither Cells nor the reference RHS. It verifies both source capsules,
all 271 payload hashes, and 43812 native implicit accepted states, including
duplicated event endpoints. Qualification contributes 38669 states in 81 segments,
with 21 exact all-coordinate event continuations; the study contributes 5143
states in nine segments. Native clocks, positive amounts, gate/voltage domains,
material/charge/energy balances and dissipation monotonicity pass.
[Authoritative audit](../runs/num-003-2026-09-08/audit-accepted.json).

Event continuation inside this independent tool is not production snapshot/replay
acceptance; that remains MODEL-004 work. No source-assay, biological, organ, or
GPU result is claimed.

## Accuracy and accounting

These are maximum absolute errors over the saved comparison grid, not formal
continuous-time ODE error bounds. Reference-method limits are one tenth of the
RK4 targets. All 20 cases meet them.

| Quantity | Maximum RK4/cubic error | Target |
| --- | --- | --- |
| Ion amount | 6.48015e-12 fmol | 1e-7 fmol |
| Membrane leak ledger | 2.92360e-12 fmol | 1e-7 fmol |
| Pump-cycle ledger | 2.12327e-13 fmol cycles | 1e-7 fmol cycles |
| Junction transfer ledger | 4.73343e-12 fmol | 1e-7 fmol |
| Gate fraction | 1.14882e-8 | 1e-7 |
| Cell voltage | 8.35366e-11 V | 1e-6 V |
| Each dissipation quadrature | 4.29831e-11 pJ | 1e-6 pJ |

Maximum reference-method disagreement is 4.29487e-10 in gate fraction,
2.77998e-11 V, and 4.76064e-12 fmol in amount. Across reference, RK4 accepted
and RK4 observed arrays, maximum accounting residuals are 1.76908e-12 fmol,
1.47143e-11 V and 7.32540e-11 pJ. Targets remain 1e-8 fmol, 1e-8 V and
1e-6 pJ respectively. The separate native-increment audit obtains maximum
residuals of 6.66134e-16 fmol, 8.06749e-15 V and 7.27490e-11 pJ.
Increment and absolute-amount representations have different roundoff floors;
neither is a second physical model.

Every cubic interval is also checked at its polynomial extrema for amount,
gate and derived voltage admissibility, rather than only at the requested
sample times. The check is floating-point, not interval-arithmetic certification.
Instantaneous dissipation-rate diagnostics use at most 257 explicitly identified
samples per case; bounds/accounting/monotonicity use all comparison samples.

## Timestep and observation failures retained

The inherited 5 ms step would have been inadequate. Largest observed gate errors:

| Case | 5 ms | 2.5 ms | 1 ms |
| --- | --- | --- | --- |
| Q03 gate-only | 7.68879e-10 | 4.77062e-11 | 1.44407e-12 |
| Q09 fast gate | 8.45245e-6, fail | 4.76874e-7, fail | 1.14882e-8 |
| Q11 strong junction | 4.82723e-7, fail | 3.26701e-8 | 8.77251e-10 |

The Q11 values above are rounded observation errors; full precision is in the
study receipt. The accepted-state gate error ratios on successive halvings
10 -> 5 -> 2.5 ms are 16.34/16.12 for Q03 and 19.65/17.72 for Q09,
consistent with fourth-order refinement over this measured range. These are
not global order or stability guarantees for arbitrary parameters.

All 20 linear-observation alternatives fail at least one target even with
1 ms integration. Their maximum gate error is 1.69823e-4; maximum voltage error
is 1.84947e-6 V. Thus interpolation, not only integration endpoints, belongs in
the numerical contract. Both endpoint derivatives of each cubic use the
interval-held control, so sub-step inhibition events remain correctly resolved.

A deliberately oversized 100 ms fast-gate RK4 trial is rejected at its second
stage in the unit tests, with the attempted state and accepted prefix retained
by the error object. It is not clipped into range or reported as a biological event.

## Independent limits and baseline endpoint

Q01's blocked pair matches two separately integrated one-cell references:
maximum common ion-amount difference 2.84217e-14 fmol and voltage difference
3.25649e-13 V. Summed dissipation differs by 2.55906e-14 pJ. This comparison
independently supplies amounts, leaks, pump cycles, voltages and summed
dissipation—not a gate or separate per-process quadratures from a one-cell model.

Q03's refined trajectory agrees with the analytic gate-only solution to
4.76730e-13, with all other coordinates constant. Q02's sampled isolated
species-total error is zero at reported precision. Q04 keeps identical ionic
states and junction-transfer magnitude below 4.24e-25 fmol. Reversing Q06's
edge orientation gives equivalent physical trajectories after negating the
transfer ledger, within 2.84217e-14 fmol and 2.74239e-13 V. Q14's K-transfer
ledger remains exactly zero.

The synthetic 10 s baseline ends at:

| Quantity | Cell A | Cell B |
| --- | --- | --- |
| Na amount, fmol | 11.824705472292287 | 17.779337160960672 |
| K amount, fmol | 140.18445686546966 | 130.21471541873888 |
| Cl amount, fmol | 10.008930916907431 | 14.995771002698667 |
| Voltage, V | -0.06276712819921924 | -0.061580261379830505 |

Its final gate is 0.9644226802107893, with net A -> B transfer
`[-0.006398972088030308, 0.001640741177901966, -0.0008342709613542659]` fmol.
These are engineering endpoints, not a prepared equilibrium or calibrated cells.
The initial local seven-coordinate spectrum spans decay rates near 20.67 s⁻¹
and 0.000193 s⁻¹, suggesting widely separated local timescales. Ten seconds of
trajectory qualification does not establish behaviour over the slow mode's
roughly 5183 s timescale or justify automatic coarse graining.

## Reproduction and preservation

Use the existing main CPU environment; no new dependency was installed.
Recorded versions are Python 3.13.5, NumPy 2.5.3 and SciPy 1.18.1.
All runs were bounded to CPU affinity 0-3. Native reference/RK4 timings are
recorded per case; some overlapped the regression suite on the same host, so
they are not representative performance benchmarks or GPU projections.

Choose new output paths; these tools refuse overwrites:

```bash
taskset -c 0-3 .venv/bin/python scripts/verify_bioelectric_pair_reference.py --mode study --output runs/new-pair-study
taskset -c 0-3 .venv/bin/python scripts/verify_bioelectric_pair_reference.py --mode qualification --dt 0.001 --study runs/new-pair-study --output runs/new-pair-reference
taskset -c 0-3 .venv/bin/python scripts/audit_bioelectric_pair_reference.py runs/new-pair-study runs/new-pair-reference --output runs/new-pair-audit.json
taskset -c 0-3 .venv/bin/python -m pytest -q -W error
.venv/bin/ruff check src tests scripts
.venv/bin/ruff format --check src tests scripts
```

The study and qualification each preserve eight code/input entries in
`reference_sources.zip`, exact resolved case definitions, solver statistics,
native accepted increments, absolute comparison arrays, numerical failures and
payload hashes. Their driver versions differ only in logging formatting and
the later explicit study-link/refinement verification; the reference equations,
panel and targets are unchanged. The archived design document retains its
pre-qualification wording; its live status links were updated afterwards.
Numerical code, input and production hashes were rechecked.

The separate auditor's first exact-zero gate-only unit test exposed a
2.27374e-13 pJ subtraction-roundoff artifact in its absolute-potential calculation.
It now independently computes the potential change with `log1p` and a factored
capacitor-energy difference, returning exact zero for unchanged ionic state.
No simulation, physical parameter or acceptance target was changed. Preliminary
`audit.json` / `audit-final.json` and the earlier 535-test XML remain development
records; `audit-accepted.json` and the 542-test XML are authoritative.

| Artifact | SHA-256 |
| --- | --- |
| Frozen source panel | `642c92c6dba5f1f06c1639fbe37c0f69ef962e7018f2003d88c1c34d5ae14d46` |
| Study receipt | `420f3eaedf8c84be7326f3e0bb090725daab4175c4e248210bf4e30319f17abc` |
| Qualification receipt | `7c69c33f76dc6658b10b2cd874d9787ef03f1ae817050827c04d9c3596c1df2a` |
| Qualification source capsule | `4107841ced4a71784d48388179b2b23e61f06963a1031e1230c688f6c4f97a10` |
| Authoritative audit | `3d2a6d8618bbb04d15d0015ec220b330c94639cc2a39ff42baeba93863bc3616` |
| Auditor source | `50bcf7e75203f9a38907e31de560005126d6815e2d120a0f7abb88cf48c8e93b` |
| Final 542-test XML | `d1b1e3789eb92e95e5a53b4e8b3e639807338d7de05116c56a65dd7c5a8a1775` |

Generated numerical runs are ignored local artifacts. Exact regeneration needs
the pinned numerical environment and recorded source/input versions; a future
runtime change needs requalification, not an implicit equivalence assumption.

## Next step

MODEL-004 is ready. Preserve verified Cells 0.5.0 source before changing it;
implement the physical JAX pair against these frozen arrays and unchanged
targets, then verify full state/layout, controls, padding/identity, numerical
failure handling, observations, exact snapshots/branches and five-model regressions.
Do not add source gate quirks to generic infrastructure, or treat this physical
reference as completion of CONTACT-003. GPU, organ and continuing research-lane
jobs remain untouched.
