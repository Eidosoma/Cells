# Gene regulation as physics: design, and options for the first milestone

*Status: proposed, 20 November 2026, for the lead and the advisor, then the user (D234 item 2).
Desk work only: no engine code and no runs. Written on branch `gene-regulation-design` from main
f85d8f3e, where the code was read; code is cited `file`:line under `src/cells/` at that revision.
The core-laws roadmap is cited from its branch, `core-laws-roadmap` at 5662b28f, which is not on
main. Tags: **(code)** read in the code; **S** this note's own reading, arithmetic or proposal;
**(estimate)** this note's rough agent-days; **(checked)** a reference, number or licence read
for this note on 19–20 November 2026 (Sources); **named from memory, not read** a classical
reference not re-read for this note.*

**Engine models it runs** (AGENTS.md): none, since it is a design note. Each option in §4 names the
models its milestone would run.

**What is asked.** D234 item 2: "Gene regulation begins with a design note. D145's hold is lifted
for the design: transcription and translation as physics, regulatory networks as declared laws,
and how they are verified. Its options come to the user before any engine code is written. D218's
door is unchanged until then."

**Basis.**
- The core-laws roadmap's Family 7 (gene expression), Family 8 (metabolism), §1.4 and §1.5.
- D145, D179, D209 (machines' U4), D217, D218, D224, D228 item 7 and D234.
- [GRN_WETLAB_VALIDATION.md](GRN_WETLAB_VALIDATION.md), [INVENTORY_COUPLING_DESIGN.md](INVENTORY_COUPLING_DESIGN.md)
  and [ABUNDANCE_TO_FUNCTION_DESIGN.md](ABUNDANCE_TO_FUNCTION_DESIGN.md) (FR-7).
- The Syn3A track: [SOTA_SYN3A.md](SOTA_SYN3A.md) and [SYN3A_MINIMAL_CELL_TRACK.md](SYN3A_MINIMAL_CELL_TRACK.md)
  (F8–F11).
- [MOLECULAR_MACHINES_DESIGN.md](MOLECULAR_MACHINES_DESIGN.md), and
  [MEMBRANE_RETRIEVAL_DESIGN.md](MEMBRANE_RETRIEVAL_DESIGN.md) §3.4, the fuel coupling.
- [ARCHITECTURE.md](ARCHITECTURE.md)'s modular core, and AGENTS.md.
- The code of the building blocks, read at f85d8f3e.

**Contents.** §0 in short. §1 gene regulation as physics. §2 architecture. §3 the low-copy regime.
§4 options for the first milestone, and the recommendation. §5 consumers. §6 the user's decisions.
Sources.

## 0. In short

1. **Production is templated polymerisation** (§1.1).
   - Transcription and translation are chemical reactions run residue by residue, by finite
     machines, on a template. Each residue consumes a monomer and fuel. Each product appears after a
     delay set by its length and the machine's speed.
   - One kernel on main already has that material shape: FR-7's unit producer,
     `population_unit_turnover@1`. It turns a precursor into units through an exact chain of delay
     pools, at ν precursor molecules per unit.
   - The first new piece generalises it. It needs a soluble product with a free energy, a machine
     pool that is occupied while it works, monomers and fuel drawn along the chain, and turnover that
     returns the monomers (§2.2).
2. **Promoter occupancy is binding** (§1.3).
   - Four blocks on main can carry it:
     - B1′'s Hill factor of a species, the all-or-none equilibrium, which cannot express titration;
     - the rapid-equilibrium closure `rapid_binding@1`, whose binding polynomial is the
       thermodynamic model of transcription regulation;
     - the regulatory state `hill_regulated_two_state@1`, which is kinetic and is already B1′'s
       source, but sequesters nothing;
     - `site_occupancy@1`, which is kinetic, conserving and judged, but hosted on patches and
       contacts only.
   - The choice turns on whether bound transcription factor must leave the free pool.
3. **A regulatory network is a declaration, not code** (§1.4).
   - Its laws are general: Hill factors, occupancy, two-state kinetics and templated synthesis.
   - Its genes, regulators and wiring are data in the definition. No law is named for a protein
     (D144).
   - Abstract and Boolean networks stay outside the engine, as references (D137, D138).
4. **One account** (§1.5).
   - The polymer is a species row with a standard potential per residue. So every stage books an
     exact ΔG, and its heat is checked to be non-negative.
   - Fuel enters as the polymerisation's own stoichiometry. That is the common energy interface's
     rule for reactions (MEMBRANE_RETRIEVAL §3.4). The machinery's other costs wait for seam E's fuel
     block (D217).
   - Nucleotides and RNA are polyanions. Version 1 would declare them as neutral formula units, as
     FR-10 does, and say so.
5. **Where each entity lives decides most of the rest** (§2.1).
   - Species rows hold what other mechanisms read or move: regulators, monomers, fuel and products.
   - Operator-owned pools hold the machines and the elongating complexes. Counts may reach zero
     there, and they cost no row.
   - The gene is declared template data.
6. **The low-copy regime** (§3).
   - The deterministic aggregate is the exact mean of a first-order network driven by given inputs.
     So an open-loop expression chain is exact in expectation at any copy number.
   - Feedback, bimolecular steps at low copy and bistability are not.
   - A stochastic regime needs count state, keyed streams, event semantics inside the composite's
     step, hazard integration for two-way coupling, and GARD's guard for stochastic laws.
   - The assembly family has the exact kernel and the keyed streams. The composite has neither.
7. **Four options for the first milestone** (§4):
   - **A,** the expression unit: one gene, open loop, deterministic;
   - **B,** promoter occupancy as binding, judged on the simple-repression input–output;
   - **C,** the low-copy regime first;
   - **D,** a network with feedback: delayed autorepression, with the EMT switch on the same laws.

   **Recommended: A,** with its first acceptance numerical against code-blind references, and its
   biological comparison registered separately (§4.6).
8. **Consumers** (§5): the heredity work's expression carrier, Syn3A's Stage 4 (F10 and F11), the
   Xenopus lane's mediator-to-expression path, the gap-junction replication's F6, the REVERT plan's
   group 2, FR-7's precursor, and machines' U4.
9. **The user's decisions** (§6): which part of D145's hold to lift; whether D218's door covers
   transcription-factor feedback; fuel; the one route from state to production; data licences.
10. **Effort (estimate):** A about 9–13 agent-days; B 9–14; C 14–22; D 6–9 on top of A.

## 1. Gene regulation as physics

### 1.1 Production is templated polymerisation

**Transcription.**
- RNA polymerase reads a DNA template and adds one nucleotide per step:
  NTP + RNA_n → RNA_{n+1} + PPi.
- Pyrophosphatase hydrolyses the PPi to 2 Pi, which makes growth practically irreversible. The
  textbook biochemistry is named from memory, not read.

**Translation.**
- The ribosome reads the mRNA. Each amino acid is first activated, aa + ATP → aa-AMP + PPi, and
  then loaded onto its tRNA. Each elongation cycle spends two GTP, at EF-Tu and EF-G.
- The chain-elongation costs, in ATP equivalents, are 2 per nucleotide for transcription and 4 per
  amino acid for translation. Making the monomers costs far more: about 45 per ribonucleotide and
  about 30 per amino acid (Lynch and Marinov 2015, **(checked)** through the authors' own summary;
  the article itself was not read).

**Turnover.**
- mRNA is degraded to NMPs, which kinases recharge with ATP.
- Proteins are degraded to amino acids. In eukaryotes the proteasome spends ATP: 50–160 per
  ubiquitinated substrate (Peth, Nathan and Goldberg 2013, as MOLECULAR_MACHINES §10.3 read it).

**Machines.**
- An elongating polymerase or ribosome is occupied for the chain's whole duration, L/v.
- So machines are a finite capacity: free plus engaged is the total, and genes compete for it.

**Delays.**
- From initiation to a finished product takes L/v, plus processing and export in eukaryotes.
- A deterministic aggregate represents it as m first-order stages: the linear chain trick that
  FR-7's producer uses (MacDonald 1978, as the producer cites it). The dwell is Erlang, with mean
  L/v and variance (L/v)²/m. Large m approaches a fixed delay.

**Scales, as orders of magnitude.**

| Quantity | Value | Source |
| --- | --- | --- |
| *E. coli* RNA polymerase, mRNA | 40–55 nt/s | Bremer and Dennis, through BioNumbers; the chapter itself not read |
| *E. coli* RNA polymerase, rRNA | about 85 nt/s | Dennis et al. 2009, through BioNumbers; not read |
| *E. coli* ribosome | about 12–21 aa/s | Bremer and Dennis, through BioNumbers; not read |
| Mouse fibroblasts (NIH3T3): median mRNA and protein half-lives | 9 h and 46 h | Schwanhäusser et al. 2011 **(checked)** |
| The same: median copies per cell | mRNA 17; protein 50,000 | The 2013 corrigendum's corrected values **(checked)** |
| Mammalian reporter mRNA half-life | about 4 ± 1 h | Raj et al. 2006 **(checked)** |
| *M. pneumoniae* protein half-lives | 488 proteins, per protein | Burgos et al. 2020, Table EV1 **(checked)** |

**What the physics fixes, and what stays data.**
- **Physics:** the stoichiometry per residue, the residues conserved from monomer to polymer and
  back, the machines conserved, and the free energy per residue.
- **Data, with evidence records:** initiation rates, promoter strengths, elongation speeds,
  lifetimes and copy numbers.

**What this layer is not.**
- Not protein folding (D140).
- Not abstract regulatory modules: "The abstract regulatory modules stay out of the engine. Only
  claims with a physical mapping are tested" (D137).
- Not a network fitted to the data it then reproduces (GRN_WETLAB_VALIDATION's warning).

### 1.2 Turnover of mRNA and protein

- **Degradation is first order, and it returns monomers.** mRNA goes back to NMPs and protein to
  amino acids. Each removal is booked as a move between rows, with its exact ΔG.
- **There is no dilution by growth, because Cells has no growth yet (MG3).** In a non-growing cell
  a stable protein's level is set by degradation alone. Bacterial proteins whose loss is mostly
  dilution need a declared degradation, or growth first. Many of Burgos et al.'s fitted rates sit
  at the dilution rate (SYN3A_MINIMAL_CELL_TRACK §3.1).
- **What exists today (code).**
  - D150's clearance removes a species with no material return: "Its real metabolic cost
    (synthesis, proteolysis) lies outside the modelled inventory, a declared limit"
    (`operators/species_turnover.py`:27–28).
  - FR-7's producer removes units into a sink. "The units carry no free energy in the model"
    (`operators/population_unit_turnover.py`:62).
  - So neither returns material.
  - D152's driven mass action could return them: one polymer to L monomers is order 1, and products
    are not capped (`operators/species_reactions.py`:544–548). But a driven route books its ΔG as
    signed work, not as the heat of a downhill hydrolysis (S). Degradation that returns monomers
    and books heat is new.

### 1.3 Promoter occupancy as binding

**At equilibrium: the thermodynamic model.**
- A promoter's states s have statistical weights w_s = Π_L (c_L/K_{L,s})^{n_L,s}. The fraction of
  time in the active states is Σ_active w_s / Σ_s w_s. Shea and Ackers 1985 couple such
  statistical-thermodynamic probabilities to synthesis in phage λ's O_R system **(checked**,
  abstract); Bintu et al. 2005 generalise the form (named from memory, not read).
- **`rapid_binding@1` computes exactly this.** Its binding polynomial,
  P_B = Σ_f exp(ln β'_f + Σ_L n_{L,f} ln x_L), is that partition function. The registry declares
  each form's standard potential, from which β follows (`laws/reactions/rapid_binding.py`:11–17;
  `registry/species_registry.py`:28–38) **(code)**.
- **It conserves the ligand.** The free transcription factor is what the binders leave. So titration
  by many sites, or by decoys, follows from the closure as it stands. Reading its result into a rate
  is the one new piece (§2.3).
- **Non-specific DNA as a second binder gives the classic weak-promoter form (S).** With R
  repressors, N_NS non-specific sites and a binding energy Δε of the operator relative to
  non-specific DNA, the fraction repressed is w/(1 + w), with w = (R/N_NS) e^{−Δε/k_BT}. The
  expression left is 1/(1 + R/K_eff), with K_eff = N_NS e^{Δε/k_BT}: a Hill inhibition with n = 1
  in total R (named from memory, not read). So the same form also runs through B1′'s Hill factor,
  as long as titration does not matter.

**Kinetic: the two-state (telegraph) promoter.**
- The mean occupancy of a single promoter, with c(t) given, obeys ds/dt = k_a c (1 − s) − k_d s
  exactly. Occupancy is exact in expectation for identical, independent sites in a given
  environment (MOLECULAR_MACHINES §3.1, point 1).
- **`hill_regulated_two_state@1` is this law only where c is much less than K.** Its on-rate is
  k_on u (1 − s), with u a product of Hill factors in [0, 1]
  (`operators/species_regulated_availability.py`:27–30) **(code)**. With n = 1, u = c/(K + c) ≈ c/K
  is mass action. Beyond that, the saturation in u is a different mechanism (S).
- `site_occupancy@1`'s Langmuir law, J = m_b [k_on c R − k_off B], is mass action with the sites
  conserved. Seam C names it the detailed representation of the same mechanism, and the closure its
  rapid limit (CORE_SEAMS §5.3).

**The four blocks against a promoter.**

| Block | Equilibrium or kinetic | Bound factor leaves the free pool | Host | Status on main | What a promoter would need |
| --- | --- | --- | --- | --- | --- |
| B1′'s Hill factor of a species (`hill_activation`, `hill_inhibition`) | Equilibrium, all-or-none | No | A rate route on any routable target | `@1` judged for channels and junctions; `@2`'s rate routes are development | Nothing for the weak-promoter form. It cannot express titration |
| `rapid_binding@1`, the closure | Equilibrium | **Yes** | A node, through a kind | Compared, not judged. "No built-in law moves a closure row" (roadmap, Family 4) | First, seam C's mover rule. Today a row with forms stays inert: any operator that names it is refused, the coupling's reads included (`species_registry.py`:783–813) **(code)**. Then an operator's read of a form fraction. A ligand may not have forms of its own (`species_registry.py`:36), so a repressor bound by an inducer cannot also be a promoter's ligand |
| `hill_regulated_two_state@1`, the regulatory state | Kinetic | No | One state per cell | Judged within the coupling's scope | Mass action only in its linear regime. It holds slow, chromatin-like states well: retention 1/k_off, writes at events |
| `site_occupancy@1` | Kinetic | **Yes** | Patches and contacts only (`operators/site_occupancy.py`:4–6) | Judged (FR-3, 51 of 51) | A node owner, for sites on DNA in a cell |

**The discriminator.** Does bound factor have to leave the free pool?
- If promoters and decoy sites are few against the factor, it does not. B1′'s Hill factor or the
  regulatory state serve, and both are on main.
- If they are many, or the factor is scarce, it does. Then the closure (at equilibrium) or the sites
  (kinetic) are needed. The sites need a node owner. The closure needs more: seam C's rule for laws
  that declare the forms they move (CORE_SEAMS §5.2), and then a read.
- A ligand row has no forms, so the refusal does not reach it. A transcription factor that turnover
  or synthesis writes can still be the closure's ligand (S, from `species_registry.py`:793–797).

**Two misfits of the closure.**
- **Its envelope.** Rapid equilibrium must be fast against the processes that read it. Operator
  dissociation can take minutes (named from memory, not read), which is not fast against a
  bacterial transcript's life. The closure's lag estimate (`lag_first_order`) measures this per
  ligand, and a kinetic block takes over where it fails.
- **A binder total of about one copy.** The closure's total is then one molecule's concentration,
  and its occupancy is a probability. That is right in the mean (§3.1). It is not a distribution.

### 1.4 Regulatory networks as declared laws

- **A network is a definition, not a model.** It is the species (regulators, transcripts, products),
  one templated-synthesis route per gene, and the factors that act on each route's initiation. Its
  wiring is data. The engine holds only general laws, as the coupling note put it: "Track R's
  network is a driver's declaration" (INVENTORY_COUPLING §5).
- **The laws stay general, with physical units:** concentrations in mM, rates in s⁻¹, lengths in
  residues, and potentials from the registry. No law is labelled with a protein (D144; the
  catalogue rule).
- **Logic from the same laws (S):**
  - factors on one route multiply, which acts like AND;
  - two routes into one product add, which acts like OR. The gap-junction replication writes each
    modified Hill rate as two Hill-factored sources (its §3);
  - several factors on one promoter, through the binding polynomial, give general logic (Bintu et
    al. 2005; named from memory, not read).
- **The "λ" form of F6 is B1′'s basal level (S).** The replication's modified Hill rate is
  (1 + λ x^n)/(1 + x^n), with x = TF/K.
  - For λ < 1 it is b + (1 − b)·(an inhibition), with b = λ.
  - For λ > 1, divide by λ: it is b + (1 − b)·(an activation), with b = 1/λ, and the scheduled rate
    set at λ times the basal rate. The schedule is the maximum (B1′'s rule).
- **Boolean and logical networks are references, not physics.** This covers Taoma et al. 2024,
  Albert and Othmer 2003, and REVERT's 17-node network.
  - They run out of process, with the user's approval per paper (D138).
  - A continuous network in Cells can be compared with them, as REVERT's group 1 asks.
- **Already on main, as development:**
  - D152 sources with Hill factors are phenomenological production with no precursor. The
    gap-junction replication's EMT switch runs on them (its §3).
  - Whether that counts as gene regulation under D145 is a question for the user (§6, Q3).
- **`emt_mirna@1` is legacy** (`legacy/models/emt_mirna.py`). It runs in scaled coordinates, with no
  volume and no ledger. It is a reference for the equations (D196), not a block to extend.

### 1.5 Material and energy in one account

**Material (S).**
- Per route, the monomers consumed equal the residues in finished products, plus the residues in
  transit in the chain, plus the residues returned by degradation. That is one conversion ledger,
  as the producer's `unit_conversion` and `unit_chain` are (`population_unit_turnover.py`:137,
  :929) **(code)**.
- The machines are conserved: free plus engaged equals the total.
- Seam E's moieties will check the stoichiometry once the registry holds them. That is the binding
  owner's item, queued after the nucleotide entries (D234).

**Energy (S).**
- Each stage's ΔG comes from the registry's potentials: the monomers, the fuel, and the polymer per
  residue.
- So the product row carries a standard potential per residue, and its free energy is booked, not
  dropped. FR-7's units, by contrast, carry none (`population_unit_turnover.py`:62).
- Heat is H = −ΔG ≥ 0 per stage. A stage that would run uphill is refused, never repaired.
- The law's flux takes the form J = J⁺(1 − e^{ΔG/RT}), so it vanishes at equilibrium. This is seam
  A's principle: thermodynamics from the registry, kinetics in the law.
- The per-residue potentials need sources. Values of the right kind exist for phosphodiester and
  peptide bonds, but none was read for this note.

**Fuel: two kinds of draw.**
- **(a) Stoichiometric:** the NTP that is both monomer and fuel, translation's ATP and GTP per
  residue, and recharging NMPs. This is the polymerisation's own chemistry.
  - MEMBRANE_RETRIEVAL §3.4 records the rule for that case: "a reaction coupled to ATP is a reaction
    with ATP in its stoichiometry ... No new mechanism is needed, only the admitted fuel rows."
  - So the operator writes the fuel rows in its own half-steps, as D152's reactions do. Those rows
    are finite (moved): "Held rows have one writer: none" (the same section).
- **(b) The machinery's other costs:** chromatin remodelling, export, the proteasome's unfolding,
  and a regulatory state's maintenance (the coupling note's §6.4 Q6).
  - These have no stoichiometry of their own. They need seam E's fuel block, which D217 says is
    "designed once, in the common energy interface", after `finite-fuel-v1`.
  - D151 also defers drawing D150's operators on finite energy pools.
- **What finite fuel brings.** Depletion becomes a response: expression slows when ATP or NTP runs
  short. Held fuel would only record the supply.

**Charge.**
- NTPs, PPi and RNA are polyanions, and Mg²⁺ binds them. The engine conserves charge as well as
  material and energy.
- **Version 1: neutral formula units, declared as such.** FR-10 doses in formula units whose charge
  is zero in integer arithmetic, and "a neutral species is its own formula unit"
  (BATH_SCHEDULE_DESIGN §2).
  - Version 1 declares each nucleotide and polymer row at valence 0. The row stands for the anion
    with its bound counter-cations, as one neutral unit.
  - It is a declared reduction. An observable that needs the charge, such as Mg²⁺ or pH effects on
    elongation, is refused.
  - The alternative is FR-10's own shape: charged rows (NTP⁴⁻ and its cations) moved together in
    neutral units. That needs charged species in the new operator, which is the later path below.
- **Later: charged rows,** through FR-15 S1 (charged species in D152 reactions, each conserving
  charge) and the binding owner's nucleotide forms (H⁺ and Mg²⁺ on ATP, ADP and Pi;
  MITOCHONDRIA_DESIGN §1.3).
  - Today `scheduled_species_turnover@2`, for charged clearance, is unbuilt.
  - FR-7's producer refuses a charged precursor (`population_unit_turnover.py`:71).
- **Version 1 worlds therefore do not compose with mitochondria's rows.** Each species has one
  authority, so ATP cannot be a neutral lump in one operator and a charged row with H⁺ and Mg²⁺
  forms in the same world (S). An expression cell beside MT-1's nucleotide rows waits for the
  charged path.

### 1.6 What the products act on

The coupling note asked whether the layer's output should "reach physics only through this
operator, keeping one route from molecular state to controls" (its §6.4 Q5). Two directions need
keeping apart (S).
- **Into production.** Every route from a molecular state to a production rate goes through B1′:
  a Hill factor, a regulatory state, or occupancy as a new source kind (§2.3). That is D218's "one
  coupling and rate-routing mechanism".
- **Out to physiology.** A product acts only through a declared mechanism, never through a parameter
  read from an expression level:
  - as material: a subunit that FR-7's producer turns into channel units;
  - as a source of the coupling operator's factors on channels, junctions or rates;
  - as a catalyst row that D152's Michaelis–Menten law reads.
- **Cell behaviour** (proliferation, survival, migration) driven by a state or an expression level
  is D228 item 7's own design note, in FR-7's family. It is not designed here.

## 2. Architecture

### 2.1 Where each entity lives

**The homes, and what each admits.**

| Home | Amounts | Free energy | Cost | Readable by other mechanisms |
| --- | --- | --- | --- | --- |
| **An @3 species row** | Strictly positive everywhere. An absent species is held at a declared trace (SECRETED_SPECIES §1.3) | μ from the registry | One of 16 rows per world, ions included (`operators/species_common.py`:52, :279–288) **(code)**. Neutral unless FR-15 S1's charged path applies | Yes: the coupling, the reactions, the producer, the closure |
| **Population units on a host** (`membrane_entity_state@1`) | N ≥ 0, with an entity ledger | None | No row | Through the view, for channels on patches. A node host is proposed (MOLECULAR_MACHINES's N2), not built |
| **An operator-owned pool** (as the producer's `unit_pool_units` [route, pool]) | ≥ 0, with the operator's ledgers | None | No row | No: owned by one operator |
| **A regulatory state** | s in [0, 1] | None: kinetic | No row | Through B1′ |
| **Declared data** | Structural, fixed in a run | — | — | At binding |

**Each entity's proposed home (S).**

| Entity | Proposed home | Why |
| --- | --- | --- |
| **The gene, the template** | Declared data per gene and cell: copies, length, product and promoter | It changes only at replication, which is out of scope, or at division, an integer partition later. It is never a moved amount. At 1–2 copies it is always below the floor (§3.1) |
| **Promoter state** | Form fractions of the closure; a regulatory state; or site populations on a node | §1.3 |
| **Free RNA polymerase and ribosomes** | An operator-owned machine pool per node, with a machine ledger | In version 1 only the synthesis operator reads them. A pool admits zero and costs no row. A row is the alternative if another mechanism must read them |
| **Elongating complexes** | Operator-owned chain pools [route, stage], holding the engaged machines and the residues in transit | The producer's pattern |
| **mRNA** | A species row, with a per-residue potential | The gap-junction replication's F6 binds it, and Syn3A's degradosome would read it. An operator-owned pool would save one row where only its own operator translates and degrades it |
| **Protein** | A species row | It is read as a regulator (B1′), consumed as a subunit (FR-7's producer) and read as a catalyst (D152) |
| **Monomers:** NTP, NMP, amino acids | Species rows, lumped, neutral formula units | Shared with recharging (D152) and, later, metabolism (F8) |
| **Fuel:** ATP, ADP and Pi | Species rows (D176's F2) | One authority for amounts and potentials. GTP and GDP are counted as ATP equivalents, and PPi as 2 Pi hydrolysed at once: two declared reductions |
| **Transcription factor or inducer** | A species row | A Hill source for B1′, or the closure's ligand |
| **Slow, chromatin-like state** | A regulatory state | GZMK item 6's "slow, writable per-cell state", with retention, reset and transfer |

**The row count, against 16 (S).**
- The heredity cell already holds four rows: Na⁺, K⁺, M⁻ and P⁻ (`HEREDITY_SPECIES`,
  `validation/tissue/surface_pump_v3_fixtures.py`:150).
- One gene adds nine rows: the regulator, mRNA, protein, NTP, NMP, amino acid, ATP, ADP and Pi.
  That makes 13.
- A second gene adds its mRNA and protein, for 15.
- Separate PPi, GTP and GDP rows would reach 18. Four NTPs and twenty amino acids are F8's scale.
  So version 1 lumps, and says so.

### 2.2 The building blocks: reuse and extension

| Block, at f85d8f3e | What it gives today (code) | Its role here | What is missing |
| --- | --- | --- | --- |
| `population_unit_turnover@1` (FR-7 F1; development) | A neutral precursor becomes channel units through m ≤ 8 maturation pools (`MAX_POOLS`, :110). The half-steps are exact by uniformization, with Λ dt ≤ 1 refused otherwise (:113). There are ν molecules per unit, two ledgers, and signed work for the precursor. One precursor per route. No fuel, no machine. Its refusal is simulation-wide (D232) | The pattern the synthesis operator generalises | A soluble product with a potential; a machine pool; monomers drawn along the chain; fuel in the stoichiometry; degradation that returns monomers; several monomer roles per route |
| `species_regulated_availability@1` (judged) and `@2` (B1′; development) | A Hill factor of a species, or a regulatory state, sets @3's channel or junction availability, or a routable rate in its target's own half-steps. F lies in [b, 1], the scheduled rate is the maximum, and each route declares an operating range | Initiation's regulation | A new target is one row in `OPERATOR_TABLES` (:149–154). FR-7's F3 added its producer that way on its branch (cf7145ad, not on main), as a recorded exception naming the operators owner |
| `local_species_reactions@1` (judged within MG0c's scope) | Driven mass action and Michaelis–Menten with Hill factors; passive detailed balance; integer moieties. A passive reaction has molecularity at most 3 on each side, and a driven one an order of at most 3 (`MAX_MOLECULARITY`, :156, :535–548); 16 species | Recharging (NMP to NTP, PPi to Pi); small phenomenological networks | It cannot carry polymerisation: a product takes 10²–10⁴ monomers, an order far above 3. Degradation to L monomers is admissible as a driven reaction of order 1, since products are not capped, but a driven route books its ΔG as signed work, not heat (S) |
| `rapid_binding@1` (compared) | A multi-ligand closure over binders whose forms the registry declares | Equilibrium occupancy | Seam C's mover rule, since no operator may name a row with forms today (`species_registry.py`:783–813); then a read of form fractions; nested binders, for induction |
| `site_occupancy@1` (judged) | Kinetic Langmuir binding with the sites conserved, on patches and contacts | Kinetic occupancy | A node owner |
| `hill_regulated_two_state@1` (judged within the coupling's scope) | ds/dt = k_on u (1 − s) − k_off s, with exact half-steps | A kinetic promoter in its linear regime; slow chromatin-like states | — |
| `scheduled_species_turnover@1` (clearance judged with D150's faces; production guarded only) | Production P with no material origin, and first-order clearance; `turnover_rate` is routable (:437) | The regulator's supply; today's phenomenological stand-in for expression | Material origin and fuel, by design |
| `membrane_entity_state@1` | Units with a ledger; conductance linear in units | Where a product becomes function (through FR-7's producer) | — |
| Fuel rows (`maintained_held_rows@1`, `finite_fuel_rows@1`) | Held, or moved with stored energy | The ATP pool | `finite-fuel-v1` is not yet judged; seam E's fuel block is not built |
| The assembly family's kernel and streams (`models/assembly_lineages/kernel.py`, `streams.py`) | The exact direct method in JAX over vmapped lanes; keyed counter-based streams (Threefry, folded from the seed, the world, the carrier, the domain and the counter); event heat | The pattern for the low-copy regime (§3.3) | A home inside the composite |
| `emt_mirna@1` (legacy) | Scaled equations, with no volume and no ledger | A reference for F6's equations | — |

### 2.3 New pieces, named as proposals (S)

1. **`templated_polymerisation@1`, one operator module.** It declares routes. Each route names:
   - a template: a gene of the declared template data, or an mRNA row;
   - a machine pool;
   - its monomer rows, with residues per product;
   - its fuel per residue, as stoichiometry;
   - its product row and length L;
   - its stages m and speed v;
   - its initiation law.

   Transcription and translation are two routes of the same operator, because they are the same
   physics.

   **Its laws:**
   - **Initiation:** mass action in free machines and template copies, times B1′'s factors, through
     a routable control `initiation_rate`.
   - **Elongation:** the Erlang chain with per-stage moves, at constant speed in version 1. A
     monomer-dependent law could follow later: Hofmeyr, Gqwaka and Rohwer 2013 give a generic rate
     equation for catalysed template-directed polymerisation that includes monomer saturation
     **(checked**, abstract only; whether it is reversible was not confirmed).
   - **Degradation:** first order, returning monomers, with fuel where declared.

   **The numerical method is open.** The producer's half-step is exact because its rates are
   frozen and its chain is linear. Machine sharing makes initiation depend on how many machines
   are already engaged. Frozen over a half-step, that dependence is first order. Three ways keep
   the composite second order:
   - a midpoint predictor;
   - D152's SSPRK(3,3);
   - machines declared abundant, with a per-step cap on the change of the free fraction.

   The references measure the order whichever is chosen (§4.1, R-share).
2. **A node host for site populations.** It would give kinetic, conserving promoter occupancy, with
   sites on DNA in a cell.
3. **An occupancy source in the coupling operator.** A closure's form fraction, or a site
   population's occupancy, becomes a B1′ source, as FR-7's population-abundance source (b) was
   designed. So one mechanism still carries every route from state to production. This is D218's
   "one coupling and rate-routing mechanism", and the coupling note's §6.4 Q5. For the closure it
   waits on seam C's mover rule, the binding owner's, since the registry refuses the coupling's
   reads of a row with forms today.
4. **A count-based stochastic block** (§3).

### 2.4 Composition, ownership and seats

**Order in the split (S).** The regulator's writers come first, then the coupling's states, then
templated synthesis, then recharging. Each is a split part with exact or second-order half-steps.
The composite step stays Strang second order when the order is declared, as the coupling note
argues for its states (INVENTORY_COUPLING §1.4).

**Two writers of one row.**
- The monomer and fuel rows are written both by the synthesis operator and by D152's recharging.
- Today D152 refuses only turnover on its rows (`species_reactions.py`:837–851). Its §1.1 rule is
  one local-kinetics writer per row.
- The lead admitted two writers for FR-7's producer and turnover, on 19 November, under conditions:
  each is a split part with exact half-steps in declared order, books its own moved amounts and the
  exact ΔG of its own move, and refuses a non-positive amount (`population_unit_turnover.py`:13–17).
- **That ruling would need extending** to a D152 network beside the new operator, with a measured
  splitting check. That is D152's door "turnover on reacting rows" (its §7.3).

**Idleness.** An undeclared operator is absent from every program, so crossrev stays identical
(ARCHITECTURE, "Undeclared mechanisms are absent from the traced program"). A declared one with zero
rates is bitwise idle, as the producer is.

**Files (code).**
- A new operator module "joins with no edit" to the package (`operators/__init__.py`:10–14). New
  law modules go under `laws/`, one module per law (seam F).
- One row goes in the coupling module's table of routable targets.
- Registry entries are definition data, declared on the inner model's species entries
  (`species_registry.py`:11–14). They need no change to the registry's code.
- So option A touches no core owner's file beyond that one row. Option B touches the binding and
  operators owners' files (§4).

**Seats.**
- Each option needs a gene-regulation lane agent and a code-blind references agent: two seats,
  within the cap of seven.
- Whether they fit beside D234's mitochondria lane is the lead's count.

### 2.5 Numerics and timescales (S)

- **Who sets the step.**
  - In a cell with no gated channel and no pump, the species' own rates set dt. D152's probe chain
    admitted 0.25 s (SHARED_INVENTORY_REACTIONS §4.1).
  - For templated synthesis the bound is Λ dt ≤ 1, with Λ the largest chain rate m v/L.
  - With ions moving, 1 ms holds (D231's FR-7 world).
- **Two worked cases, with m = 8.** The dt below is only the producer's stability rule, an upper
  bound. Other checks may bind first: the gap-junction replication's runs held dt × rate ≤ 0.1, and
  one of its steps was limited by @3's energy check, not by stability (its §4). The capability probe
  reports which check binds (§4.1).
  - *Bacterial-like:* 1,000 nt at 50 nt/s and 300 aa at 15 aa/s. Each chain is 20 s, so κ = 0.4 s⁻¹
    and dt ≤ 2.5 s at most. A 5 h horizon at 1 s is 18,000 steps; at dt × κ ≤ 0.1 it is 72,000.
  - *Mammalian-like:* 10 kb at 50 nt/s and 500 aa at 5 aa/s, so κ = 0.04 s⁻¹ and 0.08 s⁻¹. Five
    median protein half-lives (46 h) make 230 h, which is 8.3 × 10⁵ steps at 1 s. That step keeps
    dt × κ below 0.1.
  - At 1 ms, one hour is 3.6 × 10⁶ steps.
- **Cost.** D152's species-only chain cost 2.2–2.7 ms per step at 32 nodes, on one CPU core with
  host checks (SHARED_INVENTORY_REACTIONS §4.7). At that rate 8.3 × 10⁵ steps take about 30–40
  minutes (S): a detached judged run, not a test.
- **Consequences.**
  - A channel-free expression cell runs real lifetimes on today's engine.
  - Coupling to Vm runs at 1 ms. So it takes synthetic minute-scale lifetimes, labelled as such
    (D217's rule for FR-7), or it waits for FR-8.
  - Tests use short horizons, under the 30-minute rule. Judged runs are detached.
  - Tests stay lean (D224): one parametrized file for the operator's guards, and each new
    world-compiling test states its seconds and its reason at landing.

## 3. The low-copy regime

### 3.1 What the deterministic aggregate means below the floor

**The floor.** D150 §1.3: "Below about 10² molecules per node, the compared quantities need coarser
nodes or a stochastic treatment."

**One molecule at Cells' scales (S, from the volumes named).**

| Node | One molecule | 10² molecules |
| --- | --- | --- |
| Syn3A, radius about 200 nm | about 50 nM (SYN3A_MINIMAL_CELL_TRACK §4.3) | about 5 µM |
| *E. coli*, about 1 fL | 1.7 nM | 0.17 µM |
| FR-7's F4 cell, 7.5 fL (D233) | 0.22 nM | 22 nM |
| The heredity cell, 0.75 pL (`HEREDITY_VOLUME_PL`) | 2.2 pM | 0.22 nM |
| A mammalian cell, about 2 pL | 0.83 pM | 83 pM |

**Typical counts.**
- A gene has 1–2 copies, always below the floor.
- mRNA: a median of 17 per mouse fibroblast (Schwanhäusser et al. 2011, as corrected); about one
  per gene in Syn3A (SYN3A §4.3).
- Protein: a median of 50,000 per mouse fibroblast; about 120 in Syn3A, with 10% of proteins below
  10 copies (SYN3A §4.3).
- Monomers and fuel are at mM, far above the floor.

**When the deterministic form is exact.**
- **A first-order network with given inputs.** The rate equations are then the exact mean of the
  chemical master equation. For monomolecular systems the distribution is a convolution of
  multinomial and product Poisson distributions whose parameters follow the reaction-rate equations
  (Jahnke and Huisinga 2007, **(checked**, abstract).
- **Independent, identical sites in a given environment.** Occupancy is exact in expectation
  (MOLECULAR_MACHINES §3.1, point 1).
- **So an open-loop expression chain is exact in the mean at any copy number,** when the regulator
  is given and the machines and monomers are abundant.
- **"Given" matters.** A two-gene cascade, in which gene 1's product regulates gene 2, is not exact
  even without feedback: gene 2's initiation is a nonlinear function of a low-copy, fluctuating
  input (S).
- **Machine sharing is nonlinear.** With machines and monomers at 10³ copies or more, its
  mean-field error should be small (S). The references measure it (§3.4, step 1).

**When it fails.**
- Feedback through a low-copy species, because E[f(x)] ≠ f(E[x]).
- Bimolecular steps between low-copy species.
- Bistability. A population splits between branches, while a deterministic run picks one.
- Bursts, and partition noise at division.

**The precedent until then: D233.** FR-7's F4 scaled its template five-fold to keep the judged
effect above the floor. Its sub-floor tail is registered as a bounded term, the same on both sides
of the comparison.

### 3.2 What a stochastic or hybrid regime needs

1. **Count state** for declared low-copy species: integers per species and node, beside the
   continuous rows. Counts may be zero. @3's rows may not, so counts live with their operator.
2. **Propensities in count form** from the same declared laws. A bimolecular rate becomes
   k/(N_A V) n_A n_B, and a homodimer's n(n − 1)/2. ARCHITECTURE: "stochastic execution needs
   count-based propensities and its own qualification".
3. **Keyed streams.** Counter-based draws, keyed by seed, world, cell, process, domain and counter,
   with no random state in a checkpoint. The fixed-step checkpoint refuses random state
   (`records/io.py`:173–174) **(code)**, and keyed streams need none. Initialisation, process noise,
   partition, intervention and analysis use separate domains (ARCHITECTURE, "Randomness, replay,
   and checkpoints").
4. **Event semantics inside the composite's step.**
   - *One-way coupling:* an exact SSA over each step, with the deterministic environment frozen for
     the step and declared as frozen. Nothing writes back, so every other array stays bitwise.
     This is machines' I1 pattern.
   - *Two-way coupling:* hazards integrated against changing propensities, and pending events
     rescheduled. One method is Anderson's modified next-reaction method (2007, named from memory,
     not read). The execution architecture names the risk: "a voltage, calcium or resource change
     that alters a reaction propensity can invalidate a previously sampled waiting time. Specify and
     qualify the hazard integration ... before adding such feedback."
   - *Hybrid by copy number:* a fixed split first, high-copy species continuous and low-copy ones
     counted (Haseltine and Rawlings 2002; Salis and Kaznessis 2005; named from memory, not read).
     The 4D minimal-cell model splits its methods this way (PAPER_REVIEW_WHOLE_CELL §5, item 3).
     Promotion and demotion during a run come last (ARCHITECTURE, "Levels of detail").
5. **Energy:** GARD's guard for stochastic laws (GARD_DESIGN §2.4).
   - Local detailed balance is checked at the kernel.
   - Event heat is booked per committed event, in a ledger declared non-monotone.
   - The ledger closes against ln π.
   - Driven synthesis books −ΔG per event, with its fuel.
6. **Delays.** Either explicit Erlang stages, which keep the process Markov, or a delay SSA (Cai
   2007; Barrio et al. 2006; named from memory, not read). Stages fit the deterministic
   representation, so the two levels share one declaration.
7. **Partition at division:** binomial, drawn from a partition stream. GARD's streams already
   have a partition domain (`streams.py`:36–37).
8. **Declared representations** (D175). Counts and means are two representations of one mechanism.
   One representation per scope is enforced by the `represents` key, and the counted one is the
   reference.
9. **Verification by distributions.**
   - Exact stationary distributions: Poisson for birth and death; the telegraph model (Peccoud and
     Ycart 1995); a negative binomial in the bursty limit (Shahrezaei and Swain 2008). All named
     from memory, not read.
   - Finite state projection (Munsky and Khammash 2006, named from memory) as an exact numerical
     reference.
   - Tests with their power declared before the runs.
   - Replay is bitwise on the CPU through the keys. Across devices, agreement is distributional
     (ARCHITECTURE).

### 3.3 What exists

- **In the assembly family:**
  - the exact direct method in JAX over vmapped lanes, with partial sums in a declared fold order;
  - keyed counter-based streams, "an assembly's draws depend on its identity alone";
  - event heat, and partition draws (`models/assembly_lineages/kernel.py`:1–30, `streams.py`:1–30).
  - It is a separate engine, one assembly per lane, with no bridge into the composite.
- **`capsid_graph@1`'s event solver,** with a host oracle (CAPSID_ASSEMBLY).
- **Machines' I1, designed:** tagged individuals that follow the aggregate's rates with no effect
  on the run (MOLECULAR_MACHINES §2).
- **Nothing in the composite** runs stochastic chemistry. Syn3A's F11 is a line in its track note
  (§4.3), with no design.

### 3.4 A staged path (S)

1. **From milestone 1: the references measure the gap.** A code-blind SSA, in NumPy, of the same
   declared equations reports the mean-field error at the world's own copy numbers. It needs no
   engine change, and it tells each later claim whether the deterministic run is enough.
2. **A one-way stochastic block per cell** (option C): exact in distribution for a given
   environment, with every other array bitwise.
3. **Two-way hybrid coupling,** with hazard integration, when a consumer needs feedback at low copy:
   a bistable network, Syn3A's Stage 4, or noise-driven fate.

## 4. Options for the first milestone

Each option names:
- its scope and the engine models it runs;
- what it needs from the engine;
- its code-blind references and its planted controls (ledgers cannot see a wrong rate, as the
  coupling note found);
- a biological target, with what calibrates and what is predicted, and the licence class;
- its rows against 16, its steps, its molecules against the floor, its fuel, and the owners and
  seats it uses;
- its effort and its main risk.

The milestone labels **GR-1A** to **GR-1D** are this note's.

### 4.1 Option A: the expression unit, one gene, open loop, deterministic (GR-1A)

**Scope.**
- One cell, one or two genes. Transcription and translation run as two routes of
  `templated_polymerisation@1`, each with its machine pool and its chain.
- A second gene is only a partner that shares the machines. Neither gene's product regulates the
  other, which would leave the exact-in-mean regime (§3.1).
- mRNA and protein are degraded, and their monomers are returned. NMP recharging and fuel
  regeneration run as D152 reactions.
- An inducer or transcription factor, made and cleared in the cell by D150's turnover on a declared
  schedule, sets initiation through B1′: a Hill factor of its concentration, or a regulatory state.
  There is no feedback.
- **Two arms:**
  - **A1:** a channel-free cell. The species' own rates set dt, at seconds, and lifetimes are sourced
    or declared.
  - **A2:** the protein becomes FR-7's precursor. `population_unit_turnover@1` makes channel units
    from it, and Vm responds. This runs at 1 ms with synthetic minute-scale lifetimes, labelled
    (D217). It is the chain from gene to voltage, open loop.

**Engine models it runs.**
- `resolved_pump_composite@1` over `resolved_pump_tissue@3`.
- `templated_polymerisation@1` (new).
- `species_regulated_availability@2` (B1′).
- `local_species_reactions@1`.
- `scheduled_species_turnover@1`.
- A2 adds `membrane_entity_state@1` and `population_unit_turnover@1`.

**What it needs from the engine.**
- A capability probe first, as Syn3A's P0 and the Xenopus lane's parse-only probe were: a
  channel-free heredity cell holding the expression rows, admitted at second-scale steps (§2.5 is
  this note's reading, not yet a measurement).
- The operator and its law modules: the lane's own new files.
- One row in the coupling module's routable targets.
- Registry entries as definition data: lumped monomers, polymers with per-residue potentials, and
  the fuel rows.
- The two-writer ruling for D152's recharging (§2.4), with its splitting check.
- For A2, the producer must admit a precursor that the new operator writes. Today it refuses every
  author but turnover (`population_unit_turnover.py`:77–79), so that is an edit for the producer's
  owner.

**Code-blind references** (an agent that never reads the operator, working from the laws' appendix
of declared equations).
- **R-chain:** the cascade's closed form for the means (gene to mRNA to protein, with Erlang
  stages). It is exact at any copy number in the open loop (§3.1).
- **R-account:** the residue identity per route, the machine identity, and ΔG per stage from the
  registry's potentials, so that heat is −ΔG.
- **R-share:** an independent stiff ODE for two genes sharing machines. It also measures the
  method's order (§2.3).
- **R-noise:** an exact SSA of the same equations, reporting the mean-field gap. It is reported, not
  judged.

**Planted controls.** A wrong stage count m, a wrong speed v, a dropped fuel term, a machine not
returned, a factor applied twice, and a wrong residue count L. Each must fail a judged item.

**What its judged run covers.** Two blocks it runs are development, not judged: B1′'s rate route
(`@2`) and, in A2, FR-7's producer.
- A1's protocol judges the route's factor on initiation within A1's own scope, as the coupling's
  protocol judged `@1`'s factors.
- A2 is reported as development until FR-7's own protocol judges the producer (its F2–F4).

**The biological target.** The test of independence: no input may be derived from the quantity it
predicts.
- **Ruled out by that test:**
  - Weber et al. 2023's per-gene initiation and elongation rates (CC BY). They were derived from the
    same mRNA and protein copies, half-lives and ribosome densities, so predicting those abundances
    from them is circular **(checked**, abstract).
  - Burgos et al. 2020's half-lives (CC BY), which are fitted to the pulse-chase they would be
    compared with.
  - A steady-state ratio of two expression levels. The chain after initiation cancels in it, so it
    tests occupancy (option B), not synthesis.
- **The class that passes: a closed batch of cell-free expression.** The components are defined
  inputs, and the exhaustion of precursors and fuel is the measured response. Calibrate on one
  condition, one template or energy level. Predict the others: saturation by finite machines, and
  the plateau that the fuel budget sets. [CANDIDATE]
- **If no permissive candidate exists,** A's first acceptance is numerical only, and the first
  biological prediction arrives with option D's period.

**Rows, steps, molecules, fuel.**
- **Rows:** 13 for one gene, 15 for two (§2.1).
- **Steps:** A1, 1.8 × 10⁴ (bacterial-like, 5 h) to 8.3 × 10⁵ (mammalian-like, 230 h) at 1 s. A2, at
  1 ms, 6 × 10⁵ for 10 synthetic minutes.
- **Molecules:** the gene is below the floor, and mRNA usually is too. Both are exact in the mean
  in the open loop. Protein, machines and monomers are above it.
- **Fuel:** finite rows, written as stoichiometry (§1.5). Held fuel would need seam E's block.

**Owners and seats.** The lane's new files; one row as a recorded exception naming the operators
owner; for A2, the producer's owner. Two seats.

**Effort (estimate): 9–13 agent-days.** The operator and its laws 5–7; the references 2–3; the
protocol and the judged run 1–2; registry data and sourcing 1.

**Main risk.** The numerical method under machine sharing (§2.3). Then the two-writer ruling, the
per-residue potentials' sources, and the 16-row cap, which forces lumping.

### 4.2 Option B: promoter occupancy as binding, judged on the simple-repression input–output (GR-1B)

**Scope.**
- A repressor binds a promoter and non-specific DNA at equilibrium, on the closure. The promoter and
  the non-specific sites are binders with registry forms, and the repressor is their ligand.
- A reporter's initiation rate scales with the free-promoter fraction, through an occupancy source
  of B1′ (§2.3).
- Production can stay D150's phenomenological source, because fold-change is a ratio of
  initiation rates, and a linear chain after it cancels (S).
- The kinetic counterpart, site populations on a node host, is the detailed representation. The
  closure is its rapid limit (CORE_SEAMS §5.3).

**Engine models it runs.** @3 and the composite; the proton-buffer kind with `rapid_binding@1`;
`species_regulated_availability@2` with the occupancy source; `scheduled_species_turnover@1`;
`site_occupancy@1` on a node host.

**What it needs from the engine.**
- **The closure's first mover or reader.** Today any operator that names a row with forms is
  refused, the coupling's reads included (`species_registry.py`:783–813). Seam C's §5.2 admits a
  law that declares its stoichiometry in base forms with every ligand written out. That rule is the
  binding owner's.
- Then an operator's read of a closure's form fraction: the binding owner's seam C and the operators
  owner's contract.
- The occupancy source in the coupling module.
- A node owner for site populations.
- Induction, through the MWC model, needs nested binders, which the registry refuses today
  (`species_registry.py`:36).

**Code-blind references.** The thermodynamic model's closed forms; the closure against an
independent Newton solve; kinetic sites relaxing to the closure; titration across promoter copies.

**Planted controls.** A wrong binding energy (standard potential); the non-specific binder left
out; the total promoter used in place of the free fraction.

**The biological target.** [Pending the validation check; §4.6.]

**Rows, steps, molecules, fuel.**
- **Rows:** 8.
- **Steps:** hundreds, at seconds.
- **Molecules:** in *E. coli*, one molecule is 1.7 nM. A repressor at about ten copies (named from
  memory) sits below the floor, and the closure is the mass-action (grand-canonical)
  approximation (S).
- **Fuel:** none. Binding is passive, and the closure books its own free energy.

**Owners and seats.** The binding and operators owners, both on D234's critical path, plus two
seats.

**Effort (estimate): 9–14 agent-days,** including about 1–2 for seam C's mover rule.

**Main risk.** Contention with mitochondria's binding work (D234). Then *E. coli* as a data-only
organism (D179 added it for the FEP track only), the closure's envelope against slow operator
kinetics, and small-number effects.

### 4.3 Option C: the low-copy regime first (GR-1C)

**Scope.**
- A count-based block per cell for declared low-copy species: gene states, mRNA, and optionally
  protein.
- It is coupled one way. It reads the regulator and the machines and writes nothing back (§3.2,
  item 4).
- Exact SSA within each step, with keyed streams and event heat.

**Engine models it runs.** @3 and the composite, with a new `count_reactions@1` (S) that reads its
species through the read-only list (the coupling's ruling 1).

**What it needs from the engine.**
- The composite admitting integer count state and keyed draws, with counters checkpointed.
- Count-form propensities from declared laws.
- The run view's distributional outputs.
- Batches for statistics.

**Code-blind references.** Exact distributions and finite state projection (§3.2, item 9); tests
with declared power.

**Planted controls.** A wrong propensity (n against n − 1 for a dimer); a stream shared between
cells, which plants a correlation; a wrong burst size.

**The biological target.** Single-molecule FISH distributions.
- Raj et al. 2006 (PLoS Biology, **CC BY**, **(checked)**) measured mammalian mRNA counts and fitted
  a bursting model. Raising the transcription factor's level increased burst size, not frequency.
- Its rates are fitted, so a judged comparison needs a held-out condition.
- [Pending: a series that predicts noise from independently measured parameters; §4.6.]

**Rows, steps, molecules, fuel.**
- **Rows:** counts live in the operator.
- **Steps:** about 10³–10⁴ events per gene and hour; statistics need 10³–10⁴ replicate cells in
  batches.
- **Molecules:** this is the regime's point.
- **Fuel:** none one way. Event bookings against finite rows need two-way coupling.

**Owners and seats.** A new operator module; the operators owner, for count state and draws in the
contract; the run view's owner; two seats.

**Effort (estimate): 14–22 agent-days.** The roadmap gives F11 10–20.

**Main risk.** Two-way coupling, the hard part, is left out. The composite's guarantees (crossrev,
bitwise idleness) must hold beside a stochastic block, and statistical verdicts need power.

### 4.4 Option D: a network with feedback, as declared laws (GR-1D)

**Scope.**
- Delayed negative autoregulation, on option A's operator. A transcription factor represses its own
  gene through B1′'s Hill inhibition.
- The delay is the chain: gene length over elongation speed, plus declared processing. Both
  products turn over.
- The observable is the oscillation's period and its damping.
- The same laws then carry the EMT switch as a second network, the gap-junction replication's F6:
  - the microRNA–mRNA binding partition as closure forms (mRNA a binder with zero to six bound);
  - the λ-form factors as B1′'s basal levels (§1.4).

**Engine models it runs.** Option A's models, with the feedback route under D218's conditions. F6
adds B's occupancy source.

**What it needs from the engine.**
- Option A, and the cut-feedback control, which exists (the coupling's `coupling_controls`
  switches).
- For F6, more than B's read. The mRNA becomes a binder with forms, and the synthesis operator makes
  and degrades it. The registry refuses any operator that names such a row
  (`species_registry.py`:783–813), so F6 waits for seam C's mover rule (CORE_SEAMS §5.2).

**Code-blind references.** The chain version's linear stability, which gives the Hopf threshold and
the period at onset (S: the characteristic equation of an m-stage chain); an independent ODE or DDE
solve; the period under refinement.

**Planted controls.** The feedback cut, which must give no oscillation; a wrong delay, which shifts
the period; a factor on the wrong route.

**The biological target.** The Hes1 oscillation.
- Serum-treated cultured cells oscillate with a period of about 2 h, cell-autonomously, through
  negative autoregulation (Hirata et al. 2002, **(checked)**, abstract).
- The measured half-lives are given in secondary sources as 24.1 ± 1.7 min for mRNA and
  22.3 ± 3.1 min for protein. They are to be read in the original.
- Monk 2003 shows that the period is set by the delay and the two half-lives, and is robust to the
  transcription and translation rates **(checked**, abstract).
- **The split.** The half-lives and a delay computed from gene length and elongation speed are
  inputs. The period is the prediction.
- **The weakness.** Whether it oscillates at all depends on unmeasured parameters: the Hill
  coefficient and the rates. Those are calibration, declared as such.
- **Licence:** subscription papers, so bare numbers only (D227).

**Rows, steps, molecules, fuel.**
- **Rows:** 12.
- **Steps:** a 12 h horizon at 1–10 s is 4,320 to 43,200 steps, in A1's channel-free cell.
- **Molecules:** Hes1 copy numbers are not in hand. In a loop the low-copy question bites (§3.1). So
  R-noise must compare the deterministic period with the stochastic mean period before any judged
  claim (Barrio et al. 2006, named from memory, not read).
- **Fuel:** as A.

**Owners and seats.** As A.

**Effort (estimate): 6–9 agent-days on top of A.**

**Main risk.** GRN_WETLAB's warning: oscillation itself is tuned. D218 was written for FR-7's
physiological loops. Low copy in a loop. Mouse data from subscription papers.

### 4.5 Side by side

| | A | B | C | D (after A) |
| --- | --- | --- | --- | --- |
| Proves first | Synthesis as physics, one account | Occupancy as binding | Low copy | Feedback and delay |
| New engine pieces | One operator | Seam C's mover rule, closure read, occupancy source, node host | Count block, contract change | Feedback route evidence; for F6, seam C's mover rule |
| Rows of 16 | 13–15 | 8 | Counts outside rows | 12 |
| Steps | 10⁴–10⁶ at 1 s; A2 at 1 ms | 10² | Events | 10³–10⁴ |
| Fuel | Finite, as stoichiometry | None | None one way | Finite |
| Core owners touched | One table row; the producer (A2) | Binding, operators | Operators, run view | As A |
| Seats | 2 | 2 | 2 | As A |
| Effort (estimate) | 9–13 | 9–14 | 14–22 | 6–9 more |
| D145 and D218 asks | Lift D145 for polymerisation laws (F10); D218 unchanged (open loop) | Lift D145 for occupancy | Lift D145 for the low-copy regime | Lift D145 for networks; confirm D218 covers TF feedback |
| Biological target | Pending (§4.6) | Pending (§4.6) | smFISH, with a held-out condition | Hes1's period |

### 4.6 The recommendation: A, then D and B, then C

**A first.**
- It is the physics the user asked for: polymerisation, finite precursors and fuel, machines,
  delays, turnover, and one account. Every consumer needs it first (§5).
- It extends one known kernel in new files, and touches no core owner's file but one table row.
  So it does not slow D222's or D234's queues.
- Its first acceptance is exact: closed forms for the means at any copy number, the account and the
  energy. The references' SSA measures the low-copy gap before any stochastic block is built.
- It needs no new door in D218, being open loop. It needs only a narrow, explicit lift of D145 for
  polymerisation laws (F10).

**The biological comparison** is registered separately, as D151 keeps every reviewed candidate. Its
target, its split between calibration and prediction, and its licence are in §4.1.

**Then D and B, by different owners.** D is the first feedback loop under D218, with the EMT switch
as F6's network. B gives the occupancy source.

**Then C,** when Syn3A's Stage 4 or a bistable network asks for it.

**The layer as a whole** is A, B, C and D: about 38–58 agent-days (estimate), beyond the owners'
pieces they wait on. A comes first because every other piece builds on it, not because the layer
stops there.

## 5. Consumers

| Consumer | What it needs | Served by | Notes |
| --- | --- | --- | --- |
| **The heredity work** | An expression carrier: "Ca/CaV plus a slow regulator", a parallel Stage D of 12–20 days (HEREDITY_FIRST_EXPERIMENT). Regulatory state among the causal carriers (CURRENT_PLAN). FR-7's U1 junction-channel unit | A with FR-7's producer, then D | The slow regulator is the regulatory state, on main. Inheritance at division is the partition's |
| **Syn3A's Stage 4** | F10, polymerisation laws, and F11, a stochastic regime. F8, metabolism past 16 species, and F9, fuel made and spent | A gives F10; C gives F11 | mRNA is about one per gene (§3.1). For *M. pneumoniae*'s Stage 4a, Burgos 2020 and Weber 2023 are CC BY, and their PRIDE deposits CC0 **(checked)** |
| **The Xenopus lane's XC1** | The butyrate route: SLC5A8 uptake, then HDAC inhibition, then expression, then incidence. Its gap list asks for an occupancy-to-state read (G-L8) and a response path to cell behaviour (G-O2) | B, for butyrate bound to HDAC sites; A, for the expression it changes | D226: the first bundle does not need it. Until then the response is the validation side's observation model |
| **The gap-junction replication's F6** | "The modified Hill (lambda) form and the microRNA-target binding partition as checked laws, with the regulatory coordinates' physical scale and time unit declared" | The λ form is B1′'s basal level, on main. The partition needs seam C's mover rule, since its mRNA is a binder that synthesis writes, and then B's occupancy source. D carries the network | The switch already runs on D152 sources, as development (its §3) |
| **The REVERT plan's group 2** | "A gene-regulation layer with sourced kinetics, coupled to cells" | D's declared networks | Group 1's Boolean reproduction runs out of process with approval (D138). No patient-specific rule set becomes an engine model (D136) |
| **FR-7** | Its precursor, today a declared pool or D150's supply | A2: the translated protein becomes the precursor | The producer's refusal of other authors changes (§4.1) |
| **Machines** | U4: the ribosome and RNA polymerase, held under D145 (D209) | A, as aggregate machine pools; individuals with FR-13's M4 after C | — |
| **Also** | Track R's pulse networks (INVENTORY_COUPLING §4.5); partial reprogramming's cross-lineage test, logged as "a second-tier benchmark for the future gene-regulation layer" (D151); the FEP track's regulated synthesis (held, D179); GRN_WETLAB's candidate networks | D and B | GRN_WETLAB's yeast model is node-to-node logic. It tests the layer once the layer exists, not as its first acceptance (INVENTORY_COUPLING §4.6) |

## 6. The user's decisions

Each question has a recommendation (S).

1. **D145's hold.** Lift it for the first milestone's laws only: polymerisation (F10) for option A,
   with machines' U4 answered as aggregate machine pools? Cortés-Poza Phase 1 and catalogue stage 3
   stay held.
   - Gene identity needs no catalogue code: a template carries D150's identity form (`catalogue`,
     `evidence`), and law IDs never name proteins.
   - *Recommended:* yes, for A.
2. **D218's door.**
   - (a) Is a transcription factor acting on its own or another gene's transcription "physical,
     state-mediated production feedback"? D218 was written for FR-7's loops.
   - (b) Should every route from molecular state to production go through B1′, including occupancy
     as a new source kind? And should products act on physiology only through declared mechanisms:
     material, the coupling's factors and catalysis (§1.6; the coupling note's §6.4 Q5)?
   - *Recommended:* (a) yes, under D218's conditions per loop, when D is built; (b) yes to both.
3. **What already runs.** D152 sources with Hill factors carry the gap-junction replication's EMT
   switch, as development. Are they admitted chemistry, or gene regulation under D145?
   - *Recommended:* admitted for development runs. A judged claim about a gene network goes through
     the layer once it is lifted.
4. **Fuel.**
   - Finite fuel rows written as the polymerisation's own stoichiometry from the first milestone.
     This needs the two-writer ruling (§2.4), and it gains from `finite-fuel-v1`.
   - The machinery's non-stoichiometric costs, and a regulatory state's maintenance, wait for seam
     E's fuel block. That covers the coupling note's §6.4 Q6, D150's question 11 and D152's
     question 10 in one design (D217).
   - *Recommended:* both.
5. **Charge.** Nucleotides and RNA as neutral formula units in version 1, declared, with charged rows
   later through FR-15 S1 and the nucleotide forms? The cost: until then an expression world does
   not share its ATP rows with a mitochondria world (§1.5). *Recommended:* yes.
6. **Data licences.** Cells is commercial open source (D173).
   - Judged results rest on permissive data (CC BY or CC0, and the deposit's own terms checked).
     Non-commercial data serve analysis only and are never committed. Bare published numbers are
     cited (D173, D227).
   - May *E. coli*, a data-only organism under D179, supply a general law's biological check, as
     ATP synthase's check uses bacterial enzyme numbers?
   - Running a paper's own model out of process stays the user's approval per paper (D138).
   - *Recommended:* yes to all three.
7. **The order.** A first, after D222's core and FR order, the Xenopus lane (D225) and D234's
   mitochondria lane? Its two seats are the lead's count within seven. *Recommended:* yes, when two
   seats are free.

## Sources

**Read in the repository** (at f85d8f3e unless stated):
- AGENTS.md; DECISIONS.md (D136–D145, D150–D152, D173–D176, D179, D209, D217–D234).
- The core-laws roadmap, branch `core-laws-roadmap` at 5662b28f: Families 3, 4, 6, 7 and 8, §1.4,
  §1.5.
- GRN_WETLAB_VALIDATION; INVENTORY_COUPLING_DESIGN §0–§6; ABUNDANCE_TO_FUNCTION_DESIGN.
- SYN3A_MINIMAL_CELL_TRACK §0, §3, §4, §8–§12; SOTA_SYN3A §5–§6.
- MOLECULAR_MACHINES_DESIGN §0–§9; MEMBRANE_RETRIEVAL_DESIGN §3 and §12.
- SECRETED_SPECIES_TRANSPORT_DESIGN §1.3 and §2.2; SHARED_INVENTORY_REACTIONS_DESIGN §0, §4.1, §7.
- CORE_SEAMS_DESIGN §2 and §5; ARCHITECTURE's modular core, "Time and numerical integration" and
  "Randomness, replay, and checkpoints"; MULTISCALE_EXECUTION_ARCHITECTURE's coupled execution and
  randomness sections.
- GARD_DESIGN §2.2–§2.4; PAPER_REVIEW_WHOLE_CELL_MINIMAL_CELL §2.3 and §5.
- GAP_JUNCTION_CANCER_REPLICATION §3–§5; SHIN_2025_REVERT_PLAN; HEREDITY_FIRST_EXPERIMENT;
  CURRENT_PLAN; PROTEIN_CATALOGUE_PLAN's stages; CORTES_POZA_2026_TEST_PLAN; BATH_SCHEDULE_DESIGN §2;
  docs/lanes/LEVIN_CANCER_XENOPUS.md; the Xenopus lane's gap analysis
  (/mnt/workspaces/Cells/xenopus-lane-20261119/GAP_ANALYSIS.md, its gap register G-L8 and G-O2).
- **Code:** `operators/population_unit_turnover.py`, `species_regulated_availability.py`,
  `species_reactions.py`, `species_turnover.py`, `site_occupancy.py`, `species_common.py`,
  `__init__.py`; `laws/reactions/rapid_binding.py`, `hill_factors.py`;
  `registry/species_registry.py`; `models/assembly_lineages/kernel.py`, `streams.py`,
  `family.py`; `records/io.py`; `legacy/models/emt_mirna.py`; FR-7's fixtures; the branch fr7-f3
  at cf7145ad (its routable-target row).

**Checked on 19–20 November 2026** (through Europe PMC, PubMed and PRIDE records, with a generic
client; publisher pages for Science, Nature, ASM and PNAS refused automated access):
- Hofmeyr JHS, Gqwaka OPC, Rohwer JM (2013) *FEBS Lett* 587:2868–2875,
  doi:10.1016/j.febslet.2013.07.011. Subscription. Abstract: monomer saturation is included;
  reversibility not confirmed.
- Hirata H et al. (2002) *Science* 298:840–843, doi:10.1126/science.1074560. Subscription. Abstract
  read; the half-lives come from secondary sources.
- Monk NAM (2003) *Curr Biol* 13:1409–1413, doi:10.1016/s0960-9822(03)00494-9. Subscription.
  Abstract read.
- Lynch M, Marinov GK (2015) *PNAS* 112:15690–15695, doi:10.1073/pnas.1514974112. No open licence
  on the record. The cost figures were read in the first author's own summary chapter, not in the
  article.
- Schwanhäusser B et al. (2011) *Nature* 473:337–342, doi:10.1038/nature10098, and its corrigendum,
  *Nature* 495:126–127 (2013), doi:10.1038/nature11848. Half-lives read in the accepted manuscript;
  copies per cell read in the corrigendum's corrected figure.
- Burgos R et al. (2020) *Mol Syst Biol* 16:e9530, doi:10.15252/msb.20209530: CC BY 4.0. Table EV1
  holds 488 per-protein half-lives. PRIDE PXD016386: CC0.
- Weber M et al. (2023) "Comprehensive quantitative modeling of translation efficiency in a
  genome-reduced bacterium", *Mol Syst Biol* 19:e11301, doi:10.15252/msb.202211301: CC BY. Its
  datasets hold per-gene mRNA and protein copies, protein degradation rates and mRNA half-lives. Its
  initiation and elongation rates were derived from those measurements and ribosome densities, so
  they are not independent of the abundances. PRIDE PXD035159: CC0.
- Raj A et al. (2006) *PLoS Biol* 4:e309, doi:10.1371/journal.pbio.0040309: CC BY.
- Bremer and Dennis (EcoSal Plus, 2008, doi:10.1128/ecosal.5.2.3) and Dennis et al. (2009) *J
  Bacteriol* 191:3740–3746: their rates were read only through BioNumbers entries, not in the
  sources.

**Also checked, abstracts only (Europe PMC):** Shea MA, Ackers GK (1985) *J Mol Biol* 181:211–230,
doi:10.1016/0022-2836(85)90086-5; Jahnke T, Huisinga W (2007) *J Math Biol* 54:1–26,
doi:10.1007/s00285-006-0034-x.

**Named from memory, not read:** Bintu et al. 2005; Peccoud and Ycart 1995; Shahrezaei and Swain
2008; Munsky and Khammash 2006; Anderson 2007; Haseltine and Rawlings 2002; Salis and Kaznessis
2005; Cai 2007; Barrio et al. 2006; MacDonald 1978, as the producer cites it.
