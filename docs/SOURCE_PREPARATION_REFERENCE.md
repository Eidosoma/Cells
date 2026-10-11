# Independent bounded preparation reference

NUM-005b / D032, 2026-09-08. This is independent numerical infrastructure, not
a production model or a general preparation API. Cells remains 0.10.0.
The frozen [E02-SW1 protocol](E02_SWITCHING_PROTOCOL.md) and
[numerical plan](E02_SWITCHING_NUMERICS.md) are unchanged. Numerical acceptance
and actual preparation endpoints are recorded separately from those prospective
documents; a completed trajectory alone is not a qualified preparation.
The registered 500-unit campaign and separate artifact audit now pass; see
[NUM-005b evidence](../reports/NUM005B_PREPARATION.md) for measured results and
the full prepared packets. Longer connected paths and candidate selection remain
unqualified.

## Scope and separation

Use the already checked [graph equations](SOURCE_EMT_GRAPH_REFERENCE.md), with
fresh E/M regulatory seeds, the complete ionic state and fixed P/Snail/ST context.
Run each isolated cell from zero to exactly 500 nominal time units under the
maintained bath, leak and pump. No connected graph is integrated in this gate.
No native cancer driver, continuing-exploration job, production kernel or GPU is
used. No model equation, parameter, conductance, scientific tolerance, seed or
duration is changed to obtain a preparation label.

The [integrator](../tests/reference_source_graph_numerics.py) accepts the general
fixed-graph reference interface. It knows state coordinates, controls and numerical
limits, not E/M labels. The [campaign](../scripts/qualify_source_preparations.py)
owns the two preparation inputs, comparison inventory and observer criteria.
The [read-only auditor](../scripts/audit_source_preparations.py) imports neither
the simulator nor the reference RHS; it separately reconstructs ledger accounting,
dense domain bounds, source identity, phenotype margins and prepared packet caches.

## Live integration and bounded recording

Run Radau and BDF at `rtol=1e-10`, `atol=1e-11`, and refined Radau at one tenth
both tolerances, with maximum step 0.1. Evolve primary increments about a fixed
full-state anchor and passive typed histories. Isolated preparations have 13
coordinates; the general graph reference retains `13*N + 4*E` coordinates.
Diagnostic histories cannot feed back, and fixed context is not integrated.

One live SciPy solver crosses every recording boundary. Do not call `solve_ivp`
afresh each window, reset adaptive history, reanchor the state, or concatenate all
windows in memory. At most 256 accepted steps are buffered before writing a chunk.
Hash-indexed NPZ chunks hold accepted global clocks, complete increment states,
dense polynomial coefficients/degrees, full initial anchor and fixed context.
Adjacent chunks share an exactly identical boundary state and clock.

These boundary snapshots contain complete physical/ledger state. They do **not**
serialize every private adaptive-solver cache or promise an exact Radau/BDF restart.
The live run preserves adaptive history; artifact sampling is read-only and does
not restart integration. Production's existing strict checkpoint contracts are
unchanged. No simulation-history array or list grows with the complete horizon.
Small fixed observer panels and streaming scalar maxima are retained separately.

Read installed, pinned Radau/BDF dense coefficients directly, rather than fitting
a polynomial to samples. Radau uses a cubic and BDF degrees one through five.
Compare an independently evaluated power polynomial with SciPy's output at both
endpoints and five interior points, using actual representable global times.
Accepted boundary values take precedence over polynomial endpoint roundoff when
sampling an exact accepted time. This does not authorize shifting observer clocks.

## Numerical checks

- Check all real stationary points of every primary-coordinate polynomial,
  each affine cell/edge voltage polynomial, and each ledger-reconstruction
  residual. Enforce the existing concentration, voltage, exponent and `2e-9`
  accounting limits. Blocked history coefficients must be exactly zero. No
  negative concentration clipping or tolerance around the declared domain is used.
- Use a bounded second-order finite-difference Jacobian, with zero passive
  columns, central differences where valid and one-sided differences at domain
  boundaries. Check it against a separate five-point stencil at a different
  step scale at the initial and final states. Perturbing histories must leave the
  complete derivative bitwise unchanged. All these RHS calls count toward budget.
- Merge the three methods' accepted endpoints and midpoints with fixed observer
  times, without storing the whole merged grid. Compare all three method pairs
  at every merged time, including complete typed histories, voltage, scales,
  membrane/junction fluxes and reconstructed binding caches.
- Apply the frozen error budgets and their 0.1 reference-agreement fraction.
  Binding caches additionally use the same budget as regulatory coordinates;
  this is an explicit extra diagnostic check, not a relaxed scientific target.
- At the integer observations 400–500, require the intended signed `u-m` margin
  to clear 10 after subtracting the full coordinate error budgets plus measured
  reference disagreement. Apply the corresponding allowance to each E/M
  regulatory anchor separation, which must clear 1.
- Report per-coordinate drift, peak-to-peak range and maximum absolute RHS over
  those observations, plus voltage drift/range/RHS in volts. Ionic and regulatory
  values retain their distinct source units. A zero residual, full-state
  equilibrium or continuous-time phenotype residence is not required or claimed.

Polynomial extrema and numerical uncertainty allowances use floating-point
arithmetic. Neither is a rigorous interval proof of the ODE solution. Agreement
among independent methods is empirical numerical qualification, not biological
validation or a guarantee for other initial states and horizons.

## Budgets, provenance and publication

The campaign registers six attempts and archives source/config/test/runtime pins
before the first trajectory. Workers verify that identity and run sequentially
under CPU affinity 0–3 with one numerical-library thread. The frozen limits remain
900 seconds per worker, 3,600 seconds per campaign session, 2,000,000 RHS calls,
1,000,000 accepted steps, a 256 MiB working-array estimate and a 1 GiB artifact
budget. Preflight the uncompressed output estimate before each array batch.
These are array/work/output limits, not a total process-RSS guarantee.

Timeout or exhausted resources means **incomplete**. Domain refusal or numerical
disagreement means **unqualified**, not a biological negative. Retain registration,
source capsule, logs, complete earlier chunks and failure records. Do not retry
with altered scientific inputs or expanded budgets automatically. A success
manifest is written only after the whole registered campaign and checks pass.

After all six trajectories and preparation criteria pass, write a qualification
receipt, then a new hash-pinned `prepared-packets.json` referencing that receipt.
Each E/M packet includes its original anchor, refined exact endpoint, complete
absolute/increment history state, fixed context, reconstructed source packet,
phase clock, numerical allowance and parent trajectory digest. A future connected
world copies the prepared primary/context with **new zero assay ledgers** and
explicit parent provenance; this is not an ordinary restart or a replication law.

## Commands and next gate

```bash
taskset -c 0-3 .venv/bin/python -m pytest tests/unit/test_source_preparations.py -q -W error
env OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 taskset -c 0-3 .venv/bin/python scripts/qualify_source_preparations.py --output runs/my-new-preparation-attempt
taskset -c 0-3 .venv/bin/python scripts/audit_source_preparations.py runs/my-new-preparation-attempt
```

The first command runs bounded engineering tests, including a clearly labelled
one-unit smoke case; it does not substitute a shortened scientific preparation.
The second command requires a new directory and runs the registered 500-unit
campaign. The third is a read-only audit of a completed campaign.

NUM-005c remains responsible for all 14 connected 1000-unit conditions, the
registered RK4 study, selected/half-step qualification and candidate-owned
preparation-to-contact continuations. No long-time production timestep is chosen
here. MODEL-006/VERIFY-011 and ASSAY-002 follow the full numerical gate. Fluid
fields, multirate/fine-coarse physics, interacting organs and GPU execution remain
separate future work.
