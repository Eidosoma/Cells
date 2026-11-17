// The Laws library: a view of its own (the user, 16 November 2026: "racjs", "a view of its
// own", "something cool and impressive"). A glass wall of shelves holds every declared piece of
// the engine, a slate bar for each on its family's plank; in front of it stand the racks, one
// for each model, with a rail for every kind of piece it declares and each piece seated in its
// slot. Choose a piece and it slides out of the wall and glows, and light runs from it along a
// route to every slot that declares it; choose a rack and its pieces glow on the wall.
//
// Drawn from data/laws/pieces.json (schema/LAWS_LIBRARY.md), read from the engine's code. Every
// visual difference stands for one thing the list says, and the legend names each one drawn
// (MARKS, below): solid slate, a dark band, a glass outline, a narrower bar higher up, a
// column's height, a rack, a card, a block, an empty socket marked "free", a box on the plinth,
// forward and faint under a search, a faint empty place, and blue light for what is chosen.
// Nothing else differs: the glass, rails, planks, dividers, sockets and plinth are the room.
// No colour, glow or height is a status; a status is said only in the panel, with its source.

import * as THREE from "../three.js";
import { roundedSlab } from "../core/materials.js";
import { makeEnvironment, makeStudio } from "../core/environment.js";
import { disposeTree } from "../core/stage.js";
import { Library, WHERE, pageId, engineId } from "./laws_data.js";
import { describe as describePart, sections as listSections } from "./laws_card.js";
import { layoutOf, WIDE } from "./laws_layout.js";
import { PLANK, FOOT, PLINTH, plaquesOf, plaqueMesh, routeMaterial, mergeTubes, fitView } from "./laws_marks.js";

/** The look this view asks of the stage (core/look.js): its slate and glass are natural colours, so filmic light suits them. */
export const LAWS_LOOK = { rich: true, filmic: true, exposure: 1.06, contact: true, reach: 0.5, shade: 0.6 };
/** The bloom while something is chosen: only what is chosen is marked to shine (stage.glow). */
export const LAWS_BLOOM = { strength: 0.35, radius: 0.34, floor: 0.08 };
/** In the light theme a little less: on a light ground the glow washes out what it shines from. */
export const LAWS_BLOOM_LIGHT = { strength: 0.28, radius: 0.3, floor: 0.1 };
const RIM = 0.1; // how much wider and taller than a card its lit edge is, in the light theme
const LIFT = { chosen: 0.62, found: 0.2, slot: 0.3 };
const GROW = 0.5; // seconds for a route's light to reach its slot
const RUNS = 3; // how many times the light runs along the routes after a choice, before it holds steady
const RUN = 1.4; // seconds for one run
const VIEW = { azimuth: 0.2, polar: 1.36 };
const FADE = 0.8; // seconds over which the running light fades into a steady glow
const now = () => (typeof performance !== "undefined" ? performance.now() : Date.now());

/**
 * What each visual difference stands for: the legend's words (truth stays exactly as strict).
 * `when` says when a mark is drawn at all; the legend lists only what is drawn.
 */
export const MARKS = [
  { id: "laws-main", label: "Solid slate: on main", description: "A solid slate bar on the wall, or a slate card in a rack: a piece read on main.", when: (lens) => lens.library.counts().where.main > 0 },
  { id: "laws-candidate", label: "Dark band: on the landing candidate, not main", description: "A dark band across a bar or card: the piece is read on the landing candidate and is not on main yet.", when: (lens) => lens.library.counts().where.candidate > 0 },
  { id: "laws-design", label: "Glass outline: a design note's; no code", description: "A bar of clear glass with an outline: a design note names the piece; there is no code for it.", when: (lens) => lens.library.counts().where.design > 0 },
  { id: "laws-older", label: "Narrower, higher: an older family's, or no registry", description: "A narrower bar on the upper part of its column, above a gap: a law of an older model family's tables, or a named law in no registry. Neither is a piece of the one model.", when: (lens) => lens.layout.bars.some((bar) => bar.id && bar.older) },
  { id: "laws-height", label: "Column height: the family's count", description: "Each column holds one bar for each piece of its family, so its height is the family's count.", when: () => true },
  { id: "laws-rack", label: "Rack: a model, by its MODEL_ID", description: "Each rack in front of the wall is a model the engine names by its MODEL_ID; its rows are the kinds of piece it declares.", when: (lens) => lens.layout.frames.length > 0 },
  { id: "laws-slot", label: "Card: a piece the model declares", description: "A card seated in a rack's slot: a piece the model declares there, drawn in the piece's own form.", when: (lens) => lens.cardList.length > 0 },
  { id: "laws-block", label: "Block: the inner model a rack holds", description: "A long block across the head of a rack: the inner model that model holds whole.", when: (lens) => lens.blocks.mesh.count > 0 },
  { id: "laws-next", label: "Empty socket, 'free': a next code; no piece", description: "An empty socket at the end of a row, marked with a number and 'free': the row's next free registry code, as read from the code. No piece stands there.", when: (lens) => lens.nextCount > 0 },
  { id: "laws-older-family", label: "Box on the plinth: an older model family", description: "Each small box on the plinth's front is an older model family; its laws are tables inside it.", when: (lens) => lens.older.mesh.count > 0 },
  { id: "laws-found", label: "Forward: found; faint: not found", description: "While a search, a filter or a mark of the legend is chosen, what it picks out stands forward in its own form, and the rest fades.", when: (lens) => Boolean(lens.filter.family || lens.filter.where || lens.filter.query || lens.filter.box || lens.isolate) },
  { id: "laws-empty", label: "Faint bar: an empty place (size test)", description: "A faint bar is no piece: an empty place added to test the wall at a larger size.", when: (lens) => lens.size > 0 },
  { id: "laws-chosen", label: "Blue light: your choice, its slots and routes", description: "Blue light marks what you chose, every slot that declares it and a route from the piece to each slot; after a choice the light runs along each route from the piece to its slot, then holds.", when: () => true },
];
/** The legend's marks that pick out pieces, for its own choice (setIsolate). */
const OLDER = new Set(["an older family", "no registry"]);
const ISOLATES = {
  "laws-main": (piece) => piece?.where === "main",
  "laws-candidate": (piece) => piece?.where === "candidate",
  "laws-design": (piece) => piece?.where === "design",
  "laws-older": (piece) => OLDER.has(piece?.registry),
};
/** What the legend says of everything else. */
export const LAWS_NOTE = "Glass, rails, planks, dividers, sockets and the plinth are the room, and stand for nothing.";

const dummy = new THREE.Object3D();

/** Instances of one shape, each with a base place and an offset that eases to its target. */
class Instances {
  constructor(geometry, material, count, { pick = null } = {}) {
    this.mesh = new THREE.InstancedMesh(geometry, material, Math.max(1, count));
    this.mesh.count = count;
    this.mesh.instanceMatrix.setUsage(THREE.DynamicDrawUsage);
    this.mesh.instanceColor = new THREE.InstancedBufferAttribute(new Float32Array(Math.max(1, count) * 3).fill(1), 3);
    this.items = new Array(count);
    this.offset = new Float32Array(count);
    this.target = new Float32Array(count);
    if (pick) this.mesh.userData.pick = (hit) => pick(this.items[hit.instanceId]);
  }

  place(index, item) {
    this.items[index] = item;
    dummy.position.set(item.x, item.y, item.z + this.offset[index]);
    dummy.scale.set(item.w, item.h, item.d);
    dummy.updateMatrix();
    this.mesh.setMatrixAt(index, dummy.matrix);
  }

  tint(index, value) {
    this.mesh.setColorAt(index, value);
  }

  /** Eases every offset toward its target; returns whether anything still moves. */
  step(k) {
    let moving = false;
    for (let index = 0; index < this.mesh.count; index++) {
      const gap = this.target[index] - this.offset[index];
      if (Math.abs(gap) < 1e-4) {
        if (this.offset[index] === this.target[index]) continue;
        this.offset[index] = this.target[index];
      } else {
        this.offset[index] += gap * k;
        if (Math.abs(this.target[index] - this.offset[index]) >= 1e-4) moving = true;
      }
      this.place(index, this.items[index]);
    }
    this.mesh.instanceMatrix.needsUpdate = true;
    return moving;
  }

  flush() {
    this.mesh.instanceMatrix.needsUpdate = true;
    if (this.mesh.instanceColor) this.mesh.instanceColor.needsUpdate = true;
    this.mesh.computeBoundingSphere();
  }
}

/** A set of instances built from a list of boxes, added to a parent: the room's own parts. */
function boxes(parent, geometry, material, items, options = {}) {
  const set = new Instances(geometry, material, items.length, options);
  items.forEach((item, index) => set.place(index, item));
  set.flush();
  parent.add(set.mesh);
  return set;
}

export class LawsLens {
  constructor(stage, model, labels, library = model?.raw?.laws) {
    this.id = "laws";
    this.stage = stage;
    this.model = model;
    this.labels = labels;
    this.library = library instanceof Library ? library : new Library(library);
    this.root = new THREE.Group();
    this.shine = new THREE.Group(); // what the bloom shines from: the chosen bar, the lit slots and the routes
    this.selected = null; // a page id: a piece or a frame
    this.hovered = null;
    this.filter = { family: null, where: null, query: "", box: null };
    this.wantsLeftRoom = true; // the viewer leaves the room clear of its cards on the left (stage.setInsets left)
    this.size = 0; // a test of size only: empty slots on the wall
    this.narrow = false;
    this.active = false;
    this.growth = 1; // how far the routes' light has grown toward their slots, 0 to 1
    this.running = 0; // seconds of the light's runs left
    this.clock = 0;
    this.routes = [];
    this.materials = this.makeMaterials();
    this.build();
    this.applyPalette(stage.palette || {});
  }

  // ------------------------------------------------------------ materials

  makeMaterials() {
    const standard = (options) => new THREE.MeshStandardMaterial({ roughness: 0.5, metalness: 0.05, ...options });
    const materials = {
      // A piece: slate with a soft sheen, so the studio's lights run along each bar.
      slate: standard({ roughness: 0.34, metalness: 0.18, envMapIntensity: 1.1 }),
      band: standard({ roughness: 0.5 }),
      glass: new THREE.MeshPhysicalMaterial({ roughness: 0.08, metalness: 0, transparent: true, opacity: 0.2, clearcoat: 1, clearcoatRoughness: 0.05, depthWrite: false }),
      outline: new THREE.LineBasicMaterial({ transparent: true, opacity: 0.95 }),
      ghost: new THREE.MeshBasicMaterial({ transparent: true, opacity: 0.2, depthWrite: false }),
      // The room: a glass wall, planks and rails of brushed metal, a slate plinth.
      panel: new THREE.MeshPhysicalMaterial({ roughness: 0.14, metalness: 0, transparent: true, opacity: 0.4, clearcoat: 1, clearcoatRoughness: 0.08, depthWrite: false, side: THREE.DoubleSide }),
      plank: standard({ roughness: 0.3, metalness: 0.55 }),
      rail: standard({ roughness: 0.26, metalness: 0.65 }),
      socket: standard({ roughness: 0.8, metalness: 0.1 }),
      plinth: standard({ roughness: 0.62, metalness: 0.1 }),
      // What is chosen carries a meaning: it gives off its own light, and stays out of filmic light and contact shade.
      // It shines by its own light in the accent, not by the lamps, so it stays the accent's blue under any light.
      lit: new THREE.MeshStandardMaterial({ color: 0x000000, roughness: 0.55, metalness: 0, emissiveIntensity: 0.9, envMapIntensity: 0.35, toneMapped: false }),
      line: routeMaterial(),
      ring: new THREE.MeshBasicMaterial({ toneMapped: false, transparent: true, opacity: 0.95 }),
    };
    for (const name of ["line", "ring", "ghost", "outline", "lit"]) materials[name].userData.noContact = true;
    return materials;
  }

  // ------------------------------------------------------------ the picture

  build() {
    // A rebuild (another size, a turned screen) frees the old shapes and the names' texture; the materials are kept.
    if (this.plaqueMesh) {
      this.plaqueMesh.material.map?.dispose();
      this.plaqueMesh.material.dispose();
      this.plaqueMesh = null;
    }
    this.root.traverse((object) => object.geometry?.dispose?.());
    for (const child of [...this.root.children]) this.root.remove(child);
    for (const child of [...this.shine.children]) this.shine.remove(child);
    const library = this.library;
    this.layout = layoutOf(library, { size: this.size, narrow: this.narrow });
    const { bars, frames, wall, older, heads } = this.layout;
    const box = new THREE.BoxGeometry(1, 1, 1);
    this.box = box;
    const zWall = bars[0]?.z ?? WIDE.bar.z;

    // The plinth the room stands on, the wall's glass, and the wall's rim of rails.
    const span = this.layout.bounds;
    const plinth = new THREE.Mesh(roundedSlab(span.maxX - span.minX + 2 * PLINTH.x, span.maxZ - span.minZ + 2 * PLINTH.z, 1.4, PLINTH.bevel), this.materials.plinth);
    plinth.scale.y = PLINTH.h;
    plinth.position.set(0, PLINTH.y, (span.maxZ + span.minZ) / 2);
    plinth.receiveShadow = true;
    plinth.userData.blocker = true;
    const back = new THREE.Mesh(roundedSlab(wall.w, wall.h, 0.6, 0.04), this.materials.panel);
    back.rotation.x = Math.PI / 2;
    back.scale.y = 0.22;
    back.position.set(wall.x, wall.y + wall.h / 2, wall.z);
    back.userData.unpickable = true;
    this.root.add(plinth, back);
    const t = 0.16;
    this.rim = boxes(this.root, box, this.materials.rail, [
      { x: wall.x - wall.w / 2, y: wall.y + wall.h / 2, z: wall.z + 0.1, w: t, h: wall.h, d: 0.5 },
      { x: wall.x + wall.w / 2, y: wall.y + wall.h / 2, z: wall.z + 0.1, w: t, h: wall.h, d: 0.5 },
      { x: wall.x, y: wall.y + wall.h, z: wall.z + 0.1, w: wall.w + t, h: t, d: 0.5 },
      { x: wall.x, y: wall.y + FOOT.y, z: wall.z + FOOT.z, w: wall.w + t, h: FOOT.h, d: FOOT.d },
    ]);
    this.rim.mesh.userData.unpickable = true;

    // Each column stands on a plank, its older part on a plank of its own; dividers keep the columns apart.
    const planks = [], dividers = [];
    const { col, gap } = WIDE.bar;
    for (const head of heads) {
      planks.push({ x: head.x, y: head.foot - PLANK.h / 2, z: zWall, w: col + gap * 0.6, h: PLANK.h, d: PLANK.d });
      if (head.olderFoot !== null) planks.push({ x: head.x, y: head.olderFoot - 0.03, z: zWall, w: col * 0.82, h: 0.06, d: PLANK.d * 0.8 });
    }
    const bands = new Map();
    for (const head of heads) bands.set(head.band, [...(bands.get(head.band) || []), head]);
    for (const group of bands.values()) {
      const top = Math.max(...group.map((head) => head.top)) + 0.3, foot = group[0].foot - PLANK.h;
      for (let n = 0; n <= group.length; n++) {
        const x = n === 0 ? group[0].x - (col + gap) / 2 : n === group.length ? group.at(-1).x + (col + gap) / 2 : (group[n - 1].x + group[n].x) / 2;
        dividers.push({ x, y: (top + foot) / 2, z: zWall - 0.05, w: 0.035, h: top - foot, d: PLANK.d * 0.9 });
      }
    }
    this.planks = boxes(this.root, box, this.materials.plank, planks);
    this.dividers = boxes(this.root, box, this.materials.plank, dividers);
    this.planks.mesh.userData.unpickable = this.dividers.mesh.userData.unpickable = true;
    this.planks.mesh.receiveShadow = true;

    // The wall: one set of instances for each form, so a thousand bars cost a handful of draws.
    const forms = { solid: [], band: [], design: [], empty: [] };
    bars.forEach((bar, index) => {
      const piece = bar.id ? library.piece(bar.id) : null;
      bar.index = index;
      bar.form = !piece ? "empty" : piece.where === "design" ? "design" : piece.where === "candidate" ? "band" : "solid";
      forms[bar.form === "band" ? "solid" : bar.form].push(bar);
      if (bar.form === "band") forms.band.push(bar);
    });
    const pickBar = (bar) => (bar?.id ? pageId(bar.id) : null);
    this.wall = {
      solid: new Instances(box, this.materials.slate, forms.solid.length, { pick: pickBar }),
      band: new Instances(box, this.materials.band, forms.band.length, { pick: pickBar }),
      design: new Instances(box, this.materials.glass, forms.design.length, { pick: pickBar }),
      empty: new Instances(box, this.materials.ghost, forms.empty.length),
    };
    this.barSlot = new Map(); // piece id -> [{ set, index }]
    for (const [name, list] of Object.entries(forms)) {
      list.forEach((bar, index) => {
        const item = name === "band" ? { ...bar, x: bar.x - bar.w / 2 + 0.1, w: 0.14, d: bar.d * 1.12 } : bar;
        this.wall[name].place(index, item);
        if (bar.id) this.barSlot.set(bar.id, [...(this.barSlot.get(bar.id) || []), { set: name, index }]);
      });
      this.wall[name].flush();
      this.wall[name].mesh.castShadow = name === "solid";
      this.root.add(this.wall[name].mesh);
    }
    this.wall.empty.mesh.userData.unpickable = true;
    this.designEdges = this.edgesOf(forms.design, this.materials.outline);

    // The racks: two uprights on feet, a top rail, a rail under every row, a dark socket for every
    // slot with its piece seated in it, and the inner model's block where a rack holds it.
    const panels = [], rails = [], sockets = [], cards = [], blocks = [], nexts = [];
    for (const frame of frames) {
      const id = pageId(frame.id);
      panels.push({ x: frame.x, y: frame.y + frame.h / 2, z: frame.z - 0.16, w: frame.w, h: frame.h, d: 0.05, id });
      const u = 0.16;
      rails.push(
        { x: frame.x - frame.w / 2, y: frame.y + frame.h / 2, z: frame.z, w: u, h: frame.h + 0.1, d: 0.34, id },
        { x: frame.x + frame.w / 2, y: frame.y + frame.h / 2, z: frame.z, w: u, h: frame.h + 0.1, d: 0.34, id },
        { x: frame.x, y: frame.y + frame.h, z: frame.z, w: frame.w + u, h: u, d: 0.34, id },
        { x: frame.x, y: frame.y + 0.02, z: frame.z, w: frame.w + u, h: u * 1.2, d: 0.42, id },
        { x: frame.x - frame.w / 2, y: frame.y - 0.06, z: frame.z + 0.05, w: u * 2.4, h: 0.12, d: 0.7, id },
        { x: frame.x + frame.w / 2, y: frame.y - 0.06, z: frame.z + 0.05, w: u * 2.4, h: 0.12, d: 0.7, id }
      );
      if (frame.block) blocks.push({ ...frame.block, z: frame.z + 0.03, d: 0.18, frame: frame.id, id: pageId(frame.block.id) });
      for (const row of frame.rows) {
        const all = [...row.slots, ...(row.next ? [row.next] : [])];
        if (all.length) {
          const left = Math.min(...all.map((slot) => slot.x - slot.w / 2)) - 0.08, right = Math.max(...all.map((slot) => slot.x + slot.w / 2)) + 0.08;
          // A rail under the slots of each row of the inner model; the operators' cards hang on one rail each in their column.
          if (frame.kind === "inner model") rails.push({ x: (left + right) / 2, y: row.y - all[0].h / 2 - 0.05, z: frame.z + 0.02, w: right - left, h: 0.05, d: 0.22, id });
        }
        for (const slot of row.slots) {
          sockets.push({ x: slot.x, y: slot.y, z: frame.z - 0.04, w: slot.w + 0.08, h: slot.h + 0.07, d: 0.08 });
          cards.push({ ...slot, z: frame.z + 0.05, d: 0.1, frame: frame.id, piece: slot.id });
        }
        if (row.next) {
          sockets.push({ x: row.next.x, y: row.next.y, z: frame.z - 0.04, w: row.next.w + 0.08, h: row.next.h + 0.07, d: 0.08 });
          nexts.push({ ...row.next, z: frame.z + 0.05 });
        }
      }
    }
    const pickFrame = (item) => item?.id || null;
    this.panels = boxes(this.root, box, this.materials.panel, panels, { pick: pickFrame });
    this.rails = boxes(this.root, box, this.materials.rail, rails, { pick: pickFrame });
    this.sockets = boxes(this.root, box, this.materials.socket, sockets);
    this.sockets.mesh.userData.unpickable = true;
    this.blocks = boxes(this.root, box, this.materials.rail, blocks, { pick: pickFrame });
    for (const card of cards) {
      const piece = library.piece(card.piece);
      card.form = piece?.where === "candidate" ? "band" : piece?.where === "design" ? "design" : "solid";
    }
    const cardBands = cards.filter((card) => card.form === "band");
    this.slots = boxes(this.root, box, this.materials.slate, cards, { pick: (card) => (card ? pageId(card.piece) : null) });
    this.slotBands = boxes(this.root, box, this.materials.band, cardBands.map((item) => ({ ...item, x: item.x - item.w / 2 + 0.09, w: 0.12, d: item.d * 1.2 })), { pick: (card) => (card ? pageId(card.piece) : null) });
    this.cardList = cards;
    this.cardBandList = cardBands;
    this.rails.mesh.castShadow = this.slots.mesh.castShadow = true;
    // The next free registry code: an empty socket, its number written in it (laws_marks.js).
    this.nextCount = nexts.length;

    // The older families: a strip of small closed boxes on the plinth's front edge.
    const thin = this.narrow ? 0.07 : WIDE.older.w;
    this.older = boxes(this.root, box, this.materials.rail, older.map((item) => ({ ...item, w: thin, h: WIDE.older.h, d: thin })), { pick: (item) => (item ? pageId(item.id) : null) });

    // The names the room carries: on the planks, on the wall's foot, beside the rows.
    this.plaques = plaquesOf(library, this.layout);
    this.plaqueMesh = null;

    // What is chosen: lit copies of the chosen bar and of every lit slot, that ease out with them and glow.
    const capacity = Math.max(1, bars.length);
    this.litBars = new Instances(box, this.materials.lit, capacity);
    this.litBars.mesh.count = 0;
    this.litSlots = new Instances(box, this.materials.lit, Math.max(1, cards.length + blocks.length + rails.length + 1));
    this.litSlots.mesh.count = 0;
    this.lines = new THREE.Group();
    this.lines.userData.unpickable = true;
    this.ring = new THREE.Mesh(new THREE.TorusGeometry(1, 0.045, 8, 48), this.materials.ring);
    this.ring.visible = false;
    for (const object of [this.litBars.mesh, this.litSlots.mesh, this.ring]) object.userData.unpickable = true;
    this.shine.add(this.litBars.mesh, this.litSlots.mesh, this.lines, this.ring);
    this.root.add(this.shine);
    this.lit = { bars: new Set(), cards: new Set(), blocks: new Set(), frame: null };
  }

  /** One set of line segments for the edges of many boxes. */
  edgesOf(items, material) {
    const points = [];
    const unit = new THREE.EdgesGeometry(this.box);
    const corners = unit.attributes.position;
    for (const item of items) {
      for (let index = 0; index < corners.count; index++) {
        points.push(item.x + corners.getX(index) * item.w, item.y + corners.getY(index) * item.h, item.z + corners.getZ(index) * item.d);
      }
    }
    unit.dispose();
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute("position", new THREE.Float32BufferAttribute(points, 3));
    const lines = new THREE.LineSegments(geometry, material);
    lines.userData.unpickable = true;
    lines.visible = items.length > 0;
    this.root.add(lines);
    return lines;
  }

  /** The names as one mesh, written in the page's colours: made again when the theme changes. */
  writePlaques() {
    if (this.plaqueMesh) {
      this.root.remove(this.plaqueMesh);
      this.plaqueMesh.geometry.dispose();
      this.plaqueMesh.material.map?.dispose();
      this.plaqueMesh.material.dispose();
    }
    this.plaqueMesh = plaqueMesh(this.plaques, this.palette || {});
    if (this.plaqueMesh) this.root.add(this.plaqueMesh);
  }

  // ------------------------------------------------------------ the lens interface

  has(id) {
    const name = engineId(id);
    return Boolean(name && (this.library.piece(name) || this.library.frame(name)));
  }

  describe(id) {
    return describePart(this.library, id);
  }

  entities() {
    return listSections(this.library).flatMap((section) => section.entities);
  }

  sections() {
    return listSections(this.library);
  }

  get pickRoots() {
    return [this.root];
  }

  chrome() {
    const counts = this.library.counts();
    const stamp = this.library.stamp;
    // The legend names every visual difference that is drawn now; a mark with nothing to show is left out.
    const shown = MARKS.filter((mark) => mark.when(this));
    const lit = this.lit || { bars: new Set(), cards: new Set(), blocks: new Set() };
    const count = {
      "laws-main": counts.where.main, "laws-candidate": counts.where.candidate, "laws-design": counts.where.design,
      "laws-older": this.layout.bars.filter((bar) => bar.id && bar.older).length, "laws-height": this.layout.heads.length,
      "laws-rack": this.layout.frames.length, "laws-slot": this.cardList.length, "laws-block": this.blocks.mesh.count, "laws-next": this.nextCount,
      "laws-older-family": this.older.mesh.count, "laws-found": this.library.pieces.filter((piece) => this.library.passes(piece, this.filter) && (!ISOLATES[this.isolate] || ISOLATES[this.isolate](piece))).length, "laws-empty": this.layout.bars.filter((bar) => !bar.id).length,
      "laws-chosen": lit.bars.size + lit.cards.size + lit.blocks.size,
    };
    return {
      card: {
        heading: "Laws library",
        find: { label: "Find a piece", placeholder: "Find a piece", value: this.filter.query },
        open: this.filter.box ? { label: `The pieces of the Engine view's ${this.library.inBox(this.filter.box)[0]?.box?.label || this.filter.box}`, count: this.library.inBox(this.filter.box).length } : null,
        // Only where a piece stands today: a choice that would show nothing is not offered.
        modes: { label: "Where it stands", options: [["all", "All"], ...WHERE.filter((item) => counts.where[item.id] > 0 || this.filter.where === item.id).map((item) => [item.id, item.short])], active: this.filter.where || "all" },
        marks: { label: "Family", options: [["all", "All families"], ...this.library.families.map((family) => [family.id, family.label])], active: this.filter.family || "all" },
        stats: [[counts.pieces, "pieces"], [counts.frames, "frames"], ...(counts.where.candidate ? [[counts.where.candidate, "on the landing candidate"]] : []), [counts.where.design, "named in a design note"]],
        text: `Read from the engine's code at main ${stamp.main.revision}${stamp.candidate ? ` and the landing candidate ${stamp.candidate.ref} ${stamp.candidate.revision}, not on main yet` : ""}. No level is shown that a record does not state.`,
        sources: [
          { name: "The engine's code", holds: "the pieces, their tables and contracts, and the models that declare them, read without running it (tools/extract_laws.py)", licence: "the project's own, MIT" },
          { name: "The viewer's records", holds: "the families, the units a law acts on (the protein inventory) and the Engine view's statuses with their sources", licence: "the project's own, MIT" },
        ],
      },
      legend: { title: "What the marks stand for", items: shown.map((mark) => ({ id: mark.id, label: mark.label, description: mark.description, count: count[mark.id] ?? 0, swatch: mark.id })), note: { swatch: "laws-room", text: LAWS_NOTE } },
      stamp: `Read at main ${stamp.main.revision}`,
    };
  }

  activate() {
    const { stage } = this;
    this.active = true;
    stage.scene.add(this.root);
    const bounds = this.layout.bounds;
    if (stage.sun) {
      stage.sun.castShadow = false;
      stage.sun.position.set(bounds.maxX * 0.7, bounds.maxY + 26, 34);
      stage.sun.target?.position.set(0, bounds.maxY / 3, 0);
    }
    // The page's look: studio reflections on the slate, glass and metal, filmic light, contact shade where bars meet planks.
    stage.dress?.(LAWS_LOOK);
    // The bloom's spread and floor as the stage had them, handed back on leaving (core/passes.js keeps them).
    const bloom = stage.finish?.bloom;
    this.bloomBefore ??= bloom ? { radius: bloom.radius, floor: bloom.floor } : {};
    stage.glow?.(this.shine, true);
    this.light();
    this.stopLook ??= stage.look?.onChange?.(() => this.active && this.light());
    // A lost context that comes back: the names are written again and sent again (laws_marks.js plaqueMesh).
    if (!this.stopRestore && stage.canvas?.addEventListener) {
      const restored = () => {
        this.plaqueMesh?.userData.repaint?.();
        stage.invalidate?.();
      };
      stage.canvas.addEventListener("webglcontextrestored", restored);
      this.stopRestore = () => stage.canvas.removeEventListener("webglcontextrestored", restored);
    }
    if (stage.rig) {
      stage.rig.limits = { minDistance: 3, maxDistance: 260, minPolar: 0.35, maxPolar: Math.PI / 2 - 0.02 };
      stage.rig.setView(this.homeView());
      // The viewer gives the room its insets after the view opens: the opening view is fitted again to them (see update).
      this.homeHeld = { insets: JSON.stringify(stage.insets || {}), until: now() + 2500 };
    }
    this.writePlaques();
    this.buildLabels();
    this.refresh();
  }

  light() {
    const { stage } = this;
    if (!stage.renderer || !stage.scene) return; // a stand-in stage has no renderer to prepare surroundings with
    const dark = stage.palette?.dark;
    const studio = stage.look?.on?.("reflections") ? (this.studio ??= makeStudio(stage.renderer)) : null;
    this.environment ??= makeEnvironment(stage.renderer);
    stage.scene.environment = studio || this.environment;
    stage.scene.environmentIntensity = dark ? 0.85 : 0.95;
    // A raking key light along the wall gives the bars and planks their edges; less fill, so the room has depth.
    if (stage.sky) stage.sky.intensity = dark ? 0.85 : 1.25;
    if (stage.sun) stage.sun.intensity = dark ? 2.1 : 1.9;
  }

  deactivate() {
    const { stage } = this;
    this.active = false;
    stage.setBloom?.(0, this.bloomBefore || {});
    stage.glow?.(this.shine, false);
    stage.dress?.({ rich: false }); // the other views keep the look they had
    stage.scene.remove(this.root);
    if (stage.scene) stage.scene.environment = null;
    stage.applyPalette?.();
    this.labels.clear();
  }

  /**
   * The opening view, fitted to the screen by projection: on a wide screen the whole library,
   * the wall, the racks and the older strip, nothing cut and no band left empty. On a tall
   * screen the whole wall, where the library's size shows and its names can be read; the racks
   * stand below it, and the camera goes to them when one is chosen.
   */
  homeView() {
    const { bounds, wall } = this.layout;
    const box = this.narrow
      ? new THREE.Box3(new THREE.Vector3(wall.x - wall.w / 2, wall.y - 0.3, wall.z), new THREE.Vector3(wall.x + wall.w / 2, wall.y + wall.h, wall.z + 0.7))
      : new THREE.Box3(new THREE.Vector3(bounds.minX - PLINTH.x / 2, PLINTH.y, bounds.minZ), new THREE.Vector3(bounds.maxX + PLINTH.x / 2, wall.y + wall.h, bounds.maxZ + PLINTH.z));
    return this.fitOnScreen(box, 0.04);
  }

  /**
   * A view that frames `box` in what the page's panels and cards leave of the screen
   * (stage.setInsets: right, bottom and left), as the stage centres the picture in it.
   */
  fitOnScreen(box, margin) {
    const { stage } = this, { right = 0, bottom = 0, left = 0 } = stage.insets || {};
    const width = stage.width || 1600, height = stage.height || 1000, fov = stage.camera?.fov || 34;
    const seen = Math.max(0.2, (height - bottom) / height);
    const narrowed = (2 * Math.atan(Math.tan((fov * Math.PI) / 360) * seen) * 180) / Math.PI;
    return fitView(box, { fov: narrowed, aspect: Math.max(0.3, (width - right - left) / Math.max(1, height - bottom)), ...VIEW, margin });
  }

  /** Rebuild for a tall or a wide screen when the stage turns from one to the other. */
  fitScreen() {
    const narrow = this.stage.width < this.stage.height * 0.9;
    if (narrow === this.narrow) return false;
    this.narrow = narrow;
    this.build();
    this.applyPalette(this.stage.palette || {});
    if (this.active) {
      this.stage.rig?.setView(this.homeView());
      this.writePlaques();
      this.buildLabels();
      this.refresh();
    }
    return true;
  }

  /** The page's labels are kept for what can be chosen by its name (the racks) and for the chosen piece; the room's names are written on it. */
  buildLabels() {
    const labels = this.labels;
    labels.clear();
    this.chosenLabel = null;
    for (const frame of this.layout.frames) {
      const short = this.narrow && frame.kind === "composition" ? this.library.frame(frame.id)?.short || frame.id : frame.id;
      labels.add({ id: pageId(frame.id), text: short, anchor: new THREE.Vector3(frame.x - frame.w / 2 + 0.2, frame.y + frame.h + 0.32, frame.z), priority: 600, kind: "part", lift: 2 });
    }
  }

  setSelection(id) {
    const next = id && this.has(id) ? id : null;
    if (next !== this.selected) {
      this.focused = null;
      if (next) this.homeHeld = null; // a choice ends the opening view's hold // a move asked for the last choice is not fitted again for this one
      const still = this.stage.reducedMotion;
      this.growth = still ? 1 : 0;
      this.running = still || !next ? 0 : RUNS * RUN;
      this.clock = 0;
    }
    this.selected = next;
    this.refresh();
  }

  setHover(id) {
    const next = id && this.has(id) ? id : null;
    if (next === this.hovered) return;
    this.hovered = next;
    this.refresh();
  }

  /** The legend's own choice (cells-isolate): the pieces drawn with that mark stand forward and the rest fade. Marks of the room and of the racks change nothing on the wall. */
  setIsolate(id) {
    this.isolate = ISOLATES[id] ? id : null;
    this.refresh();
  }


  /** The card's "Where it stands" (the view card's modes). */
  setMode(value) {
    this.filter.where = value && value !== "all" ? value : null;
    this.refresh();
    this.onChrome?.();
  }

  /** The card's "Family" (the view card's marks). */
  setMark(value) {
    const before = this.filter.family;
    this.filter.family = value && value !== "all" ? value : null;
    this.refresh();
    this.onChrome?.();
    // The camera goes to the family chosen, and back to the whole library when the choice is let go.
    if (this.active && this.filter.family && this.filter.family !== before) this.focusFamily(this.filter.family);
    else if (this.active && before && !this.filter.family && !this.selected) this.stage.rig?.flyTo?.(this.homeView(), 900);
  }

  /**
   * The door from an Engine view box (the viewer's openDoor, `value`): the pieces whose file that
   * box holds stand forward, and the camera goes to them. setFinding(null) lets them go.
   */
  setFinding(box) {
    const pieces = box ? this.library.inBox(box) : [];
    this.filter.box = pieces.length ? box : null;
    this.refresh();
    this.onChrome?.();
    if (!this.active || !pieces.length) return;
    const around = new THREE.Box3();
    for (const piece of pieces) {
      const point = this.barPoint(piece.id);
      if (point) around.expandByPoint(point.clone().addScalar(0.9)).expandByPoint(point.clone().addScalar(-0.9));
    }
    this.flyToBox(around, `box:${box}`);
  }

  /** The way back from what a door opened (the card's Close, Escape): true if there was one. */
  back() {
    if (!this.filter.box) return false;
    this.setFinding(null);
    return true;
  }

  /** A search of the wall: the pieces whose id, unit, file or family holds the words. */
  setQuery(text) {
    const before = Boolean(this.filter.query);
    this.filter.query = String(text || "");
    this.refresh();
    if (before !== Boolean(this.filter.query)) this.onChrome?.(); // the legend names what a search draws while one is set
  }

  /** A test of size only: the wall with empty slots to this many places in all (0 is the real list). */
  setSize(size) {
    this.size = Math.max(0, Number(size) || 0);
    this.build();
    this.applyPalette(this.stage.palette || {});
    if (this.active) this.buildLabels();
    this.refresh();
  }

  /** The ids of what passes the filters, in the wall's order: what the arrow keys step through. */
  order() {
    return this.library.pieces.filter((piece) => this.library.passes(piece, this.filter)).map((piece) => pageId(piece.id));
  }

  /** The next or previous piece of the order, from the one chosen: for the arrow keys. */
  step(direction = 1) {
    const order = this.order();
    if (!order.length) return null;
    const at = order.indexOf(this.selected);
    return order[at < 0 ? (direction > 0 ? 0 : order.length - 1) : (at + direction + order.length) % order.length];
  }

  /** What is lit now: the chosen piece's bar and every slot that declares it, or a chosen frame's pieces. */
  lights() {
    const name = engineId(this.selected);
    const piece = name ? this.library.piece(name) : null;
    const frame = name && !piece ? this.library.frame(name) : null;
    const bars = new Set(), cards = new Set(), blocks = new Set();
    if (piece) {
      bars.add(piece.id);
      for (const slot of this.library.slotsOf(piece.id)) {
        if (slot.block) blocks.add(`${slot.frame}|${slot.block}`);
        else cards.add(`${slot.frame}|${slot.row}|${slot.index}`);
      }
    }
    if (frame) {
      for (const id of this.library.piecesOf(frame.id)) bars.add(id);
      frame.rows.forEach((row, r) => row.pieces.forEach((_, index) => cards.add(`${frame.id}|${r}|${index}`)));
      if (frame.inner) blocks.add(`${frame.id}|${frame.inner}`);
    }
    return { piece, frame, bars, cards, blocks };
  }

  refresh() {
    const lit = this.lights();
    this.lit = lit;
    const isolate = ISOLATES[this.isolate];
    const quiet = this.filter.family || this.filter.where || this.filter.query || this.filter.box || isolate;
    const passes = (id) => !id || (this.library.passes(this.library.piece(id), this.filter) && (!isolate || isolate(this.library.piece(id))));
    const base = this.colours || {};
    // The wall: what is chosen slides out (its lit copy glows over it), what is found comes forward, the rest dims.
    for (const [name, set] of Object.entries(this.wall)) {
      set.items.forEach((bar, index) => {
        const chosen = Boolean(bar.id && lit.bars.has(bar.id));
        const pass = passes(bar.id);
        const shown = bar.id ? pass : !quiet;
        const tone = name === "band" ? base.band : name === "design" ? base.glass : name === "empty" ? base.ghost : base.slate;
        set.tint(index, chosen ? base.accent : shown ? tone : base.dim);
        // A design piece is an outline: it is coloured when chosen, and stays in its outline.
        set.target[index] = name === "design" ? 0 : chosen ? LIFT.chosen : bar.id && quiet && pass ? LIFT.found : 0;
      });
      if (set.mesh.instanceColor) set.mesh.instanceColor.needsUpdate = true;
    }
    // The racks' cards: a lit one comes out of its socket. In the light theme its face stays a
    // card (slate drawn toward the accent) and its edges shine; in the dark theme it shines whole.
    const face = this.palette?.dark ? base.accent : base.litFace;
    this.cardList.forEach((card, index) => {
      const chosen = lit.cards.has(`${card.frame}|${card.row}|${card.index}`);
      this.slots.tint(index, chosen ? face : passes(card.piece) ? (card.form === "design" ? base.glass : base.slate) : base.dim);
      this.slots.target[index] = chosen ? LIFT.slot : 0;
    });
    this.cardBandList.forEach((card, index) => {
      const chosen = lit.cards.has(`${card.frame}|${card.row}|${card.index}`);
      this.slotBands.tint(index, chosen ? (this.palette?.dark ? base.accent : base.band) : base.band);
      this.slotBands.target[index] = chosen ? LIFT.slot : 0;
    });
    this.blocks.items.forEach((block, index) => {
      const chosen = lit.blocks.has(`${block.frame}|${engineId(block.id)}`);
      this.blocks.tint(index, chosen ? face : base.rail);
      this.blocks.target[index] = chosen ? LIFT.slot : 0;
    });
    this.rails.items.forEach((rail, index) => this.rails.tint(index, lit.frame && engineId(rail.id) === lit.frame.id ? base.accent : base.rail));
    this.older.items.forEach((item, index) => this.older.tint(index, pageId(item.id) === this.selected ? base.accent : base.rail));
    for (const set of [this.slots, this.slotBands, this.blocks, this.rails, this.older]) if (set.mesh.instanceColor) set.mesh.instanceColor.needsUpdate = true;
    this.placeLit(lit);
    this.drawLines(lit);
    this.markChosen(lit);
    this.labelChosen(lit);
    // Bloom only while something is chosen, and only from what was marked: the chosen and its routes.
    const any = Boolean(lit.piece || lit.frame || (this.selected && this.has(this.selected)));
    const bloom = this.palette?.dark ? LAWS_BLOOM : LAWS_BLOOM_LIGHT;
    this.stage.setBloom?.(any && this.active ? bloom.strength : 0, { radius: bloom.radius, floor: bloom.floor });
    this.stage.invalidate?.();
  }

  /**
   * The lit copies: one over each chosen bar and each lit slot, a little larger, that ease out
   * with it. In the light theme a lit slot's copy stands behind the card, a little wider and
   * taller, so that only its edges shine round a face that can still be read; the chosen rack's
   * rails shine too. The dark theme keeps the whole card shining.
   */
  placeLit(lit) {
    const light = !this.palette?.dark;
    const bars = [];
    // A design piece keeps its glass outline when chosen: it is tinted, and only what has a bar of slate gets a lit copy.
    for (const id of lit.bars) for (const entry of this.barSlot.get(id) || []) if (entry.set === "solid") bars.push({ set: entry.set, index: entry.index });
    this.litBars.mesh.count = bars.length;
    this.litBars.links = bars;
    bars.forEach(({ set, index }, n) => {
      const bar = this.wall[set].items[index];
      this.litBars.offset[n] = this.wall[set].offset[index];
      this.litBars.target[n] = LIFT.chosen;
      this.litBars.place(n, { ...bar, w: bar.w * 1.02, h: bar.h * 1.06, d: bar.d * 1.04 });
    });
    const slots = [];
    this.cardList.forEach((card, index) => lit.cards.has(`${card.frame}|${card.row}|${card.index}`) && slots.push({ item: card, set: this.slots, index }));
    // A chosen older family: its box on the plinth.
    this.older.items.forEach((item, index) => pageId(item.id) === this.selected && slots.push({ item: { ...item, w: this.narrow ? 0.07 : WIDE.older.w, h: WIDE.older.h, d: this.narrow ? 0.07 : WIDE.older.w }, set: this.older, index, lift: 0 }));
    this.blocks.items.forEach((block, index) => lit.blocks.has(`${block.frame}|${engineId(block.id)}`) && slots.push({ item: block, set: this.blocks, index }));
    if (light && lit.frame) this.rails.items.forEach((rail, index) => engineId(rail.id) === lit.frame.id && slots.push({ item: rail, set: this.rails, index, lift: 0, whole: true }));
    this.litSlots.mesh.count = slots.length;
    slots.forEach(({ item, set, index, lift = LIFT.slot, whole = false }, n) => {
      this.litSlots.offset[n] = set.offset[index];
      this.litSlots.target[n] = lift;
      const rim = light && !whole && set !== this.older;
      this.litSlots.place(n, rim ? { ...item, w: item.w + RIM, h: item.h + RIM, d: item.d * 0.5, z: item.z - item.d * 0.25 - 0.01 } : whole ? { ...item, w: item.w + 0.02, h: item.h + 0.02, d: item.d + 0.02 } : { ...item, w: item.w * 1.02, h: item.h * 1.08, d: item.d * 1.1 });
    });
    for (const set of [this.litBars, this.litSlots]) set.flush();
  }

  /** Where a lit card or block stands, for its route. */
  slotPoint(key) {
    const [frameId, row, index] = key.split("|");
    if (index === undefined) {
      const block = this.blocks.items.find((item) => item.frame === frameId && engineId(item.id) === row);
      return block ? new THREE.Vector3(block.x, block.y, block.z + LIFT.slot + 0.1) : null;
    }
    const card = this.cardList.find((item) => item.frame === frameId && String(item.row) === row && String(item.index) === index);
    return card ? new THREE.Vector3(card.x, card.y, card.z + LIFT.slot + 0.06) : null;
  }

  barPoint(id) {
    const first = this.barSlot.get(id)?.[0];
    if (!first) return null;
    const bar = this.wall[first.set].items[first.index];
    return new THREE.Vector3(bar.x, bar.y, bar.z + bar.d / 2);
  }

  /** The routes: an arc from the chosen bar out toward the visitor and into each slot, as one glowing mesh. */
  drawLines(lit) {
    for (const child of [...this.lines.children]) {
      child.geometry.dispose();
      this.lines.remove(child);
    }
    const pairs = [];
    if (lit.piece) {
      const from = this.barPoint(lit.piece.id);
      if (from) for (const key of [...lit.cards, ...lit.blocks]) pairs.push([from.clone().add(new THREE.Vector3(0, 0, LIFT.chosen)), this.slotPoint(key)]);
    } else if (lit.frame) {
      // A rack: a route from each of its direct slots' pieces on the wall to the slot.
      lit.frame.rows.forEach((row, r) => row.pieces.forEach((id, index) => pairs.push([this.barPoint(id)?.add(new THREE.Vector3(0, 0, LIFT.chosen)), this.slotPoint(`${lit.frame.id}|${r}|${index}`)])));
    }
    this.routes = pairs.filter(([from, to]) => from && to);
    if (!this.routes.length) return;
    const curves = this.routes.map(([from, to]) => {
      const out = Math.max(1.8, from.distanceTo(to) * 0.26);
      return new THREE.CubicBezierCurve3(from, from.clone().add(new THREE.Vector3(0, 0.15, out)), to.clone().add(new THREE.Vector3(0, 0.8, out)), to);
    });
    const tubes = new THREE.Mesh(mergeTubes(curves, this.narrow ? 0.032 : 0.05), this.materials.line);
    tubes.userData.unpickable = true;
    this.lines.add(tubes);
    this.showGrowth();
  }

  showGrowth() {
    const uniforms = this.materials.line.uniforms;
    uniforms.grown.value = this.growth;
    uniforms.pulse.value = Math.min(1, this.running / FADE); // the running light fades into the steady glow
    uniforms.time.value = this.clock / RUN;
  }

  markChosen(lit) {
    const point = lit.piece ? this.barPoint(lit.piece.id) : null;
    this.ring.visible = Boolean(point);
    if (point) {
      this.ring.position.copy(point).add(new THREE.Vector3(0, 0, LIFT.chosen + 0.02));
      this.ring.scale.set(WIDE.bar.w * 0.64, Math.max(0.25, this.layout.pitch * 1.6), 1);
    }
  }

  labelChosen(lit) {
    if (this.chosenLabel) {
      this.labels.remove?.(this.chosenLabel);
      this.chosenLabel = null;
    }
    if (!this.active || !lit.piece) return;
    const point = this.barPoint(lit.piece.id);
    if (point) this.chosenLabel = this.labels.add({ id: this.selected, text: lit.piece.id, anchor: point.clone().add(new THREE.Vector3(0, 0, LIFT.chosen)), priority: 2000, kind: "part", lift: 10 });
  }

  /** A move toward what was chosen: a piece's column and the racks it plugs into, a rack and its pieces on the wall, or an older family's box. */
  focus(id) {
    const name = engineId(id);
    const frame = this.layout.frames.find((item) => item.id === name);
    const older = this.older.items.find((item) => item.id === name);
    // The whole of what is lit, and the chosen thing alone for when the whole cannot be seen beside the panel.
    const box = new THREE.Box3(), core = new THREE.Box3();
    let approach = false; // a rack is come up to: its own box
    const add = (point, pad = 0.6, into = box) => point && into.expandByPoint(point.clone().addScalar(pad)).expandByPoint(point.clone().addScalar(-pad));
    if (frame) {
      for (const into of [box, core]) {
        add(new THREE.Vector3(frame.x - frame.w / 2, frame.y, frame.z), 0.4, into);
        add(new THREE.Vector3(frame.x + frame.w / 2, frame.y + frame.h + 0.5, frame.z), 0.4, into);
      }
      for (const piece of this.library.piecesOf(frame.id)) add(this.barPoint(piece), 0.4);
      approach = true;
    } else if (older) {
      // The box among its neighbours on the plinth, with the racks behind it.
      add(new THREE.Vector3(older.x - 2.5, older.y, older.z), 0.4);
      add(new THREE.Vector3(older.x + 2.5, older.y + 1.6, older.z - 2), 0.4);
    } else {
      const point = this.barPoint(name);
      if (!point) return;
      const column = this.layout.heads.find((head) => head.family.id === this.library.piece(name)?.family);
      add(point, 0.9);
      if (column) add(new THREE.Vector3(column.x, column.foot - PLANK.h, point.z), 0.9);
      // Alone, a piece is seen in its family's column, among its neighbours.
      if (column) core.copy(this.familyBox(column.family.id));
      // Each slot whole, a block as wide as it is, so that none ends under the panel.
      for (const slot of this.library.slotsOf(name)) {
        const item = this.slotItem(slot.block ? `${slot.frame}|${slot.block}` : `${slot.frame}|${slot.row}|${slot.index}`);
        if (!item) continue;
        box.expandByPoint(new THREE.Vector3(item.x - item.w / 2 - 0.3, item.y - item.h / 2 - 0.3, item.z));
        box.expandByPoint(new THREE.Vector3(item.x + item.w / 2 + 0.3, item.y + item.h / 2 + 0.3, item.z + LIFT.slot + 0.2));
      }
    }
    this.flyToBox(box, id, core.isEmpty() ? null : core, approach);
  }

  /** The card or block a slot key names, with its place and size. */
  slotItem(key) {
    const [frameId, row, index] = key.split("|");
    if (index === undefined) return this.blocks.items.find((item) => item.frame === frameId && engineId(item.id) === row) || null;
    return this.cardList.find((item) => item.frame === frameId && String(item.row) === row && String(item.index) === index) || null;
  }

  /** A move toward a family's column, with its name and its neighbours: when the card's Family is chosen. */
  focusFamily(family) {
    const box = this.familyBox(family);
    if (!box.isEmpty()) this.flyToBox(box, `family:${family}`);
  }

  /** A family's column with its name and its neighbours on the shelf. */
  familyBox(family) {
    const box = new THREE.Box3();
    const at = this.layout.heads.findIndex((head) => head.family.id === family);
    if (at < 0) return box;
    const head = this.layout.heads[at], z = this.layout.bars[0]?.z ?? WIDE.bar.z;
    for (const other of this.layout.heads.filter((item, n) => item.band === head.band && Math.abs(n - at) <= 1)) {
      box.expandByPoint(new THREE.Vector3(other.x - WIDE.bar.col / 2, head.foot - PLANK.h - 0.7, z - 0.3));
      box.expandByPoint(new THREE.Vector3(other.x + WIDE.bar.col / 2, Math.max(head.top, head.foot + 2.4) + 0.4, z + 0.6));
    }
    return box;
  }

  /**
   * Fly to a box of the scene, fitted to what the panel leaves of the screen (stage.setInsets),
   * as the stage centres the picture beside it. The viewer sets the insets after it calls focus,
   * so a change of insets within the flight fits the move again (see update).
   */
  flyToBox(box, key, core = null, approach = false) {
    const { stage } = this, rig = stage.rig;
    if (!rig?.flyTo || box.isEmpty()) return;
    this.homeHeld = null; // a move asked for (a door, a family, a choice) ends the opening view's hold
    const fit = (which) => this.fitOnScreen(which, 0.08);
    const home = this.homeView(), far = home.distance * 1.15;
    // Where the whole cannot be seen beside the panel (a phone, a piece declared far apart), the chosen thing itself is.
    let view = fit(box);
    // A rack is come up to: its own box. A piece whose slots cannot all be seen beside the panel is seen among its neighbours.
    if (core && (approach || view.distance > far)) view = fit(core);
    // Never closer than a third of the opening view, never much farther: the room stays in view.
    view.distance = Math.min(far, Math.max(home.distance * 0.33, view.distance));
    rig.flyTo(view, 1100);
    this.focused = { key, box: box.clone(), core: core?.clone() ?? null, approach, insets: JSON.stringify(stage.insets || {}), until: now() + 1600 };
  }

  update(dt = 16) {
    if (this.stage.width && this.stage.height && this.fitScreen()) return true;
    // The panel opened, closed or changed its size while the camera was on its way: fit the move to what it leaves.
    const held = this.homeHeld, insets = JSON.stringify(this.stage.insets || {});
    if (held && !this.selected && now() < held.until && held.insets !== insets) {
      held.insets = insets;
      this.stage.rig?.setView?.(this.homeView());
    }
    const focused = this.focused;
    if (focused && now() < focused.until && focused.insets !== JSON.stringify(this.stage.insets || {})) this.flyToBox(focused.box, focused.key, focused.core, focused.approach);
    const still = this.stage.reducedMotion;
    const k = still ? 1 : Math.min(1, (dt / 1000) * 9);
    let moving = false;
    for (const set of [...Object.values(this.wall), this.slots, this.slotBands, this.blocks, this.litBars, this.litSlots]) moving = set.step(k) || moving;
    // The light runs along the routes a few times after a choice, then holds steady: it says which way a route goes, then rests.
    if (this.growth < 1) {
      this.growth = still ? 1 : Math.min(1, this.growth + dt / 1000 / GROW);
      moving = true;
    }
    if (this.running > 0) {
      if (still) this.running = 0;
      else {
        this.running = Math.max(0, this.running - dt / 1000);
        this.clock += dt / 1000;
        moving = true;
      }
    }
    if (this.routes.length) this.showGrowth();
    return moving;
  }

  applyPalette(palette) {
    this.palette = palette;
    const set = (name, value) => value && this.materials[name].color.set(value);
    set("panel", palette.plate);
    set("plinth", palette.dark ? palette.plate : palette.plateEdge);
    set("outline", palette.edge);
    set("ring", palette.accent);
    set("socket", palette.dark ? palette.bg : palette.edge);
    if (palette.accent) {
      this.materials.line.uniforms.colour.value.set(palette.accent);
      this.materials.lit.emissive.set(palette.accent);
    }
    // Instance colours multiply the material's, so the instanced sets keep a white material and carry their colours here.
    for (const name of ["slate", "band", "glass", "ghost", "rail", "plank"]) this.materials[name].color.set(0xffffff);
    const tone = (value) => new THREE.Color(value || "#888888");
    this.colours = {
      slate: tone(palette.ghost), band: tone(palette.fg), glass: tone(palette.plate), ghost: tone(palette.ghost), rail: tone(palette.plateEdge),
      accent: tone(palette.accent), dim: tone(palette.ghost).lerp(tone(palette.bg), 0.82), litFace: tone(palette.ghost).lerp(tone(palette.accent), 0.5),
    };
    const plank = tone(palette.plateEdge).lerp(tone(palette.ghost), 0.35);
    for (const room of [this.planks, this.dividers]) {
      for (let index = 0; index < room.mesh.count; index++) room.tint(index, plank);
      if (room.mesh.instanceColor) room.mesh.instanceColor.needsUpdate = true;
    }
    for (let index = 0; index < this.rim.mesh.count; index++) this.rim.tint(index, this.colours.rail);
    if (this.rim.mesh.instanceColor) this.rim.mesh.instanceColor.needsUpdate = true;
    if (this.active) this.writePlaques();
    this.refresh();
  }

  /** What one frame costs to draw, counted from the scene: draws and triangles of every visible thing. */
  cost() {
    let draws = 0, triangles = 0;
    this.root.traverseVisible((object) => {
      if (!(object.isMesh || object.isLine || object.isPoints)) return;
      const geometry = object.geometry;
      const instances = object.isInstancedMesh ? object.count : 1;
      if (instances === 0) return;
      draws += 1;
      if (object.isMesh) {
        const range = geometry.drawRange.count === Infinity ? (geometry.index ? geometry.index.count : geometry.attributes.position.count) : geometry.drawRange.count;
        triangles += (range / 3) * instances;
      }
    });
    return { draws, triangles: Math.round(triangles) };
  }

  dispose() {
    this.stopLook?.();
    this.stopRestore?.();
    this.stage.glow?.(this.shine, false);
    disposeTree(this.root);
    this.environment?.dispose?.();
    this.studio?.dispose?.();
  }
}
