# FR-7's unit producer at division (D238 item 3), with W against L (D244)

**Proposed, 20 November 2026, by the FR-7 lane. Desk work only; nothing here is built.**

D238 lifts D232's simulation-wide refusal of `population_unit_turnover@1` for division only, and
only with three things:
- this note, fixing how the producer's pools and history split at division;
- a code-blind division reference, registered first;
- worlds without division bitwise unchanged.

Insertion and recycling stay refused until FR-2's ownership design. D244 adds a fourth: compare
two ways to handle operators' owned state at lifecycle events (§4). The operators owner's analysis
is the input (OPERATOR_FEATURES_FR23_24_26_DESIGN.md §4.3 and §4.9).

## 1. What already divides, and what does not

The partition (`isopotential_partition@1`, CELL_DIVISION_S5_DESIGN.md) handles these at the
division event:

| State | Split today | By |
| --- | --- | --- |
| The precursor, a species row of @3 in the cell | yes | the cell's volume fraction f, as every amount increment |
| Surface units N, membrane state's `population_abundance_increment` | yes, through membrane state's accepted writes | the population's patch area fraction a_k |
| The populations' gates | copied (intensive) | none |
| The parent's inner history (transfers, heat) | retired into the partition's record | none |

**Not split today, the producer's own state** (`population_unit_turnover.py`, STATE_AXES):

| Field | Axis | Kind |
| --- | --- | --- |
| `unit_pool_units` | route x pool | extensive: units in transit |
| `unit_consumed_fmol`, `unit_assembled_units` | route | history |
| `unit_inserted_units`, `unit_removed_units` | channel slot | history |
| `unit_turnover_work_pJ`, `unit_turnover_energy_magnitude_pJ` | cell slot | history |

**Two walls stand in the way:**
- **The producer refuses the partition.** `check_writers` refuses any other writer of population
  units, as D232 required.
- **It reads the activity masks as declared** (CONFLICTS_VIEW, D150's static-tissue list), which
  the partition closes.

## 2. The rule at division

1. **Routes follow the slots.** A dividing population's route maps to one route on each
   daughter's population, declared in the producer's routes. A daughter's route is idle while its
   slot is closed, from time 0 until the division, and the parent's is idle after it.
   - The producer reads `active`, `membrane_active` and `channel_active` current (D191) instead of
     as declared. With no closer composed, it receives no view and its programs are unchanged (C1).
2. **The pools divide with the cytoplasm, by f.** Units in transit are intracellular (ER, Golgi,
   carriers), as the precursor is.
   - Daughter 1 takes fl(f M_j), daughter 2 takes M_j - fl(f M_j), and the parent's pools become 0:
     the partition's exact anchor rule, summing to M_j exactly.
   - The alternative is a_k, the destination patch's fraction. It would tie transit to a surface
     the units have not reached. Question 2.
3. **History stays with the slot.** The parent route's consumed, assembled, inserted and removed
   records, and its cell's work, stay on the retired slots. Each daughter route's records start at
   0. Records are not split, so no history moves between carriers.
4. **The ledgers.** The per-route chain ledger (initial units in transit + assembled = pools +
   inserted) gains one signed transfer per route:
   - out of the parent's pools;
   - into each daughter's pools.

   They are booked in a division record that exists only beside the partition (C5), so worlds
   without division keep their fields and programs. Membrane state's population ledger already
   closes with the partition's split of N, and the precursor's with @3's.
5. **Schedules follow the carrier** (D150 §5.2). Each daughter route declares its own k_a and k_r
   from time 0. They apply from its birth, and the removal of every unit (D232) continues on the
   daughters' inherited units at their own k_r.
6. **The template's coupling (@2)** needs the operators owner's step beside the partition. Its
   CONFLICTS_VIEW refuses closers of masks (M1 on M3's pattern), and its operator-target elements
   then name the daughter routes. The template itself, a species, divides by f.
7. **Energy.** Units carry no free energy in the model (F1's declared limit), so the pools' split
   books no work. The precursor's split is the partition's own booking.

## 3. The code-blind reference, registered first

A references agent writes R-div from §2's equations alone: R-chain's chain through a division at
t_d.
- **The setup:** declared f and a_k; the precursor split by f; the pools by f; N by a_k; two
  daughter chains after the division, with their own k_a and k_r.
- **Its plants:**
  - pools split by a_k instead of f;
  - records split instead of kept;
  - the transfer booked twice;
  - the parent's route left active after the division;
  - N split by f.

Registered before any engine output, in the lane's pattern.

## 4. W against L (D244)

**What they are:**
- **W, per owner.** Each owner declares its split, and the partition writes its per-cell state
  through the owner's accepted writes (OPERATOR_COMPOSITION_DESIGN.md §4.4, E4). This is how the
  partition writes membrane state today. FR-26 builds W for site populations at replacement.
- **L, one lifecycle by roles.** Owners declare per-field roles (extensive by f or a_k, intensive,
  structural, history) on hosted axes. One composite lifecycle applies them at both replacement
  and division, as B1 does for the kinds' fields.

**For the producer, the content is the same either way:**
- `unit_pool_units` is extensive by f;
- every record is history;
- C5 carries the division record.

The operators owner's estimate (as the lead relays it) is that FR-7's division needs only C5 of
L's pieces.

| | W | L |
| --- | --- | --- |
| FR-7's division needs | C5; the producer's accepted-write split; the mask reads | C5; the producer's role declarations; the mask reads |
| Owners covered | one at a time: sites (FR-26), the producer, @2's states, D152's routes, each its own writer | every owner that declares roles, at replacement and division |
| Price for the current owners (the operators owner's estimate, relayed) | 6.5-10 agent-days, summed per owner | 7-10.5 agent-days, once |
| Risk | many small writers, each its own first | a new system: roles for operators' fields, hosted axes, C5 and C6 |
| Later owners | each pays again | declare roles only |

**My recommendation for FR-7, whichever is ruled:** declare the producer's split as field roles,
as data, and build C5 first.
- Under W, the partition's writer reads those roles through the accepted writes.
- Under L, the lifecycle reads the same roles.

So the producer's part is not redone if L replaces W. L is a new system, so the choice is the
user's (D244).

## 5. Bitwise, tests, price

- **Bitwise.** These stay bitwise in every world without the partition: C5's fields and the
  division record are absent there, and with no closer the mask reads receive no view.
  - **Checked by:** crossrev, FR's set, and A/B runs of FR-7's judged C2, C5, F3 and F4 worlds.
- **Tests (D224).**
  - Rows in `test_population_unit_turnover.py`: the split rule against R-div's closed form, the
    ledgers across the event, the refusals that stay (insertion, recycling).
  - One compiled division world in tier 2, with its seconds and reason.
- **Price,** in agent-days:

  | Part | Owner | Agent-days |
  | --- | --- | --- |
  | The producer's split, records, ledgers, mask reads and daughter routes | FR lane | 2-3 |
  | C5 | operators owner | 1-1.5 |
  | @2 beside the partition | operators owner | 1-1.5 |
  | R-div | references agent | 1-1.5 |
  | **Total** | | **5-7.5** |

  This is within D238's 5-8. It excludes L itself.

## 6. Questions

1. W or L (the user, D244)?
2. The pools at division: f, recommended (with the cytoplasm), or a_k (with the destination patch)?
3. History: kept on the retired parent slots (recommended), or split?
4. Daughter routes' schedules: declared per daughter route from time 0 (the carrier's, D150 §5.2;
   recommended)?
