// The assembly view's own styles (src/lenses/lineage.js): its colour tokens, light and dark, read
// by the lens from the page, and its swatches for the list and the legend. The hook-up puts
// `originTokens` beside the page's own tokens (src/page.css) and `originCss` in the viewer's shadow
// styles; nothing else of the page changes.
//
// Three molecule types wear colour, each also with its own shape (a diamond, a cube, a
// tetrahedron) and its name: only three hues stay apart for colour-blind readers where any two can
// sit side by side, checked with a colour-vision simulation (Machado and others, 2009) against the
// page's surfaces in both themes. The other types are neutral greys, chosen to stay apart from each
// of the three. Counts and similarity use one violet ramp, faint to strong, so that no type's hue
// stands for a number.

export const originTokens = `
:root {
  --origin-type-1: #2a78d6; --origin-type-2: #eb6834; --origin-type-3: #1baf7a;
  --origin-type-other: #b0b5ba; --origin-type-other-2: #c3c8cd; --origin-tail: #8a99aa; --origin-glow: #1f6fd0;
  --origin-ramp-0: #ece9fb; --origin-ramp-1: #c8c0f3; --origin-ramp-2: #9d90e8; --origin-ramp-3: #6f5fd9; --origin-ramp-4: #4a3aa7; --origin-ramp-5: #2f237a;
}
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    --origin-type-1: #3987e5; --origin-type-2: #d95926; --origin-type-3: #199e70;
    --origin-type-other: #4f565e; --origin-type-other-2: #5d646b; --origin-tail: #6f8297; --origin-glow: #5b9dee;
    --origin-ramp-0: #1c1a3a; --origin-ramp-1: #2f2870; --origin-ramp-2: #4a3db0; --origin-ramp-3: #7566e0; --origin-ramp-4: #a69cf0; --origin-ramp-5: #d8d3fa;
  }
}
:root[data-theme="dark"] {
  --origin-type-1: #3987e5; --origin-type-2: #d95926; --origin-type-3: #199e70;
  --origin-type-other: #4f565e; --origin-type-other-2: #5d646b; --origin-tail: #6f8297; --origin-glow: #5b9dee;
  --origin-ramp-0: #1c1a3a; --origin-ramp-1: #2f2870; --origin-ramp-2: #4a3db0; --origin-ramp-3: #7566e0; --origin-ramp-4: #a69cf0; --origin-ramp-5: #d8d3fa;
}
`;

export const originCss = `
.swatch-origin-type-1 { background: var(--origin-type-1); transform: rotate(45deg) scale(0.82); }
.swatch-origin-type-2 { background: var(--origin-type-2); }
.swatch-origin-type-3 { background: var(--origin-type-3); clip-path: polygon(50% 4%, 100% 96%, 0 96%); border-radius: 0; }
.swatch-origin-type-other { background: var(--origin-type-other); border-radius: 50%; }
.swatch-origin-threshold { background: color-mix(in srgb, var(--accent) 30%, transparent); box-shadow: inset 0 0 0 1.5px var(--accent); height: 6px; margin-top: 3px; }
.swatch-origin-fission { background: var(--fg); border-radius: 50%; }
.swatch-origin-break { border: 2px solid var(--fg); border-radius: 50%; background: transparent; }
.swatch-origin-part { border: 1.5px solid var(--ghost); }
.swatch-origin-ramp { width: 46px; background: linear-gradient(90deg, var(--origin-ramp-0), var(--origin-ramp-1), var(--origin-ramp-2), var(--origin-ramp-3), var(--origin-ramp-4), var(--origin-ramp-5)); }
`;
