#!/usr/bin/env python3
"""Build the viewer's data on the fruit fly, Drosophila melanogaster: the species with its levels and
placeholder outlines, its side of the protein atlas, and its own proteins on shelves.

Six files are written, each from saved answers of public databases:

    data/species/fruitfly.json           the species file (schema/SPECIES.md)
    data/species/shapes/fruitfly.json    placeholder outlines of the fly and its wings (schema/SPECIES_SHAPES.md)
    data/proteins/atlases/fruitfly.json  its side of the protein atlas (schema/SPECIES_ATLAS.md)
    data/proteins/fruitfly/              shelves.json, proteins.tsv and README.md (schema/SPECIES_PROTEINS.md,
                                         "A curated proteome"), for the whole reference proteome

The catalogue is UniProt's whole reference proteome of the fly, reviewed entries and unreviewed ones
(the user, 15 November 2026: "on whole reference proteome"). One protein is shown for each gene: the
one that UniProt's own gene-by-gene set of the proteome gives as canonical. The proteome's other
entries for the same gene are a count on it.

    python3 tools/build_fruitfly_atlas.py fetch --datasets DATA     the only step that uses the network
    python3 tools/build_fruitfly_atlas.py build --datasets DATA     the same bytes every time
    python3 tools/build_fruitfly_atlas.py members --out DIR         the members' files, for the page

DATA holds every species' downloads, one folder per source with a MANIFEST.json. The shelves'
machinery (the vocabulary of places, the placement, the families, the districts, the lines) is that
of tools/build_human_atlas.py, with the human's own table of an animal cell's shelves; the families
asked of every species are those of tools/build_mpneumoniae_atlas.py; the download step and the rule
on accessory families are those of tools/build_ecoli_atlas.py. A change to any of them shows in this
tool's byte-for-byte test.

This is the viewer's reference data. Nothing of the fly is in the engine. Standard library only.
"""

from __future__ import annotations

import argparse
import gzip
import json
import math
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
import build_human_atlas as H  # noqa: E402
import build_mpneumoniae_atlas as M  # noqa: E402
import build_ecoli_atlas as E  # noqa: E402

SNAPSHOT = ROOT / "data" / "proteins" / "inventory.snapshot.json"
SPECIES_FILE = ROOT / "data" / "species" / "fruitfly.json"
SHAPES_FILE = ROOT / "data" / "species" / "shapes" / "fruitfly.json"
ATLAS_FILE = ROOT / "data" / "proteins" / "atlases" / "fruitfly.json"
OUT_DIR = ROOT / "data" / "proteins" / "fruitfly"
PATHS = re.compile(r"/(?:home|mnt|Users|tmp)/")
MINE = "the visualizer's fruit fly agent"
TOOL = "tools/build_fruitfly_atlas.py"

SPECIES_ID, LABEL, ORGANISM, TAXON, PROTEOME = "fruitfly", "Fruit fly", "Drosophila melanogaster", 7227, "UP000000803"
UNIPROT = "https://rest.uniprot.org"
GENE_SETS = "https://ftp.uniprot.org/pub/databases/uniprot/current_release/knowledgebase/reference_proteomes"
KB = "fruitfly/uniprot-fruitfly-reference-proteome"
FLYBASE = "fruitfly/terms-flybase"
HUMAN_KB, KB_DOCS, IPR, GO, BIG_PI = "human/uniprot-human-reviewed-proteome", "human/uniprot-docs-and-terms", "human/interpro-entries-tree-and-go", "human/geneontology-go-basic", "human/terms-big-pi"
PLACES_FILE = f"uniprotkb_{PROTEOME}_places.json.gz"
SIGNATURES_FILE = f"uniprotkb_{PROTEOME}_signatures.tsv.gz"
CANONICAL_FILE = f"{PROTEOME}_{TAXON}.fasta.gz"
ALL = f"(proteome:{PROTEOME})"
PLACE_FIELDS = "accession,id,protein_name,gene_primary,xref_flybase,length,protein_existence,cc_subcellular_location,ft_transmem,ft_intramem,ft_signal,ft_transit,ft_topo_dom,ft_lipid,cc_alternative_products,fragment"
FLYBASE_TERMS = r"All annotations and data produced by FlyBase that are accessible from flybase\.org are distributed under a Creative Commons Attribution 4\.0 International License \(CC BY 4\.0\)"

SOURCES = {
    KB: {"what": f"UniProtKB: every entry of the reference proteome {PROTEOME} of Drosophila melanogaster, reviewed and unreviewed, with its name, gene, FlyBase gene, length, level of evidence, stated places with the evidence for each, segments, signals and anchors; the InterPro entries and Gene Ontology terms of each; the proteome's record and counts; UniProt's gene-by-gene set of the proteome (one protein for each gene) with the page that explains it; and UniProt's help page on its automatic annotation", "licence": "CC BY 4.0"},
    FLYBASE: {"what": "FlyBase's own statement of its licences, read before linking to it. Nothing else of FlyBase was downloaded", "licence": "CC BY 4.0 for its annotations and data, as the page states"},
}

# Places that fly entries state and the human's table has no line for (filled as the build asks).
PLACES_MORE = {}

# What stands behind a statement, by UniProt's evidence codes. A reviewed entry's are a curator's;
# an unreviewed entry's are automatic: a rule system (ARBA, UniRule) or a program named on the feature.
RULE_CODES = {"ECO:0000255", "ECO:0000256", "ECO:0000259"}
# ECO:0000312, a statement a curator took over from another database (one entry has it), is counted with the curator's own.
WORDS = {"ECO:0000269": "experiment", "ECO:0000250": "similarity", "ECO:0000305": "curator", "ECO:0000303": "curator", "ECO:0000312": "curator", **{code: "rule" for code in RULE_CODES}}
UPSTREAM = ["PROSITE", "HAMAP", "TMHMM", "Phobius", "SignalP", "TargetP", "Memsat", "Predotar", "big-PI"]
OWN_SYSTEMS = ("ARBA", "RuleBase", "PIRNR", "SAAS", "unnamed analysis")  # UniProt's own rule systems and analyses
OWNERS = {"PROSITE-ProRule", "HAMAP-Rule", "segments", "signal", "big-PI", "TMHMM", "Phobius", "SignalP", *OWN_SYSTEMS}
TABLE_COLUMNS = [*H.TABLE_COLUMNS, "reviewed", "entries"]

GENE_DB = ("FlyBase", "FBgn")  # the database whose gene identifiers tie a gene's entries together, and how they begin
listed, plural = E.listed, E.plural


def some(names, most=10):
    names = list(names)
    return listed(names) if len(names) <= most else ", ".join(names[:most]) + f" and {len(names) - most} more"


# ---------------------------------------------------------------------------------------
# Fetch (the download step of the E. coli tool, with this tool's requests)
# ---------------------------------------------------------------------------------------

def requests():
    out = []

    def add(source, file, url, purpose, **more):
        out.append({"source": source, "file": file, "url": url, "purpose": purpose, **more})

    q = H.q
    stream = f"{UNIPROT}/uniprotkb/stream?query={q(ALL)}&compressed=true"
    add(KB, PLACES_FILE, f"{stream}&format=json&fields={PLACE_FIELDS}", "every entry of the proteome: its name, gene, FlyBase gene, length and level of evidence, where the entry places it and on what evidence, its segments, signals and anchors", gzip=True)
    add(KB, SIGNATURES_FILE, f"{stream}&format=tsv&fields=accession,xref_interpro,go_id", "the InterPro entries and the Gene Ontology terms UniProt gives each entry", gzip=True)
    count = lambda query: f"{UNIPROT}/uniprotkb/search?query={q(query)}&size=1&fields=accession&format=json"
    for name, query in (("all", ALL), ("reviewed", f"{ALL} AND (reviewed:true)"), ("unreviewed", f"{ALL} AND (reviewed:false)"), ("reviewed_with_place", f"{ALL} AND (reviewed:true) AND (cc_scl_term:*)"), ("unreviewed_with_place", f"{ALL} AND (reviewed:false) AND (cc_scl_term:*)")):
        add(KB, f"count_{name}.json", count(query), f"how many entries of the proteome: {name.replace('_', ' ')} (the count is in the answer's header)")
    add(KB, f"proteome_{PROTEOME}.json", f"{UNIPROT}/proteomes/{PROTEOME}", "the proteome's own record: its counts and its genome assembly")
    add(KB, CANONICAL_FILE, f"{GENE_SETS}/Eukaryota/{PROTEOME}/{CANONICAL_FILE}", "UniProt's gene-by-gene set of the proteome: one protein for each gene. Only the names of its entries are read", gzip=True)
    add(KB, "reference_proteomes_README.txt", f"{GENE_SETS}/README", "UniProt's explanation of the gene-by-gene sets of its reference proteomes", contains="gene")
    add(KB, "help_arba.json", f"{UNIPROT}/help/arba", "UniProt's help page on ARBA, the rule system behind most statements of its unreviewed entries", contains="ARBA")
    add(FLYBASE, "flybase_about.html", "https://wiki.flybase.org/wiki/FlyBase:About", "FlyBase's statement of its licences", contains="FlyBase")
    return out


def fetch(datasets, refresh=False):
    E.requests, E.SOURCES, E.MINE, E.TOOL = requests, SOURCES, MINE, TOOL
    return E.fetch(datasets, refresh=refresh)


# ---------------------------------------------------------------------------------------
# Reading the entries: reviewed and unreviewed alike
# ---------------------------------------------------------------------------------------

def evidence_of(evidences, unknown):
    codes = {item["evidenceCode"] for item in evidences or []}
    if not codes:
        return H.NOT_GIVEN
    unknown.update(codes - set(WORDS))
    words = {WORDS[code] for code in codes if code in WORDS}
    return next((word for word in ("experiment", "similarity", "curator", "rule") if word in words), H.NOT_GIVEN)


def owner_of(item):
    """The rule system or the program an evidence names: a curator's sequence analysis names none."""
    source = item.get("source")
    if source == "SAM":  # UniProt's automatic sequence analysis names the program on the feature
        return item.get("id") or "unnamed analysis"
    return source or (H.ANALYSIS if item["evidenceCode"] == "ECO:0000255" else "unnamed analysis")


def behind(evidences):
    codes = {item["evidenceCode"] for item in evidences or []}
    if not codes:
        return (H.NOT_GIVEN,)
    if codes - RULE_CODES:
        return (H.OTHER,)
    return tuple(sorted({owner_of(item) for item in evidences}))


def rules_named(evidences):
    return sorted({f"{item['source']}:{item.get('id')}" for item in evidences or [] if item["evidenceCode"] in RULE_CODES and item.get("source") not in (None, "SAM")})


def read_entries(d, vocabulary):
    """Every entry of the proteome, as H.read_entries reads the human's reviewed ones, with what an
    unreviewed entry adds: whether it is reviewed, and its FlyBase genes."""
    results = json.loads(d.text(KB, PLACES_FILE))["results"]
    entries, counts, unknown_codes, unknown_places = {}, Counter(), Counter(), Counter()
    for item in results:
        accession = item["primaryAccession"]
        reviewed = item["entryType"].startswith("UniProtKB reviewed")
        description = item["proteinDescription"]
        name = (description.get("recommendedName") or (description.get("submissionNames") or [{}])[0]).get("fullName", {}).get("value", "")
        genes = item.get("genes") or []
        gene = next((g[key]["value"] for g in genes for key in ("geneName", "orderedLocusNames", "orfNames") if isinstance(g.get(key), dict)), "")
        if not gene and genes:
            gene = next((names[0]["value"] for g in genes for key in ("orfNames", "orderedLocusNames") for names in [g.get(key) or []] if names), "")
        flybase = sorted({ref["id"] for ref in item.get("uniProtKBCrossReferences", []) if ref["database"] == GENE_DB[0] and ref["id"].startswith(GENE_DB[1])})
        features = Counter(feature["type"] for feature in item.get("features", []))
        displayed, described = None, 0
        for comment in item.get("comments", []):
            if comment["commentType"] == "ALTERNATIVE PRODUCTS":
                for isoform in comment.get("isoforms", []):
                    status = isoform.get("isoformSequenceStatus")
                    if status == "Displayed":
                        displayed = isoform["name"]["value"]
                    described += status == "Described"
        comments, states = [], False
        for comment in item.get("comments", []):
            if comment["commentType"] != "SUBCELLULAR LOCATION" or not comment.get("subcellularLocations"):
                continue
            states = True
            note = " ".join(text.get("value", "") for text in comment.get("note", {}).get("texts", []))
            if note.startswith("(Microbial infection)"):
                continue
            comments.append(comment)
        counts["reviewed, states a place" if reviewed else "unreviewed, states a place"] += states
        general = [comment for comment in comments if not comment.get("molecule")]
        of = None
        if general:
            chosen = general
        elif any(comment["molecule"] == f"Isoform {displayed}" for comment in comments):
            chosen = [comment for comment in comments if comment["molecule"] == f"Isoform {displayed}"]
        elif comments:
            of = comments[0]["molecule"]
            chosen = [comment for comment in comments if comment["molecule"] == of]
        else:
            chosen = []
        statements = []
        for comment in chosen:
            for stated in comment["subcellularLocations"]:
                term = vocabulary.terms.get(stated["location"].get("id"))
                if term is None or term["kind"] != "location" or term["path"] != stated["location"]["value"]:
                    raise SystemExit(f"{accession} states a place the vocabulary does not hold as written: {stated['location']}")
                line = vocabulary.resolve(term["name"])
                if line is None:
                    unknown_places[term["name"]] += 1
                    continue
                topology, face = stated.get("topology"), stated.get("orientation")
                for part, kind in ((topology, "topology"), (face, "face")):
                    known = vocabulary.terms.get(part.get("id"), {}) if part else None
                    if part and (known.get("kind") != kind or known.get("path") != part["value"]):
                        raise SystemExit(f"{accession} states a {kind} the vocabulary does not hold as written: {part}")
                location = stated["location"].get("evidences")
                statements.append({
                    "name": term["name"], "words": stated["location"]["value"], "accession": term["accession"], "shelf": line[0], "kind": line[1], "under": line[3],
                    "topology": topology["id"] if topology else None, "topology_words": topology["value"] if topology else None,
                    "face": vocabulary.terms[face["id"]]["name"] if face else None, "face_accession": face["id"] if face else None,
                    "evidence": evidence_of(location, unknown_codes), "by_rule": sorted({owner_of(source) for source in location or [] if source["evidenceCode"] in RULE_CODES and source.get("source")}),
                    "topology_evidence": evidence_of(topology.get("evidences"), unknown_codes) if topology else None,
                    "behind": behind(location), "rules": rules_named(location),
                    "topology_behind": behind(topology.get("evidences")) if topology else None,
                    "face_behind": behind(face.get("evidences")) if face else None,
                })
        of_type = lambda kind: [evidence for feature in item.get("features", []) if feature["type"] == kind for evidence in feature.get("evidences", [])]
        entries[accession] = {
            "id": accession, "name": name, "gene": gene, "length": item["sequence"]["length"], "reviewed": reviewed, "flybase": flybase,
            "seen": int(item["proteinExistence"].split(":")[0]), "isoforms": 1 + described,
            "statements": statements, "of": of, "segments": features["Transmembrane"], "signal": features["Signal"] > 0,
            "segments_only_predicted": bool(features["Transmembrane"]) and not ({e["evidenceCode"] for e in of_type("Transmembrane")} - RULE_CODES),
            "signal_only_predicted": features["Signal"] > 0 and not ({e["evidenceCode"] for e in of_type("Signal")} - RULE_CODES),
            "segments_behind": behind(of_type("Transmembrane")) if features["Transmembrane"] else None,
            "signal_behind": behind(of_type("Signal")) if features["Signal"] else None,
        }
    if unknown_codes or unknown_places:
        raise SystemExit(f"evidence codes the table does not know: {dict(unknown_codes)}; places the table has no line for: {dict(unknown_places)}")
    if len(entries) != len(results):
        raise SystemExit("two entries share an accession")
    return entries, counts


def canonical(d):
    """UniProt's gene-by-gene set of the proteome: the accessions of its entries, in the file's order."""
    found = [line.split("|")[1] for line in d.text(KB, CANONICAL_FILE).splitlines() if line.startswith(">")]
    if len(found) != len(set(found)):
        raise SystemExit("the gene-by-gene set names an entry twice")
    return found


def adopt(catalogue):
    """Give the shared machinery this organism's folders, and its catalogue: one protein for each gene."""
    H.KB, H.KB_DOCS, H.IPR, H.GO = KB, KB_DOCS, IPR, GO
    H.PLACES_FILE, H.SIGNATURES_FILE = PLACES_FILE, SIGNATURES_FILE
    H.PLACES = {**H.PLACES, **PLACES_MORE}

    def read_signatures(d, entries):
        lines = d.text(KB, SIGNATURES_FILE).splitlines()
        if lines[0].split("\t") != ["Entry", "InterPro", "Gene Ontology IDs"]:
            raise SystemExit("UniProt's table of signatures and terms is not the one asked for")
        signatures, terms = {}, {}
        for line in lines[1:]:
            accession, found, ontology = line.split("\t")
            if accession in entries:
                signatures[accession] = [signature for signature in found.split(";") if signature]
                terms[accession] = [term.strip() for term in ontology.split(";") if term.strip()]
        if set(signatures) != set(entries):
            raise SystemExit("the table of signatures does not hold every protein of the catalogue; fetch both again")
        return signatures, terms

    H.read_signatures = read_signatures


# ---------------------------------------------------------------------------------------
# The outlines: a fly with its wings folded back, as a placeholder
# ---------------------------------------------------------------------------------------

BODY_UM, WING_UM = 2500, 2000  # the picture's choice: no measurement was read for this file


def outlines():
    hump = lambda x, start, end, peak: peak * math.sin(math.pi * (x - start) / (end - start)) ** 0.55 if start < x < end else 0
    body = []
    for x in range(0, BODY_UM + 1, 50):
        wide = max(hump(x, 0, 520, 700), hump(x, 430, 1420, 880), hump(x, 1300, BODY_UM, 900))
        high = max(hump(x, 0, 520, 620), hump(x, 430, 1420, 920), hump(x, 1300, BODY_UM, 780))
        body.append([x, 0, 0, round(wide), round(high)])
    wing = lambda side: [[round(950 + WING_UM * t), round(430 + 60 * t), round(side * (260 + 120 * t)), round(880 * math.sin(math.pi * t) ** 0.55) if 0 < t < 1 else 0, 14 if 0 < t < 1 else 0] for t in [step / 20 for step in range(21)]]
    wing_look = {"rings": {"every": 4, "first": 2, "points": 18}, "lines": [0.5, 1.5], "strength": 0.8, "alone": 0.95, "edge": 0.8, "pick": 10}
    return {
        "format": "cells.visualizer.outline@1",
        "note": f"A fruit fly with its wings folded back over its body, as placeholder outlines. The fly is drawn {BODY_UM / 1000:g} mm long and each wing {WING_UM / 1000:g} mm long: these sizes, the widths and the proportions are the picture's choice, and no measurement was read for them. The numbers were written out by tools/build_fruitfly_atlas.py from three rounded humps for the head, the thorax and the abdomen, and one flat blade for each wing.",
        "tissue_on": {"at_um": [1950, 468, -320], "clearance_um": 3, "note": "On the left wing, about half-way along it."},
        "parts": [
            {"name": "body", "kind": "loft", "stations": body, "rings": {"from": 0.04, "to": 0.97, "step": 0.04, "points": 28}, "lines": [0.25, 0.5, 0.75, 1.25, 1.5, 1.75], "strength": 0.5, "edge": 1, "fill": 0.07, "pick": 20, "context": {"edge": 0.4, "fill": 0.06}},
            {"name": "left wing", "group": "wings", "kind": "loft", "stations": wing(-1), **wing_look},
            {"name": "right wing", "group": "wings", "kind": "loft", "stations": wing(1), **wing_look},
        ],
    }


# ---------------------------------------------------------------------------------------
# Build
# ---------------------------------------------------------------------------------------

NOTHING = {
    "U18": "The inventory gives this unit no gene product: it is a default shape of current, not a named channel.",
    "U34": "A background conductance that the inventory ties to no protein.",
    "U35": "A lumped permeability of the whole membrane, not a population of proteins.",
    "U46": "A slot that each model configuration fills with a transporter of its own; it has no fixed protein in any species.",
    "U48": "A protein cage designed in the laboratory, with no gene in any organism, so there is nothing to look for in this one.",
    "U49": "A lumped water permeability of the membrane; water channels (aquaporins) are not part of it.",
}


# Proteins a reader would look for under a unit that the search by signature does not list.
NEAR = {"U11": ["Shab"], "U12": ["Shab"]}


def build(datasets_folder, snapshot):
    d = H.Datasets(datasets_folder)
    E.KB_DOCS, E.IPR, E.GO = KB_DOCS, IPR, GO
    must = lambda source, file, pattern, field=None: re.search(pattern, json.loads(d.text(source, file))[field] if field else H.plain(d.text(source, file))) or sys.exit(f"{source}/{file} no longer states its terms as they were read; read the page again before building")
    must(KB_DOCS, "terms_uniprot_license.json", r"We have chosen to apply the \[?Creative Commons Attribution 4\.0 International \(CC BY 4\.0\) License\]?(\([^)]*\))? to all copyrightable parts of our databases", "content")
    must(IPR, "terms_interpro_license.html", r"All of the InterPro, Pfam, PRINTS and SFLD downloadable data provided on the InterPro website is freely available under CC0 1\.0 Universal")
    must(GO, "go_citation_policy.html", r"licensed under the Creative Commons Attribution 4\.0 Unported License")
    # The fetch step asks for FlyBase's statement of its licences; the build does not need it, since nothing of FlyBase is taken.
    must(KB, "help_arba.json", r"ARBA", "content")
    must(*H.SAVED_TERMS["prosite"], r"distributed under the Creative Commons Attribution-NonCommercial-NoDerivatives \(CC BY-NC-ND 4\.0\) License")
    must(*H.SAVED_TERMS["hamap"], r"distributed under the Creative Commons Attribution \(CC BY 4\.0\) License")
    for tool in ("tmhmm", "signalp", "targetp"):
        must(*H.SAVED_TERMS[tool], rf"ACADEMIC SOFTWARE LICENSE AGREEMENT FOR END-USERS AT PUBLICLY FUNDED ACADEMIC, EDUCATION OR RESEARCH INSTITUTIONS FOR THE USE OF {tool}")
    must(*H.SAVED_TERMS["phobius"], r"Phobius is intended for academic users only")
    must(BIG_PI, "gpi_server.html", r"big-PI Predictor")
    must(KB_DOCS, "help_transmem.json", r"predicted by the application of the predictive tools TMHMM, Memsat, Phobius and the hydrophobic moment plot method", "content")
    must(KB_DOCS, "help_signal.json", r"predicted by the application of the predictive tools Phobius, Predotar, SignalP and TargetP", "content")

    adopt(None)
    vocabulary = H.Vocabulary(d)
    every, read = read_entries(d, vocabulary)
    release = d.entry(KB, PLACES_FILE)["x_uniprot_release"]
    proteome = json.loads(d.text(KB, f"proteome_{PROTEOME}.json"))
    total = {name: d.total(KB, f"count_{name}.json") for name in ("all", "reviewed", "unreviewed", "reviewed_with_place", "unreviewed_with_place")}
    if any(d.entry(KB, file)["x_uniprot_release"] != release for file in (SIGNATURES_FILE, "count_all.json", "count_reviewed.json", "count_unreviewed.json")) or vocabulary.release != release:
        raise SystemExit("the downloads from UniProt are not of one release; fetch them again")
    if total["all"] != len(every) or total["reviewed"] != sum(1 for e in every.values() if e["reviewed"]) or total["reviewed"] + total["unreviewed"] != total["all"] or proteome["proteinCount"] != total["all"] or proteome["taxonomy"]["taxonId"] != TAXON:
        raise SystemExit(f"the entries read do not add up to UniProt's own counts: {total}")
    if total["reviewed_with_place"] != read["reviewed, states a place"] or total["unreviewed_with_place"] != read["unreviewed, states a place"]:
        raise SystemExit(f"the entries that state a place are not as many as UniProt's search finds: {dict(read)} against {total}")

    # --- the catalogue: one protein for each gene, as UniProt's gene-by-gene set gives it ---------------
    chosen = canonical(d)
    missing = [accession for accession in chosen if accession not in every]
    if missing:
        raise SystemExit(f"{len(missing)} proteins of the gene-by-gene set are not entries of the proteome as fetched ({missing[:5]}); fetch both again")
    entries = {accession: every[accession] for accession in chosen}
    of_gene = defaultdict(set)
    for accession, entry in every.items():
        for gene_id in entry["flybase"]:
            of_gene[gene_id].add(accession)
    together = {accession: len(set().union({accession}, *(of_gene[gene_id] for gene_id in entry["flybase"]))) for accession, entry in entries.items()}
    covered = set().union(set(entries), *(of_gene[gene_id] for entry in entries.values() for gene_id in entry["flybase"]))
    stated = {
        "entries": total["all"], "reviewed": total["reviewed"], "unreviewed": total["unreviewed"], "genes": proteome["geneCount"],
        "shown": len(entries), "shown_reviewed": sum(1 for e in entries.values() if e["reviewed"]), "shown_unreviewed": sum(1 for e in entries.values() if not e["reviewed"]),
        "further": total["all"] - len(entries), "further_tied_to_a_shown_gene": len(covered) - len(entries), "no_flybase_gene": sum(1 for e in entries.values() if not e["flybase"]),
    }
    if abs(stated["shown"] - stated["genes"]) > 0.01 * stated["genes"]:
        raise SystemExit(f"the gene-by-gene set holds {stated['shown']:,} proteins and the proteome counts {stated['genes']:,} genes")
    adopt(entries)
    filing = H.Filing(d, entries)
    placed = {accession: H.place(entry, vocabulary) for accession, entry in entries.items()}
    gene = lambda accession: entries[accession]["gene"] or accession
    order = lambda accessions: sorted(set(accessions), key=lambda a: H.natural(gene(a).lower()))
    by_gene = lambda accessions: [gene(a) for a in order(accessions)]

    # --- the atlas: the families behind Cells' units, asked of this organism ---------------------------
    carriers = defaultdict(list)
    for accession, found in filing.signatures.items():
        for signature in found:
            carriers[signature].append(accession)
    human_lines = d.text(HUMAN_KB, "uniprotkb_UP000005640_reviewed_signatures.tsv.gz").splitlines()[1:]
    human_signatures = {line.split("\t")[0]: set(line.split("\t")[1].split(";")) for line in human_lines}
    signature_name = lambda signature: filing.names[signature]["name"]
    carried = lambda family: order(accession for signature in family["signatures"] for accession in carriers.get(signature, []))
    said = lambda families: f"{listed(family['of'] for family in families)} ({', '.join(signature for family in families for signature in family['signatures'])})"
    units, unit_of, beside = {}, defaultdict(set), {}
    for unit in snapshot["units"]:
        spec = M.UNITS[unit["id"]]
        if spec.get("finding"):
            units[unit["id"]] = {"finding": spec["finding"], "note": NOTHING[unit["id"]], "products": []}
            continue
        families = [(key, M.FAMILIES[key]) for key in spec["parts"]]
        candidates = [product["human_uniprot"] for product in unit.get("products") or [] if product.get("human_uniprot")]
        for _, family in families:
            if family.get("human", True) and not any(set(family["signatures"]) & human_signatures.get(candidate, set()) for candidate in candidates):
                raise SystemExit(f"{unit['id']}: none of its human candidates carries the signature of {family['of']}; the question is not the unit's")
        own = [family for key, family in families if key not in E.ACCESSORY and family.get("human", True)]      # the families the engine's law names
        other = [family for key, family in families if key not in E.ACCESSORY and not family.get("human", True)]  # another family that makes the same machine
        going_with = [family for key, family in families if key in E.ACCESSORY]
        if any(carried(family) for family in own):
            finding, shown = "found", [family for family in [*own, *going_with] if carried(family)]
        elif any(carried(family) for family in other):
            finding, shown = "different family", [family for family in other if carried(family)]
        else:
            finding, shown = "none found", []
        products, listed_here = [], set()
        for family in shown:
            for accession in carried(family):
                if accession in listed_here:
                    continue
                listed_here.add(accession)
                entry = entries[accession]
                which = [signature for signature in family["signatures"] if accession in carriers.get(signature, [])]
                products.append({
                    "name": entry["name"], "gene": entry["gene"] or None, "role": family["of"], "ids": [{"db": "uniprot", "id": accession}], "length": entry["length"],
                    "evidence": "reviewed entry" if entry["reviewed"] else "family signature",
                    "evidence_note": f"Its {'reviewed' if entry['reviewed'] else 'unreviewed'} UniProtKB entry carries {', '.join(which)} ({'; '.join(signature_name(s) for s in which)}). A signature says the family, not which member does the unit's work.",
                    "citation": None,
                })
                unit_of[accession].add(unit["id"])
        hits = order(listed_here)
        if finding == "found":
            note = f"{plural(len(hits), 'protein')} of its {len(entries):,} carr{'ies' if len(hits) == 1 else 'y'} the signature of {said(shown)}: {some(by_gene(hits))}. Each is a candidate by its family alone: no source read here says which of them does the unit's work in the fly."
        elif finding == "different family":
            note = f"None of its {len(entries):,} proteins carries the signature of {said(own)}, the family the engine's law names. {plural(len(hits), 'protein')} carr{'ies' if len(hits) == 1 else 'y'} that of {said(shown)}, the other family this machine is asked for, as on the planarian's side of the atlas: {some(by_gene(hits))}."
        else:
            only = [(family, carried(family)) for family in going_with if carried(family)]
            aside = " ".join(f"{plural(len(found), 'protein')} ({some(by_gene(found))}) carr{'ies' if len(found) == 1 else 'y'} that of {family['of']}, which go with the machine and make none by themselves: no candidate for the unit." for family, found in only)
            note = f"None of its {len(entries):,} proteins carries the signature of {said([*own, *other])}. {aside} The unit's human candidates carry {'them' if len(own) + len(other) > 1 or len(own[0]['signatures']) > 1 else 'it'}, so the search finds the family where it exists.".replace("  ", " ")
            for family, found in only:
                for accession in found:
                    beside[accession] = family["of"]
        for near in NEAR.get(unit["id"], []):
            # A protein a reader would look for here, which the search by signature does not list: said, with what it carries.
            accession = next(a for a in entries if entries[a]["gene"] == near)
            under = filing.family.get(accession)
            if finding != "none found" or not under:
                raise SystemExit(f"{unit['id']}: the sentence on {near} no longer holds; read the unit's finding again")
            note += f" The fly's {near}, a voltage-gated potassium channel by its entry's name (\"{entries[accession]['name']}\"), carries the signature of another family of such channels ({under}, {filing.names[under]['name']}) and not this one, so a search by signature does not list it."
        units[unit["id"]] = {"finding": finding, "note": note, "products": products}
    if set(units) != {unit["id"] for unit in snapshot["units"]}:
        raise SystemExit("the units of the atlas are not the units of the inventory")
    unit_ids = {accession: sorted(found, key=H.natural) for accession, found in unit_of.items()}

    # --- the lines of the shelves -----------------------------------------------------------------------
    lines, alone, rest = H.make_lines(entries, placed, filing, unit_ids)
    sequence = [protein for line in [*lines, *alone, *rest] for protein in line["proteins"]]
    if len(sequence) != len(entries) or len(set(sequence)) != len(entries):
        raise SystemExit("a protein is filed twice or not at all")
    SIDES, NO_SHELF = H.SIDES, H.NO_SHELF
    key = lambda shelf: NO_SHELF if shelf is None else shelf
    shelf_counts = {name: {side: 0 for side in SIDES} for name in [*H.SHELF_IDS, NO_SHELF]}
    for item in placed.values():
        shelf_counts[key(item["shelf"])][item["side"]] += 1
    counts = {side: sum(found[side] for found in shelf_counts.values()) for side in SIDES}
    bases = Counter((item["side"], item["basis"]) for item in placed.values())
    rules = Counter(item["rule"] for item in placed.values())
    evidence = Counter(item["evidence"] for item in placed.values() if item["evidence"])
    # How sure: what stands behind each protein's place, for curated entries and for automatic ones.
    def sure(accession):
        item = placed[accession]
        return "predicted from a segment or a signal" if item["basis"] == "predicted" else "not known" if item["basis"] == "none" else {"experiment": "stated, on an experiment", "similarity": "stated, by likeness", "curator": "stated, by a curator's inference", "rule": "stated, by a rule", H.NOT_GIVEN: "stated, with no evidence given"}[item["evidence"]]
    kinds = ["stated, on an experiment", "stated, by likeness", "stated, by a curator's inference", "stated, with no evidence given", "stated, by a rule", "predicted from a segment or a signal", "not known"]
    how_sure = {kind: {"reviewed": 0, "unreviewed": 0} for kind in kinds}
    for accession in entries:
        how_sure[sure(accession)]["reviewed" if entries[accession]["reviewed"] else "unreviewed"] += 1
    family_total = Counter(filing.family.values())
    distinct = len({line["id"] for line in lines})
    lone_families = sum(1 for size in family_total.values() if size <= H.LONE_UP_TO)
    shelves = []
    for shelf in H.SHELVES:
        on = [line for line in lines if line["shelf"] == shelf["id"]]
        here = sum(len(line["proteins"]) for line in alone if line["shelf"] == shelf["id"])
        shelves.append({**shelf, **({"note": H.SHELF_NOTES[shelf["id"]]} if shelf["id"] in H.SHELF_NOTES else {}), "proteins": sum(shelf_counts[shelf["id"]].values()), "families": len(on) + here, "lines": len(on), "lone": here, "no_family": sum(len(line["proteins"]) for line in rest if line["shelf"] == shelf["id"])})
    none = [line for line in lines if line["shelf"] is None]
    here = sum(len(line["proteins"]) for line in alone if line["shelf"] is None)
    no_shelf = {"proteins": sum(shelf_counts[NO_SHELF].values()), "families": len(none) + here, "lines": len(none), "lone": here, "no_family": sum(len(line["proteins"]) for line in rest if line["shelf"] is None)}
    groups = []
    for group in H.DISTRICT_ORDER:
        asked = next((terms for key_, _, terms in H.DISTRICTS if key_ == group), None)
        said_from = "Gene Ontology terms: " + ", ".join(f"{name} ({term})" for term, name in asked) if asked else "The line's proteins carry Gene Ontology terms, and none of the districts' terms" if group == H.OTHER_DISTRICT[0] else "The line's proteins carry no Gene Ontology term"
        on = [line for line in lines if line["group"] == group]
        groups.append({"id": group, "label": H.DISTRICT_LABEL[group], "from": said_from, "lines": len(on), "proteins": sum(len(line["proteins"]) for line in on), "lone": sum(len(line["proteins"]) for line in alone if line["group"] == group)})
    first_places = Counter(item["where"]["name"] for item in placed.values() if item["where"])
    used = {statement["name"] for entry in entries.values() for statement in entry["statements"]}
    place_rows = []
    for name in sorted(used, key=lambda name: (-first_places[name], name)):
        shelf, kind, how, under = vocabulary.resolve(name)
        place_rows.append([vocabulary.by_name[name]["accession"], vocabulary.by_name[name]["path"], shelf, kind, how, under, first_places[name]])
    codes_used = {part for entry in entries.values() for statement in entry["statements"] for part in H.code(statement).split(".")}
    place_words = {term["accession"][3:]: term["path"] for term in sorted(vocabulary.terms.values(), key=lambda term: term["accession"]) if term["accession"][3:] in codes_used}

    resting, rule_ids = H.account(entries, placed)
    if set(resting) - OWNERS:
        raise SystemExit(f"a placement rests on a rule system or a program this tool does not name: {sorted(set(resting) - OWNERS)}")
    of = lambda owner, what="placements": resting.get(owner, {}).get(what, 0)
    PLACE, SPANS, FACE, ANCHOR = "the stated place", "the statement that it spans the membrane", "the stated face", "the stated GPI anchor"
    FROM_SEGMENTS, FROM_SIGNAL = "a side read from its segments", "a side read from its signal peptide"
    named = lambda owner: f"{of(owner):,} ({of(owner, FROM_SEGMENTS):,} by a side read from segments, {of(owner, FROM_SIGNAL):,} from a signal peptide, {of(owner, SPANS) + of(owner, PLACE) + of(owner, FACE):,} behind a statement)"
    predictors = "TMHMM, Memsat, Phobius and a hydrophobic moment plot for the segments; Phobius, Predotar, SignalP and TargetP for the signal peptides"
    ruling = "By the project's rule (the user, 15 November 2026), a value stands on the terms of the database it was read from, and the tool behind it is named and counted: the project's rule, not a legal opinion."
    made = d.last_day()
    header = {
        "format": H.SHELF_FORMAT, "species": SPECIES_ID, "made": made,
        "from": f"UniProtKB release {release}: the reference proteome {PROTEOME} of Drosophila melanogaster, {stated['entries']:,} entries ({stated['reviewed']:,} reviewed, {stated['unreviewed']:,} unreviewed) for {stated['genes']:,} genes. One protein is shown for each gene, the one that UniProt's own gene-by-gene set of the proteome gives: {stated['shown']:,} proteins, {stated['shown_reviewed']:,} with a reviewed entry and {stated['shown_unreviewed']:,} with an unreviewed one. The proteome's other {stated['further']:,} entries are further forms of the same genes; each protein counts its gene's entries in the mark 'entries'.",
        "from_counts": stated,
        "predicted": False,
        "curated": {"note": "A reviewed entry was written by a curator; an unreviewed one was annotated automatically, by rule systems and prediction programs. The table says, for the proteins shown, what stands behind each one's place.", "columns": ["what stands behind the place", "reviewed", "unreviewed"], "rows": [[kind, how_sure[kind]["reviewed"], how_sure[kind]["unreviewed"]] for kind in kinds]},
        "shelves": shelves, "no_shelf": no_shelf, "groups": groups,
        "groups_from": "A protein's Gene Ontology terms are those InterPro maps to any of its signatures and those UniProt gives its entry. With every broader term (by the ontology's kind-of and part-of links), the protein falls in the first district, in the order listed, one of whose terms it carries. A family's line stands in the district most of its classed members on that shelf fall in; of equal counts, the first listed. A protein that is the only member of its family stands in its own district. A part of no_family stands in a district only if more than half of all its members on that shelf fall there. The choice of the districts' terms and their order is the viewer's, and is the planarian's and the human's.",
        "family_from": f"A family is an InterPro entry of the type Family (InterPro {filing.release}). A protein is filed under the narrowest family among the InterPro entries UniProt gives it: one that is not a broader kind of another it carries, by InterPro's tree of entries. Where several unrelated families remain ({filing.several:,} proteins), it is the deepest in that tree, then the one fewest proteins of this catalogue are in, then the first by accession. This is the rule of the planarian's and the human's files, so a family has the same id in each.",
        "family_columns": H.FAMILY_COLUMNS,
        "family_notes": {
            "lines": "A family has one line for each shelf that holds members of it, and one with a null shelf for its members that are on no shelf. A line is identified by id and shelf together; side, group, count, sides, file, at and units are of its members on that shelf alone.",
            "side": "The side most of the line's members sit on; of equal counts, a membrane first.",
            "units": "The inventory units for which a member on this line carries the family's signature: candidates by family alone.",
            "total": "The family's members on every shelf and on none.",
            "counts": "distinct_families is the number of families that have lines; families_in_all counts also the families of one, whose proteins are under 'lone'.",
        },
    }
    lone_sides = Counter(side for line in alone for side, n in line["sides"].items() for _ in range(n))
    lone = {"label": H.LONE_LABEL, "count": sum(len(line["proteins"]) for line in alone), "families": lone_families, "sides": H.ordered_sides(lone_sides), "parts_from": f"A family with a single member in this catalogue does not open, so it has no line among the families: {lone_families:,} families of one. Their proteins are listed here together, one part for each shelf, district and side, and each names its family in its mark 'family'. A part is not a family.", "part_columns": H.PART_COLUMNS}
    no_family = {"label": "No family assigned", "count": len(filing.part), "sides": H.ordered_sides(Counter(placed[protein]["side"] for protein in filing.part)), "parts_from": "A protein with no family is filed under one part. If it carries an InterPro entry of the type Homologous superfamily, the part is that superfamily: a wider grouping than a family, by shared structure. Of several superfamilies it is the one fewest proteins of this catalogue carry, then the first by accession. The other two parts hold the proteins with only a domain, repeat or site signature, and those with no signature at all. A part has one line for each shelf, as a family has.", "part_columns": H.PART_COLUMNS}
    files = sorted({line["file"] for line in [*lines, *alone, *rest]})
    tail = {
        "member_columns": ["id", "label", "gene", "side", "basis", "length", "unit", "marks"],
        "members_from": {
            "table": f"data/proteins/{SPECIES_ID}/{H.TABLE_FILE}", "format": H.MEMBERS_FORMAT,
            "order": "The table's lines are the members in order: every line of the families as listed here, then every part of 'lone', then every part of 'no_family'; within each, by gene name. A line's members are the next 'count' lines of the table. For a family's line and for a part of no_family, 'under' is its id and 'shelf' its shelf (empty for none); for a part of 'lone', 'under' is the protein's own family and 'family' that family's name.",
            "files": f"A file holds the members of consecutive lines: a new file begins where the next line would take it past {H.MEMBERS_PER_FILE:,} members, so a line is never split. 'file' names the file and 'at' the first and one past the last of its members there.",
            "places": "In the table a stated place is written with UniProt's identifiers, without their prefix: the place, then the topology and the face where the entry states them, joined by a full stop. 'place_words' gives the words of each.",
            "letters": {"basis": {letter: word for word, letter in H.BASIS_LETTER.items()}, "evidence": {letter: word for word, letter in H.EVIDENCE_LETTER.items()}, "seen": {str(level): H.SEEN[level] for level in sorted(H.SEEN)}},
            "step": f"python3 {TOOL} members --out DIR writes the files from the two files.",
        },
        "side_notes": {
            "stated": "The protein's UniProtKB entry states where it is, and the first place it states decides the shelf and the side. For a reviewed entry the statement is a curator's, and the mark 'evidence' says what stands behind it: an experiment, likeness to another protein, the curator's inference, or a rule. For an unreviewed entry no curator wrote it: the statement was made by one of UniProt's rule systems, and its evidence is 'rule'.",
            "predicted": f"Read from the entry's own features, where its words do not give the side. A membrane-spanning segment puts the protein in a membrane; a signal peptide with no such segment puts it on the side away from the cytoplasm. Where the entry states no place, the protein stands on the shelf of a membrane that is not named. In a reviewed entry UniProt's curators annotate these features, and its pages name the predictors behind the predicted ones: {predictors}. In an unreviewed entry the program is named on each feature. Each is named among the sources, with its terms and what rests on it. {ruling}",
            "none": "The entry states a membrane or a place and not the side (the protein then stands apart beside that shelf, with the place in its mark 'where'), or it states no place of the cell and carries no membrane-spanning segment and no signal peptide (the protein is then on no shelf). Nothing is placed by guess.",
        },
        "placed_by": [{"rule": rule, "basis": basis, "what": what, "proteins": rules[rule]} for rule, basis, what in H.RULES_USED],
        "place_kinds": H.KINDS,
        "place_columns": ["id", "words", "shelf", "names", "resolved", "under", "first"],
        "place_notes": "Every place the entries state, in UniProt's words, with the shelf and what the place names against its membrane (place_kinds), how the table's line was reached and which of the table's terms it rests on, and how many proteins it places as the statement that decided.",
    }
    marks = {
        "reviewed": {"label": "Curated entry", "values": [True, False], "measured": False, "note": "Whether the protein's UniProtKB entry is reviewed, written by a curator, or unreviewed, annotated automatically.", "source": "UniProt"},
        "entries": {"label": "Entries for its gene", "values": "number", "measured": False, "note": "The proteome's entries for the same gene, by the FlyBase gene that UniProt gives each entry: this protein's own and the further forms of the gene. The marker stands for the one UniProt's gene-by-gene set names.", "source": "UniProt"},
        "isoforms": {"label": "Isoforms described", "values": "number", "measured": False, "note": "The canonical sequence and the other sequences its own entry describes.", "source": "UniProt"},
        "seen": {"label": "Evidence that the protein exists", "values": [H.SEEN[level] for level in sorted(H.SEEN)], "measured": False, "note": "UniProt's level of evidence for the entry: at protein level, at transcript level, inferred from homology, predicted, or uncertain.", "source": "UniProt"},
        "evidence": {"label": "What stands behind the stated place", "values": [word for word, _, _ in H.EVIDENCE] + [H.NOT_GIVEN], "measured": False, "note": "From UniProt's evidence codes on the statement: an experiment in a paper the entry cites; likeness to a protein of which it is known; a curator's inference; a rule (a family rule or a sequence model that a curator applied, or, in an unreviewed entry, one of UniProt's automatic rule systems); not given, an older curated statement. Of several, the first in this order.", "source": "UniProt"},
        "where": {"label": "Stated place", "values": "text", "measured": False, "note": "The statement that decided the shelf, in UniProt's words: the place, then the topology and the face where the entry states them.", "source": "UniProt"},
        "also": {"label": "Also stated", "values": "text", "measured": False, "note": "The entry's other statements of place, in order and in UniProt's words.", "source": "UniProt"},
        "family": {"label": "Family, of which it is the only member here", "values": "text", "measured": False, "note": "The InterPro family's accession and name, for a protein listed among the only members of their families.", "source": "InterPro"},
        "of": {"label": "Stated for", "values": "text", "measured": False, "note": "The named form of the protein that the place is stated for, where the entry states none for the protein as a whole.", "source": "UniProt"},
    }
    cite_uniprot = "The UniProt Consortium, UniProt: the Universal Protein Knowledgebase in 2025, Nucleic Acids Res. 53:D609-D617 (2025)"
    cite_interpro = "Blum and others (2025) InterPro: the protein sequence classification resource in 2025. Nucleic Acids Res 53:D444-D456."
    terms_day = lambda name: d.day(*H.SAVED_TERMS[name])
    own_said = "; ".join(f"{owner} {of(owner):,}" for owner in OWN_SYSTEMS if of(owner))
    sources = [
        {"name": "UniProt", "url": "https://www.uniprot.org/", "release": release, "accessed": d.day(KB, PLACES_FILE), "licence": "CC BY 4.0", "class": "permissive", "cite": cite_uniprot,
         "holds": f"for each entry of the fly's reference proteome: its name, gene, FlyBase gene, length and level of evidence, the places it states with the evidence for each, its membrane-spanning segments, signal peptide and anchors, and the InterPro entries and Gene Ontology terms UniProt gives it; the gene-by-gene set of the proteome; and UniProt's vocabulary of places. The programs and rule systems of other owners behind its statements are sources below. Placements that rest on UniProt's own automatic systems alone: {own_said or 'none'}"},
        {"name": "InterPro", "url": "https://www.ebi.ac.uk/interpro/", "release": filing.release, "accessed": d.day(IPR, "entry.list"), "licence": "CC0 1.0", "class": "permissive", "cite": cite_interpro, "holds": "the type and name of each entry, the tree of broader and narrower entries, and the mapping of entries to Gene Ontology terms"},
        {"name": "Gene Ontology", "url": "https://geneontology.org/", "release": filing.ontology, "accessed": d.day(GO, "go-basic.obo"), "licence": "CC BY 4.0", "class": "permissive", "cite": H.ontology_citation(d), "holds": "the names of terms and which term is a kind or a part of which; no term's text is copied beyond the names of the districts' terms"},
        {"name": "PROSITE", "url": "https://prosite.expasy.org/prosite_license.html", "licence": "CC BY-NC-ND 4.0; commercial users are asked to pay a yearly licence fee", "class": "non-commercial", "accessed": terms_day("prosite"), "through": "UniProt",
         "holds": f"Nothing was downloaded from it but its statement of terms, and nothing of it is copied. Its rules (ProRule) are named in UniProt's entries as what stands behind a statement. {of('PROSITE-ProRule'):,} placements rest on them alone: {of('PROSITE-ProRule', PLACE):,} by the statement of place that decides the shelf ({len(rule_ids.get('PROSITE-ProRule', {})):,} rules), {of('PROSITE-ProRule', SPANS):,} by the statement that the protein spans the membrane, and {of('PROSITE-ProRule', FROM_SEGMENTS) + of('PROSITE-ProRule', FROM_SIGNAL):,} by a side read here from a feature that a rule gives."},
        {"name": "HAMAP", "url": "https://hamap.expasy.org/hamap_about.html", "licence": "CC BY 4.0", "class": "permissive", "accessed": terms_day("hamap"), "through": "UniProt",
         "holds": f"Nothing was downloaded from it but its statement of terms. Its family rules are named in UniProt's entries as what stands behind a statement: {of('HAMAP-Rule'):,} placements rest on them alone."},
        {"name": "TMHMM", "url": "https://services.healthtech.dtu.dk/services/TMHMM-2.0/", "licence": H.DTU_LICENCE, "class": "non-commercial", "accessed": terms_day("tmhmm"), "through": "UniProt",
         "holds": f"{H.NOT_RUN} {H.FOUR_SEGMENTS}. In reviewed entries {of('segments'):,} placements rest on segments that an entry gives by sequence analysis alone ({of('segments', FROM_SEGMENTS):,} read here from such segments, {of('segments', SPANS):,} statements of spanning, {of('segments', PLACE):,} stated places). In unreviewed entries UniProt names the program on each feature: TMHMM on {named('TMHMM')}."},
        {"name": "Phobius", "url": "https://phobius.sbc.su.se/download", "licence": "For academic users only: the program may be used for private study, education or nonprofit research, and other users are asked to write to its author. The terms are of the program: they do not speak of predictions made with it", "class": "non-commercial", "accessed": terms_day("phobius"), "through": "UniProt",
         "holds": f"{H.NOT_RUN} In reviewed entries, one of the four methods for segments and of the four for signal peptides: the placements counted under TMHMM ({of('segments'):,}) and SignalP ({of('signal'):,}). In unreviewed entries UniProt names it on each feature: {named('Phobius')}."},
        {"name": "SignalP", "url": "https://services.healthtech.dtu.dk/services/SignalP-5.0/", "licence": H.DTU_LICENCE, "class": "non-commercial", "accessed": terms_day("signalp"), "through": "UniProt",
         "holds": f"{H.NOT_RUN} {H.FOUR_SIGNALS}. In reviewed entries {of('signal'):,} placements rest on a signal peptide that an entry gives by sequence analysis alone. In unreviewed entries UniProt names the program on each feature: SignalP on {named('SignalP')}."},
        {"name": "TargetP", "url": "https://services.healthtech.dtu.dk/services/TargetP-2.0/", "licence": H.DTU_LICENCE, "class": "non-commercial", "accessed": terms_day("targetp"), "through": "UniProt", "holds": f"{H.NOT_RUN} {H.FOUR_SIGNALS}. The placements are those counted under SignalP for reviewed entries ({of('signal'):,})."},
        {"name": "Memsat", "url": "https://www.uniprot.org/help/transmem", "licence": "Terms not read: UniProt's help names Memsat without a version or an address, so no page of terms could be tied to the program it runs", "class": "no stated terms", "accessed": d.day(KB_DOCS, "help_transmem.json"), "through": "UniProt", "holds": f"Nothing was downloaded from it. {H.FOUR_SEGMENTS}. The placements are those counted under TMHMM for reviewed entries ({of('segments'):,})."},
        {"name": "Predotar", "url": "https://www.uniprot.org/help/signal", "licence": "Terms not read: the program's own page answers this tool with a check for a browser, so its terms could not be read", "class": "no stated terms", "accessed": d.day(KB_DOCS, "help_signal.json"), "through": "UniProt", "holds": f"Nothing was downloaded from it. {H.FOUR_SIGNALS}. The placements are those counted under SignalP for reviewed entries ({of('signal'):,})."},
        {"name": "big-PI", "url": "https://mendel.imp.ac.at/gpi/gpi_server.html", "licence": "No open licence stated: the predictor's own page gives no terms of use", "class": "no stated terms", "accessed": d.day(BIG_PI, "gpi_server.html"), "through": "UniProt",
         "holds": f"Nothing was downloaded from it but its own page, and the program was not run here. The predictor that UniProt's help names for the GPI anchors it predicts. {of('big-PI'):,} placements rest on a GPI anchor that the entry states on a sequence analysis alone: such an anchor puts the protein on the face away from the cytoplasm."},
    ]
    sources = [source for source in sources if source["name"] != "big-PI" or of("big-PI")]
    closing = {"marks": marks, "counts": counts, "shelf_counts": shelf_counts, "by_basis": {side: {basis: bases[side, basis] for basis in ("stated", "predicted", "none") if bases.get((side, basis))} for side in SIDES}, "by_evidence": {word: evidence.get(word, 0) for word in [word for word, _, _ in H.EVIDENCE] + [H.NOT_GIVEN]}, "sources": sources}

    compact = H.compact
    rows = lambda items, pad=" ": "[\n" + ",\n".join(f"{pad} " + compact(item) for item in items) + f"\n{pad}]"
    nested = lambda block, items: json.dumps(block, indent=1, ensure_ascii=False).replace("\n", "\n ")[:-3] + ',\n  "parts": ' + rows(items, "  ") + "\n }"
    body = json.dumps(header, indent=1, ensure_ascii=False)[:-2]
    body += ',\n "families": ' + rows([H.line_row(line, H.FAMILY_COLUMNS) for line in lines])
    body += f',\n "distinct_families": {distinct},\n "family_lines": {len(lines)},\n "families_in_all": {len(family_total)}'
    body += ',\n "lone": ' + nested(lone, [H.line_row(line, H.PART_COLUMNS) for line in alone])
    body += ',\n "no_family": ' + nested(no_family, [H.line_row(line, H.PART_COLUMNS) for line in rest])
    body += "," + json.dumps(tail, indent=1, ensure_ascii=False)[1:-2]
    body += ',\n "places": ' + rows(place_rows)
    body += ',\n "place_words": ' + json.dumps(place_words, ensure_ascii=False, separators=(", ", ": "))
    body += "," + json.dumps(closing, indent=1, ensure_ascii=False)[1:] + "\n"
    json.loads(body)

    lone_of = {protein for line in alone for protein in line["proteins"]}
    table_rows = []
    for protein in sequence:
        entry, item = entries[protein], placed[protein]
        under = filing.family.get(protein) or filing.part[protein]
        table_rows.append([
            protein, entry["gene"], entry["name"], str(entry["length"]), str(entry["isoforms"]), str(entry["seen"]), under, item["shelf"] or "", item["side"], H.BASIS_LETTER[item["basis"]], H.EVIDENCE_LETTER[item["evidence"]] if item["evidence"] else "",
            H.code(item["where"]) if item["where"] else "", ",".join(H.code(statement) for statement in item["also"]), ";".join(unit_ids.get(protein, [])),
            filing.names[under]["name"] if protein in lone_of else "", entry["of"] or "", "1" if entry["reviewed"] else "0", str(together[protein]),
        ])
    for row in table_rows:
        if any("\t" in value or "\n" in value for value in row):
            raise SystemExit(f"{row[0]}: a value of the table holds a tab or a line break")
    table = "\n".join("\t".join(row) for row in [TABLE_COLUMNS, *table_rows]) + "\n"

    # --- the species file and its outlines ---------------------------------------------------------------
    findings = Counter(unit["finding"] for unit in units.values())
    species = {
        "format": "cells.visualizer.species@1", "id": SPECIES_ID, "label": LABEL, "organism": ORGANISM, "taxon": TAXON,
        "plain": f"The fruit fly of the laboratory: {stated['genes']:,} genes in UniProt's reference proteome, with one protein shown for each. Many of the channels and pumps Cells has laws for have a counterpart of the same family in it.",
        "group": "Animals", "order": 25, "default": False, "made": made,  # after the other animals, before the bacteria
        "modelled": {"state": "generic", "text": "Cells models a generic cell and a sheet of such cells, not this animal. The sheet is drawn on a wing for the scales only. The wings and the fly are placeholder outlines: nothing at those scales is simulated."},
        "levels": [
            {"id": "molecules"},
            {"id": "cell", "shape": {"kind": "prism", "sides": 6, "radius_um": 10.6, "height_um": 13, "corner_um": 2.4, "edge_um": 1.3},
             "note": "The cell drawn is a generic animal cell, as one of a layer; it is not a model of a cell type of the fly. Its shape and its sizes are the picture's choice: six flat sides where it meets its neighbours, about 20 µm across.",
             "notes": [{"text": "A generic animal cell, as one of a layer"}, {"text": "Its flat-sided shape is the picture's choice", "roomy": True}], "fade_out_um": [120, 190]},
            {"id": "tissue", "shape": {"kind": "cell sheet", "rings": 6, "beyond": [[8, 0.34], [10, 0.2], [11, 0.1]]},
             "note": "The sheet is the one Cells simulates: a single layer of coupled cells. It stands for no particular tissue of the fly.",
             "notes": [{"text": "The sheet Cells simulates: a single layer of coupled cells", "short": "The simulated sheet"}], "fade_in_um": [100, 190]},
            {"id": "organ", "label": "Wing", "shape": {"kind": "outline", "ref": SPECIES_ID, "parts": ["wings"], "context": ["body"]},
             "note": f"The outline drawn is a fly's two wings, folded back over its body, as a placeholder. The wing is the picture's choice of organ: a visitor knows it, and the project's record names the Drosophila wing disc as a long-term target of its work on how a tissue takes its shape (the user's decisions of 9 November 2026 on the morphogenesis plan). No wing and no wing disc is modelled. The sheet of cells is drawn on a wing so that the scales follow one another; it is not the wing's tissue. Each wing is drawn {WING_UM / 1000:g} mm long: the picture's choice, since no measurement was read for this file.",
             "sheet_mark": {"band": 0.05, "note": "The sheet, to scale: drawn on a wing for the scales only"},
             "notes": [{"text": "A fly's wings: a placeholder outline"}, {"text": "The wing's own cells are not modelled", "lift": -22, "roomy": True}]},
            {"id": "organism", "label": "Whole fly", "shape": {"kind": "outline", "ref": SPECIES_ID},
             "note": f"The outline drawn is a fruit fly with its wings folded back, {BODY_UM / 1000:g} mm long, as a placeholder. The sheet of cells is drawn on a wing for the scales only. The fly's length, its width and its proportions are the picture's choice: no measurement was read for this file.",
             "sheet_mark": {"band": 0.05, "note": "The sheet, to scale", "roomy": True}, "notes": [{"text": "A fruit fly: a placeholder outline"}]},
        ],
        "cell": {
            "facts": [
                {"label": "Proteins", "value": f"{stated['genes']:,} genes in UniProt's reference proteome, with {stated['entries']:,} entries: {stated['reviewed']:,} reviewed by a curator and {stated['unreviewed']:,} annotated automatically. One protein is shown for each gene", "sources": ["uniprot"]},
                {"label": "Cells' machines", "value": f"of the 49 units of the law inventory, {findings['found']} have proteins of the same family in the fly and {findings['different family']} are built from another family; {findings['none found']} were not found", "sources": ["uniprot"]},
            ],
            "parts": {"membranes": 1, "wall": False, "nucleus": True, "organelles": ["er", "golgi", "mitochondria"]},
        },
        "sources": {"uniprot": {"text": f"UniProt Consortium, UniProt release {release}: the reference proteome {PROTEOME} (Drosophila melanogaster), its entries and its gene-by-gene set.", "url": f"https://www.uniprot.org/proteomes/{PROTEOME}", "licence": "CC BY 4.0", "class": "permissive", "accessed": d.day(KB, PLACES_FILE)}},
    }
    atlas = {
        "format": "cells.visualizer.species_atlas@1",
        "species": {"id": SPECIES_ID, "label": LABEL, "organism": ORGANISM, "taxon": TAXON, "plain": f"The fruit fly of the laboratory, with {stated['genes']:,} genes in UniProt's reference proteome. This is what the family signatures of Cells' machines find among the one protein shown for each gene."},
        "made": made,
        "method": [
            f"The fly's proteins are the {len(entries):,} of UniProt's gene-by-gene set of the reference proteome {PROTEOME} (release {release}): one for each gene, {stated['shown_reviewed']:,} with a reviewed entry and {stated['shown_unreviewed']:,} with an unreviewed one.",
            "Licences were read before anything was copied; each is stated in sources.",
            "Each unit's family was taken from its own human candidates, by the same InterPro signatures that the other species' atlases ask. The build checks that the candidates carry them.",
            "Each signature was looked for among the InterPro entries UniProt gives each protein. A unit counts as found only where a protein carries the signature of a family that makes the machine itself; an accessory family alone does not make it found.",
            "Where no protein carries the family the engine's law names and proteins carry another family asked for the same machine (innexins, for gap junctions), the finding is 'different family'.",
            "A product with a reviewed entry is listed as a reviewed entry, one with an unreviewed entry as a family signature. Either is a candidate by family: several units of one family (the Kv1 channels) list the same proteins, and nothing here says which protein does which unit's work.",
            "No similarity search was run, and nothing is called an ortholog.",
        ],
        "sources": [
            {"name": "UniProt", "url": "https://www.uniprot.org/", "release": release, "accessed": d.day(KB, PLACES_FILE), "licence": "CC BY 4.0", "class": "permissive", "cite": cite_uniprot, "holds": "the entries of the fly's proteins, reviewed and unreviewed, with the InterPro entries UniProt gives each; the signatures of the units' human candidates"},
            {"name": "InterPro", "url": "https://www.ebi.ac.uk/interpro/", "release": filing.release, "accessed": d.day(IPR, "entry.list"), "licence": "CC0 1.0", "class": "permissive", "cite": cite_interpro, "holds": "the identifiers and names of the family signatures"},
        ],
        "not_copied": "No sequence is copied. FlyBase is linked to; nothing was downloaded from it, and the FlyBase genes used here are those UniProt gives its entries.",
        "units": units,
        "extra": [],
    }
    report = {
        "release": release, "interpro": filing.release, "ontology": filing.ontology, "made": made, "stated": stated, "read": dict(read),
        "shelf_counts": shelf_counts, "counts": counts, "bases": {f"{side} / {basis}": n for (side, basis), n in sorted(bases.items())}, "rules": {rule: rules[rule] for rule, _, _ in H.RULES_USED},
        "evidence": dict(evidence), "how_sure": how_sure, "resting": resting, "rule_systems": {owner: len(found) for owner, found in rule_ids.items()},
        "families": len(family_total), "in_families": len(filing.family), "several": filing.several, "no_family": len(filing.part),
        "family_sizes": {"one": sum(1 for size in family_total.values() if size == 1), "two to four": sum(1 for size in family_total.values() if 2 <= size <= 4), "five or more": sum(1 for size in family_total.values() if size >= 5)},
        "largest_families": [[filing.names[family]["name"], n] for family, n in sorted(family_total.items(), key=lambda pair: (-pair[1], pair[0]))[:8]],
        "lines": len(lines), "distinct": distinct, "lone": lone["count"], "lone_parts": len(alone), "part_lines": len(rest), "groups": groups, "member_files": files, "places_used": len(used),
        "findings": dict(findings), "found_units": {unit: [product["gene"] for product in found["products"]] for unit, found in units.items() if found["products"]}, "beside": {gene(a): what for a, what in beside.items()},
        "with_units": len(unit_ids), "entries_per_gene": dict(sorted(Counter(min(n, 6) for n in together.values()).items())),
    }
    files_out = {"shelves": body, "table": table, "species": json.dumps(species, indent=1, ensure_ascii=False) + "\n", "shapes": json.dumps(outlines(), ensure_ascii=False, separators=(",", ":")) + "\n", "atlas": json.dumps(atlas, indent=1, ensure_ascii=False) + "\n"}
    files_out["readme"] = build_readme(report, header, closing)
    for name, text in files_out.items():
        if PATHS.search(text):
            raise SystemExit(f"the {name} would hold a machine path")
    size = {name: len(text.encode("utf-8")) for name, text in files_out.items()}
    if size["shelves"] >= H.LIMIT_SHELVES or max(size.values()) >= H.LIMIT_FILE:
        raise SystemExit(f"the files have outgrown their limits: {size}")
    report["sizes"] = size
    return files_out, report


def build_readme(report, header, closing):
    r = report
    names = {shelf["id"]: shelf["label"] for shelf in header["shelves"]}
    lines = [
        "# The fruit fly: its own proteins, on shelves",
        "",
        "Generated by `tools/build_fruitfly_atlas.py`; do not edit by hand. The note is `docs/FRUITFLY.md`.",
        "",
        f"- `shelves.json`: {header['from']}",
        f"- `proteins.tsv`: one line for each of the {r['stated']['shown']:,} proteins shown, in the order of the shelves' lines. No sequences.",
        "- The members' files are not kept here: `python3 tools/build_fruitfly_atlas.py members --out DIR` cuts them from these two files.",
        "",
        "Nothing of the fly is in the engine. This is reference data for the viewer.",
        "",
        "## Shelves",
        "",
        "| Shelf | Proteins | Outside | In | Inside | Side not known |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
        *[f"| {names.get(name, 'On no shelf')} | {sum(found.values()):,} | {found['outside']:,} | {found['in']:,} | {found['inside']:,} | {found['not known']:,} |" for name, found in r["shelf_counts"].items()],
        "",
        "## How sure the places are",
        "",
        "| What stands behind the place | Reviewed entries | Unreviewed entries |",
        "| --- | ---: | ---: |",
        *[f"| {kind} | {found['reviewed']:,} | {found['unreviewed']:,} |" for kind, found in r["how_sure"].items()],
        "",
        "## Families",
        "",
        f"- {r['families']:,} InterPro families hold {r['in_families']:,} proteins: {r['family_sizes']['one']:,} of one, {r['family_sizes']['two to four']:,} of two to four, {r['family_sizes']['five or more']:,} of five or more. {r['no_family']:,} proteins have no family.",
        f"- {r['lines']:,} lines of {r['distinct']:,} families; the {r['lone']:,} only members of their families stand in {r['lone_parts']} parts; the proteins with no family in {r['part_lines']} lines.",
        "- The largest: " + "; ".join(f"{name} ({n})" for name, n in r["largest_families"]) + ".",
        f"- {r['with_units']:,} proteins carry the family signature of one of Cells' machines and name its units.",
        "",
        "## What rests on tools and rule systems of other owners",
        "",
        "By the project's rule (the user, 15 November 2026), a value stands on the terms of the database it was read from, here UniProt's, and the tool behind it is named and counted. It is the project's rule, not a legal opinion. Nothing was downloaded from any of these tools, and none was run.",
        "",
        "| Tool or rule system | Class | What rests on it |",
        "| --- | --- | --- |",
        *[f"| {source['name']} | {source['class']} | {source['holds']} |" for source in closing["sources"] if source.get("through")],
        "",
        "## Sources",
        "",
        *[f"- **{source['name']}** ({source['licence']}; read {source['accessed']}): {source['holds']}." for source in closing["sources"] if not source.get("through")],
        "",
    ]
    return "\n".join(lines)


def cut_members(folder):
    """The members' files, cut from the two files of the repository as shelves.json says."""
    folder = Path(folder)
    shelves = json.loads((folder / H.SHELVES_FILE).read_text(encoding="utf-8"))
    with open(folder / H.TABLE_FILE, encoding="utf-8") as handle:
        header = handle.readline().rstrip("\n").split("\t")
        table = [dict(zip(header, line.rstrip("\n").split("\t"))) for line in handle]
    said = shelves["place_words"]
    place = lambda written: "; ".join(said[part] for part in written.split("."))
    letters = shelves["members_from"]["letters"]
    lines = [("family", dict(zip(shelves["family_columns"], row))) for row in shelves["families"]]
    lines += [("lone", dict(zip(shelves["lone"]["part_columns"], row))) for row in shelves["lone"]["parts"]]
    lines += [("part", dict(zip(shelves["no_family"]["part_columns"], row))) for row in shelves["no_family"]["parts"]]
    files, cursor = defaultdict(list), 0
    for what, line in lines:
        rows = table[cursor:cursor + line["count"]]
        cursor += line["count"]
        if len(files[line["file"]]) != line["at"][0] or len(rows) != line["at"][1] - line["at"][0]:
            raise SystemExit(f"the members of {line['id']} on {line['shelf']} are not where {H.SHELVES_FILE} says they are")
        for row in rows:
            if row["shelf"] != (line["shelf"] or "") or (what != "lone" and row["under"] != line["id"]) or (what == "lone" and (row["side"] != line["side"] or not row["family"])):
                raise SystemExit(f"{row['id']} is not a member of the line {line['id']} on {line['shelf']}: the two files are not of one build")
            marks = {"reviewed": row["reviewed"] == "1", "entries": int(row["entries"]), "isoforms": int(row["isoforms"]), "seen": letters["seen"][row["seen"]]}
            if row["evidence"]:
                marks["evidence"] = letters["evidence"][row["evidence"]]
            if row["place"]:
                marks["where"] = place(row["place"])
            if row["also"]:
                marks["also"] = [place(written) for written in row["also"].split(",")]
            if what == "lone":
                marks["family"] = [row["under"], row["family"]]
            if row["of"]:
                marks["of"] = row["of"]
            files[line["file"]].append([row["id"], row["name"], row["gene"], row["side"], letters["basis"][row["basis"]], int(row["length"]), row["units"].split(";") if row["units"] else None, marks])
    if cursor != len(table):
        raise SystemExit(f"the table holds {len(table)} proteins and the lines {cursor}")
    out = {}
    for file in sorted(files):
        head = {"format": H.MEMBERS_FORMAT, "species": shelves["species"], "file": file, "columns": shelves["member_columns"]}
        out[file] = json.dumps(head, indent=1, ensure_ascii=False)[:-2] + ',\n "members": [\n' + ",\n".join("  " + H.compact(member) for member in files[file]) + "\n ]\n}\n"
    return out


def summary(report):
    r = report
    return "\n".join([
        f"UniProt {r['release']}, InterPro {r['interpro']}, Gene Ontology {r['ontology']}; made {r['made']}",
        f"proteome: {r['stated']}; read: {r['read']}",
        "by shelf: " + "; ".join(f"{shelf} {sum(sides.values()):,} {sides}" for shelf, sides in r["shelf_counts"].items()),
        f"sides: {r['counts']}; side and basis: {r['bases']}",
        f"rules: {r['rules']}",
        f"how sure: {r['how_sure']}",
        f"evidence behind the deciding statement: {r['evidence']}",
        f"families: {r['families']:,} holding {r['in_families']:,} (sizes {r['family_sizes']}); no family {r['no_family']:,}; lines {r['lines']:,} of {r['distinct']:,}; lone {r['lone']:,} in {r['lone_parts']} parts; part lines {r['part_lines']}; largest {r['largest_families'][:5]}",
        f"rests on, by owner: {r['resting']}; rules named: {r['rule_systems']}",
        f"atlas: {r['findings']}; accessory only {r['beside']}; proteins with units {r['with_units']}",
        "found: " + "; ".join(f"{unit} {len(genes)} ({', '.join(str(g) for g in genes[:4])})" for unit, genes in r["found_units"].items()),
        f"entries per gene (6 = six or more): {r['entries_per_gene']}; member files: {r['member_files']}; places used: {r['places_used']}; sizes: {r['sizes']}",
    ])


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("step", choices=["fetch", "build", "members"])
    parser.add_argument("--datasets", help="fetch, build: the folder that holds every species' downloads")
    parser.add_argument("--refresh", action="store_true", help="fetch: ask again even where an answer is saved")
    parser.add_argument("--out-dir", default=str(OUT_DIR), help="build: the folder for shelves.json, the table and their README.md; members: the folder that holds them")
    parser.add_argument("--out-species", default=str(SPECIES_FILE))
    parser.add_argument("--out-shapes", default=str(SHAPES_FILE))
    parser.add_argument("--out-atlas", default=str(ATLAS_FILE))
    parser.add_argument("--out", help="members: the folder to write the member files into")
    parser.add_argument("--report", help="build: also write what was counted, as JSON, to this file (kept outside the repository)")
    args = parser.parse_args()
    if args.step == "members":
        if not args.out:
            parser.error("members needs --out")
        Path(args.out).mkdir(parents=True, exist_ok=True)
        for name, text in cut_members(args.out_dir).items():
            (Path(args.out) / name).write_text(text, encoding="utf-8")
            print(f"wrote {Path(args.out) / name} ({len(text.encode('utf-8')):,} bytes)")
        return
    if not args.datasets:
        parser.error(f"{args.step} needs --datasets")
    if args.step == "fetch":
        sys.exit(1 if fetch(Path(args.datasets), refresh=args.refresh) else 0)
    files, report = build(Path(args.datasets), json.loads(SNAPSHOT.read_text(encoding="utf-8")))
    folder = Path(args.out_dir)
    for target, name in [(folder / H.SHELVES_FILE, "shelves"), (folder / H.TABLE_FILE, "table"), (folder / "README.md", "readme"), (Path(args.out_species), "species"), (Path(args.out_shapes), "shapes"), (Path(args.out_atlas), "atlas")]:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(files[name], encoding="utf-8")
        print(f"wrote {target.name} ({len(files[name].encode('utf-8')):,} bytes)")
    if args.report:
        Path(args.report).write_text(json.dumps(report, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(summary(report))


if __name__ == "__main__":
    main()
