# Arrival-time labels on a substance (`cells.operator.neutral_arrival_labels@1`)

**In one sentence:** It follows when material of one substance arrived, by keeping each pool's shares of older and newer material, without changing how the substance behaves.

## In plain words

A pulse-chase experiment marks what is made during a window and follows it. This
[operator](../../GLOSSARY.md#operator) does that without a second chemical species. Each labelled
substance stays one [species row](../../GLOSSARY.md#species-row), and the operator keeps, at every
cell and [finite node](../../GLOSSARY.md#finite-node), the shares of it that arrived in each window.
No law reads the shares, so labelling never changes the dynamics, the energy or a physical record.
Each process that moves the substance reports its one-way moves, and the shares follow them. At
events, a replaced cell's material takes the label in force, and a wash removes every label in
proportion while its fresh buffer joins the unlabelled base. Surface sites that bind only unlabelled
substances may sit beside it. Left out: movers that do not report, such as charged faces, channels
and pumps, sites binding a labelled substance, and an exchange of a cell's own liquid.

## Seen from each field

- **Biology:** a pulse-chase or tracer label, followed as cohorts of one molecule kind.
- **Chemistry:** isotope-free bookkeeping: material is split by arrival time, and every label
  carries the same chemical potential.
- **Physics:** a passive scalar carried on the material's flows, with no free energy of its own.
- **Computing:** shares advanced from each reporter's one-way moves and each event's typed
  report; no part of its own, and zero-size records where no event of their kind is declared.

## At a glance

<!-- generated: at-a-glance -->

| | |
| --- | --- |
| Piece | Operator, interface `cells.operator@1` ([its fields](../../DECLARATIONS_FORMAT.md#operators)) |
| ID | `cells.operator.neutral_arrival_labels@1`; definitions write `cells.operator.neutral_arrival_labels@1` |
| Runs in | `cells.model.resolved_pump_composite@1`, its host. Definitions of `cells.model.resolved_pump_composite@1` can declare it |
| Where it acts in the step | No part of its own; scheduled by `label_arrivals` |
| Needs | No law or kind |
| Provenance | Not yet extracted: the composite's operator contract has no provenance field yet |

<!-- /generated -->

## What it reads and changes

<!-- generated: touches -->

| Field | Role | Axes | Unit | Which way is positive |
| --- | --- | --- | --- | --- |
| `label_share` | Owns | label_species, label_slot, cell_slot | 1 | Not stated |
| `label_outside_share` | Owns | label_species, label_slot, extracellular_slot | 1 | Not stated |
| `label_closure_relative` | Owns | label_species | 1 | Not stated |
| `label_pool_share` | Owns | label_pool_owner, label_slot, label_pool | 1 | Not stated |
| `label_removed_fmol` | Owns | label_removed_species, label_slot, cell_slot | fmol | Not stated |
| `label_pool_removed_fmol` | Owns | label_removed_pool_owner, label_slot, label_pool | fmol | Not stated |
| `label_outside_removed_fmol` | Owns | label_outside_removed_species, label_slot, extracellular_slot | fmol | Not stated |
| `label_arrival` | Controls | | Not stated | |
| `label_source_arrival` | Controls | | Not stated | |

Writes into other pieces' fields: none. Ledgers: none. Records: `label_share` (level), `label_outside_share` (level), `label_closure_relative` (level), `label_pool_share` (level), `label_removed_fmol` (cumulative), `label_pool_removed_fmol` (cumulative) and `label_outside_removed_fmol` (cumulative).

<!-- /generated -->

## The mathematics

<!-- generated: bounds -->

None declared.

<!-- /generated -->

Each labelled row at each node holds shares $s_k$ (1), $\sum_k s_k = 1$, with $k = 0$ the base.
The row's amount $n$ (fmol) is the engine's own.

**Over a reporter's application** of length $h$ (s), with one-way loss $\text{out}$ and gains
$\text{into}_k$ (fmol), $u \ge 0$ is solved from the engine's $n_0$, $n_1$ and
$I = \sum_k \text{into}_k$:

$$n_1 = n_0\,e^{-u} + I\,\phi(u), \qquad \phi(u) = \frac{1 - e^{-u}}{u}, \qquad x_k = n_0\,s_k\,e^{-u} + \text{into}_k\,\phi(u), \qquad s_k' = \frac{x_k}{\sum_j x_j}$$

- **This is exact** for a constant per-molecule loss rate with constant arrivals.
- **Otherwise it is second order,** as Strang splitting is.
- **Without arrivals** the shares are kept bit for bit.

**Transport between nodes** carries each source's shares to its destination. It uses a
predictor and a corrector, so it is second order in the step.

**At an event:**
- a replaced slot takes the label in force;
- an emptied pool takes the base;
- a liquid exchange, with sample $r$ and supply $a$ (fmol) at an outside node, gives

$$x_k = (n - r)\,s_k + a\,[k = 0], \qquad s_k' = \frac{x_k}{\sum_j x_j}$$

  - It is exact in the amounts it is given. At a whole wash, $r = n$, so every other share is
    exactly 0.
  - The buffer carries no label, so it joins the base even while a window is open. A replaced
    slot instead takes the label in force.
  - The report's axis is the outside nodes, so an exchange of a cell's own liquid cannot be
    expressed in version 1.

**What left** at each event is recorded by label, cumulative from $t = 0$ (fmol): the amount
before the event times the shares just before it.

**Refused, never repaired:** a labelled row moved by a mover that does not report, and an event
whose report kind is missing or contradicts its declarations.

## Sources

<!-- generated: provenance -->

Provenance: not yet extracted; the composite's operator contract has no provenance field yet.

<!-- /generated -->

- **The update for a constant per-molecule loss with constant arrivals** (Der): it was derived for
  this piece, as were its second-order error, the transport's predictor-corrector and the
  exchange map.

## How it is checked

<!-- generated: tests -->

Declared test: not yet extracted; the composite's operator contract has no test field yet.

<!-- /generated -->

- **The update alone:**
  - it is held against the exact solution for a constant rate;
  - its domain is tested on random and extreme inputs;
  - its order is measured under step halving.
- **The exchange map** is held to its identity on six cases. Two planted errors must fail: the
  continuous update used for a wash, and the buffer not credited to the base.
- **A wash and a replacement in one step** commute, in either declared order, bit for bit.
- **Surface sites beside labels:** every pairing not yet qualified is refused by name. A compiled
  run of sites with four partners keeps every physical record of its unlabelled twin bit for bit,
  and its labels follow each partner exactly.
- **Compiled runs** keep every physical record of their unlabelled twins bit for bit:
  - the dN/dt = −N² reference, a window's cohort against its analytic solution, a replacement's
    record by label, and labels across five washes;
  - a labelled run resumes bit for bit, through a snapshot and across a wash, where planted redo
    and skip errors are caught.

## Status

<!-- generated: status -->

Not stated: no record states a level for this piece.

<!-- /generated -->

## Links

<!-- generated: links -->

- Declared in [`src/cells/operators/species_labels.py`](../../../../src/cells/operators/species_labels.py), class `NeutralArrivalLabels` (`cells.operators.species_labels`).
- Runs in `cells.model.resolved_pump_composite@1`.
- Manifest entry: (operator, `cells.operator.neutral_arrival_labels@1`), from `python -m cells declarations --out FILE` ([the format](../../DECLARATIONS_FORMAT.md)).
- In the Laws library: `select=laws:cells.operator.neutral_arrival_labels@1`.

<!-- /generated -->
