# The experiment's source package and its manifest (`cells.experiment_package@1`)

The contract another person can write a package from: the run folder an experiment's runs are saved in, given a name,
and the manifest (`experiment_package.json`) that says what is in it. It is the first of the two levels the owner
accepted on 19 November 2026 (`docs/EXPERIMENT_PACKAGE.md`, sections 3 and 4): the **source package** is what the
engine side writes and what stays with the frozen evidence. The **play package**, what is carried to a page, comes in
the next round.

**The names are the engine's lead's.** The engine's lead keeps the specification of the source level (decision 7), and
read the viewer's proposal and this contract's first text on 20 November 2026: the names and rules below are as
settled then. The last section says what that reading changed. No run folder written so far has a manifest: the
engine's drivers come to write one from their next runs, and frozen evidence is not written into.

The run view itself, what one package's `view.json` states and how the viewer reads it, is `schema/RUN_VIEW.md`
("The engine's view", "A run with the engine's own view beside its files"); nothing of it is repeated here. The
manifest's schema file is `schema/experiment_package.schema.json`, and the validator is `tools/check_package.py`.

## The folder

```
<run folder>/                    the source package
  experiment_package.json        the manifest (cells.experiment_package@1)
  summary.json                   optional: the experiment's sweeps (cells.experiment_summary@1), named by the manifest
  <arm>/                         one package for each arm, the folder named as its arm
    view.json                    cells.run_view@1: what the run saved and how to read it
    trajectory.npz               the arrays the view names (a windowed run: the chunks its time bases name)
    <sidecar>.json               optional: a quantity the experiment's driver states (cells.experiment_quantity@1,
                                 cells.experiment_criterion@1), named by the manifest
    run.json                     optional: the run's own record, in its driver's format; the manifest's copies are
                                 held to it
    ...                          the run's other files: read by no reader of this level
  <arm>/REFUSED.json             in place of a package, for a pick an engine check refused, named by the manifest
```

- **Must be there:** `experiment_package.json`; for each package of the kind `cells.run_view@1`, its folder with its
  `view.json` and every file the view's time bases name, each holding the arrays the view says are there; every
  sidecar, summary and `REFUSED.json` the manifest names.
- **May be there:** anything else. The engine's own files of a run (`resolved_config.json`, `manifest.json`,
  `run.json`, `summary.json`, `checkpoint_final/`) stay beside its view as the evidence they are. One of them is read
  where it is there: a run's own record, `run.json`, to which the manifest's copies are held ("The rules").
- **What a reader ignores:** every file and folder the manifest does not name, and every field it does not know (see
  "Versions"). A folder that holds a `view.json` and is not one of the manifest's packages is left aside, and the
  validator says so in a note.
- **No links.** A package holds its files itself: a reader follows no link, and a link anywhere in a package, or on
  the way to a file the manifest names, is refused.

## The manifest, field by field

`experiment_package.json` is one JSON object (UTF-8, no `NaN` or `Infinity`, at most 1 MiB). A field marked required
must be there and not null.

| Field | Type | Required | What it means |
| --- | --- | --- | --- |
| `format` | one of: `cells.experiment_package@1` | required | The manifest's format and major version. A reader of @1 reads @1 only. |
| `level` | one of: `source` | required | Which level of package this is: `source`, the run folder as the engine writes it. The play level comes in the next round. |
| `experiment` | object | required | The experiment the packages are runs of, in its own words. |
| `experiment.id` | id | required | The experiment's id, one for each source package: the public id, and what other files point at (a card, an address, a life stage's span). A run's id is `<experiment id>--<arm>`, with the seed where there is one. |
| `experiment.group` | id | optional | The id under which a catalogue gathers this package with the other source packages of one experiment: its sweeps are each a package with an id of its own. |
| `experiment.title` | text | required | The experiment's name, in a few words. |
| `experiment.asks` | text | optional | What the experiment asks, in one sentence. |
| `experiment.plain` | text | optional | What it does, in plain sentences. |
| `experiment.status` | text | optional | The owner's own words for the runs' standing ("development run of the engine, not judged", say). For an experiment of the public record the page reads its standing from the Engine map and the record, and shows these words only where the record has none. |
| `experiment.sources` | list of objects | optional | Where the experiment is stated: documents of the engine's repository, at its revision. |
| `experiment.sources[].path` | text | required | The document's path in the engine's repository (a reference, not a file of the package; never a path of a machine). |
| `experiment.sources[].where` | text | optional | Where in it, in words. |
| `experiment.citation` | object | optional | What the experiment replicates or reads from, as it is cited. |
| `experiment.citation.text` | text | required | The citation as written. |
| `experiment.citation.doi` | text | optional | Its DOI. |
| `engine` | object | optional | The engine's provenance, copied from the runs' own records: its revision, its snapshot and whether its tree was clean, and no more. The manifest adds no digest of its own. Where it is given, each run's view must agree with it, and so must its `run.json` where it has one. |
| `engine.revision` | revision | optional | The engine's revision that ran (7 to 40 hexadecimal digits): each view's `run.source.revision` and each `run.json`'s `revision` (a short form of the same revision is the same). |
| `engine.snapshot` | text | optional | The execution snapshot it ran from, by name: each `run.json`'s `snapshot`. |
| `engine.clean` | true or false | optional | Whether the engine's tree was clean: each `run.json`'s `clean`, and the opposite of each view's `run.source.dirty`. |
| `made` | day | optional | The day the package was written (`YYYY-MM-DD`). |
| `visibility` | one of: `public`, `private` | required | Who may see the package. A tool that stages a page, a site or an API refuses a private package (the next round). |
| `licence` | text | required | The licence the package is given under, by its SPDX identifier where it has one (`CC-BY-4.0`, say). Words and numbers read from a source keep that source's terms. |
| `summary` | path | optional | The experiment's summary of its sweeps (`cells.experiment_summary@1`, `schema/RUN_VIEW.md`, "A sweep's chart"), relative to the manifest. |
| `packages` | list of objects | required | The packages, one for each arm, at least one, in the order a reader lists them. |
| `packages[].arm` | id | required | The arm's id. One arm once, in `packages` and `refused` together. |
| `packages[].kind` | text | required | How the package is read: `cells.run_view@1`, a folder that holds the engine's `view.json` and the arrays it names; or `cells.assembly_view@1`, the assembly's, written by its model's own writer. A reader names a package of a kind it does not read, and reads the rest. |
| `packages[].path` | path | required | The package's folder, relative to the manifest. In @1 it is the folder named as its arm, directly in the run folder. |
| `packages[].sidecars` | list of sidecar names | optional | The quantities the experiment's driver states beside the run, each by its plain file name in the package's folder, in the order they are played (the order of their records). Where the run's own `run.json` lists its sidecars, these are the same names, each once. |
| `packages[].label` | text | optional | The arm's name in words. |
| `refused` | list of objects | optional | Picks an engine check refused: each a folder named as its arm, holding its `REFUSED.json` and no view. |
| `refused[].arm` | id | required | The pick's arm: its folder's name. |
| `refused[].file` | name | required | The refusal's file, by its plain name in the arm's folder (`REFUSED.json`). |

Types: **text** is a string that is not empty; an **id** is lower-case letters and digits joined by single dots or
hyphens (`^[a-z0-9]+([.-][a-z0-9]+)*$`), so that a run's id splits at its first `--`; a **path** is file names
joined by `/`, each of letters, digits, dots, underscores and hyphens; a **name** is one such file name; a **sidecar
name** is lower-case letters, digits, underscores and hyphens, then `.json` (the adapter's own rule); a **day** is
`YYYY-MM-DD`.

A made-up example:

```json
{
  "format": "cells.experiment_package@1",
  "level": "source",
  "experiment": { "id": "made-up-package", "group": "made-up-group", "title": "A made-up package", "status": "made up, not a run of any experiment" },
  "engine": { "revision": "0123456789abcdef0123456789abcdef01234567", "snapshot": "snapshot-01234567", "clean": true },
  "visibility": "public",
  "licence": "CC-BY-4.0",
  "summary": "summary.json",
  "packages": [
    { "arm": "alpha", "kind": "cells.run_view@1", "path": "alpha", "sidecars": ["criterion.json", "concentration.json"], "label": "Alpha" },
    { "arm": "beta", "kind": "cells.run_view@1", "path": "beta", "sidecars": ["concentration.json"] }
  ],
  "refused": [{ "arm": "gamma", "file": "REFUSED.json" }]
}
```

## The rules

- **Paths stay inside the folder.** `summary` and `packages[].path` are relative to the manifest; a sidecar and a
  refusal's `file` are plain names in their arm's folder. None is absolute, none has a `..` part, none names nothing,
  and none goes through a link. `experiment.sources[].path` is a reference into the engine's repository, not a file of
  the package, and is held only to carry no path of a machine.
- **No path of a machine anywhere in the manifest**: no `/home/`, `/mnt/`, `/Users/` (nor `/tmp/`, `/var/`, `/root/`,
  `/opt/`, `/srv/`) and no drive letter, in any key or any string.
- **Ids.** The experiment's id and every arm are ids (above). An experiment's id is one for each source package, and
  it is the public id: the sweeps of one experiment are each a source package with an id of its own, and
  `experiment.group` is the id a catalogue gathers them under. A run's id is `<experiment id>--<arm>`, with the seed
  where there is one (`schema/RUN_VIEW.md`, "Packaged for the viewer"); ids are what other files point at.
- **One arm once**, across `packages` and `refused`. A refused pick is no package, and its folder holds no view.
- **`kind`** says how a package is read. `cells.run_view@1` is the one kind this reader reads. The assembly's kind is
  `cells.assembly_view@1`, written by its model's own writer: this reader names such a package and leaves it aside
  until that writer and a reader of it exist. A kind a reader does not know is named and left aside the same way, and
  the rest is read.
- **Sidecars are named in the order they are played.** The order of `packages[].sidecars` is the order of their
  records in the replay, and a reader follows it. Where an arm's `run.json` lists its `sidecars`, the manifest names
  the same names, each once and no other; the record's own order is not held.
- **`visibility` and `licence` are required.** Nothing in this round refuses a private package: the staging tools'
  refusal of a private or unlicensed package is the next round's.
- **Provenance stays the engine's.** A run's own record (`run.json`, in its driver's own format, where its driver
  wrote one) stays where it is, and is what the manifest points at. `engine` copies three things and no more: the
  revision, the snapshot, and whether the tree was clean. Where `engine` is given, a view that states otherwise is
  refused (`run.source.revision`, `run.source.dirty`), and so is a `run.json` that does (`revision`, `snapshot`,
  `clean`). A `run.json` is not required. Its key for a clean tree is `clean`; one written before the manifest may
  say `snapshot_clean`, and is read as the same. The engine models a package runs are each view's own statement
  (`run.engine_models`), which the manifest does not copy.
- **Versions.** Within a major, a reader ignores a field it does not know (the validator names it in a note). A change
  that an older reader would misread is a new major (`cells.experiment_package@2`), which a reader of @1 refuses.

## A folder with no manifest

Every run folder written so far has none. A reader reads such a folder as the adapter has read one since before the
manifest (`tools/adapt_run.py`): its packages are those its `index.json` chooses (`selected`, or else every package
whose `view` is `written`), or, with no `index.json`, every folder in it that holds a `view.json`, by name; its
sidecars are those the `index.json` names for each package (`packages[].sidecar`), and with no `index.json` the
viewer's overlay names them (`data/replays/overlay.json`, `sidecar`); its refused picks are the folders that hold
`REFUSED.json` and no view; its summary is the file the overlay names. A folder that holds a `view.json` itself is one
package. The validator reads such a folder the same way (without the overlay, which is the viewer's, not the
package's), says in a note that it has no manifest, and gives what a manifest would state: every package with its
kind, its path and the sidecars named or found beside it, the refused picks, the summary, and the engine's provenance
where every view agrees (with the snapshot, where the runs' own records name one), with `null` for what the folder
does not say (its title, visibility and licence).

## Sidecars, refused picks and the summary

- **Sidecars** (`cells.experiment_quantity@1`, `cells.experiment_criterion@1`) are as `schema/RUN_VIEW.md` states them
  ("A quantity the experiment states"): their cells are the view's cells, each once, and every time the replay steps
  through is one of their `times_s`. Only the sidecars the manifest names are read, in its order, which is the order
  they are played and the order of their records. A file beside a view that says it is a sidecar and that nothing
  names is read by nobody.
- **A refused pick** is a folder named as its arm that holds `REFUSED.json` and no view: `{"arm", "status":
  "refused", <the sweep's parameter>: value, ...}`. A reader names it by its arm and its value of the parameter of
  the summary's one sweep, and reads nothing else of it (not its error, not when it was refused). A manifest that lists
  refused picks names a summary of one sweep.
- **The summary** (`cells.experiment_summary@1`) is as `schema/RUN_VIEW.md` states it ("A sweep's chart"); its arms
  are named as the packages' arms.

## Checking a package

```
python3 -I tools/check_package.py FOLDER [--json]
python3 -I tools/check_package.py --schema        the manifest's JSON schema, as the validator writes it
python3 -I tools/check_package.py --codes         every code with its kind and what it means
```

- **Exit status** 0: the package can be read; the report gives the experiment, its packages with their kinds, their
  sidecars and the runs they give, the refused picks, the summary, and what the manifest carries of visibility and
  licence, with any notes. 1: it cannot, with every problem found, each a code and one sentence that names the file and
  the field. 2: a wrong call (no folder, a folder that is not one, or flags that do not go together). `--json` gives
  the same report as one JSON object (`folder`, `manifest`, `readable`, `experiment`, `visibility`, `licence`,
  `packages`, `refused`, `summary`, `problems`, `notes`, `would_state`; each problem and note `{code, file, field,
  says}`).
- **What "readable" means.** The validator holds the contract (the manifest's fields, the paths, the arms, the views'
  files, arrays and shapes, the sidecars, the refused picks, the summary, and the manifest's copies against each view
  and each run's own record), and then reads each package by the adapter's own reading (`adapt_engine_view` in
  `tools/adapt_run.py`, with the sidecars the folder names) and the adapter's machine-path check of what it would
  package. So a package that passes is one `npm run adapt:runs` reads. The adapter's reading runs only on a package
  whose own checks found nothing, and only where the adapter reads the manifest.
- **It writes nothing and runs nothing of a package.** Array files are read as the adapter reads them, a zip of `.npy`
  members, and the validator's own checks read only each member's header for its shape and type: a large array costs no
  more to check than a small one. A package is untrusted input: the manifest is read up to 1 MiB, every other JSON file
  up to 32 MiB (an arm's `resolved_config.json` and `summary.json` too, which the adapter's reading reads, and its
  `run.json`), an array a view names up to 1 GiB as its header or its zip gives it (the adapter's reading decompresses
  it whole), a `.npy` header up to 64 KiB, a `.npz` of up to 65,536 members, and a walk of up to 200,000 files and
  folders; past a cap nothing is read and the cap is said. A sentence of the report that quotes what a package says of
  itself is cut at 2,000 characters. No link is followed and no path leads outside the folder.
- **A folder that is itself one package** is read as its arm, and nothing of the folder around it is listed. The
  adapter's own reading looks there for `index.json` and `experiment_package.json`, and reads them where they are (they
  would name the package's sidecars); the validator then says so in its note.
- **It judges no science.** It says whether a package can be read, never whether a run is right.
- **What it does not hold yet:** the size of the play files (a run's file under 1 MB is the adapter's, and depends on
  the viewer's choices for the experiment); the refusal of a private or unlicensed package (the staging tools', next
  round); every refusal of the adapter's own reading is given under `adapter.refused`, with the adapter's sentence,
  not under a code of its own.

### Codes

Each problem's sentence names the file and the field; the sentence here says what each code means.

| Code | Kind | What it means |
| --- | --- | --- |
| `manifest.none` | note | The folder has no `experiment_package.json`: it is read as the adapter reads a folder today (its `index.json`, or else every folder in it that holds a `view.json`), and the report gives what a manifest would state. |
| `folder.one-package` | note | The folder holds a `view.json` itself: it is read as one package, the arm named as the folder, of the folder around it; a source package is that folder, with its manifest. |
| `manifest.unknown-field` | note | The manifest gives a field this reader does not know: it is left aside (within a major, a reader ignores what it does not know). |
| `package.kind-unknown` | note | A package is of a kind this reader does not read (one it does not know, or the assembly's, `cells.assembly_view@1`, which it does not read yet): it is named and not read, and the rest is read. |
| `package.not-listed` | note | A folder holds a `view.json` and is not one of the folder's packages: a reader leaves it aside. |
| `package.no-view` | note | A folder holds a run of the engine's shared output path and no `view.json`: the adapter derives its view from tables of its own, and a source package holds the engine's own view. |
| `sidecar.unnamed` | note | A file beside a view says it is a sidecar, and nothing names it: a reader does not read it; a manifest names the sidecars to read, in their order. |
| `package.not-id` | note | In a folder with no manifest, a package's folder name is not an id, as a manifest's arm must be. |
| `index.machine-path` | note | The folder's `index.json` carries a path of a machine; a manifest may carry none. |
| `json.invalid` | problem | A file that must be JSON is not (or is not UTF-8). |
| `size.cap` | problem | A file, an array or the folder is larger than this reader's cap: a package is untrusted input, and nothing past the cap is read. |
| `manifest.format` | problem | `experiment_package.json` is not a JSON object whose format is `cells.experiment_package@1`. |
| `manifest.level` | problem | `experiment_package.json`'s level is not `source`: this round reads the source level only. |
| `manifest.missing` | problem | `experiment_package.json` lacks a required field. |
| `manifest.type` | problem | A field of `experiment_package.json` is not of its type (text, a list, an object, a revision, a day, or true or false). |
| `manifest.id` | problem | An id (the experiment's, or an arm's) is not lower-case letters and digits, joined by single dots or hyphens. |
| `manifest.visibility` | problem | `experiment_package.json` gives no visibility, or one that is not `public` or `private`. |
| `manifest.licence` | problem | `experiment_package.json` gives no licence. |
| `manifest.machine-path` | problem | `experiment_package.json` carries a path of a machine (`/home/`, `/mnt/`, `/Users/` and the like, or a drive letter). |
| `path.absolute` | problem | A path is absolute: every path of a package is relative to the manifest (a sidecar or a refusal's file, to its arm's folder). |
| `path.outside` | problem | A path leaves the folder (`..`). |
| `path.form` | problem | A path is not file names joined by `/`, each of letters, digits, dots, underscores and hyphens. |
| `path.missing` | problem | A path names nothing in the folder. |
| `path.kind` | problem | A path names a file where a folder is wanted, or a folder where a file is wanted. |
| `path.link` | problem | A file or folder of the package is a link: a package holds its files itself, and a reader follows no link. |
| `package.arm-twice` | problem | An arm is named twice (in `packages` and `refused` together): one arm once. |
| `package.path` | problem | A package's path is not the folder named as its arm, directly in the run folder: readers of @1 read a package from there. |
| `folder.no-package` | problem | A folder with no manifest holds no package: no `index.json` that chooses one, and no folder that holds a `view.json`. |
| `index.content` | problem | A folder's `index.json` does not choose its runs, or names a sidecar that is not a JSON file's plain name. |
| `view.missing` | problem | A package of the kind `cells.run_view@1` holds no `view.json`. |
| `view.format` | problem | A package's `view.json` is not a run view (`cells.run_view@1`), or lacks a part every view gives. |
| `view.time` | problem | A view's time bases are not each an id, an array's name and the files that hold its rows. |
| `view.file-missing` | problem | A file a view's time base names (for itself and its records) is not there. |
| `view.array-file` | problem | A file a view names is not a zip of `.npy` arrays this reader can read. |
| `view.array-missing` | problem | A file a view names does not hold an array the view says is saved there. |
| `view.rows` | problem | A file of a time base does not hold the rows the view gives it. |
| `view.record` | problem | A view's record names no time base of the view, no array, or axes that are not the view's sets. |
| `view.shape` | problem | An array's shape does not fit its record: its time base's rows, then one length for each axis, from the view's sets. |
| `sidecar.name` | problem | A sidecar is not named by its plain file name in its arm's folder (lower-case letters, digits, underscores, hyphens, `.json`). |
| `sidecar.format` | problem | A sidecar is not of a sidecar's format (`cells.experiment_quantity@1`, `cells.experiment_criterion@1`). |
| `sidecar.cells` | problem | A sidecar's cells are not the view's cells, each once. |
| `sidecar.times` | problem | A sidecar has no row at a time the replay steps through: a sidecar is never resampled. |
| `sidecar.listed` | problem | A package's sidecars are not the ones its run's own record lists (`run.json`, `sidecars`): the same names, each once and no other. Their order is the manifest's, the order they are played. |
| `summary.format` | problem | The experiment's summary is not `cells.experiment_summary@1`. |
| `summary.content` | problem | The experiment's summary does not state what a reader of its sweeps reads (the adapter's own reading refuses it). |
| `refused.format` | problem | A `REFUSED.json` does not name its own arm with the status `refused`. |
| `refused.has-view` | problem | A refused pick's folder holds a `view.json`: a refused pick has no view. |
| `refused.sweep` | problem | Refused picks are placed by the one sweep of the experiment's summary, and no summary is named, or it states several sweeps. |
| `refused.parameter` | problem | A `REFUSED.json` gives no finite value of its sweep's parameter. |
| `engine.provenance` | problem | The manifest's engine provenance (revision, snapshot, clean) is not what a run's own view states, or its `run.json` where it has one. |
| `adapter.refused` | problem | The adapter's own reading of the package refuses it, with its reason. |
| `adapter.error` | problem | The adapter's own reading of the package fails on it (an error of the adapter, or input it cannot read). |
| `adapter.machine-path` | problem | The view the adapter would package carries a path of a machine. |
| `check.error` | problem | The check itself failed on the folder: an error of this reader, to be reported with the folder. |

### The schema file, the validator and this contract, kept together

No JSON-schema library is installed, and none is needed: the manifest's fields are one table in the validator
(`MANIFEST` in `tools/check_package.py`), from which it types a manifest and writes the schema file
(`python3 -I tools/check_package.py --schema > schema/experiment_package.schema.json`; the file says so and is not
edited by hand). `tests/check_package.test.mjs` holds that the committed schema file is what the validator writes, that
the table of fields above is the schema's fields and no others, and that the table of codes above is the validator's
codes, with their kinds. The schema file states what a JSON-schema library could check (types, patterns, required
fields); what no schema says (a path that is there, one arm once, a view that fits its arrays) is the validator's.

### The conformance set

`tests/check_package.test.mjs` builds its packages in its own scratch folder from the fixtures tracked under
`tests/engine-views/`: a world the engine's run-view writer wrote, copied as two arms, each with a made-up sidecar and a
made-up record of its run, a made-up refused pick and summary of one sweep, and a manifest. That package, the eight
worlds of `run-view-89bd2ffb` and the windowed loop of `loop-b08af640`, each with a manifest, must pass; each breach
(one thing of a copy broken) must give its own code and no other; a field or a kind the reader does not know, and a
folder it is not given, are notes; the fixture folders without a manifest pass with theirs. A package whose record
lists its sidecars in another order than they are played, names a clean tree by its older key, or is missing for one
arm, and whose manifest gives a short form of the revision, is still sound and needs no note. The same file holds that
the adapter packages a run folder with a manifest to the same bytes as the same folder without one.

## What the adapter reads of a manifest (this round)

Where a run folder holds `experiment_package.json`, the adapter (`tools/adapt_run.py`, `package_manifest`) takes from it
the arms (its packages of the kind `cells.run_view@1`, in its order, in place of `index.json`'s or of the search for
folders that hold a view), each package's sidecars (in place of `index.json`'s and of the overlay's `sidecar`), and the
refused picks (in place of the search for `REFUSED.json`). A package of a kind it does not read is named on its error
output and left out. It refuses a manifest it cannot read so: not `cells.experiment_package@1` at the level `source`, no
packages, a package not read from the folder named as its arm, an arm twice, a sidecar that is not a plain name. Nothing
else of the manifest is read yet: the experiment's words, the summary's name and whether refused picks are shown still
come from the viewer's overlay, and visibility and licence are not yet acted on (the next round). The adapter does not
yet run the validator before it packages. Its own reading stays inside a run's folder all the same: a file name that a
view or `windows.jsonl` gives must not leave the folder (no part made of dots alone, and nowhere led out through a
link), a run folder that holds a link is refused before anything of it is read, and a JSON file or a manifest that is
itself a link is refused. The validator says the same of a whole package, with a code for each.

## What the engine's lead settled (20 November 2026)

The lead read the proposal (`docs/EXPERIMENT_PACKAGE.md`, section 3) and this contract's first text. Everything above
is written to what was settled then.

Kept as this contract had it:

- **Sidecars and a refusal's file are plain names in their arm's folder.** The proposal's rule was "paths relative to
  the manifest", under which its own example named a sidecar at the folder's top. A sidecar belongs to its package, as
  `index.json`'s `sidecar` and the adapter's reading have it; likewise `refused[].file`.
- **A package's `path` is the folder named as its arm, in @1.** The adapter names a run by its folder, so a path that
  differs from its arm would give a run another id; allowing it is a reader's change, for a later version.
- **`index.json`'s `selected` and `within_limit` have no counterpart.** A package that is not to be played is left out
  of `packages` (its folder may stay, and a reader leaves it aside with a note), and a refused pick goes in `refused`.

Changed from the proposal:

- **The manifest is `experiment_package.json`**, named as its format is. The proposal's `package.json` is what a
  JavaScript package's own manifest is called.
- **One id for each source package, and a group.** An experiment's id is the public id. The sweeps of one experiment
  are each a source package with an id of its own, and the optional `experiment.group` gathers them. Arms are unique
  within a package.
- **Sidecars are listed in the order they are played**, and held to the run's own record by their names, not by its
  order.
- **`run.json` stays the run's own record, and is pointed at.** The manifest copies its revision, its snapshot and
  whether the tree was clean, and the validator holds the copies to each view and to each `run.json` there is.
- **`engine.models` is not a field.** Each view states the models its run ran. A manifest that still gives it is
  read all the same: within a major, a reader leaves aside a field it does not know, with a note.
- **The assembly's kind is `cells.assembly_view@1`**, written by its model's own writer.

Left as this contract has it, with no remark from the lead: `experiment.sources[].path` is a reference into the
engine's repository and not a file of the package, so the rule that paths name files inside the folder does not hold
for it. It is held only to carry no path of a machine.

What is now the engine side's to do, and what is the next round's, is in `docs/EXPERIMENT_PACKAGE.md`, section 6.
