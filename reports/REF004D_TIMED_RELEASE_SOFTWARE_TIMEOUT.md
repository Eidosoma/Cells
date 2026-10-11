# REF-004d timed-release software: retained foreground timeout

2026-09-16, D105 development only. The first combined focused-test command used
`timeout 55s` and requested `ref-004d-timed-release-checks-01.xml`. It exited 124
before pytest finalized that XML, so no complete receipt exists for attempt 01.
Partial console output included one native-check failure. No full 2 ms capture,
reference integration or independent full-panel review was started.

The software fixtures are being separated and bounded more tightly: the native
smoke uses four intervals and all four conditions; the Cells smoke uses the same
four intervals for suppression/release, with eager/JIT and a release-boundary
restart. Complete all-condition, two-history coverage belongs to the registered
detached experiment. Later numbered receipts retain the complete software
outcomes. No scientific tolerance or production implementation is changed.
