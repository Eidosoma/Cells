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

# BETSE's role

BETSE v1.5.0 is an external reference for the Cells bioelectric layer. It is not
part of the engine.

- Run BETSE unmodified, out of process, in its own environment
  (`/mnt/workspaces/Cells/venv-betse`). Only `validation/betse/` may import it.
- Nothing in `src/cells` imports, executes, re-hosts or copies BETSE code. Cells
  implementations of BETSE-compatible laws are fine; cite the source law.
- Compare Cells against saved, extracted BETSE outputs, never against live BETSE
  objects inside a Cells process.
- `src/cells/processes/betse_native_*` and `betse_normal_*` are frozen tooling
  from before 8 November 2026 (tag `native-betse-frozen-2026-11-08`). Do not
  extend or launch them, and do not delete them without the user's approval.

# Milestones and provenance

- Every milestone names the Cells engine models it runs. A milestone that runs
  none is tooling and needs the user's explicit approval.
- Run provenance is the Git revision, the dirty diff and the frozen snapshot. Do
  not add per-call or bytecode attestation layers, and do not embed SHA-256
  hashes of other source files as literals in new code.
- If a check needs more than 30 minutes to reach the code under test, build a
  faster harness first.

# Running jobs

For runs expected to finish in under 10 minutes, an attached watcher may monitor
completion while keeping the user updated. For runs expected to take 10 minutes
or more, including acceptance, benchmark or regression jobs, launch detached
with durable logs and result/failure artifacts, then return control to the user.
Do not automatically wait or poll repeatedly for detached jobs; the user will
request status checks.
Do not interrupt an active computation merely to stop assistant polling.
Follow-up audits and regression jobs should wait for the user's next instruction.

From 8 November 2026 a single lead agent coordinates this checkout, with at most
four subagents working on disjoint files. Within the plan agreed with the user,
the lead may start planned follow-up runs without waiting for a status request.
It relies on completion notifications, not repeated polling.

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
