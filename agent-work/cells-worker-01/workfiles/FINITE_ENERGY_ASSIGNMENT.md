# Assignment: finite cellular energy pools

2026-10-28. This replaces ACTIVE_WATER_ASSIGNMENT.md following the user's request
for independent next-feature tracks. Hand off any active-water files already
written; the coordinator owns that integration. Your substantial parallel task
is the first finite-energy component proposed in docs/PAPER_REVIEW_MITOCHONDRIA.md.

## Exclusive ownership

Create only these new code/test/reference files plus your own WORK_LOG.md:

- `src/cells/processes/finite_energy.py`
- `tests/unit/test_finite_energy.py`
- `validation/chemistry/finite_energy_reference.py`
- `validation/chemistry/finite_energy_protocol.json` (if needed for qualification)
- `docs/FINITE_ENERGY_POOLS.md`

Do not edit existing pump, ER, calcium, model/registry/schema files or PROGRESS.md.
Use your workfiles directory for drafts and `/mnt/workspaces/Cells` for all
outputs, temporary files, caches, snapshots and retained failures.

## Physical contract and reusable boundary

Implement a small pure NumPy/JAX component for explicit finite ATP, ADP and
phosphate amounts in fmol, physical volume in pL and temperature in K. Resolve
concentrations from current amounts/current volume at every stage. Reuse the
Na/K process's explicit 1-M (1000-mM) standard state. Do not silently substitute
the older numeric-mM calcium pump quotient. Preserve all existing named laws.

Positive pump cycles consume one ATP and produce one ADP plus one Pi; reverse
cycles do the opposite. Support multiple declared routes sharing an energy
owner, with deterministic accumulation, inactive padding and independent world
axes. Retain adenylate and phosphorus identities (ATP+ADP and 3ATP+2ADP+Pi) and
signed consumption/production ledgers. The same pump cycles must never be counted
twice. A bridge may return stage-local kinetic_pump.Parameters from finite pools
without modifying that module or its immutable maintained-pool definitions.

Derive chemical potentials and finite-pool free energy consistent with
`g = delta_g0 + RT*log(ADP*Pi/(1000*ATP))`. One valid standard-energy gauge assigns
mu0_ATP=-delta_g0 and mu0_ADP=mu0_Pi=0, with ideal mixing relative to 1000 mM.
For fixed volume, the pool free-energy derivative from pump hydrolysis must be
`1e-3 * cycles * g` pJ/s. This will replace maintained chemical work in a later
whole-model balance, not add a second energy source. Report osmotic particle
amount and the volume derivative separately for eventual water coupling; do not
add them silently to existing ionic osmolyte or charge totals.

Use a declared transformed biochemical-potential model with buffered pH/Mg and
solvent activity; document what is excluded. It is not a detailed proton/Mg
speciation or electrical-charge model. Explicitly flag the future ownership and
osmotic/charge integration decisions. Keep strict positive domains for the pump
interface, never log floors/clipping. Trial exhaustion must reject; no claim of
continuing through zero substrate unless a separately derived boundary law is
implemented and independently checked.

Add a minimal explicitly driven ADP+Pi -> ATP regeneration route if its complete
energy contract can be derived now. Its external free-energy supply and signed
work must be declared and recorded; no arbitrary ATP reset or free regeneration.
For positive synthesis rate J and declared supplied energy w J/mol, reaction
energy is -g-w, supply power .001*J*w and heat .001*J*(g+w). Choose a reversible
law with nonnegative total dissipation and bounded numeric domain. It is a
synthetic supply port, not mitochondrial respiration, oxygen utilization or a
measured ATP recovery model. If a sound regeneration law is not ready, finish
finite consumption plus explicit port accounting and state that boundary.

## Useful tests and handoff

Use independent Decimal/scalar equations, material/energy identities, forward
and reversed demand, multiple owners/routes, sealed routes, source-off/recovery
examples, exact fixed-volume limiting cases and invalid domains. If writing a
trajectory helper, use a separately integrated reference and retain all histories
before assertions. Prototype the compiled/JAX/world checks but do not consume the
L4 or run heavy JIT workers while the water qualification is active.

First run only lightweight CPU7/BLAS1 NumPy/reference contracts, with <=1 GiB
worker RSS and >=8 GiB host reserve, through the existing bounded driver. Keep
logs and source snapshots. Tell the coordinator before a test expected >=10 min;
the coordinator owns detached qualification launch. Do not poll existing jobs.

Read docs/PAPER_REVIEW_MITOCHONDRIA.md, docs/KINETIC_PUMP_INTEGRATION.md,
src/cells/processes/kinetic_pump.py and its independent source reference. Use
primary-source research only if resolving a concrete missing scientific detail.
Report the usable API, implemented limits, evidence and remaining integration.
After completing this component, propose the next independent work item rather
than editing shared files or broadening biological claims automatically.
