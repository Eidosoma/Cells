**Mitochondria: implications for Cells — reviewed 10 October 2026**

Liyam Chitayat, *Mitochondria Are Alive*, Asimov Press, 8 November 2024.
[Article](https://www.asimov.press/p/mitochondria),
[DOI](https://doi.org/10.62211/38pe-75hu).

**Relevant for future bioenergetics, calcium coupling and inheritance work.**
The essay argues for treating mitochondria as living participants within cells.
It is an opinion piece synthesizing other work, with no new experimental
dataset or executable model. For Cells, the useful proposal is to give
mitochondria explicit energetic, chemical and inherited state. Whether to call
them alive need not be settled to model those mechanisms. The priorities below
are proposed work, not implemented or biologically validated capabilities.

Several primary sources sharpen the interpretation:

| Source and evidence | What it supports for our planning | Limit to preserve |
| --- | --- | --- |
| [Kenyon & Moraes, PNAS 1997](https://pmc.ncbi.nlm.nih.gov/articles/PMC23071/), cited by the essay: primate cytoplasts were fused with human cells lacking mtDNA; mtDNA identity, respiration and mitochondrial protein synthesis were measured. | Mitochondrial cargo can change recipient function, with host–donor compatibility constraints. Chimpanzee/bonobo/gorilla donors supported respiration; several other primates did not. | This was engineered cytoplast fusion and selection, not spontaneous uptake of isolated mitochondria as the essay suggests. It is also mtDNA transfer, so it cannot establish inheritance independent of DNA. |
| [Giger et al., Nature 2024](https://www.nature.com/articles/s41586-024-08010-x), cited by the essay: bacteria implanted into fungi were followed by microscopy, spore measurements and adaptive selection. | Compartment compatibility, vertical transmission and host responses are experimentally testable. Different bacterial species had different outcomes. | These were bacteria inside fungi. Host mutations accompanied adaptation; the experiment does not isolate non-genetic memory or supply mitochondrial rate constants. |
| [Rizzuto et al., Science 1998](https://pubmed.ncbi.nlm.nih.gov/9624056/), additional primary source: imaging and a targeted calcium reporter in living HeLa cells. | Following IP3-dependent ER release, calcium near mitochondria exceeded bulk cytosolic calcium. ER–mitochondrial proximity is a useful mechanism to investigate. | A well-mixed cytosol cannot claim to resolve these local concentrations. This review checked the abstract, not a quantitative reanalysis of the images. |
| [Katajisto et al., Science 2015](https://pmc.ncbi.nlm.nih.gov/articles/PMC4405120/), additional primary source: age-labelled mitochondrial components were followed through division of human mammary stemlike cells. | Unequal inheritance of older mitochondrial material was associated with daughter-cell properties; fission perturbation affected segregation and stemness. | This is evidence in a particular experimental system, not proof that an arbitrary acquired mitochondrial state is repeatedly transmitted or regenerated. An age label is not automatically a damage variable. |

The essay's broad mutation-rate multiplier and therapeutic extrapolations are
not suitable simulation defaults. Tissue, organism, assay and intervention
would need their own primary evidence before choosing parameters or endpoints.

The immediate gap in Cells is concrete: the current
[Na/K ATPase](../src/cells/processes/kinetic_pump.py) and
[calcium pump laws](../src/cells/processes/er_calcium.py) use maintained
ATP/ADP/Pi concentrations. Their work is recorded, but pump activity does not
deplete a shared cellular energy supply. The
[resolved calcium model](../src/cells/models/surface_calcium.py) already has
owned chemical stores and separate plasma/ER charge accounting, providing a
possible integration point. Qualification status stays in
[PROGRESS.md](../PROGRESS.md).

| Priority | Proposed addition | First useful experiment or comparison |
| --- | --- | --- |
| First | Finite cell-owned ATP, ADP and phosphate, with an explicitly accounted regeneration source and pump consumption. | Apply a demand pulse or supply interruption; measure ATP recovery, plasma voltage and calcium clearance. Compare against the existing maintained-pool limit. |
| Next | One effective mitochondrial compartment system per cell: matrix/intermembrane ownership, inner-membrane charge, proton buffering, respiratory input, ATP synthesis and nucleotide/phosphate exchange. | Reproduce an isolated-mitochondria reference before connecting it to the tissue model; compare oxygen consumption and energetic state under several loads. |
| Then | Mitochondrial calcium uptake/export and ER proximity, initially through a declared reduced contact-region model. | Compare identical calcium pulses with and without mitochondrial uptake, and vary the contact-region coupling while preserving total calcium. A measured local concentration must not become an unexplained uptake multiplier. |
| Later | Mitochondrial populations, fission/fusion, turnover, material partition at cell division, and optional mtDNA composition. | Test persistence, unequal inheritance and recipient compatibility under a common environment; distinguish genetic change from inherited chemical or structural state. |

A useful starting model is [Beard, PLOS Computational Biology 2005](https://journals.plos.org/ploscompbiol/article?id=10.1371/journal.pcbi.0010036).
It models respiratory complexes, ATP synthesis, transport and both electrical
and chemical contributions to the proton gradient, with mass/charge/free-energy
accounting. Its parameters were fitted to previously measured isolated cardiac
mitochondria data and compared with additional datasets. Those experimental
curves are potential reference targets; the fitted parameters are not universal
measurements for every cell type. **Use the published
[2006 parameter-table correction](https://journals.plos.org/ploscompbiol/article?id=10.1371/journal.pcbi.0020008).**
Equations, corrected parameters and source data would need a pinned reproduction
before adoption; none was ported or executed in this review.

There is an important implementation detail to resolve before sharing ATP:
our Na/K law uses a dimensionless quotient with a 1 M standard state, while the
BETSE calcium laws retain their historical numeric-mM quotient. A new physical
energy module needs consistent chemical potentials, standard-state conversions
and declared pH/Mg assumptions. Keep existing named laws reproducible. The
current ER law also transports one calcium per formal turnover; it should not
silently become a detailed two-calcium SERCA mechanism. Mitochondrial calcium
export requires its own supported transporter law rather than reuse of the
synthetic plasma NCX by name alone.

Proposed accounting requirements are to derive each capacitor voltage from its
own charge, keep plasma/ER/mitochondrial inventories distinct, and count every
exchange once on each side. ATP regeneration must have a declared material and
free-energy source. Closed cases should conserve adenylate and phosphorus
inventories under the chosen reaction scheme; open cases need source ledgers.
Proton buffering and fixed-pH reservoirs need explicit treatment. If later
fission/fusion changes area or capacitance, its material, charge and energy
changes also need accounting. New stiffness and timescales require their own
step-refinement and independent-solver checks.

For Plastic Heredity and Where Do Forms Come From, a useful proposed assay is:
condition otherwise matched cells, remove the conditioning, restore a common
environment, then challenge them. Separately compare retaining, resetting or
transferring mitochondrial state, while controlling mtDNA genotype, host
parameters and ongoing energy supply. Record retention, transfer, expression
and repeated reconstruction as different outcomes. A persistent energetic state
or a single successful transfer would not by itself establish renewable
heredity. Material partition at division must be implemented before interpreting
checkpoint copies as biological inheritance.

For assembly, an eventual energy module could test whether ATP availability
affects a specifically identified ATP-dependent synthesis or remodelling
process. The present neutral protein-bond model has no measured ATP cost;
assigning an ATP charge to every bond event would invent a mechanism. Likewise,
a mitochondrial morphology graph would have different physical meaning from
the protein assembly graph, even if event scheduling and ownership machinery
can be reused.

For the L4 and future 4–16 GPU runs, start with bounded compartment arrays and
independent worlds, then group comparable organelle counts and expected costs.
Retain complete energetic/chemical/event checkpoints and stable random streams
when stochastic turnover is introduced. Couple fast and slow processes using
validated flux exchange if multiple timescales become necessary. Continue
reporting GPU-busy, measured SM-active, coverage, throughput and node-time
accounting; greater biological complexity does not guarantee higher SM use.

**Recommended first follow-up:** after the current electrical/calcium
qualification is resolved, define and verify the finite-energy interface and
reproduce one corrected isolated-mitochondria reference. Full organelle networks
and inheritance experiments can then build on that evidence. This review adds
planning notes only; no simulator changes, parameter fits or runs were made.
