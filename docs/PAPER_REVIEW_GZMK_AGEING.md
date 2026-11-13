**Granzyme K and tissue ageing: relevance to Cells — reviewed 13 November 2026**

Five papers supplied by the user as a backlog cluster, with a secondary assessment
written by another assistant. The assessment's claims were treated as unverified and
checked against the papers; §2 reports the result.

**Verdict first.** This is a strong biological story about a secreted protease driving
organ ageing, and it is **not a validation target for Cells today or at any gate now
on the plan**. None of the five papers reports a bioelectric measurement (§2, last
row), none reports an enzyme kinetic constant, and the phenotypes develop over 22–24
months of mouse life. The cluster's real value is as **motivation for four general
engine features** the plan already wants for other reasons — secreted species on the
extracellular entity, extracellular catalysis, a persistent cell-state layer and an
ECM entity — and as a worked example of the prevent-versus-reverse experimental
design (§4, §5). Everything below is proposed work. No simulator change, parameter
fit, run or scientific acceptance follows from this review.

## 1. The papers, what was readable, and what they show

| Paper | Access obtained | Access refused |
| --- | --- | --- |
| **Kannangara et al. 2026**, *Granzyme K is a driver of age-related tissue remodeling and functional decline independently of age-associated immune dysfunction*, [*Immunity*](https://doi.org/10.1016/j.immuni.2026.10.013). PMID 43020081, first published 12 November 2026, 24 authors, last author N. L. La Gruta (Monash). Europe PMC and OpenAlex both record a CC BY licence, yet `isOpenAccess: N`, `inEPMC: N`, no PMCID | Title, author list, **abstract**; the OpenAlex record; the institutional press release ([EurekAlert 1151592](https://www.eurekalert.org/news-releases/1151592)) | **Full text.** `cell.com` and `sciencedirect.com` both returned HTTP 403. No methods, figures, group sizes, statistics or assay names |
| **Sucharov et al. 2026**, *Aged circulating CD8+ T cells and their secreted factors drive cognitive decline*, [*Immunity*](https://doi.org/10.1016/j.immuni.2026.04.014) 59(6):1651–1666.e8. PMID 42140192, 14 May 2026, CC BY | **Full text and methods**, via [PMC13274914](https://pmc.ncbi.nlm.nih.gov/articles/PMC13274914/) | The figures themselves. Figure legends were read only through the fetch tool's report |
| **Terekhova et al. 2026**, on GZMK+ versus GZMB+ memory CD8+ T-cell states and human ageing trajectories, [*Immunity*](https://doi.org/10.1016/j.immuni.2026.09.012). PMID 42854692, 9 October 2026, 27 authors | **Abstract** | Full text, cohort tables, all statistics |
| **Donado et al. 2025**, *Granzyme K activates the entire complement cascade*, [*Nature*](https://doi.org/10.1038/s41586-025-08713-9) 641(8061):211–221. PMID 39914456, 6 February 2025 | **Full text and methods**, via the [PMC12180478](https://pmc.ncbi.nlm.nih.gov/articles/PMC12180478/) author manuscript | The version of record; no licence statement in the author manuscript |
| **Joeckel et al. 2017** — *the paper the assessment cited without a reference; found*: *Granzyme K-deficient mice show no evidence of impaired antiviral immunity*, [Immunol Cell Biol](https://doi.org/10.1038/icb.2017.35) 95(8):676–683. PMID 28428612. Allele `Gzmk tm1.1Pib`, MGI:5636646. P. I. Bird is also an author on Kannangara et al. | **Abstract** | Full text |

No PDF was retrievable, so the prepared downloads directory stayed empty and no
extraction script was run.

**Kannangara et al. (mouse, lifelong deletion).** Young and aged `GzmK`-deficient mice
are compared with controls. From the abstract: GzmK is **not** required for the main
hallmarks of immune ageing, which persisted in the knockouts, while its absence
markedly reduced age-related tissue decline — the authors therefore describe immune
ageing and tissue ageing as uncoupled. Named in the abstract: reduced complement
deposition in the aged **kidney**; improved **liver** function and reduced liver
fibrosis, **independently of complement**, alongside higher decorin and lower
pro-fibrotic TGF-β signalling. The abstract gives no effect size, group size or
p-value. **Heart results are not in the abstract**: the press release reports
significantly better cardiac function and reduced cardiac fibrosis, and attributes
"markedly reduced" glomerular enlargement and complement deposition to a kidney
figure caption. Those two organ claims therefore rest on a secondary source here.
The press release also states that human datasets showed higher GZMK in inflammatory
and fibrotic disease including lupus nephritis and heart failure — an association —
and that because the mice lacked GzmK from birth, **blocking it later in life was not
tested**.

**Sucharov et al. (mouse, full text read).** Heterochronic parabiosis (young 4 mo,
aged 20 mo, 28 days, CITE-seq n=4/group), adoptive transfer of aged (22 mo) CD8+ T
cells into young recipients (cognition n=12/group), pertussis-toxin and GPCR blockade
arms (n=11–12/group), tofacitinib and anti-VLA-4 (n=9/group), `Tap1`−/− mice
(n=11/group), CD8a depletion in aged mice (n=12–16/group). GZMK was identified from
the single-cell data as an age-associated effector-memory CD8+ transcript and
confirmed as a raised plasma protein by ELISA. Two gain-of-function routes: retroviral
GZMK overexpression in young CD8+ T cells (n=11/group) and systemic hydrodynamic
tail-vein injection of a GZMK plasmid in young mice (50 µg in 3 mL saline over 5–7 s;
n=14–15/group). Both impaired radial arm water maze (RAWM) performance. A HiBiT tag
put the signal in plasma and liver but **not** hippocampus or cortex, which the
authors read as circulating GZMK not readily crossing the blood–brain barrier; the
proposed mechanism runs through GZMK substrates enriched in brain-barrier cells and
reduced PAR1 coverage. A CCL5 control did not impair cognition. Behaviour: RAWM by
two-way ANOVA with Šídák post-hoc, novel object recognition by one-sample t-test
against 50%, randomised and blinded, mean ± s.e.m.; **most figures are from a single
independent experiment**. Mostly male mice. The paper reports no original code; GEO
accessions GSE266468, GSE266454, GSE266467.

**Terekhova et al. (human, abstract only).** Seven large public single-cell PBMC
datasets integrated with one newly generated cohort, **2,609 ostensibly healthy
individuals in total across all of them** — the new cohort's own size is not in the
abstract. 59 immune populations; CD8+ T cells the main source of variation. The
GZMK+/GZMB+ effector-memory ratio distinguishes healthy from pathology-associated
ageing trajectories, and is said to reflect remodelling driven by chronic viral
exposure including CMV and by disease-related immune dysregulation, with the dominant
driver differing between populations. A plasma proteomic signature of GZMB+ Tem cells
across four cohorts was associated with inflammaging, poor self-reported health,
all-cause mortality and raised immune, metabolic and cardiovascular disease risk. The
abstract carries no p-value, effect size or confidence interval, and its design is
cross-sectional and associative; "drivers" and "driven by" are the only causal words.

**Donado et al. (biochemistry and mouse, full text read).** GZMK cleaves **C4** to C4b
unaided and **C2** to C2b when C4 is present; the fragments form a C3 convertase, so
C3a/C3b, then C5a and terminal complement complex (TCC) follow. GZMK does **not**
directly cleave C3 or C5, and did not activate the alternative pathway via factor B.
GZMA did neither cleavage. Systems: purified proteins, cytokine-stimulated synovial
fibroblast supernatants, C1q-depleted human serum, HUVEC and THP-1 surfaces. GZMK
bound nearly all cells tested, dependent on heparan sulfate and blocked by soluble
heparin, and **membrane-bound GZMK cleaved C4 and C2 more effectively than
fluid-phase GZMK** — described qualitatively as greater catalytic efficiency, with
**no kcat, Km or catalytic efficiency reported anywhere in the paper**. Concentrations
and times are stated instead: 125–1000 nM for 4 h (purified cleavage), 12.5–100 nM
and 25–100 nM for 4 h (opsonisation, TCC with purified components), 50–400 nM for 2 h
in serum, 200 nM for 2 h (membrane versus fluid phase), 100–400 nM for 3 h (C5a).
Mice: `Gzmk`−/− with littermate controls, 10–14 weeks, both sexes; reduced
antigen-induced arthritis and imiquimod dermatitis with reduced C3d/C4d deposition.

**Joeckel et al. (mouse, abstract only).** The `Gzmk` knockout mice were healthy,
anatomically normal, fertile, with normal haematopoietic development, and recovered
readily from lymphocytic choriomeningitis virus and from ectromelia virus (mousepox).
Virus-specific CTLs lacking GzmK induced target-cell apoptosis at wild-type levels.
The authors conclude GzmK is not essential for antiviral immunity or CTL
cytotoxicity.

## 2. The assessment checked, claim by claim

| The assessment's claim | Verdict | Evidence and correction |
| --- | --- | --- |
| Lifelong GZMK loss protected the **liver**: function, fibrosis, more decorin, less TGF-β signalling, independent of complement | **Right** | All five elements are in the Kannangara abstract, including the complement independence. No numbers are given there |
| …protected the **kidneys**: less glomerular enlargement and complement deposition | **Partly verified** | Reduced kidney complement deposition is in the abstract. **Glomerular enlargement is not**; it comes from a figure caption quoted in the press release. Direction right, source secondary |
| …protected the **heart**: function and fibrosis | **Partly verified** | **Not in the abstract.** Better cardiac function and reduced cardiac fibrosis are stated in the institutional press release, and OpenAlex tags the work "Cardiac dysfunction". Plausible and consistent, but I could read no paper text supporting it, and no assay, n or statistic |
| …**while immune ageing persisted** | **Right** | The abstract's central claim: GzmK is not required for the hallmarks of immune ageing, which persisted; the authors call immune and tissue ageing uncoupled |
| A GZMK inhibitor, **D-Pro-Phe-Arg-chloromethylketone**, **four doses**, improved **spatial memory** in **22–24-month** mice | **Right on the facts, overstated as a GZMK result** | Methods confirm every detail: aged 22–24 months, male; 62.5 µg intraperitoneally in 100 µL, every 4 days, 4 injections total, then behaviour; fewer RAWM errors than controls (n=9–10/group). RAWM is hippocampal-dependent spatial memory. **Three cautions.** (a) The paper's own limitation is that this is a pharmacological tool "lacking cell specificity", previously used in airway models. (b) The catalogue entry the methods cite, MedChemExpress **HY-P4245** (CAS 88546-74-1), is described by the vendor's distributor listing as a covalent serine-protease inhibitor whose **named target is KLK1**; granzyme K is not named and no GZMK potency is given. Peptidyl chloromethylketones are active-site-directed irreversible serine-protease inhibitors, so GZMK inhibition is chemically plausible, but it is not established by the cited catalogue entry, and the near-identical PPACK (D-**Phe**-Pro-Arg-chloromethylketone, CAS 71142-71-7, same formula, reversed D-residue order) is the entry a search reported as listing GZMK — I could not read that vendor page. (c) The fetch tool reports that the figure 6S legend calls the agent an "anti-GZMK antibody", conflicting with the methods. Treat the behavioural rescue as measured and its attribution to GZMK specifically as unestablished — note that the proposed brain mechanism runs through PAR1, a thrombin receptor, and this compound class hits coagulation proteases |
| Raising circulating GZMK in young mice impaired cognition | **Right** | Two independent routes, retroviral in CD8+ T cells (n=11/group) and systemic plasmid (n=14–15/group), both impairing RAWM, with a CCL5 negative control. Caveats the paper states: mostly single experiments, male mice, and GZMK did not reach brain parenchyma, so the effect is inferred to act at the barrier |
| The human data are associative, and the GZMK/GZMB balance relates to health trajectories in complex ways | **Right** | Cross-sectional integration of seven public datasets plus one new cohort; the ratio reflects CMV exposure and disease-related dysregulation, with the dominant driver differing between populations. **One correction:** 2,609 is the **combined total across all eight data sources**, not the size of a single cohort; the new cohort's own size is not in the abstract |
| The 2017 study: GZMK-deficient mice developed normally and recovered from two viral infections | **Right, and the citation is now supplied** | Joeckel et al. 2017, [10.1038/icb.2017.35](https://doi.org/10.1038/icb.2017.35). The abstract's wording is healthy, anatomically normal, fertile, normal haematopoietic development — not the phrase "developed normally" — and the two viruses are LCMV and ectromelia |
| **"There is no direct bioelectric result in these papers"** | **Right everywhere I could check; one genuine hole** | **Sucharov (full text): confirmed.** No electrophysiology, patch clamp, field potential, LTP or calcium imaging anywhere in the methods. The nearest readouts are cFos immunostaining, synaptic and NMDA-subunit westerns (NR2A, NR2B, PSD95, Homer1, Synapsin1) and a ZO1 western — protein levels, not currents. **Donado (full text): confirmed, and pointedly so.** The paper's own endpoint is the terminal complement complex, a membrane pore, yet TCC was measured only by flow cytometry with an anti-TCC antibody: **no lysis, pore count, conductance or membrane-potential measurement**. Its single calcium measurement is a Fluo-5F dye flux in C5aR1-expressing reporter cells, used to show C5a bioactivity — an ion-concentration readout in a reporter line, not a bioelectric result. **Terekhova and Joeckel: consistent at abstract level** (a PBMC single-cell/proteomic survey and a viral-immunity phenotyping study). **Kannangara: unverifiable.** Cardiac function was assessed by an unnamed method, and cardiac phenotyping commonly includes electrocardiography, which would be a bioelectric measurement. Resolving this needs the full text |

## 3. Where such a module would sit against the plan

Cells today is a bioelectric, ionic and volume tissue engine with replacement and
turnover, division operators, the [composite operator model](CURRENT_PLAN.md), a
planned gene-regulation layer ([GRN track](GRN_WETLAB_VALIDATION.md)) and a
[protein catalogue](PROTEIN_CATALOGUE_PLAN.md). An
"immune-cell secreted protease → extracellular transport → organ-dependent signalling
→ persistent tissue-state change" module needs the following. The honest summary is
that **items 1–2 are plausible next-decade-of-this-plan features, items 3–7 are not
on any current gate, and item 8 has no qualified route at all.**

| What it needs | What exists today | What is missing |
| --- | --- | --- |
| 1. **A secreted non-ionic species in the extracellular inventory** | Extracellular material is already an owned entity with conserved inventories: [`finite_extracellular`](../src/cells/models/finite_extracellular.py), [`spatial_extracellular`](../src/cells/models/spatial_extracellular.py) and the conservative [face law](../src/cells/processes/extracellular_face_transport.py). All valence domains including neutral species are expressible. The [plan's entity table](CURRENT_PLAN.md) already names secretion, uptake and diffusion as contributions to that entity, and roadmap item 9 (Golgi and trafficking) already intends to supply secretion | A protein-scale species with its own diffusivity, a secretion flux from a cell with a ledger, an uptake or clearance sink that books what it removed, and a catalogue identity. Today a secreted protein has no producer and no account |
| 2. **Enzyme kinetics on an extracellular substrate** | More than the brief assumed. [`network_reactions@1`](../src/cells/processes/network_reactions.py) carries cell, mitochondrial, **environment** and growth reaction branches with Km terms and activation/inhibition influencers (equations cited from BETSE v1.5.0, no BETSE code), wired into `surface_calcium_energy_regulated@1/@2` as availability factors on existing pumps, channels and junctions. [`compartment_reactions`](../src/cells/models/compartment_reactions.py) and [`mass_action`](../src/cells/processes/mass_action.py) give closed chemistry with detailed balance and per-reaction dissipated energy | A **catalytic** law: an enzyme that converts substrate to product without being consumed, with a conserved protein material account, and with its substrate and product having distinct identities. Also unsettled: the reaction network holds **its own species state** feeding availability ports, so whether reaction species share the physical inventory is a shared-state question for the ownership contract, not a solved one |
| 3. **Surface-bound catalysis** | Membrane domains already hold populations with abundance as state ([`membrane_state`](../src/cells/models/operators/membrane_state.py)); the redistribution pumps and junction formation already treat abundance as state | Binding-site occupancy on a membrane domain modulating a surface reaction rate. This is Donado's cleanest mechanistic finding (heparan-sulfate binding, membrane-phase rate enhancement) and it is a **general** feature |
| 4. **A proteolytic cascade with amplification** | Nothing comparable. The existing reaction laws are local and mostly reversible | A multi-step, effectively irreversible chain whose output is amplified relative to its input, with conserved accounting and its own stiffness, refinement and restart checks |
| 5. **An ECM entity** | Nothing. [`finite_ecm_polygon_geometry`](../src/cells/processes/finite_ecm_polygon_geometry.py) is a cell/ECM **geometric** partition with bath-face distances, not a matrix with composition or mechanics. 2-D vertex mechanics exists ([`vertex_mechanics`](../src/cells/processes/vertex_mechanics.py)) and MG1 is still being diagnosed | A matrix entity owning material (collagen-like and decorin-like pools), a deposition and degradation account, and a declared coupling to mechanics. "Fibrosis" is an accumulated matrix state, which the engine cannot represent at all |
| 6. **A persistent cell-state layer** | [`emt_mirna`](../src/cells/models/emt_mirna.py) is the nearest: regulatory equations with no ions, voltage, contacts or physical conversion, deliberately isolated. The coupled-renewal gate already requires interventions on slow variables as "causal carriers" | A slow, writable per-cell state that changes transport, secretion or mechanics, with retention, reset and transfer distinguished — and with its own timescale declared |
| 7. **Distinct cell types, including a motile immune cell** | Cells have stable identity, membership and ancestry; replacement and removal operators exist ([`cell_replacement`](../src/cells/models/operators/cell_replacement.py), [`tissue_removal`](../src/cells/processes/tissue_removal.py)) | No cell-type differentiation of function, no migration, no infiltration, no systemic circulation compartment. Organ coupling is roadmap M8, the farthest milestone |
| 8. **The duration** | The decisive obstacle. At 1 ms, one simulated hour is 3.6 million steps ([plan](CURRENT_PLAN.md)); the engine's qualified step ceilings are 1e-3 to 1.25e-4 s | A 24-month mouse is about 6×10¹⁰ steps at 1 ms — four to five orders of magnitude beyond any trajectory run here, and E07 tier 1 alone is already estimated at 4,100–7,200 L4 GPU-hours. Coarse-time modes are opt-in and **projective failed its qualification**; the long-time-method verdict is still an open gate deliverable. There is no qualified route to organism-ageing durations today, and none should be invented for this cluster |

**Placement.** Items 1 and 3 are the only ones that could be built as narrow, general,
qualifiable features in the current plan's language, and both sit **behind** the
composite, the lifecycle operators, coupled renewal and the closed molecular-to-physiology
loop. Item 2's catalytic law would most naturally arrive with the gene-regulation layer
or the Golgi/trafficking item, not on its own. Nothing here should displace a current
gate.

## 4. What Cells could test, ranked

Each row is a **general** feature with a validation target that is **not** one of these
five papers, per D136 and D144: an experiment may reveal a missing mechanism, but the
engine gains a reusable model, never one built for a single paper. Crucially, **none of
these five papers can calibrate any of them** — Donado reports no kinetic constants,
Kannangara's full text is unread, Terekhova is associative, and the whole cluster
measures no electrical quantity.

| Rank | What Cells could test | Engine features it needs | Where its calibration must come from |
| --- | --- | --- | --- |
| 1 | **A secreted species' concentration field**: one cell secretes, the field spreads through the existing extracellular inventory, neighbours take it up or it decays; conservation holds across secretion, transport, uptake and decay, and the field is unchanged when the feature is off | Item 1 above: a non-ionic protein-scale species with diffusivity, a secretion flux with a ledger, a clearance sink that books removals, and a catalogue identity. Reuses the existing extracellular inventories and face law unchanged | A measured protein or morphogen gradient with a stated geometry and diffusivity. This also serves the roadmap's morphogen-source goal, which is why it is first |
| 2 | **Surface-phase versus solution-phase reaction rate**: the same reaction proceeds faster when its catalyst is bound to a membrane domain at a declared site occupancy; occupancy competes with a soluble blocker | Item 3: binding-site occupancy as membrane-domain state modulating a surface reaction rate. Composes through the existing availability-factor rule (factors multiply) | A published surface-versus-solution kinetics dataset. Donado's heparin-competition and membrane-phase results are the **motivation**, but supply no rate constants |
| 3 | **A membrane permeability lesion's bioelectric consequence**: a population of non-selective pores raises Na/K permeability, and the cell's voltage, ion inventories and volume respond; recovery follows a declared closure law | **Already expressible.** `resolved_repair@1` ([`membrane_injury`](../src/cells/processes/membrane_injury.py)) gives each patch a damage fraction driving extra Na/K permeability through the existing GHK transport, with water and volume available in the composite | **Not these papers.** This is the cluster's one genuine contact with today's physics — the terminal complement complex is a membrane pore — and Donado measured TCC only by antibody staining. Pore conductance and count would have to come from the complement-biophysics literature. The existing law is phenomenological, not a fitted lesion model |
| 4 | **Does a written cell state persist once its driver is removed?** Condition matched cells through a slow state variable, remove the driver, restore a common environment, then challenge. Report retention, relaxation and transmissibility as separate outcomes | Item 6: a slow writable cell state with a declared timescale and interventions on it. This is already a coupled-renewal gate deliverable ("causal carriers"), not a new track | The engine's own registered assay. This cluster supplies the **design**, not data (§5) |
| 5 | **An amplifying cascade's numerics**: a multi-step irreversible chain whose output far exceeds its input, checked for conservation, stiffness, step refinement and restart across the amplification | Item 4, with the usual refinement and split-run restart checks | An independent published cascade solution run out of process as a reference. **This is tooling and needs the user's approval per paper (D138)** |
| 6 | **Slow matrix accumulation changing tissue mechanics**: a matrix pool is deposited and degraded, and its amount changes a mechanical property, with the material booked on both sides | Item 5, plus mechanics coupling. MG1 must land first | A mechanical measurement with matrix composition. Far out |
| — | **Not a Cells target**: an organ-scale ageing phenotype — cardiac function or liver fibrosis over 22–24 months, in an organ Cells does not represent, over a duration with no qualified method (item 8). This should not be attempted or promised | — | — |

## 5. The preprints, carefully

Grepped: *Plastic Heredity* is [10.5281/zenodo.22143269](https://doi.org/10.5281/zenodo.22143269)
and *How Patterns Return* is [10.5281/zenodo.23327869](https://doi.org/10.5281/zenodo.23327869)
(README, and `docs/EXPERIMENTS.md` for the second).

The "preventing a pathological tissue state versus reversing an established one"
framing does touch both preprints, but **only as a design pattern, and the cluster
does not in fact contain the reversal arm**:

- Kannangara is **prevention only** — lifelong deletion, with the press release
  stating explicitly that blocking GzmK later in life was not tested.
- Sucharov's four-dose intervention in 22–24-month mice is the nearest thing to a late
  intervention, and it reports a **functional behavioural improvement**, not the
  reversal of an established tissue state — with the tool-specificity problem in §2.
- So the honest reading is that **no paper here demonstrates reversal of an
  established tissue state**, which is precisely the question both preprints care
  about.

What transfers is the experimental logic, and Cells already has it: remove the driver
late and see whether the state relaxes, which is the cue, release and turnover
structure of the coupled-renewal gate. The useful distinction the cluster sharpens is
between a tissue state **held up by a continuing extracellular driver** (relaxes when
the driver goes) and one that **persists after the driver is gone** (written). Only
the second is a *Plastic Heredity* claim, and only repeated re-establishment in fresh
material would be a *How Patterns Return* claim. None of these papers measures a
written state, a reconstruction or heredity, and none supplies a parameter for either
preprint. Nothing here should be cited as support for them.

## 6. What not to do

- **Do not reproduce any of these papers' models or code.** Sucharov et al. state
  plainly that they report no original code, so there is nothing to port; building an
  independent complement-cascade reference solution is tooling and needs the user's
  approval **per paper** (D138).
- **Do not put this physics in `validation/`.** Secreted species, catalysis and matrix
  belong in `src/cells` as Cells models, under neutral names; `validation/` holds
  drivers, analysis, independent reference solutions and runners (AGENTS.md).
- **Do not name a law after granzyme K, a granzyme, complement or a complement
  component.** Neutral names, and a generic law stays generic
  ([catalogue rule](PROTEIN_CATALOGUE_PLAN.md)); labelling a generic catalysis law
  with a protein is a new scientific claim.
- **Do not turn an association into a rate.** Terekhova's GZMK+/GZMB+ ratio is a
  cross-sectional human association; it is not a kinetic parameter, a secretion rate or
  a permeability — the same rule the [CCI-seq review](PAPER_REVIEW_CCI_SEQ.md) applies.
- **Do not treat the chloromethylketone result as GZMK-specific causality** (§2), and
  do not derive a "GZMK inhibition" parameter from a four-injection behavioural
  endpoint.
- **Do not build an "ageing mode", an organ-ageing preset or an immune-cell agent type
  to serve this cluster** (D144). Do not invent a coarse-time method to reach 24
  months; the projective mode already failed qualification.
- **Do not claim complement independence or decorin and TGF-β mechanisms from the
  abstract** as though the mechanism were read: the abstract asserts them, and the
  supporting figures were unreadable here.

## 7. Open questions for the user

1. **Is this cluster to model, or to read?** It supplies no bioelectric target and no
   kinetic constants. The nearest general features are already wanted for other
   reasons. Logging it as reading notes, with §4 rows folded into the existing
   engine-feature queue, is the lead's recommendation.
2. **Priority.** It would sit behind the composite, lifecycle operators, coupled renewal
   and the molecular loop. Confirm it stays logged, not started.
3. **Access.** Do you have institutional access to the Kannangara full text? It would
   settle the heart and glomerular claims, the cardiac assay (and so the one open
   bioelectric question), and the group sizes and statistics. Failing that, may we
   write to the authors?
4. **Feature promotion.** Should "a secreted species on the extracellular entity" be
   promoted in the engine-feature queue (D136)? Roadmap item 9 already intends
   secretion, so this would bring a planned feature forward rather than add one.
5. **Reference solution.** Is an independent complement-cascade reference solution in
   `validation/` worth the tooling approval (D138), or should the amplifying-cascade
   numerics test use a synthetic chain instead?
6. **Catalogue scope.** The protein catalogue covers channels, pumps, transporters and
   junction channels. Should it extend to secreted proteases and ECM proteins, which
   items 1, 2 and 5 would need for identity?

Review provenance: five papers, two read in full (Sucharov via PMC13274914, Donado via
PMC12180478), three at abstract level, one organ claim from an institutional press
release. Elsevier's DOI redirects served only "Redirecting" and both publisher sites
returned 403, so Europe PMC REST and PMC were used; Nature's own page redirected to its
identity provider. No PDF was obtainable, so the prepared downloads directory stayed
empty and no extraction ran. Access detail and the exact fetch record are in the
[run log](/mnt/workspaces/Cells/paper-review-gzmk-20261113-01/HANDOFF.md). Current
simulation and qualification status stays in [PROGRESS.md](../PROGRESS.md). This review
adds notes only: no simulator change, no parameter fit, no run and no scientific
acceptance.
