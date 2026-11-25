# Membrane retrieval and its populations into an owned compartment (FR-2, design)

*Status: proposed, 18 November 2026, for the lead and the user (D216). Docs only. Nothing is built,
and nothing is scaffolded before the user has discussed the options. Code was read at main 5133a850
and is cited `file`:line by today's path under `src/cells/`; D188's move 2 has not landed. Tags:
**(code)** read in the code; **S** this note's own reading, derivation or arithmetic (the script and
its output are in §11). Other statements cite their source.*

**Engine models it runs** (AGENTS.md): none. Version 1 would run `resolved_pump_composite@1` over
`resolved_pump_tissue@3`, with `membrane_entity_state@1`, `cell_owned_compartments@1` and one new
operator (§2). §6 names what else composes.

**What is asked.**
- **FR-2, from the requesting study** (D158): "the retrieval direction of
  `scheduled_membrane_insertion@1`: membrane area, capacitance and the populations on it move
  inward at a scheduled rate, carrying the compartment they form (FR-1) with them". Its reason:
  "Receptor-mediated uptake depletes the surface pool and returns it."
- **D158's open question:** retrieval's energy source. One design of energy-pool coupling should
  serve FR-2 and the pool doors that D150 and D152 deferred.
- **The task's form of it.** Is the source a declared external reservoir, as D150's and D152's
  routes book work, or a finite energy pool? One answer should serve D150's question 11, D152's
  question 10 and D151's deferral together.
- **FR-3 asks two things of FR-2** ([its note](SITE_OCCUPANCY_DESIGN.md) §5.3):
  - retrieval moves a site population's pools R and B by the membrane's area fraction, through
    `ACCEPTS_WRITES` of both population owners;
  - its energy source also serves FR-3's internalisation work (§3.3 there).
- **D216 on ownership:** FR-1's later doors (creation, division, fission and fusion, retirement) go
  with seam B and the mitochondria work (D210).

**Basis.**
- [CLOSED_COMPARTMENT_DESIGN.md](CLOSED_COMPARTMENT_DESIGN.md): §1.3–§1.5, §3.1, §3.6, §4, §5.3,
  §7 and §8.
- [CORE_SEAMS_DESIGN.md](CORE_SEAMS_DESIGN.md) §4 (populations and their roles; §4.6, the merge
  verb), with [step 0](CORE_SEAMS_STEP0.md) §4.2's owner table.
- [COMPARTMENT_PH_TRANSFER_DESIGN.md](COMPARTMENT_PH_TRANSFER_DESIGN.md) §5 and §17 (fuel under F2).
- [SECRETED_SPECIES_TRANSPORT_DESIGN.md](SECRETED_SPECIES_TRANSPORT_DESIGN.md) §2.4 and §10, and
  [SHARED_INVENTORY_REACTIONS_DESIGN.md](SHARED_INVENTORY_REACTIONS_DESIGN.md) §3.3, §7.3 and §9.
- ARCHITECTURE.md, "Material identity and fuel".
- [MITOCHONDRIA_DESIGN.md](MITOCHONDRIA_DESIGN.md), addendum B.1 (the physics of fission and
  fusion).
- The insertion and partition operators **(code)**.

## 0. Summary

1. **The capacitor's free energy rises only under insertion's own rule, run backwards** (§2.2).
   Insertion changes capacitance at fixed free-node charges: "the inserted membrane arrives
   uncharged" **(code)**. Retrieval by that rule (R1) would strip the retrieved membrane of its
   charge.
   - Its work is ΔU = q² dC/(2C(C − dC)) for a one-patch cell. Retrieving 1% of a 10 pF cell at
     −70 mV costs 2.47 × 10⁻⁴ pJ and moves Vm to −70.71 mV (**S**). That voltage step is an
     artefact of the rule.
2. **If the retrieved membrane keeps its charge** (R2: "charges follow the patches", the partition's
   rule **(code)**), no potential changes except the compartment's.
   - The compartment's voltage becomes the capacitance-weighted mean, (C_b V_b + dC V_k)/(C_b + dC).
   - The capacitor energy falls by C_b dC (V_b − V_k)²/(2(C_b + dC)) ≥ 0, which is booked as heat.
     It is zero for a new compartment (**S**).
   - Retrieval is then a split of the plasma patch and its outside node, followed by a merge into
     the compartment: seam B's verbs (CORE_SEAMS §4.2, §4.6).
3. **So retrieval's own physics needs no energy source** (§3), beyond conventions the engine already
   books:
   - heat for the merges;
   - a small signed work for the charge's carrier ions, booked as exchange books its moves;
   - a held bath's supply, booked as @3 books it.
   The real cost of endocytosis (coat, curvature, scission, sorting) is the machinery's. It lies
   outside @3's state, the limit D150 §2.4 already declares for endocytosis.
4. **The one answer for every consumer (S): a fuel coupling on driven routes, in the transporter
   kind's existing vocabulary** (§3.4).
   - **Held fuel rows** (`maintained_held_rows@1`) are the declared external reservoir: a named
     fuel, its supply recorded, its work from the registry's potentials.
   - **Finite fuel rows** (`finite_fuel_rows@1`) are the pool.
   - D152's reactions already have it, by writing ATP, ADP and Pi into their stoichiometry (R-fuel's
     regeneration). D150's operators, FR-3's internalisation and FR-2's machinery would declare a
     fuel block.
   - Seam E designs it once, after the finite-fuel acceptance. FR-2's version 1 does not wait for
     it.
5. **Version 1, recommended (S, §9):** R2, with no enclosed fluid and the compartment's volume fixed
   (F0); into a lumped pool declared with the world, so no creation event (D1); retrieval and
   recycling as one law's two directions (T2). Internalised channel units are held silent in the
   operator's record (P0), because refusal 4 refuses @3's channels and pumps on a bounding patch
   **(code)**. A patch's pump stays on the plasma patch with its aggregate capacity, as insertion@1
   holds it.
6. **Three population owners move** (§4): membrane state's units now; FR-3's sites once its count
   is state and its admission line exists; the kinds' populations by seam B's roles. Each moves by
   seam B's split and merge.
7. **Limits stated:** the 64-node cap and the held-bath topology apply (§5). Discrete vesicles,
   stochastic loading and fluid-phase uptake are out of version 1.
8. **Effort (S, rough):** about 6–8.5 agent-days for version 1, after seam B's operator part (§9).

## 1. What exists, and what refuses

### 1.1 Insertion's law, and its refusal

- **The law** (`operators/membrane_insertion.py`:1–24 **(code)**). Per half-step h, on each
  inserted patch with rate r ≥ 0: dA = r h, dC = c_d r h and dN_j = ρ_j r h.
  - These are written to membrane state's increments, "at fixed free-node charges with the
    potentials re-solved (`adapter.fixed_charge_change`): the inserted membrane arrives uncharged".
  - The capacitor free energy falls by H ≥ 0, booked as insertion heat. Each held bath's plate-charge
    change is booked as electrode transfer, with its work.
- **The refusal:** "a negative rate (retrieval: its heat would be negative, and the work would need
  a declared source)" (:36–37). The parser says "Membrane retrieval (a negative insertion rate) is
  refused" (:198).
- **The kernel** (`pump_composite_adapter.fixed_charge_change`, :727–761 **(code)**) assumes
  dc ≥ 0. Its one-patch case is "V' = V C/C' and H = q² dc/(2 C C')".

### 1.2 The partition's charge rule

- "Charges follow the patches: with q_k = C_k V_k at the composite's view, the mismatch dq = Σ_k
  (a_k − f) q_k is carried by the declared carriers, δ_s = t_s dq/(z_s F)"
  (`partition.py`:22–23 **(code)**).
- The free-energy change less the clamps' work is booked as partition work: "with proportional
  anchors that is the unmixing term, ≥ 0" (:37–40).
- The partition is qualified (S5a, against R-ops and R-tissue; CURRENT_PLAN's lifecycle gate).

### 1.3 FR-1's compartment and its doors

- **A compartment is a finite, face-free outside node, bounded by one patch of its owner**
  (FR-1 §1.1). Its patch voltage is V_b = −q_j/C_b exactly, and the owner's plasma membrane sees
  q_cell + q_comp (FR-1 §3.1).
- **A node can be a lumped pool** of N identical organelles. That is the regime of validity for µM
  cargo, and per-vesicle counts are out of scope (FR-1 §1.3).
- **The declaration refuses today what FR-2 needs** **(code)**:
  - providers of areas and capacitances (`compartments.py`:100–111);
  - membrane state and insertion, through the admitted list (:89–97). That is "the membrane-state
    wall" (FR-1 §4);
  - on the bounding patch, @3's pumps and channel populations: refusal 4 (:186–200).
- **The doors** (FR-1 §1.5, §8) and their owners under D216:

  | Door | What it needs | Owner (D216) | Needed by FR-2's version 1? |
  | --- | --- | --- | --- |
  | C, creation | A pending compartment slot opened at an event | Seam B and the mitochondria work | No: version 1 retrieves into a declared pool (§2.4) |
  | V, volume as state | Volume through the view, the dilution term, the mixing heat; D150's and D152's version 1.1 | FR-1's door, with composition's current reads (D191) | No: version 1 encloses no fluid (§2.3) |
  | F, fusion and fission | A transfer between a compartment and another node | Seam B and the mitochondria work | Its physics is version 1's kernel (§2.2); see §7 |
  | D, division of an owner | Pending slots and the entity hierarchy | Seam B | No: owners still do not divide |
  | The membrane-state wall | Membrane state admitted beside a compartment | The operators owner (`compartments.py`) | **Yes** (§6) |

### 1.4 Seam B's verbs

- **Close, split, retire and open** are implemented once, by declared field roles: extensive,
  intensive, history, structural (CORE_SEAMS §4.2).
- **Merge,** split's inverse, is a collected requirement, not yet a design (§4.6). Its rules:
  - extensive fields summed;
  - history moved to a record;
  - structural fields equal, or refused;
  - intensive fields weighted by a declared extensive field;
  - "members merged at unequal voltages lose capacitor energy C₁C₂(V₁ − V₂)²/2(C₁ + C₂), and at
    unequal contents mixing free energy", both booked as heat.

### 1.5 Fuel, as decided

- **F2 (D176):** "ATP, ADP and Pi are shared inventory species, used by reactions and pumps", with
  one authority for amounts and standard potentials.
  - The FR-2 entry's reading that "the pools live in the older families" predates D176. The older
    family's `finite_atp_adp_pi_transformed@1` (`legacy/`, FINITE_ENERGY_POOLS.md) is a reference
    under D196, not a host.
- **The transporter kind already declares fuel in two kinds** (`kinds/transporter.py`:27–37
  **(code)**):
  - `maintained_held_rows@1`: rows read, never moved; the maintenance supplies −Δ_rG'_ATP per
    cycle as work; the supplied material is recorded;
  - `finite_fuel_rows@1`: the rows move, and their standard term is stored. Its design is accepted
    (FR-4/FR-5 note §17) and is built with its own protocol (`finite-fuel-v1`).
- **ARCHITECTURE.md:** "Booked work is not fuel. D152's booked external work is not a finite
  fuel-consumption law. Finite fuel needs a declared donor, stoichiometry and affinity."

## 2. The law: what retrieval moves

The setting (**S**):
- an owner cell i;
- a plasma patch k from i to an outside node o (finite, or a held bath), with capacitance C_k and
  voltage V_k = φ_i − φ_o;
- a compartment node j of i, bounded by patch b, with capacitance C_b and V_b = φ_i − φ_j.

Retrieval moves area dA from k to b.

### 2.1 Area and capacitance

- **dA from k to b; dC = (C_k/A_k) dA,** so the plasma patch keeps its specific capacitance (**S**;
  membrane state admits C ≠ c_d A per patch, `membrane_state.py`:3–5 **(code)**).
- **Conserved per cell:** A_k + A_b and C_k + C_b, through membrane state's entity ledgers. The
  operator books both changes, as insertion books its own.

### 2.2 The plate charge: two rules

**R1, insertion's rule run backwards: fixed free-node charges.** The retrieved membrane leaves
uncharged.
- For a one-patch cell, q = C V stays and V' = q/(C − dC).
- The capacitor energy rises by ΔU = q² dC/(2C(C − dC)), about ½ V² dC.
- **Arithmetic (S):** with C = 10 pF, V = −70 mV and dC = 0.1 pF (1% of the membrane), ΔU = 2.47 ×
  10⁻⁴ pJ, and V' = −70.71 mV.
- The work needs a declared source. The voltage step is an artefact: a membrane piece pinched off
  at its own voltage leaves the rest at that voltage (R2's result below).

**R2, charges follow the patches: the partition's rule.**
- The retrieved area takes its share of the plate charge on the outside node's side, −dC V_k. It
  moves from o to j, carried by declared carrier species with transference numbers t_s,
  δ_s = t_s δq/(z_s F) (`partition.py`:22–23's form).
- **What it does, derived from @3's capacitor rows (S).** Every node's row stays satisfied by the
  old potentials, except j's.
  - Cell i's row: (C_k − dC) V_k + (C_b + dC) V_b' = (C_k − dC) V_k + C_b V_b + dC V_k =
    C_k V_k + C_b V_b, its old value.
  - Node o's row: its left side and its charge both change by dC V_k, so it still holds. The same
    holds when other cells' patches face o.
  - So only φ_j moves, to
        V_b' = (C_b V_b + dC V_k)/(C_b + dC),
    and
        ΔU = −C_b dC (V_b − V_k)²/(2(C_b + dC)) ≤ 0.
  - This is CORE_SEAMS §4.6's merge loss, booked as heat. Into a new or empty pool (C_b → 0), or a
    pool at V_k, it is 0.
- **Arithmetic (S):**
  - a pool of 1 pF at 0 mV receiving 0.1 pF at −70 mV ends at −6.36 mV, with heat 2.23 × 10⁻⁴ pJ;
  - the charge carried is 7.0 × 10⁻¹⁵ C, which is 7.25 × 10⁻⁵ fmol of a monovalent carrier.
- **Exact over a half-step at a constant rate (S).** Within the operator's half-step V_k is
  constant, since R2 does not move it. C_b V_b grows linearly, so V_b(t) has the closed form above
  with dC = c r t. The heat equals the one-step merge's, since H = −ΔU is a state difference.
- **Recycling, the reverse (S):**
  - a packet leaves the pool at the pool's own voltage, so the pool keeps V_b;
  - its lumen charge share moves from j to o;
  - its capacitance merges into k. For an owner with no other patch and a held bath outside,
    V_k' = (C_k V_k + dC V_b)/(C_k + dC), and the merge heat is C_k dC (V_k − V_b)²/(2(C_k + dC)).
    In general the potentials are re-solved at the new charges, as `fixed_charge_change` re-solves
    them;
  - insertion@1 is this rule's special case of a packet from an undeclared source at V = 0. Its
    heat, q² dc/(2CC'), is the merge loss with V₂ = 0.
- **A held bath as o** (**S**). The clamp absorbs the plate-charge change of k's lost area as
  electrode transfer, with its work, as `fixed_charge_change` books today. The bath supplies the
  carriers as a reservoir supply, with @3's reservoir work. The two charges cancel.

### 2.3 The enclosed fluid: two choices

- **F0: no fluid.** The compartment's volume stays fixed, as in FR-1's version 1. Only the plate
  charge's carriers move from o to j.
  - Their move changes the two nodes' chemical free energy by Σ_s δ_s RT ln(c_s,j/c_s,o), to first
    order. That is signed, so it is booked as signed work, as exchange books its moves (D174: a
    driven route).
  - **Its size (S):** δ RT ln 2 = 1.3 × 10⁻⁴ pJ for the example's carrier at a twofold
    concentration ratio. That is comparable to the capacitor terms, though tiny in material
    (7.3 × 10⁻⁶ of a 0.1 pL pool at 100 mM).
  - The term is an artefact of moving ions without their water, so F0 is a declared reduction.
- **F1: fluid-phase uptake.** A packet of o's fluid, of volume v dA, encloses with the membrane.
  - The sphere's v = r/3 is about 8–17 nm for radii of 25–50 nm (**S**, geometry; no source read).
    10 µm² retrieved at r = 50 nm encloses 1.7 × 10⁻⁴ pL.
  - It is the partition's split of o by the volume fraction, with the mismatch carriers. Its
    unmixing term is second order and ≥ 0, booked as the partition books it (§1.2). Then comes the
    merge into j, whose mixing heat is ≥ 0 (FR-1 §5.3's Jensen gap).
  - From a held bath, the packet is a reservoir supply.
  - It needs door V: volume as state at j and o, with D150's and D152's current-volume reads
    (D191). That is version 1.1.

### 2.4 The destination: two choices

- **D1: a lumped pool declared with the world.** A compartment that exists from time 0, with a
  small declared seed area and volume. Membrane state's domain needs A > 0 and C > 0
  (`membrane_state.py`:24–27 **(code)**), and @3 needs every species positive at every active node
  (D150 §1.3).
  - Retrieval grows its bounding patch, and recycling shrinks it.
  - No creation event, no slot and no mask: so the operator provides no activity mask (§6).
  - "The compartment they form" is that pool, in FR-1 §1.3's regime of validity.
- **D2: a compartment created at an event.** Door C, seam B's with the mitochondria work (D216).
  - Discrete vesicles also need slots (2^(k+1) − 1 for k rounds, S5 §6.2), the 64-node cap's
    room, and a stochastic treatment that FR-1 §1.3 leaves out of scope.
  - FR-2 consumes door C when seam B builds it. This note does not design it.

### 2.5 The direction: two choices

- **T1: retrieval only.** The return would come from insertion@1, whose units come from an
  undeclared source, so the pool's material account would not close.
- **T2: retrieval and recycling, two schedules of one law per route** (plasma patch, compartment).
  - The surface pool is depleted and returned from the same compartment, which is the requester's
    need and FR-3 §5.3's "FR-2's exocytic direction".
  - Each direction is a split at the source followed by a merge at the destination (§2.2).

### 2.6 The half-step

For a constant rate r over a half-step h (**S**):
- dA = r h, refused if the source's area would fall below a declared floor;
- dC as §2.1;
- the plate charge and the merge in closed form (§2.2);
- the units as §4.1;
- untouched entries selected, never offset by zero; a zero rate selects the start state, so the
  operator is bitwise idle.

Retrieval provides no mask, so it is a split part with exact half-steps around @3's step, as
insertion is. The composite step stays Strang-symmetric.

## 3. Energy: what each law leaves to be sourced, and the source

### 3.1 The bookings, per law (S)

| Law | Capacitor | Material | What needs a source |
| --- | --- | --- | --- |
| R1 (with F0) | ΔU = q² dC/(2C(C − dC)) > 0: work | — | **The capacitor's rise:** first order in dC, for example 2.47 × 10⁻⁴ pJ per 1% of a 10 pF cell at −70 mV |
| R2 with F0 | −ΔU ≥ 0: merge heat | The carriers' move: signed work, Σ δ RT ln(c_j/c_o) | A signed work term set by the carriers' amount (7.3 × 10⁻⁵ fmol per 0.1 pF at 70 mV), booked under today's convention |
| R2 with F1 | −ΔU ≥ 0: merge heat | Mixing heat ≥ 0; the split's unmixing term, second order and ≥ 0, as partition work | Only the unmixing term, as the partition books it |
| Any, from a held bath | The clamp's electrode transfer and its work | The bath's reservoir supply and its work | Nothing new: @3's reservoir and electrode ledgers |

**What this means (S).** Under R2, retrieval's electrical and chemical changes are heat, plus small
signed terms of kinds the engine already books. The capacitor's rise that insertion's refusal
anticipates belongs to R1 alone.

### 3.2 The machinery's own cost

- Coat assembly, bending, scission and sorting cost free energy. Clathrin, dynamin and the uncoating
  machinery are cited here from memory as textbook biology, not read for this note.
- @3 has no state for curvature or coats, so that cost has no ledger to close against. This is
  D150 §2.4's declared limit: "Their real metabolic cost and dissipation (synthesis, trafficking,
  endocytosis, proteolysis) lie outside the modelled inventory".
- It matters for the gate's "energy demand" as a measured response (CURRENT_PLAN, the aim), and for
  saturation when fuel runs short. Counting it is a fuel draw, not a correction of the ledger.

### 3.3 The options for the source

| Option | What it books | For | Against |
| --- | --- | --- | --- |
| **E1. A declared external reservoir, D150's and D152's convention** | Signed work against an undeclared reservoir | Exists; R1 could run on it | ARCHITECTURE: "booked work is not fuel". Under R1 it pays for an artefact |
| **E2. No source for the physics (R2), the machinery's cost a declared limit** | Heat and today's signed terms (§3.1) | Physical; needs nothing new; version 1 does not wait | Energy demand is not counted |
| **E3. E2, plus a declared fuel draw for the machinery** | ν fuel cycles per unit area moved, against held or finite F2 rows (§3.4) | Energy demand becomes a response, and fuel limits trafficking | Needs the fuel coupling (seam E) and ν from a source |
| *E4. The older families' finite pools* | — | — | Rejected: F2 is decided (D176), and the older code is a reference (D196) |

### 3.4 One answer for D150's question 11, D152's question 10, D151 and FR-3: a fuel coupling (S)

**The coupling.** A driven route (an operator's production, exchange route, internalisation or
retrieval) may declare a `fuel` block in the transporter kind's vocabulary:
`{"kind": "maintained_held_rows@1" | "finite_fuel_rows@1", "node": ..., "rows": [ATP, ADP, Pi],
"cycles_per_unit": ν}`.
- **Held rows: the declared external reservoir.**
  - The route reads them, never writes them, since binding refuses another writer of held rows
    (`transporter.py`:66 **(code)**).
  - It books the fuel's work, W_f = −ν Δ_rG' per unit of progress, with Δ_rG' from the registry's
    potentials only (seam E's one authority).
  - It records the supplied material, as `transporter_fuel_supplied_fmol` does.
- **Finite rows: the pool.**
  - The route moves ATP → ADP + Pi at its node in its own half-steps and books the standard term as
    stored energy (FR-4/FR-5 note §17.2's frame).
  - It joins @3's material ledger through a `produced` record. Seam E's moiety ledger checks the
    stoichiometry (CORE_SEAMS §7.3).
- **The booking.** With held rows, H = W_f − ΔG_route. With finite rows the fuel's own free-energy
  change replaces the supplied work, H = −(ΔG_route + ΔG_fuel), as the transporter books its cycles
  ("there is no work, since the free energy comes from the stored rows", FR-4/FR-5 note §17.2).
  Either way H ≥ 0 is checked at every step.
  - A step whose fuel cannot pay for its route's ΔG is refused, never repaired.
  - A route whose own affinity can exceed the fuel's is a cycle, and it belongs to seam A's cycle
    kind, with its thermodynamics in the kind (CORE_SEAMS §3).

**Why it is one answer.**
- *D152's question 10:* a reaction coupled to ATP is a reaction with ATP in its stoichiometry,
  passive and detailed-balanced. R-fuel's regeneration D + ADP + Pi ⇌ P + ATP is that form
  (FR-4/FR-5 note §17.1). No new mechanism is needed, only the admitted fuel rows.
- *D150's question 11 and FR-3's internalisation:* operators that are not reactions declare the
  block.
- *FR-2 and the coupling note's §6.4 Q6* (a regulatory state's maintenance cost): the same block.
- *D151:* CURRENT_PLAN's composition gate lists "drawing on finite energy pools" as deferred under
  D151. It stays deferred until the user lifts it with this one design.
- **ARCHITECTURE's three conditions:** the donor is the node, the stoichiometry is ν, and the
  affinity is the H ≥ 0 rule.

**Rows written by an operator (S).**
- **D152's ownership contract:** @3 owns every species row, and operators write through
  `ENTITY_WRITES`, booked in their own accumulators. A finite fuel row written by an operator's
  half-step and moved by a kind inside @3's step is R-fuel's composition, admitted today: D152
  regenerates ATP and the pump consumes it (FR-4/FR-5 note §17.3 item 1).
- **Held rows have one writer: none.** So a held-fuel draw is a supply record and its work, never a
  write.
- **D176's "moved by the step" admission.** Fuel rows that kinds move inside @3's step cannot be the
  source of an instantaneous factor held through @3's stages. A retrieval rate limited by ATP is
  therefore a rate route evaluated in the retrieval's own half-steps (FR-7's note §6.1, step B1′),
  not a held factor.
- **§5.2 of the FR-4/FR-5 note still binds:** finite fuel at a node with a dynamic proton row is
  refused.

**Where it lives, and when.**
- Seam E, finite fuel's core part. That is a contract hook in `contract.py` (the operators owner's)
  and the potentials in `species_registry.py` (the binding owner's) (STEP0 §4.2).
- It comes after `finite-fuel-v1` is judged, so that the kind path it reuses is qualified.
- FR-2's version 1 needs none of it (E2). Version 1.1 adds the draw (E3) if the user wants energy
  demand counted.

## 4. Populations: three owners, one set of verbs

Seam B's verbs (§1.4) govern every move. The packet's fields leave the source by split and join
the destination by merge.

### 4.1 @3's channel populations: membrane state's units

- **The units move with their area.**
  - A declared enrichment e_j ≥ 0 per population gives dN_j/dA = −e_j N_j/A_k.
  - That is exact for a constant rate: N_j' = N_j (A_k'/A_k)^(e_j) (**S**). Positivity holds by
    construction.
  - e = 1 keeps the plasma density, e > 1 is down-regulation, and e = 0 excludes a population.
- **Their destination: two choices.**
  - **P0, a silent record (recommended for version 1).** The operator holds the internalised units
    per (compartment, population) as its own extensive state, and books the plasma population's
    decrement in membrane state's increment through `ENTITY_WRITES`, as insertion books its
    increment. Recycling returns them.
    - Plasma units plus the record is the population's conserved total. No unit conducts across
      the bounding patch, so refusal 4 does not bind.
    - Returned units join the plasma population at its own gate state. That is a declared rule of
      the operator, as insertion@2's "gates at opening" rule is (`membrane_insertion_v2.py`:24–33
      **(code)**), not a claim about the channels vesicles deliver.
  - **P1, populations on the bounding patch.** The units become populations of the same law on b
    and conduct between cytosol and lumen.
    - Refusal 4 refuses @3's channels and pumps on a bounding patch at any availability
      (`compartments.py`:186–200 **(code)**).
    - P1 needs refusal 4 per move (B1, CORE_SEAMS §4.4), @3's channel laws' declared step terms,
      and the charged door's stiffness: FR-1 §3.4 reads G_b/C_b as about 4.8 × 10³ s⁻¹ for its
      cited chloride permeability.
    - It is later work, with FR-4's and FR-5's lumen physics as its consumer.
- **Population gates (intensive) and histories** follow seam B's roles: copied at a split, weighted
  by units at a merge, and history from zero in the packet (CORE_SEAMS §4.2).

### 4.2 FR-3's site populations

- **FR-3 §5.3 asks** that retrieval move "a fraction of the patch's area, with that fraction of each
  population's R and B, onto the compartment's bounding patch", so that bound cargo stays bound on
  the moved membrane and is released into the lumen.
- **Two prerequisites:**
  - FR-3's copies N are declared, not state (FR-3 §1.1), so the moiety R + B = S fixes the site
    count per owner. Moving sites needs N as an extensive state under seam B's roles;
  - FR-1's admission line for `site_occupancy@1` past the membrane-state wall (FR-1 §4).
- **Sites carry no charge,** so on the bounding patch they meet no charged door. They join in
  version 1.1, after both prerequisites.

### 4.3 The kinds' populations and @3's pumps

- **A kind's per-entity fields move only if every one declares a role,** the fail-closed rule of
  CORE_SEAMS §4.2. Before seam B's B1 and B2, a kind's population on a retrieved patch is refused.
- **@3's pumps stay on the plasma patch in version 1** (**S**; a point for the lead, §10).
  - Every cell of the seven-cell heredity sheet carries a pump on its patch to the held bath
    (`validation/tissue/regulated_availability_fixtures.py`:3–5 **(code)**). Refusing retrieval from
    a pumped patch would refuse T8's own world.
  - Insertion@1 refuses pumps only on onset patches (`membrane_insertion.py`, `check_onsets`
    **(code)**). Elsewhere it changes a pumped patch's area with the pump's aggregate capacity held,
    since `pump_capacity` is a per-patch view field that membrane state does not touch.
  - So version 1 mirrors that convention: the pump is not in the packet, and its aggregate capacity
    stays. Its density rises as the area falls, a declared rule. @3's step bound has no term for its
    own pump (§5), so holding the pump changes none of the bound's terms.
  - **Internalising pumps** with their membrane waits for capacity as extensive state (CORE_SEAMS
    §4.5 item 3; composition M6).

## 5. Numerics and the topology

- **The step bound (R5).** @3's explicit-rate bound reads the declared layout
  (`surface_pump.explicit_rate_bound`).
  - Retrieval lowers the plasma patch's capacitance, while its units fall by (A'/A)^e. With e < 1,
    G/C rises.
  - So the bound is checked on the definition at the smallest plasma area over the schedule, with
    units at their largest: insertion's pattern, "the largest conductance over the smallest
    capacitance at every point of the schedule" (`membrane_insertion.py`:48–52 **(code)**).
  - The bound counts leaks, channels, junctions, faces and the kinds' stage terms, not @3's own pump
    (`surface_pump_v3.membrane_rate`, :1484–1491 **(code)**). A held pump is outside it, as it is
    for insertion today.
  - Under P0 the bounding patch has no conductance of @3's, and adds no term **only if no kind sits
    on it** (§6).
- **The 64-node cap.** Membrane state provides capacitances, so every FR-2 world is a field-input
  world and is refused above 64 field nodes (`pump_composite_adapter.FIELD_INPUT_NODE_CAP`, :126
  **(code)**).
  - With one pool per cell, about half as many cells fit (FR-1 §3.6). The 7-cell sheet does; the
    127-cell sheet does not.
  - Condensing face-free nodes (FR-1 §3.6) or FR-17 lifts it later.
- **The held-bath topology.** Field-input providers refuse floating components, and so does the
  compartments declaration (refusal 6, `compartments.py`:320–326 **(code)**).
  **Amended 25 November 2026:** the compartments declaration's version 1.1 refuses only a compartment
  that is its component's representative (CLOSED_COMPARTMENT_DESIGN §3.5.1); the field-input
  providers refuse floating components as before.
- **Restart and windows.** The operator's records are state, and schedule changes lie on the dt grid,
  so restart is exact (R7). D195 holds: no checkpoint crosses move 2.

## 6. Composition

| With | Version 1 | Why, and the door |
| --- | --- | --- |
| `membrane_entity_state@1` | Required | It owns area, capacitance and units |
| `cell_owned_compartments@1` | Composes after one change in `compartments.py` | Admit membrane state and this operator in the list, and declare the reads of areas and capacitances `reference` (D191's third mode), since they are identity checks at the definition (**S**) |
| `species_regulated_availability@1` | Composes | Retrieval provides no mask and no volume (§2.4), so the coupling's `CONFLICTS_VIEW` does not refuse it. FR-7's U2 removal |
| D150's turnover | Composes at cells and the compartment | It reads no area |
| D150's exchange | Refused in the same world | Exchange refuses any provider of `membrane_area` (`species_exchange.py`:463–464 **(code)**), and membrane state provides the whole field. The doors: door S's slot scoping, or exchange's current-area read (D191). The requester's uptake world needs one of them |
| D152's reactions | Composes | Its `CONFLICTS_VIEW` names no area or capacitance (`species_reactions.py`:1257–1263 **(code)**) |
| Insertion@1 and @2 | Compose on other patches; refused on a retrieved patch | Two writers of one patch's area need one declared order and a joint R5 bound. Insertion's masks also meet the coupling's `CONFLICTS_VIEW` |
| The partition, the bridge, replacement@1 of an owner | Refused | FR-1's identity rules (§1.5 there); doors D and R |
| `site_occupancy@1` | Refused until §4.2's prerequisites | Version 1.1 |
| Water, the lumens | Refused | Door V |
| RK4 | Guarded | Exact half-steps around @3's RK4 step, as insertion's are |
| Kinds on the pool's bounding patch (FR-4's and FR-5's transporter, passive routes and buffer) | Refused in version 1 | Retrieval and recycling change C_b, and recycling shrinks it, so the kinds' definition-time terms (`bound_rate`) would need the smallest C_b over the schedule. A lumped transporter's capacity, "N x the per-member value" (`transporter.py`:24), needs a rule as the pool grows. The door: both, under seam B's roles |

**Two consequences of R2 for the compartment (S):**
- **The lumen becomes charged, with no route to relax it.** R2 gives the pool the charge of its
  membrane, so V_b ≠ 0, while P0 leaves the bounding patch with no conductance.
  - FR-1's silence claims S1–S3 then no longer apply. They hold only in the silent version
    (FR-1 §3.3), which a retrieval world is not.
  - Within one run the charge sits in the increments, over a zero anchor, so refusal 5 is met.
  - But a checkpoint imported as a new definition (D153's rule (b)) carries a nonzero anchor.
    Refusal 5 version 1.1 refuses that unless the world declares kinds and steps with an IMEX
    tableau (`compartments.py`:26–29 **(code)**). The door is a refusal 5 version 1.2 that admits
    an anchor where this operator is declared.
- **The operator is a first of its kind as a writer.**
  - It is the first to move ion rows between outside nodes: the carriers from o to j. D150's and
    D152's operators write neutral rows only, and the partition moves cell increments.
  - It is the first to draw from a held bath into a finite node: exchange refuses any route on a
    held bath (FR-1's delivery world).
  - So its bookings against @3's outside, reservoir and electrode ledgers are new. T6 judges them
    (§8), with planted errors in each.

## 7. Ownership: who owns each piece

Against CORE_SEAMS_STEP0 §4.2's owner table, so that no file has two owners:

| Piece | File | Owner |
| --- | --- | --- |
| The new operator: parse, schedules, half-steps, records, refusals, summary | A new module under `models/operators/` | The FR lane |
| Its registration | `operators/__init__.py`, or F's section built so that no edit is needed | F owner |
| The charge-following split and the merge with its heat | `models/pump_composite_adapter.py`, beside `fixed_charge_change` | Operators owner, as seam B's split and merge kernels (B1's operator part; §4.6's merge) |
| The compartments admission and its `reference` reads | `operators/compartments.py` | Operators owner |
| Field roles for kinds; @3's own fields | `kinds/*`; `models/surface_pump_v3.py` | Kinds owner; @3 owner (B1, B2) |
| FR-3's count as state | `operators/site_occupancy.py` | FR-3's owner, the FR lane |
| Door C (creation), door F's slot events | — | Seam B and the mitochondria work (D216) |
| Door V | — | FR-1's door, with composition's current reads (operators owner) |
| The fuel coupling (E3) | `operators/contract.py` hook; `registry/species_registry.py` potentials | Seam E: operators owner and binding owner |
| Code-blind references | `validation/` (new folder) | A references agent |

**One kernel, two users (S).** The split-and-merge kernel is the physics of door F and of
mitochondrial fission and fusion (MITOCHONDRIA_DESIGN, addendum B.1). It is written once, by seam
B's owner. FR-2's operator calls it with continuous amounts, and door F will call it with slot
events. So FR-2's version 1 waits for that kernel, or the lead assigns it to the operators owner
within B1's operator part. This is a question for the lead (§10).

## 8. Qualification

Numerical first (D138), against references written by an agent that reads neither the engine nor
this note's derivations.

| Item | Check | Reference |
| --- | --- | --- |
| T1. Identity and refusals | Each refusal of §4–§6 fires with its reason | Definitions |
| T2. Idleness | Undeclared: every program unchanged (crossrev). Zero rates: bitwise idle | Constants-aware crossrev |
| T3. Area, capacitance and units | A_k + A_b, C_k + C_b and plasma units plus record, each conserved to rounding; membrane state's ledgers closing | Closed forms |
| T4. The charge rule | After retrieval, every potential but φ_j unchanged to the field solve's rounding; V_b and the merge heat against §2.2's forms; recycling's V_k with a held bath | An independent dense capacitor solve |
| T5. Down-regulation and return | A retrieval–recycling cycle on one population against the closed form N (A'/A)^e, piecewise in the schedule | Closed forms |
| T6. Energy | The energy ledger closes, and heat ≥ 0 at every step. The carriers' signed work equals an independent ΔG. A held-bath world books its electrode and reservoir work | An independent ΔG function |
| T7. Restart and batches | Restart at, before and after a schedule change and through a snapshot: bitwise. vmap against the reversed batch | — |
| T8. A composed world | A channel population regulated by the coupling and internalised by retrieval (FR-7's U2): the factor and the removal both act | References for the linear chain |

**Planted controls:**
- R1's rule in place of R2 must fail T4, by V dC/(C − dC);
- a merge heat with the wrong sign must fail the dissipation check;
- a unit dropped from the record must fail T3.

**Not claimed:** no biological comparison, no vesicle counts, no fluid-phase uptake (F0), and no
conduction on the bounding patch (P0).

## 9. Recommendation, order and effort

**Version 1 (S):** R2 with F0, into a declared pool (D1), retrieval and recycling (T2), silent
internalised units (P0), and no fuel (E2).
- **R2 is the physics.** Under R1, the work insertion's refusal points to pays for an artefact.
- **F0 and D1 avoid door V and door C,** which are larger and are other owners' (§1.3).
- **P0 avoids refusal 4** and still gives the requester's depleted and returned surface pool.
- **Pumps stay on the plasma patch** with their aggregate capacity, insertion@1's convention, so the
  seven-cell sheet is admitted. Kinds on the pool's bounding patch are refused (§6).

**Then, version 1.1 and later:**
- F1 with door V;
- FR-3's sites, after §4.2's prerequisites;
- the fuel draw (E3), after seam E's coupling and `finite-fuel-v1`;
- kinds' populations and pumps by seam B's roles;
- P1 after refusal 4 per move and the charged door;
- discrete vesicles after door C.

**Effort (S, rough), version 1:**

| Part | Agent-days |
| --- | --- |
| The operator: declaration, two schedules, half-steps, records, refusals, summary, tier-1 tests | 1.5–2 |
| The split-and-merge kernel, with its NumPy test, if FR-2 is its first user | 1–1.5 |
| The compartments admission and `reference` reads | 0.5 |
| Code-blind references | 1–1.5 |
| Guards, the protocol, the judged run (CPU minutes) | 1.5–2 |
| **Total** | **about 6–8.5** |

- **Later items:** F1 with door V about 3–5; FR-3's sites about 1–2; the fuel coupling about 2–4,
  plus its acceptance. Each is labelled **S**.
- **Order:** after D188's move 2 and seam B's operator part (D195, D213). Its files are owned in the
  pass.

## 10. Questions

**For the user:**
1. **The energy source.** Do you accept the one answer?
   - Retrieval's own physics needs no new source when the membrane keeps its charge (R2).
   - The machinery's cost is a declared limit in version 1.
   - A fuel coupling on held (reservoir) or finite (pool) F2 rows, designed once in seam E, then
     serves D150's question 11, D152's question 10, D151's deferral, FR-3's internalisation and
     FR-2 alike.
   - Or should the fuel draw come in version 1, which would make FR-2 wait for finite fuel?
2. **Discrete vesicles.** Is the lumped pool enough for the requesting study's competition and
   cell-to-cell variation, as each cell's own surface pool and compartment? Or are discrete vesicles
   needed (door C, with a stochastic treatment)?
3. **Fluid-phase uptake** (F1) in version 1 or in version 1.1?
4. **Conduction on the bounding patch** (P1): needed with FR-4's and FR-5's lumen physics, or silent
   internalised units (P0) first?

**For the lead:**
5. R2 as version 1's charge rule, with R1 refused as an artefact?
6. The split-and-merge kernel: seam B's operators owner within B1's operator part, with FR-2 waiting
   for it, or FR-2 writing it as its first user under that owner's review?
7. P0's record in the new operator's own state, so that `membrane_state.py` is not edited?
8. The compartments declaration's reads of areas and capacitances as `reference` reads (D191)?
9. The name: `scheduled_membrane_trafficking@1` for the two-way law, or `scheduled_membrane_retrieval@1`?
10. Pumps on a retrieved patch: held on the plasma patch with their aggregate capacity, as insertion@1
    does (recommended, §4.3)? Or refused until capacity is extensive state, which would refuse the
    seven-cell sheet?
11. A refusal 5 version 1.2 that admits a retrieval-charged lumen's anchor at import (§6)?

## 11. The arithmetic

The numbers marked **S** in §0, §2 and §3 come from the first script below, run with `python3 -I`
outside the repository. The second checks R2's claim independently. Neither imports anything from
Cells.

```python
# FR-2 note arithmetic (S): one-patch cell, held bath outside; no Cells import.
import math
F, R, T = 96485.33212, 8.314462618, 310.0
C, V, dC = 10e-12, -0.070, 0.1e-12          # 10 pF cell, -70 mV, retrieve 1% of C
q = C * V
dU_R1 = q**2 * dC / (2 * C * (C - dC))        # R1: the capacitor's rise (J)
V_R1 = q / (C - dC)
print("R1: dU %.4e pJ (1/2 V^2 dC %.3e pJ), V' %.3f mV" % (dU_R1 * 1e12, 0.5 * V**2 * dC * 1e12, V_R1 * 1e3))
for Cb, Vb in ((0.0, 0.0), (1e-12, 0.0), (1e-12, -0.070)):   # R2: merges into a pool
    Vb_new = (Cb * Vb + dC * V) / (Cb + dC)
    H = Cb * dC * (Vb - V) ** 2 / (2 * (Cb + dC)) if Cb > 0 else 0.0
    print("R2: Cb %.1f pF, Vb %.0f mV -> Vb' %.3f mV, heat %.4e pJ" % (Cb * 1e12, Vb * 1e3, Vb_new * 1e3, H * 1e12))
dq = dC * abs(V)                              # the plate charge carried (C)
delta_fmol = dq / F * 1e15                    # monovalent carrier (fmol)
print("charge %.2e C = %.4e fmol monovalent" % (dq, delta_fmol))
print("carriers' work at a twofold ratio, delta RT ln 2: %.3e pJ" % (delta_fmol * 1e-15 * R * T * math.log(2) * 1e12))
print("fraction of a 0.1 pL pool at 100 mM (10 fmol): %.2e" % (delta_fmol / 10.0))
for r in (25e-9, 50e-9):                      # a sphere's volume per area, v = r/3
    print("v = r/3 at r = %.0f nm: %.1f nm" % (r * 1e9, r / 3 * 1e9))
print("10 um^2 at r = 50 nm encloses %.3e pL" % (10e-12 * (50e-9 / 3) * 1e15))
```

Its output:

```text
R1: dU 2.4747e-04 pJ (1/2 V^2 dC 2.450e-04 pJ), V' -70.707 mV
R2: Cb 0.0 pF, Vb 0 mV -> Vb' -70.000 mV, heat 0.0000e+00 pJ
R2: Cb 1.0 pF, Vb 0 mV -> Vb' -6.364 mV, heat 2.2273e-04 pJ
R2: Cb 1.0 pF, Vb -70 mV -> Vb' -70.000 mV, heat 0.0000e+00 pJ
charge 7.00e-15 C = 7.2550e-05 fmol monovalent
carriers' work at a twofold ratio, delta RT ln 2: 1.296e-04 pJ
fraction of a 0.1 pL pool at 100 mM (10 fmol): 7.25e-06
v = r/3 at r = 25 nm: 8.3 nm
v = r/3 at r = 50 nm: 16.7 nm
10 um^2 at r = 50 nm encloses 1.667e-04 pL
```

**An independent check of R2 (S).** A dense capacitor solve of a four-node world, written from @3's
capacitor rows and not from the engine: a held bath, a cell i, a finite outside node o and a
compartment j. The patches are w (i to the bath, 5 pF), k (i to o, 10 pF) and b (i to j, 1 pF), at
V_w = V_k = −70 mV and V_b = −20 mV, and 0.1 pF moves from k to b. It ran with the project's CPU
environment on one lane CPU (`taskset -c 6 nice -n 10`).

```python
# Independent check of FR-2's R2 claim (S): a dense capacitor solve, no Cells import.
# Nodes: 0 bath (held at 0 V), 1 cell i, 2 finite outside node o, 3 compartment j.
# Patches: w (i-bath), k (i-o), b (i-j). Patch voltage = phi(inside cell) - phi(outside node).
import numpy as np

def solve(caps, charges):
    """Free-node potentials (i, o, j) for patch capacitances and free-node charges; bath at 0."""
    Cw, Ck, Cb = caps
    # Capacitor rows: sum over patches C (phi_node - phi_other) = q_node, for i, o, j.
    K = np.array([[Cw + Ck + Cb, -Ck, -Cb],
                  [-Ck,           Ck,  0.0],
                  [-Cb,           0.0, Cb]])
    return np.linalg.solve(K, np.asarray(charges, float))

def energy(caps, phi):
    Cw, Ck, Cb = caps
    pi, po, pj = phi
    Vw, Vk, Vb = pi - 0.0, pi - po, pi - pj
    return 0.5 * (Cw * Vw**2 + Ck * Vk**2 + Cb * Vb**2), (Vw, Vk, Vb)

def bath_plate(caps, phi):
    Cw, _, _ = caps
    return -Cw * (phi[0] - 0.0)          # charge on the bath's side of patch w

caps = (5e-12, 10e-12, 1e-12)            # F
phi0 = np.array([-0.070, 0.0, -0.070 + 0.020])   # choose potentials, derive consistent charges
Cw, Ck, Cb = caps
K = np.array([[Cw + Ck + Cb, -Ck, -Cb], [-Ck, Ck, 0.0], [-Cb, 0.0, Cb]])
q = K @ phi0
U0, (Vw, Vk, Vb) = energy(caps, phi0)
dC = 0.1e-12

# R2: capacitance dC from k to b; the o-side share of k's charge, -dC*Vk, moves from o to j.
caps2 = (Cw, Ck - dC, Cb + dC)
q2 = q + np.array([0.0, +dC * Vk, -dC * Vk])     # o loses -dC*Vk, j gains it
phi2 = solve(caps2, q2)
U2, (Vw2, Vk2, Vb2) = energy(caps2, phi2)
print("R2: dphi_i %.3e V, dphi_o %.3e V, Vb' %.6f V (formula %.6f)" % (
    phi2[0] - phi0[0], phi2[1] - phi0[1], Vb2, (Cb * Vb + dC * Vk) / (Cb + dC)))
print("R2: dU %.6e pJ; formula -Cb dC (Vb-Vk)^2/(2(Cb+dC)) = %.6e pJ; bath plate change %.3e C" % (
    (U2 - U0) * 1e12, -Cb * dC * (Vb - Vk) ** 2 / (2 * (Cb + dC)) * 1e12,
    bath_plate(caps2, phi2) - bath_plate(caps, phi0)))

# R1: the same capacitance move at fixed free-node charges (insertion's rule, both patches).
phi1 = solve(caps2, q)
U1, (Vw1, Vk1, Vb1) = energy(caps2, phi1)
print("R1: dVk %.4e V, dVb %.4e V, dU %.6e pJ, bath plate change %.3e C" % (
    Vk1 - Vk, Vb1 - Vb, (U1 - U0) * 1e12, bath_plate(caps2, phi1) - bath_plate(caps, phi0)))
```

Its output:

```text
R2: dphi_i 2.776e-17 V, dphi_o 3.993e-17 V, Vb' -0.024545 V (formula -0.024545)
R2: dU -1.136364e-04 pJ; formula -Cb dC (Vb-Vk)^2/(2(Cb+dC)) = -1.136364e-04 pJ; bath plate change -1.515e-28 C
R1: dVk -7.0707e-04 V, dVb 1.8182e-03 V, dU 2.292929e-04 pJ, bath plate change -1.010e-28 C
```

- **Under R2,** the cell's and the outside node's potentials move by rounding only, V_b' and the
  energy change equal §2.2's closed forms, and the bath's plate charge does not change.
- **Under R1,** the same move at fixed charges shifts V_k by −0.71 mV and V_b by +1.8 mV, and raises
  the capacitor energy by 2.29 × 10⁻⁴ pJ. That is the work R1 would need.

## Sources

- The code at main 5133a850, as cited.
- The biology of endocytic machinery in §3.2 is cited from memory as textbook knowledge, not read
  for this note, and carries no number.
- FR-1's chloride rate, 4.8 × 10³ s⁻¹, is FR-1 §3.4's, from Ishida et al. (2013) as that note read
  it.
- No web search was made, and no external file was fetched.

## 12. The user's answers and the lead's rulings (18 November 2026; D217)

- **Version 1** is membrane and channel retrieval and recycling.
  - Retrieval follows the membrane's charge (R2), with one shared split-and-merge accounting.
  - Its scope reads "no new explicit machinery fuel draw in v1".
  - It still records carrier-ion chemical work, reservoir and electrode work, and merge heat.
  - The machinery's cost is a declared limit, so the version claims no total trafficking energy and
    no ATP-limited uptake.
  - The later fuel coupling is designed once, in the common energy interface.
- **The receiving pool.** There is one lumped, well-mixed receiving pool per cell, stated as an
  assumption and indexed by compartment, owner and route. Cohorts or discrete vesicles follow when an
  observable needs within-cell variation.
- **Staging.** F1, fluid-phase uptake, comes in version 1.1, and P0 is first.
- **Kept visible:** FR-3's receptor and cargo movement, exchange with a changing area, and FR-4 and
  FR-5 on a growing compartment.
- **The lead's rulings on questions 5–11:**
  - R2, with R1 refused;
  - the split-and-merge kernel is the operators owner's, inside B1's operator part, and FR-2 starts
    when it lands;
  - P0's record lives in the new operator's state;
  - areas and capacitances are `reference` reads;
  - the name is `scheduled_membrane_trafficking@1`;
  - pumps are held on the plasma patch with aggregate capacity;
  - refusal 5 gains version 1.2, with a planted case.
