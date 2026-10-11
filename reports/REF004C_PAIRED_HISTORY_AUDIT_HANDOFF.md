# REF-004c / D100 paired-history audit: prelaunch handoff

2026-09-15. The user reviewed the [D099 capture pass](REF004C_PAIRED_HISTORY_CAPTURE.md)
and requested independent closeout. This handoff records implementation and
software evidence, not an actual audit completion or new trajectory result.

## Scope and independence

The [audit contract](../docs/BETSE_CHANNEL_HISTORY_CLOSEOUT.md) and
[fixed plan](../validation/betse/channel_history_audit/plan.json) retain the
complete 291-file paired capture, 143 original source inputs, all old failures
and the original pending-audit receipt. Production stays unchanged: 352 accepted
implementation files / 51 production modules. No dependencies were installed.

Frozen comparator replay is accompanied by independently reconstructed numerical
columns, with native identities streamed and checked for complete coverage.
Both initial histories remain explicit; independently check full physical
preparation, gate settings, full Cells state, reference coordinates/readouts,
all eight refinement decisions and all six signed a-minus-b comparisons.
Retain all **21 coarse misses**, fourteen for a and seven for b.

Reference reconstruction cross-checks the two existing separately audited
mathematical formulations. It is not a new independent integration algorithm.
Checkpoint verification adds a separate raw-payload route to the capture's
older value-level decoder: independently pack full saved state, validate canonical
definition/clock/source identity, and link layout bytes to the D098-authenticated
preparation. All **24 checkpoints / 1,296 arrays** are in scope. Native pickles
are hash-bound but never loaded, and native restart is not qualified.

## Software receipts

- Attempt 01: **29 passed / 99 setup errors in 9.82 s**. A single common setup
  failure came from hashing the input definition instead of the canonical
  checkpoint definition. Python numeric equality hid the `0` versus `0.0`
  serialization difference. The new auditor was corrected; no checkpoint,
  simulator, scientific input or error budget changed. XML SHA-256
  `d0e9430e0278afbf87117986ff1ae938239ffbded15f36fc9c07d46798cb44da`.
- Attempt 02: **128 passed in 15.64 s**. XML SHA-256
  `1c7b478734b191a04fd12a39760e02ab8126e14746c48093e093023db4e4f718`.
- Attempt 03: expanded full-reference replay tests reached the **55-second
  foreground limit**, exit 124, before writing a completed XML. Retain the
  [timeout record](ref-004c-history-audit-checks-03-timeout.json), SHA-256
  `fc8633d25dbfcb54c53e751ac7cb2ef675357b7a5418914095101be83ddf3dfb`.
  This is not a numerical acceptance or rejection. Full reference replay stays
  in the detached audit; only the quick software replay fixture was bounded.
- Attempt 04: **137 passed in 16.56 s**. [Final XML](ref-004c-history-audit-checks-04.xml),
  SHA-256 `66765deaee3e826fc4fc70c519cace4e395495ec6c73cadc2fbbb71723fd9de3`.
  Tests check actual saved reference metadata and alternate mathematics,
  both complete Cells histories/definitions, all 24 checkpoint preparations,
  native first-boundary/fresh-probe slices, both three-observation reference
  replay fixtures and all six full contrast groups. Canonical-hash, corruption,
  forbidden-import/write, omitted/duplicate-identity and changed-budget controls
  pass. Native saved points in routing-only fixtures are explicitly labelled;
  complete native mathematical reconstruction belongs to the full audit.

No numerical integration ran in these checks. The original 56-test capture
receipt remains authenticated, not rerun. Repository lint, formatting and
whitespace checks are recorded in the progress log before launch.

## Frozen launch

Register a **152-input source capsule**, complete capture hashes, original
software/handoff receipts, all audit attempts above and the final passing XML.
After registration, freeze these new audit sources and reports too; corrections
must use a new version, not edit completed evidence in place.

One detached audit, CPUs 0–3, **900 seconds total / 256 MiB aggregate artifacts /
128 MiB per file and decoded record**. Artifact limits are not RAM caps. Durable
stdout/stderr, `started.json`, and exclusive `completion.json` or `failure.json`
establish actual execution state.

Launch once from the Cells root, with the destination absent:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -B \
  validation/betse/channel_history_audit/history_audit_job.py launch \
  runs/ref-004c-paired-history-audit-2026-09-15/audit-01 \
  --tests reports/ref-004c-history-audit-checks-04.xml
```

Return after launch without polling. No simulator/reference rerun, automatic
retry, follow-up regression, intervention, physiology expansion or GPU job.
Successful software checks do not replace the actual audit's complete identity
reconstruction. A passing closeout qualifies only the registered 2 ms paired
numerical scope, not biological memory, broad BETSE parity or organ-scale accuracy.
