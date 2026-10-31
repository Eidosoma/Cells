# Source code and outputs

Keep production source, reusable validation tools and tests in this Git checkout
under `src/`, `validation/`, `scripts/` and `tests/` as appropriate. Use
`/mnt/workspaces/Cells` for run outputs, logs, frozen evidence and execution
snapshots; it must not be the only location of an active implementation.
Preserve frozen snapshots when integrating their source into the repository.
The checkout is the single editable source of truth. Generate execution
snapshots from it in one direction, recording the Git revision and any dirty or
untracked source changes in the run inputs. Treat those snapshots as immutable:
make fixes in the checkout and generate a new snapshot for a later run. Do not
develop a parallel implementation under `/mnt/workspaces` that later needs to
be copied back or manually reconciled with Git. Reuse the existing snapshot and
source-binding tools; preserve exact run-source identification.
Code awaiting qualification belongs in the checkout with its existing guards
and validation status intact; integration alone grants no scientific acceptance.
Coordinate file ownership in this shared checkout and do not overwrite another
developer's changes.

# Running jobs

For runs expected to finish in under 10 minutes, an attached watcher may monitor
completion while keeping the user updated. For runs expected to take 10 minutes
or more, including acceptance, benchmark or regression jobs, launch detached
with durable logs and result/failure artifacts, then return control to the user.
Do not automatically wait or poll repeatedly for detached jobs; the user will
request status checks.
Do not interrupt an active computation merely to stop assistant polling.
Follow-up audits and regression jobs should wait for the user's next instruction.

# Lean scientific workflow

Keep reproducible evidence and thorough logs, with documentation proportional to
the scientific and engineering risk.

- Use `PROGRESS.md` for current status and a concise per-run summary linking to
  machine-readable inputs, results, checks and failures. Avoid duplicating the
  same status across multiple documents.
- Reuse established runners and checks. Routine fixes do not each need a new
  design document, handoff, numbered stage or separate sign-off.
- Add a protocol or independent review when it resolves a concrete risk or
  supports a new scientific claim; explain that purpose briefly. Batch related
  low-risk work and validation where practical.
- Preserve failed evidence, reproducibility, conservation/domain checks and
  numerical tolerances. Simplify the process, not the scientific standards;
  leave frozen evidence and active jobs untouched.
