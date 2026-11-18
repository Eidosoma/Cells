"""fr10-dose-schedule-v1's registered reference inputs stay the protocol's worlds (tier 1).

The code-blind references (R-faces, R-ion, R-records) are written from Appendix A and
validation/bath_schedule/reference_inputs.json alone, so that file must be what the protocol's
world builders declare: the registered copy equals what validation.tissue.
bath_schedule_reference_inputs writes from today's builders, and a planted change of a builder's
parameter (face_1's area) makes them differ.
"""

import json

from validation.tissue import bath_schedule_fixtures as bfx
from validation.tissue import bath_schedule_reference_inputs as ri


def test_the_registered_inputs_are_the_builders_worlds(monkeypatch):
    registered = json.loads(ri.REGISTERED.read_text())
    assert json.loads(json.dumps(ri.inputs())) == registered
    monkeypatch.setattr(bfx, "FACE_5", (6e-10, 1e-5))
    assert json.loads(json.dumps(ri.inputs())) != registered
