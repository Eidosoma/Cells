# Typical flux values: which cited numbers may stand behind the beads

**Status: research note by agent F for the coordinator, 16 November 2026.** Nothing here is
entered in any data file, and no code or data was changed. The note answers one question:
for the form `typical values` of the flux illustration (`data/layers/flux.json`), which
real numbers exist under terms that let the project keep them? It proposes no change to the
contract; section 6 offers a shape for the coordinator to decide on.

**The licence rule used here.** A source is *permissive* (CC BY, CC0, public domain, or a
plain statement that no restriction is placed on use), *non-commercial* (any CC BY-NC
variant), or *no stated terms*. Only a permissive source stands behind a number in
section 2. Other sources appear in section 3 with what is to be read there and no value.

**A question for the coordinator: numbers a permissive paper restates.** Many rows of
section 2 come from a permissive paper that restates a number first published elsewhere.
This note treats them in two ways:

- where the original is **non-commercial**, the number is not kept: it moved to section 3
  (the cAMP flux per gap junction channel, and the glucose uptake of *M. pneumoniae*);
- where the original has **no stated terms or was not checked**, the number is kept but
  marked *second-hand*, with the original in section 3. Of the 40 rows kept, 24 are
  first-hand, 6 are partly second-hand and 10 are second-hand.

The task's rule for a database or textbook table is to class the original paper. If the
coordinator applies that rule to reviews too, the second-hand rows must also move to
section 3. That would remove the calcium number of the red cell (U4) and the water exchange
time (U17), on which two headline values rest (D3, D5). The sodium and potassium numbers of
the red cell (D2) and its ATP use (D4) rest only on first-hand rows.

**How the licences were read (16 November 2026).** PubMed Central's own article pages
answered automated reading with a robot check. For papers deposited there, the licence was
read in the paper's full text as PubMed Central holds it, served by Europe PMC; that text
carries the publisher's own licence statement. Two papers were also read on the
publisher's page (PLOS, Frontiers). The fetching tool returned long licence lines in
pieces, which are joined here. The URL read is given for each source. If the coordinator
wants each licence re-read on the PubMed Central page in a browser, the PMC numbers are
given. Nothing was saved to disk, so no folder under `/mnt/datasets/Cells/flux/` was made.

**Words used.** *Flux*: how many ions or molecules cross a membrane each second.
*Unidirectional* flux counts one way only; *net* flux is inward minus outward. A *pump-leak
turnover* is the rate at which a pump moves an ion out while the same ion leaks back in at
the same rate, so the cell stays steady. *mmol/(L cells·h)*: millimoles per litre of packed
cells per hour; it becomes a per-cell number only once the number of cells in a litre is
known (section 4). *First-hand*: the permissive paper measured, modelled or stated the number
itself, citing no other paper for it. *Second-hand*: the permissive paper cites another paper
for the number; that paper is listed in section 3.

## 1. In short

- **The human red blood cell is the one cell for which typical values can be shown today
  for most lanes.** One CC BY review gives the sodium and potassium pump-leak turnover and
  the cell's whole fuel (ATP) use in one unit, and also the number of red cells and their
  total volume in an adult, which turns those into numbers per cell. All of that is
  first-hand. Per cell: roughly 33,000 to 50,000 sodium ions a second through the pumps (and
  as many leaking back in), and roughly 17,000 to 33,000 ATP a second.
- **Two more red-cell numbers rest on second-hand values** and stand or fall with the
  question above: roughly 330 to 840 calcium ions a second through the calcium pump, and
  roughly 2.5 × 10¹⁴ water molecules a second crossing each way. The same review is the
  source, but it cites a 1982 paper with no stated terms for the calcium, and the water
  exchange time is from the review's authors' earlier work.
- **A red cell is not a generic cell**: it has no nucleus and no mitochondria, and the page
  would have to say so.
- **For a nucleated human cell there is a pump value, not a full set.** A CC BY model of the
  human retina puts the sodium–potassium pump of one retinal pigment epithelium cell at about
  1.07 × 10⁸ ATP a second (second-hand). Taking one ATP per pump cycle, an assumption no
  source read here states, that is about 3.2 × 10⁸ sodium ions out. A CC BY measurement on a
  human glioblastoma cell line (U87-MG) gives the pump's *maximum* rate, about 2 × 10⁸ cycles
  a second, and its resting leak conductances for sodium, potassium and chloride.
- **Ion channels**: a CC BY review says a typical open channel passes millions to tens of
  millions of ions a second. No species, no cell. **Gap junctions**: CC BY measurements on
  pairs of cultured human cells (HeLa) made to carry rat and chicken connexins give
  junctional conductances of 8.4 to 32 nS. A conductance becomes ions per second only for a
  stated voltage difference between the two cells.
- **Secretion**: one well-studied case, CC BY and first-hand: mouse T cells release
  interleukin-2 at about 7.5 molecules per cell per second, rising up to about 30-fold when
  strongly stimulated.
- **Fuel in *E. coli***: CC BY, measured and first-hand: about 6.4 million ATP a second per
  cell in fast growth, falling to about 0.23 million in stationary phase (strain BW25113, a
  K-12 derivative, minimal medium, 37 °C). *E. coli* has no numbers here for pumps,
  channels, water or secretion; its water permeability exists only in papers with no stated
  terms.
- **Cannot be shown today**: the number of sodium–potassium or calcium pumps on a red cell
  (only in sources with no stated terms or not checked); a chloride flux of any cell; anything
  for the fruit fly or the planarian; per-cell numbers for thale cress (only a plant proton
  pump's rate per pump and currents per area in root cells under patch-clamp conditions,
  second-hand); per-cell numbers for JCVI-syn3A and *Mycoplasma pneumoniae* (their energy
  numbers are per gram of dry mass, and no permissive dry mass per cell was found).

## 2. Usable numbers (permissive sources only)

Each row is one number from a source classed permissive. The sources (S1 to S18) are listed
in full under the tables, with the licence line, the URL read and the day. The column "How
obtained" says whether the row is first-hand or second-hand, and names the original
(P-numbers, section 3). Numbers are written as the source gives them.

### Human red blood cell

| # | Quantity | Value | Cell, conditions | How obtained | Source, where |
| --- | --- | --- | --- | --- | --- |
| U1 | Red blood cells in a healthy adult | about 2 · 10¹³ cells | human adult | first-hand: review statement, no citation | S1, Abstract |
| U2 | Total red cell volume in a healthy adult | ~2 L | human adult | first-hand: review statement, no citation | S1, "Key features of volume control in human RBCs" |
| U3 | Pump-leak turnover of Na⁺ and K⁺ | about 2–3 mmol/(L cells·h) | middle-aged human red cells, "mean population values" | first-hand: review statement, no citation; one range is given for both ions | S1, same section |
| U4 | Pump-leak turnover of Ca²⁺ | about 20–50 µmol/(L cells·h) | human red cells, physiological conditions | second-hand: cited from P4 (no stated terms) | S1, same section |
| U5 | Calcium pump capacity when saturated with Ca²⁺ | about three orders of magnitude above U4 (a ratio, no value) | human red cells | second-hand: cited from P3 (no stated terms) and P21 (not checked) | S1, same section |
| U6 | ATP turnover of the whole cell | about 1.0–2.0 mmol/(L cells·h) | normal, mature, middle-aged human red cells | first-hand: review statement, no citation | S1, same section |
| U7 | Na⁺ efflux through the Na/K pump, model reference state | −3.2 mmol/(Loc·h) (minus: out of the cell) | human red cell model at the start of a simulated life span | first-hand: a model setting, not a measurement. The unit "Loc" is defined in the model's user guide, which was not read; the paper's reference cell is "1 L/Loc" | S2, Figure 3 legend |
| U8 | Calcium pump (PMCA) maximum rate, model default | 12 mmol/(Loc·h) (one run doubles it to 24) | as U7 | first-hand: model default, not a measurement | S2, Results, "The Reference pattern" |
| U9 | Water in the reference cell | 0.75 L cell water per Loc (with 0.25 L haemoglobin and 340 g haemoglobin per Loc) | as U7 | first-hand: the model's definition of its reference cell | S2, Figure 3 legend |
| U10 | Share of the cell's ATP used by the pumps | Na⁺/K⁺-ATPase 40%, Ca²⁺-ATPase 10% "of the total ATP produced by erythrocytes" | human red cells | first-hand by the rule, but the sentence cites nothing, so its basis is unknown | S3, Results, "Classification of membrane transport proteins" |
| U11 | Osmotic water permeability, P_f | 3.27 ± 0.01 × 10⁻² cm/s (AQP1-null cells: 0.41 ± 0.03) | human red cells, control donors, 15 °C | first-hand: measured, stopped-flow light scattering | S4, Table 2 |
| U12 | Diffusional water permeability, P_d | 2.77 ± 0.04 × 10⁻³ cm/s (AQP1-null: 0.73 ± 0.02) | human red cell ghosts, 15 °C | first-hand: measured, stopped-flow fluorescence in heavy water | S4, Table 2 |
| U13 | Water through one aquaporin-1 (AQP1) channel | diffusional p_d 1.67 (1.38–1.97) × 10⁻¹⁴ cm³/s; osmotic p_f 23.5 (19.4–27.7) × 10⁻¹⁴ cm³/s | per AQP1 monomer, human red cells, 15 °C | partly second-hand: computed in the paper from U11, U12 and copy numbers of 150,000–200,000 cited from two papers (one is P2) | S4, Table 2 and its footnote |
| U14 | AQP1 copies per red cell | ~2 × 10⁵ | human red cells | second-hand: cited from P2 (unresolved) | S4, Discussion |
| U15 | UT-B (urea transporter, also passes water) copies per red cell | 13.91 ± 0.31 × 10³ | human red cells, control | first-hand: measured, flow cytometry with calibration beads | S4, Table 1 |
| U16 | Diffusional water permeability, P_d | ~4 × 10⁻³ cm/s at 25 °C; ~7 × 10⁻³ cm/s at 37 °C | human red cells | second-hand: the review's authors' earlier NMR papers (P20, not checked) | S5, Section 3 |
| U17 | Water exchange time across the membrane | about 10 ms | red cells of children (an epilepsy study and its controls); temperature not stated | hand uncertain, treated as second-hand: the passage describes the review's authors' earlier study (P20) and cites the method (P11, NMR with manganese added to the plasma); whether the value itself carries a citation was not checked | S5, Section 2 |

### Nucleated human cells

| # | Quantity | Value | Cell, conditions | How obtained | Source, where |
| --- | --- | --- | --- | --- | --- |
| U18 | ATP used by the Na⁺/K⁺-ATPase | 1.07 × 10⁸ ATP/s per cell (demand); maximum from pump abundance × turnover 2.05 × 10⁸ ATP/s per cell | human retinal pigment epithelium cell | partly second-hand: the demand is cited from a theoretical model (P12, not checked); the maximum is computed in the paper | S6, Results, "Plasma membrane ion transport" |
| U19 | Na⁺/K⁺-ATPase turnover used | k_cat 45 s⁻¹ | as U18 | first-hand: taken from the paper's own supplement (S1 File), no published reference given | S6, same section |
| U20 | ATP needed to pump out a rod's dark current | 1.02 × 10⁸ ATP/s per rod (dark current 40 pA) | human retina model, rod photoreceptor in darkness | partly second-hand: computed in the paper from a current cited from P13 (not checked) | S6, same section |
| U21 | Maximum Na⁺/K⁺ pump current density | 0.9 ± 0.1 pA/pF; with 36 pF, ≈ 3.35 × 10⁻⁴ pmol/s per cell | U87-MG human glioblastoma cells in culture | first-hand: measured, perforated patch clamp, ouabain-sensitive current | S7, Sections 4.2.4 and 4.3 |
| U22 | Pump density | ≈ 560 pumps/µm² (a range for other cells, 400–1200, is cited) | as U21 | first-hand: derived in the paper from U21 *assuming* about 100 cycles/s per pump | S7, Section 4.2.4 |
| U23 | Cell size and membrane capacitance | radius 10.3 ± 1.1 µm, volume 4.7 ± 1.4 pL; capacitance about 36 pF (35.3 ± 10.7 pF in the leak recordings) | as U21 | first-hand: measured | S7, Sections 4.1.2 and 4.3; Table 3 |
| U24 | Resting leak conductances, per membrane capacitance | Na⁺ 0.00504 ± 0.0032 nS/pF; K⁺ 0.00432 ± 0.0025 nS/pF; Cl⁻ 0.0044 ± 0.0039 nS/pF (n = 8 each) | as U21, resting conditions | first-hand: measured with voltage ramps and channel blockers | S7, Table 3 |

### Channels and junctions (no single species unless stated)

| # | Quantity | Value | Cell, conditions | How obtained | Source, where |
| --- | --- | --- | --- | --- | --- |
| U25 | Ions through one open channel | "millions of ions per second"; "fluxes of tens of millions of ions per second" | typical ion channels, no species | first-hand: review statement, no citation | S8, Introduction and "Noise analysis and patch clamp" |
| U26 | Ions through one channel compared with transporters | channels "often transport over 10⁶ ions/(second*molecule)"; transporters about 100–10,000 ions per second | general | second-hand: cited from two textbooks (P23, not checked) | S9 (section not recorded) |
| U27 | Junctional conductance between two coupled cells | mono-heteromeric pairs: 8.59 ± 0.64 nS (MhetCx43, n = 175) and 8.37 ± 0.99 nS (MhetCx45, n = 73); homotypic Cx43, homotypic Cx45 and bi-heteromeric pairs: 27–32 nS | HeLa cell pairs transfected with rat Cx43 and chicken Cx45 | the 8.4–8.6 nS values first-hand, measured; the 27–32 nS restated "as we have previously published" (P24, not identified) | S10, Results, "Total junctional conductance is reduced in mono-heteromeric channels" |
| U28 | One Cx43 gap junction channel, and channels per junction | 120 pS; about 266 channels per homotypic Cx43 junction | as U27 | first-hand: 120 pS is the authors' working value, not measured here; 266 is their calculation (36,000 pS ÷ 120 pS) | S10, Discussion |

### Secretion

| # | Quantity | Value | Cell, conditions | How obtained | Source, where |
| --- | --- | --- | --- | --- | --- |
| U29 | Interleukin-2 (IL-2) released | basal 7.5 molecules per cell per second; maximal boost 30-fold, "hence 225 molecules per second per cell" | mouse 5C.C7 T cells in culture, stimulated with antigen peptide, populations of 10³ to 10⁵ cells, about 8 h | first-hand: estimated from IL-2 measured by ELISA in the culture medium over time | S12, Figure 8—figure supplement 1B; Figure 7 legend |

### *Escherichia coli*

| # | Quantity | Value | Strain, conditions | How obtained | Source, where |
| --- | --- | --- | --- | --- | --- |
| U30 | ATP consumed per cell | 6.4 million ATP/s (table: 6.38) in exponential growth; about 0.82 million in lag phase; about 0.23 million in stationary phase. ATP pool turned over in about 0.33 s | BW25113, "the parental strain of the Keio knockout collection" (a K-12 derivative; the paper does not say K-12), minimal medium, 37 °C; per cell assuming 1 fL per cell | first-hand: measured with an ATP reporter and a luciferase assay, fitted with a kinetic model, three experiments | S13, Abstract, Results, Table 1 |
| U31 | ATP consumed per growing cell, earlier reports | "between 1 and 10 million ATP/cell/s" | growing *E. coli* | second-hand: S13's reference 51 (P22, not identified) | S13, Results |
| U32 | Maintenance and growth cost of a bacterial cell | maintenance C_M = 0.39 V^0.88 (10⁹ ATP per cell per hour, V in µm³); growth C_G = 27 V^0.97 (10⁹ ATP per cell); standard errors of the exponents 0.07 and 0.04; *E. coli* volume "on average" 1.0 µm³ | fitted across many bacteria | first-hand: the paper's fit to published data | S14, "The energetic costs of building and maintaining a cell" (Equations 1a, 1b); "The biosynthetic cost of lipids" |
| U33 | ATP made by one ATP synthase | required rates of 221 (*E. coli*), 19 (*M. pneumoniae*) and 2109 (*B. subtilis*) ATP per complex per second | as named | first-hand: the paper's estimates | S14, Section 2.2 |
| U34 | ATP cost of building one cell | 4.85 × 10¹⁰ ATP | a 1 µm³ bacterium modelled on *E. coli* | first-hand: the authors' calculation | S15, Section 4 |
| U35 | Na⁺/H⁺ antiporter NhaA turnover | about 1500 ions per second at pH 8.5 | *E. coli* NhaA | second-hand: cited from P16 (not checked) | S9 (section not recorded) |

**Sources disagree on the cost of a cell:** U32 gives 27 × 10⁹ ATP for growth of a 1 µm³
cell (plus maintenance for the time it takes to divide), while U34 gives 48.5 × 10⁹ ATP for
a 1 µm³ cell modelled on *E. coli*. S15 also gives 27 and 47 × 10⁹ ATP by two other routes
(by its Equation 2, which leaves out maintenance, and by elemental composition). Neither is
needed for a lane; U30 is the measured rate.

### Thale cress and plants, JCVI-syn3A

| # | Quantity | Value | Organism, conditions | How obtained | Source, where |
| --- | --- | --- | --- | --- | --- |
| U36 | Ions moved by one plant plasma-membrane proton pump (H⁺-ATPase) | "about 100 ions per a second" | plants in general; no species or cell type named | second-hand: cited from P17 (not checked) | S16, "Ion Channels vs. Ion Transporters" |
| U37 | Inward K⁺ and Na⁺ currents per area | K⁺: about 120 mA/m² (about 1.2 µmol/(m²·s)); Na⁺: about 70 mA/m² (about 700 nmol/(m²·s)) | *Arabidopsis thaliana* root protoplasts, patch clamp at −80 mV in 100 mM KCl or NaCl: forced conditions, not a resting cell | second-hand: cited from P18 (not checked) | S16, "Comparison between Different Methods for Measuring Ion Fluxes" |
| U38 | ATP for maintenance (not for growth) | total 3.30 mmol ATP per g dry mass per hour, of which 0.57 is for pumping protons out (from about 2.30 mmol H⁺ per g dry mass per hour, at 4 H⁺ per ATP) | JCVI-syn3A, metabolic model | partly second-hand: model values; the proton rate is converted from a cited measurement (not checked) | S17, "GAM/NGAM" |
| U39 | ATP for growth | 46.54 mmol ATP per g dry mass (compared with 53.95 estimated for *E. coli*) | JCVI-syn3A, metabolic model | first-hand: model | S17, "GAM/NGAM" |
| U40 | K⁺ uptake | model 0.29 mmol per g dry mass per hour; measured 0.49 in *Mycoplasma mycoides capri* PG3 | JCVI-syn3A model; the measured value is of a relative | partly second-hand: the model value is the paper's; the measurement is cited (not checked) | S17, "Ion uptake" |

### Sources (all read on 16 November 2026)

Each licence line is quoted as the paper states it. Where it is long, the part that
decides the class is quoted. "Read at" is the URL actually fetched.

- **S1** Lew VL, Tiffert T (2017). On the mechanism of human red blood cell longevity: roles
  of calcium, the sodium pump, PIEZO1, and Gardos channels. *Frontiers in Physiology* 8:977.
  doi:10.3389/fphys.2017.00977. PMC5732905. Read at
  https://www.frontiersin.org/journals/physiology/articles/10.3389/fphys.2017.00977/full and
  https://www.ebi.ac.uk/europepmc/webservices/rest/PMC5732905/fullTextXML. Licence: "This is
  an open-access article distributed under the terms of the Creative Commons Attribution
  License (CC BY)." **Permissive.**
- **S2** Rogers S, Lew VL (2021). PIEZO1 and the mechanism of the long circulatory longevity
  of human red blood cells. *PLoS Computational Biology* 17(3):e1008496.
  doi:10.1371/journal.pcbi.1008496. Read at
  https://journals.plos.org/ploscompbiol/article?id=10.1371/journal.pcbi.1008496. Licence:
  "This is an open access article distributed under the terms of the Creative Commons
  Attribution License, which permits unrestricted use, distribution, and reproduction in any
  medium, provided the original author and source are credited." **Permissive.**
- **S3** Haiman ZB, Key A, D'Alessandro A, Palsson BO (2025). RBC-GEM: a genome-scale
  metabolic model for systems biology of the human red blood cell. *PLoS Computational
  Biology* 21(3):e1012109. doi:10.1371/journal.pcbi.1012109. PMC11925312. Read at
  https://www.ebi.ac.uk/europepmc/webservices/rest/PMC11925312/fullTextXML. Licence: "This is
  an open access article distributed under the terms of the Creative Commons Attribution
  License, which permits unrestricted use, distribution, and reproduction in any medium,
  provided the original author and source are credited." **Permissive.**
- **S4** Azouzi S, et al. (2013). Energetic and molecular water permeation mechanisms of the
  human red blood cell urea transporter B. *PLoS ONE* 8(12):e82338.
  doi:10.1371/journal.pone.0082338. PMC3869693. Read at
  https://www.ebi.ac.uk/europepmc/webservices/rest/PMC3869693/fullTextXML. Licence: "This is
  an open-access article distributed under the terms of the Creative Commons Attribution
  License, which permits unrestricted use, distribution, and reproduction in any medium,
  provided the original author and source are properly credited." **Permissive.**
- **S5** Benga G, Cox G (2022). Light and scanning electron microscopy of red blood cells
  from humans and animal species providing insights into molecular cell biology. *Frontiers
  in Physiology* 13:838071. doi:10.3389/fphys.2022.838071. PMC9283769. Read at
  https://www.ebi.ac.uk/europepmc/webservices/rest/PMC9283769/fullTextXML. Licence: "This is
  an open-access article distributed under the terms of the Creative Commons Attribution
  License (CC BY)." **Permissive.**
- **S6** Kiel C, Prins S, Foss AJE, Luthert PJ (2025). Energetics of the outer retina II:
  calculation of a spatio-temporal energy budget in retinal pigment epithelium and
  photoreceptor cells based on quantification of cellular processes. *PLoS ONE*
  20(1):e0311169. doi:10.1371/journal.pone.0311169. PMC11771881. Read at
  https://www.ebi.ac.uk/europepmc/webservices/rest/PMC11771881/fullTextXML. Licence: "This is
  an open access article distributed under the terms of the Creative Commons Attribution
  License, which permits unrestricted use, distribution, and reproduction in any medium,
  provided the original author and source are credited." **Permissive.**
- **S7** Catacuzzeno L, Cavaliere MG, Michelucci A (2026). An approach based on linear
  programming to build experimentally driven pump-leak models. *Biophysical Journal*
  125(4). doi:10.1016/j.bpj.2026.01.021. PMC13351560. Read at
  https://www.ebi.ac.uk/europepmc/webservices/rest/PMC13351560/fullTextXML. Licence: "This is
  an open access article under the CC BY license (http://creativecommons.org/licenses/by/4.0/)."
  **Permissive.**
- **S8** Catacuzzeno L, Michelucci A, Franciolini F (2025). The crucial decade that ion
  channels were proven to exist. *Pflügers Archiv* 477:903–917.
  doi:10.1007/s00424-025-03085-5. PMC12152087. Read at
  https://www.ebi.ac.uk/europepmc/webservices/rest/PMC12152087/fullTextXML. Licence: "Open
  Access This article is licensed under a Creative Commons Attribution 4.0 International
  License …" **Permissive.**
- **S9** Volkov V (2015). Quantitative description of ion transport via plasma membrane of
  yeast and small cells. *Frontiers in Plant Science* 6:425. doi:10.3389/fpls.2015.00425.
  PMC4462678. Read at https://www.ebi.ac.uk/europepmc/webservices/rest/PMC4462678/fullTextXML.
  Licence: "This is an open-access article distributed under the terms of the Creative
  Commons Attribution License (CC BY)." **Permissive.**
- **S10** Zhong G, et al. (2017). Mono-heteromeric configurations of gap junction channels
  formed by connexin43 and connexin45 reduce unitary conductance and determine both voltage
  gating and metabolic flux asymmetry. *Frontiers in Physiology* 8:346.
  doi:10.3389/fphys.2017.00346. PMC5447054. Read at
  https://www.ebi.ac.uk/europepmc/webservices/rest/PMC5447054/fullTextXML. Licence: "This is
  an open-access article distributed under the terms of the Creative Commons Attribution
  License (CC BY)." **Permissive.**
- **S11** Brink PR, Valiunas V, White TW (2020). Lens connexin channels show differential
  permeability to signaling molecules. *International Journal of Molecular Sciences*
  21(18):6943. doi:10.3390/ijms21186943. PMC7555617. Read at
  https://www.ebi.ac.uk/europepmc/webservices/rest/PMC7555617/fullTextXML. Licence: "This
  article is an open access article distributed under the terms and conditions of the
  Creative Commons Attribution (CC BY) license (http://creativecommons.org/licenses/by/4.0/)."
  **Permissive.** Its cAMP numbers are restated from P7 (non-commercial), so none is kept.
- **S12** Tkach KE, et al. (2014). T cells translate individual, quantal activation into
  collective, analog cytokine responses via time-integrated feedbacks. *eLife* 3:e01944.
  doi:10.7554/eLife.01944. PMC3980879. Read at
  https://www.ebi.ac.uk/europepmc/webservices/rest/PMC3980879/fullTextXML (eLife's own page
  did not load for automated reading). Licence: "This article is distributed under the terms
  of the Creative Commons Attribution License, which permits unrestricted use and
  redistribution provided that the original author and source are credited." **Permissive.**
- **S13** Deng Y, Beahm DR, Ionov S, Sarpeshkar R (2021). Measuring and modeling energy and
  power consumption in living microbial cells with a synthetic ATP reporter. *BMC Biology*
  19:101. doi:10.1186/s12915-021-01023-2. PMC8130387. Read at
  https://www.ebi.ac.uk/europepmc/webservices/rest/PMC8130387/fullTextXML. Licence: "This
  article is licensed under a Creative Commons Attribution 4.0 International License …"; and
  "The Creative Commons Public Domain Dedication waiver
  (http://creativecommons.org/publicdomain/zero/1.0/) applies to the data made available in
  this article, unless otherwise stated in a credit line to the data." **Permissive.**
- **S14** Lynch M, Marinov GK (2017). Membranes, energetics, and evolution across the
  prokaryote-eukaryote divide. *eLife* 6:e20437. doi:10.7554/eLife.20437. PMC5354521. Read at
  https://www.ebi.ac.uk/europepmc/webservices/rest/PMC5354521/fullTextXML. Licence: "This
  article is distributed under the terms of the Creative Commons Attribution License, which
  permits unrestricted use and redistribution provided that the original author and source
  are credited." **Permissive.**
- **S15** Schavemaker PE, Lynch M (2025). Bioenergetics and the evolution of cellular
  traits. *Annual Review of Biophysics* 54:81–99.
  doi:10.1146/annurev-biophys-070524-090334. PMC12921477. Read at
  https://www.ebi.ac.uk/europepmc/webservices/rest/PMC12921477/fullTextXML. Licence: "This
  work is licensed under a Creative Commons Attribution 4.0 International License, which
  permits unrestricted use, distribution, and reproduction in any medium, provided the
  original author and source are credited." **Permissive.**
- **S16** Volkov V (2015). Salinity tolerance in plants. Quantitative approach to ion
  transport starting from halophytes and stepping to genetic and protein engineering for
  manipulating ion fluxes. *Frontiers in Plant Science* 6:873.
  doi:10.3389/fpls.2015.00873. PMC4621421. Read at
  https://www.ebi.ac.uk/europepmc/webservices/rest/PMC4621421/fullTextXML. Licence: the
  article is open access under the "Creative Commons Attribution License (CC BY)" (the rest
  of the paragraph was not returned). **Permissive.**
- **S17** Breuer M, et al. (2019). Essential metabolism for a minimal cell. *eLife*
  8:e36842. doi:10.7554/eLife.36842. PMC6609329. Read at
  https://www.ebi.ac.uk/europepmc/webservices/rest/PMC6609329/fullTextXML. Licence: "This
  article is distributed under the terms of the Creative Commons Attribution License".
  **Permissive.** Its glucose uptake for *M. pneumoniae* is restated from P10
  (non-commercial), so it is not kept.
- **S18** Gaimster H, et al. (2014). The indole pulse: a new perspective on indole
  signalling in *Escherichia coli*. *PLoS ONE* 9(4):e93168.
  doi:10.1371/journal.pone.0093168. PMC3973702. Read at
  https://www.ebi.ac.uk/europepmc/webservices/rest/PMC3973702/fullTextXML. Licence: "This is
  an open-access article distributed under the terms of the Creative Commons Attribution
  License, which permits unrestricted use, distribution, and reproduction in any medium,
  provided the original author and source are properly credited." **Permissive.** (Used only
  in section 5.)

## 3. Pointers: numbers in sources that are not permissive, or not checked

No value is copied from these. The class of a source marked "Europe PMC record" was read
from the licence field of its record at Europe PMC, not on the publisher's page. "Not
checked" means the licence was not read in this round; such a source is treated as having
no stated terms until someone reads it.

| # | What is to be read there | Source | Class, and how it was found |
| --- | --- | --- | --- |
| P1 | Sodium pumps per human red cell, counted by ouabain binding, in young and old cells (as its title says; not read) | Ouabain binding and potassium transport in young and old populations of human red cells. *Membrane Biochemistry* 1978. doi:10.3109/09687687809063847 | No stated terms (Europe PMC record) |
| P2 | Copies of AQP1 (then "CHIP28") per human red cell, the original of U14 | Identification, purification, and partial characterization of a novel Mr 28,000 integral membrane protein from erythrocytes and renal tubules. *J Biol Chem* 1988. doi:10.1016/s0021-9258(19)37635-5 | **Unresolved.** The Europe PMC record lists "cc by", but the publisher's pages refused automated reading (HTTP 403). If the coordinator reads a CC BY line on the journal's page, this becomes a usable original and U14 becomes first-hand |
| P3 | Maximum calcium extrusion capacity of the red cell calcium pump, and its stoichiometry (behind U5) | Maximal calcium extrusion capacity and stoichiometry of the human red cell calcium pump. *J Physiol* 1988;407:569–586. doi:10.1113/jphysiol.1988.sp017432 | No stated terms (Europe PMC record) |
| P4 | Resting Ca²⁺ level and calcium pump-leak turnover in intact red cells (the original of U4) | Physiological [Ca²⁺]i level and pump-leak turnover in intact red cells measured using an incorporated Ca chelator. *Nature* 1982;298:478–481. doi:10.1038/298478a0 | No stated terms (Europe PMC record) |
| P5 | Osmotic water permeability of human red cells and how it depends on the direction of flow and on cell volume | Osmotic water permeability of the human red cell. *J Gen Physiol* 1983;81:213. doi:10.1085/jgp.81.2.213 | Non-commercial: CC BY-NC-SA (Europe PMC record) |
| P6 | Counts of ions and water molecules moving in single file through an open potassium channel | Counting ion and water molecules in a streaming file through the open-filter structure of the K channel. *J Neurosci* 2011. doi:10.1523/jneurosci.1377-11.2011 | Non-commercial: CC BY-NC-SA (Europe PMC record) |
| P7 | cAMP molecules per second through one gap junction channel of Cx43, Cx46 and Cx50, with the concentrations used; S11 restates these numbers | Lens connexin channels have differential permeability to the second messenger cAMP. *Invest Ophthalmol Vis Sci* 2019. doi:10.1167/iovs.19-27302 | Non-commercial: CC BY-NC-ND (Europe PMC record) |
| P8 | Water permeability of *E. coli* cells with and without the water channel AqpZ | AqpZ-mediated water permeability in *Escherichia coli* measured by stopped-flow spectroscopy. *J Bacteriol* 2006;188:820–822. doi:10.1128/jb.188.2.820-822.2006; and Visualization of AqpZ-mediated water permeability in *Escherichia coli* by cryoelectron microscopy. *J Bacteriol* 1999;181:4193–4197. doi:10.1128/jb.181.14.4193-4197.1999 | No stated terms (Europe PMC records: no licence, not open access) |
| P9 | Simulated ATP costs, transport and growth of a whole JCVI-syn3A cell | Fundamental behaviors emerge from simulations of a living minimal cell. *Cell* 2022. doi:10.1016/j.cell.2021.12.025 | Non-commercial: CC BY-NC-ND (Europe PMC record) |
| P10 | Energy budget of *M. pneumoniae*: ATP for maintenance and growth, and its measured glucose uptake per gram of dry mass, which S17 restates | Dissecting the energy metabolism in *Mycoplasma pneumoniae* through genome-scale metabolic modeling. *Mol Syst Biol* 2013. doi:10.1038/msb.2013.6 | Non-commercial: CC BY-NC-SA (Europe PMC record) |
| P11 | The NMR method behind the red cell water exchange time (U17) | Conlon and Outhred, 1972, as cited in S5 (its reference B56) | Not checked |
| P12 | The demand of the retinal pigment epithelium's sodium pump (behind U18) | Fluid and solute transport across the retinal pigment epithelium: a theoretical model. *J R Soc Interface* 2020;17:20190735. doi:10.1098/rsif.2019.0735 | Not checked. If it is CC BY, U18 becomes first-hand |
| P13 | Dark current of retinal rods (behind U20) | Dark current and photocurrent in retinal rods. *Biophys J* 1970;10:380–412. doi:10.1016/S0006-3495(70)86308-1 | Not checked |
| P14 | Single-channel permeability of gap junctions to cAMP and IP₃, measured by FRET | Unitary permeability of gap junction channels to second messengers measured by FRET microscopy. *Nat Methods* 2007. doi:10.1038/nmeth1031 | Not checked |
| P15 | Copies per human red cell of 41 membrane transporters, which may include the pumps this note lacks | Quantitative analysis of human red blood cell proteome. *J Proteome Res* 2017. doi:10.1021/acs.jproteome.7b00025 | Not checked: the publisher's page refused automated reading (HTTP 403) |
| P16 | Turnover of the *E. coli* Na⁺/H⁺ antiporter NhaA (behind U35) | Taglicht et al., 1991, as cited in S9 | Not checked |
| P17 | Turnover of the plant plasma-membrane proton pump (behind U36) | Sze et al., 1999, as cited in S16 | Not checked |
| P18 | K⁺ and Na⁺ currents of *Arabidopsis* root protoplasts (behind U37) | Volkov and Amtmann, 2006, as cited in S16 | Not checked |
| P19 | The BioNumbers database; for example its entries 101675 (AQP1 copies per human red cell) and 110725 (ions per second through a typical channel) | bionumbers.hms.harvard.edu | No stated terms: its About page (https://bionumbers.hms.harvard.edu/aboutus.aspx, read 16 November 2026) asks for a citation and states no licence or terms of reuse. Each entry points to an original paper, which is what must be classed |
| P20 | The red cell water permeabilities measured by NMR, and the epilepsy study with its exchange time (behind U16, U17) | Earlier papers by the authors of S5, cited there | Not identified, not checked |
| P21 | Distribution of the calcium pump's activity among human red cells (behind U5) | Distribution of plasma membrane Ca²⁺ pump activity in normal human red blood cells. *Blood* 2003;102:4206–4213 | Not checked |
| P22 | Earlier estimates of a growing *E. coli* cell's ATP use (behind U31) | S13's reference 51 | Not identified, not checked |
| P23 | The general comparison of channels and transporters (behind U26) | Two textbooks cited by S9 (Levitan and Kaczmarek, 2001; Chakrapani and Auerbach, 2005) | Not checked |
| P24 | Junctional conductance of homotypic Cx43 and Cx45 HeLa pairs (behind the 27–32 nS of U27) | Earlier papers of the authors of S10 | Not identified, not checked |

## 4. Derivations

Constants: Avogadro's number 6.022 × 10²³ per mole; elementary charge 1.602 × 10⁻¹⁹ C;
water about 55.5 mol per litre (1000 g per litre divided by 18.0 g per mole). One hour is
3600 s. Each derived number is usable only if every input is; the inputs are named, so a
derived number inherits their first-hand or second-hand mark. All inherit the roughness of
the red-cell count and volume (U1, U2), which are given to one significant figure.

**One ATP per pump cycle is an assumption.** No source read for this note states how many
ATP the sodium–potassium pump spends per cycle (three Na⁺ out, two K⁺ in). D4 and D7 assume
one, and say so wherever they use it.

**D1. Red cells per litre of cells, and the volume of one cell (first-hand).** 2 · 10¹³ cells
(U1) in ~2 L (U2) gives about 1 × 10¹³ cells per litre of cells, so about 100 fL per cell.

**D2. Sodium and potassium through the pumps of one red cell (first-hand).** 2–3 mmol/(L
cells·h) (U3) × 6.022 × 10²³ ÷ 10¹³ cells per litre (D1) ÷ 3600 s = **about 33,000 to 50,000
ions per second per cell**. S1 gives one range for both ions; the pump moves 3 Na⁺ out for
2 K⁺ in, so the two cannot both be exactly at the same value. If the range is read as the
sodium flux, the pump turns over 11,000 to 17,000 cycles per second per cell and potassium
enters at 22,000 to 33,000 per second. At steady state the same numbers leak back through
passive paths (a "pump-leak" balance); S1 does not say which paths. The model value of S2
(U7) gives 3.2 mmol/(Loc·h) → **about 54,000 Na⁺ out per second, 36,000 K⁺ in, 18,000
cycles**, if one Loc is taken as one litre of cells (the user guide that defines Loc was not
read). The model value is a little above the review's range.

**D3. Calcium through the pump of one red cell (second-hand, through U4).** 20–50 µmol/(L
cells·h) → **about 330 to 840 Ca²⁺ per second per cell**. The pump's capacity is about a
thousand times more (U5). The model's default maximum (U8, 12 mmol/(Loc·h)) gives about 2 ×
10⁵ per second per cell; the review's "three orders of magnitude" would put it at about 3 ×
10⁵ to 8 × 10⁵. The two differ by up to four-fold; both are capacities, not the resting flux.

**D4. ATP used by one red cell, and the pump's share (first-hand inputs, one assumption).**
1.0–2.0 mmol/(L cells·h) (U6) → **about 17,000 to 33,000 ATP per second per cell**.
*Assuming one ATP per pump cycle*, the sodium pump's share is the cycle rate of D2 divided by
this: anything **from about a third to all** of the cell's ATP, depending on which ends of
the two ranges are paired. S3 states 40% (U10) with no citation. **The sources do not pin
this down; do not show a share.**

**D5. Water crossing the membrane of one red cell (second-hand, through U17).** Water in one
cell: 100 fL (D1) × 0.75 (U9) × 55.5 mol/L × 6.022 × 10²³ ≈ 2.5 × 10¹² molecules. Exchanged
in about 10 ms (U17), so **about 2.5 × 10¹⁴ water molecules per second each way**: a
unidirectional flux; the net flux at rest is zero. (S2 gives its starting cell 0.85 L of
cell water per Loc rather than the reference 0.75; with 0.85 the result is about 2.8 × 10¹⁴.) This rests on the diffusional exchange,
not on osmotic permeability: osmotic permeability (U11) describes net flow when the two
sides differ in what is dissolved, and it is about twelve times larger than the diffusional
one (U11 against U12). A second route checks the order of magnitude: one AQP1 monomer's
diffusional permeability (U13, 1.67 × 10⁻¹⁴ cm³/s) × water's 3.34 × 10²² molecules per cm³ =
**about 5.6 × 10⁸ water molecules per second through one AQP1 channel**, each way, at 15 °C;
times 1.5 to 2 × 10⁵ copies (U13, U14) = 0.8 to 1.1 × 10¹⁴ per second per cell at 15 °C. The
diffusional permeability rises about 1.75-fold from 25 to 37 °C (U16), so the two routes
agree in order of magnitude; the second counts only water through AQP1. The temperature of
U17 is not stated. The second route is partly second-hand too (U13, U14).

**D6. Ions between two coupled cells (first-hand for 8.4–8.6 nS; second-hand for 27–32
nS).** A junctional conductance passes a net current only when the two cells' voltages
differ. At an assumed difference of 1 mV: 8.4 to 32 × 10⁻⁹ S × 10⁻³ V ÷ 1.602 × 10⁻¹⁹ C =
**about 0.5 to 2.0 × 10⁸ charges per second**, net; at 10 mV, ten times that. The voltage
difference is an assumption of this note, not a sourced number; with no difference, ions
still cross both ways but no net charge does.

**D7. Sodium and potassium through the pumps of one retinal pigment epithelium cell
(second-hand, through U18; one assumption).** 1.07 × 10⁸ ATP/s, *assuming one ATP per
cycle* → **about 3.2 × 10⁸ Na⁺ out and 2.1 × 10⁸ K⁺ in per second**.

**D8. Maximum pump rate of one U87-MG cell (first-hand).** 0.9 pA/pF × 36 pF = 32 pA; one net
charge per cycle → **about 2.0 × 10⁸ cycles per second at most** (S7 itself gives 3.35 ×
10⁻⁴ pmol/s, the same). This is a capacity, measured with the pump saturated, not the
resting rate.

**D9. Leak currents of one U87-MG cell (first-hand, one assumption).** Each leak conductance
of U24 × 35.3 pF (U23) gives, per cell: Na⁺ about 0.18 nS, K⁺ about 0.15 nS, Cl⁻ about 0.16
nS. A conductance passes ions only in proportion to the ion's driving force (the membrane
voltage minus that ion's equilibrium voltage), which needs the concentrations on both sides;
those were not read. Per 10 mV of driving force, *as an assumption*, each passes **about 1 ×
10⁷ ions per second** (0.18 nS × 10 mV = 1.8 pA → 1.1 × 10⁷ Na⁺ per second). The real
driving forces differ between the ions and were not read, so this is not yet a flux; it
says only how many ions each 10 mV would move.

**D10. Maintenance cost of an *E. coli*-sized cell (first-hand).** C_M at V = 1.0 µm³ (U32)
= 0.39 × 10⁹ ATP per hour ≈ **1.1 × 10⁵ ATP per second**, the cost of staying alive without
growing. The measured stationary-phase rate (U30) is about twice that.

**D11. Share of JCVI-syn3A's maintenance ATP spent pumping protons (partly second-hand).**
0.57 ÷ 3.30 (U38) ≈ **17%**, per gram of dry mass; no per-cell number.

## 5. What was not found, per species

Searches were made in Europe PMC, limited to papers licensed CC BY or CC0, and on the open
web, by topic and title words only. What was searched is named for each species, so that
"not found" means "not found by these searches".

- **Human (generic cell).** Searched: red cell osmotic water permeability; sodium pump
  turnover with per-cell counts; calcium or sodium pump copies per red cell; ions per second
  through potassium channels; gap junction unitary permeability and molecules per second;
  junctional conductance of cell pairs; the sodium pump's share of cellular ATP in energy
  budgets; IL-2 secretion rate. Not found in a permissive source: the number of
  sodium–potassium pumps or calcium pumps on a red cell (P1, P15 hold them); a calcium pump's
  own turnover (cycles per second per pump); a chloride flux of any human cell (only the
  U87-MG leak conductance, U24); a measured share of a nucleated cell's ATP spent on the
  sodium pump; a source stating ATP per pump cycle (not searched directly; two CC BY papers
  read for it state the 3:2 ratio but not the ATP). Two pump turnover values were found and
  they differ: 45 per second used in S6 (U19) and about 100 per second assumed in S7 (U22).
- ***E. coli* K-12.** Searched: whole-cell osmotic water permeability by stopped flow; ATP
  per second per cell; per-cell release of signalling molecules (AI-2, autoinducers, indole,
  acyl-homoserine lactones); potassium uptake and efflux per cell. Found only fuel (U30 to
  U34) and one antiporter's turnover (U35). Not found: water permeability of whole cells in a
  permissive source (P8); potassium fluxes per cell (the search returned nothing relevant);
  sodium fluxes per cell (not searched apart from U35); a per-cell release rate of a
  signalling molecule. For indole, S18 gives the concentration in the medium (0.7–0.8 mM at
  most, stationary phase, strain BW25113, LB medium, 37 °C), a cell-associated concentration
  of about 58 to 60 mM at the peak and a pulse of about 20 minutes, but no rate per cell and
  no cell density to derive one.
- **Fruit fly.** Searched: morphogen production rates (Dpp, Wingless, Bicoid, Hedgehog) in
  the wing disc; junctional conductance, the sodium pump, fluid secretion rates and water
  permeability with per-cell or per-tubule units. Nothing per cell. One CC BY paper (Song and
  Hyeon, *eLife* 2021, doi:10.7554/eLife.70034) restates the number of Bicoid molecules made
  in an embryo's first two hours; Bicoid is made in the embryo, not released by a cell, so it
  does not fit the secretion lane.
- **Thale cress.** Searched: plasma-membrane proton pump turnover and copies; osmotic water
  permeability of protoplasts. Found only U36 (a plant proton pump's rate, no species named)
  and U37 (currents per area under forced patch-clamp conditions), both second-hand. The
  water search found studies of pollen and of cauliflower membrane vesicles, none of an
  *Arabidopsis* cell. Not found: pumps per cell, resting fluxes, water permeability of a cell,
  ATP use.
- **Planarian *Schmidtea mediterranea*.** Searched: ion flux, proton pumps, H⁺,K⁺-ATPase,
  gap junctions and innexins, water permeability, ATP use. No per-cell number.
- **JCVI-syn3A.** Looked up the minimal cell's metabolic model (S17, read) and its whole-cell
  simulation (P9, non-commercial). Energy and potassium numbers per gram of dry mass only (U38
  to U40). No dry mass per cell was found in a permissive source, so no per-cell number.
- ***Mycoplasma pneumoniae*.** Searched: ATP, ion transport, potassium, protons and
  secretion with per-cell numbers; looked up its energy model (P10, non-commercial). Only an
  ATP synthase rate per complex (U33). Its glucose uptake per gram exists only restated from
  P10, so it is not kept.

## 6. A proposed shape for an entry (for the coordinator to decide)

One entry feeds one bead lane of `data/layers/flux.json`, under
`illustration.forms["typical values"].entries`. A sketch for the sodium lane of the
sodium–potassium pump, on a human red blood cell, built only on first-hand rows:

```json
{
  "kind": "pumps", "group": "sodium-potassium", "lane": "sodium",
  "cell": "human red blood cell (mature, middle-aged; no nucleus, no mitochondria)",
  "quantity": "sodium ions moved out of one cell by its pumps",
  "value": { "low": 33000, "high": 50000, "unit": "ions per second per cell" },
  "derived": "2–3 mmol/(L cells·h) × Avogadro ÷ (2·10¹³ cells ÷ ~2 L) ÷ 3600 s",
  "hand": "first-hand",
  "sources": [{
    "cite": "Lew VL, Tiffert T (2017) Front Physiol 8:977. doi:10.3389/fphys.2017.00977",
    "where": "Abstract; section \"Key features of volume control in human RBCs\"",
    "licence": "CC BY. \"This is an open-access article distributed under the terms of the Creative Commons Attribution License (CC BY).\"",
    "class": "permissive", "read": "2026-11-16"
  }],
  "bead": "1 bead = 10,000 ions",
  "says": "Typical value for a human red blood cell: about 33,000 to 50,000 sodium ions a second leave through its pumps, and as many leak back in. From a cited review, not a run."
}
```

Points for the decision:

- A licence string should begin "CC BY" or "CC0": the register in
  `tests/licence_classes.test.mjs` classes a licence by its first words, and a line that
  begins "This is an open-access article…" would not be recognised.
- The potassium lane would read the same source (D2) and say that the pump moves two
  potassium in for every three sodium out. The calcium lane would read D3 (about 330 to 840
  a second) only if the coordinator accepts second-hand rows. The channel lanes could read
  D2's leak, but only with the words "by all passive paths together", since S1 does not say
  the leak goes through channels. Water would read D5, again only with second-hand rows.
  Fuel stays undrawn, as now; its number (D4) could stand in words.
- The cell must be named in every sentence. The project's human cell is a generic cell, and
  a red cell lacks parts the picture draws. The coordinator may prefer to offer `typical
  values` only where the picture is labelled as a red cell, or to use the retinal pigment
  epithelium cell (D7) for the pump lanes of a nucleated cell, with its own words and its
  assumption.
- One scale for all lanes of a picture keeps the pump lanes honest against each other. At
  1 bead = 10,000 ions, sodium shows 3 to 5 beads a second and calcium none (0.03 to 0.08), so
  calcium would need its own scale, stated on the picture.
