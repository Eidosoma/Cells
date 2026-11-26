# FR-43 part 3's co-writers registration: the builder's tools

The registration is `docs/FR43_PART3_COWRITERS_PROTOCOL.md` with the spec folder `spec/` (tag
`fr43-part3-cowriters-criteria-2026-11-25`). The builder writes the engine side (the protocol's §5): the world
builders, the run driver and its records, the exporter of the engine table (`spec/TABLE.md`), the Lie patch and the
format sample. It reads `spec/` and its own code. It does not read the references' values or any judge's code.

| File | What it does |
| --- | --- |
| `worlds.py` | Each run's composite definition from an inputs file of the spec's layout, with `check_world` for SPEC.md §1's structure: one cell, one finite node, one patch with one site, no face, junction, channel or pump, and every patch's permeability zero |
| `run.py` | One run per process, cold: the windowed run with every host check, the restart through snapshot files, the Lie plant under its patch, the record (TABLE.md §3's entry); the launcher; `parse`, every definition parsed and its echo compared with the inputs, with nothing compiled |
| `lie.py` | The Lie plant's host patch (P3): the composite's second halves in declared order |
| `table.py` | The engine table from the records alone: `table/` and, for owed families, `table-retry/`, each with its SHA256SUMS |
| `sample.py` | The format sample (TABLE.md §5): its runs, the scrub, and its README's key list |

## The operators, in declared order

The rehearsal compares `operators` with this list (CRITERIA.md §4.1), in place of the strings note. All run in
`cells.model.resolved_pump_composite@1` over `cells.model.resolved_pump_tissue@3`.

| Family | `operators` |
| --- | --- |
| `W5 reactions-first`, `W5-exact reactions-first` | `cells.operator.local_species_reactions@1`, `cells.operator.integer_unit_population@1` |
| `W5 population-first`, `W5-exact population-first` | `cells.operator.integer_unit_population@1`, `cells.operator.local_species_reactions@1` |
| `W6 gene-first` | `cells.operator.templated_polymerisation@1`, `cells.operator.integer_unit_population@1` |
| `W6 population-first` | `cells.operator.integer_unit_population@1`, `cells.operator.templated_polymerisation@1` |

## Where each readout comes from (TABLE.md §3)

- **A row** is the engine's amount at the sample: its reference plus its increment, at `cell_0` or `ecs_0`.
- **The books** are the writers' own accumulators, each read once at the sample, never a difference of rows:
  - `xi_1` and `xi_2` are the reactions' extents (`reaction_extent_fmol`) of the routes of `make` and `spend` at the
    cell;
  - `moved` is the population's transfer (`integer_transferred_fmol`, cell to node positive);
  - the gene unit's `inits` (`poly_initiated_fmol`), `exits` (`poly_stage_exits_fmol`, every stage), `made`
    (`poly_released_fmol`, the finished chains) and `lost` (`poly_degraded_fmol`), and `free`
    (`poly_free_machines_fmol`);
  - `engaged` = Σ_j C_j and `transit` = r Σ_j (j − 1) C_j, summed in stage order over `poly_complexes_fmol`.
- **The events** come from the population's trace: its clock's times, the declared channel IDs and its pools at each
  event (`pools_at_event`).
- **`integer_ledger`** is Σ_k w_k n_k from the engine's `integer_counts` at each sample.
- **`counts_after`.** On this head the exporter forms it by applying each listed channel's declared jump to the
  engine's own counts, starting at t = 0 or at the checkpoint. It checks the result against the engine's
  `integer_counts` at every sample. A mismatch is a `harness` refusal.
  - The user chose (1) instead: the engine records the counts (branch `fr43-trace-counts`, its own landing).
  - Once (1) lands, the exporter copies `integer_trace_counts` and derives nothing.
- **`inputs`** is read back from the definition the engine parsed (its `to_dict`), with exactly `echo`'s keys:
  - `copy` comes from the site's ID (`site_c<copy>`);
  - `first` comes from the operators' declared order;
  - `rate_unit` comes from the reaction's order (mass action's k in mM^(1−q)/s);
  - the degradation's `monomers` is the declared count per residue times `residues`;
  - `initiation_per_mM_s` and `rate_per_s` are the gene unit's constant schedules;
  - a read's `at` is the operator's `cell` or `outside`, written `cell` or `node`.
- **`checks`** holds the windows' diagnostics (the engine's checks of every row), the composite's ledgers at the last
  row, and the counts' check.

## The kinds of refusal (for the checker)

From what the engine raised and where (`run.kind_of`):

| Kind | What was raised |
| --- | --- |
| `domain` | A ConfigError while the definition is parsed, built or planned, before the first step, whose message states a bound or a range that a declared value left (`run.OUT_OF_RANGE`: a comparison with a number, "at least", "at most", "positive", "non-negative", "finite", "outside", "exceeds", "domain", "above", "below", a near miss). Also, at run time, a step the engine refused: a NumericalError raised outside the row checks, the runner's trial or endpoint domain failure, whose time is the refused step's start |
| `definition` | Any other error while the definition is parsed, built or planned: a ConfigError, or the parser's KeyError, TypeError, ValueError, IndexError or AttributeError |
| `check` | A NumericalError raised by the model's host checks of accepted rows (`check_values`: their domain, ledgers and dissipation), or a ConfigError of the windows' diagnostics |
| `harness` | Anything else: the driver, the export, a truncated trace (`events_total` above `trace_capacity`), the counts' check. A crash leaves no record, and its run is listed in `missing` |

## The restart, the Lie plant and the windows

- **Windows.** A run's window is the gcd of its samples' steps, the restart's checkpoint included, so every sample and
  the checkpoint end a window.
- **The restart** runs the uninterrupted run to the registered checkpoint. It writes the checkpoint with
  `cells.records.io.write_snapshot`, reads it back with `load_snapshot`, and resumes in the same process.
  - Its record lists the samples at and after the checkpoint (the resumed part's rows) and the events after it.
  - `first_index` is the checkpoint's `integer_events`.
- **The Lie plant** is `lie.second_halves_in_declared_order()`. It binds `cells.models.pump_composite`'s name
  `reversed` to the given order, in the plant's process only. It refuses unless that name's one use is
  `Composition.split_step`'s `for op in reversed(splits)`.
  - Its definition, inputs and operators are its honest run's.
  - `host_patch` is `{"id": "second_halves_declared_order", "change": ...}`.

## The invented inputs (format sample and rehearsal)

The references' two invented files, read with `git show fr43-part3-cowriters-references-2026-11-25:<path>` (4eb797ba)
at the lead's word of 26 November 2026. Nothing else of `references/` is read.

| File | sha256 (the lead's record) |
| --- | --- |
| `validation/fr43_part3_cowriters/references/out/inputs_invented.json` | `db3da0be6c12fe88827706c18da3d8652b91fb66b19521a044480680221f6dd6` |
| `validation/fr43_part3_cowriters/references/out/draws_invented.json` | `0c98fdccc0b0009572d1dada25c8569c475c2cbe4b098f472942f6837f20eb5a` |

## What the build checked (26 November 2026, development runs, nothing judged)

- **`run.py parse`** on `spec/inputs.json`: all 250 registered runs and the 32 retry runs that CRITERIA.md §7's rule
  names parse, none refused. Each echo equals the inputs by CRITERIA.md §4.1's comparison.
  - The engine's own dt a₀,max at the coarsest step is the placement's: W5-exact 0.082 and W6 0.703. W5's site is
    unchecked, since S has no static bound.
  - The same on the invented inputs: 131 of 132 parse, and the invented `refused` run is refused (kind `domain`).
- **The invented smoke** (18 runs from the checkout, its three fault runs included) shows the book mapping is right:
  - READOUTS.md §4's identities hold within 0.0025 of their 16 (S + 1) u s_id bound in every run, and the start
    values are exact.
  - W5-exact's event times equal LAWS.md §4's sums over the invented draws within 0.0007 of their bound.
  - Both restarts equal their uninterrupted runs bit for bit, in rows, books, events and ledger.
  - The Lie plant's events differ from its honest run's while its identities hold.
  - The invented `stopped` run stops at a refused step (kind `domain`).
