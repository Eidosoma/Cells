# NUM-009: short finite extracellular-compartment reference qualification

2026-09-10, D056. **First frozen attempt stopped — not qualified.**
Production remains Cells 0.13.0. No finite-outside production model, biological
acceptance, GPU result or inherited timestep is claimed.

The [protocol](../docs/FINITE_EXTRACELLULAR_NUMERICS.md) and
[panel](../configs/reference/finite_extracellular_trajectories_v1.json) freeze
fourteen short cases / 112 attempts, including two tiny-outside synthetic stress
cases. The panel SHA-256 is
`81e7e68a1821a57dc9e8b96889dfcc0d9b4eca514785f4aac9dce32a77aff397`.

Both paths retain all ten physical state fields as anchored amount increments,
gates and complete histories. Independent hyperbolic Radau/BDF references use a
linear conservation-consistent outside reconstruction, including every Jacobian
probe and dense-basis coefficient. The Bernoulli RK4 candidate evolves outside
increments independently; its balance is checked rather than projected.

## Retained preflight correction

The [first preflight](num-009-preflight-01.xml) has 85 passing tests and one failed
cubic-countercharge corruption test. A companion-matrix root calculation lost a
finite stationary point when the cubic coefficient was near roundoff size:
the polynomial [0, 1e-13, -1e-13, 1e-30] was incorrectly assigned zero maximum
instead of approximately 2.5e-14. A scaled, cancellation-resistant quadratic
formula now finds the cubic derivative's roots, including linear/constant cases.

The [correction record](num-009-preflight-correction.json) preserves the exact
old checker/test source and failed receipt. The [second preflight](num-009-preflight-02.xml)
passes all **101 tests**, including fifteen near-degenerate scale/sign cases.
The physical equations, frozen inputs, solver settings and tolerances did not
change. Earlier accepted production/reference files have not been patched.

A [read-only review](num-009-prior-graph-extrema-review.json) applies the stable
stationary-root calculation to all 48 actual saved NUM-008 candidate records.
All 48 whole-cubic domain checks still pass, with **zero changed verdicts**.
It takes 26.789 s, reruns no solver and changes no old source or evidence file.
This checks that bounded saved panel, not all possible earlier cubic inputs.

## Frozen attempt and evidence

The [prospective registration](num-009-registration.json) precedes the first
session, [reference-01](../runs/num-009-2026-09-10/reference-01/failure.json).
It runs 80 attempts across ten complete case ladders in **227.342 s**, retaining
**77,109,196 bytes** under the declared 1800 s / 512 MiB bounds. One CPU worker
(CPU 4), single-thread libraries and the frozen runtime/settings are retained.
This is qualification work, not a simulation performance benchmark.

The first nine cases pass all three independent reference gates. The tenth,
`star_mono_internal`, stops the session at the predeclared reference gate. Every
attempt in those ten ladders has a complete native trajectory and saved dense
data: 30 implicit and 50 RK4 attempts. Four completed 4 ms candidates fail their
observed-accuracy budgets (disconnected cells, pair, mono/divalent stars), with
maximum normalized errors 1.301679, 1.298604, 1.267400 and 1.268718. Those verdicts
remain failures. There are no rejected candidate stages in this completed prefix.

No timestep is selected. The remaining full-panel block/release, short-pulse,
pump-only depletion and tiny-divalent-outside cases are **unrun**. Short synthetic
preflight coverage is not substituted for those missing qualification cases.
In particular, the planned 5% depletion witness has not been evaluated.

The separate [stopped-attempt auditor](../scripts/audit_finite_extracellular_attempt.py)
authenticates **174 payloads / 31 captured sources** and exactly replays all
**80 arrays / 184,240 sampled rows**, then recomputes the saved accounting,
controls and accuracy verdicts. Its [receipt](num-009-stopped-attempt-audit.json)
passes as an evidence audit, with qualification explicitly `stopped_not_qualified`
and selected step null. It does not rerun a solver or manufacture a whole-panel
acceptance receipt. The stopped-session failure receipt SHA-256 is
`7dd501991ab3c61144d3f8862f91a8b76c146619e5c554b2b9fd46a5c87f3e67`.

## Why the reference stopped

In the junction-only star, every membrane route is off. Junctions may redistribute
ions between cells, but the outside derivative must be exactly zero. All five
RK4 candidates retain an exactly constant outside increment and pass this case.
The implicit reference instead reconstructs outside increments as the negative
sum of independently evolved intracellular increments. Floating-point internal
exchange leaves a tiny summation residual, which becomes stored outside state.

| Implicit reference | Largest observed outside increment, fmol | Exact blocking |
| --- | --- | --- |
| Radau | 6.507750e-19 | Fails |
| BDF | 5.425096e-19 | Fails |
| Refined Radau | 7.592961e-19 | Fails |

Native outside increments exactly equal the negative inside sum, confirming the
coordinate reconstruction. All reconstructed physical outside amounts round to
their original constants. Both native and observed charge/material/energy checks
and every reference-reference accuracy comparison pass. This is therefore a
representation-level failure of the declared exact invariant, not a resolved
physical leakage or a biological finding. A smaller numeric discrepancy does
not satisfy an exact complete-state contract. It is not waived or rounded away.

The short preflight had an all-off interval, where both inside and outside stay
fixed, but did not expose this cancellation under continuing junction exchange.
The retained failed-case audit tests now specifically detect its hidden outside
state, reject a forged passing analysis and refuse invented missing cases.

## Tests and preservation

All **109 targeted tests pass** in the [post-attempt receipt](num-009-targeted-01.xml):
101 numerical/preflight tests and eight stopped-evidence audit checks, with no
failures, errors or skips in that run. Complete-session acceptance tests were
authored prospectively but have not been executed against completed evidence;
there is no such session. The strict full build matrix has **not been rerun or
declared passing**. Its earlier 3298-test SPEC-008 result remains historical.
This numerical gate remains open, so no production acceptance is implied.

The [previous production audit](num-009-core008-audit.json) passes again:
600 saved payloads, 223 captured implementation files and all 46 production
modules. No ODE is rerun. The [pre-edit baseline](num-009-workspace-baseline.json)
includes 516 existing files and the user's uncommitted work. All 507 non-edited
files remain byte-identical; nine existing documents have status/design-only
updates. No prior file is missing. Production, packaging, test-context driver,
earlier reference/pilot data and the failed formal session remain unchanged.
All 230 Python files pass Ruff lint/format checks; dependency and whitespace
checks pass. The [attempt closeout](num-009-attempt-closeout.json) binds the
artifacts, exact preservation hashes and final documentation checks.

## Required next engineering step

NUM-009 needs a revised **general** reference representation before a new frozen
qualification. Prefer investigating full explicit inventory increments with
conservation-consistent Jacobian linearization/probes; compare a properly derived
constrained-coordinate alternative. The former is a recommendation, not yet an
implemented or qualified method. It should preserve both conserved totals and
each disabled inventory without extracting an inventory from other compartments'
floating-point cancellation.

Do not just choose a convenient dependent cell for this star, reset/zero the
outside after steps, reanchor, infer amounts from transfer histories or relax
blocking/charge checks. Preserve this version's complete source/audit context;
declare any method change and new resources before a fresh destination/run.
No automatic retry or reference modification followed the frozen stop here.

CORE-009 comes only after that qualification: an explicit anchor/coordinate
adapter, CPU/JAX implementation, restart/branch/window/cohort and complete-state
checkpoint acceptance. No production, cross-organ, mesh, GPU optimization,
biological or deferred E02 campaign is started in this slice.
