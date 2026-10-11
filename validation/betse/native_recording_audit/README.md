# Independent offline codec review

2026-09-17, D124 / REF-005d R0. Review the completed D123 conversion with a
separately implemented decoder and a direct comparison against the originals.
This is software/evidence independence, not a claim of a different research team.

The converter reports all 36 rows exact in **215.987 s**, covering 6,720 observed
updates and 20,196 stream records. Native JSON files total **1,509,951,698 bytes**;
new streams total **18,070,684 bytes**: **83.558× smaller / 98.803% less storage**.
These are measured evidence-storage figures, not faster numerical integration.
All converter artifacts and frozen sources remain unchanged.

## What is independently checked

- Decode every CNRS@1 byte using a new cursor parser and standard-library
  float64 vectors, not the producer's `record_codec` implementation.
- Check deterministic directory membership, chunk/frame lengths, compression
  limits, both byte digests, the append-only index chain, terminal manifest,
  version and exact complete record counts. Partial iteration is not a pass.
- Compare every original nested value directly: identical JSON type, identical
  dictionary keys/list lengths, and **identical float64 bits**, including signed
  zero. No numerical tolerance, coercion or producer round-trip digest substitutes
  for this comparison.
- Independently account for root/trace/history field coverage. Compare the
  number of matched primitive values with a separate traversal of the entire
  original tree; an unhandled field is an error, not a permitted omission.
- Recompute byte digests of all nine histories and fourteen endpoint arrays per
  row; retain the original dtype/shape metadata, raw calls, clocks and lifecycle
  fields. Native pickle paths stay data; existing prerequisite evidence binds
  the pickle files without loading them or claiming native restart support.
- Recompute storage/buffer sizes from actual streams, check saved row-report
  links and aggregate producer measurements, and reauthenticate the accepted
  numerical pilot plus its original rejection history.

The reviewer imports no producer serializer, partitioner, compatibility decoder,
converter job, simulator or array framework. An import fence enforces that
boundary. Existing read-only source/authentication helpers are reused, not
physical-law evaluators. No BETSE, Cells, reference ODE or high-precision energy
calculation is rerun by this review.

The original JSON row is still materialized one at a time. The new stream reader
retains a bounded chunk and current decoded value, not a rebuilt trajectory or
horizon-length index. This is **not** a demonstration of bounded live BETSE
memory. Tests exercise reader release with cyclic GC disabled, while the job
records its own RSS separately from the converter's source-bound RSS report.

## Scope, prerequisites and result

Input: `runs/ref-005d-offline-codec-2026-09-17/qualification-01`.

Registration SHA-256:
`092cd7db7dc3dd9d7d1378607a67ecf16687b249bdded1765eaeceef75529847`.
Completion SHA-256:
`9e5ea291c711deb6edbd6c674c8a7aaff033b932f4c8ef9388db40a4637fe379`.

Authenticate all **778 sealed payloads**, the four operational files, fourteen
converter/helper/contract inputs, the 132-test receipt, final resource probe,
and the full original evidence chain. Bind that exact inventory into a fresh
review registration, along with review code, tests and handoff.

The matrix is the same six controls × three native grids × two modes: **36 rows,
6,720 observed updates, 13,404 history samples and 20,196 stream records**. Each
row receives a durable review report. Success requires every row and all final
source/resource/coverage checks, not just the largest-row preflight.

The passing preflight software receipt is linked from the
[handoff](../../../reports/REF005D_CODEC_AUDIT_HANDOFF.md). Tests include manually
constructed wire fixtures, adversarial/torn/resealed streams, signed-zero and
type mutations, unknown/omitted fields, all six real controls in both modes,
one complete real 640-update pump+leak row, source/import guards and detached
controller failure behavior. No producer encoder generates the wire fixtures.

**133 checks pass in 52.34 s**; the final receipt is
[`ref-005d-codec-audit-checks-02.xml`](../../../reports/ref-005d-codec-audit-checks-02.xml),
SHA-256 `808895f7f6df01981312241077e75f1c568595496c2b4ff6e6c2591e2ac2d8fd`.
The earlier 120-check receipt is preserved; the final suite adds independent
array-digest failures and terminal matrix/resource/controller checks.

One detached review is bounded to **CPUs 0–3 / 600 s / 4 GiB address space /
4 MiB per output file / 32 MiB aggregate**, with a 1 GiB free-disk reserve.
The controller receives the registration digest from its launcher, preserves
partial reports/failure evidence, and never polls, retries or launches another
job. Use fresh output and receipt paths; never overwrite frozen evidence.

Launch the prepared review once (the named destination must still be absent):

```bash
.venv/bin/python -B validation/betse/native_recording_audit/codec_audit_job.py launch \
  runs/ref-005d-codec-audit-2026-09-17/audit-01 \
  --tests reports/ref-005d-codec-audit-checks-02.xml
```

A passing terminal status would be
`offline_lossless_recording_independently_closed`. It closes **only the offline
codec sub-gate**, not all of R0, live observer neutrality, bounded native process
memory, matched Cells window/restart behavior or a longer trajectory.

After user-requested status and closeout, separately prepare the same-1 ms live
observer replay and matched Cells window/restart checks. A new 10 ms reference/
resource scope follows those gates. Biological validation, broader BETSE feature
coverage, release promotion and GPU/organ-scale execution remain separate.
