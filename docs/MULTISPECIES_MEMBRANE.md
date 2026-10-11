# Multispecies membrane: first production assembly

CORE-006 / D048, Cells 0.11.0. A new `multispecies_membrane@1` family through
the existing CPU/float64 JAX engine. This is one fixed-volume cell, one membrane
and one maintained bath, not tissue, calcium signaling or BETSE feature parity.
The [SPEC-005 physical contract](MULTISPECIES_MEMBRANE_SPEC.md) and
[NUM-006 numerical protocol](MULTISPECIES_NUMERICS.md) retain their original bytes.

[Production acceptance is complete](../reports/CORE006_ACCEPTANCE.md): both
eager/JIT modes on all 14 frozen cases, independently reconstructed readouts,
exact restart/branch/cohort checks, unchanged older-model regressions and 2565
passing tests across the two source contexts below. This is numerical and
software qualification in a declared regime, not new biological validation.

## What changed

Species are declared by stable names and integer valences, not hard-coded ion
positions. A membrane's passive permeability binds every species by name; the
optional synthetic Na/K pump binds its sodium/potassium roles and -3/+2
stoichiometry explicitly. Existing pure constant-field and reversible-pump
laws are reused unchanged. No test, case, organ or species name selects a
numerical law inside the kernel.

Amounts own mobile charge. Voltage remains an affine-derived quantity anchored
to the **original** amounts, fixed charge and voltage assertion. Signed fixed
intracellular charge and maintained bath background charge are explicit inputs;
an inconsistent definition fails without repairing chloride or any other ion.
Turning a route off never removes its species or its charge contribution.

The shared runner, RK4 integrator, observer interpolation primitives and disk
writers are unchanged. Small shared extensions resolve variable-width controls,
estimate memory from species extent and reject incompatible cohort shapes.
The seven older model families retain their equations, configuration meaning,
numerical bounds and output fields. Their source/checkpoint identity is not
silently migrated to the new package version.

## Configuration and identities

See [four-species baseline](../configs/multispecies_baseline.json),
[block/release controls](../configs/multispecies_controls.json), and
[Na/K/Cl reduction](../configs/multispecies_nakcl.json).

The outer configuration keeps `schema_version`, `model`, `experiment` and
`execution`. The new model object contains `id: multispecies_membrane@1`,
`species`, `cell`, `bath` and `membrane`. Those physical objects follow SPEC-005,
with units in field names. It is **not** a loader for the reference's separate
`cells.multispecies_membrane_reference@1` schema.

The experiment declares an end time, read-only observation times and two
independent membrane control schedules. Leak multipliers are complete maps by
species ID. Pump multipliers are scalar. Both groups explicitly start at zero;
events are right-continuous and their union splits the accepted numerical grid.
The final-time setting changes instantaneous readouts, not preceding evolution.

Execution includes explicit `material_balance_atol_fmol` by species. These
are accounting tolerances, **not** integrator error tolerances. NUM-006's supplied
fixtures use 1e-10 fmol for ordinary species and 1e-12 fmol for the small divalent
pool. The settings are hashed and preserved on restart; production does not
recognize the string `Ca` as a numerical special case. Scientific acceptance
always applies the frozen protocol's limits independently of those settings.

Host-side names remain in the complete resolved definition. Device layouts use
local positive integer label codes: species 1…S in declaration order, and code 1
in each of the cell/membrane/bath namespaces. Inactive slots carry -1. The
summary's `identity_labels` dictionary makes this encoding explicit. Codes are
not chemical identity, global organ IDs or string hashes. Changing names/order
changes definition identity; a restart cannot silently reinterpret a code.

## State, numerical checks and observations

| Quantity | Ownership / array axes |
| --- | --- |
| `amount` | Primary fmol inventory, `[species, cell_slot]` |
| `leak_transferred` | Signed inward fmol history, `[species, membrane_slot]` |
| `pump_cycles` | Signed fmol cycle history, `[membrane_slot]` |
| `dissipated_energy_pJ` | Diagnostic quadrature, `[membrane_slot]`; not extra biological energy state |
| Layout | Immutable amount/voltage/charge anchors, valence, stoichiometry, endpoints, geometry and maintained bath support |

Every RK4 trial and endpoint must have positive real-species amounts, finite
state and `abs(z F V / RT) <= 50` for **all** declared valences. Padding is made
finite before logarithms/division, never by flooring a real ion. Failed trials
return refusal without accepting a clipped or partially advanced state.

The largest actual step is at most **0.01 s for this new family**. NUM-006
qualifies this choice only for its two assemblies and fourteen schedules through
10 s; it is not a parameter-box, long-time or all-valence trajectory guarantee.
The old physical cell remains limited to 0.005 s, the physical pair to 0.001 s.
New concentrations, geometry, kinetics or horizons need independent refinement.

Observations use interval-control cubic Hermite sampling. Both endpoint slopes
hold the old interval's control; readouts at the event use the new control.
Every amount and voltage cubic's interior extrema are checked, even if no
observation was requested there. Stored endpoints and all-off intervals remain
exact. Observations never create integration steps.

Readouts include concentrations, voltage, controls, species fluxes, cycle rate,
electrochemical potentials, current, chemical work, dissipation and accounting
residuals. `bath_exchange_fmol` is the signed negative of cumulative net inward
transfer. It is **not** a finite bath inventory. Fixed temperature, volume,
bath chemistry/background and pump drive remain externally supported assumptions.

## Run, resume and qualify

Use a new output directory for every command:

```bash
.venv/bin/python -m cells validate configs/multispecies_baseline.json
.venv/bin/python -m cells run configs/multispecies_controls.json --output runs/my-multispecies --checkpoint-at 0.713
.venv/bin/python -m cells windowed run configs/multispecies_controls.json --window-steps 64 --output runs/my-multispecies-windows
.venv/bin/python scripts/verify_multispecies_build.py --output runs/my-core006-acceptance
.venv/bin/python scripts/audit_multispecies_build.py runs/my-core006-acceptance
.venv/bin/python scripts/test_cells_build.py --output reports/my-core006-tests
```

The ordinary `resume`, future-input `branch`, batch and windowed-cohort APIs also
apply. Complete snapshots retain every dynamic and diagnostic leaf, original
anchors, species/role bindings and local clock. A different observation/recording
policy does not erase history. Changing model chemistry or anchors is not an
allowed future-input branch.

CORE-006's test matrix originally had **two explicit source contexts**. After
CORE-008, current model/engine tests use 0.13.0. Three SPEC-007/NUM-008 graph
reference modules use preserved 0.12.0, and the three SPEC-006/NUM-007
reference modules use preserved 0.11.0. Ten historical NUM-005 modules authenticate their
old experiment sources against preserved 0.10.0, on their frozen CPUs 0–3 with
single-thread numerical settings. The test driver copies a temporary source
workspace and reads existing evidence; it does not patch source validators or
rerun the long campaign. Running all historical provenance tests directly
against changed production sources correctly fails their old identity gate.
New multispecies reference auditing similarly uses
`scripts/audit_preserved_multispecies_reference.py` after the packaging change.

## Multiscale/GPU consequences and next boundary

This adds reusable species/stoichiometry axes, not a universal assembly runtime.
Compatible independent worlds share a species **extent**, not necessarily names
or parameter values. Unequal extents require separate batches; no implicit
padding/remapping is inferred. Cell and membrane capacities remain separate;
memory estimates include species count before capacity-sized allocation.

All numerical state/parameters are numeric PyTrees, ready for later device
qualification. This version still explicitly selects CPU/float64. No GPU speedup,
multi-device execution or efficient coupled-tissue decomposition is established.
Independent-world execution is not communication between cells or organs.

[SPEC-006 now supplies the first state-bearing channel contract](VOLTAGE_GATED_CHANNEL_SPEC.md)
and [independent reference](../reports/SPEC006_DESIGN_CHECK.md), not a production
channel. [NUM-007 now qualifies coupled trajectories](../reports/NUM007_REFERENCE.md),
selecting a 0.5 ms RK4/cubic candidate with passing refinement for subsequent
CORE-007 acceptance. The [separate production channel](VOLTAGE_GATED_MEMBRANE.md)
is now implemented, with [bounded acceptance complete](../reports/CORE007_ACCEPTANCE.md).
This does not alter this model's
10 ms bound. Gate kinetics,
abundance/permeability, experimental inhibition and
geometry remain separate. Prescribed voltage in an **isolated gate test**
is not a whole-cell voltage-clamp feature: that requires an explicit electrode
current/charge closure. Coupled-cell voltage must still follow its owned charge.
A new physical ionic graph, finite extracellular
compartments and fine/coarse coupling follow their own ownership, conservation
and convergence gates in the [capability roadmap](BETSE_CAPABILITY_ROADMAP.md).
[SPEC-007](PHYSICAL_IONIC_GRAPH_SPEC.md) now checks
instantaneous graph composition with a common bath, separate edge histories and
single/disconnected/pair/star reductions. [NUM-008 now qualifies short graph
trajectories](../reports/NUM008_REFERENCE.md), with a panel-specific 2 ms candidate
and passing 1 ms refinement. CORE-008 now implements a separate
[physical graph family](PHYSICAL_IONIC_GRAPH.md), with independently padded
cell/membrane/channel/edge extents and complete transport history; its
[acceptance status](../reports/CORE008_ACCEPTANCE.md) is recorded separately.
This one-cell model and its 10 ms bound are unchanged.
The first biological pilot remains closed/descriptive; no refit or physiological
claim follows from this engineering extension.
