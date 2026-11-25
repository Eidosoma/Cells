# Criteria, classes, bands, power, faults, plants and verdicts

**Fixed on 25 November 2026, before any run of the registered campaign.** Its author had seen no re-expressed run. Others had (the protocol's §11 says who and what), and §8 says what the verdict does with that. Every number here is a formula's constant. None comes from a run of either side.
- "The run" is a run of the candidate, read from its table (`TABLE.md`). "The capture" is the legacy run's array (`SPEC.md` §7).
- The judged set is READOUTS §3's and §4's. The run names are `inputs.json`'s.
- **Three kinds of tolerance, never mixed** (D370): a **rounding** bound, a **closure** bound and a **truncation** estimate. Each has its own term in a band, and a readout of
  one kind is never judged by another kind's bound.
- This file holds for both parts. Where a number is a world's, `inputs.json` (Part 1) or `inputs_part2.json` (Part 2) gives it.

## 1. Symbols

- ε = 2⁻⁵². s is a readout's scale (`inputs.json` `scales`; `SPEC.md` §5).
- S_c = end_s/h₃, the candidate's steps to the end at its finest judged step. S_l = end_s/(the captured h/4). **Both from the registered grids,** never from a table.
- p is the declared order of the candidate: 4 for an RK4 family, 2 for an IMEX family. Legacy's is 4.
- e_round(S) = 8 ε (S + 1) s. e_close = 4 × 10⁻¹² s. (`SPEC.md` §6 derives both.)
- **An entry** is one readout of one family, over all of its entities and compared times, or one equality, identity or completion.

## 2. Rungs and families

A family is three runs of one world at steps h₁ > h₂ > h₃, each half the last. An S entry needs all three, and the retry adds one more halving (§7).

## 3. The classes

| Class | What | Judged by |
| --- | --- | --- |
| **E** | Equal as numbers: integers equal, doubles equal as doubles, and +0.0 equals −0.0 | §4.1 |
| **R** | An assembly pool's exposure, within a rounding bound | §4.2 |
| **S** | Stepped, against the captures: three runs, extrapolated, with an order rule | §4.3 |
| **D** | Completes, with the engine's own ledger rule held at every accepted step | §4.4 |
| **P** | Power: whether the entry could have failed | §4.5, judged first |

No ruling assigns a class, and none changes after a run.

## 4. The criteria

### 4.1 E, equal

Every value equals the named value.
- **The pool's 19 arrays** of every pool run equal the captured ones (READOUTS §4), over all its worlds.
- **The event path** of every world and cell equals `reference_paths.json`'s, event by event: the same number, the same times, the same availabilities.
- **The switch list and the channel schedule.** Both the `switch_list` that an ionic run of `cell` or `base` records and the schedule its definition was parsed with (`controls.channel`), with the entries that repeat the value before them removed, equal the path's changes of that
  world and that cell. Their times are the path's doubles. Each is an entry of its own.
- **The seeds:** the echoed `pools.<cell>.seed` of a pool run, and the `pool_seeds` that an ionic run of `cell` or `base` records, equal `inputs.json`'s for their seed index.
- **Structural zeros:** `n_out_x` of `integrated`, every row.
- **Restarts** (support runs), over every class S readout and the potentials, at every compared time after the restart's time, and at that time if the resumed run holds a row there:
  equal to the uninterrupted run of the same step. The pool restart: the 19 arrays at 0.02 s, and the path after the restart's time.
- **An integer array is compared as integers, a double as doubles.** A JSON 4 equals 4.0, and a value printed in two ways that read to one double is equal.

### 4.2 R, rounded

|value − expected| ≤ the bound READOUTS §5 gives. The exposure uses the run's own event path, over every world and cell of the pool run.

### 4.3 S, stepped

For a family and an entry, over its compared times and entities, with Y₁, Y₂, Y₃ the runs at h₁, h₂, h₃ and L₁, L₂, L₃ the captures at h, h/2, h/4:

    d₂ = max |Y₂ − Y₁|,   d₁ = max |Y₃ − Y₂|,   U_c = max( d₁/(2^p − 1),  d₂/(2^p (2^p − 1)) ),   Y* = Y₃ + (Y₃ − Y₂)/(2^p − 1)

    d₂ˡ = max |L₂ − L₁|,  d₁ˡ = max |L₃ − L₂|,  U_l = max( d₁ˡ/15,  d₂ˡ/240 ),                 L* = L₃ + (L₃ − L₂)/15

    β = 2 (U_l + U_c) + e_round(S_c) + e_round(S_l) + e_close

**Pass:** max |Y* − L*| ≤ β.

- **The band is §8's of the port plan,** with two changes, each before any run:
  - **the floor of 64 ulp × max|X| is replaced** by e_round and e_close. Legacy's own runs refute that floor: between its own h/2 and h/4, arrays at rounding differ by up to about 3000 ulp of their
    largest entry. The two terms come from a count and from two declared acceptance constants (`SPEC.md` §6), and they are kept apart from the truncation term;
  - the error estimates take the **larger of the two step-halving pairs** (D271, D334).
- Every compared time needs one row in each run the entry needs (within 10⁻¹² s). Where one is missing, or there are two, the entry is not formed (§5), and no time is dropped from it.

**The order rule.** Let θ = 10 × 8 ε (S_c + 1) s.

| d₁, d₂ | What the entry is | What decides |
| --- | --- | --- |
| both ≤ θ | **unresolved** | β alone. The order is reported |
| exactly one ≤ θ | **mixed** | at most β: **inconclusive by order**. Above β: it fails |
| both > θ, and q = log₂(d₂/d₁) lies in [p − ½, 4½] | **resolved** | β alone |
| both > θ, and q outside that window | **resolved outside its window** | **inconclusive by order, whatever its error.** Never a pass |

- **Why 4½.** The low edge is D271's (p less its half). The high edge comes from the schemes. For RK4 it is p plus the half. A symmetric composition of order 2 has an error expansion in even powers,
  so the only higher order that can appear is 4, and FR-25's and FR-38's orders of 3.7 to 3.9 are of this kind. The cap of 3½ made them inconclusive, and here a looser cap costs
  nothing: an estimate that is too large can only widen β, and power (§4.5) is judged first and makes a wide band untested.
- **The legacy side** is classed by the same rule with p = 4, S_l and its own differences (`legacy_part1.json`). Every captured entry of this folder is unresolved. A legacy entry resolved outside [3½, 4½], or with d₁ˡ > θ ≥ d₂ˡ, is a **C0 fault**, found before any run and settled by a
  further legacy capture, never by a judgement.

### 4.4 D, completes: conservation is the engine's own rule

A judged run completes, and so does every accepted row's check. The engine checks its own ledgers (material, charge, energy and the rest it declares) at **every accepted step**, each against its declared
allowance, and stops at the first that fails. That rule is the criterion. No absolute number of legacy's is used, since legacy's 10⁻⁹ pJ belongs to a fourth-order integrator and is not established for an order-2 one.
- **A run that the engine's own check stops fails** (as FR-54's protocol has it, and for its reason: the check's residual above its allowance is the evidence). A refusal at parse, or one that a harness made, is a refusal (§5).
- **The checks were on.** The table's `checks` (recorded) name each ledger the engine checks and its largest residual. The checker confirms from the run's own record that the engine checked every accepted row and that no check was switched off. A run whose record cannot show it
  is refused, its readouts are judged, and a fail stands.
- **Legacy's own ledgers** are its side's evidence: every captured job ended with its own checks passed.

### 4.5 P, power, judged first (D366)

**Stage 1 of the judgement.** From the runs' own rows and the captures' own refinement, and before any difference between a run and a capture is formed, the judge forms every entry's U_c and β, and its class under §4.3's table. It
writes `power.json` and the lead records its sha256. Stage 2 forms the differences.

- **The planted distance D(y)** of an entry is the size of the effect that a 1 % change in one rate constant has on it, on the legacy side alone. `margins.json` gives a ratio ρ(y) (a planted change's
  effect over the readout's own magnitude, from planted legacy runs or by arithmetic; `PLANTS.md`), and D(y) = ρ(y) × max |L₃| of that entry's family. No run enters it.
- **An entry is tested** when **β ≤ D(y)/10**, with the ratio that `margins.json` gives its readout (a home's is its own plant's, and any other readout's is the plant's that moves it most). Otherwise it is **not tested:** its
  comparison is reported, a comparison above β still fails, and one within β is neither a pass nor counted.
- **A mechanism is tested** when at least one of its home entries (`PLANTS.md` §2) is tested. **A consumer with an untested mechanism is at best inconclusive.** A home entry that is
  not tested is owed the retry (§7) where 2 U_c is the larger part of β, since a finer step lowers U_c. Where it is not, the retry cannot help and the entry stays not tested.
- **An observable that a mechanism cannot reach** in 20 ms is declared so in `PLANTS.md`, with the number, before any run. It is "not tested" in advance, and is not made a
  home. A plant of such a mechanism is enlarged or replaced by a dated line before the tag, never after.
- The R and E entries have no power entry. Their own plants are §6's. Class D has none.

## 5. Faults and refusals

**Nothing hides a fail.** Every entry that can be formed is judged. If any judged entry fails, its run fails, whatever else of that run or of its support is refused, stopped or missing.

| Fault | What follows |
| --- | --- |
| The echo (`inputs`, but the items that `SPEC.md` §2.4 gives to class E; `strings`, `world`, `seed_index`, `world_id`, `step_s`) departs from the registered run (`SPEC.md` §2.4; the strings note exactly) | The run is **refused, and nothing of it is judged.** It is not the registered one |
| Provenance: `source` incomplete, `checkout_dirty` true, a missing `record_sha256` or snapshot, an `engine_revision` that is not the strings note's, a `snapshot_patch_sha256` other than an empty file's, a non-null `host_patch`, a `t` that does not strictly increase, `steps` outside its range (`TABLE.md` §3), a status that disagrees with `refusal`, a shared `record_sha256` | The run is **refused,** its readouts are judged and a fail stands |
| A judged leaf missing, mistyped or non-finite, or a registered time with no row, or with two | That **entry is not formed**. The rest of the run is judged |
| A recorded-only leaf missing, mistyped or non-finite | Flagged to the checker |
| Two runs of one family whose class S series and potentials are **bit-identical at every compared time** | Both are **refused** (a copy). Their readouts are judged |
| A refused entry of kind `domain`, `definition` or `harness` | **Refused** |
| A refused entry of kind `check` | A **stop:** it fails if the run is judged (§4.4) |
| A run in `missing`, or in neither list, across all of a consumer's tables | **Refused** |
| A run name that `inputs.json` does not list, and the retry's rule does not register | Ignored, recorded and flagged |
| A duplicated key anywhere in a file | The file is refused, and every run of it |

- **A refused run cannot pass.** With no failing entry its consumer is at best inconclusive, and so is every S entry that needs it. The entry cannot be formed and is neither passed nor failed.
- **A refused or missing support run** leaves its consumer at best inconclusive. It does not refuse the run it supports.
- **The one place a fail can go unseen** is a departing echo. It leaves nothing of that run judged, and its family's S entries are not formed. It is kept: such a run is not the registered
  world. The checker sees the departure and its cause.
- **The owner of an entry.** An S entry belongs to the run at h₃. A D entry belongs to its own run, and the exposure to its pool run. A restart's E entry belongs to the judged run it resumes, never to the support run. The exposure, the path and the pool's arrays belong to the pool run. The switch list's, the channel schedule's and the recorded seeds' E entries belong to the ionic run that records them, and a pool run's seeds to the pool run.
- **Nothing passes empty.** A consumer's S entries that were formed are counted. If they are fewer than READOUTS §3 lists, the consumer is at best inconclusive. A plant whose named entry is not formed is unscorable, never caught.

**C0, before any table is read:** the judge reads `inputs.json`, `legacy_part1.json`, `reference_paths.json`, `margins.json` and the manifest, and the captures they name. It checks every sha256, every key, the scales
against the rule, the legacy side's classes against the rule (§4.3), and that every mechanism has a home entry with a ratio. A fault is named and refused. The order of reading is the lead's: the
tables' hashes are recorded, then C0, then stage 1, then the tables are opened for stage 2.

## 6. The plants

`PLANTS.md` lists them, with their homes and their margins. Four kinds, by what they act on:

| Kind | What it is | Scored |
| --- | --- | --- |
| **Power plant** (PW) | A planted legacy run with one rate constant × 1.01, or a stated kinetic constant. It gives ρ(y) | Before any run. No candidate run |
| **Structural plant** (ST) | A planted legacy run with one wrong factor (a factor missing, a sign, a valence, an exponent, a wrong owner) | The **honest** candidate's Y* against the planted legacy run P (at the captured finest step in Part 1, at 12.5 µs in Part 2), over the entry's compared times, at every named entry |
| **Engine plant** (EP) | A run of the candidate with one declared change | Its Y₃ (finest step, not extrapolated) against L*, with the **honest** family's β, at every named entry |
| **Judge's plant** (JP) | An altered copy of an honest table (a sign, a lump, a copied run, a moved value) | Caught when the judge's rules score it as the text says |

- **A plant is scored with the honest family's β,** never its own. The **registered distance** of a structural or engine plant at a named entry is the legacy side's (`margins.json`).
  - Where the registered distance is at most 2 β, the comparison cannot see that plant there, and the plant is **unscorable**. It is never called caught or not caught, and it leaves its consumer at best inconclusive.
  - Where it is above 2 β, the plant is caught when the candidate and the planted capture differ by more than β at that entry. A candidate whose honest S entry passes always differs by more than β, so a plant not caught says that the candidate resembles the plant, and its consumer **fails**.
  - A plant that reads an honest run that is refused, or whose named entry is not formed, is **unscorable**. An engine plant whose own declared change is not what `PLANTS.md` §5 says (EP2's switch list and schedule are class E against the **swapped** paths) is unscorable too.
- **A plant is caught** when every entry it names is caught. One unscorable entry makes it unscorable, and any not caught makes it not caught.
- **A power plant decides no verdict.**
- **Margins are stated before any run** from the legacy side alone, against the band at U_c = 0. The sizing rule is 10 at the best entry. Below it, a plant is enlarged or replaced by a dated line before the tag, stated, and **no band, class or window moves because of a margin**.

## 7. The retry

**Once, for the entries that are owed it:** an entry inconclusive by order, or a home entry not tested whose 2 U_c is the larger part of β. The judge's first pass writes `retry_owed.json` (`TABLE.md` §6). The lead records its sha256, and the builders run exactly those.
- **The run:** one more halving, h₃/2, of every family that holds an owed entry, named `<family> h=<step> retry`, with its own support runs only if owed. The triple becomes (h₂, h₃, h₃/2), and S_c is its finest.
- **Entries that passed or failed keep their score.** An owed entry is judged again by §4.3 and §4.5 on the new triple. The retry run's own D entry is judged, and a fail there counts.
- **An entry still inconclusive, or still not tested, stays so.** A wrong coarse run that the retry drops is forgiven (the protocol's §9 says so), and the verdict states the steps that its pass covers.
- A refused or stopped run takes no retry. No tolerance, window or class changes.
- **A retry run that is present and not owed** is recorded, flagged and not judged. An owed retry run that is missing is a missing run.

## 8. Verdicts

- **A run** fails if any entry it owns fails, or if D fails. Otherwise it is inconclusive if any entry it owns is inconclusive, not formed or refused, or if it is refused. Otherwise it passes.
- **A consumer:**
  - **fails** if any of its judged runs fails, or a structural or engine plant of it is not caught;
  - otherwise is **inconclusive** if any of its judged entries is inconclusive or not formed, any judged or support run is refused, missing or stopped, a mechanism is untested, or a plant is unscorable;
  - otherwise **passes.**
- **An entry not tested (§4.5)** that is not a home entry counts for neither side. It is listed.
- **Part 1 passes** when its four consumers pass. A part decides nothing about another part.
- **`base` is reported in two sets.** A design author ran world IDs 0 and 1 in composed form against legacy, at the configuration's own pool seeds, before this folder's tag (the protocol's §11). Those seeds (20260925 for cell 0's stream and 20260926 for cell 1's) are the captured seed index 0's. So `base s0 w0` and `base s0 w1` are **not blind**, and the other 30 families are.
  - **The verdict of `base` is the worse of its two sets' verdicts,** each formed by this section from its own families. A fail in either fails it, and an inconclusive in either leaves it inconclusive.
  - **The 30 must pass by themselves,** with every mechanism tested by a home entry of one of them. The two add nothing to a pass.
  - **The pool run `base s0 pool`** holds both worlds among its 8. Its entries are marked in the record and are judged as any other.
  - The record gives both sets' verdicts side by side, with their counts. No plant of `base` is scored on the two (ST6, ST10 and EP2 use world 2).
  - **`jupiter_baseline` is the same ionic world as `base`,** value for value, with the channels open throughout. What a prototype showed on `base` bears on it, and the record says so beside its verdict. No entry of `jupiter` was run.
- **An inconclusive verdict is not a fail.** The retry is the only answer to it.
- **The record** lists, for every entry: consumer, family, run, readout, class, statistic, band, their ratio, d₁, d₂, q, the order's class, U_c, the planted distance and whether it is tested, and the verdict. Then every refusal, stop and flag with its cause, every plant's margin and score, and the count of judged entries
  per consumer beside the count READOUTS §3 lists.

## 9. What a miss means, stated before any run

- **A miss in class E on the pool** says the live pool's event path, seed or stream is not the captured one. It is a defect of the re-expression (a stream renamed, an order changed) or of the capture's machine. It is settled by an independent replay on the snapshot's pool, and no tolerance can settle it.
- **A miss in class R** (an exposure) says the event path's intervals disagree with the captured exposure, and so does one in class E on the path: a defect of the pool, the path or the exporter.
- **A stop** (class D) says the engine's own check found a ledger above its allowance. It is followed by a labelled, non-blind diagnosis by someone other than the author, the builders, the judge and the checker.
- **A miss in class S with the others passing** says that the candidate's equations, or its declared constants, are not the captured ones, or that a rounding or closure bound is too tight. The plants say which readout a mechanism moves.
  - The largest ratio and the entities it lies at go to a labelled, non-blind diagnosis, by someone other than the author, the builders, the judge and the checker. It names the equation or the bound.
  - **A bound that the count left out is corrected only at the rehearsal** (§10), never after a registered run. A miss that a registered run shows is recorded as a miss.
- **A reported identity that a run misses** (READOUTS §5) while its own checks pass says that the exporter's rows and the engine's ledgers disagree. It is a question for the checker, and decides nothing by itself.
- **A failed consumer stays in legacy.** Its capture, its pre-cleanup tag and its snapshot hold it. The cleanup does not remove it until a new registration passes, and the user decides what happens to the rest.
- A miss is never dropped, rescaled or re-run at another step. Any new run is a new registration, with this one's record beside it.

## 10. The rehearsal, and correcting a bound

**The rehearsal** is the judge's whole scoring path, run on the invented worlds of `inputs_rehearsal.json` through the registered exporter, with the frozen legacy snapshot's runs on the same definitions as the reference side. It comes after
the criteria tags and the judge's tag, and before the registration tag. It must: pass every honest entry, catch every plant that can be formed, take every refusal and stop as this file says, and flag every fault of §5 (planted
copies of the table included).
- **No final fail can rest on a bound that the rehearsal has not met.** The counts of `SPEC.md` §6 are derived without the engine's arithmetic. A bound that an honest invented run misses is a defect (of the exporter, the judge, the engine or the reference side), found and fixed, or a bound to correct as below.
- **A route to correct a bound.** Before the registration tag, and only when an honest invented run at the rehearsal misses it, a count or a constant is corrected by a dated amendment that re-derives it from a stated reason (a path of operations the count left out), shows the derivation, is disclosed with the
  run that showed it, and re-tags this folder and the judge. It never fits a run, never sets a bound to an observed value times a margin, and changes no class and no window. After a registered run no bound moves for any reason.
- A rehearsal is evidence for the harness and the bounds. It is none for or against a consumer.
