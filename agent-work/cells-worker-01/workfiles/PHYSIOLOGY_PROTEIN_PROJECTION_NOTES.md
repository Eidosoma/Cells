# Explicit protein amount and charge projection

Chief owns the separate read-only field-response view and public/coupled work.
This worker owns only the new pure adapter, independent reference, unit tests
and these workfiles. Existing tissue/field/component/loop kernels stay frozen.

## Stable adapter contract

`cells.core.physiology_protein_projection.project(protein, binding, *, valence,
faraday_C_mol)` returns immutable `ProteinProjection` in physical tissue cell/
environment ID order, without padding. Inputs are a complete `ProteinState` and
the explicit existing `TissueBinding`. Values are amount mol/fmol and charge C
per owner, plus totals and the declared units/identity. Membrane concentrations
remain finite nonnegative buffers but contribute no separate inventory; they
can be stale views and can refresh without any stock or charge change.

`delta(reference_protein, current_protein, binding, *, valence, faraday_C_mol)`
returns immutable `ProteinDelta` with explicit baseline/current projections,
`cell_charge_delta_C`, `environment_charge_delta_C`, amount deltas, raw net/gross
balances and precision diagnostics. It calculates `(Ccurrent - Creference)*V`,
avoiding loss from subtracting two rounded absolute amounts. It neither rebases
the reference nor repairs/rescales a residual. Nonconservative changes return
false conservation flags and their actual arrays. Invalid/unrepresentable
conversion raises `ProteinProjectionError`, retaining raw output when formed.

Valence is one explicit finite scalar for this protein on both sides. Faraday
constant is explicit and positive. Pinned native source uses zP=-1 and F=96485;
the Cells field uses `electrochemistry.F = 6.02214076e23 * 1.602176634e-19`.
The read-only field view must pass its exact field constant; the adapter has
no default that conceals this difference.

Volumes are the actual declared component cell/exterior owner m3. Existing
calcium declarations require ionic and chemical cytosol volumes to coincide;
the adapter adds no ER/store volume or membrane-view volume. Physical source
IDs control reordering. A bare `ProteinState` has no independent provenance;
the caller declares its binding, and Chief's complete-component wrapper checks
the full ownership association before applying a field response.

## Conservation and representation

`strict_conservation_valid` keeps the existing 3e-13 gross amount tolerance and
its charge-scaled counterpart. The original component transfer law and its
acceptance bound are unchanged. Stored concentrations can lose part of a small
transfer through floating addition before this adapter sees them. For that
separate stock-difference quantity, `conservation_valid` also includes explicit
half-ULP input-stock resolution and exact floating projection error. The
adapter reports each bound and actual net residual, and
`storage_resolution_used` says whether stock resolution was needed.

Decimal arithmetic computes these diagnostic bounds from the actual float64
inputs at sufficient precision. Only bounds round outward; inventories and
charges are never changed. A resolution-compatible delta is not evidence of
strict exact material conservation. Chief's original stricter field closure
continues to decide whether a particular read-only charge response is admissible.
No field tolerance is widened to match a stock bound.

## Coupling questions deliberately outside this adapter

- Existing `initial_*_charge_C` anchors already declare total reference charge.
  A field response adds only an explicit reference/current protein delta.
  Absolute protein charge cannot be added again without a separately declared
  initial charge partition. No source inventories or anchors change here.
- A closed field may refuse a representation-compatible stock delta whose actual
  net charge misses the stricter charge closure. No charge balancing projection
  is provided. Live evolution may need a separately qualified conservative
  transfer ledger, charge ownership and cumulative reference policy.
- Protein charge feedback would affect fields, ionic fluxes, capacitor energy,
  electrical work and operator ordering. It requires a new coupled identity and
  energy/work bookkeeping, not an adapter or hidden kernel patch.
- Held ionic reservoirs/voltage clamps do not automatically create protein
  reservoirs. The adapter reports every actual exterior protein stock and does
  not discard it; future source/electrode policies must be explicit.
- Binding changes/cuts, changing protein valence, chemical binding states, native
  bulk clipping and other RNG sites remain separate declared operations.

Pinned source/anchor audit is in `physiology_protein_projection_source_audit.json`
(11 native files, including ion_current verified against the pinned git revision).
Qualification inputs, fixed tolerances, protected sources and receipts belong in
`physiology_protein_projection_workqueue.json`.

## Frozen qualification

All 44 unit/contract cases pass. They cover 16 four-family owner/layout cases,
explicit F/valence/units, zero-amplitude membrane-view refresh, one-ULP deltas,
nonconservative changes, original component transfer precision, malformed and
unrepresentable inputs, immutable results and forbidden evolution/RNG/field calls.
A fresh Cells/JAX-denied process replays the actual 16 named-owner cases in both
projection/delta forms (32 forms), exactly matching saved Decimal reference data.
Maximum per-owner relative error is 2.15316e-16 against the fixed 3e-15 bound.
No field, trajectory, native full-loop or live protein-feedback claim is added.

Receipt: `/mnt/workspaces/Cells/physiology-protein-projection-tests-20261030-01/result.json`,
SHA256 `5431811203ea5f72ebdff986217d50a3106ba9d25d2581b4db97ed440db3f12b`.
Unit/reference phases took 4.28/0.51 s, peak RSS 234803200/38219776 B, with host
reserve above 24 GB. Captured and current three owned sources stayed exact;
32 protected sources remain unchanged. All three new files are frozen; full
source hashes and raw outputs/failures/bounds are in the workqueue/receipt.

Chief separately reports 24 field-response cases plus 16 exact isolated field
comparisons/32 roots passing on the same `b90eb054...` core, with original field
closure and anchors unchanged. Its initial launch/reference failures are retained:
`/mnt/workspaces/Cells/physiology-protein-charge-view-20261030-03/completion-verification.json`.
Those read-only field results belong to Chief and are separate from this adapter's
owner/unit qualification. No active campaign was queried and no existing kernel,
public I/O or shared progress file was edited by this worker.
