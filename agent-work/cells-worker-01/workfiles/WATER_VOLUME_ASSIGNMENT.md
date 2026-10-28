# Assignment: water/volume model definition and configuration

Coordinator: Cells Chief Developer. Worker: Cells Key Developer. Same checkout;
no worktrees. Keep your status in your existing WORK_LOG.md, not PROGRESS.md.

## File ownership

You own only:

- `src/cells/core/surface_water_spec.py`
- `tests/unit/test_surface_water_spec.py`
- `configs/resolved_water_tissue.json`
- your existing `agent-work/cells-worker-01/` files

The coordinator owns the numerical kernel, production model, shared registry,
shared schedule/serialization dispatch, integrated numerical tests, qualification
protocol and PROGRESS.md. A separate reference agent owns
`validation/tissue/water_volume_reference.py`,
`validation/tissue/test_water_volume_reference.py` and
`docs/WATER_VOLUME_REFERENCE.md`. Do not modify those files.

## Definition contract

Implement a strict new `resolved_water@1` definition by extending the existing
`resolved_tissue@1` model. Reuse its named ionic owners, species, fixed interfaces,
capacitances, topology, execution and passive ionic schedules. Restrict outside
compartments to finite closed owners (`reservoir=false`). This first composition
adds water exchange across membranes only: no water routes along extracellular
faces or gap junctions, no solvent drag, changing shape or fluid velocity field.

Add `water_compartments` to the model, one entry for every cell and outside
owner, identified by `compartment_id`. Every entry explicitly contains:

- `reference_volume_pL` (positive; elastic reference)
- `minimum_volume_pL`, `maximum_volume_pL` (positive, strict bounds containing
  that owner's initial volume; also contain reference volume)
- `impermeant_amount_fmol` (nonnegative effective impermeant osmolyte count;
  independent of fixed-charge equivalents, never inferred from charge)
- `bulk_modulus_Pa` (nonnegative)
- `pressure_offset_Pa` (finite signed static elastic prestress)

Add `water_membranes`, exactly one entry per ionic membrane, identified by
`membrane_id`, with nonnegative `hydraulic_permeability_m_per_Pa_s`. Reuse each
ionic membrane's area and physical owners. Normalize entries to the existing
cell-then-outside order / membrane order, rejecting duplicates, missing entries,
extra entries, unknown fields, booleans masquerading as numbers and nonfinite
values. Reuse existing parser helpers and validations.

Add independent `water_controls` in the experiment, identified by membrane_id,
with the existing time/availability schedule format. The new Experiment's
changes must union membrane, junction and water boundaries with right-continuous
values. Define a Control NamedTuple with fields `membrane`, `junction`, `water`.
The coordinator will wire `control_values` into shared schedule.py.

Use dataclass names `WaterCompartment`, `WaterMembrane`, `SurfaceWaterModel`,
`Experiment`, `Change`, and `Execution` if an execution subclass is necessary.
Prefer retaining the existing execution type: fixed new conservation/energy
tolerances belong in the numerical implementation rather than user-adjustable
fields in this first version. Export `MODEL_ID`, `parse`, `to_dict`, `prior_spec`.
`prior_spec` must strip only water additions and preserve the original ionic
definition exactly. Parse tests may call this module directly until coordinator
dispatch wiring lands; do not patch shared registries yourself.

## Physical meaning (for schema/docs; do not implement production numerics)

`Pi=R*T*(sum(ion amounts)+impermeant amount)/V` Pa, with fmol/pL numerically mM
or mol/m^3. `P=K*(V/Vref-1)+P0` Pa. Water flow cell-to-outside is
`Q=1e15*area*Lp*((P-Pi)_cell-(P-Pi)_outside)` pL/s, multiplied by water
availability. Equal/opposite volume changes conserve water; water alone does
not change any ion amount or charge. Current volumes determine concentrations
at every coupled integration stage. Fixed interfaces with changing volumes are
a declared compliant-compartment approximation, not shape mechanics.

The new model is an independently specified Cells extension. The reference
agent found pinned BETSE computes osmotic pressures/velocities but leaves its
volume/dilution updates commented out. Do not claim native volume-trajectory
parity.

## Checks and resources

Create a small GPU-configured one-cell/one-finite-outside example based on the
existing resolved tissue fixtures. Include nonzero water permeability and an
off-grid block/release schedule independent of ionic controls. Test strict
ownership, ordering, bounds, roundtrip, prior reduction and union clocks.

CPU-only checks, affinity CPU 7, one BLAS thread, target <=1 GiB RSS. No GPU or
long qualification jobs; I coordinate those. Use the existing CPU venv with -B
and no pytest cache. Put outputs, temporary files and caches under a fresh
`/mnt/workspaces/Cells/water-volume-schema-20261028-*` directory. Follow AGENTS.md.
Preserve all failed evidence. Report exact modified paths, test results, any
interface questions and your readiness for integration directly to my thread.
