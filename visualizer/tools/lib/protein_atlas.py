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
"""

from __future__ import annotations

import re
from collections import Counter

from .static_eval import Unresolved, plain

IDENTIFIER = re.compile(r"\b[A-Za-z][A-Za-z0-9_]*@\d+")
PDB = re.compile(r"PDB (\d[A-Z0-9]{3})")
GROUP = "proteins"


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
    def __init__(self, build, snapshot, overlay):
        self.build = build
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
            listing = self.build.git("grep", "-o", "-E", "[A-Za-z][A-Za-z0-9_]*@[0-9]+", rev, "--", "src/cells")
            found = {}
            for line in listing.splitlines():
                _, path, name = line.split(":", 2)
                found.setdefault(name, set()).add(path)
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
        return {"added": len(added), "removed": len(set(before) - set(now)), "where": [list(item) for item in where]}

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

        sections = [{"title": "Engine laws", "items": [self.law_item(law) for law in laws]}]
        if unit.get("products"):
            sections.append({"title": "Candidate products", "items": [self.product_item(product) for product in unit["products"]]})
        cited = [pdb for source in unit["assembly"].get("sources", []) for pdb in PDB.findall(source)]
        shown = [structures[pdb] for pdb in dict.fromkeys(cited) if pdb in structures]
        if shown:
            sections.append({"title": "Reference structures", "items": [self.structure_item(item) for item in shown]})

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
        }


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
