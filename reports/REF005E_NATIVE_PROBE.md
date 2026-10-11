# 10 ms pump–leak: focused review and native probe

2026-09-17. One user-authorized detached job, reusing the existing independent
arithmetic, recorder, decoder, trajectory checks and process-group runner.
No production, physics or scientific-tolerance change; no new full campaign.

The preceding reference study passed all eighteen solves in **53.065 s**.
Its completion is `3a7710f88c309b16c2cca9739282801fc2b3b9bad8bf61253add4c816404d29c`.

## What this job checks

1. Review all eighteen saved references: solver and 1 ms prefix agreement;
   domains and charge-derived voltage on every dense/accepted state; existing
   independent 60-digit material/charge/energy arithmetic at every accepted
   endpoint and the 41 common observations. This does not independently check
   energy at every interpolated dense state or recompute endpoint rates.
2. Only after that passes, capture **four native BETSE runs** of the unchanged
   seven-cell pump–leak preparation: observed **6.25 / 3.125 / 1.5625 µs** steps
   over **10 ms**, plus the finest-step storage-only observer partner.
3. Check exact physical 1 ms prefixes, observer neutrality, reference errors,
   material/charge/energy accounting and successive error contraction. Raw
   native sample labels change with horizon and are not physical elapsed time.
   Keep all numerical misses visible; the finest energy limit remains **1e-7 pJ**.

This measures whether the main-case ladder is adequate, not six-control parity,
biological realism or equilibrium. Structural/domain failures stop the job;
numerical misses are retained as diagnostic results. No automatic retry or
subsequent campaign. No Cells run or new reference integration.

## Evidence and launch

- **27 software checks pass / 9.15 s**; source-bound execution **10.641 s**.
  Software packet: `runs/ref-005e-native-probe-2026-09-17/software-01`.
  Completion: `8c1c9a1a44a71129967540265cc20010aef728c0488e71760ec5de23861dd31f`.
- Launched **20:52:08 UTC**, PID **3536706**, at
  `runs/ref-005e-native-probe-2026-09-17/probe-01`.
  Registration: `c7ab26e3fdde3d9a46471508b20f7275b0622d0ef72c859445bd464d7a31746a`.
- The registration/source archive binds **689 reused/new inputs**. Separate
  review, native and comparison logs/results and terminal completion/failure
  receipts preserve the evidence. **Launch acknowledgment only; no worker poll.**

Limits: CPUs 0–3, one BLAS thread, **180 s review / 900 s native / 600 s comparison /
1,800 s total**, 8 GiB per worker, 128 MiB per file, 512 MiB total new artifacts,
1 GiB free reserve. The recorder's existing 32 MiB per-stream cap remains.
Native histories are retained; comparison deliberately materializes one offline
row at a time under its memory cap. Neither path claims constant memory.

## Completed result and smaller-step follow-up

The probe completed at **21:04:02 UTC / 713.654 s**. Its 947 sealed payloads
authenticate. The saved-reference review passes; exact physical prefixes and
observer neutrality pass. At 1.5625 µs, the only failed comparison is native
energy closure: **3.65767315845e-7 pJ**, against **1e-7 pJ**. Error approximately
halves on each timestep halving. This supports timestep error as the working
explanation; it is not an independently reconstructed energy diagnosis.
Completion: `cd0c629469baa03d162b39a06a038701516d27dc97f0a3a78b64a8d8ad3c7414`.

On the user's instruction to fix this, reuse the completed reference review and
1.5625 µs comparison. Add **0.78125 and 0.390625 µs / 10 ms** observed runs,
a finest-step storage-only partner, and a **0.390625 µs / 1 ms** observed run
for exact physical-prefix checking. Four new runs / 66,560 native updates.
No cross-timestep bitwise-prefix promise is made. All scientific limits remain
unchanged. Linear error scaling predicts approximately **9.14e-8 pJ** at the
new finest step; that is a planning estimate, not an accepted result.

The previous finest observed stream used 15,568,066 compressed payload bytes;
a 4× refinement would exceed its old 32 MiB aggregate cap. The new adapter
selects **128 MiB per stream**, retaining the qualified codec, exact bits,
32-record / 8 MiB chunk bounds and all integrity checks. Only its writer
dependency and a private reader instance receive the aggregate-cap override;
the shared modules, frozen sources and both simulators remain unchanged.
The new offline comparison retains one row at a time under a **16 GiB** worker
cap; it is not constant-memory execution.

- **27 checks pass / 13.47 s**, including a **39,963,162-byte** exact round-trip,
  unchanged chunks/index bytes for saved native data, preserved chunk limits,
  unchanged preparations/tolerances and failure/detachment controls.
  Source-bound execution: 15.237 s; **693 inputs / 71 sealed software payloads**.
  The first packet's 19 passes / one assertion-message failure remain preserved;
  its larger-stream round-trip already passed. Only the expected rejection
  message was corrected; subsequent tests also cover resealed registration changes.
- Software: `runs/ref-005e-finer-native-2026-09-17/software-02/completion.json`;
  SHA-256 `f01fcac7012e629a7b5cdff86c82c73c58cfef2f9cc57ee0ccb5bb8a43cdbd8f`.
- Launched detached **22:06:20 UTC**, PID **3548348**, at
  `runs/ref-005e-finer-native-2026-09-17/refinement-01`;
  registration `71e7cfebc0a933f569e8bee4c7913ab509dfdbcc482120b63487e46115d42f10`.

Caps: CPUs 0–3, one BLAS thread; **3,000 s native / 1,200 s comparison /
4,500 s total**, 16 GiB per worker, 128 MiB per file, 512 MiB new artifacts,
1 GiB free reserve. These are limits, not an ETA. Old results remain unchanged.
**Launch acknowledgment only: no worker polling, automatic retry, full
six-control campaign or Cells run. The proposed numerical fix is not yet verified.**
