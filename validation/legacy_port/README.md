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
1. Merge `legacy-open-retirements` (the rows of six files that stay). It is prepared already, with the second commit on it
   (below); after the user's word the script with `--branch` makes the same tree from the approved list.
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
- **The prepared branches** (25 November, late; not merged): `legacy-deletion` 3747bb3e is 61ebb75f (legacy-cleanup) and one commit made
  by this script with its message, from the list at 742abcf0: 1,693 files removed and 42 edited (tree 8ae52c5f). `legacy-guard-list`
  9818e4b8 adds three readers of captured states that legacy-cleanup gained at 61ebb75f to the bypass guard's read-only group: on the
  deletion's tree the guard fails on them alone (16 of 17 rows pass), and with them all 17 pass. `legacy-open-retirements` 34e2e8c1 is
  830ae93b, a merge of `legacy-guard-list` (59d40c8b) and the second commit, which `--retirements` staged on that merge (`--branch`
  refuses it until the user's word, so its staged tree was committed by hand, with the script's message): 11 more files removed and 8
  edited against `legacy-guard-list`, the six files' prepared rows among them (tree ed86a1fa). Merge them in that order.
- Measured on those trees (m): after the deletion 11,140 tests collect and 8 files fail to, all of which would retire; of 21,927 base IDs
  11,531 no longer collect (10,956 in files that go, 261 rows of files that stay, 138 of the two files that the pump and symports work
  rewrote, 176 in the eight files that fail to import) and 744 are new. After the second commit 11,131 collect with no error: 11,545 of
  the base and 749 new (`second_commit_test_ids.tsv`: 14 leave, and 5 are new, the same rows without the parked family's parameter).
  The tier record loses 302 rows (114, 46 and 142), and 8 more (2 of tier 1, 6 of tier 3). The library pages pass their check, the
  definitions that leave are the 129 of `removed_definitions.txt`, and nothing that the merges since abd78068 added is touched by
  either commit or reached only by retiring files. The one import that resolves to nothing after both is the rehearsals' drivers',
  which are of the frozen snapshot.
- The rows that the commits change, run: on `legacy-deletion`, the guard and the files that read the law modules it edits (236 pass;
  the guard's one row fails as said); on `legacy-open-retirements`, the guard and the six files (59 pass, two GPU rows skip).
- `carrier_plants.py` at abd78068: all 39 plants fail their rows (33 passed with nothing planted): 28 by an assertion, 7 by a raise of the engine's while the row ran, and 4 by such a raise in a fixture. None is unseen, and none counts an import or collection error. The fresh reader's 168 plants (its file as it stood at 21:09:48 UTC), run on its own copies of the tree after the deletion (the staged tree bc40533b with seven newer files of d8920e5b): 116 fail a row by an assertion (one of them also by a raise), 12 only by a raise of the engine's (7 while the row ran, 5 in a fixture), and 40 fail no row that it ran (`carrier_plants_reader.tsv`; what they mean is in `open_rows.tsv`).
