# Abundance to function in the composite, and the closed loop's unit (FR-7, design)

> **Legacy cleanup (25 November 2026, D386).** Paths under `src/cells/legacy/` and the older model
> IDs named below left the engine. The tag `pre-cleanup-2026-11-25` keeps them.

*Status: proposed, 18 November 2026, for the lead and the user (D216). Docs only. Nothing is built,
and nothing is scaffolded before the user has discussed the options (the user's rule of
14 November). The lead ruled on the note's three questions for the lead on 18 November (§6.1,
§6.2, §8). The rulings can be revised, and the user's four questions stay open. Code was read at
main 5133a850 and is cited `file`:line by today's path under `src/cells/`; D188's move 2 has not
landed. Tags: **(code)** read in the code; **S** this note's own reading, derivation or proposal.
Other statements cite their source.*

**Engine models it runs** (AGENTS.md): none. Every option would run `resolved_pump_composite@1`
over `resolved_pump_tissue@3`, with `membrane_entity_state@1`, `species_regulated_availability@1`
and `scheduled_species_turnover@1`. §5 names the further operators, existing and proposed.

**What is asked.**
- **D216:** "Design notes for FR-2, FR-7 and FR-8 follow. FR-7 needs the user's choice of the
  closed loop's unit, framed by its note."
- **FR-7, from the requesting study** (D163; registered as a consumer by D177). It asks for no new
  scope. When the closed molecular-to-physiology loop's unit is chosen:
  - **(a)** the loop admits a production rate driven by a declared species (FR-6 item 2), not only
    a scheduled one;
  - **(b)** a factor's source may be a population's abundance, not only a species concentration.
    This is the requester's narrowing of 14 November, after the coupling note's channel target.
- **The standing default (D145).** The molecular-loop unit is "provisionally the junction-channel
  population, which both renewal and division consume; confirmed at that gate". So the user's
  question is to confirm it or to change it.

**Basis.**
- CURRENT_PLAN's gate "a closed molecular-to-physiology loop".
- The [coupling note](INVENTORY_COUPLING_DESIGN.md): §1.3, §1.4, §1.12, §2.1, §6.4 and §7.2.
- The [core-seams note](CORE_SEAMS_DESIGN.md) §2 and §4, and its [step 0](CORE_SEAMS_STEP0.md)
  §4.2 (the owner table).
- The [composition note](OPERATOR_COMPOSITION_DESIGN.md) (D191).
- The [heredity experiment](HEREDITY_FIRST_EXPERIMENT.md) and [E07-v2](E07_V2_DESIGN.md) §3.
- FR-2's note, [MEMBRANE_RETRIEVAL_DESIGN.md](MEMBRANE_RETRIEVAL_DESIGN.md), and FR-8's,
  [LONG_DURATION_MODE_DESIGN.md](LONG_DURATION_MODE_DESIGN.md).

## 0. Summary

1. **The gate asks for seven things in one material account** (§1): regulated production, a finite
   precursor, assembly and trafficking delays, insertion and removal, a quantitative
   abundance-to-function relation, partition at division, and a measured response they predict.
2. **Four candidates** (§2, §3):
   - **U1, the junction-channel population** (D145's default). Its abundance today is the relative
     abundance of `delayed_first_order_junction_formation@1`. That is a ledger-free fraction that
     relaxes to 1 after each replacement, not a material count **(code)**.
   - **U2, a membrane channel population on `membrane_entity_state@1`,** which the code suggests.
     Its units are entity state with a ledger. Insertion writes them, the partition splits them,
     and the view already maps them to conductance, P a A = P N/ρ_ref **(code)**. Nothing removes
     them until FR-2.
   - **U3, the redistribution populations** (`resolved_redistribution@1/@2`). They have lived in
     `src/cells/legacy/` since D188's move 1 **(code)**, so choosing them means re-expressing them
     (D167, D196).
   - **U4, the coupling operator's regulatory state.** It is not admissible as the gate's unit: it
     has no material account, and its persistence is the declared 1/k_off.
3. **The request's reading is corrected (code).** It says the abundance-to-function relation "is
   state only in `resolved_redistribution@1/@2`". In fact `membrane_entity_state@1`'s units are
   state in the composite, with a linear relation to conductance.
4. **Heredity is measurable only if persistence is not built in** (§4).
   - The unit needs its own declared removal, so that its lifetime is a closed-form null.
   - The template needs a measured clearance.
   - Any persistence beyond the unit's lifetime must run through a declared feedback that can be
     cut.
   - The mark and the function are scored apart (E07-v2's rule (c)).
5. **The recommendation (S, §5): close the first loop on U2, then carry the same pieces to U1 for
   the coupled-renewal question.**
   - U2 needs the fewest new pieces, all on the qualified composite path.
   - U1 needs those pieces and more: a junction population as material state, the
     contact-maturation process and newborn integration.
   - D145's default stands until the user rules.
6. **Part (a) is the coupling note's operator rate route (§2.1). It is not built** (§6.1).
   - It edits the operators owner's files: `contract.py`, `pump_composite*.py`,
     `species_turnover.py` and `species_reactions.py`.
   - **The lead's ruling (18 November):** it is step B1′ of the core pass, after B1, with the
     operators owner (D216, amended 18 November; CORE_SEAMS §13's table). It goes ahead only if
     the user's answer to question 2 admits the loop.
   - The kinds' routing door (INNER_MODEL_V4_DESIGN §7.4 (n), built for FR-5) is a different
     mechanism.
7. **Part (b) is a source kind of the coupling operator** (§6.2).
   - **Its source, by the lead's ruling:** a population's absolute density N/A, a count per µm²,
     with its unit declared and K in the same unit. It is read through D191's current read of the
     view.
   - A count and a self-source are refused. A constant source is reported in the run's
     declarations, not refused.
8. **Questions for the user** (§8):
   - the unit: confirm D145, or change it;
   - whether the species → control → production loop falls inside D145's narrowed hold (the
     coupling note's open §6.4 Q2);
   - synthetic or measured lifetimes for the first acceptance;
   - the measured response the loop must predict.
9. **Effort (S, rough):** about 10–16 agent-days to close U2's loop, beyond FR-2 and composition's
   milestones. U1 adds about 8–14 (§7).

## 1. The gate

CURRENT_PLAN's gate "a closed molecular-to-physiology loop":

| Deliverable | Completion evidence |
| --- | --- |
| One regulated functional-unit population | A regulated production rate; a finite precursor inventory; assembly and trafficking delays; insertion and removal; a quantitative abundance-to-function relation; partition at division |
| One material account | All of these reconcile in one account and predict a measured physiological response |

- **"One material account" is ARCHITECTURE's target "one authoritative account per physical
  quantity".** A population's units and the precursor species they are made from would resolve to
  one species identity and one conserved total.
  - Today a population's units have their own entity ledger, `membrane_entity_state@1`'s
    `population_abundance_entity`, and no species ledger counts them **(code)**.
- **FR-7 asks only** that the chosen loop admit (a) and (b).

## 2. What the composite holds today

| Piece | What it is | Where |
| --- | --- | --- |
| Units of a channel population | N per population, as anchored increments, with the ledger `population_abundance_entity` and the domain N ≥ 0 | `operators/membrane_state.py`:151 **(code)** |
| Its abundance-to-function relation | The view's `channel_abundance` = a₀A₀/A + dN/(A ρ_ref). So @3's conductance P a A = P N/ρ_ref is linear in units at any area: "A fixed number of units keeps its conductance ... whatever the area" | `membrane_state.py`:12–15, :158 **(code)** |
| Writers of units | Insertion@1 and @2, dN = ρ r h with their area; the partition, by the patch's fraction | `membrane_insertion.py`:407; `partition.py`:24–26 **(code)** |
| Removers of units | None: insertion refuses a negative rate | `membrane_insertion.py`:198 **(code)** |
| A species-driven factor | `species_regulated_availability@1`: F ∈ [b, 1] on @3's junction or channel availability, from a cell's species concentration (a Hill law) or a regulatory state | `species_regulated_availability.py`:81, :863 **(code)**. The channel target is qualified for gate-free populations (A5, 15 November; FR-6 item 1's status of 18 November) |
| A rate route to another operator's control | Designed in the coupling note's §2.1. Not built: no `ROUTABLE_CONTROLS` anywhere in `src/` | **(code)** |
| A population-abundance source | Recorded as a door of the coupling note's §1.3. Not built | Coupling §7.2 item 4 |
| Production | `scheduled_species_turnover@1`: a scheduled P (fmol/s) of a neutral species at a cell, with exact half-steps and signed work | `species_turnover.py`:1–30 **(code)** |
| Junction abundance | `delayed_first_order_junction_formation@1`: A = 1 − (1 − A₀) e^(−max(0, age − lag)/τ), "a modelling choice loosely consistent with the cited time courses, not a fit". Replacement@1 owns it, and it multiplies the junction's availability | `laws/junctions/junction_formation.py`:1–25; `cell_replacement.py`:28–31 **(code)** |
| Mobile surface populations | `resolved_redistribution@1`, neutral leak populations whose "local permeability is background + reference permeability × local density / reference density", and `@2`, Na/K ATPase populations. Both live on fixed patches with lateral drift and diffusion, and their law performs "No synthesis, removal, membrane crossing" | `legacy/models/surface_redistribution.py`:1–7; `legacy/numerics/membrane_redistribution.py`:1–10 **(code)** |

**Two walls bear on every candidate (code):**
- **The coupling refuses providers of volumes and masks, and closers of masks** (`CONFLICTS_VIEW`,
  `species_regulated_availability.py`:864). So it refuses insertion@1 and @2, which provide masks,
  and the partition, which closes them (coupling §1.12).
  - A regulated population that is inserted and partitioned therefore needs D191's general
    composition first: composition's M1, then the coupling's own current reads, on the pattern of
    M3.
  - A writer of units that provides no mask and no volume composes as it stands (**S**). FR-2's
    note designs its first version that way.
- **Replacement@1 and membrane state refuse each other.** Replacement provides `channel_abundance`
  and refuses any provider of `membrane_area` (`cell_replacement.py`:624–634). Membrane state
  provides both (`membrane_state.py`:186).

## 3. The candidates, against the gate

| Gate item | U1: junction-channel population | U2: membrane channel population | U3: redistribution populations | U4: regulatory state |
| --- | --- | --- | --- | --- |
| Abundance as material state | No. A is a fraction with no ledger, filling to 1 after a replacement | **Yes:** units, with an entity ledger | Yes, in fmol per patch, in a legacy family | No: kinetic state with no free energy (coupling §1.5) |
| Regulated production | New: junction units produced, routed by (a) | New: (a) on a producer of units | New, after re-expression | Its own kinetics, of a fraction |
| Finite precursor | New | New: a precursor species row that assembly consumes | New | None |
| Assembly and trafficking delays | The formation lag, for newcomers only | New: an assembly lag, or a trafficking pool (FR-1's compartment with FR-2's two directions) | New | A first-order lag only |
| Insertion and removal | New: docking at contacts, and removal of plaques | Insertion exists. Removal is FR-2's | Lateral movement only | — |
| Abundance → function | New: a factor on junction availability from both cells' abundances, by (b) with side "both" | **Exists:** linear conductance in the view. (b) is needed only across populations | Exists, in the legacy family | Exists: F of s |
| Partition at division | The partition maps contacts, each with its a_e | **Exists:** units split by the patch's fraction | Not in the composite | A carry rule is a door (coupling §1.5) |
| Walls | Replacement owns A today; newborn contacts need the maturation process (coupling §3.3–§3.4) | D191's composition with the coupling; replacement beside membrane state | D196: rebuilt on the modular path first | — |
| What renewal and division consume | **Both** (D145's reason) | Division; renewal after a replacement door | — | — |

**U4 is not admissible as the gate's unit (S).**
- Its only account is kinetic, so the gate's "one material account" cannot hold.
- Its persistence is a parameter. With k_off = 0 it is "a saturating integrator of the input"
  (coupling §0 item 5), so a written state would last by construction.
- It stays what it is: a regulation inside the loop, not the unit.

**U3 is not recommended (S).**
- Its abundance is material, but it lives in a legacy family that runs outside the composite.
- Re-expressing mobile surface populations is new work with no consumer today.
- Pumps as the unit would come instead through seam B's capacity as state (CORE_SEAMS §4.5 item 3;
  composition's M6), on the modular path.

## 4. Heredity: what makes "does the response outlive the template?" measurable

*Plastic Heredity* asks two things about an acquired state
([HEREDITY_FIRST_EXPERIMENT.md](HEREDITY_FIRST_EXPERIMENT.md)): "Once the signal that caused it is
gone, does the cell keep it?" and "When those cells die and are replaced by new ones, does the state
pass on?" FR-7 asks the first at the molecular scale: a transient template changes an abundance,
which changes a response.

**Requirements on the unit (S):**
1. **Its own removal, declared.** The unit's abundance must have a removal law with a declared
   rate, so that its decay after the template is a closed form. That decay is the null against
   which "outlives" is measured.
   - An integrator (k_off = 0) lasts by construction, and an instantaneous factor ends with the
     template by construction. Neither measures anything.
   - Today no channel unit is ever removed. With U2 as built, every inserted unit would persist: a
     built-in "yes". FR-2's removal, or a turnover of units, comes first.
2. **A template with a measured clearance.** The template is its own species, cleared by D150's
   turnover, or released and degraded in FR-1's compartment. "After the template" starts at a
   measured clearance time: E07-v2's rule (a), "clearance is measured, not fixed".
3. **A response that @3 computes:** Vm, a junctional current or a conduction time, computed from the
   unit's function, each with one observation owner (D154's run view).
4. **Persistence beyond the lifetime only through a declared path that can be cut.**
   - An example: an ion, then a regulatory state, then a rate route on the unit's production. Ions
     enter through a state only (coupling ruling 1).
   - Its cut (`coupling_controls`) is the control.
   - Persistence is then a measured outcome, never an assumption.
5. **The mark and the function scored apart** (E07-v2's rule (c); D151): the retained abundance,
   and the response to a post-release challenge.
6. **For the second question, inheritance at the unit's own scale.** The unit is extensive at
   division, where the partition splits units, and owned by the occupant at replacement, so a
   newcomer arrives without it.
7. **A horizon of several lifetimes.**
   - Connexin half-lives of 1.3–5 h are cited in `laws/junctions/junction_formation.py` (Beardslee et al.
     1998; Fallon and Goodenough 1981; not read for this note).
   - At 1 ms that is about 4.7–18 million steps per half-life (**S**: 3.6 million steps per hour).
   - So a judged run at measured lifetimes waits for FR-8. A first numerical acceptance uses
     declared synthetic lifetimes, labelled as such.

**Against the candidates (S):**
- **U2 meets 1–5 once FR-2's removal and (a) exist,** with Vm as the response. It meets 6 through
  division. Its second question through replacement needs a door: replacement beside membrane state
  (§2's wall), with the occupant rule for units.
- **U1 meets 6 most directly.** Junctions are what renewal and division consume (D145). E07-v1's
  written disc did not renew under donor-copy turnover, and the coupling's effect was far smaller
  than predicted (CURRENT_PLAN, the coupled-renewal gate), so coupling is the open carrier. U1 meets
  1 only once its abundance is material, with production and removal.
- **U4 fails 1** (above).

## 5. Recommendation (S)

**Close the first loop on U2, and carry the same pieces to U1 for the coupled-renewal question.**
- **U2 is the composite's own functional-unit population.** Its units, their ledger, their
  partition and their linear conductance are on the qualified path today. The loop adds a template,
  (a) on a producer, a precursor, removal (FR-2) and the material link.
- **Every piece U2 needs, U1 needs too:** the rate route, a producer with a precursor and a delay,
  removal, and one material account. U1 then adds:
  - a junction population as material state, on seam B's junction host (CORE_SEAMS §2's host
    table);
  - (b) with side "both";
  - the coupling note's contact-maturation process (§3.3) and newborn integration (§3.4).
- **So the order costs U1 nothing,** and the first loop closes earlier, with Plastic Heredity's
  first question measurable per cell.
- **If the user confirms D145 instead,** the same pieces are built first as U1's prerequisites, and
  the gate's judged loop waits for U1's own pieces.

**U2's loop, as a sketch (S):**
1. **A template species T,** dosed or produced, and cleared by D150's turnover. FR-10's bath
   schedule or FR-1's compartment release supplies it where the route of entry matters.
2. **(a):** a rate route from a Hill activation of T to the production rate of a precursor species
   (D150's production), or to a unit producer's rate.
3. **A unit producer (new):** precursor → units of a declared population on a patch, first order in
   the precursor, after a declared assembly lag. It books the precursor's moved amount and the
   units in one material account. It provides no mask and no volume, so it composes with the
   coupling as it stands (§2).
4. **Removal:** FR-2's retrieval with its population move, then degradation of the internalised
   units in a compartment.
5. **The partition at division,** unchanged.
6. **The response:** Vm, from the population's conductance.
7. **Feedback, when declared:** an ion through a regulatory state into the producer's rate, by (a),
   with its cut as the control.

## 6. The two doors

### 6.1 Part (a): the operator rate route

- **What it is:** the coupling note's §2.1 rate route.
  - A target operator declares `ROUTABLE_CONTROLS = {control: "rate"}`.
  - The coupling declares `target: {"operator": ..., "control": ..., "ids": [...]}` with a §1.3
    law.
  - The factor F ∈ [b, 1] multiplies the scheduled rate. It is evaluated in the target's own
    half-steps, from the state each half-step receives, so the route is second order (coupling
    §2.1, **S**). Where the target itself moves the route's species source, it is read at the
    half-step's midpoint, which keeps the route second order. The scheduled rate is therefore the
    maximum.
- **Energy:** the target books as today. A factor on D150's production is the same object as a
  scheduled production (coupling §2.1).
- **Not the kinds' door.**
  - The routing door of INNER_MODEL_V4_DESIGN §7.4 (n) carries factors from source kinds into
    kinds' control slots at every stage. It is built (FR-5), and CORE_SEAMS §4.3 extends its sinks
    to @3's channel availability.
  - A D150 or D152 rate is an operator's control, evaluated in that operator's half-steps. So (a)
    needs the operator route.
- **Its files, against CORE_SEAMS_STEP0 §4.2's owner table:**

  | File | Change | Owner in the pass |
  | --- | --- | --- |
  | `operators/contract.py` | `ROUTABLE_CONTROLS`, and the routed control passed to a target's half-steps | Operators owner |
  | `models/pump_composite*.py` | Routes wired at build; a route to an undeclared control refused; the per-operator static branch | Operators owner |
  | `operators/species_turnover.py`, `species_reactions.py` | Their routable controls declared | Operators owner |
  | `operators/species_regulated_availability.py` | The `operator` target in the declaration | Not in the pass ("named, not edited by the pass") |

- **What the note found.** D216 assigned "FR-6's routing door" to seam B1. But B1's operator part,
  as CORE_SEAMS §13 and STEP0 §4.2 wrote it, is lifecycle by roles, refusal 4 per move, and the
  composite's refusal lifted for kinds with roles. It does not name the rate route.
- **The lead's ruling (18 November 2026, revisable).**
  - The rate route is **step B1′** of the core pass, after B1, with the operators owner. It edits
    that owner's files: `contract.py`, `pump_composite*.py`, `species_turnover.py` and
    `species_reactions.py`.
  - It goes ahead only if the user's answer to question 2 (§8; D145's hold) admits the species →
    control → production loop.
  - It is recorded in D216's amendment of 18 November and in CORE_SEAMS §13's table, whose B1′ row
    carries the coupling note's estimate: 6–10 agent-days with the event trigger.
  - Every file above then has one owner, the operators owner, and the coupling's side follows in
    its own module.
- **The hold.** The loop it closes, species → control → production, is the coupling note's open
  question for the user (§6.4 Q2): inside D145's narrowed hold, or after the gene-regulation
  decision? FR-7's (a) is that loop, so the question is the user's before (a) is built (§8).

### 6.2 Part (b): a population's abundance as a factor's source

- **Where it lives:** a source kind of the coupling operator (§1.3's door, recorded in §7.2 item 4),
  in `species_regulated_availability.py`, outside the pass.
- **The read:** D191's rule A.
  - The coupling declares a `current` read of the view's `channel_abundance`, resolved to the
    current value wherever `membrane_entity_state@1` composes.
  - Its factors need the view passed to `control_factors`, which today receives none (coupling
    §1.1). That change is composition's M1 (C1–C4), the operators owner's.
- **The variable: the absolute density ρ = N/A, a count per µm²** (the lead's ruling, 18 November
  2026, revisable). Its unit is declared, and K is declared in the same unit.
  - *The ruling's reason:* it is the physical quantity, with nothing hidden. A world that wants a
    threshold relative to the declared reference density sets K = K_rel·ρ_ref itself.
  - *What the note had proposed:* the relative density a = N/(A ρ_ref), @3's own view field, with K
    relative to ρ_ref. The two are equivalent through that substitution.
  - *At the read,* ρ = a·ρ_ref, from the view's current `channel_abundance` and the population's
    declared reference density (`membrane_state.py`:158).
  - *Why a density, not a count (S).* The coupling note rejected amount sensing for species,
    because a half-saturation is a concentration (§1.3). The surface analogue is a density. A count
    would make the factor depend on the host's size, so a count is refused.
  - *What a density keeps (S).* It is unchanged by insertion at the declared density and by a
    division with a = f, so neither event moves the factor by itself.
- **Evaluation time.** Units change only in writers' half-steps and event maps, never inside @3's
  step (**S**, from §2's writers). So an instantaneous factor on them is exact under the held
  evaluation, as one on a neutral impermeant species is (coupling §1.4).
- **Refusals (S):**
  - **a self-source:** a factor on population k's availability from k's own abundance. The view
    already carries k's linear abundance-to-function relation, so a self-factor would count it
    twice;
  - a count as the source variable (above);
  - a source outside the target's cell, or outside a contact's two cells (§1.3's locality).
- **A constant source is reported, not refused** (the lead's ruling, 18 November 2026, revisable).
  - A source population that no declared writer changes is a legitimate world: a fixed
    population.
  - The run's declarations record it as "constant source: the factor cannot vary in this run", so
    that no reader takes it for a live loop.
- **Its uses:** one population setting another's availability (an auxiliary subunit, or a regulator
  of a pump), and U1's junction availability from both cells' hemichannel abundances, with side
  "both" (§1.3's product).

## 7. Order, owners and effort (S, rough)

| Piece | Owner | Needs | Agent-days |
| --- | --- | --- | --- |
| (a) the rate route | Operators owner, step B1′ (D216, amended) | B1; the user's answer to question 2 | 3–5 for the route alone (**S**); CORE_SEAMS §13's B1′ row carries the coupling note's 6–10, with the event trigger |
| (b) the abundance source | The FR lane, in the coupling's module | M1's view in `control_factors` | 1–1.5 |
| The unit producer and one material account | The FR lane, in a new operator module. The species identity goes with the binding owner (`species_registry.py`), and membrane state's ledger with the operators owner | (a); F's operators section | 3–5 |
| Removal | FR-2's note | FR-1; seam B | FR-2's |
| The coupling beside insertion and the partition | Operators owner (D191) | M1, on M3's pattern | Composition's |
| Code-blind references and the protocol | A references agent; the FR lane | The pieces | 2–3 |
| **U2's loop** | | | **about 10–16, beyond FR-2 and composition** |
| U1's extra pieces: junction units on seam B's host, (b) with side "both", contact maturation | Seam B; the coupling note's §3.4 | U2's pieces | about 8–14 |

- **Not before** the user's answers (§8), D188's move 2 and the core-seams pass, whose owners hold
  these files (D195, D213).
- **The first acceptance is numerical** (D138). It runs against code-blind references of the
  linear chain T → precursor → units → conductance, under refinement, with synthetic lifetimes.
  Then comes a registered protocol.
- **A biological comparison** needs a measured response, registered on its own (D151).

## 8. Questions

**For the user:**
1. **The unit.** Confirm D145's junction-channel population as the first loop? Or change it to a
   membrane channel population (U2) first, with U1 next, as recommended? Or another unit?
2. **The hold.** Is a species → control → production loop within D145's narrowed hold? This is the
   coupling note's §6.4 Q2, still open, and FR-7's (a) is that loop.
3. **Lifetimes.** For the first acceptance, declared synthetic lifetimes of minutes, labelled, so
   that it runs at the fine engine's cost? Measured lifetimes of hours would wait for FR-8.
4. **The measured response** the loop must later predict: one channel's abundance against Vm, or
   coupling against conduction (Track E's data, D155 item 2)?

**For the lead, ruled on 18 November 2026** (revisable; recorded in §6.1 and §6.2):
5. **The operator rate route:** step B1′ of the core pass, after B1, with the operators owner. It
   goes ahead only if the user's answer to question 2 admits the loop (D216, amended 18 November;
   CORE_SEAMS §13's table).
6. **(b)'s variable:** the absolute density N/A, a count per µm², with its unit declared and K in
   the same unit. A world that wants a relative threshold sets K = K_rel·ρ_ref itself.
7. **A constant source in (b):** reported, not refused. The run's declarations record "constant
   source: the factor cannot vary in this run". The count and self-source refusals stay.

## Sources

- The code, read at main 5133a850, as cited.
- Connexin half-lives: as cited in `src/cells/laws/junctions/junction_formation.py`. The papers were not
  read for this note.
- No web search was made, and no external file was fetched.

## 9. The user's answers (18 November 2026; D217, D218)

These hold before any build, and the details are in D217 and D218.
- **U2 first,** a membrane channel population, then U1. The estimate is 10–16 agent-days, beyond
  FR-2 and composition. The abundance source's live integration needs composition's M1.
- **The first acceptance** runs on synthetic minute-scale lifetimes, labelled as such. It covers
  finite unit turnover, several declared lifetimes, and template clearance measured from the
  trajectory:
  - the criterion is declared before the run;
  - its threshold is meaningful for the template's remaining drive;
  - there is a rule for falling back below it;
  - releasing compartments are included;
  - "not cleared" is a valid outcome.
- **Qualification of the closed loop.** The closed-loop capability is not called qualified until a
  closed feedback case passes with a feedback-cut control. Persistence is measured, not required. The
  linear chain (§7) is a first check only.
- **The loop itself** (question 2) is admitted under D218, through B1′, with its evaluation timing and
  operating range declared. It is verified with a reference, timestep refinement and the cut control.
  The self-source refusal is built with (b).
