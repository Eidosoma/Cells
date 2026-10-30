# Explicit physiological passive-permeability view

Chief-assigned three-file host adapter, frozen and qualified on 2026-10-30.
[The workqueue](physiology_permeability_view_workqueue.json) records exact
sources, fixed budgets, resources and accepted evidence. Chief owns future
driver/checkpoint integration; no original source, scheduler, state or numeric
checkpoint was changed by this worker feature.

## API

`cells.models.physiology_permeability_view.evaluate(spec, state, layout, control,
binding, component, *, step_s)` returns frozen `PermeabilityView` with:

- `runtime_layout`: original ordinary layout type, changing ONLY
  `membrane_permeability` to the accepted component's literal current D/thickness.
- `readouts`: complete original model readouts (the original field result for
  passive tissue); `derivative`: every original state RHS field.
- `physical_permeability`: immutable current/base/signed-scheduled P buffers
  mapped by the qualified tissue binding; only current P enters the RHS.
- `admission`: immutable source/binding identity, actual held control, proposed
  step, all original balance diagnostics, actual passive and fuel turnover,
  and the unchanged component time/loop count/stream tick.

`.field` is a convenience property returning the full original field readout.
All returned runtime/readout/derivative/control/permeability arrays have
immutable bytes owners, including zero-dimensional scalar arrays. Original
spec/state/layout/component bytes and writeability flags remain unchanged.

Supported exact families are ordinary passive `resolved_tissue@1` (12 fields),
ionic `resolved_tissue@12` (19), calcium `resolved_calcium@11` (34), and finite
fuel `resolved_calcium_energy@5` (38). Binding is the previously qualified
`TissueBinding`, with actual owner IDs/SI geometry and explicit positive
thickness. Other model types, water/cut/bath/transport extensions and implicit
geometry are outside this view.

## Admission and preserved physics

The adapter reconstructs actual binding provenance from the exact complete
ordinary definition and compares every original layout field to the original
constructor: ownership, geometry, anchors, active masks, channels, pumps,
chemical/fuel parameters and source P. Exact state/control types, shapes and
precision are required. The actual held control must be finite in [0,1].

The only runtime replacement is passive P. An internal declaration with that
same changed P is used exclusively for original `check_values`/`check_steps`;
it is never returned as a rewritten spec/checkpoint. Every other reconstructed
parameter is verified unchanged. Original domain, material, charge, energy,
method/gate/loss and actual-control field checks remain active. All active
channels/pumps and their complete equations remain in the original readouts;
there is no scaling of a total membrane flux or replacement of the full RHS.

`step_s` is explicit, finite and positive. It cannot exceed the source nominal
dt apart from the explicit clock-representation bound
`8*epsilon*max(source_horizon, source_dt)`. It also passes all inherited step
ceilings. Actual absolute passive membrane transfers are summed separately at
each finite free-ion owner (reservoir stocks are held); the step fraction must
be <=0.05. Live finite ATP/ADP/Pi additionally use gross hydrolysis PLUS gross
synthesis from all Na/K, PMCA, ER and regeneration consumers, with fraction
<=0.05 of the smallest actual pool species. Net cancellation cannot hide either
bound. These are stage admission checks; this module performs no integration.

Existing structural limitation: original ordinary domain checks require zero
past passive transfer when a species/membrane P is zero. Therefore setting
current P to zero on an evolved nonzero passive ledger explicitly refuses.
The adapter does not reset histories or silently reinterpret zero P as an
availability gate. Initial zero passive P with zero passive history remains
valid when the original model admits it; active channels/pumps still operate.

The held control is an explicit caller input, not proof of synchronization with
a schedule or component clock. Component loop dt/time/count/tick remain
independent. This function draws nothing, finalizes no scheduled buffers,
advances no clock, updates no protein, adds no protein charge and writes no
numeric checkpoint. The runtime layout is temporary and must not replace the
original declared layout in a numeric checkpoint.

Unit conversion is literal float64 D/thickness with no snapping or repair.
The exact unchanged-P tests use positive power-of-two thicknesses so the mapped
P is bit-identical to declared P. Every original readout/RHS field and original
balance admission diagnostic is then identical, including evolved states.
Arbitrary positive thicknesses retain the qualified unit bridge's floating
representation semantics.

## Independent evidence

All 43 host cases passed in 11.82 s, including 32 complete initial/evolved RHS
comparisons across all four families, compact/padded and reordered named owners,
changed and bit-identical unchanged P. An independent source-only wrapper
reconstructs P by named-owner 80-digit division using raw source geometry and
component D, ignoring production slot maps/runtime layout. It then evaluates
the previously qualified complete ordinary oracles with the explicit held
packet. No production mapping, RHS or check is called by that reference.

Maximum complete RHS error/budget: `0.003802780170869254`.
Fixed rate budget: 3e-12 absolute +3e-10 relative (3e-23 for charge rates),
potential 3e-13 V, rate-energy 1e-10 pJ/s. No acceptance budget changed.
Raw definitions, complete fields/controls/D, binding provenance, actual and
expected full rates/potentials, signed errors and budgets are in `evidence/`.

A separate fresh process replayed all 32 actual independent RHS cases with
both import mechanisms denying Cells/JAX; no production modules were loaded.
Its maximum replay error/budget was 0.0. This independence check does not add
32 extra counted host test cases or a trajectory claim.

Refusals cover mismatched source/geometry/owner/anchor/channel/P parameters,
state/control shape/precision/domain, foreign component streams, invalid
component P and steps, actual gross passive transfer, and the explicit zero-P
history limitation. Other checks preserve active channels/pumps at initial
zero passive P, original inputs/flags/RNG/clocks, signed scheduled values,
independent component clocks and all immutable outputs. No-draw/finalization/
advance guards and changed neutral protein buffers leave every rate unchanged.

## Receipt and resources

`/mnt/workspaces/Cells/physiology-permeability-view-tests-20261030-01/result.json`
SHA256: `a1408a9a551e9b355bd5a4dcf5862826f5203d306a5661594100e29b97306db7`.
`inputs.json` and `driver.py` retain exact commands, environment, versions and
captured private source; JUnit, stderr/stdout, raw arrays and host-resource
samples remain alongside. All captured sources and the 3 owned sources stayed
unchanged. All 14 protected ATP/binding/cut sources remained exact.

CPU7, one thread, <=480 s/command, <=1 GiB process-tree RSS and >=8 GiB host
reserve. Peak RSS was 239206400 B; fresh reference took 2.52 s /84074496 B.
No GPU, long numerical job, campaign poll, temporal-noise policy, coupled
solver execution or checkpoint rewrite was invoked. This qualifies the
explicit ordinary RHS view, not a complete physiological simulation.

## Frozen sources

| Source | SHA256 |
| --- | --- |
| `src/cells/models/physiology_permeability_view.py` | `a696c2cc795020d2069347c0034094cf7569c2923e8c32302a06f2b6f6decc18` |
| `validation/tissue/physiology_permeability_view_reference.py` | `11dbb6234401346959869e0b3b1d8104b315bf0f70659fe9044b065aab8eaea1` |
| `tests/unit/test_physiology_permeability_view.py` | `8575cbde3863c26b5fb0d390cb9de7bd8a82c75e383266ec2c121545e1dd9948` |
