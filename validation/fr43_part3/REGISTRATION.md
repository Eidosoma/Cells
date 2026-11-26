# FR-43 part 3: the registered comparisons and their pass criteria

This note fixes the pass criteria for FR-43 part 3's comparisons. It was written on 23 November 2026,
before the code-blind references returned. The lead tags their results before this builder reads
them.

It covers the comparisons against the same-draws references (`references/spec/`, worlds W1–W4) and
the closed-form statistical checks of `tests/unit/test_integer_unit_population*.py`.

**The engine.** The engine is `integer_unit_population@1`. In W3 it runs beside
`scheduled_species_turnover@1`, and in the division worlds beside `isopotential_partition@1`.

**Bounds fixed before any reference value was seen.** Each bound below was fixed before this builder
saw any value from the registered references.

**What informed the order criterion's window and its phase allowance (§2):**
- one engine self-convergence run;
- one development integration that this builder wrote. It is not code-blind and is not the
  registered reference.

The records of both are listed in §5.

## 1. W1, W2 and W4: agreement at rounding, at every step

In these worlds only the operator moves its pools. So its half-steps are the exact flow, and the
event times do not depend on the step (`docs/FR43_PART3_BUILD_PLAN.md` §3).

**Each world is run at dt = 20 ms and 5 ms.** Each run passes when all of the following hold for every
event with t_k ≤ 20 s:
- **The trace matches.** The number of events, every channel and the counts after each event equal
  the reference's.
- **The event times agree.** |t_k(engine) − t_k(reference)| ≤ 1e-9 s.
- **The pools agree.** The pools at each event agree within |Δn| ≤ 1e-9 fmol, both the cell's and the
  node's S.
- **The step does not matter.** Between the engine's own two runs, |t_k(20 ms) − t_k(5 ms)| ≤ 1e-11 s.
  This is checked without the reference.

**Why these bounds.**
- The engine's own error is at rounding: about 1e-13 s against the development integration (§5).
- The reference's declared accuracy is 1e-10 s and 1e-12 relative. The bound is ten times that
  accuracy.

**When the comparison is inconclusive.** If the reference reports a cross-check difference above its
declared accuracy, the comparison is inconclusive, not a pass.

## 2. W3, the two-way world: order 2 under step halving

**Where the error comes from.** In W3, turnover writes the pool the clock reads. Strang's splitting
then makes the event times second order.

A single event's error is ≈ C dt² φ(1 − φ), where φ is where the event falls inside its step. φ moves
from one step size to the next, so pairwise orders scatter: they ranged from 1.4 to 2.9 in the
development run. The criterion therefore fits over the whole window and allows for the phase.

**The window.** dt ∈ {20, 10, 5, 2.5, 1.25} ms, the horizon 20 s, and e_k = |t_k(engine, dt) −
t_k(reference)|.

**The pass criteria:**
1. **The trace matches.** At every dt the number of events and every channel equal the reference's.
2. **The order.** Fit log(RMS_k e_k) against log dt by least squares over the five steps. The slope
   lies in [1.7, 2.3].
3. **The phase band.** RMS_k e_k / dt² lies within a factor of 4 across the window: max/min ≤ 4.
   - A first-order part would grow this ratio by up to 16 over the window, so this also excludes
     order 1.
4. **The size.** RMS_k e_k ≤ 1e-6 s at 1.25 ms.

**Also reported, not judged:**
- the same statistics with the maximum over events in place of the RMS;
- the pools at the events.

## 3. The split at division: an equal-probability split

**The world.** Each parent site holds exactly one active unit, and its rates are 0, so no event
precedes the division.
- The cell divides by `isopotential_partition@1` with volume fraction ½. Every patch takes the
  partition's default area fraction, so f = ½ exactly.
- The units segregate by `independent_segregation`.
- The run is 64 seeds × 128 sites, which is N = 8,192 draws.

**The pass criteria:**
1. **Exactly one recipient per draw.** On every draw the pair (first daughter's active count, second
   daughter's) is (1, 0) or (0, 1), and the parent's count goes to 0.
2. **The inventories sum.**
   - The integer counts sum exactly, and each site's subunit ledger is exactly 0.
   - The pools of S sum to the parent's within the partition's material ledger.
3. **The frequency.** X is the number of draws the first daughter receives. It satisfies
   |X/N − ½| ≤ 3.29 √(¼/N) = 0.0182. This is a two-sided binomial band at 99.9% confidence.

**The plant.** The same 64 seeds at area fraction f = 0.55, with the larger daughter first as the
anchor rule requires.
- It must lie outside the ½ band. It is expected 9 standard deviations away.
- It must lie inside its own band, |X/N − 0.55| ≤ 3.29 √(0.55 × 0.45/N) = 0.0181.

## 4. C3.3: feedback off, constant rates (the closed form, inside the test)

**The world.** One world holds 16,384 independent sites, each with two free subunits and no transfer.
- The assembly constant is k_a = 0.5 /s, so the propensity is 2 k_a = 1 /s at n = 2.
- The disassembly constant is k_d = 1 /s.
- The closed form is P₀(t) = π₀ + (1 − π₀) e^{−(2k_a + k_d)t}, with π₀ = k_d / (2k_a + k_d).

**The pass criterion.** At t_m = 0.25, 0.5, …, 2.5 s (m = 10), the fraction of sites with no active
unit satisfies |p̂_m − P₀(t_m)| ≤ 3.89 √(P₀(1 − P₀)/n). The value 3.89 is Bonferroni for 10
comparisons at an overall α = 0.001.

**The plant.** The same world with k_a 10% high must fail at least one of the ten comparisons.

**The pathwise check.** For the first 16 sites the trace equals the exact kernel's for the same
uniforms: t_k = t_{k−1} + E_k/a₀, with the channel by u₂. The times agree within 1e-11 s and the
channels and counts are identical.

## 5. Evidence that informed §1 and §2

The evidence is in `/mnt/workspaces/Cells/fr43-part3-20261123/`. These are development runs from this
branch's working tree, not frozen evidence:
- **`out/conv/`.** W3 at 20, 10, 5, 2.5 and 1.25 ms, and W1 at 20 and 5 ms, from `probe/trace_run.py`
  run by `probe/conv_batch.sh`. They ran on lane A under its lock.
- **`probe/dev_reference.py`.** This builder's own Radau integration, scipy, rtol 1e-12. It is not
  code-blind, and it is a development aid only.

**W1.** The engine agrees with it within 8.5e-14 s at both step sizes.

**W3.** The maximum error is 6.1e-5, 8.7e-6, 3.3e-6, 1.18e-6 and 2.2e-7 s from 20 ms down. The
least-squares order is 1.91 by the maximum and 1.96 by the RMS. RMS/dt² lies in [0.062, 0.112], a
ratio of 1.8.
