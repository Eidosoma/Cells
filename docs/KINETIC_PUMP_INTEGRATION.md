# Substrate-dependent Na/K pump: integration contract and numerical gate

2026-09-16, D109 / SPEC-010 / NUM-011 candidate. The user authorized independent
contact review, production integration and coupled validation. The
[source-contact review is complete](../reports/REF005A_PUMP_CONTACT_CLOSEOUT.md).
This document specifies the production route and implements its **coupled
numerical prerequisite**, not a released production family.

## Named mechanism and metabolic boundary

Proposed identity: `nak_atp_mass_action_positive@1`, with explicit Na/K species
roles and −3/+2 inward coefficients. It follows the audited positive-domain
[kinetic equation](BETSE_PUMP_CONTACT.md), not the existing
`nak_atp_affinity_tanh@1`. Both should remain available under distinct identities.
Do not subtract an old synthetic pump to retrofit a new one into an accepted
RHS, or modify the solver for a source experiment.

Per membrane, declare maximum cycle density in mol/m²/s, KmNa/KmK/KmATP in mM,
ATP/ADP/Pi concentrations in mM and standard hydrolysis energy in J/mol. Temperature,
membrane area, local voltage and instantaneous inside/outside ionic concentrations
are supplied through the normal physical interfaces. Concentrations use a
declared standard state; no hidden fit or species-name branch enters the kernel.

Initially ATP, ADP and Pi are **maintained chemical reservoirs**, not depleted
intracellular inventories. Their drive is
`deltaG0 + RT log(ADP*Pi/(1000*ATP))`. With fixed pools and temperature this is
constant, so the existing signed cycle ledger can account for supplied chemical
work. A dynamic metabolic pool or time-varying drive needs additional owned
chemical state/work integration, not an observer update or a silently reused
constant-drive formula.

The first law accepts strictly positive substrates and finite parameters, with
`|cycle free energy / RT| <= 80`. Invalid trials are refused; there is no
concentration floor, equilibrium reset or repair. Zero *pump capacity* or
availability gives exact zero transfer; it does not excuse an invalid physical
compartment. Zero-substrate limiting kinetics and reversible metabolic synthesis
over a wider domain remain separately specified extensions. Native BETSE's
zero-denominator guard is not adopted as a physical depletion law.

## Conservative composition and ownership

Use the existing finite-extracellular design: cell and outside amount increments,
charge-derived voltage, signed leak/cycle ledgers and membrane dissipation.
One inward membrane transfer contributes once to its cell and once, with the
opposite sign, to its outside owner. Pump current is derived from that same
transfer; it is not another independent charge update. Evaluate all mechanisms
against the same solver-stage concentrations and voltage.

```
membrane_amount_rate = passive_leak + stoichiometry * cycle_rate
inside_amount_rate   = owned membrane transfers + owned junction transfers
outside_amount_rate  = negative owned membrane transfers
pump_dissipation    = -1e-3 * cycle_rate_fmol_s * cycle_free_energy_J_mol
chemical_power_pJ_s = -1e-3 * cycle_rate_fmol_s * chemical_drive_J_mol
```

Use full finite-system ionic chemical energy plus each capacitor's energy once.
Check `energy_change + dissipated_energy - supplied_chemical_work = 0` alongside
material and countercharge checks. A maintained-bath grand potential cannot be
substituted when the bath inventory evolves. Junction flux must not enter the
outside ledger.

## Executable coupled candidate now

The new `validation/betse/pump_coupled/` harness composes the audited array pump
with the existing Cells constant-field leak and shared checked JAX RK4 primitive.
No production file is edited. A separately written scalar mass-action/symmetric-
flux RHS and adaptive **DOP853 and Radau** integrations run in a separate process
without importing Cells, JAX or BETSE. Neither candidate nor reference invokes
a native BETSE cell world; this is a Cells-side physical/numerical qualification.

Six prospective synthetic cases, each 10 ms:

1. One-cell pump plus passive Na/K/Cl leak.
2. Pump only.
3. Leak only, with the pump blocked.
4. All transport blocked.
5. Pump suppression from 4 to 6 ms, then release; passive leak continues.
6. Two heterogeneous cells sharing one small finite bath.

Fixture preparation declares fixed charges and initial capacitor voltages
explicitly. These are manufactured synthetic initial conditions, not fitted
oocyte data or a runtime neutralization step. The three-species harness is a
reference coordinate system, not a universal production species limit. Na/K
roles follow explicit index mappings, including a permutation check.

Each cell contributes eight evolving coordinates: three amount increments,
three leak integrals, signed cycles and dissipated energy. The shared outside
adds three coordinates. Thus the complete state has 11 values for one cell or
19 for the two-cell case. All are retained for restart; no voltage is integrated
independently. Membrane channel and junction gates are absent in this first
candidate, not inferred to be qualified with the new pump.

Candidate step sizes are **100 and 50 µs**, not an inherited accepted timestep.
Run NumPy and compiled JAX at both: 24 trajectories, plus 12 complete-state
restart suffixes at 6 ms. Eager JAX gets bounded instantaneous smoke checks, not
a claimed full eager trajectory panel. Independent references add 12 trajectories.
Keep all candidate endpoints and 1 ms comparison samples, including exact input
boundaries; checkpoints undergo JSON round-trip and exact-value suffix checks.

Prospective numerical budgets:

| Quantity | Bound |
| --- | --- |
| Complete-state agreement | 1e-8 fmol for amounts/cycles, 1e-8 pJ for energy; plus 2e-7 relative |
| Derived membrane voltage | 1e-7 V |
| Material-history residual | 2e-11 fmol |
| Charge residual | 1e-20 C |
| Full finite-system energy residual | 2e-8 pJ |
| Refinement | Fine scaled error <= max(0.25 coarse, 0.001 roundoff floor) |

These budgets and all fixtures are registered before the full panel. The
roundoff floor does not support a measured convergence-order claim. Check all
candidate endpoint ledgers and reference sample ledgers, exact complete blocking,
unchanged cycle history while pump transport is suppressed, saved-sample linkage
and full restart suffixes. Positivity/domain checks occur at every candidate RK4
stage. Whole Hermite interiors, ordinary runner/checkpoint/branch/window/cohort
acceptance and fresh-process production restart remain later gates.

## Production implementation after numerical review

1. Inspect the detached candidate result and independently review saved coupled
   evidence before declaring a timestep qualified. A capture pass is not review.
2. Authenticate/archive accepted 0.15.0.dev0 and its test/source contexts before
   changing production identity. Preserve old configurations and exact replay;
   never relax a source hash to make old checkpoints load under new equations.
3. Add a pure typed kinetic-pump process and a versioned finite-bath configuration
   route. Store explicit law/roles/metabolic coefficients in numeric layout;
   choose the process in the composing model, never the time integrator. Reuse
   existing state owners, input schedules and unit-aware readouts. Keep the
   existing synthetic family and its accepted bounds unchanged.
4. Add host parameter validation, neutral inactive padding and stage/interior
   pump-domain checks, then verify ordinary run, complete restart/branch,
   homogeneous batches/windows and independent all-state accounting.
5. Run a separately bounded acceptance and old-model regression. Stable promotion
   is explicit, not implied by adding a kernel or by this candidate's success.
6. Measure the pinned native pump driver's ordering, area/rho/boundary treatment
   and initial preparation before a whole-cell BETSE comparison; then extend
   to longer relaxation and the original-data biological benchmark.

Production integration therefore stays **pending the coupled numerical gate**;
the authorized work is staged, not silently marked complete. No equations,
numerical limits, native state semantics or biological claims are changed to
make the test pass.

## CPU/GPU and job boundary

Pure batched local laws and a single signed transfer per interface fit the
multiscale ownership design. A shared bath is one world-level state, not a
private replica per GPU partition. Device reductions, larger graphs, multirate
coupling and adaptive resolutions need separate accuracy/resource evidence.
No GPU qualification or speedup follows from compiled CPU JAX.

The full candidate runs detached: CPUs 0–3, **240 s per worker / 600 s total**,
**16 MiB/file / 64 MiB aggregate disk artifacts**, not a RAM limit. Source-contact
closeout, accepted implementation bytes, source capsule and software receipt are
authenticated before either worker. Preserve durable logs/results/failures.
Return without polling, retry, automatic post-capture audit or regression.
