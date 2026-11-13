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

On the W1 hold's 825-node tissue, a converged root's residual sits at 0.8–1.1 of that
target: it is at the rounding floor of the current balance, not above it. Whether a
converged root is accepted then depends on how XLA compiled the evaluation.

- **The CPU vectorized program refuses** world 3 at [0.085, 0.086] s and world 1 at
  [0.186, 0.187] s. Their normalized residuals are 0.010193 and 0.0100014, against
  0.006940 and 0.003145 unbatched from the same states.
- **The scalar `jit` program and the NumPy path accept** the same steps. The scalar
  program reaches the edge later: it refuses world 3 at [0.452, 0.453] s (1.11 of the
  target) and world 1 at [0.464, 0.465] s (1.02).
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
  definition. New runs with finite extracellular space (a later full-tissue hold, E07)
  declare version 3. Old evidence stays reproducible exactly as recorded.
- **The agreement's worlds stay on version 2.** W1, W2 and G2-Q1 have no free field
  offsets, so the floor never decides there (see the margins below). Switching them would
  change registered definitions for nothing.

A switched definition is a new definition. It needs new snapshots and cannot resume a
version-2 snapshot, because the definition and its layout type differ.

## Which evidence could change

Values change only at steps that version 2 refused. Every run, guard and dump that never
reached the edge is bitwise in states, observations, diagnostics and ledgers.

What does change for a switched definition:

- the layout type: the model's floor layout (for the hold's model,
  `SurfacePumpChannelFloorLayout`) has one more leaf, `field_current_floor`;
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
2. **Dumps:** rerun the composite's guarded dumps with version 3 declared: W1, W2, G2-Q1,
   Q5, Q6, W37 and the 825-node world. This tests version 3; it does not switch those
   definitions. Every state, observation and diagnostic must match the version-2 dumps
   bitwise, except at steps version 2 refused, which are listed.
3. **Qualification judges:** rerun W1, W2 and G2-Q1's own judges with version 3 declared.
   The verdicts must be identical. These worlds have no free offsets, so this is a cheap
   control, not a risk.
4. **The defect's own cases (done on CPU; last section):** version 3 accepts the hold's
   worlds where version 2 refused, in the vectorized and scalar programs. It matches
   version 2 bitwise before that; the 200-step vectorized program was not compared state
   by state.
5. **L4:** the hold's worlds with version 3 from t = 0, on the L4 and on the CPU, past the
   CPU's edge steps: both must accept. The agreement's L4 terms are unchanged, because its
   worlds stay on version 2.

## Can a refusal class still differ by backend afterwards

Yes, at any threshold, but this one moves away from the noise. Version 3 moves the
field-solve edge from about 1× the rounding floor to 1e3× it. At the hold's four edge
states, every residual is within 2 ulps of its floor (last section), a margin of at least
500×. The measured backend and program differences in the residual are within about 5×.
They cannot cross that edge unless the Newton genuinely stalls within that factor of the
floor. A genuine stall is refused on every backend.

Other thresholds keep their designed margins:

- the explicit-stage guard, dt × membrane rate ≤ 1 (0.038 at the hold's edge steps);
- ledger tolerances, which scale with eps × steps × magnitudes;
- domain checks.

One structural mismatch remains. The loop stops on its trial norm, but acceptance uses
the evaluation after the loop. Under the floor test this no longer matters; it is a
reason not to tighten `NEWTON_TARGET`.

## Margins on the agreement's worlds (CPU)

The post-loop residual as a fraction of `NEWTON_TARGET`, at every K-th accepted state. It
was evaluated with `jit` (unbatched), and with `jit(vmap)` on one state and on six. Every
world declares solver version 2. The data is in `results/margins-*.json`.

| Family | Worlds | Free offsets | Worst fraction of the target |
| --- | --- | --- | --- |
| W1 trajectories | 6 | 0 | 0 (no Newton iteration) |
| W2 arms (stationary branches) | 8 | 0 | 0 (no Newton iteration) |
| G2-Q1 cases | 9 | 0 | 0 (no Newton iteration) |
| The hold's preparation worlds, from t = 0 | 3 | 172 | 0.92 unbatched, 0.98 batched, 0.995 batched six |
| The hold's six worlds at t = 8 s | 6 | 172 | 0.18 unbatched, 0.45 batched |

**The qualification worlds cannot reach this edge, so the agreement runs are not
exposed.** Every outside node is a held bath, or (W1's P5) the single floating component
is the gauge. The field Newton has no unknowns: it takes no iteration, and the residual is
exactly 0.

**The hold's tissue lives at the edge.** From t = 0, about half of its sampled states are
above 0.3 of the target, and the worst is 0.995. Exposure needs free field offsets, which
means finite extracellular space: the full-tissue worlds and E07.

## Version 3 on the hold's edge states (CPU)

`t0_v3.py` and `t0_scalar_v3.py` step the preparation's three worlds from t = 0, once
with version 2 and once with version 3 declared (`results/t0-v3.json`,
`results/t0-scalar-v3-w*.json`; version 2's widths from `results/t0-widths-main.json`).

| Program | Version 2 refuses | Version 3 | Equal to version 2 before that |
| --- | --- | --- | --- |
| Vectorized, windows of 1 to 186 steps | world 3 at [0.085, 0.086] s | accepts to 0.6 s | bitwise, 85 steps × 3 worlds (1-step windows) |
| Vectorized, 200-step windows | world 1 at [0.186, 0.187] s | accepts to 0.6 s | not compared |
| Scalar `jit`, world 1 | [0.464, 0.465] s | accepts to 0.6 s | bitwise, 464 steps |
| Scalar `jit`, world 3 | [0.452, 0.453] s | accepts to 0.6 s | bitwise, 452 steps |
| Scalar `jit`, world 2 | none to 0.6 s | accepts to 0.6 s | bitwise, 600 steps |

**The scalar program reaches the edge too.** At both scalar refusals, the failing term is
the start-of-step field solve: one Newton iteration, then 1.02 (world 1) and 1.11
(world 3) of the target. The refusal is not specific to `vmap`. Which step a program
refuses also depends on its window length.

**Every refused residual is within 2 ulps of its floor.** We lowered `current_floor` in
version 3's layout from 1e3 ulps (of eps × the incident sum) to 0:

- version 3 accepts the scalar edge states from 1 ulp;
- it accepts the vectorized edge states (world 3 at 0.085 s, world 1 at 0.186 s) from
  2 ulps batched, and at 0 unbatched, where version 2's own test passes.

So at the edge this tissue reaches, version 3's 1e3 ulps leave a margin of at least 500×.
