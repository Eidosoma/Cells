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

## The pair rule, classified from the reference before the run

| Class | The rule |
| --- | --- |
| `constant` | Every exact replica equals the reference's value exactly, and one wrong replica fails (`agreement.judge_constant`). (d)'s value at the pair must equal it too |
| `derived` | A constant reached by two routes of different arithmetic: within a bound derived from that arithmetic (`agreement.judge_derived`). In this protocol, only the tracer moiety's sum in (d) is derived: 8 eps × (the number of places summed) × the largest term |
| `spread` | The mean's z with the reference's own SD, and the spread's z from the reference's fourth moment (`agreement.judge_spread`). Identical replicas face the spread test |

No pair is excluded after the run, and no class changes after it.

## The criteria

| | Compares | Test |
| --- | --- | --- |
| C1 | (d)'s counts at every observation time, and its removed amounts per stop (W1, W1Δ) | \|y_d − y_ref\| ≤ 10⁻⁵·s_y, with s_y the reference's largest \|mean\| for that observable over the founder and the times. This holds over at most 10⁴ accepted steps at rtol 10⁻¹⁰; beyond that the result is inconclusive |
| C2 | The exact ensemble's means at every pair (W1, W1Δ) | The pair rule |
| C3 | The exact ensemble's spread at every `spread` pair (W1, W1Δ) | The pair rule's spread z, with μ₄ from the reference |
| C4 | Each stop's removed count, and each withdrawal's mixing heat −k·ln(1 − f), which is linear in the kept count k | Exact: the pair rule. (d): C1's bound |
| C5 | The books | Every run of either representation closes its ledger (its own check). The tracer moiety balances: present + removed = the founder's, exactly in exact events and as a `derived` pair in (d) |
| C6 | W2's exact ensemble against the gate-conditioned exact mean, variance and fourth moment, per rung | The pair rule (C2 and C3's tests) |
| C7 | W2's (d) against the mean-field reference, per rung | C1's bound |
| C8 | W2's representation gap, the mean-field minus the exact mean, and its slope in ln N_g (−1 expected) | Each rung's gap is taken at its largest pair. **The slope is claimed as measured** only over the rungs where the reference's own resolution there (the gap over the exact mean's SD/√128) is at least 4.5, and only when three rungs or more qualify. There, the ensemble's gap ((d) minus the exact replicas' mean) matches the reference's gap by the pair rule's z at each qualifying rung, and the slope is fitted on those rungs. **Otherwise the slope is reported** from the reference alone, as a prediction, and nothing is claimed as measured |
| C9 | (d)'s continuous heat over each interval between stops (W1, W1Δ) | Against the reference's −ΔF_cont of its mean counts, to C1's bound. It tests F_cont at a zero start, where (d) books the heat by closure |

## The plants

**Fixed now, as erratum 2 had to rule after the fact:**
- **Process.** Each plant runs in its own process: a scoped patch under `validation/`, never in
  `src/`, on the plant's own world.
- **Scoring.** A plant is caught when its criterion fails, or when its run is refused by its own
  books or checks.
- **Sizing.** Each plant's effect is sized by the references before any run (SPEC.md §3.4).

| Plant | Mechanism | World | Caught by |
| --- | --- | --- | --- |
| P1 | (d)'s shell exit without its e^(Σνμ°) | W1Δ | C1 |
| P2 | (d)'s withdrawal keeps (1 − f)² of the pool | W1 | C1, C4 |
| P3 | (d)'s wash applied to the lumen too | W1 | C1 |
| P4 | (d)'s old factored flux at an E2 place: after the full wash the pool never refills | W1 | C1, and C4 at the 7.5 s withdrawal |
| P5 | (d)'s gate factor on the forward direction only | W2, N_g = 256 | C7, or refused by the limit's check |
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
