# Stateful membrane channel in the shared engine

CORE-007 / D051, Cells 0.12.0. `voltage_gated_membrane@1` composes the
[multispecies membrane](MULTISPECIES_MEMBRANE.md) with the
[SPEC-006 channel law](VOLTAGE_GATED_CHANNEL_SPEC.md). Its scientific numerical
baseline is [NUM-007](../reports/NUM007_REFERENCE.md), not the older membrane's
10 ms step. [Production acceptance](../reports/CORE007_ACCEPTANCE.md) is complete,
separately from that reference qualification: all fourteen eager/JIT cases,
restart/branch/window/cohort checks and all 2883 regression tests pass.

## What is implemented

One cell, one maintained bath, one membrane, and one state-bearing channel.
Species, valences, charge anchors, pump roles, channel binding and controls are
data. This first identity supports the named `betse_kv1p5_mh@1` continuous m/h
law at 298.15 K, binding a declared +1 species as its potassium role. A species
label does not choose a kernel. This is not a full channel catalog, voltage
clamp, native BETSE timestep implementation, or calibrated physiological model.

| State | Numeric axes | Ownership |
| --- | --- | --- |
| `amount` | species × cell capacity | Only mobile-charge inventory, in fmol |
| `leak_transferred` | species × membrane capacity | Baseline passive transfer, inward fmol |
| `pump_cycles` | membrane capacity | Signed pump cycles, in fmol |
| `dissipated_energy_pJ` | membrane capacity | Resolved ionic dissipation integral |
| `gate` | 2 × channel capacity | Separate activation m and inactivation h |
| `channel_transferred` | channel capacity | Separate signed inward channel transfer, in fmol |

Initial m and h must both be declared; neither is silently replaced by its
equilibrium value. Equal `m*h` is not necessarily equal future behavior.
Permeability, abundance, intrinsic gates, experimental availability and membrane
area are independent inputs. The effective permeability is
`Pmax * abundance * availability * m * h`.

Availability zero suppresses channel current, **not gate evolution**. Previously
accumulated channel transfer survives a block, checkpoint, and future-input
branch. Baseline leak and pump schedules remain independent of channel controls.
All three schedule groups explicitly begin at zero and are right-continuous;
the shared clock splits exactly at their union of event times. Each integration
interval holds its old control through all stages, including its endpoint slope.
An observation at a switch uses the new control without changing the state.

The ionic laws are reused from existing pure kernels. Amount and gate derivatives
share the same stage state and amount-derived voltage. Each membrane's charge
anchor remains the original declared one; no independent voltage inventory or
implicit electrode is added. Channel current enters the ionic amount and energy
rates once. Material accounting sums baseline leak, stoichiometric pump transfer
and channel transfer. The diagnostic projection does not merge their saved ledgers.
Bath exchange is a maintained-reservoir ledger, not a finite bath inventory.

Energy accounting covers ions and the capacitor. It deliberately neglects gating
charge, channel conformational energy and protein turnover. It is not a claim of
complete protein thermodynamics.

## Numerical and execution contract

- CPU, float64, checked coupled RK4; largest actual step at most **0.0005 s**.
  NUM-007 qualifies only its fourteen short cases, with 0.25 ms refinement. This
  bound is not an accuracy guarantee for arbitrary parameters or long durations.
- All real trial states and endpoints require positive species amounts, finite
  storage, m/h in [0,1], and channel voltage in [-0.120,0.060] V. The existing
  all-valence electrochemical domain also applies. Failure refuses a step without
  clipping, accepting a partial state, or advancing its clock.
- Read-only cubic observations retain every state field. Every complete cubic
  interval is checked for amount, voltage and gate extrema, even when no requested
  observation samples the dangerous interior. Observer schedules do not change
  integration results.
- Cell, membrane and channel capacities are separate. Capacity is **storage**,
  not permission to populate additional cells or channels in this identity.
  Inactive slots are sanitized before nonlinear evaluation; unavailable real
  channels are not treated as padding.
- The common scalar, bounded-window, batch and independently clocked cohort
  paths remain in charge of execution. Memory preflight includes channel extent
  before capacity-sized arrays are allocated. Cohorts require compatible species
  extent and all three capacities; incompatible worlds need separate cohorts.
- Complete flat numeric state/layout records use the existing checkpoint schema.
  Snapshots bind the model/law, original charge anchors, geometry, species/channel
  IDs, gates, all ledgers, precision, sources, runtime and event cursor. A branch
  may change only supported future controls, observations and horizon.

The shared runner, RK4 implementation, I/O and earlier model equations have not
been specialized for the reference cases. New hooks provide a model-owned working
array estimate and additional compatible-batch capacities. No organ-name branches
or framework-wide channel plugin system are needed for this extension.

## Run and inspect

Every output directory must be new:

```bash
taskset -c 4 .venv/bin/python -m cells run configs/voltage_gated_baseline.json --output runs/my-channel
taskset -c 4 .venv/bin/python -m cells run configs/voltage_gated_pulse.json --output runs/my-channel-pulse --checkpoint-at 0.0203
```

The [baseline](../configs/voltage_gated_baseline.json) runs 0.5 seconds. The
[pulse](../configs/voltage_gated_pulse.json) uses the synthetic divalent assembly
and a 0.1 ms availability pulse. It is intentionally shorter than the nominal
0.5 ms step; event splitting, not an observer, resolves the pulse. Neither example
claims automatic equilibration. Find exact snapshot paths in each run's manifest
and use the existing `resume` or `branch` commands.

Alongside all state histories, observations include channel availability, m*h,
gate equilibrium values, time constants and rates, effective permeability, flux,
electrochemical potential and dissipation. Membrane current, bath exchange and
material/charge/energy residuals include the channel contribution.

Qualification commands, with new destinations:

```bash
taskset -c 4 env OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 .venv/bin/python scripts/verify_voltage_gated_build.py --output runs/my-core007-acceptance
taskset -c 4 .venv/bin/python scripts/audit_voltage_gated_build.py runs/my-core007-acceptance
.venv/bin/python scripts/test_cells_build.py --output reports/my-core007-tests
```

The saved-output audit uses independent native-unit gate equations, hyperbolic
permeation, thermodynamic identities and reconstruction of the frozen implicit
reference. It also independently rebuilds interval-held cubic observations and
checks their extrema, without solving an ODE again.

Acceptance scheduling revision 3 uses a coordinator on CPU 4 and four independent
eager verification lanes on CPUs 0–3, each with single-thread numerical libraries.
It uses a 2400 s per-session and 1 GiB output cap. The original 512 MiB allocation
was insufficient for the projected complete per-window checkpoint evidence;
both earlier interrupted attempts are retained. Do not run it concurrently
with this host's historical test matrix on CPUs 0–3. This is verification-job
scheduling, not a change to the simulator or a performance benchmark. `--reuse`
can re-audit and copy complete scalar records from a retained interrupted session
with identical production/runtime and unchanged verification dependencies; only
the scheduling driver may differ, and its original registration remains recorded.

## Preservation and next boundary

Accepted 0.11.0 was [archived before production edits](../reports/core-007-preservation.json).
Current loaders refuse implicit migration; old checkpoints require their archived
source/runtime. NUM-007's strict old-source audit runs via
`scripts/audit_preserved_voltage_gated_reference.py`; its source guards are not
weakened to accommodate 0.12.0.

CORE-008 adds a fourth test context: current 0.13.0 production; ten historical
NUM-005 modules under preserved 0.10.0; three SPEC-006/NUM-007 modules
under preserved 0.11.0; and three SPEC-007/NUM-008 physical graph modules under
preserved 0.12.0. These are temporary source/evidence copies, not reruns
of long scientific campaigns or exemptions from provenance checking.

This layout is compatible with later JAX device qualification but still selects
CPU explicitly. No GPU speedup, distributed execution, adaptive reduction or
multirate coupling is demonstrated. Independent worlds do not communicate.
[SPEC-007](PHYSICAL_IONIC_GRAPH_SPEC.md) now supplies the separate **physical ionic
graph** contract and [instantaneous checks](../reports/SPEC007_DESIGN_CHECK.md):
single/disconnected reductions, reciprocal pairs and a shared-recipient star,
with independent per-edge history/dissipation. [NUM-008 now qualifies twelve short
graph cases](../reports/NUM008_REFERENCE.md), selecting 2 ms RK4/cubic with passing
1 ms refinement. That different preparation/regime does not relax this one-cell
model's 0.5 ms limit or establish an arbitrary-graph bound. CORE-008 now
implements the separate [physical graph family](PHYSICAL_IONIC_GRAPH.md);
[production acceptance](../reports/CORE008_ACCEPTANCE.md) is tracked separately.
This is a step toward tissue, not an organ preset, GPU run
or restart of the separate deferred E02 campaign.
