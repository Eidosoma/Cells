# Mitochondria: design (proposed)

> **Legacy cleanup (25 November 2026, D386).** Paths under `src/cells/legacy/` and the older model
> IDs named below left the engine. The tag `pre-cleanup-2026-11-25` keeps them.

**Status: DECIDED, 16 November 2026: the options of §3 and the questions of §9.1 (D193).** Built
in step 4 of D194's order. Beard 2005's legibility, since checked, is under the screen items. Proposed
the same day; design only, no engine code. Written on branch
`mito-design` from 3c10b833, integration-d172's landing candidate. The note reaches main after
D172's landing. It gives the user options with recommendations, and asks the D138 question (§9.1).

**Addendum, 17 November 2026 (D210):** individual mitochondria, static and dynamic, with options, in
the section after the sources.

**21 November 2026:** the synthase stall check's rule, registered before its data are read (D269),
and MT-1b's registration as a draft, not registered, in the last two sections.

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
     - Probe P0 found the base parses and binds this topology, with no kinds declared. Nothing was
       stepped.
     - Host P is the lead's call. Its fallback is host C with two respiration cycles (§1.1).
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
     1997 Magnus–Keizer paper's page was refused (403); the 1998 pages were not tried.
7. **The other options:**
   - **Detail:** one effective mitochondrion per cell first;
   - **Respiration drive:** the source's driven NADH supply (booked work) for the organelle, held
     NADH and NAD⁺ for single-law checks, and substrate reactions later;
   - **The IMS:** a finite node for the isolated organelle (host P, the lead's call), merged with
     the cytosol for the first in-cell world, a pool at the cell's potential later;
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
  - Beard 2005 defines ΔΨ as "the outer potential minus the inner potential" [full]. That is
    positive at the operating point, since the matrix is the negative side (**S**; the text read
    gives no value).
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
- **Unlike the SR, the matrix cannot be a pool at the cell's potential.**
  - The cardiac note's pools give the SR and the subspace the cell's potential, since its source
    models give them none of their own (its §3.2).
  - The matrix's own membrane potential, ΔΨ, is the point here. So the matrix must be a capacitor
    node (host C) or a cell (host P).
  - Only the IMS, which has no potential of its own, could be such a pool (§3.4).
- **Host P is the lead's call, not settled** (§3.6, item 1). Wherever this note assumes it, the
  fallback is host C:
  - a large owner cell standing for the medium;
  - the IMS merged into it;
  - respiration as two cycles, NADH:Q and QH₂:O₂ (§3.2).

  On host C, cytochrome c's redox state cannot be observed.

### 1.2 The pieces, one by one

"Exists" means on the base at 3c10b833. Names marked **S** are proposals, not rulings.

| Piece | Physics | In Cells today | Proposed | Name (S) |
| --- | --- | --- | --- | --- |
| Matrix | The N-side pool, with its own rows | Host C: an FR-1 node; its role "mitochondrion" is metadata only (`operators/compartments.py`: "No physics depends on the role"). Host P: a @3 cell | Exists | — |
| IMS | The P-side pool between the membranes | Host C: none, merged with the cytosol. Host P: a finite outside node | A pool at the cell's potential later (the cardiac note's §3.2 (a), unruled) | — |
| Inner membrane capacitor | Its own capacitor and voltage, ΔΨ | FR-1's patch capacitance, V_b = −q/C_b exact at a face-free node (FR-1 §3.1); host P's patches | Exists (§2.1) | — |
| Outer membrane | Porin permeation for small solutes, no voltage | Host P: a face (`logmean_electrodiffusion@1`, passive, heat) | Its reuse for porin permeation is checked against ARCHITECTURE.md's reuse rule (§3.4) | — |
| Proton-motive force | Δp = ΔΨ + (RT ln 10/F)·(pH_N − pH_P), with ΔΨ = φ_P − φ_N: the free energy per proton moved from N to P, over F. Both terms are positive when the matrix is negative and alkaline (**S**). From the field and each side's closure | The voltage and free h exist; Δp is no readout | A readout of the cycle kind | — |
| Respiration | A redox-driven proton-pumping cycle per complex. The source's counts, as the fetch tool reported them: complex I pumps four protons per electron pair, complex III four, and complex IV moves two protons across the membrane with four charges in all [full] | None. The transporter kind's laws hydrolyse one ATP and move one role, n = 1–4 (`inner_kinds/transporter.py`: `STOICHIOMETRY_RANGE`) | New laws of one cycle kind, each complex a population with declared roles (§1.4) | `cells.membrane_cycles@1`; law `redox_driven_proton_cycle@1` |
| ATP synthesis | A reversible cycle coupling c H⁺ (P→N) to 3 ATP, or n_A ≈ 3 per ATP in the source [full] | FR-4's `proton_atp_mass_action_positive@1` reverses past its static head (FR-4/FR-5 note §6) | An extension: rational ratio, saturation on both sides, fuel at the N side, charged rows (§1.4) | `proton_coupled_atp_synthesis_cycle@1` |
| Nucleotide exchange | Electrogenic antiport: ATP⁴⁻ out of N, ADP³⁻ in; "involves the displacement of one negative charge from the matrix to the IM space" [full] | None | A cycle with two roles in opposite directions, no fuel (the cardiac exchanger's sibling) | `electrogenic_nucleotide_exchange@1` |
| Phosphate carrier | Electroneutral H₂PO₄⁻/H⁺ symport, one proton per phosphate [full] | None | A cycle with two roles in one direction | `phosphate_proton_symport@1` |
| K⁺/H⁺ exchange | Electroneutral antiport. The source keeps matrix pH "nearly constant" with it [full] | None | A cycle with two roles | `potassium_proton_exchange@1` |
| Proton leak | Constant-field H⁺ route [full: Nernst–Goldman] | `proton_constant_field_leak@1` (FR-4; `laws/transport/proton_leak.py`), in `cells.passive_routes@1` | Exists | — |
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
- **Checked later the same day, by an independent agent:** both are legible from PLOS's open XML
  (the article, e36, and the 2006 correction, e8).
  - The 25 display equations carry their MathML inside XML comments. 15 are well-formed, and all
    are readable once the tags are stripped.
  - Table 1's 35 parameters are text in a comment. The correction changes 9 of them.
  - The comment text was not checked against the typeset images. One apparent slip, an ATP label
    on the ADP flux in e013, is to be checked against the image.
  - Evidence: `/mnt/workspaces/Cells/verify-gard-beard-20261116/` (`beard_table1.json`).
1. **The complexes and the synthesis flux** are described as mass action driven toward equilibrium,
   with each complex's standard energy in its driving force, and F1F0 by "the thermodynamically
   balanced expression" [full].
   - If they are J = X(K′·Π[substrates] − Π[products]), they are this form with S equal to the
     forward term (**S**).
   - The reference confirms it on the printed equations.
2. **The nucleotide exchange is an "empirical expression"** after Korzeniewski and Zoladz [full].
   - In its common form the flux is a difference of two saturating terms, each with a share of
     FΔΨ/RT in an exponent.
   - Its zero is the exchange's equilibrium only if the two shares sum to one (**S**, a reading of
     the common form).
   - The screen checks its sign against −ΔG on a grid. A form that fails is refused, never repaired.
3. **The phosphate carrier,** a reversible Michaelis–Menten flux [full], passes if its numerator is
   the mass-action difference.
4. **The NADH supply** is "an arbitrary four-parameter function" outside the thermodynamic framework
   [full].
   - Cells runs it as a driven route that books its ΔG as signed work, as D150's exchange does
     (D174).
   - That is a declared supply, not a fuel.
5. **Mg²⁺ binding is kinetic in the source,** with a forward rate X_MgA [full]. The closure is its
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
  - The charges per complex are 4, 2 and 4: complex III's four include two taken up on the N side,
    and complex IV moves four charges in all [full; the split **S**].
  - Either way, ten is beyond the kind's 1–4.
- The synthesis cycle's c/3 need not be an integer (§4).
- Integer roles per rotation (c H⁺ and 3 ATP) keep the cycle exact.

### 1.5 The review's accounting requirements, mapped

The mitochondria review (PAPER_REVIEW_MITOCHONDRIA.md) sets three requirements.
- **One capacitor per membrane, each voltage from its own charge.**
  - The inner membrane is the bounding patch (host C) or the cell's patches (host P). Its voltage
    comes from the field (§1.1, §2.1). The outer membrane has none (§1.1).
- **Distinct inventories, each exchange counted once on each side.**
  - Matrix, IMS, cytosol and, later, ER rows are @3 node columns. Every cycle moves its roles
    between its two ends in one booking, with the stage's charge from the valences (§1.3, §1.4).
- **Standard states.**
  - Every potential comes from the registry at its one standard concentration c0. The source's
    standard energies are at 1 M [full: its kJ/mol values], and enter with the registry's own
    conversion, ΔG° = RT (Σ ν μ°/RT + (Σ ν) ln(1000 mM/c0)) (`registry/species_registry.py`).
  - FR-4's closure term keeps @3's 1 mM convention for stored rows (FR-4/FR-5 note §4.4).
  - No law carries its own ΔG°. A world whose source disagrees with the registry is refused, as
    INNER_MODEL_V4_DESIGN §10.2 rules for pumps (§5.4, C2).

## 2. The key engine question: can a cell-owned compartment carry its own voltage?

**Yes, in the field, today.** The two halves below separate admission from numerics.

### 2.1 Admission: what FR-1 allows (host C)

**Holds today** (code read, base, unless named):
- **The capacitor.** At a face-free compartment node with one patch, V_b = −q_j/C_b exactly, and the
  owner's plasma membrane sees q_cell + q_comp (FR-1 §3.1, a reading of `numerics/surface_field`).
  - The older family uses the same relation for its own mitochondrial capacitor
    (`models/surface_calcium_energy_mitochondria.mitochondrial_voltage`). That family is
    `resolved_calcium_energy_mitochondria@1`: passive constant-field transport
    (`legacy/processes/mitochondrial_passive.py`, which "adds neither respiration nor ATP production"),
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
  - **Amended 25 November 2026** (CALCIUM_STORE_AND_CHANNELS_DESIGN §8.3): both hold one row per patch
    that faces such a node, in place of the node's sum, and the per-stage rule holds it with kinds
    or without. At the matrix node one patch faces it, so the row is the same. A cell's row divides
    by its other patches' capacitance alone.
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
    refusal 4 keeps channels off a bounding patch. So a matrix potential of the size of FR-4's
    static head is admissible there: −0.266 V, **S** in that note. The text read here gives no ΔΨ
    value for the source.
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
- `laws/routes/patch_electrodiffusion.py` (`bounding_patch_constant_field@1`) holds the Newton stage
  solve for constant-field routes only.
- It has no caller in `src/cells` at the base, on `core-next` or on `fr45-next` (a search).
- A local implicit block for a compartment's cycles would be new, a new IMEX ID under D147, and its
  Jacobian would not stay diagonal-plus-rank-one:
  - the cycles couple rows;
  - the closure sits inside it.
- **Branch I is host-specific (S).**
  - The designed Newton form is admitted only on a face-free node with exactly one bounding patch
    (INNER_MODEL_V4_DESIGN §7.4 (g) 4). Its self-containment rests on V_b = −q_j/C_b there.
  - On host P the N side is a cell whose patches face a faced node. Its charge mode reaches the
    global field solve, so a local block does not carry over.
  - Host P would need the implicit route inside the global operator, that note's fallback form:
    another solver ID, unbuilt.

**The first engine step is a measurement, its criterion written before it runs.** Probe P1 has two
arms, one per host, since its result must match the host of M4:
- **Host C:** one cycle on a bounding patch.
- **Host P:** the same cycle on a cell's plasma patch facing a faced finite node.
- **The cycle:** FR-4's proton law, the nearest existing cycle, run past its static head at large
  capacity, with n = 4.
- **The ladder:** dt × ΣG/C from 0.01 to 2.
- **What it records:** where the per-stage rule refuses, where the energy ledger refuses, and the
  state's error against an independent two-capacitor reference.

Its result picks the effort branch of §8, for the host the lead chooses:
- **E:** explicit steps at a declared dt × ΣG/C suffice for the first protocols;
- **I:** an implicit cycle block is needed.

**Probe P0, already run** (host-side parse only; record and script in the evidence folder).
- **The world:** at the base, `parse_spec` admits a @3 definition with:
  - a cell standing for the matrix, with three patches to one finite node (the IMS);
  - a face from that node to a held bath, its diffusivity zero for two rows;
  - rows of valence +2, −1, −2, −3 and −4;
  - a start charged at C × (−0.18 V), the probe's own chosen input;
  - no kinds declared. Whether the existing kinds parse on such a plasma patch was not checked.
- **The result:** `get_model` binds it with finite initial values.
- **The limit:** nothing was stepped, so it shows no stability, accounting or field consistency.

## 3. Options for the user

### 3.1 The source of equations and parameters

Read on 16 November (Sources).
- "Free" means readable in PMC without a licence statement.
- Whether D186's "open papers" covers such papers, which the index does not mark open access, is the
  lead's reading (§9.2). This note does not assume it.

| | **Beard 2005 + 2006 correction** | Wu et al. 2007 | Cortassa et al. 2003 | Magnus–Keizer 1997/98; Bertram et al. 2006 | Vinnakota et al. 2016; Bazil et al. 2016 | A reduced Cells model |
| --- | --- | --- | --- | --- | --- | --- |
| Covers | Respiratory complexes, synthesis, nucleotide and phosphate transport, K⁺/H⁺ exchange, leak; Mg²⁺ and H⁺ binding; no Ca²⁺ or Na⁺, no TCA cycle [full] | Adds the TCA cycle, metabolite transport and electrophysiology; isolated cardiac mitochondria and skeletal muscle in vivo [abs] | TCA cycle, oxidative phosphorylation and Ca²⁺ handling; "twelve ordinary differential equations" [abs] | β-cell mitochondrial Ca²⁺ handling; six inner-membrane mechanisms [abs]; a reduction of it [abs] | Beard's successors: phosphate regulation, ROS [abs] | The same law set, fitted to nothing, verified on its own |
| Open and licence | CC BY, both [full] | Licence "cc by" in Europe PMC's record; the full text not reached (the publisher served a redirect page) | Free in PMC (PMC1201507), no licence stated; the full text not read (Europe PMC's XML: HTTP 500) | Not in PMC; the APS page refused (HTTP 403). Bertram 2006: Elsevier, not in PMC | Free in PMC (PMC4776028, PMC4776027), no licence stated; abstracts only | — |
| An IMS of its own | Yes: cytochrome c and adenylate kinase there; the IMS "1/10 of the mitochondrial water volume" [full] | Not read | Not read | Not read | Not read | Declared |
| States | 17 [full] | Not read | 12 [abs] | Not read | Not read | 9–16 rows |
| The screen (§1.4) | Mass action toward equilibrium, except the NADH supply (driven) and the empirical exchange (items 1–5) | Thermodynamically balanced reactions, in the fetch tool's summary of the abstract [abs] | Not read; its formulas need the screen | Not read | Not read | By construction |
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
    [full: p_A and p_Pi].
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
   - **Branch I is host-specific** (§2.3). A local implicit block fits host C only; host P would need
     the global form.
   - Recommended: host P, with host C at M6. Host C with two respiration cycles is the fallback
     (§1.1), and P1's arm for the chosen host sets the branch.
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
  - **The fallback,** if the lead rules for host C: a large owner cell standing for the medium, the
    IMS merged, two respiration cycles (§1.1).
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
  - **On host C,** the fallback, the IMS merge and two-cycle respiration become departures (§5.4),
    and the cytochrome c curve drops from the comparison.
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
  - The fallback is host C with a large owner cell standing for the medium, the IMS merged and two
    respiration cycles (§1.1). The steps below are the same on either host.
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
| M4: Cells' own organelle | `resolved_pump_composite@1` over @3, host P (fallback host C, §1.1) | §7's protocol, registered and judged (§5.2) | 3–5, plus CPU |
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
   - The finite node needs host P, which is the lead's call (§3.6).
   - If the lead rules for host C, the isolated organelle also merges its IMS, and its respiration
     takes two cycles.
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
     - If the lead rules for host C, the cytochrome c curve drops, and the merged IMS and two-cycle
       respiration join the declared departures.
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
12. **D167's staged move for the older family.** `resolved_calcium_energy_mitochondria@1`'s passive
    mitochondrial law (`legacy/processes/mitochondrial_passive.py`) has no energetics. Once the cycle kind
    covers its passive ion transport, is it frozen as a reference with a parity check (its
    constant-field law against the passive routes on host C), or without one?
13. **D186's reach.** Does "numbers from open papers" cover papers free to read in PMC with no
    licence stated, which Europe PMC does not mark open access? Examples are Cortassa 2003 and
    Vinnakota and Bazil 2016. This note uses none of their parameter values until the lead says so.
    It cites only facts from their abstract records.

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

**Correction (17 November 2026, the independent check; `docs/CORE_SEAMS_STEP0.md` §7).** Beard
2005's PDF is the version of record. PLOS's web XML and its MathML carry a stale Eq. 22 (the matrix
proton balance), so anything transcribed from the XML must be checked against the PDF.
- Table 1's corrected values are already in the PDF.
- As printed, Eqs. 11, 16 and 24 do not factor in seam A's form. They enter only with declared
  departures.

## Individual mitochondria (addendum, 17 November 2026)

**Status: proposed, read-only, with options (D210).** Branch `mito-individuals` from main 7538b0cd;
nothing was built or run. Code is cited `file`:line there, under `src/cells/` unless another root is
named (`records/relations.py` equals `relations-writer` 35a5bbb9); `gard-g1-merge` c6dd5956 is cited
for its commit message. **S** marks this addendum's own reading, arithmetic or proposal. **Engine
models: none;** A.2's check would run `resolved_pump_composite@1` over `resolved_pump_tissue@3`,
with `cell_owned_compartments@1` and FR-4's three kinds.

**The request (D210).** The user: "different researdh would need different levels of detail so you
could choose the setup"; on individual mitochondria with fission and fusion, "yes sooner rather than
later". Sooner means this design now, with its dependencies pulled forward. D193's first step
stands: the lumped node of §3.2 is the reference that N identical individuals must reduce to.

**The floor.**
- **No mitochondrion runs in the modular engine yet.**
- **The synthesis law waits for the user's ruling on a departure.** Beard's printed F1F0 law
  (Eq. 11) fails the step-0 screen: its exponent omits the matrix proton its own reaction consumes
  (`docs/CORE_SEAMS_STEP0.md` §1.4, §7; `docs/MOLECULAR_MACHINES_DESIGN.md` §10.1; D209).
- **P1 found a step cap where a route draws protons from a buffered outside node,** as a matrix is:
  3.37 µs in its world, for seam C to fix (CORE_SEAMS_STEP0 §8).
- **So everything below is about hosts and events,** never a mitochondrial law.

**In short.** Static individuals are admitted as compartments today, as mitochondria with host C's
refusal 4, and their check needs no engine code (A). Dynamic ones need new doors, draws, geometry as
state and `cells.relations@2` (B); inexact levels need D175's fields (C). Recommended: requirements
now, the check soon, the doors after the core-seams pass, and M8 before M7 (E).

### A. Static individuals: N mitochondria per cell, no events

**A.1 What `cell_owned_compartments@1` admits today** (code read, not run).
- **N compartments per owner: admitted.** Refusal 3 reads "one compartment per node (an owner may
  own several)" (`operators/compartments.py`:16, :332–335). Each needs its own node and its
  own bounding patch (refusal 2, :296–305). Nothing counts compartments per owner.
- **Shown by a parse only.** `tests/unit/test_cell_owned_compartments.py`:196–232 parses two
  compartments in one cell. A search of `validation/` and `tests/` found no stepped world with two
  in one owner; FR-4's and FR-5's declare one (`validation/compartment_ph_engine/definitions.py`,
  :161–164).
- **N mitochondria: refused until the cycle kind is admitted.** Refusal 4 refuses any kind "which
  refusal 4 does not know: a kind's routes may cross its bounding patch" (`compartments.py`:73–81,
  :222–229). Lifting that is §2.1's item 1 for host C (CORE_SEAMS §4.4). So static individuals need
  no door that one mitochondrion in a cell does not already need (**S**). Version 1's other refusals
  hold for each member (FR-1 §1.4).

**A.2 The free check: N identical compartments against the lumped node of N members.**
- **The claim.** FR-1 §1.3 states that one node of N identical members, with N × volume, area,
  capacitance and capacities, is exact. No run has tested it, yet FR-4's world rests on it: its
  "lumped population" holds 1,000 members (`validation/compartment_ph_engine/definitions.py`:163;
  `.../parameters.py`:1–6, :55, :83–96). The check tests the host's reduction, not a mitochondrial
  law; it carries over once the cycle kind declares its fields' roles.
- **The worlds,** from one frozen snapshot, at one dt. **L:** FR-4's world, N members in one node
  (`definitions.py`:117). **I_N:** the same owner with N one-member compartments, each with its
  patch, pump population, leak route and buffer. N of 2, 8 and 64 divide exactly; 3 and 7 form a
  rounding arm. A neutral arm on FR-1's world W (`validation/tissue/compartment_fixtures.py`) runs
  exchange and turnover.
- **The scaling map** is the check's input, and a parameter missing from it is refused. It is a
  requirement on seam B's field roles, which also split populations at division (CORE_SEAMS §4.2).

| Divided by N (extensive) | Unchanged (intensive) |
| --- | --- |
| Volume; patch area and capacitance; every row's amount, buffers included; fixed charge and charge anchor; the transporter's `capacity_fmol_s` (`kinds/transporter.py`:24 says so); exchange's flux J and first-order export k_e, per route on the cell's pool | Permeabilities (m/s; `inner_kinds/passive_routes.py`:150); exchange's uptake velocity, V_max per area and K_M (`operators/species_exchange.py`:13–20); the transporter's n, K and K_ATP; the buffer's constants; turnover's clearance k (`operators/species_turnover.py`:12); specific capacitance |

- **At definition time** (host only): the members' extensive anchors sum (`math.fsum`) to the lumped
  ones, bitwise when N is a power of two; intensive values match bitwise. Each member's
  definition-time rates (B7's face-free term, the transporter's bound) match to rounding, since they
  rest on ratios such as G/C that N leaves unchanged (**S**). Both worlds pass @3's checks.
- **At run time,** on every saved row: N × each member's amounts and cycle rate, and each member's
  V_b and pH, against the lumped node's; the owner's rows and potential against L's; the ledgers.
- **The spread among members,** (max − min)/scale per field, is recorded. Identical members should
  stay identical to rounding; the solve's elimination order can part them in the last bit (S5 §3.2).
  If the spread grows, the symmetric state is unstable. That is a finding about the reduction, not a
  numerical failure: the lumped node is then the wrong reference for that world (**S**).
- **Tolerances** are fixed in the protocol before any run, from two sources only: the field solve's
  declared 2e-12 for charge and current (`numerics/surface_field.py`:43, :45), and a rounding budget
  in ulps of each quantity's scale, as S5 judges its event map (its §7.4: 64 ε × magnitude). Never
  from the engine's spread.
- **Controls that must be caught:** one member's pump capacity raised by 1e-6 relative; members at
  0.5 and 1.5 times the capacity against the lumped mean (D175's case outside the envelope); an
  intensive parameter divided by N.
- **A known limit.** FR-4's protocol leaves its single-compartment form unjudged until energy floors
  scale with species (`validation/compartment_ph/protocols/fr4_acidification_v1.json`:37, :134).
  I_N's small members meet the same floors, so they stay large enough, or the check waits.
- **Cost (S):** 1–1.5 agent-days for a builder variant and a protocol in `validation/`, no `src/`
  change. FR-4's 900 s at 1 ms is 900,000 steps (`parameters.py`:71, :75), so most arms take a short
  horizon and a full-length arm runs detached, off CPUs 6, 7, 22 and 23 (D207).

**A.3 The field solve's node cap.**
- **Compartment nodes count.** A compartment is an outside node (FR-1 §1.1). Parsing refuses more
  cells and outside nodes than the bound, and padded capacities above it
  (`definitions/surface_tissue_spec.py`:190–191, :318–319). The pump family parses with field solver 2 or 3
  (`definitions/surface_pump_spec.py`:175–178), whose bound is 2,048 (`numerics/surface_field.py`:65–71);
  `bind` checks again (:132–138).
- **Mitochondria per cell (S).** K cells of N compartments, with B other outside nodes, need
  K(1 + N) + B ≤ 2,048, so N ≤ ⌊(2,048 − B)/K⌋ − 1: 2,046 for one cell in one bath, 126 for 16
  cells, and 14 for FR-1 §3.6's 127-cell sheet with its 127 outside nodes.
- **A field-input provider lowers the cap to 64** (`models/pump_composite_adapter.py`:102, :122–126,
  :553–563; `models/pump_composite.py`:1190–1192). Every event door of B is one (B.2), so one cell
  in one bath could hold 62 compartment slots, pending ones included.
- **Cost (S).** The dense solve takes 1.7 ms per step on one core at 14 nodes, 7.7 ms at 254 and
  76 ms at 825 (FR-1 §3.6). Grown as n² to n³, 2,048 nodes take 0.47–1.2 s per step: one cell with
  2,000 mitochondria for 100 s at 1 ms is 13–32 CPU-hours.
- **So FR-17 gains a second consumer on paper, but condensation fits compartments better** (FR-1
  §3.6, §8). A face-free node with one patch is a leaf of the capacitor graph, so eliminating it is
  exact: its potential is φ_owner + q_comp/C_b, and the owner's plasma row keeps q_cell + Σ q_comp
  (**S**, from FR-1 §3.1). The dense solve then holds cells and other outside nodes only; each
  member costs O(1); and a door that changes a compartment's capacitance or mask need not
  refactorise it, the 64-node cap's reason (**S**). It is a new solver ID (D147), with its own
  references. FR-17's entry says only the 3D table needs it; that goes to the lead.

### B. Dynamic individuals: fission, fusion, removal and inheritance

Here the set of compartments changes during a run. FR-1's doors (§1.5, §8) were written for pools.

**B.1 What each event needs beyond FR-1 §8.**

| Event | Nearest door | What it needs beyond it |
| --- | --- | --- |
| Fission | F: "a transfer between a compartment and another node across a fusion pore", for exocytosis and endosome maturation (FR-1 §1.5) | **A split door:** a pending slot, closed until the event, as S5's daughters are (S5 §3.2); anchors as exact fractions, f for amounts, volume, fixed charge and charge anchor, and a for area, capacitance and populations. With a = f both daughters keep V_b, and the capacitor energy splits exactly: (fq)²/2fC + ((1 − f)q)²/2(1 − f)C = q²/2C (**S**). With a ≠ f, S5's mismatch rule applies (its §3.3). Populations split by seam B's roles: extensive by the fraction, intensive copied, history from zero (CORE_SEAMS §4.2) |
| Fusion | F, as above | **A merge door, split's inverse.** Seam B has close, split, retire and open, but no merge. Its rules (**S**): extensive fields summed; history moved to a record; structural fields equal, or refused; intensive fields weighted by a declared extensive field (a gate fraction by capacity), or refused. **Its bookings (S):** unequal voltages lose capacitor energy C₁C₂(V₁ − V₂)²/2(C₁ + C₂), and unequal contents lose mixing free energy, both as heat. The review asks for this accounting (PAPER_REVIEW_MITOCHONDRIA) |
| Removal (mitophagy) | X: compartments retire only with their owner (FR-1 §1.5) | **A removal door in a living owner:** node, patch and populations closed; content to a declared sink or to the owner's cytosol, with its free-energy change booked. The owner's plasma membrane sees q_cell + q_comp (FR-1 §3.1), so the door moves the charge to the owner with declared ions, or refuses a node with \|V_b\| above a declared bound. The second matches the biology, where depolarisation comes first (D). History goes to a record (S5 §3.5) |
| Inheritance at division | D: declared fractions, 0 or 1 for an organelle; stochastic partition of discrete organelles out of scope (FR-1 §1.5; §3.2 here) | Door D itself, which puts compartments into the entity hierarchy; then stochastic partition (B.3) |

**B.2 What the events share (S).**
- **The 64-node cap.** Opening or closing a slot changes `outside_active` and `membrane_active`, and
  a split changes `membrane_capacitance`: all field inputs (`pump_composite_adapter.py`:102).
  Without condensation, a world with events holds at most 64 field nodes.
- **Slots run out.** S5 reuses none: 1 → 2^k cells need 2^(k+1) − 1 slots (S5 §6.2). Repeated
  fission and fusion need slot reuse with re-anchoring, a decision against D057 (S5 §6.3).
- **Geometry as state.** Prescribed events can declare anchors in advance; fusion of partners found
  at run time cannot. Volume, area and charge anchor then become state: door V (FR-1 §5.3), and area
  as population state, which meets the membrane-state wall (FR-1 §4). Growth needs the same.
- **Timing in three steps:** prescribed on the dt grid, as operator events are today
  (`pump_composite.py`:1178–1184); state-triggered, by a threshold; stochastic. Only the last draws.

**B.3 Stochastic partition, and GARD's rules.**
- **The fixed-step world refuses random state in a checkpoint:** "These deterministic models have no
  random state" (`io.py`:158–159; None is written at :116, "unused" at :313).
- **The refusal can stand (S).** Keyed counter-based streams hold no state to save: in GARD's
  family "an assembly's draws depend on its identity alone" (`assembly_lineages/streams.py`:22).
  The composite needs a stream identity, a carrier key per slot (S5 §6.1 defers it) and draws keyed
  by event and compartment, as the machines note plans for tags (its §10.4).
- **GARD's two rules are the two needed** (`models/assembly_lineages/fission.py`:8–13, :31,
  :101–122): `exact_fraction` gives floor(f N) to the first daughter as a uniformly random subset,
  and `binomial` sends each to it with probability p. Read "molecules" as "compartments".
- **They live in another family,** with its own counts, interfaces, runner, kernel and keys. **Reuse
  is a question for the lead and GARD's owner.** It would take (S): the rule, a pure function of
  counts and uniforms, moved to a shared module under a neutral name, GARD kept bitwise; the RNG
  contract in the composite (MODULE_SYSTEM_DESIGN §5); door D calling it, with a replay reference
  like GARD's (`assembly_lineages/reference.py`:46). It waits for GARD's G1 (D207, amended).

**B.4 `cells.relations@2`: mitochondria's requirements,** which D209's L1 collects with machines'
and GARD's. Against `records/relations.py`:
1. **Two parents.** A life has one `parent` (:199), present exactly when born by division
   (:675–676), and is born where its parent ended "divided", one generation on, with its parent's
   root (:713–726). Fusion needs `parent_of` edges as the record, with shares summing to one; a
   fusion birth and end; and generation and root under two parents.
2. **Lives that are not cells.** A life's id is `carrier:<name>` (:652). A mitochondrion needs a
   declared entity kind, and an "inside" relation over time that moves at its owner's division while
   its own life goes on.
3. **Removal in a living owner.** `removed` is a declared bottleneck (:104); mitophagy needs
   `degraded`, which machines ask for too.
4. **Same-time order.** GARD found that the event-row rule cannot order two events at one time
   (`gard-g1-merge` c6dd5956). One fixed step often holds a fission, a fusion and a removal.
5. **Keys** for two parents, since RELATIONSHIPS_DESIGN §1.3's sub-lineage rule assumes one.
6. **Labels** that mix at fusion and split at fission (RELATIONSHIPS_DESIGN's RT3), for D's second
   question.

The other consumers are machines (`assembled`, `disassembled`, `degraded`, `assembled_from`,
`member_of`; MOLECULAR_MACHINES_DESIGN §2) and GARD's same-time order: one design serves all three.

**B.5 Another representation: fixed segments with gated links (S).** A mitochondrion is a set of
fixed compartments. Fusion opens a matrix route between two of them, and fission closes it; a
mitochondrion at a given time is a connected component of the open routes.
- **It avoids** split, merge, re-anchoring and any change of capacitance or mask, and descent
  becomes a graph query (D200).
- **It needs** a route between two compartments of one owner, which refusal 1 refuses
  (`compartments.py`:289–294); a control on it, which faces lack (the base spec controls membranes
  and junctions only, `definitions/surface_tissue_spec.py`:123, :269); and condensation per owner.
- **Its limits:** fission only at segment ends, and sizes in whole segments. Removal and biogenesis
  still need their doors.

### C. Choosing the setup

- **Today the hosts a definition declares choose the level:** one compartment of N members (lumped),
  several per owner with different capacities (classes), or N compartments (static individuals).
  Each is exact where it claims to be, for identical members (A.2).
- **Nothing refuses two levels for the same mitochondria.** A lumped node and individuals in one
  cell are both just compartments.
- **A named, checked choice between levels that are not exact needs D175's four fields,** which
  registration refuses (`registry/laws.py`:25–26, :161–165, :195–203).
- **Mitochondria's requirements on the fields,** for one design with fuel (D174, the first consumer)
  and machines (D209, L4):
  1. **On host declarations, not only on `Law`.** A mitochondrion's level is set by the compartments
     declaration, an operator, and later by the event doors.
  2. **`represents`:** a key for the population and its owner, with each declaration's share. A pool
     beside k individuals stays admissible when the shares are disjoint and cover the whole.
  3. **`preserves`:** totals, mean state and the capacitor relation (lumped); per-class or
     per-member state; identity, history and connectivity (dynamic). What each level drops is named.
  4. **`supports`:** a lumped node answers mean ΔΨ and ATP output. It refuses the ΔΨ distribution,
     the depolarised share, a member's age, "depolarise one mitochondrion" and "block fusion".
  5. **`qualified`:** exact for identical members within A.2's tolerances; otherwise an error budget
     declared before a comparison with individuals, one case outside failing (A.2's controls).

### D. The science

**The first research question (S): do fission, selective fusion and removal keep a cell's
mitochondria polarised, and what spread of ΔΨ and depolarised share do the measured event rates
give?**
- **It needs individuals.** A lumped node has one ΔΨ, and classes have fixed members. A depolarised
  subpopulation is made by fission and kept apart by selective fusion, so it depends on each
  mitochondrion's history. **It comes first** because it needs no cell division and no door D.
- **Something must break the symmetry (S).** Deterministic laws keep identical members identical
  (A.2), and a split with a = f keeps V_b (B.1), so selective fusion would have nothing to select:
  - **a prescribed unequal split** makes Twig's asymmetry an input, and the check a consistency one;
  - **discrete units drawn at fission** (respiratory or pump units) make it a prediction, but need
    draws at fission and integer unit state, which kinds lack today (MOLECULAR_MACHINES_DESIGN
    §10.4);
  - **a per-member damage law,** such as FR-5's damage kind (`compartments.py`:80), is an input when
    scheduled and draws when its onset is random.
  - **Recommended: discrete units,** the only predictive source. Keyed draws then come before the
    first question, not only with inheritance (E).
- **The data:** Twig et al. 2008 (EMBO J 27:433–446; PMC2234339), free to read, with no licence
  stated on the page read; numbers only (D186, D201). Read through a page-reading tool, which
  summarises; a direct read is owed before any number is registered. Cells: rat INS1, the COS7 line,
  primary mouse β-cells and mouse embryonic fibroblasts.

| Quantity | Value | Measured or inferred |
| --- | --- | --- |
| Time fused after a fusion | 77 ± 71 s (INS1); 87 ± 78 s (COS7) | Measured |
| Time solitary after a fission | 1,434 s (INS1); 1,172 s (COS7), means | Measured |
| Fissions giving one depolarised and one hyperpolarised daughter | 85% of 48 | Counted, at a 2 mV criterion on the inferred scale |
| Size of those changes | +5.9 ± 3.7 and −6.5 ± 3.8 mV | Inferred: TMRE intensity to mV by a calibration published elsewhere (Twig et al. 2006, not read) |
| Fusion within 3 min of a fission | About 6 times likelier for the hyperpolarised daughter | Counted; that ΔΨ causes it is inferred |
| Non-fusing mitochondria | TMRE 26 ± 5.3% dimmer, given as 7.8 ± 1.6 mV | Intensity measured; mV inferred |
| Cells with a non-fusing subpopulation | 32% of INS1 cells (n = 22); 60% of primary β-cells (n = 10) | Measured |
| Depolarisation before engulfment | ≥ 1 h | Inferred from dye pulses |

- **A judged check (S).** Cited inputs: the event times, and a declared fusion hazard that depends
  on ΔΨ. Targets for Cells' ΔΨ physics: the depolarised share and its TMRE deficit, compared as
  intensity ratios through a declared dye model, so the Nernst conversion stays in the observation
  model. The daughters' asymmetry is a target only if fission splits discrete units unequally;
  otherwise it is an input. β-cell data under D193's cardiac laws is a declared mismatch, as at M6.

**Inheritance, second:** Katajisto et al. 2015 (Science; PMC4405120), an author manuscript free to
read, with no licence stated on the page read, read the same way.
- Human mammary stem-like cells, mitochondria labelled through an outer-membrane protein (Omp25).
  Divisions within 10 h of labelling were symmetric and later ones asymmetric: "old" is ≥ 10 h.
- About 5.6-fold more old label went to one daughter (photoactivatable GFP). By SNAP-tag the old
  label split 89% : 11% (n = 5, p = 0.004), the young 67% : 33% (p = 0.04). A fission inhibitor
  (mDivi-1) cut the share of daughters receiving mostly young mitochondria (numbers not read).
- **Measured:** label intensities per daughter. **Inferred:** "age", from labelling time, and
  stemness, from a sphere-forming assay. An age label is not a damage variable (the review).
- **What Cells could test (S).** With no space inside a cell, Cells cannot place old mitochondria.
  It can test whether rules without space (fusion mixing labelled content, then a random partition)
  reach the measured split. If they cannot, the asymmetry is a declared rule, an input. It needs
  labels (B.4).

**Which organism.** Cardiac cells rarely divide (the lead's premise; no number read). The first
question needs no division; its data are from rat and mouse cells and the COS7 line. Inheritance
needs dividing human (Katajisto's) or mouse cells. No planarian data were sought; JCVI-syn3A has no
mitochondria; mtDNA, the review's optional item, is out of scope.

### E. Options and a recommendation

Agent-days are rough (**S**).

| Option | What | Agent-days | Needs |
| --- | --- | --- | --- |
| **O1, recommended** | (1) **Now:** mitochondria's requirements into three formats before they freeze: seam B, whose operators owner holds `compartments.py` in the pass (CORE_SEAMS §13), for compartments in the entity hierarchy and a merge verb; `cells.relations@2` (D209, L1); D175's fields (D209, L4). Condensation is recorded beside FR-17. (2) **Soon:** A.2's check. (3) **After the pass:** B's doors on FR-4's compartments, prescribed events first | (1) 0.5–1; (2) 1–1.5; (3) 25–39 | (2): FR-4's judged run done, and a free lane. (3): seam B and condensation |
| O2 | D193 as written: individuals at M8, after M7 | (3), later | The formats freeze without these needs and are edited again |
| O3 | B's doors before D193's M3 | As (3) | No physics to judge them with; it takes the operators owner during the pass |
| O4 | Fixed segments with gated links (B.5) in place of split and merge | About 13–19 for (3) | A route between compartments and its control. Coarser |

**O1's step (3), in order:** condensation 3–5; split 3–4; merge with its bookings 3–5; removal
1.5–2.5; keyed streams for draws at events 2–3, with integer unit state 0.5–1
(MOLECULAR_MACHINES_DESIGN §10.5); geometry as state 3–5; state-triggered events 1.5–2.5; door D
for compartments 1.5–2 (FR-1 §10 gives about 1.5) and its stochastic partition 1–2; `@2`'s writer
2–3, shared with machines and GARD; independent references and a protocol 3–4. **O4's (3):**
condensation per owner 3–5; a route between compartments with its control 3–4; removal 1.5–2.5;
creation 1.5–2; relations as interval edges 1–1.5; references and a protocol 3–4.

**The order:**
1. **GARD and the gap-junction replication keep the highest priority** (D207, amended). O1 takes
   none of their CPUs or files, and the GARD reuse question waits for its G1.
2. **The core-seams pass comes first:** seams A and C gate every mitochondrion, seam B the doors.
3. **The desk work now; A.2's check when a lane is free. After the pass, two lanes on disjoint
   files:** D193's M3–M5, and O1's step (3) on FR-4's compartments.
4. **M6 (host C) brings static individual mitochondria** with no further door; **M8 then moves
   ahead of M7,** the doors carry over, and D's first question becomes M8's first protocol.

### Questions

- **For the user.** **U1:** D's first question, on data from cells that are not cardiac, with
  inheritance second, and discrete units drawn at fission as the source of asymmetry? **U2:** O1,
  with M8 ahead of M7? **U3:** split and merge, or segments (O4)?
- **For the lead.** **L1:** hand B's and C's requirements now to seam B, `cells.relations@2` and
  D175's fields? **L2:** condensation as the route for many compartments, recorded beside FR-17,
  whose entry says only the 3D table needs it? **L3:** reusing GARD's partition rules, with GARD's
  owner, after its G1? **L4:** A.2's check, its lane and time, after FR-4's judged run?

### Sources for this addendum

- **Read:** the documents, decisions and code cited above, at main 7538b0cd (DECISIONS.md D057,
  D144, D174, D175, D186, D193–D195, D201, D202, D207–D210 among them), and GARD_DESIGN.md §5.2 on
  `gard-g1-merge`. **Cited through those, not read:** MODULE_SYSTEM_DESIGN §5, S5 §3.5, FR-1 §3.1
  and §5.3 (through FR-1 §0 and §8), D147 and D200.
- **External, 17 November 2026:** one web search and two pages through a page-reading tool, for Twig
  et al. 2008 and Katajisto et al. 2015. Numbers only; searches used titles and scientific terms.
  **Cited, not read:** Twig et al. 2006.

## The synthase stall check: the registered rule (21 November 2026)

**Status: a rule registered before the per-entry data are read (D269; the lead's go, 21 November
2026).** Docs only, on branch `mito-stall-rule-mt1b-draft` from main fff62169; the lead's tag
registers it. Nothing under `src/` or `validation/` changes, and the driver is built only once the
data are in. **S** marks this section's own derivation or arithmetic.

**The question.** Petersen et al. (2012) measured the stall of purified yeast mitochondrial ATP
synthase in proteoliposomes at an imposed 60 mV, at ten loads Q = [ATP]/([ADP][Pi]) (Table S4,
corrected for uncoupled hydrolysis; doi:10.1073/pnas.1202799109). The Lean lane's comparison
(`lean/claims/mitochondrial-stall-heat.md`; `yeast_synthase` in
`lean/checks/mitochondrial_stall.py`) sets the offset at the single entry at Q = 5.79. The endpoint
shift then matches the law's three protons (0.745 pH unit predicted, 0.74 observed), and four
intermediate entries fall 0.068–0.078 pH unit below the line, outside the added interpolation
limits. D269: free activities and interpolation errors are checked before any change of
stoichiometry; the paper's coupling is 2.9 ± 0.2 H⁺/ATP.

**What was seen before this rule, disclosed.** A desk probe on the Lean lane's manifest
(`lean/checks/data/mitochondrial_stall.json` at main 587ba787, last changed in f0783ad9: each
entry's Q, stall and interpolation limit), on total quotients with a constant conversion to the free
quotient. Evidence:
`/mnt/workspaces/Cells/mito-resume-20261121/stall-stage-a/` (`refit.py`, `curvature.py` and
`rule_status.py`, each with its JSON).
- **The anchor decides the count.** With each of the ten entries as the single anchor (n = 3, added
  limits), between 0 and 5 of the other nine fall outside. The 0.068–0.078 figures belong to the
  anchor at Q = 5.79, which lies 0.046 pH unit above the weighted line.
- **Both fits include 3.**
  - Unweighted, through all ten: n = 2.87 ± 0.18, which reproduces the paper's 2.9 ± 0.2.
  - Weighted by the interpolation limits, read as standard deviations: n = 3.01 ± 0.14, or ± 0.21
    scaled by χ².
  - 8/3 is about one standard error from the unweighted fit, so these data do not select n.
- **The quadratic: a description made after the fact.**
  - With n = 3 and one fitted offset, the residuals' signs run + − + − − − − + + + with Q ascending,
    and χ² is 19.0 on 9 degrees of freedom.
  - A quadratic term in log₁₀ Q brings χ² to 3.1, with c = 0.078 ± 0.020 per decade² (weighted).
    Unweighted it is 0.078 ± 0.019; leaving out any one entry gives 0.069 to 0.096.
  - Ten points cannot separate curvature from an offset between measurement series.
  - A constant n changes only the slope, so no change of stoichiometry removes this pattern.
- **On the manifest as it stands, both criteria below fail:** (i) by 0.051 pH unit (the entry at
  Q = 0.095 against the second at Q = 1.87), and (ii) with c at 4.0 standard errors.

**What free activities mean for the engine (the laws appendix's §0 and §2; S).**
- The law's x reads ATP⁴⁻, ADP³⁻, HPO₄²⁻ and h_N at N, h_P at P, and Δψ = φ_P − φ_N. Its binding
  set has Mg²⁺ on ATP and ADP and H⁺ on phosphate, nothing more.
- At stall, with ΔpH = pH_N − pH_P and n_A = 3:
  ΔpH_stall = log₁₀(Q_b)/n_A + pH_N/n_A − Δψ/(RT ln 10/F) + ΔG°_F/(n_A RT ln 10),
  where Q_b = Q (1 + [Mg²⁺]_N/K_MgADP)(1 + h_N/k_dH)/(1 + [Mg²⁺]_N/K_MgATP) and Q is the total
  quotient.
- In one medium the conversion, pH_N and Δψ are common to every entry, so they cancel from the
  shifts, which follow log₁₀ Q/3 alone. Free activities move the shifts only through what differs
  between entries:
  - catalytic-side pH: 0.1–0.2 pH unit gives 0.03–0.07 at a fixed Q_b;
  - free Mg²⁺, through Q_b;
  - Δψ: 1.8–4.1 mV gives 0.03–0.07, at 59.16 mV per pH unit (298.15 K).

**The mapping.** N is the external medium, where F₁ sits; P is the lumen. ΔpH is the paper's
pH_out − pH_in. Δψ is the imposed diffusion potential, lumen positive.

**The data, requested** through the lead's brief, from the Lean lane through the user. Numbers with
their citation only (D186); no file is committed.
- Per entry: total ATP, ADP, phosphate and Mg²⁺; K⁺ on both sides (for Δψ); catalytic-side pH;
  temperature; the measurement series.
- Per entry, where reported: the rate points and the uncoupled-hydrolysis correction behind its
  interpolated stall.
- The paper's definition of its quotient. If it is not the total concentrations in the assay medium,
  the reader records the definition, and the driver converts it to totals before the engine's
  closure.
- A quantity not reported per entry takes the paper's stated common value; one not stated at all is
  declared and listed. The Lean lane owns the manifest, and the driver reads it at a named commit
  with `git show`.

**The computation, built only after the data are in.**
- **Engine models:** `proton_coupled_atp_synthesis_cycle@1` on `cells.transporter@1` in
  `resolved_pump_tissue@3`, with `rapid_binding@1` and the `beard2005@2` potential set. The engine
  only evaluates, through the cycle kind's numpy path at a world's start, as the Lean driver does;
  no step is taken. The engine revision is recorded at run time.
- **Per entry,** the predicted stall is the ΔpH at which the engine's x is zero at that entry's
  conditions, found by bracketing; d_i is the observed stall minus the predicted one.
- **Temperature:** the registry rows' 298.15 K (D236). The assay's temperature is recorded; with a
  common Δψ it moves only the offset.
- **Arm 1:** Table S4's corrected stalls.
- **Arm 2, reported, not judged, and only if every entry's rate points are reported:** each stall
  re-derived as the zero of the law's own J(ΔpH) shape at that entry's conditions, fitted to its
  rate points with the zero's position and one amplitude free, after the paper's
  uncoupled-hydrolysis correction applied the same way to every entry. The paper's σ_i are kept. If
  the correction cannot be reproduced from what is reported, arm 2 is not run, and that is
  recorded.

**The rule.**
- **n stays 3.** The law's counts fix it (n_A = 3, a declared limit until affine counts exist, a
  held item), and the check fits no n. A free-slope fit is reported, not judged.
- **Only the load dependence is judged.** One common offset is free. It carries ΔG°_F at 298.15 K,
  the assay's temperature and Δψ's calibration, and is reported, not judged.
- **(i) Every residual within its own limit:** some common offset b gives |d_i − b| ≤ σ_i for every
  entry, that is max(d_i − σ_i) ≤ min(d_i + σ_i), with σ_i the entry's reported interpolation limit.
- **(ii) The quadratic below two standard errors:** the weighted fit d_i = b + c (L_i − L̄)², with
  L_i = 3 × (entry i's predicted stall), the load in decades of the effective quotient (in one
  medium, log₁₀ Q_i plus a constant), weights 1/σ_i², and c's standard error from the normal
  equations without χ² scaling: |c| < 2 SE(c). The unweighted fit is reported.
- **The verdict reads arm 1 only.**
  - The item closes as explained if (i) or (ii) holds ("explained by the per-entry conditions").
  - Otherwise it is recorded as an unexplained feature of the reconstituted yeast assay: a
    validation target, not a defect of the law.
  - Arm 2's (i) and (ii) are reported beside it, as information on the interpolation.
  - Either way the engine is unchanged. The verdict and its numbers go to the Lean lane's claim
    through the lead.

**What it does not claim.**
- The cardiac model's n_A: the law's 3 is Beard's Table 1 value, and these are measurements on the
  yeast enzyme. They test the 1/n load dependence.
- The absolute stall: the offset is not judged.
- Binding outside the engine's set (Mg²⁺ on phosphate, K⁺ on the nucleotides, ionic strength). It
  matters only if phosphate or salts differed between entries, and is then listed as a limit.
- Differences of Δψ between entries that the tables do not report.

## MT-1b's registration: DRAFT (21 November 2026)

**Status: DRAFT, NOT REGISTERED AND NOT TAGGED.** Desk only, on the same branch. It registers
nothing. It sets out the user's choices for the morning, with recommendations. The registration is
written after those choices and C1's checks, and tagged by the lead before any engine organelle
output exists. **S** marks this draft's own reading, arithmetic or proposal.

**Decisions so far (22 November 2026).**
- R2, a fresh code-blind integration, is the judged reference (D280).
- W2's option 1 is built: the outer-membrane face that reads the IMS closure (D288). Its design is
  the next section.
- The judged run keeps ΔΨ at 180 mV with the source's activities, and takes a larger CPU budget
  rather than scaled activities (D288).
- **The solver route (W1): implicit cycles (D290).** The cycles' slope conductances join N2's
  operator. With explicit cycles the run would have cost years of CPU.

**What MT-1b is** (CORE_LAWS_ROADMAP §2.4; §5.2 and §7 here; D235 item 2; D288). Cells' own
organelle in a medium, on host P. It runs §7's respiratory-control protocol at the source's
activities and ΔΨ near 180 mV, with the cycles implicit in N2's operator (W1; D290). It is judged
against R2, an independent integration of the same declared equations. It reproduces no published
model; that is MT-2. Roadmap estimate: 3–5 agent-days, plus CPU.

**Engine models** (the roadmap's list, brought to main fff62169):
- `resolved_pump_composite@1` over `resolved_pump_tissue@3`, with @3's IMEX ARS(2,2,2), with or
  without N2 (`imex_ars222_implicit_conductances@1`, landed 03fe5119: the membranes' and junctions'
  slope conductances; the cycles stay explicit);
- `cells.transporter@1` hosting head 1's and head 2's nine laws, with its availability schedules
  (`transporter_controls`);
- `cells.passive_routes@1` with `proton_constant_field_leak@1`: the leak, and the uncoupler on its
  own patch;
- `cells.rapid_proton_buffer@1` declaring `rapid_binding@1` at N and P (H⁺ and Mg²⁺ on ATP, ADP, Pi
  and a buffer), on `beard2005@2`;
- the outer membrane as a face (W2);
- `scheduled_bath_composition@1` for the ADP step;
- `step_doubled_energy@1` (X2) in every registered run.

### The worlds

**The start: head 2's host-P test world** (`host_p_world` in `tests/unit/test_mito_cycle_laws.py`).
It has `beard2005@2`'s rows at 298.15 K, the nine laws (seven across the inner membrane, the supply
at N and the kinase at P), the closure at the matrix and the IMS (H⁺ and Mg²⁺ on ADP, ATP, Pi and
each node's buffer), and the supply's pair held at its declared ratio.

**What it lacks for MT-1b (S):**
- **Its layout is FR-4's.** The matrix cell also faces the held bath through a plasma patch, and
  the IMS, FR-4's lumen, has no outer membrane. Host P (§1.1) needs the matrix facing the IMS only,
  and a face from the IMS to the held buffer.
- **Its capacities** are 10⁻¹⁵ fmol/s, chosen to keep two steps bounded, not declared activities.
- **It has no leak and no O₂ supply.** Its volumes and capacitance are FR-4's.
- **Parameters, proposed:** Table 1 (2006) as head 2's populations carry it, with W1's activities.
  The set is declared, not the source's, so MT-1b reproduces no published model.

**W1, the activities and the solver route.**
- **Decided (D288):** the source's activities, with ΔΨ at 180 mV. The scaled activities this draft
  first proposed are dropped.
- **The step bounds** (P1′, CORE_SEAMS_STEP0 §9.2):
  - the cycle kind's explicit bound at the source's activity: 27 ns at 180 mV, 0.8 µs at 150 mV;
  - the outer membrane's face at the source's permeabilities: about 18 µs.
- **The step's cost, measured on 22 November 2026** on head 2's host-P world at 184fc81c (light CPU
  7, nice 10; `/mnt/workspaces/Cells/mito-mt1b-20261122/`):
  - the compiled device step alone: 6.3 ms;
  - today's runner path for that world: 168 ms a step (being traced; the lead's side item).
- **The price of 300 s of protocol (S).** One trajectory runs on one core, so its CPU time is also
  its wall time.

| Route | Steps | Device step | With X2 (×3) | Today's runner path |
| --- | --- | --- | --- | --- |
| Explicit cycles at 180 mV (27 ns; P1′'s proxy, an upper-end estimate) | 1.1 × 10¹⁰ | ≈ 19,400 CPU-h | ≈ 58,000 CPU-h | ≈ 5 × 10⁵ CPU-h |
| Explicit cycles at 150 mV (0.8 µs) | 3.8 × 10⁸ | ≈ 650 CPU-h | ≈ 2,000 CPU-h | ≈ 17,500 CPU-h |
| Implicit cycles; the face's 18 µs binds | 1.7 × 10⁷ | ≈ 29 CPU-h | ≈ 87 CPU-h | ≈ 780 CPU-h |

- **Decided (D290): implicit cycles.**
  - With explicit cycles the run takes years of wall time at 180 mV, consistent with the @3 owner's
    estimate (10 CPU-hours needs activities 1,100 times lower).
  - So the cycles' slope conductances join N2's implicit operator: D235's build for MT-2, branch I
    of §8 (M2's 6–9 agent-days). Its design is the last section of this note.
  - Under that route the face's 18 µs binds. With the windowed runner's device row checks (12.5 ms
    a step on head 2's world), that is about 58 CPU-hours, 2.4 days a world, detached on a lane,
    before X2's half steps.
  - Still unpriced: the fast chemistry's explicit material bounds at the source's activity (the
    IMS kinase runs at 44 times respiration). C1 measures them on MT-1b's world.

**W2, the outer membrane: decided, option 1 (D288).** The kinds owner found that judged readouts
depend on the IMS binding equilibria, which rules out option 3. The face that reads the IMS closure
is designed in the next section; the options below are kept as the record.
- ATP, ADP, AMP and Pi must cross it. In the IMS they are closure rows, which `check_closure_rows`
  refuses at a face (CORE_SEAMS_STEP0 §9.2; still so at fff62169).
- The @3 owner's options:
  1. **a face that reads the closure:** 2–4 days, an engine build;
  2. **outer-membrane uniports:** 4–6 days, which needs a new host;
  3. **no closure in the IMS:** no engine cost, but a declared departure. The IMS's nucleotides and
     Pi are unbound, and the laws read totals at P;
  4. **host C,** which D235 did not choose.
- **Recommended (S): option 1,** now decided. The kinase and the exchange read free forms at P, and
  the base-form laws read the closure.
- **The face law is ruled:** `logmean_electrodiffusion@1`, provided the lane shows it reduces to
  the source's p·Δc at zero potential difference; its runs report the potential across the outer
  membrane (the roadmap's D234 rulings). The appendix's §8 declares a Fick flux for each form, which
  sums to Eq. 13's totals exactly, and leaves the IMS's free H⁺, K⁺ and Mg²⁺ to the world. So W2's
  open point is the closure-row path alone, with that declaration.
- **Its step cap:** about 18 µs at the source's p_Pi and 70 µs at p_A, lowered with W1's
  permeabilities.
- A face carrying a driven gradient is untested for order (CORE_SEAMS_STEP0 §9.4 B). C1 tests it.

**W3, the protocol's worlds:**
- (a) the main world, with a held buffer;
- (b) the uncoupled control;
- (c) the exchange off, whose effect must exceed the declared budget (§7's controls);
- (d) a finite-buffer variant for O₂ exhaustion.

State 4 uses a declared ADP trace, bounded against the judged effect (the roadmap's ruling, D233's
pattern). How O₂ is held at N, as the source holds it at 26 µM, is checked in C1: a held row of
complex IV's population if its law admits one, or permeation from the buffer.

### The protocol

§7's steps run on the step grid. Each mechanism below was read from main's code and docstrings
(steps 2 and 4 from comments only); none has been parsed in a world. C1 checks each before
registration.
1. **The ADP step,** 0 → 1.3 mM → 0 in the buffer, by `scheduled_bath_composition@1` on the held
   buffer. Its composition with declared kinds is checked first (§7).
2. **The uncoupler step.** A second inner-membrane patch carries only the leak, at the uncoupled
   permeability. Its availability steps from 0 to 1: a passive route's opening is its patch's
   availability, at most 1.
3. **The inhibitor step.** Complex IV's availability is set to 0 by its `transporter_controls`
   schedule. The reversed synthase and exchange then spend the buffer's ATP.
4. **O₂ exhaustion** in W3(d): O₂ falls through the declared P50 range.

Each plateau runs until its drift over a declared final window is below a tenth of its band.

**Readouts:** ΔΨ; both sides' pH; NADH's and cytochrome c's reduced fractions; O₂ flux; ATP export;
each cycle's rate; every ledger.

### The reference: options for the user

**Decided: R2 (D280),** a fresh code-blind integration, as the judged reference. R1 and R3 are kept
below as the record. Whether R1's plateaus are reported beside R2 is still open. Its author must not
have read the engine.

**R1: MR1's frame-B arm at declared activities.** This is MR1-MT2's arm (tag
`mito-mr1-mt2-registration-2026-11-20`), with W1's activities as overrides.
- **For:**
  - It exists and is code-blind, and its arm matches the appendix term by term.
  - Its steady states come from a 50-digit Newton solve: integration agrees within 4.7 × 10⁻¹³
    relative.
  - It already runs the ADP step in the rapid Mg²⁺ limit (`reproduce.adp_step_time_course`, X_MgA
    at 10⁹ or more; the ADP_STEP row of `references/proposal.json`).
- **Against:**
  - It has no uncoupler, inhibitor or O₂-exhaustion step.
  - Its IMS free Mg²⁺ is held at the buffer's. The appendix leaves that to the world (its §8), so
    MT-1b's world must declare the same rule, or R1 must take the world's.
  - Its outer membrane is Eq. 13 on totals, which the appendix's per-form fluxes sum to exactly. The
    engine's face reduces to them only at zero outer-membrane potential, which its runs report
    (W2).
  - It is also MT-2's reference, so one error would pass both milestones.
- **The 6.78 limit.** `xf1_scaling` (on `mito-references`) finds that X_F1 can be lowered up to 6.78
  times while frame B's fit to the published curves stays within 10% of its own (3.36 against
  3.10).
  - Within the limit, MT-1b stays close to MT-2's behaviour.
  - But only X_F1 is scaled, and the explicit step stays near the source's. Scaled from P1′'s
    bounds, if the synthase alone sets them (S): about 5 µs at 150 mV and 0.2 µs at 180 mV, so
    about 60 and 1,500 CPU-hours for 300 s at P1′'s runner rate.
  - Past the limit (30 times and more, W1), the fit departs: 4.81 at 30 times, 17.3 at 300 times.
    MT-1b does not judge that fit.

**R2: a fresh code-blind integration of MT-1b's declared equations** (§5.2 and the roadmap §2.4 as
written).
- **For:**
  - It is the plan's own reference.
  - It covers every protocol step and transient, with the engine's closure at N and P as declared.
  - It is independent of MR1, so MT-1b and MT-2 keep separate references. R1 and R2 can then check
    each other at the plateaus where their equations coincide.
- **Against:**
  - It needs a new agent seat, and the lanes are at the cap.
  - It takes about 2–4 agent-days (S).
  - It waits for W1 and W2, since it integrates the same declared equations.

**R3: MR1 extended by its own agent,** with a rapid-binding switch (the IMS free Mg²⁺ solved), the
other three steps and W1's activities.
- **For:** it reuses MR1's verified accounting (frame B, Eq. 22, its invariants and plants), and it
  is cheaper than R2: about 1–2 agent-days (S).
- **Against:**
  - It is coupled to MT-2 in the same way as R1.
  - It adds new code in `references/` beside a registered arm.
  - Its author's brief included this note (the roadmap's D234 rulings). That only touched Eq. 11's
    finding, which is now settled.

**Recommended (S): R2 judged, with R1's plateaus at the same activities reported beside it.** That
checks both references, as D193 judges R1 against R2 for MT-2. If no seat frees, R3.

### Tolerances, plants and checks

**Tolerances** follow D193's rule: from the reference's convergence or a stated physical scale,
never from the engine.
- **Plateaus:** MR1-MT2's bands. ΔΨ ±0.05 mV; pH ±0.0005; NADH's and cytochrome c's fractions
  ±0.0005; O₂ flux and the matrix's K⁺, Pi and ATP ±0.1%. Their basis is a third of the published
  figures' 1-px resolution.
  - An IMEX step's fixed point should be the equations' steady state (S, asserted, not shown here).
    The registered run's dt/2 repeat covers the plateaus too, and the drift rule covers the
    approach.
- **Transients:** a stated physical scale per readout, a tenth of its excursion in the step, fixed
  at registration from the reference alone. MR1's ADP_STEP row proposed ΔΨ 0.2 mV and NADH 0.002.
  - The dt is chosen in C1 so that the engine's Richardson estimate at it is below a third of each
    band. The registered run repeats at dt/2 as a check, plateaus included.
- **Ledgers:** material, charge and energy close at every step. The matrix's Mg²⁺ total and charge
  invariant drift less than 10⁻⁹ relative (MR1's INV row).
- **Thermodynamics:** every process's dissipation is non-negative at every plateau (MR1's THERMO
  row).

**Plants.** Each must miss by at least 3 bands on a judged row, the references' margin.
- **P-a:** the exchange's shares at 0.35 and 0.70, not summing to one (MR1's P4: a zero offset of
  0.05 FΔΨ).
- **P-b:** a 1% coefficient change, the exchange's activity × 1.01. MR1's P5 found 4 to 9 bands on
  its grid.
- **P-c:** the 2005 k_O₂ (MR1's P2), caught on O₂ exhaustion.
- P-a and P-b are rerun in the reference at W1's activities before registration. A plant that misses
  by fewer than 3 bands is replaced, before any engine output.

**C1: the checks before registration.** These are development runs, not judged, on light CPUs.
None takes a test lane ahead of FR and core.
- The worlds parse with W2's option, and every population is admitted.
- Steps 1–4's mechanisms compose with the declared kinds.
- **A dt study at W1's activities,** on plain ARS and on N2: second order, with no stage, validity
  or ledger refusal. It includes the face's order under a driven gradient, the untested case above.
- **X2's count check at the worlds' flows.**
  - X2's count threshold is 1000 eps M, and M grows with a run's flows (CORE_SEAMS_STEP0 §9.2,
    §9.4).
  - The binding closure's floor, which blocked P1′'s reading (b), was removed at its source
    (4802dc9a: R's median |e| fell from 9 × 10⁻¹³ to 1.4 × 10⁻¹⁷ pJ).
  - C1 records, per world at the chosen dt: the counted steps; the median order ratio (near 4 at
    second order); the held count against its cap; and the largest integration error against its
    cap.
  - If X2 would refuse, MT-1b is not registered, and the finding goes to the user.
- **The registered runs' cost,** from C1's step rate (S: P1′'s runner did about 10⁶ steps per
  CPU-hour). Runs of 10 minutes or more go detached.

### Held, and the morning's choices

**MT-2's engine run is held for the user (D277).**
- At Beard's synthase activity it needs the cycles' and faces' slope conductances in N2's operator
  (D235 item 2).
- N2 landed with membranes and junctions only. That build is not designed.
- MR2, the published model run out of process, can start now that MR1 is registered (the roadmap's
  §2.4).

**Decided, and open (22 November 2026):**
- **Decided:**
  - W2's outer membrane: option 1, the face that reads the IMS closure (D288);
  - the reference: R2 (D280);
  - the source's activities at 180 mV, with a larger CPU budget (D288).
  - the solver route: implicit cycles in N2's operator (D290).
- **Open:** the buffer's treatment under the face, (a) or (b) (the next section's §3); and whether
  R1's plateaus are reported beside R2.

## MT-1b's outer membrane: a face that reads the IMS closure (design, 22 November 2026)

**Status: a design, before code (D288; W2's option 1).** It is more than a day of engine work, so
this note comes first. It is for the lead, with the @3 owner (faces, the IMEX step, reservoir work)
and the binding owner (the closure's read, the forms), before any code. **S** marks this note's own
reading or proposal. Read at main c79e8ca4.

**Why.** ATP, ADP, AMP and Pi cross the outer membrane, and in the IMS they are rows of the general
binding closure (`rapid_binding@1`: H⁺ and Mg²⁺ on the adenylates, Pi and a buffer).
- `species_registry.check_closure_rows` refuses @3's own routes at closure rows, faces included,
  because they read stored totals as concentrations.
- The kinds owner found that the judged readouts depend on the IMS binding equilibria, so option 3
  (no closure in the IMS) is out (D288).

### 1. Who owns it

**@3's own face path, reading the closure.**
- The core owns it: the face fluxes (`numerics/surface_transport.py`), the IMEX step's face terms
  (`numerics/surface_imex.py`, `models/surface_pump_v3.imex_step`) and the reservoir work.
- The binding owner's general closure supplies the read (`kinds/proton_buffer._general_read`) and
  the forms (`laws/reactions/rapid_binding.forms_from_free`).
- **It is not a composite operator.** Closure rows cannot be moved by split operators
  (`check_stage_read_rows`). The face must also sit in the IMEX step, where the field solve sees its
  electromigration.
- **Nor a kind:** kinds are hosted on patches and junctions, not between two outside nodes. That is
  option 2, at 4–6 days.

### 2. The law: each binding form moves by log-mean electrodiffusion

A new face law, `logmean_electrodiffusion_forms@1` (name **S**), declared per face in place of
`logmean_electrodiffusion@1`.
- **A binder row** carried by the face (ATP, ADP, AMP, Pi) moves as its forms f. Each form moves at
  its own valence z_f and its class's diffusivity D_class (the appendix's §8: one permeability for
  the adenylate forms, one for the phosphate forms):
  J_f = (D_class A/L) · logmean(c_f,s, c_f,r) · [ln(c_f,s/c_f,r) + z_f F Δφ/RT].
  This is today's face expression, per form.
- **The rows move by their forms.** The binder's stored row changes by Σ_f J_f, and each ligand row
  by Σ_f n_f,ℓ J_f: a bound form carries its ligand (the appendix's §8).
- **The free ions** that cross the outer membrane (H⁺, Mg²⁺, K⁺) move at their free amounts: the
  closure's read at the IMS, stored amounts elsewhere. Every other row keeps today's law.
- **At Δφ = 0 the forms' fluxes sum to the source's Eq. 13,** (D A/L)(c_total,s − c_total,r) on
  totals, since logmean(a, b) · ln(a/b) = a − b for each form. That is the condition the roadmap set
  for using log-mean electrodiffusion on the outer membrane (D234). The runs report the outer
  membrane's potential, φ_IMS − φ_buffer.

### 3. How it reads each end

- **The IMS, a closure node.** At each stage the closure's read gives the free ligands x_ℓ and the
  free base c_base. The forms follow: c_f = c_base β_f Π x_ℓ^{n_f,ℓ} (`forms_from_free`). The P1
  predictor reads free forms there already (`free_amount_reads`).
- **The held buffer: the open point.** A closure at a held bath is refused today
  (`proton_buffer`), because @3 values a held bath's supply at the stored total's concentration
  while the routes book against free forms, so the ledger cannot close. Two ways:
  - **(a) Held, with its speciation declared** (recommended, **S**):
    - the held bath's forms are solved from its held totals with the closure's own constants, once
      per held composition (again at a scheduled bath event);
    - its supply is valued at each row's free potential: a binder row at its free base's μ̃, a
      ligand row at its free ligand's μ̃. That is the value the face's forms carry, so the ledger
      closes.
    - It keeps the source's held buffer and FR-10's scheduled ADP step on a held bath (§7, step 1).
    - It changes @3's reservoir work, behind a static switch: only baths that a forms face
      touches.
  - **(b) A large finite buffer under the closure:** no reservoir change. But the ADP step then
    needs a dose on a finite node, and the buffer drifts slightly. It is a departure from the
    source's held buffer.

### 4. The IMEX step, the energy booking and the step bound

- **Field.** The face Laplacian's conductance gains Σ_f z_f² W_f, with W_f the forms' log-mean
  weights at the predicted state, as today's species terms. Electromigration stays implicit, and
  diffusion explicit.
- **Heat.** The tableau's booking, per form: RT J̄_f²/W_f, non-negative per form. With binding at
  equilibrium it agrees with the ledger's terms: @3's ideal terms on totals, the closure's stored
  term S_c, the capacitors, and (a)'s valuation at the bath. The energy ledger closes within
  `ENERGY_RTOL`, the tableau's quadrature. F2's exact booking does not apply, since the forms are
  charged (CORE_SEAMS_DESIGN §6.5).
- **Step bound.** The face's explicit diffusion bound joins the per-stage bound per form. P1′
  measured about 18 µs at the source's p_Pi (CORE_SEAMS_STEP0 §9.2), with A_OM/V_IMS = γ/V_i, the
  @3 owner's reading of Eq. 13. The mitochondria lane confirms that reading from the source.
- **Admission.** `check_closure_rows` admits the forms law at closure rows because it names the
  closure's read (`rapid_binding@1`), as kinds' movers are admitted. Today's face law stays refused
  there. Every binder that a forms face carries must have all its forms in one class.

### 5. What stays bitwise (D148), and the rows

- **Static switches only.** A face takes the forms path only where it declares the forms law; a
  bath takes (a)'s valuation only where a forms face touches it. No registered world declares
  either. So every registered program, crossrev set, G1 world and FR set stays bitwise, and the gate
  shows it.
- **Rows (D224)**, in the existing `test_rapid_binding_world.py` (FR-4's general-closure world with
  a face) and `test_mito_cycle_laws.py` (the host-P world):
  - at Δφ = 0, the forms' fluxes sum to (D A/L) Δc_total;
  - the ligands move with their bound forms, and the material ledgers close;
  - equal free forms at both ends give zero flux and zero heat;
  - a few steps keep the energy ledger within its bound, every form's heat non-negative;
  - with (a), a forms face to a held bath closes the ledger;
  - planted: forms moved without their ligands, or the bath's supply valued at the total's
    concentration, are refused;
  - admission: today's face law refused at closure rows, the forms law admitted; the outer
    membrane's potential read out.
- **The cost (S):** the @3 owner's 2–4 agent-days for the face path, plus about a day for (a)'s bath
  valuation.

### 6. The declared equations R2 needs from this note

R2, the judged reference, integrates the same declared equations (D280).
- From this note it needs:
  - the outer membrane's law, per form (§2);
  - the buffer's treatment, (a) or (b);
  - the free ions' crossing (§2);
  - the outer membrane's potential (§3).
  - **Erratum (22 November 2026):** §3 does not define that potential. φ_IMS − φ_buffer is set by
    zero net outer-membrane current (the lead's ruling), as MT-1b's world declaration states (G5).
- **The rest is fixed already:**
  - the laws: the appendix at tag `mito-laws-appendix-2026-11-20b`, with its §12;
  - the source's activities at 180 mV (D288);
  - §7's protocol.
- R2's own stiff integrator does not depend on the engine's solver route (D290).
- So R2's author can start once (a) or (b) is ruled and this note is accepted.

### 7. The build plan (22 November 2026): files, owners, bitwise, checks and price

**Scope.** The user approved this face, reading the IMS closure at 180 mV (D288), with the held
buffer as option (a) (the lead's ruling). The cycles stay explicit, at about 16 µs (D302). This
section plans the build. It decides nothing new, except where flagged at its end. It goes to the
@3, binding and kinds owners for review before any code.

**0. The first parse, already done (development, S): no parse change is needed.**
- **The test.** Step 0's world (MT-1b's world without its outer membrane), with its plasma patch
  removed, has the matrix and the IMS as one capacitor component with no capacitor to the bath.
  - With today's face law carrying K⁺ (a row no closure holds) from the IMS to the held bath, it
    parses.
  - Without the face it is refused: "Floating capacitor components require an outside return path
    to a clamp/gauge" (`numerics/surface_field.bind`).
- **So the field law already admits the topology** through a charged face path to a clamp. G5's
  condition is the field's own floating-offset solve, by current balance through that face.
- **The composite's floating-component refusal** (`pump_composite_adapter.check_field_inputs`)
  applies only to operators that change capacitances or activity masks, and MT-1b declares none.
- **Its build check:** the same parse with the forms law (a row; the forms face is charged too).

**1. The forms law, `logmean_electrodiffusion_forms@1` (§2–4).**
- **Files and owners** (the @3 owner's review, 22 November 2026):
  - a new law module, `laws/routes/logmean_electrodiffusion_forms.py`, beside today's face law;
  - electromigration in the IMEX's implicit operator: `numerics/surface_imex.py` (`face_weights`,
    `drift_flux`). The Σ_f z_f² W_f term goes there, not in `surface_pump_v3`;
  - the explicit face fluxes: `numerics/surface_transport.py`;
  - the field's face term and the floating-offset solve: `numerics/surface_field.py` and
    `tissue_field.py`;
  - the face-law dispatch: `models/inner_laws.py` (`FACE_ROUTE_LAW_ID`);
  - per-form heat and the per-form explicit bound, in @3's face booking and step rule;
  - its admission on faces in `definitions/surface_tissue_spec.py`, which today accepts only
    `logmean_electrodiffusion@1`;
  - `analysis/stationary.py` and `execution/state.py` read `face_factor`. Each must refuse a forms
    face statically or support it;
  - the IMS's free forms are read through the binding owner's export (`forms_from_free`,
    `free_amount_reads`).
- **Bitwise (the @3 owner's ruling).**
  - Forms faces are their own entity set, with their own layout fields and sender and receiver
    indices, statically absent unless declared. They are not a per-face branch in today's face
    arrays.
  - So plain faces and the implicit operator stay bitwise by construction (D148 case 2), and no
    registered world declares a forms face.
- **FR-42.** A labelled row on a forms face is refused in `label_errors` in version 1, since FR-42's
  face one-way term assumes one face factor per row. Whichever lands second adds the line.
- **Checks.** §5's rows, then the gate: crossrev, tiers 1+2, G1 and FR's bitwise set. Also a
  degenerate-equivalence row: a forms face that declares one form equal to its row reproduces
  today's log-mean face, bitwise where the arithmetic matches, otherwise at rounding.
- **Price:** likely 3–5 agent-days, with the implicit operator and the floating solve in it (the @3
  owner).

**2. The held buffer, option (a) (§3).**
- **Files and owners:**
  - `kinds/proton_buffer.py` (the binding owner) lifts its held-bath refusal for a bath that a forms
    face touches. It solves that bath's forms once per held composition with the closure's
    constants, and again at a scheduled bath event such as the ADP step.
  - @3's reservoir work (the @3 owner) values those baths' supply at each row's free potential.
  - **G3 holds the bath's free H⁺ (10⁻⁷·¹ M), not an H total** (the face builder's note). So the
    held bath's solve takes free H⁺ as given, solves the other free ligands (Mg²⁺) from their held
    totals, and lets the bath's H total follow.
- **Bitwise.** A static switch per held bath that a forms face touches, at `surface_pump_v3`'s
  reservoir work (1e-3 Σ μ·supplied); no registered world has such a bath.
- **Checks.**
  - §5's (a) rows;
  - one row where a scheduled bath event re-solves the bath's forms;
  - one row showing that a bath without a forms face stays bitwise.
- **Price:** about 1 agent-day (§5), split between the two owners.

**3. The leak and the uncoupler reading the closure (G1's Eq. 19 at h_P, erratum 2's item 1).**
- **Today.** `proton_constant_field_leak@1` is a route law with no declared reads.
  - Its kernel is `laws/transport/proton_leak.py`, the FR-4/FR-5 owner's, which is never edited.
  - Its host is `cells.passive_routes@1`, in `kinds/passive_routes.py` (the kinds owner).
  - `registry/species_registry.check_closure_rows` refuses it where rapid_binding@1 holds H⁺.
    Step 0's world showed this.
- **The change (the kinds owner's review, 22 November 2026):** `proton_constant_field_leak@2`.
  - It lives in a new inert law module that imports the unedited kernel and joins the model's
    `law_homes`.
  - It shares @1's `passive_leak` mask and fields, and the dispatch maps both IDs to the leak
    kernel.
  - It declares `reads=("rapid_binding@1",)` and takes free h at both ends from the closure's stage
    read, which already writes the free ligand × V into the held H row.
  - Its parse check is the ligand row at the route's closure nodes.
- **What admission needs.** "`check_closure_rows` then admits it" fails twice in today's code:
  - `RouteLaw` has no `reads` field. The fix is a defaulted `reads=()`, host-side.
  - `_closure_mover_errors` needs `role_species`, which `passive_routes` lacks, and it resolves
    modes through `cycle_changes`, which raises `TypeError` for anything but a `CycleLaw`.
  - The clean fix is a route-law branch in `species_registry`'s admission (the binding owner's
    file). It admits a route law whose reads name the closure, whose one carried row is the
    closure ligand's base form, and which crosses between its two ends.
- **The same capability as the face's IMS read,** so the two are designed and reviewed together.
- **Bitwise holds under three conditions:** @2 adds no fields, `reads` defaults to `()`, and no
  registered world declares @2.
- **Checks,** as rows in `test_rapid_binding_world.py`:
  - at a general-closure node, @2 is admitted and @1 refused;
  - its flux equals the GHK flux at the closure's free h at both ends;
  - the energy ledger closes with the closure's S_c;
  - @2 equals @1 bit for bit in a world with no closure (about 10–20 s), and the row states
    whether @2 is admitted at B4's nodes;
  - an admission row refuses @2 where its row is not the closure's ligand;
  - the IMS's step at 16 µs with the leak at free h, as a row, or covered by the argument that
    dh/dH_total ≤ 1 keeps B7's charge slope in charge.
- **Price:** 1.5–2 agent-days for the kinds owner, plus about half a day for the binding owner's
  admission branch. That branch may come to the robustness agent under leave.

**4. The forms-aware lag drive.**
- **Today.**
  - The closure's stage check estimates its lag from the node rates by rows, and enters a binder
    row's drive into its base form (`kinds/proton_buffer._general_stage`,
    `laws/reactions/rapid_binding.lag_first_order`).
  - At the ADP step the face brings 92% of its ADP as MgADP. So the row convention reads 1.41 ×
    10⁻³ log10 for the first ~100 µs, above the 1 × 10⁻³ budget, and the step is refused.
  - With the face's moves taken as the forms they are, the worst is 4.0 × 10⁻⁴. That is Step 0's
    development estimate, along a path that includes the IMS kinase.
- **The change:**
  - `lag_first_order` takes an optional species-level drive beside the row drives (the binding
    owner: `proton_buffer.py`, `rapid_binding.py`).
  - The forms face passes its per-form fluxes at the stage to the stage check (the @3 owner: the
    plumbing of `surface_pump_v3._stage_checks`).
  - Every other mover keeps the row convention.
- **Bitwise.** Static: without a forms face the same function runs on the same inputs.
- **Checks.**
  - A row in `test_rapid_binding_kernel.py`: when every move enters its base form, the forms drive
    equals the row drive bitwise.
  - A row in `test_rapid_binding_world.py`: a forms face's step at a bath step stays within the
    budget where the row drive refuses.
- **Price:** about 1 agent-day (the binding owner), plus half a day (the @3 owner).

**5. The capacitor/held-bath parse change: not needed** (item 0).

**The solver.** MT-1b runs on today's ARS(2,2,2) with implicit face electromigration
(`imex_ars222_face_electromigration@1`), the solver its dt ladder ran at 16 µs. It does not declare
N2, because N2 has nothing to move in MT-1b:
- N2 makes @3's own constant-field routes implicit: patch permeabilities, channel populations and
  junctions. MT-1b has none of these.
- Its cycles, its leak and its uncoupler are kinds, which N2 leaves explicit.
- The face's electromigration is implicit already.
So a forms face under N2 can stay refused in version 1, as the face builder plans.

**The order:**
1. items 1 and 2 together (the face path and its bath);
2. item 3, in parallel once the closure read's form is agreed;
3. item 4, after item 1 provides the per-form drive;
4. then MT-1b's worlds and C1's checks.

**Total:** about 7.5–10 agent-days across three owners: item 1 3–5, item 2 about 1, item 3 2–2.5
and item 4 about 1.5 (the @3 and kinds owners' estimates). Each landing is gated, or stacked (D229
rule 2).

**Builder.** A separate face builder works under the @3 owner's leave, and the @3 owner reviews the
seams. The binding lane is unstaffed, so its parts of items 2, 3 and 4 may come to the robustness
agent under leave (the lead's assignment). The kinds owner reviewed item 3 (above).

**Also for MT-1b's worlds** (declaration values, not decisions):
- each species' declared background at or below 1 pM (erratum 2);
- per-species ledger floors suited to the source's activities. On Step 0's world, head 2's floors
  (1 × 10⁻¹⁶ fmol for H) refused a long run ("accounting failed: local"). The parse caps a floor
  at 1 × 10⁻¹⁰ fmol and requires each declared background's floor to equal its row's.

**Flags that would need a decision:**
1. **The leak as a transporter population instead of @2.** Mass action in place of GHK changes Eq.
   19's form, so it would need a G1 erratum.
2. **The ledger floors.** If 1 × 10⁻¹⁰ fmol, the parse cap, proves too tight over 300 s at the
   source's activities, the cap itself is a decision.
3. **A future operator.** A later declaration that adds a capacitance-changing operator would meet
   the composite's floating-component refusal.

## MT-1b's implicit cycle block: the cycles' slopes in N2's operator (design, 22 November 2026)

**Status: a design, before code (D290; D235's branch I for MT-2).** The user chose implicit cycles
to keep ΔΨ at 180 mV with the source's activities. This is more than a day of engine work, so the
note comes first, for the lead and the @3 owner. It builds on N2
(`imex_ars222_implicit_conductances@1`, FR-8 rung 1; its design in `models/surface_pump_v3.py`'s
N2 section, and `validation/long_duration/RUNG1_20261119.md`). **S** marks this note's own proposal.
Read at main 38cc2eae.

**Why.** With the cycles explicit, the electrogenic slope at the source's activity caps the step
near 27 ns at 180 mV, so 300 s costs about 19,400 CPU-hours (the MT-1b draft's W1 table).
- **That figure is a proxy's.** P1′'s arm S scaled FR-4's proton pump until ΣG/C reached the
  source's 5 × 10⁶ /s, and its cap was the pump law's definition-time bound, near rung 0.14
  (CORE_SEAMS_STEP0 §9.2).
- **MT-1b's own cycles are monomial (K6).** The definition-time kind bound
  (`transporter._population_bound_rate`) covers factored kinetics only. The monomial cycles are
  bounded per stage instead: the stage term takes each population's closed-form slope dJ/dψ at
  the stage's potentials (`_population_stage_term`). Step 0 measures their own ΣG/C.

### 1. What N2 does today

- **Each constant-field route** (a patch's own permeabilities, a channel population, a junction) is
  split as J(dv) = W dv + [J(dv) − W dv]. W = dJ/d(dv) is frozen for the step at the tableau's
  operator time, from the step start's prediction.
- **The linear part is implicit.** Its charge current G dv, with G = CHARGE_PER_FMOL Σ_s z_s W_s
  ≥ 0, is a Laplacian block beside the faces' in (C + a dt L) φ = q. One factorization serves the
  step, and the matrix stays SPD.
- **The species move with the same W,** so material and charge stay exact.
- **The remainder stays explicit.** Its derivative in dv vanishes at the operator time.
- **Each part's heat** is booked with its own tableau weights.
- **What N2 leaves explicit.** The kinds' electrogenic currents stay explicit. Under N2 the stage
  rule counts the kinds' terms alone, and the kind and calcium bounds stay (N2's comment). So the
  cycles keep their cap.

### 2. The block

**The split, per cycle population.** For each electrogenic cycle population of `cells.transporter@1`
(complexes I, III and IV, the synthase, the nucleotide exchange):
- its cycle rate is split as J_c(dv) = W_c dv + [J_c(dv) − W_c dv];
- W_c = ∂J_c/∂(dv) is frozen at the same operator time, from the kind's closed-form slope (the
  `d_j_d_psi` its stage term already forms);
- its patch's charge conductance gains G_c = CHARGE_PER_FMOL q_c W_c, where q_c is the charge moved
  per turnover;
- its rows move by ν (W_c dv) at the implicit stages and by ν × the remainder at the explicit ones,
  so material and charge stay exact, as for N2's routes;
- the neutral carriers (q_c = 0) and the kinase have no electrical part, and stay explicit.

**Only the non-negative slope goes implicit (S).** A cycle's slope can be negative: far from
equilibrium, the monomial's voltage factor e^{θqu} can make dI/dV < 0.
- The implicit part takes W_c⁺, the part with q_c W_c ≥ 0, so the operator stays SPD.
- The rest stays in the explicit remainder. The split is exact for any frozen W.
- **The remainder's own rule.** Away from the operator time the remainder's slope is not zero. So
  under the new ID the per-stage rule counts, per population, its stage slope less the frozen
  implicit slope, |q_c (dJ_c/dψ − W_c⁺)| over C. Any definition-time bound on an implicit slope
  (a factored kind's B7 term) likewise counts only the part that stays explicit.

**Its kind hook.** An optional hook, `implicit_slopes(read, potentials, control, p)`, returns W per
population.
- The transporter implements it from its kernel.
- A kind without it adds nothing, so today's kinds and programs are unchanged.

**Heat.** Each part's heat is booked as N2's routes' are: the remainder's at the explicit stages,
the linear part's at the implicit ones. The cycle kind's existing booking (the tableau, or
`trapezoid_nonnegative@1` where picked) applies to each part. The per-element dissipation check
stands.

**Its ID.** A new IMEX ID, as D147 asks of an implicit cycle block: N2 plus the declared kinds'
slopes, `imex_ars222_implicit_kinds@1` (name **S**). N2's own ID is untouched, so FR-8's
registered N2 worlds keep their programs.

**With the face.** The face's forms add Σ_f z_f² W_f to the face Laplacian (the face note's §4). The
cycles add patch conductances. Both sit in the same SPD operator.

### 3. Events, what stays explicit, and the first measurement

**Events (RUNG1's lesson).**
- §7's protocol has scheduled events: the ADP step's two edges, the uncoupler step and the inhibitor
  step. O₂ exhaustion is a continuous world.
- Each event, and t = 0, kicks the fast ΔΨ mode: about 0.2 µs at 180 mV, so dt·ΣG/C ≈ 90 at 18 µs.
- N2's own rung work met this. From t = 0 the dissipation check refused N2's third step. The judged
  N2 arm then ran with C's 1 ms fine window around its cue (RUNG1 §10.13 and §10.20; tags
  `fr8-c-judged-2026-11-20` and `fr8-n2c-judged-2026-11-21`).
- **So the block runs with C's fine windows** (`execution.fine_windows`) at t = 0 and around each
  event. Their width and fine step come from Step 0's ΣG/C.
- The qualification ladder includes an event, with and without its window.


- **Still explicit:**
  - the kinds' material slopes (D4's material term, dt × material ≤ the bound; since 25 November
    2026 a population of the seven laws that move a charged row at both ends gives its whole rate,
    CALCIUM_STORE_AND_CHANNELS_DESIGN §6.3);
  - the face's diffusion: about 18 µs at the source's p_Pi (P1′);
  - the general closure's lag;
  - X2's order condition and its integration-error cap, which registered runs select.
- **The risk (S).** At the source's activity the cycles' material relaxation may bind far below
  18 µs. Candidates are the NADH and quinone pools, the protons through the closure, and the IMS
  kinase at 44 times respiration. Implicit electrical slopes do not lift that.
- **Step 0, with its criterion written first** (development, light CPUs, about half a day to a day):
  - **The world:** head 2's host-P world with the source's capacities, at MR1-MT2's states. The
    worst case is the highest ΔΨ, state 4 at [Pi]e = 10 mM (194.7 mV), beside state 3 at
    [Pi]e = 10 mM (169.0 mV).
  - **What it evaluates:**
    - the monomial cycles' own ΣG/C, from the stage term over C;
    - the material term, the face's bound and the closure's lag;
    - the size of C's windows around an event.
  - **If the material and face bounds allow about 10 µs or more,** this electrical block is enough.
  - **If not,** the block must also take the cycles' material slopes: a linearly implicit material
    block per node, the scope of §8's original branch I. A new estimate goes to the lead before any
    build.

### 4. What stays bitwise (D148), the rows and the qualification

- **Bitwise.** It is a new solver ID that nothing registered selects, so every registered program,
  crossrev set, G1 world, FR set and FR-8's N2 world stays bitwise.
- **Rows (D224),** in the existing `tests/unit/test_n2_implicit_conductances.py`:
  - at every stage, a cycle population's rate equals its frozen-slope linear part plus its
    remainder;
  - material and charge are exact, and the ledgers close;
  - a planted negative slope stays explicit and is counted by the stage rule;
  - a world without slope-declaring kinds runs bit for bit as N2 under the new ID;
  - planted: the linear part's charge without its rows' material move is refused.
- **The qualification**, after the build, on MT-1b's world (development, light CPUs): a ladder from
  1 µs to the binding bound (the face's 18 µs if Step 0 allows), as RUNG1's I3.
  - It measures order against a fine reference, X2's count and cap, and the ledgers.
  - It crosses one scheduled event, the ADP step, with and without C's window.
  - The registration then fixes dt and the windows.

### 5. The price, against the earlier 6–9 agent-days

That earlier figure (§8's M2) was a per-node Newton block. This design reuses N2's linearization,
with no Newton (**S**):

| Part | Agent-days |
| --- | --- |
| Step 0 | 0.5–1 |
| The kind hook and the transporter's slopes at the operator time | about 1 |
| The operator and remainder extension, with the stage rule | 1–1.5 |
| The rows and the gate | about 1 |
| The qualification ladder | about 1 |
| **The electrical block** | **about 4.5–5.5** |
| If Step 0 finds material stiffness binding, the material block on top | 3–4 more (about 8–9 in all, the earlier range) |

**The judged run under this route.**
- **The step's cost** on head 2's world (`/mnt/workspaces/Cells/mito-mt1b-20261122/`, light CPU
  7), as a slope over 300 and 1,500 steps, so each run's fixed cost cancels:
  - 12.5 ms a step on the windowed runner with device row checks;
  - against 6.3 ms for the device step alone;
  - and 170–270 ms with host row checks.
- **So 300 s at the face's 18 µs** (1.7 × 10⁷ steps) is about 58 CPU-hours, about 2.4 days a
  world, detached on a lane, with device row checks.
- That is before X2's two half steps per step, which roughly triple the stepping part (not
  measured).

## MT-1b's world declaration (22 November 2026)

**Status: declared, for the lead's tag.** Both the engine's MT-1b worlds and R2 build from it (the
lead's request, after R2's reading found the laws fixed but no runnable world).
- **Every value has its source or its reason:**
  - the source is Beard (2005), PLoS Comput Biol 1(4):e36, with its 2006 correction, 2(1):e8;
  - both are CC BY, read through `validation/mitochondria/beard2005_cardiac.py`, which keeps each
    number with its place in the source;
  - **S** marks a value this declaration chooses, with its reason.
- The laws are the appendix's at tag `mito-laws-appendix-2026-11-20b`; the outer membrane is the
  face note's (tag `mito-mt1b-face-design-2026-11-22`, option (a)).

### 0. Scale and units

| Quantity | Value | Source or reason |
| --- | --- | --- |
| Mitochondrial volume V_mito | 1 pL, one lumped organelle | **S**: the engine's fmol and pL; every source quantity is per litre of mitochondria, so the scale cancels |
| Matrix water W_x | 0.6435 per unit V_mito: 0.6435 pL | Table 1 (2006), V_x; footnote f, 90% of 0.715 |
| IMS water W_i | 0.0715 per unit V_mito: 0.0715 pL | Table 1 (2006), V_i; footnote f, 10% of 0.715 (the lane's reading note, Q10) |
| Temperature | 298.15 K | D236; the lane's `DECLARED` |
| Inner-membrane capacitance | C_IM = 6.75 × 10⁻⁶ mol (L mito)⁻¹ mV⁻¹, so C = 6.513 × 10⁻¹⁰ F for 1 pL | Table 1 (2006) |
| Outer-membrane area A_OM | γ V_mito = 5.99 µm⁻¹ × 1,000 µm³ = 5,990 µm² | Table 1, γ, per unit mitochondrial volume (Q09) |
| Inner-membrane area A_IM | 6.513 × 10⁻⁸ m², C at 1 µF cm⁻² | **S**: the source gives no area. Only P × A enters the leak, so it scales P alone |

**C_IM is the corrected value.** The 2005 PDF printed 1.0 × 10⁻⁶ (`TABLE_1`'s `printed_2005`), and
the 2006 correction prints 6.75 × 10⁻⁶. So §2.3's 6.75 × 10⁻⁶ is the corrected figure, not an
earlier one.

### G1. The appendix's §12 items

- **The leak (Eq. 19).**
  - The source: J_Hle = X_Hle ΔΨ (H_e e^u − H_x)/(e^u − 1), with u = FΔΨ/RT. That is the
    constant-field (GHK) flux for H⁺.
  - X_Hle = 250.00 mol s⁻¹ mV⁻¹ M⁻¹ (L mito)⁻¹ (Table 1 (2006), with Pi control).
  - **Erratum 2 (item 1):** H_e here is read as the IMS's own free H⁺, h_P (the appendix's §0).
  - The engine: `proton_constant_field_leak@1` on the inner-membrane patch, with P_H A_IM = X_Hle
    RT/F per litre of mitochondria (term by term, **S**). That is 6.423 × 10⁻¹² m³ s⁻¹ for 1 pL, so
    P_H = 9.862 × 10⁻⁵ m s⁻¹ at A_IM (RT/F = 25.693 mV).
- **The uncoupler patch** (§7's step 2; not in the source).
  - A second inner-membrane patch carries only `proton_constant_field_leak@1`, with P_unc A = 30 ×
    the leak's P_H A_IM, and its availability steps 0 → 1.
  - **S:** the factor's purpose is to drop ΔΨ below the synthase's stall so that synthesis reverses,
    which is §7's test. R2 reports the uncoupled plateau's ΔΨ against the stall before
    registration. If ΔΨ stays above the stall, the factor rises before registration.
  - **The reversal's readout: for the lead.** With the bath's ATP at its trace, the matrix adenylate
    pool is conserved and the exchange is 1:1. So at the uncoupled steady state the synthase's net
    flux is about zero at any factor, and its sign is the trace's. Two ways:
    - (i), proposed: give the uncoupler branch the inhibitor branch's bath, the source's ATP buffer
      (ADP 0.5 mM, ATP 0.87 mM; G7). The reversed synthase then runs at a steady plateau;
    - (ii): read the reversal on the transient: the synthase's sign, and its integrated reverse
      turnover, over the seconds after the step.
- **The matrix buffer.**
  - The source: 1/r_buff = (100 M⁻¹)[H⁺]_x (text after Eq. 22; `BUFFER_PER_M`). That is a buffering
    capacity of ln 10 / (100 M⁻¹) = 23.03 mM per pH unit at every pH (**S**).
  - **The engine's closure holds one-site buffers,** so the matrix declares one buffer row B_x under
    the closure, with pK 7.10 and total 40.0 mM. That total gives the source's 23.03 mM per pH at
    the pK (**S**).
  - The operating matrix pH is 7.07–7.14 at MR1-MT2's twelve states. Within 0.1 pH of the pK the
    capacity is 98.7% of the source's, 89.0% within 0.3 and 73.0% within 0.5.
  - This is a declared departure from the source. R2 integrates the same buffer, so the judged
    comparison does not see it; MT-2 reports it.
- **The IMS buffer: none.** The source holds [H⁺]_i = [H⁺]_e (text after Eq. 21). The IMS's pH
  follows the bath through the face's H⁺ (G4), and the IMS closure binds H⁺ on phosphate only.
- **Passive K⁺ (Eq. 20): absent,** since X_K = 0 in both columns (Table 1).
- **Passive Mg²⁺ across the inner membrane: absent.** The source's fits set the passive K⁺ and
  Mg²⁺ fluxes to zero (`PROTOCOL`), so the matrix Mg²⁺ total is conserved at 5 mM (D236).

### G2. The water volumes

- W_x = 0.6435 and W_i = 0.0715 per unit of mitochondrial volume. Both are Table 1's own values
  (2006), not only the 90/10 split.
- With W_i, the face's explicit bound at p_Pi is 1/(2 γ p_Pi / W_i) = 18.3 µs, P1′'s figure.

### G3. The held bath

**Its composition** is the source's protocol (`PROTOCOL`):
- **Free pH 7.10 held:** the free proton concentration is held at 10^−7.1 M, not a proton total
  (the lead's ruling). No bath buffer is needed for a held free proton.
- **K⁺:** 150 mM.
- **Mg²⁺:** total 5.0 mM. Its free part is solved at the bath's speciation (option (a)).
- **Pi total: 10 mM.**
  - **S:** that is the top of the source's 0–10 mM sweep, and the Pi of MR1's ADP-step time
    course.
  - One Pi keeps R2's world and the engine's single. Other Pi values are later worlds.
- **ADP:** 1.3 mM in state 3 (the source).

**Traces** (**S**), where the source has exactly zero: ADP, ATP and AMP at 1 nM (10⁻⁶ mM) each.
**Erratum 2 (items 2 and 3):** they are 1 pM, checked against 1 fM; concentration bands have
absolute floors.
- At exactly zero a form's potential is −∞ and the energy ledger is undefined.
- 1 nM is positive and small against every saturation constant: k_mADP = 3.5 µM, K_MgATP = 24 µM.
- **R2 checks it before registration:** the same run with traces 1,000 times smaller must move no
  judged readout by more than a tenth of its band. Otherwise the trace falls before registration.

### G4. The outer membrane for the free ions

- **The source:** H⁺ and K⁺ "rapidly equilibrate across the outer membrane", with [H⁺]_i = [H⁺]_e
  and [K⁺]_i = [K⁺]_e (text after Eq. 21). The IMS's free Mg²⁺ is no state in the source (Q26), and
  MR1 holds it at the buffer's free Mg²⁺.
- **Declared (S):** free H⁺, K⁺ and Mg²⁺ cross the face as log-mean electrodiffusion at
  p = p_Pi = 327 µm s⁻¹, the source's fastest outer-membrane permeability.
  - Their equilibration time, W_i / (γ p), is 36.5 µs, far below every readout's time scale. So
    the IMS should sit at the bath's free H⁺, K⁺ and Mg²⁺, as the source assumes.
  - That is asserted, not shown: phosphate's forms carry most of the protons across. R2 reports
    pH_P and the outer membrane's potential at every plateau.
  - No faster permeability is introduced, so the face's step bound stays P1′'s 18.3 µs.
- **No counter-ion crosses (S).** The source has no Cl⁻. The bath and the IMS carry the fixed
  charges that balance their declared ions at the start (the engine's fixed-charge equivalents).
  The outer membrane's potential then follows G5.

### G5. The outer membrane's potential

φ_IMS − φ_bath is set by zero net outer-membrane current (the lead's ruling), over the permeant
forms and ions. The outer membrane carries no capacitance. The face note's §6 carries an erratum
pointing here.
- **A parse check for the build.** The matrix and the IMS form one capacitor component with no
  held bath, since the face to the bath is no capacitor.
- The composite's field refresh has required a held bath in every component (the floating-component
  checks of 21 November). So the build's first parse of MT-1b's world checks it.
- If it is refused, the floating component's offset solve (the field's own, with fix (A)'s scope)
  is the place G5's condition goes.
- **Erratum (22 November 2026): the start state's seventh conserved quantity.** R2's author found
  it; the rule is the lead's ruling.
  - **The finding.** G5 (zero net outer-membrane current) with G4 (no counter-ion) conserves a
    seventh quantity: the matrix-plus-IMS row charge, I_NP = W_x Σ_N z c + W_i Σ_P z c. G7 anchored
    only I_N, the matrix's charge inventory, so the start state was underdetermined. Different
    choices of I_NP move it by tens of ΔΨ bands.
  - **The rule.** I_NP is set by zero outer-membrane potential at the anchor state ([Pi]e → 0,
    pH_x = 7.1418) and again at the start state ([Pi]e = 10 mM). Each IMS sits at its own bath's
    free ions, as G4 intends and the source assumes.
  - **Its consequence within the protocol, stated for the registration.** I_NP is conserved, so the
    IMS's row charge follows C_IM·ΔΨ. Per 10 mV of ΔΨ that is about 0.94 mM in W_i, about 0.7 mM
    of it in K_P, and about 0.1 mV of outer-membrane potential. It is a modelling consequence of
    "no counter-ion".
  - **A check, not an input.** R2's anchor value is I_N = 0.0851185587 mol (L mito)⁻¹. The engine
    computes its own start state from this rule, never from R2's numbers. This replaces G7's "R2
    records the numbers, and the engine starts from them".

### G6. O₂ at N

- **The source:** 2.6 × 10⁻⁵ M (20 mmHg, as it states it for the matrix; `PROTOCOL`), held in
  worlds (a)–(c), C1's default.
- **"Held" at the matrix has no engine mechanism yet. It is open for the build:**
  - (i): complex IV's population holds O₂, if its law admits a held row;
  - (ii), proposed (**S**): O₂ in the held bath at 26 µM, supplied through the face at p_Pi and
    across the inner membrane by `passive_neutral_permeation@1` at P_O₂ = 9.9 × 10⁻⁵ m s⁻¹ (P A =
    6.4 × 10⁻¹² m³ s⁻¹ at A_IM). It equilibrates in about 0.1 ms. Its explicit bound at the
    matrix, 1/(2 P A/W_x), is about 50 µs, above the face's 18.3 µs.
  - **(ii)'s cost.** At the state-3 O₂ flux (1.64 fmol s⁻¹ per pL) the matrix O₂ sits about
    1.1 µM, 4%, below the bath's: 0.84 µM across the face and 0.26 µM across the inner membrane.
    Complex IV's O₂ factor, 1/(1 + k_O₂/[O₂]), then reads about 3.5% lower.
    - R2 takes the same supply, so the judged comparison does not see it.
    - Against the source's held 26 µM it is a declared departure, which MT-2 reports.
    - (i) avoids it, if complex IV's law can hold O₂.
- W3(d) makes it finite (G7).

### G7. The protocol (§7)

**Against the source.** The source fits steady states only: Bose et al.'s states 4 and 3 at
[Pi]e 0–10 mM, and the low-O₂ sweep. It reports no transient, so every time below is ours.
- R2's plateaus are of the order of MR1's ADP-step course (`reproduce.adp_step_time_course`: from
  state 4, ADP on for 60 s, then off for 120 s).
- Its 60 s and 120 s plateaus carry no claim from the source. The drift rule decides them.

**Accepted from R2's proposal, with what this declaration adds:**

| Item | Declared | Source or reason |
| --- | --- | --- |
| Start state | R2's steady state 4 at [Pi]e = 10 mM, at the declared inventories: the matrix Mg²⁺ total 5 mM (D236), and the matrix charge inventory anchored as MR1-MT2's, to pH_x = 7.1418 at state 4, [Pi]e = 0 (`mr1_mt2_registration.json`, `charge_inventory_definition`), but computed with G1's buffer. R2 records the numbers, and the engine starts from them. **Erratum (G5):** I_NP is set by zero outer-membrane potential at the anchor and start states, and the engine computes its own start state from that rule; R2's numbers are a check | **S**; MR1-MT2's anchoring |
| State 4 | 0–60 s | R2 |
| ADP step | 1.3 mM total in the bath, 60–180 s | the source's ADP; R2's times |
| Back to state 4 | the ADP trace, 180–300 s | R2 |
| The uncoupler (step 2) | a branch from the 300 s state: the uncoupler patch on (G1), 120 s | R2's branch; §7 |
| The inhibitor (step 3) | a branch from the 300 s state: complex IV's availability 0, and the bath switched to ADP 0.5 mM with ATP 0.87 mM, 120 s | §7. The bath is the source's only buffer carrying ATP, its low-O₂ cytochrome c protocol (`PROTOCOL`): the reversed synthase and exchange spend that ATP |
| Branches | each judged at matching times since its own start from its own 300 s state | **S** |
| Outputs | every 10 ms for 2 s after each step, then every 0.5 s | R2 |
| Drift rule | a plateau counts as steady when every judged readout changes by less than a tenth of its band over its last 10 s. R2 reports whether each plateau meets it; one that does not lengthens before registration | **S**, the MT-1b draft's drift rule made concrete |
| Control (b) | the uncoupler patch on from t = 0; otherwise (a)'s schedule | §7's controls |
| Control (c) | the nucleotide exchange's availability 0 from t = 0; otherwise (a)'s schedule | §7's controls |

**W3(d), O₂ exhaustion.** The held bath stays held for every row but O₂, which lives in its own
finite node.
- **The O₂ node:** O₂ only, 6.3 nL per pL of mitochondria, starting at 26 µM.
- **The route:** a face from the O₂ node to the IMS at p_Pi, and the inner membrane at G6 (ii)'s
  P_O₂.
- **The run:** from the state-4 start, ADP stepped to 1.3 mM at 60 s and held, to 240 s.
  **Erratum 2 (item 4):** depletion starts at 60 s; the window with matrix O₂ below 0.37 nM is
  excluded from scoring; the P50 crossing is expected near 160.4 s, not near the run's end.
  **Erratum 3:** the window is re-derived on the O₂ flux (opening near 195.8 s), and the collapse
  from the P50 crossing to the window takes transient bands.
- **Outputs:** as G7's, every 10 ms for 2 s after the step, then every 0.5 s.
- **Why 6.3 nL (S):** at MR1-MT2's state-3 O₂ flux, 1.640 × 10⁻³ mol s⁻¹ (L mito)⁻¹ at [Pi]e
  10 mM, that holds about 100 s of O₂. The matrix O₂ then falls through the source's P50 of
  0.373 µM near the run's end.

**Cytochrome c.** cytC_tot = 2.70 mM is the concentration that complexes III and IV read at P
(appendix §1.2–1.3 and §9; head 2's world holds 2.7 mM at the lumen). So the IMS holds 2.70 mM in
its 0.0715 pL, 0.193 fmol, and its rows' changes divide by W_i.
- That is MR1's V_i switch (Q05). MR1's published arm divides by V_x instead.
- Steady states do not depend on it, but transients do. R2 takes W_i as the engine does, and MT-2
  reports the difference from the published arm.

### Erratum 2 (22 November 2026): R2's findings, the lead's rulings

R2, built at `mito-refs-r2` 0edb4c97, found five things. Its README has the details. The lead ruled
on each, and this erratum states the rulings. R2's numbers serve only to check this erratum's
predictions. The engine computes its own start state, as before (G5's erratum).

1. **G1's Eq. 19: the leak and the uncoupler read the IMS's own free H⁺.**
   - Both read h_P on the P side, per the appendix's §0 ("Here every P-side quantity is the IMS's
     own"). They do not read the bath's H_e, which G1 prints.
   - It matters where the IMS departs from the bath. At the uncoupled plateaus pH_P sits
     0.009–0.019 above the bath's 7.10, so there the two readings differ by 2–4%.
   - **In the engine (S):** at a general-closure node, `proton_constant_field_leak@1` must read the
     IMS closure's free h. Today that law is refused there: as a route law it declares no reads.
     That capability is designed with the outer-membrane face, which needs the same closure reads,
     and the kinds and binding owners review it. No erratum to G1's law is needed unless that proves
     impossible.
2. **Traces at 1 pM, with the error control relative down to the smallest trace.**
   - ADP, ATP and AMP sit at 1 pM (10⁻⁹ mM) where the source has zero; they were 1 nM (G3).
   - R2's concentration floor (1 × 10⁻⁹ M) scales with the trace, so its error control stays
     relative down to the smallest trace: 1 pM in the run of record, 1 fM in the check's arm.
   - The trace check is 1 pM against 1 fM, judged as before: no judged readout may move by more
     than a tenth of its band. At 1 nM it failed, at 1.39 bands.
   - **In the engine (S):** each species' declared background (`trace_mM`) is set at or below 1 pM.
3. **An absolute floor on every concentration readout's band:** band = max(relative band, absolute
   floor).
   - **The floor is 0.1% of the readout's pool, its declared total:**
     - ATP_N and ADP_N: 10 µM (A_tot = 10 mM);
     - Pi_N: 10 µM (the bath's 10 mM);
     - K_N: 0.15 mM (the bath's 150 mM);
     - the IMS's adenylates, wherever they are judged: 1.3 µM (the bath's 1.3 mM ADP).
   - **The reason is the band's own basis (S).** The 0.1% band is a third of one pixel on a figure's
     axis, and an axis that plots a concentration spans its pool. So the resolution it encodes is
     absolute, a fraction of the pool. As a relative band it understates that resolution when the
     readout falls far below the span, as a depleted pool does.
   - **Where that bit:** R2's development check (1 pM against 1 fM) found relative bands on a
     depleted matrix ATP still failing, and a lower trace does not help:
     - (a)'s inhibitor branch: ATP_N near 6 µM at 307.5 s, 0.16 band;
     - (d): ATP_N near 6.8 µM at 178 s, 0.41 band.
   - The floor is set by the band's basis, not to pass that check. R2's rerun reports the moves
     against the floored bands.
4. **W3(d), O₂ exhaustion.**
   - **Depletion starts at 60 s,** so 0–60 s is a true state-4 plateau.
     - With the node finite from t = 0, R2 found that segment failing the drift rule by 14 times,
       and lengthening could not fix it. With depletion from 60 s, R2's development check finds it
       meeting the rule.
     - The mechanism is the build's (**S**): for example, the node held at 26 µM until 60 s, then
       finite.
   - **The O₂ window: excluded while the matrix's free O₂ is below 10⁻³ × P50, 0.37 nM.**
     (Superseded by erratum 3: the reason below fails at this threshold.)
     - It reads the O₂ that complex IV reads, at N (G6).
     - While it is open, every judged readout of world (d) is excluded from scoring and reported.
     - **The reason:** below P50 the O₂ flux is first order in O₂, so there it falls under 0.1% of
       its state-3 value: the flux band's own absolute floor, by item 3's rule.
     - In the anoxic tail the O₂ is about 5 × 10⁻¹⁴ M. There a relative band on a vanishing
       readout fails at any trace: the O₂ flux still moved 0.72 band at 1 pM against 1 fM.
   - **The expected P50 crossing (S): about 160.4 s.**
     - With depletion from t = 0, R2 saw the matrix O₂ cross 0.373 µM at 153.3 s.
     - Starting depletion at 60 s returns the O₂ that state 4 used over 0–60 s: 60 s × 1.93 ×
       10⁻⁴ mol s⁻¹ (L mito)⁻¹. At the state-3 flux of 1.640 × 10⁻³, that is about 7.1 s.
     - So the crossing is expected near 160.4 s, not near the 240 s end that G7 assumed. R2's
       development check found about 160.5 s.
5. **I_NP's consequences, as R2 observed them** (G5's erratum states the rule):
   - the outer membrane's potential ranges from −0.54 mV (control (c), state 3) to +1.15 mV
     (control (b));
   - the IMS's K⁺ ranges over 143–153 mM;
   - in control (c), with the exchange off, the bath's ADP gathers in the IMS and pH_P falls to
     7.091 at state 3, since the IMS must keep its charge.
6. **A reported feature, not scored.** The uncoupled plateau's ΔΨ, 100.89 mV, sits 0.37 mV below
   the synthase's stall at its concentrations (101.26 mV), and the synthase runs reversed: J_F1 =
   −2.6 × 10⁻⁴ mol s⁻¹ (L mito)⁻¹. The margin is small; the reversal is not. MT-1b reports it and
   does not score it.
7. **Where the judged comparison's weight sits.**
   - Most plant catches in R2's checks sit on fragile places: the depleted pools and the anoxic tail.
     Items 3 and 4 now keep those places from deciding a verdict.
   - The robust catches are P-c, on cytochrome c's reduced fraction, and P-b, mainly on ΔΨ's
     transients.
   - So the judged comparison rests on:
     - ΔΨ, at the plateaus and in the transients;
     - cytochrome c's reduced fraction, NADH's fraction and pH;
     - the O₂ flux outside the window;
     - the concentration readouts only above their floors.

### Erratum 3 (22 November 2026): the O₂ window's criterion and the anoxic collapse

R2's window check on its run of record (world (d)) found that erratum 2's stated reason for the O₂
window does not hold at its threshold. This erratum re-derives the window and declares how the
anoxic collapse is judged. Each reason is stated in advance, not chosen to pass; R2 re-scores with
these rules (`rescore.py`, no rerun).

1. **The finding.**
   - At 10⁻³ × P50 (0.373 nM, t = 189.20 s in R2's world (d)), the O₂ flux is 7.07 × 10⁻⁶ mol s⁻¹
     (L mito)⁻¹. That is 0.43% of the state-3 flux (1.638 × 10⁻³), not 0.1%.
   - The flux falls to 0.1% only near O₂_N ≈ 0.10 nM (2.7 × 10⁻⁴ × P50), at t ≈ 195.8 s.
   - **Why:** by then cytochrome c is fully reduced (0.213 → 1.000) and ΔΨ has collapsed (168.6 →
     37.6 mV), and both raise complex IV's forward term. Complex IV's law also carries [O₂]^¼ beside
     1/(1 + k_O₂/[O₂]) (k_O₂ = 120 µM). So near zero O₂ the flux is not first order with the
     state-3 coefficient, and erratum 2's derivation of 0.37 nM fails.
2. **The window, re-derived on the flux itself.** World (d)'s judged readouts are excluded from the
   time the reference's O₂ flux first falls below 0.1% of its state-3 value, to the run's end.
   - **The reason** is erratum 2's item 3: 0.1% of the state-3 flux is the flux band's absolute
     floor, below which the flux is under its own resolution. Defined on the flux, the window's
     reason holds by construction, whatever the flux's order in O₂.
   - **The time** is fixed at registration from the reference alone: about 195.8 s in R2's run of
     record (O₂_N ≈ 0.10 nM). The engine is scored up to the same time.
   - It replaces erratum 2's O₂ threshold (0.37 nM) and its reason.
3. **The anoxic collapse is a transient, judged with transient bands.**
   - **Onset:** the matrix O₂ crosses P50 (0.373 µM), the source's own half-maximal point, where
     respiration turns O₂-limited (t ≈ 160.5 s in R2). **End:** the window's opening.
   - **Bands:** the registration's transient rule (the draft's tolerances): a tenth of each judged
     readout's excursion over the collapse, fixed from the reference alone. For ΔΨ, 135.7 mV at the
     onset and 33.4 mV at the window in R2, so its band is 10.2 mV.
   - **The reason:** during the collapse the readouts move fast. Near 189 s ΔΨ falls at about
     1.1 mV s⁻¹.
     - So the plateau band (0.05 mV) there judges a shift of about 45 ms in the collapse's timing.
     - The trace check's 0.245 band at t = 189.0 s (37.840 against 37.827 mV) is a shift of about
       12 ms.
     - A plateau band on a transient judges timing at a resolution the protocol registers for no
       readout. The transient rule is the registration's own, so no new parameter enters.
   - **Why score the collapse rather than exclude it:** it keeps the O₂ law's plant, P-c (the 2005
     k_O₂), on judged rows. R2's re-scoring reports whether P-c still misses by at least 3 bands
     under these bands, as the plant rule requires before registration.

### R2's readings, confirmed or corrected

| R2's reading | Verdict |
| --- | --- |
| The "with Pi control" column | **Confirmed:** the source's final model (Eq. 24), the appendix's column |
| The binding table | **Confirmed** (appendix §0): Mg²⁺ on ATP and ADP, H⁺ on phosphate, nothing on AMP, no Mg²⁺ on phosphate. Add G1's matrix buffer B_x |
| Eq. 20 absent | **Confirmed:** X_K = 0 in both columns |
| ΔΨ free | **Confirmed:** C_IM dΔΨ/dt follows the net charge current; nothing clamps it |
| The face law J_f = γ p [(c_e − c_P) + z_f v L_f] | **Confirmed,** with L_f = logmean(c_f,e, c_f,P) and v = F(φ_e − φ_P)/RT. It is positive into the IMS, per unit mitochondrial volume. It equals the engine's log-mean electrodiffusion with D A/L = γ p V_mito, and the free ions of G4 take the same form |
| Option (a)'s supply at the free potentials | **Confirmed** (the lead's ruling): a binder row's supply at its free base's μ̃, a ligand row's at its free ligand's μ̃ |
