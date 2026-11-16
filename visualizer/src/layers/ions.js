// One fixed colour for each ion, wherever a layer draws it (schema/QUANTITY_LAYERS.md,
// rule 8). The colours are data (data/layers/ions.json), validated for colour-blind
// readers on the page's light and dark surface. Only three can be told apart from one
// another by every reader, so only three ions have one; any other species wears one neutral
// tone and is told apart by its name, which always stands beside its marks.

/**
 * The colour of each species of a run, as CSS text: Map id -> "#rrggbb". `species` are the
 * run's own ids, in its order; `dark` chooses the steps for the dark surface. Two species
 * that would share a colour (Cl and the generic M) do not: the later one takes the neutral tone.
 */
export function ionColours(table, species, dark) {
  const mode = dark ? "dark" : "light", taken = new Set(), out = new Map();
  for (const id of species) {
    const entry = table.colours?.[id], share = entry?.shares || id;
    if (entry && !taken.has(share)) {
      taken.add(share);
      out.set(id, entry[mode]);
    } else out.set(id, table.other[mode]);
  }
  return out;
}
