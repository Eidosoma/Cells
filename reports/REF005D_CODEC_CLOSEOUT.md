# REF-005d R0: offline recording independently closed

2026-09-17, D125 closeout of D123–D124. This closes **offline lossless evidence
recording only**, not the live observer, bounded native simulator memory, a
longer trajectory, biological validation or GPU execution.

The separate decoder/direct-value review finished at **13:20:14.534 UTC**, in
**191.565 seconds**, with status `offline_lossless_recording_independently_closed`.
It compared all **36 rows / 54,685,116 original scalar values**, with **zero
failed comparisons**. All **54,512,738 float64 bit comparisons**, including
**708,120 negative-zero values**, agree. Every original primitive is covered;
the reviewer does not establish equality using the producer's round-trip hash.

Coverage includes **6,720 observed updates / 13,404 history samples / 20,196
stream records**, with independently recomputed **324 history and 504 endpoint
array digests**. All forty sealed review payloads, fourteen frozen review
inputs/capsule members and the 133-test receipt authenticate. The controller
authenticated the original accepted/rejected numerical chain before and after
review; no simulator, ODE reference or physical-law evaluator was rerun.

Original native JSON totals **1,509,951,698 bytes**; streams total **18,070,684
bytes**: **83.558× smaller / 98.803% saved**. The largest encoded chunk is
1,088,005 bytes; the largest encoded record is 61,772 bytes. Review peak RSS
is **404,140,032 bytes (385.42 MiB)**, including one materialized legacy JSON
row. This is an offline review measurement, not bounded live native memory
or a numerical integration speedup.

## Evidence identities

- [Codec completion](../runs/ref-005d-offline-codec-2026-09-17/qualification-01/completion.json):
  `9e5ea291c711deb6edbd6c674c8a7aaff033b932f4c8ef9388db40a4637fe379`.
- [Review registration](../runs/ref-005d-codec-audit-2026-09-17/audit-01/registration.json):
  `e6c8a6c884aa243db1b554448048b702b9c31f746add10d1c384a803948a03f3`.
- [Review completion](../runs/ref-005d-codec-audit-2026-09-17/audit-01/completion.json):
  `b7cc5472783236f12ccec4e658374ba83c28dba11851543a4ebdca81e3fc883f`.
- [Review software receipt](ref-005d-codec-audit-checks-02.xml):
  `808895f7f6df01981312241077e75f1c568595496c2b4ff6e6c2591e2ac2d8fd`.

The original producer's historical `pending_independent_review` status is not
rewritten. Its source files, both captured packets, original numerical failure
and accepted refined pilot remain immutable. The new
[live/window qualification](REF005D_LIVE_HANDOFF.md) is a separate source
context, on the **same 1 ms fixture**, with exact overlap and recording/restart
checks. Independent live review and a newly scoped 10 ms reference/resource
study remain later user-authorized steps.
