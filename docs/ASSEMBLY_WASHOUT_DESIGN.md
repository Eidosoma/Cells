# A pulse and washout for assembly populations (FR-20): design note

**Status: approved by the user, 20 November 2026 (D240): the recommended operator,
`cells.pool_replacement@1`, with the note's answers to Q1–Q5.** It was proposed the same day as desk
work: options, a recommendation, files, tests and a price (D142). It is a general feature
(D144) of `cells.assembly_lineages@2`, built on the population accounting that landed with the
origin-of-life stack (merge d1697656, OL2 milestone 3: `cells.shared_pool@1` and
`cells.serial_transfer@1`).

**The request** (FEATURE_REQUESTS.md FR-20; D237). At a declared time, replace the exterior of an
assembly population with fresh, tracer-free solution:
- keep each assembly, its gate state and its bound tracer, including tracer held at an exposed-site
  control;
- record the material and the energy exchanged;
- the wash bath is finite, so released tracer can re-enter.

**Engine models it would run:** `cells.assembly_lineages@2` in population mode, with
`cells.shared_pool@1` and a new operator (§3).

## 1. What is kept, replaced and recorded, in the engine's terms

A population world (`execution.mode: population`) holds one shared pool and K vesicle slots. Each
slot holds its vesicle's membrane and lumen places; the pool holds the exterior's places, each
`finite` (a count in the state) or `held` (a declared concentration, a reservoir).

- **Kept** at a replacement: every slot's places, bitwise, with its key, its sub-lineage counter
  and its life. Its gate state and its bound tracer are slot places, so they are kept with it.
- **Replaced:** the pool's finite places, by a declared composition.
- **Unchanged:** the held places, c_ext, and the pool's volume (a world constant today).
- **Recorded:**
  - the material: the old pool's count per finite place, removed to the sink, and the fresh
    pool's count per place, supplied by the replacement's source;
  - the energy: the sink takes F(old pool), and the replacement's schedule-work column takes
    F(fresh pool). Then F(after) − F(before) = work − sink, and the ledger closes.
- **The bath is finite:** after a tracer-free replacement the pool's tracer count is 0 and rises
  as tracer leaves the vesicles; the reverse steps then let it re-enter. This holds for a finite
  pool place, not for a held one (§4, Q3).

**What expresses a gate, bound tracer and an exposed site today.** The requester's model is not
assumed. A world with a geometry, as every population world is, can declare the following; both
were checked by parsing an osmotic population world with them (20 November):
- **a gate:** a membrane species in two forms, joined by a membrane-locus step
  (`count_on_m`), with a rate factor on the common membrane state (`cells.transition_state_factor@1`)
  modulating a permeation or a join;
- **bound tracer:** a complex formed by a membrane-locus step, after the tracer's join from the
  pool (`cells.phase_exchange@1`);
- **an exposed site:** only by that same route. A direct step from a pool species to a membrane
  site is an interfacial reaction, which §0.2c rule 3 refuses in a world with a geometry until a
  geometric encounter is declared for it. A site count independent of the membrane's inventory is
  FR-21's ground (D237), not this note's.

Under `lumen_volume: osmotic` every membrane and lumen species has a pool place (§0.2c rule 8), so
the gate's forms, the site and the complex have pool places too, and a replacement's `pool` lists
them.

Whichever route a world declares, a replacement keeps what the slots hold and acts only on the pool.
Nothing in it is specific to a bilayer, so a prescribed shell from FR-21 needs no change here.

## 2. What exists: a serial transfer that keeps every assembly (option 0)

`cells.serial_transfer@1` with `K_keep` at or above the number of slots already does most of FR-20
today, with no code. Clause by clause:

| FR-20 clause | `kind: transfer`, `K_keep` ≥ K |
| --- | --- |
| Every assembly kept, with its gate state and bound tracer | Yes: the K_keep smallest of the uniforms keep every living slot |
| The exterior replaced by a declared composition | Yes: `fresh_pool`, one count per finite pool place |
| Held places and c_ext unchanged; the fresh solutes at most c_ext | Yes (§0.2c rule 6's refusal) |
| A finite bath, so released tracer re-enters | Yes, for a finite tracer place at the pool's own volume |
| The energy exchanged | Yes: the sink's F and the schedule's work column, per transfer in run.json |
| The material exchanged, per species | **No:** only F is booked. A row is saved after the transfer, but the pool just before it is not |
| No sampling | **No:** it draws one uniform per living assembly on its own stream (domain 6). The draws touch no other stream, but they are recorded as a sample that selects nothing |
| Its name and records | **No:** it is a transfer, with `transfer` events and a source of class substrate |
| Material edges in relations@2 | **No:** population worlds have no pool node or material edges yet (planned in Task 2) |

A world can test kinetics around a wash this way now. The gaps are the per-species record, the
meaning of the draws, and the relations rows.

## 3. Options

| Option | What | For | Against |
| --- | --- | --- | --- |
| **O0** | Option 0 above, as it is | No code | No per-species record; a sample that selects nothing; named a transfer |
| **O1** | A new operator, `cells.pool_replacement@1` (schedule `kind: replacement`), which shares the pool step with the transfer | No draws; its own name, records and source; transfer worlds bitwise unchanged | A second operator to register and test |
| O2 | `cells.serial_transfer@1` with a `K_keep: all` token that skips the draw | Fewer files | Two meanings under one ID. Transfer's draw-even-when-all-kept rule is ruled (§0.2d item 6) |
| O3 | A held place's concentration changed at a declared time | Washes a held species | A held place is an infinite bath, so released tracer could never accumulate and re-enter. It contradicts the request, and its booking needs a ruling (Q3) |

**Recommended: O1.** Its declaration mirrors the transfer's, without the sample:
`{index, kind: replacement, times_s, pool}`, with `pool` giving one count per finite pool place,
in place order.
- **At each time:** a host stop, as the transfer is. It draws nothing and keeps every slot, and
  the pool's finite places take `pool`.
- **The shared step:** the transfer's pool replacement and its booking move into one function that
  both operators call. Every transfer world's arrays stay bitwise.
- **Same-time stops:** in schedule-index order, with every other schedule (§0.2d item 10.1).
- **The schedule's stream** (domain 6) is reserved by its index and never drawn.
- **A pulse** is a replacement whose `pool` holds tracer, or the founder's pool. A washout is a
  replacement whose `pool` holds none (Q2).
- **Records:**
  - run.json's population block lists each replacement: its time, schedule, the removed and
    supplied counts per place, the sink's F and its work;
  - its rows' `row_kind` gains `replacement`;
  - its schedule-work column is paid by `source:replacement/<index>`;
  - the diagnostic record lists the replacement events.
- **relations@2:**
  - one event per replacement, `event:replacement/<n>`, kind `replacement`, by
    `cells.pool_replacement@1`;
  - a source `source:replacement/<index>` (kind `schedule`, class `substrate`), the payer of its
    column;
  - a pool node, `node:pool` (kind `node`);
  - `removes_to` edges from `node:pool` to `sink:discard`, and `supplies` edges from the source to
    `node:pool`, one per species with a count, each weighed by that count at the event (mode
    `event`).

  The pool node and these edges are specified once, here, for the material edges of OL2's
  remaining work as well: there, `moves_to` edges run between the pool and each slot, weighed by
  one-way join and leave records.

**Two rules** (the lead's conditions of 20 November):
- **The fresh pool declares every finite pool species.** `pool` has one count per finite pool
  place, so a species left out changes its length and is refused. Nothing is kept silently.
- **A replacement never shares its time with another stop**, since cells.relations has no order
  between same-time events yet. It is refused at three points:
  - **at parse,** a replacement time equal to a declared time of a shear, a transfer or another
    replacement;
  - **at the run's start,** a Poisson shear time drawn equal to a replacement time, on the grouped
    plan before the first event;
  - **at the stop,** a lysis whose event committed at the replacement's own time. An event exactly
    at a stop's time commits before the stop.

**Q3 as built** is broader than its approved words, "a held tracer concentration is refused". The
engine cannot tell which species is the tracer, so a replacement refuses every held pool species
that also has a membrane or lumen place, a held lipid supply included. Such a world declares the
species finite, with its count in `pool`.

**Non-claims and status:**
- tracer captured on an exposed-site control is not claimed until FR-21;
- FR-20 lands as development, not as a judged reading, unless the user later asks for one.

## 4. Questions for the lead

1. **Q1, the bath's volume.** The pool's volume is a world constant, so a replacement keeps it.
   If a wash bath's volume must differ from the medium's, the pool's volume becomes scheduled
   state. Every pool activity, F and the c_ext check then read it.
   - **Recommended:** the same volume now. A declared bath volume is priced separately.
2. **Q2, the pulse.**
   - **(a)** A replacement whose fresh pool holds tracer, or tracer in the founder's pool.
   - **(b)** An addition: counts added to the pool with nothing removed, which is a dose, a source
     of kind `dose`.
   - **Recommended:** (a), which O1 covers. (b) is a third operator, priced separately.
3. **Q3, a held tracer.** A world whose tracer is a held place cannot be washed by O1, since held
   places are unchanged.
   - **Recommended:** refuse a replacement whose world holds the tracer, and say so in the
     refusal. A held-concentration schedule (O3) waits for a ruling on how a chemostat's change
     is booked.
4. **Q4, the osmotic side.**
   - **Recommended:** the transfer's refusal applies as it is: the fresh solutes may not exceed
     c_ext.
   - The run's c_ext drift report then covers the replaced pool, with no new rule.
5. **Q5, the name.** `cells.pool_replacement@1`, with schedule kind `replacement`, after its
   mechanism (D144). "Washout" names an experiment's use of it.

## 5. FR-22's needs from the wash

FR-22's rung P cuts a run only at an exact event count, so a cut around a wash sits at the last event
before the replacement or at the first event after it, never at the stop's own time. A resumed run
whose first row sat at the replacement's time would need an order between same-time events in
relations (RELATIONSHIPS_DESIGN, GARD's case 1), which is not built. The checkpoint carries the
replacement's host state: the stops applied, the replacements' numbering and the schedule columns
in the host's bookings.

## 6. Files

- **New:** `src/cells/models/assembly_lineages_v2/replacement.py` holds the operator, its parse,
  its contract and its registration (`cells.assembly_operator@1`).
- **Changed:**
  - `transfer.py`: the shared pool step;
  - `division.py`: `Schedule` gains the kind and its `pool`, and `parse_schedules` routes it;
  - `population.py`: the stop applies it, books it and records the row;
  - `records.py`: the relations rows above;
  - `diagnostic.py`: the replacement events;
  - `registry/model_table.py`: one operator home;
  - the registration test's operator rows;
  - `validation/assembly_lineages_v2/FORMAT_OL2.md`: one section.
- **Not changed:** @1's files, the single-lineage runner and every world without a replacement.
  The invariance gate (`scripts/assembly_lineages_invariance.sh`) shows @1's and OL1's probe sets
  unchanged.

## 7. Tests

A new file, `tests/unit/test_assembly_lineages_v2_replacement.py`, since the population file runs at
69–81 s against tier 2's 90 s cap. It uses one compiled population program and one three-phase
world, which serves W1–W4 in one run:
- two slots;
- a two-state gate whose forms catalyse the tracer's permeation;
- a site that binds tracer in the membrane;
- a tracer-free founder pool, then a pulse (a replacement whose pool holds tracer), then a wash (a
  tracer-free replacement), as two schedules.

The file states its seconds and its reason when it lands (D224). Each claim has a planted error it
must catch (D187):
- **W1 kept and replaced.** At each replacement, every slot's places, keys and lives, the gate's
  forms and the bound tracer included, equal those of the same world stopped at the last event
  before it (FR-22's stop), bitwise. The pool's finite places equal `pool`. Planted: a replacement
  that also empties the lumen.
- **W2 the books close.** The sink's increment and the column's increment equal F(old pool) and
  F(fresh pool), computed apart on the host, and the residual stays within its bound at every row.
  Planted: the fresh pool left unbooked, which opens the ledger by F(fresh pool).
- **W3 the material record.** The removed counts equal the pool of the stopped run, and the
  supplied counts equal the pool after the replacement. Planted: removed counts taken after the
  replacement.
- **W4 the rates follow the replaced pool, and released tracer re-enters.**
  - The first event after each replacement is the host's pick at the replaced pool, with the
    device's own uniforms.
  - After the wash, no tracer entry precedes a release, and one follows.
  - Planted: stale rates (the refresh returning its input after the first call), which pick other
    events.
- **W5 the replacement draws nothing.** The schedule draws are the other schedules' alone. Planted:
  a replacement drawing one uniform per living assembly, as a transfer would, which the draw record
  shows. That transfer worlds are unchanged bitwise is landing evidence, not a unit claim: the
  fresh population controls are compared with main's arrays and records.
- **W6 refusals,** host-only rows:
  - a replacement without a population;
  - a `pool` of the wrong length, as a species left out gives;
  - solutes above c_ext;
  - a held pool species with a membrane or lumen place (Q3 as built);
  - a replacement at the declared time of a shear, a transfer or another replacement.
- **Around a wash** (FR-22, rows in the same file, reusing its program and its stopped run): a cut
  at the last event before each replacement and at the first after it, resumed and compared with
  the uninterrupted run, bitwise.
- **The round trip:** `parse_spec(spec.to_dict())` keeps the fingerprint of a world with
  replacements, which a checkpoint's admission relies on.

## 8. Price

| Part | Agent-days |
| --- | --- |
| O1: the operator, its parse, the shared step and the population stop | 0.5–0.75 |
| Records, the diagnostic record and relations@2's rows (pool node, edges, source) | 0.5–0.75 |
| Tests W1–W6, FORMAT_OL2.md, the registration rows | 0.5–0.75 |
| Invariance gate, tier rows, review | 0.25 |
| **O1 in all** | **1.75–2.5** |
| Q1's declared bath volume, if chosen | +1–1.5 |
| Q2's addition (a dose operator), if chosen | +0.5 |
| Q3's held-concentration schedule, after a ruling | +1 |

O0 costs nothing and serves kinetics now, as §2 lists.
