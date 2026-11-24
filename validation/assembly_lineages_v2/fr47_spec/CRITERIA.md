# FR-47's criteria, bands and plants

These are fixed before any engine run (`docs/FR47_SHELL_EXCHANGE_PROTOCOL.md`; D323).
- "The reference" is the references agent's file (SPEC.md §5).
- "(d)" is `cells.rate_equations@1` with FR-47's build.
- "Exact" is `cells.assembly_lineages@2`'s exact events.
- The pair rule is `validation/assembly_lineages_v2/agreement.py`.

## The bands

- **Statistical criteria** pass at |z| ≤ 4.5. They are inconclusive above that up to 6, and fail
  beyond 6 (Protocol D's bands, D304).
- **(d)'s criteria** are deterministic, so they have no band. A deterministic result is
  inconclusive only through the step-count guard (C1). Such a result is rerun once at rtol 10⁻¹²
  with the same bound, and a second inconclusive result fails.

**The two z formulas** (M = 128 replicas, ȳ their mean, s² their unbiased variance with divisor
M − 1; m, σ² and μ₄ the reference's mean, variance and fourth central moment):
- the mean's z = (ȳ − m)/√(σ²/M);
- the spread's z = (s² − σ²)/√((μ₄ − σ⁴(M − 3)/(M − 1))/M).

**The scales s_y:**
- **for a pair:** its observable's largest |reference mean| over the founder and the times;
- **for a stop's removed count:** the largest over the world's stops;
- **for a mixing heat:** the largest over its withdrawals;
- **for an interval heat:** the largest over its intervals.

## The pair rule, classified from the reference before the run

| Class | The rule |
| --- | --- |
| `constant` | Every exact replica equals the reference's value exactly, and one wrong replica fails (`agreement.judge_constant`). (d)'s value at the pair must equal it too |
| `derived` | A constant reached by two routes of different arithmetic: within a bound derived from that arithmetic (`agreement.judge_derived`), as release_check's bounds are. In this protocol, only the tracer moiety's sum in (d) is derived (C5) |
| `spread` | The mean's z with the reference's own SD, and the spread's z from the reference's fourth moment (`agreement.judge_spread`). Identical replicas face the spread test |

No pair is excluded after the run, and no class changes after it.

## The criteria

| | Compares | Test |
| --- | --- | --- |
| C1 | (d)'s counts at every observation time, and its removed amounts per stop (W1, W1Δ) | \|y_d − y_ref\| ≤ 10⁻⁵·s_y, with s_y the reference's largest \|mean\| for that observable over the founder and the times. This holds over at most 10⁴ accepted steps at rtol 10⁻¹⁰; beyond that the result is inconclusive |
| C2 | The exact ensemble's means at every pair (W1, W1Δ) | The pair rule |
| C3 | The exact ensemble's spread at every `spread` pair (W1, W1Δ) | The pair rule's spread z, with μ₄ from the reference |
| C4 | Each stop's removed count, and each withdrawal's mixing heat −k·ln(1 − f), which is linear in the kept count k | Exact: the pair rule. (d): C1's bound |
| C5 | The books | Every run of either representation closes its ledger (its own check). The tracer moiety balances: present + removed = the founder's, exactly in exact events, and in (d) as a `derived` pair within 16 eps × (A + S) × P_t × T. Here A is the run's accepted steps and S its stops; P_t is the tracer's places and T the founder's tracer count. The derivation: each Rodas4 step updates each place by six stage terms, each place at most T, and each stop's map rounds each place once |
| C6 | W2's exact ensemble against the gate-conditioned exact mean, variance and fourth moment, per rung | The pair rule (C2 and C3's tests) |
| C7 | W2's (d) against the mean-field reference, per rung | C1's bound |
| C8 | W2's representation gap on the **tracer observables only**, S@pool and S@lumen: the mean-field minus the exact mean, and its slope in ln N_g (−1 expected) | **Reported from the reference alone, not claimed** (AMENDMENT-2026-11-24.md §1: at M = 128 no rung resolves the gap). Each rung's gap is taken at its largest pair, the largest \|gap\| over S@pool and S@lumen at the observation times; ties go to S@pool, then to the earliest time. The slope is fitted on ln\|gap\| and reported with its resolution table. The wall forms' gaps (O(N_g/N_w), from the limit's switching factor) are left to C6 and C7 |
| C9 | (d)'s continuous heat over each interval between stops (W1, W1Δ) | Against the reference's −ΔF_cont of its mean counts, to C1's bound. It tests F_cont at a zero start, where (d) books the heat by closure |

## The plants

**Fixed now, as erratum 2 had to rule after the fact:**
- **Process.** Each plant runs in its own process: a scoped patch under `validation/`, never in
  `src/`, on the plant's own world.
- **Scoring.** A plant is caught when its criterion fails, or when its run is refused by its own
  books or checks.
- **Sizing.** Each plant's effect is sized by the references before any run (SPEC.md §3.4).
  - **Statistical criteria:** the distance is |planted − honest| in units of the fail band,
    6·SD_ref/√128, with SD_ref the honest reference's SD.
  - **Deterministic criteria:** the distance is in units of that criterion's own bound. C5's is at
    the step guard's cap, A = 10⁴.
  - **Each (plant, criterion) entry** reports and names its compared quantity of largest distance.
- **P4, P6, P8 and P9,** as the second amendment reads them (AMENDMENT-2026-11-24.md §2):
  - P4 is the honest reference before the full wash, with both tracer places frozen after it;
  - P6 follows the tie rule: a tie goes to the earliest time or stop, then the first observable;
  - P8 samples at f² and books −k·ln(1 − f) with the declared f at the planted k;
  - P9 takes the zero place's whole term at n = 1, μ° − ln X − 1.
- **P2, P3 and P5,** as the amendment defines them (AMENDMENT-2026-11-23.md §3–§5):
  - P2 keeps (1 − f)² of the pool and books the rest as removed, with −k·ln(1 − f) at the planted
    k;
  - P3 maps the lumen at every stop as the pool and books its loss as removed (the replacement-only
    variant stays out of the files);
  - P5 gates the entry alone.

| Plant | Mechanism | World | Caught by |
| --- | --- | --- | --- |
| P1 | (d)'s shell exit without its e^(Σνμ°) | W1Δ | C1 |
| P2 | (d)'s withdrawal keeps (1 − f)² of the pool | W1 | C1, C4 |
| P3 | (d)'s wash applied to the lumen too | W1 | C1 |
| P4 | (d)'s old factored flux at an E2 place: after the full wash the pool never refills | W1 | C1, and C4 at the 9.0 s withdrawal, the first after the full wash (corrected 23 November: AMENDMENT-2026-11-23.md §2) |
| P5 | (d)'s gate factor on the entry's forward direction only, pool → lumen (κ_in times g; the exit ungated) | W2, N_g = 256 | C7, or refused by the limit's check |
| P6 | (d)'s removed tracer left unbooked | W1 | C5, or refused by its books |
| P7 | The exact kernel's shell exit without its e^(Σνμ°) (scoped) | W1Δ | C2 |
| P8 | The exact withdrawal sampling at f² | W1 | C4 |
| P9 | (d)'s F_cont at a zero place taken as one molecule's | W1 | C9 |

## E2's build rows (tier rows of FR-47's build, after the tag; not judged here)

- **The flux and its one-sided derivative:** at an empty reactant and at an empty product, on a
  first-order world. They must equal the first-order law's (J = k_f n_A − k⁻ n_C, with derivatives
  k_f and −k⁻) to rounding. The plant is the old factored form, which gives J = −0 and derivatives
  −0 at an empty reactant.
- **The step-halving order:** across a step that starts at zero, the error of one Rodas4 step falls
  by about 2⁴ per halving of h. The plant is the old factored form, with its zero derivative.
- **The rule for E2 places below zero,** which replaces the envelope's guard there:
  - their rates use the first-order law's linear form, defined for any real count, so a Rodas4
    stage below zero is evaluated as the law, with an exact Jacobian;
  - a step result with an E2 place below −10·atol_count is rejected and retried at h/4. A run that
    cannot avoid it stops `stalled`.
