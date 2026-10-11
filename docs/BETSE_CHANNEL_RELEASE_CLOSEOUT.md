# D106 — Independent timed block/release audit

This is a saved-data audit of the D105 seven-cell, finite shared-bath Kv1p5
capture, not another simulation. It cannot establish biological validity, broad
BETSE feature parity, native restart support, or GPU performance.

## Fixed scope

Two gate histories (a: m=0.2/h=0.6; b: m=0.6/h=0.2), four availability
conditions (baseline, no-op switch metadata, static block, block/release), 2 ms.
Block at 0.5 ms; release at 1 ms. Positive intrinsic permeability is retained in
every condition. The intervention is a held input, not a state reset.

Target: `runs/ref-004d-timed-release-2026-09-16/capture-01`.
Completion SHA-256:
`355a5709eb30460f4734ecb6ea3d9e391d0b7102fdfdb4211d0f411e4083b6a6`.
The 555-file packet and its 194 source inputs remain immutable.

## Independent checks

- Reconstruct both columns of every numerical ledger: 15,042,946 identities in
  182 groups, including 14,772,920 native boundary comparisons.
- Reconstruct native gates, flux, current, charge, all accepted stage states,
  geometry/array bindings, 24 observer pairs, input application and restoration.
- Independently reproduce the six ordered pre-channel voltage nonce additions
  and the pinned 30-face NumPy reduction using exact rational intermediates
  rounded to binary64 at each arithmetic operation. Preserve 28,280 zero-flux
  means and all 3,265 original identity-guard diagnostics. No tolerance relaxation.
- Reconstruct full Cells state, padding, ownership, and both switch-side RHS
  arrays. Verify 8 eager/JIT pairs, 8 restart pairs, and every byte of 48 numeric
  checkpoints (2,592 arrays), including the right-continuous control-event clock.
- Recompute the 16 refinement decisions and 12 history-contrast groups. Preserve
  all 49 coarse-grid misses (35 a / 14 b); finest-grid qualification does not
  imply coarse-grid accuracy.
- Authenticate the already closed D105 review of D104's reference. Do not rerun
  its 1,485,380 identities or integrate a new reference. Reconstruct the sample
  and side readouts needed here and the saved cross-solver error floors.

Independence means alternate arithmetic/assembly and raw-byte decoding plus a
frozen-checker replay. This reuses previously audited independent mathematical
helpers; it is not a third independently authored solver or external execution
attestation. Structural checks and hash provenance supplement numeric ledgers.

## Execution and evidence

All 116 bounded software checks pass in two disjoint batches (103 in 41.99 s;
13 in 43.13 s), using saved slices and corruption controls. Earlier receipts and
the 55-second foreground software timeout are retained. The full audit
runs detached on CPUs 0–3 with a 1,800-second deadline, 128 MiB/file and 256 MiB
aggregate artifact ceilings; these are disk limits, not a RAM restriction.
Sources and historical reports are bound before launch. Production remains
unchanged (352 accepted implementation files / 51 modules).

The controller forbids model-library imports and writes to either capture. It
writes durable `launch.json`, `started.json`, `audit.json` and a terminal
`completion.json` or `failure.json`. No polling, automatic retry or follow-up.
Failures do not qualify the pilot. Success closes only the explicitly registered
fixed numerical scope; all original receipts retain their original status.

## After a successful audit

Review the receipt when the user requests status, then select the next narrow
validation/design increment. Multi-ion electrodiffusion, explicit extracellular
spatial fields, additional channel/pump laws, and GPU/multiscale work remain
separate tasks. This audit does not authorize or launch them.
