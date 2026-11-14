// The protein atlas lens: the molecular machines Cells models, set in the membranes
// where their laws act. One stretch of plasma membrane holds the channels, pumps and
// transporters; a second membrane above one corner is the neighbouring cell, for the
// junction channels; pieces of ER and mitochondrial membrane and the protein cage sit
// below, inside the cell.
//
// The picture keeps the inventory's own distinction, and form carries it:
//   assigned in source   a solid assembly, drawn from the stated subunit counts;
//   candidate            the candidate's assembly, drawn clear;
//   generic              a plain grey stand-in with no subunits: no protein is assigned.
// These are the inventory's words, not engine statuses.

import * as THREE from "../three.js";
import { soften } from "../core/materials.js";
import { disposeTree } from "../core/stage.js";
import { makeEnvironment } from "../core/environment.js";
import { SHEET, UPPER, buildUnit, membrane, outline } from "./protein_parts.js";

const PITCH = 11.5; // spacing of units within a district
const GUTTER = 9; // between districts
const BETWEEN_BANDS = 17;
const MARGIN = 8; // from the outermost units to the membrane's edge
const DROP = 30; // how far below the plasma membrane the organelle membranes sit
const HALF = SHEET / 2;
const WHITE = new THREE.Color(0xffffff), BLACK = new THREE.Color(0x000000);

// How each tone is drawn. "named" is the colour of a protein the law names; "generic" is grey.
const TONES = {
  main: { hue: "named", shade: 0 },
  alt: { hue: "named", shade: -0.24 },
  aux: { hue: "named", shade: 0.36 },
  second: { hue: "named", shade: 0.44 },
  secondAlt: { hue: "named", shade: 0.27 },
  ghost: { hue: "named", shade: 0.3, opacity: 0.26, glass: 0.6 },
  glass: { hue: "named", shade: 0.08, opacity: 0.4, glass: 0.55 },
  glassAlt: { hue: "named", shade: -0.06, opacity: 0.4, glass: 0.55 },
  glassAux: { hue: "named", shade: 0.32, opacity: 0.32, glass: 0.55 },
  plain: { hue: "generic", shade: 0, roughness: 0.78, side: THREE.DoubleSide },
  plainSoft: { hue: "generic", shade: 0.12, opacity: 0.55 },
};
const CLEAR = { main: "glass", alt: "glassAlt", aux: "glassAux", second: "glassAux", secondAlt: "glassAux", ghost: "ghost" };
const SHEET_HUE = { plasma: "bioMembrane", neighbour: "bioMembrane", er: "bioEr", mitochondria: "bioMito" };
const months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const day = (iso) => (iso ? `${Number(iso.slice(8, 10))} ${months[Number(iso.slice(5, 7)) - 1]} ${iso.slice(0, 4)}` : "");

export class ProteinLens {
  constructor(stage, model, labels) {
    this.id = "proteins";
    this.stage = stage;
    this.model = model;
    this.labels = labels;
    this.atlas = model.raw.proteins;
    this.root = new THREE.Group();
    this.nodes = new Map(); // unit id -> { entity, group, meshes, reach, top, ... }
    this.tones = new Map();
    this.sheets = [];
    this.districts = [];
    this.selected = null;
    this.hovered = null;
    this.isolate = null; // a mapping id
    this.evidence = null; // a kind of evidence
    this.active = false;
    this.environment = makeEnvironment(stage.renderer);
    this.build();
    this.applyPalette(stage.palette);
  }

  // ------------------------------------------------------------ layout

  build() {
    const units = this.model.inGroup("proteins");
    const districts = this.atlas.districts
      .map((district) => ({ ...district, units: units.filter((unit) => unit.district === district.id) }))
      .filter((district) => district.units.length);
    for (const district of districts) {
      district.rows = Math.ceil(district.units.length / district.columns);
      district.width = district.columns * PITCH;
      district.depth = district.rows * PITCH;
    }
    const band = (index) => districts.filter((district) => district.band === index);
    const span = (row, gap = GUTTER) => row.reduce((sum, district) => sum + district.width, 0) + gap * (row.length - 1);
    const deepest = (row) => Math.max(0, ...row.map((district) => district.depth));
    const back = band(0), front = band(1), inside = band(2);
    const width = Math.max(span(back), span(front)) + 2 * MARGIN;
    const depth = deepest(back) + (front.length ? BETWEEN_BANDS + deepest(front) : 0) + 2 * MARGIN;
    const place = (row, z, y, gap = GUTTER, centre = 0) => {
      let x = centre - span(row, gap) / 2;
      for (const district of row) {
        district.centre = new THREE.Vector3(x + district.width / 2, y, z);
        x += district.width + gap;
      }
    };
    place(back, -depth / 2 + MARGIN + deepest(back) / 2, 0);
    place(front, depth / 2 - MARGIN - deepest(front) / 2, 0);
    place(inside, depth / 2 + 22, -DROP, 20, width * 0.12);

    this.lineMaterial = new THREE.LineBasicMaterial({ transparent: true, opacity: 0.4, depthWrite: false });
    this.dashes = new THREE.LineDashedMaterial({ transparent: true, opacity: 0.9, dashSize: 0.7, gapSize: 0.5 });
    this.sheet("plasma", width, depth, new THREE.Vector3(0, 0, 0), 7);
    for (const district of districts) {
      const { centre } = district;
      const own = district.band === 2 && SHEET_HUE[district.id];
      if (own) this.sheet(district.id, district.width + 12, district.depth + 12, centre, 6);
      if (district.id === "junctions") this.sheet("neighbour", district.width + 8, district.depth + 8, centre.clone().setY(UPPER), 6);
      if (district.band !== 2) {
        const edge = new THREE.LineLoop(outline(district.width + 1.5, district.depth + 1.5, 4), this.lineMaterial);
        edge.position.set(centre.x, HALF + 0.08, centre.z);
        edge.userData.unpickable = true;
        edge.renderOrder = 3;
        this.root.add(edge);
      }
      // The district's name lies just in front of it, on the membrane.
      const drop = district.id === "assembly" ? -5 : HALF;
      district.anchor = new THREE.Vector3(centre.x, centre.y + drop, centre.z + district.depth / 2 + (own ? 9.5 : 4.4));
      district.units.forEach((unit, index) => {
        const column = index % district.columns, row = Math.floor(index / district.columns);
        this.unit(unit, new THREE.Vector3(centre.x - district.width / 2 + (column + 0.5) * PITCH, centre.y, centre.z - district.depth / 2 + (row + 0.5) * PITCH));
      });
    }
    this.districts = districts;
    this.sides = [
      { text: "Outside the cell", anchor: new THREE.Vector3(-width / 2 + 4, 13, -depth / 2 + 2) },
      { text: "Inside the cell", anchor: new THREE.Vector3(-width / 2 + 4, -DROP * 0.55, depth / 2 + 6) },
    ];
    this.bounds = { minX: -width / 2, maxX: width / 2, minZ: -depth / 2, maxZ: depth / 2 + 22 + PITCH, minY: -DROP - 8, maxY: UPPER + 4 };

    // One ring marks the unit in focus, a lighter one the unit under the pointer.
    const ring = new THREE.TorusGeometry(1, 0.02, 8, 72);
    this.ring = new THREE.Mesh(ring, new THREE.MeshBasicMaterial());
    this.hoverRing = new THREE.Mesh(ring, new THREE.MeshBasicMaterial({ transparent: true, opacity: 0.6 }));
    for (const mark of [this.ring, this.hoverRing]) {
      mark.rotation.x = Math.PI / 2;
      mark.visible = false;
      mark.renderOrder = 6;
      mark.userData.unpickable = true;
      this.root.add(mark);
    }
    this.fill = new THREE.DirectionalLight(0xffffff, 0.6);
    this.fill.position.set(-80, -30, 60); // from below and in front, so the parts under the membrane read
    this.root.add(this.fill);
  }

  sheet(name, width, depth, centre, radius) {
    const sheet = membrane(width, depth, radius);
    sheet.group.position.copy(centre);
    sheet.hue = SHEET_HUE[name];
    this.sheets.push(sheet);
    this.root.add(sheet.group);
  }

  tone(name) {
    if (!this.tones.has(name)) {
      const spec = TONES[name];
      const opacity = spec.opacity ?? 1;
      const lit = new THREE.MeshStandardMaterial({ roughness: spec.roughness ?? 0.42, metalness: 0, transparent: opacity < 1, opacity, depthWrite: opacity === 1, side: spec.side ?? THREE.FrontSide });
      soften(lit, { rim: 0.32, alphaRim: spec.glass || 0 });
      const dim = new THREE.MeshStandardMaterial({ roughness: 0.9, metalness: 0, transparent: true, opacity: Math.max(0.06, opacity * 0.14), depthWrite: false, side: spec.side ?? THREE.FrontSide });
      this.tones.set(name, { spec, lit, dim });
    }
    return this.tones.get(name);
  }

  unit(entity, position) {
    const form = entity.form;
    const group = new THREE.Group();
    group.position.copy(position);
    group.userData.pick = entity.id;
    const node = { entity, group, meshes: [], position };
    const scratch = new THREE.Object3D();
    const add = (geometry, tone, at, options = {}) => {
      if (options.line) {
        const line = new THREE.LineLoop(geometry, this.dashes);
        line.computeLineDistances();
        line.position.fromArray(at);
        line.userData.unpickable = true;
        group.add(line);
        return;
      }
      const name = form.style === "glass" ? CLEAR[tone] || tone : tone;
      const set = this.tone(name);
      const scale = options.scale ?? 1;
      let mesh;
      if (Array.isArray(at) && at[0]?.isVector3) {
        // Many copies of one shape, each a little lighter or darker (the cage's trimers).
        mesh = new THREE.InstancedMesh(geometry, set.lit, at.length);
        at.forEach((point, index) => {
          scratch.position.copy(point);
          scratch.scale.setScalar(scale);
          scratch.updateMatrix();
          mesh.setMatrixAt(index, scratch.matrix);
          mesh.setColorAt(index, new THREE.Color().setScalar(options.shades?.[index] ?? 1));
        });
        mesh.instanceMatrix.needsUpdate = true;
      } else {
        mesh = new THREE.Mesh(geometry, set.lit);
        mesh.position.fromArray(at);
        if (Array.isArray(scale)) mesh.scale.fromArray(scale);
        else mesh.scale.setScalar(scale);
      }
      mesh.userData.tone = name;
      mesh.renderOrder = 4; // clear parts are drawn after the membranes they stand in
      group.add(mesh);
      node.meshes.push(mesh);
    };
    const reach = buildUnit(form, add);
    if (form.flip) group.rotation.x = Math.PI;
    if (reach.floats) group.position.y += 3;
    node.reach = reach;
    node.top = group.position.clone().setY(group.position.y + reach.top + 0.6);
    // The ring lies on the membrane the unit stands in; a junction channel's, on the neighbouring cell's.
    node.ringAt = group.position.clone().setY(group.position.y + (reach.floats ? 0 : form.shape === "junction" ? UPPER + HALF + 0.2 : HALF + 0.2));
    this.root.add(group);
    this.nodes.set(entity.id, node);
  }

  // ------------------------------------------------------------ lens interface

  has(id) {
    return this.nodes.has(id);
  }

  entities() {
    return [...this.nodes.values()].map((node) => node.entity);
  }

  sections() {
    return this.districts.map((district) => ({ label: district.label, entities: district.units }));
  }

  chrome() {
    const { atlas } = this;
    const { stamp, counts } = atlas;
    const lost = stamp.found.missing || 0;
    return {
      caveat: atlas.caveat,
      stamp: `Inventory of ${day(stamp.created)} · engine ${stamp.read_at}`,
      legend: {
        title: "Mapping",
        items: atlas.mappings.map((item) => ({ id: item.id, label: item.label, description: item.description, count: item.count, swatch: `map-${item.id}` })),
      },
      filter: {
        title: "Evidence for a law",
        unit: "records",
        items: atlas.evidence.filter((item) => item.count).map((item) => ({ id: item.id, label: item.label, title: item.description, count: item.count })),
        active: this.evidence,
      },
      card: {
        heading: "The proteins Cells models",
        stats: [[counts.units, "functional units"], [counts.laws, "laws"], [counts.genes, "candidate genes"]],
        text: `${atlas.summary} The inventory was made on ${day(stamp.created)}, at engine ${stamp.read_at}.`,
        check:
          `${lost ? `${lost} of its ${stamp.records} law records are no longer found` : `All ${stamp.records} of its law records are still found`} at main ${stamp.checked_at}.` +
          (stamp.gained?.added ? ` The engine has gained ${stamp.gained.added} identifiers since, most under ${stamp.gained.where[0][0]}. The inventory has not reviewed them, so a law added since would be missing here.` : ""),
        sources: atlas.sources,
        notCopied: atlas.not_copied,
      },
    };
  }

  get pickRoots() {
    return [this.root];
  }

  activate() {
    const { stage } = this;
    this.active = true;
    stage.scene.add(this.root);
    stage.sun.castShadow = false;
    stage.sun.position.set(-60, 150, 110);
    stage.sun.target.position.set(0, 0, 0);
    stage.rig.limits = { minDistance: 16, maxDistance: 900, minPolar: 0.12, maxPolar: 2.5 };
    this.light();
    stage.rig.setView(this.homeView());
    this.buildLabels();
    this.refresh();
  }

  deactivate() {
    this.active = false;
    this.stage.scene.remove(this.root);
    this.stage.scene.environment = null;
    this.stage.applyPalette(); // back to the stage's own lighting
    this.labels.clear();
  }

  light() {
    const { stage } = this;
    const dark = stage.palette.dark;
    stage.scene.environment = this.environment;
    stage.scene.environmentIntensity = dark ? 0.5 : 0.62;
    stage.sky.intensity = dark ? 1.0 : 1.25;
    stage.sun.intensity = dark ? 1.5 : 1.25;
    this.fill.intensity = dark ? 0.8 : 0.55;
  }

  homeView() {
    const { stage, bounds } = this;
    const half = Math.tan((stage.camera.fov * Math.PI) / 360);
    const wide = bounds.maxX - bounds.minX, deep = bounds.maxZ - bounds.minZ, tall = bounds.maxY - bounds.minY;
    const target = new THREE.Vector3((bounds.minX + bounds.maxX) / 2, -7, (bounds.minZ + bounds.maxZ) / 2 - 2);
    if (stage.width < stage.height * 0.9) {
      // A tall screen looks along the membrane, so its long side runs up the screen.
      const polar = 0.74, across = deep + 66, up = wide * Math.cos(polar) + tall * Math.sin(polar) + 10;
      target.z += 13;
      return { target, distance: Math.max(up / (2 * half), across / (2 * half * stage.camera.aspect)) * 1.04 + wide * 0.2, azimuth: 1.36, polar };
    }
    const polar = 0.98, across = wide + 14, up = deep * Math.cos(polar) + tall * Math.sin(polar) + 34;
    target.y = -11; // leaves room below for the note on the shapes
    return { target, distance: Math.max(up / (2 * half), across / (2 * half * stage.camera.aspect)) * 1.02 + deep * 0.3, azimuth: 0.24, polar };
  }

  buildLabels() {
    const labels = this.labels;
    labels.clear();
    labels.calloutFrame = null;
    for (const district of this.districts) {
      district.tag = labels.add({ text: district.label, anchor: district.anchor, priority: 500, kind: "layer label-district", lift: -8 });
    }
    for (const side of this.sides) labels.add({ text: side.text, anchor: side.anchor, priority: 400, kind: "note", lift: 0 });
    for (const node of this.nodes.values()) {
      node.label = labels.add({ id: node.entity.id, text: node.entity.short || node.entity.label, anchor: node.top, priority: 20, kind: "part label-unit", lift: 6 });
    }
  }

  setSelection(id) {
    this.selected = id && this.nodes.has(id) ? id : null;
    this.refresh();
  }

  setHover(id) {
    const next = id && this.nodes.has(id) ? id : null;
    if (next === this.hovered) return;
    this.hovered = next;
    this.refresh();
  }

  /** Show only the units of one mapping (the legend's first block). */
  setIsolate(mapping) {
    this.isolate = mapping || null;
    this.refresh();
  }

  /** Show only the units with a law resting on one kind of evidence (the legend's second block). */
  setTogether(evidence) {
    this.evidence = evidence || null;
    this.refresh();
    this.onChrome?.();
  }

  lit(entity) {
    if (this.isolate && entity.mapping !== this.isolate) return false;
    if (this.evidence && !(entity.evidence || []).includes(this.evidence)) return false;
    return true;
  }

  refresh() {
    for (const [id, node] of this.nodes) {
      const lit = this.lit(node.entity);
      const hot = id === this.selected || id === this.hovered;
      for (const mesh of node.meshes) {
        const set = this.tones.get(mesh.userData.tone);
        mesh.material = lit ? set.lit : set.dim;
      }
      if (node.label) {
        node.label.boost = hot ? 1000 : 0;
        node.label.hidden = !lit && !hot;
        node.label.element.classList.toggle("is-focus", id === this.selected);
      }
    }
    this.mark(this.ring, this.selected);
    this.mark(this.hoverRing, this.hovered && this.hovered !== this.selected ? this.hovered : null);
    this.stage.invalidate();
  }

  mark(ring, id) {
    const node = id ? this.nodes.get(id) : null;
    ring.visible = Boolean(node);
    if (!node) return;
    ring.position.copy(node.ringAt);
    ring.scale.setScalar(node.reach.radius + 1.5);
  }

  focus(id) {
    const node = this.nodes.get(id);
    if (!node) return;
    const rig = this.stage.rig;
    rig.flyTo({ target: node.group.position.clone().setY(node.group.position.y + 1), distance: Math.min(rig.distance, 78), polar: Math.min(rig.polar, 1.02) }, 1100);
  }

  update() {
    return false;
  }

  applyPalette(palette) {
    const named = new THREE.Color(palette.bioProtein), generic = new THREE.Color(palette.atlasGeneric);
    for (const { spec, lit, dim } of this.tones.values()) {
      const colour = (spec.hue === "named" ? named : generic).clone();
      if (spec.shade > 0) colour.lerp(WHITE, spec.shade);
      else if (spec.shade < 0) colour.lerp(BLACK, -spec.shade);
      lit.color.copy(colour);
      dim.color.copy(colour);
      lit.userData.rim?.uRimColor.value.copy(colour).lerp(WHITE, palette.dark ? 0.35 : 0.65);
    }
    for (const sheet of this.sheets) {
      // On a dark page a membrane this large would glare, so it is drawn deeper there.
      const colour = new THREE.Color(palette[sheet.hue] || palette.ghost);
      sheet.body.color.copy(colour).lerp(BLACK, palette.dark ? 0.45 : 0);
      sheet.body.opacity = palette.dark ? 0.55 : 0.45;
      if (palette.dark) sheet.faces.color.copy(colour).lerp(BLACK, 0.42);
      else sheet.faces.color.copy(colour).lerp(WHITE, 0.3);
    }
    this.lineMaterial.color.set(palette.edge);
    this.dashes.color.set(palette.ghost);
    this.ring.material.color.set(palette.fg);
    this.hoverRing.material.color.set(palette.fg);
    if (this.active) this.light();
    this.stage.invalidate();
  }

  dispose() {
    disposeTree(this.root);
    for (const { lit, dim } of this.tones.values()) {
      lit.dispose();
      dim.dispose();
    }
    this.environment?.dispose();
  }
}
