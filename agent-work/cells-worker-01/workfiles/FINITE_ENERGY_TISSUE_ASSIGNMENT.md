# Assignment: finite energy coupled to ordinary resolved tissue

2026-10-28. The finite-energy component handoff passed 80 CPU checks and its
owned source hashes were verified. Continue the independently assigned energy
lane by building a usable simulation family with actual Na/K pumping and finite
ATP depletion/regeneration. This is the next platform capability, not an
additional biological research sweep. Do not rerun completed qualifications.

## File ownership

You own these NEW files and your existing WORK_LOG.md:

- `src/cells/core/surface_energy_spec.py`
- `src/cells/models/surface_energy.py`
- `tests/unit/test_surface_energy_spec.py`
- `tests/unit/test_surface_energy.py`
- `validation/tissue/surface_energy_fixtures.py`
- `validation/tissue/surface_energy_reference.py`
- `configs/resolved_energy_tissue.json`

You may extend your new `docs/FINITE_ENERGY_POOLS.md` with the model contract.
Keep the delivered finite_energy process/reference/tests stable unless a concrete
bug requires a fix; tell the coordinator before changing them. Do not edit
shared registry/spec/schedule/ensemble modules, existing models, PROGRESS.md,
water files or frozen evidence. The coordinator owns shared integration hooks,
execution/replay support, the full qualification protocol and job launches.
All generated outputs/caches belong under `/mnt/workspaces/Cells`.

## Versioned model contract

Use `MODEL_ID = "resolved_energy@1"`, based on `resolved_tissue@7` active ions,
shared gates and maintained-pump kinetics, but with fixed geometry/volume and
explicit finite cellular energy pools. Use the broad existing channel catalog;
qualify only the selected coupled channel regimes. Calcium remains an ordinary
ion here, without dedicated ER/buffer/pump composition.

Each cell has one explicit ATP/ADP/Pi owner. Multiple Na/K pump patches on that
cell consume the same finite pool using their already-computed signed cycles
exactly once. Define explicit regeneration ports and independent availability
schedules. Material and temperature/standard-state ownership must be unambiguous.
Finite pools use the existing 1-M transformed biochemical standard state.
Retain adenylate/phosphorus identities and strict positive-domain rejection.
No concentration floors or ATP resets; no zero-substrate continuation claim.

Propose the strict raw schema first in your workfiles and notify the coordinator
of dataclass/Control names before running parser hooks. Prefer finite-pool owner
references in pump metabolism declarations rather than unused maintained ATP
inputs. An explicitly named initial-ionic projection may supply initial pool
concentrations to the existing parser/layout helpers. Serialization must retain
the finite-pool declarations; that projection is not the actual time evolution.

Every coupled stage must gather current ATP/ADP/Pi and matching owner temperature
before Na/K kinetics. The previous maintained metabolic-work ledger may remain
as a clearly labelled internal pump/pool transfer diagnostic, but it must not
remain an external energy source in the full balance. The dynamic chemical drive
also invalidates a fixed-initial-drive-times-cycles identity: replace that check
with finite-pool/route accounting and independently integrated transfer power.

Use a minimal complete state: existing 19 active ionic fields plus finite pool
amount increments, regeneration extents, regeneration heat and regeneration work
(with explicit species/cell/port axes). The exact field names are yours to
propose. Complete checkpoints will need all of them, not only ATP endpoints.

Combined transformed-energy accounting includes ion/capacitor free energy,
finite-pool free energy, existing transport and pump heat, regeneration heat and
signed supplied work. Do not subtract the old maintained work a second time.
Declare buffered pH/Mg/solvent assumptions and distinguish this transformed
energy balance from a complete proton/Mg/water/whole-cell energy model. No new
ionic charge or osmotic contribution should be inserted implicitly; changing
volume and composition with the water model remain a later explicit integration.

## Verification and immediate resource scope

Begin with a small finite closed cell/exterior example and a second case sharing
one pool between two pump patches. Synthetic rates may make a resolvable finite
fuel effect over a bounded interval, but label them as manufactured inputs.
Compare independent scalar/Decimal stages, pool/ion material identities, combined
energy, supply off/on, pump inhibition/reversal, and an initial maintained-pool
rate limit. Full trajectories/refinement/restarts are for coordinated checks.

Use existing independent ionic and finite-energy references; do not import the
production model into reference equations. The source-specific PMCA/SERCA energy
quotient is outside this model. Do not invent ATP costs for assembly or repair.

Only lightweight CPU7 NumPy/host/reference checks under <=1 GiB RSS and >=8 GiB
host reserve are authorized initially, with single-thread BLAS and durable logs.
No GPU, no heavy coupled JIT/trajectory job, and no polling the active water
qualification. Send the schema/interface draft and stage-ready handoff promptly
so the coordinator can code shared hooks in parallel and schedule compiled work.
