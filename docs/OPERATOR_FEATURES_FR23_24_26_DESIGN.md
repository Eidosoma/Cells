# Operator features FR-23, FR-24 and FR-26 (design notes)

**Status: proposed, 20 November 2026, by the operators owner, for the lead and the user.** Desk
work only (D142): three design notes before any code, each a general feature (D144). Nothing is
built. The user chooses between the options before anything is built.

**Engine models:** `resolved_pump_composite@1` over `resolved_pump_tissue@3`, with:
- FR-23: `site_occupancy@1` beside `scheduled_bath_composition@1`;
- FR-24: `species_regulated_availability@2`, `site_occupancy@1` and `local_species_reactions@1`;
- FR-26: `scheduled_cell_replacement@1` with `site_occupancy@1`, `local_species_reactions@1` and,
  optionally, the coupling operator.

**Code read at 3d3d9641.** `src/`, `tests/` and `validation/` are unchanged at 5011ed3d. Line
numbers will drift. **S** marks our own reading or derivation.

The requests are logged in [FEATURE_REQUESTS.md](FEATURE_REQUESTS.md) (FR-23, FR-24, FR-26; D239).

## 0. Summary

| | FR-23 | FR-24 | FR-26 |
| --- | --- | --- | --- |
| **Today** | Refused at the structure check. Site occupancy reads `extracellular_amount_reference` as declared on every slot, and the bath schedule provides it | No source kind reads a site population. The contract has no declared read of another operator's owned state | Refused at the definition: site populations, D152 cell routes and coupling states on replaced slots |
| **Recommended** | Door S narrowing: site occupancy's fixed reads scoped to the outside nodes its populations face. Also, the trace rule applied to scheduled compositions | A site-population source on coupling @2: the occupied fraction, and amounts as concentrations. It is read through quantities the owner declares in the contract | One occupant rule. A replacement writer of site populations goes through the site operator's accepted writes, with D152's occupant rule for cell routes. The coupling's part is needed only where a link sits in a replaced cell (§5) |
| **Bitwise** | Every registered world, at all three levels (§1) | Values in every world without a site route; @1 and the site operator at all levels. @2's programs gain empty arrays (§3.6) | Every registered world, at all three levels |
| **Development price** | 1–1.25 agent-days | 2.75–3.75 | 3.5–5.25 |

The prices exclude gates. References and judged protocols are priced separately in each note.
FR-23's admission was probed on the engine (§2.1); the rest is read, not run.

## 1. "Bitwise", and the sets each note is checked against

**Three levels**, used in every note:
- **Values:** every state field, observation column and `max_` diagnostic, compared with
  `np.array_equal`, NaN-aware, as PUMP_COMPOSITE.md's equivalence section compares them.
- **Programs:** crossrev identity (`validation/tissue/composite_crossrev.py`). The jaxprs are
  textually identical and every bound input is identical.
- **Structure:** the state, layout and control fields, the declaration keys and their `to_dict`,
  the batch signature and the checkpoints.

**The registered and judged sets:**
- **Crossrev's FR set** (`acceptances_worlds`, `composite_crossrev.py:280`): FR-1
  `fr1-closed-compartment-v1`, FR-3 `fr3-site-occupancy-v1`, FR-10 `fr10-dose-schedule-v1` and
  FR-6's A5″ `fr6-a5pp-v1` (coupling @1). It is compared bitwise at every landing under
  `operators/` (CORE_SEAMS_DESIGN.md §18).
- **D152's MG0c** (`mg0c-turing-v1`, judged 15 November 2026).
- **Replacement@1's frozen guards** (`validation/tissue/composite_guard.py`) and its tests.
- **FR-7's compartment registration** (`validation/fr7/compartment_registration.json`). Its C2 and
  C5 run coupling @2. Their judged run was launched at 17:27 UTC on 20 November, from a frozen
  snapshot of main 439f54fd, and was still running at 18:04 UTC
  (`/mnt/workspaces/Cells/fr7-loop-20261119/u2-compartment/judged-439f54fd/RUN.txt`).

## 2. FR-23: timed bath changes beside binding sites on distinct finite nodes

### 2.1 The request, and today's refusal

**The request (D239):** admit a timed bath change and binding sites in one world when they act on
distinct finite nodes. **Acceptance:** at the event boundary the bath records the dose, and
occupied sites keep their bound material.

**The refusal.** It comes from the composite's structure check (`pump_composite.structure_errors`):
"site_occupancy@1 reads extracellular_amount_reference as declared, but
scheduled_bath_composition@1 provides it". `tests/unit/test_door_s.py:334` asserts it. The
composition matrix tags it **nominal** (`docs/PUMP_COMPOSITE.md:279`; cells 17↔19 at :173 and :175).

**Why the tag is nominal** (read, not run):
- **What the site operator declares.** It lists the field in `CONFLICTS_VIEW` with no slots
  (`src/cells/operators/site_occupancy.py:1195`). Door S therefore treats it as a `fixed` read of
  every outside node.
- **What it actually reads:**
  - the anchors only at its pools' outside nodes (`pool_amounts`, :760–773), and the volumes there
    (`pool_volumes`, :776–783);
  - for a cell pool, an index-0 read that `where` discards (:765, :770). That is not a read in door
    S's sense.
- **What its parse refuses:** a population that faces a held bath (:298–303).
- **What the bath schedule changes:** the field at its held baths only, scoped
  (`src/cells/operators/bath_schedule.py:550`; `changed_slots`, :650–653; `view_slots`, :655).
- **So the slots never meet.** SCOPED_COMPOSITION_DESIGN.md §5 already lists this narrowing, at
  :223: "Admits it beside the bath schedule". D152 made the same narrowing
  (`src/cells/operators/species_reactions.py:1302–1308`; `read_slots`, :1448–1451).

**Probed on the engine, 20 November 2026** (CPU 7; `probe_fr23.py` and its output under
`/mnt/workspaces/Cells/operators-20261120/`). Option A's declarations (§2.3) were patched onto the
site operator inside the probe's process only; no file was edited. The world is the bath schedule's
`dosed_world`, with an outward population at θ0 = 0.5 on `contact_0` and a ×10 step of the neutral
species at the bath at t_e.
- **Before the patch:** both orders are refused at the structure check, and the definition is
  refused at parse with the message above.
- **After it:**
  - both orders pass the structure check;
  - the definition parses and its model builds, the per-slot check included;
  - the twin beside insertion@1 is still refused.
- **At the event boundary, in NumPy:** the event map is valid and leaves every site field bitwise
  unchanged. The dose record is 1 ulp from V_b·a (relative 1.9e-16), since it is the held content's
  change, n_new − n_old (§2.8).

### 2.2 Reading "distinct finite nodes"

**We read it as a held bath, dosed by the schedule, beside sites that face finite nodes.** The
request's own text confirms that reading: it says each operator parses on its own today. The bath
schedule's own parse refuses any target that is not a held bath (BATH_SCHEDULE_DESIGN.md §3.1: "a
finite node cannot be clamped").

**A timed change of a finite node's content** is a different law. A bolus or a wash into a finite
bath is closer to FR-20's pool replacement (ASSEMBLY_WASHOUT_DESIGN.md). It is a question for the
lead (§2.10), not one of the options here.

### 2.3 Options

| Option | What | For | Against |
| --- | --- | --- | --- |
| **A** | Site occupancy declares `SCOPED_READS`: `fixed`, stage `split`, `scoped`, for `extracellular_amount_reference` and `extracellular_volume`. Its `read_slots` gives the outside nodes its outward populations face | Exactly what it reads. A future scoped changer of finite nodes that no population faces (insertion@1, once it declares its onset slots) also composes | None found |
| B | The same, with D152's slot set: every finite outside node | Copies the precedent line for line | Too broad: it would refuse a future scoped changer of a finite node that no population faces |
| C | No engine change; the requester uses turnover's clearance as a workaround | Nothing to build | It is not the request |

**Recommended: A.** Its other `CONFLICTS_VIEW` fields keep their slotless `fixed` reads: cell
volumes and the masks. So water, insertion and the closers stay refused, as today.

**One data rule goes with it (S).**
- **Today's rule:** `check_traces` (:307–335) holds every declared concentration of a ligand at or
  above its declared trace, and `check_template_traces` (:509–523) extends it to replacement
  templates.
- **The new case:** a scheduled bath composition is also a declared concentration. The bath
  schedule itself requires only positivity.
- **The rule:** a dose that sets a held bath's ligand below the ligand's trace is refused at the
  definition. It is read on the host from the bath schedule's declaration, as the template rule
  reads replacement's.

### 2.4 What does not change

- **The bath schedule needs no edit.** `bath_schedule.py` is another agent's file today.
  - Its docstring and BATH_SCHEDULE_DESIGN.md §1.3 and §3.1 call site occupancy refused. Those lines
    become stale.
  - The docstring is corrected later, by that file's owner. The design note's lines are corrected
    here, with the landing.
- **Still refused:**
  - site occupancy beside a compartment: the compartments' admitted list fails closed (matrix
    18↔19, `d`);
  - RK4, which site occupancy refuses;
  - insertion@1, which provides the anchors on every slot;
  - the closers.
- **The composition is development, not judged (D143).**
  - FR-3's judged scope names "site occupancy beside a bath schedule" as not claimed
    (`validation/tissue/site_occupancy_acceptance_protocol.json`, its `scope`).
  - A world in which a face carries the dose to the sites is also outside that scope, which was
    face-free.

### 2.5 What stays bitwise

- **Every world, at all three levels.** `SCOPED_READS` and `read_slots` are host-side declarations,
  and the trace rule runs at the definition. No state, layout, control, declaration key, kernel or
  batch signature changes. Crossrev's FR set and MG0c are identical.
- **What does change:**
  - the composition matrix: cells 17↔19 go from `n` to ✓, and the refusal row at :279 goes;
  - the assertions that recorded the refusal (§2.7).

### 2.6 Files and owners

- **The operators owner** (this seat). `site_occupancy.py` is not in CORE_SEAMS_STEP0.md §4.2's
  table; this seat takes it under the lead's brief, as it takes the coupling module in §3.7.
  - `src/cells/operators/site_occupancy.py`: the declarations, the trace rule and the docstring
    (:39–40);
  - `validation/tissue/site_occupancy_fixtures.py`: a world builder with a face;
  - the regenerated matrix: `validation/tissue/composition_matrix.py --write` into
    `docs/PUMP_COMPOSITE.md`. Both are the operators owner's files under FR-7 F1's recorded
    exception (1e8f7bf3);
  - the tests in §2.7;
  - the docs: SITE_OCCUPANCY_DESIGN.md (as built), SCOPED_COMPOSITION_DESIGN.md §5's row,
    BATH_SCHEDULE_DESIGN.md's two lines, FEATURE_REQUESTS.md and PROGRESS.md.
- **Not touched:** `bath_schedule.py`.
- **The lead:** the tier rows, if a file's count changes against the recorded baseline.

### 2.7 Tests (D224: as few as is enough)

- **One assertion flips.** `test_door_s.py:334–337` becomes an admission in both orders. Its
  still-refused twin sits beside it: sites beside insertion@1, whose anchors are unscoped.
- **One row:** the bath schedule joins the admitted neighbours at `tests/unit/test_site_occupancy.py:295`.
- **One row** in `REFUSALS` (:184): a dose that sets a ligand below its trace.
- **One uncompiled event-boundary row.**
  - **Its world:** a held bath dosed by the schedule, a face to a finite node, and an occupied
    outward population facing that node.
  - **The checks:** the composite's event maps at t_e, with `xp=np`, book the dose as the held
    content's change and leave every site field bitwise unchanged. The probe (§2.1) ran exactly
    this check.
  - **Its cost:** tier 1, no compile, about a second. It goes in `test_site_occupancy.py`.
- **No new compiled test.** The response through the face is development evidence (§2.8), outside
  the suite.
- `tests/unit/test_composition_matrix.py` checks the regenerated block, as it does today.

### 2.8 Acceptance, from the request

At the event boundary:
1. **The bath records the dose:** `bath_dose_fmol` equals the change of the bath's held content,
   n_new − n_old, bit for bit. That change equals V_b Σ_f a_f ν_f to rounding: 1 ulp in the probe
   (§2.1).
2. **Occupied sites keep their bound material:** the event map changes no site field, bit for bit.

**The development run** (a record, not a test), with its criterion written first:
- **Two arms in one vmap batch:** dosed and undosed, with per-world schedules on the same bath.
  The run uses ARS at 1 ms and a neutral step inside the measured region, for example ×10 at
  1e-2 mM, with the face at κ/V ≤ 10/s (BATH_SCHEDULE_DESIGN.md §8.1).
- **What it must show:**
  - the rows before t_e are bitwise equal between the arms;
  - every host check passes on every row, the site's own ledgers and the bath's reconciliation term
    included;
  - after the event, B rises in the dosed arm.

### 2.9 Price (S)

| Part | Agent-days |
| --- | --- |
| The site operator's declarations, the trace rule and the docstring | 0.25 |
| The matrix, the flipped assertion, the rows and the event-boundary row | 0.25–0.5 |
| The development run and its record | 0.25 |
| Docs | 0.25 |
| **Development** | **1–1.25** |
| Optional: a registered protocol, with code-blind references of the dosed world with a face | +1.5–2 |

Calibration: FR-10's note priced door S at 0.5–1 for the whole contract change (BATH_SCHEDULE_DESIGN.md
§5). This is one operator's narrowing on that contract.

### 2.10 Questions

1. **For the lead:** is the held-bath reading of "distinct finite nodes" right (§2.2)? If the
   requester means dosing a finite node, that is a new law, best designed beside FR-20's pool
   replacement.
2. **For the user:** is development evidence enough for the requester, or should the dosed world
   with a face be judged under a protocol?

## 3. FR-24: binding-site occupancy as an input to reaction rates

### 3.1 The request, and today's gap

**The request (D239):** a reaction reads a named site population's occupied amount, accessible
capacity or occupied fraction as a rate input, through the coupling operator's sources.
**Acceptance:** changing occupancy changes the linked rate, and disabling the link leaves the
binding dynamics unchanged.

**Today's sources.** Coupling @2 reads three kinds of source (`src/cells/operators/species_regulated_availability.py:84–102`
and :555–601):
- a species, as its concentration in the element's cell;
- a regulatory state, as its fraction;
- a channel population, as its density (FR-7's part (b)).

Anything else is refused: "coupling {name}'s source is {'species': id} or {'state': id}" (:593).
No source reads a site population.

**The read has no path in the contract.**
- Site occupancy provides no view (`site_occupancy.py:22–25`).
- The contract declares no read of another operator's owned state. Operators reach each other
  through views, accepted writes and host-side declarations.
- The population source works only because membrane state provides `channel_abundance` as a view
  field (R2).

**The design notes already name it.**
- SITE_OCCUPANCY_DESIGN.md §2.6 (:588–596): a source kind `{"site_population": id}`, read as θ, "a
  cross-operator state read". It is exact under the held evaluation, since @3's step never moves
  the site pools.
- INVENTORY_COUPLING_DESIGN.md §2.2 (:724) names a declared cross-operator state read
  (`STATE_READS`) as a contract option for the event trigger.

### 3.2 The three quantities, against the standing rulings

The request names three quantities: the occupied amount B, the accessible capacity S and the
occupied fraction θ = B/S.
- **θ** is dimensionless and intensive. No ruling stands against it.
- **B and S** are amounts, in fmol. Two standing rulings stand against reading raw amounts:
  - "Amount sensing is rejected" (INVENTORY_COUPLING_DESIGN.md §1.3, :250): a half-saturation is
    a dissociation constant, which is a concentration;
  - "a density, never a count", the lead's ruling of 18 November for the population source
    (ABUNDANCE_TO_FUNCTION_DESIGN.md §6.2; the module's docstring at :86).
- **S is a layout constant in version 1.** α, copies and sites per copy are not scheduled
  (SITE_OCCUPANCY_DESIGN.md §2.3). So a source on S is constant in every admissible world. It is
  reported as `CONSTANT_SOURCE` (:198), the population source's precedent, and it becomes live
  when a writer of S exists.

**Options for reading B and S:**

| Option | B and S read as | For | Against |
| --- | --- | --- | --- |
| Q1 | Refused: θ only | No ruling moves | Not the request |
| **Q2** | Concentrations in the element's cell: B/V and S/V in mM, at the declared volume, with K in mM | It is §1.3's own form. The bound complexes per cytosol volume are the activator that a cytosolic reaction sees (**S**) | A contact population needs the cell on its side |
| Q3 | Surface densities on the owner patch: B/A and S/A, in fmol per µm² | The population source's density form | Contacts have no area, and a cytosolic reaction does not see a surface density |
| Q4 | Raw fmol | Literal | It reverses both rulings, which is the user's call |

**Recommended: θ and Q2.**

**The laws:**
- **For θ:**
  - `site_fraction`, f = θ, and `site_complement`, f = 1 − θ. These are the regulatory state's two
    laws, since occupancy is that state with material (SITE_OCCUPANCY_DESIGN.md §2.6);
  - the two Hill laws, with a dimensionless half-saturation.
- **For B/V and S/V:** the two Hill laws, with `half_saturation_mM`.

**What every coupling keeps:**
- F = b + (1 − b) f, in [b, 1], on the scheduled rate, which is the maximum;
- its operating range, declared in the quantity's unit.

### 3.3 The read path: options

| Option | What | For | Against | Cost against R1 |
| --- | --- | --- | --- | --- |
| R1 | The coupling reads, by name, site occupancy's increments, anchors and capacity from the merged state, and its own `check_definition` refuses a missing or misplaced owner | No contract change | The field map does not record the read. The coupling carries the site operator's representation (anchored increments). The event trigger would repeat the pattern | — |
| R2 | A declared cross-operator state read, `STATE_READS = {owner law: fields}`. The composite checks that the owner is present and in order, and records the read | Declared and recorded. It is the coupling note's own option (b) | The reader still computes θ from the owner's fields | +0.25 |
| **R3** | **Declared readable quantities**, described below | The owner keeps its representation private. One seam serves every later source and the event trigger | A contract item, and four call sites in the composite | +0.75 |
| R4 | A view field that site occupancy provides | Reuses door S | View fields are @3's layout names, in the adapter. Operator targets' half-steps receive no view (the module's docstring, :97–98) | Rejected |

**R3 in detail:**
- **The owner** declares named quantities, each with its entity axis and unit. For site occupancy
  these are the occupied fraction, the occupied amount and the accessible capacity, per
  population. Its own function computes them.
- **A reader** declares the quantities it reads.
- **The composite** checks each read's presence, axis and order, and records it in the field map.
  It passes the reader its quantities as a keyword, as R2 passes `view=`, and only where a read is
  declared, so every other call is unchanged.

**Why R3 is recommended:**
- **The owner's representation can change** without breaking readers. Planned changes that would
  move it are the shared SSPRK block (SITE_OCCUPANCY_DESIGN.md §12) and a later kind.
- **One seam serves every later source:** a compartment's contents, a unit producer's pools and the
  event trigger.
- **It applies composition's C6 rule to reads.** C6 is the rule that writers book through the
  contract, never by importing the owner (OPERATOR_COMPOSITION_DESIGN.md §4.1).

### 3.4 Order, locality and evaluation (S)

- **Order.**
  - **When a factor is evaluated:** a rate route's factor is evaluated at the start of each of its
    target's half-steps (B1′). Site occupancy moves B in its own half-steps.
  - **The rule:** every owner whose quantity a route reads precedes the route's target, as B1′'s
    source does (`pump_composite.rate_route_definition_errors`, :927–949).
  - **Why:** the target's two halves then both read θ after the owner's first half, at the midpoint
    of the binding flow. The split stays symmetric about the target (the coupling note §1.4's
    midpoint form).
  - **An inner target** reads at the control view, after every first half, whatever the order.
    @3's step never moves B, so the held factor is exact.
- **Locality.**
  - **@2's rule:** a source is read in its element's cell, and outside-node elements are refused at
    binding.
  - **A patch population's cell** is its patch's own cell, whichever face it binds from.
  - **A contact population's cell** is the cell on its side.
  - **The rule:** the element and the population share that cell, as the population source requires.
- **Out of scope in version 1:**
  - a reaction at the population's facing outside node (chemistry in the medium; @2 routes
    cell-side elements only);
  - a reaction in a compartment (site occupancy is refused beside compartments).
- **Targets.** The source kind comes with every @2 routable control: turnover's rate, the
  reactions' multiplier and the unit producer's assembly rate. @3's channel and junction
  availabilities come too. The acceptance uses a reaction.
- **A regulatory state's input from occupancy** (§2.6's second use) is an option, at +0.5.

### 3.5 The loop (D218)

- **When a loop exists.** An operator may write the ligand's row at the population's facing pool:
  the routed reaction itself, a turnover, or @3's faces. Occupancy then feeds back on the rate. That
  is a physical, state-mediated loop through the one routing door, which D218 admits.
- **D218's conditions:**
  - its evaluation timing (`target_half_steps`) and its operating range are declared, which @2
    already requires;
  - each such loop is verified whole against a reference, under timestep refinement, with a control
    in which the feedback is cut.
- **The verification is per loop:** a consumer's item, priced in §3.10. The acceptance world is
  open: its reaction does not touch the ligand.
- **It is not an instantaneous algebraic cycle.** B is state, and only the owner's half-steps move
  it.

### 3.6 What stays bitwise

- **Coupling @1:** untouched, at all three levels (A5″ is judged and is in crossrev's set).
- **Site occupancy @1:** its readable quantities are a class declaration and a function that runs
  on the device. That function is traced only where a read is declared, so its values, programs and
  structure are unchanged in every other world. FR-3's judged worlds and crossrev are among them.
- **D152:** untouched.
- **Coupling @2:**
  - **Values:** bitwise in every world without a site route. The site-route arrays are static by
    shape, as F2's population arrays are.
  - **Programs:** they gain empty site-route layout arrays, as @2's population source did on 19
    November (de65d033).
  - **FR-7's C2 and C5 run @2.** Their judged run uses a frozen snapshot of 439f54fd (§1), so this
    landing cannot touch its verdict. The landing carries an A/B comparison of C2 and C5 on main,
    over a short window (the full runs are 1000 s), that shows their values bitwise. If the lead has
    added either to crossrev by then, its record is renewed.
  - **A version @3** would leave @2's programs alone, at the cost of a new law version. Composition's
    decision (D191) prefers none, and nothing here needs it.
- **The contract and the composite:** new declarations with empty defaults, so every other
  operator's program is unchanged.

### 3.7 Files and owners

- **The operators owner.** CORE_SEAMS_STEP0.md §4.2 gives this seat `contract.py` and the
  composite. The coupling module and `site_occupancy.py` are outside that table, and this seat takes
  them under the lead's brief.
  - `src/cells/operators/species_regulated_availability.py`: the source kind;
  - `src/cells/operators/site_occupancy.py`: the readable quantities;
  - `src/cells/operators/contract.py` and `src/cells/models/pump_composite.py`: R3;
  - the tests: `tests/unit/test_species_regulated_availability.py`,
    `tests/unit/test_pump_composite_contract.py`, and optionally
    `tests/unit/test_species_regulated_availability_with_reactions.py`;
  - the docs: INVENTORY_COUPLING_DESIGN.md (a section), SITE_OCCUPANCY_DESIGN.md §2.6, and
    PUMP_COMPOSITE.md's operator and contract tables.
- **The F owner, optionally:** `src/cells/registry/declarations.py`, if the declarations manifest
  should list readable quantities (D185). Nothing requires it.
- **The lead:** the tier rows, and crossrev's record if it holds C2 or C5 by then (§3.6).

### 3.8 Tests (D224)

**Rows in the existing NumPy route test** (tier 1, no compile), in the form of
`test_species_regulated_availability.py:1006`. The world has an outward population and a D152
reaction in its cell, routed from θ. The rows check that:
- the factor equals b + (1 − b) f(θ), worked out by hand at the bound state;
- the routed half-step is bitwise the half-step at the product control;
- at a second bound state with another B, the factor differs and so does the routed half-step (the
  rate follows occupancy);
- switched off, the factor is exactly 1 and the half-step is the plain one;
- the site half-step is bitwise the same with the coupling on, off or absent, so the read is one-way;
- a θ outside the declared range refuses the half-step, and only while the coupling is on.

**Refusal rows** in `REFUSALS` (:558):
- no site operator;
- the owner after the target;
- an unknown population;
- a law that does not match its quantity;
- a half-saturation in another unit;
- a population in another cell;
- an outside-node element;
- a θ range outside [0, 1].

**Contract rows** in `test_pump_composite_contract.py`: a read of an undeclared quantity or axis,
and a read whose owner follows the target.

**The constant source:** one row asserting `CONSTANT_SOURCE` for a source on S.

**One compiled row, optional,** in `test_species_regulated_availability_with_reactions.py`:
- tier 2, one compile, about 25–40 s. The file runs 56 s for three tests today;
- the arms are set by the switch;
- **its reason:** it is the only check that the factor applied on every row of a run follows a
  binding transient.

### 3.9 Acceptance, from the request

1. **Changing occupancy changes the linked rate.** At two states that differ only in B, the applied
   factors differ, and so do the routed reaction half-steps. Each factor equals b + (1 − b) f(θ),
   evaluated independently in NumPy, to a relative 1e-14.
2. **Disabling the link leaves the binding dynamics unchanged.** With the coupling switched off,
   the factor is exactly 1, and the site state is bitwise the state of the same world without the
   coupling, step by step.
   - **Where the linked reaction writes the ligand's row at the facing pool,** the switched-on and
     switched-off arms legitimately differ. They differ through the free ligand, not through the
     read (§3.5).

### 3.10 Price (S)

| Part | Agent-days |
| --- | --- |
| R3: the contract's declarations, the composite's checks, its field map and its four call sites | 0.75–1 |
| The site operator's readable quantities | 0.25 |
| The source kind on @2: parse, binding arrays, four kernels, ranges, the constant source, summary, view sets, refusals | 1–1.5 |
| Tests | 0.5–0.75 |
| Docs | 0.25 |
| **Development, with R3** | **2.75–3.75** (R2: 0.5 less; R1: 0.75 less) |
| Optional: a regulatory state's input from occupancy | +0.5 |
| Optional: an outside-node element at the population's facing node | +0.5 |
| Per loop class (D218): a code-blind reference, refinement and a feedback-cut control | +1.5–2 |
| Optional: a registered protocol | +1.5–2.5 |

Calibration: FR-7's part (b), the population source on @2, was estimated at 1–1.5
(ABUNDANCE_TO_FUNCTION_DESIGN.md §7). It landed as one commit (de65d033): 334 lines in the module
and a 457-line test file of 21 tests, about 25 s.

### 3.11 Questions for the user

1. **The amounts:** Q1, Q2, Q3 or Q4 (§3.2)? Recommended: θ and Q2.
2. **The read path:** R3, or the cheaper R1 or R2 (§3.3)?

## 4. FR-26: owned state when a cell is replaced

### 4.1 The request, and today's refusals

**The request (D239):**
- the incoming cell is initialised from its template;
- environment-owned material is preserved;
- what leaves with the departing cell is recorded.

**Minimal acceptance:** the material balance closes across one replacement, with occupied sites
and active reactions.

**Today's refusals,** each at the definition, each saying that version 1 has no occupant rule:
- site populations on a replaced slot's patch, or on a contact incident to it (`site_occupancy.py:472–488`);
- D152 cell routes on replaced slots (`species_reactions.py:854–864`);
- coupling states, targets and junction endpoints on replaced slots
  (`species_regulated_availability.py:1290–1320`), and @2's operator-target elements there
  (:1347–1366).

**What already holds** (replacement@1, D139; CELL_REPLACEMENT.md):
- the occupant's cytosolic amounts leave as waste (`replacement_removed_fmol`);
- the template's amounts arrive (`replacement_supplied_fmol`);
- gates and route values reset;
- incident junctions restart;
- the free-energy and charge changes are booked;
- D150's turnover and exchange take a newcomer's rates from their own `templates`, keyed by
  replacement template ID (`src/cells/operators/species_common.py:442–512`; D150 §5.2).

**The rule is already declared:**
- **SITE_OCCUPANCY_DESIGN.md §5.2** (:993–1012):
  - the occupant leaves with its sites and its bound cargo, booked as removed;
  - the newcomer arrives with its template's site state, never the previous occupant's;
  - contacts incident to the slot reset.
- **INVENTORY_COUPLING_DESIGN.md §1.5** (:385): a newcomer's regulatory state comes from its
  template, through the operator's own event at replacement's event steps.

### 4.2 The rule, once, for every operator that owns cell state

**Carriers have identity; slots are storage** (D139; D150 §5.2).
- **The occupant takes its state with it.** Its state is everything on the slot's entity subtree:
  the cell, its patches and their populations. All of it leaves with the occupant and is recorded
  as departed.
- **The newcomer** takes its template's declared state, recorded as arrived. A donor copy takes the
  donor's; for sites that is version 1.1.
- **Environment-owned state is untouched:** outside nodes, finite and held, with their routes, and
  every other cell with its entities.
- **Records stay with the slot.** Cumulative transfers, heat, work and extents are history, and the
  ledgers close with the departed and arrived terms.

| Owner | Leaves with the occupant (recorded) | What the newcomer brings | Stays | Version 1 |
| --- | --- | --- | --- | --- |
| @3, through replacement@1 | Cytosolic amounts (`replacement_removed_fmol`) | The template's amounts, gates and route values | Outside nodes; neighbours | Built (D139) |
| `site_occupancy@1`: patch populations of the slot, either face | Bound B, with the site free energy | The template's arrival occupancy θ′; in version 1 the same unit, copies, sites per copy, α and constants | Free ligand at the facing node (an outside node is environment; the cytosol is replacement's); the records of net binding, internalisation, heat and work | **Lifted** (§4.3, W) |
| `site_occupancy@1`: the binding and internalisation multipliers (`site_controls`) of those populations | The founder's schedule ends at its death | The template's multipliers, held through the newcomer's life in version 1 (a newcomer's own schedule is version 1.1) | — | **Lifted** with W; built on the host (§4.3) |
| `site_occupancy@1`: contact populations incident to the slot | §5.2 resets them, but where the material bound on the neighbour's side goes needs a ruling (§4.11) | — | — | Stays refused |
| `local_species_reactions@1`: cell routes at the slot | Nothing material; the records are history | The template's per-site multipliers (rates follow the occupant) | Extent, produced and consumed, heat, work, its standard-potential term | **Lifted**, at the definition only |
| `local_species_reactions@1`: outside routes | — | — | Environment | Composes today |
| D150's turnover and exchange: cell-side routes | Rates | The template's rates | Outside-node routes are environment | Built (D150 §5.2) |
| The coupling, @1 and @2: targets and operator-target elements at the slot, whose source is a species or a site population | Nothing: the source is already the occupant's | — | — | Lifted only for a link in a replaced cell (part C′, §4.3) |
| The coupling, @1 and @2: regulatory states at the slot | The state s (kinetic, with no ledger) | The template's s′ | The crossing record and the input integral, as slot diagnostics | Optional (part C) |
| Membrane state, with insertion, trafficking and the unit producer | — | — | — | Stays refused: replacement and membrane state both provide `channel_abundance` (a real matrix refusal) |
| `cell_owned_compartments@1`: an owner's compartments | — | — | — | Stays refused (door R, CLOSED_COMPARTMENT_DESIGN.md §1.5) |
| Water, and replacement@2 | — | — | — | Out of scope: sites and D152 read the declared volumes, and replacement@2 is a later version |

### 4.3 Options for the site populations

| Option | What | For | Against |
| --- | --- | --- | --- |
| **W** | A replacement writer of site populations: a new law in `site_occupancy.py`, proposed as `site_occupant_replacement@1`, described below | `site_occupancy@1` and replacement@1 keep their structure and programs. No contract change. The accepted-write path is the one the composition note gives division (OPERATOR_COMPOSITION_DESIGN.md §4.4) | Two laws for one entity's lifecycle. It departs from §5.2's "an event part of this operator" |
| O | The owner's own event part, as §5.2 sketches it, under @1 (a D148 round) | One law | New state, keys and a part on @1, so every site world's program and structure change, FR-3's judged program included |
| O + C5 | The same, with C5's declared conditional bookings (composition's M4, not built): the event part and its records exist only beside replacement@1 | One law; worlds without replacement are unchanged | Builds C5 early, in `contract.py` and the composite (+1–1.5) |
| O@2 | `site_occupancy@2`: @1 plus the event part | @1 stays frozen | A second version of the law, which D191 prefers to avoid |
| L | A composite lifecycle by roles for replacement, like B1's for division. Owners declare per-field roles on hosted axes, and replacement calls the lifecycle | Designed once for replacement and division, for every owner at once | It needs roles for operators' owned fields, hosted axes, C5 and C6: 7–10 agent-days, ahead of FR-7's division design |

**W in detail:**
- **Where it sits:** declared after `site_occupancy@1`, beside replacement@1.
- **What it writes:** at replacement's prescribed event steps, its event map writes the site pools
  through the owner's accepted writes (`site_occupancy.py:1211–1214`).
- **What it books:** the departed and arrived bound material, and the site free energy exchanged, in
  its own fields. It adds its terms to the owner's ledgers through the contract's
  `external_ledger_terms` (`contract.py:688`), and its exchange to the energy ledger.
- **Where the newcomers' occupancy comes from:** its own `templates`, keyed by replacement template
  ID, which is D150's form.
- **The composite already admits it:** "an entity write targets inner state or a field an earlier
  operator accepts" (`pump_composite.py:650–659`).
- **W would be the first writer of the site pools (S).**
  - The site operator's accepted writes are declared and tested with no writer
    (`tests/unit/test_site_occupancy.py`, its docstring at :11).
  - The path itself is exercised by four writers: insertion@2, trafficking, the partition and
    replacement@2. Replacement@2 is W's closest precedent: its event writes water's accepted state
    at a replacement (`src/cells/operators/cell_replacement_v2.py:472–481`).
  - **The risk** is the site operator's own ledgers taking external terms for the first time. W's
    price allows for it (§4.10).

**The site multipliers follow the occupant** (D150 §5.2: a carrier's schedule applies while it
occupies a slot).
- **The founder** keeps today's `site_controls` entry, which ends at its death; a change after the
  death is refused.
- **A newcomer** takes the binding and internalisation multipliers that W's templates declare, held
  through its life in version 1. A newcomer's own schedule is version 1.1.
- **It is built on the host:** the site operator's control construction reads W's declaration, as
  `check_template_traces` reads replacement's. Its declaration and schedule keys are unchanged.
- **The alternative** keeps the slot's schedule across occupants, as an intervention on the slot. It
  departs from D150's rule (§4.11).

**Recommended: W for the sites and D152's occupant rule.** The coupling's part C′ is added where a
link sits in a replaced cell, and part C is optional.

**D152's part (S).**
- **Its owned state is records only:** extent, produced and consumed, heat, work and its
  standard-potential term (`species_reactions.py:168–182`). They stay with the slot.
- **So its occupant rule is about rates, on the sites' pattern:**
  - the founder's per-site multipliers keep today's schedule, which ends at its death;
  - a newcomer from a template takes its template's multipliers. The tables are built in the
    operator from `species_common.occupants` (:442–458), the host table of each slot's occupants
    that D150's `route_tables` reads. `route_tables` itself keys schedules by carrier, which version
    1 does not add;
  - the refusal is lifted for every cell route these cover.
- **It is definition-time only.**
  - The new `templates` key is optional and absent from `to_dict` when empty. `_fields` requires the
    exact key set (`src/cells/definitions/specs.py:74–82`), so every registered definition still
    parses and round-trips identically.
  - Version 1 adds no carrier key to `reaction_controls`, whose entries are also exact-match
    (`species_reactions.py:714`). A newcomer's own schedule is version 1.1, with that key optional.

**Part C′, a link in a replaced cell.**
- **Today's refusal.** @2's element check refuses an operator target's element in a replaced cell
  (`species_regulated_availability.py:1347–1366`), and @1's check refuses targets there (:1290–1320).
  So an occupancy-linked reaction in a replaced cell is refused even once W and D152's rule exist.
- **The change.** The refusal is lifted where the source is a species of that cell or a site
  population. Replacement already swaps the species, and W already resets the population, so the
  factor reads the newcomer's state. No state is needed: it is definition-time only.

**Part C, the coupling's states (optional).**
- **The rule** is its §1.5's: an event at replacement's steps.
- **Version 1 needs no new state.** The newcomer's value is a `regulatory_writes` entry at t_e,
  derived on the host from the template.
- **The diagnostics stay the slot's.** The crossing record and the input integral are slot
  diagnostics, so a state with a crossing level on a replaced slot stays refused.
- **A donor copy's s depends on state,** so donor copies stay refused.
- **A link whose source is a state** in a replaced cell needs part C as well as C′.

**Contacts.** §5.2's reset of a contact population needs a ruling on where the material bound from
the neighbour's side goes:
- out with the departing contact, and recorded; or
- released into the neighbour's pool, booked as unbinding.

Version 1 keeps contact populations incident to a replaced slot refused.

### 4.4 Accounting at the event (S)

- **Material.**
  - For each population on the slot, the departed amount is D = B and the arrived amount is A = θ′S.
    S is unchanged in version 1.
  - The owner's `site_bound_entity` ledger becomes ΔB − (net − internalised) − (A − D), through W's
    external term.
  - `site_moiety_entity` still closes, since R′ = S − B′.
- **Energy.**
  - The site free energy changes by ΔG = G(R′, B′; S) − G(R, B; S). W computes it with the module's
    own `site_free_energy` (:733).
  - W books it in an exchange field. The field has neither the heat nor the work suffix, so it
    stays out of the IMEX flow bound, as the bath schedule's records do (BATH_SCHEDULE_DESIGN.md
    §2.2).
  - Its ledger term closes the composite's energy ledger at the event row, and its magnitudes enter
    the rounding allowance.
- **@3's ledgers:** the site event does not touch them, since the bound pools are not @3's rows.
  Replacement@1's own terms cover the cytosol.
- **Charge:** none, since the ligands are neutral.
- **D152 across the event, unmeasured.** This is the first world in which D152's cell routes see a
  replacement. Its energy terms around the event row are therefore checked in development, not
  assumed.

### 4.5 What stays bitwise

- **Replacement@1:** no file changes.
- **`site_occupancy@1`:** structure and programs unchanged.
  - Its replaced-slot refusal narrows at the definition only: populations that W covers are
    admitted. Worlds refused today become new definitions.
  - Its control tables read W's declaration on the host, and they are identical in every world
    without W.
- **D152:** values and programs unchanged in every world without a covered cell route on a replaced
  slot. That includes MG0c and crossrev's FR-1 C7. Its structure is unchanged too: the optional key
  is absent.
- **The coupling.** Part C′ is definition-time only, and part C adds writes derived on the host. So
  the programs are unchanged in every world without replacement, A5″ and FR-7's C2 and C5 among
  them.
- **What changes:** W is a new law, so the composition matrix gains its row and column.

### 4.6 Files and owners

- **The operators owner.** `site_occupancy.py` and the coupling module are outside CORE_SEAMS_STEP0.md
  §4.2's table, and this seat takes them under the lead's brief.
  - `site_occupancy.py`: W, the narrowed `check_slots` and the multiplier tables;
  - `species_reactions.py`: the occupant rule;
  - `species_regulated_availability.py`: parts C′ and C, where chosen;
  - `validation/tissue/site_occupancy_fixtures.py`: a world builder with a replaced slot;
  - the tests in §4.7 and the regenerated matrix;
  - the docs: SITE_OCCUPANCY_DESIGN.md §5.2 (as built), SHARED_INVENTORY_REACTIONS_DESIGN.md's door
    (§2.1, Q6), INVENTORY_COUPLING_DESIGN.md §1.5's row, CELL_REPLACEMENT.md and PUMP_COMPOSITE.md.
- **Read only, no edit:**
  - `species_common.py`, which is shared with D150's operators, hands-off now;
  - `cell_replacement.py` and `src/cells/definitions/cell_replacement_spec.py`;
  - `compartments.py`, whose door R is unchanged.
- **The F owner: nothing.** A new law class in an existing module registers itself
  (`src/cells/operators/__init__.py`, its docstring).

### 4.7 Tests (D224)

**Uncompiled event rows** (tier 1, NumPy, in `test_site_occupancy.py`). The world has a template
newcomer at t_e, and an occupied outward and inward population on the replaced cell. The event maps
at t_e must show:
- the newcomer's B = θ′S and R = S − B, exactly;
- the facing outside node and the other cell's populations unchanged, bit for bit;
- W's departed amount equal to B before the event, its arrived amount equal to θ′S, and its
  exchange equal to ΔG from an independent NumPy evaluation;
- the owner's ledgers closing with W's terms.

Planted: W's external term dropped, so the bound ledger misses by A − D.

**Refusal rows** in `REFUSALS` (:184), each refused:
- a population on a replaced slot without W, with a message that names W;
- a contact population incident to a replaced slot;
- a template newcomer whose template declares no arrival occupancy;
- a donor copy onto a slot with populations;
- W without replacement@1;
- W before `site_occupancy@1`.

The existing case at :191–199 changes: a patch population there is admitted with W and refused
without it, and the contact case stays refused.

**D152:** `tests/unit/test_species_reactions_refusals.py:467` flips. Cell routes on replaced slots
are admitted with a template's multipliers and refused without them; outside routes compose, as
today.

**The multipliers at a replacement** (tier 1, NumPy, on the host's control values):
- the site multipliers switch from the founder's schedule to the template's at t_e, and a founder's
  change after its death is refused (in `test_site_occupancy.py`);
- D152's per-site multipliers do the same (in `test_species_reactions_refusals.py`).

**Part C′,** where chosen: in `test_species_regulated_availability.py`'s `REFUSALS` (:558), an
element on a replaced slot is admitted with a species or site source and refused with a state source
unless part C is chosen.

**One compiled acceptance world,** a new id in `tests/unit/test_site_occupancy_runs.py:39` (tier 2):
- **its world:** replacement@1, an occupied outward population on the replaced cell, and a D152
  reaction in that cell, under ARS at 1 ms, over a few tens of steps across t_e;
- **what it checks:** the runner passes every host check on every row, every ledger and the energy
  ledger included, and §4.8's identity holds on every row;
- **planted:** the identity recomputed without W's departed term misses at the event row by the
  departed B;
- **its seconds:** about 40–60 s. The file's two configurations take 76 s today;
- **its reason:** it is the request's minimal acceptance. The event rows cannot show the reaction
  running across the event.

The hosts named for tier 2 avoid `test_cell_replacement.py`, which is tier 3.

### 4.8 Acceptance: the balance equation

For each species s, on every row k, with i over the cells and finite outside nodes and p over the
populations binding s:

    Σ_i n_s,i(k) + Σ_p B_p(k)
        = Σ_i n_s,i(0) + Σ_p B_p(0)
        + S_res,s(k)                            supply from held baths (@3)
        + Σ_slots [supplied_s(k) − removed_s(k)]  replacement@1
        + Σ_p [A_p(k) − D_p(k)]                 W
        + Σ [produced_s(k) − consumed_s(k)]     D152

It holds within the composite's rounding allowance.

The request's three clauses:
- **"From its template":** B′ = θ′S, and the cytosol is the template's.
- **"Environment-owned material preserved":** the facing node is untouched by the event.
- **"Recorded":** D, A and replacement's records.

### 4.9 Division (FR-7's step), not designed here

- **The sites.** W writes the owner's pools through accepted writes. That is the path the
  composition note gives division (§4.4): the partition writes each owner's per-cell state through
  its declared interfaces, never by name. A site writer at division would split R and B by the
  patch's area fraction (SITE_OCCUPANCY_DESIGN.md §5.1) through the same accepted writes.
- **The coupling.** At a prescribed division its state is set by its own event after the
  partition's (INVENTORY_COUPLING_DESIGN.md §1.5, :386), the same shape as part C.
- So FR-26's declarations fit FR-7's division step in shape. The division's maps and bookings (C5,
  C6) belong to that note.

### 4.10 Price (S)

| Part | Agent-days |
| --- | --- |
| W: parse and templates, the occupant tables, the event map with its counter, records, ledger and magnitude terms, energy, summary, the narrowed `check_slots`, the multiplier tables; the upper end allows for the first writer of the site pools | 1.75–2.5 |
| Its matrix row and column | 0.25 |
| D152's occupant rule | 0.5–1 |
| Tests | 0.75–1 |
| Docs | 0.25–0.5 |
| **Development, recommended** | **3.5–5.25** |
| Part C′, a link in a replaced cell (needed only for that case, §5) | +0.25–0.5 |
| Optional: part C, the coupling's states | +0.75–1 |
| Optional: contact populations, after the ruling | +0.5–1 |
| Optional: donor copies | +0.5–1 |
| Instead of W: O + C5 | +1–1.5 |
| Instead of W: L | 7–10 in all |
| References and a registered protocol | +2–3 |

Calibration: D150's occupant rule was built with no new state from the same host tables
(SECRETED_SPECIES_TRANSPORT_DESIGN.md §5.2). Replacement@1's event bookings are the model for W's.

### 4.11 Questions for the user

1. **W** (recommended), or O + C5, O@2 or L (§4.3)?
2. **Part C:** include the coupling's states in version 1?
3. **Contacts:** at a contact's restart, does the material bound on the neighbour's side leave with
   the contact, or is it released to the neighbour?
4. **Donor copies with site populations:** version 1.1?
5. **Templates:** may a template change a population's capacity or constants (copies, α, k_on,
   k_off), or only its occupancy, as in version 1?
6. **The site and reaction multipliers at a replacement:** the newcomer's from its template (D150's
   rule; recommended), or the slot's schedule carried across occupants as an intervention on the
   slot?

## 5. Order, and the three in one world

**One requester sent all three** (D239), so the likely world holds a bath dose, binding sites, an
occupancy-linked reaction and a replacement together. After version 1:

| In one world | After version 1 | What it needs |
| --- | --- | --- |
| A bath dose beside binding sites | Composes | FR-23 |
| A reaction rate from a site population's occupancy | Composes | FR-24 |
| A replacement with occupied sites and reactions in the replaced cell | Composes | FR-26's W and D152's rule |
| A bath dose beside a replacement | Composes today (matrix 3↔17 ✓) | Nothing |
| The linked reaction in a replaced cell, its source a site population or a species of that cell | Refused by @2's element check (`species_regulated_availability.py:1347–1366`) | Part C′ (§4.3): definition-time, no state |
| The same, with a regulatory state as its source | Refused | Part C as well |
| All four together | Composes | FR-23, FR-24, W, D152's rule and C′; C as well if a state is a source |

So C′ is not optional for the one-world case.

**The order:**
- **FR-23 first:** it is the smallest and independent.
- **FR-24 next.** FR-7's judged run uses a frozen snapshot, so FR-24 does not wait for it (§3.6).
- **FR-26.** W touches `site_occupancy.py`, as FR-23 and FR-24 do, so the three take that file one
  branch at a time. D152's part and parts C′ and C are on other files and can run in parallel.

**The price of all three as recommended:** 7.25–10.25 agent-days of development, excluding gates;
7.5–10.75 with C′ for the one-world case. That is before the options, references and protocols.

**Each lands behind tiers 1 and 2,** with crossrev's FR set and G1. Integration grants no
acceptance (D143).
