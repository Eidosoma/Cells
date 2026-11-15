// The colour of a magnitude: one hue, light to dark on a light page and dark to light on a
// dark one, so that "more" always stands out from the page. The stops are the page's
// --seq-* tokens (validated: one hue, monotone lightness, both ends clear of the page).

const channel = (hex, at) => parseInt(hex.slice(at, at + 2), 16) / 255;

/** "#rrggbb" to [r, g, b] in 0..1 (sRGB, as written). */
export function parse(hex) {
  const text = /^#[0-9a-f]{6}$/i.test(hex) ? hex : "#888888";
  return [channel(text, 1), channel(text, 3), channel(text, 5)];
}

export class Ramp {
  /** stops: hex colours from the low end to the high end. */
  constructor(stops) {
    this.hex = stops;
    this.stops = stops.map(parse);
  }

  /** The colour at t in 0..1, as [r, g, b] in sRGB. Written into `out` when given. */
  at(t, out = [0, 0, 0]) {
    const last = this.stops.length - 1;
    const x = Math.min(1, Math.max(0, Number.isFinite(t) ? t : 0)) * last;
    const index = Math.min(last - 1, Math.floor(x));
    const mix = x - index;
    const a = this.stops[index], b = this.stops[index + 1];
    out[0] = a[0] + (b[0] - a[0]) * mix;
    out[1] = a[1] + (b[1] - a[1]) * mix;
    out[2] = a[2] + (b[2] - a[2]) * mix;
    return out;
  }

  /** The same ramp as a CSS gradient, for the legend. */
  css(direction = "to right") {
    return `linear-gradient(${direction}, ${this.hex.join(", ")})`;
  }
}

/** Relative luminance of an sRGB colour, for checking that a ramp reads in one direction. */
export function luminance([r, g, b]) {
  const linear = (value) => (value <= 0.04045 ? value / 12.92 : Math.pow((value + 0.055) / 1.055, 2.4));
  return 0.2126 * linear(r) + 0.7152 * linear(g) + 0.0722 * linear(b);
}
