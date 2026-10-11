"""Independent scalar process laws, scalar nonlinear roots and adaptive trajectories.

Reuse the independent spatial process reference with explicit outside owners and
the separately implemented tissue root. No Cells/JAX imports or production RHS.
"""

from validation.betse.spatial_cluster import reference as spatial
from validation.tissue import reference as electrical

bind, flatten, initial = spatial.bind, spatial.flatten, spatial.initial
unpack, control_at = spatial.unpack, spatial.control_at


def coupled_field(c, ci, co, vm, state, control):
    m, names = c["model"], c["ids"]
    outside = [o["id"] for o in c["outside"]]
    cells = [row["cell"]["id"] for row in c["cells"]]
    faces, junctions = m["faces"], m["junctions"]
    definition = {
        "ci": ci.tolist(),
        "co": co.tolist(),
        "membrane_voltage": vm.tolist(),
        "gate": state["junction_gate"].tolist(),
        "availability": [control[e["id"], "schedule"]["open_fraction"] for e in junctions],
        "layout": {
            "temperature": m["temperature_K"],
            "valence": [[int(z)] for z in c["z"]],
            "cell_active": [True] * len(cells),
            "cell_outside": c["outside_owners"].tolist(),
            "extracellular_active": [True] * len(outside),
            "gauge_mask": [o == m["closure"]["gauge_reference"] for o in outside],
            "face_active": [True] * len(faces),
            "face_senders": [outside.index(f["sender"]) for f in faces],
            "face_receivers": [outside.index(f["receiver"]) for f in faces],
            "face_factor": [
                [f["diffusivity_m2_per_s"][s] * f["area_m2"] / f["length_m"] for f in faces]
                for s in names
            ],
            "junction_active": [True] * len(junctions),
            "junction_senders": [cells.index(e["from_cell"]) for e in junctions],
            "junction_receivers": [cells.index(e["to_cell"]) for e in junctions],
            "junction_area": [e["area_m2"] for e in junctions],
            "junction_permeability": [
                [e["permeability_m_per_s"][s] for e in junctions] for s in names
            ],
        },
    }
    return electrical.solve(definition)


def rhs(c, control, state):
    return spatial.rhs(c, control, state, coupled_field=coupled_field)


def integrate(raw, *, rhs_cap=10000):
    return spatial.integrate(
        raw,
        {
            "method": "DOP853",
            "rtol": 2e-12,
            "atol": 1e-14,
            "max_step_s": 2.5e-5,
        },
        rhs_cap=rhs_cap,
        evaluate_rhs=rhs,
    )
