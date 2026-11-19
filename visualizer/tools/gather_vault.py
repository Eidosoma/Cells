"""The vault, as a kind of the Machines catalogue (schema/MACHINE_DOSSIERS.md, "The vault").

The vault is a named exception to how a kind is identified: the Gene Ontology has no term for it and UniProt no keyword, so
its proteins are not found by a term. They are found by three footings, each kept apart and said in its own words:

  record      the species' Complex Portal has an entry whose name holds the word gather.json gives (`portal_name`): its
              protein members are parts by that record, with the stoichiometry the entry gives;
  entry       a reviewed UniProt entry of the species whose FUNCTION or SUBUNIT lines name the vault particle, found by
              rule (a sentence that says "vault particle", "The vault is" or "vault ribonucleoprotein particle") in the
              saved entry files that gather.json lists, each sentence with the evidence it carries: "By similarity" to
              an accession, or a publication it cites. No protein is found by a name typed into this tool;
  family      a protein of the species' own table that carries the family's signature (IPR039059) or the PARP4 marker
              (IPR058904): a candidate by its family, never a part.

A signature not found in a species is not an absence: such a species has no vault on its bench and the page says what was
looked for. The tool reads saved files only (standard library). Its answers go into the dossiers that gather_machines.py
writes.
"""

from __future__ import annotations

import csv
import io
import json
import re
from pathlib import Path

# A sentence of a FUNCTION or SUBUNIT comment that names the vault particle, not one that only mentions a protein of it
# ("Interacts with major vault protein" does not match).
NAMES_THE_VAULT = re.compile(r"\bvaults?\b(?!\s+protein)", re.I)
SENTENCE = re.compile(r"(?<=[.)])\s+(?=[A-Z])")
SIMILAR = re.compile(r"\(By similarity\)\s*\.?\s*$")
CITED = re.compile(r"\(((?:PubMed:\d+(?:,\s*)?)+)\)\s*\.?\s*$")
COPIES_SAID = re.compile(r"\babout\s+(\d+)\s+copies of ([A-Za-z][A-Za-z0-9-]*)")


class Breach(SystemExit):
    pass


def read_json(path: Path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def lines_of(entry):
    """The sentences of a UniProt entry's FUNCTION and SUBUNIT comments that name the vault particle, each with the evidence
    its own closing note gives (UniProt marks a sentence "(By similarity)" or with the publications it cites), and, for a
    sentence by similarity, the accession the comment's evidence names (ECO:0000250)."""
    out = []
    for comment in entry.get("comments") or []:
        if comment.get("commentType") not in ("FUNCTION", "SUBUNIT"):
            continue
        for text in comment.get("texts") or []:
            value = text.get("value") or ""
            evidences = text.get("evidences") or []
            similar_to = sorted({e.get("id") for e in evidences if e.get("evidenceCode") == "ECO:0000250" and e.get("id")})
            for sentence in SENTENCE.split(value):
                if not NAMES_THE_VAULT.search(sentence):
                    continue
                cited = CITED.search(sentence)
                if SIMILAR.search(sentence):
                    how, ids = "by similarity", []
                elif cited:
                    how, ids = "cited", re.findall(r"PubMed:(\d+)", cited.group(1))
                else:
                    how, ids = "unmarked", []
                out.append({"comment": comment["commentType"].lower(), "says": sentence.strip().rstrip("."), "evidence": how, "publications": ids,
                            "similar_to": similar_to if how == "by similarity" else []})
    return out


def organisms_of(datasets, folders):
    """The organism of every entry in the saved entry files, by accession (a sentence "by similarity" names an accession; the
    card says whose protein it is where a saved file says)."""
    out = {}
    for folder in folders:
        for path in sorted((Path(datasets) / folder).glob("*.json")):
            if path.name != "MANIFEST.json":
                entry = read_json(path)
                if isinstance(entry, dict) and "primaryAccession" in entry:
                    out[entry["primaryAccession"]] = (entry.get("organism") or {}).get("scientificName")
    return out


def vault_entries(datasets, folders, taxon):
    """Reviewed entries of the species (by the entry's own organism) in the saved entry files, with their vault lines."""
    organisms = organisms_of(datasets, folders)
    found = {}
    for folder in folders:
        for path in sorted((Path(datasets) / folder).glob("*.json")):
            if path.name == "MANIFEST.json":
                continue
            entry = read_json(path)
            if not isinstance(entry, dict) or "primaryAccession" not in entry:
                continue
            if (entry.get("organism") or {}).get("taxonId") != taxon:
                continue
            if not str(entry.get("entryType", "")).startswith("UniProtKB reviewed"):
                continue
            lines = lines_of(entry)
            if not lines:
                continue
            also = also_lines(entry)
            for line in lines + also:
                if line["similar_to"]:
                    line["similar_of"] = {accession: organisms.get(accession) for accession in line["similar_to"]}
            name = ((entry.get("proteinDescription") or {}).get("recommendedName") or {}).get("fullName", {}).get("value")
            genes = [g.get("geneName", {}).get("value") for g in entry.get("genes") or []]
            found[entry["primaryAccession"]] = {"id": entry["primaryAccession"], "gene": next((g for g in genes if g), None), "label": name, "folder": folder, "file": path.name, "lines": lines, "also": also,
                                               "length": (entry.get("sequence") or {}).get("length")}
    return found


# A sentence that makes the protein a component of another complex (TEP1 of telomerase): kept beside the vault's lines, said as the entry says it.
ALSO_COMPONENT = re.compile(r"\b(?:Associated )?[Cc]omponent of (?:the )?(?!vault)[^.(]*?(?:complex|holoenzyme)\b")


def also_lines(entry):
    """The sentences of an entry's FUNCTION and SUBUNIT comments that make the protein a component of another complex, each
    with the evidence its own closing note gives."""
    out = []
    for comment in entry.get("comments") or []:
        if comment.get("commentType") not in ("FUNCTION", "SUBUNIT"):
            continue
        for text in comment.get("texts") or []:
            similar_to = sorted({e.get("id") for e in text.get("evidences") or [] if e.get("evidenceCode") == "ECO:0000250" and e.get("id")})
            for sentence in SENTENCE.split(text.get("value") or ""):
                if NAMES_THE_VAULT.search(sentence) or not ALSO_COMPONENT.search(sentence):
                    continue
                cited = CITED.search(sentence)
                how, ids = ("by similarity", []) if SIMILAR.search(sentence) else (("cited", re.findall(r"PubMed:(\d+)", cited.group(1))) if cited else ("unmarked", []))
                out.append({"comment": comment["commentType"].lower(), "says": sentence.strip().rstrip("."), "evidence": how, "publications": ids, "similar_to": similar_to if how == "by similarity" else []})
    return out


def footing_of_entry(lines):
    """How a reviewed entry names the vault: every sentence by similarity, or at least one citing a publication."""
    return "by similarity" if all(line["evidence"] == "by similarity" for line in lines) else "cited"


def portal_entries(portal_rows, word):
    """The Complex Portal entries of the species whose name holds the word (rows: the file's, as a list of dicts)."""
    return [row for row in portal_rows if re.search(rf"\b{re.escape(word)}\b", row["Recommended name"], re.I)]


def read_portal_rows(text):
    rows = list(csv.reader(io.StringIO(text), delimiter="\t"))
    head = [name.lstrip("#") for name in rows[0]]
    return [dict(zip(head, row)) for row in rows[1:]]


def portal_vault(row):
    """What the entry gives: its protein members with the copies it states (0: none stated), the molecules that are no protein,
    the size and mass its description gives, and its evidence code."""
    members, others = {}, []
    for item in row["Identifiers (and stoichiometry) of molecules in complex"].split("|"):
        found = re.match(r"^([A-Z0-9]+)(?:-[A-Z0-9_]+)?\((\d+)\)$", item.strip())
        if found and re.match(r"^[OPQ][0-9][A-Z0-9]{3}[0-9]$|^[A-NR-Z][0-9]([A-Z][A-Z0-9]{2}[0-9]){1,2}$", found.group(1)):
            members[found.group(1)] = int(found.group(2))
        else:
            others.append(re.sub(r"\(\d+\)$", "", item.strip()))
    description = " ".join([row.get("Description") or "", row.get("Complex properties") or ""])
    size = re.search(r"size\s+(\d+(?:\.\d+)?)\s*[x×]\s*(\d+(?:\.\d+)?)\s*[x×]\s*(\d+(?:\.\d+)?)\s*nm", description)
    mass = re.search(r"approximately\s+(\d+(?:\.\d+)?)\s*MDa", description)
    # A sentence of the entry that gives a number of copies of one of its molecules ("about 9 copies of <its name>"): kept in the
    # entry's own words, with the name it uses; whose protein that is, is found from the name by the caller, never typed here.
    said = None
    for sentence in SENTENCE.split(description):
        copies = COPIES_SAID.search(sentence)
        if copies:
            said = {"of": copies.group(2), "copies": int(copies.group(1)), "says": sentence.strip().rstrip(".")}
            break
    return {"id": row["Complex ac"], "name": row["Recommended name"], "members": members, "others": others,
            "evidence": re.match(r"^(ECO:\d+)", row["Evidence Code"]).group(1) if row.get("Evidence Code") else None,
            "size_nm": [float(x) for x in size.groups()] if size else None, "mass_MDa": float(mass.group(1)) if mass else None,
            "copies_said": said}


def copies_line(lines, name):
    """The sentence among a reviewed entry's vault lines that gives a number of the molecules of the named protein ("up to 78
    <name> molecules"), as the entry says it, with its evidence; None where no sentence does."""
    wanted = re.compile(rf"\b\d+\s+{re.escape(name)}\s+molecules\b")
    return next(({"comment": line["comment"], "says": line["says"], "evidence": line["evidence"], "publications": line["publications"]} for line in lines if wanted.search(line["says"])), None)


def signature_hits(accessions_by_signature, wanted):
    """Which of the species' proteins carry the signature (a mapping from a signature to its proteins)."""
    return sorted(accessions_by_signature.get(wanted) or [])


def own_structure(answer, taxon, held, share, copies, lengths):
    """The entry that stands for the vault in a species: among the deposited entries whose source organism is the species (by
    taxon), those whose first biological assembly holds at least `copies` copies of a major vault protein entity covering at
    least `share` of the reference protein's length (the particle, not a fragment of its repeats). The best resolution first;
    the first of them whose assembly file is held. Entries that fail are listed with why, so that a mouse's fragments of seven
    repeats (3GNF and its kin) are seen to be left out and never taken for the particle."""
    ranked, left_out = [], []
    for entry in answer["data"]["entries"]:
        for entity in entry.get("polymer_entities") or []:
            organisms = {o.get("ncbi_taxonomy_id") for o in entity.get("rcsb_entity_source_organism") or []}
            if taxon not in organisms:
                continue
            reference = (entity.get("rcsb_polymer_entity_align") or [{}])[0].get("reference_database_accession")
            seq = len((entity.get("entity_poly") or {}).get("pdbx_seq_one_letter_code_can") or "")
            whole = lengths.get(reference)
            instances = max([a["rcsb_assembly_info"]["polymer_entity_instance_count"] for a in entry.get("assemblies") or []] or [0])
            covered = (seq / whole) if whole else None
            resolution = (entry["rcsb_entry_info"].get("resolution_combined") or [None])[0]
            # The entity as the entry's own records give it: its number in the entry, its description and its source organism's name.
            named = next((o.get("ncbi_scientific_name") for o in entity.get("rcsb_entity_source_organism") or [] if o.get("ncbi_taxonomy_id") == taxon), None)
            row = {"entry": entry["rcsb_id"], "title": entry["struct"]["title"], "method": entry["exptl"][0]["method"], "resolution_A": resolution, "copies": instances, "covers": round(covered, 3) if covered is not None else None, "protein": reference,
                   "entity": str(entity.get("rcsb_id") or "").split("_")[-1] or None, "description": (entity.get("rcsb_polymer_entity") or {}).get("pdbx_description"), "organism": named}
            if covered is not None and covered >= share and instances >= copies:
                ranked.append(row)
            else:
                why = []
                if covered is None or covered < share:
                    why.append(f"its entity holds {round(100 * covered)} per cent of the protein's {whole} residues" if covered is not None else "its entity has no reference protein")
                if instances < copies:
                    why.append(f"its first assembly holds {instances} {'copy' if instances == 1 else 'copies'}, not the particle's {copies}")
                left_out.append({**row, "why": "; ".join(why)})
    ranked.sort(key=lambda r: (r["resolution_A"] is None, r["resolution_A"] or 0, r["entry"]))
    chosen = next((r for r in ranked if any(h["entry"] == r["entry"] for h in held)), None)
    return {"ranked": ranked, "left_out": sorted(left_out, key=lambda r: r["entry"]), "chosen": chosen, "better_not_held": [r["entry"] for r in ranked[: ranked.index(chosen)]] if chosen else [r["entry"] for r in ranked]}


def preprint_statements(text, spec):
    """The preprint's statements the vault's card carries, each verified in the saved page: its words must stand in the section
    it names (and in the paragraph that begins as it says), so that no number is taken that the page does not give. The page is
    read as text (tags removed); its sections are its second-level headings."""
    import html as _html
    body = re.sub(r"(?s)<(script|style).*?</\1>", "", text)
    parts = re.split(r"(?s)(<h2[^>]*>.*?</h2>)", body)
    sections, current = {}, None
    for chunk in parts:
        if chunk.startswith("<h2"):
            current = re.sub(r"\s+", " ", _html.unescape(re.sub(r"<[^>]+>", "", chunk))).strip()
            sections.setdefault(current, [])
        elif current:
            sections[current].append(chunk)
    plain = {}
    for name, chunks in sections.items():
        joined = "".join(chunks).replace("</p>", "\n\n")
        plain[name] = re.sub(r"[ \t\r\f\v]+", " ", _html.unescape(re.sub(r"<[^>]+>", "", joined)))
    out = []
    for item in spec["statements"]:
        section = plain.get(item["section"])
        if section is None:
            raise Breach(f"the preprint's page has no section {item['section']}")
        scope = section
        if item.get("begins"):
            paragraphs = [p.strip() for p in re.split(r"\n\s*\n", section) if p.strip().startswith(item["begins"])]
            if len(paragraphs) != 1:
                raise Breach(f"the preprint's {item['section']} has {len(paragraphs)} paragraphs that begin {item['begins']!r}")
            scope = paragraphs[0]
        if re.sub(r"\s+", " ", item["contains"]) not in re.sub(r"\s+", " ", scope):
            raise Breach(f"the preprint does not say {item['contains']!r} in {item['place']}")
        out.append({"id": item["id"], "quote": item["contains"], "place": item["place"]})
    return out
