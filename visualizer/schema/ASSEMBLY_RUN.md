# Assembly run: what the assembly view reads of a lineage of assemblies

Status: **fixed for the viewer, 16 November 2026**, so that the view and its example can be built
standing alone. The user chose the options of `docs/ORIGIN_OF_LIFE.md` the same day ("go on your
recommendation on all of those", "be ambitous"); its section "Decided" is the brief.

A model system under the heading "Origin of life" (the first is a GARD assembly) is shown by a view
of its own: an assembly growing molecule by molecule and splitting, its composition, the similarity
across each fission, the lineage, and the table of catalysis it grows by. This file is what that view
reads: `cells.visualizer.assembly_run@1`. It is the viewer's own contract. **No GARD run of Cells'
engine exists, and nothing of GARD is in the engine.** The engine's GARD design note is proposed, on a
development branch, not on main; the table at the end says which of its proposed records each field
would be read from, and an adapter is written when the engine's first run exists. No code of the
viewer binds to those proposed names.

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
    "law": {"name": "the published form", "says": "…"},
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
- **`runs`**: one or more runs. Two or more in one file may be shown as a pair under one clock, each
  labelled with its own `law.name` (the user's answer 9). The view says nothing of which is right.
  - `mode`: `single lineage` (one daughter carries on at each fission). `population` is reserved for
    a run of a fixed number of slots; the view leaves its place and draws none yet.
  - `law`: the law of catalysis the run ran, in its own words. For an engine run its `name` is the
    engine's law id.
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
3. **What is the picture's**: the shape of the assembly (a micelle, or a loose cluster where less
   motion is asked for or the screen is small; the model gives an assembly no shape), where each bead
   sits, the map's axes (the directions in which the lineage's compositions differ most, worked out by
   the view), the layout of the lineage. Each is said to be the picture's choice where it is drawn.
4. **Motion at speed.** Molecules fly in and out only molecule by molecule, at most four in flight
   at once. At a step of fissions a second below two, a molecule that joins appears at its place with
   a short glow, at most ten at once; from two fissions a second, nothing flies or glows. The clock
   opens at half a fission a second. So the assembly reads as an assembly at every speed.
5. **An example** carries its mark on the picture and in the legend while it is shown.
6. **No status** is said of the model in the engine beyond what the record states.

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

## The engine's proposed records, for the adapter (proposed, on a development branch, not on main)

From the engine's GARD design note (`docs/GARD_DESIGN.md`, branch `gard-design`, e75b4b1f), section
5. These names are the note's proposals; nothing in the viewer reads them until a run exists.

| Field here | Would be read from (proposed) |
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

The engine's note has an open finding on the published kernel, under review, and proposes a second
form of the law beside it. The viewer takes no view on it.

## The example

`data/origin/example-run.json`, written by `tools/make_assembly_example.mjs` (deterministic: run
twice, it writes the same bytes; a test holds the committed file to it). Two lineages of 120 fissions
in one environment, by the rules the tool's opening comment states with their sources. It is marked
as an example, names no engine model, and is not any published study's run.
