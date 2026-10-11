# Spatial cells with finite calcium chemistry

`spatial_calcium@1` composes the existing spatial ionic cluster with one
`er_calcium@1` store per cell. The [example](../configs/spatial_calcium_cluster.json)
has two cells, three finite outside regions, free Na/K/Cl/Ca, charged two-site
buffers, and finite ER inventories. All values are synthetic verification inputs.
Status and evidence are recorded only in [PROGRESS.md](../PROGRESS.md).
This model version uses passive GHK plasma calcium transport.
[`spatial_calcium@2`](PLASMA_CALCIUM.md) adds named plasma calcium extrusion and
exchange; calcium-selective gated channels remain a separate extension.

This contract and the [qualification protocol](../validation/chemistry/spatial_protocol.json)
address a concrete coupling risk: internal calcium exchange must not create
plasma-membrane charge, and free calcium must not be counted twice or confused
with bound calcium. Existing channel, junction, field, ER and reaction laws are
reused; the coupling introduces no fitted biological law.

## Material and capacitor ownership

Each chemical store owns its full cytosol/ER inventory, including free ions and
buffer complexes. Its cytosol volume and initial free ionic amounts must exactly
match the spatial cell definition. Named ionic moieties count each ion across
free, bound and ER species. Other moieties, including charged buffers, remain
inside their owning cell. Reactions conserve declared moieties and charge.

The spatial `amount_increment` field is a **whole-cell exchange ledger**, not
another free-ion inventory. It changes only through plasma transport and
cell-to-cell junctions. At every RK4 trial it must agree with the chemical
store's total ionic moiety changes; retained moieties and true chemical charge
are also checked. Plasma transport gathers free cytosolic amounts directly
from the chemical state. All routes, gates and the extracellular field read
the same solver stage. There is no sequential chemistry/transport split.

For cell i, the outer capacitor voltage uses whole-cell transported charge.
The ER voltage uses the ER's chemical charge increment. Therefore moving an
ion between cytosol and ER changes ER voltage but leaves the outer capacitor
unchanged. Initially, immobile chemical background charge is derived from the
declared inventories and voltage anchors: ER charge is `C_ER * V_ER`, and
cytosol charge is `C_plasma * V_plasma - C_ER * V_ER`. These background charges
are saved in the complete layout and never adjusted during integration. The
nested ionic definition's fixed charge belongs to its collapsed spatial
reference inventory; `chemical_fixed_charge_C` records the actual chemical
compartment backgrounds.

Energy includes every intracellular species once, the outside ionic solution,
both sets of capacitors, local reaction and all transport dissipation, and
external metabolic work. The existing Na/K pump retains its 1-M quotient;
the named BETSE ER pump retains its numerical mM quotient. The combined energy
residual limit is **1e-9 pJ**. No negative amount, voltage-domain excursion or
failed ownership check is clipped or repaired.

The chemical loss bound uses the entire finite world's available ionic moieties
and the cell's retained buffer moieties, so exchange cannot invalidate an
isolated-store concentration bound. Actual steps must satisfy the inherited
spatial guards, be at most 50 us, and have chemical loss-bound times step at
most 0.25. This is a domain guard, not an accuracy guarantee. The default is
**12.5 us**, with qualification refinement at **25/12.5/6.25 us**. Observation
cubics check free amounts, nested voltages, ER and Na/K affinity enclosures,
gates and component charge; observations never change solver steps.

## Assembly and execution

The [assembly example](../configs/assembly_regulated_calcium_cluster.json) uses
the existing `assembly_regulated_cluster@1` event-union solver with this explicit
physical model. Assembly organization scales the existing potassium channel
availability. Its effect on calcium is mediated by voltage and the declared
transport laws. Protein pools remain separate, and calcium does not alter
assembly reaction rates. This is a one-way coupling hypothesis.

Float64 CPU/GPU execution, scalar/batch windows and complete checkpoints use
the ordinary APIs. Assembly checkpoints include every chemical/ER state and
event clock. The existing ensemble scheduler preserves the physical-model
identity, calcium summaries, world IDs and per-cell random streams when
planning up to four nodes / 16 GPUs. No remote execution or scaling measurement
is established by those planning checks.

The bounded qualification compares independent scalar spatial/ER equations
using DOP853 and Radau, timestep refinement, route interventions, component
reductions, full restarts/partitions and actual CPU/L4 correspondence. An
independent scalar assembly history supplies event boundaries for the coupled
reference. Prior ER/native-function and selected assembly regressions run in
the same frozen panel:

```bash
PYTHONPATH=src /mnt/workspaces/Cells/venv-cpu/bin/python -B \
  validation/assembly/qualify_cell.py launch \
  /mnt/workspaces/Cells/spatial-calcium-YYYYMMDD-NN \
  --chemistry --chemistry-case spatial
```

Native BETSE lifecycle/trajectory parity, IP3, finite ATP, a detailed two-Ca
SERCA/proton cycle, cross-region junctions, water/volume, mechanics, calcium
feedback on assembly and biological calibration remain separate work.
