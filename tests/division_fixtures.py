"""Synthetic cells for the R-full tests (validation/division); none is the J1 egg."""

from dataclasses import replace

from validation.division import cleft_egg_reference as ref

T = 300.0
CYTOSOL = (12.0, 140.0, 30.0)
BATH = (140.0, 5.0, 145.0)


def synthetic(**changes):
    """A small cell with a cleft lumen; every value is synthetic."""
    egg = ref.Egg(
        temperature_K=T,
        cytosol_volume_m3=1e-12,
        cytosol_mM=CYTOSOL,
        bath_mM=BATH,
        old_area_m2=1e-8,
        old_capacitance_F=1e-10,
        old_relative=(0.05, 1.0, 0.0),
        p_old=1e-8,
        new_permeability=(2e-11, 4e-10, 0.0),
        new_specific_capacitance_F_m2=1e-2,
        onset_s=1.0,
        activation_area_m2=1e-9,
        schedule=((1.0, 0.0),),
        gap_width_m=1e-6,
        access_law="logmean",
        access_D=(1.33e-9, 1.96e-9, 2.03e-9),
        a_over_l_m=1e-7,
        pulses=ref.Pulses(enabled=False),
    )
    return replace(egg, **changes)


def growing(**changes):
    """The synthetic cell with insertion under way and the pulse train on (fast pulses)."""
    pulses = ref.Pulses(amplitude_A=2e-10, duration_s=0.12, period_s=0.5, sample_s=0.1)
    base = dict(
        onset_s=0.5,
        activation_area_m2=1e-10,
        schedule=((0.5, 2e-10),),
        new_permeability=(1e-10, 1e-7, 0.0),
        pulses=pulses,
    )
    return synthetic(**(base | changes))
