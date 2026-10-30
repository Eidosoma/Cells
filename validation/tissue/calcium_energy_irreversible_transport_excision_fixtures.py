"""Explicit None-energy routes on the existing neutral-removal owner panel.

The supplied 50-kJ/mol work is a manufactured external source. Native rates,
concentration owners and finite fuel are unchanged. A neutral KCl route on the
removed owner creates nonzero history without altering its net plasma charge.
These are removal/restart probes, not a fitted physiological trajectory.
"""

from validation.tissue import calcium_energy_transport_excision_fixtures as prior

MODEL_ID = "resolved_calcium_energy_irreversible_transport@1"
DT = prior.DT
ARMS = (
    "open",
    "reordered",
    "zero_routes",
    "network_blocked",
    "removed_neutral_history",
    "sequential",
)


def definition(arm="removed_neutral_history", *, backend="cpu", padded=True):
    if arm not in ARMS:
        raise ValueError(arm)
    raw = prior.definition(arm, backend=backend, padded=padded)
    raw["model"]["id"] = MODEL_ID
    block = raw["model"]["network_transport"]
    block["accounting"] = "irreversible_species_transport_explicit_physical_work@1"
    for index, route in enumerate(block["routes"]):
        route["configuration"]["standard free energy"] = None if index % 2 == 0 else "None"
        route["drive"]["supplied_energy_J_per_mol"] = 50000.0
    raw["execution"]["jit"] = False
    return raw
