# Finite extracellular CPU/JAX assembly

CORE-009 production contract for `finite_extracellular@1`, Cells 0.14.0.
Acceptance results belong in a separate report; this is the implementation and
prospective acceptance contract, not a claim that an organ or GPU is validated.
The physical definition is [SPEC-008](FINITE_EXTRACELLULAR_SPEC.md); the unchanged
[NUM-009 v2 reference](../reports/NUM009_REFERENCE_V2.md) selects RK4/cubic at 1 ms
on fourteen synthetic 0.05–0.3 s cases, with 0.5 ms refinement.

## Ownership and composition

One world contains one finite, fixed-volume, well-mixed extracellular compartment,
one or more fixed-volume cells, one membrane/capacitor per cell, optional
state-bearing Kv1.5-style channels and sparse state-bearing ionic junctions.
All membranes gather their outside concentration from the same inventory.
Disconnected cells therefore still interact through this shared environment.
The outside potential is the zero gauge, not a maintained electrode or bath.

Species properties, compartments, membranes, channels, edges, independent
availability schedules and capacities are explicit configuration data.
The example is [one cell](../configs/finite_extracellular_cell.json).
No organ names, assay identities or species-name dispatch enter the model kernels.
The current channel law binds a declared +1 species and requires 298.15 K.

The existing pure constant-field, reversible pump, channel-kinetic and selective
junction laws operate on the same complete stage state. Each membrane's signed
transfer is scattered once to its cell and once with opposite sign to its
outside owner. Internal junction flux only updates its two intracellular owners.
An unavailable real route still requires valid chemistry, voltage and gates;
its intrinsic gates relax even while transport is blocked.

## State and numerical meaning

The ten evolving fields are:

- `amount_increment[species, cell]` and
  `extracellular_amount_increment[species, outside]`, in fmol;
- membrane leak transfers, pump-cycle integrals and dissipated energy;
- membrane m/h gates and channel transfer integrals;
- junction gates, signed transfer integrals and dissipated energy.

Actual inventories equal immutable initial inventories plus these increments.
Voltage is derived directly as
`V_i = V_i0 + F·1e-15/C_i · sum_s(z_s Δn_si)`.
It is not integrated separately or obtained by subtracting nearly equal large
absolute inventories. Checkpoints retain all ten fields, initial anchors, fixed
charges, ownership and padding; no outside inventory or cycle ledger is inferred
from intracellular amounts on restart.

Cells, membranes, channels, junctions and the outside have independent numeric
capacity axes. The current schema permits one active outside slot per world;
additional slots are genuine inactive padding, not disconnected private baths.
Zero channels/edges and larger padded capacities are supported. No evolving
padding may become nonzero. The pre-allocation array budget includes the outside.

Actual RK4 steps must be at most 1 ms. This is a necessary production restriction,
not a guarantee for arbitrary new parameters, outside volumes or long horizons.
Every stage checks positive physical amounts/concentrations, unit gates,
all-valence membrane/junction voltage domains, the channel voltage domain, finite
state and outside/capacitor countercharge within 1e-20 C. Whole Hermite cubic
interiors also check inventory, gate, voltage and countercharge domains.
No clipping, concentration floors, state projection or automatic retry is used.

Local, outside and global material accounting retain distinct ledgers.
Energy includes both finite ideal chemical inventories and each capacitor once,
with pump chemical work and membrane/junction dissipation. It does not use a
maintained-bath grand potential. The energy budget excludes metabolism, gating
charge, protein energy and volume/mechanical work. Pump drive, temperature and
geometry remain externally prescribed support.

## Shared execution and future GPUs

The common runner, RK4 implementation, event scheduler, scalar/cohort windows,
snapshot format and restart/branch rules are reused without solver-specific
exceptions. The finite model has its own schema, state type and observer identity;
older model identities and equations remain unchanged.

Independent worlds own independent outside inventories and can use the existing
homogeneous-capacity batch path. Within one connected world, later partitioned
GPU execution must reduce membrane contributions to the shared outside and make
the updated inventory available at every solver stage. Junction partition halos
are a separate exchange. This implementation uses pure JAX arrays and explicit
owners but is CPU/float64 only: it adds no GPU backend, distributed reductions,
spatial extracellular mesh, multirate solver or speedup claim.

## Prospective acceptance

Use all fourteen unchanged NUM-009 v2 cases and saved reference trajectories.
No reference ODE rerun or tolerance changes. Require:

1. Independent complete-state RHS checks and all-field trajectory comparisons,
   including outside amounts/concentrations and actual cubic interiors.
2. Eager and JIT CPU runs, fresh-process full-state restarts for every case,
   a future-only branch, full windows and heterogeneous independent-world
   cohorts with complete cohort restart.
3. An independently written saved-data audit of every readout, canonical state,
   conserved quantity, control schedule and cubic; rehashed corruptions refused.
4. Exact earlier-model regression and archived-source replay. The accepted
   0.13.0 source archive is authenticated before any production edits.
5. Maintained tests in explicit current / 0.10 / 0.11 / 0.12 / 0.13 contexts.
   The thirteen prospective v1 complete-session tests remain unexecuted because
   the original NUM-009 v1 session stopped; their v2 replacement does run.

The formal session is prospectively limited to **3600 seconds and 2 GiB**,
CPUs 0–3, four eager lanes and one thread per numerical library.
The larger allowance than CORE-008 covers fourteen rather than twelve cases,
the 1 ms rather than 2 ms step, and additional outside state/readouts. These are
upper limits, not a reservation to be consumed. Any failed/capped attempt is
retained and excluded from acceptance; no silent extension of the budget.
Full regression tests and read-only closeout audits are separate operations.

Run the bounded acceptance with:

```sh
env PYTHONPATH=src OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 taskset -c 0-3 .venv/bin/python scripts/verify_finite_extracellular_build.py --output runs/core-009-2026-09-10/acceptance-01
```

The saved run directory must not already exist. Old 0.13.0 checkpoints require
their preserved source/runtime; strict current-source refusal is intentional,
not a migration mechanism.
