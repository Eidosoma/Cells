# REF-003e1: next response refinement, design only

2026-09-13, D082. **A proposed next experiment, not an executable registration
or launch.** First inspect the detached [failure audit](BETSE_HELD_RESPONSE_AUDIT.md)
and its complete ledger. Preserve D081's rejected 25 µs packet and its original
criteria regardless of later outcomes.

## What the saved data can already tell us

D081 completed all trajectories. Its original report has zero failed internal
law/accounting checks, passing fixed-input Cells subdivisions and eager/JIT
agreement, but 150 failed cross-engine shared-bath amount checks. The largest
baseline amount discrepancy is about 2.364e-7 fmol; the pulse maximum is about
1.427e-7 fmol. Small per-cell errors can accumulate into a failing shared bath,
even when voltage traces and local transfers satisfy their own tolerances.

Existing D077 constant-input native captures at 25/12.5/6.25 µs can be compared
with D081's finest baseline Cells result without rerunning either model. New
focused checks find roughly halving amount error, with the finest baseline
meeting the unchanged criteria. The complete offline audit will preserve those
diagnostic values and hashes. This is evidence supporting a native timestep
explanation **for the constant-input baseline only**, not pulse convergence.

## Keep the two numerical scales separate

| Change | What is held fixed | What it can establish |
| --- | --- | --- |
| Refine Cells integration inside a fixed input hold | Same prescribed input table | Cells solver sensitivity for that input |
| Refine native integration with constant input | Unchanging permeability | Native baseline timestep sensitivity |
| Refine native timestep for the scheduled pulse | Same analytic pulse, newly sampled at each step | Joint native-integration and input-sampling sensitivity |
| Compare sufficiently refined Cells across input holds | Same physics, separate fixed-h solver checks | Sensitivity to representing the pulse as held samples |

In the pinned native SIM loop, event dispatch and pulse resampling occur at
each integration step. Reducing that step changes the held input as well as
the integrator. Keeping the analytic pulse parameters corresponding does **not**
make the finer native run a fixed-input solver refinement.

An isolated native solver test under the original 25 µs pulse table would need
a genuine mechanism to retain that table across smaller native updates. Such
a native mechanism is not currently established by our adapter. Do not patch
the old worker, inject an unqualified callback or call the resampled pulse
equivalent. Investigate source-supported options separately if this isolation
becomes necessary; explicitly version and qualify any adapter extension.

## Recommended next bounded candidate

After user review of the audit, prepare a separately versioned extension using
the D079 compiler's existing 25/12.5/6.25 µs hold definitions:

1. Extend and preflight actual native clock/target/control application for the
   two finer holds before running transport. D080's fresh actual nonzero
   preflight and D081's checker are currently fixed at 25 µs; neither silently
   authorizes or accepts new step counts.
2. Retain all four conditions: baseline, zero amplitude, static block and
   suppression/recovery, with exact observed/unobserved native partners.
   Use matched constants, the same neutral seven-cell finite bath and 1 ms.
3. For each input hold, compare the same held input between engines and retain
   genuinely distinct Cells subdivisions 1/2/4 on eager and compiled JAX.
   Use common elapsed-time state/ledger observations and correct fresh-rate
   sides. Never compare stored native endpoint current as a fresh RHS.
4. First assess Cells solver refinement at each fixed hold. Then report native
   cross-h pulse changes as **combined solver-and-forcing refinement**, and
   compare fine Cells across holds for the separate forcing sensitivity.
5. Preserve all original numerical limits and every coarse failure. Define
   prospective convergence/finest-level gates and their scientific scope before
   capture. A single passing fine result is not by itself convergence evidence.

Retain the original 25 µs capture as an explicit overlap anchor, not an erased
attempt. A later implementation must decide prospectively which overlaps need
fresh execution and which authenticated saved records can be reused. Do not
blindly multiply the old panel or count reused files as new native evidence.

The D081 measurement is **19.821 s native, 687.130 s Cells and 6.774 s
comparison**, not a prediction for the expanded workload. Before launch, budget
the exact rows and accepted step counts, eager/compiled costs, full recording,
file limits and audit resources. Keep expensive captures and follow-up audits
separate, detached and user-polled; no automatic ladder expansion or retry.

## Implications for our simulator architecture

Keep model state, prescribed input sampling, solver steps, observation sides
and conserved interface transfers as separate contracts. This matters for later
multirate tissue/organ coupling: refining a local solver must not silently change
the communication/input policy. Conservation must be checked both locally and
over shared reservoirs and interfaces.

The optional BETSE adapter continues to own native clocks, phase details and
source-specific conversions. Cells production keeps ordinary numeric control
arrays and pure CPU/JAX model kernels, with no BETSE or Python event callback
inside a compiled update. This preserves a path to future GPU batches; it is
not a measured GPU performance or memory claim. No production change is justified
by the current reporting defect or coarse native discrepancy alone.
