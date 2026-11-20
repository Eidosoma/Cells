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

**C, host-side.** A validation tool reads each window's per-step history (the runner's
`RunResult.history`, one row per accepted step). At each step:
- a node's losses and its outgoing transfers split over the cohorts by the node's composition at the
  step's start (well mixed, age-independent);
- a transfer carries its source node's composition;
- new material joins the cohort the study's label schedule names.

This is exact for first-order laws, except for the split of inflows within a step, which is first
order in dt. `validation/gene_regulation/cohort.py` (on the gene regulation lane) is its one-pool
case. An in-step tracer operator would need to read other operators' accumulators within the step.
That is a contract question for the operators owner, and R1 does not need it.

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
