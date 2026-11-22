<!-- Generated from lean/claims.json by scripts/generate_claims.py. -->

# A lossless release fate gains all its detached RNA

For a fate row filled by a single release, amount gain equals cumulative detachment less loss. With established zero loss the gain equals the amount detached. The host comparison checks whether the exported fields let the cohort reader recover that surviving amount.

## Assumptions

- One local release feeds the named row. The initial amount is known, the counters start at zero, and all changes to the row are included.
- Zero cumulative loss must be established for that cell and fate. The public reader requires an explicit loss time series.

## Lean proof

**Proved**

- [CellsProofs.Chemistry.TerminalRelease.fate_balance_step](../CellsProofs/Chemistry/TerminalRelease.lean#L58)
- [CellsProofs.Chemistry.TerminalRelease.lossless_gain](../CellsProofs/Chemistry/TerminalRelease.lean#L63)

Direct proof subject `cells.templated_polymerisation@1`

Proof sources [Cells release updates, specialized locally as the exact single-fate balance](https://github.com/Eidosoma/Cells/blob/fc07c545836b155928aeca3e9ba74528d6e3b66d/src/cells/operators/templated_polymerisation.py#L1331-L1353) · [Public reader’s required loss series](https://github.com/Eidosoma/Cells/blob/fc07c545836b155928aeca3e9ba74528d6e3b66d/validation/gene_regulation/cohort.py#L289-L306)

## Numerical comparison

**Failed.** Both fates gained 1.2776562362330652 × 10⁻¹⁰ fmol in each compiled world. The reader recovered three of four fate records. Omitting the short-lived fate’s degradation route removed int_D_R_s from the export. The reader refused the fourth record. Every physical amount balance closed.

**Engine** `resolved_pump_composite@1`, `resolved_pump_tissue@3`

**Operators** `cells.templated_polymerisation@1`

[Compiled window execution](https://github.com/Eidosoma/Cells/blob/fc07c545836b155928aeca3e9ba74528d6e3b66d/src/cells/execution/windows.py) · [R1 and R1S development worlds](https://github.com/Eidosoma/Cells/blob/fc07c545836b155928aeca3e9ba74528d6e3b66d/validation/gene_regulation/worlds.py#L519-L591) · [Observation horizon and grid](https://github.com/Eidosoma/Cells/blob/fc07c545836b155928aeca3e9ba74528d6e3b66d/validation/gene_regulation/kernel.py#L23-L38) · [Compiled history collection](https://github.com/Eidosoma/Cells/blob/fc07c545836b155928aeca3e9ba74528d6e3b66d/validation/gene_regulation/engine_run.py#L169-L181) · [Release route and fate layout](https://github.com/Eidosoma/Cells/blob/fc07c545836b155928aeca3e9ba74528d6e3b66d/src/cells/operators/templated_polymerisation.py#L312-L345) · [Public export of zero losses](https://github.com/Eidosoma/Cells/blob/fc07c545836b155928aeca3e9ba74528d6e3b66d/validation/gene_regulation/engine_run.py#L262-L313) · [Detachment counters for each fate](https://github.com/Eidosoma/Cells/blob/fc07c545836b155928aeca3e9ba74528d6e3b66d/validation/gene_regulation/engine_run.py#L393-L411) · [Local producer resolution and loss-counter requirement](https://github.com/Eidosoma/Cells/blob/fc07c545836b155928aeca3e9ba74528d6e3b66d/validation/gene_regulation/cohort.py#L240-L308) · [Survivor calculation](https://github.com/Eidosoma/Cells/blob/fc07c545836b155928aeca3e9ba74528d6e3b66d/validation/gene_regulation/cohort.py#L142-L162) · [Exact single-fate balance](https://github.com/Eidosoma/Cells/blob/f11bfae57c7d3db1ac632b313cdb05dd863063de/lean/CellsProofs/Chemistry/TerminalRelease.lean) · [Comparison driver](https://github.com/Eidosoma/Cells/blob/f11bfae57c7d3db1ac632b313cdb05dd863063de/lean/checks/terminal_release.py) · [Recorded result](https://github.com/Eidosoma/Cells/blob/f11bfae57c7d3db1ac632b313cdb05dd863063de/lean/PROGRESS.md#fr38-lossless-fate)

[Tested engine fc07c545836b](https://github.com/Eidosoma/Cells/commit/fc07c545836b155928aeca3e9ba74528d6e3b66d) · [Evidence checkpoint f11bfae57c7d](https://github.com/Eidosoma/Cells/commit/f11bfae57c7d3db1ac632b313cdb05dd863063de)

## Biological evidence

**Open.** Absolute gain of a separately tracked RNA fate, with an independent count of its detachments and losses over the same interval.

**Unit** fmol of released RNA

[Claim index](../README.md#proof-index) · [Editable register](../claims.json)
