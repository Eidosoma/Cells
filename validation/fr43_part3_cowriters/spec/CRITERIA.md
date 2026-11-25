# Criteria, classes, tolerances, plants and verdicts

**Fixed before any reference or engine run exists.** Every number here is a constant of a formula. None comes from a
reference, an engine run or a probe of the registered worlds.
- "The reference" is the references agent's files (SPEC.md §7), "the run" an engine run read from its table
  (TABLE.md).
- A **family** is a (world, declared order) with its copies and its rungs, `inputs.json`'s `families`. The judged
  set is READOUTS.md §3's table, and the run names are `inputs.json`'s.
- **Two kinds of tolerance, never mixed** (D370): a **rounding** bound from an operation count (LAWS.md §7), and a
  **truncation** tolerance built from step halving with a declared order. A readout of one kind is never judged by
  the other.

## 1. Symbols

- h_1 > h_2 > … the rungs of a family, each half the last (`rungs_s`), S_j = T/h_j, T the world's `end_s`. The
  references' scales and S are read from `inputs.json` and the reference files, never from the engine's rows.
- e_round = m (S + 1) u s, m and s by READOUTS.md §2 and LAWS.md §7. For the pooled statistic of §3.3, S is S_j at
  the rung (the largest over the entries), so the bound is one number per (readout, rung). An event's time: m = 4, s
  = T. A row or book: m = 16.
- e_ref = the reference's largest `accuracy` over the entries of the readout (SPEC.md §4).
- u = 2⁻⁵³.

## 2. Rungs

`W5` and `W6`: n rungs, each half the last (`inputs.json`'s `rungs_s`, n of them). `W5-exact`: two, h_1 and h_1/4.
The **retry**, when owed (§7), adds the next halving (`retry_rung_s`) as one more rung of a family, and the fit is
then over the finest n of the n + 1, renumbered 1 to n. No other run of the family is remade.

## 3. The criteria, by class

### 3.1 E, equal

**Every judged event, in every run:** event k of copy c (k < K_c) has the reference's channel and the reference's
counts after it, and the engine's events are in increasing time with no duplicate. A copy with fewer than K_c events
in its record fails. **The integer ledger,** at every sample and every event: Σ_k w_k n_k is the declared total,
exactly. **The restart:** every row, book and event of a resumed run (TABLE.md §4) from its checkpoint to T equals
the uninterrupted run's, of the same family, copy and step, bit for bit (the sign of zero included). One wrong value
fails. **Its failure belongs to the judged run it resumes,** never to the support run alone. A missing or refused
resumed run leaves its arm at best inconclusive.

**D, on every run of role `judged`: it completes.** A judged run whose entry is refused with kind `check` (the
engine's own ledger or domain check of a completed row failed) **fails**: the check's failure is the evidence the
comparison would have formed. A judged run refused for another reason is refused (§4). No registered run is expected
to be refused or to stop.

**Runs that ran.** E, R and identity entries, and D, are judged on every run whose status is completed and whose
echo matches, whether or not its provenance or its record hash refuses it (§4). A run that did not complete has no
rows to judge and forms none: a stop (D) fails it, and any other refusal leaves its family's S entries not formed.

### 3.2 R, rounded

|run − expected| ≤ e_round + accuracy, for every entry of READOUTS.md §3's R column. The expected value is the reference's
(`W5-exact`'s event times: the exact decimal sums, accuracy at most SPEC.md §4's), or the run's own rows (the
identities of READOUTS.md §4, at every sample, with bound 16 (S + 1) u s_id where S = t/h from the registered grid
and s_id the identity's terms of the run's own values). An R entry is judged at every rung that runs, in every copy.

- **W5-exact's event times** are judged at both rungs, and the comparison is class R. No order is judged.
- **The identities** (READOUTS.md §4) are judged in every run of every world, the Lie plant included.

### 3.3 S, stepped

For readout y of a family with rungs h_1 … h_n (after a retry, the finest n of its n + 1, renumbered 1 to n), with
entries over the copies (READOUTS.md §5):

    E_n = sqrt( mean over entries of (y_{h_n} − y_ref)² )                        (the finest rung against the reference)
    d_j = sqrt( mean over entries of (y_{h_{j+1}} − y_{h_j})² ),   j = 1 … n−1      (engine only)
    est = max( d_{n−1}/(2^p − 1),  d_{n−2}/(2^p (2^p − 1)) ),    p = 2              (Roache's estimate; d_{n−1} is the finest)
    τ   = 3 est + e_ref + e_round(h_n)

- **The order is engine-only,** as FR-38's and the routing registration's are: no reference enters it. A d_j is
  **resolved** where d_j > 10 (e_round(h_j) + e_round(h_{j+1})). The used differences are the longest run of
  resolved ones from j = 1, of the n − 1. The order is **resolved** where at least three are used, and then q is the
  least-squares slope of ln d_j against ln h_j over them. Otherwise it is **unresolved**: reported, not judged.
- **The order window:** resolved, with q in [p − ½, p + ½] = [1.5, 2.5] (D271's half window; p = 2 is the declared
  order of the split scheme, since each half-step is exact or third order and the sequence is symmetric).
- **The size:** E_n ≤ τ. This is the one place the reference enters S. A wrong law converges at order 2 to the wrong
  value, so it passes its order and misses its size; a split of the wrong order misses its window.
- **Score.** An entry (readout, family) **passes** where the size is inside τ and the order is inside the window or
  unresolved. It **fails** where the size misses and the order is inside the window or unresolved. It **is
  inconclusive** where the order is resolved and outside the window, whatever the size, since the window is what
  lets τ be trusted (FR-25 and FR-38's precedent): it owes the retry (§7), and after it the finest n rungs are
  scored by the same rule, so that an order still outside the window stays inconclusive, never a pass and never a
  fail. It **is not formed** where any copy's run of any of its rungs is missing, did not complete, or departs in
  its echo, or the readout is missing in one: then it is inconclusive, and takes no retry.
- **The pooled root mean square is the one statistic:** the order, the estimate and the size use it. The errors
  against the reference at the coarser rungs, the pairwise orders and the finest triple are reported and judge
  nothing.
- **Why one fit over the differences, and not the finest pair.** The scatter of one ratio of neighbouring rungs is
  set by the phases of the events of that step (LAWS.md §5), so the order is one fit over several halvings, as W3's
  (FR-43 part 3, §2) was over its errors. It is taken here on the engine's own differences, with the window from the
  declared order (no tuned number) and the size from the engine's own step-halving.

## 4. Faults and refusals

**Nothing hides a fail.** Every entry that can be formed is judged. If any judged entry of a run or family fails,
its arm fails, whatever else of that run or family is refused, stopped or missing.

| Fault | What follows |
| --- | --- |
| The echo of `inputs`, `seed`, `first` or `operators` departs from the registered run (numbers to 10⁻¹² relative; an exact zero exactly; integers, strings and booleans exact, with the formatting rules of §4.1; a plant differs only by its declared change) | The run is not the registered one. It is **refused**, and nothing of it is judged |
| A judged leaf is missing, mistyped or non-finite | That readout is **refused** in that run. The rest of the run is judged |
| A sample time departs from its registered value (10⁻¹² relative; the resumed run's may start later), the event times are not strictly increasing, or an event or sample is duplicated | That readout is **refused** in that run. The rest of the run is judged |
| Provenance: `source` incomplete, `checkout_dirty` true, a missing snapshot or `record_sha256`, or an `engine_revision` that is not the registration tag's (not checked at the rehearsal, CRITERIA.md §10) | The run is **refused**, but its readouts are judged and a fail stands |
| Two runs with the same `record_sha256` | **Both** are refused (their readouts are judged and a fail stands). No two runs share one |
| A run's table keys are missing, or a table's hash departs from its `SHA256SUMS` | The run, or the table, is refused |
| A recorded-only leaf is missing, mistyped or non-finite | Flagged to the checker. Refuses nothing |
| A judged run refused with kind `check` | **Fails** (§3.1, D): a stop of the engine's own check |
| A run refused with kind `domain`, `definition` or `harness`, or any refused support or plant run | **Refused.** There is no expected refusal among the registered runs |
| A run in `missing`, or in neither list | **Refused** |
| A run name `inputs.json` does not list, or lists twice | Ignored and recorded |
| A retry run present though not owed | Recorded, flagged, and not judged |
| A support run refused or missing | Leaves its arm at best inconclusive. The run it supports is judged without it |

- **A refused run cannot pass.** With no failing entry it leaves its family's readouts not formed, and its arm at
  best inconclusive.
- **A refusal of provenance or of a shared record hash forms the entry.** The S entries are formed from every run
  that completed and whose echo matches; such a refused run caps its family's and its arm's result at inconclusive,
  and a fail (an E or R entry, or an S size miss with the order in its window or unresolved) that any of its entries
  gives is kept.
- **A family whose entry is not formed cannot pass** (§3.3). An E entry of a run that ran is judged whatever the
  family's S entries do.
- **A non-finite value anywhere is a fault, not a gap.**
- **Nothing passes empty.** An arm, a family, or a claim's line with no judged entry formed is inconclusive, never a
  pass. A plant whose named entry is not formed is unscorable, never caught. A class E entry with no event to
  compare is not formed, and a run with no judged event (K_c = 0) is not formed, which C0 prevents by its minimum
  counts.
- **The one place a fail can go unseen** is a departing echo, which leaves nothing of that run judged: it is not the
  registered world, the checker sees the departure and its cause.

### 4.1 The echo's formatting rules

- **Numbers.** 4 and 4.0 are equal; null and an absent key are equal where TABLE.md says so; a JSON integer is
  compared as a real. 1e-12 equals 1.0e-12.
- **Collections.** A declared set (READOUTS names, channel names, state names) is compared as a set, and a declared
  order (`operators`, `channels`, `unit_states`, `seeds`) as a list.
- **Names.** Strings compare exactly, and IDs compare exactly with the strings note (the protocol's §5), not with
  anything in this folder. A null in place of a list is a fault, never an empty list.
- **An echo is the definition the engine parsed and ran,** in `inputs.json`'s schema: never a copy of this folder's
  numbers.

### 4.2 C0, before any engine run is read

The judge reads `reference_invented.json`, then each reference file, then `draws_check`, `inputs_sha256` and the
protocol's hashes. It refuses, naming the fault:
- a missing registered key, or a class not in {E, R, S}, or an entry of a world the references do not carry;
- an `accuracy` above SPEC.md §4's, or a scale that is not positive, or a value that is not finite;
- `checks` with any entry not passing, a `draws_check` that is not identical;
- **the sizing** (SPEC.md §5): an expected honest q of any S entry that is unresolved, or outside [p − 0.4, p + 0.4]
  (here [1.6, 2.4], a tenth inside the judged window), an expected E_n above its τ, a plant with a margin below 10
  (§6.2), a class E plant with a zero distance, a family with fewer than its `minimum_events` (by the reference's
  K_c: per copy and in all), and a **missing** expected value. These are the conditions under which an honest run is
  expected to be judged: one that fails is corrected by a dated amendment to the registered inputs (never a
  criterion), with the reason, before the tag.

A fault is a refusal of the reference. A refused reference refuses the whole comparison of its world. A JSON object
with a duplicate key is a fault, in any file the judge reads.

## 5. What is judged where

READOUTS.md §3 lists it. Every judged entry is compared at every rung that ran and every compared sample or event.

## 6. The plants

### 6.1 The table

Each plant changes one thing and must fail the check named. **Formed:** a *reference* plant reads a run as the
planted reference; a *record* plant edits a copy of one run's record; an *engine* plant is a run with a declared
change of the driver.

| Plant | What | Formed by | Must fail | Arm |
| --- | --- | --- | --- | --- |
| P1 | W5's k_1 1% high | reference (SPEC.md §3) | S on `t_events`, `n_S_c`, `n_S_o`, `moved`, `xi_2` | W5 |
| P2 | W6's initiation k_I 1% high | reference | S on `t_events`, `n_R_c`, `n_R_o`, `lost`, `moved` | W6 |
| P3 | The second halves in declared order: Lie splitting, not Strang | engine: the runs `… lie`, `W5 reactions-first`, three finest rungs | S on `t_events`: E at its finest rung above the honest τ, and its fitted order (of E against the reference, over its own three rungs) outside the window | W5 |
| P4 | The size: every reference event time shifted by 10 times the expected honest τ | reference (the references form it from their sizing) | S on `t_events` | W5 and W6 |
| P5 | W5-exact's `assemble` rate 1% high | reference | R on `t_events` | W5-exact |
| P6 | One writer's book 10⁻³ high: `xi_2` of W5, `lost` of W6 | record | R: the identity carrying it | W5 and W6 |
| P7 | The transfer booked on one side only: the run's `n_S_o` (W5) or `n_R_o` (W6) with the moved amount left out | record | R: that row's identity | W5 and W6 |
| P8 | One judged event removed from the coarsest rung's copy 0, its later events renumbered | record | E: the trace | W5 and W6 |
| P9 | `assemble` reads the row at the node, not the cell | reference | S on `t_events` | W5 |
| P10 | The co-writer off | reference | S on `n_S_c`, `n_S_o`, `moved`, `xi_2` (W5) and on `n_R_c`, `n_R_o`, `lost`, `moved` (W6) | W5, W6 |

- The plants of the judged runs are formed by the judge from the honest runs, or by the references. Only P3 needs an
  engine run.
- **A plant's arm is the arm whose request it names**; a plant not caught fails that arm's claim (§6.3).

### 6.2 Power, stated before any run (D366)

- **The rule:** a plant's margin is its distance from the honest reference, at its best entry of the named check,
  over the expected honest tolerance there. It must be at least **10**.
- **Expected tolerances.** S: the sizing model's τ (SPEC.md §5). R: the formula of LAWS.md §7 and the identity's
  bound. E: non-zero distance (no margin).
- **Distances.** S: the pooled RMS between the honest reference and the planted reference over the common entries
  (event index k < min of the two K's, for `t_events`; every sample, for a row or book). P3: the pooled RMS between
  the honest reference and the Lie emulation at its rungs, and its expected fitted order over those rungs at most p
  − ¾ (1.25). P4: the shift itself. R: |planted − honest|. E: the number of entries that differ.
- **The references compute every margin** and report it, or the reason for a plant with none (P8, `no_margin` true,
  no margin). A plant below 10 is enlarged or replaced by a dated amendment before the registration tag, never after
  a run.

### 6.3 Scoring after the runs

- A plant is scored with the **honest run's** tolerance (the honest τ, or the rounding bound), never with a planted
  series' own. If the honest tolerance exceeds the planted distance the plant is **not caught**.
- **What "fails its check" means for a plant.** S: the pooled E_n against the planted reference exceeds the family's
  honest τ (the order is engine-only, so a wrong law or planted reference leaves it as it is). R: the entry exceeds
  its bound. E: the entry departs.
- **A reference plant** (P1, P2, P4, P5, P9, P10) is scored against every family of its world (both declared
  orders), and is **caught** when every series it names fails in every one. A plant of one family (P3) is scored on
  it alone.
- **P3 is caught** when its E (at the finest of its rungs, against the reference) exceeds the honest τ (§3.3), and
  its own fitted order, the slope of ln E against ln h over its three rungs, is below p − ½ (outside the window). It
  does not need the honest runs' order to fail.
- **P6, P7 and P8** are formed on the honest run of copy 0 at the world's coarsest rung: `W5 reactions-first` for P6
  to P8, `W6 gene-first` for P6-W6 to P8-W6. P6 multiplies the book, and is caught when an identity that carries it
  fails (READOUTS.md §4: n_S_c's, or n_R_c's). P7 sets the node row to its value at t = 0 at every sample, and is
  caught when the node identity fails. P8 removes the record's event k = ⌊K/2⌋, renumbers the later ones, and is
  caught when E fails (a channel or count departs, or the record has fewer than K events). A record with fewer than
  three judged events leaves P8 unscorable.
- A plant that reads an honest run that is refused or stopped is **unscorable**: neither caught nor not caught, and
  its arm is at best inconclusive.
- **An engine plant** (P3) that is missing is unscorable. One that completes with a fault in its record is refused,
  as any run, and is unscorable. One the engine's own checks stop is unscorable. A patch outside the plant it names
  (`host_patch` on any other run, or null on the Lie plant's runs) refuses that run.
- **The judge's self-tests:** one value of an E entry moved by one unit in the last place, a resumed run's row moved
  by one unit in the last place, an event time out of order, a run whose echo departs, and a run whose record hash
  is another run's, must each be flagged before the judge's tag.

## 7. The retry

- **Owed** by an S entry of an inconclusive family scored by order (§3.3), only from the judge's **first pass**. The
  judge writes `retry_owed.json`: `{"kind": "fr43 part 3 co-writers retry, version 1", "families": [...], "runs":
  [sorted run names]}`, and the lead records its hash. An entry that is inconclusive because it is not formed owes
  none.
- **What is run:** for each owed family, the (n + 1)th rung's runs (every copy), named `{world} {first}-first
  h={retry_rung_s!r} c{copy} retry` (the step as its `repr`, as `inputs.json`'s names write it), role `judged`, no
  other role.
- **Then:** the family's readouts are re-scored over the finest n rungs by the same rule. Entries that passed or
  failed keep their score.
- **Only once.** An owed retry run is judged as any judged run (its E, R and D entries, and a fail there counts),
  and the family's S entries are re-scored with its finest n rungs. A retry run present though not owed is recorded
  and flagged, and nothing of it is judged. A missing owed retry run leaves the family's entry inconclusive.

## 8. Verdicts

- **A run** fails if any judged entry (E, R) of it fails, or if D fails (§3.1). **A family** fails if any of its S
  entries fails or any of its runs fails. It is inconclusive if any of its S entries is inconclusive or not formed,
  or any of its runs is refused; else it passes.
- **An arm** (W5: both families, the restart, its plants; W5-exact: both families and its plant; W6: both families,
  its restart and its plants), after the retry, fails if any family fails or a plant is not caught (its must-catch
  checks); else it is inconclusive if any family is inconclusive or a support run or plant is unscorable; else it
  passes.
- **FR-43 part 3's co-writer claim** (the population beside the reactions and beside the gene unit) is read from the
  arms: it passes when all three arms pass, fails when any fails, and is inconclusive otherwise (the W5-exact line
  judged on its own, since it holds whatever the other two say, and the two second-order lines on theirs). It is
  reported as three lines: second order beside the reactions (W5), exact times with constant rates (W5-exact),
  second order beside the gene unit (W6). No other line of the request is judged here.
- **The two declared orders are two runs of one claim:** each is its own family, and either failing fails its arm.
  Nothing in a run's own results tells the two apart, beyond the echo (§9).
- **The record** lists, for every entry: the family, run, readout, class, statistic, tolerance, ratio, q and (for S)
  the pairwise and triple orders, and the verdict; every refusal, stop and flag, with its cause; and every plant's
  margin and score.

## 9. What a miss means, stated before any run

- **An S miss** (an event's time or a shared amount off by more than three times its own step-halving estimate, in a
  resolved order inside the window) says the split of the two writers is not the one declared, or the size is off. A
  resolved order outside the window says the two writers are not split at second order (a missing symmetric half, or
  a clock or transfer reading the wrong state), or that a world is too stiff for it.
- **An R miss** in W5-exact says the engine's event times depend on a co-writer's rows or its declared order when no
  rate reads them (or that a rounding count is too small: the route of §10). In an identity, that a writer's book
  does not equal what its rows moved (a missing holder is this author's fault, and is corrected, not judged).
- **An E miss** (a channel, a count, the integer ledger, a restart) says the population's own event sequence is not
  the reference's: a wrong draw, a wrong propensity, a wrong state.
- A miss is never dropped, rescaled or re-run at another step.

## 10. The rehearsal, and correcting a bound

**The rehearsal** (the protocol's §6) is the judge's whole scoring path run on **invented** worlds through the
registered exporter, before the registration tag: a table of the invented worlds' runs (2 copies or more), an
invented reference, the plants, the restart, and every fault of §4 planted. The `engine_revision` check of §4 is not
applied to it, since no registration tag exists yet. It must: pass every honest entry (that its sizing says will
pass, §8 of SPEC.md), catch every plant, and flag every fault as §4 says.

- **No final fail can rest on a bound the rehearsal has not met.** The counts of LAWS.md §7 are derived from an
  arithmetic and not the engine's. A bound that an honest invented run misses is a defect (of the exporter, the
  judge, the engine or the references, found and fixed) or a bound to correct, as below.
- **A route to correct a bound.** Before the registration tag, and only when an honest invented run at the rehearsal
  misses it, a bound or a count is corrected by a dated change to this folder that re-derives it from a stated
  reason (a path of operations the count left out), shows the derivation, fits it to nothing, changes no class, no
  window and no statistic, and re-tags the criteria, the references where their checks depend on it, and the judge,
  which re-parses its sample. After a registered run no bound is corrected.
- A rehearsal is evidence for the harness and the bounds, and none for or against the request.
