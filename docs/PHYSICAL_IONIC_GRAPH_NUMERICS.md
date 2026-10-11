# Physical ionic graph numerical qualification

NUM-008 / D053, 2026-09-10. This protocol and its
[panel](../configs/reference/physical_ionic_graph_trajectories_v1.json) are
declared before trajectory evaluation. The unchanged
[SPEC-007 contract](PHYSICAL_IONIC_GRAPH_SPEC.md) owns the physics.
Production remains Cells 0.12.0. Results belong in a separate report.

## Cases and scope

Twelve short cases use seven unchanged SPEC-007 assemblies: single monovalent
and synthetic-divalent cells, a disconnected heterogeneous three-cell graph,
interacting mono/divalent pairs and stars, an internally exchanging pair and
star with every bath route disabled, mono/divalent star blocking/release, and
a short junction pulse. The receiving star cell has no membrane channel;
the two junctions share that cell. Volumes, capacitances and gate preparations
differ across cells. No parameter, anchor or initial gate is fitted or repaired.

Horizons are 0.05–0.3 seconds. These are engineering trajectories, not steady
states, tissues or physiological validation. The synthetic unbuffered Ca
species is not calcium signaling. The cycle fixture remains an instantaneous
history witness; no dynamic cycle-memory claim is made here.

For the three edge-free cases, also integrate each component independently
with the unchanged NUM-006/007 local reference and refined Radau settings:
five additional component solves. Save and compare every projected coordinate,
not just voltage. This qualifies composition/reduction and ownership; the
local physical equations are deliberately shared with those earlier references.

## State and independent equations

Flatten the nine SPEC-007 fields in their declared order, cell-/edge-major:

```text
amount N*S, leak N*S, pump N, membrane dissipation N,
membrane gates K*2, channel transfer K, junction gate E,
junction transfer E*S, junction dissipation E
```

The implicit methods evolve amount increments from the original anchors;
all other histories start at zero and all gates retain their explicit values.
The separate RK4 candidate evolves absolute amounts through the unchanged
SPEC-007 Bernoulli evaluator. Never compute voltage from transfer histories,
reanchor, clip, reset disabled gates, or integrate local membranes per edge.

Implicit local membrane/channel terms use the unchanged independent NUM-006/007
hyperbolic/affinity/native-unit expressions at the same complete graph stage.
For each A-to-B edge, independently express the oriented flux as

```text
x = z F (VA - VB) / (R T)
b = x / (2 tanh(x/2)), with b(0) = 1
J = area * P * u * (r + (1-r)g) / 1e-15
    * ((cA-cB)b + (cA+cB)x/2)
g_inf = 1 / (1 + 2 exp(-a Vh) cosh(a(VA-VB)))
```

Use a stable log/cosh equivalent for the independent gate target. Accumulate
each signed edge transfer once, subtract at A and add at B. Edge dissipation
uses its own destination-minus-source electrochemical potential. Local and
edge dissipation remain separate, with pJ histories, not pJ/s history limits.
The reference is CPU-only NumPy/SciPy; neither formulation imports Cells/JAX.

## Controls, native meshes and observations

Each profile row is a complete snapshot with four scalar group defaults and
explicit ID-keyed overrides (cell/species leak, cell pump, channel, junction).
Resolve these once to complete numeric controls. Refuse unknown IDs, duplicate
JSON keys, bad fractions, mutable resolved controls, missing fields or events
outside the horizon. The union timeline starts at zero and is right-continuous.

Split at every event. Hold the old interval control at every RK stage and the
endpoint slope. A final-time event changes readouts only, not the incoming state.
The star block schedule has independent groups, an all-off interval
[0.0679, 0.113] s, staggered junction releases, and a final-time shutoff.
The edge-0 pulse [0.0203, 0.0204] s is shorter than every candidate step.

Candidate meshes are zero-anchored regular grids unioned with all events.
The shared comparison grid unions all candidate endpoints and each interval's
quarter, half and three-quarter points. Native observations return their saved
states exactly; other RK observations use interval-control cubic Hermite data.
Retain data-only Radau power and BDF Newton dense bases. Observations never
choose integration steps.

## Prospective numerical and accounting limits

Use Radau and BDF at rtol 1e-11, atol 1e-13, maximum step 0.005 s;
refined Radau uses 1e-12, 1e-14 and 0.0025 s. These local mixed-coordinate
tolerances are not global error guarantees. The declared candidate ladder is
0.002, 0.001, 0.0005 and 0.00025 s, **tested anew for these graphs**.

| Quantity, maximum across owners | Candidate absolute error | Reference-reference error |
| --- | --- | --- |
| Ordinary amount, leak and signed junction history | 1e-7 fmol | 1e-8 fmol |
| Synthetic Ca amount, leak and junction history | 1e-9 fmol | 1e-10 fmol |
| Pump cycles and channel history | 1e-7 fmol | 1e-8 fmol |
| Each cell voltage | 1e-6 V | 1e-7 V |
| Each membrane/edge dissipation history | 1e-6 pJ | 1e-7 pJ |
| Each membrane gate, open fraction and junction gate | 1e-4 | 1e-5 |

Compare accepted candidate endpoints and common observations separately.
Require per-cell and summed species material residuals <= 1e-10 fmol
(1e-12 for Ca), local charge residual <= 1e-8 V, weighted global charge
residual <= 1e-19 C, and total chemical/capacitor energy change plus both
dissipations minus supplied pump work <= 1e-6 pJ. Use stable log1p energy
differences. Each dissipation history may decrease by at most 1e-10 pJ.
Bath exchange contains only local membrane routes; internal edge history
must not leak into it. Unequal capacitances require weighted, not summed, volts.

Every disabled transfer ledger is exactly constant, including dense observations.
When all transport is off, amounts and ionic histories are constant but gates
follow their analytic fixed-voltage relaxation. Compare both membrane and edge
gate relaxation to the corresponding trajectory gate budgets. Junction-only
cases must retain zero bath histories while conserving global amount and charge.
Test right-continuous endpoint readouts and held endpoint slopes explicitly.

Check every actual RHS call including implicit Jacobian probes, every native
state and every observed state: positive finite amounts, all real membrane
species |zFV/RT| <= 50, channel-owning cell voltages in [-0.120, 0.060] V,
every declared real edge species |zF(VA-VB)/RT| <= 50 (even disabled), and
all gates in [0,1]. No tolerance or clipping. Inspect the whole candidate
cubic through extrema of amounts, each cell voltage, each edge voltage
difference and every gate. Polynomial domain checking is in floating arithmetic,
not a rigorous continuous error bound. Implicit dense domain is checked at
native/trial/common points, not over its whole interpolation polynomial.

Select the coarsest all-case passing candidate whose next-finer trial also
passes. For each case voltage, maximum membrane-gate and maximum junction-gate
errors must improve with ratio <= 0.8 except below floors 1e-10 V and 1e-8
for gates. Empty axes have zero error. A rejected coarse trial does not prevent
qualification of a finer pair. The finest trial alone cannot qualify.
No input, limit or ladder extension follows observed results.

## Bounded execution, evidence and audit

One CPU worker, float64, at most 12 graph cases / 84 graph attempts and five
independent component solves. Session cap: 1800 wall seconds, 256 MiB artifacts,
100000 RHS calls (including Jacobian probes) and accepted steps per attempt,
100000 comparison samples per case. These are work/output caps, not OS RAM
guarantees. Freeze and capture all numerical/checker/auditor/test dependencies
before integration. Use a new destination and refuse overwrites.

Save native states, dense bases, observed data, settings, trial-domain summaries,
verdicts, independent component trajectories and failures. Candidate stage rejection
retains its completed prefix plus stage/time/control/reason and offending state;
do not manufacture its missing suffix. Continue only the declared ladder.
Reference failure or a resource cap stops the session with a failure receipt.
Retain completed attempts; no automatic retry or enlarged budget follows.
Preflight uses shorter synthetic fixtures, not undeclared full-panel attempts.

A read-only auditor checks immutable input and source/archive identities, complete
payload inventory, resolved bindings, settings, meshes, dense replay and reductions;
it recomputes accounting, error, control and timestep-selection verdicts. It does
not rerun an ODE solver. Trial extrema summaries are instrumentation, not a saved
transcript of every adaptive stage. Hashes establish provenance, not biology.

CORE-008 remains a separate production gate: new versioned graph identity,
numeric topology bindings, shared-stage sparse transport, full graph snapshots,
CPU/JAX/reference acceptance, exact replay and cohort isolation. No production
change, GPU installation/benchmark, optimization campaign, finite bath, organ,
multirate scheme or deferred E02 source campaign is authorized by this protocol.
