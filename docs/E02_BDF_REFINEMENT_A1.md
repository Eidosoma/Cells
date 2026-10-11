# E02 A1: one tighter BDF reference diagnostic

D035 / 2026-09-09. The user approved a separately registered tighter BDF check
after the [retained miRNA-only disagreement](../reports/NUM005C1_CONTINUATION.md).
This named amendment authorizes **one diagnostic trial**, not a parameter sweep,
the remaining controls, RK4 selection or production changes.

## Prospective trial and interpretation

The [machine-readable amendment](../configs/reference/e02_bdf_refinement_a1.json)
uses the unchanged `M_to_E/mirna_only` case and exact original assay anchor.
Run a fresh BDF path from 0 to 1000 with both tolerances multiplied by 0.1:
nominal `rtol=1e-11`, `atol=1e-12`. The binary64 multiplication, maximum step
0.1, checked Jacobian, full dense checks and lossless recorder use the existing
immutable numerical implementation. New assay ledgers start at zero, as before.

Import all three previous complete paths from their original locations. The
pinned continuation audit covers their dense domain/accounting checks, while
their original trio remains unqualified. Hash-check all prior evidence, source
identities, prepared inputs and runtime before reuse. Do not copy or link their
chunks, rerun Radau, or erase the failed BDF comparison.

Compare all four paths on the union of every accepted endpoint, midpoint,
original observer time and phase boundary. Retain complete sampled states and
all six pairwise comparisons, using the unchanged eight quantity budgets.
The three required pairs are Radau/refined-Radau and each Radau path against
the new tighter BDF path. Their maximum normalized scores must remain at most
0.1, reconstruction residual at most 2e-9, and blocked histories exactly zero.
Comparisons involving original BDF stay visible as diagnostics; they are not
silently deleted from an acceptance panel.

A pass means only that this predefined refinement meets those agreement targets.
It supports a later decision about an amended reference policy. It does not
establish a rigorous error bound or the root cause of the previous discrepancy,
reclassify the original failure, publish a qualified biological outcome, or
automatically increase the original ten-of-fourteen qualification count. A
failure stops the trial with all evidence retained; no further tolerance is tried.

## Bounded execution and source preservation

All earlier source files and evidence stay unchanged. New multi-root comparison
plumbing reuses their numerical readers and score definitions, with explicit
reader cleanup on normal exit and refusal. It changes storage ownership, not
the equations. Its four-input working-array estimate and 256-sample batches are
explicit; no whole-trajectory list is accumulated.

One CPU float64 worker, affinity 0–3 and single-thread libraries. Keep the original
900-second trajectory, one-million-step, two-million-RHS-call, 256 MiB estimated
working-array and 3600-second scientific-session caps. Comparisons and integrity
checks count toward the session. Reserve 4 MiB for metadata as before.

The original campaign's two immutable roots occupy 511,109,773 bytes. The new
root receives only 562,632,051 bytes of the same aggregate 1 GiB quota. It lives
in a separately named A1 directory so the earlier closed-session inventory checks
remain valid; the directory change does not reset the budget. Unexpected new
sibling artifacts, symlinks or hard links are refused.

Archive 35 source/configuration/instruction/test files and register the single
attempt, imports, comparison pairs and budgets before integration. Never reuse
an existing output root or launch a worker after its session is closed/expired.

## Independent checks and commands

Short tests cover exact inputs, the single tenfold refinement, old-failure
preservation, multi-root ordering/reader cleanup, aggregate quota, tampering and
single-attempt stopping. No test runs a 1000-unit scientific trajectory.

The separately bounded read-only auditor rechecks all identities and payloads,
independently audits the new dense trajectory, rebuilds the four-input union
grid, checks sampled states against all four retained trajectories, and
independently normalizes primary/history scores. Derived flux/cache/gate scores
remain online-recorded results, not independent RHS recomputations. Reuse the
exact pinned old curve audit instead of re-integrating or modifying old evidence.

```bash
env OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 taskset -c 0-3 .venv/bin/python scripts/refine_graph_reference.py --output runs/num-005c1-a1-2026-09-09/bdf-tight-01
env OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 taskset -c 0-3 .venv/bin/python scripts/audit_graph_refinement.py runs/num-005c1-a1-2026-09-09/bdf-tight-01
```

Test and read-only audit time are separate verification work, not additional
integration after a stopped scientific session. NUM-005c and production gates
remain open regardless of this single diagnostic's outcome.
