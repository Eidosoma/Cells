# Amendment 2, 25 November 2026: what the exporter's builder receives of it

**Word for word from `AMENDMENT-2-2026-11-25.md`: its items 2, 4, 7, 8, 9.1 and 10, with their numbers there.** The builder does not receive that file. Its other items are the judge's and the rehearsal runner's. Where this file and an earlier one of this folder differ, Amendment 1 included, this one governs. It holds no number of a run of either side. Each item quotes the sentence that it replaces or adds to, as it stands at its tag, and says where.

## 2. An extra entity is a departing echo

**Adds to** `SPEC.md` §2.4:

> a key that `inputs.json` does not hold is recorded, and refuses nothing.

**Now also:** a cell, region, membrane, channel, junction, face or species that the registered block does not have is a departing echo. It refuses the run, and nothing of the run is judged (`CRITERIA.md` §5). The sentence above stays for a key inside an entity.

**Where the rule is read:** in the echoed `inputs` alone. That is its sets of entities, its `species`, the IDs in `controls`, in `switch_list` and in `pool_seeds`, and a pool run's cells. In `cell` and `base` the values of `controls.channel`, `switch_list` and `pool_seeds` stay class E, and their IDs are read as echo.

**Unchanged,** at the head of `TABLE.md`:

> **Extra keys are allowed, recorded and ignored.**

So an extra series, an entity of a series that the world does not have, and an extra key of an entry refuse nothing.

**Stricter:** by that sentence such an entity was recorded, and refused nothing. **Weaker in one respect,** as for every departing echo: a fail in such a run goes unseen. Its consumer is at best inconclusive, and the checker sees it. This rule is Part 1's alone (item 10).

## 4. A file that is not the contract's is refused whole

**Adds to** `TABLE.md` §2, whose head is:

> Top-level keys, all required

**Now also:** a file of which `kind`, `part`, `consumer`, `units`, `runs` or `missing` is absent, or departs from that table, is refused whole. `consumer` departs where it is not the one in the file's name.

**Adds to** `CRITERIA.md` §5, in the table of faults:

> A duplicated key anywhere in a file | The file is refused, and every run of it

**Now also:** so is a file that one of those six keys refuses.

**Adds to** `CRITERIA.md` §5, where a partial run is judged:

> A file refused whole (a duplicate key, or a sha256 that departs) leaves every run in it unjudged; its entries are unformed and inconclusive, and the refusal is named in the verdict

**Now also:** in its parenthesis, one of those six keys absent or departing.

**Stricter:** at the tag the six keys were required, and nothing was said of one that is absent. **Weaker in one respect:** a fail in such a file goes unseen, as that place says. Its consumer is at best inconclusive, and the checker sees it.

## 7. The builder's clarifications

**(a) The strings note. Adds to** `TABLE.md` §5:

> "runs": {"<run name>": {"model": "<label>", "solver": "<label>", "field_solver": "<label>", "operators": [], "kinds": [], "laws": ["<labels>"], "pool": ["<labels>"], "observable": "<label or null>"}}}

**Now also:** `closure` and `maintained_fuel` stand among `laws`. A pool run's `model` is the pool's own model.

**(b) `time_s` of a `check` refusal. Adds to** `TABLE.md` §4:

> `time_s` is the time of the row that failed (a number for `check`, null otherwise).

**Now also:** it is the first refused row's time. The scalar runner keeps no row of a refused run, so the driver finds that time by a second pass, which runs the definition again in one-step windows. For a pool, and where the second pass completes (item 8), `time_s` is the run's end.

**(c) No declaration. Adds to** `TABLE.md` §4:

> **For a run refused at parse** the `inputs` and `definition` are the submitted declaration, and `strings` those declared.

**Now also:** where no declaration exists (another `p`, or a crash before it is written), `inputs`, `strings` and `declared_strings` are empty. Such a run is refused, and its echo departs as well, so nothing of it is judged.

**(d) `pending_valid`. Adds to** `READOUTS.md` §4, the list of the 19 arrays:

> `occupied`, `bonds`, `free`, `fragments`, `time_s`, `last_event_time_s`, `event_count`, `pending_time_s`, `pending_event`, `pending_valid`, `reaction_counts`, `removed`,

**Now also:** `pending_valid` is written as JSON booleans. It is the only captured array of that type. The sentence of `TABLE.md` §3 that has no boolean is of other keys, and stands:

> There is no NaN, infinity or boolean in `rows`, `potentials` or `path`.

**(e) The two pool legs. Replaces** in `AMENDMENT-1-2026-11-25.md`, item 1:

> The two pool restarts submit the composed file and use the same function as a pool run (item 8).

**Now:** the two legs of a pool restart submit the composed file, and use that function's own two pieces (register and execute), since the function takes no horizon.

## 8. A stop's second pass, empty keys, and a membrane without a pump

**(a) A second pass that completes. Adds to** `TABLE.md` §3, the row `refusal`:

> null, or `{"kind", "message", "time_s"}` (§4)

**Now also:** if the second pass of a `check` refusal (item 7 (b)) completes where the run was refused, `refusal` also holds `second_pass_completed: true`. Otherwise it does not hold that key. Nothing is refused by it, and the checker is told. **The run stays refused, whatever the second pass did.** A completed second pass is an engine finding for the lead, and not only a note for the checker.

**(b) Whose rows they are. Adds to** `TABLE.md` §3:

> A refused run keeps the rows it has.

**Now also:** by rule, the rows of every `check`-refused run are the second pass's, in one-step windows. That is another execution path than the refused run's.

**(c) Empty keys. Adds to** `TABLE.md` §3, the row `definition`:

> the engine's own declaration, as run (recorded)

And the row `checks`:

> the engine's own ledgers and checks at the end (recorded)

**Now also:** a refused run without a declaration may have an empty `definition` and an empty `checks`, besides the three of item 7 (c).

**(d) A membrane without a pump. Adds to** `READOUTS.md` §2, the row `pump`:

> `pump` | fmol of cycles | membranes | `pump_cycles` | `pump_cycles[membrane]`, same

**Now also:** for a membrane without a pump, in a world that has pumps, the exporter writes zeros for its pump series (`pump`, `heat_pump`, `work_pump`). The judge reads the membranes that have one. A row that is not zero, for a membrane without a pump, is flagged. No registered world of Part 1 has such a membrane.

**Where the extra-entity rule is read** is in item 2.

### 9.1 What the judge's readings say of the table, for both sides

- **Every channel of the world is a key of `switch_list`, and every world of the pool a key of each cell's `path`,** with an empty list where there is no change and no event. A key that is left out is a missing leaf, and its entry is not formed (reading 22).
- **A channel that `controls.channel` leaves out** has the default schedule [[0, 1]] (`SPEC.md` §2.4), and is compared as that (reading 22).
- **The off-grid switch's flag** (Amendment 1, item 6): its key in a run's entry is `off_grid`, the name that the judge reads, in the registered tables and in the rehearsal's. Absent or false is off, and true in a registered run refuses it (reading 10).
- **A run is named in `runs` or in `missing`,** and one that is named in both is refused, with its readouts judged (reading 20).
- **An empty string in `source`** counts as missing (reading 33).
- **The `checks` of any refused run may be empty** (reading 36).

## 10. What holds in Part 1 alone

The extra-entity rule (item 2) is Part 1's alone. `PART2.md` §2.4 and §2.5 state what stands beyond a block there, in their own words, and they govern for Part 2. Part 2's own text says which of the other items hold there.
