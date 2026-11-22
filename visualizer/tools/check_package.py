#!/usr/bin/env python3
"""Check an experiment's source package before the viewer reads it (schema/EXPERIMENT_PACKAGE.md).

    python3 -I tools/check_package.py FOLDER [--json]
    python3 -I tools/check_package.py --schema
    python3 -I tools/check_package.py --codes

FOLDER is a run folder: one with a manifest (experiment_package.json, cells.experiment_package@1), or one without, read as the
run adapter reads a folder today (its index.json, or else every folder in it that holds a view.json). A folder that
holds a view.json itself is one package, read as an arm of the folder around it.

Exit status 0: the package can be read, with a short report (notes may say what a manifest would state); 1: it cannot,
with every problem found, each a code and one sentence that names the file and the field; 2: a wrong call. --json
gives the report as JSON. --schema prints the manifest's JSON schema, written from the field table below
(schema/experiment_package.schema.json is that output, and tests/check_package.test.mjs holds the two equal). --codes
prints every code with its kind and what it means.

What it keeps to:
  * It reads and never writes. Nothing of a package is imported or run. Array files are read as the adapter reads
    them, a zip of .npy members, by their headers for shapes; each package's view is then read by the adapter's own
    reading (tools/adapt_run.py, adapt_engine_view), so that "valid" means "the adapter reads it".
  * A package is untrusted input: every file is capped in size before it is read, no link is followed, and no path
    leads outside the folder.
  * The manifest's copies are held to the runs' own statements: the engine's revision, snapshot and clean tree to each
    view and to each run's own record (run.json) where there is one, and a package's sidecars to the names that record
    lists. The order of the sidecars is the manifest's: the order they are played.
  * It judges no science: it says whether a package can be read, never whether a run is right.

Standard library only.
"""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import math
import os
import re
import stat
import sys
import zipfile
from array import array
from math import prod
from pathlib import Path

sys.dont_write_bytecode = True  # it writes nothing, not even the bytecode of the modules it reads
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import adapt_run  # noqa: E402  the adapter's own reading of a view, its sidecars, its summary and its refused picks
from lib.npy_reader import CODES as NPY_CODES  # noqa: E402
from lib.npy_reader import npz_headers  # noqa: E402

MANIFEST_FILE, MANIFEST_FORMAT = adapt_run.MANIFEST_FILE, adapt_run.MANIFEST_FORMAT
VIEW_FILE, VIEW_FORMAT, VIEW_KEYS = adapt_run.VIEW_FILE, adapt_run.VIEW_FORMAT, adapt_run.VIEW_KEYS
SIDECAR_FORMATS, SUMMARY_FORMAT, REFUSED_FILE = adapt_run.STATED_FORMATS, adapt_run.SUMMARY_FORMAT, adapt_run.REFUSED_FILE
KINDS = (VIEW_FORMAT,)  # the kinds of package this reader reads; another kind is named and left aside
LEVELS = ("source",)  # the play level comes in the next round
VISIBILITIES = ("public", "private")
# Caps: a package is untrusted input, and nothing past these is read.
MANIFEST_LIMIT = 1 << 20  # experiment_package.json
JSON_LIMIT = 32 << 20  # a view, a sidecar, a summary, an index, a REFUSED.json
ARRAY_LIMIT = 1 << 30  # one array a view names, as its header gives its size
ENTRY_LIMIT = 200_000  # files and folders walked in one check
SENTENCE_LIMIT = 2_000  # characters of one problem's or note's sentence
# Patterns, written once for this reader (re.fullmatch) and for the schema file (JSON Schema's ECMA patterns).
ID_PATTERN = r"^[a-z0-9]+([.-][a-z0-9]+)*$"
PATH_PATTERN = r"^(?!\.\.?(/|$))(?!.*/\.\.?(/|$))[A-Za-z0-9._-]+(/[A-Za-z0-9._-]+)*$"
NAME_PATTERN = r"^(?!\.+$)[A-Za-z0-9._-]+$"
SIDECAR_PATTERN = adapt_run.STATED_FILE.pattern  # a sidecar's plain name, as the adapter reads one
REVISION_PATTERN = r"^[0-9a-f]{7,40}$"
DATE_PATTERN = r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$"
PART = re.compile(r"[A-Za-z0-9._-]+")
# A path of a machine: a home, a mount or another root folder of one, or a drive letter. Read in every key and every
# string of the manifest after JSON's escapes are undone, so that a drive letter's one backslash is found.
MACHINE = re.compile(r"(?<![\w.-])/(?:home|mnt|Users|tmp|var|root|opt|srv)/|(?<![A-Za-z0-9])[A-Za-z]:[\\/]")
# Files of an arm's folder that are the run's own, not sidecars, whatever they say of themselves.
RUN_RECORD = "run.json"  # a run's own provenance record, where its driver wrote one; the manifest's copies are held to it
ASSEMBLY_KIND = "cells.assembly_view@1"  # the assembly's kind, named by the specification; this reader does not read it yet
RUN_FILES = {VIEW_FILE, "summary.json", RUN_RECORD, "manifest.json", "resolved_config.json", REFUSED_FILE, "index.json", MANIFEST_FILE}


# ---------------------------------------------------------------- the manifest's fields


class Field:
    """One field of the manifest: its kind, whether it is required, what it means, and the code a wrong value gets."""

    def __init__(self, kind, required, says, *, code="manifest.type", fields=None, item=None, values=None, at_least=0, pattern=None):
        self.kind, self.required, self.says, self.code = kind, required, says, code
        self.fields, self.item, self.values, self.at_least = fields or {}, item, values, at_least
        self.pattern = pattern or {"id": ID_PATTERN, "path": PATH_PATTERN, "name": NAME_PATTERN, "sidecar": SIDECAR_PATTERN, "revision": REVISION_PATTERN, "date": DATE_PATTERN}.get(kind)


MANIFEST = Field("object", True, "The manifest of an experiment's source package (experiment_package.json at the run folder's top).", fields={
    "format": Field("const", True, "The manifest's format and major version. A reader of @1 reads @1 only.", code="manifest.format", values=(MANIFEST_FORMAT,)),
    "level": Field("enum", True, "Which level of package this is: source, the run folder as the engine writes it. The play level comes in the next round.", code="manifest.level", values=LEVELS),
    "experiment": Field("object", True, "The experiment the packages are runs of, in its own words.", fields={
        "id": Field("id", True, "The experiment's id, one for each source package: the public id, and what other files point at. A run's id is <experiment id>--<arm>, with the seed where there is one.", code="manifest.id"),
        "group": Field("id", False, "The id under which a catalogue gathers this package with the other source packages of one experiment (its sweeps, each a package with an id of its own).", code="manifest.id"),
        "title": Field("text", True, "The experiment's name, in a few words."),
        "asks": Field("text", False, "What the experiment asks, in one sentence."),
        "plain": Field("text", False, "What it does, in plain sentences."),
        "status": Field("text", False, "The owner's own words for the runs' standing (a development run, not judged, say). For an experiment of the public record the page reads its standing from the record, and shows these words only where the record has none."),
        "sources": Field("list", False, "Where the experiment is stated: documents of the engine's repository, at its revision.", item=Field("object", True, "One source.", fields={
            "path": Field("text", True, "The document's path in the engine's repository (never a path of a machine)."),
            "where": Field("text", False, "Where in it, in words."),
        })),
        "citation": Field("object", False, "What the experiment replicates or reads from, as it is cited.", fields={
            "text": Field("text", True, "The citation as written."),
            "doi": Field("text", False, "Its DOI."),
        }),
    }),
    "engine": Field("object", False, "The engine's provenance, copied from the runs' own records: its revision, its snapshot and whether its tree was clean, and no more. The manifest adds no digest of its own. Where given, each run's view must agree with it, and so must its run.json where it has one.", fields={
        "revision": Field("revision", False, "The engine's revision that ran: each view's run.source.revision and each run.json's revision (a short form of the same is the same)."),
        "snapshot": Field("text", False, "The execution snapshot it ran from, by name: each run.json's snapshot."),
        "clean": Field("boolean", False, "Whether the engine's tree was clean: each run.json's clean, and the opposite of each view's run.source.dirty."),
    }),
    "made": Field("date", False, "The day the package was written (YYYY-MM-DD)."),
    "visibility": Field("enum", True, "Who may see the package: public, or private. A tool that stages a page, a site or an API refuses a private package (the next round).", code="manifest.visibility", values=VISIBILITIES),
    "licence": Field("text", True, "The licence the package is given under, by its SPDX identifier where it has one (CC-BY-4.0, say). Words and numbers read from a source keep that source's terms.", code="manifest.licence"),
    "summary": Field("path", False, "The experiment's summary of its sweeps (cells.experiment_summary@1), by its path relative to the manifest."),
    "packages": Field("list", True, "The packages, one for each arm, in the order a reader lists them.", at_least=1, item=Field("object", True, "One package.", fields={
        "arm": Field("id", True, "The arm's id. One arm once, in packages and refused together.", code="manifest.id"),
        "kind": Field("text", True, "How the package is read: cells.run_view@1 (a folder that holds the engine's view.json and the arrays it names), or cells.assembly_view@1 (the assembly's, written by its model's own writer). A reader names a package of a kind it does not read and reads the rest."),
        "path": Field("path", True, "The package's folder, relative to the manifest. In @1 it is the folder named as its arm, directly in the run folder."),
        "sidecars": Field("list", False, "The quantities the experiment's driver states beside the run (cells.experiment_quantity@1, cells.experiment_criterion@1), each by its plain file name in the package's folder, in the order they are played. Where the run's own run.json lists its sidecars, these are the same names, each once.", item=Field("sidecar", True, "One sidecar's plain file name: lower-case letters, digits, underscores and hyphens, then .json.", code="sidecar.name")),
        "label": Field("text", False, "The arm's name in words."),
    })),
    "refused": Field("list", False, "Picks an engine check refused: each a folder named as its arm, holding REFUSED.json and no view.", item=Field("object", True, "One refused pick.", fields={
        "arm": Field("id", True, "The pick's arm: its folder's name.", code="manifest.id"),
        "file": Field("name", True, "The refusal's file, by its plain name in the arm's folder (REFUSED.json)."),
    })),
})


def schema_of(field):
    """The JSON schema of one field of the table (draft 2020-12): what a JSON-schema library could check of it. What no
    schema says (a path that is there, one arm once, a view that fits its arrays) is the validator's."""
    out = {"description": field.says}
    if field.kind == "const":
        out["const"] = field.values[0]
    elif field.kind == "enum":
        out["enum"] = list(field.values)
    elif field.kind == "boolean":
        out["type"] = "boolean"
    elif field.kind == "object":
        out["type"] = "object"
        required = [name for name, item in field.fields.items() if item.required]
        if required:
            out["required"] = required
        out["properties"] = {name: schema_of(item) for name, item in field.fields.items()}
    elif field.kind == "list":
        out["type"] = "array"
        if field.at_least:
            out["minItems"] = field.at_least
        out["items"] = schema_of(field.item)
    else:
        out["type"] = "string"
        out["minLength"] = 1
        if field.pattern:
            out["pattern"] = field.pattern
    return out


def schema():
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": f"{MANIFEST_FORMAT}: the manifest of an experiment's source package",
        "$comment": "Written by tools/check_package.py --schema from its field table; do not edit by hand. The field names are those of the engine's lead, who keeps the specification (20 November 2026). A reader ignores a field it does not know (within a major). schema/EXPERIMENT_PACKAGE.md is the contract, and the validator holds what no schema says.",
        **schema_of(MANIFEST),
    }


# ---------------------------------------------------------------- codes

CODES = {
    # notes: said, and the package is still read
    "manifest.none": ("note", "The folder has no experiment_package.json: it is read as the adapter reads a folder today (its index.json, or else every folder in it that holds a view.json), and the report gives what a manifest would state."),
    "folder.one-package": ("note", "The folder holds a view.json itself: it is read as one package, the arm named as the folder, of the folder around it; a source package is that folder, with its manifest."),
    "manifest.unknown-field": ("note", "The manifest gives a field this reader does not know: it is left aside (within a major, a reader ignores what it does not know)."),
    "package.kind-unknown": ("note", "A package is of a kind this reader does not read (one it does not know, or the assembly's, cells.assembly_view@1, which it does not read yet): it is named and not read, and the rest is read."),
    "package.not-listed": ("note", "A folder holds a view.json and is not one of the folder's packages: a reader leaves it aside."),
    "package.no-view": ("note", "A folder holds a run of the engine's shared output path and no view.json: the adapter derives its view from tables of its own, and a source package holds the engine's own view."),
    "sidecar.unnamed": ("note", "A file beside a view says it is a sidecar, and nothing names it: a reader does not read it; a manifest names the sidecars to read, in their order."),
    "package.not-id": ("note", "In a folder with no manifest, a package's folder name is not an id, as a manifest's arm must be."),
    "index.machine-path": ("note", "The folder's index.json carries a path of a machine; a manifest may carry none."),
    # problems: the package cannot be read as it is
    "json.invalid": ("problem", "A file that must be JSON is not (or is not UTF-8)."),
    "size.cap": ("problem", "A file, an array or the folder is larger than this reader's cap: a package is untrusted input, and nothing past the cap is read."),
    "manifest.format": ("problem", "experiment_package.json is not a JSON object whose format is cells.experiment_package@1."),
    "manifest.level": ("problem", "experiment_package.json's level is not source: this round reads the source level only."),
    "manifest.missing": ("problem", "experiment_package.json lacks a required field."),
    "manifest.type": ("problem", "A field of experiment_package.json is not of its type (text, a list, an object, a revision, a date or true or false)."),
    "manifest.id": ("problem", "An id (the experiment's, or an arm's) is not lower-case letters and digits, joined by single dots or hyphens."),
    "manifest.visibility": ("problem", "experiment_package.json gives no visibility, or one that is not public or private."),
    "manifest.licence": ("problem", "experiment_package.json gives no licence."),
    "manifest.machine-path": ("problem", "experiment_package.json carries a path of a machine (/home/, /mnt/, /Users/ and the like, or a drive letter)."),
    "path.absolute": ("problem", "A path is absolute: every path of a package is relative to the manifest (a sidecar or a refusal's file, to its arm's folder)."),
    "path.outside": ("problem", "A path leaves the folder (..)."),
    "path.form": ("problem", "A path is not file names joined by /, each of letters, digits, dots, underscores and hyphens."),
    "path.missing": ("problem", "A path names nothing in the folder."),
    "path.kind": ("problem", "A path names a file where a folder is wanted, or a folder where a file is wanted."),
    "path.link": ("problem", "A file or folder of the package is a link: a package holds its files itself, and a reader follows no link."),
    "package.arm-twice": ("problem", "An arm is named twice (in packages and refused together): one arm once."),
    "package.path": ("problem", "A package's path is not the folder named as its arm, directly in the run folder: readers of @1 read a package from there."),
    "folder.no-package": ("problem", "A folder with no manifest holds no package: no index.json that chooses one, and no folder that holds a view.json."),
    "index.content": ("problem", "A folder's index.json does not choose its runs, or names a sidecar that is not a JSON file's plain name."),
    "view.missing": ("problem", "A package of the kind cells.run_view@1 holds no view.json."),
    "view.format": ("problem", "A package's view.json is not a run view (cells.run_view@1), or lacks a part every view gives."),
    "view.time": ("problem", "A view's time bases are not each an id, an array's name and the files that hold its rows."),
    "view.file-missing": ("problem", "A file a view's time base names (for itself and its records) is not there."),
    "view.array-file": ("problem", "A file a view names is not a zip of .npy arrays this reader can read."),
    "view.array-missing": ("problem", "A file a view names does not hold an array the view says is saved there."),
    "view.rows": ("problem", "A file of a time base does not hold the rows the view gives it."),
    "view.record": ("problem", "A view's record names no time base of the view, no array, or axes that are not the view's sets."),
    "view.shape": ("problem", "An array's shape does not fit its record: its time base's rows, then one length for each axis, from the view's sets."),
    "sidecar.name": ("problem", "A sidecar is not named by its plain file name in its arm's folder (lower-case letters, digits, underscores, hyphens, .json)."),
    "sidecar.format": ("problem", "A sidecar is not of a sidecar's format (cells.experiment_quantity@1, cells.experiment_criterion@1)."),
    "sidecar.cells": ("problem", "A sidecar's cells are not the view's cells, each once."),
    "sidecar.times": ("problem", "A sidecar has no row at a time the replay steps through: a sidecar is never resampled."),
    "sidecar.listed": ("problem", "A package's sidecars are not the ones its run's own record lists (run.json, sidecars): the same names, each once and no other. Their order is the manifest's, the order they are played."),
    "summary.format": ("problem", "The experiment's summary is not cells.experiment_summary@1."),
    "summary.content": ("problem", "The experiment's summary does not state what a reader of its sweeps reads (the adapter's own reading refuses it)."),
    "refused.format": ("problem", "A REFUSED.json does not name its own arm with the status refused."),
    "refused.has-view": ("problem", "A refused pick's folder holds a view.json: a refused pick has no view."),
    "refused.sweep": ("problem", "Refused picks are placed by the one sweep of the experiment's summary, and there is no summary, or it states several sweeps."),
    "refused.parameter": ("problem", "A REFUSED.json gives no finite value of its sweep's parameter."),
    "engine.provenance": ("problem", "The manifest's engine provenance (revision, snapshot, clean) is not what a run's own view states, or its run.json where it has one."),
    "adapter.refused": ("problem", "The adapter's own reading of the package refuses it, with its reason."),
    "adapter.error": ("problem", "The adapter's own reading of the package fails on it (an error of the adapter, or input it cannot read)."),
    "adapter.machine-path": ("problem", "The view the adapter would package carries a path of a machine."),
    "check.error": ("problem", "The check itself failed on the folder: an error of this reader, to be reported with the folder."),
}


class Report:
    """What one check found: the package's own statements, its problems and its notes."""

    def __init__(self, folder):
        self.folder = folder
        self.problems, self.notes = [], []
        self.entries = 0
        self.npz = {}

    def add(self, code, says, file=None, field=None):
        kind = CODES[code][0]
        if len(says) > SENTENCE_LIMIT:  # a sentence may quote what a package says of itself: never at any length
            says = says[:SENTENCE_LIMIT] + " ..."
        item = {"code": code, "file": file, "field": field, "says": says}
        (self.problems if kind == "problem" else self.notes).append(item)

    def count(self):
        return len(self.problems)


def rel(*parts):
    return "/".join(str(part) for part in parts if part not in (None, ""))


def finite(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def machine_paths(data, at=""):
    """[(where, found)] for every key and string of a JSON value that carries a path of a machine."""
    found = []
    if isinstance(data, dict):
        for key, value in data.items():
            where = f"{at}.{key}" if at else str(key)
            hit = MACHINE.search(str(key))
            if hit:
                found.append((where, hit.group(0)))
            found += machine_paths(value, where)
    elif isinstance(data, list):
        for k, value in enumerate(data):
            found += machine_paths(value, f"{at}[{k}]")
    elif isinstance(data, str):
        hit = MACHINE.search(data)
        if hit:
            found.append((at, hit.group(0)))
    return found


class Reader:
    """One check of one folder. Paths in its sentences are relative to the folder's parent (they begin with the folder's
    name), so that no path of the machine that checks is printed."""

    def __init__(self, folder):
        self.root = folder.resolve()
        self.report = Report(self.root.name)
        self.sizes = {}  # each .npz read: {array: its member's size as the zip declares it}

    # ---- files, capped and never followed through a link

    def shown(self, path):
        try:
            return rel(self.root.name, path.relative_to(self.root).as_posix()) if path != self.root else self.root.name
        except ValueError:
            return path.name

    def lstat(self, path):
        try:
            return path.lstat()
        except (FileNotFoundError, NotADirectoryError):
            return None

    def json_file(self, path, limit, *, file=None, field=None, missing="path.missing", strict=False, quiet=False):
        """A JSON file, read only where it is a plain file under the cap; None where it is not (with the problem said,
        unless `quiet`: for a file a folder need not hold and no reader of the play reads)."""
        file = file or self.shown(path)
        add = (lambda *said: None) if quiet else self.report.add
        st = self.lstat(path)
        if st is None:
            add(missing, f"{file} is not there.", file, field)
            return None
        if stat.S_ISLNK(st.st_mode):
            add("path.link", f"{file} is a link: a package holds its files itself, and a reader follows no link.", file, field)
            return None
        if not stat.S_ISREG(st.st_mode):
            add("path.kind", f"{file} is not a file.", file, field)
            return None
        if st.st_size > limit:
            add("size.cap", f"{file} is {st.st_size:,} bytes, over this reader's cap of {limit:,}: it is not read.", file, field)
            return None
        with open(path, "rb") as stream:
            raw = stream.read(limit + 1)
        if len(raw) > limit:
            add("size.cap", f"{file} grew past this reader's cap of {limit:,} bytes while it was read: it is not read.", file, field)
            return None

        def refuse(constant):
            raise ValueError(f"{constant} is not a number of JSON")

        try:
            return json.loads(raw.decode("utf-8"), **({"parse_constant": refuse} if strict else {}))
        except UnicodeDecodeError:
            add("json.invalid", f"{file} is not UTF-8 text.", file, field)
        except (ValueError, RecursionError) as error:
            add("json.invalid", f"{file} is not JSON ({str(error).splitlines()[0][:120]}).", file, field)
        return None

    def locate(self, base, text, *, file, field, want="file", missing="path.missing", plain=False, plain_code="path.form", pattern=None):
        """The file or folder a path names, relative to `base` (a folder of the package): None where the path is absolute,
        leaves the folder, is not of file names (or, given `plain`, not one plain name of `pattern`), names nothing, is a
        link on its way, or is not of the kind wanted. Each with its own code."""
        shown = f"{file}: {field} ({text})"
        if text.startswith(("/", "\\")) or re.match(r"[A-Za-z]:", text):
            self.report.add("path.absolute", f"{shown} is absolute: a package's paths are relative.", file, field)
            return None
        parts = text.replace("\\", "/").split("/")
        if ".." in parts:
            self.report.add("path.outside", f"{shown} leaves the folder.", file, field)
            return None
        if "\\" in text or not all(part not in ("", ".") and PART.fullmatch(part) for part in parts):
            self.report.add("path.form", f"{shown} is not file names joined by /, each of letters, digits, dots, underscores and hyphens.", file, field)
            return None
        if plain and (len(parts) > 1 or (pattern is not None and not re.fullmatch(pattern, text))):
            self.report.add(plain_code, f"{shown} is not {'a sidecar' if plain_code == 'sidecar.name' else 'a file'}'s plain name in its arm's folder{' (lower-case letters, digits, underscores and hyphens, then .json)' if plain_code == 'sidecar.name' else ''}.", file, field)
            return None
        target = base
        for part in parts:
            target = target / part
            st = self.lstat(target)
            if st is None:
                self.report.add(missing, f"{shown} names nothing: {self.shown(target)} is not there.", file, field)
                return None
            if stat.S_ISLNK(st.st_mode):
                self.report.add("path.link", f"{shown} goes through {self.shown(target)}, which is a link: a reader follows no link.", file, field)
                return None
        if (want == "dir") != stat.S_ISDIR(st.st_mode):
            self.report.add("path.kind", f"{shown} names a {'file' if want == 'dir' else 'folder'}, and a {'folder' if want == 'dir' else 'file'} is wanted.", file, field)
            return None
        return target

    def walk(self, top):
        """Every link under a folder of the package, said as a problem; the walk is bounded."""
        stack = [top]
        while stack:
            folder = stack.pop()
            try:
                items = sorted(os.scandir(folder), key=lambda item: item.name)
            except OSError:
                continue
            for item in items:
                self.report.entries += 1
                if self.report.entries > ENTRY_LIMIT:
                    self.report.add("size.cap", f"{self.root.name}/ holds more than {ENTRY_LIMIT:,} files and folders: it is not walked further.", self.root.name, None)
                    return False
                if item.is_symlink():
                    shown = self.shown(Path(item.path))
                    self.report.add("path.link", f"{shown} is a link: a package holds its files itself, and a reader follows no link.", shown, None)
                elif item.is_dir(follow_symlinks=False):
                    stack.append(Path(item.path))
        return True

    def headers(self, path, file, field):
        """The arrays of a .npz file, by their headers: {name: (descr, shape)}, or None (with the problem said). The
        member's size as the zip declares it is kept beside, in `sizes`: the adapter's reading decompresses a member
        whole, so a member is capped by that size as well as by its header's shape."""
        if path not in self.report.npz:
            try:
                self.report.npz[path] = npz_headers(path)
                with zipfile.ZipFile(path) as archive:
                    self.sizes[path] = {info.filename[:-4]: info.file_size for info in archive.infolist() if info.filename.endswith(".npy")}
            except (zipfile.BadZipFile, ValueError, OSError, EOFError, RuntimeError, NotImplementedError) as error:
                self.report.add("view.array-file", f"{file} is not a zip of .npy arrays this reader can read ({str(error)[:120]}).", file, field)
                self.report.npz[path] = None
        return self.report.npz[path]

    def too_large(self, path, array_name, descr, shape):
        """An array's size as its header gives it, or as its zip declares it if more: over the cap, or not."""
        size = prod(shape) * (4 * int(descr[2:]) if descr[1:2] == "U" else array(NPY_CODES[descr]).itemsize)
        return max(size, self.sizes.get(path, {}).get(array_name, 0)) > ARRAY_LIMIT, max(size, self.sizes.get(path, {}).get(array_name, 0))


# ---------------------------------------------------------------- the manifest


def check_fields(reader, data, field, at):
    """Type every field of the table; a field the table does not know is a note. A path or a file's name that is text is
    judged where it is looked for in the folder, each fault by its own code."""
    report = reader.report
    if field.kind == "object":
        if not isinstance(data, dict):
            report.add(field.code, f"experiment_package.json: {at or 'the manifest'} is not an object.", MANIFEST_FILE, at or None)
            return
        for name, item in field.fields.items():
            where = f"{at}.{name}" if at else name
            if name not in data or data[name] is None:
                if item.required:
                    code = item.code if item.code in ("manifest.visibility", "manifest.licence") else "manifest.missing"
                    report.add(code, f"experiment_package.json gives no {where}: {item.says}", MANIFEST_FILE, where)
                continue
            check_fields(reader, data[name], item, where)
        for name in sorted(set(data) - set(field.fields)):
            where = f"{at}.{name}" if at else name
            report.add("manifest.unknown-field", f"experiment_package.json gives {where}, which is not a field of {MANIFEST_FORMAT} that this reader knows: it is left aside.", MANIFEST_FILE, where)
        return
    if field.kind == "list":
        if not isinstance(data, list) or len(data) < field.at_least:
            report.add(field.code, f"experiment_package.json: {at} is not a list{f' of {field.at_least} or more' if field.at_least else ''}.", MANIFEST_FILE, at)
            return
        for k, value in enumerate(data):
            check_fields(reader, value, field.item, f"{at}[{k}]")
        return
    if field.kind in ("path", "name", "sidecar") and isinstance(data, str) and data:
        return  # judged in the folder (path.absolute, path.outside, path.form, sidecar.name, path.missing)
    ok = {
        "const": lambda value: value in field.values,
        "enum": lambda value: value in field.values,
        "boolean": lambda value: isinstance(value, bool),
    }.get(field.kind, lambda value: isinstance(value, str) and bool(value.strip()) and (field.pattern is None or re.fullmatch(field.pattern, value) is not None))(data)
    if not ok:
        wants = {
            "const": " or ".join(field.values or ()),
            "enum": " or ".join(field.values or ()),
            "boolean": "true or false",
            "text": "text",
            "id": "an id: lower-case letters and digits, joined by single dots or hyphens",
            "path": "a relative path",
            "name": "a plain file name",
            "sidecar": "a sidecar's plain file name (lower-case letters, digits, underscores and hyphens, then .json)",
            "revision": "a revision (7 to 40 hexadecimal digits)",
            "date": "a day (YYYY-MM-DD)",
        }[field.kind]
        report.add(field.code, f"experiment_package.json: {at} is {json.dumps(data)[:80]}, not {wants}.", MANIFEST_FILE, at)


def read_manifest(reader):
    """The manifest, typed by the table: (manifest, ok to read on), with every problem said."""
    report = reader.report
    manifest = reader.json_file(reader.root / MANIFEST_FILE, MANIFEST_LIMIT, file=MANIFEST_FILE, strict=True)
    if manifest is None:
        return None, False
    if not isinstance(manifest, dict) or manifest.get("format") != MANIFEST_FORMAT:
        said = manifest.get("format") if isinstance(manifest, dict) else None
        report.add("manifest.format", f"experiment_package.json is {'not a JSON object' if not isinstance(manifest, dict) else f'of the format {json.dumps(said)}'}, not {MANIFEST_FORMAT}: a reader of @1 does not read it.", MANIFEST_FILE, "format")
        return manifest, False
    if manifest.get("level") not in LEVELS:
        report.add("manifest.level", f"experiment_package.json's level is {json.dumps(manifest.get('level'))}: this round reads the source level only ({', '.join(LEVELS)}).", MANIFEST_FILE, "level")
        return manifest, False
    check_fields(reader, manifest, MANIFEST, "")
    for where, hit in machine_paths(manifest):
        report.add("manifest.machine-path", f"experiment_package.json carries a path of a machine at {where} ({hit}...): a package names its files relative to its manifest, and nothing of the machine that wrote it.", MANIFEST_FILE, where)
    return manifest, True


# ---------------------------------------------------------------- one package, its view and its sidecars


def replay_times(reader, arm, folder, view):
    """The times the replay steps through, as the adapter reads them (its time base: observed rows, else the state's)."""
    bases = {base.get("id"): base for base in view["time"].get("bases") or [] if isinstance(base, dict)}
    line = next((identifier for identifier in ("observation", "accepted") if identifier in bases and bases[identifier].get("files")), None)
    if line is None:
        return None
    try:
        _, values, _ = adapt_run.view_rows(arm, folder, bases[line], bases[line].get("array"))
    except (adapt_run.Refused, ValueError, OSError, zipfile.BadZipFile) as error:
        reader.report.add("adapter.refused", f"{arm}: the adapter cannot read its time base {line}: {str(getattr(error, 'code', error)).removeprefix('adapt_run: ')}", rel(reader.root.name, arm, VIEW_FILE), "time.bases")
        return None
    return list(values)


def check_view(reader, arm, folder):
    """A run view and the arrays it names, by their headers: (view, named cells) or None, with every problem said."""
    report = reader.report
    file = reader.shown(folder / VIEW_FILE)
    view = reader.json_file(folder / VIEW_FILE, JSON_LIMIT, file=file, missing="view.missing")
    if view is None:
        return None
    if not isinstance(view, dict) or view.get("format") != VIEW_FORMAT:
        said = view.get("format") if isinstance(view, dict) else None
        report.add("view.format", f"{file} is {'not a JSON object' if not isinstance(view, dict) else f'of the format {json.dumps(said)}'}, not a run view ({VIEW_FORMAT}).", file, "format")
        return None
    lacking = sorted(VIEW_KEYS - set(view))
    if lacking:
        report.add("view.format", f"{file} lacks {', '.join(lacking)}, which every run view gives.", file, ", ".join(lacking))
        return None
    sets = {item.get("id"): item for item in view["sets"] if isinstance(item, dict) and isinstance(item.get("id"), str)} if isinstance(view["sets"], list) else {}
    sizes = {}
    for identifier, item in sets.items():
        recorded, ids = item.get("recorded"), item.get("ids")
        if isinstance(recorded, list):
            sizes[identifier] = len(recorded)
        elif isinstance(ids, list):
            sizes[identifier] = len(ids)
    cells = [cell for cell in (sets.get("cell") or {}).get("ids") or [] if cell is not None] if isinstance((sets.get("cell") or {}).get("ids"), list) else []
    time = view["time"]
    bases_given = time.get("bases") if isinstance(time, dict) else None
    if not isinstance(bases_given, list) or not bases_given:
        report.add("view.time", f"{file}: time.bases is not a list of time bases.", file, "time.bases")
        return None
    bases, before = {}, report.count()
    for k, base in enumerate(bases_given):
        where = f"time.bases[{k}]"
        if not (isinstance(base, dict) and isinstance(base.get("id"), str) and isinstance(base.get("array"), str) and isinstance(base.get("files"), list) and base["files"]):
            report.add("view.time", f"{file}: {where} does not give its id, its array and the files that hold its rows (id, array, files).", file, where)
            continue
        parts, at = [], 0
        for j, part in enumerate(base["files"]):
            field = f"{where}.files[{j}]"
            if not (isinstance(part, dict) and isinstance(part.get("file"), str) and part["file"] and isinstance(part.get("rows"), list) and len(part["rows"]) == 2 and all(type(row) is int for row in part["rows"])):
                report.add("view.time", f"{file}: {field} does not give a file and its rows [from, to].", file, field)
                parts = None
                break
            path = reader.locate(folder, part["file"], file=file, field=f"{field}.file", missing="view.file-missing")
            if path is None:
                parts = None
                break
            arrays = reader.headers(path, reader.shown(path), f"{field}.file")
            if arrays is None:
                parts = None
                break
            shown = reader.shown(path)
            if base["array"] not in arrays:
                report.add("view.array-missing", f"{shown} does not hold {base['array']}, the array of the time base {base['id']} ({where}.array).", shown, f"{where}.array")
                parts = None
                break
            rows = arrays[base["array"]][1][0] if arrays[base["array"]][1] else None
            if part["rows"] != [at, at + (rows or 0)] or rows is None:
                report.add("view.rows", f"{shown} holds {rows} rows of {base['array']}, and {file} gives it the rows {part['rows']} ({field}.rows), which must follow on from {at}.", shown, f"{field}.rows")
                parts = None
                break
            at = part["rows"][1]
            parts.append((path, arrays, rows))
        if parts is not None:
            bases[base["id"]] = parts
    records = view["records"] if isinstance(view["records"], list) else []
    if not isinstance(view["records"], list):
        report.add("view.record", f"{file}: records is not a list.", file, "records")
    named_bases = {base.get("id") for base in bases_given if isinstance(base, dict)}
    for k, record in enumerate(records):
        where = f"records[{k}]"
        if not isinstance(record, dict):
            report.add("view.record", f"{file}: {where} is not an object.", file, where)
            continue
        label = f"{where} ({record.get('id')})"
        axes = record.get("axes")
        if record.get("base") not in named_bases or not isinstance(record.get("array"), str) or not (isinstance(axes, list) and all(isinstance(axis, str) for axis in axes)):
            report.add("view.record", f"{file}: {label} does not name a time base of the view, its array and its axes (base, array, axes).", file, where)
            continue
        strangers = [axis for axis in axes if axis != "time" and axis not in sizes]
        if strangers:
            report.add("view.record", f"{file}: {label} lies along {', '.join(strangers)}, which the view does not list as a set with its ids.", file, f"{where}.axes")
            continue
        for path, arrays, rows in bases.get(record["base"], []):
            shown = reader.shown(path)
            if record["array"] not in arrays:
                report.add("view.array-missing", f"{shown} does not hold {record['array']}, which {file} says is saved there ({label}, on the time base {record['base']}).", shown, f"{where}.array")
                continue
            descr, shape = arrays[record["array"]]
            wanted = (rows, *(sizes[axis] for axis in axes if axis != "time"))
            if tuple(shape) != wanted:
                report.add("view.shape", f"{shown}: {record['array']} has the shape {list(shape)}, and {file} gives it {list(wanted)} ({label}: the base's rows, then {', '.join(axis for axis in axes if axis != 'time') or 'nothing'} by the view's sets).", shown, f"{where}.axes")
                continue
            over, size = reader.too_large(path, record["array"], descr, shape)
            if over:
                report.add("size.cap", f"{shown}: {record['array']} is {size:,} bytes as its header or its zip gives it, over this reader's cap of {ARRAY_LIMIT:,}: it is not read.", shown, f"{where}.array")
    for identifier, parts in bases.items():
        base = next(item for item in bases_given if isinstance(item, dict) and item.get("id") == identifier)
        for path, arrays, rows in parts:
            descr, shape = arrays[base["array"]]
            over, size = reader.too_large(path, base["array"], descr, shape)
            if over:
                report.add("size.cap", f"{reader.shown(path)}: {base['array']} is {size:,} bytes as its header or its zip gives it, over this reader's cap of {ARRAY_LIMIT:,}: it is not read.", reader.shown(path), "time.bases")
    if report.count() > before:
        return None
    return view, cells


def check_sidecar(reader, arm, folder, name, field, cells, times):
    """A sidecar's format, its cells and its times against the view's (the adapter's own reading holds the rest)."""
    report = reader.report
    file = reader.shown(folder / name)
    data = reader.json_file(folder / name, JSON_LIMIT, file=file, field=field)
    if data is None:
        return
    if not isinstance(data, dict) or data.get("format") not in SIDECAR_FORMATS:
        said = data.get("format") if isinstance(data, dict) else None
        report.add("sidecar.format", f"{file} is {'not a JSON object' if not isinstance(data, dict) else f'of the format {json.dumps(said)}'}, not a sidecar ({' or '.join(SIDECAR_FORMATS)}).", file, "format")
        return
    named = data.get("cells")
    if not (isinstance(named, list) and all(isinstance(cell, str) and cell for cell in named) and len(set(named)) == len(named)):
        report.add("sidecar.cells", f"{file} does not name each of its cells once (cells).", file, "cells")
    elif set(named) != set(cells):
        missing, strange = [cell for cell in cells if cell not in named], [cell for cell in named if cell not in cells]
        words = "; ".join(item for item in (f"it lacks {', '.join(missing[:4])}" if missing else "", f"the view has no {', '.join(strange[:4])}" if strange else "") if item)
        report.add("sidecar.cells", f"{file} names other cells than {arm}/{VIEW_FILE}: {words}.", file, "cells")
    stated = data.get("times_s")
    if not (isinstance(stated, list) and stated and all(finite(time) for time in stated)):
        report.add("sidecar.times", f"{file} does not give its times as numbers (times_s).", file, "times_s")
        return
    if times is None:
        return
    at = 0
    for time in times:
        while at < len(stated) and stated[at] < time and not math.isclose(stated[at], time, **adapt_run.TIME_CLOSE):
            at += 1
        if not (at < len(stated) and math.isclose(stated[at], time, **adapt_run.TIME_CLOSE)):
            report.add("sidecar.times", f"{file} has no row at {time:g} s, a time the replay of {arm} steps through: a sidecar is never resampled (times_s).", file, "times_s")
            return


def run_record(reader, folder, *, say):
    """The run's own record (run.json) where its folder holds one: what it states of the four things a manifest copies or
    names, each None where it does not state it; None where the folder holds none. Its format is its driver's own. A
    clean tree is `clean`; `snapshot_clean`, as the linear networks' driver wrote it before the manifest, is read as the
    same where `clean` is not given. With `say`, a record that is there and cannot be read is a problem by its own code
    (a link is said by the walk of the folder); without, it states nothing."""
    path = folder / RUN_RECORD
    st = reader.lstat(path)
    if st is None or stat.S_ISLNK(st.st_mode):
        return None
    data = reader.json_file(path, JSON_LIMIT, quiet=not say)
    if not isinstance(data, dict):
        return None
    text = lambda key: data[key] if isinstance(data.get(key), str) and data[key] else None  # noqa: E731
    key = "clean" if isinstance(data.get("clean"), bool) else "snapshot_clean"
    clean = data.get(key) if isinstance(data.get(key), bool) else None
    return {"revision": text("revision"), "snapshot": text("snapshot"), "clean": clean, "clean_key": key, "sidecars": data["sidecars"] if isinstance(data.get("sidecars"), list) else None}


def check_run_record(reader, folder, declared, where, engine):
    """The manifest's copies against the run's own record, where the arm's folder holds one (a run.json is not required):
    the engine's revision, snapshot and clean tree, and the names of the package's sidecars: the same names, each once
    and no other. Their order is the manifest's, the order they are played, whatever the record's."""
    report = reader.report
    record = run_record(reader, folder, say=True)
    if record is None:
        return
    file = reader.shown(folder / RUN_RECORD)
    if engine:
        revision, snapshot, clean = engine.get("revision"), engine.get("snapshot"), engine.get("clean")
        if isinstance(revision, str) and revision and record["revision"] and not (record["revision"].startswith(revision) or revision.startswith(record["revision"])):
            report.add("engine.provenance", f"{MANIFEST_FILE} gives the engine's revision {revision} (engine.revision), and {file} states {record['revision']} (revision).", MANIFEST_FILE, "engine.revision")
        if isinstance(snapshot, str) and snapshot and record["snapshot"] and snapshot != record["snapshot"]:
            report.add("engine.provenance", f"{MANIFEST_FILE} names the snapshot {snapshot} (engine.snapshot), and {file} names {record['snapshot']} (snapshot).", MANIFEST_FILE, "engine.snapshot")
        if isinstance(clean, bool) and record["clean"] is not None and clean != record["clean"]:
            report.add("engine.provenance", f"{MANIFEST_FILE} says the engine's tree was {'clean' if clean else 'dirty'} (engine.clean), and {file} says it was {'clean' if record['clean'] else 'dirty'} ({record['clean_key']}).", MANIFEST_FILE, "engine.clean")
    listed = record["sidecars"]
    if listed is None or not all(isinstance(name, str) and re.fullmatch(SIDECAR_PATTERN, name) for name in declared):
        return  # the record lists none to hold the manifest to; a name that is no sidecar's plain name is said by its own code
    if not all(isinstance(name, str) for name in listed) or sorted(listed) != sorted(declared):
        shown = lambda names: ", ".join(str(name) for name in names) or "none"  # noqa: E731
        report.add("sidecar.listed", f"{MANIFEST_FILE}: {where} names {shown(declared)}, and {file} lists {shown(listed)} (sidecars): the same names are wanted, each once and no other, in the order they are played.", MANIFEST_FILE, where)


def check_package(reader, arm, folder, sidecars, *, root, experiment, sidecar_fields, engine=None):
    """One package of the kind cells.run_view@1: its links, its view and arrays, its sidecars, then the adapter's own
    reading of it. Returns what the report says of it."""
    report = reader.report
    before = report.count()
    out = {"arm": arm, "kind": VIEW_FORMAT, "path": arm, "sidecars": list(sidecars), "read": False}
    reader.walk(folder)
    checked = check_view(reader, arm, folder)
    if checked is None:
        return out
    view, cells = checked
    out["cells"] = len(cells)
    times = replay_times(reader, arm, folder, view)
    for name, field in zip(sidecars, sidecar_fields):
        check_sidecar(reader, arm, folder, name, field, cells, times)
    if times is not None:
        out["times"] = len(times)
    # The adapter's reading also reads the arm's definition and summary when they are there: capped before it does.
    for name in ("resolved_config.json", "summary.json"):
        st = reader.lstat(folder / name)
        if st is not None and stat.S_ISREG(st.st_mode) and st.st_size > JSON_LIMIT:
            report.add("size.cap", f"{reader.shown(folder / name)} is {st.st_size:,} bytes, over this reader's cap of {JSON_LIMIT:,}: it is not read.", reader.shown(folder / name), None)
    if report.count() > before:
        return out
    # The adapter's own reading of the package, as `npm run adapt:runs` reads it: what it refuses, this check refuses.
    try:
        packaged, _, notes = adapt_run.adapt_engine_view(root, arm, experiment, {})
        adapt_run.check_clean(arm, json.dumps(packaged, ensure_ascii=False))
    except adapt_run.Refused as refusal:
        said = str(refusal.code).removeprefix("adapt_run: ")
        code = "adapter.machine-path" if "would carry a machine path" in said else "adapter.refused"
        report.add(code, f"{reader.shown(folder)}: the adapter refuses it: {said}", reader.shown(folder), None)
        return out
    except Exception as error:  # noqa: BLE001  garbage in a package gives a code, never a traceback
        report.add("adapter.error", f"{reader.shown(folder)}: the adapter's reading fails on it ({type(error).__name__}: {str(error)[:160]}).", reader.shown(folder), None)
        return out
    out.update({"read": True, "records": len(packaged.get("records") or []), "rows": notes.get("records")})
    stated_run = view.get("run") if isinstance(view.get("run"), dict) else {}
    source = stated_run.get("source") if isinstance(stated_run.get("source"), dict) else None
    out["engine"] = {"revision": (source or {}).get("revision"), "dirty": (source or {}).get("dirty"), "models": [model for model in stated_run.get("engine_models") or [] if isinstance(model, str)]}
    if engine:
        file = reader.shown(folder / VIEW_FILE)
        revision, clean = engine.get("revision"), engine.get("clean")
        if isinstance(revision, str) and source and isinstance(source.get("revision"), str) and not (source["revision"].startswith(revision) or revision.startswith(source["revision"])):
            report.add("engine.provenance", f"experiment_package.json gives the engine's revision {revision} (engine.revision), and {file} states {source['revision']} (run.source.revision).", MANIFEST_FILE, "engine.revision")
        if isinstance(clean, bool) and source and isinstance(source.get("dirty"), bool) and clean == source["dirty"]:
            report.add("engine.provenance", f"experiment_package.json says the engine's tree was {'clean' if clean else 'dirty'} (engine.clean), and {file} says it was {'dirty' if source['dirty'] else 'clean'} (run.source.dirty).", MANIFEST_FILE, "engine.clean")
    return out


# ---------------------------------------------------------------- the summary and the refused picks


def check_summary(reader, path, file, field, rows):
    """The experiment's summary, read by the adapter's own reading of its sweeps: its sweeps, or None."""
    data = reader.json_file(path, JSON_LIMIT, file=file, field=field)
    if data is None:
        return None
    if not isinstance(data, dict) or data.get("format") != SUMMARY_FORMAT:
        reader.report.add("summary.format", f"{file} is not an experiment summary ({SUMMARY_FORMAT}).", file, field)
        return None
    try:
        return adapt_run.sweeps_of(path, rows)
    except adapt_run.Refused as refusal:
        reader.report.add("summary.content", f"{file}: {str(refusal.code).removeprefix('adapt_run: ')}", file, field)
    except Exception as error:  # noqa: BLE001
        reader.report.add("summary.content", f"{file}: the adapter's reading of it fails ({type(error).__name__}: {str(error)[:160]}).", file, field)
    return None


def check_refused(reader, arm, folder, name, sweeps, field):
    """One refused pick: a folder named as its arm, holding its REFUSED.json and no view."""
    report = reader.report
    reader.walk(folder)
    if reader.lstat(folder / VIEW_FILE) is not None:
        report.add("refused.has-view", f"{reader.shown(folder)} holds {name} and a {VIEW_FILE}: a refused pick has no view.", reader.shown(folder / VIEW_FILE), None)
    file = reader.shown(folder / name)
    said = reader.json_file(folder / name, JSON_LIMIT, file=file, field=field)
    if said is None:
        return
    if not (isinstance(said, dict) and said.get("arm") == arm and said.get("status") == "refused"):
        report.add("refused.format", f"{file} does not name its own arm ({arm}) with the status refused (arm, status).", file, "arm, status")
        return
    if sweeps is not None and len(sweeps) == 1:
        parameter = sweeps[0]["parameter"]["id"]
        if not finite(said.get(parameter)):
            report.add("refused.parameter", f"{file} gives no finite value of the sweep's parameter {parameter} ({parameter}).", file, parameter)


# ---------------------------------------------------------------- one folder


def check(folder):
    """Check one folder: the report as a dict."""
    reader = Reader(folder)
    report, root = reader.report, reader.root
    result = {"folder": root.name, "manifest": False, "experiment": None, "visibility": None, "licence": None, "packages": [], "refused": [], "summary": None, "would_state": None}
    manifest_stat = reader.lstat(root / MANIFEST_FILE)
    if manifest_stat is not None:
        result["manifest"] = True
        manifest, ok = read_manifest(reader)
        if ok:
            check_manifest_folder(reader, manifest, result)
    elif reader.lstat(root / VIEW_FILE) is not None:
        check_one_package(reader, result)
    else:
        check_bare_folder(reader, result)
    result["problems"], result["notes"] = report.problems, report.notes
    result["readable"] = not report.problems
    return result


def run_id_of(experiment, arm):
    try:
        return adapt_run.run_id(experiment, arm)
    except adapt_run.Refused:
        return None


def check_manifest_folder(reader, manifest, result):
    """A folder with its manifest: every package it lists, its refused picks and its summary."""
    report, root = reader.report, reader.root
    experiment = manifest.get("experiment") if isinstance(manifest.get("experiment"), dict) else {}
    identifier = experiment.get("id") if isinstance(experiment.get("id"), str) and re.fullmatch(ID_PATTERN, experiment["id"]) else "package"
    result.update({"experiment": {key: experiment.get(key) for key in ("id", "group", "title", "status") if isinstance(experiment.get(key), str)}, "visibility": manifest.get("visibility"), "licence": manifest.get("licence")})
    engine = manifest.get("engine") if isinstance(manifest.get("engine"), dict) else None
    packages = manifest.get("packages") if isinstance(manifest.get("packages"), list) else []
    refused = manifest.get("refused") if isinstance(manifest.get("refused"), list) else []
    seen, listed, to_read = {}, set(), []
    for k, item in enumerate(packages):
        if not isinstance(item, dict):
            continue
        arm, where = item.get("arm"), f"packages[{k}]"
        if isinstance(arm, str):
            if arm in seen:
                report.add("package.arm-twice", f"experiment_package.json names the arm {arm} twice ({seen[arm]} and {where}): one arm once.", MANIFEST_FILE, f"{where}.arm")
                continue
            seen[arm] = where
        if not (isinstance(arm, str) and re.fullmatch(ID_PATTERN, arm)):
            continue  # said by the field's type
        path = item.get("path")
        if not isinstance(path, str) or not path:
            continue
        folder = reader.locate(root, path, file=MANIFEST_FILE, field=f"{where}.path", want="dir")
        if folder is None:
            continue
        listed.add(folder.name)
        if path != arm:
            report.add("package.path", f"experiment_package.json: {where}.path ({path}) is not the folder named as its arm ({arm}): readers of @1 read a package from the folder named as its arm, directly in the run folder.", MANIFEST_FILE, f"{where}.path")
            continue
        kind = item.get("kind")
        if kind not in KINDS:
            if isinstance(kind, str) and kind:
                why = "the assembly's, which this reader does not read yet" if kind == ASSEMBLY_KIND else "which this reader does not know"
                report.add("package.kind-unknown", f"experiment_package.json: {where} ({arm}) is of the kind {kind}, {why}: it is named and not read, and the rest is read.", MANIFEST_FILE, f"{where}.kind")
                result["packages"].append({"arm": arm, "kind": kind, "path": path, "read": False})
            continue
        sidecars = item.get("sidecars") if isinstance(item.get("sidecars"), list) else []
        check_run_record(reader, folder, sidecars, f"{where}.sidecars", engine)
        names, fields = [], []
        for j, name in enumerate(sidecars):
            field = f"{where}.sidecars[{j}]"
            if not (isinstance(name, str) and name):
                continue  # said by the field's type (sidecar.name)
            if reader.locate(folder, name, file=MANIFEST_FILE, field=field, plain=True, plain_code="sidecar.name", pattern=SIDECAR_PATTERN) is not None:
                names.append(name)
                fields.append(field)
        to_read.append((arm, folder, names, fields, len(names) == len(sidecars)))
    picks = []
    for k, item in enumerate(refused):
        if not isinstance(item, dict):
            continue
        arm, name, where = item.get("arm"), item.get("file"), f"refused[{k}]"
        if isinstance(arm, str):
            if arm in seen:
                report.add("package.arm-twice", f"experiment_package.json names the arm {arm} twice ({seen[arm]} and {where}): one arm once.", MANIFEST_FILE, f"{where}.arm")
                continue
            seen[arm] = where
        if not (isinstance(arm, str) and re.fullmatch(ID_PATTERN, arm) and isinstance(name, str) and name):
            continue  # said by the fields' types
        folder = reader.locate(root, arm, file=MANIFEST_FILE, field=f"{where}.arm", want="dir")
        if folder is None:
            continue
        listed.add(folder.name)
        if reader.locate(folder, name, file=MANIFEST_FILE, field=f"{where}.file", plain=True, pattern=NAME_PATTERN) is not None:
            picks.append((arm, folder, name, where))
    # The summary, read as the adapter reads it, with the runs this folder would give.
    sweeps, rows = None, [{"arm": arm, "id": run_id_of(identifier, arm)} for arm, *_ in to_read]
    if isinstance(manifest.get("summary"), str) and manifest["summary"]:
        path = reader.locate(root, manifest["summary"], file=MANIFEST_FILE, field="summary")
        if path is not None:
            sweeps = check_summary(reader, path, reader.shown(path), "summary", rows)
            result["summary"] = {"file": manifest["summary"], "sweeps": len(sweeps) if sweeps is not None else None}
    # The adapter refuses a manifest it cannot read before it reads any package: its own reading of the packages waits for
    # a manifest it reads. Where this check has found no reason, the adapter's own is said.
    try:
        with contextlib.redirect_stderr(io.StringIO()):
            adapt_run.package_manifest(root)
        manifest_ok = True
    except adapt_run.Refused as refusal:
        manifest_ok = False
        if not report.problems:
            report.add("adapter.refused", f"{MANIFEST_FILE}: the adapter refuses it: {str(refusal.code).removeprefix('adapt_run: ')}", MANIFEST_FILE, None)
    for arm, folder, names, fields, whole in to_read:
        if not whole:
            result["packages"].append({"arm": arm, "kind": VIEW_FORMAT, "path": arm, "sidecars": names, "read": False})
            continue
        if not manifest_ok:
            reader.walk(folder)
            checked = check_view(reader, arm, folder)
            if checked is not None:
                times = replay_times(reader, arm, folder, checked[0])
                for name, field in zip(names, fields):
                    check_sidecar(reader, arm, folder, name, field, checked[1], times)
            result["packages"].append({"arm": arm, "kind": VIEW_FORMAT, "path": arm, "sidecars": names, "read": False})
            continue
        said = check_package(reader, arm, folder, names, root=root, experiment=identifier, sidecar_fields=fields, engine=engine)
        said["run"] = run_id_of(identifier, arm)
        result["packages"].append(said)
    for arm, folder, name, where in picks:
        check_refused(reader, arm, folder, name, sweeps, f"{where}.file")
        result["refused"].append({"arm": arm, "file": name})
    # A summary that is named and cannot be read is said by its own code; here only one that is not named, or that states several sweeps.
    if picks and ("summary" not in manifest or (sweeps is not None and len(sweeps) != 1)):
        why = "experiment_package.json names no summary" if "summary" not in manifest else f"its summary states {len(sweeps)} sweeps"
        report.add("refused.sweep", f"experiment_package.json lists {len(picks)} refused pick(s), which a reader places by the one sweep of the experiment's summary, and {why}.", MANIFEST_FILE, "refused")
    order = {item.get("arm"): k for k, item in enumerate(packages) if isinstance(item, dict)}
    result["packages"].sort(key=lambda item: order.get(item["arm"], len(order)))
    for item in sorted(os.scandir(root), key=lambda entry: entry.name):
        if item.is_dir(follow_symlinks=False) and item.name not in listed and reader.lstat(Path(item.path) / VIEW_FILE) is not None:
            report.add("package.not-listed", f"{reader.shown(Path(item.path))}/ holds a {VIEW_FILE} and is not one of experiment_package.json's packages: a reader leaves it aside.", reader.shown(Path(item.path)), None)


def sidecars_found(reader, folder, named):
    """Files beside a view that say they are sidecars and that nothing names: (name, format) for each, by plain name."""
    found = []
    for item in sorted(os.scandir(folder), key=lambda entry: entry.name):
        if item.name in named or item.name in RUN_FILES or not adapt_run.STATED_FILE.match(item.name) or not item.is_file(follow_symlinks=False):
            continue
        if item.stat(follow_symlinks=False).st_size > JSON_LIMIT:
            continue
        try:
            data = json.loads(Path(item.path).read_bytes().decode("utf-8"))
        except (ValueError, RecursionError):
            continue
        if isinstance(data, dict) and data.get("format") in SIDECAR_FORMATS:
            found.append((item.name, data["format"]))
    return found


def check_bare_folder(reader, result):
    """A folder with no manifest, read as the adapter reads one today: its index.json chooses its packages, and names
    their sidecars; else every folder in it that holds a view.json is a package, and none names a sidecar (the
    viewer's overlay does, today). Refused picks are the folders that hold REFUSED.json and no view."""
    report, root = reader.report, reader.root
    report.add("manifest.none", f"{root.name}/ has no {MANIFEST_FILE}: it is read as the adapter reads a folder today (its index.json, or else every folder in it that holds a {VIEW_FILE}), and the report gives what a manifest would state.", root.name, None)
    index_path = root / "index.json"
    index = None
    if reader.lstat(index_path) is not None:
        index = reader.json_file(index_path, JSON_LIMIT, file=rel(root.name, "index.json"))
        if index is None:
            return
        places = machine_paths(index)
        if places:
            where, hit = places[0]
            more = f" and {len(places) - 1} more place(s)" if len(places) > 1 else ""
            report.add("index.machine-path", f"{root.name}/index.json carries a path of a machine at {where} ({hit}...){more}; a manifest may carry none.", rel(root.name, "index.json"), where)
    folders = sorted((item for item in os.scandir(root) if item.is_dir(follow_symlinks=False)), key=lambda entry: entry.name)
    try:
        arms = adapt_run.runs_in_index(root)
    except adapt_run.Refused as refusal:
        said = str(refusal.code).removeprefix("adapt_run: ")
        if index is None:
            report.add("folder.no-package", f"{root.name}/ holds no package: no {MANIFEST_FILE}, no index.json, and no folder in it that holds a {VIEW_FILE}.", root.name, None)
            for item in folders:
                if reader.lstat(Path(item.path) / "resolved_config.json") is not None or any(reader.lstat(Path(sub.path) / "resolved_config.json") is not None for sub in os.scandir(item.path) if sub.is_dir(follow_symlinks=False)):
                    report.add("package.no-view", f"{reader.shown(Path(item.path))}/ holds a run of the engine's shared output path (resolved_config.json) and no {VIEW_FILE}: the adapter derives its view from tables of its own; a source package holds the engine's own view.", reader.shown(Path(item.path)), None)
        else:
            report.add("index.content", f"{root.name}/index.json: {said}", rel(root.name, "index.json"), "selected, packages")
        return
    chosen = set(arms)
    packages, would, revisions, cleans, snapshots = [], [], set(), set(), set()
    for arm in arms:
        folder = reader.locate(root, arm, file=rel(root.name, "index.json") if index is not None else root.name, field="selected" if index is not None else "a package's folder", want="dir")
        if folder is None:
            continue
        try:
            names = adapt_run.stated_files(root, arm, {})
        except adapt_run.Refused as refusal:
            report.add("index.content", f"{root.name}/index.json: {str(refusal.code).removeprefix('adapt_run: ')}", rel(root.name, "index.json"), "packages[].sidecar")
            continue
        fields = [f"index.json: {arm}'s sidecar" for _ in names]
        said = check_package(reader, arm, folder, names, root=root, experiment=arm_experiment(index), sidecar_fields=fields)
        packages.append(said)
        found = sidecars_found(reader, folder, set(names))
        for name, format_ in found:
            report.add("sidecar.unnamed", f"{reader.shown(folder / name)} is a {format_} that nothing names: a reader does not read it; a manifest names it in its package's sidecars, in the order the records are wanted.", reader.shown(folder / name), None)
        would.append({"arm": arm, "kind": VIEW_FORMAT, "path": arm, **({"sidecars": names or [name for name, _ in found]} if names or found else {})})
        engine = said.get("engine") or {}
        if engine.get("revision"):
            revisions.add(engine["revision"])
        if isinstance(engine.get("dirty"), bool):
            cleans.add(not engine["dirty"])
        record = run_record(reader, folder, say=False) or {}
        if record.get("snapshot"):
            snapshots.add(record["snapshot"])
        if not re.fullmatch(ID_PATTERN, arm):
            report.add("package.not-id", f"{reader.shown(folder)}/: its name ({arm}) is not an id, as a manifest's arm must be (lower-case letters and digits, joined by single dots or hyphens).", reader.shown(folder), None)
    result["packages"] = packages
    picks = []
    for item in folders:
        if item.name in chosen:
            continue
        folder = Path(item.path)
        if reader.lstat(folder / VIEW_FILE) is not None:
            report.add("package.not-listed", f"{reader.shown(folder)}/ holds a {VIEW_FILE} and is not one of the folder's packages ({'index.json does not choose it' if index is not None else 'its name is not a package'}): a reader leaves it aside.", reader.shown(folder), None)
        elif reader.lstat(folder / REFUSED_FILE) is not None:
            picks.append((item.name, folder))
    sweeps, rows = None, [{"arm": item["arm"], "id": run_id_of(arm_experiment(index), item["arm"])} for item in packages]
    if reader.lstat(root / "summary.json") is not None:
        sweeps = check_summary(reader, root / "summary.json", rel(root.name, "summary.json"), None, rows)
        result["summary"] = {"file": "summary.json", "sweeps": len(sweeps) if sweeps is not None else None}
    for arm, folder in picks:
        check_refused(reader, arm, folder, REFUSED_FILE, sweeps, None)
        result["refused"].append({"arm": arm, "file": REFUSED_FILE})
    if picks and (result["summary"] is None or (sweeps is not None and len(sweeps) != 1)):
        why = "the folder has no summary.json" if result["summary"] is None else f"its summary states {len(sweeps)} sweeps"
        report.add("refused.sweep", f"{root.name}/ holds {len(picks)} refused pick(s), which a reader places by the one sweep of the experiment's summary, and {why}.", root.name, None)
    named = index.get("experiment") if isinstance(index, dict) and isinstance(index.get("experiment"), str) else None
    if named is None and result["summary"]:
        summary = reader.json_file(root / "summary.json", JSON_LIMIT, file=rel(root.name, "summary.json"))
        named = summary.get("experiment") if isinstance(summary, dict) and isinstance(summary.get("experiment"), str) else None
    result["would_state"] = {
        "format": MANIFEST_FORMAT,
        "level": "source",
        "experiment": {"id": named if named and re.fullmatch(ID_PATTERN, named) else None, "title": None},
        **({"engine": {"revision": next(iter(revisions)), **({"snapshot": next(iter(snapshots))} if len(snapshots) == 1 else {}), **({"clean": next(iter(cleans))} if len(cleans) == 1 else {})}} if len(revisions) == 1 else {}),
        "visibility": None,
        "licence": None,
        **({"summary": "summary.json"} if result["summary"] else {}),
        "packages": would,
        **({"refused": [{"arm": arm, "file": REFUSED_FILE} for arm, _ in picks]} if picks else {}),
    }


def arm_experiment(index):
    """The experiment's id the adapter is called with: the index's own name where it gives one, else a stand-in."""
    named = index.get("experiment") if isinstance(index, dict) else None
    return named if isinstance(named, str) and re.fullmatch(ID_PATTERN, named) else "package"


def check_one_package(reader, result):
    """A folder that is itself one package (it holds view.json): read as the arm named as the folder, and nothing else
    of the folder around it is opened but what the adapter's own reading looks for there (its index.json and manifest)."""
    report, root = reader.report, reader.root
    arm = root.name
    around = [name for name in (MANIFEST_FILE, "index.json") if reader.lstat(root.parent / name) is not None]
    beside = f" The folder around it holds {' and '.join(around)}, which the adapter's own reading takes this package's sidecars from." if around else ""
    report.add("folder.one-package", f"{root.name}/ holds a {VIEW_FILE} itself: it is read as one package, the arm {arm}; a source package is the folder around its packages, with its manifest.{beside}", root.name, None)
    said = check_package(reader, arm, root, [], root=root.parent, experiment="package", sidecar_fields=[])
    result["packages"] = [said]
    found = sidecars_found(reader, root, set())
    for name, format_ in found:
        report.add("sidecar.unnamed", f"{arm}/{name} is a {format_} that nothing names: a reader does not read it; a manifest names it in its package's sidecars.", f"{arm}/{name}", None)
    engine = said.get("engine") or {}
    snapshot = (run_record(reader, root, say=False) or {}).get("snapshot")
    result["would_state"] = {
        "format": MANIFEST_FORMAT,
        "level": "source",
        "experiment": {"id": None, "title": None},
        **({"engine": {"revision": engine["revision"], **({"snapshot": snapshot} if snapshot else {}), **({"clean": not engine["dirty"]} if isinstance(engine.get("dirty"), bool) else {})}} if engine.get("revision") else {}),
        "visibility": None,
        "licence": None,
        "packages": [{"arm": arm, "kind": VIEW_FORMAT, "path": arm, **({"sidecars": [name for name, _ in found]} if found else {})}],
    }


# ---------------------------------------------------------------- the report


def text_of(result):
    lines = []
    head = f"{result['folder']}/: " + ("a source package with its manifest" if result["manifest"] else "no manifest")
    lines.append(head)
    experiment = result.get("experiment") or {}
    if experiment:
        lines.append(f"  experiment: {experiment.get('id')}" + (f" ({experiment['title']})" if experiment.get("title") else "") + (f"; group: {experiment['group']}" if experiment.get("group") else "") + (f"; status: {experiment['status']}" if experiment.get("status") else ""))
    if result["manifest"]:
        lines.append(f"  visibility: {result.get('visibility') or 'not given'}; licence: {result.get('licence') or 'not given'}")
    packages = result.get("packages") or []
    lines.append(f"  packages: {len(packages)}")
    for item in packages:
        bits = [item.get("kind") or "?"]
        if item.get("sidecars"):
            bits.append("sidecars " + ", ".join(item["sidecars"]))
        if item.get("read"):
            bits.append(f"{item.get('records')} records, {item.get('rows')} rows, {item.get('cells')} cells; the adapter reads it")
        else:
            bits.append("not read")
        lines.append(f"    {item['arm']}: " + "; ".join(bits))
    if result.get("refused"):
        lines.append(f"  refused picks: {len(result['refused'])} ({', '.join(item['arm'] for item in result['refused'])})")
    if result.get("summary"):
        lines.append(f"  summary: {result['summary']['file']}" + (f" ({result['summary']['sweeps']} sweep(s))" if result["summary"].get("sweeps") is not None else ""))
    if result["notes"]:
        lines.append(f"  notes: {len(result['notes'])}")
        lines += [f"    {item['code']}: {item['says']}" for item in result["notes"]]
    if result.get("would_state"):
        lines.append("  a manifest would state (null: the folder does not say):")
        lines += ["    " + line for line in json.dumps(result["would_state"], indent=1, ensure_ascii=False).splitlines()]
    if result["problems"]:
        lines.append(f"  problems: {len(result['problems'])}")
        lines += [f"    {item['code']}: {item['says']}" for item in result["problems"]]
        lines.append("not readable")
    else:
        lines.append("readable: no problem found")
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("folder", nargs="?", help="the run folder to check (read only)")
    parser.add_argument("--json", action="store_true", help="give the report as JSON")
    parser.add_argument("--schema", action="store_true", help="print the manifest's JSON schema, written from the field table")
    parser.add_argument("--codes", action="store_true", help="print every code with its kind and what it means")
    arguments = parser.parse_args(argv)
    if arguments.schema or arguments.codes:
        if arguments.folder or (arguments.schema and arguments.codes):
            parser.error("--schema and --codes take no folder, and one at a time")
        data = schema() if arguments.schema else {code: {"kind": kind, "says": says} for code, (kind, says) in CODES.items()}
        sys.stdout.write(json.dumps(data, indent=1, ensure_ascii=False) + "\n")
        return 0
    if not arguments.folder:
        parser.error("give the folder to check")
    folder = Path(arguments.folder)
    if not folder.is_dir():
        print("check_package: the folder given is not a folder", file=sys.stderr)
        return 2
    try:
        result = check(folder)
    except Exception as error:  # noqa: BLE001  a fault of this reader is said as a problem, never as a pass
        said = f"the check itself failed ({type(error).__name__}: {str(error)[:160]}): an error of this reader, to be reported with the folder."
        result = {"folder": folder.resolve().name, "manifest": None, "packages": [], "refused": [], "summary": None, "would_state": None, "notes": [], "problems": [{"code": "check.error", "file": folder.resolve().name, "field": None, "says": said}], "readable": False}
    sys.stdout.write((json.dumps(result, indent=1, ensure_ascii=False) if arguments.json else text_of(result)) + "\n")
    return 0 if result["readable"] else 1


if __name__ == "__main__":
    sys.exit(main())
