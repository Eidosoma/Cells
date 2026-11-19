"""crossrev's sets of one snapshot (the gates' cross-revision runner and record maker).

  run     SNAPSHOT OUT RECORD   each set of the snapshot, compared with the record's (the gates)
  record  SNAPSHOT OUT          a new record of the snapshot (the record maker), each set compared
                                with its set in an earlier record when --previous is given

Per set it runs the set's actions (jaxprs, bindings, and check for the operators' own modules) from
the snapshot's root, with PYTHONPATH at the snapshot, at nice 10, into OUT/SET. Then
composite_crossrev compare reads RECORD/SET and OUT/SET; the record side goes first, because compare
reads only its first argument's files. Finally the two set folders' file listings are diffed. The
layout is the shell runner's, so the gates' greps read it unchanged: OUT/SET, OUT/SET-ACTION.log,
OUT/compare-SET.txt, OUT/listing-SET.diff, and OUT/crossrev.log with its line forms. Exit 0 when
every set is identical with the same listing.

The sets are fail-closed (the lead's ruling, 18 November 2026). Every set the runner knows (SETS, in
ORDER) is required unless --sets names fewer. A required set missing from the record (or from the
--previous record) fails the run, unless the call names it with --allow-missing SET. The log
records that, and no gate passes the flag. A record folder with a dash in its name is a superseded
copy, kept for the record's renewal notes, and is skipped. Any other folder the runner does not know
is refused, so a new set is added here before a record holding it is used. A snapshot lacking a set
fails that set's actions, so a branch older than a set's landing merges main first.

This supersedes these runners, which stay byte for byte because recorded runs cite them:
- the ten-set runner /mnt/workspaces/Cells/crossrev-acceptances-20261118/tools/crossrev.sh,
  installed as d198-retire-20261117/tools/crossrev.sh and d188-m1-20261117/tools/crossrev.sh;
- their nine-set originals (crossrev.sh.nine-sets-20261118);
- the record maker /mnt/workspaces/Cells/core-fixes-20261116/tools/crossrev-record.sh.

Usage:
  python crossrev_sets.py run SNAPSHOT OUT RECORD [--sets SET ...] [--allow-missing SET ...]
  python crossrev_sets.py record SNAPSHOT OUT [--sets SET ...] [--previous RECORD]
                                              [--allow-missing SET ...]
"""

import argparse
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

COMPOSITE = "validation.tissue.composite_crossrev"
# set: (module, actions, whether the module takes the set's name after the output directory)
SETS = {
    "base": (COMPOSITE, ("jaxprs", "bindings"), True),
    "qualification": (COMPOSITE, ("jaxprs", "bindings"), True),
    "injection": (COMPOSITE, ("jaxprs", "bindings"), True),
    "volume": (COMPOSITE, ("jaxprs", "bindings"), True),
    "kinds": (COMPOSITE, ("jaxprs", "bindings"), True),
    "division": ("validation.division.division_crossrev", ("jaxprs", "bindings", "check"), False),
    "species": ("validation.tissue.secreted_species_crossrev", ("jaxprs", "bindings", "check"),
                False),
    "reactions": ("validation.tissue.species_reactions_crossrev", ("jaxprs", "bindings", "check"),
                  False),
    "coupling": ("validation.tissue.regulated_availability_crossrev",
                 ("jaxprs", "bindings", "check"), False),
    "acceptances": (COMPOSITE, ("jaxprs", "bindings"), True),
    "replication": (COMPOSITE, ("jaxprs", "bindings"), True),
}
ORDER = tuple(SETS)
PYTHON = "/mnt/workspaces/Cells/venv-cpu/bin/python"


def record_sets(record):
    """The record's known sets in ORDER (superseded copies skipped); SystemExit on an unknown
    folder."""
    names = [p.name for p in Path(record).iterdir() if p.is_dir() and "-" not in p.name]
    unknown = sorted(n for n in names if n not in SETS)
    if unknown:
        raise SystemExit(f"Refused: the record holds sets this runner does not know: {unknown} "
                         "(add them to SETS first)")
    return [s for s in ORDER if s in names]


def chosen(sets):
    """The required sets: those named, or every known set (fail-closed)."""
    if not sets:
        return list(ORDER)
    unknown = sorted(set(sets) - set(SETS))
    if unknown:
        raise SystemExit(f"Refused: unknown sets {unknown} (known: {list(ORDER)})")
    return [s for s in ORDER if s in sets]


def commands(snapshot, out, name, python):
    """[(action, argv)] of one set, run from the snapshot's root."""
    module, actions, takes_name = SETS[name]
    target = str(Path(out) / name)
    named = (name,) if takes_name else ()
    return [(a, [python, "-B", "-u", "-m", module, a, target, *(named if a != "check" else ())])
            for a in actions]


def environment(snapshot):
    env = dict(os.environ, JAX_PLATFORMS="cpu", CUDA_VISIBLE_DEVICES="",
               PYTHONDONTWRITEBYTECODE="1", JAX_ENABLE_X64="1")
    env["PYTHONPATH"] = f"{snapshot}/src:{snapshot}"
    return env


def call(argv, cwd, env, log_path):
    """Run argv at nice 10, its output into log_path; its exit code."""
    with open(log_path, "w") as log:
        return subprocess.run(["nice", "-n", "10", *argv], cwd=cwd, env=env, stdout=log,
                              stderr=subprocess.STDOUT).returncode


def listing(path):
    return sorted(p.name for p in Path(path).iterdir()) if Path(path).is_dir() else None


def sweep(snapshot, out, sets, against, python, log, call=call, allow_missing=()):
    """Each set's actions, then its compare with `against` (a record, or None): the exit status.
    A set the record lacks fails, unless allow_missing names it."""
    snapshot, out = Path(snapshot).resolve(), Path(out)
    env, status = environment(snapshot), 0
    for name in sets:
        for action, argv in commands(snapshot, out, name, python):
            start = time.time()
            rc = call(argv, snapshot, env, out / f"{name}-{action}.log")
            status |= rc != 0
            log(f"{name} {action} exit {rc} seconds {round(time.time() - start)}")
        if against is None:
            continue
        if not (Path(against) / name).is_dir():
            if name in allow_missing:
                log(f"compare {name} skipped: the record has no {name} set "
                    "(allowed by --allow-missing)")
            else:
                status = 1
                log(f"compare {name} exit 1: the record has no {name} set (fail-closed; "
                    f"--allow-missing {name} would accept it)")
            continue
        compare = out / f"compare-{name}.txt"
        rc = call([python, "-B", "-m", COMPOSITE, "compare", str(Path(against) / name),
                   str(out / name)], snapshot, env, compare)
        last = (compare.read_text().strip().splitlines() or [""])[-1]
        mine, theirs = listing(out / name), listing(Path(against) / name)
        (out / f"listing-{name}.diff").write_text(
            "" if mine == theirs else "\n".join(
                [f"< {n}" for n in sorted(set(theirs or []) - set(mine or []))]
                + [f"> {n}" for n in sorted(set(mine or []) - set(theirs or []))]) + "\n")
        same = mine == theirs
        status |= rc != 0 or not same
        log(f"compare {name} exit {rc}: {last}; file listing {'same' if same else 'DIFFERS'}")
    return int(status)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = p.add_subparsers(dest="mode", required=True)
    for mode in ("run", "record"):
        m = sub.add_parser(mode)
        m.add_argument("snapshot")
        m.add_argument("out")
        if mode == "run":
            m.add_argument("record")
        else:
            m.add_argument("--previous", help="an earlier record to compare each set with")
        m.add_argument("--sets", nargs="+")
        m.add_argument("--allow-missing", nargs="+", default=[],
                       help="required sets the record may lack (logged; never in a gate)")
        m.add_argument("--python", default=PYTHON)
    a = p.parse_args(argv)
    snapshot, out = Path(a.snapshot), Path(a.out)
    if not (snapshot / "SNAPSHOT.json").is_file():
        raise SystemExit(f"Refused: {snapshot} is not an execution snapshot")
    against = a.record if a.mode == "run" else a.previous
    sets = chosen(a.sets)
    allowed = chosen(a.allow_missing) if a.allow_missing else []
    if set(allowed) - set(sets):
        raise SystemExit(f"Refused: --allow-missing names sets not required: "
                         f"{sorted(set(allowed) - set(sets))}")
    if against is not None:
        record_sets(against)  # Refuses a folder this runner does not know.
    out.mkdir(parents=True, exist_ok=True)

    def log(line):
        with open(out / "crossrev.log", "a") as f:
            f.write(f"{datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')} {line}\n")

    log(f"crossrev {a.mode} {snapshot} sets {' '.join(sets)} affinity "
        f"{','.join(map(str, sorted(os.sched_getaffinity(0))))}"
        + (f" against {against}" if against else "")
        + (f"; allowed missing from the record: {' '.join(allowed)}" if allowed else ""))
    status = sweep(snapshot, out, sets, against, a.python, log, allow_missing=set(allowed))
    log(f"done status {status}")
    return status


if __name__ == "__main__":
    sys.exit(main())
