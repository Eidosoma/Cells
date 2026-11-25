# The ID hierarchy: the rename's design

25 November 2026. Settled by D371 (the user's decisions and the lead's rulings on this note's questions), with the
legacy plan's input (`legacy-port-plan` ef344334, §11.1). Three items are still open, listed in §11. A design note
only: it writes no engine code and changes no live file.

**What is decided** (D345, D346, D348, D371):
- every live ID becomes `cells.<family>.<name>@major`, from a closed list of families; names and majors are kept;
- interface IDs and schema IDs keep their names;
- no aliases: an old ID is refused at parse, and the refusal names its new one;
- one scripted move, pure, with the long-line rewrap as a separate commit and no folder moves in it;
- legacy's own IDs stay bare and frozen. The live pieces that legacy also spells are re-spelled in legacy's files
  (Q3), after the digest check of §1.5;
- never rewritten: tagged specs, references and judges, the crossrev replication record, `lean/` and past decision
  entries;
- no compatibility beyond this repository. The user renames their private IDs.

**The candidate table** comes from a read-only probe at main `0767867f`, not from the generator. It ran on CPU 4 under
the timed lock (70 s, then 20 s for the digests), with git, jq and shell for the rest:
- `/mnt/workspaces/Cells/rename-design-20261124/candidate-0767867f/`: `table.tsv` and `mapping.json` (the rows),
  `SUMMARY.txt` (every class and every ID), `FROZEN2.tsv` and `PINS2.tsv` (the frozen set), `move_files.tsv`,
  `digest_pins.json` and `three/`. Its `README.txt` says what supersedes what;
- the probe scripts are in `probe/` beside it. `candidate-ce4780d2/` and `candidate-f8c6c326/` are earlier runs.

**Two errors in this note's first version, now corrected** (§1.5, §6):
- it said no other pin sat on a file the move changes. The check had hashed `src/` only;
- its frozen rule skipped registration tags that point at merge commits. With that rule the move would have rewritten
  29 registered spec-like files, OL6's Protocols D and G and FR-38's rule among them.

## 0. Summary

- **The table:** 127 settled rows, 14 pending, 282 old spellings, no collisions.
  - 106 rows are registry pieces: 55 laws, 5 kinds, 27 composite operators, 8 family operators and 11 models.
  - 15 are settled seeds: 9 solvers, 4 execution choices and 2 heat choices. The block law's row is a registry row
    once the hand refactors (H1) register it, so no seeded law row remains (the candidate still lists it as a seed).
  - 5 are live models outside the model table.
  - 14 are pending: the ten sub-laws and the field closure law (in scope, words for the user), and three
    `resolved_tissue` models whose dispatch sits in legacy's hub (the lead rules, §1.4).
- **Families:** D346's list plus D371's words: `binding`, `population`, `assembly_geometry`, `assembly_hazard`,
  `assembly_representation` and `channel_block`. All operators share `operator`. The interface decides, never the
  folder.
- **The grammar:** one module holds it. A piece ID has three parts in every namespace, outside modules included.
  Refusal is by table lookup. `qualified()` stays as the one normaliser, now a checker.
- **Frozen files:** 352 files under four rules, 160 of which hold old spellings. A judged run is pinned to its
  pre-rename snapshot; a live driver that feeds a frozen file to the renamed engine translates it in `validation/`.
- **The move:** 927 files and about 6,400 changed lines, plus three `src` modules a hash pins (§5).
- **The gate:** one stack, the full gate, with G1 and crossrev through the table. Tier 3 runs the night after, and the
  scope map is refreshed right after the landing.
- **Test cost:** 14 rows in existing files, under 5 s.

## 1. What the probe found

### 1.1 The registries

| Source | Pieces | Spelled today as |
| --- | --- | --- |
| Laws | 55 over 14 interfaces: channel 11, cycle 15, route 8, reaction 4, rate_factor 3 + 2, free_energy_term 3, junction 2, assembly_geometry 2, binding 1, exchange 1, assembly_hazard 1, population_structure 1, assembly_representation 1 | Bare (`kv1p5_mh@1`). 13 cycle and transporter laws also carry `DECLARED_ID = f"cells.{LAW_ID}"`; the assembly family's laws are qualified |
| Kinds | 5 | Qualified (`cells.transporter@1`) |
| Composite operators (`cells.operator@1`) | 27 | Bare (`site_occupancy@1`) |
| Family operators (`cells.lineage_operator@1`, `cells.assembly_operator@1`) | 8 | Qualified (`cells.shear_fission@1`) |
| Models (`model_table.MODELS`) | 11 | Bare, except the two assembly families |

The lead's dump missed the 8 family operators: it read the composite's section only. D185's rule joins the two
spellings today (`kind_registry.qualified()`), and the manifest carries both, as `id` and `declared_id`.

### 1.2 Live IDs that no registry holds

| Class | IDs | Examples | Disposition |
| --- | --- | --- | --- |
| Declared choices | 15 | `imex_ars222_face_electromigration@1`, `capacitive_reduction_gauged_damped_newton@2`, `trapezoid_nonnegative@1`, `fixed_fine_windows@1` | Seed rows from their module constants (§5) |
| The block law | 1 | `open_channel_block_weighted_modes@1` | Registered in H1 (§4) |
| Live models outside the model table | 5 | `source_decay@1`, `emt_mirna@1`, `passive_pair@1`, `capsid_graph@1`, `finite_bond_assembly@1` | Seed rows. The first three go in the deletion batch after the rename (D374); re-spelling them first costs a few rows |
| **Sub-laws with no Law record** | 10 | §11's table | In scope (D371 Q4). Words: §11 |
| **The field closure law** | 1 | `resolved_capacitor_components_current_continuity@1`, the `closure.law` of every @3 world (185 spellings in 145 files) | In scope. Word: §11 |
| Recorded labels | 35 | `*_half_steps@1`, `ssprk33_*`, stage domains, observers, the analyses, the assembly RNG | Not in scope (D371 Q4). Kept bare |
| **Live models dispatched by legacy's hub** | 3 | `resolved_tissue@1`, `@2`, `@8` | §1.4 |
| Laws in live modules that only legacy and the calcium ensemble read | about 52 | the channel and calcium catalogues, `hcn1_m@1` to `hcn4_m@1` (built by an f-string), the tissue field's laws | Frozen with legacy (D348) |
| The calcium ensemble's model | 1 | `ionic_worlds@1` | Frozen with legacy until the ensemble's port |
| Legacy's own | 126 models, about 350 other IDs | `resolved_calcium@11`, `spatial_calcium@4` | Frozen (D348) |
| Interface and schema IDs | 18 interfaces, about 1,100 record and file kinds | `cells.channel_law@1`, `cells.declarations@2` | Unchanged (D346) |
| Test plants | about 260 | `tests.planted_route@1`, `seamtest.net_exchange@1`, `test_closer@1` | Three-part shape (D371 Q8): §3 |
| Validation's own | about 120 | BETSE emulator IDs, policy and revision labels, data set IDs | Unchanged: no engine piece |
| Prose shorthand | 8 | `replacement@1`, `water@1`, `insertion@2` | The docstring batch, not the script |

### 1.3 Live pieces that legacy also spells

Legacy's definitions and code use 22 live pieces by their old names: the 18 D371 ruled on, the field closure law, and
the three models of §1.4. They make 2,292 occurrences in 98 legacy definitions (JSON), and sit in 76 code files: 12 in
`src/cells/legacy`, 6 in live `src` that imports it, 22 tests and 36 validation files.

| Piece | In legacy's definitions | In other live files |
| --- | --- | --- |
| `constant_field@1` | 454 | 580 |
| `logmean_electrodiffusion@1` | 362 | 135 |
| `nak_atp_mass_action_positive@1` | 313 | 203 |
| `kir2p1_mh2@1`, `kv1p5_mh@1` | 171, 164 | 154, 54 |
| `nav1p2_m3h_regularized@1`, `junction_voltage_relaxation@1` | 115, 100 | 166, 199 |
| `capacitive_reduction_gauged_damped_newton@1`, the field closure law | 82 each | 37, 99 |
| `finite_bond_assembly@1` (nested in `assembly_regulated_cluster@1`'s definitions) | 63 | 7 |
| the five other Kv1 laws; the K, Na and Cl leaks | 50 each; 42 each | 14 each; 93, 63, 27 |
| `ideal_osmosis_linear_compliance_water@1` | six legacy models import its constant | 58 |

**How legacy reads them:** with its own literals (`legacy/core/spatial_extracellular_spec.py:26–27`,
`legacy/assembly_cluster/mobile_channels.py:93`), through live parsers that live models share
(`surface_tissue_spec.py:23, 143, 159–161, 224–228`; `surface_pump_spec.py:31, 189`;
`surface_kinetic_spec.py:449–513`), and through live constants. So live code alone cannot be renamed. D371's Q3 (a)
re-spells legacy's files too.

### 1.4 Three live models whose dispatch sits in legacy's hub

`resolved_tissue@1`, `@2` and `@8` are live models: their spec classes, parsers and model modules are live
(`surface_tissue_spec.py:22`, `surface_kinetic_spec.py:36` and `:42`; `models/surface_tissue.py`,
`models/surface_kinetic.py`, and for `@8` legacy's wrapper `legacy/models/surface_catalog.py`). Only their dispatch is
in legacy, at `legacy/registration.py:1196–1211` and `1444–1447` (parse), `794–833` (models) and `1946–1980`
(dicts). The first version of the table listed them with legacy's frozen models.

| At main 0767867f | `@1` | `@2` | `@8` |
| --- | --- | --- | --- |
| live `src` (6 files) | 3 | 6 | 2 |
| the hub (one file, three literals) | 1 | 1 | 1 |
| legacy's other `src` (6 files) | 8 | — | — |
| tests that import legacy (15 files) | 4 | 7 | 10 |
| tests that do not (4 files) | — | 3 | 1 |
| configs (10 files) | 2 | 3 | 5 |
| examples (6 files) | 13 | — | — |
| validation (56 files) | 45 | 32 | 22 |
| **in scope, total** | **76** | **52** | **41** |

That is 169 occurrences in 104 files. 14 of them are in 12 frozen files, so 155 would be re-spelled, in 92 files, 50 of
which hold nothing else the move changes. `ensemble/ionic.py:177, 196, 202` admits them. The 19 test files that spell
them are 7 in tier 1, 1 in tier 2 and 11 in tier 3. The live-subject ones (row A12's six, and `@8`'s catalogue and
equivalence files) are all in tier 3; the eight in tiers 1 and 2 reach them through legacy's dispatch.

| | Mint now, as the 18 are re-spelled | Leave bare until the legacy batch (C-1) |
| --- | --- | --- |
| Rows | 3, `cells.model.resolved_tissue@1`, `@2` and `@8` | none: they stay on the kept list |
| Now | 92 files, the hub's 3 literals among them, and the generator's frozen set needs an exception with a planted case | nothing changes |
| Then | nothing | at C-1, when their dispatch moves to the live registry, a second small scripted move: 3 rows, and the files that still exist |
| Coverage | the eight test files of tiers 1 and 2 parse the re-spelled dispatch in the gate; the live-subject tests run in tier 3 the night after | none needed |
| D346 | every live ID is hierarchical | three live IDs stay bare until C-1 |
| Manifest | `legacy_entries()` lists them under their new IDs, still as legacy's | unchanged |

**Recommended: leave them bare, and mint them at C-1.** It is the safer choice for the morning's script: the hub and the
generator's rule for what is frozen do not change, and C-1, where the dispatch moves anyway, has its own full gate and
tier 3. Minting now also works, and the gate would exercise it. Its price is the 92 files, the hub's literals and an
exception in the one rule that decides what is rewritten; its gain is one move and one table. The lead rules.

### 1.5 Hazards for a token rewriter

- **Computed IDs** (D188's R2 class), refactored by hand first: `KV1_LAWS` in `kv1_channels.py`, the 13 `DECLARED_ID`
  f-strings, about 20 test sites and 2 in `betse_reference_extract.py`. `hcn_channels.py`'s f-string builds frozen IDs.
  About 50 of the 86 hits are `role@end` and similar labels.
- **Path segments:** 56 tokens sit inside paths. The page rule (§3) moves the pages; the token rule skips a token after
  `/`.
- **Line length:** 1,156 lines become longer than 100 characters, in 447 Python files. They are wrapped in a
  separate commit after the move (D371), checked at the AST level; docstring lines stay. No gate runs ruff.
- **Hash pins.** 33 files that the move would change have their SHA-256 quoted by another file in `src`, `tests`,
  `validation`, `scripts`, `examples` or `configs` (`PINS2.tsv`). 30 are excluded by rule (§6). Three are `src`
  modules:
  `assembly/__init__.py`, `assembly_pool/__init__.py` and `ensemble/worker.py`, pinned by
  `validation/topology/joint_water_profile_phase_handoff_protocol.json`. They carry live IDs, so they are re-spelled.
  D187 holds: no hash is ever updated, and the tiers show whether a live reader checks those pins.
- **The legacy digest check** (D371 Q3): 8 example artifacts hold 19 digests of their own nested definitions
  (`digest_pins.json`, the raw canonical digest of each object). Re-spelling them leaves the digests stale. The 83
  definitions that parse had no fingerprint pinned anywhere. §11 has the choice.
- **Three schema kinds already have three parts** (`cells.assembly_lineages.probe@1`,
  `cells.assembly_lineages.f12_table@1`, `cells.source_moves.report@1`). No piece slot reads them.
- **Sorts** (CHECKS.md item 1): every sort that sets an array's order is over qualified keys of one family, or over
  codes, and a uniform prefix keeps it. Two sorts over declared spellings exist and set no number:
  `surface_pump_v3.py:1194` (the routing door's sources, whose factors fold in declared order) and
  `pump_composite.py:2505` (column names).

## 2. The families

The user's rule (D371): short where unambiguous, prefixed where a collision could come. The interface's own noun,
without `_law` or `_term`, gives the word; the host family's prefix stays where the bare word would be vague. `block`
was not used, since it already names a definition section. The word for an interface added later is declared in the
same table, so the list stays closed and in one place.

| Family | Holds | Rows |
| --- | --- | --- |
| `model` | the model table's 11 and the 5 outside it (the three of §1.4 pending) | 16 |
| `operator` | the composite's (`cells.operator@1`) and the families' own (`cells.lineage_operator@1`, `cells.assembly_operator@1`) | 35 |
| `kind` | the inner model's kinds (`cells.kind@1`) | 5 |
| `solver`, `heat`, `execution` | what `execution.solver` and `field_solver` choose; the heat choice; `fine_windows`, `projective`, `energy_check`, the vector windows' mapping | 9, 2, 4 |
| `channel`, `cycle`, `route`, `junction`, `reaction`, `exchange` | `cells.<word>_law@1` | 11, 15, 8, 2, 4, 1 |
| `rate_factor`, `free_energy` | `cells.rate_factor_law@1` and `@2`; `cells.free_energy_term@1` | 5, 3 |
| `binding`, `population` | `cells.binding_law@1`; `cells.population_structure@1` | 1, 1 |
| `assembly_geometry`, `assembly_hazard`, `assembly_representation` | the assembly interfaces of the same names | 2, 1, 1 |
| `channel_block` | `cells.channel_block_law@1` (H1) | 1 |
| words for the 11 sub-laws | §11 | 11 |

**Operators share one family.** The registry already holds one namespaced ID per operator across its two sections, and
every operator's `interface` still names its contract.

**The interface decides, never the folder.** One table in the grammar module, `LAW_FAMILIES = {interface: word}`, is the
only home of the words. Registration checks a law's family against its type's interface: `cells.cycle.kv1p5_mh@1`
declared as a ChannelLaw is refused. So `rapid_binding@1`, which sits in `laws/reactions/`, becomes
`cells.binding.rapid_binding@1`. Folder moves come later, in a separate move (D371 Q5), not in this one.

**The word "family".** The prose keeps D345's word. The manifest's `family` key keeps its meaning, the model whose
registries hold the piece, which the viewer shows. The manifest gains no key for the ID's family: `id` carries it.

## 3. The grammar and its parse sites

**The grammar** (`src/cells/registry/ids.py`, new, imported by the registries and the parsers):
- a piece is `namespace.family.name@major`, each part `[a-z][a-z0-9_]*`, the major `[1-9][0-9]*`;
- an interface or a schema ID keeps `namespace.name@major`. The two never share a slot;
- the family is from the closed list in the `cells` namespace;
- D185's bare rule ends for live pieces: one spelling, so a definition, a manifest's `id` and `declared_id`, and a
  record all write the full ID;
- the kept list keeps today's rule (`qualified()` still prefixes `cells.`): legacy's frozen IDs, the 35 recorded labels
  and, if they are left bare, the three models of §1.4. Each ID leaves it when legacy goes or when it is minted;
- **refusal is by table lookup.** An old spelling in the committed table is refused, naming its new ID. Any other bare
  or two-part value in a piece slot that is not on the kept list is refused for its shape;
- **plain words stay schema words.** `"solver": "rk4"` and `"mapping": "lax_map"` have no major and are not IDs. A slot
  that takes a word or an ID checks its words first.

**Outside modules** (D371 Q8; there are none in the tree, D195):
- a piece has the same three parts in every namespace, and `cells` is reserved. The family words `kind`, `operator` and
  `model` hold in every namespace; a law of a `cells` interface takes that interface's word
  (`acme.channel.my_kv@1`); an outside interface declares its own word beside itself, and its laws use it;
- a two-part piece ID from an outside namespace is refused for its shape. The engine cannot name its new ID: the
  table covers this repository only (D346);
- test plants take the shape. The script places a plant by its declaring type, and the dry run lists the rest by hand.

**The refusal's wording** (one function, every site):

    model.id: resolved_pump_tissue@3 was renamed cells.model.resolved_pump_tissue@3 (D345)
    Law cells.cycle.kv1p5_mh@1: a cells.channel_law@1 law's ID is cells.channel.<name>@major
    populations[0].law: kv9_mh@1 is not namespace.family.name@major (D345)

The first line is the old-ID refusal: the slot, the old spelling, the new ID and D345. The table stays as data, so a
past decision entry or a Lean claim is read through it. The refusal costs one dictionary lookup.

**Every parse, split, qualify and compare site, and how each changes:**

| Site | After |
| --- | --- |
| `registry/laws.py` `_ID`, `_is_id(value, namespaced)` (132–139) | `ids.piece()` for laws and hosts; `ids.interface()` for the `namespaced=True` case |
| `registry/laws.py` `Law.errors()` (196–200) | adds the family check against `LAW_FAMILIES[interface]` |
| `registry/laws.py` 211, 626; `registry/operators.py` 102, 143, 165 (the first part is the namespace) | unchanged |
| `registry/operators.py` `FamilyOperator.errors()` | `ids.piece(…, family="operator")` |
| `registry/kind_registry.py` `qualified()` (98–103) | returns a full piece ID unchanged; refuses an old spelling by the table; prefixes the kept list only. Its ~100 call sites in 17 files do not change |
| `registry/kind_registry.py` `_BOOKING_ID` (594, heat bookings) | `ids.piece()`: keys `kind`, values `heat` |
| `registry/declarations.py` `page_path()` (251), `scripts/library_pages.py` `page_identity()` (653) | **no change**: below |
| `registry/declarations.py` `_Context.identity()` (301–302) | `ids.parts()`: `name` stays the last part, with no new key, so `@2`'s keys and the meaning of each hold (D371 Q6). Its ID rule's text is amended |
| `registry/declarations.py` `_Context.spellings`, `legacy_entries()` | an identity map while legacy lasts; unchanged |
| `records/relations.py` `PIECE`, `SEGMENT` (151–154) | unchanged (any number of dots) |
| `definitions/specs.py` `parse_spec()` (993 on) | the literal `==` chain is rewritten by the script. Before the legacy fall-through, an old live model ID is refused by the table. For a live model, one pass over the definition refuses every old spelling (`ids.refuse_old(data)`), so no family parser needs its own check |
| Exact-key lookups on declared spellings (`channel_laws()`, `TODAYS_CHANNEL_LAWS`, `OPERATORS`, `MODELS`, compositions, `REQUIRES`, `inner_laws`' tables) | the same lookups on the one spelling, through constants and literals the script rewrites |
| `ensemble/plan.py` 23, 92; `ensemble/families.py` `TODAY` and the `model_of` compares; `ensemble/cli.py` 141, 240, 512; `ensemble/ionic.py` | rewritten for `capsid_graph@1` and `finite_bond_assembly@1`. `ionic_worlds@1` and legacy's models stay |
| `cells.modules` (provisional, D195) | exports `qualified`; its docstring states the new contract |
| Outside src: `qualified()` in 12 files of `validation/`, `scripts/` and `tests/` | unchanged |
| Outside src: `tests/unit/test_cell_owned_compartments.py:1029` (`model_key` from `kind_id.split(".")[1]`) and the `"cells." +` test sites | H2. No ID regex exists outside src |

**The library pages** (D371 Q6), checked: the six pages are at `docs/library/cells/<section>/<name>@<major>.md`
(one kind, one law, four operators). `page_path()` takes what follows the namespace, so for
`cells.channel.kv1p5_mh@1` it gives `docs/library/cells/laws/channel.kv1p5_mh@1.md`, and `page_identity()` still
reads three parts and returns the same ID. No code changes: the six files are renamed by the script, and
`test_library_pages.py`'s four path strings, the text of `LAW_DOCUMENTATION_DESIGN.md` §1.2, `TEMPLATE.md` and the
format page (`<name>` becomes `<family>.<name>`) and the regenerated index follow. The viewer's tests quote one page
path (`visualizer/tests/laws_library.test.mjs`); the lead tells the viewer session.

## 4. The block law

**Decided (D371 Q2):** its own family, `channel_block`, and the interface `cells.channel_block_law@1`, whose name
follows the word. The law and the interface are registered in the hand refactors (H1), so the table holds no seeded
law row. H1 gives `open_channel_block.py` its Law record on a `ChannelBlockLaw` type, adds the module to @3's
`law_homes` in the model table and the interface to its row. The generator then maps
`open_channel_block_weighted_modes@1` to `cells.channel_block.open_channel_block_weighted_modes@1` as it maps every other
law. `fr51-slot-refusal` landed at f66fa681 without registering it.
- FR-51's tagged `cases.json` names no block ID (`engine.py` adds the constant), so registering it touches no tagged
  file.
- H1's record gives it a citation (Woodhull 1973), its D187 test and a library page (a seventh page).

## 5. The generator and the script

**One tool, `scripts/id_moves.py`, shaped and reused from D188's `source_moves.py`:** `table`, `scan` (hazards), `apply`
(the token rewriter), `verify --base --head` (replay equality, no hash edits, a second application changes nothing, no
old spelling left in scope), `ids` (collected test IDs through the table) and `selftest` (planted cases, kept out of
`tests/`).

**The generator** (`table`) refuses to write a table while any live ID is unplaced. Its four sources:
1. **The registries,** loaded as the manifest loads them. The family is the interface's word, or the piece's.
2. **Seeds:** non-registry module constants, each listed by module and name with its family. A seed whose constant is
   gone is refused.
3. **Legacy's frozen set:** `legacy_entries()`, every `MODEL_ID` that a module under `cells.legacy` defines, and every
   ID that only legacy's places use. Excluded by ID, not by path. If the three models of §1.4 are minted, they leave
   the set, with a planted case (a legacy-dispatched ID whose code is live).
4. **The reconciliation:** `git grep` of every `name@major` token in scope, each placed in a class of §1.2.

Each row holds every old spelling, the new ID, the family, the piece, the interface, the host and the declaring module.
The collision report checks: two old keys to one new ID (none), one spelling naming two pieces (none), an old key equal
to a legacy ID or an interface (none), and the old keys that a schema-named key carries (the five kinds, whose `kind`
key names a kind piece, not a format).

**The rewriter** maps whole tokens, longest match. It skips a token after `/` (the page rule's), a line marked
`id-moves: keep`, and every excluded file (§6). It does no formatting: the long-line rewrap is its own commit.

**Its scope:** tracked Python, JSON, shell and TOML files under `src/` (legacy included, D371 Q3), `tests/`,
`validation/`, `scripts/`, `examples/` and `configs/`, less the exclusions. Today that is 927 files and about 6,350
lines: 171 in live `src`, 12 in legacy, 281 in tests, 331 in validation, 117 in configs, 9 in examples and 6 in scripts
(`move_files.tsv`), plus the three hash-pinned `src` modules.

## 6. Exclusions, and how frozen files keep being read

**Never rewritten:**
- **Frozen files, by four rules,** recomputed at the morning's tagged base (`frozen_rule_v2.sh`, git and shell only).
  The tag and merge rules take only files whose blob on main is still the tag's. The dry run prints the list for each
  owner to confirm:
  - **tag** (195 files): the non-merge commits a registration-style tag owns. The tags are named registered,
    registration, judge, references, erratum, amendment, criteria, rule, sheet, predictions, declaration, supplement
    or protocol. For a tag on a side branch, the merge that brought it in is found by searching main's first-parent
    line;
  - **merge** (158): such a tag at a merge commit on main's first-parent line, which the first version skipped. Its
    branch's own non-merge commits, restricted to spec-like paths: `references/`, `spec/`, `designs/`, and
    REGISTRATION, CRITERIA, AMENDMENT, ERRATUM, judge, rule, protocol, predictions, RUNG and sheet names. 35 of the
    files the old rules missed hold old spellings, 29 of them spec-like;
  - **commit** (48): the last change is a commit whose subject begins "Freeze" or "Register". This covers the protocols
    and predictions that predate tags;
  - **pin** (33): another file quotes the SHA-256 (§1.5). The three `src` modules are re-spelled, so 30 are excluded.
- **Together: 352 files, 160 of which hold old spellings** (98 JSON, 44 Python, 18 Markdown; `FROZEN2.tsv`). FR-50's
  registration files joined when FR-50 landed.
- **`lean/`:** 173 files hold 2,498 old spellings.
- **The crossrev replication record** and every record under `/mnt/workspaces`, which are outside the tree.
- **Past decision entries,** `docs/` in general, `reports/`, `agent-work/`, `visualizer/` and D188's maps.
- **Legacy's own IDs,** wherever they appear (§5, source 3).

**How they keep being read** (D371 Q7):

| Option | What | Where |
| --- | --- | --- |
| pin | a judged run uses its pre-rename snapshot | every judged run registered before the rename (D350) |
| translate | `validation/id_table.py` maps old spellings to new through the committed table, recursively over JSON-like data, refusing an ambiguous one. A live driver applies it to a frozen input before parse. The engine stays strict | G1's saved definitions, crossrev's predictions, regression tests, FR-51's `cases.json`, and every live reader the dry run finds |
| erratum | a tagged erratum names the new spellings | only where a judge's own code must change |

**Registrations with a run still to come** (D371 Q7):

| Registration | Old spellings in its frozen text | Marked |
| --- | --- | --- |
| FR-38 v2, the second comparison | prose in its spec (6); the judge, untagged, is on `fr38-v2-judge` (15) | **pinned.** Its judged run comes before its branch merges main after the rename (D371) |
| FR-45 (W1 to W7s) | prose in its spec (4); no references JSON | **translated** only if a driver feeds old text to the engine; its engine code is not on main, so it is built after the rename from constants. W2 and W7 stay on the wash, or on a pre-rename snapshot (D364). Its judge is written after the rename (D376) |
| FR-49 (World B, C1, C2, C4) | `judge_l.py` (1) and `worlds.py` (4), frozen code that calls the engine; `REGISTRATION.md` (16) | **translated** at B's and C's live judges, which wrap the frozen builders' definitions before parse. World L is judged (D331). Until those judges exist, B and C1 stay pinned to their snapshot (D362) |
| FR-30's Ek-Vitorín 2016 fit | none frozen: prose in `docs/JUNCTION_TWO_RELAXATION_DESIGN.md`; `harness.py` and `score.py` on `fr30-next` hold one each | neither: the branch re-spells its live files when it merges main. The fit waits for its amendment (D366) |
| GJ-N1's field point | `neither_rule.json` and the judge (frozen) | **pinned**, in flight on its snapshot |
| FR-51's two-potassium run (D353) | not tagged yet | written after the move, or pinned to 955765ef (D361) |

## 7. What each consumer needs

| Consumer | Needs | Recommendation |
| --- | --- | --- |
| Frozen judges, references and protocols | to keep being read | §6: pin judged runs, and translate at the live driver |
| G1 (`results_baseline.py`) | the gate runs c1's saved definitions (`--from`), old IDs included | a `--map TABLE` option: the saved definitions are translated before the head parses them. Arrays are compared bitwise and refusals must match; records go through the table. c1 is saved again at the new head as a new record |
| Crossrev | its sets are built by live generators; the qualification set reads the frozen predictions | the head reads those definitions through the translator. Programs and arrays carry no ID |
| Lean's drivers (`lean/checks/*.py`) | the table, through the user, before the landing (D346) | the Lean lane runs `id_moves.py apply --paths lean/checks` on its branch after merging main, or re-spells by hand. Its claims are read through the table. Its waiting tips are held until it rewords and rebuilds (D376); they re-merge after the landing |
| The viewer session | the table, a manifest written at the landing revision, the amended ID rule and the page paths (§3) | told by the lead. Its own data (pieces, atlas, catalogue) re-keys; its reader needs no change, since `@2`'s keys hold |
| Private modules | the new three-part shape | the user is told that private IDs change shape; the engine cannot name the new ones |
| Checkpoints and snapshots | snapshots keep their names. A checkpoint resumes only on the snapshot that wrote it: continuity refuses a changed model ID (case 3) | nothing translates a checkpoint. A needed one is renewed by a fresh run. Runs in flight continue on their snapshots |
| Run manifests and records | `definition_sha256` and other derived digests change; arrays do not | compared through the table (`compare_renamed_runs.py`) |
| IDs born after the rename | FR-54/57's router `cells.operator.liquid_routing@1`; FR-64's shift, a declaration with no ID | minted in the new shape, with no mapping row |

## 8. The gate plan

**One stack, gated once with the full gate, since it changes src:**
1. **The no-src notes:** this note, FR-64's and FR-54/57's, with the notes D377 lists.
2. **The docstring batch** (D351, D355, D356) and D364's two follow-ups. They come before the move, so the script covers
   their IDs.
3. **H1 to H3, hand refactors,** each small and AST-checked:
   - H1: the grammar module, the refusal, the parse sites of §3, the manifest's identity, and the block law's
     registration (§4);
   - H2: the computed IDs of §1.5;
   - H3: `validation/id_table.py`, G1's `--map`, and one translator call at each live reader of a frozen file.
4. **M: the scripted move,** alone in its commit and pure: no folder move, no hash edit. It includes the 22 shared
   pieces in legacy's files. `verify --base H3 --head M` must hold: the replay is equal, a second application
   changes nothing, and no old spelling is left in scope.
5. **W: the long-line rewrap,** a separate commit, checked at the AST level.
6. **D: docs.** The page renames, the format page's ID rule, ARCHITECTURE's where-it-lives lines, PROGRESS and the
   decision entry.

**The checks:**
- **Pre-lock:** the IDs step through the table (`id_moves.py ids`), the guard set, and the changed test files within
  their rows.
- **Under the lane's lock:** crossrev (every set, bitwise); tiers 1 and 2 against the record; G1 through the table;
  FR's bitwise set and the fingerprints unit, both through the table.
- **After the lock:** `compare_renamed_runs.py` on the run-paths pair; the manifest regenerated and the library check;
  **the scope map refreshed right after the landing** (D371); tier 3 the night after, with the dry run's files.

About an hour locked (D346), plus G1. The six files that gain §10's rows are re-measured or folded and declared
(`ADDITIONS_FROM`). No other row changes.

## 9. The morning, and the branches in flight

**The order** (D346 as D348 and D371 amend it):
1. Land what is gated, then the queue. **FR-38's build runs its judged run before it merges main after the rename.**
2. Pin each judged run not finished to its pre-rename snapshot (§6's table; GJ-N1's field point is running).
3. Tag main, `pre-id-rename-<date>`, and freeze the pre-rename snapshot (D369).
4. Write the decision entry. The words (§11) and the three models (§1.4) are ruled on here.
5. Write `scripts/id_moves.py` and H1 to H3.
6. Generate the table at the tag with the collision report, the frozen list and an empty unplaced list. Dry-run on a
   scratch copy: `verify`, the IDs through the table, the over-long lines, and the changed files' tests. Each frozen
   file is confirmed by its owner.
7. Hand the table to the Lean lane and the viewer session, through the user.
8. Gate the stack, land it, and refresh the scope map.
9. Re-merge the branches.

**Expected time:** the script and the H commits take about one agent-day, reusing `source_moves.py`; the dry run and its
fixes take half a day; the gate takes one to two hours. FR-64's, FR-54/57's and the other queued builds wait for it.

**Branches in flight:** merge main; where a conflict is only in a file M changed, take the branch's side and run
`id_moves.py apply`, which rewrites the branch's own new references and leaves its tagged files alone; merge H1 to H3's
files by hand; run the leftover guard and the changed tests. The tips held for Lean (D376) are re-merged by Lean.

## 10. Test cost (D224)

Rows in existing files. None compiles a world:

| Row | File | Seconds |
| --- | --- | --- |
| a law whose family is not its interface's is refused (the block law's registration included) | `tests/unit/test_law_registry.py` | < 0.1 |
| an old spelling is refused, naming its new ID | `tests/unit/test_law_registry.py` | < 0.1 |
| every family interface of the model table has its word (planted: one without); the keys are full IDs | `tests/unit/test_model_table.py` | 2 × < 0.1 |
| an old model ID at parse | `tests/unit/test_specs.py` (`test_invalid_definitions`) | < 0.1 |
| an old ID at parse for a law, an operator, a kind, a solver, a heat choice and an execution choice | `tests/unit/test_surface_pump_v3_definitions.py` (`test_definition_errors_reject`) | 6 × < 0.1 |
| identity's three parts, and the page path | `tests/unit/test_declarations.py` | < 0.1 |
| the leftover guard: no old spelling in scope outside the exclusions | `tests/unit/test_model_table.py`, beside its tree checks | about 2 |
| a frozen input through `validation/id_table.py`, round trip | FR-51's host rows, `tests/unit/test_surface_pump_v3_populations.py` | < 0.1 |

14 rows, under 5 s. The script's own checks live in its `selftest`. No test is removed: tests change spelling only.

## 11. Decided, and still open

**Decided by D371:**

| Question | Ruling |
| --- | --- |
| Q1, the five words | `binding`, `population`, `assembly_geometry`, `assembly_hazard`, `assembly_representation` |
| Q2, the block law | its own family `channel_block`, with its law and interface registered in H1 |
| Q3, the shared pieces | re-spelled in legacy's files too, after the digest check of §1.5 |
| Q4, unregistered IDs | the ten sub-laws and the field closure law are in scope; the 35 labels are not |
| Q5, folders | a separate move after the rename: no folder moves in this one |
| Q6, the manifest | `@2`'s keys, with the ID rule amended |
| Q7, frozen files | pin or translate; an erratum only where a judge must change |
| Q8, test plants | the three-part shape, with the grammar for outside modules in §3 |

**Open:**
1. **The words for the ten sub-laws and the field closure law** (D371: a new word comes back to the user). Three have an
   existing word that fits; the other eight need seven new ones:

| ID | Named in | Proposed word |
| --- | --- | --- |
| `delayed_first_order_junction_formation@1` | `junction_formation.law` of the replacement operator | `junction_formation`, new |
| `ph_conditioned_factor@1` | `law` of a pH condition | `rate_factor`, existing |
| `bounding_patch_damage@1` | `law` of a patch damage | `damage`, new |
| `hill_regulated_two_state@1` | `states[].law` of regulated availability | `regulation`, new |
| `langmuir_site_binding@1` | the site operator's recorded `laws` | `site_binding`, new |
| `site_conserving_internalisation@1` | the site operator's recorded `laws` | `site_internalisation`, new |
| `exponential_volume_activation@1` | `volume_factor` of the symport | `rate_factor`, existing |
| `exponential_mean_rate_linear_target_gates@1` | its module constant and 15 protocol notes; nothing in `src` reads it | `solver`, existing |
| `maintained_held_rows@1`, `finite_fuel_rows@1` | `fuel.kind` of a transporter | `fuel_kind`, new (two rows) |
| `resolved_capacitor_components_current_continuity@1` | `closure.law` of every @3 world | `field_closure`, new |

   They carry no Law record, so each is a seed row whose family the user fixes now. The word must be the one its later
   interface would take, or the ID moves again. The recommendation is the words above: seven new ones and three reuses.
   A smaller set is possible by grouping (`site` for the two site laws, one `factor` word); a larger one by giving
   each its own.
2. **The three models of §1.4:** mint now, or leave bare until C-1. The lead rules.
3. **The legacy digest pins of §1.5:** leave the 8 example artifacts unspelled, with the readers checking the digest on
   the raw text before translating (recommended); regenerate them with their own tools after the move (new digests); or
   let them go with legacy's tests at C-1. The lead rules.

**For the user:** private modules' IDs change shape, from `namespace.name@major` to `namespace.family.name@major`, and
the engine refuses the old shape without naming a new ID.
