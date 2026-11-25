# The ensemble's re-expression: the builder's side (Part 1)

This folder makes the definitions, the runs and the tables that `spec/` registers (tag `ensemble-reexpression-criteria-part1-2026-11-25`).
It judges nothing. Its builder read `spec/SPEC.md`, `spec/READOUTS.md`, `spec/TABLE.md`, `spec/inputs.json`, the rules of `spec/README.md`, and the engine with its documents.
From 25 November also `spec/AMENDMENT-1-2026-11-25.md`, which holds what the lead answered ("Amendment 1" below), and the exporter's copy of Amendment 2 (its items 2, 4, 7, 8, 9.1 and 10; "Amendment 2" below).
The builder read no other file of `spec/`, no capture, no legacy output and no code of the judge.

No registered world has been run by the builder. The run driver refuses to run one from a checkout.

## Files

| File | What it does |
| --- | --- |
| `labels.py` | The spec's labels and the registered strings they stand for, from the engine's own constants. The strings that a definition declares |
| `inputs.py` | Reads `inputs.json` (and `inputs_rehearsal.json`): worlds, runs, retries, compared times, the grid rule |
| `worlds.py` | A block and the engine's definition of it, each written from the other, section by section. The echo's comparison |
| `definitions.py` | Every run's definition and its checks (`check`, `write`, `strings`) |
| `run.py` | The run driver: one command makes one run and its record |
| `refusals.py` | What the engine raised, as a kind of refusal. The rows that a refused run keeps |
| `readouts.py` | The series and potentials of READOUTS §2, read from a run's own rows |
| `table.py` | The exporter (`export`) and the contract's keys and types (`check`) |
| `sample.py`, `format_sample/` | The invented worlds of the format sample, how it is made, and the sample itself |

The rows are `tests/unit/test_ensemble_reexpression.py` (parse only and fabricated records).

## How to use it

From the registered head, in the checkout (parse and validate only, about 40 s):

    python -m validation.ensemble_reexpression.definitions check
    python -m validation.ensemble_reexpression.definitions strings

The campaign, from a frozen snapshot, by whoever starts it:

    python -m validation.ensemble_reexpression.run snapshot SNAPSHOT        # in the clean checkout of the registration tag
    cd SNAPSHOT
    python -m validation.ensemble_reexpression.run all --runs RUNS --tag TAG --workers 4     # or, one unit for each run:
    python -m validation.ensemble_reexpression.run commands --runs RUNS --tag TAG --cpus 6,7,22,23
    python -m validation.ensemble_reexpression.run status --runs RUNS
    python -m validation.ensemble_reexpression.table export --runs RUNS --output RUNS/table
    python -m validation.ensemble_reexpression.table check RUNS/table --strings registered_strings.json

With `PYTHONPATH=SNAPSHOT/src:SNAPSHOT`, `JAX_ENABLE_X64=1` and `JAX_PLATFORMS=cpu`. `all` goes through `scripts/run_detached.sh` like any long job. It makes the runs that have no record, so it is started again after an
interruption and goes on. `commands` prints one `run_detached.sh` command for each run. `one NAME` makes one run in the foreground. The retry, when the judge owes one, is `--owed retry_owed.json` on `all`, `commands`, `status` and
`export` (into `RUNS/table-retry`).

- **Each run is its own process** with a cold compile (no compilation cache, one BLAS thread). Measured on the sample's worlds, on four shared and loaded CPUs under `nice`: 85 to 92 s to compile an RK4 world, under a second to run ten steps, 1.1 GB at the peak.
  So the 204 ionic runs are some hours of one CPU (an estimate: no registered step count was run).
- **What needs what:** a restart needs its judged run's record, and `all` makes the restarts last. A driven run needs its composed file's resolution, which the first run that needs it makes under a lock (`RUNS/resolutions`). Nothing else needs anything.
- **A run's folder** is `RUNS/runs/<name>/`: `RUN.json` (its record, written last) and `attempt-N/` with `submitted.json` (what was submitted), `parsed.json` (what the engine parsed), `output/` (the engine's own record, or the pools'), `partial.npz` (a
  refused run's rows), `outcome.json` and `worker.log`. The record holds the run's name, the registered entry, the inputs file's sha256, the source, the fingerprints, the timings and the sha256 of every file of the attempt.
- **Guards.** A run whose name does not begin with `inv_` is made only from a clean, complete frozen snapshot whose revision is the registration tag that the caller names, and from that snapshot's own `inputs.json`. Records stand outside the tree they are made from.
- **Off the grid.** A declared time that is no grid point of the run's step is refused by name (`off_grid_change`, kind `harness`) before anything runs. `one NAME --off-grid` makes that one run all the same, and the flag stands in its record and, as the extra key `off_grid`, in its table entry, where no key means off (Amendment 1). The table then shows it as it is: more steps than its grid. A registered run made with the flag is refused (`harness`), by the driver and by the exporter.

## The definitions

- **An ionic world** is a closed world of the inner tissue model, version 3, with no registry, kind, operator, label, reservoir or electrode. Every number in it is the block's own double. `definitions check` parses and validates every run's definition (as `cells validate` does), reads its block back, and compares leaf by leaf: by SPEC §2.4's rule, and by
  the doubles too, but for the derived `initial_voltage_V`. It compares each registered block with the literal one of SPEC §2.5.
- **A driven world** is a composed file for `cells assembly-pool resolve`. Its ionic part declares the channel at 1 throughout, and the pool's path multiplies that. An ionic run's schedule comes from the resolution of its own composed file's pools (Amendment 1). The ionic runs of one seed and step have one composed file, and so one resolution.
- **A pool run** submits its world's composed file at the first step and runs the file's pools with the function that `resolve` uses, so `channel` and `stream_id` are read back from that file (Amendment 1).
- **The field solver** is D147's (`validation/tissue/field_solver_choice.py`). The count of free offsets is made on the floor variant, which parses every world, and `declare()` has the last word. `check` holds the count to the block's own topology.
- **Part 2** adds sections to `worlds.SECTIONS`, labels to `labels.LABELS` (and their place in the strings note to `labels.PLACES`), and series to `readouts.SERIES` and `readouts.POTENTIALS`. Nothing else names a section, a label or a series. A key of a block that no section holds is refused by name
  (`no_section`), and so is a field of an entity that has no place.

**What the 214 runs parse to** (measured, `definitions check`, no fault): 10 ionic definitions for the 11 ionic runs (a restart has its judged run's); 25 composed files, of whose world definitions 193 are run; 15 pools in the 10 pool runs.

## The strings, for the lead's note

`definitions strings` prints each run's entry. `labels.LABELS` is the map, from the engine's constants, so the ID move rewrites no literal here.

| Runs | `model` | `solver` | `field_solver` | `laws` | `pool` | `observable` |
| --- | --- | --- | --- | --- | --- | --- |
| `jupiter` (8) | `inner_model` | `rk4` | `field_solver_floor` | `closure`, `constant_field`, `junction_relaxation`, `kv15_mh`, `logmean_face`, `maintained_fuel`, `nak_pump_positive` | | null |
| `integrated` (3) | `inner_model` | `rk4` | `field_solver` | `closure`, `constant_field`, `junction_relaxation` | | null |
| `cell` ionic (96) | `inner_model` | `rk4` | `field_solver` | `closure`, `constant_field`, `kv15_mh`, `maintained_fuel`, `nak_pump_positive` | | `assembly_observable` |
| `base` ionic (97) | `inner_model` | `rk4` | `field_solver_floor` | as `jupiter` | | `assembly_observable` |
| Pool runs (10) | `pool_model` | null | null | | `pool_model`, `pool_topology` | `assembly_observable` |

- **No run declares an operator or a kind.** The retry's runs declare their family's strings.
- **The closure and the fuel stand among `laws`:** the note has no word of their own for them, and `kinds` holds declared kinds.
- **The rehearsal's IMEX family** declares the label `imex` in place of `rk4` (Amendment 1).
- **What counts as declared:** every string of the form `name@version` that the parsed definition holds, as a value or a key, and the execution's solver, which has no version today. For a driven run, the observable of its composed file's pools too. For a pool run, its pools' own definitions and their observable, and nothing of the ionic definition (Amendment 1).

## The kinds of refusal (TABLE §4)

| What was raised | Kind |
| --- | --- |
| `NumericalError` of the engine's ledgers ("Resolved pump accounting failed: ..."), of its dissipation, or of its step-doubled energy check; a pool whose finite material or transfer counters do not balance | `check` |
| Any other `NumericalError` (a step's or a row's domain) | `domain` |
| `ConfigError` or `AssemblyError` that says "domain", "RK4 steps", "step exceeds", "must lie in", "must be in [", "cannot exceed", "must be finite and positive" or "nonnegative", "exceeds positive finite" or "reached its event cap" | `domain` |
| The junction gate's message, which names a law and a range together, where the declared law is the one it names | `domain` |
| Any other `ConfigError` or `AssemblyError`; a `KeyError`, `TypeError`, `AttributeError` or `IndexError` of the parser | `definition` |
| Anything else: memory, the disk, a signal, the driver's own clock (`--max-seconds`), the generator (`no_section`, `unknown_order`, `off_grid_change`), the exporter | `harness` |

- **The message is the engine's**, as raised.
- **`time_s` of a `check`.** The scalar runner keeps no row of a run that it refuses. So the driver runs the same definition again in windows of one step, by the engine's windowed path, keeps every row that it accepts (`partial.npz`), and takes the time of the first row that it refuses. These are the rows of the run's entry: another path of the engine's than the refused run's. If that pass itself fails, the engine's own refusal stands without rows, a `check`'s time is the end of the run, and the record says what failed. The record says whose rows they are (`second_pass`: the windows' length, the file, whether the pass completed) and holds the sha256 of that file among those of the attempt (`files_sha256`), which the exporter checks. If that pass completes, or for a pool, which has no rows, the time is the end of the run. Where it completes, the refusal also holds `second_pass_completed: true`, in the record and in the table entry (absent otherwise; Amendment 2, item 8).
- **A refused run at run time** keeps its rows at the compared times that it reached, and `steps` counts the accepted steps before it.

## The readings taken

Each is this builder's, with the sentence it rests on. What the lead answered is said so.

1. **Observation times are the potentials' times, and no other** (SPEC §3.1: "They include every time of `potential_times_s`"; TABLE §3 `potential_t`). For `cell` and `base` they are 0 and then `summary_times_s`.
2. **The record keeps every accepted row; the table holds the compared ones** (SPEC §3.1 "Every accepted row is recorded"; TABLE §3 `t`: "every compared time there", "Extra rows are allowed"). A table's `t` is the run's own doubles.
3. **Steps and times are `inputs.json`'s decimals.** A retry's step is the decimal of its name, and it must be half of its family's finest step (SPEC §3.1's table and §4's "by rule").
4. **A pump's ID** is `pump_<membrane>`: the block keys a pump by its membrane, and SPEC §2.5 says the pump's own ID is lost.
5. **A channel's relative permeability** is its law's own for that species, which is 1 for K (SPEC §2.1). Its gate vector is in the law's order, m then h.
6. **Levels:** the coupling's `active` is the level of the observable's true value and `inactive` that of its false one (SPEC §3.2, "1 if the number of set bits ...").
7. **A pool's harness** is the block's, but `recording` is "events" (SPEC §2.4: "since a candidate's pool run records events").
8. **A pool restart** is a first leg of the same definition and seed to the checkpoint's time, the checkpoint through a file, and a second leg to the end (Amendment 1; the live pool writes a checkpoint only at the end of a leg). Both legs are run by the two functions that `resolve` runs a pool with. The first leg is in the support run's own record (`first_legs`: the command it equals, its checkpoint, the sha256 of its files) and in no table entry. `step_index` is null (Amendment 1).
9. **`stream_id`** is the pool's position in the composed file, the first 0 (Amendment 1). **A pool's cell**, for `pool`, `path`, `inputs` and `pool_seeds`, is the cell of that position among the cells that have a channel, in the definition's order. So the swapped plant's seeds are its honest run's (Amendment 1).
10. **EP1 and EP2** are what the lead told: both channels' maximal permeability times 1.01; the two pools' channels exchanged. In the rehearsal a run's entry may carry `declared_change`, a list whose items are `{"path": [...], "value": ...}`, with the path inside the world's ionic block (`worlds.<w>.ionic`; its first key is for example `channels`, and the path must exist there), or `{"exchange_channels": [cell, cell]}`.
11. **`p` = 4 is RK4 and `p` = 2 is ARS(2,2,2)**; any other is refused by the generator, by name (`unknown_order`), with kind `harness` (Amendment 1).
12. **A route's series exist in a world that has the route** (READOUTS §2: "A series absent from a world counts as zero"). A leak exists where some membrane has a nonzero permeability, which is why `integrated` has none. A pump's series hold every membrane of a world that has a pump, with zeros for one that has none.
13. **`phi_out`** is written for every region but the gauge, in `base` too, where it has no captured counterpart (READOUTS §2: "no captured `phi_out`").
14. **`composed_file_fingerprint`** is the sha256 of the composed file's bytes, which a checker forms with `sha256sum` (TABLE §3: "The checker recomputes it from the composed file").
15. **A restart's potentials** are those after the checkpoint, strictly (TABLE §3: "For a restart, the ones after the checkpoint"). Its row at the checkpoint's time is written (SPEC §4: optional).
16. **`restart.through`** is the string "file". **`source.snapshot`** of a run from a checkout is "none". The `source` of a run whose worker was ended before it could say is the driver's own process's (`source_from` in the record).
17. **`pending_valid`** is written as JSON booleans, as the array is. Every mask is an integer.
18. **`switch_list`** leaves out the entry [0, 1], and holds every channel of the world, an empty list for one without a change (TABLE §3: "may be written or left out"; Amendment 2, 9.1). A pool's `path` holds every world of the pool, an empty list for one without an event. `controls.channel` holds every channel, as the engine's definition does.
19. **An extra field of a definition** that the block has no name for is read back under its own name (TABLE §3: extra keys are recorded), so nothing declared is hidden.
20. **A definition that the engine refuses to parse** has no count of free offsets. Its field solver is declared by the block's own topology: the floor variant where a capacitor component is without the gauge.
21. **`checks`** is the engine's `summary.json`, or each pool's `result.json`. `definition` is the engine's canonical form, and for a driven run also what the run recorded of its composed file.

## The rehearsal (SPEC §8)

The exporter and the generator read `inputs_rehearsal.json` with the code that reads `inputs.json`. Nothing of them names a registered world, consumer, run or number, but the registered plants' changes (EP1, EP2) and the check against SPEC §2.5's literals, which is made for the registered file alone.

    python -m validation.ensemble_reexpression.definitions check --inputs validation/ensemble_reexpression/rehearsal/inputs_rehearsal.json
    python -m validation.ensemble_reexpression.run all --inputs .../inputs_rehearsal.json --runs REHEARSAL
    python -m validation.ensemble_reexpression.table export --inputs .../inputs_rehearsal.json --runs REHEARSAL --output REHEARSAL/table-rehearsal

- **Names:** worlds and runs begin with `inv_`, so a checkout may make them. A run's `world`, `family`, `seed_index`, `world_id`, `step_s`, `role` and `variant` are read as in `inputs.json`. A restart is named `<judged run> restart` with the variant `restart at <s>` or `pool restart at <s>`.
- **What each listed item needs:**
  - the cluster at the bound, the assembly worlds, the gated cluster, the large amounts with the rounded fixed charge, the default written out, the change one unit off its k h: their blocks, and nothing else. The check takes a fixed charge as it is declared;
  - the IMEX family: `p` = 2 in its world's block;
  - a plant: `declared_change` in its run's entry (reading 10);
  - a refusal of kind `definition`: a block with a law that the engine does not have (an unknown label passes through as it is). `domain`: a value outside a law's domain, such as a temperature of 150 K. `check`: a world whose steps the engine's own energy check stops. `harness`: `one NAME --max-seconds 0.05`;
  - the off-grid change: `one NAME --off-grid`. Without the switch it gets a record that refuses it, and so does `all`. So this run and the `harness` one are made first, by name, or again with `--again`;
  - the strings note: `table check ... --strings registered_strings_rehearsal.json` holds every run's strings to it.
- **The faulty tables that the judge's reader needs** beside these are not made here: this code writes what a run did.

## The format sample (TABLE §7)

`format_sample/` holds the tables of `sample.py`'s invented worlds with every number replaced. `format_sample/README.md` lists every key and type. It is made again with:

    python -m validation.ensemble_reexpression.sample make RUNS
    python -m validation.ensemble_reexpression.sample scrub RUNS validation/ensemble_reexpression/format_sample
