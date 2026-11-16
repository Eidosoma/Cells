# Scoped composition: door S's interface (design)

**Status: proposed, 15 November 2026, by the integration owner of D172's round, for the lead (D176);
built in that round, and landed on main with it on 16 November 2026 (merge ab267c39, tag
`d172-landed-2026-11-16`).**
It is the interface that [ARCHITECTURE.md](ARCHITECTURE.md#scoped-composition-door-s), "Scoped
composition (door S)", requires, as the [inner-model note](INNER_MODEL_V4_DESIGN.md) §8 sketches it,
with D176's two corrections:
- order independence holds for disjoint writes only;
- a reference read of an anchor is not an assumption that a physical field is unchanged.

It is published before code (D142), so that FR-4's and FR-5's laws can be written against it. It
landed in R, the single restructure round, built on `integration-d172` behind the gates of §7. §1
describes the code before it.

**Engine models:** `resolved_pump_composite@1` over `resolved_pump_tissue@3`, with every operator
that provides, closes or reads a view field (§5).

**S** marks our own reading or derivation.

## 1. Today (holds today, read at f791294)

- **One provider per field** (`pump_composite.structure_errors`). The adapter's view
  (`pump_composite_adapter.view`) replaces each provided field whole, in declared order. The bath
  schedule therefore returns its held amounts at its baths and the bound values elsewhere
  (`bath_schedule.held_view`).
- **`CONFLICTS_VIEW`** names fields an operator reads as declared. Any provider or closer of such a
  field is refused, whichever slots each touches. So D152's reactions refuse the bath schedule,
  although the reactions read finite nodes and the schedule holds baths (a nominal refusal in the
  composition matrix).
- **`VIEW_READS`** names fields read at their provided value. An earlier operator must provide each.
- **Closers** (`CLOSES`) combine masks by conjunction, propagate closure down the entity hierarchy,
  and pad closed slots (`adapter.close`). A mask has closers or a provider, never both.
- **Control factors** multiply controls in declared order: the precedent for a fixed evaluation
  order of overlapping contributions.
- **The view is formed afresh** from the bound layout wherever it is needed: at a `BOOKS_AT_VIEW`
  event or half-step when a field input is provided, for the inner step, for the end-of-step
  domain, and for readouts. Each provider's contribution is a function of the current state.
- **Any provider of a field input** (a capacitance or a mask) puts the field refresh into every
  step and the 64-node cap on the world.

## 2. The declarations

Each operator declares, per view field, what it **changes** and what it **reads**.

**A change** has three parts:
- **its slots:** the entity slots it may change;
- **its contribution:** `replace`, `add` or `multiply`. A closer's contribution on a mask is `and`;
- **its stage:** `event` when the state that drives it changes only at its event map, or `split`
  when it follows variables its split part moves (water's volumes, a lumen's volume).

**A read** also has three parts:
- **its slots;**
- **its mode:**
  - `reference`: the bound, declared value as data, such as an anchor or an energy reference. It is
    read from the layout `p`, never from the view, and is correct whatever any changer does;
  - `current`: the merged view at the reader's stage;
  - `fixed`: the declared value used as the physical value, because the reader assumes that the
    physical field does not change on those slots. Today's `CONFLICTS_VIEW` is this mode at the
    level of whole fields. D176 keeps it apart from `reference`.
- **its stage:** `event`, `split`, `inner` (the view handed to the inner step), `end` (the end-of-step
  domain) or `observe`. It is the point whose view the reader consumes, fixed by its part.

**Slots** are entity indices on the field's entity axis: cells, outside nodes, patches, populations,
contacts or faces. They are resolved from the definition's identities at binding.
- `ALL` means every slot.
- A field with a species axis (`extracellular_amount_reference`, `[species, node]`) is scoped by
  entity, and every species row of a slot is in scope. Narrowing to rows is reserved.
- **Slot sets are static:** the union over the whole run, including later doses, onsets and
  closures. A change outside its declared set is impossible by construction (§4).

**The contract's API** (`contract.py`; the names are proposals):

| Declaration | Meaning | Default, which keeps today's semantics |
| --- | --- | --- |
| `VIEW_CHANGES = {field: Change(contribution, stage)}` | What it changes | `replace` on `ALL` for each of `VIEW_FIELDS`; `and` on `ALL` for each of `CLOSES`. The stage is `split` for an operator with a split part or none (a state owner), else `event` |
| `SCOPED_READS = {field: Read(mode, stage)}` | What it reads | `current` on `ALL` for each of `VIEW_READS`; `fixed` on `ALL` for each of `CONFLICTS_VIEW` |
| `changed_slots(spec, declaration) → {field: slots}` | Host, at the definition | `ALL` |
| `read_slots(spec, declaration) → {field: slots}` | Host, at the definition | `ALL` |
| `view(state, p, q, *, xp) → {field: values}` | Device. Full-shaped values; only its slots are taken (§4). `q` is the accumulated view before it | Today's method, unchanged |

**How a reader receives what it reads.**
- **A `fixed` or `reference` reader reads the layout `p`,** as every reader does today. For a
  `fixed` read, admission (§3) guarantees that no changer touches its slots, so `p` holds the
  physical value there.
- **A `current` reader receives the merged view at its stage,** through the keyword its part
  already has for `BOOKS_AT_VIEW`:
  - `event(state, control, p, *, xp, view)`, where `view` is a function of state giving the merged
    view;
  - `half_step(state, h, control, p, *, xp, view)`, the merged view at the state current to that
    half-step;
  - `rates(state, control, p, view, *, xp)` and `observe(..., view, ...)`, which take the view
    today.
- **When the view is passed is static,** decided when the composition is built. A part with a
  `current` read at stage `event` or `split` gets `view` if some operator of the composition
  changes a field it reads, and `p` otherwise. That is a field-level test on declarations, so slot
  sets, which are runtime data, never change a program.
- **`BOOKS_AT_VIEW` keeps today's condition** (a field input is provided), so its bits are unchanged.

So every operator keeps its present admissions and bits until it narrows its slots. Narrowing is
per operator (§5).

## 3. Admission (host, at the definition)

The composite checks each rule when it binds a definition, and names the field, the laws and the
overlapping slots in every refusal.

1. **Disjoint changes** are admitted, in any declared order.
2. **Overlapping changes:**
   - `add` with `add`, `multiply` with `multiply`, and `and` with `and` are admitted. They apply in
     the declared order, which is fixed and recorded in the field map as a chain, as control
     factors are.
   - Every other overlap is refused: `replace` with anything, and `add` with `multiply`.
3. **A `current` read** requires a changer of its field to exist, and every changer of a slot it
   reads to precede it in the declared order. This is today's `VIEW_READS` rule (a read with no
   earlier provider is refused), now per slot.
   - It is needed when the reader is itself a changer, since its `view` reads the accumulated view
     at its own place in the merge.
   - Between split parts it fixes the numerical order. The first halves run in declared order, so
     a split reader sees an earlier split changer's first-half update.
4. **A `fixed` read** is refused if any changer, a closer included, changes a slot it reads, at
   any stage.
5. **A `reference` read** has no constraint.
6. **Closers.**
   - A closer's changed slots on the masks include their descendants in the entity hierarchy: a
     cell's patches, those patches' populations and the cell's contacts; a node's patches and
     faces. They are computed at the definition, and a `fixed` read of a mask at an intersecting
     slot is refused (rule 4).
   - A mask still has closers or providers, never both.
   - **Padded fields keep today's rule in R:** no provider of a field in `PADDED_FIELDS`
     (`extracellular_amount_reference` among them) beside any closer. The lead ruled the bath
     schedule's pairs with the partition and insertion@2 real (PUMP_COMPOSITE.md), and T8 keeps
     them so.
   - *For the lead:* under door S the padding acts only on closed slots (`where(open, q, 0)`), so
     those pairs could be admitted where the closed slots and the provider's slots are disjoint
     (**S**). That would be a ruling, not part of R's default.
7. **Field inputs are unchanged in R.** Any change of a field in `FIELD_INPUTS` keeps the refresh
   and the 64-node cap. A refresh only where a field input's slots change is §9.1 of the inner-model
   note, reserved (B6).

**Admission stays valid across steps.** Slot sets are the union over the run and the rules are
static. The view is rebuilt from the bound layout at every formation, so nothing accumulates in it
from one step or formation to the next.

## 4. The runtime merge (device)

At every formation point of §1:
1. `q` starts from the bound layout.
2. **For each changer in declared order,** its `view(state, p, q)` gives its values at the current
   state. The composite takes them on its slots only, with a static per-world slot mask `m`, bound
   at binding as layout data:
   - `replace`: `where(m, v, q)`;
   - `add`: `where(m, q + v, q)`;
   - `multiply`: `where(m, q * v, q)`.

   A changer on `ALL` slots is applied as today, with no mask. So a changer cannot change a slot
   outside its declaration, and an idle slot is selected, never offset by a computed zero (D136).
3. **Then the closers** (conjunction, propagation, padding) and, if a field input changed, the
   refresh, both as today.

**Bitwise properties (S):**
- Selections on disjoint masks commute exactly, so disjoint changers give the same bits in any
  order.
- A changer on `ALL` reproduces today's whole-field replacement.
- The bath schedule's values are its held amounts at its baths, so `where(m, held, q)` equals
  today's `where(scheduled, held, p.field)` while no other changer precedes it on the field.
- Masks are runtime data, not structure. Worlds that differ only in slot sets reuse one executable.
  The structure is the set of changed fields, their contributions and their stages, and it joins
  the batch signature.

**Reader-stage semantics** (D169, amended by D174). A reader at stage `s` sees the view formed at
`s`, which includes every changer's contribution at the state current at `s`, in today's step order:
- **Event readers** see earlier events' changes, and split changers as of the previous step's end.
- **A split reader in the first halves** sees earlier split changers after their first half, and
  later ones as of the step start.
- **The inner step** sees everything after the events and the first halves.
- **The end domain** sees the step's end, and **observation** the accepted row.

This is today's order, stated per stage. It is the splitting's own semantics, not a lag that door S
adds.

**Permutation tests keep the numerical split order.** They reorder the merge (unit tests), or
operators whose reordering does not change the order of split parts, such as an event-only changer
against a split-only reader. Reordering split parts changes the splitting, which is not a door S
property.

## 5. What each operator declares in R

The defaults (§2) keep every operator as today. **R narrows only what the integration case
needs:**

| Operator | Changes: field, slots, contribution, stage | Reads: field, slots, mode |
| --- | --- | --- |
| `scheduled_bath_composition@1` | `extracellular_amount_reference` at its held baths, `replace`, `event` | none |
| `local_species_reactions@1` (D152) | none | volumes, masks and `extracellular_amount_reference` at its sites' cells and nodes, `fixed` |

Every other operator stays on `ALL` in R. FR-1's compartments are among them: their `fixed` reads
do not include the anchor field, so the chain needs no narrowing of them. Narrowing a declaration
would also need `read_slots` and `SCOPED_READS` added to `DECLARATION_MAY_DEFINE`.

**Narrowing that door S makes possible, each when its owner or a consumer needs it.** Each turns a
nominal pair of the composition matrix into an admission. The operators' files belong to their
owner; the integration owner supplies or reviews the slot functions; each lands under crossrev
identity for the worlds it already admits.

| Operator | Changes | Reads | Note |
| --- | --- | --- | --- |
| D150's exchange and turnover, the coupling operator | none | volumes and masks at their routes' cells and nodes; exchange's `membrane_area` at its patches; all `fixed` | |
| `site_occupancy@1` (FR-3) | none | its `CONFLICTS_VIEW` fields at its populations' patches and contacts and their facing pools, `fixed` | Admits it beside the bath schedule |
| `scheduled_membrane_insertion@1` | masks and `extracellular_amount_reference` at its onset patches and nodes, `replace`, `event` | `membrane_capacitance`, `current` | Admits it beside the bath schedule |
| `scheduled_cell_replacement@1` | its five channel and pump fields at the replaced slots' patches and populations, `replace`, `event` | volumes and `membrane_area` at the replaced slots, `fixed` | |
| The lumens, @1 and @2 | `extracellular_volume` at lumen nodes, `replace`, `split` | **new:** the source bath's `extracellular_amount_reference`, `fixed` (an undeclared read today, PUMP_COMPOSITE.md) | Only with insertion@1's narrowing for lumen@1, and insertion@2's (its closures at onset slots) for lumen@2, in the same commit: otherwise each lumen is refused beside the insertion it requires |

**The integration case, which is work item 2 and a real acceptance world:** a bath dose, uptake,
an owned compartment, then a reaction.
- **The operators:** FR-10 doses a held bath (`replace` at the bath, `event`). D150's exchange takes
  the species up from the finite node that a face joins to the bath, into the cell, and exports it
  into FR-1's compartment. D152's reactions run in the compartment, with `fixed` reads at the
  compartment's node and cell, disjoint from the bath.
- **Material** closes across all four, by D150's and D152's own records.
- **The requester's first admissible delivery world** runs with reactions instead of its turnover
  workaround (FEATURE_REQUESTS.md, FR-1).
- **The bath schedule first and last in the declared order** gives the same state and
  observations, bit for bit by field name. It is the only event-only operator, so the split parts
  keep their order.

## 6. What FR-4 and FR-5 build against

- **A compartment law addresses "species S in compartment C"** through FR-1's identity map
  (`compartments.identity_map`). Its reads resolve to C's node, its bounding patch and its owner
  cell. `fixed` reads of C's volume and anchors are admitted beside a dose at any bath.
- **FR-5's damage fraction sits outside door S.** FEATURE_REQUESTS.md maps it to a control
  factor on the transfer law's rate and to the coupling operator's routing door. A per-slot scaling
  of a view field is still available to any law (**S**, an example, not FR-5's mapping): a
  `multiply` on one patch's slot composes with replacement's `replace` on other patches and with
  another `multiply` in declared order, and is refused beside a `replace` of the same patch.
- **FR-4's pump** on the bounding patch is the inner model's (stage `inner`). F2's fuel is held
  inventory rows, not a view field (D176).
- **What door S does not give:**
  - a reader that changes physics when a changed field moves under it: that is a `current` reader
    with its own bookings (D150 §5.1's fallback; door V);
  - a compartment's net charge (FR-1's charged door);
  - a new view field, which needs the adapter's `VIEW_FIELDS`, the integration owner's file.

## 7. Acceptance: the tests that land with door S

| Test | Pass |
| --- | --- |
| T1, the merge | Two changers on disjoint slots, merged in either order, give bitwise equal views, in NumPy and under `jit` |
| T2, overlaps | `replace` overlaps are refused, naming the slots. `add`/`add` and `multiply`/`multiply` chains apply in declared order and are recorded in the field map |
| T3, readers | A `current` reader sees the merged values at its stage. A `fixed` reader is refused where a changer meets its slots and admitted where they are disjoint. A `reference` reader reads the bound value on a changed slot |
| T4, successive steps | A run with a dose mid-run: on every row, outside the union of declared slots, the view equals the bound layout bitwise |
| T5, permutation with the split order kept | The delivery world (§5) with the event-only bath schedule moved from first to last, every split part in its order: every state field and observation column bitwise, compared by name. The ledger diagnostics are compared within rounding, since operators' ledger terms add in declared order |
| T6, single-provider worlds | G1's results, every set, against the baseline the acceptance owner saves at `d172-base-2026-11-15`: bitwise. Worlds whose operators all keep `ALL` slots also keep crossrev identity |
| T7, planted controls | A test double whose values differ off its slots changes nothing there. A planted `replace` overlap and a planted `fixed` reader beside a changer of its slot are both refused |
| T8, the composition matrix | Regenerated. A nominal pair becomes admitted only where the declarations make its slots disjoint; real pairs stay refused |

**Effort (S):** 3–4 agent-days, as in the inner-model note §8. The contract, the adapter and the
composite are the integration owner's. Each operator's slot functions are reviewed with its owner.
