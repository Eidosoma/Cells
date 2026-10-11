# REF-004b: bounded coupled feedback pilot closed

2026-09-15. D096 completed at **13:22:49 UTC**, in **172.504 seconds**. Its
user-requested status check authenticated the complete packet, source capsule,
software receipt and unchanged D095 evidence. No simulator or reference
integrator was rerun by the audit.

## What passed

- **5,806,006 independent numerical identities**, matching all frozen replay
  comparisons, with **zero independent-column mismatches**, across 67 groups.
- **5,181,760 native boundary/probe identities**, 2,264 direct charge snapshots
  and 612 native float64 array records.
- **24 complete Cells checkpoints / 1,296 arrays**, twelve observer pairs,
  four restart pairs, four eager/JIT pairs and eight refinement groups.
- Twelve saved continuous-reference solves checked without integration.
- All **122 audit-only software tests** passed in 11.18 seconds. The original
  157-test pilot receipt remains bound without rerunning its integrations.
- All nine audit files, 122 source inputs and 284 original capture files
  authenticate; accepted 352 implementation files / 51 production modules
  remain unchanged.

All **fourteen coarse native diagnostic misses** remain in the evidence: seven
active voltage rows and seven blocked-gate rows. They were correctly replayed,
not relabelled as passing. Required finest-grid checks and the registered
refinement policy passed. Some Cells comparisons are reference/roundoff limited;
this does not establish an observed RK4 order or generic near-machine accuracy.

## Scope and provenance

This closes only the registered **2 ms, four-control, seven-cell / thirty-face**
Kv1p5 feedback pilot at 298.15 K, matched constants, fixed geometry and one shared
finite bath, at the specified observations and tolerances. It is not biological
validation, broad channel-family/BETSE parity, native restart equivalence, a
long-time/stiff-regime result, GPU execution or multiscale/organ qualification.

The immutable D095 receipt still says `capture_pass_pending_audit`; the separate
successful D096 receipt supplies closeout. No old input, capture or failure was
rewritten. No production release is promoted.

- [Completion](../runs/ref-004b-feedback-audit-2026-09-15/audit-01/completion.json),
  SHA-256 `61e700cbddda5141f92443ba684bf344d14d09e1b3c9db12110d1a0a923a28b9`.
- [Audit details](../runs/ref-004b-feedback-audit-2026-09-15/audit-01/audit.json).
- Registration SHA-256
  `8de505e9b6f1d076e82e07321c6b834baa8850b14ca4ece7297c7d5bb98b488d`.
- Original D095 completion SHA-256
  `28e985c8f1d49d7953b21382ad6a34b6f2989f23c5407a97118902f8391c8ceb`.

## Next bounded question

The separately requested [D097 history preflight](../docs/BETSE_CHANNEL_HISTORY_PREFLIGHT.md)
asks whether identical initial voltage/inventories/channel current conceal a
different subsequent opening tendency. It uses explicit initial settings,
not a claim about how biological history created those settings. Constant-control
paired trajectories, suppression/release, longer recovery and extra physiology
remain separate steps.
