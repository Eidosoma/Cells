# Labelled protein inside a region, outside it and in the whole cell (FR-33's study note)

A study asks whether a synaptic protein's 48-hour decline is redistribution or degradation (FR-33;
D248, D251). This note names the Cells fields for its three quantities, states its two predictions
in those fields, and lists what the study needs to freeze them before fresh data are scored. It
builds on the FR-7 lane's maintained example, `validation/compartment_transfer/` (60cf2364), whose
README names the donor, receiver and loss fields and whose control holds exactly.

## The regions in Cells

- **A region is a set of nodes.** A synapse or an imaged patch of dendrite is a compartment of its
  cell (`cell_owned_compartments@1`): a finite outside node bounded by one patch, with the cell as
  its owner. The cell's cytosol is one well-mixed node.
- **The study declares its measured region** as a list of those nodes. Cells holds no region
  declaration of its own, so the list lives in the study's analysis.
- **The labelled protein is its own species row**, a neutral inventory species
  (`cells.registry.inventory_species`). A pulse label is a second row beside the unlabelled one, with
  the same laws declared on both.

## The three quantities, and the movements between them

Amounts are levels, in fmol. The loss and transfer records are cumulative from t = 0, in fmol. All are
read at each output row, as the example's `exports()` reads them.

| Quantity | Field | Index |
| --- | --- | --- |
| Inside the region | Σ over the region's nodes: `extracellular_amount_reference` + `extracellular_amount_increment` | [species, outside node] |
| Outside it | the cytosol, `amount_reference` + `amount_increment` [species, cell], plus the cell's other compartments | as above |
| Whole cell | inside + outside: the cell and every compartment it owns. The owner of each node is in the `cell_owned_compartments@1` declaration | |
| Loss by turnover (degradation) | `turnover_outside_cleared_fmol` at a compartment; `turnover_cleared_fmol` in the cytosol | [species, outside node]; [species, cell] |
| Loss by a reaction | `reaction_outside_consumed_fmol`; `reaction_consumed_fmol` (`local_species_reactions@1`) | the same |
| Transfer between a compartment and the cytosol | `exchange_moved_fmol`, export positive (cell to node). The route names the patch, and so the node | [route] |
| Transfer on a face or junction | @3's `face_transferred` and `junction_transferred`, signed sender to receiver | [species, face]; [species, junction] |
| New labelled material, if labelling continues | `turnover_produced_fmol` | [species, cell] |

Each loss and transfer record names its node or route. So Cells always says where material was
lost and which route moved it.

## The two predictions, in those fields

- **Redistribution:**
  - the whole-cell total stays constant, to rounding;
  - the losses at the region's nodes stay 0;
  - the region's decrease equals the transfers out of it.
- **Degradation:**
  - the whole-cell total falls by the cumulative losses;
  - the transfers out of the region stay 0;
  - the region's decrease equals the losses at its nodes.
- **A mix:** Cells splits the region's decrease into transfer and loss, since both records are kept.

The example's two arms are these predictions in their pure forms. The donors fade identically, the
receiver rises only under transfer, and the cumulative loss only under destruction.

## What the study needs to freeze both predictions

1. **The region's node list**, and which compartment stands for which synapse or imaged patch.
2. **One export per output row** of inside, outside, whole cell, cumulative loss per node and
   cumulative transfer per route, read together. `validation/regions/readouts.py` (`region_rows`)
   gives it for any region of one cell's nodes, with each node's amount beside it, and with no
   engine change. It refuses, at setup, a world in which anything it does not read could move the
   species: a face, junction or patch that moves it, every operator law it neither reads nor
   lists as shown inert, and every declared kind (`check_movers`, fail closed since the review of
   21 November 2026).
3. **Every other way out of the cell, named.** Secretion to a node the cell does not own also lowers
   the whole-cell total. Cells books it as a transfer (`exchange_moved_fmol` to that node), not as a
   loss, so the two stay apart, which imaging alone cannot do.

**Fields that do not exist:**
- **A population within one species row.** A labelled cohort, such as protein made before a pulse,
  or an age class has no field. A cohort is declared as its own species row today, which works
  while every law that acts on it is age-independent and first order. Under age-selective loss, no
  field names which population lost material. `docs/COHORT_LABELS_DESIGN.md` gives the engine work.
- **A declared region.** The study's region exists only in its analysis. A named set of nodes in the
  run view would make the export self-describing. It is not needed to freeze the predictions.

**Two limits to state with the predictions:**
- **The cytosol is one well-mixed node,** so redistribution along a dendrite is represented only
  between compartments, through the cytosol. Each synapse is its own compartment, and two exchange
  routes take the protein from one to another. Cells has no route from one compartment directly to
  another, and no motor-driven transport law.
- **Photobleaching has no engine counterpart.** An imaging loss that is not the protein's fate is
  the study's correction, made before scoring.
