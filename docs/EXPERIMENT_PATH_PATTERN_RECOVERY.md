# Experiment path: pattern recovery after damage (backlog)

**Status: backlog, logged 13 November 2026 at the user's request. Not active.** This note
records a question, a design sketch and the engine features the question would need. No
code, run, protocol or engine change follows from it. Every candidate here is deferred,
not closed ([D151](DECISIONS.md#d151-every-reviewed-candidate-is-deferred-not-closed)).
Current status stays in [Progress](../PROGRESS.md), and the gates and their order are the
[current plan's](CURRENT_PLAN.md).

**Engine models it would run** (the AGENTS.md milestone rule):
- **Version 0** (§4): `resolved_pump_composite@1` over `resolved_pump_tissue@3`, with
  `scheduled_cell_replacement@1` and its junction law
  `delayed_first_order_junction_formation@1` (together, `resolved_pump_replacement@1`).
  Optionally it adds `electrode_current_injection@1`.
- **Later versions** add the general operators named in §3. Each lands and qualifies on
  its own gate first.

**Where the idea comes from.** A synthesis of developmental-control frameworks that the
user pasted, which reads as another assistant's output. Its scientific claims are treated
as unverified background. None was checked against sources for this note, and no engine
feature or parameter rests on them. Its framing, in short:
- development is integrated multiscale control, in which gene regulatory networks read
  their inputs in the context of a cell's state;
- positional information (morphogen gradients such as Wnt, BMP, SHH and FGF) and
  self-organisation (Turing-type reaction–diffusion) coexist;
- epigenetic memory keeps regulatory states, and mechanical feedback and bioelectric
  regulation feed in;
- collective anatomical control is an open question;
- planarian regeneration is the example: positional information is kept in existing
  tissue, with Wnt and BMP central and bioelectric signalling as a further layer.

The experiment it proposes, which the user asked to log:

> "Give identical cell populations the same gene regulatory network, progressively add
> positional signaling, mechanical coupling, bioelectric communication and persistent
> regulatory memory, and test which combinations generate **robust pattern recovery after
> damage**, rather than merely producing a pattern once. That distinction—between
> generating a form and *knowing how to restore it*—may be one of the most consequential
> questions in the field."

**Relation to *How Patterns Return*** ([10.5281/zenodo.23327869](https://doi.org/10.5281/zenodo.23327869)).
It goes only through what the repository already states; the preprint was not read for
this note.
- **The question.** The [project README](../README.md) puts it as: how do experience,
  retained cellular state and tissue organisation affect which patterns and functions can
  be expressed, repaired or reconstructed? This path's distinction, generating a pattern
  against restoring it, is that question's "expressed" against "repaired", asked of a
  spatial pattern.
- **The open point.** [Experiments](EXPERIMENTS.md#future-experiments-pattern-information-error-sensing-and-corrective-action)
  records that the local v2.2 working draft leaves autonomous maintenance and valuation
  open (its §8.3). A positive result here would bear on that point, within the model's
  scope.
- **What it would not show.** It would not show that a tissue represents its target or
  selects its repair. The same section says: "A decrease in observer-defined
  reconstruction error does not, by itself, establish that the system represents that
  error or autonomously selects its repair." "Knowing how to restore it" is the
  quotation's phrase, not a claim this path can test.
- **The preprint's recorded Cells work is different.** It is the BITSEY lineage assays
  ([BITSEY replication](ROADMAP.md#bitsey-replication)) on the miRNA/EMT circuit: writing,
  retaining and transmitting a cell state to fresh carriers. This path neither reproduces
  nor extends them.
- **For *Plastic Heredity*** ([10.5281/zenodo.22143269](https://doi.org/10.5281/zenodo.22143269)),
  the bearing is through renewal. A pattern that returns after its carriers are replaced
  (E07-v1's question) is one case of restoration; an acute lesion is another.

## 1. The question

**Generation and restoration, operationally.**
- **Generation.** From a naive tissue, the layer combination produces the pattern: by a
  declared transient cue (as E07-v1 writes a D disc), or with no cue for a self-organising
  layer (MG0c's Turing case).
- **Restoration.** The pattern exists, and **every generator has been withdrawn**: the cue
  is off, and any prescribed source is either removed or kept as a declared input. Then a
  declared damage is applied, and the pattern returns without further external
  instruction.
- **Why withdrawal matters.** If the generator is still present after damage, a return is
  generation again, not recovery. Both earlier cut-and-restore tests recorded this
  ([Progress](../PROGRESS.md), 9 November):
  - MG0a's linear steady state is unique, so its cut tested the machinery, not memory;
  - at MG0b's coupling the return was "close to guaranteed", so its cut also tested the
    machinery.

**A positive result** for a layer combination L, under a protocol registered before its
runs, needs all six:
1. **Maintenance.** Without damage, L keeps the pattern over the window. This is the
   precondition: without it, "recovery" is undefined.
2. **Return.** After damage, the pattern returns to a declared two-sided agreement with
   the pre-damage pattern, over all original slots, by a declared time, and holds for a
   declared time.
3. **It beats the null.** The return exceeds what passive relaxation, or the damage's own
   refill rule, gives. The null is paired on the same schedule and draws, in the spirit of
   E07-v1's copy-only null ([E07-v1 §4](E07_V1_DESIGN.md#4-the-copy-only-null)).
4. **It needs L.** The same damage, with each layer of L set inert in turn, does not
   recover by the same criteria.
5. **No supplied answer.** Where the rebuilding information is held is declared: slot
   route values, templates, a kept source or the driver. Recovery from supplied
   information is reported as its own class, a positive control, not as tissue-held
   recovery.
6. **Robust.** It holds in a declared fraction of worlds across seeds, lesion sizes and
   positions, and parameter draws.

**A negative result.** L generates and maintains the pattern but does not restore it: the
damaged region stays changed, or the pattern erodes or spreads. This is the case the
quotation calls "merely producing a pattern once". It is informative: a valid negative
result may complete a milestone ([Roadmap](ROADMAP.md#updating-this-roadmap)).

**Outcome classes to keep apart** (the [common contract](EXPERIMENTS.md#common-experimental-contract)
and [measurements](EXPERIMENTS.md#measurements)):
- **Returned with hold; returned without hold; did not return; collapsed to a uniform
  state.** A collapse to all-D or all-H is never scored as recovery. Cortés-Poza Phase 0
  found the author code's switching rule counting collapse to uniform depolarisation as a
  switch ([test plan](CORTES_POZA_2026_TEST_PLAN.md)).
- **The label against the full state.** A returned label is not necessarily an identical
  full state (composition, junction abundance).
- **Re-patterning of supplied cells against autonomous regrowth.** A scripted refill
  re-patterns newcomers that the schedule supplies. Autonomous regrowth needs growth and
  division, which come later (§3, row 7).

**Controls:**
- **The same layers without damage:** undamaged runs from the same start, and a sham
  damage (the same schedule with no effect, or no events, bitwise identical to the
  undamaged run).
- **Damage without the layer:** each layer set inert in turn, with the same damage and the
  same draws.
- **No cue and no damage:** no spontaneous pattern. E07's draft validity gate allows
  spontaneous D in at most 1 world in 32.
- **A supplied answer:** a positional input that fixes each slot's state, or the cue
  re-applied to the lesion. This is the 24 October brainstorm's "controller explicitly
  given the correct anatomy", with its supplied information declared.
- **A timing-matched open-loop replay:** the cue replayed into the lesion at a fixed time.
  It tells tissue feedback from a preset schedule (the 24 October table).
- **Matched appearance, different history:** two worlds matched in their present pattern,
  with different retained history, under the same damage (the 24 October table's first row;
  the E04 extension).

## 2. Design sketch

**Populations.** Identical cells carry the same declared laws and parameters, homogeneous
as E07-v1's heredity cells are. A declared heterogeneity is added later, for robustness.
"The same gene regulatory network" is the quotation's premise, but Cells has no regulatory
network on the tissue family today (§3, row 4). Version 0 therefore uses the shared
bioelectric cell law set as the cells' intrinsic state network, and it is labelled as
**not yet the proposed experiment**.

**The layers, and what "off" means.** Each layer's off state is inert in the engine's own
sense: a law at zero rate, or one with no routes. That is D136's rule that the default
engine is unchanged when a model is off. Where an operator promises bitwise idleness at
zero rate (the secreted-species design's idle claim 2, §7), arms that differ only in a
layer's rates share one batch signature. The factorial then runs as batched worlds.

| Layer | On | Off (inert) |
| --- | --- | --- |
| Positional signalling | A declared source region secretes a signal that cells read (needs D150 v1 plus a responder, §3). Version 0 has only a prescribed prepattern of route values, which is supplied positional information | No source; uniform route values |
| Mechanical coupling | Cells share a vertex-model geometry whose state feeds transport (needs the integrated tissue unit, §3) | Fixed geometry |
| Bioelectric communication | Gap junctions at a declared coupling s; newcomers form junctions by the formation law | s = 0 (junction availability 0) |
| Persistent memory | A slow state with a declared timescale that outlives its write. In version 0 that is the heredity cell's intrinsic bistability; later a regulatory memory (§3) | Monostable cells, or the slow state clamped |
| Self-organisation (named by the synthesis, not by the quotation) | Reaction–diffusion on the shared inventory (§3, row 3) | No reactions |

**Where positional information is held (version 0).** A replacement newcomer keeps the
slot's route values unless its template declares them ([CELL_REPLACEMENT.md](CELL_REPLACEMENT.md)).
A prescribed prepattern of route values can therefore be held two ways, and both are
declared:
- **slot-held:** templates declare no route values, so the position stays with the slot
  (the geometry) and survives any refill. That is a supplied answer;
- **carrier-held:** templates declare uniform route values, so every newcomer arrives
  positionally naive.

Under D150's rule that rates belong to the occupant (design §5.2, §11.5), a secreting
source region that is refilled with naive cells loses its source. Whether the remaining
tissue can make a new source is then the "positional information kept in existing tissue"
question. It needs state-dependent secretion (§3, row 2).

**Damage, by kind.** Each is declared, with its ledgers.
- **Ablate and refill.** A block of slots is replaced at one time by naive isolated
  templates, and their junctions restart the formation law (`scheduled_cell_replacement@1`).
  - The parser admits one event per slot and time, so a block lesion parses.
  - Whether a dense block lies inside G2-Q1's qualified scope is **unverified**. It must be
    checked before a judged run.
  - It models newcomers in place of the lost cells, not a wound: there is no vacancy, no
    release of contents and no uncoupling ([limits](CELL_REPLACEMENT.md#limits)).
- **State lesion.** A transient perturbation erases the pattern in a region without
  removing cells: a scheduled permeability or availability pulse of the cue's kind, or
  `electrode_current_injection@1`.
- **Communication lesion.** Junctions are closed across a line and reopened later. This is
  MG0b's cut, through @3's junction availability schedule.
- **Removal with a vacancy, and regrowth.** These come later, on the lifecycle gate (§3,
  row 7).

**Progressive addition, then factorial.** Following the quotation, layers are added one at
a time to the base (identical cells, the same network). Then the full factorial of the
layers that exist at that time is run, every cell of it under each damage kind and its
controls. The engine cannot supply the layers in the quotation's order (§4): bioelectric
communication and memory exist now, positional signalling comes next, and mechanics last.

**Readouts.** All are observers, never mechanisms. `src/cells/assays/recovery.py` is the
existing classifier for a sampled return with a hold.

| Readout | Definition |
| --- | --- |
| Pattern metric | Two-sided Jaccard of the declared state label over all original slots, against the pre-damage pattern. Also the domain-wall position and width (MG0b); for a gradient, the decay length and boundary position (MG0a); for self-organisation, the dominant wavelength and peak count (MG0c) |
| Recovery fidelity | The pattern metric at the judged record, against the pre-damage pattern and against the paired undamaged run at the same time |
| Recovery time | From damage to the first sustained return: agreement at or above the threshold, held for the declared time |
| Persistence | Hold time after the return; and the return after a second damage (repeated damage, as Cortés-Poza Phase 3 plans) |
| Robustness | The fraction of worlds that recover, across seeds, lesion size and position, parameter draws and challenges (NaV block, injected current). The run is the unit; nothing is pooled per cell (E07-v1 §6) |
| Full-state residue | Composition and junction-abundance differences after a returned label |
| Cost | Osmotic loading or volume change, pump work, and material supplied and removed |

**The minimal world first.** That is E07-v1's held-bath 127-cell sheet on CPU, or smaller
for screening: MG0b's 1-D chain, or a 37-cell disc.
- **Cost** (from [E07-v1 §5](E07_V1_DESIGN.md#5-arms-seeds-and-budget), **S** our
  arithmetic). 7.7 ms per step with two units at 5 ms steps is about 1.5 h of wall time per
  hour of model time per world. A screen of 24–40 runs of an hour each is then about 35–60
  core-hours, E07-v1's order.
- **The fixed-volume budget.** At fixed volume a D lineage loads K and anions at about 2%
  osmotic excess per 10 min of D residence. E07-v1 therefore judges every arm within
  70 min of the cue ([E07-v1 §2](E07_V1_DESIGN.md#2-donor-copy-content-composite-v2-2-decision-4)).
  Writing, retention, damage and recovery must fit that window. Otherwise the path waits
  for water plus replacement, which the composite refuses today (the composition gate).
- **The 825-node tissue** needs GH200 access or a qualified long-time method
  ([current plan](CURRENT_PLAN.md#gate-coupled-renewal)).

## 3. Feature-gap table

**How to read it.**
- **Family** names the model family a piece lives on. The layers do not share one world
  today:
  - the heredity work runs on the pump family (`resolved_pump_tissue@3` and the
    composite);
  - injury and cutting run on the older resolved-tissue and calcium-energy families;
  - mechanics and the regulatory circuits are standalone models.
- **The general feature is usually an operator on the composite** (D143), not a port of
  another family.
- **"Design only"** means no code in `src/cells` (grepped on `ae278b4`).
- **"Open question"** means a choice put to the user in a review, not a plan.

| # | Layer | Cells today (family; IDs; files) | Designed or planned (document; decision) | Missing | General engine feature needed (D136, D144) | Prerequisite and gate |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | Bioelectric communication | **Pump family.** `resolved_pump_tissue@3` (`models/surface_pump_v3.py`): resolved membranes and field, Na/K and Ca pumps, NaV1.2, Kir2.1 and Kv1.5 populations, leaks, voltage-gated junctions (`junction_voltage_relaxation@1`, `processes/junction_gate.py`). The composite `resolved_pump_composite@1` (`models/pump_composite.py`) with `scheduled_cell_replacement@1`, `delayed_first_order_junction_formation@1` (`processes/junction_formation.py`), water (`resolved_pump_water@1/@2`), `electrode_current_injection@1` and `membrane_entity_state@1` | E07-v1 registered, not run ([E07_V1_DESIGN.md](E07_V1_DESIGN.md); D139); E07-v2 (D151); Cortés-Poza Phase 1, T1–T6 on @3 ([test plan](CORTES_POZA_2026_TEST_PLAN.md); **held**, D145); the molecular-loop unit, provisionally the junction-channel population (D145) | Junction abundance that depends on activity or state: the formation law only restarts at replacement (Cortés-Poza group 2's connexin turnover). A mechanically gated conductance: none in `src` (row 6). Stochastic perturbation on @3: `physiological_noise_perturbations@1` exists as arithmetic, but no model uses it (grep), and E07 tier 1 has no noise | A regulated junction-channel population: abundance as state, production, turnover, insertion and partition. Optionally, a noise operator on the composite with stable-owner draws, for robustness | Composite v2 landed (composition); the molecular-loop gate; noise under composition |
| 2 | Positional signalling (a secreted signal) | **Standalone:** `reaction_transport@1` (`models/reaction_transport.py`): two synthetic species, one linear reversible conversion, passive contacts and no source term; MG0a's gradient from a large-volume reservoir cell on fixed tissue passed (9 November). **Prescribed prepatterns:** per-slot route values in @3 definitions and templates; static regional profiles (older families, for example `resolved_tissue_static_profiles@1`); `spatial_gradient_modulation@1` (`processes/spatial_modulation.py`), used only by validation permeability schedules. None is a signal that a cell reads | D150 secreted-species transport, version 1 ([design](SECRETED_SPECIES_TRANSPORT_DESIGN.md)): one inventory on @3's species axis, valence 0, carried by @3's face law. Its two operators, `scheduled_species_turnover@1` and `scheduled_species_exchange@1`, are **design only**. Rates are scheduled, not regulated; uptake is a plain sink; the tissue is static; at most 7 species. About 6 agent-days, code after S5a; the first acceptance is numerical (Pomreinke 2017, radial world). ROADMAP item 9: secretion as the morphogen source (trafficking, not started) | (a) State-dependent secretion. (b) A responder side: a species concentration modulating a declared law in the receiving cell. Both are **open questions to the user** ([bone review](PAPER_REVIEW_BONE_MECHANOSENSING.md), question 3), not plans. (c) The site-occupancy primitive (receptor binding): **undesigned**; design §2.5 keeps the door open. (d) Sparse field IDs for 2-D gradient sheets of about 10⁴ nodes | A state-dependent source law and a concentration-to-availability responder coupling, as composite operators. Fluxes add and availabilities multiply (the plan's combination rules). Then the general site-occupancy primitive | D150 v1 lands (after S5a; composition); then the extracellular-environment entity. Sparse IDs: compute limits (the field-solver interface) |
| 3 | Self-organisation (reaction–diffusion) | **Standalone:** `compartment_reactions@1`, closed mass action with detailed balance (`ideal_detailed_balance_mass_action@1`). A closed system relaxes to equilibrium and cannot hold a Turing pattern (**S**). **Calcium-energy family:** `network_reactions@1` (`processes/network_reactions.py`; cited kinetics with Km terms, activators and inhibitors) is wired only into `resolved_calcium_energy_regulated@1/@2`, through `network_control_factors@1`. It holds **its own species state beside the physical inventory** ([GZMK review](PAPER_REVIEW_GZMK_AGEING.md), item 2; secreted-species design §1.1). `reaction_transport@1` is linear | MG0c, "Turing patterning at the predicted wavelength", is on the [ladder](MORPHOGENESIS_PLAN.md) with its check (the dispersion relation; only k = nπ/L on zero-flux domains). PROGRESS records no run (MG0 is complete with MG0a and MG0b) | Driven, open, nonlinear reactions acting on the same inventory that transport moves, at cells and outside nodes. Energy is booked as work for driven steps and as heat for spontaneous ones | A reaction operator on the composite that writes @3's species rows (one inventory), composing with D150's transport. The GZMK review's shared-state question is settled first | D150 v1; the ownership contract (composition); a design note first (D142) |
| 4 | Gene regulation (the shared network) | **Standalone:** `emt_mirna@1`, the isolated miR200/Zeb/ZEB equations, nominal clock ([EMT_REFERENCE.md](EMT_REFERENCE.md)); `emt_mirna_pair@1` (`models/source_pair.py`), two cells, nominal clock, with the reference's numerical conventions confined to it (D146, D149). **Calcium-energy family:** `network_reactions@1` regulation of pumps, channels and junctions in `resolved_calcium_energy_regulated@1/@2`, qualified on µs-scale transients only ([archived progress](history/PROGRESS_BEFORE_2026-11-08.md)). **Nothing on the pump family** | The gene-regulation layer: heredity Stage D, an expression carrier of Ca/CaV plus a slow regulator, 12–20 days ([HEREDITY_FIRST_EXPERIMENT.md](HEREDITY_FIRST_EXPERIMENT.md)); parity rung P8; the wet-lab benchmarks, yeast cell cycle first ([GRN_WETLAB_VALIDATION.md](GRN_WETLAB_VALIDATION.md), [PAPER_BACKLOG.md](PAPER_BACKLOG.md)). **Held under D145.** The molecular-loop gate's regulated production rate | A general regulatory-network operator on the tissue family: nodes as cell state with one owner, in physical time; declared inputs (voltage, free ions, signal concentration); declared outputs (availability factors, production rates); partition at division and reset or copy at replacement, by declared rules | As in "Missing". It is validated first against wet-lab GRN benchmarks, run out of process (approval per paper, D138), then in Cells (D136) | The user lifts D145's hold; the molecular-loop gate (one regulated functional-unit population) |
| 5 | Persistent memory | **Pump family:** the bistable heredity cell (a NaV1.2 window current with Kir2.1; H about −80 mV, D about −21 mV), whose written D state E07-v1 tests; slow ion loading over hours; junction abundance under the formation law; channel gate states. `stationary_continuation_analysis@1` (`analysis/stationary.py`, mode E, qualified) finds the states and their stability. A donor copy is an inheritance route (D139) | The coupled-renewal gate's "causal carriers" (interventions on ion loading, channel state, junction abundance and regulatory state) and its robustness deliverable ([current plan](CURRENT_PLAN.md#gate-coupled-renewal)); E07-v2's write–clear–challenge rules (D151); Cortés-Poza T6, resetting voltage, composition and junction gates independently (**held**); the bone review's rank 4 (deferred) | A regulatory memory with its own declared timescale, separate from the ionic state. A booked way to change one slow variable in place: replacement@1 swaps a whole content. Coupling memory that depends on activity. Cortés-Poza Phase 0 found the author model's slow memory erasing its pattern rather than storing it, so memory can lower recovery, a reason to test it factorially | Row 4's slow nodes. A declared, booked state-intervention event for causal tests ("an event may replace a value, but books what it removed and supplied"); whether that is a new operator or a template option is the gate's design question | Coupled renewal (after E07-v1's analysis); row 4's hold |
| 6 | Mechanical coupling | **Standalone:** `apical_vertex_mechanics@1` (`models/apical_vertex.py`): a 2-D apical vertex model with Farhadifar energy, forces by `jax.grad`, overdamped, padded topology. With it, `mechanical_equilibrium_analysis@1` and `junction_tension_inference@1`. MG1 v2 passed 57/57 and landed (weaker evidence after v1's failure). Not coupled to any transport model; no T1, growth or division | MG2 (T1, sorting), MG3 (growth, division, death) and MG4 (bioelectric and chemical prepatterns guiding shape, voltage → mechanics, on moving geometry) ([MORPHOGENESIS_PLAN.md](MORPHOGENESIS_PLAN.md); D134). That plan's engine gaps 3, 6 and 7: topology events, transport on changing geometry, coupling to the bioelectric and regulatory layers | The mechanics → bioelectric direction: a declared per-patch mechanical observable and a mechanically gated conductance. Both are absent in `src`, and the direction is an **open question to the user** (bone review, question 2), not a plan. Transport on time-varying areas and lengths. Mechanics as a composite operator | Mechanics as a composite operator on shared geometry; a per-patch mechanical observable; a mechanically gated conductance law, from the mechanosensitive-channel biophysics literature, sourced before design | The integrated tissue unit (mechanics, transport and lifecycle on changing geometry); S2's membrane state as the area owner |
| 7 | Damage: removal, ablation, lesion | **Pump family:** `scheduled_cell_replacement@1`, an in-place swap by an isolated template or a donor copy, with no vacancy, release or uncoupling; qualified under G2-Q1 in held-bath heredity worlds, ARS(2,2,2) at 1 ms. Junction availability schedules: MG0b's cut is a junction closure, and @3 has no excision (`validation/morphogenesis/mg0b_domain_wall.py`). Scheduled availability pulses; `electrode_current_injection@1`. **Older families:** `conservative_tissue_removal_remap@1` (`processes/tissue_removal.py`) behind `resolved_tissue_excision@1`, `resolved_tissue_active_excision@1`, `resolved_calcium_excision@1` and the `resolved_calcium_energy_*_excision@1` models. These cut from checkpoint to checkpoint, rebuild the field and continue at absolute time. Removed material leaves the system, and junctions are abstract edges, so there is no wound surface. `resolved_repair@1`–`@4` with `prescribed_patch_injury_resealing@1` (`processes/membrane_injury.py`): fixed-geometry Na/K injury and prescribed resealing, on the calcium catalog families | S5 partition and bridge closure ([CELL_DIVISION_S5_DESIGN.md](CELL_DIVISION_S5_DESIGN.md)): `isopotential_partition@1` and `cytoplasmic_bridge_closure@1` are **design only**, and S5a lands after the volume ledger. `scheduled_cell_replacement@2`, water plus replacement ([composite v2](PUMP_COMPOSITE_V2_DESIGN.md) §2): **design only**, open until the renewal assay asks. The endogenous lifecycle (milestone 2, later). [ROADMAP "Injury and repair"](ROADMAP.md#injury-and-repair): fixed geometry first, then cutting, then regrowth | Removal on the pump family and the composite: a vacancy, the removed cell's contents and contacts, and a field rebuilt during the run or by archive. MG0a's driver also recorded "no excision contract". Injury and resealing on the pump family. Regrowth, which is growth plus division | An excision operator or contract for the composite that reuses `conservative_tissue_removal_remap@1`'s accounting rules; injury as a composite operator; growth and endogenous division | Lifecycle operators (S5); the endogenous-lifecycle milestone; the integrated tissue unit for regrowth on changing geometry |
| 8 | Recovery readouts and analysis | `src/cells/assays/recovery.py`: a sampled return to a matched trajectory, with a hold; an observer only. E07-v1's driver and copy-only null (`validation/tissue/e07_v1_turnover.py`). MG0b's Jaccard scoring | E07-v1's run-level classes (§6 there); Cortés-Poza Phase 3's two-sided pattern agreement | Pattern metrics beyond a D/H set (gradient, wavelength, shape), as observers | None in the engine. These are validation drivers and observers (AGENTS.md) | The experiment's own protocol |
| 9 | Timescales | Fine steps of about 1–5 ms (one hour is 3.6 million steps at 1 ms). `stationary_continuation_analysis@1` (mode E) is qualified. `projective_forward_euler@1` (mode C) landed, but qualification qual-01 failed on the absolute caps. Mode B, quasi-steady electrical, comes later (D135) | The compute-limits gate's verdict on long-time methods ([current plan](CURRENT_PLAN.md#gate-compute-limits)). The secreted-species design §8 keeps the door open, but version 1 refuses the stationary analysis on the composite | A qualified method for hours to days. Recovery in animals runs over days (the synthesis's framing, unverified; not a Cells number) | Qualified multirate or quasi-steady methods (D135), never specific to one experiment | Compute limits |
| 10 | Execution scale | CPU, and one L4 with batched worlds (G4: 2.28 ms per world-step at 256 worlds for @3). Dense node-space field solves: a Cholesky every IMEX step, and the dense IDs' 2,048-node bound | GH200, expected by the end of next week (D145). The [field-solver interface](FIELD_SOLVER_INTERFACE_DESIGN.md): proposed, no code, waiting for the GH200 numbers; it compares sparse and matrix-free alternatives | Measured GH200 cost; sparse IDs for large 2-D gradient sheets. One world is partitioned across devices only if measurements justify it | The field-solver interface | Compute limits |

## 4. Order of features, and the gates the path rides on

**Version 0, the first informative version.** It needs no new engine feature.
- **Engine models:** `resolved_pump_composite@1` over `resolved_pump_tissue@3`, with
  `scheduled_cell_replacement@1` (`resolved_pump_replacement@1`); optionally
  `electrode_current_injection@1` for the state lesion.
- **World:** E07-v1's held-bath 127-cell sheet with homogeneous heredity cells, on CPU. 1-D
  chain screens come first.
- **Layers it has:**
  - bioelectric communication: the coupling s, and the formation law for newcomers;
  - intrinsic bistable memory: bistable against monostable parameter sets, within the
    ranges the pre-screens used;
  - a prescribed positional prepattern as supplied information, held either by the slot or
    by the carrier (§2), and declared in every template.
- **Damage:** ablate and refill (a block), a state lesion and a communication lesion, with
  the controls of §1.
- **The question it can answer.** With identical bistable cells and no regulatory network,
  does bioelectric coupling alone restore a lesioned written domain beyond the refill null?
  How much supplied positional bias does fidelity need? Two existing results bound the
  expectation:
  - MG0b: below the critical coupling, a wall pins;
  - E07-v1's set (b): how fast junctions must form for an isolated newcomer to be recruited
    (tau*).
- **What it is not.** It is not the proposed experiment: it has no regulatory network, no
  secreted signal and no mechanics, and it is labelled so.
- **Prerequisites:**
  - E07-v1's analysis. Version 0 reuses its world, driver and null, and E07-v1's registered
    protocol stays untouched (D151);
  - a check of block lesions against G2-Q1's scope;
  - the 70-minute fixed-volume window, or water plus replacement;
  - its overlap with Cortés-Poza Phase 1 (T6) and Phase 3 settled, since those are held
    under D145 (open question 2).

**After version 0, in the order the gates allow.**
1. **D150 v1** (composition; after S5a). It gives a measurable gradient but no response,
   so it adds a readout, not a causal layer.
2. **A responder side and state-dependent secretion**, if the user takes them (bone review,
   question 3). Positional signalling becomes a causal layer, with a source region that can
   itself be lesioned.
3. **Reactions on the shared inventory** (design first). This adds self-organisation, with
   MG0c as its qualification case.
4. **The gene-regulation layer**, when D145's hold lifts (the molecular-loop gate; the GRN
   benchmarks first). "The same GRN" then becomes literal, and regulatory memory with it.
5. **The lifecycle:** S5, the volume ledger and replacement@2, an excision operator on the
   composite, then growth and endogenous division. This gives removal with a vacancy, and
   regrowth.
6. **Mechanics** composed on shared geometry, with both coupling directions (the integrated
   tissue unit).
7. **Long-time methods**, and GH200 or the field-solver interface, for the 825-node tissue
   and recovery over days.

Each step is a general feature with its own design note (D142), qualification and gate. A
version of this path's protocol is registered only after the features it uses have
qualified.

**Gates it rides on:**
- **Coupled renewal:** version 0 shares E07-v1's world, and the causal-carriers and
  robustness deliverables are row 5's features;
- **composition:** D150, the responder, reactions on the shared inventory, water plus
  replacement;
- **lifecycle operators:** S5, removal, then the endogenous lifecycle;
- **the molecular-loop gate:** the regulated junction population, the regulatory network;
- **the integrated tissue unit:** mechanics;
- **compute limits:** long-time methods, GH200, the field-solver interface.

**Related entries, cross-referenced rather than restated:**
- [Experiments](EXPERIMENTS.md): the 24 October comparisons (pattern information, error
  sensing and corrective action); E08 (autonomous renewal); E09 (memory location); E11
  (embedded control);
- the [morphogenesis plan](MORPHOGENESIS_PLAN.md): MG0b and its history arm, MG4, and
  planarian anterior–posterior polarity on fixed geometry (D134), with the outcome
  fractions recorded there from Durant 2017;
- the [Cortés-Poza test plan](CORTES_POZA_2026_TEST_PLAN.md): T6 and Phase 3 (regeneration
  after a lesion against a plain bistable baseline).

## 5. What not to do

- **Do not build a feature for this experiment** (D144). No regeneration operator, no
  planarian polarity law, and no species named Wnt or BMP. The engine gains general
  features (a responder coupling, reactions on the shared inventory, a regulatory-network
  operator, an excision operator, a mechanically gated conductance), each qualified on its
  own references.
- **Do not reproduce a paper's model without approval** (D138, restated in D151). That
  covers published planarian or morphogen models, and the Cortés-Poza author model beyond
  its approved Phase 0. The pasted synthesis is not a paper and supplies no model.
- **Do not start a held track** (D145). The GRN track, Cortés-Poza Phase 1 and catalogue
  stage 3 stay held, and this path does not lift them.
- **Every candidate is deferred, not closed** (D151).
- **Do not touch E07-v1's registered protocol** (D151). Version 0 is a separate protocol,
  registered later.
- **Do not put missing physics in a driver** (AGENTS.md). Do not relabel channel
  bistability as a gene regulatory network.
- **Do not count a slot-held prepattern as tissue-held positional information.** It is a
  supplied answer.
- **Do not score a collapse to a uniform state as recovery.** Do not infer from a recovery
  that the tissue "knows" or represents its target.
- **Do not treat the synthesis's claims as verified**, or use them as parameters or
  tolerances.
- **Do not run anything now.** The path is backlog.

## 6. Open questions for the user

1. **Numbering and home.** Should the path take an E-number in [Experiments](EXPERIMENTS.md)
   (the later-experiments table runs to E14), or fold into E09 or E11? The lead's call or
   the user's.
2. **Overlap with Cortés-Poza.** Should version 0's bioelectric-only arms merge with
   Cortés-Poza T6 and Phase 3, both held under D145, or stay separate?
3. **Timing.** May version 0's protocol be drafted after E07-v1's analysis, given that it
   reuses that world and driver?
4. **The first damage.** Ablate and refill, a state lesion or a communication lesion? True
   removal with a vacancy needs a new general feature, an excision operator for the
   composite. Is that wanted?
5. **Supplied positional information.** Is a prescribed prepattern acceptable as version 0's
   positional layer, labelled as supplied information? Or should the positional layer wait
   for a responder side?
6. **D150 version 2, and reactions.** Already asked in the bone review: should D150 v2 take
   state-dependent secretion and a responder side? New here: should reactions on the shared
   inventory, for Turing-type self-organisation and MG0c, be designed as a general feature?
7. **"The same GRN".** Is version 0 acceptable with the bioelectric cell law set as the shared
   intrinsic network, honestly labelled, with a real regulatory network only when the held
   track opens?
8. **The biological anchor.** Planarian anterior–posterior polarity on fixed geometry,
   already D134's parallel target, or the wing disc?
9. **Mechanics.** Already asked in the bone review: should MG4 gain the mechanics →
   bioelectric direction?
10. **Timescale.** Are windows of minutes to hours acceptable for the first versions, given
    that recovery over days waits for a qualified long-time method?

## 7. Sources for this note

- **Repository documents read:**
  - plans and records: the [current plan](CURRENT_PLAN.md), [Roadmap](ROADMAP.md),
    [Decisions](DECISIONS.md) D133–D151, [Progress](../PROGRESS.md),
    [Experiments](EXPERIMENTS.md);
  - experiment designs: [the heredity design](HEREDITY_FIRST_EXPERIMENT.md),
    [E07-v1](E07_V1_DESIGN.md), the [morphogenesis plan](MORPHOGENESIS_PLAN.md), the
    [Cortés-Poza test plan](CORTES_POZA_2026_TEST_PLAN.md);
  - model and feature designs: the [secreted-species design](SECRETED_SPECIES_TRANSPORT_DESIGN.md),
    [cell replacement](CELL_REPLACEMENT.md), the [S5 design](CELL_DIVISION_S5_DESIGN.md)
    and [composite v2](PUMP_COMPOSITE_V2_DESIGN.md) (read only), the
    [field-solver interface](FIELD_SOLVER_INTERFACE_DESIGN.md),
    [tissue electrical models](TISSUE_RETURN_CURRENT.md);
  - reviews and tracks: the [bone mechanosensing review](PAPER_REVIEW_BONE_MECHANOSENSING.md),
    the [GZMK review](PAPER_REVIEW_GZMK_AGEING.md), the
    [GRN wet-lab track](GRN_WETLAB_VALIDATION.md), the [paper backlog](PAPER_BACKLOG.md),
    [EMT_REFERENCE.md](EMT_REFERENCE.md), [SOURCE_EMT_PAIR.md](SOURCE_EMT_PAIR.md).
- **Code:** IDs and files were checked by grep in `src/cells`, at `ae278b4`.
- **Nothing fetched from the web.** No preprint or paper was read for this note.
- **Log:** `/mnt/workspaces/Cells/experiment-path-pattern-recovery-20261113-01/HANDOFF.md`.
