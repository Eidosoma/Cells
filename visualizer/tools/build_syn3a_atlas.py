#!/usr/bin/env python3
"""Build the viewer's data on the minimal cell JCVI-syn3A, and the start of its protein catalogue.

Three things are written, each from saved responses of public databases and open papers:

    data/species/syn3a.json            the species file (schema/SPECIES.md): its levels, the
                                       cell's shape and parts, and which of Cells' capabilities
                                       have a place in it
    data/proteins/atlases/syn3a.json   its side of the protein atlas (schema/SPECIES_ATLAS.md):
                                       an entry for every unit of the law inventory
    data/proteins/syn3a/               proteins.tsv, one line per protein product of one frozen
                                       genome annotation, and the README that explains it

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
MADE = "2026-11-14"

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

PAPERS = {
    "breuer2019": "30657448", "gilbert2021": "34368224", "thornburg2022": "35063075",
    "pelletier2021": "33784496", "hutchison2016": "27013737", "thornburg2026": "41806832",
}
LICENCES = {"breuer2019": "CC BY 4.0", "gilbert2021": "CC BY 4.0", "thornburg2022": "CC BY-NC-ND 4.0"}


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
     "why": "Part of the cell's F-type ATP synthase, which sits in its one membrane; four of its eight subunits are listed here. In mycoplasmas this machine typically runs backwards, spending ATP to pump protons out, which was measured in related species and not in this strain. The law inventory has no F-type ATPase."},
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
     "why": "The membrane part of the system that brings in glucose, the cell's fuel. All of its ATP comes from breaking that sugar down."},
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
    "ncbi-pmc-PMC9985924": {"pmcid": "PMC9985924", "doi": "10.1016/j.cell.2021.12.025", "licence": "CC BY-NC-ND 4.0", "what": "Thornburg and others 2022, the author manuscript (JATS XML), read for numbers and one short quotation"},
    "terms-syn3a-sources": {"what": "Terms of use as read before anything was copied: GenBank's data usage statement, the policy of the nucleotide sequence databases, InterPro's licence and EMBL-EBI's terms"},
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
    (BREUER, r"Creative Commons Attribution License"),
    (GILBERT, r"small cell of radius 201\.26 nm with 503 ribosomes and large cell of radius 247\.42 nm with 820 ribosomes"),
    (GILBERT, r"small cell of radius 203\.52 nm with 684 ribosomes and large cell of radius 241\.20 nm with 1,095 ribosomes"),
    (GILBERT, r"the synthetic cells lack a cell wall"),
    (GILBERT, r"ribosomes appear to be nearly randomly distributed throughout the cell"),
    (GILBERT, r"Creative Commons Attribution License \(CC BY\)"),
    (THORNBURG, r"Syn3A does not have the proteins to perform oxidative phosphorylation, so all ATP in Syn3A is generated by the central metabolism"),
    (THORNBURG, r"In Mycoplasmas, the ATP synthase typically breaks down ATP and pumps out protons"),
    (THORNBURG, r"has retained few regulatory proteins or small RNAs"),
    (THORNBURG, r"CC BY-NC-ND license"),
    ("terms_ncbi_genbank.html", r"NCBI places no restrictions on the use or distribution of the GenBank data"),
    ("terms_insdc_policy.html", r"no use restrictions or licensing requirements will be included in any sequence data records"),
    ("terms_uniprot_license.json", r"Creative Commons Attribution 4\.0 International \(CC BY 4\.0\) License"),
    ("terms_interpro_license.html", r"CC0"),
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
    if "two known cell division genes, ftsZ and sepF" not in papers[PAPERS["pelletier2021"]].get("abstractText", ""):
        raise SystemExit("the division paper's abstract no longer names ftsZ and sepF")
    if "473 genes" not in papers[PAPERS["hutchison2016"]].get("abstractText", ""):
        raise SystemExit("the 2016 abstract no longer gives JCVI-syn3.0's gene count")
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


def sources_of_species(c):
    ev = c.evidence
    out = {}
    for key, name in [("breuer2019", BREUER), ("gilbert2021", GILBERT), ("thornburg2022", THORNBURG)]:
        cite = citation(c, key)
        out[key] = {"text": cite["text"], "doi": cite["doi"], "licence": LICENCES[key] + (", read for numbers and one short quotation" if key == "thornburg2022" else ""), "accessed": ev.day(name)}
    cite = citation(c, "pelletier2021")
    out["pelletier2021"] = {"text": cite["text"] + " Abstract only.", "doi": cite["doi"], "accessed": ev.day("europepmc_citations.json")}
    out["genbank"] = {
        "text": f"Glass J (2017) {c.record_title}. GenBank {RECORD}, annotation of 12 April 2018.",
        "url": f"https://www.ncbi.nlm.nih.gov/nuccore/{RECORD}",
        "licence": "NCBI places no restrictions on the use or distribution of GenBank data; submitters may claim rights in what they submitted, and this record states none",
        "accessed": ev.day(f"genbank_{RECORD}_features.ft"),
    }
    out["uniparc"] = {
        "text": f"UniProt Consortium, UniParc release {c.uniprot_release}: the archived protein sequences of taxon {TAXON} and the family signatures on them.",
        "url": f"https://www.uniprot.org/uniparc?query=taxonomy_id:{TAXON}",
        "licence": "CC BY 4.0",
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
        "cap.membrane": {"place": "present", "note": "Its one membrane holds the cell's ion and proton gradients. In mycoplasmas the ATP synthase typically runs backwards and pumps protons out; that was measured in related species, not in this strain."},
        "cap.channels": {"place": "absent", "why": f"No ion channel was found among its {count} proteins: none carries the signature of a channel family in Cells' catalogue, or of the bacterial channels for potassium, chloride, magnesium, water or membrane stretch, which the same search does find in other mollicutes. Its ions cross the membrane through transporters and pumps."},
        "cap.pumps": {"place": "present", "note": "Not the pumps of animal cells: it has no sodium-potassium pump. By its annotation, its ATP-driven ion movers are the ATP synthase, two P-type ATPases named as magnesium transporters, and a potassium uptake system."},
        "cap.junctions": {"place": "absent", "why": "It lives as single cells and has no gap junctions: none of its proteins carries the signature of connexins or innexins."},
        "cap.extracellular": {"place": "present", "note": "Here it is the growth medium around the single cell, which the cell depends on. By the 2019 reconstruction of its metabolism it takes up glucose, amino acids, fatty acids and cholesterol from a rich medium."},
        "cap.water": {"place": "present", "note": "It has no cell wall: nothing but the membrane bounds its volume."},
        "cap.calcium": {"place": "absent", "why": "It has no endoplasmic reticulum: it is a bacterium with a single membrane and no internal compartments, and none of its proteins carries the signature of the store's calcium pump or of its release channels."},
        "cap.energy": {"place": "present", "note": "All of its ATP comes from breaking down sugar in the cytoplasm; it has no proteins for oxidative phosphorylation."},
        "cap.mitochondria": {"place": "absent", "why": "It is a bacterium and has no mitochondria. Its ATP synthase sits in the cell membrane."},
        "cap.circuits": {"place": "present", "note": "At the chromosome, which lies in the cytoplasm: there is no nucleus. The minimised genome kept few regulatory proteins."},
        "cap.grn": {"place": "absent", "why": "It forms no tissue, so there is nothing for gene networks to be coupled across. Gene expression within the one cell belongs with regulatory circuits."},
        "cap.trafficking": {"place": "absent", "why": "It has no endoplasmic reticulum and no Golgi. By its annotation, new membrane proteins are put straight into the cell membrane by the Sec translocon and the YidC insertase."},
        "cap.assembly": {"place": "present", "note": "Its assemblies are its ribosomes, RNA polymerase and the ATP synthase. The designed protein cage that Cells models is not one of its proteins."},
        "cap.machines": {"place": "present", "note": "About 500 ribosomes, with RNA polymerase, the ATP synthase and the protein translocon. None of its proteins carries the proteasome's signature; its annotation lists the proteases FtsH and Lon."},
        "cap.secretion": {"place": "present", "note": "By the 2019 reconstruction of its metabolism it releases the end products of sugar breakdown, lactate and acetate, into the medium and takes nutrients up. Signalling between its cells was not looked for."},
        "cap.repair": {"place": "present", "note": "The place would be its bare membrane. No source read for this file describes a membrane injury or its resealing in this organism."},
        "cap.division": {"place": "present", "note": "It grows and divides as a single cell. Seven genes that the smaller strain JCVI-syn3.0 lacks, the division genes ftsZ and sepF among them, are needed together for its regular shape and division."},
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
        {"label": "Energy", "value": "ATP from sugar breakdown alone; no oxidative phosphorylation", "sources": ["thornburg2022"]},
        {"label": "Food", "value": "glucose, amino acids, fatty acids and cholesterol, taken up from a rich medium that is not fully defined", "sources": ["breuer2019"]},
        {"label": "Ion channels", "value": f"none found among its {count} proteins", "sources": ["uniparc"]},
        {"label": "Division", "value": "ftsZ and sepF are among seven genes needed together for regular shape and division", "sources": ["pelletier2021"]},
        {"label": "Origin", "value": "a genome designed and synthesised from that of Mycoplasma mycoides subspecies capri, strain GM12, and cut down to a minimum", "sources": ["genbank", "breuer2019"]},
    ]
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
            "text": "JCVI-syn3A is the project's minimal-cell track (decision D173, 14 November 2026), taken up from a note that proposes it as the first whole-cell validation organism for Cells. Nothing of it is in the engine yet: the project's record holds an evidence audit and a proposal, in which no engine model ran.",
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
        "sources": sources_of_species(c),
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
    cite = citation(c, "breuer2019")
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
                "cite": f"Glass J (2017) {c.record_title}. GenBank {RECORD}.",
                "holds": "the locus tags, gene names, products, protein identifiers and lengths of the organism's proteins",
            },
            {
                "name": "UniProt", "url": "https://www.uniprot.org/", "release": c.uniprot_release, "accessed": ev.day(f"uniparc_{TAXON}.json"), "licence": "CC BY 4.0",
                "cite": "The UniProt Consortium, UniProt: the Universal Protein Knowledgebase in 2025, Nucleic Acids Res. 53:D609-D617 (2025)",
                "holds": "which archived sequences of the organism carry each family signature; the signatures of the units' human candidates; the control counts",
            },
            {
                "name": "InterPro", "url": "https://www.ebi.ac.uk/interpro/", "accessed": ev.day("terms_interpro_license.html"), "licence": "CC0 1.0",
                "cite": "Blum and others (2025) InterPro: the protein sequence classification resource in 2025. Nucleic Acids Res 53:D444-D456.",
                "holds": "the identifiers and names of the family signatures, as UniProt gives them",
            },
            {
                "name": "Breuer and others 2019", "url": f"https://doi.org/{breuer['doi']}", "accessed": ev.day(BREUER), "licence": "CC BY 4.0",
                "cite": breuer["text"],
                "holds": "the names the paper gives five of the organism's transport proteins",
            },
            {
                "name": "Europe PMC", "url": "https://europepmc.org/", "accessed": ev.day("europepmc_citations.json"),
                "licence": "Bibliographic facts only (authors, title, journal, year, identifiers). Open texts were read to check names and are not copied.",
                "cite": "Europe PMC Consortium, Europe PMC, https://europepmc.org/.",
                "holds": "the record of the paper cited",
            },
        ],
        "not_copied": "No sequence is copied: they stay with the downloads, outside the repository. The 2022 whole-cell paper (CC BY-NC-ND) was read for numbers and one short quotation, and the 2021 division paper for its abstract; nothing else was taken from them. The 2026 whole-cell paper and the archive of its model were not read for this file, and the instrument files of the 2019 proteomics (PXD008159) were not downloaded.",
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


def build_readme(c, rows):
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
    ]
    inputs = "\n".join(f"| {what} | `{ev.read[name]['source']}` | `{ev.read[name]['file']}` | `{ev.read[name]['sha256']}` |" for what, name in built_from)
    day_record, day_paper, day_archive = ev.day(f"genbank_{RECORD}_cds_aa.fa"), ev.day("elife_36842_supp3.xlsx"), ev.day(f"uniparc_{TAXON}.json")
    return f"""# Syn3A proteins: the start of a catalogue

`{CATALOGUE_FILE}` lists the {count} protein products of one frozen genome annotation of the
minimal cell {ORGANISM}, one per line, with what open sources say of each: what it is
named, how long it is, what it is for, whether the cell can do without it, and how many
copies were estimated in a cell.

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
any model, structures, and anything about where a protein sits in the cell. Strain
identity matters: every value is for {ORGANISM} itself. Nothing is carried over from
JCVI-syn3.0, JCVI-syn3B or *Mycoplasma mycoides*, except that `uniprotkb_identical` names
other organisms' entries and says so.

## Sources and terms

| Source | What is taken | Terms |
| --- | --- | --- |
| [GenBank {RECORD}](https://www.ncbi.nlm.nih.gov/nuccore/{RECORD}), read {day_record} | Locus tags, gene names, products, protein identifiers, lengths | "NCBI places no restrictions on the use or distribution of the GenBank data"; submitters may claim rights in what they submitted, and this record states none |
| [Breuer and others 2019](https://doi.org/{breuer['doi']}), supplementary files 3 and 5, read {day_paper} | Origin, functional class, essentiality, detection and estimated copies | CC BY 4.0 |
| [UniProt](https://www.uniprot.org/), release {c.uniprot_release}, read {day_archive} | Archive identifiers, signatures, and other organisms' entries with the same sequence | CC BY 4.0 |
| [InterPro](https://www.ebi.ac.uk/interpro/) | The signatures' identifiers | CC0 1.0 |

Cite:

- GenBank: Glass J (2017) {c.record_title}. GenBank {RECORD}.
- {breuer['text']} doi:{breuer['doi']}
- The UniProt Consortium, UniProt: the Universal Protein Knowledgebase in 2025, Nucleic Acids Res. 53:D609-D617 (2025)

## The files it was built from

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
log of what this tool asked. Both are kept outside the repository. The build also writes
`data/species/syn3a.json` and `data/proteins/atlases/syn3a.json`. `docs/SYN3A.md`
describes the method and its limits.
"""


def build(evidence_folder, datasets_folder, snapshot):
    evidence = Evidence(evidence_folder, datasets_folder)
    context = Context(evidence, snapshot)
    check_sources(context)
    species = build_species(context)
    atlas = build_atlas(context)
    rows = build_catalogue(context)
    files = {
        "species": json.dumps(species, indent=1, ensure_ascii=False) + "\n",
        "atlas": json.dumps(atlas, indent=1, ensure_ascii=False) + "\n",
        "catalogue": table(rows),
        "readme": build_readme(context, rows),
    }
    for name, text in files.items():
        if PATHS.search(text):
            raise SystemExit(f"the {name} would hold a machine path")
    if len(files["catalogue"].encode("utf-8")) > 1_000_000:
        raise SystemExit("the catalogue has grown past 1 MB")
    return files, species, atlas, rows, context


def summary(species, atlas, rows, context):
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
    parser.add_argument("--out-catalogue", default=str(CATALOGUE_DIR), help="the folder for proteins.tsv and its README.md")
    args = parser.parse_args()
    snapshot = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    if args.step == "fetch":
        sys.exit(1 if fetch(Path(args.evidence), Path(args.datasets), snapshot, refresh=args.refresh) else 0)
    files, species, atlas, rows, context = build(Path(args.evidence), Path(args.datasets), snapshot)
    targets = {"species": Path(args.out_species), "atlas": Path(args.out_atlas), "catalogue": Path(args.out_catalogue) / CATALOGUE_FILE, "readme": Path(args.out_catalogue) / "README.md"}
    for name, target in targets.items():
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(files[name], encoding="utf-8")
        print(f"wrote {target} ({len(files[name].encode('utf-8')):,} bytes)")
    print(summary(species, atlas, rows, context))
    if args.inputs_record:
        read = context.evidence.files_read()
        Path(args.inputs_record).write_text(json.dumps({"note": "Every file this run read, with the SHA-256 that the MANIFEST of its dataset folder gives; each was checked against it before it was read.", "files": read}, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"wrote {args.inputs_record} ({len(read)} files read)")


if __name__ == "__main__":
    main()
