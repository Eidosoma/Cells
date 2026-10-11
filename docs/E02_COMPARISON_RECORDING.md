# E02 lossless reference-backed comparison records

D040 / NUM-005c2d, 2026-09-09. The user approved the next bounded prototype after
[D039](../reports/NUM005C2C_LOSSLESS_EVIDENCE.md). Remove repeated comparison
states from storage, not samples, state coordinates, scientific checks or
restart carries. Production, numerical kernels and all original limits stay fixed.

## Representation and dependency contract

Select `full_samples` or `trajectory_backed` per comparison recorder. Both use
the unchanged D039 runner with `rk4_basis` trajectory recording and D038 cached
readouts. Recording policies remain separate from numerical model identity.

| Policy | Comparison payload | Logical evidence |
| --- | --- | --- |
| `full_samples` | All times, observer flags and four complete sampled states | Full D039 comparison arrays |
| `trajectory_backed` | Every time and observer flag | The same arrays reconstructed from retained candidate and reference trajectories |

Retain per-input state hashes, the combined logical-array hash, all six-field
readout fingerprints and complete sample counts. Before publishing compact
records, reconstruct from the already-written candidate window and separately
held immutable reference readers and require bit-exact logical arrays. No RHS
replay, quantization, rounding, thinning, coordinate omission or fallback.

An exclusive dependency manifest pins the candidate attempt, selected reference
case/method/numerical settings, reference case/report/index hashes, codec/source
identity and runtime. Verify all referenced trajectory payload hashes and their
availability before opening reconstruction readers. Each sample-index record
binds the manifest hash and candidate window payload/logical identity. Candidate
commits bind the comparison-index prefix afterwards; this avoids a circular
commit hash while preserving the D039 publication boundary.

Paths are explicit local absolute dependencies, not portable embedded copies.
Reject symlinks/hardlinks, changed/missing dependencies, incompatible selected
inputs, changed runtime/source, malformed inventory, nonfinite arrays and wrong
precision. Bound JSON lines, JSON manifests, ZIP/NPY inventories and numerical
working arrays before loading. Metadata and dependency-tree checks are not
constant-cost claims; measure them rather than hiding them.

## Closure, restart and failure

Reuse D039's payload-before-comparison-before-commit order and complete endpoint
checkpoints. The logical comparison evidence is not reduced; the D039 recorder's
`comparison_evidence_reduced: false` continues to describe logical coverage,
while the separate comparison-storage receipt describes encoded bytes.

New comparison readers and the explicit dependency-aware restart entry point
accept only a verified closed committed prefix. Validate reconstruction
dependencies even when a complete numerical carry could otherwise be loaded.
Older low-level D039 readers do not understand the new dependency semantics and
are not the D040 restart API. Cross-policy and window-width changes are allowed
under identical numerical identity and complete verified state.

Do not retry failed writes, overwrite partial evidence or promote uncommitted
comparison files. Failed closed prefixes may retain later diagnostic files;
successful closures must account for the complete index. Missing closure and
malformed candidate commit tails remain refusals. D039's independent emergency
preservation remains unchanged; no general process-kill recovery, distributed
transaction or power-loss guarantee is added.

## Tests and registered measurements

Test exact full/backed arrays, observer clocks, complete passive histories,
all graph layouts, bounded headers and allocations, dependency corruption and
removal, mismatched methods/context/source, forged or reordered index records,
closed-prefix restart and both policy transitions. Verify independent decoding
with the writer's decoder/sampler disabled. Exercise comparison failures before
commit and independent D039 preservation without changing numerical tolerances.

Freeze implementation, tests and the [profile inventory](../configs/reference/e02_comparison_profiles_v1.json)
before twelve sequential short CPU float64 profiles: full then backed for the
same six D039 inputs, 0–5.12 nominal units, step 0.01 and width 256. Reuse the
same immutable reference selections and D039 basis trajectory policy. No new
long references, long candidate run, refinement or automatic retry.

Keep CPU affinity 0–3 and all four numerical-library thread counts at 1.
Original limits remain 900 seconds/worker, 3600/session and independent audit,
one million global steps, 256 MiB estimated arrays and 1 GiB aggregate artifacts.
All prior roots occupy 821,019,434 bytes, leaving 252,722,390 for one new root
under `runs/num-005c2d-2026-09-09/`. Keep the existing 4 MiB emergency reserve.
Include additional reconstruction/reference buffers in aggregate preallocation
checks. Report process RSS separately from estimated numerical arrays.

The read-only auditor uses independently written reconstruction, checks the
full logical arrays, reference dependency identity, whole trajectories, grids,
scalar readouts and all eight comparison scores, and requires exact ordered
trajectory/sample hashes against D039. It does not independently recompute every
constitutive integration slope or establish interval-certified ODE bounds.

Measure full checked and offline audit costs, actual compressed bytes and logical
versus encoded arrays, dependency validation and reconstruction costs, checkpoints
and metadata. Single short observations and rate extrapolations are not long
measurements, statistical speed guarantees or a resource-fit certificate.
No compact long-study policy, timestep selection, production/GPU/organ change or
budget extension follows automatically from a successful prototype.

## Entry points and registered commands

The explicit reference API is `tests.reference_comparison_evidence.Comparison`,
`integrate`, `chunks` and `load_checkpoint`. Callers supply the reference mapping,
selected case/numerics, output root and storage policy. Readers stream logical
arrays; the audit supplies its own sample and RK4-basis reconstruction functions.
There is no production storage-schema migration or dependency relocation API.

Use the pinned `.venv`, affinity 0–3, and `OPENBLAS_NUM_THREADS`,
`OMP_NUM_THREADS`, `MKL_NUM_THREADS`, `NUMEXPR_NUM_THREADS` all set to `1`.
Outputs are exclusive; do not reopen or rerun a closed profile session.

```bash
taskset -c 0-3 .venv/bin/python scripts/profile_comparison_evidence.py --run --output runs/num-005c2d-2026-09-09/comparison-01
taskset -c 0-3 .venv/bin/python scripts/audit_comparison_evidence.py runs/num-005c2d-2026-09-09/comparison-01 --output reports/num-005c2d-audit.json
```
