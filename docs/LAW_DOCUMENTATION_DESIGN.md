# Plain-language pages for the engine's laws, kinds, operators and models (design)

> **Legacy cleanup (25 November 2026, D386).** Paths under `src/cells/legacy/` and the older model
> IDs named below left the engine. The tag `pre-cleanup-2026-11-25` keeps them.

*Status: proposed, 17 November 2026, for the lead. Docs only, with no code. The code was read at
main 14f03753, whose `src/` equals 75e925ea's, where seam F landed. The manifest quoted is the
lead's example, written from main at 75e925ea
(`/mnt/workspaces/Cells/declarations-example/declarations-75e925ea.json`). The visualizer's Laws
library was read on the `visualizer` branch at 2a7de02a. Tags: **(code)** read in the code; **S**
this note's proposal; "from memory" where a fact was not checked.*

**The request.** The user, 17 November 2026: "how do we offer human readable documentation on the
laws and operators etc, maybe we need a template, and we need those to start with simple terms
descriptions so working for scientists across fields", and "also so we can link to those in the viz
tool so probably many .md files also easier to maintain". The same day, the coordinator relayed
the Laws library's five needs from each manifest entry (§4.1).

**Engine models it runs:** none. Building it is tooling, which needs the user's explicit approval
(AGENTS.md, "Milestones and provenance").

## 0. The plan

- **One Markdown page for each registered piece and each active model,** at
  `docs/library/<namespace>/<section>/<name>@<major>.md`. The path is derived from the namespaced
  ID, so a page never moves when code does. Today that is 38 pieces and 5 models: 43 pages (§1).
- **One template.** Every page opens with one plain sentence and a short plain paragraph that a
  biologist, a chemist, a physicist and a computer scientist can each follow. Then come, under
  fixed headings, the declared facts, the mathematics, the sources, the checks, the status and the
  links (§2).
- **One source for each fact.**
  - What the code declares is generated from the declarations manifest into marked blocks.
  - The words are written by hand, on the page, never in code.
  - One tier-1 test fails when a registered piece has no page, a page has no piece, a generated
    block is stale, a plain layer is empty or a link breaks (§3).
- **The viewer links both ways.**
  - `cells.declarations@2` gives each piece the path of its page (`doc`) and the coordinator's
    other four items.
  - The Laws library links the page at the manifest's revision and quotes its one sentence.
  - Each page names its address in the viewer (§4, §7).
- **One glossary** says each term in the words of all four fields (§5).
- **Contributors add a page with their piece,** as the contributor guide and the pull-request
  template (D185) say (§6).
- **The manifest's format page,** `docs/library/DECLARATIONS_FORMAT.md`, becomes its specification
  in place of the docstring. The same test holds it to the code, and it settles CORE_SEAMS §15's
  three meanings of null (§7).
- **Three pilot pages** are drafted in Appendices A–C. Writing them found ten gaps in what the
  code declares (§8).
- **The estimate:** 8.5–14.5 agent-days in all. A first landing is 3.5–5.5 of them, @2 included.
  Upkeep is about 0.1–0.2 agent-day per new piece (§9).

| # | Question | Options | Recommendation |
| --- | --- | --- | --- |
| 1 | Where pages live | (a) beside the code; (b) `docs/library/<namespace>/<section>/<name>@<major>.md`; (c) one flat folder | (b) (§1) |
| 2 | The template | — | Eight fixed headings and one optional one, plain layers first (§2.1). Kinds, operators and models change the middle (§2.2) |
| 3 | One source | What is generated: (a) nothing; (b) the declared facts, between markers; (c) whole pages. Where the one sentence lives: (a) in the declaration; (b) on the page | (b) and (b), held by one tier-1 test; the manifest carries `doc` (§3) |
| 4 | The viewer's links | (a) the viewer derives paths itself; (b) the manifest gives them | (b), with the one sentence read from the page (§4) |
| 5 | The glossary | (a) terms defined on each page; (b) one page | (b) (§5) |
| 6 | Contributors | (a) a guide; (b) a guide, a pull-request checklist, a scaffold command and the same test | (b) (§6) |
| 7 | The format page | (a) the docstring; (b) a page held to the code by a key-set test; (c) (b) plus a JSON Schema | (b) (§7) |
| 8 | Pilot | — | Appendices A–C |
| 9 | Upkeep and estimate | — | §9 |

## 1. One page per piece (Q1)

### 1.1 What gets a page

- **Every piece the manifest lists, and only those:** at 75e925ea, 14 laws, 5 kinds and 19
  operators (**code**: the example manifest).
- **The active models with declared structure:**
  - the inner model, `cells.resolved_pump_tissue@3`;
  - the composite, `cells.resolved_pump_composite@1`;
  - the three compositions that `frozen_definition` rewrites: `resolved_pump_water@1`,
    `resolved_pump_water@2` and `resolved_pump_replacement@1` (**code**:
    `definitions/pump_composite_spec.py`).

  They come from @2's `models` section (§7).
- **No page:**
  - **The older model families,** active or legacy. Their laws are tables inside them, and the
    legacy ones are to be dropped (D196). Their existing guides stay as they are.
  - **A catalogue law in a `LAW_CODES` table, or a named constant in no registry.** The
    coordinator ruled that the manifest is the whole truth of what is declared. So a catalogue law
    that an active host can use gets its page in the change that registers it: seam F's step 2,
    with `parity` and `moved_from` (CORE_SEAMS §8.6). Anything else gets none.
  - **A piece named only in a design note.** The note is its document until it is registered.
  - **Solvers and step methods,** until a registry declares them.

### 1.2 The path

The page is at `docs/library/<namespace>/<section>/<name>@<major>.md`.
- **`namespace`, `name` and `major`** come from the namespaced ID. A bare ID is in `cells`
  (D185's rule; `kind_registry.qualified`), so the viewer's bare `kv1p5_mh@1` and the manifest's
  `cells.kv1p5_mh@1` name one page.
- **`section`** is `laws`, `kinds`, `operators` or `models`.
  - The manifest's key is the pair (piece, ID), and the three registries are separate, so one ID
    could name both a law and a kind.
  - IDs already repeat across kinds of thing: the proton buffer's read ID, `rapid_proton_buffer@1`,
    qualifies to its kind's ID, `cells.rapid_proton_buffer@1`, though the read is not a registered
    piece.

**Examples:**
- `cells.kv1p5_mh@1` → `docs/library/cells/laws/kv1p5_mh@1.md`;
- `cells.transporter@1` → `docs/library/cells/kinds/transporter@1.md`;
- a contributed `example.boltzmann_mh@1` → `docs/library/example/laws/boltzmann_mh@1.md`.

**Why this form (S):**
- **Not where the code is.** D188's move 2 and CORE_SEAMS §8.2's one module per law will move
  files soon; the ID does not move.
- **Not by interface.** A piece keeps its ID when its interface takes a new major, as seam A's
  cycle laws may (CORE_SEAMS §15), so a path by interface would move.
- **The namespace first.** Each contributed module's pages then sit in one folder with one owner
  (D185: its own folder, namespace and named owner).
- **The ID verbatim, `@` included,** so a search for the ID finds its page.
  - `@` is legal in Git paths and in URL paths, and GitHub serves paths such as
    `node_modules/@types/…` (from memory). The tool's first build renders one page on GitHub and
    checks its links, mathematics and tables.
  - IDs and file names are always written in backticks. Otherwise GitHub's Markdown would turn
    `name@1.md` into an e-mail link (the GFM autolink rule, from memory).
- **A changed piece takes a new ID,** so it gets a new page. This is D147's rule as D148 reads it
  ("D147 makes an ID promise its semantics"), and as the inner-model design (§6) states it for
  each piece: "a changed behaviour takes a new ID". D148 admits an in-place fix only when physical
  fields stay bitwise identical.
  - The model IDs are the exception: a restructure that passes the results gate keeps @3's ID
    (D172). A model page holds words and rows, never mathematics, so it is regenerated, not
    rewritten.
  - The old page stays while its ID is registered, and it goes in the commit that unregisters the
    ID.
  - Links pinned at a revision, as the viewer's are, keep working.

### 1.3 The library's other files

| File | Made | Holds |
| --- | --- | --- |
| `docs/library/README.md` | Generated | The index: every page by section and interface, with its one sentence and its status. GitHub shows it when the folder is opened |
| `docs/library/TEMPLATE.md` | By hand | §2.1's skeleton and its writing rules |
| `docs/library/GLOSSARY.md` | By hand, with generated backlinks | §5 |
| `docs/library/DECLARATIONS_FORMAT.md` | By hand, held to the code by the test | §7 |

- **The pages are plain GitHub Markdown,** with GitHub's `$…$` and `$$…$$` math (from memory).
- **A static site** could be built from the same files later; nothing here needs one.
- `docs/README.md` gains a line for the library when it lands.

## 2. The template (Q2)

### 2.1 The layers

**G** marks a generated block and **H** a hand-written part. The headings are fixed, so their
GitHub anchors are stable (§4.2).

````markdown
# <Plain name> (`<namespaced ID>`)

**In one sentence:** <H: one sentence that biology, chemistry, physics and computing can each follow>

## In plain words
<H: what it does, why it matters in a cell, and what it leaves out>

## Seen from each field
<H, optional: one line each for biology, chemistry, physics and computing, where the fields name
the same thing differently>

## At a glance
<!-- generated: at-a-glance -->

<G: piece and interface; the ID and the spelling definitions use; its host; the models whose
definitions can declare it; its provenance tag; for a channel law, its registry code>

<!-- /generated -->

## What it reads and changes
<!-- generated: touches -->

<G: one table, a row per field or per row by role (reads, changes, owns, writes, provides, controls),
with its axes, unit and which way is positive; ledgers and energy roles; the laws it hosts or the
pieces it needs, each linked to its page>

<!-- /generated -->
<H, optional: two or three sentences on what the signs mean physically>

## The mathematics
<!-- generated: bounds -->

<G: the declared domain, step bounds and stage terms>

<!-- /generated -->
<H: the equations, each symbol with its unit; the assumptions; the domain and why; what it leaves out>

## Sources
<!-- generated: provenance -->

<G: the provenance tag; the declared citation: its works, place, licence and departures>

<!-- /generated -->
<H: each work with its mark; what was taken from it, the form or the numbers; each departure in words>

## How it is checked
<!-- generated: tests -->

<G: the declared test IDs, linked>

<!-- /generated -->
<H, in words: the independent reference, the planted error it must catch, and any recorded evidence
with its scope. Never a level: that is the Status>

## Status
<!-- generated: status -->

<G: the level, with the record it was copied from; or "Not stated: no record states a level for
this piece.">

<!-- /generated -->

## Links
<!-- generated: links -->

<G: the declaring module and kernels, as file paths; the tests; the host and related pages; the
manifest key; the format page's section; the address in the Laws library>

<!-- /generated -->
<H, optional: further reading, to design notes only>
````

**The rules for writing it (S):**
- **The one sentence:** at most 30 words, with no symbols or equations, and units named in words.
- **"In plain words":** at most 150 words. A term that a reader outside the author's field may not
  know links to the glossary at its first use.
- **Nothing in the plain layers claims more than the Status says.**
- **Name the mechanism.** Name a protein only to say where a form came from.
- **IDs, field names and file names are always in backticks.**
- **Code and test paths appear only in generated blocks,** so that a file move needs one
  regeneration and no hand edit.
- **The tool writes a blank line inside each marker,** so that a table or a list never runs into
  it.
- **The mathematics uses GitHub math,** with each symbol's unit.
- **Each work in Sources carries a mark:**
  - the project's own marks: FT (full text), FT-img (an equation image), ABS (abstract only) and
    Der (derived here);
  - plus "relayed" (taken from a named Cells document that read the work) and "unread" (named, not
    read).

### 2.2 How kinds, operators and models differ from laws

| | Law | Kind | Operator | Model |
| --- | --- | --- | --- | --- |
| What it is | Mathematics with no state of its own. Its host keeps its gates | Machinery inside the inner model: it hosts laws and keeps their state and books | A part of the composite's step, with its own state and books, carrying its own law | What a definition names, and what it declares |
| "What it reads and changes" | What it reads; the rows it changes, by role, with valence and relative permeability or counts per cycle; its gates | Owned state, with axes; readouts; controls; records; the laws it hosts; its definition key. Hooks and layout fields go in a "For developers" fold | What it reads; owned state; its writes into others' fields, with their booking accumulators; view fields and readouts; controls; ledgers; heat and work; the laws and kinds it needs | Its rows: the pieces it declares or requires, by slot, from @2's `models` |
| "The mathematics" | Its equations | What the kind computes itself, such as bookings and closures. The rates are its laws' | Its law, and where it acts in the step: event, split or in-step process | None. Further reading is its guide |
| Generated sources and test | Provenance, citation and test | None declared today (§8) | None declared today (§8) | None |

## 3. One source (Q3)

### 3.1 What is generated, and what is written

| Layer | Generated from the manifest | Written by hand |
| --- | --- | --- |
| Title | The ID | The plain name |
| One sentence; plain words; each field | — | All |
| At a glance | `piece`, `interface`, `id`, `declared_id`, `host`, `models`, the provenance tag; a channel law's `code` | — |
| What it reads and changes | `reads`, `changes`, `owns`, `writes`, `provides`, `controls`, `units`, `signs`, `ledgers`, `energy`, `requires`, `laws`; the record kinds and layers in `fields` | A few sentences, optional |
| The mathematics | The domain, step bound and stage terms in `fields` | The equations, assumptions and what is left out |
| Sources | The tag and the declared citation | Each work's mark, and the departures in words |
| How it is checked | `test` | The reference, the planted error and the evidence, in words |
| Status | `status` and `status_source` | — |
| Links | `module_path`, `kernels`, `test`, the related pages, the manifest key, the viewer address | Further reading |

- **Prose stays out of code (S).**
  - `source_hashes()` hashes every `.py` file under `src/cells`. `load_snapshot` refuses a
    checkpoint whose recorded hashes differ, unless a continuity record admits it (**code**:
    `io.py`:32–37, :161–162).
  - So a wording fix in a docstring or a summary string would strand checkpoints. On a page it
    costs nothing at run time.
- **Nulls are rendered by their meaning (§7):** "Not stated", "Not yet extracted", or left out
  where the key does not apply to the piece.

### 3.2 Where the one sentence lives

- **(a) In the declaration** (a `summary` on the law template, the kind and the operator contract).
  - *For:* one source flows to the manifest, the viewer's card and the page, and an outside module
    carries it with its code.
  - *Against:* it is prose in `.py`, with §3.1's cost, and a reader from another field must edit
    Python to fix a word.
- **(b) On the page (recommended):** the line that starts `**In one sentence:**`.
  - The viewer's extractor already reads files through git at a revision (its
    `schema/LAWS_LIBRARY.md`), so it reads the sentence from `doc` at the manifest's revision.
  - The generated index copies it, and the test checks the copy.

### 3.3 The drift check

`tests/unit/test_library_pages.py`, in tier 1. It is pure Python over the active registries, as
`test_declarations.py` is, and takes seconds. It makes five claims, each with a planted error
(D187):

| Claim | The planted error that must fail |
| --- | --- |
| C1 Every registered piece, and every model with declared structure (§1.1), has its page at §1.2's path; every page names one of them | A law registered for the test, with no page; a stray page in a temporary copy |
| C2 Each generated block equals a fresh render from the active registries' manifest, compared as text, never by hashes (AGENTS.md) | One unit changed in a copy of a page |
| C3 The plain layers are present and within their limits; the title carries the ID; the headings come in order; "The mathematics" holds an equation or the line "No equations:" with a reason | An empty "In plain words" |
| C4 Every relative link and anchor resolves, glossary anchors included | A link to a missing glossary term |
| C5 The format page's key tables equal the code's key sets (§7) | A key added to a copy of `PIECE_KEYS` |

- **What it cannot check:** that the hand-written equations match the kernel. D147's rule keeps
  them stable per ID, since a changed behaviour takes a new ID (§1.2). So a page's mathematics is
  reviewed once, when its piece lands.
- **The tool is `scripts/library_pages.py`:**
  - `--new <section> <ID>` writes a page from the template, with its generated blocks filled in;
  - `--write` renders every generated block again;
  - `--check` runs C1–C5.
- **It sits in `scripts/`,** so editing it changes no source hash. It moves into the conformance
  kit when an outside module needs it (§6).

### 3.4 Should the manifest carry the page's link?

Yes (S): as `doc`, which is the coordinator's item 1.
- **Derived, never read from disk.** For an in-tree namespace, `doc` is §1.2's path. An installed
  engine cannot see `docs/`, so it cannot confirm that the file exists. C1 confirms it at every
  main revision.
- **An outside module's page** cannot live in `docs/`, and the tier test cannot reach it.
  - Its `Module` (module stage 1) declares where its pages are.
  - `doc` is that address, or null.
  - The conformance kit checks those pages.
- **`doc` is in @2's key set from the start, and null until the pages are complete.**
  - The key set is fixed once, because `format_errors` requires it exactly (§7).
  - While the pages are written in batches, C1 checks only that each page names a registered
    piece or model, and the viewer shows no page link.
  - The commit that completes the pages flips one switch in the manifest's generator, so that
    `doc` takes §1.2's path, and sets C1 to require a page for every piece.
  - So on main, a `doc` that is not null always names a file.

## 4. The viewer's links (Q4)

### 4.1 From the manifest: the coordinator's five items

| Item | What `cells.declarations@2` gives (S) | Notes |
| --- | --- | --- |
| 1 `doc` | §3.4 | The viewer links it at the manifest's revision, and shows no link where it is null |
| 2 The declaring module's file | `module_path` (repository-relative, beside the dotted `module`) and `line` | See the notes on lines below the table |
| 3 Citations as fields | `Citation` gains `works`, each with authors, year, title, and a DOI or URL. `licence` and `departures` stay as they are | Works rarely change, so they belong in the declaration. Whether a work was read changes as people read it, so that mark lives on the page (§2.1) |
| 4 A `models` section | Each active model's `id`, `declared_id`, `type`, `module`, `module_path`, `doc` and rows (see below) | It replaces the viewer's source parsing for its racks |
| 5 Laws that no registry declares | Nothing | §1.1: a catalogue law that an active host can use is registered by seam F's step 2 and gets its page then; the rest drop off the wall |

**Lines (item 2):**
- **Kinds and operators:** cheap. A kind gives the line of its registering call's frame; an
  operator gives its class's source line.
- **@3's five channel laws register inside one comprehension** (**code**: `inner_laws.py`), so
  their caller line would be shared. It stays null until each law registers by its own call, as
  CORE_SEAMS §8.2's one module per law gives.
- **Kernels:** cheap too (`co_firstlineno`).
- **Pages carry the path but no line.** Otherwise every edit above a declaration would make a page
  stale.

**The `models` section (item 4):**
- **`type`** is the inner model, the composite, a composition or a model family.
- **Rows** are the pieces a model declares or requires, by slot where it has slots:
  - for @3: its channel laws by code, with the next free code; its junction, cycle and route laws;
    its fuel kinds; its kinds, by definition key;
  - for the composite: its operators, any ordered subset of which is a definition;
  - for a composition: its operators in order, and its inner model.
- **A model family** is listed with no rows and no page.

### 4.2 From the page

- **The one sentence.** The card quotes it, read from `doc` at the manifest's revision (§3.2). The
  viewer's rule "What a piece computes is its module's docstring, quoted" (its
  `schema/LAWS_LIBRARY.md`) becomes "its page's one sentence, quoted".
- **Deep links** go to the fixed headings, whose GitHub anchors are stable: `#in-plain-words`,
  `#the-mathematics`, `#sources`, `#how-it-is-checked` and `#status`. GitHub's anchor rule is from
  memory; C4 implements it.
- **A glossary term** can link to `docs/library/GLOSSARY.md#<term>`.

### 4.3 Back to the viewer

- **Each page names its address in the library,** `select=laws:<namespaced ID>`, the viewer's own
  address form (its `schema/LAWS_LIBRARY.md`, "On the map's page"). The viewer should accept the
  bare spelling too, since its list uses it today.
- **The viewer's base address is not written on each page.**
  - It is a private artifact, and its address has already changed twice (the visualizer's
    `artifacts.json`).
  - One line of the generated index holds it, or nothing until the viewer has a public address
    (§10, question 3).
- **A frame links its model's page.** An Engine view box may link its family's section of the
  index.

## 5. The glossary (Q5)

- **One page,** `docs/library/GLOSSARY.md`: alphabetical, with one `### Term` heading per term, so
  that each term has a stable anchor.
- **Each entry has:**
  - a plain definition, in one or two sentences;
  - a line "In other fields:" with the words biology, chemistry, physics and computing use for the
    same thing;
  - its unit and sign convention, where it has one;
  - for a word of Cells' own (kind, host, ledger, refusal…), "Cells' word", and the document that
    defines it.
- **"Used by" is generated:** the pages that link the term.
- **A page links a term at its first use** in the plain layers, and C4 checks every such link.
- **The seed list, about 60 terms:**
  - **Cells' words:** piece, law, kind, operator, model, composite, composition, inner model, host,
    interface, namespace, ID and version, definition, world, population, patch, node, face,
    junction, held bath, finite node, species row, inventory, ledger, booking, stage, step, split
    step, refusal, domain, availability, abundance, parity, cited, calibrated, planted error,
    qualified, judged, status.
  - **Science:** membrane voltage, inward-positive, channel, pump, permeant, valence, permeability,
    gate, open fraction, constant-field flux, electrochemical potential, cycle free energy, ATP's
    drive, stoichiometry, osmotic pressure, water potential, compliance, hydraulic permeability, pH,
    buffer, heat, work.
  - **Units:** fmol, pL, pJ, mM, Pa, J/mol.

One entry, as drafted:

```markdown
### Gate

The part of a channel that opens or shuts it. For each gate, Cells tracks the fraction of a
population's channels in which that gate is open: a number from 0 to 1.

- **In other fields:** an activation or inactivation gate (biology); a two-state conformational
  equilibrium (chemistry); a relaxation variable (physics); a state variable advanced at each step
  (computing).
- **Unit:** none (a fraction).
- **Used by:** [`cells.kv1p5_mh@1`](cells/laws/kv1p5_mh@1.md), … (generated)
```

## 6. Contributors (Q6)

- **The contributor guide** (D185), as `CONTRIBUTING.md`, which GitHub shows to contributors (from
  memory), gains a section, "Add a law, kind or operator":
  1. Name it by mechanism and form, never by protein (the `law_id` rule, CORE_SEAMS §8.1).
  2. Declare it on its interface. Cite it (`Citation`, with numbers under D186 and D201). Name its
     test, which has a planted error.
  3. Run `python scripts/library_pages.py --new law <namespace>.<name>@1`. Write the plain layers
     for a reader outside your field, then the mathematics, and the sources with their marks.
  4. Run `--write` and `--check`, then the tiers and the kit.
- **The pull-request template** (`.github/pull_request_template.md`, GitHub's convention, from
  memory) asks:
  - that each new or changed piece has its page;
  - that the one sentence and the plain paragraph read well for someone outside the author's
    field. A reader from another field, or an agent asked to read as one, checks them. This is
    advice, not a gate;
  - that new terms are in the glossary;
  - that each source carries its mark.
- **An in-tree contributed module** writes its pages under `docs/library/<namespace>/`, owned by its
  named owner. C1 covers it with no edit, because C1 reads the manifest.
- **An outside module** (later) keeps its pages in its own repository, on the same template. Its
  `Module` declares where they are (§3.4), and the kit runs C2–C4 on them.
- **D185's automatic checks on GitHub** stay a separate question for the user. Nothing here needs
  them.

## 7. The manifest's format page, and `cells.declarations@2` (Q7)

**Where it goes:** `docs/library/DECLARATIONS_FORMAT.md`, the engine's own page. The viewer's
`schema/LAWS_LIBRARY.md` stays the viewer's account of its own list, and links to this page.

**What it holds:**
- **The top-level keys, and each piece key:** what it means, and which pieces it applies to.
- **The ID rule.**
  - `id` is namespaced, and `declared_id` is the spelling that definitions use.
  - `host` and `models` are namespaced, and a raw join with a definition applies D185's rule that
    a bare ID is in `cells`.
  - This settles CORE_SEAMS §15's IDs item by stating the rule, with no second spelling.
- **The three meanings of null (CORE_SEAMS §15):**
  - a key that does not apply to a piece is null;
  - a key not yet extracted is listed in a top-level `not_extracted` list of (piece, key) pairs.
    Today these are the kinds' `ledgers` and `energy`, and the `provenance` and `test` of kinds
    and operators, whose contracts have no such fields yet (§8, gaps 1 and 6);
  - any other null means "not stated". A law's `test` is extracted, so its null means that no
    test is declared.
- **Each interface's own `fields`, explained once:** for example, the channel law's `gates`,
  `permeant` and `voltage_domain_V`. Pages link to these instead of repeating them.
- **Units:** as declared, or else by the run view's suffix rule (`run_view.SUFFIX_UNITS`), which
  @2 applies to every field it lists.
- **The legacy list.**
- **The version rule:** any change of keys or of meaning is a new major, and a reader checks
  `kind`.

**How it stays in step with the code:**
- The module's docstring keeps a short summary and points to the page.
- C5 compares the page's key tables with `PIECE_KEYS`, the top-level and legacy keys and @2's model
  keys, in both directions, and checks that the page names `FORMAT`.

**@2's changes, made as one format change before the viewer binds** (CORE_SEAMS §15 says it has
not bound yet):
- `doc`, null until the pages are complete (§3.4);
- `module_path` and `line` (§4.1);
- the citation's `works` (§4.1);
- the `models` section (§4.1);
- `not_extracted`;
- resolved units;
- each read's mode, current or fixed (§8, gap 8).

`format_errors` requires the exact key set (**code**: `declarations.py`), so a key added under @1
would make every @1 reader refuse the file; hence a new major. Its owner is the manifest's owner
(seam F's step 2), not the builder of the pages.

## 8. What the pilots found in the declarations

Writing Appendices A–C found these gaps in what the code declares. They are engine items, reported
here and not filled in by hand on the pages.
1. **No piece declares a test.** `test` is null on all 14 laws, and kinds and operators have no test
   field (**code**).
2. **@3's ten laws are `parity`, with no source and no `moved_from`** (CORE_SEAMS §8.6). Kv1.5's
   sources stand only in an older family's specification (Appendix A).
3. **Channel laws declare no sign for what they move.** `ChannelLaw.SIGNS` is empty, and `UNITS`
   covers only the domain and the step bound. @3's code computes channel flux outward
   (`channel_rates`, "Outward flux and heat"), while MODULE_SYSTEM_DESIGN §2.1 calls the amount
   changes inward-positive. Only a declaration can settle this for readers.
4. **Route laws declare nothing that they change** (`changes` is empty). The definition chooses
   the species of most routes, and the proton leak's role is stated only in its citation's
   departures.
5. **The kinds' ledgers and energy roles are not extracted** (CORE_SEAMS §15), though the
   transporter books heat and work (its docstring).
6. **Kinds and operators declare no provenance or citation.**
7. **Units are missing where a field name's suffix gives them.** The water operator's `units` is
   `{}`, although its fields end in `_pL` and `_pJ`. It also declares no orientation; only a code
   comment says "Cell to outside positive".
8. **The manifest merges two kinds of read.** An operator's `reads` joins `VIEW_READS` (the current
   value) with `CONFLICTS_VIEW` (the declared value). The water operator's `membrane_area` is the
   second kind (**code**: `osmotic_water.py`:502).
9. **Kernels are named by their wrappers.** Kv1.5's is `cells.models.inner_laws._kv1p5_kinetics`,
   which calls `laws/channels/voltage_gates.py`. CORE_SEAMS §8.2's one module per law removes the
   wrapper.
10. **Kv1.5's only check of its kernel sits in an older family's tier-3 test file.**
    - The file is `tests/unit/test_voltage_gated_membrane.py`, which imports `cells.legacy`.
    - Its 19 kernel cases, against an independent scalar reference, passed in D172's tier-3
      record. 14 other cases in the file fail there for missing untracked data
      (`tests/tier3_record.json`).
    - No planted-error case for the kernel is among its test names.
    - Under D196 the check would go with that family. It should move beside the law, gain a
      planted error and be declared as the law's `test`.

Also, CORE_SEAMS §8.1's parameters (names, units, structure or value) and energy role are not in
the template as built. Until they are, the maths layer names the parameters by hand.

## 9. Upkeep, and the estimate (Q9)

**Upkeep (S):**
- **A new piece:** its page, about 0.1–0.2 agent-day within the piece's own milestone. Once C1
  covers every piece, a piece cannot land without its page.
- **A changed declaration or a moved file:** `--write`, and a look at the mathematics; minutes.
- **A qualification:** one status line, once a per-piece record exists (§10, question 4).
- **The test:** seconds in tier 1.
- **The glossary:** a few terms per new piece.

**The estimate.** It is the design lane's own, not measured. Its basis: 38 pieces and 5 models
today; 3 pages drafted here; and 0.1–0.2 agent-day for each remaining page (reading the design note
and the kernel, writing the layers, marking the sources).

| Part | Agent-days |
| --- | --- |
| The tool and the test (C1–C5, with planted errors) | 1–1.5 |
| `cells.declarations@2` and the format page (the manifest's owner) | 2–3 |
| The template, the glossary's seed and the index | 0.5–1 |
| 40 pages (3 drafted here) | 4–8, by section, on disjoint files |
| The contributor guide and the pull-request template (shared with module stage 1) | 0.5 |
| Review: the advisor, and a reading of the plain layers by someone outside each field | 0.5 |
| **Total** | **8.5–14.5**: about 4–6 working days elapsed, with three or four agents |

**The order of building:**
1. `cells.declarations@2` and the format page, by the manifest's owner, with `doc` null (§3.4).
   The pages render from @2: the model pages need its `models` section, and the null meanings
   need its `not_extracted`.
2. The tool and the test (C1 in its partial form), the template, the glossary's seed, the index
   and the three pilot pages.
3. The other 40 pages, in batches.
4. The commit that completes them: `doc` takes its paths, and C1 requires every page.

- **A first landing, if the user wants it small,** is steps 1 and 2: about 3.5–5.5 agent-days, of
  which @2 is 2–3. The viewer shows no page links until step 4.
- **The viewer's side** is the visualizer session's work, not counted here.

## 10. Questions

**For the user:**

1. **Approve building it?** It is tooling (AGENTS.md). As a whole, or the first landing first?
2. **Where does the one sentence live?** On the page (recommended), or in the code, where every
   wording fix would strand checkpoints (§3.2)?
3. **Links from the pages into the viewer.** The repository is public and the viewer is a private
   artifact. Should its address be written once in the index now, or only once the viewer has a
   public address? Recommended: wait. Until then, pages name `select=laws:<ID>`.
4. **Per-piece status: which record do the pages copy?**
   - (a) None until a per-piece record exists, so every page says "Not stated".
   - (b) A record the lead keeps as data in the engine tree. It is JSON, so no source hash moves.
     Each level names the Progress or plan heading it was copied from. The manifest copies it, and
     the test checks that each named heading exists.
   - (c) The viewer's overlay, which already keeps the operators' levels with their sources. But it
     would be a second source.

   Recommended: (a) now, and (b) when the first level is wanted.

**For the lead:**

5. **`cells.declarations@2` (§7):** one change, owned by seam F's step 2, made before the viewer
   binds?
6. **The ten gaps of §8:** which go to seam F's step 2, and which to the owners of the kinds and
   the operators?
7. **Kv1.5's kernel check (gap 10):** move it before D196 drops its family.

## Appendix A. Pilot: a channel law, `cells.kv1p5_mh@1`

The page as it would stand at `docs/library/cells/laws/kv1p5_mh@1.md`. Its generated blocks show
the manifest's entry as it is at 75e925ea, with its nulls and empty values.

In all three pilots, the plain layers use a few textbook statements as background, such as that
potassium usually leaves the cell and that ATP is the cell's energy currency. These are from memory
and carry no citation.

````markdown
# Kv1.5-type potassium channel gating (`cells.kv1p5_mh@1`)

**In one sentence:** A potassium channel that opens within milliseconds when the membrane voltage
rises, then slowly shuts over seconds, letting potassium out so that the voltage falls back.

## In plain words

Every cell holds a voltage across its membrane, and [channels](../../GLOSSARY.md#channel) are the
pores that let ions cross it. This law says when one type of potassium channel is open. It has two
[gates](../../GLOSSARY.md#gate). The first opens within milliseconds when the inside of the cell
becomes less negative; the second shuts over seconds after the same change. Ions pass only while
both are open. Potassium usually leaves the cell, so opening this channel brings the voltage back
down. Because the slow gate remembers the last few seconds, two cells with the same open fraction
can respond differently next. The law leaves out temperature (it is fixed at 25 °C), the charge
that moves when a gate moves, and the energy of the channel protein itself.

## Seen from each field

- **Biology:** a voltage-dependent outward potassium current with slow inactivation, as SPEC-006
  relays for Kv1.5 expressed in oocytes. Its form and numbers come from another simulator's
  description of the Kv1.5 channel, not from a fit to any cell type.
- **Chemistry:** each gate is an open–shut equilibrium whose rates depend on voltage; the two
  gates are independent.
- **Physics:** two first-order relaxations toward sigmoid targets, with time constants linear in
  voltage.
- **Computing:** a pure function from voltage to targets and time constants. The host advances the
  gates and computes the current.

## At a glance

<!-- generated: at-a-glance -->

| | |
| --- | --- |
| Piece | Law, interface `cells.channel_law@1` ([its fields](../../DECLARATIONS_FORMAT.md#channel-laws)) |
| ID | `cells.kv1p5_mh@1`; definitions write `kv1p5_mh@1` |
| Runs in | [`cells.resolved_pump_tissue@3`](../models/resolved_pump_tissue@3.md), its host. Definitions of `cells.resolved_pump_composite@1` and `cells.resolved_pump_tissue@3` can declare it |
| Registry code | 0 |
| Provenance | `parity` |

<!-- /generated -->

## What it reads and changes

<!-- generated: touches -->

| Role | What | Unit | Which way is positive |
| --- | --- | --- | --- |
| Reads | None declared | | |
| Changes | `K`: valence 1, relative permeability 1.0 | Not stated | Not stated |
| Its gates, kept by the host | `m`, `h` | | |

<!-- /generated -->

## The mathematics

<!-- generated: bounds -->

| Declared | Value | Unit |
| --- | --- | --- |
| Voltage domain | −0.12 to 0.06 | V |
| Reference RK4 step | 2.5e-05 | s |
| Stage term | `constant_field_slope` | |

<!-- /generated -->

With $V$ the membrane voltage (inside less outside, in volts), $t$ in seconds and
$\sigma(x) = 1/(1 + e^{-x})$:

$$m_\infty = \sigma\!\left(\frac{V + 0.0060}{0.0064}\right), \qquad h_\infty = \sigma\!\left(-\frac{V + 0.0253}{0.0035}\right)$$

$$\tau_m = 0.008330 - 0.1163\,V, \qquad \tau_h = 1.620 - 15.50\,V$$

$$\frac{dm}{dt} = \frac{m_\infty - m}{\tau_m}, \qquad \frac{dh}{dt} = \frac{h_\infty - h}{\tau_h}, \qquad \text{open fraction} = m\,h$$

- **Domain:** −0.120 V ≤ V ≤ 0.060 V, chosen so that both time constants stay positive ($\tau_m$
  from 1.35 to 22.3 ms, $\tau_h$ from 0.69 to 3.48 s). A step outside it is refused, never clipped.
- **Assumptions:** each gate lies between 0 and 1 and relaxes monotonically at fixed $V$. Both are
  kept as state, since equal products $m h$ can have different futures. The temperature is fixed
  at 298.15 K, with no temperature law.
- **The current:** the host multiplies the open fraction by the population's permeability,
  abundance and availability, and moves potassium by the constant-field (Goldman–Hodgkin–Katz)
  flux, the form of [`cells.constant_field@1`](constant_field@1.md). Which way a positive flux
  points is not declared.
- **Integration:** the host advances each gate by its exponential stage update. The reference RK4
  step is at most 25 µs.
- **Left out:** gating charge, conformational energy and protein turnover.

## Sources

<!-- generated: provenance -->

Provenance: `parity`, moved from an older family. No citation is declared.

<!-- /generated -->

| Work | What was taken | Mark |
| --- | --- | --- |
| BETSE v1.5.0's `Kv1p5` channel, at the commit that SPEC-006 pins | The two-gate form and its coefficients, converted to SI units, with both gate powers one | Relayed from [SPEC-006](../../../VOLTAGE_GATED_CHANNEL_SPEC.md) (D049), which read the source |
| Philipson et al. 1991, which that source cites | Nothing directly. SPEC-006 states that its abstract reports Kv1.5 expressed in oocytes, with a slowly inactivating outward current, which does not establish each coefficient | Relayed from SPEC-006, which read its abstract |

**Departures, as SPEC-006 states them:** the gates follow the continuous equations, not the
source's semi-implicit update; the source's reversal-voltage constant is not used, since the
current is the constant-field flux; the domain and the fixed temperature are Cells' own choices.

**The licence of the numbers:** not stated by the declaration.

## How it is checked

<!-- generated: tests -->

Declared test: not stated.

<!-- /generated -->

An independent scalar implementation of the equations above agrees with the kernel at 19 voltages
across the domain, in NumPy and in JAX, to about 2e-15 relative. No planted error is recorded for
that comparison yet.

## Status

<!-- generated: status -->

Not stated: no record states a level for this piece.

<!-- /generated -->

## Links

<!-- generated: links -->

- Declared in [`src/cells/models/inner_laws.py`](../../../../src/cells/models/inner_laws.py) (`cells.models.inner_laws`).
- Kernels: `kinetics`, `cells.models.inner_laws._kv1p5_kinetics`; `opening`, `cells.models.inner_laws._open_mh`.
- Host: [`cells.resolved_pump_tissue@3`](../models/resolved_pump_tissue@3.md).
- Manifest entry: (law, `cells.kv1p5_mh@1`), from `python -m cells declarations --out FILE` ([the format](../../DECLARATIONS_FORMAT.md)).
- In the Laws library: `select=laws:cells.kv1p5_mh@1`.

<!-- /generated -->

Further reading: [SPEC-006](../../../VOLTAGE_GATED_CHANNEL_SPEC.md); the inner model's
declarations, [§7.1](../../../INNER_MODEL_V4_DESIGN.md).
````

**What writing it showed:**
- **Gaps 2, 3, 9 and 10 of §8.**
- **The words had to come from elsewhere.** The declaration carries no source, so the plain layers
  and the sources came from SPEC-006, an older family's specification.
- **The check is described in words only.** The kernel check found (gap 10) has no place in the
  generated block until it is declared.

## Appendix B. Pilot: a kind, `cells.transporter@1`

At `docs/library/cells/kinds/transporter@1.md`. The kinds' ledgers and energy roles are shown with
@2's meaning of null, "not yet extracted" (§7).

````markdown
# ATP-driven transporters (`cells.transporter@1`)

**In one sentence:** Membrane pumps that each spend one ATP molecule per cycle to move a fixed
number of one kind of molecule or ion across a membrane, even against its gradient.

## In plain words

Cells push many molecules "uphill", from where they are scarce to where they are plentiful, and
pay for it with ATP, the cell's energy currency. This [kind](../../GLOSSARY.md#kind) is the
machinery Cells uses to run such pumps in the tissue model. Each pump population sits on one
membrane patch. In every cycle it splits one ATP into ADP and phosphate on the cell's side, and
moves a fixed number of its cargo to the other side. A pump runs forward only while the energy
freed by ATP exceeds the energy its cargo needs to move; otherwise it stalls or runs backward. The
kind keeps the books, counting cycles, heat and the work drawn from the fuel, so that matter and
energy add up at every step. It hosts two laws today: one for an uncharged cargo, and the proton
pump that acidifies a compartment. By default the ATP supply is held steady; a finite supply is
designed but refused for now.

## Seen from each field

- **Biology:** primary active transport, such as the proton pump that acidifies a compartment
  (FR-4).
- **Chemistry:** ATP hydrolysis coupled to transport in one cycle. The cycle's free energy sets its
  direction, and saturation in the cargo and in ATP sets its speed.
- **Physics:** an energy converter whose heat is the cycle rate times minus the cycle's free
  energy.
- **Computing:** a module that registers fields and hook functions, which the inner model calls at
  fixed points of each step. Its laws are pure kernels that it finds in the law registry.

## At a glance

<!-- generated: at-a-glance -->

| | |
| --- | --- |
| Piece | Kind, interface `cells.kind@1` ([its fields](../../DECLARATIONS_FORMAT.md#kinds)) |
| ID | `cells.transporter@1`; definitions write `cells.transporter@1` |
| Runs in | [`cells.resolved_pump_tissue@3`](../models/resolved_pump_tissue@3.md). Definitions of `cells.resolved_pump_composite@1` and `cells.resolved_pump_tissue@3` can declare it, under the key `transporters` |
| Laws it hosts | [`cells.atp_driven_transporter_mass_action_positive@1`](../laws/atp_driven_transporter_mass_action_positive@1.md), [`cells.proton_atp_mass_action_positive@1`](../laws/proton_atp_mass_action_positive@1.md) |
| Provenance | Not yet extracted: kinds have no provenance field yet |

<!-- /generated -->

## What it reads and changes

<!-- generated: touches -->

| Field | Role | Axes | Unit | Record | Which way is positive |
| --- | --- | --- | --- | --- | --- |
| `transporter_cycles` | Owns | membrane_slot | fmol | cumulative | From inside to outside: "a positive cycle moves n (the stoichiometry) of the role from the patch's cell to its outside node; held fuel's maintenance restores its ATP (transporter_fuel_supplied_fmol)" |
| `transporter_dissipated_energy_pJ` | Owns | membrane_slot | pJ | cumulative | Not stated |
| `transporter_fuel_supplied_fmol` | Owns | species, membrane_slot | fmol | cumulative | Not stated |
| `transporter_metabolic_work_pJ` | Owns | membrane_slot | pJ | cumulative | Not stated |
| `transporter_cycle_rate_fmol_s` | Provides | | fmol/s | rate | From inside to outside: the same statement |
| `transporter_cycle_free_energy_J_mol` | Provides | | J/mol | level | Not stated |
| `transporter_chemical_drive_J_mol` | Provides | | J/mol | level | Not stated |
| `transporter_availability` | Controls | | | | |

Ledgers: not yet extracted. Energy roles: not yet extracted. Its records are on the `pumps` layer.

<details><summary>For developers</summary>

Hooks: `bound_rate`, `check_definition`, `control_values`, `domain`, `held_rows`, `initial`,
`ledger_terms`, `moved_rows`, `parse`, `rates`, `readouts`, `stage_term`, `structure_entry`,
`to_dict`. Layout fields: `transporter_present`, `transporter_neutral`, `transporter_proton`,
`transporter_role`, `transporter_fuel_rows`, `transporter_held`, `transporter_capacity_fmol_s`,
`transporter_stoichiometry`, `transporter_km_role_mM`, `transporter_km_atp_mM`,
`transporter_drive0_J_mol`, `transporter_c0_mM`, `transporter_ph_ref`, `transporter_ph_band`.
Experiment keys: none.
</details>

<!-- /generated -->

## The mathematics

<!-- generated: bounds -->

None declared by the kind; each law it hosts declares its own.

<!-- /generated -->

For one population with stoichiometry $n$ (1 to 4), one cycle turns ATP into ADP and phosphate at
the patch's inside cell, and moves $n$ of its cargo from the inside of the patch to its outside.
For an uncharged cargo the cycle's free energy is

$$\Delta G_\text{cyc} = \Delta_r G'_\text{ATP} + n R T \ln\frac{c_\text{out}}{c_\text{in}}, \qquad \Delta_r G'_\text{ATP} = \Delta_r G'^\circ + R T \ln\frac{c_\text{ADP}\, c_\text{Pi}}{c_\text{ATP}\, c^\circ}$$

where $\Delta_r G'^\circ = \mu'^\circ_\text{ADP} + \mu'^\circ_\text{Pi} - \mu'^\circ_\text{ATP}$
comes from the species registry's standard potentials at its standard concentration $c^\circ$,
never from a parameter. The proton law adds its charge's electrical term (its own page). Each
hosted law gives the cycle rate $J$; for each population the kind books:
- the cargo's transfer, $n J$ from inside to outside, into the shared inventory;
- the heat, $-J\,\Delta G_\text{cyc}$;
- with held fuel, the work $-J\,\Delta_r G'_\text{ATP}$ drawn from the maintenance, and the supply
  of one ATP restored per cycle, kept as a record: the held rows never move.

- **Domain:** a population is refused at a stage where $|\Delta G_\text{cyc}/RT| > 80$, where an
  input is not positive, or, under the proton law, where the inside pH leaves its declared band.
- **Version 1:** one population per patch; the fuel at the patch's inside cell; finite fuel
  refused.
- **Not here:** the rate laws, which are the hosted laws'.

## Sources

<!-- generated: provenance -->

Provenance: not yet extracted; kinds have no provenance field yet.

<!-- /generated -->

- **The kind is Cells' own design:** the inner model's transporter kind
  ([the inner-model design](../../../INNER_MODEL_V4_DESIGN.md), §7.4 (g) 2 and (k)) and FR-4's
  pump ([the compartment pH design](../../../COMPARTMENT_PH_TRANSFER_DESIGN.md), §5–6), as its
  module states. Relayed; not read again here.
- **Each hosted law declares its own citation.** Both cite the sodium–potassium pump law's
  mass-action form in Cells' own documents, and take no numbers.
- **The standard potentials** come from the species registry's records, which carry their own
  sources.

## How it is checked

<!-- generated: tests -->

Declared tests: not yet extracted; kinds have no test field yet.

<!-- /generated -->

Its tests run a one-cell world through the runner. The cargo lands in the shared inventory, the
held fuel rows never change, the maintenance's record follows the cycles, and all ten ledgers close
with the kind's terms. A planted flip of the cargo's direction must fail the material ledger. Other
tests check that a malformed declaration is refused with its reason, that a change of values reuses
the built implementation, and that the law's domain and the pH band refuse at the stage.

## Status

<!-- generated: status -->

Not stated: no record states a level for this piece.

<!-- /generated -->

## Links

<!-- generated: links -->

- Declared in [`src/cells/kinds/transporter.py`](../../../../src/cells/kinds/transporter.py) (`cells.kinds.transporter`).
- Hosts [`cells.atp_driven_transporter_mass_action_positive@1`](../laws/atp_driven_transporter_mass_action_positive@1.md) and [`cells.proton_atp_mass_action_positive@1`](../laws/proton_atp_mass_action_positive@1.md); runs in [`cells.resolved_pump_tissue@3`](../models/resolved_pump_tissue@3.md).
- Manifest entry: (kind, `cells.transporter@1`) ([the format](../../DECLARATIONS_FORMAT.md)).
- In the Laws library: `select=laws:cells.transporter@1`.

<!-- /generated -->
````

**What writing it showed:**
- **Gaps 1, 5 and 6 of §8.**
- **A kind's page is mostly generated.** The plain layers and the mathematics are short, because
  the rates belong to the hosted laws, which the page links.
- **Its test file is found only by name.** No declaration links it.

## Appendix C. Pilot: an operator, `cells.ideal_osmosis_linear_compliance_water@1`

At `docs/library/cells/operators/ideal_osmosis_linear_compliance_water@1.md`.

````markdown
# Osmotic water flow and cell volume (`cells.ideal_osmosis_linear_compliance_water@1`)

**In one sentence:** Water crosses each cell membrane toward the side with more dissolved
particles, so cells swell or shrink until an elastic back-pressure balances that pull.

## In plain words

Water crosses membranes by osmosis: it moves toward the side where dissolved particles are more
concentrated. This [operator](../../GLOSSARY.md#operator) gives every
cell, and every finite space outside the cells, a volume that changes as water flows. The flow
across a membrane patch grows with its area, its water permeability and the difference in
[water potential](../../GLOSSARY.md#water-potential) between its sides: the pressure of the
stretched compartment, less the osmotic pressure of what is dissolved in it. Concentrations are
amounts divided by current volumes, so swelling dilutes everything inside, which changes voltages
and rates. A large bath keeps its own volume and composition; the water it gives or takes is
booked as supply, with its work. Left out: changes of membrane area, water through junctions or in
open solution, and the effect of temperature on permeability.

## Seen from each field

- **Biology:** osmotic swelling and shrinking. Aquaporins raise the water permeability, which is a
  value of the definition.
- **Chemistry:** the ideal (van 't Hoff) osmotic pressure: RT times the total concentration of
  dissolved particles.
- **Physics:** flow driven by a difference of water potential through a hydraulic conductance, with
  a linear elastic pressure–volume law. The dissipated power is the flow times that difference, and
  is never negative.
- **Computing:** an operator of the composite. Half-steps of Heun's method advance the volumes
  before and after the inner model's step (Strang splitting). It owns the volume increments and
  four water ledgers.

## At a glance

<!-- generated: at-a-glance -->

| | |
| --- | --- |
| Piece | Operator, interface `cells.operator@1` ([its fields](../../DECLARATIONS_FORMAT.md#operators)) |
| ID | `cells.ideal_osmosis_linear_compliance_water@1`; definitions write `ideal_osmosis_linear_compliance_water@1` |
| Runs in | [`cells.resolved_pump_composite@1`](../models/resolved_pump_composite@1.md) |
| Where it acts in the step | A split part, by `heun_frozen_amount_water@1`; scheduled by `water_controls` |
| Needs | No law or kind |
| Provenance | Not yet extracted: operators have no provenance field yet |

<!-- /generated -->

## What it reads and changes

<!-- generated: touches -->

| Field | Role | Axes | Unit | Which way is positive |
| --- | --- | --- | --- | --- |
| `membrane_area` | Reads | | Not stated | |
| `bath_water_supplied_pL` | Owns | extracellular_slot | Not stated | Not stated |
| `bath_water_work_pJ` | Owns; work | extracellular_slot | Not stated | Not stated |
| `extracellular_volume_increment_pL` | Owns | extracellular_slot | Not stated | Not stated |
| `volume_increment_pL` | Owns | cell_slot | Not stated | Not stated |
| `water_dissipated_energy_pJ` | Owns; heat | membrane_slot | Not stated | Not stated |
| `water_transferred_pL` | Owns | membrane_slot | Not stated | Not stated |
| `volume`, `extracellular_volume`, `cell_volume_pL`, `extracellular_volume_pL`, `cell_concentration_mM`, `extracellular_concentration_mM`, `osmotic_pressure_Pa`, `hydrostatic_pressure_Pa`, `water_potential_Pa`, `water_flow_pL_s`, `water_dissipation_pJ_s`, `bath_water_supply_pL_s`, `water_availability`, `energy_balance_pJ` | Provides | | Not stated | |
| `water` | Controls | | | |

Writes into other pieces' fields: none. Ledgers: `water_local`, `water_outside`, `water_total`,
`bath_water_work`. Records: none declared.

<!-- /generated -->

## The mathematics

<!-- generated: bounds -->

None declared.

<!-- /generated -->

With amounts $n$ in fmol, volumes $V$ in pL, pressures in Pa and energies in pJ:

$$\Pi = \frac{R T \left(\sum_s n_s + n_\text{imp}\right)}{V}, \qquad P = K\left(\frac{V}{V_\text{ref}} - 1\right) + P_0, \qquad \psi = P - \Pi$$

$$Q = 10^{15} A\, L_p\, a\, (\psi_\text{cell} - \psi_\text{out}) \ \text{pL/s, cell to outside}, \qquad D = 10^{-3}\, Q\, (\psi_\text{cell} - \psi_\text{out}) \ge 0 \ \text{pJ/s}$$

- **The terms:**
  - $\Pi$ is the ideal (van 't Hoff) osmotic pressure of the declared amounts and the neutral
    impermeants;
  - $P$ is a linear elastic pressure, with stiffness $K$ about the reference volume;
  - $A$ is the patch's area and $L_p$ its hydraulic permeability;
  - $a$ is the patch's scheduled water availability, from 0 to 1.
- **A held bath** keeps its volume and composition, so its water potential
  $\psi_b = P_b - RT\sum_s c_{b,s}$ is fixed. The water it exchanges is booked as supply, with the
  work $10^{-3}\,\psi_b\,dS$.
- **In the step:** $\Phi_{dt} = W_{dt/2} \circ I_{dt} \circ W_{dt/2}$. $I$ is the inner model's
  own step at frozen volumes, and $W$ advances the volumes at frozen amounts by Heun's method.
  Under RK4, the water rates join the coupled right-hand side instead.
- **Refused, never repaired:** a volume at its bound; $dt$ times the water relaxation rate above
  0.05; an availability outside [0, 1].
- **Assumptions:** an ideal dilute solution; membrane areas and capacitances held fixed; water
  carries no solute and no charge; each declared species counts once; fixed-charge equivalents
  carry no particles.

## Sources

<!-- generated: provenance -->

Provenance: not yet extracted; operators have no provenance field yet.

<!-- /generated -->

| Work | What was taken | Mark |
| --- | --- | --- |
| The ideal (van 't Hoff) osmotic pressure, and a linear compliance | The forms of $\Pi$ and $P$ | Standard forms, named in [the water guide](../../../PUMP_WATER_MODEL.md); no work is cited |
| Manning and Kay 2023, J Gen Physiol 155:e202313332, Eq. 6 | $L_p = P_f V_w / (RT)$, to set $L_p$ from an osmotic permeability $P_f$ | Relayed from the water guide; unread here |

The parameter values ($P_f$, $K$, $P_0$, the volume bounds and the impermeants) belong to each
definition, not to this operator. The water guide's "Parameters" table gives their sources, with
its own marks.

## How it is checked

<!-- generated: tests -->

Declared tests: not yet extracted; operators have no test field yet.

<!-- /generated -->

The water kernel is compared with an independent reference written for its thermodynamics and its
graphs: the stage values, conservation over an owned graph, sealed edges and the pressure gauge,
the relaxation bound, and the refusal of invalid volumes.

Recorded evidence, with its scope: on 11 November the water law was qualified as the model
`resolved_pump_water@1`. Its judged run passed 25 of 25 criteria against predictions frozen from an
independent reference ([Progress](../../../../PROGRESS.md), "Osmotic water and volume qualified and
landed"). This operator is that law, moved unchanged. But the record names the model, not this
operator in today's compositions, so no status is copied from it.

## Status

<!-- generated: status -->

Not stated: no record states a level for this piece.

<!-- /generated -->

## Links

<!-- generated: links -->

- Declared in [`src/cells/operators/osmotic_water.py`](../../../../src/cells/operators/osmotic_water.py), class `OsmoticWater` (`cells.operators.osmotic_water`).
- Runs in [`cells.resolved_pump_composite@1`](../models/resolved_pump_composite@1.md).
- Manifest entry: (operator, `cells.ideal_osmosis_linear_compliance_water@1`) ([the format](../../DECLARATIONS_FORMAT.md)).
- In the Laws library: `select=laws:cells.ideal_osmosis_linear_compliance_water@1`.

<!-- /generated -->

Further reading: [the water guide](../../../PUMP_WATER_MODEL.md);
[the water reference](../../../WATER_VOLUME_REFERENCE.md); [the composite](../../../PUMP_COMPOSITE.md).
````

**What writing it showed:**
- **Gaps 1, 6, 7 and 8 of §8.**
- **Units.** Under @2, the suffix rule fills in every unit shown here as "Not stated".
- **Status.** The only record that states a level names the model `resolved_pump_water@1`, so the
  page copies none (§10, question 4).
- **The plain sentence.** It names the mechanism, osmosis against an elastic back-pressure, which
  serves all four fields; "Seen from each field" carries each field's own words.

## Sources read

- **Decisions:** `docs/DECISIONS.md`, D180, D185–D187 and D195–D201.
- **Design notes:**
  - `docs/MODULE_SYSTEM_DESIGN.md`;
  - `docs/CORE_SEAMS_DESIGN.md`, §0, §8 and §15;
  - `docs/FEATURE_REQUESTS.md`, FR-11 and FR-12;
  - `docs/INNER_MODEL_V4_DESIGN.md` §7.1;
  - `docs/RUN_VIEW_DESIGN.md`, its headings only.
- **The viewer:** `visualizer/docs/LAWS_LIBRARY.md`; on the `visualizer` branch at 2a7de02a,
  `visualizer/schema/LAWS_LIBRARY.md`, `visualizer/src/lenses/laws_card.js`,
  `visualizer/src/scene/model.js` and `visualizer/artifacts.json`, the last for its record of
  addresses only.
- **The pilots' documents:**
  - `docs/VOLTAGE_GATED_CHANNEL_SPEC.md` (SPEC-006);
  - `docs/PUMP_WATER_MODEL.md`, "Physics" and "Parameters";
  - `PROGRESS.md`, "Osmotic water and volume qualified and landed".
- **Code, read only:**
  - `src/cells/registry/laws.py`, `operators.py` and `declarations.py`;
  - `src/cells/modules/__init__.py`;
  - `src/cells/models/inner_laws.py`;
  - `src/cells/models/inner_kinds/` (`__init__.py`, the headers of `proton_buffer.py` and
    `transporter.py`);
  - `src/cells/models/operators/` (`__init__.py`, the header of `contract.py`, the header of
    `osmotic_water.py`);
  - `src/cells/registry/kind_registry.py` (the `Kind` fields);
  - `src/cells/laws/channels/voltage_gates.py` and `atp_transporter.py`;
  - `src/cells/numerics/osmotic_water.py` (its header);
  - `src/cells/models/surface_pump_v3.py` (`channel_rates`);
  - `src/cells/records/io.py` (`source_hashes`, `load_snapshot`);
  - `src/cells/records/run_view.py` (the suffix rule's names).
- **Tests:** the test names and docstrings of `tests/unit/test_declarations.py`,
  `test_law_registry.py`, `test_voltage_gated_membrane.py`, `test_transporter_kind.py` and
  `test_osmotic_water.py`; `tests/test_tiers.json` and `tests/tier3_record.json` for the Kv1.5 file.
- **The example manifest:** `/mnt/workspaces/Cells/declarations-example/declarations-75e925ea.json`.
- **No outside work was read.** Every outside citation above is marked relayed or unread.
