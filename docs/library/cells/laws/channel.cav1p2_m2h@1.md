# CaV1.2-type calcium channel gating (`cells.channel.cav1p2_m2h@1`)

**In one sentence:** A calcium channel that opens within milliseconds when the membrane voltage rises and shuts within tens of milliseconds, so that a rise lets in a short pulse of calcium.

## In plain words

Every cell holds a voltage across its membrane, and [channels](../../GLOSSARY.md#channel) are the
pores that let ions cross it. This law says when one type of calcium channel is open. It has two
[gates](../../GLOSSARY.md#gate). The first opens within milliseconds when the inside of the cell
becomes less negative; the second shuts within tens of milliseconds after the same change. Calcium
passes only while both are open, so a rise of the voltage gives a short pulse. Calcium is scarce
inside a cell, so a small pulse changes its amount much while it moves little charge, and the host
limits its time step by that change too. It leaves out inactivation by calcium itself, temperature,
the charge that moves with a gate, and the energy of the channel protein.

## Seen from each field

- **Biology:** a voltage-dependent calcium current that inactivates. Its form and numbers are another
  simulator's description of the CaV1.2 channel, not a fit to any cell type.
- **Chemistry:** each gate is an open–shut equilibrium whose rates depend on voltage; the two
  gates are independent.
- **Physics:** two first-order relaxations toward sigmoid targets, with sigmoid time constants.
- **Computing:** a pure function from voltage to targets and time constants. The host advances the
  gates and computes the current.

## At a glance

<!-- generated: at-a-glance -->

| | |
| --- | --- |
| Piece | Law, interface `cells.channel_law@1` ([its fields](../../DECLARATIONS_FORMAT.md#channel-laws)) |
| ID | `cells.channel.cav1p2_m2h@1`; definitions write `cells.channel.cav1p2_m2h@1` |
| Runs in | `cells.model.resolved_pump_tissue@3`, its host. Definitions of `cells.model.resolved_pump_composite@1` and `cells.model.resolved_pump_tissue@3` can declare it |
| Registry code | 11 |
| Provenance | `parity`: moved from an older family; moving is not calibrating |

<!-- /generated -->

## What it reads and changes

<!-- generated: touches -->

| Role | What | Unit | Which way is positive |
| --- | --- | --- | --- |
| Reads | None declared | | |
| Changes | `Ca`: valence 2, relative permeability 1.0 | Not stated | Not stated |
| Its gates, kept by the host | `m` and `h` | | |

Energy role: not yet extracted; the law template has no energy role yet.

<!-- /generated -->

## The mathematics

<!-- generated: bounds -->

| Declared | Value | Unit |
| --- | --- | --- |
| Voltage domain | -0.12 to 0.06 | V |
| Stage term | `constant_field_slope` |  |
| Material term | `material_slope_per_s` |  |

<!-- /generated -->

With $V$ the [membrane voltage](../../GLOSSARY.md#membrane-voltage) (inside less outside, in volts),
$u = V - 0.010$ V, $t$ in seconds and $\sigma(x) = 1/(1 + e^{-x})$:

$$m_\infty = \sigma\!\left(\frac{u + 0.030}{0.006}\right), \qquad h_\infty = \sigma\!\left(-\frac{u + 0.080}{0.0064}\right)$$

$$\tau_m = 0.005 + 0.020\,\sigma\!\left(-\frac{u + 0.025}{0.005}\right), \qquad \tau_h = 0.020 + 0.050\,\sigma\!\left(-\frac{u + 0.040}{0.007}\right)$$

$$\frac{dm}{dt} = \frac{m_\infty - m}{\tau_m}, \qquad \frac{dh}{dt} = \frac{h_\infty - h}{\tau_h}, \qquad \text{open fraction} = m^2 h$$

- **Domain:** −0.120 V ≤ V ≤ 0.060 V, the inner model's channel domain. A step outside it is refused,
  never clipped. There $\tau_m$ runs from 5 to 25 ms and $\tau_h$ from 20 to 70 ms.
- **Its shape:** the second gate is half shut at −70 mV and the first half open at −20 mV, so at a
  steady voltage at most about one channel in ten thousand is open (near −19 mV). After a step from a
  long stay at −100 mV to 0 mV the [open fraction](../../GLOSSARY.md#open-fraction) peaks at 0.39 after
  12 ms.
- **The current:** the host multiplies the open fraction by the population's permeability, abundance
  and availability, and moves calcium by the
  [constant-field flux](../../GLOSSARY.md#constant-field-flux) at
  [valence](../../GLOSSARY.md#valence) 2, the form of the route law `cells.route.constant_field@1`. The law
  is the one authority for that valence: a model whose calcium has another is refused. Which way a
  positive flux points is not declared.
- **Step rules:** the law names the kernel of its material term: how fast the flux changes with
  calcium's amount at each end, $P a\,v\,m^2 h\,A\,B(\mp x)/\text{volume}$ with $x = 2FV/RT$ and
  $B(x) = x/(e^x - 1)$. At every explicit [stage](../../GLOSSARY.md#stage) the host takes the sum of
  the two ends' slopes as calcium's rate at both, leaves out an end that is a held bath, and refuses
  the step where the largest rate times the step exceeds 1. For an ion other than sodium, potassium
  and chloride its parser asks for such a term, since the charge rule alone does not hold a scarce
  ion's amounts. The law declares no RK4 step bound, so no RK4 grid runs it.
- **Integration:** the host advances each gate by its exponential stage update.
- **Assumptions:** each gate lies between 0 and 1 and relaxes monotonically at fixed $V$. There is no
  temperature term: the source notes 21 °C for its model and applies none.
- **Left out:** calcium-dependent inactivation, gating charge, conformational energy and protein
  turnover.

## Sources

<!-- generated: provenance -->

Provenance: `parity` (moved from an older family; moving is not calibrating).

- **Source, as declared:** BETSE v1.5.0's Cav1p2 channel class, read as text
- **Place:** betse/science/channels/vg_ca.py:292 (class Cav1p2) at commit 5269a714; BETSE's docstring cites Carlin KP. et al. Characterization of calcium currents in functionally mature mouse spinal motoneurons. Eur. J. Neurosci., 2000 May, 12 (1624-34) (not read)
- **Licence of the numbers:** BSD-2-Clause, BETSE's licence (its LICENSE at 5269a714): the coefficients are taken from its source; no code is copied
- **Departures:** continuous gates in volts and seconds: the source's semi-implicit update clock is not adopted; the constant-field flux at the concentrations in place of the source's nominal reversal voltage
- **Work:** Alexis Pietak and Cecil Curry (2025). BETSE (BioElectric Tissue Simulation Engine) 1.5.0. https://github.com/betsee/betse

<!-- /generated -->

| Work | What was taken | Mark |
| --- | --- | --- |
| BETSE v1.5.0's `Cav1p2` channel class, at commit 5269a714 | The two-gate form, its coefficients, the gate powers and the 10 mV shift, converted to volts and seconds | FT: the class's text |
| Carlin and colleagues (2000), Eur. J. Neurosci. 12:1624–34, which that class cites | Nothing directly | unread |

**What is not established:** which measurement the numbers rest on. No work was read beyond the
class. The same file's CaV1.3 class holds the same equations without the 10 mV shift and cites another
work (Avery and colleagues, 1996; unread). So the numbers are another simulator's, moved here from an
older family; moving is not calibrating, which is why the provenance is `parity` with its citation
kept.

**Departures:** the gates follow the continuous equations, not the source's semi-implicit update; the
current is the constant-field flux at the concentrations, not the source's nominal reversal voltage
(131 mV).

## How it is checked

<!-- generated: tests -->

Declared test: [`tests/unit/test_kv1_channel_laws.py`](../../../../tests/unit/test_kv1_channel_laws.py), `test_the_calcium_law_meets_its_reference_and_each_plant_misses_it`.

<!-- /generated -->

The kernels are compared with an independent copy of the equations in the source's millivolts and
milliseconds, in 80-digit decimals, at 1,801 voltages across the domain, in NumPy and compiled, within
5e-14 of each value. Leaving out the 10 mV shift must miss the targets and the time constants, and $m^3 h$ for
$m^2 h$ must miss the open fraction.

The rows that plant another record of the law (a valence, no term, an RK4 bound) use a planted law
with this one's kernels. At a state with calcium entering, and at one with it leaving, its flux, the
charge it carries, the amounts it moves and its heat are the constant-field closed form's at valence 2,
in 50-digit decimals; a law and a model at valence 1 must miss all four. A law that says calcium is +1,
or a model that does, is refused by name; so are a law without the material term, and an RK4 grid.

The material term is compared with central differences of the stage's own flux, over voltages and
openings, in a world of two cells that share one small node. Exchanging the two ends' factors, keeping
the term at one end only, and leaving it out at the node must each miss, and the rate is never less
than the fastest rate of calcium's own block there. A step above the bound is refused.

Rows of the older calcium catalogue's test run the source's unchanged class out of process and compare
it with these kernels, which that catalogue (`cells.model.resolved_tissue@8`'s) still calls. No run was compared
with a measurement.

## Status

<!-- generated: status -->

Not stated: no record states a level for this piece.

<!-- /generated -->

## Links

<!-- generated: links -->

- Declared in [`src/cells/laws/channels/cav1p2_m2h.py`](../../../../src/cells/laws/channels/cav1p2_m2h.py) (`cells.laws.channels.cav1p2_m2h`).
- Kernels: `kinetics`, `cells.laws.channels.cav1p2_m2h.kinetics`; `opening`, `cells.laws.channels.cav1p2_m2h.opening`.
- Runs in `cells.model.resolved_pump_tissue@3`.
- Manifest entry: (law, `cells.channel.cav1p2_m2h@1`), from `python -m cells declarations --out FILE` ([the format](../../DECLARATIONS_FORMAT.md)).
- In the Laws library: `select=laws:cells.channel.cav1p2_m2h@1`.

<!-- /generated -->
