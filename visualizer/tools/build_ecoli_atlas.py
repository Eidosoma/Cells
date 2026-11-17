#!/usr/bin/env python3
"""Build the viewer's data on Escherichia coli K-12: the species, its side of the protein atlas, and its own proteins on shelves.

Five files are written, each from saved answers of public databases and two open papers:

    data/species/ecoli.json            the species file (schema/SPECIES.md): its levels, the
                                       cell's shape and parts, and which of Cells' capabilities
                                       have a place in it
    data/proteins/atlases/ecoli.json   its side of the protein atlas (schema/SPECIES_ATLAS.md):
                                       an entry for every unit of the law inventory
    data/proteins/ecoli/               shelves.json, where each protein of UniProt's reviewed
                                       reference proteome stands against the cell's two
                                       membranes and how that is known (schema/SPECIES_PROTEINS.md,
                                       "A curated proteome"); proteins.tsv, one line per protein;
                                       and the README that explains both

Three steps, kept apart:

    python3 tools/build_ecoli_atlas.py fetch --datasets DATA
        asks the databases for what is not yet saved under DATA/ecoli/, one folder per source
        with a MANIFEST.json (address, time, SHA-256). The only step that uses the network.
        What the other species' tools saved under DATA (UniProt's vocabulary and help pages,
        InterPro's and the Gene Ontology's files, the terms of the tools behind UniProt's
        predictions) is read where it lies and never written.

    python3 tools/build_ecoli_atlas.py build --datasets DATA
        reads only DATA and the inventory snapshot, checks every file against its MANIFEST,
        and writes the files above: the same bytes every time.

    python3 tools/build_ecoli_atlas.py members --out DIR
        cuts the files of the shelves' members from the repository's two files, for the page.

The shelves are filed by the same rules as the human's and the planarian's, so that a
family has one id in every species: the machinery is tools/lib/proteome_shelves.py, which
every species' tool shares, given here this organism's own cell of two membranes and its
table of places; the families asked of every species are those of
tools/build_mpneumoniae_atlas.py, read and never changed. A change to either shows in this
tool's byte-for-byte test.

This is the viewer's reference data. Nothing of this organism is in the engine: the
project's record adds it as a data-only organism (decision D179). Requests carry a generic
client name and nothing about who asks. Standard library only.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
import build_mpneumoniae_atlas as M  # noqa: E402  the families asked of every species, read and never changed
from lib import proteome_shelves as P  # noqa: E402  the shelves' machinery: vocabulary, placement, families, districts, lines

SNAPSHOT = ROOT / "data" / "proteins" / "inventory.snapshot.json"
SPECIES_FILE = ROOT / "data" / "species" / "ecoli.json"
ATLAS_FILE = ROOT / "data" / "proteins" / "atlases" / "ecoli.json"
OUT_DIR = ROOT / "data" / "proteins" / "ecoli"
PATHS = re.compile(r"/(?:home|mnt|Users|tmp)/")
MINE = "the visualizer's E. coli agent"
TOOL = "tools/build_ecoli_atlas.py"  # named in the MANIFEST of what it downloads

SPECIES_ID = "ecoli"
LABEL = "E. coli"
ORGANISM = "Escherichia coli K-12"
TAXON = 83333            # Escherichia coli (strain K12), as UniProt's proteome names it
PROTEOME = "UP000000625"  # UniProt's reference proteome of strain K-12
GENOME = "U00096.3"      # the genome record of strain K-12 substrain MG1655
BACTERIA = 2             # the taxon every control count is asked of
UNIPROT = "https://rest.uniprot.org"
EPMC = "https://www.ebi.ac.uk/europepmc/webservices/rest"
EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"

# The dataset folders, under the folder that holds every species' downloads.
KB = "ecoli/uniprot-ecoli-k12-reviewed-proteome"
NCBI = "ecoli/ncbi-U00096.3"
PAPERS_AT = "ecoli/europepmc-open-papers"
TERMS = "ecoli/terms-ecoli-databases"
HUMAN_KB = "human/uniprot-human-reviewed-proteome"   # read only: the signatures of the units' human candidates
KB_DOCS = "human/uniprot-docs-and-terms"            # read only: UniProt's vocabulary, licence and help pages
IPR = "human/interpro-entries-tree-and-go"          # read only
GO = "human/geneontology-go-basic"                  # read only
GENBANK_TERMS = (NCBI, "terms_ncbi_genbank.html")  # NCBI's own statement on the use of GenBank data
PLACES_FILE = f"uniprotkb_{PROTEOME}_reviewed_places.json.gz"
SIGNATURES_FILE = f"uniprotkb_{PROTEOME}_reviewed_signatures.tsv.gz"
REVIEWED = f"(proteome:{PROTEOME}) AND (reviewed:true)"
PLACE_FIELDS = "accession,id,protein_name,gene_primary,gene_oln,length,protein_existence,cc_subcellular_location,ft_transmem,ft_intramem,ft_signal,ft_transit,ft_topo_dom,ft_lipid,cc_alternative_products,fragment,keyword"

# The two open papers a fact of the species file rests on, with the sentence each must hold.
PAPERS = {
    "volkmer2011": {
        "pmc": "PMC3146540", "doi": "10.1371/journal.pone.0023126", "licence": "CC BY",
        "text": "Volkmer B, Heinemann M (2011) Condition-dependent cell volume and concentration of Escherichia coli to facilitate data conversion for systems biology modeling. PLoS One 6:e23126.",
        "holds": [
            r"the average length of the rod-shaped bacterium E\. coli was determined to lie between 1\.6 and 3\.1 µm",
            r"the average width was determined as 0\.7–1\.1 µm",
            r"between 1\.6 µm for stationary cells and 3\.9 µm for cells growing on LB medium",
            r"cell width to be condition-independent \(1\.26 µm ±0\.16 µm\)",
            r"obtaining a volume range from 1\.5 to 4\.4 fl",
        ],
    },
    "urich2008": {
        "pmc": "PMC2424134", "doi": "10.1371/journal.pone.0002527", "licence": "CC BY",
        "text": "Urich T, Lanzén A, Qi J, Huson DH, Schleper C, Schuster SC (2008) Simultaneous assessment of soil microbial community structure and function through analysis of the meta-transcriptome. PLoS One 3:e2527.",
        "holds": [r"E\. coli cells have been estimated to contain between 6,800 and 72,000 ribosomes, depending on the growth phase"],
    },
    # The appendages. A paper with no text here is cited as its record at Europe PMC gives it.
    "mears2014": {"pmc": "PMC3917375", "doi": "10.7554/eLife.01916", "licence": "CC BY",
                  "holds": [r"plotted separately for different numbers of flagella per cell \( ?N flag = 1, purple; 2, blue; 3, green; 4, red; 5, cyan ?\)"]},
    "schavemaker2022": {"pmc": "PMC9323006", "doi": "10.7554/eLife.77266", "licence": "CC BY",
                        "holds": [r"a single 7\.5 µm long \( ?Turner et al\., 2000 ?\) flagellum", r"With an average number of 3\.4 flagella per E\. coli cell", r"The maximum number of stators, per flagellum, is at least 11",
                                  r"a single E\. coli flagellum contains 1 FliJ protein \(part of exporter\), 10 FliD.s \(filament cap\), 100 FlgE.s \(hook\), and 10 4 FliCs \(filament\)"]},
    "dvoriashyna2021": {"pmc": "PMC8291660", "doi": "10.1371/journal.pone.0254551", "licence": "CC BY",
                        "holds": [r"which is peritrichous, meaning that it has several flagella distributed over the cell body", r"typically O\(5–10\) μ ?m in length and 40 nm in diameter"]},
    "zhuang2025": {"pmc": "PMC11853445", "doi": "10.3390/biom15020170", "licence": "CC BY",
                   "holds": [r"a long extracellular filament approximately 20 nm in diameter, a hook about 50 nm in length"]},
    "jahnke2016": {"pmc": "PMC6274349", "doi": "10.3390/molecules21080985", "licence": "CC BY",
                   "holds": [r"extend from the cellular outer membrane \(in Gram-negative bacteria\) with prevalence of 200–500 copies per cell", r"fimbriae reach up to 1 μ ?m in length and are approximately 7–10 nm in diameter"]},
    # Read for the note's list of the motor's parts (docs/ECOLI.md); no fact of the species file rests on it.
    "nakamura2019": {"pmc": "PMC6680979", "doi": "10.3390/biom9070279", "licence": "CC BY", "use": "note",
                     "holds": [r"Diameters of the LP ring complex, the S ring, the M ring, and the C ring are ~25 nm, ~24\.5 nm, ~30 nm, and ~45 nm, respectively, in Salmonella", r"can accommodate about 10 stator units around a rotor in E\. coli and Salmonella",
                               r"The Salmonella hook is formed by about 120 copies of the hook protein FlgE", r"The MS ring is composed of the transmembrane protein FliF", r"FliG, FliM, and FliN form the C ring on the cytoplasmic face of the MS ring", r"with a 12 FliH to 6 FliI to 1 FliJ stoichiometry"]},
}
RIBOSOMES_DRAWN = 6800  # the low end of the range the paper gives

# Open papers whose numbers alone the species file takes, by the user's ruling of 16 November 2026
# (D186) that numbers from open papers may be used even where no licence is declared. Each was read
# at PubMed Central on 17 November 2026 for a limit on use in its own text, and states none; nothing
# of its text is copied, and nothing is downloaded. The file gives each number, the citation and
# where in the paper the number stands (schema/SPECIES_SHAPES.md, `envelope`). Each is named in
# the register of tests/licence_classes.test.mjs.
# By the user's ruling of 17 November 2026, numbers from papers that are free to read but not open access may be used, each with its citation.
NUMBERS_ONLY = {
    "matias2003": {
        "text": "Matias VRF, Al-Amoudi A, Dubochet J, Beveridge TJ (2003) Cryo-transmission electron microscopy of frozen-hydrated sections of Escherichia coli and Pseudomonas aeruginosa. J Bacteriol 185:6112–6118.",
        "doi": "10.1128/JB.185.20.6112-6118.2003", "url": "https://pmc.ncbi.nlm.nih.gov/articles/PMC225031/",
        "licence": "No open licence stated: the publisher's copyright (American Society for Microbiology), free to read at PubMed Central; its own text states no limit on use. Its numbers alone are taken, with the citation and their place in the paper",
        "where": "Table 1, the row for E. coli K-12: the five widths, each the mean of eight measurements, made on the least deformed regions of the sections (as its methods say), and the periplasm's average compression in the sections, 32.47%",
    },
    "berry2010": {
        "text": "Berry J, Savva C, Holzenburg A, Young R (2010) The lambda spanin components Rz and Rz1 undergo tertiary and quaternary rearrangements upon complex formation. Protein Sci 19:1967–1977.",
        "doi": "10.1002/pro.485", "url": "https://pmc.ncbi.nlm.nih.gov/articles/PMC2998730/",
        "licence": "No open licence stated: the publisher's copyright (The Protein Society), free to read at PubMed Central; its own text states no limit on use. Its numbers alone are taken, with the citation and their place in the paper",
        "where": "the legend of Figure 7: the distance between the inner and outer membranes at the mid-length of 31 cells of K-12, 25.5 ± 3.1 nm",
    },
}
NUMBERS_READ = "2026-11-17"
# The envelope's widths in nanometres, as Matias and others 2003 give them in Table 1 for E. coli K-12, each the
# mean of eight measurements made on the least deformed regions of the sections: the plasma (inner) membrane's
# thickness, the peptidoglycan's (the wall), the outer membrane's, the periplasm's width (between the two membranes),
# and the distance from the wall to the outer membrane. The paper does not say between which faces the last two run:
# this viewer reads them as between the facing surfaces, and the fact says so.
ENVELOPE = {"membrane_nm": 5.84, "wall_nm": 6.35, "outer_nm": 6.87, "between_nm": 20.99, "wall_to_outer_nm": 5.34}

SOURCES = {
    KB: {
        "what": f"UniProtKB: every reviewed entry of the reference proteome {PROTEOME} of Escherichia coli K-12 with its name, gene, locus, length, level of evidence, keywords, stated subcellular locations with the evidence for each, membrane-spanning segments, signal peptides and lipid anchors; the InterPro entries and Gene Ontology terms UniProt gives each; the proteome's own record; counts of its entries; and, for each family signature asked, how many reviewed entries of bacteria carry it",
        "licence": "CC BY 4.0",
    },
    NCBI: {"what": f"NCBI's summary of the genome record {GENOME} (Escherichia coli K-12 substrain MG1655): its title, length and topology; and GenBank's statement on the use of its data. No sequence was downloaded", "licence": "NCBI places no restrictions on the use or distribution of the GenBank data"},
    TERMS: {"what": "The pages on which two databases of this organism state their terms, read before deciding that nothing is taken from them: BioCyc's page on downloads (for EcoCyc) and the front page of STEPdb", "licence": "Each page is its owner's: kept as the record of what was read"},
    PAPERS_AT: {"what": "Open papers from Europe PMC, each as its record there (with its licence) and its full text: for the cell's size and volume, the number of its ribosomes, its flagella and its fimbriae, and the parts of the flagellar motor", "licence": "CC BY, each as its record at Europe PMC states"},
}


# The organism's own databases, read for their terms and pointed to: nothing is taken from them.
POINTERS = [
    {"name": "EcoCyc", "url": "https://ecocyc.org/", "page": "https://biocyc.org/download.shtml", "file": "biocyc_download.html", "contains": "BioCyc",
     "must": r"Access to the BioCyc data files requires a paid BioCyc subscription", "none_of": None,
     "licence": "No open licence stated: its page on downloads says that access to the data files requires a paid subscription",
     "holds": "Nothing is taken from it: a pointer to the curated database of this strain's genes, proteins, pathways and regulation, where a reader finds what curators say of each protein beyond its place."},
    {"name": "STEPdb", "url": "https://stepdb.eu/", "page": "https://stepdb.eu/", "file": "stepdb_home.html", "contains": "STEPdb",
     "must": r"All datasets are freely available for download", "none_of": r"(?i)licen[cs]e|terms of use|copyright|commercial|creative commons",
     "licence": "No open licence stated: its page says that all datasets are freely available for download, and states no terms of use",
     "holds": "Nothing is taken from it: a pointer to a database of where each protein of this strain is found (the cytoplasm, the inner membrane, the periplasm, the outer membrane, outside the cell), gathered from experiments, the literature and curated prediction."},
]


# ---------------------------------------------------------------------------------------
# The table: which shelf and which side a stated place stands for, in a cell with two membranes
# ---------------------------------------------------------------------------------------
#
# The inner membrane's shelf comes first, as the contract has it for the mitochondrion's two
# membranes: what lies between the two membranes is beyond the inner one (its "outside"),
# and a protein held at the outer membrane and facing that space is on the outer shelf's
# "inside". A protein free in the periplasm therefore stands on the inner shelf, outside.

SHELVES = [
    {"id": "inner", "label": "Cell inner membrane", "outside": "In the periplasm, between the cell's two membranes", "inside": "Inside the cell: in the cytoplasm"},
    {"id": "outer", "label": "Cell outer membrane", "outside": "Outside the cell", "inside": "On the periplasmic face of the outer membrane"},
    {"id": "membrane", "label": "A membrane, not told which", "outside": "Beyond the inner membrane: in the periplasm, at the outer membrane or outside the cell", "inside": "On the cytoplasmic side of a membrane"},
]
M_, IN_, OUT_, WHOLE_, REGION_, ELSE_ = P.MEMBRANE, P.INSIDE, P.OUTSIDE, P.WHOLE, P.REGION, P.ELSEWHERE
PLACES = {
    "Cell inner membrane": ("inner", M_),
    "Cell membrane": ("inner", M_),                  # the vocabulary: "Known as the cell inner membrane in prokaryotes with 2 membranes"
    "Cytoplasm": ("inner", IN_),
    "Bacterial microcompartment": ("inner", IN_),    # the vocabulary: shells of protein that enclose enzymes, in the cytoplasm
    "Periplasm": ("inner", OUT_),                    # the vocabulary: "the space between the inner and outer membrane in Gram-negative bacteria"
    "Cell wall": ("inner", OUT_),                    # the vocabulary: the wall "is surrounded by the outer membrane" in such bacteria: it lies between the two
    "Cell outer membrane": ("outer", M_),
    "Secreted": ("outer", OUT_),
    "Fimbrium": ("outer", OUT_),                     # the vocabulary: an appendage that extends from the cell surface
    "Cell surface": ("outer", WHOLE_),               # the vocabulary: "the outermost side of the cell"; in the membrane or on it is not said
    "Bacterial flagellum": ("outer", REGION_),       # its filament and hook lie outside, its basal body reaches through both membranes: the words give no side
    "Bacterial flagellum basal body": ("inner", REGION_),  # this file's reading: the rod and rings start at the inner membrane; which part a protein is in is not said
    "Membrane": ("membrane", M_),
    "Endomembrane system": ("membrane", M_),
    "Host cell membrane": (None, ELSE_),
}
FACES = {
    "Cytoplasmic side": {"inner": "inside", "membrane": "inside"},
    "Periplasmic side": {"inner": "outside", "outer": "inside", "membrane": "outside"},  # of either membrane, the periplasm lies beyond the inner one
    "Extracellular side": {"outer": "outside", "membrane": "outside"},
}
# Where an exported protein ends up: beyond the inner membrane. Of the outer membrane it is not told.
AWAY = {"inner": "outside", "membrane": "outside"}
PEPTIDOGLYCAN_ANCHOR = "SL-9900"  # bound to the wall: it does not span a membrane
LIPID_ANCHOR = "SL-9901"
# The rules that place a protein, in the order they are tried, in this organism's words.
RULES_SAID = {
    "place": "The place itself is on one side: the cytoplasm, the periplasm, or outside the cell.",
    "spans": "The entry states that the protein spans the membrane (single-pass or multi-pass).",
    "face": "The entry states which face of the membrane the protein is on.",
    "anchor": "The entry states an anchor that holds a protein on the face away from the cytoplasm, and no face. No entry of this organism states one.",
    "later part": "The first place names no side, and a later statement of the same entry names a part of that place and gives the side.",
    "segment": "The entry states the membrane and not the side, and it carries a membrane-spanning segment: in the membrane.",
    "signal": "The entry states the inner membrane, or a membrane it does not name, and not the side, and it carries a signal peptide and no membrane-spanning segment: beyond the inner membrane. Of a protein stated at the outer membrane a signal peptide settles nothing, since every such protein has crossed the inner membrane.",
    "no place: segment": "No place of the cell is stated, and the entry carries a membrane-spanning segment: in a membrane, not told which.",
    "no place: signal": "No place of the cell is stated, and the entry carries a signal peptide and no segment: beyond the inner membrane, and how far is not told.",
    "side not stated": "The entry states the membrane or the place, and nothing in it settles the side.",
    "no place": "No place of the cell is stated and nothing is predicted: on no shelf.",
}
# The families of a unit that only go with its machine: a regulator, or a subunit that forms
# no channel or pump by itself. A unit is found where a protein carries the signature of one
# of its other families; a protein with only such a family's signature is no candidate.
ACCESSORY = P.ACCESSORY

# The assemblies a protein belongs to (the contract's mark `complex`), by the Gene Ontology's
# cellular-component terms as UniProt gives them to an entry, with every narrower term.
COMPLEXES = [
    ("flagellum", "GO:0009288", "bacterial-type flagellum"),
    ("chemoreceptor array", "GO:0098561", "methyl accepting chemotaxis protein complex"),
    ("ribosome", "GO:0005840", "ribosome"),
    ("RNA polymerase", "GO:0000428", "DNA-directed RNA polymerase complex"),
    ("ATP synthase", "GO:0045259", "proton-transporting ATP synthase complex"),
]
CHEMOTAXIS_KEYWORD = "Chemotaxis"
P_TYPE = "IPR001757"   # P-type ATPases, the wider family of the animal ion pumps
F_ATPASE = "IPR000194"  # the nucleotide-binding domain of the ATP synthase's alpha and beta subunits
MARKED = ["chemotaxis", "complex"]  # the marks whose holders the file also lists by line (highlights)
EXISTENCE = {1: "evidence at protein level", 2: "evidence at transcript level", 3: "inferred from homology", 4: "predicted", 5: "uncertain"}
TABLE_COLUMNS = [*P.TABLE_COLUMNS, "locus", "chemotaxis", "complex"]
UPSTREAM = ["PROSITE", "HAMAP", "TMHMM", "Phobius", "SignalP", "TargetP", "Memsat", "Predotar"]
# The cell the shared machinery places this organism's proteins in. A protein bound to the
# wall by an anchor does not span a membrane.
CELL = P.Cell(SHELVES, PLACES, FACES, AWAY, not_spanning={"SL-9901", "SL-9903", PEPTIDOGLYCAN_ANCHOR})


# ---------------------------------------------------------------------------------------
# Fetch
# ---------------------------------------------------------------------------------------

def signatures_asked():
    asked = [signature for family in M.FAMILIES.values() for signature in family["signatures"]] + list(M.BACTERIAL_CHANNELS) + [M.PROTEASOME, P_TYPE, F_ATPASE]
    return sorted(set(asked))


def requests():
    out = []

    def add(source, file, url, purpose, **more):
        out.append({"source": source, "file": file, "url": url, "purpose": purpose, **more})

    q = P.q
    stream = f"{UNIPROT}/uniprotkb/stream?query={q(REVIEWED)}&compressed=true"
    add(KB, PLACES_FILE, f"{stream}&format=json&fields={PLACE_FIELDS}", "every reviewed entry of the proteome: its name, gene, locus, length, level of evidence and keywords, where the entry places it and on what evidence, its membrane-spanning segments, signals and lipid anchors", gzip=True)
    add(KB, SIGNATURES_FILE, f"{stream}&format=tsv&fields=accession,xref_interpro,go_id", "the InterPro entries and the Gene Ontology terms UniProt gives each reviewed entry", gzip=True)
    count = lambda query, more="": f"{UNIPROT}/uniprotkb/search?query={q(query)}&size=1&fields=accession&format=json{more}"
    add(KB, "count_reviewed.json", count(REVIEWED), "how many reviewed entries the proteome holds (the count is in the answer's header)")
    add(KB, "count_reviewed_with_isoforms.json", count(REVIEWED, "&includeIsoform=true"), "how many sequences the reviewed entries describe when each isoform is counted")
    add(KB, "count_unreviewed.json", count(f"(proteome:{PROTEOME}) AND (reviewed:false)"), "how many unreviewed entries the proteome holds")
    add(KB, "count_all.json", count(f"(proteome:{PROTEOME})"), "how many entries the proteome holds in all")
    add(KB, "count_reviewed_with_place.json", count(f"{REVIEWED} AND (cc_scl_term:*)"), "how many reviewed entries state a subcellular location, by UniProt's own search")
    add(KB, f"proteome_{PROTEOME}.json", f"{UNIPROT}/proteomes/{PROTEOME}", "the proteome's own record: its description, its counts and its genome assembly")
    for signature in signatures_asked():
        add(KB, f"count_bacteria_{signature}.json", count(f"(xref:interpro-{signature}) AND (taxonomy_id:{BACTERIA}) AND (reviewed:true)"), f"the control for {signature}: how many reviewed entries of bacteria carry it")
    add(NCBI, f"genbank_{GENOME}_summary.json", f"{EUTILS}/esummary.fcgi?db=nuccore&id={GENOME}&retmode=json", "the genome record's title, length and topology", contains='"slen"')
    add(NCBI, GENBANK_TERMS[1], "https://www.ncbi.nlm.nih.gov/genbank/", "GenBank's statement on the use of its data", contains="GenBank Overview")
    for pointer in POINTERS:
        add(TERMS, pointer["file"], pointer["page"], f"{pointer['name']}: the page on which its terms were read, before deciding that nothing is taken from it", contains=pointer["contains"])
    for key, paper in PAPERS.items():
        add(PAPERS_AT, f"{key}_record.json", f"{EPMC}/search?format=json&resultType=core&query=PMCID:{paper['pmc']}", "the paper's record at Europe PMC, with its licence", contains=paper["pmc"])
        add(PAPERS_AT, f"{key}_fulltext.xml", f"{EPMC}/{paper['pmc']}/fullTextXML", "the paper's full text", contains="<article")
    return out


def fetch(datasets, refresh=False):
    """Ask every request whose file is not yet saved, by the downloader the species' tools share."""
    return P.fetch(datasets, requests(), SOURCES, MINE, TOOL, refresh=refresh)


# ---------------------------------------------------------------------------------------
# Build
# ---------------------------------------------------------------------------------------

listed, plural = P.listed, P.plural
paper_text = lambda d, key: P.paper_text(d, PAPERS_AT, PAPERS, key)
paper_cite = lambda d, key: P.paper_cite(d, PAPERS_AT, PAPERS, key)


def check_terms(d):
    """Each source's terms, read in its own saved page before anything of it is used."""
    must = lambda source, file, pattern, field=None: P.holds(d, source, file, pattern, field)

    must(KB_DOCS, "terms_uniprot_license.json", r"We have chosen to apply the \[?Creative Commons Attribution 4\.0 International \(CC BY 4\.0\) License\]?(\([^)]*\))? to all copyrightable parts of our databases", field="content")
    must(IPR, "terms_interpro_license.html", r"All of the InterPro, Pfam, PRINTS and SFLD downloadable data provided on the InterPro website is freely available under CC0 1\.0 Universal")
    must(GO, "go_citation_policy.html", r"licensed under the Creative Commons Attribution 4\.0 Unported License")
    must(*GENBANK_TERMS, r"NCBI places no restrictions on the use or distribution of the GenBank data")
    must(*P.SAVED_TERMS["prosite"], r"distributed under the Creative Commons Attribution-NonCommercial-NoDerivatives \(CC BY-NC-ND 4\.0\) License")
    must(*P.SAVED_TERMS["hamap"], r"HAMAP is copyrighted by the SIB Swiss Institute of Bioinformatics and distributed under the Creative Commons Attribution \(CC BY 4\.0\) License")
    for tool in ("tmhmm", "signalp", "targetp"):
        must(*P.SAVED_TERMS[tool], rf"ACADEMIC SOFTWARE LICENSE AGREEMENT FOR END-USERS AT PUBLICLY FUNDED ACADEMIC, EDUCATION OR RESEARCH INSTITUTIONS FOR THE USE OF {tool}")
    must(*P.SAVED_TERMS["phobius"], r"Phobius is intended for academic users only")
    must(KB_DOCS, "help_transmem.json", r"predicted by the application of the predictive tools TMHMM, Memsat, Phobius and the hydrophobic moment plot method of Eisenberg and coworkers", field="content")
    must(KB_DOCS, "help_signal.json", r"predicted by the application of the predictive tools Phobius, Predotar, SignalP and TargetP\. At least two methods must return a positive signal peptide prediction", field="content")
    for pointer in POINTERS:
        text = P.plain(d.text(TERMS, pointer["file"]))
        if not re.search(pointer["must"], text) or (pointer["none_of"] and re.search(pointer["none_of"], text)):
            raise SystemExit(f"{pointer['name']}: its page no longer states its terms as they were read; read it again and class it again")


def unit_tail(parts, own):
    """The sentence that closes a unit's note, by what the unit is."""
    if any(part in ("connexin", "innexin") for part in parts):
        return "Gap junctions join the neighbouring cells of a tissue, and this organism lives as single cells."
    if any(part in ("serca", "ip3r", "ryr") for part in parts):
        return "No entry of its proteome states a place in an endoplasmic reticulum, the store this machine sits in."
    if "mcu" in parts:
        return "It is a bacterium: no entry of its proteome states a place in a mitochondrion."
    if any(part in ("nka_alpha", "pmca") for part in parts):
        return f"The wider family, the P-type ATPases, has {plural(len(own['p_type']), 'member')} here ({listed(own['p_type'])}), listed under extra; none carries this signature."
    if any(part in ("kcc", "nkcc", "ncx") for part in parts):
        return "Its own transporters are in its protein catalogue."
    return f"Its own ion channels are of bacterial families that no unit of the inventory stands for: {own['channels']} proteins, listed under extra."


def vocabulary_says(d, sentences):
    """UniProt's vocabulary of places still holds the sentences this file's words rest on."""
    text = re.sub(r"\s+", " ", re.sub(r"\nDE   ", " ", d.text(KB_DOCS, "subcell.txt")))
    for sentence in sentences:
        if sentence not in text:
            raise SystemExit(f"UniProt's vocabulary of places no longer says: {sentence}")


def build(datasets_folder, snapshot):
    d = P.Datasets(datasets_folder)
    check_terms(d)
    vocabulary = P.Vocabulary(d, KB_DOCS, CELL)
    vocabulary_says(d, [
        "Known as the cell inner membrane in prokaryotes with 2 membranes.",
        "separates the cytoplasm from the periplasm in prokaryotes with 2 membranes.",
        "separates the prokaryotic periplasm from its cell surroundings.",
        "The periplasm is the space between the inner and outer membrane in Gram-negative bacteria.",
        "is surrounded by the outer membrane in bacteria with 2 membranes",
        "plays a role in cell shape, cell stability",
        "is not surrounded by a membrane.",
    ])
    entries, read = P.read_reviewed(d, KB, PLACES_FILE, vocabulary)
    # This file's reading: a lipid-anchored protein whose entry says "Cell membrane", with no
    # experiment behind the statement, stands on the shelf of a membrane that is not named.
    anchored = Counter()
    for entry in entries.values():
        for index, statement in enumerate(entry["statements"]):
            if statement["topology"] != LIPID_ANCHOR:
                continue
            anchored[statement["name"]] += index == 0
            if statement["name"] == "Cell membrane" and statement["evidence"] != "experiment":
                statement["shelf"] = "membrane"
    filing = P.Filing(d, entries, KB, SIGNATURES_FILE, IPR, GO)
    placed = {accession: P.place(entry, vocabulary) for accession, entry in entries.items()}
    moved = [accession for accession, item in placed.items() if item["where"] and item["where"]["name"] == "Cell membrane" and item["where"]["topology"] == LIPID_ANCHOR and item["shelf"] == "membrane"]
    moved_behind = Counter(placed[accession]["where"]["evidence"] for accession in moved)
    if set(moved_behind) - {"rule", "curator", "similarity", P.NOT_GIVEN}:
        raise SystemExit(f"a lipid anchor at the cell membrane has evidence this file does not expect: {dict(moved_behind)}")
    said_places = {statement["words"] for entry in entries.values() for statement in entry["statements"]}
    for absent in ("Endoplasmic reticulum", "Golgi", "Mitochondrion", "Nucleus"):
        if any(absent in words for words in said_places):
            raise SystemExit(f"an entry states a place in the {absent}; the species file says that none does")
    raw = {item["primaryAccession"]: item for item in json.loads(d.text(KB, PLACES_FILE))["results"]}
    release = d.entry(KB, PLACES_FILE)["x_uniprot_release"]
    proteome = json.loads(d.text(KB, f"proteome_{PROTEOME}.json"))
    stated = {"reviewed": d.total(KB, "count_reviewed.json"), "sequences": d.total(KB, "count_reviewed_with_isoforms.json"), "unreviewed": d.total(KB, "count_unreviewed.json"), "all": d.total(KB, "count_all.json"), "with_place": d.total(KB, "count_reviewed_with_place.json"), "genes": proteome["geneCount"]}
    if any(d.entry(KB, file)["x_uniprot_release"] != release for file in (SIGNATURES_FILE, "count_reviewed.json", "count_reviewed_with_isoforms.json", "count_unreviewed.json", "count_all.json", "count_reviewed_with_place.json")) or vocabulary.release != release:
        raise SystemExit("the downloads from UniProt are not of one release; fetch them again")
    if stated["reviewed"] != len(entries) or stated["sequences"] != sum(entry["isoforms"] for entry in entries.values()) or stated["with_place"] != read["entries that state a place"] or stated["reviewed"] + stated["unreviewed"] != stated["all"] or proteome["proteinCount"] != stated["all"] or proteome["taxonomy"]["taxonId"] != TAXON:
        raise SystemExit(f"the entries read do not add up to UniProt's own counts: {stated}")
    gene = lambda accession: entries[accession]["gene"] or accession
    by_gene = lambda accessions: sorted((gene(a) for a in accessions), key=lambda name: P.natural(name.lower()))
    locus = {a: next((name["value"] for g in item.get("genes") or [] for name in g.get("orderedLocusNames") or [] if name["value"].startswith("b")), "") for a, item in raw.items()}
    keywords = {a: {word["name"] for word in item.get("keywords") or []} for a, item in raw.items()}

    # --- the marks: chemotaxis by UniProt's keyword, the assemblies by the Gene Ontology -------
    for word, term, name in COMPLEXES:
        if filing.terms.get(term, {}).get("name") != name:
            raise SystemExit(f"the ontology no longer calls {term} {name!r}; choose the assemblies' terms again")
    complex_of = {}
    for accession in entries:
        terms = set()
        for term in filing.entry_terms[accession]:
            usable = filing.usable(term)
            if usable:
                terms |= filing.up(usable)
        hit = next((word for word, term, _ in COMPLEXES if term in terms), None)
        if hit:
            complex_of[accession] = hit
    chemotaxis = {a for a, words in keywords.items() if CHEMOTAXIS_KEYWORD in words}
    wanted = {"cheA", "cheW", "cheY", "cheZ", "cheR", "cheB", "tsr", "tar", "trg", "tap", "aer", "motA", "motB", "fliG", "fliM", "fliN"}
    if wanted - {gene(a) for a in chemotaxis}:
        raise SystemExit(f"UniProt's keyword no longer marks the chemotaxis proteins this file promises: {sorted(wanted - {gene(a) for a in chemotaxis})}")

    # --- the atlas: the families behind Cells' units, asked of this organism ---------------------
    carriers = filing.carriers()
    control = {signature: d.total(KB, f"count_bacteria_{signature}.json") for signature in signatures_asked()}
    human_signatures = P.human_signatures(d, HUMAN_KB)
    order = lambda accessions: sorted(set(accessions), key=lambda a: P.natural(gene(a).lower()))
    channel_hits = {signature: by_gene(carriers.get(signature, [])) for signature in M.BACTERIAL_CHANNELS}
    channels = order(accession for signature in M.BACTERIAL_CHANNELS for accession in carriers.get(signature, []))
    channels_said = "; ".join(f"{what} ({listed(channel_hits[signature])})" for signature, what in M.BACTERIAL_CHANNELS.items() if channel_hits[signature])
    own = {"p_type": by_gene(carriers.get(P_TYPE, [])), "channels": len(channels)}
    signature_name = lambda signature: filing.names[signature]["name"]
    carried = lambda family: order(accession for signature in family["signatures"] for accession in carriers.get(signature, []))
    units, beside = {}, {}  # beside: a protein with only an accessory family's signature -> [the family, the units that asked]
    for unit in snapshot["units"]:
        spec = M.UNITS[unit["id"]]
        if spec.get("finding"):
            if unit.get("products"):
                raise SystemExit(f"{unit['id']} has candidates in the inventory; it cannot be '{spec['finding']}'")
            units[unit["id"]] = {"finding": spec["finding"], "note": NOTHING[unit["id"]](own, channel_hits), "products": []}
            continue
        families = [(key, M.FAMILIES[key]) for key in spec["parts"]]
        signatures = [signature for _, family in families for signature in family["signatures"]]
        candidates = [product["human_uniprot"] for product in unit.get("products") or [] if product.get("human_uniprot")]
        for _, family in families:
            if family.get("human", True) and not any(set(family["signatures"]) & human_signatures.get(candidate, set()) for candidate in candidates):
                raise SystemExit(f"{unit['id']}: none of its human candidates carries the signature of {family['of']}; the question is not the unit's")
        makers = [family for key, family in families if key not in ACCESSORY]
        found = order(accession for family in makers for accession in carried(family))
        if found or not makers:
            # No unit's own family is carried by a protein of this organism today. If one is, the entry,
            # its products and the species file's sentences on channels and pumps are to be written for it.
            raise SystemExit(f"{unit['id']}: {by_gene(found)} carry the signature of the family that makes this machine; this tool writes no such entry yet")
        only = [(family, carried(family)) for key, family in families if key in ACCESSORY and carried(family)]
        many = len(signatures) > 1
        elsewhere = sum(control[signature] for signature in signatures)
        said = f"Among the reviewed UniProtKB entries of all bacteria, {plural(elsewhere, 'entry carries', 'entries carry')} {'one of the signatures asked' if many else 'it'}." if elsewhere else f"No reviewed UniProtKB entry of any bacterium carries {'any of the signatures asked' if many else 'it'} either."
        proof = f" The unit's human candidates carry {'them' if sum(len(family['signatures']) for _, family in families if family.get('human', True)) > 1 else 'it'}, so the search finds the family where it exists."
        if only:
            asked = f"the signature of {listed(family['of'] for family in makers)} ({', '.join(signature for family in makers for signature in family['signatures'])}), the family that makes the machine itself"
            aside = " ".join(
                f"{plural(len(hits), 'protein')} ({listed(by_gene(hits))}) carr{'ies' if len(hits) == 1 else 'y'} that of {family['of']} ({', '.join(signature for signature in family['signatures'] if carriers.get(signature))}), which go with the machine and make none by themselves: with nothing to go with, {'it is' if len(hits) == 1 else 'they are'} no candidate for the unit, and {'is' if len(hits) == 1 else 'are'} listed under extra."
                for family, hits in only
            )
            note = f"None of the {len(entries):,} proteins of its reference proteome carries {asked}. {aside} {said}{proof}"
            for family, hits in only:
                for accession in hits:
                    beside.setdefault(accession, [family, []])[1].append(unit["id"])
        else:
            asked = f"the signature of {listed(family['of'] for _, family in families)} ({', '.join(signatures)})"
            note = f"None of the {len(entries):,} proteins of its reference proteome carries {asked}. {said}{proof} {unit_tail(spec['parts'], own)}"
        units[unit["id"]] = {"finding": "none found", "note": note, "products": []}
    if set(units) != {unit["id"] for unit in snapshot["units"]}:
        raise SystemExit("the units of the atlas are not the units of the inventory")
    unit_ids = {}  # no protein of this organism is a candidate for a unit: none is drawn as one

    # The organism's own membrane machines that bear on what the atlas draws and match no unit.
    extra, seen_extra = [], set()

    def add_extra(accession, role, signature, why, found_by=P.FOUND_SIGNATURE):
        if accession in seen_extra:
            return
        seen_extra.add(accession)
        entry = entries[accession]
        # Found by the signature named; every entry of this catalogue is a reviewed one.
        extra.append({"name": entry["name"], "gene": entry["gene"] or None, "role": role, "ids": [{"db": "uniprot", "id": accession}], "length": entry["length"], "found_by": found_by, "entry": P.ENTRY_REVIEWED, "evidence_note": f"Its reviewed UniProtKB entry names it \"{entry['name']}\", with UniProt's level of evidence \"{EXISTENCE[entry['seen']]}\". The entry carries {signature} ({signature_name(signature)}).", "citation": None, "why": why})

    for signature, what in M.BACTERIAL_CHANNELS.items():
        for accession in order(carriers.get(signature, [])):
            add_extra(accession, "channel", signature, f"Carries the signature of {what}. The law inventory has no unit for this family; it is one of the cell's own channels.")
    for accession in order(carriers.get(P_TYPE, [])):
        add_extra(accession, "ion pump", P_TYPE, "A P-type ATPase, of the wider family of the animal ion pumps; it carries the signature of neither the sodium-potassium pump nor the calcium pumps that the inventory has units for.")
    for accession in order(carriers.get(F_ATPASE, [])):
        if complex_of.get(accession) == "ATP synthase":
            add_extra(accession, "catalytic head", F_ATPASE, "Part of the cell's F-type ATP synthase, which sits in its inner membrane. The law inventory has no F-type ATPase.")
    for accession in order(beside):
        family, asked_by = beside[accession]
        signature = next(signature for signature in family["signatures"] if accession in carriers.get(signature, []))
        add_extra(accession, "accessory-subunit family", signature, found_by=P.FOUND_ACCESSORY, why=f"Carries the family signature of {family['of']}, which go with a channel and make none by themselves. No protein of this organism carries the signature of a family that makes such a channel, so it is a candidate for no unit ({asked_by[0]} to {asked_by[-1]} asked for it).")

    # --- the lines of the shelves ---------------------------------------------------------------
    lines, alone, rest = P.make_lines(entries, placed, filing, unit_ids, CELL)
    sequence = P.in_order(entries, lines, alone, rest)
    NO_SHELF = P.NO_SHELF
    key = lambda shelf: NO_SHELF if shelf is None else shelf
    shelf_counts, counts, bases, rules, evidence = P.counted(placed, CELL)
    family_total = Counter(filing.family.values())
    distinct = len({line["id"] for line in lines})
    lone_families = sum(1 for count in family_total.values() if count <= P.LONE_UP_TO)
    plain_words = sum(1 for item in placed.values() if item["where"] and item["where"]["name"] == "Cell membrane" and item["shelf"] == "inner")
    unnamed = sum(1 for item in placed.values() if item["where"] and item["shelf"] == "membrane" and item["where"]["name"] != "Cell membrane")
    behind_moved = "; ".join(f"{what}: {moved_behind[word]}" for word, what in (("rule", "a rule of PROSITE or HAMAP"), ("curator", "a curator's inference"), ("similarity", "likeness to another protein"), (P.NOT_GIVEN, "no evidence given")) if moved_behind[word])
    shelf_notes = {
        "inner": f"Here stand also the {plain_words} proteins whose entry says \"Cell membrane\" and not which: UniProt's vocabulary says that the cell membrane is known as the inner membrane where a cell has two. The lipid-anchored ones among them stand on the shelf of a membrane that is not named.",
        "outer": "On its inside stand only proteins that an entry places at the outer membrane's periplasmic face. A protein free in the periplasm stands on the inner membrane's shelf, on its outside.",
        "membrane": f"Three kinds of protein. The {unnamed} that an entry places in a membrane without naming it. The {len(moved)} lipid-anchored ones whose entry says \"Cell membrane\" with no experiment behind the statement ({behind_moved}): this file reads those words as not telling which membrane, since an entry that tells the membrane of a lipid-anchored protein names it, \"Cell inner membrane\" in {anchored['Cell inner membrane']} entries and \"Cell outer membrane\" in {anchored['Cell outer membrane']}. And the {rules['no place: signal'] + rules['no place: segment']} with no stated place whose entry carries a signal peptide: such a protein was carried across the inner membrane, and how far beyond it is not told.",
    }
    shelves, no_shelf = P.shelf_rows(CELL, shelf_counts, lines, alone, rest, notes=shelf_notes)
    groups = P.district_rows(lines, alone)
    places, place_words, first_places, used = P.place_rows(entries, placed, vocabulary)

    # What stands between the two membranes, by the rule this file builds by.
    on = lambda shelf, side, rule=None: sum(1 for item in placed.values() if item["shelf"] == shelf and item["side"] == side and (rule is None or (item["rule"] == "place") == rule))
    between = {
        "free in the periplasm or in the wall: the inner membrane's shelf, outside": on("inner", "outside", True),
        "held at the inner membrane and facing the periplasm: the inner membrane's shelf, outside": on("inner", "outside", False),
        "held at the outer membrane and facing the periplasm: the outer membrane's shelf, inside": on("outer", "inside"),
        "beyond the inner membrane, in a place that is not told: the shelf of a membrane that is not named, outside": on("membrane", "outside"),
    }

    resting, rule_ids = P.account(entries, placed)
    signal_on = Counter(item["shelf"] for item in placed.values() if item["rule"] == "signal")
    if set(signal_on) - {"inner", "membrane"} or rules["no place: segment"]:
        raise SystemExit("a signal peptide or a segment places a protein where the file's words do not say")
    if set(resting) - {"PROSITE-ProRule", "HAMAP-Rule", "RuleBase", "segments", "signal", "unnamed analysis"}:
        raise SystemExit(f"a placement rests on a rule system or an analysis the sources do not name: {sorted(resting)}")
    of = lambda owner, what="placements": resting.get(owner, {}).get(what, 0)
    PLACE, SPANS, FACE, FROM_SEGMENTS, FROM_SIGNAL = P.ON_PLACE, P.ON_SPANS, P.ON_FACE, P.FROM_SEGMENTS, P.FROM_SIGNAL

    made = d.last_day()
    header = {
        "format": P.SHELF_FORMAT,
        "species": SPECIES_ID,
        "made": made,
        "from": f"UniProtKB release {release}: the {stated['reviewed']:,} reviewed entries of the reference proteome {PROTEOME} of Escherichia coli strain K-12, one protein each; with the other forms that {sum(1 for entry in entries.values() if entry['isoforms'] > 1)} of them describe, {stated['sequences']:,} sequences. The proteome holds {plural(stated['unreviewed'], 'unreviewed entry', 'unreviewed entries')}: every protein of it is listed, for {stated['genes']:,} genes.",
        "from_counts": {"reviewed": stated["reviewed"], "isoforms": stated["sequences"] - stated["reviewed"], "sequences": stated["sequences"], "unreviewed": stated["unreviewed"], "entries": stated["all"], "genes": stated["genes"], "state_a_place": stated["with_place"]},
        "predicted": False,
        "shelves": shelves,
        "no_shelf": no_shelf,
        "between": {"rule": "A protein free in the space between the two membranes (the periplasm, and the wall that lies in it) stands on the inner membrane's shelf, on its outside. A protein held at a membrane and facing that space stands on that membrane's shelf, on the side that faces the space: the outside of the inner shelf, the inside of the outer. A protein known only to lie beyond the inner membrane stands on the outside of the shelf of a membrane that is not named.", "counts": between},
        "groups": groups,
        "groups_from": "A protein's Gene Ontology terms are those InterPro maps to any of its signatures and those UniProt gives its entry. With every broader term (by the ontology's kind-of and part-of links), the protein falls in the first district, in the order listed, one of whose terms it carries. A family's line stands in the district most of its classed members on that shelf fall in; of equal counts, the first listed. A protein that is the only member of its family stands in its own district. A part of no_family is a looser grouping: it stands in a district only if more than half of all its members on that shelf fall there. The choice of the districts' terms and their order is the viewer's, and is the planarian's and the human's.",
        "family_from": f"A family is an InterPro entry of the type Family (InterPro {filing.release}). A protein is filed under the narrowest family among the InterPro entries UniProt gives it: one that is not a broader kind of another it carries, by InterPro's tree of entries. Where several unrelated families remain ({filing.several:,} proteins), it is the deepest in that tree, then the one fewest proteins of this catalogue are in, then the first by accession. This is the rule of the planarian's and the human's files, so a family has the same id in each.",
        "family_columns": P.FAMILY_COLUMNS,
        "family_notes": {
            "lines": "A family has one line for each shelf that holds members of it, and one with a null shelf for its members that are on no shelf. A line is identified by id and shelf together; side, group, count, sides, file, at and units are of its members on that shelf alone.",
            "side": "The side most of the line's members sit on; of equal counts, a membrane first.",
            "units": P.UNITS_NOTE,
            "total": "The family's members on every shelf and on none.",
            "counts": "distinct_families is the number of families that have lines; families_in_all counts also the families of one, whose proteins are under 'lone'. In 'shelves' and 'no_shelf', 'families' is every family with a member there (its lines and its lone proteins), 'lines' the families' lines there, 'lone' the proteins that are the only member of their family, 'no_family' those with none.",
        },
    }
    lone = P.lone_block(alone, lone_families)
    no_family = P.no_family_block(filing, placed)
    files = sorted({line["file"] for line in [*lines, *alone, *rest]})
    complexes_said = {word: by_gene(a for a, found in complex_of.items() if found == word) for word, _, _ in COMPLEXES}
    tail = {
        "member_columns": P.MEMBER_COLUMNS,
        "members_from": {
            "table": f"data/proteins/{SPECIES_ID}/{P.TABLE_FILE}",
            "format": P.MEMBERS_FORMAT,
            "order": "The table's lines are the members in order: every line of the families as listed here, then every part of 'lone', then every part of 'no_family'; within each, by gene name. A line's members are the next 'count' lines of the table. For a family's line and for a part of no_family, 'under' is its id and 'shelf' its shelf (empty for none); for a part of 'lone', 'under' is the protein's own family and 'family' that family's name.",
            "files": f"A file holds the members of consecutive lines: a new file begins where the next line would take it past {P.MEMBERS_PER_FILE:,} members, so a line is never split. 'file' names the file and 'at' the first and one past the last of its members there. A member's shelf is its line's.",
            "places": "In the table a stated place is written with UniProt's identifiers, without their prefix: the place, then the topology and the face where the entry states them, joined by a full stop (0037.9909 is SL-0037 with SL-9909). 'place_words' gives the words of each.",
            "letters": P.letters(),
            "step": "python3 tools/build_ecoli_atlas.py members --out DIR writes the files from the two files.",
        },
        "side_notes": {
            "stated": "The protein's reviewed UniProtKB entry states where it is, and the first place it states decides the shelf and the side: the cytoplasm, the periplasm or outside the cell; a membrane the protein is said to span; or a membrane with the face the protein is on. Where the first place names no side, a later statement of the same entry that names a part of that place decides. The mark 'evidence' says what stands behind the statement.",
            "predicted": f"Read from the entry's own features, where its words do not give the side. A membrane-spanning segment puts the protein in the membrane its entry states ({rules['segment']} proteins). A signal peptide with no such segment says that the protein was carried across the inner membrane: it stands on the outside of the inner membrane's shelf where the entry states that membrane ({signal_on['inner']} proteins), and on the outside of the shelf of a membrane that is not named where the entry does not tell the membrane ({signal_on['membrane']}) or states no place ({rules['no place: signal']}). UniProt's curators annotate these features from experiments, from likeness to other proteins and from prediction; its own pages name the predictors: {P.PREDICTORS}. Each is named among the sources, with its terms and what rests on it. {P.RULING}",
            "none": "The entry states a membrane or a place and not the side (the protein then stands apart beside that shelf, with the place in its mark 'where'), or it states no place of the cell and carries no membrane-spanning segment and no signal peptide (the protein is then on no shelf). Nothing is placed by guess.",
        },
        "placed_by": [{"rule": rule, "basis": basis, "what": RULES_SAID[rule], "proteins": rules[rule]} for rule, basis, _ in P.RULES_USED],
        "place_kinds": P.KINDS,
        "place_columns": P.PLACE_COLUMNS,
        "place_notes": "Every place the entries state, in UniProt's words, with the shelf and what the place names against its membrane (place_kinds), how the table's line was reached and which of the table's terms it rests on, and how many proteins it places as the statement that decided. One reading of this file goes beyond the table: a lipid-anchored protein whose entry says \"Cell membrane\", with no experiment behind the statement, stands on the shelf of a membrane that is not named (that shelf's note says why and how many).",
    }
    marks = {
        "isoforms": {"label": "Forms described", "values": "number", "measured": False, "note": "The canonical sequence and the other sequences its entry describes: in this organism, forms that start at another codon of the same gene. The marker stands for the canonical one.", "source": "UniProt"},
        "seen": {"label": "Evidence that the protein exists", "values": [P.SEEN[level] for level in sorted(P.SEEN)], "measured": False, "note": "UniProt's level of evidence for the entry: at protein level, at transcript level, inferred from homology, predicted, or uncertain.", "source": "UniProt"},
        "evidence": {"label": "What stands behind the stated place", "values": [word for word, _, _ in P.EVIDENCE] + [P.NOT_GIVEN], "measured": False, "note": "From UniProt's evidence codes on the statement: " + "; ".join(f"{word}: {what}" for word, _, what in P.EVIDENCE) + f"; {P.NOT_GIVEN}: the entry gives no code, an older curated statement. Of several, the first in this order.", "source": "UniProt"},
        "where": {"label": "Stated place", "values": "text", "measured": False, "note": "The statement that decided the shelf, in UniProt's words: the place, then the topology and the face where the entry states them.", "source": "UniProt"},
        "also": {"label": "Also stated", "values": "text", "measured": False, "note": "The entry's other statements of place, in order and in UniProt's words.", "source": "UniProt"},
        "family": {"label": "Family, of which it is the only member here", "values": "text", "measured": False, "note": "The InterPro family's accession and name, for a protein listed among the only members of their families.", "source": "InterPro"},
        "of": {"label": "Stated for", "values": "text", "measured": False, "note": "The named form of the protein that the place is stated for, where the entry states none for the protein as a whole.", "source": "UniProt"},
        "locus": {"label": "Locus", "values": "text", "measured": False, "note": "The gene's ordered locus name in the genome of strain K-12 substrain MG1655 (its b number), as UniProt gives it.", "source": "UniProt"},
        "chemotaxis": {"label": "Chemotaxis", "values": [True], "measured": False, "note": f"The entry carries UniProt's keyword 'Chemotaxis': the receptors, the proteins that pass their signal on, the motor's switch and stator, and the binding proteins that report sugars and peptides. {len(chemotaxis)} proteins: {listed(by_gene(chemotaxis))}.", "source": "UniProt"},
        "complex": {"label": "Assembly it is part of", "values": [word for word, _, _ in COMPLEXES], "measured": False, "note": "By the Gene Ontology's cellular-component terms that UniProt gives the entry, with every narrower term: " + "; ".join(f"{word} ({name}, {term}): {len(complexes_said[word])}" for word, term, name in COMPLEXES) + ". Of several, the first listed.", "source": "Gene Ontology"},
    }
    terms_day = lambda name: d.day(*P.SAVED_TERMS[name])
    sources = [
        {"name": "UniProt", "url": "https://www.uniprot.org/", "release": release, "accessed": d.day(KB, PLACES_FILE), "licence": "CC BY 4.0", "class": "permissive", "cite": P.CITE_UNIPROT,
         "holds": f"for each reviewed entry of the reference proteome: its name, gene, locus, length, level of evidence and keywords, the places it states with the evidence for each, its membrane-spanning segments and signal peptide, and the InterPro entries and Gene Ontology terms UniProt gives it; and UniProt's vocabulary of places. The programs that its pages name behind the segments and signal peptides it predicts are sources below. Of its own: {plural(of('RuleBase'), 'statement rests', 'statements rest')} on a rule of its rule base, and {plural(of('unnamed analysis'), 'stated place rests', 'stated places rest')} on a sequence analysis for which it names no program"},
        {"name": "InterPro", "url": "https://www.ebi.ac.uk/interpro/", "release": filing.release, "accessed": d.day(IPR, "entry.list"), "licence": "CC0 1.0", "class": "permissive", "cite": P.CITE_INTERPRO, "holds": "the type and name of each entry, the tree of broader and narrower entries, and the mapping of entries to Gene Ontology terms"},
        {"name": "Gene Ontology", "url": "https://geneontology.org/", "release": filing.ontology, "accessed": d.day(GO, "go-basic.obo"), "licence": "CC BY 4.0", "class": "permissive", "cite": P.ontology_citation(d, GO), "holds": "the names of terms and which term is a kind or a part of which; no term's text is copied beyond the names of the districts' and the assemblies' terms"},
        P.through_uniprot("PROSITE", terms_day("prosite"), f"Nothing was downloaded from it but its statement of terms, and nothing of it is copied. Its rules (ProRule) are named in UniProt's entries as what stands behind a statement. {of('PROSITE-ProRule'):,} placements rest on them alone: {of('PROSITE-ProRule', PLACE):,} by the statement of place that decides the shelf ({len(rule_ids.get('PROSITE-ProRule', {})):,} rules), {of('PROSITE-ProRule', SPANS):,} by the statement that the protein spans the membrane, and {of('PROSITE-ProRule', FROM_SEGMENTS) + of('PROSITE-ProRule', FROM_SIGNAL):,} by a side read here from a feature that a rule gives."),
        P.through_uniprot("HAMAP", terms_day("hamap"), f"Nothing was downloaded from it but its statement of terms. Its family rules are named in UniProt's entries as what stands behind a statement. {of('HAMAP-Rule'):,} placements rest on them alone: {of('HAMAP-Rule', PLACE):,} by the statement of place that decides the shelf ({len(rule_ids.get('HAMAP-Rule', {})):,} rules), {of('HAMAP-Rule', SPANS):,} by the statement that the protein spans the membrane, {of('HAMAP-Rule', FACE):,} by the stated face, and {of('HAMAP-Rule', FROM_SEGMENTS) + of('HAMAP-Rule', FROM_SIGNAL):,} by a side read here from a feature that a rule gives."),
        P.through_uniprot("TMHMM", terms_day("tmhmm"), f"{P.NOT_RUN} {P.FOUR_SEGMENTS}. {of('segments'):,} placements rest on segments that an entry gives by sequence analysis alone: {of('segments', FROM_SEGMENTS):,} are read here from such segments (basis predicted; {rules['segment'] + rules['no place: segment']:,} are read from segments in all), and behind a curator's statement {of('segments', SPANS):,} are said to span the membrane on a sequence analysis and {of('segments', PLACE):,} have a stated place that rests on a sequence analysis in an entry with such segments."),
        P.through_uniprot("Phobius", terms_day("phobius"), f"{P.NOT_RUN} {P.FOUR_SEGMENTS}; and one of the four it names for signal peptides. The placements are those counted under TMHMM ({of('segments'):,}) and under SignalP ({of('signal'):,})."),
        P.through_uniprot("SignalP", terms_day("signalp"), f"{P.NOT_RUN} {P.FOUR_SIGNALS}. {of('signal'):,} placements rest on a signal peptide that an entry gives by sequence analysis alone: {of('signal', FROM_SIGNAL):,} are read here from such a signal (basis predicted; {rules['signal'] + rules['no place: signal']:,} are read from a signal peptide in all), and behind a curator's statement {of('signal', PLACE):,} have a stated place that rests on a sequence analysis in an entry with such a signal and no such segment."),
        P.through_uniprot("TargetP", terms_day("targetp"), f"{P.NOT_RUN} {P.FOUR_SIGNALS}. The placements are those counted under SignalP ({of('signal'):,})."),
        P.through_uniprot("Memsat", d.day(KB_DOCS, "help_transmem.json"), f"Nothing was downloaded from it. {P.FOUR_SEGMENTS}. The placements are those counted under TMHMM ({of('segments'):,})."),
        P.through_uniprot("Predotar", d.day(KB_DOCS, "help_signal.json"), f"Nothing was downloaded from it. {P.FOUR_SIGNALS}. The placements are those counted under SignalP ({of('signal'):,})."),
    ]
    # The organism's own databases are pointed to in the README and the note, not here: the scene carries
    # every species' sources, within a limit, and nothing of these two is in the file.
    pointers = [{"name": pointer["name"], "url": pointer["url"], "licence": pointer["licence"], "class": "no stated terms", "accessed": d.day(TERMS, pointer["file"]), "holds": pointer["holds"]} for pointer in POINTERS]
    # The marks that pick out a machine: each protein that carries one, with the line it stands on.
    line_of = {}
    for kind, found in (("family", lines), ("lone", alone), ("part", rest)):
        for line in found:
            for protein in line["proteins"]:
                line_of[protein] = (kind, line["id"])
    marked = {"chemotaxis": {a: True for a in chemotaxis}, "complex": complex_of}
    highlight_rows = []
    for name in MARKED:
        values = [True] if name == "chemotaxis" else [word for word, _, _ in COMPLEXES]
        for value in values:
            for accession in order(a for a, found in marked[name].items() if found == value):
                highlight_rows.append([name, value, accession, entries[accession]["gene"], *line_of[accession], placed[accession]["shelf"], placed[accession]["side"]])
    highlights = {
        "note": "For the marks that pick out a machine (chemotaxis, and the assemblies of 'complex'): each protein that carries the mark, with the line it stands on, so that a page can light the markers that hold them without opening every family. 'kind' says whether 'under' is a family, a part of 'lone' or a part of 'no_family'; a null shelf is no shelf.",
        "columns": ["mark", "value", "id", "gene", "kind", "under", "shelf", "side"],
    }
    if [source["name"] for source in sources if source.get("through")] != UPSTREAM:
        raise SystemExit("the sources read through UniProt are not the ones this tool names")
    closing = {"marks": marks, "highlights": highlights, "counts": counts, "shelf_counts": shelf_counts, "by_basis": P.by_basis(bases), "by_evidence": P.by_evidence(evidence), "sources": sources}

    body = P.shelves_text(header, lines, alone, rest, lone, no_family, tail, places, place_words, closing, len(family_total), highlights=highlight_rows)
    table = P.table_text(TABLE_COLUMNS, sequence, entries, placed, filing, alone, unit_ids, more=lambda protein: [locus[protein], "1" if protein in chemotaxis else "", complex_of.get(protein, "")])

    # --- the species file ---------------------------------------------------------------------
    summary = json.loads(d.text(NCBI, f"genbank_{GENOME}_summary.json"))["result"]
    record = next(value for key_, value in summary.items() if key_ != "uids")
    if record.get("accessionversion") != GENOME or "K-12" not in record.get("title", "") or record.get("topology") != "circular":
        raise SystemExit("the genome record's summary is not the one this file names")
    genome_length = int(record["slen"])
    for paper in PAPERS:
        paper_text(d, paper)
    description = proteome["description"]
    for sentence in ("Gram-negative straight rod, which either uses peritrichous flagella for mobility or is nonmotile", "facultatively anaerobic chemoorganotroph capable of both respiratory and fermentative metabolism", "colonizes the lower gut of animals and survives when released to the natural environment"):
        if sentence not in description:
            raise SystemExit("UniProt's description of the proteome no longer says what a fact rests on")
    proteasome = order(carriers.get(M.PROTEASOME, []))
    if len(proteasome) > 1:
        raise SystemExit("several proteins carry the proteasome's signature; write the sentence on them again")
    proteasome_said = f"One of its proteins carries the signature of the proteasome's subunits: its entry names it \"{entries[proteasome[0]]['name']}\"." if proteasome else "None of its proteins carries the signature of the proteasome's subunits."
    two_component = sum(1 for words in keywords.values() if "Two-component regulatory system" in words)
    by_name = {gene(a): a for a in entries}
    names_needed = {"secY": "Protein translocase subunit SecY", "tatA": "Sec-independent protein translocase protein TatA", "ftsZ": "Cell division protein FtsZ", "aqpZ": "Aquaporin Z"}
    for needed, name in names_needed.items():
        if entries.get(by_name.get(needed), {}).get("name") != name:
            raise SystemExit(f"the proteome no longer names {needed} {name!r}, which a sentence of the species file rests on")
    if "aqpZ" not in channel_hits["IPR000425"] or not channels:
        raise SystemExit("the proteins of bacterial channel families are not the ones the species file speaks of")
    synthase = [a for a, found in complex_of.items() if found == "ATP synthase"]
    if not synthase or any(placed[a]["shelf"] != "inner" for a in synthase) or any(placed[by_name[name]]["shelf"] != "inner" for name in own["p_type"]):
        raise SystemExit("the ATP synthase or a P-type ATPase is not stated at the inner membrane; the species file says that they are")
    secreted = sum(1 for item in placed.values() if item["where"] and item["where"]["name"] == "Secreted")
    porins = sum(1 for words in keywords.values() if "Porin" in words)
    if not secreted or not porins:
        raise SystemExit("no protein is stated to be secreted, or none carries the keyword Porin; the species file says that some do")
    uniprot_source = {"text": f"UniProt Consortium, UniProt release {release}: the reviewed entries of the reference proteome {PROTEOME} (Escherichia coli strain K-12), the proteome's own description, and UniProt's vocabulary of subcellular locations.", "url": f"https://www.uniprot.org/proteomes/{PROTEOME}", "licence": "CC BY 4.0", "class": "permissive", "accessed": d.day(KB, PLACES_FILE)}
    species_sources = {
        "uniprot": uniprot_source,
        "genbank": {"text": f"GenBank {GENOME}: {record['title']}.", "url": f"https://www.ncbi.nlm.nih.gov/nuccore/{GENOME}", "licence": "No restriction: \"NCBI places no restrictions on the use or distribution of the GenBank data\".", "class": "permissive", "accessed": d.day(NCBI, f"genbank_{GENOME}_summary.json")},
        **{key_: {"text": paper_cite(d, key_), "doi": paper["doi"], "licence": "CC BY", "class": "permissive", "accessed": d.day(PAPERS_AT, f"{key_}_fulltext.xml")} for key_, paper in PAPERS.items() if paper.get("use") != "note"},
        **{key_: {"text": paper["text"], "doi": paper["doi"], "url": paper["url"], "licence": paper["licence"], "class": "no stated terms", "standing": "open paper, numbers only", "where": paper["where"], "accessed": NUMBERS_READ} for key_, paper in NUMBERS_ONLY.items()},
    }
    # The envelope's widths (schema/SPECIES_SHAPES.md, `envelope`): numbers alone, each with where it stands in the paper.
    envelope = {**ENVELOPE, "sources": ["matias2003"], "read": {"source": "matias2003", "where": "Table 1, the row for E. coli K-12: the thickness of the plasma membrane, the peptidoglycan and the outer membrane, the periplasmic width, and the distance between the peptidoglycan and the outer membrane, each the mean of eight measurements made on the least deformed regions of the sections; that the last two run between the facing surfaces is this viewer's reading"}}
    # The appendages (schema/SPECIES.md): each number is a fact below, with its source.
    base = {"id": "flagellar-motor", "label": "Flagellar motor", "mark": "complex", "value": "flagellum"}
    if base["value"] not in marks[base["mark"]]["values"] or not complexes_said[base["value"]]:
        raise SystemExit("the mark and value named at the foot of a flagellum are not the shelves' own")
    for needed in ("fliF", "motA", "motB"):
        if placed[by_name[needed]]["shelf"] != "inner" or placed[by_name[needed]]["side"] != "in":
            raise SystemExit(f"{needed} is not stated to be in the inner membrane; the species file says the motor sits there")
    f_plasmid = sorted(name for name in by_name if re.fullmatch(r"tra[A-Z]", name))
    appendages = [
        {"kind": "flagellum", "label": "Flagella", "count": [1, 5], "length_um": [5, 10], "width_nm": [20, 40], "where": "all over", "from": "inner membrane", "base": base, "sources": ["mears2014", "schavemaker2022", "dvoriashyna2021", "zhuang2025", "uniprot"]},
        {"kind": "pilus", "label": "Type 1 fimbriae", "count": [200, 500], "length_um": 1, "width_nm": [7, 10], "where": "all over", "from": "outer membrane", "sources": ["jahnke2016"]},
    ]
    capabilities = {
        "cap.membrane": {"place": "present", "note": "It has two membranes. By UniProt's vocabulary the inner one separates the cytoplasm from the periplasm, and the outer one the periplasm from the cell's surroundings. No source read for this file measured a voltage across either."},
        "cap.channels": {"place": "present", "note": f"Not the channels of animal cells: none of its proteins carries the signature of a channel family that Cells has a law for. {len(channels)} of its proteins carry the signature of a bacterial channel family: {channels_said}."},
        "cap.pumps": {"place": "present", "note": f"Not the pumps of animal cells: none of its proteins carries the signature of the sodium-potassium pump. Its P-type ATPases ({listed(own['p_type'])}) and its ATP synthase are stated to be in the inner membrane."},
        "cap.junctions": {"place": "absent", "why": "It lives as single cells and has no gap junctions: none of its proteins carries the signature of connexins or innexins."},
        "cap.extracellular": {"place": "present", "note": "Two spaces lie beyond its inner membrane: the periplasm, between its two membranes, and what surrounds the cell, the lower gut of an animal or wherever it is released."},
        "cap.water": {"place": "present", "note": "By UniProt's vocabulary a wall lies between its two membranes and plays a part in the cell's shape and stability. One of its proteins, AqpZ, carries the signature of the aquaporin family."},
        "cap.calcium": {"place": "absent", "why": "It has no endoplasmic reticulum, the store this capability concerns: no entry of its proteome states a place in one, and none of its proteins carries the signature of the store's calcium pump or of its release channels."},
        "cap.energy": {"place": "present", "note": "It lives by respiration and by fermentation, with or without oxygen; its ATP synthase is stated to be in the inner membrane."},
        "cap.mitochondria": {"place": "absent", "why": "It is a bacterium and has no mitochondria: no entry of its proteome states a place in one. Its ATP synthase is in the inner membrane."},
        "cap.circuits": {"place": "present", "note": f"At the chromosome, which lies in a region of the cytoplasm that no membrane surrounds: there is no nucleus. {two_component} of its proteins carry UniProt's keyword for two-component regulatory systems."},
        "cap.grn": {"place": "absent", "why": "It forms no tissue, so there is nothing for gene networks to be coupled across. Gene expression within the one cell belongs with regulatory circuits."},
        "cap.trafficking": {"place": "absent", "why": "It has no endoplasmic reticulum and no Golgi: no entry of its proteome states a place in either. By the names of their entries, its proteins cross or enter the inner membrane through the Sec and Tat translocases."},
        "cap.assembly": {"place": "present", "note": "Its assemblies are its ribosomes, RNA polymerase, the ATP synthase, its flagella and its chemoreceptor arrays. The designed protein cage that Cells models is not one of its proteins."},
        "cap.machines": {"place": "present", "note": f"Its ribosomes, RNA polymerase, the ATP synthase, the protein translocases and the motor of its flagella. {proteasome_said}", "left_out": {"since": "2026-11-17", "says": "the barrel drawn for its molecular machines", "reason": "the picture drew it as a proteasome's core, and in a cell this small that barrel stood among the largest things drawn", "why": "On 17 November 2026 the user asked for the molecular machines' barrel to be left out of the bacteria's picture for now, as the map's protein assembly was left out of every species on 15 November; it read as an assembly of molecules, and stood among the largest things drawn. Its place and its note stay in this file: take the flag out and the barrel is drawn again."}},
        "cap.secretion": {"place": "present", "note": "Some of its proteins are stated to be secreted, and porins and transporters carry molecules across its two membranes. Signalling between its own cells was not looked for."},
        "cap.repair": {"place": "present", "note": "The place would be its envelope. No source read for this file describes an injury of it or its resealing in this organism."},
        "cap.division": {"place": "present", "note": "It divides as a single cell: its proteome names the cell division protein FtsZ."},
        "cap.replacement": {"place": "absent", "why": "It forms no tissue, so there is no neighbour for a new cell to replace."},
        "cap.mechanics": {"place": "absent", "why": "It forms no sheet: its cells share no edges to pull on. Its own movement, swimming with flagella, is not what this capability models."},
        "cap.sheet": {"place": "absent", "why": "It lives as single cells and forms no sheet of coupled cells."},
    }
    species = {
        "format": "cells.visualizer.species@1",
        "id": SPECIES_ID,
        "label": LABEL,
        "organism": ORGANISM,
        "taxon": TAXON,
        "plain": f"A rod-shaped bacterium of the animal gut: {len(entries):,} proteins in UniProt's reference proteome of strain K-12, in a cell a few micrometres long with two membranes and a wall between them. It swims with flagella.",
        "group": "Bacteria",
        "order": 50,
        "default": False,
        "made": made,
        "modelled": {"state": "proposed", "text": "The project's record adds it as a data-only organism, for a proposed track whose first stage is bacterial chemotaxis in a well-mixed cell; the track is on hold (decision D179, 15 November 2026). Nothing of it is in the engine: no organism definition, no model and no run.", "record": [{"path": "docs/DECISIONS.md", "where": "D179: The FEP track's decisions: on hold, E. coli as data only"}]},  # the record behind the word (schema/ENTRIES.md)
        "levels": [
            {"id": "molecules"},
            {"id": "cell", "label": "One cell", "shape": {"kind": "capsule", "length_um": 2.5, "across_um": 1}, "note": f"Drawn as a rod 2.5 µm long and 1 µm across: the picture's choice, within the ranges given for the cell. Its second membrane and its wall are drawn as clear shells around the cell membrane, and its {RIBOSOMES_DRAWN:,} ribosomes are the low end of the range one paper gives. Its flagella and fimbriae are given as appendages, with the ranges their sources give; that the fimbriae stand all over the cell is the picture's choice, since no source read for this file says where they stand.", "sources": ["volkmer2011", "urich2008", "uniprot"]},
        ],
        "no_further_levels": "A single-celled organism: each cell lives on its own, so there is no tissue, organ or body.",
        "cell": {
            "facts": [
                {"label": "Shape and size", "value": "a straight rod; earlier work put its average length between 1.6 and 3.1 µm and its width at 0.7 to 1.1 µm, and one study measured 1.6 µm (cells at rest) to 3.9 µm (cells growing on a rich medium) in length and 1.26 µm in width", "sources": ["volkmer2011", "uniprot"]},
                {"label": "Volume", "value": "1.5 to 4.4 femtolitres, by the conditions it grows in", "sources": ["volkmer2011"]},
                {"label": "Envelope", "value": "two membranes: the inner one separates the cytoplasm from the periplasm, the outer one the periplasm from the cell's surroundings; the cell wall lies between them", "sources": ["uniprot"]},
                {"label": "Envelope's widths", "value": f"in frozen-hydrated sections of strain K-12, measured where the sections were least deformed, the inner membrane is {ENVELOPE['membrane_nm']} nm thick, the wall {ENVELOPE['wall_nm']} nm and the outer membrane {ENVELOPE['outer_nm']} nm; the space between the two membranes is {ENVELOPE['between_nm']} nm wide, and the wall lies {ENVELOPE['wall_to_outer_nm']} nm from the outer membrane, each the mean of eight measurements. Its authors give the periplasm's average compression in the sections as 32.47%. The paper does not say between which faces these widths run: taking them between the facing surfaces is this viewer's reading. Another paper measured 25.5 nm between the outer surface of the inner membrane and the inner surface of the outer membrane, at the middle of 31 whole cells of K-12, without osmoprotectants or fixation; the flagellar motor's close view takes a wider spacing from a third paper, of whole cells in hyperosmotic conditions, which its own file names", "sources": ["matias2003", "berry2010"]},
                {"label": "Inside", "value": "a bacterium, with no nucleus: its chromosome lies in a region of the cytoplasm that no membrane surrounds", "sources": ["uniprot"]},
                {"label": "Chromosome", "value": f"one circle of {genome_length:,} base pairs", "sources": ["genbank"]},
                {"label": "Proteins", "value": f"{len(entries):,} in UniProt's reference proteome of strain K-12, every one with a reviewed entry", "sources": ["uniprot"]},
                {"label": "Ribosomes", "value": "between 6,800 and 72,000 in a cell, depending on its phase of growth, as one open paper sums up earlier estimates", "sources": ["urich2008"]},
                {"label": "Movement", "value": "swims with flagella that grow all over its surface, or does not move", "sources": ["uniprot"]},
                {"label": "Flagella", "value": "1 to 5 on a cell in one study of single cells, and 3.4 on average by another paper; each a thread typically 5 to 10 µm long (7.5 µm by one measurement). Of the width the sources disagree: about 20 nm by one, 40 nm by another", "sources": ["mears2014", "schavemaker2022", "dvoriashyna2021", "zhuang2025"]},
                {"label": "Where the flagella stand", "value": f"all over the cell body; the motor at the foot of each sits in the inner membrane, where its ring protein FliF and its stator proteins MotA and MotB are stated to be. {len(complexes_said['flagellum'])} proteins are parts of the flagellum by the Gene Ontology terms UniProt gives them", "sources": ["dvoriashyna2021", "uniprot"]},
                {"label": "Type 1 fimbriae", "value": "200 to 500 on a cell by one paper's summary, each up to 1 µm long and about 7 to 10 nm wide, standing out from the outer membrane", "sources": ["jahnke2016"]},
                {"label": "Chemotaxis", "value": f"{len(chemotaxis)} of its proteins carry UniProt's keyword for chemotaxis ({listed(by_gene(chemotaxis))}), and {len(complexes_said['flagellum'])} are parts of the flagellum by the Gene Ontology terms UniProt gives them", "sources": ["uniprot"]},
                {"label": "Energy", "value": "respiration and fermentation: it lives with or without oxygen", "sources": ["uniprot"]},
                {"label": "Where it lives", "value": "the lower gut of animals; it survives when released to the natural environment", "sources": ["uniprot"]},
                {"label": "Ion channels", "value": f"none of the animal families Cells has laws for; {len(channels)} proteins of bacterial channel families ({listed(by_gene(channels))})", "sources": ["uniprot"]},
                {"label": "Signalling", "value": f"{two_component} proteins carry UniProt's keyword for two-component regulatory systems", "sources": ["uniprot"]},
                {"label": "Strain", "value": f"K-12; the genome record is of its substrain MG1655, and UniProt's proteome is of the same genome assembly ({proteome['genomeAssembly']['assemblyId']})", "sources": ["genbank", "uniprot"]},
            ],
            "parts": {"membranes": 2, "wall": True, "nucleus": False, "chromosome_kbp": round(genome_length / 1000), "ribosomes": RIBOSOMES_DRAWN, "appendages": appendages, "envelope": envelope},
            "capabilities": capabilities,
        },
        "capability_sources": {key_: ["uniprot"] for key_ in capabilities if key_ not in ("cap.grn", "cap.replacement", "cap.mechanics", "cap.sheet", "cap.repair", "cap.junctions")} | {"cap.junctions": ["uniprot"]},
        "sources": species_sources,
    }
    species_text = json.dumps(species, indent=1, ensure_ascii=False) + "\n"

    # --- the atlas file -----------------------------------------------------------------------
    findings = Counter(unit["finding"] for unit in units.values())
    atlas = {
        "format": P.ATLAS_FORMAT,
        "species": {"id": SPECIES_ID, "label": LABEL, "organism": ORGANISM, "taxon": TAXON, "plain": f"A rod-shaped bacterium of the animal gut with {len(entries):,} proteins in UniProt's reference proteome of strain K-12. The units of the law inventory are channels, pumps and junctions of animal cells; this is what the same families' signatures find in it."},
        "made": made,
        "method": [
            f"The organism's proteins are the {len(entries):,} reviewed entries of UniProt's reference proteome {PROTEOME} (release {release}), one protein each.",
            "Licences were read before anything was copied; each is stated in sources.",
            "A unit counts as found only where a protein carries the signature of a family that makes the machine itself (the subunit that forms the channel, or the pump's own chain). A protein that carries only the signature of a family that goes with the machine (a regulator, an accessory subunit) is no candidate: the unit's note names it, and it is listed under extra. This reading is the file's own.",
            "Each unit's family was taken from its own human candidates, by the same InterPro signatures that the planarian, Syn3A and M. pneumoniae atlases ask. The build checks that the candidates carry them.",
            f"Each signature was looked for among the InterPro entries UniProt gives each of the {len(entries):,} proteins. No unit's own family was found; {plural(len(beside), 'protein carries', 'proteins carry')} the signature of an accessory family alone.",
            "A control for every signature: how many reviewed UniProtKB entries of all bacteria carry it; each unit's note gives what came back.",
f"{len(M.BACTERIAL_CHANNELS)} further signatures, of the channels a bacterium could have (potassium, chloride, magnesium, water and membrane-stretch channels), were looked for as well; the {len(channels)} proteins that carry them are listed under extra ({channels_said}), with the cell's P-type ATPases and the catalytic head of its ATP synthase.",
            "No similarity search was run, and nothing is called an ortholog.",
        ],
        "sources": [
            {"name": "UniProt", "url": "https://www.uniprot.org/", "release": release, "accessed": d.day(KB, PLACES_FILE), "licence": "CC BY 4.0", "class": "permissive", "cite": P.CITE_UNIPROT, "holds": "the reviewed entries of the organism's proteins, with the InterPro entries UniProt gives each; the signatures of the units' human candidates; the control counts"},
            {"name": "InterPro", "url": "https://www.ebi.ac.uk/interpro/", "release": filing.release, "accessed": d.day(IPR, "entry.list"), "licence": "CC0 1.0", "class": "permissive", "cite": P.CITE_INTERPRO, "holds": "the identifiers and names of the family signatures"},
        ],
        "not_copied": "No sequence is copied. Nothing is taken from the organism's own curated databases: EcoCyc's data files need a paid subscription, and STEPdb states no terms of use. Both are named in the note as places to read.",
        "units": units,
        "extra": extra,
    }
    atlas_text = json.dumps(atlas, indent=1, ensure_ascii=False) + "\n"

    report = {
        "release": release, "interpro": filing.release, "ontology": filing.ontology, "made": made, "stated": stated, "read": dict(read),
        "shelf_counts": shelf_counts, "counts": counts, "bases": {f"{side} / {basis}": count for (side, basis), count in sorted(bases.items())}, "rules": {rule: rules[rule] for rule, _, _ in P.RULES_USED},
        "evidence": dict(evidence), "between": between, "resting": resting, "rule_ids": rule_ids,
        "families": len(family_total), "in_families": len(filing.family), "several": filing.several, "no_family": len(filing.part),
        "family_sizes": {"one": sum(1 for size in family_total.values() if size == 1), "two to four": sum(1 for size in family_total.values() if 2 <= size <= 4), "five or more": sum(1 for size in family_total.values() if size >= 5)},
        "largest_families": [[filing.names[family]["name"], count] for family, count in sorted(family_total.items(), key=lambda item: (-item[1], item[0]))[:10]],
        "family_ids": sorted(family_total), "lines": len(lines), "distinct": distinct, "lone": lone["count"], "lone_families": lone_families, "lone_parts": len(alone), "part_lines": len(rest),
        "groups": groups, "member_files": files, "places_used": len(used), "place_rows": places,
        "chemotaxis": {gene(a): [key(placed[a]["shelf"]), placed[a]["side"], placed[a]["basis"], complex_of.get(a, "")] for a in sorted(chemotaxis, key=lambda a: gene(a).lower())},
        "complexes": {word: {gene(a): [key(placed[a]["shelf"]), placed[a]["side"]] for a in sorted((a for a, found in complex_of.items() if found == word), key=lambda a: P.natural(gene(a).lower()))} for word, _, _ in COMPLEXES},
        "findings": dict(findings), "found_units": {unit: [product["gene"] for product in found["products"]] for unit, found in units.items() if found["products"]}, "extra": [item["gene"] for item in extra],
        "channels": channel_hits, "p_type": own["p_type"], "proteasome": by_gene(proteasome), "control": control, "genome_length": genome_length,
        "moved": {"proteins": by_gene(moved), "behind": dict(moved_behind), "lipid_anchors_first_stated_at": dict(anchored), "cell_membrane_on_inner": plain_words, "membrane_not_named": unnamed},
        "beside": {gene(accession): [family["of"], asked_by] for accession, (family, asked_by) in beside.items()}, "highlights": len(highlight_rows),
        "pointers": pointers, "two_component": two_component, "f_plasmid_genes": f_plasmid, "papers": {key_: paper_cite(d, key_) for key_ in PAPERS}, "isoforms": {gene(a): entry["isoforms"] for a, entry in entries.items() if entry["isoforms"] > 1},
        "per_protein": {protein: [key(placed[protein]["shelf"]), placed[protein]["side"], placed[protein]["basis"], placed[protein]["rule"]] for protein in sequence},
    }
    files_out = {"shelves": body, "table": table, "species": species_text, "atlas": atlas_text}
    files_out["readme"] = build_readme(report, header, tail, closing, lone, no_family)
    report["sizes"] = P.within_limits(files_out, PATHS)
    return files_out, report


# The whole note of a unit for which the inventory names no natural gene product.
NOTHING = {
    "U18": lambda own, hits: "The inventory gives this unit no gene product: it is a default shape of current, not a named channel." + (f" This organism has a protein with the potassium channel domain ({listed(hits['IPR013099'])}), listed under extra." if hits.get("IPR013099") else ""),
    "U34": lambda own, hits: "A background conductance that the inventory ties to no protein.",
    "U35": lambda own, hits: "A lumped permeability of the whole membrane, not a population of proteins.",
    "U46": lambda own, hits: "A slot that each model configuration fills with a transporter of its own; it has no fixed protein in any species. This organism's own transporters are in its protein catalogue.",
    "U48": lambda own, hits: "A protein cage designed in the laboratory, with no gene in any organism, so there is nothing to look for in this one.",
    "U49": lambda own, hits: "A lumped water permeability of the membrane; water channels (aquaporins) are not part of it." + (f" {plural(len(hits['IPR000425']), 'protein')} of this organism carr{'ies' if len(hits['IPR000425']) == 1 else 'y'} the aquaporin family's signature ({listed(hits['IPR000425'])}), listed under extra." if hits.get("IPR000425") else ""),
}


def build_readme(report, header, tail, closing, lone, no_family):
    r = report
    sides = lambda found: ", ".join(f"{count:,} {side}" for side, count in found.items() if count)
    lines = [
        "# Escherichia coli K-12: its own proteins, on shelves",
        "",
        "Generated by `tools/build_ecoli_atlas.py`; do not edit by hand. The note is `docs/ECOLI.md`.",
        "",
        "## What is here",
        "",
        f"- `shelves.json`: {header['from']} Each stands against one of the cell's two membranes, outside it, in it or inside it, in the format of `schema/SPECIES_PROTEINS.md` (a curated proteome on several shelves).",
        f"- `proteins.tsv`: one line for each of the {r['stated']['reviewed']:,} proteins, in the order of the shelves' lines. No sequences.",
        "- The files of the families' members are not kept here: `python3 tools/build_ecoli_atlas.py members --out DIR` cuts them from these two files, and the page builder does so when it needs them.",
        "",
        "Nothing of this organism is in the engine. It is reference data for the viewer.",
        "",
        "## Shelves",
        "",
        "| Shelf | Proteins | Outside | In | Inside | Side not known |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    names = {shelf["id"]: shelf["label"] for shelf in header["shelves"]}
    for name, found in r["shelf_counts"].items():
        lines.append(f"| {names.get(name, 'On no shelf')} | {sum(found.values()):,} | {found['outside']:,} | {found['in']:,} | {found['inside']:,} | {found['not known']:,} |")
    lines += [
        "",
        f"- **The space between the two membranes.** {header['between']['rule']} Counted: " + "; ".join(f"{what}: {count:,}" for what, count in header["between"]["counts"].items()) + ".",
        *[f"- **{shelf['label']}.** {shelf['note']}" for shelf in header["shelves"]],
        "- **How each side is known:** " + "; ".join(f"{label}: {count:,}" for label, count in r["bases"].items()) + ".",
        "- **Rules, in the order they are tried:** " + "; ".join(f"{item['rule']} ({item['basis']}): {item['proteins']:,}" for item in tail["placed_by"]) + ".",
        f"- **Half the proteome states no place.** {r['stated']['with_place']:,} entries state one; the others stand on no shelf unless a signal peptide says they left the cytoplasm.",
        "",
        "## Families and districts",
        "",
        f"- {r['families']:,} InterPro families hold {r['in_families']:,} proteins: {r['family_sizes']['one']:,} of one, {r['family_sizes']['two to four']:,} of two to four, {r['family_sizes']['five or more']:,} of five or more. {r['no_family']:,} proteins have no family.",
        f"- {r['lines']:,} lines of {r['distinct']:,} families (a line for each shelf a family has members on); the {r['lone']:,} proteins that are the only member of their family stand in {r['lone_parts']} parts; the proteins with no family in {r['part_lines']} lines.",
        "- The largest families: " + "; ".join(f"{name} ({count})" for name, count in r["largest_families"][:8]) + ".",
        "- Districts: " + "; ".join(f"{group['label']} ({group['proteins'] + group['lone']:,})" for group in r["groups"]) + ".",
        "",
        "## Chemotaxis and the assemblies",
        "",
        f"- **`chemotaxis`** ({len(r['chemotaxis'])} proteins, by UniProt's keyword): " + "; ".join(f"{name} ({found[0]}, {found[1]})" for name, found in r["chemotaxis"].items()) + ".",
    ]
    for word, found in r["complexes"].items():
        lines.append(f"- **`complex`: {word}** ({len(found)}): " + ", ".join(f"{name} ({place[0]}, {place[1]})" for name, place in found.items()) + ".")
    lines.append(f"- The page offers a mark to show by only where a species has one marker for each protein. Here the proteins stand in families, so each member carries its marks, and `shelves.json` lists under `highlights` every protein that carries one with the line it stands on ({r['highlights']} lines).")
    lines += [
        "",
        "## What rests on tools whose own terms are not permissive",
        "",
        "By the project's rule (the user, 15 November 2026), a value stands on the terms of the database it was read from, here UniProt's, and the tool behind it is named and counted. It is the project's rule, not a legal opinion. Nothing was downloaded from any of these tools, and none was run.",
        "",
        "| Tool or rule system | Its terms | Class | What rests on it |",
        "| --- | --- | --- | --- |",
    ]
    for source in closing["sources"]:
        if source.get("through"):
            lines.append(f"| {source['name']} | {source['licence']} | {source['class']} | {source['holds']} |")
    lines += [
        "",
        "## Sources",
        "",
    ]
    for source in closing["sources"]:
        if not source.get("through") and source["class"] == "permissive":
            lines.append(f"- **{source['name']}** ({source['licence']}; read {source['accessed']}): {source['holds']}.")
    lines += ["", "Read for their terms and pointed to; nothing is taken from them:", ""]
    for source in r["pointers"]:
        lines.append(f"- **[{source['name']}]({source['url']})** ({source['licence']}; read {source['accessed']}). {source['holds']}")
    lines += [
        "",
        "## To rebuild",
        "",
        "```",
        "python3 tools/build_ecoli_atlas.py fetch --datasets DATA   # the only step that uses the network",
        "python3 tools/build_ecoli_atlas.py build --datasets DATA   # the same bytes every time",
        "```",
        "",
        "DATA is the folder that holds every species' downloads, one folder per source with a MANIFEST.",
        "",
    ]
    return "\n".join(lines)


def own_marks(row):
    """The marks of this organism's own columns of the table, after the shared ones."""
    marks = {}
    if row["locus"]:
        marks["locus"] = row["locus"]
    if row["chemotaxis"]:
        marks["chemotaxis"] = True
    if row["complex"]:
        marks["complex"] = row["complex"]
    return marks


def summary(report):
    r = report
    return "\n".join([
        f"UniProt {r['release']}, InterPro {r['interpro']}, Gene Ontology {r['ontology']}; made {r['made']}",
        f"in: {r['stated']['reviewed']:,} reviewed entries; unreviewed: {r['stated']['unreviewed']:,}; genes {r['stated']['genes']:,}; {r['stated']['with_place']:,} state a place; read: {r['read']}",
        "by shelf: " + "; ".join(f"{shelf} {sum(sides.values()):,} {sides}" for shelf, sides in r["shelf_counts"].items()),
        f"sides: {r['counts']}; side and basis: {r['bases']}",
        f"rules: {r['rules']}",
        f"between the membranes: {r['between']}",
        f"evidence behind the deciding statement: {r['evidence']}",
        f"families: {r['families']:,} holding {r['in_families']:,} proteins (sizes {r['family_sizes']}); no family {r['no_family']:,}; lines {r['lines']:,} of {r['distinct']:,}; lone {r['lone']:,} in {r['lone_parts']} parts; part lines {r['part_lines']}",
        f"largest: {r['largest_families'][:6]}",
        "districts: " + "; ".join(f"{group['id']} {group['lines']:,} lines, {group['proteins']:,} proteins, {group['lone']:,} lone" for group in r["groups"]),
        f"rests on a rule system or a program, by owner: {r['resting']}",
        f"chemotaxis: {r['chemotaxis']}",
        "assemblies: " + "; ".join(f"{word} {len(found)}" for word, found in r["complexes"].items()),
        f"atlas: {r['findings']}; found {r['found_units']}; accessory only {r['beside']}; extra {r['extra']}",
        f"lipid anchors at 'Cell membrane' moved to the unnamed membrane: {len(r['moved']['proteins'])} {r['moved']['behind']}; first stated at {r['moved']['lipid_anchors_first_stated_at']}; 'Cell membrane' on inner {r['moved']['cell_membrane_on_inner']}; membrane not named {r['moved']['membrane_not_named']}",
        f"channels: {r['channels']}; P-type: {r['p_type']}; proteasome signature: {r['proteasome']}",
        f"member files: {r['member_files']}; places used: {r['places_used']}; sizes: {r['sizes']}",
    ])


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("step", choices=["fetch", "build", "members"])
    parser.add_argument("--datasets", help="fetch, build: the folder that holds every species' downloads, one folder per source with a MANIFEST.json (kept outside the repository)")
    parser.add_argument("--refresh", action="store_true", help="fetch: ask again even where an answer is saved")
    parser.add_argument("--out-dir", default=str(OUT_DIR), help="build: the folder for shelves.json, the table and their README.md; members: the folder that holds them")
    parser.add_argument("--out-species", default=str(SPECIES_FILE), help="build: where the species file is written")
    parser.add_argument("--out-atlas", default=str(ATLAS_FILE), help="build: where the atlas file is written")
    parser.add_argument("--out", help="members: the folder to write the member files into")
    parser.add_argument("--report", help="build: also write what was counted, as JSON, to this file (kept outside the repository)")
    args = parser.parse_args()
    if args.step == "members":
        if not args.out:
            parser.error("members needs --out")
        P.write_members(args.out_dir, args.out, last=own_marks)
        return
    if not args.datasets:
        parser.error(f"{args.step} needs --datasets")
    if args.step == "fetch":
        sys.exit(1 if fetch(Path(args.datasets), refresh=args.refresh) else 0)
    snapshot = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    files, report = build(Path(args.datasets), snapshot)
    folder = Path(args.out_dir)
    folder.mkdir(parents=True, exist_ok=True)
    targets = [(folder / P.SHELVES_FILE, "shelves"), (folder / P.TABLE_FILE, "table"), (folder / "README.md", "readme"), (Path(args.out_species), "species"), (Path(args.out_atlas), "atlas")]
    for target, name in targets:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(files[name], encoding="utf-8")
        print(f"wrote {target.name} ({len(files[name].encode('utf-8')):,} bytes)")
    if args.report:
        Path(args.report).write_text(json.dumps(report, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(summary(report))


if __name__ == "__main__":
    main()
