"""Inner kinds of resolved_pump_tissue@3, one module each (docs/INNER_MODEL_V4_DESIGN.md §7.4 (k)).

Each kind module declares a `cells.core.kind_registry.Kind` and registers it on the registry
(BUILTIN for built-ins), exactly as an external package would; the core imports no kind module.
None is registered yet: FR-4's stage read and transporter and the passive law join here.
"""
