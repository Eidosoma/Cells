"""Closed-form oracle; deliberately outside simulator code and JAX."""

import math

import numpy as np


def exact_amount(spec, requested):
    values = []
    for target in requested:
        amount = spec.model.initial_amount
        k = spec.model.decay_rate
        for index, change in enumerate(spec.experiment.source):
            if change.time >= target:
                break
            end = min(
                target,
                spec.experiment.source[index + 1].time
                if index + 1 < len(spec.experiment.source)
                else target,
            )
            h = end - change.time
            if k == 0:
                amount += change.rate * h
            else:
                amount = amount * math.exp(-k * h) + change.rate * (-math.expm1(-k * h)) / k
        values.append(amount)
    return np.asarray(values)
