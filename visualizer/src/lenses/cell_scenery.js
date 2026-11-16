// What a species' cell may hold beyond the parts that carry a capability of Cells: threads
// and hairs that stand out from it (schema/SPECIES.md, "Appendages are a general part"), and
// a plant cell's own organelles and wall (schema/SPECIES_SHAPES.md, `cell.parts`).
//
// Nothing in the engine stands behind any of them, so each is scenery: neutral glass, no
// status. Unlike the wall of old they can be chosen, and the lens then says what the
// species' file gives of them, with its sources (cell.js, describe).
//
// One kind is one word of the contract, one entry in a species file and one function
// here: APPENDAGES for what stands out from the cell, ORGANELLES (each with its name) for
// what lies in it. A function is given the cell (`env`) and the entry (`spec`), adds what it
// draws through `env.add(object, id)`, and returns what was drawn of how many, the line the
// picture says of it, and what the panel says was drawn. A kind the viewer does
// not know draws nothing and is warned of. Everything here is placed from a stream of
// chance of its own, after the rest of the cell, so that a cell without these parts is
// built exactly as before.

import * as THREE from "../three.js";

const UP = new THREE.Vector3(0, 1, 0);
const along = (direction) => new THREE.Quaternion().setFromUnitVectors(UP, direction.clone().normalize());

/** A number the data gives as one value or as a range of two: its middle. */
export const middle = (value) => (Array.isArray(value) ? (value[0] + value[1]) / 2 : value);
/** The same in words: "5 to 10 µm". */
export const words = (value, unit = "") => `${Array.isArray(value) ? `${value[0].toLocaleString("en-US")} to ${value[1].toLocaleString("en-US")}` : Number(value).toLocaleString("en-US")}${unit ? ` ${unit}` : ""}`;

// The most of one kind that is drawn. Of a larger number a part is drawn, and the picture says how many of how many.
export const MOST = { flagellum: 12, pilus: 120, chloroplasts: 100 };
// In the schematic mode parts are enlarged and few (the page says so on the card): this many, this much larger.
const FEW = { chloroplasts: { count: 18, larger: 1.5 } };

/** Which shell of the cell a word of the contract means, as how far outside the cell membrane it stands (0 for the cell membrane). */
const shellOf = (env, name) => (name === "outer membrane" && env.parts.membranes === 2 ? env.shells.outerGap : name === "wall" && env.parts.wall ? env.shells.wallGap : 0);

/**
 * Places on the part of the cell that is kept (below the cut), spread as the contract's
 * `where` says: all over, at one pole or both (the ends of its long way), or on one side.
 * Each is a point of the cell membrane and the way out from it there.
 */
function places(env, where, count) {
  const { frame, random } = env, found = [];
  const long = frame.long / 2, mid = frame.middle;
  const fits = (spot) => {
    const along = (spot.position.x - mid) / long; // -1 at one end of the long way, 1 at the other
    if (where === "one pole") return along > 0.72;
    if (where === "both poles") return Math.abs(along) > 0.72;
    if (where === "one side") return spot.direction.z > 0.55;
    return true;
  };
  for (let guard = 0; found.length < count && guard < count * 400; guard++) {
    const spot = env.skinAt(random);
    if (spot.position.y > env.cut - 0.06 * (frame.top - frame.base) || !fits(spot)) continue;
    if (env.clear.some((point) => point.distanceTo(spot.position) < env.clearBy)) continue; // where a click is meant for the membrane itself
    found.push(spot);
  }
  return found;
}

// ------------------------------------------------------------------ what stands out from the cell

/**
 * A flagellum: a long, wavy thread. Its length and width are the data's; how it waves (a
 * helix about 0.4 µm across that turns once in 2.3 µm) is the picture's choice. Where the
 * entry names a `base`, the machine at its foot is drawn as a small part of its own.
 */
function flagellum(env, spec, id) {
  const count = Math.round(middle(spec.count)), drawn = Math.min(count, MOST.flagellum);
  const length = middle(spec.length_um) / env.u, radius = Math.max(middle(spec.width_nm) / 2000 / env.u, env.thinnest);
  const wave = { reach: 0.2 / env.u, pitch: 2.3 / env.u };
  const gap = shellOf(env, spec.from), outer = Math.max(env.shells.outerGap, env.shells.wallGap);
  const thread = env.glass({ opacity: 0.62, glass: 0.3, thin: 0.5 });
  const foot = spec.base ? env.glass({ opacity: 0.85, glass: 0.2 }) : null;
  let reach = 0;
  const feet = []; // where each thread's foot is and which way is out: what a closer view of the machine there would be framed on
  for (const at of places(env, spec.where, drawn)) {
    const start = at.position.clone().addScaledVector(at.direction, gap), out = at.direction;
    feet.push({ at: at.position.clone(), out: out.clone() });
    const side = new THREE.Vector3().crossVectors(out, Math.abs(out.y) < 0.9 ? UP : new THREE.Vector3(1, 0, 0)).normalize(), other = new THREE.Vector3().crossVectors(out, side);
    const phase = env.random() * Math.PI * 2, steps = Math.max(24, Math.ceil((length / wave.pitch) * 14));
    const points = [];
    for (let step = 0; step <= steps; step++) {
      const s = (step / steps) * length, open = Math.min(1, s / (wave.pitch * 0.5)), turn = (s / wave.pitch) * Math.PI * 2 + phase;
      points.push(start.clone().addScaledVector(out, s).addScaledVector(side, Math.cos(turn) * wave.reach * open).addScaledVector(other, Math.sin(turn) * wave.reach * open));
      reach = Math.max(reach, points.at(-1).length());
    }
    env.add(new THREE.Mesh(new THREE.TubeGeometry(new THREE.CatmullRomCurve3(points), steps * 2, radius, 6), thread), id);
    if (foot) {
      // The machine at the foot: a short drum through the cell's shells, at least 45 nm across and
      // a little more than twice as wide as its thread (its size is the picture's choice: the file gives none).
      const through = outer + 0.03 / env.u, across = Math.max(0.0225 / env.u, radius * 2.2);
      const drum = new THREE.Mesh(new THREE.CylinderGeometry(across, across, through, 14), foot);
      drum.position.copy(at.position).addScaledVector(out, through / 2 - 0.012 / env.u);
      drum.quaternion.copy(along(out));
      env.add(drum, `${id}:base`);
    }
  }
  const whole = length > env.frame.long ? ": zoom out for the whole of them" : "";
  return { drawn, of: spec.count, reach, foot: Boolean(foot), feet, note: `${drawn} of ${words(spec.count)} ${spec.label.toLowerCase()}, each drawn ${words(Number(middle(spec.length_um).toPrecision(2)), "µm")} long${whole}`, sizes: [["Drawn", `${drawn}, each ${words(Number(middle(spec.length_um).toPrecision(2)), "µm")} long and ${words(Math.round(middle(spec.width_nm)), "nm")} wide: the middle of what the sources give. How each one waves is the picture's choice.`]] };
}

/** A pilus (a fimbria): a short, straight hair. Its length and width are the data's. */
function pilus(env, spec, id) {
  const count = Math.round(middle(spec.count)), drawn = Math.min(count, MOST.pilus);
  const length = middle(spec.length_um) / env.u, radius = Math.max(middle(spec.width_nm) / 2000 / env.u, env.thinnest);
  const gap = shellOf(env, spec.from);
  const hair = new THREE.CylinderGeometry(radius, radius, length, 5).translate(0, length / 2, 0);
  const spots = places(env, spec.where, drawn).map((at) => ({ position: at.position.clone().addScaledVector(at.direction, gap), direction: at.direction }));
  env.add(env.instanced(hair, env.glass({ opacity: 0.5, glass: 0.3 }), spots), id);
  const reach = Math.max(0, ...spots.map((spot) => spot.position.length())) + length;
  return { drawn: spots.length, of: spec.count, reach, note: `${spots.length} of ${words(spec.count)} ${spec.label.toLowerCase()} drawn`, sizes: [["Drawn", `${spots.length} of them, on the part of the cell that is kept, each ${words(Number(middle(spec.length_um).toPrecision(2)), "µm")} long and ${words(Number(middle(spec.width_nm).toPrecision(2)), "nm")} wide.`]] };
}

export const APPENDAGES = { flagellum, pilus };

// ------------------------------------------------------------------ what lies in the cell

/**
 * A plant cell's vacuole: one large body that fills its share of the cell's volume, in the
 * cell's own shape. The share is the data's in both size modes. Everything else in the cell
 * is held between it and the wall (the builder presses each part outward, see `vacuoleOf`).
 */
function vacuole(env, sizes, id) {
  const body = env.vacuole;
  if (!body) return null;
  const glass = env.glass({ opacity: 0.2, glass: 0.45, clip: true, side: THREE.DoubleSide, colour: "ghost" });
  const shell = new THREE.Mesh(env.solid, glass);
  shell.scale.setScalar(body.scale);
  shell.renderOrder = 5;
  shell.userData.pickFilter = (hit) => !env.inCut(hit.point); // the part of it that the cut takes away is not there to be clicked
  env.add(shell, id);
  // Where the cut passes through it: its section, as a clear face with a line round it.
  const ring = env.frame.outline.ring(-body.inset, env.cut + 0.012, 16);
  const face = new THREE.Mesh(env.fan(ring), env.glass({ opacity: 0.22, side: THREE.DoubleSide, colour: "ghost" }));
  face.renderOrder = 4;
  env.add(face, id);
  env.add(new THREE.LineLoop(new THREE.BufferGeometry().setFromPoints(ring), env.line({ opacity: 0.9 })), null);
  const share = middle(sizes.share);
  return { drawn: 1, of: 1, note: env.real ? `The vacuole fills ${Math.round(share * 100)}% of the cell` : `The vacuole fills ${Math.round(share * 100)}%: enlarged parts reach into it`, sizes: [["Drawn", `One body in the cell's own shape that fills ${Math.round(share * 100)}% of its volume. To scale, what else the cell holds lies between it and the wall; where parts are drawn enlarged they reach into it.`]] };
}

/**
 * Chloroplasts: lens-shaped bodies that line the inside of the cell's membrane, pressed
 * into the vacuole. Their number and width are the data's; that each is a little flatter
 * than it is wide is the picture's choice. Those of the part cut away are not drawn.
 */
function chloroplasts(env, sizes, id) {
  const { frame, random } = env;
  const of = Math.round(middle(sizes.count ?? 40)), few = env.real ? null : FEW.chloroplasts;
  const whole = Math.min(of, few ? few.count : MOST.chloroplasts);
  const half = ((middle(sizes.across_um ?? 5) / 2) / env.u) * (few ? few.larger : 1), flat = 0.62;
  const spots = [];
  // Spread over the whole cell's sides and base; the ones that fall in the part cut away are left out.
  for (let guard = 0, tried = 0; tried < whole && guard < whole * 300; guard++) {
    const spot = env.skinAt(random);
    if (spot.position.y > frame.top - frame.bevel * 0.6) continue; // none on the outer face
    const at = spot.position.clone().addScaledVector(spot.direction, -(half * flat + 0.04 * half));
    if (spots.some((other) => other.at.distanceTo(at) < half * 1.9)) continue;
    spots.push({ at, out: spot.direction, kept: spot.position.y < env.cut - half * 0.5 });
    tried += 1;
  }
  const kept = spots.filter((spot) => spot.kept);
  const lens = new THREE.SphereGeometry(half, 18, 12).scale(1, flat, 1);
  // Green, as a chloroplast is (the user, 16 November 2026): the one piece of scenery with a colour of
  // its own. Where colour shows status it is neutral like the rest, since green there says "qualified".
  const body = env.glass({ opacity: 0.86, glass: 0.15, depthWrite: true, thin: 0.6, texture: "grain", natural: "bioChloroplast" });
  env.add(env.instanced(lens, body, kept.map((spot) => ({ position: spot.at, direction: spot.out }))), id);
  const text = few ? `${kept.length} of ${of.toLocaleString("en-US")} chloroplasts drawn, enlarged` : `${kept.length} of ${of.toLocaleString("en-US")} chloroplasts drawn: the rest were cut away`;
  return { drawn: kept.length, of, note: text, sizes: [["Drawn", few ? `${kept.length} of them, ${few.larger} times their size, in the schematic picture.` : `${kept.length} of them, each ${words(middle(sizes.across_um), "µm")} across: the ones that lie in the part of the cell that is kept. That each is a little flatter than it is wide is the picture's choice.`], ["Colour", "Green, as a chloroplast is. It is the one piece of scenery with a colour of its own, and says nothing of a status: where colour shows status it is neutral like the rest."]] };
}

// Each with the name the page gives it. Drawn in this order: the vacuole first, since what else the cell holds is pressed against it.
export const ORGANELLES = { vacuole: { label: "Vacuole", draw: vacuole }, chloroplasts: { label: "Chloroplasts", draw: chloroplasts } };

/**
 * The body a vacuole takes up, for a cell that holds one: the cell's own shape, smaller by
 * the cube root of its share, so that it fills that share of the volume. `holds` says
 * whether a point lies in it; `inset` is how far inside the cell's sides its own sides lie.
 */
export function vacuoleOf(frame, parts) {
  if (!parts.organelles?.includes("vacuole")) return null;
  const share = Math.min(1, Math.max(0.05, middle(parts.organelle_sizes?.vacuole?.share ?? 0.8)));
  const scale = Math.cbrt(share);
  const probe = new THREE.Vector3();
  return {
    share,
    scale,
    inset: frame.equator.widest * (1 - scale),
    holds: (point) => frame.inside(probe.copy(point).multiplyScalar(1 / scale)) > 0,
  };
}

/**
 * Draws a cell's scenery of these kinds, after everything else in it. Returns what the lens
 * needs: for each thing that can be chosen, its id, name, what the file gives and what was
 * drawn; the lines the picture says beside the cell; and how far from the cell's middle the
 * longest thread reaches.
 */
export function buildScenery(env) {
  const { parts } = env, items = [], notes = [];
  let reach = 0;
  const done = (item, result) => {
    if (!result) return;
    items.push({ ...item, drawn: result.drawn, of: result.of, sizes: result.sizes || [] });
    if (result.note) notes.push({ text: result.note });
    reach = Math.max(reach, result.reach || 0);
  };
  for (const name of Object.keys(ORGANELLES)) {
    if (!parts.organelles?.includes(name)) continue;
    const sizes = parts.organelle_sizes?.[name] || {};
    done({ id: `scenery:${name}`, kind: name, label: ORGANELLES[name].label, facts: sizes, sources: sizes.sources || [] }, ORGANELLES[name].draw(env, sizes, `scenery:${name}`));
  }
  (parts.appendages || []).forEach((spec, index) => {
    const draw = APPENDAGES[spec.kind], id = `scenery:appendage:${index}`;
    if (!draw) {
      console.warn(`cell scenery: no drawing for an appendage of kind "${spec.kind}"; it is left out`);
      return;
    }
    const result = draw(env, spec, id);
    done({ id, kind: spec.kind, label: spec.label || spec.kind, facts: spec, sources: spec.sources || [] }, result);
    // The machine at its foot, where the entry names one and the drawing gave it a foot: a part of its own.
    if (spec.base && result?.foot) items.push({ id: `${id}:base`, kind: "base", label: spec.base.label || "Its base", base: spec.base, of: spec.label || spec.kind, feet: result.feet || [], sources: spec.sources || [] });
  });
  return { items, notes, reach };
}
