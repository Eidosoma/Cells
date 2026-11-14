"""Checkpoint continuity: one recorded admission per resume across a source change.

Design: docs/CHECKPOINT_CONTINUITY_DESIGN.md (its decision lands with this module; the number
is assigned at landing).

- **Refusal is the default.** io.load_snapshot and batch_io.load_batch_snapshot, called
  without ``continuity=``, run today's code and keep every refusal.
- **A Request** names one continuity record (``cells.checkpoint_continuity@1``) in the new
  run's folder, with the execution path and window policy the caller resumes with. The
  loaders then replace their two identity comparisons, of source and of runtime, by the
  record's binding (section 3.0). Nothing else is relaxed: the manifest's integrity, the
  definition and its fingerprint, the state checksum and validate_checkpoint run as before,
  so a changed definition, layout, solver or model ID still refuses (case 3; D146, D147).
- **A record binds** exactly one checkpoint manifest, one ``from`` identity (the manifest's)
  and one ``to`` identity (the running installation's). It is decided before the resumed run,
  out of process, by the continuity probe (validation/continuity/probe.py and admit.py). This
  module only parses and binds: it is host-only, imports neither JAX nor subprocess, and
  traces nothing.
- **The first landing** (section 13.1) decides the vector-windows path, for CPU definitions
  with ``jit: true``:
  - a request that declares another path cannot decide, and is refused;
  - every runtime change is refused (case 4 is parked); ``cells_version`` is a source field,
    because a change in it is a change of ``cells/__init__.py``, which the source admission
    covers;
  - GPU, ``jit: false`` and projective definitions are refused;
  - case 2 (a D148 record) is admitted only with the lead named as its admitter.
- **The run's provenance** names the record: a driver passes provenance(admission) to its
  writer, and validation/continuity/verify_run.py checks the run afterwards.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from cells.core.specs import ConfigError, digest, read_json

RECORD_KIND = "cells.checkpoint_continuity@1"
# Every execution path that takes checkpoints; a request declares one of them.
PATHS = ("runner", "windows", "batch", "batch_windows", "vector_windows")
DECIDED_PATHS = ("vector_windows",)  # The first landing. The others wait for the consolidation.
FORMATS = ("cells_complete_numerical_checkpoint", "cells_independent_world_checkpoint")
SCALAR = "scalar"  # The record's key for a scalar snapshot's one definition and clock.
SOURCE_CASES = ("identical_programs", "d148")
RECORDINGS = ("full", "observations", "checkpoints")
# Host-side runtime fields (section 3.1): the probe's B and H speak for the resuming run only
# under these, so the record keeps the probe's runtime and the loader checks them against to.
HOST_FIELDS = (
    "python",
    "packages.numpy",
    "packages.scipy",
    "packages.ml_dtypes",
    "packages.opt_einsum",
    "packages.jax",
    "platform",
    "machine",
)
RECORD_FIELDS = (
    "kind",
    "checkpoint",
    "from",
    "to",
    "changed_files",
    "probe",
    "source_admission",
    "runtime_admission",
    "scope",
    "lineage",
    "evidence",
    "residual",
    "admitted_by",
    "admitted_utc",
    "record_sha256",
)
_HEX = re.compile(r"[0-9a-f]{64}")
_DECISION = re.compile(r"D[0-9]+")


def field_class(name):
    """The class of one flattened runtime field (section 3.4), or None if unknown."""
    if name == "cells_version":
        return "source"
    if name in ("python", "platform", "packages.jax") or name in (
        "packages.numpy",
        "packages.scipy",
        "packages.ml_dtypes",
        "packages.opt_einsum",
    ):
        return "host"
    if name in ("packages.jaxlib", "numerical_environment.XLA_FLAGS", "gpu.platform_version"):
        return "compiler"
    if name == "gpu.packages" or name.startswith("gpu.packages."):
        return "compiler"
    if name == "numerical_environment.JAX_DISABLE_JIT":
        return "execution_mode"
    if name in ("machine", "gpu", "gpu.device_kind", "gpu.platform"):
        return "device"
    return None


def flatten(runtime, prefix=""):
    """A runtime identity as {dotted field: value}; nested objects become dotted names."""
    out = {}
    for key, value in runtime.items():
        name = f"{prefix}{key}"
        if isinstance(value, dict) and value:
            out.update(flatten(value, name + "."))
        else:
            out[name] = value
    return out


def differing_runtime_fields(a, b):
    """Flattened runtime fields that differ between two identities, cells_version included."""
    fa, fb = flatten(a), flatten(b)
    return sorted(k for k in set(fa) | set(fb) if fa.get(k, _MISSING) != fb.get(k, _MISSING))


def changed_files(a, b):
    """Files whose source hashes differ between two source_hashes maps (either side)."""
    return sorted(k for k in set(a) | set(b) if a.get(k) != b.get(k))


class _Missing:
    def __repr__(self):
        return "<absent>"


_MISSING = _Missing()


# ---------------------------------------------------------------- the record


def _fail(message):
    raise ConfigError("Continuity record: " + message)


def _object(value, fields, name):
    if not isinstance(value, dict) or set(value) != set(fields):
        found = sorted(value) if isinstance(value, dict) else type(value).__name__
        _fail(f"{name} must have exactly the fields {sorted(fields)}, not {found}")
    return value


def _text(value, name):
    if type(value) is not str or not value.strip():
        _fail(f"{name} must be a nonempty string")
    return value


def _optional_text(value, name):
    return None if value is None else _text(value, name)


def _hex(value, name):
    if type(value) is not str or not _HEX.fullmatch(value):
        _fail(f"{name} must be a SHA-256 hex digest")
    return value


def _count(value, name, minimum=0):
    if type(value) is not int or value < minimum:
        _fail(f"{name} must be an integer of at least {minimum}")
    return value


def _texts(value, name, *, nonempty=False, ordered=False):
    if not isinstance(value, list) or any(type(v) is not str or not v for v in value):
        _fail(f"{name} must be a list of nonempty strings")
    if nonempty and not value:
        _fail(f"{name} must not be empty")
    if ordered and (value != sorted(set(value))):
        _fail(f"{name} must be sorted and distinct")
    return value


def _policy(value, name):
    if not isinstance(value, Mapping) or set(value) != {"window_steps", "recording"}:
        raise ConfigError(f"{name} must be {{'window_steps', 'recording'}}")
    if type(value["window_steps"]) is not int or value["window_steps"] < 1:
        raise ConfigError(f"{name}: window_steps must be a positive integer")
    if value["recording"] not in RECORDINGS:
        raise ConfigError(f"{name}: recording must be one of {RECORDINGS}")
    return {"window_steps": value["window_steps"], "recording": value["recording"]}


def _clock(value, name):
    _object(value, ("time", "step_index", "event_index"), name)
    time = value["time"]
    if isinstance(time, bool) or not isinstance(time, (int, float)) or not math.isfinite(time):
        _fail(f"{name}.time must be a finite number")
    _count(value["step_index"], f"{name}.step_index")
    if type(value["event_index"]) is not int:
        _fail(f"{name}.event_index must be an integer")
    return value


def _runtime_entry(entry, index):
    name = f"runtime_admission.fields[{index}]"
    if not isinstance(entry, dict):
        _fail(f"{name} must be an object")
    field = _text(entry.get("field"), f"{name}.field")
    kind = field_class(field)
    if kind is None:
        _fail(f"{name}: unknown runtime field {field!r}")
    if kind == "source":
        _fail(f"{name}: {field} is a source field, covered by the source admission")
    if kind == "execution_mode":
        _fail(f"{name}: {field} changes the execution mode, which is refused")
    tolerance = kind in ("compiler", "device")
    fields = {"field", "class", "from", "to", "test", "evidence"}
    if tolerance:
        fields.add("variant")
    if tolerance and "variant" not in entry:
        _fail(f"{name}: a {kind} field is decided by tolerance and needs a registered variant")
    _object(entry, fields, name)
    if entry["class"] != kind:
        _fail(f"{name}: {field} is of class {kind}, not {entry['class']!r}")
    _text(entry["test"], f"{name}.test")
    _text(entry["evidence"], f"{name}.evidence")
    if tolerance:
        _text(entry["variant"], f"{name}.variant")
    return entry


def parse_record(value):
    """Verify one continuity record: kind, digest, admitter and the fields of each case.

    Returns the record unchanged. Raises ConfigError for a proposed (unadmitted) record, a
    tampered digest, or a missing or malformed field. Binding to a checkpoint and to the
    running installation is a separate step (bind).
    """
    if not isinstance(value, dict) or value.get("kind") != RECORD_KIND:
        _fail(f"kind must be {RECORD_KIND}")
    if value.get("admitted_by") is None:
        _fail("not admitted: admitted_by is missing (admit.py finalises a proposed record)")
    if set(value) != set(RECORD_FIELDS):
        _fail(
            f"fields: missing={sorted(set(RECORD_FIELDS) - set(value))}, "
            f"unknown={sorted(set(value) - set(RECORD_FIELDS))}"
        )
    body = {k: v for k, v in value.items() if k != "record_sha256"}
    if value["record_sha256"] != digest(body):
        _fail("record_sha256 does not match the record (changed after it was admitted)")
    checkpoint = _object(
        value["checkpoint"],
        ("format", "path", "manifest_sha256", "definitions", "clocks"),
        "checkpoint",
    )
    if checkpoint["format"] not in FORMATS:
        _fail(f"checkpoint.format must be one of {FORMATS}")
    _text(checkpoint["path"], "checkpoint.path")
    _hex(checkpoint["manifest_sha256"], "checkpoint.manifest_sha256")
    definitions, clocks = checkpoint["definitions"], checkpoint["clocks"]
    if not isinstance(definitions, dict) or not definitions:
        _fail("checkpoint.definitions must be a nonempty object")
    for key, fingerprint in definitions.items():
        _hex(fingerprint, f"checkpoint.definitions[{key!r}]")
    if not isinstance(clocks, dict) or set(clocks) != set(definitions):
        _fail("checkpoint.clocks must name the same checkpoints as checkpoint.definitions")
    for key, clock in clocks.items():
        _clock(clock, f"checkpoint.clocks[{key!r}]")
    if checkpoint["format"] == FORMATS[0] and set(definitions) != {SCALAR}:
        _fail(f"a scalar checkpoint's definitions and clocks are keyed {SCALAR!r}")
    identity = ("source_hashes_sha256", "tree", "git_revision", "dirty_diff", "runtime")
    source = _object(value["from"], (*identity, "tree_reproduces_manifest"), "from")
    target = _object(value["to"], identity, "to")
    for name, side in (("from", source), ("to", target)):
        _hex(side["source_hashes_sha256"], f"{name}.source_hashes_sha256")
        _text(side["tree"], f"{name}.tree")
        _optional_text(side["git_revision"], f"{name}.git_revision")
        _optional_text(side["dirty_diff"], f"{name}.dirty_diff")
        if not isinstance(side["runtime"], dict) or not side["runtime"]:
            _fail(f"{name}.runtime must be the runtime identity")
    if source["tree_reproduces_manifest"] is not True:
        _fail("the from tree must reproduce the manifest's source_hashes exactly")
    _texts(value["changed_files"], "changed_files", ordered=True)
    probe = _object(value["probe"], ("runtime", "host_fields_equal_to_runtime"), "probe")
    if not isinstance(probe["runtime"], dict) or not probe["runtime"]:
        _fail("probe.runtime must be the probe processes' runtime identity")
    if probe["host_fields_equal_to_runtime"] is not True:
        _fail("probe.host_fields_equal_to_runtime must be true (rerun the probe otherwise)")
    admission = value["source_admission"]
    case = admission.get("case") if isinstance(admission, dict) else None
    if case not in SOURCE_CASES:
        _fail(f"source_admission.case must be one of {SOURCE_CASES}")
    if case == "identical_programs":
        _object(admission, ("case",), "source_admission")
    else:
        _object(
            admission,
            ("case", "decision", "before", "after", "guard", "ledger_fields_across_seam"),
            "source_admission (d148)",
        )
        if type(admission["decision"]) is not str or not _DECISION.fullmatch(admission["decision"]):
            _fail("source_admission.decision must name a decision, such as D148")
        for key in ("before", "after", "guard"):
            _text(admission[key], f"source_admission.{key}")
        _texts(admission["ledger_fields_across_seam"], "source_admission.ledger_fields_across_seam")
    runtime = _object(value["runtime_admission"], ("case", "fields"), "runtime_admission")
    if runtime["case"] == "none":
        if runtime["fields"] != []:
            _fail("runtime_admission 'none' names no fields")
    elif runtime["case"] == "fields":
        if not isinstance(runtime["fields"], list) or not runtime["fields"]:
            _fail("runtime_admission 'fields' names at least one field")
        for index, entry in enumerate(runtime["fields"]):
            _runtime_entry(entry, index)
        names = [entry["field"] for entry in runtime["fields"]]
        if len(set(names)) != len(names):
            _fail("runtime_admission names a field twice")
    else:
        _fail("runtime_admission.case must be 'none' or 'fields'")
    scope = _object(
        value["scope"], ("paths", "policy", "horizon_rounds", "overlap_rounds"), "scope"
    )
    paths = scope["paths"]
    if not isinstance(paths, list) or not paths or len(set(paths)) != len(paths):
        _fail("scope.paths must be a nonempty list of distinct paths")
    if any(p not in PATHS for p in paths):
        _fail(f"scope.paths must name paths of {PATHS}")
    try:
        _policy(scope["policy"], "scope.policy")
    except ConfigError as exc:
        _fail(str(exc))
    horizon = _count(scope["horizon_rounds"], "scope.horizon_rounds")
    overlap = _count(scope["overlap_rounds"], "scope.overlap_rounds")
    if overlap > horizon:
        _fail("scope.overlap_rounds cannot exceed scope.horizon_rounds")
    if case == "identical_programs" and overlap < min(2, horizon):
        _fail("case 1 needs an overlap of at least two rounds, or the whole remaining horizon")
    if not isinstance(value["lineage"], list):
        _fail("lineage must be a list")
    for index, link in enumerate(value["lineage"]):
        _object(link, ("record", "record_sha256"), f"lineage[{index}]")
        _text(link["record"], f"lineage[{index}].record")
        _hex(link["record_sha256"], f"lineage[{index}].record_sha256")
    if not isinstance(value["evidence"], list) or not value["evidence"]:
        _fail("evidence must be a nonempty list")
    for index, item in enumerate(value["evidence"]):
        _object(item, ("role", "path", "sha256"), f"evidence[{index}]")
        _text(item["role"], f"evidence[{index}].role")
        _text(item["path"], f"evidence[{index}].path")
        _hex(item["sha256"], f"evidence[{index}].sha256")
    _texts(value["residual"], "residual")
    admitted = _object(value["admitted_by"], ("name", "role"), "admitted_by")
    _text(admitted["name"], "admitted_by.name")
    _text(admitted["role"], "admitted_by.role")
    if case == "d148" and admitted["role"] != "lead":
        _fail("case 2 (a D148 record) is admitted by the lead")
    _text(value["admitted_utc"], "admitted_utc")
    return value


def seal(record):
    """The record with its record_sha256: cells.core.specs.digest of the rest (section 5)."""
    body = {k: v for k, v in record.items() if k != "record_sha256"}
    return {**body, "record_sha256": digest(body)}


# ---------------------------------------------------------------- requests and admissions


@dataclass(frozen=True)
class Request:
    """One resume: the continuity record, and the path and window policy it resumes with.

    record   the record file in the new run's folder (read and verified at load)
    path     the execution path the caller will resume with (one of PATHS)
    policy   its window policy, {"window_steps", "recording"} (or a WindowPolicy)

    The loaders refuse a request whose record does not cover the declared path and policy.
    validation/continuity/verify_run.py checks the run afterwards against the same scope.
    """

    record: Any
    path: str
    policy: Any

    def __post_init__(self):
        if not isinstance(self.record, (str, Path)) or not str(self.record):
            raise ConfigError("A continuity request names its record file")
        if self.path not in PATHS:
            raise ConfigError(f"Unknown execution path {self.path!r}; expected one of {PATHS}")
        policy = self.policy.to_dict() if hasattr(self.policy, "to_dict") else self.policy
        object.__setattr__(self, "record", Path(self.record).absolute())
        object.__setattr__(self, "policy", _policy(policy, "Declared window policy"))


@dataclass(frozen=True)
class Admission:
    """A load that a continuity record admitted; drivers pass provenance(admission) on."""

    record: str  # The record file (absolute path).
    record_sha256: str
    case: str  # The record's source_admission case.
    path: str  # The declared execution path.
    policy: Mapping  # The declared window policy.
    checkpoint_manifest_sha256: str  # The admitted manifest (a cohort's, for a cohort).


def provenance(admission):
    """The run manifest's provenance for an admitted resume (section 6)."""
    if type(admission) is not Admission:
        raise ConfigError("provenance() takes the Admission of a loaded snapshot")
    return {
        "operation": "admitted_resume",
        "continuity_record": admission.record,
        "record_sha256": admission.record_sha256,
        "source_admission": admission.case,
        "declared_path": admission.path,
        "declared_policy": dict(admission.policy),
        "parent_checkpoint_sha256": admission.checkpoint_manifest_sha256,
    }


@dataclass(frozen=True)
class _Child:
    """One child of a cohort whose manifest a record admitted (batch_io only)."""

    binding: _Binding
    key: str  # The child's world ID, as the record keys it.


class _Binding:
    """A record's binding of one manifest: its source first, then its runtime and definitions.

    bind() builds it for a Request (a scalar or a cohort manifest), or for one child of an
    admitted cohort: batch_io passes binding.child(world_id) to load_snapshot for each child,
    which is then bound to its cohort's identity, the record's from, instead of this
    installation's. The cohort writer guarantees that children and cohort share one identity.
    """

    def __init__(self, record, admission, key, is_child=False):
        self.record, self.key, self.is_child = record, key, is_child
        self._admission, self._admitted = admission, False

    def require(self, runtime, current_runtime, definitions, clocks):
        """The runtime binding and the first landing's definition rules (section 3.0).

        runtime is the manifest's runtime identity and current_runtime the running
        installation's. definitions maps the record's keys to the parsed definitions
        ({binding.key: spec} for a scalar manifest or a child), and clocks to the manifest
        clocks (None for a cohort manifest, whose children carry them). Returns the Admission.
        """
        checkpoint = self.record["checkpoint"]
        if self.is_child:
            if runtime != self.record["from"]["runtime"]:
                raise ConfigError("Batch checkpoint child runtime differs from its admitted cohort")
            expected = {k: checkpoint["definitions"].get(k) for k in definitions}
        else:
            _require_runtime(self.record, runtime, current_runtime)
            expected = checkpoint["definitions"]
        if {k: spec.fingerprint for k, spec in definitions.items()} != expected:
            raise ConfigError("Continuity record's definitions are not the checkpoint's")
        for key, spec in definitions.items():
            _require_definition(key, spec)
        for key, clock in (clocks or {}).items():
            if checkpoint["clocks"].get(key) != clock:
                raise ConfigError(f"Continuity record's clock of {key} is not the checkpoint's")
        self._admitted = True
        return self._admission

    def child(self, world_id):
        """The binding of one child of this admitted cohort manifest."""
        if self.key is not None or self.is_child or not self._admitted:
            raise ConfigError("Only an admitted cohort binding has children")
        return _Child(self, str(world_id))


def bind(continuity, *, kind, fingerprint, sources, current_sources):
    """The record's source binding of one checkpoint manifest (section 3.0, step 2).

    continuity is a Request, or a child of an admitted cohort (_Binding.child). kind and
    fingerprint are the manifest's kind and manifest_sha256, sources its source_hashes map,
    and current_sources the running installation's. Returns the binding; its require()
    binds the runtime and the definitions.
    """
    if type(continuity) is _Child:
        cohort = continuity.binding
        if kind != FORMATS[0]:
            raise ConfigError("A cohort child is a complete scalar checkpoint")
        if digest(sources) != cohort.record["from"]["source_hashes_sha256"]:
            raise ConfigError("Batch checkpoint child source differs from its admitted cohort")
        return _Binding(cohort.record, cohort._admission, continuity.key, True)
    if type(continuity) is not Request:
        raise ConfigError("continuity must be a cells.continuity.Request (or None)")
    try:
        raw = read_json(continuity.record)
    except OSError as exc:
        raise ConfigError(f"Cannot read the continuity record {continuity.record}: {exc}") from exc
    record = parse_record(raw)
    scope, checkpoint = record["scope"], record["checkpoint"]
    if continuity.path not in DECIDED_PATHS:
        raise ConfigError(
            f"Continuity cannot decide the {continuity.path} path: the first landing decides "
            "vector windows only (docs/CHECKPOINT_CONTINUITY_DESIGN.md, section 13.1)"
        )
    if continuity.path not in scope["paths"]:
        raise ConfigError(f"Continuity record's scope does not cover the path {continuity.path}")
    if continuity.policy != scope["policy"]:
        raise ConfigError(
            f"Continuity record's scope does not cover the window policy {continuity.policy}"
        )
    if checkpoint["format"] != kind:
        raise ConfigError(f"Continuity record binds a {checkpoint['format']}, not a {kind}")
    if checkpoint["manifest_sha256"] != fingerprint:
        raise ConfigError("Continuity record binds another checkpoint manifest")
    if digest(sources) != record["from"]["source_hashes_sha256"]:
        raise ConfigError("Continuity record's from source is not the checkpoint's")
    if digest(current_sources) != record["to"]["source_hashes_sha256"]:
        raise ConfigError("Continuity record's to source is not this installation's")
    if record["changed_files"] != changed_files(sources, current_sources):
        raise ConfigError("Continuity record's changed_files are not the files that differ")
    admission = Admission(
        str(continuity.record),
        record["record_sha256"],
        record["source_admission"]["case"],
        continuity.path,
        dict(continuity.policy),
        fingerprint,
    )
    return _Binding(record, admission, SCALAR if kind == FORMATS[0] else None)


def _require_runtime(record, runtime, current_runtime):
    if runtime != record["from"]["runtime"]:
        raise ConfigError("Continuity record's from runtime is not the checkpoint's")
    if current_runtime != record["to"]["runtime"]:
        raise ConfigError("Continuity record's to runtime is not this installation's")
    before, after = flatten(runtime), flatten(current_runtime)
    differing = set(differing_runtime_fields(runtime, current_runtime)) - {"cells_version"}
    entries = record["runtime_admission"]["fields"]
    named = {entry["field"] for entry in entries}
    if named != differing:
        raise ConfigError(
            "Continuity record must name exactly the differing runtime fields: "
            f"unnamed {sorted(differing - named)}, extra {sorted(named - differing)}"
        )
    for entry in entries:
        field = entry["field"]
        if entry["from"] != before.get(field) or entry["to"] != after.get(field):
            raise ConfigError(f"Continuity record misstates the runtime field {field}")
    if differing:
        raise ConfigError(
            "Runtime changes are parked: the first landing refuses every runtime change "
            f"({sorted(differing)})"
        )
    if after.get("numerical_environment.JAX_DISABLE_JIT") is not None:
        raise ConfigError("JAX_DISABLE_JIT is set: execution without JIT is refused")
    probe = flatten(record["probe"]["runtime"])
    moved = [f for f in HOST_FIELDS if probe.get(f, _MISSING) != after.get(f, _MISSING)]
    if moved:
        raise ConfigError(
            f"The probe's host-side runtime differs from the resuming runtime ({moved}); "
            "rerun the probe under the resuming runtime"
        )


def _require_definition(key, spec):
    if spec.execution.backend != "cpu":
        raise ConfigError(
            f"Definition {key}: GPU definitions are not yet admitted (first landing; "
            "docs/CHECKPOINT_CONTINUITY_DESIGN.md, section 13.4)"
        )
    if spec.execution.jit is not True:
        raise ConfigError(
            f"Definition {key}: jit: false definitions are refused; they execute eagerly, "
            "with no compiled program to compare"
        )
    if getattr(spec, "projective", None) is not None:
        raise ConfigError(f"Definition {key}: projective definitions are refused")
