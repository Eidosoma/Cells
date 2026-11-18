// What a unit of the Protein atlas says of a law no active model declares, from the law-port
// inventory (data/laws/law_port.json, cells.visualizer.law_port@1, schema/LAWS_LIBRARY.md).
//
// On 17 November 2026 the project decided to port tested older laws to the active engine
// (D211), and the law-port inventory gave each law behind the atlas's units a mark. The page's
// words for each mark are here and nowhere else. They are the lead's words, given to the
// viewer on 17 November 2026, and stand letter for letter: "tested" is the inventory's word for
// a passing test of the old kernel, not a judgement of the engine, and "declared" is not a level.
//
// A law the inventory has no row for keeps the words the unit's panel gave it before (in
// laws_card.js): no mark is guessed.

export const LAW_PORT_FORMAT = "cells.visualizer.law_port@1";

/**
 * Each mark's words, in the order a unit's panel says them. A law that is not a port has words
 * of its own, keyed by the law as the inventory names it; a row the source has no words for gets
 * none, and keeps the panel's earlier words.
 */
export const PORT_PHRASES = {
  "port as is": "Listed in Cells' law inventory, implemented in older code and tested; not yet declared by an active model. Porting is planned (D211).",
  "fold into an owner's planned law": "Listed in the law inventory; to be rebuilt as the cardiac lane's laws (D211).",
  "not a port": {
    "mitochondrial_passive_continuous_si@1": "Covered by the mitochondria design (D193)",
    "junction_flux() of emt_mirna_pair@1 (no ID)": "A feature request (FR-16)",
  },
};

/** A law ID as the atlas writes it: a name and a version, with no space. */
const LAW_ID = /^[A-Za-z_][A-Za-z0-9_.]*@[0-9]+$/;
const firstWord = (text) => String(text).trim().split(/\s+/)[0];

/** The words for one row of the table, or null where the source has none. */
export function phraseOf(row) {
  const said = PORT_PHRASES[row?.mark];
  if (typeof said === "string") return said;
  return said && typeof said === "object" && typeof said[row.law] === "string" ? said[row.law] : null;
}

/** The table, where the scene carries one of this format; null otherwise. */
export function portTable(scene) {
  const table = scene?.law_port;
  return table?.format === LAW_PORT_FORMAT && Array.isArray(table.rows) ? table : null;
}

/**
 * The row of the table for one law a unit's panel names, or null.
 * - A row with a law ID is the law of that ID, as written, on a unit the row names.
 * - A row without one (the inventory's words for a function in a model's profile) is, on a unit
 *   it names, that unit's one law that is not an ID and begins with the same word (the function's
 *   name): never a law of another unit, and nothing where a unit has two such laws.
 */
export function rowFor(table, unit, law, laws = [law]) {
  if (!table || !unit) return null;
  for (const row of table.rows) {
    if (!row.units?.includes(unit)) continue;
    if (row.has_id && row.law === law) return row;
    if (!row.has_id && !LAW_ID.test(law)) {
      const words = laws.filter((item) => !LAW_ID.test(item) && firstWord(item) === firstWord(row.law));
      if (words.length === 1 && words[0] === law) return row;
    }
  }
  return null;
}

/**
 * The lines a unit's panel gives its laws that no active model declares: one for each mark's
 * words, the laws of the same words gathered and named as the panel names them, in the marks'
 * order; and the laws the table has no row (or the source no words) for, to be said as before.
 * `unit`: the unit's code (U05); `undeclared`: its laws no active model declares; `laws`: all it names.
 */
export function portLines(table, unit, undeclared, laws = undeclared) {
  const groups = new Map(), uncovered = [];
  for (const law of undeclared) {
    const row = rowFor(table, unit, law, laws);
    const phrase = row ? phraseOf(row) : null;
    if (!phrase) {
      uncovered.push(law);
      continue;
    }
    if (!groups.has(phrase)) groups.set(phrase, { mark: row.mark, phrase, laws: [] });
    groups.get(phrase).laws.push(law);
  }
  const order = Object.keys(PORT_PHRASES);
  const lines = [...groups.values()]
    .sort((a, b) => order.indexOf(a.mark) - order.indexOf(b.mark))
    .map((group) => ({ ...group, label: `${group.laws.join(", ")}: ${group.phrase}` }));
  return { lines, uncovered };
}
