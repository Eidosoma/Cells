# Explicit physiology/tissue ownership and unit binding

Chief-assigned two-file host adapter, qualified on CPU7 on 2026-10-30.
Both scientific sources are frozen. Machine-readable status, failed evidence,
resource records and hashes: [workqueue](physiology_tissue_binding_workqueue.json).
Chief owns shared checkpoint integration, repository documentation and PROGRESS.

## API

Import `cells.core.physiology_tissue_binding`.

`bind_tissue(spec, *, cell_ids, membrane_ids, environment_ids, ion_ids,
membrane_thickness_m, boundary_cell_occurrences, provenance)` returns frozen
`TissueBinding`. Its `.component` is a qualified `betse_perturbations.Binding`.
Every component axis must be a complete explicit permutation of the actual
ordinary tissue ID set. Original tissue declarations define physical slot
order; the four immutable `*_to_tissue` arrays map component order to those
slots. IDs are never inferred from positions or sorted to guess ownership.

Supported exact model types/identities:

| Model | Identity |
| --- | --- |
| `SurfaceTissueModel` | `resolved_tissue@1` |
| `SurfaceHCNExtraModel` | `resolved_tissue@12` |
| `SurfaceCalciumHCNExtraModel` | `resolved_calcium@11` |
| `SurfaceCalciumEnergyHCNExtraModel` | `resolved_calcium_energy@5` |

Subclasses, extended transport/cut/bath/water models and alternate precision
are refused. Matrix mode is the only mode in this version.

`membrane_thickness_m` is a complete membrane-ID -> positive finite metres
mapping. No capacitance, area or diffusion value is used to invent thickness.
The boundary occurrence list names actual cells, with order and duplicates
retaining native categorical weights. Caller provenance must be an explicit
nonempty JSON dictionary and is copied into immutable canonical storage.

`initial_diffusion(binding)` gathers declared membrane permeability from
`binding.initial_permeability_m_s` and returns immutable component-order
`D_m2_s = P_m_s * thickness_m`.
`permeability_to_diffusion(P, binding, scheduled=False)` accepts the complete
physical tissue-ion x padded-membrane array. Physical inactive padding must be
exactly zero. Negative P is allowed only with explicit `scheduled=True`.

`diffusion_to_permeability(diffusion, binding)` maps a complete native
`StaticState(current_m2_s, base_m2_s, scheduled_m2_s)` back to immutable
`PhysicalPermeability(current_m_s, base_m_s, scheduled_m_s, binding_identity)`
in physical tissue order and preserves zero inactive slots. Current/base must
be finite and nonnegative; scheduled values remain finite and signed.
Overflow and nonzero-to-zero underflow refuse instead of clipping.

`component_permeability(state, binding)` first validates all six complete
component buffers, its qualified stream identity and independent clocks,
then maps those three diffusion buffers. It does not finalize SIM schedules,
advance the component, draw, or change the deterministic layout. In particular,
current need not equal base+scheduled before an explicit caller-owned
finalization. Protein buffers never become ionic charge or another inventory.

## Actual geometry and immutable replay

Membrane areas come from actual named physical membranes in m2. Cell and
exterior pL volumes are converted to m3 with the declared factor 1e-15. Native
matrix mode has a single exterior-volume parameter: all actual exterior
volumes must match exactly, including the original pL declarations. Distinct
volumes that could collide after floating conversion still refuse. There is
no averaging, inferred effective geometry or heterogeneous-volume approximation.
Existing default fixtures with heterogeneous exteriors therefore refuse; the
positive unit fixtures explicitly redeclare uniform volumes.

Every exposed map, geometry/kernel array, thickness and result buffer has an
immutable bytes owner. Caller arrays/provenance and mutable exported records
cannot modify the bound object. The record seals the complete serialized
ordinary definition hash, explicit owner axes/maps, actual SI geometry,
initial P, thickness, boundary occurrences, caller provenance and qualified
component identity. No random stream or component clock is embedded here.

`binding_record(binding)` returns fresh JSON provenance.
`restore_binding(record, spec)` rebuilds the binding from the caller's actual
exact definition and explicit declaration, then requires the entire record to
match. Cached geometry/maps/unit/source claims remain checked even when a
caller reseals a malformed record's identity. `validate_binding` checks the
live immutable object and qualified native binding without drawing.

This supports Chief's optional bound checkpoint format. The outer snapshot
must still own the complete component, all six buffers, RNG/cache and its own
clocks. Caller code explicitly supplies the binding; this module chooses no
solver-boundary timing and performs no physical layout update.

## Evidence and limits

All 75 focused host cases pass in 4.531 s; peak process-tree RSS 198729728 B.
CPU7 only, one thread, <=180 s, <=1 GiB RSS and >=8 GiB host reserve. CPU-only
JAX imports are permitted through established model parsers; no GPU or full
physiology run, automatic draw/timing or protein-charge coupling was invoked.

Checks include all four exact model classes, compact/padded slots, component
and physical declaration permutations, independent 80-digit Decimal unit and
protein amount calculations, duplicate boundary weights, signed schedule
roundtrips, immutable arrays/exports, no-draw/no-finalization guards, foreign
spec/stream refusal, malformed/resealed replay, SI underflow/overflow, invalid
current/base domains, heterogeneous volumes (including one ULP), bad owner
axes and unclaimed padding. Initial P values differ per ion and membrane so
neither axis can be swapped unnoticed. Protein membrane concentration views
are not another stock or charge.

Attempt 01 preserved 63 passes and one failure: a new aggregate protein
assertion demanded absolute residual <=1e-38 mol, below double roundoff for
~1e-20 mol flux amounts. Actual residual was 1.504632769052528e-36 mol. The
unit now uses the unchanged component 3e-13 relative-gross conservation
contract. Independent per-owner Decimal comparisons remain at 3e-15 relative.
No binding/RNG/physical code changed between attempts. Attempt 02 also adds
explicit malformed JSON replay and inverse-buffer domain checks.

Receipt: `/mnt/workspaces/Cells/physiology-tissue-binding-tests-20261030-02/result.json`
SHA256: `75355c0cb7fec463be1175ce793eaac1156ebff65ae4997947b85a464f01e033`.
`inputs.json`, `driver.py`, retained source, raw named-owner/Decimal arrays,
JUnit, child stdout/stderr and host-resource samples remain beside it. All
captured source hashes were unchanged. Frozen previous physiological and ATP
sources remained exact; failed evidence was preserved.

## Frozen sources

| Source | SHA256 |
| --- | --- |
| `src/cells/core/physiology_tissue_binding.py` | `cb12e7f8d6b2aba651fe2d5644addda1a820db0490eea805a66bdf7dcca8ca5c` |
| `tests/unit/test_physiology_tissue_binding.py` | `6353ca6750a9d3137db76d787977ac1810c76eb77f2caaae488c8b0653a7d41e` |
