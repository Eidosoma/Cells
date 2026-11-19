#!/usr/bin/env bash
# Small runs written by the engine's own run-view writer, kept as fixtures for the adapter's
# reading of a view (tools/adapt_run.py, adapt_engine_view; schema/RUN_VIEW.md, "The engine's view").
#
# The writer is on main since 050aa741 (16 November 2026); before, it lived on the development branch
# run-view-d154, whose revisions main keeps through its merge. This script exports one revision with
# `git archive` (src, tests and validation; no worktree is registered), runs the engine's own
# unit-test worlds there with the engine's Python, out of process, and
# copies what the writer wrote into tests/engine-views/run-view-<rev8>/. Nothing of the engine is
# copied into the visualizer: only the runs' saved files (view.json and the arrays it names, the
# definition and the summary).
#
#   secretion  the worked example's short world (tests/run_view_fixtures.py, secretion(): one cell
#              makes S and secretes it into a finite node that leaks to a held bath; 10 steps of
#              1 ms, 6 observed rows), through io.write_run. No declaration is planted: turnover and
#              exchange declare their own run-view items at this revision.
#   subset     the same short secretion world through io.write_run with a recording subset, as the engine's
#              own test of it records one (tests/unit/test_run_view.py): four fields, of the species only S,
#              every second observed row. No declaration is planted.
#   increments the same world with a recording subset that keeps the two increments in place of the
#              amounts (amount_increment, extracellular_amount_increment), of the species only S: from
#              the revision on which @3 declares its RECORD_REFERENCES, each is stored over a fixed
#              reference that the view names. No declaration is planted.
#   kinds      a kind world: FR-4's development world without its transporter, as the engine's own test
#              of the inner model's kinds builds it (tests/unit/test_run_view.py), run for 10 steps:
#              @3 alone with its passive routes (a set whose `carries` lists species) and its proton
#              buffer (pH on the node set). Written only where the revision's writer reads the kinds'
#              declarations; otherwise skipped, with the writer's reason in written.json.
#   division   S5's compact partition world (tests/partition_fixtures.py, divided(): a cell divides
#              into two daughters at 2 ms; 5 observed rows), through window_io.write_windowed_run
#              with two windows. The membrane state's and the partition's run-view declarations are
#              planted for the run only, exactly as the engine's own test of it does
#              (tests/run_view_fixtures.py, declare_division): those operators do not declare them
#              in their files yet, so the layer "division" and its label are the test's words.
#
# Three more worlds show the core seams pass's format items (docs/CORE_SEAMS_DESIGN.md §9 and §4.3;
# on main from d64fb664, 18 November 2026). Each is written only where the revision's engine has what
# it needs; otherwise skipped, with the reason in written.json.
#   factors    heredity cell D, as the engine's own test of the routing door into @3 builds it
#              (tests/unit/test_surface_pump_v3_populations.py, heredity(("f_b", "f_c")): its first
#              channel population declares two factors of the test's planted factor source,
#              tests.factor@1 from tests/kind_fixtures.py, registered for the run only), observed at
#              each of its 4 steps, through io.write_run with a recording subset of five fields: the
#              membrane's Na/K pump (its per_cycle), the channel set's factors and the note on
#              channel_availability.
#   condition  FR-5's development world, arm R, as the engine's own test of the pH condition's set
#              builds it (tests/unit/test_run_view_formats.py: development_world(fr5_world(ARM_R))),
#              run for 10 steps as the kind world is (its damage schedule's points after the shortened
#              end left out, as fr5_world does for a shortened horizon), with a recording subset of
#              five fields: the pH condition's kind as a word and its law under laws.
#   dose       the bath schedule's dose world (scheduled_bath_composition@1), as the engine's own test
#              of a field reference builds it (tests/unit/test_run_view_door_s.py: a dose of cargo S at
#              4 ms, 8 steps of 1 ms, observed at every step), written through io.write_run without a
#              view and given its view afterwards by run_view.write_view, as a run already on disk: a
#              record stored over a field the run did not save ({"field": X}) and X's unstated entry.
#              The bath schedule's layer is planted for the run only, as that test does: the operator
#              does not declare it in its file yet, so the layer "bath" and its label are the test's.
#
# The engine's source. An export made with `git archive` has no .git and no execution snapshot's
# record (SNAPSHOT.json), and the writer learns its source only from such a record: each view
# therefore lists the engine source as unstated, with the writer's own reason, and has no run.source.
# The secretion run (not the subset run) is given the revision's short form as the caller's label (run.revision), which
# this script plants; the division run is given none. Neither is the engine's own word for its source.
# The division run's helper (declare_division) also patches the writer's source lookup to give none,
# as the engine's tests do; from an export the lookup gives none anyway, as the unpatched secretion run shows.
#
# The engine's Python runs as its own memory-capped unit through the project's wrapper
# (scripts/run_detached.sh, cells.slice), never in this shell: the script waits for the unit, and the
# run writes its own log beside the export (write.log).
#
# Usage: tools/make_engine_view_fixture.sh [REVISION]   (default: main at 89bd2ffb, 19 November 2026,
# whose writer holds the core seams pass's format items; main's 050aa741 and b5d3faf0 made the folders
# run-view-050aa741 and run-view-b5d3faf0 with the first five worlds, and the development branch's
# fd008813 made run-view-fd008813 with its first three). Environment: CELLS_VIEW_EXPORT (where the export goes), CELLS_PYTHON (the
# engine's Python), CELLS_CPUS (the processors the unit is pinned to), CELLS_WRAPPER (run_detached.sh).
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VISUALIZER="$(dirname "$HERE")"
TOP="$(git -C "$VISUALIZER" rev-parse --show-toplevel)"
REVISION="$(git -C "$TOP" rev-parse --verify "${1:-89bd2ffba7a0732a1dc20a6c2e61f86786c9b535}^{commit}")"
SHORT="${REVISION:0:8}"
# Where the revision stands: on main's own line, or a development branch's revision that main holds through a merge.
# (grep reads all its input: with pipefail, grep -q stopping early would fail rev-list on a closed pipe.)
if git -C "$TOP" rev-list --first-parent main | grep -x "$REVISION" > /dev/null; then
  WHERE="main at \`$SHORT\`: the writer is on main since 050aa741 (16 November 2026)"
elif git -C "$TOP" merge-base --is-ancestor "$REVISION" main; then
  WHERE="the development branch \`run-view-d154\` at \`$SHORT\`, which main holds through its merge; the writer is on main since 050aa741 (16 November 2026)"
else
  WHERE="the development branch \`run-view-d154\` at \`$SHORT\`, not on main"
fi
# Whether the revision's writer holds the core seams pass's three format items (main's merge d64fb664, 18 November 2026).
if git -C "$TOP" merge-base --is-ancestor d64fb66447290d0c263602248229ef488bc9a3eb "$REVISION"; then
  ITEMS="Its writer holds the core seams pass's three format items (docs/CORE_SEAMS_DESIGN.md §9, on main from \`d64fb664\`, 18 November 2026): kinds are words with a law's ID under \`laws\`; each species a route carries moves with its own flux, coupled stoichiometry being \`per_cycle\`; a reference constant only where a record names it, and a \`{\"field\": X}\` reference only with X's \`unstated\` entry. And where a channel population declares factors, the channel set gives each population's \`factors\`."
else
  ITEMS="Its writer is from before the core seams pass's three format items (on main from \`d64fb664\`, 18 November 2026)."
fi
EXPORT="${CELLS_VIEW_EXPORT:-/mnt/workspaces/Cells/visualizer-scratch-20261116-02/run-view-$SHORT}"
PYTHON="${CELLS_PYTHON:-/mnt/workspaces/Cells/venv-cpu/bin/python}"
CPUS="${CELLS_CPUS:-12-15,28-31}"
DEST="$VISUALIZER/tests/engine-views/run-view-$SHORT"
UNIT="viz-view-fixture-$(date -u +%Y%m%d%H%M%S)"
# The wrapper is the main checkout's (a worktree of the visualizer branch may not hold scripts/).
MAIN="$(dirname "$(git -C "$TOP" rev-parse --path-format=absolute --git-common-dir)")"
WRAPPER="${CELLS_WRAPPER:-$MAIN/scripts/run_detached.sh}"
[ -x "$WRAPPER" ] || { echo "no run_detached.sh at $WRAPPER: set CELLS_WRAPPER" >&2; exit 1; }

if [ ! -f "$EXPORT/src/cells/records/run_view.py" ]; then
  mkdir -p "$EXPORT"
  git -C "$TOP" archive "$REVISION" src tests validation | tar -x -C "$EXPORT"
fi
WORK="$EXPORT/written"
PROGRAM="$EXPORT/write_views.py"
LOG="$EXPORT/write.log"
rm -rf "$WORK" "$LOG"
mkdir -p "$WORK"

# The run, as a file the unit can start: the engine's own test worlds and helpers, through the shared output paths.
cat > "$PROGRAM" <<'PYTHON'
import json
import sys
from pathlib import Path

import pytest

from cells.records import run_view
from cells.execution.runner import run
from cells.definitions.specs import parse_spec
from cells.execution.windows import WindowPolicy
from cells.records.io import write_run
from cells.records.window_io import write_windowed_run
from tests import partition_fixtures as pf
from tests.run_view_fixtures import declare_division, secretion

out, short = Path(sys.argv[1]), sys.argv[2]
label = "the visualizer's fixture of the run view's writer"
# run.revision is a caller's label, planted here: the export has no execution snapshot, so the writer states no source.
write_run(
    out / "secretion",
    run(secretion()),
    view=run_view.Request({"id": "secretion-short", "label": f"{label}: the short secretion world", "revision": short}),
)
keep = run_view.Recording(fields=("membrane_voltage_V", "cell_potential_V", "amount", "exchange_moved_fmol"), elements={"species": ("S",)}, every=2)
write_run(
    out / "subset",
    run(secretion()),
    view=run_view.Request({"id": "secretion-subset", "label": f"{label}: the short secretion world, a recorded subset"}, recording=keep),
)
skipped = {}
increments = run_view.Recording(fields=("membrane_voltage_V", "cell_potential_V", "amount_increment", "extracellular_amount_increment"), elements={"species": ("S",)})
write_run(
    out / "increments",
    run(secretion()),
    view=run_view.Request({"id": "secretion-increments", "label": f"{label}: the short secretion world, its increments recorded"}, recording=increments),
)
try:  # The kinds' declarations are read by the writer from b08af640 on; before, it refuses the kind world.
    from validation.compartment_ph_engine import definitions as defs

    raw = defs.development_world(defs.fr4_world())
    raw["model"].pop("transporters")
    dt = raw["execution"]["dt"]
    raw["experiment"]["end_time"] = 10 * dt
    raw["experiment"]["observation_times"] = [k * dt for k in range(0, 11, 2)]
    raw["execution"]["max_steps"] = 18
    spec = parse_spec(raw)
    write_run(out / "kinds", run(spec), view=run_view.Request({"id": "kinds-short", "label": f"{label}: a kind world (passive routes and a proton buffer)"}))
except (run_view.ViewRefused, ImportError, AttributeError, KeyError) as exc:
    skipped["kinds"] = f"{type(exc).__name__}: {exc}"
with pytest.MonkeyPatch.context() as patch:
    declare_division(patch)
    raw = pf.divided()
    raw["experiment"]["observation_times"] = [0.0, 0.001, 0.002, 0.003, 0.004]
    write_windowed_run(
        out / "division",
        parse_spec(raw),
        WindowPolicy(2, "full"),
        view=run_view.Request({"id": "division-short", "label": f"{label}: S5's partition world"}),
    )
# The core seams pass's format items (docs/CORE_SEAMS_DESIGN.md §9, §4.3; on main from d64fb664): each world only where the
# revision's engine has what it needs, otherwise skipped with the reason.
from cells.definitions.specs import ConfigError

MISSING = (ConfigError, ImportError, AttributeError, KeyError, TypeError, ValueError)
try:  # The routing door into @3: a channel population that declares factors of the test's planted factor source.
    from cells.registry import kind_registry
    from tests import kind_fixtures as kf
    from tests.unit.test_surface_pump_v3_populations import heredity

    with kind_registry.scope(kf.registry(kf.factor_source())):
        raw = heredity(("f_b", "f_c"))
        dt = raw["execution"]["dt"]
        raw["experiment"]["observation_times"] = [k * dt for k in range(0, 5)]
        door = run_view.Recording(fields=("membrane_voltage_V", "cell_potential_V", "channel_availability", "channel_transferred", "pump_cycles"))
        write_run(out / "factors", run(parse_spec(raw)), view=run_view.Request({"id": "factors-short", "label": f"{label}: heredity cell D, its first channel population factored"}, recording=door))
except MISSING as exc:
    skipped["factors"] = f"{type(exc).__name__}: {exc}"
try:  # FR-5's development world: the pH condition's set, its kind a word and its law under laws.
    from validation.compartment_ph_engine import definitions as defs
    from validation.compartment_ph_engine.parameters import ARM_R

    raw = defs.development_world(defs.fr5_world(ARM_R))
    dt = raw["execution"]["dt"]
    end = 10 * dt
    raw["experiment"]["end_time"] = end
    raw["experiment"]["observation_times"] = [k * dt for k in range(0, 11, 2)]
    raw["execution"]["max_steps"] = 18
    for control in raw["experiment"].get("damage_controls") or []:  # As fr5_world keeps a shortened horizon's points.
        for key in ("injury", "resealing"):
            control[key] = [point for point in control[key] if point["time"] <= end]
    fr5 = run_view.Recording(fields=("membrane_voltage_V", "cell_potential_V", "amount", "passive_transferred", "ph_condition_factor"))
    write_run(out / "condition", run(parse_spec(raw)), view=run_view.Request({"id": "condition-short", "label": f"{label}: FR-5's development world, arm R"}, recording=fr5))
except MISSING as exc:
    skipped["condition"] = f"{type(exc).__name__}: {exc}"
try:  # A run on disk given its view afterwards: a record stored over a field the run did not save, and its unstated entry.
    from tests.run_view_fixtures import layers, plant
    from validation.tissue import bath_schedule_fixtures as bfx
    from validation.tissue import secreted_species_fixtures as fx

    with pytest.MonkeyPatch.context() as patch:
        plant(patch, bfx.LAW, VIEW_LAYERS=layers("bath", "Bath composition"))
        dt, end, dose = 1e-3, 0.008, 0.004
        raw = bfx.dosed_world(dt=dt, end=end, observation_times=fx.grid_times(end, dt, dt))
        raw = bfx.with_bath_schedule(raw, ["bath"], bfx.CARGO, [(dose, ["bath"], {"cargo": 5e-4})])
        write_run(out / "dose", run(parse_spec(raw)))
        run_view.write_view(out / "dose", run={"id": "dose-on-disk", "label": f"{label}: the bath schedule's dose, a run on disk"})
except MISSING as exc:
    skipped["dose"] = f"{type(exc).__name__}: {exc}"
(out / "written.json").write_text(json.dumps({"worlds": sorted(p.name for p in out.iterdir() if p.is_dir()), "skipped": skipped}) + "\n")
print("written:", ", ".join(sorted(p.name for p in out.iterdir() if p.is_dir())))
PYTHON

"$WRAPPER" "$UNIT" 6G --cpus "$CPUS" --oom-first --runtime-max 900 --dir "$EXPORT" \
  --env PYTHONPATH=src:. --env JAX_ENABLE_X64=1 --env JAX_PLATFORMS=cpu --env CUDA_VISIBLE_DEVICES= --env PYTHONDONTWRITEBYTECODE=1 \
  -- /bin/bash -c "exec '$PYTHON' '$PROGRAM' '$WORK' '$SHORT' > '$LOG' 2>&1"
until ! systemctl --user is-active -q "cells-$UNIT"; do sleep 15; done
journalctl --user -u "cells-$UNIT" -n 5 --no-pager || true
if [ ! -f "$WORK/written.json" ]; then
  echo "the writer's run did not finish: see $LOG and the unit's journal (cells-$UNIT)" >&2
  tail -20 "$LOG" >&2 || true
  exit 1
fi

rm -rf "$DEST"
for world in secretion subset increments kinds division factors condition dose; do
  [ -f "$WORK/$world/view.json" ] || continue
  mkdir -p "$DEST/$world"
  cp "$WORK/$world/view.json" "$WORK/$world/resolved_config.json" "$WORK/$world/summary.json" "$DEST/$world/"
  if [ -f "$WORK/$world/trajectory.npz" ]; then cp "$WORK/$world/trajectory.npz" "$DEST/$world/"; fi
  if [ -f "$WORK/$world/windows.jsonl" ]; then cp "$WORK/$world/windows.jsonl" "$DEST/$world/" && cp -r "$WORK/$world/chunks" "$DEST/$world/"; fi
done
if grep -rlE '/(home|mnt|Users|tmp|var|root|opt|srv)/' "$DEST"; then
  echo "a kept file names a machine path: not kept" >&2
  rm -rf "$DEST"
  exit 1
fi
cat > "$DEST/README.md" <<NOTE
# Runs written by the engine's run-view writer ($SHORT)

Written by \`tools/make_engine_view_fixture.sh $SHORT\` at revision \`$REVISION\`, that is $WHERE.
Exported with \`git archive\` (src, tests, validation) and run with the engine's own Python as a
memory-capped unit (\`scripts/run_detached.sh\`). Every
file here is the writer's own output, kept as written: \`view.json\` (\`cells.run_view@1\`), the
arrays it names, \`resolved_config.json\` and \`summary.json\` (the manifest and the final checkpoint
are left out). Do not edit by hand; run the script again.

- \`secretion\`: the worked example's short world (one cell makes S and secretes it into a finite
  node that leaks to a held bath; 10 steps, 6 observed rows) through \`io.write_run\`. No declaration
  is planted.
- \`subset\`: the same world through \`io.write_run\` with a recording subset, as the engine's own
  test records one: four fields, of the species only S, every second observed row. Nothing is
  planted.
- \`increments\` (where written): the same world with a recording subset that keeps the two
  increments in place of the amounts, of the species only S. Nothing is planted.
- \`kinds\` (where written): FR-4's development world without its transporter, as the engine's own
  test of the inner model's kinds builds it, run for 10 steps: @3 alone with its passive routes
  and its proton buffer. Nothing is planted. The writer reads the kinds' declarations only from
  b08af640 on; written.json in the export says why where it was skipped.
- \`division\`: S5's compact partition world (a cell divides into two daughters) through
  \`window_io.write_windowed_run\` with two windows. The membrane state's and the partition's
  run-view declarations are planted for the run only, as the engine's own test does
  (\`declare_division\`): the layer "division" and its label are the test's words, not the
  operators' files'.
- \`factors\` (where written): heredity cell D, as the engine's own test of the routing door into @3
  builds it: its first channel population declares two factors of the test's **planted** factor
  source (\`tests.factor@1\`, registered for the run only). Observed at each of its 4 steps, with a
  recording subset of five fields. It shows the membrane's Na/K pump (\`per_cycle\`), the channel
  set's \`factors\` and the note on \`channel_availability\`.
- \`condition\` (where written): FR-5's development world, arm R, as the engine's own test of the pH
  condition's set builds it, run for 10 steps (its damage schedule's points after that end left out,
  as \`fr5_world\` does for a shortened horizon), with a recording subset of five fields. It shows
  the pH condition's kind as a word and its law under \`laws\`. Nothing is planted.
- \`dose\` (where written): the bath schedule's dose world (8 steps, a dose of cargo S at 4 ms),
  written through \`io.write_run\` without a view and given its view afterwards by
  \`run_view.write_view\`, as a run already on disk: a record stored over a field the run did not
  save (\`{"field": X}\`) with X's \`unstated\` entry. The bath schedule's layer is **planted** for the
  run only, as the engine's own test does: the layer "bath" and its label are the test's words.

$ITEMS

**The engine's source is not stated.** An export has no execution snapshot's record
(\`SNAPSHOT.json\`), from which alone the writer learns its source, so no view here has
\`run.source\`: each lists the engine source as unstated, with the writer's reason. The
\`run.revision\` of the secretion view, \`$SHORT\`, is a caller's label **planted** by the script;
it is not the engine's own word for its source, and nothing may read it as that. The other views
name no revision. The division run's helper (\`declare_division\`) also patches
the writer's source lookup to give none, as the engine's tests do; from an export the lookup gives
none anyway, as the unpatched runs show. The exported code is that of \`$REVISION\`.

These are development runs of unit-test worlds: no result and no evidence.
NOTE
du -sh "$DEST"
find "$DEST" -type f | sort
