# Exchange of three sodium ions for one calcium ion, with a synthetic rate (`cells.sodium_calcium_exchange_symmetric_barrier@1`)

**In one sentence:** Three sodium ions cross a membrane one way for each calcium ion that crosses the other way, each exchange carrying one charge, at a rate whose form is synthetic.

## In plain words

Cells keep free calcium scarce, and one way to push it out is to let sodium in. In each cycle this
law swaps three sodium ions for one calcium ion. It spends no fuel: sodium running downhill pays for
calcium climbing. Each swap carries one charge, so the
[membrane voltage](../../GLOSSARY.md#membrane-voltage) helps to set its direction: the swap stops at
the voltage where the two gradients balance and runs backward beyond it. That balance is the only
part that measurements support. The rest is synthetic: how fast the swap runs, how it saturates and
how the voltage splits between its two directions are a made-up form, with no measured number in it.
A definition gives the capacity and both half-saturations. The law leaves out inactivation,
regulation, other swap ratios, leaks and any competition between the two ions. It is not a model of
any exchanger protein.

## Seen from each field

- **Biology:** sodium-calcium exchange, forward when calcium leaves the cell. It can also run
  backward and bring calcium in, as when the cell holds much sodium or its voltage is high.
- **Chemistry:** a reversible exchange of two ions in one cycle, with a saturation in each ion that
  counts both sides of the membrane.
- **Physics:** one cycle driven by two electrochemical gradients. The rate is a one-way flux times
  one less the exponential of the cycle's free energy over RT, so it stalls where that energy is
  zero.
- **Computing:** data only, with no kernel and no state: a monomial form that the cycle kind's one
  program runs.

## At a glance

<!-- generated: at-a-glance -->

| | |
| --- | --- |
| Piece | Law, interface `cells.cycle_law@1` ([its fields](../../DECLARATIONS_FORMAT.md#cycle-laws)) |
| ID | `cells.sodium_calcium_exchange_symmetric_barrier@1`; definitions write `cells.sodium_calcium_exchange_symmetric_barrier@1` |
| Runs in | `cells.transporter@1`, its host, in `cells.resolved_pump_tissue@3`. Definitions of `cells.resolved_pump_composite@1` and `cells.resolved_pump_tissue@3` can declare it |
| Provenance | `cited`: taken from a cited source |

<!-- /generated -->

## What it reads and changes

<!-- generated: touches -->

| Role | What | Unit | Which way is positive |
| --- | --- | --- | --- |
| Reads | `rapid_binding@1`, current at each inner stage | | |
| Changes | `Na@N`: 3 per cycle | | inward-positive, per forward cycle |
| Changes | `Na@P`: -3 per cycle | | inward-positive, per forward cycle |
| Changes | `Ca@N`: -1 per cycle | | inward-positive, per forward cycle |
| Changes | `Ca@P`: 1 per cycle | | inward-positive, per forward cycle |

Energy role: not yet extracted; the law template has no energy role yet.

<!-- /generated -->

## The mathematics

<!-- generated: bounds -->

| Declared | Value | Unit |
| --- | --- | --- |
| Fuel kinds | none |  |

<!-- /generated -->

A [population](../../GLOSSARY.md#population) sits on one [patch](../../GLOSSARY.md#patch), whose two
ends are its N and P (N is the cell where the definition says `"N": "a"`). It declares a capacity $k$
(fmol cycles/s) and half-saturations $K_\text{Na}$ and $K_\text{Ca}$ (mM), and $v$ is its
[availability](../../GLOSSARY.md#availability) (0 to 1). With each ion's concentration at an end in
mM, the ends' potentials $\varphi$ in V, $\psi = F(\varphi_N - \varphi_P)/RT$, and

$$a = \frac{[\text{Na}]_N}{K_\text{Na}}, \quad b = \frac{[\text{Na}]_P}{K_\text{Na}}, \quad c = \frac{[\text{Ca}]_N}{K_\text{Ca}}, \quad d = \frac{[\text{Ca}]_P}{K_\text{Ca}},$$

the [cycle free energy](../../GLOSSARY.md#cycle-free-energy) over $RT$ and the rate (fmol cycles/s)
are

$$x = 3 \ln\frac{[\text{Na}]_N}{[\text{Na}]_P} + \ln\frac{[\text{Ca}]_P}{[\text{Ca}]_N} + \psi, \qquad J = k v\, \frac{b^3 c\, e^{-\psi/2} - a^3 d\, e^{\psi/2}}{(1 + a^3 + b^3)(1 + c + d)} = k v S\, (1 - e^x),$$

with $S = b^3 c\, e^{-\psi/2} / [(1 + a^3 + b^3)(1 + c + d)]$.

- **What moves:** per forward cycle three sodium ions leave P for N, and one calcium ion leaves N for
  P, so one elementary charge goes from P to N. The kind books these amounts at both ends in the
  shared [inventory](../../GLOSSARY.md#inventory), the charge through the field, and the
  [heat](../../GLOSSARY.md#heat) $-RT\,J\,x$, which is never negative. No work is booked and no fuel
  is used.
- **The reversal:** $J = 0$ at $\varphi_N - \varphi_P = 3 E_\text{Na} - 2 E_\text{Ca}$, with the Nernst
  potentials $E_\text{Na} = (RT/F) \ln([\text{Na}]_P/[\text{Na}]_N)$ and $E_\text{Ca} = (RT/2F) \ln([\text{Ca}]_P/[\text{Ca}]_N)$.
  The capacity and the half-saturations do not move it.
- **What it claims:** the 3:1 coupling, so the reversal, and no more. The denominator, the equal
  split of the charge over the two directions and every number are synthetic. The sodium and calcium
  factors multiply, so the ions do not compete. Each one-way flux changes by a factor 2 in
  $(2 \ln 2) RT/F$, 36 mV at 298 K, at every concentration.
- **Domain:** $x \le 80$, one-sided, with no voltage bound of its own; positive concentrations and
  half-saturations. A state outside it is refused, never clipped. The older law of the same rate
  (`ncx_3na_1ca_symmetric_barrier@1`) kept $|x| \le 80$ and $|V| \le 0.15$ V.
- **Step rules:** at each [stage](../../GLOSSARY.md#stage) the kind bounds its charge slope, at both
  ends. Its material slope is not bounded: the kind's material term counts no charged
  [species row](../../GLOSSARY.md#species-row) that crosses, so a world with scarce calcium must choose
  a step small enough for it. The law declares no step term, so its moves at a closed compartment's
  node are refused ([refusal 4](../../../CLOSED_COMPARTMENT_DESIGN.md)). RK4 runs are refused, as for
  every kind.
- **At a binding closure:** it declares the read `rapid_binding@1` and base forms, so where a closure
  holds calcium or sodium it reads the free amount and moves the total.
- **Left out:** inactivation, regulation by either ion, other coupling ratios and transport modes,
  leaks, competition between the ions, and any temperature dependence beyond $RT$.

## Sources

<!-- generated: provenance -->

Provenance: `cited` (taken from a cited source).

- **Source, as declared:** only the 3:1 coupling, so the reversal, is supported: measured reversals of the sodium-calcium exchange current of guinea-pig ventricular cells, in giant patches (1992) and in whole cells (2002). The denominator, the equal voltage split and every number are synthetic: no source gives them
- **Place:** the abstracts of the works below (1992, item e; 2002, the conclusion); none was read in full
- **Licence of the numbers:** no number taken: the capacity and the two half-saturations are a definition's values, none of them measured for this form
- **Departures:** the denominator, a sodium factor times a calcium factor, is synthetic: it has no competition between the two ions, which the 1992 abstract reports at the inner face; the equal voltage split is synthetic: each one-way flux changes by a factor 2 in 36 mV (298 K), where the 1992 abstract reports currents that change by a factor 2 in about 100 mV, and voltage dependences that move with the concentrations; one mode at 3:1: a 2000 abstract concludes 4:1 or a variable coupling in patches of the same cells, and a 2004 abstract reports flux ratios near 3.2, two minor modes and a net current and a calcium flux that can reverse at different potentials; no inactivation, no regulation by either ion, no leak mode and no temperature dependence beyond RT
- **Work:** Matsuoka S and Hilgemann DW (1992). Steady-state and dynamic properties of cardiac sodium-calcium exchange. Ion and voltage dependencies of the transport cycle. doi:10.1085/jgp.100.6.963
- **Work:** Hinata M, Yamamura H, Li L, Watanabe Y, Watano T, Imaizumi Y and Kimura J (2002). Stoichiometry of Na+-Ca2+ exchange is 3:1 in guinea-pig ventricular myocytes. doi:10.1113/jphysiol.2002.025866
- **Work:** Fujioka Y, Komeda M and Matsuoka S (2000). Stoichiometry of Na+-Ca2+ exchange in inside-out patches excised from guinea-pig ventricular myocytes. doi:10.1111/j.1469-7793.2000.t01-2-00339.x
- **Work:** Kang TM and Hilgemann DW (2004). Multiple transport modes of the cardiac Na+/Ca2+ exchanger. doi:10.1038/nature02271

<!-- /generated -->

| Work | What was taken | Mark |
| --- | --- | --- |
| Matsuoka and Hilgemann (1992), J. Gen. Physiol. 100:963–1001 | The 3:1 coupling: measured reversals "close to the equilibrium potential expected for a 3 Na to 1 Ca exchange". Against this form: the two ions compete at the inner face, the currents change by a factor 2 in about 100 mV, and their voltage dependence moves with the concentrations. No numbers | ABS |
| Hinata and colleagues (2002), J. Physiol. 545:453–461 | The 3:1 coupling, their conclusion in whole cells. No numbers | ABS |
| Fujioka, Komeda and Matsuoka (2000), J. Physiol. 523:339–351 | Against the coupling: "either 4Na:1Ca or variable", in patches of the same cells | ABS |
| Kang and Hilgemann (2004), Nature 427:544–548 | Against one mode: flux ratios of about 3.2, two minor transport modes, and a net current and a calcium flux that "can reverse at different membrane potentials". It says that calcium flux equilibria had indicated 3:1 and current reversals a ratio closer to 4:1 | ABS |

The abstracts and records were read at Europe PMC on 25 November 2026. Two works support the coupling
(1992, 2002) and two speak against a single 3:1 mode (2000, 2004); each is one study, an indication.
Nothing else in the law rests on a source. **The departures** are the rest of the law: the
denominator, the equal split of the charge, the single mode, and the absence of regulation.

**The same rate elsewhere:** an older model family ran it as `ncx_3na_1ca_symmetric_barrier@1`. No
live model runs that kernel. It goes when that family leaves the tree. A four-state exchange cycle is
planned for cardiac cells ([the cardiac note](../../../HUMAN_CARDIAC_LAWS_DESIGN.md)), a second form of
this mechanism. Which of the two stays is decided when it lands.

## How it is checked

<!-- generated: tests -->

Declared test: [`tests/unit/test_cycle_kind.py`](../../../../tests/unit/test_cycle_kind.py), `test_the_exchange_meets_its_rate_equation_and_each_plant_misses_its_criteria`.

<!-- /generated -->

The kind's own evaluation is compared with the rate equation above and the two ions'
electrochemical potentials, in 60-digit decimals from the SI constants, never through the form: at 24
random states and at 12 states of the domain's edges, for six sets of capacity and half-saturations,
in NumPy and compiled. Fluxes are held to 2e-13 of the one-way scale, and the slopes to 1e-12. The
criteria are the rate, the detailed balance with the heat's value and sign, the moved amounts and
charge, the reversal and the sign on either side, the slopes and the domain. Each plant must miss
exactly the criteria it is planted against. Ten are changed laws (the split reversed or left out, a
half-saturation's power, activities against 1 M, a constant off by 1e-9, the orders of the two ions
exchanged or taken at the other ends, a one-sided calcium factor, four sodium, the cycle run
backward) and four are changes to the kind's evaluation. The plants of the form keep the reversal
and the detailed balance, which are the counts', and that is what the law claims.

Other rows run a small closed world. Each end's amounts follow the cycles, the voltage follows the
charge, the heat grows and every [ledger](../../GLOSSARY.md#ledger) closes, in both directions and
under both heat bookings. The stage's charge slope is the reference's at both ends and refuses a step
1% beyond it. A population with a stoichiometry of its own, a mode that creates charge, a wrong or
missing species, a zero half-saturation, a held ion, a start outside the domain or RK4 is refused by
name. Beside a calcium binder under a closure it reads the free calcium. A run from a checkpoint
file continues bit for bit. Each has a planted error. No run was compared with a measurement.

## Status

<!-- generated: status -->

Not stated: no record states a level for this piece.

<!-- /generated -->

## Links

<!-- generated: links -->

- Declared in [`src/cells/laws/cycles/sodium_calcium_exchange_symmetric_barrier.py`](../../../../src/cells/laws/cycles/sodium_calcium_exchange_symmetric_barrier.py) (`cells.laws.cycles.sodium_calcium_exchange_symmetric_barrier`).
- Runs in `cells.transporter@1`.
- Manifest entry: (law, `cells.sodium_calcium_exchange_symmetric_barrier@1`), from `python -m cells declarations --out FILE` ([the format](../../DECLARATIONS_FORMAT.md)).
- In the Laws library: `select=laws:cells.sodium_calcium_exchange_symmetric_barrier@1`.

<!-- /generated -->
