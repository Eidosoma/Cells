# Fixed-volume tissue cotransport

The coordinator owns water/energy composition, shared integration and full
qualification. You own a separate finite-energy tissue extension using the
delivered cotransport component. Keep all existing delivered files stable.

Own only these new files and your worker log/workfiles:

- `src/cells/core/surface_cotransport_spec.py`
- `src/cells/models/surface_cotransport.py`
- `configs/resolved_cotransport_tissue.json`
- `validation/tissue/surface_cotransport_fixtures.py`
- `validation/tissue/surface_cotransport_reference.py`
- `tests/unit/test_surface_cotransport_spec.py`
- `tests/unit/test_surface_cotransport.py`
- `docs/TISSUE_COTRANSPORT.md`

Propose and then implement `resolved_cotransport@1`, extending fixed-volume
`resolved_energy@1`. No water, ER, structural geometry changes or new ATP
reaction in cotransport. Declare routes explicitly by ID, owning membrane ID,
named manufactured law and cycle capacity; membrane ownership supplies both
compartments. Preserve arbitrary species order. Add an independent route
availability clock and explicit route capacity/padding. Project faithfully to
the finite-energy model. Send the public schema/control/state interface early
so the coordinator can wire shared registration, serialization, scheduling and
ensemble support; do not edit those shared files yourself.

Integrate signed route cycles, per-species route transfer and dissipated heat.
Scatter matching material into cell/outside state exactly once; cotransport
does not directly change capacitive charge. Reconstruct local conservation
using the additional transport ledger, and include heat exactly once in the
combined energy identity. Existing field/current checks must see live altered
ionic concentrations. Keep all finite ATP/regeneration and channel behavior.
Strict positive substrates must be checked even when a route is blocked.
Do not floor concentrations, reset pools or loosen existing tolerances.

Use an independent scalar/reference tissue RHS combining the delivered
independent energy and cotransport references, with explicit ownership and no
production imports. Initial checks should cover full-state stage agreement,
sealed/absent-route reduction, reversal/stall, repeated routes sharing a patch
or pool, reordered species, padding, independent clocks, corruption of local
ledgers and complete energy accounting. Include fixtures for later full
trajectories, refinement, replay/windows and independent worlds; the
coordinator owns that qualification and its protocol/execution tests.

Begin with source/interface review, implementation and bounded host/reference
checks on CPU7, one BLAS thread, <=1 GiB charged memory and >=8 GiB host
reserve. Ask for the resource handoff before compiled checks. All generated
outputs go under `/mnt/workspaces/Cells`. No GPU or long qualification launch,
no polling of existing runs, and no PROGRESS/shared-document edits. Preserve
failed evidence. Keep named tanh-law contracts and native BETSE generic source
probes distinct: this extension does not establish native named KCC/NKCC parity.
