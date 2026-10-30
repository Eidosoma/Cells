# Native square/HEX lattice seeds

The first bounded qualification failed: twenty of thirty-seven checks passed,
sixteen native-capture checks could not resolve the retained `type_check`
decorator, and one centroid assertion recomputed a source F-order reduction
from C-order frozen storage. The failed directory and original static receipt
are preserved. Chief requested narrow static repairs for the next user
qualification. The repaired static receipt is preserved; authorization and
qualification outcomes belong to the preparation plan and run artifacts.
Project status and the ECM diagnostic remain Root-owned.

`src/cells/processes/betse_lattice_seed_generation.py` exposes `bind`, `generate`,
`validate_state`, `export_seed_stage` and `restore_seed_stage`. The declaration
contains the actual normalized native scalar controls: one world length for
both axes, cell radius, disorder and SQUARE/HEX branch. It accepts no prepared
counts, expanded widths, drawing gap or true cell-space override. The input
stream is the existing complete legacy NativeStream; no seed is inferred from
world/owner IDs and no process-global RNG is consumed.

Eight original Parameters assignments define the scalar preparation order.
`ac=1e-6` is the drawing gap, independent of true `cell_space`; diameter is
twice radius. `nx/ny` truncate the original world length before width/height
expand by `5*disorder*diameter`. Square uses those earlier counts. HEX uses
expanded sizes to derive blue/red counts, so valid HEX seed preparation can
have unused original nx/ny equal zero. Source linspace includes endpoints;
actual HEX point spacing need not equal nominal a_hex/b_hex.

Square draws one `(ny,nx)` x block followed by its y block and flattens in C
order. HEX concatenates the entire blue cloud followed by the red cloud,
then draws x and y one-dimensional blocks. Both branches draw even at zero
disorder. Empty red coordinate matrices retain shape `(0,2)`. The complete
624-word RNG state, position and Gaussian cache are retained at each boundary.
Prepared cases include continuation with a twist at the y block.

The repaired isolated native wrapper authenticates and executes the original
`types.py` `type_check` function; the pinned function returns its callable.
It retains the complete original lattice AST, including annotations and the
decorator, using postponed annotation compilation. The eight parameter stores,
lattice function and decorator AST are checked before compilation. Native
package import hooks are outside this normalized boundary; scalar controls
and the complete MT stream are explicitly validated before calling it.

The centroid is calculated from the jittered lattice alone. Four unexpanded
extrema-corner occurrences BL,BR,TR,TL are appended afterwards; a separate bbox
and axis bounds expand by radius. Exact-coordinate duplicates are recorded
without deduplication, with distinct occurrence IDs. Those IDs label this seed
recipe, not physical cells or cross-generation owners.

Native local shapes, dtypes, original strides and C/F flags are recorded before
K-order copies. Both centroid assertions use retained native points in their
original reduction order. The production arrays, fixtures, RNG arithmetic and
accuracy budgets are unchanged. Actual arrays and RNG successors are saved
before native evaluation, including the nonfinite trial, so capture failures
also leave raw component evidence.

The portable handoff is explicitly `native_lattice_seed_occurrences`, before
the make_voronoi image prelude. It cannot be passed to the reviewed geometry
adapter as manufactured coordinates. Image/SVG clipping, alpha filtering,
close-point removal, merging, refinement, triangulation and full make_world
remain separate unimplemented stages. The existing B09/geometry/MT helpers and
their evidence are reused, with no coverage counts claimed again. No biological
geometry, physical amount/energy, whole-cell solver or GPU claim is made.

The prepared panel has 37 checks: twelve full seed cases, zero-disorder/cache,
ordering/centroid/duplicate/parameter invariants, raw empty square/HEX failures,
a retained nonfinite native-mean case, tampering, serialization and unsupported
input refusals. Original source arithmetic executes from authenticated AST
bodies with local owned MT state. Independent Decimal100/160 coordinates use
exact binary64 parameter/count-store seams and the established independent MT
helper. Fixed B09 coordinate budgets apply; discrete counts and streams are
exact, with no propagated allowance. Primary/refined and raw precomparison
arrays are saved before assertions. The nonfinite mean is a stricter finite
admission refusal, not an accepted independent-accuracy case. These checks have
were prepared without numerical execution; source parsing and Ruff passed
before authorization. The qualification outcome belongs to its run artifacts.

The frozen preparation inputs are listed in
`betse_lattice_seed_generation_preparation_plan.json`. The prepared runner is
`/mnt/workspaces/Cells/specialist-runners/betse-lattice-seed-generation-20261030-02-checks.py`;
it refuses a numerical launch while that plan's authorization is false. Chief
coordinates CPU6 for the next panel. The panel is bounded
to one CPU/thread, 1 GiB summed process-tree RSS, an 8 GiB host reserve and
480 seconds per phase. The qualification output is
`/mnt/workspaces/Cells/betse-lattice-seed-generation-20261030-02` when authorized.
The preserved failed-round receipt is
`/mnt/workspaces/Cells/betse-lattice-seed-generation-failed-round-20261030-01.json`.
