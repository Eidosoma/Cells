> **Scope for Cells ([D140](DECISIONS.md), 11 November 2026).** The one level Cells
> skips is protein folding itself. Beneath it, Cells aims to simulate the gene
> regulation that sets protein amounts. Above it, Cells aims to simulate the
> assembly of proteins into complexes and molecular machines, from protein cages
> toward structures such as the proteasome and larger, and how those machines are
> used in cell physiology. (Lead note: folded structures and interfaces would come
> from structural data or prediction; the current cage model uses a prescribed
> contact graph.) This note surveys methods more broadly than that scope.

Yes. **We can simulate protein components moving, rotating, binding, separating, and assembling into larger structures from mathematical interaction rules.** Electrostatics is an important part of that, alongside shape, water, hydrogen bonding, molecular flexibility, and the entropy gained or lost during binding.

**As of November 2026, the strongest practical approach combines several levels of simulation:** detailed molecular calculations establish how particular interfaces behave; reduced models then simulate many proteins assembling over longer periods. Selected protein interactions can be recovered directly from atomic simulations, while larger assembly models increasingly predict pathways, intermediate structures, and assembly yields. A general system that reliably takes arbitrary protein sequences and predicts the complete construction and operation of a molecular machine remains an open research goal. That is my assessment of the capabilities demonstrated in the literature below. [PMC](https://pmc.ncbi.nlm.nih.gov/articles/PMC6410769/?utm_source=chatgpt.com)

The central mathematical object is an **interaction free-energy landscape**: how favourable different arrangements are, together with the barriers that determine how quickly proteins can move between them.

## 1. What actually makes protein components assemble?

A protein has a chemically patterned, flexible surface. Its interactions depend on **where another protein approaches, its orientation, its conformation, and the surrounding conditions**.

The main ingredients are:

| Ingredient | What it contributes to assembly |
|---|---|
| **Electrostatic interactions** | Charged groups attract or repel and can favour particular approach orientations. Salt and protonation change these interactions. |
| **Shape and steric exclusion** | Proteins cannot occupy the same space. Complementary surfaces allow close packing and restrict possible arrangements. |
| **Van der Waals interactions** | Numerous short-range contacts contribute to the stability and specificity of a well-packed interface. |
| **Hydrogen bonds** | Directional interactions favour particular geometries. Their benefit depends partly on which interactions with water they replace. |
| **Hydrophobic and hydration effects** | Bringing surfaces together changes the surrounding water. Burying nonpolar surfaces and releasing interfacial water can favour association. |
| **Entropy** | Binding restricts the proteins’ freedom to move, rotate, and change shape. Changes in solvent and counterion entropy can offset these costs. |
| **Conformational changes and allostery** | Binding at one location can change the protein’s shape or expose another interface, making assembly cooperative or sequential. |
| **Membranes, cofactors, and cellular context** | Lipids, metal ions, scaffolds, crowding, and assembly factors can determine where and how complexes form. |

These ingredients overlap physically. For example, standard atomistic force fields usually capture much of hydrogen bonding through electrostatic and van der Waals terms. Hydrophobic effects emerge from the protein–water system when water is represented explicitly. They should therefore be combined according to a consistent model, avoiding double counting. Work on geometric solvation models and more detailed electrostatic models illustrates how different mathematical descriptions isolate different contributions. [academic.oup.com](https://academic.oup.com/pnasnexus/article/4/3/pgaf065/8042116?utm_source=chatgpt.com)

### How local properties can specify a larger shape

Consider a simplified protein with two binding interfaces. Suppose those interfaces favour connections that turn neighbouring subunits by approximately 60 degrees in a plane.

A collection of these proteins can form chains and eventually six-membered rings. The simulator needs local shape, angular preferences, binding strengths, and flexibility. Ring formation can then emerge from those local interactions.

Several outcomes remain possible:

- Binding may be too weak for chains to survive.
- Binding may be sufficiently reversible for incorrect contacts to detach.
- Binding may be so strong that malformed intermediates persist.
- Flexible interfaces may permit several ring sizes.
- Concentration may change how often nuclei form and whether enough free subunits remain to finish them.

This is a useful conceptual distinction: **deriving a whole structure from local interaction rules is one achievement; deriving those local rules accurately from the amino-acid sequence is another.**

## 2. The mathematics underneath it

There are three linked questions:

1. **What forces act on the components?**
2. **Which assembled states are thermodynamically favourable?**
3. **How does the system reach those states, and on what timescale?**

### A. Atomistic simulation: calculate forces and integrate motion

In classical molecular dynamics, the basic equation is:

\[
m_i\frac{d^2\mathbf r_i}{dt^2}
=
-\nabla_i U.
\]

Here, \(U\) is the potential energy of the complete simulated system. A conventional force field includes terms for covalent bonds, bond angles, torsions, electrostatics, and van der Waals interactions.

If water and ions are explicit, their atoms also move and interact. Temperature control introduces an appropriate coupling to a thermal environment.

This is already a mathematical account of assembly, although the potential is an approximation whose parameters come from quantum calculations, experiments, and model development. Full quantum treatment is generally reserved for smaller regions where electronic rearrangement or chemical reactions matter.

The difficulty is the number of particles and, especially, the number of time steps. **At a 2-femtosecond step, one millisecond requires \(5\times10^{11}\) integration steps.** That is simple arithmetic, before considering the cost of evaluating all the forces. GPUs accelerate those calculations, but they do not remove the sequential time evolution.

### B. Electrostatics: screened, spatially patterned, and sensitive to conditions

A simple approximation for two charges in an electrolyte is the screened Coulomb, or Debye–Hückel, interaction:

\[
U_{\mathrm{el}}(r)
\approx
\frac{q_iq_j}{4\pi\epsilon_0\epsilon_r r}
e^{-r/\lambda_D}.
\]

The quantities are:

- \(q_i,q_j\): the charges;
- \(r\): their separation;
- \(\epsilon_r\): the dielectric response of the medium;
- \(\lambda_D\): the screening length set by the ionic environment.

For an illustrative aqueous solution with ionic strength around 150 mM, the usual continuum estimate gives a screening length of roughly **0.8 nm**. This describes a particular solution approximation; it should not be treated as a universal intracellular value. [frontiersin.org](https://www.frontiersin.org/journals/molecular-biosciences/articles/10.3389/fmolb.2023.1264161/full?utm_source=chatgpt.com)

For realistic proteins, the **distribution of charge across the surface** matters greatly. Two proteins with similar net charges can have very different orientation-dependent interactions. A 2025 *Nature Communications* paper developed an anisotropic electrostatic model specifically to represent this charge patchiness efficiently. [Nature Communications](https://www.nature.com/articles/s41467-025-58991-0?utm_source=chatgpt.com)

More detailed continuum calculations solve the **Poisson–Boltzmann equation** around molecular shapes, accounting approximately for solvent dielectric properties and mobile ions. APBS is an established implementation. At close interfaces, hydration, dielectric boundaries, and specific ion interactions make simple screening formulas less reliable. [pubmed.ncbi.nlm.nih.gov](https://pubmed.ncbi.nlm.nih.gov/28836357/?utm_source=chatgpt.com)

Charges can also change. Protonation depends on pH and the local environment, which itself changes when proteins bind. A substantial recent advance is GPU-accelerated **constant-pH molecular dynamics**, including a 2025 GROMACS implementation that couples protonation states to molecular conformation. [ACS Publications](https://pubs.acs.org/doi/10.1021/acs.jctc.4c01318?utm_source=chatgpt.com)

### C. Binding depends on free energy

For a simple reversible interaction,

\[
A+B \rightleftharpoons AB,
\]

the equilibrium dissociation constant is

\[
K_d=\frac{[A][B]}{[AB]},
\]

and the standard binding free energy per mole is

\[
\Delta G^\circ_{\mathrm{bind}}
=
RT\ln\left(\frac{K_d}{c^\circ}\right),
\]

where \(c^\circ\) is the standard concentration, conventionally 1 M.

This free energy includes the consequences of water rearrangement, lost translational and rotational freedom, conformational changes, and direct contacts.

A strongly attractive contact can therefore still be unfavourable overall if forming it carries a large desolvation or entropy cost.

For simple two-state mass-action kinetics,

\[
K_d=\frac{k_{\mathrm{off}}}{k_{\mathrm{on}}}.
\]

That ratio determines equilibrium affinity, but **it does not determine both rates individually**. Two interfaces can have the same affinity and very different association and dissociation times.

This is why an energy-minimized complex, an affinity estimate, and a prediction of assembly time answer different questions.

### D. Coarse-graining: mathematically remove detail

Suppose \(X\) describes the protein positions, orientations, and selected conformational states, while \(y\) describes water and other degrees of freedom we will not track.

Schematically, at fixed conditions, the effective free energy is

\[
W(X)
=
-k_BT\ln
\int e^{-U(X,y)/(k_BT)}\,dy
+
C.
\]

This equation expresses the central idea: **average over the microscopic configurations that are compatible with a larger-scale arrangement**.

A common approximation then moves proteins using overdamped Brownian dynamics:

\[
\Delta\mathbf r_i
=
-\frac{D_i}{k_BT}\nabla_i W\,\Delta t
+
\sqrt{2D_i\Delta t}\,\boldsymbol\xi_i.
\]

The first term is drift driven by the effective interaction. The second is thermal random motion. Here \(\boldsymbol\xi_i\) is a vector of independent standard normal variables. Rotation requires corresponding equations; more detailed models use anisotropic diffusion and hydrodynamic coupling. ReaDDy’s formulation provides a concrete implementation of this mathematical framework. [PLOS Computational Biology](https://journals.plos.org/ploscompbiol/article?id=10.1371%2Fjournal.pcbi.1006830\&utm_source=chatgpt.com)

The challenge is obtaining a sufficiently accurate \(W\), diffusion model, and set of state transitions. Removing microscopic detail can introduce many-body effects and memory. **A reduced model that reproduces equilibrium structures does not automatically reproduce physical kinetics.**

## 3. Where the state of the art sits

There is no single best resolution for every question.

| Approach | What is represented | Most useful question | Principal limitation |
|---|---|---|---|
| **Quantum chemistry / QM–MM** | Electrons in a selected region, often embedded in a larger classical system | How does a chemical reaction or proton-transfer event occur? | Expensive for whole assembly processes |
| **All-atom molecular dynamics** | Protein atoms, often explicit water and ions | What stabilizes an interface? How do conformations and encounters evolve? | Long assembly times and rare events |
| **Bead or residue-level models** | Groups of atoms or amino acids | How do proteins, lipids, and flexible domains organize collectively? | Interaction calibration and structural assumptions |
| **Rigid-body or patch-based Brownian models** | Protein shapes, orientations, and selected interaction sites | Which assembly pathways and competing structures occur? | Internal flexibility and detailed chemistry are reduced |
| **Reaction–diffusion models** | Diffusing subunits plus binding and chemical reaction rules | How do assembly and cellular chemistry interact over long times? | Rates and permitted interactions must be supplied |
| **Kinetic networks and Markov models** | Populations of intermediates and transitions between them | What are the yields, bottlenecks, waiting times, and pathway probabilities? | Dependence on the states and transitions included |

The modern frontier is often a **combination of these representations**, with detailed calculations informing the faster ones.

### All-atom simulations can recover real binding interfaces

A useful established demonstration is Pan and colleagues’ 2019 work on **five protein pairs**. Their simulations recovered experimentally observed complexes without supplying the structures of those complexes as targets. Enhanced sampling produced association and dissociation, while additional conventional simulations captured spontaneous association events; those conventional trajectories totalled more than **2 milliseconds of aggregate simulation**. [PMC](https://pmc.ncbi.nlm.nih.gov/articles/PMC6410769/?utm_source=chatgpt.com)

That establishes that physical molecular models can recover specific interfaces from separated proteins.

The scope matters: selected pairs are a more tractable problem than many different subunits assembling through a long sequence of intermediates. Also, enhanced sampling must be interpreted carefully. Some methods alter the dynamics to explore configurations; others preserve the underlying dynamics while reallocating sampling.

**Weighted-ensemble sampling** is particularly relevant when rates are important. A protein-binding study used it to obtain continuous, explicit-solvent association pathways and rate estimates without modifying the underlying dynamics. [pubs.rsc.org](https://pubs.rsc.org/en/content/articlehtml/2019/sc/c8sc04811h?utm_source=chatgpt.com)

### Martini and related models provide a useful middle scale

Martini replaces groups of atoms with interaction beads, making larger protein–lipid and protein–protein systems more accessible.

However, folded proteins generally need additional structural constraints, such as elastic networks or native-contact potentials, to maintain their folds. **GōMartini 3**, published in 2025, improved the treatment of conformational changes while retaining this structure-informed approach. [Nature Communications](https://www.nature.com/articles/s41467-025-58719-0?utm_source=chatgpt.com)

The distinction between a preserved fold and a calibrated interaction is consequential. A 2025 study found that unmodified Martini 3 overestimated self-interaction strength for lysozyme and subtilisin. Reparameterization improved agreement with measured second virial coefficients and diffusion coefficients. [pubmed.ncbi.nlm.nih.gov](https://pubmed.ncbi.nlm.nih.gov/40074017/?utm_source=chatgpt.com)

For assembly research, this means that apparent aggregation or rapid complex formation needs quantitative checking. A model can produce convincing structures while making interfaces too sticky.

### CGRig: a directly relevant 2026 development

**CGRig** represents each protein as a rigid body containing residue-level interaction sites. Its mathematics combines:

- translational and rotational overdamped Langevin dynamics;
- shape-dependent friction;
- screened electrostatics;
- excluded volume;
- native-contact interactions.

The authors demonstrated association of initially separated proteins into the intended complex and reported a benchmark exceeding **17 microseconds of simulated time per day for 1,024 molecules**. [PubMed](https://pubmed.ncbi.nlm.nih.gov/42272229/?utm_source=chatgpt.com)

This is close to the representation you are imagining: protein shapes with chemically meaningful interactions moving in three dimensions.

Its main qualification is that the native-contact component contains knowledge of the intended interface. It can investigate assembly under that interaction model; independent discovery of an unknown interface requires a more transferable potential.

### ioNERDSS: converting protein structures into assembly simulations

The **ioNERDSS preprint, updated in April 2026**, is one of the most immediately relevant tools.

It takes atomic structures and converts them into:

- rigid protein subunits;
- discrete binding interfaces;
- orientation constraints;
- reaction rules for the NERDSS simulator.

The authors report models involving thousands of subunits, minute-scale assembly simulations, and benchmarking against more than **40,000 PDB structures**. Affinities can be initialized using learned predictors, while binding rates and abundances begin with defaults that users must adjust. [pubmed.ncbi.nlm.nih.gov](https://pubmed.ncbi.nlm.nih.gov/41659451/?utm_source=chatgpt.com)

This automates a substantial amount of model construction.

The resulting trajectories are conditional on geometry extracted from the supplied complex. Reassembling that geometry demonstrates consistency of the constructed model; quantitative predictions about biology require validated rates, competing interactions, and experimental comparisons.

CGRig and NERDSS also illustrate why speed comparisons require care: one explicitly evaluates residue-level interactions, while the other replaces more of the encounter process with reaction rules.

### Markov models extend the accessible timescale

The **multiMSM** framework, published in *Physical Review X* in December 2024, learns transitions between assembly intermediates from shorter simulations and uses them to predict longer-time behaviour.

A particularly useful feature is its treatment of **monomer depletion**. As assemblies grow, free-subunit concentrations fall, changing subsequent reaction rates.

On its model systems, multiMSM predicted intermediate populations, yields, nucleation times, and pathway fluxes over timescales far beyond direct simulation. Its predictions remain dependent on the quality and coverage of the underlying model and sampled transitions. [Phys. Rev. X](https://journals.aps.org/prx/abstract/10.1103/PhysRevX.14.041063?utm_source=chatgpt.com)

This is an important direction: use detailed simulation to discover relevant transitions, then propagate a reduced description.

## 4. Recent results that most directly answer your question

### Electrostatic barriers can determine the order of assembly

An **October 2026 paper in *Protein Science*** studied assembly of a protein virus-like particle using an electrostatic model based on the linearized Poisson–Boltzmann equation.

The model helped explain why changing salt conditions altered the assembly pathway and product quality: screening changed the relative barriers for different interfaces, affecting which contacts formed first. [Wiley Online Library](https://onlinelibrary.wiley.com/doi/10.1002/pro.70824?af=R\&utm_source=chatgpt.com)

The general lesson is that **electrostatics can regulate the sequence of assembly events**, beyond simply making the final object more or less stable.

For simulation, this makes environmental history relevant. Two systems ending at the same salt concentration can have followed different pathways and become trapped in different states.

### Geometry and solvent can recover small assemblies

A 2025 *PNAS Nexus* paper, **“Solvation, geometry, and assembly of the tobacco mosaic virus,”** used a geometric approximation to nonpolar solvation free energy.

The model expresses the solvent contribution through geometric measures such as excluded volume, accessible surface area, and curvature. It found arrangements close to experimentally observed assemblies for **up to three protein subunits**, using protein geometry and the solvent model. [academic.oup.com](https://academic.oup.com/pnasnexus/article/4/3/pgaf065/8042116?utm_source=chatgpt.com)

This is a particularly interesting answer to “from math”: substantial information about favourable association can arise from the geometry of surfaces and the surrounding fluid.

The demonstrated scope was small assemblies. Extending that result to large, flexible, chemically diverse machinery is a further problem.

### Topological mathematics can improve the search for assembled configurations

A September 2026 *PLOS Computational Biology* paper added a potential based on **persistent homology**, which measures geometric features such as connected components, loops, and enclosed spaces across scales.

Combined with a geometric solvation model, it increased successful assembly in its tests by **up to sixteen-fold** across four protein systems. [PLOS Computational Biology](https://journals.plos.org/ploscompbiol/article?id=10.1371%2Fjournal.pcbi.1014709\&utm_source=chatgpt.com)

This is an interesting computational technique, with a precise limitation: the topological term is an added search bias, and the simulations use Monte Carlo exploration. The authors explicitly distinguish that exploration from physical dynamics.

It therefore helps identify favourable assembled configurations. Predicting natural pathways and assembly times requires separate treatment.

### Experiments increasingly resolve the stochastic pathway itself

A September 2026 *Nature* study followed individual engineered virus-like particles assembling using mass photometry and single-molecule trapping.

It found that **weak, reversible contacts** allow components to explore arrangements until more highly connected intermediates form. Those intermediates are much harder to dismantle, producing distinct nucleation and growth stages. [Nature](https://www.nature.com/articles/s41586-026-10948-z?utm_source=chatgpt.com)

This provides unusually direct experimental targets for simulation: intermediate populations, waiting times, reversible encounters, and successful completion.

It also explains why maximizing attraction is a poor general design objective. Productive assembly depends on a balance between sufficiently stable correct contacts and the ability to escape unproductive ones.

## 5. What AI is changing

There are three separate advances here.

### Structure prediction supplies starting hypotheses

AlphaFold 3 can predict complex structures involving proteins and other molecular components. Its original paper explicitly states that its predictions do not provide the dynamical behaviour or calibrated solution ensemble of the system. [Nature](https://www.nature.com/articles/s41586-024-07487-w?utm_source=chatgpt.com)

Such models can supply candidate folds and interfaces for subsequent simulation. The questions of pathway, timing, concentration dependence, and competing products still need additional modelling.

### Learned force fields improve the interaction model

A learned force field replaces some or all of the energy function with \(U_\theta\), while forces still follow from

\[
\mathbf F_i=-\nabla_iU_\theta.
\]

One relevant 2025 example is **SO3LR**, which combines a neural model of local interactions with explicit terms for long-range electrostatics, dispersion, and short-range repulsion. Its implementation supports GPU execution through JAX. This is a practical example of combining learned molecular physics with explicit physical terms. [GitHub](https://github.com/general-molecular-simulations/so3lr?utm_source=chatgpt.com)

Another is the 2025 *Nature Chemistry* study **“Navigating protein landscapes with a machine-learned transferable coarse-grained model.”** It trained a reduced potential on atomistic simulations and demonstrated predictions for previously unseen sequences, including metastable conformations, disordered ensembles, and mutation-dependent folding free energies. [PubMed](https://pubmed.ncbi.nlm.nih.gov/40681718/?utm_source=chatgpt.com)

My assessment is that learned coarse-grained potentials are especially relevant to scalable assembly simulation: they offer a way to retain more of the effective many-body physics than a small hand-written table of pairwise attractions.

Their transferability still needs to be established for the assembly class and environment being studied.

### Learned dynamics can skip microscopic time steps

A very recent development is **BioEmu2**, released as a preview in October 2026. It supports multicomponent molecular systems and time-lagged propagation, including a demonstration of peptide binding. [GitHub](https://github.com/microsoft/bioemu2/releases?utm_source=chatgpt.com)

Conceptually, such a model learns a conditional distribution:

\[
p_\theta(X_{t+\tau}\mid X_t,\text{molecular system}),
\]

allowing it to sample a later configuration directly.

The documentation recommends propagation intervals of **1–1,000 ns**, the range predominantly represented during training. Successive propagation steps can be chained into a trajectory. [GitHub](https://github.com/microsoft/bioemu2/blob/main/docs/propagation.md?utm_source=chatgpt.com)

The calibration boundary is significant: the model card explicitly warns that sample frequencies are **not calibrated Boltzmann probabilities or quantitative free energies**. Quantitative affinity prediction is outside its stated scope. I would treat it as a promising source of dynamical hypotheses and candidate transitions, with assembly kinetics requiring independent validation. [GitHub](https://github.com/microsoft/bioemu2/blob/main/MODEL_CARD.md?utm_source=chatgpt.com)

### Designed assemblies show how powerful local interface rules have become

A separate 2026 *Nature* milestone combined geometric parameterization with generative protein design to produce experimentally observed cages containing **180–2,160 subunits**, with diameters of **68–220 nm**. [Nature](https://www.nature.com/articles/s41586-026-10554-z?utm_source=chatgpt.com)

This is strong evidence that designed local geometry and interfaces can specify large structures. The experimental design achievement should be distinguished from a fully atomistic prediction of every step by which those thousands of subunits assemble.

## 6. A functioning nanomachine adds another layer

A protein cage is a relatively clean assembly problem. A molecular motor or biosynthetic machine introduces additional requirements:

- different chemical and nucleotide-bound states;
- assembly factors and chaperones;
- conformational cycles;
- coupling to membranes or other polymers;
- energy consumption or an electrochemical gradient.

For example, a June 2026 study of human ATP synthase investigated how its **28 subunits of 17 kinds** assemble through modules and assembly-factor-dependent steps. The work also identifies remaining questions about how those components are put together. [Springer Nature Link](https://link.springer.com/article/10.1038/s44318-026-00842-9?utm_source=chatgpt.com)

An operating machine needs a model of **motion plus chemical-state transitions**. Sustained work requires an energy source and consistent accounting of that energy.

At equilibrium, reversible transition rates must be consistent with equilibrium probabilities. In a driven system, ATP, GTP, or an ion gradient can maintain circulating probability currents through a cycle of states. A single equilibrium potential generally cannot describe that entire process.

Particle reaction–diffusion frameworks such as ReaDDy are useful here because they combine interaction forces with reactions that change particle identities, bonding, and behaviour. The relevant chemistry remains part of the model that must be specified and validated. [PLOS Computational Biology](https://journals.plos.org/ploscompbiol/article?id=10.1371%2Fjournal.pcbi.1006830\&utm_source=chatgpt.com)

## 7. What I would build for a molecular assembly layer in Cells

**I would use proteins or protein domains as the main simulated objects, with detailed molecular calculations informing their interactions.** The representation should retain enough geometry and internal state to allow meaningful competing outcomes.

For each component, I would consider:

| Property | Purpose |
|---|---|
| Shape and excluded volume | Prevent impossible overlap and preserve geometric constraints |
| Position and orientation | Represent directional encounters and interfaces |
| Charge patches and protonation response | Connect interactions to local ionic conditions and pH |
| Reversible binding sites | Allow assembly, disassembly, and error correction |
| A small number of conformational states | Capture binding-induced changes and cooperative assembly |
| Diffusion and rotational mobility | Give encounters a calibrated timescale |
| Chemical state | Represent nucleotide binding, hydrolysis, modifications, or cofactors where relevant |

This is a proposed architecture, rather than a claim about what Cells currently implements.

### Calibrate the molecular rules

Use atomistic calculations and measurements to estimate:

- binding free energies and their uncertainty;
- association and dissociation rates;
- angular flexibility at interfaces;
- conformational transitions;
- changes with pH, salt, or membrane composition.

A model that matches only the assembled structure is underconstrained. Several different interaction models may produce the same endpoint while predicting different pathways.

### Choose the assembly engine according to the question

My initial shortlist would be:

- **[ioNERDSS](https://github.com/JohnsonBiophysicsLab/ionerdss)** for quickly constructing assembly models from known structures.
- **CGRig-style models** when protein shape and residue-level interface interactions are central.
- **Martini/GōMartini** when membrane interactions and selected flexibility need greater resolution.
- **ReaDDy-style reaction–diffusion models** when assembly must interact with a chemical network.
- **Markov models such as multiMSM** for longer-time predictions, pathway analysis, and broad parameter sweeps.

For GPU work, I would benchmark the actual chosen implementation. For example, NERDSS’s published 2025 parallelization uses **MPI and CPUs**; its scaling results are not evidence of a GPU implementation. [pubmed.ncbi.nlm.nih.gov](https://pubmed.ncbi.nlm.nih.gov/40405327/?utm_source=chatgpt.com)

### Couple assembly to the local cellular environment

A useful Cells model could let local pH, ion concentrations, membrane composition, and chemical resources influence protein states and assembly rates. The assembled complexes could then alter those same variables through transport, catalysis, or mechanical action.

That creates a physically interpretable feedback loop between molecular organization and cell physiology.

Even the ambitious 2026 spatial model of a genetically minimal cell uses kinetic networks and explicit assembly assumptions. It illustrates the practicality of combining levels of description while keeping track of which mechanisms are supplied as rules. [doi.org](https://doi.org/10.1016/j.cell.2026.02.009?utm_source=chatgpt.com)

### Set a predictive first milestone

I would begin with one well-characterized oligomer or cage and ask the model to predict:

1. The distribution of complete, incomplete, and incorrect assemblies.
2. Assembly and disassembly times.
3. How those distributions change with concentration.
4. The response to a previously untested salt or pH condition.
5. Whether the prediction remains accurate without retuning the interactions for that condition.

**That would be a substantial and credible result: a molecular assembly model whose local physical rules predict a new collective outcome.** It is a realistic stepping stone toward connecting the construction of protein machinery to the behaviour of a simulated cell.
