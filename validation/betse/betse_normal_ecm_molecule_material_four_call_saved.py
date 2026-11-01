"""Released postprocessing of complete, pinned four-call evidence only.

No constructor, source step, native adapter, Decimal provider or RNG is called.
Decoded records are observations, never restored live execution authority.
"""

import argparse
import builtins
import json
import os
import sys
from contextlib import contextmanager
from pathlib import Path

from validation import source_snapshot as snapshot
from validation.betse import betse_normal_ecm_molecule_material_four_call as q

FILE = "validation/betse/betse_normal_ecm_molecule_material_four_call_saved.py"
TEST = "tests/unit/test_betse_normal_ecm_molecule_material_four_call_saved.py"
KIND = "cells.material_four_call_saved_assessment@1"
RELEASE = "CELLS_MATERIAL_FOUR_CALL_SAVED_RELEASED"
STAGES = (
    "primitive-begin",
    *(name for i in range(4) for name in (f"primitive-drive-{i}", f"primitive-step-{i}")),
    "legacy-binding",
    "legacy-initial",
    *(name for i in range(3) for name in (f"legacy-drive-{i}", f"legacy-step-{i}")),
    "original-four",
    "Decimal-raw-1",
    "Decimal100",
    "Decimal-raw-2",
    "Decimal160",
)
ORIGIN_FILES = (
    "packet-01/inputs.json",
    "packet-01/source-plan.json",
    "qualification-01/work.json",
    "qualification-01/runtime.json",
    "qualification-01/invocations.jsonl",
    "terminal.json",
    "process/failure.json",
    "process/stderr.log",
    "release.json",
)
require = q.require


def _path(value, *, exists=True):
    path = Path(value).absolute()
    require(".." not in path.parts, "Noncanonical evidence path")
    require(not any(p.is_symlink() for p in (path, *path.parents)), "Linked evidence path")
    return path.resolve(strict=exists)


def _read(path):
    path = _path(path)
    return q.primitive.codec.parse_json(
        q.primitive_validation.checkpoint._read(path, q.primitive.codec.DEFAULT_LIMITS.json_bytes),
        q.primitive.codec.DEFAULT_LIMITS,
    )


def _pin(path):
    path = _path(path)
    require(path.is_file(), "Missing regular evidence file")
    return dict(path=str(path), sha256=snapshot.digest(path), bytes=path.stat().st_size)


def _verify_pin(row):
    require(type(row) is dict and set(row) == {"path", "sha256", "bytes"}, "File pin schema")
    require(type(row["bytes"]) is int and row["bytes"] >= 0, "File size pin")
    require(_pin(row["path"]) == row, "Changed pinned evidence: " + str(row["path"]))
    return Path(row["path"])


def _archive_pin(directory):
    directory = _path(directory)
    manifest = _read(directory / "manifest.json")
    require(
        manifest.get("kind") == "cells.material_four_call_evidence@2"
        and manifest.get("owner_admission") is False
        and manifest.get("live_array_aliases_reconstructed") is False
        and set(manifest.get("files", {})) == {"state.json", "arrays.npz"},
        "Complete data-only archive required",
    )
    files = {name: _pin(directory / name) for name in ("state.json", "arrays.npz")}
    for name, row in files.items():
        require(
            manifest["files"][name] == {k: row[k] for k in ("path", "sha256")},
            "Archive manifest/file mismatch",
        )
    return dict(manifest=_pin(directory / "manifest.json"), files=files)


def _runtime_files(runtime):
    loaded = runtime["loaded"]
    result = {}
    for row in loaded["loaded_files"].values():
        p = _pin(row["path"])
        require(p["sha256"] == row["sha256"], "Original runtime producer drift")
        result[p["path"]] = p
    for row in (runtime["child"]["executable"], loaded["executable"]):
        p = _pin(row["path"])
        require(p["sha256"] == row["sha256"], "Original executable drift")
        result[p["path"]] = p
    return result


def origin_inputs(origin, *, origin_review, origin_review_sha256):
    """Authenticate saved metadata and every archive before any data decoding."""
    origin, review_path = _path(origin), _path(origin_review)
    require(snapshot.digest(review_path) == origin_review_sha256, "Wrong original review")
    review = _read(review_path)
    require(
        review.get("scientific_acceptance") is False
        and review.get("complete_archives", {}).get("output_archive_count") == 22
        and review["complete_archives"].get("program_archive_count") == 1,
        "Explicit reviewed failed four-call evidence required",
    )
    files = {name: _pin(origin / name) for name in ORIGIN_FILES}
    associations = {
        "packet-01/inputs.json": review["source"]["packet"],
        "packet-01/source-plan.json": review["source"]["source_plan"],
        "qualification-01/work.json": review["work"]["receipt"],
        "qualification-01/runtime.json": review["runtime"]["receipt"],
        "qualification-01/invocations.jsonl": review["work"]["invocations"],
        "process/failure.json": review["process_failure"],
        "process/stderr.log": review["stderr"],
        "release.json": review["release"],
    }
    for name, row in associations.items():
        require(
            row == {k: files[name][k] for k in ("path", "sha256")},
            "Review file association differs: " + name,
        )
    terminal = _read(origin / "terminal.json")
    require(terminal.get("status") == "failed", "Original source outcome must remain failed")
    require(
        review["terminal"]["path"] == str(origin / "terminal.json")
        and review["terminal"]["sha256"] == files["terminal.json"]["sha256"],
        "Review belongs to another source outcome",
    )
    packet = _read(origin / "packet-01/inputs.json")
    require(
        packet.get("kind") == q.KIND
        and packet.get("held") is True
        and packet.get("automatic_launch") is False,
        "Original four-call packet schema",
    )
    old_source = origin / "packet-01/source"
    manifest = snapshot.verify(old_source, manifest_sha256=packet["snapshot_sha256"])
    require(
        review["source"]["snapshot"]
        == {k: _pin(old_source / "SNAPSHOT.json")[k] for k in ("path", "sha256")},
        "Review snapshot association differs",
    )
    for relative, expected in packet["expected_producer"]["source_hashes"].items():
        require(
            manifest["files"]["src/cells/" + relative]["sha256"] == expected,
            "Original source closure mismatch",
        )
    external = _runtime_files(_read(origin / "qualification-01/runtime.json"))
    for name, expected in packet["expected_producer"]["runtime_code_sha256"].items():
        row = _pin(name)
        require(row["sha256"] == expected, "Original runtime closure drift")
        external[row["path"]] = row
    plan = _read(origin / "packet-01/source-plan.json")
    for name, expected in plan["native_source"]["source_sha256"].items():
        row = _pin(Path(plan["native_source"]["checkout"]) / name)
        require(row["sha256"] == expected, "Original native source drift")
        external[row["path"]] = row
    require(plan == q.source_plan(), "Changed original source plan or comparison budgets")
    work = _read(origin / "qualification-01/work.json")
    q.check_work(work)
    archives = {name: _archive_pin(origin / "qualification-01" / name) for name in STAGES}
    program = _archive_pin(origin / "packet-01/program")
    require(
        packet["program"] == {k: program["manifest"][k] for k in ("path", "sha256")}
        and packet["source_plan"]
        == {k: files["packet-01/source-plan.json"][k] for k in ("path", "sha256")},
        "Original packet/archive association",
    )
    reviewed = {r["name"]: r for r in review["complete_archives"]["records"]}
    require(
        set(reviewed) == {"packet-01/program", *("qualification-01/" + n for n in STAGES)},
        "Review archive roster differs",
    )
    for name, archive in [
        ("packet-01/program", program),
        *(("qualification-01/" + n, a) for n, a in archives.items()),
    ]:
        row = reviewed[name]
        require(
            row["manifest"] == {k: archive["manifest"][k] for k in ("path", "sha256")}
            and row["state"] == {k: archive["files"]["state.json"][k] for k in ("path", "sha256")}
            and row["npz"] == {k: archive["files"]["arrays.npz"][k] for k in ("path", "sha256")},
            "Review archive producer mismatch",
        )
    return dict(
        root=str(origin),
        review=_pin(review_path),
        files=files,
        snapshot=_pin(old_source / "SNAPSHOT.json"),
        external=external,
        archives=archives,
        program=program,
        original_status="failed",
    )


def _disjoint(output, roots):
    output = _path(output, exists=False)
    for root in roots:
        root = _path(root)
        require(
            not output.is_relative_to(root) and not root.is_relative_to(output),
            "Output overlaps retained evidence/source",
        )
    require(not output.exists(), "Output already exists")
    return output


def _loaded_source(root, manifest):
    for name, module in tuple(sys.modules.items()):
        if name.startswith(("cells", "validation")) and getattr(module, "__file__", None):
            path = Path(module.__file__).resolve()
            require(path.is_relative_to(root), "Foreign loaded saved-reader source")
            rel = str(path.relative_to(root))
            require(
                rel in manifest["files"]
                and snapshot.digest(path) == manifest["files"][rel]["sha256"],
                "Unbound loaded saved-reader source",
            )


def prepare(origin, output, *, origin_review, origin_review_sha256, repository, cpu=3):
    """One-way checkout snapshot and saved input binding; no archive decoding."""
    repo = _path(repository)
    require(Path(__file__).resolve() == repo / FILE, "Prepare from current checkout only")
    require(type(cpu) is int and cpu >= 0, "Exact nonnegative CPU")
    output = _disjoint(output, (repo, origin))
    with source_blocked():
        original = origin_inputs(
            origin, origin_review=origin_review, origin_review_sha256=origin_review_sha256
        )
        old = _read(original["snapshot"]["path"])
        names = {r["checkout_path"] for r in old["files"].values()} | {FILE, TEST}
        for name, module in tuple(sys.modules.items()):
            if name.startswith(("cells", "validation")) and getattr(module, "__file__", None):
                path = Path(module.__file__).resolve()
                require(path.is_relative_to(repo), "Foreign loaded source during preparation")
                names.add(str(path.relative_to(repo)))
        output.mkdir()
        image = snapshot.freeze(repo, output / "source", {n: n for n in names})
        payload = dict(
            kind=KIND,
            held=True,
            automatic_launch=False,
            origin=original,
            snapshot=_pin(output / "source/SNAPSHOT.json"),
            repository=str(repo),
            resources=dict(
                cpu=cpu,
                threads=1,
                max_process_tree_bytes=2**30,
                wall_seconds=480,
                min_available_bytes=8 * 2**30,
            ),
            source_changes={
                n: dict(before=r["sha256"], after=image["files"][n]["sha256"])
                for n, r in old["files"].items()
                if r["sha256"] != image["files"][n]["sha256"]
            },
            release_environment=RELEASE,
            original_source_status="failed",
            scientific_source_calls=0,
            independent_input_sequences=1,
            independent_biological_cases=0,
        )
        snapshot.write_json(output / "inputs.json", payload)
    return _pin(output / "inputs.json")


def verify_preparation(prepared, preparation_sha256):
    prepared = _path(prepared)
    require(snapshot.digest(prepared / "inputs.json") == preparation_sha256, "Wrong preparation")
    value = _read(prepared / "inputs.json")
    require(
        value["kind"] == KIND
        and value["held"] is True
        and value["automatic_launch"] is False
        and value["original_source_status"] == "failed"
        and value["release_environment"] == RELEASE,
        "Saved assessment preparation schema",
    )
    image = _verify_pin(value["snapshot"])
    require(image == prepared / "source/SNAPSHOT.json", "Foreign prepared source")
    manifest = snapshot.verify(prepared / "source", manifest_sha256=value["snapshot"]["sha256"])
    require(Path(__file__).resolve() == prepared / "source" / FILE, "Run immutable saved reader")
    _loaded_source(prepared / "source", manifest)
    original = value["origin"]
    current = origin_inputs(
        original["root"],
        origin_review=original["review"]["path"],
        origin_review_sha256=original["review"]["sha256"],
    )
    require(current == original, "Changed original evidence binding")
    r = value["resources"]
    require(
        set(r)
        == {"cpu", "threads", "max_process_tree_bytes", "wall_seconds", "min_available_bytes"}
        and all(type(v) is int for v in r.values())
        and r["cpu"] >= 0
        and r["threads"] == 1
        and r["max_process_tree_bytes"] == 2**30
        and r["wall_seconds"] == 480
        and r["min_available_bytes"] == 8 * 2**30,
        "Saved analysis resource contract",
    )
    return value


@contextmanager
def source_blocked():
    """Fail before source/setup/RNG dispatch, including C RNG entry points."""
    prior, importer = sys.getprofile(), builtins.__import__
    evidence = dict(attempts=[], observer_errors=[])
    material = q.primitive.material
    forbidden = {
        f.__code__
        for f in (
            q.program,
            q.validate_program,
            q.primitive.begin,
            q.primitive.Execution.__init__,
            q.primitive.Execution.advance,
            q.primitive.Execution._advance_once,
            material.bind,
            material.validate_binding,
            material.state,
            material._state_values,
            material.drive,
            material.step,
            material._step_source,
            material.geometry_source.bind,
            material.geometry_source._geometry,
            material.geometry_source.current.bind,
            q.reference.evaluate_original,
            q.reference.evaluate_decimal,
            q.reference.compile_adapter,
        )
    }
    providers = (
        q.reference.native.__name__,
        q.reference.decimal.__name__,
        q.reference.native.geometry_native.__name__,
        "validation.betse.betse_environment_field_reference",
        "validation.betse.betse_normal_current_reference",
    )

    def refuse(label):
        evidence["attempts"].append(label)
        raise ValueError("Saved assessment forbids scientific entry: " + label)

    def profile(frame, event, arg):
        if event == "call":
            module = frame.f_globals.get("__name__", "")
            if (
                frame.f_code in forbidden
                or module in providers
                or module.startswith("betse.")
                or module in {"random", "_random"}
                or module.startswith("numpy.random")
                or frame.f_code.co_filename.startswith(("<pinned native ", q.reference.PREFIX))
            ):
                refuse(module + "." + frame.f_code.co_name)
        elif event == "c_call":
            module = getattr(arg, "__module__", "") or ""
            owner = getattr(arg, "__self__", None)
            if owner is not None and (
                type(owner).__module__.startswith("numpy.random")
                or type(owner).__module__ == "_random"
            ):
                module = type(owner).__module__
            if module in {"random", "_random"} or module.startswith("numpy.random"):
                refuse(module + "." + getattr(arg, "__name__", "?"))
        if prior is not None:
            if event in {"return", "c_return", "c_exception"}:
                try:
                    prior(frame, event, arg)
                except BaseException as error:
                    evidence["observer_errors"].append(dict(event=event, type=type(error).__name__))
            else:
                prior(frame, event, arg)

    def imports(name, *args, **kwargs):
        if name == "betse" or name.startswith("betse."):
            refuse("import " + name)
        return importer(name, *args, **kwargs)

    builtins.__import__ = imports
    sys.setprofile(profile)
    try:
        yield evidence
        require(
            sys.getprofile() is profile and not any(evidence.values()),
            "Saved source guard changed or refused",
        )
    finally:
        sys.setprofile(prior)
        builtins.__import__ = importer


class ObservedFingerprint(q.primitive.codec.Encoder):
    """Hash original descriptor atoms without changing decoded array buffers."""

    def __init__(self, observations):
        super().__init__()
        self.observed = {}
        fields = {
            "category",
            "dtype",
            "shape",
            "strides",
            "writable",
            "owns_data",
            "aligned",
            "C",
            "F",
            "base",
            "offset_bytes",
            "logical_snapshot",
        }
        for row in observations:
            require(
                type(row) is dict and set(row) in (fields, fields | {"buffer_contract"}),
                "Array observation schema",
            )
            value = row["logical_snapshot"]
            require(
                type(value) is q.np.ndarray and id(value) not in self.observed,
                "Absent/ambiguous array observation association",
            )
            require(
                value.dtype.str == row["dtype"] and list(value.shape) == row["shape"],
                "Conflicting array observation dtype/shape",
            )
            require(
                all(type(row[k]) is bool for k in ("writable", "C", "F")),
                "Typed array observation flags",
            )
            self.observed[id(value)] = (value, row)

    def encode(self, value, depth=0):
        row = None
        if type(value) is q.np.ndarray:
            require(id(value) in self.observed, "Missing original array observation")
            original, row = self.observed[id(value)]
            require(
                original is value and row["category"] == "ndarray" and (row["C"] or row["F"]),
                "Unsupported original fingerprint layout",
            )
            require(
                list(value.strides) == row["strides"]
                and bool(value.flags.c_contiguous) == row["C"]
                and bool(value.flags.f_contiguous) == row["F"],
                "Original fingerprint layout correspondence",
            )
        atom = super().encode(value, depth)
        if row is not None:
            node = self.nodes[atom[1]]
            require(node["tag"] == "array", "Fingerprint array node")
            node["writable"] = row["writable"]
            node["fortran"] = row["F"] and not row["C"]
        return atom


def original_fingerprint(value, observations):
    encoder = ObservedFingerprint(observations)
    return encoder.seal(encoder.capture(value))


def _same_data(a, b, reason):
    require(q.primitive.codec.fingerprint(a) == q.primitive.codec.fingerprint(b), reason)


def _declared_values(actual, declared):
    require(type(declared) is dict and actual.keys() == declared.keys(), "Declared buffer roster")
    for key in actual:
        a, b = q.np.asarray(actual[key]), q.np.asarray(declared[key])
        require(
            a.dtype == b.dtype and a.shape == b.shape and a.tobytes() == b.tobytes(),
            "Declared saved buffer differs: " + key,
        )


def _state(value, binding_id, index):
    m = q.primitive.material
    require(
        type(value) is m.State
        and type(value.step_index) is int
        and value.step_index == index
        and value.binding_identity == binding_id,
        "Saved source state binding/epoch",
    )
    require(value.identity == m.current._digest(m.state_record(value)), "Saved state identity")


def _trial(value, binding_id, parent, index, drive):
    m = q.primitive.material
    require(
        type(value) is m.Trial
        and type(value.drive) is m.Drive
        and value.binding_identity == binding_id
        and value.parent_identity == parent.identity,
        "Saved trial binding/parent",
    )
    _state(value.candidate, binding_id, index)
    _same_data(value.drive, drive, "Saved trial/drive differs")
    require(value.identity == m.current._digest(m.trial_record(value)), "Saved trial identity")


def validate_histories(saved, observations, program, domain):
    """Verify recorded lineage using data records, never numerical admission."""
    require(set(saved) == set(STAGES), "Complete saved stage roster")
    require(
        type(program) is dict
        and set(program) == {"definition", "initial", "steps"}
        and type(program["steps"]) is list
        and len(program["steps"]) == 4,
        "Complete pinned four-call program",
    )
    p, m = q.primitive, q.primitive.material
    begin = saved["primitive-begin"]
    require(
        type(begin) is dict
        and begin["kind"] == p.KIND
        and begin["failed"] is False
        and begin["failure"] is None
        and begin["failed_trial"] is None
        and begin["recovery_errors"] == [],
        "Failed/incomplete saved begin",
    )
    _same_data(begin["original_definition"], program["definition"], "Original definition differs")
    _same_data(begin["original_initial"], program["initial"], "Original initial inputs differ")
    binding, parent = begin["binding"], begin["current"]
    require(
        type(binding) is tuple
        and len(binding) == 4
        and binding[0] == p.KIND
        and type(binding[2]) is m.Binding
        and binding[3] == begin["original_input_fingerprint"],
        "Saved binding record",
    )
    _same_data(binding[1], begin["domain"], "Saved binding domain differs")
    _same_data(binding[1], q._tuples(domain), "Original packet domain differs")
    require(
        begin["original_input_fingerprint"]
        == original_fingerprint(
            (begin["original_definition"], begin["original_initial"]),
            observations["primitive-begin"],
        ),
        "Original input fingerprint cannot be reproduced",
    )
    source = binding[2]
    gb, cb = source.geometry_binding, source.geometry_binding.current_binding
    require(
        cb.identity == m.current._digest(m.current.binding_record(cb))
        and gb.identity == m.current._digest(m.geometry_source.binding_record(gb)),
        "Nested source binding identities",
    )
    require(
        source.identity == m.current._digest(m.binding_record(source)), "Material binding identity"
    )
    require(
        m.current._digest(source.definition) == m.current._digest(program["definition"]),
        "Binding definition differs from pinned program",
    )
    binding_id = original_fingerprint(binding, observations["primitive-begin"])
    require(
        type(parent) is tuple
        and len(parent) == 8
        and parent[:2] == (p.KIND, binding_id)
        and parent[4:6] == (None, None)
        and type(parent[6]) is int
        and parent[6:] == (0, "ready"),
        "Saved initial primitive record",
    )
    _state(parent[2], source.identity, 0)
    _declared_values(parent[2].values._asdict(), program["initial"])
    require(parent[3] == parent[2].identity, "Saved original initial identity")
    initial_id = parent[3]
    last = original_fingerprint(parent, observations["primitive-begin"])
    rows, lineage = [], []
    for i in range(4):
        name = f"primitive-step-{i}"
        pair, drive = saved[name], saved[f"primitive-drive-{i}"]
        require(
            type(pair) is tuple and len(pair) == 2 and type(drive) is m.Drive,
            "Saved primitive return/drive schema",
        )
        state, trial = pair
        require(
            type(state) is tuple
            and len(state) == 8
            and state[:2] == (p.KIND, binding_id)
            and state[3:5] == (initial_id, last)
            and type(state[6]) is int
            and state[6] == i + 1
            and state[7] == ("exhausted" if i == 3 else "ready"),
            "Noncontiguous primitive lineage/status",
        )
        forcing_id = original_fingerprint(drive, observations[f"primitive-drive-{i}"])
        _declared_values(drive._asdict(), program["steps"][i])
        require(state[5] == forcing_id, "Saved forcing fingerprint")
        _trial(trial, source.identity, parent[2], i + 1, drive)
        _same_data(state[2], trial.candidate, "Primitive candidate/trial association")
        last = original_fingerprint(state, observations[name])
        lineage.append(
            dict(
                index=i,
                state_identity=last,
                forcing_fingerprint=forcing_id,
                source_candidate_identity=trial.candidate.identity,
            )
        )
        parent = state
        rows.append(trial)
    legacy_binding = saved["legacy-binding"]
    require(
        type(legacy_binding) is m.Binding and legacy_binding.identity == source.identity,
        "Legacy/primitive binding identity",
    )
    _same_data(legacy_binding, source, "Legacy/primitive complete binding differs")
    legacy_parent = saved["legacy-initial"]
    _state(legacy_parent, source.identity, 0)
    _same_data(legacy_parent, begin["current"][2], "Legacy initial/source association")
    legacy = []
    for i in range(3):
        trial, drive = saved[f"legacy-step-{i}"], saved[f"legacy-drive-{i}"]
        _same_data(drive, saved[f"primitive-drive-{i}"], "Legacy/primitive drive differs")
        _trial(trial, source.identity, legacy_parent, i + 1, drive)
        legacy.append(trial)
        legacy_parent = trial.candidate
    native, first, second = (saved[n] for n in ("original-four", "Decimal100", "Decimal160"))
    require(
        native["failure"] is None
        and native["warnings"] == []
        and native["RNG_unchanged"] is True
        and all(r["source_completed"] is True for r in native["history"]),
        "Incomplete original source history",
    )
    for value, precision, refinement in ((first, 100, 1), (second, 160, 2)):
        raw = saved[f"Decimal-raw-{refinement}"]
        require(
            type(value["precision"]) is int
            and value["precision"] == precision
            and value["fixed_budget_reference"] is True
            and value["carried_error_allowance"] is False
            and type(raw) is dict
            and set(raw) == {"refinement", "exact"}
            and type(raw["refinement"]) is int
            and raw["refinement"] == refinement,
            "Incomplete precision/raw coefficient record",
        )
        require(
            type(raw["exact"]) is dict
            and raw["exact"]["precision"] == precision
            and len(raw["exact"]["history"]) == 4,
            "Complete raw Decimal histories retained",
        )
    require(
        all(len(v["history"]) == 4 for v in (native, first, second)),
        "Complete four-call reference histories",
    )
    return (
        rows,
        legacy,
        native,
        first,
        second,
        source.geometry_binding.geometry._asdict(),
        source.geometry_binding.current_binding.ion_ids,
    ), dict(
        binding_fingerprint=binding_id,
        source_binding_identity=source.identity,
        original_initial_identity=initial_id,
        states=lineage,
        metadata_fingerprint_bridge="original writable/Fortran atoms only; no owner hydration",
    )


def load_histories(original):
    saved, observations = {}, {}
    for name in STAGES:
        archive = original["archives"][name]
        require(
            _archive_pin(Path(archive["manifest"]["path"]).parent) == archive,
            "Changed archive before decode",
        )
        value, obs = q.read_archive(
            Path(archive["manifest"]["path"]).parent, with_array_observations=True
        )
        if name.startswith("Decimal-raw-"):
            saved[name] = value
        else:
            require(
                type(value) is dict
                and set(value) == {"status", "returned"}
                and value["status"] == "returned",
                "Failed/incomplete saved stage",
            )
            saved[name] = value["returned"]
        observations[name] = obs
    program = q.read_archive(Path(original["program"]["manifest"]["path"]).parent)
    packet = _read(original["files"]["packet-01/inputs.json"]["path"])
    return validate_histories(saved, observations, program, packet["domain"])


def _persist(directory, name, value, primary=None):
    try:
        require(
            len(q.primitive.codec.json_bytes(value)) <= q.primitive.codec.DEFAULT_LIMITS.json_bytes,
            "Saved result metadata bound",
        )
        snapshot.write_json(directory / name, value)
    except BaseException as secondary:
        if primary is None:
            raise
        primary.add_note("Saved assessment persistence failed: " + repr(secondary))
        try:
            print(
                json.dumps(dict(stage=name, primary=value, persistence_error=repr(secondary))),
                file=sys.stderr,
                flush=True,
            )
        except BaseException:
            pass


def _error(error):
    try:
        return q.primitive_validation.checkpoint._exception_record(error)
    except BaseException as secondary:
        return dict(
            type=type(error).__name__,
            module=type(error).__module__,
            recorder_error_type=type(secondary).__name__,
            complete_traceback=False,
        )


def worker(prepared, output, *, preparation_sha256, enabled=False):
    require(enabled is True and os.environ.get(RELEASE) == "1", "Saved assessment remains held")
    require(__debug__ and sys.flags.optimize == 0, "Assertion-enabled saved comparison")
    prepared = _path(prepared)
    output = _disjoint(output, (prepared,))
    # Establish a durable destination before verification so refusals survive.
    raw = _read(prepared / "inputs.json")
    output = _disjoint(output, (prepared, raw["origin"]["root"], raw["repository"]))
    output.mkdir()
    stage, guard = "verification", dict(attempts=[], observer_errors=[])
    try:
        with source_blocked() as guard:
            inputs = verify_preparation(prepared, preparation_sha256)
            require(os.sched_getaffinity(0) == {inputs["resources"]["cpu"]}, "Saved worker CPU")
            stage = "decode-and-lineage"
            args, lineage = load_histories(inputs["origin"])
            stage = "saved-comparison"
            comparison = q.compare_history_data(*args)
            stage = "post-verification"
            require(
                verify_preparation(prepared, preparation_sha256) == inputs,
                "Evidence changed during saved analysis",
            )
            q.archive(output / "comparison", dict(per_step=comparison, lineage=lineage))
            _persist(output, "evidence-references.json", inputs["origin"])
        stage = "terminal-evidence"
        _persist(output, "runtime.json", dict(child=q.identity(), loaded=q.inventory()))
        _persist(
            output, "source-blocked.json", dict(guard, completed=True, scientific_source_calls=0)
        )
        _persist(
            output,
            "result.json",
            dict(
                kind=KIND,
                status="saved_data_comparison_passed",
                preparation=_pin(prepared / "inputs.json"),
                comparison=_pin(output / "comparison/manifest.json"),
                original_source_status="failed",
                scientific_source_calls=0,
                independent_input_sequences=1,
                independent_biological_cases=0,
                physical_or_coupled_or_checkpoint_admission=False,
            ),
        )
        return comparison
    except BaseException as error:
        _persist(
            output,
            "failure.json",
            dict(
                kind=KIND,
                status="failed",
                stage=stage,
                error=_error(error),
                preparation=dict(path=str(prepared / "inputs.json"), sha256=preparation_sha256),
                original_source_status="failed",
                scientific_acceptance=False,
                scientific_source_calls=0,
            ),
            error,
        )
        for name, payload in (
            ("source-blocked.json", dict(guard, completed=False, scientific_source_calls=0)),
            ("evidence-references.json", raw["origin"]),
        ):
            if not (output / name).exists():
                _persist(output, name, payload, error)
        if not (output / "runtime.json").exists():
            try:
                _persist(
                    output, "runtime.json", dict(child=q.identity(), loaded=q.inventory()), error
                )
            except BaseException as secondary:
                error.add_note("Saved runtime capture failed: " + type(secondary).__name__)
        raise


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--prepare", action="store_true")
    parser.add_argument("--released", action="store_true")
    parser.add_argument("--origin", type=Path)
    parser.add_argument("--origin-review", type=Path)
    parser.add_argument("--origin-review-sha256")
    parser.add_argument("--repository", type=Path)
    parser.add_argument("--cpu", type=int, default=3)
    parser.add_argument("--prepared", type=Path)
    parser.add_argument("--preparation-sha256")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.prepare:
        prepare(
            args.origin,
            args.output,
            origin_review=args.origin_review,
            origin_review_sha256=args.origin_review_sha256,
            repository=args.repository,
            cpu=args.cpu,
        )
    else:
        worker(
            args.prepared,
            args.output,
            preparation_sha256=args.preparation_sha256,
            enabled=args.released,
        )


if __name__ == "__main__":
    main()
