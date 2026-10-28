"""Manufactured isolated native Mito inputs with explicit physical units."""

from copy import deepcopy


def base():
    return dict(
        name="cached-zero",
        species_ids=["Na", "K", "Cl", "Ca", "M"],
        species_valence=[1, 1, -1, 2, -1],
        moving_species=[0, 1, 2, 3],
        cell_volume_m3=[1e-15, 1.5e-15, 2e-15],
        cell_area_m2=[1e-9, 1.2e-9, 1.5e-9],
        specific_capacitance_F_m2=0.05,
        membrane_thickness_m=7.5e-9,
        temperature_K=310.0,
        faraday_C_mol=96485.0,
        gas_constant_J_mol_K=8.314,
        cytosol_mM=[[12.0] * 3, [140.0] * 3, [10.0] * 3, [0.001] * 3, [142.002] * 3],
        mitochondria_mM=[[20.0] * 3, [100.0] * 3, [30.0] * 3, [0.1] * 3, [90.2] * 3],
        charge_C=[0.0] * 3,
        voltage_V=[0.0] * 3,
        extra_charge_density_C_m3=[0.0] * 3,
        dt_s=0.001,
        refresh_before=False,
    )


def cases():
    result = []

    def add(name, **changes):
        row = base()
        row.update(name=name, **changes)
        result.append(row)
        return row

    add("cached-zero")
    add("negative-cached-voltage", voltage_V=[-0.15, -0.07, -0.03])
    add("positive-cached-voltage", voltage_V=[0.02, 0.04, 0.06])
    add("mixed-cached-voltage", voltage_V=[-0.1, 0.0, 0.05])
    add("extra-charge-before-refresh", extra_charge_density_C_m3=[-7500.0, -3500.0, 2000.0])
    add(
        "explicit-refresh-before",
        extra_charge_density_C_m3=[-7500.0, -3500.0, 2000.0],
        refresh_before=True,
    )
    add("reverse-ion-order", moving_species=[3, 2, 1, 0])
    add("one-moving-ion", moving_species=[1])
    add("no-moving-ions", moving_species=[])
    add("zero-time-refresh", dt_s=0.0, extra_charge_density_C_m3=[-7500.0, 0.0, 2000.0])
    add("different-temperature", temperature_K=280.0, voltage_V=[-0.05] * 3)
    add(
        "explicit-si-constants",
        faraday_C_mol=96485.33212331002,
        gas_constant_J_mol_K=8.31446261815324,
        voltage_V=[-0.05] * 3,
    )
    add("altered-live-cytosol-volume", live_cytosol_volume_m3=[2e-15, 3e-15, 4e-15])
    for label, valence in (("cation", 1), ("anion", -1), ("neutral", 0)):
        row = add("single-" + label)
        row.update(
            species_ids=[label],
            species_valence=[valence],
            moving_species=[0],
            cytosol_mM=[[10.0] * 3],
            mitochondria_mM=[[20.0] * 3],
        )
    row = add("zero-diffusivity")
    row["diffusivity_m2_s"] = [[0.0] * 3 for _ in row["species_ids"]]
    row = add("unused-channel-copies")
    row["base_diffusivity_m2_s"] = [[1e-12] * 3 for _ in row["species_ids"]]
    row["channel_diffusivity_m2_s"] = [[1e-10] * 3 for _ in row["species_ids"]]
    for label, cy, mi in (
        ("zero-cytosol", 0.0, 20.0),
        ("zero-mitochondria", 10.0, 0.0),
        ("zero-both", 0.0, 0.0),
    ):
        row = add(label)
        row.update(
            species_ids=["neutral"],
            species_valence=[0],
            moving_species=[0],
            cytosol_mM=[[cy] * 3],
            mitochondria_mM=[[mi] * 3],
        )
    return result


def neutral_relaxation():
    row = deepcopy(next(row for row in cases() if row["name"] == "single-neutral"))
    row.update(
        name="physical-neutral-pair",
        cell_volume_m3=[1e-15],
        cell_area_m2=[1e-9],
        cytosol_mM=[[10.0]],
        mitochondria_mM=[[30.0]],
        charge_C=[0.0],
        voltage_V=[0.0],
        extra_charge_density_C_m3=[0.0],
    )
    return row
