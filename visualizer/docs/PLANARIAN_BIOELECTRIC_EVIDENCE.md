# Planarian bioelectricity: what wet-lab data exists on the proteins

**Status: an audit by the visualizer session, 15 November 2026, for the user and the lead.**
The user asked: "so for the bio electric proteins for planerian we must have plenty of data
on those right? all those wet lab experimetns?" The coordinator answered from general
knowledge that the experiments are many and the data on the proteins themselves is thin,
said that this was not audited, and the user asked for the audit. It follows the pattern
of the lead's Syn3A audit (`docs/SYN3A_MINIMAL_CELL_TRACK.md`) and uses its evidence
categories.

It is an inventory of pointers and cited facts. No table, trace or figure is copied from
any source, no author was contacted, and nothing here says anything about the engine.

| | |
| --- | --- |
| The inventory | `data/evidence/planarian_bioelectric.json`, format `cells.visualizer.planarian_bioelectric_evidence@1` (described below) |
| The check | `node --test tests/planarian_evidence.test.mjs` |
| What was read | `/mnt/datasets/Cells/planarian/literature-planarian-bioelectric-audit/`: every search result, record and open full text, with a `MANIFEST.json` |
| The working files | `/mnt/workspaces/Cells/visualizer-planarian-bioelectric-audit-20261115-01/`: the access log (161 requests, each with its time), the scripts, the working tables |
| The target | *Schmidtea mediterranea*, the species of the viewer's planarian atlas and catalogue. Categories are given relative to it |

## Answer

**The experiments are plentiful. Data on the proteins themselves is thin, and for the
species of our atlas almost absent.**

- **Plentiful: what the animal does.** 32 of the 55 records are outcomes after a
  pump, a channel family or the gap junctions were knocked down or drugged: two-headed
  worms, small heads, lost behaviours.
- **Plentiful: where genes are expressed.** In situ maps of the innexins, of all 318
  solute carriers, of the TRPM and PKD channels, and two single-cell atlases whose data is
  public.
- **Thin: the behaviour of a channel, a pump or a junction, measured.** Six records hold
  any (`ip3-receptor`, `muscle-ca-current`, `muscle-ryanodine`, `brain-cell-currents`, `muscle-cell-currents`, `trpa1-patch-clamp`): one *S. mediterranea* channel, TRPA1, patch-clamped in insect cells;
  sodium, calcium and potassium currents voltage-clamped in cells of two other planarians,
  in papers of 1993, 1994 and 2003; a binding affinity of an IP3-receptor fragment; and
  caffeine's action on muscle fibres.
- **None found** for the innexins, for the proton-potassium, sodium-potassium and V-type
  pumps, or for any voltage-gated channel of *S. mediterranea*: no conductance, no gating,
  no coupling, no transport rate.
- **No membrane voltage in millivolts.** The voltage images are dye fluorescence, and
  their own protocol calls them qualitative. One thesis reports a voltage gradient along
  the body from measurements of tissue potential; its record gives no numbers.

**How sure.** The picture of which kinds of data exist is firm for what the searches
reached: 161 requests, 64 papers behind 55 records. "None found" is a
statement about those searches, not proof of absence. 25 records rest on an abstract
alone, and no paper was read from end to end. The ligand-gated channels were searched
only in passing.

## The species question

Most of the best-known experiments are not on the species of our atlas.

- ***Dugesia japonica*** (mostly its GI clonal strain): the pump block with voltage
  imaging, octanol and the two-headed worms, the innexin family and its triple knockdown,
  praziquantel and the calcium channels, the barium adaptation, the IP3 receptor.
- ***Schmidtea mediterranea***: smedinx-11, the knockdown of the proton-potassium pump,
  TRPA1 with its patch-clamp recording, the TRPM and PKD families, the sodium-channel
  genes of the nervous system, the solute-carrier map, ammonia excretion, applied
  currents, a surface recording of the brain, and both single-cell atlases.
- **Other planarians:** *Girardia tigrina* and the marine *Bdelloura candida* (the current
  recordings), *Girardia dorotocephala* (octanol and head shape, TRPA1, drugs), *Dugesia
  ryukyuensis* (an innexin).

By records: 18 include *S. mediterranea*, 16 are *D. japonica* without it, and 21
are another planarian, a model, or name no species in what was read.

**What that means for use.** A result in another species is a prior, not a measurement of
ours: the lead's category for it is "related strain or species". The genes differ too.
The catalogue holds *S. mediterranea* only, so a *D. japonica* calcium channel or innexin
has no gene model to be tied to here without a sequence comparison across species, which
was not made. One preprint in the inventory shows how far a drug's effect can differ:
barium chloride takes three days to remove the head of *D. japonica* and dissolved a wild
*Girardia* within thirty minutes.

## Family by family

"None found" says what the searches below returned; the last column is the one that
bears on a law.

| Family | Named and sequenced genes | Expression | Knockdown | Drugs | Imaging | The protein's own behaviour, measured |
| --- | --- | --- | --- | --- | --- | --- |
| Innexins (gap junctions) | Dugesia japonica: the family cloned (2005), three members knocked down together. Schmidtea mediterranea: smedinx-11 and two more entries in UniProt. Dugesia ryukyuensis: one. | In situ maps of the family in Dugesia japonica; smedinx-11 in stem cells | Yes, in three species | Octanol and heptanol, in four species | Voltage-dye images after octanol | None found. No dye-transfer, electrical-coupling or expressed-channel measurement of a planarian innexin turned up in PubMed searches for those words |
| Proton-potassium pump | One alpha subunit each in Schmidtea mediterranea (tied) and Dugesia japonica | Head blastema in Dugesia japonica | Schmidtea mediterranea | SCH-28080 in Dugesia japonica | Voltage-dye images | None found: the pump's transport was not measured; its role is inferred from a drug, a knockdown and dye images |
| Sodium-potassium pump | None named in the papers read | Transcript level of the alpha subunit in Schmidtea mediterranea | None found | Inhibitors in an excretion study | None | None found |
| V-type proton pump | None named in the papers read | Transcript level of subunit A in Schmidtea mediterranea | None found | Inhibitors in an excretion study | None | None found |
| Voltage-gated sodium channels | scna-1, -2, -3 in Schmidtea mediterranea (tied); BdNa1 in Bdelloura candida | Neuronal, by the screen they come from | scna-2 | None found | None | A tetrodotoxin-sensitive sodium current recorded in brain cells of Bdelloura candida (1993). Not tied to a cloned channel |
| Voltage-gated potassium channels | kcnb in Schmidtea mediterranea (tied) | From sequencing datasets only | None found for a named gene | Barium chloride, as a blocker of potassium channels | None | Potassium currents recorded in brain and muscle cells of Bdelloura candida and in muscle of Girardia tigrina. Not tied to cloned channels |
| Other potassium channels (two-pore, inward-rectifier, calcium-activated) | kcnka in Schmidtea mediterranea (tied) | From sequencing datasets only | None found | Barium chloride | None | As for the voltage-gated potassium channels |
| HCN and cyclic-nucleotide-gated channels | CNG1 in Schmidtea mediterranea (tied) | Edge of the head | Part of a screen | None found | None | None found |
| Voltage-gated calcium channels and their subunits | Five alpha and two beta subunits in Dugesia japonica | In situ probes in Dugesia japonica | Each alpha subunit and both beta subunits in Dugesia japonica | Praziquantel and many others | Calcium entry, as reported | An inward calcium current recorded in muscle of Girardia tigrina (2003) and of Bdelloura candida (1994), and in its brain cells. None on a cloned channel |
| Release channels of the calcium store (IP3 receptor, ryanodine receptor) | The IP3 receptor of Dugesia japonica | Pharynx, optic nerves, reproductive organs | Yes | Caffeine and ryanodine on muscle fibres | None | A binding affinity for IP3 of an expressed fragment (0.9 nM); functional ryanodine receptors shown by contraction |
| TRP channels (TRPA, TRPM, TRPV, PKD) | TRPA1 (tied), 21 TRPM candidates and the PKD genes in Schmidtea mediterranea; TRPA1 and TRPM in Dugesia japonica; TRPA1 in Girardia dorotocephala | In situ maps of TRPM and PKD genes | TRPA1 in three species; TRPM; PKD | Agonists and antagonists | None | Whole-cell patch clamp of the Schmidtea mediterranea TRPA1 in Drosophila S2 cells: activated by AITC and hydrogen peroxide, not by heat (2017) |
| Acid-sensing and degenerin channels | None: a survey found no candidate in Schmidtea mediterranea | Not applicable | Not applicable | None found | None | Not applicable |
| Chloride channels | None named in the papers read | None found | None found | Ivermectin, and chloride-channel blockers | None | None found |
| Ligand-gated channels | Nicotinic receptor subunits in Girardia dorotocephala; receptor subunits among a screen's targets in Schmidtea mediterranea | Not audited | Part of a screen | Not audited | None | Not audited: this family was searched only in passing |
| Exchangers (sodium-calcium, sodium-proton, anion) | Sodium-proton, sodium-calcium and anion exchangers of Schmidtea mediterranea (tied) | Every one mapped by in situ hybridisation | None found for these | Inhibitors in an excretion study | None | None found |
| Cation-chloride cotransporters | Five slc12a genes of Schmidtea mediterranea (tied) | Mapped by in situ hybridisation | None found | None found | None | None found |
| Calcium pumps (plasma membrane, SERCA) | None named in the papers read | None found | None found | None found | None | None found |
| Aquaporins | None named in the papers read | None found | None found | None found | None | None found: the searches returned nothing on planarian aquaporins |

Searched for the last column, in PubMed and Europe PMC: patch clamp, voltage clamp,
whole-cell, ionic currents, oocytes, heterologous expression, dye coupling, dye transfer,
electrical coupling and conductance, each with planarian, *Dugesia*, *Schmidtea*,
*Girardia*, *Bdelloura*, triclad or turbellarian.

## What was said from general knowledge, checked

| Statement | Verdict | What was read |
| --- | --- | --- |
| Much of the work measures whole-animal outcomes after a pump, a channel family or the gap junctions are knocked down or blocked, such as two-headed worms | **Confirmed** | Read in eleven records, among them the pump block, octanol, the innexin knockdowns and praziquantel |
| Voltage-dye images show body-wide patterns of membrane voltage, relative and not in millivolts | **Confirmed** | The protocol's own abstract says the images 'qualitatively reveal variations in time-averaged membrane potential'; the papers speak of relative depolarisation |
| Expression maps show where channel genes are switched on | **Confirmed** | In situ maps of innexins, of all solute carriers, of TRPM and PKD genes, and two single-cell atlases with public data |
| Data on what a channel law needs, conductances and gating measured on a planarian channel, is thin and is still borrowed from other species | **Corrected in part** | Thin, but not absent. One Schmidtea mediterranea channel, TRPA1, was patch-clamped in a heterologous cell. Native sodium, calcium and potassium currents were voltage-clamped in cells of two other planarians (Bdelloura candida, 1993 and 1994; Girardia tigrina, 2003), and an IP3 receptor fragment's binding affinity was measured. None of this is on the channels the atlas draws for Schmidtea mediterranea, and only abstracts of the current recordings were read, so whether they give numbers a law could use is not known |
| Several of the best-known experiments were done in Dugesia japonica, not Schmidtea mediterranea | **Confirmed, and stronger than said** | The pump block with dye imaging, the octanol and two-headed work, the innexin triple knockdown, praziquantel and the calcium channels, the barium adaptation and the IP3 receptor are all Dugesia japonica |
| Only 4 of the atlas's products are named in a paper tied to a database entry | **Holds by the atlas's rule; more by a wider one** | By this audit's rule (the entry cites the paper), kcnb, kcnka, CNG1, the proton-potassium pump, TRPA1 and the exchangers, cotransporters and PKD channels of one expression study are also named and tied |

## The evidence

55 records from 64 papers. By category: 16 measured in *S. mediterranea*,
29 in another planarian, 2 in a reconstructed system, 2 inferred, 3 from
models, 2 protocols and 1 with no species stated. By reading: 29 with the full text
searched, 25 by abstract only, 1 by record only. Public data: 7 deposits seen to
exist, 5 stated by the article and not fetched, 18 none found, 25 not determined;
and 14 sequence records seen at GenBank.

By kind of measurement (a record can have several): drug outcome 19, knockdown outcome 19, expression map 12, sequencing dataset 9, sequence 7, behaviour 6, voltage-dye imaging 5, model 5, applied field 4, current recording, isolated cells 3, contraction of isolated cells 3, sequence survey 3, extracellular recording 3, calcium entry 2, ion transport physiology 2, pH imaging 1, binding assay 1, current recording, heterologous cells 1, tissue potential 1.

| Record | What was measured | How | Species | Families | Category | Paper, licence | Public data | Could test | Read |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `hk-block-head` | Which end regenerates a head when the proton-potassium pump is blocked with SCH-28080, or when voltage is shifted with ivermectin; relative membrane voltage of fragments | Drug exposure of cut fragments; marker genes; the dye DiBAC4(3) imaged on 24-hour fragments | Dugesia japonica (GI, asexual clonal) | Proton-potassium pump, Chloride channels, No protein named: voltage, fields or transport of the whole tissue | related strain | Beane 2011, doi:10.1016/j.chembiol.2010.11.012 (no licence stated; the author manuscript in PMC may be used for text mining and under fair use) | none found | voltage shift and head-or-tail outcome after a pump is blocked | full text searched |
| `hk-rnai-size` | Head size and organ proportions after RNAi of the proton-potassium pump; the abstract reports membrane hyperpolarisation and missing apoptosis | RNAi; how voltage was read is not in the abstract | Schmidtea mediterranea | Proton-potassium pump | measured exact | Beane 2013, doi:10.1242/dev.086900 (no licence stated) | not determined | organ proportions after a pump's knockdown | abstract only |
| `hk-eye-asymmetry` | Left-right bias of eye defects when H+/K+-ATPase activity is inhibited; a non-gastric H+/K+-ATPase alpha transcript seen in the head blastema | Inhibitor exposure; in situ hybridisation | Dugesia japonica | Proton-potassium pump | related strain | Nogi 2005, doi:10.1080/1357650054200001440 (no licence stated) | not determined | where a pump's transcript is found after amputation | abstract only |
| `dibac-protocol` | A protocol for imaging membrane potential in live planarians with DiBAC4(3) | The abstract: the images 'qualitatively reveal variations in time-averaged membrane potential', and standard electrophysiology 'cannot be used' on a whole worm 'due to small cell size and large cell number' | planarians; the text searched names no species | No protein named: voltage, fields or transport of the whole tissue | method | Oviedo 2008, doi:10.1101/pdb.prot5055 (no licence stated; the author manuscript in PMC may be used for text mining and under fair use) | none found | what a relative voltage image can and cannot be compared with | full text searched |
| `ph-protocol` | A protocol for imaging intracellular pH gradients in living planarians with the ratiometric dye SNARF-5F-AM | Ratiometric dye imaging of intact and regenerating worms | planarians; the text names Schmidtea mediterranea and Dugesia japonica once each | No protein named: voltage, fields or transport of the whole tissue | method | Beane 2019, doi:10.1093/biomethods/bpz005 (CC BY-NC) | none found | pH gradients along the body | full text searched |
| `octanol-two-heads` | The share of trunk fragments that regenerate two heads after brief exposure to the gap-junction blocker octanol, in that round and in later cuts in plain water; relative voltage patterns | Octanol exposure; DiBAC4(3) imaging, with the dye's response rechecked against a valinomycin and potassium depolarising solution | Dugesia japonica | Innexins, No protein named: voltage, fields or transport of the whole tissue | related strain | Durant 2017, doi:10.1016/j.bpj.2017.04.011 (CC BY-NC-ND) | none found | a stable two-outcome ratio that persists through later regeneration | full text searched |
| `early-depolarisation` | Double-headed regeneration and altered gene expression at 6 hours after depolarising the wound with ionophores during the first 3 hours | Ionophore exposure and washout; gene expression | Dugesia japonica | No protein named: voltage, fields or transport of the whole tissue | related strain | Durant 2019, doi:10.1016/j.bpj.2019.01.029 (no licence stated) | not determined | an early voltage change and the later head-or-tail outcome | abstract only |
| `octanol-head-shape` | Head shapes regenerated after octanol, some resembling other species; relative voltage patterns; an agent-based model | Octanol exposure; morphometrics; DiBAC imaging | Girardia dorotocephala | Innexins, No protein named: voltage, fields or transport of the whole tissue | related strain | Emmons-Bell 2015, doi:10.3390/ijms161126065 (CC BY) | none found | shape outcomes after coupling is blocked | full text searched |
| `barium-adaptation` | Head degeneration in barium chloride and regeneration of barium-insensitive heads; transcript changes; effects of chloride-channel, calcium-channel and TRPM blockers | Drug exposure; RNA sequencing of heads | Dugesia japonica | Other potassium channels, Voltage-gated potassium channels, Chloride channels, Voltage-gated calcium channels and their subunits, TRP channels | related strain | Emmons-Bell 2019, doi:10.1016/j.isci.2019.11.014 (CC BY-NC-ND) | none found | adaptation of a tissue to a potassium-channel blocker | full text searched |
| `barium-single-worm` | Transcript profiles of individual worms adapting to barium chloride | RNA sequencing of single animals | Dugesia japonica | Other potassium channels | related strain | Kapsetaki 2026, doi:10.64898/2026.07.28.741268 (CC BY) | not determined | variation between animals in the same adaptation | abstract only |
| `barium-girardia` | Peripheral disintegration within thirty minutes in 1 mM barium chloride, unlike the slow head loss reported in Dugesia japonica | Drug exposure | Girardia species, collected from a stream (wild) | Other potassium channels | related strain | Molano 2023, doi:10.1101/2023.04.29.538822 (no licence stated) | not determined | how far one species' drug response carries to another | abstract only |
| `innexin-family-dj` | The innexin gene family cloned, its expression during regeneration in three groups, and polarity changes after a gap-junction blocker | Cloning; in situ hybridisation; blocker exposure | Dugesia japonica | Innexins | related strain | Nogi 2005, doi:10.1016/j.ydbio.2005.09.002 (no licence stated) | not determined | which junction genes are expressed where coupling matters | abstract only |
| `smedinx-11` | Loss of regeneration and of stem cells after RNAi of the innexin smedinx-11, which is expressed in stem cells | RNAi; in situ hybridisation; irradiation | Schmidtea mediterranea (CIW4 (sequence record)) | Innexins | measured exact | Oviedo 2007, doi:10.1242/dev.006635 (no licence stated) | not determined | what the loss of one junction gene does to a tissue's renewal | abstract only |
| `innexin-triple-rnai` | Ectopic anterior blastemas after octanol (127 µM) or after RNAi of three innexins together; octanol taken up by the tissue | Octanol exposure; injection of double-stranded RNA for Dj-Inx-5, -13 and -12; gas chromatography and mass spectrometry of tissue octanol | Dugesia japonica (GI, clonal) | Innexins | related strain | Oviedo 2010, doi:10.1016/j.ydbio.2009.12.012 (no licence stated; the author manuscript in PMC may be used for text mining and under fair use) | none found | polarity after coupling is reduced by a drug or by knockdown | full text searched |
| `innexin-reproduction` | An innexin, Dr-siri, needed to end the asexual state when sexual development is induced | RNAi; expression | Dugesia ryukyuensis (OH) | Innexins | related strain | Kumagai 2025, doi:10.1371/journal.pgen.1011944 (CC BY) | none found | a junction gene's role outside patterning | full text searched |
| `pzq-cav-beta` | Two-headed regeneration caused by praziquantel, removed by RNAi of calcium-channel beta subunits and not by RNAi of an alpha subunit | Drug exposure; RNAi; cloning of the beta subunits | Dugesia japonica (GI, asexual clonal) | Voltage-gated calcium channels and their subunits | related strain | Nogi 2009, doi:10.1371/journal.pntd.0000464 (CC BY) | none found | a drug's outcome depending on one channel subunit | full text searched |
| `cav-alpha-family` | The family of calcium-channel alpha subunits; praziquantel's two-headed outcome and calcium entry prevented by RNAi of Cav1A; opposing roles of Cav1A and Cav1B | RNAi of single subunits; drug exposure; how calcium entry was measured is not in the abstract | Dugesia japonica | Voltage-gated calcium channels and their subunits | related strain | Zhang 2011, doi:10.1523/jneurosci.3029-11.2011 (CC BY-NC-SA) | not determined | opposite outcomes from two channels of one family | abstract only |
| `pzq-phenologs` | Compounds that copy or block praziquantel's two-headed outcome, used to predict agents against schistosomes | Drug screens on regenerating fragments; RNAi | Dugesia japonica (GI, clonal) | Voltage-gated calcium channels and their subunits | related strain | Chan 2014, doi:10.1371/journal.ppat.1003942 (CC BY) | none found | one phenotype read out for many drugs on calcium entry | full text searched |
| `cav-transcriptome` | A de novo transcriptome and its voltage-gated-like channel genes; the outcome of knocking down each calcium channel, with Cav1B knockdown impairing muscle function | RNA sequencing and assembly; curation of channel sequences; RNAi; in situ probes | Dugesia japonica (GI) | Voltage-gated calcium channels and their subunits, Voltage-gated sodium channels, Voltage-gated potassium channels, Other potassium channels, TRP channels, HCN and cyclic-nucleotide-gated channels | related strain | Chan 2017, doi:10.1016/j.bbamcr.2016.10.010 (no licence stated; the author manuscript in PMC may be used for text mining and under fair use); Chan 2016, doi:10.1016/j.dib.2016.11.022 (CC BY) | Files with the Data in Brief article: the assemblies as FASTA and a table of the channels (CC BY (the article); not fetched) | which channels a planarian has, and the muscle's dependence on one of them | full text searched |
| `ip3-receptor` | The IP3 receptor cloned; an expressed fragment (residues 223 to 585) binds IP3 with an affinity of 0.9 ± 0.1 nM, lost with one point mutation; expression; fewer eggs laid after RNAi | Expression of the binding region and radioligand binding; in situ hybridisation; RNAi | Dugesia japonica | Release channels of the calcium store | reconstituted | Zhang 2013, doi:10.1016/j.ceca.2013.01.003 (no licence stated; the author manuscript in PMC may be used for text mining and under fair use) | none found | a measured ligand affinity of a planarian channel | full text searched |
| `muscle-ca-current` | A voltage-gated inward current in single muscle fibres, larger with barium, independent of sodium, blocked by cobalt and not by tetrodotoxin; an outward potassium current; contraction on depolarisation | Whole-cell recording from freshly dispersed muscle fibres; contraction in raised potassium | Girardia tigrina | Voltage-gated calcium channels and their subunits, Other potassium channels | related strain | Cobbett 2003, doi:10.1016/s1095-6433(02)00350-1 (no licence stated) | not determined | a native calcium current of a planarian muscle cell | abstract only |
| `muscle-ryanodine` | Caffeine contracts single muscle fibres (half-maximal at 3.2 mM in Dugesia tigrina and 4.6 mM in Procerodes littoralis), blocked by ryanodine | Drugs applied to dispersed muscle fibres | Girardia tigrina; Procerodes littoralis | Release channels of the calcium store | related strain | Day 2000, doi:10.1017/s0031182099005594 (no licence stated) | not determined | release from the calcium store in a muscle cell | abstract only |
| `brain-cell-currents` | Brain cells in culture carry a fast transient sodium current that tetrodotoxin blocks, a calcium current and several potassium currents | Whole-cell voltage clamp of cultured cells from the brain | Bdelloura candida (a marine triclad) | Voltage-gated sodium channels, Voltage-gated calcium channels and their subunits, Voltage-gated potassium channels, Other potassium channels | related strain | Blair 1993, doi:10.1242/jeb.185.1.267 (no open licence: the publisher's user licence (Crossref record)) | not determined | the set of currents in a planarian neuron | abstract only |
| `muscle-cell-currents` | Isolated muscle fibres carry an inward calcium current and three potassium currents, and contract in response to transmitters and praziquantel | Voltage clamp of dissociated muscle fibres; contraction | Bdelloura candida (a marine triclad) | Voltage-gated calcium channels and their subunits, Other potassium channels, Voltage-gated potassium channels | related strain | Blair 1994, doi:10.1017/s0031182000078355 (no open licence: the publisher's terms (Crossref record)) | not determined | the set of currents in a planarian muscle cell | abstract only |
| `sodium-channel-clone` | A cDNA, BdNa1, encoding a protein like the main subunit of voltage-gated sodium channels | Cloning and sequence comparison | Bdelloura candida (a marine triclad) | Voltage-gated sodium channels | related strain | Jeziorski 1997, doi:10.1017/s0031182097001388 (no licence stated) | not determined | the channel behind a recorded sodium current | abstract only |
| `trpa1-behaviour` | Escape from noxious heat and irritant chemicals is lost after RNAi of TRPA1 | RNAi; behavioural assays | Schmidtea mediterranea (CIW4, asexual) | TRP channels | measured exact | Arenas 2017, doi:10.1038/s41593-017-0005-0 (no open licence; the PMC manuscript may be viewed and data-mined for academic research under the publisher's terms) | none found | a behaviour that depends on one channel | full text searched |
| `trpa1-patch-clamp` | The planarian TRPA1 channel, expressed in Drosophila S2 cells, is activated by the irritant AITC and by hydrogen peroxide and not by heat | Whole-cell patch clamp of S2 cells expressing Smed-TRPA1 | Schmidtea mediterranea (CIW4 (the cloned channel)) | TRP channels | reconstituted | Arenas 2017, doi:10.1038/s41593-017-0005-0 (no open licence; the PMC manuscript may be viewed and data-mined for academic research under the publisher's terms) | none found | a planarian channel's own response to an agonist | full text searched |
| `trpa-light` | Avoidance of near-ultraviolet light by eyeless worms is lost after RNAi of Smed-TrpA | RNAi; behavioural assays | Schmidtea mediterranea (asexual) | TRP channels | measured exact | Birkholz 2017, doi:10.1242/jeb.152298 (CC BY) | none found | a second behaviour that depends on the same kind of channel | full text searched |
| `trp-scrunching` | Agonists of TRPA1 and TRPV induce the scrunching gait; RNAi of TRPA1 removes the response to AITC in both species | Drug exposure; RNAi; gait analysis | Dugesia japonica (asexual); Schmidtea mediterranea (asexual) | TRP channels | measured exact | Sabry 2019, doi:10.1371/journal.pone.0226104 (CC BY) | Within the article and its supporting files (CC BY (the article); not fetched) | one channel's part in a behaviour, in two species | full text searched |
| `trpm-thermotaxis` | Thermotaxis needs neurons that express the TRPM homolog DjTRPMa | RNAi; in situ hybridisation; a thermotaxis assay | Dugesia japonica | TRP channels | related strain | Inoue 2014, doi:10.1523/jneurosci.5379-13.2014 (CC BY-NC-SA) | not determined | temperature sensing through one channel | abstract only |
| `trpm-family` | Twenty-one candidate TRPM genes; where each is expressed; RNAi of the two expressed in testis | Sequence search of transcriptomes; in situ hybridisation; RNAi | Schmidtea mediterranea (sexual and asexual) | TRP channels | measured exact | Curry 2025, doi:10.1387/ijdb.240180lr (CC BY) | none found | how large one channel family is, and where its members are expressed | full text searched |
| `pkd-family` | Expression and function of all the pkd genes of the genome | In situ hybridisation; RNAi; behavioural tests | Schmidtea mediterranea (asexual and hermaphroditic) | TRP channels | measured exact | Ross 2024, doi:10.1093/iob/obae035 (CC BY) | In the article and its supplementary material (CC BY (the article); not fetched) | sensory channels of one family mapped to cells | full text searched |
| `trpa1-girardia` | Cinnamaldehyde evokes a nociceptive behaviour that RNAi of Gd-TRPA1 suppresses | Drug exposure; RNAi; open-field analysis | Girardia dorotocephala | TRP channels | related strain | Morana 2025, doi:10.1016/j.neulet.2024.138041 (CC BY) | not determined | the same channel's role in a third species | abstract only |
| `asic-absent` | No candidate acid-sensing ion channel was found in Schmidtea mediterranea | A search of sequence data across bilaterians | Schmidtea mediterranea | Acid-sensing and degenerin channels | inferred fitted | Martí-Solans 2023, doi:10.7554/elife.81613 (CC BY) | The alignment is a supplementary file of the article (CC BY (the article); not fetched) | a channel family the organism does not have | full text searched |
| `coe-targets` | Genes that fall after RNAi of the transcription factor coe, many of them ion channels; RNAi of those genes, where a sodium-channel alpha subunit, scna-2, is needed for regeneration of the nervous system | RNA sequencing of control and RNAi animals; RNAi of the validated targets | Schmidtea mediterranea (CIW4, asexual) | Voltage-gated sodium channels, Voltage-gated potassium channels, Other potassium channels, Ligand-gated channels | measured exact | Cowles 2014, doi:10.1371/journal.pgen.1004746 (CC BY) | NCBI Sequence Read Archive: PRJNA235907 (seen; no licence on the record; the sequence databases' policy places no restriction on use) | channel genes of neurons, and one whose loss shows | full text searched |
| `brain-screen-cng` | A screen of genes expressed in the regenerating brain; CNG1, a cyclic-nucleotide-gated channel, is expressed at the edge of the head | RNA sequencing; in situ hybridisation; RNAi | Schmidtea mediterranea (CIW4, asexual clonal) | HCN and cyclic-nucleotide-gated channels | measured exact | Roberts-Galbraith 2016, doi:10.7554/elife.17002 (CC BY) | NCBI Sequence Read Archive: PRJNA319973 (seen; no licence on the record; the sequence databases' policy places no restriction on use) | where a sensory channel is expressed | full text searched |
| `slc-expression-map` | 318 solute-carrier genes found in the genome and the expression of all of them mapped, among them sodium-proton and anion exchangers in the excretory tubules; cysts after RNAi of kidney-disease gene homologs | Sequence search; in situ hybridisation of every gene; RNAi | Schmidtea mediterranea (asexual) | Exchangers, Cation-chloride cotransporters, TRP channels | measured exact | Thi-Kim 2015, doi:10.7554/elife.07405 (CC BY) | UniProtKB entries that cite the paper, which the catalogue holds: PubMed 26057828 (seen; CC BY 4.0 (UniProt); CC BY (the article)) | where each exchanger and cotransporter is expressed | full text searched |
| `ammonia-excretion` | Ammonia excretion depends on acidifying the body surface; inhibitors implicate the V-type proton pump and carbonic anhydrase, and possibly the sodium-potassium pump and sodium-proton exchangers; transcript levels of the pump subunits and an Rh protein change with the water's pH and ammonia | Excretion rates in buffered water; inhibitors; transcript levels; in situ hybridisation | Schmidtea mediterranea | V-type proton pump, Sodium-potassium pump, Exchangers | measured exact | Weihrauch 2012, doi:10.1242/jeb.067942 (no licence stated) | not determined | ion transport across the skin of the animal | abstract only |
| `tissue-potential-thesis` | A voltage gradient in the tissue spaces, with the head more negative than the tail, kept in regenerating fragments; techniques for transepithelial potential, epithelial ion transport and applied fields | Techniques developed for the thesis to measure transepithelial potential and epithelial ion transport; applied electric fields | Dugesia japonica; Schmidtea mediterranea | No protein named: voltage, fields or transport of the whole tissue | measured exact | Annand 2014 (no licence stated (thesis record)) | not determined | a measured electrical gradient along the body | abstract only |
| `field-polarity-1952` | Two papers on the electrical control of regeneration in Dugesia tigrina: axial polarity against field strength, and potential gradient against current density | Applied electric fields, by the titles | Girardia tigrina | No protein named: voltage, fields or transport of the whole tissue | related strain | MARSH 1952, doi:10.1002/jcp.1030390203 (no licence stated); DIMMITT 1952, doi:10.1002/jcp.1030400103 (no licence stated) | not determined | polarity reversed by an applied field | record only |
| `field-model-1978` | A substance that inhibits brain formation runs as a negatively charged molecule in electrophoresis; the authors propose that a bioelectric field moves it tailward | Electrophoresis of the substance; a proposed model | Dugesia etrusca | No protein named: voltage, fields or transport of the whole tissue | inferred fitted | Lange 1978, doi:10.1111/j.1432-0436.1978.tb00965.x (no licence stated) | not determined | a field acting on a charged signal | abstract only |
| `current-stimulation` | Direct current applied to whole worms changes where cells divide, and restores stem-cell activity in irradiated tissue through calcium entry by L-type channels and release from stores | Current through pulled glass microelectrodes for up to six hours; how calcium was measured is not in the abstracts | Schmidtea mediterranea | No protein named: voltage, fields or transport of the whole tissue, Voltage-gated calcium channels and their subunits, Release channels of the calcium store | measured exact | Davidian 2021, doi:10.1089/bioe.2020.0026 (no licence stated); Davidian 2022, doi:10.1242/jcs.259304 (no licence stated) | not determined | a tissue's response to an applied current | abstract only |
| `electrotaxis` | Worms move to the cathode at 2 V and respond to voltage, not current; decapitation restores the response in head fragments | An automated electrotaxis setup | Dugesia japonica (asexual) | No protein named: voltage, fields or transport of the whole tissue | related strain | Sabry 2022, doi:10.1242/jeb.243972 (CC BY) | GitHub, Collinslab-swat/Planarian-electrotaxis: https://github.com/Collinslab-swat/Planarian-electrotaxis (seen; no licence stated) | behaviour in an electric field | full text searched |
| `eeg-electrode` | A continuous brain signal at sub-microvolt amplitude, 0.1 to 5 Hz | A single electrode inserted in the head on a cold stage | a planarian; the abstract names no species | No protein named: voltage, fields or transport of the whole tissue | not assigned | Aoki 2009, doi:10.1016/j.neuroscience.2008.11.011 (no licence stated) | not determined | ongoing electrical activity of the brain | abstract only |
| `eeg-surface` | Continuous electrical activity recorded without piercing the animal, under different lighting | Surface wire electrodes on living worms | Schmidtea mediterranea (asexual) | No protein named: voltage, fields or transport of the whole tissue | measured exact | Freiberg 2023, doi:10.1186/s12868-023-00799-z (CC BY) | not determined | ongoing electrical activity of the brain | full text searched |
| `brain-units` | Multi-unit activity of the brain, its change along the head, and responses to stimuli, also in worms with two heads | Extracellular recording from a semi-intact, pinned preparation | Dugesia japonica | No protein named: voltage, fields or transport of the whole tissue | related strain | Benita 2024, doi:10.1242/bio.060480 (CC BY) | none found | spiking activity of a planarian brain | full text searched |
| `atlas-fincher` | Transcriptomes of essentially every cell type of the animal, so the cell types that express any channel gene can be read off | Single-cell RNA sequencing | Schmidtea mediterranea (asexual) | No protein named: voltage, fields or transport of the whole tissue | measured exact | Fincher 2018, doi:10.1126/science.aaq1736 (no licence stated; the author manuscript in PMC may be used for text mining and under fair use) | NCBI Gene Expression Omnibus: GSE111764 (seen; no licence stated on the record) | which cells express a given channel | full text searched |
| `atlas-plass` | A cell type atlas and lineage tree of the whole animal | Single-cell RNA sequencing | Schmidtea mediterranea | No protein named: voltage, fields or transport of the whole tissue | measured exact | Plass 2018, doi:10.1126/science.aaq1723 (no licence stated) | NCBI Gene Expression Omnibus: GSE103633 (seen; no licence stated on the record) | which cells express a given channel | abstract only |
| `transcriptome-tigrina` | A transcriptome of Girardia tigrina and drug screens on three targets | RNA sequencing; inhibitors on worms | Girardia tigrina | No protein named: voltage, fields or transport of the whole tissue | related strain | Wheeler 2015, doi:10.1186/s13071-014-0622-3 (CC BY) | Assemblies and annotations behind a shortened web link in the article (CC BY (the article); its data under a CC0 waiver; not fetched) | the gene set of a third species | full text searched |
| `nachr-dorotocephala` | A transcriptome of Girardia dorotocephala, checked by characterising its nicotinic acetylcholine receptor subunits | RNA sequencing; sequence analysis | Girardia dorotocephala (clonal line) | Ligand-gated channels | related strain | Almazan 2018, doi:10.1016/j.ydbio.2017.07.022 (CC BY-NC-ND) | NCBI Sequence Read Archive: PRJNA317859 (seen; no licence on the record; the sequence databases' policy places no restriction on use) | ligand-gated channel genes of a third species | full text searched |
| `lanthanum-channels` | Lanthanum's toxicity changes with agonists and antagonists of calcium, potassium, sodium, magnesium and chloride channels | Drug combinations on whole worms | Girardia dorotocephala (bought stock) | Voltage-gated calcium channels and their subunits, Voltage-gated potassium channels, Voltage-gated sodium channels, Chloride channels | related strain | Briner 2018, doi:10.3390/toxics6020033 (CC BY) | none found | which channel classes a toxic ion acts through | full text searched |
| `ivermectin-regeneration` | Regeneration under ivermectin, a chloride-channel opener | Drug exposure of regenerating worms | Girardia dorotocephala | Chloride channels | related strain | Ferenc 2019, doi:10.1002/mabi.201800237 (no licence stated) | not determined | regeneration when a chloride conductance is opened | abstract only |
| `model-betse` | The BETSE simulator, its extension to gene and reaction networks, and a model of body-axis control that predicts the share of two-headed regenerates | Finite-volume simulation of ion flows and gap junctions; a network model | a simulator; the 2019 model is set against experiments on Dugesia japonica | No protein named: voltage, fields or transport of the whole tissue | other simulator | Pietak 2016, doi:10.3389/fbioe.2016.00055 (CC BY); Pietak 2017, doi:10.1098/rsif.2017.0425 (no licence stated); Pietak 2019, doi:10.1371/journal.pcbi.1006904 (CC BY) | none found | another simulator's predictions for the same experiments | abstract only |
| `model-cervera` | Bioelectrical models of head-tail patterning from channels and gap junctions, of grafts between fragments, and of adaptation to a channel blocker | Mean-field and multicellular models | models of planaria | No protein named: voltage, fields or transport of the whole tissue | other simulator | Cervera 2020, doi:10.1016/j.bioelechem.2019.107410 (no licence stated); Cervera 2023, doi:10.1016/j.jtbi.2022.111356 (CC BY-NC-ND); Cervera 2024, doi:10.1038/s41598-024-79087-7 (CC BY) | not determined | another model's predictions for the same experiments | abstract only |
| `model-others` | Models of two-outcome pattern memory, of bioelectric networks, a hybrid framework for morphogenesis, and a geometric model of bioelectric memory | Mathematical and computational models | models motivated by planaria | No protein named: voltage, fields or transport of the whole tissue | other simulator | Pezzulo 2021, doi:10.1098/rstb.2019.0765 (no licence stated); Grodstein 2022, doi:10.1089/bioe.2021.0036 (no licence stated); Cortés-Poza 2026, doi:10.1007/s00285-026-02459-2 (CC BY-NC-ND); Blattner 2026, doi:10.64898/2026.04.01.715890 (no licence stated) | not determined | other models' predictions | abstract only |

## Named genes and our gene models

A gene is tied only through a database record: the paper's sequence record is a UniProtKB
entry that cites the paper, and the catalogue joins that entry to a gene model by
sequence. Nothing is tied by name, and nothing is called an ortholog. 62 named genes
are tied; 20 are not.

| Gene named | Its record | Tied to in the catalogue | From |
| --- | --- | --- | --- |
| ATP12A (non-gastric H+,K+-ATPase alpha subunit) | JX174182 | M4LUP7; h1SMcG0015880 | `hk-rnai-size` |
| smedinx-11 | DQ851133 | A7RDN9; h1SMcG0020152 | `smedinx-11` |
| Smed-TRPA1 | MF818036 | A0A291IA19; h1SMcG0019963 | `trpa1-behaviour` |
| scna-1 | A0A0A1CVW3 | A0A0A1CVW3; h1SMcG0013155 | `coe-targets` |
| scna-2 | A0A0A1CQM0 | A0A0A1CQM0; h1SMcG0014796 | `coe-targets` |
| scna-3 | A0A0A1CRL5 | A0A0A1CRL5; h1SMcG0013155 | `coe-targets` |
| kcnb | A0A0A1CQL4 | A0A0A1CQL4; h1SMcG0008430 | `coe-targets` |
| kcnka | A0A0A1CVW0 | A0A0A1CVW0; h1SMcG0004125 | `coe-targets` |
| CNG1 | A0A1Z1R0Y6 | A0A1Z1R0Y6; h1SMcG0005006 | `brain-screen-cng` |
| 53 genes of one expression study: slc4a, slc8a, slc9a, slc12a, slc24a, slc26a and PKD | their UniProtKB entries | each to its entry; 45 also to a gene model | `slc-expression-map` |

Not tied:

| Gene named | Species | Why it is not tied |
| --- | --- | --- |
| BdNa1 | Bdelloura candida | Another species: the catalogue holds Schmidtea mediterranea only |
| Cav1A | Dugesia japonica | Another species: the catalogue holds Schmidtea mediterranea only |
| Cav1B | Dugesia japonica | Another species: the catalogue holds Schmidtea mediterranea only |
| Cav2A | Dugesia japonica | Another species: the catalogue holds Schmidtea mediterranea only |
| Cav2B | Dugesia japonica | Another species: the catalogue holds Schmidtea mediterranea only |
| Cav3 | Dugesia japonica | Another species: the catalogue holds Schmidtea mediterranea only |
| Cavβ1 | Dugesia japonica | Another species: the catalogue holds Schmidtea mediterranea only |
| Cavβ2 | Dugesia japonica | Another species: the catalogue holds Schmidtea mediterranea only |
| Dj-Inx-12 | Dugesia japonica | Another species: the catalogue holds Schmidtea mediterranea only |
| Dj-Inx-13 | Dugesia japonica | Another species: the catalogue holds Schmidtea mediterranea only |
| Dj-Inx-5 | Dugesia japonica | Another species: the catalogue holds Schmidtea mediterranea only |
| Dj.IP3R | Dugesia japonica | Another species: the catalogue holds Schmidtea mediterranea only |
| DjTRPMa | Dugesia japonica | Another species: the catalogue holds Schmidtea mediterranea only |
| Dr-siri | Dugesia ryukyuensis | Another species: the catalogue holds Schmidtea mediterranea only |
| Gd-TRPA1 | Girardia dorotocephala | Another species: the catalogue holds Schmidtea mediterranea only |
| Smed-TRPM-c | Schmidtea mediterranea | Its record is not among the UniProtKB entries the catalogue was built from, and no sequence comparison was made here |
| Smed-TrpA | Schmidtea mediterranea | No accession was found in what was read |
| inx3 | Dugesia japonica | Another species: the catalogue holds Schmidtea mediterranea only |
| inx7 | Dugesia japonica | Another species: the catalogue holds Schmidtea mediterranea only |
| non-gastric H,K-ATPase alpha subunit | Dugesia japonica | Another species: the catalogue holds Schmidtea mediterranea only |

## What could not be determined

- Whether the current recordings of 1993, 1994 and 2003 report conductances, kinetics or current-voltage relations that a law could be set from: only their abstracts were read.
- How membrane voltage and calcium entry were read in the papers known only by abstract.
- What the 2014 thesis measured in numbers: its record's abstract is cut short and the thesis was not fetched.
- The two papers of 1952 on applied fields: their records have no abstract.
- Which strain was used in the papers read by abstract.
- Whether data behind the papers that name no deposit exists elsewhere: no author was asked, by rule.
- The ligand-gated channels, and behavioural pharmacology in general, were not audited beyond what the searches returned.
- Which gene models the named genes of other species correspond to: the catalogue holds Schmidtea mediterranea only, and no sequence comparison across species was made.

## Reviews read for orientation, and leads not audited

Reviews and overviews, used to find papers and not as evidence:

- Barghouth PG, Thiruvalluvan M, Oviedo NJ. (2015) Bioelectrical regulation of cell cycle and the planarian model system. Biochim Biophys Acta. doi:10.1016/j.bbamem.2015.02.024 (no licence stated)
- Durant F, Lobo D, Hammelman J, Levin M. (2016) Physiological controls of large-scale patterning in planarian regeneration: a molecular and computational perspective on growth and form. Regeneration (Oxf). doi:10.1002/reg2.54 (CC BY)
- Peiris TH, Oviedo NJ. (2013) Gap junction proteins: master regulators of the planarian stem cell response to tissue maintenance and injury. Biochim Biophys Acta. doi:10.1016/j.bbamem.2012.03.005 (no licence stated)
- Marchant JS. (2019) Ca2+ Signaling and Regeneration. Cold Spring Harb Perspect Biol. doi:10.1101/cshperspect.a035485 (no licence stated)
- Chan JD, Zarowiecki M, Marchant JS. (2013) Ca²⁺ channels and praziquantel: a view from the free world. Parasitol Int. doi:10.1016/j.parint.2012.12.001 (no licence stated)
- Jeziorski MC, Greenberg RM. (2006) Voltage-gated calcium channel subunits from platyhelminths: potential role in praziquantel action. Int J Parasitol. doi:10.1016/j.ijpara.2006.02.002 (no licence stated)
- Blair KL, Anderson PAV. (1996) Physiology and pharmacology of turbellarian neuromuscular systems. Parasitology 113:S73-S82. doi:10.1017/s0031182000077908 (no open licence: the publisher's terms (Crossref record))
- Reho G, Lelièvre V, Cadiou H. (2022) Planarian nociception: Lessons from a scrunching flatworm. Front Mol Neurosci. doi:10.3389/fnmol.2022.935918 (CC BY)
- Levin M, Pietak AM, Bischof J. (2019) Planarian regeneration as a model of anatomical homeostasis: Recent progress in biophysical and computational approaches. Semin Cell Dev Biol. doi:10.1016/j.semcdb.2018.04.003 (no licence stated)

Leads the searches returned that were not audited:

- Settles SE, Miller KE, Roberts-Galbraith RH. (2025) A parenchymal niche regulates pluripotent stem cell function in planarians. preprint. A preprint: two innexin genes needed for stem-cell function; its abstract names no species.
- Scimone ML, Srivastava M, Bell GW, Reddien PW. (2011) A regulatory program for excretory system regeneration in planarians. Development. Excretory cells express homologs of reabsorption proteins; not audited.
- Moneypenny CG, Kreshchenko N, Moffett CL, Halton DW, Day TA, Maule AG. (2001) Physiological effects of FMRFamide-related peptides and classical transmitters on dispersed muscle fibres of the turbellarian, Procerodes littoralis. Parasitology. Transmitters and peptides contract dispersed muscle fibres of Procerodes littoralis; not audited.
- Reho G, Menger Y, Goumon Y, Lelièvre V, Cadiou H. (2024) Behavioral and pharmacological characterization of planarian nociception. Front Mol Neurosci. Nociceptive tests and drugs in Girardia dorotocephala; not audited.
- McCubbin RA, Auwal MA, Wang S, Alvarez Zepeda S, Sasik R, Zeller RW, Ross KG, Zayas RM. (2025) Smed-pou4-2 regulates mechanosensory neuron regeneration and function in planarians. Elife. A transcription factor of mechanosensory neurons in Schmidtea mediterranea; its channel genes were not audited.

## The inventory's format

`cells.visualizer.planarian_bioelectric_evidence@1`, one JSON file:

- `target`, `evidence_categories`, `read_levels`, `kinds`, `families`: the fixed words.
  The first five categories are the lead's; `method` and `not assigned` are added here
  for protocols and for records that name no species.
- `papers`: each with its citation, DOI, PubMed and PMC ids, the licence its record
  states ("no licence stated" where it states none), and how far it was read.
- `records`: one per experiment family or dataset. Each has its papers, species and
  strain, protein families, kinds of measurement, what was measured and how, what the
  reported values are (a relative image, a count, a current), the evidence category, the
  public deposit with its state and licence, the sequence records seen, the genes named
  with their ties to the catalogue, and one phrase on what it could test.
- `family_summary`, `claims_checked`, `context`, `leads_not_audited`, `not_determined`:
  the tables of this note.

Reading levels: `full text searched` means the open text was fetched and searched for
the animals, sequences, deposits and methods, and the passages found were read; it is
not a reading of the whole paper. `abstract only` and `record only` say what they say.
A deposit is `verified` when its record was seen to exist, `stated` when the article
names it and it was not fetched.

## Terms

- Each paper's licence is recorded as its record states it. 33 of the 64 papers state no
  open licence. By the project's rule, tables, traces and plots from those, and from
  non-commercial sources, stay outside the repository; none is in this inventory.
- GEO and GitHub records seen here state no licence. Sequence and read archives fall
  under the sequence databases' policy of unrestricted use.
- Authors were not contacted. Where a paper names no deposit, the inventory says "none
  found" or "not determined", and nothing further was asked.

## A next step, not taken

The three current recordings and the thesis are where numbers a law could use would be,
if anywhere. Reading them in full needs the papers themselves, which were not open to
the routes this audit used. The patch-clamp paper's figures hold the one cloned
channel's responses and were not read. None of that was done here.
