#!/usr/bin/env python3
"""Build the planarian side of the protein atlas, and the reference proteins it draws on.

The protein atlas draws the functional units of the Cells law inventory. A unit has no
species; what changes with the species is which gene products would make that machine.
This tool answers that for the planarian Schmidtea mediterranea, for every unit, in the
form schema/SPECIES_ATLAS.md fixes. The answers are drawn from the planarian's UniProtKB
entries and from the gene models of one genome annotation, which the tool also writes
out as a table.

Two steps, kept apart:

    python3 tools/build_planarian_atlas.py fetch --evidence DIR
        asks public databases and saves every response in DIR/responses, with what was
        asked and when in DIR/requests.json. The only step that uses the network.

    python3 tools/build_planarian_atlas.py build --evidence DIR
        reads only DIR and the inventory snapshot, and writes
        data/proteins/atlases/planarian.json, data/proteins/planarian/reference_proteins.tsv
        and data/proteins/planarian/README.md: the same bytes every time.

The mass-spectrometry library of about 10,000 planarian proteins (Ying and others 2025)
is not imported: its list of proteins could not be reached under terms that allow a copy.
The README the build writes says what was found and what is missing.

This is the viewer's reference data. It is not the engine's protein catalogue and it
makes no claim about the engine: the laws are the same for every species.

Requests carry a generic client name and nothing about who asks. Standard library only.
"""

from __future__ import annotations

import argparse
import gzip
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
SNAPSHOT = ROOT / "data" / "proteins" / "inventory.snapshot.json"
ATLAS = ROOT / "data" / "proteins" / "atlases" / "planarian.json"
REFERENCE_DIR = ROOT / "data" / "proteins" / "planarian"
ATLAS_FORMAT = "cells.visualizer.species_atlas@1"
CLIENT = "atlas-builder/1.0"
PATHS = re.compile(r"/(?:home|mnt|Users)/")

TAXON = 79327
ORGANISM = "Schmidtea mediterranea"
PLANARIANS = 6159  # the order Tricladida
# The other planarians databases hold entries for; read only to settle the species.
OTHER_PLANARIANS = {6161: "Dugesia japonica", 6162: "Girardia tigrina", 79738: "Dugesia ryukyuensis", 50054: "Schmidtea polychroa"}

UNIPROT = "https://rest.uniprot.org"
EPMC = "https://www.ebi.ac.uk/europepmc/webservices/rest"
WBPS_RELEASE = "WBPS19"
WBPS_SET = "S2F19H1_PRJNA885486"
WBPS_FILES = f"https://ftp.ebi.ac.uk/pub/databases/wormbase/parasite/releases/{WBPS_RELEASE}/species/schmidtea_mediterranea/{WBPS_SET}/schmidtea_mediterranea.{WBPS_SET}.{WBPS_RELEASE}"
KB_FIELDS = "accession,reviewed,id,protein_name,gene_names,length,protein_existence,xref_interpro,xref_pfam,xref_panther,lit_pubmed_id,sequence"
HUMAN_FIELDS = "accession,gene_primary,protein_name,length,xref_interpro,xref_pfam,xref_panther"


# ---------------------------------------------------------------------------------------
# Fetch: what is asked, and how each answer is kept
# ---------------------------------------------------------------------------------------

def q(text):
    return urllib.parse.quote(text, safe="")


def human_accessions(snapshot):
    return sorted({p["human_uniprot"] for unit in snapshot["units"] for p in unit.get("products") or [] if p.get("human_uniprot")})


def requests(snapshot):
    """Every request of the fetch step: (file name, URL, what it is for)."""
    out = []

    def add(name, url, purpose, **more):
        out.append({"name": name, "url": url, "purpose": purpose, **more})

    # Which planarian: what UniProt and the genome databases hold for each candidate species.
    for taxon, name in [(TAXON, ORGANISM), *sorted(OTHER_PLANARIANS.items())]:
        add(f"uniprot_taxonomy_{taxon}.json", f"{UNIPROT}/taxonomy/{taxon}", f"UniProt's entry counts for {name}")
    add(f"uniprot_taxonomy_{PLANARIANS}.json", f"{UNIPROT}/taxonomy/{PLANARIANS}", "UniProt's entry counts for all planarians together (the order Tricladida)")
    add(f"uniprot_proteomes_{TAXON}.json", f"{UNIPROT}/proteomes/search?query={q(f'taxonomy_id:{TAXON}')}&format=json&size=5", "whether UniProt holds a proteome of the species")
    add(f"uniprot_proteomes_{PLANARIANS}.json", f"{UNIPROT}/proteomes/search?query={q(f'taxonomy_id:{PLANARIANS}')}&format=json&size=5", "whether UniProt holds a proteome of any planarian")
    add("ncbi_bioprojects_genome.json", "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi?db=bioproject&id=885486,1052007&retmode=json&tool=atlas-builder", "the project the gene models are listed under, and the project the genome paper names")
    add(f"uniparc_databases_{TAXON}.json", f"{UNIPROT}/uniparc/search?query={q(f'taxonomy_id:{TAXON}')}&facets=database_facet&size=0&format=json", "where UniProt's archive of sequences of the species comes from")
    add(f"ncbi_protein_count_{TAXON}.json", f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?db=protein&term=txid{TAXON}%5BOrganism%3Aexp%5D&retmax=0&retmode=json&tool=atlas-builder", "how many protein records NCBI holds for the species")
    for key, path in [("s3h1", "Schmidtea_mediterranea_s2f19h1prjna885486"), ("s3h2", "Schmidtea_mediterranea_s2f19h2prjna885486"), ("smedgd", "Schmidtea_mediterranea_prjna12585")]:
        add(f"wbps_species_{key}.html", f"https://parasite.wormbase.org/{path}/Info/Index", "WormBase ParaSite's page of a genome annotation of the species: assembly, source and gene counts")

    # The species' entries in UniProtKB, and the signatures of the units' human candidates.
    add(f"uniprotkb_{TAXON}.json", f"{UNIPROT}/uniprotkb/stream?query={q(f'taxonomy_id:{TAXON}')}&format=json&fields={KB_FIELDS}", "every UniProtKB entry of the species, with its signatures and the papers it cites")
    add("uniprotkb_human_candidates.json", f"{UNIPROT}/uniprotkb/accessions?accessions={','.join(human_accessions(snapshot))}&format=json&fields={HUMAN_FIELDS}", "the family signatures carried by the units' human candidates")

    # The gene models: predicted proteins and their signatures, one genome annotation.
    add("wbps_s3h1_protein.fa.gz", f"{WBPS_FILES}.protein.fa.gz", "predicted proteins of the gene models (identifiers and lengths)")
    add("wbps_s3h1_annotations.gff3.gz", f"{WBPS_FILES}.annotations.gff3.gz", "the gene models and the InterPro signatures on each predicted protein")
    add("interpro_entry_list.tsv", "https://ftp.ebi.ac.uk/pub/databases/interpro/current_release/entry.list", "the name and type of each InterPro entry")
    add("interpro_release_notes.txt", "https://ftp.ebi.ac.uk/pub/databases/interpro/current_release/release_notes.txt", "the InterPro release the names come from")

    # Each family signature, asked of UniProt's archive of the species' sequences (every
    # annotation set, current InterPro), and as a control of other flatworms and of human:
    # a signature that finds nothing in the planarian must find the family where it is known.
    for signature in rule_signatures():
        add(f"uniparc_{signature}_{TAXON}.tsv", f"{UNIPROT}/uniparc/stream?query={q(f'taxonomy_id:{TAXON} AND feature_id:{signature}')}&format=tsv&fields=upi,length,accession,sequence", f"the archived sequences of {ORGANISM} that carry {signature}")
        add(f"control_uniprotkb_{signature}_6157.json", f"{UNIPROT}/uniprotkb/search?query={q(f'(xref:interpro-{signature}) AND (taxonomy_id:6157)')}&size=1&fields=accession&format=json", f"how many UniProtKB entries of flatworms (Platyhelminthes) carry {signature}")
        add(f"control_uniprotkb_{signature}_9606.json", f"{UNIPROT}/uniprotkb/search?query={q(f'(xref:interpro-{signature}) AND (taxonomy_id:9606) AND (reviewed:true)')}&size=1&fields=accession&format=json", f"how many reviewed human UniProtKB entries carry {signature}")

    # Papers: the records of the publications the atlas cites, and the open-access texts
    # read to check that a paper uses a name.
    pmids = sorted(cited_pmids(), key=int)
    add("europepmc_citations.json", f"{EPMC}/search?query={q('src:med AND ext_id:(' + ' OR '.join(pmids) + ')')}&format=json&resultType=core&pageSize=100", "the records of the papers the atlas cites")
    for pmcid in sorted(FULL_TEXTS):
        add(f"europepmc_fulltext_{pmcid}.xml", f"{EPMC}/{pmcid}/fullTextXML", "an open-access paper's text, read to check the name it gives a planarian protein")

    # The sequence records behind entries whose own name is not the paper's: each ties its
    # sequence to the paper and gives the name the submitters used.
    tied = sorted(accession for accession, item in [*NAMED.items(), *((e["accession"], e) for e in EXTRA if e.get("accession"))] if item.get("record"))
    add("uniprotkb_record_links.json", f"{UNIPROT}/uniprotkb/accessions?accessions={','.join(tied)}&format=json&fields=accession,xref_embl", "the sequence records that these UniProtKB entries were made from")
    for record in sorted(item["record"]["embl"] for item in [*NAMED.values(), *EXTRA] if item.get("record")):
        add(f"ena_{record}.txt", f"https://www.ebi.ac.uk/ena/browser/api/embl/{record}?lineLimit=40", "a sequence record: its title, its species and the paper it belongs to")

    # Terms of each source, read before anything was copied.
    add("terms_uniprot_license.json", f"{UNIPROT}/help/license", "UniProt's licence")
    add("terms_wbps_disclaimer.html", "https://parasite.wormbase.org/info/about/legal/disclaimer.html", "WormBase ParaSite's disclaimer on the use of its data")
    add("terms_wbps_datausage.html", "https://parasite.wormbase.org/info/about/datausage.html", "WormBase ParaSite's data usage policy")
    add("terms_interpro_license.html", "https://interpro-documentation.readthedocs.io/en/latest/license.html", "InterPro's licence")
    add("terms_embl_ebi.html", "https://www.ebi.ac.uk/about/terms-of-use/", "EMBL-EBI's terms of use, which cover WormBase ParaSite and Europe PMC")
    add("terms_europepmc_s3_genome_paper.json", f"{EPMC}/search?query={q('DOI:10.1038/s41467-024-52380-9')}&format=json&resultType=core", "the record and licence of the paper that published the genome annotation")
    add("terms_europepmc_s3_genome_paper_fulltext.xml", f"{EPMC}/PMC11410931/fullTextXML", "the genome paper's own licence and data availability statement")
    add("terms_iprox_data_licence.html", "https://www.iprox.org/page/iproxDataLisence.html", "iProX's data licence")
    add("terms_insdc_policy.html", "https://www.insdc.org/policy/", "the policy of the nucleotide sequence databases, which covers the sequence records read")
    # The catalogue of about 10,000 proteins: read, and not copied.
    add("spectral_library_europepmc.json", f"{EPMC}/search?query={q('ext_id:40961932 AND src:med')}&format=json&resultType=core", "the paper that reports a spectral library of about 10,000 planarian proteins")
    add("spectral_library_crossref.json", "https://api.crossref.org/works/10.1016/j.devcel.2025.08.015", "that paper's licence and copyright statement")
    add("spectral_library_publisher_page.html", "https://www.cell.com/developmental-cell/fulltext/S1534-5807(25)00536-2", "the paper's own page, where its supplementary tables are listed", refusal_expected=True)
    add("spectral_library_PXD042308.xml", "https://proteomecentral.proteomexchange.org/cgi/GetDataset?ID=PXD042308&outputMode=XML", "what the paper's public deposit holds")
    add("spectral_library_PXD059861.xml", "https://proteomecentral.proteomexchange.org/cgi/GetDataset?ID=PXD059861&outputMode=XML", "what the paper's second public deposit holds")
    for part, name in DEPOSIT_TABLES:
        add(f"spectral_library_iprox_{part}_{name}", f"http://download.iprox.org/IPX0006394000/{part}/{name}", "one of the six files of the deposit that are not instrument files, read to see whether it lists proteins")
    add("spectral_library_search_preprints.json", f"{EPMC}/search?query={q('SRC:PPR AND (planarian OR "Schmidtea mediterranea") AND "spectral library"')}&format=json&resultType=lite&pageSize=25", "whether a preprint reports the library")
    add("spectral_library_search_datacite.json", "https://api.datacite.org/dois?query=" + q('"Schmidtea mediterranea" AND (proteome OR proteomic OR proteomics OR "mass spectrometry" OR "spectral library") AND NOT publisher:"The Global Biodiversity Information Facility"') + "&page%5Bsize%5D=100", "whether a data repository holds a record of the library")
    add("spectral_library_proteomexchange_species.json", "https://proteomecentral.proteomexchange.org/api/proxi/v0.1/datasets?species=Schmidtea%20mediterranea&resultType=compact&pageSize=50", "every ProteomeXchange dataset of the species")
    add("spectral_library_GSE232894.txt", "https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE232894&targ=self&form=text&view=brief", "the record of the same study's RNA-seq deposit")
    add("spectral_library_GSE232894_TPM.csv.gz", "https://ftp.ncbi.nlm.nih.gov/geo/series/GSE232nnn/GSE232894/suppl/GSE232894_fuzhao_TPM_gene.matrix.csv.gz", "the same study's RNA-seq table, read only for the kind of gene identifier the study uses")
    add("terms_planmine_front_page.html", "http://planmine.mpinat.mpg.de/planmine/begin.do", "PlanMine's front page, read for terms of use")
    return out


def load_manifest(evidence):
    path = evidence / "requests.json"
    if not path.exists():
        return {"client": CLIENT, "note": "Every response the planarian atlas is built from: what was asked, when, and what came back.", "requests": []}
    return json.loads(path.read_text(encoding="utf-8"))


def fetch(evidence, snapshot, refresh=False, pause=0.5, tries=5):
    """Ask every request not yet answered, save the body as it came, and note it."""
    responses = evidence / "responses"
    responses.mkdir(parents=True, exist_ok=True)
    manifest = load_manifest(evidence)
    done = {item["name"]: item for item in manifest["requests"]}
    asked = failed = 0
    for request in requests(snapshot):
        old = done.get(request["name"])
        target = responses / request["name"]
        if old and old["url"] == request["url"] and not refresh and ((old["status"] == 200 and target.exists()) or (request.get("refusal_expected") and old["status"] in (401, 403))):
            continue
        record = dict(request)
        call = urllib.request.Request(request["url"], headers={"User-Agent": CLIENT, "Accept-Encoding": "identity"})
        for attempt in range(tries):
            record = dict(request, asked=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
            try:
                with urllib.request.urlopen(call, timeout=600) as answer:
                    body = answer.read()
                    record["status"] = answer.status
                    for header, key in [("X-Total-Results", "total_results"), ("X-UniProt-Release", "uniprot_release"), ("X-UniProt-Release-Date", "uniprot_release_date"), ("Last-Modified", "last_modified"), ("Content-Type", "content_type")]:
                        if answer.headers.get(header):
                            record[key] = answer.headers[header]
                target.write_bytes(body)
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
                time.sleep(20)
        failed += record["status"] != 200 and not (request.get("refusal_expected") and record["status"] in (401, 403))
        done[request["name"]] = record
        asked += 1
        print(f"{record['status']}  {request['name']}  {record.get('bytes', '')}", flush=True)
        manifest["requests"] = [done[name] for name in sorted(done)]
        (evidence / "requests.json").write_text(json.dumps(manifest, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
        time.sleep(pause)
    print(f"asked {asked} request(s), {failed} failed; {len(done)} on record in {evidence / 'requests.json'}")
    return failed


# ---------------------------------------------------------------------------------------
# What is looked for: the family behind each unit, by its InterPro signature
# ---------------------------------------------------------------------------------------
#
# Each family is marked by one or two InterPro entries that the unit's human candidates
# carry (the build checks that they do). "second" signatures are asked only as a cross-check
# when the first finds nothing. "without" drops the models that carry a narrower mark.

FAMILIES = {
    "nav_alpha": {"name": "Voltage-gated sodium channel alpha subunit", "signatures": ["IPR001696"]},
    "nav_beta": {"name": "Sodium channel beta subunit", "signatures": ["IPR027098", "IPR000920"]},
    "kv1": {"name": "Kv1-type voltage-gated potassium channel", "signatures": ["IPR003972"]},
    "kv2": {"name": "Kv2-type voltage-gated potassium channel", "signatures": ["IPR003973"]},
    "kv3": {"name": "Kv3-type voltage-gated potassium channel", "signatures": ["IPR003974"]},
    "kv4": {"name": "Kv4-type voltage-gated potassium channel", "signatures": ["IPR003975"]},
    "kv_beta": {"name": "Potassium channel Kv-beta subunit", "signatures": ["IPR005983"]},
    "kir": {"name": "Inward-rectifier potassium channel", "signatures": ["IPR016449"], "second": ["IPR040445", "IPR041647"]},
    "hcn": {"name": "HCN-type channel", "signatures": ["IPR051413"], "second": ["IPR013621"]},
    "cav_l": {"name": "L-type calcium channel alpha-1 subunit", "signatures": ["IPR005446"]},
    "cav_hva": {"name": "Calcium channel alpha-1 subunit", "signatures": ["IPR002077"], "without": ["IPR005445"]},
    "cav2": {"name": "Calcium channel alpha-1 subunit", "signatures": ["IPR002077"], "without": ["IPR005445", "IPR005446"]},
    "cav_t": {"name": "T-type calcium channel alpha-1 subunit", "signatures": ["IPR005445"]},
    "cav_beta": {"name": "Calcium channel beta subunit", "signatures": ["IPR000584"]},
    "cav_a2d": {"name": "Calcium channel alpha-2/delta subunit", "signatures": ["IPR051173", "IPR013680"]},
    "bk": {"name": "BK (Slowpoke-like) calcium-activated potassium channel", "signatures": ["IPR047871"]},
    "sk": {"name": "SK calcium-activated potassium channel", "signatures": ["IPR015449"]},
    "bk_beta": {"name": "BK channel beta subunit", "signatures": ["IPR003930"]},
    "connexin": {"name": "Connexin", "signatures": ["IPR000500"], "second": ["IPR013092"]},
    "innexin": {"name": "Innexin", "signatures": ["IPR000990"], "human": False},
    "nka_alpha": {"name": "P-type ATPase IIC alpha subunit", "signatures": ["IPR005775"]},
    "nka_beta": {"name": "Sodium-potassium pump beta subunit", "signatures": ["IPR000402"]},
    "fxyd": {"name": "FXYD regulator", "signatures": ["IPR000272"]},
    "pmca": {"name": "Plasma-membrane calcium pump", "signatures": ["IPR006408"]},
    "serca": {"name": "SERCA-type calcium pump", "signatures": ["IPR005782"]},
    "ncx": {"name": "Sodium-calcium exchanger", "signatures": ["IPR004836"]},
    "ip3r": {"name": "Inositol trisphosphate receptor", "signatures": ["IPR000493"]},
    "ryr": {"name": "Ryanodine receptor", "signatures": ["IPR013333"]},
    "kcc": {"name": "Potassium-chloride cotransporter", "signatures": ["IPR000076"]},
    "nkcc": {"name": "Sodium-potassium-chloride cotransporter", "signatures": ["IPR002443"]},
    "slc12": {"name": "SLC12 family transporter", "signatures": ["IPR004842"]},
    "mcu": {"name": "Mitochondrial calcium uniporter", "signatures": ["IPR039055", "IPR006769"]},
    "emre": {"name": "Essential MCU regulator (EMRE)", "signatures": ["IPR018782"]},
    "micu": {"name": "Mitochondrial calcium uptake protein (MICU)", "signatures": ["IPR039800"]},
    # Not families of any unit's candidates: planarian proteins that bear on what is drawn.
    "aquaporin": {"name": "Aquaporin-family channel (major intrinsic protein)", "signatures": ["IPR000425"], "human": False},
    "k2p": {"name": "Two-pore-domain potassium channel", "signatures": ["IPR003280"], "human": False},
}

NAV = [("alpha", "nav_alpha"), ("beta", "nav_beta")]
KV1 = [("alpha", "kv1"), ("Kv-beta", "kv_beta")]
CAV_AUX = [("beta", "cav_beta"), ("alpha2delta", "cav_a2d")]
NOTHING_TO_LOOK_FOR = "nothing to look for"

# For each unit: the parts searched (role, family), and the short human name its note uses.
UNITS = {
    "U01": {"parts": NAV, "as": "NaV1.2", "note": "nav"},
    "U02": {"parts": NAV, "as": "NaV1.3", "note": "nav"},
    "U03": {"parts": NAV, "as": "NaV1.6", "note": "nav"},
    "U04": {"parts": NAV, "as": "the unnamed neuronal sodium channel", "note": "nav"},
    "U05": {"parts": KV1, "as": "Kv1.1", "note": "kv1"},
    "U06": {"parts": KV1, "as": "Kv1.2", "note": "kv1"},
    "U07": {"parts": KV1, "as": "Kv1.3", "note": "kv1"},
    "U08": {"parts": KV1, "as": "Kv1.4", "note": "kv1"},
    "U09": {"parts": KV1, "as": "Kv1.5", "note": "kv1"},
    "U10": {"parts": KV1, "as": "Kv1.6", "note": "kv1"},
    "U11": {"parts": [("alpha", "kv2")], "as": "Kv2.1", "note": "kv2"},
    "U12": {"parts": [("alpha", "kv2")], "as": "Kv2.2", "note": "kv2"},
    "U13": {"parts": [("alpha", "kv3")], "as": "Kv3.1", "note": "kv3"},
    "U14": {"parts": [("alpha", "kv3")], "as": "Kv3.2", "note": "kv3"},
    "U15": {"parts": [("alpha", "kv3")], "as": "Kv3.3", "note": "kv3"},
    "U16": {"parts": [("alpha", "kv3")], "as": "Kv3.4", "note": "kv3"},
    "U17": {"parts": [("alpha", "kv4")], "note": "kv4"},
    "U18": {"finding": NOTHING_TO_LOOK_FOR, "note": "The inventory gives this unit no gene product: it is a default shape of current, not a named channel. Planarian candidates for voltage-gated potassium channels are listed under the Kv units."},
    "U19": {"parts": [("alpha", "kir")], "as": "Kir2.1", "note": "kir"},
    "U20": {"parts": [("alpha", "hcn")], "as": "HCN1", "note": "hcn"},
    "U21": {"parts": [("alpha", "hcn")], "as": "HCN2", "note": "hcn"},
    "U22": {"parts": [("alpha", "hcn")], "as": "HCN4", "note": "hcn"},
    "U23": {"parts": [("alpha", "hcn")], "note": "hcn_leak"},
    "U24": {"parts": [("alpha1", "cav_l")] + CAV_AUX, "as": "CaV1.2", "note": "cav_l"},
    "U25": {"parts": [("alpha1", "cav_l")] + CAV_AUX, "as": "CaV1.3", "note": "cav_l"},
    "U26": {"parts": [("alpha1", "cav_l")] + CAV_AUX, "as": "the channel behind this L-type current", "note": "cav_l"},
    "U27": {"parts": [("alpha1", "cav_hva")] + CAV_AUX, "note": "cav_hva"},
    "U28": {"parts": [("alpha1", "cav2")] + CAV_AUX, "as": "CaV2.1", "note": "cav2"},
    "U29": {"parts": [("alpha1", "cav2")] + CAV_AUX, "as": "CaV2.2", "note": "cav2"},
    "U30": {"parts": [("alpha1", "cav2")] + CAV_AUX, "as": "CaV2.3", "note": "cav2"},
    "U31": {"parts": [("alpha1", "cav_t")], "as": "CaV3.1", "note": "cav_t"},
    "U32": {"parts": [("alpha1", "cav_t")], "as": "CaV3.3", "note": "cav_t"},
    "U33": {"parts": [("alpha (BK)", "bk"), ("alpha (SK)", "sk"), ("beta (BK)", "bk_beta")], "note": "kca"},
    "U34": {"finding": NOTHING_TO_LOOK_FOR, "note": "A background conductance that the inventory ties to no protein. Planarian two-pore-domain potassium channels, a usual molecular basis of a potassium leak, are noted under extra."},
    "U35": {"finding": NOTHING_TO_LOOK_FOR, "note": "A lumped permeability of the whole membrane, not a population of proteins."},
    "U36": {"parts": [("innexin", "innexin")], "replaces": "connexin", "note": "gap_generic"},
    "U37": {"parts": [("innexin", "innexin")], "replaces": "connexin", "as": "connexin 45", "note": "gap_named"},
    "U38": {"parts": [("innexin", "innexin")], "replaces": "connexin", "as": "connexin 40 or connexin 37", "note": "gap_named"},
    "U39": {"parts": [("alpha", "nka_alpha"), ("beta", "nka_beta"), ("FXYD", "fxyd")], "note": "nka"},
    "U40": {"parts": [("catalytic", "pmca")], "note": "pmca"},
    "U41": {"parts": [("catalytic", "serca")], "note": "serca"},
    "U42": {"parts": [("exchanger", "ncx")], "note": "ncx"},
    "U43": {"parts": [("IP3R", "ip3r"), ("RyR", "ryr")], "note": "release"},
    "U44": {"parts": [("KCC", "kcc")], "note": "kcc"},
    "U45": {"parts": [("NKCC", "nkcc")], "note": "nkcc"},
    "U46": {"finding": NOTHING_TO_LOOK_FOR, "note": "A slot that each model configuration fills with a transporter of its own; it has no fixed protein in any species."},
    "U47": {"parts": [("MCU", "mcu"), ("EMRE", "emre"), ("MICU", "micu")], "note": "mcu"},
    "U48": {"finding": NOTHING_TO_LOOK_FOR, "note": "A protein cage designed in the laboratory, with no gene in any animal, so there is nothing to look for in a planarian."},
    "U49": {"finding": NOTHING_TO_LOOK_FOR, "note": "A lumped water permeability of the membrane; water channels (aquaporins) are not part of it. Planarian aquaporin-family gene models are noted under extra."},
}

# Planarian proteins a paper names. A claim holds only if the saved abstract or the saved
# open-access text of the paper contains the words given; the build checks each one.
NAMED = {
    # UniProt calls this entry "Innexin", gene inx. Its sequence record belongs to the paper
    # and carries the paper's name, misspelt.
    "A7RDN9": {"family": "innexin", "gene": "smedinx-11", "pmid": "17670787", "words": "smedinx-11", "text": "abstract", "record": {"embl": "DQ851133", "words": "smedxin-11"}},
    "A0A0A1CVW3": {"family": "nav_alpha", "gene": "scna-1", "pmid": "25356635", "words": "sodium channel (scna-1)", "text": "PMC4214590"},
    "A0A0A1CQM0": {"family": "nav_alpha", "gene": "scna-2", "pmid": "25356635", "words": "sodium channel (scna-2)", "text": "PMC4214590"},
    "A0A0A1CRL5": {"family": "nav_alpha", "gene": "scna-3", "pmid": "25356635", "words": "sodium channel (scna-3)", "text": "PMC4214590"},
}
# Named by a paper as something other than the unit's own family: listed by signature, with
# the paper's name said in the evidence note (checked the same way).
CALLED = {
    "A0A1Z1R0Y6": {"called": "CNG1, a cyclic-nucleotide-gated channel", "pmid": "27612384", "words": "CNG1", "text": "PMC5055394"},
    "A0A0H3YK51": {"called": "slc12a-4", "pmid": "26057828", "words": "slc12a-4", "text": "PMC4500094"},
}
# Planarian proteins that bear on what the atlas draws but match no unit.
EXTRA = [
    {"accession": "M4LUP7", "family": "nka_alpha", "gene": "ATP12A", "role": "alpha", "pmid": "23250205", "words": "H(+),K(+)-ATPase", "text": "abstract",
     "record": {"embl": "JX174182", "words": "non-gastric H+,K+-ATPase alpha subunit (ATP12A)"},
     "name": "Non-gastric proton-potassium pump (H+/K+-ATPase) alpha subunit",
     "why": "A proton-potassium pump of the planarian membrane: the paper that reports it found that knocking it down changes membrane voltage and the size of the regrown head. It carries the same signature as the sodium-potassium pump's alpha subunit but was described as a different pump, so it is kept out of that unit."},
    {"accession": "A0A291IA19", "gene": "TRPA1", "role": None, "pmid": "29184198", "words": "TRPA1", "text": "abstract", "title_match": True,
     "name": "TRPA1 cation channel",
     "why": "A sensory cation channel of the planarian, shown to be needed for its escape from heat and irritants; the atlas draws no unit of this family."},
    {"accession": "A0A0A1CVW0", "family": "k2p", "gene": "kcnka", "role": None,
     "why": "A two-pore-domain potassium channel, the kind of protein that usually carries a potassium leak; the atlas's leak units name no protein. {k2p} planarian gene models carry this signature; the reference table lists them."},
    {"family": "aquaporin", "models": True, "role": None,
     "why": "An aquaporin-family gene model: the kind of water channel that the lumped water-permeability unit does not represent."},
]
SET_ASIDE = {"M4LUP7": "nka_alpha"}  # described as another pump than the unit's (see EXTRA)
FULL_TEXTS = {"PMC4214590": "25356635", "PMC5055394": "27612384", "PMC4500094": "26057828"}
# Papers whose records are kept: those behind the products, the two families of gap
# junctions, the genome annotation, and the catalogue that was not copied.
PAPERS = {
    "gap_families": "22366062", "gap_planarian": "17670787", "gap_review": "22450236",
    "genome": "39294119", "spectral_library": "40961932",
    "inx13": "22385657", "inx1": "22549959", "slc": "26057828", "coe": "25356635", "brain": "27612384", "hk": "23250205", "trpa1": "29184198",
    "uniprot": "39552041", "wbps": "27899279", "interpro": "39565202", "planmine": "30496475",
}
# The files of the paper's public deposit that are not instrument files.
DEPOSIT_TABLES = [
    ("IPX0006394001", "RESULT.xlsx"), ("IPX0006394002", "ResultTMT.xlsx"), ("IPX0006394003", "ResultWBRPDIA.xlsx"),
    ("IPX0006394004", "F20200519yingy_PulseDIA.csv"), ("IPX0006394005", "Results.xlsx"), ("IPX0006394006", "ResultMRM.xlsx"),
]
REFERENCE_FILE = "reference_proteins.tsv"
MATCH_WORD = 8      # residues in a word when a named sequence is compared with gene models
MATCH_SHARE = 0.8   # share of the sequence's words a gene model must contain
MATCH_MARGIN = 0.5  # and no other gene may reach this fraction of the best share


def rule_signatures():
    out = []
    for family in FAMILIES.values():
        for signature in family["signatures"] + family.get("second", []) + family.get("without", []):
            if signature not in out:
                out.append(signature)
    return sorted(out)


def cited_pmids():
    return set(PAPERS.values()) | {item["pmid"] for item in list(NAMED.values()) + list(CALLED.values()) + EXTRA if item.get("pmid")}


# ---------------------------------------------------------------------------------------
# Build: read the saved responses
# ---------------------------------------------------------------------------------------

class Evidence:
    """The saved responses, read through the record of what was asked."""

    def __init__(self, folder):
        self.folder = Path(folder)
        self.records = {item["name"]: item for item in load_manifest(self.folder)["requests"]}

    def record(self, name):
        record = self.records.get(name)
        if not record or record.get("status") != 200 or not (self.folder / "responses" / name).exists():
            raise SystemExit(f"no saved response {name!r}; run the fetch step first")
        return record

    def path(self, name):
        self.record(name)
        return self.folder / "responses" / name

    def text(self, name):
        return self.path(name).read_text(encoding="utf-8", errors="replace")

    def json(self, name):
        return json.loads(self.text(name))

    def total(self, name):
        return int(self.record(name)["total_results"])

    def day(self, name):
        return self.record(name)["asked"][:10]

    def last_day(self):
        return max(item["asked"][:10] for item in self.records.values())

    def refused(self, name):
        """The status and day of a request that the site did not answer with the page."""
        record = self.records.get(name)
        if not record or record["status"] == 200:
            raise SystemExit(f"{name!r} is on record as answered, or not on record; read it and rewrite what is said of it")
        return record["status"], record["asked"][:10]


def plain(markup):
    """Markup as running text, for looking up words in an abstract or an article."""
    import html

    return re.sub(r"\s+", " ", html.unescape(re.sub(r"(?s)<[^>]+>", " ", markup))).strip()


def natural(identifier):
    return [int(part) if part.isdigit() else part for part in re.split(r"(\d+)", identifier)]


def read_models(evidence):
    """The gene models of the annotation: predicted proteins, and the signatures on each."""
    proteins, name = {}, None
    with gzip.open(evidence.path("wbps_s3h1_protein.fa.gz"), "rt", encoding="ascii") as handle:
        for line in handle:
            if line.startswith(">"):
                fields = line[1:].split()
                name = fields[0]
                gene = next(field.split("=", 1)[1] for field in fields if field.startswith("gene="))
                proteins[name] = {"gene": gene, "sequence": []}
            else:
                proteins[name]["sequence"].append(line.strip())
    for protein in proteins.values():
        protein["sequence"] = "".join(protein["sequence"])
    names, biotypes = {}, Counter()
    with gzip.open(evidence.path("wbps_s3h1_annotations.gff3.gz"), "rt", encoding="utf-8") as handle:
        for line in handle:
            if line.startswith("#"):
                continue
            columns = line.rstrip("\n").split("\t")
            if len(columns) < 9 or columns[2] not in ("gene", "mRNA"):
                continue
            attributes = dict(item.split("=", 1) for item in columns[8].split(";") if "=" in item)
            if columns[2] == "gene":
                biotypes[attributes.get("biotype", "")] += 1
                continue
            protein = proteins.get(attributes["ID"].replace("transcript:", ""))
            if protein is None:
                continue
            found = re.findall(r"method:InterPro accession:(IPR\d+) description:([^\n]*)", urllib.parse.unquote(attributes.get("info", "")))
            protein["interpro"] = sorted({accession for accession, _ in found})
            for accession, description in found:
                names[accession] = description.strip()
    genes = defaultdict(lambda: {"proteins": [], "interpro": set()})
    for name in sorted(proteins, key=natural):
        gene = genes[proteins[name]["gene"]]
        gene["proteins"].append(name)
        gene["interpro"].update(proteins[name].get("interpro", []))
    for gene in genes.values():
        # The longest predicted protein stands for the gene; the first of equals.
        gene["protein"] = max(gene["proteins"], key=lambda name: len(proteins[name]["sequence"]))
        gene["length"] = len(proteins[gene["protein"]]["sequence"])
    return proteins, dict(genes), names, biotypes


def read_entry_names(evidence):
    entries = {}
    for line in evidence.text("interpro_entry_list.tsv").splitlines()[1:]:
        columns = line.split("\t")
        if len(columns) >= 3:
            entries[columns[0]] = {"type": columns[1], "name": columns[2]}
    return entries


def read_entries(evidence):
    """The species' UniProtKB entries, with what each needs for the atlas."""
    entries = {}
    for item in evidence.json(f"uniprotkb_{TAXON}.json")["results"]:
        description = item["proteinDescription"]
        named = description.get("recommendedName") or (description.get("submissionNames") or [{}])[0]
        cross = defaultdict(list)
        for reference in item.get("uniProtKBCrossReferences", []):
            cross[reference["database"]].append(reference["id"])
        genes = []
        for gene in item.get("genes", []):
            genes += [gene[key]["value"] for key in ("geneName",) if key in gene]
            genes += [other["value"] for key in ("synonyms", "orfNames", "orderedLocusNames") for other in gene.get(key, [])]
        papers, titles = [], []
        for reference in item.get("references", []):
            citation = reference.get("citation", {})
            titles.append(citation.get("title", ""))
            papers += [link["id"] for link in citation.get("citationCrossReferences", []) if link["database"] == "PubMed"]
        entries[item["primaryAccession"]] = {
            "reviewed": item["entryType"].startswith("UniProtKB reviewed"),
            "name": named.get("fullName", {}).get("value", ""),
            "genes": genes,
            "length": item["sequence"]["length"],
            "sequence": item["sequence"]["value"],
            "existence": item.get("proteinExistence", "").split(": ", 1)[-1],
            "interpro": sorted(cross["InterPro"]),
            "pmids": papers,
            "titles": titles,
        }
    return entries


def read_humans(evidence):
    return {
        item["primaryAccession"]: {reference["id"] for reference in item.get("uniProtKBCrossReferences", []) if reference["database"] == "InterPro"}
        for item in evidence.json("uniprotkb_human_candidates.json")["results"]
    }


def read_archive(evidence, proteins):
    """For each family signature: the gene models whose predicted protein is, letter for
    letter, a sequence of UniProt's archive that carries the signature there."""
    by_sequence = defaultdict(list)
    for name, protein in proteins.items():
        by_sequence[protein["sequence"]].append(name)
    out = {}
    for signature in rule_signatures():
        rows = evidence.text(f"uniparc_{signature}_{TAXON}.tsv").splitlines()
        header = rows[0].split("\t") if rows else []
        hits = set()
        for row in rows[1:]:
            record = dict(zip(header, row.split("\t")))
            hits.update(by_sequence.get(record.get("Sequence", ""), []))
        out[signature] = {"sequences": max(0, len(rows) - 1), "proteins": hits}
    return out


def read_links(evidence):
    """The sequence records each of a few UniProtKB entries was made from."""
    return {
        item["primaryAccession"]: {reference["id"] for reference in item.get("uniProtKBCrossReferences", []) if reference["database"] == "EMBL"}
        for item in evidence.json("uniprotkb_record_links.json")["results"]
    }


def read_papers(evidence):
    """The cited papers: a citation each, and the texts in which names are looked up."""
    papers = {}
    for item in evidence.json("europepmc_citations.json")["resultList"]["result"]:
        journal = item.get("journalInfo", {})
        authors = [author.get("lastName") or author.get("collectiveName") or "" for author in item.get("authorList", {}).get("author", [])]
        if len(authors) > 2:
            who = f"{authors[0]} and others"
        else:
            who = " and ".join(authors)
        title = plain(item.get("title", "")).rstrip(".")
        where = journal.get("journal", {}).get("medlineAbbreviation") or journal.get("journal", {}).get("title") or ""
        place = ":".join(part for part in (str(journal.get("volume") or ""), item.get("pageInfo") or "") if part)
        year = item.get("pubYear", "")
        papers[item["pmid"]] = {
            "authors": (item.get("authorString") or "").rstrip("."),
            "citation": {"text": f"{who} ({year}) {title}. {where} {place}".strip() + ".", "doi": item.get("doi"), "pmid": item["pmid"]},
            "short": f"{who} {year}",
            "title": title,
            "abstract": plain(item.get("abstractText") or ""),
            "licence": item.get("license"),
        }
    missing = sorted(cited_pmids() - set(papers), key=int)
    if missing:
        raise SystemExit(f"the saved paper records lack PubMed ids {missing}")
    texts = {pmcid: plain(evidence.text(f"europepmc_fulltext_{pmcid}.xml")) for pmcid in FULL_TEXTS}
    return papers, texts


# ---------------------------------------------------------------------------------------
# Build: find the candidates
# ---------------------------------------------------------------------------------------

def match_entries(entries, proteins):
    """Join a UniProtKB sequence to the gene model it is a copy of: the gene whose
    predicted protein contains most of the sequence's words, when no other comes close."""
    words, size = defaultdict(list), {}
    for accession in sorted(entries):
        sequence = entries[accession]["sequence"]
        own = {sequence[i : i + MATCH_WORD] for i in range(len(sequence) - MATCH_WORD + 1)}
        if len(own) < 20:
            continue
        size[accession] = len(own)
        for word in own:
            words[word].append(accession)
    shared = defaultdict(Counter)
    for name, protein in proteins.items():
        sequence, seen = protein["sequence"], set()
        for i in range(len(sequence) - MATCH_WORD + 1):
            word = sequence[i : i + MATCH_WORD]
            if word in words and word not in seen:
                seen.add(word)
                for accession in words[word]:
                    shared[accession][protein["gene"], name] += 1
    out = {}
    for accession in sorted(shared):
        by_gene = Counter()
        for (gene, _), count in shared[accession].items():
            by_gene[gene] = max(by_gene[gene], count)
        ranked = sorted(by_gene.items(), key=lambda item: (-item[1], natural(item[0])))
        share = ranked[0][1] / size[accession]
        runner = ranked[1][1] / size[accession] if len(ranked) > 1 else 0.0
        if share >= MATCH_SHARE and runner <= MATCH_MARGIN * share:
            out[accession] = {"gene": ranked[0][0], "share": share}
    return out


class Context:
    """Everything the build read, and the questions asked of it."""

    def __init__(self, evidence, snapshot):
        self.evidence = evidence
        self.snapshot = snapshot
        self.proteins, self.genes, annotation_names, self.biotypes = read_models(evidence)
        self.entry_names = read_entry_names(evidence)
        self.old_names = annotation_names
        self.entries = read_entries(evidence)
        self.humans = read_humans(evidence)
        self.archive = read_archive(evidence, self.proteins)
        self.papers, self.texts = read_papers(evidence)
        self.links = read_links(evidence)
        self.matches = match_entries(self.entries, self.proteins)
        # Which predicted proteins of each gene model carry each family signature, and by
        # which of the two records: the genome annotation's own matches, or UniProt's archive.
        self.marks = defaultdict(lambda: defaultdict(lambda: defaultdict(set)))
        wanted = set(rule_signatures())
        for name, protein in self.proteins.items():
            for signature in wanted.intersection(protein.get("interpro", [])):
                self.marks[protein["gene"]][signature]["annotation"].add(name)
        for signature, found in self.archive.items():
            for name in found["proteins"]:
                self.marks[self.proteins[name]["gene"]][signature]["archive"].add(name)
        self._products = {}
        self.check_rules()

    # --- names and checks -------------------------------------------------------------

    def signature_name(self, signature):
        if signature in self.entry_names:
            return self.entry_names[signature]["name"]
        return self.old_names[signature]

    def check_rules(self):
        """Each family signature must be one the unit's own human candidates carry."""
        human_of = {unit["id"]: [p["human_uniprot"] for p in unit.get("products") or [] if p.get("human_uniprot")] for unit in self.snapshot["units"]}
        for unit_id, spec in UNITS.items():
            for _, key in spec.get("parts", []):
                family = FAMILIES[key]
                if family.get("human") is False:
                    continue
                carried = set().union(*(self.humans[accession] for accession in human_of[unit_id]))
                missing = [s for s in family["signatures"] + family.get("second", []) if s not in carried]
                if missing:
                    raise SystemExit(f"{unit_id}: no human candidate of the unit carries {missing} (family {key})")
        unknown = sorted(set(UNITS) ^ {unit["id"] for unit in self.snapshot["units"]})
        if unknown:
            raise SystemExit(f"the units of the snapshot and of this tool differ: {unknown}")

    def said(self, claim, accession=None):
        """True when the paper's saved abstract or text holds the words of a claim, and,
        for a claim about an entry, when the entry is tied to that paper."""
        text = self.papers[claim["pmid"]]["abstract"] if claim["text"] == "abstract" else self.texts[claim["text"]]
        if claim["words"] not in text:
            raise SystemExit(f"the saved {claim['text']} of PubMed {claim['pmid']} does not contain {claim['words']!r}")
        if accession and not claim.get("title_match") and claim["pmid"] not in self.entries[accession]["pmids"]:
            raise SystemExit(f"{accession} does not cite PubMed {claim['pmid']}")
        if accession and claim.get("record"):
            self.recorded(claim, accession)
        return True

    def recorded(self, claim, accession):
        """The entry's own sequence record: it must be the entry's, of this species, of the
        claimed paper, and carry the words given."""
        record = claim["record"]
        if record["embl"] not in self.links.get(accession, ()):
            raise SystemExit(f"{accession} was not made from the sequence record {record['embl']}")
        lines = self.evidence.text(f"ena_{record['embl']}.txt").splitlines()
        title = " ".join(line[5:] for line in lines if line.startswith("DE   "))
        if record["words"] not in title or f"OS   {ORGANISM}" not in lines or f"RX   PUBMED; {claim['pmid']}." not in lines:
            raise SystemExit(f"the sequence record {record['embl']} no longer says what is claimed of it")
        return record

    # --- candidates -------------------------------------------------------------------

    def models(self, key):
        """Gene models of a family: {gene: (signature, the records that show it, the
        longest predicted protein that carries it)}."""
        family, out = FAMILIES[key], {}
        for gene_id, marks in self.marks.items():
            first = next((s for s in family["signatures"] if s in marks), None)
            if first is None or any(s in marks for s in family.get("without", [])):
                continue
            carriers = sorted(set().union(*marks[first].values()), key=natural)
            out[gene_id] = (first, set(marks[first]), max(carriers, key=lambda name: len(self.proteins[name]["sequence"])))
        for accession, aside in SET_ASIDE.items():
            if aside == key and accession in self.matches:
                out.pop(self.matches[accession]["gene"], None)
        return out

    def listed(self, key):
        """UniProtKB entries of the species that carry a family's signature."""
        family, out = FAMILIES[key], {}
        for accession, entry in self.entries.items():
            if SET_ASIDE.get(accession) == key:
                continue
            first = next((s for s in family["signatures"] if s in entry["interpro"]), None)
            if first and not any(s in entry["interpro"] for s in family.get("without", [])):
                out[accession] = first
        return out

    def count(self, key):
        return len(self.models(key))

    def offside(self, key):
        """Gene models of a family whose signature is not on the gene's longest predicted protein."""
        return sorted((gene_id for gene_id, (_, _, name) in self.models(key).items() if name != self.genes[gene_id]["protein"]), key=natural)

    def control(self, signature):
        return {
            "archive": self.archive[signature]["sequences"],
            "flatworms": self.evidence.total(f"control_uniprotkb_{signature}_6157.json"),
            "human": self.evidence.total(f"control_uniprotkb_{signature}_9606.json"),
            "species": sum(1 for entry in self.entries.values() if signature in entry["interpro"]),
        }

    def absent(self, key):
        """The controls of a family that was not found; fails if it was found after all."""
        family = FAMILIES[key]
        signatures = family["signatures"] + family.get("second", [])
        controls = {signature: self.control(signature) for signature in signatures}
        if self.models(key) or self.listed(key) or any(c["archive"] or c["species"] for c in controls.values()):
            raise SystemExit(f"family {key} was found; its note says it was not")
        return controls

    def joined(self, accession):
        match = self.matches.get(accession)
        if not match:
            return [], ""
        return [{"db": "wormbase_parasite", "id": match["gene"]}], f"; matches gene model {match['gene']} ({round(match['share'] * 100)}% of its {MATCH_WORD}-residue words)"

    def products(self, key, role):
        """The products of a family: named in a paper, then other UniProtKB entries with
        the signature, then the gene models not already joined to one of those."""
        if (key, role) in self._products:
            return self._products[key, role]
        family, out, taken = FAMILIES[key], [], set()
        for accession in sorted((a for a, claim in NAMED.items() if claim["family"] == key), key=lambda a: natural(NAMED[a]["gene"])):
            claim, entry = NAMED[accession], self.entries[accession]
            self.said(claim, accession)
            paper = self.papers[claim["pmid"]]
            ids, tail = self.joined(accession)
            taken.update(item["id"] for item in ids)
            if claim.get("record"):
                # The entry does not carry the paper's name; its sequence record does.
                spelt = "" if claim["record"]["words"] == claim["gene"] else f", which spells it {claim['record']['words']}"
                tail = f"; the name is tied to this entry by its sequence record {claim['record']['embl']}{spelt}" + tail
            elif claim["gene"].lower() not in [name.lower() for name in entry["genes"]]:
                raise SystemExit(f"{accession} does not carry the name {claim['gene']}, and no sequence record ties it to the name")
            out.append({
                "name": entry["name"], "gene": claim["gene"], "role": role, "ids": [{"db": "uniprot", "id": accession}] + ids, "length": entry["length"],
                "evidence": "named in a publication", "evidence_note": f"Named {claim['gene']} in {paper['short']}{tail}.", "citation": paper["citation"],
            })
        listed = self.listed(key)
        for accession in sorted(listed):
            if NAMED.get(accession, {}).get("family") == key:
                continue
            entry, signature = self.entries[accession], listed[accession]
            note = f"{signature} ({self.signature_name(signature)}) on its UniProtKB entry"
            if accession in CALLED and self.said(CALLED[accession], accession):
                note += f"; called {CALLED[accession]['called']} in {self.papers[CALLED[accession]['pmid']]['short']}"
            elif entry["pmids"]:
                first = entry["pmids"][0]
                if first not in self.papers:
                    raise SystemExit(f"{accession} cites PubMed {first}, whose record is not saved; add it to PAPERS and fetch again")
                note += f"; its sequence was reported with {self.papers[first]['short']}"
            ids, tail = self.joined(accession)
            taken.update(item["id"] for item in ids)
            if ids and ids[0]["id"] not in self.models(key):
                tail += ", which does not carry the signature itself"
            out.append({
                "name": entry["name"], "gene": entry["genes"][0] if entry["genes"] else None, "role": role, "ids": [{"db": "uniprot", "id": accession}] + ids, "length": entry["length"],
                "evidence": "reviewed entry" if entry["reviewed"] else "family signature", "evidence_note": note + tail + ".", "citation": None,
            })
        models = self.models(key)
        own = set(listed) | {a for a, claim in NAMED.items() if claim["family"] == key}
        for gene_id in sorted(models, key=natural):
            if gene_id in taken:
                continue
            signature, where, name = models[gene_id]
            gene = self.genes[gene_id]
            note = f"{signature} ({self.signature_name(signature)}) on predicted protein {name}"
            note += "" if len(where) == 2 else (" (in the genome annotation only)" if "annotation" in where else " (in UniProt's archive only)")
            if name != gene["protein"]:
                note += f"; the gene's longest predicted protein, {gene['protein']} ({gene['length']:,} residues), does not carry it"
            # A copy of the gene in UniProtKB that lacks the signature is a reason for doubt, and is said.
            others = [a for a in sorted(self.matches) if self.matches[a]["gene"] == gene_id and a not in own and SET_ASIDE.get(a) != key]
            if others:
                called = ", ".join(f"{a} ({self.entries[a]['genes'][0] if self.entries[a]['genes'] else self.entries[a]['name']})" for a in others)
                note += f"; the gene model matches the UniProtKB {'entry' if len(others) == 1 else 'entries'} {called}, which {'does' if len(others) == 1 else 'do'} not carry the signature"
            out.append({
                "name": f"{family['name']}, gene model {gene_id}", "gene": None, "role": role, "ids": [{"db": "wormbase_parasite", "id": gene_id}], "length": len(self.proteins[name]["sequence"]),
                "evidence": "family signature", "evidence_note": note + ".", "citation": None,
            })
        self._products[key, role] = out
        return out

    # --- words for the notes ----------------------------------------------------------

    def carry(self, key):
        n = self.count(key)
        return "No planarian gene model carries" if n == 0 else "One planarian gene model carries" if n == 1 else f"{n} planarian gene models carry"

    def also(self, key):
        n = self.count(key)
        return "none carries" if n == 0 else "one carries" if n == 1 else f"{n} carry"

    def close(self, spec, key):
        if "as" not in spec:
            return ""
        if len(self.products(key, None)) == 1:
            return f"Nothing here says that it is the counterpart of {spec['as']}."
        return f"None can be singled out as the counterpart of {spec['as']}."

    def listed_clause(self, key):
        """The species' UniProtKB sequences that carry a family's signature, in words."""
        listed = self.listed(key)
        names = sorted({self.entries[a]["genes"][0] for a in listed if self.entries[a]["genes"]}, key=natural)
        if not listed or len(names) != len(listed):
            return ""
        if len(names) == 1:
            return f"; so does one planarian sequence in UniProtKB, submitted as {names[0]}"
        return f"; so do {len(names)} planarian sequences in UniProtKB, submitted as {names[0]} to {names[-1]}"

    def short(self, name):
        return self.papers[PAPERS[name]]["short"]


# ---------------------------------------------------------------------------------------
# Build: the notes, one plain statement per unit, with the numbers read from the evidence
# ---------------------------------------------------------------------------------------

def aux_calcium(c):
    return f"{c.also('cav_beta')} the signature of the beta subunit and {c.also('cav_a2d')} that of the alpha-2/delta subunit"


def note_nav(spec, c):
    named = sorted((claim["gene"] for claim in NAMED.values() if claim["family"] == "nav_alpha"), key=natural)
    years = sorted({c.papers[claim["pmid"]]["short"].rsplit(" ", 1)[1] for claim in NAMED.values() if claim["family"] == "nav_alpha"})
    beta = c.absent("nav_beta")
    joined = {c.matches[a]["gene"] for a, claim in NAMED.items() if claim["family"] == "nav_alpha" and a in c.matches}
    if not joined <= set(c.models("nav_alpha")):
        raise SystemExit("a named sodium channel sequence matches a gene model without the signature; rewrite the note")
    # "short": each named sequence is less than half as long as the gene model it matches.
    if any(2 * c.entries[a]["length"] >= c.genes[c.matches[a]["gene"]]["length"] for a, claim in NAMED.items() if claim["family"] == "nav_alpha"):
        raise SystemExit("a named sodium channel sequence is not short beside its gene model; rewrite the note")
    return (
        f"{c.carry('nav_alpha')} the signature of the sodium channel's pore subunit, and a {years[0]} paper named {len(named)} short planarian sequences as sodium channels ({named[0]} to {named[-1]}), which match {len(joined)} of those gene models. "
        f"{c.close(spec, 'nav_alpha') or 'Nothing here says which of them, if any, carries such a current.'} "
        f"No planarian sequence carries either signature of the beta subunits; they mark {sum(v['human'] for v in beta.values())} reviewed human entries."
    )


def note_kir(spec, c):
    controls = c.absent("kir")
    first = controls[FAMILIES["kir"]["signatures"][0]]
    return (
        "No planarian sequence carries the signature of inward-rectifier potassium channels: no gene model, no UniProtKB entry of the species, and none of the planarian sequences in UniProt's archive, "
        f"for this signature or for {len(controls) - 1} others of the family. The same search finds the family in {first['flatworms']} UniProtKB entries of other flatworms and in {first['human']} reviewed human entries, so the search can find it where it exists."
    )


def note_hcn(spec, c, closing=None):
    called = [accession for accession in c.listed("hcn") if accession in CALLED]
    aside = ""
    if called:
        c.said(CALLED[called[0]])
        aside = f" One of them matches a planarian protein that the paper reporting it calls {CALLED[called[0]]['called']}: the signature and the published name point to related but different kinds of channel."
    return f"{c.carry('hcn')} the signature of hyperpolarization-activated (HCN) channels.{aside} {closing or c.close(spec, 'hcn')}"


def note_gap(spec, c, named):
    families, planarian = c.papers[PAPERS["gap_families"]], c.papers[PAPERS["gap_planarian"]]
    for paper, words in ((families, "connexins are exclusive of chordates"), (planarian, "innexin gap junction channel gene")):
        if words not in paper["abstract"]:
            raise SystemExit(f"the saved abstract of {paper['short']} does not contain {words!r}")
    controls = c.absent("connexin")
    first = controls[FAMILIES["connexin"]["signatures"][0]]
    if first["flatworms"]:
        raise SystemExit("a flatworm entry carries the connexin signature; rewrite the gap-junction notes")
    basis = (
        f"Connexins are known only from chordates ({families['short']}), and a planarian innexin gap-junction gene, smedinx-11, has been described ({planarian['short']}). "
        f"{c.carry('innexin')} the innexin signature and none the connexin one; no UniProtKB entry of any flatworm carries the connexin signature either, while {first['human']} reviewed human entries do."
    )
    if named:
        return f"There is no {spec['as']} to find in a planarian: its gap junctions are built from innexins, a different protein family. {basis} Nothing says which innexins, if any, would form a channel like this one."
    return f"Planarians build gap junctions from innexins, not connexins. {basis} Which innexins a general gap-junction law would stand for is not known."


def note_nka(spec, c):
    fxyd = c.absent("fxyd")[FAMILIES["fxyd"]["signatures"][0]]
    if fxyd["flatworms"] or len(SET_ASIDE) != 1:
        raise SystemExit("the sodium-potassium pump note no longer fits the evidence; rewrite it")
    return (
        f"{c.carry('nka_alpha')} the signature of the pump's alpha subunit, and {c.also('nka_beta')} that of its beta subunit. "
        "The alpha signature is shared with proton-potassium pumps: one further planarian protein that carries it was described as such a pump and is listed under extra instead. "
        f"No planarian sequence carries the signature of the small FXYD regulators, which marks {fxyd['human']} reviewed human entries and no flatworm entry."
    )


def note_pmca(spec, c):
    partners = [p["human_uniprot"] for unit in c.snapshot["units"] if unit["id"] == "U40" for p in unit["products"] if p.get("role") == "partner"]
    for accession in partners:
        if any(c.entry_names.get(s, {}).get("type") == "Family" for s in c.humans[accession]):
            raise SystemExit(f"partner {accession} carries a family signature; search for it and rewrite the note")
    return (
        f"{c.carry('pmca')} the signature of plasma-membrane calcium pumps. Nothing here says which of them, if any, works at the outer membrane. "
        "The two partner proteins the inventory lists (neuroplastin and basigin) were not searched for: they carry only general immunoglobulin-domain signatures, which cannot mark a counterpart."
    )


def note_ncx(spec, c):
    return f"{c.carry('ncx')} the signature of sodium-calcium exchangers{c.listed_clause('ncx')}. Nothing here says which of them, if any, works at the outer membrane."


def note_kcc(spec, c):
    called = [a for a in c.listed("kcc") if a in CALLED]
    aside = f" It matches a planarian sequence called {CALLED[called[0]]['called']} in {c.papers[CALLED[called[0]]['pmid']]['short']}." if called and c.said(CALLED[called[0]]) else ""
    return f"{c.carry('kcc')} the signature of potassium-chloride cotransporters.{aside} Nothing here says whether it moves potassium and chloride as the unit does."


def note_nkcc(spec, c):
    control = c.absent("nkcc")[FAMILIES["nkcc"]["signatures"][0]]
    if control["flatworms"]:
        raise SystemExit("a flatworm entry carries the NKCC signature; rewrite the note")
    return (
        "No planarian sequence carries the signature of the sodium-potassium-chloride branch of this transporter family. "
        f"The same signature finds no UniProtKB entry of any flatworm and only {control['human']} reviewed human entries, so it may not recognise flatworm forms. "
        f"{c.carry('slc12')} the signature of the wider family (SLC12), of which {c.also('kcc')} the potassium-chloride signature; whether any of the others moves sodium, potassium and chloride together is not known from these sources."
    )


def note_mcu(spec, c):
    emre = c.control(FAMILIES["emre"]["signatures"][0])
    if c.count("emre") or not emre["archive"]:
        raise SystemExit("the uniporter note no longer fits the evidence; rewrite it")
    return (
        "The unit is a lumped leak of the inner mitochondrial membrane, and the only candidate the inventory names for it is the calcium uniporter. "
        f"Planarian gene models carry the signatures of two of its parts: {c.count('mcu')} that of the pore (MCU) and {c.count('micu')} that of MICU. "
        f"None carries that of the regulator EMRE, although {emre['archive']} planarian sequences from other annotation sets carry it in UniProt's archive."
    )


NOTES = {
    "nav": note_nav,
    "kv1": lambda s, c: f"{c.carry('kv1')} the signature of Kv1 (Shaker-type) potassium channels, and {c.also('kv_beta')} that of the Kv-beta partner subunit. {c.close(s, 'kv1')}",
    "kv2": lambda s, c: f"{c.carry('kv2')} the signature of Kv2 potassium channels{c.listed_clause('kv2')}. {c.close(s, 'kv2')}",
    "kv3": lambda s, c: f"{c.carry('kv3')} the signature of Kv3 potassium channels. {c.close(s, 'kv3')}",
    "kv4": lambda s, c: f"{c.carry('kv4')} the signature of Kv4 potassium channels, the family the inventory infers for this fast-inactivating current. Nothing here says whether any of them carries such a current.",
    "kir": note_kir,
    "hcn": note_hcn,
    "hcn_leak": lambda s, c: note_hcn(s, c, "The unit itself is an always-open leak with the ion preferences of an HCN channel; nothing here says a planarian protein behaves so."),
    "cav_l": lambda s, c: f"{c.carry('cav_l')} the signature of L-type calcium channel pore subunits; {aux_calcium(c)}. {c.close(s, 'cav_l')}",
    "cav_hva": lambda s, c: f"{c.carry('cav_hva')} the signature of calcium channel pore subunits without the T-type mark, which makes them candidates for a high-voltage-activated current; {aux_calcium(c)}. Nothing here says which of them carry such a current.",
    "cav2": lambda s, c: f"No signature marks the CaV2 group on its own. {c.carry('cav2')} the general signature of calcium channel pore subunits without the L-type or the T-type mark, which makes them the nearest candidates, not established counterparts of {s['as']}; {aux_calcium(c)}.",
    "cav_t": lambda s, c: f"{c.carry('cav_t')} the signature of T-type calcium channel pore subunits. {c.close(s, 'cav_t')}",
    "kca": lambda s, c: f"The unit does not say which of two channel families it means, and planarian gene models carry the signature of each: {c.count('bk')} that of the large-conductance (BK, Slowpoke-like) channels and {c.count('sk')} that of the small-conductance (SK) channels; {c.also('bk_beta')} the signature of the BK beta subunit.",
    "gap_generic": lambda s, c: note_gap(s, c, named=False),
    "gap_named": lambda s, c: note_gap(s, c, named=True),
    "nka": note_nka,
    "pmca": note_pmca,
    "serca": lambda s, c: f"{c.carry('serca')} the signature of SERCA-type calcium pumps. Nothing here says which of them, if any, fills the internal calcium store.",
    "ncx": note_ncx,
    "release": lambda s, c: f"The unit has two candidate families, and planarian gene models carry the signature of each: {c.count('ip3r')} that of inositol trisphosphate receptors and {c.count('ryr')} that of ryanodine receptors.",
    "kcc": note_kcc,
    "nkcc": note_nkcc,
    "mcu": note_mcu,
}
MAIN = {"U33": ["bk", "sk"], "U43": ["ip3r", "ryr"]}  # units with two candidate families


def unit_entry(unit_id, c):
    spec = UNITS[unit_id]
    if "finding" in spec:
        return {"finding": spec["finding"], "note": spec["note"], "products": []}
    main = MAIN.get(unit_id, [spec["parts"][0][1]])
    found = any(c.products(key, role) for role, key in spec["parts"] if key in main)
    note = " ".join(NOTES[spec["note"]](spec, c).split())
    offside = sorted({gene_id for _, key in spec["parts"] for gene_id in c.offside(key)})
    if offside:
        note += f" For {len(offside)} gene models the signature is on a shorter alternative protein of the gene, not on its longest." if len(offside) > 1 else " For one gene model the signature is on a shorter alternative protein of the gene, not on its longest."
    if not found:
        return {"finding": "none found", "note": note, "products": []}
    products, seen = [], set()
    for role, key in spec["parts"]:
        for product in c.products(key, role):
            identity = tuple((item["db"], item["id"]) for item in product["ids"])
            if identity not in seen:
                seen.add(identity)
                products.append(product)
    return {"finding": "different family" if spec.get("replaces") else "found", "note": note, "products": products}


def extra_products(c):
    out = []
    for item in EXTRA:
        if item.get("models"):
            for product in c.products(item["family"], item["role"]):
                out.append(dict(product, why=item["why"]))
            continue
        accession = item["accession"]
        entry = c.entries[accession]
        ids, tail = c.joined(accession)
        if item.get("pmid"):
            c.said(item, accession)
            paper = c.papers[item["pmid"]]
            if ORGANISM not in paper["abstract"] and item["pmid"] not in entry["pmids"]:
                raise SystemExit(f"nothing ties PubMed {item['pmid']} to {accession} in {ORGANISM}")
            if item.get("title_match") and not any(plain(title).rstrip(".").lower() == paper["title"].lower() for title in entry["titles"]):
                raise SystemExit(f"{accession} does not cite the paper titled {paper['title']!r}")
            evidence, citation = "named in a publication", paper["citation"]
            note = f"Reported in {paper['short']}"
            if item.get("record"):
                note += f"; its sequence record {item['record']['embl']} calls it the {item['record']['words']}"
            if item.get("family"):
                signature = FAMILIES[item["family"]]["signatures"][0]
                if signature not in entry["interpro"]:
                    raise SystemExit(f"{accession} does not carry {signature}")
                note += f"; carries {signature} ({c.signature_name(signature)})"
        else:
            signature = next(s for s in FAMILIES[item["family"]]["signatures"] if s in entry["interpro"])
            evidence, citation = "family signature", None
            note = f"{signature} ({c.signature_name(signature)}) on its UniProtKB entry"
            if entry["pmids"] and entry["pmids"][0] in c.papers:
                note += f"; its sequence was reported with {c.papers[entry['pmids'][0]]['short']}"
        out.append({
            "name": item.get("name") or entry["name"], "gene": item["gene"], "role": item["role"], "ids": [{"db": "uniprot", "id": accession}] + ids, "length": entry["length"],
            "evidence": evidence, "evidence_note": note + tail + ".", "citation": citation,
            "why": item["why"].format(k2p=c.count("k2p")),
        })
    return out


# ---------------------------------------------------------------------------------------
# Build: sources, terms and the three files
# ---------------------------------------------------------------------------------------

TERMS = [
    # (saved page, words it must contain): the terms the files state, as they were read.
    ("terms_uniprot_license.json", "Creative Commons Attribution 4.0 International (CC BY 4.0) License"),
    ("terms_wbps_disclaimer.html", "Ensembl imposes no restrictions on access to, or use of, the data provided"),
    ("terms_wbps_datausage.html", "Please cite the original paper for the genome publication"),
    ("terms_interpro_license.html", "CC0 1.0 Universal"),
    ("terms_embl_ebi.html", "EMBL-EBI imposes no additional restriction on the use of the contributed data than those provided by the data owner"),
    ("terms_europepmc_s3_genome_paper_fulltext.xml", "licensed under a Creative Commons Attribution 4.0 International License"),
    ("spectral_library_crossref.json", "All rights are reserved"),
    ("terms_insdc_policy.html", "no use restrictions or licensing requirements will be included in any sequence data records"),
    ("terms_iprox_data_licence.html", "Creative Commons Public Domain (CC0) license apply to all iProX datasets submitted since March 23rd, 2023"),
    ("terms_iprox_data_licence.html", "for use solely by you for your own personal use and not for republication"),
    ("spectral_library_europepmc.json", "10,000 proteins"),
]


def check_terms(evidence):
    for name, words in TERMS:
        if words not in plain(evidence.text(name)):
            raise SystemExit(f"the saved {name} no longer says {words!r}; read the terms again before building")
    planmine = plain(re.sub(r"(?is)<(script|style)\b.*?</\1>", " ", evidence.text("terms_planmine_front_page.html")))
    if re.search(r"licen[cs]e|terms of use|creative commons", planmine, re.I) or "To cite PlanMine" not in planmine:
        raise SystemExit("PlanMine's saved front page now speaks of terms; read them and rewrite what is said of it")


def species_facts(c):
    ev = c.evidence
    counts = {}
    for taxon in [TAXON, *OTHER_PLANARIANS]:
        stats = ev.json(f"uniprot_taxonomy_{taxon}.json")["statistics"]
        counts[taxon] = {"entries": stats["reviewedProteinCount"] + stats["unreviewedProteinCount"], "reviewed": stats["reviewedProteinCount"], "proteomes": stats["proteomeCount"]}
    if counts[TAXON]["entries"] != len(c.entries) or ev.json(f"uniprot_proteomes_{TAXON}.json")["results"]:
        raise SystemExit("UniProt's counts for the species and its saved entries disagree")
    order = ev.json(f"uniprot_taxonomy_{PLANARIANS}.json")["statistics"]
    order_entries = order["reviewedProteinCount"] + order["unreviewedProteinCount"]
    if 2 * counts[TAXON]["entries"] <= order_entries or order["proteomeCount"] or ev.json(f"uniprot_proteomes_{PLANARIANS}.json")["results"]:
        raise SystemExit("the species no longer holds most of UniProt's planarian entries, or a planarian proteome exists; choose the species again")
    page = plain(ev.text("wbps_species_s3h1.html"))
    found = re.search(r"Assembly (\S+) Strain (\S+) Database Version (\S+) .*?Annotation Version (\S+) Gene counts Coding genes ([\d,]+) Gene transcripts ([\d,]+)", page)
    if not found or found.group(3) != WBPS_RELEASE:
        raise SystemExit("WormBase ParaSite's page of the annotation is not the one this tool was written for")
    if sum(c.biotypes.values()) != int(found.group(5).replace(",", "")) or c.biotypes["protein_coding"] != len(c.genes):
        raise SystemExit("the gene counts of the annotation file and of WormBase ParaSite's page disagree")
    # Is this the annotation the genome paper describes? Neither says so; the counts are compared.
    paper = plain(ev.text("terms_europepmc_s3_genome_paper_fulltext.xml"))
    told = re.search(r"([\d,]+) and ([\d,]+) hconf gene loci in S3h1 and S3h2", paper)
    second = re.search(r"Gene counts Coding genes ([\d,]+)", plain(ev.text("wbps_species_s3h2.html")))
    projects = ev.json("ncbi_bioprojects_genome.json")["result"]
    listed = next(projects[uid] for uid in projects["uids"] if projects[uid]["project_acc"] == "PRJNA885486")
    if not told or not second or "PRJNA885486" not in page or "PRJNA885486" in paper or re.search(r"Publication|PubMed", page):
        raise SystemExit("what ties the gene models to the genome paper has changed; read both again and rewrite what is said of it")
    return {
        "counts": counts, "order_entries": order_entries,
        "paper_genes": [int(told.group(1).replace(",", "")), int(told.group(2).replace(",", ""))],
        "second_genes": int(second.group(1).replace(",", "")),
        "project_day": listed["registration_date"][:10].replace("/", "-"), "project_by": listed["submitter_organization"],
        "assembly": found.group(1), "strain": found.group(2), "annotation": found.group(4).replace("-WormBase", ""),
        "coding_genes": int(found.group(5).replace(",", "")), "transcripts": int(found.group(6).replace(",", "")),
        "untranslated": sum(count for biotype, count in c.biotypes.items() if biotype != "protein_coding"),
        "archive": ev.total(f"uniparc_databases_{TAXON}.json"),
        "ncbi": int(ev.json(f"ncbi_protein_count_{TAXON}.json")["esearchresult"]["count"]),
        "interpro": re.search(r"Release ([\d.]+),", ev.text("interpro_release_notes.txt")).group(1),
        "uniprot": ev.record(f"uniprotkb_{TAXON}.json")["uniprot_release"],
    }


def origin(facts):
    """What ties the gene models to the genome paper: an inference, with its grounds."""
    same = "the same" if facts["second_genes"] == facts["paper_genes"][1] else "different"
    return (
        "The database's page of this annotation names no paper. That it is the annotation this paper describes is inferred, not stated by either: "
        f"the assembly has the paper's name ({facts['assembly'].replace('_haplotype', ' haplotype ')}), the count of coding genes in the second haplotype is {same} in both ({facts['second_genes']:,}), "
        f"and in the first it is {facts['coding_genes']:,} here against the paper's {facts['paper_genes'][0]:,}."
    )


def sources(c, facts):
    ev = c.evidence
    genome = c.papers[PAPERS["genome"]]["citation"]
    return [
        {
            "name": "UniProt", "db": "uniprot", "url": "https://www.uniprot.org/", "release": facts["uniprot"], "accessed": ev.day(f"uniprotkb_{TAXON}.json"), "licence": "CC BY 4.0",
            "cite": "The UniProt Consortium, UniProt: the Universal Protein Knowledgebase in 2025, Nucleic Acids Res. 53:D609-D617 (2025)",
            "holds": "the planarian's UniProtKB entries (accessions, names, gene names, lengths, signatures and the papers they cite); which archived planarian sequences (UniParc) carry each family signature; the signatures of the units' human candidates; the counts used as controls",
        },
        {
            "name": "WormBase ParaSite", "db": "wormbase_parasite", "url": "https://parasite.wormbase.org/", "release": WBPS_RELEASE, "accessed": ev.day("wbps_s3h1_protein.fa.gz"),
            "licence": "No restriction on use is stated: the database's disclaimer says \"Ensembl imposes no restrictions on access to, or use of, the data provided\". It asks that a genome's paper and the database be cited, asks users of an unpublished genome to tell its owners before a large-scale analysis, and warns that third-party constraints may apply. The paper taken to describe this genome is CC BY 4.0.",
            "cite": f"{c.papers[PAPERS['wbps']]['citation']['text']} Genome: {genome['text']} {origin(facts)}",
            "holds": f"the gene models of one genome annotation (assembly {facts['assembly']}, annotation version {facts['annotation']}): each model's identifier, the identifier and length of its longest predicted protein, and the InterPro signatures on its predicted proteins",
        },
        {
            "name": "InterPro", "url": "https://www.ebi.ac.uk/interpro/", "release": facts["interpro"], "accessed": ev.day("interpro_entry_list.tsv"), "licence": "CC0 1.0",
            "cite": c.papers[PAPERS["interpro"]]["citation"]["text"],
            "holds": "the name and type of each signature entry",
        },
        {
            "name": "European Nucleotide Archive", "url": "https://www.ebi.ac.uk/ena/", "accessed": ev.day("uniprotkb_record_links.json"),
            "licence": "Free and unrestricted: the policy of the nucleotide sequence databases is that \"no use restrictions or licensing requirements will be included in any sequence data records\".",
            "cite": "each record is named where it is used",
            "holds": "the accession and the title of two sequence records, read to tie a UniProtKB entry to the name its paper uses",
        },
        {
            "name": "Europe PMC", "url": "https://europepmc.org/", "accessed": ev.day("europepmc_citations.json"),
            "licence": "Bibliographic facts only (authors, title, journal, year, identifiers). EMBL-EBI's terms of use add no restriction to those of the data owners. Abstracts and article texts were read to check names and are not copied.",
            "cite": "each paper is cited where it is used",
            "holds": "the records of the cited papers",
        },
    ]


def build_atlas(c, facts):
    counts = facts["counts"]
    others = ", ".join(f"{name} {counts[taxon]['entries']:,}" for taxon, name in sorted(OTHER_PLANARIANS.items(), key=lambda item: -counts[item[0]]["entries"]))
    units = {unit["id"]: unit_entry(unit["id"], c) for unit in c.snapshot["units"]}
    named = len({p["ids"][0]["id"] for unit in units.values() for p in unit["products"] if p["evidence"] == "named in a publication"})
    reviewed = [accession for accession, entry in c.entries.items() if entry["reviewed"]]
    in_atlas = {item["id"] for unit in units.values() for p in unit["products"] for item in p["ids"] if item["db"] == "uniprot"}
    if set(reviewed) & in_atlas:
        raise SystemExit("a reviewed entry is among the products; say so in the method")
    spectral = c.papers[PAPERS["spectral_library"]]
    return {
        "format": ATLAS_FORMAT,
        "species": {
            "id": "planarian", "label": "Planarian", "organism": ORGANISM, "taxon": TAXON,
            "plain": f"A freshwater flatworm that regrows its whole body from a fragment; it is the planarian the databases know best, with {counts[TAXON]['entries']:,} UniProtKB entries, more than all other planarians together, and a chromosome-scale genome with predicted genes.",
        },
        "made": c.evidence.last_day(),
        "method": [
            f"Species: UniProt holds {counts[TAXON]['entries']:,} entries for {ORGANISM} ({counts[TAXON]['reviewed']} reviewed), more than half of the {facts['order_entries']:,} it holds for all planarians (the order Tricladida; among the others, {others}), and a proteome for no planarian. WormBase ParaSite holds a chromosome-scale genome assembly of {ORGANISM} with gene models; the assembly is described by {c.short('genome')}. So the atlas is of {ORGANISM}.",
            "Licences were read before anything was copied; each is stated in sources, and what was read but not copied is in not_copied.",
            "Each unit's family was taken from its own human candidates: the InterPro signatures they carry were read from UniProt, and one or two that mark the family were chosen. The build checks that the candidates carry them.",
            f"Curated entries first: UniProt has {len(reviewed)} reviewed entries for the species, and none belongs to a family the atlas draws.",
            f"Named in a publication: a planarian protein counts as named only where the saved abstract, or the saved open-access text, of the paper uses the name. {named} products rest on this.",
            f"Family signature: unreviewed UniProtKB entries of the species that carry the signature, and gene models that carry it. The gene models are those of one genome annotation ({WBPS_RELEASE} of WormBase ParaSite, assembly {facts['assembly']}): {len(c.genes):,} genes with a predicted protein. The ones the atlas names are listed in data/proteins/planarian/{REFERENCE_FILE}. A model carries a signature if that annotation's own InterPro matches say so, or if its predicted protein is, letter for letter, a sequence that carries it in UniProt's archive (InterPro {facts['interpro']}).",
            f"A UniProtKB sequence and a gene model are given as one product when at least {round(MATCH_SHARE * 100)}% of the sequence's {MATCH_WORD}-residue words occur in the model's predicted protein and no other gene reaches half of that share.",
            f"Where a signature found nothing, it was also asked of all {facts['archive']:,} planarian sequences in UniProt's archive, of the UniProtKB entries of all flatworms and of reviewed human entries; the unit's note gives what came back.",
            "A product found by signature is a candidate, never an established counterpart. Counts are gene models in one haplotype of one genome assembly, not genes confirmed in the animal, and short models may be fragments.",
            "No similarity search against other species was run, and no product is called an ortholog.",
        ],
        "sources": sources(c, facts),
        "not_copied": (
            f"The catalogue of about 10,000 planarian proteins detected by mass spectrometry ({spectral['short']}, doi:{spectral['citation']['doi']}) was not copied: the paper and its supplementary tables reserve all rights, "
            "and its public deposit (ProteomeXchange PXD042308, which iProX's data licence puts under CC0) holds instrument files and sample sheets, not the list of proteins. "
            "PlanMine was read and nothing taken from it, because its front page states no licence or terms of use, only how to cite it. Abstracts and article texts were read to check names and are not copied."
        ),
        "units": units,
        "extra": extra_products(c),
    }


REFERENCE_COLUMNS = ["db", "id", "length", "kind", "name", "gene", "interpro", "match", "note"]


def atlas_identifiers(atlas, rows):
    """The identifiers the atlas names, and the entries or models those are joined to."""
    used = {(item["db"], item["id"]) for unit in atlas["units"].values() for p in unit["products"] for item in p["ids"]}
    used |= {(item["db"], item["id"]) for p in atlas["extra"] for item in p["ids"]}
    other = {"uniprot": "wormbase_parasite", "wormbase_parasite": "uniprot"}
    joined = {(other[row[0]], match) for row in rows if (row[0], row[1]) in used for match in row[7].split(";") if match}
    return used, used | joined


def build_reference(c):
    """One line per protein: a gene model with its longest predicted protein, or a UniProtKB entry."""
    by_gene = defaultdict(list)
    for accession, match in c.matches.items():
        by_gene[match["gene"]].append(accession)
    rows = []
    for gene_id in sorted(c.genes, key=natural):
        gene = c.genes[gene_id]
        families = [c.entry_names[s]["name"] for s in sorted(gene["interpro"]) if c.entry_names.get(s, {}).get("type") == "Family"]
        more = len(gene["proteins"]) - 1
        rows.append(["wormbase_parasite", gene_id, gene["length"], "gene model", "; ".join(families), "", ";".join(sorted(gene["interpro"])), ";".join(sorted(by_gene.get(gene_id, []))), gene["protein"] + (f" +{more}" if more else "")])
    for accession in sorted(c.entries):
        entry = c.entries[accession]
        rows.append(["uniprot", accession, entry["length"], "reviewed entry" if entry["reviewed"] else "unreviewed entry", entry["name"], " ".join(entry["genes"]), ";".join(entry["interpro"]), c.matches.get(accession, {}).get("gene", ""), entry["existence"].lower()])
    return [[re.sub(r"\s+", " ", str(value)).strip() for value in row] for row in rows]


def table(rows):
    return "\n".join("\t".join(row) for row in [REFERENCE_COLUMNS, *rows]) + "\n"


def sheet_rows(path):
    """How many rows a small spreadsheet or table holds (to tell a sample sheet from a list of proteins)."""
    import zipfile

    if path.suffix == ".csv":
        return sum(1 for line in path.read_text(encoding="utf-8", errors="replace").splitlines() if line.strip())
    with zipfile.ZipFile(path) as book:
        return sum(len(re.findall(r"<row\b", book.read(name).decode("utf-8", "replace"))) for name in book.namelist() if name.startswith("xl/worksheets/sheet"))


def library_facts(c):
    """What the saved records say of the mass-spectrometry library that was not imported."""
    ev = c.evidence
    paper = c.papers[PAPERS["spectral_library"]]
    said = re.search(r"establishing a spectral library covering \S*10,000 proteins", paper["abstract"])
    crossref = ev.json("spectral_library_crossref.json")["message"]
    rights = next(item["value"] for item in crossref["assertion"] if item["name"] == "copyright")
    first, second = ev.text("spectral_library_PXD042308.xml"), ev.text("spectral_library_PXD059861.xml")
    kinds = Counter(re.findall(r'<cvParam[^>]*name="([^"]*file URI)"', first))
    tables = [ev.path(f"spectral_library_iprox_{part}_{name}") for part, name in DEPOSIT_TABLES]
    rows = [sheet_rows(path) for path in tables]
    table = gzip.open(ev.path("spectral_library_GSE232894_TPM.csv.gz"), "rt", encoding="utf-8").read().splitlines()[1:]
    prefixes = Counter(re.match(r"[A-Za-z]+\d", line).group(0) for line in table)
    status, day = ev.refused("spectral_library_publisher_page.html")
    preprints = ev.json("spectral_library_search_preprints.json")["hitCount"]
    records = [item["attributes"] for item in ev.json("spectral_library_search_datacite.json")["data"]]
    ours = [r for r in records if re.search(r"spectral library", json.dumps(r.get("titles")), re.I) or any(re.match(r"(Lei|Ying)\b", creator.get("name", "")) for creator in r.get("creators", []))]
    if preprints or ours:
        raise SystemExit("a preprint or a data record of the library is on record; read it and rewrite what is said of the library")
    facts = {
        "citation": paper["citation"], "authors": paper["authors"], "title": paper["title"],
        "year": paper["short"].rsplit(" ", 1)[1], "journal": paper["citation"]["text"].split(paper["title"] + ". ", 1)[1],
        "says": said.group(0) if said else None, "rights": rights,
        "raw": kinds["Associated raw file URI"], "other": kinds["Search engine output file URI"],
        "announced": re.search(r'<DatasetSummary announceDate="([\d-]+)"', first).group(1),
        "raw_second": len(re.findall(r'name="Associated raw file URI"', second)),
        "rows": max(rows), "bytes": max(path.stat().st_size for path in tables),
        "rna_rows": len(table), "rna_prefix": prefixes.most_common(1)[0],
        "refused": status, "refused_day": day,
        "records": len(records), "other_proteomics": sorted({r["titles"][0]["title"].split(" - ")[0] for r in records if r.get("publisher") == "MassIVE"}),
    }
    if not said or facts["other"] != len(DEPOSIT_TABLES) or facts["rows"] > 1000 or facts["rna_prefix"][1] != len(table) or "All rights are reserved" not in rights:
        raise SystemExit("the records of the mass-spectrometry library no longer say what the README says of them")
    return facts


def build_readme(c, facts, atlas, listed, named):
    models, entries = len(c.genes), len(c.entries)
    library = library_facts(c)
    kept_models = sum(1 for row in listed if row[0] == "wormbase_parasite")
    table_sources = [s for s in atlas["sources"] if s["name"] in ("UniProt", "WormBase ParaSite", "InterPro")]
    rows = "\n".join(f"| [{s['name']}]({s['url']})" + (f", release {s['release']}" if s.get("release") else "") + f", read {s['accessed']} | {s['holds'][0].upper() + s['holds'][1:]} | {s['licence']} |" for s in table_sources)
    cites = "\n".join(f"- {s['name']}: {s['cite']}" for s in table_sources)
    more = len(listed) - named
    return f"""# Planarian proteins

Two things are recorded here for the planarian *{ORGANISM}*.

1. **The mass-spectrometry library of about 10,000 proteins was not imported.** It was
   found, its terms were read, and its list of proteins could not be reached under terms
   that allow a copy. What was found and what is missing is set out below.
2. **`{REFERENCE_FILE}` is a different thing:** the {named} predicted gene models and
   UniProtKB entries that the planarian protein atlas names, and {more} more that are joined
   to them, so that its identifiers can be looked up. It is not the library and does not
   stand in for it.

Generated by `tools/build_planarian_atlas.py`; do not edit. This is reference data for
the viewer's protein atlas. It is not the engine's protein catalogue, and nothing in the
engine reads it.

## The library of about 10,000 proteins: found, not imported

| | |
| --- | --- |
| The study | {library['authors']} ({library['year']}) {library['title']}. {library['journal']} doi:{library['citation']['doi']}, PubMed {library['citation']['pmid']} |
| What it reports | In its abstract: "{library['says']}" of *{ORGANISM}* |
| Its public deposits | ProteomeXchange PXD042308 (iProX IPX0006394000, announced {library['announced']}): {library['raw']} instrument files and {library['other']} other files. ProteomeXchange PXD059861 (iProX IPX0010799000): {library['raw_second']} instrument files. GEO GSE232894: the study's RNA sequencing |
| Terms of the paper | "{library['rights']}" |
| Terms of the deposits | iProX's data licence puts datasets submitted since 23 March 2023 under CC0, and elsewhere limits what is taken from its site to personal use; both clauses are on record |
| What is missing | The list of the library's proteins. The {library['other']} files of the deposit that are not instrument files are run lists and sample sheets (the longest has {library['rows']} rows), not proteins. A search of Europe PMC's preprints and of the data repositories that DataCite indexes found no preprint and no other record of the library. The paper's own page, where its supplementary tables are listed, answered this tool with HTTP {library['refused']} on {library['refused_day']}, and the paper reserves all rights, so nothing was taken from it |
| Which reference its identifiers use | Not stated in any record that was read. The same study's RNA-sequencing table is indexed by {library['rna_rows']:,} identifiers that begin `{library['rna_prefix'][0]}`, which suggests, and does not show, the reference the library uses |
| Other proteomics of the species | Not examined, and not the library: {len(library['other_proteomics'])} public datasets of another group ({', '.join(library['other_proteomics'])}) |

An import would need one of two things: the authors' or the publisher's permission (or a
deposit of the library under an open licence); or a new protein list derived from the
deposit's instrument files, which is a mass-spectrometry reanalysis and not a download.

## `{REFERENCE_FILE}`

{len(listed)} proteins, one per line: {kept_models} gene models and {len(listed) - kept_models} UniProtKB entries.
{named} are named by `data/proteins/atlases/planarian.json`; the other {more} are entries or
gene models joined to one that is. Tab-separated, with a header line.

| Column | Meaning |
| --- | --- |
| `db` | `wormbase_parasite` for a gene model, `uniprot` for a UniProtKB entry |
| `id` | The gene identifier in WormBase ParaSite, or the UniProtKB accession |
| `length` | Residues: of the gene's longest predicted protein, or of the entry |
| `kind` | `gene model`, `reviewed entry` or `unreviewed entry` |
| `name` | For a gene model, the InterPro families its signatures name (empty when none does); for an entry, UniProt's protein name |
| `gene` | Gene names of a UniProtKB entry, as submitted |
| `interpro` | InterPro signatures: on any predicted protein of the gene, as WormBase ParaSite computed them for its release; or on the entry, from UniProt |
| `match` | The other side of a join: a gene model's UniProtKB entries, or an entry's gene model |
| `note` | For a gene model, its longest predicted protein and how many more it has (`+2`); for an entry, UniProt's level of evidence |

They are drawn from {models:,} gene models and {entries:,} UniProtKB entries. That whole table
is not in the repository; the build writes it when asked (`--full-table FILE`, about 2 MB).

A gene model is a prediction from one haplotype of one genome assembly
({facts['assembly']}, strain {facts['strain']}, annotation version {facts['annotation']}; BioProject
PRJNA885486, registered {facts['project_day']} by the {facts['project_by']}).
WormBase ParaSite counts {facts['coding_genes']:,} coding genes in it; the {models:,} searched are those with a
predicted protein (it marks the other {facts['untranslated']:,} as not translating). Sequences are not
in this file.

{origin(facts)}

An entry and a gene model are joined when at least {round(MATCH_SHARE * 100)}% of the entry's {MATCH_WORD}-residue
words occur in the model's predicted protein and no other gene reaches half of that
share; {len(c.matches):,} of the {entries:,} entries join a gene model this way. A join says the two are
copies of one sequence, not that either is confirmed in the animal.

## Where the reference proteins came from, and under what terms

| Source | What is taken | Terms |
| --- | --- | --- |
{rows}

Cite:

{cites}

## How to rebuild

```bash
python3 tools/build_planarian_atlas.py fetch --evidence DIR   # network; saves every response
python3 tools/build_planarian_atlas.py build --evidence DIR   # offline; the same bytes every time
```

`DIR` holds the saved responses and `requests.json`, the record of what was asked and
when; it is kept outside the repository. The build also writes
`data/proteins/atlases/planarian.json`. `docs/PLANARIAN_ATLAS.md` describes the method
and its limits.
"""


def build(evidence_folder, snapshot):
    evidence = Evidence(evidence_folder)
    check_terms(evidence)
    context = Context(evidence, snapshot)
    facts = species_facts(context)
    atlas = build_atlas(context, facts)
    rows = build_reference(context)
    used, kept = atlas_identifiers(atlas, rows)
    listed = [row for row in rows if (row[0], row[1]) in kept]
    if not used <= {(row[0], row[1]) for row in listed}:
        raise SystemExit("the atlas names an identifier that the reference proteins do not hold")
    files = {
        "atlas": json.dumps(atlas, indent=1, ensure_ascii=False) + "\n",
        "reference": table(listed),
        "readme": build_readme(context, facts, atlas, listed, len(used)),
        "full": table(rows),
    }
    for name, text in files.items():
        if PATHS.search(text):
            raise SystemExit(f"the {name} would hold a machine path")
    return files, atlas, context


def summary(atlas, context):
    findings = Counter(unit["finding"] for unit in atlas["units"].values())
    products = [p for unit in atlas["units"].values() for p in unit["products"]]
    distinct = {tuple((i["db"], i["id"]) for i in p["ids"]): p for p in products}
    lines = [
        f"units by finding: {dict(sorted(findings.items()))}",
        f"product entries: {len(products)} over the units; {len(distinct)} distinct products",
        f"distinct products by evidence: {dict(sorted(Counter(p['evidence'] for p in distinct.values()).items()))}",
        f"extra: {len(atlas['extra'])}",
        f"proteins searched: {len(context.genes)} gene models + {len(context.entries)} UniProtKB entries; {len(context.matches)} entries joined to a gene model",
    ]
    for key in FAMILIES:
        lines.append(f"  family {key}: {context.count(key)} gene models, {len(context.listed(key))} UniProtKB entries")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("step", choices=["fetch", "build"], help="fetch asks the databases and saves the answers; build reads only what was saved")
    parser.add_argument("--evidence", required=True, help="the folder of saved responses (kept outside the repository)")
    parser.add_argument("--refresh", action="store_true", help="fetch: ask again even where an answer is saved")
    parser.add_argument("--out-atlas", default=str(ATLAS))
    parser.add_argument("--out-reference", default=str(REFERENCE_DIR), help="the folder for reference_proteins.tsv and its README.md")
    parser.add_argument("--full-table", help="also write every gene model and every UniProtKB entry of the species to this file (about 2 MB; not kept in the repository)")
    args = parser.parse_args()
    snapshot = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    if args.step == "fetch":
        sys.exit(1 if fetch(Path(args.evidence), snapshot, refresh=args.refresh) else 0)
    files, atlas, context = build(Path(args.evidence), snapshot)
    targets = {"atlas": Path(args.out_atlas), "reference": Path(args.out_reference) / REFERENCE_FILE, "readme": Path(args.out_reference) / "README.md"}
    if args.full_table:
        targets["full"] = Path(args.full_table)
    for name, target in targets.items():
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(files[name], encoding="utf-8")
        print(f"wrote {target} ({len(files[name].encode('utf-8')):,} bytes)")
    print(summary(atlas, context))


if __name__ == "__main__":
    main()
