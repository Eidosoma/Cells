// The experiments lens: one saved run, replayed. The sheet of cells is drawn from the
// run's own polygons, each cell coloured (and raised) by one of its records at the
// playhead. Seams between cells fill in as their junctions form, a frame marks a region
// the run's plan names (the disc), and a ring with an arrow marks each replacement as
// it happens.
//
// It shows what the run saved. Every step is a saved record and nothing is interpolated;
// a record the run does not count as valid is drawn grey, never as data. The class shown
// with a run is the one the experiment's own summary records: the viewer judges nothing.

import * as THREE from "../three.js";
import { disposeTree } from "../core/stage.js";
import { loadRun } from "../replay/source.js";
import { Player } from "../replay/player.js";
import { Catalogue, RUN, CELL } from "../replay/catalogue.js";
import { Ramp, parse } from "../replay/ramp.js";
import { clock, display, niceDomain, number } from "../replay/format.js";
import "../replay/trace.js";

const INSET = 0.055; // each cell is drawn a little small, so cells read as separate tiles
const MARK_SECONDS = 45; // how long, in the run's time, a replacement stays marked
const MARKS = 6; // replacements marked at once
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
    this.neutral = [0.6, 0.65, 0.7];
    this.setRamp(stage.palette);
    this.player.addEventListener("time", () => {
      this.draw();
      this.stage.invalidate();
    });
    this.player.addEventListener("state", () => this.stage.invalidate());
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
      frames.push({ region, anchor: new THREE.Vector3(far[0], frame.position.y, far[1]) });
    }

    // Marks for replacements: a ring over the cell replaced and an arrow from the cell copied.
    const ring = new THREE.RingGeometry(0.8, 1, 40).rotateX(-Math.PI / 2);
    const arrow = arrowShape();
    this.marks = [];
    for (let k = 0; k < MARKS; k++) {
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
    this.domain = this.scaleOf(this.record);
    this.applyInk();
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
    const { run, sheet, record } = this;
    if (!run || !sheet || !record) return;
    const step = this.player.index;
    const valid = run.isValid(step);
    const { low, high, steps } = this.domain;
    const position = sheet.geometry.attributes.position, colour = sheet.geometry.attributes.color;
    const rgb = [0, 0, 0], linear = new THREE.Color();
    sheet.cells.forEach((cell, number_) => {
      let share = (record.at(step, number_) - low) / (high - low);
      if (steps) share = Math.round(share * steps) / steps;
      share = Math.min(1, Math.max(0, share));
      if (valid) this.ramp.at(share, rgb);
      else rgb.splice(0, 3, ...this.neutral); // not a valid record: no value is shown
      const height = valid ? this.low + (this.high - this.low) * share : this.low;
      cell.height = height;
      cell.top.y = height;
      const n = cell.inset.length;
      linear.setRGB(rgb[0], rgb[1], rgb[2], THREE.SRGBColorSpace);
      for (let k = 0; k <= n; k++) {
        position.array[(cell.start + k) * 3 + 1] = height;
        colour.array.set([linear.r, linear.g, linear.b], (cell.start + k) * 3);
      }
      for (let k = 0; k < n; k++) {
        const wall = cell.walls + k * 4, shade = cell.shade[k];
        position.array[wall * 3 + 1] = height;
        position.array[(wall + 1) * 3 + 1] = height;
        linear.setRGB(rgb[0] * shade, rgb[1] * shade, rgb[2] * shade, THREE.SRGBColorSpace);
        for (let corner = 0; corner < 4; corner++) colour.array.set([linear.r, linear.g, linear.b], (wall + corner) * 3);
      }
    });
    position.needsUpdate = true;
    colour.needsUpdate = true;

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
        mark.arrow.position.set(donor.centre[0], this.high + this.pitch * 0.12, donor.centre[1]);
        mark.arrow.rotation.y = -Math.atan2(dy, dx);
        mark.arrow.scale.set(Math.hypot(dx, dy), 1, this.pitch);
      }
    });

    this.outline("hover", this.hovered !== this.selected ? this.hovered : null);
    this.outline("pick", this.selected);
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
    }
    const step = this.player.index, valid = this.run.isValid(step);
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
      sections,
      sources: [],
    };
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
    const records = run && this.cells ? run.recordsOn("cell").filter((record) => !record.quantised) : [];
    const chrome = {
      quiet: true, // the timeline takes the place of the hint
      status: this.error ? `This run could not be shown: ${this.error}` : this.loading ? "Loading the run…" : null,
      stamp: [experiment.label, run?.info.revision ? `engine ${run.info.revision}` : null].filter(Boolean).join(" · "),
      timeline: run && this.sheet ? { player: this.player, eventWord: lower(experiment.events?.replacement?.label || "event") } : null,
      run: {
        heading: experiment.label,
        text: experiment.plain || "",
        // What the experiment found, in the record's words, so one run is not read as the whole result.
        outcome: this.catalogue.outcomeOf(experiment),
        // With runs of several experiments, the card also picks the experiment.
        experiments: [...this.catalogue.experiments.values()]
          .filter((item) => this.catalogue.runs.some((one) => one.experiment === item.id))
          .map((item) => ({ id: item.id, label: item.label, active: item.id === entry?.experiment, first: this.catalogue.runs.find((one) => one.experiment === item.id).id, outcome: this.catalogue.outcomeOf(item) })),
        runs: this.catalogue.runs
          .filter((item) => item.experiment === entry?.experiment)
          .map((item) => ({ id: item.id, title: item.arm, sub: item.seed === null || item.seed === undefined ? "" : `seed ${item.seed}`, klass: this.catalogue.classOf(item)?.label || "", early: this.catalogue.endOf(item).early, active: item.id === this.runId })),
        ended: this.catalogue.endOf(entry),
        klass: klass ? { label: klass.label, description: klass.description, note: experiment.class_note || "" } : null,
        colour: records.length > 1 ? { options: records.map((record) => [record.id, this.recordLabel(record)]), active: this.recordId } : null,
        details: RUN + this.runId,
      },
      legend: { title: "Shown", items: [] },
    };
    if (run && this.sheet && this.record) {
      const { shown, low, high, steps, nice } = this.domain;
      const scale = { label: this.recordLabel(this.record), unit: shown.unit };
      if (steps) {
        scale.steps = Array.from({ length: steps + 1 }, (_, k) => ({ colour: cssOf(this.ramp.at(k / steps)), text: String(k) }));
      } else {
        scale.gradient = this.ramp.css();
        const decimals = nice.step * 1 < 1 ? 1 : 0;
        scale.ticks = [low, (low + high) / 2, high].map((value, k) => ({ at: k / 2, text: number(value * shown.factor, decimals) }));
        scale.marks = (this.record.marks || []).filter((mark) => mark.value > low && mark.value < high).map((mark) => ({ at: (mark.value - low) / (high - low), text: `${number(mark.value * shown.factor, 1)} ${shown.unit}: ${mark.label}` }));
      }
      chrome.legend.scale = scale;
      const keys = [];
      if (this.sheet.seams?.record) keys.push({ key: "seam", text: "A seam fills in as the junctions between two cells form" });
      for (const frame of this.sheet.frames) keys.push({ key: "frame", text: `${experiment.regions?.[frame.region.id]?.label || frame.region.label}: ${lower(experiment.regions?.[frame.region.id]?.plain || "a region the run names")}` });
      if (run.events.length) keys.push({ key: "ring", text: `${experiment.events?.replacement?.label || "Event"}: a ring on the cell, an arrow from the cell copied` });
      chrome.legend.keys = keys;
      chrome.legend.note = { text: "Height repeats the colour. Every step is a saved record." };
    }
    return chrome;
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
    } else {
      this.selected = null;
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

  /** Colour the sheet by another of the run's records. */
  setRecord(id) {
    const record = this.run?.records.get(id);
    if (!record || record.set !== "cell" || record.quantised || record === this.record) return;
    this.record = record;
    this.recordId = id;
    this.domain = this.scaleOf(record);
    this.draw();
    this.onChrome?.();
    this.onPanel?.();
    this.stage.invalidate();
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
      rig.flyTo({ target: new THREE.Vector3(cell.centre[0], 0, cell.centre[1]).lerp(home.target, 0.45), distance: Math.min(rig.distance, home.distance * 0.72) }, 900);
    } else {
      rig.flyTo(home, 900);
    }
  }

  update(dt) {
    return this.active ? this.player.tick(dt) : false;
  }

  setRamp(palette) {
    this.ramp = new Ramp([palette.seq0, palette.seq1, palette.seq2, palette.seq3, palette.seq4]);
    this.neutral = parse(palette.stUnstated);
    this.ink.set(palette.fg);
  }

  applyInk() {
    this.inkMaterial?.color.copy(this.ink);
    this.softMaterial?.color.copy(this.ink);
    for (const mark of this.marks || []) mark.material.color.copy(this.ink);
  }

  applyPalette(palette) {
    this.setRamp(palette);
    this.applyInk();
    this.draw();
    if (this.active) this.onChrome?.();
    this.stage.invalidate();
  }

  dispose() {
    disposeTree(this.root);
  }
}

const lower = (text) => (text ? text.charAt(0).toLowerCase() + text.slice(1) : "");
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
