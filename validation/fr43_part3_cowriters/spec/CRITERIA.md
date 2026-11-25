# Criteria, classes, tolerances, plants and verdicts

**Fixed before any reference or engine run exists.** Every number here is a constant of a formula. None comes from a
reference, an engine run or a probe of the registered worlds.
- "The reference" is the references agent's files (SPEC.md §7), "the run" an engine run read from its table
  (TABLE.md).
- A **family** is a (world, declared order) with its copies and its rungs (`inputs.json`'s `families`). The judged
  set is `inputs.json`'s `judged`, restated in READOUTS.md §3 and §4; the run names are `inputs.json`'s.
- **Two kinds of tolerance** (D370): a **rounding** bound from an operation count (LAWS.md §7), which alone judges
  class R; and a **truncation** tolerance built from step halving with a declared order, which judges class S, with
  the rounding bound and the reference's accuracy as its floor. A readout of one class is never judged by the
  other's.

## 1. Symbols

| Symbol | Meaning |
| --- | --- |
| T | the world's `end_s` (s) |
| h_1 > h_2 > … > h_n | the family's rungs (`rungs_s`), each half the last in W5 and W6 (n = 6), h_1 and h_1/4 in W5-exact (n = 2) |
| S_j = T/h_j | the number of steps of a run at rung j; S = t/h the number to a sample time t, both from the registered grid |
| K_c | the number of judged events of copy c: the reference's (SPEC.md §3), never the engine's |
| m, s | the operation count and the scale of LAWS.md §7 and READOUTS.md §2; m = 4 and s = T for an event's time, m = 16 for a row or book |
| e_round = m (S + 1) u s | the rounding bound, u = 2⁻⁵³. For a pooled statistic S is S_j at the rung (the largest over the entries) |
| e_ref | the reference's largest `accuracy` over the entries of the readout (SPEC.md §4) |
| p | a readout's declared order: 2, or 3 for the gene unit's own `made` and `exits` |
| g | `inputs.json`'s `guard_steps` |

## 2. Rungs and the retry

`W5` and `W6` run at n rungs, each half the last. `W5-exact` runs at two, h_1 and h_1/4. The **retry**, when owed
(§7), adds one run per copy at the next halving (`retry_rung_s`): the finest of the n + 1 rungs. The coarsest is
dropped, so the order is fitted and the size read over the finest n. Nothing else of the family is remade.

## 3. What is judged, by class

### 3.0 Formation, and what a refusal does

**Formed.** An entry is **formed** where no run it reads is missing or refused by any row of §4 (**provenance and a
shared record hash included**), and everything it reads is present, readable and registered. A judged entry that is
not formed makes its **family inconclusive, never a pass.** (A run's entries are its family's. A restart's are those
of the run it resumes, §3.6: a restart made from a dirty checkout leaves its judged run's restart entry unformed.)

**Refused.** The faults of §4 say which runs are refused. A refused run leaves its entries unformed, so it cannot
pass. Unformed is not unread: what can be compared is compared, and a miss fails.
- Where the echo departs, or the table's hash does (§4's first two rows), **nothing of the run is judged**, in any
  class.
- By any other refusal, the E and R entries are compared on what the run holds, and a miss fails. A run that did not
  complete is compared on the events and samples it lists, and their number is not asked of it.
- The S entries of a run refused by provenance or a shared record hash are compared too, and a miss fails. Those of
  a run refused otherwise, and §3.5's pair of a refused run, are not compared.

**What unforms an S entry, or the pair, listed once.** Any one of these, in any run it reads (every copy at every
rung of the family; for the pair, every copy of both families at h_1):
- the run is missing, or did not complete (§4);
- nothing of it is judged: its echo departs, or its table's hash does;
- it is refused by **any other row of §4, provenance and a shared record hash included** (of these two a miss fails
  all the same): a key of its table or of its entry (missing, or of another type), its `host_patch` or its
  `restart`, its sample times, a name listed twice or in `missing` and `runs`, a duplicate key;
- a leaf the entry reads is missing, mistyped or non-finite, or is not as long as `t`;
- for `t_events`: its record contradicts itself or lists fewer than K_c events (its trace then fails E too, §3.1).

**What unforms an E or R entry:** its run is missing or refused by any row of §4, or a leaf it reads is missing,
mistyped or non-finite, or is not as long as `t`. (W5-exact's identities have the running check of §3.2 besides.)

### 3.1 E, equal

Bit for bit, the sign of zero included:
- **The trace.** The record is the event sequence of a run of its world:
  - its events have the indices `first_index`, `first_index` + 1, …, and `first_index` is 0 in a run that starts at
    t = 0;
  - its times increase strictly;
  - the counts after an event are the counts before it changed by its channel's declared jump (before the first
    listed event: the initial counts, or, in a resumed run, the counts after the uninterrupted run's event
    `first_index` − 1);
  - `events_total` is `first_index` plus the number of events listed, and it is at least K_c;
  - for every k with `first_index` ≤ k < K_c, the event of index k has the reference's channel and the reference's
    counts after it.

  **A record that breaks any of these fails E,** by one rule (events out of order, counts against a channel, a total
  against its list, too few events, another event than the reference's). Of a resumed run the events before
  `first_index` are the uninterrupted run's, and they count toward K_c. Of a run that did not complete,
  `events_total` and the number K_c are not asked.
- **The ledger.** Σ_k w_k n_k (w_k the `subunits` of unit state k) is the declared total at every sample, and after
  every listed event (the judge forms this from `counts_after`).
- **The restart.** Every row, book and event the resumed run lists, and its `events_total`, equal the uninterrupted
  run's, matched by sample time and by event index (`first_index` plus its place in the list). An event the
  uninterrupted run does not have is a difference. **The resumed run is checked at its registered time:** its
  `restart.time_s` is `inputs.json`'s (10⁻¹² relative), its `first_index` is the number of events the uninterrupted
  run has at or before that time, its `t` holds every registered sample at and after it, and its list holds every
  event the uninterrupted run has after it. One that does not is refused and its restart entry is not formed; a
  difference in what it lists, or in `events_total`, fails all the same.

### 3.2 R, rounded

|run − expected| ≤ e_round + accuracy:
- **The start** (READOUTS.md §4). At the sample t = 0 every row and book equals its declared value (`inputs.json`'s
  `start`): a bound of 4 u |declared| for a nonzero value, and exactly zero where the declared value is 0.
- **The identities.** Each of `inputs.json`'s `judged[world].identities` at every sample of every run: the sum of
  the named terms over the run's own rows and books is zero within 16 (S + 1) u s_id, where s_id is the sum of the
  absolute values of the identity's terms at that sample (S = t/h). The identities name every holder of their amount
  (LAWS.md §2 and §3).
- **W5-exact's event times:** within e_round (m = 4) plus the reference's accuracy, at each rung, for k < K_c.
- **W5-exact's running check.** An identity of zero against zero proves nothing. So in W5-exact the identities are
  formed only where ξ_1, ξ_2 and |moved| at the last sample each exceed 10⁴ times the bound (16 (S + 1) u s_id, at
  the last sample) of the identity that carries it: `X` for ξ_1, `Y` for ξ_2 and `S node` for moved, **and each is
  there at least half of the reference's, of the same sign** (nearer to its size than to absent). The 10⁴ is
  derived: a plant that raises a book by 10⁻³ must fail its identity by a margin of 10, so a book below 10⁴ times
  its identity's bound cannot be told from rounding. In a run in which one is not exceeded, or one is below half, an
  identity inside its bound is not formed (it passes nothing, so the family is inconclusive) and one outside it
  fails all the same (`inputs.json`'s `judged` holds the readouts, the multiple and the half,
  `fraction_of_reference`, under `running`).

### 3.3 S, stepped

For a readout of a family with rungs h_1 … h_n (after a retry the finest n of n + 1, renumbered 1 to n), pooled over
the entries of READOUTS.md §5:

    E_n = sqrt( mean over entries of (y_{h_n} − y_ref)² )                              (the finest rung against the reference)
    d_j = sqrt( mean over entries of (y_{h_{j+1}} − y_{h_j})² ),   j = 1 … n−1            (engine only)
    est = max( d_{n−1}/(2^p − 1),  d_{n−2}/(2^p (2^p − 1)) )                               (Roache's estimate; d_{n−1} is the finest)
    τ   = 3 est + e_ref + e_round(h_n)

- **The order is engine-only:** no reference enters it. A d_j is **resolved** where d_j > 10 (e_round(h_j) +
  e_round(h_{j+1})); the used differences are the longest run of resolved ones from j = 1. With at least three used,
  q is the least-squares slope of ln d_j against ln h_j over them, and the window is [p − ½, p + ½] (D271's half
  window).
- **An order that cannot be formed** (fewer than three used differences) makes the entry **inconclusive**, unless
  the entry is named in `inputs.json`'s `judged[world].at_rounding` (an entry whose truncation is below what the
  rounding bound resolves, by construction: W6's `made` and `exits`, READOUTS.md §5, and C0 checks the name). A
  named entry is judged by its size alone.
- **The size:** E_n ≤ τ. A wrong law converges at its order to the wrong value, so it misses its size; a split of
  the wrong order leaves its window.
- **Score.** An entry that is not formed (§3.0) is inconclusive, unless §3.0 compares it and it misses: it fails. Of
  the formed ones:
  - **an entry named in `at_rounding`** passes where its size is inside τ and fails where it is not, whatever its
    order;
  - **any other entry** passes where its size is inside τ and its order is inside the window, and fails where its
    size misses and its order is inside the window. Where its order is formed and outside the window it is
    inconclusive, whatever the size (the window is what lets τ be trusted: FR-25 and FR-38's precedent), and it owes
    the retry (§7). Where its order cannot be formed, or where a d_j is exactly zero (two rungs that are one
    series), it is inconclusive and owes none.
- **The pooled root mean square is the one statistic:** order, estimate and size use it. The errors against the
  reference at the coarser rungs, the pairwise orders and the finest triple are reported and judge nothing.

### 3.4 D, completes

A run of role `judged` that is refused with kind `check` (the engine's own ledger or domain check of a completed row
failed) **fails**: the check's failure is the evidence the comparison would have formed. It cannot be re-run. The
same on a plant or support run counts against that run's own use only (the plant is unscorable, the restart is not
formed).

### 3.5 The pair: the two declared orders differ

The two declared orders of a world are two runs of the coupled process, and at the coarsest rung they differ by the
split error in every readout that the declared order can change. So for each readout of `inputs.json`'s
`judged[world].orders_differ` the pooled root mean square (§3.3's entries) of the difference between the two
families' runs at h_1 must exceed 10 e_round(h_1). **Otherwise the two are the same series (a copied family), and
both families are inconclusive.** A fail of theirs stands.
- Readouts the order cannot change are excluded by name: W6's `made` and `exits`, which only the gene unit writes.
- W5-exact has no S entry, so it checks two of its recorded rows, `n_S_c` and `moved`.
- **W5-exact's two rungs differ as the pair does:** in each of its families the pooled root mean square of the
  difference between the runs at h_1 and at h_1/4, in each of those two rows, must exceed 10 e_round(h_1). Otherwise
  the two are one rung (a copied one), and the family is inconclusive.

### 3.6 What the plant runs' and support runs' entries count for

- **Plant runs' own entries** (E, R, D, identities) are judged for their scores only (§6) and never toward an arm.
- **A restart's entries** (its trace and ledger, its equality, and its identities at its own samples) belong to the
  judged run it resumes, the uninterrupted run of its family, copy and step: its failure and its unformed case are
  that run's. Nothing else of a support run counts. Its identities read the uninterrupted run's t = 0 row, since it
  has none.

## 4. Faults and refusals

**What can be compared is compared** (§3.0; §11 says where a fail can go unseen). If any judged entry of a run or a
family fails, its arm fails, whatever else of that run or family is refused, stopped or missing.

| Fault | What follows |
| --- | --- |
| The echo departs from the registered run (§4.1) | The run is not the registered one. It is refused, and **nothing of it is judged** (§11) |
| A table's hash departs from its line in `SHA256SUMS`, has no line in that file, departs from the lead's record, or is one of the format sample's | Its runs are refused, and **nothing of them is judged** (§11). An absent `SHA256SUMS` is recorded and flagged, and refuses nothing by itself |
| A top-level key of a table is missing, of another type, or (for `kind`, `arm`, `units`) of another value | Every run in it is refused |
| A key of an entry (a row of TABLE.md §3; `source`, `record` and `record_sha256` are the provenance row's, and a name missing from `series` is the missing leaf's) is missing or of another type (a `null` only where that row allows it) | The run is refused |
| A completed run with a non-null `refusal`, or a refused run without one | The run did not complete: it is refused with the refusal's kind, or `harness` if there is none |
| `events_total` above `trace_capacity` (a truncated trace) | The run did not complete: refused with kind `harness` |
| A completed run whose `t` is not the registered `samples_s`: a sample missing, one extra, or one that departs (10⁻¹² relative; 0 exactly). A resumed run: §3.1 | The run is refused |
| A `host_patch` on a run that is not the Lie plant's, or a null or another `id` on one that is (such a run's echo is its honest run's **apart from `variant`**, §4.1); a `restart` on a run that is not a resumed one, or a null on one that is | The run is refused |
| **The missing leaf:** a judged leaf is missing (a name missing from `series` included), mistyped or non-finite (a NaN or an infinity in an entry included), or not as long as `t` | The entries that read it unform, in that run. The rest of the run is judged |
| A record that contradicts itself (counts against its `channel`, `events_total` against its list, an event out of order), or with fewer than K_c events | Its trace fails E (§3.1), and the S entry `t_events` unforms |
| A resumed run whose `restart.time_s` departs, whose `first_index` is not the number of events the uninterrupted run has at or before that time, or that does not list each later sample and event | It is refused, and its restart entry is not formed (§3.1). A difference in what it lists fails |
| Two runs with the same `record_sha256` (a record plant's edited copy, which the judge makes and no table holds, is no run of its own) | Both are refused: their entries are unformed, compared all the same, and a miss fails. No two runs share one |
| Provenance: `source`, `record` or `record_sha256` missing or incomplete, `checkout_dirty` true, a missing snapshot, or an `engine_revision` that is not the registration tag's (not checked at the rehearsal, §10) | The run is refused: its entries are unformed, compared all the same, and a miss fails |
| A judged run refused with kind `check` | **Fails** (§3.4) |
| A run refused with kind `domain`, `definition` or `harness`, or any refused support or plant run | It did not complete, and is refused. No registered run is expected to be refused or to stop |
| A run in `missing` (and not in `runs`), or in neither list | It is missing: refused |
| A run in `missing` and in `runs`, or a run name listed twice (in two tables, or twice in one `runs`) | The run is refused. Each entry under its name is judged (E, R, D) and a fail in any stands |
| A run name that neither `inputs.json` nor the retry's rule (§7) lists | Ignored and recorded. A retry's name (§7) is listed where a retry is owed |
| An unowed retry run | Recorded, flagged, and not judged |
| A support run missing or refused (by any row, provenance and a shared record hash included) | Leaves its judged run's restart entry unformed, and nothing else |
| A leaf inside a recorded-only key (`definition`, `checks`, `pools_at_event`, `samples_echo`, `steps`) is missing, mistyped, non-finite, or another than the grid's | Flagged to the checker. Refuses nothing |
| A JSON object with a duplicate key | In a reference file: that file is refused. In a table's entry: that run is refused. Elsewhere in a table (a name twice in `runs` is above): its runs are refused |
| A NaN or an infinity | In a reference file: that file is refused. In a table's entry: it is the missing leaf's case (or, inside a recorded-only key, that row's). Elsewhere in a table: its runs are refused |

- **An arm is inconclusive at best** where any of its judged entries is unformed or inconclusive, or any of its
  judged runs is refused, unless one of them fails.
- **A non-finite value anywhere is a fault, not a gap.**
- **Nothing passes empty.** An arm, a family, or a line of the request with no judged entry formed is inconclusive,
  never a pass. A plant whose named entry is not formed is unscorable, never caught.

### 4.1 The echo

`inputs`, the entry's own keys (`world`, `first`, `copy`, `step_s`, `seed`, `variant`) and `operators` are compared
with the registered ones:
- **Numbers** to 10⁻¹² relative; a declared zero exactly zero; integers and strings exactly; 4 and 4.0 are equal, as
  are 1e-12 and 1.0e-12; a JSON integer is compared as a real. **null and an absent key are equal** for `read`, and
  for every optional key (one whose registered value is null).
- **Collections.** A collection keyed by id (the reactions, the rows, the reactants) is compared by id, in any
  order. A declared order (`channels`, `unit_states`, `operators`) is compared as a list.
- **The echoed keys** are exactly `inputs.json`'s `echo`: the world's keys of its kind and the run's keys, the
  excluded ones left out. A planted run's echo (the Lie plant's) equals its honest run's, and a resumed run's its
  uninterrupted run's, **apart from `variant`**, which is its own registered one (the Lie plant's declared change is
  in its `host_patch`, not in its echo).
- **IDs compare exactly with the strings note** (the protocol's §5) and with nothing in this folder. At the
  rehearsal, which comes before that note, `operators` is compared with the list in the builder's own README (§10).
- An echo is the definition the engine parsed and ran, in this schema: never a copy of this folder's numbers. A run
  refused at parse has none (TABLE.md §3): it did not complete, and it holds nothing to judge.

### 4.2 C0, before any engine run is read

The judge reads `reference_invented.json`, then each reference file, then `draws_check`, `inputs_sha256` and the
protocol's hashes. A fault is named and refuses the reference, and a refused reference refuses the comparison of its
world:
- a missing registered key, a class other than `inputs.json`'s `judged`, or an entry of a world the references do
  not carry;
- an `accuracy` above SPEC.md §4's, a scale that is not positive, a value that is not finite;
- a `checks` entry that does not pass, a `draws_check` that is not identical;
- **the sizing** (SPEC.md §5): for an S entry not named in `at_rounding`, an expected order that cannot be formed or
  is outside [p − 0.4, p + 0.4] (a tenth inside the window); **for an entry named there, three or more used
  differences** (it is not at rounding, so its name is wrong); for any S entry, an expected E_n above its expected
  τ; a plant's margin below 10 (1 − 10⁻⁹) (§6.2); P3's expected order not within ¼ of p − 1 (§6.2); a class E plant
  with a zero distance; a pair (§3.5), or W5-exact's two rungs, whose expected ratio to its threshold is below 10;
  W5-exact's running check (§3.2) not met by the references' own extents; a family with fewer than its
  `minimum_events` (by the reference's K_c: per copy and in all); a missing expected value.

These are the conditions under which an honest run is expected to be judged. A world that misses one is changed by a
dated amendment to the registered inputs (never to a criterion), with the reason, before the tag.

## 5. What is judged where

READOUTS.md §3 and §4 list it, by world, with `inputs.json`'s `judged`. Every entry is judged at every rung that ran
and every sample or event that is registered, with the formation rules of §3.0.

## 6. The plants

### 6.1 The table

Each plant changes one thing and must fail the check named. **A reference plant** reads the honest runs against a
planted reference (LAWS.md §9). **A record plant** edits a copy of one honest run's record. **An engine plant** is a
run with a declared change of the driver. The plants of a world's families are in `inputs.json`'s `plants`.

| Plant | What | Formed by | Must fail (every series named) |
| --- | --- | --- | --- |
| P1 | W5's k_1 1% high | reference | S on every S readout of W5 |
| P2 | W6's initiation k_I 1% high | reference | S on every S readout of W6 |
| P3 | The second halves in declared order: Lie splitting | engine: the runs ` lie`, W5 reactions-first, three finest rungs | S on `t_events`: its own order (over its three rungs) inside [p − 3/2, p − ½], one order lost (§6.3) |
| P4 | A size: every reference event time moved by 10 expected τ | reference, the shift and the margin per family | S on `t_events` |
| P5 | W5-exact's `assemble` rate 1% high | reference | R on `t_events` |
| P6 | One book 10⁻³ high (`xi_2`; `lost`) | record | R: the identities that carry it |
| P7 | The node's row at its t = 0 value (the transfer booked on one side) | record | R: the node identity |
| P8 | One event removed, the later renumbered and `events_total` lowered | record | E: the trace |
| P9 | `assemble` reads the row at the node | reference | S on `t_events` |
| P10 | The co-writer off | reference | S on the S readouts it writes |
| P11 | W6: the transcription's factor 1 − e^x dropped | reference | S on `made`, `exits`, `n_R_c`, `lost`, `t_events` |
| P12 | W6: the degradation's factor 1 − e^y dropped | reference | S on `lost`, `n_R_c` |
| P13 | W6: a product not released (Pi) | record | R: the identity `Pi` |
| P14 | W6: a start amount 1% off (N, M, Pi, free machines) | record | R: `start`, on each of the four |
| P15 | W6: the monomer neither made nor consumed (N, M unchanged) | record | R: the identities `N` and `M` |

- **Wrong W6 engines that must fail a judged entry:** a reversibility factor dropped (P11, P12), a product not
  released (P13), a start amount wrong (P14), and the monomer neither made nor consumed (P15). Each must fail a
  judged entry with a margin of at least 10: P11 and P12 fail the size of `made`, `exits` or `lost`, P13 and P15 the
  identities of W6's monomers, P14 the start (each of its four).
- **P3 and P4 rest on the order check.** The size of S has almost no power against a first-order engine, since τ is
  formed from that engine's own differences and grows with its error. P3 (Lie) is caught because its own order is
  one lower (§6.3), not by its size. P4 shows the size only for a family whose honest order has passed, against the
  honest τ; a first-order engine is caught by the window alone.

### 6.2 Power, stated before any run (D366)

- **The rule:** a plant's margin is its distance from the honest reference (or the honest record), at its best entry
  of the named check, over the expected honest tolerance there. It must be at least **10** (read with a relative
  slack of 10⁻⁹).
- **Expected tolerances.** S: the sizing model's τ of the family (SPEC.md §5). R: the formula of §3.2. E: non-zero
  distance.
- **Distances.** S: the pooled RMS between the honest and the planted references over the common entries (for
  `t_events` the events k < K_c that the planted reference also has, for a row or a book every sample t > 0; with
  none, the plant has no margin, a fault of §4.2). P3: the pooled RMS between the honest reference and the Lie
  emulation at its rungs, and its expected order over them within ¼ of p − 1 (a quarter inside the ends of §6.3's
  window). P4: the shift, per family, with its margin. R: |planted − honest|. E: the number of entries that differ.
  P14: the 1% of each start amount.
- **The references compute every margin**, per family, and report it, or the reason for a plant with none (P8,
  `no_margin`). A plant below 10 is enlarged or replaced by a dated amendment before the tag, never after a run.

### 6.3 Scoring

- **What is scored.** A plant's entries are the pairs of a family of its `families` (`both`: every family of its
  world) and a check of its `must_fail`. Each is scored **once**, with the honest run's tolerance, and only where
  the honest entry it reads passed: at the first pass, or, where that entry was inconclusive at the first pass and
  owed the retry, after the retry if it then passed. **A score once given stands:** a retry does not re-score it.
  Where the honest entry did not pass (failed, inconclusive or not formed) the plant's entry is unscorable: neither
  caught nor not caught.
- **What "fails its check" means.** S: the pooled E_n of the honest runs against the planted reference, over the
  common entries (§6.2), exceeds the family's honest τ. R: at least one entry of the check exceeds its bound. E: the
  entry departs.
- **A reference plant** is caught when every one of its entries fails. P3 is caught when its own order, the slope of
  ln E (its own runs against the reference) against ln h over its three rungs, is inside [p − 3/2, p − ½] (p = 2,
  the scheme's order: 0.5 to 1.5): the half window of §3.3 about p − 1, the order of a step whose second halves run
  in declared order. Another order does not show the loss, and P3 is then not caught.
- **A record plant** edits the honest run of copy 0 of the family named, at the world's coarsest rung, and is caught
  when every named check fails on the edited record.
- **A plant with an unscorable entry** is not caught if one of its scored entries is not caught, else unscorable.
- **If the honest tolerance exceeds the planted distance, the plant is not caught.**
- **An engine plant** that is missing, refused or stopped is unscorable.
- **The judge's self-tests**, before its tag: one value of an E entry moved by one unit in the last place, a resumed
  run's row moved by one unit in the last place, an event out of order, an echo that departs, and a record hash
  shared by two runs, must each be flagged.

## 7. The retry

- **Owed** by an S entry whose order is formed and outside the window (§3.3; never by a named entry), only from the
  judge's **first pass**. The judge writes `retry_owed.json`, `{"kind": "fr43 part 3 co-writers retry, version 2",
  "families": [...], "runs": [sorted names]}`, and the lead records its hash.
- **What is run:** for each owed family, the runs at `retry_rung_s`, one per copy, named `{world} {first}-first
  h={step!r} c{copy} retry`, role `judged`. A retry's name counts as registered where a retry is owed.
- **Then:** only the S entries that owed the retry are re-scored, over the finest n rungs. Every other entry keeps
  its first score: one that passed, failed or could not be formed is not scored again. The retry runs' own E, R and
  D entries are judged as any judged run's. An entry still outside the window stays inconclusive. The pair (§3.5) is
  read at the first pass and is not read again.
- **Only once.** A retry run present though not owed is recorded, flagged and not judged. A missing owed retry run
  leaves its entries inconclusive. A refused or stopped run takes no retry.

## 8. Verdicts

- **A run** fails if any judged entry (E, R) of it or of its restart fails, or if D fails. **A family** fails if any
  of its S entries fails or any of its runs fails; else it is inconclusive if any of its judged entries (E, R, S) is
  unformed or inconclusive, its pair (§3.5) is unformed or does not differ, W5-exact's two rungs do not differ, or
  any of its runs is refused (a provenance refusal included); else it passes.
- **An arm** (W5: both families; W5-exact: both families; W6: both families; with their restarts and plants), after
  the retry, fails if any family fails or a plant is not caught (its must-fail checks), else is inconclusive if any
  family is inconclusive or a plant is unscorable, else passes.
- **FR-43 part 3's co-writer claim** reads the three arms: it passes when all three pass, fails when any fails, and
  is inconclusive otherwise. It is reported on three lines: second order beside the reactions (W5), exact times with
  constant rates (W5-exact), second order beside the gene unit (W6, with the gene unit's own material judged). Each
  line stands on its own arm. No other line of the request is judged here.
- **The record** lists every entry: family, run, readout, class, statistic, tolerance, ratio (0 where the statistic
  and the tolerance are both 0, as for `engaged` and `transit` at t = 0), q and p, the pairwise and triple orders,
  and the verdict; every refusal, stop and flag, with its cause; and every plant's margin and score.

## 9. What a miss means, stated before any run

- **An S miss** (an event time, a shared amount or a gene-unit total off by more than three times its step-halving
  estimate, the order inside its window) says the law of the run is not the declared one, or its book is not what
  moved its row. **A formed order outside the window** says the two writers are not split at the declared order (a
  missing half, or a clock or a transfer that reads the wrong state), or that a world is too stiff for it.
- **An R miss** in W5-exact says the engine's event times depend on a co-writer's rows or the declared order when no
  rate reads them (or that a rounding count is too small: §10). An identity's miss says a writer's book is not what
  its rows moved. A start miss says the engine began from other amounts than the declared ones.
- **An E miss** says the population's own sequence of events, its ledger or a restart is not the reference's. **A
  pair that does not differ** says that one family's runs are the other's, or that the declared order did not reach
  the step.
- A miss is never dropped, rescaled or re-run at another step.

## 10. The rehearsal, and correcting a bound

**The rehearsal** is the judge's whole scoring path, run on **invented** worlds through the registered exporter
(TABLE.md), before the registration tag: the invented runs, references, plants, restart, retry and every fault of §4
planted. It must pass every honest entry that its sizing says will pass, catch every plant, and flag every fault as
§4 says. The `engine_revision` check of §4 is not applied to it, since no registration tag exists yet. Nor does the
strings note, so there `operators` is compared with the list in the builder's own README.

- **No final fail can rest on a bound the rehearsal has not met.** The event-time count of LAWS.md §7 was written
  with the engine's own clock and hazard sum in view (the author read the source; the protocol's §10), the count of
  16 for a row from the operators' declared increments. Neither is an observed error. A bound that an honest
  invented run misses is a defect (of the exporter, the judge, the engine or the references, found and fixed) or a
  bound to correct, as below.
- **A route to correct a bound.** Before the registration tag, and only when an honest invented run misses it, a
  bound or a count is corrected by a dated change to this folder that re-derives it from a stated reason, shows the
  derivation, fits it to nothing, changes no class, window or statistic, and re-tags the criteria, the references
  where their checks depend on it, and the judge. After a registered run no bound is corrected.
- A rehearsal is evidence for the harness and the bounds, and none for or against the request.

## 11. What a pass cannot show

- **The channel rule's use of the second draw.** Every site has 2 subunits, so one channel has a non-zero propensity
  at each state: the second draw never decides a channel (LAWS.md §1), and the channels of a site alternate. So
  **class E's trace tests that the events alternate from the declared start and that there are at least K_c of
  them;** it does not test the choice of a channel (whatever draws it), and not the times (S's, and R's in
  W5-exact).
- **A small shift.** A timing or amount error below τ (about three times the finest step's own error, at the
  registered ladder) passes. The magnitudes of τ are the references' (SPEC.md §5), not this file's.
- **The first-order engine's size.** The size of S has almost no power against an engine of lower order (§6.1). The
  order window is what catches it.
- **The order of `made` and `exits`.** They are judged by size alone (§3.3): the gene unit's own half-step may be of
  another order and still inside the size.
- **Books formed from rows.** TABLE.md asks for the writer's own account. Books formed as differences of rows would
  satisfy every identity, and nothing in a table shows which they are.
- **The order of W5's reactions' own half-step.** A half-step of second order keeps W5's order inside its window and
  its size, so a pass does not show that the reactions' own order is higher.
- **A family copied at finer rungs.** The pair is read at the coarsest rung alone, so a family whose finer rungs are
  the other's passes it.
- **A pass after a retry drops the coarsest rung.** It is read over the finest n rungs, and says nothing of h_1.
- **An equal error in W6's `inits`, `engaged` and `free`.** The identities tie them to each other and to `made`, and
  no reference judges them, so an error the three share passes.
- **The two declared orders' labels.** The results of W5 and W6's two families differ (§3.5), and nothing in a run
  says which is which but the echo of its operators.
- **The finest step alone is measured against the reference;** coarser steps enter the order only through the
  engine's own differences. A pass says nothing of an engine's error at a step above the ladder, or at λ dt of order
  one.
- **W5-exact judges event times and identities only.** Its amounts, published by the references, are not judged
  against them (the running check of §3.2 asks only that each book be at least half of its reference).
- **A fail that goes unseen.** A record that is there is not judged at these rows of §4: an echo that departs and a
  table whose hash departs (nothing of the run); a run name that is not registered and an unowed retry run (no run
  of the registration); and, for the S entries, every other refusal but provenance and a shared record hash (for the
  pair, any refusal). A missing run, a run cut short (the events and samples it does not list) and a non-finite
  value in a judged leaf can hide a fail too. **None of these can become a pass:** each leaves its entries unformed,
  and its family is inconclusive at best (a run that is not registered belongs to no family).
- **The gene unit beyond W6's readouts:** heats, release, recharging, translation, a hold, an export, or a second
  gene.
- **Streams' statistics:** the draws' distribution, only their rule. **Energies:** no energy readout is judged.
  **The trace's recorded pools:** first order beside a co-writer. **The engine's own checks** in `checks` are
  recorded, not judged (only a run the engine itself stopped on one is, §3.4). **The two worlds' reach:** one volume
  pair, one gain, one parameter set, one network, one chain, one transfer per world.
- **The same misread of the law in two places.** The references and the engine share the law text (LAWS.md and the
  sheet). A shared error is seen only through the plants and the references' own checks (SPEC.md §9).
