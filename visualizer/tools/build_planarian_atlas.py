#!/usr/bin/env python3
"""Build the planarian side of the protein atlas, and the reference proteins it draws on.

The protein atlas draws the functional units of the Cells law inventory. A unit has no
species; what changes with the species is which gene products would make that machine.
This tool answers that for the planarian Schmidtea mediterranea, for every unit, in the
form schema/SPECIES_ATLAS.md fixes. The answers are drawn from the planarian's UniProtKB
entries and from the gene models of one genome annotation, which the tool also writes
out as a table.

Three steps, kept apart:

    python3 tools/build_planarian_atlas.py fetch --evidence DIR --datasets DATA
        asks public databases and saves every response: those of the atlas and the
        catalogue in DIR/responses, with what was asked and when in DIR/requests.json;
        those the shelves added in DATA, one folder for each source with a MANIFEST.json
        that gives every file's address, time and SHA-256. The only step that uses the
        network.

    python3 tools/build_planarian_atlas.py build --evidence DIR --datasets DATA
        reads only DIR, DATA and the inventory snapshot, and writes
        data/proteins/atlases/planarian.json and, in data/proteins/planarian/,
        predicted_proteins.tsv, reference_proteins.tsv, shelves.json, shelf_members.tsv
        and README.md: the same bytes every time.

    python3 tools/build_planarian_atlas.py members --out OUT
        cuts the shelves' member files, which the page publishes beside it, from the
        tables in data/proteins/planarian/. It reads nothing else.

The mass-spectrometry library of planarian proteins (Ying and others 2025) is not
imported: its list of proteins could not be reached under terms that allow a copy. The
paper reserves all rights, so nothing of it, its count of proteins included, is repeated.
The README the build writes says what was found and what is missing. In the meantime the
open set is written out whole (predicted_proteins.tsv): every gene model with a predicted
protein and every UniProtKB entry of the species. It is predicted, not measured.

The shelves (schema/SPECIES_PROTEINS.md) lay that open set out for the atlas: every
protein is given one family, a side of a membrane and how that side is known, and the
families open to show their members. Everything in them is a prediction on a predicted
protein.

This is the viewer's reference data. It is not the engine's protein catalogue and it
makes no claim about the engine: the laws are the same for every species.

Requests carry a generic client name and nothing about who asks. Standard library only.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
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
    # The mass-spectrometry library: read, and not copied.
    add("spectral_library_europepmc.json", f"{EPMC}/search?query={q('ext_id:40961932 AND src:med')}&format=json&resultType=core", "the paper that reports a spectral library of planarian proteins")
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
# Fetch for the shelves: later downloads, kept as datasets
# ---------------------------------------------------------------------------------------
#
# What the shelves need beyond the responses above is saved the way the project keeps
# downloads: one folder per source under a datasets folder, each with a MANIFEST.json that
# gives every file's address, time and SHA-256. The build reads a file only through its
# MANIFEST and checks it against the SHA-256 there.

BIOMART = "https://parasite.wormbase.org/biomart/martservice"
BIOMART_GENOME = "smedh1prjna885486"  # the genome annotation's name in WormBase ParaSite's BioMart
INTERPRO_FILES = "https://ftp.ebi.ac.uk/pub/databases/interpro/current_release"
SHELF_MINE = "the visualizer's planarian shelves agent"
TOPOLOGY_FIELDS = "accession,fragment,ft_non_ter,ft_signal,ft_transmem,ft_intramem,ft_topo_dom,cc_subcellular_location"
SHELF_SOURCES = {
    "wbps-biomart-smedh1prjna885486": {
        "what": "WormBase ParaSite BioMart (release 19), genome smedh1prjna885486: the membrane-spanning helices (TMHMM) and signal-peptide cleavage sites (SignalP) it holds for each predicted protein, the gene count, and the list of attributes that names them",
        "licence": "WormBase ParaSite's disclaimer: \"Ensembl imposes no restrictions on access to, or use of, the data provided\"; it asks that the genome's paper and the database be cited",
    },
    "interpro-hierarchy-and-go": {
        "what": "InterPro release files: the tree of parent and child entries, the mapping of entries to Gene Ontology terms, and the release notes",
        "licence": "CC0 1.0",
    },
    "geneontology-go-basic": {
        "what": "The Gene Ontology (go-basic.obo), read for the is_a and part_of links between terms, with the consortium's page on citing and licence",
        "licence": "CC BY 4.0",
    },
    "uniprot-smed-topology": {
        "what": "UniProtKB entries of Schmidtea mediterranea (taxon 79327): whether each is a fragment; the signal peptides, membrane-spanning segments and subcellular location UniProt gives, with the evidence for each; and the Gene Ontology terms UniProt gives each entry",
        "licence": "CC BY 4.0",
    },
    "terms-upstream-tools": {
        "what": "The terms of the tools and rule systems whose results WormBase ParaSite and UniProt give out and the planarian shelves rest on, each as its own page states them (TMHMM, SignalP, Phobius, PROSITE, HAMAP), and UniProt's own account of how it applies them. Added on 15 November 2026. Only the page of terms was asked of each tool: no program was downloaded and no form was sent",
        "licence": "Each page states the terms of its own tool; UniProt's help pages are CC BY 4.0",
    },
}
DTU = "https://services.healthtech.dtu.dk/cgi-bin/sw_request"
UPSTREAM = "terms-upstream-tools"


def biomart(attributes, flags=(), unique=False, count=False):
    """The address of one BioMart query on the genome annotation: its attributes, one row
    for each feature (or each distinct row), closed by a stamp that says the answer is whole."""
    filters = f'<Filter name="species_id_1010" value="{BIOMART_GENOME}"/>' + "".join(f'<Filter name="{flag}" excluded="0"/>' for flag in flags)
    wanted = "".join(f'<Attribute name="{name}"/>' for name in attributes)
    query = (
        '<?xml version="1.0" encoding="UTF-8"?><!DOCTYPE Query>'
        f'<Query virtualSchemaName="parasite_mart" formatter="TSV" header="1" uniqueRows="{int(unique)}" count="{1 if count else ""}" datasetConfigVersion="0.6" completionStamp="{0 if count else 1}">'
        f'<Dataset name="wbps_gene" interface="default">{filters}{wanted}</Dataset></Query>'
    )
    return f"{BIOMART}?query={q(query)}"


def shelf_requests():
    """Every request of the fetch step that the shelves added: the dataset folder, the file
    there, the address and what it is for. "whole" is what the body must end with."""
    out = []

    def add(source, file, url, purpose, **more):
        out.append({"source": source, "file": file, "url": url, "purpose": purpose, **more})

    mart = "wbps-biomart-smedh1prjna885486"
    add(mart, "biomart_attributes.tsv", f"{BIOMART}?type=attributes&dataset=wbps_gene", "the attributes BioMart offers, read for what the two predictions are called", contains="transmembrane_domain")
    add(mart, "biomart_gene_count.txt", biomart(["wbps_gene_id"], unique=True, count=True), "how many genes BioMart holds for the genome annotation, to check that it is the one the catalogue uses")
    add(mart, "biomart_tmhmm.tsv", biomart(["wbps_gene_id", "wbps_transcript_id", "transmembrane_domain"], flags=["with_tmhmm"]), "each membrane-spanning helix TMHMM predicts, one row for each, by predicted protein", whole="[success]")
    add(mart, "biomart_signalp.tsv", biomart(["wbps_gene_id", "wbps_transcript_id", "signal_domain"], flags=["with_signalp"]), "each signal-peptide cleavage site SignalP predicts, by predicted protein", whole="[success]")
    interpro = "interpro-hierarchy-and-go"
    add(interpro, "ParentChildTreeFile.txt", f"{INTERPRO_FILES}/ParentChildTreeFile.txt", "which InterPro entry is a narrower kind of which")
    add(interpro, "interpro2go", f"{INTERPRO_FILES}/interpro2go", "the Gene Ontology terms InterPro gives each of its entries")
    add(interpro, "release_notes.txt", f"{INTERPRO_FILES}/release_notes.txt", "the InterPro release these two files belong to")
    ontology = "geneontology-go-basic"
    add(ontology, "go-basic.obo", "https://current.geneontology.org/ontology/go-basic.obo", "the Gene Ontology's terms and the links between them")
    add(ontology, "go_citation_policy.html", "https://geneontology.org/docs/go-citation-policy/", "the Gene Ontology's licence")
    add("uniprot-smed-topology", f"uniprotkb_{TAXON}_topology.json", f"{UNIPROT}/uniprotkb/stream?query={q(f'taxonomy_id:{TAXON}')}&format=json&fields={TOPOLOGY_FIELDS}", "where UniProt places each of the species' entries, and on what evidence")
    add("uniprot-smed-topology", f"uniprotkb_{TAXON}_go.tsv", f"{UNIPROT}/uniprotkb/stream?query={q(f'taxonomy_id:{TAXON}')}&format=tsv&fields=accession,go_id", "the Gene Ontology terms UniProt gives each of the species' entries", contains="Gene Ontology IDs")
    # The terms of the tools and rule systems whose results the two databases give out, each
    # at its own page; and UniProt's account of how it applies them. Only pages of terms are
    # asked for: no program, and the forms on the download pages are not sent.
    add(UPSTREAM, "tmhmm_licence.html", f"{DTU}?software=tmhmm&version=2.0c&packageversion=2.0c&platform=Linux", "the licence under which DTU Health Tech gives TMHMM out, as its download page shows it", contains="ACADEMIC SOFTWARE LICENSE AGREEMENT")
    add(UPSTREAM, "signalp_licence.html", f"{DTU}?software=signalp&version=5.0&packageversion=5.0b&platform=Linux", "the licence under which DTU Health Tech gives SignalP out, as its download page shows it", contains="ACADEMIC SOFTWARE LICENSE AGREEMENT")
    add(UPSTREAM, "phobius_download.html", "https://phobius.sbc.su.se/download", "the terms under which Phobius is given out, as its download page states them", contains="academic")
    add(UPSTREAM, "prosite_license.html", "https://prosite.expasy.org/prosite_license.html", "PROSITE's licence conditions", contains="PROSITE")
    add(UPSTREAM, "hamap_about.html", "https://hamap.expasy.org/hamap_about.html", "HAMAP's statement of its licence", contains="HAMAP")
    add(UPSTREAM, "uniprot_help_sam.json", f"{UNIPROT}/help/sam", "UniProt's account of the sequence analysis methods it applies to unreviewed entries", contains="Phobius")
    add(UPSTREAM, "uniprot_help_unirule.json", f"{UNIPROT}/help/unirule", "UniProt's account of its rule systems", contains="RuleBase")
    add(UPSTREAM, "uniprot_help_arba.json", f"{UNIPROT}/help/arba", "UniProt's account of its association-rule annotator", contains="ARBA")
    add(UPSTREAM, "uniprot_help_license.json", f"{UNIPROT}/help/license", "UniProt's licence and disclaimer", contains="License")
    return out


def utc_now():
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
    return manifest is not None and SHELF_MINE in manifest.get("note", "")


def fetch_datasets(datasets, refresh=False, pause=2.0, tries=6):
    """Ask every shelf request whose file is not yet in its dataset folder; save the body as
    it came and describe it in the folder's MANIFEST. A folder another agent made is read
    and never written."""
    datasets = Path(datasets)
    asked = failed = 0
    for request in shelf_requests():
        folder = datasets / request["source"]
        manifest = read_manifest(folder)
        held = (folder / request["file"]).exists() and any(item["name"] == request["file"] for item in (manifest or {}).get("files", []))
        if held and not (refresh and is_ours(manifest)):
            continue
        if folder.exists() and not is_ours(manifest):
            print(f"missing  {request['source']}/{request['file']}: the folder was made by another agent, so nothing is written there", flush=True)
            failed += 1
            continue
        record, body = {}, None
        call = urllib.request.Request(request["url"], headers={"User-Agent": CLIENT, "Accept-Encoding": "identity"})
        for attempt in range(tries):
            record, body = {"asked": utc_now()}, None
            try:
                with urllib.request.urlopen(call, timeout=900) as answer:
                    body = answer.read()
                    record["status"] = answer.status
                    for header, key in [("X-Total-Results", "total_results"), ("X-UniProt-Release", "uniprot_release"), ("X-UniProt-Release-Date", "uniprot_release_date"), ("Last-Modified", "last_modified"), ("Content-Type", "content_type")]:
                        if answer.headers.get(header):
                            record[key] = answer.headers[header]
                # A table that was cut short, or an error page sent as an answer, is not kept.
                text = body[-200:].decode("utf-8", "replace").rstrip()
                if request.get("whole") and not text.endswith(request["whole"]):
                    record["status"], body = 0, None
                    record["error"] = "the answer does not end with its completion stamp"
                elif request.get("contains") and request["contains"].encode() not in body:
                    record["status"], body = 0, None
                    record["error"] = "the answer is not the listing asked for"
                else:
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
        asked += 1
        if record.get("status") != 200 or body is None:
            failed += 1
            print(f"{record.get('status')}  {request['source']}/{request['file']}  {record.get('error', '')}", flush=True)
            continue
        # The folder is made only if it is not there at this moment; one that another agent
        # has just made is left alone.
        folder.mkdir(parents=True, exist_ok=True)
        manifest = read_manifest(folder)
        if manifest is not None and not is_ours(manifest):
            print(f"skipped  {request['source']}/{request['file']}: the folder was just made by another agent", flush=True)
            failed += not (folder / request["file"]).exists()
            continue
        (folder / request["file"]).write_bytes(body)
        sha, md5 = digest(folder / request["file"])
        entry = {
            "name": request["file"], "url": request["url"], "role": request["purpose"], "retrieved_utc": record["asked"], "http_status": record["status"],
            "content_type": record.get("content_type"), "size_bytes": len(body), "sha256": sha, "md5": md5,
            "expected_size": None, "expected_md5": None, "ok": True, "error": None,
        }
        for key in ("total_results", "uniprot_release", "uniprot_release_date", "last_modified"):
            if record.get(key) is not None:
                entry["x_" + key] = record[key]
        manifest = manifest or {"source_id": request["source"], "files": []}
        manifest["record"] = SHELF_SOURCES[request["source"]]
        manifest["files"] = sorted([item for item in manifest["files"] if item["name"] != entry["name"]] + [entry], key=lambda item: item["name"])
        manifest["manifest_written_utc"] = utc_now()
        manifest["note"] = f"Added by {SHELF_MINE}: downloaded as untrusted data by tools/build_planarian_atlas.py of the Cells checkout. Nothing here was executed."
        (folder / "MANIFEST.json").write_text(json.dumps(manifest, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"200  {request['source']}/{request['file']}  {len(body)}", flush=True)
        time.sleep(pause)
    print(f"asked {asked} dataset request(s), {failed} failed or missing, under {datasets}")
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
     "why": "A proton-potassium pump of the planarian, by the name its sequence record gives it. The paper that reports it is on bioelectric signalling and the size of the head and organs in regeneration; it states no open licence, so its findings are not repeated here. The protein carries the same signature as the sodium-potassium pump's alpha subunit, but its record names it as a different pump, so it is kept out of that unit."},
    {"accession": "A0A291IA19", "gene": "TRPA1", "role": None, "pmid": "29184198", "words": "TRPA1", "text": "abstract", "title_match": True,
     "name": "TRPA1 cation channel",
     "why": "A cation channel of the TRP family in the planarian, by the name of its UniProtKB entry. The paper that reports it is on its activation by reactive oxygen species and on pain sensing; it states no open licence, so its findings are not repeated here. The atlas draws no unit of this family."},
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
FULL_FILE = "predicted_proteins.tsv"  # every gene model with a predicted protein, and every UniProtKB entry
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


# How each source may be used (the project's rule of 15 November 2026, decision D173):
#   permissive        CC BY, CC0, or a plain statement that no restriction is placed: its
#                     values may enter the files, with attribution;
#   non-commercial    a CC BY-NC licence of any kind: analysis only, so nothing of it enters;
#   no stated terms   no open licence is stated: nothing of it enters.
# A paper of the last two classes is a pointer. Where it is cited for a gene's name, the
# name must stand in a permissive record as well (a sequence record, or the UniProtKB entry).
PERMISSIVE, NON_COMMERCIAL, NO_TERMS = "permissive", "non-commercial", "no stated terms"


def licence_class(licence):
    """The class of a paper, from the licence its bibliographic record names."""
    if licence in ("cc by", "cc0"):
        return PERMISSIVE
    return NON_COMMERCIAL if (licence or "").startswith("cc by-nc") else NO_TERMS


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
            "citation": {"text": f"{who} ({year}) {title}. {where} {place}".strip() + ".", "doi": item.get("doi"), "pmid": item["pmid"], "class": licence_class(item.get("license"))},
            "short": f"{who} {year}",
            "title": title,
            "abstract": plain(item.get("abstractText") or ""),
            "licence": item.get("license"),
            "class": licence_class(item.get("license")),
        }
        if item.get("license") is None and item.get("isOpenAccess") == "Y" and item["pmid"] != "29184198":
            raise SystemExit(f"the record of PubMed {item['pmid']} calls it open and names no licence; read its terms and class it")
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
                held = {"source": "European Nucleotide Archive", "id": claim["record"]["embl"]}
            elif claim["gene"].lower() not in [name.lower() for name in entry["genes"]]:
                raise SystemExit(f"{accession} does not carry the name {claim['gene']}, and no sequence record ties it to the name")
            else:
                held = {"source": "UniProt", "id": accession}
            product = {
                "name": entry["name"], "gene": claim["gene"], "role": role, "ids": [{"db": "uniprot", "id": accession}] + ids, "length": entry["length"],
                "evidence": "named in a publication", "evidence_note": f"Named {claim['gene']} in {paper['short']}{tail}.", "citation": paper["citation"],
            }
            if paper["class"] != PERMISSIVE:
                # The paper's terms do not allow a copy: the name stands in a permissive record, which is named.
                product["name_record"] = held
            out.append(product)
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
    # Two papers are named as places to read; neither states an open licence, so nothing
    # is said from them: the note rests on the search of signatures alone.
    families, planarian = c.papers[PAPERS["gap_families"]], c.papers[PAPERS["gap_planarian"]]
    if PERMISSIVE in (families["class"], planarian["class"]):
        raise SystemExit("a paper of the gap-junction note now has open terms; read it and say what it says")
    controls = c.absent("connexin")
    first = controls[FAMILIES["connexin"]["signatures"][0]]
    if first["flatworms"]:
        raise SystemExit("a flatworm entry carries the connexin signature; rewrite the gap-junction notes")
    basis = (
        f"{c.carry('innexin')} the innexin signature and none the connexin one; no UniProtKB entry of any flatworm carries the connexin signature either, while {first['human']} reviewed human entries do. "
        f"One planarian innexin has a sequence record of its own, smedinx-11. More is to be read in {families['short']}, on which animals have each family, and in {planarian['short']}, on that innexin; neither states an open licence, so nothing is taken from them."
    )
    if named:
        return f"There is no {spec['as']} to find in a planarian: by its signatures it has innexins, another family of gap-junction proteins, and no connexins. {basis} Nothing says which innexins, if any, would form a channel like this one."
    return f"By their signatures, planarians have innexins and no connexins. {basis} Which innexins a general gap-junction law would stand for is not known."


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
                held = {"source": "European Nucleotide Archive", "id": item["record"]["embl"]}
            elif item["gene"].lower() in [name.lower() for name in entry["genes"]]:
                held = {"source": "UniProt", "id": accession}
            else:
                raise SystemExit(f"{accession} does not carry the name {item['gene']}, and no sequence record ties it to the name")
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
        product = {
            "name": item.get("name") or entry["name"], "gene": item["gene"], "role": item["role"], "ids": [{"db": "uniprot", "id": accession}] + ids, "length": entry["length"],
            "evidence": evidence, "evidence_note": note + tail + ".", "citation": citation,
        }
        if citation and citation["class"] != PERMISSIVE:
            # The paper's terms do not allow a copy: the name stands in a permissive record, which is named.
            product["name_record"] = held
        product["why"] = item["why"].format(k2p=c.count("k2p"))
        out.append(product)
    return out


# ---------------------------------------------------------------------------------------
# Build: sources, terms and the three files
# ---------------------------------------------------------------------------------------

TERMS = [
    # (saved page, words it must contain): the terms the files state, as they were read.
    ("terms_uniprot_license.json", "Creative Commons Attribution 4.0 International (CC BY 4.0) License"),
    ("terms_wbps_disclaimer.html", "Ensembl imposes no restrictions on access to, or use of, the data provided"),
    ("terms_wbps_disclaimer.html", "Some of the data and software included in the distribution may be subject to third-party constraints. Users of the data and software are solely responsible for establishing the nature of and complying with any such restrictions."),
    ("terms_wbps_datausage.html", "Please cite the original paper for the genome publication"),
    ("terms_interpro_license.html", "CC0 1.0 Universal"),
    ("terms_embl_ebi.html", "EMBL-EBI imposes no additional restriction on the use of the contributed data than those provided by the data owner"),
    ("terms_europepmc_s3_genome_paper_fulltext.xml", "licensed under a Creative Commons Attribution 4.0 International License"),
    ("spectral_library_crossref.json", "All rights are reserved"),
    ("terms_insdc_policy.html", "no use restrictions or licensing requirements will be included in any sequence data records"),
    ("terms_iprox_data_licence.html", "Creative Commons Public Domain (CC0) license apply to all iProX datasets submitted since March 23rd, 2023"),
    ("terms_iprox_data_licence.html", "for use solely by you for your own personal use and not for republication"),
    ("spectral_library_europepmc.json", "establishing a spectral library"),
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


def cited_in_atlas(c):
    """The PubMed ids of the papers that the atlas's products and notes name."""
    return {item["pmid"] for item in [*NAMED.values(), *CALLED.values(), *EXTRA] if item.get("pmid")} | {PAPERS[name] for name in ("gap_families", "gap_planarian", "inx13", "inx1")}


def listed_papers(c, kind):
    """The papers the atlas names that are of one class, in words."""
    names = sorted((c.papers[pmid]["short"] for pmid in cited_in_atlas(c) if c.papers[pmid]["class"] == kind), key=lambda name: (name.rsplit(" ", 1)[1], name))
    return ", ".join(names[:-1]) + " and " + names[-1] if len(names) > 1 else "".join(names)


def sources(c, facts):
    ev = c.evidence
    genome = c.papers[PAPERS["genome"]]["citation"]
    return [
        {
            "name": "UniProt", "db": "uniprot", "url": "https://www.uniprot.org/", "release": facts["uniprot"], "accessed": ev.day(f"uniprotkb_{TAXON}.json"), "licence": "CC BY 4.0", "class": PERMISSIVE,
            "cite": "The UniProt Consortium, UniProt: the Universal Protein Knowledgebase in 2025, Nucleic Acids Res. 53:D609-D617 (2025)",
            "holds": "the planarian's UniProtKB entries (accessions, names, gene names, lengths, signatures and the papers they cite); which archived planarian sequences (UniParc) carry each family signature; the signatures of the units' human candidates; the counts used as controls",
        },
        {
            "name": "WormBase ParaSite", "db": "wormbase_parasite", "url": "https://parasite.wormbase.org/", "release": WBPS_RELEASE, "accessed": ev.day("wbps_s3h1_protein.fa.gz"),
            "licence": "No restriction on use is stated: the database's disclaimer says \"Ensembl imposes no restrictions on access to, or use of, the data provided\". It asks that a genome's paper and the database be cited, asks users of an unpublished genome to tell its owners before a large-scale analysis, and warns that third-party constraints may apply. The paper taken to describe this genome is CC BY 4.0.",
            "class": PERMISSIVE,
            "cite": f"{c.papers[PAPERS['wbps']]['citation']['text']} Genome: {genome['text']} {origin(facts)}",
            "holds": f"the gene models of one genome annotation (assembly {facts['assembly']}, annotation version {facts['annotation']}): each model's identifier, the identifier and length of its longest predicted protein, and the InterPro signatures on its predicted proteins",
        },
        {
            "name": "InterPro", "url": "https://www.ebi.ac.uk/interpro/", "release": facts["interpro"], "accessed": ev.day("interpro_entry_list.tsv"), "licence": "CC0 1.0", "class": PERMISSIVE,
            "cite": c.papers[PAPERS["interpro"]]["citation"]["text"],
            "holds": "the name and type of each signature entry",
        },
        {
            "name": "European Nucleotide Archive", "url": "https://www.ebi.ac.uk/ena/", "accessed": ev.day("uniprotkb_record_links.json"),
            "licence": "Free and unrestricted: the policy of the nucleotide sequence databases is that \"no use restrictions or licensing requirements will be included in any sequence data records\".",
            "class": PERMISSIVE,
            "cite": "each record is named where it is used",
            "holds": "the accession and the title of two sequence records, read to tie a UniProtKB entry to the name its paper uses",
        },
        {
            "name": "Europe PMC", "url": "https://europepmc.org/", "accessed": ev.day("europepmc_citations.json"),
            "licence": "Bibliographic facts only (authors, title, journal, year, identifiers). EMBL-EBI's terms of use add no restriction to those of the data owners. Abstracts and article texts were read to check names and are not copied.",
            "class": PERMISSIVE,
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
            f"The catalogue of planarian proteins detected by mass spectrometry ({spectral['short']}, doi:{spectral['citation']['doi']}) was not copied: the paper and its supplementary tables reserve all rights, "
            "and its public deposit (ProteomeXchange PXD042308, which iProX's data licence puts under CC0) holds instrument files and sample sheets, not the list of proteins. "
            "PlanMine was read and nothing taken from it, because its front page states no licence or terms of use, only how to cite it. Abstracts and article texts were read to check names and are not copied. "
            f"Of the papers that name the proteins listed here, {listed_papers(c, NO_TERMS)} state no open licence: each is cited for a name, which a sequence record or a UniProtKB entry carries too, and none of their findings is repeated."
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
    said = re.search(r"establishing a spectral library", paper["abstract"])
    if not said or paper["class"] == PERMISSIVE:
        raise SystemExit("the library's paper no longer reads as it did, or now has open terms; read it again")
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
        "rights": rights,
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


# ---------------------------------------------------------------------------------------
# The shelves: every protein given one family, a side and a district
# ---------------------------------------------------------------------------------------
#
# schema/SPECIES_PROTEINS.md fixes the form. The catalogue is too large for one marker
# each, so it is given as families that open: shelves.json holds the families, and
# shelf_members.tsv holds, for every protein, what it is filed under, its side and how
# that side is known. The page builder cuts the members into files from the two tables.

SHELF_FORMAT = "cells.visualizer.species_proteins@1"
MEMBERS_FORMAT = "cells.visualizer.species_protein_members@1"
SHELVES_FILE = "shelves.json"
MEMBERS_FILE = "shelf_members.tsv"
MEMBERS_COLUMNS = ["id", "under", "side", "basis", "helices", "signal", "units"]
SIDES = ["outside", "in", "inside", "not known"]
SIDE_TIE = ["in", "outside", "inside", "not known"]  # where a family's members are split evenly
MEMBERS_PER_FILE = 2000
SHELF = {
    "id": "cell",
    "label": "The cell's membranes, not told apart",
    "outside": "Beyond a membrane: outside the cell, or within one of its compartments",
    "inside": "Inside the cell: in the cytoplasm or the nucleus, or carried into an organelle",
}
# This tool's own reading of a sequence, used only where the two predictors leave a doubt
# (see side_of_model). It takes no published scale: a stretch is hydrophobic when most of
# its residues are among the plainly hydrophobic ones.
HYDROPHOBIC = frozenset("AILMFVW")
HYDROPHOBIC_WINDOW = 19   # residues, about the span of a membrane
HYDROPHOBIC_LEAST = 12    # how many of them must be hydrophobic for a membrane-spanning stretch
SIGNAL_REACH = 35         # a stretch that starts before this residue can be the signal peptide itself

# The districts, in order. A protein's Gene Ontology terms are those InterPro maps to any
# of its signatures, and those UniProt gives a UniProtKB entry (a gene model takes also
# the terms of the entries joined to it). The protein falls in the first district one of
# whose terms it carries, and a family stands where most of its classed members fall.
# The choice of terms and their order is the viewer's; each term's name is checked
# against the ontology.
DISTRICTS = [
    ("channels", "Channels", [("GO:0015267", "channel activity")]),
    ("transport", "Transporters and pumps", [("GO:0005215", "transporter activity"), ("GO:0055085", "transmembrane transport"), ("GO:0006811", "monoatomic ion transport")]),
    ("signalling", "Receptors and signalling", [("GO:0038023", "signaling receptor activity"), ("GO:0060089", "molecular transducer activity"), ("GO:0007165", "signal transduction"), ("GO:0005102", "signaling receptor binding")]),
    ("genes", "DNA, RNA and making proteins", [("GO:0010467", "gene expression"), ("GO:0006259", "DNA metabolic process"), ("GO:0003677", "DNA binding"), ("GO:0003723", "RNA binding"), ("GO:0140110", "transcription regulator activity"), ("GO:0006355", "regulation of DNA-templated transcription"), ("GO:0006325", "chromatin organization"), ("GO:0005840", "ribosome"), ("GO:0140640", "catalytic activity, acting on a nucleic acid")]),
    ("proteins", "Protein folding, change, sorting and breakdown", [("GO:0006457", "protein folding"), ("GO:0006508", "proteolysis"), ("GO:0036211", "protein modification process"), ("GO:0015031", "protein transport"), ("GO:0016192", "vesicle-mediated transport"), ("GO:0140096", "catalytic activity, acting on a protein")]),
    ("structure", "Cytoskeleton, movement and adhesion", [("GO:0005856", "cytoskeleton"), ("GO:0007010", "cytoskeleton organization"), ("GO:0003774", "cytoskeletal motor activity"), ("GO:0007018", "microtubule-based movement"), ("GO:0007155", "cell adhesion"), ("GO:0031012", "extracellular matrix"), ("GO:0005929", "cilium"), ("GO:0005198", "structural molecule activity")]),
    ("metabolism", "Enzymes and metabolism", [("GO:0003824", "catalytic activity"), ("GO:0008152", "metabolic process")]),
]
OTHER_DISTRICT = ("other", "Other functions")
NO_DISTRICT = ("unclassed", "Not classed by function")
# Where in the cell the same terms place a protein: an annotation carried by its
# signatures, kept as a hint beside the predicted side. It is not a prediction for the
# protein itself.
WHERE = [
    ("nucleus", "GO:0005634", "nucleus"), ("mitochondrion", "GO:0005739", "mitochondrion"), ("endoplasmic reticulum", "GO:0005783", "endoplasmic reticulum"),
    ("Golgi apparatus", "GO:0005794", "Golgi apparatus"), ("lysosome", "GO:0005764", "lysosome"), ("peroxisome", "GO:0005777", "peroxisome"),
    ("cilium", "GO:0005929", "cilium"), ("cytoskeleton", "GO:0005856", "cytoskeleton"), ("ribosome", "GO:0005840", "ribosome"),
    ("cytosol", "GO:0005829", "cytosol"), ("plasma membrane", "GO:0005886", "plasma membrane"), ("extracellular", "GO:0005576", "extracellular region"),
]
INSIDE_WHERE = {"nucleus", "mitochondrion", "cilium", "cytoskeleton", "ribosome", "cytosol"}
# The roles of a unit's products that span a membrane: their families must come out "in".
SPANNING_ROLES = {"alpha", "alpha1", "innexin", "alpha (BK)", "alpha (SK)", "beta (BK)", "catalytic", "exchanger", "IP3R", "RyR", "KCC", "MCU"}


class Datasets:
    """The shelves' downloads, each read through its folder's MANIFEST and checked against it."""

    def __init__(self, folder):
        self.folder = Path(folder)
        self.read = {}

    def entry(self, source, file):
        if (source, file) not in self.read:
            manifest = read_manifest(self.folder / source)
            if manifest is None:
                raise SystemExit(f"no dataset folder {source!r} with a MANIFEST; run the fetch step first")
            entry = next((item for item in manifest["files"] if item["name"] == file), None)
            if entry is None or not (self.folder / source / file).exists():
                raise SystemExit(f"the dataset folder {source} does not hold {file!r}; run the fetch step first")
            if digest(self.folder / source / file)[0] != entry["sha256"]:
                raise SystemExit(f"{source}/{file} is not the file its MANIFEST describes")
            self.read[source, file] = entry
        return self.read[source, file]

    def path(self, source, file):
        self.entry(source, file)
        return self.folder / source / file

    def text(self, source, file):
        return self.path(source, file).read_text(encoding="utf-8", errors="replace")

    def day(self, source, file):
        return self.entry(source, file)["retrieved_utc"][:10]

    def last_day(self):
        return max(entry["retrieved_utc"][:10] for entry in self.read.values())


def read_hierarchy(d):
    """InterPro's tree: each entry's parent, the broader entry it is a kind of."""
    parent, stack = {}, []
    for line in d.text("interpro-hierarchy-and-go", "ParentChildTreeFile.txt").splitlines():
        if not line.strip():
            continue
        depth = (len(line) - len(line.lstrip("-"))) // 2
        accession = line.lstrip("-").split("::")[0]
        stack = stack[:depth]
        if depth:
            parent[accession] = stack[-1]
        stack.append(accession)
    return parent


def read_family_terms(d):
    """InterPro's mapping of its entries to Gene Ontology terms."""
    terms = defaultdict(list)
    for line in d.text("interpro-hierarchy-and-go", "interpro2go").splitlines():
        found = re.match(r"InterPro:(IPR\d+) .* ; (GO:\d+)$", line)
        if found and found.group(2) not in terms[found.group(1)]:
            terms[found.group(1)].append(found.group(2))
    return dict(terms)


def read_ontology(d):
    """The Gene Ontology: each term's name and the broader terms it is a kind or a part of."""
    terms, current = {}, None
    for line in d.text("geneontology-go-basic", "go-basic.obo").splitlines():
        if line == "[Term]":
            current = {"up": [], "alt": []}
            continue
        if line.startswith("["):
            current = None
            continue
        if current is None or ": " not in line:
            continue
        key, value = line.split(": ", 1)
        if key == "id":
            terms[value] = current
        elif key == "name":
            current["name"] = value
        elif key == "is_a":
            current["up"].append(value.split(" ! ")[0])
        elif key == "relationship" and value.startswith("part_of "):
            current["up"].append(value.split()[1])
        elif key == "alt_id":
            current["alt"].append(value)
        elif key == "is_obsolete":
            current["obsolete"] = True
        elif key == "replaced_by":
            current["replaced_by"] = value
    for term in list(terms):
        for other in terms[term]["alt"]:
            terms.setdefault(other, {"same_as": term})
    version = re.search(r"^data-version: (\S+)", d.text("geneontology-go-basic", "go-basic.obo")[:400], re.M)
    for _, _, wanted in DISTRICTS:
        for term, name in wanted:
            if terms.get(term, {}).get("name") != name:
                raise SystemExit(f"the ontology no longer calls {term} {name!r}; choose the districts' terms again")
    for _, term, name in WHERE:
        if terms.get(term, {}).get("name") != name:
            raise SystemExit(f"the ontology no longer calls {term} {name!r}; choose the places again")
    return terms, version.group(1)


def broader_terms(terms):
    """For a term, itself and every broader term, by the kind-of and part-of links."""
    memo = {}

    def up(term):
        if term not in memo:
            out = {term}
            for other in terms[term]["up"]:
                if other in terms:
                    out |= up(other)
            memo[term] = out
        return memo[term]

    def usable(term):
        entry = terms.get(term)
        if entry is None:
            return None
        if "same_as" in entry:
            return entry["same_as"]
        if entry.get("obsolete"):
            return usable(entry["replaced_by"]) if entry.get("replaced_by") else None
        return term

    return up, usable


def read_predictions(d, c):
    """TMHMM's helices and SignalP's signal peptides, as WormBase ParaSite holds them for
    the gene models' predicted proteins: how many helices each has, and which have a signal."""
    mart = "wbps-biomart-smedh1prjna885486"
    called = {}
    for line in d.text(mart, "biomart_attributes.tsv").splitlines():
        columns = line.split("\t")
        if len(columns) > 1:
            called.setdefault(columns[0], columns[1])
    if called.get("transmembrane_domain") != "Transmembrane (TMHMM) domain" or called.get("signal_domain") != "Cleavage site (SignalP)":
        raise SystemExit("BioMart no longer names the two predictions as TMHMM's and SignalP's; read its listing again")
    if int(d.text(mart, "biomart_gene_count.txt").strip()) != sum(c.biotypes.values()):
        raise SystemExit("BioMart's genome is not the annotation the catalogue uses: the gene counts differ")
    helices, signals = Counter(), {}
    for file, values in (("biomart_tmhmm.tsv", {"TMhelix"}), ("biomart_signalp.tsv", {"SignalP-noTM", "SignalP-TM"})):
        lines = d.text(mart, file).splitlines()
        if lines[-1] != "[success]" or not lines[0].startswith("Gene stable ID\tTranscript stable ID\t"):
            raise SystemExit(f"{file} is not a whole BioMart answer")
        for line in lines[1:-1]:
            gene, protein, value = line.split("\t")
            if c.proteins.get(protein, {}).get("gene") != gene or value not in values:
                raise SystemExit(f"{file} holds a line the annotation file does not explain: {line!r}")
            if file == "biomart_tmhmm.tsv":
                helices[protein] += 1
            else:
                signals[protein] = value
    return helices, signals


# Whose tool or rule a statement of a UniProtKB entry is by, as its evidence names it. The
# first two are programs that UniProt's sequence analysis runs (its own account says how);
# PROSITE and HAMAP are rule systems of the SIB with terms of their own; the others are
# UniProt's own rule systems, or its curators.
SYSTEMS = {
    ("SAM", "Phobius"): "TMHMM and Phobius", ("SAM", "SignalP"): "SignalP", ("PROSITE-ProRule", None): "PROSITE", ("HAMAP-Rule", None): "HAMAP",
    ("RuleBase", None): "UniProt's rules", ("ARBA", None): "UniProt's rules", ("PIRNR", None): "UniProt's rules", ("PIRSR", None): "UniProt's rules",
    (None, None): "UniProt's curators, by sequence analysis", ("UniProtKB", None): "likeness",
}


def systems_named(evidences):
    out = set()
    for evidence in evidences:
        source = evidence.get("source")
        key = (source, evidence.get("id") if source == "SAM" else None)
        if evidence.get("evidenceCode") == "ECO:0000250":
            key = ("UniProtKB", None)
        if key not in SYSTEMS:
            raise SystemExit(f"a UniProtKB entry gives a statement by {key}; read what that is, and its terms, before the statement is used")
        out.add(SYSTEMS[key])
    return frozenset(out)


def read_topology(d, c):
    """What UniProt gives for each of the species' entries: membrane-spanning segments,
    a signal peptide, whether the start of the sequence is missing, and where it places it."""
    out = {}
    for item in json.loads(d.text("uniprot-smed-topology", f"uniprotkb_{TAXON}_topology.json"))["results"]:
        features = item.get("features", [])
        places = []
        for comment in item.get("comments", []):
            if comment.get("commentType") == "SUBCELLULAR LOCATION":
                for place in comment.get("subcellularLocations", []):
                    given = [evidence for part in ("location", "topology", "orientation") if place.get(part) for evidence in place[part].get("evidences", [])]
                    places.append((place["location"]["value"], (place.get("topology") or {}).get("value") or "", systems_named(given)))
        by = lambda kind: tuple(sorted(set().union(*(systems_named(feature.get("evidences", [])) for feature in features if feature["type"] == kind)))) if any(feature["type"] == kind for feature in features) else ()
        out[item["primaryAccession"]] = {
            "helices": sum(feature["type"] == "Transmembrane" for feature in features),
            "signal": any(feature["type"] == "Signal" for feature in features),
            "helices_by": by("Transmembrane"),
            "signal_by": by("Signal"),
            "start_missing": any(feature["type"] == "Non-terminal residue" and feature["location"]["start"]["value"] == 1 for feature in features),
            "places": places,
            "reviewed": item["entryType"].startswith("UniProtKB reviewed"),
        }
    if set(out) != set(c.entries):
        raise SystemExit("UniProt's entries of the species are not the ones the catalogue was made from; fetch both again")
    return out


def ontology_citation(d):
    """The two papers the Gene Ontology asks to be cited, in its own page's words."""
    page = plain(d.text("geneontology-go-basic", "go_citation_policy.html"))
    first = re.search(r"(Ashburner et al\. Gene ontology: tool for the unification of biology\. [^\[]*?DOI: \S+)", page)
    latest = re.search(r"(The Gene Ontology Consortium\. The Gene Ontology knowledgebase in \d{4}\. [^\[]*?DOI: \S+)", page)
    if not first or not latest:
        raise SystemExit("the Gene Ontology's saved page no longer names the two papers to cite; read it again")
    return f"{first.group(1)}; {latest.group(1)}"


def read_entry_terms(d, c):
    """The Gene Ontology terms UniProt gives each of the species' entries."""
    lines = d.text("uniprot-smed-topology", f"uniprotkb_{TAXON}_go.tsv").splitlines()
    if lines[0].split("\t") != ["Entry", "Gene Ontology IDs"]:
        raise SystemExit("UniProt's table of the entries' terms is not the one asked for")
    out = {}
    for line in lines[1:]:
        accession, _, found = line.partition("\t")
        out[accession] = [term.strip() for term in found.split(";") if term.strip()]
    if set(out) != set(c.entries):
        raise SystemExit("UniProt's entries of the species are not the ones the catalogue was made from; fetch both again")
    return out


def hydrophobic_stretches(sequence):
    """Where at least 12 of a window of 19 residues are hydrophobic: [start, end) of each
    stretch, counted from 0."""
    values = [residue in HYDROPHOBIC for residue in sequence]
    out, run = [], None
    if len(values) < HYDROPHOBIC_WINDOW:
        return out
    total = sum(values[:HYDROPHOBIC_WINDOW])
    for start in range(len(values) - HYDROPHOBIC_WINDOW + 1):
        if start:
            total += values[start + HYDROPHOBIC_WINDOW - 1] - values[start - 1]
        if total >= HYDROPHOBIC_LEAST:
            if run is None:
                run = [start, start + HYDROPHOBIC_WINDOW]
            else:
                run[1] = start + HYDROPHOBIC_WINDOW
        elif run is not None:
            out.append(tuple(run))
            run = None
    if run is not None:
        out.append(tuple(run))
    return out


def side_of_place(value, spans):
    """The side a location in UniProt's words stands for, or None where it does not say."""
    if value.startswith("Secreted"):
        return "outside"
    if "membrane" in value.lower() or value.startswith("Endomembrane system"):
        return "in" if spans.startswith(("Multi-pass", "Single-pass")) else None
    if value.startswith(("Nucleus", "Chromosome", "Cytoplasm", "Mitochondrion", "Cell projection")):
        return "inside"
    return None


def side_from_where(where):
    """The side a family's annotated places leave no real doubt of, or None."""
    if where and set(where) <= INSIDE_WHERE:
        return "inside"
    if where == ["extracellular"]:
        return "outside"
    return None


class Shelves:
    """Everything the shelves are made from, and each protein's family, side and district."""

    def __init__(self, c, d, rows, atlas):
        self.c, self.d, self.rows, self.atlas = c, d, rows, atlas
        if len({row[1] for row in rows}) != len(rows):
            raise SystemExit("two proteins of the catalogue share an identifier; the members' table needs both columns")
        self.release = re.search(r"Release ([\d.]+),", d.text("interpro-hierarchy-and-go", "release_notes.txt")).group(1)
        if self.release != re.search(r"Release ([\d.]+),", c.evidence.text("interpro_release_notes.txt")).group(1):
            raise SystemExit("the InterPro tree and the InterPro names are of different releases; fetch both again")
        if "licensed under the Creative Commons Attribution 4.0 Unported License" not in plain(d.text("geneontology-go-basic", "go_citation_policy.html")):
            raise SystemExit("the Gene Ontology's saved page no longer states its licence as read; read the terms again before building")
        self.parent = read_hierarchy(d)
        self.signature_terms = read_family_terms(d)
        self.entry_terms = read_entry_terms(d, c)
        self.terms, self.ontology = read_ontology(d)
        self.up, self.usable = broader_terms(self.terms)
        self.helices, self.signals = read_predictions(d, c)
        self.topology = read_topology(d, c)
        self.kind = lambda accession: c.entry_names.get(accession, {}).get("type")
        self.units = defaultdict(set)   # protein -> the units the atlas lists it under
        self.roles = defaultdict(set)   # protein -> the roles it has there
        for unit_id, unit in atlas["units"].items():
            for product in unit["products"]:
                for item in product["ids"]:
                    self.units[item["id"]].add(unit_id)
                    self.roles[item["id"]].add(product["role"])
        self.file_proteins()
        self.class_proteins()
        self.place_proteins()

    # --- one family for each protein ----------------------------------------------------

    def depth(self, accession):
        depth = 0
        while accession in self.parent:
            accession, depth = self.parent[accession], depth + 1
        return depth

    def broader(self, accession):
        out = []
        while accession in self.parent:
            accession = self.parent[accession]
            out.append(accession)
        return out

    def file_proteins(self):
        """under[id] is the family the protein is filed under, or the part of "no family"."""
        signatures = {row[1]: [s for s in row[6].split(";") if s] for row in self.rows}
        narrowest, carried = {}, Counter()
        for protein, found in signatures.items():
            families = [s for s in found if self.kind(s) == "Family"]
            covered = {b for family in families for b in self.broader(family)}
            narrowest[protein] = [family for family in families if family not in covered]
            carried.update(set(found))
        held = Counter(family for families in narrowest.values() for family in families)
        self.family, self.part, self.several = {}, {}, 0
        for protein, families in narrowest.items():
            if families:
                # The narrowest family; of several unrelated ones, the deepest in InterPro's
                # tree, then the one fewest proteins of this catalogue are in, then the first.
                self.several += len(families) > 1
                self.family[protein] = min(families, key=lambda f: (-self.depth(f), held[f], f))
                continue
            wider = [s for s in signatures[protein] if self.kind(s) == "Homologous_superfamily"]
            if wider:
                self.part[protein] = min(wider, key=lambda s: (carried[s], s))
            else:
                self.part[protein] = "other-signature" if signatures[protein] else "no-signature"
        self.signatures = signatures

    # --- what a protein's signatures say it does, and where -------------------------------

    def class_proteins(self):
        """classed[id] is the district the protein's own terms put it in; places[id] the
        places in the cell they name."""
        joined = defaultdict(list)
        for accession, match in self.c.matches.items():
            joined[match["gene"]].append(accession)
        self.classed, self.places, self.dropped = {}, {}, set()
        for row in self.rows:
            direct = [term for signature in self.signatures[row[1]] for term in self.signature_terms.get(signature, [])]
            for accession in ([row[1]] if row[0] == "uniprot" else sorted(joined.get(row[1], []))):
                direct += self.entry_terms[accession]
            terms = set()
            for term in direct:
                usable = self.usable(term)
                if usable:
                    terms |= self.up(usable)
                else:
                    self.dropped.add(term)
            self.places[row[1]] = [key for key, term, _ in WHERE if term in terms]
            self.classed[row[1]] = next((key for key, _, wanted in DISTRICTS if any(term in terms for term, _ in wanted)), OTHER_DISTRICT[0] if terms else NO_DISTRICT[0])

    def district(self, proteins, loose=False):
        """A family's members are one kind of protein, so the district most of its classed
        members fall in speaks for it; of equal counts, the first district. A part of
        "no family" is a looser grouping (loose): it stands in a district only if more
        than half of all its members fall there."""
        found = Counter(self.classed[protein] for protein in proteins)
        order = [key for key, _, _ in DISTRICTS]
        best = max(order, key=lambda key: (found.get(key, 0), -order.index(key)))
        if loose:
            best = max([*order, OTHER_DISTRICT[0]], key=lambda key: found.get(key, 0))
            return best if 2 * found.get(best, 0) > len(proteins) else NO_DISTRICT[0]
        if found.get(best):
            return best
        return OTHER_DISTRICT[0] if found.get(OTHER_DISTRICT[0]) else NO_DISTRICT[0]

    def where(self, proteins):
        """The places at least half of the proteins that are given any place are given."""
        placed = [self.places[protein] for protein in proteins if self.places[protein]]
        return [key for key, _, _ in WHERE if 2 * sum(key in found for found in placed) >= len(placed) > 0]

    # --- the side of each protein -------------------------------------------------------

    def side_of_model(self, row):
        """A gene model: by TMHMM and SignalP on its longest predicted protein."""
        protein = row[8].split()[0]
        helices, signal = self.helices.get(protein, 0), protein in self.signals
        sequence = self.c.proteins[protein]["sequence"]
        # What a predicted side rests on: what the two programs found, or did not find, as
        # WormBase ParaSite ran them.
        ran = lambda on: ("gene model", on, frozenset())
        if helices >= 2 or (helices == 1 and not signal):
            return "in", "predicted", helices, signal, ran("helices")
        if helices == 1:
            # One helix and a signal peptide: TMHMM may have taken the signal peptide for a
            # helix. Where the hydrophobic stretch lies decides, by this tool's own reading.
            stretches = hydrophobic_stretches(sequence)
            if any(start >= SIGNAL_REACH for start, _ in stretches):
                return "in", "predicted", helices, signal, ran("a helix and a signal peptide")
            if stretches:
                return "outside", "predicted", helices, signal, ran("a helix and a signal peptide")
            return "not known", "none", helices, signal, None
        if signal:
            return "outside", "predicted", helices, signal, ran("a signal peptide")
        if sequence.startswith("M"):
            return "inside", "predicted", helices, signal, ran("nothing found")
        # The model does not begin with a start codon's methionine, so a signal peptide may
        # be missing with its beginning: nothing was predicted, and nothing can be said
        # from that, unless what its family is annotated to be leaves no real doubt.
        side = side_from_where(self.places[row[1]])
        return (side, "by function", helices, signal, None) if side else ("not known", "none", helices, signal, None)

    def side_of_entry(self, row):
        """A UniProtKB entry: by what the entry states or what UniProt predicts on it."""
        known = self.topology[row[1]]
        helices, signal = known["helices"], known["signal"]
        sides = {side_of_place(value, spans) for value, spans, _ in known["places"]} - {None}
        # What the side rests on: the tools and rule systems named on the features, or on
        # the stated places that give the side.
        said = lambda side: frozenset().union(*(by for value, spans, by in known["places"] if side_of_place(value, spans) == side))
        if known["reviewed"] and len(sides) == 1:
            side = sides.pop()
            return side, "stated", helices, signal, ("entry", "a stated place", said(side))
        if helices:
            return "in", "predicted", helices, signal, ("entry", "segments", frozenset(known["helices_by"]))
        if signal:
            return "outside", "predicted", helices, signal, ("entry", "a signal peptide", frozenset(known["signal_by"]))
        if len(sides) == 1:
            side = sides.pop()
            return side, "by function", helices, signal, ("entry", "a stated place", said(side))
        if not known["start_missing"]:
            return "inside", "predicted", helices, signal, ("entry", "nothing found", frozenset())
        side = side_from_where(self.places[row[1]])
        return (side, "by function", helices, signal, None) if side else ("not known", "none", helices, signal, None)

    def place_proteins(self):
        self.placed, self.rests = {}, {}
        for row in self.rows:
            *placed, rest = self.side_of_model(row) if row[0] == "wormbase_parasite" else self.side_of_entry(row)
            self.placed[row[1]], self.rests[row[1]] = tuple(placed), rest

    # --- how the predictions fare ---------------------------------------------------------

    def agreement(self):
        """Each UniProtKB entry that is whole, against the gene model it is joined to: two
        sets of predictors on copies of one sequence. Returns all such pairs, and those
        whose gene model has one helix and a signal peptide (settled by this tool)."""
        by_id = {row[1]: row for row in self.rows}
        out, settled = Counter(), Counter()
        for accession, match in sorted(self.c.matches.items()):
            model = by_id[match["gene"]]
            if self.topology[accession]["start_missing"] or self.c.entries[accession]["length"] < 0.9 * int(model[2]):
                continue
            pair = (self.placed[model[1]][0], self.placed[accession][0])
            out[pair] += 1
            protein = model[8].split()[0]
            if self.helices.get(protein, 0) == 1 and protein in self.signals:
                settled[pair] += 1
        return out, settled


TOOLS_OF_SAM = "TMHMM and Phobius"   # what UniProt's sequence analysis keeps a segment on
OWN_RULES = "UniProt's rules"


def rests_on(s, rows):
    """What the sides rest on beyond the two databases themselves: counted from each
    protein's placement, as side_of_model and side_of_entry say it."""
    found = Counter()
    for row in rows:
        side, basis, _, _ = s.placed[row[1]]
        rest = s.rests[row[1]]
        if rest:
            found[(rest[0], rest[1], tuple(sorted(rest[2])), side, basis)] += 1
    count = lambda want: sum(n for key, n in found.items() if want(*key))
    models = {
        "predicted": count(lambda kind, on, by, side, basis: kind == "gene model"),
        "in a membrane, by helices": count(lambda kind, on, by, side, basis: kind == "gene model" and on == "helices"),
        "one helix and a signal peptide, settled by this tool": count(lambda kind, on, by, side, basis: kind == "gene model" and on == "a helix and a signal peptide"),
        "outside, by a signal peptide": count(lambda kind, on, by, side, basis: kind == "gene model" and on == "a signal peptide"),
        "inside, nothing found": count(lambda kind, on, by, side, basis: kind == "gene model" and on == "nothing found"),
    }
    entry = lambda want: count(lambda kind, on, by, side, basis: kind == "entry" and want(on, by, side, basis))
    entries = {
        "predicted": entry(lambda on, by, side, basis: basis == "predicted"),
        "in a membrane, by segments of the sequence analysis": entry(lambda on, by, side, basis: on == "segments" and by == (TOOLS_OF_SAM,)),
        "in a membrane, by segments that carry a PROSITE rule": entry(lambda on, by, side, basis: on == "segments" and "PROSITE" in by),
        "in a membrane, by segments of UniProt's own rules": entry(lambda on, by, side, basis: on == "segments" and by == (OWN_RULES,)),
        "outside, by a signal peptide of the sequence analysis": entry(lambda on, by, side, basis: on == "a signal peptide" and by == ("SignalP",)),
        "outside, by a signal peptide of UniProt's own rules": entry(lambda on, by, side, basis: on == "a signal peptide" and by == (OWN_RULES,)),
        "inside, nothing found": entry(lambda on, by, side, basis: on == "nothing found"),
        "by function": entry(lambda on, by, side, basis: basis == "by function"),
        "by function, on a place that names a PROSITE rule": entry(lambda on, by, side, basis: basis == "by function" and "PROSITE" in by),
        "of which on no other rule": entry(lambda on, by, side, basis: basis == "by function" and by == ("PROSITE",)),
        "by function, on a place that names a HAMAP rule": entry(lambda on, by, side, basis: basis == "by function" and "HAMAP" in by),
        "by function, on a place of UniProt's own rules alone": entry(lambda on, by, side, basis: basis == "by function" and by == (OWN_RULES,)),
        "stated, by likeness": entry(lambda on, by, side, basis: basis == "stated"),
    }
    # The words of the files are written for these kinds, and for no other.
    if models["predicted"] != sum(n for key, n in models.items() if key != "predicted"):
        raise SystemExit("a gene model's predicted side rests on something the files have no word for")
    if entries["predicted"] != sum(entries[key] for key in list(entries)[1:7]):
        raise SystemExit("an entry's predicted side rests on something the files have no word for")
    if entries["by function"] != entries["by function, on a place that names a PROSITE rule"] + entries["by function, on a place that names a HAMAP rule"] + entries["by function, on a place of UniProt's own rules alone"]:
        raise SystemExit("an entry is placed by function on a place whose rule system the files have no word for")
    if entry(lambda on, by, side, basis: basis == "stated" and by != ("likeness",)):
        raise SystemExit("a reviewed entry states a place on evidence the files have no word for")
    return {"gene models": models, "entries": entries}


def help_text(d, file):
    """One of UniProt's help pages as running text, without its markup."""
    content = json.loads(d.text(UPSTREAM, file))["content"]
    return re.sub(r"\s+", " ", re.sub(r"[#*`]", " ", re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", content)))


DTU_LICENCE = "Academic licence of DTU Health Tech: free to publicly funded academic, education or research institutions for internal research; any other user must obtain a commercial licence, and no use of the program may result in commercialization. It is a licence of the program: no clause speaks of predictions made with it"
PHOBIUS_TERMS = "For academic users only: the program may be used for private study, education or nonprofit research, and other users are asked to write to its author. The terms are of the program: they do not speak of predictions made with it"
UPSTREAM_SAID = [
    # (saved page, words it must contain): the terms of each tool as the files state them.
    *[(f"{tool}_licence.html", words) for tool in ("tmhmm", "signalp") for words in (
        f"ACADEMIC SOFTWARE LICENSE AGREEMENT FOR END-USERS AT PUBLICLY FUNDED ACADEMIC, EDUCATION OR RESEARCH INSTITUTIONS FOR THE USE OF {tool}",
        "If you are not a member of a publicly funded Academic and/or Education and/or Research Institution you must obtain a commercial license",
        "free non-exclusive license to use the Software for internal research purposes only",
        "Any use of the software which results in any form of commercialization is not allowed under this license",
    )],
    ("phobius_download.html", "Phobius is intended for academic users only"),
    ("phobius_download.html", "By downloading you agree to use the software only for private study, education or nonprofit research"),
    ("prosite_license.html", "distributed under the Creative Commons Attribution-NonCommercial-NoDerivatives (CC BY-NC-ND 4.0) License"),
    ("prosite_license.html", "Commercial users are asked to pay a yearly license fee"),
    ("prosite_license.html", "commercial users need their company to pay a license fee irrespective of the method by which they access the database"),
    ("hamap_about.html", "HAMAP is copyrighted by the SIB Swiss Institute of Bioinformatics and distributed under the Creative Commons Attribution (CC BY 4.0) License"),
    ("uniprot_help_sam.json", "TMHMM and Phobius predictors are used to infer transmembrane regions. If there is an overlap of at least 10 amino acids between TMHMM and Phobius results, the transmembrane region is annotated using the sequence ranges predicted by Phobius"),
    ("uniprot_help_sam.json", "TMHMM, SignalP and Phobius predictors are used to infer signal peptides"),
    ("uniprot_help_sam.json", "we annotate the sequence region predicted by SignalP"),
    ("uniprot_help_sam.json", "These methods are applied to UniProtKB sequences by InterPro to predict sequence features"),
    ("uniprot_help_unirule.json", "UniRule has been developed by merging existing manual rule-based systems (HAMAP, PIR name and site rules, NCBIfam rules and RuleBase rules) into one system"),
    ("uniprot_help_arba.json", "The Association-Rule-Based Annotator (ARBA) is one of the contributors to this pipeline"),
    ("uniprot_help_license.json", "We cannot provide unrestricted permission regarding the use of the data, as some data may be covered by patents or other rights"),
]


def check_upstream_terms(d):
    for file, words in UPSTREAM_SAID:
        page = help_text(d, file) if file.endswith(".json") else plain(d.text(UPSTREAM, file))
        if words not in page:
            raise SystemExit(f"{UPSTREAM}/{file} no longer says: {words}")
    if not re.search(r"contains \d+ documentation entries, \d+ patterns, \d+ profiles and \d+ ProRule", plain(d.text(UPSTREAM, "prosite_license.html"))):
        raise SystemExit("PROSITE's page no longer counts its rules among what it holds")
    # The two licences of DTU Health Tech are of the program: beyond the clauses on
    # commercialization and on benchmark tests, none speaks of results, output or predictions.
    for tool in ("tmhmm", "signalp"):
        page = plain(d.text(UPSTREAM, f"{tool}_licence.html"))
        agreement = page[page.index("ACADEMIC SOFTWARE LICENSE AGREEMENT"):]
        spoken = re.findall(r"(?i)[^.;]*\b(?:results?|outputs?|predictions?)\b[^.;]*", agreement)
        if len(spoken) != 2 or "commercialization" not in spoken[0] or "benchmark tests" not in spoken[1]:
            raise SystemExit(f"the licence of {tool} now speaks of results or output beyond the two clauses the files name; read it again")


def upstream_sources(d, rests):
    """The tools and rule systems whose results the two databases give out, each as a source
    of its own: its terms as its own page states them, the sources its results were read
    through, and what rests on it."""
    check_upstream_terms(d)
    models, entries = rests["gene models"], rests["entries"]
    nothing = "Nothing was downloaded from it but its statement of terms, and the program was not run here."
    day = lambda file: d.day(UPSTREAM, file)
    prosite = entries["in a membrane, by segments that carry a PROSITE rule"], entries["by function, on a place that names a PROSITE rule"], entries["of which on no other rule"]
    out = [
        {"name": "TMHMM", "url": "https://services.healthtech.dtu.dk/services/TMHMM-2.0/", "accessed": day("tmhmm_licence.html"), "licence": DTU_LICENCE, "class": NON_COMMERCIAL, "through": "WormBase ParaSite and UniProt",
         "holds": f"{nothing} WormBase ParaSite ran it and SignalP on the gene models' proteins: {models['predicted']:,} predicted sides rest on what the two found or did not find ({models['in a membrane, by helices']:,} in a membrane by helices, {models['one helix and a signal peptide, settled by this tool']:,} with one helix and a signal peptide, {models['outside, by a signal peptide']:,} outside by a signal peptide, {models['inside, nothing found']:,} inside because neither found anything). UniProt's sequence analysis keeps a segment where TMHMM and Phobius overlap: {entries['in a membrane, by segments of the sequence analysis']:,} entries are placed in a membrane by such segments, and {entries['inside, nothing found']:,} inside because nothing was found."},
        {"name": "SignalP", "url": "https://services.healthtech.dtu.dk/services/SignalP-5.0/", "accessed": day("signalp_licence.html"), "licence": DTU_LICENCE, "class": NON_COMMERCIAL, "through": "WormBase ParaSite and UniProt",
         "holds": f"{nothing} The gene models' sides are those counted under TMHMM. UniProt's sequence analysis gives the signal peptide SignalP predicts where TMHMM or Phobius bears it out: {entries['outside, by a signal peptide of the sequence analysis']:,} entries are placed outside by one."},
        {"name": "Phobius", "url": "https://phobius.sbc.su.se/download", "accessed": day("phobius_download.html"), "licence": PHOBIUS_TERMS, "class": NON_COMMERCIAL, "through": "UniProt",
         "holds": f"{nothing} The entries' segments and signal peptides are those counted under TMHMM and SignalP."},
        {"name": "PROSITE", "url": "https://prosite.expasy.org/prosite_license.html", "accessed": day("prosite_license.html"), "licence": "CC BY-NC-ND 4.0; commercial users are asked to pay a yearly licence fee", "class": NON_COMMERCIAL, "through": "UniProt",
         "holds": f"Nothing was downloaded from it but its statement of terms, and nothing of it is copied. Its rules are named in UniProt's entries as what stands behind a statement: {prosite[0]:,} entries are placed in a membrane by segments that carry one, and {prosite[1]:,} are placed by function on a stated place that names one, {prosite[2]:,} of them on no other rule."},
    ]
    hamap = entries["by function, on a place that names a HAMAP rule"]
    if hamap:
        out.append({"name": "HAMAP", "url": "https://hamap.expasy.org/hamap_about.html", "accessed": day("hamap_about.html"), "licence": "CC BY 4.0", "class": PERMISSIVE, "through": "UniProt",
                    "holds": f"Nothing was downloaded from it but its statement of terms. {hamap:,} {'entry is' if hamap == 1 else 'entries are'} placed by function on a place that one of its family rules states."})
    return out


def majority(sides):
    """The side most members sit on; of equals, the first in SIDE_TIE."""
    return max(SIDE_TIE, key=lambda side: (sides.get(side, 0), -SIDE_TIE.index(side)))


def ordered_sides(counts):
    return {side: counts[side] for side in SIDES if counts.get(side)}


def build_shelves(c, d, rows, atlas, facts):
    """shelves.json and shelf_members.tsv, with what the README and the summary say of them."""
    s = Shelves(c, d, rows, atlas)
    order = {row[1]: index for index, row in enumerate(rows)}
    names = c.entry_names

    members = defaultdict(list)
    for protein in sorted(s.family, key=order.get):
        members[s.family[protein]].append(protein)
    parts = defaultdict(list)
    for protein in sorted(s.part, key=order.get):
        parts[s.part[protein]].append(protein)

    district_order = [key for key, _, _ in DISTRICTS] + [OTHER_DISTRICT[0], NO_DISTRICT[0]]
    district = {family: s.district(found) for family, found in members.items()}
    families = sorted(members, key=lambda f: (district_order.index(district[f]), -len(members[f]), f))
    part_kind = lambda part: "superfamily" if part.startswith("IPR") else "other signature" if part == "other-signature" else "no signature"
    part_label = {"other-signature": "A domain, repeat or site signature, and no family or superfamily", "no-signature": "No signature of any kind"}
    part_rank = {"superfamily": 0, "other signature": 1, "no signature": 2}
    listed_parts = sorted(parts, key=lambda p: (part_rank[part_kind(p)], -len(parts[p]), p))

    # The members' files: families in their order, a new file where the next family would
    # take the file past its size; a family or a part larger than a file has one of its own.
    file_index, used, plan, sequence = 0, 0, {}, []
    for key in [*families, *listed_parts]:
        count = len(members[key]) if key in members else len(parts[key])
        if used and used + count > MEMBERS_PER_FILE:
            file_index, used = file_index + 1, 0
        plan[key] = (f"members-{file_index:02d}.json", [used, used + count])
        used += count
        sequence += members[key] if key in members else parts[key]
    if len(sequence) != len(rows) or len(set(sequence)) != len(rows):
        raise SystemExit("a protein is filed twice or not at all")

    family_rows, unit_families = [], defaultdict(list)
    for family in families:
        sides = Counter(s.placed[protein][0] for protein in members[family])
        units = sorted({unit for protein in members[family] for unit in s.units.get(protein, ())}, key=natural)
        spanning = any(s.roles.get(protein, set()) & SPANNING_ROLES for protein in members[family])
        side = majority(sides)
        if spanning and side != "in":
            raise SystemExit(f"{family} holds a unit's membrane-spanning products and does not come out in a membrane; read the predictions again")
        for unit in units:
            unit_families[unit].append(family)
        file, at = plan[family]
        family_rows.append([family, names[family]["name"], SHELF["id"], side, district[family], len(members[family]), ordered_sides(sides), file, at, units, s.where(members[family])])
    part_rows = []
    for part in listed_parts:
        sides = Counter(s.placed[protein][0] for protein in parts[part])
        file, at = plan[part]
        part_rows.append([part, names[part]["name"] if part.startswith("IPR") else part_label[part], part_kind(part), majority(sides), s.district(parts[part], loose=True), len(parts[part]), ordered_sides(sides), file, at])

    all_sides = Counter(side for side, _, _, _ in s.placed.values())
    bases = Counter((side, basis) for side, basis, _, _ in s.placed.values())
    no_family_sides = Counter(s.placed[protein][0] for protein in s.part)
    groups = []
    tally = lambda key: {"families": sum(1 for f in families if district[f] == key), "proteins": sum(len(members[f]) for f in families if district[f] == key)}
    for key, label, wanted in DISTRICTS:
        groups.append({"id": key, "label": label, "from": "Gene Ontology terms: " + ", ".join(f"{name} ({term})" for term, name in wanted), **tally(key)})
    groups.append({"id": OTHER_DISTRICT[0], "label": OTHER_DISTRICT[1], "from": "The family's proteins carry Gene Ontology terms, and none of the districts' terms", **tally(OTHER_DISTRICT[0])})
    groups.append({"id": NO_DISTRICT[0], "label": NO_DISTRICT[1], "from": "The family's proteins carry no Gene Ontology term", **tally(NO_DISTRICT[0])})

    models, entries = len(c.genes), len(c.entries)
    mart = "wbps-biomart-smedh1prjna885486"
    cite = {source["name"]: source["cite"] for source in atlas["sources"]}
    ambiguous = sum(1 for row in rows if row[0] == "wormbase_parasite" and s.helices.get(row[8].split()[0], 0) == 1 and row[8].split()[0] in s.signals)
    rests = rests_on(s, rows)
    upstream = upstream_sources(d, rests)
    # The predicted sides that rest on the three programs: every gene model's, and every
    # entry's but those whose segment or signal peptide a rule gives.
    all_predicted = rests["gene models"]["predicted"] + rests["entries"]["predicted"]
    by_programs = rests["gene models"]["predicted"] + sum(rests["entries"][key] for key in ("in a membrane, by segments of the sequence analysis", "outside, by a signal peptide of the sequence analysis", "inside, nothing found"))
    if all_predicted != sum(count for (_, basis), count in bases.items() if basis == "predicted"):
        raise SystemExit("the predicted sides are not all accounted for by what they rest on")
    header = {
        "format": SHELF_FORMAT,
        "species": "planarian",
        "made": d.last_day(),
        "from": f"{FULL_FILE}: {len(rows):,} proteins of {ORGANISM}, {models:,} gene models of one genome annotation and {entries:,} UniProtKB entries. Every one is predicted, from the genome or from transcripts; none was measured.",
        "predicted": True,
        "shelves": [SHELF],
        "groups": groups,
        "groups_from": (
            "A protein's Gene Ontology terms are those InterPro maps to any of its signatures and, for a UniProtKB entry, those UniProt gives the entry; a gene model takes also the terms of the entries joined to it. "
            "With every broader term (by the ontology's kind-of and part-of links), the protein falls in the first district, in the order listed, one of whose terms it carries. "
            "A family's members are one kind of protein, so it stands in the district most of its classed members fall in; of equal counts, the first listed. A part of no_family is a looser grouping: it stands in a district only if more than half of all its members fall there. The choice of the districts' terms and their order is the viewer's."
        ),
        "family_from": (
            f"A family is an InterPro entry of the type Family (InterPro {s.release}). A protein is filed under the narrowest family among its signatures: one that is not a broader kind of another it carries, by InterPro's tree of entries. "
            f"Where several unrelated families remain ({s.several:,} proteins), it is the deepest in that tree, then the one fewest proteins of this catalogue are in, then the first by accession. "
            "A gene model's signatures are those on any of its predicted proteins, as the catalogue lists them."
        ),
        "family_columns": ["id", "label", "shelf", "side", "group", "count", "sides", "file", "at", "units", "where"],
        "family_notes": {
            "side": "The side most of the family's members sit on; of equal counts, a membrane first.",
            "units": "The inventory units whose candidate products, in the planarian atlas, are members of this family.",
            "where": "The places in the cell that the same Gene Ontology terms name for at least half of the family's members that are given any: an annotation carried by signatures, not a prediction for these proteins. " + "; ".join(f"{key}: {name} ({term})" for key, term, name in WHERE) + ".",
        },
    }
    no_family = {
        "label": "No family assigned",
        "count": len(s.part),
        "sides": ordered_sides(no_family_sides),
        "parts_from": (
            "A protein with no family is filed under one part. If it carries an InterPro entry of the type Homologous superfamily, the part is that superfamily: a wider grouping than a family, by shared structure. "
            "Of several superfamilies it is the one fewest proteins of this catalogue carry, then the first by accession. The other two parts hold the proteins with only a domain, repeat or site signature, and those with no signature at all."
        ),
        "part_columns": ["id", "label", "kind", "side", "group", "count", "sides", "file", "at"],
    }
    tail = {
        "member_columns": ["id", "label", "gene", "side", "basis", "length", "unit", "marks"],
        "members_from": {
            "table": f"data/proteins/planarian/{MEMBERS_FILE}",
            "format": MEMBERS_FORMAT,
            "order": "The table's lines are the members in order: the families as listed here, then the parts of no_family as listed; within each, the catalogue's order. A family's members are the lines whose 'under' is its id.",
            "files": f"A file holds the members of consecutive families: a new file begins where the next family or part would take it past {MEMBERS_PER_FILE:,} members, so a family or a part is never split, and one larger than that has a file of its own. 'file' names the file and 'at' the first and one past the last of its members there.",
            "label": f"A member's label is its name in {FULL_FILE}; where that is empty, the label of the part it is filed under.",
            "step": "python3 tools/build_planarian_atlas.py members --out DIR writes the files from the two tables.",
        },
        "side_notes": {
            "predicted": (
                f"Gene models: TMHMM (membrane-spanning helices) and SignalP (signal peptides) as WormBase ParaSite ran them on each model's predicted proteins and gives them in its BioMart (release {WBPS_RELEASE[4:]}); the gene's longest predicted protein is read. "
                "One helix or more without a signal peptide, or two or more with one: in a membrane. A signal peptide and no helix: outside. Neither, on a model that begins with methionine: inside. "
                f"A signal peptide with exactly one helix ({ambiguous:,} models) is settled by this tool's own reading of the sequence, because TMHMM can take a signal peptide for a helix: "
f"a stretch of {HYDROPHOBIC_WINDOW} residues of which {HYDROPHOBIC_LEAST} or more are hydrophobic ({', '.join(sorted(HYDROPHOBIC))}) that starts at residue {SIGNAL_REACH + 1} or later puts it in a membrane; such a stretch only before that puts it outside. "
                "UniProtKB entries: the membrane-spanning segments and signal peptides that UniProt's automatic annotation gives the entry; its sequence analysis keeps a segment where TMHMM and Phobius overlap, and gives the signal peptide SignalP predicts where TMHMM or Phobius bears it out. "
                "Which membrane a protein spans is not predicted: the shelf stands for the cell's membranes together. "
                f"So {by_programs:,} of the {all_predicted:,} predicted sides rest on what TMHMM, SignalP and Phobius found or did not find. "
                "The three programs are given out for academic use; neither database's terms speak for them, and WormBase ParaSite says that third-party constraints may apply to what it gives out. Each is named among the sources, with its own terms and what rests on it."
            ),
            "by function": f"Taken from an annotation: for a UniProtKB entry with nothing predicted, the subcellular location UniProt's rules give it; for a protein whose beginning is missing and on which nothing was predicted, the place its Gene Ontology terms name, where that leaves no real doubt. Of the {rests['entries']['by function']:,} entries placed by a rule's location, {rests['entries']['by function, on a place that names a PROSITE rule']:,} rest on a statement that names a PROSITE rule; the others rest on UniProt's own rule systems or, for {rests['entries']['by function, on a place that names a HAMAP rule']:,}, on HAMAP's.",
            "stated": "A reviewed UniProtKB entry states the location, by similarity to another species' protein.",
            "not known": "Nothing was predicted and the protein's beginning is missing, so a signal peptide could be missing with it; or the two predictors cannot be told apart.",
        },
        "marks": {
            "helices": {"label": "Membrane-spanning segments predicted", "measured": False, "source": "WormBase ParaSite (TMHMM) for a gene model; UniProt for an entry"},
            "signal": {"label": "A signal peptide is predicted", "values": [True, False], "measured": False, "source": "WormBase ParaSite (SignalP) for a gene model; UniProt for an entry"},
            "kind": {"label": "What the line is", "values": ["gene model", "unreviewed entry", "reviewed entry"], "measured": False, "source": FULL_FILE},
            "same": {"label": "The other line of the same sequence: a gene model's UniProtKB entries, or an entry's gene model", "measured": False, "source": FULL_FILE},
        },
        "counts": {side: all_sides.get(side, 0) for side in SIDES},
        "by_basis": {side: {basis: bases[side, basis] for basis in ("stated", "predicted", "by function", "none") if bases.get((side, basis))} for side in SIDES},
        "rests_on": rests,
        "sources": [
            {
                "name": "WormBase ParaSite", "url": "https://parasite.wormbase.org/", "release": WBPS_RELEASE, "accessed": d.day(mart, "biomart_tmhmm.tsv"),
                "class": PERMISSIVE,
                "licence": "The database's disclaimer: \"Ensembl imposes no restrictions on access to, or use of, the data provided and the software used to analyse and present it. Ensembl data generated by members of the project are available without restriction.\" It goes on: \"Some of the data and software included in the distribution may be subject to third-party constraints. Users of the data and software are solely responsible for establishing the nature of and complying with any such restrictions.\" It asks that the genome's paper and the database be cited.",
                "cite": cite["WormBase ParaSite"],
                "holds": "the gene models; and, from its BioMart, the helices TMHMM predicts and the signal peptides SignalP predicts on each predicted protein",
            },
            {
                "name": "InterPro", "url": "https://www.ebi.ac.uk/interpro/", "release": s.release, "accessed": d.day("interpro-hierarchy-and-go", "ParentChildTreeFile.txt"), "licence": "CC0 1.0", "class": PERMISSIVE,
                "cite": cite["InterPro"],
                "holds": "the type and name of each entry, the tree of broader and narrower entries, and the mapping of entries to Gene Ontology terms",
            },
            {
                "name": "Gene Ontology", "url": "https://geneontology.org/", "release": s.ontology, "accessed": d.day("geneontology-go-basic", "go-basic.obo"), "licence": "CC BY 4.0", "class": PERMISSIVE,
                "cite": ontology_citation(d),
                "holds": "the names of terms and which term is a kind or a part of which; no term's text is copied beyond the names of the districts' and the places' terms",
            },
            {
                "name": "UniProt", "url": "https://www.uniprot.org/", "release": d.entry("uniprot-smed-topology", f"uniprotkb_{TAXON}_topology.json").get("x_uniprot_release") or facts["uniprot"], "accessed": d.day("uniprot-smed-topology", f"uniprotkb_{TAXON}_topology.json"), "licence": "CC BY 4.0", "class": PERMISSIVE,
                "cite": cite["UniProt"],
                "holds": "for each of the species' entries: the membrane-spanning segments, the signal peptide and the subcellular location it gives, whether the sequence's beginning is missing, and its Gene Ontology terms",
            },
            # The tools and rule systems whose results the two databases give out: each with
            # its own terms, the sources it was read through, and what rests on it.
            *upstream,
        ],
    }
    compact = lambda value: json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    lines = lambda items: "[\n" + ",\n".join("  " + compact(item) for item in items) + "\n ]"
    body = json.dumps(header, indent=1, ensure_ascii=False)[:-2]
    body += ',\n "families": ' + lines(family_rows)
    body += ',\n "no_family": ' + json.dumps(no_family, indent=1, ensure_ascii=False).replace("\n", "\n ")[:-3] + ',\n  "parts": ' + lines(part_rows).replace("\n", "\n ") + "\n }"
    body += "," + json.dumps(tail, indent=1, ensure_ascii=False)[1:] + "\n"
    json.loads(body)

    under = {**s.family, **s.part}
    table_rows = [[protein, under[protein], s.placed[protein][0], s.placed[protein][1], str(s.placed[protein][2]), "1" if s.placed[protein][3] else "0", ";".join(sorted(s.units.get(protein, ()), key=natural))] for protein in sequence]
    members_table = "\n".join("\t".join(row) for row in [MEMBERS_COLUMNS, *table_rows]) + "\n"

    sizes = sorted((len(found) for found in members.values()), reverse=True)
    report = {
        "shelves": s, "families": len(families), "in_families": len(s.family), "no_family": len(s.part), "several": s.several,
        "sizes": sizes, "largest": [(names[f]["name"], len(members[f])) for f in sorted(members, key=lambda f: (-len(members[f]), f))[:12]],
        "parts": Counter(part_kind(part) for part in parts), "part_proteins": Counter({kind: sum(len(parts[p]) for p in parts if part_kind(p) == kind) for kind in part_rank}),
        "largest_parts": [(names[p]["name"], len(parts[p])) for p in listed_parts[:8] if p.startswith("IPR")],
        "sides": all_sides, "bases": bases, "groups": groups, "files": file_index + 1, "ambiguous": ambiguous,
        "truncated": sum(1 for row in rows if row[0] == "wormbase_parasite" and not c.proteins[row[8].split()[0]]["sequence"].startswith("M")),
        "start_missing": sum(1 for known in s.topology.values() if known["start_missing"]),
        "agreement": s.agreement()[0], "settled": s.agreement()[1], "unit_families": {unit: found for unit, found in sorted(unit_families.items(), key=lambda item: natural(item[0]))},
        "with_terms": sum(1 for f in families if district[f] != NO_DISTRICT[0]), "with_where": sum(1 for row in family_rows if row[10]),
        "classed": Counter(s.classed.values()), "dropped": len(s.dropped),
        "by_kind": Counter((row[3] if row[0] == "uniprot" else "gene model", s.placed[row[1]][0], s.placed[row[1]][1]) for row in rows),
        "release": s.release, "ontology": s.ontology, "shelves_bytes": len(body.encode("utf-8")), "members_bytes": len(members_table.encode("utf-8")),
        "member_files": sorted({plan[key][0] for key in plan}), "largest_file": max(Counter(plan[key][0] for key in plan for _ in range(plan[key][1][1] - plan[key][1][0])).values()),
        "retired": len({sig for found in s.signatures.values() for sig in found if sig not in names}),
        "family_rows": family_rows, "part_rows": part_rows,
    }
    report["text"] = body
    return body, members_table, report


def cut_members(folder):
    """The members' files the page publishes beside it, cut from the two tables as
    shelves.json says: {file name: text}. Reads only the repository's files."""
    folder = Path(folder)
    shelves = json.loads((folder / SHELVES_FILE).read_text(encoding="utf-8"))
    catalogue = {}
    with open(folder / FULL_FILE, encoding="utf-8") as handle:
        header = handle.readline().rstrip("\n").split("\t")
        for line in handle:
            row = dict(zip(header, line.rstrip("\n").split("\t")))
            catalogue[row["id"]] = row
    placed = defaultdict(list)
    with open(folder / MEMBERS_FILE, encoding="utf-8") as handle:
        header = handle.readline().rstrip("\n").split("\t")
        for line in handle:
            row = dict(zip(header, line.rstrip("\n").split("\t")))
            placed[row["under"]].append(row)
    columns = shelves["member_columns"]
    family_at = {name: index for index, name in enumerate(shelves["family_columns"])}
    part_at = {name: index for index, name in enumerate(shelves["no_family"]["part_columns"])}
    files = defaultdict(list)
    groups = [(row[family_at["id"]], None, row[family_at["file"]], row[family_at["at"]]) for row in shelves["families"]]
    groups += [(row[part_at["id"]], row[part_at["label"]], row[part_at["file"]], row[part_at["at"]]) for row in shelves["no_family"]["parts"]]
    for key, fallback, file, at in groups:
        if len(files[file]) != at[0] or len(placed[key]) != at[1] - at[0]:
            raise SystemExit(f"the members of {key} are not where {SHELVES_FILE} says they are")
        for row in placed[key]:
            entry = catalogue[row["id"]]
            marks = {"helices": int(row["helices"]), "signal": row["signal"] == "1", "kind": entry["kind"]}
            if entry["match"]:
                marks["same"] = entry["match"].split(";")
            unit = row["units"].split(";") if row["units"] else None
            files[file].append([row["id"], entry["name"] or fallback or "", entry["gene"], row["side"], row["basis"], int(entry["length"]), unit, marks])
    compact = lambda value: json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    out = {}
    for file in sorted(files):
        head = {"format": MEMBERS_FORMAT, "species": shelves["species"], "file": file, "columns": columns}
        out[file] = json.dumps(head, indent=1, ensure_ascii=False)[:-2] + ',\n "members": [\n' + ",\n".join("  " + compact(member) for member in files[file]) + "\n ]\n}\n"
        json.loads(out[file])
    return out


def shelves_section(report, c, d, everything):
    """What the README says of the shelves' two files, from what the build counted."""
    sizes, sides, bases, kinds = report["sizes"], report["sides"], report["bases"], report["by_kind"]
    ones = sum(1 for size in sizes if size == 1)
    at_least = lambda n: (sum(1 for size in sizes if size >= n), sum(size for size in sizes if size >= n))
    parts, part_proteins = report["parts"], report["part_proteins"]
    agreement, settled = report["agreement"], report["settled"]
    both = sum(count for (model, entry), count in agreement.items() if model != "not known")
    same = sum(count for (model, entry), count in agreement.items() if model == entry)
    settled_same = sum(count for (model, entry), count in settled.items() if model == entry)
    unplaced_models = sum(count for (kind, side, _), count in kinds.items() if kind == "gene model" and side == "not known")
    unplaced_entries = sides["not known"] - unplaced_models
    districts = "\n".join(f"| {group['label']} | {group['families']:,} | {group['proteins']:,} | {group['from']} |" for group in report["groups"])
    largest = report["largest"]
    return f"""## `{SHELVES_FILE}` and `{MEMBERS_FILE}`: the proteins laid out for the atlas's shelves

The atlas shows every one of the {len(everything):,} proteins, grouped into families that open; the
form is fixed in `schema/SPECIES_PROTEINS.md`. `{SHELVES_FILE}` holds the families.
`{MEMBERS_FILE}` holds, for every protein, what it is filed under, its side of a membrane
and how that side is known.

**Everything here is a prediction on a predicted protein.** Nothing says that the animal
makes a protein, where it was seen, or which membrane it is in.

- **Families.** A family is an InterPro entry of the type Family (InterPro {report['release']}). {report['families']:,}
  families hold {report['in_families']:,} proteins. A protein is filed under the narrowest family among
  its signatures; for {report['several']:,} proteins several unrelated families remained and a rule
  chose one (the deepest in InterPro's tree, then the smallest here, then the first).
  {ones:,} families have one member and {at_least(10)[0]:,} have ten or more; the largest are
  {largest[0][0]} ({largest[0][1]:,}), {largest[1][0]} ({largest[1][1]:,}) and {largest[2][0]} ({largest[2][1]:,}).
- **No family.** {report['no_family']:,} proteins carry no family signature. None is dropped: they
  are listed under "No family assigned", in parts. {parts['superfamily']:,} parts are InterPro
  superfamilies, a wider grouping by shared structure, and hold {part_proteins['superfamily']:,}; {part_proteins['other signature']:,}
  proteins carry only a domain, repeat or site signature; {part_proteins['no signature']:,} carry no signature
  of any kind.
- **Sides.** {sides['in']:,} span a membrane, {sides['outside']:,} are beyond one, {sides['inside']:,} are inside the cell
  and {sides['not known']:,} are not placed. By how it is known: {sum(count for (_, basis), count in bases.items() if basis == 'predicted'):,} predicted,
  {sum(count for (_, basis), count in bases.items() if basis == 'by function'):,} by function, {sum(count for (_, basis), count in bases.items() if basis == 'stated'):,} stated.
- **How a side is predicted.** For a gene model: the helices TMHMM predicts and the signal
  peptide SignalP predicts on its longest predicted protein, as WormBase ParaSite holds
  them. For a UniProtKB entry: the membrane-spanning segments and the signal peptide
  UniProt's automatic annotation gives. `{SHELVES_FILE}` gives the rule in full
  (`side_notes`).
- **This tool's own reading, in one case.** {report['ambiguous']:,} gene models have one helix and a signal
  peptide, and TMHMM can take a signal peptide for a helix. Where the hydrophobic stretch
  lies in the sequence decides: {HYDROPHOBIC_WINDOW} residues of which {HYDROPHOBIC_LEAST} or more are hydrophobic
  ({', '.join(sorted(HYDROPHOBIC))}). At residue {SIGNAL_REACH + 1} or later it is taken for a membrane-spanning
  stretch, only before that for the signal peptide. The rule uses no published scale.
- **Not placed.** {unplaced_models:,} gene models and {unplaced_entries:,} entries. Their sequence lacks its
  beginning and nothing was predicted on the rest, so a signal peptide may be missing
  with it; {report['truncated']:,} gene models do not begin with methionine. A few have one helix and a
  signal peptide that could not be told apart.
- **How the predictions fare.** {sum(agreement.values()):,} UniProtKB entries are whole copies of a gene model's
  protein, and UniProt places them with other predictors (Phobius and SignalP). Where
  both are placed, the two agree on {same:,} of {both:,}. Of the {sum(settled.values())} pairs this tool's own
  reading settled, {settled_same} agree; the rule's two numbers were set while looking at
  those pairs, so that is not an independent test.
- **Which membrane is not predicted.** The one shelf stands for the cell's membranes
  together: a predicted helix says that a protein spans a membrane, not which. "Beyond a
  membrane" likewise covers the outside of the cell and the inside of its compartments.
  Where the Gene Ontology terms of a family's members name a place in the cell, the
  family carries it as a hint (`where`).
- **Tied to the atlas.** {len(report['unit_families'])} of the inventory's units have candidate products
  here; their families carry the units' ids, and every family that holds a
  membrane-spanning product comes out in a membrane.

A family, and a part of "No family assigned", stands in a district:

| District | Families | Their proteins | From |
| --- | ---: | ---: | --- |
{districts}

A protein's Gene Ontology terms are those InterPro maps to any of its signatures and
those UniProt gives a UniProtKB entry; a gene model takes also the terms of the entries
joined to it. The protein falls in the first district, in the order of the table, one of
whose terms it carries, and a family stands where most of its classed members fall. The
choice of the terms and their order is the viewer's.

### `{MEMBERS_FILE}`

{len(everything):,} lines under a header, tab-separated, in the order the shelves read them: the
families as `{SHELVES_FILE}` lists them, then the parts of "No family assigned"; within
each, the order of `{FULL_FILE}`.

| Column | Meaning |
| --- | --- |
| `id` | The protein's `id` in `{FULL_FILE}` |
| `under` | The InterPro family it is filed under; for a protein with no family, the part: a superfamily's accession, `other-signature` or `no-signature` |
| `side` | `in`, `outside`, `inside` or `not known` |
| `basis` | `predicted`, `by function`, `stated` or `none` |
| `helices` | How many membrane-spanning segments are predicted |
| `signal` | `1` if a signal peptide is predicted |
| `units` | The inventory units that list the protein as a candidate product in the planarian atlas |

**How a family's members are read.** A family's members are the lines whose `under` is
its id, in the table's order. For the page they are cut into {len(report['member_files'])} files of at most
{MEMBERS_PER_FILE:,} members where families allow (the largest holds {report['largest_file']:,}, one part alone): a
file holds consecutive families and a family is never split. `{SHELVES_FILE}` gives each
family's file and its place there (`file`, `at`). `python3
tools/build_planarian_atlas.py members --out DIR` writes the files; they are published
beside the page and are not kept in the repository."""


def build_readme(c, facts, atlas, listed, named, everything, report, d):
    models, entries = len(c.genes), len(c.entries)
    existence = Counter(row[8] for row in everything if row[0] == "uniprot")
    known = ["evidence at transcript level", "inferred from homology", "predicted", "evidence at protein level"]
    if sum(existence[level] for level in known) != entries or len(everything) != models + entries:
        raise SystemExit("the whole table no longer holds what the README says of it")
    library = library_facts(c)
    kept_models = sum(1 for row in listed if row[0] == "wormbase_parasite")
    table_sources = [s for s in atlas["sources"] if s["name"] in ("UniProt", "WormBase ParaSite", "InterPro")]
    rows = "\n".join(f"| [{s['name']}]({s['url']})" + (f", release {s['release']}" if s.get("release") else "") + f", read {s['accessed']} | {s['holds'][0].upper() + s['holds'][1:]} | {s['licence']} |" for s in table_sources)
    cites = "\n".join(f"- {s['name']}: {s['cite']}" for s in table_sources)
    more = len(listed) - named
    shelf_sources = json.loads(report["text"])["sources"]
    why_named = {
        PAPERS["gap_planarian"]: "It names the innexin smedinx-11, whose sequence record carries the name",
        PAPERS["gap_families"]: "Which animals have connexins and which have innexins is to be read there",
        PAPERS["hk"]: "It reports the proton-potassium pump, whose sequence record names it",
        PAPERS["trpa1"]: "It reports TRPA1, whose UniProtKB entry carries the name",
        PAPERS["inx13"]: "UniProtKB entries of innexins cite it as where their sequences were reported",
        PAPERS["inx1"]: "A UniProtKB entry of an innexin cites it as where its sequence was reported",
    }
    pointers = sorted((pmid for pmid in cited_in_atlas(c) if c.papers[pmid]["class"] != PERMISSIVE), key=lambda pmid: (c.papers[pmid]["short"].rsplit(" ", 1)[1], c.papers[pmid]["short"]))
    if set(pointers) != set(why_named):
        raise SystemExit(f"the papers that are pointers are not the ones the README explains: {sorted(c.papers[pmid]['short'] for pmid in pointers)}")
    if c.papers[PAPERS["wbps"]]["licence"] != "cc by-nc-nd" or c.papers[PAPERS["planmine"]]["licence"] != "cc by-nc":
        raise SystemExit("the papers cited for WormBase ParaSite and PlanMine no longer have the licences the README states")
    pointer_rows = "\n".join(f"| {c.papers[pmid]['citation']['text']} | {c.papers[pmid]['class']} | {why_named[pmid]} |" for pmid in pointers)
    shelf_rows = "\n".join(f"| [{s['name']}]({s['url']}), release {s['release']}, read {s['accessed']} | {s['holds'][0].upper() + s['holds'][1:]} | {s['licence']} |" for s in shelf_sources if not s.get("through"))
    upstream_rows = "\n".join(f"| {s['name']} | {s['through']} | {s['licence']} | {s['class']} | {s['holds'].split('. ', 1)[1]} |" for s in shelf_sources if s.get("through"))
    rests = json.loads(report["text"])["rests_on"]
    shelf_files = "\n".join(f"| `{source}` | `{file}` | {entry['retrieved_utc'][:10]} | `{entry['sha256']}` |" for (source, file), entry in sorted(d.read.items()))
    return f"""# Planarian proteins

Three things are recorded here for the planarian *{ORGANISM}*.

1. **The mass-spectrometry library of planarian proteins was not imported.** It was
   found, its terms were read, and its list of proteins could not be reached under terms
   that allow a copy. What was found and what is missing is set out below.
2. **`{FULL_FILE}` is the open set, brought in whole in the meantime** (the user's
   decision, 14 November 2026): the {len(everything):,} proteins on open record for the species,
   {models:,} gene models of one genome annotation and {entries:,} UniProtKB entries. They are
   predicted from the genome and from transcripts, not measured. It is not the library and
   does not stand in for it.
3. **`{REFERENCE_FILE}` holds the {len(listed)} of those lines that the planarian protein atlas
   draws on:** the {named} proteins it names and {more} more that are joined to them.
4. **`{SHELVES_FILE}` and `{MEMBERS_FILE}` lay the same {len(everything):,} proteins out for the
   atlas's shelves:** each is given one family, a side of a membrane and how that side is
   known, and the families open to show their members. Every one of these is a
   prediction on a predicted protein.

Generated by `tools/build_planarian_atlas.py`; do not edit. This is reference data for
the viewer's protein atlas. It is not the engine's protein catalogue, and nothing in the
engine reads it.

## The mass-spectrometry library: found, not imported

| | |
| --- | --- |
| The study | {library['authors']} ({library['year']}) {library['title']}. {library['journal']} doi:{library['citation']['doi']}, PubMed {library['citation']['pmid']} |
| What it reports | A spectral library of the proteins of *{ORGANISM}* detected by mass spectrometry. How many proteins it covers is in its abstract; the paper reserves all rights, so the number is not repeated here |
| Its public deposits | ProteomeXchange PXD042308 (iProX IPX0006394000, announced {library['announced']}): {library['raw']} instrument files and {library['other']} other files. ProteomeXchange PXD059861 (iProX IPX0010799000): {library['raw_second']} instrument files. GEO GSE232894: the study's RNA sequencing |
| Terms of the paper | "{library['rights']}" |
| Terms of the deposits | iProX's data licence puts datasets submitted since 23 March 2023 under CC0, and elsewhere limits what is taken from its site to personal use; both clauses are on record |
| What is missing | The list of the library's proteins. The {library['other']} files of the deposit that are not instrument files are run lists and sample sheets (the longest has {library['rows']} rows), not proteins. A search of Europe PMC's preprints and of the data repositories that DataCite indexes found no preprint and no other record of the library. The paper's own page, where its supplementary tables are listed, answered this tool with HTTP {library['refused']} on {library['refused_day']}, and the paper reserves all rights, so nothing was taken from it |
| Which reference its identifiers use | Not stated in any record that was read. The same study's RNA-sequencing table is indexed by {library['rna_rows']:,} identifiers that begin `{library['rna_prefix'][0]}`, which suggests, and does not show, the reference the library uses |
| Other proteomics of the species | Not examined, and not the library: {len(library['other_proteomics'])} public datasets of another group ({', '.join(library['other_proteomics'])}) |

An import would need one of two things: the authors' or the publisher's permission (or a
deposit of the library under an open licence); or a new protein list derived from the
deposit's instrument files, which is a mass-spectrometry reanalysis and not a download.

## `{FULL_FILE}`

{len(everything):,} lines, each one protein, tab-separated under a header line: {models:,} gene models
with a predicted protein, then {entries:,} UniProtKB entries. The columns are explained in the
next section.

- **Not measured.** A gene model is a prediction from the genome. Of the UniProtKB
  entries, UniProt marks {existence['evidence at transcript level']:,} "evidence at transcript level", {existence['inferred from homology']:,} "inferred from homology",
  {existence['predicted']:,} "predicted" and {existence['evidence at protein level']:,} "evidence at protein level"; the `note` column gives each
  entry's level.
- **Not the animal's proteome.** The gene models are those of one haplotype of one genome
  assembly, and the entries overlap them: {len(c.matches):,} entries are joined to a gene model
  (column `match`), so one protein can stand on two lines.
- **No sequences.** They stay with the saved responses, outside the repository.
- **Nothing here says which of these proteins the animal makes, where or when.** That is
  what the mass-spectrometry library measures.

## `{REFERENCE_FILE}`

{len(listed)} proteins, one per line: {kept_models} gene models and {len(listed) - kept_models} UniProtKB entries.
{named} are named by `data/proteins/atlases/planarian.json`; the other {more} are entries or
gene models joined to one that is. Tab-separated, with a header line. Each line is a line
of `{FULL_FILE}`.

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

The atlas's proteins were drawn from all {models:,} gene models and {entries:,} UniProtKB entries, which
are the lines of `{FULL_FILE}`.

A gene model is a prediction from one haplotype of one genome assembly
({facts['assembly']}, strain {facts['strain']}, annotation version {facts['annotation']}; BioProject
PRJNA885486, registered {facts['project_day']} by the {facts['project_by']}).
WormBase ParaSite counts {facts['coding_genes']:,} coding genes in it; the {models:,} searched are those with a
predicted protein (it marks the other {facts['untranslated']:,} as not translating). Sequences are not
in either file.

{origin(facts)}

An entry and a gene model are joined when at least {round(MATCH_SHARE * 100)}% of the entry's {MATCH_WORD}-residue
words occur in the model's predicted protein and no other gene reaches half of that
share; {len(c.matches):,} of the {entries:,} entries join a gene model this way. A join says the two are
copies of one sequence, not that either is confirmed in the animal.

{shelves_section(report, c, d, everything)}

## Where the proteins came from, and under what terms

| Source | What is taken | Terms |
| --- | --- | --- |
{rows}

Cite:

{cites}

For the shelves, more was taken from the same sources, and the Gene Ontology was added:

| Source | What the shelves take | Terms |
| --- | --- | --- |
{shelf_rows}

Every source in the two tables is permissive: its terms allow what is taken, with
attribution.

**What the two databases give out that a tool or a rule system computed.** The sides
are predictions, and the programs and rules that made them have terms of their own.
WormBase ParaSite's disclaimer says, after the sentence quoted above: "Some of the data
and software included in the distribution may be subject to third-party constraints.
Users of the data and software are solely responsible for establishing the nature of and
complying with any such restrictions." UniProt's licence page says: "We cannot provide
unrestricted permission regarding the use of the data, as some data may be covered by
patents or other rights." Each tool and rule system is listed here with its own terms,
read at its own page, and with what rests on it in `{SHELVES_FILE}`. Nothing was
downloaded from any of them but its page of terms, and no program was run.

| Tool or rule system | Read through | Its own terms | Class | What rests on it |
| --- | --- | --- | --- | --- |
{upstream_rows}

UniProt's help pages describe RuleBase, ARBA and the PIR rules as parts of its own
annotation pipeline. No terms were read for them apart from UniProt's, so they are not
classed separately: {rests['entries']["in a membrane, by segments of UniProt's own rules"] + rests['entries']["outside, by a signal peptide of UniProt's own rules"]:,} entries are placed by a segment or a signal peptide they give, and
{rests['entries']["by function, on a place of UniProt's own rules alone"]:,} by function on a place they state.

**Two kinds of terms.** The licences of TMHMM and SignalP and the terms of Phobius are of
the programs: they say who may run them and say nothing of predictions made with them,
and it was WormBase ParaSite and UniProt that ran them. PROSITE's terms are of the
database itself, of which its rules are part, and its page says that commercial users pay
a licence fee "irrespective of the method by which they access the database". Whether
sides that rest on the academic programs, or on PROSITE's rules, may stay in a commercial
project is the project's to decide and is not settled here. Until it is, every such side
is counted above and is said to be predicted wherever it is shown.

**Papers named, with nothing taken beyond a name.** The atlas names planarian genes by
the papers that reported them. A paper under CC BY may stand behind a name. A paper
whose terms do not allow a copy is a pointer: the name it is cited for stands in a
sequence record or a UniProtKB entry as well, and none of its findings is repeated.

| Paper | Class | Why it is named |
| --- | --- | --- |
{pointer_rows}

Two more papers are cited because their databases ask for it, and nothing is taken from
the papers themselves: {c.papers[PAPERS['wbps']]['short']} for WormBase ParaSite (the
paper is under CC BY-NC-ND) and {c.papers[PAPERS['planmine']]['short']} for PlanMine (under CC BY-NC).
The paper of the mass-spectrometry library reserves all rights; it is set out above.

The Gene Ontology asks for two papers to be cited, in its own words: {ontology_citation(d)}.
Its release here is {report['ontology']}. WormBase ParaSite's BioMart names TMHMM and
SignalP and no version of either; the licence read for each is the one DTU Health Tech
shows on its download page today.

The files read for the shelves, each in its dataset folder outside the repository and
checked against the SHA-256 its folder's MANIFEST gives:

| Folder | File | Retrieved | SHA-256 |
| --- | --- | --- | --- |
{shelf_files}

## How to rebuild

```bash
python3 tools/build_planarian_atlas.py fetch --evidence DIR --datasets DATA   # network; saves what is not yet there
python3 tools/build_planarian_atlas.py build --evidence DIR --datasets DATA   # offline; the same bytes every time
python3 tools/build_planarian_atlas.py members --out OUT                      # the shelves' member files, cut from the tables here
```

`DIR` holds the saved responses of the catalogue and the atlas, with `requests.json`, the
record of what was asked and when. `DATA` holds the shelves' downloads, one folder for
each source with a `MANIFEST.json` that gives every file's address, time and SHA-256.
Both are kept outside the repository. The build also writes
`data/proteins/atlases/planarian.json`. `docs/PLANARIAN_ATLAS.md` describes the method
and its limits.
"""


def build(evidence_folder, datasets_folder, snapshot):
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
    datasets = Datasets(datasets_folder)
    shelves, members, report = build_shelves(context, datasets, rows, atlas, facts)
    files = {
        "atlas": json.dumps(atlas, indent=1, ensure_ascii=False) + "\n",
        "reference": table(listed),
        "readme": build_readme(context, facts, atlas, listed, len(used), rows, report, datasets),
        "full": table(rows),
        "shelves": shelves,
        "members": members,
    }
    for name, text in files.items():
        if PATHS.search(text):
            raise SystemExit(f"the {name} would hold a machine path")
    # The limits the repository keeps: the families under 1 MB, no file over 3 MB, and what
    # the shelves add under about 1.5 MB.
    size = {name: len(text.encode("utf-8")) for name, text in files.items()}
    if size["shelves"] >= 1_000_000 or max(size.values()) >= 3_000_000 or size["shelves"] + size["members"] >= 1_600_000:
        raise SystemExit(f"the shelves' files have outgrown their limits: {size}")
    return files, atlas, context, report


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


def shelves_summary(report):
    sizes, s = report["sizes"], report["shelves"]
    at_least = lambda n: (sum(1 for size in sizes if size >= n), sum(size for size in sizes if size >= n))
    lines = [
        f"families: {report['families']:,} holding {report['in_families']:,} proteins; no family: {report['no_family']:,}; filed by a tie-break among unrelated families: {report['several']:,}",
        "  sizes: " + "; ".join(f">={n}: {at_least(n)[0]:,} families, {at_least(n)[1]:,} proteins" for n in (1, 2, 3, 5, 10, 20, 50)),
        f"  one-member families: {sum(1 for size in sizes if size == 1):,}; largest: {report['largest'][:6]}",
        f"no family, by part: {dict(report['parts'])} holding {dict(report['part_proteins'])}; largest superfamilies: {report['largest_parts'][:5]}",
        f"sides: {dict(report['sides'])}",
        f"side and basis: {dict(sorted(report['bases'].items()))}",
        f"gene models with one helix and a signal peptide: {report['ambiguous']:,}; models not beginning with M: {report['truncated']:,}; entries whose beginning is missing: {report['start_missing']:,}",
        "districts: " + "; ".join(f"{group['id']} {group['families']:,} families, {group['proteins']:,} proteins" for group in report["groups"]),
        f"families whose proteins carry a Gene Ontology term: {report['with_terms']:,}; with a place in the cell: {report['with_where']:,}; signatures no longer in InterPro: {report['retired']}; terms no longer usable: {report['dropped']}",
        f"proteins by the district their own terms give: {dict(report['classed'])}",
        f"member files: {report['files']}",
        "a whole UniProtKB entry against the gene model it is joined to (model side, entry side): " + str(dict(sorted(report["agreement"].items()))),
        "  of those, the models with one helix and a signal peptide: " + str(dict(sorted(report["settled"].items()))),
        "families that hold the atlas's products, by unit: " + "; ".join(f"{unit}: {', '.join(found)}" for unit, found in report["unit_families"].items()),
    ]
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("step", choices=["fetch", "build", "members"], help="fetch asks the databases and saves the answers; build reads only what was saved; members cuts the shelves' member files from the repository's tables")
    parser.add_argument("--evidence", help="fetch, build: the folder of saved responses (kept outside the repository)")
    parser.add_argument("--datasets", help="fetch, build: the folder of the shelves' downloads, one folder per source with a MANIFEST.json (kept outside the repository)")
    parser.add_argument("--refresh", action="store_true", help="fetch: ask again even where an answer is saved")
    parser.add_argument("--out-atlas", default=str(ATLAS))
    parser.add_argument("--out-reference", default=str(REFERENCE_DIR), help="the folder for the tables, shelves.json and their README.md")
    parser.add_argument("--out", help="members: the folder to write the member files into")
    args = parser.parse_args()
    if args.step == "members":
        if not args.out:
            parser.error("members needs --out")
        Path(args.out).mkdir(parents=True, exist_ok=True)
        for name, text in cut_members(args.out_reference).items():
            (Path(args.out) / name).write_text(text, encoding="utf-8")
            print(f"wrote {Path(args.out) / name} ({len(text.encode('utf-8')):,} bytes)")
        return
    if not args.evidence or not args.datasets:
        parser.error(f"{args.step} needs --evidence and --datasets")
    snapshot = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    if args.step == "fetch":
        failed = fetch(Path(args.evidence), snapshot, refresh=args.refresh)
        failed += fetch_datasets(Path(args.datasets), refresh=args.refresh)
        sys.exit(1 if failed else 0)
    files, atlas, context, report = build(Path(args.evidence), Path(args.datasets), snapshot)
    folder = Path(args.out_reference)
    targets = {"atlas": Path(args.out_atlas), "full": folder / FULL_FILE, "reference": folder / REFERENCE_FILE, "shelves": folder / SHELVES_FILE, "members": folder / MEMBERS_FILE, "readme": folder / "README.md"}
    for name, target in targets.items():
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(files[name], encoding="utf-8")
        print(f"wrote {target} ({len(files[name].encode('utf-8')):,} bytes)")
    print(summary(atlas, context))
    print(shelves_summary(report))


if __name__ == "__main__":
    main()
