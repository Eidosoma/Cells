# Cells Key Developer workfiles

Use this directory for this worker's task-specific drafts, small inputs and
supporting files. Record their purpose and associated assignment in
[the work log](../WORK_LOG.md).

Keep durable simulation logs, machine-readable results and failures in the
established runner's evidence directory and link them from the work log. Preserve
frozen evidence and active jobs. Do not place large generated trajectories here.

The worker owns assigned features through their implementation and initial
checks. The coordinator also implements separate features and owns priorities,
shared integration files, handoff review, qualification launches and PROGRESS.md.
After a feature handoff, take the next independent feature assignment while its
qualification runs. Keep one active implementation assignment per developer;
queue later features rather than editing overlapping model or status files.
Use the same checkout without worktrees. Long qualifications remain detached
and are checked when the user requests status.
