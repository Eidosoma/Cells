# The declarations manifest's format (`cells.declarations@3`)

The declarations manifest lists every piece the engine has registered, every law, kind and
operator, and every active model, as one JSON file. It is the engine's own record of what it
declares: the [library's pages](README.md) and the viewer's Laws library are made from it, and
neither reads the engine's source to learn what a piece is.

```bash
PYTHONPATH=src JAX_ENABLE_X64=1 JAX_PLATFORMS=cpu python -m cells declarations --out FILE
```

- **The contract is this page and the file's `kind`,** not any Python module.
  `src/cells/registry/declarations.py` writes the file; its docstring is a summary of this page.
- **The same tree gives the same bytes.** The file holds no time stamp. Its keys are sorted, its
  pieces are in (piece, `id`) order, and its models are in the order of the static model table
  (`src/cells/registry/model_table.py`). The registries load every home of that table before they
  are read, so the bytes do not depend on what a process happened to import first.
- **The writer checks the file before it writes it.** It refuses a file that breaks this format,
  or that misses a registered piece or an active model.
- **The tables below are held to the code.** `tests/unit/test_library_pages.py` (claim C5)
  compares each key table of this page with the writer's key set, in both directions.

## The file

### Top-level keys

| Key | What it holds |
| --- | --- |
| `kind` | `cells.declarations@3`. A reader checks it first and refuses another major |
| `revision` | The Git revision of the checkout or source snapshot the file was written from, or null where neither is found |
| `dirty` | Whether that tree had changes beyond its revision, or null |
| `origin` | Where the revision was read: a Git checkout or a source snapshot, or null |
| `pieces` | Every registered law, kind and operator, one object each (below) |
| `models` | Every active model of the static model table, in its order (below) |
| `not_extracted` | The (interface, key) pairs whose contract has no field for the key yet (below) |

## The ID rule

- **`id` is namespaced:** `namespace.name@major`, such as `cells.kv1p5_mh@1`. It is the key a
  reader joins on.
- **`declared_id` is the spelling the piece's own declaration uses,** and so the one
  definitions and `view.json` write. A bare ID is in the `cells` namespace (D185), so
  `kv1p5_mh@1` and `cells.kv1p5_mh@1` name one piece.
- **`host` is namespaced, and `declared_host` is its declared spelling.** The declared spelling
  is the host's own: a model's ID as the model table keys it, a kind's `kind_id`, an operator's
  `LAW_ID`. So `cells.resolved_pump_tissue@3` hosts Kv1.5, and definitions write
  `resolved_pump_tissue@3`.
- **The two spellings join byte for byte.** A definition's IDs, and a `view.json`'s, equal the
  manifest's `declared_id` of a piece or a model, its `declared_host`, or a model row's
  `declared_id`, with no rule applied. A reader that holds only the namespaced spelling applies
  D185's rule once.
- **`models` and `laws` are namespaced.** A model's `declared_id` in the models section gives its
  declared spelling.
- **`requires` keeps the operator's own spellings,** as its `REQUIRES` and `REQUIRES_KINDS`
  declare them, since a definition's operator list is compared with them as written: the
  composite's operator IDs are bare, and kind IDs namespaced.

## Pieces

Each piece is an object with exactly these keys. "Laws" means every law; "cells laws" the laws of
the five `cells` law interfaces; "operators" the composite's operators (`cells.operator@1`); and
"family operators" a model family's own (`FamilyOperator`).

### Piece keys

| Key | What it holds | Which pieces |
| --- | --- | --- |
| `id` | Its namespaced ID (the ID rule) | All |
| `declared_id` | Its ID as its declaration spells it | All |
| `namespace` | The ID's namespace | All |
| `name` | The ID's name | All |
| `version` | The ID's major, an integer | All |
| `piece` | `law`, `kind` or `operator` | All |
| `interface` | Its interface's ID with its major: a law type's own, `cells.kind@1`, `cells.operator@1`, or a family operator type's own | All |
| `host` | The namespaced ID of what runs it: a kind or a model. Kinds run in the inner model, and operators in the composite | All |
| `declared_host` | The host's declared spelling (the ID rule). Null where the host is no registered model, kind or operator: not stated | All |
| `family` | The model whose registries hold it: the inner model for its own laws, its kinds and its kinds' laws; the composite for its operators; a family's model for that family's pieces | All |
| `models` | The models whose definitions can declare it: its family, and, for the inner model's pieces, the composite. Empty where its family is no active model | All |
| `module` | Its declaring module, dotted: for a law or a family operator, the module that registered it; for a kind, the module of its hooks; for an operator, its class's | All |
| `module_path` | That module's file in this repository, `src/cells/...`. Null for a module outside the `cells` package, such as an outside package's or a test's | All |
| `line` | The first line of its declaration in that file: the call that builds a law's, a kind's or a family operator's declaration, or an operator's class statement. Null with `module_path` | All |
| `doc` | Its page, `docs/library/<namespace>/<section>/<name>@<major>.md`. Null until every page is written (below), and for a piece outside the `cells` package | All |
| `kernels` | Its functions by field, each a kernel object (below) | Laws, family operators |
| `provenance` | What it rests on: a provenance object (below) | Laws, family operators; not extracted for kinds and operators |
| `test` | The ID of the test that checks it against its reference with a planted error (D187). Null: no test is declared | Laws, family operators; not extracted for kinds and operators |
| `reads` | What it reads, each a read object with its mode (below) | Cells laws (their stage reads), operators |
| `changes` | The rows a law moves: a channel law's permeant ions, as `species`, `valence` and `relative_permeability`; a cycle law's moves, as `role` and `per_cycle`, with each row's `mode` where its general form gives them. An empty list: the law declares none | Cells laws |
| `owns` | Its own state fields, each with its axes | Kinds, operators |
| `writes` | Its writes into the inner model's fields, each with the accumulators of its own that book them | Operators |
| `provides` | The view fields and readout columns it provides: a kind's readout columns; an operator's view fields, then its readout columns | Kinds, operators |
| `controls` | Its control fields: a kind's; an operator's control fields, then the fields it multiplies | Kinds, operators |
| `ledgers` | Its own ledgers | Operators; not extracted for kinds |
| `energy` | Its heat and work fields, as `heat` and `work` | Operators; not extracted for laws, kinds and family operators |
| `units` | The unit of every field it names in a role, and of every field of its own with a unit (below). Null: not stated | All |
| `signs` | Its declared sign conventions, by field: a law type's, a kind's orientation, an operator's | All |
| `requires` | What an operator needs: `laws`, the operators that must come before it in the list, and `kinds`, the inner kinds it reads or writes, each as the operator spells it (the ID rule) | Operators |
| `laws` | The laws a kind hosts, namespaced and sorted | Kinds |
| `fields` | The rest of its declaration, as declared (each interface's own fields, below) | All |
| `status` | A level copied from a record that states one for this piece, or null: not stated. A level is never inferred | All |
| `status_source` | The record `status` was copied from; required with a level | All |

### The three meanings of null

A key that is null means one of three things, and a reader can tell which:
1. **Not applicable.** The key does not apply to that kind of piece, as "Which pieces" says.
   A kind has no `kernels`, and a law has no `owns`.
2. **Not extracted.** The pair (the piece's `interface`, the key) is in `not_extracted`, because
   that interface's contract has no field for it yet. The manifest says nothing about the piece
   there; its page says "not yet extracted".
3. **Not stated.** Otherwise: the key applies and can be declared, and the declaration does not
   state it. A law's `test` of null means that no test is declared.

An empty list or object is never null: it says that the declaration lists none.

### Units

Each field a piece names in a role (`reads`, `owns`, `writes` and their accumulators, `provides`,
`controls`), and each of its own fields with a unit, has its unit in `units`, resolved as the run
view resolves it ([the run view's design](../RUN_VIEW_DESIGN.md), "What models and operators
declare"):
1. the unit its owner declares (a law type's `UNITS`, a kind's view, an operator's `UNITS`);
2. else, for a view field of the inner model, the run view's table (`run_view.VIEW_FIELD_AXES`):
   `volume` is in pL and `membrane_area` in m2;
3. else the run view's suffix rule (`run_view.SUFFIX_UNITS`): a name ending in `_pL_s` is in pL/s,
   in `_mM` in mM, in `_V` in V, and so on;
4. else null: not stated. Many of these are fractions with no unit, such as availabilities, but
   the declaration does not say so.

### Reads and their modes

A read says which value of a field the piece takes, in the words of the operator contract's door
S (`src/cells/operators/contract.py`).
- **`current`:** the value as the step has made it so far.
- **`fixed`:** the declared value, taken as the physical one; no operator may provide it.
- **`reference`:** the bound value as data, an anchor.

An operator's reads are its view reads, which are current, and the fields it reads as declared,
which are fixed, as `SCOPED_READS` may refine them. A cells law's reads are stage reads, taken
at each stage of the inner step: current, at the inner stage.

### Read keys

| Key | What it holds |
| --- | --- |
| `name` | The field read, or for a law the read it takes (such as `rapid_proton_buffer@1`) |
| `mode` | `current`, `fixed` or `reference` |
| `stage` | The point of the step whose value it reads: `event`, `split`, `inner`, `end` or `observe` |
| `scoped` | Whether it covers only the slots the piece names, rather than every slot |

### Kernels

A kernel object names one of a piece's functions, such as a channel law's `kinetics`.

### Kernel keys

| Key | What it holds |
| --- | --- |
| `function` | The function, as `module.qualname` |
| `module_path` | Its file, `src/cells/...`, or null outside the `cells` package or for a callable with no code of its own |
| `line` | The first line of its definition, or null with `module_path` |

A page links the file and never the line, so an edit above a declaration leaves no page stale.

### Provenance keys

| Key | What it holds |
| --- | --- |
| `tag` | `parity` (moved from an older family; moving is not calibrating), `cited` or `calibrated` |
| `citation` | A cited source, as a citation object, or null |
| `source` | Any other record the piece rests on (a calibrated piece's data and method), or null |

### Citation keys

| Key | What it holds |
| --- | --- |
| `source` | The work or works, in a few words |
| `place` | Where in them |
| `licence` | The licence of any numbers taken from them (D186, D201) |
| `departures` | How the piece departs from them, each in a few words |
| `works` | The works it names, as data, each a work object. Empty for a citation of Cells' own documents, and for a citation that names its works only in words |

### Work keys

| Key | What it holds |
| --- | --- |
| `authors` | The authors, as the work gives them |
| `year` | The year, an integer |
| `title` | The title |
| `doi` | The DOI, without `https://doi.org/`, or null |
| `url` | A URL, or null. A work has a DOI or a URL at least |

Whether a work was read, and how (full text, abstract, an equation image), changes as people read
it, so that mark lives on the piece's page, never in the declaration.

## Each interface's own fields

A piece's `fields` holds the rest of its declaration. Pages link to these sections rather than
repeat them.

### Channel laws

`cells.channel_law@1`: a channel population's law on the inner model.
- `code`: its registry code in the inner model, which no other law takes;
- `gates`: the names of its gates, whose open fractions the host keeps as state;
- `permeant`: each permeant ion as (species, valence, relative permeability), also given as
  `changes`;
- `voltage_domain_V`: the voltages (V) where it is valid; a step outside is refused;
- `rk4_step_s`: the reference RK4 step bound (s), or null for a law with no gate;
- `stage_term`: its term in the step's stage rule; `loop_term`, reserved;
- its kernels: `kinetics` (voltage to each gate's target and time constant) and `opening` (the
  gates to the open fraction).

### Cycle laws

`cells.cycle_law@1`: a membrane cycle, such as a pump.
- `moves`: the rows moved per forward cycle, by role, inward-positive, also given as `changes`. A
  count is an integer, or the name of the population's parameter that holds it, negated by a
  leading `-`;
- `fuel_kinds`: the fuel kinds it can run on;
- `stage_term`, its charge slope in the step's stage rule; `material_term`, its material slope
  per stage; `charge_bound` and `material_bound`, its definition-time bounds on a charged and on
  a neutral row. Each names the kernel that supplies it, or is null where the law has none;
- `loop_term`: its loop term, where its host takes one;
- `forms`: `"base"` where its moves are written in base forms with every ligand out, so a rapid
  binding closure's totals stay exact (CORE_SEAMS §5.2), or null;
- `cycle`: its general form (seam A's cycle form), or null. Where it is set, the form carries the
  law: the form's own checks apply, `moves` may be empty and the kernels null, and `changes` holds
  the form's rows, one for each row a mode changes, with that `mode`;
- its kernels: `kinetics` and `domain_valid`. Its stage reads are its `reads`.

### Route laws

`cells.route_law@1`: a passive route.
- `hosts`: the entities its routes sit on, such as membranes and junctions;
- `basis`: what it is, in its sources' words.
- `stage_term`, `material_term`, `charge_bound` and `material_bound`: its step terms, as for cycle
  laws, each a kernel's name or null;
- `forms`: as for cycle laws.

A route law declares nothing it changes: a definition chooses the species of most routes.

### Binding laws

`cells.binding_law@1`: a rapid binding closure.
- `ligands`: the ligands it binds, by role;
- `forms`: `"registry"` where its binders' forms are the species registry's, or null;
- its kernels: `closure` (free forms from totals) and, optionally, `domain_valid`. A general
  closure (CORE_SEAMS §19) also declares `free_energy` (its free-energy term G*), `envelope` (the
  first-order lag envelope of its binding network) and `free_amounts` (the free forms from the
  totals, which P1's predictor reads); a version-1 closure declares none of the three.

### Junction laws

`cells.junction_law@1`: a junction's conductance law.
- `gated`: whether it carries a gate state;
- `max_abs_voltage_V`: the largest voltage across a junction (V) where it is valid;
- `gate_count`: its gates in series, 1 for a one-gate law (FR-30);
- its kernels: `kinetics`, `rhs` and `domain_valid`, and `conductance` (the junction's relative
  conductance from its gates) where it has several gates; a one-gate law's `conductance` is null.

### Kinds

`cells.kind@1`: machinery of the inner model that hosts laws and keeps their state and books.
- `model_key`: the definition key under which a definition declares it;
- `layout_fields`: its layout fields, which hold a definition's values;
- `experiment_keys`: its keys in a definition's experiment, for its schedules;
- `hooks`: the hooks it gives the inner model, by name;
- `record_kinds` and `record_layers`: each record's kind (level, amount, cumulative or rate) and
  its layer in the run view.

### Operators

`cells.operator@1`: a part of the composite's step, with its own state and books.
- `parts`: where it acts in the step: an `event` map, a `split` part or an in-step `process`;
- `declaration_only`: true for a declaration with no part of the step;
- `step_method`: the numerical method of its split part, or null;
- `closes` and `retires`: the activity masks it may close, and whether its events retire slots;
- `experiment_keys`: its keys in a definition's experiment;
- `record_kinds` and `record_layers`, as for kinds; `class_name`, its class.

### Family interfaces

A model family's own interface, declared in its row of the static model table. A law of one is a
type built on the law template (`Law`), and an operator of one a type built on the operator
template (`FamilyOperator`). The manifest does not interpret their fields: every field of its own
is under `fields`, its functions under `kernels`, and the role keys are null.

## Models

`models` lists every active model of the static model table, in its order. Its pieces are the
model's rows.
- **`type`** is `inner` (the inner model, which hosts its own laws and its kinds), `composite` (an
  inner model and any ordered list of operators), `composition` (the composite with a fixed
  operator list, as `frozen_definition` rewrites it) or `family` (a model family of its own).
- **A family with no rows** is an older family whose laws are tables inside it. It gets no page.

### Model keys

| Key | What it holds |
| --- | --- |
| `id` | Its namespaced ID |
| `declared_id` | Its ID as definitions write it |
| `type` | `inner`, `composite`, `composition` or `family` |
| `module` | The module whose `parse` reads its definitions |
| `module_path` | That module's file, `src/cells/...` |
| `doc` | Its page, null until every page is written; always null for a family with no rows |
| `rows` | The pieces it declares or requires, each a row object (below) |
| `next_code` | The inner model's next free channel code, which a new channel law takes; null for other models |

### Row keys

| Key | What it holds |
| --- | --- |
| `role` | What the row is to the model (below) |
| `id` | The row's namespaced ID |
| `declared_id` | Its ID as definitions write it |
| `piece` | Where the row has its own entry: `law`, `kind`, `operator` or `model`; null where it has none, as for a fuel kind |
| `slot` | Where the model has slots: `code` for a channel law, `key` for a kind (its definition key), `position` for a composition's operator; else null |

**Roles:**
- the inner model: `channel law`, by code; `junction law`; `cycle law`; `route law`; `binding law`;
  `law` for a law of another interface; `fuel kind`, the fuel kinds its cycle laws run on; and
  `kind`, by definition key;
- the composite: `operator`, in ID order; any ordered list of them is a definition's composition;
- a composition: its `inner model`, then each `operator` by position;
- a family: its `law`s and its `operator`s.

## Not extracted

`not_extracted` lists, for the interfaces the pieces use, the keys their contracts have no field
for yet. Each such key is null on every piece of that interface. Today:
- every law interface lacks `energy`, the law template's energy role ([the core-seams
  design](../CORE_SEAMS_DESIGN.md) §8.1);
- `cells.kind@1` lacks `energy`, `ledgers`, `provenance` and `test`;
- `cells.operator@1` lacks `provenance` and `test`;
- every family operator interface lacks `energy`.

### Not-extracted keys

| Key | What it holds |
| --- | --- |
| `interface` | An interface the pieces use |
| `key` | A piece key its contract has no field for yet |

## Pages: `doc`

Every piece declared in the `cells` package, and every model with declared structure, gets one
page at `docs/library/<namespace>/<section>/<name>@<major>.md`, where the section is `laws`,
`kinds`, `operators` or `models`. The path follows the ID alone, so a page never moves when code
does ([the design](../LAW_DOCUMENTATION_DESIGN.md) §1.2). While the pages are written in batches,
`doc` is null on every piece and model. The commit that writes the last page sets it, so a `doc`
that is not null always names a file.

## The version rule

Any change to the keys, or to what a key means, takes a new major of `kind`. A reader checks
`kind` and refuses a major it does not know.
- `cells.declarations@3` (25 November 2026) has every key of `@2` but `legacy`, a list of model IDs
  that the static model table did not hold. It covers the ID move too (D345, D371): the move
  amends how the ID rule spells an ID, and no key changes its meaning. So a reader compares whole
  IDs, by the ID rule, and takes neither an ID's number of parts nor its spelling as fixed.
- `cells.declarations@2` (17 November 2026) added `doc`, `module_path`, `line`, `declared_host`,
  `models` and `not_extracted`. `cells.declarations@1` (seam F, the same day) gave each read as a
  bare name, each kernel as a bare `module.qualname`, and citations without `works`.
