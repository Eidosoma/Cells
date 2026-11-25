# The removal of the legacy package: the list and the tools

The legacy families leave in one commit (the user's decisions of 25 November 2026, D383 to D387).
This folder holds what that commit is made from. The tag `pre-cleanup-2026-11-25` keeps everything
that leaves.

| File | What it holds |
| --- | --- |
| `removal_list.tsv` | One row per file (or per name of a file that stays): its action, owner, reason, basis and state |
| `open_rows.tsv` | The rows that were open on 25 November, one line per test function: what it claims, the proposal, what carries it, the plant that shows it, and what no live row holds |
| `carrier_plants.py`, `.json`, `.tsv` | Faults planted in the engine, in a scratch worktree, and the staying rows that must fail on each. A row carries a claim of a retiring row only where a plant of that claim makes it fail |
| `law_reference_checks.tsv` | Every live law and kernel: its declared test and the reference rows that check it after the deletion (D196) |
| `removal_test_ids.txt`, `retargeted_test_ids.txt`, `new_test_ids.txt`, `removed_rows.tsv` | The test IDs that leave, that are rewritten and that are new, and why each row of a file that stays left |
| `removed_definitions.txt` | The definitions that leave the gate's fingerprints (`fingerprints.py compare --removed`) |
| `make_edits.py` | Writes `edits.json` and `edits-optional.json` at a head. It stops where a text to replace has changed |
| `edits.json`, `edits-optional.json` | The edits that belong to the deletion's own commit, and those that the optional batch adds |
| `make_deletion.py`, `reach.py` | Prepares the deletion in a new worktree, staged and not committed, with a report and the commit's message. `reach.py` reads the import graph |

## Making the deletion

The optional batch (165 files, `optional_batch` in the list) goes with the rest: the user approved it
on 25 November 2026. `--without-optional` leaves it out.

1. `python validation/legacy_port/make_edits.py REPO HEAD DIR`, and compare with the two files here.
2. A dry run: `python validation/legacy_port/make_deletion.py REPO HEAD
   validation/legacy_port/removal_list.tsv WORKTREE --edits DIR/edits.json
   --optional-edits DIR/edits-optional.json --out DIR`.
3. In the worktree: `scripts/library_pages.py --check`, a collection of `tests`, and
   `tests/unit/test_continuity_bypass.py`, whose list the script edits.
4. The same with `--branch NAME`. The commit takes the message that the script wrote, which names
   the head and the list's own revision.

`--branch` refuses before it makes anything while a row is open before the deletion (the rows whose
retirement waits for the user, and the JUPITER check's model part, are such rows), while a row on
which the user was asked is not approved, and while the list is not a committed file. The batch
without its edits is refused too.

## Shown (25 November 2026)

- Planted, and refused with no branch and no worktree: a list with one approval taken out (a row of
  B1, and one of the optional batch), a list with one open gate row, a list that is not a committed
  file, and the batch without its edits.
- A prepared text that no longer stood in its page stopped `make_edits.py` (a page rewritten at
  8d82e435).
- At 62d5da58 this script and the scratch copy it came from stage one tree from one list (ad34ed59).
- At a6432f98 (branch `legacy-counts`: legacy-cleanup 94805c08 with the documents and the open rows, a
  merge for the measurement): 1,693 files removed and 42 edited (staged tree d090ffd8). The library
  pages pass their check, all 17 rows of `tests/unit/test_continuity_bypass.py` pass, the definitions
  that leave are the 129 of `removed_definitions.txt`, 11,008 tests collect, and 8 files fail to: all
  of them wait for the user.
- With the proposal of `open_rows.tsv` (407bc106, with `legacy-open-retirements`): 1,706 files removed
  (staged tree bc40533b), 10,995 tests collect with no error, the same 17 rows pass, and the one import
  that resolves to nothing is the rehearsal driver's, which is of the frozen snapshot.
