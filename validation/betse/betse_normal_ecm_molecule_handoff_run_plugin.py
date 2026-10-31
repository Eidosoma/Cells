"""Observe actual released pytest work without wrapping or replacing owners.

The profile counts callable boundaries, not floating point operations or C
constructor internals. Exit events may be normal returns or exception unwinds;
pytest phases and the existing operation records determine success/failure.
"""

import importlib.abc
import json
import os
import subprocess
import sys
from collections import Counter
from pathlib import Path
from types import MemberDescriptorType

from validation.betse import betse_normal_ecm_molecule_handoff_run as runner
from validation.betse.betse_normal_channel_join_runtime import inventory

SESSION = None


def identity():
    return dict(
        pid=os.getpid(),
        start_ticks=int(Path("/proc/self/stat").read_text().rsplit(")", 1)[1].split()[19]),
        cpu_affinity=sorted(os.sched_getaffinity(0)),
        executable=runner.ref(sys.executable),
        optimize=sys.flags.optimize,
    )


class Calls:
    """Record all Cells calls, with durable entries for major work and RNG."""

    def __init__(self, stream):
        self.stream = stream
        self.counts = Counter()
        self.phases = Counter()
        self.active = {}
        self.sequence = 0
        self.stage = "collection"
        self.failure = None
        self.original = None

    def emit(self, value):
        self.stream.write(json.dumps(value, allow_nan=False) + "\n")
        self.stream.flush()
        os.fsync(self.stream.fileno())

    @staticmethod
    def category(module, name):
        if module == "random" or module.startswith("numpy.random"):
            return "RNG_callable"
        if not module.startswith("cells."):
            return None
        if module.endswith("betse_normal_ecm_molecule_checkpoint"):
            if name in {"save_checkpoint", "load_checkpoint", "_verify", "_rng_identity"}:
                return "checkpoint_" + name
        if name in {"initialize", "pre_cold", "finalize", "prepare", "initialize_both"}:
            return "setup_boundary"
        if name in {"advance", "step", "dispatch_both"}:
            return "timestep_boundary"
        if name.startswith(("verify", "_verify", "validate", "check")) or name in {
            "_binding",
            "_entry",
        }:
            return "verification_boundary"
        if name in {"numpy_restore", "python_restore", "numpy_manifest", "python_manifest"}:
            return "RNG_manifest_or_restore"
        if name == "transition":
            return "transition_boundary"
        return "other_Cells_callable"

    def profile(self, frame, event, arg):
        try:
            self.observe(frame, event, arg)
        except BaseException as error:
            self.failure = repr(error)
            raise

    def observe(self, frame, event, arg):
        if event in {"return", "c_return", "c_exception"}:
            key = id(frame) if event == "return" else (id(frame), id(arg))
            row = self.active.pop(key, None)
            if row is not None:
                self.emit(dict(event="exit", invocation=row["invocation"], exit_event=event))
            return
        if event not in {"call", "c_call"}:
            return
        if event == "call":
            module = frame.f_globals.get("__name__", "")
            name = frame.f_code.co_name
            key = id(frame)
        else:
            module = getattr(arg, "__module__", "") or ""
            owner = getattr(arg, "__self__", None)
            if owner is not None and type(owner).__module__.startswith("numpy.random"):
                module = type(owner).__module__
            if not (module == "random" or module.startswith("numpy.random")):
                return
            name, key = getattr(arg, "__name__", "?"), (id(frame), id(arg))
        category = self.category(module, name)
        if category is None:
            return
        qualified = module + "." + name
        self.counts[qualified] += 1
        if category == "other_Cells_callable":
            return
        parent = frame.f_back if event == "call" else frame
        ancestor = None
        while parent is not None:
            if id(parent) in self.active:
                ancestor = self.active[id(parent)]["invocation"]
                break
            parent = parent.f_back
        self.sequence += 1
        # Read plain dataclass fields only. This performs no validation,
        # property evaluation, owner construction or source-state mutation.
        binding = frame.f_locals.get("binding") if event == "call" else None
        fields = getattr(binding, "__dict__", {})
        calendar = fields.get("calendar")
        phase = getattr(calendar, "__dict__", {}).get("phase")
        member = vars(type(calendar)).get("phase")
        if isinstance(member, MemberDescriptorType):
            phase = member.__get__(calendar, type(calendar))
        if phase in {"INIT", "SIM"}:
            self.phases[qualified + ":" + phase] += 1
        row = dict(
            event="entry",
            invocation=self.sequence,
            function=qualified,
            category=category,
            parent_invocation=ancestor,
            pytest_stage=self.stage,
            phase=phase if phase in {"INIT", "SIM"} else None,
        )
        self.active[key] = row
        self.emit(row)

    def start(self):
        self.original = sys.getprofile()
        if self.original is not None:
            raise ValueError("Existing profiler would make invocation accounting ambiguous")
        sys.setprofile(self.profile)

    def stop(self):
        intact = getattr(sys.getprofile(), "__self__", None) is self
        sys.setprofile(self.original)
        return dict(
            counts=dict(self.counts),
            phase_counts=dict(self.phases),
            active_invocations=len(self.active),
            profile_intact=intact and self.failure is None,
            durable_major_entries=self.sequence,
            scope=(
                "Observed Python and RNG C callable boundaries, including nested validation; "
                "return events can include exception unwind. No individual C constructor/draw "
                "or FLOP enumeration. Layer counts overlap; "
                "phase.advance counts source call requests."
            ),
        )


class NoNative(importlib.abc.MetaPathFinder):
    def __init__(self, attempted):
        self.attempted = attempted

    def find_spec(self, fullname, path=None, target=None):
        if fullname == "betse" or fullname.startswith("betse."):
            self.attempted.append(dict(kind="native_import", module=fullname))
            raise ImportError("Native BETSE is outside Cells continuity scope")
        return None


class Session:
    def __init__(self, target):
        self.target = target
        self.reports = []
        self.collected = []
        self.forbidden = []
        self.guard = NoNative(self.forbidden)
        self.original_popen = subprocess.Popen
        self.stream = None
        self.calls = None

    def start(self):
        if os.environ.get(runner.handoff.RELEASE_ENV) != "1" or not __debug__:
            raise RuntimeError("Held: existing Root release and assertions required")
        if any(name == "betse" or name.startswith("betse.") for name in sys.modules):
            raise RuntimeError("Native BETSE was loaded before the continuity guard")
        runner.snapshot.write_json(self.target / "pytest-start.json", identity())
        self.stream = (self.target / "invocations.jsonl").open("x")
        self.calls = Calls(self.stream)
        sys.meta_path.insert(0, self.guard)
        subprocess.Popen = self.block_child
        self.calls.start()

    def block_child(self, *args, **kwargs):
        row = dict(kind="subprocess", command=repr(args[0] if args else kwargs.get("args")))
        self.forbidden.append(row)
        raise RuntimeError("No native/reference or other child in a continuity target")

    def finish(self, status):
        accounting = self.calls.stop()
        subprocess.Popen = self.original_popen
        sys.meta_path.remove(self.guard)
        self.stream.close()
        from cells.processes import betse_normal_ecm_molecule_checkpoint as checkpoint

        producer = checkpoint.producer_identity()  # file/config metadata; profile already stopped
        runner.snapshot.write_json(
            self.target / "pytest-finish.json",
            dict(
                **identity(),
                exitstatus=int(status),
                collected=self.collected,
                reports=self.reports,
                forbidden_entries=self.forbidden,
                accounting=accounting,
                producer=producer,
                runtime=inventory(),
            ),
        )


def pytest_sessionstart(session):
    global SESSION
    SESSION = Session(Path(os.environ["CELLS_MOLECULE_HANDOFF_RUN"]))
    SESSION.start()


def pytest_collection_finish(session):
    SESSION.collected = [item.nodeid for item in session.items]
    declared = runner.read_json(SESSION.target / "target.json")["node"]
    if SESSION.collected != [declared]:
        raise ValueError("Exact single declared target required before setup")


def pytest_runtest_logstart(nodeid, location):
    SESSION.calls.stage = nodeid


def pytest_runtest_logreport(report):
    row = dict(
        nodeid=report.nodeid,
        when=report.when,
        outcome=report.outcome,
        wasxfail=hasattr(report, "wasxfail"),
        longrepr=str(report.longrepr) if report.failed or report.skipped else None,
    )
    SESSION.reports.append(row)
    SESSION.calls.emit(dict(event="pytest_report", **row))


def pytest_sessionfinish(session, exitstatus):
    try:
        SESSION.finish(exitstatus)
    except BaseException as error:
        runner.retain_failure(SESSION.target, error, stage="pytest_finish_inventory")
        raise
