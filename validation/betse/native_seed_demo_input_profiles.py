"""Exact raw-input variants; no YAML parsing, parameter owner or native work.

The headless variant changes only the two while-solving animation switches.
After-solving export settings, enabled networks and all numerical inputs retain
their original bytes. This module never changes an existing configuration.
"""

import hashlib

ORIGINAL = "original"
HEADLESS = "headless"
PROFILES = (ORIGINAL, HEADLESS)
MAIN = "sim_config.yaml"
ORIGINAL_SHA256 = "7ed5a32f9fc256c541db63090aeed6d0207bf706d2847b27269d6bc8c9e85415"
HEADLESS_SHA256 = "6e3279e94197a7a1701f36e8fd830c097959f1b8b4d39ef7b4cd1616cec957b3"
ORIGINAL_BYTES, HEADLESS_BYTES = 63375, 63377
_BEFORE = (
    b"  while solving:          # Results exported during simulation computation.\n"
    b"    animations:           # Animations exported during simulation computation.\n"
    b"      show: True          # Display animations during simulation computation?\n"
    b"      save: True          # Save animations with the animation saving options\n"
)
_AFTER = _BEFORE.replace(b"show: True ", b"show: False ").replace(b"save: True ", b"save: False ")


def require_profile(value):
    if type(value) is not str or value not in PROFILES:
        raise ValueError("Exactly original or headless input profile required")
    return value


def changes():
    return [
        dict(
            path=["results options", "while solving", "animations", name],
            before=True,
            after=False,
        )
        for name in ("show", "save")
    ]


def transform(original):
    """Render the sole declared byte transformation from the exact original."""
    if (
        type(original) is not bytes
        or len(original) != ORIGINAL_BYTES
        or hashlib.sha256(original).hexdigest() != ORIGINAL_SHA256
        or original.count(_BEFORE) != 1
    ):
        raise ValueError("Exact original BETSE animation input bytes required")
    value = original.replace(_BEFORE, _AFTER, 1)
    if len(value) != HEADLESS_BYTES or hashlib.sha256(value).hexdigest() != HEADLESS_SHA256:
        raise ValueError("Exact two-switch headless transformation required")
    return value


def inventory(source, profile):
    """Return an independent declared inventory without reading native objects."""
    require_profile(profile)
    result = dict(source, files={name: dict(row) for name, row in source["files"].items()})
    if profile == HEADLESS:
        row = result["files"].get(MAIN)
        if row != dict(sha256=ORIGINAL_SHA256, size_bytes=ORIGINAL_BYTES):
            raise ValueError("Headless profile requires the complete original main YAML")
        result["files"][MAIN] = dict(sha256=HEADLESS_SHA256, size_bytes=HEADLESS_BYTES)
    return result


def selected_inventory(bundle):
    """Validate the declared difference even when output-directory epochs are used."""
    profile = require_profile(bundle.get("configuration_profile", ORIGINAL))
    source = bundle["source_inventory"]
    if profile == ORIGINAL:
        if "input_inventory" in bundle or "configuration_changes" in bundle:
            raise ValueError("An original input bundle cannot hide an input variant")
        return source
    expected = inventory(source, profile)
    if (
        bundle.get("input_inventory") != expected
        or bundle.get("configuration_changes") != changes()
        or bundle.get("raw_configuration_and_images_unchanged") is not False
    ):
        raise ValueError("Exact declared two-switch headless input inventory required")
    return expected
