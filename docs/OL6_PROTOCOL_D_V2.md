# OL6 Protocol D, version 2: the re-registration, with M repaired by the shared rule (registration)

**Status: proposed for the lead's tag, 24 November 2026, before any run of its comparison.** Docs and
validation only, with no src change. Branch `ol6-protocol-d-v2` from main 0661ccf5. The proposed tag
is `ol6-protocol-d-v2-registered-2026-11-24`. Its message names the seed ranges of §3.

**The decisions it follows.**
- **D318 (the user, 23 November):** Protocol D is re-registered after FR-43, with M repaired and
  fresh seeds. The first verdict and its diagnosis stay on record, and are not quoted here (§10).
- **D323's R12:** every pair is classified from the reference before the run, by one rule shared with
  FR-47 (`validation/assembly_lineages_v2/agreement.py`):
  - `constant`: every replica must match exactly, and one wrong replica fails;
  - `derived`: a tolerance only where it is derived, as release_check's is;
  - `spread`: identical replicas still face the spread test.

  There is no declared rounding floor. An excluded pair is justified from the model, not from the
  replicas.
- **D334:** FR-38's second comparison uses the same agreement.py and queues behind this protocol's
  run.

**What the tag holds.** It holds these files, read byte for byte as tagged:
- **This document:** the authority for the re-run.
- **`validation/assembly_lineages_v2/protocol_d_v2.py`:** its arithmetic, namely the seeds, the
  classification, M repaired, the precondition and the world's verdict, the linear-noise variance,
  P-D8 and the checks.
- **`validation/assembly_lineages_v2/protocol_d_v2.json`:** its numbers, namely the seeds and the
  earlier ranges, (d)'s margins and the linear-noise table at them, the classification table, the
  plant it adds and the cost.
- **The registered arithmetic it judges with, unchanged since its own tags:**
  - `limit_qualification.py` and `protocol_d.json`, from `ol6-protocol-d-registered-2026-11-23`;
  - `protocol_d_erratum_2.py`, from `ol6-protocol-d-erratum-2-2026-11-23`;
  - `agreement.py`, from `fr47-shell-exchange-registered-2026-11-24`.

**Everything not stated here is as registered.** That is `docs/OL6_PROTOCOL_D.md`, with errata 1
and 2 folded in as §7 says. Erratum 3 is superseded by §5. Where this document speaks, it is the
authority.

**Engine models (AGENTS.md).** These are unchanged from the first registration:
- **The representation under test:** `cells.rate_equations@1` (`rosenbrock_rodas4_dense@1`), with
  D309's clock bound.
- **The detailed form:** `cells.assembly_lineages@2`'s exact events.
- **Each world's laws:** as protocol_d.json's `engine_models` lists them.

**The engine under test.** The checker runs at the first main head after the tag, with the tagged
files unchanged.
- It records that revision, and every file of `src/cells/models/assembly_lineages_v2/` changed since
  3e50d48d, the first check's head, with each landing's D148 proofs.
- FR-47's (d) paths (the shell, washes, E2 and the gate factor) are absent from D0–D7 by
  construction. No world here has a prescribed shell, a wash or an E2 place, and the representation
  refuses each outside a shell's world.
- FR-47's landing ran four existing (d) worlds on main and on its head, and they were bitwise equal.
- FR-47's inert-wall fix (branch `fr47-inert-wall`, to land after main 1e40fc16) makes the
  envelope's mask precise. The registered reader takes its count keys from that mask. The fix leaves
  every mask of D0–D7, at every rung, as it was. §10's own check verifies that at the run's head.

## 1. Why M is repaired

**The defect is arithmetic, and the model predicts where it can arise.** Erratum 3's §1 gives the
mechanism:
- the registered `mean_error` takes e as the mean over replicas minus y_d, and SE from the replicas;
- at a pair where every exact replica equals (d)'s value bit for bit, the sum down the replicas
  leaves a rounding residue r. Then e = r and SE = |r|/√(M − 1);
- so M's z measures rounding alone, up to √(M − 1) = 11.3 at M = 128.

The registered code also has the reverse defect. Where the combined SE is exactly 0, `criterion_m`
divides by infinity, so a nonzero error there passes as "no limit" (erratum 3 §5).

**The repair, from the shared rule:**
- the model marks, before any run, the pairs at which every exact replica holds one value (§4);
- those pairs are judged by the constant rule: every replica and (d)'s value bit for bit, with no
  sample statistic, so no rounding can pass or fail them;
- every other pair keeps the registered statistic. Where its combined SE is 0, the registered
  inequality is evaluated exactly instead of by division (§5);
- where a spread pair's replicas are identical, their mean and SE are taken exactly, so that the
  zero-SE path is reached at all (§5). The registered sum's residue would otherwise keep SE above
  0 and give z = ±√(M − 1) there.

## 2. What changes, completely

1. **The seeds (§3).** Fresh ranges that no run has used, disjoint from every earlier one.
2. **M's pairs are classified from the model before any run (§4).** The constant pairs are
   D5's floppy slot's V and σ, and D6's σ, plus D6's V before the shear. Every other pair is
   spread. None is derived. The linear-noise variance predicts that no replica turns tense at a
   constant pair (§4.3).
3. **M's rule (§5).** Constant pairs take the constant rule, and spread pairs take the registered
   excess, evaluated exactly at a zero combined SE, with identical replicas' moments taken exactly.
4. **A precondition for the constant pairs, judged first (§6).** The vesicle is floppy in every run
   at those times, recomputed from the recorded counts. Otherwise those pairs are not judged and
   the world is inconclusive, with its tense runs counted.
5. **The errata are folded in (§7).** Erratum 3 is superseded. A clock-bound refusal is stated.
6. **One plant is added, P-D8 (§8, §12):** one ulp in (d) alone on D6, which M's constant rule must
   catch.
7. **The checks before the tag (§8).** These are the reader on invented inputs, M and the world's
   verdict on made-up columns, the zero-SE path on the registered constants, the classification,
   the seeds and the parse.
8. **The cost and who checks (§9, §10).**

Nothing else changes (§12). That covers the worlds, rungs, times, horizons, replicas, integrators,
envelope, scales, criteria P, B, E, L and N, n_min's rule, the registered plants and their
registered effects, the other preconditions, the verdicts and the retry rule.

**Superseded, each with its replacement.** A checker using the registered functions takes these from
this registration, never from the first:

| In the first registration | Use instead |
| --- | --- |
| `limit_qualification.SEED_BASE` and `limit_qualification.seeds` (seeds 1 and 100001 onward) | `protocol_d_v2.SEEDS` and `protocol_d_v2.seeds` (§3) |
| protocol_d.json's `constants.ladder.seeds` | protocol_d_v2.json's `seeds` |
| §2's "Seeds: 1 to M ... the retry's seeds are 100001 to 100000 + M" | §3 |
| §7.4's convergence seeds 1–6 | 670001–670006 (§3) |
| Erratum 2's "seeds 1 to 256" for D0 (P-D1) | D0's first seeds here, 670001–670256 |
| `limit_qualification.criterion_m` for M's verdict | `protocol_d_v2.criterion_m` (§5); `limit_qualification.mean_error` stays its input |
| Erratum 3, its document and `protocol_d_erratum_3.py` | §4 and §5 |
| §11's cost (2–3 CPU-hours) | §9 |

## 3. The seeds

- **First seeds:** 670001 to 670000 + M, with environment 0, lineage 0 and branch 0. M is 256 for
  D0–D3 and 128 for D4–D7.
- **Retry seeds**, once and for inconclusive worlds only: 690001 to 690000 + M.
- **D7's clock convergence (§7.4 of the first registration)** reads the first six seeds of the set
  it checks: 670001–670006.
- **D2's β generator seed, 20261124,** is a world input and stays as registered.
- **Unused, as far as the record shows.**
  - The author has run nothing on either range, and nothing will be run on them before the
    comparison. In particular, D7's (d) runs are not pre-screened for the clock bound (§7).
  - No number of either range appears anywhere in the repository (docs/, validation/, tests/,
    src/ and scripts/), in any context.
  - Nor does any appear as a number in the run folders of OL6 and FR-46 to FR-48 under
    /mnt/workspaces/Cells (JSON, Python, shell and Markdown files; searched 24 November). The only
    matches there are digits after the decimal point of five timestamps' seconds.
- **Why the ranges moved from those proposed at dbf17e84 (640001 and 740001).** A (d) run of D7
  consumes its seed. Its pore threshold is drawn from the replica's own stream:
  - `_Run.__init__` (rate_equations.py:1472): `self.base_key = streams.base_key_data(x.seed,
    x.environment, x.lineage, x.branch)`;
  - `_Run.draw_threshold` (rate_equations.py:1517): `u, energy = pore_clock.threshold(
    self.base_key, key, 0)`;
  - `pore_clock.threshold` (pore_clock.py:70–74): domain 7 (`"pore"`), the vesicle's key, counter 0.

  So **the D7 clock-room probe** (§8, §11), which ran D7's (d) alone on 640001–640128 at all three
  rungs, 384 runs, probed the first range proposed at dbf17e84. The retry range proposed there,
  740001–740256, was never run. Both are withdrawn, and both are now earlier ranges.
- **A second move, before any run.** The ranges first chosen after that, 540001 and 560001, were
  dropped unused: a repository search found those numbers as world identifiers of an unrelated
  assay design (`validation/assays/channel_compensation_design.py`).
- **Disjoint from every earlier range the author could find** (`EARLIER_SEEDS`, checked by
  `seeds_disjoint`): those registered in docs/ and validation/, those the decisions name, and the
  probes' and smokes' seeds the author knows. A range used only in an unrecorded run is outside
  what this check can see. A range recorded with no upper end is taken as open.

| Range | Seeds |
| --- | --- |
| Protocol D, first and retry | 1–256, 100001–100256 |
| Protocol G (its @1 1001–1256 and @2 2001–2256 among them) | 1–5256 |
| Protocol G's matrix seeds | 20261123–20261142 |
| Protocol G's checker, unregistered timing smokes ("900001+", disclosed in D322) | 900001 onward, open |
| FR-47, first (W1, W1Δ, W2's rungs, P7, P8) | 470001–471528 |
| FR-47, retry (W2's are the first plus 500,000) | 970001–971528 |
| The probes' and smokes' stream seeds | 1 and 7 |
| This registration's ranges as proposed at dbf17e84, withdrawn: the D7 clock-room probe's 640001–640128 within the first | 640001–640256, 740001–740256 |
| The noise check, exact events on an unregistered 12.5 nm D5 (§4.3) | 1–128 |

## 4. The classification, from the model before any run

### 4.1 The rules (`classify`)

The pairs are the observables M reads (`reader_keys`, the registered reader's keys, from the world
alone) at the registered times. A pair is `constant` only where the model holds every exact replica at
one value:

- **σ of a vesicle is constant, 0.0**, at a time when two things hold:
  - no step moves the vesicle's lumen;
  - (d)'s vesicle is floppy there.

  `lumen.tension` returns `xp.where(tense, …, 0.0)`, exactly +0.0, while floppy.
- **V of such a vesicle is also constant** at such a time, provided no operator has acted on it yet.
  - Its lumen count is then the founder's integer in every exact replica, since no event moves it.
  - While floppy, `lumen.log_volume` is the minimum of ln V_osm(N_L) and ln V_sph(W), and returns ln
    V_osm's bits, which read N_L alone.
  - So V is V_osm(N_L0) in every replica, whatever its W.
  - The value is the registered reader's own function at the founder, `vesicle_derived`.
- **(d) holds the same bits.** Erratum 3's §4 gives the argument from the code:
  - while floppy, (d)'s lumen count has a zero derivative and a zero Jacobian column, so every
    Rodas4 stage leaves it unchanged;
  - an observation row is the landed step's state, not the dense output.
- **Every other pair is spread:**
  - each count is moved by a step;
  - each A reads a footprint that the exchange moves;
  - W_res is a stochastic integral;
  - D4's lumen takes up its permeant S, so its V and σ move. Its tension's kink is crossed by each
    replica at its own time, so a pre-kink σ is a mixture of the floppy 0.0 and a tense value;
  - D6's V after the shear: the exact shear splits the lumen by a multinomial draw (division.py,
    rule 10, on the parent's fission stream), so the followed daughter's lumen count, and its V,
    vary between replicas. Its σ stays 0.0 while it is floppy (§4.2).
- **No pair is derived.** A derived pair is one constant reached by two routes of different
  arithmetic. Here every constant is reached by the same function on the same bits, in both
  representations.

### 4.2 The table (`classification_table`, protocol_d_v2.json)

| World | Constant pairs, at every rung | Value |
| --- | --- | --- |
| D1, D2, D3, D4 | none | — |
| D5 | slot 1's V and σ (the floppy vesicle, x0 = 0.85, lumen I only), at all 8 times | V_osm of slot 1's founder lumen; 0.0 |
| D6 | V at 0.25, 0.5 and 0.75 s, before the shear | V_osm of the founder's lumen |
| D6 | σ at all 8 times (the vesicle, then its floppy daughter at v ≈ 0.85) | 0.0 |

- **M reads the top two rungs,** 50 and 100 nm, so its constant pairs are 16 in D5 and 11 in D6.
- **D0** has one size, so M does not apply. Its B, through P-D1, reads counts. **D7** is judged on its
  paired event only.
- **B is unchanged.** It reads counts only, and no count is constant.

### 4.3 Why the vesicles stay floppy: (d)'s margins and the linear-noise variance

A constant pair needs its vesicle to be floppy at that time in every exact replica.
- **The margin** is (d)'s ln V_sph − ln V_osm at each registered time. The author's (d)-alone runs of
  the registered definitions give it (`d_margins`).
- **The exact process's spread about it** is the model's linear-noise approximation (van Kampen)
  about (d)'s own trajectory (`linear_noise` and `noise_table`; `linear_noise` in the JSON):
  - dΣ/dt = AΣ + ΣAᵀ + D, from Σ = 0 at the fixed founder. A is the drift's Jacobian. D sums
    (a⁺ + a⁻)·ννᵀ over every step's two directions. Both come from the engine's own `Problem` at
    (d)'s states. The drift built from those directions matches the engine's right-hand side to
    between 2 × 10⁻¹⁶ and 2 × 10⁻¹⁴, relative.
  - (d) is rerun alone with a fine grid of observation rows: 0.1 s in D5 and 0.01 s in D6. Each
    interval is solved exactly (Van Loan) with A and D at the mean of its two ends.
  - **D6's shear:** (d) gives the followed daughter half the vesicle. The exact split cuts a
    one-species membrane at equal areas (division.py, rule 9: variance at most 1/4), and sends each
    lumen molecule to the daughter with p = 1/2 (rule 10: variance N_L/4). The lumen's binomial
    dominates the daughter's spread, so the table also gives its exact binomial tail.
  - **Checked against exact events** on an unregistered variant: D5 at 12.5 nm, with 128 exact
    replicas (seeds 1–128, §3). Only spreads were formed, with no mean against (d).
    - At the 8 registered times, the ratio of the exact SD of slot 1's margin to the linear-noise
      SD runs from 0.92 to 1.06. Each ratio's sampling SE is 0.063.
    - No replica was tense.
- **The rough random-walk estimate proposed at dbf17e84 is withdrawn.** It ignored the shared pool's
  coupling between the vesicles, and overstated D5's SD at 100 nm by 1.6×.

**The result.** Each world's smallest margin over its constant times, in units of the linear-noise
SD (z), and the chance that any of its 128 replicas is tense at a constant time. That chance is the
union over the constant times, 1 − (1 − Σ_t p_t)^128, with Gaussian p_t:

| Vesicle | 25 nm | 50 nm | 100 nm | Where |
| --- | --- | --- | --- | --- |
| D5's slot 1 | z 10.3; 7 × 10⁻²³ | z 14.9; 2 × 10⁻⁴⁸ | z 9.7; 1.8 × 10⁻²⁰ | at 60 s; margins 0.120, 0.084 and 0.026, the floppy slot losing amphiphile to the tense one |
| D6 | z 4.9; 3.6 × 10⁻⁴ (by the lumen's exact binomial, drawn once at the shear: 6.7 × 10⁻⁶) | z 13.7; 2 × 10⁻⁴⁰ | z 38.4; below 10⁻³⁰⁰ | after the shear, margin 0.164; before it, 0.511 at z of 338 or more |

- **M reads 50 and 100 nm.** There the largest chance is 1.8 × 10⁻²⁰, at D5's 100 nm rung.
- **The lead's rule:** above 1 in 20, the late pairs at thin margins would have been classed spread
  from the model before the tag. No chance comes near it, so §4.2's classification stands.
- **At 25 nm,** which M does not read, D6's chance is at most 3.6 × 10⁻⁴.
- **§6 still guards the claim.** A tense replica makes its world inconclusive, never a pass.

## 5. M, repaired (`criterion_m`)

At the top rung K against K − 1, each rung's observables as the registered reader gives them:
- **A constant pair at K** is judged by the constant rule at K, and at K − 1 where it is constant there
  too. `agreement.judge_constant` takes every exact replica, and (d)'s value must have the model's
  bits.
  - One replica off, or (d) off, fails M.
  - A NaN, from a run that ended before the time, is not the constant.
  - 0.0 and −0.0 differ.
  - A constant pair is not in M's z.
- **Every other pair is spread.** It takes the registered excess,
  (|e_K| − |e_(K−1)|/2)/(SE_K² + SE_(K−1)²/4)^½ (`spread_excess`), on `moments` at both rungs. That
  is the registered `mean_error`, except at identical replicas.
  - **Identical replicas take exact moments.** Where at least two replicas are finite and every
    finite replica holds one value bit for bit, e is that value minus y_d, one subtraction, and SE
    is 0.
  - **Why:** the registered sum leaves its rounding residue r there, so SE = |r|/√(M − 1) stays
    above 0 and z = ±√(M − 1) = ±11.27. The zero-SE path below is then never reached.
  - **The lead asked for this to be verified** before any pair could be classed spread on a thin
    margin. At dbf17e84 it failed. §8's check takes the 54 constant pairs M reads as identical
    replicas at their registered values, with (d) at them. The registered `mean_error` leaves a
    residue at 14 of them (D5's V at 50 nm, D6's V at 50 and 100 nm), each at z = 11.27. With
    `moments` all 54 give SE 0, e 0 and an excess of −∞.
  - **Where the combined SE is exactly 0,** the registered inequality |e_K| ≤ z*·0 + |e_(K−1)|/2 is
    evaluated exactly. Where it holds the excess is −∞, and where it does not it is +∞, a fail.
    - Identical replicas at (d)'s bits at both rungs pass.
    - Identical replicas one ulp off (d)'s at the top rung, with K − 1 exact, fail.
    - The registered code's division by infinity, which took any such pair as "no limit", is gone.
  - **Identical replicas are not excluded.** At a spread pair they are judged, exactly, by the
    registered inequality. No pair here is expected to have them: §4 marks every pair where the
    model holds the replicas at one value constant.
  - Away from identical replicas, the z is bitwise the registered one (§8).
  - A NaN term, at a time after a run's end, enters no maximum, as registered.
- **The verdict:**
  - M **passes** when every constant pair passes and the largest spread z is at most 4.5;
  - it **fails** when a constant pair fails, or the largest z passes 6;
  - otherwise it is **inconclusive**.
  - With no spread pair, the largest z is −∞.
  - z* = 4.5 and the fail threshold of 6 are as registered.
- **The false-alarm bound of §5.2 stands** for the spread pairs. The constant rule adds no false
  alarm while §6's precondition holds, since under it every replica and (d) have the model's bits.

## 6. The constant pairs' precondition, judged first (added to §9 of the first registration)

- **At the rungs M reads,** at every time of a constant pair, the vesicle is floppy in every exact
  replica and in (d): ln V_osm < ln V_sph by the engine's own `lumen.log_branches`.
- **It is recomputed from the recorded counts alone.**
  - `floppy_margins` takes N_L and W from each run's rows, as the reader does.
  - It reads no σ, no V and no flag of the run.
  - So a replica whose counts are floppy is judged by the constant rule, whatever its σ or V. A
    wrong replica cannot read as tense and escape that rule.
  - Only a finite margin at or below 0 is tense. **A run with no row at a time** (it ended before
    it) has no counts there, so it is not called tense. Its pairs stay judged, and its missing value
    is not the constant (§5): one wrong replica fails, as the first registration fails a censored
    replica. A (d) run that did not end as registered is §9's own precondition, judged before M.
- **`judge_world` judges it first, at each rung.** At a time where any run's vesicle is tense by its
  counts, that vesicle's constant pairs are not judged: neither the constant rule nor the z sees them. The
  world then:
  - **fails** when M fails on what is judged: a judged constant pair is off, or the largest z is
    beyond 6;
  - otherwise is **inconclusive** when the precondition fails anywhere, or M is inconclusive;
  - otherwise **passes**.
- **One wrong replica still fails, and a tense one gives inconclusive, never a pass.** That is as far
  as "one wrong replica fails" softens (the lead's ruling). Anything further would change the shared
  rule, which is the user's decision.
- **An inconclusive world bars the protocol's pass,** which needs every world to pass (§10 of the
  first registration).
- **It is final after the retry.** The retry reruns an inconclusive world once, on the retry seeds
  (§3).
  - If the precondition fails again, the world stays inconclusive, and so does the protocol. It
    cannot pass.
  - The retry's "the bands then fail" applies to the criteria's bands, such as M's z between 4.5
    and 6. It does not apply to a precondition.
- **The judge reports, per world and rung:**
  - the tense counts: the exact replicas with a vesicle tense at a constant time, whether (d) is,
    and the count at each (vesicle, time);
  - the constant pairs left unjudged.
- **§4.3 predicts no tense replica** at the rungs M reads. So the precondition guards the model's
  claim; it is not expected to act.

## 7. The errata, folded in

- **Erratum 1 (D309's clock bound): in force.**
  - The bound is in the engine, |U^H| ≤ 1 × 10⁻¹⁰ + 2 × 10⁻³ |ΔH| per vesicle and accepted step.
  - D7 runs as registered.
  - §7.4's convergence runs at rtol 1e-13 take atol_count 1e-10.
  - **What a clock-bound refusal means.** A D7 (d) run refused by D309's bound is inconclusive
    (numerics) for its replica, never a fail (§7.1 of the first registration, and erratum 1).
    - It makes D7 inconclusive (§10 of the first registration), so the protocol cannot pass.
    - D7 is then rerun once, on the retry seeds. A refusal there leaves D7 inconclusive, and that
      is final.
    - The seeds are not pre-screened for it. No (d) run of D7 is made on either range before the
      run (§3).
- **Erratum 2: in force.**
  - **P-D1's (d) side** is the closed form's fixed point (`protocol_d_erratum_2.pd1_b`).
  - **P-D1's n_k:** when §6 of the first registration gives no n_min, n_k = 98. It is computed once,
    on D0's first seed set of this registration.
  - **P-D2(ii)'s process** computes `rate_equations.verdict()` before it enters
    `plant_scope("P-D2", check=False)`.
  - **A planted run refused by its own books** is a plant outcome, recorded as found, and not a fail
    of L.
- **Erratum 3: superseded by §4 and §5.**
  - Its rule excluded a pair exact at the top rung, a judgement made from the replicas.
  - Here the model marks the pairs before any run.
  - Its §4, the code argument for D5's floppy slot, is §4.1's justification of (d)'s bits.

## 8. The checks, before the tag (`python -m validation.assembly_lineages_v2.protocol_d_v2 check`)

They use invented inputs and made-up columns only, the registered constants, and the parse of the
registered definitions. No world is run. All 28 pass, in about 3 s:

- **Seeds:** every seed of every world and both sets lies outside every earlier range of §3,
  including the withdrawn ones and the open range from 900001.
- **M on made-up columns** (128 replicas, 8 times):
  - **constant pairs** are judged by the constant rule. The rest give a z bitwise equal to the
    registered `criterion_m` over the same columns, −0.13. Over every column, the registered
    function gives 11.27, the artifact;
  - **a constant pair fails** with one replica 1 ulp off, with (d) 1 ulp off, with −0.0 against
    0.0, and with a NaN replica;
  - **zero SE:**
    - identical integer replicas at (d)'s value give z = −∞, a pass;
    - identical integer replicas off (d) give z = +∞, a fail. The registered code gave 0.0 there,
      "no limit";
  - **identical non-integer replicas at a spread pair are judged exactly:** at (d)'s bits at both
    rungs z = −∞, a pass; all one ulp off at the top rung z = +∞, a fail. The registered
    `mean_error` gave 11.27 on the same columns;
  - **genuine spread columns** give a z bitwise equal to the registered one;
  - **an observable without a class is refused.**
- **The zero-SE path on the registered constants** (§5): every constant pair M reads, 54 in all, as
  128 identical replicas at its registered value with (d) at it. `moments` gives SE 0, e 0 and −∞
  at all 54. The registered `mean_error` leaves a residue at 14, each at z = 11.27.
- **The world's verdict on made-up columns** (`judge_world`; a constant V before an operator, a
  constant σ and a spread count, at two rungs, with invented margins):
  - every run floppy and every constant exact: pass;
  - **a tense replica gives inconclusive, never pass:** with its σ as recorded, with its own
    tension in σ, and with (d) tense instead, all three are inconclusive. The tense count names one
    replica at one time, and the one unjudged pair is σ there;
  - a floppy replica one ulp off at another time fails the world, the tense replica
    notwithstanding;
  - **P-D8 on made-up columns:** all 22 single-pair plants (11 pairs at each rung) are caught. With
    a tense replica at one time, the 20 pairs still judged are caught, and the 2 at that time are
    not judged.
- **End to end, as the checker will feed it** (D5 and D6 at 100 against 50 nm): 128 invented exact
  runs in the exact row layout and one (d) run in (d)'s, each through the registered reader and
  `floppy_margins`, into `judge_world`. D5's tense slot 0 has no constant pair. (d)'s spread values
  are set to make e exactly 0, so that only the constant path and the precondition decide.
  - The honest worlds pass.
  - A wrong σ (10⁻⁶ N/m) on one replica whose counts are floppy fails the world at that pair alone,
    with the precondition holding.
  - A replica made tense at the last time gives inconclusive, its tense count 1 there.
  - A replica without its last row fails the world at the constant pairs of that time.
  - P-D8 on D6's read rows: all 22 single-pair plants are judged and caught.
- **The classification:** from the model and (d)'s registered margins, the constant pairs are exactly
  §4.2's at every rung. σ's value is +0.0, and V's is positive.
- **The registered reader, on invented rows of the registered worlds, in both representations' row
  layouts** (D1 and D2 at Ω = 1000, D4 at 25 nm, D5 and D6 at 50 nm):
  - `limit_qualification.observables` gives exactly `classify`'s keys, in order;
  - at an unmoved floppy vesicle, the constant pairs' values carry the model's bits;
  - `floppy_margins` reads positive where floppy, and negative after an invented tension at the last
    time;
  - `precondition` names that run and that time.
- **The parse:** every registered definition parses at this head, at its first seed. D0 is refused
  in (d) at `min_count` 10, as registered.

**On the engine's own output** (in `/mnt/workspaces/Cells/ol6-protocol-d-v2-20261124/probes/`;
booleans, keys, shapes, spreads and the clock's room only, with no observable compared with
(d)):
- **(d)'s half of the constant rule** (`real_reader.py`): (d) alone on the registered D5 and D6 at
  50 and 100 nm. At every constant pair, its value carries the model's bits: 16, 16, 11 and 11
  pairs.
- **The reader on real rows,** on an unregistered variant at 12.5 nm (D5 and D6), in exact events on
  the smoke seeds 1 and 7 and in (d):
  - the reader's keys equal `reader_keys` in both layouts, each array of shape [8];
  - `floppy_margins` is finite, and the vesicle floppy at every constant time;
  - every run's values at the variant's constant pairs carry the model's bits (16 in D5, 11 in
    D6).
- **The linear-noise table** (`protocol_d_v2 noise`, §4.3), and its check against 128 exact
  replicas of the 12.5 nm D5 variant (`lna_check.py`).
- **The D7 clock-room probe** (`d7_fresh_seeds.py`, `d7/`), named here and in §11. The author ran
  (d) alone on the registered D7 at all three rungs on 640001–640128, the first range proposed at
  dbf17e84, to see the clock bound's room on fresh seeds.
  - No opening time was printed or written.
  - Of 384 runs, none was refused by D309's bound, and every one lysed by its pore.
  - The largest fraction of the bound used was 0.016, 0.061 and 0.389 at 25, 50 and 100 nm.
  - It consumed those seeds' D7 draws, so that range is withdrawn (§3). The registered seeds are not
    probed, and a refusal on them means what §7 says.

## 9. The cost

Measured from the first check of the same worlds, with the same replicas and settings. The figures
come from its exact folders' `seconds` and D7's (d) records' run seconds, read for these numbers
alone (`cost` in the JSON).
- **Units:** each figure is one process's wall time, in a unit the first check pinned to light CPUs.
- **So it is a CPU-hour figure only if each process held one CPU.** The first check's chains ran one
  world-rung process at a time per unit, but a unit pinned to two CPUs could have let a process use
  both, so the CPU-hours are between these figures and twice them.

| Part | CPU-hours |
| --- | --- |
| Exact events, D0–D6 | 10.7: D5 6.0 (its 100 nm rung 4.5 in one chain), D2 1.5, D3 1.6, D1 0.6, D4 0.5, D6 0.5, D0 0.02 |
| Exact events, D7 | 0.7 |
| (d): D7's 384 paired runs | 0.75 |
| (d): every other world's runs, and D7's convergence runs | about 1 |
| The plants, in (d) | about 0.3 |
| **The first seed set** | **about 13.5 process-hours (13.5 to 27 CPU-hours)** |
| A retry of inconclusive worlds | up to those worlds' share again: up to about 27 process-hours in all |

- **It runs before FR-47's exact ensemble** (D323), which is about 3 CPU-hours.
- **D5's 100 nm rung sets the wall time** unless its 128 replicas are split across CPUs.
- **The first registration's estimate was 2–3 CPU-hours.** It counted events at the density worlds'
  rate, and D5's population at 100 nm costs far more per event.

## 10. Who checks

- **A fresh independent checker,** assigned by the lead (D304). It must not have seen the first
  Protocol D's results: not this registration's author, and not the first checker.
- **It should not read,** before its verdict:
  - the first check's folders, `/mnt/workspaces/Cells/ol6-checker-20261123/`;
  - decisions D317–D318;
  - erratum 3, which is superseded and quotes the first check's findings;
  - PROGRESS.md's Protocol D lines and the builders' notes
    (`/mnt/workspaces/Cells/ol6-20261122/STATE.md`), which record the first results.

  It reads the first registration, and erratum 1, which §7 folds in. §7 restates erratum 2's rules,
  so the checker need not read erratum 2, whose §1 and §4 quote the first check's plant findings in
  (d) alone. This document quotes none of the first results.
- **Before any run,** at its own head, it runs `python -m validation.assembly_lineages_v2.
  protocol_d_v2 check` and stops if any check fails. Main may move between the tag and the run, and
  the reader's keys come from `rate_equations.enveloped`, so the check verifies them at the run's
  head.
- **Its driver** may be its own, using the registered functions, as the first check's was.
- **It runs detached,** with durable logs (AGENTS.md), on the CPUs the lead assigns.
- **It judges M with `judge_world`** at each world M reads, and P-D8 with `pd8` on D6's honest runs.
- **It writes** under `/mnt/workspaces/Cells/ol6-protocol-d-v2-<head>/`, as JSON: the definitions,
  both representations' observables, the per-criterion tables, the constant pairs' judgements, the
  precondition with its tense counts and unjudged pairs per world and rung, n_min, the plants'
  outcomes (P-D8's rows among them) and the verdicts.
- **PROGRESS** gets one line linking to them.

## 11. What had been seen (disclosed)

- **The author** is OL6's builder, who wrote errata 2 and 3 and FR-47's protocol and build.
- **The author knows the first verdict** as decision D318 records it, and erratum 3's diagnosis
  through the lead.
  - So §4's classification is not blind to them.
  - It is derived from the model, by §4.1's rules, and §6 guards it. This document quotes none of
    the first results, so that the checker can read it blind.
- **Read from the first check,** for §9's cost and nothing else:
  - the exact folders' `meta.json` `seconds`;
  - D7's (d) records' `run_seconds`.

  No observable, judgement or verdict file of the first check was opened for this registration.
- **Read for the lead's question whether the files the checker executes hold first-check results:**
  `protocol_d_erratum_2.py` in full, and `protocol_d.json`'s keys and its non-constant sections. Both
  are registered files. The answer went to the lead, and this document quotes none of it.
- **Run for this registration:**
  - cells.rate_equations@1 alone on the registered D5 and D6 definitions at the three rungs (seed 1;
    (d) is deterministic here), for §4.3's margins. The script is
    `/mnt/workspaces/Cells/ol6-protocol-d-v2-20261124/probes/margins.py`, with its JSON;
  - the same, on a fine observation grid, for §4.3's linear-noise table (`protocol_d_v2 noise`);
  - **the noise check:** exact events on an unregistered 12.5 nm D5, seeds 1–128, forming spreads
    only (`lna_check.py`);
  - §8's checks, including:
    - (d) alone on the registered D5 and D6 at 50 and 100 nm, for the constant pairs' bits;
    - an unregistered 12.5 nm variant of D5 and D6, in exact events (smoke seeds 1 and 7) and in
      (d), printing booleans, keys and shapes only;
  - **the D7 clock-room probe:** (d) alone on the registered D7 at all three rungs on 640001–640128,
    384 runs, with statuses, causes and the bound's largest fraction only. Its seeds are withdrawn
    (§3).
- **Withdrawn:** the random-walk scale estimate proposed at dbf17e84 (`fluctuation_scale.py`, which
  ran nothing), replaced by §4.3's linear-noise variance.
- **Not run:** no exact-event run of any registered world, and no run of any kind on the registered
  seeds.

## 12. What does not change

- **The worlds D0–D7,** their rungs, observation times, horizons, replicas per world, integrators,
  envelope (`min_count` 10, "Protocol D's qualification runs") and exact settings.
- **The observables and scales (§3)** and the stated error terms (§4).
- **P, B, E, L and N (§5.1, §5.3–§5.6),** with their constants: the slope window, b = 2, c_r = 5,
  the 0.75 ratio and the bands.
- **n_min's rule (§6).**
- **The registered plants (§8 of the first registration) and their registered effects.**
  - None is caught by a criterion the repair changes. P-D2(ii) and P-D3 are caught by M and B on
    count pairs, which stay spread pairs under the registered excess. Their replicas vary and their
    combined SE there is positive, so neither the constant rule, the exact moments nor the zero-SE
    evaluation reaches them.
  - The others are caught by B (P-D1), E (P-D4), N (P-D5), L (P-D6) and the limit's check (P-D2(i),
    P-D7).
  - So none is re-sized.
- **One plant is added, P-D8,** the constant rule's (the lead's ruling 3; `pd8`, and `plants` in the
  JSON). No registered plant acts at a constant pair, so the constant path had no plant.
  - **What it plants:** on D6's honest observables at 50 and 100 nm, (d)'s value at one constant
    pair moves one ulp up (np.nextafter toward +∞; σ's +0.0 becomes the smallest subnormal). The
    exact replicas and every other value are as run. It is planted once per constant pair and rung:
    22 plants.
  - **Its registered effect:** each planted pair that the precondition lets M judge fails the world
    by the constant rule. M's constant failures are then the honest judgement's plus that pair.
    P-D8 is caught when every judged plant is, and at least one is judged.
  - **Why one ulp, on the observables:** it is the smallest error (d) can make, and no statistical
    rule sees it. It is planted on the read values, not in an engine run, because the reader
    recomputes V and σ from counts. A floppy V reads N_L through a logarithm, and σ is +0.0 while
    floppy. Moving N_L up by 1 to 16 ulps leaves V's bits as they were in D5 and D6 at 50 and 100
    nm (32 at three of them), and σ's at every step, so a count-level plant of one ulp would not
    be there to catch.
  - **Its cost** is none. It reads the honest D6 runs, with no new run.
- **The other preconditions (§9),** the verdicts and the retry (§10), with the retry's seeds as §3
  gives them.
- **D7 and the clock bound.** Its (d) runs draw their thresholds from the registered seeds, which
  are not pre-checked (§3). A refusal means what §7 says.
