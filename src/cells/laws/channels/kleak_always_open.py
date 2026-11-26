"""cells.channel.kleak_always_open@1: an always-open potassium leak, the law and its declaration on @3.

A gate-free population: open at all times, so its flux is the host's constant-field flux of
K⁺ at the population's permeability, abundance and availability. Channel code 3 of
cells.model.resolved_pump_tissue@3 (cells.channel_law@1), registered by the law registry's loader
(docs/CORE_SEAMS_DESIGN.md §8.2); it carries no gate state, kernel or RK4 step bound.
"""

from cells.laws.channels.kv1p5_mh import VOLTAGE_DOMAIN_V  # @3's channel domain, -120..60 mV.
from cells.modules import ChannelLaw

LAW_ID = "cells.channel.kleak_always_open@1"
LAW = ChannelLaw(
    LAW_ID,
    3,
    (),
    (("K", 1, 1.0),),
    VOLTAGE_DOMAIN_V,
    None,
    host="cells.model.resolved_pump_tissue@3",
)
