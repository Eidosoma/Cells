# Long-running jobs

For long-running acceptance, benchmark or regression jobs, launch detached with
durable logs and result/failure artifacts, then return control to the user.
Do not automatically wait or poll repeatedly; the user will request status checks.
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
