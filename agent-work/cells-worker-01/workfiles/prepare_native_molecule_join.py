"""Copy the accepted outer engine and add owned chemistry state at its late seam."""

from pathlib import Path

source = Path("src/cells/processes/betse_normal_network_join.py").read_text()
source = source.replace(
    "Rectangular normal join with endogenous native network feedback.",
    "Rectangular normal join with real molecule chemistry and native molecule_mover.",
)
source = source.replace("betse_normal_network_join_source", "betse_normal_molecule_source")
source = source.replace(
    "betse_normal_native_network_feedback_v1_5_0@1",
    "betse_normal_native_molecule_chemistry_transport_v1_5_0@1",
)
source = source.replace(
    "cells.betse_normal_network_join_inputs@1", "cells.betse_normal_molecule_join_inputs@1"
)
old = """        None,
    )


def _values(arrays):"""
assert source.count(old) == 1
source = source.replace(
    old,
    """        network_source.initial_cache(binding.definition["network"]),
    )


def _values(arrays):""",
    1,
)
needle = """                    incoming_extra_current=extra_current_A_m2,
"""
assert source.count(needle) == 1
source = source.replace(
    needle,
    needle
    + """                    configured_temperature_K=ib.kernel.configured_temperature_K,
                    membrane_thickness_m=ib.kernel.membrane_thickness_m,
                    bath_volume_m3=ib.kernel.bath_volume_m3,
                    cluster_open=ib.kernel.cluster_open,
                    geometry=dict(owner=ib.kernel.owner, partner=ib.kernel.partner,
                        boundary=ib.kernel.boundary, membrane_area_m2=ib.kernel.area_m2,
                        cell_volume_m3=ib.kernel.cell_volume_m3, owner_sum=ib.kernel.owner_sum,
                        gap_length_m=ib.kernel.gap_length_m),
""",
    1,
)
needle = """                    controls_before=effective_controls,
"""
assert source.count(needle) == 1
source = source.replace(
    needle,
    needle
    + """                    molecule_states_before=network_source.snapshot(core.molecules),
                    molecular_geometry=dict(owner=ib.kernel.owner, partner=ib.kernel.partner,
                        boundary=ib.kernel.boundary, membrane_area_m2=ib.kernel.area_m2,
                        cell_volume_m3=ib.kernel.cell_volume_m3, owner_sum=ib.kernel.owner_sum,
                        gap_length_m=ib.kernel.gap_length_m, radius_m=binding.definition["network"]["radius_m"]),
                    configured_temperature_K=ib.kernel.configured_temperature_K,
                    membrane_thickness_m=ib.kernel.membrane_thickness_m,
                    bath_volume_m3=ib.kernel.bath_volume_m3,
                    cluster_open=ib.kernel.cluster_open,
                    gap_open=opening.copy(),
""",
    1,
)
source = source.replace(
    'observe("network_chemistry_empty")', 'observe("network_molecule_chemistry")'
)
source = source.replace(
    "empty_chemistry_run_loop_executed=True", "configured_chemistry_run_loop_completed=True"
)
needle = """                        cache_after=network_source.cache(core),
"""
assert source.count(needle) == 1
source = source.replace(
    needle,
    needle
    + """                        molecule_frames=tuple(core.molecule_frames),
                        mover_frames=tuple(core.mover_frames),
                        molecule_states_after=network_source.snapshot(core.molecules),
                        chemical_rhs_evaluated=any(row["stage"] == "rhs_ready" for row in core.molecule_frames),
                        executed_chemistry=any(row["stage"] == "rhs_ready" for row in core.molecule_frames)
                            and (bool(binding.definition["network"]["reactions"]) or any(row["growth"]["enabled"] for row in binding.definition["network"]["molecules"])),
                        molecular_transports_completed=sum(row["stage"] == "transport_after" for row in core.molecule_frames),
""",
    1,
)
needle = """                network.update(
                    values_before=network_values_before,"""
assert source.count(needle) == 1
source = source.replace(
    needle,
    """                feedback["cache_after"] = network_source.checked_cache(feedback["cache_after"], binding.definition["network"])
                network.update(
                    values_before=network_values_before,""",
    1,
)
source = source.replace(
    "extra_charge_C_m3=np.zeros(cell.shape[1]),",
    "extra_charge_C_m3=ions.freeze(core.extra_rho_cells),",
    1,
)
source = source.replace("user_molecules=0,", "user_molecules=len(core.molecules),", 1)
source = source.replace("reactions=0,", "reactions=len(core.reactions),", 1)
source = source.replace(
    "energy_charge=np.zeros(cell.shape[1]),", "energy_charge=ions.freeze(core.chi),", 1
)
needle = """
                executed_chemistry=False,
"""
assert source.count(needle) == 1
source = source.replace(
    needle,
    """
                executed_chemistry=material.network_feedback["executed_chemistry"],
""",
    1,
)
# The pre-network observation must still truthfully precede all rate evaluation.
source = source.replace(
    """                    executed_chemistry=False,
""",
    """                    executed_chemistry=False,
""",
    1,
)
needle = """    mapping = raw["network"]["membrane_to_environment"]"""
if needle in source:
    source = source.replace(
        needle,
        """    if not np.array_equal(np.asarray(raw["network"]["radius_m"], np.float64), pump_binding.gated_binding.voltage_binding.kernel.radius_m):
        raise ValueError("Molecule intracellular radius must share the explicit voltage geometry")
"""
        + needle,
        1,
    )
else:
    needle = """    result = Binding(pump_binding, ions.freeze(raw), "")"""
    assert source.count(needle) == 1
    source = source.replace(
        needle,
        """    if not np.array_equal(np.asarray(raw["network"]["radius_m"], np.float64), pump_binding.gated_binding.voltage_binding.kernel.radius_m):
        raise ValueError("Molecule intracellular radius must share the explicit voltage geometry")
"""
        + needle,
        1,
    )
output = Path("src/cells/processes/betse_normal_molecule_join.py")
with output.open("x") as stream:
    stream.write(source)
print("Created separate joined engine; five numerical outer helpers remain literal copies")
