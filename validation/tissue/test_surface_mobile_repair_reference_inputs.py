"""Check species ownership when raw and serialized reference inputs differ in order."""

import numpy as np
import pytest

from cells.core.specs import parse_spec
from validation.tissue import surface_mobile_repair_fixtures as fixtures
from validation.tissue import surface_mobile_repair_reference as reference


@pytest.mark.parametrize("arm", ["mobile", "release"])
def test_raw_and_serialized_inputs_keep_all_reference_array_owners(arm):
    raw = fixtures.definition(arm)
    serialized = parse_spec(raw).to_dict()
    assert raw != serialized
    assert parse_spec(raw) == parse_spec(serialized)
    a, b = reference.bind(raw), reference.bind(serialized)
    assert list(a["shapes"].items()) == list(b["shapes"].items())
    assert len(a["shapes"]) == 47
    for original, parsed in zip(a["stores"], b["stores"], strict=True):
        assert original.ids == parsed.ids
        assert original.owners == parsed.owners
        assert original.reactions == parsed.reactions
        for field in ("n0", "volume", "mu0", "z"):
            np.testing.assert_array_equal(getattr(original, field), getattr(parsed, field))
    state = reference.initial(a)
    np.testing.assert_array_equal(state, reference.initial(b))
    # Exercise nonzero increments and controls on both sides of the release.
    for time in (0.0, 20e-6, 35e-6):
        slope, phi, proof = reference.evaluate(a, state, time)
        other_slope, other_phi, other_proof = reference.evaluate(b, state, time)
        np.testing.assert_array_equal(slope, other_slope)
        np.testing.assert_array_equal(phi, other_phi)
        assert proof == other_proof
        state = state + 1e-9 * slope
