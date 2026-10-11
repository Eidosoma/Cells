# REF-004c: paired coupled capture passed, independent closeout pending

2026-09-15. D099 finished at **15:53:41 UTC**, in **391.917 seconds**. The
user-requested status check authenticated all 291 files, 143 source inputs,
reference-gate evidence and worker identities. No warnings were recorded.

## What the capture establishes

- Twelve reference solves passed method/tolerance, domain and integrated-signal
  checks before either simulator started. This selects the registered 2 ms
  candidate in the fixed active/blocked paired-history fixture.
- **24 native runs / 4,480 updates**, **16 complete Cells trajectories**, four
  midpoint resumes and four eager/JIT pairs completed. Twelve native observer
  pairs matched; 24 complete checkpoints / 1,296 arrays passed the capture checks.
- **7,367,280 native accounting identities**, 2,264 direct charge snapshots and
  all required Cells accounting, trajectory and refinement checks passed.
- All six signed a-minus-b comparison groups passed. Equal initial current and
  opening with distinct m/h state yields an active reference voltage contrast
  of approximately **-0.722 mV** and opening contrast **+0.05422** at 2 ms. Both
  engines match their references and paired contrasts within registered budgets.
  Blocked voltage contrast stays exactly zero despite continuing gate evolution.
- **21 coarse diagnostic misses** remain: fourteen for a and seven for b.
  They are not relabelled as passing. Finest-grid and refinement requirements
  pass; reference/roundoff-limited comparisons do not establish an observed RK4 order.

This is a numerical capture, not biological validation or independent closeout.
The initial gate settings are declared data, not a claim about the biological
preparation that produces them. The fixed seven-cell / thirty-face shared-bath
Kv1p5 scope does not establish broad BETSE parity, native restart, long-time,
GPU, coarse-graining or organ-scale accuracy. Accepted production is unchanged.

## Evidence and next gate

- [Capture completion](../runs/ref-004c-paired-history-2026-09-15/capture-01/completion.json),
  SHA-256 `ec63dc8d69a9f4c5b9da93ddf64708e91fc708729eb0f52cb1d8899170bde690`.
- [Reference gate](../runs/ref-004c-paired-history-2026-09-15/capture-01/reference-gate.json).
- [Paired contrasts](../runs/ref-004c-paired-history-2026-09-15/capture-01/history-contrasts.json).
- Registration SHA-256
  `9c539f504312e77e3d695e5a549e0e0d2a34d1801b128c57e23c81f4e128341b`.

The immutable capture receipt remains `paired_capture_pass_pending_audit`.
The separately requested [D100 saved-data audit](../docs/BETSE_CHANNEL_HISTORY_CLOSEOUT.md)
must reconstruct the evidence without simulator/reference integration. No
automatic retry, regression, intervention or expanded physiology follows.
