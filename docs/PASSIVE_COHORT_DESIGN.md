# Passive cohort observations for integer units (FR-52): design note

**Status: a design, written 24 November 2026 at main cfb08756 on branch `fr52-design`, and revised since with the
user's decisions and the lead's rulings (D371 at main b4138881, D375 at main c9da0fdb and D376 at main fcc73736,
all merged here, and the lead's after D376). Final. The build follows the rename. Nothing is built.**
Integration grants no acceptance (D143). **S** marks this note's own reading or proposal.
The premises were read at cfb08756. The operator, its contract and its tests are unchanged at fcc73736.

**The request:** FR-52 in [FEATURE_REQUESTS.md](FEATURE_REQUESTS.md), high priority (the user). D339 corrects its
premise: one event can move several units. D347 records that C3.6's same-seed restart settles its restart premise.
D371 decides its form and scope, and D375 how a split counts.

**Engine models it runs:**
- `resolved_pump_composite@1` over `resolved_pump_tissue@3`;
- `integer_unit_population@1` (FR-43 part 3), with its step `located_events_exact_transfer_half_steps@1`;
- the scalar windowed runner and `execution/batch.run_batch`, on CPUs.

**Read for it:**
- the code: `operators/integer_unit_population.py`, its library page and both test files; `operators/contract.py`;
  `numerics/label_shares.py`;
- the notes: [NEUTRAL_LABELS_DESIGN.md](NEUTRAL_LABELS_DESIGN.md) §7 and §9, and FR-38 v2's classes (erratum I);
- the requests FR-42, FR-44 and FR-49, and the decisions D148, D339, D345 to D347, D362, D371, D375 and D376.

## 0. Summary

| | |
| --- | --- |
| **The quantity** | A cohort names one site, its identity class (the unit states that are forms of one unit) and a window [start, end). For each state of the class it gives the expected number of units whose identity began at t = 0, or before, inside or after the window. In each state these sum to the engine's count |
| **Decided (D371, D375, D376)** | **The user:** the engine record kept at each event, with the trace reader in `validation/` as the independent check (Q1); an identity map across states in version 1 (Q2); a split makes a new unit (P2). **The lead:** a class state on both sides of a channel is refused (Q3); the new tier-2 file plus one integer-unit world, its cohorts declared, in G1 and crossrev (Q4, P3); an optional `cohorts` key (Q5); a one-for-one step keeps its identity undeclared (P1); exactly min(R, P) identities go on, and a unique pairing resolves by rule (D376); frozen fractions with a stated rounding bound; a host test of the update with a planted one-pair error, and `open2` (2T_c → 2T_o), compiled and frozen as row G (after D376) |
| **The identity map** | A channel whose legal pairing is unique resolves by rule, with no declaration (a one-for-one step, a merge, a split or a conversion between single states). A channel with two or more legal pairings declares its pairs, and an undeclared one is refused. As many identities go on as the channel can: min(R, P). In a split one half keeps the identity and the others are new (D375). A unit entering the class is new, and one leaving it is lost (§2.3) |
| **The update** | Exact by linearity. A uniform loss scales each label by (n − r)/n, a carried unit brings its source state's share, and a new unit joins the label of the event's time (§2.3) |
| **Passive** | No law, validity check or random draw reads the record. Twins, observed and unobserved, must agree bit for bit on every other field, in fresh processes, scalar and batch (§2.2) |
| **Frozen values** | Seven event lists with their exact fractions, enumerated over labelled units: FR-52's table, D339's row, a dimer-to-tetramer chain, its round trip, a single-subunit activation, a heterotetramer whose channels need a declared map, and two closed tetramers opening together, whose table holds two pairs (§3). A binary64 record must meet each within 8 (K + 1) u N (§2.3). The copying reading of a split, not taken, is frozen beside the chain's |
| **Splits (D375)** | A split makes a new unit. One half keeps the original identity and the other counts as newly assembled, so the class's `initial` is a survival count (§2.3) |
| **Refused in version 1** | An ambiguous or incomplete map, a class state on both sides of a channel, a conducting state outside the class, and a map that crosses a division (§2.6) |
| **Price** | 4.25 to 5 agent-days with the gate. The build comes after the rename (§8) |

## 1. What FR-52 asks, in the engine's terms

**Exchangeability.** Units of a state are exchangeable under the operator's own law.
- A channel's propensity, k Π ff(n_k, r_k), counts ordered tuples of distinct units.
- So the units an event consumes are a uniformly random subset of each state's units, independently across states.

**The cohort (S).** FR-52's "one exchangeable active-unit class" becomes a declared identity class C: the unit states
that are forms of one unit, at one site s.
- **One state** is the plainest case. FR-52's table and D339's row use it.
- **Closed and open,** or inactive and active, form one class, so a unit that opens or activates is not new.
- **A chain such as dimer and tetramer** forms one class, so a partial-assembly step is not a new assembly. A split does
  make a new unit: one half keeps the identity, and the other is new (D375, §2.3).

**The labels (S)** follow FR-38 erratum I's pattern, as FR-52's first reading asks: a class for what is present at the
start, then classes by arrival time. So they partition each state's count:
- `initial`: the units in C's states at t = 0, the run's start;
- `before`, `inside` and `after`: the units whose identity began at an event time in [0, start), [start, end) or
  [end, ∞).

**What the record gives:**
- **An exact expectation** of each label's count, conditional on the recorded events (§2.3).
- **No realization.** It takes no random draw.
- **Gross across events.** A unit that leaves the class and comes back is new. The library page states how returns are
  counted, since net against gross was FR-38's first confusion (D371).
- **Counts, not shares.** Expected counts are carried, so an emptied state holds an exact 0, with no 0/0.

**The outputs:**
- the expected count (units) for each state of the class and each label, each labelled an expectation;
- the class's expected conductance per label, Σ_k∈C g_r,k E_k,l (pL/s) on each route r;
- at a declared driving difference Δc (mM), the flux contribution, conductance times Δc (fmol/s).

FR-52's two quantities are then:
- the `initial` label summed over the conducting states: the original units still contributing to transport;
- the `inside` label summed over the class: the units formed in the window, by assembly or by a split.

**Premises, checked at cfb08756:**
- **Several units per event.** `_stoichiometry` admits up to `MAX_ORDER` = 4 units of a state on each side.
- **A state on both sides.** Each side is parsed alone. A channel is refused only when its sides are identical, when it
  has no reactant, or when it does not conserve the subunits.
  - So `{active: 2} → {active: 1, free: 2}` parses, and `integer_change` is net there.
  - The gross figures can still be recovered from `integer_reactants`.
- **The trace:**
  - it holds the first `trace_events` = T ≤ 65,536 events per site;
  - channel −1 means not recorded, and `integer_events` counts every event;
  - it is owned state, so every saved row carries all of it: T (2 + 2R) values per site (`working_size`).
- **Division.** `divide()` moves counts with no trace entry and no event.
- **Neighbours.** `check_writers` refuses a label owner, and the wash refuses the operator.
- **Restart.** C3.6 resumes a same-seed run bit for bit over every owned field, the trace included (D347).

## 2. Options and decisions

### 2.1 Where the observation lives: decided, A (the user, D371)

| Option | For | Against |
| --- | --- | --- |
| **A. A record in the operator (decided)** | It has no capacity limit and costs 4 values per class state per cohort per row. The update reads the same integers the counts add, at the event's own time. Checkpoints carry it as owned state | Where declared it changes the compiled step, so its passivity is measured, not given (§2.2) |
| B. A host readout over complete traces | The step does not change, only T | It can read only 65,536 events per site, and every row grows with T. With one route, an hour at one event per second holds 3,600 × 4 values per site in each row. Raising T changes the program too, so B needs the same twins |
| C. A cohort owner, like FR-42's label owner | One owner for labels and cohorts | Events within a half-step depend on their order: an arrival then a loss differs from a loss then an arrival. So an owner needs a per-event report. Either way the per-event arithmetic stays in the operator that sees the events, so an owner adds a seam and no logic |

**On AGENTS.md's line.** A reader that is the feature computes a consequence of an engine law for users, so it belongs
in `src`. Only the reference stays in `validation/`: the exact-rational reader over complete traces, and the exact
distribution by enumeration (§3).

**The pieces (S):**
- **`numerics/unit_cohorts.py`:** the map's rule (§2.3), the update and the half-open label rule.
  - It is one code for NumPy and jax.numpy.
  - A later owner of integer units can reuse it, for example the assembly family's exact events.
- **`integer_unit_population@1`:**
  - an optional declaration key `cohorts` (§2.3);
  - the record `integer_cohort_units` [integer_cohort, integer_state, integer_cohort_label]. Each state of the class
    starts at [n_k(0), 0, 0, 0], and the other states hold 0;
  - the layout fields `integer_cohort_site`, `integer_cohort_class` [cohort, state] and `integer_cohort_pairs`
    [cohort, channel, state, state]. The rule's readings are resolved into the pairs at binding, so the step applies one
    form;
  - `integer_cohort_window_s` [cohort, 2], per-world data in a batch;
  - the run view's sets, the summary and the batch signature;
  - any sum the operator gains goes through `entity_sum` and joins A7's frozen list
    (`tests/species_sum_entity_sums.json`).
- **A host readout, `cohort_readout`,** in the operator's module: the outputs of §1, with their integrity (§2.3).

### 2.2 How it stays passive, bit for bit

- **Undeclared worlds (D148).**
  - With no cohort the record is zero-size, and a static branch keeps it out of the segment, as `if trace:` keeps the
    trace's updates out at T = 0. So the program is unchanged.
  - crossrev and G1 check the worlds they hold at the gate, and crossrev is renewed at the landing. But crossrev's
    sets hold no world of this operator today.
  - **So the landing reruns FR-43 part 3's evidence,** as part 3's own landing did (`nochange-*` under
    `/mnt/workspaces/Cells/fr43-part3-20261123/`): the 11 engine traces (`compare.py run`) and `statistics.py run`.
    Every event must match exactly, and `verdict.json` and `statistics.json` must be byte-identical to
    `evidence-52935908`'s.
  - **One integer-unit world joins G1 and crossrev at the landing** (Q4, D371; P3, D375): the qualification world of
    §3, with its cohorts declared. It carries the operator's regression from then on, its jaxprs and bindings in
    crossrev (`scripts/gates/crossrev_sets.py`) and its saved fields in G1. Both records are renewed with it.
  - **What that world guards, and what it does not.** It guards the program with the record. The program without one,
    which every existing world of the operator runs, is in neither set. Its values are tied to the declared world's by
    the twins wherever tier 2 runs, and to FR-43 part 3's recorded evidence by the landing's rerun. A change in its
    compiled form that leaves the twins' values unchanged would not be caught at a later gate.
  - **No judge erratum.** Part 3's judge reads named fields only (`integer_events` and the trace), and its worlds
    declare no cohort, so its verdict cannot see the new field. FR-49's judge is different: it compares an exact set
    of extra fields, which is why the router's zero-size field needs FR-49's erratum 2 (D364).
- **Declared worlds.**
  - No rate, validity check, ledger, heat or draw reads the record.
  - Its update reads the counts before the event, the chosen channel and the event's time, formed as the trace forms
    it.
  - So the physics could move only through compilation: fusion or FMA contraction. The precedents are D148's first
    case, where XLA summed one quantity in two orders, and `species_sums`' FMA note.
- **The twins prove it.** The twins are the same world, observed and unobserved, at equal T. Each runs in a fresh
  process, scalar and through `run_batch`. Every field except the record must be bit for bit: counts, events, channel
  events, hazard, threshold, clocks, the trace, transfers, heat and magnitudes, and every composite field, observation
  column, diagnostic and ledger accumulator. The comparison takes the form of the labels' `same_physics`
  (`test_neutral_arrival_labels.py`).
- **An observation never stops a run.** The record is not in `own_valid`. Its domain (finite, ≥ 0, summing to n within
  the bound) is the readout's.
- **If a twin ever differs:**
  - first, the record's inputs pass through `jax.lax.optimization_barrier`, as `species_sums` does, and the twins are
    rerun. A barrier is not free: in D148 one changed a derivative program;
  - second, the arithmetic moves after the event loop and reads the half-step's own list of events.

### 2.3 The identity map and the exact update (S)

**The declaration.** `cohorts` is optional: omission is the only spelling of none, and an empty list is refused, as for
`factors` and `block` (D371). Each cohort is `{id, site, states, window_s}`, with `carries` optional in the same way. A
cohort whose channels all resolve by the rule below has no `carries`, and one that leaves a choice declares it:

```json
{"id": "tetramers", "site": "site_0", "states": ["dimer", "tetramer"], "window_s": [1.0, 2.0]}
```

```json
{"id": "heterotetramers", "site": "site_0", "states": ["dimer_a", "dimer_b", "tetramer"],
 "carries": [{"channel": "join", "pairs": [["dimer_a", "tetramer"]]},
             {"channel": "cut", "pairs": [["tetramer", "dimer_a"]]}],
 "window_s": [1.0, 2.0]}
```

- `states` is the identity class C: which states are the same unit's forms.
- A pair [a, b] says that one consumed unit of state a gives its identity to one produced unit of state b.
- An entry is for a channel with two or more legal pairings, and it holds exactly min(R, P) pairs (below).

**How many identities go on.** R and P are the class units a channel consumes and makes: the sums, over the states in
`states`, of its declared reactants and products. No class state is on both sides of a channel (refused, §2.6).
- **R = 0 or P = 0:** none. With R = 0 and P ≥ 1 the channel assembles into the class, and every class product is new.
  With R ≥ 1 and P = 0 it disassembles out of it, and every class reactant is lost. With R = P = 0 it is not the
  cohort's.
- **R ≥ 1 and P ≥ 1:** exactly min(R, P), as many as the channel can (accepted by the lead, D376). The reactants
  left over are lost, and the products left over are new, at the label of the event's time.
  - Where R ≥ P every class product takes one consumed unit's identity, so a partial-assembly step never counts a unit
    as new (D371).
  - Where P > R every consumed identity goes on in one product, and the rest are new. A split of one unit into k adds
    k − 1 units to that label (D375).

**Which state gives its identity to which: the pairing.** It is a table m_ab of whole numbers, the identities going from
consumed state a to produced state b, with at most r_a out of each a, at most p_b into each b, and min(R, P) in all.
- **A channel with exactly one legal table resolves by rule.** Nothing is declared, and declaring it is refused by name
  ("resolved by rule; omit it"), since one meaning has one spelling, as for the empty `cohorts` list (the lead, D376).
  P1's one-for-one step is its case R = P = 1.
- **A channel with two or more legal tables needs an entry.** Undeclared, it is refused as ambiguous.

**How a reader tells them apart, from the declaration alone.** For each channel with R, P ≥ 1, count the class states on
each side (a state with coefficient 3 counts once). The table is unique when
- the consumed side has one class state and R ≥ P: then m_ab = p_b, each product taking its identity from that state; or
- the produced side has one class state and P ≥ R: then m_ab = r_a, each consumed identity going on in that state.

Every other channel with R, P ≥ 1 has two or more legal tables. Row F's `join` (two consumed states, one product) and
`cut` (one consumed state, two products) are such channels. The desk counted the tables of 1,296 small channels (up
to three class states a side, coefficients 1 to 3, at most 7 units a side) by brute force, and the test agreed with all
of them (S).

**Why pairs at the level of states suffice.** Units of one state are exchangeable, so it does not matter which consumed
unit of state a carries. Each has the same expected labels, its state's share s_a = E_a/n_a. So where a merge's units
are all of one class state, its product carries that state's common share, the only rule symmetric in them. Where they
are of several states, the declared table says whose identity goes on (row F).

**Splits make a new unit (the user, D375).** Each consumed unit gives its identity to at most one product, and each
product takes at most one identity (the pair limits of §2.6).
- **`initial` is a survival count.** Summed over the class it never rises: a carry only moves it between states, and a
  loss removes it. One state's `initial` can still rise: in row D, A's goes from 1 to 3/2 as an initial I activates.
- **A split adds to newly assembled.** D375 refines D371's sentence: a partial-assembly step does not count a unit as
  new, but a split does create one.
- **The round trip** (row C′, §3). From two initial dimers, 2D → T and then T → 2D inside the window end at one initial
  dimer and one new one.
- **The reading not taken:** a split that copies its identity to both halves, so that no partial step counts a unit as
  new. The class's `initial` would then rise at a split and read as descent, not survival. Its frozen values stay in
  §3, labelled not taken, as the copying plant. Its declaration is refused at parse: as "resolved by rule; omit it"
  where the channel needs no entry, and as more pairs than its reactant can give where it does (§2.6).

**The exact update at an event.** n_k is state k's count just before the event, r_k and p_k are the channel's
stoichiometry, m_ab is its table (resolved by rule or declared), and λ is the label of the event's time:
1. s_k,l = E_k,l / n_k for each consumed class state k;
2. E_k,l ← E_k,l (n_k − r_k)/n_k;
3. E_b,l ← E_b,l + Σ_a m_ab s_a,l;
4. E_b,λ ← E_b,λ + p_b − Σ_a m_ab.

**Why it is exact, and what follows:**
- **Exactness.** Each state's consumed units are a uniform subset, independently across states, and a carried unit is
  one of them. So by linearity, E_k,l is each label's expected count conditional on the recorded events.
- **No class state is on both sides** (refused, Q3). So steps 2 to 4 touch disjoint states, and their order does not
  matter.
- **Step 2 is multiplicative,** so an emptied state holds an exact 0, also in binary64. Step 3 reads the shares from
  before the loss.
- **Each state's labels sum to n_k:** step 2 removes r_k, and steps 3 and 4 add p_b.
- **With C a single state,** the update is E ← E (n − d)/n, and D339's row gives 2/3 and 1/3.

**Multi-unit events.** The update reads the event's declared stoichiometry, so an event that moves several units moves
them once. Removing 2 of 3 gives E/3, as removing one and then another does. A reader that takes every event as one
unit gives E·2/3, a total of 2 against the engine's 1, and fails integrity.

**The time.** The label rule compares [start, end) with the time the trace records for the event: the operator's
compensated clock at the half-step's start, plus the offset inside it.
- FR-42's label windows resolve on the step grid (`same_instant`), because their arrivals are continuous.
- An event has its own time, so no grid rule is needed.

**The binary64 record's rounding bound** (corrected at 128eea12: the earlier form, 8 K u N, counted three roundings
per event where an entry can take seven).
- **The form,** in the class's state order: s = fl(E/n), then fl(fl(E (n − r))/n) for a loss, fl(E + fl(m s)) for each
  carry, and fl(E + a) for an arrival.
- **The bound:** every entry is within 8 (K + 1) u N of its exact value, and each state's labels, summed in binary64,
  are within 8 (K + 1) u N of n_k.
  - K is the site's events so far, and u = 2⁻⁵³.
  - N is the most class units the site can hold: its subunits over the smallest weight in the class.
- **Why:**
  - every quantity is non-negative, and the update never subtracts, since a loss multiplies by (n − r)/n. So a value's
    relative error is at most the largest among those it is formed from, plus one rounding per operation;
  - one event puts at most 7 roundings on any path to an entry: a carried term has 2 (the share and the product), and
    its state takes at most 5 additions, since a state's products are at most `MAX_ORDER` = 4 and its arrival is one
    more. A loss has 2;
  - so after K events an entry's relative error is at most 7 K u to first order, and the sum of the four labels adds at
    most 3 u n_k. Since 7 K + 3 ≤ 8 (K + 1), the constant leaves K + 5 in hand, more than the O(K² u²) remainder at any
    K below 10¹².
- **For the frozen rows** (§3), N = 3 and the total's bound is 24 (K + 1) u: 72 u for rows B and C′, 120 u for row A's
  two-unit form and for rows C and D, and 144 u for row A's one-unit form. Row F has N = 4, so its bound is 160 u, and
  row G has N = 8, so its bound is 320 u. The author's desk run of this form in binary64 meets every frozen fraction, at
  every row, within 1 u.
- **The desk stress (S):** 1,500 random declared maps, 65,005 events, with up to four carries into one state. The worst
  entry error was 0.23 K u N and the worst summed total 0.33 K u N, with no violation.
- **Beyond the bound,** the readout returns unresolved.

**Integrity:**
- **The reference rebuilds each state's count** from the trace and the declared stoichiometry.
  - It indexes by position against the site's own population in the summary, since the run view pads channels and
    states by the first population's names.
  - It resolves the map's rule from the declaration on its own, so a wrong resolution in the operator shows as a
    disagreement.
  - Each rebuilt count must equal the saved `integer_counts` at every row, exactly.
  - A mismatch, or a row past the trace's capacity (`integer_events` > T), is unresolved, never 0 or ∞, as for the
    cohort readers (`test_the_cohort_readers_fail_closed`).
- **The record's labels** must sum to each class state's saved count within the bound.

### 2.4 How restart and checkpoints carry it

- **(a) As owned state (recommended).**
  - Checkpoints carry the record like every owned field, in process as C3.6 shows.
  - Through a snapshot it should travel by the generic owned-state I/O. **To verify at the build.**
  - The window's edges and the pairs are layout constants, so a cut inside the window needs nothing more.
  - `initial` stays the units at t = 0. A resume never takes it again.
- **(b) Rebuilt from the trace at a resume.** Refused: the trace's capacity is limited, and a rebuild is a second code
  path.
- **Old checkpoints of this operator** lack the field, so they are expected not to load at the new head. **To verify
  at the build.** Pre-alpha, they are reproduced at their tags.

### 2.5 How it composes with labels and washes

- **Labels.**
  - The record is FR-42's share rule in count form: a uniform loss leaves the shares unchanged, arrivals join the label
    in force, and windows are half-open. A carry moves a share between states of one class.
  - It sits on unit states, not species rows, so it shares nothing with the label owner.
  - `check_writers`' refusal of a label owner stays. Lifting it needs the operator to report its transfers' one-way
    parts, in FR-42 stage 2's form. That is a separate extension, which FR-52 neither needs nor blocks.
- **Washes.**
  - The wash refuses the operator today, and `liquid_routing@1` takes the wash over (D362).
  - A wash or a routed portion moves liquid, never units, so the record needs no rule there.
  - Admitting the operator beside the router is the router's question, not FR-52's: the router must read the
    operator's transfers across a routed surface.

### 2.6 The refusals

Version 1 refuses each of these by name, with one row each:
1. **A malformed cohort:**
   - an unknown site, state or channel;
   - a repeated ID, or empty `states`;
   - a window other than a finite 0 ≤ start < end;
   - an empty `cohorts` or `carries` list (omit it for none, D371, as for `factors` and `block`).
2. **An incomplete map:**
   - an entry with fewer than min(R, P) pairs;
   - a conducting state outside the class, since the cohort would then miss units that carry transport, and the
     sum-to-flux check would not close.
3. **An ambiguous or repeated map:**
   - a channel with two or more legal pairings and no entry: "ambiguous: declare its pairs";
   - an entry for a channel whose pairing is unique, R = 0 or P = 0 included: "resolved by rule; omit it";
   - an entry given twice for one channel;
   - a pair naming a state outside the class, or one that the channel neither consumes nor makes;
   - more pairs into a state than the channel makes of it;
   - more pairs from a state than the channel consumes of it, which would copy an identity (D375).
4. **A class state on both sides of a channel** (Q3, D371). The net and gross readings then give different counts with
   the same total: from two initial units, `{active: 2} → {active: 1, free: 2}` gives (initial, inside) = (1, 0) net and
   (0, 1) gross. Integrity cannot tell them apart.
5. **A map that crosses a division:** a site that divides or is born. That is a parent or daughter of a site map, or a
   site whose cell's lifetime is bounded. `divide()` moves counts with no event, so nothing could follow them.

At readout, a failed integrity check is unresolved (§2.3).

**What no refusal can catch.** `states: ["open"]` in a closed/open population parses, and reads as residence: a
reopened unit is new. No parse rule can tell it from row D's F → I, where the outside state is the pool a unit is made
from. So leaving no form of the unit out is the declaration's to get right, and the library page says so.

## 3. Acceptance cases with controls, and the frozen values

**These fractions are frozen at this note's commit, before the build.**
- The builder's rows must reproduce them, and may not edit them. A change needs an erratum to this note.
- Each was found twice at the desk, by the update by hand and by enumerating every equally likely choice of consumed
  and carried units over labelled units (S). The engine's binary64 record must meet each within 8 (K + 1) u N (§2.3).
- The fractions have not changed since the note first froze them (ed0bd135). The rounding bound's form and constants
  were corrected at 128eea12, before the build.
- The lead's ruling on resolution by rule (D376) changed which channels are declared, not any value. Rows F and G are
  new with the lead's rulings, G after D376.
- The window is [1, 2) s throughout. No event falls before it, so the `before` label stays 0, and the tables omit it.
  Rows A, B and D also omit `after`, which stays 0 there.

**A. FR-52's table.** C is {X}, with X of 2 subunits and free subunits of 1, and arrivals at 1.5 s. The last two
columns give (initial, inside) under the two mutants.

| Event at the site | n_X | initial | inside | Oldest-first | Newest-first |
| --- | ---: | ---: | ---: | ---: | ---: |
| Start with two units | 2 | 2 | 0 | (2, 0) | (2, 0) |
| One assembles inside the window | 3 | 2 | 1 | (2, 1) | (2, 1) |
| One disassembles, uniform over the three | 2 | 4/3 | 2/3 | (1, 1) | (2, 0) |
| Both remaining disassemble | 0 | 0 | 0 | (0, 0) | (0, 0) |
| One more assembles inside the window | 1 | 0 | 1 | (0, 1) | (0, 1) |

- **The control:** enumerated, the three equally likely removals give (1, 1) twice and (2, 0) once, a mean of
  (4/3, 2/3).
- **The mutants** conserve the totals and fail row 3 in exact rationals.
- **Row 4 runs two ways:** as one two-unit event and as two one-unit events. Both give exact zeros, in binary64 too.
- **The flux:** at a declared Δc, Σ_l g E_l Δc = g n Δc on every row.

**B. D339's row.** C is {X}. Start at (initial, inside) = (2, 1); one event removes two.

| | n_X | initial | inside |
| --- | ---: | ---: | ---: |
| Before | 3 | 2 | 1 |
| After | 1 | 2/3 | 1/3 |
| The one-unit mutant | 2 (the engine's: 1) | 4/3 | 2/3 |

- **The control:** the three equally likely pairs give (0, 1), (1, 0) and (1, 0).
- **The mutant** fails integrity: its total is 2, against the engine's 1.
- **Truncation:** over a trace whose capacity ends before the removal, the reference is unresolved from that row on. The
  record has no capacity, so it is unaffected.

**C. A dimer-to-tetramer chain.**
- **The population:** free subunits F (1 subunit), dimers D (2) and tetramers T (4); C is {D, T}.
- **The channels:**
  - 2F → D, an assembly;
  - D → 2F, a loss;
  - 2D → T and T → 2D, both resolved by rule: in the split one half keeps the identity, and the other is new.
- **The start:** two initial dimers and two free subunits.

| Event (time) | n_D | n_T | D: initial, inside, after | T: initial, inside, after |
| --- | ---: | ---: | --- | --- |
| Start | 2 | 0 | 2, 0, 0 | 0, 0, 0 |
| 2F → D (1.5 s) | 3 | 0 | 2, 1, 0 | 0, 0, 0 |
| 2D → T (1.6 s) | 1 | 1 | 2/3, 1/3, 0 | 2/3, 1/3, 0 |
| T → 2D (2.5 s) | 3 | 0 | 4/3, 2/3, 1 | 0, 0, 0 |
| D → 2F (3.0 s) | 2 | 0 | 8/9, 4/9, 2/3 | 0, 0, 0 |

- **The control:** the enumeration over the three equally likely pairs of dimers, and the carried one of each pair,
  gives every row above.
- **The merge read as new,** a kernel or reader mutant that drops the merge's pair: T after the merge is (0, 1, 0),
  against (2/3, 1/3, 0). The totals are unchanged, so only the fractions catch it.
- **A merge carrying both identities:** T's total is 2 against 1, so integrity fails.
- **The shares read after the loss:** the split reads 0/0 at the emptied tetramer state.

**The reading not taken** (a split copies its identity to both halves; refused at parse). It stays frozen as the copying
plant: row C's start and merge, then

| Event (time), not taken | n_D | n_T | D: initial, inside, after | T: initial, inside, after |
| --- | ---: | ---: | --- | --- |
| T → 2D (2.5 s) | 3 | 0 | 2, 1, 0 | 0, 0, 0 |
| D → 2F (3.0 s) | 2 | 0 | 4/3, 2/3, 0 | 0, 0, 0 |

The totals agree with the rule's, and only the fractions tell them apart. So a copying record fails rows C4 and C5.

**C′. The round trip** (D375's example). The population is row C's, and its channels resolve by rule. From two initial
dimers, 2D → T at 1.6 s and then T → 2D at 1.8 s, both inside the window:

| Reading | n_D | D: initial, inside |
| --- | ---: | --- |
| The rule: a split makes a new unit | 2 | 1, 1 |
| Not taken: a split copies its identity | 2 | 2, 0 |

Under the rule the split adds one to FR-52's newly assembled count, and the round trip ends at one initial and one new,
as D375 says. The not-taken reading returns the start, and is the copying plant's value.

**D. A single-subunit activation.**
- **The population:** free F, inactive I and active A, each of 1 subunit; C is {I, A}, and only A conducts.
- **The channels:**
  - F → I, an assembly;
  - I → F, a loss;
  - I → A and A → I, each resolved by rule (one for one, P1).
- **The start:** one initial I, one initial A and one F.

| Event (time) | n_I | n_A | I: initial, inside | A: initial, inside |
| --- | ---: | ---: | --- | --- |
| Start | 1 | 1 | 1, 0 | 1, 0 |
| F → I (1.5 s) | 2 | 1 | 1, 1 | 1, 0 |
| I → A (2.5 s) | 1 | 2 | 1/2, 1/2 | 3/2, 1/2 |
| A → I (3.0 s) | 2 | 1 | 5/4, 3/4 | 3/4, 1/4 |
| I → F (3.5 s) | 1 | 1 | 5/8, 3/8 | 3/4, 1/4 |

- **The control:** the enumeration gives every row.
- **The residence mutant** (C = {A}, so an activation counts as new): after I → A, A holds 1 initial and 1 after,
  against 3/2 initial and 1/2 inside. The totals are unchanged.
- **FR-52's quantities at the end:**
  - A's `initial`, 3/4, is the original units still conducting;
  - the class's `inside`, 3/8 + 1/4 = 5/8, is the units formed in the window.

**E. A restart** (compiled, §5.3).
- The qualification world is cut inside the window, between events, and resumed with the same seed.
- Every field, the record included, must be bit for bit the uninterrupted run's.
- **The plants**, each of which must be caught:
  - the record set at the cut to its start values, as if `initial` were taken at the resume;
  - the record zeroed.

**F. A declared map: a heterotetramer.** Its `join` and `cut` need a declared entry (the qualification world's hetero
population holds the same two).
- **The population:** free F (1 subunit), dimers D_a and D_b (2) and tetramers T (4), at 8 subunits; C is {D_a, D_b, T}.
- **The channels:** 2F → D_a, 2F → D_b and their losses; `join`, D_a + D_b → T; `cut`, T → D_a + D_b.
- **The declared pairs:** join [dimer_a, tetramer], cut [tetramer, dimer_a]. Each channel has two legal tables: either
  dimer can give `join` its identity, and either half can keep it in `cut`.
- **The start:** two initial D_a and one initial D_b.

| Event (time) | n_Da | n_Db | n_T | D_a: initial, inside, after | D_b: initial, inside, after | T: initial, inside, after |
| --- | ---: | ---: | ---: | --- | --- | --- |
| Start | 2 | 1 | 0 | 2, 0, 0 | 1, 0, 0 | 0, 0, 0 |
| 2F → D_b (1.5 s) | 2 | 2 | 0 | 2, 0, 0 | 1, 1, 0 | 0, 0, 0 |
| join (1.6 s) | 1 | 1 | 1 | 1, 0, 0 | 1/2, 1/2, 0 | 1, 0, 0 |
| cut (2.5 s) | 2 | 2 | 0 | 2, 0, 0 | 1/2, 1/2, 1 | 0, 0, 0 |
| D_b → 2F (3.0 s) | 2 | 1 | 0 | 2, 0, 0 | 1/4, 1/4, 1/2 | 0, 0, 0 |

- **The control:** the enumeration gives every row, with each pair's unit uniform among those consumed.
- **A wrong pair in `join`,** [dimer_b, tetramer], which is legal too: T after the join is (1/2, 1/2, 0), against
  (1, 0, 0), and D_a after the cut is (3/2, 1/2, 0), against (2, 0, 0).
- **A wrong pair in `cut`,** [tetramer, dimer_b]: after the cut D_a is (1, 0, 1), against (2, 0, 0), and D_b is
  (3/2, 1/2, 0), against (1/2, 1/2, 1).
- **The totals are unchanged in both,** so only the fractions catch them. The parse cannot, since both tables are legal.
  That is why the declaration is required, and why the test holds the fractions.
- **The binding is checked on the host:** each channel's layout table equals the declared pairs here, and the rule's
  in the other rows. The compiled qualification world declares the same pairs (below), so its step reads a declared
  table too.

**G. A two-pair table: two closed tetramers opening together** (`open2`, 2T_c → 2T_o). Resolved by rule with m = 2.
- **The population:** free F (1 subunit), dimers D (2), closed tetramers T_c (4) and open tetramers T_o (4), at 16
  subunits; C is {D, T_c, T_o}. The channel has R = P = 2 and one class state a side, so it is not declared.
- **The start:** one D and three T_c, all initial, and F = 2.

| Event (time) | n_D | n_Tc | n_To | D: initial, inside, after | T_c: initial, inside, after | T_o: initial, inside, after |
| --- | ---: | ---: | ---: | --- | --- | --- |
| Start | 1 | 3 | 0 | 1, 0, 0 | 3, 0, 0 | 0, 0, 0 |
| 2F → D (1.5 s) | 2 | 3 | 0 | 1, 1, 0 | 3, 0, 0 | 0, 0, 0 |
| 2D → T_c (1.6 s) | 0 | 4 | 0 | 0, 0, 0 | 7/2, 1/2, 0 | 0, 0, 0 |
| `open2` (2.5 s) | 0 | 2 | 2 | 0, 0, 0 | 7/4, 1/4, 0 | 7/4, 1/4, 0 |
| T_c → T_o (3.0 s) | 0 | 1 | 3 | 0, 0, 0 | 7/8, 1/8, 0 | 21/8, 3/8, 0 |

- **The control:** the enumeration gives every row, with each pair's unit a distinct consumed one, and the update rule
  gives the same.
- **The one-pair plant** (an update that applies at most one pair per channel): at `open2` T_o is (7/8, 1/8, 1), against
  (7/4, 1/4, 0), since the second product counts as new. The totals agree, so only the fractions catch it.
- **Its bound** is 320 u (K = 4, N = 8). The desk run meets every fraction exactly.

**Which channels need a `carries` entry.** Only `join` and `cut`, in row F and in the qualification world's hetero
population. A reader counts R, P and the class states per side (§2.3):

| Row | Channel | R, P | Class states consumed, produced | Reading |
| --- | --- | --- | --- | --- |
| A, B, C, C′, D, F, G, the qualification world | Assembly from, and loss to, free subunits | R = 0 or P = 0 | – | Resolved: nothing goes on |
| C, C′, G, the qualification world | 2D → T, 2D → T_c | 2, 1 | 1, 1 | Resolved: R ≥ P and one consumed state |
| C, C′, the qualification world | T → 2D, T_c → 2D | 1, 2 | 1, 1 | Resolved: P ≥ R and one produced state |
| D, G, the qualification world | I ⇄ A, T_c ⇄ T_o | 1, 1 | 1, 1 | Resolved: one for one (P1) |
| G, the qualification world | 2T_c → 2T_o (`open2`) | 2, 2 | 1, 1 | Resolved: one class state a side, m = 2 |
| F | D_a + D_b → T (`join`) | 2, 1 | 2, 1 | Needs an entry: two legal tables |
| F | T → D_a + D_b (`cut`) | 1, 2 | 1, 2 | Needs an entry: two legal tables |

Declaring a pairing for any resolved channel is refused, so rows A, B, C, C′, D and G and the qualification world's homo
population have no `carries`. Its hetero population has row F's `join` and `cut`, and the same two entries.

**Further controls:**
- **Ties:** an arrival at exactly `start` joins `inside`, and one at exactly `end` joins `after`. The plants are a
  closed end and an open start.
- **No event:** a site with no event keeps its start values bit for bit.
- **The unobserved twin** (§2.2).
- **The host update test** (the lead, after D376): the kernel's update equals the exact mean, enumerated over
  individually labelled units, on
  - the explicit channels 2X → 2Z (m = 2), X + Y → 2Z (two states in, one out, such as D_a + D_b → 2D_c), 2X + Y → 3Z
    (m = 2 and 1) and 2T_c → 2T_o, from starts holding several labels;
  - random small channels: two to four states, coefficients 1 to 3, up to six pairs, from random starts.
  - **Its teeth:** a planted update that applies at most one pair per channel must fail it. The test asserts that it
    fails on each explicit channel, so a build that handled one pair per channel cannot pass. At the desk (S) the rule
    agreed with the enumeration on all 1,313 random tables. The plant differed on 721 of the 760 that hold two or more
    pairs, and on every explicit channel.

**The qualification world (S), grown with row F's population (the lead, after D376).** Two populations sit on one
cell's patch, each with one site, so one compile runs both kinds of table.
- **The homo population** (site_0) is row G's: free F (1 subunit), dimers D (2), closed tetramers T_c (4) and open
  tetramers T_o (4), at 16 subunits from row G's start. Its channels are 2F ⇄ D, 2D ⇄ T_c, T_c ⇄ T_o and `open2`
  (2T_c → 2T_o), and its transfer conducts through T_o only. At 8 subunits `open2` could only take both T_c.
- **The hetero population** (site_1) is row F's: free F (1), D_a and D_b (2) and T (4), at 8 subunits, with 2F ⇄ D_a,
  2F ⇄ D_b, `join` and `cut`. It has no transfer, so it moves nothing (as C3.3's many-site world has none). **To verify
  at the build:** two populations in one declaration, which no world so far has compiled. If it is not supported, the
  fallback is one population of seven states, or the host row (row F), and the landing text reports which.
- **Why two populations:** a cohort may leave out no conducting state of its population (§2.6), and the homo's T_o
  conducts, so the two classes cannot be two cohorts of one population. The alternative is one population of seven
  states under one cohort. Two populations also run two cohorts, at two sites, in one program.
- **The channels' rates** are constant and read nothing, so the event times are exact and the two sites never meet.
- **Two cohorts:** the homo's C is {D, T_c, T_o}, with no `carries`, since every channel resolves by rule. The hetero's
  C is {D_a, D_b, T}, with row F's two `carries` entries. The tables reach the compiled step through the one layout
  array, so the compiled program, and with it the G1 and crossrev world, runs a declared table.
- **The run:** both windows inside it, complete traces and a row every step.
- **The seed** is chosen so that the run holds at least, in the homo, one merge, one split, one opening, one closing,
  one `open2`, one assembly inside the window and one loss after it; and in the hetero, one `join`, one `cut` and one
  loss of a D_b after its window. The test asserts all ten.
- **How many pairs the tables hold.** Of the thirteen channels, `open2` alone carries two or more pairs (R = P = 2,
  m = 2, by rule). Every other, including row F's declared `join` and `cut`, has min(R, P) ≤ 1. So the compiled program
  runs one two-pair table, and no table with two carries from different states into one state, which is the host update
  test's (§5.5).

**In the compiled run:**
- for both cohorts, the record agrees with the reference's exact means, within the bound, at every row;
- each rebuilt count equals the saved one exactly;
- **sum-to-flux, with teeth (S):**
  - over every event-free step of the homo's site, Σ_l g E_T_o,l I must equal the booked change of
    `integer_transferred_fmol` (the hetero has no conducting state, so its contribution is zero);
  - I = u0 (1 − e^(−λ dt))/λ is the closed-form integral of the driving difference over the step. u0 is the difference
    at the step's start and λ = G (1/V_c + 1/V_o), both from the start row's pools and counts;
  - the tolerance is the record's bound times g I, plus c ε |ΔQ| for the rounding of the two closed forms, where ΔQ is
    the booked change and c is fixed in the build;
  - it fails for a record whose total drifts, and for a conductance put on the wrong state or route;
  - shares of the booked transfer would sum to it by construction, which is why the check does not use them.

## 4. IDs under the rename (D345, D346, D371)

The rename's family words are decided (D371). The build comes after the rename lands.

| Today | Under the rename | Here |
| --- | --- | --- |
| `integer_unit_population@1` | `cells.operator.integer_unit_population@1` | It owns the record, widened in place at @1 (Q5) |
| `located_events_exact_transfer_half_steps@1` | The rename's mapping | The step. Its event rule does not change |
| `resolved_pump_composite@1`, `resolved_pump_tissue@3` | `cells.model.…` | The host and its inner model |
| `neutral_arrival_labels@1`, `scheduled_compartment_wash@1`, `isopotential_partition@1` | `cells.operator.…@1` | Refused beside it, as today |

- **No new ID.** The record is a field, the kernel a numerics module and the readout a function. Field and axis names
  are not IDs.

## 5. The qualification plan

### 5.1 The cheapest proof of each claim

| Claim | Proof |
| --- | --- |
| The update is the exact conditional expectation | The frozen rows A to D, F and G, and the ties, against the enumerated distribution in rationals |
| The map reads chains, activation and a declared pairing | Rows C, C′, D and F, and their mutants; a host check that the bound tables equal the reader's |
| The reader's test of a unique table is right | A host test against brute-force counts of the legal tables, over small channels |
| Multi-unit events are read exactly | Row B and its mutant; the compiled world's merges and splits |
| The update with several pairs in a channel | The host update test and its planted update; row G (`open2`, m = 2); the compiled world's `open2` |
| The labels partition each state's count | Σ = n exactly in the rows, and within the bound at every compiled row |
| Integrity | The reference's rebuilt counts against the saved ones, exactly, at every compiled row |
| Sum-to-flux | The compiled world's event-free steps, against the booked transfer |
| Passive where declared | The twins (§2.2): scalar and in process in tier 2; in fresh processes, scalar and batch, once at the landing |
| Passive where undeclared | crossrev and G1 at the gate (D148); FR-43 part 3's 11 traces and statistics rerun against `evidence-52935908` (§2.2) |
| Regression from then on | The qualification world, with its cohorts declared, in G1 and crossrev (Q4, P3) |
| Restart | Case E, with its two plants |
| The refusals | One row each in the existing `REFUSALS` and `DIVISION_REFUSALS` |

### 5.2 Planted errors

| Plant | It fails |
| --- | --- |
| One unit per event | Integrity, in row B |
| Oldest-first or newest-first removal | Row A3, exactly |
| n read after the event | Rows A3 and B |
| The merge read as new | Row C3 |
| A split that copies its identity to both halves (the reading not taken) | Rows C4, C5 and C′, against their frozen values |
| A merge carrying both identities | Integrity, in row C3 |
| An update that applies at most one pair per channel | The host update test on each explicit channel; row G at `open2`; the compiled world's `open2` |
| A wrong pair: [dimer_b, tetramer] in `join`, or [tetramer, dimer_b] in `cut` | Row F3 or F4; the totals agree, so only the fractions tell |
| The shares read after the loss | Row C4 (0/0) |
| The residence reading of an activation | Row D3 |
| An arrival added to two labels | The partition and sum-to-flux |
| A closed end; an open start | The tie rows |
| The record re-initialised or zeroed at a resume | Case E |
| A relative drift of 10⁻¹² per event | The record's bound |

### 5.3 Test cost (D224)

| File | Change | Seconds | Reason |
| --- | --- | --- | --- |
| `test_integer_unit_population.py` (tier 2, 35.5 s) | The frozen rows A to D, F and G, the ties and the plants; the resolution test against brute force; the update test against enumeration (desk: about 0.5 s); the refusal rows, among them "resolved by rule; omit it" and "ambiguous: declare its pairs" | +3 | NumPy and parsing only |
| **New** `test_integer_unit_cohorts.py` (tier 2) | Two compiles, the qualification world observed and its unobserved twin, and one in-process resume of the first | About 65–75, priced from the existing file's one compile and resume of a two-state world. To measure at the build for two populations, of four states and seven channels and of four states and six. If the grown world would exceed the 90 s cap, the hetero population stays a host row (row F), and the landing text says so | The record's only compiled path, the twins and the restart. The existing file has no room under the 90 s cap |

- **G1 and crossrev** gain the qualification world at the landing (Q4). In every later gate that costs about one
  compile and run in G1, priced at 30–40 s from the existing file's two-state world (the grown world's is measured at
  the build), and one set of jaxprs and bindings in crossrev.
- **The batch and fresh-process twins,** and the rerun of FR-43 part 3's evidence (§2.2), run once at the landing.
  They run as a detached job with its inputs and results under `/mnt/workspaces/Cells`, and are not a tier file.
- **To verify at the build:** a trace with T > 0 through `run_batch`. C3.5 reads owned fields through it only at T = 0.
- **The guard set** gains A7's frozen-list entries for any new sum in the operator, at no test cost.
- **The tiers** are re-measured after the landing, and at the build the new file is measured against the 90 s cap.

### 5.4 No registered comparison

- **The claims are exact identities,** decided in rationals, integers and bytes, with two derived rounding bounds: the
  record's and sum-to-flux's.
- **Nothing is compared** with a reference simulator or a wet-lab study.
- **The independence is in the frozen values.** They were enumerated over labelled units before any code, and the
  builder reproduces them.
- **An experiment** that uses a cohort for a scientific claim registers it in its own protocol.

### 5.5 What is not exercised

- **The declared path in the compiled program, only if the grown world would exceed the 90 s cap** (§5.3). The
  heterotetramer then stays row F, on the host, and the landing text says so. This is the one piece that nothing would
  exercise.
- **Two carries from different states into one state in one event, in the compiled program.** No channel there has them.
  The host update test covers the path (D_a + D_b → 2D_c among its channels).
- **Ties at a window's edge,** which only the host rows run.

Tables of two or more pairs are exercised: in the compiled program by `open2` (row G), and on the host by row G, the
resolution test and the update test.

## 6. What is not claimed

- **A realization.** The record is an expectation given the events: it holds no variance and no sampled identities.
- **Biology's notion of identity.** The class and its carries are the declaration's: which states are one unit's
  forms, and which unit a merge or split continues.
  - A merge of units of one class state carries their state's common share, because they are exchangeable. A merge
    across states follows the declared table.
  - Exchangeability is the operator's law, one hazard per unit of a state. Real units may age, so a measured survival
    can differ. The observation describes the model.
- **A lineage reading of splits.** A split makes a new unit (D375): one half keeps the identity. Both halves keeping it
  would count descent, not survival, and is not what the record does.
- **Cohorts across a division,** and composition with labels, washes or the router. Each is refused or not composed.
- **That raising T leaves the physics bit for bit.** This is expected but not claimed, since the twins hold T fixed.
- **The GPU.** The composite is refused on a GPU in the vector path (D336), so the record is qualified on CPUs.
- **The assembly family's exact events.** The kernel could serve them, but nothing connects it to them.
- **Any change to FR-43's qualification.** Its judge needs no erratum, and its evidence is rerun at the landing
  (§2.2).

## 7. Decisions

Decided on 24 November 2026 (D371, D375 and D376, and the lead's rulings after D376 on the compiled world, the host
update test and row G). Nothing is left open, and the note is final.

| Question | Decision | By |
| --- | --- | --- |
| Q1. Where it lives | (a) The engine record kept at each event, with the trace reader in `validation/` as the independent check | The user |
| Q2. The scope | Chains now. Version 1 covers dimer-to-tetramer chains and single-subunit activation through a declared identity map across states (§2.3), in place of the two-state limit | The user |
| P2. Splits | A split makes a new unit. One half keeps the original identity, and the other counts as newly assembled, so `initial` stays a survival count (§2.3). The copying reading is not taken. Its frozen values stay in §3 as the copying plant | The user (D375) |
| Q3. A state on both sides | (a) A class state on both sides of a channel is refused in version 1. The library page states how returns are counted | The lead |
| P1. One-for-one steps | (a) A step with one tracked unit on each side keeps its identity with no declaration (§2.3) | The lead (D375) |
| How many identities go on | Exactly min(R, P). An entry holds that many pairs, so an empty list for a merge or split is refused: where the pairing is unique as "resolved by rule; omit it", else as incomplete | The lead (D376) |
| Unique pairings | A channel with one legal pairing resolves by rule and is not declared. Declaring it is refused ("resolved by rule; omit it"). Only a channel with two or more legal pairings is declared, and an undeclared one is refused as ambiguous (§2.3, §2.6). Row F tests the declared path | The lead (D376) |
| Several pairs in a channel | A host test of the update against enumeration, with a planted one-pair update that must fail it, and row G: `open2`, 2T_c → 2T_o, rule-resolved with m = 2, in the same compile and frozen before the build | The lead (after D376) |
| Q4. Routine tests | (a) The new tier-2 file, plus one integer-unit world in G1 and crossrev at the landing | The lead |
| P3. The world in G1 and crossrev | (a) The qualification world with its cohorts declared, grown with the heterotetramer's `join` and `cut` so that a declared table is compiled, and with `open2`, so that a table of two pairs is. Two populations, verified at the build, or a fallback reported (one of seven states, or the host row). What it does not guard is stated in §2.2, and what it does not exercise in §5.5 | The lead (D375; the growth, after D376) |
| Q5. The declaration and the ID | (a) `@1` widened in place, with `cohorts` optional: omission is the only spelling, and an empty list is refused | The lead |
| Independence | The enumerated fractions are frozen in this note before the build, with the binary64 record's bound stated against them (§2.3, §3) | The lead |

## 8. Price and order (S)

| Part | Agent-days |
| --- | --- |
| The kernel: the map's rule, the update with carries, the label rule, and its rows | 0.5 |
| The operator: the declaration with its map and refusals, layout, state, the update, run view, summary, batch signature and working sizes | 1.25–1.5 |
| The readout | 0.25 |
| The reference: the enumerated distribution with identities, the trace reader with integrity, and the qualification world | 0.5–0.75 |
| Tests: the frozen rows, the refusal rows and the new compiled file | 0.5–0.75 |
| The landing's evidence: the twins in fresh processes, scalar and batch, and FR-43 part 3's rerun | 0.25 |
| G1 and crossrev: the world added, both records renewed | 0.25 |
| Docs: the library page, with how returns are counted; the composition table; PROGRESS | 0.25 |
| The gate | 0.5 |
| **Total** | **4.25–5** |

The price was not re-estimated for the grown world, the update test or row G. The compile and run seconds are measured
at the build (§5.3).

**The order:**
1. This note, with its frozen values.
2. The build, after the rename lands.
3. The gate: tiers 1 and 2, the FR set and the proofs.
4. The landing's evidence, with the world added to G1 and crossrev.

## 9. Amendment for D400 (26 November 2026)

**Written** on branch `fr52-build` at main 69d2a36a, before any code, as the lead asked. The note above is c43f9a4a's,
unchanged. D400 landed a write-only trace field in `cells.operator.integer_unit_population@1`, `integer_trace_counts`,
holding the counts the event loop carries after each event (7f98d838, tag `fr43-trace-counts-landed-2026-11-26`). This
section supersedes the sentences it quotes, and nothing else. Every decision of §7, every frozen value of §3 and the
record's rounding bound (§2.3) stand. **S** marks this section's own reading or proposal, as above. Two items wait for
the lead's ruling (§9.4 and §9.5).

### 9.1 The trace's size

- **§1's premise,** "T (2 + 2R) values per site (`working_size`)", becomes **T (2 + 2R + S)**. S is the operator's
  padded state axis, the most unit states of any of its populations (`dimensions`' K, not the K of §2.3's bound). A
  recorded event holds its time, its channel, the two pools on each route and the counts after it in each state.
  `working_size` is now 2 n ((2S + J + R + 7) + T (2 + 2R + S)).
- **§2.1's option B,** "an hour at one event per second holds 3,600 × 4 values per site in each row", now holds
  3,600 × (4 + S) values with one route: 3,600 × 8 for the qualification world's four states. B stays not taken
  (D371). Its capacity is unchanged, and its rows now grow faster.
- **The record's own size** does not change with D400. Its axes are [cohort, state, label], so it holds 4 S values per
  cohort in each row, with the states outside the class at 0. §2.1's "4 values per class state per cohort per row"
  counted the class only. Where a cohort is declared, `working_size` gains 2 · 4 S per cohort. Where none is, it gains
  nothing, since the record and its layout are zero-size: FR-43 part 3's worlds keep D400's row size (§9.6).

### 9.2 What the reference's trace reader finds

**Per recorded event the trace now holds** its time (`integer_trace_time_s`), its channel (`integer_trace_channel`),
the pools at it (`integer_trace_cell_fmol`, `integer_trace_node_fmol`) and the counts after it (`integer_trace_counts`
[site, slot, state], int64).
- **As the code reads at 69d2a36a** (`bind` and `_run_stage`):
  - an unrecorded slot holds −1 in its channel and in every state;
  - a recorded slot holds the counts the loop carries on after the event (`counts_new`), written as the loop forms
    them and never formed again from the declared jump;
  - in a population with fewer states than S, a recorded slot holds 0 in the padded states, not −1, since their
    initial counts and changes are 0. The reader's test checks this on the two-population world, the first world to
    compile two populations (§3).
- **The reference keeps rebuilding the counts** from the trace's channels and the declared stoichiometry (§2.3), so it
  stays independent of the engine's counts. It never seeds or steps its counts from `integer_trace_counts`. The n_k its
  exact update reads before each event are its own rebuilt counts.
- **The new integrity row (the lead):** at every recorded event, the reference's rebuilt counts after it equal the
  slot's `integer_trace_counts` exactly, in every state of the site's own population, with 0 in the padded states.
  Beside it:
  - the slots agree with the channels: a slot holds a channel ≥ 0 exactly when its counts are ≥ 0, and from
    `integer_events` up to T every slot holds −1 throughout;
  - §2.3's row stays: the rebuilt counts equal the saved `integer_counts` at every row, exactly;
  - a failure is unresolved, never 0 or ∞. A row past the trace's capacity is unresolved from there on (row B's
    truncation), since the trace's counts end with the trace.
- **What the row adds.** It places a wrong jump at its own event, and it catches what the row check cannot: two wrong
  jumps inside one row whose sum is the declared one. A wrong but balanced jump (D400's plant) fails both rows,
  because the reference rebuilds from the declaration. A reference seeded from the trace's counts would pass it, which
  is why the reference is not seeded (§9.8).
- **The record does not read the trace.** Its update reads the loop's counts before the event, the chosen channel's
  declared stoichiometry and the event's time (§2.2), so D400 changes nothing in it.

### 9.3 A zero-size leaf still changes the program

- **D400's finding.** An owned field of zero size is still a leaf. So the state layout and the program text change for
  every world of the operator, declared or not, and checkpoints saved before do not load. D400's pair check
  (`/mnt/workspaces/Cells/fr43-cowriters-build-20261126/trace-counts-dev/RESULT.md`, and the round's
  `d148-counts/ROUND.md`) found that dead-code elimination drops the leaf's input. In eight of its nine worlds the
  eliminated programs were then identical, apart from names and the loops' `ft_in` and `ft_out` annotations, which
  count a carried leaf. The ninth, the dividing world, is §9.5's.
- **So §2.2's** "With no cohort the record is zero-size, and a static branch keeps it out of the segment, as
  `if trace:` keeps the trace's updates out at T = 0. So the program is unchanged." **is withdrawn.** FR-52 adds one
  owned leaf (`integer_cohort_units`) and four layout leaves (`integer_cohort_site`, `integer_cohort_class`,
  `integer_cohort_pairs`, `integer_cohort_window_s`), each zero-size where no cohort is declared. There the values stay
  unchanged, not the text.
- **The build's form (S).** Where no cohort is declared, a static branch keeps the record out of the event loop's
  carry as well as out of the segment, so the loops' text and annotations stay as they are. The outer programs then
  differ only by the zero-size leaves they pass through. Where a cohort is declared, the loop carries the record.
- **The proof where undeclared** is D400's pair check, rerun with FR-52's base and head over the operator's worlds
  (D400's nine, the co-writer world among them): every existing field equal at every step, every common binding
  equal, and the programs compared after dead-code elimination as D400 compared them. The landing's rerun of FR-43
  part 3's evidence (§2.2, §9.6) stays.
- **What the landing renews,** besides adding the qualification world (§9.4). crossrev's `reactions_integer_source`
  will again differ in its four program texts and its bindings, so its files are renewed again, as at D400. G1's save
  of it gains the new field's arrays (its history and observations, zero-size), and the renewed save goes beside G1's
  record, as D400's did.
- **§2.4's old checkpoints.** D400 made the checkpoints before it unloadable, and FR-52 does the same to D400's. §2.4's
  expectation stands, now with that precedent.

### 9.4 crossrev and G1 already hold a world of this operator

- **§2.2's** "But crossrev's sets hold no world of this operator today." **is outdated.** Since D395 (the lead's L4),
  crossrev's reactions set holds the co-writer world `reactions_integer_source` (`source_world` in
  `validation/fr43_part3/worlds.py`), and G1 saves it through `crossrev-reactions`. It runs the operator with no
  cohort. No other world of the operator is in either set.
- **So §2.2's paragraph "What that world guards, and what it does not" changes.** The qualification world will guard
  the program with the record, and the co-writer world already guards the program without one, at every later gate.
  The undeclared programs of other compositions (several populations, a division, a trace of capacity 0) are in
  neither set. A change in their compiled form that leaves the twins' values unchanged would still pass a later gate.
- **Which set takes the qualification world (to rule).** The reactions set's `check` reads the reaction parameters
  (`PARAMETER_FIELDS`) of every world in the set and marks a world without them MISSING. So the qualification world,
  which has no reaction, cannot join that set as it stands.
  - **Proposed (S):** the `qualification` set of `validation/tissue/composite_crossrev.py` (`qualification_worlds`).
    It has no `check` action, and G1 reads it as `crossrev-qualification`. That is one world entry, with no change to
    the runner (`scripts/gates/crossrev_sets.py`) or to G1's sets.
  - **The alternatives:** a new set, in `crossrev_sets.py` and in G1's sets (`validation/results_baseline.py`), or
    the reactions set's `check` skipping the world by name.

### 9.5 The partition's finiteness check reads the record (to rule)

- **What D400's pair check found.** A dividing world's step gains a finiteness test of each new field. `event_map` in
  `cells.operator.isopotential_partition@1` (`operators/partition.py`) ands `isfinite` of every field of the
  composite's state into a division's validity (`for value in new`). For an int64 field the test is constant true.
- **For FR-52's record, a float, it is a real read.** It reads the record wherever a cohort is declared in a world that
  composes the partition. §2.6's refusal 5 refuses a cohort at a site that divides or is born. It does not refuse one
  at a non-dividing site of a world where another cell divides.
- **So these sentences hold as written only where no partition is composed:** §0's "No law, validity check or random
  draw reads the record", and §2.2's "No rate, validity check, ledger, heat or draw reads the record" and "An
  observation never stops a run". Where no cohort is declared, the record is zero-size and the test is constant true,
  as for D400's field.
- **The record is finite by construction.** Its update multiplies and adds finite values ≥ 0. A consumed state has
  n ≥ r ≥ 1 at its event, and the kernel guards the division where n = 0. So the test is true wherever the kernel is
  right. A non-finite record, which only an engine fault could make, would refuse that division's step instead of
  being saved.
- **The options.** `partition.py` is not this build's file, and a staleness guard pins its event checks
  (`tests/unit/test_s5_protocol_binding.py`).
  - **(a) Accept it, and say so as the program shows,** here and on the library page: one check reads the record, the
    partition's finiteness test at a division, which is true for every record the kernel can make. **Recommended
    (S):** it costs nothing, changes no other file, and refuses a fault rather than saving it.
  - **(b) Refuse a cohort in any world that composes the partition,** with one more row in `REFUSALS`, so that no
    check reads the record. Version 1's cohorts would then not run in a dividing world at all.

### 9.6 The twins, the rerun and the test cost

- **The twins (§2.2) and case E (§3)** compare `integer_trace_counts` bit for bit with the rest of the trace.
  - FR-43 part 3's co-writers registration copies that field into its export (branch `fr43-cowriters-builder`), so
    the twins' list names it.
  - That exporter reads named fields only, and its judge (tag `fr43-part3-cowriters-judge-2026-11-26`) reads the
    exporter's files and imports nothing from `cells`. So neither needs an erratum, and part 3's own judge stays as
    §2.2 says.
- **FR-43 part 3's rerun at the landing (§2.2)** runs its statistics in windows of at most 10 steps, as
  `validation/fr43_part3/statistics.py` has done since bec67c3f. That was the lead's ruling (a) in D400's round, after
  the trace's counts put C3.3's estimate over the 2^31-byte cap.
  - The targets stay evidence-52935908's: the 11 traces equal (`wall_s` aside), and `verdict.json` and
    `statistics.json` byte-identical.
  - FR-52 adds no value to those rows, since no world of part 3 declares a cohort.
- **Test cost (§5.3).** `tests/unit/test_integer_unit_population.py` measures 61.41 s with 70 tests at D400's fold,
  not 35.5 s. The host rows' +3 s leave it about 25 s under the 90 s cap. The compiled qualification world still needs
  its own file.

### 9.7 Drift that D400 did not cause

- **The rename has landed** (the ID move, steps 4 to 7). The IDs are `cells.operator.integer_unit_population@1`,
  `cells.model.resolved_pump_composite@1` and `cells.model.resolved_pump_tissue@3`. The step's ID in the code is still
  `located_events_exact_transfer_half_steps@1`. §4's "Under the rename" column is now today's.
- **Co-writers (D395).** The operator now admits a declared split writer on a row it moves. A co-writer changes no
  unit count, so the record's update is unchanged. Beside a co-writer the event times are second order in dt (the
  module's docstring), and a cohort's labels follow the recorded times, as the trace does. The qualification world has
  no co-writer.
- **Unchanged premises.** `check_writers` still refuses a label owner, and the wash still refuses the operator (§1's
  neighbours). The operator's test file is `tests/unit/test_integer_unit_population.py`.

### 9.8 Planted errors added to §5.2

Both run on host traces, with no compile.

| Plant | It fails |
| --- | --- |
| One recorded slot's counts altered between two saved rows, the rows' counts as they were (two compensating wrong jumps) | The per-event integrity row (§9.2). The row check passes it |
| A wrong but balanced jump (D400's plant: assemble's change zeroed in the bound layout), in the trace the reference reads | Both integrity rows, since the reference rebuilds from the declaration. A reference seeded from `integer_trace_counts` would pass it |
