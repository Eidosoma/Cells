"""The one generic driver of the looping replay packages (FR-11; LOOPING_REPLAY_DESIGN §1, §2).

Usage: python -m validation.replay.driver BUILDER OUT
  BUILDER  a builder of this package (BUILDERS);
  OUT      a new directory, under /mnt/workspaces/Cells/replay-<date>/.

It writes the builder's package through the shared windowed output path
(cells.window_io.write_windowed_run) with recording "observations" (only the observed rows, which
the builder places in the last period) and the builder's run view request (view=, with its loop),
then checks the view against its files (run_view.validate) and writes OUT.result.json beside OUT:
the loop block or the reason it was left out, the engine models and source, and the package's
size against the viewer's limit.

Exit 0: the run is a loop. Exit 1: the run completed but is not a loop (the view says why, under
unstated) or the package is above the size limit; the run stays as failed evidence. Exit 2: refused
before any output, for instance from a checkout (a package names its engine source, so it runs
from an execution snapshot of the checkout).
"""

import importlib
import json
import sys
from pathlib import Path

from cells import run_view
from cells.core.specs import parse_spec
from cells.core.windows import WindowPolicy
from cells.window_io import write_windowed_run

BUILDERS = {"planarian": "validation.replay.planarian"}
LIMIT_BYTES = 1_000_000  # The viewer's limit per package (about 1 MB, §1).


def package_bytes(out):
    """The bytes the viewer loads: the view and the chunks of observed rows it names."""
    view = json.loads((out / run_view.FILE).read_text())
    files = {part["file"] for base in view["time"]["bases"] for part in base["files"]}
    return (out / run_view.FILE).stat().st_size + sum((out / f).stat().st_size for f in files)


def write(name, out):
    """Write one package; returns (exit code, result record)."""
    out = Path(out)
    builder = importlib.import_module(BUILDERS[name])
    package = builder.package()
    spec = parse_spec(package.definition)
    policy = WindowPolicy(window_steps=package.window_steps, recording="observations")
    try:
        write_windowed_run(
            out,
            spec,
            policy,
            view=package.request,
            provenance={"operation": "windowed_fresh", "replay_package": name},
        )
    except run_view.ViewRefused as exc:
        return 2, {"package": name, "status": "refused", "why": str(exc)}
    view = json.loads((out / run_view.FILE).read_text())
    run_view.validate(view, out)
    loop = view.get(run_view.LOOP_KEY)
    size = package_bytes(out)
    record = {
        "package": name,
        "builder": BUILDERS[name],
        "status": "loop" if loop is not None else "not a loop",
        "loop": loop,
        "why_not": [u["why"] for u in view["unstated"] if u["id"] == run_view.LOOP_KEY],
        "engine_models": view["run"]["engine_models"],
        "source": view["run"].get("source"),
        "end": view["run"].get("end"),
        "package_bytes": size,
        "limit_bytes": LIMIT_BYTES,
        "observed_rows": sum(
            part["rows"][1] - part["rows"][0]
            for base in view["time"]["bases"]
            if base["id"] == "observation"
            for part in base["files"]
        ),
    }
    return (0 if loop is not None and size <= LIMIT_BYTES else 1), record


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 2 or argv[0] not in BUILDERS:
        print(__doc__, file=sys.stderr)
        return 2
    out = Path(argv[1])
    code, record = write(argv[0], out)
    result = out.with_name(out.name + ".result.json")
    result.write_text(json.dumps(record, indent=1, sort_keys=True) + "\n")
    print(result, record["status"])
    return code


if __name__ == "__main__":
    sys.exit(main())
