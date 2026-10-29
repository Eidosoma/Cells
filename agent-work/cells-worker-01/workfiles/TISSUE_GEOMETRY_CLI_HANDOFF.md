# Public geometry preparation workflow

Cells Key Developer, 2026-10-29. New public module
`src/cells/tissue_geometry.py` exposes `python -m cells.tissue_geometry` with
`prepare REQUEST --output NEW`, `validate DIRECTORY` and
`replay PROVENANCE --output NEW`. The complete request/provenance contract is
the frozen geometry component's contract; no extra physical inputs or inferred
owners are introduced. Public helpers are `read_json`, `prepare_request`,
`replay` and `read_preparation`.

`docs/TISSUE_GEOMETRY.md` is the concise user guide. The portable repository
example is `examples/tissue_geometry/irregular_native_radial.request.json`, an
exact copy of passed component evidence. It embeds the native capture, geometry
specs, generation inputs/RNG and source/runtime identities, plus all explicit
physical inventories, volumes, charge, constitutive coefficients and controls.
It requires no native installation or external capture path for replay.

Strict parsing refuses duplicate JSON fields at every nesting level, NaN,
infinities and overflowed literals. Validation reads both saved files strictly,
replays the full recipe, and compares complete JSON identities. Consequently a
boolean replacing integer 1, or a float replacing an integer capacity, cannot
pass through Python's numeric equality. Prepared output definitions and state
match the component evidence exactly. Existing directories, files and dangling
symlinks are refused before reading/evaluating input. Errors return code 2 on
stderr; successful output is JSON. Serialization still uses the qualified
component's non-overwriting two-file writer.

The shared dispatch change is **unapplied**:
`agent-work/cells-worker-01/workfiles/tissue_geometry_cli_dispatch.patch`.
Its metadata records base/patched/patch hashes. It adds one help entry and an
early delegation for `python -m cells tissue-geometry`. The check applies it
only to an isolated temporary copy, verifies its exact patched hash, checks
help and uses a fresh process to validate through that entry. Root owns applying
the patch. Shared dispatch and PROGRESS.md were not edited.

The frozen geometry handoff remains
`/mnt/workspaces/Cells/geometry-tissue-preparation-handoff-20261029-01/result.json`,
SHA256 `7259b548229f637c5e90889276119ad7cccbb422f5e4ae35a5c20bd8d2dfeba2`.
Its 56 component checks are reused rather than rerun. Fourteen frozen geometry/
physical source identities and the exact example file hashes are checked.

Public qualification:
`/mnt/workspaces/Cells/tissue-geometry-cli-development-20261029-02/result.json`.
All **33 checks** passed. Four fresh processes prepare, validate a relocated
bundle, replay its provenance, then validate the replay. The original input and
output are removed first, and an audit hook refuses attempts to open original
external geometry evidence directories. Full definition/provenance and all
initial state arrays/dtypes match the qualified component. Additional checks
cover finite/duplicate JSON, malformed requests, resealed tampering, strict
reading of both files, JSON numeric types, nonoverwrite, helper purity and
isolated shared-dispatch integration. The earlier 31-check receipt remains
frozen; the final two checks cover exact JSON type preservation.

Guarded host time was 19.91 seconds (19.02 seconds pytest), CPU7, one thread,
JIT disabled. Peak sampled process-tree RSS was 382,615,552 bytes; minimum
available memory 18,179,772,416 bytes. Limits: 300 seconds, 1 GiB RSS and 8 GiB
reserve. No GPU, component science rerun, long job, native generation, new
physics, implicit renaming, detached-job polling or automatic follow-up.

The metadata-only finalizer packages the public-replayed example, exact request,
guide, patch/metadata and verified receipts. Final receipt:
`/mnt/workspaces/Cells/tissue-geometry-cli-handoff-20261029-01/result.json`.
