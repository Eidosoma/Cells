"""Native selected x/y/r store assignments in relative source order.

This normalized spatial projection omits unrelated temporal/bitmap/parser work.
Native float lookups, get defaults and failed partial stores remain literal.
"""


def populate(self):
    self.gradient_x_properties = {}
    self.gradient_y_properties = {}
    self.gradient_r_properties = {}
    self.gradient_x_properties["slope"] = float(
        self._conf["modulator function properties"]["gradient_x"]["slope"]
    )
    self.gradient_x_properties["x-offset"] = float(
        self._conf["modulator function properties"]["gradient_x"].get("x-offset", 0.0)
    )
    self.gradient_x_properties["z-offset"] = float(
        self._conf["modulator function properties"]["gradient_x"].get("z-offset", 0.0)
    )
    self.gradient_x_properties["exponent"] = float(
        self._conf["modulator function properties"]["gradient_x"].get("exponent", 1)
    )
    self.gradient_y_properties["slope"] = float(
        self._conf["modulator function properties"]["gradient_y"]["slope"]
    )
    self.gradient_y_properties["x-offset"] = float(
        self._conf["modulator function properties"]["gradient_y"].get("x-offset", 0.0)
    )
    self.gradient_y_properties["z-offset"] = float(
        self._conf["modulator function properties"]["gradient_y"].get("z-offset", 0.0)
    )
    self.gradient_y_properties["exponent"] = float(
        self._conf["modulator function properties"]["gradient_y"].get("exponent", 1)
    )
    self.gradient_r_properties["slope"] = float(
        self._conf["modulator function properties"]["gradient_r"]["slope"]
    )
    self.gradient_r_properties["x-offset"] = float(
        self._conf["modulator function properties"]["gradient_r"].get("x-offset", 0.0)
    )
    self.gradient_r_properties["z-offset"] = float(
        self._conf["modulator function properties"]["gradient_r"].get("z-offset", 0.0)
    )
    self.gradient_r_properties["exponent"] = float(
        self._conf["modulator function properties"]["gradient_r"].get("exponent", 1)
    )
