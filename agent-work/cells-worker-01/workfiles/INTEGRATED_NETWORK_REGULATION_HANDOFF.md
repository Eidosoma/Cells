# Integrated Na/K network regulation — B07 handoff

Cells Key Developer, 2026-10-29. Model
`resolved_calcium_energy_regulated@1` composes the frozen network factor
equations over `resolved_calcium_energy@5`. All **38 complete state fields**
remain exactly the parent fields. This is a new Cells common-stage composition;
native SIM timing and lag are not claimed to match it.

## Qualified files and evidence

- Spec: `src/cells/core/surface_calcium_energy_regulated_spec.py`, SHA
  `42378ea33c8576b7b132fe8ea72a13d11b73b4594ff02910f90f17b16a501099`.
- Model: `src/cells/models/surface_calcium_energy_regulated.py`, SHA
  `76c1ddd7ad918e3aa49456c9f106f40f533a48b8550b4254541eb53b24129bc9`.
- Independent reference, fixtures and protocol:
  `validation/regulation/integrated_network_regulation_{reference,fixtures}.py`
  and `integrated_network_regulation_protocol.json`.
- Tests: `tests/unit/test_surface_calcium_energy_regulated.py`; own runner:
  `check_integrated_network_regulation.py`.
- [Complete component receipt](/mnt/workspaces/Cells/integrated-network-regulation-development-20261029-03/result.json),
  SHA `01113b95ad364a45f0c25da84dde2a666d942f7c161d786d232e15ac2f8f6563`:
  **46 tests: 43 host and three CPU JAX**, zero skips/errors/failures or source
  drift; **141 component artifact identities**, 42 JSON evidence summaries.

Seven scientific files/evidence are frozen. Earlier regulation, calcium/fuel,
geometry, transport and flow modules remain read-only. No registry, shared
specs/schedule/state/runner, assembly, PROGRESS or frozen file was edited.

## Explicit declaration and physical ownership

The parent full calcium/fuel/56-law definition remains intact. The new model
adds `network_regulation` with exactly:

```json
{
  "law": "betse_network_modulation_source_v1_5_0@1",
  "timing": "common_stage_free_cytosol_exterior_fuel@1",
  "control_composition": "scheduled_times_ordered_native_nak_factor@1",
  "rules": [
    {
      "id": "nak_rule_0",
      "pump_id": "pump_0",
      "fuel_pool_id": "fuel_cell_0",
      "configuration": {
        "name": "nak_rule_0",
        "target": "Na/K-ATPase",
        "max effect": 0.8,
        "activators": ["ATP"],
        "activator Km": [0.6],
        "activator n": [2.0],
        "activator zone": ["cell"]
      }
    }
  ]
}
```

`execution.regulation_capacity` explicitly reserves rule slots, including
neutral padding. The ordered list has unique rule IDs distinct from existing
physical owners/routes. Configuration name equals rule ID; target is strictly
`Na/K-ATPase`. Every target pump must exist and its explicitly named fuel pool
must be the pump's own finite cytosol pool. Fuel cannot be referenced in an
environment zone. Limits are 64 rule slots and 16 influencer terms per rule.

Native configuration validation/binding and factor evaluation reuse frozen
`betse_network_modulation` and its frozen reaction-regulator implementation.
No Hill/direct/independent equation is copied into production code. Each rule
binds one membrane and one exterior concentration view, with the actual
target owner indices carried separately in the new model layout. Shapes are
stacked and neutral term/rule padding is explicit.

Samples are ephemeral `[rule, ionic_species+ATP/ADP/Pi, cell/environment]`
concentrations in mM. Ionic cell samples come from the **current free cytosol
store amounts**, divided by cytosolic volume. They are not the total ionic
transfer ledger, total calcium, bound calcium or an initial concentration.
Exterior samples are the actual finite exterior amount/volume on that
membrane's outside owner. ATP/ADP/Pi samples use the named finite pool's
current amounts/owner volume. Exterior fuel slots are absent read views filled
with zero and cannot be selected by a fuel influencer.

No new chemical species or amount/state inventory is created. Multiple rules
may read the same owner, but only the existing store/exterior/pool quantities
own physical amounts. The existing substrate dependence of the pump remains;
an explicitly declared ATP regulatory term adds availability dependence, not
a second fuel-consuming route.

## Timing, control composition and refusal

At every common RK trial stage:

1. Read the current free cytosol, exterior and owned fuel concentrations.
2. Evaluate each frozen native `max_effect * alpha` factor.
3. Apply factors in declared rule order to their named pump targets; the last
   rule at a target replaces earlier factors. Unregulated present pumps keep
   factor one, absent/padded pumps keep zero. Rules do not multiply each other.
4. Multiply the final factor by the held scheduled pump availability **once**.
5. Pass that effective control to the unchanged complete calcium/fuel model.

Existing passive/channel/junction, PMCA, NCX, ER chemistry/release, signed pump
fuel demand, regeneration, charge, field and heat/work bookkeeping run at the
same parent stage. Availability scales the existing Na/K cycle rate; its
signed cycles enter the one existing owner ATP/ADP/Pi exchange exactly once.
No regulatory ATP consumption, energetic supply, lag history or clock is added.

All active rule factors must be finite and in **[0,1]**, including factors
whose target is currently scheduled off. Maximum effects outside [0,1] are
rejected during parsing. Independent/direct source expressions that yield an
incompatible factor are refused at definition/trial/observation boundaries;
they are not clipped, repaired or interpreted as a pump reversal. Supported
sample values/parameters also retain the frozen source domain checks.
`rhs` produces invalid trial values when its domain is invalid; the supplied
`domain_valid.with_control` is the common checked-step guard.

The source component permits signed/unbounded factors and native whole-control
replacement. Its authentic captures use `mem_concs`/`map_mem2ecm`, and normal/
fast network consumer order differs from simultaneous staging. This model's
actual free-owner samples, schedule multiplication and common-stage timing are
declared **Cells composition choices**. The frozen native handoff/protocol and
all source identities are preserved; no new native SIM coupled run is claimed.

## Public model interface and observations

Before shared dispatch is applied, use the new spec module's explicit
`parse`, `to_dict`, `base_spec` and `control_values` functions and the new model
module directly. State/layout initialization, RHS, field values, trial/control
domains, conservative parent step ceilings, balances, complete value checks,
batch signature/working size, observations and summaries are supplied.

`sample_concentrations` and `regulation_values` expose the current read views,
per-rule factors and final membrane factors. Scheduled controls retain all 12
parent control fields and unchanged merged clocks. Observations use the
effective pump control for **every inherited physical readout**, then add
per-rule factors/samples and scheduled/final pump availability. They do not
evaluate inherited physical rates with an unregulated control. Observations
remain read-only and require accepted integration boundaries.

## Validation and scientific limits

Eight manufactured arms (active, blocked, identity, empty, reordered, ordered
overlap, independent and direct) are checked with/without capacity padding.
Identity/empty regulation reduces exactly to all parent derivative fields.
Checks distinguish free versus bound calcium at unchanged ionic transfer
ledger, live own-pool ATP and exterior Na, last-writer replacement versus
factor multiplication, repeated evaluation without hidden control history,
and one signed fuel transfer per physical cycle.

The independent reference imports no production/JAX code. It reconstructs owner
views from raw store/pool/exterior data, uses the frozen independent 80-digit
Decimal factor reference, and independently modifies held input schedules in
the full calcium/fuel reference. Production instead modifies the live control
vector. The full independent field, chemistry, material, charge and energy
reference therefore runs with the same regulated physical rates without
sharing the new production wiring.

The **10-us, full 63-population** coupled CPU probe includes pump events at
**3.3/7.1 us** and a fuel-supply event at **6.25 us**. All input families are
held within their common-stage segment and all events are integration
boundaries. RK4 step caps **1.25 / 0.625 / 0.3125 us** are checked against an
independent DOP853 solution (`rtol=2e-11`, `atol=1e-15`, max step 1.25 us).
Maximum error/budget ratios decrease **1.0126774e-3 / 9.6793164e-5 /
7.1338931e-6**. Raw maximum serialized-coordinate errors decrease
**8.0454532e-12 / 7.6899598e-13 / 5.6676885e-14**; these coordinates have their
own declared units, so this is not a single material-amount error metric.

Across these trajectories, maximum material closure residual is
**1.6940659e-21 fmol**, charge closure **5.0511750e-29 C**, global charge closure
zero, and combined energy closure **1.0570971e-18 pJ**. Pool material residual
is <=**2.1931351e-16 fmol**, adenylate <=**4.4408921e-16 fmol**, phosphorus
<=**3.5527137e-15 fmol**, and pool internal energy <=**2.7105054e-20 pJ**.
Existing numerical tolerances and physical checks are retained.

CPU JAX checks a complete **63-population, 38-field** instantaneous stage
against host and independent reference (max error/budget **2.6818936e-5**,
energy-rate residual **7.1054274e-15 pJ/s**). The complete **38-field, two shared
channel-population** 5-us JAX trajectory matches CPU at max error/budget
**4.3149657e-9**, and an in-memory split at **2.5 us** resumes exactly. This
does not establish shared checkpoint serialization or a monolithic generic
checked-step compilation/resource claim. JAX factor derivatives are finite;
own ATP response is **0.0146345925**, cross-owner response exactly zero.

Fifteen schema/initial-factor failure arms include wrong/missing owners, target
and species, duplicate IDs, unsupported timing/composition/capacity, signed
coefficients, native direct-group limitations and unbounded independent terms.
An initially valid direct ATP factor is then driven above one with positive
finite pools; both implementations reject it even with the pump scheduled
off. Source states are left unchanged. No empirical calibration, steady-state
settling, full native SIM, regulatory energetic-cost or additional network
target-family claim is made.

## Dispatch patch for the Chief

`integrated_network_regulation_dispatch.patch` and its JSON identity/anchor
manifest are **prepared, syntax-checked and unapplied** in these own workfiles.
They contain the exact narrow changes for four Chief-owned files:

- `core/specs.py`: parse and serialize the new model before parent inheritance.
- `models/registry.py`: select the new module before the HCN-extra parent.
- `core/schedule.py`: delegate the unchanged 12-field table through the new
  spec helper, before the general finite-energy family.
- `ensemble/ionic.py`: allow the new model ID for the established ensemble path.

Apply/reconcile these before using shared dispatch. Their before/after hashes
and patch SHA are in the JSON manifest; if Chief edits change those before
hashes, retain these exact branches before their parent branches. Existing
assembly family checks already accept the parent subclass; no shared state or
assembly inventory fields are added. `regulation_capacity` uses the existing
model capacity hook. Registered CLI/core/assembly/checkpoint integration has
not been executed by this worker and remains Chief-owned.

## Resources and frozen attempts

CPU7/one thread, CPU-only x64 JAX, no GPU/persistent cache/dependency changes.
Host phase **65.759 s**, RSS **235,446,272 B** (<=1 GiB). Compiled phase
**180.898 s**, RSS **1,697,222,656 B** (<=4 GiB). Minimum available host memory
**16,369,115,136 B** (>=8 GiB). Versions and package metadata are recorded by
the receipt/finalizer.

01 preserves lint failures. 02 passed its two selected host preflight checks,
then the disjoint JAX selection returned pytest's empty-selection exit code;
it is retained as an incomplete preflight. 03 is the complete qualifying run.
No scientific source or tolerance was changed after it passed. The finalizer
performs metadata/hash/XML/resource verification only, retaining attempts,
source provenance, this contract and the unapplied dispatch artifacts. No
worker job, automatic audit or regression is active.
