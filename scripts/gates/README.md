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
| `crossrev_sets.py` | crossrev's sets of a snapshot. `run` compares each set with a record; `record` makes a new record. The sets are the record's own folders, mapped to their modules; an unknown set is refused. | The ten-set `crossrev.sh` (`crossrev-acceptances-20261118/tools/`, installed in `d198-retire-20261117/tools/` and `d188-m1-20261117/tools/`), its nine-set originals, and `core-fixes-20261116/tools/crossrev-record.sh` |
| `fingerprints.py` | R1's definition-fingerprint check through a move map: every saved definition's digest value, harness rows and control arrays, compared through the map. It carries the harness parts it uses. | `d188-m2-move-20261118/tools/fingerprints.py` |
| `fingerprints_landing.sh` | That check at a landing after a move: main's snapshot against the head, and the head against the move's pre-move record. | `d188-m2-move-20261118/tools/fingerprints-landing.sh` |

`scripts/test_tiers.py` holds the tier record's tools. Two of them changed with D222:
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
```

The workspace folders above are under `/mnt/workspaces/Cells/`, and `fr45` stands for
`d172-restructure-20261115-01/fr45`.
