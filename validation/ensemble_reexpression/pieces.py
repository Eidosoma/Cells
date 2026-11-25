"""Where the pieces of a definition stand: which outside nodes are cells' stores, which patches
bound them, what each passive route, transporter population, condition and reaction of a composite
belongs to, and where each is on its axis of the engine's record.

A definition of the inner model has none of these: every membrane of it is a plasma membrane and
every outside node a region. Every name and every place here is read from the definition, and
nothing is assumed of its IDs. A piece that a block (spec/PART2 §2) has no place for is listed in
`unplaced`, so that a reader refuses it by name and hides nothing.
"""

from validation.ensemble_reexpression.blocks import no_section
from validation.ensemble_reexpression.labels import LABELS

CALCIUM = "Ca"  # The species of a store's pump and release, which the blocks do not name.
FUEL = {"ATP": "atp_mM", "ADP": "adp_mM", "Pi": "pi_mM"}  # {a pump's role: the block's key}.
CYTOSOL, STORE = "cytosol", "er"  # The block's names of a cell's two compartments.


class Pieces:
    """The pieces of a definition in the engine's canonical JSON form, by where they stand."""

    def __init__(self, definition):
        model = definition["model"]
        self.model = model
        self.composite = model.get("id") == LABELS["composite_model"]
        self.unplaced = []
        self.species = [s["id"] for s in model["species"]]
        operators = {op["law"]: op for op in model.get("operators", ())}
        self._operators(operators)
        self.regions = [
            o["id"] for o in model["extracellular"] if o["id"] not in self.cell_of_store
        ]
        self.plasma = [m["id"] for m in model["membranes"] if m["id"] not in self.cell_of_patch]
        self._channels()
        self._routes()
        self._populations()
        self._conditions()
        self._reactions(operators.get(LABELS["local_reactions"], {}))
        self._rows(operators.get(LABELS["local_reactions"], {}))

    # ---- what is declared

    def _operators(self, operators):
        laws = (LABELS["compartment_law"], LABELS["local_reactions"])
        self.unplaced += [f"the operator {law}" for law in operators if law not in laws]
        self.store, self.patch, self.compartment = {}, {}, {}
        for c in operators.get(laws[0], {}).get("compartments", ()):
            if c["owner"] in self.store:
                self.unplaced.append(f"a second store of {c['owner']}, {c['id']}")
                continue
            self.store[c["owner"]], self.patch[c["owner"]] = c["node"], c["patch"]
            self.compartment[c["owner"]] = c
        self.cell_of_store = {node: cell for cell, node in self.store.items()}
        self.cell_of_patch = {patch: cell for cell, patch in self.patch.items()}

    def _channels(self):
        """Populations that carry calcium stand apart from the others."""
        ions = {
            c["id"]: [i["species_id"] for i in c["permeant_ions"]] for c in self.model["channels"]
        }
        self.calcium_channels = [c for c, carried in ions.items() if carried == [CALCIUM]]
        if not self.composite:  # The inner model's blocks have one list of channels.
            self.calcium_channels = []
        self.channels = [c for c in ions if c not in self.calcium_channels]

    def _routes(self):
        """The passive routes, by the host and the species they carry: a leak of a plasma membrane,
        a junction's, a store's leak, or a store's release, which is the one with a factor."""
        self.routes = sorted(self.model.get("passive_routes", ()), key=lambda r: r["id"])
        self.leak, self.junction_route, self.store_leak, self.release = {}, {}, {}, {}
        for route in self.routes:
            species, factors = route.get("species"), route.get("factors", [])
            cell = self.cell_of_patch.get(route.get("patch"))
            if "junction" in route:
                place, key = self.junction_route, (route["junction"], species)
            elif cell is None:
                place, key = self.leak, (route.get("patch"), species)
            elif factors:
                place, key = self.release, cell
            else:
                place, key = self.store_leak, (cell, species)
            fits = len(factors) == (1 if place is self.release else 0)
            fits = fits and route["law"] == LABELS["passive_constant_field"]
            if key in place or species != CALCIUM or not fits:
                self.unplaced.append(f"the passive route {route['id']}")
                continue
            place[key] = route

    def _populations(self):
        self.populations = list(self.model.get("transporters", ()))
        self.store_pump, self.plasma_pump, self.exchanger = {}, {}, {}
        for population in self.populations:
            host, law = population.get("host"), population["law"]
            cell = self.cell_of_patch.get(host)
            if law == LABELS["calcium_pump_positive"]:
                place, key = (self.plasma_pump, host) if cell is None else (self.store_pump, cell)
            elif law == LABELS["exchanger_3na_1ca"] and cell is None:
                place, key = self.exchanger, host
            else:
                place, key = None, host
            if place is None or key in place:
                self.unplaced.append(f"the transporter {population['id']}")
                continue
            place[key] = population

    def _conditions(self):
        self.conditions = {c["id"]: c for c in self.model.get("species_conditions", ())}
        self.release_condition = {}
        for cell, route in self.release.items():
            condition = self.conditions.get(route["factors"][0])
            if condition is not None and condition["node"] == cell:
                self.release_condition[cell] = condition
        used = [c["id"] for c in self.release_condition.values()]
        for name in self.conditions:
            if used.count(name) != 1:
                self.unplaced.append(f"the species condition {name}")
        for cell in self.release:
            if cell not in self.release_condition:
                self.unplaced.append(
                    f"the release of {cell}, whose factor is no condition of its cell"
                )

    def _reactions(self, operator):
        """The reactions by ID, and the place of each at each of its sites on the routes' axis: one
        reaction after another, its cells first and then its outside nodes."""
        self.reactions, self.reaction_route = {}, {}
        place = 0
        for reaction in operator.get("reactions", ()):
            sites = dict(reaction["sites"])
            every = {
                "cells": [c["id"] for c in self.model["cells"]],
                "outside": [o["id"] for o in self.model["extracellular"] if not o["reservoir"]],
            }
            at = {k: every[k] if sites.get(k) == "all" else list(sites.get(k, ())) for k in every}
            nodes = [*at["cells"], *at["outside"]]
            where = {n: place + k for k, n in enumerate(nodes)}
            place += len(nodes)
            if at["cells"] and not at["outside"]:
                owners, kind = {n: n for n in nodes}, CYTOSOL
            elif at["outside"] and not at["cells"]:
                owners, kind = {n: self.cell_of_store.get(n) for n in nodes}, STORE
            else:
                owners, kind = {}, None
            if kind is None or None in owners.values():
                self.unplaced.append(f"the reaction {reaction['id']}")
                continue
            self.reactions[reaction["id"]] = (kind, reaction)
            self.reaction_route[reaction["id"]] = {owners[n]: where[n] for n in nodes}

    def _rows(self, operator):
        """Which species rows are fuel (held by a population), chemical (every other) and ionic (a
        row that no reaction names, or that something carries between two cells or regions)."""
        self.fuel = {
            p["roles"][role]
            for p in self.populations
            for role, _ in (tuple(row) for row in p.get("held_rows", ()))
        }
        reacting = {s["id"] for s in operator.get("species", ())}
        self.reacting = [s for s in self.species if s in reacting]
        self.chemical = [s for s in self.species if s not in self.fuel]
        self.ionic = [s for s in self.chemical if s not in reacting or self._carried(s)]

    def _carried(self, species):
        model = self.model
        plasma = [m for m in model["membranes"] if m["id"] in self.plasma]
        pumps = [m["pump"] for m in plasma if m["pump"] is not None]
        return (
            any(m["permeability_m_per_s"].get(species, 0.0) for m in plasma)
            or any(j["permeability_m_per_s"].get(species, 0.0) for j in model["junctions"])
            or any(f["diffusivity_m2_per_s"].get(species, 0.0) for f in model["faces"])
            or any(name == species for _, name in (*self.leak, *self.junction_route))
            or any(species in p["roles"].values() for p in pumps)
            or any(
                species in p["roles"].values()
                for p in (*self.plasma_pump.values(), *self.exchanger.values())
            )
            or any(
                species in [i["species_id"] for i in c["permeant_ions"]] for c in model["channels"]
            )
        )

    # ---- what a reader asks

    def complete(self):
        """Refuse a definition with a piece that no block has a place for."""
        if self.unplaced:
            raise no_section(f"a block has no place for {'; '.join(self.unplaced)}")
        return self

    def route_index(self, route):
        return [r["id"] for r in self.routes].index(route["id"])

    def population_index(self, population):
        return [p["id"] for p in self.populations].index(population["id"])
