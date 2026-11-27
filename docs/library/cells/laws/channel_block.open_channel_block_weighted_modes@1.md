# Voltage-dependent block of open channels (`cells.channel_block.open_channel_block_weighted_modes@1`)

**In one sentence:** A charged blocker held on one side of the membrane plugs open channels to an extent set by the voltage, lowering the current they carry.

## In plain words

Some open [channels](../../GLOSSARY.md#channel) carry less current than they could, because a
charged molecule or ion enters the pore and plugs it. How much of the time it sits there depends on
how concentrated it is and on the [membrane voltage](../../GLOSSARY.md#membrane-voltage), which
pulls the charge into the pore or pushes it out. This law gives the fraction of a channel
[population](../../GLOSSARY.md#population) that is not plugged, and the host multiplies the
population's current by it. A population may mix up to four kinds of block, each with its own
strength and its own dependence on voltage. The plug is always taken to be at balance: the law
leaves out how fast it comes and goes. It also leaves out where the blocker comes from: its
concentration is held at a declared value, and none is taken from the solution when it binds.

## Seen from each field

- **Biology:** voltage-dependent open-channel block. A positive blocker from the inside binds more
  tightly as the voltage rises, so the population passes current more easily inward than outward.
- **Chemistry:** reversible binding of one blocker to one site in each kind of block, with a
  dissociation constant that is exponential in voltage. Binding is trace: the blocker's amount in
  solution does not change.
- **Physics:** the blocker moves through part of the membrane's electric field, so each kind of
  block is a logistic function of voltage; the fraction is their weighted mean.
- **Computing:** a pure function of a reference voltage, the blocker's concentration and each
  mode's constants, with no state. Its sums run over a static axis, in declared order.

## At a glance

<!-- generated: at-a-glance -->

| | |
| --- | --- |
| Piece | Law, interface `cells.channel_block_law@1` ([its fields](../../DECLARATIONS_FORMAT.md#family-interfaces)) |
| ID | `cells.channel_block.open_channel_block_weighted_modes@1`; definitions write `cells.channel_block.open_channel_block_weighted_modes@1` |
| Runs in | `cells.model.resolved_pump_tissue@3`, its host. Definitions of `cells.model.resolved_pump_composite@1` and `cells.model.resolved_pump_tissue@3` can declare it |
| Provenance | `cited`: taken from a cited source |

<!-- /generated -->

## What it reads and changes

<!-- generated: touches -->

| Its interface's own field | Value | Unit |
| --- | --- | --- |
| `max_modes` | `4` |  |
| `max_steepness` | `8.0` | 1 |
| `k0_range_mM` | `[1e-15, 1000000000000000.0]` | mM |
| `blocker_range_mM` | `[0.0, 1000.0]` | mM |
| `sides` | `[["outside", 1], ["inside", -1]]` |  |

Energy role: not yet extracted; the law template has no energy role yet.

<!-- /generated -->

## The mathematics

<!-- generated: bounds -->

| Declared | Value | Unit |
| --- | --- | --- |
| Domain check | `cells.laws.channels.open_channel_block.domain_valid` |  |

<!-- /generated -->

A population declares a blocker of valence $z_B$ (a nonzero integer) at the constant concentration
$c_B$ (mM) on one side, and up to four modes $k$, each with a weight $w_k$ (1), a dissociation
constant at zero voltage $K_k(0)$ (mM) and a steepness $m_k$ (1). With $V_\text{ref}$ the reference
voltage (V), $F/(RT)$ in 1/V, and $s$ the blocker's side, $+1$ outside and $-1$ inside:

$$K_k = K_k(0)\,e^{a_k V_\text{ref}}, \qquad a_k = s\,\operatorname{sgn}(z_B)\,m_k\,\frac{F}{RT}$$

$$\theta_k = \frac{c_B}{c_B + K_k}, \qquad 1 - \theta_k = \frac{K_k}{c_B + K_k}, \qquad u = \frac{\sum_k w_k\,(1 - \theta_k)}{\sum_k w_k}$$

$$\left|\frac{du}{dV_\text{ref}}\right| \le \frac{\sum_k w_k\,|a_k|\,\theta_k\,(1 - \theta_k)}{\sum_k w_k}$$

- **The fraction:** $u$ is the unblocked fraction, and the host multiplies every permeant ion's flux
  by it. Each fraction is formed directly, and both sums run in declared order. So $u$ is exactly 1
  without a blocker, and it keeps its relative accuracy where nearly everything is blocked.
- **The reference voltage** is the one the population's declared shift gives its block (FR-64).
  Without a shift it is the patch voltage (inside less outside). With one, the population's
  `voltage_shift.block` subtracts either the reversal potential $E$ of one of its moved
  [permeant](../../GLOSSARY.md#permeant) ions, or a declared slope times the pH's distance from
  its reference.
- **The steepness** is $m_k = |z_B|\,\delta_k$, with the electrical distance $\delta_k$ in [0, 1], or
  a declared effective valence above 0, which may exceed the blocker's charge. A mode declares
  exactly one of the two.
- **The slope bound** is the host's: its per-stage rules add the block's part to the population's.
- **Domain:** $m_k \le 8$, $K_k(0)$ in [1e-15, 1e15] mM, $c_B$ in [0, 1e3] mM, at most four modes,
  and weights in [0, 1] that sum to 1 within 8 units in the last place. Every intermediate is then
  a normal floating-point number, which matters because compiled code flushes smaller ones to zero.
  A definition outside it is refused, and so is a step where $K_k$ or $c_B + K_k$ is not finite and
  normal; nothing is clipped.
- **Left out (version 1's limits):** the blocker is held at a declared constant concentration, not a
  [species row](../../GLOSSARY.md#species-row); the block has no kinetics; and binding is trace, with
  no count.
- **Scope (D355, D356):** `cells.channel.kir2p1_mh2@1`'s own gates read absolute voltage, so they do not shift
  with external potassium. A world in which external potassium changes declares this block, shifted
  by the potassium reversal, on an always-open potassium population. That composition stays
  development-only for changes of external potassium (D391).
- **Scope of the block on a reversal (D355):** it is supported for changes of that ion outside the
  cell only.
  - When external potassium changes, a non-blind two-lab replay (Lean commit 48fb7e0f, D378; run on
    engine revision 7ca7c9c1) finds the half-conductance shift tracking the measured reversal at
    about 0.97 to 0.98 mV per mV.
  - One lab finds that raising internal potassium moves the half-block voltage about +5 mV, where
    $V - E_\text{K}$ predicts −36 mV. That is an indication.

## Sources

<!-- generated: provenance -->

Provenance: `cited` (taken from a cited source).

- **Source, as declared:** Woodhull's single-site block (A. M. Woodhull, 1973, J. Gen. Physiol. 61:687-708, PMID 4541078), applied in up to four weighted modes of one channel population
- **Place:** the single-site block's voltage dependence; the weighted form and the admitted domain are fr51-channel-block-v1's (validation/fr51/REGISTRATION.md §1)
- **Licence of the numbers:** no numbers taken: the law is a form, its blocker and its modes a definition's values
- **Departures:** up to four modes of one population, each with its own K(0) and steepness; a mode's steepness may be an effective valence in place of the charge times the electrical distance, and may exceed the blocker's charge; at equilibrium at every voltage: no binding or unbinding rates
- **Work:** Woodhull AM (1973). Ionic blockage of sodium channels in nerve. doi:10.1085/jgp.61.6.687

<!-- /generated -->

| Work | What was taken | Mark |
| --- | --- | --- |
| A. M. Woodhull (1973), J. Gen. Physiol. 61:687–708 | The law's form: single-site block by a charged blocker, whose dissociation constant is exponential in voltage through an electrical distance. No numbers | unread: the record (title, journal, pages and identifiers) was checked against Europe PMC on 23 November 2026, and the full text was not read (FR-51's registration, §6) |
| Yan and Ishihara (2005), J. Physiol. 563:725–744 | The motive for weighted modes: two Kir2.1 populations with different block sensitivities. No numbers | ABS, as FR-51's registration quotes it |
| Shin and Lu (2005), J. Gen. Physiol. 125:413–426 | The motive for an effective valence: an apparent valence of spermine block near 5, above spermine's charge of 4. No numbers | ABS, as FR-51's registration quotes it |
| Lopatin and Nichols (1996), J. Gen. Physiol. 108:105–113 | The motive for the reversal reference: rectification that shifts with the potassium reversal. No numbers | ABS, as FR-51's registration quotes it |

Each motive rests on one study, so it is an indication, not a claim.

**Departures:** up to four modes in one population, where the source's block has one site; an
effective valence in place of the charge times the electrical distance; and a block taken at
equilibrium at every voltage.

## How it is checked

<!-- generated: tests -->

Declared test: [`tests/unit/test_surface_pump_v3_populations.py`](../../../../tests/unit/test_surface_pump_v3_populations.py), `test_each_registered_plant_fails_its_criterion`.

<!-- /generated -->

On the host, the inner model's clamped current, unblocked fraction and per-stage terms are compared
with the laws' closed forms evaluated to 60 digits: eleven cases, at 37 voltages from −0.120 to
0.060 V, at the ion's reversal and half a millivolt either side of it, by the registration's bands
(1e-12 relative). The declared test plants twelve errors in the same comparison, and each must fail
it. Among them are a flipped side, the modes' weights swapped, a reversal read with the wrong sign
of its valence, the fraction written as one less the blocked sum, and an effective valence capped
at the blocker's charge.

The registered comparison `fr51-channel-block-v1` ran once, against references written without
sight of the code: every criterion passed, and all eleven planted errors judged against those
references were caught (D377). Its scope is the registration's cases, in the admitted domain, at
one temperature. It says nothing about any one channel's numbers, which a definition gives.

## Status

<!-- generated: status -->

Not stated: no record states a level for this piece.

<!-- /generated -->

## Links

<!-- generated: links -->

- Declared in [`src/cells/laws/channels/open_channel_block.py`](../../../../src/cells/laws/channels/open_channel_block.py) (`cells.laws.channels.open_channel_block`).
- Kernels: `dissociation`, `cells.laws.channels.open_channel_block.dissociation`; `fractions`, `cells.laws.channels.open_channel_block.fractions`; `unblocked_fraction`, `cells.laws.channels.open_channel_block.unblocked_fraction`; `slope`, `cells.laws.channels.open_channel_block.slope`; `domain_valid`, `cells.laws.channels.open_channel_block.domain_valid`.
- Runs in `cells.model.resolved_pump_tissue@3`.
- Manifest entry: (law, `cells.channel_block.open_channel_block_weighted_modes@1`), from `python -m cells declarations --out FILE` ([the format](../../DECLARATIONS_FORMAT.md)).
- In the Laws library: `select=laws:cells.channel_block.open_channel_block_weighted_modes@1`.

<!-- /generated -->
