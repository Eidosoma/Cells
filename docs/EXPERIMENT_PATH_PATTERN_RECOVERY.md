# E15: pattern recovery after damage (experiment path, backlog)

**Status: backlog, logged 13 November 2026 at the user's request.** It is
[E15](EXPERIMENTS.md#later-experiments) and is not active. This note records which engine
features the experiment would need, its question and a design sketch. No code, run,
protocol or engine change follows from it. Every candidate is deferred, not closed
([D151](DECISIONS.md#d151-every-reviewed-candidate-is-deferred-not-closed)). Run status
stays in [Progress](../PROGRESS.md), and the gates and their order are the
[current plan's](CURRENT_PLAN.md).

**Snapshot.** Written against main `ae278b4` on 13 November 2026. Three pieces of work were
then in flight on branches: S5a, the volume ledger and E07-v1's judged arms. Where this note
and Progress differ, Progress is current.

**Engine models it would run** (the AGENTS.md milestone rule):
- **Version 0** (§3): `resolved_pump_replacement@1`. That is `resolved_pump_composite@1`
  with `scheduled_cell_replacement@1` over `resolved_pump_tissue@3`, and junction formation
  `delayed_first_order_junction_formation@1`. It is E07-v1's engine model
  (`validation/tissue/e07_v1_protocol.json`). Optionally it adds
  `electrode_current_injection@1`.
- **Later versions** add the general operators of §1, each landed and qualified on its own
  gate first.

**The idea.** It comes from a synthesis of developmental-control frameworks that the user
pasted, which reads as another assistant's output. Its claims are unverified background:
none was checked for this note, and no feature or parameter rests on them. The synthesis
frames development as integrated multiscale control:
- gene regulatory networks read their inputs in the context of a cell's state;
- positional information (Wnt, BMP, SHH and FGF gradients) and Turing-type
  self-organisation coexist;
- epigenetic memory keeps regulatory states;
- mechanical and bioelectric feedback feed in.

Planarian regeneration is its example. The experiment it proposes:

> "Give identical cell populations the same gene regulatory network, progressively add
> positional signaling, mechanical coupling, bioelectric communication and persistent
> regulatory memory, and test which combinations generate **robust pattern recovery after
> damage**, rather than merely producing a pattern once. That distinction—between
> generating a form and *knowing how to restore it*—may be one of the most consequential
> questions in the field."

**Relation to *How Patterns Return*** ([10.5281/zenodo.23327869](https://doi.org/10.5281/zenodo.23327869)).
It goes only through what the repository states; the preprint was not read for this note.
- **The question.** The [project README](../README.md) asks which patterns and functions can
  be "expressed, repaired or reconstructed". This path asks the "expressed" against
  "repaired" contrast of a spatial pattern.
- **The open point.** [Experiments](EXPERIMENTS.md#future-experiments-pattern-information-error-sensing-and-corrective-action)
  records that the v2.2 working draft leaves autonomous maintenance open (its §8.3). A
  positive result would bear on that point within the model's scope.
- **What it would not show.** A return would not show that a tissue represents its target
  or selects its repair, as the same section notes. "Knowing how to restore it" is the
  quotation's phrase, not a testable claim.
- **What it is not.** The preprint's recorded Cells work is the
  [BITSEY lineage assays](ROADMAP.md#bitsey-replication), which this path neither reproduces
  nor extends.
- **For *Plastic Heredity*** ([10.5281/zenodo.22143269](https://doi.org/10.5281/zenodo.22143269)),
  a pattern that returns after its carriers are replaced (E07's renewal question) is one
  case of restoration.

## 1. The engine features it needs

**How to read the table.**
- **Family:** the layers do not share one world today. The heredity work runs on the pump
  family (`resolved_pump_tissue@3` and the composite). Cutting, injury and the reaction
  network run on older families. Mechanics and the regulatory circuits are standalone
  models. The general feature is usually an operator on the composite (D143), not a port of
  another family.
- **Standing:** each feature is marked in one of three ways:
  - **planned**: in a design or a plan;
  - **asked**: already put to the user in a review;
  - **new here**: raised by this path.
- **Other consumers:** a second consumer is the D144 evidence that a feature is general,
  not built for this experiment.
- **Design only:** no code in `src/cells` at `ae278b4` (grepped).

| # | Layer | Cells today (family) | Missing | General feature | Standing | Other consumers | Gate |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | Bioelectric communication | Pump family: `resolved_pump_tissue@3`; the composite with replacement, the formation law and injection (§1.1) | Junction abundance driven by activity or state; noise | (a) A regulated junction-channel population. (b) A noise operator on the composite | (a) Planned: the molecular-loop unit (D145). (b) Planned as a need (E07 tier 2), undesigned | (a) E07 renewal; S5 division; Cortés-Poza group 2. (b) E07 tier 2 | Molecular loop; composition |
| 2 | Positional signalling | Standalone `reaction_transport@1` (MG0a); prescribed prepatterns only (§1.2) | A secreted signal; a cell response to it; binding | (a) Secreted-species transport v1. (b) State-dependent secretion and a responder coupling. (c) The site-occupancy primitive | (a) Planned (D150; design only, code after S5a). (b) Asked (bone review, question 3); this path is its second consumer. (c) Planned as a requirement, undesigned | (a) GZMK review; ROADMAP item 9; MG4. (b) Bone review ranks 1, 2 and 5; MG4; Cortés-Poza's wound signal. (c) Kinetochore review; the Fgf8 sink case | Composition (after S5a); then the extracellular-environment entity |
| 3 | Self-organisation (reaction–diffusion) | Closed chemistry (`compartment_reactions@1`); `network_reactions@1` on the calcium-energy family, with its own species state (§1.3) | Driven nonlinear reactions on the inventory that transport moves | Reactions on the shared inventory: a composite operator that writes @3's species rows | **Decided:** designed as a general feature (user, 13 November; D152); a design note first | MG0c; GZMK review item 2 (catalysis on a substrate); the reaction–diffusion part of BITSEY parity | Composition (the ownership contract); a design note first |
| 4 | Gene regulation (the shared network) | Standalone `emt_mirna@1` and `emt_mirna_pair@1`; regulation factors on the calcium-energy family; nothing on the pump family (§1.4) | A regulatory network on the tissue family | A regulatory-network operator on the composite | Planned, **held** (D145) | Heredity Stage D; parity P8; the GRN wet-lab track; the REVERT plan; the partial-reprogramming benchmark (D151) | D145's hold; molecular loop |
| 5 | Persistent memory | The bistable heredity cell; slow ion loading; junction abundance (§1.5) | A regulatory memory with its own timescale; a booked change to one slow variable in place | (a) Row 4's slow nodes. (b) A declared, booked state-intervention event | (a) Planned, held (Stage D). (b) Planned as a deliverable (causal carriers), undesigned | (b) Coupled renewal's causal carriers; Cortés-Poza T6 | Coupled renewal |
| 6 | Mechanical coupling | Standalone `apical_vertex_mechanics@1` (MG1), coupled to nothing (§1.6) | Mechanics in the tissue world; mechanics → bioelectric; directed migration | (a) Mechanics as a composite operator on shared geometry. (b) A per-patch mechanical observable and a mechanically gated conductance. (c) Directed cell migration | (a) Planned (MG4; morphogenesis gaps 6–7). (b) Asked (bone review, question 2); this path is its second consumer. (c) **New here:** a gap (§1.6) | (a) MG4; the integrated tissue unit. (b) Bone review ranks 3–4. (c) The 24 October comparisons; field-directed migration (Zhao 2006) | Integrated tissue unit |
| 7 | Damage and regrowth | Pump family: an in-place swap and junction cuts. Removal and injury exist only on older families (§1.7) | Removal with a vacancy on the composite; regrowth | (a) S5a's partition and bridge closure. (b) The volume ledger, water plus replacement. (c) An excision operator for the composite. (d) Growth and endogenous division | (a) In flight (S5a branch); lands after the volume ledger. (b) In flight; first in the landing queue. (c) **New here** as an operator; the need is already named in two places. (d) Planned (the endogenous lifecycle, later) | (a) Division milestone 1; J2. (b) E07-v2's osmotic challenge; the renewal assay (D144). (c) ROADMAP injury (cutting, BETSE cutting parity); Cortés-Poza Phase 3; MG0a's "no excision contract". (d) MG3; E08 | Lifecycle operators; the endogenous lifecycle |
| 8 | Recovery readouts | `src/cells/assays/recovery.py`; E07-v1's null; MG0b's scoring (§1.8) | Pattern metrics beyond a D/H set | None in the engine (validation only) | – | E07-v1 and E07-v2's analyses; Cortés-Poza Phase 3 | The protocol |
| 9 | Timescales | Modes E and C exist (§1.9) | A qualified method for hours to days | Qualified multirate or quasi-steady methods (D135) | Planned (compute limits) | GZMK ageing; the E07 tier-1 cost; secreted species §8 | Compute limits |
| 10 | Execution scale | CPU and one L4; dense field solves (§1.10) | Measured GH200 cost; sparse solves | The field-solver interface | Planned (a proposed design) | The 825-node tissue; 2-D gradient sheets | Compute limits |

### 1.1 Bioelectric communication

- **Today (pump family).**
  - `resolved_pump_tissue@3` (`models/surface_pump_v3.py`): resolved membranes and field,
    Na/K and Ca pumps, NaV1.2, Kir2.1 and Kv1.5 populations, leaks, and voltage-gated
    junctions (`junction_voltage_relaxation@1`).
  - The composite `resolved_pump_composite@1` (`models/pump_composite.py`), with
    `scheduled_cell_replacement@1`, `delayed_first_order_junction_formation@1`
    (`processes/junction_formation.py`), water (`resolved_pump_water@1/@2`),
    `electrode_current_injection@1` and `membrane_entity_state@1`.
  - Runs and qualification (MG0b, the parity rungs, E07-v1): [Progress][P].
- **Designed:** E07-v1 ([design](E07_V1_DESIGN.md), D139) and E07-v2 (D151). Cortés-Poza
  Phase 1's T1–T6 run on @3 and are held (D145).
- **Missing.** The formation law restarts only at replacement, so junction abundance never
  responds to activity (Cortés-Poza group 2). `physiological_noise_perturbations@1` exists as
  arithmetic, but no model uses it (grep).

### 1.2 Positional signalling

- **Today.**
  - `reaction_transport@1` (`models/reaction_transport.py`, standalone): two synthetic
    species, one linear conversion, passive contacts and no source term. MG0a ran its
    gradient from a large-volume reservoir cell.
  - Prescribed prepatterns:
    - per-slot route values in @3 definitions and templates;
    - static regional profiles on older families;
    - `spatial_gradient_modulation@1`, used only by validation permeability schedules.

  None is a signal that a cell reads.
- **Designed: D150 version 1** ([design](SECRETED_SPECIES_TRANSPORT_DESIGN.md)).
  - Neutral species rows on @3's species axis, carried by the face law.
  - `scheduled_species_turnover@1` and `scheduled_species_exchange@1` are design only.
  - Rates are scheduled, uptake is a plain sink, the tissue is static, and a world has at
    most 7 species.

  ROADMAP item 9 (trafficking) is not started.
- **Why (b) matters here.** Under D150's rule that rates belong to the occupant (design §5.2,
  §11.5), refilling a source region with naive cells removes the source. A tissue can rebuild
  its source only if secretion depends on cell state. That is the synthesis's "positional
  information kept in existing tissue", and it needs (b).
- **Still undesigned:** the occupancy primitive (design §2.5 records its four
  requirements). Large 2-D gradient sheets need sparse field IDs (row 10).

### 1.3 Self-organisation

- **Today.**
  - `compartment_reactions@1` is closed mass action with detailed balance
    (`ideal_detailed_balance_mass_action@1`). A closed system relaxes to equilibrium and
    cannot hold a Turing pattern (**S**, our reasoning).
  - `network_reactions@1` (`processes/network_reactions.py`) has cited kinetics with Km
    terms, activators and inhibitors. It is wired only into
    `resolved_calcium_energy_regulated@1/@2`, through `network_control_factors@1`. It holds
    its own species state beside the physical inventory ([GZMK review](PAPER_REVIEW_GZMK_AGEING.md)
    item 2; secreted-species design §1.1).
  - `reaction_transport@1` is linear.
- **Designed:** MG0c is on the [ladder](MORPHOGENESIS_PLAN.md) with its check, the
  dispersion relation. [Progress][P] records MG0 complete with MG0a and MG0b.
- **The feature.**
  - An operator on the composite that writes @3's species rows at cells and outside nodes,
    with driven nonlinear kinetics.
  - It books work for driven steps and heat for spontaneous ones, and it composes with
    D150's transport.
  - The GZMK review's shared-state question is settled first.

### 1.4 Gene regulation

- **Today.**
  - `emt_mirna@1` ([reference](EMT_REFERENCE.md)) and `emt_mirna_pair@1`
    (`models/source_pair.py`) are a fixed miRNA/EMT circuit on a nominal clock, at most two
    cells. The reference's conventions are confined to the pair (D146, D149).
  - `network_reactions@1` regulates pumps, channels and junctions on the calcium-energy
    family. It was qualified on µs-scale transients
    ([archived progress](history/PROGRESS_BEFORE_2026-11-08.md)).
  - Nothing exists on the pump family.
- **Planned, held under D145:**
  - heredity Stage D, an expression carrier ([design](HEREDITY_FIRST_EXPERIMENT.md));
  - parity P8;
  - the [GRN wet-lab track](GRN_WETLAB_VALIDATION.md).
- **The feature.**
  - Nodes are cell state with one owner, in physical time.
  - Inputs and outputs are declared: voltage, free ions and signal concentration in;
    availability factors and production rates out.
  - Partition at division and reset or copy at replacement follow declared rules.
  - It is benchmarked out of process first, with approval per paper (D138).

### 1.5 Persistent memory

- **Today.**
  - The bistable heredity cell: a NaV1.2 window current with Kir2.1, H about −80 mV and D
    about −21 mV.
  - Slow ion loading over hours, junction abundance under the formation law, and channel
    gates.
  - `stationary_continuation_analysis@1` (mode E) finds the states and their stability.
  - A donor copy is an inheritance route (D139).
- **Planned:**
  - the coupled-renewal gate's causal-carriers and robustness deliverables
    ([current plan](CURRENT_PLAN.md#gate-coupled-renewal));
  - E07-v2 (D151);
  - Cortés-Poza T6's independent resets (held).
- **Missing.** Replacement@1 swaps a whole content, so one slow variable cannot be changed
  alone with its booking. The plan's rule is that "an event may replace a value, but books
  what it removed and supplied". Whether that change is a new operator or a template option
  is the coupled-renewal gate's design question.
- **A caution.** In Cortés-Poza Phase 0, the author model's slow memory erased its pattern
  rather than storing it. So a memory layer can lower recovery.

### 1.6 Mechanical coupling

- **Today.** `apical_vertex_mechanics@1` (`models/apical_vertex.py`) is a 2-D apical vertex
  model: Farhadifar energy, forces by `jax.grad`, overdamped, padded topology. It comes with
  `mechanical_equilibrium_analysis@1` and `junction_tension_inference@1`; MG1's status is in
  [Progress][P]. It is standalone, with no T1, growth or division.
- **Planned:** MG2 to MG4 and the plan's gaps 3, 6 and 7 ([morphogenesis plan](MORPHOGENESIS_PLAN.md),
  D134).
- **Asked:** the mechanics → bioelectric direction (bone review, question 2). Nothing
  mechanosensitive exists in `src`.
- **Directed migration into a lesion is a gap.**
  - MG2 sorts cells by tension through T1 transitions.
  - MG3 adds growth, division and death.
  - The plan's gap 5 is adhesion and polarity.
  - No rung moves cells up a chemical, electrical or mechanical cue.

  The 24 October comparisons already name migration as a repair actuator to block. A
  motility law would need its own sources and design note (D136, D142).

### 1.7 Damage and regrowth

- **Today (pump family).**
  - `scheduled_cell_replacement@1` swaps contents in place, by an isolated template or a
    donor copy, with no vacancy, release or uncoupling ([limits](CELL_REPLACEMENT.md#limits)).
    Its qualification, G2-Q1, is scoped to held-bath heredity worlds.
  - @3 has no excision. MG0b's cut is a junction closure
    (`validation/morphogenesis/mg0b_domain_wall.py`).
  - Scheduled availability pulses and `electrode_current_injection@1` perturb state without
    removing cells.
- **Today (older families).**
  - `conservative_tissue_removal_remap@1` (`processes/tissue_removal.py`) sits behind
    `resolved_tissue_excision@1`, `resolved_tissue_active_excision@1`,
    `resolved_calcium_excision@1` and the `resolved_calcium_energy_*_excision@1` models.
    Each cuts between checkpoints and rebuilds the field. Removed material leaves the system,
    and no wound surface forms.
  - `resolved_repair@1`–`@4`, with `prescribed_patch_injury_resealing@1`: fixed-geometry
    Na/K injury with prescribed resealing.
- **In flight at the snapshot** (not on main at `ae278b4`):
  - S5a's `isopotential_partition@1` and `cytoplasmic_bridge_closure@1`
    ([S5 design](CELL_DIVISION_S5_DESIGN.md)), landing after the volume ledger;
  - the volume ledger, water plus replacement (`scheduled_cell_replacement@2`;
    [composite v2](PUMP_COMPOSITE_V2_DESIGN.md) §2), first in the landing queue.
- **New here: an excision operator for the composite.** The need is already named twice:
  - in the ROADMAP's [injury table](ROADMAP.md#injury-and-repair), under actual cutting and
    replacement;
  - in Cortés-Poza Phase 3: a lesion removes cells and their junctions as an engine
    operation, with ledgers.

  Regrowth is growth plus endogenous division (the lifecycle gate's milestone 2).

### 1.8 Readouts

- **The existing pieces:**
  - `src/cells/assays/recovery.py`, a sampled return with a hold (an observer only);
  - E07-v1's copy-only null (`validation/tissue/e07_v1_turnover.py`);
  - MG0b's Jaccard scoring.
- **Validation-side work:** metrics for gradients, wavelengths and shapes (AGENTS.md).

### 1.9 Timescales

`stationary_continuation_analysis@1` (mode E) and `projective_forward_euler@1` (mode C)
exist, and mode B comes later (D135). Their qualification status is in [Progress][P]. At
1 ms, one hour is 3.6 million steps. The compute-limits gate owes a verdict on long-time
methods.

### 1.10 Execution scale

- **Today:** CPU and one L4, with batched worlds. Field solves are dense node-space
  solves, bounded at 2,048 nodes by the dense IDs.
- **GH200 access** is expected by about 20 November 2026 (D145).
- **The [field-solver interface](FIELD_SOLVER_INTERFACE_DESIGN.md)** is proposed, with no
  code, and waits for the GH200 numbers.

## 2. The question

**Withdrawal applies to driver-supplied inputs only.** Restoration is tested after the
driver's cues, scheduled sources and prepatterns have been withdrawn. A standing tissue
mechanism, such as a Turing layer or a state-dependent source, stays on, because it is part
of what is tested. If a driver-supplied input is still present after damage, a return is
generation again. MG0a and MG0b each recorded that their cut-and-restore tested the
machinery, not memory ([runs][R]).

**Each layer combination is scored three ways:**

| Outcome | Test |
| --- | --- |
| Generates | From a naive tissue, a declared transient cue writes the pattern, or a self-organising layer forms it without one |
| Maintains | Without damage, after withdrawal, the pattern holds over the window |
| Restores | After withdrawal and damage, the pattern returns to a declared agreement by a declared time, holds, and beats a paired null |

- **The negative result.** A combination that generates and maintains but does not restore
  is the quotation's "producing a pattern once". That result is informative.
- **Needed for maintenance, not restoration.** A layer whose removal breaks maintenance is
  needed for maintenance. With memory off and the cue withdrawn, no pattern is left to
  damage, so restoration cannot be assessed that way.
- **Switching off at the damage.** A layer switched off at the damage time (a scheduled zero
  rate) separates its role in restoration from its role before damage, though not from its
  role during recovery.

**Two kinds of return**, scored separately for standing mechanisms:
- **same-instance return:** slot-wise, two-sided agreement with the pre-damage pattern
  over all original slots;
- **same-class return:** the class re-forms (wavelength, peak count or gradient length),
  possibly in new positions. That is re-generation of the class.

**A positive restoration result** needs, under a protocol registered before its runs:
- the generates and maintains scores;
- a return that beats a paired null. The null is passive relaxation, or the damage's own
  refill rule, as in E07-v1's [copy-only null](E07_V1_DESIGN.md#4-the-copy-only-null);
- a declared place where the rebuilding information is held: slot route values,
  templates, a kept source or the driver. Recovery from supplied information is its own
  class;
- robustness across seeds, lesion sizes and positions, and parameter draws.

A collapse to a uniform state is never a return (Cortés-Poza Phase 0).

**Controls.** Most come from the 24 October comparisons in [Experiments](EXPERIMENTS.md):
- the same layers without damage, and a sham damage;
- damage with each layer inert in turn;
- no cue and no damage, giving no spontaneous pattern;
- a supplied answer, declared: a positional input that fixes each slot's state, or the cue
  re-applied to the lesion;
- a timing-matched open-loop replay of the cue into the lesion;
- **matched appearance, different history**, under the same damage. This separates
  **history-held** recovery, where the return depends on retained state beyond the present
  pattern, from **attractor-held** recovery, where any history with the same present state
  returns.

## 3. Design sketch

**Populations and layers.**
- **Identical cells:** every cell carries the same declared laws and parameters.
- **Inert off states:** each layer's off state is inert in the engine's sense, a zero rate
  or no routes (D136).
- **Batching:** where an operator promises bitwise idleness at zero rate, arms that differ
  only in a layer's rates share a batch signature and run as batched worlds.
- **Order:** the engine's order is not the quotation's. Bioelectric communication and memory
  exist now, positional signalling comes next, and mechanics last (§4).

**Version 0 is E07-v2 arms plus spatial lesions, not a second protocol.**
- **E07-v2's frame.** E07-v2 drafts the write–clear–challenge rules on E07-v1's world,
  driver and null ([current plan](CURRENT_PLAN.md#gate-coupled-renewal)).
- **The added challenges.** Version 0 adds spatial lesions, inside the written domain or
  across its boundary:
  - **block refills:** a block of slots replaced at one time by naive isolated templates.
    The parser admits one event per slot and time. Whether a dense block lies inside
    G2-Q1's scope is unverified;
  - **state lesions:** a scheduled availability pulse of the cue's kind, or
    `electrode_current_injection@1`, in the same regions.
- **When it is settled:** when E07-v2 is drafted after E07-v1's analysis, under E07-v2's own
  rules. Each challenge registers a no-turnover control, fits inside the fixed-volume window
  and is checked not to be the mark again.
- **Layers it has:**
  - the coupling s and the formation law;
  - the heredity cell's intrinsic bistability;
  - optionally, a prescribed prepattern as a supplied-answer control. Replacement keeps
    the slot's route values unless a template declares them, so a prepattern is declared
    either slot-held (it survives any refill) or carrier-held (the templates declare uniform
    values).
- **What it is not:** the proposed experiment. It has no regulatory network, no secreted
  signal and no mechanics. The heredity cell's law set stands in for "the same network"
  and is labelled so.
- **World and window:** E07-v1's held-bath 127-cell sheet on CPU, with 1-D chain screens
  first.
  - Damage and recovery fit E07-v1's fixed-volume window, with every judged record within
    70 min of the cue.
  - Otherwise those arms wait for the volume ledger to land, bringing water plus
    replacement.

**Readouts** (observers only):

| Readout | Definition |
| --- | --- |
| Pattern metric | Two-sided Jaccard of the declared state label over all original slots; wall position and width; gradient length; wavelength and peak count |
| Fidelity | The metric at the judged record, against the pre-damage pattern and the paired undamaged run |
| Recovery time | From damage to the first sustained return (`src/cells/assays/recovery.py`) |
| Persistence | Hold after the return; the return after a second damage |
| Robustness | The fraction of worlds that recover; the run is the unit (E07-v1 §6) |
| Residue and cost | Full-state differences after a returned label; osmotic loading, pump work, material moved |

## 4. Order of features

1. **Already in flight:** the volume ledger (water plus replacement), then S5a's partition
   and bridge closure. E07-v1's analysis comes next, then E07-v2. Version 0 rides on these.
2. **D150 v1** (composition, after S5a): a measurable gradient with no response yet.
3. **A responder side and state-dependent secretion,** if the user takes them (bone review,
   question 3).
4. **Reactions on the shared inventory** (D152), designed first, with MG0c as their
   qualification case.
5. **The gene-regulation layer,** when D145's hold lifts.
6. **The new lifecycle piece, an excision operator for the composite;** then growth and
   endogenous division for regrowth.
7. **Mechanics as a composite operator,** with both coupling directions; directed migration
   once it is sourced.
8. **Long-time methods, GH200 and the field-solver interface.**

Each step is a general feature with its own design note (D142), qualification and gate. A
version of E15 is registered only after the features it uses have qualified.

## 5. What not to do

- **Build nothing for this experiment** (D144): no regeneration operator, no planarian
  polarity law and no species named Wnt or BMP.
- **Reproduce no paper's model without approval** (D138, restated in D151).
- **Start no held track** (D145): the GRN track, Cortés-Poza Phase 1 and catalogue stage 3
  stay held.
- **Every candidate is deferred, not closed** (D151). E07-v1's registered protocol stays
  as it is.
- **Put no missing physics in a driver** (AGENTS.md), and do not relabel channel
  bistability as a gene regulatory network.
- **Do not count a slot-held prepattern as tissue-held positional information**, a collapse
  to a uniform state as recovery, or a recovery as evidence that the tissue "knows" its
  target.
- **Do not treat the synthesis's claims as verified**, and run nothing now.

## 6. Questions

**Rulings taken by the lead (13 November 2026):**
- The path is E15, a row in the [later-experiments table](EXPERIMENTS.md#later-experiments).
- Version 0's protocol is drafted with E07-v2, after E07-v1's analysis.
- D150 v2 (state-dependent secretion and a responder side) and the mechanics → bioelectric
  direction are already pending with the user, from the
  [bone review](PAPER_REVIEW_BONE_MECHANOSENSING.md) (its questions 3 and 2). This path is
  recorded as their second consumer and does not ask again.

**The user's answer (13 November 2026):** yes. Reactions on the shared inventory, for
Turing-type self-organisation and MG0c, are designed as a general feature (D152).

**To settle when the path is activated:**
- the overlap with Cortés-Poza T6 and Phase 3, both held;
- the first damage kind, and whether removal with a vacancy (the excision operator) is
  wanted;
- whether a prescribed prepattern is acceptable as a labelled supplied answer;
- version 0's stand-in for "the same network";
- the biological anchor: planarian polarity on fixed geometry (D134), or the wing disc;
- whether windows of minutes to hours are acceptable for the first versions.

**Sources.** Repository documents and code only, at `ae278b4`. Nothing was fetched from the
web. The log is `/mnt/workspaces/Cells/experiment-path-pattern-recovery-20261113-01/HANDOFF.md`.

[P]: ../PROGRESS.md#plan-betse-parity-on-cpu-and-l4-then-jupiter-from-8-november
[R]: ../PROGRESS.md#runs
