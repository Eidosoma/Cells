"""Independent scalar calcium/IP3 laws with independent nonlinear tissue roots."""

from tests import reference_ip3_calcium as base
from tests.reference_spatial_calcium import reference as integrate
from validation.tissue.dynamics_reference import coupled_field

physical_energy_derivative = base.physical_energy_derivative


class System(base.System):
    coupled_field = staticmethod(coupled_field)


def reference(raw, requested, **kwargs):
    return integrate(raw, requested, system_class=System, **kwargs)
