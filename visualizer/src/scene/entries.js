// The entries of the species switch, in three kinds (schema/ENTRIES.md): a species, a cell type
// of a species, and a model system. What the page says of each in the ladder's words, and the
// small helpers the Cell view, the switch and the views of model systems share. The scene
// carries them as tools/lib/entries.py reads them: each species with its `cell_types` and
// `default_cell_type`, and the model systems in `models`.

/** What Cells models of an entry, one word for each step of the ladder: each asks of the record all that the one before asks, and more. */
export const LADDER = ["generic", "proposed", "planned", "designed", "modelled"];

/** The ladder's words on the page. "Not modelled" wherever nothing of the entry is in the engine. */
export const MODELLED = { generic: "Generic cell", proposed: "Proposed, not modelled", planned: "Planned, not modelled", designed: "Designed, not modelled", modelled: "Modelled" };

/** Whether nothing of an entry is in the engine, by its word: proposed, planned or designed. */
export const notInEngine = (modelled) => ["proposed", "planned", "designed"].includes(modelled?.state);

/** The model systems of a scene (schema/MODEL_SYSTEMS.md), in their order. */
export const modelSystems = (scene) => scene?.models || [];

/** A model system of the scene by its id, or null. */
export const modelSystemOf = (scene, id) => modelSystems(scene).find((item) => item.id === id) || null;

/**
 * The cell types of a species, the species' own first: as the scene carries them, or, for a
 * scene made before cell types (or a species written by hand), the one the species' own cell
 * block describes, made here as the entries reader makes it (schema/CELL_TYPES.md).
 */
export function cellTypesOf(species) {
  if (!species) return [];
  if (species.cell_types?.length) return species.cell_types;
  const own = species.cell_type || {};
  return [
    {
      id: own.id || "cell",
      label: own.label || (species.modelled?.state === "generic" ? "Generic cell" : "Its cell"),
      own: true,
      modelled: species.modelled,
      levels: (species.levels || []).filter((level) => level.id === "cell" || level.id === "tissue"),
      parts: species.cell?.parts || {},
      capabilities: species.cell?.capabilities || {},
      facts: species.cell?.facts || [],
      loop: own.loop || null,
    },
  ];
}

/**
 * The rows of the species switch for its options ([id, label, line]), in the options' order: each
 * species and model system with its line (a species' organism, a model system's `is`), its word
 * in the ladder and its heading; and, under a species with more than one cell type, a row for
 * each type ("<species>.<type>"). A species with one type offers no choice of type.
 */
export function switchRows(scene, options) {
  const said = new Map([...(scene?.species || []), ...modelSystems(scene)].map((item) => [item.id, item]));
  return options.flatMap(([id, label, line]) => {
    const item = said.get(id) || {};
    const state = item.modelled?.state || null;
    const kind = item.kind === "model system" ? "model system" : "species";
    const row = { id, label, organism: line || item.organism || item.is || "", state, word: state ? MODELLED[state] || state : "", group: item.group || "", kind };
    const types = kind === "species" ? cellTypesOf(item) : [];
    if (types.length < 2) return [row];
    return [row, ...types.map((type) => {
      const word = type.modelled?.state || state;
      return { id: `${id}.${type.id}`, label: `${label}, ${type.label}`, organism: "", state: word, word: word ? MODELLED[word] || word : "", group: row.group, kind: "cell type", of: id };
    })];
  });
}

const EUKARYA_GROUPS = new Set(["Animals", "Plants", "Amoebozoa"]);
const DOMAINS = ["Eukarya", "Bacteria", "Archaea"];

/** Domains come first. Their groups and other sections follow the order of their first rows. */
export function switchSections(rows) {
  const sections = new Map();
  for (const row of rows) {
    const name = EUKARYA_GROUPS.has(row.group) ? "Eukarya" : row.group;
    if (!sections.has(name)) sections.set(name, new Map());
    const groups = sections.get(name);
    if (!groups.has(row.group)) groups.set(row.group, []);
    groups.get(row.group).push(row);
  }
  const ordered = [...DOMAINS.filter((name) => sections.has(name)), ...[...sections.keys()].filter((name) => name && !DOMAINS.includes(name))];
  if (sections.has("")) ordered.push("");
  return ordered.map((name) => ({
    name,
    groups: [...sections.get(name)].map(([name, rows]) => ({ name, rows })),
  }));
}

/** The cell type of a species with this id, or its default where the id is not one of its types. */
export function cellTypeOf(species, id = null) {
  const types = cellTypesOf(species);
  return types.find((type) => type.id === id) || types.find((type) => type.id === species?.default_cell_type) || types[0] || null;
}
