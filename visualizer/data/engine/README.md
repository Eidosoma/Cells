# The engine's own declarations, as the viewer reads them

`declarations.json` is the engine's declarations manifest (`cells.declarations@2`), written by
the engine's own command and copied here unchanged. Its format is the engine's page
`docs/library/DECLARATIONS_FORMAT.md`: that page and the file's `kind` are the contract. The
file states the revision it was written from (`revision`, `dirty`, `origin`) and holds no time
stamp: the same tree gives the same bytes.

It is the whole truth of what the engine declares: every registered law, kind and operator,
every active model, and the older model families by ID only (`legacy`). The viewer reads what
a piece is from this file and never from the engine's source; what no active registry declares
is not shown as a piece.

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

The file here was written on 17 November 2026 from main `7538b0cd` (a clean checkout): 38
pieces (14 laws, 5 kinds, 19 operators), 10 models and 127 legacy model IDs. The run's own
log is kept in `/mnt/workspaces/Cells/visualizer-analysis/declarations-7538b0cd/`.
