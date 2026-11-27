"""FR-45's plants (validation/fr45/spec/TABLE.md §8): each a scoped patch of one engine seam, applied in its run's
own process before the world is built, never in src/ (CRITERIA:111-112).

Each module holds ID (P1 to P9), CHANGE (one line naming what it changes), declare(inputs) -> (inputs, the
`inputs` key paths it changes: empty except for P2, planted by declaration) and apply(), which patches the seam.
The INVENTED_* modules are development-only: invented patches that cause the format sample's two `~check`
refusals on invented worlds (the sample's README); no registered run takes them.
"""


def same(inputs):
    """A plant that changes no input."""
    return inputs, []
