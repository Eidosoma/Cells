# Gate tooling

The landing gates' tools, brought into the repository (D220, D222) from the workspace folders
where they grew. Each tool says which workspace copy it supersedes. Those copies stay byte for byte,
because recorded runs cite them, and units already running keep their old paths. Every tool has
tests with planted failures (`tests/unit/test_gates_*.py`, `tests/unit/test_tier_fold.py`).

| Tool | What it does | Supersedes |
| --- | --- | --- |
| `lane_busy.py` | A holder's lane check. It refuses while a unit computes on the lane's CPUs without the lane's lock, charging each process by its own affinity and CPU time over a sampling window, so a child pinned onto the lane is seen. It ignores units that only wait for the lock (blocked in flock, or idle) and the caller's own unit. | The inline check in `fr45/judged-20261117/landing-laneB-holder.sh` |
| `freeze_snapshot.py` | Freezes an execution snapshot with the checkout's own `validation/source_snapshot.py`, at scope `full` (every tracked file but `visualizer/`) or `guards` (`src/cells`, `validation`, `tests`, `pyproject.toml`). | `core-boundary-checks-20261117/tools/snap_full.py`, `inventory-coupling-m4-20261114-01/freeze.py` |
| `fr_landing_set.sh` | FR's bitwise landing set on lane B, synchronously: a worktree of the revision, the holder under lane B's lock, then the verdict. | `fr45/judged-20261117/landing-checks-laneB.sh` and the gates' own lane-B wrappers |
| `fr_landing_holder.sh` | The set's holder: freeze, lane check (`lane_busy.py`), the four queues, held until they end. | `fr45/judged-20261117/landing-laneB-holder.sh` |
| `fr_landing_queue.sh` | One queue: FR-4's and FR-5's quick parts compared with the earlier dry runs, and FR-5's windowed arms. | `fr45/rehearsal-20261117/landing-queue.sh` |
| `fr_landing_verdict.py` | The set's verdict: nine identical quick parts and two bitwise windowed arms. | `d198-retire-20261117/tools/fr_landing_verdict.py` |
| `crossrev_sets.py` | crossrev's sets of a snapshot. `run` compares each set with a record; `record` makes a new record. It fails closed: every set the runner knows is required, and a set the record lacks fails the run unless `--allow-missing` names it (logged; no gate passes it). An unknown record folder is refused. | The ten-set `crossrev.sh` (`crossrev-acceptances-20261118/tools/`, installed in `d198-retire-20261117/tools/` and `d188-m1-20261117/tools/`), its nine-set originals, and `core-fixes-20261116/tools/crossrev-record.sh` |
| `fingerprints.py` | R1's definition-fingerprint check through a move map: every saved definition's digest value, harness rows and control arrays, compared through the map. It carries the harness parts it uses. Across the ID rename (D345), `--inputs` and `--outputs` read the definitions and the results through a table of renamed IDs, before anything is serialized, digested or cut. `--removed` and `--added` name the keys that the new side removes and adds, one on a line, as exact lists: a key on one side only passes where its list names it, and a listed key that did not move as listed refuses. Without a list, both sides hold the same keys. `keys TREE` prints a tree's, for the lists. | `d188-m2-move-20261118/tools/fingerprints.py` |
| `cache_qualify.sh` | The qualification of JAX's persistent compilation cache on CPU (the testing plan's section 5.3): OFF, COLD, WARM, WARM2, the cross-revision arm and G3's planted controls, on one lane under its lock and behind a go-file. Bits per test ID and per world, memory per process and per stage, and whether the cache engaged; `gate_steps.py cache-verdict` lists every criterion. It turns the cache on in no gate. | New |
| `cache_compare.py` | Two caches' independent compiles compared program by program (equal; the same kernels reordered; other metadata; different machine code), as the qualification's information. JAX's byte check cannot pass on XLA:CPU. | New |
| `fingerprints_landing.sh` | That check at a landing after a move: main's snapshot against the head, and the head against the move's pre-move record. The base's identity and record are cached per main revision (`GATE_CACHE`). Each tree reads the definitions through its own table of renamed IDs, where it has one; where the head's table holds IDs that the base's does not, both sides' results are read through it (D345). `REMOVED` and `ADDED` name a landing's lists of removed and added definitions (for the legacy cleanup, `validation/legacy_port/removed_definitions.txt` and `added_definitions.txt`); both records, the report and the base cache's key hold their digests. | `d188-m2-move-20261118/tools/fingerprints-landing.sh` |
| `gate.sh` | The landing gate, failing fast and lane-aware. Before the lock, on one light CPU at nice 10: the configuration, IDs with declared additions and removals, and the guard set with the head's changed test files. Under the lock, stopping at the first failure: crossrev head against base (a difference passes only where `CROSSREV_EXPECTED` declares it), then tiers 1+2, then G1 on shards planned from the last passing G1's seconds, its saved definitions and refusals read through the head's own table of renamed IDs (D345; `stack.sh` and `cache_qualify.sh` read theirs the same way, tree by tree). The base side's crossrev and IDs are cached per main revision. With `SELECT`, a landing with no src/ change runs the tier-1/2 files its change can reach (`scope.py`); `SELECT_ALWAYS=readers` keeps D229's always-run readers there; `CHECKS` lets such a landing drop crossrev or G1 under D223, and preflight refuses that when src/ changed. Run the copy in the gate's own base snapshot. | The owners' `gate-laneA.sh` copies (for example `core-pass-at3-20261118/tools/gate-laneA.sh`) and the lead's `gate-tiers-ids.sh` |
| `stack.sh` | Stacked gates (D229 rule 2): two or three queued heads merged in order onto main as the lead lands them (the previous trial's tier record, each head's measured rows folded, its message with the line `Stack gate: OUT`), the top gated once by `gate.sh` with the union of the heads' declarations. A conflict refuses the stack and lists its paths; a head may name a merge made by hand. On a refusal only the failing check runs again (the failing test files, crossrev sets or G1 worlds, or IDs or preflight) on the intermediate trees, nearest first, under the same lane's lock when it ran under it; the first tree where an item passes blames the head above it, and the stack is re-gated without the blamed heads. A head that declares a crossrev difference rides alone; a head's own pre-lock pass (`PRELOCK_ONLY=1`), when it names one, is checked against its revision and recorded. The top is kept as `refs/stacks/TOP`; `OUT/stack.json` holds the record. | New |
| `scope.py` | The scope map and the selection for a landing with no src/ change (D229 rule 3, D358). `build` makes the map from a tiers run with the recorder on: per test file, every repository path its processes touched (imports, files opened, asked about or named to a child), every folder they listed and every name their imports looked up, each with its state in the run's snapshot, and checked against strace's view of the same run. `select` gives the tier-1/2 files a landing can reach: the guard set, files whose children the map cannot see, new or changed files, files not complete in the map, and every file a path of which is in another state at the head than in the map's snapshot (or one of whose imports would find another file). A file that reads the repository's files runs by its recorded paths only where a trace checked its entry; `--always readers` is D229's rule (every such file), the fallback, and each selection counts it beside its own. It refuses (the full tiers run) on a src/ change, a change to a tool that every file runs through (`RUNNER` in `scope.py`, against the base and against the map's snapshot), a missing, failed, old or earlier map, another interpreter, or `gate-cache/selection-stopped`. | New |
| `scope_inject/sitecustomize.py` | The map's recorder, loaded only by `test_tiers.py run --scope-map`: an audit hook on opens, listings, links and child processes, wrappers on `os.stat` and its kin, `os.open` and the calls that start a child (which give a child whose environment dropped the recorder its variables), a finder that notes each name an import looks up, and the repository's modules at exit, one JSON line per fact, written as it happens. It changes nothing a process computes. | New |
| `nightly_tiers.sh`, `systemd/cells-nightly-tiers.*` | The nightly full tiers 1+2 at 02:30 UTC (definitions only; the lead installs them), and the same run on demand after an engine landing (`systemctl --user start --no-block cells-nightly-tiers.service`; a start while one runs does nothing), so later gates select against a map of the current main (D358): main frozen, whichever lane's lock is free first taken like a gate, tiers 1+2 with the recorder and strace on, the map built and published to `gate-cache/scope-map.json` when the run passes; on a failure `gate-cache/selection-stopped`, which turns selection off until the lead removes it with the explanation. What the trace found is in `verdict.json`; it fails nothing. `TRACE=0` runs without strace. | New |
| `weekly_tier3.sh`, `systemd/cells-weekly-tier3.*` | The weekly tier 3 on Sundays at 04:00 UTC, after the nightly (D390; definitions only, the lead installs them): main frozen, whichever lane's lock is free first taken like the nightly and let go again while the lane is busy without it (`lane_busy.py`), tier 3 at cap 1800 s on the lane's four physical cores with their siblings idle, the cold check, the run's test IDs collected, and `test_tiers.py diff --require-complete` against tier 3's record read through the ID move's table (`id_moves.py`'s ids rule). The lead reads `weekly/DATE/verdict.json`; a failure turns nothing off. `--judge OUT` judges a finished run again, against `RECORD`. | New |
| `gate_steps.py` | `gate.sh`'s host steps: preflight, the pre-lock selection and its verdict, the IDs check, the base cache, crossrev's set pool and its head-against-base verdict, and G1's plan, merge and seconds; the cache qualification's tier subsets and verdict. | `core-pass-at3-20261118/tools/ids_additions.py`, `d198-retire-20261117/tools/g1_plan.py` (plan and merge) and `g1-shard.sh` |

**Locks.** Every lock taken in `scripts/gates/` uses flock's command form, which runs the locked
work only once flock holds the lock, and its exit status is checked. A flock killed while it waits
therefore runs nothing (`tests/unit/test_gates_fr_landing_set.py`). The workspace gate scripts built
as `exec 9> LOCK; flock 9` without a check run unlocked when their flock dies. Stop a unit with
`systemctl --user stop`, never by killing a flock.

**What the scope map cannot see stays always-run (D358).** A test file's entry releases it from a gate
only while nothing it recorded has changed, so a missed recording must keep the file running:
- **An entry is incomplete,** and its file always runs, when the recorder faulted, a process of it wrote no
  exit record, it made a link into the tree, or strace saw a regular repository file opened, or a
  folder listed, that the entry lacks.
- **Its children are unmapped,** and it always runs, when a child neither recorded itself nor is
  accounted for by its arguments alone (`scope.py`, `answered`): bash and other programs, `python
  -I`, `os.system`, or a program that only strace saw.
- **A reader whose entry no trace checked** always runs, as under D229. So where strace cannot trace,
  the old rule holds by itself.
- **Not recorded:** modification times (a frozen copy's are its own), extended attributes, what C code
  asks of a path without opening it, and files outside the tree (frozen evidence included). D229's
  rule ran a reader whatever changed; the narrowed rule does not see a change in these alone.

`scripts/test_tiers.py` holds the tier record's tools. `run --scope-map DIR` (D229) loads the scope map's recorder into each file's processes, and `--trace DIR` (D358) adds strace's view of them (about 0.4 s a file on average, and 12 to 16 s for the two that open the most files); without these, a run is unchanged. Two of the tools changed with D222:
- `measure --only`: a tier the only-list does not hold now selects nothing (it raised `KeyError`),
  and a listed file that is not a test file is refused.
- `fold` (new): at landing time, a landing's measured rows go onto main's current record, never as a
  folded file merged in. Every other row is kept as it stands. The fold refuses to drop a row.
- `merge` (new): the three-way fold of a merge, when the branch's measurements are not at hand. The
  branch's row delta against the merge base is applied to main's record, in main's order. It refuses
  a row that both sides changed differently.

**JAX's persistent compilation cache (D321, step 1).** Tier membership is decided by seconds, and a
warm cache moves files across tiers, so everything that measures or gates runs cold by construction:
- `test_tiers.py` disables the cache in every test process, whatever its caller's environment.
  - `measure` marks its record `"jax_compilation_cache": "disabled"`, and `fold` and `tiers` refuse
    a measurement without that marker. `--pre-marker-ok` takes one made before the marker existed.
  - Only `run --jax-cache FOLDER` runs warm, and its record names the folder. That is for the cache
    qualification's arms and, once step 2 is ruled, gates.
- `gate.sh`, `stack.sh`, `nightly_tiers.sh` and `fr_landing_set.sh` (with the holder's queue units)
  export `JAX_ENABLE_COMPILATION_CACHE=false`, drop any cache folder and log it. After each stage the
  cold check (`gate_steps.py jax-entries`) refuses if an entry appeared under their outputs. That
  stop is the gate's own fault, so a stack does not bisect it.
- `scripts/run_detached.sh` disables the cache in every unit without `--jax-cache`, so registered and
  judged runs stay cold.

Development runs opt in per unit (`run_detached.sh --jax-cache`) or per command
(`scripts/with_jax_cache.sh CMD`), never through an exported shell variable.
- Both are CPU-only: they are refused with a visible GPU, since the L4's recorded bitwise failure
  crossed this cache.
- They use the qualified mode (every compile written, JAX's default store) in one folder per jaxlib
  version and CPU model, `/mnt/workspaces/Cells/jax-cache/cpu-jaxlib<VERSION>-<CPU>`
  (`scripts/jax_cache.py folder`).
- `systemd/cells-jax-cache-sweep.*` (definitions only; the lead installs them) runs
  `scripts/jax_cache.py sweep` nightly at 02:00 UTC:
  - folders of another jaxlib or CPU go;
  - entries that no longer decompress (a torn write) go;
  - the least recently read entries above 8 GB go, down to 90% of it.

GARD's @1 invariance gate comes in after OL2 lands, using OL2's
`validation/assembly_lineages/compare_probes.py` (the lead's ruling, 18 November 2026).

Typical uses:

```
scripts/gates/fr_landing_set.sh REV OUT
python3 scripts/gates/lane_busy.py --cpus 8-11,24-27 --lock /mnt/workspaces/Cells/locks/gate-cores-8-11.lock
python scripts/gates/freeze_snapshot.py CHECKOUT DESTINATION --scope full --require-clean
python scripts/test_tiers.py fold --record tests/test_tiers.json --measured LANDING/measured.json --out tests/test_tiers.json
python scripts/test_tiers.py merge --base BASE.json --ours BRANCH.json --theirs MAIN.json --out tests/test_tiers.json
python scripts/gates/crossrev_sets.py run SNAPSHOT OUT /mnt/workspaces/Cells/core-fixes-20261116/record-cda5dc82
scripts/gates/fingerprints_landing.sh OUT HEAD_SNAPSHOT BASE_SNAPSHOT [PREMOVE_RECORD]
LANE=A REMOVED_OK_FILE=removed-ok.txt ADDITIONS_FROM="tests/unit/test_x.py" bash BASE_SNAPSHOT/scripts/gates/gate.sh HEAD_SNAPSHOT BASE_SNAPSHOT OUT
LANE=A bash BASE_SNAPSHOT/scripts/gates/stack.sh STACK.json OUT
```

The base cache lives in `/mnt/workspaces/Cells/gate-cache` (`GATE_CACHE`). Each entry is named by its
kind, the base's revision and a key, and holds `CACHE.json`. Entries are renamed into place whole,
so a partial entry is never used. Deleting an entry only costs the next gate its recomputation.

The workspace folders above are under `/mnt/workspaces/Cells/`, and `fr45` stands for
`d172-restructure-20261115-01/fr45`.
