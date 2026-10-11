# BETSE as the realism baseline

Historical snapshot retained before the 2026-10-11 documentation refresh.
Status statements below describe their original stages. Read the
[maintained document](../BETSE_REALISM_AND_NEXT_STEPS.md) and [current progress](../../PROGRESS.md)
for present scope and run status.

2026-09-16, D107; updated 2026-09-17 through D130. User requirement: Cells should ultimately be at least as
biologically and physically detailed as BETSE, while retaining modular,
computationally multiscale CPU/GPU execution. **This is a target, not today's
capability claim.** Simplified models remain useful selectable resolutions;
they must not become the ceiling on the detailed model.

## What counts as reaching the target

Use the pinned BETSE 1.5.0 source as a reproducible initial comparator, alongside
experimental evidence. It is not a permanent ceiling: review subsequent source
and biological evidence explicitly. Track the full [B01–B17 inventory](../BETSE_CAPABILITY_ROADMAP.md#capability-inventory-and-engineering-route).
Deferring a feature does not remove it from that inventory.

For each mechanism distinguish specification, independent numerical reference,
production implementation, source correspondence, experimental evaluation,
GPU qualification, and cross-resolution qualification. A passing isolated
equation or short trajectory does not complete the other columns. More equations
alone do not establish greater biological accuracy.

The detailed path must support, in stages:

- Ion inventories, membrane charge and passive transport with realistic units,
  selective channels, substrate-dependent pumps/exchangers and energy accounting.
- Selective and voltage-dependent junctional communication, heterogeneous cells,
  regional interventions and tissue geometry.
- Finite and spatial extracellular spaces, tissue barriers, membrane surface
  resolution and electric-field coupling.
- Biochemical feedback, intracellular compartments and calcium handling; then
  water/volume/flow, mechanics and spatial redistribution where required.
- Reproducible preparation, parameter provenance, experimental observables and
  uncertainty, not merely agreement with another simulator.

Do not reproduce an upstream implementation quirk as a universal biological law.
Separate a source-compatibility adapter from a named physical mechanism, document
the difference, and test its consequences. No silent change to accepted models.

## Work now and the next gates

| Track | Current position | Next deliverable | What remains before claiming parity |
| --- | --- | --- | --- |
| Passive transport and one Kv1.5 channel | Narrow source comparisons independently closed, including timed suppression/release | Preserve [D106 closeout](../../reports/REF004D_TIMED_RELEASE_CLOSEOUT.md) and use its controls | Broader regimes and other channel/ligand families; experimental responses |
| Na/K pump–leak | Source contact, bounded v2 acceptance, native lifecycle, [refined 1 ms pilot](../../reports/REF005C_PUMP_PILOT_CLOSEOUT.md) and live/window recording independently closed; original rejection preserved | [18-solve 10 ms reference study](../../reports/REF005E_REFERENCE_SCOPE_LAUNCH.md) launched detached; review its results before native timestep/resource probes and a full matched campaign | Longer relaxation, timed recovery, other transporters and experiments; broader release matrix separately |
| Gap junctions | Conservative graph mechanism exists; specific BETSE gate semantics differ | [Held-open transport and lifecycle preflight](../BETSE_GAP_JUNCTION_PLAN.md) on a supported small cluster | Dynamic gating, recovery, heterogeneity, coupled graph experiments |
| Biological benchmark | [Xenopus candidate](../BETSE_BIOLOGICAL_BENCHMARK_PLAN.md) extracted with explicit provenance gaps | Verify original measurements, input conditions and uncertainty; preregister evaluation | Long enough pump–leak equilibrium plus an independent perturbation test; no fitting to held-out targets |
| Spatial and remaining multiphysics | Passive spatial development accepted; B06–B14 still incomplete | Stage-consistent pump/channel/junction composition, then barriers and resolved membranes | Compartments, chemistry, water and mechanics remain explicit engineering projects |
| GPU and multiscale organs | Architecture requirement, not measured readiness | Preserve pure array laws and ownership now; measure a representative tissue later | Sparse/device field solver, workload/memory benchmarks, GPU accuracy, conservative coarse/fine coupling, organ validation |

Source contact and the fixed 10 ms numerical candidate are closed, **not the
final pump feature**. The new named process uses numeric array interfaces;
its reviewed qualification now permits versioned configuration and conservative
model integration. The working 0.16.0.dev0 family's bounded 422-test
lifecycle/trajectory gate and independent saved-data review now pass; full
release promotion remains separate. Native driver preparation is now independently
closed: scaling, masks, single transfers and physical clocks are reconstructed.
The original matched 1 ms attempt remains rejected after its independent
failure diagnosis: its finest native step was insufficient for the unchanged
energy budgets. D119's separately authorized finer ladder now reports zero
failures in 616,806 producer comparisons; the main energy defect falls below
the original limit. D120's independent review now passes: 203,274 acceptance
comparisons and 10,610,676 additional law/conservation/link checks. D121 closes
only that bounded 1 ms scope. The D122 design qualifies lossless recording before
extending duration; 35 planning checks pass. D123 implements the
[lossless native record layer](../../validation/betse/native_recording/README.md):
132 checks pass, and all 36 saved rows now round-trip exactly in 215.987 s,
using 83.6× less storage overall. D124's
[separate decoder/review](../../validation/betse/native_recording_audit/README.md)
passes its full review: **54,685,116 exact comparisons / zero failures**.
D125 [closes offline recording](../../reports/REF005D_CODEC_CLOSEOUT.md) and implements
the [same-1 ms live/window gate](../../reports/REF005D_LIVE_HANDOFF.md), using a
non-accumulating observer and Cells' existing public APIs. Native histories
remain unchanged, so whole-BETSE memory is not bounded. No longer simulation
is launched; live independent review remains separate. D126
[closes the 79-test preflight and proceeds to the full same-1 ms matrix](../../reports/REF005D_LIVE_QUALIFICATION_LAUNCH.md),
with unchanged source/physics/tolerances and detached, user-polled execution.
D127 [preserves the resulting logging-gate failure and continues with Cells only](../../reports/REF005D_LIVE_CONTINUATION_LAUNCH.md):
the 36 native comparisons and eighteen pairs passed, but a script-name prefix
was classified incorrectly. Fifty-four new regression checks pass, and all
saved native payloads authenticate for reuse. No native recomputation, physics
change or relaxed warnings/tolerances; full acceptance and independent review
remain pending. D128 [separates baseline/window output ownership](../../reports/REF005D_OUTPUT_LAYOUT_LAUNCH.md)
after a second harness failure: the existing no-overwrite guard caught a shared
`full/` destination. Fifty-one fast filesystem/control checks pass; the detached
job must pass a real combined baseline/recording/restart case through the same
worker before its full matrix can start. Preserve failures and native evidence;
no partial Cells acceptance, production change or numerical relaxation. That
probe and matrix subsequently pass in **553.910 s**. D129 now launches the
[independent saved-evidence review](../../reports/REF005D_LIVE_AUDIT_LAUNCH.md),
with 97 passing preflight checks and detached execution,
without rerunning either simulator. Saved arrays get direct bit checks; unsaved
windows get expected-receipt reconstruction, with that evidence limit explicit.
That review now passes in **128.769 s**. D130
[closes the bounded live-recording scope](../../reports/REF005D_LIVE_CLOSEOUT.md)
and launches the [18-solve 10 ms reference study](../../reports/REF005E_REFERENCE_SCOPE_LAUNCH.md)
detached after **73 passing preflight checks**, without a native/Cells run or
automatic campaign. The study's result remains pending. [Next-gate readiness](../BETSE_NEXT_GATES.md)
records the missing junction-topology map and original-data provenance work.
Longer native/Cells correspondence and biological evaluation remain separate. Keep
Cells' own integration and independent physical/reference checks: another
simulator's numerical error is not the behavior to reproduce. No old
timestep or checkpoint identity is silently inherited. Existing material, charge
and energy interfaces are reused; the synthetic law remains separately selectable.
A qualified whole-cell pump–leak model
and a coupled junctional cluster follow; planning biological data acquisition
does not have to wait for those implementations.

## Architecture guardrails

Biological mechanism, spatial resolution, numerical method and execution device
are independent choices. Organ identity remains data, including future multiple
organs and explicit inter-organ ports. Fine cells can retain membrane/compartment
state; any reduced region needs a declared validity regime and checked exchange
of amounts, charge, energy and volume with neighbouring regions.

Use batched, side-effect-free local laws; explicit species/compartment/membrane/
edge axes; one owner per stored inventory and one signed transfer per interface.
Evaluate coupled fluxes at a common solver stage. Inputs and observations do not
silently mutate hidden kinetics. Checkpoints contain all dynamical state.

JAX-friendly array algebra is a useful first constraint, not proof of GPU speed
or scalability. The present dense spatial solve is a bounded reference/backend;
large tissues will need sparse or matrix-free device-compatible solves, an
explicit precision policy and measured communication costs. Multirate stepping
and coarse/fine adaptation need their own conservation and convergence evidence.

No organ, geometry, timestep, biological parameter or experimental uncertainty
is chosen merely to make a source comparison pass. Detailed modes cannot be
silently replaced by reduced modes for speed. Long captures and regressions stay
detached, bounded and user-polled; there is no automatic follow-up campaign.
