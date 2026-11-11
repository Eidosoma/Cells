# Cell division in Cells: high-priority plan

Status: **high priority** (user, 11 November 2026; D141). The first subjects are
**Xenopus early cleavage and the C. elegans early embryo**. As with every test,
whatever physiology a subject needs is added to the engine, aiming to be as
realistic as possible (D136). This plan is the first slice of
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
- **Out of scope:** DNA replication, chromosome packaging, spindle mechanics and
  the cytokinetic ring. The molecular scope (D140) skips folding, and these
  machines sit far below the level Cells models.

## The minimum "division" Cells needs

| Piece | What it means | Engine status |
| --- | --- | --- |
| Trigger | When a cell divides: prescribed times first, then a size or cell-cycle law | None yet |
| Growth | Volume and material increase between divisions | Volume is a state in the water model (on main). Synthesis of material is not modelled |
| Partition | One cell's amounts, charge and volume split into two daughters, with closed material, charge and energy ledgers | Cell replacement (G2, in qualification) has event, ledger and lineage machinery; its donor copy explicitly does not halve the parent |
| New membrane | Daughters together have more surface than the parent; area, capacitance and membrane channel and pump abundances must be assigned | **Hard gap:** area and capacitance are static layout in the pump-tissue family |
| New contacts | A junction between the two daughters, and the parent's contacts shared between them | Tissue topology is static; G2 restarts junction formation but adds no cells. New cells need padded slots that switch on at division |
| Lineage | Stable IDs and parent–daughter records | G2 has carrier IDs and lineage |

The membrane and topology rows are the real engineering work. The rest builds on
G2 and the water model.

## Candidate subjects

Each still has to be checked against the papers. The marks say what our quick
searches on 11 November established.

| Subject | Growth needed? | Fits Cells' physics? | Wet-lab data (to verify) | First judged observable |
| --- | --- | --- | --- | --- |
| **Xenopus early cleavage** (first few divisions) | No: cleavage divides the egg without growth | Yes. Animal cells with ion transport, membrane potential and gap junctions. Electrical coupling between early blastomeres was measured, along with membrane resistance and capacitance by cleavage stage (DiCaprio, French & Sanders). Dye coupling is cell-cycle dependent and reported lost by the 32-cell stage. Seen in search results only. | Classic electrophysiology papers (digitised values), plus cell-cycle oscillator models (Cdk1) | Total membrane capacitance and junctional coupling against cleavage stage. This directly tests the new-membrane and new-contact pieces |
| **C. elegans early embryo** (1 to about 350 cells) | No | Partly. Ion physiology is not what sets its division timing or asymmetry (spindle positioning and polarity do) | Large open 4-D datasets: the CShaper morphology atlas (4–350 cells, 17 embryos), division timing, and volume asymmetry in about 40% of early divisions (search results; open access to check) | Daughter volume ratios and timing would be inputs, not predictions, so a weak test of Cells' physics |
| **Epithelial monolayer, e.g. MDCK** | Yes | Yes, and it matches the vertex-mechanics ladder. One study (Voltron sensor) reports that membrane potential regulates cell density through growth, proliferation and elimination (search result) | Live imaging, cycle reporters, density and voltage data (to verify) | Membrane potential against density, and proliferation after depolarisation. Needs growth and mechanics (MG1–MG3) |
| **Microbes** (E. coli size "adder", fission yeast size control, B. subtilis biofilm signalling) | Yes | Poorly. Cell walls and turgor, proton-motive force and no gap junctions, so little of the qualified engine applies | The richest division-size datasets (mother machines). Taheri-Araghi 2015 has an erratum and its data location is unconfirmed. The fission-yeast sizer mechanism is contested. B. subtilis membrane-potential memory (Yang et al. 2020, Cell Systems) was seen only through press coverage | Size at birth and division laws; would need a separate physiology |

## Order of work (lead's ranking under D141)

Both subjects are early embryos, so neither needs growth at first. The order:

1. **Division as an engine operation.** This is common to both subjects; see the
   stages below.
2. **Xenopus early cleavage first.** It sits on Cells' qualified bioelectric
   physics.
   - **Observables:** the measured membrane capacitance and junctional coupling
     across cleavage stages directly test the new-membrane and new-contact pieces.
   - **Trigger:** prescribed at first, with the measured cleavage period. A Cdk1
     cell-cycle oscillator model follows.
3. **C. elegans early embryo next.** It has the larger open datasets (4-D
   morphology and timing from 4 to about 350 cells). Its division timing and size
   asymmetry come from cortical polarity and spindle positioning, so those are
   added as engine models when this subject starts:
   - a PAR polarity reaction–diffusion model on the cortex, building on
     `reaction_transport@1`;
   - later, cortical flow and spindle positioning.

   The measured volumes and timing then become predictions to test, not inputs.
4. **An epithelial monolayer later,** once growth and vertex mechanics (MG1–MG3)
   exist.

## Stages

1. **Verify.** Read the papers for both subjects and confirm the data (values,
   access, licences). Fix the first judged observable for Xenopus and list the
   C. elegans datasets and the physiology each needs. Running any paper's own
   model needs per-paper approval.
2. **Engine piece 1: division as an operation.** Add an opt-in division event on
   the pump-tissue family, built on G2's event machinery and the water model's
   volume state:
   - padded slots that switch on;
   - partition of amounts, charge and volume with closed ledgers;
   - new membrane area and capacitance with a declared rule;
   - a daughter–daughter junction;
   - lineage.

   With no division it must be bitwise equal to the inner model, with an
   independent reference.
3. **First subject, development runs:** the cleavage sequence with prescribed
   timing, compared with the measured capacitance and coupling.
4. **Judged run** under a protocol registered before it.
5. **Growth and a trigger law,** then the second subject.

The cost is not estimated until stage 1 settles the subject.
