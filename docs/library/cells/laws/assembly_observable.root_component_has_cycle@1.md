# Whether an assembly has a closed ring (`cells.assembly_observable.root_component_has_cycle@1`)

**In one sentence:** It says whether a molecular assembly has a closed ring of bonds, by comparing how many bonds it has with how many building blocks are joined in it.

## In plain words

Building blocks that bind into an assembly can make an open chain or close into a ring. A ring needs
one more bond than an open chain of the same blocks, so for an assembly in one piece, counting the
bonds and the blocks is enough to tell. This law gives that answer, yes or no, for one assembly at
one moment. It holds no number of its own, and it changes nothing.

What the answer does is declared elsewhere. A composed file may give each answer a level, and a
[channel](../../GLOSSARY.md#channel) [population](../../GLOSSARY.md#population)'s
[availability](../../GLOSSARY.md#availability) is then multiplied by that level as the assembly
opens and closes. That a ring should matter to a channel at all is a hypothesis of that file. The
law leaves out how many rings there are, which blocks make them, and any energy of closing one.

## Seen from each field

- **Biology:** whether a complex, such as a ring of subunits, has closed on itself.
- **Chemistry:** whether the bonds of one oligomer hold a ring. It says nothing of how strong they
  are: a bond in a ring breaks at the same rate as any other.
- **Physics:** whether a connected graph has an independent loop, that is, whether its cycle rank is
  at least one.
- **Computing:** a comparison of two population counts, of a word of bonds and a word of occupied
  sites. It has no state.

## At a glance

<!-- generated: at-a-glance -->

| | |
| --- | --- |
| Piece | Law, interface `cells.assembly_observable@1` ([its fields](../../DECLARATIONS_FORMAT.md#family-interfaces)) |
| ID | `cells.assembly_observable.root_component_has_cycle@1`; definitions write `cells.assembly_observable.root_component_has_cycle@1` |
| Runs in | `cells.model.finite_bond_assembly@1`, its host. No model's definitions can declare it |
| Provenance | `parity`: moved from an older family; moving is not calibrating |

<!-- /generated -->

## What it reads and changes

<!-- generated: touches -->

| Its interface's own field | Value | Unit |
| --- | --- | --- |
| `reads` | `["occupied", "bonds"]` |  |
| `values` | `["false", "true"]` |  |

Energy role: not yet extracted; the law template has no energy role yet.

<!-- /generated -->

## The mathematics

<!-- generated: bounds -->

None declared.

<!-- /generated -->

An assembly of $V$ occupied sites and $E$ bonds (counts, 1) that is in one connected piece has
$E - V + 1$ independent rings, its cycle rank (1). The value of the observable is

$$\text{true where } E \ge V, \qquad \text{false where } E < V .$$

- **What the ID commits** is this map, from an assembly's occupied sites and bonds to one of two
  values, and nothing else. A change of the map takes a new major.
- **What is data:** the level each value stands for, a number in [0, 1]; the channel populations that
  the level scales; and the schedule it multiplies. The composed file declares them beside the
  observable, and the ID says nothing of them.
- **The assumption: one piece.** The pool keeps its assembly connected to its root. A part that a
  broken bond cuts off leaves the assembly at that event, and the pool checks the connection at
  every state it accepts.
- **When it is read:** after each committed event of the pool. An event that leaves the value as it
  was is no switch.
- **Domain:** every state of the pool.
- **Left out:** the number of rings beyond the first, their size and place, and any energy. The
  assembly does not feel the answer: no rate of the pool depends on it.

## Sources

<!-- generated: provenance -->

Provenance: `parity` (moved from an older family; moving is not calibrating).

- **Source, as declared:** The cycle rank of a connected graph, E - V + 1 (elementary graph theory), read from an assembly of cells.model.finite_bond_assembly@1: a topology readout, no number
- **Place:** docs/CAPSID_ASSEMBLY.md, 'Driving ionic channels from pools', which states the rule; its use as a channel's control is a hypothesis with no literature source
- **Licence of the numbers:** no numbers taken: the levels of its values are a composed file's data
- **Departures:** the pool keeps its assembly connected to its root, so one component is assumed
- **Works, as data:** none declared

<!-- /generated -->

| Work | What was taken | Mark |
| --- | --- | --- |
| Elementary graph theory | The cycle rank of a connected graph, $E - V + 1$: a spanning tree has $V - 1$ bonds, and each bond beyond it closes one ring. No numbers | Der |
| [Capsid assembly](../../../CAPSID_ASSEMBLY.md), "Driving ionic channels from pools" | The rule's statement, with the comparison of the two counts. No numbers | Der |

The rule, under this ID, is that of an older family of assembly-regulated cells. No work is cited for
its use as a channel's control. It is a hypothesis of the composed file that declares it.

**Departures:** one component is assumed, since the pool keeps its assembly connected to its root.

## How it is checked

<!-- generated: tests -->

Declared test: [`tests/unit/test_assembly_pool.py`](../../../../tests/unit/test_assembly_pool.py), `test_the_cycle_observable_is_the_cycle_rank_of_every_connected_assembly`.

<!-- /generated -->

The declared test compares the law with a search for rings that counts nothing: it joins the ends of
the bonds one at a time, and finds a ring where a bond's ends are already joined. It does so for
each of the 3,961 connected assemblies of at most seven bonds around one site, 105 of which have a
ring, and for the full cage with and without one of its bonds, on both array libraries. The
comparison turned round, two rings taken for one, and the two counts exchanged must each disagree
with the search. Nothing here says what a ring does in a cell.

## Status

<!-- generated: status -->

Not stated: no record states a level for this piece.

<!-- /generated -->

## Links

<!-- generated: links -->

- Declared in [`src/cells/assembly_pool/observables.py`](../../../../src/cells/assembly_pool/observables.py) (`cells.assembly_pool.observables`).
- Kernels: `evaluate`, `cells.assembly_pool.observables.cycle_index`.
- Runs in `cells.model.finite_bond_assembly@1`.
- Manifest entry: (law, `cells.assembly_observable.root_component_has_cycle@1`), from `python -m cells declarations --out FILE` ([the format](../../DECLARATIONS_FORMAT.md)).
- In the Laws library: `select=laws:cells.assembly_observable.root_component_has_cycle@1`.

<!-- /generated -->
