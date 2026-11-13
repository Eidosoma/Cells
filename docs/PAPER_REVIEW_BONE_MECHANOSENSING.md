**Bone mechanosensing, PIEZO1 and a secreted anti-ageing factor: relevance to
Cells — reviewed 13 November 2026**

Zhimin Zhang, Zhiqing Cai, Shencai Liu, Yun Chu, Zhengtao Jiang, Wuju Zhang,
Yating Pan, Ying Lin, Xiaocui Wei, Jingting Chen, Junnan Huangfu, Bocheng Nan,
Yibo Zhou, Le Hu, Wenquan Liang, Zhipeng Zou, Minjun Huang, Sheng Lu, Di Lu and
Xiaochun Bai, *Dynamic force sensing by bone delays aging and extends lifespan*,
*Cell Metabolism*, [10.1016/j.cmet.2026.09.020](https://doi.org/10.1016/j.cmet.2026.09.020),
PII S1550-4131(26)00433-X, PMID 42914985. Received 18 March, revised 3 August,
accepted 28 September, published online 23 October 2026; **ahead of print**, so no
volume, issue or page numbers are assigned yet. Southern Medical University
(Guangzhou), with Kunming Medical University and the First People's Hospital of
Yunnan; corresponding authors Sheng Lu, Di Lu and Xiaochun Bai. No competing
interests declared. The journal is *Cell Metabolism*, as the ISSN 1550-4131
indicated: **verified** through Crossref and PubMed.

**Licence: Crossref records CC BY 4.0 for the version of record** (from 30
September 2026), alongside Elsevier's text-and-data-mining licences, and the
copyright line reads "© 2026 The Author(s)". Despite that, **the full text could
not be obtained**: `sciencedirect.com` returned HTTP 403 to a single attempt, the
article is not in PMC or Europe PMC (`isOpenAccess: N`, `inEPMC: N`, no PMCID),
and no preprint version exists in Europe PMC. **This review is written from the
abstract and the bibliographic record only** (§5). It should be re-read against
the full text before anything is built on it.

**Verdict first.** This paper is **not a validation target for Cells at any gate
now on the plan**, and the abstract supplies no quantity the engine could be
calibrated against. Its value is that it names, in one mechanism, the two engine
features Cells most plainly lacks on the mechanical side: **a channel gated by
mechanical state**, and **a secreted factor whose production depends on a cell's
state rather than on a schedule**. The first is genuinely absent — a grep of
`src/cells` and `docs` for mechanosensitive, stretch-activated, PIEZO or membrane
tension returns **nothing**, so Cells today has mechanics (MG1) and channels, with
no law connecting them. The second is the natural version 2 of the
secreted-species transport that [D150](DECISIONS.md#d150-secreted-species-transport-is-promoted-now)
has just promoted, whose version 1 has prescribed secretion and uptake as a plain
sink. Both are general and reusable (D136, D144); neither may be built for this
paper, and neither can be calibrated from it. Per
[D151](DECISIONS.md#d151-every-reviewed-candidate-is-deferred-not-closed) every
candidate in §4 is **deferred with its prerequisite and gate**, not closed. No
simulator change, parameter fit, run or scientific acceptance follows from this
review.

## 1. What was readable, and what the abstract claims

| Access obtained | Access refused or absent |
| --- | --- |
| Title; all 20 authors with affiliations; journal, DOI, PII, PMID; submission, revision, acceptance and e-publication dates; the **abstract**; author keywords; the competing-interests and copyright lines; the Crossref licence record | **The full text.** No introduction, results, STAR Methods, figures, figure legends, group sizes, statistics, assay descriptions, loading parameters, mouse strains or supplementary material. **The data and code availability statement was not read**, so whether the study deposits data is unknown. PubMed lists no grants and no MeSH terms for the record yet |

Because only the abstract was read, the table below separates what the abstract
**states as a result** from what it leaves undefined. Nothing here is verified
against methods, and no effect size other than the lifespan figure is available.

| Stated as a result in the abstract | Not determinable without the full text |
| --- | --- |
| Deleting the mechanosensitive channel **Piezo1 in osteocytes** accelerated whole-body ageing in mice | The deletion strategy, driver line, controls, age at analysis, which ageing measures moved and by how much, and whether bone phenotypes confound the systemic ones |
| **Dynamic tibial axial loading** of mice aged 20–24 months extended healthspan and lifespan, by **9.4% (79.5 days)** — the one quantity in the abstract | The loading waveform, magnitude, frequency, duration and schedule; which lifespan statistic the 9.4% refers to and its confidence interval; cohort sizes; survival-analysis method; whether healthspan was pre-defined |
| Loading **reversed bone marrow immunosenescence** | Which populations, by which assay, and whether the reversal is cell-intrinsic or compositional |
| Loading raised anti-ageing and protective factors and lowered pro-ageing and pro-inflammatory ones | Which factors, measured where (bone, marrow, serum), and by what method |
| **PEDF** (pigment epithelium-derived factor, gene *SERPINF1*) is identified as a **mechano-responsive anti-ageing factor**, and is **associated with healthy ageing in humans** | Whether PEDF was shown to be necessary, sufficient, or both, in mice; the route of administration or genetic test; the human cohort, its size, design and covariates. **"Associated" is the abstract's own word, so the human result is correlational** |
| The authors frame the work as a route for people who cannot exercise or have reduced mobility, and the keyword list includes "exercise mimetics" | Whether any intervention was tested pharmacologically |

**Limits visible from the abstract alone.** It is a mouse study with a human
association; the intervention is applied to one bone by external loading, so
generalisation to voluntary exercise is the authors' inference; the phenotypes
develop over months of mouse life; and a single named secreted factor emerging
from a screen is a candidate mediator until necessity and sufficiency are both
shown. A 9.4% lifespan extension is a modest effect for which the statistical
treatment matters, and that treatment was not read.

## 2. Relevance to Cells, layer by layer

Placed against the gates in the [current plan](CURRENT_PLAN.md).

| Cells layer | Bearing | Why |
| --- | --- | --- |
| **The bioelectric layer** (`resolved_pump_tissue@3`, channels, pumps, gap junctions and the formation law) | **A named gap, not a parameter** | PIEZO1 is a mechanically gated cation channel, and Cells has **no mechanically gated channel of any kind**: the grep above finds no mechanosensitive, stretch-activated, PIEZO or membrane-tension term anywhere in `src/cells` or `docs`. Every existing channel law gates on voltage, calcium or a scheduled availability. So the paper's central mechanism has no representation, and the abstract supplies no conductance, no pressure–activation curve and no kinetics with which to build one |
| **Mechanics (MG1 vertex model)** | **The coupling direction the ladder is missing** | MG1 is a 2-D apical vertex model with area elasticity and line tension, passive and landed. The [morphogenesis ladder's](MORPHOGENESIS_PLAN.md) MG4 rung is bioelectric-and-chemical prepatterns guiding shape — that is **voltage → mechanics**. This paper is the reverse: **mechanics → membrane conductance → cell state**. Adding that direction would need a declared mechanical observable per membrane patch (MG1's energy gives junction tensions and areas, not a patch membrane tension), which is the real design question and is not answered by this paper |
| **Secreted species (D150)** | **Genuine: it motivates version 2** | The [design](SECRETED_SPECIES_TRANSPORT_DESIGN.md) puts a secreted species on @3's species axis with valence 0 and its own diffusivity, carried by the existing face law, with `scheduled_species_turnover@1` and `scheduled_species_exchange@1` as writers, and **uptake as a plain sink** in version 1. A mechano-responsive factor such as PEDF is exactly the case that version 1 cannot express, in two ways: secretion is **scheduled**, not a function of the cell's state, and uptake changes no behaviour in the receiving cell. Both extensions are general; neither is PEDF-specific |
| **Metabolism and the energy pools** | **Little, despite the journal** | The abstract reports no metabolic flux, no ATP measurement and no energetic quantity. Cells' energy models (`surface_calcium_energy_*`, `surface_energy*`) are owned fuel pools coupled to pump work at the single-cell scale, and `network_reactions@1` is a local reaction and growth/decay law with explicit route ownership; neither is an organismal metabolism model, and nothing in the abstract constrains them. D151 records the energy pools as deferred in any case |
| **Cell replacement and turnover (E07-v1)** | **Conceptual only** | "Reversal of bone marrow immunosenescence" is renewal of a cell population in a niche, which is adjacent to the replacement operator's subject, but the cell types, the niche and the months-long timescale are all outside what Cells represents. E07-v1's registered protocol is untouched by this review (D151) |
| **The composite model and its operators** | **No new operator from the paper itself** | A state-dependent source term and a responder coupling would both be writers under the existing `ENTITY_WRITES` contract, with fluxes adding and availability factors multiplying. The entity table needs no change |
| **Division (S2–S5) and water and volume** | **None** | No division, volume, osmotic or water measurement in the abstract. Mechanical loading of a tissue would eventually interact with volume regulation, but nothing here constrains it |
| **The planned gene-regulation layer** | **None from the abstract** | A mechano-responsive factor implies transcriptional control, but no regulatory measurement or network is reported in what was readable |
| **The protein catalogue** | **Two candidate identities, nothing more** | If a mechanically gated channel law is ever written, PIEZO1 would be its functional unit and would need a catalogue entry with assembly stoichiometry and evidence, as the [catalogue plan](PROTEIN_CATALOGUE_PLAN.md) requires of the 49 existing units; PEDF (*SERPINF1*) would be a secreted-species identity under D150's catalogue-identity requirement. Both are metadata, and catalogue stage 3 is held under D145 |

## 3. The preprints, carefully

*Plastic Heredity* is [10.5281/zenodo.22143269](https://doi.org/10.5281/zenodo.22143269)
and *How Patterns Return* is [10.5281/zenodo.23327869](https://doi.org/10.5281/zenodo.23327869).

The bearing is thematic and weak, and rests on an abstract. For *How Patterns
Return*, the shape of the claim is that **a mechanical history changes what a
tissue can later do** — loading applied late in life alters a systemic trajectory
— which is the kind of retained-state-and-experience question the preprint asks.
For *Plastic Heredity*, the relevant feature is that the proposed carrier is
**extracellular and systemic**: a secreted factor would transmit a state between
cells that never shared a lineage, which is a different transmission route from
either of E07-v1's (an isolated newcomer, or a donor copy). That is worth noting
when E07-v2 is drafted. Neither point is evidence for anything in the preprints:
the paper tests no inheritance, follows no carrier replacement, and its human
result is an association.

## 4. What Cells could test, ranked — every row deferred (D151)

Each row is a **general** feature whose validation target is **not this paper**
(D136, D144). The paper can calibrate none of them: the abstract gives no
conductance, no activation curve, no gradient, no concentration and no rate.

| Rank | What Cells could test | General engine feature it needs | Prerequisite | Gate | Status |
| --- | --- | --- | --- | --- | --- |
| 1 | **A secreted factor whose production depends on the producing cell's state**: the source term is a declared function of cell state rather than a schedule; conservation holds across secretion, transport, clearance and uptake, and results are unchanged when the feature is off | State-dependent secretion in `scheduled_species_exchange@1` — version 2 of the D150 feature, with the state input declared explicitly, never mechanics-specific | D150 version 1 lands, which D150 places after S5a | Composition, then the extracellular entity | **Deferred to D150 v2.** Calibration from a measured secretion rate with a stated stimulus, per D150's own rule |
| 2 | **A responder side for secreted species**: local concentration of a secreted species modulates a declared law in the receiving cell through the existing availability-factor rule, with the material booked on uptake | A receptor-like coupling from a species concentration to a law's availability factor. This is what D150 v1 deliberately omits by making uptake a plain sink | D150 v1; the ownership rule that each derived observation has one owner | Composition; it also serves ROADMAP item 9 (morphogen sources) | **Deferred.** Calibration from a published dose–response with a stated concentration |
| 3 | **A channel gated by mechanical state**: a membrane permeability that depends on a declared mechanical observable, so that deforming a cell changes its ion fluxes, voltage and volume, with charge and material conserved and the law inert when the mechanics are flat | A mechanically gated conductance law, plus the missing piece underneath it — a **declared mechanical observable per membrane patch** derived from the vertex model's state | MG1's failed judged run diagnosed and MG1 landed on main; the composite landed | Integrated tissue unit; it would add the **mechanics → bioelectric** direction to MG4 of the morphogenesis ladder | **Deferred.** Calibration must come from the mechanosensitive-channel biophysics literature (a stated mechanical stimulus and single-channel or whole-cell conductance), sourced before design (D136, D142) — **not from this paper** |
| 4 | **Does a mechanically written cell state persist once the loading stops?** Condition cells by a mechanical history, remove it, restore a common environment, then challenge; report retention, relaxation and transmissibility separately | The slow writable cell state with a declared timescale and interventions on it, already a coupled-renewal deliverable ("causal carriers"), plus rank 3 to write the state mechanically | Ranks 1–3; E07-v2's write–clear–challenge rules (D151) | Coupled renewal | **Deferred.** The design comes from the assay, not from this paper |
| 5 | **A systemic factor transmitting a state between cells of no shared lineage**, as a transmission route alongside E07-v2's isolated newcomer and donor copy | Ranks 1 and 2 together, in a tissue with an extracellular field | Ranks 1–2; E07-v2 drafted | Coupled renewal | **Deferred**, and noted for the E07-v2 draft |
| 6 | **An organ- or organism-scale ageing phenotype over months**, of the kind this paper measures (healthspan, lifespan, marrow composition) | Organ representation Cells does not have, and a qualified long-time method | A qualified multirate or quasi-steady method (projective integration failed its qualification), and the organ models | Compute limits, then an organ model | **Deferred to Cells' planned long-time modes**, exactly as D150 defers organ-scale ageing timescales. Not attempted and not promised now |

## 5. What not to do

- **Do not build a bone, osteocyte, marrow or organismal-ageing model** for this
  paper (D136, D144). The engine gains general features — a state-dependent
  secretion source, a responder coupling, a mechanically gated conductance — or
  nothing.
- **Do not implement PEDF as a named engine species.** Under D150 a secreted
  species is general, with the identity carried as catalogue metadata; a
  PEDF-specific law would be a feature built for one paper.
- **Do not reproduce the paper's own analysis, model or figures**, and do not
  write a reference solution for it: that is tooling needing the user's approval
  per paper ([D138](DECISIONS.md#d138-mg1-start-and-the-paper-backlog), restated
  in D151), and a milestone that runs no Cells engine model needs explicit
  approval (AGENTS.md).
- **Do not treat the 9.4% lifespan figure, or any abstract claim, as a target or a
  tolerance.** The statistics behind it were not read.
- **Do not repeat the human PEDF result as causal.** The abstract says
  "associated".
- **Do not take this review as a reading of the paper.** It rests on the abstract;
  §1 lists what is missing, and the ranked candidates above are motivated by the
  mechanism named in the abstract, not by any number in the paper.
- **Do not retry ScienceDirect.** One attempt returned HTTP 403, consistent with
  the refusals recorded in the [granzyme K review](PAPER_REVIEW_GZMK_AGEING.md).
  If the full text is wanted, it should come through the user's own access, or by
  waiting for a PMC deposit.

## 6. Open questions for the user

1. **Is the full text wanted?** Everything in §4 would be firmer with the STAR
   Methods, the loading parameters and the PEDF experiments. The publisher refuses
   automated access although the version of record is CC BY, so this needs the
   user's own access or a later PMC deposit.
2. **Should the mechanics → bioelectric direction be added to MG4?** The ladder's
   MG4 is voltage → mechanics; a mechanically gated channel is the opposite
   direction and would need a declared per-patch mechanical observable from the
   vertex model. That is a design decision about MG1's interface, not a new rung.
3. **Should D150 version 2 include state-dependent secretion and a responder
   side?** Ranks 1 and 2 are the two things version 1 deliberately leaves out, and
   this paper is a motivation for both; the calibration source would still have to
   be a measured gradient or dose–response.
4. **Catalogue identities for PIEZO1 and *SERPINF1*** when stage 3 opens, given
   that stage 3 is held under D145?
5. **Does this paper get a backlog row at all**, given that the full text is
   unread and the abstract calibrates nothing?

## 7. Provenance

| Step | Source | Result |
| --- | --- | --- |
| 1 | Web search for the PII | Did not resolve the article; the journal was confirmed as *Cell Metabolism* from the ISSN only |
| 2 | Crossref `filter=alternative-id:S155041312600433X` | **Resolved the DOI** 10.1016/j.cmet.2026.09.020, with the title, container and the **CC BY 4.0** version-of-record licence from 2026-09-30 |
| 3 | Europe PMC REST search on the PII | Zero hits |
| 4 | Europe PMC REST search on the DOI, then on the title | One MED record: PMID 42914985, **no PMCID**, `isOpenAccess: N`, `inEPMC: N`, `inPMC: N`, `hasPDF: N`, `hasSuppl: N`; the only full-text link is the DOI, marked subscription-required. No preprint version |
| 5 | NCBI E-utilities `efetch` on PMID 42914985 | The **abstract**, all 20 authors with affiliations, dates, keywords, publication type, competing-interests and copyright lines. Read through the fetch tool, whose quotation cap means the abstract was reported as a paraphrase with the one numeric result |
| 6 | `sciencedirect.com/science/article/pii/S155041312600433X`, one attempt | **HTTP 403 Forbidden.** Not retried |

No file was downloaded, so the prepared downloads directory stayed empty and no
extraction script ran. No user, project or contact details were sent in any
request. The access log is under
[/mnt/workspaces/Cells/paper-review-20261113-03](/mnt/workspaces/Cells/paper-review-20261113-03).
These notes introduce no model changes, no runs and no scientific acceptance.
Current status stays in [PROGRESS.md](../PROGRESS.md).
