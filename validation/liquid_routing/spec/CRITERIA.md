# Criteria, classes, tolerances, plants and verdicts

**Fixed before any reference or engine run exists.** Every number is a constant of a formula stated
here. None comes from a reference or a run.
- "The reference" is the references agent's files (SPEC.md §7). "The run" is an engine run, read from
  its table (TABLE.md).
- The **judged** set is READOUTS.md §3's table. The run names are `inputs.json`'s.
- **Two kinds of tolerance, never mixed** (D370): a **rounding** bound, derived from an operation count
  (LAWS.md §9), and a **truncation** tolerance, derived from a scheme's order by a Taylor remainder or
  step-halving. A readout of one kind is never judged by the other.

## 1. Symbols

- S = t/h, the steps to time t (from the registered grid, never from the table). H and N count the
  world's holders and species in `inputs.json`: H is its inlets plus the nodes any link touches plus its
  collector.
- e_round = m (S + 1) u s. An event adds 8 u s, once. The count m and scale s by quantity:

| Quantity | m | s |
| --- | --- | --- |
| Arm 1 and 2 amounts, and their sums | m_f | N_x |
| Arm 1's T3 and arm 2's exact heat against its own rows | m_f + 24 | s_F |
| T4, and arm 2's `H_face` by class S | m_4 | s_F |
| Arm 3, 4 and 5 amounts, volumes, supplied, and their sums | m_n | N_x, or V_K's end |
| Labels and their sums | m_q | N_x |
| Heats of flow, totals and portions | m_n + m_h | s_F |
| Arm 6 amounts, volumes, sums | m_n + m_f | N_x |
| Arm 6 heats | m_n + m_f + m_h | s_F |

- An exchange's sample and supplied, from the run's own `before`: 8 u N_x. Its heat from the same: 32 u
  s_F. By class S, `before`, `sample` and `heat` take their amount's and their heat's row above, at S = 16 s/h.

## 2. Rungs and the retry

Each S-class world runs at three steps, each half the last. Arm 1 takes four (exact and default alike).
The retry, once, for an inconclusive entry only: the next halving, so the triple becomes the finer one
(arm 1: j = 1 … 4). A refused or stopped run takes none.

## 3. The criteria, by class

### 3.1 E, equal

Every value equals the named value bit for bit, the sign of zero included. One wrong value fails.
- **Twins and restarts,** over the named series at every output they share:

| Twin | Over |
| --- | --- |
| `F1L` and `F6L` against `F1` and `F6` | every `n`, `V_K`, `supplied` and `H_<i>` |
| `F7` against `F7 h=1.0 no router` | `n_L_S`, `free_sites_S`, `bound_L_S` |
| `G5 h=1.0 restart` against `G5 h=1.0` | `n_T_K`, `V_K`, `supplied_T`, `H_K` |
| `N-buffered` and `N-clean` against `N-none` at the same heat and step, the rows to 16 s inclusive | `n_T_1`, `n_T_2`, `H_face` |
| `J0 h=0.25` against `J0 h=0.25 no router` | `n_*_A`, `n_*_B`, `H_face` |

- **Structural zeros:** SPEC.md §4's `E` entries, +0.0.
- **Outside these,** every other series of a twin is recorded, and a difference is flagged.

### 3.2 R, rounded

|run − expected| ≤ e_round + accuracy, for every entry of READOUTS.md §3's R column. The expected value
is the reference's, the scheme's (T1), or the run's own rows (an identity). An R entry is judged at
every step that runs.
- **Sums:** Σ_i n_x,i − supplied_x equals the start, and Σ_l label equals its row.
- **T3:** `H_face` of an exact run against D of its own levels at 0 and h.
- **The exchange,** from the run's own row at its time: sample = f × n_T_1 there; supplied = f V x;
  heat = H_ev of it; and the first step after it is the scheme's one step from (n_T_1 − sample + supplied,
  n_T_2). The event's `before` equals that row bit for bit (E).
- **Arm 2's exact `H_face`:** the sum over the intervals of D of the run's own levels, the exchange's
  jump left out.
- **Arm 6:** Σ H_<i> + `H_face` equals F(start) + F(supplied) − F(now) on the run's own levels.

### 3.3 B, remainder: the first step's transfer (T2)

Let m = n_T_1(0) − n_T_1(h). Then |m − m*(h)| ≤ M∞ z³/6 + e_round, z = kh, and the same with n_T_2(h) −
n_T_2(0). The bound is LAWS.md §2's Taylor remainder for the published scheme, and needs no run.

### 3.4 L, the local orders, and the default heat (T4)

- **T2's order:** with e_j = |m_j − m*(h_j)| on the exact runs' steps j = 0 … 3, a pair is **resolved** where e_j
  and e_{j+1} both exceed 10 e_round. A resolved pair's q_j = log₂(e_j/e_{j+1}) must lie in [2.5, 3.5], and
  one outside it makes the entry **inconclusive**. An unresolved pair's order is reported, not judged.
- **T4, the default heat (the subject),** at every judged default run:
  - by class R, |H_face(h) − H_def(h)| ≤ e_round, H_def the declared law's closed form (LAWS.md §2);
  - by class B, |H_face(h) − D(own levels)| ≤ B_def(h) + e_round, the law's Taylor remainder;
  - by order, with e_j = |H_face(h_j) − D(own levels)|, j = 0 … 3, as T2's. A lower-order booking fails class
    B first; the order shows why.
- **Why B and L and not S here:** a one-step quantity at different steps ends at different times, so no
  step-halving difference exists.

### 3.5 S, stepped

For readout y in world w with steps h₁ > h₂ > h₃ (each half the last), over the compared times:

    d₂ = max_t |y_{h₂} − y_{h₁}|,   d₁ = max_t |y_{h₃} − y_{h₂}|
    est = max( d₁/(2^p − 1),  d₂/(2^p (2^p − 1)) )        τ = 3 est + accuracy + e_round(last compared time)

- **Pass:** max_t |y_{h₃} − y_ref| ≤ τ. **p** is 2 for arms 2 and 6 (the scheme's and Strang's order) and
  1 for arm 5 (how a step's heat splits among holders).
- **Order:** the entry is **resolved** where d₁ and d₂ both exceed 10 e_round. Then q = log₂(d₂/d₁) must lie in
  **[p − ½, 2.5]**, and one outside it makes the entry **inconclusive**, never a pass (D271). Where either is
  at most 10 e_round the order is **unresolved**: it is reported, not judged, and the entry passes or fails
  by τ alone.
- **The cap is the scheme's:** the integrator and the split are second order, so the cap is 2 plus D271's
  half (its 3.5 was a third-order integrator plus the same half). A holder whose heat is better than first
  order is then not punished. The tolerance is at most 3(2^q − 1)/(2^p − 1) times the actual error: 4.7
  times at p = 2, 14 at p = 1, where a cap of 3.5 would allow 31. The judge reports the factor.
- **Compared times:** arm 2, every 2 s; arms 5 and 6, every output. An event's numbers form their own
  one-time readouts.

### 3.6 N and U

- **N:** `H_<i>` never falls between outputs (arms 3 to 6), and is never negative.
- **U:** `H5`: H_tot ≤ 8 RT (Σ_x N_x)(S + 1) η², with η = m_n (S + 1) u max_{x,i} N_x/n_x,i(0). Levels
  uniform to relative η mix with at most φ ≤ (2η)², twice a step. A heat formed as a remainder of two
  large numbers misses this bound by many orders.

### 3.7 M and D: a stopped run

- **A stop** is an entry whose status is `refused` with kind `check` (TABLE.md): the engine's own energy,
  material or charge check failed a completed row.
- **M1, on every stop** (a recorded run's too): the message holds the word `residual` and then a number, and
  the word `tolerance` and then a number, each with the unit of the ledger that failed, which the message
  names (a stop may be the energy, the material or the charge check). Both are finite, in the same unit, with
  |residual| > tolerance > 0.
- **M2, on P8's stops** (the energy ledger, in pJ): | |residual| − H_missing | ≤ tolerance + (half a unit in the
  residual's last printed digit) + e_round. H_missing is what the ledger's residual spans: for `P8 event`, H_ev
  of the run's own row at 16 s; for `P8 flow`, *(pending the study)*, the reference's H_tot to the stop row if
  the residual is cumulative from t = 0, or the missing heat of the step that ended there if it is that row's
  alone. If neither fits, `P8 flow` is scored on the stop and M1 alone, by a dated change before the tag.
- **D, on every run of role `judged`:** it completes. One that the engine's own check stops **fails**: the
  check's residual above its tolerance is the evidence the comparison would have formed. This departs from
  FR-38's amendment 6, where a refused run is at best inconclusive, and is stated here before any run.
- **The expected stops** (`eq-tr default stop` and `eq-mid default stop`) must stop. If one completes, M1
  is not formed on it and arm 2 is at best inconclusive. They never count against the heat. A stopped
  support run is a refused one.
- **The expected refusals,** each as its run's `expects` says. The message is recorded.
  - `F6 h=4.0 refused` (a throughput of 1.25 at B, above SPEC.md §1's domain) must be `refused` with kind
    `domain`, at parse.
  - `N-clean exact j=0 no admission` (arm 2) and `J1 h=0.25 no admission` (arm 6) declare no admission (SPEC.md
    §1) and must be `refused` with kind `domain`, so the construct is refused unless admitted.
  - If one completes, its arm fails: the operator admitted what its domain or admission rule refuses. If it
    is refused another way, its arm is at best inconclusive.

### 3.8 Arm 7: the takeover

Both sides of each pair run on one engine revision, the registration tag's snapshot, where the wash still
exists. The table carries, for
each side, the digest of every array the run saves, and the operators it declares. Criterion E:
- every array of the run's state, observation rows, ledgers and diagnostics that the two sides both
  save under one name has equal digests;
- every record of the wash is equal to the router record that `takeover_map.json` names for it (the
  sample and supply per event and cumulative, the heats, the label removals against the label
  collections);
- **C0** confirms that the two sides' `operators` differ by the wash on one and the router on the other,
  and that their `inputs` are equal otherwise. An array that only one side saves, and that the map does
  not name, refuses the pair.

`takeover_map.json` is the builder's, filed before the judge's tag. The pairs are SPEC.md §6's.

## 4. Faults and refusals

**Nothing hides a fail.** Every entry that can be formed is judged. If any judged entry fails, its run
fails, whatever else of that run or of its support is refused, stopped or missing.

| Fault | What follows |
| --- | --- |
| The echo of `inputs`, `solver`, `heat` or `operators` departs from the registered run (numbers to 10⁻¹² relative, exact zeros, strings and integers exact; a plant differs only by its declared change) | The run is not the registered one. It is **refused**, and nothing of it is judged |
| A judged leaf is missing, mistyped or non-finite | That readout is **refused**. The rest of the run is judged |
| Provenance: `source` incomplete, `checkout_dirty` true, a missing `record_sha256` or snapshot | The run is **refused**, but its readouts are judged and a fail stands |
| A recorded-only leaf is missing, mistyped or non-finite | Flagged to the checker. Refuses nothing |
| A `refused` entry of kind `domain`, `definition` or `harness` | **Refused** |
| A `refused` entry of kind `check` | A **stop** (§3.7) |
| A run in `missing`, or in neither list | **Refused** |
| A run name `inputs.json` does not list, or lists twice | Ignored and recorded |

- **A refused run cannot pass.** With no failing entry it is at best inconclusive, and so is its arm.
- **A refused or missing support run** leaves its arm at best inconclusive. It does not refuse the run it
  supports.
- **A non-finite value anywhere is a fault, not a gap.**
- **The one place a fail can go unseen** is a departing echo, which leaves nothing of that run judged. It is
  kept: such a run is not the registered world. The checker sees the departure and its cause.
- **C0, before any engine run is read:** the judge reads `reference_invented.json`, then each reference
  file: every key of SPEC.md §7, the inputs' sha256, the classes of SPEC.md §4, every `checks` entry
  passing, and every plant margin at least 10 (§6.2). A fault is named and refused.

## 5. What is judged where

READOUTS.md §3 lists it. Every judged entry is compared at every step that ran and every compared time.
A time is compared only where it is an output of every run it needs.

## 6. The plants

### 6.1 The table

Each plant changes one thing and must fail the check named. **Formed:** a *mapping* plant reads one
honest run as another; a *record* plant replaces a series by LAWS.md §11's planted one; an *engine* plant
is a run with a declared change. P6, P11's first two variants, P12 and P13 live only in tier rows.

| Plant | What | Where and how | Must fail | Request |
| --- | --- | --- | --- | --- |
| P1 | The chain in reverse order | mapping, `F1` and `F2` at h = 1 | R on `n_T_K` at 8 s, both ways | FR-57 |
| P2 | No mixing in B | record, `F1`, `F3` at h = 1 | R on `n_T_B` and `n_T_K` | FR-57 |
| P3 | A first-order transfer, no volume | record, `F3` at h = 1. In `F1` the amounts must pass (negative control: failing it makes P3 unscorable) | R on `n_T_B`, `n_T_K` in `F3`, and on `V_K` in both | FR-57 |
| P4 | A rate per species | record, `F1` at h = 1 | R on `n_U_B` and `n_U_K` | FR-57 |
| P5 | The stream's F as μ times its amount | record, `H1` | S on `H_A` | FR-57 |
| P7 | Heat as the start rate × h | record, `H2`, `H3`, `H4` at the finest step | R on `H_tot` | FR-57 |
| P8 | No heat booked | engine: `P8 event` (the exchange's heat), `P8 flow` (the router's heat) | the run stops; M1 and M2 hold | FR-54 (event), FR-57 (flow) |
| P9 | The collector starts as a node | record, `G1` | E: the first portion's loss | FR-57 |
| P10 | The propagator with h in place of h/2 | mapping, `F1` at h = 1, rows at 2t read at t | R on `n_T_K` at 8 s | FR-57 |
| P11 | A collector's portion at the outlet node's share | record, `F1L` at h = 8 | R on `label_T_tag_K` | FR-57 |
| P14 | k from V₁ alone | record, `r4-mid`, every exact step | B | FR-54 |
| P15 | A transfer that depends on the background | record, `eq-lo`, `eq-mid`, `eq-hi` at h = 1/4 | B, in each | FR-54 |
| P16 | The heat's weight at the step's start, m A(0) | record, formed by the judge from the run's own rows: every `eq-mid` default step, and `eq-mid` exact j = 0 | T4's class B (default), T3 (exact) | FR-54 |
| P17 | The exchange applied after the step | record, `N-buffered` exact j = 2 | R: sample = f × before | FR-54 |
| P18 | A stop's message without its numbers | record, the message of any stop in the tables, with its digits removed | M1 | FR-54 |
| P19 | Lie splitting for Strang's | record, `J1` at its three steps | S on `n_T_A`, error and order | FR-57, arm 6 |

Where a plant names several series, each is sized and scored on its own.

### 6.2 Power, stated before any run (D366)

- **The rule:** a plant's margin is its distance from the honest reference, at its best entry of the
  named check, over the expected honest tolerance there. It must be at least **10**.
- **The expected tolerance:** R and B, the formulas of §1, §3.3 and §3.4. S, three times the step-error
  model of LAWS.md §10. E: the distance itself, which must be non-zero.
- **For P19** also: the planted order, computed at the registered steps, is at most p − ¾, below the window's low
  edge by at least a quarter.
- **The references compute every margin** and report it. A plant below 10 is enlarged or replaced by a
  dated change to this file before the registration tag, never after a run. P8 and P18 have no margin;
  P8's H_missing is reported.

### 6.3 Scoring after the runs

- A plant is scored with the **honest run's** tolerance at the plant's step, never with the planted
  series' own. If that tolerance exceeds the planted distance, the plant is **not caught**.
- **A plant is caught** when every series it names fails its named check.
- **An S-class plant** fails when its error at h₃ exceeds the honest τ. P19 acts on the order, so it must
  also leave its order window on its own three steps: an engine with that defect is then never scored a
  pass. It would be inconclusive by order, and the diagnosis would follow.
- **A plant that reads an honest run that is refused or stopped is unscorable.** It is neither caught nor
  "not caught", and leaves its request at best inconclusive.
- **An engine plant** is caught if the engine's own check stopped it as named and M1 and M2 hold. It is
  unscorable if it is missing, or refused for another reason. One that completes is not caught.
- **The judge's self-tests:** one value of one E series moved by one unit in the last place, a missing
  digit in a message, and a swapped twin must be flagged before the judge's tag.

## 7. Retry

Only for entries scored inconclusive by order, by §2's rule, with their support runs. An entry still
inconclusive after it stays so. No tolerance, window or class changes.

## 8. Verdicts

- **A run** fails if any judged entry fails, or if D fails. Otherwise it is inconclusive if any judged
  entry is, or if it or any of its readouts is refused. Otherwise it passes.
- **An arm,** after the retry, fails if any run fails; otherwise it is inconclusive if any run or support
  run is inconclusive, refused, stopped or missing; otherwise it passes. The expected stop is judged
  only by §3.7.
- **FR-54** reads arms 1 and 2, on three lines: the first step (arm 1), the exchange (arm 2), and the
  stopped-run report (M on the stops of its own tables). It passes if all three pass and P8 (event) and
  P14 to P18 are caught. It fails if any line fails or a plant is not caught. Otherwise it is inconclusive.
- **FR-57** reads arms 3 to 7. It is reported on three lines: flow alone (arms 3, 4 and 5, plants P1 to
  P5, P7, P8 flow, P9 to P11), takeover (arm 7), and flow beside diffusion (arm 6, plant P19). FR-57
  passes if all three pass. It fails if any fails. Otherwise it is inconclusive.
- **Arm 6 not run** (FR-54 did not pass) is neither a pass nor a fail. FR-57 is then reported on the two
  other lines, with "flow beside diffusion: not judged", and is inconclusive as a whole.
- **A plant must be caught** for the request it names. One not caught fails that request. One unscorable
  leaves it at best inconclusive.

- **The record** lists, for every entry: run, readout, class, statistic, tolerance, their ratio, q and the
  factor for S, and the verdict; every refusal, stop and flag, with its cause; and every plant's margin.

## 9. What a miss means, stated before any run

- **T1** (the scheme) is a premise of T2 and T4. A miss says the run's transfer is not the published
  scheme's. It fails arm 1, and T2's bound is not read as evidence for or against the physics.
- **T2 with T1 passing** cannot fail except by rounding, since the scheme's remainder is bounded.
- **T3** is the control. A miss there points at the harness, not at the heat law.
- **T4** is the subject. Its class R is a scheme check, as T1's is: the law was transcribed from the engine, so
  its pass is expected and it shows the compiled composite follows the law. Its class B is the claim: a miss
  says the default heat is off by more than the law's own local error.
- **An `R` miss in arms 3 to 5** says the flow's trajectory, its books, or a heat's total is wrong at
  rounding. **An `S` miss** says how a step's heat is split among holders, or flow beside diffusion,
  does not follow its scheme's order.
- **A stop** inside the registered domain fails its run (§3.7). It is followed by a labelled, non-blind
  diagnosis by someone other than the author, the judge and the checker.
- A miss is never dropped, rescaled or re-run at another step.

## 10. The rehearsal, and correcting a bound

**The rehearsal** (the protocol's §5) is the judge's whole scoring path, run on **invented** worlds through the
registered exporter, before the registration tag. The judge scores the builder's table of
`inputs_invented.json`'s worlds against `reference_invented.json`, every class exercised, honest and planted,
with the faults of §4 planted too. It must: pass every honest entry, catch every plant, take every stop and
refusal as expected, and flag every fault as §4 says.

- **No final fail can rest on a rounding bound that the rehearsal has not met,** since the counts of LAWS.md §9
  are derived without the engine's arithmetic. A bound an honest invented run misses is a defect (of the
  exporter, the judge, the engine or the references, found and fixed) or a bound to correct, as below.
- A rehearsal is evidence for the harness and the bounds. It is none for or against the request.

**A route to correct a bound.** Before the registration tag, and only when an honest invented run at the
rehearsal misses it, a bound or a count is corrected by a dated change to this folder that:
- **re-derives** it from a stated reason (a path of operations the count left out, or a case it did not
  cover), and shows the derivation;
- never fits it to a run, never sets it to an observed value times a margin, and changes no class and no
  window;
- is disclosed with the run that showed it, and re-tags the criteria, the references where their checks
  depend on it, and the judge, which re-parses its sample.

After a registered run no bound is corrected for any reason. A bound that cannot be re-derived stays, and the
rehearsal's miss is recorded.
