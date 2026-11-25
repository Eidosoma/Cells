"""The bypass guard of checkpoint continuity (docs/CHECKPOINT_CONTINUITY_DESIGN.md, section 7).

One rule: every engine execution that starts from saved state either loads through
io.load_snapshot or batch_io.load_batch_snapshot (refused by default, or admitted by a
continuity record), or declares itself a new run of a definition whose initial values are
imported, recorded and judged on its own. Reading saved bytes without executing from them is
not a migration.

The scan is static, over the modules under validation/ and scripts/ (test files excluded:
they test the read-only tools). It flags a module that
- names a snapshot's ``state.npz``;
- constructs a Checkpoint from arrays it loads itself (a ``Checkpoint(...)`` call and an
  ``np.load`` call in one module);
- resumes from its own saved numeric state: ``np.load`` of an ``.npz`` file whose name says
  checkpoint, state or restart (a driver's checkpoint.npz, last-state.npz or restart.npz); or
- defines a module-level ``start_state``, section 7's name for importing a saved state as a
  new definition's start;
and fails unless EXEMPT lists the module with its class and reason (section 7's table, with
registered drivers and development tools). It also fails for a module that passes
``continuity=`` without being on the development allow-list, for such a module that does not
pass provenance(admission) on, for registered drivers and judges that pass or import a record,
and for engine call sites: in src/cells only batch_io passes ``continuity=``, to load a
cohort's children.

The scan sees names and calls, not what a module does at run time; the rule above binds a
module that reads saved state in a way the scan does not see.
"""

import ast
import functools
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]

READ = "read-only comparison or audit, or a writer of its own output: nothing continues"
DIAGNOSTIC = (
    "rebuilds and executes outside the loaders as a diagnostic; no output is a continuation "
    "of the run (its rule (b) record of the snapshot digest and both identities is the lead's "
    "to add: outside the first landing's files)"
)
IMPORT = "imports saved states into a new definition (rule (b)); exempt while its runs last"
DRIVER = "driver-owned resume inside one execution snapshot; exempt while its runs last"
SAME = "same-process restart or an independent reference: no source change, or no Cells engine"
REGISTERED_DRIVER = (
    "a registered driver's own resume inside one execution snapshot; exempt while its runs "
    "last, and as a registered driver it never passes a continuity record"
)
DEVELOPMENT_TOOL = (
    "a development tool that imports a reference record's state as a new definition's start "
    "(rule (b)): a new run, judged on its own; it claims no continuity"
)
PROBE = (
    "the continuity probe: reads checkpoints without the identity comparison to trace them "
    "under S0 and S1, keeps every other loader check, and never continues a run"
)
EXEMPT = {
    # Read-only comparisons, audits and writers of their own output (16).
    "validation/assembly/compare_throughput.py": READ,
    "validation/betse/channel_feedback_audit/feedback_audit_cells.py": READ,
    "validation/betse/channel_feedback_audit/feedback_audit_context.py": READ,
    "validation/betse/channel_history_audit/history_audit_cells.py": READ,
    "validation/betse/channel_history_pilot/preparation_review.py": READ,
    "validation/betse/channel_release_audit/release_audit_cells.py": READ,
    "validation/betse/channel_release_audit/release_audit_context.py": READ,
    "validation/betse/channel_release_pilot/timed_cells_check.py": READ,
    "validation/betse/live_recording/matched_windows.py": READ,
    "validation/betse/live_recording_audit/cells_review.py": READ,
    "validation/betse/pump_pilot_diagnosis/diagnose.py": READ,
    "validation/ensemble/jupiter_check.py": READ,
    "validation/ensemble/spatial_matrix.py": READ,
    "validation/ensemble_reexpression/rehearsal/legacy_arrays.py": READ,
    "validation/ensemble_reexpression/rehearsal/reference.py": READ,
    "validation/ensemble_reexpression/table.py": READ,
    # Rebuild and execute outside the loaders, as diagnostics (2).
    "scripts/profile_dispatch.py": DIAGNOSTIC + " (L4 timing on held states, other XLA flags)",
    "validation/tissue/field_floor_held.py": DIAGNOSTIC
    + " (--state: version 3 on version-2 states, a deliberate case-3 diagnostic)",
    # Imports into a new definition, and driver-owned resumes.
    "validation/tissue/heredity_turnover_literature.py": IMPORT
    + " (start_state: sheet70 states into resolved_pump_replacement@1, E07-v1's start; "
    "they predate the D148 ledger fix); also " + DRIVER + " (checkpoint.npz)",
    # A registered driver and a development tool (section 7's table).
    "validation/tissue/e07_v1_run.py": REGISTERED_DRIVER
    + " (E07-v1-B, validation/tissue/e07_v1_protocol.json: checkpoint.npz through the "
    "validation-side Stepper)",
    "validation/division/static_cleft_egg_steps.py": DEVELOPMENT_TOOL
    + " (S0b step 3's step study: start_state takes R-full's J1 state from its record.json)",
    "validation/tissue/excitable_import.py": DEVELOPMENT_TOOL
    + " (Track E M1, D170 ruling 5: start_state takes one world's resolved_pump_tissue@3 "
    "checkpoint into a conduction assay's definition; its import record names the source "
    "manifest's digest and identities)",
    "validation/long_duration/rung0.py": DEVELOPMENT_TOOL
    + " (FR-8 rung 0's restart windows: checkpoint() takes stage 0's R3 state at each window's "
    "start from its kept rows.npz, named by path and revision in rung0_20261119.json; the runs "
    "recorded no source digest, which RUNG0_20261119.md section 9.5 records after the fact)",
    "validation/long_duration/rung1.py": DEVELOPMENT_TOOL
    + " (FR-8 rung 1's re-based windows, RUNG1_20261119.md section 10.3: start_state takes "
    "stage 0's R3 state at each window's start from its kept rows.npz into H2's declared initial "
    "values; each run checks the file's sha256 against the registered digest and records it)",
    # Same-process restart and independent references.
    "validation/betse/fresh_rerun/workers.py": SAME
    + " (restart.npz written and read in one process)",
    "validation/mitochondria/references_r2/steady.py": SAME
    + " (R2, MT-1b's code-blind reference: start_state solves the anchored start state with R2's"
    " own solver from a freshly settled state; it reads no saved Cells state and runs no Cells "
    "engine)",
    "validation/gap_junction_tissue/references/neither_reference.py": SAME
    + " (GJ-N1's code-blind references: start_state lays out stage 1's own steady states over the "
    "network; it reads no saved Cells state and runs no Cells engine)",
    # The probe itself.
    "validation/continuity/probe.py": PROBE,
}
# The only modules that may pass continuity= (development runs, never registered ones).
DEVELOPMENT = {
    "validation/continuity/dev_run.py": "the first consumer: a CPU development run",
}
# Registered drivers and judges never pass a record (section 10, item 6).
REGISTERED = (
    "validation/tissue/heredity_pilot.py",
    "validation/tissue/e07_v1_run.py",
    "validation/tissue/heredity_turnover_literature.py",
)


def _name(call):
    f = call.func
    return f.id if isinstance(f, ast.Name) else f.attr if isinstance(f, ast.Attribute) else None


RESUME_WORDS = ("checkpoint", "state", "restart")  # In the name of an .npz a module np.loads.


def _resume_file(value):
    return value.endswith(".npz") and any(w in value for w in RESUME_WORDS)


def scan(tree):
    """What one module does with saved state, statically."""
    calls = [n for n in ast.walk(tree) if isinstance(n, ast.Call)]
    numpy_loads = [
        c
        for c in calls
        if _name(c) == "load"
        and isinstance(c.func, ast.Attribute)
        and isinstance(c.func.value, ast.Name)
        and c.func.value.id in ("np", "numpy")
    ]
    loads = bool(numpy_loads)
    imports = {
        alias.name if isinstance(node, ast.Import) else f"{node.module}.{alias.name}"
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for alias in node.names
    }
    return dict(
        state_npz=any(
            isinstance(n, ast.Constant) and isinstance(n.value, str) and "state.npz" in n.value
            for n in ast.walk(tree)
        ),
        rebuilds=loads and any(_name(c) == "Checkpoint" for c in calls),
        resumes=any(
            isinstance(n, ast.Constant) and isinstance(n.value, str) and _resume_file(n.value)
            for c in numpy_loads
            for n in ast.walk(c)
        ),
        imports_start=any(
            isinstance(n, ast.FunctionDef) and n.name == "start_state" for n in tree.body
        ),
        continuity=any(k.arg == "continuity" for c in calls for k in c.keywords),
        provenance=any(_name(c) == "provenance" for c in calls),
        imports_continuity=any(
            name == "cells.execution.continuity" or name.startswith("cells.execution.continuity.") for name in imports  # noqa: E501
        ),
    )


def flagged(found):
    return found["state_npz"] or found["rebuilds"] or found["resumes"] or found["imports_start"]


# A module without any of these words has nothing to scan (and is not parsed).
WORDS = ("state.npz", "Checkpoint", ".npz", "start_state", "continuity", "provenance")
NOTHING = scan(ast.parse(""))


@functools.cache
def modules():
    """{path: scan} for every non-test module under validation/ and scripts/ (parsed once)."""
    out = {}
    for base in ("validation", "scripts"):
        for path in sorted((ROOT / base).rglob("*.py")):
            if path.name.startswith("test_"):
                continue
            text = path.read_text()
            found = scan(ast.parse(text)) if any(w in text for w in WORDS) else NOTHING
            out[path.relative_to(ROOT).as_posix()] = found
    return out


def test_every_execution_from_saved_state_is_classified():
    offenders = [name for name, found in modules().items() if flagged(found) and name not in EXEMPT]
    assert not offenders, (
        "Modules reading a snapshot's state.npz, building a Checkpoint from loaded arrays, "
        f"resuming from their own saved state or importing a start state: {offenders}. Load "
        "through io.load_snapshot or batch_io.load_batch_snapshot, or declare a new run from "
        "imported state (rule (b)) and add the module to EXEMPT with its class and reason "
        "(design section 7)."
    )


def test_every_exemption_is_still_flagged():
    found = modules()
    stale = [name for name in EXEMPT if name not in found or not flagged(found[name])]
    assert not stale, f"Remove these EXEMPT entries: {stale}"


def test_only_development_drivers_pass_a_record():
    passing = sorted(name for name, found in modules().items() if found["continuity"])
    assert passing == sorted(DEVELOPMENT), (
        f"Modules passing continuity=: {passing}. Only development drivers may pass a "
        "continuity record (design section 10, item 6); registered runs are the user's."
    )


def test_a_driver_passing_a_record_passes_its_provenance():
    found = modules()
    missing = [name for name in DEVELOPMENT if not found[name]["provenance"]]
    assert not missing, f"These pass continuity= without provenance(admission): {missing}"


def test_registered_drivers_and_judges_never_pass_a_record():
    found = modules()
    judges = [name for name in found if "judge" in Path(name).name]
    assert judges, "no judges found: the glob is wrong"
    passing = [
        name
        for name in (*REGISTERED, *judges)
        if found[name]["continuity"] or found[name]["imports_continuity"]
    ]
    assert not passing, f"Registered drivers or judges reach cells.execution.continuity: {passing}"


def test_engine_call_sites_pass_no_record():
    """No engine call site passes a record in the first landing; batch_io binds children.

    Modules are named by their dotted names, which a source move rewrites (D188)."""
    passing = {}
    for path in sorted((ROOT / "src" / "cells").rglob("*.py")):
        tree = ast.parse(path.read_text())
        calls = [
            c
            for c in ast.walk(tree)
            if isinstance(c, ast.Call) and any(k.arg == "continuity" for k in c.keywords)
        ]
        if calls:
            passing[".".join(path.relative_to(ROOT / "src").with_suffix("").parts)] = calls
    assert sorted(passing) == ["cells.records.batch_io"]
    (call,) = passing["cells.records.batch_io"]
    assert _name(call) == "load_snapshot"
    (value,) = [k.value for k in call.keywords if k.arg == "continuity"]
    assert ast.unparse(value) == "binding.child(world.world_id)"


SOURCES = {  # Synthetic modules: does the scan flag them, and do they pass a record?
    "import numpy as np\nnp.load(path / 'state.npz')\n": (True, False),
    "path = run / 'snapshots' / 'x' / 'world-1' / 'state.npz'\n": (True, False),
    "import numpy as np\nfrom cells.execution.state import Checkpoint\n"
    "a = np.load(f)\nc = Checkpoint(a['s'], a['l'], 0.0, 0, 0)\n": (True, False),
    "from cells.execution.state import Checkpoint\nc = Checkpoint(s, l, 0.0, 0, 0)\n": (False, False),  # noqa: E501
    "from cells.records.io import load_snapshot\nsaved = load_snapshot(path)\n": (False, False),
    "from cells.records.batch_io import load_batch_snapshot\n"
    "saved = load_batch_snapshot(p, continuity=request)\n": (False, True),
    "import numpy as np\nsaved = dict(np.load(out / 'checkpoint.npz'))\n": (True, False),
    "import numpy as np\nlast = np.load(run / 'last-state.npz')\n": (True, False),
    "import numpy as np\nrecords = np.load(out / 'records.npz')\n": (False, False),
    "def start_state(args):\n    return json.loads(path.read_text())['j1']\n": (True, False),
    "def run():\n    def start_state():\n        return None\n": (False, False),  # Not top level.
}


@pytest.mark.parametrize("source", sorted(SOURCES))
def test_the_scan_sees_each_pattern(source):
    found = scan(ast.parse(source))
    assert (flagged(found), found["continuity"]) == SOURCES[source]
