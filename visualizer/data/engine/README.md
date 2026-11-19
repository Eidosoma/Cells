# The engine's own declarations, as the viewer reads them

`declarations.json` is the engine's declarations manifest (`cells.declarations@2`), written by
the engine's own command and copied here unchanged. Its format is the engine's page
`docs/library/DECLARATIONS_FORMAT.md`: that page and the file's `kind` are the contract. The
file states the revision it was written from (`revision`, `dirty`, `origin`) and holds no time
stamp: the same tree gives the same bytes.

It is the whole truth of what the engine declares: every registered law, kind and operator,
every active model, and the older model families by ID only (`legacy`). The engine map
(`tools/extract_architecture.py`) takes from this file which operators, laws, kinds, family
operators and models the engine declares, and what each operator declares. What no active
registry declares is not shown as a piece. The build refuses a file of another major, one
written at another revision than the checkout it reads, and one written from a tree with changes.

Some things are still read from the engine's source, because this file does not hold them, or
does not hold them apart:
- the files, their sizes and imports, the plan's gates and the shared-state table, which are
  not pieces;
- four class attributes of each composite operator, read through the class this file names, and
  checked against the file where it holds them:
  - `RK4` and `ACCEPTS_WRITES`, which it does not hold;
  - `VIEW_FIELDS` and `CONTROL_FACTORS`, which split its `provides` (view fields, then readout
    columns) and its `controls` (control fields, then the availabilities it multiplies);
- each model module's `MODEL_ID`, only to place a declared model on the part of the module that
  runs it, since a model's `module_path` here is the module that declares its structure;
- whether a model module defines `device_checks`;
- the protein atlas's check of each law record's identifier, whose laws are mostly the older
  families' and not in this file.

## How it is made

The viewer never imports or runs engine code in its own process. The manifest is made out of
process, in a checkout of the engine at one pushed revision of main, as a detached unit:

```bash
scripts/run_detached.sh viz-declarations-<revision> 3G --cpus 12-15,28-31 --oom-first \
  --runtime-max 900 --dir <a clean checkout of main at that revision> \
  --env PYTHONPATH=src --env JAX_ENABLE_X64=1 --env JAX_PLATFORMS=cpu \
  -- <the engine's Python> -m cells declarations --out <a folder under /mnt/workspaces/Cells>/declarations.json
```

Then the file is copied here byte for byte. Nothing edits it by hand. A reader checks `kind`
first and refuses another major.

The file here was written on 19 November 2026 from main `1ca5eada` (a clean checkout): 55
pieces (28 laws, 5 kinds, 22 operators), 11 models and 127 legacy model IDs. The run's own
line of output, which gives its totals (55 pieces, 11 models, 127 legacy model IDs) and `dirty:
false`, is kept in its unit's journal, the second unit of that day's run: the first had exited
with an error, and the file is the second's.
