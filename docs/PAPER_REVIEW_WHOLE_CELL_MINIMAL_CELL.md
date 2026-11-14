**A whole-cell 4D simulation of the minimal cell JCVI-syn3A, and what Cells can learn from it — reviewed 14 November 2026**

Zane R. Thornburg, Andrew Maytin, Jiwoong Kwon, Troy A. Brier, Benjamin R. Gilbert,
Enguang Fu, Yang-Le Gao, Jordan Quenneville, Tianyu Wu, Henry Li, Talia Long, Weria
Pezeshkian, Lijie Sun, Daniela Matias de C. Bittencourt, John I. Glass, Angad P. Mehta,
Taekjip Ha and Zaida Luthey-Schulten, *Bringing the genetically minimal cell to life on a
computer in 4D*, *Cell* **189**(9): 2582–2597.e27, April 2026; online 9 March 2026
(received 10 June 2025, revised 9 December 2025, accepted 9 February 2026). **CC BY 4.0.**
[Article](https://doi.org/10.1016/j.cell.2026.02.009) (PMID 41806832; not in PMC).
Erratum: *Cell* 189(9): 2780–2781, [doi:10.1016/j.cell.2026.04.003](https://doi.org/10.1016/j.cell.2026.04.003),
15 April 2026. Preprint: [bioRxiv 10.1101/2025.06.10.658899](https://doi.org/10.1101/2025.06.10.658899)
v1, 15 June 2025, 17 authors, all rights reserved with no reuse permitted. Affiliations
(v1): Illinois Urbana-Champaign, the J. Craig Venter Institute, Johns Hopkins, Boston
Children's Hospital and Harvard Medical School, HHMI and the Niels Bohr Institute; lead
contact Z. Luthey-Schulten. The news story that prompted the review is
[*Team simulates a living cell that grows and divides*](https://las.illinois.edu/news/2026-03-20/team-simulates-living-cell-grows-and-divides)
(Illinois News Bureau, 20 March 2026).

**Which text this review rests on.** The *Cell* version could not be read.
- cell.com and ScienceDirect returned HTTP 403.
- The open copy in the University of Copenhagen repository sits behind a Cloudflare challenge.
- It is not in PMC, and the NSF public-access record is embargoed until 1 April 2027.

**Every page, section, figure and number below is therefore from bioRxiv v1**, read in full,
unless marked otherwise. The published version differs in ways we can see but not inspect:
- an 18th author (Bittencourt);
- a reworded abstract;
- a revision in December 2025;
- an erratum in April 2026.

Figures that appear only in the news story (about six days per cycle, simulated cycles within
two minutes of the real one) are secondary. The preprint's licence forbids reuse, so this
review paraphrases and reproduces no figure, table or passage. **S** marks our arithmetic or
interpretation, and **F** a value read off a figure.

**Verdict first.** This is the most complete published simulation of one living cell's whole
cycle in space and time: every gene expressed, the whole metabolic network, a replicating and
segregating chromosome, growth and division, in 50 stochastic replicates. Its organism is a
bacterium, and the v1 text describes:
- no membrane potential and no ions as charged species;
- no water or osmotic balance;
- no mechanics beyond a prescribed shape;
- no transcriptional regulation.

These rest on a search of the full text. The metabolic network itself sits in Tables S1–S2 and
the 2022 model, which we did not read, and Fig. S4 does list ATP costs for transport and for an
ATP synthase.

It therefore touches no qualified Cells model and sets no numerical target for any gate in the
[current plan](CURRENT_PLAN.md). Nothing in it should enter `src/cells`. Its value to Cells is
as an engineering and validation case study:
- how four solvers on different clocks were made to share one inventory;
- where the wall-clock time actually went on two GPUs: mostly outside the GPU RDME kernel;
- what partition at division looks like when it emerges from particle positions;
- how thin the held-out evidence becomes once tuned and input quantities are set apart from
  predictions.

The paper is also frank about what was hard. Every candidate below is deferred under
[D151](DECISIONS.md#d151-every-reviewed-candidate-is-deferred-not-closed), and none is proposed
for now. No code, run or acceptance follows from this review.

## 1. What it is

| Item | What the paper reports (v1) |
| --- | --- |
| Organism | JCVI-syn3A, a genetically minimal bacterium reduced from *Mycoplasma mycoides* subsp. *capri*: one 543 kbp circular chromosome, 493 genes, doubling time 105 min (p. 2) |
| What is simulated | One cell from birth to division: expression of all 493 genes, the full metabolic network, ribosome biogenesis, chromosome replication and dynamics, growth and division (p. 3) |
| Space | Cubic lattice of 10 nm sites in a 64 × 64 × 128 box (0.64 × 0.64 × 1.28 µm, **S**). The cell radius grows from 200 nm to 250 nm (pp. 5, 35). The chromosome is 54,338 beads of 10 bp (p. 35); the GPU benchmark quotes a system of about 100,000 beads (p. 42) |
| Time | 2 h (7,200 s) of biology per replicate (Fig. 1). Clocks run from 0.1 ns (Brownian dynamics) to 4 s (chromosome exchange) (§2.2) |
| Replicates | 50 cells, each with its own sampled starting mRNA counts and stochastic history (pp. 3, 34–35) |
| Hardware | Two GPUs per cell, for example NVIDIA A100s on Delta (pp. 3, 42; the news story places Delta at NCSA) |
| Cost | 4–6 days per cycle, about 250 GPU-hours per replicate, and roughly 15,000 A100 GPU-hours for the 50 (Fig. 1; p. 10). A cycle took over two weeks before the chromosome moved to its own GPU (p. 10) |
| Software | Lattice Microbes 2.5 (RDME and CME) with its Python layers pyLM and jLM; odeCELL with LSODA for metabolism; LAMMPS (19 November 2024) with Kokkos, driven by btree_chromo; sc_chain_generation for the starting chromosome; cobrapy to read the SBML network. FreeDTS was tested and set aside. Docker and Apptainer recipes are given on CUDA 11.6 (pp. 36–37, 42, 59) |
| Output | One saved frame per biological second. Saving every step would take over 80 TB per trajectory, by the authors' estimate (p. 11) |
| Deposits | v1 promises code on GitHub and Zenodo and gives the SRA accession (p. 12). Checked on 14 November 2026: the [GitHub repository](https://github.com/Luthey-Schulten-Lab/Minimal_Cell_4DWCM); the [Zenodo record 10.5281/zenodo.15579159](https://doi.org/10.5281/zenodo.15579159) (2 June 2025), a frozen snapshot of code and inputs with 50 count-and-flux traces and 4 lattice trajectories; and sequencing reads in BioProject PRJNA1257452 (nine runs). Licences are in §6 |

**Where the time goes** (Fig. 1, bar chart, **F**). The chart gives wall-clock seconds per
biological second:

| Component | Wall-clock seconds per biological second |
| --- | --- |
| The RDME solver itself | 18.4 |
| Updating ribosome positions | 11.2 |
| Communication and file writing | 8.67 |
| The CME | 5.49 |
| Chromosome communication and morphology | 5.22 |
| The ODE | 1.26 |

- The six sum to about 50 s per biological second, about 100 h per 7,200 s cycle (**S**). That is
  consistent with the stated 4–6 days.
- **The GPU RDME kernel is about 37% of the wall time.** The rest is work done outside that
  kernel while the solver is paused (**S**). The preprint does not say on which device the CME
  runs.
- The chromosome's Brownian dynamics on the second GPU are not in the chart. They run in
  parallel and take about as long per biological second as everything else together (p. 38).

## 2. How it works

### 2.1 Four methods, chosen by copy number and locality

| Method | Processes the paper assigns to it | Where it runs |
| --- | --- | --- |
| **RDME**, spatial and stochastic (Lattice Microbes' multiparticle diffusion solver, its single-GPU 32-bit version; Eq. 1, p. 37) | RNAP diffusion and binding at gene start sites; ribosome–mRNA binding and translation; mRNA–degradosome binding and degradation; membrane-protein insertion; replication initiation (p. 37). Every protein and RNA is an individual particle (p. 4) | GPU 1 |
| **CME**, well-stirred and stochastic (Gillespie direct method in Lattice Microbes) | Transcription elongation and tRNA charging (pp. 36, 50) | During the pause; the preprint names only the RDME and the chromosome as GPU work |
| **ODE**, deterministic (odeCELL; LSODA with BDF orders 1 to 5) | Glycolysis, nucleotide and lipid synthesis, transporters. The network is that of the group's 2022 well-stirred model ([Thornburg et al., *Cell* 185, 2022](https://doi.org/10.1016/j.cell.2021.12.025)), unchanged in structure (pp. 36, 43) | During the pause |
| **Brownian dynamics** (LAMMPS with Kokkos, via btree_chromo) | The chromosome polymer, replication forks, SMC loop extrusion, topoisomerase strand passage (pp. 38–43) | GPU 2, as a background process |

- **The rule behind the split.** Low-copy macromolecules that must meet in space go on the
  lattice. Low-copy species that react with abundant, fast-diffusing small molecules (tRNA with
  ATP and amino acids) are well-stirred and stochastic. Metabolites are deterministic
  concentrations (pp. 36, 50).
- **Assembly.** RNAP, degradosomes and both ribosomal subunits are assembled in the
  simulation (p. 6). RNAP and degradosome subunits start scattered and assemble within the first
  second (p. 34). Ribosome assembly follows linear pathways reduced from *E. coli* assembly
  maps (p. 49).
- **Not flux balance.** "FBA" in the paper's Results and Methods is the glycolytic enzyme
  fructose-bisphosphate aldolase. Flux balance analysis appears only in the introduction, as
  background. Metabolism is kinetic ODE throughout (pp. 2, 43).

### 2.2 The clocks and how they exchange

| Clock | Interval | What happens (pp. 37–38 unless noted) |
| --- | --- | --- |
| RDME step | 50 µs | Diffusion and spatial reactions on the lattice |
| Pause ("hook") | 250 steps = 12.5 ms | The lattice is copied to the host and ribosome excluded volume re-projected (Fig. 1 flowchart). The ribosomes set this interval: a centre of mass with D = 0.001 µm²/s crosses one site in about 17 ms, and 12.5 ms was taken as a conservative common clock (p. 52) |
| Well-stirred chemistry | 1 s | Read the cell state from the lattice; run 1 s of CME; write the results back; convert counts to concentrations at the current volume; charge the second's gene-expression costs to the metabolite pools; integrate 1 s of ODE; convert back to counts |
| Output | 1 s | Counts and fluxes to CSV, a lattice frame to the trajectory, restart files |
| Chromosome and shape | 4 s | Read the finished Brownian interval; advance replication (at most 400 bp per fork); move gene and origin particles; rebuild the DNA sites; update area and volume, and the lattice shape if a 10 nm threshold is crossed; launch the next 4 s of Brownian dynamics in the background (pp. 42–43, 53) |
| SMC hinge | 0.4 s of biology | Ten hinge steps per 4 s, with anchors re-placed every 4 s. Each step runs 10,000 Brownian steps of 0.1 ns, i.e. 1 µs of polymer time (p. 40) |
| Topoisomerase | Every 2 s | Hard excluded volume is swapped for a soft potential over five minimisation and dynamics stages (p. 39) |

- **A sequential, lagged split.** Each method advances its own interval with the others' state
  frozen at the last exchange (**S**, our reading of the algorithm on pp. 37–38).
- **One store of counts.** All particle counts live in one Python dictionary, which is the single
  source of truth. Counts become concentrations only inside the ODE (p. 38).
- **The chromosome is exchanged in 4 s blocks.** A polymer interval launched at one exchange
  uses the cell state of that moment and is read back at the next. Replication set by the dNTP
  pools at time t therefore reaches the lattice at t + 4 s (**S**, from p. 43 and the Fig. 1
  flowchart). Shape updates during division run serially, because the lattice membrane and the
  polymer's boundary must agree (pp. 38, 55).
- **Costs are paid by fictitious reactions.** Gene-expression costs are summed over each second.
  Each cost is a "cost particle" converted to a "paid" state one amino acid at a time by fast
  reactions. Direct subtraction would almost always leave costs unpaid, since a second's
  translation exceeds the roughly 200 charged tRNAs per isoform (p. 50).
- **Bookkeeping particles.** Every transcription, translation and degradation event creates a
  bookkeeping particle, so events between saved frames reach both the cost accounting and the
  analysis (p. 58).
- **No refinement of any exchange interval is reported**, and no conservation check across
  exchanges (**S**: we found neither in the preprint).
- **The polymer clock is not physical time.** Each 0.4 s of biology runs 1 µs of Brownian
  dynamics between energy minimisations. That is about 20 ms of polymer time per 2 h cycle
  (**S**). The authors say this is why their segregation force has no real-time meaning (p. 41).

### 2.3 Gene expression and its link to metabolism

- **Binding rates from another organism.** Binding steps are bimolecular RDME reactions.
  Their rate constants are converted from event frequencies measured in *E. coli*, as frequency
  × Avogadro's number × volume / (n_A n_B) (Eq. 14, p. 46). The base values (pp. 46–48):

  | Binding pair | Rate constant (M⁻¹ s⁻¹) |
  | --- | --- |
  | RNAP with rRNA and tRNA genes | 8.8 × 10³ |
  | RNAP with mRNA genes | 2.1 × 10³ × the gene's promoter strength |
  | Ribosome with mRNA | 5.9 × 10⁴ |
  | Degradosome with mRNA | 1.4 × 10⁴ |

  The final set multiplies ribosome binding by 1.3 and degradosome binding by 0.3 (p. 8). The
  Methods values reproduce the unscaled *E. coli* arithmetic, so the factors apply on top (**S**).
- **Promoter strength from proteomics.** Each gene's promoter strength is its initial protein
  count divided by 180, the average (Eq. 20, p. 47). It scales both RNAP binding and elongation
  speed (20 nt/s, capped at 85 nt/s).
- **Elongation reads the live pools.** It uses a generic rate law for template-directed
  polymerisation (Hofmeyr et al. 2013) whose monomer terms are the current pools:
  - NTPs (K_D 0.1 mM) for transcription;
  - charged tRNAs (K_D 1 µM) for translation;
  - dNTPs for replication, at up to 100 bp/s over the 400 bp ahead of each fork (Eqs. 6 and 15;
    pp. 43, 46).
- **The only path from metabolism into expression.** That substrate limitation is it. The
  preprint describes no transcriptional regulation, since promoter strengths are constants, and
  says metabolic inhibition is not modelled (p. 44).
- **Degradation.** It runs at 88 nt/s once a degradosome binds. Degradosomes are confined to
  the layer of sites just inside the membrane (pp. 48, 51).
- **Several RNAP on rRNA genes.** They are tracked in 400 nt increments, up to 4 on 16S and 7 on
  23S genes. Without this, ribosomes could never double (p. 48).
- **No polysomes.** Each ribosome is an independent lattice particle, so one mRNA is read by one
  ribosome at a time (pp. 7, 52).

### 2.4 Chromosome

- **Polymer.** A bead-spring chain at 10 bp per 3.4 nm bead, with FENE bonds, a bending
  persistence length of 45 nm and hard excluded volume (p. 39). There is no twist: the authors
  expect supercoiling to matter little at 10 nm resolution, and the Kokkos path lacks the
  torsion potential (p. 42).
- **Dynamics.** Overdamped Langevin at 310 K with a 0.1 ns step, and friction from
  Stokes–Einstein with a viscosity of 1.2 Pa·s (p. 39).
- **SMC loop extrusion,** one-sided (pp. 40, 43):
  - anchors are placed uniformly at random every 4 s;
  - the hinge steps every 0.4 s, by a Poisson number of beads with mean 20 (about 200 bp),
    capped at 30;
  - the number of loops is half the current SMC protein count, read from the shared counts.
- **Replication** follows the train-track model at 10 bp resolution, with each fork advancing at
  the dNTP-limited rate (p. 43).
- **Segregation needs a fictitious force.** SMC and topoisomerases disentangle the daughters but
  do not separate them (pp. 40–41).
  - A 12 pN repulsion acts on replicated DNA and is switched off once both chromosomes have
    crossed the mid-plane.
  - The authors call it a constraint, not a calibrated value.
  - A BLAST search finds no ParA or ParB genes and no complete parS sites in Syn3A. The authors
    could not identify a MatP or Min system, and cryo-ET shows no attachment organelle (p. 41).
- **Coupling to the lattice.** Bead positions mark DNA sites, where diffusion is halved. Gene
  start sites and the origin are lattice particles, moved to their bead's site with their state
  kept (pp. 42, 51). The polymer's boundary is smaller than the lattice membrane, so DNA never
  overlaps it (p. 4).
- **GPU.** Custom Kokkos versions of two LAMMPS fixes gave about 10× over CPU-only for about
  100,000 beads on A100s (p. 42). Running the polymer as a background process on a second GPU
  removed a wait of 2–5 minutes per 4 s of biology (p. 43).

### 2.5 Growth and division

- **Area from composition.** The membrane area is the sum of fixed per-molecule areas:
  28 nm² per membrane protein, and 0.4–0.6 nm² per lipid by class. A constant 51.3% of lipids
  is taken to be in the outer leaflet (pp. 52–53). Membrane growth therefore follows lipid
  synthesis in the ODE and protein insertion on the lattice.
- **Volume from geometry.** The cell grows as a sphere, its radius set by the area, until its
  volume has doubled (radius 200 to 250 nm). The volume is then held constant while the area
  keeps growing (p. 53).
  - The dividing shape is two overlapping spheres. Their radius and separation are solved
    numerically from the current area and volume every 4 s (pp. 53–54).
  - The solution does not preserve volume exactly after doubling (p. 54; Fig. S3D).
- **On the lattice** (pp. 53–56):
  - the shape is rebuilt only at 10 nm steps of radius during growth (200, 210, ..., 250 nm);
  - displaced particles move to the nearest site of their own type;
  - the polymer's boundary moves by at most one bead radius per minimisation;
  - a rescue routine pulls DNA out of the closing division plane.
- **No division machinery.** FtsZ is present as particles, but it has no polymerisation
  kinetics and does not localise to the midplane. A Helfrich membrane model (FreeDTS) gave
  teardrop shapes with long necks and was set aside (pp. 6, 56–58).
- **Partition is emergent.** The particles on each side when the membranes separate go to that
  daughter (p. 9).

### 2.6 Parameterisation from omics and other organisms

| Quantity | Source (v1) |
| --- | --- |
| Protein counts | Proteomics, as in the 2022 model. Ribosomal proteins are reduced by the 500 in ribosomes, with 25 free copies added where proteomics fell short (p. 34) |
| Ribosomes | 500, placed uniformly, from cryo-electron tomograms (p. 34) |
| mRNA | No quantitative transcriptomics. Counts are Poisson samples around twice the previous model's averages, chosen after test runs gave about 400 mRNAs rather than 200 (pp. 34–35) |
| tRNA | 200 per isoform, scaled from *E. coli* (pp. 34–35) |
| Metabolites | Scaled from *E. coli* metabolomics, unchanged since the 2022 model (p. 34) |
| Medium | A defined medium, held constant, since one cell does not deplete it (p. 33) |
| Rate constants | A kinetic table (Table S2, not read) drawn from BRENDA and measurements in related organisms. Binding rates come from *E. coli* event frequencies, and glucose uptake from *M. pneumoniae* uptake and proteomics (pp. 43–48) |
| Chromosome | Gene positions from GenBank CP016816.2. The starting configuration is grown inside a 190 nm sphere. The 3C-seq contact map is used to argue against persistent supercoiling (pp. 35, 42) |

**Retuning for 4D** (pp. 8, 44–45).
- **DnaA.** Its single-strand binding rates were moved from the average of a single-molecule
  study to that study's origin-like construct: on 100 → 140 mM⁻¹ s⁻¹, off 0.55 → 0.42 s⁻¹. With
  the averages, replication never began within 60 minutes.
- **Survival.** The aldolase rate and glucose uptake were raised, after which every cell
  survived the cycle. The authors chose the parameter set in which more cells stay healthy,
  noting that no death rate has been measured for Syn3A (p. 44).
- **Nucleoside uptake.** Five uptake rates were lowered to stop the (d)NTP build-up seen in the
  earlier model, in place of the missing inhibition (p. 44).

## 3. Validation: what was compared, and what the data show

The paper generated two new data sets (pp. 31–33):
- whole-genome sequencing, for the origin-to-terminus (ori:ter) ratio;
- fluorescence imaging of fixed cells, for morphology.

Everything else is compared with earlier models, with other bacteria, or with the inputs.

| Authors' claim | Measurement behind it | Input, tuned or held out | Our reading |
| --- | --- | --- | --- |
| Doubling time of 105 min matches experiment (pp. 5, 10) | 105 min (Breuer et al. 2019) | **Not held out.** It lies downstream of the rates retuned for 4D (§2.6), which targeted initiation, protein doubling, survival and NTP build-up, not the doubling time itself. No doubling time is reported for the untuned set. The previous model gave 97 min, and the authors attribute the slowdown to protein underproduction (p. 5) | A consistency check, not a held-out prediction. The news story's "within two minutes" is not in v1 |
| ori:ter of 1.28 agrees with the measured 1.21 (pp. 6, 10) | New sequencing, three replicates: 1.20, 1.21 and 1.21 in exponential phase; 0.97–0.99 stationary. Ten evolution endpoints from earlier data give 1.02–1.19 (p. 33) | **Closest to held out.** But initiation was retuned so that it happens at all (§2.6) | See below: the agreement depends on how the simulated population is sampled |
| Imaging supports symmetric division (pp. 3, 5) | 1,319 fixed Syn3B cells with labelled FtsZ: 79.5% spherical, 11.6% prolate, 4.7% dividing, 4.2% budding (Fig. 4D, **F**). About 15% carry cell-in-cell structures in late exponential phase (p. 5) | **Imposed.** Symmetric two-sphere division is a constraint built from the imaging, not an output (p. 5) | The one quantitative morphology comparison disagrees; see below. The authors attribute the gap to missing FtsZ kinetics |
| mRNA half-lives are recovered (abstract) | None for Syn3A in v1. Compared with the earlier model (1.97 and 1.48 min) and with the spread across other bacteria (pp. 8, 10) | Output, shaped by retuning the ribosome-to-degradosome binding ratio to bring proteins closer to doubling (p. 8) | Model mean 3.63 min, median 2.98 (Fig. 5, **F**). Not a validation against Syn3A data in v1 |
| Ribosome counts are recovered (abstract) | The starting 500 come from cryo-ET (p. 34) | Input at birth | 500 → 881 at 105 min (Fig. 5A, **F**), short of doubling. No independent count at division is compared in v1 |
| Protein distributions are recovered (abstract); proteins double (p. 7) | Proteomics: the same data that set the initial counts and the promoter strengths (pp. 34, 47) | **Circular** | Median 1.9, mean 2.45, with a tail to about 6× among proteins that start at 10 copies or fewer (p. 7; Fig. 5, **F**). Long proteins (genes over 3 kb) reach only 1.25–1.5× (p. 7) |
| Partition is unbiased and near-binomial (p. 9) | None; a prediction | Output | See below |
| About 55% of ribosomes, 70% of RNAP and 10% of degradosomes are active (p. 7) | None for Syn3A, as the authors say (p. 7) | Prediction | Plausibility only: ribosome activity reaches 85% in *E. coli* (p. 7) |
| Gene distance from the membrane sets mRNA lifetime (a 2022 hypothesis) | None | Tested inside the model | No significant correlation (p. 11; Fig. S3G) |

**The ori:ter ratio, sampled two ways (S).**
- The model's 1.28 is a uniform average over one cell's cycle.
- A population in balanced exponential growth over-represents young cells. Weighting the same
  mean periods (B ≈ 5, C ≈ 46, D ≈ 54 min, p. 6) by that age distribution gives
  2^(C/τ) ≈ 1.35.
- Under the same assumptions (one initiation per cycle, balanced growth), the measured 1.21
  corresponds to a C period of about 29 min.

**The dividing fraction (S).** The model divides for roughly the last 45 minutes of the cycle,
which the authors equate with about 40% of cells dividing (p. 5). Imaging shows about 16%
prolate plus dividing (Fig. 4D). Age weighting still gives about 28–35%.

**Partition noise (S).** Pair differences are centred near zero (Fig. 6, **F**).
- For a fair binomial split of N particles, the difference between daughters has a standard
  deviation of √N: about 30 for ribosomes, 14 for degradosomes, 37 for PtsG and 44 for GapD.
- The observed ranges sit at about ±2 standard deviations, as 50 pairs would give.
- The authors report no test statistic.
- Degradosomes show peaks at both edges, which the authors trace to DNA excluding the layer next
  to the membrane (p. 10).

**Two points the paper does not raise (S).**
- **The cycle does not close on itself.** At 105 minutes each daughter holds about 440
  ribosomes, 88 RNAP and 96 degradosomes. Its mother started with 500, 93 and 120 (Fig. 5;
  p. 6). The median protein reaches 1.9× rather than 2×.
  - Every replicate starts from the same proteomics-based state, and v1 simulates no second
    generation.
  - A model of a cycle should be judged on whether daughters reproduce the mother's starting
    state. This one would drift downward if run on.
- **Most agreement is with inputs or tuned quantities.** Of the abstract's list, only the ori:ter
  ratio rests on a Syn3A measurement made for the purpose and not used to set parameters. The
  authors themselves note that many of their quantities are still predictions awaiting Syn3A
  measurements (p. 10).

## 4. Relevance to Cells, layer by layer

| Cells layer | Bearing | Why |
| --- | --- | --- |
| Bioelectric layer (`resolved_pump_tissue@3`: channels, pumps, junctions, field) | **None** | No membrane potential, ionic current, charge or electrochemical gradient appears anywhere in the model (**S**: a search of the full text finds none) |
| Water and volume (`resolved_pump_water@1/@2`) | **None, and a contrast** | Volume is prescribed by geometry (a sphere until doubled, then constant), not computed from water fluxes. The v1 text describes no osmotic or turgor term |
| Division S2–S5 (insertion, the cleft lumen, `isopotential_partition@1`, bridge closure) | **A contrast, not data** | S5 splits continuum amounts by declared fractions with closed ledgers ([S5 design](CELL_DIVISION_S5_DESIGN.md) §3.3), which is right for ions at 10⁹ molecules and up (**S**). This paper's partition of integer particles is emergent and binomial-like, which matters at tens to hundreds of copies. Its shape is imposed. Microbes are rated a poor fit for Cells' physics in the [division plan](CELL_DIVISION_PLAN.md), and chromosome segregation is outside that plan's scope |
| The composite and its operators ([PUMP_COMPOSITE.md](PUMP_COMPOSITE.md)) | **Architecture lessons** | One shared inventory with explicit conversion points, separate clocks and one exchange loop. The paper gets there with lagged exchange of unmeasured accuracy and no ledgers. The composite uses ordered Strang halves with owned ledgers and refusal |
| Secreted species (D150) | **Slight** | The medium is held constant, and the preprint text describes no secreted species. Nutrient uptake runs through transporters inside the ODE; the transporter set is in Table S2 and the 2022 model, both unread |
| Reactions on the shared inventory (D152, `local_species_reactions@1`) | **Moderate, as a pattern** | Metabolism as kinetic ODE on concentrations at the live volume, with costs drawn from shared pools, is D152's family. The paper adds the stochastic regimes that D152 version 1 does not have ([design](SHARED_INVENTORY_REACTIONS_DESIGN.md) §7) |
| The protein catalogue ([plan](PROTEIN_CATALOGUE_PLAN.md)) | **An omics-parameterisation pattern** | Counts come from proteomics and cryo-ET, or are scaled from *E. coli*. This shows why the catalogue's abundance field must record the method and any transfer between organisms |
| The gene-regulation layer (held, D145) | **Indirect** | Whole-genome expression without regulation, with promoter strengths set from proteomics. A warning for the layer's benchmarks: expression set from one data set cannot be judged against the same data |
| Execution and compute limits | **Direct lessons** | Lessons 1 and 2 in §5 |
| The closed molecular-to-physiology loop | **A worked pattern, no parameters** | Production, assembly, insertion, cost to metabolism and partition all appear in one model, for a bacterium |
| The two preprints | **None as evidence** | No inheritance, memory or pattern question is tested, and every replicate starts from the same state |

## 5. What Cells can learn, ranked

1. **Name every clock and qualify every exchange.**
   - **What the paper shows.** A working hybrid of four methods on clocks from 0.1 ns to 4 s,
     with one store of counts as the single source of truth (§2.2). Its exchanges are lagged,
     and their error is never measured.
   - **Where Cells stands.** The composite already uses ordered half-steps around @3's step,
     with one owner per row and refusal on a failed check ([PUMP_COMPOSITE.md](PUMP_COMPOSITE.md)).
     The [execution architecture](MULTISCALE_EXECUTION_ARCHITECTURE.md#qualification-before-scale-claims)
     asks for the timestep, mesh and coupling interval to be varied separately.
   - **What Cells should do.** Keep both rules for any future operator with its own clock:
     refine the exchange interval against a common-step reference, and refuse a step when a pool
     would be overdrawn at an exchange. Never repay an overdraft with fictitious reactions, as
     the paper does for tRNA (p. 50).
   - **What the paper sidesteps.** Its 1 s exchange freezes the pools that set the rates between
     exchanges. That is the hazard-invalidation problem the execution architecture names for
     bidirectional stochastic coupling ([§ Coupled numerical execution](MULTISCALE_EXECUTION_ARCHITECTURE.md#coupled-numerical-execution)).
     Whether freezing is accurate here was not tested (**S**).
2. **Measure where the time goes before scaling hardware.**
   - **What the paper shows.**
     - The GPU RDME kernel took about 37% of the wall time (**S**, Fig. 1). Work outside it, at
       the pauses, took the rest: ribosome updates at all 80 pauses per biological second, and
       the CME, ODE and output once per second.
     - The large gain was concurrency, not a faster kernel: the polymer moved to its own GPU,
       and a cycle fell from over two weeks to 4–6 days (p. 10).
     - At about 250 GPU-hours per replicate, the study stops at 50 cells. The authors say that
       testing more parameter sets was too expensive (pp. 8, 10).
   - **Where Cells stands.** The [current plan's](CURRENT_PLAN.md#gate-compute-limits)
     compute-limits gate already asks for a full step profile: today only 41.5 of 154 ms is
     accounted for. Cells' design point is the opposite one: many batched worlds per GPU, with
     state kept on the device across windows. The paper's chart is a reminder to report
     host orchestration, transfers and I/O as separate lines, beside the kernels.
3. **Choose stochastic or deterministic by copy number and locality, and say why.**
   - **What the paper shows.** It assigns each process a method by copy number and by whether
     encounters are local (§2.1).
   - **Copy numbers at the scales in question (S).**
     - In a 200 nm cell, one molecule is about 50 nM.
     - In an illustrative 2 pL mammalian cell, 1 nM is about 1,200 molecules.
     - In the 1.28 mm Xenopus egg, 1 nM is about 7 × 10⁸ molecules.
   - **So the deterministic ions are right.** A stochastic regime would enter Cells through
     functional-unit populations on a patch, low-copy transcripts in the gene-regulation layer,
     and secreted proteins at pM to nM in small extracellular volumes.
   - **What to build on.** Cells' one stochastic model, `capsid_graph@1`, already has keyed
     random streams and an exact host oracle ([CAPSID_ASSEMBLY.md](CAPSID_ASSEMBLY.md)). Any
     stochastic door would build on that pattern.
4. **Division: stochastic partition where counts are small, growth from composition, and a
   cycle that closes.**
   - **Partition.** S5 splits by declared fractions, and its design already notes that keyed
     per-carrier streams wait for milestone 2 ([S5 design](CELL_DIVISION_S5_DESIGN.md) §6.1).
     The paper shows the integer case: unbiased, near-binomial partition at hundreds of copies,
     with representation artefacts (the degradosome edge peaks) leaking into the statistics.
     Such artefacts are what an independent reference like S5's R-ops is there to catch.
   - **Inventories through growth and division.** Lattice particles are conserved by
     construction: shape changes move them to the nearest site of their own type, and division
     gives each to one daughter by position (pp. 9, 54–55). The count-to-concentration round
     trip each second and the cost payments carry no reported check (**S**: none found). S5
     instead books every moved quantity as signed transfers that sum to zero, checked against
     an independent reference.
   - **Growth.** The paper's area-from-composition idea fits Cells' membrane entity state, where
     area is already state written by insertion. Its volume-from-geometry rule does not fit:
     Cells has water. Keep area and volume as separate states with their own physics.
   - **The cycle.** Judge the [endogenous lifecycle](CURRENT_PLAN.md#gate-lifecycle-operators)
     on whether daughters reproduce the founder's state over several generations. That check is
     missing from this paper (§3).
5. **Keep inputs, tuned values and held-out tests apart.**
   - **What the paper shows.** The strongest evidence is a measurement made for the purpose:
     sequencing for the ori:ter ratio. Even that agreement depends on population sampling (§3).
     Imposed morphology cannot validate morphology. Proteomics in, proteomics out is circular.
   - **Where Cells stands.** Cells already registers judged observables that the model's own
     rules do not set, so a test can fail. The J1 rule is that no value is picked from Em.
   - **What to add.** Two habits for the gene-regulation layer's benchmarks and the catalogue:
     - record, per value, whether it was used to set the model or to judge it;
     - declare how a simulated population is sampled before comparing it with a population
       measurement.

Three further lessons, lower in rank:

6. **What they found hard is a forecast for Cells' later layers.**
   - **Chromosome segregation:** a fictitious force.
   - **Division machinery:** no FtsZ, and wrong Helfrich shapes.
   - **Objects larger than a lattice site:** the ribosomes, at the cost of polysomes.
   - **Sensitivity to second-order binding rates in 3D:** DnaA, and mRNA with ribosomes or
     degradosomes.
   - **Metabolic balance:** NTPs low while precursors pile up, with no inhibition modelled.
   - **Storage:** one frame per second.
   - **Cost:** it limits any parameter search.

   Each maps to a Cells layer that does not exist yet. Together they argue for building those
   layers from general, qualified operators (D144), and for declaring any constraint force or
   prescribed shape as a stated limit, never as physics.
7. **Expensive fine runs can calibrate cheap reduced models.** The authors use 4D runs to
   constrain well-stirred models, which run in hours and in parallel (p. 11). That is the logic
   of Cells' optional long-time modes, each qualified against the fine engine
   ([D135](DECISIONS.md#d135-optional-long-horizon-time-modes)).
8. **Provenance and restart.**
   - **The deposit.** Code, inputs and outputs are frozen in a citable snapshot, and the Zenodo
     record predates the preprint.
   - **Bookkeeping particles** play the role of Cells' owned accumulators.
   - **Restart.** The repository duplicates the restart path in separate scripts
     (`Restart_Hook.py`, `Restart_MC_RDME_initialization.py`; repository file list). Cells keeps
     one checkpoint path, with a recorded admission for any change
     ([D153](DECISIONS.md#d153-checkpoints-resume-across-a-source-or-runtime-change-only-through-a-recorded-admission)).

## 6. What Cells should not copy

### 6.1 Code and licences (as found on 14 November 2026)

| Component | Where | Licence |
| --- | --- | --- |
| The 4D model's code | [GitHub, Luthey-Schulten-Lab/Minimal_Cell_4DWCM](https://github.com/Luthey-Schulten-Lab/Minimal_Cell_4DWCM) | **No licence file** in the repository |
| Frozen code, inputs and outputs | [Zenodo 10.5281/zenodo.15579159](https://doi.org/10.5281/zenodo.15579159), 2 June 2025, one 12 GB archive | **CC BY 4.0** on the record. This conflicts with the unlicensed repository; we record the conflict and do not resolve it |
| Lattice Microbes (RDME and CME) | GitHub, Luthey-Schulten-Lab/Lattice_Microbes | University of Illinois Open Source License (permissive, notice required), in `docs/LICENSE` |
| odeCELL (ODE metabolism) | GitHub, Luthey-Schulten-Lab/odecell | **GPL-3.0** |
| btree_chromo_gpu (the polymer driver) | GitHub, Luthey-Schulten-Lab/btree_chromo_gpu | **No licence file**. It carries additions to LAMMPS's own source |
| LAMMPS | GitHub, lammps/lammps | **GPL-2.0** |
| sc_chain_generation | GitHub, Luthey-Schulten-Lab/sc_chain_generation | University of Illinois Open Source License |
| FreeDTS (tested, not used) | GitHub, weria-pezeshkian/FreeDTS | **GPL-2.0** |
| The preprint text | bioRxiv | All rights reserved, no reuse |
| The published article | *Cell* | CC BY 4.0 (not read) |

- **The rule.** External simulators are references only: never imported into `src/cells` and
  never copied, run out of process if at all ([AGENTS.md](../AGENTS.md)). That holds whatever the
  licence.
- **Licence compatibility.** Cells is MIT. Three components are copyleft: odeCELL, LAMMPS and
  FreeDTS. Two carry no licence at all, which grants no reuse rights (**S**). Even the
  permissive Lattice Microbes licence changes nothing under the rule above.
- **Note on locations.** The preprint's environment section points to copies of btree_chromo and
  sc_chain_generation under a personal account (p. 59). We read only READMEs, licence files and
  file listings; nothing was cloned, built or run.

### 6.2 Methods

- **A fictitious force presented as segregation**, or any constraint presented as a mechanism.
  Missing mechanisms enter Cells as cited models, never as driver resets or tuned rules
  ([D136](DECISIONS.md#d136-experiments-drive-biologically-valid-engine-features)).
- **Volume prescribed by geometry.** A growth law in Cells must not override the water model.
- **Repaying an overdrawn pool with fictitious reactions.** Cells refuses the step instead.
- **Parameters chosen so that every cell survives, or so that a process happens at all,**
  without a registered selection rule. Cells declares its selection data (the J1 rules).
- **Lagged exchange** with no interval-refinement study.
- **Rate constants converted from another organism's event frequencies** without a check.
- **A time-uniform single-cell average compared with a population measurement.**
- **A polymer clock that is not physical time,** presented as dynamics.

### 6.3 Scope

- **Nothing organism-specific enters `src/cells` for this paper**
  ([D136](DECISIONS.md#d136-experiments-drive-biologically-valid-engine-features),
  [D144](DECISIONS.md#d144-qualify-the-simulator-for-many-uses-not-one-experiment)). That rules
  out a bacterium, a chromosome polymer, SMC extrusion, FtsZ and a lattice RDME.
  - The division plan keeps DNA replication and chromosome packaging out of scope.
  - Mitosis is down the road, under the endogenous lifecycle, with nothing built for it now
    (user, 13 November 2026; [ROADMAP](ROADMAP.md) item 7).
- **No reproduction without approval.** The paper's model is not reproduced, and its outputs are
  not analysed, without the user's approval for this paper
  ([D138](DECISIONS.md#d138-mg1-start-and-the-paper-backlog)). Either is tooling: it runs no
  Cells engine model (AGENTS.md).

## 7. Candidate Cells work, all deferred (D151)

None of these is a feature for this paper (D144). Each would be a general operator or a
validation driver, designed first (D142) and qualified against independent references.

| Rank | Candidate | Prerequisites | Gate | Status |
| --- | --- | --- | --- | --- |
| 1 | **A stochastic reaction door for D152.** Exact stochastic simulation per node for low-copy neutral species rows: integer state, keyed random streams (world, entity, process, event counter), per-event ledger booking. A hybrid split by copy number would come later, with its switching rule qualified. D152's design lists no such door (§7.3), so it would be a new door with its own design note | D152 version 1 landed and MG0c qualified. A named low-copy consumer (most likely transcripts in the gene-regulation layer, or a functional-unit population). A hazard-integration method for propensities that change between events (execution architecture). Independent references: exact chemical-master-equation results, and `capsid_graph@1`'s oracle pattern | Composition (as an operator), consumed by the closed molecular-to-physiology loop | Deferred |
| 2 | **Stochastic partition of integer populations at division.** A binomial split of integer functional-unit abundances per carrier, with keyed streams. Continuum amounts keep S5's declared fractions, and the ledgers are unchanged | Integer abundance as state for one functional-unit population. Carrier-keyed streams (S5 §6.1). The milestone-2 decisions on anchors and slot reuse. Reference: exact binomial moments, with this paper's Fig. 6 as a qualitative comparison only, never a target | Lifecycle operators, endogenous lifecycle (milestone 2) | Deferred |
| 3 | **Division with growth, judged on cycle closure.** Area accumulated from insertion (existing operators), volume from water, material from a production law, a trigger sourced from the literature, and a registered check that daughters reproduce the founder's state over several generations within a declared tolerance | S5b. Water composed with partition (S5 refuses water today). The composition gate's entity volume ledger. A production law (the gene-regulation layer, or D150's production routes) | Lifecycle operators, milestone 2; composition | Deferred |
| 4 | **The closed molecular-to-physiology loop with the paper's cost pattern.** The provisional junction-channel unit (D145): made by a regulated law, drawing precursors and energy from finite pools ([FINITE_ENERGY_POOLS.md](FINITE_ENERGY_POOLS.md)), assembled with delays, inserted and partitioned. The paper supplies a pattern, not parameters | The gate's own list. Catalogue stage 3 (held under D145) | [Closed molecular-to-physiology loop](CURRENT_PLAN.md#gate-a-closed-molecular-to-physiology-loop) | Deferred |
| 5 | **A minimal-cell benchmark world.** A validation driver, not an engine feature: a small cell whose low-copy expression, growth by insertion and stochastic partition use only general operators (ranks 1–4). The paper's published distributions would be an external reference, read out of process | Ranks 1–4. The user's approval to use the paper's outputs (D138) | Endogenous lifecycle and the closed loop | Deferred; far out |
| 6 | **Comparison with the saved Zenodo outputs** (50 traces and 4 trajectories, CC BY 4.0), analysed out of process | The user's approval per paper (D138). Until ranks 1–4 exist, it would run no Cells engine model and is pure tooling | Tooling: the user's approval (D138) | Deferred |
| 7 | **Running their stack** (reproduction), out of process in its own environment | The user's approval (D138). About 250 A100 GPU-hours per replicate: 50 replicates take 12,500–15,000 GPU-hours, more than the whole 10,000 GH200 GPU-hour JUPITER allocation ([ROADMAP](ROADMAP.md)) (**S**). It needs two GPUs per cell | Tooling: the user's approval (D138) | Deferred. This review's judgement is that it would not earn a slot |

Lessons 1, 2 and 5 of §5 need no new item. Exchange qualification is already the execution
architecture's rule, the step profile is already in the compute-limits gate, and registered
judged observables are already Cells' practice.

## 8. What replicating it would mean

- **Wet-lab replication is out of scope.** Cells is a simulator.
- **Data re-analysis is possible but low in value.** The sequencing reads are public
  (PRJNA1257452, nine runs), so the ori:ter ratio could be recomputed. That is tooling and needs
  the user's approval.
- **Two small discrepancies to note.** The BioProject describes samples at 5, 9 and 21 hours,
  while v1's Methods describe 8 and 21 hours (p. 32). v1's Figure 5 legend letters panels F–J
  differently from the panels and the text.
- **Model reproduction means running their code.** It is tooling under D138, at the GPU cost
  above.
- **What Cells could eventually reproduce is the statistical behaviour, not the bacterium:**
  partition noise for integer populations, and whether a simulated cycle closes on itself.
  Both are general questions with exact references.

## 9. Open questions

**For the user.**
1. **Will you supply the *Cell* PDF (CC BY) and the April 2026 erratum** through your own
   browser? A diff pass would then replace the v1 citations with the version of record and check
   what the revision and the erratum changed.
2. **Is a stochastic regime wanted in Cells at all?** If so, which consumer comes first:
   transcripts in the gene-regulation layer, integer functional-unit populations, or low-copy
   secreted species?
3. **Should cycle closure become a registered acceptance criterion** for the endogenous
   lifecycle? Cycle closure means daughters reproduce the founder's state over several
   generations.
4. **Approve, decline or defer** analysing the paper's saved outputs out of process (tooling,
   D138). This review recommends deferring it.
5. **Should a microbe ever be a Cells subject?** The division plan rates microbes a poor fit, and
   this paper's model has no bioelectric content.

**For the lead.**
6. Should the operator contract's qualification checklist name an exchange-interval refinement
   for any operator that keeps its own clock?
7. Should the compute-limits profile report host orchestration, transfers and I/O separately,
   as the paper's Figure 1 does?
8. Should the catalogue's abundance field, at stage 3, record "transferred from another organism
   by scaling" as its own kind of evidence?

## Provenance

**Read in full: the bioRxiv v1 PDF** (63 pages), comprising:
- the main text, the STAR Methods and all figure legends;
- the supplemental figure legends and the reference list;
- the figure pages for Figures 1 and 4–6, and Figures S3 and S4, as images.

**Also read:**
- the published abstract and the article history (PubMed, Europe PMC, Crossref);
- the repositories' READMEs, licence files and file lists;
- the Zenodo record's metadata and the BioProject record.

**Not read:**
- the *Cell* version of record, its STAR Methods and the erratum;
- Tables S1–S3, Data S1, Videos S1–S3 and the key resources table;
- the 2022 *Cell* paper and the other method papers it cites, so no reaction or species count is
  given here;
- the Zenodo archive (12 GB, not downloaded) and the model code itself.

**Access.**
- **Refused:** cell.com and ScienceDirect (HTTP 403); the Copenhagen repository (a Cloudflare
  challenge, not bypassed); Nature's news page (a login redirect).
- **Metadata only:** Elsevier's text-mining API without a key.
- **Embargoed:** the NSF repository, until 1 April 2027.
- **The preprint PDF:** bioRxiv rate-limited three requests (HTTP 429) and then served it to a
  plain request.
- **Requests and privacy.** No request carried a user or project detail, and searches used only
  the paper's own terms.
- **Text extraction.** The PDF's text was extracted with `pdftotext` in a capped unit through
  `scripts/run_detached.sh`, with paths passed as arguments.

For weighing the claims: funding from NSF (MCB 2221237; the Science and Technology Center for
Quantitative Cell Biology, DBI 2243257), the Novo Nordisk Foundation, the Independent Research
Fund Denmark and the Cancer Center at Illinois–Beckman Institute. The authors declare no
competing interests (pp. 12–13).

The access log, notes, downloads, extracted text and the PDF's SHA-256 are under
[/mnt/workspaces/Cells/paper-review-whole-cell-20261114-01](/mnt/workspaces/Cells/paper-review-whole-cell-20261114-01).
These notes introduce no model changes, no runs and no scientific acceptance. Current status
stays in [PROGRESS.md](../PROGRESS.md).
