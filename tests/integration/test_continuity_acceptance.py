"""Checkpoint continuity end to end, through admit.py and the loader (design section 10, 4 and 8).

Scratch copies of src/cells in tmp_path, never trees under /mnt/workspaces:
- S0, an unchanged copy, runs the first consumer's cohort uninterrupted (dev_run.py: the
  probe-5 cohort, five rounds of 8 steps) and writes a snapshot after each round. The
  checkpoint is the one after round 1 (step 8): both worlds' next events and the next
  observation are still ahead.
- Each S1 variant is the same copy with one edit, ported from the design's probe patches with
  a count-equals-one check, and is admitted or refused by admit.py propose:

  | Variant  | Edit                                                       | Outcome        |
  | -------- | ---------------------------------------------------------- | -------------- |
  | host     | a phase helper; a host attribute of vector_windows._Round   | admitted       |
  | benign   | a DEBUG phase marker per round in the driving loop          | admitted       |
  | ulp      | the driving loop feeds round 2 a pump table one ulp lower   | refused by O   |
  | builder  | _Round raises later rounds' pump table by 1e-6              | refused by B   |
  | program  | an optimization barrier on dt in the composite step         | refused by P   |
  | constant | the device-check constant arrays one ulp up                 | refused (P, B) |
  | binding  | control_values one ulp lower on the pump table              | refused by B   |
  | observer | one ulp on every floating observation column but times      | refused by H   |
  | missing  | no _Round in core/vector_windows (renamed)                  | cannot decide  |

- The host variant's record admits the resume through batch_io.load_batch_snapshot; the
  resumed run is bitwise equal to the uninterrupted run at every round, and verify_run.py
  passes. The same record is refused under another tree, and a tampered run fails
  verify_run.py.

S0's own probe outputs depend only on S0, the checkpoint, the policy and the probe, so an
injected launcher computes them once. Slow: about seven compiles of the vector window, and
twelve probe processes; run it deliberately, not as a gate.
"""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from validation.continuity import admit

ROOT = Path(__file__).resolve().parents[2]
WINDOW = ["--window-steps", "8", "--recording", "checkpoints"]
APPEND = None  # An edit that appends to its file.
EDITS = {
    "host": [
        ("core/phases.py", APPEND, '\n\ndef acceptance_note():\n    return "host only"\n'),
        (
            "core/vector_windows.py",
            "        self.seconds = perf_counter() - tick\n",
            "        self.seconds = perf_counter() - tick\n"
            "        self.host_note = worlds  # Acceptance-test edit: host only.\n",
        ),
    ],
    "benign": [
        (
            "core/vector_windows.py",
            "        following = _Round(plan, grids, starts, ids, current.stops, False)\n",
            "        following = _Round(plan, grids, starts, ids, current.stops, False)\n"
            '        phases.detail("acceptance.round", index=round_index + 1)  # Host only.\n',
        )
    ],
    "ulp": [
        (
            "core/vector_windows.py",
            "        following = _Round(plan, grids, starts, ids, current.stops, False)\n",
            "        following = _Round(plan, grids, starts, ids, current.stops, False)\n"
            "        moved = following.arrays[2]._replace(\n"
            "            pump=np.nextafter(following.arrays[2].pump, 0.0)\n"
            "        )  # Acceptance-test edit: the loop's own control, one ulp.\n"
            "        following.arrays = (*following.arrays[:2], moved, *following.arrays[3:])\n",
        )
    ],
    "builder": [
        (
            "core/vector_windows.py",
            "        self.arrays = (steps, counts, _stack(tables), index, slots, origin)\n",
            "        table = _stack(tables)\n"
            "        if not first_round:  # Acceptance-test edit: pump controls 1e-6 higher.\n"
            "            table = table._replace(pump=table.pump * (1.0 + 1e-6))\n"
            "        self.arrays = (steps, counts, table, index, slots, origin)\n",
        )
    ],
    "program": [
        (
            "models/pump_composite.py",
            '        """The composite step (module docstring); RK4 for an empty tableau."""\n',
            '        """The composite step (module docstring); RK4 for an empty tableau."""\n'
            "        dt = jax.lax.optimization_barrier(dt)  # Acceptance-test edit: program.\n",
        )
    ],
    "constant": [
        (
            "models/cell_replacement.py",
            "device_check_constants = _model.device_check_constants\n",
            "def device_check_constants(spec):  # Acceptance-test edit: arrays one ulp up.\n"
            "    import jax\n\n"
            "    return jax.tree.map(  # A scalar would print in the jaxpr text: arrays only.\n"
            "        lambda v: np.nextafter(np.asarray(v), np.inf) if np.ndim(v) else v,\n"
            "        _model.device_check_constants(spec),\n"
            "    )\n",
        )
    ],
    "binding": [
        (
            "core/schedule.py",
            "        return replacement.control_values(spec, times)\n",
            "        table = replacement.control_values(spec, times)  # Acceptance-test edit:\n"
            "        return table._replace(pump=np.nextafter(table.pump, 0.0))  # one ulp.\n",
        )
    ],
    "observer": [
        (
            "models/pump_composite.py",
            "            row = {k: v[0] for k, v in vars(observed).items()}\n",
            "            row = {k: v[0] for k, v in vars(observed).items()}\n"
            "            for k in row:  # Acceptance-test edit: an observer change, host only.\n"
            '                if k != "times" and np.issubdtype(np.asarray(row[k]).dtype, '
            "np.floating):\n"
            "                    row[k] = row[k] * (1.0 + 2.0**-52)\n",
        )
    ],
}


def tree(base, name, edits=()):
    """A scratch source root holding a copy of this checkout's src/cells, edited."""
    target = base / name
    shutil.copytree(
        ROOT / "src" / "cells",
        target / "src" / "cells",
        ignore=shutil.ignore_patterns("__pycache__"),
    )
    for relative, old, new in edits:
        path = target / "src" / "cells" / relative
        text = path.read_text()
        if old is APPEND:
            text += new
        else:
            assert text.count(old) == 1, (name, relative, "the edit's anchor moved")
            text = text.replace(old, new)
        path.write_text(text)
    return target


def run_tool(module, *args, source):
    env = dict(
        PATH=os.environ.get("PATH", "/usr/bin:/bin"),
        PYTHONPATH=f"{source / 'src'}:{ROOT}",
        JAX_PLATFORMS="cpu",
        PYTHONDONTWRITEBYTECODE="1",
    )  # The runtime identity's environment fields pass through, as admit.py passes them.
    env.update({k: os.environ[k] for k in admit.ENVIRONMENT if k in os.environ})
    return subprocess.run(
        [sys.executable, "-B", "-m", f"validation.continuity.{module}", *map(str, args)],
        env=env,
        capture_output=True,
        text=True,
    )


class Launcher:
    """admit.py's subprocess launcher; S0's outputs are computed once and copied."""

    def __init__(self, s0):
        self.s0, self.cache = str(s0 / "src"), {}

    def __call__(self, command, env, log, label, args):
        out = Path(command[command.index("--out") + 1])
        key = command[command.index("--parts") + 1]
        if env["PYTHONPATH"].startswith(self.s0 + ":") and key in self.cache:
            shutil.copytree(self.cache[key][0], out)
            shutil.copy(self.cache[key][1], log)
            return 0
        code = admit.launch_subprocess(command, env, log, label, args)
        if env["PYTHONPATH"].startswith(self.s0 + ":"):
            self.cache[key] = (out, log)
        return code


@pytest.fixture(scope="module")
def world(tmp_path_factory):
    base = tmp_path_factory.mktemp("continuity")
    s0 = tree(base, "s0")
    done = run_tool("dev_run", "cohort", "--out", base / "cohort.json", source=s0)
    assert done.returncode == 0, done.stderr
    done = run_tool(
        "dev_run", "run", "--batch", base / "cohort.json", "--out", base / "run0", *WINDOW,
        source=s0,
    )  # fmt: skip
    assert done.returncode == 0, done.stderr
    return dict(base=base, s0=s0, launcher=Launcher(s0), run0=base / "run0")


def admission(world, s1, out):
    """admit.py propose's arguments: the checkpoint after round 1, S0 against s1."""
    argv = [
        "propose",
        "--checkpoint", world["run0"] / "snapshots" / "round-000001",
        "--checkpoint-run", world["run0"],
        "--from-tree", world["s0"],
        "--to-tree", s1,
        "--out", out,
        *WINDOW,
        "--tool-root", ROOT,
    ]  # fmt: skip
    return admit.arguments([str(a) for a in argv])


def propose(world, name):
    s1 = tree(world["base"], name, EDITS.get(name, ()))
    out = world["base"] / f"run-{name}" / "continuity"
    code = admit.propose(admission(world, s1, out), launcher=world["launcher"])
    verdict = json.loads((out / ("proposed.json" if code == 0 else "refusal.json")).read_text())
    return code, verdict, s1, out


def test_host_only_edits_are_admitted_and_resume_bitwise(world):
    code, proposed, s1, out = propose(world, "host")
    assert code == 0
    assert proposed["changed_files"] == ["core/phases.py", "core/vector_windows.py"]
    assert proposed["scope"]["horizon_rounds"] == 4 and proposed["scope"]["overlap_rounds"] == 2
    done = run_tool(
        "admit", "finalise", "--proposed", out / "proposed.json",
        "--admitted-by", "test suite", "--role", "test",
        source=s1,
    )  # fmt: skip
    assert done.returncode == 0, done.stderr
    run = out.parent
    checkpoint = world["run0"] / "snapshots" / "round-000001"
    done = run_tool(
        "dev_run", "resume", "--snapshot", checkpoint, "--checkpoint-run", world["run0"],
        "--out", run, *WINDOW, "--continuity", out / "record.json",
        source=s1,
    )  # fmt: skip
    assert done.returncode == 0, done.stderr
    done = run_tool(
        "dev_run", "compare", world["run0"], run, "--out", world["base"] / "host-compare.json",
        source=s1,
    )  # fmt: skip
    assert done.returncode == 0, done.stdout + done.stderr  # Bitwise equal at every round.
    report = world["base"] / "host-verify.json"
    done = run_tool("verify_run", run, "--out", report, source=s1)
    assert done.returncode == 0, done.stdout
    assert json.loads(report.read_text())["verdict"] == "verified"
    # A tampered run fails the check of its schedule.
    tampered = world["base"] / "tampered"
    shutil.copytree(run, tampered)
    lines = (tampered / "windows.jsonl").read_text().splitlines()
    (tampered / "windows.jsonl").write_text("\n".join(lines[:-1]) + "\n")
    done = run_tool("verify_run", tampered, source=s1)
    assert done.returncode == 1 and "run.files" in done.stdout
    world["host_record"] = out / "record.json"


def test_the_record_is_refused_under_any_other_tree(world):
    """In this process (this checkout, S0's source) the host record binds nothing."""
    from cells import continuity
    from cells.batch_io import load_batch_snapshot
    from cells.core.specs import ConfigError

    checkpoint = world["run0"] / "snapshots" / "round-000001"
    assert load_batch_snapshot(checkpoint).admission is None  # Same source: no record needed.
    record = world.get("host_record")
    if record is None:
        pytest.skip("needs the host variant's record")
    request = continuity.Request(
        record, path="vector_windows", policy={"window_steps": 8, "recording": "checkpoints"}
    )
    with pytest.raises(ConfigError, match="to source is not this installation's"):
        load_batch_snapshot(checkpoint, continuity=request)


def test_a_benign_loop_edit_is_admitted(world):
    code, proposed, _, _ = propose(world, "benign")
    assert code == 0, proposed.get("reason")
    assert proposed["changed_files"] == ["core/vector_windows.py"]


def test_a_one_ulp_loop_control_is_refused_by_the_overlap_arguments(world):
    code, refusal, _, _ = propose(world, "ulp")
    assert code == 2
    comparison = refusal["comparison"]
    assert all(comparison[p]["identical"] for p in ("P0", "P", "B", "H", "texts"))
    checks = comparison["O"]["checks"]
    assert not checks["arguments_identical"] and not checks["arguments_equal_own_rounds_S1"]
    assert checks["arguments_equal_own_rounds_S0"]


@pytest.mark.parametrize(
    ("name", "differ", "same"),
    [
        ("builder", {"B"}, {"P0", "P", "H", "texts"}),  # Later rounds only.
        ("program", {"P0", "P", "texts"}, {"B", "H"}),
        # The texts do not carry a closed-over array's values; its digests and bindings do.
        # (A scalar constant prints as a literal, so the edit leaves the scalar alone.)
        ("constant", {"P0", "P", "B"}, {"H", "texts"}),
        ("binding", {"P0", "B"}, {"P", "H", "texts"}),
        ("observer", {"H"}, {"P0", "P", "B", "texts"}),
    ],
)
def test_an_edit_reaching_the_run_is_refused_before_the_overlap(world, name, differ, same):
    code, refusal, _, out = propose(world, name)
    assert code == 2
    comparison = refusal["comparison"]
    differing = {p for p, row in comparison.items() if not row["identical"]}
    assert differ <= differing and not same & differing, differing
    assert comparison["first_round_equals_P0_S1"]["identical"]  # Its own builders, as captured.
    assert not (out / "overlap-s1").exists()  # O is not run once P, B or H refuses.


def test_a_tree_without_an_entry_point_cannot_decide(world):
    s1 = tree(world["base"], "missing")
    path = s1 / "src" / "cells" / "core" / "vector_windows.py"
    text = path.read_text()
    assert text.count("_Round(") == 2 and text.count("class _Round:") == 1
    path.write_text(text.replace("_Round", "_RoundBuilder"))
    out = world["base"] / "run-missing" / "continuity"
    assert admit.propose(admission(world, s1, out), launcher=world["launcher"]) == 3
    refusal = json.loads((out / "refusal.json").read_text())
    assert refusal["verdict"] == "cannot_decide"
    assert "cells.core.vector_windows._Round" in refusal["reason"]
