# Cohorts and age classes within a species row: design options (FR-33, FR-25's follow-up)

## The gap

**What the records name today:**
- every loss record names its node and its species row: `turnover_cleared_fmol` [species, cell],
  `turnover_outside_cleared_fmol` [species, outside node], and the reactions' consumed amounts;
- every transfer names its route, and so its patch, face or junction.

So region-selective loss is already named, by node (docs/LABELLED_PROTEIN_READOUTS.md).

**What nothing names** is a population within one row: a cohort, by the time its material was made
(a pulse label) or by its region of origin, and an age class.

**Who needs it:**
- **FR-33:** which population lost material under region-selective loss (D251);
- **FR-25's paused follow-up:** the surviving cohort under age- or region-selective loss. Its window
  survivors are recovered today only for one well-mixed pool with age-independent loss (D251).

**Two different needs:**
1. **Bookkeeping cohorts.** The laws do not read the label: who is where, and who was lost where.
   The row's dynamics are unchanged.
2. **Age classes whose loss depends on age.** Older material is cleared faster, so the dynamics
   change and the classes must be state.

## Requirements

- **R1.** Each cohort's amount per node, and its own loss and transfer records.
- **R2.** Age classes, with first-order ageing and a loss rate per class.
- **R3.** A label is not chemistry: the same standard potential and the same moiety weights.
  Relabelling moves material between no moieties.
- **R4.** A world without cohorts runs bit for bit as today.
- **R5.** The material and energy ledgers close with every new move.

## Options

| Option | What it is | Meets | Not met, or the cost |
| --- | --- | --- | --- |
| **A. Label rows by hand** (today's workaround) | Each cohort its own species row, every law declared on each row with equal parameters (the example at 60cf2364) | R1 under first-order laws that ignore the label; R4; R5 | Nothing checks that the duplicated declarations agree. Every label row counts against the cap of 16 species per world (FR-9, D165). No ageing route (R2). The registry sees unrelated species, so R3 is unchecked |
| **B. A cohort axis in @3's state** | Every species field gains an index, [species, cohort, node]. Every law reads the totals and splits its moves by share | R1, R2, R3, R5. Nonlinear laws too | Every operator, @3's laws, the field solver's amounts, the ledgers, the checkpoints and the run view change. R4 holds only if every reduction stays unchanged at a cohort axis of length 1. Several weeks across every owner |
| **C. A passive tracer beside the row** | Cohort shares driven by the movers' per-step records: turnover's cleared and produced amounts, exchange's moved amounts, the reactions' consumed and produced amounts, @3's face and junction transfers | R1 with no law touched, and R4 trivially | Not R2: the tracer changes no flux |
| **D. Declared label families, and an ageing route** | The registry declares rows as labels of one species, and a new operator moves material between them at first order | R1, R2, R3, R4, R5, under laws that act on each row alone and linearly | A saturable or mass-action law on a family member would saturate per row, not on the total. Version 1 refuses that at the definition |

**C, host-side** (built: `validation/regions/readouts.py`, `trace`). A validation tool reads each
window's per-step history (the runner's `RunResult.history`, one row per accepted step). At each
step:
- a node's losses and its outgoing transfers split over the cohorts by the node's mean composition
  over the step (well mixed, age-independent);
- a transfer carries its source node's split;
- new material joins the cohort the study's label schedule names.

**C's limits:**
- **Only one-way records.** C is right only where the per-step records carry the direction of every
  labelled movement. Turnover's and exchange's do, since each route moves one way. A two-way law's
  net record does not.
  - **The case** (a review finding, 20 November 2026): two equal nodes exchanging by diffusion keep
    both totals, and the face's net flux, at 0, while labelled material crosses one way and
    unlabelled the other. A tracer of net records saw no movement and kept 0.1 fmol of label on
    the right, where an explicit label row reaches 0.299999 (0.3 by the closed form).
  - **So the built tracer refuses, at setup,** any face, junction or patch that moves the species,
    and it fails closed on everything else (`check_movers`; the review of 21 November 2026):
    - every operator law it neither reads (turnover and exchange) nor lists as shown inert
      (`SHOWN_INERT`: laws whose declarations write no species amount, provide no amount view and
      close no node) is refused, with its reason (`REFUSED`);
    - a law in no list is refused until it is classified there;
    - every declared kind is refused;
    - a charged species is refused: its channel, pump and membrane fluxes are in-step laws the
      tracer does not read, and they can be two-way.
  - The rule before it looked for an operator's species field. The wash
    (`scheduled_compartment_wash@1`) declares nodes, not species, so it passed: the tracer kept all
    60 fmol of the well's label while the wash took 30 of it. The region export shares the check.
- **The split.** At a node with no inflow and no production it is exact for any step, since a
  starting cohort's survival (1 - r)/(1 + r), with r = O/S the step's outflow against the node's
  start and end amounts, equals n1/n0 there. Where material flows in during a step, a split by the step's
  starting composition would be first order in dt. The built tracer splits by the mean of the
  start and end compositions, the trapezoid, which is second order:
  - its error is set by the inflow within a step relative to the node's amount: 1.3e-6 against
    the closed form at a 1 ms step, where the node first receives its own amount each step
    (tests/unit/test_region_readouts.py);
  - **where the node gains material, r must stay small** (the review of 21 November 2026). At a
    steady node the survival is the (1,1) Pade form of e^(-2r). At r = 1 it reads 0, where the
    truth is e^(-2) = 0.135, and above 1 it is negative: a steady 1 fmol pool made and cleared at
    4 per second gave -0.333 fmol for e^(-4) = 0.018316 in one 1 s step, and the closure check could
    not see it;
  - **a node that sends material along a route needs the bound too,** though its own split stays
    exact, because its arrivals shape its receiver's split. A donor draining most of itself in
    one step (r = 0.76) into a receiver at r = 0.01 put 9.4e-4 of the receiver's amount on the
    wrong cohort in that one step;
  - so the tracer refuses a step with r above 0.01 at a node that gains material or sends it
    along a route, and reports the largest such r.
  - At that bound, measured on 15 closed-form scenarios (`validation/regions/readouts.py`, "The
    resolution"), each step adds at most 7.61e-6 of the node's amount to a starting cohort's
    error. Over each run the cohort stays within 5.6e-4 of its exact amount, relative to itself.
  - The example's largest r is 1.0e-3.
- **The returned rows are checked:** each cohort non-negative and the cohorts summing to the
  node's amount at every row, on the returned dictionary. The tracer's own cohort names,
  `unlabelled` and `produced`, are refused as a caller's: a caller's `unlabelled` cohort was
  replaced by the tracer's own on export.
- **Label switches** must fall on step boundaries; the tracer refuses one that does not.

**Tracing through two-way transport is engine work:**
- **The label carried by the transport law itself.** Label rows (A, or D's families) do this today
  for faces, junctions and patches: each row diffuses or permeates down its own gradient. D1 would
  check that a family's rows carry equal transport coefficients, about 0.5 day more. A net flux on
  Fick's law has no gross components, so for diffusion this is the only way.
- **Directional records from a two-way law** that has them: the forward and backward extents of
  `local_species_reactions@1`'s passive routes, booked separately, about 1 day for the operators
  owner, plus the tracer reading them.

`validation/gene_regulation/cohort.py` (on the gene regulation lane) is C's one-pool case. An
in-step tracer operator would need to read other operators' accumulators within the step. That is
a contract question for the operators owner, and R1 does not need it.

**D, in three parts:**
- **D1: label families in the species registry.** A family is {id, rows}. The registry checks equal
  standard potentials and equal moiety weights across a family (R3), and the readouts sum it. Each
  label row stays an ordinary row, so every law, ledger and energy term is unchanged (R4 by
  construction). The registry's forms do not fit: they partition a row at rapid equilibrium through
  a closure, and cohorts must never equilibrate.
- **D2: an ageing operator,** `scheduled_species_progression@1` (a neutral name).
  - **Its routes:** first-order, from one family row to another at a node. Ageing from class c to
    c + 1 runs at rate m/τ, giving an Erlang age structure.
  - **Its step:** exact over each half-step, n' = n e^(−kh), booked in its own accumulators per
    route and node.
  - **Its energy:** signed work, as turnover's is. Between rows of equal potential, a move changes G
    by RT ln(c_to/c_from) per molecule: the label-mixing term, an accounting artefact of a
    bookkeeping partition, declared as such. It can run uphill, so it is not heat.
  - **What it gives:** age-selective loss is then turnover's clearance per class row, which exists
    today. The field naming the population that lost material is the existing per-row loss record,
    read at the label row.
- **D3 (optional): one declaration per family.** A route declared on a family applies to each of its
  rows, under one schedule, so the copies cannot diverge.

**Pulse labelling into a family row:**
- turnover's production routes, one per row, with complementary schedules: this exists today;
- templated_polymerisation@1 releasing into a label row by schedule: that is FR-25's G4 follow-up, on
  the gene regulation lane.

## Recommendation

1. **C, host-side, now,** for FR-33's pulse-labelled cohorts under first-order loss. It needs no
   engine change.
2. **D1 and D2 next,** when a study needs age-selective loss (FR-25's follow-up).
3. **D3 when a world declares many label rows.**
4. **Not B now.** Its generality (nonlinear laws on labelled material) has no consumer yet.

## Files and owners

Owners are those of docs/CORE_SEAMS_STEP0.md §4.2.

| Piece | Files | Owner |
| --- | --- | --- |
| C | A new tool in `validation/` and one test row (D224) | The FR lane that takes it |
| D1 | `registry/species_registry.py`: families, their checks and their sums | Binding owner |
| D2 | `operators/species_progression.py` (new), with its NumPy ΔG test; its registration in `operators/__init__.py` | Operators owner; F owner for the registration |
| D3 | The composite's parse (`definitions/pump_composite_spec.py`) | Operators owner |
| Run view (optional) | Family totals and a named region set, `records/run_view.py` | @3 owner |
| FR-25's release into a label row | `operators/templated_polymerisation.py` | Gene regulation lane |

## What stays bit for bit

- **Every world that declares no family and no progression route.**
  - D1 is a definition check that such a world never reaches.
  - D2 is a new module that no current world composes.
  - C runs host-side.
- **Crossrev's sets and G1's worlds**, so their gates need no declared difference.
- **In a world that does declare a family**, material transport and every ledger are exact: the
  rows' moves sum to the unsplit species' move. But each row's heat is booked as its own row's, so
  a family's booked face heat can differ from the unsplit species' (the Lean lane, 22 November
  2026). At a parent of 1 mM on both sides, with labels at 0.9/0.1 and 0.1/0.9, the unsplit species
  books no face heat, and the two rows book 2 × 0.8 ln 9 RT per unit of the face's rate constant.
  Physical heat attributable to the labels alone is unverified.

## Price, in agent-days

| Piece | Days |
| --- | --- |
| C: the tool, the study's export of its region, one test row | 1–1.5 |
| D1 | 0.5–1 |
| D2: the operator, its NumPy ΔG test, kernel rows and one world test | 2–3 |
| D3 (optional) | 1 |
| The run view's family totals and region sets (optional) | 0.5 |
| Gates: about 0.5 per landing that changes src | 1 |

**C, D1 and D2 together: 4.5–6.5.** With the options: 6–8.
