"""FR-1's registered reference inputs stay the protocol's worlds (tier 1).

FR-1's code-blind references (docs/CLOSED_COMPARTMENT_DESIGN.md §6.2) are written from its Appendix
A and validation/closed_compartment/reference_inputs.json alone, so that file must be what the
protocol's world builders declare: the registered copy equals what validation.tissue.
compartment_acceptance_reference_inputs writes from today's builders, and a planted change of a
builder's parameter (the cytosol's pool) makes them differ.
"""

import json

from validation import id_table
from validation.tissue import compartment_acceptance_fixtures as af
from validation.tissue import compartment_acceptance_reference_inputs as ri


def test_the_registered_inputs_are_the_builders_worlds(monkeypatch):
    registered = id_table.load(ri.REGISTERED)
    assert json.loads(json.dumps(ri.inputs())) == registered
    monkeypatch.setattr(af, "POOL_mM", 2e-3)
    assert json.loads(json.dumps(ri.inputs())) != registered
