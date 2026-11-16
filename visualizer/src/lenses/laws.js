// The Laws library: a view of its own (the user, 16 November 2026: "racjs", "a view of its
// own", "something cool and impressive"). A wall of every declared piece of the engine, a bar
// for each in its family's column, and in front of it the frames: each model with a slot row
// for every kind of piece it declares. Choose a piece and lines run from its bar to every slot
// that declares it; choose a frame and its pieces light on the wall.
//
// Drawn from data/laws/pieces.json (schema/LAWS_LIBRARY.md), read from the engine's code.
// Shape says where a piece stands: solid slate on main, slate with a dark band on the landing
// candidate, a glass outline when only a design note names it, faint for an empty slot (a
// test of size only). The accent marks only what is chosen or found. No colour is a status.

import * as THREE from "../three.js";
import { roundedSlab } from "../core/materials.js";
import { makeEnvironment, makeStudio } from "../core/environment.js";
import { disposeTree } from "../core/stage.js";
import { Library, WHERE, pageId, engineId } from "./laws_data.js";
import { describe as describePart, sections as listSections } from "./laws_card.js";
import { layoutOf, WIDE } from "./laws_layout.js";

/** The look this view asks of the stage (core/look.js): its slate and glass are natural colours, so filmic light suits them. */
export const LAWS_LOOK = { rich: true, filmic: true, exposure: 1.06, contact: true, reach: 0.55, shade: 0.55 };
const LIFT = { chosen: 0.55, found: 0.2, slot: 0.22 };
const GROW = 0.45; // seconds for a line to reach its slot

const dummy = new THREE.Object3D();
const colour = new THREE.Color();

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

export class LawsLens {
  constructor(stage, model, labels, library = model?.raw?.laws) {
    this.id = "laws";
    this.stage = stage;
    this.model = model;
    this.labels = labels;
    this.library = library instanceof Library ? library : new Library(library);
    this.root = new THREE.Group();
    this.selected = null; // a page id: a piece or a frame
    this.hovered = null;
    this.filter = { family: null, where: null, query: "" };
    this.size = 0; // a test of size only: empty slots on the wall
    this.narrow = false;
    this.active = false;
    this.growth = 1; // how far the lines to the chosen slots have grown, 0 to 1
    this.materials = this.makeMaterials();
    this.build();
    this.applyPalette(stage.palette || {});
  }

  // ------------------------------------------------------------ materials

  makeMaterials() {
    const standard = (options) => new THREE.MeshStandardMaterial({ roughness: 0.5, metalness: 0.05, ...options });
    const materials = {
      slate: standard({ roughness: 0.42, metalness: 0.12 }),
      band: standard({ roughness: 0.5 }),
      glass: new THREE.MeshPhysicalMaterial({ roughness: 0.12, metalness: 0, transparent: true, opacity: 0.16, clearcoat: 1, clearcoatRoughness: 0.08, depthWrite: false }),
      outline: new THREE.LineBasicMaterial({ transparent: true, opacity: 0.95 }),
      ghost: new THREE.MeshBasicMaterial({ transparent: true, opacity: 0.2, depthWrite: false }),
      panel: new THREE.MeshPhysicalMaterial({ roughness: 0.18, metalness: 0, transparent: true, opacity: 0.32, clearcoat: 1, clearcoatRoughness: 0.12, depthWrite: false, side: THREE.DoubleSide }),
      rail: standard({ roughness: 0.38, metalness: 0.35 }),
      plinth: standard({ roughness: 0.85 }),
      next: new THREE.LineDashedMaterial({ dashSize: 0.12, gapSize: 0.08, transparent: true, opacity: 0.9 }),
      // What is chosen carries a meaning: it stays out of filmic light and contact shade.
      line: new THREE.MeshBasicMaterial({ toneMapped: false }),
      ring: new THREE.MeshBasicMaterial({ toneMapped: false, transparent: true, opacity: 0.9 }),
    };
    for (const name of ["line", "ring", "ghost", "outline", "next"]) materials[name].userData.noContact = true;
    return materials;
  }

  // ------------------------------------------------------------ the picture

  build() {
    // A rebuild (another size, a turned screen) frees the old shapes; the materials are kept.
    this.root.traverse((object) => object.geometry?.dispose?.());
    for (const child of [...this.root.children]) this.root.remove(child);
    const library = this.library;
    this.layout = layoutOf(library, { size: this.size, narrow: this.narrow });
    const { bars, frames, wall, older } = this.layout;
    const box = new THREE.BoxGeometry(1, 1, 1);
    this.box = box;

    // The plinth under the frames, and the wall's glass behind the bars.
    const span = this.layout.bounds;
    const plinth = new THREE.Mesh(roundedSlab(span.maxX - span.minX + 3, span.maxZ - span.minZ + 2, 1.2, 0.05), this.materials.plinth);
    plinth.scale.y = 0.3;
    plinth.position.set(0, -0.32, (span.maxZ + span.minZ) / 2);
    plinth.receiveShadow = true;
    plinth.userData.blocker = true;
    const back = new THREE.Mesh(roundedSlab(wall.w, wall.h, 0.6, 0.04), this.materials.panel);
    back.rotation.x = Math.PI / 2;
    back.scale.y = 0.16;
    back.position.set(wall.x, wall.y + wall.h / 2, wall.z);
    back.userData.unpickable = true;
    this.root.add(plinth, back);

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
    // The design pieces' edges: one set of lines for all of them.
    this.designEdges = this.edgesOf(forms.design, this.materials.outline);

    // The frames: glass backs and slate rails, their slot cards, and the inner model's block.
    const panels = [], rails = [], cards = [], blocks = [], nexts = [];
    for (const frame of frames) {
      const id = pageId(frame.id);
      panels.push({ x: frame.x, y: frame.y + frame.h / 2, z: frame.z - 0.12, w: frame.w, h: frame.h, d: 0.06, id });
      const t = 0.12;
      rails.push(
        { x: frame.x - frame.w / 2, y: frame.y + frame.h / 2, z: frame.z, w: t, h: frame.h, d: 0.26, id },
        { x: frame.x + frame.w / 2, y: frame.y + frame.h / 2, z: frame.z, w: t, h: frame.h, d: 0.26, id },
        { x: frame.x, y: frame.y + frame.h, z: frame.z, w: frame.w + t, h: t, d: 0.26, id },
        { x: frame.x, y: frame.y, z: frame.z, w: frame.w + t, h: t * 1.3, d: 0.34, id }
      );
      if (frame.block) blocks.push({ ...frame.block, z: frame.z + 0.02, d: 0.16, frame: frame.id, id: pageId(frame.block.id) });
      for (const row of frame.rows) {
        for (const slot of row.slots) cards.push({ ...slot, z: frame.z + 0.04, d: 0.08, frame: frame.id, piece: slot.id });
        if (row.next) nexts.push({ ...row.next, z: frame.z + 0.04 });
      }
    }
    const pickFrame = (item) => item?.id || null;
    this.panels = new Instances(box, this.materials.panel, panels.length, { pick: pickFrame });
    this.rails = new Instances(box, this.materials.rail, rails.length, { pick: pickFrame });
    this.blocks = new Instances(box, this.materials.rail, blocks.length, { pick: pickFrame });
    this.cards = { solid: [], band: [], design: [] };
    for (const card of cards) {
      const piece = library.piece(card.piece);
      card.form = piece?.where === "candidate" ? "band" : piece?.where === "design" ? "design" : "solid";
    }
    const cardSolid = cards, cardBands = cards.filter((card) => card.form === "band");
    this.slots = new Instances(box, this.materials.slate, cardSolid.length, { pick: (card) => (card ? pageId(card.piece) : null) });
    this.slotBands = new Instances(box, this.materials.band, cardBands.length, { pick: (card) => (card ? pageId(card.piece) : null) });
    panels.forEach((item, index) => this.panels.place(index, item));
    rails.forEach((item, index) => this.rails.place(index, item));
    blocks.forEach((item, index) => this.blocks.place(index, item));
    cardSolid.forEach((item, index) => this.slots.place(index, item));
    cardBands.forEach((item, index) => this.slotBands.place(index, { ...item, x: item.x - item.w / 2 + 0.09, w: 0.12, d: item.d * 1.2 }));
    this.cardList = cardSolid;
    this.cardBandList = cardBands;
    for (const set of [this.panels, this.rails, this.blocks, this.slots, this.slotBands]) {
      set.flush();
      this.root.add(set.mesh);
    }
    this.rails.mesh.castShadow = this.slots.mesh.castShadow = true;
    // The next free registry code: a dashed outline where a new channel law would go.
    this.nextEdges = this.edgesOf(nexts.map((item) => ({ ...item, d: 0.06 })), this.materials.next, true);

    // The older families: a strip of small closed boxes on the plinth's front edge.
    const thin = this.narrow ? 0.07 : WIDE.older.w;
    this.older = new Instances(box, this.materials.rail, older.length, { pick: (item) => (item ? pageId(item.id) : null) });
    older.forEach((item, index) => this.older.place(index, { ...item, w: thin, h: WIDE.older.h, d: thin }));
    this.older.flush();
    this.root.add(this.older.mesh);

    // The lines to a chosen piece's slots, and the ring that marks it: made when something is chosen.
    this.lines = new THREE.Group();
    this.lines.userData.unpickable = true;
    this.root.add(this.lines);
    this.ring = new THREE.Mesh(new THREE.TorusGeometry(1, 0.05, 6, 40), this.materials.ring);
    this.ring.visible = false;
    this.ring.userData.unpickable = true;
    this.root.add(this.ring);
    this.lit = { bars: new Set(), cards: new Set(), blocks: new Set(), frame: null };
  }

  /** One set of line segments for the edges of many boxes. */
  edgesOf(items, material, dashed = false) {
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
    if (dashed) lines.computeLineDistances();
    lines.userData.unpickable = true;
    lines.visible = items.length > 0;
    this.root.add(lines);
    return lines;
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
    return {
      card: {
        heading: "Laws library",
        modes: { label: "Where it stands", options: [["all", "All"], ...WHERE.map((item) => [item.id, item.short])], active: this.filter.where || "all" },
        marks: { label: "Family", options: [["all", "All families"], ...this.library.families.map((family) => [family.id, family.label])], active: this.filter.family || "all" },
        stats: [[counts.pieces, "pieces"], [counts.frames, "frames"], ...(counts.where.candidate ? [[counts.where.candidate, "on the landing candidate"]] : []), [counts.where.design, "named in a design note"]],
        text: `Read from the engine's code at main ${stamp.main.revision}${stamp.candidate ? ` and the landing candidate ${stamp.candidate.ref} ${stamp.candidate.revision}, not on main yet` : ""}. No level is shown that a record does not state.`,
        sources: [
          { name: "The engine's code", holds: "the pieces, their tables and contracts, and the models that declare them, read without running it (tools/extract_laws.py)", licence: "the project's own, MIT" },
          { name: "The viewer's records", holds: "the families, the units a law acts on (the protein inventory) and the Engine view's statuses with their sources", licence: "the project's own, MIT" },
        ],
      },
      legend: {
        title: "Where it stands",
        items: WHERE.map((item) => ({ id: item.id, label: item.label, count: counts.where[item.id], swatch: `laws-${item.id}` })),
      },
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
      stage.sun.position.set(bounds.maxX * 0.6, bounds.maxY + 30, 40);
      stage.sun.target?.position.set(0, bounds.maxY / 3, 0);
    }
    // The page's look: studio reflections on the slate and glass, filmic light, contact shade where the bars meet the wall.
    stage.dress?.(LAWS_LOOK);
    this.light();
    this.stopLook ??= stage.look?.onChange?.(() => this.active && this.light());
    if (stage.rig) {
      stage.rig.limits = { minDistance: 4, maxDistance: 220, minPolar: 0.35, maxPolar: Math.PI / 2 - 0.02 };
      stage.rig.setView(this.homeView());
    }
    this.buildLabels();
    this.refresh();
  }

  light() {
    const { stage } = this;
    if (!stage.renderer || !stage.scene) return; // a stand-in stage has no renderer to prepare surroundings with
    const studio = stage.look?.on?.("reflections") ? (this.studio ??= makeStudio(stage.renderer)) : null;
    this.environment ??= makeEnvironment(stage.renderer);
    stage.scene.environment = studio || this.environment;
    stage.scene.environmentIntensity = stage.palette?.dark ? 0.7 : 0.85;
  }

  deactivate() {
    const { stage } = this;
    this.active = false;
    stage.dress?.({ rich: false }); // the other views keep the look they had
    stage.scene.remove(this.root);
    if (stage.scene) stage.scene.environment = null;
    stage.applyPalette?.();
    this.labels.clear();
  }

  homeView() {
    const { stage } = this;
    const { bounds } = this.layout;
    const camera = stage.camera;
    const aspect = camera?.aspect || stage.width / stage.height || 1.6;
    const half = Math.tan(((camera?.fov || 34) * Math.PI) / 360);
    const spanX = bounds.maxX - bounds.minX + 2, spanY = bounds.maxY - bounds.minY + 1.5;
    const distance = Math.max(spanY / (2 * half), spanX / (2 * half * aspect)) * 1.04 + 4;
    return { target: new THREE.Vector3(0, (bounds.maxY + bounds.minY) / 2, 0), distance, azimuth: 0.16, polar: 1.42 };
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
      this.buildLabels();
      this.refresh();
    }
    return true;
  }

  buildLabels() {
    const labels = this.labels;
    labels.clear();
    this.chosenLabel = null;
    const { heads, frames, older } = this.layout;
    const shelves = new Map();
    for (const head of heads) {
      labels.add({ text: head.family.short, anchor: new THREE.Vector3(head.x, head.y, this.layout.bars[0]?.z ?? WIDE.bar.z), priority: 300, kind: "layer", lift: 0 });
      const key = `${head.shelf}:${head.band}`;
      if (!shelves.has(key)) shelves.set(key, []);
      shelves.get(key).push(head);
    }
    for (const [key, group] of shelves) {
      if (group.length < 2) continue; // a shelf of one family is named by its family alone
      const shelf = this.library.shelfById.get(key.split(":")[0]);
      const x = (group[0].x + group.at(-1).x) / 2, top = Math.max(...group.map((head) => head.top));
      labels.add({ text: shelf?.label || key, anchor: new THREE.Vector3(x, top + 0.5, this.layout.bars[0]?.z ?? WIDE.bar.z), priority: 450, kind: "layer", lift: 4 });
    }
    for (const frame of frames) {
      labels.add({ id: pageId(frame.id), text: frame.id, anchor: new THREE.Vector3(frame.x - frame.w / 2 + 0.2, frame.y + frame.h + 0.35, frame.z), priority: 600, kind: "part", lift: 2 });
      if (frame.kind === "inner model") for (const row of frame.rows) labels.add({ text: row.label, anchor: new THREE.Vector3(row.x + 0.9, row.y, frame.z + 0.1), priority: 200, kind: "layer", lift: 0 });
    }
    if (older.length) labels.add({ text: `${older.length} older families: their laws are tables inside each family`, anchor: new THREE.Vector3(older[0].x, 0.9, older[0].z), priority: 250, kind: "layer", lift: 0 });
  }

  setSelection(id) {
    const next = id && this.has(id) ? id : null;
    if (next !== this.selected) this.growth = this.stage.reducedMotion ? 1 : 0;
    this.selected = next;
    this.refresh();
  }

  setHover(id) {
    const next = id && this.has(id) ? id : null;
    if (next === this.hovered) return;
    this.hovered = next;
    this.refresh();
  }

  setIsolate() {
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
    this.filter.family = value && value !== "all" ? value : null;
    this.refresh();
    this.onChrome?.();
  }

  /** A search of the wall: the pieces whose id, unit, file or family holds the words. */
  setQuery(text) {
    this.filter.query = String(text || "");
    this.refresh();
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
    const palette = this.palette || {};
    const lit = this.lights();
    this.lit = lit;
    const quiet = this.filter.family || this.filter.where || this.filter.query;
    const passes = (id) => !id || this.library.passes(this.library.piece(id), this.filter);
    const base = this.colours || {};
    // The wall: chosen in the accent, found pushed forward, the rest dimmed by the filters.
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
    // The frames' cards: the chosen slots in the accent and lifted.
    this.cardList.forEach((card, index) => {
      const key = `${card.frame}|${card.row}|${card.index}`;
      const chosen = lit.cards.has(key);
      this.slots.tint(index, chosen ? base.accent : passes(card.piece) ? (card.form === "design" ? base.glass : base.slate) : base.dim);
      this.slots.target[index] = chosen ? LIFT.slot : 0;
    });
    this.cardBandList.forEach((card, index) => {
      const chosen = lit.cards.has(`${card.frame}|${card.row}|${card.index}`);
      this.slotBands.tint(index, chosen ? base.accent : base.band);
      this.slotBands.target[index] = chosen ? LIFT.slot : 0;
    });
    this.blocks.items.forEach((block, index) => {
      const chosen = lit.blocks.has(`${block.frame}|${engineId(block.id)}`);
      this.blocks.tint(index, chosen ? base.accent : base.rail);
      this.blocks.target[index] = chosen ? LIFT.slot : 0;
    });
    this.rails.items.forEach((rail, index) => this.rails.tint(index, lit.frame && engineId(rail.id) === lit.frame.id ? base.accent : base.rail));
    this.older.items.forEach((item, index) => this.older.tint(index, pageId(item.id) === this.selected ? base.accent : base.rail));
    for (const set of [this.slots, this.slotBands, this.blocks, this.rails, this.older]) if (set.mesh.instanceColor) set.mesh.instanceColor.needsUpdate = true;
    this.drawLines(lit);
    this.markChosen(lit);
    this.labelChosen(lit);
    this.stage.invalidate?.();
  }

  /** Where a lit card or block stands, for its line. */
  slotPoint(key) {
    const [frameId, row, index] = key.split("|");
    if (index === undefined) {
      const block = this.blocks.items.find((item) => item.frame === frameId && engineId(item.id) === row);
      return block ? new THREE.Vector3(block.x, block.y, block.z + 0.1) : null;
    }
    const card = this.cardList.find((item) => item.frame === frameId && String(item.row) === row && String(item.index) === index);
    return card ? new THREE.Vector3(card.x, card.y, card.z + 0.06) : null;
  }

  barPoint(id) {
    const first = this.barSlot.get(id)?.[0];
    if (!first) return null;
    const bar = this.wall[first.set].items[first.index];
    return new THREE.Vector3(bar.x, bar.y, bar.z + bar.d / 2);
  }

  /** The lines that read at a glance: an arc from the chosen bar out toward the viewer and into each slot. */
  drawLines(lit) {
    for (const child of [...this.lines.children]) {
      child.geometry.dispose();
      this.lines.remove(child);
    }
    const pairs = [];
    if (lit.piece) {
      const from = this.barPoint(lit.piece.id);
      if (from) for (const key of [...lit.cards, ...lit.blocks]) pairs.push([from, this.slotPoint(key)]);
    } else if (lit.frame) {
      // A frame: a line from each of its direct slots to that piece's bar.
      lit.frame.rows.forEach((row, r) => row.pieces.forEach((id, index) => pairs.push([this.barPoint(id), this.slotPoint(`${lit.frame.id}|${r}|${index}`)])));
    }
    const radius = this.narrow ? 0.03 : 0.045;
    for (const [from, to] of pairs) {
      if (!from || !to) continue;
      const out = Math.max(1.6, from.distanceTo(to) * 0.22);
      const curve = new THREE.CubicBezierCurve3(from, from.clone().add(new THREE.Vector3(0, 0, out)), to.clone().add(new THREE.Vector3(0, 0.6, out)), to);
      const tube = new THREE.Mesh(new THREE.TubeGeometry(curve, 40, radius, 6, false), this.materials.line);
      tube.userData.unpickable = true;
      tube.userData.full = tube.geometry.index ? tube.geometry.index.count : tube.geometry.attributes.position.count;
      this.lines.add(tube);
    }
    this.showGrowth();
  }

  showGrowth() {
    for (const tube of this.lines.children) {
      const count = Math.ceil((tube.userData.full * this.growth) / 6) * 6;
      tube.geometry.setDrawRange(0, Math.max(0, Math.min(tube.userData.full, count)));
    }
  }

  markChosen(lit) {
    const point = lit.piece ? this.barPoint(lit.piece.id) : null;
    this.ring.visible = Boolean(point);
    if (point) {
      this.ring.position.copy(point).add(new THREE.Vector3(0, 0, LIFT.chosen + 0.02));
      this.ring.scale.setScalar(this.layout.bars[0] ? WIDE.bar.w * 0.62 : 1);
      this.ring.scale.y = Math.max(0.25, this.layout.pitch * 1.6);
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

  focus(id) {
    const rig = this.stage.rig;
    if (!rig?.flyTo) return;
    const name = engineId(id);
    const home = this.homeView();
    const frame = this.layout.frames.find((item) => item.id === name);
    const point = frame ? new THREE.Vector3(frame.x, frame.y + frame.h / 2, frame.z) : this.barPoint(name);
    if (!point) return;
    // Close enough to read the piece's lines, far enough to keep the frames it plugs into in view.
    rig.flyTo({ target: point.lerp(home.target, 0.55), distance: Math.min(rig.distance ?? home.distance, home.distance * 0.82) });
  }

  update(dt = 16) {
    if (this.stage.width && this.stage.height && this.fitScreen()) return true;
    const still = this.stage.reducedMotion;
    const k = still ? 1 : Math.min(1, (dt / 1000) * 9);
    let moving = false;
    for (const set of [...Object.values(this.wall), this.slots, this.slotBands, this.blocks]) moving = set.step(k) || moving;
    if (this.growth < 1) {
      this.growth = still ? 1 : Math.min(1, this.growth + dt / 1000 / GROW);
      this.showGrowth();
      moving = true;
    }
    return moving;
  }

  applyPalette(palette) {
    this.palette = palette;
    const set = (name, value) => value && this.materials[name].color.set(value);
    set("panel", palette.plate);
    set("plinth", palette.plate);
    set("outline", palette.edge);
    set("next", palette.edge);
    set("line", palette.accent);
    set("ring", palette.accent);
    // Instance colours multiply the material's, so the instanced sets keep a white material and carry their colours here.
    for (const name of ["slate", "band", "glass", "ghost", "rail"]) this.materials[name].color.set(0xffffff);
    const tone = (value) => new THREE.Color(value || "#888888");
    this.colours = {
      slate: tone(palette.ghost), band: tone(palette.fg), glass: tone(palette.plate), ghost: tone(palette.ghost), rail: tone(palette.plateEdge),
      accent: tone(palette.accent), dim: tone(palette.ghost).lerp(tone(palette.bg), 0.7),
    };
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
    disposeTree(this.root);
    this.environment?.dispose?.();
    this.studio?.dispose?.();
  }
}
