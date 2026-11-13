# Floor-aware field-solve acceptance (design note, approved as a routing policy)

Status: approved by the lead as a routing policy on 13 November 2026, after the advisor's
review. Version 2 is unchanged and new definitions with free field offsets declare
version 3 (D147, drafted). No engine code has changed. The evidence is in
`/mnt/workspaces/Cells/window-timing-20261112-01/` (`summary.json`, `results/t0-*.json`,
`results/margins-*.json`) and, for the guards, in
`/mnt/workspaces/Cells/field-floor-guards-20261113-01/` (last section).

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
- **Version 3 already exists and is tested** (`tests/unit/test_field_floor.py`) on the
  `resolved_pump_tissue@1` and `@2` fixtures. There it is bitwise equal to version 2
  wherever version 2 converges, it refuses a solve stopped above the floor, and its
  snapshots round-trip and resume bitwise. The hold's model, `resolved_pump_tissue@3`, is
  now covered by `tests/unit/test_field_floor_pump_v3.py` and
  `tests/unit/test_field_floor_held.py` (guard 6).
- **Routing is a definition choice, not a code change.** `field_solver` is part of each
  definition. New runs with finite extracellular space (a later full-tissue hold, E07)
  declare version 3. Old evidence stays reproducible exactly as recorded.
- **The agreement's worlds stay on version 2.** W1, W2 and G2-Q1 have no free field
  offsets, so the floor never decides there (see the margins below). Switching them would
  change registered definitions for nothing.

A switched definition is a new definition. It cannot resume or start from a version-2
checkpoint: `validate_checkpoint` (`core/runner.py`) refuses a layout without the floor
leaf, and the hold's driver refuses a resume snapshot that holds other definitions. For
the running hold, a refusal of this class on the L4 would mean a rerun from t = 0 (start,
preparation and run) under version 3, not a resume.

## Which evidence could change

Values change only at steps that version 2 refused. Every run, guard and dump that never
reached the edge should stay bitwise in states, observations, diagnostics and ledgers.
The CPU runs in the last section show it for states; guard 2 checks the rest.

What does change for a switched definition:

- the layout type: the model's floor layout (for the hold's model,
  `SurfacePumpChannelFloorLayout`) has one more leaf, `field_current_floor`;
- the jaxpr, which gains the floor computation after the loop. Its only output is the
  solve's `converged`, and so the step's validity.

A run that stopped at a refusal of this class is rerun under version 3 from its start,
not resumed (see above). Its records after the old refusal are new evidence and get
judged as such.

## Guard plan

1. **Jaxprs and bindings (done: pass; last section):**
   - Version-2 definitions are unchanged, so their guards stay as they are.
   - For each world switched to version 3, show that the jaxpr differs from version 2's
     only by the post-loop floor operations and the extra layout leaf.
   - Show that the step's state outputs do not depend on the floor except through
     validity.
2. **Runs (done: equal; last section):** rerun the composite's guarded runs with version 3
   declared: W1, W2, G2-Q1, Q5, Q6, W37 and the 825-node world. This tests version 3; it
   does not switch those definitions. Every state, observation and diagnostic must match
   version 2's bitwise, except at steps version 2 refused, which are listed.
3. **Qualification judges:** rerun W1, W2 and G2-Q1's own judges with version 3 declared.
   The verdicts must be identical. These worlds have no free offsets, so this is a cheap
   control, not a risk. (Not run: guard 2 already shows their runs bitwise.)
4. **The defect's own cases (done on CPU; the section before last):** version 3 accepts the
   hold's worlds where version 2 refused, in the vectorized and scalar programs. Its states
   match version 2's bitwise before that; the 200-step vectorized program was not compared
   state by state.
5. **L4 (steps 6–7 of `l4_dispatch_plan.sh`):** the hold's worlds with version 3 from
   t = 0, on the L4 and on the CPU, past the CPU's edge steps: both must accept. Record the
   L4's floor multiple at those steps, because the 500× margin (in ulps) was measured on
   the CPU only. The agreement's L4 terms are unchanged, because its worlds stay on
   version 2.
6. **A unit test for `resolved_pump_tissue@3` with version 3 (done: pass; last section)**,
   as `test_field_floor.py` does for `@1` and `@2`, on a small fixture with free offsets:
   bitwise equal to version 2 where version 2 converges, a root at the floor accepted, one
   above it refused, and a checkpoint round trip. It also holds a solve just under the cap
   on the 825-node tissue.

## Can a refusal class still differ by backend afterwards

Yes, at any threshold, but this one moves away from the noise. Version 3 moves the
field-solve edge from about 1× the rounding floor to 1e3× it. At the hold's four edge
states, every residual is within 2 ulps of its floor (see "Version 3 on the hold's edge
states"), a margin of at least 500× in ulps. The measured backend and program differences
in the residual are within about 5×. They cannot cross that edge unless the Newton
genuinely stalls within that factor of the floor. A genuine stall is refused on every
backend. Nothing else catches an inaccurate solve: the row checks and ledgers pass even
under a cap 1e9 times wider (the positive control in the last section).

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
means finite extracellular space: the full-tissue worlds, E07-v1's among them. The turnover
pre-screen's held-bath sheets have none (last section).

## Version 3 on the hold's edge states (CPU)

`t0_v3.py` and `t0_scalar_v3.py` step the preparation's three worlds from t = 0, once
with version 2 and once with version 3 declared (`results/t0-v3.json`,
`results/t0-scalar-v3-w*.json`; version 2's widths from `results/t0-widths-main.json`).

| Program | Version 2 refuses | Version 3 | States equal to version 2's before that |
| --- | --- | --- | --- |
| Vectorized, 1-step windows | world 3 at [0.085, 0.086] s (also with 10- to 186-step windows) | accepts to 0.6 s | bitwise, 85 steps × 3 worlds |
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

So at the edge this tissue reaches, version 3's 1e3 ulps leave a margin of at least 500× in
ulps. In units of the target, the cap is much larger (the last section).

## Guards on the CPU (13 November)

The guards ran from execution snapshots `source-01` (`7a1f7f6`) to `source-04`
(`9181b67`); guard 2 and the guard 6 tests ran from `source-01`. The results are in `/mnt/workspaces/Cells/field-floor-guards-20261113-01/`
(`summary.json`).

**Guard 1, jaxprs and bindings: pass on 41 worlds.** These are `composite_crossrev`'s base
(12) and qualification (27) sets, which include the 825-node study tissue, and the hold's
own preparation and run definitions (2, with 172 free offsets each). For each world,
`field_floor_guard.py jaxprs` traces the checked step, the right-hand side and the device
row checks under both declarations. It then follows the floor leaf through every nested
jaxpr: calls, while, cond and scan.

- The floor's magnitude reaches exactly three operations per field solve: two
  multiplications (the floor itself) and one comparison (|R| ≤ floor).
- Every output depends on the floor only through that comparison's boolean: the validity,
  and the states through `where(valid, new, old)`.
- The device row checks never read the floor.
- Version 3 adds 42 equations per field solve to version 2's 11,500–51,800 and removes
  none. This is a count by primitive, not a structural identity.
- The bindings are identical except the added leaf, which holds 1e3.
- At the merged head (main's S2, `source-03`), the result is the same on all 41 worlds.

**Guard 2, runs: every part equal, 35 worlds and 2 vectorized cohorts.** Each part runs `composite_guard.py`'s comparison with the
pair (version 2, version 3) of one definition instead of (frozen, composite). The part
outputs keep `composite_guard`'s labels, so "frozen" means version 2 and "composite" means
version 3. Every state, observation column and `max_` diagnostic is compared with
`np.array_equal`; where the part records bit patterns and device row checks, those too.

| Part | Worlds | Result |
| --- | --- | --- |
| W1 trajectories (windowed, 1 ms) | 6 | equal |
| W2 arms (rhs, Jacobian and 4-step map at the stationary branches; 1 s run) | 8 | 48 of 48 points equal; the 1 s runs bitwise |
| G2-Q1 cases | 9 | bitwise, device row checks bitwise |
| Q5: G2-Q1 at 2, 1, 0.5 and 0.25 ms | 8 | bitwise |
| Q6: G2-Q1's vectorized cohorts | 2 cohorts (10 worlds) | equal |
| W37 | 1 | bitwise, device row checks bitwise |
| The 825-node world: the study tissue (the hold's model), closed water, event-free replacement (200 steps) | 3 | bitwise, device row checks bitwise |

The first W2 attempt was OOM-killed at its unit's 5G cap, compiling the right-hand side's
Jacobian under both declarations; it was rerun alone at 8G.

**Guard 6, tests: pass.** `test_field_floor_pump_v3.py` runs the @3 fixtures (three cells,
one or two free offsets): version 3 is bitwise version 2, and a checkpoint round-trips and
resumes bitwise. It is tier 3 (over the 90 s cap). `test_field_floor_held.py` covers a root
at the floor accepted, one above it refused, and the held solve below; it is tier 2 (52 s).
All 9 tests pass.

**Row checks and ledgers cannot see field residuals, so version 3's safety rests on the
state bound.** Anyone who later relies on the checks to catch an inaccurate field solve
should know this: they passed under caps a billion times wider than version 3's (the
positive control below). The field solve's own acceptance test is the only guard of its
accuracy.

**A solve held just under the cap passes every row check and ledger.**
`field_floor_held.py` replaces the field solve on the host path. Each solve finds its root,
then moves the free offsets along a direction until its residual is at 0.95 of version 3's
cap. The cap is located by bisection against the solve's own test, and every held solve is
checked to be refused at 0.9 of the cap. The run's host row checks (`check_values`, every
ledger), device row checks, ledger margins and states are then compared with the normal run.
"Largest" moves only the free component with the largest incident face current, where the
floor binds; "uniform" moves every free offset alike.

| State (20 held steps; the unit test 2) | Direction | Held residual, × target | Checks | Largest state change |
| --- | --- | --- | --- | --- |
| Preparation world 3 at 0.45 s (its CPU edge) | largest | 2,134–2,166 | all pass | 1.0e-13 |
| Preparation world 3 at 0.45 s | uniform | 8.0–10.3 | all pass | 4.5e-16 |
| Run world 1 at 8 s and at 306 s | largest | 1,003–1,005 and 866–867 | all pass | 4.6e-13 |
| Run world 6 at 8 s and at 306 s | largest | 1,001–1,003 and 973–974 | all pass | 1.7e-13 |
| Study tissue after 100 steps (the unit test) | largest | about 190 | all pass | below 1e-12 |

"Checks" means every step accepted, `check_values` passing, no device row check failing,
and the largest ledger ratio unchanged (0.0006–0.0012 of its bound in both runs). State
changes are relative, over 20 steps, against the normal run; about 1e-13 is the rounding
spread of two trajectories. In the uniform direction at the run states, the floor does not
bind: the first refusal along that direction is version 2's own target, so the held
residuals stay at 0.3–1.0 of it, and the checks pass there too (`held-uniform-run-*`). The
first uniform runs held at a point past a refused gap, because acceptance along a direction
need not be one interval; `9181b67` holds at the first boundary seen from the root.

In target units the cap is not one number. On the hold's tissue it lies 8–2,200 times above
`NEWTON_TARGET`, depending on the component the residual sits on; it is about 190 times on
the study tissue.

**Positive control: no row check or ledger can see the field residual.** The same edge state
was held under caps of 1e6, 1e9 and 1e12 ulps instead of 1e3, which is up to 2×10^12 times
the target. Every step was still accepted, every row check and ledger passed, and the
largest ledger ratio stayed at 0.0011–0.0012. The state change cannot be told from
rounding up to 1e9 ulps (1.0e-13 at 1e3, 5e-14 at 1e6, 6.6e-13 at 1e9) and reaches 4e-11 at
1e12, where the free offsets moved by 1.7e-10 V. Scaled linearly from that point, the change
at 1e3 ulps would be about 4e-20. The ledgers check conservation, which the update keeps
whatever the potentials. So the pass at 1e3 ulps rests on that bound, not on the checks. The
field solve's own acceptance test is the only guard of its accuracy.

**The turnover pre-screen's worlds have no free offsets.** These are the five sheet70
discs: 37 cells at s 1.0, 0.6 and 0.3, and 19 cells at s 0.6 and 0.3, on the held-bath
127-cell sheet under `resolved_pump_replacement@1` over @3. Their residual is exactly 0 with
no Newton iteration, in all three programs (`margins-turnover.json`). The pre-screen's "no
refusal" therefore did not depend on the program, for this refusal class. E07-v1's
registered world is the full tissue (172 free offsets), so D147 applies to it.

**A restart under version 3 needed a driver change; it is done.** The hold's definitions
took their field solver from `validation/tissue/resolved_scale_world.py`, which declared
version 2, and `heredity_pilot.py` did not override it. The field solver is now a parameter
of the builder (default still version 2), and `heredity_pilot.py`'s `--field-solver`
(default `auto`, D147) declares version 3 for the full tissue's preparation and run.
`--field-solver 2` rebuilds the hold's three preparation and six run definitions with
source-09's fingerprints, and `auto` differs from them only in the solver
(`/mnt/workspaces/Cells/field-solver-driver-20261113-01/reproduce-hold*.json`). A CPU dry
run of start, prepare, run and resume under `auto` declared version 2 for the held-bath
start graph and version 3 for the rest, and resumed from a version-3 snapshot. A new-code
`run` from a version-2 preparation needs `--field-solver 2`. The restart itself is
prepared, not launched: `heredity-pilot-w1-20261110-01/launch8.sh` and
`restart-v3-note.md`.
