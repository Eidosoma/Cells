# A timed partial wash of a closed space (`cells.operator.scheduled_compartment_wash@1`)

**In one sentence:** At set times, a chosen fraction of the liquid in a closed space outside the cells is drawn off and replaced by fresh buffer, as in a laboratory wash.

## In plain words

Experiments often exchange part of the liquid around cells: a sample is drawn off and fresh
buffer is added. This [operator](../../GLOSSARY.md#operator) does that at scheduled times for a
[finite node](../../GLOSSARY.md#finite-node), a closed space of fixed volume. Each uncharged
dissolved substance mixes with the buffer in proportion to the fraction exchanged. A charged
substance is exchanged for liquid of the same composition, so its amount stays as it is. Material
bound to surfaces stays where it is. The wash records what it removed and supplied, the free energy
carried off and brought in, and the heat of mixing, which is never negative. Where substances carry
arrival labels, it reports each exchange so the labels can follow it. Left out: washes of a
[held bath](../../GLOSSARY.md#held-bath) or of a cell, and nodes whose substances can cross a
membrane or face.

## Seen from each field

- **Biology:** a medium change, or one wash step of a perfusion or tracer-washout protocol.
- **Chemistry:** two ideal dilute solutions mixed at constant volume, with the ideal free energy
  of mixing.
- **Physics:** an instantaneous map of the node's state at a point of the time grid, with its
  free-energy split and its heat booked in the energy ledger.
- **Computing:** an event map at the start of the step, its times and buffers controls of the
  schedule. Beside the label owner its call also returns a typed report.

## At a glance

<!-- generated: at-a-glance -->

| | |
| --- | --- |
| Piece | Operator, interface `cells.operator@1` ([its fields](../../DECLARATIONS_FORMAT.md#operators)) |
| ID | `cells.operator.scheduled_compartment_wash@1`; definitions write `cells.operator.scheduled_compartment_wash@1` |
| Runs in | `cells.model.resolved_pump_composite@1`, its host. Definitions of `cells.model.resolved_pump_composite@1` can declare it |
| Where it acts in the step | An event map; scheduled by `compartment_wash_events` |
| Needs | No law or kind |
| Provenance | Not yet extracted: the composite's operator contract has no provenance field yet |

<!-- /generated -->

## What it reads and changes

<!-- generated: touches -->

| Field | Role | Axes | Unit | Which way is positive |
| --- | --- | --- | --- | --- |
| `extracellular_volume` | Reads (fixed, at the event stage) | | pL | |
| `extracellular_amount_reference` | Reads (fixed, at the event stage) | | fmol | |
| `outside_active` | Reads (fixed, at the event stage) | | 1 | |
| `wash_collected_fmol` | Owns | species, extracellular_slot | fmol | From node to exterior: "the samples taken from the node's liquid, out of the world to their sink" |
| `wash_supplied_fmol` | Owns | species, extracellular_slot | fmol | From exterior to node: "the buffer supplied to the node's liquid, into the world from its source" |
| `wash_sample_free_energy_pJ` | Owns | extracellular_slot | pJ | Not stated |
| `wash_buffer_free_energy_pJ` | Owns | extracellular_slot | pJ | Not stated |
| `wash_mixing_heat_pJ` | Owns | extracellular_slot | pJ | Not stated |
| `wash_last_mixing_heat_pJ` | Owns | extracellular_slot | pJ | Not stated |
| `wash_last_sample_fmol` | Owns | species, extracellular_slot | fmol | From node to exterior: "the latest wash's sample from the node's liquid, out of the world" |
| `wash_last_supply_fmol` | Owns | species, extracellular_slot | fmol | From exterior to node: "the latest wash's buffer supplied to the node's liquid, into the world" |
| `wash_energy_magnitude_pJ` | Owns | extracellular_slot | pJ | Not stated |
| `wash_applied` | Owns | extracellular_slot | 1 | Not stated |
| `wash_count` | Controls | | Not stated | |
| `wash_fraction` | Controls | | Not stated | |
| `wash_buffer_mM` | Controls | | mM | |

Writes into other pieces' fields: `extracellular_amount_increment`, booked in `wash_collected_fmol` and `wash_supplied_fmol`. Ledgers: `wash_ions`. Records: `wash_collected_fmol` (cumulative), `wash_supplied_fmol` (cumulative), `wash_sample_free_energy_pJ` (cumulative), `wash_buffer_free_energy_pJ` (cumulative), `wash_mixing_heat_pJ` (cumulative), `wash_last_mixing_heat_pJ` (level), `wash_last_sample_fmol` (level), `wash_last_supply_fmol` (level), `wash_energy_magnitude_pJ` (cumulative) and `wash_applied` (cumulative).

<!-- /generated -->

## The mathematics

<!-- generated: bounds -->

None declared.

<!-- /generated -->

At a wash of node $i$ at time $t$, applied at the start of the step leaving $t$, write $f$ for the
fraction (1), $V$ for the node's volume (pL), $n_s$ for species $s$'s amount there (fmol),
$c_s = n_s / V$ (mM) and $c_{\text{buf},s}$ for the buffer's concentration (mM). Then for an
uncharged species:

$$n_s' = (1 - f)\,n_s + f\,V\,c_{\text{buf},s}, \qquad r_s = f\,n_s, \qquad a_s = f\,V\,c_{\text{buf},s}$$

- **An ion's buffer is the node's own composition,** so $a_s = r_s$ and $n_s' = n_s$. Its supply
  record is its sample record, one expression.
- **The records** $r_s$ (the sample) and $a_s$ (the supply) are kept cumulatively, and the latest
  event's as level records.

With $F(n, V) = 10^{-3} RT\, n\,(\ln(n/V) - 1)$ in pJ ($R$ in J/(mol K), $T$ in K, $n$ in fmol,
concentrations in mM):

$$F_\text{sample} = f\,F(n, V), \qquad F_\text{buffer} = F(f V c_\text{buf}, f V)$$

$$H_\text{mix} = 10^{-3} RT\, V \sum_s c_s' \Big[(1 - f)\,\varphi\big(c_s / c_s'\big) + f\,\varphi\big(c_{\text{buf},s} / c_s'\big)\Big] \ge 0$$

with $c' = (1 - f)\,c + f\,c_\text{buf}$ and $\varphi(x) = x \ln x - x + 1$.

- **The books:**
  - the outside and total material ledgers gain $r - a$ at the node;
  - the energy ledger gains $H_\text{mix} - (F_\text{buffer} - F_\text{sample})$ against the node's
    own chemical jump, so its closure checks the split.
- **The labelled report.** Beside `cells.operator.neutral_arrival_labels@1` the event also reports
  $(r, a)$ for the labelled rows at the nodes washed in this step, and zero elsewhere. These are
  read from the latest event's level records, never from a cumulative record's gain.
  - The label owner then carries $r$ away with the node's shares and adds $a$ to the unlabelled
    base.
  - The report's axis is the outside nodes, so an exchange of a cell's own liquid cannot be
    expressed in version 1.
- **The domain:**
  - $0 < f \le 1$;
  - every buffer concentration $> 0$: a tracer-free buffer is declared at the species' trace;
  - times on the grid, inside the horizon, increasing per node.
- **Assumptions:** a well-mixed node, ideal dilute solutions and constant volume.
- **Refused in version 1:**
  - a held bath;
  - a node that a face touches;
  - a node across whose surface any declared path may move an uncharged species;
  - a compartment's node, whether or not an event names it: a compartment lies behind its owner's
    membrane, out of the liquid's reach (a wash of another node beside a compartment is admitted);
  - a buffer that misses an uncharged species or names another;
  - ions declared other than the node's own composition.

## Sources

<!-- generated: provenance -->

Provenance: not yet extracted; the composite's operator contract has no provenance field yet.

<!-- /generated -->

- **Ideal dilute mixing at constant volume** (Der): the event map, the free-energy split and the
  heat of mixing were derived for this piece. The whole wash's booking, the old pool to its sink
  and the fresh pool from its source, agrees with Cells' exact-count pool replacement
  (`cells.operator.pool_replacement@1`), the whole-exchange execution of the same mechanism.
- **The form of $\varphi$** (Der): its series near 1, its log1p form and its ratio form, derived for
  the restricted lumen's fix and shared with it bit for bit.

## How it is checked

<!-- generated: tests -->

Declared test: not yet extracted; the composite's operator contract has no test field yet.

<!-- /generated -->

- **The heat of mixing** is held against a 50-digit reference, at the trace too. Two planted
  forms of $\varphi$ must each break it.
- **At the event,** the sample, the supply and the free-energy split are checked:
  - every site field and every ion amount keeps its bits;
  - the ledgers close with the wash's terms, and fail without them by orders of magnitude.
- **A whole wash** books the old and fresh pools, as the exact-count replacement does.
- **The labelled report:**
  - it equals the level records at the washed nodes, in NumPy and compiled;
  - the call's state and validity are the unlabelled call's, bit for bit.
- **A whole wash after an earlier one** must leave no labelled share behind. A planted cumulative
  gain must leave one, on two cases chosen to fail.
- **Compiled runs:**
  - a labelled run and its unlabelled twin, washed five times, keep every physical record bit for
    bit;
  - a run resumes bit for bit across a wash, and a planted redo and a planted skip of it are
    caught.

## Status

<!-- generated: status -->

Not stated: no record states a level for this piece.

<!-- /generated -->

## Links

<!-- generated: links -->

- Declared in [`src/cells/operators/wash_schedule.py`](../../../../src/cells/operators/wash_schedule.py), class `ScheduledCompartmentWash` (`cells.operators.wash_schedule`).
- Runs in `cells.model.resolved_pump_composite@1`.
- Manifest entry: (operator, `cells.operator.scheduled_compartment_wash@1`), from `python -m cells declarations --out FILE` ([the format](../../DECLARATIONS_FORMAT.md)).
- In the Laws library: `select=laws:cells.operator.scheduled_compartment_wash@1`.

<!-- /generated -->
