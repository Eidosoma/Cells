# REF-004d timed channel suppression/release: numerical closeout

2026-09-16. D106's separate saved-data audit completed successfully at
10:24:42.566665 UTC in **387.772 s**. This report records the completed outcome;
the original prelaunch, capture and pending-audit receipts remain unchanged.

Evidence: [completion](../runs/ref-004d-timed-release-audit-2026-09-16/audit-01/completion.json),
[independent audit](../runs/ref-004d-timed-release-audit-2026-09-16/audit-01/audit.json),
[capture report](REF004D_TIMED_RELEASE_CAPTURE.md).
Completion SHA-256:
`f144dea687a1140409b549237faf63cf1b758e2aafe8b91091fd6055f7c5b8a7`.

- 15,042,946 independent numerical comparisons in 182 groups; zero column
  mismatches. All 16 refinement and 12 history-contrast groups pass.
- All 48 complete checkpoints / 2,592 arrays, 24 observer pairs, eight Cells
  restart pairs and eight eager/JIT pairs pass.
- All 49 coarse diagnostic failures remain (35 history a / 14 history b), as
  do 3,265 original exact-identity diagnostics and 28,280 zero-flux means.
- The ten-file audit packet, 203 audit source inputs / 37 historical reports,
  and all 555 original capture files / 194 capture inputs authenticate. The
  separate D104 reference review was authenticated, not repeated.
- Software preflight: 116 tests, in two bounded groups (41.99 s and 43.13 s).
  Neither simulator nor the reference integrator was rerun for the audit.

Qualified scope: the registered seven-cell shared-bath Kv1.5 experiment, two
initial histories, four conditions and a 2 ms window, at the accepted finest
grids and refinement settings. This is numerical source correspondence, not
biological memory, native restart, broader channel-family parity or GPU evidence.

All 352 accepted implementation files / 51 production modules remain unchanged.
Stable release remains 0.14.0; accepted development remains 0.15.0.dev0. The next
work is [substrate-dependent pumps, junctions and biological evidence](../docs/BETSE_REALISM_AND_NEXT_STEPS.md),
not another rerun of this completed channel benchmark.
