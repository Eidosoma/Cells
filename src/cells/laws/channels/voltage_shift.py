"""FR-64: the closed set of voltage shifts a channel population's readers may declare.

docs/FR64_VOLTAGE_SHIFT_DESIGN.md §3 to §5, read again at main 7149f90a in its §17. A channel
population's gates and its open-channel block each read a voltage. Each of these readers is one gate
of the population's law, or its block. The population may declare, per reader, that the voltage it
reads is

    V_ref = V - dV,

where V = phi_in - phi_out is its patch voltage, and dV is a declared function of a local ionic
condition. dV never reads V, so dV_ref/dV = 1. Permeation, its heat and its charge still read V
(D361).

**The closed set (KINDS; D356, D361).** Each shift is a one-key mapping that names its kind:
- **`{"reversal_of": ion}` (ReversalShift).** dV is E = (R T/(z F)) ln(c_o/c_i) of the population's
  own moved ion, at its cell and its patch's outside node. This is FR-51's reversal reference,
  moved here with no alias; its arithmetic is electrochemistry.reversal_potential, unchanged.
- **`{"ph": {"side", "shift_V_per_ph", "reference_ph", "ph_window"[, "proton"]}}` (PhShift).**
  dV = sigma (pH - pH_ref), with pH = -log10(h / 1 M), the closure's convention
  (rapid_proton_buffer.PH_REFERENCE_mM).
  - h is the free proton concentration of the stage's read at the declared side: the population's
    cell (`inside`) or its patch's outside node (`outside`).
  - sigma = d(dV)/dpH, in V per pH unit; it is negative for Kv1.5's acid shift (D361).
  - pH_ref is the pH at which the law's own curves hold.
  - The window [low, high] is required and closed. The pH is admitted on
    [low - PH_MARGIN, high + PH_MARGIN]; the margin is for rounding only. Beyond it a step is
    refused, never clipped.
  - The linear form is the secant through one preparation's two conditions. Nothing is claimed
    between or beyond them (the note's §10).

A combined or new kind is a new request. The membrane voltage is the default, spelled by omission.

**Each kind is one frozen type,** holding its parse, its dictionary form, the species rows it
reads, its layout values, and two kernels:
- dV;
- dV's slope in the concentration it reads, which the per-stage rules bound (the note's §4.2). For
  the reversal this is FR-51's part through E.

The kernels are pure, in the xp style of the layout's arrays.

**This module is no law home.** It has no registry record and no ID (D361; ID_HIERARCHY §7). A
shift is a declaration on the population, part of @3's channel-population schema
(definitions/surface_pump_v3_spec.parse_voltage_shift).
"""

import math
from dataclasses import dataclass
from types import MappingProxyType
from typing import ClassVar

import numpy as np

from cells.laws import electrochemistry
from cells.laws.electrochemistry import F, R
from cells.laws.reactions.rapid_proton_buffer import PH_REFERENCE_mM
from cells.modules import ConfigError, require_fields

SIDES = ("inside", "outside")  # The population's cell, or its patch's outside node.
DEFAULT_PROTON = "H"
PH_MARGIN = 1e-9  # The window's rounding margin, in pH units (the note's §3.5, option (c)).
# FR-51's admitted domain keeps |V_ref| <= 0.49 V: the laws' -120 to +60 mV, less a reversal
# potential of at most 0.369 V (validation/fr51/REGISTRATION.md, "Why the domain's limits"). A
# block's pH shift is bounded by the same 0.369 V over its window widened by PH_MARGIN, so that
# normal-number argument holds unchanged (the note's §4.3).
BLOCK_SHIFT_LIMIT_V = 0.369
LN10 = math.log(10.0)


def _real(value, name):
    """A finite real number (an int or a float, never a bool), its sign kept."""
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ConfigError(f"{name} must be a finite number")
    return float(value)


@dataclass(frozen=True)
class ReversalShift:
    """`{"reversal_of": ion}`: the reader reads V - E of the population's own moved ion."""

    ion: str

    KEY: ClassVar[str] = "reversal_of"

    @classmethod
    def parse(cls, value, where):
        if not isinstance(value, str) or not value:
            raise ConfigError(f"{where}: reversal_of names one of the population's permeant ions")
        return cls(value)

    def to_dict(self):
        return {self.KEY: self.ion}

    def rows(self):
        """The species rows the shift reads."""
        return (self.ion,)

    def layout_values(self, species_ids):
        """This reader's entries in the shift's layout fields (the host prefixes their names)."""
        return dict(reversal=True, row=species_ids.index(self.ion))

    @staticmethod
    def delta_v(inside_mM, outside_mM, valence, temperature, *, xp=np):
        """dV = E (V) of the ion, from its concentrations at the cell (inside) and at the outside
        node, through electrochemistry.reversal_potential (called through its module, so a plant
        of it is seen)."""
        return electrochemistry.reversal_potential(
            inside_mM, outside_mM, valence, temperature, xp=xp
        )

    @staticmethod
    def slope(concentration_mM, valence, temperature, *, xp=np):
        """|d(dV)/dc| (V/mM) at one end, at that end's concentration: R T/(|z| F c)."""
        return R * temperature / (xp.abs(valence) * F * concentration_mM)


@dataclass(frozen=True)
class PhShift:
    """`{"ph": {...}}`: the reader reads V - sigma (pH - pH_ref), with the pH taken at its side."""

    side: str
    shift_V_per_ph: float
    reference_ph: float
    ph_window: tuple[float, float]
    proton: str = DEFAULT_PROTON

    KEY: ClassVar[str] = "ph"
    FIELDS: ClassVar[tuple[str, ...]] = ("side", "shift_V_per_ph", "reference_ph", "ph_window")

    @classmethod
    def parse(cls, value, where):
        name = f"{where}'s ph"
        if not isinstance(value, dict):
            raise ConfigError(f"{name} must be an object")
        require_fields(value, set(cls.FIELDS) | ({"proton"} & set(value)), name)
        side = value["side"]
        if side not in SIDES:
            raise ConfigError(
                f"{name}: side is inside (the population's cell) or outside (its patch's outside "
                "node); neither is a default"
            )
        sigma = _real(value["shift_V_per_ph"], f"{name}'s shift_V_per_ph")
        reference = _real(value["reference_ph"], f"{name}'s reference_ph")
        window = value["ph_window"]
        if type(window) is not list or len(window) != 2:
            raise ConfigError(f"{name}: ph_window is [low, high]")
        low, high = (_real(v, f"{name}'s ph_window") for v in window)
        if not low < high:
            raise ConfigError(f"{name}: the window's low pH lies below its high pH")
        if not low <= reference <= high:
            raise ConfigError(f"{name}: the reference pH lies inside its window, an edge at most")
        proton = value.get("proton", DEFAULT_PROTON)
        if not isinstance(proton, str) or not proton:
            raise ConfigError(f"{name}: proton names the proton row")
        return cls(side, sigma, reference, (low, high), proton)

    def to_dict(self):
        out = dict(
            side=self.side,
            shift_V_per_ph=self.shift_V_per_ph,
            reference_ph=self.reference_ph,
            ph_window=list(self.ph_window),
        )
        if self.proton != DEFAULT_PROTON:
            out["proton"] = self.proton
        return {self.KEY: out}

    def rows(self):
        """The species rows the shift reads."""
        return (self.proton,)

    def largest_shift_V(self):
        """|sigma| max |pH - pH_ref| (V) over the window widened by PH_MARGIN."""
        low, high = self.ph_window
        reach = max(self.reference_ph - (low - PH_MARGIN), (high + PH_MARGIN) - self.reference_ph)
        return abs(self.shift_V_per_ph) * reach

    def layout_values(self, species_ids):
        """This reader's entries in the shift's layout fields (the host prefixes their names)."""
        low, high = self.ph_window
        return dict(
            ph=True,
            row=species_ids.index(self.proton),
            outside=self.side == "outside",
            V_per_ph=self.shift_V_per_ph,
            reference_ph=self.reference_ph,
            ph_low=low,
            ph_high=high,
        )

    @staticmethod
    def ph(h_mM, *, xp=np):
        """pH = -log10(h / 1 M) of a free proton concentration h (mM)."""
        return -xp.log10(h_mM / PH_REFERENCE_mM)

    @staticmethod
    def delta_v(h_mM, shift_V_per_ph, reference_ph, *, xp=np):
        """dV = sigma (pH - pH_ref) (V) at the free proton concentration h (mM)."""
        return shift_V_per_ph * (PhShift.ph(h_mM, xp=xp) - reference_ph)

    @staticmethod
    def slope(h_mM, shift_V_per_ph, *, xp=np):
        """|d(dV)/dh| (V/mM) at h: |sigma|/(h ln 10)."""
        return xp.abs(shift_V_per_ph) / (h_mM * LN10)

    @staticmethod
    def valid(h_mM, ph_low, ph_high, *, xp=np):
        """True where h is finite and positive and its pH lies on [low - PH_MARGIN,
        high + PH_MARGIN]."""
        usable = xp.isfinite(h_mM) & (h_mM > 0)
        ph = PhShift.ph(xp.where(usable, h_mM, PH_REFERENCE_mM), xp=xp)
        return usable & (ph >= ph_low - PH_MARGIN) & (ph <= ph_high + PH_MARGIN)


# The closed set: the parse, the model and the guard row all read this one table.
KINDS = MappingProxyType({ReversalShift.KEY: ReversalShift, PhShift.KEY: PhShift})


def parse_shift(raw, where):
    """One reader's shift: a one-key mapping that names its kind in the closed set (KINDS)."""
    if not isinstance(raw, dict) or len(raw) != 1:
        raise ConfigError(
            f"{where}: a shift is one {{kind: value}} mapping of the closed set "
            f"({', '.join(KINDS)}); a combined or new kind is a new request, and the membrane "
            "voltage is the default: omit the reader for it"
        )
    ((key, value),) = raw.items()
    kind = KINDS.get(key)
    if kind is None:
        raise ConfigError(
            f"{where}: {key!r} is no shift kind; the closed set is {', '.join(KINDS)}, and the "
            "membrane voltage is the default: omit the reader for it"
        )
    return kind.parse(value, where)
