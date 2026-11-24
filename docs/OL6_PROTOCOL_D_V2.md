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
  classification, M repaired, the precondition and the checks.
- **`validation/assembly_lineages_v2/protocol_d_v2.json`:** its numbers, namely the seeds and the
  earlier ranges, (d)'s margins and the model's fluctuation scale at them, the classification table
  and the cost.
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
  inequality is evaluated exactly instead of by division (§5).

## 2. What changes, completely

1. **The seeds (§3).** Fresh ranges, disjoint from every earlier one.
2. **M's pairs are classified from the model before any run (§4).** The constant pairs are
   D5's floppy slot's V and σ, and D6's σ, plus D6's V before the shear. Every other pair is
   spread. None is derived.
3. **M's rule (§5).** Constant pairs take the constant rule, and spread pairs take the registered
   excess, evaluated exactly at a zero combined SE.
4. **A precondition for the constant pairs (§6).** The vesicle is floppy in every run at those
   times; otherwise the world is inconclusive.
5. **The errata are folded in (§7).** Erratum 3 is superseded.
6. **The checks before the tag (§8).** These are the reader on invented inputs, M on made-up columns,
   the classification, the seeds and the parse.
7. **The cost and who checks (§9, §10).**

Nothing else changes (§12). That covers the worlds, rungs, times, horizons, replicas, integrators,
envelope, scales, criteria P, B, E, L and N, n_min's rule, the plants and their registered effects,
the other preconditions, the verdicts and the retry rule.

**Superseded, each with its replacement.** A checker using the registered functions takes these from
this registration, never from the first:

| In the first registration | Use instead |
| --- | --- |
| `limit_qualification.SEED_BASE` and `limit_qualification.seeds` (seeds 1 and 100001 onward) | `protocol_d_v2.SEEDS` and `protocol_d_v2.seeds` (§3) |
| protocol_d.json's `constants.ladder.seeds` | protocol_d_v2.json's `seeds` |
| §2's "Seeds: 1 to M ... the retry's seeds are 100001 to 100000 + M" | §3 |
| §7.4's convergence seeds 1–6 | 640001–640006 (§3) |
| Erratum 2's "seeds 1 to 256" for D0 (P-D1) | D0's first seeds here, 640001–640256 |
| `limit_qualification.criterion_m` for M's verdict | `protocol_d_v2.criterion_m` (§5); `limit_qualification.mean_error` stays its input |
| Erratum 3, its document and `protocol_d_erratum_3.py` | §4 and §5 |
| §11's cost (2–3 CPU-hours) | §9 |

## 3. The seeds

- **First seeds:** 640001 to 640000 + M, with environment 0, lineage 0 and branch 0. M is 256 for
  D0–D3 and 128 for D4–D7.
- **Retry seeds**, once and for inconclusive worlds only: 740001 to 740000 + M.
- **D7's clock convergence (§7.4 of the first registration)** reads the first six seeds of the set
  it checks: 640001–640006.
- **D2's β generator seed, 20261124,** is a world input and stays as registered.
- **Disjoint from every earlier range the author could find** (`EARLIER_SEEDS`, checked by
  `seeds_disjoint`): those registered in docs/ and validation/, those the decisions name, and the
  probes' and smokes' seeds the author knows. A range used only in an unrecorded run is outside
  what this check can see.

| Range | Seeds |
| --- | --- |
| Protocol D, first and retry | 1–256, 100001–100256 |
| Protocol G (its @1 1001–1256 and @2 2001–2256 among them) | 1–5256 |
| Protocol G's matrix seeds | 20261123–20261142 |
| Protocol G's checker, unregistered timing smokes | 900001 onward |
| FR-47, first (W1, W1Δ, W2's rungs, P7, P8) | 470001–471528 |
| FR-47, retry (W2's are the first plus 500,000) | 970001–971528 |
| The probes' and smokes' stream seeds | 1 and 7 |

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

### 4.3 Why the vesicles stay floppy: (d)'s margins and the model's fluctuation scale

A constant pair needs its vesicle to be floppy at that time in every exact replica.
- **The margin** is (d)'s ln V_sph − ln V_osm at each registered time. The author's (d)-alone runs of
  the registered definitions give it (`d_margins`).
- **The model's scale** for an exact replica's deviation from it is estimated from the world's
  parameters and (d)'s trajectory alone (`floppy_scale_estimate`):
  - **an unmoved lumen:** only W moves, by the exchange's joins and leaves. That is a random walk of
    about 2rt events by time t, with r the join rate, equal to the leave rate at the floppy
    equilibrium. So SD(ln v) ≈ 1.5·√(2rt)/n_mem;
  - **after D6's shear:** the split's binomial variance, √(1/N_L + 2.25/n_mem) of the parent's
    counts, plus the walk since the shear.

The smallest margin over each world's constant times, in units of that scale:

| Vesicle | 25 nm | 50 nm | 100 nm | Where |
| --- | --- | --- | --- | --- |
| D5's slot 1 | 0.120 (7.0) | 0.084 (9.7) | 0.026 (6.0) | at 60 s, the floppy slot losing amphiphile to the tense one |
| D6 | 0.164 (4.5) | 0.164 (11.9) | 0.164 (30.2) | after the shear; before it, 0.511 |

M reads 50 and 100 nm, where the smallest is 6.0 scales. That is about 1 × 10⁻⁹ per replica on a
Gaussian tail. The estimate is a model's, so §6 guards it.

## 5. M, repaired (`criterion_m`)

At the top rung K against K − 1, each rung's observables as the registered reader gives them:
- **A constant pair at K** is judged by the constant rule at K, and at K − 1 where it is constant there
  too. `agreement.judge_constant` takes every exact replica, and (d)'s value must have the model's
  bits.
  - One replica off, or (d) off, fails M.
  - A NaN, from a run that ended before the time, is not the constant.
  - 0.0 and −0.0 differ.
  - A constant pair is not in M's z.
- **Every other pair is spread.** It takes the registered `mean_error` at both rungs and the
  registered excess, (|e_K| − |e_(K−1)|/2)/(SE_K² + SE_(K−1)²/4)^½ (`spread_excess`).
  - **Where the combined SE is exactly 0,** the registered inequality |e_K| ≤ z*·0 + |e_(K−1)|/2 is
    evaluated exactly. Where it holds the excess is −∞, and where it does not it is +∞, a fail. The
    registered code's division by infinity, which took any such pair as "no limit", is gone.
  - **Identical replicas are not excluded.** At a spread pair they face the test like any other, so
    §1's artifact would fail a pair that the model had wrongly called spread. That is why §4's
    classification carries the weight.
  - A NaN term, at a time after a run's end, enters no maximum, as registered.
- **The verdict:**
  - M **passes** when every constant pair passes and the largest spread z is at most 4.5;
  - it **fails** when a constant pair fails, or the largest z passes 6;
  - otherwise it is **inconclusive**.
  - With no spread pair, the largest z is −∞.
  - z* = 4.5 and the fail threshold of 6 are as registered.
- **The false-alarm bound of §5.2 stands** for the spread pairs. The constant rule adds no false
  alarm while §6's precondition holds, since under it every replica and (d) have the model's bits.

## 6. The constant pairs' precondition (added to §9 of the first registration)

- **At the rungs M reads,** at every time of a constant pair, the vesicle is floppy in every exact
  replica and in (d): ln V_osm < ln V_sph by the engine's own `lumen.log_branches`, on real N_L and W.
  `floppy_margins` reads this from each run's rows as the reader does, and `precondition` judges it.
- **A violation makes the world inconclusive,** as §9's other preconditions do. It means the model's
  condition failed, not its claim. A floppy replica whose V differs is a wrong replica, and fails
  under §5.
- **The precondition is judged first.** At a pair where it fails, the constant rule is not judged,
  so a tense replica gives an inconclusive world, never a fail of M. On the retry, a violation again
  leaves the world inconclusive, and the protocol with it (§10 of the first registration).

## 7. The errata, folded in

- **Erratum 1 (D309's clock bound): in force.**
  - The bound is in the engine, |U^H| ≤ 1 × 10⁻¹⁰ + 2 × 10⁻³ |ΔH| per vesicle and accepted step.
  - D7 runs as registered.
  - §7.4's convergence runs at rtol 1e-13 take atol_count 1e-10.
  - A run refused by the bound is inconclusive (numerics) for that replica.
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

They use invented inputs and made-up columns only, plus the parse of the registered definitions. No
world is run. All 20 pass, in about 2 s:

- **Seeds:** every seed of every world and both sets lies outside every earlier range.
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
  - **identical non-integer replicas at (d)'s bits, classed spread,** give z = 11.27, §1's
    artifact, and do not pass. Identical replicas face the test, which is why §4 marks such pairs
    constant;
  - **genuine spread columns** give a z bitwise equal to the registered one;
  - **an observable without a class is refused.**
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

**On the engine's own output** (`/mnt/workspaces/Cells/ol6-protocol-d-v2-20261124/probes/
real_reader.py` and its JSON; booleans, keys and shapes only, no observable value printed):
- **(d)'s half of the constant rule, at this head:** (d) alone on the registered D5 and D6 at 50 and
  100 nm. At every constant pair, its value carries the model's bits: 16, 16, 11 and 11 pairs.
- **The reader on real rows,** on an unregistered variant at 12.5 nm (D5 and D6), in exact events on
  the smoke seeds 1 and 7 and in (d):
  - the reader's keys equal `reader_keys` in both layouts, each array of shape [8];
  - `floppy_margins` is finite, and the vesicle floppy at every constant time;
  - every run's values at the variant's constant pairs carry the model's bits (16 in D5, 11 in
    D6).
- **D7's (d) side on the fresh seeds.** Each D7 (d) run draws its pore threshold from its replica's
  seed, so the fresh seeds change D7's (d) runs. The first registration measured the clock bound's
  room over seeds 1–128.
  - The author ran (d) alone on the registered D7 at all three rungs, on 640001–640128
    (`probes/d7_fresh_seeds.py`, `d7/`). No opening time was printed or written.
  - Of 384 runs, none was refused by D309's bound, and every one lysed by its pore (cause `pore`).
  - The largest fraction of the bound used was 0.016, 0.061 and 0.389 at 25, 50 and 100 nm.

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
  protocol_d_v2 check` and stops if any check fails. Main moves between the tag and the run, and the
  reader's keys come from `rate_equations.enveloped`, which FR-47's inert-wall fix makes precise.
  That fix leaves every mask of D0–D7 unchanged at its head, but the check verifies it at the run's.
- **Its driver** may be its own, using the registered functions, as the first check's was.
- **It runs detached,** with durable logs (AGENTS.md), on the CPUs the lead assigns.
- **It writes** under `/mnt/workspaces/Cells/ol6-protocol-d-v2-<head>/`: the definitions, both
  representations' observables, the per-criterion tables, the constant pairs' judgements and
  precondition, n_min, the plants' outcomes and the verdicts, as JSON.
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
- **Run for this registration:**
  - cells.rate_equations@1 alone on the registered D5 and D6 definitions at the three rungs (seed 1;
    (d) is deterministic here), for §4.3's margins. The script is
    `/mnt/workspaces/Cells/ol6-protocol-d-v2-20261124/probes/margins.py`, with its JSON;
  - §4.3's scale estimate (`fluctuation_scale.py`), which runs nothing;
  - §8's checks, including:
    - (d) alone on the registered D5 and D6 at 50 and 100 nm, for the constant pairs' bits;
    - an unregistered 12.5 nm variant of D5 and D6, in exact events (smoke seeds 1 and 7) and in
      (d), printing booleans, keys and shapes only;
    - (d) alone on the registered D7 at all three rungs on the fresh first seeds, for the clock
      bound's room, with statuses, causes and the bound's largest fraction only.
- **Not run:** no exact-event run of any registered world.

## 12. What does not change

- **The worlds D0–D7,** their rungs, observation times, horizons, replicas per world, integrators,
  envelope (`min_count` 10, "Protocol D's qualification runs") and exact settings.
- **The observables and scales (§3)** and the stated error terms (§4).
- **P, B, E, L and N (§5.1, §5.3–§5.6),** with their constants: the slope window, b = 2, c_r = 5,
  the 0.75 ratio and the bands.
- **n_min's rule (§6).**
- **The plants (§8) and their registered effects.**
  - None is caught by a criterion the repair changes. P-D2(ii) and P-D3 are caught by M and B on
    count pairs, which stay spread pairs under the registered excess. Their combined SE there is
    positive, so neither the constant rule nor the zero-SE evaluation reaches them.
  - The others are caught by B (P-D1), E (P-D4), N (P-D5), L (P-D6) and the limit's check (P-D2(i),
    P-D7).
  - So none is re-sized.
  - No plant acts at a constant pair. The constant path's catches are §8's made-up columns.
- **The other preconditions (§9),** the verdicts and the retry (§10), with the retry's seeds as §3
  gives them.
- **D7 and the clock bound.** Its (d) runs draw their thresholds from the fresh seeds, and §8 shows
  the bound's room on the first set. A retry's (d) runs are not pre-checked. A refused replica is
  inconclusive (numerics), as erratum 1 says.
