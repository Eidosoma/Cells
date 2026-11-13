"""The bypass guard of checkpoint continuity (docs/CHECKPOINT_CONTINUITY_DESIGN.md, section 7).

One rule: every engine execution that starts from saved state either loads through
io.load_snapshot or batch_io.load_batch_snapshot (refused by default, or admitted by a
continuity record), or declares itself a new run of a definition whose initial values are
imported, recorded and judged on its own. Reading saved bytes without executing from them is
not a migration.

The scan is static, over the modules under validation/ and scripts/ (test files excluded:
they test the read-only tools). It flags a module that
- names a snapshot's ``state.npz``, or
- constructs a Checkpoint from arrays it loads itself (a ``Checkpoint(...)`` call and an
  ``np.load`` call in one module),
and fails unless EXEMPT lists the module with its class and reason (section 7's table). It
also fails for a module that passes ``continuity=`` without being on the development
allow-list, for such a module that does not pass provenance(admission) on, for registered
drivers and judges that pass or import a record, and for engine call sites: in src/cells only
batch_io passes ``continuity=``, to load a cohort's children.

The scan sees names and calls, not what a module does at run time: a module that reads saved
state under another file name (UNSEEN lists the known ones) is outside its reach, and the rule
above still binds it.
"""

import ast
import functools
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]

READ = "read-only comparison or audit, or a writer of its own output: nothing continues"
PAIRED = "its own paired format with identity checks; the numeric part goes through the loaders"
DIAGNOSTIC = (
    "rebuilds and executes outside the loaders as a diagnostic; no output is a continuation "
    "of the run (its rule (b) record of the snapshot digest and both identities is the lead's "
    "to add: outside the first landing's files)"
)
IMPORT = "imports saved states into a new definition (rule (b)); exempt while its runs last"
DRIVER = "driver-owned resume inside one execution snapshot; exempt while its runs last"
SAME = "same-process restart or an independent reference: no source change, or no Cells engine"
PROBE = (
    "the continuity probe: reads checkpoints without the identity comparison to trace them "
    "under S0 and S1, keeps every other loader check, and never continues a run"
)
EXEMPT = {
    # Read-only comparisons, audits and writers of their own output (22).
    "scripts/audit_spatial_extracellular_build.py": READ,
    "scripts/spatial_extracellular_production_audit.py": READ,
    "scripts/verify_windows_build.py": READ
    + " (CORE-005a: a baseline trace row as an explicit test fixture, checked against "
    "load_snapshot restores)",
    "validation/assembly/compare_throughput.py": READ,
    "validation/betse/channel_feedback_audit/feedback_audit_cells.py": READ,
    "validation/betse/channel_feedback_audit/feedback_audit_context.py": READ,
    "validation/betse/channel_history_audit/history_audit_cells.py": READ,
    "validation/betse/channel_history_pilot/preparation_review.py": READ,
    "validation/betse/channel_release_audit/release_audit_cells.py": READ,
    "validation/betse/channel_release_audit/release_audit_context.py": READ,
    "validation/betse/channel_release_pilot/timed_cells_check.py": READ,
    "validation/betse/kinetic_family_audit/family_audit.py": READ,
    "validation/betse/live_recording/matched_windows.py": READ,
    "validation/betse/live_recording_audit/cells_review.py": READ,
    "validation/betse/pump_pilot_diagnosis/diagnose.py": READ,
    "validation/ensemble/jupiter_check.py": READ,
    "validation/ensemble/parallel_cluster.py": READ,
    "validation/ensemble/profile_cluster.py": READ,
    "validation/ensemble/spatial_matrix.py": READ,
    "validation/ensemble/tile_benchmark.py": READ,
    "validation/tissue/open_calcium_trajectory_compare.py": READ,
    "validation/tissue/open_calcium_trajectory_production.py": READ + " (its own full-state.npz)",
    # Own paired formats with identity checks (5).
    "validation/betse/physiology/physiology_boundary_voltage_transition_io.py": PAIRED,
    "validation/betse/physiology/physiology_checkpoint.py": PAIRED,
    "validation/betse/physiology/physiology_protein_block_calendar_io.py": PAIRED,
    "validation/betse/physiology/physiology_protein_checkpoint.py": PAIRED,
    "validation/betse/physiology/physiology_protein_loop_io.py": PAIRED,
    # Rebuild and execute outside the loaders, as diagnostics (2).
    "scripts/profile_dispatch.py": DIAGNOSTIC + " (L4 timing on held states, other XLA flags)",
    "validation/tissue/field_floor_held.py": DIAGNOSTIC
    + " (--state: version 3 on version-2 states, a deliberate case-3 diagnostic)",
    # Imports into a new definition, and driver-owned resumes.
    "validation/tissue/heredity_turnover_literature.py": IMPORT
    + " (start_state: sheet70 states into resolved_pump_replacement@1, E07-v1's start; "
    "they predate the D148 ledger fix); also " + DRIVER + " (checkpoint.npz)",
    "validation/tissue/open_calcium_bath_trajectory_production.py": DRIVER
    + " (its last-state.npz handoff)",
    # Same-process restart and independent references.
    "validation/betse/fresh_rerun/workers.py": SAME
    + " (restart.npz written and read in one process)",
    "validation/tissue/open_calcium_bath_trajectory_oracle.py": SAME + " (the oracle's own state)",
    # The probe itself.
    "validation/continuity/probe.py": PROBE,
}
# Known reads of saved state that the scan does not see (other file names); section 7.
UNSEEN = {
    "validation/tissue/e07_v1_run.py": DRIVER + " (checkpoint.npz through the Stepper)",
    "validation/division/static_cleft_egg_steps.py": IMPORT + " (R-full's J1 state, a record)",
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


def scan(tree):
    """What one module does with saved state, statically."""
    calls = [n for n in ast.walk(tree) if isinstance(n, ast.Call)]
    loads = any(
        _name(c) == "load"
        and isinstance(c.func, ast.Attribute)
        and isinstance(c.func.value, ast.Name)
        and c.func.value.id in ("np", "numpy")
        for c in calls
    )
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
        continuity=any(k.arg == "continuity" for c in calls for k in c.keywords),
        provenance=any(_name(c) == "provenance" for c in calls),
        imports_continuity=any(
            name == "cells.continuity" or name.startswith("cells.continuity.") for name in imports
        ),
    )


def flagged(found):
    return found["state_npz"] or found["rebuilds"]


# A module without any of these words has nothing to scan (and is not parsed).
WORDS = ("state.npz", "Checkpoint", "continuity", "provenance")
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
        "Modules reading a snapshot's state.npz, or building a Checkpoint from loaded arrays, "
        f"outside the loaders: {offenders}. Load through io.load_snapshot or "
        "batch_io.load_batch_snapshot, or declare a new run from imported state (rule (b)) and "
        "add the module to EXEMPT with its class and reason (design section 7)."
    )


def test_every_exemption_is_still_flagged():
    found = modules()
    stale = [name for name in EXEMPT if name not in found or not flagged(found[name])]
    assert not stale, f"Remove these EXEMPT entries: {stale}"


def test_the_known_unseen_cases_stay_unseen():
    found = modules()
    assert set(UNSEEN) <= set(found)
    seen = [name for name in UNSEEN if flagged(found[name])]
    assert not seen, f"The scan now sees these; classify them in EXEMPT instead: {seen}"


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
    assert not passing, f"Registered drivers or judges reach cells.continuity: {passing}"


def test_engine_call_sites_pass_no_record():
    """No engine call site passes a record in the first landing; batch_io binds children."""
    passing = {}
    for path in sorted((ROOT / "src" / "cells").rglob("*.py")):
        tree = ast.parse(path.read_text())
        calls = [
            c
            for c in ast.walk(tree)
            if isinstance(c, ast.Call) and any(k.arg == "continuity" for k in c.keywords)
        ]
        if calls:
            passing[path.relative_to(ROOT / "src" / "cells").as_posix()] = calls
    assert sorted(passing) == ["batch_io.py"]
    (call,) = passing["batch_io.py"]
    assert _name(call) == "load_snapshot"
    (value,) = [k.value for k in call.keywords if k.arg == "continuity"]
    assert ast.unparse(value) == "binding.child(world.world_id)"


SOURCES = {  # Synthetic modules: does the scan flag them, and do they pass a record?
    "import numpy as np\nnp.load(path / 'state.npz')\n": (True, False),
    "path = run / 'snapshots' / 'x' / 'world-1' / 'state.npz'\n": (True, False),
    "import numpy as np\nfrom cells.core.state import Checkpoint\n"
    "a = np.load(f)\nc = Checkpoint(a['s'], a['l'], 0.0, 0, 0)\n": (True, False),
    "from cells.core.state import Checkpoint\nc = Checkpoint(s, l, 0.0, 0, 0)\n": (False, False),
    "from cells.io import load_snapshot\nsaved = load_snapshot(path)\n": (False, False),
    "from cells.batch_io import load_batch_snapshot\n"
    "saved = load_batch_snapshot(p, continuity=request)\n": (False, True),
}


@pytest.mark.parametrize("source", sorted(SOURCES))
def test_the_scan_sees_each_pattern(source):
    found = scan(ast.parse(source))
    assert (flagged(found), found["continuity"]) == SOURCES[source]
