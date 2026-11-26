# OL6 Protocol D, erratum 2: P-D1's (d) side from its closed form, and P-D2's plant process (registration)

**Status: proposed for the lead's tag, 23 November 2026, before the checker opens any honest
comparison.** Docs and validation only, with no src change. Branch `ol6-protocol-d-erratum-2` from
main 81a98ca0. The proposed tag is `ol6-protocol-d-erratum-2-2026-11-23`.

**What it amends.** Protocol D as tagged at `ol6-protocol-d-registered-2026-11-23`, with erratum 1
(`ol6-protocol-d-erratum-1-2026-11-23`).
- The three registered files and erratum 1 are still read byte for byte as tagged, and none is
  edited.
- This erratum adds two files:
  - this document, the authority where it speaks;
  - `validation/assembly_lineages_v2/protocol_d_erratum_2.py`, its arithmetic.

**The user's decision.** B reads P-D1's (d) side from the registered closed form,
`limit_qualification.d0_stationary`, recorded as `pd1_closed_form` in protocol_d.json, in place of
the refused (d) run.

## 1. What the checker found, in (d) alone

No honest comparison had been computed or opened. The facts below reached this erratum's author
through the lead.
- **P-D1, the envelope disabled on D0** (`min_count` 1).
  - The planted (d) run was made at the registered integrator (rtol 1e-10, atol_count 1e-6), in a
    fresh process at 3e50d48d.
  - It is refused by its own books: "the ledger did not close". The residual is 7.26 × 10⁻⁸ k_BT
    from the first observation row (t = 5 s) to the end, against the closure tolerance of
    1.00 × 10⁻⁸, whose floor is 100·rtol.
  - It returns no rows, so B's replica part, P-D1's registered catch (§8), cannot be computed from
    it.
- **Honest D0** is refused at parse at `min_count` 10, as registered (§6). So there is no honest D0
  (d) run.
- **P-D2(ii)**, with the world's own check off.
  - In a fresh process, `plant_scope("P-D2", check=False)` replaces `rate_equations.limit_check` with
    a stub that returns a float.
  - The cached generic verdict, if it is first computed inside the scope, reads
    `worst["identity"]` from that float (rate_equations.py:842) and fails. §3 states the remedy.
- **The other plants ran as registered.**

## 2. P-D1 under this erratum

- **The (d) side** (`pd1_d_side`). At each of D0's eight registered times (5 to 40 s, §2) it is the
  closed form's rate-equation fixed point:
  - n_A* is `fixed_point_n_A`, 3.5584219849035215 (protocol_d.json);
  - n_B* = (T − n_A*)/2 follows from D0's conservation law T = n_A + 2 n_B, with T = 12.

  At the start it is the founder, (n_A, n_B) = (4, 4), which is (d)'s own first row.
- **The rule for the times, fixed now.** The closed form gives D0's stationary law and the fixed
  point, not (d)'s path.
  - §2 registers D0's times as 5 to 40 s, every 5 s, at least 7 relaxation times apart, and the
    first comes 5 s after the start, the same spacing. So at every registered time (d)'s path is
    at its fixed point, up to a relaxation remainder that this rule sets to zero.
  - It is the rule §8's registered effect already used: |8 − 3.558|/4.
- **The scales**, by §3's rule applied to that side: s_A = max(4, n_A*) = 4, and
  s_B = max(4, n_B*) = n_B*.
- **The exact side.** D0's 256 exact replicas: seeds 1 to 256, environment 0, lineage 0, branch 0
  (§2). They are read at the registered times by `limit_qualification.observables`, which gives
  A@pool and B@pool, each [256, 8].
- **B.** `criterion_b_at(exact, d, mean_error(exact, d), scales, n_k)`.
  - n_k is n_min from §6's rule over the protocol's worlds.
  - When §6 gives no n_min, n_k = 98, the smallest value n_min can take (§6). The replica budget
    c_r/√n_k is largest there, 0.505.
- **Caught** when B's replica part fails (`spread_passes` false), as §8 registers. The mean part is
  reported and never judged (§8).
- **The arithmetic** is `protocol_d_erratum_2.pd1_b(exact, n_min)`. It adds no number, and it
  judges with `limit_qualification`'s registered functions (`d0_stationary`, `D0`, `scales`,
  `mean_error`, `criterion_b_at`).
- **One attempt.** P-D1 is computed once under this erratum, on D0's first seed set, at the head of
  the checker's D0–D6 reading. It has no retry and no second (d) run. The refused run's outcome
  stays in the record as found.

- **L and the planted run (the lead's ruling).** §5.5's L judges the honest worlds' (d) runs.
  - A planted run refused by its own books is a plant outcome, recorded as found, and not a fail
    of L.
  - P-D6's registered catch is exactly such a refusal.
  - P-D1's refused run stays in the record as its found outcome.
- **When §6 gives no n_min** (the lead confirmed): n_k = 98, the strictest case, fixed before any
  reading.

## 3. P-D2(ii)'s plant process (the lead's ruling)

- **The step.** The plant process computes `rate_equations.verdict()`, the cached generic verdict,
  before it enters `plant_scope("P-D2", check=False)`. Inside the scope the cached verdict is read
  and the stub never reaches it.
- **Reproduced by the checker.** The effect is 0.20764924410295305 of scale, bit for bit the
  registered `plant_power_d_alone["P-D2 (check off)"]`.
- **Nothing else moves.** The registered driver is unchanged; the order is a step of the plant
  process.

## 4. What had been seen (disclosed, added to §12)

- **Known:** §1's plant outcomes, in (d) alone, from the checker through the lead.
- **Not computed:** no honest comparison of (d) with exact events had been computed or opened, by
  the checker or by anyone.
- **This erratum's author** (OL6's fourth builder) read none of the checker's outputs.
- **The adapter's checks:**
  - its `check`, the closed form's (d) side and scales, which runs nothing;
  - its arithmetic on synthetic arrays only:
    - 256 replicas at the fixed point are not caught;
    - 4 of 256 replicas at n_A = 8 at one time are caught;
    - the wrong keys or columns are refused.

## 5. What does not change

- D0–D7's worlds, every criterion and tolerance, and every other plant.
- P-D1's registered effect and closed form (§8; protocol_d.json's `pd1_closed_form` and
  `plant_power_d_alone`).
