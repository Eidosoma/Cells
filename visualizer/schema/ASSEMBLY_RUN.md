# Assembly run: what the assembly view reads of a lineage of assemblies

Status: **fixed for the viewer, 16 November 2026**, so that the view and its example can be built
standing alone. The user chose the options of `docs/ORIGIN_OF_LIFE.md` the same day ("go on your
recommendation on all of those", "be ambitous"); its section "Decided" is the brief.

A model system under the heading "Origin of life" (the first is a GARD assembly) is shown by a view
of its own: an assembly growing molecule by molecule and splitting, its composition, the similarity
across each fission, the lineage, and the table of catalysis it grows by. This file is what that view
reads: `cells.visualizer.assembly_run@1`. It is the viewer's own contract. **Since 17 November 2026,
evening, the page plays the engine's own pair of GARD runs,** adapted from the engine's final set by
`tools/adapt_assembly_run.py`: development runs, not judged, and marked so. The engine's GARD design
note is on main, decided on 16 November 2026 (`docs/GARD_DESIGN.md`, D192), and both parts of its
build have been on main since 17 November 2026: the stochastic assembly family
`cells.assembly_lineages@1`, with GARD's two forms as one law set on it (`PROGRESS.md`). The table
below says which of the engine's records each field is read from.

## The file

```json
{
  "format": "cells.visualizer.assembly_run@1",
  "example": {"says": "Example: invented numbers · not a run of Cells' engine", "made_by": "visualizer/tools/make_assembly_example.mjs"},
  "model": {"id": "gard", "label": "GARD assembly", "plain": "One or two sentences on the model."},
  "time": {"base": "fission", "unit": "fission", "plural": "fissions", "nominal": "What the model's own time is, in words."},
  "environments": [{
    "id": "environment-1",
    "types": ["t000", "t001", "…"],
    "catalysis": {"says": "…", "encoding": "log10, two decimals", "rows": [[-3.12, 0.4, "…"], "…"]},
    "reservoir": {"each": 0.01, "says": "…"},
    "rates": {"join": 0.01, "leave": 0.0001}
  }],
  "runs": [{
    "id": "lineage-a", "label": "Lineage A", "environment": "environment-1", "mode": "single lineage",
    "law": {"name": "the preprint's single-event form", "form": "single-event", "engine_name": null, "says": "…"},
    "engine_models": [], "revision": null,
    "rules": {"start": "…", "events": "…", "fission_size": 80, "split": "…", "continues": "…"},
    "founder": [[12, 1], [40, 1], "…"],
    "fissions": [{"k": 1, "nominal": 412.7, "parent": [[12, 3], "…"], "first": [[12, 2], "…"], "continues": "first",
                  "similarity": [0.96, 0.95], "totals": {"joined": 51, "left": 11, "discarded": 40}}, "…"],
    "trace": {"encoding": "…", "growths": [62, 57, "…"], "events": "base64 of signed bytes"},
    "analysis": {"by": "…", "inheritance": {"compares": "…", "threshold": 0.9, "strict": true, "says": "…", "marks": [true, false, "…"]},
                 "composomes": null}
  }],
  "sources": {"key": {"text": "…", "doi": "…", "licence": "CC BY 4.0", "class": "permissive", "accessed": "2026-11-16", "for": "…"}}
}
```

## Fields

- **`example`** is present only for a run of invented numbers. Its `says` is shown on the picture and
  in the legend for as long as the run is shown, in the words the replays' example uses where they fit
  (`schema/QUANTITY_LAYERS.md`, rule 6). An example names no engine model (`engine_models` empty,
  `revision` null) and nothing in it is a finding; the view states no statistic of it.
- **`development`** is present only for a run of the engine, in an example's place (a file is one or
  the other): `{"says", "standing", "from", "run_states"}`. Its `says` ("Development run of the
  engine, not judged"), with the run's revision (its first eight characters) and the engine's model,
  is the view's mark, on the picture at every level, in the legend, in the bar and at the head of an
  opened card. The engine's run record states no standing of its own, so the adapter is given it and
  writes where it is recorded (`from`) and that the run states none (`run_states`). Such a file's
  runs name their `revision` and their `engine_models`.
- **`model`** names the model system. Its `id` is the id of the entry the run belongs to (below). The
  view's code names no model: "GARD" is in the data.
- **`time`**: the run's own clock. **The clock counts fissions** (`base: "fission"`); `unit` and
  `plural` are the words it is counted in; `nominal` says what the model's own time is. There is no
  "true speed": the view offers speeds in fissions a second of watching, and molecule by molecule
  only where a run has its event trace (below).
- **`environments`**: what a run grows in, which no assembly writes or inherits.
  - `types`: the molecule types, in the order every count uses (an index is a position in this list).
  - `catalysis.rows`: the table, a row for each type i and a column for each type j, the factor by
    which a molecule of type j in the assembly speeds the joining and the leaving of type i; in the
    `encoding` stated (`log10, two decimals` in the example).
  - `reservoir`: the held concentration of each type (`each` where all are the same, else `of`, one
    for each type); `rates`: the basal join and leave constants (one number, or one for each type).
    Shown on the card; the view computes no rate from them.
  - `world` (optional): the engine's id of the world the environment is (a run of the engine).
- **`runs`**: one or more runs. Two runs of one world, one of each form of the law, are shown as a
  pair under one clock (below, "The two forms of the law, side by side"). The view says nothing of
  which is right.
  - `mode`: `single lineage` (one daughter carries on at each fission). `population` is reserved for
    a run of a fixed number of slots; the view leaves its place and draws none yet.
  - `world` (optional): the world the run is of, in the engine's own words for it. Runs that say they
    are of one world share its environment (the matrix and the supply) and its rules.
  - `law`: the law of catalysis the run ran, in its own words (`name`, `says`), with:
    - `form` (optional): which of the two forms of the law it ran, `single-event` or
      `pair-consistent` (below). An example may state it.
    - `engine_name`: the engine's own name for the law the run used, as the run's record gives it;
      null until the engine has one. The view shows it as words beside the form and binds to none:
      **no code of the viewer reads a proposed name**, and the view never decides a form from a name.
  - `founder`: the composition at the lineage's start, as sparse pairs `[type index, count]`.
  - `fissions`: the fission table, one entry for each fission k = 1, 2, … in order.
    - `parent`: the composition just before the fission (the row at the fission's time);
    - `first`: the first daughter's counts; **the second daughter is the parent less these**, as the
      view works out and says;
    - `continues`: `first` or `second`, the daughter that carries the lineage on;
    - `similarity`: the run's own H of the parent with the first and with the second daughter, the
      cosine of the two count lists;
    - `totals`: the lineage's cumulative joins, leaves and discarded molecules at the parent's row,
      since the lineage began;
    - `nominal` (optional): the fission's time in the model's own units.
    - `keys` (optional): the run's own carrier keys, `{parent, first, second}`, in the run's spelling
      (`run.keys.spelling`); shown on the fission's panel.
  - `trace` (optional): every molecule that joined or left, in order: for each growth (from the
    founder or a daughter to the next parent) the number of events in `growths`, and the events as
    signed type numbers (`+(i + 1)` a join of type i, `-(i + 1)` a leave), as base64 of signed bytes.
    Without it the view steps from a daughter to the grown parent and says that the growth between
    was not saved. `trace.times` (optional): `{encoding, values}`, each event's place in its growth's
    span (from the growth's start, its birth, to its fission) as 0 to 65535, unsigned 16-bit
    little-endian in base64. Where it is given, the clock spaces a growth's events by the run's own
    times; where not, evenly.
  - `states` (optional, a run of the engine): `{says, lines: [{path, text, unit?}]}`, what the run
    states of its law's check and of its ledger, each line its place in the run's record and the
    run's own text (numbers as the record writes them, `1e-09` staying `1e-09`). The run's panel shows
    every line as it is, with no gloss: the view says nothing of which form is right.
  - `provenance` (optional, a run of the engine): where it came from, as its record names it: the run
    folder (relative to the evidence, no machine path), the record's format, the engine's model, laws
    and operators, the interface IDs the record gives (copied, never held by the viewer), the source
    revision and whether it was clean, the run's qualifier, its definition's hash, its world, the
    SHA-256 of its files as its manifest gives them, and how it ended.
  - `analysis` (optional): what an analysis of the run adds, by `by`.
    - `inheritance`: what it `compares`, its `threshold`, whether the comparison is `strict` (above
      the threshold, so that equality is a break), its words, and a mark for each fission, in order.
      **The view reads the marks; it never works a verdict out.** Where a run states no threshold,
      no line is drawn.
    - `composomes`: null, or `{"method", "settings", "names": [{"id", "label", "fissions": [k, …]}]}`.
      **A composome is named only where this names it**, with its method; the view runs no clustering.
- **`sources`**: what the run's rules and constants rest on, each with its licence and its class
  (D173). Only a permissive source stands behind a number.

## Rules the view keeps

1. **The run's H is read, never recomputed, for the fissions it saves.** H between any other two
   compositions (the carpet; a daughter against itself grown) is worked out by the view from the
   saved counts and said to be. A test holds the view's own H to the run's at every fission.
2. **The 0.9 line stands only on the comparison of a parent with the daughter that carries on**,
   and only where the run's analysis states the threshold. Anywhere else a threshold is the picture's
   choice and says so.
3. **What is the picture's**: the assembly drawn as lipids in water (the user, 16 November 2026:
   "visuall for now but maybe law later"): how a lipid looks (a head whose form and colour say its
   type, two tails the same for every type), how the lipids pack (a protocell, a closed shell of two
   faces with heads to the water outside and inside, the view's opening packing since 17 November
   2026; a micelle, heads to the water and tails in; or a loose cluster; the model gives an assembly
   no shape), the shell's glassy faces, how the lipids move, the paths by which one comes in from the
   water and goes out into it, how the assembly lengthens, necks and parts, the water itself
   (its depth, haze, light, caustics and specks), the free molecules' number, places and drift (their
   mix of types is the supply the run states), every size, the map's axes (the directions in which
   the lineage's compositions differ most, worked out by the view), and the layout of the lineage.
   No law of Cells computes how the lipids move and pack. Each is said to be the picture's where it
   is drawn, in a line on the picture and in the legend.
4. **Motion at every speed: the run's joins and leaves are seen.** (Until 17 November 2026 a join
   flew in only molecule by molecule; the user then asked for the molecules to be seen moving in and
   out all the time the run plays.) A joining molecule comes in from the water to its place and is a
   member from its event; a leaving one is no member from its event, and goes out into the water. The
   run gives which type joins or leaves and in what order within a growth, and a run of the engine
   when each happens (`trace.times`): the clock spaces a growth's events by those times where the run
   gives them, else evenly; molecule by molecule it walks them event by event at the same pace either
   way. Their paths are the picture's own. No more than a cap are in flight at
   once (26 wide, 14 on a phone; molecule by molecule about four): where a growth's pace would put
   more in flight, one in N of its joins and leaves is drawn in flight, N worked out from that
   growth's pace (`streamStride`), the others taking or leaving their places at once, and the legend
   says N ("1 in 2 to 8" across the run's growths at the speed shown). Where the run's own times space
   a growth's events unevenly, N is worked out from the growth's mean pace, and the cap holds a burst. The clock opens at half a
   fission a second. **One exception, said so on the picture:** at a run's start the founder's
   molecules gather from the water all at once (about four seconds), while the clock stands at the
   start. The run starts with the founder made, so the gathering is the picture's alone. With less
   motion asked for nothing gathers, flies or glows: the assembly stands, and a join or a leave
   happens in place.
5. **What helped a join** (which member's catalysis) is drawn as a brief light between the two only
   where a run records it. No field of this contract records it today, and the example does not, so
   the view draws no such light and says so on the assembly's panel. **The catalytic network inside a
   protocell** is another thing, and the run's own: for the types the assembly holds, the links are
   the factors of its world's table (`environments[].catalysis`, the column type speeding the row
   type), the strongest drawn (at most 18, 10 on a phone, of factor 10^0.5 or more); the points'
   places and the links' look are the picture's. It changes when the types held change, and never
   pulses with a join.
6. **An example** carries its mark on the picture and in the legend while it is shown.
7. **No status** is said of the model in the engine beyond what the record states.

## The two forms of the law, side by side

The engine builds both forms of GARD's law of catalysis (D192): **the preprint's single-event form,
built for the reference comparison**, and **the pair-consistent form, the engine's own law**. A run
says which it ran in `law.form`, and the engine's name for it in `law.engine_name`. The user, 16
November 2026, on showing the two side by side: "yes we'll wait for the real runs but great to have
everything ready". So:

- **The view offers the pair only for two real runs of the engine**: each names its `revision` and
  its `engine_models`, so **an example is never one of a pair** (an example names neither, and a file
  with `example` offers no pair whatever its runs state).
- **Where the entry names such a pair, the view opens on it** (the lead, 17 November 2026): on a wide
  screen side by side, the engine's default first, the pair-consistent form, labelled as the
  engine's passive law, and the preprint's single-event form beside it, labelled as the comparison
  model (D192); on a phone one at a time, the engine's default first, with a switch on the card. The
  words "the engine's passive law" and "the comparison model (D192)" are said only of a file whose
  `development` block says it is the engine's: a test's made-up runs, which name a revision too, are
  named by their forms and no more.
- **Of one world, by one set of rules, one of each form**: the same `world`, the same `environment`,
  the same `rules`, and the two `law.form`s differ. Anything else is no pair, and is not offered.
- **What is the same is drawn the same, so that what differs is seen**: one clock (both at the same
  fission at every moment), the same marks and scales (each run's own H and its own analysis's
  marks, on fences of one height), side by side, each lineage named by its run's `label` and its
  form (with the engine's name where the run gives one), on the picture and in the stamp.
- **The page shows no comparison of the two forms on invented numbers.** The tests hold the pair on
  a test's own two made-up runs (`tests/fixtures/assembly-forms/`), which no page carries.

## What the lens needs from an entry

The entry (its contract and its place in the species switch are designed with the cell-type
contract) gives the lens:

| Field | What the lens does with it |
| --- | --- |
| `id` (`gard`) | Matched with the run's `model.id`; a run of another model is refused |
| `kind`: `model system` | The kind of view to open: this lens, not the Cell view |
| `levels`: `[{id, label}]` with ids from `molecules`, `assembly`, `population`, `lineage` | The scale rail's stops, in order; a level the entry lacks is not offered |
| `runs`: the run files it names, with their labels | What the view loads; the first is shown first |
| `modelled`: `{state, text}` | The card's "What Cells models of it", word for word |

## The adapter, from the engine's run format

`tools/adapt_assembly_run.py` (17 November 2026) writes one file of this contract for each run folder
of the engine's stochastic assembly family (`cells.assembly_lineages.run@1`: `run.json`, `world.json`,
`records.npz`, `manifest.json`; the run folder's `FORMAT.md` says what each holds). It reads the
arrays with the viewer's own reader (`tools/lib/npy_reader.py`: no numpy, nothing of the engine), finds
each through `run.json`'s own `records` table (its file, array, axes, base and unit held to what it
reads), and reads every convention from the run's own tables. It holds no interface ID of the engine:
the run's own are copied into `provenance`. It stops with a plain error where the run lacks what this
contract needs (an empty daughter's similarity, a growth after the last fission that holds events, a
record of another shape) or states something it does not know (a key of `run.json` it has not met).
Same input, same bytes.

| Field here | Read from the run |
| --- | --- |
| `environments[].types`, `catalysis`, `reservoir`, `rates` | `world.json`: `derived.types`; `world.law_data.catalysis_matrix` (log10, two decimals); `world.supply`; `derived.join_rate`, `leave_rate` |
| `founder` | `assembly_count` at the start row (`row_kind`'s legend), held to `world.founder` |
| `fissions[].parent`, `first`, `continues` | `assembly_count` at the fission's parent row; `fission_split`; the daughter row itself, held to `fission_followed` |
| `fissions[].similarity`, `nominal`, `keys` | `fission_similarity`; `fission_time`; `fission_parent`, `fission_daughters` (carrier keys, spelt s:c) |
| `fissions[].totals` | `joined_total`, `left_total`, `discarded_total` summed over the types at the parent row |
| `trace.growths`, `events`, `times` | `events_per_growth` (one for each fission; the run's last, after its last fission, must be empty), `event_channel` through `channels.rows`, `event_time` within each growth's span; replayed to every parent |
| `law` | `law.id` (as `name` and `engine_name`), `law.form`; `says` the run's own `g_join_i`, `g_leave_i` |
| `states` | `law.check`, `law.world_report` (where not null) and `ledger.closure`, line by line as `run.json` writes them |
| `revision`, `engine_models`, `provenance` | `source`, `engine_models`, `run.qualifier`, `definition_sha256`, `world`, the interfaces, `manifest.json` |
| `development` | given to the adapter (`--standing development --standing-from WHERE`): the run states no standing |

A run of the engine carries no analysis: no threshold is drawn and no fission is marked (rule 2).

**What the run has that the view does not use yet:** the thermodynamic ledger row by row
(`exchange_heat_kT`, `fission_work_kT`, `discarded_free_energy_kT`, `log_weight`,
`ledger_residual_kT`); the lives table (birth and end of every life, the daughters not followed with
their end reasons and censoring); the channel table's rate formulas; the streams' keys and counters.
**What the view would want that the run does not record:** what helped any one join (which member's
catalysis tipped it: rule 5), and the run's own standing.

**The two forms of the law, in D192's words** (`docs/DECISIONS.md` on main, D192, "The
reversibility finding, as checked"): in a closed two-type world, the preprint's single-event kernel
generically fails Kolmogorov's cycle criterion (a rank-one catalysis matrix is the exception); the
original authors' kernel is not established either way; the preprint's vector-Poisson contracts were
not tested; the preprint's driven runs are not affected; the pair-consistent form is exactly
reversible. The engine builds both forms, and its first experiment measures the difference. A run
names its form in `law.form` and the engine's law in `law.engine_name`; the viewer shows no comparison of the two forms on invented numbers, and judges neither.

## What the engine's runs will be, and what this contract carries of them

D192 decides how the engine's GARD runs are made. Each, and what this contract does with it:

| D192 | This contract |
| --- | --- |
| The exact stochastic simulation (direct method), one molecule per event | Carried as it is: `trace.events` is one signed type per event, in order, and `trace.times` each event's place in its growth's span; a fission's `nominal` time is the run's |
| Abstract assemblies first, over a generic ideal-mixing phase | Carried as it is: an assembly is counts only. Its shape, size and look in the view are the picture's (rule 3) |
| A dense lognormal matrix, β = exp(−4 + 4Z), about 100 types, as each world's data | Carried as it is: `environments[].catalysis.rows`, log10 to two decimals, 100 × 100 (about 50 kB a world). A run of several worlds gives one environment for each |
| Both forms of the law | Carried: `law.form` says which, `law.engine_name` the engine's name for it, and `world` which world; two runs of one world, one of each form, are shown side by side (above) |
| τ-leaping later, only as a qualified fast mode | Would need one field: a run made so gives no event trace, and says its mode; the view then steps from fission to fission (as it does for any run without a trace) |
| A population of slots (`cells.population_replacement@1`, later) | `mode: "population"` is reserved; its fields are written when a run of one exists |

Nothing else had to change for the engine's runs: the adapter (above) writes them into this contract.

## The example

`data/origin/example-run.json`, written by `tools/make_assembly_example.mjs` (deterministic: run
twice, it writes the same bytes; a test holds the committed file to it). Two lineages of 120 fissions
in one environment, by the rules the tool's opening comment states with their sources. It is marked
as an example, names no engine model, and is not any published study's run.

## Vesicle replays in recorded seconds

The vesicle entry reads `cells.visualizer.assembly_run@2`. The adapter dispatches on
`run.json` format and reads the bundle using the viewer's standard-library NPZ reader.
The source contract is the engine's published FORMAT.md, FORMAT_OL2.md and FORMAT_PORES.md.
The caller supplies the standing and its source. The two included files are development
runs on OL5's registered inputs with a row at every committed event. Their output records
the clean execution revision, world ID, run qualifier and digests of the three files read.
The adapter verifies the digests against the bundle manifest and enforces a 1,000,000-byte
limit per adapted file. Raw bundles stay outside Git.

| Output | Meaning and source |
| --- | --- |
| `places`, `species` | Recorded place indices, species, phases, finite or held status, held concentration and available catalogue identity. A held pool place has no molecular count. |
| `channels`, `trace` | Each signed event code maps to the channel's own forward or reverse reactants and products, indexed by place. Event times are saved in seconds at their original precision. A same-species transfer can be shown moving between its stated phases. |
| `rows` | Saved time, event index and named row kind. Each changed slot carries its place counts, footprint in quanta, and recorded volume in L and tension in N/m where present. The first row supplies every slot. A null slot has become vacant. A repeated slot state may be omitted. Population pool counts are a separate row field. |
| `shears` | Every shear attempt, outcome, schedule, recorded parent key and counts, shear work in kT, and, for a split, all daughter keys, counts, birth-lysis flags and the followed daughter index. A refused attempt leaves the parent in place. |
| `releases` | The osmotic lysis record supplies the threshold cause, triggering tension, limit and returned counts by pool place. Pore events supply their own cause, carrier, slot, time, hold, tension, area and returned counts. |
| `holds` | Recorded hold index, start, end and applied tension. The population's survival staircase counts the founder vesicles still present after each recorded rupture. It has no fitted curve. |
| `development` | The lead's standing, geometry, OL5 comparison and experiment-judging words. A pore bundle also carries the rupture law's own standing. |

The cursor chooses the last saved row at or before the playhead. All rows at a shared
timestamp retain their original order. The last intact threshold row and the post-release
end row have the same time and are independently inspectable. Between rows, molecular
counts can be read by replaying the recorded channel stoichiometry. Geometry samples hold
until their next row. The diagram maps footprint to displayed area and lumen volume to
displayed volume. The renderer supplies the shell, lipid packing, solute positions, directions
of travel, daughter markers and release shapes.

The optional molecular illustration uses the wwPDB LBN ideal conformer. The stored reference
contains the coordinates in ångströms and bonds of the 52 heavy atoms. The run's species
labels are carried independently. [wwPDB POPC chemical component](https://www.rcsb.org/ligand/LBN)
