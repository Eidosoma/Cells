# REF-004d: actual piecewise-reference capture

Recorded 2026-09-16 after the user-requested status check. The D104 job completed
2026-09-15 at **23:22:10 UTC**, in **160.675 s** (reference worker **88.462 s**).
Its status is `piecewise_reference_pass_pending_review`, not simulator-response
or biological qualification. No production implementation changed.

All **24 paths / 48 segment integrations** completed: two histories, four
conditions and three solver settings in the fixed 2 ms window, with 321 samples
per path. All **1,250,740 physical/reference comparisons** and **234,640 dense
replay comparisons** passed: **1,485,380 total, zero failures**. Maximum scaled
errors were 0.000191883 and 0.000179024 respectively. No worker warnings or
simulator imports were recorded.

Minimum signal across the three solver settings:

| Quantity | History a | History b | Required minimum |
| --- | ---: | ---: | ---: |
| Block effect at release, V | 0.0009282214 | 0.0007787969 | 0.00004002004 |
| Post-release voltage change, V | 0.0021110504 | 0.0015603759 | 0.00004002004 |
| Immediate release flux, fmol/s | 0.07087614 | 0.05648817 | 0.00020010004 |
| Gate change while blocked | 0.02661747 | 0.00501541 | 0.00040002004 |

The signed final a-minus-b diagnostics are approximately -0.604351 mV in voltage
and +0.0564564 in open fraction. Their sign was not an acceptance requirement;
they do not establish biological memory. Dense-domain probing is not a rigorous
all-times domain proof.

The 34-file packet, 182 source inputs, 19 bound reports and accepted production
source chain authenticate unchanged. This report records the saved result;
the new D105 independent numerical-column review is still a separate gate.

- Capture: `runs/ref-004d-release-reference-2026-09-15/reference-01`.
- Completion SHA-256: `ae670b6e1825c1677ccfd29d008b5036aca371ede5c83d1dba49d3bcc3d01b8f`.
- Registration SHA-256: `d5aa23c0dca9621c120fe73426d1efdec88a48da88b8b063cd1e2b1ca1ffc39e`.
- Gate SHA-256: `09d95d6cce4138817fc023bdb6a0d4077fd4ff9a6f98b13a54c39a9395f8edfc`.
- Worker aggregate SHA-256: `c4cc248351010e1097065c86ee0b107442920db3f4ac22a56d2d4eb0272ddec7`.

Original registration, software receipts and capture files are not rewritten.
The user has now authorized saved-reference review followed, only if that review
passes, by the [timed native/Cells comparison](../docs/BETSE_CHANNEL_TIMED_RELEASE.md).
