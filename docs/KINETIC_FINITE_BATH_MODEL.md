# Kinetic finite-bath integration design

2026-09-16, D112 design; implemented as **0.16.0.dev0 / D113**, with full
new-family acceptance **pending**. The D111 process gate has now been
[reviewed and preserved](../reports/SPEC010_PROCESS_CLOSEOUT.md): 930 source
comparisons and 348 targeted regression tests pass. Before production edits,
1,273 working-context files were archived with byte verification. Historical
receipts and the accepted 0.15.0.dev0 context remain unchanged.

The new configuration is runnable through the ordinary engine; this is not a
stable release or BETSE parity claim. The
[family handoff](../reports/SPEC010_FAMILY_HANDOFF.md) separates passing bounded
checks from the broader detached lifecycle/trajectory/regression job.

It extends the [process contract](KINETIC_PUMP_PROCESS.md) and the
[closed short numerical scope](../reports/NUM011_COUPLED_CLOSEOUT.md).

## Version and scope

Use a new model identity, **`finite_extracellular@2`**, with a distinct immutable
host model type and numeric layout type. Keep top-level `schema_version: 1`:
the model identity versions the changed physics/configuration contract, not
the generic experiment container. The existing `finite_extracellular@1` parser,
configuration fingerprints and synthetic-law semantics remain available.

Initially v2 accepts either no pump or `nak_atp_mass_action_positive@1` on each
membrane. The old synthetic pump stays available through v1; no implicit
conversion, silent law substitution or mixed-law selector is needed for this
first increment. Preserve existing channels and junction mechanisms in the
composition, but qualify their combined use with the new pump separately.

Keep the existing bounded geometry: one membrane per cell and one active
well-mixed shared outside compartment, with explicit capacity padding. Neither
arbitrary surface meshes nor a spatial extracellular field is implemented by
this change. Species labels, cell count and topology remain data. The process
interface must remain reusable by later resolved-membrane/spatial families.

Do not append optional kinetic fields to the old frozen membrane dataclass:
that can change old serialization and create contradictory parameter meanings.
Use separate typed kinetic-pump and membrane specifications, with shared
validation/binding helpers only where their physical contracts really match.

## Pump declaration

The parser accepts this fragment. A complete synthetic preparation is available
in [kinetic_finite_cell.json](../configs/kinetic_finite_cell.json):

```json
{
  "id": "nak_0",
  "law": "nak_atp_mass_action_positive@1",
  "roles": {"sodium": "Na", "potassium": "K"},
  "stoichiometry": {"Na": -3, "K": 2},
  "capacity_fmol_per_s": 0.1,
  "km_na_mM": 12.0,
  "km_k_mM": 0.2,
  "km_atp_mM": 0.5,
  "metabolism": {
    "kind": "maintained_chemical_reservoirs@1",
    "atp_mM": 1.5,
    "adp_mM": 0.1,
    "pi_mM": 0.1,
    "delta_g0_J_per_mol": -37000.0
  }
}
```

Use one canonical extensive capacity field initially. If a preparation starts
from surface density, convert `area * density * 1e15` to fmol cycles/s explicitly
and retain the density's provenance. Do not accept both capacity and density as
independent authorities, or multiply the extensive capacity by area again.

Require distinct declared Na/K role IDs, each with valence +1, and exactly
−3/+2 coefficients. Resolve IDs to integer indices once on the host; labels
such as `cation_A` must work identically to `Na`. Reject missing/unknown fields,
booleans as numbers, nonfinite values, invalid capacity, and nonpositive pools/Km.
The temperature and affinity domains come from the named process; an attached
channel retains its own narrower temperature/voltage contract.

There is no user-supplied `drive_J_per_mol` in this kinetic declaration. Derive
the maintained chemical drive from pools, temperature and standard free energy.
Keep it immutable and verify any stored derived coefficient against those
declared inputs. ATP/ADP/Pi are not finite dynamical inventories in this version.
Reject time-varying metabolic-pool controls rather than reusing a constant-drive
work formula after the drive has changed.

```bash
.venv/bin/python -m cells validate configs/kinetic_finite_cell.json
.venv/bin/python -m cells run configs/kinetic_finite_cell.json --output runs/my-kinetic-cell
```

Use a fresh output directory. The fixture's extensive capacity is explicitly
converted from the NUM-011 density/area inputs; it is not an experimental fit.

## Layout, state and transfer ownership

Keep the existing ten physical/history state fields: local and outside amount
increments; leak, pump-cycle and channel histories; membrane dissipation; channel
and junction gates; junction transfer and dissipation. Extra pump coefficients
belong in layout, not new evolving state. Complete checkpoints must retain every
state field plus all numeric layout fields and the new configuration identity.

Add explicit pump presence/role indices and the process parameter arrays, with
`[..., membrane_slot]` semantics. Species remain a separate axis. All gathered
owner/species indices must be safe before device execution, including inactive
slots. Neutral inactive lanes use positive pools/Km/concentrations, valid
temperature, finite potentials and zero capacity. This is host padding, never
a floor applied to a depleted active cell or a blocked physical pump.

At each solver stage:

1. Gather current cell/outside concentrations and derive voltage from the
   charge-bearing amount state.
2. Evaluate passive leak, the named pump and any channels from that same state;
   evaluate each junction against its two current cells.
3. Form one signed membrane transfer: `leak + stoichiometry * cycles + channel`.
   Scatter it once to the cell and its negative once to the outside owner.
   Scatter junction transfers only between their two cells.
4. Derive current and energetic readouts from those same transfers. Integrate
   cycles and dissipation; do not introduce a second independent voltage update.

Reuse shared pure ownership/scatter/accounting helpers. Introduce a small
explicit composition helper if necessary; avoid duplicating the complete old
model or designing a general plugin system for this increment. In particular,
aliasing the old `rhs` is insufficient: its module-level `readouts` still calls
the synthetic pump. Do not monkeypatch it or subtract synthetic pump flux from
a completed RHS. Select the new process in the new model's composition.

For constant maintained pools, reuse the signed cycle ledger to calculate
chemical work. Verify full finite-system chemical plus capacitor energy,
dissipation and supplied work. A finite bath cannot use the maintained-bath
grand-potential shortcut. Dynamic metabolism would require a separately owned
work/pool state and a new explicit contract.

## Stage and interpolation safety

Retain all existing positivity, charge, gate and inactive-state checks, then
add the kinetic process predicate before accepting RK4 trials and endpoints.
The shared integrator must remain independent of pump identity. Initial-state
and derived-coefficient validation must happen before capacity-sized allocations.

Endpoint checks are not sufficient for cubic observation/restart interpolation.
Use the existing Hermite bounds for cell/outside amounts and voltage. With
fixed positive volumes, obtain positive concentration intervals and monotone
log intervals. For monovalent Na/K, the affinity is

```
A = drive + RT[-3 log(Na_i) + 3 log(Na_o)
               +2 log(K_i) - 2 log(K_o)] - F V
```

Use the appropriate interval endpoint for each signed term to enclose A over
the whole cubic interval; also enclose the individual ion potentials. Specify
outward rounding/roundoff allowances for the polynomial, logarithm and signed
sum bounds, with independent high-precision edge-case checks. Require
the complete enclosures to satisfy the process's declared domains. This is a
conservative certificate: an overly wide enclosure means **unable to certify**,
not proof that the true trajectory left the domain. Refuse that output interval
with an accurate diagnostic; do not clip it or silently change integration.
Test an unsafe interior whose endpoints both pass, and a conservative refusal.

**D113 implementation detail:** retain v1's floating extrema checks, then use
outward-rounded Bernstein control-point hulls for the kinetic certificate.
For a cubic they enclose all interpolation times without relying on rounded
derivative roots. The four controls are `y0`, `y0 + h*f0/3`,
`y1 - h*f1/3`, `y1`. Subtractions, products, division, accumulation and inventory
anchors are widened with `nextafter`. Logs have a 64-epsilon absolute/relative
allowance, followed by a 128-epsilon expression-size allowance for the alternate
process evaluation order and RT rounding. These are explicit CPU float64/libm
engineering assumptions, **not a formal correctly-rounded transcendental proof**.
An 80-digit Decimal check covers polynomial samples and a near-domain-boundary
affinity; it does not prove all possible inputs. No physical domain tolerance is
enlarged. Bernstein hulls may conservatively refuse a safe interval: this is
tested and reported as inability to certify, not depletion or domain escape.

Use 50/100 µs as initial acceptance candidates from the closed NUM-011 cases.
Do not inherit v1's 1 ms bound or declare a universal timestep. Channels,
junctions, different parameters and longer runs require their own evidence.

## Implementation map

| Area | Implementation | Guardrail |
| --- | --- | --- |
| `core/specs.py` and new kinetic finite-bath parser | New model/membrane/pump types; v2 parse/serialize route | Old v1 fingerprints and strict rejection behavior unchanged |
| `core/state.py` | New numeric layout with role indices and metabolic coefficients | Flat named checkpoint arrays; no missing hidden state |
| `models/registry.py` and new composing model | Explicit v2 dispatch, same-stage rates and conservative ownership | No law branch in RK4 or organism-name selector |
| Existing shared physical helpers | Reuse or narrowly extract pure binding/scatter/balance operations | Preserve arithmetic order and test old-family behavior |
| Model domain/observers/resource estimates | Pump stage/interior checks, physical units, extra coefficient storage | No hidden clipping or uncounted padded arrays |
| Configurations and tests | Data-defined cases, lifecycle and corruption checks | Synthetic fixture values are not experimental calibration |

The registry and `SimulationSpec` now explicitly route the new concrete type.
The flat layout adds ten leaves: presence, two role indices and seven kinetic/
metabolic coefficients. The existing capacity and derived-drive leaves remain
owned and checked against the declared inputs. Resource estimates add 192
float64-equivalent membrane columns for layout, rate and enclosure buffers;
they are conservative array reservations, not a compiler/OS memory limit.

## Acceptance sequence

Steps 1–2 are complete, with 43 schema/layout tests and a preserved-context
check that all fourteen old-family initial fingerprints, resolved definitions,
states, layouts and complete NumPy RHS values are byte-equivalent. Thirteen
equation/interpolation checks and three compiled runner/composition/event smoke
checks pass. Full step-3 trajectories and step-4 lifecycle coverage are written
but await the detached step-5 result; **do not infer full acceptance from smoke**.

1. Inspect the existing qualification's terminal result on user request. Require
   its source-contact and regression gates to pass; preserve failures if not.
   Archive the complete pre-change working context before editing production
   dispatch/types or shared code. Do not reuse a running capture's directory.
2. Implement strict parser/serializer and layout tests: old/new separation,
   role permutations, heterogeneous membranes, absent pumps, neutral padding,
   parameter round-trip, and byte/resource limits.
3. Compare the ordinary model's complete stage RHS and short trajectories to
   NUM-011's separately preserved reference coordinates. Test blocking/release,
   one cell, two cells sharing a finite bath, and all material/charge/energy
   ledgers. Add combined channel/junction cases without claiming those are
   qualified merely by the original pump-only panel.
4. Test ordinary runner checkpoints and fresh-process restarts, branches,
   event-boundary clocks, off-grid observations, Hermite safety, padded layouts,
   homogeneous batches and windowed/cohort equivalence.
5. Freeze and launch bounded new-family acceptance and appropriately routed
   regressions detached. Inspect results before any acceptance/release claim.
   Keep all reference, old-family and new-family source contexts explicit.

The full-package fingerprint will change when the new model is added. Old
checkpoints remain tied to their preserved source context; same field names
do not justify weakening the identity check or treating v1 as v2.

## Multiscale and GPU boundary

The new mechanism uses local numeric arrays and explicit signed transfers.
One shared bath has one inventory owner, including under future device
partitioning. Independent batch worlds are **not interacting organs**; future
inter-organ exchange needs conservative ports and clocks of its own. Organ
identity remains data, not a new hard-coded pump or solver branch.

GPU correctness/performance, sparse spatial solves, multirate/coarse-fine
coupling, multiple interacting organs and long biological relaxation are not
delivered by this integration. This slice preserves interfaces needed to add
them without changing the named pump equation.
