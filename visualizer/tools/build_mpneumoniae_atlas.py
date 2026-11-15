#!/usr/bin/env python3
"""Build the viewer's data on the bacterium Mycoplasma pneumoniae M129, and its protein catalogue.

Four things are written, each from saved responses of public databases and open papers:

    data/species/mpneumoniae.json            the species file (schema/SPECIES.md): its levels,
                                             the cell's shape and parts, and which of Cells'
                                             capabilities have a place in it
    data/proteins/atlases/mpneumoniae.json   its side of the protein atlas
                                             (schema/SPECIES_ATLAS.md): an entry for every unit
                                             of the law inventory
    data/proteins/mpneumoniae/proteins.tsv   one line per protein product of one frozen genome
                                             annotation, and the README that explains it
    data/proteins/mpneumoniae/shelves.json   where each of those proteins sits against the cell
                                             membrane (schema/SPECIES_PROTEINS.md)

Two steps, kept apart, and two folders: DATA holds the downloads, one folder per source
with a MANIFEST.json that gives each file's address, time and SHA-256; DIR holds the
analysis, which is the log of what this tool asked and the record of what a build read.

    python3 tools/build_mpneumoniae_atlas.py fetch --evidence DIR --datasets DATA
        asks public databases for what is not yet in DATA and saves each answer in the
        folder of its source, with a line in DIR/requests.json. The only step that uses
        the network. Folders that another agent made are read and never written.

    python3 tools/build_mpneumoniae_atlas.py build --evidence DIR --datasets DATA
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
SPECIES_FILE = ROOT / "data" / "species" / "mpneumoniae.json"
ATLAS = ROOT / "data" / "proteins" / "atlases" / "mpneumoniae.json"
CATALOGUE_DIR = ROOT / "data" / "proteins" / "mpneumoniae"
CATALOGUE_FILE = "proteins.tsv"
SHELVES_FILE = "shelves.json"
SPECIES_FORMAT = "cells.visualizer.species@1"
ATLAS_FORMAT = "cells.visualizer.species_atlas@1"
SHELVES_FORMAT = "cells.visualizer.species_proteins@1"
CLIENT = "atlas-builder/1.0"
PATHS = re.compile(r"/(?:home|mnt|Users|tmp)/")
MADE = "2026-11-15"

SPECIES_ID = "mpneumoniae"
LABEL = "M. pneumoniae"
ORGANISM = "Mycoplasma pneumoniae M129"
TAXON = 272634               # the strain, M129 (ATCC 29342)
RECORD = "U00089.2"          # the frozen annotation: the submitters' record, re-annotated in 2000
REFSEQ = "NC_000912.1"       # the same sequence as NCBI's own pipeline annotates it; read only for its counts
MOLLICUTES = 31969           # the class of bacteria the organism belongs to

EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
UNIPROT = "https://rest.uniprot.org"
OPEN = "https://pmc-oa-opendata.s3.amazonaws.com"  # PubMed Central's store of open articles and their files
HUMAN_FIELDS = "accession,gene_primary,protein_name,length,xref_interpro"
ENTRY_FIELDS = "accession,id,reviewed,protein_name,gene_names,gene_oln,gene_orf,length,protein_existence,keyword,cc_subcellular_location,ft_transmem,ft_topo_dom,ft_intramem,ft_signal,ft_lipid,xref_interpro,sequence"

PAPERS = {
    "himmelreich1996": "8948633", "dandekar2000": "10954595", "kuhner2009": "19965468", "yus2009": "19965476",
    "maier2011": "21772259", "wodke2013": "23549481", "lluchsenar2015": "25609650", "hasselbring2006": "17062751",
    "chen2016": "26773059", "parrott2016": "27148202", "nakane2015": "26633540", "nakane2021": "34111235",
    "visual2026": "42790420",
}
# The open articles that are read in full, with the licence PubMed Central records for each.
OPEN_TEXTS = {
    "parrott2016": ("PMC4828434", "CC BY"), "nakane2015": ("PMC4669176", "CC BY"), "nakane2021": ("PMC8191905", "CC BY"),
    "maier2011": ("PMC3159969", "CC BY-NC-SA"), "wodke2013": ("PMC3658275", "CC BY-NC-SA"), "chen2016": ("PMC4756857", "CC BY-NC"),
    "lluchsenar2015": ("PMC4332154", "CC BY"),
}
LICENCES = {
    "parrott2016": "CC BY 4.0", "nakane2015": "CC BY 4.0", "nakane2021": "CC BY 4.0", "lluchsenar2015": "CC BY 4.0",
    "maier2011": "CC BY-NC-SA 3.0, read for numbers and short quotations; its tables are not copied",
    "wodke2013": "CC BY-NC-SA 3.0, read for numbers and short quotations; its tables are not copied",
}


# ---------------------------------------------------------------------------------------
# What is looked for: the family behind each unit, by its InterPro signature
# ---------------------------------------------------------------------------------------
#
# The same signatures as the planarian and Syn3A atlases ask, so that every species is
# asked the same question. "of" is the family as a sentence names it.

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
AQUAPORIN_FAMILY = "IPR000425"  # the one of them that finds a protein here: the glycerol facilitator
PROTEASOME = "IPR001353"        # the 20S proteasome's subunits; asked for the molecular-machines note

NOTHING_TO_LOOK_FOR = "nothing to look for"
NO_CHANNEL = "No ion channel of any family searched was found in this organism: its ions cross the membrane through transporters and pumps."
KV_TAIL = "By its annotation it takes up potassium with a transporter instead (the two proteins listed under extra as KtrB and KtrA). " + NO_CHANNEL
NAV = ["nav_alpha", "nav_beta"]
KV1 = ["kv1", "kv_beta"]
CAV_AUX = ["cav_beta", "cav_a2d"]
GAP = ["connexin", "innexin"]
GAP_TAIL = "Gap junctions join the neighbouring cells of a tissue, and this organism lives as single cells."
NO_ER = "It is a bacterium with a single membrane and no internal compartments, so it has no endoplasmic reticulum for this machine to sit in."
P_TYPE = "The wider family, the P-type ATPases, has one member here, annotated only as a cation-transporting ATPase (locus MPN_209, listed under extra)."

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
    "U39": {"parts": ["nka_alpha", "nka_beta", "fxyd"], "tail": P_TYPE + " It does not carry the mark of the sodium-potassium pump."},
    "U40": {"parts": ["pmca"], "tail": P_TYPE + " Which cation it carries is not established in any source read here, and it does not carry this signature."},
    "U41": {"parts": ["serca"], "tail": NO_ER},
    "U42": {"parts": ["ncx"], "tail": "Nothing in its annotation is named a sodium-calcium exchanger."},
    "U43": {"parts": ["ip3r", "ryr"], "tail": NO_ER},
    "U44": {"parts": ["kcc", "slc12"], "tail": "Its annotation names no chloride-coupled cotransporter."},
    "U45": {"parts": ["nkcc", "slc12"], "tail": "Its annotation names no chloride-coupled cotransporter."},
    "U46": {"finding": NOTHING_TO_LOOK_FOR, "note": "A slot that each model configuration fills with a transporter of its own; it has no fixed protein in any species. This organism's own transporters are in its protein catalogue."},
    "U47": {"parts": ["mcu", "emre", "micu"], "tail": "It is a bacterium and has no mitochondria."},
    "U48": {"finding": NOTHING_TO_LOOK_FOR, "note": "A protein cage designed in the laboratory, with no gene in any organism, so there is nothing to look for in this one."},
    "U49": {"finding": NOTHING_TO_LOOK_FOR, "note": "A lumped water permeability of the membrane; water channels (aquaporins) are not part of it. One protein of this organism carries the aquaporin family's signature: the glycerol facilitator GlpF (locus MPN_043), listed under extra."},
}

# The organism's own membrane machines that bear on what the atlas draws and match no unit.
# Each has a reviewed UniProtKB entry of this strain; "signature" must be on the protein's
# sequence in UniProt's archive.
EXTRA = [
    {"locus": "MPN_600", "name": "ATP synthase, F1 alpha subunit", "role": "catalytic head", "signature": "IPR000194",
     "why": "Part of the cell's F-type ATP synthase, which sits in its one membrane; four of its subunits are listed here. A 2013 model of the cell's metabolism has this machine run backwards, spending ATP to pump protons out; that is the model's estimate, not a measurement. The law inventory has no F-type ATPase."},
    {"locus": "MPN_598", "name": "ATP synthase, F1 beta subunit", "role": "catalytic head", "signature": "IPR000194",
     "why": "The other subunit of the ATP synthase's catalytic head."},
    {"locus": "MPN_603", "name": "ATP synthase, F0 c subunit", "role": "proton-carrying ring", "signature": "IPR000454",
     "why": "The ring of the ATP synthase that carries protons across the membrane."},
    {"locus": "MPN_604", "name": "ATP synthase, F0 a subunit", "role": "proton path", "signature": "IPR000568",
     "why": "The membrane subunit of the ATP synthase beside the ring, where protons enter and leave."},
    {"locus": "MPN_209", "name": "P-type ATPase", "role": "ion pump", "signature": "IPR001757",
     "why": "A pump of the same superfamily as the sodium-potassium and calcium pumps of animal cells. Its sequence carries the superfamily's signature and none of the signatures of those pumps' branches, so which ion it moves is not known here. It is the only P-type ATPase in the genome."},
    {"locus": "MPN_460", "name": "Potassium uptake protein KtrB-like", "role": "membrane part of a potassium uptake system", "signature": "IPR003445",
     "why": "The membrane part of what the genome record calls the cell's potassium uptake system, KtrAB. That is how a cell without a sodium-potassium pump or a potassium channel would take up potassium; UniProt's curators leave the protein uncharacterised."},
    {"locus": "MPN_461", "name": "Potassium uptake protein KtrA-like", "role": "regulatory part of a potassium uptake system", "signature": "IPR006037",
     "why": "The cytoplasmic partner that the genome record gives the potassium uptake system."},
    {"locus": "MPN_207", "name": "Glucose transporter PtsG", "role": "sugar uptake", "signature": "IPR003352",
     "why": "The membrane part of the system that brings in glucose, the cell's main fuel. Its ATP comes from fermenting that sugar."},
    {"locus": "MPN_043", "name": "Glycerol facilitator GlpF", "role": "channel for glycerol", "signature": AQUAPORIN_FAMILY,
     "why": "The one channel-like protein found here: a member of the family of water and glycerol channels, annotated as the cell's glycerol uptake facilitator. It is not an ion channel, and the law inventory has no unit for it; its water permeability unit is a lumped property with no protein."},
]

# The classes the 2015 paper gives each gene, in the words of its supplementary text.
CLASSES = {
    "A": "Membrane proteins of unknown function", "C": "Energy production and conversion, coenzyme metabolism",
    "D": "Cell division and chromosome partitioning", "E": "Amino acid transport and metabolism",
    "F": "Nucleotide transport and metabolism", "G": "Carbohydrate transport and metabolism", "H": "Coenzyme metabolism",
    "I": "Lipid metabolism", "J": "Translation, ribosomal structure and biogenesis", "K": "Transcription",
    "L": "DNA replication, recombination and repair", "M": "Cell envelope biogenesis, outer membrane",
    "N": "Cell motility and secretion", "O": "Post-translational modification, protein turnover, chaperones",
    "P": "Inorganic ion transport and metabolism", "R": "General function prediction only", "S": "Function unknown",
    "T": "Signal transduction mechanisms", "U": "Intracellular trafficking, secretion and vesicular transport",
    "V": "Defense mechanisms",
}
NO_CLASS = "none"
ESSENTIALITY = {"E": "essential", "F": "fitness", "NE": "non-essential", "NE*": "non-essential (repeats)"}

# Keywords of a curated entry that leave no real doubt that the protein works inside the
# cell: on the ribosome, on transfer or ribosomal RNA, in transcription or on the chromosome.
INSIDE_BY_FUNCTION = ["Ribosomal protein", "Aminoacyl-tRNA synthetase", "Protein biosynthesis", "DNA-directed RNA polymerase", "Transcription", "DNA replication", "DNA repair", "DNA recombination", "tRNA processing", "rRNA processing", "Ribosome biogenesis"]
# A protein placed at the membrane with no face stated, whose work needs what is inside.
INNER_FACE_BY_FUNCTION = ["ATP-binding", "GTP-binding", "ATP synthesis", "DNA-binding"]
EXPERIMENT, CURATOR, SIMILARITY, RULE = "experiment", "curator", "similarity", "rule"


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


def requests(snapshot):
    """Every request of the fetch step: (file name, URL, what it is for)."""
    out = []

    def add(name, url, purpose):
        out.append({"name": name, "url": url, "purpose": purpose})

    # The frozen annotation, and the same sequence as NCBI's pipeline annotates it.
    add(f"genbank_{RECORD}_summary.json", f"{EUTILS}/esummary.fcgi?db=nuccore&id={RECORD}&retmode=json&tool=atlas-builder", "the genome record: its title, length, organism and dates")
    add(f"genbank_{RECORD}_head.gb", f"{EUTILS}/efetch.fcgi?db=nuccore&id={RECORD}&rettype=gb&retmode=text&seq_start=1&seq_stop=60&tool=atlas-builder", "the head of the genome record: who submitted it and the papers it rests on")
    add(f"genbank_{RECORD}_features.ft", efetch(RECORD, "ft"), "every feature of the genome record: genes, coding sequences and RNA genes")
    add(f"genbank_{RECORD}_cds_aa.fa", efetch(RECORD, "fasta_cds_aa"), "the protein product of each coding sequence, with its locus tag, gene, product and protein identifier")
    add(f"refseq_{REFSEQ}_features.ft", efetch(REFSEQ, "ft"), "the same genome as NCBI's own pipeline annotates it, read only to count its coding sequences")

    # UniProt: its curated entries of the strain, the archive's sequences with the family
    # signatures on them, and the signatures of the units' human candidates.
    add(f"uniprot_taxonomy_{TAXON}.json", f"{UNIPROT}/taxonomy/{TAXON}", "how many UniProtKB entries the strain has, and what UniProt calls it")
    add(f"uniprot_taxonomy_{MOLLICUTES}.json", f"{UNIPROT}/taxonomy/{MOLLICUTES}", "the class of bacteria the controls are asked of")
    add(f"uniprotkb_{TAXON}.json", f"{UNIPROT}/uniprotkb/stream?query={q(f'(taxonomy_id:{TAXON})')}&format=json&fields={ENTRY_FIELDS}", "every UniProtKB entry of the strain: names, level of evidence, keywords, stated location, membrane-spanning segments, signals and lipid anchors")
    add(f"uniparc_{TAXON}.json", f"{UNIPROT}/uniparc/stream?query={q(f'(taxonomy_id:{TAXON})')}&format=json", "every archived protein sequence of the strain, with the family signatures on it")
    add(f"uniparc_{TAXON}_count.json", f"{UNIPROT}/uniparc/search?query={q(f'(taxonomy_id:{TAXON})')}&format=json&size=1", "how many archived sequences the strain has, to check that the answer above is whole")
    add("uniprotkb_human_candidates.json", f"{UNIPROT}/uniprotkb/accessions?accessions={','.join(human_accessions(snapshot))}&format=json&fields={HUMAN_FIELDS}", "the family signatures carried by the units' human candidates")
    for signature in sorted({*rule_signatures(), *BACTERIAL_CHANNELS, PROTEASOME}):
        add(f"control_uniprotkb_{signature}_{MOLLICUTES}.json", f"{UNIPROT}/uniprotkb/search?query={q(f'(xref:interpro-{signature}) AND (taxonomy_id:{MOLLICUTES})')}&size=1&fields=accession&format=json", f"how many UniProtKB entries of mollicutes carry {signature}")
    for page in ("transmem", "signal", "lipid"):
        add(f"uniprot_help_{page}.json", f"{UNIPROT}/help/{page}", "UniProt's own account of how it annotates this feature, and with which predictors")
    add("terms_uniprot_license.json", f"{UNIPROT}/help/license", "UniProt's licence")

    # The 2015 paper (CC BY 4.0): its text, the licence PubMed Central records, its table of
    # every gene's class and essentiality, and the supplementary text that explains the table.
    paper = f"{OPEN}/PMC4332154.1"
    add("lluchsenar2015_article.xml", f"{paper}/PMC4332154.1.xml", "Lluch-Senar and others 2015, the open text")
    add("lluchsenar2015_article.json", f"{paper}/PMC4332154.1.json", "Lluch-Senar and others 2015, the licence PubMed Central records")
    add("lluchsenar2015_table_s2.xlsx", f"{paper}/msb0011-0780-sd11.xlsx", "Lluch-Senar and others 2015, Supplementary Table S2: each gene's class and essentiality")
    add("lluchsenar2015_supplementary_information.docx", f"{paper}/msb0011-0780-sd21.docx", "Lluch-Senar and others 2015, the supplementary text that explains the table's columns and classes")

    # The other open texts that the facts are read from, each with its recorded licence.
    for key, (pmc, _) in sorted(OPEN_TEXTS.items()):
        if key != "lluchsenar2015":
            add(f"pmc_{pmc}.xml", f"{OPEN}/{pmc}.1/{pmc}.1.xml", f"the open text of the paper cited as {key}")
            add(f"pmc_{pmc}.json", f"{OPEN}/{pmc}.1/{pmc}.1.json", f"the licence PubMed Central records for the paper cited as {key}")
    add("pubmed_abstracts.xml", f"{EUTILS}/efetch.fcgi?db=pubmed&id={','.join(sorted(PAPERS.values(), key=int))}&retmode=xml&tool=atlas-builder", "the records of the papers cited, with their abstracts")
    add("emdb_EMD-53631.json", "https://www.ebi.ac.uk/emdb/api/entry/EMD-53631", "the EMDB entry that the user's note names, to check what it is")

    # Terms of each source, read before anything was copied.
    add("terms_ncbi_genbank.html", "https://www.ncbi.nlm.nih.gov/genbank/", "GenBank's statement on the use of its data")
    add("terms_insdc_policy.html", "https://www.insdc.org/policy/", "the policy of the nucleotide sequence databases")
    add("terms_interpro_license.html", "https://interpro-documentation.readthedocs.io/en/latest/license.html", "InterPro's licence")
    return out


# Where the downloads live. Each source has a folder of its own under the datasets folder,
# with a MANIFEST.json. This tool makes every folder it reads, and their note says so;
# a folder that another agent made is never written.

MINE = "the visualizer's M. pneumoniae agent"
OWN = {
    "ncbi-U00089.2": {"accession": "U00089.2", "licence": "INSDC public data; NCBI places no restrictions on the use or distribution of GenBank data", "what": "Mycoplasma pneumoniae M129 genome record: its summary, its head, its feature table and the protein product of each coding sequence"},
    "ncbi-NC_000912.1": {"accession": "NC_000912.1", "licence": "NCBI RefSeq; no restrictions on use or distribution", "what": "The same genome as NCBI's annotation pipeline annotates it: the feature table, read only to count its coding sequences"},
    "uniprot-mpneumoniae": {"licence": "CC BY 4.0", "what": "UniProt: the curated entries of taxon 272634, the archived protein sequences of the taxon with the family signatures on them, the signatures of the law inventory's human candidates, control counts in mollicutes, three help pages on how features are annotated, and UniProt's licence"},
    "lluchsenar2015-msb": {"doi": "10.15252/msb.20145558", "pmcid": "PMC4332154", "licence": "CC BY 4.0", "what": "Lluch-Senar and others 2015, from PubMed Central's open-data store: the article, its recorded licence, Supplementary Table S2 and the supplementary text"},
    "pmc-open-mpneumoniae-papers": {"licence": "Each article's own: CC BY for Parrott 2016, Nakane 2015 and Nakane 2021; CC BY-NC-SA for Maier 2011 and Wodke 2013; CC BY-NC for Chen 2016. The JSON beside each article records it", "what": "Open articles on Mycoplasma pneumoniae from PubMed Central's open-data store (JATS XML), read for numbers and short quotations"},
    "pubmed-mpneumoniae-papers": {"licence": "Bibliographic records and abstracts, cited as facts", "what": "PubMed records of the papers cited, with their abstracts"},
    "emdb-EMD-53631": {"accession": "EMD-53631", "licence": "CC0 1.0 (EMDB metadata)", "what": "The EMDB entry's record, read for its title and release date"},
    "terms-mpneumoniae-sources": {"what": "Terms of use as read before anything was copied: GenBank's data usage statement, the policy of the nucleotide sequence databases and InterPro's licence"},
}
PLACES = [
    ("genbank_", "ncbi-U00089.2"), ("refseq_", "ncbi-NC_000912.1"),
    ("terms_uniprot", "uniprot-mpneumoniae"), ("uniprot", "uniprot-mpneumoniae"), ("uniparc", "uniprot-mpneumoniae"), ("control_uniprotkb", "uniprot-mpneumoniae"),
    ("lluchsenar2015_", "lluchsenar2015-msb"), ("pmc_", "pmc-open-mpneumoniae-papers"), ("pubmed_", "pubmed-mpneumoniae-papers"),
    ("emdb_", "emdb-EMD-53631"), ("terms_", "terms-mpneumoniae-sources"),
]
HEADERS = [("X-Total-Results", "total_results"), ("X-UniProt-Release", "uniprot_release"), ("X-UniProt-Release-Date", "uniprot_release_date")]


def place(name):
    """The dataset folder of a request, and the name its file has there."""
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
    manifest = read_manifest(folder) or {"source_id": source, "record": OWN[source], "files": []}
    if manifest["files"] and not is_ours(manifest):
        raise SystemExit(f"{folder} was not made by this tool; nothing is written there")
    manifest["files"] = sorted([item for item in manifest["files"] if item["name"] != entry["name"]] + [entry], key=lambda item: item["name"])
    manifest["manifest_written_utc"] = now()
    manifest["note"] = f"Added by {MINE}: downloaded as untrusted data by tools/build_mpneumoniae_atlas.py of the Cells checkout (analysis in {evidence}). Nothing here was executed."
    (Path(folder) / "MANIFEST.json").write_text(json.dumps(manifest, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")


def load_log(evidence):
    path = Path(evidence) / "requests.json"
    if not path.exists():
        return {"client": CLIENT, "note": "Every request this tool made for the M. pneumoniae data: what was asked, when, what came back and where it was saved.", "requests": []}
    return json.loads(path.read_text(encoding="utf-8"))


def fetch(evidence, datasets, snapshot, refresh=False, pause=0.6, tries=5):
    """Ask every request whose file is not yet in its dataset folder; save the body as it
    came, with its entry in that folder's MANIFEST and a line in the request log."""
    evidence, datasets = Path(evidence), Path(datasets)
    evidence.mkdir(parents=True, exist_ok=True)
    log = load_log(evidence)
    done = {item["name"]: item for item in log["requests"]}
    asked = failed = 0
    for request in requests(snapshot):
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
            # has just added the same source, theirs is left alone and nothing is written.
            try:
                folder.mkdir(parents=True)
            except FileExistsError:
                pass
            if (folder / "MANIFEST.json").exists() and not is_ours(read_manifest(folder)):
                print(f"skipped  {source}/{file}: the folder was just made by another agent", flush=True)
                failed += 1
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

    def page(self, name):
        """The running text of one of UniProt's help pages."""
        return re.sub(r"\s+", " ", re.sub(r"<[^>]+>|[#*\[\]]", " ", self.json(name).get("content", "")))

    def document(self, name):
        """The running text of a word-processor file."""
        with zipfile.ZipFile(self.path(name)) as book:
            text = book.read("word/document.xml").decode("utf-8", "replace")
        return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", re.sub(r"</w:p>", "\n", text)))

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


def feature_kinds(text):
    """How many features of each kind a feature table lists."""
    return Counter(re.findall(r"^[<>]?\d+\t[<>]?\d+\t(\S+)", text, re.M))


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


def entry_name(entry):
    description = entry["proteinDescription"]
    named = description.get("recommendedName") or (description.get("submissionNames") or [{}])[0]
    return named.get("fullName", {}).get("value", "")


def entry_gene(entry):
    return next((gene["geneName"]["value"] for gene in entry.get("genes", []) if gene.get("geneName")), "")


def entry_loci(entry):
    return [locus for gene in entry.get("genes", []) for name in gene.get("orderedLocusNames", []) for locus in name["value"].split("/")]


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
        self.record_strain = summary["strain"]
        self.record_organism = summary["organism"]
        self.kinds = feature_kinds(ev.text(f"genbank_{RECORD}_features.ft"))
        coding = coding_sequences(ev.text(f"genbank_{RECORD}_cds_aa.fa"))
        self.proteins = sorted((item for item in coding if item.get("protein_id")), key=lambda item: natural(item["locus_tag"]))
        if len({item["locus_tag"] for item in self.proteins}) != len(self.proteins) or len(self.proteins) != len(coding):
            raise SystemExit("the coding sequences of the genome record are not one protein per locus tag")
        self.by_locus = {item["locus_tag"]: item for item in self.proteins}
        self.refseq_kinds = feature_kinds(ev.text(f"refseq_{REFSEQ}_features.ft"))

        # UniProt's archive: the same sequences, with the family signatures on them.
        archive = ev.json(f"uniparc_{TAXON}.json")["results"]
        if len(archive) != ev.total(f"uniparc_{TAXON}_count.json"):
            raise SystemExit("the archive's answer is not complete")
        self.archived = len(archive)
        self.uniprot_release = ev.record(f"uniparc_{TAXON}.json")["uniprot_release"]
        if ev.record(f"uniprotkb_{TAXON}.json")["uniprot_release"] != self.uniprot_release:
            raise SystemExit("the archive and the curated entries were not read from one release of UniProt")
        by_sequence = {record["sequence"]["value"]: record for record in archive}
        missing = [item["locus_tag"] for item in self.proteins if item["sequence"] not in by_sequence]
        if missing:
            raise SystemExit(f"the archive does not hold the sequence of {missing[:5]}")
        for item in self.proteins:
            record = by_sequence[item["sequence"]]
            item["uniparc"] = record["uniParcId"]
            item["interpro"] = sorted({feature["interproGroup"]["id"] for feature in record.get("sequenceFeatures", []) if feature.get("interproGroup")})
        self.signature_names = {feature["interproGroup"]["id"]: feature["interproGroup"]["name"] for record in archive for feature in record.get("sequenceFeatures", []) if feature.get("interproGroup")}

        # UniProt's curated entries of the strain, tied to the record by locus tag.
        taxon = ev.json(f"uniprot_taxonomy_{TAXON}.json")
        self.uniprot_name = taxon["scientificName"]
        self.kb_counts = taxon.get("statistics", {})
        entries = ev.json(f"uniprotkb_{TAXON}.json")["results"]
        if len(entries) != self.kb_counts.get("reviewedProteinCount", 0) + self.kb_counts.get("unreviewedProteinCount", 0):
            raise SystemExit("the answer with the strain's UniProtKB entries is not complete")
        self.entries = entries
        self.entry_of = {}
        for entry in entries:
            loci = entry_loci(entry)
            if not loci or any(locus not in self.by_locus or locus in self.entry_of for locus in loci):
                raise SystemExit(f"UniProtKB entry {entry['primaryAccession']} cannot be tied to one locus of the genome record: {loci}")
            for locus in loci:
                self.entry_of[locus] = entry
        if ev.json(f"uniprot_taxonomy_{MOLLICUTES}.json")["scientificName"] != "Mollicutes":
            raise SystemExit("the taxon of the controls is not the mollicutes")

        # The units' human candidates: the signatures they carry.
        self.human = {entry["primaryAccession"]: {x["id"] for x in entry.get("uniProtKBCrossReferences", []) if x["database"] == "InterPro"} for entry in ev.json("uniprotkb_human_candidates.json")["results"]}

        # The 2015 paper's table: each gene's class and essentiality.
        rows = sheet(ev.path("lluchsenar2015_table_s2.xlsx"), "Table S2")
        head = rows[3]
        expected = {0: "ORF", 3: "Protein name", 5: "COG category", 17: "Essentiality Thr7", 18: "Essentiality Thr41"}
        if any(head[index] != name for index, name in expected.items()):
            raise SystemExit("the 2015 paper's table is not laid out as it was read")
        self.table = {}
        for row in rows[4:]:
            row = row + [""] * (19 - len(row))
            if re.fullmatch(r"MPN\d{3}[a-z]?&?", row[0]):
                self.table[row[0]] = {"class": row[5], "relaxed": row[17], "stringent": row[18]}
        self.numbered = {f"MPN_{key[3:]}": value for key, value in self.table.items() if re.fullmatch(r"MPN\d{3}", key)}
        if set(self.numbered) != set(self.by_locus):
            raise SystemExit("the 2015 paper's table and the genome record do not list the same numbered genes")

        # The papers' records.
        self.papers = {}
        for article in ElementTree.fromstring(ev.text("pubmed_abstracts.xml")).iter("PubmedArticle"):
            pmid = article.findtext(".//PMID")
            journal = article.find(".//Journal")
            self.papers[pmid] = {
                "pmid": pmid,
                "title": "".join(article.find(".//ArticleTitle").itertext()).strip(),
                "abstract": " ".join("".join(node.itertext()) for node in article.iter("AbstractText")),
                "authors": [author.findtext("LastName") for author in article.iter("Author") if author.findtext("LastName")],
                "journal": journal.findtext("ISOAbbreviation"),
                "year": journal.findtext(".//PubDate/Year") or (journal.findtext(".//PubDate/MedlineDate") or "")[:4],
                "volume": journal.findtext(".//Volume"),
                "pages": article.findtext(".//MedlinePgn"),
                "doi": next((node.text for node in article.iter("ArticleId") if node.get("IdType") == "doi"), None),
            }

    def carriers(self, signature):
        return [item for item in self.proteins if signature in item["interpro"]]

    def mollicutes(self, signature):
        return self.evidence.total(f"control_uniprotkb_{signature}_{MOLLICUTES}.json")


# ---------------------------------------------------------------------------------------
# Checks: the saved sources must still say what the files state
# ---------------------------------------------------------------------------------------

def text_of(key):
    return "lluchsenar2015_article.xml" if key == "lluchsenar2015" else f"pmc_{OPEN_TEXTS[key][0]}.xml"


SAID = [
    ("parrott2016", "just 1–2 μm long and 0.1–0.2 μm wide"),
    ("parrott2016", "unable to synthesize rigid peptidoglycan cell walls"),
    ("parrott2016", "sterols provide the structural support in the triple-layer cell membrane"),
    ("parrott2016", "reproduces via binary fission"),
    ("parrott2016", "Preceding binary cell fission, the attachment organelle"),
    ("parrott2016", "Creative Commons Attribution License"),
    ("nakane2015", "This tiny bacterium, about 2 μm long"),
    ("nakane2015", "at a maximum speed of 1 μm, one-half its cell length, per second"),
    ("nakane2015", "lack a peptidoglycan layer"),
    ("nakane2015", "Creative Commons Attribution License"),
    ("nakane2021", "a membrane protrusion with a precise length of 250–300 nm"),
    ("nakane2021", "Creative Commons Attribution License"),
    ("maier2011", "the 140 ribosomes per cell previously determined for M. pneumoniae by electron tomography"),
    ("maier2011", "150 ribosomes per cell"),
    ("maier2011", "(0.22 and 0.05 μm 3 , respectively)"),
    ("maier2011", "with an average abundance of 167 copies per cell"),
    ("maier2011", "from about 2300 copies (Ef-Tu) to two copies"),
    ("maier2011", "Creative Commons Attribution Noncommercial Share Alike 3.0 Unported License"),
    ("wodke2013", "relies on simple organic acid fermentation, due to the absence of TCA cycle and a functional respiratory chain"),
    ("wodke2013", "a single, small chromosome of only 816 394 base pairs, encoding 689 proteins"),
    ("wodke2013", "it metabolizes glucose as major carbon and energy source"),
    ("wodke2013", "lactate and acetate secretion"),
    ("wodke2013", "the ATPase uses about 57–80% (growth stage depending) of the total generated energy"),
    ("wodke2013", "Creative Commons Attribution Noncommercial Share Alike 3.0 Unported License"),
    ("chen2016", "comprising 1748 consistently generated"),
    ("chen2016", "creativecommons.org/licenses/by-nc/4.0"),
    ("lluchsenar2015", "The current annotation of the M. pneumoniae genome contains 694 ORFs (32 of which are smORFs)"),
    ("lluchsenar2015", "essential (E; 342 ORFs), non-essential (NE; 259 ORFs) and fitness (F; 93 ORFs)"),
    ("lluchsenar2015", "mapped to the M. pneumoniae reference genome ( NC_000912 , NCBI)"),
    ("lluchsenar2015", "Creative Commons Attribution 4.0 License"),
]
ABSTRACTS = [
    ("himmelreich1996", "It has a size of 816,394 base pairs"),
    ("himmelreich1996", "We predict 677 open reading frames (ORFs)"),
    ("himmelreich1996", "no amino acid synthesis"),
    ("dandekar2000", "has been increased from 677 to 688"),
    ("kuhner2009", "62 homomultimeric and 116 heteromultimeric soluble protein complexes"),
    ("kuhner2009", "is among the smallest found in self-replicating organisms"),
    ("yus2009", "a defined, minimal medium with 19 essential nutrients"),
    ("hasselbring2006", "Mycoplasmas are cell wall-less bacteria considered among the smallest and simplest prokaryotes known"),
    ("hasselbring2006", "a membrane-bound cell extension distinguished by an electron-dense core"),
    ("hasselbring2006", "which is also the leading end in gliding motility"),
    ("hasselbring2006", "Duplication of the terminal organelle is thought to precede cell division"),
    ("hasselbring2006", "indicating a requirement for gliding in normal cell division"),
    ("visual2026", "to resolve 140 maps"),
]
SUPPLEMENT = [
    "NE*, non-essential containing repetitive regions",
    "We estimated the minimal genome by considering the analysis of Thr41 since it is the most restrictive",
    "Column 6 indicates the COG category of the ORF",
    "A, Membrane Proteins of unknown function", "C, Energy production and conversion, Coenzyme metabolism",
    "D, Cell division and chromosome partitioning", "E, Amino acid transport and metabolism", "F, Nucleotide transport and metabolism",
    "G, Carbohydrate transport and metabolism", "H, Coenzyme metabolism", "I, Lipid metabolism", "J Translation, ribosomal structure and biogenesis",
    "K, Transcription", "L, DNA replication, recombination and repair", "M, Cell envelope biogenesis, outer membrane", "N, Cell motility and secretion",
    "O, Post-translational modification, protein turnover, chaperones", "P, Inorganic ion transport and metabolism", "R, General function prediction only",
    "S, Function unknown", "T, Signal transduction mechanisms", "U, Intracellular trafficking, secretion and vesicular transport", "V, Defense mechanisms",
]
TERMS = [
    ("terms_ncbi_genbank.html", r"NCBI places no restrictions on the use or distribution of the GenBank data"),
    ("terms_insdc_policy.html", r"no use restrictions or licensing requirements will be included in any sequence data records"),
    ("terms_uniprot_license.json", r"Creative Commons Attribution 4\.0 International \(CC BY 4\.0\) License"),
    ("terms_interpro_license.html", r"CC0"),
    ("uniprot_help_transmem.json", r"TMHMM, Memsat, Phobius and the hydrophobic moment plot method of Eisenberg"),
    ("uniprot_help_transmem.json", r"at least two methods must return a positive prediction"),
    ("uniprot_help_signal.json", r"Phobius, Predotar, SignalP and TargetP"),
    ("uniprot_help_lipid.json", r"Most bacterial lipoproteins are anchored to the outer plasma membrane by diacylglycerol"),
]
COUNTS = {"gene": 732, "CDS": 688, "tRNA": 37, "rRNA": 4, "misc_RNA": 3, "repeat_region": 40}


def check_sources(c):
    ev = c.evidence
    for key, words in SAID:
        if words not in ev.plain(text_of(key)):
            raise SystemExit(f"the paper cited as {key} no longer says: {words}")
    for key, (pmc, licence) in OPEN_TEXTS.items():
        recorded = ev.json("lluchsenar2015_article.json" if key == "lluchsenar2015" else f"pmc_{pmc}.json")
        if recorded["license_code"] != licence or str(recorded["pmid"]) != PAPERS[key]:
            raise SystemExit(f"PubMed Central no longer records {pmc} as {licence}, or as the paper cited as {key}")
    if set(PAPERS.values()) - set(c.papers):
        raise SystemExit("a cited paper's record was not returned")
    for key, words in ABSTRACTS:
        if words not in c.papers[PAPERS[key]]["abstract"]:
            raise SystemExit(f"the abstract of the paper cited as {key} no longer says: {words}")
    supplement = ev.document("lluchsenar2015_supplementary_information.docx")
    for words in SUPPLEMENT:
        if words not in supplement:
            raise SystemExit(f"the 2015 paper's supplementary text no longer says: {words}")
    for name, words in TERMS:
        if not re.search(words, ev.page(name) if name.endswith(".json") else ev.plain(name)):
            raise SystemExit(f"{name} no longer says: {words}")
    if ev.json("emdb_EMD-53631.json")["admin"]["title"] != "Map of M. pneumoniae 50S mid biogenesis in native cells":
        raise SystemExit("the EMDB entry is no longer titled as the note says")
    head = ev.text(f"genbank_{RECORD}_head.gb")
    if "Complete sequence analysis of the genome of the bacterium" not in head or "Re-annotating the Mycoplasma pneumoniae genome sequence" not in head:
        raise SystemExit("the genome record no longer names the two papers it rests on")
    # The counts the files state, from the record and the 2015 paper's own table.
    if dict(c.kinds) != COUNTS or len(c.proteins) != 688 or c.length != 816394:
        raise SystemExit(f"the genome record's counts are not the ones the files state: {dict(c.kinds)}, {len(c.proteins)} protein products, {c.length} bp")
    stringent = Counter(row["stringent"] for row in c.numbered.values())
    if dict(stringent) != {"E": 342, "F": 91, "NE": 159, "NE*": 96} or set(stringent) - set(ESSENTIALITY):
        raise SystemExit(f"the 2015 table's classes of the 688 numbered genes are not the ones the files state: {dict(stringent)}")
    classes = {row["class"] for row in c.numbered.values()}
    if classes - set(CLASSES) - {"--", ""}:
        raise SystemExit(f"the 2015 table uses a class the files do not name: {sorted(classes - set(CLASSES))}")
    without = sorted(set(c.by_locus) - set(c.entry_of), key=natural)
    if without != ["MPN_441"] or len(c.entries) != 686:
        raise SystemExit(f"the loci without a UniProtKB entry are no longer MPN_441 alone, or the entries are no longer 686: {without}, {len(c.entries)}")
    if c.entry_of["MPN_304"] is not c.entry_of["MPN_305"]:
        raise SystemExit("MPN_304 and MPN_305 no longer share one UniProtKB entry")
    if any(not entry["entryType"].startswith("UniProtKB reviewed") for entry in c.entries):
        raise SystemExit("an entry of the strain is no longer a reviewed one; rewrite what the files say")
    # Each family signature is carried by a human candidate of a unit that searches it, so
    # the search can find the family where it exists.
    carried = set().union(*c.human.values())
    for key, family in FAMILIES.items():
        if family.get("human", True) and family["signatures"][0] not in carried:
            raise SystemExit(f"no human candidate carries {family['signatures'][0]} ({key})")
    # Nothing was found for any unit, and one bacterial channel family was: the notes are
    # written for that, and must be rewritten otherwise.
    found = {signature: [item["locus_tag"] for item in c.carriers(signature)] for signature in [*rule_signatures(), *BACTERIAL_CHANNELS, PROTEASOME]}
    if {signature: loci for signature, loci in found.items() if loci} != {AQUAPORIN_FAMILY: ["MPN_043"]}:
        raise SystemExit(f"the signatures no longer find what the notes say; read them and rewrite the notes: { {k: v for k, v in found.items() if v} }")
    # The sentence on channels says the search finds them in other mollicutes.
    if not all(c.mollicutes(signature) for signature in BACTERIAL_CHANNELS):
        raise SystemExit("a bacterial channel signature finds no mollicute entry; rewrite what is said of the channels")
    for locus, name in [("MPN_317", "ftsZ"), ("MPN_184", "secY"), ("MPN_671", "ftsH"), ("MPN_332", "lon")]:
        if c.by_locus[locus].get("gene") != name:
            raise SystemExit(f"{locus} is no longer annotated {name}")
    if entry_gene(c.entry_of["MPN_680"]) != "yidC":
        raise SystemExit("UniProt no longer names MPN_680 yidC")
    p_type = [item["locus_tag"] for item in c.carriers("IPR001757")]
    if p_type != ["MPN_209"]:
        raise SystemExit(f"the P-type ATPases of the genome are no longer MPN_209 alone: {p_type}")
    for item in EXTRA:
        if item["signature"] not in c.by_locus[item["locus"]]["interpro"]:
            raise SystemExit(f"{item['locus']} does not carry {item['signature']}")
        if item["locus"] not in c.entry_of:
            raise SystemExit(f"{item['locus']} has no UniProtKB entry")


# ---------------------------------------------------------------------------------------
# Where a protein sits against the cell membrane
# ---------------------------------------------------------------------------------------

GRADES = {"ECO:0000269": (3, EXPERIMENT), "ECO:0000305": (2, CURATOR), "ECO:0000303": (2, CURATOR), "ECO:0000304": (2, CURATOR), "ECO:0000250": (1, SIMILARITY)}


def grade(codes):
    """How strong the best of a statement's evidence is, and the word for it. A statement of
    a curated entry that carries no evidence tag is the curator's own."""
    if not codes:
        return 2, CURATOR
    return max((GRADES.get(code, (1, RULE)) for code in codes), key=lambda item: (item[0], item[1] == SIMILARITY))


def placement(entry):
    """The side of the cell membrane a curated entry puts its protein on, and on what basis."""
    unknown = {"side": "not known", "basis": "none", "evidence": None, "where": None, "also": None}
    if entry is None:
        return unknown
    statements, where, at_membrane, no_face = [], None, False, False
    locations = [place_ for comment in entry.get("comments", []) if comment["commentType"] == "SUBCELLULAR LOCATION" for place_ in comment.get("subcellularLocations", [])]
    for index, stated in enumerate(locations):
        value = stated["location"]["value"]
        if value.startswith("Host"):
            continue  # where the protein goes in the host's cell, not in this one
        topology = (stated.get("topology") or {}).get("value", "")
        orientation = (stated.get("orientation") or {}).get("value", "")
        rank, word = grade({item["evidenceCode"] for part in ("location", "topology", "orientation") if stated.get(part) for item in stated[part].get("evidences", [])})
        if value.startswith("Cell projection, attachment organelle"):
            where = "attachment organelle"
        side = None
        if topology in ("Single-pass membrane protein", "Multi-pass membrane protein"):
            side = "in"
        elif topology.startswith("Lipid-anchor"):
            side = "outside"
        elif topology == "Peripheral membrane protein":
            side = {"Cytoplasmic side": "inside", "Extracellular side": "outside"}.get(orientation)
            no_face = no_face or side is None
        elif value in ("Cell surface", "Secreted"):
            side = "outside"
        elif value.startswith("Cytoplasm"):
            side = "inside"
        elif value in ("Cell membrane", "Membrane") or value.endswith("membrane"):
            at_membrane = True
        if side:
            statements.append((side, rank, word, index))
    features = {}
    for feature in entry.get("features", []):
        features.setdefault(feature["type"], set()).update(item["evidenceCode"] for item in feature.get("evidences", []))
    # What the sequence features add where no statement of location says it.
    if "Transmembrane" in features and not any(side == "in" for side, *_ in statements):
        statements.append(("in", *grade(features["Transmembrane"]), len(locations)))
    if "Lipidation" in features and not any(side == "outside" for side, *_ in statements):
        statements.append(("outside", *grade(features["Lipidation"]), len(locations) + 1))
    if "Signal" in features and not statements:
        statements.append(("outside", *grade(features["Signal"]), len(locations) + 2))

    spanning = [item for item in statements if item[0] == "in"]
    if spanning:
        _, rank, word, _ = max(spanning, key=lambda item: item[1])
        return {"side": "in", "basis": "stated" if rank >= 2 else "predicted", "evidence": word, "where": where, "also": None}
    if statements:
        side, rank, word, _ = min(statements, key=lambda item: (-item[1], item[3]))
        others = sorted({other for other, *_ in statements} - {side})
        return {"side": side, "basis": "stated" if rank >= 2 else "predicted", "evidence": word, "where": where, "also": others[0] if others else None}
    keywords = {keyword["name"] for keyword in entry.get("keywords", [])}
    if no_face and keywords & set(INNER_FACE_BY_FUNCTION):
        return {"side": "inside", "basis": "by function", "evidence": None, "where": where or "at the membrane", "also": None}
    if no_face or at_membrane:
        return dict(unknown, where=where or "at the membrane")
    if not locations and keywords & set(INSIDE_BY_FUNCTION):
        return {"side": "inside", "basis": "by function", "evidence": None, "where": where, "also": None}
    return dict(unknown, where=where)


# ---------------------------------------------------------------------------------------
# Building
# ---------------------------------------------------------------------------------------

def citation(c, key):
    record = c.papers[PAPERS[key]]
    tail = f" {record['volume']}:{record['pages']}." if record["volume"] and record["pages"] else (f" {record['volume']}." if record["volume"] else ".")
    return {"text": f"{record['authors'][0]} and others ({record['year']}) {record['title'].rstrip('.')}. {record['journal']}{tail}", "doi": record["doi"], "pmid": record["pmid"]}


def sources_of_species(c):
    ev = c.evidence
    out = {}
    for key in ("parrott2016", "nakane2015", "nakane2021", "lluchsenar2015", "maier2011", "wodke2013"):
        cite = citation(c, key)
        out[key] = {"text": cite["text"], "doi": cite["doi"], "licence": LICENCES[key], "accessed": ev.day(text_of(key))}
    for key in ("hasselbring2006", "himmelreich1996", "dandekar2000", "kuhner2009", "yus2009"):
        cite = citation(c, key)
        out[key] = {"text": cite["text"] + " Abstract only.", "doi": cite["doi"], "accessed": ev.day("pubmed_abstracts.xml")}
    out["genbank"] = {
        "text": f"Himmelreich R, Hilbert H, Li B-C; Suyama M, Dandekar T, Herrmann R (1996, 2000) {c.record_title}. GenBank {RECORD}.",
        "url": f"https://www.ncbi.nlm.nih.gov/nuccore/{RECORD}",
        "licence": "NCBI places no restrictions on the use or distribution of GenBank data; submitters may claim rights in what they submitted, and this record states none",
        "accessed": ev.day(f"genbank_{RECORD}_features.ft"),
    }
    out["uniprot"] = {
        "text": f"UniProt Consortium, UniProt release {c.uniprot_release}: the curated entries of taxon {TAXON}, and the archived sequences of the taxon with the family signatures on them.",
        "url": f"https://www.uniprot.org/uniprotkb?query=taxonomy_id:{TAXON}",
        "licence": "CC BY 4.0",
        "accessed": ev.day(f"uniprotkb_{TAXON}.json"),
    }
    return out


def build_species(c):
    count = len(c.proteins)
    capabilities = {
        "cap.membrane": {"place": "present", "note": "Its one membrane holds the cell's ion and proton gradients. A 2013 model of its metabolism has the ATP synthase spend more than half of the cell's energy keeping the proton gradient up; that is the model's estimate, and no source read for this file measured the voltage."},
        "cap.channels": {"place": "absent", "why": f"No ion channel was found among its {count} proteins: none carries the signature of a channel family in Cells' catalogue, or of the bacterial channels for potassium, chloride, magnesium or membrane stretch, which the same search does find in other mollicutes. One protein, the glycerol facilitator GlpF, carries the signature of the family of water and glycerol channels; it is not an ion channel."},
        "cap.pumps": {"place": "present", "note": "Not the pumps of animal cells: it has no sodium-potassium pump. By its annotation, its ATP-driven ion movers are the ATP synthase, one P-type ATPase whose ion is not known, and a potassium uptake system."},
        "cap.junctions": {"place": "absent", "why": "It lives as single cells and has no gap junctions: none of its proteins carries the signature of connexins or innexins."},
        "cap.extracellular": {"place": "present", "note": "Here it is what surrounds the single cell: the surface of the airway cells it lives on, or a growth medium. The cell depends on it: it makes no amino acids of its own, and a defined medium needs 19 nutrients."},
        "cap.water": {"place": "present", "note": "It has no cell wall: nothing but the membrane bounds its volume. One of its proteins, GlpF, belongs to the family of water and glycerol channels."},
        "cap.calcium": {"place": "absent", "why": "It has no endoplasmic reticulum: it is a bacterium with a single membrane and no internal compartments, and none of its proteins carries the signature of the store's calcium pump or of its release channels."},
        "cap.energy": {"place": "present", "note": "Its ATP comes from fermenting sugar in the cytoplasm to lactate and acetate; it has no citric acid cycle and no working respiratory chain."},
        "cap.mitochondria": {"place": "absent", "why": "It is a bacterium and has no mitochondria. Its ATP synthase sits in the cell membrane."},
        "cap.circuits": {"place": "present", "note": "At the chromosome, which lies in the cytoplasm: there is no nucleus."},
        "cap.grn": {"place": "absent", "why": "It forms no tissue, so there is nothing for gene networks to be coupled across. Gene expression within the one cell belongs with regulatory circuits."},
        "cap.trafficking": {"place": "absent", "why": "It has no endoplasmic reticulum and no Golgi. By its annotation, new membrane proteins are put straight into the cell membrane by the Sec translocon and the YidC insertase."},
        "cap.assembly": {"place": "present", "note": "Its assemblies are its ribosomes, RNA polymerase, the ATP synthase and the dense core of its attachment organelle; a screen of 2009 found 62 complexes of one kind of protein and 116 of several. The designed protein cage that Cells models is not one of its proteins."},
        "cap.machines": {"place": "present", "note": "About 150 ribosomes, with RNA polymerase, the ATP synthase, the protein translocon and the machinery in its attachment organelle that lets it glide. None of its proteins carries the proteasome's signature; its annotation lists the proteases FtsH and Lon."},
        "cap.secretion": {"place": "present", "note": "It releases lactate and acetate, the end products of its fermentation, and takes its nutrients up. Signalling between its own cells was not looked for."},
        "cap.repair": {"place": "present", "note": "The place would be its bare membrane. No source read for this file describes a membrane injury or its resealing in this organism."},
        "cap.division": {"place": "present", "note": "It divides in two as a single cell. Its attachment organelle is duplicated first, and gliding is needed for the two to part normally; the division gene ftsZ is in its genome."},
        "cap.replacement": {"place": "absent", "why": "It forms no tissue, so there is no neighbour for a new cell to replace."},
        "cap.mechanics": {"place": "absent", "why": "It forms no sheet: its cells share no edges to pull on. Its own movement, gliding on a surface, is not what this capability models."},
        "cap.sheet": {"place": "absent", "why": "It lives as single cells and forms no sheet of coupled cells."},
    }
    facts = [
        {"label": "Shape and size", "value": "a thin cell 1 to 2 µm long and 0.1 to 0.2 µm wide, of changeable shape, drawn out at one end into its attachment organelle; one paper gives its volume as 0.05 µm³", "sources": ["parrott2016", "nakane2015", "maier2011"]},
        {"label": "Attachment organelle", "value": "a membrane-bound extension at one pole, 250 to 300 nm long, with a dense core; it carries the adhesins and leads the cell when it glides", "sources": ["nakane2021", "hasselbring2006"]},
        {"label": "Envelope", "value": "one membrane, stiffened by sterols; no cell wall", "sources": ["parrott2016", "nakane2015", "hasselbring2006"]},
        {"label": "Inside", "value": "a prokaryote, among the smallest and simplest known: no nucleus and no internal compartments", "sources": ["hasselbring2006"]},
        {"label": "Chromosome", "value": f"one circle of {c.length:,} base pairs", "sources": ["genbank", "himmelreich1996"]},
        {"label": "Genes", "value": f"{count} protein products in the genome record frozen here, the re-annotation of 2000; papers count 677, 688, 689 or 694 by annotation, and UniProt has {len(c.entries)} entries", "sources": ["genbank", "himmelreich1996", "dandekar2000", "wodke2013", "lluchsenar2015", "uniprot"]},
        {"label": "Ribosomes", "value": "about 140 to 150 in a cell, counts from electron tomograms of 2009 as a paper of 2011 reports them; the 2009 papers were not open to read", "sources": ["maier2011"]},
        {"label": "Proteins", "value": "167 copies of a protein on average among those measured, from about 2 to about 2,300 (the elongation factor Tu), by mass spectrometry", "sources": ["maier2011"]},
        {"label": "Essential genes", "value": "342 of 694 genes essential, 93 needed for normal growth and 259 dispensable, by transposon mutagenesis", "sources": ["lluchsenar2015"]},
        {"label": "Energy", "value": "ATP from fermenting sugar to lactate and acetate; no citric acid cycle and no working respiratory chain", "sources": ["wodke2013"]},
        {"label": "Food", "value": "glucose as its main source of carbon and energy; no amino acid synthesis; a defined medium with 19 essential nutrients", "sources": ["wodke2013", "himmelreich1996", "yus2009"]},
        {"label": "Ion channels", "value": f"none found among its {count} proteins; one glycerol facilitator of the aquaporin family", "sources": ["uniprot"]},
        {"label": "Division", "value": "in two; the attachment organelle is duplicated first, and gliding is needed for normal division", "sources": ["parrott2016", "hasselbring2006"]},
        {"label": "Movement", "value": "glides on surfaces, attachment organelle first, at up to 1 µm a second", "sources": ["nakane2015", "hasselbring2006"]},
        {"label": "Name", "value": f"databases now list it as {c.uniprot_name.split(' (')[0]}; the papers cited call it Mycoplasma pneumoniae", "sources": ["genbank", "uniprot"]},
    ]
    return {
        "format": SPECIES_FORMAT,
        "id": SPECIES_ID,
        "label": LABEL,
        "organism": ORGANISM,
        "taxon": TAXON,
        "plain": f"A small bacterium of the human airways, with a genome among the smallest of any organism that copies itself: {count} proteins in the genome record frozen here, in a thin cell about 2 µm long with one membrane, no wall and an attachment organelle at one end.",
        "order": 40,
        "default": False,
        "made": MADE,
        "modelled": {
            "state": "proposed",
            "text": "Its public measurements were audited beside the minimal-cell track on JCVI-syn3A (decision D173; the track's note of 15 November 2026), which recommends it to lead a later stage on energy, transport and pH. Nothing of it is in the engine, and no model of it has run.",
        },
        "levels": [
            {"id": "molecules"},
            {
                "id": "cell",
                "label": "One cell",
                "shape": {"kind": "capsule", "length_um": 2, "across_um": 0.2},
                "note": "Drawn as a rod 2 µm long and 0.2 µm across, the upper ends of the ranges given for the cell, with 150 ribosomes. The real cell is not a plain rod: it changes shape, and one end narrows into the attachment organelle, about 0.3 µm long, which this shape cannot show.",
                "sources": ["parrott2016", "nakane2015", "nakane2021", "maier2011"],
            },
        ],
        "no_further_levels": "A single-celled organism: each cell lives on its own, on the cells of its host, so it has no tissue, organ or body of its own.",
        "cell": {
            "facts": facts,
            "parts": {"membranes": 1, "wall": False, "nucleus": False, "chromosome_kbp": round(c.length / 1000), "ribosomes": 150},
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
        control = f"UniProtKB holds {found} entr{'y' if found == 1 else 'ies'} of mollicutes, the class of bacteria it belongs to, that carr{'ies' if found == 1 else 'y'} {'one of them' if many else 'it'}."
    else:
        control = f"No UniProtKB entry of any mollicute, the class of bacteria it belongs to, carries {'them' if many else 'it'} either."
    human = [family for family in families if family.get("human", True)]
    proof = f" The unit's human candidates carry {'them' if sum(len(f['signatures']) for f in human) > 1 else 'it'}, so the search finds the family where it exists." if human else ""
    return f"None of the {len(c.proteins)} protein products of its genome carries the signature of {listed(f['of'] for f in families)} ({', '.join(signatures)}). {control}{proof} {spec['tail']}"


EXISTENCE = {"1": "evidence at protein level", "2": "evidence at transcript level", "3": "inferred from homology", "4": "predicted", "5": "uncertain"}


def existence(entry):
    return EXISTENCE[entry["proteinExistence"][0]]


def extra_products(c):
    out = []
    for item in EXTRA:
        protein, entry = c.by_locus[item["locus"]], c.entry_of[item["locus"]]
        out.append({
            "name": item["name"],
            "gene": entry_gene(entry) or protein.get("gene") or None,
            "role": item["role"],
            "ids": [{"db": "uniprot", "id": entry["primaryAccession"]}],
            "length": len(protein["sequence"]),
            "evidence": "reviewed entry",
            "evidence_note": f"Locus {item['locus']}, product \"{protein['protein']}\" in the genome record. Its reviewed UniProtKB entry names it \"{entry_name(entry)}\", with UniProt's level of evidence \"{existence(entry)}\": the entry is curated, and its function is assigned from its sequence, not measured in this organism. The sequence carries {item['signature']} ({c.signature_names[item['signature']]}).",
            "citation": None,
            "why": item["why"],
        })
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
    return {
        "format": ATLAS_FORMAT,
        "species": {
            "id": SPECIES_ID,
            "label": LABEL,
            "organism": ORGANISM,
            "taxon": TAXON,
            "plain": f"A small bacterium of the human airways with {len(c.proteins)} proteins in its genome record, to be audited beside JCVI-syn3A for measured data to validate Cells against; the units of the law inventory are machines of animal cells, and it has none of them.",
        },
        "made": MADE,
        "method": [
            f"The organism's proteins are the {len(c.proteins)} protein products of one frozen genome annotation, GenBank {RECORD}: the genome of strain M129 as its submitters re-annotated it in 2000. UniProtKB holds a reviewed entry for {len(set(c.entry_of))} of them, and UniProt's archive (UniParc) holds all {len(c.proteins)} sequences letter for letter, with the family signatures on each.",
            "Licences were read before anything was copied; each is stated in sources, and what was read but not copied is in not_copied.",
            "Each unit's family was taken from its own human candidates, by the same InterPro signatures that the planarian and Syn3A atlases ask. The build checks that the candidates carry them.",
            f"Each signature was looked for on all {len(c.proteins)} sequences. None was found, for any unit.",
            "A control for every zero: the same signature was asked of the UniProtKB entries of all mollicutes, the class of bacteria the organism belongs to; each unit's note gives what came back.",
            "Eight further signatures, of the channels a bacterium could have (potassium, chloride, magnesium, water and membrane-stretch channels), were looked for as well. Seven were not found, although each is carried by UniProtKB entries of other mollicutes. One was: the family of water and glycerol channels, on the glycerol facilitator GlpF.",
            "Under extra are nine of the organism's own membrane machines that bear on what the atlas draws and match no unit. Each has a reviewed UniProtKB entry of this strain and is listed by it; their functions are assigned by curators from sequence, not measured in this organism.",
            "No similarity search was run, and nothing is called an ortholog.",
        ],
        "sources": [
            {
                "name": "GenBank", "url": f"https://www.ncbi.nlm.nih.gov/nuccore/{RECORD}", "release": f"{RECORD}, the re-annotation of 2000", "accessed": ev.day(f"genbank_{RECORD}_cds_aa.fa"),
                "licence": "No restriction: \"NCBI places no restrictions on the use or distribution of the GenBank data\". Submitters may claim rights in what they submitted; this record states none.",
                "cite": f"Himmelreich R, Hilbert H, Li B-C; Suyama M, Dandekar T, Herrmann R (1996, 2000) {c.record_title}. GenBank {RECORD}.",
                "holds": "the locus tags, gene names, products and lengths of the organism's proteins",
            },
            {
                "name": "UniProt", "url": "https://www.uniprot.org/", "release": c.uniprot_release, "accessed": ev.day(f"uniparc_{TAXON}.json"), "licence": "CC BY 4.0",
                "cite": "The UniProt Consortium, UniProt: the Universal Protein Knowledgebase in 2025, Nucleic Acids Res. 53:D609-D617 (2025)",
                "holds": "the reviewed entries of the organism's proteins; which archived sequences carry each family signature; the signatures of the units' human candidates; the control counts",
            },
            {
                "name": "InterPro", "url": "https://www.ebi.ac.uk/interpro/", "accessed": ev.day("terms_interpro_license.html"), "licence": "CC0 1.0",
                "cite": "Blum and others (2025) InterPro: the protein sequence classification resource in 2025. Nucleic Acids Res 53:D444-D456.",
                "holds": "the identifiers and names of the family signatures, as UniProt gives them",
            },
        ],
        "not_copied": "No sequence is copied: they stay with the downloads, outside the repository. The papers with measured protein amounts and other tables of this organism (Maier and others 2011, Wodke and others 2013, Chen and others 2016) are under non-commercial licences: numbers from them are cited in the species file and their tables are not copied. No whole-cell or genome-scale model of the organism was read for its files.",
        "units": units,
        "extra": extra_products(c),
    }


CATALOGUE_COLUMNS = ["locus_tag", "gene", "product", "length", "protein_id", "uniprotkb", "uniprotkb_name", "uniprotkb_length", "protein_existence", "functional_class", "essentiality", "essentiality_relaxed", "uniparc", "interpro"]


def class_of(c, locus):
    letter = c.numbered[locus]["class"]
    return letter if letter in CLASSES else NO_CLASS


def build_catalogue(c):
    rows = []
    for protein in c.proteins:
        locus = protein["locus_tag"]
        entry = c.entry_of.get(locus)
        table = c.numbered[locus]
        letter = class_of(c, locus)
        rows.append([
            locus, protein.get("gene", ""), protein["protein"], len(protein["sequence"]), protein["protein_id"],
            entry["primaryAccession"] if entry else "", entry_name(entry) if entry else "", entry["sequence"]["length"] if entry else "",
            existence(entry) if entry else "",
            f"{letter}: {CLASSES[letter]}" if letter != NO_CLASS else "",
            ESSENTIALITY[table["stringent"]], ESSENTIALITY[table["relaxed"]],
            protein["uniparc"], ";".join(protein["interpro"]),
        ])
    return [[re.sub(r"\s+", " ", str(value)).strip() for value in row] for row in rows]


def table(rows):
    return "\n".join("\t".join(row) for row in [CATALOGUE_COLUMNS, *rows]) + "\n"


SHELF_COLUMNS = ["id", "label", "gene", "shelf", "side", "basis", "group", "length", "unit", "marks"]
SIDES = ["outside", "in", "inside", "not known"]


def build_shelves(c):
    ev = c.evidence
    proteins = []
    for protein in c.proteins:
        locus = protein["locus_tag"]
        entry = c.entry_of.get(locus)
        placed = placement(entry)
        marks = {"essential": ESSENTIALITY[c.numbered[locus]["stringent"]]}
        if entry and entry["proteinExistence"].startswith("1"):
            marks["seen"] = True
        for key in ("evidence", "where", "also"):
            if placed[key]:
                marks[key] = placed[key]
        label = re.sub(r"\s+", " ", (entry_name(entry) if entry else "") or protein["protein"]).strip()
        proteins.append([locus, label, (entry_gene(entry) if entry else "") or protein.get("gene") or None, "cell", placed["side"], placed["basis"], class_of(c, locus), len(protein["sequence"]), None, marks])
    used = [letter for letter in [*CLASSES, NO_CLASS] if any(row[6] == letter for row in proteins)]
    lluch = citation(c, "lluchsenar2015")
    by_side = Counter(row[4] for row in proteins)
    return {
        "format": SHELVES_FORMAT,
        "species": SPECIES_ID,
        "made": MADE,
        "from": f"GenBank {RECORD}: {len(proteins)} protein products",
        "shelves": [{"id": "cell", "label": "Cell membrane", "outside": "Outside the cell", "inside": "Inside the cell"}],
        "groups": [{"id": letter, "label": CLASSES.get(letter, "No class given"), "from": "the class the 2015 essentiality paper gives each gene (its Supplementary Table S2)"} for letter in used],
        "columns": SHELF_COLUMNS,
        "proteins": proteins,
        "side_notes": {
            "stated": "The protein's reviewed UniProtKB entry states where it is, on a curator's own word or on an experiment that the entry cites. The mark 'evidence' says which.",
            "predicted": "Read from the sequence, as UniProt's reviewed entry for this exact protein records it. Membrane-spanning segments are those UniProt predicts with TMHMM, Memsat, Phobius and a hydrophobic moment plot, keeping a segment only where at least two agree; signal peptides are predicted with Phobius, Predotar, SignalP and TargetP. A lipoprotein signal (the PROSITE rule PRU00303) means the protein is exported and then held by a lipid at the outer face of the membrane, which in a cell with one membrane is the cell's surface: that reading is this file's. A location that UniProt gives a whole protein family by rule (HAMAP), or by likeness to a protein of another organism, is counted as predicted too.",
            "by function": "Taken from what the protein does, only where that leaves no real doubt. A protein with no stated location is put inside if its UniProt keywords say it works on the ribosome, on transfer or ribosomal RNA, in transcription or on the chromosome (" + ", ".join(INSIDE_BY_FUNCTION) + "). A protein that its entry places at the membrane without saying on which face is put inside if it binds ATP or GTP, makes ATP or binds DNA, all of which are inside the cell.",
            "not known": "No statement, no prediction and no function that settles it. These proteins are not placed.",
        },
        "marks": {
            "essential": {"label": "Essentiality", "values": list(ESSENTIALITY.values()), "measured": True, "source": "Lluch-Senar and others 2015"},
            "seen": {"label": "Evidence at protein level", "values": [True], "measured": True, "source": "UniProt"},
            "evidence": {"label": "How the side is known", "values": [EXPERIMENT, CURATOR, SIMILARITY, RULE], "measured": False, "source": "UniProt"},
            "where": {"label": "Where in the cell", "values": ["attachment organelle", "at the membrane"], "measured": False, "source": "UniProt"},
            "also": {"label": "Also stated on another side", "values": ["outside", "inside"], "measured": False, "source": "UniProt"},
        },
        "counts": {side: by_side[side] for side in SIDES},
        "sources": [
            {"name": "GenBank", "url": f"https://www.ncbi.nlm.nih.gov/nuccore/{RECORD}", "licence": "NCBI places no restrictions on the use or distribution of GenBank data; this record states none", "accessed": ev.day(f"genbank_{RECORD}_cds_aa.fa"), "holds": "the locus tags and lengths of the proteins, and the names of those without a UniProtKB entry"},
            {"name": "UniProt", "url": "https://www.uniprot.org/", "licence": "CC BY 4.0", "accessed": ev.day(f"uniprotkb_{TAXON}.json"), "holds": f"release {c.uniprot_release}: each protein's name and gene, its stated location with the evidence for it, its membrane-spanning segments, signal and lipid anchor, its keywords and its level of evidence"},
            {"name": "Lluch-Senar and others 2015", "url": f"https://doi.org/{lluch['doi']}", "licence": "CC BY 4.0", "accessed": ev.day("lluchsenar2015_table_s2.xlsx"), "holds": "each gene's class and its essentiality, from Supplementary Table S2"},
        ],
    }


def build_readme(c, rows, shelves):
    ev = c.evidence
    count = len(rows)
    with_entry = sum(bool(row[5]) for row in rows)
    essentiality = Counter(row[10] for row in rows)
    relaxed = Counter(row[11] for row in rows)
    levels = Counter(row[8] for row in rows if row[8])
    differ = sum(1 for row in rows if row[7] and row[7] != row[3])
    unsigned = sum(not row[13] for row in rows)
    unclassed = sum(not row[9] for row in rows)
    lluch = citation(c, "lluchsenar2015")
    sides = shelves["counts"]
    bases = Counter(row[5] for row in shelves["proteins"])
    at_tip = sum(1 for row in shelves["proteins"] if row[9].get("where") == "attachment organelle")
    built_from = [
        ("The genome record's summary", f"genbank_{RECORD}_summary.json"), ("Its features: genes, coding sequences, RNA genes", f"genbank_{RECORD}_features.ft"),
        ("Its protein products", f"genbank_{RECORD}_cds_aa.fa"), ("The same genome as NCBI's pipeline annotates it", f"refseq_{REFSEQ}_features.ft"),
        ("UniProt's curated entries of the strain", f"uniprotkb_{TAXON}.json"), ("UniProt's archived sequences and signatures", f"uniparc_{TAXON}.json"),
        ("The 2015 paper's Supplementary Table S2", "lluchsenar2015_table_s2.xlsx"), ("The 2015 paper's supplementary text", "lluchsenar2015_supplementary_information.docx"),
    ]
    inputs = "\n".join(f"| {what} | `{ev.read[name]['source']}` | `{ev.read[name]['file']}` | `{ev.read[name]['sha256']}` |" for what, name in built_from)
    day_record, day_paper, day_uniprot = ev.day(f"genbank_{RECORD}_cds_aa.fa"), ev.day("lluchsenar2015_table_s2.xlsx"), ev.day(f"uniprotkb_{TAXON}.json")
    rna = c.kinds["tRNA"] + c.kinds["rRNA"] + c.kinds["misc_RNA"]
    classes = "\n".join(f"| `{letter}` | {name} | {sum(row[9].startswith(letter + ':') for row in rows)} |" for letter, name in CLASSES.items())
    return f"""# M. pneumoniae proteins: a catalogue

`{CATALOGUE_FILE}` lists the {count} protein products of one frozen genome annotation of the
bacterium *{ORGANISM}*, one per line, with what open sources say of each: what it is
named, how long it is, what it is for, how sure it is that the protein exists, and whether
the cell can do without it. `{SHELVES_FILE}` says, for the same {count} proteins, on which
side of the cell membrane each one sits.

Generated by `tools/build_mpneumoniae_atlas.py`; do not edit. This is reference data for
the viewer. It is not the engine's protein catalogue, and nothing in the engine reads it.

## The frozen annotation

GenBank **{RECORD}**: "{c.record_title}", {c.length:,} base pairs, one circular
chromosome, strain {c.record_strain} (taxon {TAXON}). It is the genome as its authors
submitted it in 1996 and re-annotated it in 2000, and its locus tags (MPN_001 to MPN_688)
are the numbers the papers on this organism use. NCBI and UniProt now list the organism as
*{c.uniprot_name.split(' (')[0]}*.

| In the record | Count | In this table |
| --- | --- | --- |
| Coding sequences, each with a protein product | {count} | all {count} |
| RNA features (tRNA, rRNA and other RNA) | {rna} | not listed |
| Repeat regions | {c.kinds['repeat_region']} | not listed |

**Why the counts in the literature differ.** The user expected about 700 proteins; this
record has {count}.

| Count | Whose | What it counts |
| --- | --- | --- |
| 677 | Himmelreich and others 1996 | the reading frames predicted when the genome was sequenced |
| 688 | Dandekar and others 2000; this record | the re-annotation: 12 added and one dismissed |
| 689 | Wodke and others 2013 | "encoding 689 proteins", citing the two papers above; which gene makes the difference was not traced here |
| 694 | Lluch-Senar and others 2015 | their re-annotation, 32 of them reading frames under 100 residues; their table lists 49 lettered additions (MPN037a and the like) beside the {count} numbered genes |
| {len(c.entries)} | UniProt, release {c.uniprot_release} | reviewed entries of the strain: MPN_304 and MPN_305, two fragments of one gene, share an entry, and MPN_441 has none |
| {c.refseq_kinds['CDS']} | NCBI RefSeq {REFSEQ} | the coding sequences that NCBI's own annotation pipeline finds in the same genome today |

## Columns

Tab-separated, with a header line. An empty cell means the source says nothing.

| Column | What it is | From | Measured, or annotation? |
| --- | --- | --- | --- |
| `locus_tag` | The gene's locus tag | GenBank {RECORD} | Annotation |
| `gene` | The gene name, where the record gives one | GenBank {RECORD} | Annotation of 2000 |
| `product` | The product's name | GenBank {RECORD} | Annotation of 2000, mostly by similarity to other bacteria |
| `length` | Residues of the protein product | GenBank {RECORD}, counted from its translation | From the sequence |
| `protein_id` | The protein's identifier at NCBI | GenBank {RECORD} | Identifier |
| `uniprotkb` | The accession of the protein's UniProtKB entry | UniProt, release {c.uniprot_release} | Identifier; every entry is a reviewed one |
| `uniprotkb_name` | The name UniProt's curators give the protein | UniProt | Curated annotation |
| `uniprotkb_length` | Residues of the sequence in UniProt's entry | UniProt | From the sequence; it differs from `length` for {differ} proteins, where the curators set another start or end |
| `protein_existence` | UniProt's level of evidence that the protein exists | UniProt | UniProt's judgement of the published evidence: "evidence at protein level" means an experiment saw the protein |
| `functional_class` | The class the 2015 paper gives the gene: its letter and the paper's name for it | Lluch-Senar and others 2015, Supplementary Table S2 and the supplementary text | Annotation |
| `essentiality` | `essential`, `fitness`, `non-essential` or `non-essential (repeats)`, at the paper's stringent threshold | Lluch-Senar and others 2015, Supplementary Table S2 | **Measured** by transposon mutagenesis in this strain, then classed by the paper's probabilities |
| `essentiality_relaxed` | The same at the paper's relaxed threshold | Lluch-Senar and others 2015, Supplementary Table S2 | **Measured**, as above |
| `uniparc` | The sequence's identifier in UniProt's archive | UniProt (UniParc), release {c.uniprot_release} | Identifier |
| `interpro` | The InterPro family and domain signatures on the sequence | UniProt (UniParc), release {c.uniprot_release} | Computed from the sequence |

**Essentiality.** The paper grew a library of transposon mutants for 12 days and read
where insertions survived. A gene is `essential` where insertions were as rare as in
genes known to be essential, `non-essential` where they were as common as in dispensable
genes, and `fitness` in between, the paper's word for a score that is neither. `(repeats)`
marks dispensable genes that hold repeated sequence, which the paper sets apart because
reads cannot be placed surely there. The paper counts an insertion at two thresholds of
reads, 41 (stringent, the one it uses for its minimal genome) and 7 (relaxed); both are
copied.

| | essential | fitness | non-essential | non-essential (repeats) |
| --- | --- | --- | --- | --- |
| stringent | {essentiality['essential']} | {essentiality['fitness']} | {essentiality['non-essential']} | {essentiality['non-essential (repeats)']} |
| relaxed | {relaxed['essential']} | {relaxed['fitness']} | {relaxed['non-essential']} | {relaxed['non-essential (repeats)']} |

The paper's own totals, over the 694 genes of its annotation, are 342 essential, 93
fitness and 259 non-essential.

**Classes.** The paper's letters, with its own names for them{"; every one of the " + str(count) + " genes has one" if not unclassed else "; " + str(unclassed) + " genes have none"}. The names are the paper's: its `A`, for one, is not the class of that letter in the database of gene families the letters come from.

| Letter | The paper's name | Genes |
| --- | --- | --- |
{classes}

Other counts, as built:

- **A UniProtKB entry:** {with_entry} of the {count}, all reviewed.
- **UniProt's level of evidence:** {levels['evidence at protein level']} at protein level, {levels['evidence at transcript level']} at transcript level, {levels['inferred from homology']} inferred from homology, {levels['predicted']} predicted, {levels['uncertain']} uncertain.
- **No signature at all:** {unsigned} of the {count}.

**What is not here, and why.** Measured amounts of each protein exist for this organism,
in Maier and others 2011, and many more data sets in Chen and others 2016. Both papers are
under non-commercial licences, so their tables are not copied; the species file cites a
few of their numbers. Sequences stay with the downloads. Nothing is taken from a
whole-cell or genome-scale model. Strain identity matters: every value is for strain M129.

## `{SHELVES_FILE}`: where each protein sits

In the form `schema/SPECIES_PROTEINS.md` fixes: one shelf, the cell membrane, and one line
for each of the {count} proteins, in the catalogue's order.

| Side | Proteins | |
| --- | --- | --- |
| outside | {sides['outside']} | beyond the membrane, free or held to its outer face |
| in | {sides['in']} | spans the membrane |
| inside | {sides['inside']} | enclosed by the membrane |
| not known | {sides['not known']} | not placed |

- **How each side is known:** {bases['stated']} stated by the protein's reviewed UniProtKB
  entry, {bases['predicted']} predicted from the sequence, {bases['by function']} by
  function, {bases['none']} not known. The file's `side_notes` say what each word covers
  and name the predictors.
- **Lipoproteins and adhesins.** A protein with a lipoprotein signal is put outside: it is
  exported and then held by a lipid at the outer face of the membrane. That reading is
  this file's; UniProt records the signal, by the PROSITE rule PRU00303. The adhesins
  that span the membrane are `in`.
- **The attachment organelle** is not a shelf of its own. The {at_tip} proteins whose entry
  states that location carry the mark `where: attachment organelle`.
- **Districts** are the 2015 paper's classes, the letters above.
- **Marks:** essentiality (measured, from the 2015 paper), whether UniProt records evidence
  at protein level, how the side is known, and whether another side is stated as well.
  No amount is given: the measured amounts are under non-commercial terms.
- **`unit`** is empty on every line: the atlas found none of the law inventory's machines
  in this organism.

## Sources and terms

| Source | What is taken | Terms |
| --- | --- | --- |
| [GenBank {RECORD}](https://www.ncbi.nlm.nih.gov/nuccore/{RECORD}), read {day_record} | Locus tags, gene names, products, protein identifiers, lengths | "NCBI places no restrictions on the use or distribution of the GenBank data"; submitters may claim rights in what they submitted, and this record states none |
| [UniProt](https://www.uniprot.org/), release {c.uniprot_release}, read {day_uniprot} | Accessions, curated names, levels of evidence, stated locations and sequence features, archive identifiers and signatures | CC BY 4.0 |
| [Lluch-Senar and others 2015](https://doi.org/{lluch['doi']}), Supplementary Table S2 and supplementary text, read {day_paper} | Each gene's class and essentiality | CC BY 4.0 |
| [InterPro](https://www.ebi.ac.uk/interpro/) | The signatures' identifiers | CC0 1.0 |

Cite:

- GenBank: Himmelreich R, Hilbert H, Li B-C; Suyama M, Dandekar T, Herrmann R (1996, 2000) {c.record_title}. GenBank {RECORD}.
- {lluch['text']} doi:{lluch['doi']}
- The UniProt Consortium, UniProt: the Universal Protein Knowledgebase in 2025, Nucleic Acids Res. 53:D609-D617 (2025)

## The files it was built from

Each is in the dataset folder of its source, outside the repository, and the build checks
it against the SHA-256 that the folder's MANIFEST gives before reading it.

| What | Dataset folder | File | SHA-256 |
| --- | --- | --- | --- |
{inputs}

## How to rebuild

```bash
python3 tools/build_mpneumoniae_atlas.py fetch --evidence DIR --datasets DATA   # network; saves what is not yet there
python3 tools/build_mpneumoniae_atlas.py build --evidence DIR --datasets DATA   # offline; the same bytes every time
```

`DATA` holds the downloads, one folder per source with a MANIFEST.json; `DIR` holds the
log of what this tool asked. Both are kept outside the repository. The build also writes
`data/species/mpneumoniae.json` and `data/proteins/atlases/mpneumoniae.json`.
`docs/MPNEUMONIAE.md` describes the method and its limits.
"""


def build(evidence_folder, datasets_folder, snapshot):
    evidence = Evidence(evidence_folder, datasets_folder)
    context = Context(evidence, snapshot)
    check_sources(context)
    species = build_species(context)
    atlas = build_atlas(context)
    rows = build_catalogue(context)
    shelves = build_shelves(context)
    files = {
        "species": json.dumps(species, indent=1, ensure_ascii=False) + "\n",
        "atlas": json.dumps(atlas, indent=1, ensure_ascii=False) + "\n",
        "catalogue": table(rows),
        "shelves": shelves_text(shelves),
        "readme": build_readme(context, rows, shelves),
    }
    for name, text in files.items():
        if PATHS.search(text):
            raise SystemExit(f"the {name} would hold a machine path")
    for name in ("catalogue", "shelves"):
        if len(files[name].encode("utf-8")) > 1_000_000:
            raise SystemExit(f"the {name} has grown past 1 MB")
    return files, species, atlas, rows, shelves, context


def shelves_text(shelves):
    """The shelves as text: one protein to a line, so the file can be read and compared."""
    mark = "@@proteins@@"
    text = json.dumps({**shelves, "proteins": mark}, indent=1, ensure_ascii=False)
    lines = ",\n".join("  " + json.dumps(row, ensure_ascii=False) for row in shelves["proteins"])
    if text.count(f'"{mark}"') != 1:
        raise SystemExit("the shelves' text cannot be laid out")
    return text.replace(f'"{mark}"', "[\n" + lines + "\n ]") + "\n"


def summary(species, atlas, rows, shelves, context):
    findings = Counter(unit["finding"] for unit in atlas["units"].values())
    places = Counter(item["place"] for item in species["cell"]["capabilities"].values())
    lines = [
        f"frozen annotation: GenBank {RECORD}, {context.length:,} bp; features {dict(context.kinds)}; {len(rows)} protein products; RefSeq {REFSEQ} has {context.refseq_kinds['CDS']} coding sequences",
        f"UniProt release {context.uniprot_release}: {len(context.entries)} entries of the strain, {context.archived} archived sequences",
        f"units by finding: {dict(sorted(findings.items()))}; extra: {len(atlas['extra'])} ({dict(Counter(p['evidence'] for p in atlas['extra']))})",
        f"capabilities stated: {dict(sorted(places.items()))} of {len(species['cell']['capabilities'])}",
        f"catalogue: essentiality {dict(Counter(row[10] for row in rows))}; relaxed {dict(Counter(row[11] for row in rows))}; existence {dict(Counter(row[8] for row in rows))}",
        f"shelves: sides {shelves['counts']}; bases {dict(Counter(row[5] for row in shelves['proteins']))}; groups {dict(Counter(row[6] for row in shelves['proteins']))}",
        f"shelves: marks where {dict(Counter(row[9].get('where') for row in shelves['proteins'] if row[9].get('where')))}; also {dict(Counter(row[9].get('also') for row in shelves['proteins'] if row[9].get('also')))}; evidence {dict(Counter(row[9].get('evidence') for row in shelves['proteins'] if row[9].get('evidence')))}; seen {sum(1 for row in shelves['proteins'] if row[9].get('seen'))}",
        "mollicute entries carrying a searched signature: " + (", ".join(f"{s} {context.mollicutes(s)}" for s in sorted({*rule_signatures(), *BACTERIAL_CHANNELS, PROTEASOME}) if context.mollicutes(s)) or "none"),
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
    folder = Path(args.out_catalogue)
    targets = {"species": Path(args.out_species), "atlas": Path(args.out_atlas), "catalogue": folder / CATALOGUE_FILE, "shelves": folder / SHELVES_FILE, "readme": folder / "README.md"}
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
