// Flux in the Cell view: what may flow in a species' cell, and on what basis each direction
// is drawn (schema/QUANTITY_LAYERS.md, rules 3, 7, 11 and 12, and "Flux in the Cell view").
//
// Nothing here draws. The declarations are data (data/layers/flux.json); this module checks
// them and works out, for one species, what is drawn and what is not, each with its reason.
//
// A species' cell has one source at a time, and the two never share a picture:
//   a looping run    the species' own run, made by the engine and packaged to loop (./loop.js);
//   illustration     where the species has no such run. Its form `direction only` is built:
//                    the number of beads stands for no number. Its form `typical values` is
//                    declared and holds no entries: each number needs a cited source.
//
// Every direction drawn has a declared basis, and the page says which. For illustration it
// is a law of the engine, cited by its id and where it was read; and only where that law
// speaks for the species shown (speaksFor). Where no basis gives a direction, both ways are
// drawn and none is claimed, or nothing is drawn and the reason is given.

export const FLUX_FORMAT = "cells.visualizer.flux@1";
export const WAYS = ["in", "out"];
export const FORMS = ["direction only", "typical values"];
/** What a group does where its law does not speak for the species: draws nothing, or both ways with no claim. */
export const WITHOUT = ["nothing", "both"];
/**
 * Beads a second on every lane of a `direction only` illustration. One pace for all, so
 * that no lane looks busier than another: the number of beads stands for no number.
 */
export const PACE = 1.25;

const text = (value) => typeof value === "string" && value.trim().length > 0;

/** A file of declarations (data/layers/flux.json), checked: { flux, problems }. Kinds with a problem are left out. */
export function readFlux(file) {
  const problems = [];
  const say = (problem) => problems.push(problem);
  if (file?.format !== FLUX_FORMAT) return { flux: null, problems: [`the flux declarations are not in the format ${FLUX_FORMAT}`] };
  const illustration = file.illustration || {};
  if (!text(illustration.notice)) say("the illustration has no notice to carry on the picture");
  for (const form of FORMS) if (!illustration.forms?.[form]) say(`the form \`${form}\` is not declared`);
  const typical = illustration.forms?.["typical values"];
  // Typical values are offered only once an entry with a source stands behind them.
  if (typical && typical.offered && !(typical.entries || []).length) say("the form `typical values` is offered with no entries");
  if (!text(file.engine?.revision)) say("the engine's revision the laws were read at is not given");
  const laws = file.laws || {};
  for (const [name, law] of Object.entries(laws)) {
    for (const field of ["id", "path", "declares"]) if (!text(law[field])) say(`law "${name}" has no ${field}`);
  }
  const seen = new Set();
  const kinds = [];
  for (const kind of file.kinds || []) {
    const before = problems.length;
    const name = `kind "${kind.id}"`;
    for (const field of ["id", "part", "label"]) if (!text(kind[field])) say(`${name} has no ${field}`);
    if (seen.has(kind.id)) say(`${name} is declared twice`);
    seen.add(kind.id);
    const groups = kind.groups || [];
    if (kind.only !== undefined && kind.only !== "run") say(`${name}: \`only\` may say "run" and nothing else`);
    if (kind.only === "run" && !text(kind.stream)) say(`${name} is drawn only from a run and names no stream of a run`);
    if (!groups.length && kind.only !== "run" && !text(kind.nothing)) say(`${name} draws nothing and does not say why`);
    for (const group of groups) {
      const at = `${name}, group "${group.id}"`;
      for (const field of ["id", "label", "says"]) if (!text(group[field])) say(`${at} has no ${field}`);
      const lanes = group.lanes || [];
      if (!lanes.length) say(`${at} has no lanes`);
      for (const lane of lanes) if (!text(lane.id) || !WAYS.includes(lane.way)) say(`${at}: a lane needs an id and a way, in or out`);
      if (group.law !== undefined) {
        if (!laws[group.law]) say(`${at} names the law "${group.law}", which is not declared`);
        if (!WITHOUT.includes(group.without)) say(`${at} does not say what is drawn where its law does not speak for a species`);
        if (group.without === "both" && !text(group.unclaimed)) say(`${at} draws both ways without its law and has no words for that`);
      }
      // Without a law no direction is claimed: both ways must then be there to be drawn.
      const both = WAYS.every((way) => lanes.some((lane) => lane.way === way));
      if ((group.law === undefined || group.without === "both") && !both) say(`${at} claims no direction and does not draw both ways`);
    }
    if (problems.length === before) kinds.push(kind);
  }
  return { flux: { ...file, kinds }, problems };
}

/**
 * Whether a law of the engine speaks for a part of this species (the file's `speaks_for`).
 * It does not for a species of which nothing is in the engine (proposed, planned or designed:
 * schema/ENTRIES.md), nor where the species' file has words of its own on the part: they say
 * how the species' part differs from the engine's, and the viewer does not weigh free text.
 * Returns { ok } or { ok: false, proposed, note }.
 */
export function speaksFor(species, capability) {
  const proposed = ["proposed", "planned", "designed"].includes(species?.modelled?.state);
  const note = (capability && species?.cell?.capabilities?.[capability.id]?.note) || null;
  return proposed || note ? { ok: false, proposed, note } : { ok: true };
}

/** Why a law's direction is not drawn for a species, in the page's words. */
export function whyNot(species, verdict) {
  const name = species?.label || "this species";
  if (verdict.note) {
    const first = `No direction is drawn for ${name}: its file says of its own part, “${verdict.note}”`;
    return `${first} ${verdict.proposed ? "Nothing of it is in the engine, and the engine's law claims nothing about it." : "The engine's law claims nothing about it."}`;
  }
  return `No direction is drawn for ${name}: nothing of it is in the engine, so no law of the engine speaks for this part of it.`;
}

/** Where a law was read, for the page: its id, the file and the revision. */
export function citation(flux, law) {
  return `the engine's law ${law.id}, read in ${law.path} at ${flux.engine.branch || "main"} ${flux.engine.revision}`;
}

/** The basis of a group's directions, in full, for a panel. */
export function basisOf(flux, group) {
  const law = flux.laws[group.law];
  return `Basis: ${citation(flux, law)}. It declares ${law.declares}. ${law.limit || ""}`.trim();
}

/**
 * What an illustration draws for one species, and what it does not.
 *   species        the species shown (its label, how it is modelled, what its file says of its parts)
 *   has(part)      whether the picture has that part for the species: it is in the map, the species
 *                  does not mark it absent, and the cell drawn has a place for it
 *   capabilityOf   (part) => the map's capability for the part, or null
 * Returns { kinds, withheld }.
 *   kinds     [{ id, part, label, token, groups: [{ id, label, says, claimed, basis, law, lanes }] }], the lanes
 *             as [{ id, key, label, way, species, spots, count, claimed }]: `claimed` says whether
 *             the lane's direction is the engine's declaration, or one of two ways neither of which is claimed
 *   withheld  [{ id, part, label, why }]: what has a place in the species and is not drawn, with the reason
 * A part the species lacks is neither: nothing is offered for it, and nothing is said of it here.
 */
export function planFor(flux, { species, has, capabilityOf = () => null }) {
  const kinds = [], withheld = [];
  for (const kind of flux?.kinds || []) {
    // What is drawn only from a run (the membrane's own routes) has no illustration, and none is spoken of.
    if (kind.only === "run" || !has(kind.part)) continue;
    const capability = capabilityOf(kind.part);
    if (!kind.groups.length) {
      withheld.push({ id: kind.id, part: kind.part, label: kind.label, why: kind.nothing });
      continue;
    }
    const groups = [];
    for (const group of kind.groups) {
      const verdict = group.law === undefined ? null : speaksFor(species, capability);
      const claimed = Boolean(verdict?.ok);
      if (verdict && !verdict.ok && group.without === "nothing") {
        withheld.push({ id: `${kind.id}/${group.id}`, part: kind.part, label: group.label, why: whyNot(species, verdict) });
        continue;
      }
      groups.push({
        id: group.id,
        label: group.label,
        claimed,
        law: claimed ? flux.laws[group.law] : null,
        says: claimed || group.law === undefined ? group.says : group.unclaimed,
        basis: claimed ? basisOf(flux, group) : null,
        lanes: group.lanes.map((lane) => ({
          id: lane.id,
          key: `${kind.id}/${group.id}/${lane.id}`,
          label: lane.label || lane.id,
          way: lane.way,
          species: lane.species || null,
          spots: group.spots || null,
          count: claimed ? (lane.count ?? null) : null,
          claimed,
        })),
      });
    }
    if (groups.length) kinds.push({ id: kind.id, part: kind.part, label: kind.label, token: kind.token || "particle", groups });
  }
  return { kinds, withheld };
}

/**
 * Which of a plan's kinds show now. A part's flux shows when the part is chosen, alone;
 * the Flux switch shows all of it. At rest (no part with flux chosen, the switch off)
 * nothing flows. A chosen part that the plan speaks of and draws nothing for (fuel, or
 * pumps the engine's law does not speak for) shows nothing, alone: its reason is given.
 */
export function shownKinds(plan, { on = false, part = null } = {}) {
  const chosen = part ? plan.kinds.filter((kind) => kind.part === part) : [];
  if (chosen.length || (part && plan.withheld.some((item) => item.part === part))) return chosen;
  return on ? plan.kinds : [];
}

/** What a plan withholds that speaks to what is shown now: of the chosen part alone, or of all. */
export function shownWithheld(plan, { on = false, part = null } = {}) {
  const chosen = part ? plan.withheld.filter((item) => item.part === part) : [];
  if (part && (chosen.length || plan.kinds.some((kind) => kind.part === part))) return chosen;
  return on ? plan.withheld : [];
}

/** The words an illustration keeps on the picture for as long as it shows: its notice, then its form. */
export function illustrationWords(flux, still = false) {
  const form = flux.illustration.forms["direction only"];
  return [flux.illustration.notice, still ? `${form.says} · shown still` : form.says];
}
