"""Exact raw-input variants; no YAML parsing, parameter owner or native work.

The headless variant changes only the two while-solving animation switches.
The separately declared headless_core case also disables cutting and the custom
general network. All other bytes, including numerical inputs and calendars,
remain original. This module never changes an existing configuration.
"""

import hashlib

ORIGINAL = "original"
HEADLESS = "headless"
HEADLESS_CORE = "headless_core"
PROFILES = (ORIGINAL, HEADLESS, HEADLESS_CORE)
MAIN = "sim_config.yaml"
ORIGINAL_SHA256 = "7ed5a32f9fc256c541db63090aeed6d0207bf706d2847b27269d6bc8c9e85415"
HEADLESS_SHA256 = "6e3279e94197a7a1701f36e8fd830c097959f1b8b4d39ef7b4cd1616cec957b3"
HEADLESS_CORE_SHA256 = "c801296a6382de057cde97f383250a7256c9b0be6310ee943e417e289445d193"
ORIGINAL_BYTES, HEADLESS_BYTES = 63375, 63377
HEADLESS_CORE_BYTES = 63379
_BEFORE = (
    b"  while solving:          # Results exported during simulation computation.\n"
    b"    animations:           # Animations exported during simulation computation.\n"
    b"      show: True          # Display animations during simulation computation?\n"
    b"      save: True          # Save animations with the animation saving options\n"
)
_AFTER = _BEFORE.replace(b"show: True ", b"show: False ").replace(b"save: True ", b"save: False ")
_CUT_BEFORE = (
    b"cutting event:\n    event happens: True      # enable (True) or disable (False) this event?\n"
)
_NETWORK_BEFORE = (
    b"general network:\n\n"
    b"  implement network: True  # Turn the entire network defined below on (True) or off (False)\n"
)


def require_profile(value):
    if type(value) is not str or value not in PROFILES:
        raise ValueError("Exactly original, headless or headless_core input profile required")
    return value


def changes(profile=HEADLESS):
    require_profile(profile)
    if profile == ORIGINAL:
        return []
    result = [
        dict(
            path=["results options", "while solving", "animations", name],
            before=True,
            after=False,
        )
        for name in ("show", "save")
    ]
    if profile == HEADLESS_CORE:
        result.extend(
            dict(path=path, before=True, after=False)
            for path in (
                ["cutting event", "event happens"],
                ["general network", "implement network"],
            )
        )
    return result


def main_file(profile):
    """Exact selected raw main-file declaration, independent of any live owner."""
    require_profile(profile)
    pin, size = {
        ORIGINAL: (ORIGINAL_SHA256, ORIGINAL_BYTES),
        HEADLESS: (HEADLESS_SHA256, HEADLESS_BYTES),
        HEADLESS_CORE: (HEADLESS_CORE_SHA256, HEADLESS_CORE_BYTES),
    }[profile]
    return dict(sha256=pin, size_bytes=size)


def transform(original, profile=HEADLESS):
    """Render only the selected declared byte transformation from the original."""
    require_profile(profile)
    if (
        type(original) is not bytes
        or len(original) != ORIGINAL_BYTES
        or hashlib.sha256(original).hexdigest() != ORIGINAL_SHA256
        or original.count(_BEFORE) != 1
    ):
        raise ValueError("Exact original BETSE animation input bytes required")
    value = original if profile == ORIGINAL else original.replace(_BEFORE, _AFTER, 1)
    if profile == HEADLESS_CORE:
        for before in (_CUT_BEFORE, _NETWORK_BEFORE):
            if value.count(before) != 1:
                raise ValueError("Exact original optional-feature declarations required")
            value = value.replace(before, before.replace(b": True ", b": False "), 1)
    if dict(size_bytes=len(value), sha256=hashlib.sha256(value).hexdigest()) != main_file(profile):
        raise ValueError("Exact declared input-profile transformation required")
    return value


def inventory(source, profile):
    """Return an independent declared inventory without reading native objects."""
    require_profile(profile)
    result = dict(source, files={name: dict(row) for name, row in source["files"].items()})
    if profile != ORIGINAL:
        row = result["files"].get(MAIN)
        if row != dict(sha256=ORIGINAL_SHA256, size_bytes=ORIGINAL_BYTES):
            raise ValueError("Input profile requires the complete original main YAML")
        result["files"][MAIN] = main_file(profile)
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
    declared_changes = bundle.get("configuration_changes")
    if (
        bundle.get("input_inventory") != expected
        or type(declared_changes) is not list
        or declared_changes != changes(profile)
        or any(
            type(row) is not dict or row.get("before") is not True or row.get("after") is not False
            for row in declared_changes
        )
        or bundle.get("raw_configuration_and_images_unchanged") is not False
    ):
        raise ValueError("Exact declared input-profile inventory required")
    return expected
