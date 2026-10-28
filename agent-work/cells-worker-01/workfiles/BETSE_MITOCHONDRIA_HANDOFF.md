# Native mitochondrial ion/voltage component

The new NumPy/JAX component preserves the executable BETSE 1.5.0 `Mito`
constructor, ion-update ordering and final charge/voltage refresh. It is ready
for Chief-owned integration. Shared dispatch, schemas, documentation and root
PROGRESS remain untouched by this worker.

- Law: `betse_mitochondrial_ion_voltage_source_v1_5_0@1`.
- Implementation: `src/cells/processes/betse_mitochondria.py`.
- Reference, captures, fixtures and protocol: `validation/organelles/betse_mitochondria*`.
- Final component receipt:
  `/mnt/workspaces/Cells/betse-mitochondria-development-20261028-01/result.json`.
  SHA `9551e3ba7b3b43c5992f162408bd46b0990d49c298712d7189488c72f552cb45`.
- Frozen handoff metadata:
  `/mnt/workspaces/Cells/betse-mitochondria-handoff-20261028-01/result.json`.

The first bounded run passes **85 tests: 81 host and four CPU JAX**. Actual native
captures cover **21 valid cases**, **seven source limitations**, a twelve-update
multi-ion trajectory and three analytic neutral diffusion profiles. The native
child imports no Cells/JAX. Peak sampled process-tree RSS is **367,468,544 B**,
minimum available memory **18,979,463,168 B**. Native/host/JAX phases take
**1.014 / 6.288 / 10.330 s**, on CPU7 with one BLAS thread, <=1-GiB RSS,
>=8-GiB reserve and 180-s command limits. No GPU or persistent compilation cache.

## API and state

`bind(species_valence, moving_species, cell_volume_m3, cell_area_m2, *,
specific_capacitance_F_m2, temperature_K, membrane_thickness_m=7.5e-9,
faraday_C_mol=96485.0, gas_constant_J_mol_K=8.314, active=None)` returns
`Topology, Parameters`. It snapshots half cell volume, half cell area, their
capacitance, and native current/base/channel diffusivity copies at **1e-19 m2/s**.
Only current diffusivity participates in flux. Current cytosolic volume can
subsequently change independently; mitochondrial geometry remains fixed.

`initial_state(cytosol_mM, topology, xp=...)` copies all cytosolic concentrations
into mitochondria and initializes cached Q/V to zero. It does not calculate a
charge-derived initial voltage or supply external charge. State fields are:

| Field | Shape | Meaning |
| --- | --- | --- |
| `cytosol_mM` | `[..., species, cell]` | Full-cell cytosolic concentration |
| `mitochondria_mM` | `[..., species, cell]` | Finite mitochondrial concentration |
| `charge_C` | `[..., cell]` | Cached mitochondrial charge |
| `voltage_V` | `[..., cell]` | Cached mitochondrial-minus-cytosolic voltage |

State arrays require float64. Species valences are fixed integers in [-8,8],
including nonmoving/neutral species. Moving species are unique ordered indices.
All active concentrations are finite and nonnegative, including zero boundaries.
Inactive cell slots have zero state, geometry, diffusivity and external charge.
Temperature, F, R and dt are scalar or per-world singletons `[..., 1]`.

```python
valid = domain_valid(state, topology, parameters, extra_rho_C_m3, dt_s, xp=np)
candidate = step(state, topology, parameters, extra_rho_C_m3, dt_s, xp=np)
```

Reject before publishing a candidate when `valid` is false. The predicate checks
the complete input and predicted output, including negative concentrations and
nonfinite native fluxes. No clamp, timestep retry or input mutation occurs.
`step` is the unchecked pure discrete native Euler update. `refresh_voltage`
exposes the separate native `get_v` phase; it is not implicitly called before
fluxes. Zero dt still performs native flux evaluation and a final cache refresh.
`material_balances` checks explicit cytosolic/mitochondrial amount and charge
ledgers. JAX kernels support shared topology with leading world axes; use
`jax.vmap(domain_valid)` when separate world rejection flags are required.

## Native timing, constants and owner signs

Positive density moves ions **cytosol -> mitochondrion**. Density is mol/(m2 s),
with **D in m2/s divided by thickness in m**. Cytosolic concentration subtracts
`density * mito_area / full_cytosol_volume * dt`; mitochondrial concentration adds
`density * mito_area / mito_volume * dt`. The transferred fmol ledger is
`density * mito_area * dt / 1e-15`. Apply these paired updates once to the
authoritative ion/store owners. Fixed ions still contribute to charge.

Each moving ion uses incoming cached voltage, mutated by **+1e-25 V** before
that ion's flux. Its valence nonce acts on a temporary array. The component
retains this literal source behaviour and records `voltage_used_V`. Charge is
refreshed once after all ion updates:

`Q = sum(F * mito_volume * c_mito * z) + extra_rho_C_m3 * mito_volume`;
`V = (1/capacitance) * Q`.

The caller supplies external molecular charge density before the update. Changing
it affects the final refresh; incoming cached voltage still drives that step's
flux. A supplied optimizer-style voltage override can also differ from cached Q.
Both Q and V must survive restart. CPU and JAX scan tests retain the complete
state and reproduce split continuations exactly. The source is a discrete Euler
component; recomposition into another time integrator needs its own claim.

Pinned native defaults are **F=96485 C/mol, R=8.314 J/(mol K)**. Parameters expose
both; captures cover defaults and an explicit modern SI override. Choose and
record constants consistently across a coupled physical ledger. The earlier
frozen transporter receipt used explicit modern p.F/p.R inputs in its native
captures; that distinction was reported to Chief without changing frozen files.

## Material, energy and source limits

Constructor copying adds a mitochondrial inventory without withdrawing any
cytosolic inventory. With unchanged concentrations, paired initial ion amount is
**1.5 times** the original full-cell amount. This is native correspondence, not
an inferred physical partition of an existing cell. No water state or volume
conservation law is added. Geometry changes between calls need explicit caller
amount/work accounting.

`physical_charge_before_C` and `cache_charge_adjustment_C` distinguish the
incoming ion/external charge from cached Q. At fixed geometry, refreshed charge
changes by F times the signed transferred ion amount, plus any explicit change
in external charge. Cached V can independently disagree with physical charge;
computing capacitor energy before resolving that phase would hide reset/forcing
work. External charge changes likewise need caller-owned work. This component
adds no physical heat, ATP synthesis, respiration, channel kinetics or solvent
ledger. Descriptions/comments in the native class do not implement those laws.

Authenticated source bytes and method line ranges are retained under
`native-source/upstream`. Revision is `5269a714aa2593ed2a6708c4516289977d8ae1a2`.
`Mito` and the actual `electroflux`/`get_charge` ASTs execute in the capture.
Pinned caller source documents transporter/channel/modulator processing,
network chemistry, external charge accumulation, then `Mito.update`. A full
native network simulation is outside the capture claim.

Seven preserved limitations are: missing `extra_rho` at `get_v`; missing
`extra_rho` after a partially mutated native update; nonce-shifted alpha=0 at
incoming -1e-25 V; untrimmed external charge after `remove_mits`; integer
constructor diffusivity truncation; float32 diffusivity/update precision loss;
and unguarded negative Euler outputs. Dynamic cutting is not silently repaired:
the caller must rebuild/select matching cytosol, mitochondrial, geometry and
external-charge arrays. Native `redefine_dynamic_dics` constructs a fresh Mito
and resets organelle state. The Ca uniporter/channel suggestions are commented
out; the optimizer's -150-mV assignment is not constructor initialization.

## Physical reduced check and reproduction

The neutral, two-finite-volume case uses actual default D, **7.5-nm** thickness,
**1e-15 m3** cytosol, **0.5e-15 m3** mitochondrion and **0.5e-9 m2** interface.
Its analytic tau is **50,000 s**; all three native/component profiles span twelve
tau, **600,000 s**, with dt=tau/32, tau/64 and tau/128. Maximum trace errors are
**0.0776554 / 0.0385722 / 0.0192230 mM**, observed Euler orders
**1.00952 / 1.00473**. Maximum material residual is **5.3291e-14 fmol**.
This is a neutral fixed-geometry unit/conservation check, not all-ion organelle
or full-cell settling. The separate controlled multi-ion run covers **0.012 s**.

Reproduce with a fresh output suffix using the new bounded runner:

```sh
taskset -c 7 env PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 \
  OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 \
  /mnt/workspaces/Cells/venv-cpu/bin/python -B \
  agent-work/cells-worker-01/workfiles/check_betse_mitochondria.py \
  --output /mnt/workspaces/Cells/betse-mitochondria-development-NEW
```

The component and evidence are frozen. No follow-up computation, regression or
audit is running. Shared integration remains Chief-owned.
