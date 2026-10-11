# REF-005d R0: saved live outputs and expected window receipts independently closed

2026-09-17, D130 closeout of D125–D129. The independent review completed at
**17:20:12.570 UTC**, in **128.769 s**, with **zero failures**. This closes the
registered 1 ms recording/window scope, not biological validation or BETSE parity.

## Accepted evidence

- Native: 36 live streams, **54,685,116 exact scalar comparisons**, including
  54,512,738 float64 bit comparisons and 708,120 signed negative zeros. Eighteen
  observed/quiet pairs add **3,648,192** common-field comparisons.
- Coverage: 6,720 observed updates, 13,404 history samples, 20,196 stream records;
  324 history and 504 endpoint array digests independently reconstructed.
- Cells matrix: 24 baselines, 18 disk recordings, six saved full restart suffixes;
  expected-receipt reconstruction for 72 window runs, six restart windows,
  six zero-length and two sparse controls. A separate probe adds one baseline,
  three recordings, one full/window restart and one zero-length case.
- Direct saved Cells checks across both phases: **14,028 arrays / 284,103 values**.
  Unsaved trajectories are **not** described as directly inspected. Their
  assurance is through independently reconstructed expected checksums and the
  sealed producer comparison receipts.

All **66 sealed payloads / 70 regular files**, **21 reviewer/helper inputs**,
source capsules and the 97-test source-bound software receipt authenticate.
The complete D128 520-file/680-input context, 964-file native packet, 24-file
stopped continuation and earlier numerical/codec prerequisite chain remain
intact. The original two stopped producer attempts stay failed.

Reviewer peak RSS: **403,587,072 bytes / 384.89 MiB**. New review artifacts before
completion: **444,950 bytes**. These are reviewer measurements, not whole-native
bounded-memory or numerical speed claims. BETSE retains its own histories.

## Frozen identities

- D129 registration: `4b8cb8f0e4eb919c4930b40f2b7b8702ab8fd2bc96e45e39de6ca9d23da0eb55`.
- [D129 completion](../runs/ref-005d-live-audit-2026-09-17/audit-01/completion.json):
  `769994fac30ba99e64bc5c3f998c49e9d1c747c3a2e9bbeb5fadd2c57febb647`.
- D128 producer completion: `bb6448d1be688c1b3613e8580c3e365cc75a6a794fb6bab22f7fffa4612bf2c1`.
- D129 software completion: `66d8a0e4f7002171632adf3360929324af70d085859cbab8afaa1bc312005b92`.
- D129 97-test XML: `ac3a0d077500caff23bda9463877a88c809c1b12e61bdd2abd8e141de46d7316`.

The status is `live_recording_saved_outputs_and_receipts_independently_closed`.
Do not rewrite producer `pending_independent_review` records or any frozen source.
The source-bound D130 closeout command reauthenticates this packet and publishes
a separate machine-readable receipt without rerunning either simulator/audit.

## Next, separately scoped

The newly authorized [10 ms reference study](REF005E_REFERENCE_SCOPE_HANDOFF.md)
checks domains, accounting, reference agreement and the old physical prefix
before native timestep/resource selection and full matched execution. It does
not inherit a 10 ms acceptance stamp from this 1 ms closeout. Junction topology
and original biological methods remain separate [next gates](../docs/BETSE_NEXT_GATES.md).
