# Cell division in Cells: high-priority plan

Status: **high priority** (user, 11 November 2026; D141). The user accepted either
**Xenopus early cleavage or the C. elegans early embryo** as the first subject; the
order below is the lead's. As with every test, whatever physiology a subject
needs is added to the engine, aiming to be as realistic as possible (D136). This plan is the first slice of
morphogenesis rung MG3 ("growth, division and death with conserved
partitioning", [morphogenesis plan](MORPHOGENESIS_PLAN.md)), brought forward. It
is not a parallel track.

## What the division review gives us

[SOTA_REVIEW_CELL_DIVISION.md](SOTA_REVIEW_CELL_DIVISION.md) is a user-supplied
overview of animal and human mitosis. Like the GRN note, it is unverified: its
links are search-sourced, it makes "published today" claims, and its diagram is
missing.

Cells takes a small slice of it:
- **In scope:**
  - when a cell divides (a trigger);
  - how it grows;
  - how its material, volume, membrane and junctions are split between two
    daughters;
  - what each daughter inherits.
- **Out of scope for now:** DNA replication, chromosome packaging, and the
  internal mechanics of the spindle and the cytokinetic ring.
  - Spindle *positioning* is the exception: it enters as a cell-scale model if and
    when C. elegans needs it.
  - The molecular scope (D140) skips folding, and these machines sit below the
    level Cells models today.

## The minimum "division" Cells needs

| Piece | What it means | Engine status |
| --- | --- | --- |
| Trigger | When a cell divides: prescribed times first, then a size or cell-cycle law | None yet |
| Growth | Volume and material increase between divisions | Volume is a state in the water model (on main). Synthesis of material is not modelled |
| Partition | One cell's amounts, charge and volume split into two daughters, with closed material, charge and energy ledgers | Cell replacement (G2, in qualification) has event, ledger and lineage machinery; its donor copy explicitly does not halve the parent |
| New membrane | Daughters together have more surface than the parent; area, capacitance and membrane channel and pump abundances must be assigned | **Hard gap:** area and capacitance are static layout in the pump-tissue family. It is also a charge-law gap: evolving capacitance needs a newly derived charge law and work accounting (multiscale architecture page) |
| New contacts | A junction between the two daughters, and the parent's contacts shared between them | Tissue topology is static; G2 restarts junction formation but adds no cells. New cells need padded slots that switch on at division |
| Lineage | Stable IDs and parent–daughter records | G2 has carrier IDs and lineage |

The membrane and topology rows are the real engineering work. The rest builds on
G2 and the water model.

**Division is a process, not an instant.** During cleavage the two daughters start
as one compartment and separate as the furrow closes. Their electrical coupling
therefore falls from high, rather than rising from zero as in G2's
junction-formation law, which must not be reused by default. The design either
ramps area, capacitance and coupling over the furrowing time, or records an
instant split as a stated limit.

## Candidate subjects

Each still has to be checked against the papers. The marks say what our quick
searches on 11 November established.

| Subject | Growth needed? | Fits Cells' physics? | Wet-lab data (to verify) | First judged observable |
| --- | --- | --- | --- | --- |
| **Xenopus early cleavage** (1 to 4 cells at first) | No: cleavage divides the egg without growth | Plausibly, with new parameters. Animal cells with ion transport, membrane potential and gap junctions. The qualified channels are mammalian, so a frog blastomere parameter set must be extracted. The egg is about 1 mm across, far larger than current cells. Electrical coupling between early blastomeres was measured, along with membrane resistance and capacitance by cleavage stage (DiCaprio, French & Sanders). Dye coupling is cell-cycle dependent and reported lost by the 32-cell stage. Seen in search results only. | Classic electrophysiology papers, possibly only a few figure-read values, plus cell-cycle oscillator models (Cdk1). BETSE's amphibian ion profile is a possible outside reference | Quantities the new-membrane and junction rules do not set directly: membrane potential and input resistance through cleavage, and the coupling ratio over time. Capacitance alone would be circular once the membrane rule is declared |
| **C. elegans early embryo** (1 to about 350 cells) | No | Partly. Ion physiology is not what sets its division timing or asymmetry (spindle positioning and polarity do) | Large open 4-D datasets: the CShaper morphology atlas (4–350 cells, 17 embryos), division timing, and volume asymmetry in about 40% of early divisions (search results; open access to check) | Without polarity and spindle-positioning models, volume ratios and timing could only be inputs. With those models added (D141), they become predictions |
| **Epithelial monolayer, e.g. MDCK** | Yes | Yes, and it matches the vertex-mechanics ladder. One study (Voltron sensor) reports that membrane potential regulates cell density through growth, proliferation and elimination (search result) | Live imaging, cycle reporters, density and voltage data (to verify) | Membrane potential against density, and proliferation after depolarisation. Needs growth and mechanics (MG1–MG3) |
| **Microbes** (E. coli size "adder", fission yeast size control, B. subtilis biofilm signalling) | Yes | Poorly. Cell walls and turgor, proton-motive force and no gap junctions, so little of the qualified engine applies | The richest division-size datasets (mother machines). Taheri-Araghi 2015 has an erratum and its data location is unconfirmed. The fission-yeast sizer mechanism is contested. B. subtilis membrane-potential memory (Yang et al. 2020, Cell Systems) was seen only through press coverage | Size at birth and division laws; would need a separate physiology |

## Order of work (lead's ranking under D141)

Both subjects are early embryos, so neither needs growth at first.

**The trade.** Xenopus is ranked first for its fit to Cells' bioelectric physics.
That trades away part of the user's criterion of "a lot of wet-lab data": its
electrical data may be a few older papers, while C. elegans is the data-rich
subject. **Go/no-go at stage 1:** if Xenopus yields only a handful of figure-read
values, the order swaps and C. elegans goes first.

The order:

1. **Division as an engine operation.** This is common to both subjects; see the
   stages below.
2. **Xenopus early cleavage first, from 1 to 4 cells.** It uses Cells' bioelectric
   physics with a frog parameter set.
   - **Membrane rule:** set from geometry or an independent source, not fitted.
   - **Judged observables:** quantities that rule does not set, such as membrane
     potential, input resistance and coupling ratio through each cleavage.
   - **Trigger:** prescribed at first, with the measured cleavage period. A Cdk1
     cell-cycle oscillator model follows.
3. **C. elegans early embryo next.** It has the larger open datasets (4-D
   morphology and timing from 4 to about 350 cells). Its division timing and size
   asymmetry come from cortical polarity and spindle positioning, so those are
   added as engine models when this subject starts:
   - a new model of PAR polarity: reaction–diffusion on one cell's cortex (a
     membrane surface, not the cell-to-cell exchange of `reaction_transport@1`);
   - later, cortical flow and spindle positioning.

   The measured volumes and timing then become predictions to test, not inputs.
4. **An epithelial monolayer later,** once growth and vertex mechanics (MG1–MG3)
   exist.

## Stages

1. **Verify.** Read the papers for both subjects and confirm the data (values,
   access, licences). For Xenopus:
   - extract the blastomere parameter set: resting potential, specific membrane
     resistance and capacitance, ion composition, and which conductances exist;
   - check BETSE's amphibian profile;
   - confirm that membrane potential, input resistance and coupling were measured
     through cleavage;
   - make the go/no-go call on data volume.

   For C. elegans, list the datasets and the physiology each needs. Running any
   paper's own model needs per-paper approval.
2. **Smoke test of scale.** Run one egg-sized cell at rest through the checked
   runner. The rounding bounds of the ledgers have broken on magnitude before, and
   the egg is far larger than any cell run so far.
3. **Engine piece 1: division as an operation.** Waits until G2 is judged and on
   main.
   - **First question for its design note:** the charge law for a split. What is
     conserved, what the voltage does, where the energy is booked, and how a
     growing capacitance fits static batched layouts.
   - **What it adds:** an opt-in division process on the pump-tissue family, built
     on G2's event machinery and the water model's volume state:
     - padded slots that switch on;
     - partition of amounts, charge and volume with closed ledgers;
     - new membrane area and capacitance with a declared rule;
     - furrowing as a ramp or a stated instant limit;
     - a daughter–daughter junction;
     - lineage.
   - **Checks:** with no division it must be bitwise equal to the inner model, and
     it gets an independent reference.
4. **First subject, development runs:** the cleavage sequence with prescribed
   timing, compared with the measured potential, resistance and coupling.
5. **Judged run** under a protocol registered before it.
6. **Growth and a trigger law,** then the second subject.

The cost is not estimated until stage 1 settles the subject.
