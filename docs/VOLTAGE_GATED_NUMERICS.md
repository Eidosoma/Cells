# Coupled cell/channel numerical qualification

NUM-007 / D050, 2026-09-09. This protocol and its
[panel](../configs/reference/voltage_gated_trajectories_v1.json) are fixed before
trajectory evaluation. They extend [SPEC-006](VOLTAGE_GATED_CHANNEL_SPEC.md)
without changing its panel, production Cells 0.11.0, or prior evidence.
Results and any rejected attempts belong in a separate qualification report.

## Frozen physical cases

Fourteen cases use the two unchanged SPEC-006 assemblies. Each has baseline,
depolarized, channel-only, independent block/release and short-channel-pulse
profiles. The monovalent assembly additionally has two equal-open-fraction
preparations, a gates-only case and a disabled-channel reduction. Horizons are
0.1–2 seconds: short engineering trajectories, not equilibrium or physiology.
The unbuffered synthetic Ca species is not calcium signaling.

Baseline definitions are unchanged. Other initial gates are explicitly stated.
Depolarized and equal-open cases declare both a new initial voltage and a
consistent fixed-charge anchor; amounts, bath, geometry and transport parameters
are unchanged. This is a new synthetic initial preparation, not a change of
charge anchors during evolution or a hidden electrode. No input is fitted.

Block/release independently changes channel availability, pump and Na leak;
it includes an all-transport-off interval [0.113, 0.407] s and a final-time event.
A channel pulse at [0.0203, 0.0204] s is shorter than every candidate step.
Resolve controls by species ID; unknown/duplicate bindings are refused. Split
integration at every event, retain complete state and original anchors, and use
the old interval's controls at its endpoint stages/slopes. Final-time settings
change only right-continuous readouts, not preceding evolution.

In the gates-only case every ionic route is off, so amounts and ionic histories
are exactly constant and voltage stays at its charge-owned +60 mV value.
The gates still relax. This gives a coupled-state reduction to SPEC-006's analytic
solution; it is not a supported whole-cell voltage clamp. Equal initial m h does
not imply equal subsequent gates or voltage under a shared input.

## Independent formulation and full state

The canonical reference coordinates are:

```text
[amount increments S, baseline-leak ledgers S, pump cycles, ionic dissipation pJ,
 activation m, inactivation h, channel transfer H]
```

The implicit reference extends NUM-006's independent hyperbolic transport and
affinity pump formulation with a separately expressed hyperbolic channel flux
and the literal native millivolt/millisecond gate expressions. Radau and BDF
evolve amount increments. They do not call the SPEC-006 gate/flux evaluator.
The separate candidate evolves absolute amounts and uses that scalar Bernoulli
evaluator with both gate derivatives at the same solver-stage voltage.
Neither imports production Cells or JAX.

Reuse the unchanged reference grid/dense-record infrastructure where its
dimension-independent contract applies; add explicit gate/channel semantics.
No special-case gate equilibrium, held-voltage split update, reanchoring,
clipping or discarded disabled state is permitted. m/h are primary state;
open fraction is a readout. H is separate from baseline and pump histories.

## Methods, observations and predeclared limits

On every control interval compare Radau and BDF at rtol 1e-11, atol 1e-13 and
maximum step 0.005 s with refined Radau at rtol 1e-12, atol 1e-14 and maximum
step 0.0025 s. Local tolerances act on the stated mixed coordinates; they do not
guarantee global accuracy. These settings must match saved source and receipts.

The candidate ladder is coupled RK4 at **0.002, 0.001, 0.0005 and 0.00025 s**.
It does not inherit NUM-006's 10 ms acceptance. Use a zero-anchored regular mesh
unioned with all events, independent of observation requests. Compare native
candidate endpoints and interval-control cubic Hermite observations separately.
The common observation mesh is the union of endpoints and quarter/half/three-
quarter points from all candidate meshes, including event-split intervals.
Native points return saved states exactly. Save the full dense basis for replay.

| Quantity | Candidate maximum absolute error | Reference-reference maximum |
| --- | --- | --- |
| Ordinary amount and baseline ledger | 1e-7 fmol | 1e-8 fmol |
| Synthetic Ca amount and baseline ledger | 1e-9 fmol | 1e-10 fmol |
| Pump cycles and channel ledger | 1e-7 fmol | 1e-8 fmol |
| Voltage | 1e-6 V | 1e-7 V |
| Ionic dissipation | 1e-6 pJ | 1e-7 pJ |
| Each gate and open fraction | 1e-4 | 1e-5 |

These are engineering limits set before evaluation, not parameter uncertainty
or biological agreement. Report sampled error maxima, not rigorous global
continuous-time error bounds. Analytic gates-only comparisons use the same
gate budget (the tighter reference factor for implicit methods).

Require material residual `delta_n - L - nu P - e_k H` within 1e-10 fmol
(1e-12 for Ca), its charge residual within 1e-8 V, and ionic chemical/capacitor
energy change plus dissipation minus supplied pump work within 1e-6 pJ.
Use stable energy differences with log1p. Dissipation may not decrease by more
than 1e-10 pJ between inspected samples. No gate-protein energy is modeled.
Disabled-route histories are exactly constant. When all transport is off,
the entire ionic substate and H are constant, **not** m/h.

Check every actual RHS trial, including implicit Jacobian probes, accepted
state and observed state: finite positive amounts, per-species |zFV/RT| <= 50,
-0.120 <= V <= 0.060 V, and both gates in [0,1]. No domain tolerance or clipping.
For every complete candidate cubic interval inspect polynomial extrema of all
amounts, voltage and both gates, even when no sample lands at that extremum.
This checks the polynomial's domain within floating arithmetic, not its error.
Implicit dense domain is checked at native endpoints, trials and comparison
points; no whole-polynomial domain guarantee is claimed for its interpolation.

Select the coarsest candidate passing every case whose next-finer trial also
passes every case. For each case require both voltage error and maximum gate
error to improve by a factor <= 0.8, except below floors 1e-10 V and 1e-8
respectively. The finest trial alone cannot qualify. A rejected coarse trial
does not disqualify a finer eligible pair. If no pair qualifies, report that
outcome; do not tune inputs, limits or extend the ladder after seeing results.

## Bounded execution and failure preservation

One CPU worker, existing float64 NumPy/SciPy environment, at most 14 cases and
98 declared attempts (three implicit plus four candidate attempts per case).
Cap the session at 900 wall seconds, 128 MiB of artifacts, 100000 RHS calls and
100000 accepted steps per attempt, and 100000 common samples per case.
These are work/output caps, not an operating-system RAM guarantee.

Freeze and capture protocol, resolved cases, numerical/checker/auditor/tests
and dependency sources before integration. Use a new directory; refuse any
existing destination. Keep native states, dense coefficients, comparison data,
per-attempt statistics, verdicts and failures. Artifact audit runs read-only.

A candidate domain rejection retains its completed prefix and the exact rejected
stage, stage time, held control and reason, and the declared ladder continues.
Never construct comparisons over its missing suffix or promote a partial path.
Reference failure or exhausted work/output budget stops the session, retaining
completed artifacts and a stopping receipt. No automatic retry/extension follows.
Ordinary accuracy or candidate-cubic-domain failures remain recorded verdicts.
Preflight tests use explicitly smaller synthetic fixtures, not an unreported
trial of the frozen scientific panel.

The read-only auditor checks frozen/current/archive identities, exact payload
inventory, settings, case bindings, candidate meshes and dense replay; it
recomputes numerical/accounting verdicts and candidate selection. A rejected
trial must independently violate its stated domain and bind to its recorded
prefix and held control. Stage-domain extrema for successful attempts are
instrumented summaries, not a saved/replayed transcript of all adaptive trials.
Hash checks are provenance/integrity checks, not proof of experimental biology.

## Production and future multiscale boundary

Passing qualifies only these preparations, schedules, horizons and equations.
CORE-007 must separately implement a new CPU/JAX identity, numeric gate/channel
axes, pure shared-stage dynamics, preflight, observations, complete snapshots,
branching and scalar/cohort acceptance against this reference. Old models,
source identities and timestep limits remain unchanged. No optimizer, GPU
installation/execution, organ graph, finite bath, biological refit or deferred
E02 campaign is part of NUM-007. Later multirate or reduced models must retain
or explicitly approximate slow gate history and quantify their additional error.
