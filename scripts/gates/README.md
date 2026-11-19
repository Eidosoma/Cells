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
| `fingerprints.py` | R1's definition-fingerprint check through a move map: every saved definition's digest value, harness rows and control arrays, compared through the map. It carries the harness parts it uses. | `d188-m2-move-20261118/tools/fingerprints.py` |
| `cache_qualify.sh` | The qualification of JAX's persistent compilation cache on CPU (the testing plan's section 5.3): OFF, COLD, WARM, WARM2, the cross-revision arm and G3's planted controls, on one lane under its lock and behind a go-file. Bits per test ID and per world, memory per process and per stage, and whether the cache engaged; `gate_steps.py cache-verdict` lists every criterion. It turns the cache on in no gate. | New |
| `cache_compare.py` | Two caches' independent compiles compared program by program (equal; the same kernels reordered; other metadata; different machine code), as the qualification's information. JAX's byte check cannot pass on XLA:CPU. | New |
| `fingerprints_landing.sh` | That check at a landing after a move: main's snapshot against the head, and the head against the move's pre-move record. The base's identity and record are cached per main revision (`GATE_CACHE`). | `d188-m2-move-20261118/tools/fingerprints-landing.sh` |
| `gate.sh` | The landing gate, failing fast and lane-aware. Before the lock, on one light CPU at nice 10: the configuration, IDs with declared additions and removals, and the guard set with the head's changed test files. Under the lock, stopping at the first failure: crossrev head against base (a difference passes only where `CROSSREV_EXPECTED` declares it), then tiers 1+2, then G1 on shards planned from the last passing G1's seconds. The base side's crossrev and IDs are cached per main revision. With `SELECT`, a landing with no src/ change runs the tier-1/2 files its change can reach (`scope.py`); `CHECKS` lets such a landing drop crossrev or G1 under D223, and preflight refuses that when src/ changed. Run the copy in the gate's own base snapshot. | The owners' `gate-laneA.sh` copies (for example `core-pass-at3-20261118/tools/gate-laneA.sh`) and the lead's `gate-tiers-ids.sh` |
| `stack.sh` | Stacked gates (D229 rule 2): two or three queued heads merged in order onto main as the lead lands them (the previous trial's tier record, each head's measured rows folded, its message with the line `Stack gate: OUT`), the top gated once by `gate.sh` with the union of the heads' declarations. A conflict refuses the stack and lists its paths; a head may name a merge made by hand. On a refusal only the failing check runs again (the failing test files, crossrev sets or G1 worlds, or IDs or preflight) on the intermediate trees, nearest first, under the same lane's lock when it ran under it; the first tree where an item passes blames the head above it, and the stack is re-gated without the blamed heads. A head that declares a crossrev difference rides alone. The top is kept as `refs/stacks/TOP`; `OUT/stack.json` holds the record. | New |
| `scope.py` | The scope map and the selection for a landing with no src/ change (D229 rule 3). `build` makes the map from a tiers run with the recorder on: per test file, every repository path its processes touched (imports, files opened or asked about, the files a failed or shadowed import would have been, paths named to a child) and every folder they listed, each with its state in the run's snapshot. `select` gives the tier-1/2 files a landing can reach: the guard set, files whose children the map cannot see, D229's always-run readers of the repository's files, new or changed files, files not complete in the map, and every file a path of which is in another state at the head than in the map's snapshot. It refuses (the full tiers run) on a src/ change, a missing, failed or old map, another interpreter, or `gate-cache/selection-stopped`. | New |
| `scope_inject/sitecustomize.py` | The map's recorder, loaded only by `test_tiers.py run --scope-map`: an audit hook on opens, listings and child processes, wrappers on `os.stat`, `os.lstat` and `os.access`, and the repository's modules at exit, one JSON line per fact, written as it happens. It changes nothing a process computes. | New |
| `nightly_tiers.sh`, `systemd/cells-nightly-tiers.*` | The nightly full tiers 1+2 at 02:30 UTC (definitions only; the lead installs them): main frozen, whichever lane's lock is free first taken like a gate, tiers 1+2 with the recorder on, the map built and published to `gate-cache/scope-map.json` when the run passes; on a failure `gate-cache/selection-stopped`, which turns selection off until the lead removes it with the explanation. | New |
| `gate_steps.py` | `gate.sh`'s host steps: preflight, the pre-lock selection and its verdict, the IDs check, the base cache, crossrev's set pool and its head-against-base verdict, and G1's plan, merge and seconds; the cache qualification's tier subsets and verdict. | `core-pass-at3-20261118/tools/ids_additions.py`, `d198-retire-20261117/tools/g1_plan.py` (plan and merge) and `g1-shard.sh` |

**Locks.** Every lock taken in `scripts/gates/` uses flock's command form, which runs the locked
work only once flock holds the lock, and its exit status is checked. A flock killed while it waits
therefore runs nothing (`tests/unit/test_gates_fr_landing_set.py`). The workspace gate scripts built
as `exec 9> LOCK; flock 9` without a check run unlocked when their flock dies. Stop a unit with
`systemctl --user stop`, never by killing a flock.

`scripts/test_tiers.py` holds the tier record's tools. `run --scope-map DIR` (D229) loads the scope map's recorder into each file's processes; without it, a run is unchanged. Two of the tools changed with D222:
- `measure --only`: a tier the only-list does not hold now selects nothing (it raised `KeyError`),
  and a listed file that is not a test file is refused.
- `fold` (new): at landing time, a landing's measured rows go onto main's current record, never as a
  folded file merged in. Every other row is kept as it stands. The fold refuses to drop a row.
- `merge` (new): the three-way fold of a merge, when the branch's measurements are not at hand. The
  branch's row delta against the merge base is applied to main's record, in main's order. It refuses
  a row that both sides changed differently.

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
