"""Authentic frozen caller recipes; no opt-in flag rewrites or eager runs."""

from validation.betse import betse_initial_mesh_preparation_fixtures as original

B09_CASES = tuple(name for name in original.B09_CASES if name != "merged-square-aux")
CALLER_CASES = original.CALLER_CASES
MESH_CASES = (*B09_CASES, *CALLER_CASES)
RAW_CASES = original.RAW_CASES
REQUEST_CASES = (
    "wrong-law",
    "boolean-law",
    "native-request-type",
    "changed-opt-in",
    "changed-request-identity",
    "forged-native-identity",
)
OWNERSHIP_CASES = (
    "native-state-type",
    "changed-state-identity",
    "changed-cache",
    "changed-rng",
    "changed-occurrence-order",
    "changed-certificate-event",
)
COMPLEX_CONTROLS = (
    "two-triangle-square",
    "concave-tile",
    "disconnected-tiles",
    "interior-overlap",
    "duplicate-face",
    "reversed-face",
    "self-crossing",
    "boundary-t-junction",
)


def native_request(name, directory):
    if name in B09_CASES:
        return original.reused_B09(name)
    if name in (*CALLER_CASES, *RAW_CASES):
        return original.caller(name, directory)
    raise ValueError("Require a declared authentic initial-mesh case")


def complex_control(name):
    a, b, c, d = (0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)
    cases = {
        "two-triangle-square": ([[a, b, c], [a, c, d]], True),
        "concave-tile": ([[a, b, (0.5, 0.5), c, d]], True),
        "disconnected-tiles": ([[a, b, d], [(2.0, 0.0), (3.0, 0.0), (2.0, 1.0)]], True),
        "interior-overlap": ([[a, b, c, d], [(0.5, 0.5), (1.5, 0.5), (0.5, 1.5)]], False),
        "duplicate-face": ([[a, b, c], [a, b, c]], False),
        "reversed-face": ([[a, c, b]], False),
        "self-crossing": ([[a, c, b, d]], False),
        "boundary-t-junction": (
            [[a, b, c, d], [(1.0, 0.0), (2.0, 0.0), (2.0, 0.5), (1.0, 0.5)]],
            False,
        ),
    }
    polygons, passed = cases[name]
    return [[list(point) for point in polygon] for polygon in polygons], passed
