# OL6 Protocol D, erratum 3: exact agreement under M (registration)

**Status: proposed for the lead's tag, 23 November 2026, before the checker judges D0, D3 or D5.**
Docs and validation only, with no src change. Branch `ol6-protocol-d-erratum-3` from main 2263d11c.
The proposed tag is `ol6-protocol-d-erratum-3-2026-11-23`.

**What it amends.** Protocol D as tagged at `ol6-protocol-d-registered-2026-11-23`, with errata 1
and 2 (`ol6-protocol-d-erratum-1-2026-11-23`, `ol6-protocol-d-erratum-2-2026-11-23`).
- The three registered files and both errata are still read byte for byte as tagged, and none is
  edited.
- This erratum adds two files:
  - this document, the authority where it speaks;
  - `validation/assembly_lineages_v2/protocol_d_erratum_3.py`, its arithmetic.

**The user's decision.** A pair at which every exact replica equals (d)'s value bitwise has error
exactly 0. It is excluded from M's z and reported as "exact". Every other pair is computed as
registered.

## 1. The defect, a property of the registered arithmetic

- **What `mean_error` computes.** It gives e = the mean over replicas − y_d, and SE from the
  replicas' SD (`np.nanmean` and `np.nanstd` down axis 0).
- **When every replica equals y_d bitwise,** the error and the spread are both 0. But the sum down
  axis 0 rounds, so:
  - e is a residue r of a few ulp (the checker found about 7 ulp at 100 nm);
  - every replica then deviates from the computed mean by the same −r, so SE = |r|/√(M − 1);
  - at a pair exact at both rungs, with r_(K−1) the lower rung's residue, M's excess is
    √(M − 1) (|r_K| − |r_(K−1)|/2)/(r_K² + r_(K−1)²/4)^½. That is up to √127 = 11.3 at M = 128,
    and it measures rounding alone.
- **At a count the registered arithmetic is already exact.** An exact count pair's value is an
  integer, and a sum of integers below 2^53 rounds nothing. So e and SE are exactly 0, and
  `criterion_m` takes a zero combined SE as an excess of 0. The defect is in A, V, σ and W_res.
- **The checker's finding at D6** (through the lead): V_L before the shear (t = 0.25, 0.5 and
  0.75 s) has all 128 replicas bitwise equal to (d), because the lumen is impermeant and the vesicle
  floppy (§9). M gave 10.47, against the fail threshold of 6. Without those pairs, D6's largest M
  excess is 2.293.

## 2. The rule

- **Exact** (`exact_pairs`). A pair (observable, time) is exact at a rung when (d)'s value there is
  finite and every exact replica's value has its bits.
  - The float64 words are compared as integers, so 0.0 and −0.0 differ.
  - A NaN is never exact. A replica, or the (d) run, that ended before the time makes the pair not
    exact.
- **Its error is exactly 0,** and it is reported as "exact". `mean_error` reports (e, SE) =
  (0, 0) there and the registered values at every other pair.
- **M at the top rung K against K − 1** (`criterion_m`):
  - **A pair exact at K** is excluded from M's z and reported as "exact". There e_K = 0, so the
    registered inequality |e_K| ≤ z*(SE_K² + SE_(K−1)²/4)^½ + |e_(K−1)|/2 holds whatever K − 1's
    terms are.
  - **Every other pair keeps the registered `mean_error` at both rungs,** a pair exact at K − 1 only
    among them, so its excess is bitwise the registered one. M judges e_K, and K − 1 enters only
    through its allowance.
  - **The verdict** is the registered `criterion_m` over the pairs left: the largest z, passing at
    most 4.5 and failing beyond 6.
  - **With no pair left,** every top-rung error is 0. The registered function's largest z is then
    −∞, and M passes.
- **Only bitwise agreement is exact.** A pair that differs anywhere by one ulp is judged as
  registered (§5 shows what that gives).

## 3. Where it applies

- **D3 and D5** are judged under it, and so is their retry (§10), if they take one.
- **D0:** it has nothing to act on.
  - D0 has one size (§2), and M takes the top two rungs.
  - P-D1's B (erratum 2) keeps the registered `mean_error`.
  - No D0 pair can be exact anyway: (d)'s side at the registered times is the fixed point
    (n_A*, n_B*) = (3.558…, 4.221…), which is not an integer, and D0's replicas are integers.
- **D6:** its registered verdict, a fail, stands. It is rescored under this erratum only as a
  labelled, non-blind diagnostic, by this erratum's own rule, the top rung's exactness.
  - That set is not the checker's own set behind 2.293, which dropped the pairs exact at both rungs.
  - It contains that set. So if the checker's set came from the same bitwise test on the registered
    values, the diagnostic's largest z is at most 2.293. That is this erratum's author's inference,
    not the checker's.
- **D1, D2, D4 and D7:** their passes stand, and they are not rescored.
  - The erratum only removes pairs from M's maximum, and leaves every other pair's excess bitwise as
    registered. So M's largest z can only fall.
  - Nothing else changes.
- **B is untouched.** It judges counts only (`is_count`). At an exact count, the registered
  `mean_error` already returns e = SE = 0 exactly (§1), and the replica part's |y_a − y_d| is 0.

## 4. D3's and D5's deterministic observables, from the code

An observable that the exact process holds fixed by construction could agree with (d) to within an
ulp, and not bitwise, only if the two representations reached it by different arithmetic. From the
code alone, before any run:
- **D3 has none.**
  - Its observables are its six enveloped counts, U0–U2 in the pool and in the membrane
    (`rate_equations.enveloped`), and its join steps move every one of them.
  - It has no geometry, so no A, V or σ, and no held place, so no W_res.
- **D5's observables** are L@pool, each slot's L@membrane, and each slot's A_m2, V_L and σ. I@lumen
  and I@pool are not among them: `enveloped` marks only a step's own places and, with a membrane
  locus or a geometry, the membrane's places, and no step moves I.
- **Deterministic by construction:** slot 1's V_L and σ (`slot1:V_L`, `slot1:sigma_N_per_m`; the
  floppy vesicle, x0 = 0.85), while it is floppy.
  - `lumen.log_volume` is the minimum of ln V_osm = ln N_L − ln(N_A c_ext) and ln V_sph(W). While
    floppy it returns ln V_osm, which reads N_L alone.
  - `lumen.tension` is exactly 0.0 unless the vesicle is tense.
  - N_L is I@lumen, which no event moves.
- **The same function on the same inputs.**
  - Both representations' values come from `limit_qualification.vesicle_derived(world, counts)`.
    It calls `lumen.log_volume` and `lumen.tension` with numpy, on N_L = counts·is_lumen, for the
    same world.
  - An exact replica's N_L is its founder's integer.
  - (d)'s N_L is that integer to the bit:
    - its derivative is `j @ nu_slot` over a zero column, so ±0;
    - while floppy (V_osm < V_sph), its Jacobian column is ±0 too. (d)'s μ is `jax.grad` of
      F_cont, and the osmotic term's W-derivative passes through `jnp.minimum`'s unselected
      branch, whose derivative is 0, so no rate reads N_L;
    - so in Rodas4's LU of I/(γh) − J, that column's only nonzero is its own diagonal. Every stage
      is ±0 there, and y + Σ b_j U_j keeps N_L;
    - each observation row is the state of the step that lands on the observation time
      (`integrate`'s hh = stop − t, then `row("observed")`), not the dense output, whose
      (1 − θ)N_L + θN_L need not be N_L to the bit. `_arrays` copies the slot block.
- **So slot 1's V_L and σ can only agree bitwise or differ for real.**
  - If both are floppy, the pair is exact.
  - If a slot 1 turned tense, its V and σ follow its own W.
  - So §5's one-ulp exposure cannot arise at them. The checker's D6 finding is the same mechanism
    in a single lineage, and §6 records the population layout run once on a made-up world.
- **Every other D5 observable reads W or the pool's count,** which the exact process draws. That
  covers A_m2 = qW/2, slot 0's V_L (V_sph(W) while tense) and σ, and the counts. Slot 0's N_L need
  not stay exact in (d), because its Jacobian column is not zero; it is not an observable.

## 5. The synthetic checks

`python -m validation.assembly_lineages_v2.protocol_d_erratum_3 check` runs them on made-up columns
only (128 replicas, 8 times, generator seed 3). Every check passed:
1. **A bitwise-equal column is excluded.** The column was exact at both rungs at the first three
   times.
   - Those three pairs were reported as "exact".
   - M's z over the other five was bitwise the registered function's over them, 0.873.
   - The registered function over all eight gave 11.27, which is the defect, at √127.
2. **One replica 1 ulp off,** with K − 1 exact, is computed as registered: z = 11.31, bitwise.
3. **Genuinely different columns** are unchanged: z = 0.565, bitwise.
4. **A pair exact at K − 1 only** is computed as registered: z = 0.441, bitwise.
5. **A NaN replica, or a NaN (d) value,** makes its pair not exact.
6. **(d) alone 1 ulp off,** with every replica equal and K − 1 exact, is computed as registered,
   bitwise, in both directions.
   - One ulp up gives z = 0, because the offset cancels the mean's rounding residue there
     (e = 0, SE > 0).
   - One ulp down gives z = 22.5, a fail.
7. **0.0 against −0.0** is not exact.
8. **Every pair exact at K:** none is judged, the largest z is −∞, and M passes.
9. **The reported errors** are (0, 0) at the exact pairs and bitwise registered elsewhere.
   - The registered residues at those pairs were 1.1 × 10⁻¹⁶ to 2.1 × 10⁻¹⁵.
   - At an exact count, the registered `mean_error` is already exactly (0, 0).

**What the registered arithmetic gives at pairs this erratum leaves as registered.** These come from
`information`, on made-up values. They are disclosed, and not changed, since nothing else changes
(§7). Each pair has K − 1 exact, over 200 values from 0.1 to 10:
- **One replica 1 ulp off:** z ran from −11.2 to 11.3, with a median of 5.05. 129 were beyond 4.5
  and 82 beyond 6.
- **(d) alone 1 ulp up,** every replica equal: z ran from −8.0 to 33.8, with a median of 7.5. 116
  were beyond 4.5 and 102 beyond 6.
- **(d) alone 1 ulp down:** z ran from −9.4 to 33.8, with a median of 5.6. 107 were beyond 4.5 and
  97 beyond 6.
- **So rounding alone** can put a pair that agrees to within one ulp in the retry band, or fail it.

**A zero combined SE is taken as no limit.**
- **When it is zero.** From the formula, the combined SE is exactly 0 only where both rungs' SE are
  0. That means every replica is equal at each rung and each rung's sum leaves no residue (barring
  an underflow of SE², far below these observables' rounding).
- **That holds at every integer- or zero-valued pair:**
  - at the counts, which B judges;
  - at a floppy vesicle's σ, exactly 0.0, which B does not judge (B reads counts only).
- **It also holds, by rounding luck, at other values.** On made-up values from 10⁻²⁵ to 10² in the
  observables' [M, 8] layout, a single rung's constant column had SE exactly 0 in 159 of 4,000 cases
  at M = 128 and 72 of 4,000 at M = 256. A zero combined SE needs it at both rungs.
- **What M then does.** Replicas all at 1.0 against (d) at 2.0, at both rungs, give z = 0. So M does
  not judge a zero-SE pair. The lead has asked the checker to list every zero-SE, nonzero-error pair
  by name in each world's verdict.
- **In D5** this could happen at slot 1's σ, if (d)'s slot 1 turned tense while every replica stayed
  floppy. Slot 1's V_L at that time would differ for real, and fail M unless its sums leave no
  residue.

## 6. What had been seen (disclosed, added to §12)

- **Known, from the checker through the lead:**
  - D1, D2, D4 and D7 pass as registered;
  - D6 fails M as in §1;
  - nothing of D0, D3 or D5 has been computed.
- **This erratum's author** read none of the checker's outputs and ran no world of the protocol,
  exact or (d). Its probes and checks of the registered functions ran on made-up columns only.
- **§4 is from the code alone.** No D3 or D5 run, exact or (d), was made or read for it.
- **The population layout, run once on a made-up world.**
  - The files are `/mnt/workspaces/Cells/ol6-20261122/dev/erratum3/slot_probe.py` and its `.log`.
  - The world has two slots at 40 nm, with founders at x0 = 1.3 and 0.8. These are not D5's
    diameters or founders. Only its founder state was used, and no time integration was run.
  - The floppy slot's I@lumen has an all-zero Jacobian row and column. The tense slot's has an
    all-zero row and a column of at most 2.0 × 10⁻².
  - One Rodas4 step at h = 10⁻⁶, 10⁻³, 10⁻¹ and 1 s kept both slots' I@lumen to the bit.

## 7. What does not change

- B, P, E, L and N.
- z* = 4.5 and the fail threshold of 6.
- Every world, time, scale, plant and tolerance.
- The retry (§10).
- M at every pair that is not exact at its top rung.
