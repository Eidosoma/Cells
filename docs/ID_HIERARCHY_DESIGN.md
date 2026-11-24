# The ID hierarchy: the rename's design

25 November 2026, for the morning's review by the user and the lead with the advisor, before any script runs.
A design note only: it writes no engine code and changes no live file. It settles D350's design inputs and the two
questions D361 moved here.

**What is decided** (D345, D346, D348):
- every live ID becomes `cells.<family>.<name>@major`, from a closed list of families;
- interface IDs and schema IDs keep their names;
- no aliases: an old ID is refused at parse, and the refusal names its new one;
- one scripted move, with a mapping table generated from the registries;
- legacy's IDs stay bare and frozen until legacy is deleted, which follows the ports;
- never rewritten: tagged specs, references and judges, the crossrev replication record, `lean/` and past decision
  entries;
- no compatibility beyond this repository.

**The candidate table** comes from a read-only probe, not from the generator. It ran at main `f8c6c326`, on CPU 4
under the timed lock. The tree's only untracked file was this note, which the probe does not read:
- `/mnt/workspaces/Cells/rename-design-20261124/candidate-f8c6c326/` holds `table.tsv` (old spelling, new ID, family),
  `mapping.json`, `SUMMARY.txt` (every class and every ID in it), `TAGGED.txt` and `FOLLOWUP.txt`;
- the probe is beside it, in `probe/`.

The real generator goes into `scripts/` with the rename (§5).

## 0. Summary

- **The table has 127 rows and no collisions:**
  - 106 registry pieces: 55 laws, 5 kinds, 27 composite operators, 8 family operators and 11 models. The family
    operators were missing from the lead's dump, which read only the composite's section;
  - 21 seeded rows: 9 solvers, 4 execution choices, 2 heat choices, the block law, and 5 live models the model table
    lacks.
- **Families:** D346's list, plus `binding`, `geometry`, `population`, `hazard` and `representation` for the five
  missing interfaces, and `block` for the block law. All operators share `operator`. The interface decides a law's
  family, never its folder.
- **The grammar:** one module holds it. A piece ID has three parts; interface and schema IDs keep two. Refusal is by
  table lookup, never by shape. `qualified()` stays as the one normaliser, now a checker.
- **Two findings change the plan:**
  - About 120 live IDs are in no registry. 21 of them become seed rows. The rest are 10 sub-laws with no Law record,
    the field closure law, 35 recorded labels, and about 53 IDs in live modules that only legacy reads (§1.2,
    question 4).
  - 18 live pieces are also spelled inside legacy's definitions and code: 2,272 occurrences in 102 legacy definitions,
    and 67 in 33 code files. They include constant_field, the Na/K pump, Kv1.x, Kir2.1, Nav1.2, the leaks and the
    field solver. They cannot be renamed in live code alone (§1.3, question 3).
- **Frozen files:**
  - 152 files under `validation/` are frozen by two rules: registration tags, and Freeze and Register commits.
    71 of them hold old IDs.
  - By default a judged run is pinned to its pre-rename snapshot.
  - A live driver that feeds a frozen file to the renamed engine translates it through the committed table, in
    `validation/` only. The engine never accepts an old ID.
- **The gate:** one stack, with the full gate. G1 and crossrev go through the table, and `compare_renamed_runs.py`
  runs on a sample of the run paths. Tier 3 runs the night after.
- **Test cost:** 14 rows in existing files, under 5 s, with no new file and no world compiled.
- **The questions for the user** are in §11.

## 1. What the probe found

### 1.1 The registries

| Source | Pieces | Spelled today as |
| --- | --- | --- |
| Laws (`laws.active()`) | 55 over 14 interfaces: channel 11, cycle 15, route 8, reaction 4, rate_factor@1 3, rate_factor@2 2, free_energy_term 3, junction 2, assembly_geometry 2, binding 1, exchange 1, assembly_hazard 1, population_structure 1, assembly_representation 1 | Bare (`kv1p5_mh@1`). The 13 cycle and transporter laws also carry `DECLARED_ID = f"cells.{LAW_ID}"`. The assembly family's laws are qualified (`cells.stochastic_mass_action@1`) |
| Kinds | 5 | Qualified (`cells.transporter@1`) |
| Composite operators (`cells.operator@1`) | 27 | Bare (`site_occupancy@1`) |
| Family operators (`cells.lineage_operator@1`, `cells.assembly_operator@1`) | 8 | Qualified (`cells.shear_fission@1`) |
| Models (`model_table.MODELS`) | 11 | Bare, except the two assembly families |

Today D185's rule joins the two spellings: a bare ID is in `cells` (`kind_registry.qualified()`). The manifest carries
both, as `id` and `declared_id`.

### 1.2 Live IDs that no registry holds

The probe took every `name@major` token in the live tree and classed it. The full lists are in `SUMMARY.txt`.

| Class | IDs | Examples | Disposition |
| --- | --- | --- | --- |
| Declared choices | 15 | `imex_ars222_face_electromigration@1`, `capacitive_reduction_gauged_damped_newton@2`, `trapezoid_nonnegative@1`, `fixed_fine_windows@1`, `vmap_device_checks@1` | Renamed, as seed rows from their module constants (§5) |
| The block law | 1 | `open_channel_block_weighted_modes@1` | §4 |
| Live models outside the model table | 5 | `source_decay@1`, `emt_mirna@1`, `passive_pair@1` (parse_spec's inline families), `capsid_graph@1`, `finite_bond_assembly@1` (the ensemble's assembly families) | Renamed as seed rows (question 4) |
| Sub-laws with no Law record, named inside a live kind or operator | 10 | `delayed_first_order_junction_formation@1`, `ph_conditioned_factor@1`, `bounding_patch_damage@1`, `hill_regulated_two_state@1`, `langmuir_site_binding@1`, `site_conserving_internalisation@1`, `exponential_volume_activation@1`, `exponential_mean_rate_linear_target_gates@1`, `maintained_held_rows@1`, `finite_fuel_rows@1` | Question 4 |
| The field closure law | 1 | `resolved_capacitor_components_current_continuity@1`, the `closure.law` of every @3 world. Legacy's `resolved_tissue@1` parser reads the same constant | Question 4 |
| Recorded labels | 35 | step and splitting IDs (`*_half_steps@1`, `ssprk33_*`, `events_then_symmetric_operator_halves@1`), stage domains, observers, the three analyses, the assembly RNG, a topology | Question 4 |
| Laws in live modules that only legacy and the calcium ensemble read | about 52 | 44 channel catalogue laws (`cav1p2_m2h@1`, the Morris–Lecar and HCN sets, `hcn1_m@1` to `hcn4_m@1` built by an f-string), 4 calcium reactions (`ncx_3na_1ca_symmetric_barrier@1`), and the tissue field's laws and solver (`capacitive_regions_ghk_return_current@1`, `gauged_damped_newton@1`) | Frozen with legacy (D348). Their modules are live, but only legacy's models reach them |
| The calcium ensemble's model | 1 | `ionic_worlds@1` | Frozen with legacy until the ensemble's port |
| Legacy's own | 129 models and about 350 other IDs | `resolved_calcium@11`, `spatial_calcium@4`, `assembly_regulated_cluster@1` | Frozen (D348) |
| Interface and schema IDs | 18 interfaces and about 1,100 kinds of records and files | `cells.channel_law@1`, `cells.declarations@2`, `cells_assembly_checkpoint@1` | Unchanged (D346) |
| Test plants | about 120 in the `tests` and `seamtest` namespaces, and about 140 bare | `tests.planted_route@1`, `seamtest.net_exchange@1`, `test_closer@1` | Question 8 |
| Validation's own | about 120 | BETSE emulator IDs, policy and revision labels, data set IDs, the potential sets `beard2005@1` and `@2` | Unchanged: no engine piece |
| Prose shorthand | 8 | `replacement@1`, `water@1`, `insertion@2`, `relations@2` | The docstring batch, not the script |

### 1.3 Live pieces that legacy also spells

Legacy's definitions (JSON whose model is one of legacy's 129) and legacy's code use 18 live pieces by their old
names:

| Piece | In legacy's definitions | In other live files |
| --- | --- | --- |
| `constant_field@1` | 477 | 557 |
| `logmean_electrodiffusion@1` | 378 | 119 |
| `nak_atp_mass_action_positive@1` | 321 | 195 |
| `kir2p1_mh2@1`, `kv1p5_mh@1` | 174, 170 | 151, 48 |
| `nav1p2_m3h_regularized@1`, `junction_voltage_relaxation@1` | 117, 102 | 164, 197 |
| `capacitive_reduction_gauged_damped_newton@1` | 86 | 33 |
| `finite_bond_assembly@1` (nested in `assembly_regulated_cluster@1`'s definitions) | 63 | 7 |
| the five other Kv1 laws | 51 each | 13 each |
| the K, Na and Cl leaks | 43 each | 91, 62, 26 |
| `ideal_osmosis_linear_compliance_water@1` | six legacy models import its constant | 58 |

That is 2,272 occurrences in 102 legacy definitions, and 67 in 33 code files (7 in `src/cells/legacy`, 26 tests and
drivers that import it).

Legacy compares these IDs partly with its own literals (`spatial_extracellular_spec.MEMBRANE_LAW =
"constant_field@1"`), and partly through live constants and live parsers (the tissue base, the channel tables).
Renaming them in live code only would make legacy refuse its own definitions. Question 3 has the options.

### 1.4 Hazards for a token rewriter

- **Computed IDs** (D188's R2 class), refactored by hand before the move:
  - in src, `laws/channels/kv1_channels.py` (`KV1_LAWS`, an f-string over the five Kv1 laws) and the 13
    `DECLARED_ID = f"cells.{LAW_ID}"` modules. After the move these would read `cells.cells.cycle...`;
  - in tests, about 20 sites (`"cells." + law`, `f"tests.{name}@1"`, `f"test_r{k}@1"`);
  - in validation, one file (`betse/betse_reference_extract.py`, two sites).

  `hcn_channels.py`'s f-string builds catalogue IDs that stay frozen. The other hits, about 50 of the 86, are
  `role@end`, `species@phase` and `case@time` labels, not IDs.
- **Path segments:** 56 tokens sit inside paths, such as `docs/library/cells/laws/kv1p5_mh@1.md`. The page rule moves
  them (§3), and the token rule skips any token after `/`.
- **Line length:** the rewrite makes about 1,100 lines longer than 100 characters, in about 420 Python files.
  Ruff's E501 is selected, but no gate runs ruff.
- **Pins:**
  - Two data-file pins in `validation/topology/joint_water_profile_phase_handoff_protocol.json` pin
    `src/cells/assembly/__init__.py` and `src/cells/assembly_pool/__init__.py`, whose `MODEL_ID`s question 4 (a)
    renames. D187 holds: no hash is updated, and the tier gate shows whether any live reader checks them.
  - No pin is on any other rewritten file, nor on the 7 legacy code files question 3 (a) would touch.
- **Three schema kinds already have three parts:** `cells.assembly_lineages.probe@1`,
  `cells.assembly_lineages.f12_table@1` and `cells.source_moves.report@1`. They keep their names, since no piece slot
  reads them, and `assembly_lineages` is not a family word.
- **Sorts** (CHECKS.md item 1, extended):
  - every sort that sets an array's order is over qualified keys of one family (`laws.laws()`,
    `kind_registry.canonical`) or over codes, and a uniform `cells.<family>.` prefix keeps its order;
  - two sorts over declared spellings exist. `surface_pump_v3.py:1193` orders the routing door's sources, whose factors
    fold in declared order, so no number moves. `pump_composite.py:2498` sorts column names, not IDs.

## 2. The families

| Family | Holds | Rows |
| --- | --- | --- |
| `model` | the model table's models and the 5 live models outside it | 16 |
| `operator` | the composite's (`cells.operator@1`) and the families' own (`cells.lineage_operator@1`, `cells.assembly_operator@1`) | 35 |
| `kind` | the inner model's kinds (`cells.kind@1`) | 5 |
| `solver` | what `execution.solver` and `field_solver` choose, and the integrator a representation declares | 9 |
| `heat` | the heat choice (`heat_bookings`, the faces' exact heat) | 2 |
| `execution` | `fine_windows`, `projective` and `energy_check`, and the vector windows' mapping | 4 |
| `channel`, `cycle`, `route`, `junction`, `reaction`, `exchange` | `cells.<word>_law@1` | 11, 15, 8, 2, 4, 1 |
| `rate_factor` | `cells.rate_factor_law@1` and `@2` | 5 |
| `free_energy` | `cells.free_energy_term@1` | 3 |
| `binding` (new) | `cells.binding_law@1` | 1 |
| `geometry` (new) | `cells.assembly_geometry@1` | 2 |
| `population` (new) | `cells.population_structure@1` | 1 |
| `hazard` (new) | `cells.assembly_hazard@1` | 1 |
| `representation` (new) | `cells.assembly_representation@1` | 1 |
| `block` (new, question 2) | the block law, under `cells.block_law@1` once registered | 1 |

**The word rule:** the interface's own noun, without the generic `_law` or `_term` and without the host family's
`assembly_` prefix. It reads as the existing words do (`cells.free_energy_term@1` gives `free_energy`). An interface
added later declares its word in the same table, so the list stays closed and in one place. Names are unchanged, even
where they repeat the word (`cells.binding.rapid_binding@1`, `cells.geometry.bilayer_geometry@1`), since D345 keeps
names and majors.

**Operators share one family.** The registry already holds one namespaced ID per operator across both of its
sections, and every operator's `interface` still names its contract. A word per operator interface would put a model
family's name into the closed list for each new family.

**The interface decides, never the folder.** One table in the grammar module, `LAW_FAMILIES = {interface: word}`, is
the only home of the words. Registration checks a law's family against its type's interface: `cells.cycle.kv1p5_mh@1`
declared as a ChannelLaw is refused. So `rapid_binding@1`, which sits in `laws/reactions/` and implements
`cells.binding_law@1`, becomes `cells.binding.rapid_binding@1`. `laws/pumps/` (cycle laws), `laws/transport/` (route
laws) and the block law's place in `laws/channels/` mismatch the same way. Moving the folders is question 5.

**The word "family".** The prose keeps D345's word: "the ID's family". The declarations manifest's `family` key keeps
its meaning, the model whose registries hold the piece, which the viewer shows ("in the registries of ..."). The
manifest gains no key for the ID's family: `id` carries it, and for a law `interface` implies it. The code names it
only inside the grammar module (`ids.parts(x).family`), so no field anywhere is called `family` with the new meaning.

## 3. The grammar and its parse sites

**The grammar** (`src/cells/registry/ids.py`, new, imported by the registries and the parsers):
- a piece is `namespace.family.name@major`, each part `[a-z][a-z0-9_]*`, the major `[1-9][0-9]*`;
- an interface or a schema ID keeps `namespace.name@major`. The two never share a slot: a parse site knows which it
  expects;
- the family is from the closed list in the `cells` namespace. An outside namespace takes the same shape, and an
  outside interface declares its own word (D345);
- D185's bare rule ends for live pieces: one spelling, so a definition, a manifest's `id` and `declared_id`, and a
  record all write the full ID;
- the kept list keeps today's rule: legacy's frozen IDs, and the live IDs question 4 (a) keeps bare. `qualified()`
  still prefixes `cells.` to an ID on that list. Each ID leaves the list when legacy goes or when it is minted in its
  family;
- **refusal is by table lookup.** A value that is an old spelling in the committed table is refused, naming its new
  ID. Any other bare or two-part value in a piece slot that is not on the kept list is refused for its shape. Shape
  alone cannot decide, since interface and schema IDs keep two parts.

**The refusal's wording** (one function, every site):

    model.id: resolved_pump_tissue@3 was renamed cells.model.resolved_pump_tissue@3 (D345)
    Law cells.cycle.kv1p5_mh@1: a cells.channel_law@1 law's ID is cells.channel.<name>@major
    populations[0].law: kv9_mh@1 is not namespace.family.name@major (D345)

The first line is the old-ID refusal: the slot, the old spelling, the new ID and D345. The table stays as data, so a
past decision entry or a Lean claim is read through it (D345). The refusal costs one dictionary lookup.

**Every parse, split, qualify and compare site, and how each changes:**

| Site | Today | After |
| --- | --- | --- |
| `registry/laws.py` `_ID`, `_is_id(value, namespaced)` (132–139) | one optional dot | `ids.piece()` for laws and hosts; `ids.interface()` for the `namespaced=True` case |
| `registry/laws.py` `Law.errors()` (196–200) | "[namespace.]name@major" | adds the family check against `LAW_FAMILIES[interface]` |
| `registry/laws.py` 211, 626; `registry/operators.py` 102, 143, 165 | `x.split(".", 1)[0] == NAMESPACE` | unchanged: the namespace is still the first part |
| `registry/operators.py` `FamilyOperator.errors()` | `_is_id` | `ids.piece(…, family="operator")` |
| `registry/kind_registry.py` `qualified()` (96–101) | prefixes `cells.` to a bare ID | returns a full piece ID unchanged; refuses an old spelling by the table; keeps the prefix for the kept list only. Its ~100 call sites in 17 files do not change |
| `registry/kind_registry.py` `_BOOKING_ID` (554, heat bookings) | one optional dot | `ids.piece()`: keys `kind`, values `heat` |
| `registry/declarations.py` `page_path()` (251) | `<namespace>/<section>/<name>@<major>.md` | `docs/library/<namespace>/<family>/<name>@<major>.md`. The six pages move |
| `registry/declarations.py` `_Context.identity()` (301–302) | splits on the first dot and the last `@` | `ids.parts()`: `name` is the last part, with no new key (§2) |
| `registry/declarations.py` `_Context.spellings` | declared spelling by qualified ID | an identity map while legacy lasts; then it goes |
| `registry/declarations.py` `legacy_entries()` | reads legacy's dispatch | unchanged |
| `records/relations.py` `PIECE`, `SEGMENT` (151–154) | any number of dots | unchanged |
| `definitions/specs.py` `parse_spec()` (993 on) | a literal `==` chain, then `legacy().parse` | the chain is rewritten by the script. Before the legacy fall-through, an old live model ID is refused by the table. For a live model, one pass over the definition refuses every old spelling (`ids.refuse_old(data)`), so no family parser needs its own check |
| Exact-key lookups on declared spellings: `surface_pump_v3_spec.channel_laws()`, `TODAYS_CHANNEL_LAWS`, `OPERATORS`, `MODELS`, compositions, `REQUIRES` and `REQUIRES_KINDS`, `inner_laws`' tables | the declared string | the same lookups on the one spelling, through constants and literals the script rewrites |
| `ensemble/plan.py` 23, 92; `ensemble/families.py` `TODAY` and the `model_of` compares; `ensemble/cli.py` 141, 240, 512 | literal model IDs | rewritten for `capsid_graph@1` and `finite_bond_assembly@1`. `ionic_worlds@1` and the legacy models stay |
| Computed IDs (§1.4) | f-strings, `"cells." +` | hand refactors before the move: H2 (§8) |
| `cells.modules` (provisional, D195) | exports `qualified` | its docstring states the new contract |
| `scripts/library_pages.py`, `tests/unit/test_library_pages.py` | the page path | follow `page_path()` |

## 4. The block law (D361)

`open_channel_block_weighted_modes@1` is live in definitions (`"law": ...` under a population's `block`). It has no
Law record and is not among the law homes. `fr51-slot-refusal` landed at f66fa681 without registering it, so its row
is a seed from `open_channel_block.LAW_ID`. After FR-64 its interface is simple: an instantaneous fraction of V_ref and
c_B, with no reference of its own.

| Option | ID | For | Against |
| --- | --- | --- | --- |
| (a) a family of its own | `cells.block.open_channel_block_weighted_modes@1`, interface `cells.block_law@1` | D345 reads the family as the interface, and D346 gives one word per law interface. `JunctionLaw` took an interface of its own for a contract unlike the channel's. A Law record gives it provenance (Woodhull 1973), its D187 test and a library page | one more word in the closed list |
| (b) the channel family, a second interface | `cells.channel.open_channel_block_weighted_modes@1` | it acts on a channel population, and readers find it beside the channels | breaks one word per interface. `rate_factor` spans two IDs, but they are two majors of one interface, not two interfaces |
| (c) no law ID, a declaration | the block's `law` key goes | no word, no interface | loses the record, citation, test and page. The definition's schema changes, so a refusal row is needed and FR-51's tagged REGISTRATION.md names a key that no longer exists |

**FR-51's tagged files under each:** `cases.json`'s blocks carry no law ID; `validation/fr51/engine.py` adds it from
the constant. So (a) and (b) touch no tagged file, and REGISTRATION.md's mention is prose, read through the table.
Under (c) engine.py stops adding the key.

**Recommended: (a).** The rename mints the ID once as a seed row. FR-64's build then gives it its Law record and
`cells.block_law@1` under that ID. Registering it before the rename would mint an ID that the rename then changes.

## 5. The generator and the script

**One tool, `scripts/id_moves.py`, shaped and reused from D188's `source_moves.py`:**
- `table`: the generator;
- `scan`: reports hazards;
- `apply`: the token rewriter;
- `verify --base --head`: replay equality, no hash edits, a second application changes nothing, no old spelling left
  in scope;
- `ids`: collected test IDs through the table;
- `selftest`: the planted cases, kept out of `tests/` so that new test files do not change the collected IDs.

**The generator** (`table`) builds the rows from four sources, and refuses to write a table while any live ID is
unplaced:
1. **The registries,** loaded the way the manifest loads them (every home of the model table): laws with their
   interfaces, kinds, the composite's operators, the families' operators and the model table. The family is the
   interface's word, or the piece's.
2. **Seeds:** non-registry module constants, each listed by module and name with its family, the definition key that
   carries it (§1.2 says which). A seed whose constant is gone is refused.
3. **Legacy's frozen set:** `legacy_entries()`, plus every `MODEL_ID` that a module under `cells.legacy` defines, plus
   every ID that only legacy's places use. Excluded by ID, not by path.
4. **The reconciliation:** `git grep` of every `name@major` token in scope, each placed in a class of §1.2. Any token
   still unplaced stops the table.

**Each row** holds every old spelling (bare, qualified and declared), the new ID, the family, the piece, the interface,
the host and the declaring module.

**The collision report** checks:
- two old keys mapping to one new ID (none);
- one spelling naming two pieces (none);
- an old key equal to a legacy ID, an interface or a schema ID (none);
- the shared pieces of §1.3.

**The rewriter** (`apply`) maps whole tokens, taking the longest match, so `cells.kv1p5_mh@1` is one token. It skips:
- a token after `/`, which the page rule moves;
- a token on a line marked `id-moves: keep` (D188's marker, for recorded text in code);
- every excluded file (§6).

It does no formatting. The over-long lines are listed, not wrapped: a follow-up commit wraps code lines and is checked
at the AST level, as D188's refactor commits were. Docstring lines stay as they are.

**Its scope:** tracked Python, JSON, shell and TOML files under `src/`, `tests/`, `validation/`, `scripts/`,
`examples/` and `configs/`, less the exclusions (§6). That is 812 files and about 4,160 lines today: 168 in src, 259
in tests, 350 in validation, 23 in configs, 7 in examples and 5 in scripts. Question 3 (a) adds 102 legacy definitions
and 33 code files.

## 6. Exclusions, and how frozen files keep being read

**Never rewritten:**
- **Frozen files, by two rules,** recomputed at the morning's tagged base:
  - **the tag rule.** For each registration-style tag (142 today: registered, registration, judge, references,
    erratum, amendment, criteria, rule, sheet, predictions, declaration and supplement), take its own non-merge
    commits: reachable from the tag, but not from main before the merge that brought it in. Every file under
    `validation/` they changed whose blob on main is still the tag's is frozen. That gives 105 files, 33 of which hold
    210 old spellings (`TAGGED.txt`);
  - **the commit rule.** Every file under `validation/` whose last change is a commit whose subject begins "Freeze" or
    "Register" is frozen. There are 28 such commits, from 9 to 22 November, and they include the registered protocols
    and predictions that predate tags, such as W1's, W2's and G2-Q1's. That gives 48 files, 39 of which hold old
    spellings;
  - **the keep list.** The dry run reviews the result and adds any frozen file the two rules miss;
  - together, 152 files, 71 of which hold old spellings: 48 JSON, 18 Python and 5 Markdown;
  - FR-50's `judge.py`, `REGISTRATION.md`, `JUDGE_ERRATUM_1.md` and `references/` join when FR-50 lands.
- **`lean/`:** 166 files hold 2,491 old spellings.
- **The crossrev replication record** and every record under `/mnt/workspaces`, which are outside the tree.
- **Past decision entries,** `docs/` in general, `reports/`, `agent-work/`, `visualizer/` (the viewer's own) and
  D188's maps in `scripts/moves/`.
- **Legacy's own IDs,** wherever they appear (§5, source 3).

**How the 71 frozen files with old spellings are read, by the advisor's test:**

| How | Cases |
| --- | --- |
| It reaches the engine's parse at a post-rename head through a live reader | the commit rule's protocols and predictions, whose definitions G1 (through c1's saves), crossrev's qualification set (W1's, W2's and G2-Q1's predictions), regression tests and acceptance drivers parse. From the tag rule: `fr7/references/interface/{inputs,loop_inputs}.json` (`fr7/loop_comparison.py`), `gap_junction_tissue/{linear,neither}_rule.json` (their judges' tests), `mitochondria/references/components/interface/inputs.json` (`component_comparison.py`), `tissue/regulated_availability_protocol.json` (a regression test and a dt study), and `fr7/references/{loop,worlds}.py` (imported by `test_fr7_references.py`). Also FR-51's `cases.json` leak laws, which `engine.py` copies into the engine's declaration |
| It meets only other frozen text | registered judges and rules (gap-junction, XC0, mitochondria, OOL). FR-50 joins this row at its landing: its judge compares the references' `declared` with `cases.json`, both frozen, and its `engine.py` takes law IDs from module constants |
| Prose | READMEs and registrations, read through the table |

The dry run lists the first row exactly. A strict engine refuses each live reader at parse, naming the new ID, and the
tiers show where. Each read site then gains one call to the translator below.

**The options** for the first row (D361: the pre-alpha rule argues against a shim):

| Option | What | Cost |
| --- | --- | --- |
| (a) pin | every rerun of a registration from before the rename uses a pre-rename snapshot, as judged runs already do (D350) | no code. But a frozen input then cannot be run on the renamed engine at all: not G1's saved definitions, not crossrev's predictions, not the regression tests above |
| (b) translate at the driver's boundary | one function in `validation/id_table.py` maps old spellings to new through the committed table, recursively over JSON-like data, refusing an ambiguous one. A live driver applies it to a frozen input before parse. If a frozen judge ever compares a string the engine writes with a frozen one, the driver maps the engine's string back (no case today) | one small module and one row. The engine stays strict: the translator sits outside `src/`, reads frozen evidence, and is retired with the last frozen input that needs it |
| (c) tagged errata | each affected registration re-spells its files under a new tag, as FR-49's judge erratum did for one field | about 30 registrations now, and every later frozen file the same way |

**Recommended:**
- (a) for judged runs;
- (b) for the live drivers, G1 and the regression tests;
- (c) only where a judge's own logic must change.

The same table feeds the leftover guard (§10).

## 7. What each consumer needs

| Consumer | Needs | Recommendation |
| --- | --- | --- |
| Frozen judges, references and protocols | to keep being read | §6: pin judged runs, and translate at the live driver |
| G1 (`results_baseline.py`) | the gate runs c1's saved definitions (`--from`), old IDs included | a `--map TABLE` option: the saved definitions are translated before the head parses them. Arrays are compared bitwise and refusals must match. Records are compared through the table, as `compare_renamed_runs.py` does. After the landing, c1 is saved again at the new head as a new record; the old record stays |
| Crossrev | its sets are built by live generators. The qualification set also reads W1's, W2's and G2-Q1's frozen predictions (`validation/tissue/*_predictions.json`, by the commit rule) | the head reads those definitions through the translator. Programs and binding arrays carry no ID, so the comparison is unchanged |
| Lean's drivers (`lean/checks/*.py` declare worlds with old IDs) | the table, through the user, before the landing (D346) | the Lean lane runs `scripts/id_moves.py apply --paths lean/checks` on its own branch after merging main, or re-spells by hand. Its claims and records stay readable through the table. `kir_spermine_potassium.py`'s `reference` key is FR-64's change, not the rename's |
| The viewer (`visualizer/`, the viewer agent's) | its committed `declarations.json` is pinned to a revision, and its own data (pieces, protein atlas, catalogue) key on IDs | the table, and a manifest written at the landing revision. The viewer re-keys its own data. If the manifest's key set is unchanged, its reader needs no change (question 6) |
| Frozen checkpoints and snapshots | snapshots keep their names. A checkpoint resumes only on the snapshot that wrote it: continuity refuses a changed model ID (case 3), and a definition's fingerprint changes with its IDs | nothing translates a checkpoint. A checkpoint needed on the renamed engine is renewed by a fresh run, as FR-44's washed worlds were. Runs in flight (GJ-N1's field point, judged runs) continue on their snapshots |
| Run manifests and records | `definition_sha256` and the other DERIVED digests change; arrays do not | compared through the table (`compare_renamed_runs.py`) |
| New IDs born after the rename | FR-54/57's router is `cells.operator.liquid_routing@1` (D362), and FR-64's shift is a declaration with no ID | minted in the new shape at their builds, with no mapping row. The table holds only IDs that existed before |

## 8. The gate plan

**One stack, gated once with the full gate, since it changes src:**
1. **The no-src notes:** this note, FR-64's (`fr64-design`) and FR-54/57's (`fr54-57-design`).
2. **The docstring batch** (D351, D355, D356) and D364's two follow-ups. They come before the move, so the script
   covers their IDs.
3. **H1 to H3, hand refactors,** each small and AST-checked (D188 called its own R1 to R4):
   - H1: the grammar module, the refusal, the parse sites of §3, and the manifest's identity and page path;
   - H2: the computed IDs of §1.4;
   - H3: `validation/id_table.py`, G1's `--map`, and one translator call at each live reader of a frozen file.
4. **M: the scripted move, alone in its commit.** Under question 3 (a) it includes the 18 shared pieces in legacy's
   files. `verify --base H3 --head M` must hold: the replay is equal, no hash is edited, a second application changes
   nothing, and no old spelling is left in scope.
5. **D: docs.** The library pages move to their new paths. The format page's ID rule, ARCHITECTURE's where-it-lives
   lines, PROGRESS and the decision entry follow.

**The checks:**
- **Pre-lock:**
  - the IDs step, through the table (`id_moves.py ids`), so that a parametrized test ID carrying a renamed ID is the
    same test;
  - the guard set, and the changed test files within their rows.
- **Under the lane's lock:**
  - crossrev, every set, bitwise;
  - tiers 1 and 2 against the record;
  - G1 through the table (§7);
  - FR's bitwise set and the fingerprints unit (`fingerprints_landing.sh`), both through the table.
- **After the lock:**
  - `compare_renamed_runs.py` on the run-paths pair (fresh, resumed, branched, windowed and batch), with the table as
    its map, longest first;
  - the manifest regenerated, and the library check;
  - tier 3 the next night, since every world's definition changes spelling.

About an hour locked (D346), plus G1. No tier needs re-measuring: no test file is added and none changes cost.

## 9. The morning, and the branches in flight

**The order** (D346 as D348 amends it):
1. Land what is gated: FR-50 on lane B with the FR set, then the queue.
2. List the judged runs not finished and pin each to its pre-rename snapshot (D350). They include FR-45's W2 and W7,
   FR-49's B and C1, OL6 Protocol D v2's further seed sets if any, and GJ-N1's field point. D353's two-arm
   registration is written after the move, or pinned to 955765ef (D361).
3. Tag main: `pre-id-rename-2026-11-25`.
4. Review this note's questions, and write the decision entry.
5. Write `scripts/id_moves.py` (§5) and H1 to H3.
6. Generate the table at the tag, with the collision report and an empty unplaced list. Do a dry run on a scratch
   copy: `verify`, the IDs through the table, the over-long lines, and the changed files' tests.
7. Hand the table to the Lean lane and the viewer, through the user.
8. Gate the stack, then land it.
9. Re-merge the branches.

**Expected time:** the script and the H commits take about one agent-day, reusing `source_moves.py`. The dry run and
its fixes take half a day, and the gate one to two hours. So the landing is late on 25 November or on 26 November.
FR-64's and FR-54/57's builds wait for it (D361, D362).

**Branches in flight** (36 unmerged today; only `fr50-one-way-records`, `speedup-r4-configure-caches`,
`fr38-export-probe(-b)` and `packed-gpu-planner` change src):
1. merge main;
2. in a file only the M commit changed, resolve a conflict by taking the branch's side, then run
   `scripts/id_moves.py apply`. It rewrites the branch's own new references and leaves its tagged files alone, since
   the rule finds the branch's tags;
3. merge conflicts in H1 to H3's files by hand;
4. run the leftover guard and the branch's changed tests.

Reference and registration branches never rewrite their tagged files. Their live drivers translate (§6).

## 10. Test cost (D224)

Rows in existing files. None compiles a world:

| Row | File | Seconds |
| --- | --- | --- |
| a law whose family is not its interface's is refused | `tests/unit/test_law_registry.py` | < 0.1 |
| an old spelling is refused, naming its new ID | `tests/unit/test_law_registry.py` | < 0.1 |
| every family interface of the model table has its word (planted: one without) | `tests/unit/test_model_table.py` | < 0.1 |
| the model table's keys are full IDs | `tests/unit/test_model_table.py` | < 0.1 |
| an old model ID at parse | `tests/unit/test_specs.py` (`test_invalid_definitions`) | < 0.1 |
| an old ID at parse for a law, an operator, a kind, a solver, a heat choice and an execution choice | `tests/unit/test_surface_pump_v3_definitions.py` (`test_definition_errors_reject`) | 6 × < 0.1 |
| identity's three parts, and the page path | `tests/unit/test_declarations.py` | < 0.1 |
| the leftover guard: no old spelling in scope outside the exclusions | `tests/unit/test_model_table.py`, beside its tree checks | about 2 |
| a frozen input through `validation/id_table.py` (FR-51's `cases.json`), round trip | FR-51's host rows, `tests/unit/test_surface_pump_v3_populations.py` | < 0.1 |

14 rows and under 5 s. The script's checks live in its `selftest` (D188). No test is removed: tests change spelling
only.

## 11. Questions for the user

1. **The five new family words.**
   - (a) `binding`, `geometry`, `population`, `hazard`, `representation`;
   - (b) the interfaces' full nouns: `binding`, `assembly_geometry`, `population_structure`, `assembly_hazard`,
     `assembly_representation`.

   **Recommended: (a).** The words describe what the interface is, and another family may implement them later.
2. **The block law** (§4).
   - (a) a family of its own, `block`, with `cells.block_law@1` at FR-64's build;
   - (b) the channel family with a second interface;
   - (c) no law ID: the block becomes a declaration.

   **Recommended: (a).**
3. **The 18 live pieces that legacy also spells** (§1.3).
   - (a) re-spell them in legacy's definitions and code too. Legacy's own IDs stay bare. This adds 135 files (102
     definitions, 33 code files) to the move, and the tiers measure legacy's tests;
   - (b) keep the 18 bare until legacy is deleted, with a second scripted move then. @3's definitions mix spellings
     until that move;
   - (c) delete legacy first, which reverses D348's order and waits for the multi-day ports.

   **Recommended: (a).** D346 itself says old live IDs are refused, so legacy's uses of live pieces must change. Only
   legacy's own IDs are frozen.
4. **Live IDs that no registry holds** (§1.2).
   - (a) rename the 5 live models outside the table with the pieces and declared choices. Keep the 10 sub-laws, the
     field closure law and the 35 recorded labels bare until each gets a Law record or becomes a declared choice. Each
     is then minted once in its family, as the block law will be;
   - (b) rename them all now, adding words for them, such as `field`, `factor`, `fuel` and `step`.

   **Recommended: (a).** A word without an interface is what FR-64 rejected for `voltage_shift` (§7 there). The closure
   law is tied to legacy's `resolved_tissue@1` parser anyway.
5. **Folders** (D345's "folders mirror interfaces").
   - (a) a separate `source_moves.py` move after the rename, with its own gate: `laws/pumps` and `laws/transport` into
     `cycles` and `routes`, `rapid_binding` into `binding`, the block law into `block`;
   - (b) in the same move;
   - (c) never, since the ID now carries the family.

   **Recommended: (a).** Module paths reach tagged files, plants and pins, so they are best verified apart.
6. **The manifest's format.**
   - (a) keep `cells.declarations@2`'s keys and amend its ID rule: `name` is the last part, and `declared_id` equals
     `id`;
   - (b) bump to `@3`: drop `declared_id` and `declared_host`, and add the ID's family under a key not named `family`.

   **Recommended: (a).** The viewer needs no reader change. The redundant keys can go with the next format change.
7. **How frozen files are read** (§6).
   - (a) pin judged runs, translate at live drivers' boundaries through the table, and use an erratum only where a
     judge must change;
   - (b) errata for every affected registration;
   - (c) pin only, with G1 and crossrev re-recorded once from a translated run.

   **Recommended: (a).**
8. **Test plants** (§1.2).
   - (a) plants take the full shape (`tests.route.planted_route@1`). The script places a plant by its declaring type
     and the dry run lists the rest for hand edits;
   - (b) outside namespaces keep `namespace.name@major`, which makes a second grammar.

   **Recommended: (a),** since plants stand for outside modules (D345).
