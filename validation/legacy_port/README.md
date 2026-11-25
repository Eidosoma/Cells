# The removal of the legacy package: the list and the tools

The legacy families leave in one commit (the user's decisions of 25 November 2026, D383 to D387), and the test rows on
their old forms in a second one, if the user agrees. This folder holds what both are made from. The tag
`pre-cleanup-2026-11-25` keeps everything that leaves.

| File | What it holds |
| --- | --- |
| `removal_list.tsv` | One row per file (or per name of a file that stays): its action, owner, reason, basis and state. `goes` and `optional_batch` leave in the first commit, `retires` in the second |
| `open_rows.tsv` | The rows that were open on 25 November, one line per test function: what it claims, the proposal, what carries it, the plant that shows it and its outcome, what the fresh reader's plants did, and what no live row holds. The first column is the line of the table at 8c598905, by which the reader's report and the lead's rulings name a row |
| `carrier_plants.py`, `.json`, `.tsv` | Faults planted in the engine, in a scratch worktree, and the staying rows that must fail on each. A row carries a claim of a retiring row only where a plant of that claim makes it fail. Each outcome is told by where the row crashed: an assertion of the row's, a raise of the engine's (a real detection, and not the row's own), or the same in a fixture |
| `carrier_plants_reader.tsv` | The fresh reader's plants, as the reader wrote them (made on the tree after the deletion, its own copies; 25 November). A and E are its words for an assertion and a raise in `src/` |
| `law_reference_checks.tsv` | Every live law and kernel: its declared test and the reference rows that check it after the deletion (D196) |
| `removal_test_ids.txt`, `retargeted_test_ids.txt`, `new_test_ids.txt`, `removed_rows.tsv` | The test IDs that leave, that are rewritten or retire, and that are new, and why each row of a file that stays left |
| `removed_definitions.txt` | The definitions that leave the gate's fingerprints (`fingerprints.py compare --removed`) |
| `make_edits.py` | Writes `edits.json` and `edits-optional.json` at a head. It stops where a text to replace has changed |
| `edits.json`, `edits-optional.json` | The edits that belong to the deletion's own commit, and those that the optional batch adds |
| `make_deletion.py`, `reach.py` | Prepares a commit in a new worktree, staged and not committed, with a report and the commit's message. `reach.py` reads the import graph |

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

## Making the second commit

It needs the user's yes on the rows of `open_rows.tsv`, and the campaign's results (L67: one of the rows is the only one
of a reference that Part 2's judge may use). After the deletion's commit:

0. The user's word sets the rows' states: each `retires` row, and each row that says `open, before the second commit`, then says
   `approved by the user` with the date (the script reads only that), and the second state is no longer `open, ...`.
1. Merge `legacy-open-retirements` (the rows of six files that stay).
2. `python validation/legacy_port/make_deletion.py REPO HEAD validation/legacy_port/removal_list.tsv WORKTREE
   --retirements --out DIR`, with `--branch NAME` at the end. It removes the eleven files whose row says `retires`, their
   entries in the bypass guard's list and their rows of the tier record. It takes no other edits.

Until then the deletion's tree has eight files that fail to import (they fail on the cleanup branch before it too), and
five rows of three files that fail when they run: they read what left. No gate runs between the two commits: the second
follows the first right away, and the ID move and the one full gate come after both (the lead, 25 November).

`--branch` refuses before it makes anything while a row is open before that commit (`open, before the deletion` for both,
`open, before the second commit` for the second), while a row on which the user was asked is not approved, and while the
list is not a committed file. The batch without its edits is refused too, and so are the second commit's `--edits`.

## Shown (25 November 2026)

- Planted, and refused with no branch and no worktree: a list with one approval taken out (a row of
  B1, and one of the optional batch), a list with one open gate row, a list that is not a committed
  file, and the batch without its edits. For `--retirements`: the list as it stands (its rows wait for the user), a list
  with one approval taken out, one with one row open before the second commit, one that is not a committed file, and
  `--edits`.
- A prepared text that no longer stood in its page stopped `make_edits.py` (a page rewritten at
  8d82e435).
- At 62d5da58 this script and the scratch copy it came from stage one tree from one list (ad34ed59).
- At abd78068 (legacy-cleanup f429ea4b with `legacy-retiring-rows`), the list at c07d1d91: 1,693 files removed and 42 edited (staged tree eaa1bb65). The library pages pass their check, all 17 rows
  of `tests/unit/test_continuity_bypass.py` pass, the definitions that leave are the 129 of `removed_definitions.txt`, 11,012 tests collect, and 8 files fail to, all of
  which would retire.
- Test IDs, of 21,927 at the base: after the deletion 11,531 no longer collect (10,956 in files that go, 261 rows of files that stay, 138 of the two
  files that the pump and symports work rewrote, 176 in the eight files that fail to import) and 616 are new, so 11,012 collect. After the second
  commit 11,545 and 621, so 11,003 (`second_commit_test_ids.tsv`: 14 leave, and 5 are new, the same rows without the parked family's parameter).
- On that commit with `legacy-open-retirements` 830ae93b merged (a detached commit, for the measurement), `--retirements`: 11 more files removed and 2 edited (staged tree c5f61ed0), 11,003 tests collect with 0 errors, the same 17 rows
  pass, and the one import that resolves to nothing is the rehearsal driver's, which is of the frozen snapshot.
- `carrier_plants.py` at abd78068: all 39 plants fail their rows (33 passed with nothing planted): 28 by an assertion, 7 by a raise of the engine's while the row ran, and 4 by such a raise in a fixture. None is unseen, and none counts an import or collection error. The fresh reader's 168 plants (its file as it stood at 21:09:48 UTC), run on its own copies of the tree after the deletion (the staged tree bc40533b with seven newer files of d8920e5b): 116 fail a row by an assertion (one of them also by a raise), 12 only by a raise of the engine's (7 while the row ran, 5 in a fixture), and 40 fail no row that it ran (`carrier_plants_reader.tsv`; what they mean is in `open_rows.tsv`).
