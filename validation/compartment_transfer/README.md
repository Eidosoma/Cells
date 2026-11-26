# Compartment transfer against local destruction (FR-33): donor, receiver and loss together

A maintained example (D251) of the fields that report, together:
- the material in a donor compartment;
- the material in the receiver;
- the cumulative loss.

It runs one world with two arms, transfer (T) and local destruction (D), and the request's control.
The code is in `example.py`; the test `tests/unit/test_compartment_transfer_example.py` runs it.

## The world

One cell owns two compartments (`cells.operator.cell_owned_compartments@1`). Each is a finite node bounded by one
patch that no ion crosses, and each holds the same amount of its own labelled neutral species.

| Arm | Species and node | What empties it | Rate |
| --- | --- | --- | --- |
| T, transfer | `ST` in `ecs_0` | `cells.operator.scheduled_species_exchange@1`'s first-order import releases it into the cell | kappa = k_u A 1e15 / V_o |
| D, local destruction | `SD` in `ecs_1` | `cells.operator.scheduled_species_turnover@1` clears it at its node | the same kappa, formed by the same operations |

## What it exports per row, per arm

| Export | Field | Units |
| --- | --- | --- |
| `donor_fmol` | the species' amount in its compartment: the node's reference plus `extracellular_amount_increment` | fmol |
| `receiver_fmol` | its amount in the cell: the cell's reference plus `amount_increment` | fmol |
| `loss_fmol` | turnover's cumulative cleared amount at the compartment's node: `turnover_outside_cleared_fmol`, per species and outside node | fmol |
| `transfer_fmol` | exchange's cumulative released amount: −`exchange_moved_fmol`, which counts export positive, so a release is negative | fmol |

## The control

- **The donors fade identically,** n0 exp(−kappa t). At these settings they are equal bit for bit.
- **Only T's receiver rises,** by exactly what the release moved. D's receiver is unchanged.
- **Only D's cumulative loss rises,** by exactly what its donor lost. T's loss stays 0.

## Which field names who lost material, under region-selective loss

**Each loss record names its region and its species row:**
- `turnover_outside_cleared_fmol` [species, outside node] names the node, here `ecs_1`;
- `turnover_cleared_fmol` [species, cell] names the cell;
- `exchange_moved_fmol` [route] names the route, and with it the patch and its donor node.

**What no field names** is a population *within* one species row, such as a labelled cohort or an
age class:
- **a labelled cohort:** declare it as its own species, as this example does with `ST` and `SD`;
- **an age class:** age-selective loss has no field. That is FR-25's engine work.

## Run it

```
PYTHONPATH=src:. JAX_ENABLE_X64=1 JAX_PLATFORMS=cpu /mnt/workspaces/Cells/venv-cpu/bin/python -m validation.compartment_transfer.example
```
