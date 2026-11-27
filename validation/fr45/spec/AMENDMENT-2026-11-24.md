# FR-45's spec: amendment of 24 November 2026, before the tag

This answers the references agent's 13 questions and rules on two power findings, before the tag
and before any engine run. It is in words and value-silent: it states no result of any world.
- **No band changes.**
- **One error is corrected:** C3's worlds (§2.1).
- **Two checks are strengthened,** without a band change: C3b's free energy is taken from the
  references (§2.2), and C3c covers the wash's interval (answer 7).
- SPEC.md and CRITERIA.md carry the corrections, each marked with this amendment's date.

## 1. The 13 questions, answered

1. **The package.** Accepted: the references' code in `validation/fr45/references/`, and the
   writer's files committed under `validation/fr45/references/outputs/` at the tag.
2. **`value`, and the convergence condition.** Accepted, with one requirement.
   - `value` is the 50-digit Taylor solution, rounded once to binary64 by `repr` at the write.
   - `tolerance_gap` is |DOP853 at rtol 10⁻¹² − DOP853 at rtol 10⁻¹³|, as SPEC.md §3.2 asks.
   - CRITERIA.md's inconclusive condition applies to `tolerance_gap`, as registered.
   - **The requirement, a check of the reference itself:** at every reported pair, the Taylor
     value agrees with DOP853 at rtol 10⁻¹³ within `tolerance_gap` + 10⁻¹² of the pair's scale.
     A pair that does not is reported before the tag, and the world is resized then, never after a
     run.
3. **Inert pools.** Accepted, and stated for every world, not only W3.
   - An amount that no law moves is left out of the trajectory and of every criterion: a ligand's
     free amount at a node that no population binds it from. That excludes C1, C2a, G, E, B_H and
     the balances.
   - SPEC.md §1.1: every ligand is impermeant and moves only by binding, so such an amount is a
     constant.
   - The judge may report it unchanged, as information.
4. **s_node.** Accepted.
   - It is taken over the trajectory amounts at the node: its free amounts, and the R_s and B_b of
     the sets that face it, over the start and the observation times.
   - The capacity S_s, a constant, is not one of them. Every R_s and B_b lies in [0, S_s].
5. **E.** Accepted: the sum, over both ends of the interval, of the magnitudes of the node's G
   terms. Each pool has one term, RT·n·(ln c − 1). Each population has one term,
   B_b·(μ°_b + RT·ln(B_b/S_s)). Each set has one term, RT·R_s·ln(R_s/S_s).
6. **B_H.** Accepted, literally:
   - every amount's term at both ends, each multiplied by 2δ;
   - plus 16ε·E;
   - with max(x, δ) in the log, and the scales of answer 4.
7. **Rows.**
   - **Accepted:** C4a, C5 and C9 are judged at the start and at every observation time: the saved
     rows.
   - **Accepted:** the heat intervals start at t = 0.
   - **C3c is strengthened** to cover every interval, the wash's included.
     - It reads only the engine's own cumulative site heat, which the wash does not book.
     - Binding after the wash is passive, so that heat cannot fall across the event either.
     - C3a and C3b keep the wash's interval out: G jumps at the event, which is the wash's own
       books.
8. **C2b's x_root.** Accepted: W1's root, written once. W1eq's start echoes it.
9. **C9's and C4b's state terms.** Accepted, with the roles stated.
   - The references write the tolerances' terms that the inputs fix: 4ε, and f·V·c_buf.
   - Any term from a state is filled from R-ode and marked as information.
   - The judge recomputes each tolerance from the engine's own saved state: for C9, the engine's
     moiety term |R_s + ΣB − S_s|/S_s; for C4b, the engine's anchor and amount at the event.
10. **Sections.** Accepted.
    - W1p and W4 carry `equilibrium` and `distance_at_horizon` as information. No criterion reads
      them there.
    - W5's inapplicable keys are null or empty.
11. **The pair scope per criterion.**
    - The references' scope, as their message gave it, is accepted where it agrees with §3 below.
    - §3 now registers each criterion's worlds and amounts in this spec, so the scope no longer
      lives only in a message.
    - W4's pairs carry `dt_s`.
12. **JSON shapes.** Accepted, and registered as the file format (SPEC.md §5, amended):
    - `"balances"`: {ligands: [...], sets: [...]};
    - `"heats"`: {intervals: [...], G: [...]};
    - `"spread"`: "none";
    - interval pairs carry `start_s` and `end_s`.
13. **Plant distances where a bound is not a number.** Accepted:
    - C6's in ulps of the amount the plant changes;
    - C7's as |Δ(h·max L)|/(1/2), the decision quantity's change against its threshold;
    - P8's, under C10, in C5's moiety-tolerance units, the planted per-population residual against
      C5's tolerance.

## 2. The two power findings, ruled

### 2.1 C3a in W4 is vacuous, so W4 leaves C3 (an error, corrected)

- **What happened.** CRITERIA.md's C3 rows named no worlds, so C3a was read over every world. W4's
  node holds pools far larger than its sites. Its δ, set by those pools through s_node, makes B_H
  exceed every W4 heat by orders of magnitude, so C3a could not fail there.
- **The registration already says otherwise.** The protocol's §4 gives W4 to C8 alone: W4 is the
  order study at fixed concentrations.
- **The correction:** C3a, C3b and C3c are judged in W1, W2, W3 and W6. They are not judged in W4.
  CRITERIA.md's C3 rows now name these worlds (§3).
- **The other C3a worlds are not affected.** There the sites and pools are of one scale, and the
  dry run's honest margin (CRITERIA.md) was found on neighbouring inputs of exactly those worlds.

### 2.2 P3 and P6 keep every planted heat non-negative, so C3b alone catches them: sufficient, with C3b's free energy taken from the references

- **The finding.** Neither plant makes any heat negative, so neither the sign checks (C3c, the
  engine's dissipation check) nor, by the references' sizing, C3a catches them.
- **Why C3b suffices.** C3b is a derived pair. Its tolerance comes from the arithmetic, and it
  tests exactly what P3 and P6 break: that the booked heat is −ΔG of the shared-lattice free energy
  of the engine's own states.
  - A booking that uses a wrong free energy consistently is caught only by comparison with the
    right one, and C3b is that comparison at rounding resolution.
  - P6 is also refused by the energy ledger when its heat and its ledger term disagree. CRITERIA.md
    lists that.
- **The strengthening.** C3b's −ΔG is computed by the references' own implementation of SPEC.md
  §1.3, called on the engine's saved states, not by a copy in the judge.
  - The judge is the builder's, so a judge-side copy could share the builder's error, and C3b would
    then miss the very plants it is there to catch.
  - The references therefore expose one function: G of a node's amounts, per world, as SPEC.md §5
    now asks.
  - P3's and P6's distances under C3a stay in the file as information.
- **No plant is changed.**

## 3. Each criterion's worlds and amounts (registered here; SPEC.md and CRITERIA.md follow)

| Criterion | Worlds | Amounts and times |
| --- | --- | --- |
| C1 | W1, W2, W3, W6 | Every free amount a law moves, every R_s, every B_b; every observation time |
| C2a | W1, W2, W3, W6 | The same amounts, at the horizon |
| C2b | W1eq | The same amounts, at every observation time |
| C3a, C3b | W1, W2, W3, W6 | Each node's heat over each interval from t = 0, the wash's interval excluded |
| C3c | W1, W2, W3, W6 | Each node's cumulative site heat, every interval, the wash's included |
| C4a | W2 | Each ligand's books, at the start and every observation time |
| C4b, C6 | W2 | The wash's event alone, on the engine's state at 4.0 s |
| C4c | W2 | Each ligand's removed and supplied amounts at the wash |
| C5 | Every world but W5 | Every set's R_s + ΣB, at the start and every observation time |
| C7 | W5 | Its first step |
| C8 | W4 | R and the B_b at its observation times, at its three steps |
| C9 | W1, W3, W6 | Every population's fraction, at the start and every observation time |
| C10 | Every run, W5's refusal apart | The run completes |
| The plants | W1p, W2, W3p, W5 as CRITERIA.md lists | Each plant's criterion, on its world |
