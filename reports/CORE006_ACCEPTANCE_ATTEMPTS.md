# CORE-006 retained engineering attempts

2026-09-09. These are test-context/verification attempts, not failed biological
predictions or revised numerical targets. No SPEC-005/NUM-006 input, tolerance,
reference trajectory, production equation or runtime guard changed for them.

| Attempt | Outcome and handling |
| --- | --- |
| Direct all-tests call, `core-006-tests-01.xml` | 2468 pass, 31 fail, 57 fixture errors. Ten historical NUM-005 modules require original 0.10.0 source/packaging, CPU affinity 0–3 and fixed thread settings. Production had deliberately advanced and this call used CPUs 0–23. The new model's 108 tests pass. Keep the receipt; do not claim a passing full suite from this call. |
| Isolated reference test context, `core-006-reference-tests-01/` | 959 pass, 6 fail, 6 fixture errors. Original source and CPU guards now pass, but linked evidence violates existing path-confinement/no-links guards. Correct the test workspace to use independent temporary copies; no validator or historical test is patched. |
| Production `acceptance-01/` | Manually interrupted at 114.73 s before changing the captured test-workspace driver. The reference audit, 948 scalar/99 cohort old-source loads, old source-pair replay, both mono 1 s modes and mono 10 s JIT had passed. The mono 10 s eager run was interrupted; no numerical comparison failed. Preserve its registration, implementation capsule, three completed runs and `failure.json`; exclude it from final accepted totals. |

Final [production acceptance](CORE006_ACCEPTANCE.md) uses the separate
`acceptance-02/` directory and passes, with no production/reference change after
registration. The complete `core-006-tests-02/` matrix also passes: 1594 current
tests and 971 preserved-reference tests, with no failures/errors/skips. The real
historical evidence is never rewritten or counted as newly generated trajectories.

The source archive made **before production edits** remains
[cells-0.10.0-source.tar.gz](cells-0.10.0-source.tar.gz), SHA-256
`24a65b3bd478b76e230670785091b255f51d1427450e15c7b5dabc8a154f6536`.
Its [preservation receipt](core-006-preservation.json) authenticates all 39 old
production modules and the reference audit environment.
