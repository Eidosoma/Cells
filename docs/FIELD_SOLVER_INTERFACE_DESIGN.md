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

**Result on CPU: falsified as stated, by a narrow margin; it holds once the dense matrices'
own handling is counted.** The GPU is not yet measured (§7). The authoritative measurement is
the trace of the fused step (the hold world, step alone, each instruction's own time):
- **Narrow form, as stated: falsified.** The four kernel classes (dense Cholesky, triangular
  solves, LU, dense products) take 45% of the step's attributed instruction time, under half.
  That is 36.0 of 80.1 ms per call, or 33% of the 110 ms to ready, the rest being executor
  overhead.
- **Broad form: holds.** Counting also the element-wise passes and copies on 825 × 825
  arrays raises this to 70% of attributed time (51% of time to ready). Those passes exist
  only because the matrices are dense: the operator's assembly and scaling, the copies of
  factors, and the validity checks over them.
- **Upper bound: the pieces compiled alone.** They give 75% (E07's world) and 81% (the hold's
  world 1) of the step for the named pieces, and 79% batched over six worlds. Each such piece
  carries its own copies and dense matrix-vector products, which the fused step partly shares.

**So on CPU the step is mostly work on dense node-space matrices, whose density is under 1%
(§3).** The factorisation and solve kernels alone are just under half of it.

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
- **The pieces overcount.** At 825 nodes the rest of the step comes out near zero, which leaves
  no room for transport, kinetics and gates that the fused trace shows. Each piece compiled
  alone carries its own copies and dense matrix-vector products, which the fused step partly
  shares. Read the named shares as upper bounds; the fused trace below is the measurement.
- **XLA CPU's triangular solves are slow.** A capacitor solve (two triangular solves at 825
  nodes) takes 6.6–10.2 ms. That is a CPU fact; the L4 split below is the device's.
- **The sheet does dense work on diagonal matrices.** All 127 of its outside nodes are held
  baths. Its free operator and capacitor solve matrix are diagonal, its face Laplacian is
  empty and it has no floating groups.

**The fused step on CPU.** The hold world, one world, the step alone, traced over five calls.
Each instruction counts its own time, with nested events (a while loop's body) subtracted.
About 80 ms per call is attributed to instructions, against 110 ms to ready. Classes follow
each instruction's op_name; "on n × n arrays" counts instructions whose output holds at
least 825² elements.

| Class | ms per call | Share of attributed | Of it on n × n arrays |
| --- | --- | --- | --- |
| Dense Cholesky (with its symmetrisation) | 19.9 | 24.8% | 19.9 |
| Triangular solves | 11.9 | 14.8% | 0 (vector outputs) |
| LU (the 172 × 172 offset solves) | 4.1 | 5.1% | 0 |
| Dense products | 0.2 | 0.2% | 0 |
| **The four kernel classes** | **36.0** | **44.9%** | |
| Copies | 10.9 | 13.6% | 8.1 |
| Element-wise and other | 30.8 | 38.4% | 12.2 |
| Scatters, gathers, loops | 2.5 | 3.1% | 0.1 |
| **Dense node-space work** (the four classes and the n × n passes) | **56.4** | **70.4%** | |

**With the device checks** the program takes 123 ms to ready. The four classes are then 45.5%
and dense node-space work 71.0%; the fused checks add about 8 ms of attributed time, against
19 ms compiled alone.

**The first trace overcounted.** An earlier version of the trace summed nested events, so a
while loop's event and its body's instructions were both counted. It reported 49% for the four
classes with checks (LU 11.3% instead of 4.7%). Both traces are kept.

The dense face and Jacobian products appear as fused multiply-adds rather than as dots, so
they sit in "element-wise".

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

So in the hold one factor would serve the whole 1,200 s as a preconditioner, with a contraction
of about 5 × 10⁻⁵ per refinement iteration.

This is the hold's quasi-steady state only. The movement jumped from 7 × 10⁻⁸ to 4.7 × 10⁻⁵
between 16 and 18 s, and E07's cue phases are unmeasured.

For Jacobi-scaled CG, the condition number bounds the count at about 180 iterations per 10¹⁰ of
residual reduction (½√κ ln(2/ε)). That is a bound, not a measured count.

## 4. What every step recomputes

Sources: `models/surface_pump_v3.imex_step`, `readouts`, `numerics/surface_field.solve`
and `numerics/surface_imex`. The cost column gives CPU times for the hold world, per step.

These costs were seen in single-step programs (the pieces and the one-step trace). Inside a
window's scan the compiler may already hoist some definition-invariant work out of the loop.
That is unverified for the window program.

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
- **CPU ceiling.** Making all dense node-space work free would bound the hold step's gain on
  CPU between about 2× and 3.4×:
  - about 2×: it is 51% of the fused step's time to ready;
  - 3.4×: it is 70% of the step's attributed instruction time, if the executor overhead
    shrank with it.

  The pieces compiled alone (81%, so 5×) overstate it.
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
- **CPU:** dense node-space work is 51–70% of the fused hold step (§1). With a replacement
  close to free, the gain is about 2× to 3.4× on CPU.
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
- With Jacobi preconditioning: condition 223, at most about 180 iterations per 10¹⁰ of residual
  reduction (a bound from the condition number, not a measurement).
- Preconditioned by a reused factor (§6.3): two or three in the hold's quasi-steady state.

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
rank update does not fit. Reuse does: in the hold the operator moves by under 5 × 10⁻⁵ over
1,200 s.
- **Refresh.** Refresh the factor at declared epochs, or between windows on the host.
  Within a window the refresh cannot depend on a per-world measurement: under vmap a
  per-world predicate turns the cond into a select, both branches run, and the
  factorisation would still run every step (the composite note's R3 point).
- **Solve.** Correct each solve with one or two refinement steps, or CG preconditioned by the
  factor.
- **Its contraction is a check, not a trigger.** The contraction each refinement measures is
  checked like any residual; exceeding its bound is a refusal.

**The capacitor matrix** is constant in `resolved_pump_tissue@3`. Under a capacitance provider
(the composite's R3) there are two options:
- **(b) refactor at declared insertion epochs.** Booking is exact at each epoch and the result is
  bitwise when idle.
- **(c) a rank-k update for the k changed patches,** about k n² operations. It is bitwise when
  idle only if skipped statically or shown exact at ΔC = 0.

**Expected gain.**
- **CPU:** this removes the per-step factorisation but adds refinement solves. In the fused
  step the Cholesky and the operator's n × n assembly are about 32 of 80 ms of attributed
  time. Alone, reuse is therefore at most about 1.4–1.6×; it combines with §6.1's sparse
  solves.
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

### 6.5 Definition-invariant waste: candidates (parked)

These change `@3`'s step program without changing the method. They are parked by the lead
(13 November): each needs its own round under D148 (an in-place fix to shared qualified code)
with a crossrev renewal, sequenced after the volume-ledger guards land. Costs are CPU, hold
world, from single-step programs. Inside a window's scan the compiler may already hoist some
of them (§4).

| Candidate | Cost seen | Change | Expected bitwise status |
| --- | --- | --- | --- |
| C @ 0 in the potential-rate capacitor solve | one dense 825² product per field solve | Skip the product when the boundary is statically zero | Bitwise: C @ 0 is exactly 0, and q − 0 = q, signed zeros included |
| Junction product of the offset Jacobian, an exact zero when no floating group holds a cell | 1.9 ms per Newton iteration | Skip it when the bound junction incidence is all zero (decided at bind time) | Bitwise in value. matrix + 0 = matrix, but an entry of −0.0 becomes +0.0, so the guard must compare the signs of zero too |
| \|face incidence\| and \|junction incidence\| in version 3's floor | small | Bind them once | Bitwise: abs is exact |
| The bound capacitor factor's per-step copy | about 7 ms per step | Bind the factor in the layout the triangular solve takes | Likely bitwise if the solve's call and order are unchanged and only the stored layout moves; not if it becomes a transposed solve |
| C @ boundary in the base capacitor solve (boundary voltages are layout leaves) | one dense 825² product per field solve | Bind once | Not bitwise in general: a host or separately compiled product may sum in another order. It would need tolerance equality and a new ID, or a guard showing the bound value equals the in-step one |
| Masks, clamp/free, diag(~free) | cheap | Bind once | Bitwise (exact operations) |
| The four dense zero matrices the face Laplacian is scattered into | part of the 5.7 ms build | Scatter straight into one bound pattern | Not bitwise: the scatters' summation order changes (that belongs to §6.1, not here) |

A guard like D147's guard 1 shows each bitwise claim on the guarded worlds before it lands.

## 7. Measurements before any field-solver code

**Kernel profile at the next L4 gap.** The plan is
[kernel_profile_plan.sh](/mnt/workspaces/Cells/field-solver-limits-20261113-01/kernel_profile_plan.sh),
about 15 min, under 20:
- `profile_step.py trace` at 6 and 256 worlds of E07's world, then at 6 of the hold world;
- the hold world's pieces on the device;
- the pieces vmapped over 6 hold worlds and over 256 of E07's.

**What it measures.** For each trace: time to ready and each instruction's own device time, by
operation class and on n × n arrays. For the batched pieces: each piece's batched time.

**It is untested on a GPU.** Whether this jaxlib's profiler records device kernels with HLO
names is open (venv-gpu holds libcupti). The batched pieces are the fallback that needs no
profiler.

**Inputs.**
- From its start, E07's world takes no Newton iteration, so its traces hold no in-loop
  Jacobian or LU; the hold world's trace does.
- E07's definition declares version 2, although its free offsets would make a new run declare
  version 3 under D147. The plan's FIELD_SOLVER variable sets the version.

**On GH200.** It reruns unchanged there, with PY and the input paths set.

**Falsification on the device**, as on the CPU:
- the narrow form needs the four kernel classes at half or more of the attributed device time;
- the broad form adds the n × n passes.

**Result on the L4 (14 November): the narrow form holds.** The run: E07's world as version 3,
the hold's as declared (version 2), step and checks.
- **The device is busy.** Device time is 92–99% of each call's time to ready.
- **Attribution is by kernel name.** On this jaxlib the device kernels carry their command
  buffer as hlo_op, not the instruction, so they are classed by name. cuSOLVER and cuBLAS
  kernels name their operation
  ([read_gpu_trace.py](/mnt/workspaces/Cells/field-solver-limits-20261113-01/read_gpu_trace.py)).

| Run | Ready | Four kernel classes | Triangular solves | Cholesky | Dense products | LU | Fusions | Copies |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| E07, 6 worlds | 52.1 ms | 79% | 61% | 11% | 5% | 2% | 17% | 4% |
| Hold, 6 worlds | 57.5 ms | 78% | 58% | 11% | 5% | 4% | 18% | 4% |
| E07, 256 worlds | 538 ms (2.10 ms per world-step) | 53% | 11% | 25% | 17% | 1% | 29% | 18% |

- **At six worlds** the step is mostly cuBLAS's batched triangular solve (`batch_trsm_left_kernel`)
  applied to single vectors: about 30 ms of a 52–58 ms step.
- **At 256 worlds** the Cholesky and the dense products lead.
- **The broad form cannot be read from kernel names.** It would add n × n fusions and copies; the
  pieces compiled alone bound it at 65% (hold, 6 worlds) to 86% (E07, 256 worlds) of the step.

**The conduction workload belongs in the same plan (added 14 November, from an external
architecture review the advisor confirmed).** Everything above was measured in slow,
quasi-steady hold states. These do not establish conditioning or safe reuse intervals during
an active wave. The L4 and GH200 measurements therefore add the following. The Track E
conduction probe's numbers fill them when they land.
- **Excitation onset, propagation and recovery** as measured workloads, alongside the hold:
  - the operator's conditioning through each phase, and its drift between steps and between
    windows (the drift part, at states saved through a wave);
  - the Newton iterations and backtracking trials per step;
  - the per-class device time. Reuse (§6.3) and PCG (§6.2) are judged on these phases, not
    only on the hold's 5 × 10⁻⁵ over 1,200 s.
- **Complete workloads compared at equal numerical accuracy,** never piece against piece, for
  each solver candidate against the dense ID. The candidate must meet the same acceptance
  checks and the same ledger tolerances, and the plan records for it:
  - time per assay and ensemble throughput (world-steps per second);
  - compile cost;
  - host and device memory;
  - the solve residuals against their acceptance bounds;
  - rejection rates (refused steps and refined or repeated solves).
- **Static-world capacity apart from dynamic-field capacity.**
  - A world whose topology, capacitances and masks are fixed can bind every factor once.
  - A world with dynamic capacitance or activity masks refactorises: the composite's field
    refresh runs every view and is capped at `FIELD_INPUT_NODE_CAP` = 64 field nodes.
  - Node bounds and throughput are stated separately for the two; a static-world figure
    does not carry to a dynamic one.
- **Qualified invalidation or reuse rules at the events that change geometry or activity,
  before any lifecycle worlds are scaled.** Insertion, replacement, division and mask
  closures each change the operator or its pattern. A bound factor, ordering or symbolic
  factorisation must be invalidated, refreshed or shown still valid by a declared rule at each
  such event. That rule is qualified (exact at the event, as R3's option (b) requires, or within
  the acceptance checks) before lifecycle worlds grow past the current caps.

**Decision after GH200.**
- **If dense node-space work dominates at E07's batch size,** prototype the sparse IMEX
  operator (§6.1) with reuse (§6.3) first, as a new solver ID, and measure it on CPU, the L4
  and GH200.
- **If it does not,** this interface waits and the profile's leading class is the next
  question.
