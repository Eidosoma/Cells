// How far apart two colours are for normal sight and for the three kinds of colour-vision deficiency, and how
// they stand against the page: the palette check of docs/ATLAS_LOOK.md (16 November 2026), used by
// tests/palette.test.mjs on the page's tokens and by tools/check_shelves.mjs "colours" on the colours as drawn.
//
// The deficiencies are simulated at full severity with the matrices of Machado, Oliveira and Fernandes (2009),
// applied to linear RGB; distance is CIE Lab (1976); contrast is WCAG 2's. Standard library only.

export const KINDS = ["normal", "protan", "deutan", "tritan"];
const MATRICES = {
  normal: [[1, 0, 0], [0, 1, 0], [0, 0, 1]],
  protan: [[0.152286, 1.052583, -0.204868], [0.114503, 0.786281, 0.099216], [-0.003882, -0.048116, 1.051998]],
  deutan: [[0.367322, 0.860646, -0.227968], [0.280085, 0.672501, 0.047413], [-0.01182, 0.04294, 0.968881]],
  tritan: [[1.255528, -0.076749, -0.178779], [-0.078411, 0.930809, 0.147602], [0.004733, 0.691367, 0.3039]],
};

/** "#rrggbb" (or "rgb(r, g, b)") as linear RGB, each 0 to 1. */
export function linear(colour) {
  const text = String(colour).trim();
  let parts;
  const hex = /^#([0-9a-f]{6})$/i.exec(text);
  if (hex) parts = [0, 2, 4].map((at) => parseInt(hex[1].slice(at, at + 2), 16));
  else {
    const rgb = /^rgba?\(\s*([\d.]+)[\s,]+([\d.]+)[\s,]+([\d.]+)/i.exec(text);
    if (!rgb) throw new Error(`not a colour: ${colour}`);
    parts = rgb.slice(1, 4).map(Number);
  }
  return parts.map((value) => {
    const c = value / 255;
    return c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
  });
}

function lab([r, g, b]) {
  const clamp = (value) => Math.min(1, Math.max(0, value));
  [r, g, b] = [clamp(r), clamp(g), clamp(b)];
  const x = (0.4124564 * r + 0.3575761 * g + 0.1804375 * b) / 0.95047;
  const y = 0.2126729 * r + 0.7151522 * g + 0.072175 * b;
  const z = (0.0193339 * r + 0.119192 * g + 0.9503041 * b) / 1.08883;
  const f = (t) => (t > 216 / 24389 ? Math.cbrt(t) : (24389 / 27 * t + 16) / 116);
  const [fx, fy, fz] = [f(x), f(y), f(z)];
  return [116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz)];
}

/** The colour as seen with one kind of sight, in CIE Lab. */
export function seen(colour, kind = "normal") {
  const rgb = linear(colour), m = MATRICES[kind];
  return lab(m.map((row) => row[0] * rgb[0] + row[1] * rgb[1] + row[2] * rgb[2]));
}

/** CIE76 distance between two colours as seen with one kind of sight. */
export function distance(a, b, kind = "normal") {
  const p = seen(a, kind), q = seen(b, kind);
  return Math.hypot(p[0] - q[0], p[1] - q[1], p[2] - q[2]);
}

/** The least distance under any of the three deficiencies. */
export function leastDeficient(a, b) {
  return Math.min(...KINDS.slice(1).map((kind) => distance(a, b, kind)));
}

/** WCAG 2 contrast ratio. */
export function contrast(a, b) {
  const luminance = (colour) => {
    const [r, g, b] = linear(colour);
    return 0.2126 * r + 0.7152 * g + 0.0722 * b;
  };
  const [high, low] = [luminance(a), luminance(b)].sort((x, y) => y - x);
  return (high + 0.05) / (low + 0.05);
}

/** The hue angle in CIE LCh, in degrees, and the chroma. */
export function hue(colour) {
  const [, a, b] = seen(colour);
  return { angle: ((Math.atan2(b, a) * 180) / Math.PI + 360) % 360, chroma: Math.hypot(a, b) };
}

/** What the page shows of a colour at `alpha` over `under`, mixed in linear light. */
export function over(colour, under, alpha) {
  const p = linear(colour), q = linear(under);
  const encode = (c) => Math.round(255 * (c <= 0.0031308 ? 12.92 * c : 1.055 * c ** (1 / 2.4) - 0.055));
  return `#${p.map((value, index) => encode(value * alpha + q[index] * (1 - alpha)).toString(16).padStart(2, "0")).join("")}`;
}

/**
 * The thresholds of the palette check (declared before any palette was chosen, docs/ATLAS_LOOK.md): the sides
 * from one another, each from the grey of "not known", from what it stands on, from the law hue and from every
 * status colour; contrast to the page; neighbouring steps of a ramp.
 */
export const THRESHOLDS = { pairNormal: 30, pairDeficient: 20, unknownNormal: 20, unknownDeficient: 12, surfaceNormal: 20, surfaceDeficient: 12, law: 20, status: 22, contrast: 3, step: 12 };
