"""Generate a WCAG-contrast-safe accent palette from one base color.

Spendly's global stylesheet already fixes its neutral colors (ink, paper,
borders); the only themeable slots are the accent pair (--accent /
--accent-light) and the secondary accent pair (--accent-2 / --accent-2-light).
This module derives both pairs from a single user-picked base color in HSL
space, nudging lightness where needed so text/background combinations that
reuse these variables stay readable.
"""

import colorsys
import re

HEX_RE = re.compile(r"^#[0-9a-fA-F]{6}$")

PAPER = "#f7f6f3"
MIN_CONTRAST = 4.5


def is_valid_hex(value):
    return bool(value) and bool(HEX_RE.match(value))


def hex_to_rgb(hex_color):
    hex_color = hex_color.lstrip("#")
    return tuple(int(hex_color[i:i + 2], 16) for i in (0, 2, 4))


def rgb_to_hex(r, g, b):
    return "#{:02x}{:02x}{:02x}".format(
        max(0, min(255, round(r))),
        max(0, min(255, round(g))),
        max(0, min(255, round(b))),
    )


def hex_to_hls(hex_color):
    r, g, b = hex_to_rgb(hex_color)
    return colorsys.rgb_to_hls(r / 255, g / 255, b / 255)


def hls_to_hex(h, l, s):
    h = h % 1.0
    l = max(0.0, min(1.0, l))
    s = max(0.0, min(1.0, s))
    r, g, b = colorsys.hls_to_rgb(h, l, s)
    return rgb_to_hex(r * 255, g * 255, b * 255)


def relative_luminance(hex_color):
    def channel(c):
        c = c / 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

    r, g, b = hex_to_rgb(hex_color)
    r, g, b = channel(r), channel(g), channel(b)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast_ratio(hex_a, hex_b):
    l1 = relative_luminance(hex_a) + 0.05
    l2 = relative_luminance(hex_b) + 0.05
    return max(l1, l2) / min(l1, l2)


def _accent_pair(hue, sat, lightness):
    """A tint (light background) plus a solid color readable as text on
    that tint and as a background under light (paper-colored) text."""
    tint_sat = max(min(sat, 0.55), 0.15)
    light = hls_to_hex(hue, 0.93, tint_sat)

    l = lightness
    solid = hls_to_hex(hue, l, sat)
    passed = False
    for _ in range(30):
        passed = (
            contrast_ratio(solid, light) >= MIN_CONTRAST
            and contrast_ratio(PAPER, solid) >= MIN_CONTRAST
        )
        if passed:
            break
        l = max(0.0, l - 0.03)
        solid = hls_to_hex(hue, l, sat)

    return solid, light, l, passed


def generate_palette(base_hex):
    base_hex = base_hex.lower()
    h, l, s = hex_to_hls(base_hex)
    warnings = []

    primary, primary_light, primary_l, ok = _accent_pair(h, s, l)
    if not ok:
        warnings.append("primary-contrast")
    primary_dark = hls_to_hex(h, max(primary_l - 0.15, 0.05), s)

    accent2_hue = (h + 0.5) % 1.0
    accent_2, accent_2_light, _accent2_l, ok = _accent_pair(accent2_hue, s, l)
    if not ok:
        warnings.append("accent-2-contrast")

    return {
        "primary": primary,
        "primary_light": primary_light,
        "primary_dark": primary_dark,
        "accent_2": accent_2,
        "accent_2_light": accent_2_light,
        "warnings": warnings,
    }
