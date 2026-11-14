"""S5, the declaration is pure identity (FR-1; docs/CLOSED_COMPARTMENT_DESIGN.md §3.3), traced.

S5's criterion, fixed before any run: the same world with and without cell_owned_compartments@1
traces to identical program text and constants, with identical bindings. Compared, through
validation/tissue/composite_crossrev's own tracing (validation/tissue/compartment_fixtures.traced
and bindings):
- the jaxpr text of the checked step, the right-hand side and the device row checks, with scalar
  constants as literals;
- the dtype, shape and SHA-256 of every array each program closes over;
- every initial state, layout and control array at every schedule time, and the device-check
  constants.
The pairs: the silence world W (the exchange route in both) under ARS(2,2,2) and under RK4; W with
turnover's clearance at the node beside exchange; and, as the lead ruled with the composite's
empty-composition branch, the declaration alone against no operators at all, which runs the inner
step itself. Tracing only, with no XLA compile.
"""

import jax
import pytest

from validation.tissue import compartment_fixtures as cfx
from validation.tissue import secreted_species_fixtures as fx

jax.config.update("jax_enable_x64", True)

END = 0.004


def alone(declared):
    raw = fx.face_free(pool_mM=1e-3, node_mM=1e-6, end=END)
    return cfx.with_compartments(raw, [cfx.compartment()]) if declared else raw


PAIRS = {
    "W under ARS": lambda declared: cfx.loaded_compartment(end=END, declared=declared),
    "W under RK4": lambda declared: cfx.loaded_compartment(
        dt=1e-4, end=4e-4, solver="rk4", declared=declared
    ),
    "W with clearance at the node": lambda declared: cfx.loaded_compartment(
        end=END, turnover=True, declared=declared
    ),
    "the declaration alone": alone,
}


@pytest.mark.parametrize("name", sorted(PAIRS))
def test_the_declaration_traces_to_identical_programs_and_bindings(name):
    build = PAIRS[name]
    with_it, without = build(True), build(False)
    a, b = cfx.traced(with_it), cfx.traced(without)
    assert a.keys() == b.keys() == {"checked_step", "rhs", "device_checks"}
    for kind in a:
        assert a[kind][0] == b[kind][0], f"{kind}: jaxpr text"
        assert a[kind][1] == b[kind][1], f"{kind}: closed-over constants"
    assert cfx.same_bindings(cfx.bindings(with_it), cfx.bindings(without)) == []
