# Species condition at a node (`cells.species_condition@1`)

**In one sentence:** A condition at a node reads the concentrations of chosen substances there and gives a number between zero and one that opens or closes routes and channels.

## In plain words

Cells open and close transport with what is dissolved around it: a store releases calcium when a
signal molecule and a little calcium are present. This [kind](../../GLOSSARY.md#kind) is a general
gate of that sort. A condition sits at one [node](../../GLOSSARY.md#node), a cell or a space outside
it, and reads declared substances there. Its [law](../../GLOSSARY.md#law) turns the readings into
one factor between zero and one. Any passive route or [channel](../../GLOSSARY.md#channel)
population may name any number of conditions, and is multiplied by each. The factor follows the concentrations at
every [stage](../../GLOSSARY.md#stage) of a step, so a release that raises what opens it is followed
as it happens. A condition keeps no state, moves nothing and books nothing: the route books what it
moves. It leaves out binding, so what it reads is never used up, and any delay or inactivation of
the gate.

## Seen from each field

- **Biology:** ligand- and calcium-gated release or conductance.
- **Chemistry:** an instantaneous rate factor of concentrations, without depletion.
- **Physics:** a multiplicative control read from the state of the same stage.
- **Computing:** a source of the routing door: a module that gives each named factor at each stage,
  and the factor's logarithmic slope in every amount it reads.

## At a glance

<!-- generated: at-a-glance -->

| | |
| --- | --- |
| Piece | Kind, interface `cells.kind@1` ([its fields](../../DECLARATIONS_FORMAT.md#kinds)) |
| ID | `cells.species_condition@1`; definitions write `cells.species_condition@1` |
| Runs in | `cells.resolved_pump_tissue@3`, its host, which definitions write `resolved_pump_tissue@3`. Definitions of `cells.resolved_pump_composite@1` and `cells.resolved_pump_tissue@3` can declare it, under the key `species_conditions` |
| Laws it hosts | `cells.hill_product_factor@1` |
| Provenance | Not yet extracted: the kind contract has no provenance field yet |

<!-- /generated -->

## What it reads and changes

<!-- generated: touches -->

| Field | Role | Axes | Unit | Record | Which way is positive |
| --- | --- | --- | --- | --- | --- |
| `species_condition_factor` | Provides | | 1 | level | Not stated |

Ledgers: not yet extracted. Energy roles: not yet extracted. Its records are on the `membrane` layer.

<details><summary>For developers</summary>

Hooks: `check_definition`, `factor_log_slopes`, `factor_rows`, `factor_sources`, `factors`, `initial`, `parse`, `readouts`, `structure_entry`, `to_dict` and `view_sets`. Layout fields: `species_condition_node`, `species_condition_row`, `species_condition_form`, `species_condition_half_saturation_mM`, `species_condition_coefficient`, `species_condition_pair` and `species_condition_pair_condition`. Experiment keys: none.

</details>

<!-- /generated -->

## The mathematics

<!-- generated: bounds -->

None declared by the kind; each law it hosts declares its own.

<!-- /generated -->

The kind computes the concentrations its law reads, and the law gives the factor. For a condition at
a node with volume $V$ (pL) and amounts $N_s$ (fmol), reading $j$ of species $s_j$ takes

$$\ln x_j = \ln N_{s_j} - \ln V$$

from the amounts that every rate of the stage reads: a [species row](../../GLOSSARY.md#species-row)'s
free amount where a closure owns the row, and the node's current volume. It is a concentration, so
the species' [valence](../../GLOSSARY.md#valence) does not enter. The factor is
`hill_product_factor@1`'s.

- **The door.** Each route or channel slot that names conditions takes its held value times their
  factors, multiplied in its own declared order, at every explicit stage and at each observed row. A
  factor outside [0, 1], or one that is not a number, is a [refusal](../../GLOSSARY.md#refusal) of
  the step or the row.
- **Order:** the stepper's, second under the ARS(2,2,2) IMEX step. Under RK4 every declared kind is
  refused.
- **Feedback.** A route that moves a row its own condition reads closes a loop. The kind names the
  rows each condition reads, and gives at a stage the slope $\partial \ln f / \partial \ln N$ of each
  (no unit, signed, finite at a zero amount): the sum over the condition's readings of that species.
  The bound that uses them is the core's, and is not built yet. A loop through two routes is not
  bounded, nor one through a source that reads an amount and has no such slopes (the pH condition);
  and where a closure owns the row, the slope is in the free amount, without the closure's own.
- **Beside operators:** water (the read takes the current volume), the compartment wash and arrival
  labels are admitted. An operator that closes, divides or retires slots refuses it, and so does one
  that builds the inner model's fields in a fixed layout, such as cell replacement.
- **The pH condition** (`ph_condition@1`) is a condition with one activation reading of the proton
  row, $K = 10^{3 - \text{pH}_{50}}$ mM and $n$ its slope: the two factors differ by at most 2.3e-15
  (absolute) on 20,000 random points. It retires in a landing of its own, with the worlds that declare
  it.

## Sources

<!-- generated: provenance -->

Provenance: not yet extracted; the kind contract has no provenance field yet.

<!-- /generated -->

- **The kind is Cells' own design:** [the note on ligand-gated store
  release](../../../IP3_RELEASE_AND_ASSEMBLY_AVAILABILITY_DESIGN.md), Part I, on the routing door of
  [the inner-model design](../../../INNER_MODEL_V4_DESIGN.md) (§7.4 (n)). FT.
- **Its law declares its own citation** (`hill_product_factor@1`). No number is taken by either.

## How it is checked

<!-- generated: tests -->

Declared test: not yet extracted; the kind contract has no test field yet.

<!-- /generated -->

Its declaration is refused with its reason for each malformed entry, the kind and the condition
named. On the host, a gated calcium route in a small world gives the flux of a closed form written
without the law's kernels, at a state the run reached, and each [planted
error](../../GLOSSARY.md#planted-error) misses it: a wrong exponent, the forms exchanged, a missing
factor, a wrong node, a half-saturation in M, and another species' row. The released amount converges
at second order, and a factor held at the step's start at first. A ligand of valence -3 and one of
valence 0 give one run bit for bit. The door refuses a factor out of range and a reading that is not
a number. The hooks' slopes agree with finite differences of the factor, and the core's rule, stubbed
in the test, with the finite difference of the routed flux through the factor. A compiled world of a store in a composite runs
ten steps in which the route's heat never falls, and restarts from a checkpoint bit for bit.

Its scope is those worlds. It says nothing about a receptor, or about the numbers of any one gate.

## Status

<!-- generated: status -->

Not stated: no record states a level for this piece.

<!-- /generated -->

## Links

<!-- generated: links -->

- Declared in [`src/cells/kinds/species_condition.py`](../../../../src/cells/kinds/species_condition.py) (`cells.kinds.species_condition`).
- Hosts `cells.hill_product_factor@1`.
- Runs in `cells.resolved_pump_tissue@3`.
- Manifest entry: (kind, `cells.species_condition@1`), from `python -m cells declarations --out FILE` ([the format](../../DECLARATIONS_FORMAT.md)).
- In the Laws library: `select=laws:cells.species_condition@1`.

<!-- /generated -->
