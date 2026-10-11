# Independent source-coordinate fixed-graph reference

NUM-005a / D031, 2026-09-08. **Implemented and checked outside production.**
This completes the instantaneous graph-composition gate in the frozen
[E02-SW1 numerical plan](E02_SWITCHING_NUMERICS.md), not its trajectory
qualification. Cells production remains 0.10.0 and its nominal communicating
model remains a pair. [Acceptance evidence](../reports/NUM005A_REFERENCE.md)
records native comparisons, invariants, source preservation and the retained
first capture failure.

## Composition and state ownership

The [independent reference](../tests/reference_source_graph.py) accepts explicit
cell IDs, edge IDs/endpoints, full primary/context arrays, membrane and per-edge
diffusion, algebraic gate profiles, hemichannel orientation and separate held
controls. It checks a simple fixed graph: at least one cell, zero or more edges,
unique nonnegative integer IDs, no self-edge or duplicate undirected edge, and
exact axis lengths. It does not implement inactive capacity, topology events,
an experiment scheduler or production configuration parsing.

Local regulation and membrane exchange are evaluated once per cell. Each edge's
four transported coordinates (Na/K/Cl and the source miRNA proxy) contribute
equal and opposite transfer to their two endpoints through an **explicit loop**.
The loop is independent of production scatter and is also checked against a
separate incidence-matrix assembly. Summing complete pair derivatives would
duplicate the local dynamics of shared cells and is not used.

Reuse the independently written SPEC-003 constitutive equations and isolated
regulatory oracle, not Cells kernels or BITSEY implementation. Source membrane
area normalization, upwind transport, pump eligibility before IC-leak inhibition,
non-iterative binding and nominal clock remain explicit. Per-edge gate profiles
are algebraic, not evolving memory. Regulatory transport sees effective valence
-1 while the regulatory coordinates remain excluded from ionic charge closure.
There is no degree normalization, donor clamp, new cancer-expression mechanism
or assay-specific equation. The inherited pair reference is unchanged.

For N cells and E edges the reference interchange vector has `13*N + 4*E`
coordinates, with separately named slices:

| Quantity | Coordinates | Role |
| --- | ---: | --- |
| Primary Na/K/Cl and u/m/z | 6N | Evolving state; ionic and regulatory units differ |
| Membrane leak history | 3N | Ionic concentration-equivalent contribution |
| Pump-cycle history | N | Ionic contribution with stoichiometry (-3,+2,0) |
| Oriented ionic exchange | 3E | One signed ledger per ion and edge |
| Local regulatory history | 3N | Source-coordinate local contribution |
| Oriented miRNA exchange | E | Source-coordinate regulatory transfer |

Fixed P/Snail/ST context and derived binding caches, voltages and gate scales
are not integrated coordinates. History coordinates never feed back. The
reference supports both absolute-primary and fixed-anchor increment derivatives;
neither is a solver selection. For N=2/E=1, all 30 coordinates retain the existing
pair-reference ordering. Constructor inputs are copied, numerical parameter/
anchor arrays are read-only, and alternate held controls are checked explicitly.
Create a new model for changed fixed context/layout; this object is not a mutable
experiment controller or a production checkpoint format.

## What the checks establish

The [frozen probe definition](../configs/reference/source_emt_graph_probes_v1.json)
expands to 45 instantaneous inputs:

- 17 existing pair initial-state/control settings, including gated orientation,
  release and pulse settings. These are initial states under held controls,
  not newly evolved event states or rerun trajectories.
- 14 E02 **construction-seed** conditions and two isolated preparation seeds.
  These exercise topology/control construction before any preparation; they
  are explicitly not the future 500-unit prepared states.
- 12 additional constructed cases: isolated cell, star, mixed gates, reversed
  edges with/without hemichannel swap, cell/edge permutations, chain,
  disconnected pairs plus an isolate, separate base-membrane/leak inhibition,
  blocked star and absent contacts. The panel spans one through five cells.

The [native capture adapter](../scripts/capture_source_graph_reference.py) calls
only reusable modules in the pinned clean local checkout, in a separate
60-second-limited reference process. Expanded full inputs and harness/source
hashes are saved before execution. Array-valued native diffusion and masked
native algebraic gates specify per-edge controls; they do not replace flux
formulas. The worker imports neither the independent reference nor production,
the cancer driver, or continuing-exploration dispatchers. It performs no
integration and deliberately starts with stale finite plotting caches.

All 45 native full-RHS/readout comparisons and the 17 pair reductions pass the
unchanged instantaneous tolerances. Tests also check local terms once per cell,
reciprocal accounting, donor accumulation, disconnected-component independence,
permutations, orientation, charge exclusion, pump eligibility, state/domain
refusal and corrupt-evidence rejection. Algebraic tangent reconstruction of
state from ledgers is a bookkeeping identity, **not an accepted Euler step**.

The first native attempt failed in the new diagnostic collector's tuple indexing,
after the native RHS returned. Its input registration, log, failure receipt and
11-file source archive remain. Correcting that single collector index changed
no model, input or tolerance; the new output directory contains the passing
capture. No upstream implementation is vendored.

## Next: bounded preparation, then long-time qualification

NUM-005 remains in progress. NUM-005b must implement bounded independent
integration/recording and qualify the two exact 500-unit preparations, using
Radau/BDF/refined references, all-interval domain checks, accounting and the
frozen phenotype-margin/drift criteria. It must preserve full endpoint packets
and their provenance before any connected run. Do not substitute these seed
probes or the old 10000-unit pair inputs.

Then NUM-005c qualifies the 14 connected 1000-unit conditions and the registered
RK4 study, including candidate-owned preparation continuations. Only after that
evidence may MODEL-006/VERIFY-011 extend production through shared engineering
and ASSAY-002 report the selected assay. No long-time step is selected here.
GPU, multirate/fine-coarse physics, physical EMT calibration, memory/relay and
organ models remain separate gates. A fixed graph is a useful model interface,
not itself a computational-multiscale method.

## Reproduce

```bash
taskset -c 0-3 .venv/bin/python scripts/check_source_graph_reference.py
taskset -c 0-3 .venv/bin/python -m pytest tests/unit/test_source_graph_reference.py -q -W error
```

The first command audits the retained native fixture without needing a source
checkout or launching a simulation. For a new native derivative capture, use
the existing optional reference environment and a **new** output directory:

```bash
taskset -c 0-3 .reference-venv/bin/python scripts/capture_source_graph_reference.py upstream/bitsey --output runs/my-native-graph-probes
```

Never overwrite the retained fixture or a previous attempt to make a new result
look like the original. The source reuse terms and nominal/physical unit boundary
remain those of [SPEC-003](SOURCE_EMT_PAIR_SPEC.md).
