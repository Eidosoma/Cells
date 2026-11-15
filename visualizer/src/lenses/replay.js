// The experiments lens: one saved run, replayed. The sheet of cells is drawn from the
// run's own polygons. What cannot be seen is drawn onto it by quantity layers
// (schema/QUANTITY_LAYERS.md): each layer maps a record the run saved to a mark, and one
// layer holds each visual channel. As it opens, a cell is coloured and raised by its
// membrane voltage, as the replay always was. Seams between cells fill in as their
// junctions form, a frame marks a region the run's plan names (the disc), and a ring with
// an arrow marks each replacement as it happens.
//
// A layer that lives on a membrane is drawn on a close-up of one chosen cell's membrane: a
// piece of glass beside the sheet, tied to its cell, that follows the time of the replay
// and says what it is. It is there while a cell is chosen and such a layer is on.
//
// Where a run's view gives the spaces outside the cells (its outside nodes) tiles of their
// own, they lie flat beside the cells, never as prisms: a small world of one cell and its
// surroundings. A layer on the motion channel draws beads for what the run's saved totals
// say crossed a border between two records; the picture then states what one bead stands
// for and what time it keeps (rule 3). A run whose numbers are invented says "Example:
// invented numbers" on the picture for as long as it shows (rule 6).
//
// It shows what the run saved. Every step is a saved record and nothing is interpolated;
// a record the run does not count as valid is drawn grey, never as data. The class shown
// with a run is the one the experiment's own summary records: the viewer judges nothing.

import * as THREE from "../three.js";
import { disposeTree } from "../core/stage.js";
import { loadRun, loadPart } from "../replay/source.js";
import { Player } from "../replay/player.js";
import { Catalogue, RUN, CELL } from "../replay/catalogue.js";
import { Ramp, parse } from "../replay/ramp.js";
import { clock, display, niceDomain, number, rateDisplay } from "../replay/format.js";
import "../replay/trace.js";
import { MARKS } from "../layers/marks/index.js";
import { paint } from "../layers/marks/tint.js";
import { paintOutside } from "../layers/marks/fog.js";
import { SLOWS, statementOf, timeWords } from "../layers/marks/beads.js";
import { worldOf } from "../layers/world.js";
import { raise } from "../layers/marks/relief.js";
import { layersFor, readDeclarations, account, Switch, CHANNELS, CHANNEL_WORDS, STRENGTHS } from "../layers/layers.js";
import { Closeup, freeRect } from "../layers/closeup.js";
import { membranesOf } from "../layers/membrane.js";
import { ionColours } from "../layers/ions.js";
import declaredLayers from "../../data/layers/layers.json" with { type: "json" };
import ionTable from "../../data/layers/ions.json" with { type: "json" };

const INSET = 0.055; // each cell is drawn a little small, so cells read as separate tiles
const MARK_SECONDS = 45; // how long, in the run's time, a replacement stays marked
const RINGS = 6; // replacements marked at once
const LAYERS = "layers:shown"; // the panel that says what the layers show and what stands behind them
const BLOOM = { quiet: 0.6, bold: 1 }; // how strongly what flows shines, where the stage has a finishing pass for it
const LIGHT = new THREE.Vector2(-0.55, 0.83).normalize(); // where the side walls' shading comes from
const smooth = (t) => t * t * (3 - 2 * t);

export class ReplayLens {
  constructor(stage, model, labels) {
    this.id = "experiments";
    this.stage = stage;
    this.model = model;
    this.labels = labels;
    this.catalogue = new Catalogue(model.raw.replays);
    this.player = new Player();
    this.root = new THREE.Group();
    this.loaded = new Map(); // run id -> Run
    this.run = null;
    this.runId = this.catalogue.runs[0]?.id || null;
    this.recordId = "vm";
    this.selected = null; // a cell index of the run shown
    this.hovered = null;
    this.panel = null; // the id whose details are open: a run or a cell
    this.active = false;
    this.loading = false;
    this.error = null;
    this.token = 0;
    this.pendingTime = null;
    this.autoplayed = false;
    this.ink = new THREE.Color();
    this.ground = new THREE.Color();
    this.neutral = [0.6, 0.65, 0.7];
    // The layers: what is declared, which hold a channel, and for the run shown what it can feed.
    this.declarations = readDeclarations(declaredLayers, MARKS).layers;
    this.switch = new Switch();
    this.offers = []; // for the run shown: [{ layer, ok, why, parts, … }]
    this.drawn = new Map(); // the id of a layer that is on -> { layer, fed, mark }
    this.fetching = new Set(); // ids of layers whose records are on their way
    this.wanted = new Set(); // ids of layers the visitor switched on (kept across runs)
    this.off = new Set(); // channels the visitor switched off
    this.layerError = null; // { id, text }: a layer whose records could not be fetched
    // The close-up of a chosen cell's membrane, and the layers drawn on it.
    this.closeup = null;
    this.onMembrane = new Map(); // the id of a layer that lives on a membrane and is on -> { layer, fed, mark }
    this.memos = new Map(); // what a mark worked out once for the run shown (the scale of its arrows)
    this.slow = 1; // how much a layer on the motion channel is slowed: 1 is true speed
    this.glass = new THREE.Color();
    this.raised = new THREE.Color();
    this.ions = new Map(); // species id -> { css, colour } for the run shown and the theme
    this.setRamp(stage.palette);
    this.player.addEventListener("time", () => {
      this.draw();
      this.stage.invalidate();
      if (!this.player.playing) this.numbersMoved();
    });
    this.player.addEventListener("state", () => {
      this.stage.invalidate();
      this.numbersMoved();
    });
    this.ready = this.runId ? this.show(this.runId) : Promise.resolve();
  }

  // ------------------------------------------------------------ loading a run

  /** Show a run of the catalogue. Resolves when it is drawn, or when it has failed to load. */
  show(id) {
    if (this.pending?.id === id) return this.pending.promise; // already on its way
    const promise = this.load(id);
    this.pending = { id, promise };
    promise.finally(() => {
      if (this.pending?.promise === promise) this.pending = null;
    });
    return promise;
  }

  async load(id) {
    const entry = this.catalogue.byId.get(id);
    if (!entry) return;
    const token = ++this.token;
    this.runId = id;
    this.error = null;
    this.player.pause();
    if (this.loaded.has(id)) {
      this.open(this.loaded.get(id));
      await this.settling;
      return;
    }
    this.loading = true;
    this.clear();
    this.onChrome?.();
    try {
      const run = await loadRun(entry);
      this.loaded.set(id, run);
      if (token !== this.token) return; // another run was asked for meanwhile
      this.loading = false;
      this.open(run);
      await this.settling; // the records of a layer the run opens with are on their way
    } catch (error) {
      if (token !== this.token) return;
      this.loading = false;
      this.error = error.message;
      this.run = null;
      this.player.load(null);
      this.onChrome?.();
      this.onPanel?.();
      this.stage.invalidate();
    }
  }

  open(run) {
    this.clear();
    this.run = run;
    this.setIons();
    this.cells = run.sets.get("cell");
    const choices = this.cells ? run.recordsOn("cell").filter((record) => !record.quantised) : [];
    this.record = choices.find((record) => record.id === this.recordId) || choices.find((record) => record.id === "vm") || choices[0] || null;
    this.recordId = this.record?.id || this.recordId;
    if (this.cells?.geometry?.kind === "polygons" && this.record) this.buildSheet();
    else this.error = "This run has no sheet of cells the replay can draw.";
    if (this.selected !== null && !(this.selected < (this.cells?.ids.length || 0))) this.selected = null;
    this.player.load(run);
    if (this.pendingTime !== null) {
      this.player.seek(this.pendingTime);
      this.pendingTime = null;
    }
    if (this.active) this.enter();
    this.draw();
    this.onChrome?.();
    this.onPanel?.();
    this.stage.invalidate();
  }

  clear() {
    this.dropCloseup();
    this.memos.clear();
    for (const { mark } of this.drawn.values()) mark.dispose();
    this.drawn.clear();
    this.surface = null;
    this.offers = [];
    for (const child of [...this.root.children]) {
      this.root.remove(child);
      disposeTree(child);
    }
    this.sheet = null;
    this.run = null;
    this.hovered = null;
    if (this.active) this.labels.clear();
    this.tags = null;
  }

  // ------------------------------------------------------------ geometry

  /** Prisms from the cells' polygons, seams from the junctions, a frame per named region. */
  buildSheet() {
    const { vertices, faces } = this.cells.geometry;
    let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity;
    for (const [x, y] of vertices) {
      minX = Math.min(minX, x);
      maxX = Math.max(maxX, x);
      minY = Math.min(minY, y);
      maxY = Math.max(maxY, y);
    }
    const cx = (minX + maxX) / 2, cy = (minY + maxY) / 2;
    const point = (index) => [vertices[index][0] - cx, vertices[index][1] - cy];
    this.extent = Math.max(maxX - minX, maxY - minY) / 2;

    // Each cell: its corners pulled a little towards its middle.
    let area = 0, corners = 0;
    const cells = faces.map((face) => {
      const ring = face.map(point);
      let mx = 0, my = 0, twice = 0;
      ring.forEach(([x, y], k) => {
        const [nx, ny] = ring[(k + 1) % ring.length];
        mx += x;
        my += y;
        twice += x * ny - nx * y;
      });
      mx /= ring.length;
      my /= ring.length;
      area += Math.abs(twice) / 2;
      corners += ring.length;
      const inset = ring.map(([x, y]) => [mx + (x - mx) * (1 - INSET), my + (y - my) * (1 - INSET)]);
      return { face, ring, inset, centre: [mx, my], radius: Math.sqrt(Math.abs(twice) / 2 / Math.PI), height: 0, top: new THREE.Vector3(mx, 0, my) };
    });
    const pitch = Math.sqrt(area / cells.length); // about one cell across
    this.low = 0.2 * pitch;
    this.high = 0.78 * pitch;
    this.pitch = pitch;

    // One mesh for all the prisms. Per cell: a top fan (centre + corners), then four vertices per side wall.
    const total = corners * 5 + cells.length;
    const positions = new Float32Array(total * 3), colours = new Float32Array(total * 3), index = [];
    const faceCell = [];
    let at = 0;
    for (const [number_, cell] of cells.entries()) {
      const n = cell.inset.length;
      cell.start = at;
      positions.set([cell.centre[0], 0, cell.centre[1]], at * 3);
      cell.inset.forEach(([x, y], k) => positions.set([x, 0, y], (at + 1 + k) * 3));
      for (let k = 0; k < n; k++) {
        index.push(at, at + 1 + ((k + 1) % n), at + 1 + k);
        faceCell.push(number_);
      }
      at += n + 1;
      cell.walls = at;
      cell.shade = [];
      for (let k = 0; k < n; k++) {
        const [ax, ay] = cell.inset[k], [bx, by] = cell.inset[(k + 1) % n];
        // top a, top b, bottom b, bottom a
        positions.set([ax, 0, ay, bx, 0, by, bx, 0, by, ax, 0, ay], at * 3);
        index.push(at, at + 1, at + 2, at, at + 2, at + 3);
        faceCell.push(number_, number_);
        // The wall's outward direction decides how dark it is: a fixed, drawn light.
        const out = new THREE.Vector2((ax + bx) / 2 - cell.centre[0], (ay + by) / 2 - cell.centre[1]).normalize();
        cell.shade.push(0.6 + 0.26 * Math.max(0, out.dot(LIGHT)));
        at += 4;
      }
    }
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute("position", new THREE.BufferAttribute(positions, 3));
    geometry.setAttribute("color", new THREE.BufferAttribute(colours, 3));
    geometry.setIndex(index);
    geometry.boundingSphere = new THREE.Sphere(new THREE.Vector3(0, 0, 0), this.extent * 1.5 + this.high);
    // Unlit, so a cell's colour is exactly the legend's; the walls carry their own shading.
    const mesh = new THREE.Mesh(geometry, new THREE.MeshBasicMaterial({ vertexColors: true, side: THREE.DoubleSide }));
    mesh.frustumCulled = false;
    mesh.userData.pick = (hit) => CELL + faceCell[hit.faceIndex];
    this.root.add(mesh);

    // Seams: the strip between two joined cells, darker the further their junctions have formed.
    const junctions = this.run.sets.get("junction");
    const abundance = this.run.records.get("junction_abundance");
    let seams = null;
    if (junctions?.geometry?.kind === "links" && junctions.geometry.between === "cell") {
      const quads = [];
      junctions.geometry.ends.forEach(([a, b], link) => {
        const shared = cells[a].face.filter((vertex) => cells[b].face.includes(vertex));
        if (shared.length !== 2) return; // not neighbours in the drawing: nothing to draw between them
        const corner = (cell, vertex) => cell.inset[cell.face.indexOf(vertex)];
        quads.push({ a, b, link, points: [corner(cells[a], shared[0]), corner(cells[a], shared[1]), corner(cells[b], shared[1]), corner(cells[b], shared[0])] });
      });
      if (quads.length) {
        const seamPositions = new Float32Array(quads.length * 12), seamColours = new Float32Array(quads.length * 16), seamIndex = [];
        quads.forEach((quad, k) => {
          quad.points.forEach(([x, y], corner) => seamPositions.set([x, 0, y], (k * 4 + corner) * 3));
          seamIndex.push(k * 4, k * 4 + 1, k * 4 + 2, k * 4, k * 4 + 2, k * 4 + 3);
        });
        const seamGeometry = new THREE.BufferGeometry();
        seamGeometry.setAttribute("position", new THREE.BufferAttribute(seamPositions, 3));
        seamGeometry.setAttribute("color", new THREE.BufferAttribute(seamColours, 4));
        seamGeometry.setIndex(seamIndex);
        const seamMesh = new THREE.Mesh(seamGeometry, new THREE.MeshBasicMaterial({ vertexColors: true, transparent: true, depthWrite: false, side: THREE.DoubleSide }));
        seamMesh.frustumCulled = false;
        seamMesh.userData.unpickable = true;
        seamMesh.renderOrder = 2;
        this.root.add(seamMesh);
        seams = { quads, geometry: seamGeometry, record: abundance || null };
      }
    }

    // A frame over each region the run's plan names, at the height of the tallest cell.
    this.inkMaterial = new THREE.MeshBasicMaterial({ transparent: true, opacity: 0.92, side: THREE.DoubleSide });
    this.softMaterial = new THREE.MeshBasicMaterial({ transparent: true, opacity: 0.55, side: THREE.DoubleSide });
    // The spaces outside the cells, where the run's view gives them tiles, and the borders between all the tiles.
    const outside = this.buildOutside(vertices, point, pitch);
    const world = worldOf(this.run, [...cells.map((cell, number_) => ({ set: "cell", index: number_, face: cell.face, ring: cell.ring, centre: cell.centre })), ...(outside ? outside.tiles : [])]);
    const frames = [];
    for (const region of this.run.regions) {
      if (region.set !== "cell" || !region.indices.length) continue;
      const count = new Map();
      for (const cellIndex of region.indices) {
        const face = cells[cellIndex].face;
        face.forEach((vertex, k) => {
          const other = face[(k + 1) % face.length];
          const key = vertex < other ? `${vertex}:${other}` : `${other}:${vertex}`;
          count.set(key, (count.get(key) || 0) + 1);
        });
      }
      const edges = [...count].filter(([, times]) => times === 1).map(([key]) => key.split(":").map((vertex) => point(Number(vertex))));
      const frame = new THREE.Mesh(ribbon(edges, pitch * 0.07), this.inkMaterial);
      frame.position.y = this.high + pitch * 0.07;
      frame.userData.unpickable = true;
      frame.renderOrder = 3;
      this.root.add(frame);
      // Its name sits at the frame's far edge.
      const far = edges.flat().reduce((best, [x, y]) => (y < best[1] ? [x, y] : best), [0, Infinity]);
      frames.push({ region, mesh: frame, anchor: new THREE.Vector3(far[0], frame.position.y, far[1]) });
    }

    // Marks for replacements: a ring over the cell replaced and an arrow from the cell copied.
    const ring = new THREE.RingGeometry(0.8, 1, 40).rotateX(-Math.PI / 2);
    const arrow = arrowShape();
    this.marks = [];
    for (let k = 0; k < RINGS; k++) {
      const material = new THREE.MeshBasicMaterial({ transparent: true, depthTest: false, side: THREE.DoubleSide });
      const group = new THREE.Group();
      const ringMesh = new THREE.Mesh(ring, material), arrowMesh = new THREE.Mesh(arrow, material);
      group.add(ringMesh, arrowMesh);
      group.visible = false;
      group.userData.unpickable = true;
      group.renderOrder = 5;
      ringMesh.renderOrder = arrowMesh.renderOrder = 5;
      this.root.add(group);
      this.marks.push({ group, ring: ringMesh, arrow: arrowMesh, material });
    }

    // Outlines of the cell under the pointer and of the cell picked.
    this.hoverLine = new THREE.Mesh(new THREE.BufferGeometry(), this.softMaterial);
    this.pickLine = new THREE.Mesh(new THREE.BufferGeometry(), this.inkMaterial);
    for (const line of [this.hoverLine, this.pickLine]) {
      line.visible = false;
      line.userData.unpickable = true;
      line.renderOrder = 4;
      this.root.add(line);
    }
    this.outlined = { hover: null, pick: null };

    this.sheet = { cells, geometry, seams, frames };
    // What the layers' marks draw on (src/layers/marks/index.js).
    this.surface = { cells, geometry, links: seams ? seams.quads : [], pitch, low: this.low, high: this.high, extent: this.extent, root: this.root, outside, world };
    this.settleLayers();
    this.applyInk();
  }

  /**
   * The spaces outside the cells (the run's outside nodes), where its view gives each a tile:
   * flat on the ground beside the cells, with an edge of its own; a bath held at a fixed
   * composition has a double edge. They are never prisms, so that none reads as a cell. The
   * tiles share the cells' list of corners: that is how the border between two tiles is
   * found. Returns { set, tiles, geometry, level }, or null where the view gives them no place.
   */
  buildOutside(vertices, point, pitch) {
    const set = [...this.run.sets.values()].find((item) => (item.holds || item.id) === "outside node" && item.geometry?.kind === "polygons");
    const own = set?.geometry.vertices;
    if (!set || own.length !== vertices.length || own.some(([x, y], k) => x !== vertices[k][0] || y !== vertices[k][1])) return null;
    const level = pitch * 0.012; // just above the ground the prisms stand on
    let corners = 0;
    const tiles = set.geometry.faces.map((face, index) => {
      const ring = face.map(point);
      const mx = ring.reduce((sum, [x]) => sum + x, 0) / ring.length, my = ring.reduce((sum, [, y]) => sum + y, 0) / ring.length;
      corners += ring.length;
      return { set: set.id, index, face, ring, inset: ring.map(([x, y]) => [mx + (x - mx) * (1 - INSET), my + (y - my) * (1 - INSET)]), centre: [mx, my], held: set.reservoir?.[index] === true, top: new THREE.Vector3(mx, level, my) };
    });
    const positions = new Float32Array((corners + tiles.length) * 3), colours = new Float32Array((corners + tiles.length) * 3), index = [];
    let at = 0;
    for (const tile of tiles) {
      const n = tile.inset.length;
      tile.start = at;
      positions.set([tile.centre[0], level, tile.centre[1]], at * 3);
      tile.inset.forEach(([x, y], k) => positions.set([x, level, y], (at + 1 + k) * 3));
      for (let k = 0; k < n; k++) index.push(at, at + 1 + ((k + 1) % n), at + 1 + k);
      at += n + 1;
    }
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute("position", new THREE.BufferAttribute(positions, 3));
    geometry.setAttribute("color", new THREE.BufferAttribute(colours, 3));
    geometry.setIndex(index);
    const mesh = new THREE.Mesh(geometry, new THREE.MeshBasicMaterial({ vertexColors: true, side: THREE.DoubleSide }));
    mesh.frustumCulled = false;
    mesh.userData.unpickable = true;
    this.root.add(mesh);
    const edges = (rings) => rings.flatMap((ring) => ring.map((corner, k) => [corner, ring[(k + 1) % ring.length]]));
    const within = (tile, share) => tile.inset.map(([x, y]) => [tile.centre[0] + (x - tile.centre[0]) * share, tile.centre[1] + (y - tile.centre[1]) * share]);
    const band = new THREE.Mesh(ribbon([...edges(tiles.map((tile) => within(tile, 0.985))), ...edges(tiles.filter((tile) => tile.held).map((tile) => within(tile, 0.9)))], pitch * 0.03), this.softMaterial);
    band.position.y = level + pitch * 0.004;
    band.userData.unpickable = true;
    band.renderOrder = 2;
    this.root.add(band);
    return { set, tiles, geometry, level };
  }

  // ------------------------------------------------------------ layers

  /** An offer of the run shown: by a layer's id, or by the mark and the record it shows. */
  offer(id) {
    return this.offers.find((item) => item.layer.id === id) || null;
  }

  offerOf(mark, recordId) {
    return this.offers.find((item) => item.ok && item.layer.mark === mark && !item.quantity.derivation && item.source.id === recordId) || null;
  }

  /** What is drawn on a channel now: { layer, fed, mark }, or null. */
  markOn(channel) {
    return this.drawn.get(this.switch.holder(channel)) || null;
  }

  /**
   * For the run just opened: which layers it can feed, and which are on. A layer the
   * visitor switched on stays on in the next run that can feed it; as it opens, the sheet
   * is coloured by the record chosen and its height repeats that colour.
   */
  settleLayers() {
    const { run } = this;
    this.offers = layersFor(run, this.declarations, MARKS);
    const ready = this.offers.filter((item) => item.ok && !item.parts.length).map((item) => item.layer.id);
    this.switch.keep(ready);
    // A layer that says it opens a run (the secreted species, where the run names one) takes the colour as the
    // run opens, and the sheet then stays flat. Otherwise the sheet is coloured by the record chosen, and its
    // height repeats that colour, as the replay always was.
    const opening = !this.switch.holder("colour") && !this.off.has("colour") ? this.offers.find((item) => item.ok && item.layer.opens === true && item.layer.channels.includes("colour")) || null : null;
    if (opening && !opening.parts.length) this.switch.switchOn(opening.layer);
    if (!opening && !this.switch.holder("colour") && !this.off.has("colour")) {
      const tint = this.offerOf("tint", this.record.id);
      if (tint) this.switch.switchOn(tint.layer);
    }
    if (!opening && !this.switch.holder("height") && !this.off.has("height")) {
      const relief = this.offerOf("relief", (this.offer(this.switch.holder("colour"))?.source || this.record).id);
      if (relief) this.switch.switchOn(relief.layer);
    }
    this.buildMarks();
    // The records of a layer the run opens with, and of a layer that was on, come in files of their own: they are fetched now.
    const fetches = [];
    if (opening?.parts.length) fetches.push(this.setLayer(opening.layer.id, true, { silent: true }));
    for (const id of this.wanted) if (!this.switch.isOn(id) && this.offer(id)?.ok) fetches.push(this.setLayer(id, true, { silent: true }));
    this.settling = Promise.all(fetches);
  }

  /**
   * The colours a mark may use: the ramp of a magnitude, the tone of no value, the page's ink
   * and its ground, the colour of the page's membranes, and each ion's own colour.
   */
  colours() {
    const other = { css: "#888888", colour: this.ink };
    return {
      ramp: this.ramp, neutral: this.neutral, ink: this.ink, ground: this.ground, raised: this.raised, glass: this.glass, dark: this.dark,
      ion: (id) => (this.ions.get(id) || other).colour,
      ionCss: (id) => (this.ions.get(id) || other).css,
    };
  }

  /** The layers that are on and that this run feeds, in the order of the channels: [{ layer, fed, mark }], on the sheet or on a membrane. */
  layersOn() {
    return this.switch.on.map((id) => this.drawn.get(id) || this.onMembrane.get(id) || (this.offer(id)?.ok ? { layer: this.offer(id).layer, fed: this.offer(id), mark: null } : null)).filter(Boolean);
  }

  /** Whether a layer is drawn on a membrane, on the close-up of a chosen cell, and not on the sheet. */
  livesOnMembrane(fed) {
    return MARKS[fed.layer.mark]?.surface === "membrane";
  }

  /** Build the marks of the layers that are on, for the run shown. */
  buildMarks() {
    for (const { mark } of this.drawn.values()) mark.dispose();
    this.drawn.clear();
    if (!this.surface) return this.shine();
    const context = { surface: this.surface, run: this.run, scaleOf: (record) => this.scaleOf(record), shown: display, strength: this.switch.strength, colours: this.colours(), slow: () => this.slow, still: () => this.still(), ions: this.knownIons() };
    for (const id of this.switch.on) {
      const fed = this.offer(id);
      if (!fed?.ok || fed.parts.length || this.livesOnMembrane(fed)) continue;
      this.drawn.set(id, { layer: fed.layer, fed, mark: MARKS[fed.layer.mark].create({ ...context, layer: fed.layer, fed }) });
    }
    // What the tags, the panel and the chart speak of: the record that colours the sheet, or else the one that raises it.
    const lead = this.markOn("colour") || this.markOn("height");
    if (lead?.mark.record) {
      this.record = lead.mark.record;
      this.recordId = this.record.id;
    }
    this.tags = null; // a label of a mark may have come or gone
    this.buildCloseup();
  }

  // ------------------------------------------------------------ the close-up of a chosen cell's membrane

  /** The membrane the close-up shows for a cell: the cell's first, with how many it has; or null. */
  membraneOf(number_) {
    const membranes = this.run ? membranesOf(this.run) : null;
    const own = membranes && number_ !== null && number_ !== undefined ? membranes.of(number_) : [];
    return own.length ? { index: own[0], id: membranes.ids[own[0]], of: own.length } : null;
  }

  /**
   * Build the close-up, or take it down: it is there while a cell is chosen and a layer
   * that lives on a membrane is on, for a run that says which membrane lies on that cell.
   */
  buildCloseup() {
    this.dropCloseup();
    const on = this.surface && this.selected !== null ? this.switch.on.map((id) => this.offer(id)).filter((fed) => fed?.ok && !fed.parts.length && this.livesOnMembrane(fed)) : [];
    const membrane = on.length ? this.membraneOf(this.selected) : null;
    if (!on.length || !membrane) return this.shine();
    this.closeup = new Closeup({ root: this.root, colours: this.colours() });
    this.closeup.membrane = membrane;
    this.closeup.cell = this.selected;
    const memo = (key, make) => {
      if (!this.memos.has(key)) this.memos.set(key, make());
      return this.memos.get(key);
    };
    const context = { surface: this.closeup.surface, run: this.run, membrane: membrane.index, strength: this.switch.strength, colours: this.colours(), memo, slow: () => this.slow, still: () => this.still() };
    for (const fed of on) this.onMembrane.set(fed.layer.id, { layer: fed.layer, fed, mark: MARKS[fed.layer.mark].create({ ...context, layer: fed.layer, fed }) });
    this.tags = null;
    // Once the window has settled (a panel may be opening), the view makes room for the close-up if it has none.
    this.roomIn = 350;
    this.shine();
  }

  /** Whether nothing may move: the visitor asks for less motion, or the picture is a still one. */
  still() {
    return Boolean(this.stage.reducedMotion || this.stage.rig?.instant);
  }

  /** The species of the run shown that the page knows as ions (data/layers/ions.json): a bead of another species is a token of molecules. */
  knownIons() {
    // Where the run's view states each species' valence, a species with one is an ion; otherwise the page's own table of ions decides.
    const table = new Set(Object.keys(ionTable.colours || {})), valence = this.run?.constants.get("valence");
    return new Set((this.run?.sets.get("species")?.ids || []).filter((id, k) => (valence ? valence.at(0, k) !== 0 : table.has(id))));
  }

  /**
   * What flows may shine, where the stage has a finishing pass for it (bloom): the marks say
   * what shines, and the stage is asked. Beads and glows read without it. While a layer on
   * the motion channel shows, the look's own motion stands still (rule 12).
   */
  shine() {
    const { stage } = this;
    const all = [...this.drawn.values(), ...this.onMembrane.values()];
    const lit = this.active ? all.flatMap(({ mark }) => mark.shines || []) : [];
    for (const object of this.lit || []) if (!lit.includes(object)) stage.glow?.(object, false);
    for (const object of lit) if (!(this.lit || []).includes(object)) stage.glow?.(object, true);
    this.lit = lit;
    // The stage is shared with the other lenses: this one asks for bloom only while it is shown and something of its
    // own shines, and switches off only the bloom it switched on. The same goes for holding the look's motion still.
    if (lit.length) {
      stage.setBloom?.(BLOOM[this.switch.strength]);
      this.bloomed = true;
    } else if (this.bloomed) {
      stage.setBloom?.(0);
      this.bloomed = false;
    }
    const moving = this.active && all.some(({ layer }) => layer.channels.includes("motion"));
    if (moving && !this.holding) stage.decoration?.pause("layers");
    if (!moving && this.holding) stage.decoration?.resume("layers");
    this.holding = moving;
  }

  /**
   * Where the close-up has room neither above its cell nor below it, the view moves, at the
   * same distance and angle, until the cell stands where the close-up fits above it.
   */
  makeRoom() {
    const { closeup, stage } = this;
    if (!closeup || !this.active || !this.sheet) return;
    this.placeCloseup();
    const placed = closeup.placed;
    if (!placed || placed.fits) return;
    const rig = stage.rig;
    // A pixel's length in the scene, at the cell's own distance along the line of sight.
    const cell = this.sheet.cells[closeup.cell].top;
    const depth = cell.clone().sub(stage.camera.position).dot(stage.camera.getWorldDirection(new THREE.Vector3()));
    const perPixel = (2 * Math.max(depth, 1e-6) * Math.tan((stage.camera.fov * Math.PI) / 360)) / stage.height;
    const across = (placed.room.x - placed.cell.x) * perPixel, down = ((placed.room.y + 8 - placed.cell.y) * perPixel) / Math.max(0.2, Math.cos(rig.polar));
    // What is on the ground moves right on the screen when the view looks further left, and down when it looks further away.
    const right = new THREE.Vector3(Math.cos(rig.azimuth), 0, -Math.sin(rig.azimuth)), away = new THREE.Vector3(-Math.sin(rig.azimuth), 0, -Math.cos(rig.azimuth));
    rig.flyTo({ target: rig.target.clone().addScaledVector(right, -across).addScaledVector(away, down) }, 600);
  }

  dropCloseup() {
    for (const { mark } of this.onMembrane.values()) mark.dispose();
    this.onMembrane.clear();
    if (this.closeup) {
      this.closeup.dispose();
      this.closeup = null;
      this.tags = null;
    }
  }

  /** What the close-up says of itself: the membrane and the cell, the time, the run, and what its numbers are worked out from. */
  closeupCaption() {
    const { closeup, run } = this;
    const entry = this.catalogue.byId.get(this.runId);
    const name = this.cells.ids[closeup.cell];
    const which = closeup.membrane.of > 1 ? `Membrane ${closeup.membrane.id}, one of ${closeup.membrane.of} of ${name}` : `Membrane of ${name}`;
    // The inputs of every layer drawn on it, each once: the saved ones, then the definition's.
    const saved = [], stated = [];
    for (const { fed } of this.onMembrane.values()) {
      for (const input of Object.values(fed.inputs || {})) {
        const list = input.how === "constant" ? stated : saved;
        const words = SHORT[input.part] || input.says;
        if (!list.includes(words)) list.push(words);
      }
      // A rate of saved totals has no parts: it is worked out from the totals themselves.
      if (fed.sources && !saved.includes("totals")) saved.push("totals");
    }
    const list = (items) => (items.length > 1 ? `${items.slice(0, -1).join(", ")} and ${items[items.length - 1]}` : items[0] || "");
    const from = [saved.length ? `the saved ${list(saved)}` : "", stated.length ? `the ${list(stated)} of the run's definition` : ""].filter(Boolean).join(", with ");
    // On a wide window the close-up also says what its signs are; on a narrow one the legend alone does, to keep the card low.
    const notes = this.stage.width >= 760 ? [...this.onMembrane.values()].map(({ mark }) => mark.note?.(number)).filter(Boolean) : [];
    // What a motion layer must state on the picture itself (rule 3), and that an example's numbers are invented (rule 6): on a window of any width.
    const flow = [...this.onMembrane.values()].map(({ mark }) => this.statement(mark)).filter(Boolean);
    return [...(run.example ? [run.example.says] : []), `${which} at ${clock(this.player.time, { precise: true })}`, this.catalogue.title(entry), ...flow, `Worked out by the viewer from ${from}.`, ...notes].join("\n");
  }

  /** What a mark on the motion channel states on the picture: what one bead stands for, the time it keeps, the interval its rate is a mean over. */
  statement(mark) {
    if (!mark?.interval || mark.token === undefined) return null;
    return statementOf({ token: mark.token, what: mark.what || "ion", slow: this.slow, interval: mark.interval(), clock: (seconds) => clock(seconds, { precise: true }), still: this.still() });
  }

  /** Place the close-up for the frame about to be drawn: in the free part of the window, by its cell. */
  placeCloseup() {
    const { closeup, stage } = this;
    if (!closeup || !this.active || !this.sheet) return;
    const cell = this.sheet.cells[closeup.cell];
    if (!cell) return;
    const blocked = this.labels.blocked ? this.labels.blocked() : [];
    const key = `${stage.width}x${stage.height}:${blocked.map((box) => [box.left, box.top, box.right, box.bottom].map(Math.round).join(",")).join(";")}`;
    if (this.freeKey !== key) {
      this.freeKey = key;
      this.free = freeRect(stage.width, stage.height, blocked, this.labels.keepClear?.top || 0);
    }
    closeup.place(stage, cell.top, this.free);
  }

  /**
   * The numbers on the chosen cell's membrane at the record shown, for the panel: one item
   * for each ion with its three terms and the way each drives the ion, and one for the charge.
   */
  membraneNumbers() {
    if (!this.closeup || !this.run) return null;
    const step = this.player.index, valid = this.run.isValid(step);
    const items = [];
    const way = (drive) => (drive === "out" ? "out of the cell" : drive === "in" ? "into the cell" : "neither way");
    const mv = (volts) => `${number(volts * 1000, 1)} mV`;
    for (const { layer, mark } of this.onMembrane.values()) {
      if (!valid) continue;
      if (layer.mark === "arrows") {
        mark.at(step).forEach((term, k) => {
          const id = mark.species[k];
          if (!term) return items.push({ label: id, detail: "no value at this record" });
          items.push({
            label: `${id}, valence ${number(term.valence, 0)}`,
            detail: `${number(term.inside, 2)} mM inside, ${number(term.outside, 2)} mM outside`,
            lines: [
              `Push of the concentration difference: ${mv(term.size.concentration)} ${way(term.drives.concentration)}`,
              `Pull of the voltage (${mv(term.voltage)}): ${mv(term.size.electrical)} ${way(term.drives.electrical)}`,
              term.size.sum < 0.001 ? `What is left: ${number(term.size.sum * 1000, 2)} mV, in balance` : `What is left: ${mv(term.size.sum)} ${way(term.drives.sum)}`,
            ],
          });
        });
        for (const item of mark.missing) items.push({ label: item.id, detail: `Not drawn: this run did not save ${item.lacks}.` });
      }
      if (layer.mark === "beads") {
        const interval = mark.interval();
        if (!interval) items.push({ label: "Ion traffic", detail: "No rate at the run's first record: a rate is a mean between two records." });
        else items.push(...mark.readings().map((reading) => this.flowItem(reading, interval, mark.token, "ion")));
      }
      if (layer.mark === "stipple") {
        const charge = mark.at(step);
        const whole = Math.round(charge.charges).toLocaleString("en-US");
        items.push({
          label: "Charge",
          detail: `${number(charge.coulombs * 1e12, 3)} pC at the inner face`,
          lines: [
            `Capacitance ${number(charge.capacitance * 1e12, 3)} pF times voltage ${mv(charge.voltage)}: ${whole} charges on the whole membrane of ${number(charge.area * 1e12, 1)} square micrometres`,
            `${Math.round(charge.per_um2).toLocaleString("en-US")} charges on each square micrometre; ${number(charge.on_piece, 1)} on the piece drawn (${mark.piece.width_nm} nm by ${mark.piece.depth_nm} nm), so ${charge.marks} ${charge.inside === "plus" ? "plus" : "minus"} marks stand at the inner face and as many of the other sign at the outer face`,
          ],
        });
      }
    }
    const title = this.player.playing ? "On its membrane (pause to read a moment)" : `On its membrane at ${clock(this.player.time, { precise: true })}`;
    if (this.player.playing) return { title, items: [{ label: "The run is playing", detail: "The numbers of a moment are given when the run is paused." }] };
    if (!valid) return { title, items: [{ label: "Not a valid record", detail: "The run does not count this record as valid: nothing is worked out from it." }] };
    return { title, items, note: "Worked out by the viewer from this run's saved records and its definition; the panel on what the layers show says how." };
  }

  /**
   * One stream of beads, or one glowing element, as the panel gives it: the two saved totals,
   * the time between, the mean rate, and what that is on the picture. Enough to check by hand.
   */
  flowItem(reading, interval, token, what) {
    const at = (seconds) => clock(seconds, { precise: true });
    const total = display({ unit: reading.unit, range: [reading.before, reading.now], dtype: "float32" });
    const totals = `${number(reading.before * total.factor, 4)} ${total.unit} at ${at(interval[0])}, ${number(reading.now * total.factor, 4)} ${total.unit} at ${at(interval[1])}: the difference over ${number(reading.seconds, 3)} s`;
    // The rate reads in the unit of the two totals, a second: the three numbers of an item can then be checked against each other.
    const whole = rateDisplay(reading.unit, 1), speed = { factor: total.factor, unit: /W$/.test(whole.unit) ? `${total.unit.charAt(0)}W` : `${total.unit} a second` };
    const per = reading.per !== undefined && reading.per !== 1 ? ` (the pump's cycles times ${number(Math.abs(reading.per), 0)}, what one cycle moves of it)` : "";
    const label = reading.share !== undefined ? `${reading.name} · ${lower(reading.label)}` : [reading.name, reading.species].filter(Boolean).join(" · ");
    if (reading.reset) return { label, detail: "no rate in this interval", lines: [totals, "A slot was retired in this interval, and its total restarted at nought: the difference is the operator's booking, not a flow, and no rate is taken across it."] };
    if (reading.share !== undefined) {
      // A glow: a power, and how far up the scale it stands.
      return { label, detail: reading.mean ? `${number(reading.mean * speed.factor, 3)} ${speed.unit}` : "nothing in this interval", lines: [totals, reading.mean ? `${number(reading.share * 100, 0)} in a hundred of the brightest glow` : null].filter(Boolean) };
    }
    if (!reading.mean) return { label, detail: "nothing in this interval", lines: [totals] };
    const way = reading.way || `from ${reading.from} to ${reading.to}`;
    const each = Math.round(reading.particles).toLocaleString("en-US");
    return { label, detail: `${number(Math.abs(reading.mean) * speed.factor, 3)} ${speed.unit} ${way}${per}`, lines: [totals, `${each} ${what}s a second; one bead is ${token.toLocaleString("en-US")}, so ${number(reading.beads, 2)} beads a second pass${this.slow > 1 ? `, slowed ${this.slow.toLocaleString("en-US")} times` : ""}`] };
  }

  /**
   * The numbers behind what flows on the sheet at the record shown, for the panel: one
   * section for the beads that cross its borders, one for what glows.
   */
  flowNumbers() {
    if (!this.run || !this.sheet) return [];
    const sections = [];
    const at = (seconds) => clock(seconds, { precise: true });
    for (const channel of ["motion", "glow"]) {
      const drawn = this.markOn(channel);
      if (!drawn?.mark.readings || !drawn.mark.interval) continue;
      const name = lower(this.layerLabel(drawn.fed)), interval = drawn.mark.interval();
      if (this.player.playing) sections.push({ title: `${capital(name)} (pause to read a moment)`, items: [{ label: "The run is playing", detail: "The numbers of a moment are given when the run is paused." }] });
      else if (!this.run.isValid(this.player.index)) sections.push({ title: capital(name), items: [{ label: "Not a valid record", detail: "The run does not count this record as valid: nothing is worked out from it." }] });
      else if (!interval) sections.push({ title: `${capital(name)} at ${at(this.player.time)}`, items: [{ label: "No rate yet", detail: "This is the run's first record: a rate is a mean between two records." }] });
      else {
        const readings = drawn.mark.readings();
        // What moved or glowed is listed, and so is what has no rate because its total restarted; the rest is counted.
        const moving = readings.filter((reading) => reading.mean || reading.reset), idle = readings.length - moving.length;
        const items = moving.map((reading) => this.flowItem(reading, interval, drawn.mark.token, drawn.mark.what || "ion"));
        if (idle) items.push({ label: `${idle} more`, detail: channel === "motion" ? "Nothing crossed in this interval." : "Nothing was dissipated in this interval." });
        if (!readings.length) items.push({ label: "Nothing", detail: channel === "motion" ? "No saved total of this run ever changes on a border this picture draws." : "No ledger of this run ever grows." });
        sections.push({ title: `${capital(name)}, a mean from ${at(interval[0])} to ${at(interval[1])}`, items, note: "Each number is the saved total at one record less the total at the record before, divided by the time between: worked out by the viewer." });
      }
    }
    return sections;
  }

  /** The numbers the panel gives are those of one moment: when the playhead rests elsewhere, the panel is written again. */
  numbersMoved() {
    if (!this.active) return;
    if (this.panel === LAYERS && (this.closeup || this.markOn("motion") || this.markOn("glow"))) return this.onPanel?.();
    if (this.closeup && this.panel === CELL + this.closeup.cell) this.onPanel?.();
  }

  /**
   * Switch a layer on or off. Switching one on takes its channels from the layers that
   * held them. Records that come in a file of their own are fetched first; the promise
   * settles when the layer is drawn, or when its records could not be fetched.
   */
  async setLayer(id, on = true, { silent = false } = {}) {
    const fed = this.offer(id);
    if (!fed || !this.run) return;
    if (!on) {
      this.wanted.delete(id);
      for (const channel of fed.layer.channels) this.off.add(channel);
      this.switch.switchOff(id);
      return this.layersChanged();
    }
    if (!fed.ok) return;
    if (!silent) this.wanted.add(id);
    for (const channel of fed.layer.channels) this.off.delete(channel);
    if (fed.parts.length) {
      const run = this.run;
      this.fetching.add(id);
      this.layerError = null;
      this.onChrome?.();
      try {
        await Promise.all(fed.parts.map((part) => loadPart(run, part)));
      } catch (error) {
        this.fetching.delete(id);
        if (run === this.run) {
          this.layerError = { id, text: `Its records could not be fetched: ${error.message}` };
          this.onChrome?.();
        }
        return;
      }
      this.fetching.delete(id);
      if (run !== this.run) return; // another run was opened meanwhile
      this.offers = layersFor(run, this.declarations, MARKS);
    }
    const now = this.offer(id);
    if (!now?.ok || now.parts.length) return;
    for (const evicted of this.switch.switchOn(now.layer)) this.wanted.delete(evicted);
    return this.layersChanged();
  }

  /** Switch on exactly the layers named ("voltage-relief,junction-drops"), beside the colouring. */
  async setLayers(list) {
    const ids = String(list || "").split(",").map((id) => id.trim()).filter(Boolean);
    for (const id of ids) await this.setLayer(id.replace(/^-/, ""), !id.startsWith("-"));
  }

  /** Draw the marks quiet or bold. */
  setStrength(value) {
    if (!STRENGTHS.includes(value) || value === this.switch.strength) return;
    this.switch.setStrength(value);
    for (const { mark } of [...this.drawn.values(), ...this.onMembrane.values()]) mark.setStrength?.(value);
    this.shine();
    this.tags = null;
    this.draw();
    this.onChrome?.();
    this.stage.invalidate();
  }

  layersChanged() {
    this.buildMarks();
    this.draw();
    this.onChrome?.();
    this.onPanel?.();
    this.stage.invalidate();
  }

  /** The limits a record is drawn between: round numbers around its range, in the unit shown. */
  scaleOf(record) {
    const shown = display(record);
    if (!record.dtype.startsWith("float")) {
      // A count: whole steps from zero to the most the run reaches.
      return { shown, low: 0, high: Math.max(1, record.range[1]), steps: Math.max(1, Math.round(record.range[1])) };
    }
    // An experiment may give a record one scale for all its runs, so a value has the same
    // colour in each of them. A run that reaches beyond it widens the scale.
    const experiment = this.catalogue.experimentOf(this.catalogue.byId.get(this.runId));
    const common = experiment?.records?.[record.id]?.shown_between;
    if (common && record.range[0] >= common[0] && record.range[1] <= common[1]) {
      // The experiment's limits are used as given: they are already round in the unit shown.
      const low = common[0] * shown.factor, high = common[1] * shown.factor;
      return { shown, low: common[0], high: common[1], nice: { low, high, step: (high - low) / 8 } };
    }
    const low = common ? Math.min(common[0], record.range[0]) : record.range[0];
    const high = common ? Math.max(common[1], record.range[1]) : record.range[1];
    const nice = niceDomain(low * shown.factor, high * shown.factor);
    return { shown, low: nice.low / shown.factor, high: nice.high / shown.factor, nice };
  }

  // ------------------------------------------------------------ drawing a moment

  /** Draw the run as it was at the playhead: the last record saved at or before it. */
  draw() {
    const { run, sheet, surface } = this;
    if (!run || !sheet || !surface) return;
    const step = this.player.index;
    const valid = run.isValid(step);
    // Each channel is drawn by the layer that holds it: the heights first, since what lies
    // on the sheet stands on them. With no layer on a channel the sheet is flat, or of one tone.
    const height = this.markOn("height"), colour = this.markOn("colour");
    if (height) height.mark.update(step, valid);
    else raise(surface, () => this.low);
    // The spaces outside the cells wear the tone of no value, unless the layer that holds the colour paints them.
    paintOutside(surface, () => this.neutral);
    if (colour) colour.mark.update(step, valid);
    else paint(surface, () => this.neutral);
    const done = new Set([height?.mark, colour?.mark]);
    for (const channel of CHANNELS) {
      const mark = this.markOn(channel)?.mark;
      if (!mark || done.has(mark)) continue;
      done.add(mark);
      mark.update(step, valid);
    }
    // What stands over the sheet clears its tallest cell.
    const ceiling = height ? height.mark.ceiling : this.low;
    for (const frame of sheet.frames) {
      frame.mesh.position.y = ceiling + this.pitch * 0.07;
      frame.anchor.y = frame.mesh.position.y;
    }

    if (sheet.seams) {
      const { quads, geometry, record: formed } = sheet.seams;
      const seamPosition = geometry.attributes.position, seamColour = geometry.attributes.color;
      const { r, g, b } = this.ink;
      quads.forEach((quad, k) => {
        const height = Math.min(sheet.cells[quad.a].height, sheet.cells[quad.b].height);
        // Without a record of the junctions, or at a record that is not valid, the seam is only a faint line.
        const alpha = formed && valid ? 0.88 * Math.min(1, Math.max(0, formed.at(step, quad.link))) : 0.18;
        for (let corner = 0; corner < 4; corner++) {
          seamPosition.array[(k * 4 + corner) * 3 + 1] = height;
          seamColour.array.set([r, g, b, alpha], (k * 4 + corner) * 4);
        }
      });
      seamPosition.needsUpdate = true;
      seamColour.needsUpdate = true;
    }

    // Replacements of the last stretch of the run: newest first, each fading as the run moves on.
    const now = this.player.time;
    const recent = run.eventsBetween(now - MARK_SECONDS, now + 5e-4).reverse();
    this.marks.forEach((mark, k) => {
      const event = recent[k];
      const cell = event?.at?.set === "cell" ? sheet.cells[event.at.index] : null;
      mark.group.visible = Boolean(cell);
      if (!cell) return;
      const age = Math.min(1, Math.max(0, (now - event.time) / MARK_SECONDS));
      mark.material.opacity = 0.95 * (1 - smooth(age));
      mark.ring.position.set(cell.centre[0], cell.height + this.pitch * 0.05, cell.centre[1]);
      mark.ring.scale.setScalar(cell.radius * (0.82 + 0.5 * smooth(age)));
      const donor = event.from?.set === "cell" ? sheet.cells[event.from.index] : null;
      mark.arrow.visible = Boolean(donor);
      if (donor) {
        // From the middle of the cell copied towards the cell replaced, above every prism.
        const dx = cell.centre[0] - donor.centre[0], dy = cell.centre[1] - donor.centre[1];
        mark.arrow.position.set(donor.centre[0], ceiling + this.pitch * 0.12, donor.centre[1]);
        mark.arrow.rotation.y = -Math.atan2(dy, dx);
        mark.arrow.scale.set(Math.hypot(dx, dy), 1, this.pitch);
      }
    });

    this.outline("hover", this.hovered !== this.selected ? this.hovered : null);
    this.outline("pick", this.selected);
    // What is drawn on the chosen cell's membrane follows the same record.
    for (const { mark } of this.onMembrane.values()) mark.update(step, valid);
    if (this.closeup) this.closeup.caption.set(this.closeupCaption());
    this.tag();
  }

  /** A band round one cell's top. */
  outline(which, number_) {
    const line = which === "pick" ? this.pickLine : this.hoverLine;
    const cell = number_ === null || number_ === undefined ? null : this.sheet?.cells[number_];
    if (!line) return;
    line.visible = Boolean(cell);
    if (!cell) {
      this.outlined[which] = null;
      return;
    }
    if (this.outlined[which] !== number_) {
      const edges = cell.inset.map((corner, k) => [corner, cell.inset[(k + 1) % cell.inset.length]]);
      line.geometry.dispose();
      line.geometry = ribbon(edges, this.pitch * (which === "pick" ? 0.1 : 0.07));
      this.outlined[which] = number_;
    }
    line.position.y = cell.height + this.pitch * 0.03;
  }

  /** The name tags over the sheet: the region, the cell under the pointer, the cell picked. */
  tag() {
    if (!this.active || !this.sheet) return;
    const labels = this.labels;
    if (!this.tags) {
      labels.clear();
      this.closeup?.detach();
      labels.calloutFrame = null;
      this.tags = { regions: [], hover: null, pick: null };
      const experiment = this.catalogue.experimentOf(this.catalogue.byId.get(this.runId));
      for (const frame of this.sheet.frames) {
        const text = experiment.regions?.[frame.region.id]?.label || frame.region.label || frame.region.id;
        this.tags.regions.push(labels.add({ text, anchor: frame.anchor, priority: 300, kind: "note label-region", lift: 4 }));
      }
      this.tags.hover = labels.add({ text: "", anchor: new THREE.Vector3(), priority: 900, kind: "part label-read", lift: 8 });
      this.tags.pick = labels.add({ text: "", anchor: new THREE.Vector3(), priority: 950, kind: "part label-read", lift: 8 });
      this.tags.pick.element.classList.add("is-focus");
      this.tags.hover.boost = this.tags.pick.boost = 1000;
      // A bold relief stands a bar beside the sheet: how much of the quantity one stretch of height is.
      this.tags.bar = labels.add({ text: "", anchor: new THREE.Vector3(), priority: 320, kind: "note label-region", lift: 6 });
      // Each space outside the cells is named on its tile, and a held bath is called one.
      this.tags.outside = (this.surface.outside?.tiles || []).map((tile) => labels.add({ text: "", anchor: tile.top, priority: 310, kind: "note label-region", lift: 4 }));
      // In such a small world each cell is named too, as its neighbours are; on a sheet a cell is named when it is pointed at or chosen.
      this.tags.cells = this.surface.outside ? this.sheet.cells.map((cell) => labels.add({ text: "", anchor: cell.top, priority: 305, kind: "note label-region", lift: 4 })) : [];
      // What the picture says of itself for as long as it shows: that an example's numbers are invented (rule 6),
      // and for a layer on the motion channel what one bead stands for and what time it keeps (rule 3).
      this.tags.example = this.run.example ? labels.add({ text: this.run.example.says, anchor: new THREE.Vector3(0, this.high, -this.extent * 1.02), priority: 980, kind: "note label-region label-example", lift: 10 }) : null;
      this.tags.flow = labels.add({ text: "", anchor: new THREE.Vector3(0, 0, this.extent * 1.06), priority: 970, kind: "note label-region label-flow", lift: 0 });
      for (const label of [this.tags.example, this.tags.flow]) if (label) label.boost = 1000;
      // The close-up's own words: the ions' names and readings, which side is which, and its caption.
      this.closeup?.attach(labels);
    }
    const bar = this.markOn("height")?.mark.bar || null;
    this.tags.bar.hidden = !bar;
    if (bar) {
      this.tags.bar.anchor.copy(bar.anchor);
      labels.setText(this.tags.bar, bar.text);
    }
    const step = this.player.index, valid = this.run.isValid(step);
    const fogged = this.markOn("colour")?.mark;
    this.tags.outside.forEach((label, number_) => {
      const outside = this.surface.outside, tile = outside.tiles[number_];
      const value = valid && fogged?.reading ? fogged.reading(step, "outside", number_, number) : null;
      labels.setText(label, `${outside.set.ids[number_]}${tile.held ? " (held bath)" : ""}${value ? ` · ${value}` : ""}`);
    });
    this.tags.cells.forEach((label, number_) => {
      // The tag of a cell pointed at or chosen says the same and more: the standing name gives way to it.
      label.hidden = number_ === this.selected || number_ === this.hovered;
      const value = valid && fogged?.reading ? fogged.reading(step, "cell", number_, number) : null;
      labels.setText(label, `${this.cells.ids[number_]}${value ? ` · ${value}` : ""}`);
    });
    // On a narrow window the statement stands in three short lines, so that none of it is cut.
    const flow = this.statement(this.markOn("motion")?.mark);
    this.tags.flow.hidden = !flow;
    if (flow) labels.setText(this.tags.flow, this.stage.width < 620 ? flow.replace(/ · /g, "\n") : flow);
    const words = (number_) => {
      const name = this.cells.ids[number_];
      return valid ? `${name} · ${this.record.text(step, number_)}` : `${name} · not a valid record`;
    };
    const place = (label, number_) => {
      label.hidden = number_ === null || number_ === undefined;
      if (label.hidden) return;
      const cell = this.sheet.cells[number_];
      label.anchor.copy(cell.top);
      labels.setText(label, words(number_));
    };
    place(this.tags.pick, this.selected);
    place(this.tags.hover, this.hovered !== this.selected ? this.hovered : null);
  }

  // ------------------------------------------------------------ lens interface

  has(id) {
    if (typeof id !== "string") return false;
    if (id.startsWith(RUN)) return this.catalogue.byId.has(id.slice(RUN.length));
    if (id.startsWith(CELL)) return Boolean(this.sheet) && Number(id.slice(CELL.length)) < this.sheet.cells.length;
    if (id === LAYERS) return Boolean(this.sheet) && this.layersOn().length > 0;
    return false;
  }

  /** The runs, as the list shows them. */
  entities() {
    return this.catalogue.entities();
  }

  /** The list: the runs, then the cells of the run on screen, so a cell can be opened without a pointer. */
  sections() {
    const sections = this.catalogue.sections();
    if (this.sheet) {
      const inside = new Set(this.run.regions.filter((region) => region.set === "cell").flatMap((region) => region.indices));
      sections.push({
        label: "Cells of the run shown",
        entities: this.cells.ids.map((name, number_) => ({ id: CELL + number_, label: name, keywords: inside.has(number_) ? "disc region" : "" })),
      });
    }
    return sections;
  }

  /** What the panel shows for a run or for a cell of the run on screen. */
  describe(id) {
    if (typeof id !== "string") return null;
    if (id.startsWith(RUN)) {
      const runId = id.slice(RUN.length);
      return this.catalogue.describe(id, this.loaded.get(runId) || null);
    }
    if (id === LAYERS) return this.has(id) ? this.describeLayers() : null;
    if (!id.startsWith(CELL) || !this.has(id)) return null;
    const number_ = Number(id.slice(CELL.length));
    const { run } = this;
    const entry = this.catalogue.byId.get(this.runId);
    const experiment = this.catalogue.experimentOf(entry);
    const name = this.cells.ids[number_];
    const chips = [{ label: this.catalogue.title(entry), title: "The run this cell is shown in." }];
    for (const region of run.regions) {
      if (region.set !== "cell") continue;
      const named = experiment.regions?.[region.id];
      const inside = region.indices.includes(number_);
      chips.push({ label: `${inside ? "In" : "Outside"} ${lower(named?.label || region.label || region.id)}`, title: named?.plain || "" });
    }
    const events = run.eventsOf("cell", number_);
    const replaced = events.filter((event) => event.at.set === "cell" && event.at.index === number_);
    const copied = events.filter((event) => event.from?.set === "cell" && event.from.index === number_);
    const word = lower(experiment.events?.replacement?.label || "replacement");
    const junctions = run.sets.get("junction");
    const joined = junctions?.geometry?.ends?.filter((pair) => pair.includes(number_)).length;
    const facts = [];
    if (joined !== undefined) facts.push(["Cells it is joined to", String(joined)]);
    facts.push([`Times replaced in this run`, String(replaced.length)], ["Times copied into a neighbour", String(copied.length)]);
    const generation = run.records.get("generation");
    const item = (event, other, verb) => ({
      label: `At ${clock(event.time, { precise: true })}`,
      detail: other === undefined ? verb : `${verb} ${this.cells.ids[other]}`,
      tag: event.label || null,
      tag_title: "The run's own name for this newcomer.",
    });
    const sections = [];
    if (replaced.length) sections.push({ title: `Replaced here`, items: replaced.map((event) => item(event, event.from?.index, event.from ? "by a copy of" : "replaced")) });
    if (copied.length) sections.push({ title: "Copied from here", items: copied.map((event) => item(event, event.at.index, "into the place of")) });
    return {
      id,
      label: name,
      eyebrow: experiment.label,
      kind: "cell",
      plain: `One cell of the sheet. The chart shows its ${lower(this.recordLabel(this.record))} at every saved record; the line through it is the playhead.`,
      note: "Values are the run's saved records, and nothing is interpolated between them. A record saved at the moment of a replacement shows the cell just before it; the newcomer appears in the next record.",
      chips,
      facts,
      chart: {
        run,
        record: this.record,
        index: number_,
        player: this.player,
        title: this.recordLabel(this.record),
        judged: run.info.judged_s,
        levels: this.record.marks || [],
        events: replaced.map((event) => ({ time: event.time, label: `Replaced (${word} ${event.label || ""})`.replace(" )", ")") })),
        extra: generation && generation !== this.record ? (step) => `generation ${generation.at(step, number_)}` : null,
      },
      // With a layer on its membrane drawn, the numbers of the close-up at the record shown come first; then what the run's ledgers say of the cell.
      sections: [this.closeup?.cell === number_ ? this.membraneNumbers() : null, this.ledgerOf("cell", number_), ...sections].filter(Boolean),
      sources: [],
    };
  }

  /** What the run's ledgers say of one place at the record shown (what was made there, what was cleared), where the layer that colours the sheet reads them. */
  ledgerOf(where, number_) {
    const mark = this.markOn("colour")?.mark;
    if (!mark?.ledger || !this.run.isValid(this.player.index)) return null;
    const lines = mark.ledger(this.player.index, where, number_, number);
    if (!lines.length) return null;
    const species = mark.species ? ` of ${mark.species}` : "", totals = lines.every((line) => line.total);
    return { title: `${totals ? "Totals" : "Ledgers"}${species} at ${clock(this.player.time, { precise: true })}`, items: lines.map((line) => ({ label: line.label, detail: line.text })), note: totals ? "Saved by the run: totals since its start." : "Saved by the run." };
  }

  /** The experiment's own name for a record, or the run's. */
  recordLabel(record) {
    const experiment = this.catalogue.experimentOf(this.catalogue.byId.get(this.runId));
    return experiment.records?.[record.id]?.label || record.label || record.id;
  }

  chrome() {
    const entry = this.catalogue.byId.get(this.runId);
    const experiment = this.catalogue.experimentOf(entry);
    const klass = this.catalogue.classOf(entry);
    const run = this.run;
    // The records the sheet can be coloured by: one colouring layer each.
    const records = run && this.sheet ? this.offers.filter((item) => item.ok && item.layer.mark === "tint").map((item) => run.records.get(item.source.id)) : [];
    const chrome = {
      quiet: true, // the timeline takes the place of the hint
      status: this.error ? `This run could not be shown: ${this.error}` : this.loading ? "Loading the run…" : null,
      stamp: [experiment.label, run?.example ? run.example.says : null, run?.info.revision ? `engine ${run.info.revision}` : null].filter(Boolean).join(" · "),
      timeline: run && this.sheet ? { player: this.player, eventWord: lower(experiment.events?.replacement?.label || "event") } : null,
      run: {
        heading: experiment.label,
        text: experiment.plain || "",
        // What the experiment found, in the record's words, so one run is not read as the whole result.
        outcome: this.catalogue.outcomeOf(experiment),
        // With runs of several experiments, the card also picks the experiment.
        experiments: [...this.catalogue.experiments.values()]
          .filter((item) => this.catalogue.runs.some((one) => one.experiment === item.id))
          .map((item) => ({ id: item.id, label: item.label, active: item.id === entry?.experiment, first: this.catalogue.runs.find((one) => one.experiment === item.id).id, outcome: this.catalogue.outcomeOf(item), development: Boolean(item.development), example: Boolean(item.example) })),
        runs: this.catalogue.runs
          .filter((item) => item.experiment === entry?.experiment)
          .map((item) => ({ id: item.id, title: item.arm, sub: item.seed === null || item.seed === undefined ? "" : `seed ${item.seed}`, klass: this.catalogue.classOf(item)?.label || "", early: this.catalogue.endOf(item).early, active: item.id === this.runId })),
        ended: this.catalogue.endOf(entry),
        klass: klass ? { label: klass.label, description: klass.description, note: experiment.class_note || "" } : null,
        colour: records.length > 1 ? { options: records.map((record) => [record.id, this.recordLabel(record)]), active: this.markOn("colour")?.mark.record.id ?? null } : null,
        details: RUN + this.runId,
      },
      legend: { title: "Shown", items: [] },
    };
    if (run && this.sheet && this.record) {
      const colour = this.markOn("colour"), height = this.markOn("height");
      // The scale of what colours the sheet, as the layer's mark gives it.
      if (colour) chrome.legend.scale = colour.mark.scale(colour.mark.label || this.recordLabel(colour.mark.record), number);
      const keys = [];
      if (this.sheet.seams?.record) keys.push({ key: "seam", text: "A seam fills in as the junctions between two cells form" });
      for (const frame of this.sheet.frames) keys.push({ key: "frame", text: `${experiment.regions?.[frame.region.id]?.label || frame.region.label}: ${lower(experiment.regions?.[frame.region.id]?.plain || "a region the run names")}` });
      if (run.events.length) keys.push({ key: "ring", text: `${experiment.events?.replacement?.label || "Event"}: a ring on the cell, an arrow from the cell copied` });
      chrome.legend.keys = keys;
      chrome.legend.note = { text: this.heightNote(colour, height) };
      chrome.legend.layers = this.layerSwitch();
      // Where the layers add signs of their own, the sheet's standing marks fold away to leave them room.
      if (chrome.legend.layers.keys.length) chrome.legend.folded = true;
    }
    return chrome;
  }

  /** What the legend says of the sheet's height, in one line. */
  heightNote(colour, height) {
    const saved = "Every step is a saved record.";
    if (!height) return `The sheet is flat: no layer is on its height. ${saved}`;
    const record = height.mark.record;
    if (colour && colour.mark.record === record) return `Height repeats the colour. ${saved}`;
    const { shown, low, high } = height.mark.domain;
    const unit = shown.unit ? ` ${shown.unit}` : "";
    return `Height: ${lower(this.recordLabel(record))}, from ${number(low * shown.factor, 0)}${unit} (low) to ${number(high * shown.factor, 0)}${unit} (tall). ${saved}`;
  }

  /**
   * The switch for layers, as the legend draws it: for each channel but colour (which the
   * card chooses), the layers this run can feed and which one is on; the layers it cannot
   * feed, each with the reason; how strongly the marks are drawn; and, for the layers that
   * are on, what stands behind their numbers.
   */
  layerSwitch() {
    const rows = [];
    for (const channel of CHANNELS) {
      const offered = this.offers.filter((item) => item.layer.channels.includes(channel));
      const can = offered.filter((item) => item.ok);
      // The colour is chosen in the run's card while only colourings of a record compete for it.
      if (channel === "colour" && can.every((item) => item.layer.mark === "tint")) continue;
      if (!can.length) continue;
      const held = this.switch.holder(channel);
      rows.push({
        channel,
        label: CHANNEL_WORDS[channel],
        options: [{ id: null, label: "Off", on: !held, off: held }, ...can.map((item) => ({ id: item.layer.id, label: this.layerLabel(item), on: held === item.layer.id, busy: this.fetching.has(item.layer.id), title: item.layer.says }))],
        problem: this.layerError && can.some((item) => item.layer.id === this.layerError.id) ? this.layerError.text : null,
      });
    }
    const cannot = this.offers.filter((item) => !item.ok && !item.layer.plain).map((item) => ({ id: item.layer.id, label: `${CHANNEL_WORDS[item.layer.channels[0]]}: ${lower(item.layer.label)}`, why: item.why }));
    // The signs the layers add to the sheet, each with what it stands for.
    const keys = [], listed = new Set();
    for (const channel of CHANNELS) {
      const drawn = this.markOn(channel) || this.onMembrane.get(this.switch.holder(channel));
      if (!drawn || listed.has(drawn) || !drawn.mark.keys) continue;
      listed.add(drawn);
      keys.push(...drawn.mark.keys(number));
    }
    // A layer on a membrane is drawn for a chosen cell: with none chosen, the switch says how to see it.
    const waiting = this.layersOn().filter((item) => this.livesOnMembrane(item.fed) && !this.onMembrane.has(item.layer.id));
    const hint = waiting.length ? "Choose a cell of the sheet: a piece of its membrane is drawn beside it." : null;
    // The time a layer on the motion channel keeps: true speed as it opens, and a slow-down beside it.
    const moving = this.layersOn().some((item) => item.layer.channels.includes("motion"));
    const time = moving ? { label: "Speed", options: SLOWS.map((value) => ({ id: value, label: value === 1 ? "True" : `1/${value.toLocaleString("en-US")}`, title: timeWords(value), on: this.slow === value })) } : null;
    return { title: "Layers", rows, cannot, keys, hint, time, example: this.run.example?.says || null, strength: { options: STRENGTHS.map((value) => ({ id: value, label: value.charAt(0).toUpperCase() + value.slice(1), on: this.switch.strength === value })) }, details: this.layersOn().length ? LAYERS : null };
  }

  /** What the panel says of the layers that are on: what each shows and what stands behind its numbers (rule 4). */
  describeLayers() {
    const entry = this.catalogue.byId.get(this.runId);
    const experiment = this.catalogue.experimentOf(entry);
    const sections = this.layersOn().map(({ layer, fed }) => {
      const said = account(this.run, layer, fed);
      const items = [{ label: "What it shows", detail: said.shows }, { label: said.derived ? "Its numbers: worked out by the viewer" : "Its numbers: saved by the run", lines: said.numbers }];
      if (said.more.length) items.push({ label: "What else the run saved about it", lines: said.more });
      if (this.livesOnMembrane(fed)) items.push({ label: "Where it is drawn", detail: this.onMembrane.has(layer.id) ? `On a piece of the membrane of ${this.cells.ids[this.closeup.cell]}, the cell chosen, beside the sheet.` : "On a piece of the membrane of a chosen cell, beside the sheet. No cell is chosen now." });
      return { title: `${said.channel}: ${lower(this.layerLabel(fed))}`, items };
    });
    // The numbers of the close-up at the record shown, where a cell is chosen.
    const numbers = this.membraneNumbers();
    if (numbers) sections.push({ ...numbers, title: `${this.cells.ids[this.closeup.cell]}: ${lower(numbers.title)}` });
    // The numbers behind the beads that cross the sheet's borders and behind what glows, at the record shown.
    sections.push(...this.flowNumbers());
    const cannot = this.offers.filter((item) => !item.ok && !item.layer.plain);
    if (cannot.length) sections.push({ title: "Not shown for this run", items: cannot.map((item) => ({ label: `${CHANNEL_WORDS[item.layer.channels[0]]}: ${lower(item.layer.label)}`, detail: item.why })) });
    return {
      id: LAYERS,
      label: "What the layers show",
      eyebrow: experiment.label,
      kind: "layers",
      plain: `${this.run.example ? `${this.run.example.says}. ` : ""}A layer draws one quantity onto the sheet, or onto a piece of a chosen cell's membrane, from numbers this run saved. One layer holds each visual channel: the colour, the height, the signs on the junctions, the arrows through a membrane, the marks at its faces, what moves, what glows.`,
      note: "A number is either saved by the run, or worked out by the viewer from saved ones by a stated rule. The viewer computes no law of the engine again.",
      chips: [{ label: this.catalogue.title(entry), title: "The run these layers are drawn on." }],
      facts: [["Drawn", this.switch.strength]],
      sections,
      sources: [],
    };
  }

  /** A layer's name in the switch: the experiment's own name for its record where it has one. */
  layerLabel(fed) {
    // A colouring or a relief of a record is called by the record's name; the layer of a species by the species; any other layer by its own.
    const record = !fed.quantity?.derivation && fed.source && ["tint", "relief"].includes(fed.layer.mark) ? this.run.records.get(fed.source.id) : null;
    if (fed.quantity?.species === "secreted" && fed.species) return `Amount of ${fed.species}`;
    return record ? this.recordLabel(record) : fed.layer.label;
  }

  /** The scale bar reads in real units when the run's space is in micrometres. */
  scaleInfo() {
    if (!this.run || !this.sheet) return null;
    if (this.run.space.unit !== "um") return { note: `Lengths are in ${this.run.space.unit || "the run's own units"}` };
    return { micronsPerUnit: 1, note: this.run.derived ? "cell positions derived" : null };
  }

  get pickRoots() {
    return [this.root];
  }

  activate() {
    const { stage } = this;
    this.active = true;
    stage.scene.add(this.root);
    stage.sun.castShadow = false;
    this.tags = null;
    this.labels.clear();
    this.labels.calloutFrame = null;
    if (this.sheet) this.enter();
    this.shine();
    this.draw();
    stage.invalidate();
  }

  /** Frame the sheet, and start the first run playing unless motion is unwanted. */
  enter() {
    const { stage } = this;
    stage.rig.limits = { minDistance: this.pitch * 1.6, maxDistance: this.extent * 16, minPolar: 0.06, maxPolar: 1.46 };
    stage.rig.setView(this.homeView());
    this.tags = null;
    if (!this.autoplayed && !stage.reducedMotion && !stage.rig.instant && this.pendingTime === null && this.player.time === this.player.start) {
      this.autoplayed = true;
      this.player.play();
    }
    this.autoplayed = true;
  }

  deactivate() {
    this.active = false;
    this.player.pause();
    this.shine(); // nothing of this lens shines while another is shown
    this.stage.scene.remove(this.root);
    this.labels.clear();
    this.tags = null;
  }

  homeView() {
    const { stage } = this;
    const half = Math.tan((stage.camera.fov * Math.PI) / 360);
    const narrow = stage.width < stage.height * 0.9;
    const polar = narrow ? 0.62 : 0.88;
    const across = this.extent * 2.25;
    const up = this.extent * 2.25 * Math.cos(polar) + this.high * 3;
    const distance = Math.max(up / (2 * half), across / (2 * half * stage.camera.aspect)) * (narrow ? 1.26 : 1.2);
    // The timeline lies along the bottom, so on a wide screen the sheet sits a little above the
    // middle; on a narrow one the run's card covers the top, so it sits a little below.
    return { target: new THREE.Vector3(0, 0, this.extent * (narrow ? -0.3 : 0.16)), distance, azimuth: 0.38, polar };
  }

  setSelection(id) {
    this.panel = id || null;
    if (id?.startsWith(RUN)) {
      const runId = id.slice(RUN.length);
      this.selected = null;
      if (runId !== this.runId) this.show(runId);
    } else if (id?.startsWith(CELL) && this.has(id)) {
      this.selected = Number(id.slice(CELL.length));
    } else if (id !== LAYERS) {
      // The panel on what the layers show leaves the chosen cell chosen: its close-up stays.
      this.selected = null;
    }
    // The close-up follows the cell chosen, while a layer that lives on a membrane is on.
    const wanted = this.selected !== null && this.switch.on.some((layer) => this.offer(layer)?.ok && this.livesOnMembrane(this.offer(layer))) ? this.selected : null;
    if ((this.closeup?.cell ?? null) !== wanted) {
      this.buildCloseup();
      this.onChrome?.();
    }
    this.draw();
    this.stage.invalidate();
  }

  setHover(id) {
    const next = id?.startsWith?.(CELL) && this.has(id) ? Number(id.slice(CELL.length)) : null;
    if (next === this.hovered) return;
    this.hovered = next;
    this.draw();
    this.stage.invalidate();
  }

  setIsolate() {}

  /**
   * Colour the sheet by another of the run's records. Where the height repeats the colour,
   * it follows to the new record, as it always did.
   */
  setRecord(id) {
    const tint = this.offerOf("tint", id);
    if (!tint || this.switch.holder("colour") === tint.layer.id) return;
    const colour = this.markOn("colour"), height = this.markOn("height");
    const repeats = Boolean(colour && height && height.mark.record === colour.mark.record);
    this.off.delete("colour");
    this.switch.switchOn(tint.layer);
    if (repeats || (!height && !this.off.has("height"))) {
      const relief = this.offerOf("relief", id);
      if (relief) this.switch.switchOn(relief.layer);
    }
    this.layersChanged();
  }

  /** Move the playhead; before the run is in, the time is kept for when it is. */
  seek(seconds) {
    if (!Number.isFinite(seconds)) return;
    if (this.run) this.player.seek(seconds);
    else this.pendingTime = seconds;
  }

  focus(id) {
    if (!this.sheet) return;
    const rig = this.stage.rig, home = this.homeView();
    if (id?.startsWith(CELL) && this.has(id)) {
      const cell = this.sheet.cells[Number(id.slice(CELL.length))];
      const target = new THREE.Vector3(cell.centre[0], 0, cell.centre[1]).lerp(home.target, 0.45), distance = Math.min(rig.distance, home.distance * 0.72);
      if (this.closeup) {
        // The close-up stands above its cell: the view looks at a point beyond the cell, so that the two share the window.
        const { stage } = this;
        const card = Closeup.widthFor(stage.width, this.free || { left: 0, right: stage.width }) * 0.78;
        const down = Math.min(0.3 * stage.height, (card + 26) / 2); // how far below the middle the cell is to stand, in pixels
        const perPixel = (2 * distance * Math.tan((stage.camera.fov * Math.PI) / 360)) / stage.height;
        const beyond = (down * perPixel) / Math.max(0.2, Math.cos(rig.polar));
        target.set(cell.centre[0], 0, cell.centre[1]).add(new THREE.Vector3(-Math.sin(rig.azimuth), 0, -Math.cos(rig.azimuth)).multiplyScalar(beyond));
      }
      rig.flyTo({ target, distance }, 900);
    } else {
      rig.flyTo(home, 900);
    }
  }

  update(dt) {
    const playing = this.active ? this.player.tick(dt) : false;
    this.placeCloseup();
    // A mark that moves (a layer on the motion channel) is advanced on every frame, and keeps the frames coming. It
    // is advanced by the time that truly passed since the frame before: the stage hands a frame at most a tenth of a
    // second, which on a slow device would let the beads pass more slowly than the picture says they do.
    const clock = globalThis.performance?.now?.() ?? null;
    const passed = clock !== null && this.ticked !== undefined && this.ticked !== null ? Math.max(dt, clock - this.ticked) : dt;
    let moving = false;
    if (this.active) for (const { mark } of [...this.drawn.values(), ...this.onMembrane.values()]) if (mark.tick) moving = mark.tick(passed, this.slow) || moving;
    this.ticked = moving ? clock : null; // a lane that was not watched starts afresh: its first frame is the stage's own
    // A close-up just built waits a moment for the window to settle, then asks for room once.
    let waiting = false;
    if (this.closeup && this.roomIn > 0) {
      this.roomIn -= dt;
      waiting = this.roomIn > 0;
      if (!waiting) {
        this.makeRoom();
        // The view may have moved at once (a still picture, reduced motion): the close-up is placed again for it, and one more frame is drawn.
        this.placeCloseup();
        this.stage.invalidate();
      }
    }
    return playing || waiting || moving;
  }

  /**
   * How much a layer on the motion channel is slowed: 1 is true speed (a second here is a
   * second in the cell). The legend states it with what one token stands for (rule 3).
   */
  setSlow(value) {
    if (!(value >= 1) || value === this.slow) return;
    this.slow = value;
    for (const { mark } of [...this.drawn.values(), ...this.onMembrane.values()]) mark.setSlow?.();
    this.draw();
    this.onChrome?.();
    this.numbersMoved();
    this.stage.invalidate();
  }

  setRamp(palette) {
    this.ramp = new Ramp([palette.seq0, palette.seq1, palette.seq2, palette.seq3, palette.seq4]);
    this.neutral = parse(palette.stUnstated);
    this.ink.set(palette.fg);
    this.ground.set(palette.bg);
    this.glass.set(palette.bioMembrane);
    this.raised.set(palette.bgRaised || palette.bg);
    this.dark = Boolean(palette.dark);
    this.setIons();
  }

  /** Each ion's own colour for the run shown and the theme: the same for an ion wherever it is drawn. */
  setIons() {
    const species = this.run?.sets.get("species")?.ids || [];
    this.ions = new Map([...ionColours(ionTable, species, this.dark)].map(([id, css]) => [id, { css, colour: new THREE.Color(css) }]));
  }

  applyInk() {
    this.inkMaterial?.color.copy(this.ink);
    this.softMaterial?.color.copy(this.ink);
    for (const mark of this.marks || []) mark.material.color.copy(this.ink);
  }

  applyPalette(palette) {
    this.setRamp(palette);
    this.applyInk();
    for (const { mark } of [...(this.drawn?.values() || []), ...(this.onMembrane?.values() || [])]) mark.setColours?.(this.colours());
    this.closeup?.setColours(this.colours());
    this.draw();
    if (this.active) this.onChrome?.();
    this.stage.invalidate();
  }

  dispose() {
    disposeTree(this.root);
  }
}

const lower = (text) => (text ? text.charAt(0).toLowerCase() + text.slice(1) : "");
const capital = (text) => (text ? text.charAt(0).toUpperCase() + text.slice(1) : "");
// The close-up's caption names each input of a rule in a word or two.
const SHORT = { voltage: "membrane voltage", inside: "ion concentrations", outside: "composition outside", temperature: "temperature", valence: "valences", capacitance: "capacitance", area: "area" };
const cssOf = ([r, g, b]) => `rgb(${Math.round(r * 255)}, ${Math.round(g * 255)}, ${Math.round(b * 255)})`;

/** Flat bands of a given width along a list of edges ([[x, y], [x, y]]), in the plane y = 0. */
function ribbon(edges, width) {
  const positions = [], index = [];
  edges.forEach(([[ax, ay], [bx, by]], k) => {
    const length = Math.hypot(bx - ax, by - ay) || 1;
    const ux = (bx - ax) / length, uy = (by - ay) / length;
    const nx = (-uy * width) / 2, ny = (ux * width) / 2;
    // A little longer than the edge, so that bands meet at the corners.
    const sx = ax - (ux * width) / 2, sy = ay - (uy * width) / 2, ex = bx + (ux * width) / 2, ey = by + (uy * width) / 2;
    positions.push(sx + nx, 0, sy + ny, ex + nx, 0, ey + ny, ex - nx, 0, ey - ny, sx - nx, 0, sy - ny);
    index.push(k * 4, k * 4 + 1, k * 4 + 2, k * 4, k * 4 + 2, k * 4 + 3);
  });
  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute("position", new THREE.Float32BufferAttribute(positions, 3));
  geometry.setIndex(index);
  return geometry;
}

/** An arrow lying flat, from x = 0.24 to x = 0.8 of a unit length, to be stretched between two cells. */
function arrowShape() {
  const shaft = 0.035, head = 0.11, from = 0.24, neck = 0.6, tip = 0.8;
  const positions = [from, 0, -shaft, neck, 0, -shaft, neck, 0, shaft, from, 0, shaft, neck, 0, -head, tip, 0, 0, neck, 0, head];
  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute("position", new THREE.Float32BufferAttribute(positions, 3));
  geometry.setIndex([0, 1, 2, 0, 2, 3, 4, 5, 6]);
  return geometry;
}
