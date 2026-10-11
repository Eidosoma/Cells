# Source-compatible EMT pair: Cells 0.7.0

`bitsey_emt_pair@1` couples source-scaled regulation, Na/K/Cl membrane exchange
and selective contact transport through the shared JAX engine. It is the seventh
production model, not a replacement for the physical bioelectric pair. The
[specification](SOURCE_EMT_PAIR_SPEC.md), [numerical contract](SOURCE_EMT_PAIR_NUMERICS.md)
and [acceptance report](../reports/MODEL005_ACCEPTANCE.md) distinguish its equations,
qualified scope and engineering evidence.

This is a bounded nominal-clock source-compatible model, not physical EMT
calibration, full Levin-assay parity, a memory/heredity result or an organ.

## Run, resume and intervene

From the Cells directory, choose new output paths:

```bash
taskset -c 0-3 .venv/bin/python -m cells validate configs/source_pair_baseline.json
taskset -c 0-3 .venv/bin/python -m cells run configs/source_pair_baseline.json --output runs/my-source-pair --checkpoint-at 5
taskset -c 0-3 .venv/bin/python -m cells resume runs/my-source-pair/snapshots/step-000500 --output runs/my-source-replay
taskset -c 0-3 .venv/bin/python -m cells branch runs/my-source-pair/snapshots/step-000500 configs/source_pair_branch.json --output runs/my-source-branch
taskset -c 0-3 .venv/bin/python -m cells run configs/source_pair_controls.json --output runs/my-source-controls
```

The baseline imports the previously prepared full E/M primary/context values
and runs for ten **nominal source-time units**, not ten physical seconds. It does
not rerun preparation or establish equilibrium. The branch starts from the exact
five-unit state, inhibits miRNA contact transfer until 7.13 and cell A pumping
until 6.27; ionic contact remains active. No state or history is reset. The
separate controls example uses constructed voltage-gradient seeds, algebraic
40/37 gating and the frozen 0.137/0.274 pulse protocol.

Snapshots require matching source and runtime identities. A branch may change
only future controls, horizon and observations, retaining its accepted boundary
and past schedule. Model parameters, initial anchors, geometry, entity IDs and
execution settings cannot change through an ordinary branch. A future cell
transplant or donor-removal operation needs its own explicit interface.

## Data and ownership

The first profile declares two equal fixed spherical cells, one identified
membrane per cell, one oriented contact and one maintained bath. Cell, membrane,
contact and bath ID namespaces are distinct. Membrane records and membrane/route
control groups may be reordered; IDs and route names resolve them on the host.
Ionic and regulatory row order is explicit and strict. Extra cell, membrane and
edge capacities are independent zero-state padding, not additional biology.
The engine itself is not restricted to two cells: other registered models
already use data-defined graphs, and future profiles require their own validation.

| Dynamic field | Axes | Meaning |
| --- | --- | --- |
| `ions` | Na/K/Cl, cell slot | Source numerical ionic concentrations, mol/m³ |
| `regulation` | total miRNA / mRNA / protein, cell slot | Nominal regulatory coordinates, not ionic inventory |
| `leak_history` | ion, membrane slot | Signed inward concentration-equivalent contribution |
| `pump_history` | membrane slot | Signed cycles in concentration-equivalent units; (-3,+2,0) ionic stoichiometry |
| `ion_transferred` | ion, edge slot | Signed concentration-equivalent transfer from sender to receiver |
| `local_regulation` | regulatory coordinate, cell slot | Integrated local regulatory contribution |
| `mirna_transferred` | edge slot | Signed nominal regulatory transfer, not electrical charge |

Histories integrate at the same stages as the corresponding primary state and
never feed back. Initial anchors plus these contributions reconstruct every
primary coordinate. A checkpoint also retains immutable P/Snail/inert ST context,
layout, geometry, source parameter identity and numerical continuation.

Voltage is derived from ionic concentration and P. Regulatory coordinates have
zero voltage charge weight, while miRNA transport uses source effective valence
-1. Regulation does not feed back into ionic slopes in this first profile.
The endogenous cancer K-expression mechanism is not implicitly present.

Free-miRNA and seven binding complexes are pure reconstructed readouts. The
source's approximate free proxy equals total miRNA; weighted complexes partition
mRNA, not a physically conserved free-plus-bound miRNA inventory. There is no
extra gate state: optional 45/45 or 40/37 scales are algebraic voltage readouts.
Their source amplitudes may exceed one. Reversing a heterotypic junction as an
identity transformation also requires swapping its hemichannel parameters.

## Independent controls and source laws

Every membrane has separate per-ion leak and pump schedules. The contact has
separate `ions` and `mirna` route schedules. All prescribed multipliers lie in
[0,1]; their schedules begin explicitly at time zero and are right-continuous. The shared host
resolver forms their event union into a membrane array and a route/edge array;
the runner does not know assay names or desired phenotypes.

Blocking miRNA transfer does not block ionic communication. Blocking IC leaks
does not disable pumping if a base membrane diffusion coefficient is positive.
Setting all base membrane coefficients to zero does disable that cell's pump,
matching the source's eligibility rule. A prescribed block does not delete a
cell or contact, alter intrinsic gate parameters, or reset diagnostic history.

The pinned parameter set fixes source constants, 310 K, five-micrometre radius,
capacitance, membrane/contact lengths and ATP/ADP/Pi pump context. The schema
exposes initial primary/context values, identified membrane/contact diffusion
coefficients, bath concentrations, selected gate and controls. A new parameter
regime is not automatically numerically qualified because it parses.

Membrane GHK regularization, source pump activity convention, upwind junction
drift, separately rounded electrical constants and whole-cell surface
normalization stay inside the named source-law module. Local regulation reuses
the existing pure EMT component. Shared graph scatter adds opposite edge
contributions; no source-specific integration or snapshot branch was added.
Physical transport/pump laws and energy claims of the other models are unchanged.

## Numerical contract and observations

CPU float64 RK4 uses a zero-anchored grid split exactly at every control event,
with maximum actual step 0.01 nominal units plus a floating-grid roundoff
allowance. All 14 frozen cases pass against the prior NUM-004 references.
That panel covers one- or ten-unit horizons, not arbitrary parameter sets,
long-time memory or an organ-wide timestep policy.

Checked stages and endpoints require finite storage, active ions in [1e-6,1000],
regulation in [0,1000], membrane and junction voltage magnitudes at most 0.2 V,
and exact zero inactive state. Domain violations are refused, never clipped.
Resource guards precede capacity-sized allocation. History accounting is checked
within 2e-9 in each coordinate's units.

Read-only cubic Hermite observations use both endpoint slopes under the same
interval-held control. At an event the preceding cubic uses old controls while
instantaneous readouts use new ones. Stored endpoints are returned exactly;
observation requests do not affect integration. Every primary and affine voltage
interpolant is checked at its floating polynomial extrema, even without requested
interior samples; all history coefficients must remain finite. This is not
rigorous interval arithmetic or an adaptive error guarantee.

Artifacts retain full accepted and observed state, controls, pure voltage/gate/
flux/binding readouts, accounting, labels, IDs and provenance. Labels never affect
dynamics. Flux fields are source numerical surface fluxes, not uniformly mol/s;
ionic and regulatory coordinates must be interpreted with their distinct units.
There is no dissipation inequality or physical regulatory-energy claim.

The source's native adaptive Euler clock can overshoot intervention times.
Cells retains exact event splitting and its own accepted clock; it does not copy
the native lagged-cache storage convention or overshoot to match old outputs.
NUM-004 preserves that discrepancy and the passing native refinement separately.

## Remaining engineering and science

CORE-004 now verifies [independent-world batching](INDEPENDENT_WORLDS.md) and
bounded CPU work/memory profiles, keeping independent simulations distinct from
interacting organs. Bounded windows and recording policies are the next execution
design; source-pair batching shows no overall speedup at the largest tested count.
Large-GPU and multirate/coarse-grained execution need accuracy and accounting
checks under their own representative workloads. No GPU backend is enabled by
this release and no tissue reduction is inferred from the nominal clock.

Longer E02 switching cases, selected memory/relay protocols, full-state donor
removal, and endogenous cancer-expression/neighbor strategies remain separate
acceptance gates. The continuing exploration was not rerun by this build.
