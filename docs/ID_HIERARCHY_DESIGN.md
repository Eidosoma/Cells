# The ID hierarchy: the rename's design

25 November 2026. Settled by D371 (the user's decisions and the lead's rulings on this note's questions), with the
legacy plan's input (`legacy-port-plan` ef344334, §11.1). Extended the same day, after FR-58's designer found a live law
with no row in the table (§1.6). The open items are in §11. A design note only: it writes no engine code and changes no
live file.

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

**The candidate table** comes from a read-only probe at main `76a498ae`, not from the generator. No file of `src`,
`configs` or `examples` differs from the last one's revision (`0767867f`), and main's next commit is docs only. The
Python ran on CPU 7 at nice 10, one thread, apart from a few one-line checks; git, jq and shell did the rest, unpinned:
- `/mnt/workspaces/Cells/rename-design-20261124/candidate-76a498ae/`: `table.tsv` and `mapping.json` (the rows),
  `reasons.tsv` (every other quoted ID: where it is spelled, which registry holds it, and why it has no row),
  `by_hand.tsv` (§1.5), `open_points.json` (§11, as data for the tool), `FROZEN2.tsv`, `PINS2.tsv` and
  `frozen_readers.json` (§6), `move_files.tsv`, `move_sizes.json`, `digest_pins.json` and `SUMMARY.txt`. Its
  `README.txt` says how each was made;
- the probe scripts are in `probe/` beside it. The three earlier runs are kept, superseded.

**Errors in this note's earlier versions, now corrected:**
- **its table missed 52 live IDs** that the registries do not hold, `ideal_detailed_balance_mass_action@1` among them
  (§1.6);
- it said no other pin sat on a file the move changes (§1.5). The check had hashed `src/` only;
- its frozen rule skipped registration tags that point at merge commits (§6). With that rule the move would have
  rewritten 29 registered spec-like files, OL6's Protocols D and G and FR-38's rule among them;
- it said that three schema kinds have three parts. 138 names do (§1.5);
- its list of IDs built at run time missed legacy's files and a computed major, and named two sites that build no ID
  (§1.5);
- it said that no ID pattern exists outside `src`, and that the viewer's reader needs no change. Neither holds (§3, §7);
- its docs commit left out the composition matrix's generated block (§8);
- it counted 12 files outside `src` that call the registry's `qualified()`, and five do (§3). It named a test that reads
  another file as a reader of the 8 artifacts, four of which have no reader in code (§11).

## 0. Summary

- **The table:** 193 rows and 386 old spellings, with no collisions: 127 settled, 17 that wait for the user's words and
  49 that wait for the lead (§11).
  - 106 rows are registry pieces: 55 laws, 5 kinds, 27 composite operators, 8 family operators and 11 models.
  - 15 are settled seeds: 9 solvers, 4 execution choices and 2 heat choices. The block law's row is a registry row
    once the hand refactors (H1) register it, so no seeded law row remains (the candidate still lists it as a seed).
  - 5 are live models outside the model table.
  - 17 wait for words: 12 sub-laws, the field closure law, a topology, two potential sets and an analysis.
  - 49 wait for the lead: three `resolved_tissue` models (§1.4), 45 catalogue laws and the ensemble's model (§1.6).
- **Completeness (§1.6):** 2,062 quoted IDs were found, 193 of them in the table. Each of the other 1,869 has its reason
  and its evidence. No ID in a JSON definition of a live model is outside the table.
- **Families:** D346's list plus D371's words: `binding`, `population`, `assembly_geometry`, `assembly_hazard`,
  `assembly_representation` and `channel_block`. All operators share `operator`. The interface decides, never the
  folder.
- **The grammar:** one module holds it. A piece ID has three parts in every namespace, outside modules included.
  Refusal is by table lookup. `qualified()` stays as the one normaliser, now a checker.
- **Frozen files:** 320 under the three rules D346 names, 128 of which hold old spellings. 36 more are pinned by hash,
  and the lead rules on them (§11). A judged run is pinned to its pre-rename snapshot; a live driver that feeds a
  frozen file to the renamed engine translates it in `validation/` (§6 lists the files).
- **The move:** 1,025 files and about 9,600 lines with every row, or 959 files and about 6,900 lines if the three models
  and the catalogue laws stay bare (§5). Both leave out the 36 pinned files, four of which, in `src`, are re-spelled in
  any case.
- **By hand, before the move:** 45 sites that the token rule would leave wrong, five of them without any test failing
  (§1.5).
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
| **Sub-laws with no Law record** | 12 | `ideal_detailed_balance_mass_action@1`, `maintained_chemical_reservoirs@1`; §11's table | In scope (D371 Q4). Words: §11 |
| **The field closure law** | 1 | `resolved_capacitor_components_current_continuity@1`, the `closure.law` of every @3 world (185 spellings in 145 files) | In scope. Word: §11 |
| **A topology, two potential sets, an analysis** | 4 | `dodecahedron_g10_2@1`, `beard2005@1` and `@2`, `stationary_continuation_analysis@1` | Live code parses each (§1.6). Words: §11 |
| Recorded labels | 34 | `*_half_steps@1`, `ssprk33_*`, stage domains, observers, two analyses, the assembly RNG | Not in scope (D371 Q4). Kept bare |
| **Live models dispatched by legacy's hub** | 3 | `resolved_tissue@1`, `@2`, `@8` | §1.4 |
| **The catalogue laws** | 45 | `hcn2_m@1`, `cav1p2_m2h@1`, `cagpotassium_numeric_mM_scale@1` | A live parser looks them up (§1.6). The lead rules |
| **The ensemble's model** | 1 | `ionic_worlds@1` | Live code parses it (§1.6). The lead rules |
| Constants in live modules that only legacy reads, or that nothing reads | 8, 3 | `er_calcium_release@1`, `gauged_dense_kirchhoff@1`; `bounding_patch_constant_field@1` | Kept bare: no live code compares them |
| Legacy's own | 126 models, 394 other IDs | `resolved_calcium@11`, `spatial_calcium@4` | Frozen (D348) |
| Interface and schema IDs | 18 interfaces, about 1,100 record and file kinds (24 in live `src`) | `cells.channel_law@1`, `cells.declarations@2` | Unchanged (D346) |
| Test plants | about 260, two of them in validation drivers (`fr50test.net_flow_exchange@1`, `validation.ol6_plant_power_off_by_one@1`) | `tests.planted_route@1`, `seamtest.net_exchange@1`, `test_closer@1` | Three-part shape (D371 Q8): §3 |
| Validation's own | about 120 | BETSE emulator IDs, policy and revision labels, data set IDs | Unchanged: no engine piece |
| Prose shorthand | 8 | `replacement@1`, `water@1`, `insertion@2` | Not IDs: they stay as they are |

### 1.3 Live pieces that legacy also spells

Legacy's definitions and code use 25 live pieces by their old names: the 18 D371 ruled on, the field closure law, the
three models of §1.4, and three that the first table missed. They make 2,656 occurrences in legacy's definitions (JSON).
The 45 catalogue laws, if they are minted, make 2,010 more. All 70 sit in 100 definitions and 92 code files: 15 in
`src/cells/legacy`, 6 in live `src` that imports it, 24 tests and 47 validation files.

| Piece | In legacy's definitions | In other live files |
| --- | --- | --- |
| `constant_field@1` | 454 | 580 |
| `logmean_electrodiffusion@1` | 362 | 135 |
| `nak_atp_mass_action_positive@1` | 313 | 203 |
| `maintained_chemical_reservoirs@1`, `ideal_detailed_balance_mass_action@1`, `dodecahedron_g10_2@1` (missed at first) | 229, 125, 10 | 193, 14, 4 |
| `kir2p1_mh2@1`, `kv1p5_mh@1` | 171, 164 | 154, 54 |
| `nav1p2_m3h_regularized@1`, `junction_voltage_relaxation@1` | 115, 100 | 166, 199 |
| `capacitive_reduction_gauged_damped_newton@1`, the field closure law | 82 each | 37, 99 |
| `finite_bond_assembly@1` (nested in `assembly_regulated_cluster@1`'s definitions) | 63 | 7 |
| the five other Kv1 laws; the K, Na and Cl leaks | 50 each; 42 each | 14 each; 93, 63, 27 |
| `ideal_osmosis_linear_compliance_water@1` | six legacy models import its constant | 58 |

**How legacy reads them:** with its own literals (`legacy/core/spatial_extracellular_spec.py:26–27`,
`legacy/assembly_cluster/mobile_channels.py:93`), through live parsers that live models share
(`surface_tissue_spec.py:23, 143, 159–161, 224–228`; `surface_pump_spec.py:31, 189`;
`surface_kinetic_spec.py:371–376, 449–513`; `kinetic_pump_spec.py:43`), and through live constants. So live code alone
cannot be renamed. D371's Q3 (a) re-spells legacy's files too.

### 1.4 Three live models whose dispatch sits in legacy's hub

`resolved_tissue@1`, `@2` and `@8` are live models: their spec classes, parsers and model modules are live
(`surface_tissue_spec.py:22`, `surface_kinetic_spec.py:36` and `:42`; `models/surface_tissue.py`,
`models/surface_kinetic.py`, and for `@8` legacy's wrapper `legacy/models/surface_catalog.py`, laid out as the other
kinetic majors are, whose IDs stay bare with legacy's). Only their dispatch is
in legacy, at `legacy/registration.py:1196–1211` and `1444–1447` (parse), `794–833` (models) and `1946–1980`
(dicts). The first version of the table listed them with legacy's frozen models.

| At main 76a498ae | `@1` | `@2` | `@8` |
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

That is 169 occurrences in 104 files. 14 of them are in 12 frozen files, so 155 would be re-spelled, in 92 files, 43 of
which hold nothing else the move changes (46 if the catalogue laws stay bare). `ensemble/ionic.py:177, 196, 202` admits
them. The 19 test files that spell them are 7 in tier 1, 1 in tier 2 and 11 in tier 3. The live-subject ones (row A12's
six, and `@8`'s catalogue and equivalence files) are all in tier 3; the eight in tiers 1 and 2 reach them through
legacy's dispatch.

| | Mint now, as the 18 are re-spelled | Leave bare until the legacy batch (C-1) |
| --- | --- | --- |
| Rows | 3, `cells.model.resolved_tissue@1`, `@2` and `@8`, and with `@8` the catalogue laws (§1.6) | none: they stay on the kept list, the catalogue laws too |
| Now | 92 files, the hub's 3 literals among them; three f-strings of legacy's that build the IDs (`legacy/core/tissue_profile_composition_preparation.py:30, 35, 41`), by hand; and the generator's frozen set needs an exception with a planted case | nothing changes |
| Then | nothing | at C-1, when their dispatch moves to the live registry, a second small scripted move (3 rows, the files that still exist), and a second table for Lean and the viewer |
| Coverage | the eight test files of tiers 1 and 2 parse the re-spelled dispatch in the gate; the live-subject tests run in tier 3 the night after | none needed |
| D346 | every live ID is hierarchical | three live IDs stay bare until C-1 |
| Manifest | `legacy_entries()` lists them under their new IDs, still as legacy's | unchanged |

**The catalogue laws go with them.** `resolved_tissue@8` is the only live model whose definitions spell catalogue laws:
24 of the 45. The other 21 are admitted only for legacy's `@9` to `@12`. So one ruling covers the models and the laws.

**Recommended: leave both bare, and mint what remains at C-1.** The hub and the generator's rule for what is frozen do
not change, the move is 66 files and 2,700 lines smaller, and nine fewer pinned files are touched. C-1, where the
dispatch moves anyway, has its own full gate and tier 3, and D374 moves `@3`'s checks off `@8` in the end. The kept list
must name all 48, so that the strict parse admits them. Minting now also works, and the gate would exercise it: its gain
is one move and one table. The lead rules.

### 1.5 Hazards for a token rewriter

- **IDs built at run time** (D188's R2 class), by hand first (H2): `KV1_LAWS` in `kv1_channels.py`, the 13 `DECLARED_ID`
  f-strings, 13 test sites, and three in validation, of which `surface_pump_v3_fixtures.py:361` builds
  `resolved_pump_tissue@{version}`. `HCN_LAWS` and two validation sites join them if the catalogue laws are minted, and
  three of legacy's f-strings if the three models are. Most of the probe's 86 hits are `role@end` labels and plants.
- **Tests of part of an ID** (H2). The move changes their answer and leaves no token to re-spell.
  - Silent: `pump_water_fixtures.py:160` (`startswith("nav1p2")`, so `scheduled()` would set no channel change in the
    worlds of its four callers), `protocol_models.py:20, 42, 53, 55` (its scan would lose the live models),
    `legacy_inventory.py:83, 376`, and two set tests that would hold whatever the keys are (`test_declarations.py:170`,
    `test_operator_registry.py:112`).
  - Loud: `gene_regulation/plants.py:121`, `test_regulated_availability_population.py:99`, `test_declarations.py:282`,
    `test_cell_owned_compartments.py:1029`.
- **Old spellings that the token rule does not see:** 28 in all (`audit_skipped.json`). 21 are test IDs in
  `tests/tier3_record.json` that join a solver's ID with `-`, for the `ids` rule; 4 are regular expressions with an
  escaped dot (`cells\.transporter@1`), by hand; 3 are library page paths, for the page rule (§3).
- **By hand:** `by_hand.tsv` lists the 45 sites of these three kinds, with the two plants (§1.2) and the composition
  matrix (§6, §8), and says which are silent and which only some choices of §11 need.
- **Path segments:** 58 tokens sit inside paths. The page rule (§3) moves the pages; the token rule skips a token after
  `/`.
- **Line length:** up to 1,269 lines become longer than 100 characters, in 519 Python files. They are wrapped in a
  separate commit after the move (D371), checked at the AST level; docstring lines stay. No gate runs ruff.
- **Hash pins.** 36 files that the move would change have their SHA-256 quoted by another file in `src`, `tests`,
  `validation`, `scripts`, `examples` or `configs` (`PINS2.tsv`): 18 Python and 18 data. Four are `src` modules that
  carry live IDs (`assembly/__init__.py`, `assembly/graph.py`, `assembly_pool/__init__.py`, `ensemble/worker.py`, all
  pinned by `validation/topology/joint_water_profile_phase_handoff_protocol.json`). D187 holds: no hash is ever updated.
  The first pin check had hashed `src/` only. §11 has the choice.
- **The legacy digest check** (D371 Q3): 8 example artifacts hold 19 raw digests of their own nested definitions
  (`digest_pins.json`), so re-spelling them leaves the digests stale. The check covers the 85 files with a top-level
  model, experiment and execution by fingerprint (none pinned), and the raw nested digests of the other 140 JSON files.
  Digests of definitions that Python code builds are left to the tiers, so the condition is not fully discharged.
- **138 format and record names already have three or more parts** (`audit_dotted.json`). Nine are in live `src`, all
  formats of the assembly family (`cells.assembly_lineages.run@2`); the others are in validation, scripts, tests and the
  viewer. No piece slot reads them, none equals a new ID, and no second part is a family word. So a piece is known by
  its slot and its family, never by its number of parts.
- **Sorts** (CHECKS.md item 1): every sort that sets an array's order is over qualified keys of one family, or over
  codes, and a uniform prefix keeps it. Two sorts over declared spellings exist and set no number:
  `surface_pump_v3.py:1194` (the routing door's sources, whose factors fold in declared order) and
  `pump_composite.py:2505` (column names).

### 1.6 Live IDs that the registries cannot see

An ID is live when live code parses, looks up or compares it, whatever holds it; legacy's models are the exception
(D348). The registries hold 106. The others sit in constants, dictionary keys, f-strings and definitions, so no registry
lists them:
- **a law inside an operator or a pump, with no Law record:** `ideal_detailed_balance_mass_action@1`, the passive law of
  the species reactions (`operators/species_reactions.py:165`, compared at 460, 563 and 688), in three places of
  `resolved_pump_composite@1`'s definitions; and `maintained_chemical_reservoirs@1`, the kinetic pumps' held fuel
  (`kinetic_pump_spec.py:22, 43`), in 110 places of live definitions;
- **the keys of a lookup table:** the 45 catalogue laws of `laws/channels/` (`surface_kinetic_spec.py:371–376, 451,
  499`); `beard2005@1` and `@2` (`species_registry.py:501`);
- **a wrapper's model:** `ionic_worlds@1` (`ensemble/families.py:201`, `ensemble/ionic.py:124`), which wraps the worlds
  of live and legacy models and has no code in legacy;
- **a compared constant or config value:** `dodecahedron_g10_2@1` (`assembly/spec.py:71`, `assembly_pool/spec.py:82`)
  and `stationary_continuation_analysis@1` (`analysis/cli.py:118`).

**The new row:** `ideal_detailed_balance_mass_action@1` becomes
`cells.species_reaction.ideal_detailed_balance_mass_action@1`. `reaction` is the word of the assembly's
`cells.reaction_law@1`, whose type this law could not be, so the word is a new one (§11).

**Why the first table missed them.** It called an ID legacy's if a legacy module held it, even when a live module did
too. It took every `kind` key for a schema key. It wrote the catalogue off as legacy's. Its pattern was lower-case only,
so it missed 56 mixed-case IDs, and it did not expand `hcn{i}_m@1`.

**The audit** (read-only, `probe/audit_*.py`, for the generator to reuse) reads every quoted ID in `src`, `configs`,
`examples`, `validation`, `tests`, `scripts`, the docs pages that code names and the visualizer's readers: 2,062. The
table holds 193. The others:

| Why it has no row | IDs | Evidence (`reasons.tsv`) |
| --- | --- | --- |
| No source holds it: validation's own names and record kinds 972, test plants 174, the viewer's 64, reference files' keys 28, scripts' 26, named on a docs page only 7 | 1,271 | No literal in `src`, and no f-string there builds it, so no parse accepts it as a piece unless a test or a driver registers it |
| Legacy's models | 126 | Legacy's own dispatch |
| Legacy's other IDs | 394 | A literal in `src/cells/legacy`, none in live `src`, and no live model's definition spells it |
| Recorded labels | 34 | Live code writes them; one (the assembly RNG's) it also compares when it reads a checkpoint |
| Interfaces; formats and plan kinds in live `src` | 18; 15 | The interface registry; the `kind` or `format` of a record or a plan |
| Constants in live modules that only legacy reads, or that nothing reads | 8, 3 | The reader, or none |

- **No registry holds any of them** except the 18 interfaces, and the 126 models in legacy's own dispatch.
- **Live code compares 25 of them:** the 15 formats and plan kinds, and ten labels, nine of which it only writes. None
  passes `qualified()` or a piece slot, and D346 and D371 keep their names. Legacy's models are compared in live code
  too (`surface_kinetic_spec.py:36–46, 344–353`), and D348 keeps theirs.
- **Definitions:** the JSON files hold 169 definitions of live models, with no ID outside the table, the interfaces and
  legacy's models. In definitions that Python builds, each other ID under a slot's key is a plant, a refusal test's
  value, legacy's, or a reference's own name (`audit_slots.json`).
- **Also searched:** IDs inside longer strings, IDs built at run time, tracked binary files (none), and the names with
  three or more parts (§1.5).

## 2. The families

The user's rule (D371): short where unambiguous, prefixed where a collision could come. The interface's own noun,
without `_law` or `_term`, gives the word; the host family's prefix stays where the bare word would be vague. `block`
was not used, since it already names a definition section. The word for an interface added later is declared in the
same table, so the list stays closed and in one place.

| Family | Holds | Rows |
| --- | --- | --- |
| `model` | the model table's 11 and the 5 outside it (the three of §1.4 and `ionic_worlds@1` wait for the lead) | 16 |
| `operator` | the composite's (`cells.operator@1`) and the families' own (`cells.lineage_operator@1`, `cells.assembly_operator@1`) | 35 |
| `kind` | the inner model's kinds (`cells.kind@1`) | 5 |
| `solver`, `heat`, `execution` | what `execution.solver` and `field_solver` choose; the heat choice; `fine_windows`, `projective`, `energy_check`, the vector windows' mapping | 9, 2, 4 |
| `channel`, `cycle`, `route`, `junction`, `reaction`, `exchange` | `cells.<word>_law@1` (the 45 catalogue laws, channel laws with no record, wait for the lead) | 11, 15, 8, 2, 4, 1 |
| `rate_factor`, `free_energy` | `cells.rate_factor_law@1` and `@2`; `cells.free_energy_term@1` | 5, 3 |
| `binding`, `population` | `cells.binding_law@1`; `cells.population_structure@1` | 1, 1 |
| `assembly_geometry`, `assembly_hazard`, `assembly_representation` | the assembly interfaces of the same names | 2, 1, 1 |
| `channel_block` | `cells.channel_block_law@1` (H1) | 1 |
| words that wait for the user | §11 | 17 |

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
- a piece is `namespace.family.name@major`: the namespace and the family `[a-z][a-z0-9_]*`, the name
  `[a-z][A-Za-z0-9_]*` (names are kept, and `cagpotassium_numeric_mM_scale@1` has upper case), the major `[1-9][0-9]*`;
- an interface ID keeps `namespace.name@major`, and a schema ID keeps its name, of two or more parts (§1.5). Pieces,
  interfaces and schemas never share a slot, and no schema ID's second part may be a family word;
- the family is from the closed list in the `cells` namespace;
- D185's bare rule ends for live pieces: one spelling, so a definition, a manifest's `id` and `declared_id`, and a
  record all write the full ID;
- **the table's home in the engine** (the lead's choice): `src/cells/registry/renamed_ids.py`, generated, one dict
  literal `RENAMED = {old: new}` and a docstring, since `src` ships no data files. It is empty until the tool writes it;
- **refusal is by table lookup.** An old spelling in `RENAMED` is refused, naming its new ID. Any other bare or two-part
  value in a piece slot is refused for its shape;
- **the kept list is the tool's data, not the engine's:** legacy's frozen IDs, the 34 recorded labels, the 11 constants
  of §1.2, and the groups of §11 that are left bare. No kept ID reaches `qualified()` or another strict slot: legacy
  never calls it, the kinetic parser looks laws up in its own tables, and labels and formats are compared as text. So
  the strict `qualified()` refuses every bare ID. The audit (§5) checks that every live ID is in the table or listed;
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
| `registry/kind_registry.py` `qualified()` (98–103) | returns a full piece ID unchanged; refuses an old spelling by `RENAMED`, and any other bare or two-part ID for its shape (H1b). Its ~100 call sites in 17 files do not change |
| `registry/kind_registry.py` `_BOOKING_ID` (594, heat bookings) | `ids.piece()`: keys `kind`, values `heat` |
| `registry/declarations.py` `page_path()` (251), `scripts/library_pages.py` `page_identity()` (653) | **no change**: below |
| `registry/declarations.py` `_Context.identity()` (301–302) | `ids.parts()`: `name` stays the last part, with no new key, so `@2`'s keys and the meaning of each hold (D371 Q6). Its ID rule's text is amended |
| `registry/declarations.py` `_Context.spellings`, `legacy_entries()` | an identity map while legacy lasts; unchanged |
| `records/relations.py` `PIECE`, `SEGMENT` (151–154) | unchanged (any number of dots) |
| `definitions/specs.py` `parse_spec()` (993 on) | the literal `==` chain is rewritten by the script. Before the legacy fall-through, an old live model ID is refused by the table. For a live model, one pass over the definition refuses every old spelling (`ids.refuse_old(data)`), so no family parser needs its own check |
| Exact-key lookups on declared spellings (`channel_laws()`, `TODAYS_CHANNEL_LAWS`, `OPERATORS`, `MODELS`, compositions, `REQUIRES`, `inner_laws`' tables, and those of §1.6: `species_reactions.LAWS`, `METABOLISM_ID`, `POTENTIAL_SETS`, `TOPOLOGY_ID`, the catalogue tables) | the same lookups on the one spelling, through constants and literals the script rewrites |
| `ensemble/plan.py` 23, 92; `ensemble/families.py` `TODAY` and the `model_of` compares; `ensemble/cli.py` 141, 240, 512; `ensemble/ionic.py` | rewritten for `capsid_graph@1`, `finite_bond_assembly@1` and, if it is minted, `ionic_worlds@1`. Legacy's models stay |
| `cells.modules` (provisional, D195) | exports `qualified`; its docstring states the new contract |
| Outside src: the registry's `qualified()` in four test files and `scripts/library_pages.py:1030` (the other files that name a `qualified` define their own) | unchanged, but M makes `test_kind_types.py:154` trivial (a bare kind gains its namespace), so H1b turns it into a refusal |
| Outside src: `tests/unit/test_cell_owned_compartments.py:1029` (`model_key` from `kind_id.split(".")[1]`) and the `"cells." +` test sites | H2 |
| Outside src, patterns and tests of part of an ID: `validation/protocol_models.py:20, 42, 53, 55`, `scripts/legacy_inventory.py:83, 376`, `pump_water_fixtures.py:160`, `gene_regulation/plants.py:121`, `test_regulated_availability_population.py:99` | H2 (§1.5; the rest of `by_hand.tsv` too) |
| Outside src: `tests/unit/test_declarations.py:170` (`declarations.INNER.split(".", 1)[1]`, a set test that would pass without testing anything after the move) | H2: the exact ID |

**The library pages** (D371 Q6), checked: the six pages are at `docs/library/cells/<section>/<name>@<major>.md`
(one kind, one law, four operators). `page_path()` takes what follows the namespace, so for
`cells.channel.kv1p5_mh@1` it gives `docs/library/cells/laws/channel.kv1p5_mh@1.md`, and `page_identity()` still
reads three parts and returns the same ID. No code changes, and the section folder stays (this reverses the first
version, which dropped it). M renames the six files by the page rule. `test_library_pages.py`'s four path strings, the
text of `LAW_DOCUMENTATION_DESIGN.md` §1.2, `TEMPLATE.md` and the format page (`<name>` becomes `<family>.<name>`) and
the regenerated index follow. The viewer's tests quote one page
path (`visualizer/tests/laws_library.test.mjs`); the lead tells the viewer session.

## 4. The block law

**Decided (D371 Q2):** its own family, `channel_block`, and the interface `cells.channel_block_law@1`, whose name
follows the word. The law and the interface are registered in the hand refactors (H1), so the table holds no seeded
law row. H1 gives `open_channel_block.py` its Law record on a `ChannelBlockLaw` type, adds the module to @3's
`law_homes` in the model table and the interface to its row. The generator then maps
`open_channel_block_weighted_modes@1` to `cells.channel_block.open_channel_block_weighted_modes@1` as it maps every
other law. `fr51-slot-refusal` landed at f66fa681 without registering it.
- FR-51's tagged `cases.json` names no block ID (`engine.py` adds the constant), so registering it touches no tagged
  file.
- H1's record gives it a citation (Woodhull 1973), its D187 test and a library page (a seventh page).

## 5. The generator and the script

**One tool, `scripts/id_moves.py`, shaped and reused from D188's `source_moves.py`:** `table`, `scan` (hazards), `apply`
(the token rewriter), `verify --base --head` (replay equality, no hash edits, a second application changes nothing, no
old spelling left in scope), `ids` (collected test IDs through the table) and `selftest` (planted cases, kept out of
`tests/`).

**The generator** (`table`) refuses to write a table while any live ID is unplaced. It writes the mapping as data and
`renamed_ids.py` from it, and the kept list as data beside the mapping (`open_points.json` has today's). Its five
sources:
1. **The registries,** loaded as the manifest loads them. The family is the interface's word, or the piece's.
2. **Seeds:** non-registry module constants, each listed by module and name with its family. A seed whose constant is
   gone is refused.
3. **Legacy's frozen set:** `legacy_entries()`, every `MODEL_ID` that a module under `cells.legacy` defines, and every
   ID that only legacy's places use. An ID that a live module holds too is not one of the last (planted:
   `ideal_detailed_balance_mass_action@1`, which both hold). Excluded by ID, not by path. If the three models of §1.4
   are minted, they leave the set, with a planted case (a legacy-dispatched ID whose code is live).
4. **The reconciliation:** `git grep` of every `name@major` token in scope, upper case included, each placed in a class
   of §1.2.
5. **The audit of §1.6,** as `scan`. It fails while an ID that live `src` holds, or a live model's definition spells, is
   in neither the table nor the kept list, and while a site of `by_hand.tsv` still stands. `ast` gives the literals and
   constants, so a docstring or a comment places nothing.

Each row holds every old spelling, the new ID, the family, the piece, the interface, the host and the declaring module.
The collision report checks: two old keys to one new ID (none), one spelling naming two pieces (none), an old key equal
to a legacy ID or an interface (none), and the old keys that a schema-named key carries (the five kinds and
`maintained_chemical_reservoirs@1`, whose `kind` key names a piece, not a format).

**The rewriter** maps whole tokens, longest match. It skips a token after `/` (the page rule's), a line marked
`id-moves: keep`, and every excluded file (§6). `tests/tier3_record.json` goes through the `ids` rule instead, since 21
of its test IDs join an old spelling with `-`. It does no formatting: the long-line rewrap is its own commit.

**`verify` and the leftover guard** leave out the exclusions of §6 and `src/cells/registry/renamed_ids.py`, which holds
old spellings by design.

**Its scope:** tracked Python, JSON, shell and TOML files under `src/` (legacy included, D371 Q3), `tests/`,
`validation/`, `scripts/`, `examples/` and `configs/`, less the exclusions. With every row that is 180 files in live
`src`, 15 in legacy, 345 in tests, 351 in validation, 119 in configs, 9 in examples and 6 in scripts (`move_files.tsv`).
The 36 hash-pinned files are excluded from these sizes, and the 8 artifacts of §1.5 are counted (`move_sizes.json`):

| Rows | Files | Lines | Pinned files that hold them |
| --- | --- | --- | --- |
| every row | 1,025 | 9,599 | 36 (18 Python, 18 data) |
| without the catalogue laws | 1,005 | 7,010 | 36 |
| without the three models | 982 | 9,444 | 27 (12 Python, 15 data) |
| without both (recommended) | 959 | 6,855 | 27 |
| without both and `ionic_worlds@1` | 892 | 6,741 | 27 |

## 6. Exclusions, and how frozen files keep being read

**Never rewritten:**
- **Frozen files, by three rules,** recomputed at the morning's tagged base (`frozen_rule_v2.sh`, git and shell only).
  The tag and merge rules take only files whose blob on main is still the tag's. The dry run prints the list for each
  owner to confirm, both ways: a rule can miss a registered file, and it can catch a live tool whose blob happens to be
  a tag's, as it does `validation/tissue/composition_matrix.py`, which follow-ups edit (D364) and a test runs. That one
  is re-spelled:
  - **tag** (196 files): the non-merge commits a registration-style tag owns. The tags are named registered,
    registration, judge, references, erratum, amendment, criteria, rule, sheet, predictions, declaration, supplement
    or protocol. For a tag on a side branch, the merge that brought it in is found by searching main's first-parent
    line;
  - **merge** (158): such a tag at a merge commit on main's first-parent line, which the first version skipped. Its
    branch's own non-merge commits, restricted to spec-like paths: `references/`, `spec/`, `designs/`, and
    REGISTRATION, CRITERIA, AMENDMENT, ERRATUM, judge, rule, protocol, predictions, RUNG and sheet names. 35 of the
    files the old rules missed hold old spellings, 29 of them spec-like;
  - **commit** (48): the last change is a commit whose subject begins "Freeze" or "Register". This covers the protocols
    and predictions that predate tags.
- **Together: 320 files, 128 of which hold old spellings.** FR-50's registration files joined when FR-50 landed, and
  FR-51's two-potassium registration since.
- **36 files another file pins by hash** (§1.5), all of which hold old spellings: 4 in `src`, 14 other Python files
  (fixtures and references, live code that other modules import), and 18 data files. The candidate excludes all 36,
  which would make 356 frozen files, 164 with old spellings. That choice is the lead's (§11).
- **Who still reads the frozen ones** (`frozen_readers.json`): 29 of the 128 are Python, 24 with old spellings in code.
  Live code imports 17 of those, and names 32 frozen data files that hold old spellings. These 49 are H3's sites.
- **`lean/`:** 173 files hold 2,498 old spellings.
- **The crossrev replication record** and every record under `/mnt/workspaces`, which are outside the tree.
- **Past decision entries,** `docs/` in general, `reports/`, `agent-work/`, `visualizer/` and D188's maps.
- **Legacy's own IDs,** wherever they appear (§5, source 3).

**How they keep being read** (D371 Q7):

| Option | What | Where |
| --- | --- | --- |
| pin | a judged run uses its pre-rename snapshot | every judged run registered before the rename (D350) |
| translate | `validation/id_table.py` maps old spellings to new through `RENAMED`, recursively over JSON-like data, refusing an ambiguous one. A live driver applies it to a frozen input before parse. The engine stays strict | G1's saved definitions, crossrev's predictions, regression tests, FR-51's `cases.json`, and every live reader the dry run finds |
| erratum | a tagged erratum names the new spellings | only where a judge's own code must change |

**Eight frozen modules call the engine themselves,** so no translator fits inside them: `fr47_worlds.py`,
`fr49/judge_l.py` and `worlds.py`, `gap_junction_tissue/run.py`, `junction_gate_benchmark/revilla1999.py`,
`xenopus_bioelectric/xc0_engine.py` and `xc0_worlds.py`, and `composition_matrix.py`, which is a live tool (above).
The rest are pinned. Their judged runs are done, except those of the next table.

**Registrations with a run still to come** (D371 Q7):

| Registration | Old spellings in its frozen text | Marked |
| --- | --- | --- |
| FR-38 v2, the second comparison | prose in its spec (6); the judge, untagged, is on `fr38-v2-judge` (15) | **pinned.** Its judged run comes before its branch merges main after the rename (D371) |
| FR-45 (W1 to W7s) | prose in its spec (4); its references hold none | **translated, with nothing to translate.** Its engine code and its judge both come after the rename (D376, D377), built from constants; the registration's prose is read through the table. W2 and W7 run on the wash, whose retirement waits for them (D364) |
| FR-49 (World B, C1, C2) | `judge_l.py` (1) and `worlds.py` (4), frozen code that calls the engine; `REGISTRATION.md` (16) | **translated.** The live judges of B, C1 and C2 are not written; they wrap the frozen builders' definitions before parse. World L is judged (D331), and its frozen code is pinned |
| FR-30's Ek-Vitorín 2016 fit | none frozen: prose in `docs/JUNCTION_TWO_RELAXATION_DESIGN.md`; `harness.py` and `score.py` on `fr30-next` hold one each | neither: no fit is due (D343, D379), and the branch re-spells its live files when it merges main |
| GJ-N1's field point | `neither_rule.json` and the judge (frozen) | **pinned**, in flight on its snapshot |
| FR-51's two-potassium run (D353, D378) | `REGISTRATION.md` (3, prose), tagged since | **pinned** to 955765ef, with the frozen scorer. Its engine check has run there (D379) |

## 7. What each consumer needs

| Consumer | Needs | Recommendation |
| --- | --- | --- |
| Frozen judges, references and protocols | to keep being read | §6: pin judged runs, and translate at the live driver |
| G1 (`results_baseline.py`) | the gate runs c1's saved definitions (`--from`), old IDs included | a `--map TABLE` option: the saved definitions are translated before the head parses them. Arrays are compared bitwise and refusals must match; records go through the table. c1 is saved again at the new head as a new record |
| Crossrev | its sets are built by live generators; the qualification set reads the frozen predictions | the head reads those definitions through the translator. Programs and arrays carry no ID |
| Lean's drivers (`lean/checks/*.py`) | the table, through the user, before the landing (D346) | the Lean lane runs `id_moves.py apply --paths lean/checks` on its branch after merging main, or re-spells by hand. Its claims are read through the table. Its waiting tips are held until it rewords and rebuilds (D376); they re-merge after the landing |
| The viewer session | the table, a manifest written at the landing revision, the amended ID rule and the page paths (§3) | told by the lead. Its own data (pieces, atlas, catalogue, the `op.` boxes) re-keys. `@2`'s keys hold, but these read an ID's text: the two-part patterns in `laws_data.js:18` and `extract_laws.py:40`, the last-part pattern in `protein_atlas.py:35`, the labels in `laws_connections.js:31–40`, the `op.` keys (`laws_card.js:380, 496`), and the tests `flux.test.mjs:152` and `engine_declarations.test.mjs:36, 40` |
| Private modules | the new three-part shape | the user is told that private IDs change shape; the engine cannot name the new ones |
| Checkpoints and snapshots | snapshots keep their names. A checkpoint resumes only on the snapshot that wrote it: continuity refuses a changed model ID (case 3) | nothing translates a checkpoint. A needed one is renewed by a fresh run. Runs in flight continue on their snapshots |
| Run manifests and records | `definition_sha256` and other derived digests change; arrays do not | compared through the table (`compare_renamed_runs.py`) |
| IDs born after the rename | FR-54/57's router `cells.operator.liquid_routing@1`; FR-64's shift, a declaration with no ID | minted in the new shape, with no mapping row |

## 8. The gate plan

**One stack, gated once with the full gate, since it changes src:**
1. **The no-src notes:** this note, FR-64's and FR-54/57's, with the notes D377 lists.
2. **The docstring batch** (D351, D355, D356) and D364's two follow-ups. They come before the move, so the script covers
   their IDs.
3. **H1a, H2 and H3, hand refactors,** each small, AST-checked, value-neutral and passing today's tests, before any ID
   moves (the lead's staging; being built on `id-rename-hand`, from 76a498ae):
   - H1a: the block law's registration (§4), and the grammar module with its pure functions. The registries' patterns
     (`registry/laws.py:132`, `registry/kind_registry.py:594`) admit two parts at most today, so H1a also lets them
     admit three, or M's tree cannot import;
   - H2: the sites of `by_hand.tsv` (§1.5), each to give the same answer under either spelling where it can;
   - H3: `validation/id_table.py`, G1's `--map`, and one translator call at each live reader of a frozen file (§6's 49).
4. **M: the scripted move,** alone in its commit and pure: no folder move, no hash edit. It includes the shared pieces
   in legacy's files (§1.3: 25, or 22 if the three models stay bare, and 45 more if the catalogue laws are minted) and
   renames the six library pages.
   `verify --base H3 --head M` must hold: the replay is equal, a second application changes nothing, and no old
   spelling is left in scope.
5. **H1b: the strict grammar wired into the parse sites of §3,** a separate commit on top of M (branch
   `id-rename-strict`), with the refusal, the manifest's identity and §10's rows.
6. **W: the long-line rewrap,** a separate commit, checked at the AST level.
7. **D: docs.** The library's regenerated blocks and index, the format page's ID rule, the composition matrix's
   generated block in `docs/PUMP_COMPOSITE.md` (`composition_matrix.py --write`; a test compares it with the
   declarations), ARCHITECTURE's where-it-lives lines, PROGRESS and the decision entry.

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
4. Write the decision entry. The words and the groups of §11 are ruled on here.
5. Write `scripts/id_moves.py` (with `open_points.json` as its choices), and finish H1a, H2 and H3 (§8). H1b follows M.
6. Generate the table at the tag with the collision report, the frozen list, an empty unplaced list and a clean audit
   (§1.6: no live ID without a place, no site of `by_hand.tsv` standing). Dry-run on a scratch copy: `verify`, the IDs
   through the table, the over-long lines, and the changed files' tests, with H1b on top. Each frozen file is confirmed
   by its owner.
7. Hand the table to the Lean lane and the viewer session, through the user.
8. Gate the stack, land it, and refresh the scope map.
9. Re-merge the branches.

**Expected time:** the script and the H commits take about one agent-day, reusing `source_moves.py`, and the by-hand
sites add some hours; the dry run and its fixes take half a day; the gate takes one to two hours. FR-64's, FR-54/57's
and the other queued builds wait for it.

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
| Q4, unregistered IDs | the ten sub-laws and the field closure law are in scope; the 35 labels are not (34 now, §1.2: one of them is compared) |
| Q5, folders | a separate move after the rename: no folder moves in this one |
| Q6, the manifest | `@2`'s keys, with the ID rule amended |
| Q7, frozen files | pin or translate; an erratum only where a judge must change |
| Q8, test plants | the three-part shape, with the grammar for outside modules in §3 |

**Open:**
1. **The words for the 12 sub-laws, the field closure law and four other pieces** (D371: a new word comes back to the
   user). Twelve new words cover 16 of the 17; one reuses `solver`. The last five are new since the first version:

| ID | Named in | Proposed word |
| --- | --- | --- |
| `delayed_first_order_junction_formation@1` | `junction_formation.law` of the replacement operator | `junction_formation`, new |
| `ph_conditioned_factor@1` | `law` of a pH condition, on a transfer's rate | `transfer_factor`, new |
| `exponential_volume_activation@1` | `volume_factor` of the symport, on a route's rate | `transfer_factor`, new |
| `bounding_patch_damage@1` | `law` of a patch damage | `damage`, new |
| `hill_regulated_two_state@1` | `states[].law` of regulated availability | `regulation`, new |
| `langmuir_site_binding@1` | the site operator's recorded `laws` | `site_binding`, new |
| `site_conserving_internalisation@1` | the site operator's recorded `laws` | `site_internalisation`, new |
| `maintained_held_rows@1`, `finite_fuel_rows@1` | `fuel.kind` of a transporter | `fuel_kind`, new |
| `resolved_capacitor_components_current_continuity@1` | `closure.law` of every @3 world | `field_closure`, new |
| `exponential_mean_rate_linear_target_gates@1` | its module constant and 15 protocol notes; nothing in `src` reads it | `solver`, existing, or leave it out of the table |
| `ideal_detailed_balance_mass_action@1` | `reactions[].law` of the species-reaction operator | `species_reaction`, new |
| `maintained_chemical_reservoirs@1` | `kind` of a kinetic pump's pools | `fuel_kind`, new (with the two above) |
| `beard2005@1`, `beard2005@2` | `potential_set` of a world | `potential_set`, new |
| `dodecahedron_g10_2@1` | `topology` of `capsid_graph@1` and `finite_bond_assembly@1` | `topology`, new |
| `stationary_continuation_analysis@1` | `analysis` of an analysis config | `analysis`, new |

   They carry no Law record, so each is a seed row whose family the user fixes now. The word must be the one its later
   interface would take, or the ID moves again. That is why the two factors do not take `rate_factor`: its interface is
   the assembly's, whose type they could not be, and why the passive reaction law does not take `reaction`. The site
   laws are two words because their contracts differ. A smaller set is possible by grouping them. The last three rows
   could stay bare on the kept list instead, which saves three words, and with `topology` one stale `src` pin
   (`assembly/graph.py`). By the lead's rule they belong in the table, since live code parses them.
2. **The three models of §1.4 and the 45 catalogue laws of §1.6, together** (the lead). By the lead's rule (an ID that a
   live code path parses belongs in the table) both belong, and the candidate has their rows. Leaving both bare until
   C-1 is an exception to it, for the reasons of §1.4: **recommended**, with all 48 named on the kept list. Either
   choice is complete, and one switch of the generator makes it.
3. **`ionic_worlds@1`** (the lead): mint it (**recommended**: live code parses it and legacy has none of its code). It
   adds 64 to 67 files that hold nothing else, 60 of them tests.
4. **The hash-pinned files of §1.5** (the lead). The four `src` modules are re-spelled in every option, and their pins
   go stale, as D188's precedent (its §5) had it; D187 holds. The sizes are for every row, then for the rows
   recommended in 2 and 3:
   - (a) leave the others as frozen, 32 or 23 files: 1,029 or 963 to move. Their callers translate or stay pinned;
   - (b) re-spell them all and let the pins go stale: 1,061 or 986. The tiers show which live readers enforce them;
   - (c) re-spell the Python files (18 or 12) and leave the data files (18 or 15): 1,043 or 971. The Python ones are
     fixtures and references that live code imports. **Recommended.**
5. **The 8 example artifacts of §1.5** (the lead). Their embedded digests go stale if they are re-spelled, and the
   re-spelled legacy code refuses them if they are not. Four have readers, all tests, so the gate cannot pass untouched:
   `test_geometry_profiles_cli.py` (tier 1), `test_surface_active_profile_interventions_dispatch.py` (tier 2, two files)
   and `tests/phase_fixtures.py` (`test_tissue_phase_cli.py` in tier 2, `test_surface_profile_epoch_dispatch.py` in tier
   3). The other four (`active_tissue_phase`, `extracellular_barriers/scheduled.json`, `scheduled_membrane_profiles`)
   have none in code.
   - (a) regenerate them with their own tools after the move, with new digests (recommended if their inputs allow, which
     is not checked);
   - (b) declare those outcomes and retire the tests with legacy's at C-1;
   - (c) keep the 8 and their tests pinned to the pre-rename snapshot.

`open_points.json` holds these five as data: the words with their rows, the three groups with their switch, the pinned
files with what pins them, the artifacts with their digests and readers, and the kept list.

**For the user:** private modules' IDs change shape, from `namespace.name@major` to `namespace.family.name@major`, and
the engine refuses the old shape without naming a new ID.
