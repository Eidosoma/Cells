# Product of saturating factors of concentrations (`cells.hill_product_factor@1`)

**In one sentence:** A number between zero and one that rises or falls smoothly with each of the concentrations it reads, by which a transfer's rate is multiplied.

## In plain words

Many gates in a cell open more, or less, as some dissolved molecule or ion becomes more
concentrated. This [law](../../GLOSSARY.md#law) turns each concentration it reads into a factor
between zero and one, by Hill's equation. An activation starts near zero, reaches one half at its
half-saturation and levels off near one; an inhibition does the opposite. The Hill coefficient says
how steep the change is. The factor of several readings is their product, so each reading can only
close what the others leave open. A [host](../../GLOSSARY.md#host) multiplies the opening of a route
or a [channel](../../GLOSSARY.md#channel) by it; the law itself moves nothing. It leaves out how
fast a gate follows, what a reading would consume, and any way one molecule could change how
strongly another is read.

## Seen from each field

- **Biology:** gating by a ligand, by calcium or by both, such as a
  [store's](../../GLOSSARY.md#store) release that a little calcium opens and more calcium closes again.
- **Chemistry:** cooperative binding at equilibrium, without depletion of what is bound.
- **Physics:** a product of logistic functions of the logarithms of concentrations.
- **Computing:** a pure function of arrays: a sum of logarithms and one exponential, with no state.

## At a glance

<!-- generated: at-a-glance -->

| | |
| --- | --- |
| Piece | Law, interface `cells.transfer_factor_law@1` ([its fields](../../DECLARATIONS_FORMAT.md#family-interfaces)) |
| ID | `cells.hill_product_factor@1`; definitions write `hill_product_factor@1` |
| Runs in | `cells.species_condition@1`, its host, in `cells.resolved_pump_tissue@3`. Definitions of `cells.resolved_pump_composite@1` and `cells.resolved_pump_tissue@3` can declare it |
| Provenance | `parity`: moved from an older family; moving is not calibrating |

<!-- /generated -->

## What it reads and changes

<!-- generated: touches -->

| Its interface's own field | Value | Unit |
| --- | --- | --- |
| `forms` | `[["hill_activation", 1], ["hill_inhibition", 2]]` |  |
| `parameters` | `["half_saturation_mM", "hill_coefficient"]` |  |
| `value_range` | `[0.0, 1.0]` | 1 |

Energy role: not yet extracted; the law template has no energy role yet.

<!-- /generated -->

## The mathematics

<!-- generated: bounds -->

None declared.

<!-- /generated -->

A factor has readings $j = 1 \ldots J$. Reading $j$ takes a concentration $x_j$ (mM) under a form, a
half-saturation $K_j$ (mM, above 0) and a Hill coefficient $n_j$ (no unit, above 0):

$$z_j = n_j\,(\ln x_j - \ln K_j), \qquad h_j = \frac{1}{1 + e^{-z_j}} = \frac{x_j^{n_j}}{K_j^{n_j} + x_j^{n_j}} \ \text{(activation)}, \qquad h_j = \frac{1}{1 + e^{z_j}} = \frac{K_j^{n_j}}{K_j^{n_j} + x_j^{n_j}} \ \text{(inhibition)}$$

$$f = e^{\,\ln h_1 + \ln h_2 + \cdots + \ln h_J}, \qquad 0 \le f \le 1$$

$$\frac{\partial \ln f}{\partial \ln x_j} = +\,n_j\,(1 - h_j) \ \text{(activation)}, \qquad -\,n_j\,(1 - h_j) \ \text{(inhibition)}$$

- **The sum runs in declared order,** and the product is one exponential of it. The logarithm of each
  factor is the engine's own Hill helper's, so the factor of one reading is that helper's bit for bit.
- **Its sense:** a higher activation reading opens, and a higher inhibition reading closes.
- **Zero, and below:** at a zero concentration an activation is exactly 0 and an inhibition exactly 1.
  A negative concentration, or one that is not a number, gives a value that is not a number, which
  the routing door refuses. Nothing is clipped.
- **The slopes** are finite at every concentration, a zero one included, and $1 - h_j$ is formed
  directly rather than by subtraction, so it keeps its accuracy where the gate is nearly open.
- **Left out:** no reading changes another's half-saturation (the readings are separable); a reading
  binds nothing; and the gate has no state, latency or inactivation.
- **The pH factor:** `ph_conditioned_factor@1` is this law with one activation reading of the free
  proton, $K = 10^{3 - \text{pH}_{50}}$ mM and $n$ its slope. On 20,000 random points the two differ by
  at most 2.3e-15 (absolute). That law retires in a landing of its own.

## Sources

<!-- generated: provenance -->

Provenance: `parity` (moved from an older family; moving is not calibrating).

- **Source, as declared:** Hill's equation (A. V. Hill, 1910; reviewed by J. N. Weiss, 1997): one saturating factor per read, and their product
- **Place:** the form x^n/(K^n + x^n) and its complement K^n/(K^n + x^n), as the engine's Hill helper states them (laws/reactions/hill_factors.py), evaluated in log space
- **Licence of the numbers:** no numbers taken: the law is a form, its half-saturations and coefficients a definition's values
- **Departures:** a product of separable factors: no read changes another's half-saturation; a reading binds nothing and consumes nothing; instantaneous: no gate state, latency or inactivation
- **Work:** Weiss JN (1997). The Hill equation revisited: uses and misuses. doi:10.1096/fasebj.11.11.9285481

<!-- /generated -->

| Work | What was taken | Mark |
| --- | --- | --- |
| A. V. Hill (1910), J. Physiol. 40 (Suppl.): iv–vii | The form's origin. No numbers | unread |
| J. N. Weiss (1997), FASEB J. 11:835–841 | A review of the equation, which the engine's design notes cite for the form. No numbers | unread: the record (author, title, journal, pages and DOI) was checked against Crossref on 25 November 2026 |
| I. Bezprozvanny, J. Watras and B. E. Ehrlich (1991), Nature 351:751–754 | The motive for an activation times an inhibition of one calcium reading: a bell-shaped curve. No numbers | unread: the record was checked against Crossref on 25 November 2026 |
| D.-O. D. Mak, S. McBride and J. K. Foskett (1998), PNAS 95:15821–15825 | Evidence against a separable form: the ligand was found to change the calcium inhibition's half-saturation. Not represented here | relayed: the design note's author read it through a page tool that gave the equations as images |

The last rests on one laboratory's work, so it is an indication. A law in which one reading changes
another's half-saturation would be its own version.

**Departures:** a product of separable factors; a reading that binds nothing; no gate state, latency
or inactivation.

## How it is checked

<!-- generated: tests -->

Declared test: [`tests/unit/test_hill_factors.py`](../../../../tests/unit/test_hill_factors.py), `test_the_hill_product_law_and_its_planted_errors`.

<!-- /generated -->

The law is compared with its closed form, the product of plain powers, at 400 random sets of one to
four readings, and with the engine's own Hill helper bit for bit. Six [planted
errors](../../GLOSSARY.md#planted-error) must fail that comparison: a wrong exponent, the two forms
exchanged, a missing factor, a half-saturation in M for mM, the half-saturation and the coefficient
exchanged, and a reading scaled by the molecule's charge. Other tests hold the exact values at a zero
concentration, host and compiled, against a floored and a clipped reading; the slopes against finite
differences, with an inhibition's sign dropped and a derivative taken in the wrong variable; the
record against its interface; the pH factor; and the coupling operator's factor bit for bit.

## Status

<!-- generated: status -->

Not stated: no record states a level for this piece.

<!-- /generated -->

## Links

<!-- generated: links -->

- Declared in [`src/cells/laws/reactions/hill_product_factor.py`](../../../../src/cells/laws/reactions/hill_product_factor.py) (`cells.laws.reactions.hill_product_factor`).
- Kernels: `log_factor`, `cells.laws.reactions.hill_product_factor.log_factor`; `factor`, `cells.laws.reactions.hill_product_factor.factor`; `log_slopes`, `cells.laws.reactions.hill_product_factor.log_slopes`.
- Runs in `cells.species_condition@1`.
- Manifest entry: (law, `cells.hill_product_factor@1`), from `python -m cells declarations --out FILE` ([the format](../../DECLARATIONS_FORMAT.md)).
- In the Laws library: `select=laws:cells.hill_product_factor@1`.

<!-- /generated -->
