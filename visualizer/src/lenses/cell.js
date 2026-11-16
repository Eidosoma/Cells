// The cell lens: what Cells can simulate, drawn where it happens. One cell opened by
// a flat cut, and round it the larger levels of the species shown: a sheet of its cells,
// and placeholder outlines of an organ and a body for the scales nothing simulates yet.
// Which levels there are, the shape drawn at each and which capabilities have a place in
// the cell all come from the species (schema/SPECIES.md): the lens holds no drawing that
// belongs to one species. The levels are nested: the sheet lies on the body above the
// organ, so zooming out leads from tissue into organ into organism. A species of single
// cells has no such levels, and zooming out ends at its cell.
// Zooming is continuous: each scale fades in as the camera reaches it.
//
// Three things are kept apart:
//   status          built parts are solid, planned parts are sketches; the exact status
//                   is the dot beside each name (or the colour, with "Colour: Status");
//   representation  simulated, modelled or prescribed: stated in the panel;
//   size mode       "schematic" enlarges parts so each can be seen; "real" draws sizes
//                   and numbers nearer a real cell, with dots for what is too small.

import * as THREE from "../three.js";
import { statusToken } from "../core/theme.js";
import { glyphSprite, soften, enrich, jostle } from "../core/materials.js";
import { disposeTree } from "../core/stage.js";
import { makeEnvironment, makeStudio } from "../core/environment.js";
import { LookTrial } from "../core/look_trial.js";
import { R, CUT, buildCell, buildMolecules, buildTissue } from "./cell_parts.js";
import { REF, cellAcross } from "./shapes.js";
import { buildOutline } from "./outline_parts.js";
import { middle, words } from "./cell_scenery.js";
import { CellFlux, FLUX_SWITCH } from "../layers/cellflux.js";

const smooth = (a, b, x) => {
  const t = Math.min(1, Math.max(0, (x - a) / (b - a)));
  return t * t * (3 - 2 * t);
};
const WHITE = new THREE.Color(0xffffff), BLACK = new THREE.Color(0x000000);
export const SIZE_MODES = ["schematic", "real"];
// The levels a species may have, small to large, with the scene's part for each and the stop's name.
const LEVELS = [
  { id: "molecules", stop: "molecule", entity: "scale.molecule" },
  { id: "cell", stop: "cell", entity: "scale.cell" },
  { id: "tissue", stop: "tissue", entity: "scale.tissue" },
  { id: "organ", stop: "organ", entity: "scale.organ" },
  { id: "organism", stop: "organism", entity: "scale.organism" },
];
// A scene that names no species still draws a cell and its sheet: a generic cell, of no species.
const GENERIC = {
  id: null,
  levels: [{ id: "molecules" }, { id: "cell", shape: { kind: "prism", sides: 6, radius_um: REF.radius, height_um: 13, corner_um: 2.4, edge_um: 1.3 } }, { id: "tissue", shape: { kind: "cell sheet", rings: 6 } }],
  cell: { facts: [], parts: { nucleus: true }, capabilities: {} },
};
// The resting look (core/look.js), as this view asks for it. Contact shade: how far one part
// shades another, in micrometres of a cell twenty across and as a share of the camera's
// distance (the smaller counts), and how much of the shade is laid over the picture. At
// twice this reach the sheets of the endoplasmic reticulum went dark all over, which reads
// as density; at this one a shade shows only where parts meet. Drawn to scale the parts are
// several times smaller and stand closer, so the reach is shorter there, or stacks of sheets
// and shelves go dark between. Filmic light: how much light it lets in, a little over 1,
// which makes up for the curve's dark foot in the middle tones.
export const LOOK = { reach: 0.7, reachToScale: 0.3, reachOnScreen: 0.016, shade: 0.65, exposure: 1.08 };
// The camera's half view on a wide screen, for working out where one level gives way to the next.
const HALF_VIEW = Math.tan((34 * Math.PI) / 360);
const nominal = (size) => Math.max(size[1] / (2 * HALF_VIEW), size[0] / (2 * HALF_VIEW * 1.5));

/**
 * A piece of the species' own scenery as the panel describes it: that it is scenery, what the
 * species' file gives of it with its sources, and what was drawn. The foot of a thread says
 * what machine it is and opens the Protein atlas on the species' proteins that make it.
 */
export function describeScenery(item, species, links) {
  const SCENERY = { label: "Scenery", title: "Nothing in the engine stands behind it: it is drawn so that the cell looks as the species' cell does" };
  const of = (value, unit) => words(value, unit);
  const facts = item.facts || {};
  const given = [];
  if (facts.count !== undefined) given.push({ label: "How many on a cell", detail: of(facts.count) });
  if (facts.length_um !== undefined) given.push({ label: "Length", detail: of(facts.length_um, "µm") });
  if (facts.width_nm !== undefined) given.push({ label: "Width", detail: of(facts.width_nm, "nm") });
  if (facts.across_um !== undefined) given.push({ label: "Across", detail: of(facts.across_um, "µm") });
  if (facts.volume_fl !== undefined) given.push({ label: "Volume", detail: of(facts.volume_fl, "fl") });
  if (facts.share !== undefined) given.push({ label: "Share of the cell's volume", detail: `${Math.round(middle(facts.share) * 100)}%` });
  if (facts.where) given.push({ label: "Where on the cell", detail: facts.where });
  if (facts.from) given.push({ label: "Starts at", detail: `the ${facts.from}` });
  if (given.length) given[given.length - 1].links = links(item.sources);
  if (item.kind === "base") {
    const base = item.base;
    return {
      id: item.id, kind: "scenery", group: "biology", label: item.label, eyebrow: `${species.label} · scenery`, chips: [SCENERY],
      plain: `The machine at the foot of each of the cell's ${String(item.of).toLowerCase()}. Nothing in the engine stands behind it, and no closer view of it is drawn yet.`,
      note: "Its parts are among the species' own proteins: the Protein atlas shows them as one set.",
      doors: base.mark && base.value ? [{ label: `Show the proteins of the ${item.label.toLowerCase()} in the Protein atlas`, lens: "proteins", show: "own", mark: base.mark, value: base.value }] : [],
      sections: [{ title: "Sources", items: links(item.sources).length ? [{ label: "What the species' file gives of it", links: links(item.sources) }] : [] }],
    };
  }
  return {
    id: item.id, kind: "scenery", group: "biology", label: item.label, eyebrow: `${species.label} · scenery`, chips: [SCENERY],
    plain: "Drawn as scenery: nothing in the engine stands behind it, so it has no status.",
    sections: [
      { title: "As the species' file gives it", items: given },
      { title: "As drawn", items: (item.sizes || []).map(([label, text]) => ({ label, lines: [text] })) },
    ],
  };
}

// What Cells models of a species, in two or three words (schema/SPECIES.md, `modelled.state`).
export const MODELLED = { generic: "Generic cell", proposed: "Proposed, not modelled", modelled: "Modelled" };

/** The species the page opens on: the one whose file says so, else the first; null in a scene without species. */
export function defaultSpecies(scene) {
  const list = scene?.species || [];
  return (list.find((item) => item.default) || list[0])?.id ?? null;
}

let roundDot = null;
/** A soft round dot for point clouds, drawn once. */
function dotTexture() {
  if (!roundDot) {
    const canvas = document.createElement("canvas");
    canvas.width = canvas.height = 32;
    const context = canvas.getContext("2d");
    context.fillStyle = "#ffffff";
    context.beginPath();
    context.arc(16, 16, 13, 0, Math.PI * 2);
    context.fill();
    roundDot = new THREE.CanvasTexture(canvas);
  }
  return roundDot;
}

/** One drawn thing bound to one entity of the scene. */
class Part {
  constructor(lens, entity, zone, anchor) {
    this.lens = lens;
    this.entity = entity;
    this.zone = zone;
    this.anchor = anchor || null;
    this.status = entity?.status || null;
    this.materials = [];
    this.group = new THREE.Group();
    if (entity) this.group.userData.pick = entity.id;
    else this.group.userData.unpickable = true;
    this.group.userData.seeThrough = this.status === "planned";
    zone.root.add(this.group);
    zone.parts.push(this);
  }

  add(...objects) {
    this.group.add(...objects);
  }

  /**
   * A material for this part. hue names its biology colour (used with "Colour: Biology");
   * shade lightens (+) or darkens (-). A planned part is a sketch whatever is asked for:
   * thin outlines (line) or a wire mesh (wire). rim and alphaRim give solid parts a soft lit edge.
   * For the resting look (core/look.js): thin is how much light the part lets through,
   * texture a surface texture ("grain", "folds" with its long way as axis, "pores"),
   * shimmer marks a membrane, and drift is how far a crowd of copies jostles about.
   * contact: false keeps a solid part out of contact shade (a shell cut open, whose inside
   * would otherwise go dark like a pit).
   */
  material({ hue = null, opacity = 1, wire = false, line = false, shade = 0, emissive = 0, roughness = 0.42, flat = false, side = THREE.FrontSide, clip = false, depthWrite, rim = 0.3, alphaRim = 0, thin = 0, texture = null, axis = null, shimmer = false, drift = 0, contact = true } = {}) {
    const sketch = wire || line || this.status === "planned";
    let material;
    if (sketch) {
      material = new THREE.MeshBasicMaterial({ wireframe: !line, transparent: true, opacity: line ? 0.9 : 0.6, depthWrite: false });
      opacity = material.opacity;
    } else {
      if (this.status === "designed") opacity *= 0.45;
      material = new THREE.MeshStandardMaterial({ roughness, metalness: 0, flatShading: flat, side, transparent: opacity < 1, opacity, depthWrite: depthWrite ?? opacity === 1 });
      const numbers = this.lens.stage.numbers;
      if (thin || texture || shimmer) enrich(material, numbers, { rim, alphaRim, thin, texture, axis, shimmer, unit: this.zone.root.scale.x });
      else soften(material, { rim, alphaRim });
      if (drift) jostle(material, numbers, { reach: drift });
      if (!contact) material.userData.noContact = true;
    }
    if (clip) material.clippingPlanes = this.zone.cutPlanes;
    return this.register(material, { base: opacity, hue, shade, emissive, sketch });
  }

  /** Dots, for what is too small to draw as shapes. size is in screen pixels. */
  points({ hue = null, shade = 0, size = 1.6, opacity = 0.9, drift = 0 } = {}) {
    const material = new THREE.PointsMaterial({ size, sizeAttenuation: false, map: dotTexture(), alphaTest: 0.35, transparent: true, opacity, depthWrite: false });
    if (drift) jostle(material, this.lens.stage.numbers, { reach: drift });
    return this.register(material, { base: opacity, hue, shade, emissive: 0, sketch: this.status === "planned", dust: true });
  }

  /** Thin lines: outlines of a planned part, or fine structure of a built one. */
  lineMaterial({ hue = null, opacity = 0.8 } = {}) {
    const material = new THREE.LineBasicMaterial({ transparent: true, opacity, depthWrite: false });
    return this.register(material, { base: opacity, hue, shade: 0, emissive: 0, sketch: this.status === "planned" || !hue });
  }

  /** Draws nothing, but can be clicked: the body of a part that is drawn only as outlines. */
  proxyMaterial() {
    return (Part.proxy ??= new THREE.MeshBasicMaterial({ colorWrite: false, depthWrite: false }));
  }

  register(material, data) {
    material.userData = { ...material.userData, ...data, solidDepth: material.depthWrite };
    // Filmic light is for the natural colours of lit parts. A sketch's grey says "planned": it
    // stays as the legend shows it. And what gives off light of its own (the fuel's sparks, ions)
    // keeps the colour it has: rolled off, the fuel's yellow turned to the mitochondria's orange.
    material.toneMapped = !data.sketch && !(data.emissive > 0);
    this.materials.push(material);
    return material;
  }

  colour(palette) {
    const byBiology = this.lens.colourBy === "biology";
    for (const material of this.materials) {
      const data = material.userData;
      const name = data.sketch ? "ghost" : byBiology && data.hue ? data.hue : statusToken(this.status);
      const colour = new THREE.Color(palette[name] || palette.ghost);
      if (data.shade > 0) colour.lerp(WHITE, data.shade);
      else if (data.shade < 0) colour.lerp(BLACK, -data.shade);
      material.color.copy(colour);
      data.tint = colour;
      // The rim is a lighter tone of the part's own colour, so the colour still reads.
      data.rim?.uRimColor.value.copy(colour).lerp(WHITE, palette.dark ? 0.35 : 0.65);
    }
  }

  /** dim: another part is in focus. hot: this part is under the pointer or selected. */
  look(fade, dim, hot) {
    for (const material of this.materials) {
      const data = material.userData;
      const opacity = data.base * fade * (dim ? 0.14 : 1) * (data.dust ? this.lens.dustFade : 1);
      material.opacity = opacity;
      material.transparent = opacity < 0.999 || data.dust === true;
      material.depthWrite = data.solidDepth && opacity > 0.9;
      if (material.emissive && data.tint) material.emissive.copy(data.tint).multiplyScalar(data.emissive + (hot ? 0.26 : 0));
    }
  }
}

export class CellLens {
  constructor(stage, model, labels) {
    this.id = "cell";
    this.stage = stage;
    this.model = model;
    this.labels = labels;
    this.root = new THREE.Group();
    this.zones = [];
    this.byEntity = new Map(); // entity id -> [Part]
    this.sceneryLooks = new Map(); // id of a piece of scenery that can be chosen -> its materials
    this.selected = null;
    this.hovered = null;
    this.isolate = null;
    this.together = null;
    this.colourBy = "biology";
    this.sizeMode = "schematic";
    this.activeStop = "cell";
    this.dustFade = 1;
    this.clock = 0;
    this.active = false;
    this.capabilityByPart = new Map(model.ofKind("capability").map((entity) => [entity.part, entity]));
    // Parts of the cell that the scene leaves out of the picture for now (its `left_out`):
    // they have no capability in the scene, and are not drawn as scenery either.
    this.leftOut = new Set((model.raw?.left_out || []).map((item) => item.part).filter(Boolean));
    this.environment = makeEnvironment(stage.renderer);
    this.studio = null; // the studio the rich look reflects, made when first asked for
    this.reach = 0; // how far contact shade reaches now, in micrometres
    this.near = true; // whether anything solid is near enough for contact shade to show
    this.trial = null; // the readout a visitor asks for with "fps" in the address
    // The look may change while the lens is shown: the visitor chooses, or the device gives part of it up.
    this.stopLook = stage.look.onChange(() => {
      if (!this.active) return;
      this.light();
      this.onChrome?.();
    });
    this.fill = new THREE.DirectionalLight(0xffffff, 0.7);
    this.fill.position.set(-70, 25, -40);
    this.root.add(this.fill);
    // The species the scene holds; the page shows one at a time (schema/SPECIES.md).
    this.list = model.raw.species || [];
    this.species = null;
    // What flows in the cell: shown for a chosen part, or all of it with the Flux switch (layers/cellflux.js).
    this.flux = new CellFlux(this);
    this.setSpecies(defaultSpecies(model.raw));
  }

  // ------------------------------------------------------------ the species shown

  /** The species with this id. A scene that names no species draws the generic cell. */
  speciesOf(id) {
    return this.list.length ? this.list.find((item) => item.id === id) || null : GENERIC;
  }

  /** Show another species: its levels, its shapes and the capabilities that have a place in its cell. */
  setSpecies(id) {
    const species = this.speciesOf(id);
    if (!species || species === this.species) return;
    const stop = this.activeStop;
    this.species = species;
    this.plan();
    this.clear();
    this.build();
    this.applyPalette(this.stage.palette);
    // Stay at the same level where the species has it; else at its largest.
    const stops = this.currentStops;
    this.activeStop = (stops.find((item) => item.id === stop) || stops[stops.length - 1]).id;
    if (this.selected && !this.has(this.selected)) this.selected = null;
    if (this.active) this.enter();
    this.onChrome?.();
  }

  /** What follows from the species before anything is drawn: its levels, its cell's size and what has no place in it. */
  plan() {
    const species = this.species;
    this.levels = Object.fromEntries(LEVELS.map(({ id }) => [id, species.levels.find((level) => level.id === id) || null]));
    const across = cellAcross(this.levels.cell.shape);
    this.u = across / REF.pitch; // micrometres per unit of the cell's frame
    // A cell this small is drawn in one size mode: its molecules are large enough to see.
    this.small = across < REF.small;
    this.modes = this.small ? ["schematic"] : SIZE_MODES;
    if (!this.modes.includes(this.sizeMode)) this.sizeMode = this.modes[0];
    // What has no place in this species, with the reason the species gives.
    const said = species.cell.capabilities || {};
    const further = species.no_further_levels || "This species has no such level.";
    this.absent = new Map();
    for (const entity of this.model.ofKind("capability")) {
      if (said[entity.id]?.place === "absent") this.absent.set(entity.id, said[entity.id].why);
      else if (entity.scale !== "cell" && !this.levels[entity.scale]) this.absent.set(entity.id, further);
    }
    for (const { id, entity } of LEVELS) if (!this.levels[id]) this.absent.set(entity, further);
  }

  /**
   * Whether a part of the cell is drawn for the species shown. A part that the scene leaves
   * out of the picture for now is not, even as scenery; nor is one whose capability has no
   * place in the species. A part with no capability at all is scenery, and is drawn.
   */
  draws(part) {
    if (this.leftOut.has(part)) return false;
    const entity = this.capabilityByPart.get(part);
    return !entity || !this.absent.has(entity.id);
  }

  /** Takes down what was drawn for the species shown before. */
  clear() {
    this.flux.clear();
    for (const zone of this.zones) {
      this.root.remove(zone.root);
      disposeTree(zone.root);
    }
    this.zones = [];
    this.byEntity.clear();
    this.sceneryLooks.clear();
  }

  // ------------------------------------------------------------ building

  /** A group of things that fade in and out together. `scale` is micrometres per unit, for what is built in the cell's frame. */
  zone(name, mode = null, scale = 1) {
    const zone = { name, mode, range: {}, root: new THREE.Group(), parts: [], neutrals: [], labels: [], fade: -1, cutPlanes: [new THREE.Plane(new THREE.Vector3(0, -1, 0), CUT * scale)] };
    zone.root.scale.setScalar(scale);
    this.zones.push(zone);
    this.root.add(zone.root);
    return zone;
  }

  context(zone) {
    return {
      // A capability that has no place in the species shown is drawn, where its structure
      // is drawn at all, as scenery: nothing to click and no name.
      part: (name, anchor) => {
        const entity = this.capabilityByPart.get(name);
        return this.bind(entity && this.absent.has(entity.id) ? null : entity, zone, anchor, entity ? null : name);
      },
      scale: (id, anchor) => this.bind(this.model.get(id), zone, anchor, id),
      neutral: (options = {}) => {
        const material = new THREE.MeshStandardMaterial({ roughness: 0.6, metalness: 0, transparent: true, side: options.side ?? THREE.FrontSide, depthWrite: options.depthWrite ?? false });
        // Scenery takes the resting look as parts do: light through what is thin, a texture where one is asked for.
        if (options.thin || options.texture) enrich(material, this.stage.numbers, { rim: 0.2, alphaRim: options.glass || 0, thin: options.thin || 0, texture: options.texture || null, unit: zone.root.scale.x });
        else if (options.glass) soften(material, { rim: 0.2, alphaRim: options.glass });
        if (options.drift) jostle(material, this.stage.numbers, { reach: options.drift });
        if (options.contact === false) material.userData.noContact = true; // solid scenery that stays out of contact shade
        if (options.clip) material.clippingPlanes = zone.cutPlanes;
        return this.neutral(zone, material, options);
      },
      neutralPoints: ({ size = 1.4, opacity = 0.6, drift = 0 } = {}) => {
        const material = new THREE.PointsMaterial({ size, sizeAttenuation: false, map: dotTexture(), alphaTest: 0.35, transparent: true, depthWrite: false });
        material.userData = { dust: true };
        if (drift) jostle(material, this.stage.numbers, { reach: drift });
        return this.neutral(zone, material, { opacity });
      },
      neutralLine: (options = {}) =>
        this.neutral(zone, options.dashed ? new THREE.LineDashedMaterial({ transparent: true, dashSize: options.dash ?? 3, gapSize: options.gap ?? 2.2 }) : new THREE.LineBasicMaterial({ transparent: true }), options),
      illustrate: (object, zoneName) => {
        object.userData.unpickable = true;
        (zoneName ? this.zones.find((item) => item.name === zoneName) : zone).root.add(object);
      },
      // Scenery that can be chosen (cell_scenery.js): no capability stands behind it, and the lens describes it by this id.
      scenery: (object, id) => {
        object.userData.pick = id;
        if (!this.sceneryLooks.has(id)) this.sceneryLooks.set(id, new Set());
        object.traverse((item) => item.material && this.sceneryLooks.get(id).add(item.material));
        zone.root.add(object);
      },
      sprite: (part, text, position, size) => {
        const sprite = glyphSprite(text, "#ffffff", size);
        sprite.position.copy(position);
        sprite.userData.unpickable = true;
        sprite.material.toneMapped = false; // a mark, in the page's own ink
        this.neutral(part.zone, sprite.material, { opacity: 0.85, colour: "fg" });
        part.add(sprite);
      },
    };
  }

  build() {
    const species = this.species, u = this.u;
    const notesOf = (level) => (level?.notes || []).map((item) => (typeof item === "string" ? { text: item } : item));
    // The cell, in each size mode it is drawn in. It is built in its own frame and scaled to its size.
    const has = (part) => this.draws(part);
    const cell = { shape: this.levels.cell.shape, parts: species.cell.parts || {}, has, neighbours: Boolean(this.levels.tissue), notes: notesOf(this.levels.cell) };
    const toWorld = (zones) => {
      for (const zone of zones) for (const part of zone.parts) part.anchor?.multiplyScalar(u);
    };
    this.cells = {};
    for (const mode of this.modes) {
      const zones = [this.zone("cell", mode, u), this.zone("studs", mode, u), this.zone("molecules", mode, u)];
      const handles = buildCell(this.context(zones[0]), this.context(zones[1]), mode, cell);
      handles.molecule = buildMolecules(this.context(zones[2]), mode, handles.frame, has);
      toWorld(zones);
      this.cells[mode] = handles;
    }
    // A sheet of the species' own cells, where it forms one.
    this.sheet = null;
    const tissue = this.levels.tissue;
    if (tissue) {
      const zone = this.zone("tissue", null, u);
      const rings = tissue.shape.rings, height = this.cells[this.modes[0]].frame.top * 2;
      this.sheet = buildTissue(this.context(zone), { rings, height, beyond: tissue.shape.beyond ?? [[rings + 2, 0.34], [rings + 4, 0.2], [rings + 5, 0.1]], notes: notesOf(tissue), sides: cell.shape.kind === "prism" ? cell.shape.sides : 6 });
      this.sheet.height = height;
      toWorld([zone]);
    }
    // The larger scales are placeholder outlines, from the species' shape files.
    this.outlines = {};
    const shapes = this.model.raw.shapes || {};
    for (const name of ["organ", "organism"]) {
      const level = this.levels[name], shape = level && shapes[level.shape.ref];
      if (!shape) continue;
      this.outlines[name] = buildOutline(this.context(this.zone(name)), { level, shape, entity: `scale.${name}`, zone: name, sheet: this.sheet ? (this.sheet.extent / 2) * u : 0 });
    }
    // Where the species has no level beyond its cell, zooming out past the cell says so.
    if (species.no_further_levels && !tissue && !this.outlines.organ && !this.outlines.organism) this.zone("beyond");
    this.stops = Object.fromEntries(this.modes.map((mode) => [mode, this.makeStops(mode)]));
    this.setRanges();
    this.flux.build();
  }

  bind(entity, zone, anchor, missing) {
    if (!entity && missing) console.warn(`cell lens: nothing in the scene for "${missing}"; drawn as neutral`);
    const part = new Part(this, entity, zone, anchor);
    if (entity) {
      if (!this.byEntity.has(entity.id)) this.byEntity.set(entity.id, []);
      this.byEntity.get(entity.id).push(part);
    }
    return part;
  }

  neutral(zone, material, { opacity = 0.5, colour = "ghost", natural = null } = {}) {
    // `natural` names the colour a piece of scenery has in life (a chloroplast's green). It wears it
    // where the cell is coloured by kind, and the neutral colour where colour shows status.
    material.userData = { ...material.userData, base: opacity, colour, natural };
    // Scenery in the page's own ink (outlines, marks) stays out of filmic light; glass takes it with the parts.
    material.toneMapped = material.isMeshStandardMaterial === true;
    material.opacity = opacity;
    zone.neutrals.push(material);
    return material;
  }

  /** The stops of the scale rail, one for each level the species has. Sizes are in micrometres. */
  makeStops(mode) {
    const u = this.u;
    const entity = (id) => this.model.get(id);
    const cell = this.cells[mode], molecule = cell.molecule;
    const out = molecule.outward, centre = molecule.centre.clone().multiplyScalar(u), view = molecule.view.map((value) => value * u);
    const stops = [
      { id: "molecule", level: "molecules", zone: "molecules", anchor: centre.clone().addScaledVector(out, view[1] * 0.3), size: view, target: centre.clone(), azimuth: molecule.fromInside ? Math.atan2(-out.x, -out.z) : Math.atan2(out.x, out.z), polar: molecule.fromInside ? 0.42 : 0.6 },
      { id: "cell", level: "cell", zone: "cell", anchor: cell.shape.point(-Math.PI / 2, 1.6, CUT + 2.6).multiplyScalar(u), size: [Math.min(96, Math.max(42, cell.frame.long * 1.3)) * u, 31 * u], target: new THREE.Vector3(0.8 + cell.frame.middle, CUT - 2.6, 0.2).multiplyScalar(u), azimuth: 0.52, polar: 0.84 },
    ];
    if (this.sheet) {
      const extent = this.sheet.extent;
      const spread = this.sheet.spread; // a sheet of squares is wider from corner to corner than a sheet of sixes
      stops.push({ id: "tissue", level: "tissue", zone: "tissue", anchor: new THREE.Vector3(0, this.sheet.height * 2.6, -extent * 0.5).multiplyScalar(u), size: [extent * 1.42 * spread * u, extent * 1.0 * spread * u], target: new THREE.Vector3(0, -6, 0).multiplyScalar(u), azimuth: 0.55, polar: 0.86 });
    }
    // The organ with its surroundings and the sheet's ring in front; then the whole body. Both
    // are seen at a slant, so they have depth. Their frames are as tall as a wide screen needs,
    // so the height sets the distance there and the width only on a tall screen.
    for (const name of ["organ", "organism"]) {
      const outline = this.outlines[name];
      if (outline) stops.push({ id: name, level: name, zone: name, size: outline.frame.frame, target: outline.centre.clone().add(outline.frame.toward), azimuth: outline.frame.azimuth, polar: outline.frame.polar });
    }
    for (const stop of stops) {
      stop.entity = entity(LEVELS.find((level) => level.id === stop.level).entity);
      stop.label = this.levels[stop.level]?.label || stop.entity?.label || stop.id;
    }
    return stops;
  }

  /** Camera distances (in micrometres) at which each level fades in and out. */
  setRanges() {
    const u = this.u;
    const stops = this.stops[this.modes[0]];
    const far = Object.fromEntries(stops.map((stop) => [stop.id, nominal(stop.size)]));
    const chain = stops.map((stop) => stop.id).filter((id) => id !== "molecule");
    // Where one level gives way to the next: as the species says, else between the two stops.
    // Two levels far apart in size do not share a stretch: the smaller goes soon after its stop,
    // and the larger comes shortly before its own.
    const cross = (a, b) => {
      if (far[b] > far[a] * 25) return { out: [far[a] * 2.7, far[a] * 7], in: [far[b] * 0.1, far[b] * 0.5] };
      const shared = far[a] * 2.7 < far[b] * 0.55 ? [far[a] * 2.7, far[b] * 0.55] : [Math.sqrt(far[a] * far[b]) * 0.85, Math.sqrt(far[a] * far[b]) * 1.15];
      return { out: shared, in: shared };
    };
    const ranges = {};
    chain.forEach((name, index) => {
      const level = this.levels[name], before = chain[index - 1], after = chain[index + 1];
      ranges[name] = {};
      if (before) ranges[name].in = level.fade_in_um || cross(before, name).in;
      if (after) ranges[name].out = level.fade_out_um || (far[after] > far[name] * 25 ? null : this.levels[after].fade_in_um) || cross(name, after).out;
    });
    const leave = ranges.cell.out ? { out: ranges.cell.out } : {};
    const byMode = {
      schematic: { molecules: { out: [7 * u, 13 * u] }, studs: leave, cell: leave },
      real: { molecules: { out: [0.45, 1.2] }, studs: { in: [0.5, 1.6], ...leave }, cell: leave },
    };
    for (const zone of this.zones) {
      if (zone.mode) zone.range = byMode[zone.mode][zone.name];
      else if (zone.name === "beyond") zone.range = { in: [far.cell * 1.35, far.cell * 2.1] };
      else zone.range = ranges[zone.name] || {};
    }
    this.ranges = ranges;
    // The camera may go out as far as the largest level needs, and a little beyond. A very long
    // cell is framed at its middle, where its parts are; zooming out shows the whole of it.
    // A thread that stands out from the cell may be many times its length: the cell stays framed
    // as it is, and the camera may go out until the whole of the longest thread is in the picture.
    this.maxDistance = Math.max(Math.max(...stops.map((stop) => stop.size[0]), this.cells[this.modes[0]].frame.long * 1.3 * u) * 4, (this.cells[this.modes[0]].reach || 0) * 3.5 * u);
  }

  /** The camera view that frames a stop on the current screen. */
  stopView(stop) {
    const { camera } = this.stage;
    const half = Math.tan((camera.fov * Math.PI) / 360);
    const distance = Math.max(stop.size[1] / (2 * half), stop.size[0] / (2 * half * camera.aspect));
    return { target: stop.target.clone(), distance, azimuth: stop.azimuth, polar: stop.polar };
  }

  get currentStops() {
    return this.stops[this.sizeMode];
  }

  /** World points the input check clicks; they follow the layout of the current size mode. */
  get probes() {
    return Object.fromEntries(Object.entries(this.cells[this.sizeMode].probes).map(([name, point]) => [name, point.clone().multiplyScalar(this.u)]));
  }

  // ------------------------------------------------------------ lens interface

  has(id) {
    if (this.species.id && id === `species:${this.species.id}`) return true;
    if (this.sceneryItem(id) || this.flux.has(id)) return true;
    return this.model.get(id)?.group === "biology" && !this.absent.has(id);
  }

  /**
   * The species shown, as a part the panel can describe: what Cells models of it, the levels
   * drawn for it, and the capabilities that have no place in it, each with the species' reason.
   */
  describe(id) {
    const species = this.species;
    const sources = species.sources || {};
    const links = (keys) =>
      (keys || [])
        .map((key) => sources[key])
        .filter(Boolean)
        .map((source) => ({ text: source.text, url: source.doi ? `https://doi.org/${source.doi}` : source.url }));
    const scenery = this.sceneryItem(id);
    if (scenery) return describeScenery(scenery, species, links);
    if (this.flux.has(id)) return this.flux.describe(id);
    if (!species.id || id !== `species:${species.id}`) return null;
    const absent = [...this.absent].map(([part, why]) => ({ entity: this.model.get(part), why })).filter((item) => item.entity?.kind === "capability");
    const drawn = LEVELS.filter(({ id: level }) => this.levels[level]).map(({ id: level, entity }) => ({ level: this.levels[level], entity: this.model.get(entity) }));
    return {
      id,
      kind: "species",
      group: "biology",
      label: species.label,
      eyebrow: "Species",
      chips: [{ label: MODELLED[species.modelled.state] || species.modelled.state, title: "What Cells models of this species" }, ...(species.organism ? [{ label: species.organism }] : [])],
      plain: species.modelled.text,
      note: species.plain,
      sections: [
        { title: "Not in this organism", note: "Capabilities of Cells that have no place in this species, each with the reason.", items: absent.map((item) => ({ label: item.entity.label, lines: [item.why] })) },
        { title: "Its cell", items: (species.cell.facts || []).map((fact) => ({ label: fact.label, detail: fact.value, links: links(fact.sources) })) },
        { title: "Levels drawn", note: species.no_further_levels || null, items: drawn.map((item) => ({ label: item.level.label || item.entity?.label || item.level.id, lines: item.level.note ? [item.level.note] : [], links: links(item.level.sources) })) },
      ],
    };
  }

  /** A piece of the species' own scenery that can be chosen (a thread, its foot, a chloroplast), as the size mode shown drew it. */
  sceneryItem(id) {
    if (typeof id !== "string" || !id.startsWith("scenery:")) return null;
    return (this.cells?.[this.sizeMode]?.scenery || []).find((item) => item.id === id) || null;
  }

  entities() {
    return this.model.entities.filter((entity) => entity.group === "biology" && !this.absent.has(entity.id)).map((entity) => this.inSpecies(entity));
  }

  /** A part as the species shown has it: a level under the species' name for it, with what the species says of it. */
  inSpecies(entity) {
    if (!entity || !this.species.id) return entity;
    if (entity.kind === "scale") {
      const level = this.levels[LEVELS.find((item) => item.entity === entity.id)?.id];
      if (!level || (!level.label && !level.note)) return entity;
      return { ...entity, label: level.label || entity.label, note: [entity.note, level.note].filter(Boolean).join(" ") };
    }
    const said = this.species.cell.capabilities?.[entity.id];
    // With what flows through the part, and on what basis it is drawn (layers/cellflux.js).
    return this.flux.inPanel(said?.note ? { ...entity, note: [entity.note, `${this.species.label}: ${said.note}`].filter(Boolean).join(" ") } : entity);
  }

  sections() {
    const capabilities = this.model.ofKind("capability").filter((entity) => !this.absent.has(entity.id));
    return [
      { label: "One cell", entities: capabilities.filter((entity) => entity.scale === "cell") },
      { label: "Tissue", entities: capabilities.filter((entity) => entity.scale === "tissue") },
      { label: "Scales", entities: this.model.ofKind("scale").filter((entity) => !this.absent.has(entity.id)).sort((a, b) => a.order - b.order).map((entity) => this.inSpecies(entity)) },
      { label: "Species", entities: this.species.id ? [this.describe(`species:${this.species.id}`)] : [] },
    ].filter((section) => section.entities.length);
  }

  chrome() {
    const species = this.species;
    // What has no place in this species' cell, in the map's own names, each with the species' reason.
    const absent = [...this.absent].map(([id, why]) => ({ entity: this.model.get(id), why })).filter((item) => item.entity?.kind === "capability").map((item) => ({ label: item.entity.label, why: item.why }));
    return {
      // Of a species that is only proposed, nothing is in the engine (the contract's meaning of the
      // state), so the picture says that in place of the map's caveat about runs.
      caveat: species.modelled?.state === "proposed" ? `${species.label}: nothing of it is in the engine. The picture shows where the capabilities of Cells would have a place in it.` : this.model.raw.caveat,
      rail: this.currentStops.map((stop) => ({ id: stop.id, label: stop.label, title: stop.entity?.plain })),
      railActive: this.activeStop,
      // Where the species has no tissue, organ or body, the rail says so in the species' words.
      railNote: LEVELS.every(({ id }) => this.levels[id]) ? null : species.no_further_levels || null,
      together: (this.model.raw.model_groups || []).map((group) => ({ id: group.id, label: group.label, title: group.description })),
      togetherActive: this.together,
      flux: this.flux.legend(), // the Flux switch and what it shows, for the legend
      view: {
        colour: this.colourBy,
        size: this.sizeMode,
        sizes: this.modes,
        look: this.lookChrome(),
        across: cellAcross(this.levels.cell.shape),
        species: species.id
          ? {
              options: this.list.map((item) => [item.id, item.label, item.organism]),
              active: species.id,
              organism: species.organism,
              plain: species.plain,
              modelled: species.modelled,
              facts: species.cell.facts || [],
              absent,
              sources: species.sources || {},
            }
          : null,
      },
    };
  }

  /** What the scale bar may say: micrometres per unit, or why no bar applies here. */
  scaleInfo() {
    const distance = this.stage.rig.distance, u = this.u;
    if (this.sizeMode === "schematic" && distance < 13 * u) return { note: "Close-up not to scale" };
    // From where the sheet starts to give way to the outlines, the bar says what they are.
    if (this.ranges.tissue?.out && distance > this.ranges.tissue.out[0]) return { micronsPerUnit: 1, note: "the outline is a placeholder" };
    return { micronsPerUnit: 1, note: this.sizeMode === "schematic" && distance < 190 * u ? "small parts enlarged" : null };
  }

  /** Where callout labels go: the cell's centre and radius on screen, or null to label parts in place. */
  calloutFrame() {
    const zone = this.zones.find((item) => item.name === "cell" && item.mode === this.sizeMode);
    const u = this.u;
    if (!zone || zone.fade < 0.6 || this.stage.width < 900 || this.stage.rig.distance < 34 * u) return null;
    const { camera } = this.stage;
    const centre = new THREE.Vector3(0, CUT - 2.2, 0).multiplyScalar(u);
    const span = camera.position.distanceTo(centre) * Math.tan((camera.fov * Math.PI) / 360);
    const screen = this.stage.project(centre, new THREE.Vector3());
    return { x: screen.x, y: screen.y, radius: (R * 1.1 * u * this.stage.height) / (2 * span) };
  }

  get pickRoots() {
    return [this.root];
  }

  activate() {
    const { stage } = this;
    this.active = true;
    stage.scene.add(this.root);
    stage.sun.castShadow = false;
    stage.sun.position.set(55, 100, 80);
    stage.sun.target.position.set(0, 0, 0);
    this.dress();
    this.light();
    this.enter();
    this.refresh();
    if (stage.look.trial) (this.trial ??= new LookTrial(stage)).show();
  }

  // ------------------------------------------------------------ the look at rest

  /**
   * Asks the stage for the rich look (core/look.js), as far as it fits what is shown now.
   * Filmic light is for natural colours: with "Colour: Status" every colour says a status,
   * so it stays as the legend shows it. Contact shade reaches under a micrometre in a cell
   * of twenty, and less when the camera is close (never more than about a fortieth of the
   * picture's height), so that it stays a shade where parts meet and never a haze.
   */
  dress() {
    this.reach = this.reachNow();
    this.stage.dress({ rich: true, filmic: this.colourBy === "biology", exposure: LOOK.exposure, contact: this.near, reach: this.reach, shade: LOOK.shade });
  }

  reachNow() {
    const reach = this.sizeMode === "real" ? LOOK.reachToScale : LOOK.reach;
    return Math.min(reach * this.u, LOOK.reachOnScreen * this.stage.rig.distance);
  }

  /** The legend's Flux switch (layers/cellflux.js): all that flows in the cell, or nothing but a chosen part's. */
  setLayer(id, on) {
    if (id === FLUX_SWITCH) this.flux.setOn(on);
  }

  /** How much a looping run is slowed: 1 is true speed. */
  setSlow(slow) {
    this.flux.setSlow(slow);
  }

  /** The page's address named this part: it is chosen as the page opens and shows no flux until the visitor chooses a part or presses the switch. */
  openedWith(id) {
    this.flux.hold(id);
  }

  /** A choice is about to be set that was made through the page: the same part chosen again counts as the visitor's choice. */
  chosen() {
    this.flux.release();
  }

  /** "rich", "plain", or "full": rich, with every effect held on whatever the frame rate. */
  setLook(word) {
    if (!this.stage.look.choose(word)) return;
    this.stage.invalidate();
    this.onChrome?.();
  }

  /**
   * What the page shows of the look beside its switch: the choice, and a few plain lines.
   * First, in the legend's own word, that what the look adds to surfaces and what it moves
   * is scenery; then what a device that could not keep up has given up; then that motion
   * is held still for a visitor who asks for less of it.
   */
  lookChrome() {
    const look = this.stage.look, still = this.stage.decoration.still;
    const notes = [];
    if (look.rich) {
      const scenery = [look.on("texture") ? "surface texture" : null, look.on("drift") && !still ? "the crowd's slow jostling" : null, look.on("shimmer") && !still ? "the membrane's shimmer" : null].filter(Boolean);
      if (scenery.length) {
        const list = scenery.length > 1 ? `${scenery.slice(0, -1).join(", ")} and ${scenery.at(-1)}` : scenery[0];
        notes.push(`${list[0].toUpperCase()}${list.slice(1)} ${scenery.length > 1 ? "are" : "is"} scenery.`);
      }
      if (look.says()) notes.push(look.says());
      if (still && (look.on("drift") || look.on("shimmer"))) notes.push("The crowd and the membrane are held still: this device asks for less motion.");
    }
    return { active: look.choice, notes };
  }

  /** Puts the camera at the stop the lens stands on, for the species shown, and writes its labels. */
  enter() {
    const { stage } = this;
    stage.raycaster.params.Points.threshold = 0.06 * this.u;
    stage.rig.limits = { minDistance: 0.03 * Math.min(1, this.u), maxDistance: this.maxDistance, minPolar: 0.1, maxPolar: 2.35 };
    stage.rig.setView(this.stopView(this.currentStops.find((stop) => stop.id === this.activeStop)));
    this.buildLabels();
    this.fades(true);
  }

  deactivate() {
    this.active = false;
    this.flux.shine(); // the bloom and the hold on the look's motion go with the view
    this.trial?.hide();
    this.stage.dress({ rich: false }); // the other views keep the look they had
    this.stage.scene.remove(this.root);
    this.stage.scene.environment = null;
    this.stage.applyPalette(); // back to the stage's own lighting
    this.labels.clear();
    this.labels.calloutFrame = null;
  }

  /** This lens's lighting: reflections from its environment, and a little less direct light. */
  light() {
    const { stage } = this;
    const dark = stage.palette.dark, look = stage.look;
    // Studio reflections: large soft lights to catch, in place of the pale dome.
    const studio = look.on("reflections") ? (this.studio ??= makeStudio(stage.renderer)) : null;
    stage.scene.environment = studio || this.environment;
    stage.scene.environmentIntensity = studio ? (dark ? 0.66 : 0.8) : dark ? 0.5 : 0.62;
    stage.sky.intensity = dark ? 0.95 : 1.2;
    stage.sun.intensity = dark ? 1.45 : 1.2;
    this.fill.intensity = dark ? 0.9 : 0.6;
  }

  shows(zone) {
    return !zone.mode || zone.mode === this.sizeMode;
  }

  buildLabels() {
    const labels = this.labels;
    labels.clear();
    labels.calloutFrame = () => this.calloutFrame();
    for (const zone of this.zones) zone.labels = [];
    for (const parts of this.byEntity.values()) {
      for (const part of parts) {
        part.label = null;
        if (!part.anchor || !this.shows(part.zone)) continue;
        const isScale = part.entity.kind === "scale";
        const atCell = part.zone.name === "cell" || part.zone.name === "studs";
        part.label = labels.add({
          id: part.entity.id,
          text: isScale ? this.inSpecies(part.entity).label : part.entity.label,
          anchor: part.anchor,
          priority: isScale ? 300 : this.model.isBuilt(part.entity) ? 40 : 50,
          kind: isScale ? "scale" : "part",
          lift: isScale ? 4 : 9,
          swatch: isScale ? undefined : part.entity.status || "unstated",
          callout: atCell,
        });
        part.zone.labels.push(part.label);
      }
    }
    const zoneOf = (name) => this.zones.find((zone) => zone.name === name && this.shows(zone));
    for (const stop of this.currentStops) {
      if (!stop.anchor || !stop.entity) continue;
      zoneOf(stop.zone).labels.push(labels.add({ id: stop.entity.id, text: stop.label, anchor: stop.anchor, priority: 300, kind: "scale", lift: 4 }));
    }
    // Notes beside the drawing: what the cell and the sheet stand for, and what the
    // placeholder outlines are. A narrow screen gets the short form, or none if it is "roomy".
    const narrow = this.stage.width < 600;
    const note = (zoneName, item) => {
      if (item.roomy && narrow) return;
      zoneOf(zoneName).labels.push(labels.add({ text: narrow && item.short ? item.short : item.text, anchor: item.anchor, priority: item.priority ?? 280, kind: "note", lift: item.lift ?? 0 }));
    };
    // What the cell and the sheet stand for sits just under each stop's name. These two
    // notes give way to the names of parts, so they never hide one.
    const under = (stopId, line = 0) => ({ anchor: this.currentStops.find((stop) => stop.id === stopId).anchor, lift: -19 - line * 20, priority: 30 });
    this.cells[this.sizeMode].notes.forEach((item, line) => note("cell", { ...item, ...under("cell", line) }));
    (this.sheet?.notes || []).forEach((item, line) => note("tissue", { ...item, ...under("tissue", line) }));
    for (const [name, outline] of Object.entries(this.outlines)) {
      for (const item of outline.notes) note(name, item);
    }
    const molecule = this.cells[this.sizeMode].molecule, u = this.u;
    const text = this.sizeMode === "real" ? "To scale: the membrane is about 5 nm thick, the channel about 9 nm across" : molecule.pored ? "Illustration: channels and pumps are modelled as populations" : "Illustration: pumps and transporters are modelled as populations";
    const beside = molecule.centre.clone().multiplyScalar(u).addScaledVector(molecule.outward, -molecule.view[1] * u * 0.3);
    zoneOf("molecules").labels.push(labels.add({ text, anchor: beside, priority: 290, kind: "note", lift: 0 }));
    if (!molecule.pored) {
      // A species without ion channels: the close-up says so in the species' own words, and shows a pump.
      const why = (this.absent.get(this.capabilityByPart.get("channels")?.id) || "").split(/[.:]/)[0].trim();
      const said = why && why.length <= 80 ? why : "Ion channels have no place in this species";
      zoneOf("molecules").labels.push(labels.add({ text: `${said}: the close-up shows a pump`, anchor: beside, priority: 289, kind: "note", lift: -20 }));
    }
    // Past the cell of a species with no further levels: its own sentence, where they would be.
    if (zoneOf("beyond")) note("beyond", { text: this.species.no_further_levels, anchor: new THREE.Vector3(0, 0, R * 1.9 * u), priority: 290 });
    this.flux.label(labels); // what the picture says of the flux it shows
  }

  goToScale(id, immediate = false) {
    const stop = this.currentStops.find((item) => item.id === id);
    if (!stop) return;
    const view = this.stopView(stop);
    this.stage.rig.limits.minDistance = 0.03 * Math.min(1, this.u);
    if (immediate) this.stage.rig.setView(view);
    else this.stage.rig.flyTo(view, 1700);
    this.fades(true);
  }

  setSelection(id) {
    this.selected = id && this.has(id) ? id : null;
    this.refresh();
  }

  setHover(id) {
    const next = id && this.has(id) ? id : null;
    if (next === this.hovered) return;
    this.hovered = next;
    this.refresh();
  }

  setIsolate(status) {
    this.isolate = status || null;
    this.refresh();
  }

  setTogether(groupId) {
    this.together = groupId || null;
    this.refresh();
    this.onChrome?.();
  }

  /** "biology": each kind of part has its own colour. "status": colour shows status, as in the engine lens. */
  setColourBy(mode) {
    this.colourBy = mode === "status" ? "status" : "biology";
    if (this.active) this.dress(); // filmic light is for natural colours only
    this.applyPalette(this.stage.palette);
    this.onChrome?.();
  }

  setSizeMode(mode) {
    if (!this.modes.includes(mode) || mode === this.sizeMode) return;
    const atMolecule = this.activeStop === "molecule";
    this.sizeMode = mode;
    if (this.active) {
      this.buildLabels();
      // The close-up differs by a factor of about a hundred between the modes: go to the new one.
      if (atMolecule) this.goToScale("molecule");
    }
    this.fades(true);
    this.refresh();
    this.onChrome?.();
  }

  lit(entity) {
    if (this.selected && entity.kind === "capability" && entity.id !== this.selected && this.model.get(this.selected)?.kind === "capability") return false;
    if (this.isolate && entity.status !== this.isolate) return false;
    if (this.together && entity.kind === "capability" && !(entity.runs_in || []).includes(this.together)) return false;
    return true;
  }

  refresh() {
    for (const [id, parts] of this.byEntity) {
      const lit = this.lit(parts[0].entity);
      const hot = id === this.selected || id === this.hovered;
      for (const part of parts) {
        part.dim = !lit;
        part.hot = hot;
        part.look(Math.max(0, part.zone.fade), part.dim, part.hot);
        if (part.label) {
          part.label.boost = hot ? 1000 : 0;
          part.label.element.classList.toggle("is-dim", !lit);
          part.label.element.classList.toggle("is-focus", id === this.selected);
        }
      }
    }
    // Scenery that is chosen or under the pointer lights up a little, in its own neutral colour.
    for (const [id, materials] of this.sceneryLooks) {
      const hot = id === this.selected || id === this.hovered;
      for (const material of materials) material.emissive?.copy(material.color).multiplyScalar(hot ? 0.55 : 0);
    }
    this.flux.refresh(); // a chosen part shows its flux
    this.stage.invalidate();
  }

  focus(id) {
    const entity = this.model.get(id);
    if (!entity) return;
    if (entity.kind === "scale") {
      const stop = this.currentStops.find((item) => item.entity?.id === id);
      if (stop) this.goToScale(stop.id);
      return;
    }
    const parts = (this.byEntity.get(id) || []).filter((part) => this.shows(part.zone));
    const part = parts.find((item) => item.anchor) || parts[0];
    if (!part) return;
    const zoneName = part.zone.name === "studs" || part.zone.name === "molecules" ? "cell" : part.zone.name;
    const view = this.stopView(this.currentStops.find((item) => item.zone === zoneName));
    if (zoneName === "cell" && part.anchor) {
      view.target = view.target.clone().lerp(part.anchor, 0.35);
      view.distance *= 0.86;
    }
    this.stage.rig.flyTo(view, 1300);
  }

  // ------------------------------------------------------------ fading between scales

  fades(force = false) {
    const rig = this.stage.rig;
    const distance = rig.distance, u = this.u;
    let changed = false;
    const dust = this.sizeMode === "real" ? smooth(0.5, 1.6, distance) : 1;
    if (Math.abs(dust - this.dustFade) > 0.004) {
      this.dustFade = dust;
      force = true;
    }
    for (const zone of this.zones) {
      const range = zone.range;
      const fade = !this.shows(zone) ? 0 : (range.in ? smooth(range.in[0], range.in[1], distance) : 1) * (range.out ? 1 - smooth(range.out[0], range.out[1], distance) : 1);
      if (!force && Math.abs(fade - zone.fade) < 0.004) continue;
      changed = true;
      zone.fade = fade;
      zone.root.visible = fade > 0.01;
      for (const part of zone.parts) part.look(fade, part.dim, part.hot);
      for (const material of zone.neutrals) {
        material.opacity = material.userData.base * fade * (material.userData.dust ? this.dustFade : 1);
        material.transparent = true;
      }
      for (const label of zone.labels) label.hidden = fade < 0.55;
    }
    // Which stop are we nearest to, on a log scale?
    let nearest = this.activeStop, best = Infinity;
    for (const stop of this.currentStops) {
      const gap = Math.abs(Math.log(distance) - Math.log(this.stopView(stop).distance));
      if (gap < best) {
        best = gap;
        nearest = stop.id;
      }
    }
    if (nearest !== this.activeStop) {
      this.activeStop = nearest;
      this.onChrome?.();
    }
    // Contact shade is worked out only while something solid is near enough to show it, and its
    // reach follows the camera when it comes close.
    if (this.active) {
      const near = this.zones.some((zone) => zone.name !== "organ" && zone.name !== "organism" && zone.name !== "beyond" && zone.fade > 0.02);
      const reach = this.reachNow();
      if (near !== this.near || Math.abs(reach - this.reach) > 0.04 * this.reach) {
        this.near = near;
        this.dress();
      }
    }
    // The camera may come close at the cut edge, but looking at the middle of the cell it stays outside.
    const atEdge = 1 - smooth(0.3, 2.8, this.cells[this.sizeMode].shape.depth({ x: rig.target.x / u, z: rig.target.z / u }));
    rig.limits.minDistance = (R + 6 + (0.03 - R - 6) * atEdge) * u;
    return changed;
  }

  update(dt) {
    const changed = this.fades();
    const flowing = this.flux.frame(); // beads keep their own time
    const near = this.zones.some((zone) => zone.mode === this.sizeMode && zone.fade > 0.02);
    if (!near) return changed || flowing;
    if (this.stage.reducedMotion) {
      this.animate(0.35);
      return changed;
    }
    this.clock += dt / 1000;
    // The cell's own tokens keep a clock of their own: it runs at rest, and holds while any flux shows or the picture
    // is a still one, so that nothing jumps when a part is chosen and they move on from where they stood.
    this.resting ??= 0.35;
    if (!this.flux.flowing && !this.flux.still()) this.resting += dt / 1000;
    this.animate(this.clock, this.resting);
    return true;
  }

  /**
   * The drops where water crosses, the signals that leave and the ions in the close-up's channel
   * are the bodies of their parts, and at rest they move as they always did (the user, 16
   * November 2026: "bring motion back"). Their motion is the picture's own, not a measured
   * flow, and the Flux legend says so (layers/cellflux.js). They stand where they stood for a
   * visitor who asked for less motion, and hold still while any flux shows; while the flux of
   * their part shows they give way to its beads, which are a layer's: drawn out of the look,
   * marked to glow, and holding the look's own motion still. The cages turn in place. The look's
   * motion is not here: the crowd's drift and the membrane's shimmer live in the materials
   * (core/materials.js) and have no direction.
   */
  animate(time, resting = time) {
    const cell = this.cells[this.sizeMode];
    const rest = resting, water = !this.flux.takes("water"), leaving = !this.flux.takes("secretion"), crossing = !this.flux.takes("channels");
    for (const stream of cell.streams) {
      stream.drops.forEach((drop, index) => {
        drop.visible = water;
        const t = (rest * 0.2 + index / stream.drops.length) % 1;
        const offset = stream.inward ? stream.reach - t * stream.reach * 1.9 : -stream.reach * 0.9 + t * stream.reach * 1.9;
        drop.position.copy(stream.at(offset));
        drop.scale.setScalar(0.55 + 0.45 * Math.sin(Math.PI * t));
      });
    }
    cell.signals.forEach((bead, index) => {
      bead.visible = leaving;
      const t = (rest * 0.08 + index / cell.signals.length) % 1;
      bead.position.copy(cell.signalPath(t));
      bead.scale.setScalar(0.5 + 0.7 * Math.sin(Math.PI * Math.min(1, t * 1.15)));
    });
    cell.cages.forEach((cage, index) => cage.rotation.set(time * 0.22 + index, time * 0.35 + index * 2, 0));
    cell.molecule.ions.forEach((ion, index) => {
      ion.visible = crossing;
      const t = (rest * 0.3 + index / cell.molecule.ions.length) % 1;
      ion.position.copy(cell.molecule.ionPath(t));
    });
  }

  applyPalette(palette) {
    for (const zone of this.zones) {
      for (const part of zone.parts) part.colour(palette);
      for (const material of zone.neutrals) {
        const natural = this.colourBy === "biology" ? material.userData.natural : null;
        material.color.set(palette[natural || material.userData.colour] || palette.ghost);
        material.userData.rim?.uRimColor.value.copy(material.color).lerp(WHITE, 0.5);
      }
    }
    if (this.active) this.light();
    this.refresh();
    this.fades(true);
  }

  dispose() {
    this.flux.dispose();
    this.stopLook();
    this.trial?.dispose();
    disposeTree(this.root);
    this.environment?.dispose();
    this.studio?.dispose();
  }
}
