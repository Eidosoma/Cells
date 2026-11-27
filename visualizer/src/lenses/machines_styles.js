// The Machines view's legend swatches: the page's legend draws a swatch as
// <span class="swatch swatch-{id}"> (ui/dom.js statusSwatch), so each of the view's marks
// (machines.js MARKS) and each group's colour has a rule here, drawn as it is drawn on the bench.
// None is dashed, outlined in a status colour or coloured by a status: those are the page's statuses.

const GROUPS = { proteins: "--bio-ribosome", genes: "--bio-nucleus", dna: "--bio-golgi", light: "--bio-chloroplast", atp: "--bio-fuel", ions: "--bio-ion", membranes: "--bio-er", folding: "--bio-protein", breaking: "--bio-signal", moving: "--bio-mito", binding: "--bio-membrane", redox: "--bio-water", cleavage: "--bio-pump", traffic: "--bio-wound", unknown: "--bio-cyto" };

export const MACHINES_CSS = `
.swatch-mach-sized { background: radial-gradient(circle at 35% 35%, color-mix(in srgb, var(--ghost) 40%, var(--bg)), var(--ghost) 70%); border-radius: 50%; }
.swatch-mach-card { background: linear-gradient(90deg, var(--edge) 0 22%, var(--plate) 22%); box-shadow: inset 0 0 0 1px var(--plate-edge); height: 7px; vertical-align: 1px; }
.swatch-mach-found { background: linear-gradient(90deg, var(--ghost) 0 50%, color-mix(in srgb, var(--ghost) 30%, var(--bg)) 50%); }
.swatch-mach-chosen { background: var(--accent); box-shadow: 0 0 6px var(--accent); }
/* A machine looked for by family and not found: in the List only, never on the bench; a plain, empty mark. */
.swatch-mach-none { background: transparent; box-shadow: inset 0 0 0 1px var(--plate-edge); border-radius: 50%; }
/* An organelle on the shelf: drawn as the Cell view draws it, in its own colour; the swatch is the nucleus's tone, a large round body. */
.swatch-mach-organelle { background: radial-gradient(circle at 35% 35%, color-mix(in srgb, var(--bio-nucleus) 45%, var(--bg)), var(--bio-nucleus) 75%); border-radius: 50%; box-shadow: inset 0 0 0 1px color-mix(in srgb, var(--bio-nucleus) 60%, var(--bg)); }
.swatch-mach-room { background: var(--plate); box-shadow: inset 0 0 0 1px var(--plate-edge); }
${Object.entries(GROUPS).map(([group, token]) => `.swatch-mach-g-${group} { background: var(${token}); }`).join("\n")}
`;
