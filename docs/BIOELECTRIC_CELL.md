# First physical cell: Cells 0.5.0

MODEL-003 implements `bioelectric_cell@1`: one well-mixed Na/K/Cl cell, one
explicit lumped membrane, and a maintained bath. This is synthetic dimensional
engineering, not calibrated biology, a BETSE reproduction, or the source's
communicating EMT cells. See the [physical specification](BIOELECTRIC_CELL_SPEC.md),
[numerical contract](BIOELECTRIC_NUMERICS.md), and
[production acceptance](../reports/MODEL003_ACCEPTANCE.md).

## Run, replay, and change future controls

From Cells in the pinned environment; every destination must be new:

```bash
taskset -c 0-3 .venv/bin/python -m cells validate configs/bioelectric_baseline.json
taskset -c 0-3 .venv/bin/python -m cells run configs/bioelectric_baseline.json --output runs/my-physical-cell --checkpoint-at 6
taskset -c 0-3 .venv/bin/python -m cells resume runs/my-physical-cell/snapshots/step-001200 --output runs/my-physical-replay
taskset -c 0-3 .venv/bin/python -m cells branch runs/my-physical-cell/snapshots/step-001200 configs/bioelectric_branch.json --output runs/my-physical-branch
taskset -c 0-3 .venv/bin/python -m cells run configs/bioelectric_controls.json --output runs/my-physical-controls
```

The baseline lasts 10 seconds at nominal step 0.005 s. It starts at -0.065 V,
not a prepared equilibrium. The branch blocks the Na leak from 6 to 8 s and
the pump independently from 6 to 7 s. The separate controls example blocks the
pump at 2.03–5.07 s and Na leak at 3.11–4.13 s. K/Cl leaks remain available.
Neither operation removes the membrane or resets accumulated exchange.

## Data and engineering boundaries

The [host schema](../src/cells/core/bioelectric_spec.py) resolves definitions;
[model composition](../src/cells/models/bioelectric_cell.py) owns the closure and
accumulation; [pure mechanisms](../src/cells/processes/electrochemistry.py) implement
Bernoulli/GHK leaks, electrochemical potentials, and the reversible reference pump.
Mechanisms know nothing about experiments or assay outcomes.

| Definition | Meaning |
| --- | --- |
| `model.population` / `initial_state` | One stable cell ID, positive fmol amounts, fixed pL volume, voltage anchor in V |
| `parameters.membrane` | Separate stable ID, owner-cell and bath IDs, m2 area, F/m2 specific capacitance, per-ion m/s permeability, aggregate fmol cycles/s pump capacity |
| `parameters.bath` | Named clamped, electroneutral bath in mM, zero potential, K temperature, maintained effective ATP free energy in J/mol cycles |
| `experiment.membrane_controls.leak` | Independent Na/K/Cl multipliers in [0,1], resolved by ion name onto the identified membrane |
| `experiment.membrane_controls.pump` | Separate multiplier in [0,1] on that membrane |
| `execution.capacity` / `membrane_capacity` | Independent padded storage sizes, not permission to add active cells/membranes to this closure |

Each control group starts at zero with strictly increasing times. The host forms
a complete four-route array on their event union. Unknown ions, mismatched IDs,
conflicting times, missing groups, and source/contact controls are refused.
Values apply to the following interval. Final-time events change instantaneous
readouts but not prior evolution. Older models keep their configuration meaning.

State comprises `amount[species, cell_slot]`, signed
`leak_transferred[species, membrane_slot]`, and signed
`pump_cycles[membrane_slot]`. Voltage is affine-derived from amount changes and
immutable anchors, not separately integrated. Fixed charge, geometry, IDs/mappings,
bath, and anchors are retained in snapshots and checked against the definition
on restoration. Negative signed ledgers are valid; nonpositive ion amounts are not.

Inactive state is zero, with finite neutral inputs before nonlinear operations
on padded routes. Masks do not hide NaNs. Contributions read the same RK stage
and add to the owner cell. There is no plugin discovery or hidden equilibration.

## Numerics and outputs

CPU float64 RK4, actual steps at most 0.005 s, and a zero-anchored grid split at
all control boundaries are qualified on the 18-case NUM-002 panel. New parameter
combinations need independent reference/refinement checks: the step ceiling and
runtime domain are not universal nonlinear stability or accuracy guarantees.

The reusable checked-RK4 path tests every stage and endpoint for finite state,
strictly positive active ions, unchanged inactive storage, and `abs(zFV/RT) <= 50`.
Derivatives must be finite too. Invalid trials do not enter logarithms. Failure
status is numerical metadata: the compiled scan stops advancing physical state,
and the host refuses the run before publication. No floor, clipping, or automatic
smaller-step retry is used. Refinement is an explicit execution choice.

The observer identifies `read_only_interval_control_cubic_hermite@1`. Both slopes
of each interval hold its controls, including the old-control slope at a switching
endpoint. Accepted times return exact stored states. Cubic samples are checked for
physical validity and accounting, without altering integration. The four earlier
models retain linear interpolation.

NPZ files hold accepted state/layout and labelled observations: amounts and mM
concentrations, voltage, controls, leak/pump fluxes, electrochemical potentials,
inward current, signed chemical power/work, and species/charge residuals. Nonlinear
readouts are derived from sampled primary state using right-continuous controls.
Chemical work comes from the cycle ledger; the independent reference's dissipation
quadrature is not extra production state. Manifests identify source/runtime,
observation and stage-domain policies, payload hashes, timings, and parent provenance.

## Next boundaries

Stateful gates and selective two-cell coupling need specified gate state, kinetics,
electrical closure and independent validation. Source-scaled EMT coordinates and
nominal time still have no inferred conversion to fmol or seconds. Passing physical
engineering checks is not source-assay parity.

Finite baths, multiple facing potentials, changing volume/area, fields and multiple
physical cells need a re-derived electrical/accounting closure; padded slots alone
do not supply it. Independent-world batching and per-world failure policy, GPU
execution, stiff/multirate solvers, fine/coarse coupling, tissues and organs remain
future work. Moving the current model to a GPU would not remove its timestep limit.
