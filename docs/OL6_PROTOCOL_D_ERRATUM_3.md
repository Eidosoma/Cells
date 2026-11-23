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
  - M's excess at the pair is √(M − 1) (|r_K| − |r_(K−1)|/2)/(r_K² + r_(K−1)²/4)^½. That is up to
    √127 = 11.3 at M = 128, and it measures rounding alone.
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
  registered (§4 shows what that gives).

## 3. Where it applies

- **D3 and D5** are judged under it, and so is their retry (§10), if they take one.
- **D0:** it has nothing to act on.
  - D0 has one size (§2), and M takes the top two rungs.
  - P-D1's B (erratum 2) keeps the registered `mean_error`.
  - No D0 pair can be exact anyway: (d)'s side at the registered times is the fixed point
    (n_A*, n_B*) = (3.558…, 4.221…), which is not an integer, and D0's replicas are integers.
- **D6:** its registered verdict, a fail, stands. It is rescored under this erratum only as a
  labelled, non-blind diagnostic.
- **D1, D2, D4 and D7:** their passes stand, and they are not rescored.
  - The erratum only removes pairs from M's maximum, and leaves every other pair's excess bitwise as
    registered. So M's largest z can only fall.
  - Nothing else changes.
- **B is untouched.** It judges counts only (`is_count`). At an exact count, the registered
  `mean_error` already returns e = SE = 0 exactly (§1), and the replica part's |y_a − y_d| is 0.

## 4. The synthetic checks

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
6. **(d) alone 1 ulp off,** with every replica equal, is computed as registered: z = 0, bitwise.
7. **0.0 against −0.0** is not exact.
8. **Every pair exact at K:** none is judged, the largest z is −∞, and M passes.
9. **The reported errors** are (0, 0) at the exact pairs and bitwise registered elsewhere.
   - The registered residues at those pairs were 1.1 × 10⁻¹⁶ to 2.1 × 10⁻¹⁵.
   - At an exact count, the registered `mean_error` is already exactly (0, 0).

**What the registered arithmetic gives at pairs this erratum leaves as registered.** These come from
`information`, on made-up values. They are disclosed, and not changed, since nothing else changes
(§6):
- **One replica 1 ulp off,** with K − 1 exact, over 200 values from 0.1 to 10.
  - z ran from −11.2 to 11.3, with a median of 5.05.
  - 129 were beyond 4.5 and 82 beyond 6.
  - So rounding alone can put such a pair in the retry band, or fail it.
- **A zero combined SE is taken as no limit.** This happens where the replicas are all equal at
  both rungs and their sum rounds nothing.
  - Replicas all at 1.0 against (d) at 2.0 give z = 0, and that is why check 6 gives 0.
  - For counts, B judges such a pair.

## 5. What had been seen (disclosed, added to §12)

- **Known, from the checker through the lead:**
  - D1, D2, D4 and D7 pass as registered;
  - D6 fails M as in §1;
  - nothing of D0, D3 or D5 has been computed.
- **This erratum's author** read none of the checker's outputs and ran no world of the protocol,
  exact or (d). Its probes and checks of the registered functions ran on made-up columns only.

## 6. What does not change

- B, P, E, L and N.
- z* = 4.5 and the fail threshold of 6.
- Every world, time, scale, plant and tolerance.
- The retry (§10).
- M at every pair that is not exact at its top rung.
