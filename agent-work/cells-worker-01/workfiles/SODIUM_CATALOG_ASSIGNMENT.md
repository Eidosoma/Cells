# Complete the pinned sodium-channel component catalog

Start after handing off the fixed-volume cotransport tissue code and short CPU
checks. The coordinator owns its water/finite-energy integration and shared
model hooks. New GPU qualifications are deferred by the user's instruction;
prioritize mechanisms and short CPU checks.

Own only these new paths, plus your worker log/workfiles:

- `src/cells/processes/sodium_catalog.py`
- `tests/unit/test_sodium_catalog.py`
- `validation/channels/sodium_catalog_reference.py`
- `validation/channels/sodium_catalog_protocol.json`, if needed for source captures
- `docs/SODIUM_CHANNEL_CATALOG.md`

Inspect pinned BETSE v1.5.0 commit
`5269a714aa2593ed2a6708c4516289977d8ae1a2`, `science/channels/vg_na.py`,
and the inherited update methods. Account for every concrete class in that file:
Nav1p2, Nav1p3, NavRat2, NavRat1, NavRat3, NaLeak and Nav1p6. Establish names,
units, gate exponents, initialization, voltage shifts, temperature assumptions,
domain and native discrete-clock semantics before assigning stable law IDs.
Keep the accepted NaV1.2 component unchanged; reuse it where scientifically
appropriate and check overlap exactly. Send the proposed public interface and
law IDs early so the coordinator can plan catalog integration.

Implement NumPy/JAX-compatible gate kinetics, opening and declared domains in
the new module, with explicit law and population axes and independent leading
world axes. Handle NaLeak and persistent/degenerate gates according to inspected
source, not guessed generic m/h behavior. Analytically regularize removable
singularities and retain strict errors outside physical/numerical domains; do
not silently clip or invent channel thermodynamics. Continuous-time rates and
native discrete updates remain distinct claims.

Use independent scalar/Decimal reference equations and a separately executed
pinned native source probe. Capture source revision/hash, exact inputs and
outputs; do not copy upstream implementation into this repository. Compare
ordinary voltages, singular/near-singular limits, gate domains, opening powers,
renamed population ordering, padding and multiworld behavior. Source singular
failures remain evidence, with regularized physical limits labelled separately.
Initial native agreement concerns selected component equations/initialization,
not all coupled tissue trajectories or biological parameter fitting.

Start with bounded CPU7 host checks, one BLAS thread, <=1 GiB charged memory,
>=8 GiB host reserve, and an expected duration below ten minutes. Prefer checks
of tens of seconds. Ask the coordinator before a small compiled CPU pass; no
GPU, broad sweep, long qualification or polling of existing jobs. Outputs,
native captures and failures go under `/mnt/workspaces/Cells`.

Do not edit existing sodium/channel catalogs, schema, model, shared status,
delivered cotransport or energy/water files. Report a concrete inherited bug to
the coordinator. Hand off working code, scope/source distinctions, evidence and
hashes; later tissue composition and batched GPU qualification are separate.
