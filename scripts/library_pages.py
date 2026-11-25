"""The library of human-readable pages: one per registered law, kind and operator, and per model
with declared structure (docs/LAW_DOCUMENTATION_DESIGN.md; D203).

    python scripts/library_pages.py --new SECTION ID   write a page from the template, its generated
                                                       blocks filled in (SECTION: law, kind,
                                                       operator or model)
    python scripts/library_pages.py --write            render every generated block again: each
                                                       page's, the index and the glossary's
                                                       "Used by" lines
    python scripts/library_pages.py --check            the five claims below; exit 1 on a finding

Run with the engine on the path (PYTHONPATH=src JAX_ENABLE_X64=1 JAX_PLATFORMS=cpu), from any
directory: the library is this checkout's docs/library/.

**One source for each fact.** What the code declares is rendered from the declarations manifest
(cells.declarations@3, registry/declarations.py, written fresh from the active registries) into
blocks between `<!-- generated: NAME -->` and `<!-- /generated -->`. The words are written by
hand on the page, never in a .py file: a docstring's wording fix would change a source hash and
strand checkpoints (D203). Code and test paths appear only in generated blocks, so a file move
needs `--write` and no hand edit. Links to other pages are rendered from the manifest's `doc`,
which stays null until every page is written (§3.4), so a generated link never points at a page
that does not exist.

**The five claims** (`--check`; tests/unit/test_library_pages.py makes each with a planted error):
- C1: every page names a registered piece or a model with declared structure, at its path; once
  the pages are complete (declarations.PAGES_COMPLETE), every one of them has its page;
- C2: every generated block, the index and the glossary's "Used by" lines equal a fresh render,
  compared as text;
- C3: the plain layers are present and within their limits (one sentence of at most 30 words,
  with no symbols; "In plain words" of at most 150; a title that carries the ID; the headings in
  order; "The mathematics" holds an equation or a line "No equations:" with its reason);
- C4: every relative link and anchor resolves, glossary terms included (GitHub's heading anchors);
- C5: the format page's key tables equal the manifest's key sets, in both directions, and the
  page names the format.

It sits in scripts/, so editing it changes no source hash. It moves into the conformance kit when
an outside module needs it (§6).
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LIBRARY = "docs/library"
FORMAT_PAGE = f"{LIBRARY}/DECLARATIONS_FORMAT.md"
GLOSSARY = f"{LIBRARY}/GLOSSARY.md"
TEMPLATE = f"{LIBRARY}/TEMPLATE.md"
INDEX = f"{LIBRARY}/README.md"
OWN_FILES = {FORMAT_PAGE, GLOSSARY, TEMPLATE, INDEX}
PIECES = ("law", "kind", "operator", "model")
HEADINGS = (
    "In plain words",
    "Seen from each field",
    "At a glance",
    "What it reads and changes",
    "The mathematics",
    "Sources",
    "How it is checked",
    "Status",
    "Links",
)
OPTIONAL = {"Seen from each field"}
BLOCKS = {  # Each generated block, under its heading.
    "At a glance": "at-a-glance",
    "What it reads and changes": "touches",
    "The mathematics": "bounds",
    "Sources": "provenance",
    "How it is checked": "tests",
    "Status": "status",
    "Links": "links",
}
SENTENCE = "**In one sentence:**"
SENTENCE_WORDS = 30
PLAIN_WORDS = 150
SYMBOLS = set("$`=\\^<>")
MARKER = re.compile(r"<!-- generated: (?P<name>[^>]+?) -->\n(?P<body>.*?)<!-- /generated -->", re.S)
LINK = re.compile(r"(?<!!)\[(?P<text>[^\]]*)\]\((?P<target>[^)\s]+)\)")
PROVENANCE_WORDS = {
    "parity": "moved from an older family; moving is not calibrating",
    "cited": "taken from a cited source",
    "calibrated": "fitted to data by a declared method",
}
# The format page's section for each interface's own fields (the anchors pages link).
INTERFACE_SECTIONS = {
    "cells.channel_law@1": "channel-laws",
    "cells.cycle_law@1": "cycle-laws",
    "cells.route_law@1": "route-laws",
    "cells.binding_law@1": "binding-laws",
    "cells.junction_law@1": "junction-laws",
    "cells.kind@1": "kinds",
    "cells.operator@1": "operators",
}
MODEL_WORDS = {
    "inner": "The inner model: it hosts its own laws and its kinds",
    "composite": "The composite: an inner model and any ordered list of operators",
    "composition": "A composition: the composite with a fixed operator list",
    "family": "A model family of its own",
}
PART_WORDS = {"event": "an event map", "split": "a split part", "process": "an in-step process"}


def declarations():
    from cells.registry import declarations as module

    return module


# ------------------------------------------------------------------ the library on disk


def load(root=ROOT):
    """{repository path: text} of every Markdown file of the library under `root`."""
    base = Path(root) / LIBRARY
    return {
        path.relative_to(root).as_posix(): path.read_text()
        for path in sorted(base.rglob("*.md"))
        if path.is_file()
    }


def pages(files):
    """The piece pages among `files`: every Markdown file of a namespace's section folder."""
    return {path: text for path, text in files.items() if path not in OWN_FILES}


def entries(doc):
    """{(piece, namespaced ID): entry} of the manifest's pieces and models."""
    out = {(e["piece"], e["id"]): e for e in doc["pieces"]}
    out.update({("model", m["id"]): m for m in doc["models"]})
    return out


def paged(doc):
    """{page path: (piece, ID)} of every piece and model that gets a page: an in-tree piece, and a
    model with declared structure (a family with no rows gets none)."""
    page_path = declarations().page_path
    out = {}
    for entry in doc["pieces"]:
        if entry["module_path"] is not None:
            out[page_path(entry["piece"], entry["id"])] = (entry["piece"], entry["id"])
    for model in doc["models"]:
        if model["type"] != "family" or model["rows"]:
            out[page_path("model", model["id"])] = ("model", model["id"])
    return out


def relative(page, target):
    """The relative link from a page to a repository path."""
    return Path(os.path.relpath(ROOT / target, (ROOT / page).parent)).as_posix()


# ------------------------------------------------------------------ rendering


def _c(value):
    return f"`{value}`"


def _number(value):
    return repr(value) if isinstance(value, float) else str(value)


def _list(items, empty="none"):
    items = list(items)
    if not items:
        return empty
    if len(items) == 1:
        return items[0]
    return ", ".join(items[:-1]) + " and " + items[-1]


class Render:
    """The generated blocks of one page, from one manifest."""

    def __init__(self, doc):
        self.doc = doc
        self.entries = entries(doc)
        self.unextracted = {(p["interface"], p["key"]) for p in doc["not_extracted"]}

    def ref(self, page, identifier, piece=None):
        """An ID in backticks, linked to its page where the manifest gives one (`doc`)."""
        candidates = [piece] if piece else PIECES
        for p in candidates:
            entry = self.entries.get((p, identifier))
            if entry is not None and entry["doc"]:
                return f"[{_c(identifier)}]({relative(page, entry['doc'])})"
        return _c(identifier)

    def fields_link(self, page, interface):
        anchor = INTERFACE_SECTIONS.get(interface, "family-interfaces")
        return f"[its fields]({relative(page, FORMAT_PAGE)}#{anchor})"

    def missing(self, entry, key):
        return (entry["interface"], key) in self.unextracted

    def file_link(self, page, path):
        return f"[{_c(path)}]({relative(page, path)})"

    # -------------------------------------------------------------- the blocks

    def blocks(self, page, piece, identifier):
        entry = self.entries[(piece, identifier)]
        if piece == "model":
            return self.model_blocks(page, entry)
        return {
            "at-a-glance": self.at_a_glance(page, entry),
            "touches": self.touches(page, entry),
            "bounds": self.bounds(entry),
            "provenance": self.provenance(entry),
            "tests": self.tests(page, entry),
            "status": self.status(entry),
            "links": self.links(page, entry),
        }

    def runs_in(self, page, entry):
        host = self.ref(page, entry["host"])
        text = f"{host}, its host"
        if entry["declared_host"] and entry["declared_host"] != entry["host"]:
            text += f", which definitions write {_c(entry['declared_host'])}"
        if not entry["models"]:  # Its host is no active model.
            return f"{text}. No model's definitions can declare it"
        if entry["host"] not in entry["models"]:
            family = self.ref(page, entry["family"], "model")
            text += f", in {family}"
        models = _list([self.ref(page, m, "model") for m in entry["models"]])
        return f"{text}. Definitions of {models} can declare it"

    def at_a_glance(self, page, entry):
        piece, fields = entry["piece"], entry["fields"]
        rows = []
        kind_word = {"law": "Law", "kind": "Kind", "operator": "Operator"}[piece]
        rows.append(
            (
                "Piece",
                f"{kind_word}, interface {_c(entry['interface'])} "
                f"({self.fields_link(page, entry['interface'])})",
            )
        )
        rows.append(("ID", f"{_c(entry['id'])}; definitions write {_c(entry['declared_id'])}"))
        if piece == "kind":
            rows.append(
                (
                    "Runs in",
                    self.runs_in(page, entry) + f", under the key {_c(fields['model_key'])}",
                )
            )
            laws = [self.ref(page, law, "law") for law in entry["laws"]]
            rows.append(("Laws it hosts", _list(laws, "None")))
        elif piece == "operator" and entry["interface"] == "cells.operator@1":
            rows.append(("Runs in", self.runs_in(page, entry)))
            rows.append(("Where it acts in the step", self.parts(fields)))
            rows.append(("Needs", self.needs(page, entry["requires"])))
        else:
            rows.append(("Runs in", self.runs_in(page, entry)))
            if "code" in fields:
                rows.append(("Registry code", str(fields["code"])))
            if "basis" in fields:
                rows.append(("Its basis, as declared", fields["basis"]))
            if "hosts" in fields:
                rows.append(("Its routes sit on", _list([_c(h) for h in fields["hosts"]])))
        rows.append(("Provenance", self.provenance_tag(entry)))
        lines = ["| | |", "| --- | --- |", *(f"| {k} | {v} |" for k, v in rows)]
        return "\n".join(lines)

    def parts(self, fields):
        if fields["declaration_only"]:
            text = "A declaration only: it contributes no part to the step"
        else:
            words = [PART_WORDS[p] for p in fields["parts"]] or ["no part of its own"]
            text = _list(words)
            text = text[0].upper() + text[1:]
        if fields["step_method"]:
            text += f", by {_c(fields['step_method'])}"
        if fields["experiment_keys"]:
            text += "; scheduled by " + _list([_c(k) for k in fields["experiment_keys"]])
        return text

    def needs(self, page, requires):
        q = declarations().qualified
        parts = []
        if requires["laws"]:
            laws = [self.ref(page, q(law), "operator") for law in requires["laws"]]
            parts.append(_list(laws) + " before it in the operator list")
        if requires["kinds"]:
            kinds = [self.ref(page, q(kind), "kind") for kind in requires["kinds"]]
            parts.append("the kinds " + _list(kinds))
        return _list(parts) if parts else "No law or kind"

    def provenance_tag(self, entry):
        if entry["provenance"] is None:
            if self.missing(entry, "provenance"):
                return f"Not yet extracted: {self.contract(entry)} has no provenance field yet"
            return "Not stated"
        tag = entry["provenance"]["tag"]
        return f"{_c(tag)}: {PROVENANCE_WORDS.get(tag, tag)}"

    def contract(self, entry):
        if entry["interface"] == "cells.kind@1":
            return "the kind contract"
        if entry["interface"] == "cells.operator@1":
            return "the composite's operator contract"
        return f"the interface {_c(entry['interface'])}"

    def unit(self, entry, name):
        units = entry["units"] or {}
        if name in units and units[name] is not None:
            return units[name]
        return "Not stated"

    def sign(self, entry, name):
        sign = (entry["signs"] or {}).get(name)
        if sign is None:
            return "Not stated"
        if isinstance(sign, str):
            return sign
        if "from" in sign:
            return f'From {sign["from"]} to {sign["to"]}: "{sign["says"]}"'
        return f'{sign["plus"]} less {sign["minus"]}: "{sign["says"]}"'

    def touches(self, page, entry):
        piece = entry["piece"]
        if piece == "law":
            return self.law_touches(entry)
        if piece == "kind":
            return self.kind_touches(entry)
        if entry["interface"] == "cells.operator@1":
            return self.operator_touches(page, entry)
        return self.own_fields(entry)

    def law_touches(self, entry):
        if entry["reads"] is None:
            return self.own_fields(entry)
        rows = ["| Role | What | Unit | Which way is positive |", "| --- | --- | --- | --- |"]
        reads = [f"{_c(r['name'])}, {r['mode']} at each {r['stage']} stage" for r in entry["reads"]]
        rows.append(f"| Reads | {_list(reads, 'None declared')} | | |")
        changes = entry["changes"]
        if not changes:
            rows.append("| Changes | None declared | | |")
        for change in changes:
            if "species" in change:
                what = (
                    f"{_c(change['species'])}: valence {change['valence']}, relative permeability "
                    f"{_number(change['relative_permeability'])}"
                )
                rows.append(f"| Changes | {what} | Not stated | Not stated |")
            else:
                count = change["per_cycle"]
                count = _c(count) if isinstance(count, str) else str(count)
                what = f"{_c(change['role'])}: {count} per cycle"
                rows.append(f"| Changes | {what} | | {self.sign(entry, 'moves')} |")
        gates = entry["fields"].get("gates")
        if gates:
            rows.append(f"| Its gates, kept by the host | {_list([_c(g) for g in gates])} | | |")
        lines = rows + [""]
        lines.append(self.energy_line(entry))
        return "\n".join(lines)

    def energy_line(self, entry):
        if not self.missing(entry, "energy"):
            return "Energy role: not stated."
        template = "the law template" if entry["piece"] == "law" else "the operator template"
        return f"Energy role: not yet extracted; {template} has no energy role yet."

    def kind_touches(self, entry):
        fields = entry["fields"]
        kinds, layers = fields["record_kinds"], fields["record_layers"]
        rows = [
            "| Field | Role | Axes | Unit | Record | Which way is positive |",
            "| --- | --- | --- | --- | --- | --- |",
        ]
        for name, axes in entry["owns"].items():
            rows.append(
                f"| {_c(name)} | Owns | {', '.join(axes)} | {self.unit(entry, name)} | "
                f"{kinds.get(name, '')} | {self.sign(entry, name)} |"
            )
        for name in entry["provides"]:
            rows.append(
                f"| {_c(name)} | Provides | | {self.unit(entry, name)} | {kinds.get(name, '')} | "
                f"{self.sign(entry, name)} |"
            )
        for name in entry["controls"]:
            rows.append(f"| {_c(name)} | Controls | | {self.unit(entry, name)} | | |")
        notes = []
        for key, word in (("ledgers", "Ledgers"), ("energy", "Energy roles")):
            notes.append(
                f"{word}: not yet extracted."
                if self.missing(entry, key)
                else f"{word}: not stated."
            )
        on = sorted(set(layers.values()))
        if on:
            notes.append(
                f"Its records are on the {_list([_c(layer) for layer in on])} "
                + ("layers." if len(on) > 1 else "layer.")
            )
        fold = [
            "<details><summary>For developers</summary>",
            "",
            f"Hooks: {_list([_c(h) for h in fields['hooks']])}. Layout fields: "
            f"{_list([_c(f) for f in fields['layout_fields']])}. Experiment keys: "
            f"{_list([_c(k) for k in fields['experiment_keys']])}.",
            "",
            "</details>",
        ]
        return "\n".join([*rows, "", " ".join(notes), "", *fold])

    def operator_touches(self, page, entry):
        rows = [
            "| Field | Role | Axes | Unit | Which way is positive |",
            "| --- | --- | --- | --- | --- |",
        ]
        for read in entry["reads"]:
            role = f"Reads ({read['mode']}, at the {read['stage']} stage)"
            rows.append(f"| {_c(read['name'])} | {role} | | {self.unit(entry, read['name'])} | |")
        energy = entry["energy"] or {}
        for name, axes in entry["owns"].items():
            role = "Owns"
            if name in energy.get("heat", ()):
                role += "; heat"
            if name in energy.get("work", ()):
                role += "; work"
            rows.append(
                f"| {_c(name)} | {role} | {', '.join(axes)} | {self.unit(entry, name)} | "
                f"{self.sign(entry, name)} |"
            )
        for name in entry["provides"]:
            rows.append(
                f"| {_c(name)} | Provides | | {self.unit(entry, name)} | {self.sign(entry, name)} |"
            )
        for name in entry["controls"]:
            rows.append(f"| {_c(name)} | Controls | | {self.unit(entry, name)} | |")
        writes = entry["writes"] or {}
        written = [
            f"{_c(field)}, booked in {_list([_c(a) for a in booked])}"
            for field, booked in writes.items()
        ]
        notes = [
            f"Writes into other pieces' fields: {_list(written, 'none')}.",
            f"Ledgers: {_list([_c(ledger) for ledger in entry['ledgers']], 'none')}.",
        ]
        records = entry["fields"]["record_kinds"]
        notes.append(
            "Records: "
            + _list([f"{_c(k)} ({v})" for k, v in records.items()], "none declared")
            + "."
        )
        return "\n".join([*rows, "", " ".join(notes)])

    def own_fields(self, entry):
        units = entry["units"] or {}
        rows = ["| Its interface's own field | Value | Unit |", "| --- | --- | --- |"]
        for name, value in entry["fields"].items():
            shown = _c(value if isinstance(value, str) else json.dumps(value, ensure_ascii=False))
            rows.append(f"| {_c(name)} | {shown} | {units.get(name) or ''} |")
        if len(rows) == 2:
            rows.append("| None declared | | |")
        return "\n".join([*rows, "", self.energy_line(entry)])

    def bounds(self, entry):
        fields = entry["fields"]
        piece = entry["piece"]
        if piece == "kind":
            return "None declared by the kind; each law it hosts declares its own."
        rows = []
        if "voltage_domain_V" in fields:
            low, high = fields["voltage_domain_V"]
            rows.append(
                (
                    "Voltage domain",
                    f"{_number(low)} to {_number(high)}",
                    self.unit(entry, "voltage_domain_V"),
                )
            )
        if fields.get("rk4_step_s") is not None:
            rows.append(
                (
                    "Reference RK4 step",
                    _number(fields["rk4_step_s"]),
                    self.unit(entry, "rk4_step_s"),
                )
            )
        if "max_abs_voltage_V" in fields:
            rows.append(
                (
                    "Largest voltage across a junction",
                    _number(fields["max_abs_voltage_V"]),
                    self.unit(entry, "max_abs_voltage_V"),
                )
            )
        if fields.get("stage_term"):
            rows.append(("Stage term", _c(fields["stage_term"]), ""))
        if fields.get("material_term"):
            rows.append(("Material term", _c(fields["material_term"]), ""))
        if "fuel_kinds" in fields:
            rows.append(("Fuel kinds", _list([_c(f) for f in fields["fuel_kinds"]]), ""))
        kernels = entry["kernels"] or {}
        if "domain_valid" in kernels:
            rows.append(("Domain check", _c(kernels["domain_valid"]["function"]), ""))
        if not rows:
            return "None declared."
        lines = ["| Declared | Value | Unit |", "| --- | --- | --- |"]
        lines += [f"| {a} | {b} | {c} |" for a, b, c in rows]
        return "\n".join(lines)

    def provenance(self, entry):
        provenance = entry["provenance"]
        if provenance is None:
            if self.missing(entry, "provenance"):
                contract = self.contract(entry)
                return f"Provenance: not yet extracted; {contract} has no provenance field yet."
            return "Provenance: not stated."
        tag = provenance["tag"]
        lines = [f"Provenance: {_c(tag)} ({PROVENANCE_WORDS.get(tag, tag)})."]
        citation = provenance["citation"]
        if citation is None:
            lines[0] += " No citation is declared."
            if provenance["source"] is not None:
                lines += ["", f"Source, as declared: {provenance['source']}"]
            return "\n".join(lines)
        departures = citation["departures"]
        lines += [
            "",
            f"- **Source, as declared:** {citation['source']}",
            f"- **Place:** {citation['place']}",
            f"- **Licence of the numbers:** {citation['licence']}",
            f"- **Departures:** {'; '.join(departures) if departures else 'none declared'}",
        ]
        works = citation["works"]
        if not works:
            lines.append("- **Works, as data:** none declared")
        for work in works:
            where = f"doi:{work['doi']}" if work["doi"] else work["url"]
            lines.append(
                f"- **Work:** {_list(work['authors'])} ({work['year']}). {work['title']}. {where}"
            )
        return "\n".join(lines)

    def tests(self, page, entry):
        if entry["test"] is None:
            if self.missing(entry, "test"):
                contract = self.contract(entry)
                return f"Declared test: not yet extracted; {contract} has no test field yet."
            return "Declared test: not stated."
        path, _, name = entry["test"].partition("::")
        target = self.file_link(page, path) if (ROOT / path).is_file() else _c(path)
        return f"Declared test: {target}" + (f", {_c(name)}." if name else ".")

    def status(self, entry):
        if entry.get("status") is None:
            return "Not stated: no record states a level for this piece."
        return f"{entry['status']}, as {entry['status_source']} states it."

    def links(self, page, entry):
        lines = []
        where = (
            self.file_link(page, entry["module_path"])
            if entry["module_path"]
            else "outside this repository"
        )
        if entry["piece"] == "operator" and entry["interface"] == "cells.operator@1":
            lines.append(
                f"- Declared in {where}, class {_c(entry['fields']['class_name'])} "
                f"({_c(entry['module'])})."
            )
        else:
            lines.append(f"- Declared in {where} ({_c(entry['module'])}).")
        kernels = entry["kernels"] or {}
        if kernels:
            parts = []
            for name, record in kernels.items():
                text = f"{_c(name)}, {_c(record['function'])}"
                if record["module_path"] and record["module_path"] != entry["module_path"]:
                    text += f" in {self.file_link(page, record['module_path'])}"
                parts.append(text)
            lines.append("- Kernels: " + "; ".join(parts) + ".")
        if entry["piece"] == "kind" and entry["laws"]:
            lines.append(
                "- Hosts " + _list([self.ref(page, law, "law") for law in entry["laws"]]) + "."
            )
        lines.append(f"- Runs in {self.ref(page, entry['host'])}.")
        lines.append(self.manifest_line(page, entry["piece"], entry["id"]))
        lines.append(f"- In the Laws library: `select=laws:{entry['id']}`.")
        return "\n".join(lines)

    def manifest_line(self, page, piece, identifier):
        return (
            f"- Manifest entry: ({piece}, {_c(identifier)}), from `python -m cells declarations "
            f"--out FILE` ([the format]({relative(page, FORMAT_PAGE)}))."
        )

    def model_blocks(self, page, model):
        rows = [
            "| | |",
            "| --- | --- |",
            f"| Model | {MODEL_WORDS[model['type']]} |",
            f"| ID | {_c(model['id'])}; definitions write {_c(model['declared_id'])} |",
            f"| Its definitions are parsed by | {_c(model['module'])} |",
        ]
        if model["next_code"] is not None:
            rows.append(f"| Next free channel code | {model['next_code']} |")
        table = ["| Role | Piece | Slot |", "| --- | --- | --- |"]
        for row in model["rows"]:
            slot = row["slot"]
            slot = (
                ", ".join(f"{k} {_c(v) if isinstance(v, str) else v}" for k, v in slot.items())
                if slot
                else ""
            )
            table.append(f"| {row['role']} | {self.ref(page, row['id'], row['piece'])} | {slot} |")
        if len(table) == 2:
            table.append("| None declared | | |")
        if model["type"] == "composite":
            table += ["", "Any ordered list of these operators is a definition's composition."]
        links = [
            f"- Parsed by {self.file_link(page, model['module_path'])} ({_c(model['module'])}).",
            self.manifest_line(page, "model", model["id"]),
            f"- In the Laws library: `select=laws:{model['id']}`.",
        ]
        return {
            "at-a-glance": "\n".join(rows),
            "touches": "\n".join(table),
            "bounds": "None: a model holds no mathematics of its own; its pieces do.",
            "provenance": "None declared: a model's sources are its pieces'.",
            "tests": "None declared.",
            "status": "Not stated: no record states a level for this model.",
            "links": "\n".join(links),
        }


# ------------------------------------------------------------------ pages, index and glossary


def block_body(content):
    """A generated block's text between its markers: a blank line inside each marker."""
    return "\n" + content.rstrip("\n") + "\n\n"


def rewrite_blocks(text, blocks):
    """`text` with each generated block's body replaced by its fresh render; names it has no
    render for are kept."""

    def replace(match):
        name = match.group("name")
        if name not in blocks:
            return match.group(0)
        return f"<!-- generated: {name} -->\n{block_body(blocks[name])}<!-- /generated -->"

    return MARKER.sub(replace, text)


def page_identity(path):
    """(piece, namespaced ID) a page's path names, or None."""
    parts = Path(path).relative_to(LIBRARY).parts
    sections = {v: k for k, v in declarations().SECTIONS.items()}
    if len(parts) != 3 or parts[1] not in sections or not parts[2].endswith(".md"):
        return None
    return sections[parts[1]], f"{parts[0]}.{parts[2][: -len('.md')]}"


def sentence(text):
    for line in text.splitlines():
        if line.startswith(SENTENCE):
            return line[len(SENTENCE) :].strip()
    return None


def sections(text):
    """{heading: its text} of a page's level-2 sections, outside fenced code."""
    out, current, fenced = {}, None, False
    for line in text.splitlines():
        if line.startswith("```"):
            fenced = not fenced
        if not fenced and line.startswith("## "):
            current = line[3:].strip()
            out[current] = []
        elif current is not None:
            out[current].append(line)
    return {k: "\n".join(v).strip() for k, v in out.items()}


def render_index(doc, files):
    """The library's index (README.md): every page by section and interface, with its one sentence
    and its status. It lists written pages only, so registering a piece changes it only once the
    piece's page is written."""
    render = Render(doc)
    lines = [
        "# The library: plain-language pages for the engine's pieces",
        "",
        "<!-- Generated by scripts/library_pages.py --write from the declarations manifest and the",
        "pages' own sentences. Do not edit by hand. -->",
        "",
        "One page for each registered law, kind and operator, and for each model with declared",
        "structure, each opening in plain words",
        "([the design](../LAW_DOCUMENTATION_DESIGN.md); D203). The [template](TEMPLATE.md) says",
        "how to write one, the [glossary](GLOSSARY.md) defines the words, and",
        "[the manifest's format](DECLARATIONS_FORMAT.md) says what each generated fact means.",
    ]
    written = {page_identity(p): p for p in pages(files) if page_identity(p)}
    titles = {"law": "Laws", "kind": "Kinds", "operator": "Operators", "model": "Models"}
    for piece in PIECES:
        found = sorted(
            (key, path)
            for key, path in written.items()
            if key[0] == piece and key in render.entries
        )
        lines += ["", f"## {titles[piece]}", ""]
        if not found:
            lines.append("No page yet.")
            continue
        groups = {}
        for (p, identifier), path in found:
            entry = render.entries[(p, identifier)]
            group = entry["type"] if piece == "model" else entry["interface"]
            groups.setdefault(group, []).append((identifier, path, entry))
        for group, items in sorted(groups.items()):
            lines += [
                f"### {_c(group)}",
                "",
                "| Page | In one sentence | Status |",
                "| --- | --- | --- |",
            ]
            for identifier, path, entry in items:
                said = sentence(files[path]) or "Not written yet."
                status = entry.get("status") or "Not stated"
                lines.append(f"| [{_c(identifier)}]({relative(INDEX, path)}) | {said} | {status} |")
            lines.append("")
        if lines[-1] == "":
            lines.pop()
    return "\n".join(lines) + "\n"


GLOSSARY_TERM = re.compile(r"^### (?P<term>.+)$", re.M)


def used_by(doc, files):
    """{glossary anchor: [page path, ...]} of the pages that link each term."""
    out = {}
    for path, text in pages(files).items():
        for match in LINK.finditer(text):
            target = match.group("target")
            file, _, anchor = target.partition("#")
            if (
                anchor
                and file
                and Path(os.path.normpath(Path(path).parent / file)).as_posix() == GLOSSARY
            ):
                out.setdefault(anchor, set()).add(path)
    return {k: sorted(v) for k, v in out.items()}


def terms(text):
    """The anchors of the glossary's terms: its level-3 headings."""
    return [slug(m.group("term")) for m in GLOSSARY_TERM.finditer(text)]


def glossary_blocks(doc, files):
    """{block name: content} of the glossary's generated "Used by" lines, one per term."""
    users = used_by(doc, files)
    out = {}
    for anchor in terms(files[GLOSSARY]):
        name = f"used-by {anchor}"
        found = users.get(anchor, [])
        links = [f"[{_c(page_identity(p)[1])}]({relative(GLOSSARY, p)})" for p in found]
        out[name] = "- **Used by:** " + (_list(links) if links else "no page yet") + "."
    return out


# ------------------------------------------------------------------ anchors and links


def slug(heading):
    """A heading's anchor as GitHub writes it: code and link markup dropped, lowercased,
    punctuation other than hyphens and underscores removed, spaces made hyphens."""
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", heading.strip())
    text = text.replace("`", "").lower()
    text = re.sub(r"[^\w\- ]", "", text)
    return text.replace(" ", "-")


def anchors(text):
    """The anchors of a Markdown file's headings, duplicates numbered as GitHub numbers them."""
    out, seen, fenced = [], {}, False
    for line in text.splitlines():
        if line.startswith("```"):
            fenced = not fenced
            continue
        match = re.match(r"^#{1,6} (.+)$", line)
        if fenced or not match:
            continue
        base = slug(match.group(1))
        count = seen.get(base, 0)
        out.append(base if count == 0 else f"{base}-{count}")
        seen[base] = count + 1
    return out


# ------------------------------------------------------------------ the five claims


def check_pages(doc, files, complete=None):
    """C1: every page names a registered piece or a model with declared structure; once complete,
    every one of them has its page."""
    if complete is None:
        complete = declarations().PAGES_COMPLETE
    expected = paged(doc)
    found = []
    for path in sorted(pages(files)):
        if path not in expected:
            found.append(f"C1 {path}: names no registered piece or model with declared structure")
    if complete:
        found += [
            f"C1 {path}: {p} {i} has no page"
            for path, (p, i) in sorted(expected.items())
            if path not in files
        ]
    return found


def check_blocks(doc, files):
    """C2: every generated block equals a fresh render, as text; so do the index and the
    glossary's "Used by" lines."""
    render = Render(doc)
    found = []
    for path, text in sorted(pages(files).items()):
        identity = page_identity(path)
        if identity is None or identity not in render.entries:
            continue  # C1's finding.
        blocks = render.blocks(path, *identity)
        names = [m.group("name") for m in MARKER.finditer(text)]
        if sorted(names) != sorted(blocks):
            found.append(f"C2 {path}: its generated blocks are {', '.join(sorted(blocks))}")
            continue
        for match in MARKER.finditer(text):
            if match.group("body") != block_body(blocks[match.group("name")]):
                found.append(f"C2 {path}: block {match.group('name')} is stale; run --write")
    if files.get(INDEX) != render_index(doc, files):
        found.append(f"C2 {INDEX}: the index is stale; run --write")
    if GLOSSARY in files:
        expected = glossary_blocks(doc, files)
        text = files[GLOSSARY]
        names = {m.group("name") for m in MARKER.finditer(text)}
        if names != set(expected):
            found.append(f"C2 {GLOSSARY}: each term has one Used-by block; run --write")
        for match in MARKER.finditer(text):
            name = match.group("name")
            if name in expected and match.group("body") != block_body(expected[name]):
                found.append(f"C2 {GLOSSARY}: {name} is stale; run --write")
    return found


def _words(text):
    text = LINK.sub(lambda m: m.group("text"), text)
    return len(re.findall(r"\S+", text))


def check_layers(doc, files):
    """C3: the title carries the ID; the one sentence and the plain words are written and within
    their limits; the headings come in order; the mathematics holds an equation or says why
    not."""
    found = []
    for path, text in sorted(pages(files).items()):
        identity = page_identity(path)
        if identity is None:
            continue
        lines = text.splitlines()
        if not (lines and lines[0].startswith("# ") and f"(`{identity[1]}`)" in lines[0]):
            found.append(f"C3 {path}: the title is '# <plain name> (`{identity[1]}`)'")
        if "<Plain name>" in text:
            found.append(f"C3 {path}: the plain name is not written")
        said = sentence(text)
        if not said or said.startswith("<"):
            found.append(f"C3 {path}: the one sentence is not written")
        else:
            if _words(said) > SENTENCE_WORDS:
                found.append(
                    f"C3 {path}: the one sentence has {_words(said)} words "
                    f"(at most {SENTENCE_WORDS})"
                )
            if set(said) & SYMBOLS:
                found.append(
                    f"C3 {path}: the one sentence holds a symbol "
                    f"({''.join(sorted(set(said) & SYMBOLS))})"
                )
        parts = sections(text)
        order = [h for h in parts]
        expected = [h for h in HEADINGS if h in parts or h not in OPTIONAL]
        if order != expected:
            found.append(f"C3 {path}: its headings are {', '.join(expected)}, in that order")
        plain = parts.get("In plain words", "")
        if not plain or plain.startswith("<"):
            found.append(f"C3 {path}: 'In plain words' is not written")
        elif _words(plain) > PLAIN_WORDS:
            found.append(
                f"C3 {path}: 'In plain words' has {_words(plain)} words (at most {PLAIN_WORDS})"
            )
        maths = MARKER.sub("", parts.get("The mathematics", ""))
        if "$" not in maths and not re.search(r"^No equations: \S", maths, re.M):
            found.append(
                f"C3 {path}: 'The mathematics' holds an equation or a line 'No equations:' "
                "with its reason"
            )
        hand = MARKER.sub("", text)
        for line in hand.splitlines():
            if re.fullmatch(r"<[A-Za-z][^>]*>", line.strip()) and not line.strip().startswith("</"):
                found.append(f"C3 {path}: a placeholder is left: {line.strip()[:60]}")
    return found


def check_links(files, root=ROOT):
    """C4: every relative link of the library's files resolves to a file or folder of the
    repository, and every anchor to a heading of its Markdown file."""
    found = []
    for path, text in sorted(files.items()):
        for match in LINK.finditer(_unfenced_links(text)):
            target = match.group("target")
            if re.match(r"^[a-z]+:", target):
                continue
            file, _, anchor = target.partition("#")
            resolved = Path(os.path.normpath(Path(path).parent / file)).as_posix() if file else path
            if resolved in files:
                content = files[resolved]
            elif (Path(root) / resolved).exists():
                content = (Path(root) / resolved).read_text() if resolved.endswith(".md") else None
            else:
                found.append(f"C4 {path}: {target} names no file")
                continue
            if anchor and (content is None or anchor not in anchors(content)):
                found.append(f"C4 {path}: {target} names no heading")
    return found


def _unfenced_links(text):
    """A file's text with fenced code and code spans blanked, so that sample links in code are
    not checked."""
    out, fenced = [], False
    for line in text.splitlines():
        if line.startswith("```"):
            fenced = not fenced
            out.append("")
            continue
        out.append("" if fenced else re.sub(r"`[^`]*`", "", line))
    return "\n".join(out)


def format_tables(module=None):
    """{the format page's table heading: the code's key set} (C5)."""
    d = module or declarations()
    return {
        "Top-level keys": d.TOP_KEYS,
        "Piece keys": d.PIECE_KEYS,
        "Model keys": d.MODEL_KEYS,
        "Row keys": d.ROW_KEYS,
        "Read keys": d.READ_KEYS,
        "Kernel keys": d.KERNEL_KEYS,
        "Provenance keys": d.PROVENANCE_KEYS,
        "Citation keys": d.CITATION_KEYS,
        "Work keys": d.WORK_KEYS,
        "Not-extracted keys": d.NOT_EXTRACTED_KEYS,
    }


def page_tables(text):
    """{heading: [the backticked keys of the first column of the table under it]}."""
    out, current, fenced = {}, None, False
    for line in text.splitlines():
        if line.startswith("```"):
            fenced = not fenced
        if fenced:
            continue
        heading = re.match(r"^#{2,4} (.+)$", line)
        if heading:
            current = heading.group(1).strip()
            continue
        cell = re.match(r"^\| `([a-z_]+)` \|", line)
        if current is not None and cell:
            out.setdefault(current, []).append(cell.group(1))
    return out


def check_format(text, tables, format_id):
    """C5: each key table of the format page equals the code's key set, in both directions, and
    the page names the format."""
    found = []
    if format_id not in text:
        found.append(f"C5 {FORMAT_PAGE}: it names the format {format_id}")
    written = page_tables(text)
    for heading, keys in tables.items():
        page = written.get(heading)
        if page is None:
            found.append(f"C5 {FORMAT_PAGE}: no table under '{heading}'")
            continue
        if len(page) != len(set(page)):
            found.append(f"C5 {FORMAT_PAGE}: '{heading}' lists a key twice")
        for key in sorted(set(keys) - set(page)):
            found.append(f"C5 {FORMAT_PAGE}: '{heading}' lacks the code's key {key}")
        for key in sorted(set(page) - set(keys)):
            found.append(f"C5 {FORMAT_PAGE}: '{heading}' lists {key}, which the code does not have")
    return found


def check(doc, files, complete=None):
    """C1-C5 over the library's files, in order."""
    d = declarations()
    return [
        *check_pages(doc, files, complete),
        *check_blocks(doc, files),
        *check_layers(doc, files),
        *check_links(files),
        *check_format(files.get(FORMAT_PAGE, ""), format_tables(d), d.FORMAT),
    ]


# ------------------------------------------------------------------ the commands


def template_skeleton(files):
    """The page skeleton: the template's first fenced Markdown block."""
    match = re.search(r"````markdown\n(.*?)\n````", files[TEMPLATE], re.S)
    if match is None:
        raise SystemExit(f"{TEMPLATE} holds no ````markdown skeleton")
    return match.group(1) + "\n"


def new_page(doc, files, piece, identifier):
    """A new page's path and text: the template's skeleton, with the ID and its blocks."""
    d = declarations()
    key = (piece, d.qualified(identifier))
    render = Render(doc)
    if key not in render.entries:
        raise SystemExit(f"No registered {piece} {identifier} in the manifest")
    path = d.page_path(piece, key[1])
    if path not in paged(doc):
        raise SystemExit(f"{piece} {identifier} gets no page in this repository")
    if path in files:
        raise SystemExit(f"{path} exists")
    text = template_skeleton(files).replace("<namespaced ID>", key[1])
    return path, rewrite_blocks(text, render.blocks(path, *key))


def write_all(doc, files):
    """{path: new text} of every file whose generated parts change."""
    render = Render(doc)
    out = {}
    for path, text in pages(files).items():
        identity = page_identity(path)
        if identity is not None and identity in render.entries:
            new = rewrite_blocks(text, render.blocks(path, *identity))
            if new != text:
                out[path] = new
    updated = dict(files, **out)
    index = render_index(doc, updated)
    if files.get(INDEX) != index:
        out[INDEX] = index
    if GLOSSARY in files:
        new = rewrite_blocks(files[GLOSSARY], glossary_blocks(doc, updated))
        if new != files[GLOSSARY]:
            out[GLOSSARY] = new
    return out


def main(argv=None):
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    command = parser.add_mutually_exclusive_group(required=True)
    command.add_argument("--new", nargs=2, metavar=("SECTION", "ID"))
    command.add_argument("--write", action="store_true")
    command.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    doc = declarations().manifest()
    files = load()
    if args.new:
        piece, identifier = args.new
        if piece not in PIECES:
            raise SystemExit(f"SECTION is one of {', '.join(PIECES)}")
        path, text = new_page(doc, files, piece, identifier)
        (ROOT / path).parent.mkdir(parents=True, exist_ok=True)
        (ROOT / path).write_text(text)
        print(f"wrote {path}; write its plain layers, then run --write and --check")
        files = load()
    if args.new or args.write:
        for path, text in write_all(doc, files).items():
            (ROOT / path).write_text(text)
            print(f"rendered {path}")
        return 0
    found = check(doc, files)
    for line in found:
        print(line)
    todo = len(set(paged(doc)) - set(files))
    print(f"{len(found)} findings over {len(pages(files))} pages; {todo} still to write")
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main())
