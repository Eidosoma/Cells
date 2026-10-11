"""Independent scalar IP3 factor on owned chemical state; no Cells/JAX imports."""

from tests import reference_gated_calcium as base
from tests.reference_er_calcium import System as ERSystem
from tests.reference_er_calcium import native_functions  # noqa: F401

F, R = base.F, base.R


class IP3Store(ERSystem):
    def __init__(self, raw, binding):
        super().__init__(raw)
        self.ip3 = self.ids.index(binding["species_id"])
        self.half = binding["activation_mM"]
        self.power = binding["activation_n"]

    def rhs(self, y, controls):
        c = (self.n0 + self.unpack(y)[0])[self.ip3, self.cy] / self.volume[self.cy]
        a = (c / self.half) ** self.power
        return super().rhs(y, controls | {"release": controls["release"] * a / (1 + a)})


class System(base.System):
    def __init__(self, raw):
        super().__init__(raw)
        stores = {s["cell_id"]: s["model"] for s in raw["model"]["stores"]}
        bindings = {r["cell_id"]: r for r in raw["model"]["ip3_release"]}
        self.stores = [IP3Store({"model": stores[c]}, bindings[c]) for c in self.cells]


def reference(raw, requested, **kwargs):
    return base.base.base.reference(raw, requested, system_class=System, **kwargs)


physical_energy_derivative = base.physical_energy_derivative
