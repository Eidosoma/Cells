# OL6 Protocol G: the GARD limit (registration)

**Status: proposed for registration, 23 November 2026, for the lead.** Docs and validation only, with
no src change. Branch `ol6-protocol-g` from main 07ab2e5c. It is to be tagged before any comparison of
version 2's exact events with version 1's is computed. The proposed tag is
`ol6-protocol-g-registered-2026-11-23`.

**Sources.**
- The design: docs/OL6_DETERMINISTIC_REPRESENTATION_DESIGN.md §5.2 and §6.8 (tag
  `ol6-design-note-2026-11-22`).
- D304's rulings:
  - "pathwise to rounding" replaces the note's bitwise tier;
  - distributional agreement stays the second tier;
  - a planted change to one β entry must fail;
  - each protocol is run at its tag by an independent checker, never the builder.

**What is registered.** The tag holds three files, and each is read byte for byte as tagged:
- this document, which is the authority;
- `validation/assembly_lineages_v2/gard_limit.py`, its arithmetic: the worlds' generator and
  definitions, the plants, tier 1's comparison and coincidence test, tier 2's statistics, and the
  plants' power;
- `validation/assembly_lineages_v2/protocol_g.json`, every number: the constants, the twenty worlds
  as recorded numbers, and the plants' power computed from version 1 alone.

**Engine models (AGENTS.md).**
- **Version 1 (@1):** `cells.assembly_lineages@1` with `cells.reservoir_exchange@1`,
  `cells.gard_catalysis_pair_consistent@1`, `cells.size_threshold_fission@1` and
  `cells.daughter_continuation@1`.
  - `cells.gard_catalysis_pair_consistent@1` is G1's registered default and the law the claim is
    against.
  - Its exact-cache successor, `cells.gard_catalysis_pair_consistent@2` (D244, D246), is reported
    beside it.
- **Version 2 (@2):** `cells.assembly_lineages@2` with `cells.stochastic_mass_action@1`,
  `cells.transition_state_factor@1` and `cells.ideal_mixing@1`. Scope 2 adds
  `cells.size_threshold_division@1` (S7).

## 1. The claim

- **The claim:** §7.3's configuration, declared in @2, reproduces G1's GARD law set event by
  event. Under shared streams, @2's exact events take @1's channel sequence, with event times equal
  to rounding.
- **Its kind:** a consistency check by construction, not a D138 comparison (D199's U6(a)).
- **Its measure:** the exact measure, `multinomial_less_one` with `extinct` (D215).
  - The physical measure, `multinomial` with `kept`, differs at O(1/N). The join's extent is N + 1
    against N, and the last molecule is kept.
  - It is reported (§7), never judged.

## 2. The worlds

Each world has C = 8 types and @1's fission size N_split = 80. Its numbers are recorded in
protocol_g.json, and those numbers are the record. `gard_limit.generate` made them with NumPy's
default generator at the world's matrix seed, as P1 draws a world (`probe_gard_rates.gard_world`):

| Item | Value |
| --- | --- |
| Matrix seeds | 20261123 to 20261142, one world each |
| β | exp(−4 + 4Z), Z standard normal, 8 × 8, the diagonal kept (GARD's lognormal) |
| Worlds 16–19 | β[0][1] set to 10⁵ |
| kb_i | uniform on [0.5, 2) |
| K_i | uniform on [0.5, 5) |
| ρ_i | 100 w_i / Σ w / K_i, with weights w_i uniform on [0.5, 1.5), so Σ K_i ρ_i = 100 |
| Founder | integers uniform on 1 to 9 per type, one founder per world, N₀ from 30 to 57 |

**The factor's two branches are both covered.** Each world's branch is read from its parsed @2
layout and recorded:
- The count-weighted-mean branch, taken when the data's amplification passes κ_limit ≈ 7037, covers
  worlds 16–19 and also world 0, whose largest lognormal entry is 2.16 × 10⁴.
- That makes five worlds in this branch and fifteen in the cached branch.

**@1's definition** (`gard_limit.v1_definition`):
- The world is t0 to t7 with `transfer_constant` K_i, `supply` ρ_i, `leave_rate` kb_i and
  `catalysis_matrix` β.
- Fission is `exact_fraction` 0.5 at size 80. Continuation is `first`, `extinct` and `discard`.
- Units are nominal.
- The law is `cells.gard_catalysis_pair_consistent@1`.
- The run makes one fission in scope 1 and 50 in scope 2, with a growth guard of 40,000 events.
- Execution: `type_capacity` 8 and `molecule_capacity` 128.

**@2's definition** (`gard_limit.v2_definition`) is §7.3's configuration, P1's construction:
- held pool places at ρ_i in mM, with c0 = 1 mM, so ln(held/c0) = ln ρ_i;
- one join per type, `join_t<i>`, in type order, under mass action at the membrane locus, with
  k_f = K_i × kb_i (the same float product as @1's);
- μ°_sol = 0 and μ°_bil = −ln K_i, so k⁻ = kb_i;
- the transition-state factor with ΔΔG‡_ij = log1p(β_ij) (catalyst t_j on the join of t_i);
- ideal mixing, no geometry and a single lineage.

In scope 1 there is no division. The run's other settings:
- a horizon of 1 s and 512 events, past @1's first fission;
- `molecule_capacity` 1024, `place_capacity` 16 and `step_capacity` 8.

**The channel map is the identity.** Both families record a signed channel per event:
- @1's +(i + 1) and −(i + 1) are the join and leave of type t_i;
- @2's +(i + 1) and −(i + 1) are the forward and reverse of step `join_t<i>`, its step i.

With `type_capacity` and `step_capacity` both 8, the channel indices coincide too. Join i is index i
and its leave is 8 + i, in both kernels' prefix order.

## 3. Two scopes, and the dependency on S7

**Scope 1: from the founder to @1's first fission.**
- What is compared: the first k₁ events of each seed, where event k₁ is the join that brings N to
  80.
- @2 runs without a division, and its first k₁ events are compared.
- It needs no engine change, and is runnable on main at the tag.

**Scope 2: through 50 fissions, the first daughter followed.**
- It is registered now, and is **not run until `cells.size_threshold_division@1` (S7) has landed on
  main**.
- Its @2 definitions are scope 1's, plus S7's division declared with N_split 80, `exact_fraction`
  0.5 and continuation `first`, in the syntax S7 documents. They also need an event limit and a
  horizon past @1's 50th fission.

**Its interface contract.** S7's operator must do the following, or scope 2 is not run and is
reported as not run:
1. **The trigger:** a join that brings N to N_split.
2. **The draw:** from domain 2 (partition), keyed by the parent's carrier key, at counter 0.
   - The occupied places are listed by type in declared order: t0's first, then t1's, and so on.
   - Place k takes the k-th uniform.
   - Only the first N uniforms are read. Both families require JAX's partitionable threefry, under
     which they equal the first N of @1's draw of `molecule_capacity` uniforms.
3. **The partition:** the places are ranked by u ascending, ties by place. The first floor(f N),
   here 40, go to the first daughter, and the second daughter is the parent less the first.
4. **Continuation and keys:** continuation is `first`, with keys as @1's (keys.py).
   - The daughters take s:c and s:c + 1 from the parent's counter.
   - The followed daughter continues the counter.
   - Its event stream's counter (its age) restarts at 0.

**The order of the runs.**
- Scope 1 is run at the tag. Scope 2 is run at the first main head holding S7.
- Each is judged on its own, and a scope-1 failure does not stop scope 2. Since scope 1's events are
  scope 2's first growth, a scope-1 failure is a scope-2 failure.

**A flag for the lead.** This protocol's author may also build S7, whose operator scope 2 judges.
- The contract above is fixed before S7 is written.
- Neither the author nor S7's builder runs either scope.

## 4. The premise: shared uniforms

@2's domain 1 is @1's exchange stream by construction (`assembly_lineages_v2/streams.py`), so the two
families draw the same (u₁, u₂) for the same seed, key and counter. P1 measured rates only, so this
premise is checked first, on every tier-1 seed:
- Every tier-1 run, in both families, is made with `trace: true` and `uniforms: true`.
- **The check:** for every seed, the two families' recorded event uniforms agree bitwise at every
  compared event, and in scope 2 also the partition uniforms (the first N per fission).
  - The uniforms of event k are drawn at counter k − 1 of the occupant's stream.
  - They do not depend on the channels chosen, so they are compared at every compared event, even
    past a divergence.
- **If any seed fails it,** tier 1 fails. Version 2's statement that it draws version 1's uniforms
  is then false.

## 5. Tier 1: pathwise to rounding (the claim, D304)

**Seeds.** 64 per world: stream seeds 1 to 64, with environment 0, lineage 0 and branch 0. Each
seed is the same for both families, so each scope makes 1,280 comparisons.

**Per seed, over the compared events** (scope 1: events 1 to k₁; scope 2: every event through the
trigger of the 50th fission):
1. **Channels:** code₂(k) = code₁(k) at every compared k.
2. **Times:** |t₂(k) − t₁(k)| ≤ (48 + k) ε t₁(k), with ε = 2⁻⁵² and k the event index from 1.
3. **Scope 2 only:** at every fission, the first daughter's composition is equal, type for type.

**The time bound's derivation (S).** Both kernels compute τ = −ln(u₁)/a₀ with the same u₁, and
accumulate t ← t + τ in the same order:
- **A rate** differs between the kernels by at most 32 ε relative. That is twice P1's largest
  difference, 3.1 × 10⁻¹⁵ ≈ 14 ε, measured over 4,000 random states in both factor branches.
- **a₀,** a serial left fold of 16 positive channels, adds at most 8 ε of differently rounded
  additions.
- **The division** adds 1 ε.
- **So a wait** differs by at most 41 ε, rounded up to 48.
- **The accumulation:** each addition rounds to within one ulp, and different inputs can round
  apart, so after k events up to k ε. That is twice the expected k ε/2, for the worst case.

At scope 2's length, about 2,500 events, the bound is about 5.7 × 10⁻¹³ relative, inside the note's
1 × 10⁻¹² everywhere. The note's flat 1 × 10⁻¹² would have been passed by worst-case rounding near
10⁴ events, so the bound grows with k instead.

**A threshold coincidence.** At a divergence, take the state both kernels reached: the founder
plus the k − 1 events before it, and in scope 2 the shared partitions. The divergence is a
coincidence when, in either kernel, the threshold min(u₂ a₀, nextafter(a₀, 0)) lies within 128 ulps
of one of its partial totals. Each kernel's partial totals are computed by its own host arithmetic
(`gard_limit.coincidence`):
- @1: `kernel.rates` with the law's own state, then `folds.prefix`;
- @2: `balance.host_log_rates`, exponentiated, then `folds.prefix`.

**Its derivation.**
- **Why that window:** the threshold and a partial total near it each carry at most 41 + 1 ε of
  the two kernels' rounding difference. That is 84 ulps of the threshold, rounded up to 128.
- **It also absorbs** the host recomputation's last-bit differences from the device.
- **A divergence outside that window** cannot come from rounding at the bounds above, so it is a
  real difference between the kernels.

**How coincidences count.**
- A coincidence is counted and reported with its event, its state and both kernels' thresholds and
  nearest partial totals. It ends that seed's comparison.
- **Expected rate:** about 2R × 128 ε ≈ 4.5 × 10⁻¹³ per event (R = 8 steps). That is about
  3 × 10⁻⁸ over scope 1's set (about 64,000 events) and 1.5 × 10⁻⁶ over scope 2's (about 3.2 × 10⁶).
- **The bound:** at most one coincidence is allowed in each scope.
- Any other divergence fails its seed.

**Tier 1's verdict, per scope:**
- **Pass:** the premise holds; every seed passes or ends in a coincidence; and there is at most one
  coincidence.
- **Fail:** otherwise.
- **Inconclusive:** a seed is censored. Either an @1 run ended before its scope's last compared
  event (extinct, or the growth guard), or an @2 run ended before it (its event limit, its capacity,
  or the horizon). Such a seed takes the retry (§9).

## 6. Tier 2: distributional agreement at registered tolerances

**The seeds are disjoint.** @1 runs on seeds 1001–1256 and @2 on seeds 2001–2256, 256 per family
per world. No two runs share a stream.
- So tier 2 rests on no stream identity, and remains a test if the lead rules the pathwise tier
  out (the note's fallback).
- On shared seeds, tier 2 would only repeat tier 1, since identical paths give identical statistics.
- It is also the tier that judges the larger β plant (§8).

**The statistics: nine per world.**
- Scope 1: the time of the first passage to N = 80 by a join (@1's first fission), and the count
  of each type there.
- Scope 2: the same at the first and at the 50th fission, so eighteen per world. The first
  fission's statistics are kept because the larger β plant's power at the 50th fission alone is
  short in five worlds (§8).
- Per statistic, z = (mean₂ − mean₁) / (SE₁² + SE₂²)^½, with SE the standard error of each
  family's 256 values (`gard_limit.tier2_z`).

**The thresholds (S).**
- |z| ≤ 4.5 passes. A statistic with 4.5 < |z| ≤ 6 is inconclusive and takes the retry, and
  |z| > 6 fails.
- There are 20 × 9 = 180 statistics in scope 1 and 360 in scope 2. At 4.5 the two-sided rate is
  6.8 × 10⁻⁶ each, or at most 2.4 × 10⁻³ per scope for a false retry. At 6 it is 2.0 × 10⁻⁹ each,
  or 7 × 10⁻⁷ per scope for a false fail.
- With 255 degrees of freedom per sample, the normal reference is within 10% of Student's in
  these tails.

**Tier 2's verdict, per scope:**
- **Pass:** every statistic passes, and no seed is censored (no passage to N = 80).
- **Fail:** any statistic fails.
- **Inconclusive:** otherwise.

## 7. The physical measure's report (no pass or fail)

- **What runs:** @2 under `multinomial` with `kept`, on tier 2's @2 seeds, against @1 on its tier-2
  seeds.
- **What is reported:**
  - the same nine z values;
  - the observed relative shift of the mean first-passage time;
  - the composition at the passage.
- **The prediction (S):**
  - The join's extent is N + 1, so each join is faster by 1/N.
  - To first order the passage time falls by about the mean of 1/N over the growth: about 2% for
    a growth from about 40 to 80, and shorter, never longer.
  - The composition shifts only through the factor's own dependence on N, at O(1/N).
- The report names the shift's sign and size against this prediction. The lead may rule a pass
  criterion on it later, by an amendment tagged before it is read.

## 8. The β plants

Each plant takes β's largest entry (the first in row-major order at a tie) in @2's world only,
against unplanted @1:

| Plant | Entry | Judged by | Must | Its power, computed from @1 alone before the tag |
| --- | --- | --- | --- | --- |
| **G-P1** | × 1.5 | Tier 1, on tier 1's seeds | Fail tier 1 in every world | The fraction of each world's 64 seeds whose first growth fails tier 1 (channels or times) between planted and unplanted @1: at least 99% |
| **G-P2** | × 4 | Tier 2, on tier 2's seeds | Fail tier 2 in every world: some statistic beyond 6, or in the band and beyond 4.5 on the retry | The largest \|z\| of the world's statistics between unplanted @1 (tier 2's @1 seeds) and planted @1 (its @2 seeds): at least 7 in every world, that is 4.5 + 2.5 (about 99% power at the pass threshold), in each scope |

**The power, as computed** (protocol_g.json's `power`; the runs are disclosed in §11). Both plants
reach their power in every world:

| World | Branch | N₀ | G-P1: channels diverge | G-P1: times beyond bound | G-P1: seeds failing tier 1 | G-P2: largest \|z\| |
| --- | --- | --- | --- | --- | --- | --- |
| 0 | count weighted mean | 47 | 15 | 64 | 64 of 64 | 63.6 |
| 1 | cached | 42 | 64 | 61 | 64 of 64 | 52.0 |
| 2 | cached | 44 | 54 | 60 | 64 of 64 | 61.9 |
| 3 | cached | 36 | 64 | 58 | 64 of 64 | 29.0 |
| 4 | cached | 34 | 64 | 54 | 64 of 64 | 41.8 |
| 5 | cached | 42 | 64 | 44 | 64 of 64 | 51.0 |
| 6 | cached | 34 | 64 | 52 | 64 of 64 | 45.8 |
| 7 | cached | 49 | 63 | 58 | 64 of 64 | 49.2 |
| 8 | cached | 31 | 64 | 57 | 64 of 64 | 63.5 |
| 9 | cached | 43 | 64 | 52 | 64 of 64 | 56.1 |
| 10 | cached | 31 | 64 | 60 | 64 of 64 | 53.2 |
| 11 | cached | 30 | 64 | 60 | 64 of 64 | 46.1 |
| 12 | cached | 45 | 64 | 54 | 64 of 64 | 33.0 |
| 13 | cached | 35 | 64 | 57 | 64 of 64 | 48.3 |
| 14 | cached | 51 | 64 | 53 | 64 of 64 | 40.0 |
| 15 | cached | 32 | 64 | 51 | 64 of 64 | 35.8 |
| 16 | count weighted mean | 38 | 18 | 64 | 64 of 64 | 70.6 |
| 17 | count weighted mean | 41 | 3 | 64 | 64 of 64 | 69.7 |
| 18 | count weighted mean | 57 | 1 | 64 | 64 of 64 | 52.8 |
| 19 | count weighted mean | 55 | 38 | 63 | 64 of 64 | 52.6 |

**Why G-P1 is counted on channels or times.** The design note counted only channel divergence.
- In the five count-weighted-mean worlds, one catalysed join dominates a₀. Scaling it by 1.5 then
  scales a₀ with it, and barely moves the channel shares.
- So few seeds diverge in channel (1 to 38 of 64), while every wait shortens by about a third.
- Tier 1 judges both, so the plant's power is the fraction of seeds that fail tier 1.

**Scope 2's power.**
- **G-P1:** scope 2's first growth is scope 1's, so G-P1's power there is at least scope 1's.
- **G-P2 was computed through 50 fissions,** from @1 alone on tier 2's seeds (protocol_g.json,
  `scope2_tier2`).
  - At the 50th fission alone, its largest |z| falls below 7 in five worlds: world 11 (4.2) and
    worlds 16–19 (1.7 to 5.7).
  - So scope 2's statistics keep the first fission's, where every world's largest |z| is at least
    29 (the table above). The 50th fission's are reported beside them.

**A plant that is not caught makes the protocol fail.** It shows the comparison cannot see the error
it was registered to see. That is judged per scope: G-P1 in each scope's tier 1, and G-P2 in each
scope's tier 2.

## 9. Verdicts and the retry

- **Each tier in each scope** is pass, fail, inconclusive or not run (scope 2 until S7).
- **A scope passes** when its tier 1 and tier 2 pass and both plants are caught in it.
- **The protocol passes** when both scopes pass. Scope 1's verdict is reported as soon as it is
  run.
- **The retry:** once, for inconclusive outcomes only, on registered fresh seeds:
  - tier 1 on 3001–3064;
  - tier 2 with @1 on 4001–4256 and @2 on 5001–5256.

  The retry's verdict is final, under the same rules, except that the band (4.5 < |z| ≤ 6) then
  fails.
- **The engine under test** is recorded by revision: scope 1 at the main head the checker runs,
  with every changed file of either family since 07ab2e5c listed.
  - A src fix made after any reading of this protocol needs an amendment, tagged before the re-run.
  - Its first verdicts stay in the record.

## 10. What it does not claim

- **Not GARD's biology,** and not a D138 comparison with the preprint. It claims only that @2's
  declared laws reproduce @1's GARD law set event by event, on these worlds.
- **Not the physical measure's agreement** (§7).
- **Not @2's division beyond S7's contract,** and not @1's every-descendant mode.

## 11. Not blind (disclosed)

- **P1** (the previous owner's desk probe, `/mnt/workspaces/Cells/ol6-20261122/probe_gard_rates.*`)
  compared @1's and @2's rates on 4,000 random states of 8 types, in both factor branches.
  - They agree to 3.1 × 10⁻¹⁵ relative, and about 13% are bitwise equal.
  - 0 of 256,000 shared draws per case select a different channel.
  - It was read before this protocol, and sized tier 1's bounds. It ran no trajectory.
- **The author's runs, @1 alone** (`/mnt/workspaces/Cells/ol6-20261122/protocol-g/`). They used a
  frozen snapshot of main at 35519156, whose files in both families are unchanged at 07ab2e5c.
  - For the plants' power, @1 ran unplanted and × 1.5 on seeds 1–64, and unplanted on seeds
    1001–1256 and × 4 on seeds 2001–2256.
  - The unplanted runs are the runs tier 1 and tier 2 make for @1, with the same seeds and
    definitions. So the author has seen @1's side of both tiers. Only the summary in §8 was printed,
    and nothing of @2's side.
- **@2 was only parsed:** every definition of every world, each measure and each plant, and its
  layout read for the factor's branch. No @2 event was drawn.

## 12. Who runs it, and the record

- **Who:** an independent checker assigned by the lead, never this protocol's author and never S7's
  builder (D304). It runs at the tag.
- **The driver:** the checker may write its own from §4–§8. Where it uses `gard_limit.py`'s
  functions, those are the registered arithmetic.
- **The outputs** go under `/mnt/workspaces/Cells/ol6-protocol-g-<head>/`:
  - every definition;
  - both families' traces and uniforms, as arrays;
  - per-seed tier-1 results, with every coincidence and divergence;
  - tier 2's z tables, the plants' outcomes, and the physical measure's report;
  - the verdicts, as JSON.
- **PROGRESS** gets one line per scope, linking to them.
