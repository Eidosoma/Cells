"""Bounded, reference-aware failure retention for the four-call diagnostic.

Only the injected existing writer handles numerical data. This module neither
imports numerical code nor reconstructs owners from evidence.
"""

import json
import os
import re
import stat
from pathlib import Path

UNSET = object()
JSON_LIMIT = 16 * 2**20
ARCHIVE_LIMIT = 64 * 2**20
MAX_FAILURES = 2  # One outer handler, with a bounded repeated-handler safeguard.
MAX_PARTIALS = 4 * 3  # Four declared calls across original/Decimal100/Decimal160.
STAGES = (
    "primitive-begin",
    *(f"primitive-{kind}-{i}" for i in range(4) for kind in ("drive", "step")),
    "legacy-binding",
    "legacy-initial",
    *(f"legacy-{kind}-{i}" for i in range(3) for kind in ("drive", "step")),
    "original-four",
    "Decimal-raw-1",
    "Decimal-raw-2",
    "Decimal100",
    "Decimal160",
    "comparison",
    "comparison-final",
)
AVAILABLE = (
    "inputs",
    "primitive",
    "legacy",
    "native",
    "Decimal100",
    "Decimal160",
    "last_returned",
    "failed_primitive",
    "source_exception_owned_fields",
)
PRIMITIVE_FIELDS = (
    "kind",
    "domain",
    "binding",
    "current",
    "original_definition",
    "original_initial",
    "original_input_fingerprint",
    "journal",
    "attempts",
    "work",
    "failure",
    "failed_trial",
    "recovery_errors",
    "failed",
    "standalone_only",
    "source_input_native_derivation_attested",
    "extended_checkpoint_or_coupled_admission",
    "scientific_acceptance",
)
PROVENANCE = (
    "packet",
    "source_snapshot",
    "source_plan",
    "program",
    "producer",
    "reference_source",
    "reference_protocol",
    "release",
)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def _type(value):
    kind = type(value)
    return {
        name.strip("_"): type.__dict__[name].__get__(kind)
        for name in ("__module__", "__qualname__")
    }


def _digest(value):
    require(type(value) is str and re.fullmatch("[0-9a-f]{64}", value), "Invalid evidence digest")
    return value


def _pairs(rows):
    result = {}
    for key, value in rows:
        require(key not in result, "Duplicate evidence JSON key")
        result[key] = value
    return result


def _keys(value, allowed, *, exact=False):
    return (
        type(value) is dict
        and all(type(key) is str for key in value)
        and (set(value) == set(allowed) if exact else set(value) <= set(allowed))
    )


def _write(path, value):
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    require(len(raw) + 1 <= JSON_LIMIT, "Failure metadata JSON bound")
    with path.open("xb") as stream:
        stream.write(raw + b"\n")
        stream.flush()
        os.fsync(stream.fileno())
    directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(directory)
    finally:
        os.close(directory)


def _roles(stage):
    result = {"payload": ()}
    if stage.startswith("Decimal-raw-"):
        result["exact"] = ("exact",)
    elif stage != "comparison-final":
        result["returned"] = ("returned",)
        if stage.startswith("primitive-step-"):
            result.update(state=("returned", 0), trial=("returned", 1))
    return result


def _select(value, path):
    for key in path:
        if type(key) is str:
            require(type(value) is dict and key in value, "Missing declared evidence selector")
        else:
            require(type(value) in (tuple, list) and key < len(value), "Invalid evidence selector")
        value = value[key]
    return value


class Journal:
    """Own successful archive writes; retain failures without replacing their cause.

    ``fingerprint`` must be the existing evidence-compatible fingerprint, not
    an owner codec that rejects supported observational array views. Selector
    references require both object identity and an unchanged fingerprint.
    """

    def __init__(self, directory, *, archive, ref, exception_record, fingerprint, provenance=None):
        self.root = Path(directory).absolute()
        require(self.root == self.root.resolve(strict=True), "Unlinked existing output required")
        require(self.root.is_dir(), "Evidence output must be a directory")
        self.archive, self.ref = archive, ref
        self.exception_record, self.fingerprint = exception_record, fingerprint
        require(
            all(callable(f) for f in (archive, ref, exception_record, fingerprint)),
            "Evidence callbacks required",
        )
        provenance = {} if provenance is None else provenance
        require(_keys(provenance, PROVENANCE), "Closed provenance roles required")
        self.provenance = {}
        for role, pin in provenance.items():
            require(
                type(pin) is dict and set(pin) == {"path", "sha256"},
                "Exact provenance pin required",
            )
            actual = self._pin(Path(pin["path"]), JSON_LIMIT)
            require(actual["sha256"] == _digest(pin["sha256"]), "Changed provenance input")
            self.provenance[role] = actual
        self.completed = {}
        self.sections = []
        self.failures = 0
        self.journal = self.root / "completed-stages.jsonl"
        with self.journal.open("xb") as stream:
            stream.flush()
            os.fsync(stream.fileno())

    def _pin(self, path, limit):
        require(
            path.is_absolute() and path == path.resolve(strict=True),
            "Unlinked absolute evidence path required",
        )
        before = path.stat()
        require(
            stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and before.st_size <= limit,
            "Evidence file type/size bound",
        )
        pin = self.ref(path)
        after = path.stat()
        require(
            (before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns)
            == (after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns),
            "Evidence file changed while hashing",
        )
        require(
            type(pin) is dict and set(pin) == {"path", "sha256"} and pin["path"] == str(path),
            "Wrong evidence reference path",
        )
        return dict(path=str(path), sha256=_digest(pin["sha256"]), bytes=before.st_size)

    def _archive_pin(self, directory):
        require(
            directory.is_relative_to(self.root) and directory == directory.resolve(strict=True),
            "Foreign or linked archive",
        )
        manifest = self._pin(directory / "manifest.json", JSON_LIMIT)
        row = json.loads(
            (directory / "manifest.json").read_bytes(),
            object_pairs_hook=_pairs,
            parse_constant=lambda value: require(False, "Nonstandard evidence JSON"),
        )
        require(
            type(row) is dict
            and set(row)
            == {
                "kind",
                "fingerprint",
                "files",
                "owner_admission",
                "live_array_aliases_reconstructed",
            },
            "Closed completed archive manifest required",
        )
        require(
            row["kind"] == "cells.material_four_call_evidence@2"
            and row["owner_admission"] is False
            and row["live_array_aliases_reconstructed"] is False,
            "Observational archive required",
        )
        require(
            type(row["files"]) is dict and set(row["files"]) == {"state.json", "arrays.npz"},
            "Complete archive pair required",
        )
        files = {}
        for name, cap in (("state.json", JSON_LIMIT), ("arrays.npz", ARCHIVE_LIMIT)):
            declared = row["files"][name]
            require(
                type(declared) is dict and set(declared) == {"path", "sha256"},
                "Exact completed file pin required",
            )
            files[name] = self._pin(directory / name, cap)
            require(
                declared == {key: files[name][key] for key in ("path", "sha256")},
                "Changed completed archive file",
            )
        require(
            self._pin(directory / "manifest.json", JSON_LIMIT) == manifest,
            "Changed archive manifest",
        )
        return dict(manifest=manifest, fingerprint=_digest(row["fingerprint"]), files=files)

    def save(self, stage, payload, *, selectors=None):
        require(
            type(stage) is str and stage in STAGES and stage not in self.completed,
            "Unknown or repeated completed stage",
        )
        selectors = {} if selectors is None else selectors
        paths = _roles(stage)
        require(_keys(selectors, paths), "Unknown stage selector role")
        selected = []
        for role, value in selectors.items():
            require(
                _select(payload, paths[role]) is value, "Selector is not the exact saved object"
            )
            selected.append((role, value, _digest(self.fingerprint(value))))
        payload_fingerprint = _digest(self.fingerprint(payload))
        directory = self.root / stage
        self.archive(directory, payload)
        pin = self._archive_pin(directory)
        require(pin["fingerprint"] == payload_fingerprint, "Archive does not match current payload")
        for _, value, fingerprint in selected:
            require(
                _digest(self.fingerprint(value)) == fingerprint,
                "Selected object changed during archival",
            )
        row = dict(
            stage=stage,
            archive=pin,
            selectors={
                role: dict(path=list(paths[role]), fingerprint=fp) for role, _, fp in selected
            },
        )
        raw = (
            json.dumps(row, sort_keys=True, separators=(",", ":"), allow_nan=False).encode() + b"\n"
        )
        require(len(raw) <= JSON_LIMIT, "Stage journal record bound")
        with self.journal.open("ab") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        self.completed[stage] = (row, selected)
        return directory

    def _reference(self, value, valid_stages):
        for stage, (row, selected) in self.completed.items():
            if stage not in valid_stages:
                continue
            for role, original, fingerprint in selected:
                if original is value and _digest(self.fingerprint(value)) == fingerprint:
                    return dict(
                        stage=stage,
                        role=role,
                        selector=row["selectors"][role],
                        archive=row["archive"],
                    )
        for original, fingerprint, row in self.sections:
            if original is value and _digest(self.fingerprint(value)) == fingerprint:
                require(
                    self._archive_pin(Path(row["archive"]["manifest"]["path"]).parent)
                    == row["archive"],
                    "Changed prior failure section",
                )
                return dict(failure_section=row["section"], archive=row["archive"])
        return None

    def retain(
        self,
        primary,
        *,
        stage,
        available,
        source_partials=(),
        capture_errors=(),
        evidence_errors=(),
        current_primitive=UNSET,
        raw_returned=UNSET,
    ):
        """Best-effort complete index; all secondary failures annotate ``primary``.

        Fixed named sections obey the original writer's per-archive limits.
        Failure of one section never prevents attempting the others.
        """
        require(isinstance(primary, BaseException), "Primary exception required")
        errors, sections, registered, valid = [], [], [], set()

        def failed(where, error):
            row = dict(where=where, type=_type(error))
            errors.append(row)
            BaseException.add_note(
                primary,
                "Failure evidence incomplete at "
                + where
                + ": "
                + json.dumps(row["type"], sort_keys=True),
            )

        index = dict(
            kind="cells.material_failure_sections@1",
            stage=stage,
            complete=False,
            primary_written=False,
            sections=sections,
            completed_stages=registered,
            errors=errors,
            scientific_acceptance=False,
            owner_admission=False,
            provenance=self.provenance,
        )
        try:
            require(type(stage) is str and stage in (*STAGES, "failure"), "Unknown failure stage")
            require(self.failures < MAX_FAILURES, "Failure handler count bound")
            number = self.failures
            self.failures += 1
            directory = self.root / ("failure" if number == 0 else "failure-repeat")
            directory.mkdir(parents=True, exist_ok=False)
        except BaseException as error:
            failed("failure-directory", error)
            return index
        # Publish the original exception before fingerprinting or archiving data.
        try:
            _write(
                directory / "primary.json",
                dict(stage=stage, primary=self.exception_record(primary), complete_capture=False),
            )
            index["primary_written"] = True
            index["primary"] = self._pin(directory / "primary.json", JSON_LIMIT)
        except BaseException as error:
            failed("primary-metadata", error)
            try:
                cause = BaseException.__dict__["__cause__"].__get__(primary)
                _write(
                    directory / "primary-minimal.json",
                    dict(
                        stage=stage,
                        primary_type=_type(primary),
                        cause_type=None if cause is None else _type(cause),
                        complete_exception_record=False,
                        complete_capture=False,
                    ),
                )
            except BaseException as secondary:
                failed("primary-minimal-metadata", secondary)
        for role, pin in self.provenance.items():
            try:
                require(
                    self._pin(Path(pin["path"]), JSON_LIMIT) == pin, "Changed failure provenance"
                )
            except BaseException as error:
                failed("provenance-" + role, error)
        for name, (row, _) in self.completed.items():
            try:
                require(
                    self._archive_pin(self.root / name) == row["archive"],
                    "Changed registered archive",
                )
                valid.add(name)
                registered.append(dict(status="verified", **row))
            except BaseException as error:
                registered.append(dict(stage=name, status="refused", expected=row["archive"]))
                failed("completed-" + name, error)

        def section(role, value):
            entry = dict(section=role, status="incomplete")
            sections.append(entry)
            try:
                reference = self._reference(value, valid)
                if reference is not None:
                    entry.update(status="reference", reference=reference)
                    return
            except BaseException as error:
                failed(role + "-reference", error)
            fingerprint, payload_fingerprint = UNSET, UNSET
            payload = dict(section=role, value=value)
            try:
                fingerprint = _digest(self.fingerprint(value))
                payload_fingerprint = _digest(self.fingerprint(payload))
            except BaseException as error:
                # Still attempt the existing writer: its refusal sidecar may
                # identify raw storage that the fingerprint could not encode.
                failed(role + "-fingerprint", error)
            try:
                destination = directory / role
                self.archive(destination, payload)
                pin = self._archive_pin(destination)
                if payload_fingerprint is not UNSET:
                    require(
                        pin["fingerprint"] == payload_fingerprint,
                        "Failure archive does not match current payload",
                    )
                if fingerprint is not UNSET:
                    require(
                        _digest(self.fingerprint(value)) == fingerprint,
                        "Failure section changed while archiving",
                    )
                entry.update(status="saved", archive=pin)
                if fingerprint is not UNSET:
                    self.sections.append(
                        (
                            value,
                            fingerprint,
                            dict(section=str(destination.relative_to(self.root)), archive=pin),
                        )
                    )
            except BaseException as error:
                failed(role, error)

        def primitive_sections(prefix, value):
            if value is None:
                section(prefix, value)
                return
            if not _keys(value, PRIMITIVE_FIELDS, exact=True):
                failed(
                    prefix + "-schema",
                    ValueError("Complete current primitive evidence fields required"),
                )
                section(prefix, value)
                return
            for key in PRIMITIVE_FIELDS:
                # Never replace an evolving primitive aggregate with an old snapshot.
                section(prefix + "-" + key, value[key])

        if not _keys(available, AVAILABLE):
            failed("available-schema", ValueError("Closed available evidence keys required"))
        if type(available) is dict:
            for key in AVAILABLE:
                if key not in available:
                    continue
                value = available[key]
                if key == "primitive":
                    if current_primitive is UNSET:
                        failed(
                            "current-primitive",
                            ValueError("Fresh current primitive evidence required"),
                        )
                    else:
                        value = current_primitive
                    primitive_sections("primitive", value)
                elif key == "failed_primitive":
                    primitive_sections("failed-primitive", value)
                elif key == "legacy" and type(value) in (tuple, list) and len(value) <= 3:
                    for i, item in enumerate(value):
                        section("legacy-" + str(i), item)
                else:
                    if key == "legacy":
                        failed("legacy-count", ValueError("Three legacy stages maximum"))
                    section("available-" + key, value)
        if current_primitive is not UNSET and (
            type(available) is not dict or "primitive" not in available
        ):
            primitive_sections("primitive", current_primitive)
        if raw_returned is not UNSET:
            section("raw-returned", raw_returned)
        if type(source_partials) not in (list, tuple) or len(source_partials) > MAX_PARTIALS:
            failed("source-partials-count", ValueError("Declared provider partial bound exceeded"))
        else:
            for i, value in enumerate(source_partials):
                section("source-partial-" + str(i), value)
        section("capture-errors", capture_errors)
        section("evidence-errors", evidence_errors)
        for role, value in (("capture", capture_errors), ("evidence", evidence_errors)):
            if type(value) not in (list, tuple):
                failed(role + "-errors-schema", ValueError("Error sequence required"))
                index["upstream_" + role + "_errors"] = True
            else:
                index["upstream_" + role + "_errors"] = len(value) != 0
        index["complete"] = (
            index["primary_written"]
            and not errors
            and not index["upstream_capture_errors"]
            and not index["upstream_evidence_errors"]
        )
        try:
            _write(directory / "index.json", index)
        except BaseException as error:
            failed("index-publication", error)
            index["complete"] = False
        return index
