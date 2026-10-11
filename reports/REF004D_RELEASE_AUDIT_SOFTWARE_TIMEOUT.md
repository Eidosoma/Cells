# D106 bounded software timeout — retained, not a passing receipt

The expanded foreground software invocation on 2026-09-16 used `timeout 55s`
and exited 124 before completing the added full Cells state/restart/backend
tests. It had printed no assertion failures, but did not write its requested
`ref-004d-release-audit-checks-03.xml`; there is no passing receipt for attempt 03.

Earlier receipts remain: attempt 01 recorded 6 passes and 2 setup errors in
9.78 s (the new audit selected the older single-update preparation path instead
of the full-loop preparation; corrected only the new audit); attempt 02 passed
all then-existing 103 tests in 33.03 s. During preparation, helper re-exports
were made explicit after lint removed them as unused.

The expanded final verification is split into two disjoint, independently
bounded software batches. Registration requires all named test families and
rejects duplicate, failing, skipped or missing coverage across their XML receipts.
This changes neither scientific budgets nor the detached audit's 1,800 s limit.
No simulator/reference was run, and no full audit had launched at this timeout.

Final disjoint batches subsequently pass all 116 checks: attempt 04 has 103
passes in 41.99 s; attempt 05 has 13 passes in 43.13 s. The timeout and earlier
receipts remain historical evidence, not substitutes for these final receipts.
