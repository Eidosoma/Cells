# ATP-driven transport of one kind of ion or molecule, on held fuel (`cells.atp_driven_transporter_mass_action_positive@2`)

**In one sentence:** A membrane pump that spends one ATP per cycle, from a supply held constant, to move a fixed number of ions or molecules of one kind, charged or not.

## In plain words

Cells keep some ions and molecules scarce on one side of a membrane by pumping them uphill, and pay
for it with ATP. In each cycle this law splits one ATP and moves one to four of one kind of cargo to
the other side. The cargo may carry any charge, so the
[membrane voltage](../../GLOSSARY.md#membrane-voltage) helps or hinders it. The pump runs forward
while ATP's energy exceeds what the climb costs, stalls where the two balance, and runs backward
beyond. The ATP, ADP and phosphate are held: the law reads them and never uses them up, and the
books record what holding them supplies. A [definition](../../GLOSSARY.md#definition) gives the
capacity, the cargo per ATP and two half-saturations. The law gives no number. It models no pump
protein, and it leaves out counter-transport, regulation and fuel that runs out.

## Seen from each field

- **Biology:** primary active transport of one species, such as a calcium pump that keeps a cell's
  free calcium scarce.
- **Chemistry:** ATP hydrolysis coupled to transport in one cycle, with a saturation in the cargo
  and in ATP on the side it pumps from.
- **Physics:** an energy converter. The rate is a one-way flux times one less the exponential of the
  cycle's free energy over RT, so it stalls where that energy is zero.
- **Computing:** data only, with no kernel and no state: a factored form that the cycle kind's one
  program runs.

## At a glance

<!-- generated: at-a-glance -->

| | |
| --- | --- |
| Piece | Law, interface `cells.cycle_law@1` ([its fields](../../DECLARATIONS_FORMAT.md#cycle-laws)) |
| ID | `cells.atp_driven_transporter_mass_action_positive@2`; definitions write `cells.atp_driven_transporter_mass_action_positive@2` |
| Runs in | `cells.transporter@1`, its host, in `cells.resolved_pump_tissue@3`. Definitions of `cells.resolved_pump_composite@1` and `cells.resolved_pump_tissue@3` can declare it |
| Provenance | `parity`: moved from an older family; moving is not calibrating |

<!-- /generated -->

## What it reads and changes

<!-- generated: touches -->

| Role | What | Unit | Which way is positive |
| --- | --- | --- | --- |
| Reads | `rapid_binding@1`, current at each inner stage | | |
| Changes | `role@N`: `-stoichiometry` per cycle | | inward-positive, per forward cycle |
| Changes | `role@P`: `stoichiometry` per cycle | | inward-positive, per forward cycle |
| Changes | `ATP@N`: -1 per cycle | | inward-positive, per forward cycle |
| Changes | `ADP@N`: 1 per cycle | | inward-positive, per forward cycle |
| Changes | `Pi@N`: 1 per cycle | | inward-positive, per forward cycle |

Energy role: not yet extracted; the law template has no energy role yet.

<!-- /generated -->

## The mathematics

<!-- generated: bounds -->

| Declared | Value | Unit |
| --- | --- | --- |
| Stage term | `stage_term` |  |
| Material term | `material_term` |  |
| Fuel kinds | `maintained_held_rows@1` |  |

<!-- /generated -->

A [population](../../GLOSSARY.md#population) sits on one [patch](../../GLOSSARY.md#patch), whose two
ends are its N and P (N is the cell where the definition says `"N": "a"`). It declares a capacity
$k$ (fmol cycles/s), $n$ (an integer, 1 to 4) and half-saturations $K$ and $K_\text{ATP}$ (mM), and
$v$ is its [availability](../../GLOSSARY.md#availability) (0 to 1). $z$ is the cargo's
[valence](../../GLOSSARY.md#valence), $c_N$ and $c_P$ its concentrations (mM),
$\psi = F(\varphi_N - \varphi_P)/RT$ with the ends' potentials in V, $\mu^\circ$ the species
registry's standard potentials at its standard concentration $c_0$ (mM), and the fuel's
concentrations are at N. The [cycle free energy](../../GLOSSARY.md#cycle-free-energy) over $RT$ and
the rate (fmol cycles/s) are

$$x = \frac{\mu^\circ_\text{ADP} + \mu^\circ_\text{Pi} - \mu^\circ_\text{ATP}}{RT} + \ln\frac{[\text{ADP}][\text{Pi}]}{[\text{ATP}]\,c_0} + n \ln\frac{c_P}{c_N} - n z \psi,$$

$$J = k v S\,(1 - e^x), \qquad S = \frac{1}{1 + (K/c_N)^n}\cdot\frac{1}{1 + K_\text{ATP}/[\text{ATP}]}.$$

- **What moves:** per forward cycle $n$ of the cargo leave N for P, so $nz$ charges go from N to P.
  The kind books these amounts at both ends in the shared [inventory](../../GLOSSARY.md#inventory),
  the charge through the field, and the [heat](../../GLOSSARY.md#heat) $-RT\,J\,x$, which is never
  negative.
- **Held fuel:** ATP, ADP and Pi are neutral [species rows](../../GLOSSARY.md#species-row) at N,
  read and never moved. The kind records the maintenance's supply of each, and its
  [work](../../GLOSSARY.md#work), $-J$ times the fuel's part of the free energy. A held row that a
  route or another population moves is refused. Fuel that is moved is refused: finite fuel waits for
  a consumer.
- **The stall:** $J = 0$ where $n$ times the cargo's electrochemical climb equals the fuel's drive.
  The capacity and the half-saturations do not move it.
- **What it claims:** the one-to-$n$ coupling and the free energies of the species registry. The
  form is the engine's own mass-action completion, and no number is the law's. It claims no
  mechanism of any pump protein, no counter-transport and no kinetic constant.
- **Domain:** $|x| \le 80$; positive concentrations and half-saturations. A state outside it is
  refused, never clipped.
- **Step rules:** the kind bounds a charged cargo's charge slope, at both ends, and the population's
  own material rate, the cargo charged or neutral: over its two rows, the sum of
  $|\nu_k\, \partial J/\partial n_k|$ (1/s; $\nu_k$ the row's count and $n_k$ its amount in fmol),
  given to each of them. Held fuel and a held bath's rows are left out. The law declares both terms,
  so its moves at a closed compartment's node are admitted
  ([refusal 4](../../../CLOSED_COMPARTMENT_DESIGN.md)). A cargo that version 1's proton buffer holds
  is refused by name: its read has no derivative for the rate. RK4 runs are refused, as for every
  kind.
- **At a binding closure:** it declares the read `rapid_binding@1` and base forms, so where a
  closure holds the cargo it reads the free amount and moves the total, and the material rate runs
  through the closure's derivative.
- **One law per pathway:** beside this law, for the same species on the same patch, the kind refuses
  the inner model's own calcium pump and version 1's neutral and proton laws. Several populations of
  this law are admitted.
- **Left out:** a pH band (a proton's pump on transformed potentials has a law of its own), finite
  fuel, regulation, and any temperature dependence beyond $RT$.

## Sources

<!-- generated: provenance -->

Provenance: `parity` (moved from an older family; moving is not calibrating).

- **Source, as declared:** an ATP-driven transporter of one species, in the Na/K law's mass-action form (laws/pumps/nak_atp_mass_action_positive.py; docs/KINETIC_PUMP_PROCESS.md): the engine's own completion of that form
- **Place:** docs/CALCIUM_STORE_AND_CHANNELS_DESIGN.md §6.3
- **Licence of the numbers:** no numbers taken: the law is a form, its parameters a definition's values
- **Departures:** one species of any valence, where version 1 moves a neutral one; held fuel only, where version 1 also runs on finite fuel; its ions per ATP are a declared parameter, with no measured value
- **Works, as data:** none declared

<!-- /generated -->

The form is the inner model's sodium-potassium pump's, with one cargo of any valence
([the kinetic pump's note](../../../KINETIC_PUMP_PROCESS.md)), as
[the calcium note](../../../CALCIUM_STORE_AND_CHANNELS_DESIGN.md) §6.3 states it. No number was
taken from any work. One calcium per ATP, where a definition declares it, is that definition's
choice.

**What it supersedes, and when each retires.** Nothing retires at its landing, and no date below is
set. A new definition that moves one species by ATP, on held fuel and with no pH band, takes this
law.

| Law | Who runs it | When it retires |
| --- | --- | --- |
| `cells.atp_driven_transporter_mass_action_positive@1` (a neutral cargo) | FR-50's judged worlds, and tests | Superseded on held fuel: at valence zero this law is its equation. It also runs on finite fuel, which this law does not. Either it goes in a commit of its own after the calcium plan's step 5, when FR-50's driver and the tests move to this law and version 1's fields leave (recommended there), or with version 1's layout, when those worlds are judged again |
| `cells.proton_atp_mass_action_positive@1` (a proton) | FR-4's and FR-5's judged worlds | It folds into this law, with the form's pH band, when those worlds are judged again. Until then it stays: it has a band and a closure read that this law does not declare |
| `cells.ca_atp_mass_action_positive@1` (the inner model's own) | the inner model's worlds | When the sodium-potassium and calcium pumps move onto the kind ([the roadmap](../../../CORE_LAWS_ROADMAP.md), family 2) |
| `cells.nak_atp_mass_action_positive@1` (the inner model's own) | the inner model's worlds | With the same item, into a cycle law of its own: it moves two ions, so it is another mechanism |
| the older family's two calcium pump laws | that family | At its deletion; the two rate functions they are built on stay, since the inner model's own calcium pump calls them |

## How it is checked

<!-- generated: tests -->

Declared test: [`tests/unit/test_cycle_kind.py`](../../../../tests/unit/test_cycle_kind.py), `test_the_pump_and_the_symports_meet_their_equations_and_each_plant_misses_its_criteria`.

<!-- /generated -->

The kind's own evaluation is compared with the rate equation above in its rational form, one
denominator and no $1 - e^x$, and with the hydrolysis and the cargo's electrochemical potentials, in
60-digit decimals from the SI constants, never through the form: at 24 random states and at the
domain's edges and the stall from two more, for valences 2, 1, −1 and 0, one to four per ATP, with N
the cell or the bath. Fluxes are held to 2e-13 of the one-way scale, and the slopes at both ends to
1e-12. The criteria are the rate, the detailed balance with the heat's value and sign and the work,
the moved amounts, the fuel's supply and the charge, the sign on either side of the stall, the
slopes and the domain. Each plant must miss exactly the criteria it is planted against: the
electrical sign, $n$ applied to $K$ twice, ATP's factor left out, the cargo's factor at the far side
or without its power, no phosphate made, the cycle run backward, a standard part added, the held
part added to, and the domain at 79. At valence zero the law is compared with version 1's own kernel
(plant: a half-saturation larger by 1e-9). The reference is independent of the forms, not
code-blind.

At valence 2 and one per ATP it meets a pinned external simulator's own calcium-pump function, run
unmodified and out of process at six states, an independent scalar form and the inner model's own
calcium pump's kernel, to 3e-12. A small closed world with the sodium-calcium exchange converges at
second order to an independent ODE of its cycles, heat, work, amounts and voltage. Other rows run
closed worlds forward and backward, under both heat bookings: each end's amounts follow the cycles,
the voltage follows the charge, the heat grows, the work is the cycles times the fuel's drive and
every [ledger](../../GLOSSARY.md#ledger) closes. The stage's charge slope and the population's own
material rate are the reference's at both ends, over the cargo's rows and not the held fuel's.
Populations outside the law's counts, half-saturations, fuel or domain, on RK4, or beside a second
law of the pathway are refused by name. At a [store's](../../GLOSSARY.md#store) node the law is
admitted, and a copy of it without its terms is refused. Beside a calcium binder under a closure it
reads the free calcium. Each has a planted error. No run was compared with a measurement.

## Status

<!-- generated: status -->

Not stated: no record states a level for this piece.

<!-- /generated -->

## Links

<!-- generated: links -->

- Declared in [`src/cells/laws/pumps/atp_transporter_v2.py`](../../../../src/cells/laws/pumps/atp_transporter_v2.py) (`cells.laws.pumps.atp_transporter_v2`).
- Runs in `cells.transporter@1`.
- Manifest entry: (law, `cells.atp_driven_transporter_mass_action_positive@2`), from `python -m cells declarations --out FILE` ([the format](../../DECLARATIONS_FORMAT.md)).
- In the Laws library: `select=laws:cells.atp_driven_transporter_mass_action_positive@2`.

<!-- /generated -->
