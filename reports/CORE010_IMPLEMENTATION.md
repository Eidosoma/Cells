# CORE-010 development integration

2026-09-11, D061. Implemented as `spatial_extracellular@1` in **0.15.0.dev0**.
All 156 expanded preflight and **3962 regression tests pass** across six source
contexts, with no failures, errors or skips. The [development closeout](core-010-implementation-closeout.json)
passes. **Formal CORE-010 production/release acceptance remains open.**

## What is implemented

The [new family](../docs/SPATIAL_EXTRACELLULAR.md) gives a cell a finite spatial
environment rather than one well-mixed outside. Ion exchange, outside diffusion
potentials and membrane feedback run through the existing CPU/JAX RK4 engine.
Pure-bulk worlds, one cell with near/far volumes, a two-cell chain and an outside
loop are data-defined cases, not separate simulator branches.

Cell, outside-volume, membrane and transport-face axes have independent capacities.
Six state arrays preserve all five reference coordinate fields, splitting the
amount increments across cell and outside owners. Membrane transfer is outward;
face transfer is sender to receiver. The same-stage field module enforces current
continuity without adding bulk capacitance or independently grounding outside
volumes. All inventories and histories evolve explicitly, with no clipping or
conservation projection.

Checkpoints contain edge lists and complete numerical state. The explicitly
identified initial field solver uses a small dense temporary matrix, whose
quadratic storage enters resource guards before capacity allocation. This keeps
a separate interface for later sparse/matrix-free qualification; it does not
establish efficient large-GPU execution.

## Development evidence

The [expanded preflight](core-010-preflight-06.xml) passes **156 tests** in
391.33 seconds with warnings treated as errors:

- All fourteen frozen cases in NumPy/JAX instantaneous equation comparison.
- All fourteen full trajectories at both 0.125 ms and 0.0625 ms, compared against
  the authenticated independent refined Radau record at native and observed times.
  All six production state fields, physical potentials, accounting and exact
  blocked-owner checks pass, including the 8/16/32-volume meshes.
- Short eager/JIT, saved restart, future-control branch, terminal/empty-observation
  continuation, bounded window and independently clocked cohort paths.
- Owner/gauge/orientation/species ordering, padding, strict configuration,
  component charge rather than global charge alone, trial-state positivity,
  whole-cubic bounds, complete layout identity and pre-allocation resource guards.

Earlier preflights are retained, not overwritten. Preflight 01 has 69 passes and
four test API mistakes (`checkpoint` versus `final`); preflight 02 has 87 passes.
Preflight 03 has 49 passes and one test that incorrectly assumed the first coarse
cosine step immediately depletes inventory. The corrected test explicitly creates
a negative half-stage and passes in preflight 05. Preflight 04 has four passing
source-context checks. The final expanded run includes all corrected tests.

The [CLI example check](core-010-cli-example.json) runs the
[one-cell definition](../configs/spatial_extracellular_cell.json) for 0.3 seconds
and resumes from 0.15 seconds in another process. All **73 numerical arrays**—
complete native/observed suffixes and static geometry—are byte-identical.
Independent native/observed reference and material/charge/current/energy checks
pass. This is one development smoke test, not the full fresh-process panel gate.
The [full-window CLI check](core-010-cli-window.json) also passes: 19 windows
reconstruct all 40 native/observed arrays byte-for-byte, and all three complete
checkpoints verify. The example reserves 1,968,256 bytes of array workspace;
that estimate excludes compiler/runtime/OS memory and is not a GPU benchmark.

The [0.14.0 preservation receipt](core-010-preservation.json) authenticates all
48 accepted production files and an archive of 388 source/context files made
before editing. The [post-edit preserved NUM-010 audit](core-010-preserved-num010-audit.json)
verifies 339 payloads, 21 captured sources, all fourteen reference restarts and
the original numerical verdicts, with zero ODE calls and no production import.
Original reference guards are unchanged and intentionally reject the new live
production context; their tests run under preserved 0.14.0.
All [830 accepted CORE-009 payloads](core-010-core009-payload-preservation.json)
also remain byte-identical. This post-edit file check is not a claim that old
checkpoints can load under modified sources.

The [complete regression matrix](core-010-regression-01/verification.json) includes
2212 current-engine tests, 971 preserved 0.10.0 tests, 205 under 0.11.0, 213 under
0.12.0, 256 under 0.13.0 and 105 under 0.14.0. It authenticates 338 implementation,
test and definition files unchanged throughout execution. All 275 Python files
pass Ruff lint and formatting checks. The original 13 prospective NUM-009 v1
complete-session tests remain explicitly unexecuted, not passing coverage; their
v2 replacement and the original stopped-evidence checks still run.

The [development closeout](core-010-implementation-closeout.json) preserves 652
of 668 pre-existing files byte-for-byte, with sixteen planned documentation/API/
version edits and none missing. There are now 51 production modules; the five
modified old modules only cover version, spec/state/control routing and registry.
All 43 other old production modules are unchanged, including physical laws,
the RK4/runner algorithms, scalar/cohort windows and artifact writers.

## Remaining acceptance work

The next gate is to:

1. Freeze the complete production implementation and a bounded acceptance plan.
   Keep the fourteen reference definitions and inherited tolerances unchanged;
   declare full eager/JIT, refinement, checkpoint, branch, window and cohort runs
   and their time/storage caps before launching that panel.
2. Capture complete production artifacts and compare every state/readout with
   independent equations/reference records, including fresh-process replay and
   exact old-family acceptance replay.
3. Audit saved data without ODE execution, test rehashed corrupt state/readouts,
   verify every scalar/cohort checkpoint and provenance/source identity, and
   finish release preservation checks before promoting a stable version.

The current development tests do not substitute for that registered artifact
gate. The numerical ceiling applies to the qualified short panel, not arbitrary
meshes. There is no new pump/channel/junction spatial composition, tissue barrier,
mechanics, organ model, multirate coupling, biological validation, BETSE parity
or GPU qualification in this slice.
