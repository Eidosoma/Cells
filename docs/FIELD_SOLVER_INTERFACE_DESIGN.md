# Field-solver interface (proposed)

**Status.** Proposed, 13 November 2026, with no code. Field-solver code waits for the GH200
numbers. This note records:
- where one hold step's time goes,
- what each step recomputes,
- how sparse the node-space operators are,
- an interface for the three node-space solves,
- how a replacement would be measured and qualified.

**Measured models and harness.** The engine model measured is `resolved_pump_tissue@3`
with `capacitive_reduction_gauged_damped_newton@2`. The measurements use
`scripts/profile_step.py` (measurement only) on frozen snapshots of b1a4750 and ebb9c85.

**Evidence.** The measurements are in
[field-solver-limits-20261113-01](/mnt/workspaces/Cells/field-solver-limits-20261113-01/).
The L4 split comes from
[window-timing-20261112-01](/mnt/workspaces/Cells/window-timing-20261112-01/l4-dispatch-note.md).

## 1. The question and its answer

**Question.** Where does the device time of one hold step go, and which per-step
computations are definition-invariant?

**Hypothesis.** The time is dense float64 node-space linear algebra:
- the IMEX operator's Cholesky every step;
- the capacitor and stage triangular solves;
- the offset LU and products.

**Falsification test.** The hypothesis is wrong if these take less than half the step at
825 nodes on CPU.

**Result: not falsified on CPU.** The GPU is not yet measured (§7).
- **Pieces compiled alone.** The named pieces take 75% of the step in E07's 825-node world
  and 81% in the hold's world 1, or 64% and 68% of step plus checks.
- **The fused step's trace.** Dense Cholesky, triangular solves, LU and dense products take
  49% of the hold world's step and device checks together.
  - That is about 58% of the step alone, if the checks' 16% holds no factorisation or
    triangular solve.
  - It excludes the copies and element-wise passes that serve this work. The bound
    capacitor factor is copied every step (7%), and validity checks run over the dense
    factors.

On CPU the step is dominated by work done on 825 × 825 dense matrices whose density is under
1% (§3).

## 2. Where one step's time goes

### CPU, each piece compiled alone

One core, unbatched, median of 10–20 calls. Per step: one field solve, one operator build and
factorisation, and two stage solves (the ARS(2,2,2) tableau has three stages). Per field solve:
two capacitor solves, one face product, one Jacobian product per Newton iteration, and one
offset LU solve plus one per iteration.

| Piece (count per step) | Sheet, 254 nodes | E07 world, 825 (t = 0) | Hold world 1, 825 (t = 8 s) |
| --- | --- | --- | --- |
| Step | 8.25 ms | 91.3 ms | 98.5 ms |
| Field solve (1) | 3.89 | 30.1 | 41.2 |
| · capacitor solves (2) | 1.41 | 13.1 | 20.4 |
| · face product (1) | none | 3.2 | 3.6 |
| · Jacobian product (per iteration) | none | none (0 iterations) | 1.9 (1) |
| · offset LU solves | none | 1.3 (1) | 2.5 (2) |
| · the rest of the field solve | 2.48 | 12.4 | 12.8 |
| Operator build: face weights and Laplacian (1) | 0.19 | 6.0 | 5.7 |
| Operator factorisation: assembly and Cholesky (1) | 1.95 | 34.6 | 35.5 |
| · Cholesky alone | 1.21 | 20.9 | 21.1 |
| Stage solves (2) | 1.31 | 16.0 | 16.2 |
| Rest of the step (by difference) | 0.91 | 4.7 | −0.2 |
| Device checks (separate) | 2.04 | 15.5 | 19.1 |
| **Named dense pieces, share of the step** | **57%** | **75%** | **81%** |
| Adding the build | 59% | 81% | 87% |
| Named pieces, share of step plus checks | 45% | 64% | 68% |

Reading notes:
- **The pieces sum to the step.** At 825 nodes the rest of the step is near zero, so the
  separately compiled pieces account for the fused step.
- **XLA CPU's triangular solves are slow.** A capacitor solve (two triangular solves at 825
  nodes) takes 6.6–10.2 ms. That is a CPU fact; the L4 split below is the device's.
- **The sheet does dense work on diagonal matrices.** All 127 of its outside nodes are held
  baths. Its free operator and capacitor solve matrix are diagonal, its face Laplacian is
  empty and it has no floating groups.

**The fused step on CPU.** The hold world, one world, step and device checks traced over five
calls: about 98 ms per call is attributed to instructions, against about 124 ms to ready.
Shares are of the attributed time, by each instruction's op_name.

| Class | Share |
| --- | --- |
| Dense Cholesky (with its symmetrisation and copies) | 21.3% |
| Triangular solves | 16.3% |
| LU (the 172 × 172 offset solves; XLA CPU runs them as loops) | 11.3% |
| Dense products | 0.2% |
| Copies | 11.9% |
| · of which the bound capacitor factor's copy | 7.2% |
| Scatters and gathers | 3.0% |
| Element-wise and other | 35.6% |

The dense products are probably fused into multiply-add fusions here. One such fusion is 6.4%.

### L4, six hold worlds at t = 8 s

From the dispatch test, the window step is 53.05 ms:
- **Step:** 48.2 ms, of which the field solve is 22.7 ms and the rest of the step 25.5 ms.
- **Device checks:** 8.8 ms.
- **Not the cost:** loop control is ruled out (at most 1.37×), and so is kernel launch.

The L4's share by operation class is not measured yet (§7).

## 3. Sparsity and fill

The E07 world and the hold world have the same geometry and the same counts: 225 cells, 600
outside nodes, 731 free nodes, 172 floating groups (all free), 1,151 faces and 618 junctions.

Factorisation cost is Σ c_j² (c_j = below-diagonal nonzeros of factor column j), which is
n³/3 for a dense matrix.

| Matrix (825 nodes) | Nonzeros (density) | Factor nonzeros: natural, RCM, minimum degree | Factorisation: dense against minimum degree |
| --- | --- | --- | --- |
| Free IMEX operator C + aL | 4,527 (0.67%) | 13,909, 18,411, 7,537 | 1.87 × 10⁸ against 1.0 × 10⁵ (1,800×) |
| Capacitor matrix | 2,328 (0.34%) | 7,734, 8,663, 3,912 | 1.87 × 10⁸ against 3.2 × 10⁴ |
| Face Laplacian | 2,902 (0.43%) | 15,224, 10,900, 6,289 | not factored alone |
| Offset Jacobian, 172 × 172 | 802 (2.7%) | 6,408, 1,226, 768 | dense LU about 3.4 × 10⁶ against 2.3 × 10³ |

- **Face incidence (172 × 1,151):** 788 nonzeros (0.40%). The dense face product takes
  172 × 1,151 × 172 = 3.4 × 10⁷ multiply-adds; summed over faces it is about 4.6 × 10³.
- **Junction incidence (172 × 618): no nonzeros.** No floating group contains a cell, so the
  Jacobian's junction product, 1.8 × 10⁷ multiply-adds per Newton iteration, adds an exact
  zero.
- **Floating basis (825 × 172):** 731 nonzeros, one per non-fixed node.
- **Ordering.** Reverse Cuthill–McKee does worse than the natural order on the IMEX operator,
  so minimum degree (or nested dissection) is the ordering to bind.

**Conditioning and drift.** The free IMEX operator has condition number 2.7 × 10³, or 223
after Jacobi scaling, and it does not change from t = 8 s to t = 1,206 s.

Against the t = 8 s operator, the largest |λ − 1| of M₈⁻¹ M_t is:
- 7 × 10⁻⁸ at t = 16 s;
- at most 4.7 × 10⁻⁵ from t = 18 s to 1,206.2 s, with relative Frobenius changes up to
  1.5 × 10⁻⁵.

Over one 200-step window (t = 1,206.0 to 1,206.2 s) it is 3.3 × 10⁻¹⁰.

So one factor serves the whole 1,200-s hold as a preconditioner with a contraction of about
5 × 10⁻⁵ per refinement iteration. CG with Jacobi scaling instead needs about 180 iterations per
10¹⁰ of residual reduction.

## 4. What every step recomputes

Sources: `models/surface_pump_v3.imex_step`, `readouts`, `numerics/surface_field.solve`
and `numerics/surface_imex`. The cost column gives CPU times for the hold world, per step.

**Definition-invariant (could be bound once):**

| Computation | Per step | Note |
| --- | --- | --- |
| Capacitor factor | 0 | Bound once since `@2` |
| Copy of the bound factor before the triangular solves | ~7 ms (CPU trace) | Done every step |
| C @ boundary in the capacitor solve | 2 dense 825² products | One of them is C @ 0 (the potential-rate solve) |
| Junction product in the offset Jacobian | 1.9 ms per iteration | Exact zero in these worlds (§3) |
| \|face incidence\| and \|junction incidence\| | once | Version 3's floor |
| Clamp, free and required masks, diag(~free) | several | Cheap |
| The four dense zero matrices the face Laplacian is scattered into | 4 | Their shape and pattern are fixed by topology |

**Held-control-invariant:** boundary voltages and held values (`p.boundary_V` is in the layout).

**State-dependent but slowly varying:**

| Computation | Per step | Note |
| --- | --- | --- |
| Face weights and conductances | 3 | Extracellular concentrations |
| Face Laplacian values | 5.7 ms | Dense scatters |
| C + aL, its scaling and its dense Cholesky | 35.5 ms | Moves by under 5 × 10⁻⁵ over the hold |
| The offset face product and Jacobian | 3.6 + 1.9 ms | Pattern definition-invariant |
| Offset LU | 2.5 ms | |

**State-dependent:**

| Computation | Per step | Note |
| --- | --- | --- |
| Stage triangular solves | 2 × 8.1 ms | Stage charges |
| Capacitor solves | 2 × 10.2 ms | Charges and ionic rates |
| Transport | 4 in the field solve, 2 explicit | Currents at stage potentials |
| Channel and pump kinetics, gates, ledgers | | |
| The device checks | 19.1 ms | |

## 5. Scope ceiling

**No single piece reaches 2× on the L4.** Removing a whole piece of the six-world window step
(53.05 ms) gives at most:
- the field solve: 1.75×;
- the rest of the step: 1.93×;
- the device checks: 1.20×.

**The dense algebra spans both halves.** It is the operator's factorisation and stage solves
in the rest of the step, and the capacitor solves, offset LU and products in the field solve.
- **CPU ceiling.** Removing it entirely bounds the step's gain at 1 / (1 − 0.81) ≈ 5× on CPU
  for the hold world, or 3.1× counting the device checks.
- **L4 ceiling.** Its L4 share, and so its L4 ceiling, needs the kernel profile (§7).

**At E07's batch size** the L4 step is per-world work, about 2.2 ms per added world. Cutting
per-world dense work would therefore carry into E07's cost, if the profile shows it dominates
there.

## 6. The interface

**One node-space solver per field-solver ID.** It covers the three solves that share the node
graph, the capacitor matrix and the floating groups:

| Solve | System | Used |
| --- | --- | --- |
| Capacitor | C φ = q on the solved rows, boundary values held | Twice per field solve |
| IMEX operator | (C + aL(w)) φ = q on the free nodes | Prepared once per step, solved once per stage after the first |
| Offset | F(g) + B diag(s) Bᵀ on the floating offsets | Prepared and solved per Newton iteration, and for the initial offsets |

**Three phases:**
- **bind** runs once per definition, on the host. It produces orderings, symbolic factors,
  index maps for assembling values straight into the factor's pattern, and the invariant
  products of §4. Its arrays become layout leaves, so a checkpoint carries them and
  `validate_checkpoint` refuses a mismatch, as for version 3.
- **prepare** runs per step or per iteration, on the device, from the state-dependent values.
  Depending on the method it does a numeric factorisation, builds a preconditioner, or nothing
  (matrix-free).
- **solve** returns the solution and its residual.

**Acceptance is the engine's existing checks, unchanged:**
- a stage solve's |residual| ≤ `CHARGE_ATOL_C` + `CHARGE_RTOL` × scale;
- a capacitor solve's solved rows within their bound;
- the offsets under `NEWTON_TARGET`, or version 3's floor.

An inexact method is acceptable exactly when these pass. A failed solve is a refusal; there is
no silent fallback to another method.

**The choice is static.** It is made by the solver ID in the definition's execution block, never
by data inside a step: under vmap a per-world `cond` runs both branches. Every world of a batch
binds the same structure (same topology), or the batch is refused.

**A new method is a new solver ID (D147).** Existing IDs and their definitions do not change;
each ID declares its own node bound (§6.4) and whether it reproduces another ID bitwise.

### 6.1 Sparse direct with a fill-reducing ordering

**Work.** Bind a minimum-degree (or nested-dissection) ordering and the symbolic factor of
C + aL's pattern, which topology fixes: 7,537 factor nonzeros at 825 nodes. Then, per step:

| Work | Sparse | Dense |
| --- | --- | --- |
| Numeric factorisation | 10⁵ | 1.9 × 10⁸ |
| Each triangular solve pair | about 1.5 × 10⁴ | 1.4 × 10⁶ |
| Offset products, as sums over faces | 4.6 × 10³ | 3.4 × 10⁷ + 1.8 × 10⁷ |

The same applies to the capacitor factor and the offset system.

**Expected gain.**
- **CPU:** the named pieces are 81% of the hold step, so the gain approaches 5× if the
  replacement is close to free.
- **GPU:** unknown. A sparse factorisation runs as dependent steps along the elimination tree.
  At six worlds it may not beat the dense batched kernels; at 256 worlds its work is tiny. The
  kernel profile decides.

**Implementation.** JAX has no sparse Cholesky. The options are a static-pattern factorisation
written with gathers and segment sums (engine numerics to write and qualify) or a library
custom call (a dependency decision).

**Numerics.** Not bitwise to the dense solver, because the elimination order differs. It is
backward stable for these SPD systems in any order, and tolerance-based through the acceptance
checks.

**Qualification:**
- a new solver ID;
- D147-style guards: outside the solver the jaxpr is unchanged, and the state depends on the
  solver only through its solutions;
- agreement with the dense ID within the ledger tolerances on W1, W2, G2-Q1, the 825-node
  world and the hold's saved states;
- identical refusal classes on the guard worlds;
- the sheets' diagonal operators as an exact case;
- the tier gate.

### 6.2 Matrix-free preconditioned CG

**Work.** Each iteration is one sparse product with C + aL (4,527 nonzeros) plus vector
updates. There is no factorisation and no n² storage.

**Iterations.**
- With Jacobi preconditioning: condition 223, about 180 iterations per 10¹⁰ of residual
  reduction.
- Preconditioned by a reused factor (§6.3): two or three.

**Expected gain.**
- **CPU:** large. 180 sparse iterations are about 1.6 × 10⁶ operations per solve, against the
  dense factorisation's 1.9 × 10⁸.
- **GPU:** 180 dependent iterations of small kernels are latency-bound, and likely slower than
  the dense path at small batch sizes. Preconditioned by a reused factor, the iteration count is
  small.

**Numerics.** Tolerance-based. The iteration count depends on the data: a while loop, or a fixed
count whose residual the acceptance check verifies. Stopping is on a residual tied to the
acceptance check's tolerance, and non-convergence is a refusal.

**Qualification.** As §6.1, plus the stopping rule's margin against the acceptance check.

### 6.3 Factorisation reuse and rank updates (the composite note's R3 options (b) and (c))

**The IMEX operator: reuse, not rank updates.** All 1,151 face weights move every step, so a
rank update does not fit. Reuse does: the operator moves by under 5 × 10⁻⁵ over the whole hold.
- **Refresh.** Refresh the factor at declared epochs, or when the refinement's measured
  contraction exceeds a declared bound.
- **Solve.** Correct each solve with one or two refinement steps, or CG preconditioned by the
  factor.

**The capacitor matrix** is constant in `resolved_pump_tissue@3`. Under a capacitance provider
(the composite's R3) there are two options:
- **(b) refactor at declared insertion epochs.** Booking is exact at each epoch and the result is
  bitwise when idle.
- **(c) a rank-k update for the k changed patches,** about k n² operations. It is bitwise when
  idle only if skipped statically or shown exact at ΔC = 0.

**Expected gain.**
- **CPU:** this removes the per-step factorisation, 35.5 of 98.5 ms (36%), but adds refinement
  solves. Alone it is at most 1.6×; it combines with §6.1's sparse solves.
- **GPU:** follows the factorisation's share in the profile.

**Numerics.** Epoch refactoring is exact. Refinement is tolerance-based.

**Qualification.** As §6.2, plus the refresh policy declared in the definition.

### 6.4 The 2,048-node limit

`NODE_BOUNDS` refuses a definition above 256 field nodes for `@1`, and above 2,048
(`FACTORED_MAX_NODES`) for `@2` and `@3`.

**The dense layout's cost at 2,048 nodes:**
- **Memory.** Three n² matrices per world (capacitor matrix, solve matrix and factor): about
  100 MB per world, before the step's own dense temporaries (the operator, its scaled copy, its
  factor and the scatter targets).
- **Work.** The step factors an n × n operator: n³/3 ≈ 2.9 × 10⁹ operations per world-step.

**Under the interface each ID declares its own bound.**
- **Dense IDs** keep 2,048.
- **A sparse ID's bound** follows its factor's nonzeros, about 9n here (O(n log n) for planar
  graphs under nested dissection), and its index maps.

Larger tissues are then limited by transport and memory rather than by n³.

### 6.5 Changes that need no new method

Some definition-invariant work in §4 could be bound once:
- the factor's per-step copy;
- C @ boundary;
- the junction product of an exact zero;
- the floor's absolute incidences.

Each must still be shown bitwise (a guard like D147's guard 1) before it can land without a
new ID. Adding an exact zero or skipping a copy is likely bitwise. Moving a product from the
device to the host is not.

## 7. Measurements before any field-solver code

**Kernel profile at the next L4 gap.** The plan is
[kernel_profile_plan.sh](/mnt/workspaces/Cells/field-solver-limits-20261113-01/kernel_profile_plan.sh):
`profile_step.py trace` at 6 and 256 worlds of E07's world, then 6 of the hold world, then the
hold world's pieces on the device. It takes about 10–15 min, under 20.
- **What it measures.** For each run: time to ready and the device time per operation class
  (dense Cholesky, triangular solves, LU, dense products, scatters, gathers, copies, the rest).
- **On GH200.** It reruns unchanged there, with PY and the input paths set.
- **Falsification on the device.** The hypothesis holds on a device if the four dense classes
  take at least half the attributed device time.

**Decision after GH200.**
- **If the dense classes dominate at E07's batch size,** prototype the sparse IMEX operator
  (§6.1) with reuse (§6.3) first, as a new solver ID, and measure it on CPU, the L4 and GH200.
- **If they do not,** this interface waits and the profile's leading class is the next
  question.
