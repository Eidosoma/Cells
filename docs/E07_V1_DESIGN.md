# E07-v1 renewal stage: donor copies with an isolated boundary set

**Status: PROPOSED (13 November 2026), not registered.** No engine run belongs to this
design until the lead registers its protocol. The user chose option (c) on 13 November:
donor copies are the main route, and isolated newcomers with fast junction formation form
a boundary set. The design builds on the literature-rule turnover pre-screen
([Progress](../PROGRESS.md); evidence
`/mnt/workspaces/Cells/heredity-turnover-literature-20261111-01/`). The parent design is
[HEREDITY_FIRST_EXPERIMENT.md](HEREDITY_FIRST_EXPERIMENT.md).

## 1. What a donor copy may carry (D139)

D139, as written: "'Inherit' is excluded. No junction gate state carries across a
replacement." Donor copies are "a different heredity claim, an inheritance route for the
written state, and its arms are labelled as such." The engine
(`scheduled_cell_replacement@1`, [CELL_REPLACEMENT.md](CELL_REPLACEMENT.md)) implements
this as follows.

| A donor-copy newcomer gets | Not carried |
| --- | --- |
| The donor's amounts of every declared species at the event time, read before any event at that time (the supply ledger books them; the donor keeps its contents) | Junction gate state and junction abundance: every junction at the slot restarts the formation law (A0, lag, tau, gate at arrival). This is the excluded "inherit" |
| The donor's channel gates, matched by channel law | Route values (channel, leak and pump coefficients): the slot's own, unless a route-only template declares them |
| | Volume and fixed-charge background: the parser requires the donor's to equal the slot's |

So the written state can pass only through the copied composition and membrane channel
gates. Coupling to the neighbours is always built anew.

## 2. Donor-copy content: composite v2 §2, decision 4

The decision: [Composite v2](PUMP_COMPOSITE_V2_DESIGN.md) §2 (water plus replacement,
`scheduled_cell_replacement@2`) proposes that newcomers keep the slot's declared
impermeant content. Decision 4 leaves this open until the renewal assay asks. E07-v1 asks
now: does a donor copy get the slot's declared impermeant content, or the donor's?

**Impermeant content in E07-v1's worlds.** The pump family has two kinds.
- **The charged impermeant species P.** It is an amount, so it is among the copied
  amounts.
- **Water's neutral `impermeant_amount_fmol`.** It is a per-cell declaration, not state,
  and is absent at fixed volume.

In the held-bath sheets, every cell, the H template and every copy carry P = 135 mM × V0 =
101.3205 fmol. No route carries P: its membrane and junction permeabilities are 0, NaV1.2
and Kir2.1 carry Na and K only, and the pump moves Na and K. The pre-screen's checkpoints
confirm this:
- P's amount increment is exactly 0 in every cell of every arm;
- every supplied and every removed P is 101.3205 fmol per event.

There are no neutral impermeants.

**Settled for donor copies: the newcomer gets the slot's declared impermeant content.**
- **In E07-v1's worlds it is the same number as the donor's,** so the choice changes no
  trajectory, ledger or readout. `scheduled_cell_replacement@1`'s copy of the donor's P
  is exactly the slot's declared P.
- **For `@2` (later, with §2's code):** a donor whose impermeant content differs from the
  slot's declared content is refused when the definition is checked.
  - It is not mixed. The donor's permeant amounts with the slot's impermeant content
    would be a state that no cell had.
  - A different content needs water-owned impermeant state, which §2 names as a later
    extension.
- **E07-v1's driver checks this equality on every definition before a run.** It is a
  validation check, not an engine change.

**What sets the inherited loading behind the 95-minute censor.** The permeant ions do,
not the impermeant content.
- **D cells load K and the anion M in a fixed volume.** sheet70: K 136 → 146 mM and
  M 7 → 22 mM by 70 min. That is about 2% osmotic excess per 10 min of D residence: 10%
  at 56–58 min, and 15% by extrapolation at about 97 min after the cue.
- **A copy of a D cell carries that loading on.** A D lineage therefore keeps loading
  from the cue, through any number of replacements. In the pre-screen's donor arm at
  central k1, s 1.0, the excess reached 14.4% at 87 min after the cue, and flags came at
  56–58 min.
- **An isolated template resets the loading to 0.**
- **The 95-minute budget therefore bounds the time since the cue, not the number of
  turnovers.** Stage B starts 2 min after the cue (§3). Two turnovers then end 41 min
  after the cue at fast k1 and 87 min after it at central k1.

**Under water (§2, later).** The loading becomes swelling: the W1 water arms reached
1.03–1.06 V0 by 70 min. What matters for a donor copy then is its volume, which is not
decision 4.
- The donor's volume with the donor's amounts is an exact state copy.
- The slot's declared volume with the donor's amounts starts the newcomer hyperosmotic,
  and it swells back.

§2's code has to choose between these. This note proposes the donor's volume for donor
copies, since a copy is a copy of state, and leaves the decision to §2.
