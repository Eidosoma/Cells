"""The run driver: one command makes one registered run and its record.

    python -m validation.ensemble_reexpression.run list [--inputs FILE]
    python -m validation.ensemble_reexpression.run snapshot DESTINATION
    python -m validation.ensemble_reexpression.run one NAME --runs DIR [--tag TAG] [...]
    python -m validation.ensemble_reexpression.run all --runs DIR [--tag TAG] [--workers N]
        [--retries] [...]
    python -m validation.ensemble_reexpression.run commands --runs DIR [--tag TAG] [...]
    python -m validation.ensemble_reexpression.run status --runs DIR [--inputs FILE]

**One run** writes its own definition (definitions.py), lets the engine parse and run it in a fresh
process, and writes `RUN.json`, its record, last of all. README.md says what each file is. A run
that the engine refuses is a result: its record says how it was refused and keeps the rows it has.

**Resumable.** A run whose record exists is not made again (`--again` makes a new attempt and keeps
the old record). A run that stopped with no record starts a new attempt beside the old one.

**Guarded.** Only a run whose name begins with `inv_` may be made from a checkout. Every other run
is registered: it is made from a clean, complete frozen snapshot (`snapshot`), and the caller names
the registration tag, which must be the snapshot's revision. A declared time off its grid is refused
by name before any run; `--off-grid` makes that one run all the same, and the record says so.

**The retry's runs** are made when the judge's note owes them (`--owed`), or every family's with the
batch (`--retries`). Those stand apart, in `retries/`, and the exporter opens them by the sha256 of
the judge's note alone (table.py).
"""

import argparse
import dataclasses
import fcntl
import hashlib
import json
import os
import platform
import shlex
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from validation.ensemble_reexpression.inputs import (
    DRIVEN,
    IONIC,
    MATCH_S,
    REGISTERED,
    REGISTERED_PART2,
    ROOT,
    Inputs,
    InputsError,
    read_json,
)

RECORD_KIND = "ensemble-reexpression run record, version 1"
RESOLUTION_KIND = "ensemble-reexpression resolution record, version 1"
RECORD, RESOLUTION = "RUN.json", "RESOLUTION.json"
MODULE = "validation.ensemble_reexpression.run"
SNAPSHOT = "SNAPSHOT.json"
NO_SNAPSHOT = "none"  # `source.snapshot` of a run made from a checkout.
EMPTY = hashlib.sha256(b"").hexdigest()
# What a frozen snapshot of this registration holds beside the engine: this folder's modules, the
# files of the spec that they read, the tools they use and the script that starts a unit.
MODULES = (
    "__init__",
    "blocks",
    "definitions",
    "inputs",
    "labels",
    "pieces",
    "readouts",
    "refusals",
    "run",
    "sample",
    "sample_part2",
    "stores",
    "table",
    "worlds",
)
DRIVERS = (
    *(f"validation/ensemble_reexpression/{name}.py" for name in MODULES),
    "validation/ensemble_reexpression/spec/SPEC.md",
    "validation/ensemble_reexpression/spec/inputs.json",
    "validation/tissue/field_solver_choice.py",
    "validation/source_snapshot.py",
    "scripts/run_detached.sh",
)
# Part 2's files of the spec, which a snapshot holds once its tag has them.
PART2 = (
    "validation/ensemble_reexpression/spec/PART2_BLOCKS.md",
    "validation/ensemble_reexpression/spec/inputs_part2.json",
)
WORKER_ENVIRONMENT = {
    "JAX_ENABLE_X64": "1",
    "JAX_PLATFORMS": "cpu",
    "JAX_ENABLE_COMPILATION_CACHE": "false",  # A registered run is cold (D321).
    "PYTHONDONTWRITEBYTECODE": "1",
    "OPENBLAS_NUM_THREADS": "1",
    "OMP_NUM_THREADS": "1",
    "MKL_NUM_THREADS": "1",
}


class Refused(Exception):
    """A run's refusal: a table entry's `refusal`."""

    def __init__(self, refusal):
        super().__init__(refusal["message"])
        self.refusal = refusal


def refused(kind, message):
    return Refused({"kind": kind, "message": message, "time_s": None})


class Guarded(RuntimeError):
    """A run that may not be made here."""


def utc():
    return datetime.now(timezone.utc).isoformat()


def write_json(path, value):
    """A new JSON file, whole or not at all."""
    pending = path.with_name(path.name + ".pending")
    with pending.open("x") as stream:
        json.dump(value, stream, indent=1)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    pending.rename(path)


def digest(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def slug(text):
    return "".join(c if c.isalnum() or c in "._-=+" else "_" for c in text)


@contextmanager
def locked(path):
    """This driver's own lock on one folder of its runs."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as stream:
        fcntl.flock(stream, fcntl.LOCK_EX)
        yield


# ------------------------------------------------------------------ where a run is made from


def _git(root, *args):
    return subprocess.run(
        ["git", "--no-optional-locks", "-C", str(root), *args],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=60,
    ).stdout


def revision(root=ROOT):
    """(the engine's revision, whether its source is dirty, the snapshot's path or "none", the
    sha256 of its patch) of the tree this module runs from."""
    manifest = Path(root) / SNAPSHOT
    if manifest.is_file():
        value = read_json(manifest)
        dirty = bool(value["selected_status_porcelain_v1_z"]) or value["patch_sha256"] != EMPTY
        return value["git_revision"], dirty, str(root), value["patch_sha256"]
    status = _git(root, "status", "--porcelain")
    patch = hashlib.sha256(_git(root, "diff", "--binary", "HEAD")).hexdigest()
    return _git(root, "rev-parse", "HEAD").decode().strip(), bool(status), NO_SNAPSHOT, patch


def guard(inputs, run, tag, root=ROOT):
    """Refuse to make a registered run anywhere but in a clean, complete frozen snapshot of the
    registration tag that the caller names, and from any file but that snapshot's own inputs.json.
    """
    if run.invented:
        return
    if not (Path(root) / SNAPSHOT).is_file():
        raise Guarded(f"{run.name!r} is registered: it is made from a frozen snapshot, not here")
    own = [(Path(root) / p.relative_to(ROOT)).resolve() for p in (REGISTERED, REGISTERED_PART2)]
    if inputs.path.resolve() not in own:
        raise Guarded(f"{run.name!r} is registered: {inputs.path} is not the snapshot's own inputs")
    from validation import source_snapshot

    value = source_snapshot.verify(root)
    if value["selected_status_porcelain_v1_z"] or value["patch_sha256"] != EMPTY:
        raise Guarded(f"{run.name!r} is registered: the frozen snapshot is not clean")
    if tag is None:
        raise Guarded(f"{run.name!r} is registered: name the registration tag (--tag)")
    try:
        commit = _git(value["repository"], "rev-parse", "--verify", f"refs/tags/{tag}^{{commit}}")
    except subprocess.CalledProcessError as error:
        raise Guarded(f"No tag {tag!r} in {value['repository']}") from error
    if commit.decode().strip() != value["git_revision"]:
        raise Guarded(f"The frozen snapshot is not the tag {tag!r}'s")


def cpu_model():
    for line in Path("/proc/cpuinfo").read_text().splitlines():
        if line.startswith("model name"):
            return line.split(":", 1)[1].strip()
    return platform.processor()


def source():
    """A table entry's `source` (spec/TABLE.md §3)."""
    import jax
    import jaxlib
    import numpy

    from cells.execution import blas_threads

    blas_threads.pin()
    engine_revision, dirty, snapshot, patch = revision()
    return {
        "engine_revision": engine_revision,
        "checkout_dirty": dirty,
        "snapshot": snapshot,
        "snapshot_patch_sha256": patch,
        "python": platform.python_version(),
        "numpy": numpy.__version__,
        "jax": jax.__version__,
        "jaxlib": jaxlib.__version__,
        "cpu_model": cpu_model(),
        "blas_threads": max(int(lib["num_threads"]) for lib in blas_threads.libraries()),
    }


def freeze(destination):
    """A frozen snapshot of the engine and of what this driver needs (source_snapshot.freeze)."""
    from validation import source_snapshot

    selected = ("src/cells", *DRIVERS, *PART2)
    names = _git(ROOT, "ls-files", "-z", "--", *selected).decode().split("\0")
    return source_snapshot.freeze(ROOT, destination, {name: name for name in names if name})


# ------------------------------------------------------------------ the folders of a run


class Folders:
    """Where the records of one campaign stand: a folder outside the tree they are made from. The
    retry's runs stand apart where they were made up front (`held`)."""

    def __init__(self, runs, *, held=False):
        self.root, self.held = Path(runs).resolve(), held
        if self.root.is_relative_to(ROOT):
            raise Guarded(f"Records are kept outside the tree they are made from: {self.root}")

    def run(self, run):
        return self.root / ("retries" if self.held and run.retry else "runs") / run.slug

    def made_early(self, run):
        """Whether a retry's run has a folder among those made up front."""
        return (self.root / "retries" / run.slug).exists()

    def record(self, run):
        path = self.run(run) / RECORD
        return read_json(path) if path.is_file() else None

    def attempt(self, run):
        """The attempt that a run's record is of."""
        record = self.record(run)
        return None if record is None else self.run(run) / record["attempt"]

    def resolution(self, name):
        return self.root / "resolutions" / slug(name)


def next_attempt(folder):
    """A new attempt's folder, after every earlier one."""
    folder.mkdir(parents=True, exist_ok=True)
    k = 1
    while True:
        path = folder / f"attempt-{k}"
        try:
            path.mkdir()
        except FileExistsError:
            k += 1
            continue
        return path


# ------------------------------------------------------------------ what a record says of its run


# The blocks of a parsed definition beside its execution that change how its steps are taken or
# checked (None where the definition has none).
OPT_IN = ("projective", "energy_check", "fine_windows")
COUNTS = ("executed_steps", "global_step_index")  # The scalar run's own, in its summary.json.
POOL_COUNTS = ("committed_events", "chunks")  # A pool's own, in its result.json.


def new_facts():
    """What a worker's record says beside its outcome, before anything is known (README)."""
    return {
        "definition": {},
        "resolution": None,
        "restart": None,
        "timings": {},
        "path": None,
        "rows": None,
        "check_options": None,
        "raised": None,
    }


def no_rows():
    """The record's `rows`, before the engine reports any."""
    return dict.fromkeys((*COUNTS, "checked_rows", "second_pass_windows", "pools"))


def plain(value):
    """A value of a parsed definition as JSON: a dataclass by every field, its defaults written."""
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return {f.name: plain(getattr(value, f.name)) for f in dataclasses.fields(value)}
    if isinstance(value, (list, tuple)):
        return [plain(v) for v in value]
    if isinstance(value, dict):
        return {str(k): plain(v) for k, v in value.items()}
    if hasattr(value, "tolist"):  # A number or an array of numpy's.
        return value.tolist()
    return value if value is None or isinstance(value, (bool, int, float, str)) else str(value)


def check_options(spec):
    """Every field of a parsed definition's execution, its defaults written out, and each block
    that changes how its steps are taken or checked, "absent" where it has none."""
    out = {
        f.name: plain(getattr(spec.execution, f.name)) for f in dataclasses.fields(spec.execution)
    }
    for name in OPT_IN:
        block = getattr(spec, name, None)
        out[name] = "absent" if block is None else plain(block)
    return out


# ------------------------------------------------------------------ the worker: one attempt


class Worker:
    """One attempt at one run, in its own process."""

    def __init__(self, attempt):
        self.attempt = Path(attempt)
        self.job = read_json(self.attempt / "job.json")
        self.inputs = Inputs(self.job["inputs"])
        self.run = self.inputs.run(self.job["run"])
        self.folders = Folders(self.job["runs"], held=self.job.get("held", False))
        self.facts, self.stage = new_facts(), "declaration"

    @property
    def output(self):
        return self.attempt / "output"

    def raised(self, error, stage=None):
        """What was raised (an exception, or its class's full name), by its class and module, and
        the stage it was raised at, after what was raised before it (`raised`)."""
        from validation.ensemble_reexpression.refusals import qualified

        kind = error if isinstance(error, str) else qualified(type(error))
        found = {"class": kind, "stage": stage or self.stage}
        self.facts["raised"] = [*(self.facts.get("raised") or ()), found]

    # ---- what is submitted

    def declaration(self, definitions):
        """What the generator makes for this run; its own refusals are no engine's (`harness`)."""
        from validation.ensemble_reexpression.blocks import NoSection
        from validation.ensemble_reexpression.labels import UnknownOrder

        try:
            return definitions.definition(self.inputs, self.run)
        except (UnknownOrder, NoSection, InputsError) as error:
            self.raised(error)
            raise refused("harness", str(error)) from error

    def submit(self, raw):
        """The definition or composed file this run submits, written before the engine sees it."""
        write_json(self.attempt / "submitted.json", raw)
        self.facts["definition"]["submitted_sha256"] = digest(self.attempt / "submitted.json")
        return self.attempt / "submitted.json"

    def parsed(self, spec):
        write_json(self.attempt / "parsed.json", spec.to_dict())
        self.facts["definition"]["fingerprint"] = spec.fingerprint
        return spec

    def gates(self):
        """The laws that the run's own declaration names for its junctions' gates, a declared
        change's with them."""
        from validation.ensemble_reexpression import definitions
        from validation.ensemble_reexpression.labels import string

        change = definitions.declared_change(self.inputs, self.run)
        block = definitions.block_of(self.inputs.worlds[self.run.world], change)
        junctions = block.get("junctions")
        if not isinstance(junctions, dict):
            return ()
        return tuple({string(j.get("gate", {}).get("law")) for j in junctions.values()})

    @contextmanager
    def engine(self, stage):
        """What the engine raises in here is this run's refusal, by the mapping of refusals.py."""
        from cells.assembly.spec import AssemblyError
        from cells.definitions.specs import ConfigError
        from cells.execution.errors import NumericalError
        from validation.ensemble_reexpression import refusals

        caught = (ConfigError, AssemblyError, NumericalError)
        if stage == "parse":
            caught += (KeyError, TypeError, AttributeError, IndexError)
        try:
            yield
        except caught as error:
            self.raised(error)
            raise Refused(refusals.refusal(error, stage=stage, gates=self.gates())) from error

    # ---- the three kinds of run

    def make(self):
        from validation.ensemble_reexpression import definitions

        raw = self.declaration(definitions)
        path = self.submit(raw)  # The entry of a run refused from here on holds its declaration.
        if self.job["off_grid"] and not self.run.invented:
            raise refused("harness", "off_grid: a registered run is never made with --off-grid")
        fault = definitions.grid_faults(self.inputs, self.run)
        if fault is not None and not self.job["off_grid"]:
            raise refused("harness", fault)
        self.facts["off_grid"] = fault
        if self.run.kind == IONIC:
            return self.ionic(path)
        if self.run.kind == DRIVEN:
            return self.driven(raw)
        return self.pools(path)

    def ionic(self, path):
        from cells.definitions.specs import load_spec

        self.stage = "parse"
        with self.engine("parse"):
            spec = self.parsed(load_spec(path))
        self.facts["check_options"] = check_options(spec)  # Outside the parse: no refusal of it.
        if self.run.restart_time is not None:
            return self.resume(spec)
        self.facts["path"] = "run"
        return self.execute(spec, None, {"operation": "run"})

    def driven(self, raw):
        from cells.definitions.specs import load_spec

        resolved = self.resolve(raw)
        self.stage = "parse"
        with self.engine("parse"):
            spec = self.parsed(load_spec(resolved / f"worlds/world-{self.run.world_id}.json"))
        self.facts["check_options"] = check_options(spec)
        made_from = read_json(resolved / "inputs.json")
        if spec.fingerprint not in made_from["definitions_sha256"]:
            raise RuntimeError("The resolution's inputs.json is not about this definition")
        write_json(self.attempt / "inputs.json", made_from)
        if self.run.restart_time is not None:
            return self.resume(spec, made_from)
        self.facts["path"] = "run"
        return self.execute(spec, None, {"operation": "run", "inputs": made_from})

    def pools(self, path):
        from cells.assembly_pool import resolve

        self.stage = "parse"
        with self.engine("parse"):
            composed = resolve.load_composed(path)
        self.facts["definition"]["composed_fingerprint"] = composed.fingerprint
        folder = self.output / "pools"
        folder.mkdir(parents=True)
        self.facts["path"] = "pool" if self.run.restart_time is None else "pool legs"
        self.stage = "run"
        for k, drive in enumerate(composed.drives):
            pool = folder / f"pool-{k:03}"
            try:
                with self.engine("run"):
                    if self.run.restart_time is None:
                        resolve.run_pool(composed, k, pool, backend="cpu", device_index=0)
                    else:
                        self.legs(k, drive.pool, pool, self.output / f"first-leg-{k:03}")
            except Refused as refusal:
                if refusal.refusal["kind"] == "check":  # A pool has no rows: its horizon.
                    refusal.refusal["time_s"] = drive.pool.end_time_s
                self.facts["rows"] = self.pool_rows()
                raise
        self.facts["rows"] = self.pool_rows()

    def pool_rows(self):
        """`rows` of a pool run: each pool's and leg's own counts, from its result.json."""
        counts = {}
        for path in sorted(self.output.rglob("result.json")):
            made = read_json(path)
            counts[str(path.parent.relative_to(self.output))] = {k: made[k] for k in POOL_COUNTS}
        return no_rows() | {"pools": counts}

    def legs(self, k, pool, folder, first):
        """A pool's restart: a first leg of the same definition to the checkpoint's time, its
        checkpoint through a file, and a second leg resumed from that file to the end, by the two
        functions that resolve.run_pool runs a pool with. The first leg is in this run's record."""
        from cells.assembly_pool import cli
        from cells.assembly_pool.io import load_checkpoint

        at, device = self.run.restart_time, {"backend": "cpu", "device_index": 0}
        cli.register(first, pool, **device, until=at, parent=None)
        cli.execute(first)
        saved = first / "checkpoint"
        spec, state, sha = load_checkpoint(saved)
        self.facts.setdefault("first_legs", []).append(
            {
                "pool": k,
                "command": ["cells", "assembly-pool", "run", f"submitted.json pools[{k}].pool"]
                + ["--until", repr(at), "--output", str(first.relative_to(self.attempt))],
                "checkpoint": str(saved.relative_to(self.attempt)),
                "checkpoint_sha256": {path.name: digest(path) for path in sorted(saved.iterdir())},
            }
        )
        parent = {"path": str(saved), "sha256": sha}
        cli.register(folder, spec, **device, until=spec.end_time_s, parent=parent)
        cli.execute(folder)
        self.facts["restart"] = {
            "time_s": float(state.time_s.max()),
            "step_index": None,
            "through": "file",
        }

    # ---- what a driven run needs first

    def resolve(self, raw):
        """The folder of this composed file's resolution, made by the first run that needs it."""
        from cells.assembly_pool import resolve

        name = resolution_name(self.run)
        folder = self.folders.resolution(name)
        with locked(folder.with_name(folder.name + ".lock")):
            if not (folder / RESOLUTION).is_file():
                attempt = next_attempt(folder)
                composed = attempt / "composed.json"
                write_json(composed, raw)
                record = {"kind": RESOLUTION_KIND, "resolution": name, "attempt": attempt.name}
                record |= {"source": source(), "started_utc": utc()}
                began, self.stage = time.perf_counter(), "resolve"
                try:
                    with self.engine("parse"):
                        resolve.resolve(composed, attempt / "resolved")
                    record |= {"status": "completed", "refusal": None}
                except Refused as error:
                    record |= {"status": "refused", "refusal": error.refusal}
                record["raised"] = self.facts["raised"]
                record |= {"seconds": time.perf_counter() - began, "finished_utc": utc()}
                record["files_sha256"] = files(attempt)
                write_json(folder / RESOLUTION, record)
        record = read_json(folder / RESOLUTION)
        attempt = folder / record["attempt"]
        if read_json(attempt / "composed.json") != raw:
            raise RuntimeError(f"The resolution {name!r} was made from another composed file")
        self.facts["resolution"] = {
            "name": name,
            "record": str((folder / RESOLUTION).relative_to(self.folders.root)),
            "record_sha256": digest(folder / RESOLUTION),
            "composed_file_sha256": digest(attempt / "composed.json"),
        }
        if record["status"] != "completed":
            self.facts["raised"] = record["raised"]  # Whichever run made the resolution.
            raise Refused(record["refusal"])
        return attempt / "resolved"

    # ---- the ionic run itself

    def checkpoints(self, times):
        """The accepted times at which this run writes a checkpoint: each restart's of it."""
        out = []
        for run in self.inputs.runs.values():
            if run.kind == self.run.kind and run.judged_name == self.run.name:
                at = min((float(t) for t in times), key=lambda t: abs(t - run.restart_time))
                if abs(at - run.restart_time) > MATCH_S:
                    raise RuntimeError(f"No accepted row at {run.restart_time!r} s")
                out.append(at)
        return tuple(out)

    def execute(self, spec, checkpoint, provenance):
        from cells.definitions.specs import ConfigError
        from cells.execution.errors import NumericalError
        from cells.execution.runner import run
        from cells.records.io import write_run
        from validation.ensemble_reexpression import refusals

        self.stage = "run"
        try:
            result = run(spec, checkpoint)
        except (ConfigError, NumericalError) as error:
            self.raised(error)
            refusal = refusals.refusal(error, stage="run", gates=self.gates())
            if isinstance(error, NumericalError):
                try:
                    self.kept(spec, checkpoint, refusal)
                except Exception as fault:  # The engine's own refusal stands, whatever this did.
                    self.facts["second_pass"] = {"fault": f"{type(fault).__name__}: {fault}"}
                    self.raised(fault, "second pass")
                    if refusal["kind"] == refusals.CHECK:
                        refusal["time_s"] = spec.experiment.end_time
            raise Refused(refusal) from error
        write_run(
            self.output,
            result,
            checkpoint_times=self.checkpoints(result.times),
            provenance=provenance | {"registered_run": self.run.name},
        )
        summary = read_json(self.output / "summary.json")  # The engine's own counts.
        self.facts["rows"] = no_rows() | {key: summary[key] for key in COUNTS}
        self.facts["timings"] = dict(result.timings)
        self.facts["snapped_events"] = [list(pair) for pair in result.snapped_events]

    def kept(self, spec, checkpoint, refusal):
        """The rows of a refused run, and for a check that failed the time of the row it failed at:
        where the pass that finds it completes, the end of the run, and the refusal says so. The
        record says whose rows they are, and holds the sha256 of their file with the others'."""
        import numpy as np

        from validation.ensemble_reexpression import refusals

        self.stage = "second pass"
        arrays, failed, raised = refusals.rows_before(spec, checkpoint)
        if raised is not None:
            self.raised(raised)
        if arrays is not None:
            np.savez(self.attempt / refusals.PARTIAL, **arrays)
        self.facts["second_pass"] = refusals.policy() | {
            "rows": None if arrays is None else refusals.PARTIAL,
            "completed": failed is None,
        }
        # The windows that the pass yielded, each after its checks: its rows, but the first.
        windows = 0 if arrays is None else len(arrays["accepted_times"]) - 1
        self.facts["rows"] = no_rows() | {"second_pass_windows": windows}
        if refusal["kind"] == refusals.CHECK:
            refusal["time_s"] = spec.experiment.end_time if failed is None else failed
            if failed is None:
                refusal[refusals.SECOND_PASS] = True
        self.facts["refused_row_found"] = failed is not None

    def resume(self, spec, made_from=None):
        """A restart: the checkpoint that its judged run wrote at the time, through its file."""
        from cells.records.io import load_snapshot

        self.facts["path"], self.stage = "resume", "run"
        judged = self.inputs.run(self.run.judged_name)
        record = self.folders.record(judged)
        if record is None or record["status"] != "completed":
            raise RuntimeError(f"{judged.name!r} has no completed record to resume")
        snapshot = checkpoint_folder(self.folders.attempt(judged), self.run.restart_time)
        saved = load_snapshot(snapshot)
        if saved.spec.fingerprint != spec.fingerprint:
            raise RuntimeError("The checkpoint is of another definition")
        self.facts["restart"] = {
            "time_s": saved.checkpoint.time,
            "step_index": saved.checkpoint.step_index,
            "through": "file",
        }
        provenance = {
            "operation": "resume",
            "parent_snapshot_sha256": saved.fingerprint,
            "parent_definition_sha256": saved.spec.fingerprint,
            "branch_time": saved.checkpoint.time,
            "parent_run": judged.name,
        }
        if made_from is not None:
            provenance["inputs"] = made_from
        return self.execute(saved.spec, saved.checkpoint, provenance)

    # ---- the outcome

    def outcome(self):
        outcome = {"status": "completed", "refusal": None, "source": source()}
        began = time.perf_counter()
        try:
            self.make()
        except Refused as error:
            outcome |= {"status": "refused", "refusal": error.refusal}
        except Exception as error:  # Anything the engine did not raise as a refusal.
            self.raised(error)
            message = f"{type(error).__name__}: {error}"
            outcome |= {
                "status": "refused",
                "refusal": {"kind": "harness", "message": message, "time_s": None},
            }
        self.facts["timings"]["worker_seconds"] = time.perf_counter() - began
        write_json(self.attempt / "outcome.json", outcome | {"facts": self.facts})


def resolution_name(run):
    """One composed file's name: its world, seed and step, and a plant's variant."""
    name = f"{run.world} s{run.seed_index} h={run.step_s!r}"
    if run.role == "plant" or run.declared_change is not None:
        name += f" {run.variant or run.slug}"
    return name


def checkpoint_folder(attempt, at):
    """The checkpoint at this time among those that an attempt wrote."""
    for manifest in sorted((attempt / "output/snapshots").glob("*/manifest.json")):
        if abs(read_json(manifest)["clock"]["time"] - at) <= MATCH_S:
            return manifest.parent
    raise RuntimeError(f"{attempt.parent.name} wrote no checkpoint at {at!r} s")


def files(folder):
    """{relative path: sha256} of a folder's files, the copies of the package apart."""
    return {
        str(path.relative_to(folder)): digest(path)
        for path in sorted(folder.rglob("*"))
        if path.is_file() and "source" not in path.relative_to(folder).parts
    }


# ------------------------------------------------------------------ one run, one command


def worker_environment():
    environment = dict(os.environ) | WORKER_ENVIRONMENT
    environment["PYTHONPATH"] = f"{ROOT / 'src'}{os.pathsep}{ROOT}"
    return environment


def one(inputs, run, runs, *, tag=None, off_grid=False, max_seconds=None, again=False, held=False):
    """Make one run and write its record; its record. held: a retry's run is made up front."""
    guard(inputs, run, tag)
    folders = Folders(runs, held=held)
    folder = folders.run(run)
    with locked(folder.with_name(folder.name + ".lock")):
        previous = folders.record(run)
        if previous is not None:
            if not again:
                return previous
            (folder / RECORD).rename(folder / previous["attempt"] / RECORD)
        attempt = next_attempt(folder)
        write_json(
            attempt / "job.json",
            {
                "run": run.name,
                "inputs": str(inputs.path.resolve()),
                "runs": str(folders.root),
                "off_grid": off_grid,
                "max_seconds": max_seconds,
                "tag": tag,
                "held": held,
                "started_utc": utc(),
            },
        )
        crash = work_apart(attempt, max_seconds)
        record = made(inputs, run, attempt, crash, tag=tag, off_grid=off_grid)
        write_json(folder / RECORD, record)
        return record


def work_apart(attempt, max_seconds):
    """Run the worker in its own process: what ended it, None where it wrote its outcome."""
    command = [sys.executable, "-m", MODULE, "_worker", str(attempt)]
    with (attempt / "worker.log").open("x") as log:
        child = subprocess.Popen(
            command, cwd=ROOT, env=worker_environment(), stdout=log, stderr=subprocess.STDOUT
        )
        try:
            code = child.wait(timeout=max_seconds)
        except subprocess.TimeoutExpired:
            child.kill()
            child.wait()
            return f"the run took more than {max_seconds} s"
    if code < 0:
        return f"the worker was ended by signal {-code}"
    if not (attempt / "outcome.json").is_file():
        return f"the worker ended with exit code {code} and wrote no outcome"
    return None


def made(inputs, run, attempt, crash, *, tag, off_grid):
    """A run's record, from its attempt's outcome, or from what ended it where it has none: its
    source is then this process's own, which runs from the same tree on the same machine."""
    if crash is None:
        outcome = read_json(attempt / "outcome.json") | {"source_from": "worker"}
    else:
        outcome = {
            "status": "refused",
            "refusal": {"kind": "harness", "message": crash, "time_s": None},
            "source": source(),
            "source_from": "driver",
            "facts": new_facts(),
        }
    engine_revision, dirty, snapshot, patch = revision()
    return {
        "kind": RECORD_KIND,
        "run": run.name,
        "registered": {
            "consumer": run.consumer,
            "family": run.family,
            "world": run.world,
            "seed_index": run.seed_index,
            "world_id": run.world_id,
            "step_s": run.step_s,
            "role": run.role,
            "variant": run.variant,
            "declared_change": run.declared_change,
            "retry": run.retry,
        },
        "run_kind": run.kind,
        "inputs": {"name": inputs.path.name, "sha256": inputs.sha256},
        "status": outcome["status"],
        "refusal": outcome["refusal"],
        "attempt": attempt.name,
        "attempts": earlier(attempt),
        "options": {"tag": tag, "off_grid": off_grid},
        "driver_source": {
            "engine_revision": engine_revision,
            "checkout_dirty": dirty,
            "snapshot": snapshot,
            "snapshot_patch_sha256": patch,
        },
        "source": outcome["source"],
        "source_from": outcome["source_from"],
        **outcome["facts"],
        "started_utc": read_json(attempt / "job.json")["started_utc"],
        "finished_utc": utc(),
        "files_sha256": files(attempt),
    }


def earlier(attempt):
    """The attempts up to this one, in order, and whether each wrote an outcome."""
    return [
        {"attempt": path.name, "outcome": (path / "outcome.json").is_file()}
        for path in sorted(attempt.parent.glob("attempt-*"), key=lambda p: int(p.name[8:]))
    ]


# ------------------------------------------------------------------ the campaign


def ordered(inputs, *, consumers=None, owed=None, retries=False):
    """The runs in an order that makes each after what it needs: the judged ones, then plants, then
    the retry's of every family (`retries`), then the restarts. With `owed`, the retry's runs that
    the note lists, alone."""
    if owed is not None and retries:
        raise InputsError("the retry's runs are made by a note, or up front, and not both")
    runs = list(inputs.runs.values()) if owed is None else list(inputs.owed(owed))
    runs += inputs.retries() if retries else ()
    if consumers:
        runs = [r for r in runs if r.consumer in consumers]
    place = {"judged": 0, "plant": 1, "support": 2}
    return sorted(runs, key=lambda r: (r.restart_time is not None, r.retry, place.get(r.role, 3)))


def selected(inputs, args):
    """The runs that a campaign's options select."""
    return ordered(inputs, consumers=args.consumer, owed=args.owed, retries=args.retries)


def options(args):
    """The options of `one` that a campaign hands on."""
    out = ["--runs", str(args.runs), "--inputs", str(args.inputs)]
    for name in ("tag", "max_seconds"):
        value = getattr(args, name)
        if value is not None:
            out += ["--" + name.replace("_", "-"), str(value)]
    return out + (["--retries"] if args.retries else [])


def command_of(run, args):
    return [sys.executable, "-m", MODULE, "one", run.name, *options(args)]


def campaign(inputs, args):
    """Every run of the campaign that has no record yet, in stages, `--workers` at a time, each in
    its own process on this one's CPUs."""
    runs = selected(inputs, args)
    folders = Folders(args.runs, held=args.retries)

    def make(run):
        if folders.record(run) is None:
            subprocess.run(
                command_of(run, args),
                cwd=ROOT,
                env=worker_environment(),
                stdout=subprocess.DEVNULL,
                check=False,
            )
        word = ended(folders.record(run))
        print(json.dumps({"run": run.name, "ended": word}), flush=True)
        return run.name, word

    # A restart waits for every run before it; nothing else waits for anything.
    found = {}
    with ThreadPoolExecutor(args.workers) as pool:
        for restarts in (False, True):
            stage = [r for r in runs if (r.restart_time is not None) is restarts]
            found |= dict(pool.map(make, stage))
    print(json.dumps(status(inputs, args)))
    return 0 if set(found.values()) <= {"completed"} else 1


def ended(record):
    """How a record ended, in one word: its status, or the kind of its refusal."""
    if record is None:
        return "no record"
    return record["status"] if record["refusal"] is None else record["refusal"]["kind"]


def status(inputs, args):
    """{consumer: {how a run ended: how many}} of a campaign's records."""
    folders, out = Folders(args.runs, held=args.retries), {}
    for run in selected(inputs, args):
        counts = out.setdefault(run.consumer, {})
        word = ended(folders.record(run))
        counts[word] = counts.get(word, 0) + 1
    return out


def unit(run):
    return "reexpression-" + "".join(c if c.isalnum() or c in "._-" else "-" for c in run.slug)


def detached(run, args):
    """The command that makes one run as its own detached unit (scripts/run_detached.sh)."""
    head = ["bash", "scripts/run_detached.sh", unit(run), args.memory]
    if args.cpus:
        head += ["--cpus", args.cpus]
    for key, value in WORKER_ENVIRONMENT.items():
        head += ["--env", f"{key}={value}"]
    head += ["--env", f"PYTHONPATH={ROOT / 'src'}{os.pathsep}{ROOT}", "--dir", str(ROOT), "--"]
    return head + command_of(run, args)


# ------------------------------------------------------------------ the command line


def _parser():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    commands = parser.add_subparsers(dest="command", required=True)
    listed = commands.add_parser("list", help="the registered runs and what each is")
    commands.add_parser("snapshot", help="freeze the source").add_argument("path", type=Path)
    commands.add_parser("_worker", help=argparse.SUPPRESS).add_argument("attempt", type=Path)
    single = commands.add_parser("one", help="make one run")
    single.add_argument("name")
    single.add_argument("--again", action="store_true", help="a new attempt beside a record")
    single.add_argument("--off-grid", action="store_true", help="make a run off its grid (named)")
    every = commands.add_parser("all", help="make every run that has no record")
    shown = commands.add_parser("commands", help="print each run's detached command")
    counted = commands.add_parser("status", help="count the records by how they ended")
    for command in (listed, single, every, shown, counted):
        command.add_argument("--inputs", type=Path, default=REGISTERED)
    for command in (single, every, shown, counted):
        command.add_argument("--runs", type=Path, required=True, help="the records' folder")
    for command in (single, every, shown):
        command.add_argument("--tag", help="the registration tag, for registered runs")
        command.add_argument("--max-seconds", type=float, help="end a run after this long")
    for command in (every, shown, counted):
        command.add_argument("--consumer", action="append")
        command.add_argument("--owed", type=Path, help="the judge's retry_owed.json")
    for command in (single, every, shown, counted):
        command.add_argument("--retries", action="store_true", help="the retry's runs, up front")
    every.add_argument("--workers", type=int, default=1)
    shown.add_argument("--memory", default="4G")
    shown.add_argument("--cpus", default="")
    return parser


def main(argv=None):
    args = _parser().parse_args(argv)
    if args.command == "_worker":
        Worker(args.attempt).outcome()
        return 0
    if args.command == "snapshot":
        value = freeze(args.path.resolve())
        print(json.dumps({"revision": value["git_revision"], "files": len(value["files"])}))
        return 0
    inputs = Inputs(args.inputs)
    if args.command == "list":
        for run in inputs.runs.values():
            print(json.dumps({"run": run.name, "kind": run.kind, "role": run.role}))
        return 0
    try:
        if args.command == "commands":
            for run in selected(inputs, args):
                print(shlex.join(detached(run, args)))
            return 0
        if args.command == "status":
            print(json.dumps(status(inputs, args)))
            return 0
        if args.command == "all":
            return campaign(inputs, args)
        record = one(
            inputs,
            inputs.run(args.name),
            args.runs,
            tag=args.tag,
            off_grid=args.off_grid,
            max_seconds=args.max_seconds,
            again=args.again,
            held=args.retries,
        )
    except (Guarded, InputsError) as error:
        print(f"refused: {error}", file=sys.stderr)
        return 2
    print(json.dumps({k: record[k] for k in ("run", "status", "refusal", "attempt")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
