"""Explicit clocks, owners and source-noise fixtures, without hidden RNG draws."""

from copy import deepcopy
from math import cos, sin


def base():
    owner = [1, 0, 2, 1, 0, 2, 1]
    return dict(
        name="normal-SIM",
        seed=17,
        phase="SIM",
        solver="normal",
        dynamic_enabled=True,
        protein_enabled=True,
        is_ecm=True,
        fast_update_ecm=False,
        cluster_open=False,
        static_level=2.0,
        dynamic_level=3e-8,
        dt_s=0.002,
        times_s=[0.0, 0.002, 0.004],
        ion_ids=["Na", "K", "P"],
        cell_ids=["C7", "A2", "Z9"],
        membrane_ids=[f"m{x}" for x in (8, 2, 4, 1, 9, 0, 6)],
        environment_ids=["env7", "env2", "env9", "env4"],
        owner=owner,
        environment_owner=[2, 0, 1, 2, 0, 3, 2],
        membrane_area_m2=[(i + 1) * 1e-12 for i in range(7)],
        cell_volume_m3=[3e-16, 4e-16, 5e-16],
        environment_volume_m3=2.0**-52,
        bath_parameter_volume_m3=2e-16,
        delta_m=2.0**-17,
        height_m=2.0**-18,
        initial_diffusion_m2_s=[[(i + 1) * (j + 1) * 1e-18 for j in range(7)] for i in range(3)],
        initial_cell_mol_m3=[8.0, 9.0, 10.0],
        initial_membrane_mol_m3=[6.0] * 7,
        initial_environment_mol_m3=[4.0, 5.0, 6.0, 7.0],
        boundary_cells=[0, 0, 1, 2, 2, 2],
        modulator_domain="membrane",
        modulator_offset=0.2,
        target_count=7,
        static_as_list=False,
        run_microtubule=False,
        micro=dict(
            theta=[0.1 * (i + 1) for i in range(7)],
            length_m=[1e-6 * (1 + 0.05 * i) for i in range(7)],
            drag_native=[1e-17 * (1 + 0.1 * i) for i in range(7)],
            ux=[0.1, 0.2, 0.15],
            uy=[0.2, 0.1, 0.25],
            kb=1.38e-23,
            T=300.0,
            sim_T=295.0,
            dilation=2.0,
            modulator=[1.0] * 7,
            charge_C=[-1e-16] * 7,
            E_x=[0.0] * 3,
            E_y=[0.0] * 3,
            tethered=True,
            normal=[[cos(i + 0.2), sin(i + 0.2)] for i in range(7)],
            partner=[3, 4, 5, 0, 1, 2, 6],
            neighbor_length_m=[1e-5] * 6 + [-1.0],
        ),
    )


def cases():
    result = [base()]

    def add(name):
        item = base()
        item["name"] = name
        result.append(item)
        return item

    item = add("static-zero-still-draws")
    item["static_level"] = 0.0
    item = add("static-negative-valid")
    item["static_level"] = -0.5
    item = add("static-native-list")
    item["static_as_list"] = True
    item = add("INIT-skips-dynamic-and-events")
    item["phase"] = "INIT"
    item = add("dynamic-disabled")
    item["dynamic_enabled"] = False
    item = add("protein-disabled")
    item["protein_enabled"] = False
    item = add("fast-loop-no-dynamic")
    item["solver"] = "fast"
    item = add("zero-dynamic-level-still-draws")
    item["dynamic_level"] = 0.0
    item = add("negative-dynamic-level")
    item["dynamic_level"] = -3e-8
    item = add("clock-labels-do-not-set-dt")
    item["times_s"] = [0.0, 0.2, 0.8]
    item = add("half-dt-six-calls")
    item["dt_s"] = 0.001
    item["times_s"] = [i * 0.001 for i in range(6)]
    item = add("non-ECM-mixed-bath")
    item["is_ecm"] = False
    item["environment_ids"] = ["bath"]
    item["environment_owner"] = [0] * 7
    item["initial_environment_mol_m3"] = [5.0]
    item = add("fast-ECM-injective")
    item["fast_update_ecm"] = True
    item["environment_ids"] = [f"e{i}" for i in range(7)]
    item["environment_owner"] = list(range(7))
    item["initial_environment_mol_m3"] = [5.0] * 7
    item = add("boundary-cell-axis")
    item["modulator_domain"] = "cell"
    item["target_count"] = 3
    item = add("boundary-negative-offset")
    item["modulator_offset"] = -0.3
    for label in (
        "zero-field",
        "tethered-drift",
        "untethered-drift",
        "dilation-zero",
        "zero-correlation",
    ):
        item = add("disabled-microtubule-" + label)
        item["run_microtubule"] = True
        if "drift" in label:
            item["micro"].update(E_x=[10.0, 20.0, 5.0], E_y=[5.0, -10.0, 20.0])
        if label == "untethered-drift":
            item["micro"]["tethered"] = False
        if label == "dilation-zero":
            item["micro"]["dilation"] = 0.0
        if label == "zero-correlation":
            item["micro"].update(ux=[0.0] * 3, uy=[0.0] * 3)
    return result


def limitations():
    result = []

    def add(name):
        item = base()
        item["name"] = name
        result.append(item)
        return item

    item = add("missing-potassium-index")
    item["ion_ids"] = ["Na", "P"]
    item["initial_diffusion_m2_s"] = item["initial_diffusion_m2_s"][:2]
    item = add("negative-static-diffusion")
    item["static_level"] = -4.0
    item = add("nonboolean-dynamic-guard")
    item["dynamic_enabled"] = 2
    item = add("fast-ECM-duplicate-overwrite")
    item["fast_update_ecm"] = True
    item = add("negative-protein-clamp")
    item["dynamic_level"] = 1e-2
    item["initial_cell_mol_m3"] = [1e-9] * 3
    item["initial_environment_mol_m3"] = [1e-9] * 4
    item = add("non-ECM-heterogeneous-bath-collapse")
    item["is_ecm"] = False
    item["initial_environment_mol_m3"] = [float(i + 1) for i in range(7)]
    item = add("boundary-empty")
    item["boundary_cells"] = []
    item = add("boundary-subset-axis")
    item["target_count"] = 2
    item = add("boundary-equal-count-axis")
    item["cell_ids"] = [f"C{i}" for i in range(7)]
    item["owner"] = list(reversed(range(7)))
    item["cell_volume_m3"] = [4e-16] * 7
    item["initial_cell_mol_m3"] = [8.0] * 7
    item["target_count"] = 7
    item["modulator_domain"] = "cell"
    item = add("zero-source-dt-still-draws")
    item["dt_s"] = 0.0
    item = add("missing-microtubule-parameters")
    item["micro_init_failure"] = "missing"
    item = add("microtubule-invalid-drag-initializer")
    item["micro_init_failure"] = "drag"
    item = add("microtubule-missing-correlation")
    item["run_microtubule"] = True
    item["micro_failure"] = "missing-correlation"
    item = add("microtubule-negative-time")
    item["run_microtubule"] = True
    item["dt_s"] = -0.002
    return result


def distribution():
    item = deepcopy(base())
    item["samples"] = 32768
    item["choice_samples"] = 8192
    item["name"] = "native-distributions"
    return item
