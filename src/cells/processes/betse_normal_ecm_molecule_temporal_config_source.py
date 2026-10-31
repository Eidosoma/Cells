"""Selected BETSE1.5.0 temporal stores, not the full Parameters/YAML parser.

Dictionary creation and assignments below preserve native relative order.
Native gradient stores/lookups between them are deliberately outside this
normalized temporal projection. There are no temporal lookup defaults. The
None sweep slope is assigned last; its later resolution belongs to f_sweep.
"""


def populate(self):
    self.periodic_properties = {}
    self.f_scan_properties = {}
    self.periodic_properties["frequency"] = float(
        self._conf["modulator function properties"]["periodic"]["frequency"]
    )
    self.periodic_properties["phase"] = float(
        self._conf["modulator function properties"]["periodic"]["phase"]
    )
    self.f_scan_properties["f start"] = float(
        self._conf["modulator function properties"]["f_sweep"]["start frequency"]
    )
    self.f_scan_properties["f stop"] = float(
        self._conf["modulator function properties"]["f_sweep"]["end frequency"]
    )
    self.f_scan_properties["f slope"] = None
