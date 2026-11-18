# Gate tooling

The landing gates' tools, brought into the repository (D220, D222) from the workspace folders
where they grew. Each tool says which workspace copy it supersedes. Those copies stay byte for byte,
because recorded runs cite them, and units already running keep their old paths. Every tool has
tests with planted failures (`tests/unit/test_gates_*.py`, `tests/unit/test_tier_fold.py`).

| Tool | What it does | Supersedes |
| --- | --- | --- |
| `lane_busy.py` | A holder's lane check. It refuses while a unit computes on the lane's CPUs without the lane's lock, and ignores units that only wait for the lock (blocked in flock, or idle over a sampling window). | The inline check in `fr45/judged-20261117/landing-laneB-holder.sh` |
| `freeze_snapshot.py` | Freezes an execution snapshot with the checkout's own `validation/source_snapshot.py`, at scope `full` (every tracked file but `visualizer/`) or `guards` (`src/cells`, `validation`, `tests`, `pyproject.toml`). | `core-boundary-checks-20261117/tools/snap_full.py`, `inventory-coupling-m4-20261114-01/freeze.py` |
| `fr_landing_set.sh` | FR's bitwise landing set on lane B, synchronously: a worktree of the revision, the holder under lane B's lock, then the verdict. | `fr45/judged-20261117/landing-checks-laneB.sh` and the gates' own lane-B wrappers |
| `fr_landing_holder.sh` | The set's holder: freeze, lane check (`lane_busy.py`), the four queues, held until they end. | `fr45/judged-20261117/landing-laneB-holder.sh` |
| `fr_landing_queue.sh` | One queue: FR-4's and FR-5's quick parts compared with the earlier dry runs, and FR-5's windowed arms. | `fr45/rehearsal-20261117/landing-queue.sh` |
| `fr_landing_verdict.py` | The set's verdict: nine identical quick parts and two bitwise windowed arms. | `d198-retire-20261117/tools/fr_landing_verdict.py` |

`scripts/test_tiers.py` holds the tier record's tools. Two of them changed with D222:
- `measure --only`: a tier the only-list does not hold now selects nothing (it raised `KeyError`),
  and a listed file that is not a test file is refused.
- `fold` (new): at landing time, a landing's measured rows go onto main's current record, never as a
  folded file merged in. Every other row is kept as it stands. The fold refuses to drop a row.

Typical uses:

```
scripts/gates/fr_landing_set.sh REV OUT
python3 scripts/gates/lane_busy.py --cpus 8-11,24-27 --lock /mnt/workspaces/Cells/locks/gate-cores-8-11.lock
python scripts/gates/freeze_snapshot.py CHECKOUT DESTINATION --scope full --require-clean
python scripts/test_tiers.py fold --record tests/test_tiers.json --measured LANDING/measured.json --out tests/test_tiers.json
```

The workspace folders above are under `/mnt/workspaces/Cells/`, and `fr45` stands for
`d172-restructure-20261115-01/fr45`.
