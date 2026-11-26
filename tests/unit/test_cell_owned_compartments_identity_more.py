"""S5, the declaration is pure identity (FR-1; design §3.3): two more traced pairs.

The criterion and the comparison are test_cell_owned_compartments_identity.py's: identical jaxpr
text and closed-over constants of the checked step, right-hand side and device row checks, and
identical bindings, with and without cells.operator.cell_owned_compartments@1. The pairs here: the silence world W
under RK4 at 0.1 ms, and W with turnover's clearance at the node beside exchange (the declaration
beside two operators). Tracing only, with no XLA compile.
"""

import jax
import pytest

from validation.tissue import compartment_fixtures as cfx

jax.config.update("jax_enable_x64", True)

END = 0.004

PAIRS = {
    "W under RK4": lambda declared: cfx.loaded_compartment(
        dt=1e-4, end=4e-4, solver="rk4", declared=declared
    ),
    "W with clearance at the node": lambda declared: cfx.loaded_compartment(
        end=END, turnover=True, declared=declared
    ),
}


@pytest.mark.parametrize("name", sorted(PAIRS))
def test_the_declaration_traces_to_identical_programs_and_bindings(name):
    assert cfx.identity_differences(PAIRS[name]) == []
