# Gene regulation as physics: design, and options for the first milestone

> **Legacy cleanup (25 November 2026, D386).** Paths under `src/cells/legacy/` and the older model
> IDs named below left the engine. The tag `pre-cleanup-2026-11-25` keeps them.

*Status: proposed, 20 November 2026, for the lead and the advisor, then the user (D234 item 2).
**The user chose option A the same day (D235); §7 holds its plan, refreshed against main at
e0b1d3b8, and the note's other questions stay open.** Desk work only: no engine code and no runs.
Sections 0–6 were written on branch `gene-regulation-design` from main f85d8f3e, where their code
was read; code is cited `file`:line under `src/cells/` at that revision, and §7 cites e0b1d3b8.
The core-laws roadmap was cited from its branch, `core-laws-roadmap` at 5662b28f; it is on main
since. Tags: **(code)** read in the code; **S** this note's own reading, arithmetic or proposal;
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
§7 option A, as chosen (D235): what main holds now, charged ATP, the moiety hook, the mitochondria
pattern, the arms, the non-claims and the build plan. Sources.

## 0. In short

**D235 (20 November): option A was chosen.** One gene, open loop, deterministic, expression as
templated polymerisation with its ATP cost, judged against exact references only, starting when
seats free. §7 gives its plan:
- **Charged ATP beside mitochondria is the better answer, but it needs two new pieces** (§7.2),
  under `beard2005@2` as under @1.
  - The set's ATP, ADP and Pi carry forms, and the registry admits only kinds to move such rows
    today. An operator's admission at the closure's rows is the same piece that options B and F6
    need.
  - The set's required phosphorus moiety counts only its own rows. Transcription and recharging pass
    phosphate to the world's nucleotides, which breaks it until the moiety can reach them.
  - Translation's fuel stays inside the set.
  - The charged one-gene world takes 16 of 16 rows once AMP is declared.
- **A kind cannot host the polymerisation** (§7.3): it holds no state, no machine pool and no
  transit, and it sits on patches. So the operator stays, and so does G5's first piece.
- **The built form is fixed at the sheet's tag** (§7.4). A registers the neutral reduction now, and
  the charged form follows as its own registered arm. The sheet's check shows the reduction is exact
  while pH and free Mg²⁺ are held.
- **Settled before the tag** (§7.5): recharging is the operator's own route; stages carry per-residue
  terms, so the monomial form's share cap stays as it is.
- **The operator's moiety hook,** `species_moieties(declaration)`, lands with A. It is the operators
  owner's, and the binding owner's `check_moieties` reads it (§7.6).
- **The mitochondria pattern** (§7.7): an equation sheet, symbolic in the potentials and tagged;
  code-blind references from the sheet alone, tagged; registration; then engine output.
- **A machine-limited arm** with its own plants (§7.8), and **the non-claims, registered** (§7.9).
- **About 10.5–15.5 agent-days** for A; the charged arm about 7.5–11.5 more, with its own
  references; sharing a cell with mitochondria also needs the 16-row cap raised (§7.2, §7.10).

The rest of §0 is the note as written before D235.

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
       thermodynamic model of transcription regulation. But no operator may read or move its rows
       today, ligands included;
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

   **Recommended: A.** Its first acceptance is numerical, against code-blind references. No
   permissively licensed dataset passes as its biological check today. The nearest candidate for
   a biological prediction is D's Hes1 period, once its delay has a measured source (§4.4, §4.6).
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
| `rapid_binding@1`, the closure | Equilibrium | **Yes** | A node, through a kind | Compared, not judged. When written, "no built-in law moves a closure row" (roadmap, Family 4). Since K1, a kind's base-form move at its rows is admitted; operators are still refused (§7.1) | First, an admission for operators at its rows. Today a row with forms stays inert: any operator that names it is refused, the coupling's reads included (`species_registry.py`:783–813) **(code)**. So is any operator that names or moves a held closure row, ligands included (:947–950). Then an operator's read of a form fraction. A ligand may not have forms of its own (`species_registry.py`:36), so a repressor bound by an inducer cannot also be a promoter's ligand |
| `hill_regulated_two_state@1`, the regulatory state | Kinetic | No | One state per cell | Judged within the coupling's scope | Mass action only in its linear regime. It holds slow, chromatin-like states well: retention 1/k_off, writes at events |
| `site_occupancy@1` | Kinetic | **Yes** | Patches and contacts only (`operators/site_occupancy.py`:4–6) | Judged (FR-3, 51 of 51) | A node owner, for sites on DNA in a cell |

**The discriminator.** Does bound factor have to leave the free pool?
- If promoters and decoy sites are few against the factor, it does not. B1′'s Hill factor or the
  regulatory state serve, and both are on main.
- If they are many, or the factor is scarce, it does. Then the closure (at equilibrium) or the sites
  (kinetic) are needed. The sites need a node owner. The closure needs more: an admission for
  operators at its rows, beside seam C's rule for kinds (CORE_SEAMS §5.2), and then a read.
- The ligands are held too. A closure holds its binders' totals and the total equivalents of every
  ligand they bind at its node. "An operator that names a held species, or moves one in the step,
  is refused" (`species_registry.py`:947–950) **(code)**. So today a transcription factor that
  turnover or synthesis writes, or that the coupling reads, cannot be a closure's ligand. Only a
  kind whose law reads the closure may move its rows, and no shipped kind does yet (:945–946).

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
- The registry now holds moieties, and `check_moieties` refuses a kind's mode or a declared
  free-energy entry that changes one. An operator's own moieties stay its own until an
  operator-contract hook reports them. A's operator brings that hook (§7.6).

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
- Each cited reaction energy enters as a `FreeEnergyEntry` in kJ/mol, with its basis and a
  temperature-free `dG_RT_offset` (a value at pH 7 puts ν_H ln 10⁷ there). The registry converts it
  at the world's temperature and compares it with its potentials (seam E; §7.1).

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
  short, through the saturating draws of §2.3. Held fuel would only record the supply.

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
- **Refreshed after D235:** the charged path now exists as data, the named set `beard2005@1`. What
  an operator still lacks to use it is in §7.2.

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
| `species_regulated_availability@1` (judged) and `@2` (B1′; development) | A Hill factor of a species, or a regulatory state, sets @3's channel or junction availability, or a routable rate in its target's own half-steps. F lies in [b, 1], the scheduled rate is the maximum, and each route declares an operating range | Initiation's regulation | A new target is one row in `OPERATOR_TABLES` (:149–154). FR-7's F3 added its producer that way, as a recorded exception naming the operators owner. F3 was on its branch when this note was written, and is on main since 5dc63d38 (§7.1) |
| `local_species_reactions@1` (judged within MG0c's scope) | Driven mass action and Michaelis–Menten with Hill factors; passive detailed balance; integer moieties. A passive reaction has molecularity at most 3 on each side, and a driven one an order of at most 3 (`MAX_MOLECULARITY`, :156, :535–548); 16 species | Recharging (NMP to NTP, PPi to Pi); small phenomenological networks | It cannot carry polymerisation: a product takes 10²–10⁴ monomers, an order far above 3. Degradation to L monomers is admissible as a driven reaction of order 1, since products are not capped, but a driven route books its ΔG as signed work, not heat (S) |
| `rapid_binding@1` (compared) | A multi-ligand closure over binders whose forms the registry declares | Equilibrium occupancy | An admission for operators at its rows, since no operator may name a row with forms (`species_registry.py`:783–813) or a held closure row, ligands included (:947–950); then a read of form fractions; nested binders, for induction |
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
   - **Elongation:** the Erlang chain. Each stage's rate is first order in its complexes and
     saturating in each monomer and fuel row it draws, κ·c/(K + c) per row (S).
     - The 4D minimal-cell model's elongation reads its NTP and charged-tRNA pools the same way
       (PAPER_REVIEW_WHOLE_CELL §2.3).
     - So a draw slows as its row runs short, and a positivity-preserving step cannot overdraw
       it. A zero-order draw could, which is why the producer's precursor draw is first order.
     - Constant speed is the saturated limit.
     - Hofmeyr, Gqwaka and Rohwer 2013 give a generic rate equation for catalysed
       template-directed polymerisation that includes monomer saturation **(checked**, abstract
       only; whether it is reversible was not confirmed).
   - **Degradation:** first order, returning monomers, with fuel where declared.

   **The numerical method is open.** The producer's half-step is exact because its rates are
   frozen and its chain is linear. Here the rates depend on the state: initiation on how many
   machines are engaged, and each stage on its rows. Frozen over a half-step, that dependence is
   first order. Three ways keep the composite second order:
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
   waits on an admission for operators at the closure's rows, the binding owner's, since the
   registry refuses the coupling's reads of a held or multi-form row today.
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
- **Settled for A after D235 (§7.5):** recharging is the operator's own route, and A's worlds
  declare no fuel regenerator. So A needs no two-writer ruling. The question returns only for a
  world that adds a regenerator.

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

*Chosen by D235. §7 refines this option against main at e0b1d3b8; where the two differ, §7
applies.*

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
- The two-writer ruling for D152's recharging (§2.4), with its splitting check. *After D235 this
  is not needed: §7.5 puts recharging in the operator.*
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
- **The class that would pass: a closed batch of cell-free expression.** The components are
  defined inputs, and the exhaustion of precursors and fuel is the measured response. Calibrate on
  one condition, one template or energy level. Predict the others: saturation by finite machines,
  and the plateau that the fuel budget sets.
- **None found that passes all three tests** (a numeric deposit under CC BY or CC0, measured
  exhaustion, a closed batch) **(checked**, 20 November; Europe PMC with licence filters and
  Zenodo; figshare and Dryad not searched):
  - Marshall and Noireaux 2019 (*Sci Rep*, CC BY): extract-based, data "on request", and a fitted
    model with no held-out test. The project never contacts authors (D173), so "on request" is
    closed to it.
  - Doerr et al. 2019 (*Phys Biol*, IOP's standard licence, no deposit): PURE, a defined
    composition, with NTPs and amino acids measured over 3 h.
  - Stögbauer et al. 2012 (*Integr Biol*, licence not found) and Karzbrun et al. 2011 (*PRL*, APS
    licence): no deposit found.
  - Near misses: Carrara et al. 2018 (*Data*, CC BY article; its dataset's licence unclear; protein
    traces only, over 27 PURE compositions) and Sato et al. 2024 (*Molecules*, CC BY; ATP measured,
    data on request).
- **The same search carries a warning for A.** In PURE, Doerr et al. found that "neither NTPs nor
  amino acids are depleted significantly enough to explain the observed translation rate
  profiles". The LMU thesis behind Stögbauer et al. 2012 reports that 4 mM fresh NTPs did not
  restart synthesis at the plateau, and fresh ribosomes did. So a model whose only limit is
  exhaustion would fail there, and that failure would name the missing mechanism: machine
  inactivation (S).
- **So A's first acceptance is numerical only.** The nearest candidate for a biological prediction
  is option D's period, once its delay has a measured source (§4.4).

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
- **An admission for operators at the closure's rows.** Today any operator that names a row with
  forms is refused, the coupling's reads included (`species_registry.py`:783–813), and so is any
  operator that names or moves a held closure row, the ligands included (:947–950). Seam C's §5.2
  admits a kind's move whose law declares its stoichiometry in base forms; no rule yet admits an
  operator. Until one does, B's repressor is a fixed declared total, one world per repressor
  number. The rule is the binding owner's.
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

**The biological target.** The *E. coli* lac series, in which parameters fixed on one condition
predict others **(checked**, 20 November).
- **Calibrate:** Garcia and Phillips 2011 (*PNAS*, not CC) fitted the operator binding energies on
  one strain and predicted the repressor numbers of five others, which immunoblots matched within
  error. Their supplement's global fit over all strains gives slightly different energies, and
  later papers use those.
- **Predict, single site:** Brewster et al. 2014 (*Cell*, Elsevier's open archive, not CC)
  predicted fold-change against counted repressors "without any free parameters at all", from
  earlier affinities.
  - Its single-site points, with Garcia's, are in a public repository under the MIT licence
    (RPGroup-PBoC/mwc_mutants, `data/Garcia2011_Brewster2014.csv`; the repository's README names
    CC BY 4.0 for creative works and MIT for software, and does not name data).
  - **But a Hill factor on main already reproduces single-site fold-change** (§1.3). So this
    tests B1′'s factor, not the closure.
- **Predict, titration:** Brewster's multi-copy and competitor-plasmid measurements are the test
  that needs the closure's conservation. Two of its inputs were fitted (the competitor plasmids'
  copy distribution, and plasmid copy number per cell-cycle bin). No permissive deposit of them was
  found, in four of the organisation's 81 repositories. So they serve analysis only, with bare
  numbers cited (D227).
- **Predict, induction:** Razo-Mejia et al. 2018 (*Cell Systems*, **CC BY**) fitted the inducer
  constants on one strain and predicted 17 others with no further fitting. O3 and the two largest
  repressor numbers deviate systematically. Its data are in RPGroup-PBoC/mwc_induction, under MIT.
  This is the cleanest test on open terms (the article CC BY, the data in an MIT repository,
  subject to §6 Q6), but it needs nested binders (an inducer-bound repressor as
  a promoter's ligand), which the registry refuses today.

**Rows, steps, molecules, fuel.**
- **Rows:** 8.
- **Steps:** hundreds, at seconds.
- **Molecules:** in *E. coli*, one molecule is 1.7 nM. A repressor at about ten copies (named from
  memory) sits below the floor, and the closure is the mass-action (grand-canonical)
  approximation (S).
- **Fuel:** none. Binding is passive, and the closure books its own free energy.

**Owners and seats.** The binding and operators owners, both on D234's critical path, plus two
seats.

**Effort (estimate): 9–14 agent-days,** including about 1–2 for the operator admission at the
closure's rows.

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

**The biological target.** Single-molecule FISH distributions **(checked**, 20 November).
- **The prediction series:** Jones, Brewster and Phillips 2014 (*Science*, not CC) made what they
  call "zero-parameter predictions" of the mRNA Fano factor against the mean, for 18 constitutive
  promoters, for a tuned on-rate and for a tuned off-rate.
  - Their counts are in RPGroup-PBoC/chann_cap (`data/mRNA_FISH/Jones_Brewster_2014.csv`), under
    MIT.
  - Independence is partial. The off-rate is an in vitro single-molecule rate, scaled between
    operators. The on-rate comes from repressor numbers inferred from the measured mean
    repression, not counted. Calibration and prediction must be split by condition.
- **Mammalian:** Raj et al. 2006 (*PLoS Biology*, **CC BY**) measured mRNA counts and fitted a
  bursting model. Raising the transcription factor's level increased burst size, not frequency.
  Its rates are fitted, so a judged comparison needs a held-out condition.

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
- For F6, more than B's read. The mRNA becomes a binder with forms, which the synthesis operator
  makes and degrades, and the microRNA is a ligand that synthesis makes. The registry refuses an
  operator that names either (`species_registry.py`:783–813, :947–950), so F6 waits for an operator
  admission at the closure's rows (§4.2).

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
- **The split, honestly.** The half-lives are measured inputs. The delay is not, yet.
  - Transcribing a gene takes minutes at RNA polymerase II's speed: §2.5's 10 kb case takes about
    3 minutes.
  - Monk's analysis is quoted as using 10–20 minutes from promoter to cytosolic mRNA (secondary
    sources, not read). Most of that is processing, splicing and export, which would be declared.
  - A declared delay sets the period. So the period is calibrated, not predicted, until the delay
    has a measured source. Hes1's gene length is not in hand either.
- **The weakness.** Whether it oscillates at all also depends on unmeasured parameters: the Hill
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
| New engine pieces | One operator | Operator admission at closure rows, closure read, occupancy source, node host | Count block, contract change | Feedback route evidence; for F6, the same admission |
| Rows of 16 | 13–15 | 8 | Counts outside rows | 12 |
| Steps | 10⁴–10⁶ at 1 s; A2 at 1 ms | 10² | Events | 10³–10⁴ |
| Fuel | Finite, as stoichiometry | None | None one way | Finite |
| Core owners touched | One table row; the producer (A2) | Binding, operators | Operators, run view | As A |
| Seats | 2 | 2 | 2 | As A |
| Effort (estimate) | 9–13 | 9–14 | 14–22 | 6–9 more |
| D145 and D218 asks | Lift D145 for polymerisation laws (F10); D218 unchanged (open loop) | Lift D145 for occupancy | Lift D145 for the low-copy regime | Lift D145 for networks; confirm D218 covers TF feedback |
| Biological target | None found that passes; numerical first | Lac series: single site in an MIT repository (subject to §6 Q6) but a Hill factor's test; titration analysis only; induction CC BY but needs nested binders | smFISH noise series in an MIT repository (subject to §6 Q6), partly independent | Hes1's period: a candidate once its delay is measured |

### 4.6 The recommendation: A, then D and B, then C

*The user chose A (D235); §7 is its plan.*

**A first.**
- It is the physics the user asked for: polymerisation, finite precursors and fuel, machines,
  delays, turnover, and one account. Every consumer needs it first (§5).
- It extends one known kernel in new files, and touches no core owner's file but one table row.
  So it does not slow D222's or D234's queues.
- Its first acceptance is exact: closed forms for the means at any copy number, the account and the
  energy. The references' SSA measures the low-copy gap before any stochastic block is built.
- It needs no new door in D218, being open loop. It needs only a narrow, explicit lift of D145 for
  polymerisation laws (F10).

**Why not B first.**
- Its biological test on open terms, single-site fold-change in an MIT repository (subject to §6
  Q6), is one a Hill factor on main already passes.
- Its titration test, the one that needs the closure, has no permissive deposit.
- It needs an operator admission at the closure's rows from the binding owner, who is on D234's
  path (§4.2).

**The biological comparison.** No closed-batch dataset passes today (§4.1), so A's first acceptance
is numerical. The nearest biological prediction is D's Hes1 period, once its delay has a measured
source. The search is repeated when A's protocol is drafted, since figshare and Dryad were not
searched. A comparison is registered on its own, as D151 keeps every reviewed candidate.

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
| **The gap-junction replication's F6** | "The modified Hill (lambda) form and the microRNA-target binding partition as checked laws, with the regulatory coordinates' physical scale and time unit declared" | The λ form is B1′'s basal level, on main. The partition needs an operator admission at the closure's rows, since synthesis writes both its mRNA binder and its microRNA ligand, and then B's occupancy source. D carries the network | The switch already runs on D152 sources, as development (its §3) |
| **The REVERT plan's group 2** | "A gene-regulation layer with sourced kinetics, coupled to cells" | D's declared networks | Group 1's Boolean reproduction runs out of process with approval (D138). No patient-specific rule set becomes an engine model (D136) |
| **FR-7** | Its precursor, today a declared pool or D150's supply | A2: the translated protein becomes the precursor | The producer's refusal of other authors changes (§4.1) |
| **Machines** | U4: the ribosome and RNA polymerase, held under D145 (D209) | A, as aggregate machine pools; individuals with FR-13's M4 after C | — |
| **Also** | Track R's pulse networks (INVENTORY_COUPLING §4.5); partial reprogramming's cross-lineage test, logged as "a second-tier benchmark for the future gene-regulation layer" (D151); the FEP track's regulated synthesis (held, D179); GRN_WETLAB's candidate networks | D and B | GRN_WETLAB's yeast model is node-to-node logic. It tests the layer once the layer exists, not as its first acceptance (INVENTORY_COUPLING §4.6) |

## 6. The user's decisions

Each question has a recommendation (S). **After D235:** question 1 is answered for option A, and
question 5 has a better answer in §7.2. The others stay open.

1. **D145's hold.** Lift it for the first milestone's laws only: polymerisation (F10) for option A,
   with machines' U4 answered as aggregate machine pools? Cortés-Poza Phase 1 and catalogue stage 3
   stay held.
   - Gene identity needs no catalogue code: a template carries D150's identity form (`catalogue`,
     `evidence`), and law IDs never name proteins.
   - *Recommended:* yes, for A.
   - **Answered (D235):** option A, built when seats free.
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
     This needs the two-writer ruling (§2.4), and it gains from `finite-fuel-v1`. *After D235:
     §7.5 puts recharging in the operator and declares no regenerator for A, so A needs no ruling.*
   - The machinery's non-stoichiometric costs, and a regulatory state's maintenance, wait for seam
     E's fuel block. That covers the coupling note's §6.4 Q6, D150's question 11 and D152's
     question 10 in one design (D217).
   - *Recommended:* both.
5. **Charge.** Nucleotides and RNA as neutral formula units in version 1, declared, with charged rows
   later through FR-15 S1 and the nucleotide forms? The cost: until then an expression world does
   not share its ATP rows with a mitochondria world (§1.5). *Recommended:* yes.
   - **Refreshed (§7.2, §7.4):** charged ATP from a named set is now the better answer. It waits on
     two pieces: an operator admission at the closure's rows, and the set's phosphorus moiety reaching
     the world's nucleotide rows. So A registers the neutral reduction, shown exact while pH and free
     Mg²⁺ are held, and the charged form follows as its own registered arm.
6. **Data licences.** Cells is commercial open source (D173).
   - Judged results rest on permissive data (CC BY or CC0, and the deposit's own terms checked).
     Non-commercial data serve analysis only and are never committed. Bare published numbers are
     cited (D173, D227).
   - May *E. coli*, a data-only organism under D179, supply a general law's biological check, as
     ATP synthase's check uses bacterial enzyme numbers?
   - Does data in a public code repository under the MIT licence count as a permissive deposit,
     where the article itself is not CC? The lac and noise counts above sit in such repositories
     (§4.2, §4.3). Data offered only "on request" stays closed, since the project never contacts
     authors (D173).
   - Running a paper's own model out of process stays the user's approval per paper (D138).
   - *Recommended:* yes to all four.
7. **The order.** A first, after D222's core and FR order, the Xenopus lane (D225) and D234's
   mitochondria lane? Its two seats are the lead's count within seven. *Recommended:* yes, when two
   seats are free.

## 7. Option A, as chosen (D235)

The user chose option A on 20 November 2026 (D235, e0b1d3b8): "one gene, open loop, deterministic,
expression as templated polymerisation with its ATP cost. It is judged against exact references
only, and starts when seats free." The note's other questions stay open. This section refreshes the
note against main at e0b1d3b8 and adds what D235 asks for A. Code is cited `file`:line at e0b1d3b8.

### 7.1 What main holds now that bears on A

| Landing | What it is (code) | What it means for A |
| --- | --- | --- |
| **Named potential sets** (8e7a41b3, 11dc95c5) | `beard2005@1`: charged ATP⁴⁻, ADP³⁻ and Pi²⁻, with MgATP, MgADP and H₂PO₄⁻ forms, on references at 0 for H⁺, K⁺, Mg²⁺ and the other conserved quantities. A set is applied whole by `with_potential_set`, with no mixing, and its name versions its derivation. It holds no AMP ("AMP waits for an adenylate kinase law", `registry/species_registry.py`:907–908), no GTP and no other nucleotide | A's fuel can be the mitochondria's own ATP rows (§7.2). Its other rows are the world's |
| **`beard2005@2`, planned** | @1 plus AMP²⁻, which binds nothing, and K_AK matched in base forms at a declared free Mg²⁺. It lands with the user's repairs ruling: the lead's brief, and the mito lane's reading note (77e13b4a, on branch mito-lane). Not in the registry yet | §7.2 is written against it. The sheet names no set (§7.7) |
| **Registry moieties and `check_moieties`** | The model declares its moieties, and the check refuses a kind's mode or a declared free-energy entry that changes one. "An operator's own moieties (D152's reactions) stay its own until an operator-contract hook reports them (the operators owner's follow-up)" (`species_registry.py`:138–148, :1175) | The hook lands with A (§7.6) |
| **`FreeEnergyEntry` in kJ/mol** | `dG_kJ_mol` with its basis and a temperature-free `dG_RT_offset`, converted by the registry at the world's temperature (`registry/kind_registry.py`:593–620) | A's cited reaction energies enter this way: phosphodiester formation, PPi hydrolysis, peptide bonds and ATP hydrolysis. Seam E's check then ties the world's own nucleotide and polymer potentials to the set's references |
| **Moved fuel at closure nodes, K1** (4704abd1), and **the binder-form deferral** (80f9f837) | A kind's base-form move of a row that a closure holds, ATP with its forms included, passes to §5.2's admission. "Every inner route and every operator" stays refused | Operators, A's included, still cannot move the set's ATP (§7.2) |
| **The cycle kind's monomial form, K6** (d9342fcf, 7b1ad0dc) | S as a monomial in activities, with saturating factors, and k a number or a constant cited in kJ/mol (`laws/cycles/forms.py`:28–37) | A's stage kinetics can be written as this form's data: an order in the monomer and a factor (1 + a/K)⁻¹ (S). A stage of L/m residues carries its affinity per residue, as the form's affinity share does. The share is capped at 8 (`MAX_SHARE`, :91), so the sheet either takes per-residue terms or asks the kinds owner to raise the cap |
| **FR-7's F2 and F3, and pools** (de65d033, 5dc63d38, aa4aa9f4) | The population abundance is a B1′ source, the producer's assembly rate is a B1′ target, and the producer declares initial units in transit; all development | A2's path is on main. The routable-target table now has three rows (`operators/species_regulated_availability.py`:175–181). A adds a fourth, as F3 did |
| **Not yet** | `finite-fuel-v1` has no world (it follows MT-1a); seam E's fuel block; an operator's admission at the closure's rows; a node host for seam A; `beard2005@2`; K3, chemistry at P, on a branch | §7.2, §7.3, §7.10 |

### 7.2 Charged ATP beside mitochondria, against `beard2005@2`

**The set it would use.** `beard2005@2`, as the lead's brief of 20 November describes it, with the
mito lane's reading note (77e13b4a, on branch mito-lane): @1 plus AMP²⁻, which binds nothing in the
source, and adenylate kinase's constant K_AK matched in base forms at a declared free Mg²⁺ (0.153
at 1 mM, 0.389 at 3.81 mM, 0.491 at 5 mM, as the note reads it). It lands with the user's repairs
ruling and is not in the registry yet. So its moiety weights here are this note's reading (S):
adenine over ATP, ADP and AMP; phosphorus over Pi, AMP, ADP and ATP, at 1, 1, 2 and 3.

**Yes, in principle.**
- A world applies the set. Its ATP, ADP, Pi, H⁺, Mg²⁺ and K⁺ rows then carry the set's potentials
  and forms, as MT-1's will, and AMP too where the world declares it.
- The expression rows (the regulator, NTP, NMP, mRNA, amino acid and protein) are the world's own.
  Their potentials come from the operator's cited entries through seam E, anchored on the set's
  references.
- ATP then has one authority across expression and mitochondria, and §1.5's neutral-lump limit goes.

**Charge and moieties per residue (S; water omitted, PPi hydrolysed at once).**
- **Translation's fuel stays inside the set.**
  - Aminoacylation: ATP⁴⁻ → AMP²⁻ + 2 Pi²⁻ + 2 H⁺.
  - The elongation factors' two GTP, counted as ATP: 2 ATP⁴⁻ → 2 ADP³⁻ + 2 Pi²⁻ + 2 H⁺.
  - With adenylate kinase folded in, the residue's whole draw is 4 ATP⁴⁻ → 4 ADP³⁻ + 4 Pi²⁻ + 4 H⁺.
  - Each conserves charge and the set's adenine and phosphorus. @1 could carry only the folded
    form; @2 carries either.
- **Transcription and recharging still cross the set's boundary.**
  - Transcription takes the world's NTP⁴⁻ and gives the chain one more residue, with one more
    negative charge, plus the set's Pi from the PPi, and H⁺. The set's phosphorus rises by 2 per
    residue.
  - Recharging, NMP + 2 ATP → NTP + 2 ADP, moves two phosphates from the set's ATP to the world's
    nucleotide. The set's phosphorus falls by 2.
  - @2's AMP changes neither, so §7.2's second piece below stands under @2.
- **The mRNA row carries valence −L,** one charge per phosphodiester. Whether the field and the
  ledgers admit a row of valence near −10³ is a question for the capability probe.

**Rows under @2, against the cap of 16 (S).**

| World | Ions | The set's rows | The world's rows | Total |
| --- | --- | --- | --- | --- |
| A1, one gene, adenylate kinase folded | The heredity cell's four: Na⁺, K⁺, M⁻, P⁻ | H⁺, Mg²⁺, ATP, ADP, Pi | The regulator, mRNA, protein, NTP, NMP, amino acid | 15 |
| A1, one gene, AMP declared | Four | The same, and AMP | Six | **16, at the cap** |
| A1-M polymerase-limited: two templates, transcription only | Four | H⁺, Mg²⁺, ATP, ADP, Pi | mRNA₁, mRNA₂, NTP, NMP | 13 |
| A1-M ribosome-limited: one mRNA held, swept over amounts | Four | H⁺, Mg²⁺, ATP, ADP, Pi | mRNA, protein, amino acid | 12 |

- **A proton buffer, with no extra row.** The charged form releases H⁺ into the set's H⁺ row: four
  per residue in translation, one per residue in transcription, and more where degradation leaves
  phosphate monoesters to ionise. So the cell needs a buffer.
  - `proton_buffers` may name a declared row outside the set that declares no potential or forms
    (`species_registry.py`:1043–1071).
  - The heredity cell's anions declare neither (`validation/tissue/surface_pump_v3_fixtures.py`:259),
    so P⁻ can be the buffer.
- **So the charged expression cell still fits, with no spare row once AMP is declared.** Any further
  row then goes over: PPi kept as a row, GTP and GDP, or a second gene with its protein.
- **What changes where a world needs more:** the expression cell carries two background ions (K⁺ and
  one impermeant anion), not the heredity cell's four. A cell with no channels holds its ions only
  as inert background. That frees two rows, and its one anion is then the buffer. Otherwise a row
  must leave, or the cap rises by a D148 change with its guard world (D165).
- **A cell that also holds mitochondria does not fit.**
  - The set alone has 15 rows, and 16 with AMP.
  - Host P's world needs about 14–16 (CORE_LAWS_ROADMAP §2.2), and the expression rows add six.
  - That is past 20 rows once A's operator applies the cap.
  - So composing expression with mitochondria needs a third piece: the cap raised, a D148 change
    with its guard world (D165).
- **The world the charged arm would register:** an expression-only cell applying the set. That is
  the table's first row, with P⁻ as the buffer: 15 rows. It tests charge, and the drift of pH and
  free Mg²⁺ under the buffer. It does not test composition with mitochondria, which strengthens
  §7.4's (i).
- The neutral build needs 13 (§2.1).

**AMP's recycling.** If expression made AMP, something in the cell would have to run adenylate
kinase: chemistry at a node. D152 cannot name ATP once it has forms, and the cycle kind sits on
patches (§7.3). So expression folds adenylate kinase into its own stoichiometry: a declared
reduction, exact in net stoichiometry. AMP stays mitochondria's row.

**What it needs: two pieces for the charged expression cell, as under @1.** A third, the cap
raised, comes only when expression shares a cell with mitochondria (above).
1. **An admission for operators at the closure's rows.**
   - The set's ATP, ADP and Pi carry forms, so a closure holds them. The registry refuses every
     operator that names such a row (`check_two_form_rows`, `species_registry.py`:1392–1432), and
     K1's widening admits kinds only.
   - The protons released are the set's H⁺ row, which the closure also holds where it buffers.
   - This is the piece options B and F6 need (§1.3, §4.2): §5.2's base-form admission extended to
     an operator that declares its moves in base forms with every ligand written out, and a read of
     the closure's free forms at the operator's half-steps.
2. **The set's phosphorus moiety reaching the world's nucleotide and polymer rows.**
   - A set's moieties are required over the rows present, and a world may not reuse a set's moiety
     ID (`with_potential_set`, `species_registry.py`:1072–1082).
   - So a move that passes phosphate between the set's rows and the world's is refused by
     `check_moieties` (S, from the check's rule). That covers transcription and recharging, as
     above.
   - **Two ways:** a new set version naming the nucleotide rows, derived from cited reaction
     energies; or a rule that lets a world extend a set's moiety to rows the set does not name,
     never changing the set's own weights. Only the second reaches the polymers, each mRNA row
     carrying L phosphates. Both are the binding owner's.

**Owners and effort.** The binding owner (`registry/species_registry.py`) and the operators owner
(`operators/contract.py`). About 3–4.5 agent-days for both pieces (estimate). When the built form
is fixed is §7.4's question.

### 7.3 Why an operator, not a kind

Kinds are now admitted at a closure's rows: K1's moved fuel, and the binder-form deferral, under
base-form laws that read the closure. §5.2's admission is not the transporter's alone. So the
question is whether *a kind*, a new one with its own state axes, could host templated
polymerisation, or its fuel-consuming part, and so remove G5's first piece.

**The cycle kind as it stands cannot.** Its populations hold no cycle state ("It holds no cycle
states", MOLECULAR_MACHINES §1.2). A population's capacity is a declared k times its scheduled
availability (`kinds/transporter.py`:16–28, :64), not a pool of machines that complexes draw on and
return to.

**A new kind meets five constraints of the kind contract (code and MODULE_SYSTEM at e0b1d3b8).**
Kinds do carry state between steps, such as accumulators and patch damage, so state alone is not the
bar.
1. **No material held outside the inventory: rule (c).** "Material moves land in the shared
   inventory, and only own accumulators stay apart" (MODULE_SYSTEM_DESIGN §1, its version-1 limits).
   Residues in transit through the m stages are material. An operator holds such pools, as the
   producer's maturation pools are held. MODULE_SYSTEM §7 rates lifting rule (c) "moderate".
2. **No ledger of its own: rule (a).** A kind's ledgers fold into today's ten by role. The module
   note says of a new conserved count: "Operators already declare own ledgers ..., so such a module
   can be an operator". The machine identity (free plus engaged equals total) and the conversion
   ledger are such counts. MODULE_SYSTEM §7 rates lifting rule (a) "moderate" too.
3. **Hosts are patches and junctions.** `HOST_KINDS = ("patch", "junction")`
   (`models/surface_pump_v3.py`:2029). A soluble polymerase or ribosome needs a node host
   (MOLECULAR_MACHINES's N2), which is not built. K3 brings chemistry at P, still on a patch.
4. **In-step rates, not exact half-steps.** A kind's rates are evaluated at every stage of @3's step,
   as changes into the shared inventory (`registry/kind_registry.py`:256–262). The chain's exact
   uniformization half-steps, the producer's `exact_unit_chain_half_steps@1`, belong to an
   operator's split part.
5. **The door into production.** B1′'s rate routes reach an operator's `ROUTABLE_CONTROLS`. A kind's
   rates are reached through the kinds' routing door (`kind_registry.py`:246–254), which is a
   different mechanism. D218 names B1′ as the one door for state-mediated production feedback, so
   a kind's initiation would need the user to widen D218.

**The fuel draw alone** is no better. Four ATP per residue is stoichiometry. A kind's rate comes from
its own kinetics, and it cannot read the operator's elongation flux, which lives in the operator's
half-steps. Stateless node chemistry that is not tied to each residue, such as adenylate kinase,
could become a kind's on a node host. That would not remove the operator's own per-residue draw.

**Which constraint decides it: rule (c).** The residues in transit are material, and a kind may not
hold material outside the inventory.
- A kind could host the polymerisation only with rule (c) lifted, the machine ledger admitted under
  rule (a), a node host built, and D218 widened by the user.
- That is four changes, two of them to the kind contract, against G5's one admission. So G5's first
  piece stays.
- A node host for seam A (N2, 0.5–1 day in MOLECULAR_MACHINES §7) is still worth naming, as a later
  piece for stateless node chemistry.

### 7.4 The built form is fixed at the sheet's tag

References and registration come before any engine output. So the form A is judged in is fixed when
the sheet is tagged, not when G4 starts. Two orders:

| | (i) A registers the neutral reduction; the charged form is a later arm, registered on its own | (ii) A waits for G5 and `beard2005@2`, and is built charged |
| --- | --- | --- |
| Starts | When two seats are free | After G5's two pieces and @2 land. They are the binding owner's, on MT-1's path (D234, D235), with no date |
| References | G2: the neutral form's, and the sheet check's proof that the two forms agree while pH and free Mg²⁺ are held. The charged arm's own come later, from the same sheet, tagged before its engine output, since its content is the drift those hold fixed | The charged form's, at G2 |
| Registrations | Two: A now, and the charged arm later, against its own references | One |
| What A's judged items test | The chain, the account and machine sharing. None depends on charge while pH and free Mg²⁺ are held | The same, plus what the charged world lets drift |
| Composes with mitochondria's worlds | From the charged arm on | From the start |
| Its risk | The charged arm may find what the neutral form cannot see: pH or Mg²⁺ drift, or a valence of −L | It waits on pieces with no date, for judged items that gain nothing from charge |

**Recommended: (i).** A's judged claims are numerical, and none depends on charge under its declared
conditions. So waiting buys none of A's claims. The charged arm's content, the drift of pH and free Mg²⁺, is
what (i) registers later, with its own references from the same sheet.

**Either way, the sheet's check shows the reduction is exact (S).**
- **The potentials.** Each neutral row's standard potential is its charged base form's, transformed
  at the declared pH and free Mg²⁺: μ′° = μ°(base) − RT ln P(h, [Mg]), P the row's binding
  polynomial, plus its proton term. These are Alberty's transformed potentials (named from memory,
  not read), and the registry's named sets make the same split through `dG_RT_offset`.
- **The free energies.** For every move, the check computes ΔG in both forms over a grid of states at
  the declared pH and free Mg²⁺, and shows them equal to rounding.
- **The charge.** Every charged move conserves charge, so a node's charge and the field see no
  difference.
- **The rates.** Laws written on totals, or on free forms at a fixed fraction of the total, give the
  same flux in both forms.
- **So** every judged quantity is the same in both forms in a world whose pH and free Mg²⁺ are held.
  The charged arm adds what happens when they are not.

### 7.5 The two equation-shaping choices, settled before the sheet's tag

**Where recharging lives: in the operator, as a route of its own** (recommended, S).
1. **One account.** It closes the nucleotide loop in the operator's conversion ledger. Residues
   leave NTP for the chain, return as NMP at degradation, and become NTP again.
2. **One writer.** It keeps one writer of the NTP and NMP rows, so D152's one-writer rule needs no
   new ruling.
3. **The charged arm needs it there.** In the charged form D152 cannot name ATP at all. In the
   operator, recharging rides on G5's first piece, which A's charged arm needs anyway.
4. **It stays general.** One phosphoryl-transfer law, NMP + 2 ATP → NTP + 2 ADP, lumps the two
   kinases. It carries its cited ΔG° as a `FreeEnergyEntry` and the same saturating draws, beside
   the synthesis and degradation routes.
- **Against:** chemistry inside a polymerisation operator overlaps D152's role. It is bounded to the
  operator's own nucleotide rows, and D152 keeps every other reaction.
- **Fuel regeneration, ADP to ATP, is not the operator's.**
  - A1 declares finite pools sized so that the draws stay saturated over the horizon, with no
    regenerator. So no other operator writes the fuel rows, and A needs no two-writer ruling.
  - A world that adds a regenerator later brings that question back to the lead. That would be D152
    on the neutral form, or mitochondria's synthase, a kind, on the charged form.

**Per-residue terms, or a raised affinity-share cap: per-residue terms** (recommended, S, from the
code).
- **The physics.** One residue added is the elementary step, with affinity x_r. A stage of r = L/m
  residues lumps r of them, so its net flux carries the per-residue factor (1 − e^{x_r}), not
  (1 − e^{r x_r}).
- **The share is the same factor.** The monomial form's share term, −log Σ_{i<n} e^{ix/n}, makes
  S(1 − e^x) equal S′(1 − e^{x/n}). With n = r the two choices are one law. They differ only in
  where it lives and what it costs.
- **A raised cap costs every monomial world as built.**
  - `monomial_logs` carries the share as a static axis, `xp.arange(MAX_SHARE)`, in an [M, I, P]
    array for every mode of every monomial population (`laws/cycles/forms.py`:1408–1418).
  - Raising MAX_SHARE from 8 to r, of order 10²–10³, multiplies that work and memory everywhere. It
    also changes every monomial program, so crossrev moves: a new ID or a D148 round, on the kinds
    owner's file.
  - The geometric sum, Σ_{i<n} e^{ix/n} = (1 − e^x)/(1 − e^{x/n}), would remove the axis. But it is
    a new kernel, and it needs care near x = 0, where the sum tends to n.
- **Per-residue terms cost nothing outside A.**
  - A's own law writes each stage's flux with x_r, and books the moved amounts of r residues with
    their exact ΔG.
  - It declares a one-sided domain: x_r below a declared bound. A stage that would run back through
    initiation is refused, never repaired.
- **What A can still reuse:** the monomial form's data for its saturating draws (orders, saturating
  factors, constants cited in kJ/mol), at share 1.
- **The desk question for the kinds owner, after K3:**
  1. May an operator call `monomial_logs` at share 1?
  2. For laws elsewhere with n above 8, is the geometric closed form wanted?

### 7.6 The operator's moiety hook

**What (S).** `species_moieties(declaration)` joins `species_identities`, `species_potentials` and
`standard_free_energies` in the operator contract (`operators/contract.py`:500–518), with the
default (). It reports two things:
- the moiety weights the operator assumes for the rows it converts: residues per polymer molecule,
  L nucleotides for an mRNA and L amino acids for a protein;
- the net row stoichiometry of each move per unit of progress: per finished product for a chain,
  per molecule degraded, per recharging turnover.

**The check.** `check_moieties` reads it, as it reads kinds' modes and free-energy entries today.
- A weight that differs from the model's `moieties` is refused, as `check_potentials` refuses a
  second potential.
- A move that changes a declared moiety is refused, and named.
- Material in transit sits in the operator's own pools. Its own conversion ledger closes it, as the
  producer's `unit_chain` does.

**As built (G3; the lead's ruling of 20 November 2026): moves only.**
- The hook reports each move's net row change per unit of progress, not separate weights.
- A weight the operator assumes that differs from the model's moiety still shows. The move then
  changes the moiety, and `check_moieties` refuses it by name, for example "Operator
  templated_polymerisation@1's move chain tx: it changes moiety phosphorus by -1 per turnover".
- **A known limit:** a model that declares no moieties is not checked, so there the hook is not
  read and its shape is not checked.

**D152** can report its reactions through the same hook, which ends its private moiety authority
(one authority, the registry's). Whether that lands with A, or at D152's next version under
crossrev, is the operators owner's call.

**Who owns it.**
- **The operators owner:** the hook, its default and its contract check, in `operators/contract.py`.
  The registry's docstring already names it "the operators owner's follow-up".
- **The binding owner:** `check_moieties`'s reading of it, in `registry/species_registry.py`.
- **A's operator** implements it, as its first consumer.
- About 0.5–1 agent-day for the hook and the check (estimate).

### 7.7 The mitochondria pattern, for A

MT-1's pattern (CORE_LAWS_ROADMAP §2.4):
- its declared equations, the lane's laws appendix with its own check, tagged
  `mito-laws-appendix-2026-11-20` on branch mito-lane;
- code-blind component references, written from the appendix and the paper alone;
- a whole-organelle reference written from the paper alone, timestamped by a tag before any engine
  output (MR1, `mito-references-model-2026-11-19`);
- registration before the judged run.

A has no paper model, so its references come from the sheet alone. Each step below ends with its
tag before the next starts.

1. **The equation sheet** (`docs/TEMPLATED_POLYMERISATION_LAWS.md`, new; S). The lane agent states
   each law's physics only:
   - each move's integer stoichiometry, per stage and per route, with its charge and its moieties;
   - each cited reaction energy, as a `FreeEnergyEntry` with its source:
     - in kJ/mol with its basis and offset;
     - or, where the source cites an equilibrium constant, as a temperature-free dG_RT = −ln K. The
       sheet's recharging entry is entered this way (TEMPLATED_POLYMERISATION_LAWS §3.3; corrected
       with the sheet, 20 November 2026);
   - the rate laws: initiation, the m-stage chain with its saturating draws, degradation and
     recharging;
   - the machine identity and the account identities;
   - every declared, uncited value, labelled, and every reduction (the lumps), declared;
   - both forms: the charged one, and the neutral reduction that A registers (§7.4);
   - the two choices of §7.5: recharging as the operator's own route, and per-residue terms.

   **It is symbolic in the potentials.** It writes each row's μ° as a symbol and each cited reaction
   energy with its source, and it names no set version. A world names its source of potentials only
   at registration, so G1 does not wait for the user's repairs ruling.

   Its own check, `validation/gene_regulation/sheet_check.py` (new), does what `appendix_check.py`
   does for MT-1:
   - every move conserves charge and every moiety in integers;
   - each entry's ΔG° follows from the declared potentials;
   - the reduction is exact, as §7.4 sets out;
   - planted errors are caught.

   **Tag:** `gr1-sheet-<date>`.
2. **The code-blind references,** by a fresh agent that reads the sheet alone: no code, no model file
   and no engine output. They are R-chain, R-account, R-share, R-machine (§7.8) and R-noise, for the
   neutral form, in `validation/gene_regulation/references/` (new). **Tag:**
   `gr1-references-<date>`, before any engine output.
3. **Registration** of A's protocol (`validation/gene_regulation/protocols/`, new), in the neutral
   form (§7.4): its judged items and tolerances, its arms and plants, and its non-claims (§7.9). It is
   registered and tagged before the engine runs any of its worlds.
   - **What it names for its potentials.** The neutral form cannot apply a set:
     `with_potential_set` refuses a valence unlike the set's, and the set's ATP is −4 where the lump's
     is 0. So the neutral world declares its own potentials, transformed at the declared pH and free
     Mg²⁺ by the sheet's check from a named source, and the registration names that source.
   - **With adenylate kinase folded, A needs only ATP, ADP and Pi from the set.** `beard2005@1` holds
     them, so A does not wait for @2.
   - **The charged arm** registers later. It has its own references, written by the same rule from
     the same sheet, and tagged before its engine output (§7.4).
4. **The engine work** lands as development, compared against the references in every gate.
5. **The judged run,** once, from a clean snapshot.

### 7.8 The arms

**A1, the expression unit.**
- One gene, open loop, in a cell with no channels.
- The regulator comes from D150's turnover, through B1′.
- Lifetimes are real or declared, at second-scale steps.
- It is judged against R-chain and R-account, with §4.1's plants.
- **What judges the dynamics.** A1's pools are finite, with no regenerator (§7.5), so the draws
  drift a little over the horizon. The independent stiff ODE, from the same sheet, judges the
  trajectories. The closed forms (R-chain's, and R-machine's below) are limits, compared within a
  declared bound that the pools' drift over the horizon sets.

**A1-M, the machine-limited arm** (D235). Machines are scarce against templates.
- **Polymerase-limited first.** Gene copies are declared data, so a sweep over copies is a
  parameter: one world per copy number, or a batch. Ribosome-limited comes second, with the mRNA
  held: its degradation off, and its amount declared per world.
- **Monomers and fuel saturate,** so the chain's time τ = L/v holds.
- **R-machine's closed form (S).**
  - At steady state the engaged machines are E = Jτ. This is Little's law, exact for the chain's
    mean.
  - The free machines are F = M − E, and initiation is J = kTF.
  - So J = kTM/(1 + kTτ). It rises linearly at small T and saturates at M/τ.
  - With two genes, J_g = k_g T_g M/(1 + Σ_h k_h T_h τ_h): each takes its share of one budget.
  - The transient comes from R-share's stiff ODE.
- **Its own plants.** Each must fail one of the arm's judged items: the J–T curve, or the machine
  identity at every row.
  1. **Initiation reads the total machines, not the free ones.** That removes the saturation.
     - It is registered at a T where F stays positive, T = 5 (λτ ≈ 0.5). There initiation on total
       machines reads J ≈ 1.5 J*.
     - Nearer the saturated end, at T ≥ 10, the same edit drives F below zero, and the engine would
       refuse the step rather than yield a J.
     - The lead's ruling of 20 November 2026; TEMPLATED_POLYMERISATION_LAWS §5.2.
  2. A machine is not returned at release. That breaks free plus engaged equals total, and drains
     the budget.

**A2, the coupling to Vm** (development, not judged).
- The protein becomes FR-7's precursor, at 1 ms with synthetic lifetimes.
- It waits on the producer admitting a precursor that the operator writes, and on FR-7's own
  protocol.

### 7.9 What A does not claim (registered)

The protocol's scope lists these as non-claims, so that no reader takes them as tested.
1. **No biological claim.** Every judged item is numerical, against exact references. No dataset is
   compared, since none passes (§4.1).
2. **Means only.** No distribution, noise or burst is judged. R-noise's mean-field gap is reported,
   not judged.
3. **Open loop only.**
   - No feedback and no cascade: no product regulates any gene.
   - Occupancy is a given Hill factor or regulatory state.
   - No transcription factor is sequestered.
4. **No machine physics beyond capacity.** No inactivation (the cell-free stall of §4.1), no traffic
   or queuing on a template, no polysomes, no premature termination, and no proofreading beyond the
   declared stoichiometry.
5. **No processing.** Splicing, capping, export and folding are not modelled. A delay for any of them
   is a declared stage, and labelled.
6. **No growth, dilution or division.**
7. **No organism.** Rates, lengths and copy numbers are declared, or cited as orders of magnitude.
   Nothing is claimed for any species.
8. **The lumps are reductions:** one NTP row, one amino-acid row, GTP as ATP equivalents, AMP folded
   by adenylate kinase, and PPi hydrolysed at once. There is no claim per nucleotide, amino acid or
   tRNA.
9. **Charge.** The neutral reduction claims no electrical or pH effect of expression. The charged
   form claims no Mg²⁺ or pH dependence of elongation beyond its declared kinetics.
10. **A2 is development.** It makes no claim on FR-7's loop, on Vm or on FR-8's timescales.
11. **No gene-network layer.** No regulatory network is judged, and D218's door is not exercised.

### 7.10 The build plan (estimate)

| Step | Owner | Files | Agent-days |
| --- | --- | --- | --- |
| G1. The sheet and its check; its tag | The gene-regulation lane agent (a new seat) | `docs/TEMPLATED_POLYMERISATION_LAWS.md`, `validation/gene_regulation/sheet_check.py` (new) | 1–1.5 |
| G2. The references; their tag | A fresh references agent (a new seat), reading the sheet only | `validation/gene_regulation/references/` (new) | 2–3 |
| G3. The moiety hook | The operators owner; the binding owner for `check_moieties` | `operators/contract.py`; `registry/species_registry.py` | 0.5–1 |
| G4. The operator and its laws | The lane agent | `operators/templated_polymerisation.py` (new). Law modules under `laws/` (new); the F owner says whether they take an interface of their own. One row in `operators/species_regulated_availability.py`, a recorded exception naming the operators owner, as F3's was | 5–7 |
| G5. For the later charged arm: operators admitted at the closure's rows, and the set's phosphorus moiety reaching the world's rows | The binding owner; the operators owner | `registry/species_registry.py`; `operators/contract.py` | 3–4.5 |
| The charged arm's references, and the operator's charged-form work (later) | A references agent, from the sheet alone; the lane agent | `validation/gene_regulation/references/`; the operator | 3.5–5.5 |
| G6. Worlds, the protocol with its non-claims, registration, and the judged run | The lane agent; the lead registers | `validation/gene_regulation/` (new) | 1.5–2.5, plus CPU minutes |
| A2's producer edit (development) | The operators owner, who carries FR-7 (D234) | `operators/population_unit_turnover.py` | About 0.5 |

**The order (§7.4's (i)).**
- G1, then G2, each with its tag. G3 runs beside them.
- A's registration, in the neutral form, needs only G2's tag, and comes before any run of its
  worlds. So G4's development tests use other worlds, and A's judged run comes last.
- The charged arm follows G5 and `beard2005@2`: its own registration, against G2's tagged
  references, then its judged run.

**In all:**
- **Effort:** about 10.5–15.5 agent-days for A.
- **The charged arm adds about 7.5–11.5 more** (estimate):
  - G5's two pieces, 3–4.5;
  - its own references, from the same sheet, 1.5–2.5;
  - the operator's charged-form work, 2–3: closure reads at the half-steps, base-form moves, H⁺
    moves, and a valence of −L. G5 covers only the registry and the contract;
  - its registration and judged run, 1–1.5;
  - not priced here: a field-side owner for the charge the operator holds in transit. The node's
    charge must count the growing mRNA's −1 per residue (TEMPLATED_POLYMERISATION_LAWS §1.3).
- **Composing with mitochondria** adds the cap's raising (§7.2), which is not estimated here.
- **Elapsed:** about 6–9 working days for A with two new seats (estimate).

**Seats.** Two new seats: the lane agent (substantial coding) and the fresh references agent. The
operators and binding owners join part-time. The lead counts them within seven, as D235 says: "starts
when seats free".

**Settled before the sheet's tag (§7.5):** recharging lives in the operator, and A's worlds declare
no fuel regenerator, so A needs no two-writer ruling. Per-residue terms need no change to the
monomial form.

**Still the lead's before G1:** the sheet's name and its folder; and the desk question for the kinds
owner after K3 (§7.5).

**Tests (D224):**
- the kernels as rows of a parametrized pure-function test;
- one comparison file, through the references' interface;
- at most one compiled-world file, stating its seconds and its reason;
- an expected addition of about 1–2 CPU-minutes to tiers 1 and 2 (estimate).

**Risks:**
- the numerical method under machine sharing and saturating draws (§2.3);
- the timing of G5's two pieces, for the charged arm;
- the 16-row cap: the charged arm is at 16 rows with AMP declared (§7.2);
- the per-residue potentials' sources;
- a valence of −L on the mRNA row.

## Sources

**Read for §7, at e0b1d3b8:**
- `registry/species_registry.py`: the named sets and `beard2005@1`, the moieties and
  `check_moieties`, `check_two_form_rows` and its deferral to the closure.
- `registry/kind_registry.py`: `FreeEnergyEntry`.
- `laws/cycles/forms.py`: the monomial form and `monomial_logs`' share axis.
- `kinds/transporter.py`: the population axis's hosts, capacity and schedules.
- `operators/contract.py`: the species hooks.
- `beard2005@2` as the lead's brief of 20 November describes it, with the mito lane's reading note on
  K_AK (77e13b4a, `validation/mitochondria/beard2005_cardiac.py`, branch mito-lane). The set itself
  is not in the registry yet.
- `operators/species_regulated_availability.py`: the routable-target table.
- The commits 4704abd1 (K1) and 80f9f837 (the deferral), and D235.
- CORE_LAWS_ROADMAP §2.4, on main.
- The mitochondria lane's laws appendix, on branch mito-lane at aae79b1f, and the tags
  `mito-laws-appendix-2026-11-20` and `mito-references-model-2026-11-19`.

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
- **The lac series** (publisher pages, PMC copies and the repositories' licence files):
  - Garcia HG, Phillips R (2011) *PNAS* 108:12173–12178, doi:10.1073/pnas.1015616108. PNAS's
    licence, not CC. One-strain fit, then five strains predicted.
  - Brewster RC et al. (2014) *Cell* 156:1312–1323, doi:10.1016/j.cell.2014.02.022. Elsevier's open
    archive, not CC. No deposit stated.
  - Razo-Mejia M et al. (2018) *Cell Syst* 6:456–469.e10, doi:10.1016/j.cels.2018.02.004. CC BY 4.0.
    Code and tidy data in RPGroup-PBoC/mwc_induction, MIT. Zenodo 10.5281/zenodo.1163620's licence
    field reads "other-open". Its SI on CaltechDATA is CC BY-NC.
  - Jones DL, Brewster RC, Phillips R (2014) *Science* 346:1533–1536, doi:10.1126/science.1255301.
    Not CC. Counts in RPGroup-PBoC/chann_cap, MIT.
  - RPGroup-PBoC/mwc_mutants: Garcia's and Brewster's single-site points, MIT.
- **Cell-free time courses:** Marshall R, Noireaux V (2019) *Sci Rep* 9:11980,
  doi:10.1038/s41598-019-48468-8 (CC BY; data on request). Doerr A et al. (2019) *Phys Biol*
  16:025001, doi:10.1088/1478-3975/aaf33d (IOP standard licence; no deposit). Stögbauer T et al.
  (2012) *Integr Biol* 4:494–501, doi:10.1039/c2ib00102k (licence not found), and its LMU thesis.
  Karzbrun E et al. (2011) *PRL* 106:048104, doi:10.1103/PhysRevLett.106.048104 (APS licence; full
  text refused). Carrara P et al. (2018) *Data* 3:41, doi:10.3390/data3040041. Sato G et al. (2024)
  *Molecules* 29:2956, doi:10.3390/molecules29132956.

**Also checked, abstracts only (Europe PMC):** Shea MA, Ackers GK (1985) *J Mol Biol* 181:211–230,
doi:10.1016/0022-2836(85)90086-5; Jahnke T, Huisinga W (2007) *J Math Biol* 54:1–26,
doi:10.1007/s00285-006-0034-x.

**Named from memory, not read:** Bintu et al. 2005; Peccoud and Ycart 1995; Shahrezaei and Swain
2008; Munsky and Khammash 2006; Anderson 2007; Haseltine and Rawlings 2002; Salis and Kaznessis
2005; Cai 2007; Barrio et al. 2006; MacDonald 1978, as the producer cites it.
