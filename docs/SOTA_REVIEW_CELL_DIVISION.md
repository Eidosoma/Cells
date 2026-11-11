# How cell division works—and what the latest research is revealing

**Cell division is a coordinated process of copying, mechanical sorting, and reconstruction.** A cell must duplicate its genome, organize the copies so they can be separated, build a force-generating apparatus, divide its membrane and cytoplasm, and establish two functioning daughter cells.

The broad sequence is well established. What research is increasingly resolving is **how the parts coordinate themselves through local interactions, feedback, geometry, and mechanical forces**.

This account covers research available through **11 November 2026**, including a paper published today on how human DNA replication restarts after encountering damage. I’ll focus on **animal and human cells undergoing mitosis**, while identifying findings that come from yeast, frog, or zebrafish experiments. [nature.com](https://www.nature.com/articles/s41586-026-11204-0?utm_source=chatgpt.com)

Two distinctions help throughout:

- **Mitosis** distributes the duplicated chromosomes into two developing nuclei.
- **Cytokinesis** divides the cytoplasm and physically separates the daughters.

These processes overlap, but they have different machinery and can fail independently.

The diagram lets you move through the main stages. It shows three illustrative chromosomes so the mechanics remain visible.







## 1. Before division: deciding to enter the cycle

A proliferating animal cell normally progresses through **G1**, when it grows and prepares; **S phase**, when it copies DNA; **G2**, when it prepares for mitosis; and **M phase**, encompassing mitosis and cytokinesis.

Entry into this sequence depends on growth signals, nutrients, cell size, stress, and tissue context. Many differentiated cells remain outside the active cycle.

### The molecular control system

Much of the timing comes from **cyclin-dependent kinases, or CDKs**. These enzymes attach phosphate groups to other proteins, changing their activity, binding partners, or location. Their cyclin partners help determine when and where they act.

In mammalian cells, an important early pathway involves:

1. Growth-promoting signals increasing cyclin–CDK activity.
2. Changes to **RB-family proteins**, which otherwise restrain proliferation.
3. Activation of **E2F-dependent gene expression**, producing machinery needed for DNA synthesis and further cell-cycle progression.

Feedback reinforces these changes. The result is a series of coordinated transitions rather than a passive timer counting down to division. Recent human-cell experiments also show that CDK4/6–RB regulation directly helps prepare DNA replication origins, extending its role beyond simply increasing the expression of replication proteins. [PMC](https://pmc.ncbi.nlm.nih.gov/articles/PMC12432183/?utm_source=chatgpt.com)

### Recent finding: cells can use their own size to regulate entry

A **13 October 2025 Nature Communications** study followed individual epidermal stem cells in living mouse skin. Their current size helped determine when they entered S phase, through an RB-dependent mechanism.

Changes in the surrounding environment affected how quickly cells grew, while the coupling between size and S-phase entry remained largely cell autonomous in this system.

This provides evidence that at least some cells in intact tissues combine external growth signals with an internal size-control mechanism. It does not establish one universal size threshold for every mammalian cell type. [nature.com](https://www.nature.com/articles/s41467-025-64150-2?utm_source=chatgpt.com)

### Very recent finding: one regulator can have different roles at different stages

**WEE1** is best known for restraining mitotic entry by inhibiting CDKs. But a **21 October 2026 Nature** paper showed that WEE1 can also help human cells return from quiescence to proliferation.

It does this by phosphorylating **CDH1**, weakening the activity of APC/C–CDH1, a protein-destruction system that otherwise suppresses cell-cycle drivers.

The general lesson is that a protein’s effect depends on its targets and the cell’s current state: the same regulator can restrain one transition while facilitating another. [nature.com](https://www.nature.com/articles/s41586-026-11188-x?utm_source=chatgpt.com)

## 2. Copying the genome once, while managing obstacles

DNA replication happens **before** the conspicuous chromosome separation.

A normal diploid human cell has 46 chromosomes. After S phase, it still has 46 chromosomes by the usual counting convention, but each consists of two sister chromatids—92 DNA molecules in total. Successful mitosis distributes one sister from each pair to each daughter.

### First, prepare replication starting points

The genome is copied from many starting regions called **replication origins**.

During G1, proteins including **ORC, CDC6, and CDT1** load pairs of **MCM helicase complexes** onto DNA. This is called **origin licensing**.

The loaded machinery is initially inactive. Later, origin activation turns it into working replication forks.

Separating preparation from activation is central to preventing repeated copying of the same DNA within one cycle. A January 2025 study reconstructed human licensing using purified proteins and resolved structural intermediates, making this process directly accessible to molecular experiments. [PMC](https://pmc.ncbi.nlm.nih.gov/articles/PMC11711466/?utm_source=chatgpt.com)

### Then, assemble moving replication machinery

At an active fork:

- The **CMG helicase** opens the DNA double helix.
- **DNA polymerase ε** performs most leading-strand synthesis.
- **Polymerase α–primase** starts new fragments, especially on the lagging strand.
- **Polymerase δ** extends those lagging-strand fragments.
- Additional enzymes remove primers and join the fragments.
- Sliding clamps and their loaders help keep synthesis coordinated.

Both strands must be copied despite their opposite orientations. Experiments with reconstructed human replisomes show direct coordination: initiating a lagging-strand fragment can transiently slow leading-strand progression, helping the two sides remain synchronized. [nature.com](https://www.nature.com/articles/s41467-026-77578-x?utm_source=chatgpt.com)

### Recent finding: there are alternative routes into DNA replication

A **24 July 2026** study identified two regulatory routes to origin activation in cultured human cells.

One uses **CDC7** to modify MCM, allowing replication to begin at relatively low CDK activity. Another becomes available after APC/C–CDH1 inactivation and requires substantially higher CDK activity.

This reveals flexibility in the initiation system. It also cautions against treating one kinase threshold as a universal trigger for S phase. [nature.com](https://www.nature.com/articles/s41467-026-75804-0?utm_source=chatgpt.com)

### Published today: how copying restarts beyond an obstacle

The **11 November 2026 Nature** paper reconstructed stalled human replication forks and showed that CMG directly recruits and positions **PRIMPOL**, an enzyme that makes a new starting primer on the leading strand beyond an obstruction.

Cryo-electron microscopy and interaction-disrupting mutations supported the mechanism, with additional tests in human cells.

**Restarting does not immediately repair the original lesion.** It allows copying to resume while leaving a gap for subsequent processing. This is one of several ways cells preserve progress when DNA replication encounters trouble. [nature.com](https://www.nature.com/articles/s41586-026-11204-0?utm_source=chatgpt.com)

## 3. Entering mitosis: reorganizing the whole cell

Once replication has progressed sufficiently and checkpoint signals permit it, the cell undergoes a major change in organization.

### A biochemical switch drives the transition

**Cyclin B–CDK1** is a central driver of mitotic entry.

WEE1 adds an inhibitory phosphate to CDK1; **CDC25 phosphatases** remove it. Active CDK1 reinforces its own activation by promoting activating pathways and opposing inhibitory ones.

This feedback helps produce a sharp transition into the mitotic state. Phosphatases that remove modifications from downstream proteins help determine the ordering and reversibility of individual events. [nature.com](https://www.nature.com/articles/s41586-026-11188-x?utm_source=chatgpt.com)

Spatial organization also matters. A **June 2025 Nature** study found that, in fission yeast, CDK activation began in the nucleus and propagated to the cytoplasm, with different switching behavior in the two compartments.

That finding should not be generalized directly to every human cell, but it demonstrates that “CDK activity” can have distinct local dynamics within one cell. [nature.com](https://www.nature.com/articles/s41586-025-09172-y?utm_source=chatgpt.com)

### The cell changes its physical form

Many animal cells become rounder during mitosis. This involves changes to the **actomyosin cortex**, the thin structural network beneath the membrane, together with osmotic and hydrostatic pressure.

Rounding helps establish suitable geometry for the spindle and lets the cell push against surrounding constraints. Experiments measuring rounding forces show that both osmotic regulation and the cortex contribute. [nature.com](https://www.nature.com/articles/nature09642?utm_source=chatgpt.com)

In typical human mitosis, the nuclear envelope also disassembles, giving spindle microtubules access to the chromosomes. Later, declining CDK1 activity permits envelope reconstruction; proteins involved in membrane sealing are themselves controlled by this cycle. [pmc.ncbi.nlm.nih.gov](https://pmc.ncbi.nlm.nih.gov/articles/PMC8324300/?utm_source=chatgpt.com)

## 4. Packaging chromosomes so they can be moved safely

The cell must convert long, intermingled chromatin into mechanically manageable chromosomes while preserving the relationship between each pair of sisters.

Three kinds of machinery are especially important.

### Cohesin maintains sister relationships

A pool of **cohesin** holds replicated sister chromatids together. This connection allows opposing spindle attachments to develop tension without pulling the sisters apart prematurely.

Other cohesin molecules organize DNA loops during interphase. These activities need to be distinguished: the molecules performing sister cohesion are not simply interchangeable with the loop-extruding population.

### Condensins reorganize chromosome architecture

**Condensin I and II** are ATP-dependent DNA-organizing complexes. Their activities help build arrays of loops and produce compact, mechanically robust chromatids.

A 2025 study experimentally separated different cohesin and condensin activities. It showed that they can oppose and reshape one another’s effects during the transition into mitosis. Chromosome formation therefore involves dismantling parts of the interphase architecture while constructing a new one. [nature.com](https://www.nature.com/articles/s41586-025-08638-3?utm_source=chatgpt.com)

### Topoisomerase II removes DNA interlinks

Replication can leave sister DNA molecules topologically intertwined.

**Topoisomerase IIα** resolves these links by temporarily opening one DNA duplex, passing another through, and resealing it. Cutting cohesin alone would not solve this physical entanglement problem.

Single-molecule experiments published in August 2025 directly examined human topoisomerase IIα acting on braided DNA and how cohesin influences its access to that substrate. [pmc.ncbi.nlm.nih.gov](https://pmc.ncbi.nlm.nih.gov/articles/PMC12326010/?utm_source=chatgpt.com)

### Very recent finding: how condensin II is activated

A **20 October 2026 Nature Structural & Molecular Biology** paper showed how phosphorylated **M18BP1** changes the conformation of human condensin II.

Condensin II can adopt an inhibited arrangement. M18BP1 binding releases that inhibition, permitting productive DNA engagement and compaction.

The researchers combined cryo-electron microscopy with single-molecule measurements. They also observed force-resistant condensin assemblies in vitro; whether these provide equivalent mechanical reinforcement inside cells remains a further question. [nature.com](https://www.nature.com/articles/s41594-026-01902-8?utm_source=chatgpt.com)

## 5. Building the spindle: a major example of active self-organization

The **mitotic spindle** is the microtubule-based apparatus that organizes and separates chromosomes.

Microtubules continuously grow, shrink, form connections, and slide relative to one another. The spindle’s overall structure persists while many of its components turn over.

### Where the structure comes from

In typical human somatic cells, duplicated centrosomes help organize two spindle poles. Assembly also occurs around chromosomes and along existing microtubules.

Chromatin-associated **Ran-GTP** signaling releases spindle-assembly factors such as **TPX2**. The **augmin complex** helps recruit microtubule-nucleating machinery to existing microtubules, amplifying the network.

Experiments in frog egg extracts directly demonstrated this branching mode of microtubule production. [pmc.ncbi.nlm.nih.gov](https://pmc.ncbi.nlm.nih.gov/articles/PMC3680348/?utm_source=chatgpt.com)

Motor proteins then help sort and organize the network. **Eg5/KIF11** promotes sliding between oppositely oriented microtubules; **dynein** contributes to organizing and focusing spindle poles.

The self-organizing capacity has long been experimentally clear: spindle-like bipolar structures can assemble around DNA-coated beads in frog egg extracts even without centrosomes or kinetochores. The extract supplies the complex biochemical environment needed for that organization. [nature.com](https://www.nature.com/articles/382420a0?utm_source=chatgpt.com)

### Latest structural evidence: local interactions organize the larger spindle

A **29 October 2026 Nature Communications** paper used cryo-electron tomography to map microtubules and their polarity in human spindles.

It found that local packing depended on microtubule density, consistent with a contribution from steric interactions—physical constraints imposed by neighboring filaments. Eg5 helped establish local antiparallel overlaps, while the balance between Eg5 and dynein affected network organization.

This helps explain how many short microtubules, including ones that do not span the entire pole-to-chromosome distance, collectively form a coherent spindle. The liquid-crystal-like ordering discussed in the paper concerns filament arrangement; it does not imply that the whole spindle is a phase-separated droplet. [nature.com](https://www.nature.com/articles/s41467-026-78938-3?utm_source=chatgpt.com)

### How does the spindle acquire the right dimensions?

Different dimensions can have different controls.

A **9 October 2026 Nature Cell Biology** study found that metaphase-plate width scaled approximately with the cube root of genome size across diverse eukaryotes. Experiments and modeling supported a role for chromosome crowding and pushing forces.

The strongest result concerns **width**. Spindle length also depends on microtubule dynamics, cell dimensions, and cytoplasmic forces. [PMC](https://pmc.ncbi.nlm.nih.gov/articles/PMC13661270/?utm_source=chatgpt.com)

A complementary **June 2026 Science Advances** study examined biochemical activity waves in a cultured rat mast-cell line. Larger cells had longer-period cortical Cdc42 waves. Altering the lipid phosphatase **INPP4B** changed both wave timing and spindle length.

The authors propose that redistribution of signaling components between Golgi-derived membranes and the cell surface helps couple cell size to spindle scaling. This is a compelling mechanism in that experimental system; its prevalence across other cell types is still unresolved. [PMC](https://pmc.ncbi.nlm.nih.gov/articles/PMC13281794/?utm_source=chatgpt.com)

## 6. Attaching chromosomes—and correcting unsuitable attachments

Each sister chromatid builds a **kinetochore**, a large protein assembly at its centromere. The kinetochore couples the chromosome to spindle microtubules.

For accurate division, the two sisters should develop attachments toward opposite poles: **biorientation**.

### A remarkable mechanical interface

The attachment must remain secure while the microtubule itself grows or shrinks.

The **NDC80 and SKA complexes** help create this interface. Multiple copies cooperate, allowing a chromosome to stay connected to a changing microtubule end.

A **March 2026 EMBO Journal** study used reconstructed systems and cryo-electron tomography to show that NDC80–SKA assemblies stabilize microtubule ends by reinforcing interactions between tubulin protofilaments. The collective assembly of these proteins mattered, beyond the ability of individual molecules to bind microtubules. [link.springer.com](https://link.springer.com/article/10.1038/s44318-026-00749-5?utm_source=chatgpt.com)

A further paper published **5 November 2026** identified a region of SKA3 needed for normal progression from metaphase to anaphase, with evidence linking its function to the SKA–NDC80 interaction. This is a recent refinement of how mechanical attachment and mitotic progression are coupled. [pubmed.ncbi.nlm.nih.gov](https://pubmed.ncbi.nlm.nih.gov/42987094/?utm_source=chatgpt.com)

### Error correction changes attachment stability

Early attachments are often unsuitable. Both sisters may connect toward one pole, or one kinetochore may connect to microtubules from both poles.

**Aurora B kinase** contributes to correcting these configurations by modifying attachment proteins and changing how strongly they bind microtubules. Mechanical tension, molecular geometry, and opposing phosphatase activity influence the outcome.

Experiments have shown how increased separation between Aurora B and its targets can stabilize attachments under tension, although this is one component of a more elaborate regulatory system. [pmc.ncbi.nlm.nih.gov](https://pmc.ncbi.nlm.nih.gov/articles/PMC2713345/?utm_source=chatgpt.com)

### The spindle checkpoint buys time

Unattached kinetochores generate signals involving proteins such as **MPS1, MAD2, and BUBR1**. These inhibit **APC/C–CDC20**, delaying the transition into chromosome separation.

The checkpoint is a powerful safeguard, but it does not certify every aspect of spindle correctness. Some abnormal attachments can satisfy attachment-related signaling and still produce segregation errors.

A **23 October 2026 EMBO Journal** study further separated error surveillance from timing control. In engineered human cells, mitotic timing depended jointly on MAD2, inhibitory phosphorylation of CDC20, and CDC20 abundance. Disrupting several restraints caused extremely premature exit and severe chromosome missegregation.

Thus, the apparent “wait until ready” behavior emerges from overlapping controls. [Springer Nature Link](https://link.springer.com/article/10.1038/s44318-026-00931-9?utm_source=chatgpt.com)

## 7. Starting anaphase: releasing the sisters and moving them apart

Once inhibitory checkpoint signaling declines sufficiently, APC/C–CDC20 promotes the destruction of key proteins.

Two targets are central:

- **Securin**, which inhibits the protease separase.
- **Cyclin B**, whose destruction lowers mitotic CDK activity.

Freed **separase** cleaves the RAD21/SCC1 component of cohesin, releasing sister-chromatid cohesion. Structural studies of human separase show how securin and cyclin B–CDK1 provide distinct inhibitory mechanisms before this transition. [pmc.ncbi.nlm.nih.gov](https://pmc.ncbi.nlm.nih.gov/articles/PMC8482764/?utm_source=chatgpt.com)

Chromosome separation then has two broad components:

**Anaphase A:** chromosomes move toward the poles, often with kinetochore-associated microtubules shortening.

**Anaphase B:** the poles themselves move farther apart through microtubule sliding and forces transmitted from the cell cortex.

Their relative contributions differ among cell types.

A key physical point is that **microtubule disassembly can generate force**. The kinetochore captures work from a shortening polymer while maintaining attachment. ATP-powered motors also contribute, but chromosome motion is not explained by motors alone. The recent NDC80–SKA work helps clarify the interface that makes coupling to these dynamic ends possible. [link.springer.com](https://link.springer.com/article/10.1038/s44318-026-00749-5?utm_source=chatgpt.com)

## 8. Choosing the division plane and constricting the cell

As chromosomes separate, the cell must position its cleavage furrow between the two future nuclei.

### A localized RhoA signal organizes the contractile machinery

Signals from the spindle and its surroundings help establish an equatorial zone of active **RhoA**.

An important pathway involves **centralspindlin** and **ECT2**, an enzyme that activates RhoA. RhoA then promotes:

- Actin-filament assembly through formins.
- Myosin-II activation through pathways including ROCK.
- Organization of the membrane–cytoskeleton interface with proteins such as anillin.

This locally assembles a contractile system beneath the membrane.

Experiments using light to activate RhoA at chosen locations can induce ectopic furrows, demonstrating that a localized biochemical signal can organize a force-producing structure. Those furrows do not by themselves establish that every requirement for complete division has been supplied. [pmc.ncbi.nlm.nih.gov](https://pmc.ncbi.nlm.nih.gov/articles/PMC4915195/?utm_source=chatgpt.com)

### The ring continually remodels as it closes

The contractile ring contains actin, myosin, scaffolds, and membrane-binding components. Myosin consumes ATP, but successful closure also requires actin turnover, changing crosslinks, membrane supply, and management of cortical flows.

The membrane’s lipid composition helps organize this machinery. A **February 2026** study showed that septin-associated enzymes create a local pool of **PI(4,5)P₂** at the ingressed furrow. This supports recruitment and retention of proteins needed to organize the intercellular bridge and midbody.

The membrane therefore supplies spatial information and binding sites as well as a physical boundary. [PMC](https://pmc.ncbi.nlm.nih.gov/articles/PMC12886786/?utm_source=chatgpt.com)

### Recent finding: chromosome position can contribute to furrow placement

A **June 2026 Current Biology** study examined a chromatin-derived signal involving **Ran-GTP and importin-β1**.

In HeLa cells, Ran-free importin-β1 accumulated between separating chromosome masses and helped regulate the ring scaffold anillin. The same dependency was absent in the HCT116 cells examined. Changing the chromatin-to-cytosol ratio shifted the localization patterns.

This shows how DNA content and geometry can change which positioning mechanisms a cell depends on. It is not yet a universal explanation for cleavage-plane placement. [sciencedirect.com](https://www.sciencedirect.com/science/article/pii/S0960982226005816?utm_source=chatgpt.com)

## 9. Making the final cut: abscission

Furrow closure usually leaves the daughters connected by a thin **intercellular bridge** containing bundled microtubules and a protein-rich **midbody**.

Physical separation requires another stage: **abscission**.

The **ESCRT-III machinery** assembles and remodels membrane-associated polymers near a secondary constriction beside the midbody. The ATPase **VPS4** drives dynamic exchange and remodeling of these assemblies. Microtubules crossing the bridge must also be removed or severed.

Experiments established that ESCRT turnover and VPS4 activity are part of the working membrane-remodeling mechanism. [doi.org](https://doi.org/10.1038/ncb3559?utm_source=chatgpt.com)

### A safeguard can delay separation

When chromatin remains trapped in the bridge, **Aurora B–CHMP4C signaling** can delay abscission, helping prevent premature resolution and DNA damage. [PMC](https://pmc.ncbi.nlm.nih.gov/articles/PMC3998087/?utm_source=chatgpt.com)

### Recent finding: completion requires clearing an inhibitor

A **2026 Current Biology** study, published online in August and in the October issue, showed that the proteasome helps finish cytokinesis by reducing Aurora B abundance.

When researchers inhibited protein degradation after furrow ingression, Aurora B accumulated, CHMP4C phosphorylation increased, VPS4 recruitment declined, and ESCRT dynamics slowed. Appropriate inhibition of Aurora B rescued the defect.

This connects selective protein destruction to the final mechanical act of division: removing an inhibitor permits the cutting machinery to function. [pubmed.ncbi.nlm.nih.gov](https://pubmed.ncbi.nlm.nih.gov/42636804/?utm_source=chatgpt.com)

## 10. Reconstructing two functioning daughter cells

The daughters inherit much more than DNA sequence.

They receive cytoplasm, membranes, organelles, proteins, RNAs, and molecular states. Some structures persist through division; others are disassembled and reconstructed.

### Rebuilding the nucleus

As mitotic phosphorylation declines, membranes assemble around each chromosome set, nuclear pores establish regulated transport, and the envelope is sealed.

Research on **LEM2, CHMP7, and ESCRT-related machinery** shows how membrane reconstruction is coordinated where chromatin, membranes, and remaining spindle microtubules meet. [pmc.ncbi.nlm.nih.gov](https://pmc.ncbi.nlm.nih.gov/articles/PMC7321842/?utm_source=chatgpt.com)

### Distributing organelles

Organelle inheritance includes active reorganization.

A **June 2026** study found that CDK1 modifies the ER-shaping protein **RTN4**, promoting interactions with Rab11 and dynein-dependent redistribution of tubular ER around centrosomes. Disrupting this organization affected ER inheritance and mitotic fidelity.

The result adds a mechanism connecting the mitotic control system to the distribution of cellular infrastructure. [pubmed.ncbi.nlm.nih.gov](https://pubmed.ncbi.nlm.nih.gov/42325213/?utm_source=chatgpt.com)

### Restoring characteristic genome organization

Mitotic chromosomes have a very different architecture from interphase chromatin. The daughters must re-establish the organization associated with their cell state.

A **Nature Cell Biology paper published online in December 2025**, in the January 2026 issue, experimentally distinguished two contributions:

1. Factors inherited on the chromosomes themselves.
2. Factors inherited through the cytoplasm and subsequently imported into daughter nuclei.

Chromosome-associated information supported compartment formation, while imported factors—including cohesin and transcription-related machinery—modified the developing architecture.

This provides a concrete example of cellular organization being reconstructed through the interaction of inherited chromatin states and inherited cytoplasmic machinery. [nature.com](https://www.nature.com/articles/s41556-025-01828-1?error=cookies_not_supported\&code=e863a12a-cb09-4454-a896-f7bfb753d0f6\&utm_source=chatgpt.com)

## 11. Division changes with cell geometry and tissue context

The standard diagram represents a useful case, but real cells face very different physical conditions.

### Large embryos can divide with an incomplete contractile ring

One of the most striking recent papers is **“A mechanical ratchet drives unilateral cytokinesis,” published in Nature on 7 January 2026**.

Early zebrafish embryonic cells cannot form a conventional closed ring around their large yolk. They instead use an open contractile band.

The study found an alternating sequence:

1. Interphase microtubules stiffen the cytoplasm.
2. This anchors the band along its length and allows it to grow.
3. During the following mitotic phase, the cytoplasm becomes more fluid.
4. Reduced anchoring permits further inward movement.

Repeated changes in material properties advance division over successive nuclear cycles.

Laser ablation, measurements of cytoplasmic mechanics, and modeling supported the mechanism. It demonstrates a different physical implementation of cytokinesis in large embryonic cells, while conventional ring constriction remains applicable to many other cells. [PMC](https://pmc.ncbi.nlm.nih.gov/articles/PMC12916326/?utm_source=chatgpt.com)

### Neighboring cells influence how division proceeds

A **2025 Developmental Cell** study in frog embryonic epithelium found that neighboring cells generate forces that restrain furrow ingression.

Increasing neighboring-cell stiffness slowed division. Weakening mechanical coupling allowed faster closure but increased local breaches in the epithelial barrier.

Division speed therefore has to be coordinated with tissue integrity. Completing a furrow as rapidly as possible is not necessarily the best outcome for the tissue. [pmc.ncbi.nlm.nih.gov](https://pmc.ncbi.nlm.nih.gov/articles/PMC12353914/?utm_source=chatgpt.com)

### The first human embryonic division has particular vulnerabilities

A **September 2026** study used live imaging of donated, discarded human embryos to examine the first division. Fragmentation was associated with unstable central-spindle organization, misplaced furrows, and abnormal actin-ring patterns.

These observations emphasize coordination between chromosome movement and cortical cleavage. They establish associations in this embryonic setting, rather than proving a single initiating defect or a corrective intervention. [nature.com](https://www.nature.com/articles/s42003-026-10962-x?utm_source=chatgpt.com)

## 12. What makes this a self-organizing process?

For the self-organization question, the important feature is how **local molecular rules produce coordinated structures at the scale of the cell**.

Several forms of feedback interact:

| Mechanism | What it contributes |
|---|---|
| Biochemical switches | Coordinate transitions between replication, mitosis, and exit |
| Local activation and inhibition | Restrict assembly to appropriate places |
| Mechanical feedback | Changes attachment stability, force transmission, and shape |
| Molecular turnover | Allows structures to adapt while retaining their overall organization |
| Selective protein destruction | Removes inhibitors and helps make transitions directional |
| Inherited cellular structures and states | Supply the starting conditions for reconstruction |

The spindle and ring are particularly clear examples. Their components respond to nearby filaments, binding partners, membranes, and forces. The larger organization emerges from those interactions and is continually maintained.

This is **active, energy-consuming organization**. ATP supports motors, chromosome-organizing machines, protein modification, and membrane remodeling. GTP-dependent microtubule dynamics also contribute to force generation and structural turnover. The experimental systems discussed above reveal different parts of this coupling between chemical energy and organized motion. [nature.com](https://www.nature.com/articles/s41594-026-01902-8?utm_source=chatgpt.com)

## What remains unresolved?

My assessment of the field is that we have strong causal explanations for many modules, but an incomplete account of their integration across cell types.

The major open questions include:

**How do cells combine different size and geometry signals?**  
The Cdc42-wave and chromosome-crowding results identify distinct mechanisms. Their relative importance across tissues, developmental stages, and genome sizes remains to be established.

**How do mechanical and biochemical safeguards interact quantitatively?**  
We can identify proteins whose disruption causes errors, but predicting an individual cell’s error probability from its molecular state and physical environment is much harder.

**How does the shrinking cortex avoid becoming congested?**  
Material flows toward the furrow while the interface becomes smaller. Assembly, disassembly, and membrane remodeling must remain balanced. A late-October 2026 perspective develops this as a testable framework; it should be treated as an organizing hypothesis rather than a completed experimental explanation. [pubmed.ncbi.nlm.nih.gov](https://pubmed.ncbi.nlm.nih.gov/42929778/?utm_source=chatgpt.com)

**How is daughter-cell state determined?**  
Equivalent chromosome complements do not guarantee equivalent organelle condition, cytoplasmic composition, gene activity, or future fate. Reconstruction of chromatin architecture is one experimentally tractable part of this larger inheritance problem.

**How far are we from a complete predictive model?**  
We can reconstruct replication reactions, spindle-assembly processes, and membrane-remodeling modules. We can also model particular transitions and predict responses to defined perturbations. My synthesis is that we still lack a broadly reliable model that takes a human cell’s molecular state and tissue environment and predicts the timing, geometry, errors, and daughter states of an entire division.

## Papers I would prioritize

For a focused reading path, these give especially useful coverage of the newest mechanisms:

1. **DNA replication recovery — 11 November 2026**  
   [Human replisomes direct a dedicated leading-strand primase for fork restart](https://www.nature.com/articles/s41586-026-11204-0)

2. **Spindle self-organization — 29 October 2026**  
   [CryoET imaging reveals that mitotic spindles are locally organized by microtubule density and Eg5 activity](https://www.nature.com/articles/s41467-026-78938-3)

3. **Checkpoint logic — 23 October 2026**  
   [Differential roles for the spindle assembly checkpoint in error surveillance and mitotic timing](https://link.springer.com/article/10.1038/s44318-026-00931-9)

4. **Chromosome compaction — 20 October 2026**  
   [Mechanism of M18BP1-mediated activation of condensin II for mitotic DNA compaction](https://www.nature.com/articles/s41594-026-01902-8)

5. **Cell-scale biochemical coordination — 19 June 2026**  
   [Mitotic Cdc42 waves encode PI(3,4)P₂ signaling and Golgi morphological state to control spindle scaling](https://pmc.ncbi.nlm.nih.gov/articles/PMC13281794/)

6. **Division through changing material properties — 7 January 2026**  
   [A mechanical ratchet drives unilateral cytokinesis](https://pmc.ncbi.nlm.nih.gov/articles/PMC12916326/)

7. **Reconstruction and cellular inheritance — 22 December 2025**  
   [Interphase chromosome conformation is specified by distinct folding programmes inherited through mitotic chromosomes or the cytoplasm](https://www.nature.com/articles/s41556-025-01828-1)
