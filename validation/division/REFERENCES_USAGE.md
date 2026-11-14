# Using the S5 references: R-ops and R-tissue (interface only)

How to feed the two independent references of stage S5 and read their outputs, without reading
their source. The references are written from Appendix A of
[CELL_DIVISION_S5_DESIGN.md](../../docs/CELL_DIVISION_S5_DESIGN.md). Where a convention below is a
reading of Appendix A, the Appendix A item is cited; disagreements go to the lead.

- **R-ops:** `validation/division/partition_reference.py`, the partition map of A.6, numpy only.
- **R-tissue:** `validation/division/cleft_tissue_reference.py`, a graph-general R-full with
  prescribed divisions. It applies R-ops at each division.
- **Units** follow Appendix A: SI, except amounts in fmol, volumes in pL (n/V is in mM =
  mol/m³) and free energies in pJ. Potentials are in V, charges in C.
- **The J2 bright line (design §10.1).** A module that uses `partition_reference` or
  `simulate_divisions` must not read the J1 inputs or the J1 record, nor import a J1 module.
  `simulate_static` is the only entry point for J1-built worlds.

## R-ops: `apply(snapshot, division) -> Result`

```python
from validation.division import partition_reference as rops
result = rops.apply(snapshot, division)   # raises rops.PartitionRefused
plain = rops.apply(snapshot, division, charge_term=False)  # magnitudes without A.8's amendment
```

`apply` never modifies its inputs. All input dataclasses are frozen. Names of nodes and slots
are strings, unique within their kind. A node name may serve as a cell, a cleft or a held node,
but only as one of them.

### `Snapshot`: the live tissue just before the event

Supply **every live slot of the whole tissue**, not only the parent's. The pre- and post-event
potentials come from the full capacitor network. Leave out pending and retired slots.

| Field | Required | Content |
| --- | --- | --- |
| `species` | yes | Species names, e.g. `("Na", "K", "Cl")`. Every per-species tuple or array below follows this order. |
| `z` | yes | Valences, same length and order. |
| `temperature_K` | yes | Temperature (K). |
| `held` | yes | `{node: potential (V)}`, the held (clamped) outside nodes, e.g. `{"bath": 0.0}`. Any potential is accepted (A.6 step 6's W carries Σ φ_b Δq_b). |
| `cells` | yes | `{name: Cell}`, every live cell, the parent included. |
| `clefts` | yes | `{name: Cleft}`, every live finite outside node (`{}` if none). |
| `patches` | yes | `{name: Patch}`, every live patch of every live cell. |
| `populations` | no | `{name: Population}`, every live channel population (default `{}`). |
| `contacts` | no | `{name: Contact}`, every live cell–cell contact (default `{}`). |
| `bridges` | no | `{name: Bridge}`, every live bridge (default `{}`). |
| `history` | no | `{kind: {slot: value}}`, the @3 history accumulators to move to the record (see below). |

### `Cell`

| Field | Units | Meaning |
| --- | --- | --- |
| `reference_fmol` | fmol, per species | Declared anchor amounts n̄. |
| `increment_fmol` | fmol, per species | State increments Δ; the amounts are n = n̄ + Δ (A.6 step 3, increment form). Without an anchor split, pass zeros as the reference and the amounts as the increment. |
| `volume_pL` | pL, > 0 | Declared volume. |
| `background_fmol` | fmol of charge equivalent | Fixed background X (A.1). |
| `charge_C` | C | **The node charge Q at the view, carried explicitly** (A.1, A.6 steps 2 and 6). This is the charge the capacitor solve uses: the sum of the cell-side charges C_k V_k of its patches, positive for a net positive cell. R-ops does not recompute it from the amounts. It should equal 1e-15 F (Σ z n + X) to rounding, and the `charge_content_*` identities report that consistency. |
| `charge_reference_C` | C, default 0 | The declared **charge anchor** Q̄ of design §3.3. It is split (f, complement) into the daughters' anchors and enters no solve value. With `increment_fmol` it sets the magnitude of the cell's node charge (A.8 as amended; see Magnitudes). |

### `Cleft` (finite outside node, no background)

| Field | Units | Meaning |
| --- | --- | --- |
| `amounts_fmol` | fmol, per species | Amounts; carried through unchanged. |
| `volume_pL` | pL, > 0 | Volume; carried through unchanged. |
| `charge_C` | C | Node charge at the view, used by the solve; equal to minus the sum of its facing patches' cell-side charges. |

### `Patch`

Patch voltage V_k = φ(cell) − φ(node). Its cell-side charge is q_k = C_k V_k (A.2).

| Field | Units | Meaning |
| --- | --- | --- |
| `cell` | – | Its inside cell (a live cell). |
| `node` | – | Its outside node: a live cleft or a held node. |
| `area_reference_m2`, `area_increment_m2` (default 0) | m² | Anchor and increment; area = sum, > 0. |
| `capacitance_reference_F`, `capacitance_increment_F` (default 0) | F | Anchor and increment; capacitance = sum, > 0. The solve uses the sum. |

### `Population`, `Contact`, `Bridge`

| Class | Fields |
| --- | --- |
| `Population` | `patch` (its live patch); `abundance_reference`, `abundance_increment` (units; default increment 0; abundance = sum, ≥ 0); `gates` (tuple of gate values, copied). |
| `Contact` | `cells` (two live cells, either order); `area_m2` (declared, ≥ 0; no increment); `gates` (tuple, copied). |
| `Bridge` | `cells` (two live cells); `aperture_m` (its aperture at this instant, from A.7's law; `aperture(a0_m, law, tau_s, birth_s, t)` gives it); `gates` (default `(1.0,)`, fixed open). |

### `history`

Six kinds, named after design §3.5. Slots must be live slot names; values are moved, never
interpreted, so any sign convention passes through.

| Kind | Slot | Value |
| --- | --- | --- |
| `membrane_transferred_fmol` | patch | array [species] |
| `membrane_heat_pJ` | patch | float |
| `junction_transferred_fmol` | contact or bridge | array [species] |
| `junction_heat_pJ` | contact or bridge | float |
| `channel_transferred_fmol` | population | array [species] |
| `channel_heat_pJ` | population | array [species] |

### `Division`

| Field | Required | Content |
| --- | --- | --- |
| `parent` | yes | The dividing live cell. |
| `daughters` | yes | `(D1, D2)`: two new names (not live). |
| `f` | yes | Volume fraction to D1, in (0, 1). |
| `patches` | yes | `{parent patch: (D1's patch, D2's patch, a_k)}` over **exactly** the parent's live patches. a_k ∈ (0, 1) is the share of the patch's area and capacitance (and its populations' abundance) that goes to D1. Each daughter patch faces the parent patch's node. |
| `populations` | if any | `{parent population: (D1's, D2's)}` over exactly the populations on the parent's patches; their share is their patch's a_k. |
| `contacts` | if any | `{parent contact: (D1–M contact, D2–M contact, a_e)}` over exactly the contacts touching the parent; a_e ∈ [0, 1] is D1's share of the area (A.6 item 4). A share of 0 or 1 keeps the other daughter's contact live at zero area. |
| `carriers` | if some a_k ≠ f | `{species: t_s}`: charged species, t_s ≥ 0, Σ t_s = 1 (to 4 eps). Required when any a_k ≠ f (A.6 step 2). |
| `bridge` | no | Name of the bridge D1–D2 (`""` for none). |
| `bridge_a0_m` | with a bridge | Its aperture at birth, a_0 > 0 (m). |
| `bridge_gates` | no | Its declared gates, default `(1.0,)` (fixed open, A.7). |

### `Result`

- **`result.snapshot`:** the post-event `Snapshot`, in the same format.
  - **Removed:** the parent, its patches, the populations on them, its contacts and its bridges.
  - **Added daughters:** each a `Cell` in increment form (A.6 step 3); `charge_C` is the charge form Q_D1 = f Q_P + δq, Q_D2 = Q_P − Q_D1 (A.6 steps 2 and 6).
  - **Added daughter patches:** on the parent patch's node, with anchors and increments each split a_k and complement.
  - **Added daughter populations:** gates copied.
  - **Added daughter contacts:** written `(D, M)` with split areas and copied gates.
  - **Added bridge:** `(D1, D2)`, at `bridge_a0_m` with `bridge_gates`.
  - **Unchanged:** clefts and held nodes.
  - **`history`:** reads 0 at the retired slots.
- **`result.values`** (keys below), **`result.magnitudes`** (a magnitude, in the value's units, for
  the keys marked *m*), and **`result.identities`** (below).

| Key of `values` | *m* | Meaning |
| --- | --- | --- |
| `mismatch_C` | *m* | δq = Σ_k (a_k − f) q_k (C), at the pre-event view (A.6 step 2). |
| `delta_fmol` | *m* | δ_s per species (fmol), carried by the declared carriers. |
| `amounts_D1_fmol`, `amounts_D2_fmol` | *m* | n_D1 = f n_P + δ and its complement (A.6 step 3). |
| `reference_D1_fmol`, `reference_D2_fmol` | *m* | Anchors f n̄_P and complement. |
| `increment_D1_fmol`, `increment_D2_fmol` | *m* | Increments f Δ_P + δ and complement. |
| `moved_fmol` | *m* | `{parent: −Δ_P, D1: Δ_D1, D2: Δ_D2}`, the signed transfers (arrays). |
| `volume_D1_pL`, `volume_D2_pL` | *m* | f V_P and complement. |
| `background_D1_fmol`, `background_D2_fmol` | *m* | f X_P and complement. |
| `charge_reference_D1_C`, `charge_reference_D2_C` | *m* | The charge anchor split f and complement. |
| `charge_D1_C`, `charge_D2_C` | *m* | The daughters' node charges, in charge form (see `Cell.charge_C`). |
| `area_{k}_m2`, `capacitance_{k}_F` | *m* | For each daughter patch k: a_k × (anchor + increment) of its parent patch, and the complement. |
| `area_moved_m2`, `capacitance_moved_F` | – | `{parent patch: −increment, D1's patch: its increment, D2's patch: its increment}`. |
| `units_moved` | – | The same for population abundances. |
| `junction_gates_before`, `junction_gates_after` | – | `{slot: gates}` for every junction slot the event touches. A slot that is not live reads 0: the parent's contacts and bridges after, the daughter contacts and the new bridge before. The bridge opens with its declared gates; the daughter contacts take g_e (the lead's addition to A.6 item 5). |
| `record` | – | `{kind: {slot: value}}`: the retiring slots' history, moved out (A.6 item 5; design §3.5). |
| `charges_before_C`, `charges_after_C` | *m* | `{free node: Q}`, every cell's and cleft's node charge before and after the event (C). |
| `potentials_before_V`, `potentials_after_V` | *m* | `{node: φ}` over the held and free nodes, before and after the event. |
| `patch_q_before_C`, `patch_q_after_C` | – | `{patch: q_k}`, the cell-side patch charges before and after. |
| `plate_before_C`, `plate_after_C` | – | `{held node: plate charge}`, q_b = −Σ q_k over the patches facing it (A.2). |
| `image_charge_C` | *m* | `{held node: Δq_b}` across the event. |
| `capacitor_energy_change_J` | *m* | ΔU, with U = ½ Σ C_k V_k² (J). |
| `free_energy_change_pJ` | *m* | ΔG = G(D1) + G(D2) − G(P), absolute form, G(n, V) = 1e-3 RT Σ n (ln(n/V) − 1) (A.6 step 6). |
| `free_energy_parts_pJ` | – | `(G(D1), G(D2), G(P))`. |
| `unmixing_pJ` | *m* | The same change in a cancellation-free form, ≥ 0 by construction. |
| `unmixing_leading_pJ` | – | Its leading order, 1e-3 RT Σ δ²/(2 n f (1 − f)). |
| `work_pJ` | *m* | W = ΔG + 1e12 (ΔU − Σ_b φ_b Δq_b) (A.6 step 6). |

**Magnitudes (A.8, as amended by the lead's ruling of 14 November: pass at 64 eps × magnitude).**
- **Ordinary quantities:** each magnitude is the sum of the absolute values of the terms entering the quantity.
- **Node charges:** a cell's node charge has the magnitude M_i = |Q_i| + |Q̄_i| + 1e-15 F Σ_s |z_s Δ_{s,i}|.
  - Q̄_i is the cell's declared charge anchor and Δ_i its increments: for an input cell, its `charge_reference_C` and `increment_fmol`; for a daughter, its split anchor and the increments the map computes (as written in `result.snapshot`).
  - A cleft's charge has the magnitude |Q_c|.
  - A daughter's magnitude also carries what enters its charge form: f M_P + mag(δq) for D1; M_P plus that for D2.
  - `charges_before_C` and `charges_after_C` in `magnitudes` give every node charge's magnitude.
- **Solved potentials:** |K_ff⁻¹| (|K_ff| |φ_f| + |Q_f| + T_f + |K_fb| |φ_b|). This is the componentwise forward-error scale of a backward-stable solve, with each cell's term T_i = |Q̄_i| + 1e-15 F Σ_s |z_s Δ_{s,i}| carried through |K_ff⁻¹|; T is 0 for a cleft. The post-event solve takes the post-event cells' terms, the daughters' from their split anchors and computed increments.
- **Everything downstream** of the charges or the potentials carries these terms: patch voltages and charges, plate and image charges, ΔU, δq and δ, the daughters' amounts and increments, ΔG and W.
- **Without the terms:** `apply(snapshot, division, charge_term=False)` gives the magnitudes without the amendment, for comparison; the values are the same either way. With every charge anchor and increment zero, the two coincide exactly.
- **Constants:** `rops.EPS` is machine epsilon and `rops.TOLERANCE_EPS` = 64.

**`identities`**: `{name: (residual, magnitude)}`. Each residual is zero in exact arithmetic; it
passes when |residual| ≤ 64 eps × magnitude (elementwise). `result.worst()` returns the name and
the ratio residual / (eps × magnitude) of the worst. The names are:

| Group | Names |
| --- | --- |
| Contents | `amounts_sum`, `reference_sum`, `moved_sum`, `amounts_increment_form`, `volume_sum`, `background_sum` |
| Charge | `charge_sum`, `charge_follows_patches` (Q_D1 = Σ a_k q_k), `charge_content_{D1}`, `charge_content_{D2}` |
| Patches | `area_sum_{k}`, `capacitance_sum_{k}`, `area_moved_sum_{k}`, `capacitance_moved_sum_{k}`, `capacitance_increment_form_{k}` (k a parent patch) |
| Populations, contacts | `abundance_sum_{j}`, `units_moved_sum_{j}`, `contact_area_sum_{e}` |
| Electrostatics | `isopotential_{D1}`, `isopotential_{D2}`, `potential_unchanged_{node}` (every other free node), `patch_charge_{k}` (each daughter patch: q = a_k q_parent), `image_charge_{b}`, `capacitor_energy` |
| Free energy | `free_energy_forms` (absolute form against the cancellation-free form) |

### What raises `PartitionRefused` (a `ValueError`; nothing is modified)

- **The snapshot is malformed:**
  - species and valences differ in length;
  - a cell or cleft volume ≤ 0;
  - a patch whose cell is not a live cell, or whose node is not a live cleft or held node;
  - a patch with area or capacitance ≤ 0;
  - a population on a non-live patch, or with negative abundance;
  - a contact or bridge whose cells are not live;
  - a contact with negative area;
  - an unknown history kind, or history of a slot that is not live.
- **The division is inadmissible:**
  - the parent is not live;
  - the daughters are not two distinct new names;
  - f ∉ (0, 1), or some a_k ∉ (0, 1), or some a_e ∉ [0, 1];
  - the patch, population or contact map does not cover exactly the parent's;
  - a daughter slot or the bridge name is already live or repeated;
  - a contact joins the parent to itself;
  - **a bridge of the parent has aperture > 0** (its closure must end first: A.6 item 5, A.7; design §3.8);
  - a_0 is not positive and finite, or the bridge gates lie outside [0, 1];
  - carriers are missing while some a_k ≠ f; a carrier is not a charged species; a transference number is negative; or the transference numbers do not sum to 1.
- **The network has no held node:** a capacitor component without one (floating).
- **A daughter amount is ≤ 0 or non-finite** (A.6 step 7).

A closed bridge of the parent (aperture 0) is not refused: it retires with the parent, reads gate
0 and moves its history to the record.

### The bridge helpers (A.7)

- **`aperture(a0_m, law, tau_s, birth_s, t)`**, with `law` `"linear"` or `"exponential"`.
  - It returns a_0 for t ≤ t_b.
  - The linear law is exactly 0 from t_b + τ on; τ = ∞ keeps a_0.
  - **`closure_end(law, tau_s, birth_s)`** gives t_b + τ for the linear law and ∞ otherwise.
- **`bridge_diffusivities(D_free, sigma_cyt_S_m, composition_mM, z, temperature_K)`** returns
  D_s^cyt = D_s σ_cyt/σ_free, with σ_free at the given composition.
- **`bridge_conductance(a_m, D_cyt, composition_mM, z, temperature_K)`** returns G_b.
- **`free_conductivity(...)`** returns σ_free.

### Example (R-ops)

```python
from validation.division import partition_reference as rops

z = (1, 1, -1)
reference = (24.0, 280.0, 60.0)  # the parent's anchors (fmol)
increment = (0.1, -0.3, 0.0)  # its increments (fmol)
charge = -2.4e-13  # its node charge at the view (C)
amounts = [r + i for r, i in zip(reference, increment)]
background = charge / (1e-15 * rops.F) - sum(zs * n for zs, n in zip(z, amounts))
snapshot = rops.Snapshot(
    species=("Na", "K", "Cl"),
    z=z,
    temperature_K=300.0,
    held={"bath": 0.0},
    cells={"P": rops.Cell(reference, increment, 2.0, background, charge)},
    clefts={"c1": rops.Cleft(amounts_fmol=(1.8, 0.065, 1.9), volume_pL=0.013, charge_C=1.6e-14)},
    patches={
        "P.old": rops.Patch("P", "bath", area_reference_m2=4e-10, capacitance_reference_F=4e-12),
        "P.furrow": rops.Patch(
            "P",
            "c1",
            area_reference_m2=1e-11,
            capacitance_reference_F=1e-13,
            area_increment_m2=1.6e-11,
            capacitance_increment_F=1.6e-13,
        ),
    },
)
division = rops.Division(
    parent="P",
    daughters=("D1", "D2"),
    f=0.4,
    patches={"P.old": ("D1.old", "D2.old", 0.3), "P.furrow": ("D1.furrow", "D2.furrow", 0.7)},
    carriers={"K": 0.7, "Cl": 0.3},
    bridge="b",
    bridge_a0_m=3e-8,
)
result = rops.apply(snapshot, division)
d1 = result.snapshot.cells["D1"]
name, ratio = result.worst()
```

## R-tissue: `simulate_static` and `simulate_divisions`

```python
from validation.division import cleft_tissue_reference as rt
run = rt.simulate_divisions(world, t_end, record=(...), rtol=1e-10, method="Radau", atol=None)
run = rt.simulate_static(world, t_end, record=(...), rtol=1e-10, method="Radau", atol=None)
```

The two entry points:
- **`simulate_static`** refuses a world with divisions.
- **`simulate_divisions`** refuses a world converted from an R-full egg (`from_egg`; the J2 bright line). It loads R-ops when a division or bridge needs it.

Both validate the world first; `check_world(world)` does the same without running. The other
arguments:
- **`record`:** the times (s) at which to record; each becomes an integration breakpoint.
- **`rtol`, `method`:** scipy's `solve_ivp` settings.
- **`atol`:** a dict of absolute tolerances (see Tolerances).

### Declaring a `World`

| Field | Content |
| --- | --- |
| `temperature_K` | K. |
| `bath_mM` | The held bath's composition, every species > 0 (mM). The bath is held at 0 V and supplies whatever it exchanges (A.1). |
| `cells` | `{name: CellSpec}`. |
| `patches` | `{name: PatchSpec}`. |
| `clefts` | `{name: CleftSpec}` (default `{}`). |
| `faces` | `{name: FaceSpec}` (default `{}`). |
| `contacts` | `{name: ContactSpec}` (default `{}`). |
| `injections` | A tuple of `InjectionSpec` (default `()`). |
| `divisions` | `{name: DivisionSpec}` (default `{}`). |
| `species`, `z` | Default `("Na", "K", "Cl")`, `(1, 1, -1)`. |
| `origin` | Leave the default `"world"`. |

The bath's name is `rt.BATH` (`"bath"`).

**Liveness.**
- A founder is live from t = 0; a daughter from its division; a parent until its division (then retired).
- A patch is live with its cell, and from its onset for an onset patch.
- A cleft is live from the onset of its patches.
- A face is live when both its nodes are; a contact or bridge when both its cells are (A.1).
- At one instant, the divisions due are applied first (in declared order), then the onsets.

**`CellSpec(volume_pL, mM, initial_V)`.**
- A **founder** (a cell that no division has as a daughter) declares `volume_pL` (> 0) and `mM` (every species, > 0).
- `initial_V` is the founder's start potential. When it is NaN (the default), the founder starts at the zero-current potential of its bath-facing patches. That is R-full's initial-state rule, which also sets the fixed background from the initial charge.
- A **daughter** declares nothing: `CellSpec()`.

**`PatchSpec(cell, node, permeability_m_s, area_m2, capacitance_F, specific_capacitance_F_m2, onset_s, schedule)`.**

General fields:
- `node` is `"bath"` or a cleft.
- `permeability_m_s` is P_s per unit area (m/s, per species): constant-field, P_s A_k (A.3).
- `specific_capacitance_F_m2` is c_d of inserted membrane: dC = c_d dA.
- `schedule` is `((t_start, rate_m2_s), ...)`, in absolute times, sorted, with rates ≥ 0.
  - The rate is 0 before the first start, and the last rate continues.
  - A nonzero rate is allowed only while the patch is live (A.4). So a parent's furrow schedule ends (rate 0) by its division, and each daughter patch declares its own schedule (each its share).
  - A nonzero rate needs c_d > 0.

There are three kinds of patch:
- **A founder's patch** has no onset (`onset_s` NaN). It faces the bath and declares `area_m2` and `capacitance_F`.
- **An onset patch** declares `onset_s` within its cell's life, and `area_m2` = A_on. Its `capacitance_F` is c_d A_on unless declared. It faces a cleft that is not yet live: every patch of a cleft opens together, and a later onset on a live cleft is refused (A.4).
- **A daughter's patch** has no onset and leaves `area_m2` and `capacitance_F` unset; its division writes them (A.6 item 4). It must appear in its division's patch map, with the parent patch's node, permeability and c_d.

**`CleftSpec(gap_width_m)`.**
- The lumen volume is V_c = w Σ_live A_k / 2 over its live facing patches, with V_on = w A_on / 2 (A.5). It is filled at bath composition as it grows.
- A cleft opens at zero charge, with every species but the last charged one at bath composition. That is R-full's convention, the same as bath composition for a neutral bath (A.4, A.1).

**`FaceSpec(nodes, a_over_l_m, diffusivity_m2_s, law)`.**
- An access face joins two distinct outside nodes (cleft–bath, or cleft–cleft such as a central joint).
- The flux is positive from `nodes[0]`, with k_s = (A/L) D_s.
- `law` is `"logmean"` (default) or `"constant_field"`: R-full's two laws (A.3).

**`ContactSpec(cells, permeability_m_s, area_m2, gate)`.**
- A constant-field junction g P_s A_e with a fixed gate in [0, 1] (no gate kinetics).
- A contact between founders declares `area_m2` (> 0) and `gate`.
- A daughter contact leaves `area_m2` unset and is named in its division's contact map. Its
  `cells` are its daughter and the parent contact's other cell, and its permeability is the
  parent contact's. It takes the parent contact's gate; its own `gate` field is not read.
- The current is reported from `cells[0]` to `cells[1]`, in the declared order.

**`InjectionSpec(cell, pulses, carriers)`.**
- `pulses` is R-full's `Pulses` (`validation/division/cleft_egg_reference.py`). Its fields are `amplitude_A`, `duration_s`, `period_s`, `first_onset_s`, `first_sign` (the sign alternates pulse by pulse), `sample_s` and `enabled`. R-tissue ignores its carrier fields.
- `carriers` is `{species: fraction}` over charged species, with fractions ≥ 0 that sum to 1. A positive current carries cations in, and dn_s/dt gains 1e15 f_s I / (z_s F) (A.3).
- Every pulse before `t_end` must lie within its cell's life.

**`DivisionSpec(parent, daughters, time_s, f, patches, carriers, contacts, bridge, bridge_spec)`.**
- **Maps:** `patches`, `carriers` and `contacts` are as in R-ops' `Division`.
  - `patches` covers exactly the parent's patches live at `time_s`: its base patches and its onset patches with onset < `time_s`.
  - `contacts` covers exactly the contacts touching the parent that are live at `time_s`.
- **Cells:** a cell is at most one division's parent and at most one division's daughter. A daughter divides strictly after its birth. Every cell needs a patch on the bath.
- **`bridge`, `bridge_spec`:**
  - `bridge` is the bridge's name, declared through `BridgeSpec(a0_m, diffusivity_m2_s, law="linear", tau_s=inf, gate=1.0)`.
  - The bridge's P A is 2 g a(t) D_s^cyt, with `diffusivity_m2_s` = D_s^cyt per species (from `rops.bridge_diffusivities`).
  - The law is linear or exponential (A.7).
  - **A parent whose own bridge is still open at its division is refused** (aperture > 0; A.6 item 5, design §3.8). A daughter that divides again therefore needs the linear law with `time_s` ≥ its birth + τ.

### Tolerances

`atol` is a dict over five keys. The units are fmol of charge equivalent for the charges, fmol
for the amounts and pJ for the heat.

| Key | Default (`rt.ATOL`, R-full's, egg scale) | `SMALL` (the division tests', tissue scale) |
| --- | --- | --- |
| `cell_charge` | 1e-9 | 1e-15 |
| `cell_amount` | 1e-6 | 1e-12 |
| `cleft_charge` | 1e-9 | 1e-17 |
| `cleft_amount` | 1e-9 | 1e-14 |
| `heat` | 1e-12 | 1e-15 |

- **Scale `atol` to the world.** The default suits node charges of order 10 fmol. For cells of tissue scale (node charges of order 1e-3 fmol), pass the `SMALL` values or values scaled likewise.
- `SMALL` is defined in `tests/unit/test_cleft_tissue_reference.py`. Copy its values rather than importing a test module.
- A dict with some keys overrides only those keys.

### Output: `TissueRun`

| Field | Content |
| --- | --- |
| `at` | `{t: record}` for each requested time. |
| `onset_V`, `sample_V` | One dict per injection, `{pulse k: V of its cell}`: at the pulse's front edge, and one `sample_s` later. |
| `events` | One dict per division applied: `time_s`, `division` (its name), `before` (the R-ops `Snapshot` of the live tissue just before it) and `result` (R-ops' `Result`). |
| `initial` | `{founder: {V, background_fmol, charge_fmol}}` at t = 0. |
| `steps`, `wall_s` | Integrator steps and wall time. |

The `before` snapshot gives cells as zero anchors with their amounts as increments. Its patches
carry their area and capacitance as anchors.

**A record** (`run.at[t]`) holds the live tissue at t:

| Key | Content |
| --- | --- |
| `t` | The time (s). |
| `V` | `{live cell: Vm}` (V); Vm = φ_i − φ_b with the bath at 0 V (A.8). |
| `phi` | `{live free node: φ}` (V), cells and clefts. |
| `cells` | `{live cell: {mM, amounts_fmol, volume_pL, charge_C, background_fmol}}`, every species. |
| `lumens` | `{live cleft: {mM, amounts_fmol, volume_pL, charge_C}}`, every species (A.8: composition and volume). |
| `patches` | `{live patch: {area_m2, capacitance_F, V}}` with V = φ(cell) − φ(node). |
| `junctions` | `{live contact or bridge: {kind, cells, current_A, gate[, aperture_m]}}`. `current_A` = Σ_s z_s F J_s from `cells[0]` to `cells[1]` (for a bridge, D1 to D2; A.8). Bridges also carry `aperture_m`. |
| `junction_gates` | `{every declared contact and bridge: gate}`, 0 for a slot that is not live (the lead's addition to A.6 item 5). |
| `heat_pJ` | Cumulative insertion heat, ½ Σ c_d r_k V_k² integrated (A.4). |
| `capacitor_energy_J` | ½ Σ C_k V_k² over the live patches. |
| `plate_charge_C` | The bath's plate charge, −Σ C_k V_k over its patches. |
| `phase` | `{cells, clefts, patches, contacts, bridges}`, each `{name: "pending" \| "live" \| "retired"}`. |

**The state recorded at an event instant.**
- A record at time t is taken **after** the events at t (divisions, then onsets). That is R-full's convention, and A.8 states the records.
- At a division time the record shows the daughters live and the parent retired.
- The pre-event state at that instant is `run.events[i]["before"]`, with `result.values["potentials_before_V"]`.
- No event is applied at `t_end` itself.

### Other refusals

- **`ValueError` from validation**, as listed above:
  - a founder or daughter declaration in the wrong form;
  - a patch, face, contact, injection or division that breaks the rules above;
  - insertion or a pulse outside its slot's life;
  - a cell without a bath patch;
  - a parent's open bridge.
- **`ValueError` at run time:** an onset on a non-live cell or an already-live cleft.
- **`PartitionRefused` at a division:** see R-ops.
- **`RuntimeError`:** the integrator fails.

### Example (R-tissue, division run)

```python
from validation.division import cleft_egg_reference as rfull  # for Pulses only
from validation.division import cleft_tissue_reference as rt
from validation.division import partition_reference as rops

z, temperature = (1, 1, -1), 300.0
cytosol, bath = (12.0, 140.0, 30.0), (140.0, 5.0, 145.0)
d_free = (1.33e-9, 1.96e-9, 2.03e-9)
old, furrow = (1e-10, 2e-9, 5e-10), (5e-10, 2e-8, 0.0)
share = ((0.1, 1e-10), (0.2, 0.0))  # each daughter's furrow: half of the parent's rate
world = rt.World(
    temperature_K=temperature,
    bath_mM=bath,
    cells={"P": rt.CellSpec(volume_pL=2.0, mM=cytosol), "D1": rt.CellSpec(), "D2": rt.CellSpec()},
    clefts={"c": rt.CleftSpec(gap_width_m=1e-6)},
    patches={
        "P.old": rt.PatchSpec("P", "bath", old, area_m2=4e-10, capacitance_F=4e-12),
        "P.furrow": rt.PatchSpec(
            "P",
            "c",
            furrow,
            area_m2=1e-11,
            specific_capacitance_F_m2=1e-2,
            onset_s=0.02,
            schedule=((0.02, 2e-10), (0.1, 0.0)),
        ),
        "D1.old": rt.PatchSpec("D1", "bath", old),
        "D2.old": rt.PatchSpec("D2", "bath", old),
        "D1.furrow": rt.PatchSpec("D1", "c", furrow, specific_capacitance_F_m2=1e-2, schedule=share),
        "D2.furrow": rt.PatchSpec("D2", "c", furrow, specific_capacitance_F_m2=1e-2, schedule=share),
    },
    faces={"c.access": rt.FaceSpec(nodes=("c", "bath"), a_over_l_m=1e-7, diffusivity_m2_s=d_free)},
    injections=(
        rt.InjectionSpec(
            "D1",
            rfull.Pulses(
                amplitude_A=1e-13, duration_s=0.02, period_s=0.05, first_onset_s=0.12, sample_s=0.01
            ),
            {"K": 0.5, "Cl": 0.5},
        ),
    ),
    divisions={
        "d1": rt.DivisionSpec(
            parent="P",
            daughters=("D1", "D2"),
            time_s=0.1,
            f=0.5,
            patches={"P.old": ("D1.old", "D2.old", 0.5), "P.furrow": ("D1.furrow", "D2.furrow", 0.5)},
            bridge="b",
            bridge_spec=rt.BridgeSpec(
                a0_m=3e-8,
                diffusivity_m2_s=rops.bridge_diffusivities(d_free, 0.5, cytosol, z, temperature),
                law="linear",
                tau_s=0.05,
            ),
        )
    },
)
small = dict(cell_charge=1e-15, cleft_charge=1e-17, cell_amount=1e-12, cleft_amount=1e-14, heat=1e-15)
run = rt.simulate_divisions(world, 0.3, record=(0.05, 0.1, 0.15, 0.3), atol=small)
vm = run.at[0.15]["V"]["D1"]
lumen = run.at[0.15]["lumens"]["c"]
bridge_current = run.at[0.15]["junctions"]["b"]["current_A"]
partition = run.events[0]["result"]
```

For a **static run**, declare the same kind of world without `divisions` (and so without
daughter cells and patches), and call `rt.simulate_static(world, t_end, record=..., atol=...)`.
