# Floor-aware field-solve acceptance for solver version 2 (design note, proposed)

Status: proposed for the lead's and the advisor's review, 13 November 2026. No code has
changed. The evidence is in `/mnt/workspaces/Cells/window-timing-20261112-01/`
(`summary.json`, `results/t0-*.json`, `results/margins-*.json`).

## The defect

`capacitive_reduction_gauged_damped_newton@2` (`numerics/surface_field.py`) accepts a
field solve when, after the damped Newton loop, the evaluation at the final offset gives

    max_k |R_k| / (CURRENT_ATOL_A + CURRENT_RTOL x scale) <= NEWTON_TARGET = 0.01,

where `R_k` is component `k`'s Kirchhoff current residual and `scale` is the largest face
or junction current. The loop decides to stop on the same test, evaluated on its last
line-search trial.

On the W1 hold's 825-node tissue, a converged root's residual sits at 0.7–1.0 of that
target: it is at the rounding floor of the current balance, not above it. Whether a
converged root is accepted then depends on how XLA compiled the evaluation.

- **The CPU vectorized program refuses** world 3 at [0.085, 0.086] s (0.010193 of the
  tolerance, against 0.006940 unbatched from the same state) and world 1 at
  [0.186, 0.187] s (0.0100014 against 0.003145).
- **The scalar `jit` program and the NumPy path accept** the same steps.
- **The L4 accepted** these worlds over 0–6 s, and has since accepted more than 1,100
  windows of the hold.

So the refusal class differs by backend and by program.

## The floor, and why it is the attainable accuracy

Version 3 (`capacitive_reduction_gauged_damped_newton@3`, opt-in since 9 November) keeps
version 2's iterations. After the loop, it also accepts a residual within
`CURRENT_FLOOR_ULPS` (1e3) ulps of its potentials:

    floor_k = CURRENT_FLOOR_ULPS x eps x ( sum over faces f incident to k of
                  G_f (|phi_sender| + |phi_receiver|)
              + sum over junctions j incident to k of
                  slope_j (|phi_a| + |phi_b|) )
    accept if |R_k| <= floor_k for every component k

`G_f` is a face's conductance and `slope_j` a junction current's slope with respect to its
voltage.

Why this is the attainable accuracy:

- A component's offset, and so every potential `phi`, is resolved only to about
  `eps |phi|` in float64.
- One ulp of `phi` moves each incident current by its conductance (or slope) times
  `eps (|phi_s| + |phi_r|)`.
- The residual is the sum of those currents, so its computed value cannot be driven
  below about `eps` times the incident sum, whatever the Newton does.

In the ledger fix, the P2 and P4 parity states that version 2 refused measured
1.2 eps × the incident sum, under XLA and NumPy alike. Their relative norms differed
fivefold between the two.

`1e3` ulps is a potential error of about 1e-14 V. A solve that genuinely stalls above it
is still refused.

## Adopt the rule in version 2, or route to version 3

**Recommended: route definitions to version 3; leave version 2 unchanged.**

- **A version ID promises its semantics.** Every qualified world (W1, W2, G2-Q1), the
  hold and every saved snapshot declares version 2. Changing version 2's acceptance would
  change what those IDs mean, retroactively.
- **Changing version 2 would change every version-2 jaxpr.** The composite's
  cross-revision guards compare jaxprs, so they would flag every world. The values would
  still be bitwise wherever version 2 converges.
- **Version 3 already exists and is tested** (`tests/unit/test_field_floor.py`): it is
  bitwise equal to version 2 on every fixture where version 2 converges. It refuses a
  solve stopped above the floor. Its snapshots round-trip and resume bitwise.
- **Routing is a definition choice, not a code change.** `field_solver` is part of each
  definition. New runs (the agreement runs, a later full-tissue hold, E07) declare
  version 3. Old evidence stays reproducible exactly as recorded.

A switched definition is a new definition: new snapshots, no resume across the switch.
Batch snapshots check every source file's hash, and the layout type differs.

## Which evidence could change

Values change only at steps that version 2 refused. Every run, guard and dump that never
reached the edge is bitwise in states, observations, diagnostics and ledgers.

What does change for a switched definition:

- the layout type (`FloorLayout`, one more leaf, `current_floor`);
- the jaxpr, which gains the floor computation after the loop. Its only output is the
  solve's `converged`, and so the step's validity.

Runs that stopped at a refusal of this class would continue under version 3. Their later
records are new evidence and get judged as such.

## Guard plan

1. **Cross-revision (jaxprs and bindings):**
   - Version-2 definitions are unchanged, so their guards stay as they are.
   - For each world switched to version 3, show that the jaxpr differs from version 2's
     only by the post-loop floor operations and the extra layout leaf.
   - Show that the step's state outputs do not depend on the floor except through
     validity.
2. **Dumps:** rerun the composite's guarded dumps with version 3: W1, W2, G2-Q1, Q5, Q6,
   W37 and the 825-node world. Compare every state, observation and diagnostic bitwise
   with the version-2 dumps, and list any step that version 2 refused.
3. **Qualification judges:** rerun W1, W2 and G2-Q1's own judges with version 3. The
   verdicts must be identical, or changed only where version 2 had refused.
4. **The defect's own cases:** the CPU vectorized hold worlds at 0.085 s and 0.186 s must
   be accepted under version 3. Record each residual's ratio to its floor.
5. **L4:** the agreement's backend terms with version 3. The stop rule then no longer
   sees this refusal class unless a solve genuinely stalls.

## Can a refusal class still differ by backend afterwards

Yes, at any threshold, but this one moves away from the noise. Version 3 moves the
field-solve edge from about 1× the rounding floor to about 1e3× it. The measured backend
and program differences in the residual are within about 5×, so they cannot cross that
edge unless the Newton genuinely stalls within that factor of the floor. A genuine stall
is refused on every backend.

Other thresholds keep their designed margins:

- the explicit-stage guard, dt × membrane rate ≤ 1 (0.038 at the hold's edge steps);
- ledger tolerances, which scale with eps × steps × magnitudes;
- domain checks.

One structural mismatch remains. The loop stops on its trial norm, but acceptance uses
the evaluation after the loop. Under the floor test this no longer matters; it is a
reason not to tighten `NEWTON_TARGET`.

## Margins on the agreement's worlds (CPU)

The post-loop residual as a fraction of `NEWTON_TARGET`, worst state per world family:
unbatched, batched one world at a time, and batched six at a time. The data is in
`results/margins-*.json`; every K-th accepted state was evaluated.

| Family | Worlds | Free offsets | Worst fraction of the target |
| --- | --- | --- | --- |
| W1 trajectories (water @1) | 6 | 0 | 0 (no Newton iteration) |
| W2 arms (water @2, stationary branches) | 8 | 0 | 0 (no Newton iteration) |
| G2-Q1 cases (replacement @1) | 9 | 0 | 0 (no Newton iteration) |
| The hold's worlds from t = 0 (@3, finite extracellular space) | 3 | 172 | 0.80–0.995 |
| The hold's six worlds at t = 8 s | 6 | 172 | 0.04–0.45 |

**The qualification worlds cannot reach this edge.** Every outside node is a held bath,
or the single floating component is the gauge, so the field Newton has no unknowns. It
takes no iteration, and the residual is exactly 0.

**The hold's tissue lives at the edge.** From t = 0, about half of its states are above
0.3 of the target and the worst is 0.995. The CPU's scalar `jit` trajectory itself was
refused near 0.45 s (world 3) and 0.46 s (world 1).

**Exposure needs floating capacitor components**, which means finite extracellular
space. That covers the full-tissue worlds and E07.
