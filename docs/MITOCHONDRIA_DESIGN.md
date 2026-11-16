# Mitochondria: design (proposed)

**Status: PROPOSED, 16 November 2026. Design only: no engine code.** Written on branch
`mito-design` from 3c10b833, integration-d172's landing candidate. The note reaches main after
D172's landing. It gives the user options with recommendations, and asks the D138 question (§9.1).

**The request.** The user, 16 November 2026, through the lead: "Lets start Mitochandria design now".
The lead's brief asks for a design note with options, not code. The user's standing rule for a new
system is to present options and wait for the discussion. The note has no decision number yet; the
lead logs one.

**What stays as it is:**
- **Design first (D142),** general features only (D144). Every law is named by its mechanism, never
  after a protein. Protein names below are biological context only, never IDs.
- **New physics goes into `src/cells` as modules of its structure (D185, item 3):** laws, kinds and
  operators, each declared and registered. Contributed modules are pull requests inside `src/cells`,
  each in its own namespace.
- **Reproducing a published model, or writing a reference solution for it,** needs the user's
  approval per paper (D138, D151). §9.1 asks for it.
- **External simulators and model files run only out of process,** against saved outputs. Nothing is
  imported or copied (AGENTS.md).
- **Numbers from open papers may be used with a citation (D186).** Text, figures and data files are
  not copied. Non-commercial data are analysis only (D173).

**Engine models.** This note runs none.
- The laws it proposes would join `resolved_pump_tissue@3`, D172's one modular inner model, as
  declared kinds.
- Worlds would run `resolved_pump_composite@1` over it, with `cell_owned_compartments@1` (FR-1) for
  mitochondria inside a cell.
- One host-side definition parse ran (§2.3, **probe P0**). It stepped nothing.

**Evidence and sources:**
- **The code, read at 3c10b833,** with the file and function named where used.
- **Branches, cited by commit:**
  - `fr45-next` at 6992c1cb: refusal 4 version 1.2 and refusal 5 version 1.1;
  - `core-next` at 17a3863b: §7.4 (l)–(n) of the inner-model note;
  - `cardiac-laws` at 59ae93e3: the human cardiac note;
  - `visualizer` at 213f3a76.
- **The probe's record** is in `/mnt/workspaces/Cells/mito-design-20261116-01/probe/`.
- **Sources read on 16 November** by this note's author and two research subagents (Sources, at the
  end).
- **Tags:**
  - [full]: full text read;
  - [abs]: abstract or record only;
  - [code]: a model-file page, code page or licence page;
  - [sec]: a secondary source;
  - **S**: our own derivation, arithmetic or reading.
- **No number here is typed from memory.** Each carries a source or **S**. Several [full] facts came
  through a fetch tool that summarises the page. The reference agent re-reads the article itself
  (§5.3).

## 0. The choices, in plain terms

1. **Two hosts carry one law set** (§1.1).
   - **Inside a cell, the matrix is FR-1's compartment** (host C). Its one bounding patch is the
     inner membrane. The patch's inside is the cytosol, which stands for the merged intermembrane
     space (IMS), and its outside is the matrix.
   - **An isolated organelle can also be a @3 cell** (host P): its patches are the inner membrane,
     the IMS a finite node, and the outer membrane a face to a held buffer.
     - Probe P0 found the base parses and binds this topology. Nothing was stepped.
     - It is the topology of a Gram-negative bacterium, and of the source model.
   - Each law population declares which end of its patch is the matrix-like N side.
2. **The matrix can carry its own voltage today, in the field** (§2.1). FR-1's capacitor relation
   gives V_b = −q/C_b exactly. FR-4's world runs a charged compartment.
   - **What must change is not the voltage.** It is:
     - the charge carriers: fuel rows with real valences, under a binding closure;
     - the transporter kind's limits;
     - the numerics of the ΔΨ mode.
3. **Neutral fuel rows cannot carry mitochondria** (§1.3). The nucleotide exchange is electrogenic,
   and with neutral ATP and ADP rows it moves no charge in the field solve.
   - With integer reference-species valences (ATP⁴⁻, ADP³⁻, HPO₄²⁻, H⁺), every step and the whole
     ATP loop close in integers (**S**).
   - That needs multi-form rows and a rapid closure binding H⁺ and Mg²⁺. FR-4's proton closure
     generalised, the same need as the cardiac lane's Ca²⁺ buffer.
4. **Every membrane process is one thermodynamic form:** a cycle with integer roles at both ends,
   J = k·a·S·(1 − e^{ΔG_cyc/RT}) (§1.4). It dissipates at every state by construction (**S**).
   - **What it covers:** respiration's complexes, the reversible ATP synthesis cycle, the
     nucleotide exchange, the phosphate–proton symport and the K⁺/H⁺ exchange.
   - **What it extends:** FR-4's proton pump is its special case, and the cardiac lane's exchanger
     another.
5. **The ΔΨ mode is stiff** (§2.3). Each cycle adds n²F²J₁/(RT·C) to its rate. Here J₁ is the
   cycle's voltage-dependent one-way flux.
   - **Numerics may set the effort.** The source holds its synthase near equilibrium, so J₁ is large
     there. Today's explicit booking limits steps to about 0.05/rate.
   - **The first engine step is a measurement probe,** with its criterion written first. Its result
     picks one of two effort branches (§8).
6. **The source: Beard 2005 with its 2006 Table 1 correction, recommended** (§3.1).
   - It is CC BY and thermodynamically balanced except for its NADH supply, which Cells books as a
     driven supply.
   - It has three compartments that host P matches.
   - It has a curated CellML encoding, but the authors' code is on request only, and we contact no
     one.
   - **The others:** Wu et al. 2007, its successor, is CC BY but was not reachable. Cortassa 2003 is
     free to read with no licence stated, and its CellML encoding does not integrate yet. The
     Magnus–Keizer papers were refused (403).
7. **The other options:**
   - **Detail:** one effective mitochondrion per cell first;
   - **Respiration drive:** the source's driven NADH supply (booked work) for the organelle, held
     NADH and NAD⁺ for single-law checks, and substrate reactions later;
   - **The IMS:** a finite node for the isolated organelle, merged with the cytosol for the first
     in-cell world, a pool at the cell's potential later;
   - **Cell type:** isolated cardiac mitochondria first, then a cardiac cell (§3).
8. **Generality (D144)** (§4).
   - *E. coli* is host P with its periplasm and outer membrane.
   - JCVI-syn3A is host P without the outer membrane, with its synthesis cycle running in reverse.
   - The rotor gives c/3 protons per ATP, not an integer in general: yeast's ring has 10 subunits
     [abs]. Integer roles per rotation (c H⁺, 3 ATP) make it exact.
9. **Verification** (§5):
   - each cycle against an independent reference at clamped ΔΨ and concentrations (no approval);
   - Cells' own organelle in a medium (no approval);
   - then the comparison with Beard 2005, which needs the user's approval (D138). The question is
     worded in §9.1.
10. **First experiment** (§7): respiratory control in an isolated organelle. It includes an ADP
    pulse, an uncoupler step, an inhibitor step and oxygen exhaustion, first as Cells' own
    verification.
11. **Effort** (§8, **S**):
    - P1 and M1–M5: about 23–37 agent-days if explicit steps suffice, or 29–46 if an implicit
      cycle block is needed;
    - about 15–28 working days elapsed with three owners.

## 1. What a mitochondrion needs in the modular engine

### 1.1 Topology: two hosts, one N/P orientation

**The chemiosmotic convention.** The N side is the matrix-like side, negative at the operating
point: the mitochondrial matrix, or a bacterium's cytoplasm. The P side is the positive side: the
IMS, the cytosol, the periplasm or the medium. Respiration moves protons from N to P. Synthesis
lets them back from P to N and makes ATP on the N side.

| | Host C: the matrix as FR-1's compartment | Host P: the N side as a @3 cell |
| --- | --- | --- |
| Use | Mitochondria inside a cell | An isolated organelle in a medium; bacteria |
| N side | The compartment's node, the bounding patch's **outside** | The cell, its patches' **inside** |
| P side | The owner's cytosol (IMS merged), the patch's inside | A finite outside node (IMS or periplasm), or the medium |
| Inner membrane | Exactly one bounding patch (FR-1 refusal 2) | One or several patches between the cell and the node |
| Outer membrane | None (merged), or a route between pools later (§3.4) | A face from the IMS node to a held buffer (§3.4) |
| Voltage | V_b = φ_cyt − φ_matrix = −q_matrix/C_b (FR-1 §3.1) | V = φ_matrix − φ_IMS, from the field |
| Status | FR-1 is on the base; its admissions in §2.1 | **Probe P0:** the base parses and binds it (§2.3). Unrun |

- **Signs, three conventions in play.**
  - Beard 2005 defines ΔΨ as "the outer potential minus the inner potential" [full], positive at the
    operating point.
  - Host C's V_b equals Beard's ΔΨ when the IMS is merged with the cytosol (**S**). FR-1 §1.1 notes
    that V_b has the opposite sign of the usual matrix-minus-cytosol Δψ_m.
  - Host P's V has Δψ_m's sign, the opposite of Beard's.
  - The older family uses "mitochondrion minus cytosol"
    (`surface_calcium_energy_mitochondria_spec.VOLTAGE`).
  - **Every law reads its patch voltage in N/P terms** through its declared orientation, and the run
    view names the convention (FR-1 §3.2).
- **Why two hosts.**
  - Host C is the target: one effective mitochondrion inside each cell.
  - Host P is Beard's own topology: matrix, IMS, held external buffer [full]. It is also the
    topology of a Gram-negative bacterium. It needs no change to FR-1's refusals.
  - The laws are the same on both. Only the declared orientation differs (§4).
- **Nested capacitors stay out.** FR-1 §1.4 states that two membranes between two outside nodes are
  a topology limit of @3. Neither host needs them, because the outer membrane carries no potential
  in the source: "these cations rapidly equilibrate across the outer membrane" [full].

### 1.2 The pieces, one by one

"Exists" means on the base at 3c10b833. Names marked **S** are proposals, not rulings.

| Piece | Physics | In Cells today | Proposed | Name (S) |
| --- | --- | --- | --- | --- |
| Matrix | The N-side pool, with its own rows | Host C: an FR-1 node; its role "mitochondrion" is metadata only (`operators/compartments.py`: "No physics depends on the role"). Host P: a @3 cell | Exists | — |
| IMS | The P-side pool between the membranes | Host C: none, merged with the cytosol. Host P: a finite outside node | A pool at the cell's potential later (the cardiac note's §3.2 (a), unruled) | — |
| Inner membrane capacitor | Its own capacitor and voltage, ΔΨ | FR-1's patch capacitance, V_b = −q/C_b exact at a face-free node (FR-1 §3.1); host P's patches | Exists (§2.1) | — |
| Outer membrane | Porin permeation for small solutes, no voltage | Host P: a face (`logmean_electrodiffusion@1`, passive, heat) | Its reuse for porin permeation is checked against ARCHITECTURE.md's reuse rule (§3.4) | — |
| Proton-motive force | Δp = ΔΨ − (RT ln 10/F)·ΔpH, from the field and each side's closure | The voltage and free h exist; Δp is no readout | A readout of the cycle kind | — |
| Respiration | A redox-driven proton-pumping cycle per complex: complex I pumps four protons per electron pair, complex III "also pumps four", complex IV "transfers two protons across the membrane with four charges in total" [full] | None. The transporter kind's laws hydrolyse one ATP and move one role, n = 1–4 (`inner_kinds/transporter.py`: `STOICHIOMETRY_RANGE`) | New laws of one cycle kind, each complex a population with declared roles (§1.4) | `cells.membrane_cycles@1`; law `redox_driven_proton_cycle@1` |
| ATP synthesis | A reversible cycle coupling c H⁺ (P→N) to 3 ATP, or n_A ≈ 3 per ATP in the source [full] | FR-4's `proton_atp_mass_action_positive@1` reverses past its static head (FR-4/FR-5 note §6) | An extension: rational ratio, saturation on both sides, fuel at the N side, charged rows (§1.4) | `proton_coupled_atp_synthesis_cycle@1` |
| Nucleotide exchange | Electrogenic antiport: ATP⁴⁻ out of N, ADP³⁻ in; "involves the displacement of one negative charge from the matrix to the IM space" [full] | None | A cycle with two roles in opposite directions, no fuel (the cardiac exchanger's sibling) | `electrogenic_nucleotide_exchange@1` |
| Phosphate carrier | Electroneutral H₂PO₄⁻/H⁺ symport [full: "electroneutral 1:1 H+/Pi co-transport"] | None | A cycle with two roles in one direction | `phosphate_proton_symport@1` |
| K⁺/H⁺ exchange | Electroneutral antiport. The source keeps matrix pH "nearly constant" with it [full] | None | A cycle with two roles | `potassium_proton_exchange@1` |
| Proton leak | Constant-field H⁺ route [full: Nernst–Goldman] | `proton_constant_field_leak@1` (FR-4; `processes/proton_leak.py`), in `cells.passive_routes@1` | Exists | — |
| Matrix buffering | Rapid protonation of buffers and of ATP, ADP and Pi | `cells.rapid_proton_buffer@1`: one ligand (H⁺), two-form rows; a law that moves a two-form row is refused (`species_registry.check_two_form_rows`) | An extension: multi-form rows and a second ligand (Mg²⁺), with laws that declare the forms they move (§1.3) | `rapid_binding_closure@1` |
| NADH/NAD⁺ | The redox couple, rows at the N side | Rows exist; no law | Held, or finite with a driven supply (§3.3) | `driven_redox_supply@1` |
| O₂ | A neutral row, held or finite | Exists as a row | — | — |
| Q/QH₂, cytochrome c | Electron carriers: quinone at the N side, cytochrome c on the P side | Rows exist; no law | Roles of the complexes. Cytochrome c needs a P-side pool of its own (host P's node, or a pool; §3.4) | — |
| Ca²⁺ uniport (later) | Electrophoretic Ca²⁺ entry down its gradient | @3's constant-field route can carry Ca²⁺. On a bounding patch it is admitted only beside declared kinds (refusal 4 version 1.1) | A one-role cycle, or a passive route with a factor through the routing door | `electrophoretic_calcium_uniport@1` |
| Na⁺/Ca²⁺ exchange (later) | Electrogenic exchange | Proposed by the cardiac lane (`sodium_calcium_exchange_cycle@1`, its §3.6) | Another population of that law, facing the matrix | — |

**Why not the existing kinds as they stand** (code read, base):
- **The transporter kind:**
  - fixes the fuel node to the patch's inside cell (`transporter._fuel`: "the fuel node is the
    patch's inside cell ... in version 1");
  - has one moved role and n of 1 to 4;
  - holds one population per patch;
  - refuses finite fuel (`check_definition`, `GAP_FINITE_FUEL`);
  - refuses the proton law on anything but held fuel: "finite fuel at a node with a dynamic proton
    row is refused, §5.2".
- **On host C, several populations per patch is a hard requirement.** FR-1's refusal 2 allows
  exactly one bounding patch, and the matrix's inner membrane carries every cycle.

### 1.3 One charge-consistent loop: valences and protons

FR-4's fuel rows are neutral, transformed rows at a reference pH and pMg (FR-4/FR-5 note §5). For
the matrix that fails on charge, not only on the pH band.
- **The nucleotide exchange moves one charge per turnover** [full]. With neutral ATP and ADP rows,
  the field solve sees none of it, and ΔΨ would be wrong.
- **The band does not decide it.** The source keeps the matrix pH "nearly constant" [full], so a
  0.05 pH band might hold in some protocols. The charge closure fails anyway.

**The proposed representation (S).**
- **Rows hold totals, and each row's valence is its reference (base) form's:**
  - ATP −4, ADP −3, Pi (as HPO₄²⁻) −2, NAD⁺ −1, NADH −2, and Mg²⁺ +2;
  - protons in an H_eq row (+1), counted from each base form, as FR-4's §3 counts buffer protons.
- **Each law declares its stoichiometry in base forms, with every scalar proton written out.** Its
  kinetics read whichever free forms they need from the closure.
- **The node charges are then exact by FR-4's §3 argument:** charge depends on totals only.

| Step (the node gaining) | Rows per turnover, N side | Rows per turnover, P side | Charge into N |
| --- | --- | --- | --- |
| Synthesis, per ATP | ADP −1, Pi −1, ATP +1, H_eq +(n_A − 1) | H_eq −n_A | +n_A |
| Nucleotide exchange | ATP −1, ADP +1 | ATP +1, ADP −1 | +1 (one negative charge leaves) |
| Phosphate–proton symport | Pi +1, H_eq +2 | Pi −1, H_eq −2 | 0 |
| Hydrolysis by a P-side consumer | — | ATP −1, ADP +1, Pi +1, H_eq +1 | 0 |
| **The loop, per ATP made and spent** | **H_eq +(n_A + 1)** | **H_eq −(n_A + 1)** | **+(n_A + 1)** |

- **What closes (S):**
  - Each row conserves charge in integers. For synthesis's chemistry, (+3) + (+2) − (4) − (1) = 0,
    so its `produced` record (core-next 3e7095cc) is charge-neutral.
  - The loop moves n_A + 1 protons and n_A + 1 charges per ATP. That is the source's "n_A ≈ 3" [full]
    plus one for transport.
- **Two numerical facts, both read in the code:**
  - `models/surface_tissue.capacitor_change` claims exact z·n on the CPU only for |z| in
    {0, 1, 2, 4, 8}. The spec admits [−8, 8].
    - With ADP at −3, the electrode ledger's telescoping rests on its tolerance bound, as held-bath
      tissue worlds already do.
    - That is a measurement (D148), not a refusal.
    - Conserved-at-node moieties, such as cytochrome c, may shift their valences by a constant that
      the fixed charge absorbs. Mobile rows keep their true valences.
  - Mg²⁺ must be a row if it binds. A free Mg²⁺ held fixed would make bound Mg appear and vanish with
    ATP and lose charge (**S**).
- **The closure.**
  - **What it is:** the rapid-buffer closure generalised to several ligands, H⁺ and Mg²⁺: free h and
    free Mg from the totals at every stage, by a safeguarded two-dimensional Newton (**S**).
  - **Its free-energy term:** the speciation minimum G*, booked as FR-4's §4.4 books its own. Its
    derivatives are the free base forms' potentials, so every route books against free forms (**S**).
  - **What it does to FR-4's refusal:** at a node under the closure no transformed potential is
    used, so FR-4's refusal of finite fuel at a dynamic-proton node does not arise there.
    Transformed rows keep their band where a world declares them.
  - **A shared need:** the cardiac lane asks for the same generalisation for Ca²⁺ (its §3.3 and
    question 8).

### 1.4 Thermodynamic admissibility: every cycle in one form

Cells refuses a flux that runs against its own gradient.
- Every `*_dissipated_energy_pJ` field, the kinds' included, is checked non-negative and
  non-decreasing per element on the host and the device (`surface_pump_v3.dissipation_fields`).
- So every cycle needs detailed balance at the engine's own potentials (the cardiac note's §3.8).

**The form (S).**
- **Each population declares integer stoichiometries** ν_{s,e} for species s at end e (N or P) of
  its patch.
- **Its cycle free energy is ΔG_cyc = Σ ν_{s,e} μ̃_{s,e}.**
  - Each potential is the registry's μ° (B3, one authority) plus RT ln of the closure's free base
    form, plus z F φ at that end.
  - Any chemistry inside the cycle, ATP synthesis or NADH oxidation, enters through its roles'
    standard potentials. So "the fuel's free energy" is never a separate parameter.
- **Its rate is J = k·a·S·(1 − e^{ΔG_cyc/RT})**, FR-4's form, with S ≥ 0 any declared saturation.
  - Then J·ΔG_cyc ≤ 0 at every state: dissipation is non-negative by construction.
  - The zero of J is exactly the cycle's equilibrium at the engine's potentials.

**The screen items for the reference agent.** Beard's equations and both Table 1s are images on the
article pages, so no formula was read here.
1. **The complexes and the synthesis flux** are described as mass action driven toward equilibrium
   (a "driving force" with each complex's standard energy; F1F0 by "the thermodynamically balanced
   expression") [full].
   - If they are J = X(K′·Π[substrates] − Π[products]), they are this form with S equal to the
     forward term (**S**).
   - The reference confirms it on the printed equations.
2. **The nucleotide exchange is "an empirical expression"** after Korzeniewski and Zoladz [full].
   - In its common form the flux is a difference of two saturating terms, each with a share of
     FΔΨ/RT in an exponent.
   - Its zero is the exchange's equilibrium only if the two shares sum to one (**S**, a reading of
     the common form).
   - The screen checks its sign against −ΔG on a grid. A form that fails is refused, never repaired.
3. **The phosphate carrier,** a "reversible Michaelis–Menten flux" [full], passes if its numerator
   is the mass-action difference.
4. **The NADH supply** is "an arbitrary four-parameter function" outside the thermodynamic framework
   [full].
   - Cells runs it as a driven route that books its ΔG as signed work, as D150's exchange does
     (D174).
   - That is a declared supply, not a fuel.
5. **Mg²⁺ binding is kinetic in the source** ("a forward rate X_MgA" [full]). The closure is its
   rapid-equilibrium limit, a declared reduction (D175) with its envelope checked by a kinetic
   reference (§5.1).

**The domain.**
- **The kernels refuse |ΔG_cyc/RT| > 80** (`processes/proton_pump.MAX_ABS_AFFINITY_OVER_RT`),
  206 kJ/mol at 310 K (**S**).
- **The source's printed standard energies** are −69.37 (complex I), −32.53 (III), −122.94 (IV) and
  −36.03 kJ/mol (ATP) [full]. These are 26.9, 12.6, 47.7 and 14.0 RT at 310 K (**S**).
- **A lumped NADH:O₂ cycle** would span the sum, 87.2 RT, at the source's standard state, whose proton
  convention was not read (**S**). So a lumped cycle at zero voltage is of the order of the domain.
  Per-complex cycles stay inside it.
- **If a lumped cycle is wanted,** the remedy is a one-sided domain (a ≤ 80) for strongly exergonic
  cycles, since e^{a} underflows harmlessly (**S**). It would be a declared change.

**Stoichiometry.**
- Respiration lumped moves ten protons to the P side per NADH: the source's counts are 4, 4 and 2
  [full].
  - The charges per complex are 4, 2 and 4, since complex III's protons include two taken up on the
    N side and complex IV moves "four charges in total" [full; **S**].
  - Either way, ten is beyond the kind's 1–4.
- The synthesis cycle's c/3 need not be an integer (§4).
- Integer roles per rotation (c H⁺ and 3 ATP) keep the cycle exact.

## 2. The key engine question: can a cell-owned compartment carry its own voltage?

**Yes, in the field, today.** The two halves below separate admission from numerics.

### 2.1 Admission: what FR-1 allows (host C)

**Holds today** (code read, base, unless named):
- **The capacitor.** At a face-free compartment node with one patch, V_b = −q_j/C_b exactly, and the
  owner's plasma membrane sees q_cell + q_comp (FR-1 §3.1, a reading of `numerics/surface_field`).
  - The older family uses the same relation for its own mitochondrial capacitor
    (`models/surface_calcium_energy_mitochondria.mitochondrial_voltage`). That family is
    `resolved_calcium_energy_mitochondria@1`: passive constant-field transport
    (`processes/mitochondrial_passive.py`, which "adds neither respiration nor ATP production"),
    off the modular path.
- **Charged routes on the bounding patch.**
  - Refusal 4 version 1.1 (`operators/compartments.py`) admits the known kinds: `ROUTE_KINDS` (the
    transporter and the passive routes) and `READ_KINDS` (the proton buffer). It does so only with an
    IMEX tableau, since kinds need IMEX (`surface_pump_v3._check_kinds_solver`).
  - On `fr45-next` (6992c1cb), version 1.2 adds `FACTOR_KINDS` (FR-5's damage and pH condition).
- **The step rule holds the matrix node.**
  - B7's definition-time term (`surface_pump.face_free_node_rate`) bounds each free face-free node
    against its own patches.
  - With kinds declared, the per-stage rule (`surface_pump_v3.membrane_rate` with
    `free_outside_nodes`) does the same, taking each kind's `stage_term` at both ends of its patch.
- **A charged start.**
  - At the base, refusal 5 version 1 refuses any nonzero charge anchor
    (`compartments.refuse_charge_anchor`).
  - On `fr45-next`, version 1.1 admits one where kinds and an IMEX tableau are declared
    (6992c1cb), so a charged world can resume from its own checkpoint.
- **A charged compartment has run.**
  - FR-4's declared world reaches V_b = −7.33 mV at its 1800 s steady state, with +5.757e-14 C on the
    lumen (the commit message of `fr45-next` 6992c1cb, the checkpoint's own).
  - FR-4's P_K = 0 control would charge its lumen to a static head of about −0.266 V (FR-4/FR-5 note
    §13.1, **S** there). The independent reference ran it, stalling at pH 7.14 (PROGRESS, 15
    November).
  - I found no engine record of that control. It is item C9 of FR-4's proposed dt study
    (`validation/compartment_ph_engine/dt_study.py`).
- **The voltage's size.**
  - @3's −120 to +60 mV domain applies to channel populations only (FR-4/FR-5 note §13), and
    refusal 4 keeps channels off a bounding patch. So V_b ≈ +0.18 V is admissible there.
  - A Ca²⁺ uniport must therefore be a kind's law, never a @3 channel population.

**What must change for mitochondria on host C:**
1. **Refusal 4 must know the new kind:** a version 1.3, host-only. Unknown kinds fail closed.
2. **Several populations on the one bounding patch** (§1.2).
3. **Roles at the patch's outside node.** The matrix is the outside node, and the transporter kind
   fixes fuel at the inside cell.
4. **Multi-form rows and the binding closure** (§1.3), which lift `check_two_form_rows` for laws that
   declare the forms they move.
5. **Refusal 5 version 1.1 landed** from `fr45-next`, so a charged matrix can restart from its
   checkpoint.
6. **The compartment map's address** "species S in compartment C" (INNER_MODEL_V4_DESIGN §9.2, B2),
   so the cycles name their ends by compartment, not by storage.
   - It is reserved, not built, and costs 2–3 agent-days with its first consumer.
   - It is a prerequisite only for host C.

### 2.2 What must change on both hosts

- **The cycle kind** (§1.2, §1.4):
  - roles at both ends, an orientation and integer stoichiometries beyond 4;
  - several populations per patch;
  - held or moved roles;
  - the kind interface's existing seams for step terms, ledgers and the run view (INNER_MODEL_V4_DESIGN
    §7.4 (k), (m); core-next 3e7095cc and 74a75241). The API is the core owner's design, not this
    note's.
- **The binding closure** (§1.3).
- **A cycle heat booking that cannot go negative** (§2.3).
- **The species cap.**
  - Host P with the source's three compartments needs about 14–16 rows (**S**): H, K, Mg, ATP,
    ADP, Pi, NADH, NAD, Q, QH₂, two cytochrome c forms, O₂, a matrix buffer, and an anion or AMP.
  - Host C in a cell with Na⁺ adds more.
  - FR-9's cap of 16 (`species_common.MAX_SPECIES`) rises as needed, each raise a D148 change with a
    guard world and a measurement (D165, amended).

### 2.3 Numerics: the ΔΨ mode

**The rate (S).**
- A cycle that moves n charges per turnover has the slope conductance G = n²F²J₁/RT, with J₁ its
  voltage-dependent one-way flux. In FR-4's form J₁ = k·a·S·e^{ΔG_cyc/RT}, the reverse flux.
- **The mode's rate is ΣG/C.** At the source's C_IM, 6.75 × 10⁻⁶ mol (L mito)⁻¹ mV⁻¹ [full], which
  is 651 F per litre of mitochondria (**S**), each mM/s of J₁ per mitochondrial volume adds n² × 5.5
  s⁻¹ (**S**, at 310 K).
- **Near equilibrium, J₁ far exceeds the net flux.** The source holds its synthesis flux there on
  purpose: "X_F1 is determined to be large enough" [full].

| J₁ (mM/s per mito volume) | n = 10 (lumped) | n = 4 (complex I) | n = 3 (synthesis, per ATP) | Step at the stage rule, dt·ΣG/C ≤ 1 | Step at today's booking, ≈ 0.05 |
| --- | --- | --- | --- | --- | --- |
| 1 | 555 s⁻¹ | 89 s⁻¹ | 50 s⁻¹ | 1.8–20 ms | 0.09–1 ms |
| 10 | 5.5e3 | 890 | 500 | 0.18–2 ms | 9–100 µs |
| 100 | 5.5e4 | 8.9e3 | 5.0e3 | 18–200 µs | 0.9–10 µs |

- **The table is parametric.** No flux magnitude was read here. The component references read J₁ at
  the source's own parameters (§5.1).
- **The 0.05 is FR-4's measured energy-ledger limit for constant-field patch routes** (FR-4/FR-5
  note §7.2). Cycles are untested.
- **Cost (S).** FR-4's charged-patch runner path costs about 3.6 ms per step in a three-node world
  (FR-4/FR-5 note §7.2). 300 s of protocol would cost:
  - about 30 CPU-hours at a 10 µs step;
  - about 18 CPU-minutes at a 1 ms step.

  FR-4's vector path steps about 7.5 times faster (PROGRESS, 15 November).

**The booking.**
- `imex_step` books kinds' heat with the tableau, and ARS(2,2,2)'s explicit weights book a negative
  increment where a route's power falls by more than about 59% within a step (the cardiac note's
  §3.8, a code reading there).
- A cycle near equilibrium dissipates little, and one that crosses equilibrium within a step
  dissipates nothing at the crossing. Examples are the synthesis cycle reversing on an uncoupler, and
  the exchange reversing.
- So mitochondria need what the cardiac lane's H1 needs for channels: a non-negative or exact
  booking for cycles. One seam would serve both.

**The implicit patch is not there yet.**
- `processes/patch_electrodiffusion.py` (`bounding_patch_constant_field@1`) holds the Newton stage
  solve for constant-field routes only.
- It has no caller in `src/cells` at the base, on `core-next` or on `fr45-next` (a search).
- A local implicit block for a compartment's cycles would be new, a new IMEX ID under D147, and its
  Jacobian would not stay diagonal-plus-rank-one:
  - the cycles couple rows;
  - the closure sits inside it.

**The first engine step is a measurement, its criterion written before it runs.** Probe P1:
- **The world:** one cycle on a bounding patch: FR-4's proton law, the nearest existing cycle, run
  past its static head at large capacity, with n = 4.
- **The ladder:** dt × ΣG/C_b from 0.01 to 2.
- **What it records:** where the per-stage rule refuses, where the energy ledger refuses, and the
  state's error against an independent two-capacitor reference.

Its result picks the effort branch of §8:
- **E:** explicit steps at a declared dt × ΣG/C_b suffice for the first protocols;
- **I:** an implicit cycle block is needed.

**Probe P0, already run** (host-side parse only; record and script in the evidence folder).
- **The world:** at the base, `parse_spec` admits a @3 definition with:
  - a cell standing for the matrix, with three patches to one finite node (the IMS);
  - a face from that node to a held bath, its diffusivity zero for two rows;
  - rows of valence +2, −1, −2, −3 and −4;
  - a start charged at C × (−0.18 V).
- **The result:** `get_model` binds it with finite initial values.
- **The limit:** nothing was stepped, so it shows no stability, accounting or field consistency.

## 3. Options for the user

### 3.1 The source of equations and parameters

Read on 16 November (Sources). "Free" means readable without a licence statement. D186 lets its
numbers be cited.

| | **Beard 2005 + 2006 correction** | Wu et al. 2007 | Cortassa et al. 2003 | Magnus–Keizer 1997/98; Bertram et al. 2006 | Vinnakota et al. 2016; Bazil et al. 2016 | A reduced Cells model |
| --- | --- | --- | --- | --- | --- | --- |
| Covers | Respiratory complexes, synthesis, nucleotide and phosphate transport, K⁺/H⁺ exchange, leak; Mg²⁺ and H⁺ binding; no Ca²⁺ or Na⁺, no TCA cycle [full] | Adds the TCA cycle, metabolite transport and electrophysiology; isolated cardiac mitochondria and skeletal muscle in vivo [abs] | TCA cycle, oxidative phosphorylation and Ca²⁺ handling; "twelve ordinary differential equations" [abs] | β-cell mitochondrial Ca²⁺ handling; six inner-membrane mechanisms [abs]; a reduction of it [abs] | Beard's successors: phosphate regulation, ROS [abs] | The same law set, fitted to nothing, verified on its own |
| Open and licence | CC BY, both [full] | Licence "cc by" in Europe PMC's record; the full text not reached (the publisher served a redirect page) | Free in PMC (PMC1201507), no licence stated; the full text not read (Europe PMC's XML: HTTP 500) | Not in PMC; the APS page refused (HTTP 403). Bertram 2006: Elsevier, not in PMC | Free in PMC (PMC4776028, PMC4776027), no licence stated; abstracts only | — |
| An IMS of its own | Yes: cytochrome c and adenylate kinase there; the IMS "1/10 of the mitochondrial water volume" [full] | Not read | Not read | Not read | Not read | Declared |
| States | 17 [full] | Not read | 12 [abs] | Not read | Not read | 9–16 rows |
| The screen (§1.4) | Mass action toward equilibrium, except the NADH supply (driven) and the empirical exchange (items 1–5) | Abstract: "thermodynamically balanced reactions" [abs] | Not read; its formulas need the screen | Not read | Not read | By construction |
| A reference from the paper alone | Expected: CC BY. Equations and tables are images, so a fresh agent confirms they are legible in the PDF | Not until the full text is reached | Not until the full text is read | No | Not read | Its own appendix |
| Model files | CellML, curated (Physiome Model Repository; CC BY 3.0 on its metadata page; "edited to correct dimensional errors"; runs in COR and OpenCell) [code]; a BioModels auto-conversion, CC0 per a mirror [sec]; the authors' code "available from the author upon request" [full] | CellML, curated, CC BY 3.0 per a search summary; needs steps near 1e-6 and tolerances of 1e-12 [code] | CellML, "will not integrate at the moment" [code] | CellML, "original unchecked version" [code]; BioModels auto-conversions [sec] | None found | — |
| Data it was fitted to | Bose et al. 2003 (fitted); Wilson et al. 1988, Gnaiger 2001, Gnaiger and Kuznetsov 2002 (compared) [full]. Bose 2003 not read (the JBC pages refused or redirected) | Not read | Not read | Not read | Not read | — |

**Recommended: Beard 2005 with its 2006 correction.**
- **It is open (CC BY)** and its correction is published.
- **Its fluxes are thermodynamically balanced,** except two that Cells handles by declaration: the
  NADH supply as a driven route, and the empirical exchange through the screen.
- **Its three compartments match host P,** so the comparison needs no IMS departure.
- **It covers the review's second priority exactly,** one effective mitochondrial system
  (PAPER_REVIEW_MITOCHONDRIA.md), and fits the cap.
- **Its limits:**
  - it was fitted to steady-state data from isolated cardiac mitochondria;
  - its parameters are not universal, which the review already says;
  - Ca²⁺ and the TCA cycle are absent.
- **Successors by its group come later as laws and parameter sets on the same kinds.** Wu et al.
  2007's TCA cycle is the detailed representation of Beard's NADH supply (D175) once its full text is
  reached.

**Why not the others now:**
- **Cortassa 2003** carries the calcium the review ranks third, but its full text was not read, its
  formulas are unscreened, and its CellML encoding does not integrate yet.
- **Magnus–Keizer** could not be read openly.
- **A reduced Cells model** answers numerical questions only. It is M4's verification world (§5.2),
  not a source.

### 3.2 The detail level

- **Recommended: one effective mitochondrion per cell.**
  - A lumped node of N identical members, with N × volume, area, capacitance and capacities. It is
    exact for identical members (FR-1 §1.3; FR-4/FR-5 note §1).
- **Later:**
  - classes per cell, each its own compartment of one owner. FR-1 allows several compartments per
    owner, for example two populations with different capacities;
  - individual mitochondria with fission, fusion, turnover and inheritance, the review's fourth
    priority. They need FR-1's doors C, D and F, and stochastic partition is out of scope there.
- **Respiratory detail is a declaration on one law:**
  - **per-complex populations** (I, III and IV) where a P-side pool holds cytochrome c: host P's IMS
    node. Recommended for the source comparison;
  - **two populations** (NADH:Q and QH₂:O₂, cytochrome c eliminated) where the IMS is merged: host
    C's first world. This is a declared reduction (D175): cytochrome c's redox state cannot be
    observed;
  - **one lumped cycle** is not recommended. It sits at the domain's edge and hides the quinone pool.

### 3.3 The respiration drive

| | Held redox supply | Driven supply (the source's form) | Substrate reactions |
| --- | --- | --- | --- |
| What | NADH and NAD⁺ held at the N side (held roles, one writer); the maintenance books −ΔG per turnover as work | Finite NADH and NAD⁺, moved by complex I in the step; a supply law relaxes them toward a declared ratio at a declared rate, with the source's phosphate factor, booked as signed work | A declared donor oxidised by reactions (D152) at the N side; later the TCA cycle |
| Shows | Respiratory control at a fixed redox state; interruption by availability only | NADH dynamics, as the source fits them; interruption by the supply's rate | Finite fuel: depletion and recovery |
| Needs | The cycle kind's held roles | A small driven-supply law in the cycle kind, in step | D152's charged reactions (its version 2), the finite-fuel world (D176 item 2), and its "moved by the step" admission |
| Recommended for | Single-law checks (§5.1) | The organelle (M4, M5) | Later: Wu 2007's detailed representation |

### 3.4 The intermembrane space

- **Merged with the cytosol (host C).** No entity. This is the first in-cell world.
  - **Departures:** cytochrome c cannot sit in the IMS, so respiration takes two cycles. The outer
    membrane's permeation disappears.
- **A finite node with a face to a held buffer (host P).** It exists (probe P0, unrun). This is the
  isolated organelle and the comparison.
  - **The face's law** is passive electrodiffusion with heat (`logmean_electrodiffusion@1`). It
    stands in for porin permeation, parameterised from the source's outer-membrane permeabilities
    [full: "pA and pPi"].
  - **The reuse needs the lead's check:** ARCHITECTURE.md lets a law be reused only where its
    physical contract matches.
- **A pool at the cell's potential (host C, later).** This is the cardiac note's §3.2 (a), unruled:
  - a pool, a patch whose inside is a pool, and a route between pools;
  - cytochrome c and adenylate kinase stay in the IMS;
  - cytochrome c release becomes a transfer (FR-5).
  - **Two caveats:** it opens "subspace calcium", which the inner-model note's §13.1 closes in
    version 1, and it needs the lead's ruling for both lanes.
- **A nested capacitor:** refused by @3's topology (FR-1 §1.4), and needed by no source.
- **Recommended:** the finite node for the isolated organelle, merged for the first in-cell world,
  and pools when cytochrome c release or a resolved IMS is asked for.

### 3.5 The cell type

- **Recommended: isolated cardiac mitochondria first** (the source's system; no cell), then a cardiac
  cell for the in-cell milestone (M6).
  - The cardiac cell pairs with the human cardiac lane, whose ORd cell holds ATP fixed today.
  - Beard's data come from isolated cardiac mitochondria [full], not from human cells, so M6 declares
    the mismatch.
- **Alternatives:** a hepatocyte, a β-cell (the Magnus–Keizer line, unreadable today), or a generic
  cell.
- **Parameter sets live in `validation/`** as cited organism definitions
  (SYN3A_MINIMAL_CELL_TRACK §10). Nothing species-specific goes into `src/cells` (D144).

### 3.6 For the lead (not the user's)

1. **Host P for the isolated organelle**, or host C with a large owner cell standing for the medium.
   - Host P is Beard's topology and needs no FR-1 change.
   - Host C exercises the in-cell path from the start.
   - Recommended: host P, with host C at M6.
2. **The cycle kind.**
   - A new kind, recommended; it leaves FR-4's world bitwise, with an agreement test against
     `cells.transporter@1` at FR-4's stoichiometry.
   - Or `cells.transporter@2`.
3. **The binding closure:** B4 generalised to several ligands, or a sibling kind.
4. **The cycle booking.**
5. **The ΔΨ numerics:** probe P1 first.
6. Items 2–5 overlap the cardiac lane's questions 8, 9 and 13. One design for both lanes is
   recommended (§9.2).

## 4. Generality (D144): one law set for mitochondria, *E. coli* and JCVI-syn3A

- **The laws are written on N and P ends, never on "inside" and "outside".**
  - A population declares which end of its patch is N. The kernel reads its potentials and
    concentrations through that orientation.
  - Stoichiometries, capacities and saturations are parameter sets in organism definitions
    (`validation/`).
- **Mitochondria:** host C in a cell (N = the bounding patch's outside), host P isolated (N = the
  patch's inside).
- ***E. coli*:** host P.
  - The cytoplasm is the cell (N). Its plasma patches carry the respiratory cycles and the synthesis
    cycle.
  - The periplasm is a finite node, and the outer membrane a face to the medium: Gram-negative
    anatomy, the same as an isolated mitochondrion (**S**).
  - Its own respiratory stoichiometries are parameter sets. They were not read here (Sources).
- **JCVI-syn3A:** host P with no outer membrane.
  - The plasma patch faces the medium. It has no respiratory chain.
  - The synthesis cycle, with the same law, runs in reverse, hydrolysing ATP to build the
    proton-motive force. The viewer's Syn3A record says the 2019 reconstruction has this machine push
    protons out of the cell, and that the 2019 paper found its genes essential [sec: `visualizer`
    213f3a76, the protein atlas's Syn3A notes].
  - The direction follows from ΔG_cyc, not from a switch.
- **The rotor's ratio.** Per rotation the rotor carries c protons and makes 3 ATP, so H⁺/ATP is c/3.
  - The yeast mitochondrial rotor has 10 c subunits (Stock, Leslie and Walker 1999 [abs], read on
    the RCSB PDB entry that reprints the abstract), so 10/3 there (**S**).
  - The source uses n_A ≈ 3 [full], an effective integer.
  - Both are parameter sets of the same law: an effective integer per ATP, or integer roles per
    rotation.
  - The mammalian and *E. coli* counts were not read here (Sources).
- **FR-4's proton pump is the special case:** n of 1 to 4, saturation on the hydrolysis side,
  transformed held fuel at the inside cell.
  - The synthesis cycle generalises it and does not replace it. FR-4's world keeps its kind and
    stays bitwise.
- **The viewer's bacterial records** say "The law inventory has no F-type ATPase" (E. coli,
  *M. pneumoniae* and Syn3A notes, `visualizer` 213f3a76). The synthesis-cycle law fills that, and
  D185's declarations manifest would carry it to the viewer.

## 5. Verification

### 5.1 Component references: each law at clamped ΔΨ and concentrations (no approval)

Single cited laws need no approval (the cardiac note's §5.1; EXCITABLE_TISSUE_DESIGN §11).
- **The reference is written by a fresh agent** that reads neither the engine nor any model file.
  - It writes from the laws' declared equations (the successor design's appendix) and the source's
    printed formulas.
  - It runs out of process with high-precision arithmetic, as the finite-energy reference uses
    80-digit Decimal arithmetic.
- **For each cycle,** on a grid of ΔΨ, both sides' pH and the concentrations:
  - the rate, ΔG_cyc and the sign test (dissipation ≥ 0);
  - the zero at equilibrium and the reversal past it;
  - the static head;
  - `stage_term` against a finite difference of the charge current;
  - the one-way flux J₁ at the source's parameters, for §2.3's table.
- **The closure** (free h and Mg from the totals) is checked against a kinetic binding reference, as
  FR-4's A.2 does. Its envelope is declared first, and a case outside it must fail (D175).
- **Planted controls:** a reversed stoichiometry sign, and an exchange whose exponent shares do not
  sum to one. The screen must refuse both.
- **The engine side is a kernel harness, then the law inside @3:** a cell or compartment carrying
  the law and a leak, against the reference's integration of the same pair.

### 5.2 Cells' own organelle in a medium (no approval)

- **The world:** host P with generic, declared parameters, not the source's set. It reproduces no
  published model.
- **The protocol:** the first experiment (§7).
- **Checked against an independent integration of the same declared equations** (Radau, tight
  tolerances):
  - every ledger: material, charge and energy;
  - a dt study at second order;
  - a planted error.
- **Judged only through a registered protocol** (D143, D176's pattern).

### 5.3 The whole-organelle comparison (needs the user's approval: D138, D151)

**What runs.**
- **The engine:** `resolved_pump_composite@1` over `resolved_pump_tissue@3`, host P, with the
  source's parameters.
- **Who writes the references.** This note's author has read the engine, so it writes neither R1 nor
  R2. Both go to fresh agents.
- **R1, an independent reference.** A fresh agent writes it from Beard 2005 and its 2006 correction,
  reading neither the engine nor any model file. It runs out of process with its own stiff
  integrator and convergence check, in two arms:
  - R1-published: as printed;
  - R1-declared: with §5.4's departures, one switch each.
  - **Unread so far:** the equations and both Table 1s are images on the article pages. The agent's
    first task is to confirm that they are legible in the open PDF, the corrected table included.
    If not, it stops and reports.
- **R2, the published model, unmodified and out of process.**
  - **The file:** the Physiome Model Repository's curated CellML encoding (CC BY 3.0 [code]).
  - **The tool:** libOpenCOR (Apache 2.0 [code]) in its own environment. Myokit (BSD 3-Clause) only
    if it imports the file: its documentation speaks of electrophysiology models [code].
  - **Unread so far:**
    - the encoding was "edited to correct dimensional errors";
    - whether it carries the 2006 correction is unknown;
    - the authors' code is on request only, and we contact no one.
  - **The rule:** only saved outputs enter the evidence. The file is used by reference under
    `/mnt/workspaces/Cells` and never committed.

**What is compared:** the source's own protocols, as its text states them [full].
- **The steady states:**
  - external Pi from 0 to 10 mM, at external ADP 0 (state 4) and 1.3 mM (state 3);
  - external pH 7.1, K⁺ 150 mM and total Mg²⁺ 5 mM;
  - oxygen at 20 mm Hg.
- **The outputs:** NADH/NAD_tot, oxygen consumption, cytochrome c's redox state and ΔΨ (its Figs.
  2–5).
- **The low-oxygen behaviour:** its Fig. 6, with the model's P50 of 0.373 µM.

**How it is judged** (registered before its run, with D150's and MG0c's lessons):
- **The engine against R1-declared: judged.**
- **R1-published against R2: judged,** as the references' own check.
- **The engine against R2: reported, not judged,** each difference attributed to a declared change.
- **The registration fixes:** tolerances from the references' own convergence or a stated physical
  scale, never from the engine's spread; a planted coefficient change that must be caught; the CPU as
  the backend.
- **Scope:** isolated cardiac mitochondria in a held buffer, steady states and the low-oxygen sweep.
  Not a cell, not calcium, and not the measured data.
- **The measured data** (Bose et al. 2003) are a later, separate question (D151), once a fresh agent
  can read them.

### 5.4 Departures from the source, as far as known before its equations are read

The list closes when R1's author has read the printed equations. Any addition is reported to the
user before the judged run, never introduced silently.

| | Departure | Status | Why | Its size |
| --- | --- | --- | --- | --- |
| D1 | Mg²⁺ binding in rapid equilibrium (the closure), not kinetic | Definite | One closure per node (§1.3) | The envelope's lag, measured against a kinetic reference (§5.1) |
| D2 | Matrix H⁺ buffering by a declared buffer species, at the source's capacity at its operating pH | Definite | The closure buffers by species, not by a capacity formula | Reported over the protocol's pH range |
| D3 | The synthesis activity finite, at a declared value where the outputs converge | Definite | The source sets it "large enough" to sit at equilibrium [full]; Cells needs a finite rate | Convergence shown in R1 as the activity grows |
| D4 | The engine's exact SI constants | Definite | One authority for constants | Reported |
| D5 | The outer membrane as a face (`logmean_electrodiffusion@1`) | Conditional on the printed flux form | A reused passive law | Reported if the forms differ |
| C1 | The empirical exchange refused or changed if it fails the screen | Conditional (§1.4, item 2) | A flux against its gradient | Any change goes to the user |
| C2 | A standard potential declared from the source where it disagrees with the registry | Conditional | One authority for each standard potential (INNER_MODEL_V4_DESIGN §10.2) | — |

**Not departures:** the NADH supply booked as work (a booking, not a state change); the lumped
population; host P's split patches. The split patches' capacitances add exactly in the field
(**S**).

### 5.5 External tools, model files and their licences (read on 16 November 2026)

By the research subagent unless marked. None states a non-commercial clause.

| Item | Licence as read | Note |
| --- | --- | --- |
| Beard 2005 CellML (exposure 959a4da5…, workspace `beard_2005`) | CC BY 3.0, on its metadata page; none on the exposure page [code] | Curated: "edited to correct dimensional errors"; reproduces the authors' MATLAB |
| Beard 2005 in BioModels (MODEL4151491057) | CC0, per the OmicsDI mirror's record; BioModels' own terms page refused (HTTP 403) [sec] | Auto-converted from CellML, not human-curated |
| Wu 2007 CellML (357bde34…) | CC BY 3.0 per a search summary; the metadata page was not opened | Replicates the MATLAB; needs very small steps |
| Cortassa 2003 CellML (e5ba9ba5…) | CC BY 3.0 on its metadata page [code] | "Will not integrate at the moment" |
| Magnus–Keizer 1997, 1998 CellML | Not stated on the exposure pages [code] | "Original unchecked version" |
| Bertram 2006 CellML (a7f8b457…); BioModels MODEL1006230114 | CC BY 3.0 and CC0 per search summaries only | Reproduces "some of the results" |
| libOpenCOR | Apache 2.0 [code] | Simulates CellML |
| OpenCOR desktop | GPL 3.0 (copyleft) [code] | Run out of process only |
| Myokit | BSD 3-Clause [code] | "Can import most models listed in the CellML electrophysiology repository" |
| libRoadRunner, tellurium | Apache 2.0 [code] | SBML |
| COPASI | Artistic License 2.0 [code] | SBML |
| AMICI | BSD 3-Clause [code] | SBML, PySB |
| The Beard lab's GitHub repositories | MIT where shown [code] | Later works, not confirmed to be the 2005 or 2007 code |

- **Running a file out of process distributes nothing** (the cardiac note's §5.3). Only our saved
  outputs and our own code enter the repository.
- **Any such tool runs in its own environment,** as BETSE does (`venv-betse`), from one directory
  under `validation/`. None exists today.

## 6. Prerequisites and order

| Prerequisite | Gates | Status |
| --- | --- | --- |
| D172's landing: one modular inner model, with the transporter, the passive routes and the proton buffer | Everything | Landing candidate 3c10b833 |
| Refusal 4 version 1.2 and refusal 5 version 1.1 | Host C's charged restarts | `fr45-next` 6992c1cb, not on the base |
| Probe P1: one cycle's step limits on a bounding patch (§2.3) | M1's numerics branch | Proposed; criterion first |
| The cycle kind (§1.2, §1.4) | M1 onward | New; owner the lead's call, with the cardiac lane's exchanger (§9.2) |
| Multi-form rows and the binding closure for H⁺ and Mg²⁺ (§1.3) | M1 onward | New; B4's generalisation, shared with the cardiac lane's Ca²⁺ |
| A non-negative or exact cycle heat booking (§2.3) | M3 onward | New; shared with the cardiac lane's H1 seam |
| An implicit cycle block, a new IMEX ID (D147) | Only if P1 says so | New |
| The species cap above 16 | Host C in a cell | A D148 change with a guard and a measurement (D165, amended) |
| The compartment map's addressing (INNER_MODEL_V4_DESIGN §9.2) | Host C (M6) | Reserved, not built |
| Finite fuel shared by reactions and consumers (the finite-fuel acceptance world, D176 item 2) | M6's demand pulse | Designed; the transporter's finite fuel is refused in this round |
| Pools at the cell's potential | A resolved IMS in a cell; ER contacts (M7) | The cardiac note's proposal, unruled |
| The routing door (core-next) | Later regulation: Ca²⁺-activated supply; FR-5's damage on the inner membrane as permeability transition | Built on `core-next` |
| The user's D138 approval | M5 only | Asked in §9.1 |

**Order:** P1 → M1 → M2 (branch I only) → M3 → M4 → M5 if approved → M6 → M7, M8.

## 7. The first experiment

**Recommended: respiratory control in an isolated organelle,** as Cells' own verification first
(§5.2, no approval), then with the source's parameters (§5.3, if approved). The review asks for this
order: "Reproduce an isolated-mitochondria reference before connecting it to the tissue model".

- **The world:** host P, the matrix holding a lumped population; the IMS node; a held buffer.
- **The steps, each scheduled on the step grid:**
  1. **An ADP step in the buffer** from 0 to 1.3 mM and back: state 4 → 3 → 4, through FR-10's
     `scheduled_bath_composition@1`, which acts on held baths (its note). Whether it composes with
     declared kinds is checked first;
  2. **an uncoupler step:** the proton leak's availability raised. ΔΨ falls and the synthesis cycle
     reverses, so it tests the booking;
  3. **an inhibitor step:** the terminal complex's availability set to 0. Respiration stops, and the
     reversed synthesis and exchange spend the buffer's ATP to hold ΔΨ;
  4. **oxygen exhaustion** in a finite variant: O₂ falls through the source's P50 range. Respiration
     stops as a supply interruption.
- **What it shows:**
  - ΔΨ, both sides' pH, NADH, the cycles' rates, oxygen use and ATP export;
  - the ledgers;
  - the reversal, without a refused booking.
- **Its controls:** the uncoupled world, and a world with the exchange off, whose effect must exceed
  the declared budget.
- **Why this one:** it needs no cell, no finite cytosolic fuel and no FR-1 change. It exercises every
  cycle and both directions of the synthesis cycle, and it is the source's own system.
- **The alternatives, later:**
  - **an in-cell demand pulse or supply interruption** (M6): one effective mitochondrion feeding a
    cytosolic ATP consumer, with ATP recovery, plasma voltage and calcium clearance measured. It needs
    finite shared fuel and host C. It is the review's first-priority experiment, extended;
  - **an ATP-synthesis curve against Δp** at clamped ΔΨ: part of §5.1.

## 8. Milestones, effort and cost; the viewer

Estimates are ours (**S**), in agent-days. They follow the comparable costs of the inner-model
note's §7.4 (h): the transporter kind 2.5–3.5, the stage-read slot 1–1.5 and the implicit slot 1–1.5.

| Milestone | Engine models | Content | Effort |
| --- | --- | --- | --- |
| M0 (this note) | None | Options and the D138 question | Done |
| P1 | @3 with `cells.transporter@1` on a bounding patch | The cycle step-limit probe, criterion first (§2.3) | 0.5–1 |
| M1: the seams | @3 with the new kinds declared | The cycle kind; multi-form rows and the binding closure; the cycle booking; refusal 4 version 1.3. Crossrev identity for every existing world; FR-4's world bitwise | 8.5–13.5 (kind 4–6, closure 3–5, booking 1–2, refusal 0.5) |
| M2: the implicit cycle block (branch I only) | @3 with a new IMEX ID | The per-node Newton with the closure inside; its qualification against references | 6–9 |
| M3: the laws and their references | As M1 | The cycles of §1.2 as parameter sets; the driven supply; component references by a fresh agent (§5.1), in parallel | Laws 2–4; references 3–4 |
| M4: Cells' own organelle | `resolved_pump_composite@1` over @3, host P | §7's protocol, registered and judged (§5.2) | 3–5, plus CPU |
| M5: the comparison with Beard 2005 (if approved) | As M4, the source's parameters | R1, R2 and the judged comparison (§5.3) | 6–9 |
| M6: in a cell | Host C with `cell_owned_compartments@1` | One effective mitochondrion feeding a cytosolic ATP consumer on finite fuel; the cap raise; the compartment map's addressing | 5–8, plus 2–3 for the map |
| M7: calcium | As M6, with pools | Uniport, exchange and matrix Ca²⁺ buffering; a reduced ER-contact pool (the review's third priority) | 6–10 |
| M8: populations | Its own design | Fission, fusion, turnover and inheritance (FR-1's doors C, D and F) | Its own note |

- **P1 and M1–M5 in all (S):**
  - branch E (explicit steps suffice): about 23–37 agent-days;
  - branch I: about 29–46.
- **Elapsed:** with three owners (the core owner, a laws owner and a references agent), about 15–28
  working days.
- **Shared with the cardiac lane:** the cycle kind, the closure and the booking. One design for both
  lanes lowers the sum.
- **CPU (S):**
  - P1 and the component references take minutes.
  - M4's protocol of a few hundred seconds takes minutes at a 1 ms step, and tens of CPU-hours at
    10 µs, on the runner path's upper-bound cost (§2.3).
  - So branch E's step decides whether M4's runs are detached jobs, with durable logs and result or
    failure records (AGENTS.md's rule for runs of 10 minutes or more).
- **Not authorised by this note:**
  - any engine code before the user chooses;
  - a law named after a protein;
  - a feature for one experiment (D144);
  - a whole-organelle reference, or a run of a published model file, without the user's approval
    (D138, D151);
  - importing or copying any external code or file.

**The viewer.**
- **The brief expected "planned" mitochondria; the viewer says "established".** The `cap.mitochondria`
  entry is marked "established", representation "simulated", `runs_in: resolved`. That is so in
  `visualizer/data/architecture/overlay.json` on `visualizer` at 213f3a76, and in the generated scene
  on main. It describes the older
  family's passive ion exchange and own voltage, and says "Respiration and ATP synthesis are not
  modelled". That is a mismatch with the brief, reported to the lead.
- **A proposal for the visualizer's owner** (this note edits no visualizer file):
  - a capability for mitochondrial energetics, "designed" from this note;
  - then "landed" when M1–M4 integrate, and "qualified" with M4's judged protocol, with M5's
    comparison noted when it runs;
  - `runs_in` gaining the composite;
  - the bacterial atlas notes naming the synthesis-cycle law when it lands;
  - ΔΨ, both sides' pH, Δp and the cycles' N→P flows reaching the run view through the new kinds'
    run-view declarations (D154; KindView, core-next 74a75241).

## 9. Questions

### 9.1 For the user

1. **The source.** Beard 2005 with its 2006 correction (recommended), Wu et al. 2007 once its full
   text is reached, or Cortassa et al. 2003 for calcium (§3.1)?
2. **The detail level.** One effective mitochondrion per cell first, with classes and individual
   mitochondria later (recommended, §3.2)?
3. **The respiration drive.** The source's driven NADH supply for the organelle, held NADH for
   single-law checks, and substrate reactions later (recommended, §3.3)?
4. **The intermembrane space.** A finite node for the isolated organelle, merged with the cytosol in
   the first in-cell world, and pools later (recommended, §3.4)?
5. **The cell type.** Isolated cardiac mitochondria first, then a cardiac cell beside the human
   cardiac lane (recommended, §3.5)?
6. **The D138 question, for Beard 2005 with its 2006 correction only (§5.3).** Do you approve:
   - **(A)** an independent whole-organelle reference of the model, written from the paper and its
     correction by an agent who never reads the engine or any model file, run out of process, in two
     arms: as published, and with §5.4's listed departures (any later departure reported to you
     before the judged run)?
     - Its first task is to confirm that the equations and the corrected table, published as images,
       are legible in the open PDF. If they are not, it stops and reports.
   - **(B)** running the published model itself, unmodified and out of process, keeping only saved
     outputs?
     - The file: the Physiome Model Repository's curated CellML encoding (CC BY 3.0), "edited to
       correct dimensional errors".
     - Unknown: whether it carries the 2006 correction.
     - The tool: libOpenCOR (Apache 2.0) in its own environment, the file used by reference and never
       committed.
     - The authors' own code is available only on request, and we contact no one.
   - **(C)** comparing the Cells organelle over the source's steady-state protocols and its
     low-oxygen sweep, as §5.3 lists them?
     - judged against the declared arm, at tolerances registered before the run;
     - the two references judged against each other;
     - the Cells organelle against the published model reported, not judged, with each difference
       attributed to a declared change.

   **How to answer:**
   - yes to all three;
   - yes to (A) and (C) without (B): the comparison then rests on R1 alone;
   - or no: the lane stops at the component references and Cells' own organelle (§5.1–5.2), which
     need no approval.

   The measured data the source was fitted to (Bose et al. 2003) are not part of this approval. They
   come as a later question, once they can be read.

### 9.2 For the lead (with the core owner and the cardiac lane)

These overlap the cardiac note's open questions (its §9.2), so one ruling could serve both lanes.
1. **The fuel representation at nodes with dynamic protons:** charged base-form rows under a binding
   closure (recommended, §1.3), keeping transformed rows with their band where a world declares
   them?
2. **The cycle kind** (§1.4): a new kind with roles at both ends, several populations per patch, an
   N/P orientation and integer stoichiometries beyond 4?
   - It joins the cardiac lane's question 9 (several roles, no fuel, two populations).
   - Who owns it, and is FR-4's transporter kind kept as it is (recommended)?
3. **The binding closure:** B4 generalised to several ligands (H⁺, Mg²⁺ and the cardiac lane's
   Ca²⁺), or sibling kinds (the cardiac lane's question 8)?
4. **The cycle heat booking:** the cardiac lane's question 13, extended to cycles (§2.3)?
5. **Probe P1 before M1,** with its criterion written first, and the implicit cycle block (a new IMEX
   ID) only if P1 asks for it?
6. **Host P for the isolated organelle** (§3.6, item 1).
   - Is the face's reuse for porin permeation acceptable under ARCHITECTURE.md's reuse rule (§3.4)?
7. **Refusal 4 version 1.3** for the new kind, and refusal 5 version 1.1's landing from `fr45-next`?
8. **Pools at the cell's potential** for a resolved IMS and ER contacts later: the same ruling as the
   cardiac lane's question 6, including subspace calcium's closure in the inner-model note's §13.1.
9. **The species cap** for host C in a cell (§2.2).
10. **The viewer's status mismatch** (§8): established in the older family, against the brief's
    "planned".
11. **Fresh agents** for the component references, R1 and R2. This note's author has read the engine.

## Sources

**How they were read.**
- **This note's author** fetched the Beard articles, Europe PMC's records and the publishers' pages
  below.
- **Two research subagents,** briefed with the lead's guard rule and one attempt per source, read
  the model files' and tools' licence pages, and the biological sources.
- **Searches used titles, authors and scientific terms only.** Nothing was fetched behind a login,
  and no one was contacted.
- **Each paper with every host tried:**
  - **Beard 2005,** PLoS Comput Biol 1(4):e36:
    - the PLOS article page [full], read three times for different facts;
    - equations and Table 1 are images there.
  - **Beard 2006 correction,** PLoS Comput Biol 2(1):e8:
    - the PLOS page [full]: "Table 1 included incorrect values";
    - the corrected table is an image, and its values were not read.
  - **Wu et al. 2007,** J Biol Chem 282:24525. Two hosts:
    - Europe PMC's search record [abs; licence field "cc by"; not in PMC];
    - then its DOI, whose one redirect led to a publisher page with only the word "Redirecting".
  - **Cortassa et al. 2003,** Biophys J 84:2734. Two Europe PMC calls:
    - its search record [abs; PMC1201507; no licence field];
    - then its full-text XML service, which answered HTTP 500. It was not tried again.
  - **Magnus and Keizer 1997,** Am J Physiol 273:C717, **and 1998,** 274:C1158 and C1174:
    - Europe PMC's search records [abs];
    - the 1997 paper's APS page refused (HTTP 403).
  - **Bertram et al. 2006,** J Theor Biol 243:575: Europe PMC's record [abs]. Not in PMC.
  - **Vinnakota et al. 2016** and **Bazil et al. 2016,** Biophys J 110:972 and 962: Europe PMC's
    records [abs]. In PMC, no licence field.
  - **Stock, Leslie and Walker 1999,** Science 286:1700: the RCSB PDB entry 1QO1, which reprints the
    abstract [abs] (the biology subagent).
  - **The licence subagent's pages:**
    - the CellML exposures and metadata pages;
    - BioModels records through the OmicsDI mirror (BioModels' terms page answered 403);
    - the tools' licence files on GitHub;
    - the Beard 2005 article page for its data sources and its code statement [full].
    - JBC pages for Bose et al. 2003 refused (403) or redirected. They were not read.

**Refused, and not used** (the biology subagent, one attempt each):
- PMC's browser check for Watt et al. 2010 (PMC2947889), Jiang et al. 2001 (PMC33147) and a 2014
  rotor structure (PMC3971453);
- PubMed's cookie wall and PNAS (HTTP 403) for Watt et al. 2010;
- ASM journals (HTTP 403) for Calhoun et al. 1993;
- eLife's page needing JavaScript, for Breuer et al. 2019;
- **nature.com, for Seelert et al. 2000:**
  - the article page redirected to Nature's identity provider and back with a cookie error;
  - the subagent followed two redirect hops, one more than the one-attempt rule allows;
  - the permission classifier then denied the third fetch as "[Unauthorized Access]".
  - The subagent stopped and reported, no workaround was tried, and it was not resumed.
  - Nothing from that page, or from any copy of it, is used here.

**Models and their corrections:**
- Beard D. A. (2005). A biophysical model of the mitochondrial respiratory system and oxidative
  phosphorylation. PLoS Comput Biol 1:e36. Correction: PLoS Comput Biol 2:e8 (2006).
- Wu F., Yang F., Vinnakota K. C., Beard D. A. (2007). Computer modeling of mitochondrial
  tricarboxylic acid cycle, oxidative phosphorylation, metabolite transport, and electrophysiology.
  J Biol Chem 282:24525–24537 [abs].
- Cortassa S., Aon M. A., Marbán E., Winslow R. L., O'Rourke B. (2003). An integrated model of
  cardiac mitochondrial energy metabolism and calcium dynamics. Biophys J 84:2734–2755 [abs].
- Magnus G., Keizer J. (1997). Minimal model of β-cell mitochondrial Ca²⁺ handling. Am J Physiol
  273:C717–C733 [abs]; (1998) parts I and II, 274:C1158–C1173 and C1174–C1184 [abs].
- Bertram R., Pedersen M. G., Luciani D. S., Sherman A. (2006). A simplified model for mitochondrial
  ATP production. J Theor Biol 243:575–586 [abs].
- Vinnakota K. C., Bazil J. N., Van den Bergh F., Wiseman R. W., Beard D. A. (2016). Biophys J
  110:972–980 [abs]. Bazil J. N., Beard D. A., Vinnakota K. C. (2016). Biophys J 110:962–971 [abs].

**Cited through the sources above, not read here:**
- Bose et al. 2003 (J Biol Chem 278:39155), Wilson et al. 1988, Gnaiger 2001 and Gnaiger and
  Kuznetsov 2002, Beard 2005's data;
- Korzeniewski and Zoladz, its exchange form;
- the Syn3A reconstruction (Breuer et al. 2019), through the viewer's records.

**Internal:**
- PAPER_REVIEW_MITOCHONDRIA.md, FINITE_ENERGY_POOLS.md, CLOSED_COMPARTMENT_DESIGN.md (and §3.4.2–
  3.4.3 on `fr45-next`), COMPARTMENT_PH_TRANSFER_DESIGN.md, FEATURE_REQUESTS.md (FR-1, FR-4, FR-5);
- INNER_MODEL_V4_DESIGN.md (§7.4, §9.2, §10, §13; §7.4 (l)–(n) on `core-next`),
  SHARED_INVENTORY_REACTIONS_DESIGN.md, SYN3A_MINIMAL_CELL_TRACK.md, ARCHITECTURE.md;
- `docs/HUMAN_CARDIAC_LAWS_DESIGN.md` on `cardiac-laws`;
- DECISIONS.md: D138, D142, D144, D151, D167, D173, D178, D180, and D184–D186 on main;
- AGENTS.md, with D185's module provenance line on main.
