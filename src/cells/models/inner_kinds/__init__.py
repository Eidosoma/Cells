"""Inner kinds of resolved_pump_tissue@3, one module each (docs/INNER_MODEL_V4_DESIGN.md §7.4 (k)).

Each kind module declares a `cells.core.kind_registry.Kind` and registers it on the registry
(BUILTIN for built-ins), exactly as an external package would; the core imports no kind module.
kind_registry.active() imports this package by name once, which registers the built-ins below. A
registered kind that a definition does not declare changes nothing.
"""

from cells.models.inner_kinds import proton_buffer  # noqa: F401  (B4: FR-4's rapid-buffer closure)
