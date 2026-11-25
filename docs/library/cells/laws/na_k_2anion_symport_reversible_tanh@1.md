# Symport of one sodium, one potassium and two anions, with a manufactured rate (`cells.na_k_2anion_symport_reversible_tanh@1`)

**In one sentence:** One sodium ion, one potassium ion and two single-charged anions cross a membrane together, carrying no net charge, at a rate whose form is manufactured.

## In plain words

Cells take salt in, or let it out, by moving ions together so that no net charge crosses. In each
cycle this law moves one sodium, one potassium and two anions, such as chloride, the same way. It
spends no fuel: ions that run downhill carry the others uphill. The
[membrane voltage](../../GLOSSARY.md#membrane-voltage) has no say. The transport stalls where the
products of the concentrations on the two sides balance, and runs backward beyond. That balance
follows from the counts. How fast it runs does not: the rate is a manufactured function of the
balance alone, and it never exceeds the capacity that a [definition](../../GLOSSARY.md#definition)
gives. No measurement supports the form, and there is no measured number in it. The law leaves out
binding by each ion, regulation by volume, chloride or phosphorylation, and the water that follows
salt. It is no model of any transporter protein.

## Seen from each field

- **Biology:** secondary active transport of salt with no net charge, as by the
  sodium-potassium-chloride cotransporters.
- **Chemistry:** a reversible transfer of four ions in one cycle, whose reaction quotient is the
  ratio of two concentration products.
- **Physics:** one cycle driven by the difference of the moved ions' chemical potentials across the
  membrane. The rate is the capacity times the hyperbolic tangent of half the affinity over RT.
- **Computing:** data only, with no kernel and no state: a monomial form that the cycle kind's one
  program runs.

## At a glance

<!-- generated: at-a-glance -->

| | |
| --- | --- |
| Piece | Law, interface `cells.cycle_law@1` ([its fields](../../DECLARATIONS_FORMAT.md#cycle-laws)) |
| ID | `cells.na_k_2anion_symport_reversible_tanh@1`; definitions write `cells.na_k_2anion_symport_reversible_tanh@1` |
| Runs in | `cells.transporter@1`, its host, in `cells.resolved_pump_tissue@3`. Definitions of `cells.resolved_pump_composite@1` and `cells.resolved_pump_tissue@3` can declare it |
| Provenance | `parity`: moved from an older family; moving is not calibrating |

<!-- /generated -->

## What it reads and changes

<!-- generated: touches -->

| Role | What | Unit | Which way is positive |
| --- | --- | --- | --- |
| Reads | `rapid_binding@1`, current at each inner stage | | |
| Changes | `Na@N`: 1 per cycle | | inward-positive, per forward cycle |
| Changes | `Na@P`: -1 per cycle | | inward-positive, per forward cycle |
| Changes | `K@N`: 1 per cycle | | inward-positive, per forward cycle |
| Changes | `K@P`: -1 per cycle | | inward-positive, per forward cycle |
| Changes | `anion@N`: 2 per cycle | | inward-positive, per forward cycle |
| Changes | `anion@P`: -2 per cycle | | inward-positive, per forward cycle |

Energy role: not yet extracted; the law template has no energy role yet.

<!-- /generated -->

## The mathematics

<!-- generated: bounds -->

| Declared | Value | Unit |
| --- | --- | --- |
| Material term | `material_term` |  |
| Fuel kinds | none |  |

<!-- /generated -->

A [population](../../GLOSSARY.md#population) sits on one [patch](../../GLOSSARY.md#patch), whose two
ends are its N and P (N is the cell where the definition says `"N": "a"`). It declares a capacity
$k$ (fmol cycles/s), and $v$ is its [availability](../../GLOSSARY.md#availability) (0 to 1). With
each ion's concentration at an end in mM, the
[cycle free energy](../../GLOSSARY.md#cycle-free-energy) over $RT$ and the rate (fmol cycles/s) are

$$x = \ln\frac{[\text{Na}]_N}{[\text{Na}]_P} + \ln\frac{[\text{K}]_N}{[\text{K}]_P} + 2\ln\frac{[\text{A}]_N}{[\text{A}]_P}, \qquad J = k v \tanh\left(-\frac{x}{2}\right) = k v S\,(1 - e^x), \quad S = \frac{1}{1 + e^x}.$$

- **What moves:** per forward cycle one sodium, one potassium and two anions leave P for N, so no
  charge crosses. The kind books these amounts at both ends in the shared
  [inventory](../../GLOSSARY.md#inventory), and the [heat](../../GLOSSARY.md#heat) $-RT\,J\,x$,
  which is never negative. No work is booked and no fuel is used.
- **The stall:** $J = 0$ where the two ends' products $[\text{Na}][\text{K}][\text{A}]^2$ are equal.
  The capacity does not move it, and the voltage does not enter.
- **What it claims:** the 1:1:2 coupling, which is the form's, and nothing measured. The rate is
  manufactured: it depends on the concentrations through $x$ alone, and the two one-way rates sum to
  $k v$.
- **Domain:** $x \le 80$, one-sided; positive concentrations. A state outside it is refused, never
  clipped. The older law of the same rate kept its own domain, with temperatures from 200 to 400 K;
  here the inner model's is the same.
- **Step rules:** the law moves charged [species rows](../../GLOSSARY.md#species-row) and no net
  charge, so it has no charge slope. The kind bounds the population's own material rate: over the
  six rows it moves, the sum of $|\nu_k\, \partial J/\partial n_k|$ (1/s; $\nu_k$ the row's count
  and $n_k$ its amount in fmol), given to each of them. A held bath's rows are left out. It declares
  that term alone, which holds no charged row at a closed compartment's node, so its moves there are
  refused ([refusal 4](../../../CLOSED_COMPARTMENT_DESIGN.md)). RK4 runs are refused, as for every
  kind.
- **At a binding closure:** it declares the read `rapid_binding@1` and base forms, so where a
  closure holds one of its ions it reads the free amount and moves the total, and the material rate
  runs through the closure's derivative.
- **Left out:** binding by each ion and any other saturation, regulation by volume, chloride or
  phosphorylation, the water carried with the salt, any isoform, and any temperature dependence (the
  rate reads no temperature).

## Sources

<!-- generated: provenance -->

Provenance: `parity` (moved from an older family; moving is not calibrating).

- **Source, as declared:** manufactured: the rate form has no outside source. It moved from an older model family's law of the same equation
- **Place:** the older family's kernel: J = C a tanh(A / 2RT), A the affinity of one Na+, one K+ and two anions
- **Licence of the numbers:** no number taken: the law is a form, its capacity a definition's value
- **Departures:** manufactured: a saturating function of the affinity alone, with no binding constants; no regulation by volume, chloride or phosphorylation, and no water with the salt
- **Works, as data:** none declared

<!-- /generated -->

**Manufactured: the rate form has no outside source.** It moved from an older model family's
cotransport law of the same equation, $J = C a \tanh(A/2RT)$ with $A$ the affinity
([the calcium note](../../../CALCIUM_STORE_AND_CHANNELS_DESIGN.md) §7.2 holds the check, and
[the older family's note](../../../COTRANSPORT.md) that law). No number was taken. A form with a
cited rate would be another law of this mechanism, and only one of the two would stay.

## How it is checked

<!-- generated: tests -->

Declared test: [`tests/unit/test_cycle_kind.py`](../../../../tests/unit/test_cycle_kind.py), `test_the_pump_and_the_symports_meet_their_equations_and_each_plant_misses_its_criteria`.

<!-- /generated -->

The kind's own evaluation is compared with the rate as $k$ times the difference over the sum of the
two ends' concentration products, with no hyperbolic tangent, in 60-digit decimals, never through
the form: at 24 random states and at the domain's edges and the stall from two more, for two
capacities, with N the cell or the bath. Fluxes are held to 2e-13 of the one-way scale, and the
slopes to 1e-12. The criteria are the rate, the detailed balance with the heat's value and sign, the
moved amounts and the charge, the sign on either side of the stall, the slopes (none in the voltage)
and the domain. Each plant must miss exactly the criteria it is planted against: one anion in place
of two, the rate without its factor, an anion counted once in the rate, the cycle run backward, a
standard part added, and the domain at 79. The reference is independent of the form, not code-blind.

The older kernel's own 80-digit reference and protocol are kept. At nine states, from the stall and
near it to concentrations of 1e-300 and 1e300 mM and temperatures of 200 and 400 K, the cycles, the
affinity, the transport and the heat are that reference's to the protocol's tolerances.

Other rows run closed worlds: amounts follow the cycles at each end, no charge crosses, the heat
grows and every [ledger](../../GLOSSARY.md#ledger) closes, and a neutral corruption of the amounts
is refused by its ledger. The population's own material rate is the reference's at both ends. Wrong
species, valences and counts, RK4, and a population at a store's node are refused by name. Beside a
potassium binder under a closure it reads the free potassium. Each has a planted error. No run was
compared with a measurement.

## Status

<!-- generated: status -->

Not stated: no record states a level for this piece.

<!-- /generated -->

## Links

<!-- generated: links -->

- Declared in [`src/cells/laws/cycles/na_k_2anion_symport_reversible_tanh.py`](../../../../src/cells/laws/cycles/na_k_2anion_symport_reversible_tanh.py) (`cells.laws.cycles.na_k_2anion_symport_reversible_tanh`).
- Runs in `cells.transporter@1`.
- Manifest entry: (law, `cells.na_k_2anion_symport_reversible_tanh@1`), from `python -m cells declarations --out FILE` ([the format](../../DECLARATIONS_FORMAT.md)).
- In the Laws library: `select=laws:cells.na_k_2anion_symport_reversible_tanh@1`.

<!-- /generated -->
