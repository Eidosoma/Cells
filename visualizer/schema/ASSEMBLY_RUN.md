# Assembly run: what the assembly view reads of a lineage of assemblies

Status: **fixed for the viewer, 16 November 2026**, so that the view and its example can be built
standing alone. The user chose the options of `docs/ORIGIN_OF_LIFE.md` the same day ("go on your
recommendation on all of those", "be ambitous"); its section "Decided" is the brief.

A model system under the heading "Origin of life" (the first is a GARD assembly) is shown by a view
of its own: an assembly growing molecule by molecule and splitting, its composition, the similarity
across each fission, the lineage, and the table of catalysis it grows by. This file is what that view
reads: `cells.visualizer.assembly_run@1`. It is the viewer's own contract. **No GARD run of Cells'
engine exists, and nothing of GARD is in the engine.** The engine's GARD design note is on main,
decided on 16 November 2026 (`docs/GARD_DESIGN.md`, D192), and GARD is built in step 4 of D194's
order; the table below says which of the records the note designs each field would be read from, and
an adapter is written when the engine's first run exists. No code of the viewer binds to those names.

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
  - `reservoir`: the held concentration of each type (`each` where all are the same); `rates`: the
    basal join and leave constants. Shown on the card; the view computes no rate from them.
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
  - `trace` (optional): every molecule that joined or left, in order: for each growth (from the
    founder or a daughter to the next parent) the number of events in `growths`, and the events as
    signed type numbers (`+(i + 1)` a join of type i, `-(i + 1)` a leave), as base64 of signed bytes.
    Without it the view steps from a daughter to the grown parent and says that the growth between
    was not saved.
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
   type, two tails the same for every type), how the lipids pack (a micelle, heads to the water and
   tails in, or a loose cluster; the model gives an assembly no shape), how they move, how one seeps
   in from the water and out into it, how the assembly lengthens, necks and parts, the water itself
   (its depth, haze, light, caustics and specks), the free molecules' number, places and drift (their
   mix of types is the supply the run states), every size, the map's axes (the directions in which
   the lineage's compositions differ most, worked out by the view), and the layout of the lineage.
   No law of Cells computes how the lipids move and pack. Each is said to be the picture's where it
   is drawn, in a line on the picture and in the legend.
4. **Motion at speed.** Molecules seep in and out only molecule by molecule, at most four in flight
   at once. At a step of fissions a second below two, a molecule that joins appears at its place with
   a short glow, at most ten at once; from two fissions a second, nothing flies or glows. The clock
   opens at half a fission a second. So the assembly reads as an assembly at every speed. **One
   exception, said so on the picture:** at a run's start the founder's molecules gather from the
   water all at once (about four seconds), while the clock stands at the start. The run starts with
   the founder made, so the gathering is the picture's alone. With less motion asked for nothing
   gathers, flies or glows: the assembly stands, and a join or a leave happens in place.
5. **What helped a join** (which member's catalysis) is drawn as a brief light between the two only
   where a run records it. No field of this contract records it today, and the example does not, so
   the view draws no such light and says so in its legend.
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

## The records the engine's design names, for the adapter

From the engine's GARD design note (`docs/GARD_DESIGN.md` on main, decided, D192), section 5. These
names are the design's; nothing in the viewer reads them until a run exists.

| Field here | Would be read from |
| --- | --- |
| `environments[].types` | the declared type family `t000` … |
| `environments[].catalysis`, `reservoir` | β and ρ, arrays beside the run's definition |
| `fissions[].parent` | `assembly_count` at the row a fission's time holds (`time.event_rows`) |
| `fissions[].first`, `continues` | `fission_split`, `fission_followed` |
| `fissions[].similarity` | `fission_similarity` (`boundary_similarity`, a `level` on the fission table) |
| `fissions[].totals` | `joined_total`, `left_total`, `discarded_total` (`cumulative` since the lineage began) |
| `fissions[].nominal` | `fission_time` |
| `trace` | the event trace, saved on request only |
| `analysis.inheritance`, `analysis.composomes` | the analysis in `validation/gard/`, not the run |
| `law.name` | the law the run's definition names (`cells.member_catalysis_at_state@1` or `cells.member_catalysis@1`) |
| `time` | the `fission` time base; nominal time |

**The two forms of the law, in D192's words** (`docs/DECISIONS.md` on main, D192, "The
reversibility finding, as checked"): in a closed two-type world, the preprint's single-event kernel
generically fails Kolmogorov's cycle criterion (a rank-one catalysis matrix is the exception); the
original authors' kernel is not established either way; the preprint's vector-Poisson contracts were
not tested; the preprint's driven runs are not affected; the pair-consistent form is exactly
reversible. The engine builds both forms, and its first experiment measures the difference. A run
names its form in `law.name`; the viewer shows no comparison of the two forms on invented numbers.

## What the engine's runs will be, and what this contract carries of them

D192 decides how the engine's GARD runs are made. Each, and what this contract does with it:

| D192 | This contract |
| --- | --- |
| The exact stochastic simulation (direct method), one molecule per event | Carried as it is: `trace.events` is one signed type per event, in order. The run's own times of the events are not carried; the view counts events, and a fission's `nominal` time is the run's |
| Abstract assemblies first, over a generic ideal-mixing phase | Carried as it is: an assembly is counts only. Its shape, size and look in the view are the picture's (rule 3) |
| A dense lognormal matrix, β = exp(−4 + 4Z), about 100 types, as each world's data | Carried as it is: `environments[].catalysis.rows`, log10 to two decimals, 100 × 100 (about 50 kB a world). A run of several worlds gives one environment for each |
| Both forms of the law | Carried: `law.form` says which, `law.engine_name` the engine's name for it, and `world` which world; two runs of one world, one of each form, are shown side by side (above) |
| τ-leaping later, only as a qualified fast mode | Would need one field: a run made so gives no event trace, and says its mode; the view then steps from fission to fission (as it does for any run without a trace) |
| A population of slots (`cells.population_replacement@1`, later) | `mode: "population"` is reserved; its fields are written when a run of one exists |

Nothing else must change for the engine's runs. The adapter from its records (the table above) is
written when the engine writes its first run.

## The example

`data/origin/example-run.json`, written by `tools/make_assembly_example.mjs` (deterministic: run
twice, it writes the same bytes; a test holds the committed file to it). Two lineages of 120 fissions
in one environment, by the rules the tool's opening comment states with their sources. It is marked
as an example, names no engine model, and is not any published study's run.
