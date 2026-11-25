"""Inner kinds of resolved_pump_tissue@3, one module each (docs/INNER_MODEL_V4_DESIGN.md §7.4 (k)).

Each kind module declares a `cells.registry.kind_registry.Kind` and registers it on the registry
(BUILTIN for built-ins), exactly as an external package would; the core imports no kind module.
kind_registry.active() imports this package by name once, which registers the built-ins below. A
registered kind that a definition does not declare changes nothing.
- passive_routes: A5, the passive permeation law's insertion point with §7.5's exact booking;
- patch_damage: FR-5's damage of a membrane patch, a source of the routing door;
- ph_condition: FR-5's pH condition at a node, a source of the routing door;
- proton_buffer: B4, FR-4's rapid-buffer closure as the stage read;
- species_condition: G-5's Hill factors of declared species rows at a node, a source of the routing
  door;
- transporter: B5, the ATP-driven transporters (FR-4's proton pump among them).
"""

from cells.kinds import (  # noqa: F401
    passive_routes,
    patch_damage,
    ph_condition,
    proton_buffer,
    species_condition,
    transporter,
)
