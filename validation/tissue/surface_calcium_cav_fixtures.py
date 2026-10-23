"""Manufactured CaV populations sharing finite free cytosol with HCN/Na/K/ER.

Seven explicitly added populations coexist with the older dedicated CaV1.2
patch routes. They are distinct populations, never an implicit duplicate route.
"""

from copy import deepcopy

from validation.tissue import surface_calcium_kv1_fixtures as base

ARMS = base.ARMS
LAWS = (
    "betse_cav1p2_m2h@1",
    "betse_cav1p3_m2h@1",
    "betse_cav2p1_m@1",
    "betse_cav2p2_m2h_regularized@1",
    "betse_cav2p3_mh@1",
    "betse_cav3p1_mh_source_branch@1",
    "betse_cav3p3_mh@1",
)


def definition(arm="baseline", *, backend="cpu", padded=True):
    raw = base.definition(arm, backend=backend, padded=padded)
    raw["model"]["id"] = "resolved_calcium@6"
    ion = raw["model"]["ionic"]
    ion["id"] = "resolved_tissue@7"
    for index, law in enumerate(LAWS):
        population = deepcopy(ion["channels"][index % 4])
        population.update(
            id=f"cav_population_{index}",
            kinetic_law=law,
            permeant_ions=[dict(species_id="Ca", relative_permeability=1.0)],
            initial_gate=[0.2 + 0.05 * index, 0.7 - 0.04 * index],
            max_permeability_m_per_s=1e-9,
            abundance=0.10 + 0.02 * index,
        )
        ion["channels"].append(population)
        raw["experiment"]["channel_controls"].append(
            dict(
                channel_id=population["id"],
                schedule=deepcopy(raw["experiment"]["channel_controls"][index % 4]["schedule"]),
            )
        )
    raw["execution"]["channel_capacity"] = len(ion["channels"]) + int(padded)
    # The fast CaV2.1 activation transient needs a finer ordinary RK4 grid.
    # Keep physical tolerances and the complete 2-ms history unchanged.
    raw["execution"].update(dt=1.25e-6, max_steps=8192, max_trace_bytes=2**32)
    return raw


def assembly_definition(*, backend="cpu"):
    raw = base.assembly_definition(backend=backend)
    raw["ionic"] = definition(backend=backend)
    return raw
