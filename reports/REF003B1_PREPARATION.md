# REF-003b1: native preparation exposed a geometry mismatch

2026-09-12, D066. **Not numerically qualified.** BETSE's actual configuration
loader and native seeder now run in the isolated pinned environment. However,
the requested single-cell preset produces **seven cell compartments and 30
membrane faces**. The shape guard rejects it before the proposed charge/voltage,
Cells RHS, prescribed-update or trajectory comparisons. No full trajectory ran.

The earlier [54-probe passive-law result](REF003A_PASSIVE_CONTACT.md) remains
valid and independently authenticates. This new finding is about preparing a
corresponding whole model, not disagreement between the previously tested flux
laws.

## Actual evidence

The final [native preparation](../runs/ref-003b1-2026-09-12/alignment-05/native_preparation.json)
records the requested single-cell flag, seven volumes/areas/centres, all 30
membrane owners/areas, six-species initialization, native constants and runtime,
and the disabled general-network flag. All **332 installed BETSE Python files**
match the clean v1.5.0 checkout at
`5269a714aa2593ed2a6708c4516289977d8ae1a2`. Neither BETSE nor Cells was patched.

The [read-only diagnostic audit](ref-003b1-preparation-audit.json) returns
`mismatch_confirmed`, with `alignment_qualified: false`. It checks actual
geometry ownership, initial concentrations, configuration/source identity and
the absence of downstream numerical evidence. This is a confirmed rejection,
not an acceptance receipt disguised as a pass.

The upstream [mesh constructor](https://github.com/betsee/betse/blob/5269a714aa2593ed2a6708c4516289977d8ae1a2/betse/science/math/mesh.py)
creates a centre point plus six surrounding seed points. The
[Cells.make_voronoi single-cell pathway](https://github.com/betsee/betse/blob/5269a714aa2593ed2a6708c4516289977d8ae1a2/betse/science/cells.py)
passes the resulting geometry into the native cell construction. Execution
confirms seven actual compartments; this is not merely counting drawing points.
It does not establish that every other BETSE configuration or version lacks a
valid single-cell route.

## Retained attempts

| Attempt | Seconds | Stop and handling |
| --- | ---: | --- |
| alignment-01 | 3.519 | YAML flow emission wrapped mapping keys; switched the adapter to block-style YAML. No seeding. |
| alignment-02 | 3.540 | Native loader rejected absolute geometry paths; made asset paths relative to the generated configuration. No seeding. |
| alignment-03 | 3.596 | Expression-data YAML also needed source-relative resolution. No seeding. |
| alignment-04 | 4.040 | Native seeding completed but produced seven cells; one-cell guard stopped the capture. Native default general network was also enabled. |
| alignment-05 | 4.093 | Protocol revision 2 explicitly disables that network. Native seeding still produces seven cells; the unchanged one-cell guard rejects it, with structured preparation evidence. |

All failures, generated YAML, logs, seeded-world files and source/registration
capsules remain available under [the session directory](../runs/ref-003b1-2026-09-12).
These were short, individually diagnosed setup attempts, not a long polling job
or an automatic retry campaign. No equations, numerical tolerances or cell-count
requirements were loosened. Revision 2 changes only the network enable setting
and its revision/amendment metadata, not a scientific acceptance threshold.

## Architecture lessons and next step

The [alignment design](../docs/BETSE_INITIALIZATION_ALIGNMENT.md) records three
additional source-level findings, **not yet executed numerical qualifications**:

- Zero-polarizability charge closure can reduce to our existing capacitor model.
  The native custom ion profile automatically supplies a balancing anion, so
  neutral preparation is distinct from a prescribed resting voltage.
- Nonspatial BETSE still changes outside concentrations. Its face-wise update
  followed by arithmetic averaging implies a lumped effective outside volume
  of membrane-count times `p.vol_env`. This needs the planned transfer witnesses
  before numerical acceptance. Cells' explicit-volume ownership is unchanged.
- Native loop labels and post-update observations need an explicit elapsed-time
  mapping before any trajectory comparison.

Next: a geometry-only feasibility check for an unmodified native one-cell setup,
with explicit mechanism flags. If that route is unavailable, register a clearly
named seven-cell comparison using the existing finite-compartment architecture.
Do not silently select one of seven traces, change the simulator equations, or
count a synthetic checker fixture as executed BETSE agreement.

## Verification boundary

All **103 short adapter tests** pass: 52 preserved REF-003a tests, 38 synthetic
alignment/checker and preparation-guard tests, and 13 actual preparation/negative
evidence tests. Eleven deliberately corrupted preparation records are rejected.
Synthetic alignment tests verify the checker, not the pending native numerical
comparison. Test receipts: [first complete check](ref-003b1-checks-01.xml) and
[final check](ref-003b1-checks-02.xml).

The [preservation receipt](ref-003b1-preservation.json) binds 782 pre-existing
files and the earlier contact/accepted development sources. The
[handoff record](ref-003b1-closeout.json) records their final identities and all
retained attempts. All 352 accepted implementation files and 51 production
modules remain unchanged; the previous 4190-test production matrix was not
rerun. Stable 0.14.0 and development 0.15.0.dev0 are unchanged. No biological,
GPU, performance, end-to-end BETSE parity or stable-promotion claim is made.
No job remains running or scheduled.
