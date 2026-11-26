import * as THREE from "../three.js";
import { Library, engineId, isId, pageId } from "./laws_data.js";
import { describe as describePart, sections as listSections, mappedCellLaws } from "./laws_card.js";
import { LawConnections, displayName, familyKey, howLabel, modelName, partsOf, relationLabel } from "./laws_connections.js";
import { AtlasDrawing, atlasColours, drawAtlas, drawComparison, drawWiring, NEIGHBOURS_PER_LAYER } from "./laws_atlas_scene.js";
import { fitView } from "./laws_marks.js";
import { atlasControls } from "./laws_atlas_controls.js";
import { emit } from "../ui/dom.js";
import { LawsLens } from "./laws.js";

const titles = { atlas: "Family atlas", wiring: "Exploded model", compare: "Model comparison" };
const angles = { atlas: [0.28, 0.88], wiring: [-0.33, 1.16], compare: [-0.58, 1.29] };

export function makeLawsView(stage, model, labels) {
  const shelves = new URLSearchParams(globalThis.location?.search).get("lawLayout") === "shelves";
  return shelves ? new LawsLens(stage, model, labels) : new LawsAtlasLens(stage, model, labels);
}

export class LawsAtlasLens {
  constructor(stage, model, labels) {
    this.id = "laws";
    this.stage = stage;
    this.model = model;
    this.labels = labels;
    this.library = new Library(model.raw.laws);
    this.graph = new LawConnections(this.library, model.raw);
    this.drawing = new AtlasDrawing();
    this.root = this.drawing.root;
    this.colours = atlasColours(stage.palette || {});
    this.cellMap = mappedCellLaws(model.raw);
    this.defaultModel = this.library.frames.find((f) => f.kind === "composite")?.id || null;
    this.primary = this.defaultModel;
    this.family = null;
    this.other = null;
    this.filter = { query: "", where: null, box: null };
    this.anatomy = null;
    this.mode = "atlas";
    this.selected = null;
    this.trace = null;
    this.trail = [];
    this.spread = 2.65;
    this.relation = "main";
    this.page = 0;
    this.wantsLeftRoom = true;
    this.active = false;
  }
  get pickRoots() {
    return [this.root];
  }
  has(id) {
    const name = engineId(id);
    return Boolean(name && (isId(name) || this.library.rowOf(name) || this.graph.describe(id)));
  }
  canonical(id) {
    id = this.library.resolve(id);
    const [type, owner, verb, name] = partsOf(id);
    if (type === "field" && verb === "reads") {
      const target = this.library.piece(name);
      if (target && this.library.piece(owner)?.declared?.reads?.some(r => r.name === target.id)) return pageId(target.id);
    }
    const nameOf = engineId(id),
      entity = this.library.piece(nameOf) || this.library.frame(nameOf);
    return entity ? pageId(entity.id) : id;
  }
  describe(id) {
    const summary = this.graph.describe(id);
    if (summary) return summary;
    const drawn = (box) => this.model.get(box) && this.model.lensOf(this.model.get(box)) === "engine";
    const entity = describePart(this.library, id, { drawn, map: this.model.meta });
    if (!entity) return null;
    const frame = this.library.frame(engineId(id));
    if (frame && this.mode !== "atlas")
      return {
        ...entity,
        doors: [{ label: "Show this model in the family atlas", lens: "laws", value: "model/" + frame.id }, ...(entity.doors || [])],
      };
    const piece = this.library.piece(engineId(id));
    if (!piece) return entity;
    const origin = this.anatomy && this.cellMap.get(this.anatomy)?.get(piece.id);
    return origin
      ? { ...entity, related: [{ title: "Mapped through these inventory units", ids: [...origin] }, ...(entity.related || [])] }
      : entity;
  }
  sections() {
    return listSections(this.library);
  }
  entities() {
    return this.sections().flatMap((s) => s.entities);
  }
  matches(piece) {
    return this.library.passes(piece, this.filter) && (!this.anatomy || this.cellMap.get(this.anatomy)?.has(piece.id));
  }
  filtered() {
    return this.library.pieces.filter((p) => (!this.family || this.family === p.family) && this.matches(p));
  }
  order() {
    const rows = this.mode === "compare" ? this.graph.compare(this.primary, this.other).flat() : this.filtered();
    return rows.map((p) => pageId(p.id));
  }
  step(direction = 1) {
    const rows = this.order(),
      at = rows.indexOf(this.selected);
    return rows.length ? rows[at < 0 ? (direction > 0 ? 0 : rows.length - 1) : (at + direction + rows.length) % rows.length] : null;
  }
  traceGroups() {
    const rows = this.traceRows || [];
    const take = (e) =>
      this.relation === "all" ||
      (this.relation === "main" && !["owns", "conflicts"].includes(e.verb)) ||
      (this.relation === "models" && e.layer === "models") ||
      e.verb === this.relation;
    return Object.fromEntries(["models", "pieces", "fields"].map((layer) => [layer, rows.filter((e) => e.layer === layer && take(e))]));
  }
  traceLayers() {
    return Object.fromEntries(
      Object.entries(this.traceGroups()).map(([layer, list]) => {
        const start = Math.min(this.page, Math.max(0, Math.ceil(list.length / NEIGHBOURS_PER_LAYER) - 1)) * NEIGHBOURS_PER_LAYER;
        return [layer, list.slice(start, start + NEIGHBOURS_PER_LAYER)];
      }),
    );
  }
  activate() {
    this.active = true;
    this.portrait = this.isPortrait();
    this.stage.scene.add(this.root);
    this.stage.rig.limits = { minDistance: 1.2, maxDistance: 500, minPolar: 0.13, maxPolar: Math.PI - 0.14 };
    this.stage.dress?.({ rich: true, filmic: false, contact: false });
    this.rebuild();
    this.fit(false);
  }
  deactivate() {
    this.active = false;
    this.stage.scene.remove(this.root);
    this.labels.clear();
    this.stage.dress?.({ rich: false });
  }
  applyPalette(p) {
    this.colours = atlasColours(p);
    if (this.active) this.rebuild();
  }
  dispose() {
    this.drawing.dispose();
  }
  drawScene(d) {
    if (this.mode === "wiring") drawWiring(d, this, this.colours);
    else if (this.mode === "compare") drawComparison(d, this, this.colours);
    else drawAtlas(d, this, this.colours);
  }
  rebuild() {
    if (!this.active) return;
    const d = this.drawing;
    d.reset();
    this.drawScene(d);
    d.finish();
    this.labels.clear();
    this.hoverLabel = null;
    this.hovered = null;
    this.labelById = new Map();
    for (const spec of d.labels) {
      const label = this.labels.add(spec);
      if (spec.id) this.labelById.set(spec.id, label);
      if (spec.id && spec.id === this.selected) label.element?.classList.add("is-focus");
    }
    this.stage.invalidate();
  }
  framedView(box, orientation = null) {
    const { stage } = this,
      { left = 0, right = 0, bottom = 0 } = stage.insets || {};
    const width = Math.max(160, stage.width - left - right),
      height = Math.max(160, stage.height - bottom);
    const [a, p] = angles[this.mode],
      azimuth = this.portrait && this.mode === "atlas" ? 1.52 : a;
    const polar = this.portrait ? { atlas: 0.49, wiring: 1.22, compare: 1.12 }[this.mode] : p;
    const fov = (2 * Math.atan((Math.tan((stage.camera.fov * Math.PI) / 360) * height) / Math.max(height, stage.height)) * 180) / Math.PI;
    const whole = box === this.drawing.bounds;
    const view = fitView(box, {
      fov,
      aspect: width / height,
      azimuth,
      polar,
      margin: this.mode === "atlas" ? 0.15 : 0.2,
      points: whole ? this.drawing.extent : null,
      ...orientation,
    });
    if (whole && this.mode === "atlas") this.overviewDistance = view.distance;
    return view;
  }
  fit(fly = true, box = this.drawing.bounds) {
    const view = this.framedView(box);
    if (fly) this.stage.rig.flyTo(view, 470);
    else this.stage.rig.setView(view);
  }
  isPortrait() {
    const { width, height, insets = {} } = this.stage;
    return width < 760 && width < (height - (insets.bottom || 0)) * 0.83;
  }
  roomChanged() {
    if (!this.active) return;
    const key = JSON.stringify([this.stage.width, this.stage.height, this.stage.insets]);
    if (this.room === key) return;
    this.room = key;
    const portrait = this.isPortrait();
    if (this.portrait !== portrait) {
      this.portrait = portrait;
      this.rebuild();
    }
    if (this.restoreCamera) {
      this.stage.rig.setView(this.restoreCamera);
      this.restoreCamera = null;
    } else this.fit(false, this.focusBox || this.drawing.bounds);
  }
  update() {
    this.roomChanged();
    this.restoreCamera = null;
    if (this.mode === "atlas" && !this.family) {
      let near = null;
      if (this.stage.rig.distance < this.overviewDistance * 0.68) {
        const target = this.stage.rig.target;
        let closest = 4;
        for (const f of this.library.families) {
          const pos = this.drawing.anchors.get(familyKey(f.id));
          const distance = Math.hypot(pos.x - target.x, pos.z - target.z);
          if (distance < closest) {
            closest = distance;
            near = f.id;
          }
        }
      }
      if ((this.nearFamily || null) !== near) {
        this.nearFamily = near;
        this.rebuild();
      }
    }
    return false;
  }
  notice({ fit = false, chrome = true, address = true } = {}) {
    this.rebuild();
    if (fit && this.active) this.fit(true, this.focusBox || this.drawing.bounds);
    if (chrome) this.onChrome?.();
    if (address) this.onAddress?.();
  }
  selectOnPage(id) {
    emit(this.stage.canvas, "cells-select", { id, fly: false });
  }
  setHover(id) {
    if (!this.active || id === this.hovered) return;
    const old = this.labelById?.get(this.hovered);
    if (old) old.boost = 0;
    if (this.hoverLabel) {
      this.labels.remove(this.hoverLabel);
      this.hoverLabel = null;
    }
    this.hovered = id;
    const existing = this.labelById?.get(id),
      pt = this.drawing.anchors.get(id);
    if (existing) existing.boost = 800;
    else if (pt && id) {
      const part = this.graph.bundles.get(id);
      const text = part
        ? modelName(this.library.frame(part.model)) + " · " + this.library.familyById.get(part.family).short + " · " + part.entries.length
        : displayName(engineId(id));
      this.hoverLabel = this.labels.add({ id, text, anchor: pt, priority: 1300, kind: "atlas-subject" });
    }
    this.stage.invalidate();
  }
  enterTrace(piece, returnSelection = this.selected) {
    if (this.mode !== "wiring") {
      this.fromTrace = this.mode;
      this.returnSelection = returnSelection;
      this.traceCamera = this.stage.rig.view();
      this.trail = [];
    } else if (this.trace && this.trace !== piece.id) this.trail.push(this.trace);
    this.mode = "wiring";
    this.trace = piece.id;
    this.traceRows = this.graph.neighbours(piece);
    this.page = 0;
    this.relation = "main";
    this.focusBox = null;
  }
  openOnMap(id) {
    const piece = this.library.piece(engineId(id));
    if (!piece || this.mode === "compare" || this.trace === piece.id) return false;
    this.tracePiece(piece.id);
    return true;
  }
  setSelection(id) {
    const next = id && this.has(id) ? this.canonical(id) : null;
    if (next === this.selected) return;
    const previous = this.selected;
    this.selected = next;
    const raw = engineId(next),
      piece = this.library.piece(raw),
      frame = this.library.frame(raw);
    let fit = false;
    if (piece && this.mode !== "compare" && (this.trace !== piece.id || this.mode !== "wiring")) {
      this.enterTrace(piece, previous);
      fit = true;
    } else if (this.mode === "atlas" && frame) this.primary = frame.id;
    else if (this.mode === "atlas" && partsOf(next)[0] === "family") {
      this.family = partsOf(next)[1];
      this.focusBox = null;
    } else if (this.mode === "atlas" && this.graph.bundles.has(next)) {
      const b = this.graph.bundles.get(next);
      this.primary = b.model;
      this.family = b.family;
    }
    this.notice({ fit });
  }
  focus(id) {
    if (!this.active) return;
    const [type, key] = partsOf(id);
    if (this.mode === "atlas" && type === "family") {
      const p = this.drawing.anchors.get(familyKey(key));
      if (p) {
        this.focusBox = new THREE.Box3(p.clone().add(new THREE.Vector3(-2.9, -1.3, -2.9)), p.clone().add(new THREE.Vector3(2.9, 1.7, 2.9)));
        this.fit(true, this.focusBox);
      }
    }
  }
  clearPanel() {
    if (this.selected) this.selectOnPage(null);
  }
  setMark(id) {
    this.family = this.library.familyById.has(id) ? id : null;
    this.focusBox = null;
    this.clearPanel();
    this.notice({ fit: true });
    if (this.family) this.focus(familyKey(this.family));
  }
  setMode(id) {
    this.filter.where = ["declared", "design"].includes(id) ? id : null;
    this.notice();
  }
  setIsolate(id) {
    if (id === "laws-design" || id === "laws-declared") this.setMode(id.slice(5));
    else if (this.filter.where) this.setMode("all");
  }
  setQuery(q) {
    this.filter.query = String(q || "");
    this.notice({ address: false });
  }
  setFinding(value) {
    if (engineId(value) && this.has(value)) {
      this.selectOnPage(this.canonical(value));
      return;
    }
    this.mode = "atlas";
    this.trace = null;
    this.other = null;
    this.trail = [];
    this.family = null;
    this.focusBox = null;
    const cap = String(value || "").replace(/^cell\//, "");
    this.anatomy = this.cellMap.has(cap) ? cap : null;
    this.filter.box = value && this.library.inBox(value).length ? value : null;
    this.filter.query = "";
    this.filter.where = null;
    const model = String(value || "").startsWith("model/") && this.library.frame(value.slice(6));
    if (model) this.primary = model.id;
    if (this.anatomy || this.filter.box) this.primary = null;
    this.clearPanel();
    this.notice({ fit: true });
  }
  setPrimary(id) {
    const f = this.library.frame(id);
    this.primary = f?.id || null;
    if (this.mode === "compare" && (!this.primary || this.primary === this.other)) {
      this.other = null;
      this.mode = "atlas";
    }
    this.focusBox = null;
    this.clearPanel();
    this.notice({ fit: true });
  }
  compareWith(id) {
    const f = this.library.frame(id);
    if (!f || f.id === this.primary) return;
    if (!this.primary) this.primary = this.defaultModel !== f.id ? this.defaultModel : this.library.frames.find((m) => m.id !== f.id)?.id;
    if (!this.primary) return;
    if (this.mode === "atlas") this.atlasCamera = this.stage.rig.view();
    this.other = f.id;
    this.mode = "compare";
    this.trace = null;
    this.trail = [];
    this.focusBox = null;
    this.clearPanel();
    this.notice({ fit: true });
  }
  tracePiece(id) {
    const piece = this.library.piece(id);
    if (!piece) return;
    this.enterTrace(piece);
    this.selectOnPage(null);
    this.notice({ fit: true });
  }
  back() {
    let camera = null;
    let restoreId = null;
    if (this.mode === "wiring" && this.trail.length) {
      const previous = this.trail.pop();
      this.trace = previous;
      this.traceRows = this.graph.neighbours(this.library.piece(previous));
      this.relation = "main";
      this.page = 0;
      this.clearPanel();
      this.notice({ fit: true });
      return true;
    }
    if (this.mode === "wiring") {
      this.mode = this.fromTrace === "compare" && this.other ? "compare" : "atlas";
      this.trace = null;
      camera = this.traceCamera;
      restoreId = this.returnSelection;
      this.returnSelection = null;
    } else if (this.mode === "compare") {
      this.mode = "atlas";
      this.other = null;
      camera = this.atlasCamera;
    } else if (this.family || this.anatomy || this.filter.box) {
      this.family = null;
      this.anatomy = null;
      this.filter.box = null;
    } else return false;
    this.focusBox = null;
    this.clearPanel();
    if (restoreId && (this.mode === "compare" || !this.library.piece(engineId(restoreId)))) this.selectOnPage(restoreId);
    this.notice({ fit: !camera });
    if (camera) {
      this.stage.rig.setView(camera);
      this.restoreCamera = camera;
    }
    return true;
  }
  address() {
    return {
      lawModel: this.primary === this.defaultModel ? null : this.primary || "all",
      lawFamily: this.family,
      lawOrigin: this.anatomy ? "cell/" + this.anatomy : this.filter.box,
      lawWhere: this.filter.where,
      trace: this.mode === "wiring" ? this.trace : null,
      compare: this.other,
    };
  }
  restore(query) {
    const origin = query.get("lawOrigin");
    if (origin) this.setFinding(origin);
    const where = query.get("lawWhere") || query.get("show");
    this.filter.where = ["declared", "design"].includes(where) ? where : null;
    const primary = query.get("lawModel");
    if (primary === "all" || this.library.frame(primary)) this.primary = this.library.frame(primary)?.id || null;
    const family = query.get("lawFamily");
    if (this.library.familyById.has(family)) this.family = family;
    const other = query.get("compare");
    if (other) this.compareWith(other);
    const piece = this.library.piece(query.get("trace"));
    if (piece) this.enterTrace(piece);
    this.notice({ fit: true, address: false });
  }
  chrome() {
    let items,
      back = null,
      note;
    if (this.mode === "atlas") {
      items = [
        ["laws-atlas-island", "Island · mechanism family", this.library.families.length],
        ["laws-atlas-dock", "Dock · model", this.library.frames.length],
        ["laws-atlas-route", "Bridge · model and family", this.graph.bundles.size],
        ["laws-design", "Hollow pin · design note", this.library.counts().where.design],
      ];
      if (this.family || this.anatomy || this.filter.box) back = "Family atlas";
      note = "Bridge width shows the number of memberships.";
    } else if (this.mode === "wiring") {
      const totals = new Map();
      for (const edge of Object.values(this.traceLayers()).flat()) totals.set(edge.verb, (totals.get(edge.verb) || 0) + 1);
      items = [...totals].map(([verb, count]) => ["laws-atlas-" + verb, howLabel[verb] || relationLabel[verb], count]);
      back = this.trail.length ? "Previous piece" : this.fromTrace === "compare" ? "Model comparison" : "Family atlas";
      note = "Arrowheads point from the declaring piece or model to the object of its declaration.";
    } else {
      const [left, shared, right] = this.graph.compare(this.primary, this.other);
      items = [
        ["laws-atlas-first", modelName(this.library.frame(this.primary)) + " only", left.length],
        ["laws-atlas-shared", "Shared pieces", shared.length],
        ["laws-atlas-writes", modelName(this.library.frame(this.other)) + " only", right.length],
      ];
      back = "Family atlas";
      note = "Each piece appears once.";
    }
    const sources = [
      {
        name: "Cells declarations",
        holds: "Models, pieces, dependencies and field declarations at main " + this.library.manifest.short,
        licence: "MIT",
      },
      { name: "Cells protein inventory", holds: "The inventory units explicitly mapped to the cell view", licence: "MIT" },
    ];
    return {
      card: { heading: titles[this.mode], stats: [], sources, own: () => atlasControls(this) },
      legend: {
        title: this.mode === "wiring" ? "Connections" : "Map key",
        items: items.map(([swatch, label, count]) => ({ swatch, label, count, passive: true })),
        note: { text: note },
      },
      stamp: "Read at main " + this.library.manifest.short,
      back,
    };
  }
}
