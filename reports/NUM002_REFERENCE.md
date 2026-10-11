# NUM-002: bioelectric reference qualification

Date: 2026-09-08 UTC. Outcome: independent CPU trajectories and a bounded
numerical-method candidate pass qualification for the
[one-cell physical specification](../docs/BIOELECTRIC_CELL_SPEC.md).
The [numerical contract](../docs/BIOELECTRIC_NUMERICS.md) fixes scope and settings.
This is not yet a fifth registered Cells model, production JAX acceptance,
BITSEY/BETSE parity, or biological validation. Cells remains 0.4.0.

## Delivered evidence

The [qualification receipt](../runs/num-002-2026-09-08/qualification/verification.json)
records 18 short cases, 30604 RK4 probe steps, and 122428 comparison points
covering accepted endpoints and quarter/half/three-quarter interval samples.
Radau/BDF and tightened Radau references agree. The independent absolute-amount
RK4 probe passes the physical targets with a maximum step of 0.005 s and
interval-held-control cubic Hermite observations.

Cases include isolated limits, independent/simultaneous leak and pump controls,
a 4 ms pulse, area/volume/permeability/capacity variants, heterogeneous leaks,
and pump reversal. Separate checks cover transient refinement, invalid
states/schedules/resources, analytic passive equilibrium, and a long passive
relaxation. No source experiment or production cell run was substituted.

| Quantity | Maximum short-panel error | Required limit |
| --- | ---: | ---: |
| Candidate ion amounts, endpoints and cubic observations | 1.37678e-9 fmol | 1e-7 fmol |
| Candidate leak ledgers | 1.39224e-9 fmol | 1e-7 fmol |
| Candidate pump cycle ledger | 4.74188e-11 fmol cycles | 1e-7 fmol cycles |
| Candidate voltage | 1.95771e-8 V | 1e-6 V |
| Reference-reference ion amounts | 1.24771e-11 fmol | 1e-8 fmol |
| Reference-reference voltage | 5.77935e-11 V | 1e-7 V |
| Per-species material-balance residual | 6.73904e-12 fmol | 1e-10 fmol |
| Charge-balance residual, expressed as voltage | 6.79422e-11 V | 1e-8 V |
| Bath-relative energy-identity residual | 7.14210e-9 pJ | 1e-6 pJ |

Maxima are over saved comparison points, not continuous-time supremum bounds.
All tested trial/accepted physical amounts remain positive, and sampled passive
and pump dissipation signs pass. The extra dissipation quadrature is a reference
diagnostic, not required additional biological state. The maintained bath and
chemical drive remain declared external support.

For orientation, the baseline 10 s probe ends at approximately -62.9913 mV with
Na/K/Cl amounts [11.819739, 140.188276, 10.007807] fmol. Its pump has completed
0.188868 fmol net forward cycles. These are synthetic dimensional results, not
a fitted resting-cell state or a physiological prediction.

## Findings retained, including failed alternatives

Linear observation interpolation fails the complete target set in 17 of the
18 cases at the selected 5 ms step. Its worst voltage error is 2.50043e-5 V,
versus 1.95771e-8 V with the qualified cubic policy on the same accepted states.
No physical parameter or accuracy target was changed. Event-side slopes matter:
a dedicated test shows that using the new control at the preceding interval's
right endpoint corrupts the interpolant.

The baseline's accepted-state voltage errors at 20, 10, and 5 ms are
8.50960e-8, 4.64989e-9, and 2.71657e-10 V; refinement ratios 18.3006 and
17.1168 pass the predeclared 14-22 range. A 40 ms negative control misses the
1e-6 V target with an error of 1.73507e-6 V. These checks qualify the method on
the panel; they are not a global nonlinear stability or positivity theorem.

The initial long passive comparison at `rtol=1e-11`, `atol=1e-13` narrowly
missed its 1e-8 fmol reference-agreement target: 1.11347e-8 fmol. Its partial
development output remains under `runs/num-002-2026-09-08/development-01` and
is not an accepted receipt. Refining to `1e-12/1e-14` passed amount agreement
but still missed the additional 1e-7 pJ dissipation-agreement target, at
1.26287e-7 pJ. Final `1e-13/1e-15` tolerances pass both without changing the
equations, horizon, or targets. These were numerical-reference refinements,
not biological model adjustments.

## Slow modes and preparation

The baseline's initial three-ion Jacobian has real eigenvalues approximately
[-15.8410, -0.00088493, -0.00026982] per second: local relaxation times near
0.0631, 1130, and 3706 s. These pointwise linear diagnostics explain why a
fixed short step may become costly over long physiological horizons; they do
not establish fixed biological timescales or select an organ-scale solver.

The all-leaks-open, pump-off equilibrium is independently obtained from a
scalar finite-capacitance charge root. Its voltage is -11.747952 mV, with
Na/K/Cl amounts [229.060128, 7.898625, 94.953234] fmol. Stationary flux residuals
pass the analytic-limit check.

A separate 100000 s Radau/BDF relaxation approaches that state but does not
meet the 1e-7 fmol equilibrium-amount target: maximum distance falls from
217.060 fmol initially to 0.646005 fmol halfway and 0.00316782 fmol at the end.
The final voltage is within 1.23787e-7 V. This is a completed finite-horizon
reference run, not a steady-state preparation certificate.

For that long run, solver agreement is 2.55795e-10 fmol in amounts,
1.23403e-12 V in voltage, and 2.03759e-8 pJ in dissipation. Energy balance is
within 2.11003e-10 pJ. No 100000 s RK4 or production run was performed. These
findings motivate later stiff or validated multirate methods and explicit
preparation criteria; they do not authorize a GPU or organ implementation.

## Reproduction, preservation, and verification

Using the pinned CPU environment from Cells and a new output directory:

```bash
taskset -c 0-3 .venv/bin/python -W error scripts/verify_bioelectric_reference.py --output runs/my-bioelectric-reference
taskset -c 0-3 .venv/bin/python -m pytest -q -W error
.venv/bin/ruff check src tests scripts
.venv/bin/ruff format --check src tests scripts
.venv/bin/python -m pip check
```

The reference script refuses an existing destination and records a failure
instead of publishing a passing receipt if qualification fails. It uses no
Cells imports, upstream checkout, network, installation, or GPU. Actual runtime
was Python 3.13.5, NumPy 2.5.3, SciPy 1.18.1, with affinity limited to CPU cores
0-3. Solver work/timings are diagnostic, not a hardware benchmark.

The final read-only artifact audit verifies all 39 payload hashes, finite numeric
arrays, and six retained reference/test/contract/lock source files against both
the live files and the source ZIP. The receipt SHA-256 is
`8cf0f7a6d33867f5a1172b6eff949c887bf47bf8c0c93d616477e72d4c27d94d`.
The source ZIP preserves the exact reference even when subsequent work changes
the live files; it is not a whole-project archive or a saved production world.

All **346 tests pass** with warnings as errors in 64.97 s: the previous 270
plus 76 independent-reference tests. The retained result is
[num-002-tests.xml](num-002-tests.xml). Production's 22 Python-file hashes still
match the verified 0.4.0 composition manifest; no production code, dependency,
old run, or historical acceptance receipt was changed. The earlier 74-check
instantaneous calculator remains separate and unchanged.

Lint, format, dependency, and Git whitespace checks pass. Documentation checks
cover 22 Markdown documents, 42 tables, and 271 local link occurrences including
heading anchors. Additional diagnostics confirm that an existing qualification
directory is refused without changing any file and an injected qualification
failure creates a failure record, not a passing receipt.

Next is MODEL-003: implement this physical cell and identified observation policy
through Cells' own shared engineering, then verify eager/JIT, independent
trajectories, exact events, full checkpoints/branches, and earlier-model
regressions. Preserve the verified 0.4.0 source before that package evolution.
