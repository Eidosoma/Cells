# REF-005c refined native pump pilot handoff

2026-09-16, D119. **Prepared for one detached attempt; no refined result claimed.**
The [amendment contract](../docs/BETSE_PUMP_REFINEMENT.md) follows the
[independent failure diagnosis](REF005C_PILOT_FAILURE_DIAGNOSIS.md).

Cells physics and integration, native physics, all scientific tolerances and
the original failed packet remain unchanged. The new native ladder is
**6.25 / 3.125 / 1.5625 µs** for the same six controls and 1 ms duration, with
observed/unobserved partners. The repeated 6.25 µs records must reproduce the
previous numerical output exactly. The unchanged native producer receives the
explicitly amended timestep/resource plan.

The controller reuses 213 byte-verified files containing all 24 Cells trajectories,
eighteen independent references, six restart suffixes and saved held-state
mapping. No new Cells or reference solver runs occur. The comparator preserves
the original numerical criteria while retaining all miss counts and up to
64 concrete examples, plus per-row numerical/accounting evidence.

**46 software checks pass in 36.82 s** in the final receipt
`reports/ref-005c-refinement-checks-02.xml`.
The preceding 41-check receipt 01 is retained; receipt 02 adds explicit native
grid-identity checks and single-dispatch worker checks. The suite also covers
unchanged scientific criteria, rejected scope changes, bounded failure reporting,
signed-zero overlap, phase/output/resource guards, exact evidence copying,
reproduction of all six old failures from saved numbers, and actual loading of
all eighteen refined YAML configurations in the pinned native environment.
YAML loading does not seed or integrate a native simulation.

```text
.venv/bin/python -B validation/betse/pump_pilot_refinement/refinement_job.py launch runs/ref-005c-refined-pump-2026-09-16/refinement-01 --tests reports/ref-005c-refinement-checks-02.xml
```

The fresh registration freezes **641 inputs**, the passing software receipt,
original failure preservation and reuse manifest. The launch acknowledgement
records PID, UTC time and registration SHA-256; living progress indexes record
the acknowledgement. Do not edit this handoff, contract, protocol or registered
code after launch.

One campaign: 36 native runs / 18 observer pairs / 6,720 observed updates /
twelve exact overlap records. CPUs 0–3, one BLAS thread; 90 s reuse / 900 s native /
180 s comparison / **1,260 s total**. Hard **256 MiB/file**, checked **2 GiB disk
artifacts**, at least 3 GiB free disk at launch. These are not RAM caps.

Success requires every original numerical criterion on the new native ladder,
unchanged saved Cells/reference evidence and exact overlap. Failure leaves its
logs and partial outputs, including numerical summaries when available, and
does not trigger a retry. Original six misses are preserved, never relabeled
as passing by extrapolation or an energy correction.

Return after launch without polling. Producer success remains pending an
independent user-requested review. No automatic follow-up, optimization,
production change, biological validation, GPU run or release promotion.
