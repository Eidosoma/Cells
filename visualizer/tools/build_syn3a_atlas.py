#!/usr/bin/env python3
"""Build the viewer's data on the minimal cell JCVI-syn3A, and the start of its protein catalogue.

Four things are written, each from saved responses of public databases and open papers:

    data/species/syn3a.json            the species file (schema/SPECIES.md): its levels, the
                                       cell's shape and parts, and which of Cells' capabilities
                                       have a place in it
    data/proteins/atlases/syn3a.json   its side of the protein atlas (schema/SPECIES_ATLAS.md):
                                       an entry for every unit of the law inventory
    data/proteins/syn3a/               proteins.tsv, one line per protein product of one frozen
                                       genome annotation; shelves.json, where each of those
                                       proteins sits against the cell membrane and how that is
                                       known (schema/SPECIES_PROTEINS.md); and the README that
                                       explains both

Two steps, kept apart, and two folders: DATA holds the downloads, one folder per source
with a MANIFEST.json that gives each file's address, time and SHA-256; DIR holds the
analysis, which is the log of what this tool asked and the record of what a build read.

    python3 tools/build_syn3a_atlas.py fetch --evidence DIR --datasets DATA
        asks public databases for what is not yet in DATA and saves each answer in the
        folder of its source, with a line in DIR/requests.json. The only step that uses
        the network. Folders that another agent made are read and never written.

    python3 tools/build_syn3a_atlas.py build --evidence DIR --datasets DATA
        reads only DATA, DIR and the inventory snapshot, checks every file against the
        SHA-256 its MANIFEST gives, and writes the files above: the same bytes every time.

This is the viewer's reference data. It is not the engine's protein catalogue, and it makes
no claim about the engine: nothing of this organism is modelled there on the day it was made.

Requests carry a generic client name and nothing about who asks. Standard library only.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from collections import Counter
from pathlib import Path
from xml.etree import ElementTree

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
SNAPSHOT = ROOT / "data" / "proteins" / "inventory.snapshot.json"
SPECIES_FILE = ROOT / "data" / "species" / "syn3a.json"
ATLAS = ROOT / "data" / "proteins" / "atlases" / "syn3a.json"
CATALOGUE_DIR = ROOT / "data" / "proteins" / "syn3a"
CATALOGUE_FILE = "proteins.tsv"
SPECIES_FORMAT = "cells.visualizer.species@1"
ATLAS_FORMAT = "cells.visualizer.species_atlas@1"
CLIENT = "atlas-builder/1.0"
PATHS = re.compile(r"/(?:home|mnt|Users|tmp)/")
MADE = "2026-11-15"  # revised by the licence pass; first made on 14 November 2026

SPECIES_ID = "syn3a"
LABEL = "Syn3A"
ORGANISM = "JCVI-syn3A"
TAXON = 2144189
RECORD = "CP016816.2"        # the frozen annotation
FIRST_RECORD = "CP016816.1"  # its first version, whose protein identifiers the proteomics table uses
SYN30_RECORD = "CP014940.1"  # the smaller strain JCVI-syn3.0, read only to check its counts
MOLLICUTES = 31969           # the class of bacteria the organism was made from
PARENT_SPECIES = 2102        # Mycoplasma mycoides, the species its genome was cut down from

EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
UNIPROT = "https://rest.uniprot.org"
EPMC = "https://www.ebi.ac.uk/europepmc/webservices/rest"
ELIFE = "https://cdn.elifesciences.org/articles/36842"
HUMAN_FIELDS = "accession,gene_primary,protein_name,length,xref_interpro"

SHELVES_FILE = "shelves.json"
SHELVES_FORMAT = "cells.visualizer.species_proteins@1"
SHELVES_MADE = "2026-11-15"
# The hydropathy scale's values are read from a source with an open licence: Biopython.
BIOPYTHON = "https://raw.githubusercontent.com/biopython/biopython/biopython-185"
BIOPYTHON_PAGE = "https://github.com/biopython/biopython/blob/biopython-185/Bio/SeqUtils/ProtParamData.py"
# The papers whose records are kept for where proteins sit: the hydropathy scale, and two
# papers that are pointers only (see CLASSES).
SHELF_PAPERS = {"kyte1982": "7108955", "chambaud1999": "10603485", "lhernault1992": "1527173"}

PAPERS = {
    "breuer2019": "30657448", "gilbert2021": "34368224", "thornburg2022": "35063075",
    "pelletier2021": "33784496", "hutchison2016": "27013737", "thornburg2026": "41806832",
}
LICENCES = {"breuer2019": "CC BY 4.0", "gilbert2021": "CC BY 4.0", "thornburg2022": "CC BY-NC-ND 4.0"}

# How each source may be used (the project's rule of 15 November 2026, decision D173):
#   permissive        CC BY, CC0, or a plain statement that no restriction is placed: its
#                     values may enter the files, with attribution;
#   non-commercial    a CC BY-NC licence of any kind: analysis only, so nothing of it enters;
#   no stated terms   no open licence is stated: nothing of it enters.
# A source of the last two classes is a pointer: the files name it and say what is to be
# read there, and take no value and no statement from it.
PERMISSIVE, NON_COMMERCIAL, NO_TERMS = "permissive", "non-commercial", "no stated terms"
CLASSES = {
    "breuer2019": PERMISSIVE, "gilbert2021": PERMISSIVE, "zhang2023": PERMISSIVE, "paulet2011": PERMISSIVE, "christodoulides2018": PERMISSIVE,
    "desvaux2018": PERMISSIVE, "smithers2021": PERMISSIVE, "legood2020": PERMISSIVE,
    "thornburg2022": NON_COMMERCIAL, "lhernault1992": NON_COMMERCIAL,
    "pelletier2021": NO_TERMS, "chambaud1999": NO_TERMS, "kyte1982": NO_TERMS,
}
# Open articles read in full from PubMed Central's open-data store, each with the licence
# that store records for it: all CC BY. They replace what was once read in papers under
# non-commercial terms or with no stated terms.
OPEN = "https://pmc-oa-opendata.s3.amazonaws.com"
OPEN_TEXTS = {"zhang2023": "PMC9952402", "paulet2011": "PMC3110554", "christodoulides2018": "PMC6080569", "desvaux2018": "PMC5817068", "smithers2021": "PMC8689077", "legood2020": "PMC8048626"}
OPEN_LICENCE = {"zhang2023": "CC BY 4.0", "paulet2011": "CC BY 2.0", "christodoulides2018": "CC BY 4.0", "desvaux2018": "CC BY 4.0", "smithers2021": "CC BY 4.0", "legood2020": "CC BY 4.0"}
# The reviews the lipid-anchor rule is fixed from, and the one that says what it can miss,
# were added on 15 November 2026, to a folder of their own.
RULE_TEXTS = ("desvaux2018", "smithers2021", "legood2020")


# ---------------------------------------------------------------------------------------
# What is looked for: the family behind each unit, by its InterPro signature
# ---------------------------------------------------------------------------------------
#
# The same signatures as the planarian atlas asks, so that every species is asked the same
# question. "of" is the family as a sentence names it.

FAMILIES = {
    "nav_alpha": {"of": "voltage-gated sodium channel alpha subunits", "signatures": ["IPR001696"]},
    "nav_beta": {"of": "sodium channel beta subunits", "signatures": ["IPR027098", "IPR000920"]},
    "kv1": {"of": "Kv1-type potassium channels", "signatures": ["IPR003972"]},
    "kv2": {"of": "Kv2-type potassium channels", "signatures": ["IPR003973"]},
    "kv3": {"of": "Kv3-type potassium channels", "signatures": ["IPR003974"]},
    "kv4": {"of": "Kv4-type potassium channels", "signatures": ["IPR003975"]},
    "kv_beta": {"of": "Kv-beta subunits", "signatures": ["IPR005983"]},
    "kir": {"of": "inward-rectifier potassium channels", "signatures": ["IPR016449", "IPR040445", "IPR041647"]},
    "hcn": {"of": "HCN-type channels", "signatures": ["IPR051413", "IPR013621"]},
    "cav_l": {"of": "L-type calcium channel alpha-1 subunits", "signatures": ["IPR005446"]},
    "cav": {"of": "voltage-gated calcium channel alpha-1 subunits", "signatures": ["IPR002077"]},
    "cav_t": {"of": "T-type calcium channel alpha-1 subunits", "signatures": ["IPR005445"]},
    "cav_beta": {"of": "calcium channel beta subunits", "signatures": ["IPR000584"]},
    "cav_a2d": {"of": "calcium channel alpha-2/delta subunits", "signatures": ["IPR051173", "IPR013680"]},
    "bk": {"of": "BK calcium-activated potassium channels", "signatures": ["IPR047871"]},
    "sk": {"of": "SK calcium-activated potassium channels", "signatures": ["IPR015449"]},
    "bk_beta": {"of": "BK channel beta subunits", "signatures": ["IPR003930"]},
    "connexin": {"of": "connexins", "signatures": ["IPR000500", "IPR013092"]},
    "innexin": {"of": "innexins", "signatures": ["IPR000990"], "human": False},
    "nka_alpha": {"of": "the sodium-potassium pump's alpha subunit", "signatures": ["IPR005775"]},
    "nka_beta": {"of": "its beta subunit", "signatures": ["IPR000402"]},
    "fxyd": {"of": "its FXYD regulators", "signatures": ["IPR000272"]},
    "pmca": {"of": "plasma-membrane calcium pumps", "signatures": ["IPR006408"]},
    "serca": {"of": "SERCA-type calcium pumps", "signatures": ["IPR005782"]},
    "ncx": {"of": "sodium-calcium exchangers", "signatures": ["IPR004836"]},
    "ip3r": {"of": "inositol trisphosphate receptors", "signatures": ["IPR000493"]},
    "ryr": {"of": "ryanodine receptors", "signatures": ["IPR013333"]},
    "kcc": {"of": "potassium-chloride cotransporters", "signatures": ["IPR000076"]},
    "nkcc": {"of": "sodium-potassium-chloride cotransporters", "signatures": ["IPR002443"]},
    "slc12": {"of": "the wider SLC12 transporter family", "signatures": ["IPR004842"]},
    "mcu": {"of": "the mitochondrial calcium uniporter", "signatures": ["IPR039055", "IPR006769"]},
    "emre": {"of": "its regulator EMRE", "signatures": ["IPR018782"]},
    "micu": {"of": "its MICU regulators", "signatures": ["IPR039800"]},
}

# Channels a bacterium could have, which no unit of the inventory stands for. Asked so that
# "it has no ion channel" rests on more than the animal families above.
BACTERIAL_CHANNELS = {
    "IPR005821": "the ion transport domain of voltage-gated-like cation channels",
    "IPR013099": "the potassium channel domain",
    "IPR001185": "the large-conductance mechanosensitive channel (MscL)",
    "IPR006685": "the mechanosensitive channel MscS",
    "IPR001807": "chloride channels of the ClC family",
    "IPR000425": "aquaporins and their relatives (major intrinsic proteins)",
    "IPR002523": "CorA-type magnesium channels",
    "IPR006667": "MgtE-type magnesium channels",
}
PROTEASOME = "IPR001353"  # the 20S proteasome's subunits; asked for the molecular-machines note

NOTHING_TO_LOOK_FOR = "nothing to look for"
NO_CHANNEL = "No ion channel of any family searched was found in this organism: its ions cross the membrane through transporters and pumps."
KV_TAIL = "It takes up potassium with a transporter instead (KtrAB, listed under extra). " + NO_CHANNEL
NAV = ["nav_alpha", "nav_beta"]
KV1 = ["kv1", "kv_beta"]
CAV_AUX = ["cav_beta", "cav_a2d"]
GAP = ["connexin", "innexin"]
GAP_TAIL = "Gap junctions join the neighbouring cells of a tissue, and this organism lives as single cells."
NO_ER = "It is a bacterium with a single membrane and no internal compartments, so it has no endoplasmic reticulum for this machine to sit in."

# For each unit: the families searched and the sentence that closes its note; or, where the
# inventory names no natural gene product, the finding and the whole note.
UNITS = {
    "U01": {"parts": NAV, "tail": NO_CHANNEL}, "U02": {"parts": NAV, "tail": NO_CHANNEL},
    "U03": {"parts": NAV, "tail": NO_CHANNEL}, "U04": {"parts": NAV, "tail": NO_CHANNEL},
    "U05": {"parts": KV1, "tail": KV_TAIL}, "U06": {"parts": KV1, "tail": KV_TAIL}, "U07": {"parts": KV1, "tail": KV_TAIL},
    "U08": {"parts": KV1, "tail": KV_TAIL}, "U09": {"parts": KV1, "tail": KV_TAIL}, "U10": {"parts": KV1, "tail": KV_TAIL},
    "U11": {"parts": ["kv2"], "tail": KV_TAIL}, "U12": {"parts": ["kv2"], "tail": KV_TAIL},
    "U13": {"parts": ["kv3"], "tail": KV_TAIL}, "U14": {"parts": ["kv3"], "tail": KV_TAIL},
    "U15": {"parts": ["kv3"], "tail": KV_TAIL}, "U16": {"parts": ["kv3"], "tail": KV_TAIL},
    "U17": {"parts": ["kv4"], "tail": KV_TAIL},
    "U18": {"finding": NOTHING_TO_LOOK_FOR, "note": "The inventory gives this unit no gene product: it is a default shape of current, not a named channel. No potassium channel of any family searched was found in this organism."},
    "U19": {"parts": ["kir"], "tail": KV_TAIL},
    "U20": {"parts": ["hcn"], "tail": NO_CHANNEL}, "U21": {"parts": ["hcn"], "tail": NO_CHANNEL},
    "U22": {"parts": ["hcn"], "tail": NO_CHANNEL}, "U23": {"parts": ["hcn"], "tail": NO_CHANNEL},
    "U24": {"parts": ["cav_l"] + CAV_AUX, "tail": NO_CHANNEL}, "U25": {"parts": ["cav_l"] + CAV_AUX, "tail": NO_CHANNEL},
    "U26": {"parts": ["cav_l"] + CAV_AUX, "tail": NO_CHANNEL}, "U27": {"parts": ["cav"] + CAV_AUX, "tail": NO_CHANNEL},
    "U28": {"parts": ["cav"] + CAV_AUX, "tail": NO_CHANNEL}, "U29": {"parts": ["cav"] + CAV_AUX, "tail": NO_CHANNEL},
    "U30": {"parts": ["cav"] + CAV_AUX, "tail": NO_CHANNEL},
    "U31": {"parts": ["cav_t"], "tail": NO_CHANNEL}, "U32": {"parts": ["cav_t"], "tail": NO_CHANNEL},
    "U33": {"parts": ["bk", "sk", "bk_beta"], "tail": KV_TAIL},
    "U34": {"finding": NOTHING_TO_LOOK_FOR, "note": "A background conductance that the inventory ties to no protein."},
    "U35": {"finding": NOTHING_TO_LOOK_FOR, "note": "A lumped permeability of the whole membrane, not a population of proteins."},
    "U36": {"parts": GAP, "tail": GAP_TAIL}, "U37": {"parts": GAP, "tail": GAP_TAIL}, "U38": {"parts": GAP, "tail": GAP_TAIL},
    "U39": {"parts": ["nka_alpha", "nka_beta", "fxyd"], "tail": "The wider family, the P-type ATPases, has two members here, both annotated as magnesium transporters (loci JCVISYN3A_0787 and JCVISYN3A_0879, listed under extra). Neither carries the mark of the sodium-potassium pump."},
    "U40": {"parts": ["pmca"], "tail": "One of its two P-type ATPases, locus JCVISYN3A_0879, has been suggested to carry calcium, and the 2019 reconstruction of its metabolism uses it as the calcium importer. It does not carry this signature, and it is listed under extra."},
    "U41": {"parts": ["serca"], "tail": NO_ER},
    "U42": {"parts": ["ncx"], "tail": "Nothing in its annotation is named a sodium-calcium exchanger."},
    "U43": {"parts": ["ip3r", "ryr"], "tail": NO_ER},
    "U44": {"parts": ["kcc", "slc12"], "tail": "Its annotation names no chloride-coupled cotransporter."},
    "U45": {"parts": ["nkcc", "slc12"], "tail": "Its annotation names no chloride-coupled cotransporter."},
    "U46": {"finding": NOTHING_TO_LOOK_FOR, "note": "A slot that each model configuration fills with a transporter of its own; it has no fixed protein in any species. This organism's own transporters are in its protein catalogue."},
    "U47": {"parts": ["mcu", "emre", "micu"], "tail": "It is a bacterium and has no mitochondria."},
    "U48": {"finding": NOTHING_TO_LOOK_FOR, "note": "A protein cage designed in the laboratory, with no gene in any organism, so there is nothing to look for in this one."},
    "U49": {"finding": NOTHING_TO_LOOK_FOR, "note": "A lumped water permeability of the membrane; water channels (aquaporins) are not part of it. No protein of this organism carries the aquaporin family's signature."},
}

# The organism's own membrane machines that bear on what the atlas draws and match no unit.
# "words" must be found in the saved text of the 2019 paper for "named in a publication";
# "signature" must be on the protein in UniProt's archive for "family signature".
EXTRA = [
    {"locus": "JCVISYN3A_0792", "name": "ATP synthase, F1 alpha subunit", "role": "catalytic head", "signature": "IPR000194",
     "why": "Part of the cell's F-type ATP synthase, which sits in its one membrane; four of its eight subunits are listed here. The 2019 reconstruction of the cell's metabolism has this machine push protons out of the cell; that is a model's reading, not a measurement in this strain. The law inventory has no F-type ATPase."},
    {"locus": "JCVISYN3A_0790", "name": "ATP synthase, F1 beta subunit", "role": "catalytic head", "signature": "IPR000194",
     "why": "The other subunit of the ATP synthase's catalytic head. The 2019 paper found the genes of this machine essential."},
    {"locus": "JCVISYN3A_0795", "name": "ATP synthase, F0 c subunit", "role": "proton-carrying ring", "signature": "IPR000454",
     "why": "The ring of the ATP synthase that carries protons across the membrane."},
    {"locus": "JCVISYN3A_0796", "name": "ATP synthase, F0 a subunit", "role": "proton path", "signature": "IPR000568",
     "why": "The membrane subunit of the ATP synthase beside the ring, where protons enter and leave."},
    {"locus": "JCVISYN3A_0787", "name": "P-type ATPase MgtA", "role": "ion pump", "words": r"mgtA/ ?0787", "says": "the annotation lists it as an importer of magnesium",
     "why": "A pump of the same superfamily as the sodium-potassium and calcium pumps of animal cells, of another branch: its annotation calls it magnesium-translocating."},
    {"locus": "JCVISYN3A_0879", "name": "P-type ATPase annotated as CorA", "role": "ion pump", "words": r"corA/ ?0879", "says": "a putative magnesium importer that could carry calcium as well; the paper's reconstruction uses it as the calcium importer",
     "why": "Its annotation calls it a magnesium transporter and names it corA, but its signatures are those of a cation-transporting P-type ATPase and not of the CorA channel family. It is the nearest thing this organism has to a calcium pump."},
    {"locus": "JCVISYN3A_0685", "name": "Potassium uptake protein KtrB-like", "role": "membrane part of KtrAB", "words": r"KtrAB \( ?natA/ ?0685 and trkA/ ?0686 ?\)", "says": "with locus 0686, the KtrAB potassium import system; the paper's reconstruction gives it an ATP-consuming exchange of potassium for sodium",
     "why": "The membrane part of the cell's potassium uptake system. This is how the organism takes up potassium without a sodium-potassium pump or a potassium channel. Its annotation calls it a sodium transporter (natA)."},
    {"locus": "JCVISYN3A_0686", "name": "Potassium uptake protein KtrA-like", "role": "regulatory part of KtrAB", "words": r"KtrAB \( ?natA/ ?0685 and trkA/ ?0686 ?\)", "says": "with locus 0685, the KtrAB potassium import system",
     "why": "The cytoplasmic partner of the potassium uptake system, annotated trkA."},
    {"locus": "JCVISYN3A_0779", "name": "Glucose transporter PtsG", "role": "sugar uptake", "words": r"PtsG \( ?ptsG/ ?0779 ?\)", "says": "part of the glucose phosphotransferase system, the only annotated sugar importer",
     "why": "The membrane part of the system that brings in glucose, the cell's fuel. Its ATP comes from fermenting that sugar."},
]


# ---------------------------------------------------------------------------------------
# Fetch: what is asked, and how each answer is kept
# ---------------------------------------------------------------------------------------

def q(text):
    return urllib.parse.quote(text, safe="")


def human_accessions(snapshot):
    return sorted({p["human_uniprot"] for unit in snapshot["units"] for p in unit.get("products") or [] if p.get("human_uniprot")})


def rule_signatures():
    out = []
    for family in FAMILIES.values():
        for signature in family["signatures"]:
            if signature not in out:
                out.append(signature)
    return sorted(out)


def open_prefix(key):
    """The first part of an open article's file name, which names the folder it is kept in."""
    return "rule_open_" if key in RULE_TEXTS else "open_"


def open_file(key, kind="xml"):
    return f"{open_prefix(key)}{OPEN_TEXTS[key]}.{kind}"


def efetch(record, kind):
    return f"{EUTILS}/efetch.fcgi?db=nuccore&id={record}&rettype={kind}&retmode=text&tool=atlas-builder"


def requests(snapshot, datasets=None):
    """Every request of the fetch step: (file name, URL, what it is for). One request depends
    on an earlier answer and is added once that answer is saved."""
    out = []

    def add(name, url, purpose, **more):
        out.append({"name": name, "url": url, "purpose": purpose, **more})

    # The frozen annotation, its first version and the smaller strain's record.
    add(f"genbank_{RECORD}_summary.json", f"{EUTILS}/esummary.fcgi?db=nuccore&id={RECORD}&retmode=json&tool=atlas-builder", "the genome record: its title, length, organism and dates")
    add(f"genbank_{RECORD}_head.gb", f"{EUTILS}/efetch.fcgi?db=nuccore&id={RECORD}&rettype=gb&retmode=text&seq_start=1&seq_stop=60&tool=atlas-builder", "the head of the genome record: who submitted it, its versions and what it was made from")
    add(f"genbank_{RECORD}_features.ft", efetch(RECORD, "ft"), "every feature of the genome record: genes, coding sequences, RNA genes and pseudogenes")
    add(f"genbank_{RECORD}_cds_aa.fa", efetch(RECORD, "fasta_cds_aa"), "the protein product of each coding sequence, with its locus tag, gene, product and protein identifier")
    add(f"genbank_{FIRST_RECORD}_cds_aa.fa", efetch(FIRST_RECORD, "fasta_cds_aa"), "the first version of the record, whose protein identifiers the proteomics table uses")
    add(f"genbank_{SYN30_RECORD}_features.ft", efetch(SYN30_RECORD, "ft"), "the record of the smaller strain JCVI-syn3.0, read to check its gene counts")

    # UniProt: what it holds for the organism, the family signatures on its proteins, and
    # the signatures of the units' human candidates.
    add(f"uniprot_taxonomy_{TAXON}.json", f"{UNIPROT}/taxonomy/{TAXON}", "how many UniProtKB entries the organism has")
    add(f"uniprot_taxonomy_{MOLLICUTES}.json", f"{UNIPROT}/taxonomy/{MOLLICUTES}", "the class of bacteria the controls are asked of")
    add(f"uniprot_taxonomy_{PARENT_SPECIES}.json", f"{UNIPROT}/taxonomy/{PARENT_SPECIES}", "the parent species, of which the channel signatures are asked as well")
    add(f"uniparc_{TAXON}.json", f"{UNIPROT}/uniparc/search?query={q(f'taxonomy_id:{TAXON}')}&format=json&size=500", "every archived protein sequence of the organism, with the family signatures on it")
    add("uniprotkb_human_candidates.json", f"{UNIPROT}/uniprotkb/accessions?accessions={','.join(human_accessions(snapshot))}&format=json&fields={HUMAN_FIELDS}", "the family signatures carried by the units' human candidates")
    for signature in sorted({*rule_signatures(), *BACTERIAL_CHANNELS, PROTEASOME}):
        add(f"control_uniprotkb_{signature}_{MOLLICUTES}.json", f"{UNIPROT}/uniprotkb/search?query={q(f'(xref:interpro-{signature}) AND (taxonomy_id:{MOLLICUTES})')}&size=1&fields=accession&format=json", f"how many UniProtKB entries of mollicutes carry {signature}")
    for signature in sorted(BACTERIAL_CHANNELS):
        add(f"control_uniprotkb_{signature}_{PARENT_SPECIES}.json", f"{UNIPROT}/uniprotkb/search?query={q(f'(xref:interpro-{signature}) AND (taxonomy_id:{PARENT_SPECIES})')}&size=1&fields=accession&format=json", f"how many UniProtKB entries of Mycoplasma mycoides, the parent species, carry {signature}")

    # The 2019 paper's tables (CC BY 4.0) and the open texts that the facts are read from.
    add("elife_36842_supp3.xlsx", f"{ELIFE}/elife-36842-supp3-v3.xlsx", "Breuer and others 2019, supplementary file 3: functional classes and essentiality of every gene")
    add("elife_36842_supp5.xlsx", f"{ELIFE}/elife-36842-supp5-v3.xlsx", "Breuer and others 2019, supplementary file 5: the proteomics table")
    add("europepmc_fulltext_PMC6609329.xml", f"{EPMC}/PMC6609329/fullTextXML", "Breuer and others 2019, the open text and its licence")
    add("europepmc_fulltext_PMC8339304.xml", f"{EPMC}/PMC8339304/fullTextXML", "Gilbert and others 2021, the open text and its licence")
    add("ncbi_pmc_9985924.xml", f"{EUTILS}/efetch.fcgi?db=pmc&id=9985924&retmode=xml&tool=atlas-builder", "Thornburg and others 2022, the open author manuscript and its licence")
    add("europepmc_citations.json", f"{EPMC}/search?query={q('src:med AND ext_id:(' + ' OR '.join(sorted(PAPERS.values(), key=int)) + ')')}&format=json&resultType=core&pageSize=100", "the records of the papers cited, with their abstracts")
    add("proteomexchange_PXD008159.xml", "https://proteomecentral.proteomexchange.org/cgi/GetDataset?ID=PXD008159&outputMode=XML", "the public deposit of the 2019 proteomics")

    # For the shelves: the hydropathy scale's values from an openly licensed source, with
    # that licence, and the papers cited for where proteins sit.
    add("biopython_185_ProtParamData.py", f"{BIOPYTHON}/Bio/SeqUtils/ProtParamData.py", "the values of Kyte and Doolittle's hydropathy scale, as Biopython 1.85 lists them under an open licence; read as text, never run")
    add("biopython_185_LICENSE.rst", f"{BIOPYTHON}/LICENSE.rst", "Biopython's licence")
    add("europepmc_shelves_citations.json", f"{EPMC}/search?query={q('src:med AND ext_id:(' + ' OR '.join(sorted(SHELF_PAPERS.values(), key=int)) + ')')}&format=json&resultType=core&pageSize=100", "the records of the papers cited for where proteins sit, with their abstracts")
    add("europepmc_fulltext_PMC2289639.xml", f"{EPMC}/PMC2289639/fullTextXML", "L'Hernault and Arduengo 1992, the open text: read for one sentence, on how the hydropathy scale is used to find membrane-spanning stretches")

    # Open articles under CC BY, from PubMed Central's open-data store, each with the
    # licence the store records: what the files say of division, of the usual reading of
    # the hydropathy scale and of where mycoplasmas' lipoproteins sit rests on these.
    for key, pmc in sorted(OPEN_TEXTS.items()):
        add(f"{open_prefix(key)}{pmc}.xml", f"{OPEN}/{pmc}.1/{pmc}.1.xml", f"the open text of the paper cited as {key}")
        add(f"{open_prefix(key)}{pmc}.json", f"{OPEN}/{pmc}.1/{pmc}.1.json", f"the licence PubMed Central records for the paper cited as {key}")

    # The terms of a rule system whose results UniProt gives out: reviewed entries state
    # places by HAMAP's family rules. Nothing else is asked of HAMAP.
    add("upstream_hamap_about.html", "https://hamap.expasy.org/hamap_about.html", "HAMAP's statement of its licence, read because reviewed UniProtKB entries state places by its family rules")

    # Terms of each source, read before anything was copied.
    add("terms_ncbi_genbank.html", "https://www.ncbi.nlm.nih.gov/genbank/", "GenBank's statement on the use of its data")
    add("terms_insdc_policy.html", "https://www.insdc.org/policy/", "the policy of the nucleotide sequence databases")
    add("terms_uniprot_license.json", f"{UNIPROT}/help/license", "UniProt's licence")
    add("terms_interpro_license.html", "https://interpro-documentation.readthedocs.io/en/latest/license.html", "InterPro's licence")
    add("terms_embl_ebi.html", "https://www.ebi.ac.uk/about/terms-of-use/", "EMBL-EBI's terms of use, which cover Europe PMC")
    add("link_check_ncbi_protein.html", "https://www.ncbi.nlm.nih.gov/protein/AVX54569.1", "NCBI's page of one protein identifier; it answers this tool with a browser check, so the identifier is looked up through E-utilities instead")
    add("link_check_ncbi_protein.json", f"{EUTILS}/esummary.fcgi?db=protein&id=AVX54569.1&retmode=json&tool=atlas-builder", "that NCBI holds a protein record under a protein identifier of the genome record (the page itself answers this tool with a browser check)")

    # Once the archive's answer is saved: the UniProtKB entries of other organisms whose
    # sequence is, letter for letter, one of this organism's proteins.
    archive = None if datasets is None else Path(datasets).joinpath(*place(f"uniparc_{TAXON}.json"))
    if archive is not None and archive.exists():
        archived = json.loads(archive.read_text(encoding="utf-8"))
        same = sorted({a for record in archived["results"] for a in record.get("uniProtKBAccessions", []) if "." not in a})
        if same:
            add("uniprotkb_identical.json", f"{UNIPROT}/uniprotkb/accessions?accessions={','.join(same)}&format=json&fields=accession,reviewed,organism_name,organism_id,protein_name", "the UniProtKB entries of other organisms with exactly the sequence of one of this organism's proteins")
            add("uniprotkb_identical_places.json", f"{UNIPROT}/uniprotkb/accessions?accessions={','.join(same)}&format=json&fields=accession,reviewed,organism_name,cc_subcellular_location,ft_transmem,ft_signal,ft_lipid,keyword", "what those entries state of where the protein sits in the cell")
    return out


# Where the downloads live. Each source has a folder of its own under the datasets folder,
# with a MANIFEST.json. Some folders were made by the project's Syn3A evidence audit: this
# tool reads them and never writes in them. The others it makes itself, and their note
# says so.

MINE = "the visualizer's Syn3A agent"
PROVIDED = {
    f"genbank_{RECORD}_summary.json": ("ncbi-CP016816.2", "CP016816.2_esummary.json"),
    f"genbank_{RECORD}_features.ft": ("ncbi-CP016816.2", "CP016816.2_feature_table.txt"),
    "elife_36842_supp3.xlsx": ("breuer2019-elife", "elife-36842-supp3-v3.xlsx"),
    "elife_36842_supp5.xlsx": ("breuer2019-elife", "elife-36842-supp5-v3.xlsx"),
    "proteomexchange_PXD008159.xml": ("massive-MSV000081687", "proteomexchange_PXD008159.xml"),
}
OWN = {
    "ncbi-CP016816-proteins": {"accession": "CP016816.2 and CP016816.1", "licence": "INSDC public data; NCBI places no restrictions on the use or distribution of GenBank data", "what": "JCVI-syn3A genome record: the protein product of each coding sequence in the frozen annotation and in its first version, the head of the record, and one protein record looked up by its identifier"},
    "ncbi-CP014940.1": {"accession": "CP014940.1", "licence": "INSDC public data", "what": "JCVI-syn3.0 genome record: its feature table, read only to check that strain's gene counts"},
    "uniprot-syn3a": {"licence": "CC BY 4.0", "what": "UniProt: the archived protein sequences of taxon 2144189 with the family signatures on them, the UniProtKB entries of other organisms with the same sequences, the signatures of the law inventory's human candidates, control counts in mollicutes and in Mycoplasma mycoides, and UniProt's licence"},
    "europepmc-syn3a-papers": {"licence": "Breuer and others 2019 and Gilbert and others 2021 are CC BY 4.0; the records are bibliographic facts", "what": "Europe PMC: the open full texts (JATS XML) of Breuer and others 2019 (PMC6609329) and Gilbert and others 2021 (PMC8339304), and the records of the papers cited, with their abstracts"},
    "ncbi-pmc-PMC9985924": {"pmcid": "PMC9985924", "doi": "10.1016/j.cell.2021.12.025", "licence": "CC BY-NC-ND 4.0", "what": "Thornburg and others 2022, the author manuscript (JATS XML). Since 15 November 2026 the build reads it only for the licence it states: nothing of it enters the files"},
    "pmc-open-syn3a-licence-pass": {"licence": "Each article's own, all CC BY: Zhang and others 2023 (CC BY 4.0), Paulet and others 2011 (CC BY 2.0), Christodoulides and others 2018 (CC BY 4.0). The JSON beside each article records it", "what": "Open articles from PubMed Central's open-data store (JATS XML), added by the licence pass of 15 November 2026 so that what the Syn3A files state rests on sources whose terms allow it: a review that reports the genes needed for division, a paper that states the usual reading of the hydropathy scale, and a review on the lipoproteins of mycoplasmas"},
    "terms-syn3a-sources": {"what": "Terms of use as read before anything was copied: GenBank's data usage statement, the policy of the nucleotide sequence databases, InterPro's licence and EMBL-EBI's terms"},
    "pmc-open-lipoprotein-signal": {"licence": "Each article's own, all CC BY 4.0: Desvaux and others 2018, Smithers and others 2021, Legood and others 2020. The JSON beside each article records it", "what": "Open articles from PubMed Central's open-data store (JATS XML), added on 15 November 2026: the reviews from which the Syn3A shelves' rule for a lipid anchor is fixed (the lipobox, and the parts and usual length of a lipoprotein's signal peptide), and one that says lipoboxes of other forms have been reported"},
    "terms-upstream-tools": {"what": "The terms of the tools and rule systems whose results a database gives out and the Syn3A shelves rest on, each as its own page states them. Added on 15 November 2026. Nothing but the page of terms was asked of any of them"},
    "biopython-185-protparam": {"licence": "Biopython License Agreement or BSD 3-Clause License", "what": "Biopython 1.85: the file that lists Kyte and Doolittle's hydropathy scale (Bio/SeqUtils/ProtParamData.py) and the licence file, saved as text; the 20 values the Syn3A shelves are computed with are checked against it"},
}
# Where the audit's folders are absent (another machine), the fetch step makes them itself.
ELSEWHERE = {
    "ncbi-CP016816.2": {"accession": "CP016816.2", "licence": "INSDC public data", "what": "JCVI-syn3A genome record: summary and feature table"},
    "breuer2019-elife": {"doi": "10.7554/eLife.36842", "pmcid": "PMC6609329", "licence": "CC BY 4.0", "what": "eLife supplementary files 3 and 5 (version 3)"},
    "massive-MSV000081687": {"accession": "MSV000081687 / PXD008159", "what": "The ProteomeXchange record of the 2019 proteomics"},
}
PLACES = [
    ("genbank_CP014940", "ncbi-CP014940.1"), ("genbank_", "ncbi-CP016816-proteins"), ("link_check_ncbi_protein", "ncbi-CP016816-proteins"),
    ("terms_uniprot", "uniprot-syn3a"), ("uniprot", "uniprot-syn3a"), ("uniparc", "uniprot-syn3a"), ("control_uniprotkb", "uniprot-syn3a"),
    ("europepmc", "europepmc-syn3a-papers"), ("ncbi_pmc", "ncbi-pmc-PMC9985924"), ("terms_", "terms-syn3a-sources"),
    ("biopython_185", "biopython-185-protparam"), ("rule_open_", "pmc-open-lipoprotein-signal"), ("open_", "pmc-open-syn3a-licence-pass"),
    ("upstream_", "terms-upstream-tools"),
]
HEADERS = [("X-Total-Results", "total_results"), ("X-UniProt-Release", "uniprot_release"), ("X-UniProt-Release-Date", "uniprot_release_date")]


def place(name):
    """The dataset folder of a request, and the name its file has there."""
    if name in PROVIDED:
        return PROVIDED[name]
    for prefix, source in PLACES:
        if name.startswith(prefix):
            return source, name
    raise SystemExit(f"no dataset folder is named for {name!r}")


def now():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def digest(path):
    sha, md5 = hashlib.sha256(), hashlib.md5()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            sha.update(block)
            md5.update(block)
    return sha.hexdigest(), md5.hexdigest()


def read_manifest(folder):
    path = Path(folder) / "MANIFEST.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def is_ours(manifest):
    return manifest is not None and MINE in manifest.get("note", "")


def manifest_entry(folder, file, record):
    """One file's entry in a MANIFEST, in the form the evidence audit's folders use."""
    sha, md5 = digest(Path(folder) / file)
    entry = {
        "name": file, "url": record["url"], "role": record["purpose"], "retrieved_utc": record["asked"], "http_status": record["status"],
        "content_type": record.get("content_type"), "size_bytes": (Path(folder) / file).stat().st_size, "sha256": sha, "md5": md5,
        "expected_size": None, "expected_md5": None, "ok": True, "error": None,
    }
    # What the service said beside the body, which a build needs and the body does not hold.
    for _, key in HEADERS:
        if record.get(key) is not None:
            entry["x_" + key] = record[key]
    return entry


def write_manifest(folder, source, entry, evidence):
    """Add or replace one file's entry in the MANIFEST of a folder this tool made."""
    manifest = read_manifest(folder) or {"source_id": source, "record": OWN.get(source) or ELSEWHERE[source], "files": []}
    if manifest["files"] and not is_ours(manifest):
        raise SystemExit(f"{folder} was not made by this tool; nothing is written there")
    manifest["files"] = sorted([item for item in manifest["files"] if item["name"] != entry["name"]] + [entry], key=lambda item: item["name"])
    manifest["manifest_written_utc"] = now()
    manifest["note"] = f"Added by {MINE}: downloaded as untrusted data by tools/build_syn3a_atlas.py of the Cells checkout (analysis in {evidence}). Nothing here was executed."
    (Path(folder) / "MANIFEST.json").write_text(json.dumps(manifest, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")


def load_log(evidence):
    path = Path(evidence) / "requests.json"
    if not path.exists():
        return {"client": CLIENT, "note": "Every request this tool made for the Syn3A data: what was asked, when, what came back and where it was saved.", "requests": []}
    return json.loads(path.read_text(encoding="utf-8"))


def fetch(evidence, datasets, snapshot, refresh=False, pause=0.6, tries=5):
    """Ask every request whose file is not yet in its dataset folder; save the body as it
    came, with its entry in that folder's MANIFEST and a line in the request log."""
    evidence, datasets = Path(evidence), Path(datasets)
    evidence.mkdir(parents=True, exist_ok=True)
    log = load_log(evidence)
    done = {item["name"]: item for item in log["requests"]}
    asked = failed = 0
    seen = set()
    while True:
        todo = [request for request in requests(snapshot, datasets) if request["name"] not in seen]
        if not todo:
            break
        for request in todo:
            seen.add(request["name"])
            source, file = place(request["name"])
            folder = datasets / source
            manifest = read_manifest(folder)
            held = (folder / file).exists() and any(item["name"] == file for item in (manifest or {}).get("files", []))
            if held and not (refresh and is_ours(manifest)):
                continue
            if folder.exists() and not is_ours(manifest):
                # A folder this tool did not make is read and never written.
                print(f"missing  {source}/{file}: the folder was made by another agent, so nothing is written there", flush=True)
                failed += 1
                continue
            record, body = dict(request), None
            call = urllib.request.Request(request["url"], headers={"User-Agent": CLIENT, "Accept-Encoding": "identity"})
            for attempt in range(tries):
                record = dict(request, asked=now())
                try:
                    with urllib.request.urlopen(call, timeout=600) as answer:
                        body = answer.read()
                        record["status"] = answer.status
                        for header, key in [*HEADERS, ("Last-Modified", "last_modified"), ("Content-Type", "content_type")]:
                            if answer.headers.get(header):
                                record[key] = answer.headers[header]
                    record["bytes"] = len(body)
                    break
                except urllib.error.HTTPError as error:
                    record["status"] = error.code
                    if error.code < 500 and error.code != 429:
                        break
                except (urllib.error.URLError, TimeoutError, OSError) as error:
                    record["status"] = 0
                    record["error"] = str(getattr(error, "reason", error))[:200]
                # A busy service: wait and ask again.
                if attempt + 1 < tries:
                    time.sleep(15)
            if record["status"] == 200:
                # The folder is made only if it is not there at this moment. If another agent
                # has just added the same source, theirs is used and nothing is written.
                try:
                    folder.mkdir(parents=True)
                except FileExistsError:
                    pass
                if (folder / "MANIFEST.json").exists() and not is_ours(read_manifest(folder)):
                    print(f"skipped  {source}/{file}: the folder was just made by another agent", flush=True)
                    failed += not (folder / file).exists()
                    continue
                (folder / file).write_bytes(body)
                entry = manifest_entry(folder, file, record)
                write_manifest(folder, source, entry, evidence)
                record.update(source=source, file=file, sha256=entry["sha256"])
            failed += record["status"] != 200
            done[request["name"]] = record
            asked += 1
            print(f"{record['status']}  {source}/{file}  {record.get('bytes', '')}", flush=True)
            log["requests"] = [done[name] for name in sorted(done)]
            (evidence / "requests.json").write_text(json.dumps(log, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
            time.sleep(pause)
    print(f"asked {asked} request(s), {failed} failed or missing; {len(done)} on record in {evidence / 'requests.json'}")
    return failed


# ---------------------------------------------------------------------------------------
# Reading what was saved
# ---------------------------------------------------------------------------------------

class Evidence:
    """The downloads, each read through its MANIFEST and checked against it, and the log of
    what this tool asked."""

    def __init__(self, folder, datasets):
        self.folder, self.datasets = Path(folder), Path(datasets)
        self.log = {item["name"]: item for item in load_log(self.folder)["requests"]}
        self.manifests = {}
        self.read = {}

    def entry(self, name):
        source, file = place(name)
        if source not in self.manifests:
            manifest = read_manifest(self.datasets / source)
            if manifest is None:
                raise SystemExit(f"no dataset folder {source!r} with a MANIFEST; run the fetch step first")
            self.manifests[source] = manifest
        entry = next((item for item in self.manifests[source]["files"] if item["name"] == file), None)
        if entry is None:
            raise SystemExit(f"the MANIFEST of {source} does not list {file!r}; run the fetch step first")
        return source, file, entry

    def path(self, name):
        source, file, entry = self.entry(name)
        path = self.datasets / source / file
        if name not in self.read:
            if not path.exists():
                raise SystemExit(f"{source}/{file} is listed in its MANIFEST and is not there")
            sha, _ = digest(path)
            if sha != entry["sha256"]:
                raise SystemExit(f"{source}/{file} is not the file its MANIFEST describes")
            if is_ours(self.manifests[source]) and self.log.get(name, {}).get("sha256") != sha:
                raise SystemExit(f"the request log does not hold {source}/{file} as the dataset folder has it")
            self.read[name] = {"name": name, "source": source, "file": file, "sha256": sha, "bytes": path.stat().st_size, "retrieved_utc": entry["retrieved_utc"]}
        return path

    def record(self, name):
        """What is on record of a file: when it was retrieved, and what the service said beside the body."""
        self.path(name)
        entry = self.entry(name)[2]
        record = {"asked": entry["retrieved_utc"]}
        for _, key in HEADERS:
            if entry.get("x_" + key) is not None:
                record[key] = entry["x_" + key]
        return record

    def text(self, name):
        return self.path(name).read_text(encoding="utf-8", errors="replace")

    def json(self, name):
        return json.loads(self.text(name))

    def total(self, name):
        return int(self.record(name)["total_results"])

    def day(self, name):
        return self.record(name)["asked"][:10]

    def plain(self, name):
        """A saved page or article as running text: no markup, single spaces."""
        return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", self.text(name)))

    def files_read(self):
        return [self.read[name] for name in sorted(self.read)]


def natural(tag):
    return [int(part) if part.isdigit() else part for part in re.split(r"(\d+)", tag)]


def coding_sequences(text):
    """The coding sequences of a genome record's protein listing: the fields of each header and the sequence."""
    out = []
    for block in re.split(r"(?m)^>", text)[1:]:
        head, _, body = block.partition("\n")
        out.append({**dict(re.findall(r"\[(\w+)=([^\]]*)\]", head)), "sequence": "".join(body.split())})
    return out


def features(text):
    """A feature table as genes: each with its locus tag and the kinds of feature it carries."""
    genes = []
    for block in re.split(r"\n(?=[<>]?\d+\t[<>]?\d+\tgene)", text)[1:]:
        genes.append({
            "locus": re.search(r"locus_tag\t(\S+)", block).group(1),
            "kinds": re.findall(r"^[<>]?\d+\t[<>]?\d+\t(\S+)", block, re.M),
            "pseudo": "\tpseudo" in block,
        })
    return genes


def sheet(path, name):
    """The rows of one sheet of a spreadsheet file, as lists of strings."""
    space = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main", "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships"}
    with zipfile.ZipFile(path) as book:
        shared = []
        if "xl/sharedStrings.xml" in book.namelist():
            for item in ElementTree.fromstring(book.read("xl/sharedStrings.xml")).findall("m:si", space):
                shared.append("".join(node.text or "" for node in item.iter("{%s}t" % space["m"])))
        targets = {rel.get("Id"): rel.get("Target") for rel in ElementTree.fromstring(book.read("xl/_rels/workbook.xml.rels"))}
        for entry in ElementTree.fromstring(book.read("xl/workbook.xml")).find("m:sheets", space):
            if entry.get("name") != name:
                continue
            target = targets[entry.get("{%s}id" % space["r"])].lstrip("/")
            rows = []
            for row in ElementTree.fromstring(book.read(target if target.startswith("xl/") else "xl/" + target)).iter("{%s}row" % space["m"]):
                cells = {}
                for cell in row.findall("m:c", space):
                    letters = re.match(r"[A-Z]+", cell.get("r")).group(0)
                    column = 0
                    for letter in letters:
                        column = column * 26 + ord(letter) - 64
                    value = cell.find("m:v", space)
                    if cell.get("t") == "s" and value is not None:
                        content = shared[int(value.text)]
                    elif cell.get("t") == "inlineStr":
                        content = "".join(node.text or "" for node in cell.iter("{%s}t" % space["m"]))
                    else:
                        content = value.text if value is not None else ""
                    cells[column - 1] = content.strip()
                rows.append([cells.get(i, "") for i in range(max(cells) + 1)] if cells else [])
            return rows
    raise SystemExit(f"{path.name} has no sheet named {name!r}")


class Context:
    """Everything the build reads, checked as it is read."""

    def __init__(self, evidence, snapshot):
        self.evidence = ev = evidence
        self.snapshot = snapshot

        # The genome record.
        summary = next(value for key, value in ev.json(f"genbank_{RECORD}_summary.json")["result"].items() if key != "uids")
        if summary["accessionversion"] != RECORD or int(summary["taxid"]) != TAXON or summary["topology"] != "circular":
            raise SystemExit("the genome record is not the one the files name")
        self.length = int(summary["slen"])
        self.record_title = summary["title"]
        self.record_day = summary["updatedate"].replace("/", "-")
        head = ev.text(f"genbank_{RECORD}_head.gb")
        made_from = re.search(r'/isolation_source="([^"]+)"', head)
        self.made_from = re.sub(r"\s+", " ", made_from.group(1)) if made_from else None
        if not self.made_from or "Mycoplasma mycoides subspecies capri strain GM12" not in self.made_from:
            raise SystemExit("the genome record no longer says what the organism was made from")
        self.genes = features(ev.text(f"genbank_{RECORD}_features.ft"))
        self.kinds = Counter(kind for gene in self.genes for kind in gene["kinds"] if kind != "gene")
        coding = coding_sequences(ev.text(f"genbank_{RECORD}_cds_aa.fa"))
        self.pseudo = sorted((item["locus_tag"] for item in coding if item.get("pseudo") == "true"), key=natural)
        self.proteins = sorted((item for item in coding if item.get("protein_id")), key=lambda item: natural(item["locus_tag"]))
        if len({item["locus_tag"] for item in self.proteins}) != len(self.proteins) or len(self.pseudo) + len(self.proteins) != len(coding):
            raise SystemExit("the coding sequences of the genome record are not one per locus tag")

        # UniProt's archive: the same sequences, with the family signatures on them.
        archive = ev.json(f"uniparc_{TAXON}.json")["results"]
        if len(archive) != ev.total(f"uniparc_{TAXON}.json"):
            raise SystemExit("the archive's answer is not complete")
        self.uniprot_release = ev.record(f"uniparc_{TAXON}.json")["uniprot_release"]
        by_sequence = {record["sequence"]["value"]: record for record in archive}
        if set(by_sequence) != {item["sequence"] for item in self.proteins}:
            raise SystemExit("the archive's sequences are not exactly the genome record's protein products")
        for item in self.proteins:
            record = by_sequence[item["sequence"]]
            item["uniparc"] = record["uniParcId"]
            item["interpro"] = sorted({feature["interproGroup"]["id"] for feature in record.get("sequenceFeatures", []) if feature.get("interproGroup")})
            item["same"] = sorted(a for a in record.get("uniProtKBAccessions", []) if "." not in a)
        self.signature_names = {feature["interproGroup"]["id"]: feature["interproGroup"]["name"] for record in archive for feature in record.get("sequenceFeatures", []) if feature.get("interproGroup")}
        self.by_locus = {item["locus_tag"]: item for item in self.proteins}
        self.kb_entries = ev.json(f"uniprot_taxonomy_{TAXON}.json").get("statistics", {})
        if ev.json(f"uniprot_taxonomy_{MOLLICUTES}.json")["scientificName"] != "Mollicutes":
            raise SystemExit("the taxon of the controls is not the mollicutes")
        if ev.json(f"uniprot_taxonomy_{PARENT_SPECIES}.json")["scientificName"] != "Mycoplasma mycoides":
            raise SystemExit("the taxon of the parent species is not Mycoplasma mycoides")
        self.identical = {entry["primaryAccession"]: entry for entry in ev.json("uniprotkb_identical.json")["results"]} if any(item["same"] for item in self.proteins) else {}
        self.places = {entry["primaryAccession"]: entry for entry in ev.json("uniprotkb_identical_places.json")["results"]} if self.identical else {}
        if set(self.places) != set(self.identical):
            raise SystemExit("the two answers on the entries with identical sequences do not list the same entries")

        # The units' human candidates: the signatures they carry.
        self.human = {entry["primaryAccession"]: {x["id"] for x in entry.get("uniProtKBCrossReferences", []) if x["database"] == "InterPro"} for entry in ev.json("uniprotkb_human_candidates.json")["results"]}

        # The 2019 paper's tables.
        rows = sheet(ev.path("elife_36842_supp3.xlsx"), "Essentiality")
        head = rows[0]
        at = {name: head.index(name) for name in ["Locus name (syn3A)", "Feature type", "Gene", "product", "Primary functional class", "Secondary functional class", "Tertiary functional class", "Essentiality"]}
        self.classes = {}
        for row in rows[1:]:
            row = row + [""] * (len(head) - len(row))
            if row[at["Locus name (syn3A)"]]:
                self.classes[row[at["Locus name (syn3A)"]]] = {name: row[index] for name, index in at.items()}
        self.class_kinds = Counter(item["Feature type"] for item in self.classes.values())
        rows = sheet(ev.path("elife_36842_supp5.xlsx"), "Proteomics")
        if rows[0][21] != "Absolute abundance (copy number per average cell)" or rows[1][0] != "Protein" or rows[1][21] != "Time point 1, median":
            raise SystemExit("the proteomics table is not laid out as it was read")
        first = {item["protein_id"]: item["sequence"] for item in coding_sequences(ev.text(f"genbank_{FIRST_RECORD}_cds_aa.fa")) if item.get("protein_id")}
        to_locus = {item["sequence"]: item["locus_tag"] for item in self.proteins}
        self.abundance = {}
        for row in rows[2:]:
            if row and re.match(r"[A-Z]{3}\d+\.\d+$", row[0]):
                if row[0] not in first or first[row[0]] not in to_locus:
                    raise SystemExit(f"the proteomics row {row[0]} cannot be tied to a protein of the frozen annotation")
                self.abundance[to_locus[first[row[0]]]] = {"id": row[0], "copies": float(row[21])}
        total = next(row for row in rows if len(row) > 21 and row[5] == "Sum:")
        self.copies_total = round(float(total[21]))

    def carriers(self, signature):
        return [item for item in self.proteins if signature in item["interpro"]]

    def mollicutes(self, signature):
        return self.evidence.total(f"control_uniprotkb_{signature}_{MOLLICUTES}.json")

    def parent(self, signature):
        return self.evidence.total(f"control_uniprotkb_{signature}_{PARENT_SPECIES}.json")


# ---------------------------------------------------------------------------------------
# Checks: the saved sources must still say what the files state
# ---------------------------------------------------------------------------------------

BREUER, GILBERT, THORNBURG = "europepmc_fulltext_PMC6609329.xml", "europepmc_fulltext_PMC8339304.xml", "ncbi_pmc_9985924.xml"
LHERNAULT = "europepmc_fulltext_PMC2289639.xml"
ZHANG, PAULET, CHRISTODOULIDES, DESVAUX, SMITHERS, LEGOOD = (open_file(key) for key in ("zhang2023", "paulet2011", "christodoulides2018", "desvaux2018", "smithers2021", "legood2020"))
# Every statement the files make from a paper is checked here against the saved text of a
# permissive source. The two texts under non-commercial terms are read for their licence
# statement alone.
SAID = [
    (BREUER, r"consistently forms spherical cells of approximately 400 nm in diameter"),
    (BREUER, r"543 kbp genome containing 493 genes of which 452 code for proteins and 38 for RNAs"),
    (BREUER, r"This entry contains 498 genomic features, however three of those are pseudo-genes and two are genes required for cloning in yeast"),
    (BREUER, r"JCVI-syn3A has a doubling time of 105 min"),
    (BREUER, r"bacteria with a single membrane and no periplasmic space"),
    (BREUER, r"While mycoplasmas lack a cell wall"),
    (BREUER, r"this amounts to ∼ ?77,000 proteins"),
    (BREUER, r"we use the data from the first time point \(logarithmic phase\)"),
    (BREUER, r"rich and not fully defined SP4 media"),
    (BREUER, r"the import of four lipid components is necessary: free fatty acids, glycerol, cholesterol and triacylglycerol"),
    (BREUER, r"While it is not clear how mycoplasmas secrete acetate, lactate and pyruvate"),
    (BREUER, r"The only annotated sugar importer in the JCVI-syn3A genome is the glucose PTS system"),
    (BREUER, r"all other ATPase subunits \( ?atpD/ ?0790 through atpB/ ?0796 ?\) were essential"),
    (BREUER, r"Total 100\. 428 100\. 452 271 113 68"),
    (BREUER, r"JCVI-syn3A still has a smaller genome than any natural autonomously replicating cell"),
    (BREUER, r"reliance on fermentative ATP production"),
    (BREUER, r"Central metabolism as the only source of ATP"),
    (BREUER, r"a passive H \+ influx reaction is used, which is counteracted by the proton-extruding ATPase"),
    (BREUER, r"the small number of identified regulatory proteins left in the genome of JCVI-syn3A"),
    (BREUER, r"restore consistent morphologic features and increase the growth rate"),
    (BREUER, r"19 additional genes from JCVI-syn1\.0 segment six that were not present in JCVI-syn3\.0, including those encoding the cell partitioning proteins FtsZ and SepF"),
    (BREUER, r"Creative Commons Attribution License"),
    (ZHANG, r"Nineteen genes were added into JCVI-syn3\.0 to generate JCVI-syn3A"),
    (ZHANG, r"Seven genes of the nineteen genes were necessarily together for normal cell division, including two known cell division genes, ftsZ and sepF"),
    (ZHANG, r"Creative Commons Attribution \(CC BY\) license \( ?https://creativecommons\.org/licenses/by/4\.0/ ?\)"),
    (PAULET, r"based on a sliding window of 19 amino acids: if a position has an average value of hydrophobicity higher than the threshold of 1\.6, it corresponds to a TMS"),
    (PAULET, r"Creative Commons Attribution License \( ?http://creativecommons\.org/licenses/by/2\.0 ?\)"),
    (CHRISTODOULIDES, r"mycoplasmas usually induce an inflammatory and a humoral response preferentially directed against their membrane-bound, surface-exposed lipoproteins"),
    (CHRISTODOULIDES, r"Creative Commons Attribution License \(CC BY\)"),
    # The lipid-anchor rule: the lipobox, for bacteria with one membrane, among which the
    # mollicutes are counted; and the parts and usual length of a lipoprotein's signal peptide.
    (DESVAUX, r"The consensus sequence for the lipobox is \[LVI\] -3 -\[ASTVI\] -2 -\[GAS\] -1 -\[C\] \+1"),
    (DESVAUX, r"monoderm bacteria refer to species exhibiting only one biological membrane"),
    (DESVAUX, r"bacteria of the class Mollicutes, comprising the genus Mycoplasma , cannot retain the Gram stain because they naturally lack a CW"),
    (DESVAUX, r"creativecommons\.org/licenses/by/4\.0/ This is an open-access article distributed under the terms of the Creative Commons Attribution License \(CC BY\)"),
    (SMITHERS, r"an N-terminal signal peptide that is on average 16–26 residues long"),
    (SMITHERS, r"The signal peptide has three recognizable parts: an N-terminal positively charged sequence, a hydrophobic helix \(h-region\), and a C-terminal lipobox"),
    (SMITHERS, r"creativecommons\.org/licenses/by/4\.0/ This is an open-access article distributed under the terms of the Creative Commons Attribution License \(CC BY\)"),
    (LEGOOD, r"Variations in lipobox sequences have been reported but the invariant cysteine residue is always present"),
    (LEGOOD, r"This is an open access article under the terms of the http://creativecommons\.org/licenses/by/4\.0/ License"),
    (GILBERT, r"small cell of radius 201\.26 nm with 503 ribosomes and large cell of radius 247\.42 nm with 820 ribosomes"),
    (GILBERT, r"small cell of radius 203\.52 nm with 684 ribosomes and large cell of radius 241\.20 nm with 1,095 ribosomes"),
    (GILBERT, r"the synthetic cells lack a cell wall"),
    (GILBERT, r"ribosomes appear to be nearly randomly distributed throughout the cell"),
    (GILBERT, r"Creative Commons Attribution License \(CC BY\)"),
    (THORNBURG, r"CC BY-NC-ND license"),
    ("biopython_185_ProtParamData.py", r'governed by your\s+#\s+choice of the "Biopython License Agreement" or the "BSD 3-Clause License"'),
    ("biopython_185_ProtParamData.py", r"# Kyte & Doolittle index of hydrophobicity\s+# J\. Mol\. Biol\. 157:105-132\(1982\)\."),
    ("biopython_185_LICENSE.rst", r"Permission to use, copy, modify, and distribute this software and its\s+documentation with or without modifications and for any purpose and\s+without fee is hereby granted"),
    (LHERNAULT, r"creativecommons\.org/licenses/by-nc-sa/4\.0"),
    ("terms_ncbi_genbank.html", r"NCBI places no restrictions on the use or distribution of the GenBank data"),
    ("terms_insdc_policy.html", r"no use restrictions or licensing requirements will be included in any sequence data records"),
    ("terms_uniprot_license.json", r"Creative Commons Attribution 4\.0 International \(CC BY 4\.0\) License"),
    ("terms_interpro_license.html", r"CC0"),
    ("upstream_hamap_about.html", r"HAMAP is copyrighted by the SIB Swiss Institute of Bioinformatics and distributed under the Creative Commons Attribution \(CC BY 4\.0\) License"),
    ("terms_embl_ebi.html", r"EMBL-EBI itself places no additional restrictions on the use or redistribution of the data available via its Data Resources and Tools other than those provided by the original data owners"),
    ("proteomexchange_PXD008159.xml", r'title="JCVI_Syn3A"'),
]


def check_sources(c):
    ev = c.evidence
    for name, words in SAID:
        if not re.search(words, ev.plain(name) if name.endswith((".xml", ".html")) and "proteomexchange" not in name else ev.text(name)):
            raise SystemExit(f"{name} no longer says: {words}")
    papers = {record["pmid"]: record for record in ev.json("europepmc_citations.json")["resultList"]["result"]}
    if set(PAPERS.values()) - set(papers):
        raise SystemExit("a cited paper's record was not returned")
    # The class each source is given rests on a saved record of its licence: PubMed
    # Central's own record of an open article, or the paper's bibliographic record, which
    # either names a licence or names none and says the paper is not open.
    for key, pmc in OPEN_TEXTS.items():
        recorded = ev.json(open_file(key, "json"))
        if recorded["license_code"] != "CC BY" or recorded["pmcid"] != pmc or recorded["is_retracted"]:
            raise SystemExit(f"PubMed Central no longer records {pmc}, the paper cited as {key}, as an open article under CC BY")
    shelf_papers = {record["pmid"]: record for record in ev.json("europepmc_shelves_citations.json")["resultList"]["result"]}
    recorded_as = {"breuer2019": "cc by", "gilbert2021": "cc by", "thornburg2022": "cc by-nc-nd", "pelletier2021": None, "lhernault1992": "cc by-nc-sa", "chambaud1999": None, "kyte1982": None}
    for key, licence in recorded_as.items():
        record = papers[PAPERS[key]] if key in PAPERS else shelf_papers[SHELF_PAPERS[key]]
        expected = PERMISSIVE if licence == "cc by" else NON_COMMERCIAL if licence else NO_TERMS
        if record.get("license") != licence or (licence is None and record.get("isOpenAccess") != "N") or CLASSES[key] != expected:
            raise SystemExit(f"the record of the paper cited as {key} no longer states the licence its class rests on")
    # The counts the files state, from the record and the paper's own table.
    expected = {"CDS": 458, "tRNA": 29, "rRNA": 6, "ncRNA": 2, "tmRNA": 1, "misc_binding": 2}
    if dict(c.kinds) != expected or len(c.genes) != 496 or len(c.proteins) != 455 or len(c.pseudo) != 3 or c.length != 543379:
        raise SystemExit(f"the genome record's counts are not the ones the files state: {dict(c.kinds)}, {len(c.genes)} genes, {len(c.proteins)} protein products, {c.length} bp")
    if dict(c.class_kinds) != {"CDS": 452, "manip": 3, "pseudo": 3, "tRNA": 29, "rRNA": 6, "ncRNA": 2, "misc_binding": 2, "tmRNA": 1}:
        raise SystemExit(f"the 2019 table's feature types are not the ones the files state: {dict(c.class_kinds)}")
    table = {locus for locus, item in c.classes.items() if item["Feature type"] in ("CDS", "manip")}
    if table != set(c.by_locus) or {locus for locus, item in c.classes.items() if item["Feature type"] == "pseudo"} != set(c.pseudo):
        raise SystemExit("the 2019 table and the genome record do not list the same protein-coding genes")
    if len(c.abundance) != 428 or c.copies_total != 77028:
        raise SystemExit(f"the proteomics table no longer holds 428 proteins summing to 77,028 copies: {len(c.abundance)}, {c.copies_total}")
    smaller = features(ev.text(f"genbank_{SYN30_RECORD}_features.ft"))
    if len(smaller) != 473 or sum("CDS" in gene["kinds"] for gene in smaller) != 438:
        raise SystemExit("the record of JCVI-syn3.0 no longer has 473 genes and 438 coding sequences")
    if c.kb_entries.get("reviewedProteinCount") or c.kb_entries.get("unreviewedProteinCount"):
        raise SystemExit("UniProtKB now holds entries of the organism; read them and rewrite what the files say")
    # Each family signature is carried by a human candidate of a unit that searches it, so
    # the search can find the family where it exists.
    carried = set().union(*c.human.values())
    for key, family in FAMILIES.items():
        if family.get("human", True) and family["signatures"][0] not in carried:
            raise SystemExit(f"no human candidate carries {family['signatures'][0]} ({key})")
    # Nothing was found: the notes are written for that, and must be rewritten otherwise.
    found = {signature: [item["locus_tag"] for item in c.carriers(signature)] for signature in [*rule_signatures(), *BACTERIAL_CHANNELS, PROTEASOME]}
    if any(found.values()):
        raise SystemExit(f"a signature now finds a protein; read it and rewrite the notes: { {k: v for k, v in found.items() if v} }")
    # The sentence on channels says the search finds them in other mollicutes.
    if not all(c.mollicutes(signature) for signature in BACTERIAL_CHANNELS):
        raise SystemExit("a bacterial channel signature finds no mollicute entry; rewrite what is said of the channels")
    for locus, name in [("JCVISYN3A_0039", "ftsH"), ("JCVISYN3A_0394", "lon"), ("JCVISYN3A_0522", "ftsZ"), ("JCVISYN3A_0521", "sepF"), ("JCVISYN3A_0652", "secY"), ("JCVISYN3A_0908", "yidC")]:
        if c.by_locus[locus].get("gene") != name:
            raise SystemExit(f"{locus} is no longer annotated {name}")
    for item in EXTRA:
        protein = c.by_locus[item["locus"]]
        if item.get("signature") and item["signature"] not in protein["interpro"]:
            raise SystemExit(f"{item['locus']} does not carry {item['signature']}")
        if item.get("words") and not re.search(item["words"], ev.plain(BREUER)):
            raise SystemExit(f"the 2019 paper no longer names {item['locus']} as the files say")
    # The identifiers the atlas gives are NCBI's protein identifiers: one is looked up.
    looked_up = next(value for key, value in ev.json("link_check_ncbi_protein.json")["result"].items() if key != "uids")
    if looked_up["accessionversion"] != c.by_locus["JCVISYN3A_0001"]["protein_id"] or int(looked_up["taxid"]) != TAXON:
        raise SystemExit("NCBI no longer returns the protein record of the first locus under its identifier")
    for locus in ("JCVISYN3A_0787", "JCVISYN3A_0879"):
        if "IPR001757" not in c.by_locus[locus]["interpro"]:
            raise SystemExit(f"{locus} no longer carries the P-type ATPase signature")
    if "IPR006415" not in c.by_locus["JCVISYN3A_0787"]["interpro"] or c.signature_names["IPR006415"] != "P-type ATPase, subfamily IIIB":
        raise SystemExit("locus 0787 is no longer placed in the P-type ATPases' branch IIIB")


# ---------------------------------------------------------------------------------------
# Building
# ---------------------------------------------------------------------------------------

def citation(c, key):
    record = next(r for r in c.evidence.json("europepmc_citations.json")["resultList"]["result"] if r["pmid"] == PAPERS[key])
    first = record["authorString"].split(",")[0].rsplit(" ", 1)[0]
    journal = record["journalInfo"]["journal"]
    where = journal["title"] if " " not in journal["title"] else (journal.get("isoabbreviation") or journal["title"])
    volume = record["journalInfo"].get("volume")
    pages = record.get("pageInfo")
    tail = f" {volume}:{pages}." if volume and pages else (f" {volume}." if volume else ".")
    return {"text": f"{first} and others ({record['pubYear']}) {record['title'].rstrip('.')}. {where}{tail}", "doi": record["doi"], "pmid": record["pmid"]}


def open_paper(c, key):
    """An open article read from PubMed Central's open-data store: who wrote it, its citation,
    and the day it was read. The authors are read from the article's own front matter."""
    pmc = OPEN_TEXTS[key]
    recorded = c.evidence.json(open_file(key, "json"))
    front = c.evidence.text(open_file(key)).split("</article-meta>")[0]
    authors = re.findall(r'<contrib[^>]*contrib-type="author"[^>]*>.*?<surname>([^<]+)</surname>', front, re.S)
    where = re.fullmatch(r"(?P<journal>.+?)\. (?P<year>\d{4})[^;]*;(?P<place>[^.]+)\. doi: \S+", recorded["citation"])
    if not authors or not where:
        raise SystemExit(f"the saved record of {pmc} cannot be read as a citation")
    who = authors[0] if len(authors) == 1 else f"{authors[0]} and {authors[1]}" if len(authors) == 2 else f"{authors[0]} and others"
    return {"who": who, "year": where["year"], "text": f"{who} ({where['year']}) {recorded['title'].rstrip('.')}. {where['journal']} {where['place']}.", "doi": recorded["doi"], "pmid": str(recorded["pmid"]), "accessed": c.evidence.day(open_file(key))}


POINTER = "It is named so that it can be read, and nothing is taken from it."


def sources_of_species(c):
    ev = c.evidence
    out = {}
    for key, name in [("breuer2019", BREUER), ("gilbert2021", GILBERT)]:
        cite = citation(c, key)
        out[key] = {"text": cite["text"], "doi": cite["doi"], "licence": LICENCES[key], "class": CLASSES[key], "accessed": ev.day(name)}
    review = open_paper(c, "zhang2023")
    out["zhang2023"] = {"text": review["text"] + " A review.", "doi": review["doi"], "licence": OPEN_LICENCE["zhang2023"], "class": CLASSES["zhang2023"], "accessed": review["accessed"]}
    # Pointers: where to read what these files do not take.
    cite = citation(c, "thornburg2022")
    out["thornburg2022"] = {
        "text": cite["text"] + " A whole-cell model of this organism: its own account of the cell's energy, its membrane proteins and its regulation is there.",
        "doi": cite["doi"], "licence": LICENCES["thornburg2022"] + ", a non-commercial licence. " + POINTER, "class": CLASSES["thornburg2022"], "accessed": ev.day(THORNBURG),
    }
    cite = citation(c, "pelletier2021")
    out["pelletier2021"] = {
        "text": cite["text"] + " The experiments on which genes this organism needs to divide. Only its bibliographic record was read.",
        "doi": cite["doi"], "licence": "No open licence stated: the paper's record names none and does not count it as open access. " + POINTER, "class": CLASSES["pelletier2021"], "accessed": ev.day("europepmc_citations.json"),
    }
    out["genbank"] = {
        "text": f"Glass J (2017) {c.record_title}. GenBank {RECORD}, annotation of 12 April 2018.",
        "url": f"https://www.ncbi.nlm.nih.gov/nuccore/{RECORD}",
        "licence": "NCBI places no restrictions on the use or distribution of GenBank data; submitters may claim rights in what they submitted, and this record states none",
        "class": PERMISSIVE,
        "accessed": ev.day(f"genbank_{RECORD}_features.ft"),
    }
    out["uniparc"] = {
        "text": f"UniProt Consortium, UniParc release {c.uniprot_release}: the archived protein sequences of taxon {TAXON} and the family signatures on them.",
        "url": f"https://www.uniprot.org/uniparc?query=taxonomy_id:{TAXON}",
        "licence": "CC BY 4.0",
        "class": PERMISSIVE,
        "accessed": ev.day(f"uniparc_{TAXON}.json"),
    }
    return out


def build_species(c):
    count = len(c.proteins)
    seen_kept = sum(c.classes[locus]["Feature type"] == "CDS" for locus in c.abundance)
    seen_added = sorted(c.by_locus[locus].get("gene") or locus for locus in c.abundance if c.classes[locus]["Feature type"] != "CDS")
    if seen_added != ["tetM"]:
        raise SystemExit(f"the added genes seen in the proteomics are no longer tetM alone: {seen_added}")
    capabilities = {
        "cap.membrane": {"place": "present", "note": "Its one membrane holds the cell's ion and proton gradients. In the 2019 reconstruction of its metabolism the ATP synthase pushes protons out, against a passive leak of protons inwards; that is a model's reading, and no source read for this file measured the voltage of this strain."},
        "cap.channels": {"place": "absent", "why": f"No ion channel was found among its {count} proteins: none carries the signature of a channel family in Cells' catalogue, or of the bacterial channels for potassium, chloride, magnesium, water or membrane stretch, which the same search does find in other mollicutes. Its ions cross the membrane through transporters and pumps."},
        "cap.pumps": {"place": "present", "note": "Not the pumps of animal cells: it has no sodium-potassium pump. By its annotation, its ATP-driven ion movers are the ATP synthase, two P-type ATPases named as magnesium transporters, and a potassium uptake system."},
        "cap.junctions": {"place": "absent", "why": "It lives as single cells and has no gap junctions: none of its proteins carries the signature of connexins or innexins."},
        "cap.extracellular": {"place": "present", "note": "Here it is the growth medium around the single cell, which the cell depends on. By the 2019 reconstruction of its metabolism it takes up glucose, amino acids, fatty acids and cholesterol from a rich medium."},
        "cap.water": {"place": "present", "note": "It has no cell wall: nothing but the membrane bounds its volume."},
        "cap.calcium": {"place": "absent", "why": "It has no endoplasmic reticulum: it is a bacterium with a single membrane and no internal compartments, and none of its proteins carries the signature of the store's calcium pump or of its release channels."},
        "cap.energy": {"place": "present", "note": "Its ATP comes from fermenting sugar in the cytoplasm: in the 2019 reconstruction of its metabolism, central metabolism is the only source of ATP."},
        "cap.mitochondria": {"place": "absent", "why": "It is a bacterium and has no mitochondria. Its ATP synthase sits in the cell membrane."},
        "cap.circuits": {"place": "present", "note": "At the chromosome, which lies in the cytoplasm: there is no nucleus. The 2019 paper notes how few regulatory proteins the minimised genome has left."},
        "cap.grn": {"place": "absent", "why": "It forms no tissue, so there is nothing for gene networks to be coupled across. Gene expression within the one cell belongs with regulatory circuits."},
        "cap.trafficking": {"place": "absent", "why": "It has no endoplasmic reticulum and no Golgi. By its annotation, new membrane proteins are put straight into the cell membrane by the Sec translocon and the YidC insertase."},
        "cap.assembly": {"place": "present", "note": "Its assemblies are its ribosomes, RNA polymerase and the ATP synthase. The designed protein cage that Cells models is not one of its proteins."},
        "cap.machines": {"place": "present", "note": "About 500 ribosomes, with RNA polymerase, the ATP synthase and the protein translocon. None of its proteins carries the proteasome's signature; its annotation lists the proteases FtsH and Lon."},
        "cap.secretion": {"place": "present", "note": "By the 2019 reconstruction of its metabolism it releases the end products of sugar breakdown, lactate and acetate, into the medium and takes nutrients up. Signalling between its cells was not looked for."},
        "cap.repair": {"place": "present", "note": "The place would be its bare membrane. No source read for this file describes a membrane injury or its resealing in this organism."},
        "cap.division": {"place": "present", "note": "It grows and divides as a single cell. The division genes ftsZ and sepF are among 19 genes that were added to the smaller strain JCVI-syn3.0 to make it, which gave it back a regular shape; a review reports that seven of the 19 are needed together for normal division."},
        "cap.replacement": {"place": "absent", "why": "It forms no tissue, so there is no neighbour for a new cell to replace."},
        "cap.mechanics": {"place": "absent", "why": "It forms no sheet: its cells share no edges to pull on."},
        "cap.sheet": {"place": "absent", "why": "It lives as single cells and forms no sheet of coupled cells."},
    }
    facts = [
        {"label": "Shape and size", "value": "a sphere about 400 nm across; two cells measured in electron tomograms were 403 nm and 495 nm across", "sources": ["breuer2019", "gilbert2021"]},
        {"label": "Envelope", "value": "one membrane; no cell wall and no periplasm", "sources": ["breuer2019", "gilbert2021"]},
        {"label": "Inside", "value": "no nucleus: in electron tomograms the ribosomes are spread through the whole cell, with the chromosome among them", "sources": ["gilbert2021"]},
        {"label": "Chromosome", "value": f"one circle of {c.length:,} base pairs", "sources": ["genbank"]},
        {"label": "Genes", "value": f"493, of which 452 code for proteins; the genome record lists {count} protein products, 3 of them added for genetic manipulation", "sources": ["breuer2019", "genbank"]},
        {"label": "Ribosomes", "value": "about 500 in a small cell: 503 or 684 counted in the cell 403 nm across, by two ways of counting, and 820 or 1,095 in the one 495 nm across", "sources": ["gilbert2021"]},
        {"label": "Proteins", "value": f"about 77,000 molecules in an average cell, an estimate from proteomics; {seen_kept} of the 452 kinds were detected, and the added marker tetM", "sources": ["breuer2019"]},
        {"label": "Doubling time", "value": "about 105 minutes in rich medium", "sources": ["breuer2019"]},
        {"label": "Energy", "value": "ATP from fermenting sugar; in the 2019 reconstruction of its metabolism, central metabolism is the only source of ATP", "sources": ["breuer2019"], "see": ["thornburg2022"]},
        {"label": "Food", "value": "glucose, amino acids, fatty acids and cholesterol, taken up from a rich medium that is not fully defined", "sources": ["breuer2019"]},
        {"label": "Ion channels", "value": f"none found among its {count} proteins", "sources": ["uniparc"]},
        {"label": "Division", "value": "the division genes ftsZ and sepF are among 19 genes added to the smaller strain JCVI-syn3.0 to make this one, which gave it back a regular shape; a review reports that seven of the 19 are needed together for normal division", "sources": ["breuer2019", "zhang2023"], "see": ["pelletier2021"]},
        {"label": "Origin", "value": "a genome designed and synthesised from that of Mycoplasma mycoides subspecies capri, strain GM12, and cut down to a minimum", "sources": ["genbank", "breuer2019"]},
    ]
    # What each capability's words rest on: permissive sources only. A capability that is
    # left out rests on the others by reasoning, or says that nothing was read.
    capability_sources = {
        "cap.membrane": ["breuer2019"], "cap.channels": ["uniparc"], "cap.pumps": ["genbank", "uniparc"], "cap.junctions": ["uniparc"],
        "cap.extracellular": ["breuer2019"], "cap.water": ["breuer2019", "gilbert2021"], "cap.calcium": ["breuer2019", "uniparc"],
        "cap.energy": ["breuer2019"], "cap.mitochondria": ["breuer2019"], "cap.circuits": ["breuer2019", "gilbert2021"],
        "cap.trafficking": ["genbank"], "cap.assembly": ["genbank"], "cap.machines": ["gilbert2021", "genbank", "uniparc"],
        "cap.secretion": ["breuer2019"], "cap.division": ["breuer2019", "zhang2023"],
    }
    sources = sources_of_species(c)
    for where, keys in [*capability_sources.items(), *((fact["label"], fact["sources"]) for fact in facts)]:
        if not keys or any(sources[key]["class"] != PERMISSIVE for key in keys):
            raise SystemExit(f"{where} would rest on a source whose terms do not allow it")
    return {
        "format": SPECIES_FORMAT,
        "id": SPECIES_ID,
        "label": LABEL,
        "organism": ORGANISM,
        "taxon": TAXON,
        "plain": "A bacterium with a designed, minimised genome: 452 protein-coding genes kept from Mycoplasma mycoides, in a cell about 400 nm across with one membrane and no wall. It grows on its own in a rich medium, and its genome is smaller than that of any natural cell that does.",
        "order": 30,
        "default": False,
        "made": MADE,
        "modelled": {
            "state": "proposed",
            "text": "JCVI-syn3A is the project's minimal-cell track (decision D173, 14 November 2026), taken up from a note that proposes it as the first whole-cell validation organism for Cells. Nothing of it is in the engine yet: the project's record holds an evidence audit, capability probes of the engine as it stands, and a proposed first milestone, with no engine code written for it and nothing accepted.",
        },
        "levels": [
            {"id": "molecules"},
            {
                "id": "cell",
                "label": "One cell",
                "shape": {"kind": "sphere", "across_um": 0.4},
                "note": "Drawn as a sphere 0.4 µm across with 500 ribosomes: round numbers for the smaller of the two cells that were measured. The larger one was about 0.5 µm across.",
                "sources": ["breuer2019", "gilbert2021"],
            },
        ],
        "no_further_levels": "A single-celled organism: each cell lives on its own, so there is no tissue, organ or body.",
        "cell": {
            "facts": facts,
            "parts": {"membranes": 1, "wall": False, "nucleus": False, "chromosome_kbp": round(c.length / 1000), "ribosomes": 500},
            "capabilities": capabilities,
        },
        "capability_sources": capability_sources,
        "sources": sources,
    }


def listed(items):
    items = list(items)
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " and " + items[-1]


def unit_note(c, spec):
    families = [FAMILIES[key] for key in spec["parts"]]
    signatures = [s for family in families for s in family["signatures"]]
    found = sum(c.mollicutes(s) for s in signatures)
    many = len(signatures) > 1
    if found:
        control = f"UniProtKB holds {found} entr{'y' if found == 1 else 'ies'} of other mollicutes, the class of bacteria it was made from, that carr{'ies' if found == 1 else 'y'} {'one of them' if many else 'it'}."
    else:
        control = f"No UniProtKB entry of any mollicute, the class of bacteria it was made from, carries {'them' if many else 'it'} either."
    human = [family for family in families if family.get("human", True)]
    proof = f" The unit's human candidates carry {'them' if sum(len(f['signatures']) for f in human) > 1 else 'it'}, so the search finds the family where it exists." if human else ""
    return f"None of the {len(c.proteins)} protein products of its genome carries the signature of {listed(f['of'] for f in families)} ({', '.join(signatures)}). {control}{proof} {spec['tail']}"


def extra_products(c):
    cite = {**citation(c, "breuer2019"), "class": CLASSES["breuer2019"]}
    out = []
    for item in EXTRA:
        protein = c.by_locus[item["locus"]]
        product = {
            "name": item["name"],
            "gene": protein.get("gene") or None,
            "role": item["role"],
            "ids": [{"db": "genbank", "id": protein["protein_id"]}],
            "length": len(protein["sequence"]),
        }
        if item.get("words"):
            product.update(evidence="named in a publication", evidence_note=f"Locus {item['locus']}, product \"{protein['protein']}\" in the genome record. Breuer and others 2019 name it: {item['says']}. The role is assigned from its sequence and from related mycoplasmas, not measured in this strain.", citation=cite)
        else:
            product.update(evidence="family signature", evidence_note=f"Locus {item['locus']}, product \"{protein['protein']}\" in the genome record. Its sequence carries {item['signature']} ({c.signature_names[item['signature']]}) in UniProt's archive. A candidate by annotation, not a measured function in this strain.", citation=None)
        product["why"] = item["why"]
        out.append(product)
    return out


def build_atlas(c):
    ev = c.evidence
    units = {}
    for unit in c.snapshot["units"]:
        spec = UNITS[unit["id"]]
        if spec.get("finding"):
            if unit.get("products"):
                raise SystemExit(f"{unit['id']} has candidates in the inventory; it cannot be '{spec['finding']}'")
            units[unit["id"]] = {"finding": spec["finding"], "note": spec["note"], "products": []}
        else:
            if not unit.get("products"):
                raise SystemExit(f"{unit['id']} has no candidates in the inventory; nothing can be searched for it")
            units[unit["id"]] = {"finding": "none found", "note": unit_note(c, spec), "products": []}
    if set(units) != {unit["id"] for unit in c.snapshot["units"]} or set(UNITS) != set(units):
        raise SystemExit("the units of the atlas are not the units of the inventory")
    breuer = citation(c, "breuer2019")
    return {
        "format": ATLAS_FORMAT,
        "species": {
            "id": SPECIES_ID,
            "label": LABEL,
            "organism": ORGANISM,
            "taxon": TAXON,
            "plain": "A bacterium with a designed, minimised genome of 452 protein-coding genes, proposed as the first whole-cell validation organism for Cells; the units of the law inventory are machines of animal cells, and it has none of them.",
        },
        "made": MADE,
        "method": [
            f"The organism's proteins are the {len(c.proteins)} protein products of one frozen genome annotation, GenBank {RECORD} (annotation of 12 April 2018): 452 kept from Mycoplasma mycoides and 3 added for genetic manipulation. UniProtKB holds no entry of the organism; UniProt's archive (UniParc) holds exactly these {len(c.proteins)} sequences, with the family signatures on each.",
            "Licences were read before anything was copied; each is stated in sources, and what was read but not copied is in not_copied.",
            "Each unit's family was taken from its own human candidates, by the same InterPro signatures that the planarian atlas asks. The build checks that the candidates carry them.",
            f"Each signature was looked for on all {len(c.proteins)} sequences. None was found, for any unit.",
            "A control for every zero: the same signature was asked of the UniProtKB entries of all mollicutes, the class of bacteria the organism was made from; each unit's note gives what came back.",
            "Eight further signatures, of the ion channels a bacterium could have (potassium, chloride, magnesium, water and membrane-stretch channels), were looked for as well, and none was found, although each is carried by UniProtKB entries of other mollicutes.",
            "Under extra are nine of the organism's own membrane machines that bear on what the atlas draws and match no unit. Five are named for this organism in Breuer and others 2019, whose saved text the build checks; four are listed by the signature on their sequence. All are assigned by annotation, not measured in this strain.",
            "No similarity search was run, and nothing is called an ortholog.",
        ],
        "sources": [
            {
                "name": "GenBank", "url": f"https://www.ncbi.nlm.nih.gov/nuccore/{RECORD}", "release": f"{RECORD}, annotation of 12 April 2018", "accessed": ev.day(f"genbank_{RECORD}_cds_aa.fa"),
                "licence": "No restriction: \"NCBI places no restrictions on the use or distribution of the GenBank data\". Submitters may claim rights in what they submitted; this record states none.",
                "class": PERMISSIVE,
                "cite": f"Glass J (2017) {c.record_title}. GenBank {RECORD}.",
                "holds": "the locus tags, gene names, products, protein identifiers and lengths of the organism's proteins",
            },
            {
                "name": "UniProt", "url": "https://www.uniprot.org/", "release": c.uniprot_release, "accessed": ev.day(f"uniparc_{TAXON}.json"), "licence": "CC BY 4.0", "class": PERMISSIVE,
                "cite": "The UniProt Consortium, UniProt: the Universal Protein Knowledgebase in 2025, Nucleic Acids Res. 53:D609-D617 (2025)",
                "holds": "which archived sequences of the organism carry each family signature; the signatures of the units' human candidates; the control counts",
            },
            {
                "name": "InterPro", "url": "https://www.ebi.ac.uk/interpro/", "accessed": ev.day("terms_interpro_license.html"), "licence": "CC0 1.0", "class": PERMISSIVE,
                "cite": "Blum and others (2025) InterPro: the protein sequence classification resource in 2025. Nucleic Acids Res 53:D444-D456.",
                "holds": "the identifiers and names of the family signatures, as UniProt gives them",
            },
            {
                "name": "Breuer and others 2019", "url": f"https://doi.org/{breuer['doi']}", "accessed": ev.day(BREUER), "licence": "CC BY 4.0", "class": PERMISSIVE,
                "cite": breuer["text"],
                "holds": "the names the paper gives five of the organism's transport proteins, and what its reconstruction of the cell's metabolism says of the ATP synthase and of where the cell's ATP comes from",
            },
            {
                "name": "Europe PMC", "url": "https://europepmc.org/", "accessed": ev.day("europepmc_citations.json"),
                "licence": "Bibliographic facts only (authors, title, journal, year, identifiers). EMBL-EBI places no restriction of its own on the use of what its services give, beyond those of the data's owners. Open texts were read to check names and are not copied.",
                "class": PERMISSIVE,
                "cite": "Europe PMC Consortium, Europe PMC, https://europepmc.org/.",
                "holds": "the record of the paper cited",
            },
        ],
        "not_copied": "No sequence is copied: they stay with the downloads, outside the repository. Nothing is taken from the 2022 whole-cell paper, which is under a non-commercial licence (CC BY-NC-ND), or from the 2021 paper on the genes needed for division, which states no open licence: the species file names both as places to read, and what it says of energy and of division rests on the 2019 paper and on an open review. The 2026 whole-cell paper and the archive of its model were not read for this file, and the instrument files of the 2019 proteomics (PXD008159) were not downloaded.",
        "units": units,
        "extra": extra_products(c),
    }


CATALOGUE_COLUMNS = ["locus_tag", "gene", "product", "length", "protein_id", "origin", "functional_class", "essentiality", "detected", "copies_per_cell", "proteomics_id", "uniparc", "uniprotkb_identical", "interpro"]
ESSENTIALITY = {"Essential": "essential", "Quasiessential": "quasi-essential", "Nonessential": "non-essential"}


def same_sequence(c, protein, keep=3):
    """UniProtKB entries of other organisms with exactly this sequence: reviewed ones first."""
    entries = sorted((c.identical[a] for a in protein["same"]), key=lambda e: (not e["entryType"].startswith("UniProtKB reviewed"), e["primaryAccession"]))
    shown = [f"{e['primaryAccession']} [{'reviewed' if e['entryType'].startswith('UniProtKB reviewed') else 'unreviewed'}] {e['organism']['scientificName']}" for e in entries[:keep]]
    return " | ".join(shown) + (f" | +{len(entries) - keep} more" if len(entries) > keep else "")


def build_catalogue(c):
    rows = []
    for protein in c.proteins:
        locus = protein["locus_tag"]
        table = c.classes[locus]
        measured = c.abundance.get(locus)
        rows.append([
            locus, protein.get("gene", ""), protein["protein"], len(protein["sequence"]), protein["protein_id"],
            "minimal genome" if table["Feature type"] == "CDS" else "added for manipulation",
            " > ".join(part for part in (table["Primary functional class"], table["Secondary functional class"], table["Tertiary functional class"]) if part),
            ESSENTIALITY[table["Essentiality"]],
            "yes" if measured else "no",
            f"{measured['copies']:.3g}" if measured else "",
            measured["id"] if measured else "",
            protein["uniparc"], same_sequence(c, protein), ";".join(protein["interpro"]),
        ])
    return [[re.sub(r"\s+", " ", str(value)).strip() for value in row] for row in rows]


def table(rows):
    return "\n".join("\t".join(row) for row in [CATALOGUE_COLUMNS, *rows]) + "\n"


def shelves_section(c, shelves):
    """What the README says of shelves.json: the counts, how a side is known, how the reading fares."""
    counts, by_basis, checks = shelves["counts"], shelves["by_basis"], shelves["checks"]
    total = sum(counts.values())
    words = {"stated": "stated", "predicted": "predicted", "by function": "by function", "none": "nothing settles it"}
    how = lambda side: ", ".join(f"{n} {words[basis]}" for basis, n in by_basis.get(side, {}).items()) or "none"
    basis_total = Counter()
    for side in by_basis.values():
        basis_total.update(side)
    inside, permeases, stated, anchors, membrane = checks["inside_by_class"], checks["permeases"], checks["stated"], checks["lipid_anchor"], checks["membrane"]
    set_aside = f"{len(anchors['set_aside'])} ({listed(anchors['set_aside'])})" if anchors["set_aside"] else "none"
    false_alarms = listed(inside["read_as_spanning"]) if inside["read_as_spanning"] else "none"
    districts = "\n".join(f"| {group['label']} | {group['within']} | {group['count']} | " + " | ".join(str(group["sides"].get(side, 0)) for side in SIDES) + " |" for group in shelves["groups"])
    paulet, review = open_paper(c, "paulet2011"), open_paper(c, "christodoulides2018")
    desvaux, smithers, legood = open_paper(c, "desvaux2018"), open_paper(c, "smithers2021"), open_paper(c, "legood2020")
    box = "-".join(f"[{allowed}]" for allowed in LIPOBOX)
    unplaced = [row for row in shelves["proteins"] if row[4] == "not known"]
    spanning = checks["in_the_membrane"]
    behind = {"experiment": "an experiment", "curator": "a curator's inference", "similarity": "similarity to another protein", "rule": "a family rule"}
    stated_words = listed([f"{behind[name]} for {n}" for name, n in stated["by_evidence"].items()]) + ("" if "experiment" in stated["by_evidence"] else "; none rests on an experiment")
    at_membrane = stated["said_to_be_at_the_membrane"]
    at_membrane_words = "" if not at_membrane else f"\n  Such an entry also says that {listed(at_membrane)} {'is' if len(at_membrane) == 1 else 'are'} at the cell membrane as a peripheral protein, without saying\n  which face. The reading places {'it' if len(at_membrane) == 1 else 'them'} inside, and {'it is' if len(at_membrane) == 1 else 'they are'} marked as at the membrane."
    complexes = Counter(row[9]["complex"] for row in shelves["proteins"] if "complex" in row[9])
    return f"""## `{SHELVES_FILE}`: where each protein sits

For the shelves of the protein atlas (`schema/SPECIES_PROTEINS.md`): one line for each of
the {total} proteins, in this table's order, saying which side of the cell membrane it sits
on, how that is known, and the district it stands in. The organism has one membrane, so
there is one shelf.

| Side | Proteins | How it is known |
| --- | --- | --- |
| Outside the cell, anchored to the membrane's outer face | {counts['outside']} | {how('outside')} |
| In the membrane, spanning it | {counts['in']} | {how('in')} |
| Inside the cell, free or attached to the membrane's inner face | {counts['inside']} | {how('inside')} |
| Not known | {counts['not known']} | {how('not known')} |

**How a side is known.**

- **Stated ({basis_total['stated']}).** A reviewed UniProtKB entry with exactly this protein's
  sequence states the place. Every such entry is of another organism, so it states where
  the same protein sits there; the entry is named with the protein. What stands behind
  the statements: {stated_words}.{at_membrane_words}
- **Predicted ({basis_total['predicted']}).** This tool's own reading of the sequence. It is
  not the output of an established predictor: UniProt's archive holds family signatures on
  these sequences and no prediction of membrane-spanning stretches, and no UniProtKB entry
  of any organism with one of these sequences gives one.
  - *In the membrane:* a stretch of {WINDOW} residues whose mean hydropathy on Kyte and
    Doolittle's scale is {HYDROPHOBIC / 10} or more and which holds no charged residue, or
    {STRONG / 10} or more with at most one. The window and the {HYDROPHOBIC / 10} are the usual
    reading of that scale ({paulet['who']} {paulet['year']} state it). The conditions on
    charged residues are this tool's, set against the checks below.
  - *Outside:* a lipid anchor, read by a rule of this tool's own. A bacterial lipoprotein is
    made with a signal peptide of three parts: a positively charged beginning, a
    hydrophobic stretch, and the lipobox, whose cysteine takes the lipid; the signal
    peptide is on average 16 to 26 residues long ({smithers['who']} {smithers['year']}). The
    rule takes the first cysteine that has a lipobox before it ({box}, the
    form {desvaux['who']} {desvaux['year']} state for bacteria with one membrane), that sits
    within the first {ANCHOR_REACH} residues, and that is preceded by a stretch of {SIGNAL_WINDOW} residues
    with a mean hydropathy of {HYDROPHOBIC / 10} or more and no charged residue, with a lysine or an
    arginine before that stretch. The reach of {ANCHOR_REACH} and the stretch of {SIGNAL_WINDOW} are this tool's own
    choice, since no source read states a limit. The rule was fixed before it was run and
    is not adjusted to any protein. The lipoproteins of mycoplasmas are bound to the
    membrane and exposed on the cell's surface ({review['who']} {review['year']}); that is
    said of mycoplasmas in general and was not measured in this strain.
  - *Inside:* no such stretch and no lipid anchor. This includes proteins attached to the
    membrane's inner face, such as the ATP-binding parts of transporters.
- **By function ({basis_total['by function']}).** The sequence has a hydrophobic stretch, or reads as
  carrying a lipid anchor, but the protein's class in the 2019 paper leaves no doubt that
  it works inside the cell:
  translation, transcription, the upkeep of DNA, sugar breakdown, the pentose phosphate
  pathway or nucleotide metabolism. Function is never used to place a transport protein.
- **Not known ({counts['not known']}).** A hydrophobic stretch that holds charged residues, in a
  protein of unknown function: {", ".join(row[0] for row in unplaced) or "none"}. They are not placed.

**How the reading fares against what is known.**

- **Proteins that work inside the cell.** Of the {inside['proteins']} proteins in the classes named under
  "By function", {inside['with_a_hydrophobic_stretch']} have a stretch at {HYDROPHOBIC / 10} or more, which the usual reading alone would call
  membrane-spanning. With the condition on charged residues the tool reads {len(inside['read_as_spanning'])} of them so
  ({false_alarms}); it too is placed inside, by its function.
- **Proteins named as membrane-spanning.** All {permeases['proteins']} proteins that the annotation calls a
  permease are read as membrane-spanning.
- **Stated places.** The reading agrees with all {stated['proteins']}.
- **Lipid anchors.** The rule reads an anchor on {anchors['read']} proteins. {anchors['kept']} are kept: {anchors['placed_outside']} are placed outside, and
  {anchors['placed_in']}, with a membrane-spanning stretch after the anchor, in the membrane. Set aside, because a
  reviewed entry states the place or the protein's class leaves no doubt that it works
  inside the cell: {set_aside}. No lipid was measured on any of them, and nothing here
  checks the rule against a measurement: it is a reading of the sequence.
  **The rule is strict and misses lipoproteins.** Lipoboxes of other forms have been
  reported ({legood['who']} {legood['year']}), and a lipoprotein with such a one is not
  called. It is then placed like any other protein: usually in the membrane, by the
  hydrophobic stretch of its signal, with the mark that its one stretch is at its start
  ({spanning['one_stretch_at_the_start']} proteins carry that mark). `docs/SYN3A.md` says how the rule compares with
  the signature it replaced.
- **Against the literature.** Here {counts['in']} proteins span the membrane and {counts['outside']} are anchored on it,
  {membrane['in_or_on']} together. {membrane['seen']} of them were seen in the proteomics, with an estimated {membrane['estimated_copies']:,} of
  the {membrane['all_estimated_copies']:,} copies. The 2022 whole-cell model gives its own count of membrane
  proteins and of their copies. That paper is under a non-commercial licence, so its
  numbers are not repeated here and no list of the model's was copied or compared: the
  comparison is to be read there.

**Districts.** The 2019 paper's secondary functional class, in its own words; the tertiary
class is kept with each protein for laying a district out.

| District | Within | Proteins | Outside | In | Inside | Not known |
| --- | --- | --- | --- | --- | --- | --- |
{districts}

**Marks** kept with each protein: essentiality and whether it was seen (both measured),
the estimated copies (`amount`), the three proteins added for manipulation, the finer
class, the number of membrane-spanning stretches read, the lipid anchor, what stands
behind a stated side, and its assembly where the record's product name gives it outright
({", ".join(f"{name} {n}" for name, n in sorted(complexes.items()))}).

**What it does not say.** It gives no topology: not which end of a membrane protein faces
out, and not which face a protein inside is attached to. The count of stretches can fall
short, since a stretch that holds charged residues is not read. Of the {spanning['proteins']} proteins placed
in the membrane, {spanning['one_stretch']} have one stretch only, and for {spanning['one_stretch_at_the_start']} of those it is at the very start
of the protein: that may be an export signal that is cut off, and the protein would then
sit outside. They are marked. It marks no assembly beyond the three named. `unit` is
empty throughout, because the atlas found none of the law inventory's units in this
organism.

"""


def build_readme(c, rows, shelves):
    ev = c.evidence
    count = len(rows)
    native = sum(row[5] == "minimal genome" for row in rows)
    essentiality = Counter(row[7] for row in rows if row[5] == "minimal genome")
    detected = sum(row[8] == "yes" for row in rows)
    detected_kept = sum(row[8] == "yes" and row[5] == "minimal genome" for row in rows)
    with_same = sum(bool(row[12]) for row in rows)
    unsigned = sum(not row[13] for row in rows)
    breuer = citation(c, "breuer2019")
    rna = sum(c.kinds[kind] for kind in ("tRNA", "rRNA", "ncRNA", "tmRNA"))
    pseudo = ", ".join(c.pseudo)
    built_from = [
        ("The genome record's summary", f"genbank_{RECORD}_summary.json"), ("Its features: genes, RNA genes, pseudogenes", f"genbank_{RECORD}_features.ft"),
        ("Its protein products", f"genbank_{RECORD}_cds_aa.fa"), ("The protein products of its first version", f"genbank_{FIRST_RECORD}_cds_aa.fa"),
        ("The 2019 paper's supplementary file 3", "elife_36842_supp3.xlsx"), ("The 2019 paper's supplementary file 5", "elife_36842_supp5.xlsx"),
        ("UniProt's archived sequences and signatures", f"uniparc_{TAXON}.json"), ("Other organisms' entries with the same sequences", "uniprotkb_identical.json"),
        ("What those entries state of where the protein sits", "uniprotkb_identical_places.json"), ("The hydropathy scale's values", "biopython_185_ProtParamData.py"),
        ("The records of the papers cited for the shelves", "europepmc_shelves_citations.json"),
        ("The open review cited for division", ZHANG), ("The open paper cited for the usual reading of the scale", PAULET),
        ("The open review cited for where lipoproteins sit", CHRISTODOULIDES),
        ("The open review cited for the lipobox", DESVAUX), ("The open review cited for a lipoprotein's signal peptide", SMITHERS),
        ("The open review cited for lipoboxes of other forms", LEGOOD), ("HAMAP's statement of its terms", "upstream_hamap_about.html"),
    ]
    inputs = "\n".join(f"| {what} | `{ev.read[name]['source']}` | `{ev.read[name]['file']}` | `{ev.read[name]['sha256']}` |" for what, name in built_from)
    day_record, day_paper, day_archive = ev.day(f"genbank_{RECORD}_cds_aa.fa"), ev.day("elife_36842_supp3.xlsx"), ev.day(f"uniparc_{TAXON}.json")
    return f"""# Syn3A proteins: the start of a catalogue

`{CATALOGUE_FILE}` lists the {count} protein products of one frozen genome annotation of the
minimal cell {ORGANISM}, one per line, with what open sources say of each: what it is
named, how long it is, what it is for, whether the cell can do without it, and how many
copies were estimated in a cell.

`{SHELVES_FILE}` says, for the same {count} proteins, where each sits against the cell
membrane and how that is known. It is described in its own section below.

Generated by `tools/build_syn3a_atlas.py`; do not edit. This is reference data for the
viewer. It is not the engine's protein catalogue, and nothing in the engine reads it.

## The frozen annotation

GenBank **{RECORD}**: "{c.record_title}", {c.length:,} base pairs, one circular
chromosome, annotation of 12 April 2018 (taxon {TAXON}). It is the annotation that the
2019 paper names and that its tables are keyed to, so every column below can be tied to a
locus tag of this record.

| In the record | Count | In this table |
| --- | --- | --- |
| Coding sequences with a protein product | {count} | all {count} |
| of which kept from *Mycoplasma mycoides* | {native} | `origin` is `minimal genome` |
| of which added for genetic manipulation (tetM and the yeast genes HIS3 and MET14) | {count - native} | `origin` is `added for manipulation` |
| Pseudogenes, with no protein product ({pseudo}) | {len(c.pseudo)} | not listed |
| RNA genes | {rna} | not listed |

**Why 452 and 455 are both right.** Papers on this organism count {native} protein-coding
genes; the record holds {count} protein products. The difference is the {count - native} genes added
for genetic manipulation, which the 2019 paper's own table sets apart. The record's {len(c.genes)}
genes are these {count}, the {len(c.pseudo)} pseudogenes and the {rna} RNA genes.

UniProtKB holds no entry of this organism. UniProt's archive of sequences (UniParc) holds
exactly these {count} sequences, which is where the family signatures come from.

## Columns

Tab-separated, with a header line. An empty cell means the source says nothing.

| Column | What it is | From | Measured, or annotation? |
| --- | --- | --- | --- |
| `locus_tag` | The gene's locus tag | GenBank {RECORD} | Annotation |
| `gene` | The gene name, where the record gives one | GenBank {RECORD} | Annotation |
| `product` | The product's name | GenBank {RECORD} | Annotation, mostly by similarity to other bacteria |
| `length` | Residues of the protein product | GenBank {RECORD}, counted from its translation | From the sequence |
| `protein_id` | The protein's identifier at NCBI | GenBank {RECORD} | Identifier |
| `origin` | `minimal genome`, or `added for manipulation` | Breuer and others 2019, supplementary file 3 | The paper's classification |
| `functional_class` | The paper's three levels of functional class, joined by ` > ` | Breuer and others 2019, supplementary file 3 | Annotation; "Unclear" marks a function that is not known |
| `essentiality` | `essential`, `quasi-essential` or `non-essential` | Breuer and others 2019, supplementary file 3 (its final column) | **Measured** by transposon mutagenesis in this strain, then classified by the paper's model, with a few calls set by hand |
| `detected` | `yes` if the protein was seen in the proteomics | Breuer and others 2019, supplementary file 5 | **Measured** in this strain |
| `copies_per_cell` | Copies in an average cell, at the first time point (logarithmic phase) | Breuer and others 2019, supplementary file 5 | **An estimate**: the measured share of the protein signal, scaled to the paper's estimate of {c.copies_total:,} protein molecules in a cell |
| `proteomics_id` | The identifier the proteomics table uses, from the record's first version ({FIRST_RECORD}) | Breuer and others 2019, supplementary file 5 | Identifier; tied to the locus tag by identical sequence |
| `uniparc` | The sequence's identifier in UniProt's archive | UniProt (UniParc), release {c.uniprot_release} | Identifier |
| `uniprotkb_identical` | UniProtKB entries of **other organisms** with exactly this sequence: accession, whether reviewed, and the organism; at most three, reviewed ones first | UniProt, release {c.uniprot_release} | Identity of sequence only; such an entry is not an entry of this organism |
| `interpro` | The InterPro family and domain signatures on the sequence | UniProt (UniParc), release {c.uniprot_release} | Computed from the sequence |

Counts, as built:

- **Essentiality** of the {native} kept genes: {essentiality['essential']} essential, {essentiality['quasi-essential']} quasi-essential, {essentiality['non-essential']} non-essential.
  The paper's Table 1 totals 271, 113 and 68: one gene differs between that table and the
  supplementary file, and the file is what is copied here.
- **Detected:** {detected} of the {count}: {detected_kept} of the {native} kept and {detected - detected_kept} of the {count - native} added (tetM). The
  estimated copies of the detected proteins sum to {c.copies_total:,}.
- **Identical sequence in another organism's UniProtKB entry:** {with_same} of the {count}.
- **No signature at all:** {unsigned} of the {count}.

What is not here: sequences (they stay with the downloads), simulated counts from
any model, and structures. Where a protein sits is not in this table either: it is in
`{SHELVES_FILE}`, described below. Strain
identity matters: every value is for {ORGANISM} itself. Nothing is carried over from
JCVI-syn3.0, JCVI-syn3B or *Mycoplasma mycoides*, except that `uniprotkb_identical` names
other organisms' entries and says so.

{shelves_section(c, shelves)}## Sources and terms

| Source | What is taken | Terms |
| --- | --- | --- |
| [GenBank {RECORD}](https://www.ncbi.nlm.nih.gov/nuccore/{RECORD}), read {day_record} | Locus tags, gene names, products, protein identifiers, lengths | "NCBI places no restrictions on the use or distribution of the GenBank data"; submitters may claim rights in what they submitted, and this record states none |
| [Breuer and others 2019](https://doi.org/{breuer['doi']}), supplementary files 3 and 5, read {day_paper} | Origin, functional class, essentiality, detection and estimated copies | CC BY 4.0 |
| [UniProt](https://www.uniprot.org/), release {c.uniprot_release}, read {day_archive} | Archive identifiers, signatures, and other organisms' entries with the same sequence and the place they state | CC BY 4.0 |
| [InterPro](https://www.ebi.ac.uk/interpro/) | The signatures' identifiers | CC0 1.0 |
| [Biopython 1.85]({BIOPYTHON_PAGE}), read {ev.day("biopython_185_ProtParamData.py")} | The 20 values of Kyte and Doolittle's hydropathy scale, for `{SHELVES_FILE}` | Biopython License Agreement or BSD 3-Clause License |
| [{open_paper(c, "paulet2011")["who"]} 2011](https://doi.org/{open_paper(c, "paulet2011")["doi"]}), read {open_paper(c, "paulet2011")["accessed"]} | The usual reading of the hydropathy scale: a window of {WINDOW} residues and a mean above {HYDROPHOBIC / 10} | {OPEN_LICENCE["paulet2011"]} |
| [{open_paper(c, "christodoulides2018")["who"]} 2018](https://doi.org/{open_paper(c, "christodoulides2018")["doi"]}), read {open_paper(c, "christodoulides2018")["accessed"]} | That the lipoproteins of mycoplasmas are bound to the membrane and exposed on the cell's surface | {OPEN_LICENCE["christodoulides2018"]} |
| [{open_paper(c, "desvaux2018")["who"]} 2018](https://doi.org/{open_paper(c, "desvaux2018")["doi"]}), read {open_paper(c, "desvaux2018")["accessed"]} | The lipobox, as stated for bacteria with one membrane | {OPEN_LICENCE["desvaux2018"]} |
| [{open_paper(c, "smithers2021")["who"]} 2021](https://doi.org/{open_paper(c, "smithers2021")["doi"]}), read {open_paper(c, "smithers2021")["accessed"]} | The three parts of a lipoprotein's signal peptide and its usual length | {OPEN_LICENCE["smithers2021"]} |
| [{open_paper(c, "legood2020")["who"]} 2020](https://doi.org/{open_paper(c, "legood2020")["doi"]}), read {open_paper(c, "legood2020")["accessed"]} | That lipoboxes of other forms have been reported | {OPEN_LICENCE["legood2020"]} |
| [HAMAP](https://hamap.expasy.org/hamap_about.html), read {ev.day("upstream_hamap_about.html")} | Nothing downloaded but its terms: its family rules are what reviewed UniProtKB entries state places by, and they were read in those entries | CC BY 4.0 |

Every source above is permissive: its terms allow what is taken, with attribution.

Nothing in this folder rests on a source of another class. The membrane-spanning
stretches and the lipid anchors are this tool's own reading of the sequences, by rules
fixed from open descriptions; no predictor's output and no signature of another database
is read for them. The stated places are those of reviewed UniProtKB entries, which give
them by HAMAP's family rules (HAMAP is distributed under CC BY 4.0) or by similarity.

**Named, with nothing taken.** These are pointers: each says what is to be read there.
Nothing in this folder rests on them.

| Source | Class | What is to be read there |
| --- | --- | --- |
| {citation(c, "thornburg2022")["text"]} | non-commercial (CC BY-NC-ND 4.0) | The whole-cell model's own count of membrane proteins and of their copies |
| {shelf_citation(c, "lhernault1992")["text"]} | non-commercial (CC BY-NC-SA 4.0) | A use of the hydropathy scale to find the membrane-spanning stretches of a protein |
| {shelf_citation(c, "chambaud1999")["text"]} | no stated terms (not open) | A review of where the lipoproteins of mycoplasmas are anchored |
| {shelf_citation(c, "kyte1982")["text"]} | no stated terms (not open) | The paper that defined the hydropathy scale. Its values were taken from Biopython's file, not from the paper |

Cite:

- GenBank: Glass J (2017) {c.record_title}. GenBank {RECORD}.
- {breuer['text']} doi:{breuer['doi']}
- The UniProt Consortium, UniProt: the Universal Protein Knowledgebase in 2025, Nucleic Acids Res. 53:D609-D617 (2025)
- {open_paper(c, "paulet2011")["text"]} doi:{open_paper(c, "paulet2011")["doi"]}
- {open_paper(c, "christodoulides2018")["text"]} doi:{open_paper(c, "christodoulides2018")["doi"]}
- {open_paper(c, "desvaux2018")["text"]} doi:{open_paper(c, "desvaux2018")["doi"]}
- {open_paper(c, "smithers2021")["text"]} doi:{open_paper(c, "smithers2021")["doi"]}
- {open_paper(c, "legood2020")["text"]} doi:{open_paper(c, "legood2020")["doi"]}

## The files they were built from

Each is in the dataset folder of its source, outside the repository, and the build checks
it against the SHA-256 that the folder's MANIFEST gives before reading it.

| What | Dataset folder | File | SHA-256 |
| --- | --- | --- | --- |
{inputs}

## How to rebuild

```bash
python3 tools/build_syn3a_atlas.py fetch --evidence DIR --datasets DATA   # network; saves what is not yet there
python3 tools/build_syn3a_atlas.py build --evidence DIR --datasets DATA   # offline; the same bytes every time
```

`DATA` holds the downloads, one folder per source with a MANIFEST.json; `DIR` holds the
log of what this tool asked. Both are kept outside the repository. The build writes this
folder's three files, `data/species/syn3a.json` and `data/proteins/atlases/syn3a.json`.
`docs/SYN3A.md` describes the method and its limits.
"""


# ---------------------------------------------------------------------------------------
# The shelves: where each protein sits against the cell membrane (schema/SPECIES_PROTEINS.md)
# ---------------------------------------------------------------------------------------

# Kyte and Doolittle's hydropathy scale (1982), in tenths so that sums are whole numbers:
# the values as Biopython 1.85 lists them (Bio/SeqUtils/ProtParamData.py, under the
# Biopython License Agreement or the BSD 3-Clause License). The saved copy of that file
# is checked against these values before they are used.
HYDROPATHY = {"A": 18, "R": -45, "N": -35, "D": -35, "C": 25, "Q": -35, "E": -35, "G": -4, "H": -32, "I": 45, "L": 38, "K": -39, "M": 19, "F": 28, "P": -16, "S": -8, "T": -7, "W": -9, "Y": -13, "V": 42}
WINDOW = 19               # residues in a stretch long enough to span the membrane
HYDROPHOBIC = 16          # mean hydropathy, in tenths, at which a stretch counts as hydrophobic (1.6)
STRONG = 22               # mean hydropathy, in tenths, at which one charged residue is allowed in it (2.2)
CHARGED = "DEKR"
SIGNAL_START = 12         # the hydrophobic stretch of an export signal begins within these residues
# The lipid anchor of a bacterial lipoprotein, read by this tool's own rule (see lipid_anchor).
# The lipobox is the form Desvaux and others 2018 state for bacteria with one membrane; the
# two numbers are this tool's own choice, fixed on 15 November 2026 before the rule was run
# on any sequence, and not adjusted since.
LIPOBOX = ("LVI", "ASTVI", "GAS")   # the residues allowed at -3, -2 and -1 of the cysteine
ANCHOR_REACH = 40         # the cysteine sits at this residue or before
SIGNAL_WINDOW = 10        # residues in the hydrophobic stretch of a lipoprotein's signal peptide
# The 2019 paper's classes that leave no doubt that a protein works inside the cell. Used
# only where the sequence has a hydrophobic stretch, and never for a transport protein.
INSIDE_BY_FUNCTION = [
    ("Genetic Information Processing", "Translation", None),
    ("Genetic Information Processing", "Transcription", None),
    ("Genetic Information Processing", "DNA Maintenance", None),
    ("Metabolism", "Central Carbon Metabolism", "Glycolysis"),
    ("Metabolism", "Central Carbon Metabolism", "Pentose phosphate metabolism"),
    ("Metabolism", "Central Carbon Metabolism", "Nucleotide metabolism"),
]
# Assemblies whose members the annotation names outright.
COMPLEXES = [("ribosome", r"^(30S|50S) ribosomal protein "), ("ATP synthase", r"^F0F1 ATP synthase subunit "), ("RNA polymerase", r"RNA polymerase subunit ")]
SIDES = ["outside", "in", "inside", "not known"]
SOURCE_NAMES = {
    "genbank": "GenBank", "breuer2019": "Breuer and others 2019", "uniparc": "UniParc", "uniprotkb": "UniProtKB", "scale": "Biopython 1.85",
    "paulet2011": "Paulet and others 2011", "christodoulides2018": "Christodoulides and others 2018",
    "desvaux2018": "Desvaux and others 2018", "smithers2021": "Smithers and others 2021", "legood2020": "Legood and others 2020", "kyte1982": "Kyte and Doolittle 1982", "lhernault1992": "L'Hernault and Arduengo 1992", "chambaud1999": "Chambaud and others 1999", "thornburg2022": "Thornburg and others 2022",
}
BASES = ["stated", "predicted", "by function", "none"]
SHELF_COLUMNS = ["id", "label", "gene", "shelf", "side", "basis", "group", "length", "unit", "marks"]


def scale_in_file(text):
    """The scale's values as the saved file lists them, in tenths. The file is read as text."""
    listed = re.search(r"^kd = \{(.*?)\}", text, re.S | re.M)
    return {letter: round(float(value) * 10) for letter, value in re.findall(r'"([A-Z])": (-?\d+\.\d+)', listed.group(1))} if listed else {}


def scan(sequence):
    """Read a sequence for stretches that could span the membrane.

    Returns the first residue of each stretch that is read as membrane-spanning, whether any
    stretch is hydrophobic at all, and the highest mean hydropathy of a stretch. A stretch of
    WINDOW residues is read as membrane-spanning where its mean hydropathy is HYDROPHOBIC or
    more and it holds no charged residue, or STRONG or more with at most one. Stretches are
    taken strongest first and may not overlap."""
    if len(sequence) < WINDOW:
        return [], False, None
    values = [HYDROPATHY[letter] for letter in sequence]
    charged = [letter in CHARGED for letter in sequence]
    total, charges = sum(values[:WINDOW]), sum(charged[:WINDOW])
    windows = []
    for start in range(len(sequence) - WINDOW + 1):
        if start:
            total += values[start + WINDOW - 1] - values[start - 1]
            charges += charged[start + WINDOW - 1] - charged[start - 1]
        windows.append((total, start, charges))
    best = max(total for total, _, _ in windows)
    read = sorted(((total, start) for total, start, c in windows if (total >= HYDROPHOBIC * WINDOW and c == 0) or (total >= STRONG * WINDOW and c <= 1)), key=lambda item: (-item[0], item[1]))
    kept = []
    for total, start in read:
        if all(abs(start - other) >= WINDOW for other in kept):
            kept.append(start)
    return sorted(start + 1 for start in kept), best >= HYDROPHOBIC * WINDOW, best / (10 * WINDOW)


def lipid_anchor(sequence):
    """The cysteine a lipid is attached to, by this tool's own reading of the sequence, or None.

    A bacterial lipoprotein is made with a signal peptide of three parts: a positively
    charged beginning, a hydrophobic stretch, and the lipobox, whose cysteine takes the
    lipid (Smithers and others 2021). The first cysteine is taken, at residue p, for which:
      1. the three residues before it are a lipobox: [LVI] [ASTVI] [GAS] (Desvaux and others
         2018, for bacteria with one membrane);
      2. p is ANCHOR_REACH or less;
      3. before it lies a window of SIGNAL_WINDOW residues whose mean hydropathy is
         HYDROPHOBIC or more and which holds no charged residue;
      4. a lysine or an arginine stands before that window.
    The rule was written down before it was run, and is not adjusted to any protein."""
    values = [HYDROPATHY[letter] for letter in sequence[:ANCHOR_REACH]]
    for at in range(3, min(len(sequence), ANCHOR_REACH)):  # at is the cysteine's index from 0; p = at + 1
        if sequence[at] != "C" or any(sequence[at - 3 + i] not in allowed for i, allowed in enumerate(LIPOBOX)):
            continue
        for start in range(1, at - SIGNAL_WINDOW + 1):  # the window is sequence[start:start + SIGNAL_WINDOW], ending before the cysteine
            window = sequence[start:start + SIGNAL_WINDOW]
            if any(letter in CHARGED for letter in window) or sum(values[start:start + SIGNAL_WINDOW]) < HYDROPHOBIC * SIGNAL_WINDOW:
                continue
            if any(letter in "KR" for letter in sequence[:start]):
                return at + 1
    return None


def anchor_rule(desvaux, smithers):
    """The lipid-anchor rule in words, with what is stated and what is the tool's own choice."""
    box = "-".join(f"[{allowed}]" for allowed in LIPOBOX)
    return (
        f"A lipid anchor is read by a rule of this tool's own, fixed from open descriptions before it was run and not adjusted to any protein. "
        f"A bacterial lipoprotein is made with a signal peptide of three parts, a positively charged beginning, a hydrophobic stretch and the lipobox, whose cysteine takes the lipid; the signal peptide is on average 16 to 26 residues long ({smithers['who']} {smithers['year']}). "
        f"The rule takes the first cysteine that has a lipobox before it ({box}, the form {desvaux['who']} {desvaux['year']} state for bacteria with one membrane), that sits within the first {ANCHOR_REACH} residues, "
        f"and that is preceded by a stretch of {SIGNAL_WINDOW} residues with a mean hydropathy of {HYDROPHOBIC / 10} or more and no charged residue, with a lysine or an arginine before that stretch. "
        f"The reach of {ANCHOR_REACH} residues and the stretch of {SIGNAL_WINDOW} are this tool's own choice: no source read states a limit."
    )


# Made-up sequences, none a real protein: what the rule must say of each. The rule was
# debugged on these alone.
RULE_CHECKS = [
    ("MKKLLSILGSISLVASSTTVVACGNKTEDSKK", 23),                      # a charged beginning, a hydrophobic stretch, the lipobox V-V-A-C
    ("MKKLLSILGSISLVASSTTVVAAGNKTEDSKK", None),                    # no cysteine
    ("MSELLSILGSISLVASSTTVVACGNKTEDSKK", None),                    # no lysine or arginine before the stretch
    ("MKKDEEKRDSEDKKDTEDSKKLVACGNKTEDS", None),                    # no hydrophobic stretch before the cysteine
    ("MKKLLSILGSISLVASSTTVVPCGNKTEDSKK", None),                    # the residue before the cysteine is not G, A or S
    ("MK" + "A" * 38 + "LAACGNKTEDSKK", None),                       # the cysteine is at residue 44, past the reach
    ("MK" + "A" * 34 + "LAACGNKTEDSKK", 40),                         # the cysteine is at residue 40, the last within reach
    ("MKRIIALLAGLTLVGCSSNDKK", 16),                                # the stretch begins after the arginine
    ("MKKLLSILGSISLVASSTTVVACGNKTEDSKKLLSILGSISLVASSTTVVAC", 23),  # of two cysteines, the first
]


def check_rule():
    for sequence, expected in RULE_CHECKS:
        if lipid_anchor(sequence) != expected:
            raise SystemExit(f"the lipid-anchor rule no longer reads the made-up sequence {sequence[:24]}... as {expected}")
    if (LIPOBOX, ANCHOR_REACH, SIGNAL_WINDOW, HYDROPHOBIC, CHARGED) != (("LVI", "ASTVI", "GAS"), 40, 10, 16, "DEKR"):
        raise SystemExit("the lipid-anchor rule's numbers are not the ones fixed on 15 November 2026; the files' words on it must be rewritten")


# What stands behind a statement in a reviewed entry, by its evidence code, strongest first.
EVIDENCE = [("experiment", {"ECO:0000269"}), ("curator", {"ECO:0000305", "ECO:0000303", "ECO:0000304"}), ("similarity", {"ECO:0000250"}), ("rule", {"ECO:0000255", "ECO:0000256", "ECO:0000259"})]
# The rule systems whose statements may stand behind a stated place, as UniProt names them
# in an entry's evidence, each with terms that were read and allow it. A rule of another
# system stops the build until its terms are read.
RULE_SYSTEMS = {"HAMAP-Rule": "HAMAP"}


def stated_place(c, protein):
    """What reviewed UniProtKB entries with exactly this sequence state of where the protein
    sits: the side it comes to (or None), and each statement with what stands behind it."""
    said = []
    for accession in protein["same"]:
        entry = c.places[accession]
        if not entry["entryType"].startswith("UniProtKB reviewed"):
            continue
        for comment in entry.get("comments", []):
            if comment["commentType"] != "SUBCELLULAR LOCATION":
                continue
            for item in comment.get("subcellularLocations", []):
                place, topology = item["location"]["value"], item.get("topology", {}).get("value", "")
                side = "inside" if place == "Cytoplasm" and not topology else "in" if topology.startswith(("Multi-pass", "Single-pass")) else "outside" if place == "Secreted" else None
                given = [evidence for part in ("location", "topology", "orientation") if item.get(part) for evidence in item[part].get("evidences", [])]
                codes = {evidence["evidenceCode"] for evidence in item["location"].get("evidences", [])}
                behind = next((name for name, known in EVIDENCE if codes & known), None)
                if behind is None:
                    raise SystemExit(f"{accession} states a place on evidence this tool has no word for: {sorted(codes)}")
                # Whose rule: every rule named in the statement is of a system whose terms were read.
                systems = sorted({evidence.get("source") or "sequence analysis" for evidence in given if evidence["evidenceCode"] in dict(EVIDENCE)["rule"]})
                if set(systems) - set(RULE_SYSTEMS):
                    raise SystemExit(f"{accession} states a place by a rule of {systems}; read that system's terms before the statement is used")
                said.append({"side": side, "entry": accession, "organism": entry["organism"]["scientificName"], "words": "; ".join(part for part in (place, topology) if part), "evidence": behind, "peripheral": place == "Cell membrane" and topology.startswith("Peripheral"), "systems": [RULE_SYSTEMS[name] for name in systems]})
    sides = {item["side"] for item in said}
    if len(sides) > 1 and None not in sides:
        raise SystemExit(f"reviewed entries with the sequence of {protein['locus_tag']} state different places: {said}")
    return (said[0]["side"] if len(sides) == 1 else None), said


def plural(n, one, many=None):
    return f"{n} {one if n == 1 else many or one + 's'}"


def upstream_sources(c, checks):
    """The rule systems behind the stated places, each as a source of its own: its terms as
    its own page states them, and the source in whose entries its results were read."""
    hamap = (checks["by_system"][("HAMAP", "side")], checks["by_system"][("HAMAP", "where")])
    if set(system for system, _ in checks["by_system"]) - {"HAMAP"}:
        raise SystemExit("a stated place rests on a rule system that the shelves do not name as a source")
    if not any(hamap):
        return []
    rests = listed([words for words in (f"the stated side of {plural(hamap[0], 'protein')}" if hamap[0] else "", f"the place at the membrane of {hamap[1]}" if hamap[1] else "") if words])
    return [{
        "name": "HAMAP", "cite": "SIB Swiss Institute of Bioinformatics, HAMAP: its family rules, as UniProt applies them in reviewed entries.", "url": "https://hamap.expasy.org/hamap_about.html",
        "licence": "CC BY 4.0", "class": PERMISSIVE, "accessed": c.evidence.day("upstream_hamap_about.html"), "through": SOURCE_NAMES["uniprotkb"],
        "holds": f"Nothing was downloaded from it but its statement of terms. Its family rules are what reviewed entries of other organisms give a place by: {rests} rests on them, as read in UniProt's entries.",
    }]


def slug(text):
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def shelf_citation(c, key):
    record = next(r for r in c.evidence.json("europepmc_shelves_citations.json")["resultList"]["result"] if r["pmid"] == SHELF_PAPERS[key])
    authors = [name.rsplit(" ", 1)[0] for name in record["authorString"].rstrip(".").split(", ")]
    who = authors[0] if len(authors) == 1 else f"{authors[0]} and {authors[1]}" if len(authors) == 2 else f"{authors[0]} and others"
    journal = record["journalInfo"]["journal"]
    where = journal["title"] if " " not in journal["title"] else (journal.get("isoabbreviation") or journal["title"])
    return {"who": who, "year": record["pubYear"], "text": f"{who} ({record['pubYear']}) {record['title'].rstrip('.')}. {where} {record['journalInfo']['volume']}:{record['pageInfo']}.", "doi": record["doi"], "pmid": record["pmid"]}


def check_shelf_sources(c):
    ev = c.evidence
    if scale_in_file(ev.text("biopython_185_ProtParamData.py")) != HYDROPATHY:
        raise SystemExit("the saved file of the hydropathy scale does not give the values this tool uses")
    papers = {record["pmid"]: record for record in ev.json("europepmc_shelves_citations.json")["resultList"]["result"]}
    if set(SHELF_PAPERS.values()) - set(papers):
        raise SystemExit("a paper cited for the shelves was not returned")
    if papers[SHELF_PAPERS["kyte1982"]]["title"].rstrip(".") != "A simple method for displaying the hydropathic character of a protein":
        raise SystemExit("the record of the hydropathy scale's paper is not the one cited")
    if set("".join(protein["sequence"] for protein in c.proteins)) - set(HYDROPATHY):
        raise SystemExit("a protein holds a residue the hydropathy scale has no value for")
    # No entry of this organism or of another states a membrane-spanning segment for one of
    # these exact sequences: the tool's own reading is the only one there is.
    spanning = sorted(accession for accession, entry in c.places.items() if any(feature["type"] == "Transmembrane" for feature in entry.get("features", [])))
    if spanning:
        raise SystemExit(f"an entry with one of these sequences now gives a membrane-spanning stretch; read it and use it: {spanning}")
    anchored = sorted(accession for accession, entry in c.places.items() if entry["entryType"].startswith("UniProtKB reviewed") and any(feature["type"] in ("Signal", "Lipidation") for feature in entry.get("features", [])))
    if anchored:
        raise SystemExit(f"a reviewed entry with one of these sequences now gives a signal or a lipid anchor; read what stands behind it before it is used: {anchored}")
    check_rule()


def build_shelves(c, rows):
    """Where each protein of the catalogue sits against the cell membrane, and how that is known."""
    cite = {key: shelf_citation(c, key) for key in SHELF_PAPERS}
    proteins, tally, basis_tally = [], Counter(), Counter()
    groups = {}
    checks = {"controls": 0, "controls_read_as_spanning": [], "controls_hydrophobic": 0, "controls_anchor_only": 0, "permeases": 0, "permeases_read_as_spanning": 0, "stated": 0, "stated_agree": 0, "anchors": 0, "anchors_kept": 0, "anchors_set_aside": [], "copies_membrane": 0.0, "seen_membrane": 0, "stated_evidence": Counter(), "at_the_membrane": [], "by_system": Counter()}
    for row, protein in zip(rows, c.proteins):
        locus = protein["locus_tag"]
        if row[0] != locus:
            raise SystemExit("the catalogue and the proteins are not in the same order")
        table = c.classes[locus]
        classes = (table["Primary functional class"], table["Secondary functional class"], table["Tertiary functional class"])
        no_doubt = any(classes[0] == first and classes[1] == second and third in (None, classes[2]) for first, second, third in INSIDE_BY_FUNCTION)
        stretches, hydrophobic, best = scan(protein["sequence"])
        anchor = lipid_anchor(protein["sequence"])
        side_stated, said = stated_place(c, protein)
        marks = {"essential": row[7], "seen": row[8] == "yes"}
        measured = c.abundance.get(locus)
        if measured:
            copies = float(f"{measured['copies']:.3g}")
            marks["amount"] = int(copies) if copies == int(copies) else copies
        if row[5] != "minimal genome":
            marks["added"] = True
        if classes[2]:
            marks["class"] = classes[2]
        for name, pattern in COMPLEXES:
            if re.search(pattern, protein["protein"]):
                marks["complex"] = name
        if anchor:
            # The rule reads an anchor. It is kept unless a reviewed entry states the place
            # or the protein's class leaves no doubt that it works inside the cell.
            checks["anchors"] += 1
            if side_stated or no_doubt:
                checks["anchors_set_aside"].append(protein.get("gene") or locus)
            else:
                checks["anchors_kept"] += 1
        if no_doubt:
            checks["controls"] += 1
            checks["controls_hydrophobic"] += hydrophobic
            checks["controls_anchor_only"] += bool(anchor) and not hydrophobic and not side_stated
            if stretches:
                checks["controls_read_as_spanning"].append(protein.get("gene") or locus)
        if re.search(r"permease", protein["protein"], re.I):
            checks["permeases"] += 1
            checks["permeases_read_as_spanning"] += bool(stretches)
        if side_stated:
            checks["stated"] += 1
            checks["stated_agree"] += (side_stated == "inside" and not stretches) or (side_stated == "in" and bool(stretches))

        if side_stated:
            if side_stated == "inside" and stretches:
                raise SystemExit(f"{locus}: a reviewed entry says cytoplasm and the sequence reads as membrane-spanning; read both and decide")
            side, basis = side_stated, "stated"
            entry = next(item for item in said if item["side"] == side_stated)
            marks["stated_in"] = f"{entry['entry']}, {entry['organism']}: {entry['words']}"
            marks["evidence"] = entry["evidence"]
            checks["stated_evidence"][entry["evidence"]] += 1
            for system in entry["systems"]:
                checks["by_system"][(system, "side")] += 1
        elif anchor and not no_doubt:
            beyond = [start for start in stretches if start > anchor]
            if beyond:
                side, basis = "in", "predicted"
                marks["segments"] = len(beyond)
            else:
                side, basis = "outside", "predicted"
            marks["lipid_anchor"] = True
        elif anchor:
            # The rule reads an anchor, and the protein's class leaves no doubt that it
            # works inside the cell: its function decides, and the file says so.
            side, basis = "inside", "by function"
        elif stretches:
            if no_doubt:
                side, basis = "inside", "by function"
            else:
                side, basis = "in", "predicted"
                marks["segments"] = len(stretches)
                if len(stretches) == 1 and stretches[0] <= SIGNAL_START:
                    marks["at_start_only"] = True
        elif hydrophobic:
            side, basis = ("inside", "by function") if no_doubt else ("not known", "none")
        else:
            side, basis = "inside", "predicted"

        # A reviewed entry may place the protein at the membrane without saying which face.
        at_membrane = next((item for item in said if item["peripheral"]), None)
        if at_membrane and basis != "stated":
            if side != "inside":
                raise SystemExit(f"{locus}: a reviewed entry says it is at the membrane as a peripheral protein, and the reading places it {side}; read both and decide")
            marks["where"] = "at the membrane"
            marks["stated_in"] = f"{at_membrane['entry']}, {at_membrane['organism']}: {at_membrane['words']} (by {at_membrane['evidence']})"
            checks["at_the_membrane"].append(protein.get("gene") or locus)
            for system in at_membrane["systems"]:
                checks["by_system"][(system, "where")] += 1

        group = slug(classes[1])
        entry = groups.setdefault(group, {"id": group, "label": classes[1], "within": classes[0], "from": "Breuer and others 2019, supplementary file 3: the secondary functional class", "count": 0, "sides": Counter()})
        if (entry["label"], entry["within"]) != (classes[1], classes[0]):
            raise SystemExit(f"two classes of the 2019 table would share the district {group!r}")
        entry["count"] += 1
        entry["sides"][side] += 1
        tally[side] += 1
        basis_tally[(side, basis)] += 1
        if side in ("in", "outside") and measured:
            checks["copies_membrane"] += measured["copies"]
            checks["seen_membrane"] += 1
        proteins.append([locus, protein["protein"], protein.get("gene", ""), "cell", side, basis, group, len(protein["sequence"]), None, marks])

    if sum(tally.values()) != len(rows) or checks["anchors"] - checks["anchors_kept"] != len(checks["anchors_set_aside"]):
        raise SystemExit("the shelves do not hold every protein of the catalogue once")
    # What the text of the files says of the reading rests on these: if one moves, the words must be reread.
    if checks["stated_agree"] != checks["stated"] or checks["permeases_read_as_spanning"] != checks["permeases"]:
        raise SystemExit(f"the reading of the sequences no longer agrees with the stated cases or misses a permease: {checks}")
    group_list = [{**entry, "sides": {side: entry["sides"][side] for side in SIDES if entry["sides"][side]}} for entry in sorted(groups.values(), key=lambda item: (item["within"], item["label"]))]
    by_basis = {side: {basis: basis_tally[(side, basis)] for basis in BASES if basis_tally[(side, basis)]} for side in SIDES if tally[side]}
    kyte, chambaud, lhernault = cite["kyte1982"], cite["chambaud1999"], cite["lhernault1992"]
    paulet, review = open_paper(c, "paulet2011"), open_paper(c, "christodoulides2018")
    desvaux, smithers, legood = open_paper(c, "desvaux2018"), open_paper(c, "smithers2021"), open_paper(c, "legood2020")
    if (desvaux["who"], smithers["who"], legood["who"], legood["year"]) != ("Desvaux and others", "Smithers and others", "Legood and others", "2020"):
        raise SystemExit("the two reviews the lipid-anchor rule is fixed from are not the ones the files name")
    ev = c.evidence
    breuer = citation(c, "breuer2019")
    thornburg = citation(c, "thornburg2022")
    anchored_in = sum(1 for row in proteins if row[4] == "in" and row[9].get("lipid_anchor"))
    if checks["anchors_kept"] != tally["outside"] + anchored_in:
        raise SystemExit("the lipid-anchored proteins are not all outside or in the membrane")
    checks_out = {
        "inside_by_class": {"proteins": checks["controls"], "with_a_hydrophobic_stretch": checks["controls_hydrophobic"], "with_an_anchor_read_and_no_such_stretch": checks["controls_anchor_only"], "read_as_spanning": checks["controls_read_as_spanning"]},
        "permeases": {"proteins": checks["permeases"], "read_as_spanning": checks["permeases_read_as_spanning"]},
        "stated": {"proteins": checks["stated"], "reading_agrees": checks["stated_agree"], "by_evidence": {name: checks["stated_evidence"][name] for name, _ in EVIDENCE if checks["stated_evidence"][name]}, "said_to_be_at_the_membrane": checks["at_the_membrane"], "by_rule_system": {system: {"sides": checks["by_system"][(system, "side")], "at_the_membrane": checks["by_system"][(system, "where")]} for system in sorted({system for system, _ in checks["by_system"]})}},
        "lipid_anchor": {"read": checks["anchors"], "kept": checks["anchors_kept"], "placed_outside": tally["outside"], "placed_in": anchored_in, "set_aside": checks["anchors_set_aside"]},
        "membrane": {"in_or_on": tally["in"] + tally["outside"], "seen": checks["seen_membrane"], "estimated_copies": round(checks["copies_membrane"]), "all_estimated_copies": c.copies_total},
        "in_the_membrane": {"proteins": tally["in"], "one_stretch": sum(1 for row in proteins if row[4] == "in" and row[9]["segments"] == 1), "one_stretch_at_the_start": sum(1 for row in proteins if row[9].get("at_start_only"))},
    }
    return {
        "format": SHELVES_FORMAT,
        "species": SPECIES_ID,
        "made": SHELVES_MADE,
        "from": f"GenBank {RECORD}: {len(rows)} protein products",
        "shelves": [{"id": "cell", "label": "Cell membrane", "outside": "Outside the cell", "inside": "Inside the cell"}],
        "groups": group_list,
        "columns": SHELF_COLUMNS,
        "proteins": proteins,
        "side_notes": {
            "stated": "Taken from a reviewed UniProtKB entry whose sequence is, letter for letter, this protein's. Each such entry is of another organism, named in the mark stated_in: it states the place of the same protein there, not in JCVI-syn3A." + ("" if checks["stated_evidence"]["experiment"] else " None of these statements rests on an experiment: each is made by a family rule or by similarity, as the mark evidence says."),
            "predicted": f"This tool's own reading of the sequence, not the output of an established predictor: UniProt's archive holds family signatures on these sequences and no prediction of membrane-spanning stretches. A stretch of {WINDOW} residues is read as membrane-spanning where its mean hydropathy on Kyte and Doolittle's scale is {HYDROPHOBIC / 10} or more and it holds no charged residue, or {STRONG / 10} or more with at most one. The window of {WINDOW} and the level of {HYDROPHOBIC / 10} are the usual reading of that scale ({paulet['who']} {paulet['year']} state it); the conditions on charged residues are this tool's, set against this organism's own proteins. A protein with such a stretch is placed in the membrane. A protein with none and no lipid anchor is placed inside, which includes proteins attached to the membrane's inner face. {anchor_rule(desvaux, smithers)} Such a protein is placed outside, because the lipoproteins of mycoplasmas are bound to the membrane and exposed on the cell's surface ({review['who']} {review['year']}, said of mycoplasmas in general and not measured in this strain).",
            "by function": "The sequence has a hydrophobic stretch, or reads as carrying a lipid anchor, but the protein's class in the 2019 paper leaves no doubt that it works inside the cell: translation, transcription, the upkeep of DNA, sugar breakdown, the pentose phosphate pathway or nucleotide metabolism. Function is never used to place a transport protein.",
            "none": "The sequence has a hydrophobic stretch that holds charged residues, and the protein's function is not known: nothing settles its side, so it is not placed.",
        },
        "marks": {
            "essential": {"label": "Essentiality", "values": ["essential", "quasi-essential", "non-essential"], "measured": True, "note": "Measured by transposon mutagenesis in this strain, then classified by the paper's model.", "source": SOURCE_NAMES["breuer2019"]},
            "seen": {"label": "Seen in the proteomics", "values": [True, False], "measured": True, "source": SOURCE_NAMES["breuer2019"]},
            "amount": {"label": "Estimated copies in a cell", "values": "number", "measured": False, "note": f"An estimate: the measured share of the protein signal, scaled to the paper's estimate of {c.copies_total:,} protein molecules in a cell. Given only for proteins that were seen.", "source": SOURCE_NAMES["breuer2019"]},
            "added": {"label": "Added for genetic manipulation", "values": [True], "measured": False, "note": "tetM and the yeast genes HIS3 and MET14: not part of the minimal genome.", "source": SOURCE_NAMES["breuer2019"]},
            "class": {"label": "Finer class", "values": "text", "measured": False, "note": "The 2019 paper's tertiary functional class, for laying out a district.", "source": SOURCE_NAMES["breuer2019"]},
            "complex": {"label": "Assembly", "values": [name for name, _ in COMPLEXES], "measured": False, "note": "Named outright by the genome record's product name: a ribosomal protein, a subunit of the ATP synthase or of RNA polymerase. Other assemblies are not marked.", "source": SOURCE_NAMES["genbank"]},
            "segments": {"label": "Membrane-spanning stretches read from the sequence", "values": "number", "measured": False, "note": "This tool's reading; a count of stretches, not a topology. It can fall short, since a stretch that holds charged residues is not read.", "source": SOURCE_NAMES["scale"]},
            "lipid_anchor": {"label": "Lipid anchor read from the sequence", "values": [True], "measured": False, "note": f"This tool's reading, by a rule of its own: a lipobox within the first {ANCHOR_REACH} residues, with a hydrophobic stretch before its cysteine and a lysine or an arginine before that. Such a protein is placed outside, unless a membrane-spanning stretch follows the anchor: then it is placed in the membrane. No lipid was measured on any of these proteins. The rule is strict: lipoboxes of other forms have been reported ({legood['who']} {legood['year']}), and a lipoprotein with such a one is not called. It is then placed like any other protein, usually in the membrane by the hydrophobic stretch of its signal, with the mark that its one stretch is at its start.", "source": SOURCE_NAMES["desvaux2018"]},
            "at_start_only": {"label": "Its one stretch is at the protein's start", "values": [True], "measured": False, "note": "The only stretch read begins within the first 12 residues. It may be an export signal that is cut off, and the protein would then sit outside and not span the membrane. Nothing read here tells the two apart.", "source": SOURCE_NAMES["scale"]},
            "evidence": {"label": "What stands behind a stated side", "values": [name for name, _ in EVIDENCE], "measured": False, "note": "From the reviewed entry that states the place: an experiment, a curator's inference, similarity to another protein, or a family rule.", "source": SOURCE_NAMES["uniprotkb"]},
            "where": {"label": "Where within its side", "values": ["at the membrane"], "measured": False, "note": "A reviewed entry of another organism, with the same sequence, says the protein is at the cell membrane as a peripheral protein, without saying which face. Its side here is this tool's reading: inside, which includes the membrane's inner face.", "source": SOURCE_NAMES["uniprotkb"]},
            "stated_in": {"label": "Stated in", "values": "text", "measured": False, "note": "The reviewed entry of another organism, with the same sequence, that states the place, with its words.", "source": SOURCE_NAMES["uniprotkb"]},
        },
        "counts": {side: tally[side] for side in SIDES},
        "by_basis": by_basis,
        "unit_note": "No protein has a unit: the atlas found none of the law inventory's units in this organism (data/proteins/atlases/syn3a.json).",
        "checks": checks_out,
        "sources": [
            {"name": SOURCE_NAMES["genbank"], "cite": f"Glass J (2017) {c.record_title}. GenBank {RECORD}.", "url": f"https://www.ncbi.nlm.nih.gov/nuccore/{RECORD}", "licence": "NCBI places no restrictions on the use or distribution of GenBank data; this record states none", "class": PERMISSIVE, "accessed": ev.day(f"genbank_{RECORD}_cds_aa.fa"), "holds": "The proteins, their names and lengths. Their sequences were read and are not copied."},
            {"name": SOURCE_NAMES["breuer2019"], "cite": breuer["text"], "url": f"https://doi.org/{breuer['doi']}", "licence": "CC BY 4.0", "class": PERMISSIVE, "accessed": ev.day("elife_36842_supp3.xlsx"), "holds": "The functional classes that name the districts, essentiality, detection and estimated copies (supplementary files 3 and 5)."},
            {"name": SOURCE_NAMES["uniparc"], "cite": f"UniProt Consortium, UniParc release {c.uniprot_release}: the archived protein sequences of taxon {TAXON}.", "url": f"https://www.uniprot.org/uniparc?query=taxonomy_id:{TAXON}", "licence": "CC BY 4.0", "class": PERMISSIVE, "accessed": ev.day(f"uniparc_{TAXON}.json"), "holds": "That its archive holds exactly these sequences, and which UniProtKB entries of other organisms have the same ones. No signature of another database is read from it for the shelves."},
            {"name": SOURCE_NAMES["uniprotkb"], "cite": f"UniProt Consortium, UniProtKB release {ev.record('uniprotkb_identical_places.json')['uniprot_release']}: reviewed entries of other organisms with the same sequences.", "url": "https://www.uniprot.org/", "licence": "CC BY 4.0", "class": PERMISSIVE, "accessed": ev.day("uniprotkb_identical_places.json"), "holds": "The place those entries state and what stands behind it, for the proteins whose side is stated or that are said to be at the membrane."},
            {"name": SOURCE_NAMES["scale"], "cite": "The Biopython contributors, Biopython release 1.85: the file Bio/SeqUtils/ProtParamData.py, which lists the scale and names Kyte and Doolittle's paper of 1982 as its origin.", "url": BIOPYTHON_PAGE, "licence": "Biopython License Agreement or BSD 3-Clause License", "class": PERMISSIVE, "accessed": ev.day("biopython_185_ProtParamData.py"), "holds": "The 20 values of Kyte and Doolittle's hydropathy scale that the sequences are read with, as this file lists them."},
            {"name": SOURCE_NAMES["paulet2011"], "cite": paulet["text"], "url": f"https://doi.org/{paulet['doi']}", "licence": OPEN_LICENCE["paulet2011"], "class": PERMISSIVE, "accessed": paulet["accessed"], "holds": f"The usual reading of the scale: a window of {WINDOW} residues, and a mean above {HYDROPHOBIC / 10} for a stretch that spans a membrane."},
            {"name": SOURCE_NAMES["christodoulides2018"], "cite": review["text"], "url": f"https://doi.org/{review['doi']}", "licence": OPEN_LICENCE["christodoulides2018"], "class": PERMISSIVE, "accessed": review["accessed"], "holds": "That the lipoproteins of mycoplasmas are bound to the membrane and exposed on the cell's surface."},
            # A rule system whose results were read in a database's entries: its own terms, and through which source it was read.
            *upstream_sources(c, checks),
            {"name": SOURCE_NAMES["desvaux2018"], "cite": desvaux["text"], "url": f"https://doi.org/{desvaux['doi']}", "licence": OPEN_LICENCE["desvaux2018"], "class": PERMISSIVE, "accessed": desvaux["accessed"], "holds": "The lipobox, as the review states it for bacteria with one membrane: the residues allowed at the three places before the cysteine that takes the lipid."},
            {"name": SOURCE_NAMES["smithers2021"], "cite": smithers["text"], "url": f"https://doi.org/{smithers['doi']}", "licence": OPEN_LICENCE["smithers2021"], "class": PERMISSIVE, "accessed": smithers["accessed"], "holds": "The three parts of a lipoprotein's signal peptide (a positively charged beginning, a hydrophobic stretch, the lipobox) and its usual length."},
            {"name": SOURCE_NAMES["legood2020"], "cite": legood["text"], "url": f"https://doi.org/{legood['doi']}", "licence": OPEN_LICENCE["legood2020"], "class": PERMISSIVE, "accessed": legood["accessed"], "holds": "That lipoboxes of other forms than the usual one have been reported: what the rule can miss."},
            # Pointers: named so that they can be read; nothing in this file rests on them.
            {"name": SOURCE_NAMES["kyte1982"], "cite": kyte["text"], "url": f"https://doi.org/{kyte['doi']}", "licence": "No open licence stated: the paper's record names none and does not count it as open access", "class": NO_TERMS, "accessed": ev.day("europepmc_shelves_citations.json"), "holds": "Nothing is taken from it: a pointer to the paper that defined the hydropathy scale. The scale's values were taken from Biopython's file, and only this paper's bibliographic record was read."},
            {"name": SOURCE_NAMES["lhernault1992"], "cite": lhernault["text"], "url": f"https://doi.org/{lhernault['doi']}", "licence": "CC BY-NC-SA 4.0", "class": NON_COMMERCIAL, "accessed": ev.day(LHERNAULT), "holds": "Nothing is taken from it: a pointer to a paper that uses the hydropathy scale to find the membrane-spanning stretches of a protein."},
            {"name": SOURCE_NAMES["chambaud1999"], "cite": chambaud["text"], "url": f"https://doi.org/{chambaud['doi']}", "licence": "No open licence stated: the paper's record names none and does not count it as open access", "class": NO_TERMS, "accessed": ev.day("europepmc_shelves_citations.json"), "holds": "Nothing is taken from it: a pointer to a review of where the lipoproteins of mycoplasmas are anchored. Only its bibliographic record was read."},
            {"name": SOURCE_NAMES["thornburg2022"], "cite": thornburg["text"], "url": f"https://doi.org/{thornburg['doi']}", "licence": "CC BY-NC-ND 4.0", "class": NON_COMMERCIAL, "accessed": ev.day(THORNBURG), "holds": "Nothing is taken from it: a pointer to the whole-cell model's own count of membrane proteins and of their copies, for comparison with this file's."},
        ],
    }


def dump_shelves(shelves):
    """The shelves as text: one protein to a line, so that a change shows as the lines it touches."""
    head = json.dumps({**shelves, "proteins": "@proteins@"}, indent=1, ensure_ascii=False)
    lines = ",\n".join("  " + json.dumps(row, ensure_ascii=False, separators=(",", ":")) for row in shelves["proteins"])
    if head.count('"@proteins@"') != 1:
        raise SystemExit("the shelves cannot be written one protein to a line")
    return head.replace('"@proteins@"', "[\n" + lines + "\n ]") + "\n"


def build(evidence_folder, datasets_folder, snapshot):
    evidence = Evidence(evidence_folder, datasets_folder)
    context = Context(evidence, snapshot)
    check_sources(context)
    check_shelf_sources(context)
    species = build_species(context)
    atlas = build_atlas(context)
    rows = build_catalogue(context)
    shelves = build_shelves(context, rows)
    files = {
        "species": json.dumps(species, indent=1, ensure_ascii=False) + "\n",
        "atlas": json.dumps(atlas, indent=1, ensure_ascii=False) + "\n",
        "catalogue": table(rows),
        "shelves": dump_shelves(shelves),
        "readme": build_readme(context, rows, shelves),
    }
    for name, text in files.items():
        if PATHS.search(text):
            raise SystemExit(f"the {name} would hold a machine path")
    for name in ("catalogue", "shelves"):
        if len(files[name].encode("utf-8")) > 1_000_000:
            raise SystemExit(f"the {name} has grown past 1 MB")
    if json.loads(files["shelves"]) != json.loads(json.dumps(shelves)):
        raise SystemExit("the shelves were not written as they were built")
    return files, species, atlas, rows, shelves, context


def summary(species, atlas, rows, shelves, context):
    findings = Counter(unit["finding"] for unit in atlas["units"].values())
    places = Counter(item["place"] for item in species["cell"]["capabilities"].values())
    lines = [
        f"frozen annotation: GenBank {RECORD}, {context.length:,} bp; {len(context.genes)} genes, {len(rows)} protein products ({sum(row[5] == 'minimal genome' for row in rows)} kept, {sum(row[5] != 'minimal genome' for row in rows)} added), {len(context.pseudo)} pseudogenes",
        f"units by finding: {dict(sorted(findings.items()))}; extra: {len(atlas['extra'])} ({dict(Counter(p['evidence'] for p in atlas['extra']))})",
        f"capabilities stated: {dict(sorted(places.items()))} of {len(species['cell']['capabilities'])}",
        f"catalogue: essentiality {dict(Counter(row[7] for row in rows))}; detected {sum(row[8] == 'yes' for row in rows)}; with an identical UniProtKB entry elsewhere {sum(bool(row[12]) for row in rows)}",
        "mollicute entries carrying a searched signature: " + (", ".join(f"{s} {context.mollicutes(s)}" for s in sorted({*rule_signatures(), *BACTERIAL_CHANNELS, PROTEASOME}) if context.mollicutes(s)) or "none"),
        "entries of the parent species carrying a bacterial channel signature: " + ", ".join(f"{s} {context.parent(s)}" for s in sorted(BACTERIAL_CHANNELS)),
        "essentiality of the kept genes: " + str(dict(Counter(row[7] for row in rows if row[5] == "minimal genome"))) + "; of the added: " + str(dict(Counter(row[7] for row in rows if row[5] != "minimal genome"))),
        f"shelves: by side {shelves['counts']}; by basis {shelves['by_basis']}",
        f"shelves, checks: {shelves['checks']}",
        "shelves, districts: " + "; ".join(f"{group['label']} {group['sides']}" for group in shelves["groups"]),
    ]
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("step", choices=["fetch", "build"], help="fetch asks the databases and saves the answers; build reads only what was saved")
    parser.add_argument("--evidence", required=True, help="the analysis folder: the log of what was asked (kept outside the repository)")
    parser.add_argument("--datasets", required=True, help="the folder of downloads, one folder per source with its MANIFEST.json (kept outside the repository)")
    parser.add_argument("--inputs-record", help="build: also write, to this file, every file that was read with the SHA-256 its MANIFEST gives")
    parser.add_argument("--refresh", action="store_true", help="fetch: ask again even where an answer is saved")
    parser.add_argument("--out-species", default=str(SPECIES_FILE))
    parser.add_argument("--out-atlas", default=str(ATLAS))
    parser.add_argument("--out-catalogue", default=str(CATALOGUE_DIR), help="the folder for proteins.tsv, shelves.json and their README.md")
    args = parser.parse_args()
    snapshot = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    if args.step == "fetch":
        sys.exit(1 if fetch(Path(args.evidence), Path(args.datasets), snapshot, refresh=args.refresh) else 0)
    files, species, atlas, rows, shelves, context = build(Path(args.evidence), Path(args.datasets), snapshot)
    targets = {"species": Path(args.out_species), "atlas": Path(args.out_atlas), "catalogue": Path(args.out_catalogue) / CATALOGUE_FILE, "shelves": Path(args.out_catalogue) / SHELVES_FILE, "readme": Path(args.out_catalogue) / "README.md"}
    for name, target in targets.items():
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(files[name], encoding="utf-8")
        print(f"wrote {target} ({len(files[name].encode('utf-8')):,} bytes)")
    print(summary(species, atlas, rows, shelves, context))
    if args.inputs_record:
        read = context.evidence.files_read()
        Path(args.inputs_record).write_text(json.dumps({"note": "Every file this run read, with the SHA-256 that the MANIFEST of its dataset folder gives; each was checked against it before it was read.", "files": read}, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"wrote {args.inputs_record} ({len(read)} files read)")


if __name__ == "__main__":
    main()
