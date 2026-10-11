# REF-005d R0: logging classification correction and Cells-only continuation

2026-09-17, D127. Proceed under the user's instruction after the D126 status
report. Preserve the failed campaign and all tested/frozen inputs unchanged.

## Diagnosis and reuse boundary

The original run stopped after **577.531 s**, at the controller's stderr gate,
after its native worker returned successfully and native coverage passed.
`native.json` reports 36 exact original-record overlaps, eighteen matching
full-observer/storage-only pairs, 6,720 observed updates and 13,404 history
samples. No Cells phase started. Exactly 72 notices have the expected message,
but `[live_job.py]` rather than `[betse]` as their prefix.

The pinned upstream logger builds its terminal format with
`cmds.get_current_basename()` (`betse/util/io/log/conf/logconfcls.py`);
`betse/util/os/command/cmds.py` returns the application name for `-c`, otherwise
the actual script basename. The D125 real-native smoke used `-c`; its full
controller invoked a file. No numerical mismatch is indicated by this failure.

Saved packet: `runs/ref-005d-live-recording-2026-09-17/qualification-01`.
Fixed identities:

- Registration: `3eb0443fb6818e6fca6155315e74edbf3c0e16c2713bad6d5686853bca075665`.
- Failure: `1ba0076d91322d0011d80798ab3034a25999c3fdaf8d5fcf08a2b4bc048286ce`.
- Native result: `b16bd49c2719b83182c73cfe943b4fde984538f79c3f4748320cd7e355a7a7a2`.
- Native stderr: `1a062216a2011dbf1d57ac080fa739743f17d9b0a3fc5ed7f319b91219744cbf`.

The [new continuation](../validation/betse/live_recording_resume/README.md)
authenticates these identities, all 668 original source inputs/capsule members,
the prior passing software receipt and accepted prerequisites. It checks all
964 saved files, every comparison/capture link and all compressed payloads
through the capture -> manifest -> index -> chunk digest chain, including
complete row/pair/record coverage. The saved packet contains **58,017,037 bytes**.
Its entire inventory is sealed into the new registration and rechecked before
and after Cells. Native pickle bytes are retained, never loaded as restarts.

This is a source-bound reuse of previously compared producer data; no numerical
comparison, simulator or independent physical-law audit is silently rerun.
The original terminal failure is neither removed nor relabelled. The new
warning classifier still rejects wrong scripts, changed messages, missing/extra
notices and all other stderr. Cells continues to require empty stderr.

## Software and execution

The source-bound short regression includes an actual script-invoked BETSE
terminal-formatter probe, the actual saved 72-line regression, every native
hash link, corruption/coverage refusals, source/registration binding, Cells-only
dispatch, failure preservation, launch failure and process-group timeout cleanup.
It imports no simulator into the controller. The existing tested 79-case
observer/window suite is reused unchanged, not relabelled as new test work.

```bash
taskset -c 0-3 .venv/bin/python -B validation/betse/live_recording_resume/resume_job.py check \
  runs/ref-005d-live-continuation-2026-09-17/software-01 \
  --tests reports/ref-005d-live-continuation-checks-01.xml

.venv/bin/python -B validation/betse/live_recording_resume/resume_job.py launch \
  runs/ref-005d-live-continuation-2026-09-17/continuation-01 \
  --checked runs/ref-005d-live-continuation-2026-09-17/software-01/completion.json
```

Both destinations and the XML must be fresh. Passing software evidence must
match the exact new source manifest; the launch binds its registration digest
to controller and worker. Subsequent evidence/status goes in
[Progress](../PROGRESS.md), not edits to this frozen handoff.

The controller dispatches **only** the unchanged Cells worker from D125:
24 accepted-baseline comparisons, 72 window paths, eighteen disk-policy outputs,
six loaded full and six windowed restart suffixes, six zero-length and two
sparse-observation controls. Same seven-cell 1 ms preparation, ordinary public
CPU/JAX float64 RK4 APIs, physics, timesteps, readouts and scientific thresholds.

Retain CPUs 0–3/one BLAS thread, **750 s Cells / 1,800 s overall / 16 GiB
Cells address space / 32 MiB per file / 512 MiB new artifacts / 1 GiB disk
reserve**. The native phase cap is unused because no native worker is dispatched.
Caps are safety bounds, not an ETA. Detach once and return control; no polling,
retry or independent follow-up campaign. Success is producer qualification
pending separately authorized independent review. Native internal memory,
longer integration, biology, GPU and full BETSE parity remain separate gates.
