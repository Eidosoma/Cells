# Cells visualizer

A 3D viewer for Cells: the architecture today, experiment replays next.

It is tooling, asked for by the user on 14 November 2026. It reads a checkout and saved
run outputs, and it is never imported by the engine (D006, D154). It settles the open
viewer-technology item O006: three.js with web components, no framework.

**Audience:** the team, investors, other scientists and the public. Every part therefore
has a plain-language line first and the technical detail after it.

## What it shows

One data file, the scene, drawn through two lenses:

| Lens | What you see |
| --- | --- |
| **Cell and scales** | What Cells can simulate, drawn where it happens: a cutaway cell, the sheet of cells around it, and outlines of the organ and whole organism it would belong to. Zoom is continuous from molecules to organism |
| **Engine** | The simulator as a stack of layers, from the machines it runs on up to the experiments. References stand outside the stack, because the engine never contains them. The plan's gates climb beside it |

Two things are encoded, and kept apart:

- **Status** sets colour and form: qualified or judged, landed, established, designed,
  planned, failed, external reference. Built parts are solid; parts not built are ghosts.
- **Representation** says how the engine treats a capability: simulated, modelled in
  aggregate, prescribed, or illustration only. Shapes that stand for modelled populations
  (channels, pumps, protein cages) are illustrations and are labelled so.

Rules the map keeps, so it can be shown outside the team:

- It states no status the record does not state. The shared-state entities and the plan's
  gates carry the plan's own words, not an inferred status.
- Every status has a source and, where the record gives one, a date.
- Everything drawn is bound to a part of the scene or is neutral grey illustration.
- The cell picture carries the README's caveat: capabilities vary by model, and
  whole-cell integration is ongoing. The legend's "Runs together in" filter shows which
  parts run together in one model today.

## Run it

```bash
cd visualizer
npm install                 # three.js 0.170.0 and esbuild, both pinned
npm run extract             # read the main checkout, write data/architecture/architecture.scene.json
npm run serve               # http://127.0.0.1:4173/  (add -- --offline to load three.js locally)
npm test                    # scene, sources, page and allowed hosts; no browser needed
npm run check:input         # real clicks, drags and wheel in headless Chrome (picking, the cut-away, zoom between scales)
npm run shot -- --out /tmp/shot.png --query "lens=engine&select=num.imex" --theme dark
npm run export              # out/cells-architecture.html, the page as an artifact wants it
```

From another machine, forward the port (`ssh -L 4173:127.0.0.1:4173 host`) or open the
published artifact. `npm run export -- --standalone` writes one complete HTML file that
opens straight from disk.

The preview server sends a content policy close to the artifact frame's, so a load that
would be blocked when published is reported in the terminal while developing.

## How it is built

```
checkout (src/, docs/) ──tools/extract_architecture.py──┐
data/architecture/overlay.json (curated, sourced) ──────┼─▶ scene JSON ─▶ <cells-viewer> ─┬─▶ npm run serve
run outputs ──adapters (next)── run view ───────────────┘                                 └─▶ npm run export ─▶ artifact
```

| Path | Holds |
| --- | --- |
| `tools/extract_architecture.py`, `tools/lib/static_eval.py` | The extractor. Standard library only; parses source with `ast` and never imports `cells` |
| `data/architecture/overlay.json` | The curated layer: layers, statuses with sources and dates, plain lines, planned parts, the capability map |
| `data/architecture/architecture.scene.json` | The generated scene (committed, so changes show in diffs) |
| `schema/RUN_VIEW.md` | Draft of what a run saves so it can be replayed (the consumer side of D154) |
| `src/scene/model.js` | The scene format's reader and its structural checks |
| `src/core/` | Stage (renderer, camera, picking), camera control, labels, theme, status materials |
| `src/lenses/` | `stack.js` (engine), `cell.js` and `cell_parts.js` (cell and scales) |
| `src/ui/` | `<cells-viewer>` and its parts: panel, legend, list |
| `src/page.html`, `src/page.css` | The page and its colour tokens, light and dark |
| `tools/lib/build_page.mjs`, `serve.mjs`, `export_page.mjs`, `screenshot.mjs` | One page builder for every delivery mode |
| `tests/`, `tools/check_input.mjs` | Browser-free checks, and a real-input check driven through Chrome's DevTools protocol |

**What comes from the code** and so cannot drift: the files in each part and their sizes,
which part uses which (imports), the registered operators with their contract declarations
(requires, writes, provides, reads, conflicts), model identifiers, the plan's gates and the
shared-state table. Every engine file belongs to exactly one part; the extractor warns if
one does not.

**What is curated** in `overlay.json`: statuses, plain-language lines, planned parts and
the capability map. When the record changes, edit the overlay, run `npm run extract` and
`npm test`, then publish.

### The viewer as a component

```html
<cells-viewer lens="cell">
  <script type="application/json">{ ...scene... }</script>
</cells-viewer>
```

It also takes `src="scene.json"` or a `scene` property. It emits `cells-ready` and
`cells-selected`. Colours and fonts come from CSS custom properties on the page (see
`src/page.css`), so the 3D scene follows the page's theme.

## Publishing

The visualizer session publishes its own artifacts (the user, 14 November 2026).
`artifacts.json` records each one's URL so that updates go to the same link.

1. `npm run extract && npm test && npm run export`
2. Publish `out/cells-architecture.html` to the URL in `artifacts.json`.

Published pages load three.js from cdnjs, the preferred host of the artifact frame's
allowlist; everything else is inside the page.

## Git

This folder lives on the branch `visualizer`, in its own worktree, by agreement with the
lead session on 14 November 2026. The rest of the repository is read-only for this lane.
The user merges the branch when they choose.

## Next

1. **Replays.** A second scene kind built from a run directory: positions, a timeline,
   recorded channels and events. First target: a cell sheet, E07-v1 (127 cells, 623
   records, replacement events). The engine will write a view file per run (D154);
   until then adapters build the same structure from existing runs, deriving positions
   from the saved junction topology. See `schema/RUN_VIEW.md`.
2. **A replay catalogue**: every run of an experiment, by arm, seed and verdict.

Ideas kept for after the basics (the user, 14 November 2026):

- **Space–time block:** stack a sheet's records vertically, so a pattern that persists
  through turnover is a column and one that erodes dissolves.
- **Lineage arcs:** draw each donor-to-newcomer copy through time.
- **Architecture time-lapse:** run the extractor at each milestone tag and scrub through
  how the engine grew.
- **Path highlighting:** pick an experiment and light every model, operator and law it ran.
- **Verdicts and ledgers on replays:** judged predictions and conservation checks beside
  the timeline.
- **Illustrative machinery driven by aggregates:** molecular motors and channels animated
  from the modelled populations' values, marked as illustration.
- **Larger scales:** tissues beyond sheets, organs and whole animals, as the engine reaches
  them. The outlines are placeholders today.

## Known limits

- The molecular scale is one illustrative membrane patch.
- Statuses are as of the date in the top bar; the map does not update itself.
- Screenshots use software WebGL; performance on real hardware is not measured.
- Established (slate) and landed (blue) differ mainly in saturation. The four status hues
  pass the colour-blindness checks on both backgrounds; slate is a neutral and is not part
  of that check, so the panel and the list always name the status in words.
- The page has run locally under an approximation of the artifact frame's policy. A check
  inside the real frame is by eye.
- A capability marked qualified cites the pass it rests on, but a line-by-line review of
  each claim against the record is still owed before the map is shared outside the team.
