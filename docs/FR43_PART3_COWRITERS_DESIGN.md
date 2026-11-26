# FR-43 part 3: sharing a moved row with local reactions and the gene unit (design)

**Status: decided 25 November 2026; built 26 November 2026 on branch `fr43-cowriters-build` (from main c52d0998,
after the legacy cleanup and the ID move), as §10 says.** It is the open item of FR-43 part 3. D328 keeps part 3 open
"until D152 reactions and the gene unit can co-write a moved row". The IDs below are the moved ones (D345); §9's
evidence keeps the spellings it was written in.

**The decisions (25 November 2026).**
- **The user accepted all four recommendations of §7:** question 1 (a), split writers; question 2 (a), one judged run
  over W5, W6 and W5′ with code-blind references; question 3 (a), part 3 closes at this landing, and the population at
  changing volume is logged as its own request; question 4 (a), the declared general rule.
- **The lead ruled L1 to L4** (§7): L1 (a), since the search found no such pair; L2 as listed; L3 as stated; L4 (a).
- **The build waits for the legacy cleanup:** the user put every other build on hold. The spec and the references may
  start now, since they name no engine ID. They are on branch `fr43-part3-spec`.

**Engine models:** `cells.model.resolved_pump_composite@1` over `cells.model.resolved_pump_tissue@3`, with
`cells.operator.integer_unit_population@1` beside `cells.operator.local_species_reactions@1` (D152, "the reactions"),
`cells.operator.templated_polymerisation@1` ("the gene unit"), `cells.operator.scheduled_species_turnover@1`,
`cells.operator.scheduled_species_exchange@1` and `cells.operator.site_occupancy@1`.

**S** marks this note's own reading or derivation. **Measured** names a probe of §9. The probes are development, on
the host, with one small compiled world per pair. They are evidence for no claim of the engine.

## In short

- **What is refused.** A reaction that writes a row the integer population moves, and the gene unit on any species
  that both operators list. Checks at the definition do it (§1). Nothing stands behind them: with them lifted in
  process, both pairs parse in either declared order, and both run with every host check passing (measured).
- **Recommendation.** Admit both as turnover and exchange are: separate split parts in declared order. One general
  rule carries it: **a transfer may share a row with any declared writer, unless a writer claims that row alone**
  (§3.2). It lives in the species registry, fed by three optional declarations of the operator contract. No compiled
  program changes, so every existing world keeps its own.
- **Exact:** each writer's material and energy books, positive amounts, and the integer ledger. **Second order in
  the step,** beside the reactions and beside the gene unit: the event times (measured orders 1.8 to 2.2) and the
  amounts (1.5 to 2.2, noisier). Where no event rate depends on the co-writer, directly or through the transfer, the
  event times stay exact at every step (measured with constant rates: 4e-13 s).
- **A correction to the question as put.** In this operator an event moves no material. It changes the units'
  states. Material moves between events, through the active units. So no event can empty a pool (§2.1).
- **Five findings beside the question** (§1.3): the two refusals have no test; `cells.operator.site_occupancy@1` writes
  a moved row today and nothing checks it; the definition's bound on event rates does not count what a co-writer makes;
  exchange beside the population is admitted and was never run; and the pools recorded at an event are first order
  beside any co-writer.
- **Price (S):** 2.5 to 3.5 agent-days for the build, and 1.25 to 1.75 for one judged comparison. One full gate and
  one no-src stack.

## 0. The words used

- **A row** is one species' amount at one place: a cell, or a finite outside node.
- **The population** is `cells.operator.integer_unit_population@1`. A **site** is a small cluster of its units in one
  membrane patch, for example two free subunits that can form one active unit.
- **An event** changes a site's unit states at a random time. Its **propensity** is its rate, which may read one
  row's concentration: a **read row**. The site's **clock** adds up the propensities until an event fires.
- **A transfer** moves a species through the active units between the patch's cell and its outside node,
  continuously and downhill. Its two rows are **moved rows**. A row may be read, moved, both or neither.
- **A writer** of a row is an operator whose half-steps change it. Two writers of one row are **co-writers**.
- **A half-step.** A step of length dt runs each operator over dt/2 in declared order, then the tissue's own step,
  then each operator over dt/2 in reverse. That symmetric order is Strang's splitting. An error of order p falls by
  about 2^p when dt is halved.
- **A conversion** changes how much of a species there is at a place (turnover, a reaction, the gene unit). **A
  transfer** changes only where it is (exchange, the population).
- **@3** is the composite's inner model, `cells.model.resolved_pump_tissue@3`. It owns every row.
- **SSPRK(3,3)** is the third-order explicit method of the reactions' and the gene unit's half-steps. Its **stage
  condition** refuses a step whose rates would drain an amount.
- **The gene unit's one-sided domain:** its laws hold only where each route runs well forward. Elsewhere its step is
  refused.
- **R5** is the unit producer's bound on the units its population can reach, from every supplier's largest rate.
- **crossrev** compares compiled programs across two revisions, and **G1** the saved results of 113 worlds. **D148**
  is the rule that an existing world's program may not move.

## 1. What is refused today

### 1.1 The refusals, in the engine's words

Measured (`refusals.json`): parses of small worlds, the source untouched. S is the species the population moves
between `cell_0` and `ecs_0`.

| World | Today | Where, and the message |
| --- | --- | --- |
| A reaction that writes S in the cell (a sink or a source), or at the node | Refused, in either declared order | `integer_unit_population.py:1104–1113`: "a cells.operator.local_species_reactions@1 reaction writes S at cell_0, a row this operator moves: one local-kinetics writer per reacting row (D152)" |
| The gene unit, the moved row being one it draws (N) or makes (R), the population declared first | Refused | `integer_unit_population.py:1114–1120`: "cells.operator.templated_polymerisation@1 lists 'N', which this operator moves; the gene unit is its listed rows' one writer" |
| The same, the gene unit declared first | Refused | `templated_polymerisation.py:1484–1497`: "cells.operator.integer_unit_population@1 also declares 'N'; this operator is the one writer of its listed rows" |
| A reaction that only reads S (a catalyst) | Admitted | |
| A reaction, or the gene unit, that writes a row the clock only reads | Admitted | |
| Turnover or exchange of S | Admitted | By the absence of a refusal. No check names them |
| `cells.operator.site_occupancy@1` binding S at the node | Admitted | Nothing checks it (§1.3) |

- **The reactions refuse nothing here.** Their own `check_turnover_rows` refuses turnover on a row they write, and
  no other operator.
- **The gene pair is refused from both sides,** so lifting one check leaves the other.
- **The population's side reads species, not rows.** It compares its whole `species` list with the gene unit's, so a
  species that it lists and no site moves is refused too (measured).
- **Behind the checks: nothing** (measured, `refusals.json`). With the population's two branches skipped in process,
  the reactions' worlds parse in both orders. With the gene unit's branch skipped too, so do the gene unit's, on N
  and on R.
- **Both pairs run** (measured, `run-d152.json` and `run-gene.json`, compiled, every host check on every row):
  - the **five-writer world**: the population, the reactions, turnover, exchange and sites on S, 200 steps of 20 ms;
  - the gene unit and the population on N, 120 steps of 0.5 s;
  - in both, each row's amount is its start plus its writers' books, to 1.1 machine epsilons of their summed sizes.
    The energy ledger closes to 2.4e-14 pJ, the integer ledger is exactly 0, and a restart between events is
    bitwise.

### 1.2 Why they exist

- **Beside the reactions.** D152 §1.1 keeps one **local-kinetics** writer per (species, node), so that one
  integrator sees a node's chemistry whole. The same section says what the rule does not cover: routes "which are
  transport across a patch and compose freely". The population's transfer is such a route, so the reason in the
  message does not reach it (S). The check was written while part 2's files were in another builder's hands (the
  build plan, §5: "their one-writer rules; the part-2 files are not edited").
- **Beside the gene unit.** GENE_REGULATION_DESIGN §7.5 kept its rows to one writer, for one account of the
  nucleotide loop and for want of a two-writer ruling. D315 gave that ruling: one registry potential, separate
  accounts. Part 2A applied it to the reactions and the unit producer, and left other authors refused.
- **The unit producer** (`cells.operator.population_unit_turnover@1`) also refuses the population on its precursor: only
  turnover and the gene unit may supply it (measured). Its reason is different, and it stays (§3.4).

### 1.3 Five findings beside the question

1. **Neither refusal has a test row,** and the composition matrix lists neither. `test_each_refused_neighbour`
   covers replacement, insertion, labels and the partition.
2. **`cells.operator.site_occupancy@1` writes moved rows unchecked.** It binds and releases a ligand in its half-steps
   but declares no species of its own (its identity role is "user"). The population's check names two laws, and the gene
   unit's looks at "authors" only, so sites pass both: on a moved row, and on a row the gene unit lists (both measured).
   No world found holds either pair. The search: files naming both operators, and files using both site and gene-unit
   fixtures (`tests`, `validation`, `scripts`), and the registered texts of FR-49's worlds (L, B, C1, C2) and FR-45's
   protocol. The one file that uses both fixtures binds its sites to S or to a regulator, in worlds without the gene
   unit. FR-49's C4 is not registered yet and adds unlabelled sites to a world with expression (L1). The build searches
   the saved definitions of G1 and crossrev too.
3. **The bound on event rates does not count co-writers.** `check_hazard_bound` takes a moved row's largest
   concentration from its declared material and turnover's production, and refuses dt·a₀ above 1 (a₀ is a site's
   total propensity).
   - A reaction that makes S from 100 fmol of X is not counted: the site is admitted at 0.84 and could reach 80
     (measured, the check skipped). A bound pool that can release S is not counted today either (measured: admitted,
     where counting it gives 1.5).
   - Beside the gene unit a world admitted at 0.1 reached 6e4, as R rose from 1e-12 to 1.3e-6 fmol (measured; it
     then fires at once, and its events still matched at every step).
   - The run-time cap, 64 events per half-step, still refuses and never truncates.
4. **Exchange beside the population was never run.** The plan admits it. No test and no registered world holds the
   pair. This note's five-writer world is its first run.
5. **The pools recorded at an event are first order beside a co-writer** (`trace_pools.json`). The trace's
   `integer_trace_cell_fmol` is the population's view inside the step, off by up to half the co-writer's kick:
   7.0e-3 fmol of a pool of 1 to 5 fmol at 20 ms, order 0.95, where the saved rows are off by 4e-6 fmol. W3 has this
   too (S), and part 3's criteria reported those pools without judging them. The operator's page should say so.

## 2. What the physics needs

### 2.1 What an event does

The question says that a located event reads the pools "and moves whole units of material". In version 1 it reads
the pools and changes the **unit states** only. A channel's stoichiometry is over unit states, and it conserves the
subunits. The rows move between events, by the transfer, as the closed-form relaxation of two pools. So:
- every row is continuous across an event, and no event can make an amount negative;
- the integer ledger, Σ w n per site, involves no row, so no co-writer can touch it;
- an event that consumes pool molecules, such as an assembly drawing on a pool, is another law. It is not designed
  here.

### 2.2 Read rows and moved rows

A co-writer reaches a site in two ways only. Through a read row it changes the clock. Through a moved row it changes
the transfer, which reads both of its rows. So a clock that reads one end of a route feels a co-writer at the other
end. "Exact" below needs the site's rates to depend on the co-writer in neither way, and the site's rows to meet no
other site's (one stage).

| The shared row is | The clock | The amounts | Today |
| --- | --- | --- | --- |
| Read only | Second order in dt | The co-writer's own | Admitted for every writer |
| Moved, and no rate reads either row of its route | **Exact at every dt** | Second order | Refused beside the reactions and the gene unit |
| Moved and read (the feedback both ways) | Second order | Second order | Refused beside the reactions and the gene unit |

### 2.3 What stays exact, and what each writer owes

- **Material.** Every writer books its own moves in its own accumulators and applies them as increments to @3's
  rows, one after another. So n(t) = n(0) + Σ books at every row, to rounding, whatever the splitting.
- **Positive amounts.** Each half-step returns positive amounts or refuses the step: the transfer by its closed form
  (two pools relax towards each other), the reactions and the gene unit by the stage condition on their own rates. A
  sequence of such maps keeps every amount positive, so no joint condition is needed (S). A transfer can lower a
  drawn monomer or raise a product until the gene unit's one-sided domain refuses the step, as any change of its
  rows can today.
- **Energy.** Each writer books the exact free-energy change of its own move from the state it receives. The
  transfer's heat is −ΔF of its two pools, never negative. It has no standard potential in it, because the species
  is the same on both sides. So it cannot disagree with another writer's potential, which is what
  `check_shared_rows` guards (S).
- **The integer ledger** is exact, in integers (§2.1).

### 2.4 The error of two split writers

**Why second order.** For given draws the population's half-step is the exact flow of its own variables, so two of
them in a row are one whole step. The co-writer's half-step is exact or third order. The symmetric sequence of the
two is Strang's.

**Where the clock's error comes from** (S). The co-writer acts in two kicks while the clock runs. Inside a step the
clock reads a concentration that is off by O(dt), and the two halves cancel only over the whole step. An event at
phase φ of its step (0 at the start, 1 at the end) fires off by

    −(dt²/2) φ(1 − φ) r            where the co-writer is declared first (outside),
    +(dt²/2) min(φ, 1 − φ)² r      where the population is declared first,

with r the relative rate (1/s) at which the co-writer alone changes the site's total propensity at that moment. Both
are at most dt² r/8. Measured on the first event of 37 draws, at 20 and 10 ms (`first_event.json`, the prototype):
RMS errors of 1.5e-5 and 9.3e-6 s in the two orders, against 1.5e-5 and 8.2e-6 predicted, with correlations of 0.998
and 0.986. The events after it carry the error along, since the clock restarts at each event.

**Two consequences.**
- **Halving ratios scatter.** φ moves from one dt to the next, so the ratios of neighbouring steps ran from 1.7 to
  7.8 (below), where part 2's window [3.6, 4.4] would fail an honest run. The order is judged as W3's was: one fit
  over five halvings, with a band on error/dt².
- **The amounts carry the same kind of term.** In a step that holds an event the conductance jumps, and the amounts'
  local error is O(dt²) there, not O(dt³). The number of events does not depend on dt, so the whole stays second
  order.

**Measured** (`orders.json`, `orders-strong.json`, `orders-gene.json`): the engine's own half-steps in the
composite's order, the refusal lifted. Beside the reactions (X → S and S + Y → W in the cell; "strong": S rises from
1 to 4 or 5 mM), at 20, 10, 5, 2.5 and 1.25 ms over 20 s, against this probe's own same-draw integration. Beside the
gene unit (the mRNA R moved and read), at 0.5 to 0.03125 s over 600 s, against the same program at a step 64 times
finer.

| Case | RMS error of the event times (s), coarsest to finest | Fitted order |
| --- | --- | --- |
| S read and moved, the reactions declared first | 1.7e-6, 2.7e-7, 3.5e-8, 2.0e-8, 3.2e-9 | 2.19 |
| The same, the population first | 2.1e-6, 5.0e-7, 9.0e-8, 2.6e-8, 1.3e-8 | 1.91 |
| Strong, the reactions first | 2.5e-5, 7.8e-6, 1.1e-6, 4.7e-7, 1.3e-7 | 1.91 |
| Strong, the population first | 1.2e-5, 1.0e-5, 1.7e-6, 2.5e-7, 1.3e-7 | 1.85 |
| S moved, the clock reads X, which the reactions spend | 8.1e-7, 1.3e-7, 4.5e-8, 1.1e-8, 3.2e-9 | 1.96 |
| S moved, constant rates | 2e-14 to 1.7e-13 (the largest error 3.7e-13) | Exact |
| The gene unit's R read and moved, the gene unit first | 4.5e-4, 2.6e-4, 4.7e-5, 1.6e-5, 2.2e-6 | 1.94 |
| The same, the population first | 9.7e-4, 7.9e-5, 3.9e-5, 6.7e-6, 3.9e-6 | 1.95 |

Every run had the reference's events and channels at every step (21 to 33 events beside the reactions, 71 beside the
gene unit) and an integer ledger of exactly 0. Beside the reactions the moiety's total (S, X and W) was constant to
1.1e-13 fmol. The amounts' largest errors over 20 samples fitted orders 1.5 to 2.2 (1.5 on four steps in
`trace_pools.json`, 1.6 in the case that reads X), which the phase makes noisy. Either declared order is second
order, and neither is better in every world.

**A limit, measured** (`stiff.json`, a NumPy prototype that reproduces the engine's numbers to three digits). Second
order holds while the transfer is slow against the step: λ dt ≲ 2, with λ = G(1/V_c + 1/V_o) and G the open units'
conductance. At λ dt from 18 to 2.2 the event times' fitted order fell to 1.7 and 1.4 in the two declared orders (at
20 ms, errors of 5e-4 and 3.5e-4 s). Neither order cures it, and no check bounds λ dt: with nothing else writing the
rows it needs none. The operator's page gains the sentence, and a world with a fast transfer shows its own halving.

## 3. Candidate forms

### 3.1 The forms

Errors are from the NumPy prototype (`forms.json`, `lie.json`), one site beside the reactions, at 20 to 2.5 ms. Form
A's are the engine's to three digits.

| Form | What | RMS event-time error (s) | Order | Cost (S) | It refuses |
| --- | --- | --- | --- | --- | --- |
| **A. Split writers** (recommended) | As turnover and exchange: separate half-steps in declared order | 1.7e-6 to 2.0e-8 | 2 | No program changes. 2.5 to 3.5 agent-days with the general rule (§7) | §3.4 |
| A′. The same, as two lifted pairs | Delete the population's two branches and name it in the gene unit's | The same | 2 | 1.25 to 1.75 | Pairs, by name, in three files |
| B1. The step cut at each event | The composite restarts every writer at each event's time | 3.6e-7 to 5.9e-9 | 2, with clean ratios of 4 | 4 to 6, and part 3's 11 traces rerun. A loop of up to 65 sub-steps around every writer changes every population program | Nothing new |
| B2. One joint integrator | Rows and hazard in one SSPRK(3,3), the event located | 5.5e-8 to 1.1e-10 | 3 | 8 to 12. Every co-writer exposes its rates, new law IDs, one stage condition, and a share rule for the energy, since only the total ΔG is then exact | A co-writer without the hook |
| C. A narrower class | Co-writers only where no event rate depends on them (§2.2) | Exact | – | A's, less 0.25 | The feedback case, which D315 asked for |
| D. Events at step ends | No location | 0.11 to 0.015 | 1 | – | – |

**What stays exact in each.** Material, positivity and the integer ledger in every form (B2's positivity needs one
stage condition over all its writers). Each writer's own energy in all but B2. D's books are exact too; its event
times are not.

**Compile time.** A adds no device code. An existing world compiles as it did, and a co-writer world pays for its
two operators (§5.2). B1 and B2 put every co-writer's half-step inside the population's loop of 65 trips.

**The recommendation is A.**
- B1 buys a constant factor in an error that A already puts far below what a run resolves (1.7e-6 s at 20 ms). It
  also makes the trace's pools second order. But it would change the programs that part 3's judged runs were taken
  from.
- B2 gives up the property that a population alone on its pools is exact at every dt.
- C refuses what was asked, and D is first order and loses events.

### 3.2 The rule, and what carries it

**The rule: a transfer may share a row with any declared writer, unless a writer claims that row alone.**

A transfer is the one kind of writer that makes no claim on a row. It keeps the species' total, so no standard
potential enters its free-energy change and no authority for one is needed. It is transport, which D152's rule
already lets compose freely. Conversions beside conversions (the reactions beside turnover, the gene unit beside
turnover) keep today's rules. Those say which law owns a row's chemistry, which is a separate question.

**It is carried by three optional declarations in the operator contract and one function in the species registry,**
where the other rules of one authority already live (`check_identities`, `check_potentials`, `check_shared_rows`,
`moved_in_step`).

- **`ROW_MOVES`,** a class attribute: "transfer", "conversion" or None. A "transfer" is checked at registration: its
  writes at the cell and at the outside node must be booked by the same accumulators, so that what leaves one side
  enters the other. Of the eleven operators whose half-steps write amounts, that holds for exchange and the
  population and for no other (measured, `lie.json`).
- **`written_rows(spec, declaration)`:** every (species, node) its half-steps can change, by **net** change (a
  catalyst is not written), at cells and finite outside nodes. It replaces `written_species`, which three operators
  define by species only and the registry reads outside the contract, so there is one authority. `check_shared_rows`
  reads its species, and so asks what it asks today: the gene unit's written rows stay its listed rows, at its cells
  and its exported rows' nodes. `half_step_rows` is left alone. It is the rate routes' hook, it lists reactants and
  products gross, and it feeds `self_moved_targets`, which is part of a composition's structure key.
- **`sole_rows(spec, declaration)`:** rows a writer claims alone, with the reason. Only the gene unit claims any,
  and they are today's `single_writer_rows`: its exported rows, its outside degradations' monomers, and its labelled
  rows (FR43_SHARED_INVENTORIES_DESIGN §5, item 3). A label owner cannot meet the population, but exchange can meet
  one.
- **`species_registry.check_row_writers`,** called by each operator that guards its rows and naming the caller, so
  no pairwise check is added (D176's form, as `check_shared_rows` is). It refuses a second writer of a claimed row,
  and an undeclared split writer beside the caller. `check_shared_rows` stays, and asks only conversions for a
  registry potential, as today.

**The interface keeps its major.** The declarations are optional, so an outside operator that does not declare still
registers (MODULE_SYSTEM_DESIGN: an idle optional field keeps the major). Beside an operator that guards its rows it
is refused by name. Every built-in writer declares, and a test holds that.

**Who then stops naming laws.**
- The population's `check_writers` loses its two branches. It keeps the label owner, replaced amounts, mask changers
  without the lifecycle, and in-step movers of a moved row.
- The gene unit's branch on "authors" becomes one on **conversions** of a listed row other than the two admitted
  (the reactions and the unit producer). So `cells.operator.site_occupancy@1` is refused there by name, since it is a conversion
  that its role hid (§1.3).
- The unit producer's branch likewise. A transfer on its precursor stays refused with no new rule: a transfer's
  `production_bound` is infinite at both of its rows, since no static rate bounds it, and R5 already refuses a
  precursor made without one.

### 3.3 The edits

| File | Change |
| --- | --- |
| `operators/contract.py` | `ROW_MOVES` with its check, `written_rows` (for `written_species`), `sole_rows` |
| `registry/species_registry.py` | `row_writers`, `check_row_writers` |
| The eleven split writers | `ROW_MOVES` and `written_rows`, 3 to 8 lines each |
| `integer_unit_population.py` | The two branches go. The hazard bound sums `production_bound` (below); its own is infinite, as a transfer's. Docstring and limits |
| `templated_polymerisation.py`, `population_unit_turnover.py` | Their author branches; `sole_rows` |
| `species_reactions.py`, `species_turnover.py`, `species_exchange.py` | `production_bound` (a transfer's is infinite) |
| `composition_matrix.py`, `PUMP_COMPOSITE.md`, the operator's page | The rule rows. The page drops "a supply shared with reaction networks or the gene unit", and gains the trace and λ dt sentences |

**The hazard bound** (§1.3). `production_bound(spec, declaration)` is the gene unit's hook, read by the unit
producer's R5: the largest rate at which an operator makes a row. Turnover's literal becomes turnover's own hook.
The reactions give one for a zero-order source and for a saturable route without a catalyst, whose rates are
bounded. Every other route makes its product without a static bound. A moved row made without one leaves its site
unchecked at the definition, as a read of a read-only species is today, and the run-time cap stays the guard. Only
conversions are summed here: a transfer keeps the species' total, which the bound already counts in every cell and
finite node.

**D148.** Everything here runs on the host. No traced program, layout, state or control changes, and no hook that
reaches a program is edited, so crossrev is identical by construction. The proof is crossrev, G1, and a jaxpr-text
check of W1's and W3's steps, which no crossrev set holds.

### 3.4 What it refuses, by name

| Composition | Why |
| --- | --- |
| A moved row that the gene unit exports, or whose monomers it returns at a node; exchange of a labelled row of it | The gene unit claims the row alone (amendment T; the same item 3) |
| The unit producer's precursor as a moved row | R5: a transfer has no static supply rate |
| The gene unit beside `cells.operator.site_occupancy@1` on a listed row (new) | A second conversion. It closes §1.3's hole |
| An undeclared split writer beside the population, the gene unit or the unit producer (new) | Fails closed |
| A label owner; replaced amounts; insertion; an in-step mover of a moved row | As today |
| Water or a lumen beside the population | Its volumes are declared reads (§4.3) |
| A co-writer in a dividing cell | The reactions and the gene unit read the masks as declared |
| RK4 beside the reactions | As today |
| The wash, and the region readouts | §4 |

### 3.5 What newly parses, and what covers it (D327's rule)

| Newly parsing | Covered by |
| --- | --- |
| The population with the reactions, in the cell or at the node | The judged world W5, the closed-form row and the five-writer run (§5) |
| The population with the gene unit | The judged world W6 and its run |
| The gene unit, the reactions and the population on one row (all six declared orders parse with the refusals lifted, measured) | The gene unit's run, which is C2.3's pair with exchange and the site on N: books, ledgers and restart. Its order is not judged (§5.1) |
| The population beside the gene unit under RK4 (measured; the reactions refuse RK4) | A parse row. Turnover beside the population under RK4 is admitted today (measured), and the half-steps are the same functions around @3's RK4 step |
| Both with turnover, exchange and sites on the same rows | The five-writer run |
| Exchange beside the gene unit on a listed row (by the rule; it parses in both orders with the branch lifted, measured) | The gene unit's run holds exchange too. Across a compartment's patch it is refused by name in `check_compartments`, until FR-49's combination checks cover it |

## 4. D328's two version-1 refusals, and water

### 4.1 Beside `cells.operator.scheduled_compartment_wash@1`: not reached

- **Today** the wash refuses any world that holds the population, whatever the nodes (measured), because
  `surface_crossings` lists the law whole. A wash reads no transfer, with or without a co-writer, so this item
  changes nothing there.
- **What would lift it.** FR-54/57's router (`liquid_routing@1`, branch `fr54-57-design`) takes the wash's place and
  inherits its reader of crossings. Two steps, each its own:
  1. **By node.** The reader lists the population's sites (patch, species) as it lists exchange's routes, so a
     portion at a node that no site faces is admitted. About 0.25 agent-day (S) and one composed run.
  2. **At a site's own node.** A portion event is a reset at the start of a step, and the transfer's half-step is
     exact from whatever state it is given, so no new splitting error arises there (S). One composed run shows it:
     the books, the closed-form relaxation after the event, and the next event time against the same draws. About
     0.5 agent-day (S). A **flow** at that node is a second split writer of the node's rows, which the router
     refuses in version 1 as it does turnover's.
- Both belong to the router, since the wash is retired after its arm 7.

### 4.2 In the region readouts: not reached

- **Today** the export and the tracer (`validation/regions/readouts.py`) refuse any world with the population
  (measured).
- **The export** could read the transfer as one more route column, since `integer_transferred_fmol` is signed and
  booked per route. In a world with the reactions that is enough. With the gene unit it is not, because the export
  refuses that law for the same reason. About 0.25 to 0.5 agent-day (S), in `validation/`.
- **The tracer** cannot. A transfer is two-way at a net record of zero. Tracing it needs its one-way parts, ∫G
  n_c/V_c and ∫G n_o/V_o. Both are closed form in this operator's flow, but they are new owned fields, so the
  programs change. The label owner needs the same two.

### 4.3 At changing volume: a third door, not in D328

The build plan (§9, item 3) lists "beside water" with the two cases this note treats. D328 names only the two. The
population reads the declared volumes, so water is refused whatever the writers. Lifting it is current reads of both
volumes by FR-43 part 2B's pattern, in this operator's flow and heat: about 1.25 to 1.75 agent-days with its own
checks (S), after FR-65's shared volume rule. Whether part 3 closes without it is question 3.

## 5. Acceptance

### 5.1 What the registered evidence already covers

| Evidence | What it covers | What it cannot see |
| --- | --- | --- |
| **W3** (part 3, judged, D319) | The population beside turnover on a moved and read row: production in the cell, clearance at the node; order 1.96 | A rate that depends on the shared row or on other rows; an SSPRK half-step; a co-writer with rows or pools of its own; a standard potential on the shared row; the gene unit's one-sided domain |
| **C2.3, C2.8** (part 2, judged, D324) | The gene unit beside the reactions on one row, at fixed and changing volume | Any event |
| **W1, W2, W4** (part 3) | The population alone | Any co-writer |

None is a co-writer world of this item. W5 and W6 below are pairs too, so the triple's order is not judged. It rests
on the argument for any two split writers (S), and the triple's run checks its books, ledgers and restart.

### 5.2 Rows in existing files

Seconds are estimates until the build measures them (D224). This note's compiled worlds took 74 s (five writers) and
55 s (the gene pair) to compile and run on a busy CPU.

| File (tier, today) | Rows | Plants, which must be caught | Added |
| --- | --- | --- | --- |
| `test_species_registry_movers.py` (1, 0.5 s) | The rule on stub operators: a transfer shares, a claimed row refuses, an undeclared writer refuses; every built-in split writer declares | A conversion that calls itself a transfer is refused at registration | 0.3 s |
| `test_shared_inventory_writers.py` (1, 3.6 s; parses) | Admitted, both orders: the reactions at the cell and at the node; the gene unit's N and R; exchange beside the gene unit; the triple; the gene unit under RK4. Refused by name: §3.4's first four rows, the labelled row among them | Each refusal's row fails with its check removed | 3 s |
| `test_integer_unit_population.py` (2, 35.5 s) | The hazard bound: a bounded source counted, an unbounded one unchecked. One compiled world with a zero-order source of S: the first event against its closed form, the books per writer at every row, a restart between events | The closed form without the source misses by 100 times the tolerance (W3's plant); one writer's books 1e-3 high | 35–45 s |
| `test_integer_unit_population_statistics.py` (3, above the 90 s cap) | The five-writer world, and the gene unit's (C2.3's pair with exchange and a site on N): every host check on every row, the books, the integer ledger, the restart | In a copy of the run's records: one writer's books 1e-3 high; the transfer booked on one side only | 100–130 s |
| `test_composition_matrix.py` (1, 5.1 s) | The regenerated block | – | 0 |

- **No test file is added.** If the tier-2 file would pass 80 s (its cap is 90, and FR-52 adds 3), its compiled
  world goes to the statistics file.
- The tiers are re-measured at the landing (D224, D229).

### 5.3 One judged comparison (recommended)

**D187 rule 6** asks one registered judged run per claim. The claim is new: beside a writer whose rate reads the
shared row, the event times and the amounts of a low-count population converge at second order to the coupled
process. W3 is the same form beside a writer whose rates read nothing (production) or their own row alone
(clearance).

- **W5, the reactions:** part 3's cell and node, two subunits with feedback on S, and X → S with S + Y → W in the
  cell. Five steps from 20 to 1.25 ms.
- **W6, the gene unit:** its mRNA R, made and degraded by the gene unit, moved to a finite node by one site whose
  clock reads R. Five steps from 0.5 to 0.03125 s. It is the world of this note's probe (71 events, orders 1.94 and
  1.95). On the nucleotide N the gene unit is too slow to show its own splitting: in 60 s it moved N by 0.007 fmol,
  the transfer by 1.5 (measured).
- **W5′:** W5 with constant rates, at two steps. Its event times must agree with the reference at rounding.
- **The references** are code-blind: part 3's same-draws integration with W5's reactions, and part 2's coupled
  gene-unit equations with the transfer and the clock. Their spec is a new file, so the tagged `part3.json` and
  `draws.json` stay as they are. It is tagged before any engine reading.
- **The criteria** follow part 3's §2: the trace equal at every step; the fitted order of the RMS event-time error
  in [1.7, 2.3]; a band on RMS/dt²; a size at the finest step; and a fit for each writer's books and for the shared
  amount. The trace's pools are reported, not judged (§1.3).
  - **What the probes say about the bounds.** With 21 to 71 events the band on RMS/dt² ran from 1.5 to 6.4, and W3's
    was 1.8. So the bands and the amounts' window are set from an engine-only development run, before the tag, on
    worlds of about 100 events whose co-writer moves the propensity by at least 0.1/s.
- **The plants, which must fail.**
  - **In the references:** the reactions' k, and the gene unit's transcription rate, each 1% high; and a size plant
    at 10 times the finest bound.
  - **In the driver:** the second halves not reversed (Lie splitting). In the prototype it is first order (4.2e-4 to
    5.3e-5 s, order 1.0). It is a mutant of the engine's run, not of the reference.
- **The cost:** five steps of each world and the plants, a lane for about 15 minutes.

**The registration proposes other bounds (25 November 2026).** The protocol (`docs/FR43_PART3_COWRITERS_PROTOCOL.md`,
with the spec folder, both on branch `fr43-part3-spec`) proposes this comparison's worlds and plants, with 8 independent
copies of each world, sites of 2 subunits and two declared orders, the order fitted on the engine's own step differences,
and windows and tolerances from a declared order and counted rounding. The lead rules on its questions; no bound is set by
an engine run.

### 5.4 If no judged comparison is made

The rows of §5.2 hold books, ledgers, restarts and one closed-form event. None sees the order of the coupled
process. That would rest on this note's probes, which are development.

## 6. Interaction

### 6.1 The rename

The build came after it (D345's move, with the legacy cleanup). `integer_unit_population@1` became
`cells.operator.integer_unit_population@1`, and its neighbours took the same form (the candidate table on
`rename-design`, 2dd54f72). No ID or major is added. This
build deletes the population's two law literals and turnover's in `check_hazard_bound`. Part 3's tagged
`REGISTRATION.md` and `references/` are never rewritten. `validation/fr43_part3/worlds.py` is (the candidate lists
it), so the new worlds come after the move.

### 6.2 FR-52 (cohort records on the same operator)

**This item first.** It is host-only, so FR-52's frozen evidence (part 3's 11 traces, byte for byte) and its D148
proof are untouched. FR-52's note says that the program without its record, which every existing world of the
operator runs, is in neither G1 nor crossrev. The co-writer world of L4 would be that world.
- **FR-52 assumes** that an event changes unit states only, and reads counts and event times. A co-writer changes
  neither.
- **What FR-52 must not carry over:** its sum-to-flux check equates the closed-form integral over an event-free step
  with the booked transfer. That holds where the population alone moves its pools. Beside a co-writer the driving
  difference changes inside the step, so the check stays on FR-52's own world (S).
- **D327:** FR-52 lands second, so it carries the pair's check: the five-writer world with `cohorts` declared, its
  other fields bit for bit the undeclared run's (one more compile, tier 3).

### 6.3 FR-65 (turnover beside a changing volume)

**Either order; this item first is simpler.** Both edit `contract.py` (different hooks), `species_reactions.py` and
the generated matrix, and share no function. This item assumes nothing of FR-65. FR-65 gains two things from here:
- **Its D148 pair check should hold W3's world,** turnover beside the population. Its §3.9 names turnover's other
  neighbours and not this one.
- **It newly parses a four-operator composition that its note does not list:** membrane state, the partition,
  turnover and the population, in a dividing cell (measured, `fr65_meets.json`: refused today by turnover's two
  masks, admitted in both orders under FR-65's reads). Its enumeration stops at three operators. By D327 whichever
  lands second carries a check or a refusal by name. A check is cheap: W3's turnover in part 3's divided world.

### 6.4 FR-54/57

§4.1. The router's reader would list the population's sites. This item adds nothing to it.

## 7. Price, order and questions

| Part | Agent-days (S) |
| --- | --- |
| The contract, the registry rule and eleven declarations | 0.75–1 |
| The four operators' checks, and `production_bound` | 0.5–0.75 |
| Tests (§5.2) with their plants | 0.5–0.75 |
| The matrix, the page and the design notes | 0.25 |
| D148's evidence, the tiers and the gate | 0.25–0.5 |
| A co-writer world in G1 and crossrev (L4) | 0.25 |
| **The build** | **2.5–3.5** |
| The spec, the criteria and the two worlds | 0.5 |
| The code-blind references | 0.5–0.75 |
| The judged run | 0.25–0.5 |
| **The comparison** | **1.25–1.75** |
| **In all** | **3.75–5.25** |

With A′ the build is 1.25 to 1.75 (S), without L4. **Gates:** one full gate for the build (src changes), and one
no-src stack for the spec, the criteria and the references, tagged before the build.

**The order.**
1. This note, with the rulings.
2. The rename lands.
3. The spec and criteria, then the references, each tagged. They name no engine ID, so they can start before step 2,
   and may start now (the lead, 25 November 2026). The spec's branch is `fr43-part3-spec`.
4. The build, its tests and its gate. It waits for the legacy cleanup: the user put every other build on hold
   (25 November 2026).
5. The judged run from a clean snapshot of the gated head, then the landing.
6. FR-52, then FR-65 (or FR-65 first, if its owner is free).
7. The router's two steps (§4.1), after the router lands.

### Questions for the user (all decided on 25 November 2026)

1. **The form.** (a) Split writers, as turnover and exchange are: second order, no program changes. (b) The step cut
   at each event: the same order, about 5 times smaller errors at one step size, second-order pools in the trace, 4
   to 6 agent-days, and every population program changes. (c) Only co-writers that no event rate depends on (§2.2).
   **Recommended: (a). Decided: (a).**
2. **The judged comparison.** (a) One judged run over W5, W6 and W5′ with code-blind references. (b) W5 alone. (c)
   None: the builder's tests. **Recommended: (a).** It is FR-43's own claim, and nothing registered sees it.
   **Decided: (a).**
3. **When part 3 closes.** (a) At this landing, with the population at changing volume (§4.3) logged as a request of
   its own. (b) Part 3 stays open until then. **Recommended: (a).** D328 names the two co-writers only.
   **Decided: (a).**
4. **How general the rule is.** (a) The declared rule of §3.2, which also admits exchange beside the gene unit. (b)
   Two lifted pairs: about 1.25 agent-days less, and the next pair is another edit in three files. **Recommended:
   (a). Decided: (a).**

### For the lead (ruled on 25 November 2026)

- **L1. `cells.operator.site_occupancy@1`** (§1.3). (a) Refuse it beside the gene unit's listed rows, and cover it beside the
  population in the five-writer run. (b) Leave it. **Recommended: (a),** after a search of every saved definition
  for the pair. It newly refuses a composition that is admitted today. So if a registered world binds sites to a row
  the gene unit lists (none found; FR-49's C4 amendment is still to be written), L1 goes to the user. **Ruled: (a).**
  The search found no such pair, so it is refused. The build still searches the saved definitions of G1 and crossrev
  (§1.3), and a pair found there goes to the user.
- **L2. FR-65's list** (§6.3): W3 in its pair check, and the four-operator composition. **Ruled: as listed.**
- **L3. The bound on event rates** (§3.3): an unbounded producer leaves the site unchecked, as a read-only species
  does. The other choice, refusing it, would refuse most reaction networks. **Ruled: as stated.**
- **L4. G1 and crossrev** (D187 rule 2: each landed feature adds one world). (a) The tier-2 world, the population
  beside the reactions with no cohorts, joins both: one compile and run in each later gate (30 to 45 s, an estimate)
  and one set of jaxprs. FR-52's world then joins beside it, with its record. (b) None, since no program changes
  here. **Recommended: (a). Ruled: (a),** one co-writer world in G1 and crossrev.

## 8. What is not claimed

- **No other writer.** Conversions beside conversions are unchanged, as are in-step movers, charged rows and held
  baths.
- **No volume change and no division** with a co-writer (§3.4, §4.3).
- **No event that consumes material** (§2.1).
- **No order above second,** and none where the transfer is fast against the step (λ dt ≳ 2). No order for the
  trace's pools (§1.3).
- **No energy claim beyond the ledger's bound.** The operators' own guard statements stand.
- **Development.** Every number above is a probe's. Nothing is judged, and the composite on a GPU stays refused
  (D336).

## 9. Evidence and disclosures

Folder: `/mnt/workspaces/Cells/fr43-part3-cowriters-20261125/` (`probe/` the scripts, `out/` their records). Run
from this branch's worktree at 0e563668, clean, on CPU 22, one process at a time, 6 GB, no lane lock, no GPU. CPU 22
and the other light CPUs were busy with other jobs, so no time below is a timing.

**What was compiled, against the brief's limit** (no compiled world beyond what one existing test file does; the
statistics file compiles four):
- two composite worlds, through the runner: the five-writer world (200 steps) and the gene pair (120), each with one
  resume;
- nine jitted loops of the operators' half-steps without the tissue's step: `orders.py` two (and a first version,
  stopped during its compiles), `orders2.py` two, `orders_gene.py` two in each of two runs, `trace_pools.py` one.
  Each loop compiled in 20 to 35 s.

| Record | What it holds |
| --- | --- |
| `writers_table.json`, `lie.json` | Every operator's declared writes; the accumulators' pairing; the Lie plant |
| `refusals.json`, `refusals2.json`, `byproduct.json` | The parses of §1, §3.5 and §4, today and with each refusal lifted in process |
| `orders.json`, `orders-strong.json`, `orders-gene.json` | §2.4's table (the engine's half-steps) |
| `orders-gene-trace-start.json` | §1.3's second example: the same gene world with a rate 5e5 times larger |
| `trace_pools.json` | §1.3's fifth finding |
| `forms.json`, `stiff.json` | §3.1's forms and §2.4's limit (a NumPy prototype; form A agrees with the engine to three digits) |
| `run-d152.json`, `run-gene.json` | The two compiled worlds: 200 and 120 steps, every host check, a restart |
| `first_event.json`, `triple.json` | §2.4's formula against the first event; N's parses in both orders; the triple, RK4 and the labelled row |
| `fr65_meets.json` | §6.3's four-operator parse |

**What was not checked.**
- **The compiled programs' identity:** the rule is host-only by reading, and no jaxpr comparison was run.
- **A batch, a GPU, a label owner, a compartment or a partition** with a co-writer (a partition and a labelled row
  by parse only). The triple was parsed, not run. The five-writer world's own order. W5's and W6's power, beyond the
  probe's. λ dt in the engine, since §2.4's limit is the prototype's.
- **The gene unit's order is self-convergence,** against the same program at a finer step. Beside the reactions the
  reference is this probe's own integration, not code-blind.
- **The seconds** in §5.2 are estimates.
- **The saved definitions of G1 and crossrev** for §1.3's pairs. The searches are of files and registered texts.

**Read beyond the brief:** part 2's and part 3's tagged criteria texts and part 3's references' spec; the rename's
note and candidate table; the decisions D136, D142 to D144, D148, D187, D223, D224, D229, D232, D235, D301, D339,
D345, D346, D358, D365, D371 and D375 to D379; the FR-43 part 3 landing notes; FR-49's registration and FR-45's
protocol (searched for sites beside the gene unit); and MODULE_SYSTEM_DESIGN's interface rule. No file under a
`references/results` or `references/out` folder was opened. Content searches ran over `src`, `tests`, `docs` and
`validation`, which pass through the references' folders, and displayed no line of theirs. The fixture that builds
part 3's divided world reads the declared values of `part3.json` in process; they were not displayed.

**A slip in running the probes:** a `pkill -f` on the pattern `probe/orders.py`, meant for this agent's own run,
matched its own shells and stopped its first order study and a waiting command. Whether it matched any other process
was not checked. The study was rerun with one compile per declared order. **The advisor** read the draft once; its
corrections are in this version.

## 10. As built (26 November 2026)

Branch `fr43-cowriters-build` from main c52d0998: this note merged (868a51fa), the engine rule (155293d0), the tests,
worlds, matrix and page (34928328). Form A with §3.2's rule and §3.3's edits, and the lead's answers of 26 November.

**Where the build departs from §3.**
- **A fourth optional declaration, `SHARED_ROW_POTENTIAL`** (the lead's Q1 (a)), on the reactions, the gene unit and
  the unit producer. `check_shared_rows` reads their `written_rows` by species, so it asks the writers it asked before:
  on every swept definition the askers are identical. One exception, in no swept definition: a gene unit with no pool,
  chain, degradation, transfer or export writes no row, so it no longer asks (it asked for its listed species). Asking
  every conversion would have refused, where the registry gives no potential, turnover beside the reactions at another
  node, turnover beside the producer, sites beside the reactions, and §1.1's five-writer world.
- **The gene unit's and the unit producer's branches read rows, not species** (§3.2): an operator that declares a
  listed species, or the precursor, without writing it is now admitted, where an author that declared it was refused.
  It is §1.1's quirk removed, and a loosening the lead rules on; no swept definition holds such an operator.
- **The unit producer refuses site occupancy on its precursor by name,** by §3.2's "likewise": a new refusal, beside the
  gene unit's (L1). No saved or fixture definition holds the pair (the host sweep below).
- **Turnover's `production_bound`** is R5's literal: each production route's largest rate over its schedules, summed
  per row. `check_hazard_bound`'s literal summed per schedule. The two differ only with a replacement's newcomer
  schedules, and the population refuses replacement. Measured at base and head, bit for bit equal: `supply_bound` on
  the producer's turnover-supply world and on part 2's unit pair, and dt a₀,max of part 3's W3 (two horizons) and W1,
  found exactly by bisecting the check's bound.
- **Written rows:** a lumen's are every species at its node, since a scheduled bath may hold any. A gene unit with no
  pool, chain, degradation, transfer or export writes no row, so it no longer asks for a registry potential; no saved
  definition holds one.
- **L4:** the gate's crossrev verdict requires identical file listings, so the co-writer world in crossrev's reactions
  set (`reactions_integer_source`) is a listing difference until the record holds it. Its record files and its G1
  save are in the evidence below, for the lead's renewal. Its G1 window of 200 steps holds one event, the first
  assembly, and the transfer after it.

**Tests** (no new file; measured on the timed cores with lane A idle, against the record's rows: the registry file
2.3 s against 0.5, the shared-inventory file 5.3 against 3.6, the population file 63.9 against 35.5, so its compiled
world stays in tier 2 under §5.2's 80 s rule; the producer's, the gene unit's and the matrix's within their rows):
- tier 1, parses: the row rule on stub operators and the declarations' misuses (`test_species_registry_movers`); the
  newly admitted pairs in both orders, the triple in all six, RK4 and §3.4's refusals by name
  (`test_shared_inventory_writers`); the compartment's transfer row; the producer's stub rows; the matrix;
- tier 2: the event-rate bound beside a co-writer, and one compiled world, the population beside a zero-order source
  of S: the closed-form first event, each writer's books at every row, a restart between events
  (`test_integer_unit_population`);
- tier 3: the five-writer world and the gene unit's, books and ledgers by the composite's own checks with two plants,
  and a restart (`test_integer_unit_population_statistics`);
- every new refusal row fails with its check planted away (21 of 21).

**D148** (the round's records: `/mnt/workspaces/Cells/fr43-cowriters-build-20261126/d148/`):
- **crossrev** (11 sets, base c52d0998 against head 34928328, the pair runner under lane A's lock): 10 sets identical;
  the reactions set's 8 worlds identical, and its listing adds exactly the co-writer world's 9 files (L4, by design).
- **G1** (113 worlds): the base equals c1 (113 of 113), the head equals c1 (113 of 113), and base against head is 113
  of 113 identical.
- **The judges' derivative programs** (the stationary analysis's linearize and jvp programs over crossrev's
  qualification, acceptances and kinds sets and W1's P2 world, 36 worlds a side): 257 files identical.
- **The worlds no crossrev set holds** (part 3's W1 and W3, part 2's pairs and unit pair, FR-2's trafficking, S3's
  lumen@1 egg): their program texts and constant records, traced as crossrev traces them, 56 files identical; their
  bindings were not compared.
- **FR's bitwise set** (through its own holder on lane B): passed before and after, its nine quick parts identical and
  its windowed arms T and R bitwise.
- **The host sweep** (238 definitions: crossrev's, G1's 113, parts 2 and 3, the co-writer worlds; then FR-49's World
  L, B and its node-owned variant): every existing definition parses as before with the same shared-row askers. The
  only changes are the co-writer worlds (admitted), the refused ones' messages, and site occupancy on a listed row
  (refused, L1).
- **Tiers 1 and 2** of the head on lane A: 520 files, none changed (8 hold more tests than their rows). Tier 3's
  statistics file in full: 12 of 12.
- **By construction:** no traced program, layout, state or control changed; every new hook runs on the host.

**What stays for others:** §6.3's two items are FR-65's (the lead's order: this build lands first); §5.3's comparison
is registered (`fr43-part3-cowriters-criteria-2026-11-25`) and follows the landing.

**The trace's counts (26 November 2026, branch `fr43-trace-counts`; the user's choice (1), the lead's terms).** The
registration's trace check (CRITERIA.md §3.1, counts against the channel) needs the engine's own counts after each
event, and the trace held none. So the population records them: `integer_trace_counts` [site, trace slot, unit state],
int64, -1 where no event is recorded, beside each recorded event's time, channel and pools.
- **What it holds.** The value written is the counts the event loop carries on after the event (`counts_new`, which
  becomes the next segment's counts and the state's `integer_counts`). It is never formed again from the channel's
  declared jump. So a trace whose counts break the declared jump shows an engine that applied another one.
- **The plant.** `test_the_trace_records_the_counts_the_loop_carries` has two rows. The declared engine's record keeps
  the jumps and every row's counts. A planted one, assemble's change zeroed in the bound layout (a wrong jump that
  keeps the subunits), records the counts it carries, which break the declared jump.
- **In place under @1** (the lead, after MODULE_SYSTEM §2.3): no declaration key and no meaning changes. No rate, draw
  or ledger reads it. The composite's finiteness check over the operator's owned fields covers it, and is always true
  for an integer field. It is a record sized by `trace_events`.
- **What changes.** The state layout gains one owned field, zero-size at `trace_events` = 0 but still a leaf. So the
  program text changes for every world of the operator, not only those with a trace. Checkpoints saved before it do
  not load.
- **The round** waits for FR-65's landing (the lead assigns lanes): every existing field bit for bit, part 3's judged
  traces and statistics included. Crossrev's co-writer world's nine files are superseded, not added (the 23 November
  renewal's pattern), and its G1 save is renewed.
- **Once this lands,** the registration's exporter (validation/fr43_part3_cowriters) copies the field and derives
  nothing. Until then it forms the counts from the declared jumps and checks them against the engine's counts and
  channel totals at every sample.
