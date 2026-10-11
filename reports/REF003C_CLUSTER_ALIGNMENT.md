# REF-003c: explicit seven-cell BETSE alignment

2026-09-12, D067. **Capture passes; D068 now completes the
[separate audit and closeout](REF003C_CLOSEOUT.md), with all 171 adapter tests
passing.** Actual pinned BETSE initialization, charge closure,
instantaneous passive transport and prescribed single updates now correspond to
the existing Cells finite-compartment model for **seven cells and one shared
bath**. Neither simulator's full time-integration loop ran. This is not a
trajectory, physiological validation or BETSE feature-parity result.

## Resolving the geometry honestly

The earlier [one-cell preparation](REF003B1_PREPARATION.md) remains rejected:
its native preset creates seven cells / 30 membrane faces. A new bounded probe
disabled that preset and supplied [one explicit SVG centre](../validation/betse/single_cell.svg)
through BETSE's actual configuration loader and seeder. Loading succeeded, but
the native Delaunay triangulation raised `QhullError`: one point cannot construct
the required simplex. The [diagnostic](../runs/ref-003b1-2026-09-12/geometry-01/native_result.json)
and [completion receipt](../runs/ref-003b1-2026-09-12/geometry-01/completion.json)
retain the failure and its scalar-divide warning; the probe took 4.202 seconds.
The traceback reaches the pinned `DECMesh.trimesh_core_calcs` / SciPy `Delaunay`
call. This only rules out the two tested routes in this pinned configuration,
not every possible BETSE version or geometry procedure.

The fallback is a **separately registered seven-cell reference**, not an amendment
that accepts seven cells under the old one-cell guard. All seven native volumes,
areas, centres and face owners must exactly match the retained native preparation.
No selected central trace stands in for the entire world. No upstream patch,
replacement triangulator or Cells production change was needed.

## Corresponding model and actual execution

The [new protocol](../validation/betse/cluster_protocol.json) registers nine
preparations, four prescribed flux footprints, two constant profiles, tolerances
and resource limits before capture. Common physical inputs reuse the frozen
[revision-2 base protocol](../validation/betse/alignment_protocol.json).

| Quantity | Explicit correspondence |
| --- | --- |
| Cells and membranes | Seven actual native cells / 30 faces map to seven Cells compartments and seven aggregate membrane owners; each aggregate uses the sum of its own face areas. |
| Outside inventory | One uniform finite bath with effective volume `30 * p.vol_env = 6.75 pL`; it is not a maintained reservoir. |
| Charge closure | Specific capacitance 0.01 F/m², zero polarizability and zero boundary voltage give `V = Q/C`; Cells uses its existing anchored-increment expression. |
| Mobile species | Na, K and Cl, with the registered concentrations/permeabilities and temperature 310.15 K. |
| Immobile charge | Native Ca, P and balancing anion M have zero permeability; their net charges map to explicit Cells fixed-charge fields. |
| Disabled mechanisms | Pumps, ER dynamics, gap-junction exchange, general network, GRN, flow, deformation, osmosis and noise. |
| Numerical context | Native rounded F/R and explicitly matched F/R are separate profiles; only matched constants support direct cross-program differences. Cells runs NumPy, eager JAX and compiled JAX on CPU/float64. |

BETSE runs its actual `Parameters.load`, `SimRunner.seed`, `SimPhase` initialization,
`init_core`, `init_dynamics`, `update_V`, `electroflux`, `update_gj`, `update_intra`
and `update_all_concs` methods. No substitute simulator or solver is injected.
All 332 installed upstream Python files match clean v1.5.0, commit
`5269a714aa2593ed2a6708c4516289977d8ae1a2`. Native and Cells workers use isolated
processes and environments; neither imports the other simulator.

Cells uses the unchanged `finite_extracellular@1` parser, initialization, charge
calculation, RHS and domain checks. Extra inactive cell/membrane/outside capacity
tests the existing ownership masks. Nonzero prescribed states are declared as
**new initial preparations**, with corresponding cell/outside amounts and voltage,
not invented reachable trajectories or partially filled history ledgers. The
production increment-based voltage calculation is also checked independently
against the neutral baseline layout. No claim of equilibration is made: native
neutral initialization is approximately zero volts, not a resting physiological
voltage.

The nine cases cover neutral preparation, sodium entry into the central cell,
potassium exit and chloride entry in outer cells, neutral salt, opposed changes
in two cells with no net bath inventory change, distributed mixed changes,
complete blocking and doubled maximum permeability. These are prescribed states,
not evidence that a biological process produced the transfers. Actual disabled
junction and auxiliary-species fluxes must be exactly zero.

For each case BETSE performs one prescribed concentration update at 0.1 ms;
Cells supplies instantaneous rates, not its own integrated trajectory here.
Uniform, one-face, balanced-face and blocked flux footprints separately exercise
native bookkeeping. Native inward current is compared after aggregation over
each cell's faces; resolved field and individual-face current distributions are
not qualified by this reduction.

## Recorded result

The [capture receipt](../runs/ref-003c-2026-09-12/cluster-01/verification.json)
reports **pass in 18.666 seconds**, finishing at 13:11:52 UTC. It binds 14 payloads,
including both engines' outputs, native YAML, mapped Cells definitions, source
capsule, registration and logs. Both workers report **no warnings**. Limits were
25 seconds per worker, 60 seconds overall and 32 MiB; CPU 0–3 and single-thread
numerical libraries were used. This elapsed time includes setup and compilation;
it is not a simulator-throughput or GPU-speedup benchmark.

Capture receipt SHA-256:
`ca064838d5177543b7b51f8a226f89df18ecfea5d0e51cbf5e04243da42e91c8`.

The [comparison](../runs/ref-003c-2026-09-12/cluster-01/comparison.json) passes
**19,691 scalar tolerance checks**, plus structural and exact-blocking guards.
These include repeated state/accounting checks, not 19,691 independent biological
experiments. GHK is checked against separate 70-digit Decimal arithmetic.

| Recorded metric | Maximum absolute difference/residual |
| --- | ---: |
| Matched Cells/BETSE voltage | 5.90e-13 V |
| Matched per-cell ionic amount rate | 1.15e-12 fmol/s |
| Global material residual across prescribed case updates, both native profiles | 2.26e-13 fmol |

The largest normalized tolerance score is **0.282**, below the frozen limit of
1. Absolute limits remain 2e-10 V, 2e-12 mM, 2e-12 fmol, 2e-10 fmol/s,
2e-20 A and 2e-8 C/m³, with relative tolerance 2e-11. No scientific tolerance
changed after capture.

The uniform footprint provides a useful wrong-volume witness: treating the bath
as `p.vol_env` alone leaves approximately **2.00446e-5 fmol** unaccounted for.
The conservative counterpart follows the native arithmetic mean over all 30
face updates. This validates the source-specific lumped mapping, not a claim
that BETSE's configured geometric box has volume 6.75 pL. Do not copy that
face-count convention into Cells' physical-volume definition or assume it holds
for a different mesh, spatial ECM, outside heterogeneity or upstream version.

Native schedule construction also ran: ten labels span 0 to 1 ms, with sampled
indices 1–9. Source inspection puts observations after native updates, so elapsed
update time and native labels are distinct. A full loop has **not** run to
validate that sample-to-step correspondence yet; it is a requirement for REF-003d.

## Tests, preservation and next gate at the D067 capture handoff

The following records the original capture-stage handoff. Its pending audit and
closeout have since completed under [D068](REF003C_CLOSEOUT.md); the original
capture, preflight receipts and numerical criteria remain unchanged.

All **25 new preflight tests pass** in 3.58 seconds: synthetic checker/corruption
tests and actual Cells definition/domain checks. The
[first preflight](ref-003c-preflight-01.xml) retained one adapter failure: a
doubled-permeability case attempted availability 2, outside the production [0,1]
fraction contract. The adapter now doubles the permeability parameter and keeps
availability at 1. The [second preflight](ref-003c-preflight-02.xml) passes; no
production validator or physics was changed to accommodate the fixture.

The earlier 103 adapter tests and 4190-test production matrix are prior results,
**not newly rerun totals**. All 352 accepted implementation files / 51 production
modules remain unchanged, as do earlier protocols, source capsules and rejected
attempts. Stable 0.14.0 and accepted development 0.15.0.dev0 are not promoted.
The [pre-probe registration](../runs/ref-003b1-2026-09-12/geometry-01/registration.json)
also retains an 800-file worktree baseline for the later closeout.
Direct file-identity inspection finds 793 unchanged baseline files and exactly
seven intended status/design-document edits. All 14 capture payload hashes and
nine captured adapter-source hashes match their registration/receipt. These
identity checks do not replace the pending independent numerical replay and
actual-packet corruption tests.

For the architecture, the useful result is composition: geometry and mechanism
settings stayed in data, with existing species/cell/outside axes and a shared-bath
transfer reduction. The reference adapter did not become a production dependency.
That preserves the CPU/JAX design's future GPU path, but does not qualify GPU
execution, interacting-organ decomposition or a cross-resolution model.

Next, on the user's instruction:

1. Run the separate saved-data cluster audit without either simulator, then add
   tests against the actual packet and rehashed corruptions, including the
   one-centre geometry rejection. Finish the short adapter/preservation closeout.
2. Register **REF-003d**, a short actual native FULL initialization-phase transient
   against Cells' normal RK4 path, starting from neutral preparation. Freeze the
   horizon, timestep-refinement ladder, output/elapsed-time mapping, numerical
   tolerances and resource limits before execution. Retain native raw labels,
   initial state and actual step counts; distinguish pre-update flux from
   post-update state. Do not substitute BETSE flux inside our own integrator.
3. After baseline transient agreement and independent accounting checks, add a
   declared permeability perturbation. Active mechanisms and a published
   physiological case remain later, separate gates.

No separate follow-up audit/regression job or trajectory campaign was launched
automatically after this capture. No job remains running or scheduled. Long
future jobs retain the [detached/no-poll policy](../AGENTS.md).
