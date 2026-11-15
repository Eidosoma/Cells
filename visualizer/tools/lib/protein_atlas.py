"""The protein atlas part of the scene.

It turns the viewer's snapshot of the Cells law inventory (data/proteins/) into parts of
the scene: one part per functional unit, linked to the engine part that holds its law.

Three things are checked against the checkout being read, because the inventory was made
at an earlier revision:
  * every law record still names a tracked file that defines its identifier;
  * every identifier quoted in the inventory's text still exists (a curated rename is
    applied, anything else is warned about);
  * every drawn assembly agrees with the stoichiometry the inventory states.

The atlas keeps the inventory's own words for how sure a mapping is ("mapping") and what
stands behind a law ("evidence"). They are not engine statuses and never go in ``status``.

A unit has no species; which gene products would make it does. The inventory's candidates
are human. Every other species comes from a file (schema/SPECIES_ATLAS.md) that is checked
against its contract here, and each unit carries what each species' atlas says of it. The
laws, the mappings and the shapes drawn are the engine's and the same for every species.

A species' own proteins (schema/SPECIES_PROTEINS.md) are too many for the scene: each
species' file is published beside the page. The scene carries, for each, the file's name,
its counts and its sources, and the patterns of the addresses a protein is looked up at.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

from .static_eval import Unresolved, plain

IDENTIFIER = re.compile(r"\b[A-Za-z][A-Za-z0-9_]*@\d+")
PDB = re.compile(r"PDB (\d[A-Z0-9]{3})")
GROUP = "proteins"
SPECIES_FORMAT = "cells.visualizer.species_atlas@1"
SHELVES_FORMAT = "cells.visualizer.species_proteins@1"
SHELF_SIDES = ("outside", "in", "inside", "not known")
SHELF_BASES = ("stated", "predicted", "by function", "none")
SHELF_FILE = re.compile(r"members-\d+\.json$")
SHELF_LIMIT = 1024 * 1024  # a species' file stays under 1 MB (the contract's rule on size)
MACHINE = re.compile(r"/home/|/mnt/|/Users/|/tmp/|file://|\blocalhost\b")
DAY = re.compile(r"\d{4}-\d{2}-\d{2}$")
MOST_WARNINGS = 12  # for one species file; beyond that only their number is given


def _strings(value, out):
    if isinstance(value, str):
        out.add(value)
    elif isinstance(value, dict):
        for key, item in value.items():
            _strings(key, out)
            _strings(item, out)
    elif isinstance(value, (list, tuple, set, frozenset)):
        for item in value:
            _strings(item, out)


def _fill(template, value):
    return {"text": template["text"].replace("{id}", str(value)), "url": template["url"].replace("{id}", str(value))}


class Atlas:
    def __init__(self, build, snapshot, overlay, atlases=None, shelves=None):
        self.build = build
        self.shelves = shelves  # the folder that holds each species' own proteins, or None
        # The species atlases, read from a folder of files (none, if there is no folder).
        self.species = Species(snapshot, overlay, read_species_files(atlases)) if overlay.get("species") else None
        self.snapshot = snapshot
        self.overlay = overlay
        self.repo = build.repo
        self.engine = sorted(path for path in build.files if path.startswith("src/cells/") and path.endswith(".py"))
        self.texts = {}
        self.module_ids = {}
        self.renamed = {}
        self.mapping = {item["inventory"]: item for item in overlay["mappings"]}
        self.evidence = {item["id"]: item for item in overlay["evidence"]}
        self.sites = {item["id"]: item for item in overlay["sites"]}
        self.districts = {item["id"]: item for item in overlay["districts"]}

    # ------------------------------------------------------------ reading the checkout

    def text(self, path):
        if path not in self.texts:
            try:
                self.texts[path] = (self.repo / path).read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                self.texts[path] = ""
        return self.texts[path]

    def ids_defined_in(self, path):
        """Identifiers a module defines, including ones it builds (f-strings, comprehensions)."""
        if path not in self.module_ids:
            found = set(IDENTIFIER.findall(self.text(path)))
            package, evaluator = self.build.package, self.build.evaluator
            module = package.module(package.dotted_of(self.repo / path))
            values = set()
            for name in module.env if module else ():
                try:
                    _strings(plain(evaluator.constant(module, name)), values)
                except Unresolved:
                    continue
                except Exception:  # a construct the reader does not model; the text search still applies
                    continue
            found |= {value for value in values if IDENTIFIER.fullmatch(value)}
            self.module_ids[path] = found
        return self.module_ids[path]

    def check_laws(self):
        """Where each law record's identifier is found in the checkout being read."""
        tracked = set(self.engine)
        found = Counter()
        self.known_ids = set()
        for path in self.engine:
            self.known_ids |= set(IDENTIFIER.findall(self.text(path)))
        for law in self.snapshot["laws"]:
            self.known_ids |= self.ids_defined_in(law["file"]) if law["file"] in tracked else set()
        for law in self.snapshot["laws"]:
            name = law.get("id") or law.get("identity", "")[:60]
            if law["file"] not in tracked:
                found["missing"] += 1
                self.build.warnings.append(f"protein inventory: {name} names {law['file']}, which is not tracked any more")
                continue
            if not law.get("id"):
                function = re.match(r"(\w+)\(\)", law.get("identity", ""))
                if function and re.search(rf"^def {function.group(1)}\(", self.text(law["file"]), re.M):
                    found["function"] += 1
                else:
                    found["missing"] += 1
                    self.build.warnings.append(f"protein inventory: {name} is not defined in {law['file']} any more")
                continue
            if law["id"] in self.ids_defined_in(law["file"]):
                found["named_file"] += 1
            elif law["id"] in self.known_ids:
                found["elsewhere"] += 1
            else:
                found["missing"] += 1
                self.build.warnings.append(f"protein inventory: {law['id']} is not found in the engine any more")
        return dict(found)

    def gained_since(self, revision):
        """Identifiers the engine has gained since the inventory's revision. The inventory has not reviewed them."""
        def at(rev):
            # Quoted identifiers only, as the inventory's own census counts them: shorthand in a
            # comment (insertion@1) is not an identifier.
            listing = self.build.git("grep", "-o", "-E", "[\"'][A-Za-z][A-Za-z0-9_.]*@[0-9]+[\"']", rev, "--", "src/cells")
            found = {}
            for line in listing.splitlines():
                _, path, name = line.split(":", 2)
                found.setdefault(name.strip("\"'"), set()).add(path)
            return found

        before, now = at(revision), at("HEAD")
        if not before or not now:
            self.build.warnings.append(f"protein inventory: cannot compare the engine with revision {revision}")
            return None
        added = sorted(set(now) - set(before))
        places = Counter()
        for name in added:
            # Counted once, in the folder that holds most of its uses.
            folders = Counter("/".join(path.split("/")[2:-1]) or "the package root" for path in now[name])
            places[min(folders, key=lambda folder: (-folders[folder], folder))] += 1
        where = sorted(places.items(), key=lambda item: (-item[1], item[0]))[:3]
        # A review of what was gained is curated with the count it covered; beyond that count, the rest is unreviewed.
        review = self.overlay.get("gained_review")
        return {
            "added": len(added),
            "removed": len(set(before) - set(now)),
            "where": [list(item) for item in where],
            "review": {**review, "covers_all": len(added) <= review["count"]} if review else None,
        }

    def current(self, text):
        """Inventory text with identifiers that were renamed since brought up to date."""
        if not text:
            return text

        def swap(match):
            token = match.group(0)
            if token in self.known_ids:
                return token
            rename = self.overlay["renamed"].get(token)
            if rename and rename["to"] in self.known_ids:
                self.renamed[token] = rename["to"]
                return rename["to"]
            warning = f"protein inventory: its text names {token}, which the engine no longer has"
            if warning not in self.build.warnings:
                self.build.warnings.append(warning)
            return token

        return IDENTIFIER.sub(swap, text)

    # ------------------------------------------------------------ one unit

    def form(self, unit, kind, extra, mapping):
        stoichiometry = unit["assembly"].get("stoichiometry") or ""
        if mapping == "generic":
            # A generic law gets a plain stand-in: drawing subunits would claim a protein.
            neutral = kind.get("neutral")
            if not neutral:
                raise SystemExit(f"{unit['id']}: a generic {unit['kind']} has no plain form in the overlay")
            form = {**neutral, "style": "plain"}
        else:
            assembly = kind.get("assembly")
            if not assembly:
                raise SystemExit(f"{unit['id']}: {unit['kind']} has no assembly to draw in the overlay")
            if not re.search(kind["expects"], stoichiometry):
                self.build.warnings.append(
                    f"protein atlas: {unit['id']} is drawn as {assembly['shape']}, but its stoichiometry reads '{stoichiometry}'"
                )
            form = {key: value for key, value in assembly.items() if key not in ("aux", "hetero_if")}
            form["style"] = "solid" if mapping == "assigned" else "glass"
            if assembly.get("hetero_if") and re.search(assembly["hetero_if"], stoichiometry):
                form["hetero"] = True
            aux = []
            for item in assembly.get("aux", []) if extra.get("aux", True) else []:
                if not re.search(item["when"], stoichiometry):
                    continue
                firm = bool(item.get("firm_if") and re.search(item["firm_if"], stoichiometry))
                aux.append({"role": item["role"], "side": item["side"], "count": item["count"], "firm": firm})
            if aux:
                form["aux"] = aux
        if extra.get("flip"):
            form["flip"] = True
        return form

    def law_item(self, law):
        evidence = self.evidence.get(law.get("evidence_kind"))
        if evidence is None:
            raise SystemExit(f"{law.get('id')}: unknown kind of evidence {law.get('evidence_kind')}")
        lines = []
        if law.get("ion_routes"):
            ions = ", ".join(ion if weight == 1 else f"{ion} × {weight:g}" for ion, weight in law["ion_routes"])
            lines.append(f"Passes {ions}")
        if law.get("coefficients"):
            lines.append(f"Coefficients: {self.current(law['coefficients'])}")
        published = law.get("published") or {}
        if published.get("citation"):
            context = ", ".join(published[key] for key in ("organism", "cell_type", "preparation") if published.get(key))
            lines.append(published["citation"] + (f" ({context})" if context else ""))
        links = []
        if published.get("pmid"):
            links.append(_fill(self.overlay["links"]["pubmed"], published["pmid"]))
        return {
            "label": law.get("id") or self.current(law.get("identity")),
            "code": bool(law.get("id")),
            "tag": evidence["label"],
            "tag_title": evidence["description"],
            "lines": lines,
            "note": self.current(law.get("notes")),
            "links": links,
        }

    def product_item(self, product):
        record = self.snapshot["products"].get(product["gene"], {})
        human = record.get("human", {})
        links, lines = [], []
        if human.get("protein_name"):
            length = f", {human['length']:,} amino acids" if human.get("length") else ""
            lines.append(f"{human['protein_name']}{length}")
        accession = product.get("human_uniprot") or human.get("accession")
        templates = self.overlay["links"]
        if accession:
            links.append(_fill(templates["uniprot"], accession))
            if human.get("length") and human["length"] <= self.overlay["alphafold_longest"]:
                links.append(_fill(templates["alphafold"], accession))
        links.append(_fill(templates["hpa"], product["gene"]))
        frog = sorted(record.get("xenopus_laevis", []), key=lambda entry: (not entry["reviewed"], entry["accession"]))
        if frog:
            for entry in frog[:2]:
                link = _fill(templates["uniprot"], entry["accession"])
                link["text"] = f"X. laevis {entry['accession']}"
                links.append(link)
        else:
            lines.append("No Xenopus laevis entry found in UniProt by gene name")
        return {"label": product["gene"], "detail": product.get("role"), "lines": lines, "links": links}

    def structure_item(self, structure):
        method = ", ".join(name.capitalize() for name in structure.get("method", []))
        resolution = f", {structure['resolution_A']:g} Å" if structure.get("resolution_A") else ""
        assembly = structure.get("assembly", {})
        shape = ", ".join(str(part) for part in (assembly.get("kind"), assembly.get("symmetry")) if part)
        parts = "; ".join(
            f"{entity.get('copies', '?')} × {entity['description']}" + (f" ({', '.join(entity['organism'])})" if entity.get("organism") else "")
            for entity in structure.get("entities", [])
            if entity.get("description")
        )
        lines = [line for line in (f"{method}{resolution}" if method else "", f"Assembly in the entry: {shape}" if shape else "", parts) if line]
        links = [_fill(self.overlay["links"]["rcsb"], structure["pdb"])]
        if structure.get("citation", {}).get("doi"):
            links.append(_fill(self.overlay["links"]["doi"], structure["citation"]["doi"]))
        return {"label": f"PDB {structure['pdb']}", "detail": structure.get("title"), "lines": lines, "links": links}

    def unit(self, unit, laws, structures):
        build, overlay = self.build, self.overlay
        kind = overlay["kinds"].get(unit["kind"])
        if kind is None:
            raise SystemExit(f"{unit['id']}: the overlay has no entry for the kind '{unit['kind']}'")
        extra = overlay["units"].get(unit["id"])
        if extra is None:
            raise SystemExit(f"{unit['id']} ({unit['name']}) has no overlay entry")
        if extra["name"] != unit["name"]:
            build.warnings.append(f"protein atlas: {unit['id']} is '{unit['name']}' in the inventory, '{extra['name']}' in the overlay")
        mapping = self.mapping.get(unit["status"])
        if mapping is None:
            raise SystemExit(f"{unit['id']}: unknown mapping status '{unit['status']}'")
        district = extra.get("district", kind["district"])
        site = extra.get("site", kind["site"])
        if district not in self.districts or site not in self.sites:
            raise SystemExit(f"{unit['id']}: unknown district {district} or site {site}")
        generic = mapping["id"] == "generic"
        stoichiometry = unit["assembly"].get("stoichiometry")
        facts = [["Kind", unit["kind"]]]
        if stoichiometry:
            facts.append(["Candidate assembly" if generic else "Assembly", stoichiometry])
        if unit["assembly"].get("sources"):
            facts.append(["Assembly from", "; ".join(unit["assembly"]["sources"])])
        facts.append(["Engine laws", str(len(laws))])

        # The keys let the view put a species' gene products in the place of the inventory's.
        sections = [{"key": "laws", "title": "Engine laws", "items": [self.law_item(law) for law in laws]}]
        if unit.get("products"):
            sections.append({"key": "products", "title": "Candidate products", "items": [self.product_item(product) for product in unit["products"]]})
        cited = [pdb for source in unit["assembly"].get("sources", []) for pdb in PDB.findall(source)]
        shown = [structures[pdb] for pdb in dict.fromkeys(cited) if pdb in structures]
        if shown:
            sections.append({"key": "structures", "title": "Reference structures", "items": [self.structure_item(item) for item in shown]})

        tracked = set(build.files)
        sources = [{"path": overlay["plan"]["path"], "where": overlay["plan"]["where"]}]
        for path in dict.fromkeys(path for law in laws for path in law.get("docs", [])):
            if path in tracked:
                sources.append({"path": path})
            else:
                self.dropped_docs.add(path)
        for path in dict.fromkeys(law["file"] for law in laws):
            if path in tracked:
                sources.append({"path": path})

        notes = [text for text in (mapping.get("note"), self.current(unit.get("note"))) if text]
        identifier = f"unit.{unit['id']}"
        genes = [product["gene"] for product in unit.get("products", [])]
        build.add(
            {
                "id": identifier,
                "label": unit["name"],
                "short": extra["short"],
                "kind": "unit",
                "group": GROUP,
                "eyebrow": self.districts[district]["label"],
                "district": district,
                "site": site,
                "mapping": mapping["id"],
                "swatch": f"map-{mapping['id']}",
                "evidence": sorted({law["evidence_kind"] for law in laws}),
                "form": self.form(unit, kind, extra, mapping["id"]),
                "plain": kind.get("plain_generic", kind["plain"]) if generic else kind["plain"],
                "note": " ".join(notes) or None,
                "chips": [
                    {"label": mapping["label"], "title": mapping["description"], "swatch": f"map-{mapping['id']}"},
                    {"label": self.sites[site]["label"], "title": overlay["site_note"]},
                ],
                "facts": facts,
                "sections": sections,
                "sources": sources,
                "keywords": " ".join([*[law["id"] for law in laws if law.get("id")], *genes, *cited]),
                # What each species atlas says of this unit; the inventory's own candidates stay in "sections".
                **({"species": self.species.of_unit(unit["id"])} if self.species and self.species.atlases else {}),
            }
        )
        for law in laws:
            owner = build.owner.get(law["file"])
            if owner and owner in build.entities:
                build.link(identifier, owner, "modelled_by", law.get("id") or "a function without an identifier")
            else:
                build.warnings.append(f"protein atlas: {law['file']} ({unit['id']}) belongs to no part of the engine map")
        target = extra.get("cell_view", kind.get("cell_view"))
        if target:
            if target not in build.entities:
                raise SystemExit(f"{unit['id']}: the overlay points at {target}, which the scene does not have")
            build.link(identifier, target, "shown_as")
        return mapping["id"]

    # ------------------------------------------------------------ the whole atlas

    def run(self):
        snapshot, overlay = self.snapshot, self.overlay
        found = self.check_laws()
        self.dropped_docs = set()
        laws_of = {}
        for law in snapshot["laws"]:
            for unit_id in [law["unit"], *law.get("also_in", [])]:
                laws_of.setdefault(unit_id, []).append(law)
        structures = {structure["pdb"]: structure for structure in snapshot["structures"]}
        unknown = sorted(set(overlay["units"]) - {unit["id"] for unit in snapshot["units"]})
        if unknown:
            self.build.warnings.append(f"protein atlas: the overlay names units the inventory does not have: {unknown}")
        by_mapping, by_district = Counter(), Counter()
        for unit in snapshot["units"]:
            mapping = self.unit(unit, laws_of.get(unit["id"], []), structures)
            by_mapping[mapping] += 1
            by_district[overlay["units"][unit["id"]].get("district", overlay["kinds"][unit["kind"]]["district"])] += 1
        if self.dropped_docs:
            self.build.warnings.append(
                f"protein inventory: it cites documents that are not tracked any more: {sorted(self.dropped_docs)}"
            )
        evidence_laws = Counter(law["evidence_kind"] for law in snapshot["laws"])
        described = snapshot["inventory"]
        species = {}
        if self.species:
            self.build.warnings.extend(self.species.warnings)
            words = self.overlay["species"]
            species = {
                "atlases": self.species.summary(),
                "findings": words["findings"],
                "product_evidence": words["evidence"],
                "no_entry": words["no_entry"],
                "remarks": self.species.remarks,  # for the build's report; not written to the scene
            }
        # Each species' own proteins: published beside the page, summarised here.
        own = {}
        if self.shelves is not None and overlay.get("shelves"):
            summaries, breaches = read_shelves(self.shelves)
            self.build.warnings.extend(breaches)
            own = {"shelves": summaries, "shelf_links": shelf_links(overlay["shelves"])}
        return {
            "title": overlay["title"],
            "summary": overlay["summary"],
            "caveat": overlay["caveat"],
            "stamp": {
                "inventory": described["kind"],
                "created": described["created"],
                "read_at": described["read_at_revision"],
                "records": len(snapshot["laws"]),
                "found": found,
                "renamed": [{"from": old, "to": new} for old, new in sorted(self.renamed.items())],
                "gained": self.gained_since(described["read_at_revision"]),
            },
            "counts": {
                "units": len(snapshot["units"]),
                "laws": described["counts"]["laws"],
                "records": described["counts"]["records"],
                "genes": described["counts"]["candidate_genes"],
                "structures": len(snapshot["structures"]),
            },
            "mappings": [
                {"id": item["id"], "label": item["label"], "description": item["description"], "count": by_mapping[item["id"]]}
                for item in overlay["mappings"]
            ],
            "evidence": [
                {"id": item["id"], "label": item["label"], "description": item["description"], "count": evidence_laws[item["id"]]}
                for item in overlay["evidence"]
            ],
            "sites": overlay["sites"],
            "districts": [{**item, "count": by_district[item["id"]]} for item in overlay["districts"]],
            "sources": snapshot["sources"],
            "not_copied": snapshot["not_copied"],
            **species,
            **own,
        }


# ---------------------------------------------------------------- a species' own proteins


def shelf_links(words):
    """The patterns of the addresses a protein or a family is looked up at, as the page takes them.

    The overlay keeps, with each pattern, a note of when it was checked; the page needs the pattern only.
    """
    def plain(pattern):
        return {key: value for key, value in pattern.items() if key != "checked"}

    return {key: plain(value) if isinstance(value, dict) else [plain(item) for item in value] for key, value in words.get("links", {}).items()}


# The name under which a file with several shelves counts the proteins that are on none.
SHELF_NONE = "no shelf"


def _off_shelf(ids, shelf, sides):
    """What is wrong with the shelf of a line whose proteins sit on these sides, or None.

    A line's shelf is one of the file's, or null. With one shelf, null is that shelf. With
    several, null is no shelf at all, which only proteins with no known side may have.
    """
    if not ids:
        return None  # the shelves themselves are not sound, which is said already
    if shelf is None:
        if len(ids) > 1 and any(count and side != "not known" for side, count in sides.items()):
            return "it is on no shelf, yet a side of it is known"
        return None
    if shelf not in ids:
        return f"its shelf {shelf!r} is not one of the file's"
    return None


def read_shelves(folder):
    """What the scene says of each species' own proteins: (summaries, warnings).

    Every `<species>/shelves.json` under the folder is held to its contract
    (schema/SPECIES_PROTEINS.md). A file that breaks it is warned about and left out; it
    never stops the build. The scene gets the file's name beside the page, its counts and
    its sources, and for a large catalogue the names of the files of its families' members.
    Where a species has several shelves, the scene also gets each shelf's id, label and
    counts, and how many proteins are on no shelf.
    """
    summaries, warnings = [], []
    folder = Path(folder) if folder else None
    if folder is None or not folder.is_dir():
        return summaries, warnings
    for path in sorted(folder.glob("*/shelves.json")):
        name = path.parent.name
        problems = []
        try:
            text = path.read_text(encoding="utf-8")
            data = json.loads(text)
        except (OSError, ValueError) as error:
            warnings.append(f"species proteins {name}: shelves.json could not be read as JSON ({type(error).__name__}); left out")
            continue
        summary = _shelves_summary(name, data, len(text.encode("utf-8")), problems)
        if MACHINE.search(text):
            problems.append("it holds a machine path")
        if problems:
            more = f" (and {len(problems) - 3} more)" if len(problems) > 3 else ""
            warnings.append(f"species proteins {name}: {'; '.join(problems[:3])}{more}; left out")
            continue
        summaries.append(summary)
    return summaries, warnings


def _shelves_summary(name, data, size, problems):
    """One species' summary for the scene; what breaks the contract is added to `problems`."""
    if not isinstance(data, dict) or data.get("format") != SHELVES_FORMAT:
        problems.append(f"its format is not {SHELVES_FORMAT}")
        return None
    if data.get("species") != name:
        problems.append(f"it says it holds the proteins of {data.get('species')!r}")
    if size >= SHELF_LIMIT:
        problems.append(f"it is {size / 1024:.0f} KB; a species' file stays under 1 MB")
    shelves = data.get("shelves")
    if not isinstance(shelves, list) or not shelves or not all(isinstance(shelf, dict) and all(_text(shelf.get(key)) for key in ("id", "label", "outside", "inside")) for shelf in shelves):
        problems.append("its shelves need an id, a label and the names of their two sides")
        shelves = []
    # Several shelves: every line is on one of them or on none, and each shelf is counted on its own.
    shelf_ids = [shelf["id"] for shelf in shelves]
    several = len(shelf_ids) > 1
    if several and (len(set(shelf_ids)) != len(shelf_ids) or SHELF_NONE in shelf_ids):
        problems.append("its shelves do not each have an id of their own")
    on_shelf = {shelf: Counter() for shelf in [*shelf_ids, None]}
    sources = data.get("sources")
    if not isinstance(sources, list) or not sources or not all(isinstance(source, dict) and _text(source.get("name")) and _text(source.get("licence")) for source in sources):
        problems.append("every source needs a name and its licence")
        sources = []
    listed, grouped = data.get("proteins"), data.get("families")
    if isinstance(listed, list) == isinstance(grouped, list):
        problems.append("it holds either proteins or families, one of the two")
        return None
    counts = Counter()
    summary = {"id": name, "file": f"proteins/{name}/shelves.json", "bytes": size, "made": data.get("made") if DAY.match(str(data.get("made"))) else None, "from": _text(data.get("from"))}
    if isinstance(listed, list):
        columns = data.get("columns") or []
        missing = [key for key in ("id", "label", "shelf", "side", "basis", "group", "unit", "marks") if key not in columns]
        if missing:
            problems.append(f"its columns lack {', '.join(missing)}")
            return None
        at = {key: index for index, key in enumerate(columns)}
        groups = {group.get("id") for group in data.get("groups") or [] if isinstance(group, dict)}
        marks = set(data.get("marks") or {})
        ids = set()
        for line in listed:
            if not isinstance(line, list) or len(line) != len(columns):
                problems.append("a protein's line does not have the columns' length")
                break
            if line[at["side"]] not in SHELF_SIDES or line[at["basis"]] not in SHELF_BASES:
                problems.append(f"{line[at['id']]}: its side or its basis is not one of the contract's words")
                break
            if (line[at["side"]] == "not known") != (line[at["basis"]] == "none"):
                problems.append(f"{line[at['id']]}: a side that is not known has the basis none, and no other has")
                break
            if line[at["group"]] not in groups:
                problems.append(f"{line[at['id']]}: its group {line[at['group']]!r} is not declared")
                break
            if set(line[at["marks"]] or {}) - marks:
                problems.append(f"{line[at['id']]}: it carries a mark that is not declared")
                break
            wrong = _off_shelf(shelf_ids, line[at["shelf"]], {line[at["side"]]: 1})
            if wrong:
                problems.append(f"{line[at['id']]}: {wrong}")
                break
            ids.add(line[at["id"]])
            counts[line[at["side"]]] += 1
            on_shelf[line[at["shelf"]] if several else None][line[at["side"]]] += 1
        if len(ids) != len(listed):
            problems.append("two proteins share an identifier")
        summary.update(kind="proteins", proteins=len(listed))
    else:
        columns = data.get("family_columns") or []
        missing = [key for key in ("id", "label", "shelf", "side", "group", "count", "sides", "file", "at") if key not in columns]
        none = data.get("no_family")
        if missing or not isinstance(none, dict):
            problems.append(f"its family columns lack {', '.join(missing)}" if missing else "it does not say where the proteins with no family are")
            return None
        at = {key: index for index, key in enumerate(columns)}
        part_columns = none.get("part_columns") or []
        part_at = {key: index for index, key in enumerate(part_columns)}
        parts = none.get("parts") or []
        if parts and any(key not in part_at for key in ("id", "label", "side", "count", "sides", "file", "at", *(["shelf"] if several else []))):
            problems.append("the parts of no_family lack a column")
            return None
        if several and not parts and none.get("count"):
            problems.append("on several shelves the proteins with no family are given in parts, each on its shelf")
        files = []
        seen = set()
        for line, where, what in [(line, at, "family") for line in grouped] + [(line, part_at, "part") for line in parts]:
            if not isinstance(line, list):
                problems.append("a family's line is not a list")
                break
            count, sides, file, span = line[where["count"]], line[where["sides"]], line[where["file"]], line[where["at"]]
            if line[where["side"]] not in SHELF_SIDES or not isinstance(sides, dict) or set(sides) - set(SHELF_SIDES) or sum(sides.values()) != count:
                problems.append(f"{line[where['id']]}: its sides do not add up to its {count} members")
                break
            if not isinstance(file, str) or not SHELF_FILE.match(file) or not isinstance(span, list) or len(span) != 2 or span[1] - span[0] != count:
                problems.append(f"{line[where['id']]}: its file and its place in it do not hold its {count} members")
                break
            # Its shelf: one of the file's, or none; and a family has one line on a shelf, not two.
            shelf = line[where["shelf"]] if "shelf" in where else None
            wrong = _off_shelf(shelf_ids, shelf, sides)
            if not wrong and several and shelf is None and line[where["side"]] != "not known":
                wrong = "it is on no shelf, yet it stands on a side"
            if not wrong and (what, line[where["id"]], shelf) in seen:
                wrong = f"the {what} has two lines on one shelf"
            if wrong:
                problems.append(f"{line[where['id']]}: {wrong}")
                break
            seen.add((what, line[where["id"]], shelf))
            if file not in files:
                files.append(file)
            counts.update(sides)
            on_shelf[shelf if several else None].update(sides)
        if not parts:
            # No family, given whole: it opens like one family.
            counts.update(none.get("sides") or {})
            if none.get("count") and (not SHELF_FILE.match(str(none.get("file"))) or not isinstance(none.get("at"), list)):
                problems.append("no_family has neither parts nor a file of its own")
            elif none.get("count") and none["file"] not in files:
                files.append(none["file"])
        if sum(line[part_at["count"]] for line in parts if isinstance(line, list)) != (none.get("count", 0) if parts else 0):
            problems.append("the parts of no_family do not add up to its count")
        summary.update(kind="families", proteins=sum(counts.values()), families=len(grouped), no_family=none.get("count", 0), parts=len(parts), members=sorted(files))
        if several:
            # A family split over shelves is one family: the scene counts the families, and their lines apart.
            distinct = len({line[at["id"]] for line in grouped if isinstance(line, list)})
            summary.update(families=distinct, family_lines=len(grouped))
            if isinstance(data.get("distinct_families"), int) and data["distinct_families"] != distinct:
                problems.append(f"it says it has {data['distinct_families']} families; its lines are of {distinct}")
    stated = data.get("counts")
    if isinstance(stated, dict) and {side: stated.get(side, 0) for side in SHELF_SIDES} != {side: counts[side] for side in SHELF_SIDES}:
        problems.append("its counts by side are not those of its lines")
    summary["counts"] = {side: counts[side] for side in SHELF_SIDES}
    if several:
        said = data.get("shelf_counts")
        if isinstance(said, dict):
            if set(said) - set(shelf_ids) - {SHELF_NONE}:
                problems.append("it counts a shelf that it does not have")
            for shelf in [*shelf_ids, None]:
                given = said.get(SHELF_NONE if shelf is None else shelf) or {}
                if not isinstance(given, dict) or {side: given.get(side, 0) for side in SHELF_SIDES} != {side: on_shelf[shelf][side] for side in SHELF_SIDES}:
                    problems.append(f"its counts for {'the proteins on no shelf' if shelf is None else 'the shelf ' + shelf} are not those of its lines")
                    break
        summary["shelves"] = [{"id": shelf["id"], "label": shelf["label"], "proteins": sum(on_shelf[shelf["id"]].values()), "counts": {side: on_shelf[shelf["id"]][side] for side in SHELF_SIDES}} for shelf in shelves]
        summary["no_shelf"] = sum(on_shelf[None].values())
    summary["sources"] = [{key: source[key] for key in ("name", "url", "release", "accessed", "licence", "class", "through", "holds", "cite") if _text(source.get(key))} for source in sources]
    return summary


# ---------------------------------------------------------------- species atlases


def _key(text):
    """A database's name as it is compared: letters and digits only, in lower case."""
    return re.sub(r"[^a-z0-9]", "", str(text).lower())


def _text(value):
    """A string with something in it, or None."""
    return value.strip() if isinstance(value, str) and value.strip() else None


def read_species_files(folder):
    """Every species atlas in a folder, as (name, data, problem). No folder is no atlas.

    A file that is still being written, or is not JSON, is reported and left out. It never stops the build.
    """
    files = []
    folder = Path(folder) if folder else None
    if folder is None or not folder.is_dir():
        return files
    for path in sorted(folder.glob("*.json")):
        try:
            files.append((path.stem, json.loads(path.read_text(encoding="utf-8")), None))
        except (OSError, ValueError) as error:
            files.append((path.stem, None, f"could not be read as JSON ({type(error).__name__})"))
    return files


class Species:
    """The species atlases: which gene products would make each unit, species by species.

    The human atlas is the inventory's own. Its products already stand in every unit, so it
    is only described here, and it states no findings: the snapshot does not. Every other
    atlas is a file under the contract in schema/SPECIES_ATLAS.md. Whatever breaks the
    contract is a warning and is left out of the scene; the rest of the file is kept.
    Nothing here reads the checkout, so the checks run on their own.
    """

    def __init__(self, snapshot, overlay, files=()):
        self.snapshot = snapshot
        self.words = overlay["species"]
        self.links = overlay["links"]
        self.findings = {item["id"]: item for item in self.words["findings"]}
        self.evidence = {item["id"]: item for item in self.words["evidence"]}
        self.unit_ids = [unit["id"] for unit in snapshot["units"]]
        self.warnings = []
        self.remarks = []  # within the contract's letter, but worth a look
        self.atlases = []
        for name, data, problem in files:
            self.read(name, data, problem)

    def read(self, name, data, problem):
        said, noted = [], []
        atlas = None
        if problem:
            said.append(f"left out, the file {problem}")
        else:
            atlas = self.check(name, data, said.append, noted.append)
        if len(said) > MOST_WARNINGS:
            said = said[:MOST_WARNINGS] + [f"and {len(said) - MOST_WARNINGS} more problems"]
        self.warnings += [f"species atlas {name}: {text}" for text in said]
        self.remarks += [f"species atlas {name}: {text}" for text in noted]
        if atlas:
            self.atlases.append(atlas)

    # ------------------------------------------------------------ the contract

    def check(self, name, data, warn, note):
        """One file against the contract. Returns what is sound in it, or None if it cannot be shown."""
        if not isinstance(data, dict) or data.get("format") != SPECIES_FORMAT:
            found = data.get("format") if isinstance(data, dict) else type(data).__name__
            warn(f"left out, its format is {found!r}, not {SPECIES_FORMAT!r}")
            return None
        species = data.get("species") if isinstance(data.get("species"), dict) else {}
        identifier, label = _text(species.get("id")), _text(species.get("label"))
        if not identifier or not label:
            warn("left out, its species block lacks an id or a label")
            return None
        if identifier in {self.words["reference"]["id"], *(atlas["species"]["id"] for atlas in self.atlases)}:
            warn(f"left out, the species id '{identifier}' is already taken")
            return None
        if identifier != name:
            warn(f"its species id is '{identifier}', but the file is named {name}.json")
        lacking = [key for key in ("organism", "plain") if not _text(species.get(key))]
        if not isinstance(species.get("taxon"), int) or isinstance(species.get("taxon"), bool):
            lacking.append("taxon")
        if not (isinstance(data.get("made"), str) and DAY.match(data["made"])):
            lacking.append("made (a date)")
        method = [line for line in data.get("method") or [] if _text(line)] if isinstance(data.get("method"), list) else []
        if not method:
            lacking.append("method")
        if not _text(data.get("not_copied")):
            lacking.append("not_copied")
        sources = []
        for source in data.get("sources") if isinstance(data.get("sources"), list) else []:
            if not isinstance(source, dict) or not _text(source.get("name")):
                warn("one of its sources has no name")
                continue
            missing = [key for key in ("licence", "holds") if not _text(source.get(key))]
            if missing:
                warn(f"its source {source['name']} lacks: {', '.join(missing)}")
            kept = {key: source[key] for key in ("name", "url", "release", "accessed", "licence", "cite", "holds") if _text(source.get(key))}
            if "url" in kept and not kept["url"].startswith("https://"):
                # The contract sets no rule on the address; the page links out over https only.
                note(f"its source {source['name']} has an address that is not https, so it is named but not linked")
                del kept["url"]
            sources.append(kept)
        if not sources:
            lacking.append("sources")
        if lacking:
            warn(f"it lacks: {', '.join(lacking)}")
        if MACHINE.search(json.dumps(data)):
            warn("it holds a machine path or a host name")

        units = data.get("units") if isinstance(data.get("units"), dict) else {}
        missing = [unit for unit in self.unit_ids if unit not in units]
        if missing:
            warn(f"it has no entry for {len(missing)} of the inventory's {len(self.unit_ids)} units: {', '.join(missing)}")
        unknown = sorted(set(units) - set(self.unit_ids))
        if unknown:
            warn(f"it names units the inventory does not have: {', '.join(unknown)}")
        databases = {_key(source["name"]): source for source in sources}
        self.unlisted = {}  # a database no source lists -> where it is first named, and how often
        kept = {}
        for unit in self.unit_ids:
            if unit not in units:
                continue
            entry = units[unit] if isinstance(units[unit], dict) else {}
            finding = entry.get("finding")
            if finding not in self.findings:
                warn(f"{unit}: unknown finding {finding!r}")
                continue
            listed = entry.get("products") if isinstance(entry.get("products"), list) else []
            products = [product for product in (self.product(item, unit, databases, warn, note) for item in listed) if product]
            words = _text(entry.get("note"))
            if finding in ("found", "different family") and not listed:
                note(f"{unit} is '{finding}' but lists no product")
            if finding in ("none found", "nothing to look for") and listed:
                note(f"{unit} is '{finding}' but lists {len(listed)} products")
            if finding in ("different family", "none found") and not words:
                note(f"{unit} is '{finding}' without a note")
            kept[unit] = {"finding": finding, "note": words, "products": products}
        extra = []
        for item in data.get("extra") if isinstance(data.get("extra"), list) else []:
            product = self.product(item, "extra", databases, warn, note)
            if product and not product["why"]:
                note(f"extra: {product['label']} has no 'why'")
            if product:
                extra.append(product)
        for database, (where, count) in self.unlisted.items():
            warn(f"it names the database '{database}' ({count} times, first on {where}), which is neither uniprot, pdb nor one of its sources")
        return {
            "species": {"id": identifier, "label": label, **{key: species[key] for key in ("organism", "taxon", "plain") if species.get(key) is not None}},
            "made": data.get("made") if isinstance(data.get("made"), str) else None,
            "method": method,
            "sources": sources,
            "databases": databases,
            "not_copied": _text(data.get("not_copied")),
            "units": kept,
            "extra": extra,
        }

    def product(self, product, where, databases, warn, note):
        """One gene product, as far as it holds to the contract; None if it cannot be shown."""
        if not isinstance(product, dict):
            warn(f"{where}: a product is not an object")
            return None
        name, gene = _text(product.get("name")), _text(product.get("gene"))
        label = gene or name
        if not label:
            warn(f"{where}: a product has neither a name nor a gene")
            return None
        evidence = self.evidence.get(product.get("evidence"))
        if evidence is None:
            warn(f"{where}: unknown evidence {product.get('evidence')!r} on {label}")
            return None
        citation = product.get("citation")
        cited = isinstance(citation, dict) and _text(citation.get("text"))
        if evidence.get("cited") and not cited:
            warn(f"{where}: {label} is named in a publication, but has no citation with a text")
            return None
        if citation is not None and not cited:
            warn(f"{where}: the citation on {label} has no text")
        if any(isinstance(value, str) and re.match(r"https?://", value) for value in product.values()):
            warn(f"{where}: {label} holds a web address; the file names entries and the viewer builds the links")
        ids = []
        for entry in product.get("ids") if isinstance(product.get("ids"), list) else []:
            database, value = (entry.get("db"), entry.get("id")) if isinstance(entry, dict) else (None, None)
            if not _text(database) or value in (None, ""):
                warn(f"{where}: an id on {label} lacks its db or its id")
                continue
            value = str(value).strip()
            if "://" in value:
                warn(f"{where}: an id on {label} is a web address; the file names entries and the viewer builds the links")
                continue
            if _key(database) not in self.words["databases"] and _key(database) not in databases:
                first, count = self.unlisted.get(database, (f"{where}, {label}", 0))
                self.unlisted[database] = (first, count + 1)
                continue
            ids.append([_key(database), value])
        length = product.get("length")
        if length is not None and (not isinstance(length, int) or isinstance(length, bool) or length <= 0):
            note(f"{where}: the length of {label} is not a count of amino acids")
            length = None
        if not ids and not cited:
            note(f"{where}: {label} names no database entry and no paper")
        doi = _text(citation.get("doi")) if cited else None
        pmid = citation.get("pmid") if cited else None
        return {
            "label": label,
            "name": name,
            "gene": gene,
            "role": _text(product.get("role")),
            "ids": ids,
            "length": length,
            "evidence": evidence["id"],
            "evidence_note": _text(product.get("evidence_note")),
            "citation": {
                "text": cited,
                "doi": re.sub(r"^(https?://(dx\.)?doi\.org/|doi:\s*)", "", doi, flags=re.I) if doi else None,
                "pmid": str(pmid).strip() if str(pmid or "").strip().isdigit() else None,
            } if cited else None,
            "why": _text(product.get("why")),
        }

    # ------------------------------------------------------------ what the scene carries

    def item(self, product, atlas):
        """A gene product as the panel lists it: its evidence in the contract's words, and links built from its ids."""
        evidence = self.evidence[product["evidence"]]
        databases = atlas["databases"]
        # How one entry of a species' database is addressed, where that was checked (the overlay says when).
        entries = self.words.get("entries", {}).get(atlas["species"]["id"], {})
        lines, links = [], []
        if product["length"]:
            lines.append(f"{product['length']:,} amino acids")
        said = product["evidence_note"]
        if evidence.get("candidate"):
            # Found by signature or by similarity: a candidate, and the atlas says so.
            lines.append(f"Candidate, not an established counterpart: {said}" if said else "Candidate, not an established counterpart.")
        elif said:
            lines.append(said)
        for database, value in product["ids"]:
            template = entries.get(database) or self.links.get(self.words["databases"].get(database, database))
            if template:
                link = _fill(template, value)
                if database == "pdb":
                    link["text"] = f"PDB {value}"
                links.append(link)
                continue
            # A species database: the contract gives its address, not the address of one entry.
            # Without a checked pattern the entry is named in words, beside a link to the database.
            source = databases[database]
            lines.append(f"{source['name']}: {value}")
            if source.get("url") and not any(link["url"] == source["url"] for link in links):
                links.append({"text": source["name"], "url": source["url"]})
        citation = product["citation"]
        if citation:
            lines.append(citation["text"])
            if citation["doi"]:
                links.append(_fill(self.links["doi"], citation["doi"]))
            if citation["pmid"]:
                links.append(_fill(self.links["pubmed"], citation["pmid"]))
        # Under a gene's name: the protein's name and its role, unless one only repeats the other.
        name, gene, role = product["name"], product["gene"], product["role"]
        named = name if gene and name and name.lower() != gene.lower() else None
        part = role if role and not (name and role.lower() in name.lower()) else None
        return {
            "label": product["label"],
            "detail": ", ".join(text for text in (named, part) if text) or None,
            "tag": evidence["label"],
            "tag_title": evidence["description"],
            "lines": lines,
            "links": links,
        }

    def of_unit(self, unit_id):
        """What each species atlas says of one unit: {species id: {finding, note, items, keywords}}."""
        said = {}
        for atlas in self.atlases:
            entry = atlas["units"].get(unit_id)
            if entry is None:
                said[atlas["species"]["id"]] = {"finding": None, "note": None, "items": []}
                continue
            words = [text for product in entry["products"] for text in (product["gene"], product["name"], *(value for _, value in product["ids"])) if text]
            said[atlas["species"]["id"]] = {
                "finding": entry["finding"],
                "note": entry["note"],
                "items": [self.item(product, atlas) for product in entry["products"]],
                "keywords": " ".join(dict.fromkeys(words)),
            }
        return said

    def summary(self):
        """The scene's list of atlases: the reference first, then one for each species file."""
        snapshot = self.snapshot
        listed = [
            {
                **self.words["reference"],
                "reference": True,
                "made": snapshot["inventory"]["created"],
                "sources": snapshot["sources"],
                "not_copied": snapshot["not_copied"],
                "counts": {
                    "units": len(self.unit_ids),
                    "with_products": sum(1 for unit in snapshot["units"] if unit.get("products")),
                    "products": len(snapshot["products"]),
                },
            }
        ]
        for atlas in self.atlases:
            # A product that serves several units is counted once.
            distinct = {}
            for entry in atlas["units"].values():
                for product in entry["products"]:
                    distinct.setdefault(tuple(product["ids"][0]) if product["ids"] else ("", product["label"]), product)
            by_finding = Counter(entry["finding"] for entry in atlas["units"].values())
            by_evidence = Counter(product["evidence"] for product in distinct.values())
            listed.append(
                {
                    **atlas["species"],
                    "made": atlas["made"],
                    "method": atlas["method"],
                    "sources": atlas["sources"],
                    "not_copied": atlas["not_copied"],
                    "counts": {
                        "units": len(self.unit_ids),
                        "with_products": sum(1 for entry in atlas["units"].values() if entry["products"]),
                        "products": len(distinct),
                        "candidates": sum(count for kind, count in by_evidence.items() if self.evidence[kind].get("candidate")),
                    },
                    "findings": [{"id": word["id"], "count": by_finding[word["id"]]} for word in self.words["findings"]],
                    "evidence": [{"id": word["id"], "count": by_evidence[word["id"]]} for word in self.words["evidence"]],
                    "extra": [{**self.item(product, atlas), "note": product["why"]} for product in atlas["extra"]],
                }
            )
        return listed


RELATION_KINDS = [
    {
        "id": "modelled_by",
        "label": "has its law in",
        "directed": True,
        "origin": "inventory",
        "description": "The engine law that acts on this unit is in this part of the engine (from the law inventory, checked against the code).",
    },
    {
        "id": "shown_as",
        "label": "is drawn in the cell view as",
        "directed": True,
        "origin": "curated",
        "description": "The part of the cell view that stands for this unit.",
    },
]

LENS_GROUPS = [
    {"id": "biology", "label": "Cell and scales", "lens": "cell", "placement": "none"},
    {"id": GROUP, "label": "Protein atlas", "lens": "proteins", "placement": "none"},
]
